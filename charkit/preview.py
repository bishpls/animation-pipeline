"""The combined preview after a merge (Michael, 2026-09-30: review never depends on someone asking for it): a pipeline-3d
commit built on the render box with boards, stored per commit under charkit/out/previews/<sha>/, and a review page:
the design, the previous preview and this one at matching figure height; the head in the design's own projection
(level, orthographic, at head_turnaround's scale) beside the design's four heads; a turntable in that projection; the
QA tallied against the previous preview (FAIL -> PASS, PASS -> FAIL, the checks a measurement step between the two
changed).

    python -m charkit preview [REF] [--spec SPEC] [--box render] [--force] [--open]
                                             build REF (default HEAD) and write its page (run it in the background)
    python -m charkit preview --tip BRANCH   the same for BRANCH's tip as it is once the previous preview is done (the
                                             hook's form: merges in a burst preview their last commit once)
    python -m charkit preview --page SHA     the page again from the stored build
    python -m charkit preview serve [--port 8765] [--open]
                                             the previews at http://localhost:8765/ with click-to-flag on every picture:
                                             a point or a box, a severity (0 praise .. 3 severe), a note; saved to
                                             charkit/out/previews/flags.jsonl with the board, view and part under it
                                             (charkit/flags.py)
    python -m charkit preview hook install|remove|status
                                             a post-merge hook in this worktree (per-worktree core.hooksPath) that runs
                                             `preview --tip BRANCH` in the background after a merge on BRANCH
                                             (default: this worktree's branch); it never blocks the merge

The toon renderer's parity: the build's EEVEE boards against charkit.render's from the build's export (python -m
charkit.render compare, drawn where the page is made), per board the mean difference, the silhouette's IoU and the ink's
mean width, flagged past PARITY; the side-by-side page is toonrender/index.html.

The commit is built in its own detached worktree (../animation-pipeline-autopreview, kept between previews, so its box
copy syncs only what changed) whatever this worktree's state; previews queue on a lock. The page is
charkit/out/previews/<sha>/review.html, and charkit/out/previews/latest.html points at the newest.

Close-ups: the build's `design` board (charkit.scene.boards: EEVEE, orthographic and level at the eye line), cropped to
the design's window round its eye line and scaled to one px per L with it; for a commit without that board, the head is
drawn from the build's geometry bundle in the venv (charkit.qa3d.draw: the QA's own renderer, in the same projection),
and the page says which.
"""
import fcntl, glob, html, json, os, shutil, subprocess, sys, time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
OUT = os.path.join(ROOT, 'charkit', 'out', 'previews')
BUILD_WT = os.path.join(os.path.dirname(ROOT), 'animation-pipeline-autopreview')
SPEC = 'charkit/spec/clawd.json'
BOARDS = 'views,body,design'
DESIGN_VIEWS = (('front', 0), ('three_quarter', 35), ('profile', 90), ('back', 180))
BODY_AZ = (0, 35, 90, 180)                 # the body boards (charkit.scene.boards 'body'), the design's four figures
WIN = dict(up=1.2, down=1.0, half=1.0)     # the close-ups' window round the eye line, in L (the design's heads fit it)
PPL_OUT = 300                              # the close-ups' px per L on the page
BODY_H = 560                               # the full figures' height on the page (px)
KEEP_BUNDLES = 4                           # the newest previews keep their geometry bundle (the venv close-ups read it)
RANK = {'PASS': 0, 'WARN': 1, 'FAIL': 2}
DESIGN_WINDOW, DESIGN_PPL = 2.4, 400      # the build's design board (charkit.scene.boards): L across, px per L


# what git exports to a hook's processes: a git command run with them acts on the hooked repository whatever its cwd
# (the post-merge hook's preview once detached pipeline-3d's HEAD and force-checked-out there, 2026-09-30)
GIT_HOOK_ENV = ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_PREFIX', 'GIT_COMMON_DIR', 'GIT_OBJECT_DIRECTORY',
                'GIT_ALTERNATE_OBJECT_DIRECTORIES', 'GIT_QUARANTINE_PATH', 'GIT_NAMESPACE')


def _clean_env():
    """the environment without git's hook variables (GIT_HOOK_ENV)."""
    return {k: v for k, v in os.environ.items() if k not in GIT_HOOK_ENV}


def _git(*a, cwd=ROOT, check=True):
    r = subprocess.run(['git', *a], cwd=cwd, capture_output=True, text=True, env=_clean_env())
    if check and r.returncode:
        raise SystemExit('git %s: %s' % (' '.join(a), r.stderr.strip()))
    return r.stdout.strip()


def _short(sha):
    return sha[:7]


