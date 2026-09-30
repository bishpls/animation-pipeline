"""The design's light (docs/workstreams/look.md, round 6): the key light the design's drawn shading implies, fitted from
the turnarounds' shaded regions against ours drawn by charkit.render under candidate lights.

The board light is a style setting (Michael's call A: the camera key, `look.light`); this is a reference light for QA,
read from the character's manifest (`design_light`). No geometry fit reads it: shading is the look layer's.

The design's side: head_turnaround (at lookqa.FACE_PPL, aligned on the eyes as lookqa.face_shadow aligns it) and
body_turnaround (charkit.bodyqa's grid: the sheet's px per L, the eyes at the origin), each view's pixels classed by
colour family (bodyqa.family: skin, orange (hair above the shoulders, dress below), cream, dark, white), each family
split into its lit and shade tones at the luminance that best separates them over the whole sheet (Otsu, as
lookqa.skin_classes splits the skin). The drawn lines are left out.

Ours: the build's export drawn by charkit.render on the same grid from the same azimuth (the head bare, as the head
sheet draws it), its tone buffer (0 lit, 1 shade, 2 deep) cut at 0.5, its parts' objects grouped (skin, hair, garment);
the outline hulls left out. Per region (hair, skin, garment; the head sheet's skin split into the face and the neck)
over the pixels both show: the two shade masks' mean IoU (of shade and of lit: a light that shades nothing scores 0.5 at
best, not the lit share), the agreement, and the shade shares.

The fit: a camera-relative key (a0 degrees to the camera's left, el up: charkit.shade.view_light's `camera` mode), per
view and jointly (one key for every view: the turnarounds are lit from the viewer's side); a world light (one direction
for every view) beside it. A coarse grid, then a finer one round the best.

    python -m charkit.designlight BUILD [--out DIR]       # fit.json and the pictures into DIR (default BUILD/design_light)
"""
import json, math, os

import numpy as np

REGIONS = ('hair', 'skin', 'garment')
FAMILIES = {'skin': (1,), 'hair': (2,), 'garment': (6, 7, 8, 9)}      # charkit.bodyqa.CLASS ids per region
HEAD_VIEWS = ('front', 'three_quarter', 'profile')
BODY_VIEWS = ('front', 'three_quarter', 'profile', 'back')
GRID = dict(a0=np.arange(-90, 91, 10.0), el=np.arange(-30, 81, 10.0))
FINE = dict(step=2.5, reach=10.0)
MIN_PX = 200                                   # a region scored from fewer pixels both show is left out of the fit


# ------------------------------------------------------------------------------------------------------ the design
def otsu(x, bins=64, min_gap=0.06):
    """the luminance that best splits x in two (Otsu), or None when the two means are under min_gap apart."""
    x = np.asarray(x, float)
    if x.size < 100:
        return None
    hist, e = np.histogram(x, bins=bins)
    c = (e[:-1] + e[1:]) / 2
    w0 = np.cumsum(hist); w1 = w0[-1] - w0
    s0 = np.cumsum(hist * c)
    m0 = s0 / np.maximum(w0, 1); m1 = (s0[-1] - s0) / np.maximum(w1, 1)
    k = int(np.argmax(w0 * w1 * (m0 - m1) ** 2))
    return float(e[k + 1]) if m1[k] - m0[k] > min_gap else None


def lum(rgb):
    return np.asarray(rgb, float)[..., :3] @ np.array([0.3, 0.59, 0.11])


def shade_split(cls_list, rgb_list):
    """per colour family the luminance between its lit and shade tones, over every view of a sheet (the drawing uses one
    palette) -> {family id: threshold or None}."""
    out = {}
    for fam in sorted({f for fs in FAMILIES.values() for f in fs}):
        x = np.concatenate([lum(r)[c == fam] for c, r in zip(cls_list, rgb_list)])
        out[fam] = otsu(x)
    return out


