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
        self.rebake = True                              # the cast baked at each light's elevation (False: the build's)

    def frame(self, sheet, view, d):
        """a view's frame under the light d, the cast shadows rebaked at its elevation (lookqa.light_frames)."""
        from . import lookqa
        s = self.setups[sheet][view]
        kw = dict(picture=False, light=np.asarray(d, float), line=0.0)
        if sheet == 'head':
            kw.update(draw=self.draw_head, variants={self.skin: 'bare'})
        self.frames += 1
        el = round(math.degrees(math.asin(float(np.clip(d[2] / np.linalg.norm(d), -1, 1)))), 1)
        Q = (lookqa.light_frames(self.B, el) if self.rebake else None) or self.Q
        return Q.frame(s['cam'], **kw)

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
    """maximise f(a, e) on a grid, then a finer one round the best -> (best (a, e), value, the coarse table). The
    elevation is the outer loop (the cast is rebaked per elevation)."""
    tab = {(float(a), float(e)): f(a, e) for e in e_range for a in a_range}
    (a, e), v = max(tab.items(), key=lambda t: t[1])
    st, r = fine['step'], fine['reach']
    a0, e0 = a, e
    for e2 in np.arange(max(-89, e0 - r), min(89, e0 + r) + 1e-9, st):
        for a2 in np.arange(a0 - r, a0 + r + 1e-9, st):
            x = f(a2, e2)
            if x > v:
                (a, e), v = (float(a2), float(e2)), x
    return (a, e), v, tab


def _fine(best, fine=FINE):
    a, e = best
    st, r = fine['step'], fine['reach']
    return [(float(a2), float(e2)) for e2 in np.arange(max(-89, e - r), min(89, e + r) + 1e-9, st)
            for a2 in np.arange(a - r, a + r + 1e-9, st)]


def fit(B, Q, design, regions=REGIONS, grid=GRID, sheets=('head', 'body'), rebake=True):
    """-> (dict: per view the best camera key and its score (per region), the joint camera key over every view and each
    view's score under it, the joint world light, and the board light's scores; the Fitter). Every light is drawn with
    the cast rebaked at its elevation (rebake=False: the build's bake, whatever the light). The lights are visited
    elevation by elevation (a rebake each): the coarse grid, then 2.5 deg round each view's best and the joint's."""
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
    Fi.rebake = rebake
    views = Fi.views()
    az = {(sh, v): Fi.setups[sh][v]['az'] for sh, v in views}
    cam = lambda sh, v, a, e: objective(Fi.view_score(sh, v, camera_key(az[(sh, v)], a, e)), regions)
    joint = lambda a, e: float(np.nanmean([cam(sh, v, a, e) for sh, v in views]))

    def visit(points, fn):
        """points [(a, e)] visited elevation by elevation."""
        for a, e in sorted(set(points), key=lambda p: (p[1], p[0])):
            fn(a, e)
    coarse = [(float(a), float(e)) for e in grid['el'] for a in grid['a0']]
    visit(coarse, lambda a, e: [cam(sh, v, a, e) for sh, v in views])
    best = {k: max(coarse, key=lambda p, k=k: cam(*k, *p)) for k in views}
    jbest = max(coarse, key=lambda p: joint(*p))
    fine = [p for k in views for p in _fine(best[k])]
    visit(fine + _fine(jbest), lambda a, e: [cam(sh, v, a, e) for sh, v in views])
    res = dict(views={}, regions=list(regions))
    for k in views:
        pts = coarse + _fine(best[k])
        a, e = max(pts, key=lambda p: cam(*k, *p))
        sh, v = k
        res['views']['%s/%s' % k] = dict(az=az[k], key=[a, e], value=round(cam(sh, v, a, e), 4),
                                         regions=Fi.view_score(sh, v, camera_key(az[k], a, e)),
                                         surface=[[p[0], p[1], round(cam(sh, v, *p), 4)] for p in coarse])
    a, e = max(coarse + _fine(jbest), key=lambda p: joint(*p))

    def under(dirs_of):
        return {'%s/%s' % (sh, v): dict(value=round(objective(Fi.view_score(sh, v, dirs_of(sh, v)), regions), 4),
                                        regions=Fi.view_score(sh, v, dirs_of(sh, v))) for sh, v in views}
    res['camera'] = dict(key=[a, e], value=round(joint(a, e), 4),
                         per_view=under(lambda sh, v: camera_key(az[(sh, v)], a, e)),
                         surface=[[p[0], p[1], round(joint(*p), 4)] for p in coarse])
    wgrid = [(float(p), float(e)) for e in grid['el'] for p in np.arange(-180, 180, 15.0)]
    wv = lambda p, e: float(np.nanmean([objective(Fi.view_score(sh, v, world_dir(p, e)), regions) for sh, v in views]))
    visit(wgrid, wv)
    wb = max(wgrid, key=lambda q: wv(*q))
    visit(_fine(wb), wv)
    p, e = max(wgrid + _fine(wb), key=lambda q: wv(*q))
    res['world'] = dict(dir=[p, e], value=round(wv(p, e), 4), per_view={
        k: x['value'] for k, x in under(lambda sh, v: world_dir(p, e)).items()})
    look = B.meta('look') or {}
    bk = ((look.get('light') or {}).get('key')) or [30.0, 40.0]
    res['board'] = dict(key=list(bk), value=round(joint(*bk), 4),
                        per_view=under(lambda sh, v: camera_key(az[(sh, v)], *bk)))
    res['frames'] = Fi.frames
    res['rebake'] = rebake
    return res, Fi


