"""Michael's review flags as data (the perceptual study found free-text flags can't be anchored to a region and view):
click a point or drag a box on any board image of a preview page, pick a severity and type a note. Each flag is kept
in charkit/out/previews/flags.jsonl, anchored on the board it was drawn on, whichever picture of it was clicked.

    python -m charkit preview serve [--port 8765] [--open]
        a local server (standard library; 127.0.0.1 only) for charkit/out/previews/: the review pages with the flag
        tools added (charkit/flagui.js), and the flags' API. Open http://localhost:8765/ (the newest preview's page).
        A review page opened as a file still works; it says the flags need this server.

A flag (one JSON object per line of flags.jsonl; flags.log.jsonl keeps every add, edit and delete):
    id, t (when made), edited (when last changed)
    sha, short                   the preview's commit
    image                        the picture clicked, relative to charkit/out/previews (a crop on the page, a board)
    px, box                      the point, or the box [x0, y0, x1, y1] dragged, in that picture's pixels
    board, view, az              the board the picture shows (body_035, design_000, ...), its view and azimuth; for the
                                 design's own pictures, `ref:<the reference's path>`
    board_px, board_box          the same point or box in the board's pixels (a crop's map back: charkit.preview.crops)
    part, region, parts          the object under the point (its bundle name, e.g. clawd_skin, hair_bang_2), its class
                                 (skin, hair, line, ...), and for a box every object's share of it; null when unknown
    part_source                  how the part was found, or why it's null: an ID pass of the build's bundle in the board's
                                 projection (charkit.qa3d's z-buffer; the body and design boards are orthographic and level,
                                 so it's exact), or e.g. "none: perspective board", "none: the bundle was pruned"
    severity                     0 praise, 1 minor, 2 clear, 3 severe
    note

A flag drawn on one picture of a board shows on every picture of that board (the crop, the board itself), placed by the
crops' maps.
"""
import fcntl, glob, html, json, os, re, sys, threading, time, urllib.parse, uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'charkit', 'out', 'previews')
UI = os.path.join(ROOT, 'charkit', 'flagui.js')
SEVERITY = {0: 'praise', 1: 'minor', 2: 'clear', 3: 'severe'}
VIEWS = {0: 'front', 35: 'three_quarter', 90: 'profile', 180: 'back'}
LOCK = threading.Lock()
_maps, _ids = {}, {}


# ------------------------------------------------------------------------------------------------------------ storage
def _path(name='flags.jsonl'):
    return os.path.join(OUT, name)


def load():
    p = _path()
    if not os.path.exists(p):
        return []
    out = []
    for line in open(p):
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out


def _save_all(flags):
    tmp = _path('flags.jsonl.%d.tmp' % os.getpid())
    with open(tmp, 'w') as f:
        for x in flags:
            f.write(json.dumps(x, sort_keys=True) + '\n')
    os.replace(tmp, _path())


def _log(op, flag):
    with open(_path('flags.log.jsonl'), 'a') as f:
        f.write(json.dumps(dict(op=op, at=time.strftime('%Y-%m-%dT%H:%M:%S'), flag=flag), sort_keys=True) + '\n')


class _Locked:
    """the flags file under a lock (threads here, and another server on the same folder)."""
    def __enter__(self):
        LOCK.acquire()
        os.makedirs(OUT, exist_ok=True)
        self.f = open(_path('.flags.lock'), 'w')
        fcntl.flock(self.f, fcntl.LOCK_EX)
        return self

    def __exit__(self, *a):
        self.f.close()
        LOCK.release()


# ------------------------------------------------------------------------------------------------------------ pictures
def _az(board):
    m = re.search(r'_(\d{3})$', board or '')
    return int(m.group(1)) if m else None