def design_masks(cls, rgb, thr, line=None):
    """a view's design classes -> {region: (mask, shade)} (the lines left out)."""
    L = lum(rgb)
    out = {}
    for reg, fams in FAMILIES.items():
        m = np.isin(cls, fams)
        if line is not None:
            m &= ~line
        sh = np.zeros_like(m)
        for f in fams:
            t = thr.get(f)
            if t is not None:
                sh |= (cls == f) & (L < t)
        out[reg] = (m, sh & m)
    return out


def head_design(design):
    """head_turnaround at lookqa.FACE_PPL: its classes (bodyqa.family, the orange all hair: the head sheet has no dress),
    the shade thresholds -> dict(D (lookqa.design_heads), cls, line, thr) or None."""
    from . import bodyqa, lookqa
    D = lookqa.design_heads(design)
    if D is None:
        return None
    rgb = D['rgb']
    cls = bodyqa.family(rgb)
    cls[cls == bodyqa.CLASS['orange']] = bodyqa.CLASS['hair']
    line = rgb.max(-1) < lookqa.LINE_W_V
    box = np.zeros(cls.shape, bool)
    for h in D['heads'].values():
        x0, y0, x1, y1 = h['box']
        box[y0:y1, x0:x1] = True
    cls = np.where(box, cls, 0)
    thr = shade_split([cls], [rgb])
    return dict(D=D, cls=cls, line=line, thr=thr)


def body_design(design):
    """body_turnaround on charkit.bodyqa's grid per view: dict(ctx, views {view: dv}, thr) or None."""
    ctx = design.sheet_context()
    if 'why' in ctx:
        return None
    dv = design.design_views()
    thr = shade_split([v['raw'] for v in dv.values()], [v['rgb'] for v in dv.values()])
    return dict(ctx=ctx, views=dv, thr=thr)


# ------------------------------------------------------------------------------------------------------ ours
def groups(B, Q):
    """the export's parts -> region index (REGIONS; -1 none): its objects' bundle groups."""
    g = {o.name: o.group for o in B.objects()}
    reg = np.full(len(Q.objects) + 1, -1, np.int64)
    for k, name in enumerate(Q.objects):
        gr = g.get(name)
        if gr in REGIONS:
            reg[k] = REGIONS.index(gr)
    return reg


def ours_masks(F, reg):
    """a frame's regions and shade (tone >= 0.5), the hulls left out -> {region: (mask, shade)}."""
    p = F['part']
    r = np.where((p >= 0) & ~F['hull'], reg[np.maximum(p, 0)], -1)
    t = F['tone']
    sh = np.isfinite(t) & (t >= 0.5)
    return {name: (r == i, sh & (r == i)) for i, name in enumerate(REGIONS)}


def head_setup(B, Q, H):
    """per head view: our window (lookqa.HeadFrame at FACE_PPL, one sample a pixel) and the design cut to it on the eyes
    (lookqa.face_shadow's alignment) -> {view: dict(az, cam, design {region: (mask, shade)}, rows (the chin's row),
    rgb)}."""
    from . import lookqa
    from .render import buffers
    D = H['D']
    fr = lookqa.HeadFrame(B, ss=1)
    W = int(round(2 * fr.win['x'] / fr.pix)); Ht = int(round((fr.win['top'] - fr.win['bottom']) / fr.pix))
    chin_row = fr.row(fr.eye_z - float(B.assembly['chin']))
    out = {}
    for view in HEAD_VIEWS:
        h = D['heads'].get(view)
        if not h or not h['eyes']:
            continue
        az = {'front': 0.0, 'three_quarter': D['az3'], 'profile': 90.0}[view]
        oe = lookqa._ours_eyes(B, fr, az)
        de = np.array(h['eyes'], float)
        if view == 'profile' or len(de) < 2:
            o_c = oe[np.argmin(oe[:, 0])] if view == 'profile' else oe.mean(0)
            d_c = de[np.argmin(de[:, 0])]
        else:
            o_c, d_c = oe.mean(0), de.mean(0)
        dy, dx = int(round(d_c[1] - o_c[1])), int(round(d_c[0] - o_c[0]))
        bx = h['box']

        def cut(a, fill=0):
            o = np.full((Ht, W) + a.shape[2:], fill, a.dtype)
            y0, x0 = max(0, dy, bx[1]), max(0, dx, bx[0])
            y1, x1 = min(a.shape[0], dy + Ht, bx[3]), min(a.shape[1], dx + W, bx[2])
            if y1 > y0 and x1 > x0:
                o[y0 - dy:y1 - dy, x0 - dx:x1 - dx] = a[y0:y1, x0:x1]
            return o
        cls, line, rgb = cut(H['cls']), cut(H['line'], True), cut(D['rgb'], 0.93)
        cam = buffers.window(az, fr.origin, fr.pix, fr.win)
        dm = design_masks(cls, rgb, H['thr'], line)
        dm['garment'] = tuple(np.zeros_like(m) for m in dm['garment'])     # (the head sheet draws no garments: its
        out[view] = dict(az=az, cam=cam, design=dm, chin_row=chin_row, rgb=rgb, shift=(dy, dx))   # whites are eyes)
    return out