MOVES = ((0, 1), (0, 2), (1, 0), (2, 0), (0, -1), (0, -2), (-1, 0), (-2, 0))


def chin_calibration(B, design, key=None, moves=MOVES):
    """the chin measures on the jaw (lookqa.chin_on_jaw) calibrated: the design's own shadow moved 1-2 px against its
    jaw (each move against the design as drawn: a PASS must hold), and this bundle's (a known-bad build: it must FAIL)
    under the camera key `key` (None: the boards' light) -> {view: dict(moved {move: (iou, edge)}, ours (iou, edge))}."""
    from . import lookqa
    H = head_design(design)
    D = H['D']
    fr = lookqa.HeadFrame(B)
    ss = fr.ss
    rows_ours = fr.row(fr.eye_z - float(B.assembly['chin']))
    su = head_setup(B, None, H)
    out = {}
    for view in lookqa.CHIN_VIEWS:
        s = su.get(view)
        if s is None:
            continue
        az = s['az']
        dy, dx = s['shift']
        Ht, W = s['design']['skin'][0].shape
        lab = np.zeros((Ht, W), int)
        y0, x0 = max(0, dy), max(0, dx)
        y1, x1 = min(D['lab'].shape[0], dy + Ht), min(D['lab'].shape[1], dx + W)
        bx = D['heads'][view]['box']
        sub = D['lab'][y0:y1, x0:x1].copy()
        yy, xx = np.mgrid[y0:y1, x0:x1]
        sub[(xx < bx[0]) | (xx >= bx[2]) | (yy < bx[1]) | (yy >= bx[3])] = 0
        lab[y0 - dy:y1 - dy, x0 - dx:x1 - dx] = sub
        d_skin, d_sh = (lab == 1) | (lab == 5), lab == 5
        rr, cc = np.mgrid[dy:dy + Ht, dx:dx + W]
        d_line = (s['rgb'].max(-1) < lookqa.LINE_W_V) & (cc >= bx[0]) & (cc < bx[2]) & (rr >= bx[1]) & (rr < bx[3])
        cx = float((lookqa._ours_eyes(B, fr, az).mean(0))[0])
        Jd = lookqa.jaw_drawn(d_skin, d_line, rows_ours, cx, fr.ppl)
        gd = lookqa.jaw_frame(d_sh, d_skin, Jd, fr.ppl)
        moved = {}
        for my, mx in moves:
            g = lookqa.jaw_frame(np.roll(np.roll(d_sh, my, 0), mx, 1) & d_skin, d_skin, Jd, fr.ppl)
            c = lookqa.chin_on_jaw(g, gd, fr.ppl)
            moved['%+d,%+d' % (my, mx)] = (c['iou'], c['edge'])
        q, m, px, soft, depth = lookqa.board_tones(B, fr, az) if key is None else lookqa.light_tones(B, fr, az, key)
        q, m, depth = q[ss // 2::ss, ss // 2::ss], m[ss // 2::ss, ss // 2::ss], depth[ss // 2::ss, ss // 2::ss]
        Jo = lookqa.jaw_depth(m, depth, rows_ours, cx, fr.ppl, fr.L)
        c = lookqa.chin_on_jaw(lookqa.jaw_frame(m & (q >= 1), m, Jo, fr.ppl), gd, fr.ppl)
        out[view] = dict(moved=moved, ours=(c['iou'], c['edge']), design_reach=c['design_reach'],
                         ours_reach=c['ours_reach'])
    return out


CAST_VARIANTS = {                     # the hair's cast on the face: the look's, and the options tried (look.md round 6)
    'look': None,
    'face_off': {'face': False},                            # the face keeps the fringe map alone (look5's castneck)
    'fringe_only': {'hair': ['hair_bangs', 'hair_side_lock_L', 'hair_side_lock_R']},
    'bangs_only': {'hair': ['hair_bangs']},
    'lift3': {'lift': 3.0},
    'lift6': {'lift': 6.0},
    'soft4': {'soft': 4.0},
}


def cast_lab(B, design, key, variants=None, pictures=None):
    """the hair's cast on the face under a camera key with the bake's options varied (lookqa.light_frames' cast):
    per variant and view the face's and neck's shade share (ours, the design's), the face's shadow IoU, the chin on
    the jaw -> {variant: {view: dict}}; pictures: a folder for each variant's qa_face_shadow row."""
    from . import lookqa
    D = lookqa.design_heads(design)
    fr = lookqa.HeadFrame(B)
    out = {}
    for name, c in (variants or CAST_VARIANTS).items():
        t, pics, _ = lookqa._shadow_views(B, D, fr, key, pictures=bool(pictures), cast=c)
        out[name] = {v: dict(face=r['face'], neck=r['neck'], iou=r['iou'],
                             chin={k: r['chin'][k] for k in ('iou', 'edge')} if r.get('chin') else None)
                     for v, r in t.items()}
        if pictures and pics:
            os.makedirs(pictures, exist_ok=True)
            lookqa._save_row(os.path.join(pictures, 'face_shadow_%s.png' % name), pics)
    return out


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
                               z_chin, px=P['px'], soft=P['soft'], smooth=P['smooth'], face=P['face'],
                               face_lift=P['face_lift'],
                               face_dirs=None if P['face_el'] is None else faceshade.cast_dirs(P['k'], P['face_el']),
                               **extra)


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