def resolve(image):
    """a picture's place: its preview (sha dir), the board it shows and the map from its pixels to the board's ->
    dict(short, sha, board, view, az, map (x0, y0, sx, sy) or None, kind: crop | board | ref | other)."""
    image = image.lstrip('/')
    parts = image.split('/')
    short = parts[0]
    d = os.path.join(OUT, short)
    meta = {}
    if os.path.exists(os.path.join(d, 'preview.json')):
        meta = json.load(open(os.path.join(d, 'preview.json')))
    out = dict(image=image, short=short, sha=meta.get('sha', short), board=None, view=None, az=None, map=None, kind='other')
    name = os.path.basename(image)[:-4] if image.endswith('.png') else None
    if len(parts) == 3 and parts[1] == 'boards' and name:
        out.update(board=name, map=dict(x0=0, y0=0, sx=1.0, sy=1.0), kind='board')
    elif len(parts) == 3 and parts[1] == 'page' and name:
        mp = crop_maps(short).get(name)
        if mp:
            src = mp['src']
            board = src[4:] if src.startswith('ref:') else os.path.basename(src)[:-4]
            out.update(board=('ref:' + board) if src.startswith('ref:') else board,
                       map=dict((k, mp[k]) for k in ('x0', 'y0', 'sx', 'sy')), kind='ref' if src.startswith('ref:') else 'crop')
            if mp.get('view'):
                out['view'] = mp['view']
    elif len(parts) >= 2 and name:
        out.update(board='%s:%s' % (parts[1], name) if len(parts) > 2 else name, map=dict(x0=0, y0=0, sx=1.0, sy=1.0))
    if out['board'] and not out['board'].startswith('ref:'):
        az = _az(out['board'])
        out['az'] = az
        out['view'] = out['view'] or (VIEWS.get(az, 'az%03d' % az) if az is not None else None)
    return out


def crop_maps(short):
    """a preview's crop maps: crops.json's, else (a page made before they were recorded) worked out again from the
    stored boards and the design (charkit.preview.crops(save=False)) and kept in page/maps.json."""
    if short in _maps:
        return _maps[short]
    d = os.path.join(OUT, short)
    cj = os.path.join(d, 'page', 'crops.json')
    mj = os.path.join(d, 'page', 'maps.json')
    maps = {}
    if os.path.exists(cj):
        maps = json.load(open(cj)).get('maps') or {}
    if not maps and os.path.exists(mj):
        maps = json.load(open(mj))
    if not maps and os.path.isdir(os.path.join(d, 'boards')):
        try:
            from . import preview, bundle
            eye_x = 0.168
            try:
                eye_x = float(bundle.load(os.path.join(d, 'bundle')).assembly['eye_knobs']['x'])
            except Exception:
                pass
            maps = preview.crops(d, preview.design_refs(eye_x), log=lambda *a: None, save=False)[2]
            json.dump(maps, open(mj, 'w'), indent=1)
        except Exception as e:
            print('flags: no crop maps for %s: %s' % (short, e), file=sys.stderr)
    _maps[short] = maps
    return maps


def to_board(mp, px=None, box=None):
    if not mp:
        return None, None
    f = lambda x, y: [round(mp['x0'] + x * mp['sx'], 1), round(mp['y0'] + y * mp['sy'], 1)]
    bp = f(*px) if px else None
    bb = (f(box[0], box[1]) + f(box[2], box[3])) if box else None
    return bp, bb


def from_board(mp, bp=None, bb=None):
    if not mp:
        return None, None
    f = lambda x, y: [round((x - mp['x0']) / mp['sx'], 1), round((y - mp['y0']) / mp['sy'], 1)]
    return (f(*bp) if bp else None), ((f(bb[0], bb[1]) + f(bb[2], bb[3])) if bb else None)