def body_setup(B, Q, Bd):
    """per body view: our window on bodyqa's grid and the design's masks -> {view: dict(az, cam, design, rgb)}."""
    from . import bodyqa, qa3d
    from .render import buffers
    ctx, dv = Bd['ctx'], Bd['views']
    As = B.assembly
    L = float(As['L'])
    iris = np.array(qa3d.iris_centres(B))
    azs = bodyqa.azimuths(ctx['az3'])
    out = {}
    for view in BODY_VIEWS:
        if view not in dv:
            continue
        v = dv[view]
        az = azs[view]
        o = bodyqa.origin(view, az, iris, As['centre'])
        win = {k: float(x) * L for k, x in v['win'].items()}
        cam = buffers.window(az, o, L / v['ppl'], win)
        line = v['raw'] == bodyqa.CLASS['line']
        out[view] = dict(az=az, cam=cam, design=design_masks(v['raw'], v['rgb'], Bd['thr'], line), rgb=v['rgb'])
    return out


# ------------------------------------------------------------------------------------------------------ scoring
def score(O, Dm, split=None):
    """ours against the design over the pixels both show, per region -> {region: dict(miou, agree, ours, design, px)};
    split {name: (region, row mask)}: extra regions cut from one by rows (the face and the neck)."""
    out = {}
    items = [(r, r, None) for r in REGIONS] + [(n, r, m) for n, (r, m) in (split or {}).items()]
    for name, r, rows in items:
        mo, so = O[r]
        md, sd = Dm[r]
        H_, W_ = min(mo.shape[0], md.shape[0]), min(mo.shape[1], md.shape[1])
        both = mo[:H_, :W_] & md[:H_, :W_]
        if rows is not None:
            both = both & rows[:H_, :W_]
        n = int(both.sum())
        if n < 1:
            out[name] = dict(px=0)
            continue
        a, b = so[:H_, :W_][both], sd[:H_, :W_][both]
        iou_s = (a & b).sum() / max(1, (a | b).sum())
        iou_l = (~a & ~b).sum() / max(1, (~a | ~b).sum())
        out[name] = dict(miou=round(float((iou_s + iou_l) / 2), 4), agree=round(float((a == b).mean()), 4),
                         ours=round(float(a.mean()), 4), design=round(float(b.mean()), 4), px=n)
    return out


def objective(S, regions=REGIONS):
    """a view's score: the mean over its regions' mean IoU (regions under MIN_PX left out)."""
    v = [S[r]['miou'] for r in regions if S.get(r, {}).get('px', 0) >= MIN_PX]
    return float(np.mean(v)) if v else float('nan')


def camera_key(az, a0, el):
    """toward a key a0 degrees to the left of a camera at azimuth az, el up (world; charkit.shade.view_light's camera
    mode)."""
    from . import lookqa
    return lookqa.key_light(az, a0, el)


def world_dir(phi, el):
    """toward a world light at azimuth phi (0 in front of her, -y; 90 from her left, +x, charkit.faceshade.cast_dirs'),
    el up."""
    p, e = math.radians(phi), math.radians(el)
    return np.array([math.sin(p) * math.cos(e), -math.cos(p) * math.cos(e), math.sin(e)])


