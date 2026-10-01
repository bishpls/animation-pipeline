"""Human labelling pages served locally (tool/hairident; Michael 2026-10-01: pages that ask him to label or confirm things
save every answer on the click, resume where he left off, undo, keyboard first, the agent's proposal preselected).

A task is a JSON file (charkit-label-task/1): pictures of one subject in several views, regions on them (masks or
polygons, each with an id), and items to answer one at a time. An item is a region in its home view; in each other
view the agent proposes the region that is the same thing (or "not visible"), with a reason and a confidence, and the
human accepts it, picks the right region, or says it isn't visible / unsure. Generic: cross-view lock identity (the
hair), garment layers, a new character's pieces all fit it.

    python -m charkit label serve TASK.json [--port 8770] [--no-open] [--answers PATH]
        a local server (standard library; binds 127.0.0.1 only) for the page; every answer is written to the
        answers JSON at once (atomic replace), with its history (undo); reopening resumes at the first open item
    python -m charkit label status TASK.json [--answers PATH]
        progress: answered, unsure, skipped, and the links as answered

TASK.json (paths relative to the task's folder):
  format      "charkit-label-task/1"
  id, title   the task's name and the page's title
  summary     {"asked": "what is asked, one or two sentences", "minutes": 15, "used_for": "what the answers feed"}
  answers     the answers file (default: answers.json beside the task)
  views       [{"id", "name", "image", "alt": {"label": image} (other pictures of the same view at the same pixels,
              toggled with C)}]: one picture per view; all views are drawn at one scale (their own pixels)
  regions     {view: [{"id", "polygon": [[x, y], ...] or "polygons": [ring, ...] (even-odd: holes are rings too),
              "label" (optional display text), "info" (optional, shown on hover)}]
              or {"mask": "index.png", "ids": [...]} (pixel value k > 0 is ids[k - 1])}
  items       [{"id", "number", "group", "title", "reason", "home": {"view", "regions": [ids]},
              "ask": [views] (optional: only these views are asked; default every view but the home),
              "context": {view: {"regions": [ids], "points": [[x, y]], "note": "..."}} (optional: shown, not asked),
              "proposals": {view: {"regions": [ids] (empty: not visible), "confidence": 0..1, "reason": "...",
              "where": [x0, y0, x1, y1] (optional: where to look when hidden)}}}]
  keys        optional notes on the keys (the page has its own legend)

Answers (charkit-label-answers/1): {"items": {item: {"views": {view: {"verdict": accept | fixed | hidden | unsure |
point, "regions": [...], "points": [[x, y], ...] (point: present there, marked on the picture: no region there), "t"}},
"status": open | done | skipped, "seconds"}}, "cursor", "history" [every change with its
before and after: undo pops it], "undone" [the undone changes, for the record]}.
"""
import copy, hashlib, html, json, os, sys, threading, time, urllib.parse, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASK_FORMAT = 'charkit-label-task/1'
ANSWERS_FORMAT = 'charkit-label-answers/1'
UI = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'labelui.html')
VERDICTS = ('accept', 'fixed', 'hidden', 'unsure', 'point')   # point: present where marked, no region there
STATUSES = ('open', 'done', 'skipped')
SIMPLIFY_PX = 0.8          # a mask's outline simplified to within this many pixels


# ------------------------------------------------------------------------------------------------------------ task

def mask_polygons(mask, tol=SIMPLIFY_PX):
    """a bool mask -> its outline as rings [[x, y], ...] (outer edges and holes alike: drawn even-odd), simplified to
    within tol px, on pixel corners (x right, y down; a pixel (r, c) spans [c, c + 1] x [r, r + 1])."""
    import numpy as np
    from skimage import measure
    m = np.pad(np.asarray(mask, bool), 1).astype(float)
    rings = []
    for cnt in measure.find_contours(m, 0.5):
        if len(cnt) < 4:
            continue
        cnt = measure.approximate_polygon(cnt, tol)
        # find_contours' (row, col) on the padded grid at pixel centres -> x, y on pixel corners
        rings.append([[round(float(c) - 0.5, 2), round(float(r) - 0.5, 2)] for r, c in cnt])
    return rings


def _ring_area(ring):
    s = 0.0
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
        s += x0 * y1 - x1 * y0
    return s / 2