# ------------------------------------------------------------------------------------------------------------ the part
def id_pass(short, board):
    """the object and class under every pixel of a board: the build's bundle drawn in the board's projection with the
    QA's z-buffer (charkit.qa3d.scene_objects: every visible object, the skin garment-masked) -> (dict(obj (H, W) index
    into names, cls (H, W) class id, names, classes), None) or (None, why). The body boards (charkit.scene.boards: level,
    orthographic, H 1.12 m across 1000 px round (0, 0, 0.52 H)) and the design boards (level, orthographic, 2.4 L across
    round the head's centre at the eye line) have exact projections; others have none here yet. Cached in
    page/id_<board>.npz."""
    key = (short, board)
    if key in _ids:
        return _ids[key]
    import numpy as np
    d = os.path.join(OUT, short)
    cache = os.path.join(d, 'page', 'id_%s.npz' % board)
    if os.path.exists(cache):
        z = np.load(cache, allow_pickle=False)
        got = dict(obj=z['obj'], cls=z['cls'], names=list(z['names']), classes=json.loads(str(z['classes'])))
        _ids[key] = (got, None)
        return _ids[key]
    kind = board.split('_')[0]
    az = _az(board)
    if kind not in ('body', 'design') or az is None:
        return None, 'none: no ID pass for %s boards (only the orthographic body_* and design_* boards have one)' % (
            kind if kind != 'face' else 'the perspective face_*')
    if not os.path.isdir(os.path.join(d, 'bundle')):
        return None, 'none: this preview\'s bundle was pruned (only the newest previews keep theirs)'
    png = os.path.join(d, 'boards', board + '.png')
    if not os.path.exists(png):
        return None, 'none: no board %s' % board
    from PIL import Image
    from . import bundle, qa3d, bodyqa
    from .detailqa import _Window
    W, H = Image.open(png).size
    B = bundle.load(os.path.join(d, 'bundle'))
    A = B.assembly
    if kind == 'body':
        specs = glob.glob(os.path.join(d, '*.spec.json'))
        h_ = json.load(open(specs[0])).get('body', {}).get('height_m', 1.6) if specs else 1.6
        c, pix = np.array([0.0, 0.0, h_ * 0.52]), h_ * 1.12 / max(W, H)
    else:
        L = float(A['L'])
        c = np.array(A.get('centre') or (0.0, 0.0, 0.0), float)
        c[2] = float(A['eye_z'])
        pix = 2.4 * L / max(W, H)
    meshes, names = qa3d.scene_objects(B)
    fr = _Window(c, az, W / 2 * pix, H / 2 * pix, pix)
    zb, lab, mi, ti, bc = fr.zbuffer(meshes, az, ids=True)
    if mi.shape != (H, W):
        return None, 'none: the ID pass came out %s, the board is %s' % (mi.shape, (H, W))
    classes = {int(v): k for k, v in bodyqa.CLASS.items()}
    got = dict(obj=mi.astype(np.int16), cls=lab.astype(np.int16), names=list(names), classes=classes)
    np.savez_compressed(cache, obj=got['obj'], cls=got['cls'], names=np.array(names), classes=json.dumps(classes))
    _ids[key] = (got, None)
    return _ids[key]