def to_camera(az, d):
    """a world direction toward the light -> (a0, el) relative to a camera at azimuth az (camera_key's inverse)."""
    a = math.radians(az)
    R = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1.0]])
    c = R.T @ np.asarray(d, float)
    el = math.degrees(math.asin(np.clip(c[2], -1, 1)))
    a0 = math.degrees(math.atan2(-c[0], -c[1]))
    return a0, el


class Fitter:
    """every view's frame drawn under a light, memoized per (sheet, view, light)."""

    def __init__(self, B, Q, setups):
        self.B, self.Q, self.setups = B, Q, setups      # {sheet: {view: setup}}
        self.reg = groups(B, Q)
        self.skin = next((o.name for o in B.objects() if o.group == 'skin'), None)
        self.draw_head = [o.name for o in B.objects() if o.group != 'garment' and o.has('eval')]
        self._m = {}
        self.frames = 0

    def frame(self, sheet, view, d):
        s = self.setups[sheet][view]
        kw = dict(picture=False, light=np.asarray(d, float), line=0.0)
        if sheet == 'head':
            kw.update(draw=self.draw_head, variants={self.skin: 'bare'})
        self.frames += 1
        return self.Q.frame(s['cam'], **kw)

    def view_score(self, sheet, view, d):
        key = (sheet, view, tuple(np.round(d, 6)))
        if key not in self._m:
            s = self.setups[sheet][view]
            O = ours_masks(self.frame(sheet, view, d), self.reg)
            split = None
            if sheet == 'head':
                rows = np.arange(O['skin'][0].shape[0])[:, None]
                cr = s['chin_row']
                split = {'face': ('skin', np.broadcast_to(rows < cr, O['skin'][0].shape)),
                         'neck': ('skin', np.broadcast_to((rows >= cr) & (rows < cr + 0.5 * 200), O['skin'][0].shape))}
            self._m[key] = score(O, s['design'], split)
        return self._m[key]

    def views(self):
        return [(sh, v) for sh, vs in self.setups.items() for v in vs]

    def total(self, dirs_of, regions=REGIONS, views=None):
        """the mean objective over views, each lit by dirs_of(sheet, view, az)."""
        vs = views or self.views()
        o = [objective(self.view_score(sh, v, dirs_of(sh, v, self.setups[sh][v]['az'])), regions) for sh, v in vs]
        o = [x for x in o if np.isfinite(x)]
        return float(np.mean(o)) if o else float('nan')


def _grid_search(f, a_range, e_range, fine=FINE):
    """maximise f(a, e) on a grid, then a finer one round the best -> (best (a, e), value, the coarse table)."""
    tab = {(float(a), float(e)): f(a, e) for a in a_range for e in e_range}
    (a, e), v = max(tab.items(), key=lambda t: t[1])
    st, r = fine['step'], fine['reach']
    for a2 in np.arange(a - r, a + r + 1e-9, st):
        for e2 in np.arange(max(-89, e - r), min(89, e + r) + 1e-9, st):
            x = f(a2, e2)
            if x > v:
                (a, e), v = (float(a2), float(e2)), x
    return (a, e), v, tab