# ------------------------------------------------------------------------------------------------------------ the build
def build_worktree(sha, spec=SPEC):
    """the preview's own worktree, detached at sha (created on first use: sparse like a gate's, with the box configs and
    charkit/out/i3d copied from this worktree). -> its path."""
    from . import sparse
    wt = BUILD_WT
    if not os.path.exists(os.path.join(wt, '.git')):
        _git('worktree', 'add', '--no-checkout', '--detach', wt, sha)
    _git('sparse-checkout', 'set', '--cone', *sparse.dirs('charkit', spec), cwd=wt)
    _git('checkout', '-q', '-f', '--detach', sha, cwd=wt)
    for f in glob.glob(os.path.join(ROOT, 'infra', 'gcp', '*.env')):
        os.makedirs(os.path.join(wt, 'infra', 'gcp'), exist_ok=True)
        shutil.copyfile(f, os.path.join(wt, 'infra', 'gcp', os.path.basename(f)))
    src, dst = os.path.join(ROOT, 'charkit', 'out', 'i3d'), os.path.join(wt, 'charkit', 'out', 'i3d')
    if os.path.isdir(src) and not os.path.isdir(dst):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if subprocess.run(['cp', '-Rc', src, dst], capture_output=True).returncode:      # APFS clone: no space
            shutil.copytree(src, dst)
    return wt


def build(sha, spec=SPEC, box='render', log=print):
    """sha built on the box with the preview's boards, into charkit/out/previews/<short> here -> that folder."""
    short = _short(sha)
    wt = build_worktree(sha, spec)
    rel = os.path.join('charkit', 'out', 'previews', short)
    shutil.rmtree(os.path.join(wt, rel), ignore_errors=True)
    t = time.time()
    cmd = [PY, '-m', 'charkit', 'remote', '--box', box, 'build', spec, '--out', rel, '--boards', BOARDS, '--no-blend']
    log('preview %s: %s (in %s)' % (short, ' '.join(cmd[2:]), wt))
    r = subprocess.run(cmd, cwd=wt, capture_output=True, text=True, env=_clean_env())
    src = os.path.join(wt, rel)
    if r.returncode or not os.path.exists(os.path.join(src, 'qa', 'qa.json')):
        raise SystemExit('preview %s: the build failed (exit %d)\n%s' % (short, r.returncode, (r.stdout + r.stderr)[-3000:]))
    dst = os.path.join(OUT, short)
    shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(OUT, exist_ok=True)
    shutil.move(src, dst)
    shutil.rmtree(os.path.join(dst, 'geom'), ignore_errors=True)            # the build's intermediate geometry
    json.dump({'sha': sha, 'spec': spec, 'box': box, 'boards': BOARDS, 'seconds': round(time.time() - t)},
              open(os.path.join(dst, 'preview.json'), 'w'), indent=1)
    return dst


# ------------------------------------------------------------------------------------------------------------ the design
def _load(path):
    from PIL import Image
    return np.asarray(Image.open(path).convert('RGB'), float) / 255.0


def _save(a, path):
    from PIL import Image
    Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)).save(path)


def _resize(a, w, h):
    from PIL import Image
    im = Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8))
    return np.asarray(im.resize((max(1, int(round(w))), max(1, int(round(h)))), Image.LANCZOS), float) / 255.0


def _fg(rgb, bg=None, thr=0.08):
    """pixels that differ from the background (the corners' median colour, or bg)."""
    if bg is None:
        c = np.concatenate([rgb[:8, :8].reshape(-1, 3), rgb[:8, -8:].reshape(-1, 3), rgb[-8:, :8].reshape(-1, 3),
                            rgb[-8:, -8:].reshape(-1, 3)])
        bg = np.median(c, 0)
    return np.abs(rgb - np.asarray(bg)).max(-1) > thr