# ------------------------------------------------------------------------------------------------------ the review
def _tint(rgb, masks, col=(0.2, 0.3, 0.9), a=0.45):
    img = np.clip(np.asarray(rgb, float)[..., :3], 0, 1).copy()
    m = np.zeros(img.shape[:2], bool)
    for s in masks:
        m[:s.shape[0], :s.shape[1]] |= s[:img.shape[0], :img.shape[1]]
    img[m] = img[m] * (1 - a) + np.array(col) * a
    return img


def _diff(O, Dm):
    """ours against the design over the pixels both show, per region: both shaded (dark red), ours only (orange), the
    design's only (blue), both lit (pale); a region one side alone shows (grey)."""
    H, W = O['hair'][0].shape
    img = np.full((H, W, 3), 0.93)
    for r in REGIONS:
        mo, so = O[r]
        md, sd = (a[:H, :W] for a in Dm[r])
        if md.shape != (H, W):
            md = np.pad(md, ((0, H - md.shape[0]), (0, W - md.shape[1])))
            sd = np.pad(sd, ((0, H - sd.shape[0]), (0, W - sd.shape[1])))
        both = mo & md
        img[(mo | md) & ~both] = (0.80, 0.80, 0.82)
        img[both] = (0.99, 0.94, 0.90)
        img[both & so & ~sd] = (0.95, 0.55, 0.20)
        img[both & sd & ~so] = (0.25, 0.45, 0.90)
        img[both & so & sd] = (0.60, 0.12, 0.15)
    return img


