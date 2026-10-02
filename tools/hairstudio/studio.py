"""The hair studio (coordinator, 2026-10-02; Michael: "how can you better measure what you're drawing, and give yourself
better ink and paper"): greenfield, a fast local loop on the laptop.

  paper     the design's four heads and ours at one scale (charkit.preview's window: 300 px per L, the eye line 1.2 L
            from the top), ours drawn by the QA's renderer with an exact hair mask (the hair objects' pixels)
  measures  descriptors read the same way from both (the design's hair by colour, ours by object), each naming a knob:
              volume     the hair's half-width per height band, left and right (L)            -> standoff, length
              hem        the hem's tips: count and scallop depth (back view, L)               -> clump count, split
              wave       the side outline's waviness: RMS about its smooth (L), zero crossings -> wave amp, waves
              flicks     outward bumps on the side outlines (count, mean prominence, L)        -> flick
              eyes       the share of the eye boxes the hair covers (front, three-quarter)    -> bang length, sides
              lines      ink density inside the hair (share of dark px in the eroded mask)    -> relief, clumps
              shadow     shadow share of the hair; shadow_detail its edge length / sqrt area (the drawing's
                         lock-shaped shadow patches read high; a smooth dome low)             -> normals, relief
            one error: the sum of each descriptor's distance over its scale (SCALES)
  history   every iteration's picture, numbers and error on one page (OUT/index.html)

    python studio.py design                      cache the design's crops and descriptors
    python studio.py measure BUNDLE TAG          a bundle's crops and descriptors
    python studio.py page                        the history page
"""
import json, os, sys, time
import numpy as np

ROOT = os.path.expanduser('~/animation-pipeline-3d')
sys.path.insert(0, ROOT)
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'studio')
os.makedirs(OUT, exist_ok=True)
from charkit import preview as pv                                   # noqa: E402

VIEWS = pv.DESIGN_VIEWS
P = pv.PPL_OUT
EYE_ROW = int(pv.WIN['up'] * P)
SCALES = dict(colour_noise=0.1, side_frag=15.0, side_patch=2.0, line_len=4.0, line_vert=0.15, volume=0.06, hem_tips=3.0, hem_depth=0.04, wave=0.012, wave_x=3.0, flicks=2.0, flick_prom=0.02,
              eyes=0.15, lines=0.04, shadow=0.12, outline_rough=0.003)   # (specks, patches: readings only; they don't separate the drawing's shine marks from noise)


def hair_by_colour(rgb):
    """the design's hair: the orange family (hue 8-30 deg, saturated, not dark ink, not the peach skin), gaps closed and
    holes (lines, the clips) filled."""
    from scipy import ndimage
    import colorsys
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx, mn = rgb.max(-1), rgb.min(-1)
    sat = (mx - mn) / np.maximum(mx, 1e-6)
    hue = np.zeros_like(mx)
    m = (mx == r) & (mx > mn)
    hue[m] = ((g - b)[m] / (mx - mn)[m]) % 6 * 60
    hair = (hue > 4) & (hue < 32) & (sat > 0.42) & (mx > 0.35)
    hair = ndimage.binary_closing(hair, iterations=2)
    hair = ndimage.binary_fill_holes(hair)
    lab, n = ndimage.label(hair)
    if n:
        sizes = ndimage.sum(hair, lab, range(1, n + 1))
        hair = np.isin(lab, 1 + np.where(sizes > 400)[0])
    return hair


def _apply_map(mask, mp, shape):
    """a mask cut and resampled as head_crop cut its picture (its want_map), nearest."""
    H, W = shape
    ys = (mp['y0'] + (np.arange(H) + 0.5) * mp['sy']).astype(int)
    xs = (mp['x0'] + (np.arange(W) + 0.5) * mp['sx']).astype(int)
    ok_y = (ys >= 0) & (ys < mask.shape[0])
    ok_x = (xs >= 0) & (xs < mask.shape[1])
    out = np.zeros(shape, bool)
    out[np.ix_(ok_y, ok_x)] = mask[np.ix_(ys[ok_y], xs[ok_x])]
    return out


def _apply_ids(ids, mp, shape):
    H, W = shape
    ys = (mp['y0'] + (np.arange(H) + 0.5) * mp['sy']).astype(int)
    xs = (mp['x0'] + (np.arange(W) + 0.5) * mp['sx']).astype(int)
    out = np.full(shape, -1, np.int64)
    ok_y = (ys >= 0) & (ys < ids.shape[0])
    ok_x = (xs >= 0) & (xs < ids.shape[1])
    out[np.ix_(ok_y, ok_x)] = ids[np.ix_(ys[ok_y], xs[ok_x])]
    return out