def _anchor(rings, mask=None):
    """where a region's label goes: the point deepest inside it (a mask's distance transform's peak), else the largest
    ring's centroid."""
    import numpy as np
    if mask is not None and mask.any():
        from scipy import ndimage
        d = ndimage.distance_transform_edt(np.pad(mask, 1))[1:-1, 1:-1]
        r, c = np.unravel_index(int(np.argmax(d)), d.shape)
        return [float(c) + 0.5, float(r) + 0.5]
    big = max(rings, key=lambda q: abs(_ring_area(q)))
    a = _ring_area(big) or 1e-9
    cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(big, big[1:] + big[:1]):
        f = x0 * y1 - x1 * y0
        cx += (x0 + x1) * f
        cy += (y0 + y1) * f
    return [cx / (6 * a), cy / (6 * a)]


def _bbox(rings):
    xs = [p[0] for q in rings for p in q]
    ys = [p[1] for q in rings for p in q]
    return [min(xs), min(ys), max(xs), max(ys)]


def load_task(path):
    """the task with its regions resolved to polygons (a mask's regions traced) -> dict (the page's /api/task)."""
    import numpy as np
    path = os.path.abspath(path)
    T = json.load(open(path))
    if T.get('format') != TASK_FORMAT:
        raise SystemExit('%s: not a %s task' % (path, TASK_FORMAT))
    base = os.path.dirname(path)
    views = []
    for v in T['views']:
        q = dict(v)
        q['image_path'] = os.path.join(base, v['image'])
        q['alt_paths'] = {k: os.path.join(base, p) for k, p in (v.get('alt') or {}).items()}
        try:
            from PIL import Image
            q['size'] = list(Image.open(q['image_path']).size)
        except Exception:
            q['size'] = v.get('size')
        views.append(q)
    regions = {}
    for vid, R in (T.get('regions') or {}).items():
        out = []
        if isinstance(R, dict) and 'mask' in R:
            from PIL import Image
            idx = np.asarray(Image.open(os.path.join(base, R['mask'])))
            if idx.ndim == 3:                       # an RGB-coded index: r + 256 g + 65536 b
                idx = idx[..., 0].astype(np.int64) + 256 * idx[..., 1] + 65536 * idx[..., 2]
            for k, rid in enumerate(R['ids']):
                m = idx == k + 1
                if not m.any():
                    continue
                rings = mask_polygons(m)
                if rings:
                    info = (R.get('info') or {}).get(rid)
                    out.append(dict(id=rid, rings=rings, anchor=_anchor(rings, m), bbox=_bbox(rings), area=int(m.sum()),
                                    label=(R.get('labels') or {}).get(rid), info=info))
        else:
            for r in R:
                rings = r.get('polygons') or [r['polygon']]
                out.append(dict(id=r['id'], rings=rings, anchor=r.get('anchor') or _anchor(rings), bbox=_bbox(rings),
                                area=int(sum(abs(_ring_area(q)) for q in rings)), label=r.get('label'),
                                info=r.get('info')))
        regions[vid] = out
    ids = {v: {r['id'] for r in rs} for v, rs in regions.items()}
    problems = []
    for it in T['items']:
        h = it['home']
        for rid in h['regions']:
            if rid not in ids.get(h['view'], ()):
                problems.append('item %s: home region %s not in view %s' % (it['id'], rid, h['view']))
        for vid, p in (it.get('proposals') or {}).items():
            for rid in p.get('regions') or []:
                if rid not in ids.get(vid, ()):
                    problems.append('item %s: proposed region %s not in view %s' % (it['id'], rid, vid))
    if problems:
        raise SystemExit('task problems:\n  ' + '\n  '.join(problems))
    sha = hashlib.sha256(open(path, 'rb').read()).hexdigest()[:12]
    ans = T.get('answers') or 'answers.json'
    return dict(T, path=path, sha=sha, views=views, regions=regions,
                answers_path=ans if os.path.isabs(ans) else os.path.join(base, ans))


def public_task(task):
    """what the page gets: no local paths."""
    t = {k: v for k, v in task.items() if k not in ('path', 'answers_path')}
    t['views'] = [{k: v for k, v in q.items() if k not in ('image_path', 'alt_paths', 'image', 'alt')} |
                  dict(src='/img/%s' % urllib.parse.quote(q['id']),
                       alts={k: '/img/%s/%s' % (urllib.parse.quote(q['id']), urllib.parse.quote(k))
                             for k in q['alt_paths']}) for q in task['views']]
    t['answers_file'] = os.path.relpath(task['answers_path'], ROOT) if task['answers_path'].startswith(ROOT) else \
        task['answers_path']
    return t


# ------------------------------------------------------------------------------------------------------------ answers