def review(builds, out, keys=None):
    """the review page: per build (name -> BUILD dir) and view, the design (its shade tinted), and ours under each light
    (keys: name -> camera key; default the boards' and the manifest's design light) with the shade against the
    design's (diff), and each region's mean IoU and shade share. -> the page's path."""
    import html
    from PIL import Image
    from . import bundle, lookqa, qa3d, qarender
    os.makedirs(out, exist_ok=True)
    save = lambda name, img, k=1: Image.fromarray((np.clip(img, 0, 1)[::k, ::k] * 255).astype(np.uint8)).save(
        os.path.join(out, name)) or name
    rows, first = [], True
    for bname, bdir in builds.items():
        B = bundle.load(os.path.join(bdir, 'bundle'))
        Q = qarender.frames(B)
        design = qa3d.Design(B)
        DL = lookqa.design_light(design)
        ks = dict(keys or {})
        if not ks:
            look = B.meta('look') or {}
            ks['board'] = tuple(((look.get('light') or {}).get('key')) or (30.0, 40.0))
            if DL:
                ks['design light'] = tuple(DL['key'])
        setups = {'head': head_setup(B, Q, head_design(design)), 'body': body_setup(B, Q, body_design(design))}
        Fi = Fitter(B, Q, setups)
        for sh, vs in setups.items():
            k = 1 if sh == 'head' else 2
            for v, s in vs.items():
                tag = '%s_%s_%s' % (bname, sh, v)
                cells = []
                if first or True:
                    dm = s['design']
                    cells.append(('design', save(tag + '_design.png', _tint(s['rgb'], [dm[r][1] for r in REGIONS]), k),
                                  'shade share: ' + ', '.join('%s %.2f' % (r, dm[r][1].sum() / max(1, dm[r][0].sum()))
                                                               for r in REGIONS if dm[r][0].sum() > MIN_PX)))
                for lname, key in ks.items():
                    d = camera_key(s['az'], *key)
                    el = key[1]
                    Qd = (lookqa.light_frames(B, el) or Q)
                    kw = dict(light=d, line=0.0, transparent=False)
                    if sh == 'head':
                        kw.update(draw=Fi.draw_head, variants={Fi.skin: 'bare'})
                    F = Qd.frame(s['cam'], **kw)
                    O = ours_masks(F, Fi.reg)
                    S = Fi.view_score(sh, v, d)
                    txt = '; '.join('%s IoU %.3f, shade %.2f / %.2f' % (r, S[r]['miou'], S[r]['ours'], S[r]['design'])
                                    for r in list(REGIONS) + ['face', 'neck'] if S.get(r, {}).get('px', 0) >= MIN_PX)
                    cells.append(('%s (%g, %g): score %.3f' % (lname, key[0], key[1], objective(S)),
                                  save(tag + '_%s.png' % lname.replace(' ', '_'), _tint(F['picture'], [O[r][1] for r in REGIONS], a=0.3), k),
                                  txt))
                    cells.append(('%s: against the design' % lname, save(tag + '_%s_diff.png' % lname.replace(' ', '_'),
                                                                          _diff(O, s['design']), k), ''))
                rows.append((bname, sh, v, s['az'], cells))
        first = False
    H = ['<!doctype html><meta charset=utf-8><title>Design light review</title><style>body{font:13px system-ui;'
         'margin:16px;background:#fafafa;color:#222}td{vertical-align:top;padding:4px}img{max-width:100%;border:1px '
         'solid #ddd}figcaption{font-size:12px;max-width:420px}h2{margin-top:28px}</style>',
         '<h1>The design light: design | board light | design light</h1><p>The design\'s shade tinted blue; ours drawn by '
         'charkit.render (the head bare, as the head sheet draws it), our shade tinted; against the design: both shaded '
         '(dark red), ours only (orange), the design\'s only (blue), both lit (pale), one side only (grey). Numbers: per '
         'region the shade and lit mean IoU with the drawing, and the shade share ours / the design\'s.</p>']
    for bname, sh, v, az, cells in rows:
        H.append('<h2>%s: %s %s (az %.1f)</h2><table><tr>' % (html.escape(bname), sh, v, az))
        for cap, img, txt in cells:
            H.append('<td><figure><img src="%s"><figcaption><b>%s</b><br>%s</figcaption></figure></td>' % (
                img, html.escape(cap), html.escape(txt)))
        H.append('</tr></table>')
    path = os.path.join(out, 'index.html')
    open(path, 'w').write('\n'.join(H))
    return path