def fit(B, Q, design, regions=REGIONS, grid=GRID, sheets=('head', 'body')):
    """-> dict: per view the best camera key and its score (per region), the joint camera key over every view and each
    view's score under it, the joint world light, and the board light's scores."""
    setups = {}
    if 'head' in sheets:
        H = head_design(design)
        if H:
            setups['head'] = head_setup(B, Q, H)
    if 'body' in sheets:
        Bd = body_design(design)
        if Bd:
            setups['body'] = body_setup(B, Q, Bd)
    Fi = Fitter(B, Q, setups)
    res = dict(views={}, regions=list(regions))
    for sh, v in Fi.views():
        f = lambda a, e, sh=sh, v=v: objective(Fi.view_score(sh, v, camera_key(Fi.setups[sh][v]['az'], a, e)), regions)
        (a, e), val, tab = _grid_search(f, grid['a0'], grid['el'])
        res['views']['%s/%s' % (sh, v)] = dict(az=Fi.setups[sh][v]['az'], key=[a, e], value=round(val, 4),
                                               regions=Fi.view_score(sh, v, camera_key(Fi.setups[sh][v]['az'], a, e)),
                                               surface=[[k[0], k[1], round(x, 4)] for k, x in tab.items()])
    fj = lambda a, e: Fi.total(lambda sh, v, az: camera_key(az, a, e), regions)
    (a, e), val, _ = _grid_search(fj, grid['a0'], grid['el'])
    res['camera'] = dict(key=[a, e], value=round(val, 4), per_view={
        '%s/%s' % (sh, v): dict(value=round(objective(Fi.view_score(sh, v, camera_key(Fi.setups[sh][v]['az'], a, e)),
                                                       regions), 4),
                                regions=Fi.view_score(sh, v, camera_key(Fi.setups[sh][v]['az'], a, e)))
        for sh, v in Fi.views()})
    fw = lambda p, e: Fi.total(lambda sh, v, az: world_dir(p, e), regions)
    (p, e), val, _ = _grid_search(fw, np.arange(-180, 180, 15.0), grid['el'])
    res['world'] = dict(dir=[p, e], value=round(val, 4), per_view={
        '%s/%s' % (sh, v): round(objective(Fi.view_score(sh, v, world_dir(p, e)), regions), 4) for sh, v in Fi.views()})
    look = B.meta('look') or {}
    bk = ((look.get('light') or {}).get('key')) or [30.0, 40.0]
    res['board'] = dict(key=list(bk), value=round(fj(*bk), 4), per_view={
        '%s/%s' % (sh, v): dict(value=round(objective(Fi.view_score(sh, v, camera_key(Fi.setups[sh][v]['az'], *bk)),
                                                       regions), 4),
                                regions=Fi.view_score(sh, v, camera_key(Fi.setups[sh][v]['az'], *bk)))
        for sh, v in Fi.views()})
    res['frames'] = Fi.frames
    return res, Fi


def main(args):
    import time
    from . import bundle, qa3d, qarender
    os.environ.setdefault(qarender.ENV, 'render')
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    B = bundle.load(os.path.join(args[0], 'bundle'))
    out = opt('--out', os.path.join(args[0], 'design_light'))
    os.makedirs(out, exist_ok=True)
    Q = qarender.frames(B)
    if Q is None:
        raise SystemExit('no export to draw (charkit.render)')
    t0 = time.time()
    res, Fi = fit(B, Q, qa3d.Design(B))
    res['seconds'] = round(time.time() - t0, 1)
    json.dump(res, open(os.path.join(out, 'fit.json'), 'w'), indent=1, default=float)
    brief = {k: res[k] for k in ('camera', 'world', 'board')}
    print(json.dumps({'camera': res['camera']['key'], 'camera_value': res['camera']['value'],
                      'world': res['world']['dir'], 'world_value': res['world']['value'],
                      'board_value': res['board']['value'],
                      'views': {k: (v['key'], v['value']) for k, v in res['views'].items()}, 'frames': res['frames'],
                      'seconds': res['seconds']}, indent=1))
    return brief


if __name__ == '__main__':
    import sys
    from charkit import designlight as _dl
    _dl.main(sys.argv[1:])


# ------------------------------------------------------------------------------------------------------ the cast, rebaked
def _polys(G):
    """a bundle variant's polygons (loopv, counts) -> list of vertex index lists."""
    lv, cnt = np.asarray(G['loopv']), np.asarray(G['counts'])
    st = np.concatenate([[0], np.cumsum(cnt)[:-1]])
    return [lv[s:s + n].tolist() for s, n in zip(st, cnt)]