class Store:
    """the answers file: every change written at once (a temporary file beside it, then os.replace), with its history."""

    def __init__(self, task, path=None):
        self.task = task
        self.path = os.path.abspath(path or task['answers_path'])
        self.lock = threading.Lock()
        self.items = {it['id']: it for it in task['items']}
        self.order = [it['id'] for it in task['items']]
        if os.path.exists(self.path):
            self.A = json.load(open(self.path))
            if self.A.get('task_sha') != task['sha']:
                # the task was rebuilt: the answers stay keyed by item id (an item that kept its id keeps its answer)
                print('note: %s answered task %s; the task is now %s' % (self.path, self.A.get('task_sha'), task['sha']))
                self.A.setdefault('task_shas', []).append(self.A.get('task_sha'))
                self.A['task_sha'] = task['sha']
        else:
            now = time.time()
            self.A = dict(format=ANSWERS_FORMAT, task=os.path.relpath(task['path'], ROOT)
                          if task['path'].startswith(ROOT) else task['path'], task_sha=task['sha'], created=now,
                          updated=now, cursor=self.order[0] if self.order else None, items={}, history=[], undone=[])
        self.A.setdefault('items', {})
        self.A.setdefault('history', [])
        self.A.setdefault('undone', [])

    def other_views(self, item):
        """the views an item asks about: its `ask` list, else every view but its home."""
        it = self.items[item]
        if it.get('ask'):
            return list(it['ask'])
        return [v['id'] for v in self.task['views'] if v['id'] != it['home']['view']]

    def _save(self):
        self.A['updated'] = time.time()
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = '%s.%d.%d.tmp' % (self.path, os.getpid(), threading.get_ident())
        with open(tmp, 'w') as f:
            json.dump(self.A, f, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)

    def _item(self, item):
        return self.A['items'].setdefault(item, dict(views={}, status='open', seconds=0.0))

    def _status(self, item):
        rec = self._item(item)
        if rec['status'] == 'skipped':
            return
        need = self.other_views(item)
        rec['status'] = 'done' if all(v in rec['views'] for v in need) else 'open'

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.A)

    def answer(self, item, view, verdict, regions=None, seconds=None, points=None):
        """one view's answer for an item -> the answers."""
        if item not in self.items:
            raise ValueError('no item %r' % item)
        if view not in self.other_views(item):
            raise ValueError('item %r: %r is not one of its other views' % (item, view))
        if verdict not in VERDICTS:
            raise ValueError('verdict %r not one of %s' % (verdict, VERDICTS))
        it = self.items[item]
        prop = (it.get('proposals') or {}).get(view) or {}
        if verdict == 'accept':
            regions = list(prop.get('regions') or [])
        elif verdict == 'hidden':
            regions = []
        regions = list(regions or [])
        pts = None
        if verdict == 'point':
            # where the lock is, marked on the picture (no region there): [x, y] in the view's image pixels
            size = next((v.get('size') for v in self.task['views'] if v['id'] == view), None)
            pts = [[round(float(p[0]), 1), round(float(p[1]), 1)] for p in (points or [])]
            if not pts:
                raise ValueError('a point answer needs points')
            if size and any(not (0 <= p[0] <= size[0] and 0 <= p[1] <= size[1]) for p in pts):
                raise ValueError('points outside the picture')
            regions = []
        known = {r['id'] for r in self.task['regions'].get(view, ())}
        bad = [r for r in regions if r not in known]
        if bad:
            raise ValueError('regions %s not in view %s' % (bad, view))
        with self.lock:
            rec = self._item(item)
            before = copy.deepcopy(rec)
            rec['views'][view] = dict(verdict=verdict, regions=regions, t=time.time())
            if pts is not None:
                rec['views'][view]['points'] = pts
            if rec['status'] == 'skipped':
                rec['status'] = 'open'
            if seconds is not None:
                rec['seconds'] = round(float(seconds), 1)
            self._status(item)
            self.A['history'].append(dict(t=time.time(), item=item, op='answer', view=view, before=before,
                                          after=copy.deepcopy(rec)))
            self.A['cursor'] = item
            self._save()
            return copy.deepcopy(self.A)

    def accept_all(self, item, seconds=None):
        """every view of the item not yet answered takes its proposal (Enter) -> the answers."""
        it = self.items[item]
        with self.lock:
            rec = self._item(item)
            before = copy.deepcopy(rec)
            for v in self.other_views(item):
                if v in rec['views']:
                    continue
                prop = (it.get('proposals') or {}).get(v)
                if prop is None:
                    continue
                rec['views'][v] = dict(verdict='accept', regions=list(prop.get('regions') or []), t=time.time())
            if rec['status'] == 'skipped':
                rec['status'] = 'open'
            if seconds is not None:
                rec['seconds'] = round(float(seconds), 1)
            self._status(item)
            self.A['history'].append(dict(t=time.time(), item=item, op='accept_all', before=before,
                                          after=copy.deepcopy(rec)))
            self.A['cursor'] = item
            self._save()
            return copy.deepcopy(self.A)

    def clear(self, item, view, seconds=None):
        """a view's answer taken back (to answer it again) -> the answers."""
        with self.lock:
            rec = self._item(item)
            if view not in rec['views']:
                return copy.deepcopy(self.A)
            before = copy.deepcopy(rec)
            del rec['views'][view]
            if seconds is not None:
                rec['seconds'] = round(float(seconds), 1)
            self._status(item)
            self.A['history'].append(dict(t=time.time(), item=item, op='clear', view=view, before=before,
                                          after=copy.deepcopy(rec)))
            self._save()
            return copy.deepcopy(self.A)

    def skip(self, item, seconds=None):
        with self.lock:
            rec = self._item(item)
            before = copy.deepcopy(rec)
            rec['status'] = 'skipped'
            if seconds is not None:
                rec['seconds'] = round(float(seconds), 1)
            self.A['history'].append(dict(t=time.time(), item=item, op='skip', before=before, after=copy.deepcopy(rec)))
            self.A['cursor'] = item
            self._save()
            return copy.deepcopy(self.A)

    def cursor(self, item, seconds=None, prev=None):
        """the item on screen (resume returns there); seconds: the time spent on the item just left."""
        with self.lock:
            if prev is not None and seconds is not None and prev in self.items:
                self._item(prev)['seconds'] = round(float(seconds), 1)
            self.A['cursor'] = item
            self._save()
            return copy.deepcopy(self.A)

    def undo(self):
        """the last change taken back -> (the answers, the item it touched or None)."""
        with self.lock:
            if not self.A['history']:
                return copy.deepcopy(self.A), None
            h = self.A['history'].pop()
            self.A['items'][h['item']] = copy.deepcopy(h['before'])
            self.A['undone'].append(dict(h, undone_at=time.time()))
            self.A['cursor'] = h['item']
            self._save()
            return copy.deepcopy(self.A), h['item']

    def resume_at(self):
        """the item to open: the saved cursor if it is still open, else the first open item, else the cursor."""
        st = {k: v.get('status') for k, v in self.A['items'].items()}
        c = self.A.get('cursor')
        if c in self.items and st.get(c, 'open') == 'open':
            return c
        for k in self.order:
            if st.get(k, 'open') == 'open':
                return k
        return c if c in self.items else (self.order[0] if self.order else None)