def _cut(rgb, x0, y0, x1, y1, fill):
    """rgb[y0:y1, x0:x1] with rows and columns outside the image filled."""
    H, W = rgb.shape[:2]
    out = np.empty((y1 - y0, x1 - x0, 3))
    out[:] = fill
    sx0, sy0, sx1, sy1 = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
    if sx1 > sx0 and sy1 > sy0:
        out[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = rgb[sy0:sy1, sx0:sx1]
    return out


def head_crop(rgb, eye_y, ppl, cx=None, xlim=None, bg=None, clip=False, want_map=False):
    """the close-up window (WIN, in L) round the eye line at eye_y, centred on the head's columns (the foreground's
    extent from the window's top to 0.4 L under the eyes, within the columns xlim; or cx), resampled to PPL_OUT px per
    L. clip: the columns outside xlim blanked (a sheet's neighbouring figures). want_map: also the crop's map back to
    the source's pixels (source = x0 + crop * sx; charkit.flags anchors a review flag on the board with it)."""
    fill = np.median(rgb[:8, :8].reshape(-1, 3), 0) if bg is None else bg
    if clip and xlim is not None:
        rgb = rgb.copy()
        rgb[:, :max(0, int(xlim[0]))] = fill
        rgb[:, int(xlim[1]):] = fill
    y0, y1 = int(round(eye_y - WIN['up'] * ppl)), int(round(eye_y + WIN['down'] * ppl))
    if cx is None:
        a, b = (0, rgb.shape[1]) if xlim is None else (max(0, int(xlim[0])), min(rgb.shape[1], int(xlim[1])))
        band = _fg(rgb[max(y0, 0):int(round(eye_y + 0.4 * ppl)), a:b], fill)
        cols = np.nonzero(band.any(0))[0] + a
        cx = (cols[0] + cols[-1]) / 2 if len(cols) else (a + b) / 2
    hw = int(round(WIN['half'] * ppl))
    x0 = int(round(cx)) - hw
    c = _cut(rgb, x0, y0, x0 + 2 * hw, y1, fill)
    out = _resize(c, 2 * WIN['half'] * PPL_OUT, (WIN['up'] + WIN['down']) * PPL_OUT)
    if want_map:
        return out, dict(x0=x0, y0=y0, sx=c.shape[1] / out.shape[1], sy=c.shape[0] / out.shape[0])
    return out


def figure_crop(rgb, box=None, bg=None, pad=0.02, want_map=False):
    """a full figure cut to its box (or its foreground's) with a little room, scaled to BODY_H px tall. want_map: also
    the map back to the source's pixels (head_crop's)."""
    if box is None:
        m = _fg(rgb, bg)
        rows, cols = np.nonzero(m.any(1))[0], np.nonzero(m.any(0))[0]
        if not len(rows):
            out = _resize(rgb, rgb.shape[1] * BODY_H / rgb.shape[0], BODY_H)
            mp = dict(x0=0, y0=0, sx=rgb.shape[1] / out.shape[1], sy=rgb.shape[0] / out.shape[0])
            return (out, mp) if want_map else out
        box = [cols[0], rows[0], cols[-1] + 1, rows[-1] + 1]
    x0, y0, x1, y1 = box
    p = int(round(pad * (y1 - y0)))
    fill = np.median(rgb[:8, :8].reshape(-1, 3), 0)
    c = _cut(rgb, int(x0) - p, int(y0) - p, int(x1) + p, int(y1) + p, fill)
    out = _resize(c, c.shape[1] * BODY_H / c.shape[0], BODY_H)
    if want_map:
        return out, dict(x0=int(x0) - p, y0=int(y0) - p, sx=c.shape[1] / out.shape[1], sy=c.shape[0] / out.shape[0])
    return out


def design_refs(eye_x=0.168):
    """the design's pictures for the page: head_turnaround's four heads (each view's eye line and px per L: the kit's
    convention, its front eyes 2 eye_x L apart; charkit.refcheck) and body_turnaround's four figures (their boxes;
    charkit.sheetqa.detect_figures). -> dict, with the files' paths."""
    from . import refcheck, sheetqa
    man = json.load(open(os.path.join(ROOT, 'charkit', 'refs', 'clawd', 'manifest.json')))['references']
    hp = os.path.join(ROOT, man['head_turnaround']['path'])
    bp = os.path.join(ROOT, man['body_turnaround']['path'])
    rgb = _load(hp)
    rgb0, _ = refcheck.without_guides(rgb)
    _, f, H = refcheck.at_scale(rgb0, eye_x, 2 * eye_x * refcheck.FACE_PPL, -1)
    heads = {v: dict(eye_y=h['eye_y'] / f, box=[b / f for b in h['box']]) for v, h in H['heads'].items()}
    fe, te = (H['heads'].get(v, {}).get('eyes') or [] for v in ('front', 'three_quarter'))
    az3 = float(np.degrees(np.arccos(np.clip(abs(te[1][0] - te[0][0]) / abs(fe[1][0] - fe[0][0]), 0, 1)))) \
        if len(fe) == 2 and len(te) == 2 else None
    D = sheetqa.detect_figures(_load(bp), None, eye_x, -1)
    return dict(head=hp, body=bp, head_ppl=refcheck.FACE_PPL / f, heads=heads, az3=az3,
                figures={v: D['figures'][v]['box'] for v in D['figures']})


# ------------------------------------------------------------------------------------------------------------ ours
def draw_design_view(B, az, ppl=PPL_OUT, ss=2):
    """the head drawn from a geometry bundle in the design's projection (orthographic, level at the eye line, the
    close-up window round the head's centre) with the QA's renderer (charkit.qa3d.draw: toon materials, outlines, the
    boards' light for the view) on the world's colour -> RGB floats at ppl px per L, the eye line WIN['up'] L down."""
    from . import qa3d
    from .detailqa import _Window
    L = float(B.assembly['L'])
    c = np.array(B.assembly['centre'], float)
    c[2] = float(B.assembly['eye_z'])
    up, down, half = WIN['up'], WIN['down'], WIN['half']
    c[2] += (up - down) / 2 * L                                    # the window's centre (_Window is symmetric)
    fr = _Window(c, az, half * L, (up + down) / 2 * L, L / ppl / ss)
    surfs = []
    for o in B.objects():
        variant = 'masked' if o.group == 'skin' and o.has('masked') else 'eval'
        if o.has(variant):
            surfs += qa3d.surfaces(B, o, variant)
    img = qa3d.draw(B, surfs, az, fr, transparent=True, ss=ss)
    a = img[..., 3:4]
    return img[..., :3] * a + np.asarray(qa3d._srgb(np.array(qa3d.WORLD)))[None, None] * (1 - a)


def our_heads(d, log=print, maps=None):
    """ours in the design's projection for each design view: the build's design board cropped (its eye line is the
    board's middle row; DESIGN_PPL px per L), else drawn from its bundle. -> ({view: crop}, source). maps (a dict):
    gets each board crop's map back to its board (head_crop's want_map), as 'head_<view>'."""
    out = {}
    boards = os.path.join(d, 'boards')
    if all(os.path.exists(os.path.join(boards, 'design_%03d.png' % az)) for _, az in DESIGN_VIEWS):
        for v, az in DESIGN_VIEWS:
            rgb = _load(os.path.join(boards, 'design_%03d.png' % az))
            out[v], mp = head_crop(rgb, rgb.shape[0] / 2, rgb.shape[0] / DESIGN_WINDOW, want_map=True)
            if maps is not None:
                maps['head_' + v] = dict(mp, src='boards/design_%03d.png' % az)
        return out, 'EEVEE design board (orthographic, level, %d px/L)' % DESIGN_PPL
    if not os.path.isdir(os.path.join(d, 'bundle')):
        return {}, 'none (no design board and no bundle)'
    from . import bundle
    B = bundle.load(os.path.join(d, 'bundle'))
    for v, az in DESIGN_VIEWS:
        rgb = draw_design_view(B, az)
        out[v] = head_crop(rgb, WIN['up'] * PPL_OUT, PPL_OUT)
    return out, 'venv drawing from the bundle (this commit has no design board): orthographic, level'


# ------------------------------------------------------------------------------------------------------------ the QA
def tally(cur, prev=None, remeasured=None):
    """the QA counted and, against a previous preview's, the status changes -> dict(counts, prev_counts, changes
    {'FAIL -> PASS': [...], ...}, improved, regressed, new, gone, fails, remeasured (the changed checks a measurement step
    between the two covers))."""
    import fnmatch
    cc = {k: c.get('status') for k, c in cur.get('checks', {}).items()}
    count = lambda s: {k: sum(v == k for v in s.values()) for k in ('PASS', 'WARN', 'FAIL', 'INFO', 'SKIPPED')}
    out = dict(counts=count(cc), fails=sorted(k for k, v in cc.items() if v == 'FAIL'))
    if prev is None:
        return out
    pc = {k: c.get('status') for k, c in prev.get('checks', {}).items()}
    ch = {}
    for k in sorted(set(cc) & set(pc)):
        if pc[k] != cc[k] and pc[k] in RANK and cc[k] in RANK:
            ch.setdefault('%s -> %s' % (pc[k], cc[k]), []).append(k)
    val = lambda q, k: q.get('checks', {}).get(k, {}).get('value')
    rem = [k for k in sorted(set(cc) | set(pc)) if any(fnmatch.fnmatchcase(k, p) for p in (remeasured or {}))
           and (pc.get(k), val(prev, k)) != (cc.get(k), val(cur, k))]
    out.update(prev_counts=count(pc), changes=ch,
               improved=sorted(k for k in set(cc) & set(pc) if pc[k] in RANK and cc[k] in RANK and RANK[cc[k]] < RANK[pc[k]]),
               regressed=sorted(k for k in set(cc) & set(pc) if pc[k] in RANK and cc[k] in RANK and RANK[cc[k]] > RANK[pc[k]]),
               new=sorted(k for k in set(cc) - set(pc) if cc[k] in RANK),
               gone=sorted(k for k in set(pc) - set(cc) if pc[k] in RANK), remeasured=rem)
    return out


# ------------------------------------------------------------------------------------------------------------ the index
def index():
    p = os.path.join(OUT, 'index.jsonl')
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []


def previous(sha):
    """the preview to compare sha with: the newest earlier preview of an ancestor commit, else the newest other one."""
    rows = [r for r in index() if r['sha'] != sha and os.path.exists(os.path.join(OUT, r['short'], 'qa', 'qa.json'))]
    anc = [r for r in rows if subprocess.run(['git', '-C', ROOT, 'merge-base', '--is-ancestor', r['sha'], sha],
                                             capture_output=True).returncode == 0]
    return (anc or rows or [None])[-1]


def _record(row):
    rows = [r for r in index() if r['sha'] != row['sha']] + [row]
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'index.jsonl'), 'w') as f:
        for r in rows:
            f.write(json.dumps(r) + '\n')