def design():
    """the design's heads WITHOUT the clips (Michael, 2026-10-02): the QA's hair shape truth, the head sheet with the
    clips repainted from the clips-free redraw (qa3d.Design.shape_head; the back view, which the clips don't reach,
    as drawn)."""
    d = pv.design_refs()
    rgb = pv._load(d['head'])
    from charkit import bundle as bl, qa3d, palette
    B = bl.load(os.environ.get('HAIRSTUDIO_BASE', os.path.expanduser('~/animation-pipeline-3d/charkit/out/hairbase/bundle')))
    palette.activate_spec(B.spec)
    st = qa3d.Design(B).shape_head('hair')
    if st is not None:
        st = np.asarray(st, float)
        st = st / 255.0 if st.max() > 1.5 else st
        print('clips-free head sheet', st.shape, 'vs', rgb.shape)
        if st.shape[:2] == rgb.shape[:2]:
            rgb = st[..., :3]
    res = {}
    for v, az in VIEWS:
        h = d['heads'][v]
        box = h['box']
        crop = pv.head_crop(rgb, h['eye_y'], d['head_ppl'], xlim=(box[0], box[2]), clip=True)
        res[v] = dict(rgb=crop, hair=hair_by_colour(crop))
    np.savez_compressed(os.path.join(OUT, 'design.npz'), **{'%s_%s' % (v, k): x for v in res for k, x in res[v].items()})
    return res


def load_design():
    p = os.path.join(OUT, 'design.npz')
    if not os.path.exists(p):
        return design()
    z = np.load(p)
    return {v: dict(rgb=z[v + '_rgb'], hair=z[v + '_hair']) for v, _ in VIEWS}


DRAW_TONE = {}