def links(task, A):
    """the answers as links: per item, per view, the regions it is (the home view's own, then each answered view's)
    -> {item: {view: [regions] | None (hidden) | 'unsure' | 'unanswered'}}."""
    out = {}
    for it in task['items']:
        rec = A['items'].get(it['id'], {})
        q = {it['home']['view']: list(it['home']['regions'])}
        for v in task['views']:
            if v['id'] == it['home']['view']:
                continue
            a = rec.get('views', {}).get(v['id'])
            if a is None:
                q[v['id']] = 'skipped' if rec.get('status') == 'skipped' else 'unanswered'
            elif a['verdict'] == 'unsure':
                q[v['id']] = 'unsure'
            elif a['verdict'] == 'point':
                q[v['id']] = {'points': a.get('points', [])}       # present there, marked by points
            elif a['verdict'] == 'hidden' or not a['regions']:
                q[v['id']] = None                   # not visible there (said so, or the accepted proposal was)
            else:
                q[v['id']] = list(a['regions'])
        out[it['id']] = q
    return out


def progress(task, A):
    st = [A['items'].get(it['id'], {}).get('status', 'open') for it in task['items']]
    unsure = sorted({it['id'] for it in task['items']
                     for a in A['items'].get(it['id'], {}).get('views', {}).values() if a['verdict'] == 'unsure'})
    fixed = sum(1 for it in task['items'] for a in A['items'].get(it['id'], {}).get('views', {}).values()
                if a['verdict'] == 'fixed')
    acc = sum(1 for it in task['items'] for a in A['items'].get(it['id'], {}).get('views', {}).values()
              if a['verdict'] == 'accept')
    secs = [A['items'][it['id']].get('seconds', 0) for it in task['items']
            if A['items'].get(it['id'], {}).get('status') == 'done']
    return dict(items=len(st), done=st.count('done'), skipped=st.count('skipped'), open=st.count('open'),
                unsure=unsure, accepted_views=acc, fixed_views=fixed, seconds=round(sum(secs), 1))


# ------------------------------------------------------------------------------------------------------------ server