def part_at(short, board, bp=None, bb=None):
    """the part under a board point, or the parts in a board box -> dict(part, region, parts, part_source)."""
    if not board or board.startswith('ref:'):
        return dict(part=None, region=None, parts=None, part_source='none: the design\'s own picture')
    if board.startswith('qa:') or ':' in board:
        return dict(part=None, region=None, parts=None, part_source='none: not a board (a QA overlay or sheet)')
    try:
        got, why = id_pass(short, board)
    except Exception as e:
        return dict(part=None, region=None, parts=None, part_source='none: the ID pass failed (%s)' % str(e)[:200])
    if got is None:
        return dict(part=None, region=None, parts=None, part_source=why)
    import numpy as np
    obj, cls, names = got['obj'], got['cls'], got['names']
    H, W = obj.shape
    src = 'ID pass: the bundle in the board\'s projection (charkit.qa3d z-buffer)'
    name = lambda k: names[k] if 0 <= k < len(names) else None
    region = lambda c: got['classes'].get(int(c), got['classes'].get(str(int(c)))) if c >= 0 else None
    if bb:
        x0, y0 = max(0, int(min(bb[0], bb[2]))), max(0, int(min(bb[1], bb[3])))
        x1, y1 = min(W, int(max(bb[0], bb[2])) + 1), min(H, int(max(bb[1], bb[3])) + 1)
        sub = obj[y0:y1, x0:x1].ravel()
        if not sub.size:
            return dict(part=None, region=None, parts=None, part_source='none: the box is off the board')
        ks, n = np.unique(sub, return_counts=True)
        parts = {(name(int(k)) or 'background'): round(float(c) / sub.size, 3) for k, c in zip(ks, n)}
        fg = [(c, k) for k, c in zip(ks, n) if k >= 0]
        top = int(max(fg)[1]) if fg else -1
        cs = cls[y0:y1, x0:x1].ravel()
        cs = cs[cs >= 0]
        reg = region(np.bincount(cs).argmax()) if cs.size else None
        return dict(part=name(top), region=reg, parts=dict(sorted(parts.items(), key=lambda kv: -kv[1])), part_source=src)
    x, y = int(bp[0]), int(bp[1])
    if not (0 <= x < W and 0 <= y < H):
        return dict(part=None, region=None, parts=None, part_source='none: the point is off the board')
    k = int(obj[y, x])
    if k < 0:
        # the background: the nearest object within 4 px (an outline sits just outside the silhouette)
        ys, xs = np.nonzero(obj[max(0, y - 4):y + 5, max(0, x - 4):x + 5] >= 0)
        if len(ys):
            i = np.argmin((ys - min(4, y)) ** 2 + (xs - min(4, x)) ** 2)
            yy, xx = ys[i] + max(0, y - 4), xs[i] + max(0, x - 4)
            return dict(part=name(int(obj[yy, xx])), region=region(cls[yy, xx]), parts=None,
                        part_source=src + '; the nearest object, %.1f px away' % float(np.hypot(yy - y, xx - x)))
        return dict(part=None, region='background', parts=None, part_source=src + '; nothing drawn there')
    return dict(part=name(k), region=region(cls[y, x]), parts=None, part_source=src)


# ------------------------------------------------------------------------------------------------------------ the API
def _clean(v, n):
    if v is None:
        return None
    v = [round(float(x), 1) for x in v]
    if len(v) != n:
        raise ValueError('expected %d numbers' % n)
    return v


def add(body):
    where = resolve(body['image'])
    px, box = _clean(body.get('px'), 2), _clean(body.get('box'), 4)
    if px is None and box is None:
        raise ValueError('a flag needs px or box')
    if box:
        box = [min(box[0], box[2]), min(box[1], box[3]), max(box[0], box[2]), max(box[1], box[3])]
        px = px or [round((box[0] + box[2]) / 2, 1), round((box[1] + box[3]) / 2, 1)]
    sev = int(body.get('severity', 2))
    if sev not in SEVERITY:
        raise ValueError('severity is 0 (praise) .. 3 (severe)')
    bp, bb = to_board(where['map'], px, box)
    f = dict(id='f%s-%s' % (time.strftime('%m%d%H%M%S'), uuid.uuid4().hex[:4]), t=time.strftime('%Y-%m-%dT%H:%M:%S'),
             sha=where['sha'], short=where['short'], image=where['image'], px=px, box=box, board=where['board'],
             view=where['view'], az=where['az'], board_px=bp, board_box=bb, severity=sev,
             severity_name=SEVERITY[sev], note=str(body.get('note', '')).strip())
    f.update(part_at(where['short'], where['board'], bp, bb if box else None))
    with _Locked():
        with open(_path(), 'a') as fh:
            fh.write(json.dumps(f, sort_keys=True) + '\n')
        _log('add', f)
    return f