def _prune_bundles():
    """only the newest KEEP_BUNDLES previews keep their geometry bundle (17-25 MB each)."""
    for r in index()[:-KEEP_BUNDLES]:
        shutil.rmtree(os.path.join(OUT, r['short'], 'bundle'), ignore_errors=True)


# ------------------------------------------------------------------------------------------------------------ the page
def crops(d, design, log=print, save=True):
    """the page's pictures for one preview, written under d/page/: our close-ups and full figures, and (once per
    preview, so a page never depends on another worktree's files) the design's. Each crop's map back to the picture it
    was cut from (a board, or a design sheet) goes into crops.json's `maps` (charkit.flags anchors review flags on the
    board with it). save=False: only the maps (for a page made before they were recorded). -> {name: relative path},
    source, maps."""
    pd = os.path.join(d, 'page')
    os.makedirs(pd, exist_ok=True)
    got, maps = {}, {}
    put = (lambda img, name: _save(img, os.path.join(pd, name + '.png'))) if save else (lambda img, name: None)
    heads, source = our_heads(d, log, maps)
    for v, img in heads.items():
        put(img, 'head_' + v); got['head_' + v] = 'page/head_%s.png' % v
    for az in BODY_AZ:
        p = os.path.join(d, 'boards', 'body_%03d.png' % az)
        if os.path.exists(p):
            img, mp = figure_crop(_load(p), want_map=True)
            put(img, 'body_%03d' % az); got['body_%03d' % az] = 'page/body_%03d.png' % az
            maps['body_%03d' % az] = dict(mp, src='boards/body_%03d.png' % az)
    hr = _load(design['head'])
    for v, _ in DESIGN_VIEWS:
        h = design['heads'].get(v)
        if h:
            m = 0.03 * design['head_ppl']
            img, mp = head_crop(hr, h['eye_y'], design['head_ppl'], xlim=(h['box'][0] - m, h['box'][2] + m), clip=True,
                                want_map=True)
            put(img, 'design_head_' + v)
            got['design_head_' + v] = 'page/design_head_%s.png' % v
            maps['design_head_' + v] = dict(mp, src='ref:' + os.path.relpath(design['head'], ROOT), view=v)
    br = _load(design['body'])
    for v in ('front', 'three_quarter', 'profile', 'back'):
        if v in design['figures']:
            img, mp = figure_crop(br, design['figures'][v], want_map=True)
            put(img, 'design_body_' + v)
            got['design_body_' + v] = 'page/design_body_%s.png' % v
            maps['design_body_' + v] = dict(mp, src='ref:' + os.path.relpath(design['body'], ROOT), view=v)
    tt = sorted(glob.glob(os.path.join(d, 'boards', 'design_*.png')))
    for p in tt:
        rgb = _load(p)
        name = os.path.basename(p)[:-4]
        hc, mp = head_crop(rgb, rgb.shape[0] / 2, rgb.shape[0] / DESIGN_WINDOW, want_map=True)
        img = _resize(hc, 180 * 2 * WIN['half'] / (WIN['up'] + WIN['down']), 180)
        put(img, 'tt_' + name)
        got['tt_' + name] = 'page/tt_%s.png' % name
        maps['tt_' + name] = dict(x0=mp['x0'], y0=mp['y0'], sx=mp['sx'] * hc.shape[1] / img.shape[1],
                                  sy=mp['sy'] * hc.shape[0] / img.shape[0], src='boards/%s.png' % name)
    if save:
        json.dump(dict(got=got, source=source, maps=maps), open(os.path.join(pd, 'crops.json'), 'w'), indent=1)
    return got, source, maps