def rebake(B, el, cast=None, hair=None):
    """charkit.faceshade.cast_maps in the venv on the bundle's own inputs (the skin's base mesh, rest pose; the hair
    objects' own meshes, world): the cast shadows baked at elevation el with the look's face.cast laid under `cast`
    (overrides: px, soft, smooth, face, lift, bias, ...). hair: the occluders' object names (default every hair object).
    -> (n_base, k) float32, the bundle's base 'fcast' layout."""
    from . import faceshade, mh
    sk = B.skin()
    G = {k: sk.a('base', k) for k in ('V', 'loopv', 'counts', 'pmat')}
    V = np.asarray(G['V'], float)
    F = _polys(G)
    As = B.assembly
    L = float(As['L'])
    J = B.meta('landmarks')['joints']
    neck = [np.asarray(J[k], float) for k in mh.VRM_JOINTS['neck']]
    nk, _ = faceshade.neck_weight(V, As['centre'], L, As['chin'], neck)
    look = B.meta('look') or {}
    P = faceshade.cast_params(dict((look.get('face') or {}).get('cast') or {}, **(cast or {})), el)
    extra = {k: v for k, v in (cast or {}).items() if k in ('lift', 'bias', 'spacing', 'grow')}
    occ = []
    for o in B.objects():
        if o.group == 'hair' and o.has('raw') and (hair is None or o.name in hair):
            Gh = {k: o.a('raw', k) for k in ('V', 'loopv', 'counts')}
            occ.append((np.asarray(Gh['V'], float), faceshade._triangles(_polys(Gh))))
    z_chin = float(As['centre'][2]) - float(As['chin'])
    return faceshade.cast_maps(V, F, np.asarray(G['pmat']), None, nk, occ, L, faceshade.cast_dirs(P['k'], P['el']),
                               z_chin, px=P['px'], soft=P['soft'], smooth=P['smooth'], face=P['face'], **extra)


def carry(B, M, base_cast, objects=None):
    """per-vertex values on the skin's base mesh (rebake's) onto the export's skin primitives (charkit.render.model's
    M; its render-level mesh, each vertex inside one of the base's polygons): each vertex takes the barycentric blend of
    the nearest base triangle's corners -> {primitive index: (n, k) float32}."""
    from scipy.spatial import cKDTree
    from . import faceshade
    from .render import model as model_
    sk = B.skin()
    G = {k: sk.a('base', k) for k in ('V', 'loopv', 'counts')}
    V = np.asarray(G['V'], float)
    T = faceshade._triangles(_polys(G))
    A, Bv, Cv = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    tree = cKDTree((A + Bv + Cv) / 3)
    out = {}
    for k, P in enumerate(M.prims):
        if P.object != sk.name or P.cast is None:
            continue
        X = np.asarray(P.position, float) @ model_.C3
        _, cand = tree.query(X, k=8)
        best_d, best_w, best_t = np.full(len(X), np.inf), np.zeros((len(X), 3)), np.zeros(len(X), np.int64)
        for j in range(cand.shape[1]):
            t = cand[:, j]
            w, d = _bary(X, A[t], Bv[t], Cv[t])
            better = d < best_d
            best_d[better], best_w[better], best_t[better] = d[better], w[better], t[better]
        tri = T[best_t]
        out[k] = np.einsum('nj,njk->nk', best_w, np.asarray(base_cast, float)[tri]).astype(np.float32)
    return out


def _bary(X, A, B_, C):
    """the closest point's barycentric weights (clamped into the triangle) and distance, per row."""
    e0, e1, v = B_ - A, C - A, X - A
    d00, d01, d11 = (e0 * e0).sum(1), (e0 * e1).sum(1), (e1 * e1).sum(1)
    d20, d21 = (v * e0).sum(1), (v * e1).sum(1)
    den = np.maximum(d00 * d11 - d01 * d01, 1e-30)
    b = (d11 * d20 - d01 * d21) / den
    c = (d00 * d21 - d01 * d20) / den
    w = np.clip(np.stack([1 - b - c, b, c], 1), 0, None)
    w /= np.maximum(w.sum(1, keepdims=True), 1e-12)
    p = w[:, :1] * A + w[:, 1:2] * B_ + w[:, 2:] * C
    return w, np.linalg.norm(X - p, axis=1)