def edit(fid, body):
    with _Locked():
        flags = load()
        hit = [f for f in flags if f['id'] == fid]
        if not hit:
            raise KeyError(fid)
        f = hit[0]
        if 'severity' in body:
            if int(body['severity']) not in SEVERITY:
                raise ValueError('severity is 0 .. 3')
            f['severity'] = int(body['severity'])
            f['severity_name'] = SEVERITY[f['severity']]
        if 'note' in body:
            f['note'] = str(body['note']).strip()
        f['edited'] = time.strftime('%Y-%m-%dT%H:%M:%S')
        _save_all(flags)
        _log('edit', f)
    return f


def delete(fid):
    with _Locked():
        flags = load()
        keep = [f for f in flags if f['id'] != fid]
        if len(keep) == len(flags):
            raise KeyError(fid)
        _save_all(keep)
        _log('delete', [f for f in flags if f['id'] == fid][0])
    return dict(deleted=fid)


def view(images):
    """for each picture on a page: where it is (resolve) and the flags on its board, placed in its pixels."""
    flags = load()
    out = {}
    for im in images:
        w = resolve(im)
        on = []
        for f in flags:
            if f['short'] != w['short'] and not (w['board'] or '').startswith('ref:'):
                continue
            if f['image'] == w['image']:
                on.append(dict(f, at=dict(px=f['px'], box=f['box'])))
            elif w['board'] and f.get('board') == w['board'] and w['map'] and f.get('board_px'):
                px, box = from_board(w['map'], f['board_px'], f.get('board_box'))
                on.append(dict(f, at=dict(px=px, box=box)))
        out[im] = dict((k, w[k]) for k in ('short', 'sha', 'board', 'view', 'az', 'kind'))
        out[im]['flags'] = on
    return out