def _fig(src, cap, h=None):
    st = ' style="height:%dpx"' % h if h else ''
    return '<figure><a href="%s"><img src="%s"%s></a><figcaption>%s</figcaption></figure>' % (
        html.escape(src), html.escape(src), st, cap)


def page(sha, spec=SPEC, log=print):
    """the review page for a stored preview -> its path."""
    from . import history
    short = _short(sha)
    d = os.path.join(OUT, short)
    qa = json.load(open(os.path.join(d, 'qa', 'qa.json')))
    eye_x = 0.168
    try:
        from . import bundle
        eye_x = float(bundle.load(os.path.join(d, 'bundle')).assembly['eye_knobs']['x'])
    except Exception:
        pass
    design = design_refs(eye_x)
    got, source, _ = crops(d, design, log)
    prev = previous(sha)
    pgot = {}
    if prev:
        pj = os.path.join(OUT, prev['short'], 'page', 'crops.json')
        pgot = {k: '../%s/%s' % (prev['short'], v) for k, v in (json.load(open(pj))['got'] if os.path.exists(pj) else {}).items()}
    pqa = json.load(open(os.path.join(OUT, prev['short'], 'qa', 'qa.json'))) if prev else None
    rem = history.steps_between(prev['sha'], sha) if prev else {}
    T = tally(qa, pqa, rem)
    subject = _git('log', '-1', '--format=%s', sha)
    when = _git('log', '-1', '--format=%ci', sha)
    meta = json.load(open(os.path.join(d, 'preview.json'))) if os.path.exists(os.path.join(d, 'preview.json')) else {}
    row = dict(sha=sha, short=short, t=time.strftime('%Y-%m-%dT%H:%M:%S'), subject=subject, spec=spec,
               counts=T['counts'], prev=prev and prev['sha'])
    _record(row)

    def counts(c):
        return ' / '.join('%d %s' % (c.get(k, 0), k) for k in ('PASS', 'WARN', 'FAIL', 'INFO') if c.get(k))

    def lst(title, ks, bold=False):
        if not ks:
            return ''
        t = '<b>%s</b>' % title if bold else title
        return '<p>%s (%d): %s</p>' % (t, len(ks), ', '.join(
            '<code>%s</code>%s' % (html.escape(k), '*' if k in T.get('remeasured', []) else '') for k in ks))

    P = ['<!doctype html><meta charset="utf-8"><title>Clawd preview %s</title>' % short,
         '<style>body{font:14px/1.45 -apple-system,system-ui,sans-serif;margin:20px;background:#f6f5f2;color:#222}'
         'h2{margin:26px 0 6px}.row{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end}'
         'figure{margin:0;background:#fff;border:1px solid #ddd;border-radius:6px;padding:6px}'
         'figure img{display:block}figcaption{font-size:12px;color:#444;margin-top:4px;max-width:600px}'
         '.box{background:#fff;border:1px solid #ddd;border-radius:6px;padding:10px 14px;max-width:1200px}'
         'code{font-size:12px}.grid{display:grid;grid-template-columns:repeat(3,auto);gap:10px;justify-content:start}'
         '.k{color:#666;font-size:12px}table{border-collapse:collapse;font-size:13px}'
         'td,th{padding:2px 10px;border-bottom:1px solid #eee;text-align:left}</style>',
         '<h1>Clawd preview: <code>%s</code></h1>' % short,
         '<div class="box"><b>%s</b><br><span class="k">%s &middot; spec <code>%s</code> &middot; built on the %s box '
         '(boards %s, %s s) &middot; page %s</span><br>Previous: %s</div>' % (
             html.escape(subject), when, spec, meta.get('box', '?'), meta.get('boards', '?'), meta.get('seconds', '?'),
             time.strftime('%Y-%m-%d %H:%M'),
             ('<a href="../%s/review.html"><code>%s</code></a> %s' % (prev['short'], prev['short'], html.escape(prev['subject'])))
             if prev else 'none (the first preview)')]
    # the QA tally
    Q = ['<p>this preview: <b>%s</b>' % counts(T['counts'])]
    if prev:
        Q[0] += ' &middot; previous (%s): %s' % (prev['short'], counts(T['prev_counts']))
        ch = T['changes']
        Q += [lst('FAIL &rarr; PASS', ch.get('FAIL -> PASS'), True), lst('FAIL &rarr; WARN', ch.get('FAIL -> WARN')),
              lst('WARN &rarr; PASS', ch.get('WARN -> PASS')),
              lst('PASS &rarr; FAIL', ch.get('PASS -> FAIL'), True), lst('WARN &rarr; FAIL', ch.get('WARN -> FAIL'), True),
              lst('PASS &rarr; WARN', ch.get('PASS -> WARN')), lst('new graded checks', T['new']),
              lst('graded checks gone', T['gone'], True)]
        if not ch:
            Q.append('<p>No graded check changed status.</p>')
        if rem:
            Q.append('<p class="k">* a measurement step between the two commits covers the check (its number is not '
                     'comparable): %s</p>' % '; '.join('<code>%s</code>' % html.escape(k) for k in rem))
    Q.append(lst('all FAILs now', T['fails']))
    P += ['<h2>QA tally</h2><div class="box">%s</div>' % ''.join(Q)]
    # the full figures
    cols = [('design (body_turnaround)', lambda v, az: got.get('design_body_' + v))]
    if prev:
        cols.append(('previous (%s)' % prev['short'], lambda v, az: pgot.get('body_%03d' % az)))
    cols.append(('this preview (%s)' % short, lambda v, az: got.get('body_%03d' % az)))
    P.append('<h2>Full figure: design, previous, this (each cut to its figure, all %d px tall)</h2>' % BODY_H)
    for title, f in cols:
        P.append('<div class="row">%s</div>' % ''.join(
            _fig(f(v, az), '%s, %s' % (title, v.replace('_', ' ')), BODY_H // 2) for v, az in
            zip(('front', 'three_quarter', 'profile', 'back'), BODY_AZ) if f(v, az)))
    # the heads in the design's projection
    P.append('<h2>Head in the design\'s projection (orthographic, level at the eye line; %d px per L; the eye line '
             '%.1f L from the top)</h2><div class="box k">Ours: %s. The design: head_turnaround at its own scale (%.0f px '
             'per L, its front eyes 2 x %.3f L apart), each view cut round its eye line. Its three-quarter is turned %s '
             'degrees; ours %d.</div>' % (PPL_OUT, WIN['up'], html.escape(source), design['head_ppl'], eye_x,
                                         '%.1f' % design['az3'] if design['az3'] else '?', DESIGN_VIEWS[1][1]))
    for v, az in DESIGN_VIEWS:
        figs = [_fig(got.get('design_head_' + v), 'design, %s' % v.replace('_', ' '))] if got.get('design_head_' + v) else []
        if prev and pgot.get('head_' + v):
            figs.append(_fig(pgot['head_' + v], 'previous (%s), %d&deg;' % (prev['short'], az)))
        if got.get('head_' + v):
            figs.append(_fig(got['head_' + v], 'this preview, %d&deg;' % az))
        P.append('<div class="row">%s</div>' % ''.join(figs))
    tt = sorted(k for k in got if k.startswith('tt_'))
    if tt:
        P.append('<h2>Turntable in the design\'s projection</h2><div class="row">%s</div>' % ''.join(
            _fig(got[k], '%s&deg;' % int(k.split('_')[-1])) for k in tt))
    # the toon renderer against this build's EEVEE boards (the standing parity test after each merge)
    P.append(parity_section(d, parity(d, log=log)))
    # the rest of the build
    links = sorted(glob.glob(os.path.join(d, 'qa', 'qa_*.png'))) + sorted(glob.glob(os.path.join(d, 'sheet_*.png')))
    P.append('<h2>Files</h2><div class="box">QA overlays: %s<br>boards: <a href="boards/">boards/</a> &middot; '
             '<a href="qa/qa.json">qa.json</a> &middot; <a href="trace.jsonl">trace</a></div>' % ' &middot; '.join(
                 '<a href="%s">%s</a>' % (os.path.relpath(p, d), os.path.basename(p)[:-4]) for p in links))
    # the flag tools (charkit/flagui.js, served by `preview serve`; opened as a file the page says the flags need it)
    P.append('<script src="../flags.js"></script>')
    try:
        shutil.copyfile(os.path.join(ROOT, 'charkit', 'flagui.js'), os.path.join(OUT, 'flags.js'))
    except OSError:
        pass
    path = os.path.join(d, 'review.html')
    open(path, 'w').write('\n'.join(P) + '\n')
    latest = max(index(), key=lambda r: r['t'])
    open(os.path.join(OUT, 'latest.html'), 'w').write(
        '<!doctype html><meta http-equiv="refresh" content="0; url=%s/review.html">' % latest['short'])
    _prune_bundles()
    return path


# ------------------------------------------------------------------------------------------------------------ parity
PARITY = dict(mean=1.5, iou=0.998, width=0.1)     # per board: EEVEE against ours past these is flagged (levels, IoU,
                                                  # the ink's mean width in px); phase 1 read 0.64-0.86, 0.9991+, 0.02


def parity(d, log=print):
    """the build's EEVEE boards against charkit.render's from its export (python -m charkit.render compare, drawn on
    this machine) -> compare.json's content, or {'why'} (no export, no boards, no adapter). Made once per preview."""
    out = os.path.join(d, 'toonrender')
    p = os.path.join(out, 'compare.json')
    if not os.path.exists(p):
        r = subprocess.run([PY, '-m', 'charkit.render', 'compare', d, '--out', out], cwd=ROOT, capture_output=True,
                           text=True)
        if r.returncode or not os.path.exists(p):
            log('preview parity: %s' % (r.stdout + r.stderr)[-600:])
            return {'why': ((r.stdout + r.stderr).strip().splitlines() or ['compare failed'])[-1][:300]}
    return json.load(open(p))


def parity_rows(C):
    """compare.json -> per board: mean, over 8, silhouette IoU, the ink's mean width EEVEE / ours, tones, flagged."""
    rows = []
    for name, b in (C.get('boards') or {}).items():
        m = b['metrics']
        ln = m.get('lines') or {}
        we, wo = (ln.get('eevee') or {}).get('mean_width'), (ln.get('ours') or {}).get('mean_width')
        flag = [k for k, bad in (('mean', m['diff']['mean'] > PARITY['mean']),
                                 ('iou', m['silhouette']['iou'] < PARITY['iou']),
                                 ('width', we is not None and wo is not None and abs(we - wo) > PARITY['width'])) if bad]
        rows.append(dict(board=name, mean=m['diff']['mean'], over8=m['diff']['over8'], iou=m['silhouette']['iou'],
                         width=[we, wo], tones=(m.get('tones') or {}).get('agree'), seconds=b.get('seconds'), flag=flag))
    return rows


def parity_section(d, C):
    if 'why' in C:
        return ('<h2>Toon renderer parity</h2><div class="box k">not measured: %s</div>' % html.escape(C['why']))
    rows = parity_rows(C)
    bad = [r for r in rows if r['flag']]
    T = ['<table><tr><th>board</th><th>mean (levels)</th><th>&gt;8 levels</th><th>silhouette IoU</th>'
         '<th>ink width EEVEE / ours (px)</th><th>tones agree</th><th>ours (s)</th></tr>']
    for r in rows:
        f = lambda k, s: '<b style="color:#b00">%s</b>' % s if k in r['flag'] else s
        T.append('<tr><td>%s</td><td>%s</td><td>%.3f%%</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
            r['board'], f('mean', '%.3f' % r['mean']), 100 * r['over8'], f('iou', '%.5f' % r['iou']),
            f('width', '%s / %s' % tuple('%.3f' % w if w is not None else '?' for w in r['width'])),
            '%.5f' % r['tones'] if r['tones'] is not None else '?', r['seconds']))
    T.append('</table>')
    a = C.get('adapter') or {}
    return ('<h2>Toon renderer parity: this build\'s EEVEE boards against charkit.render (%s)</h2><div class="box">'
            '<p class="k">Drawn from the build\'s export on %s (%s). Flagged past mean %.1f levels, IoU %.3f, ink width '
            '%.2f px apart. <a href="toonrender/index.html">side by side and heatmaps</a></p>%s</div>' % (
                'all %d boards within bounds' % len(rows) if not bad else '<b>%d of %d boards flagged</b>' % (
                    len(bad), len(rows)),
                html.escape(str(a.get('device'))), html.escape(str(a.get('backend'))), PARITY['mean'], PARITY['iou'],
                PARITY['width'], ''.join(T)))