def draw_ours(B, az, ss=2, hide_groups=()):
    """preview.draw_design_view with the hair's object mask: -> (rgb, hair mask) in the design's window."""
    from charkit import qa3d
    from charkit.detailqa import _Window
    L = float(B.assembly['L'])
    c = np.array(B.assembly['centre'], float)
    c[2] = float(B.assembly['eye_z'])
    up, down, half = pv.WIN['up'], pv.WIN['down'], pv.WIN['half']
    c[2] += (up - down) / 2 * L
    fr = _Window(c, az, half * L, (up + down) / 2 * L, L / P / ss)
    surfs, hair_ids = [], []
    for o in B.objects():
        if o.group in hide_groups:
            continue
        variant = 'masked' if o.group == 'skin' and o.has('masked') else 'eval'
        if o.has(variant):
            got = qa3d.surfaces(B, o, variant)
            if o.group == 'hair':
                hair_ids += list(range(len(surfs), len(surfs) + len(got)))
            surfs += got
    aux = {}
    img = qa3d.draw(B, surfs, az, fr, transparent=True, ss=ss, aux=aux)
    a = img[..., 3:4]
    rgb = img[..., :3] * a + np.asarray(qa3d._srgb(np.array(qa3d.WORLD)))[None, None] * (1 - a)
    mesh = aux['mesh']
    hm = np.isin(mesh, hair_ids).astype(float)
    Hs, Ws = hm.shape
    H, W = rgb.shape[:2]
    hm = hm[:H * (Hs // H), :W * (Ws // W)].reshape(H, Hs // H, W, Ws // W).mean((1, 3)) > 0.5
    tone = aux.get('tone')
    if tone is not None:
        tone = np.where(np.isin(mesh, hair_ids), tone, np.nan)[ss // 2::Hs // H if Hs // H else 1, ss // 2::Ws // W if Ws // W else 1][:H, :W]
    DRAW_TONE['last'] = tone
    return rgb, hm


NAMES = {}
LOCK_DEPTH = {}
LOCK_S = {}
SHINE = os.environ.get('STUDIO_SHINE') == '1'
CONTOURS = os.environ.get('STUDIO_CONTOURS') == '1'
GROUP_COLOURS = {1: (0.6, 0.47, 0.86), 2: (0.93, 0.55, 0.7), 3: (0.95, 0.42, 0.6), 4: (0.98, 0.78, 0.4),
                 5: (0.96, 0.66, 0.3), 6: (0.85, 0.35, 0.35), 7: (0.65, 0.85, 0.35), 8: (0.75, 0.4, 0.55)}


def group_colour(ids):
    """the hair coloured by group as the design's breakdown sheet colours them (bangs red, side locks yellow, upper
    back purple, lower back pink, buns blue, ahoge teal, flyaways green)."""
    out = np.full(ids.shape + (3,), 0.93)
    out[(ids == -2) | (ids == -3)] = (0.72, 0.72, 0.74)
    for k in np.unique(ids[ids >= 0]):
        if k >= 100000:
            n = NAMES.get(int(k), '')
            c = (0.45, 0.62, 0.95) if 'bun' in n else (0.45, 0.85, 0.75) if 'ahoge' in n else \
                (0.65, 0.85, 0.35) if 'fly' in n else (0.5, 0.5, 0.5)
        else:
            c = GROUP_COLOURS.get(int(k) // 1000, (0.5, 0.5, 0.5))
        out[ids == k] = c
    return out


def lockmap(B, az, ss=2, skip_hair=False):
    """each hair lock (the groom's per-polygon clump id; else the object) a flat colour, everything else grey, z-buffered
    in draw_ours' window -> (H, W) int ids (-1 none, -2 not hair) at the window's resolution."""
    from charkit.detailqa import _Window
    L = float(B.assembly['L'])
    c = np.array(B.assembly['centre'], float)
    c[2] = float(B.assembly['eye_z'])
    up, down, half = pv.WIN['up'], pv.WIN['down'], pv.WIN['half']
    c[2] += (up - down) / 2 * L
    fr = _Window(c, az, half * L, (up + down) / 2 * L, L / P / ss)
    items, meta = [], []
    for k, o in enumerate(B.objects()):
        variant = 'masked' if o.group == 'skin' and o.has('masked') else 'eval'
        if not o.has(variant) or o.group == 'accessory' or (skip_hair and o.group == 'hair'):
            continue
        V, T, tm, _ = o.mesh(variant)
        items.append((V, T, np.zeros(len(T), int), np.zeros(len(T), bool)))
        poly = o.tris(variant)[1]
        cl = o.a(variant, 'clump') if o.group == 'hair' else None
        _hv = (o.a(variant, 'ao') if o.a(variant, 'ao') is not None else None) if os.environ.get('STUDIO_AO') == '1' else None
        meta.append((o.group == 'hair', poly, cl, 100000 + k, T, o.a(variant, 'sv') if o.group == 'hair' else None,
                     o.a(variant, 'uv') if o.group == 'hair' else None,
                     (1 - _hv if _hv is not None else o.a(variant, 'hv')) if o.group == 'hair' else None))
        NAMES[100000 + k] = o.name
    zb, lab, mi, ti, bc = fr.zbuffer(items, az, ids=True)
    LOCK_DEPTH['last'] = np.asarray(zb, float)[ss // 2::ss, ss // 2::ss]
    ids = np.full(mi.shape, -1, np.int64)
    sval = np.full(mi.shape, np.nan)
    uval = np.full(mi.shape, np.nan)
    hval = np.full(mi.shape, np.nan)
    for j, (is_hair, poly, cl, oid, Tm, svm, uvm, hvm) in enumerate(meta):
        px_ = mi == j
        if not px_.any():
            continue
        for arr, dst in ((svm, sval), (uvm, uval), (hvm, hval)):
            if arr is not None and len(arr) > Tm.max():
                dst[px_] = (arr[Tm[ti[px_]]] * bc[px_]).sum(-1)
    LOCK_S['last'] = sval[ss // 2::ss, ss // 2::ss]
    LOCK_S['u'] = uval[ss // 2::ss, ss // 2::ss]
    LOCK_S['h'] = hval[ss // 2::ss, ss // 2::ss]
    for j, (is_hair, poly, cl, oid, Tm, svm, uvm, hvm) in enumerate(meta):
        px = mi == j
        if not px.any():
            continue
        if not is_hair:
            nm_ = NAMES.get(oid, '')
            ids[px] = -3 if nm_.endswith('_skin') else (-4 if nm_.startswith(('sclera', 'iris', 'lash')) else -2)
        elif cl is not None and len(cl) == len(np.unique(poly)) or (cl is not None and len(cl) > poly.max()):
            ids[px] = cl[poly[ti[px]]]
        else:
            ids[px] = oid
    return ids[ss // 2::ss, ss // 2::ss]


CONTOUR_INK = (0.24, 0.08, 0.05)                                   # dark auburn, not black


GRAD_MODE = os.environ.get('STUDIO_GRADIENT_MODE', 'mul')
DEEP_SRGB = (0.6, 0.2, 0.1)
GP = json.loads(os.environ.get('STUDIO_GRADIENT_ARGS', '{}'))


def gradient_pass(rgb, ids, sval, uval, hval, along=GP.get('along', 0.3), across=GP.get('across', 0.22),
                  depth=GP.get('depth', 0.3), streak=GP.get('streak', 0.42), streak_band=tuple(GP.get('band', (0.08, 0.42))),
                  streak_col=(1.0, 0.86, 0.66), streak_u=GP.get('streak_u', 0.6)):
    """colour inside each lock (Michael: "how color is diffusing within a given strand ... color in depth"; the Land of
    the Lustrous reference): on the hair's pixels, multiply the renderer's colour by
      along   1 - along x s^1.4         bright near the root, deepening toward the tip
      across  1 - across x |u|^2        lit along the lock's ridge, deeper at its edges
      depth   1 - depth x (1 - h)       inner layers of the stack darker than the outer
    and lay a directional streak down each lock's middle near its root (s in streak_band, strongest where |u| is
    small), so every lock carries its own direction. A compositing stand-in for a hair shader's lock-space gradients."""
    out = rgb.copy()
    hair = (ids >= 0) & np.isfinite(sval) & np.isfinite(uval)
    if not hair.any():
        return out
    s_ = np.nan_to_num(sval); u_ = np.abs(np.nan_to_num(uval)); h_ = np.clip(np.nan_to_num(hval, nan=1.0), 0, 1)
    grp = np.where(ids >= 0, ids // 1000, -1)
    acr = np.where(grp == 1, across * GP.get('crown_across', 1.0), across)
    acr = np.where(grp == 6, across * GP.get('bangs_across', 1.0), acr)
    if GRAD_MODE == 'mix':
        # deepen toward a saturated deep orange (a painter mixing toward the shadow colour), not toward black
        t = 1 - (1 - along * s_ ** 1.4) * (1 - acr * u_ ** 4) * (1 - depth * (1 - h_))
        out[hair] = out[hair] * (1 - t[hair][:, None]) + np.asarray(DEEP_SRGB) * t[hair][:, None]
    else:
        f = (1 - along * s_ ** 1.4) * (1 - across * u_ ** 2) * (1 - depth * (1 - h_))
        out[hair] = out[hair] * f[hair][:, None]
    b0, b1 = streak_band
    w = np.clip(1 - np.abs((s_ - (b0 + b1) / 2) / ((b1 - b0) / 2)), 0, 1) ** 0.8 * np.clip(1 - u_ / streak_u, 0, 1) ** 1.5
    a = np.where(hair & (grp != 6) if GP.get('bangs_streak', 1.0) == 0 else hair, streak * w, 0.0)[..., None]
    out = out * (1 - a) + np.asarray(streak_col) * a
    return out


def shine_pass(rgb, ids, sval, band=(0.12, 0.3), groups=(1, 6), col=(1.0, 0.9, 0.74), amt=0.85):
    """shine marks that follow the locks: on the upper layer and the bangs, where a pixel lies in `band` of its lock's
    length and is lit (brighter than the hair's median), blended toward a warm highlight; it breaks lock by lock as
    anime shine does. A compositing stand-in for a shine channel in the hair material."""
    out = rgb.copy()
    g = np.where(ids >= 0, ids // 1000, -1)
    m = np.isin(g, groups) & np.isfinite(sval) & (sval > band[0]) & (sval < band[1])
    if not m.any():
        return out
    v = rgb.max(-1)
    lit = v > np.median(v[ids >= 0]) * 0.97
    m &= lit
    w = np.nan_to_num(np.clip(1 - np.abs((sval - (band[0] + band[1]) / 2) / ((band[1] - band[0]) / 2)), 0, 1) ** 0.6)
    a = np.where(m, amt * w, 0.0)[..., None]
    out = out * (1 - a) + np.asarray(col) * a
    return out


def contour_pass(rgb, ids, depth, L, jump=float(os.environ.get('STUDIO_CONTOUR_JUMP', 0.012)), ink=(0.12, 0.06, 0.05)):
    """ink where one lock's edge lies over another: the lock id changes between neighbouring pixels AND the depth jumps
    by more than `jump` L (touching shingles side by side get no line), on the nearer pixel's side; 1 px at the window's
    resolution. A compositing stand-in for a renderer line pass (an ID + depth edge pass in the toon renderer and the
    runtime's look)."""
    out = rgb.copy()
    d = np.where(np.isfinite(depth), depth, np.inf)
    hair = ids >= 0
    e = np.zeros(ids.shape, bool)
    thr = jump * L
    for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0)):
        nb_id = np.roll(ids, (dy, dx), (0, 1))
        nb_d = np.roll(d, (dy, dx), (0, 1))
        # this pixel is the nearer one of a pair across a lock change with a depth jump
        e |= hair & (nb_id != ids) & (nb_id >= 0) & (nb_d - d > thr)
    w = int(os.environ.get('STUDIO_INK_W', '1'))
    if w > 1:
        from scipy import ndimage
        e = ndimage.binary_dilation(e, iterations=w - 1) & (ids >= 0)
    out[e] = ink
    return out


def colour_ids(ids):
    out = np.full(ids.shape + (3,), 0.93)
    out[(ids == -2) | (ids == -3)] = (0.72, 0.72, 0.74)
    u = np.unique(ids[ids >= 0])
    r = np.random.default_rng(3)
    pal = {k: r.uniform(0.25, 0.95, 3) for k in u}
    for k in u:
        out[ids == k] = pal[k]
    return out


def ours(bundle_dir):
    from charkit import bundle as bl, palette
    B = bl.load(bundle_dir)
    palette.activate_spec(B.spec)
    res = {}
    for v, az in VIEWS:
        rgb, hm = draw_ours(B, az, hide_groups=('accessory',))
        crop, mp = pv.head_crop(rgb, EYE_ROW, P, want_map=True)
        tone = DRAW_TONE.get('last')
        ids = lockmap(B, az)
        if os.environ.get('STUDIO_GRADIENT') == '1':
            rgb = gradient_pass(rgb, ids, LOCK_S['last'], LOCK_S['u'], LOCK_S['h'])
        if SHINE:
            rgb = shine_pass(rgb, ids, LOCK_S['last'])
        if CONTOURS:
            rgb = contour_pass(rgb, ids, LOCK_DEPTH['last'], float(B.assembly['L']), ink=CONTOUR_INK)
            crop, mp = pv.head_crop(rgb, EYE_ROW, P, want_map=True)
        res[v] = dict(rgb=crop, hair=_apply_map(hm, mp, crop.shape[:2]), ids=_apply_ids(ids, mp, crop.shape[:2]))
        if tone is not None:
            t = np.nan_to_num(tone, nan=-1).round().astype(np.int64)
            res[v]['tone'] = _apply_ids(t, mp, crop.shape[:2])
    return res


# ------------------------------------------------------------------------------------------------ descriptors
def _extents(hair):
    """per row: the hair's leftmost and rightmost column (NaN where none), relative to the window's centre, in L."""
    H, W = hair.shape
    cols = np.arange(W)
    any_ = hair.any(1)
    left = np.where(any_, np.where(hair, cols, W).min(1), np.nan)
    right = np.where(any_, np.where(hair, cols, -1).max(1), np.nan)
    return (left - W / 2) / P, (right - W / 2) / P


def line_mask(rgb, hair, ids=None):
    """the interior lock lines, 1 px: ours where two locks meet (the lock map); the drawing's dark ink skeletonised;
    both inside the hair eroded off its outline."""
    from scipy import ndimage
    from skimage.morphology import skeletonize
    inner = ndimage.binary_erosion(hair, iterations=6)
    if ids is not None:
        a = ids
        edge = np.zeros_like(hair)
        edge[:, 1:] |= (a[:, 1:] != a[:, :-1]) & (a[:, 1:] >= 0) & (a[:, :-1] >= 0)
        edge[1:, :] |= (a[1:, :] != a[:-1, :]) & (a[1:, :] >= 0) & (a[:-1, :] >= 0)
        return edge & inner
    dark = (rgb.max(-1) < 0.3) & inner
    return skeletonize(dark) & inner


def line_stats(lines, hair):
    """line length per L^2 of hair, and the share of line pixels running within 30 deg of vertical (the flow)."""
    from scipy import ndimage
    area = max(hair.sum(), 1) / P ** 2
    n = lines.sum()
    if n < 10:
        return 0.0, 0.0
    f = lines.astype(float)
    gx, gy = ndimage.sobel(ndimage.gaussian_filter(f, 2), 1), ndimage.sobel(ndimage.gaussian_filter(f, 2), 0)
    Jxx, Jyy, Jxy = (ndimage.gaussian_filter(x, 3) for x in (gx * gx, gy * gy, gx * gy))
    ang = 0.5 * np.arctan2(2 * Jxy, Jxx - Jyy)                       # the gradient's direction; lines run across it
    vert = np.abs(np.cos(ang[lines])) > np.cos(np.radians(30))       # gradient ~horizontal: the line ~vertical
    return round(float(n / P / area), 2), round(float(vert.mean()), 3)


def tone_classes(rgb, hair, tone=None):
    """0 lit, 1 shade (ours: the renderer's tone; the drawing: its shade rule), -1 elsewhere."""
    from scipy import ndimage
    if tone is not None:
        t = np.where(hair & (tone >= 0), np.minimum(tone, 1), -1)
        return t
    v = rgb.max(-1)
    vs = ndimage.gaussian_filter(v, 1.2)
    med = np.median(vs[hair]) if hair.any() else 1.0
    t = np.where(hair, 0, -1)
    t[hair & (vs < 0.86 * med)] = 1
    t[hair & (v < 0.3)] = -1
    return t


def descriptors(rgb, hair, view, ids=None, tone=None):
    from scipy import ndimage, signal
    H, W = hair.shape
    y = (np.arange(H) - EYE_ROW) / P                                 # L under the eye line
    left, right = _extents(hair)
    d = {}
    # volume: half-widths in bands 0.1 L from 0.3 L above the eyes to 1.0 L under
    bands = np.arange(-0.3, 1.0, 0.1)
    vol = []
    for b0 in bands:
        m = (y >= b0) & (y < b0 + 0.1)
        l = np.nanmean(-left[m]) if np.isfinite(left[m]).any() else 0.0
        r = np.nanmean(right[m]) if np.isfinite(right[m]).any() else 0.0
        vol += [round(float(l), 4), round(float(r), 4)]
    d['volume'] = vol
    # the side outlines from the eye line down to the hem: waviness and flicks
    hem_y = y[hair.any(1)].max() if hair.any() else 0.0
    side = (y >= 0.0) & (y <= hem_y - 0.05)
    waves, crosses, flicks, proms = [], [], [], []
    for ext in (-left, right):
        e = ext[side]
        e = e[np.isfinite(e)]
        if len(e) < 20:
            continue
        sm = ndimage.gaussian_filter1d(e, 0.12 * P)
        res = e - sm
        waves.append(float(np.sqrt(np.mean(res ** 2))))
        crosses.append(int(np.sum(np.diff(np.sign(res)) != 0)) / max(len(e) / P, 1e-6))
        pk, pr = signal.find_peaks(e, prominence=0.015, distance=int(0.06 * P))
        flicks.append(len(pk))
        proms.append(float(np.mean(pr['prominences'])) if len(pk) else 0.0)
    d['wave'] = round(float(np.mean(waves)) if waves else 0.0, 4)
    rough = []
    for ext in (-left, right):
        e = ext[side]
        e = e[np.isfinite(e)]
        if len(e) >= 20:
            rough.append(float(np.sqrt(np.mean((e - ndimage.gaussian_filter1d(e, 0.02 * P)) ** 2))))
    d['outline_rough'] = round(float(np.mean(rough)) if rough else 0.0, 4)
    d['wave_x'] = round(float(np.mean(crosses)) if crosses else 0.0, 2)
    d['flicks'] = round(float(np.mean(flicks)) if flicks else 0.0, 2)
    d['flick_prom'] = round(float(np.mean(proms)) if proms else 0.0, 4)
    # the hem: the lowest hair per column, its tips (downward peaks) and their depth
    cols = hair.any(0)
    low = np.where(cols, H - 1 - np.argmax(hair[::-1], 0), np.nan)
    lowL = (low - EYE_ROW) / P
    seg = lowL[cols]
    if len(seg) > 20 and view in ('profile', 'back'):        # (front / 3q: the face's gap isn't a hem)
        pk, pr = signal.find_peaks(seg, prominence=0.02, distance=int(0.04 * P))
        d['hem_tips'] = int(len(pk))
        d['hem_depth'] = round(float(np.mean(pr['prominences'])) if len(pk) else 0.0, 4)
    else:
        d['hem_tips'], d['hem_depth'] = 0, 0.0
    # the eyes' boxes (front and three-quarter): the share covered by hair
    if view == 'front':                                             # (3q: the boxes don't land reliably)
        cx = W / 2
        ex = 0.168 * P if view == 'front' else 0.13 * P
        boxes = [(int(cx - ex - 0.09 * P), int(cx - ex + 0.09 * P)), (int(cx + ex - 0.09 * P), int(cx + ex + 0.09 * P))]
        r0, r1 = int(EYE_ROW - 0.07 * P), int(EYE_ROW + 0.07 * P)
        d['eyes'] = round(float(np.mean([hair[r0:r1, a:b].mean() for a, b in boxes])), 3)
    # lines and shadow inside the hair (eroded off the outline)
    inner = ndimage.binary_erosion(hair, iterations=6)
    v = rgb.max(-1)
    if inner.sum() > 100:
        dark = (v < 0.3) & inner
        d['lines'] = round(float(dark.mean() / inner.mean()), 4)
        near = ndimage.binary_dilation(dark, iterations=3)          # (ink lines' fringes aren't shadow)
        vs = ndimage.gaussian_filter(v, 1.2)
        body = inner & ~near
        med = np.median(vs[body]) if body.any() else 1.0
        shade = body & (vs < 0.86 * med)
        d['shadow'] = round(float(shade.sum() / max(body.sum(), 1)), 3)
        per = np.logical_xor(shade, ndimage.binary_erosion(shade)).sum()
        d['shadow_detail'] = round(float(per / np.sqrt(max(shade.sum(), 1))), 2)
        lab, n = ndimage.label(shade)
        sizes = ndimage.sum(shade, lab, range(1, n + 1)) / P ** 2 if n else np.zeros(0)
        area = max(inner.sum() / P ** 2, 1e-6)
        d['specks'] = round(float((sizes < 0.0015).sum() / area), 1)          # shadow bits under 0.0015 L^2, per L^2
        d['patches'] = round(float((sizes >= 0.004).sum() / area), 1)         # lock-sized shadow patches, per L^2
    else:
        d['lines'] = d['shadow'] = d['shadow_detail'] = d['specks'] = d['patches'] = 0.0
    ll, lv = line_stats(line_mask(rgb, hair), hair)       # drawn ink on both sides (the lock map is for the eye)
    from scipy import ndimage as _nd
    inner_ = _nd.binary_erosion(hair, iterations=4) & (rgb.max(-1) > 0.3)
    if inner_.sum() > 200:
        Y = rgb @ np.array([0.299, 0.587, 0.114])
        fine = Y - _nd.gaussian_filter(Y, 0.02 * P)
        d['colour_noise'] = round(float(fine[inner_].var() / max(Y[inner_].var(), 1e-9)), 3)
    if view == 'front':                                      # side fragmentation: tone patches in her right side's box
        from scipy import ndimage
        y0, y1, x0, x1 = 300, 620, 20, 260
        tm = tone_classes(rgb, hair, tone)[y0:y1, x0:x1]
        n, sizes = 0, []
        for k in (0, 1):
            lab, c = ndimage.label(tm == k)
            if c:
                sz = ndimage.sum(np.ones_like(lab), lab, range(1, c + 1))
                sz = sz[sz >= 30]
                n += len(sz); sizes += list(sz)
        area = max(hair[y0:y1, x0:x1].sum(), 1) / P ** 2
        d['side_frag'] = round(n / area, 1)
        d['side_patch'] = round(float(np.mean(sizes)) / P ** 2 * 1000, 2) if sizes else 0.0   # mean patch, 1e-3 L^2
    d['line_len'], d['line_vert'] = ll, lv
    return d


def error(dd, do):
    """per descriptor and view: |ours - design| / scale; the total their sum (the volume averaged over its bands)."""
    parts = {}
    for v in dd:
        for k, s in SCALES.items():
            if k not in dd[v] or k not in do[v]:
                continue
            a, b = dd[v][k], do[v][k]
            if isinstance(a, list):
                diff = float(np.mean(np.abs(np.array(a) - np.array(b))))
            else:
                diff = abs(a - b)
            parts['%s.%s' % (v, k)] = round(diff / s, 3)
    by = {}
    for k, x in parts.items():
        by[k.split('.')[1]] = by.get(k.split('.')[1], 0) + x
    return round(sum(parts.values()), 2), {k: round(x, 2) for k, x in sorted(by.items(), key=lambda t: -t[1])}, parts


TONES = np.array([(0.99, 0.93, 0.62), (0.88, 0.45, 0.3), (0.35, 0.12, 0.18)])     # lit, shade, deep


def tone_map_ours(t):
    out = np.full(t.shape + (3,), 0.95)
    for k in range(3):
        out[t == k] = TONES[k]
    return out


def tone_map_design(rgb, hair):
    from scipy import ndimage
    v = rgb.max(-1)
    vs = ndimage.gaussian_filter(v, 1.2)
    med = np.median(vs[hair]) if hair.any() else 1.0
    out = np.full(rgb.shape, 0.95)
    out[hair] = TONES[0]
    out[hair & (vs < 0.86 * med)] = TONES[1]
    out[hair & (v < 0.3)] = (0.1, 0.1, 0.1)
    return out


def save_closeups(tag, D, O):
    """2x close-ups where lock ends live: the front's left side (her right) from the cheek to the hem, and the back's
    hem; design above ours."""
    from PIL import Image
    def cut(img, v, box):
        x0, y0, x1, y1 = box
        c = img[y0:y1, x0:x1]
        return np.kron(c, np.ones((2, 2, 1)))
    boxes = {'front': (20, 300, 260, 620), 'back': (90, 380, 510, 640)}
    cols = []
    for v, box in boxes.items():
        parts = [cut(D[v]['rgb'], v, box), cut(O[v]['rgb'], v, box)]
        if 'ids' in O[v]:
            parts.append(cut(colour_ids(O[v]['ids']), v, box))
        cols.append(np.concatenate(parts, 0))
    h = max(c.shape[0] for c in cols)
    cols = [np.pad(c, ((0, h - c.shape[0]), (0, 12), (0, 0)), constant_values=1.0) for c in cols]
    Image.fromarray((np.clip(np.concatenate(cols, 1), 0, 1) * 255).astype(np.uint8)).save(
        os.path.join(OUT, tag + '_close.png'))


def save_side(tag, D, O):
    from PIL import Image
    tiles = []
    for v, _ in VIEWS:
        a, b = D[v]['rgb'], O[v]['rgb']
        ov = b.copy()
        dm, om = D[v]['hair'], O[v]['hair']
        edge = lambda m: m & ~np.roll(m, 1, 0) | m & ~np.roll(m, 1, 1) | m & ~np.roll(m, -1, 0) | m & ~np.roll(m, -1, 1)
        ov[edge(dm)] = (0.1, 0.35, 0.95)
        rows = [a, b, ov]
        if 'ids' in O[v]:
            lm = colour_ids(O[v]['ids'])
            lm[line_mask(None, O[v]['hair'], O[v]['ids'])] = 0.05
            dl = np.full(a.shape, 0.97)
            dl[D[v]['hair']] = (0.98, 0.86, 0.78)
            dl[line_mask(a, D[v]['hair'])] = 0.05
            rows += [dl, lm, group_colour(O[v]['ids'])]
        if 'tone' in O[v]:
            rows += [tone_map_design(a, D[v]['hair']), tone_map_ours(O[v]['tone'])]
        tiles.append(np.concatenate(rows, 0))
    img = (np.clip(np.concatenate(tiles, 1), 0, 1) * 255).astype(np.uint8)
    Image.fromarray(img).save(os.path.join(OUT, tag + '.png'))


def measure(bundle_dir, tag, note=''):
    D = load_design()
    dd = {v: descriptors(D[v]['rgb'], D[v]['hair'], v) for v, _ in VIEWS}
    cp = os.path.join(OUT, tag + '_ours.npz')
    if bundle_dir == '-' and os.path.exists(cp):
        z = np.load(cp)
        O = {v: dict(rgb=z[v + '_rgb'], hair=z[v + '_hair'], **({'ids': z[v + '_ids']} if v + '_ids' in z.files else {}), **({'tone': z[v + '_tone']} if v + '_tone' in z.files else {})) for v, _ in VIEWS}
    else:
        O = ours(bundle_dir)
        np.savez_compressed(cp, **{'%s_%s' % (v, k): x for v in O for k, x in O[v].items()})
    do = {v: descriptors(O[v]['rgb'], O[v]['hair'], v, O[v].get('ids'), O[v].get('tone')) for v, _ in VIEWS}
    total, by, parts = error(dd, do)
    save_side(tag, D, O)
    save_closeups(tag, D, O)
    hist = os.path.join(OUT, 'history.json')
    H = json.load(open(hist)) if os.path.exists(hist) else []
    H = [h for h in H if h['tag'] != tag] + [dict(tag=tag, note=note, error=total, by=by, ours=do, design=dd,
                                                  at=time.strftime('%H:%M'))]
    json.dump(H, open(hist, 'w'), indent=1)
    print(tag, 'error', total, json.dumps(by))
    return total, by


def page():
    H = json.load(open(os.path.join(OUT, 'history.json')))
    rows = []
    for h in H:
        by = ' · '.join('%s %.2f' % (k, v) for k, v in list(h['by'].items())[:6])
        rows.append('<div class="it"><h3>%s <span>error %.2f</span></h3><p class="n">%s</p><p class="b">%s</p>'
                    '<img src="%s.png"></div>' % (h['tag'], h['error'], h.get('note', ''), by, h['tag']))
    css = (':root{--bg:#f4f4f6;--fg:#1c1c20;--card:#fff;--line:#ddd}@media (prefers-color-scheme:dark){'
           ':root:not([data-theme="light"]){--bg:#161619;--fg:#e9e9ee;--card:#222227;--line:#3a3a42}}'
           'body{background:var(--bg);color:var(--fg);font:14px/1.4 -apple-system,system-ui,sans-serif;margin:0;'
           'padding:16px}.it{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px;'
           'margin:12px 0}h3 span{font-weight:400;opacity:.75;margin-left:8px}img{max-width:100%;border-radius:6px}'
           '.n{margin:2px 0}.b{font-size:12px;opacity:.75;margin:2px 0 8px}')
    sp = os.path.join(OUT, 'summary.html')
    summary = open(sp).read() if os.path.exists(sp) else ''
    rows = [summary] + rows
    html = ('<!doctype html><html><head><meta charset="utf-8"><title>Hair Studio</title><style>%s</style></head><body>'
            '<h1>Hair studio: iteration history</h1><p>Each picture: per view (front, three-quarter, profile, back), '
            'top the design, middle ours, bottom ours with the design hair outline in blue. Error: the descriptors\' '
            'summed distance to the design (lower is better); the six largest parts after it.</p>%s</body></html>'
            % (css, ''.join(rows)))
    open(os.path.join(OUT, 'index.html'), 'w').write(html)


def cycle_page(tag, title, notes):
    H = json.load(open(os.path.join(OUT, 'history.json')))
    h = next(x for x in H if x['tag'] == tag)
    prev = [x for x in H if x['tag'] != tag]
    keys = ['volume', 'wave', 'flick_prom', 'flicks', 'hem_tips', 'hem_depth', 'eyes', 'outline_rough', 'line_len',
            'line_vert', 'shadow']
    def val(x):
        return '%.3f' % np.mean(x) if isinstance(x, list) else str(x)
    rows = ''
    for v, _ in VIEWS:
        for k in keys:
            if k in h['design'][v]:
                rows += '<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (v, k, val(h['design'][v][k]),
                                                                                  val(h['ours'][v][k]))
    hist = ' &rarr; '.join('%s %.1f' % (x['tag'], x['error']) for x in H)
    html = ('<!doctype html><html><head><meta charset="utf-8"><title>%s</title><style>body{font:14px/1.4 -apple-system,'
            'system-ui,sans-serif;margin:16px;background:#f5f5f7;color:#1c1c20}@media (prefers-color-scheme:dark){body{'
            'background:#161619;color:#e9e9ee}}img{max-width:100%%;border-radius:6px}table{border-collapse:collapse;'
            'font-size:12px}td{padding:2px 8px;border-bottom:1px solid #8884}.e{font-size:18px}</style></head><body>'
            '<h2>%s</h2><p class="e">error <b>%.2f</b> &nbsp; <small>(%s)</small></p><div>%s</div>'
            '<p><small>Rows per view: design · ours · ours with the design outline · the design\'s lock lines · our '
            'lock map (each lock a colour, lock lines black) · our groups in the breakdown sheet\'s colours (compare the sheet below) · tone, the design then ours: yellow lit, orange shade, purple deep</small></p><p><small>Close-ups at 2x (her right side from the cheek down, and the back hem): the design, ours, our lock map</small></p><img src="%s_close.png"><img src="%s.png"><p><small>The design\'s breakdown sheet (front, profile, back):</small></p><img src="breakdown.png" style="max-width:60%%"><h3>Descriptors (design · ours)'
            '</h3><table>%s</table></body></html>' % (title, title, h['error'], hist, notes, tag, tag, rows))
    path = os.path.join(OUT, tag + '.html')
    open(path, 'w').write(html)
    return path


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'design':
        design(); print('design cached')
    elif cmd == 'measure':
        measure(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else '')
        page()
    elif cmd == 'cycle':
        tag, title, notes = sys.argv[2], sys.argv[3], open(sys.argv[4]).read()
        print(cycle_page(tag, title, notes))
    elif cmd == 'remeasure':
        for h in json.load(open(os.path.join(OUT, 'history.json'))):
            measure('-', h['tag'], h.get('note', ''))
        page()
    elif cmd == 'page':
        page()