# ------------------------------------------------------------------------------------------------------------ the server
class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=OUT, **kw)

    def log_message(self, fmt, *a):
        if os.environ.get('CHARKIT_FLAGS_VERBOSE'):
            super().log_message(fmt, *a)

    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(b)

    def _body(self):
        n = int(self.headers.get('Content-Length') or 0)
        return json.loads(self.rfile.read(n) or b'{}')

    def _html(self, text):
        b = text.encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        try:
            if u.path == '/api/ping':
                return self._json(dict(ok=True, flags=len(load())))
            if u.path == '/api/flags':
                fl = load()
                if q.get('sha'):
                    fl = [f for f in fl if f['sha'].startswith(q['sha'][0]) or f['short'] == q['sha'][0]]
                return self._json(fl)
            if u.path == '/flags.js':
                b = open(UI, 'rb').read()
                self.send_response(200)
                self.send_header('Content-Type', 'application/javascript')
                self.send_header('Content-Length', str(len(b)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                return self.wfile.write(b)
            if u.path in ('/', '/index.html'):
                return self._html(index_page())
            if u.path == '/view':
                return self._html(viewer_page(q.get('src', [''])[0]))
            if u.path.endswith('.html'):
                p = self.translate_path(u.path)
                if os.path.isfile(p):
                    t = open(p, encoding='utf-8', errors='replace').read()
                    if 'flags.js' not in t:
                        t += '\n<script src="/flags.js"></script>\n'
                    return self._html(t)
            if u.path.endswith('/boards/'):
                return self._html(board_list(u.path.strip('/')))
        except Exception as e:
            return self._json(dict(error=str(e)), 500)
        return super().do_GET()

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        try:
            if u.path == '/api/flags':
                return self._json(add(self._body()), 201)
            if u.path == '/api/view':
                return self._json(view(self._body().get('images', [])))
            if u.path.startswith('/api/flags/'):
                return self._json(edit(u.path.rsplit('/', 1)[1], self._body()))
        except KeyError as e:
            return self._json(dict(error='no flag %s' % e), 404)
        except (ValueError, TypeError) as e:
            return self._json(dict(error=str(e)), 400)
        except Exception as e:
            return self._json(dict(error=str(e)), 500)
        self._json(dict(error='not found'), 404)

    do_PUT = do_POST

    def do_DELETE(self):
        u = urllib.parse.urlparse(self.path)
        try:
            if u.path.startswith('/api/flags/'):
                return self._json(delete(u.path.rsplit('/', 1)[1]))
        except KeyError as e:
            return self._json(dict(error='no flag %s' % e), 404)
        self._json(dict(error='not found'), 404)


def index_page():
    rows = []
    idx = os.path.join(OUT, 'index.jsonl')
    fl = load()
    for line in reversed(open(idx).read().splitlines() if os.path.exists(idx) else []):
        r = json.loads(line)
        n = sum(f['short'] == r['short'] for f in fl)
        rows.append('<tr><td><a href="/%s/review.html"><code>%s</code></a></td><td>%s</td><td>%s</td><td>%s</td>'
                    '<td><a href="/%s/boards/">boards</a></td></tr>' % (
                        r['short'], r['short'], html.escape(r.get('subject', '')), r.get('t', ''),
                        '%d flag%s' % (n, 's' * (n != 1)) if n else '', r['short']))
    return ('<!doctype html><meta charset="utf-8"><title>Previews</title><style>body{font:14px/1.45 -apple-system,'
            'system-ui,sans-serif;margin:20px;background:#f6f5f2;color:#222}td{padding:4px 10px;border-bottom:1px solid #ddd}'
            '</style><h1>charkit previews</h1><p>Open a preview, press <b>F</b> (or the Flag button), then click a point or '
            'drag a box on any picture. Flags: <code>%s</code> (<a href="/api/flags">all, as JSON</a>).</p>'
            '<table>%s</table><script src="/flags.js"></script>' % (html.escape(_path()), ''.join(rows)))


def board_list(rel):
    d = os.path.join(OUT, rel)
    ims = sorted(f for f in os.listdir(d) if f.endswith('.png')) if os.path.isdir(d) else []
    return ('<!doctype html><meta charset="utf-8"><title>%s</title><style>body{font:14px/1.45 -apple-system,system-ui,'
            'sans-serif;margin:20px;background:#f6f5f2}a{margin-right:12px}</style><h2>%s</h2><p>%s</p>' % (
                html.escape(rel), html.escape(rel), ' '.join('<a href="/view?src=%s/%s">%s</a>' % (
                    urllib.parse.quote(rel), urllib.parse.quote(f), html.escape(f[:-4])) for f in ims)))


def viewer_page(src):
    src = src.lstrip('/')
    return ('<!doctype html><meta charset="utf-8"><title>%s</title><style>body{font:14px/1.45 -apple-system,system-ui,'
            'sans-serif;margin:20px;background:#f6f5f2}img{display:block;border:1px solid #ddd;background:#fff}</style>'
            '<p><a href="/%s/review.html">the review page</a> &middot; <a href="/%s/boards/">all boards</a> &middot; '
            '<code>%s</code> at its own size</p><img src="/%s"><script src="/flags.js"></script>' % (
                html.escape(src), html.escape(src.split('/')[0]), html.escape(src.split('/')[0]), html.escape(src),
                html.escape(src)))


def serve(port=8765, open_page=False):
    os.makedirs(OUT, exist_ok=True)
    srv = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    url = 'http://localhost:%d/' % port
    print('flags: serving %s at %s (flags in %s); Ctrl-C stops it' % (OUT, url, _path()), flush=True)
    if open_page:
        import subprocess
        latest = os.path.join(OUT, 'latest.html')
        subprocess.run(['open', url + ('latest.html' if os.path.exists(latest) else '')])
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


def main(args):
    port = int(args[args.index('--port') + 1]) if '--port' in args else 8765
    return serve(port, '--open' in args)