# ------------------------------------------------------------------------------------------------------------ the hook
HOOK = """#!/bin/sh
# charkit: the combined preview after a merge on %(branch)s (python -m charkit preview hook install; charkit/preview.py).
# It runs in the background and always exits 0: it never blocks or fails the merge.
[ "$(git rev-parse --abbrev-ref HEAD 2>/dev/null)" = "%(branch)s" ] || exit 0
cd "$(git rev-parse --show-toplevel)" || exit 0
# git's hook variables would point every git command the preview runs (in its own worktree too) at this one
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX GIT_COMMON_DIR GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES \
  GIT_QUARANTINE_PATH GIT_NAMESPACE
mkdir -p charkit/out/previews
nohup %(py)s -m charkit preview --tip %(branch)s >> charkit/out/previews/hook.log 2>&1 < /dev/null &
exit 0
"""


def _hooks_dir(cwd=ROOT):
    return os.path.join(os.path.abspath(os.path.join(cwd, _git('rev-parse', '--git-dir', cwd=cwd))), 'charkit-hooks')


def hook(action, branch=None, cwd=ROOT, py=PY):
    """the post-merge hook in this worktree only (a per-worktree core.hooksPath in the worktree's own git dir: the
    repository's other worktrees and its shared hooks are untouched). -> the hook's path, or None."""
    d = _hooks_dir(cwd)
    p = os.path.join(d, 'post-merge')
    if action == 'install':
        branch = branch or _git('rev-parse', '--abbrev-ref', 'HEAD', cwd=cwd)
        os.makedirs(d, exist_ok=True)
        open(p, 'w').write(HOOK % dict(branch=branch, py=py))
        os.chmod(p, 0o755)
        _git('config', '--worktree', 'core.hooksPath', d, cwd=cwd)
        print('installed: %s (after a merge on %s)' % (p, branch))
        return p
    if action == 'remove':
        _git('config', '--worktree', '--unset', 'core.hooksPath', cwd=cwd, check=False)
        if os.path.exists(p):
            os.remove(p)
        print('removed')
        return None
    import re
    hp = _git('config', '--worktree', '--get', 'core.hooksPath', cwd=cwd, check=False)
    m = re.search(r'= "([^"]+)" \]', open(p).read()) if os.path.exists(p) else None
    print('hook: %s' % ('%s (after a merge on %s)' % (p, m.group(1) if m else '?') if hp == d and m else 'not installed'))
    return p if hp == d and m else None