def make_server(task_path, port=8770, answers=None, tries=20):
    """the page's server on 127.0.0.1 (the first free port from `port`) -> (server, store)."""
    task = load_task(task_path)
    store = Store(task, answers)
    pub = public_task(task)
    files = {}
    for q in task['views']:
        files['/img/%s' % urllib.parse.quote(q['id'])] = q['image_path']
        for k, p in q['alt_paths'].items():
            files['/img/%s/%s' % (urllib.parse.quote(q['id']), urllib.parse.quote(k))] = p

    class H(BaseHTTPRequestHandler):
        def log_message(self, fmt, *a):
            pass

        def _send(self, code, body, ctype='application/json'):
            b = body if isinstance(body, bytes) else body.encode()
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(b)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(b)

        def _json(self, obj, code=200):
            self._send(code, json.dumps(obj))

        def do_GET(self):
            p = urllib.parse.urlparse(self.path).path
            if p in ('/', '/index.html'):
                self._send(200, open(UI).read().replace('__TITLE__', html.escape(task.get('title', 'Labelling'))),
                           'text/html; charset=utf-8')
            elif p == '/api/task':
                self._json(pub)
            elif p == '/api/answers':
                A = store.snapshot()
                self._json(dict(answers=A, resume=store.resume_at(), progress=progress(task, A)))
            elif p in files:
                ext = os.path.splitext(files[p])[1].lower()
                self._send(200, open(files[p], 'rb').read(),
                           {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp'}
                           .get(ext, 'application/octet-stream'))
            else:
                self._send(404, '{"error": "not found"}')

        def do_POST(self):
            p = urllib.parse.urlparse(self.path).path
            try:
                n = int(self.headers.get('Content-Length') or 0)
                body = json.loads(self.rfile.read(n) or b'{}')
                touched = body.get('item')
                if p == '/api/answer':
                    A = store.answer(body['item'], body['view'], body['verdict'], body.get('regions'),
                                     body.get('seconds'), body.get('points'))
                elif p == '/api/accept_all':
                    A = store.accept_all(body['item'], body.get('seconds'))
                elif p == '/api/clear':
                    A = store.clear(body['item'], body['view'], body.get('seconds'))
                elif p == '/api/skip':
                    A = store.skip(body['item'], body.get('seconds'))
                elif p == '/api/cursor':
                    A = store.cursor(body['item'], body.get('seconds'), body.get('prev'))
                elif p == '/api/undo':
                    A, touched = store.undo()
                else:
                    return self._send(404, '{"error": "not found"}')
            except (ValueError, KeyError) as e:
                return self._json(dict(error=str(e)), 400)
            self._json(dict(answers=A, touched=touched, progress=progress(task, A)))

    last = None
    for k in range(tries):
        try:
            srv = ThreadingHTTPServer(('127.0.0.1', port + k if port else 0), H)
            break
        except OSError as e:
            last = e
    else:
        raise SystemExit('no free port from %d: %s' % (port, last))
    srv.daemon_threads = True
    return srv, store


def serve(task_path, port=8770, open_page=True, answers=None):
    srv, store = make_server(task_path, port, answers)
    url = 'http://127.0.0.1:%d/' % srv.server_address[1]
    pr = progress(store.task, store.snapshot())
    print('labelling %s: %s' % (store.task.get('title', ''), url))
    print('answers saved on every click to %s (%d / %d done)' % (store.path, pr['done'], pr['items']))
    sys.stdout.flush()
    if open_page:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


def status(task_path, answers=None):
    task = load_task(task_path)
    store = Store(task, answers)
    A = store.snapshot()
    pr = progress(task, A)
    print('%s: %d / %d done, %d skipped, %d open; views accepted %d, fixed %d; unsure: %s; %.0f s spent' % (
        store.path, pr['done'], pr['items'], pr['skipped'], pr['open'], pr['accepted_views'], pr['fixed_views'],
        ', '.join(pr['unsure']) or 'none', pr['seconds']))
    for k, q in links(task, A).items():
        print('  %-28s %s' % (k, '  '.join('%s=%s' % (v, '|'.join(x) if isinstance(x, list) else ('hidden' if x is None else (
            'point %s' % x['points'] if isinstance(x, dict) else x))) for v, x in q.items())))
    return 0


def _opt(args, name, default=None):
    return args[args.index(name) + 1] if name in args else default


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    cmd, rest = args[0], args[1:]
    if cmd == 'serve':
        serve(rest[0], int(_opt(rest, '--port', 8770)), '--no-open' not in rest, _opt(rest, '--answers'))
        return 0
    if cmd == 'status':
        return status(rest[0], _opt(rest, '--answers'))
    raise SystemExit('unknown label command %r\n%s' % (cmd, __doc__))


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