# ------------------------------------------------------------------------------------------------------------ main
def preview(ref='HEAD', spec=SPEC, box='render', force=False, tip=None, log=print):
    """build ref (or, with tip, that branch's tip once the lock is ours) and write its page -> the page's path."""
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, '.lock'), 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        sha = _git('rev-parse', (tip or ref) + '^{commit}')
        d = os.path.join(OUT, _short(sha))
        if os.path.exists(os.path.join(d, 'review.html')) and not force:
            log('preview %s: already made: %s' % (_short(sha), os.path.join(d, 'review.html')))
            return os.path.join(d, 'review.html')
        build(sha, spec, box, log)
        p = page(sha, spec, log)
    log('preview %s: %s' % (_short(sha), p))
    return p


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return 0
    # run from a hook (an older hook script, or a user's), git's variables must not reach the build's git commands (the
    # box sync lists files with git too): dropped for this process and every child
    for k in GIT_HOOK_ENV:
        os.environ.pop(k, None)
    if args[0] == 'hook':
        hook(args[1] if len(args) > 1 else 'status', args[2] if len(args) > 2 else None)
        return 0
    if args[0] == 'serve':
        from . import flags
        return flags.main(args[1:])
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    spec = opt('--spec', SPEC)
    if '--page' in args:
        p = page(_git('rev-parse', opt('--page') + '^{commit}'), spec)
    else:
        pos = [a for i, a in enumerate(args) if not a.startswith('--') and (i == 0 or args[i - 1] not in
                                                                             ('--spec', '--box', '--tip', '--page'))]
        p = preview(pos[0] if pos else 'HEAD', spec, opt('--box', 'render'), '--force' in args, opt('--tip'))
    print('page', p)
    if '--open' in args:
        subprocess.run(['open', p])
    return 0
