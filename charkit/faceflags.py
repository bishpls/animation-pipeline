"""Michael's face flags (2026-09-30 evening review) as measures: the iris against the lid opening, the lashes' detail, the
brows' shape, the default smile, the mouth's place in three-quarter and profile, the nose's mark in front and
three-quarter. Each is read the same way on the design (head_turnaround's front, three-quarter and profile heads;
head_construction's front and profile: the hair-free close-up) and on ours drawn from the same azimuth at the same
scale, aligned on the eyes, the hair hidden (the design's features are drawn over or under it; head_construction draws
none).

Ours is drawn twice per view: the QA's drawing (charkit.qa3d.draw: the toon renderer on the build's export) for the
picture and its ink, and an id pass for the feature classes (which object and material each pixel shows). The design's
classes come from its colours (sclera, iris, skin, ink) and where the ink lies against the eye (the upper lash line, the
lower lid line, the brow, the mouth, the nose mark).
"""
import numpy as np

SHEETS = {'turnaround': ('head_turnaround', 400.0, ('front', 'three_quarter', 'profile')),
          'construction': ('head_construction', 900.0, ('front', 'profile'))}
WIN = dict(x=0.42, top=0.30, bottom=-0.62)      # the face window round the eyes' midpoint (front, three-quarter) or the
                                                # eye (profile), in L
FACING = -1                                     # the sheets' heads turn to the picture's left


class FaceFrame:
    """an orthographic face window (qa3d.Frame's interface: pix, win, origin, zbuffer) at ppl pixels per L round an origin
    (u, z) in world units, the window in L."""

    def __init__(self, L, ppl, origin, win=WIN, ss=1):
        self.L, self.ppl = L, ppl
        self.pix = L / ppl / ss
        self.win = {k: v * L for k, v in win.items()}
        self.origin = tuple(origin)
        self.res = (int(round(2 * win['x'] * ppl)), int(round((win['top'] - win['bottom']) * ppl)))

    def zbuffer(self, items, az, ids=False):
        from .geom import raster
        return raster.window_zbuffer(items, az, self.origin, 1.0, self.pix, self.win, ids=ids)


def _az3(B, design=None):
    from . import qa3d
    Dz = design or qa3d.Design(B)
    got = Dz.sheet_measures()
    return float(got[0].get('az_three_quarter', 35.0)) if got else 35.0


def view_az(view, az3):
    return {'front': 0.0, 'three_quarter': az3, 'profile': 90.0}[view]


def origin(B, az, view):
    """the window's origin (u, z world) for a view: the eyes' midpoint (front, three-quarter) or the near eye (profile),
    each iris centre set level with the head's eye line, as the sheet's views are aligned on their eyes."""
    from . import qa3d
    from .faceqa import view as proj
    ic = np.asarray(qa3d.iris_centres(B), float)
    z = float(B.assembly['eye_z']) if 'eye_z' in B.assembly else float(ic[:, 2].mean())
    u = proj(ic, az)[0]
    if view == 'profile':
        u0 = float(u[np.argmax(ic[:, 0])])          # her left eye (+x), the one a left-facing profile shows
    else:
        u0 = float(u.mean())
    return (u0, z)


def face_surfaces(B):
    """the head as the boards draw it with the hair hidden: the skin unmasked (the 'bare' variant where there is one,
    as head_turnaround draws the neck bare) with its outline, the eyes' plates, lashes and brows, the mouth's pieces."""
    from . import qa3d
    sk = B.skin()
    var = 'bare' if sk.has('bare') else 'eval'
    S = qa3d.surfaces(B, sk, var)
    for o in B.objects():
        if o.group in ('eye', 'mouth', 'face') and o.has('eval'):
            S += qa3d.surfaces(B, o, 'eval')
    return S


def draw_ours(B, view, ppl, az3, win=WIN):
    """ours drawn (qa3d.draw, the boards' light for the view) and its id pass -> dict(rgba, ids (surface index per
    pixel), surfs, frame, az)."""
    from . import qa3d
    az = view_az(view, az3)
    fr = FaceFrame(B.assembly['L'], ppl, origin(B, az, view), win)
    S = face_surfaces(B)
    rgba = qa3d.draw(B, S, az, FaceFrame(B.assembly['L'], ppl, fr.origin, win, ss=qa3d.FIG_SS))
    ids = qa3d.draw_ids(B, S, az, fr)
    return dict(rgba=rgba, ids=ids, surfs=S, frame=fr, az=az)


# ------------------------------------------------------------------------------------------------------------ design
def design_sheet(name, ppl):
    """a head sheet at ppl (charkit.refcheck.at_scale, its guide lines painted out) -> (rgb, heads {view: dict(box,
    eyes)})."""
    from . import refcheck
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rgb = refcheck._load(os.path.join(root, 'charkit', 'refs', 'clawd', 'gen', name + '.png'))
    rgb0, _ = refcheck.without_guides(np.asarray(rgb, float))
    small, f, H = refcheck.at_scale(rgb0, 0.168, 2 * 0.168 * ppl, FACING, guess=1.0)
    return small, H['heads']


def design_window(rgb, heads, view, ppl, win=WIN):
    """the design's face window for a view, aligned on its eyes as ours is (origin()), past the sheet's edge its paper
    -> rgb (H, W, 3)."""
    eyes = heads[view]['eyes']
    if view == 'profile':
        cx, cy = eyes[0]
    else:
        cx, cy = np.mean(eyes, 0)
    W, H = int(round(2 * win['x'] * ppl)), int(round((win['top'] - win['bottom']) * ppl))
    x0, y0 = int(round(cx - win['x'] * ppl)), int(round(cy - win['top'] * ppl))
    out = np.ones((H, W, 3)) * paper_of(rgb)
    ys, xs = slice(max(0, y0), min(rgb.shape[0], y0 + H)), slice(max(0, x0), min(rgb.shape[1], x0 + W))
    out[ys.start - y0:ys.stop - y0, xs.start - x0:xs.stop - x0] = rgb[ys, xs]
    return out


# ------------------------------------------------------------------------------------------------------------ classes
CL = {'none': 0, 'skin': 1, 'sclera': 2, 'iris': 3, 'lash': 4, 'lower': 5, 'crease': 6, 'brow': 7, 'mouth': 8,
      'inside': 9, 'teeth': 10, 'tongue': 11, 'eyeline': 12, 'outline': 13, 'nose': 14, 'highlight': 15, 'other': 16}
_SKIN_SLOT = {'skin': 'skin', 'face_skin': 'skin', 'cavity': 'inside', 'eyeline': 'eyeline', 'line': 'outline'}


def _obj_class(o, slot, hull):
    """a surface's class from its object and material slot (ours)."""
    if hull:
        return 'outline'
    name = o.name
    mat = (o.materials[slot] if slot < len(o.materials) else '') or ''
    if o.group == 'skin':
        return _SKIN_SLOT.get(mat, 'skin')
    if name.startswith('sclera'):
        return 'sclera'
    if name.startswith('iris'):
        return 'iris'
    if name.startswith('lash'):
        return {0: 'lash', 1: 'lower', 2: 'crease'}.get(slot, 'lash')
    if name.startswith('brow'):
        return 'brow'
    if name == 'mouth_line':
        return 'mouth'
    if name in ('teeth', 'tongue'):
        return name
    if name.startswith('nose'):
        return 'nose' if 'high' not in mat else 'highlight'
    return 'other'


def ours_classes(B, view, ppl, az3, win=WIN, ss=2):
    """ours as classes (CL) from a z-buffer of the render's surfaces (qa3d.render_surfaces: each surface pulled in by its
    outline, the hull as an outline), the iris plate's texture alpha deciding iris against the white behind it; hair
    hidden -> label image (H, W) at ppl (a pixel takes the class covering most of its ss x ss samples)."""
    from . import qa3d
    from .geom import raster
    az = view_az(view, az3)
    L = B.assembly['L']
    org = origin(B, az, view)
    pix = 1.0 / ppl / ss
    items, kinds = [], []
    sk = B.skin()
    var = 'bare' if sk.has('bare') else 'eval'
    objs = [(sk, var)] + [(o, 'eval') for o in B.objects() if o.group in ('eye', 'mouth', 'face') and o.has('eval')]
    for o, v in objs:
        for V, T, tm, cull, Tl, hull in qa3d.render_surfaces(B, o, v):
            items.append((V / L, T, tm, cull)); kinds.append((o, v, Tl, hull))
    zb, lab, mi, ti, bc = raster.window_zbuffer(items, az, (org[0] / L, org[1] / L), 1.0, pix, win, ids=True)
    cls = np.zeros(lab.shape, int)
    for k, (o, v, Tl, hull) in enumerate(kinds):
        m = mi == k
        if not m.any():
            continue
        for s in np.unique(lab[m]):
            cls[m & (lab == s)] = CL[_obj_class(o, int(s), hull)]
        if o.name.startswith('iris') and not hull:
            _, mat = o.material(0)
            img = mat.get('image') if mat else None
            if img:
                t = B.image(img)
                luv = o.a(v, 'luv')
                tl = Tl[ti[m]]
                w = bc[m]
                u = luv[tl[:, 0]] * w[:, 0:1] + luv[tl[:, 1]] * w[:, 1:2] + luv[tl[:, 2]] * w[:, 2:3]
                a = qa3d._sample(t, u)[:, 3]
                sub = cls[m]
                sub[a < 0.5] = CL['sclera']
                cls[m] = sub
    if ss > 1:
        H, W = cls.shape[0] // ss, cls.shape[1] // ss
        c = cls[:H * ss, :W * ss].reshape(H, ss, W, ss).transpose(0, 2, 1, 3).reshape(H, W, ss * ss)
        n = np.stack([(c == k).sum(-1) for k in range(max(CL.values()) + 1)], -1)
        cls = n.argmax(-1)
    return cls


PAL = {0: (0.93, 0.93, 0.93), 1: (0.98, 0.86, 0.78), 2: (0.7, 0.85, 1.0), 3: (1.0, 0.72, 0.1), 4: (0.1, 0.1, 0.1),
       5: (0.35, 0.2, 0.5), 6: (0.6, 0.4, 0.4), 7: (0.55, 0.3, 0.15), 8: (0.8, 0.1, 0.2), 9: (0.5, 0.1, 0.1),
       10: (1, 1, 1), 11: (0.9, 0.4, 0.5), 12: (0.3, 0.6, 0.3), 13: (0.4, 0.4, 0.4), 14: (0.1, 0.4, 0.9),
       15: (0.6, 0.9, 1.0), 16: (1.0, 0.0, 1.0)}


def paint(cls):
    im = np.zeros(cls.shape + (3,))
    for k, c in PAL.items():
        im[cls == k] = c
    return im


# ------------------------------------------------------------------------------------------------------------ features
# Boxes where each feature is looked for, in L from its anchor (+ down, + toward the picture's right; the eye's centre,
# or the eye line at the face's axis for the mouth and nose). The same on both sides.
BROW_BOX = dict(x=(-0.14, 0.14), y=(-0.32, -0.15))       # round each eye's centre (y up is negative: rows run down):
                                                           # over the lash line and the lid's crease
INK_V = 0.45                                               # the design's ink: its brightest channel under this


def _hsv(rgb):
    from .target3d import hsv
    H, W = rgb.shape[:2]
    return tuple(a.reshape(H, W) for a in hsv(rgb.reshape(-1, 3)))


def _cc(m, min_px=1):
    """4-connected components of a mask -> [bool masks], largest first."""
    from scipy import ndimage
    lab, n = ndimage.label(m)
    if not n:
        return []
    sizes = np.bincount(lab.ravel())[1:]
    order = np.argsort(-sizes)
    return [lab == (k + 1) for k in order if sizes[k] >= min_px]


def _box_mask(shape, cx, cy, box, ppl):
    H, W = shape
    yy, xx = np.mgrid[0:H, 0:W]
    return ((xx >= cx + box['x'][0] * ppl) & (xx <= cx + box['x'][1] * ppl) &
            (yy >= cy + box['y'][0] * ppl) & (yy <= cy + box['y'][1] * ppl))


def design_classes(rgb, bg=None):
    """the design's pixels -> dict of masks: ink (lines), brown (a brow's fill: a warm mid-tone, darker than skin), red (a
    mouth's inside or lip), white (sclera, highlights), iris (amber), skin (pale warm), hair (saturated orange), paper."""
    h, s, v = _hsv(rgb)
    mx = rgb.max(-1)
    bg = paper_of(rgb) if bg is None else bg
    paper = (np.abs(rgb - bg).max(-1) < 0.04) & (s < 0.1)
    ink = mx < INK_V
    hair = (h >= 8) & (h <= 30) & (s > 0.5) & (v > 0.45) & ~ink
    iris = (h > 30) & (h < 66) & (s > 0.35) & (v > 0.45) & ~ink
    white = (s < 0.12) & (v > 0.88) & ~paper
    skin = (h >= 5) & (h <= 45) & (s >= 0.06) & (s < 0.32) & (v >= 0.78) & ~paper
    red = (((h < 12) | (h > 330)) & (s > 0.3) & (v < 0.85)) & ~ink
    brown = (h >= 0) & (h <= 40) & (s >= 0.22) & (v >= INK_V) & (v < 0.8) & ~hair & ~red
    return dict(ink=ink, hair=hair, iris=iris, white=white, skin=skin, red=red, brown=brown, paper=paper)


def ours_eye_px(B, view, ppl, az3, win=WIN):
    """our iris centres in a view's window pixels (x, y), with their sides, nearest the picture's left first."""
    from . import qa3d
    from .faceqa import view as proj
    az = view_az(view, az3)
    org = origin(B, az, view)
    ic = np.asarray(qa3d.iris_centres(B), float)
    L = B.assembly['L']
    z = float(B.assembly.get('eye_z', ic[:, 2].mean()))
    u = proj(ic, az)[0]
    out = []
    for k in range(len(ic)):
        side = 'L' if ic[k, 0] > 0 else 'R'
        if view == 'profile' and side != 'L':
            continue
        x = ((u[k] - org[0]) / L + win['x']) * ppl
        y = (win['top'] - (z - org[1]) / L) * ppl
        out.append((side, (float(x), float(y))))
    return sorted(out, key=lambda e: e[1][0])


def design_eye_px(heads, view, ppl, win=WIN):
    """the design's eyes in its view window's pixels (design_window's alignment), with our sides: the picture's left
    eye is her right in front; the three-quarter's near eye (the picture's right) and the profile's are her left."""
    eyes = sorted(heads[view]['eyes'])
    cx, cy = (eyes[0] if view == 'profile' else np.mean(eyes, 0))
    x0, y0 = int(round(cx - win['x'] * ppl)), int(round(cy - win['top'] * ppl))
    sides = ('L',) if view == 'profile' else ('R', 'L')
    return [(s, (float(e[0] - x0), float(e[1] - y0))) for s, e in zip(sides, eyes)]


# per view: where the mouth and the nose's mark are looked for, (x range, y range) in L from the anchor (the eyes'
# midpoint in front and three-quarter, the eye in profile; + right, + down)
BOXES = {
    'front': dict(mouth=((-0.20, 0.20), (0.12, 0.31)), nose=((-0.07, 0.07), (0.03, 0.155))),
    'three_quarter': dict(mouth=((-0.26, 0.16), (0.12, 0.31)), nose=((-0.24, 0.02), (0.05, 0.16))),
    'profile': dict(mouth=((-0.36, 0.0), (0.12, 0.31))),
}
EYE_R = 0.13                                     # L round an eye centre: its opening, lashes and lids (not its brow)


def _grow(m, n):
    from scipy import ndimage
    return ndimage.binary_dilation(m, iterations=int(n)) if n > 0 else m


def _fill(m):
    from scipy import ndimage
    return ndimage.binary_fill_holes(m)


def _face(skin, walls, seed):
    """the face's skin: the skin component reached from a seed pixel (x, y), walls kept out."""
    from scipy import ndimage
    m = skin & ~walls
    lab, n = ndimage.label(m)
    x, y = int(round(seed[0])), int(round(seed[1]))
    H, W = m.shape
    ys, xs = np.nonzero(m[max(0, y - 12):y + 13, max(0, x - 12):x + 13])
    if not len(ys):
        return np.zeros_like(m)
    k = int(np.argmin((ys - min(12, y)) ** 2 + (xs - min(12, x)) ** 2))
    return lab == lab[ys[k] + max(0, y - 12), xs[k] + max(0, x - 12)]


def features(view, ppl, eyes, masks):
    """a view's features from its class masks, the same code for the design and ours. masks: dict(skin, walls (the
    lines that bound the face), background (paper, or nothing drawn), hair, eye (the eyes' openings with their lids and
    lashes: kept out of the brow, mouth and nose), brow, mouth, nose_ink, nose_high). -> dict(ppl, view, eyes, anchor,
    face, lead (the face's leading edge per row, the column, NaN off it), brow {side: mask}, mouth, nose_ink, nose_high)."""
    H, W = masks['skin'].shape
    ey = float(np.mean([e[1][1] for e in eyes]))
    ax = eyes[0][1][0] if view == 'profile' else float(np.mean([e[1][0] for e in eyes]))
    F = dict(ppl=ppl, view=view, eyes=eyes, anchor=(ax, ey), shape=(H, W))
    near = max(eyes, key=lambda e: e[1][0])[1]
    F['face'] = _face(masks['skin'], masks['walls'], (near[0] - (0.02 if view == 'profile' else 0) * ppl,
                                                      near[1] + 0.12 * ppl))
    lead = np.full(H, np.nan)
    rows = np.nonzero(F['face'].any(1))[0]
    lead[rows] = np.argmax(F['face'][rows], 1)
    F['lead'] = lead
    eyez = masks['eye']
    F['brow'] = {}
    for side, (x, y) in eyes:
        bx = _box_mask((H, W), x, y, BROW_BOX, ppl) & masks['brow'] & ~eyez
        comps = [c for c in _cc(bx, 3) if np.ptp(np.nonzero(c)[1]) > 0.04 * ppl]
        if comps:
            best = comps[0]
            m = best.copy()                     # a brow drawn as a fill and its edge stroke: the parts beside it
            for c in comps[1:]:
                if (_grow(best, 0.01 * ppl) & c).any():
                    m |= c
            F['brow'][side] = m
    for feat in ('mouth', 'nose'):
        box = BOXES.get(view, {}).get(feat)
        if box is None:
            continue
        bm = _box_mask((H, W), ax, ey, dict(x=box[0], y=box[1]), ppl) & ~eyez
        if feat == 'mouth':
            comps = _cc(bm & masks['mouth'], 3)
            if comps:
                m = comps[0].copy()
                for c in comps[1:]:                 # a smile drawn as two strokes: those within 0.1 L of the biggest
                    if (_grow(comps[0], 0.1 * ppl) & c).any() and c.sum() >= 0.15 * comps[0].sum():
                        m |= c
                F['mouth'] = m
        else:
            away = ~_grow(F['mouth'], max(1, int(round(0.01 * ppl)))) if F.get('mouth') is not None else True
            F['nose_ink'] = bm & masks['nose_ink'] & away
            F['nose_high'] = bm & masks['nose_high'] & away
    return F


def design_features(rgb, view, ppl, eyes, bg=None):
    """the design's view window -> features(): its colour classes (design_classes; bg its sheet's paper), the lines that
    touch the paper or the hair (the head's outline) kept out of the mouth and nose."""
    C = design_classes(rgb, bg)
    ppx = max(1, int(round(0.008 * ppl)))
    H, W = rgb.shape[:2]
    eye = np.zeros((H, W), bool)
    yy, xx = np.mgrid[0:H, 0:W]
    for _, (x, y) in eyes:
        # the opening and its lids: the white, the iris and the ink round them, within EYE_R
        near = ((xx - x) ** 2 + ((yy - y) * 1.3) ** 2) <= (EYE_R * ppl) ** 2
        h, sat, val = _hsv(rgb)
        core = _grow(near & (C['white'] | C['iris'] | ((sat < 0.15) & (val > 0.6) & ~C['paper'])), 2 * ppx)
        lid = [c for c in _cc(near & C['ink'], 3) if (c & core).any()]
        eye |= _fill(core | (np.any(lid, 0) if lid else False))
    outer = _grow(C['paper'] | C['hair'], ppx)
    contour = np.zeros((H, W), bool)
    for c in _cc(C['ink'], 3):                  # the head's outline: ink touching the paper or the hair
        if (c & outer).any():
            contour |= c
    masks = dict(skin=C['skin'] | C['white'] | C['red'], walls=C['ink'] | C['hair'] | C['paper'] | C['brown'],
                 eye=eye, brow=(C['brown'] | C['ink']) & ~C['hair'], mouth=(C['ink'] | C['red']) & ~contour,
                 nose_ink=C['ink'] & ~contour, nose_high=C['white'] & ~_grow(eye, ppx))
    return features(view, ppl, eyes, masks), C


def ours_features(cls, view, ppl, eyes):
    """our class image (ours_classes) -> features()."""
    c = lambda *ks: np.isin(cls, [CL[k] for k in ks])
    eye = np.zeros(cls.shape, bool)
    ppx = max(1, int(round(0.008 * ppl)))
    for m in _cc(c('sclera', 'iris', 'lash', 'lower', 'eyeline', 'crease'), 3)[:2]:
        eye |= _fill(_grow(m, ppx))
    sil = _grow(c('none'), ppx)
    outline = c('outline')
    contour = np.zeros(cls.shape, bool)
    for comp in _cc(outline, 2):                # the head's own silhouette's line: outline touching nothing drawn
        if (comp & sil).any():
            contour |= comp
    masks = dict(skin=c('skin', 'highlight'), walls=c('outline', 'eyeline', 'lash', 'lower', 'brow', 'mouth', 'inside',
                                                       'none', 'nose'),
                 eye=eye, brow=c('brow'), mouth=c('mouth', 'inside', 'teeth', 'tongue'),
                 nose_ink=(c('nose') | outline) & ~contour, nose_high=c('highlight'))
    return features(view, ppl, eyes, masks)


# ------------------------------------------------------------------------------------------------------------ eyes
EYE_CROP = 0.42                                   # L: an eye's crop (qa3d.EYE_SIZE: our eye_image's window)
LASH_TIP = 0.012                                  # L: a lash spike's least length (its top-hat piece's extent)
LASH_THIN = 0.5                                   # a spike's mean width (area / length) at most this share of the band


def paper_of(rgb):
    """a sheet's paper colour: its border's median."""
    return np.median(np.concatenate([rgb[:4].reshape(-1, 3), rgb[-4:].reshape(-1, 3), rgb[:, :4].reshape(-1, 3)]), 0)


def design_eye_crops(rgb, eyes, ppl, size=EYE_CROP, bg=None):
    """each design eye cropped round its iris (size L square) as RGBA, the paper (bg: the sheet's, paper_of) transparent
    -> [(side, rgba)]."""
    bg = paper_of(rgb) if bg is None else bg
    n = int(round(size * ppl))
    out = []
    for side, (x, y) in eyes:
        x0, y0 = int(round(x - n / 2)), int(round(y - n / 2))
        c = np.ones((n, n, 3)) * bg
        ys, xs = slice(max(0, y0), min(rgb.shape[0], y0 + n)), slice(max(0, x0), min(rgb.shape[1], x0 + n))
        c[ys.start - y0:ys.stop - y0, xs.start - x0:xs.stop - x0] = rgb[ys, xs]
        a = (np.abs(c - bg).max(-1) > 0.05).astype(float)[..., None]
        out.append((side, np.concatenate([c, a], -1)))
    return out


def ours_eye_crops(B, view, ppl, az3, sides):
    from . import qa3d
    az = view_az(view, az3)
    return [(s, qa3d.eye_image(B, s, ppl, az=az)) for s in sides]


def iris_mask(rgba, S, ppl, ring=0.006):
    """the visible iris as drawn: its colour and its dark shades (a lid's shadow) grown from its lit colour (eyeqa.refine's,
    without the ellipse segment() fits to its box) with the pale glow of its lit bottom, its dark ring (the ink within
    `ring` L of it) and its highlights (the convex hull: an iris is convex, and a highlight on its edge notches its
    colour), inside the opening's reach."""
    from . import eyeqa
    from skimage.morphology import convex_hull_image
    ib = eyeqa._box(S['iris'])
    if ib is None:
        return np.zeros(S['opening'].shape, bool)
    h, s, v = _hsv(rgba[..., :3])
    on = rgba[..., 3] > 0.5
    H, W = on.shape
    yy, xx = np.mgrid[0:H, 0:W]
    ih = ib[3] - ib[2] + 1
    box = (xx >= ib[0] - 2) & (xx <= ib[1] + 2) & (yy >= ib[2] - 0.8 * ih) & (yy <= ib[3] + 2)
    amber = on & box & (h >= eyeqa.IRIS_HUE[0] - 13) & (h <= eyeqa.IRIS_HUE[1] + 5) & (s > 0.45) & (v > 0.12)
    pale = on & box & (h >= 33) & (h <= 70) & (s > 0.15) & (v > 0.55)       # the lit bottom's pale glow
    seed = S['iris'] & amber
    grown = eyeqa._grow(seed, amber | pale, int(ih))
    grown |= S['pupil'] & box
    if not grown.any():
        return grown
    dark = on & (rgba[..., :3].max(-1) < INK_V)
    grown = eyeqa._grow(grown, dark, max(1, int(round(ring * ppl))))
    return convex_hull_image(grown)


def ellipse_rows(m, lo=0.15, hi=0.85):
    """an axis-aligned ellipse through a mask's side edges over the middle rows of its height: each row's half-width h
    fitted as h^2 = a^2 (1 - (y - cy)^2 / b^2) (least squares) -> (cx, cy, a, b) in px, or None. The height it implies
    (2b) is the iris's own, however much of it the lids hide."""
    rows = np.nonzero(m.any(1))[0]
    if len(rows) < 8:
        return None
    r0, r1 = rows[0], rows[-1]
    ys, hs, xs = [], [], []
    for r in range(int(r0 + lo * (r1 - r0)), int(r0 + hi * (r1 - r0)) + 1):
        c = np.nonzero(m[r])[0]
        if len(c):
            ys.append(r + 0.5); hs.append((c[-1] - c[0] + 1) / 2.0); xs.append((c[-1] + c[0] + 1) / 2.0)
    ys, hs = np.array(ys), np.array(hs)
    if len(ys) < 6:
        return None
    p2, p1, p0 = np.polyfit(ys, hs ** 2, 2)
    if p2 >= 0:
        return None
    cy = -p1 / (2 * p2)
    a2 = p0 - p1 ** 2 / (4 * p2)
    if a2 <= 0:
        return None
    return float(np.mean(xs)), float(cy), float(np.sqrt(a2)), float(np.sqrt(-a2 / p2))


def upper_lash(S, rgba):
    """the upper lash line: the ink over the opening (above its top edge in the opening's columns, and past its corners)
    in the component lying most along that edge -> mask or None. Ink: the picture's brightest channel under INK_V."""
    from . import eyeqa
    O = S['opening']
    ob = eyeqa._box(O)
    if ob is None:
        return None
    H, W = O.shape
    ink = (rgba[..., :3].max(-1) < INK_V) & (rgba[..., 3] > 0.5)
    top = np.full(W, -1)
    above = np.zeros((H, W), bool)
    mid = int((ob[2] + ob[3]) / 2)
    for cc in range(W):
        rr = np.nonzero(O[:, cc])[0]
        if len(rr):
            top[cc] = rr[0]
            above[:rr[0], cc] = True
        else:
            above[:mid, cc] = True
    reach = (np.arange(H)[:, None] >= ob[2] - 0.8 * (ob[3] - ob[2]))
    best, best_n = None, 0
    for comp in _cc(ink & above & reach, 4):
        n = sum(int(comp[max(0, top[cc] - 3):top[cc] + 1, cc].any()) for cc in range(ob[0], ob[1] + 1) if top[cc] >= 0)
        if n > best_n:
            best, best_n = comp, n
    return best


def eye_masks(rgba, ppl):
    """one eye's masks (eyeqa's segmentation, refined): the visible iris as drawn (iris_mask), the opening (the white
    and the iris, filled along rows), the upper lash line -> dict(I, O, U) or None."""
    from . import eyeqa
    S = eyeqa.segment(rgba)
    if eyeqa._box(S['opening']) is None or eyeqa._box(S['iris']) is None:
        return None
    S = eyeqa.refine(rgba, S)
    I = iris_mask(rgba, S, ppl)
    O = eyeqa._row_fill(S['sclera'] | I)
    U = upper_lash(dict(S, opening=O), rgba)
    return dict(I=I, O=O, U=U if U is not None else np.zeros_like(O))


def eye_numbers(E, ppl):
    """one eye's flag measures from its masks -> dict:
      iris_fit      the iris's own height (an ellipse through its side edges, ellipse_rows) over the opening's height at
                    its middle column: an iris inscribed in the opening, its top and bottom points on the lid lines, reads
                    1; one larger than the opening, clipped by the lids, over 1
      iris_top, iris_bottom   where that ellipse's top and bottom fall inside the opening's (+) or past it (-), in
                    opening heights
      lash_band     the upper lash line's thickness over the opening's middle 60% (median, L)
      lash_spikes   its spikes and flicks: its pieces thinner than its band (what an opening by a disk of 0.45 x the
                    band removes) at least LASH_TIP long and at most LASH_THIN of the band wide
      lash_gaps     the skin between its strokes: its convex hull less itself, clear of the opening, in pieces"""
    from . import eyeqa
    from scipy import ndimage
    from skimage.morphology import convex_hull_image
    if E is None:
        return {'found': False}
    I, O, U = E['I'], E['O'], E['U']
    out = {'found': True}
    E2 = ellipse_rows(I) if I.any() else None
    if E2 is not None:
        cx = int(np.clip(round(E2[0]), 0, I.shape[1] - 1))
        oc = np.nonzero(O[:, cx])[0]
        if len(oc):
            oh = oc[-1] - oc[0] + 1
            out['iris_fit'] = round(2 * E2[3] / oh, 3)
            out['iris_top'] = round(float(E2[1] - E2[3] - oc[0]) / oh, 3)
            out['iris_bottom'] = round(float(oc[-1] + 1 - (E2[1] + E2[3])) / oh, 3)
            out['_ellipse'] = E2
    ob = eyeqa._box(O)
    if U.any() and ob is not None:
        c0, c1 = ob[0] + 0.2 * (ob[1] - ob[0]), ob[1] - 0.2 * (ob[1] - ob[0])
        cols = [c for c in range(int(np.ceil(c0)), int(c1) + 1) if U[:, c].any()]
        th = float(np.median([U[:, c].sum() for c in cols])) if cols else 0.0
        out['lash_band'] = round(th / ppl, 4)
        r = max(1, int(round(0.45 * th)))
        disk = np.hypot(*np.mgrid[-r:r + 1, -r:r + 1]) <= r
        tips = U & ~ndimage.binary_opening(U, structure=disk)
        amin = max(2, int(round((0.004 * ppl) ** 2)))
        n = 0
        for c in _cc(tips, amin):
            ln = max(np.ptp(np.nonzero(c)[0]), np.ptp(np.nonzero(c)[1])) + 1
            if ln >= LASH_TIP * ppl and c.sum() / ln <= LASH_THIN * max(th, 1.0):
                n += 1                          # long, and thin against the band: a lash, not a lump
        out['lash_spikes'] = n
        gaps = convex_hull_image(U) & ~U & ~_grow(O, max(1, int(round(0.004 * ppl))))
        out['lash_gaps'] = len(_cc(gaps, amin))
        out['_tips'] = tips
    return out


# ------------------------------------------------------------------------------------------------------------ numbers
def _line_curve(m, ppl):
    """a drawn line (a mouth): its columns' middle rows -> dict(width L, sag (the middle below the chord through its
    ends, over the width: + a smile), thick (its median column height over its middle third, L), cx, cy px)."""
    cols = np.nonzero(m.any(0))[0]
    if len(cols) < 3:
        return None
    ys = np.array([np.nonzero(m[:, c])[0].mean() for c in cols])
    th = np.array([m[:, c].sum() for c in cols])
    c0, c1 = cols[0], cols[-1]
    w = c1 - c0 + 1
    k = max(1, int(round(0.08 * len(cols))))
    ya, yb = ys[:k].mean(), ys[-k:].mean()
    chord = ya + (cols - c0) / max(1, c1 - c0) * (yb - ya)
    mid = (cols >= c0 + w / 3) & (cols <= c1 - w / 3)
    yy, xx = np.nonzero(m)
    return dict(width=round(w / ppl, 4), sag=round(float((ys - chord)[mid].max() if mid.any() else 0) / w, 3),
                thick=round(float(np.median(th)) / ppl, 4),
                cx=float(xx.mean()), cy=float(yy.mean()))


def _brow_numbers(m, ppl):
    """a brow's shape: length (its column span, L), thick (its thickest column, L), taper (the thickness at 15% and 85%
    of its length over the thickest), arch (its middle row above the chord through its ends, over the length), and
    its mask centred on its centroid (for its shape IoU)."""
    cols = np.nonzero(m.any(0))[0]
    if len(cols) < 5:
        return None
    th = np.array([m[:, c].sum() for c in cols], float)
    ys = np.array([np.nonzero(m[:, c])[0].mean() for c in cols])
    n = len(cols)
    at = lambda f: th[int(round(f * (n - 1)))]
    k = max(1, int(round(0.06 * n)))
    ya, yb = ys[:k].mean(), ys[-k:].mean()
    chord = ya + np.arange(n) / max(1, n - 1) * (yb - ya)
    return dict(length=round(n / ppl, 4), thick=round(float(np.percentile(th, 90)) / ppl, 4),
                taper=round(float((at(0.15) + at(0.85)) / 2 / max(1e-9, np.percentile(th, 90))), 3),
                arch=round(float((chord - ys).max()) / n, 3))


def _centred(m, size):
    """a mask moved so its centroid sits at the middle of a (size, size) frame."""
    yy, xx = np.nonzero(m)
    out = np.zeros((size, size), bool)
    if not len(yy):
        return out
    y = yy - int(round(yy.mean())) + size // 2
    x = xx - int(round(xx.mean())) + size // 2
    ok = (y >= 0) & (y < size) & (x >= 0) & (x < size)
    out[y[ok], x[ok]] = True
    return out


def _iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else None


CORNER_COLS = (0.05, 0.075, 0.1, 0.125, 0.15)           # the opening's outermost shares of its width read as its far corner
                                                  # (their mean: one share's few columns at 400 px per L read 0.04 of
                                                  # the opening's height off with the drawing moved a pixel)
CONTOUR_ROWS = (0.17, 0.25)                       # L under the eye line: the lower face at the mouth's height


def corner_share(E, side):
    """an eye's far (outer) corner: the middle row of the opening's outermost CORNER_COLS of its columns (her left eye
    'L' the picture's right, her right eye the left; in profile the backmost), as a share of the opening's height from
    its bottom row (0 the bottom, 1 the top) -> float or None. Orthographic views keep a point's height, so a model's
    corner reads the same in every view unless the backmost point in profile is another point of the opening."""
    if E is None or not E['O'].any():
        return None
    O = E['O']
    rows, cols = np.nonzero(O.any(1))[0], np.nonzero(O.any(0))[0]
    top, bot = rows[0], rows[-1]
    got = []
    for share in np.atleast_1d(CORNER_COLS):
        k = max(2, int(round(share * (cols[-1] - cols[0] + 1))))
        sel = cols[-k:] if side == 'L' else cols[:k]
        rr = np.nonzero(O[:, sel].any(1))[0]
        got.append((bot - (rr.min() + rr.max()) / 2) / (bot - top + 1))
    return round(float(np.mean(got)), 3)


def contour_at(F, rows_L):
    """the face's leading contour (its leftmost face column per row: in three-quarter the far cheek) at the given band
    of heights (L under the eye line): its mean distance to the left of the anchor (the eyes' midpoint), L -> float or
    None."""
    ppl = F['ppl']
    ax, ey = F['anchor']
    r0, r1 = int(round(ey + rows_L[0] * ppl)), int(round(ey + rows_L[1] * ppl))
    lead = F['lead'][max(0, r0):max(0, r1) + 1]
    lead = lead[np.isfinite(lead)]
    if len(lead) < 0.5 * (r1 - r0 + 1):
        return None
    return round(float((ax - lead).mean()) / ppl, 4)


def numbers(F):
    """a view's features (features(), with 'eye_masks' {side: eye_masks()}) -> its flag measures (see the module)."""
    ppl, view = F['ppl'], F['view']
    ax, ey = F['anchor']
    N = {'view': view, 'eyes': {}, 'brows': {}}
    for side, E in (F.get('eye_masks') or {}).items():
        N['eyes'][side] = {k: v for k, v in eye_numbers(E, ppl).items() if not k.startswith('_')}
        c = corner_share(E, side)
        if c is not None:
            N['eyes'][side]['corner'] = c
    cm = contour_at(F, CONTOUR_ROWS)
    if cm is not None:
        N['contour_mouth'] = cm
    for side, m in F['brow'].items():
        b = _brow_numbers(m, ppl)
        if b:
            N['brows'][side] = b
    m = F.get('mouth')
    if m is not None and m.any():
        c = _line_curve(m, ppl)
        if c:
            row = int(round(c['cy']))
            lead = F['lead'][row] if 0 <= row < len(F['lead']) else np.nan
            N['mouth'] = dict(width=c['width'], sag=c['sag'], thick=c['thick'], x=round((c['cx'] - ax) / ppl, 4),
                              y=round((c['cy'] - ey) / ppl, 4),
                              lead=round((c['cx'] - lead) / ppl, 4) if np.isfinite(lead) else None)
            if view == 'profile':
                N['mouth'].update(_profile_marks(F, c['cy']))
    if 'nose_ink' in F:
        ink, hi = F['nose_ink'], F['nose_high']
        d = dict(ink=round(float(ink.sum()) / ppl ** 2 * 1e4, 3), high=round(float(hi.sum()) / ppl ** 2 * 1e4, 3))
        if ink.any():
            yy, xx = np.nonzero(ink)
            d.update(x=round((xx.mean() - ax) / ppl, 4), y=round((yy.mean() - ey) / ppl, 4),
                     height=round((np.ptp(yy) + 1) / ppl, 4))
        N['nose'] = d
    return N


def _profile_marks(F, my):
    """the profile's nose tip and chin on the face's leading edge (the nose: its furthest-forward row between 0.03 and
    0.2 L under the eye line; the chin: the face's lowest row still within 0.2 L of the nose's column) and the mouth's
    height between them -> dict(nose_y, chin_y (L under the eye line), between ((mouth - nose) / (chin - nose)))."""
    ppl = F['ppl']
    ey = F['anchor'][1]
    lead = F['lead']
    r0, r1 = int(ey + 0.03 * ppl), int(ey + 0.2 * ppl)
    seg = lead[r0:r1]
    if not np.isfinite(seg).any():
        return {}
    nr = r0 + int(np.nanargmin(seg))
    nx = lead[nr]
    rows = [r for r in range(nr, len(lead)) if np.isfinite(lead[r]) and lead[r] < nx + 0.2 * ppl]
    if not rows:
        return {}
    cr = max(rows)
    return dict(nose_y=round((nr - ey) / ppl, 4), chin_y=round((cr - ey) / ppl, 4),
                between=round((my - nr) / max(1, cr - nr), 3))


# ------------------------------------------------------------------------------------------------------------ reads
READS = (('turnaround', 'front'), ('turnaround', 'three_quarter'), ('turnaround', 'profile'),
         ('construction', 'front'), ('construction', 'profile'))
FLAG = {
    'iris': "Michael 2026-09-30: the iris doesn't fit (larger than the opening, past the sclera; the design's iris has "
            "its top and bottom points on the lid lines)",
    'lash': "Michael 2026-09-30: the eyelash detail is lost (a solid block of eyeshadow; the design's upper lash line has "
            "spikes, flicks and separation)",
    'brow': "Michael 2026-09-30: the eyebrow's shape and thickness are a little off",
    'smile': "Michael 2026-09-30: the default smile's shape is quite off-model",
    'place3q': "Michael 2026-09-30: in three-quarter view the mouth seems misplaced",
    'placeprof': "Michael 2026-09-30: in profile the mouth reads higher than the reference",
    'nose': "Michael 2026-09-30: the nose is invisible from the front and three-quarter views (the design draws a small "
            "nose mark there)",
    'corner': "Michael 2026-10-01 (item 4, approved for a fix): in profile the eye's far corner sits below the opening's "
              "middle where the design's sits above it, so the lash band slants and the profile spikes don't read",
    'contour': "Michael 2026-10-01 (item 2, approved for a fix): the lower face is too narrow at the mouth's height in "
               "three-quarter (its far contour 0.515 of the front half-width against the design's 0.656), part of the "
               "three-quarter mouth's miss",
    'forehead': "Michael 2026-10-01 (item 3, approved for a fix): the profile brow is short (0.097 L deep against 0.136): "
                "the forehead is flatter at brow height than the design's",
}


def _suffix(sheet, view):
    return ('closeup_' if sheet == 'construction' else '') + view


_DESIGN = {}


def design_read(sheet, view, shift=(0, 0)):
    """the design's features for a read (a sheet's view), with its eyes' masks; shift (rows, columns): the picture moved
    that many pixels against the anchor ours is aligned on (the calibration's moves). Memoized."""
    key = (sheet, view, tuple(shift))
    if key not in _DESIGN:
        name, ppl, _ = SHEETS[sheet]
        if (name, ppl) not in _DESIGN:
            _DESIGN[(name, ppl)] = design_sheet(name, ppl)
        rgb, heads = _DESIGN[(name, ppl)]
        d = design_window(rgb, heads, view, ppl)
        if shift != (0, 0):
            d = _shift(d, shift)
        eyes = design_eye_px(heads, view, ppl)
        F, _ = design_features(d, view, ppl, eyes, bg=paper_of(rgb))
        F['eye_masks'] = {s: eye_masks(a, ppl) for s, a in design_eye_crops(d, eyes, ppl, bg=paper_of(rgb))}
        F['picture'] = d
        _DESIGN[key] = F
    return _DESIGN[key]


def _shift(a, sh):
    """a picture moved (rows, columns) with its edge pixels repeated: each whole-pixel move and half a pixel more the
    same way (bilinear), so the move re-samples the drawing's anti-aliased edges too."""
    from scipy import ndimage
    dy, dx = sh
    a = ndimage.shift(a, (0.5 * np.sign(dy), 0.5 * np.sign(dx), 0), order=1, mode='nearest')
    out = np.roll(a, (dy, dx), (0, 1))
    if dy > 0:
        out[:dy] = out[dy:dy + 1]
    elif dy < 0:
        out[dy:] = out[dy - 1:dy]
    if dx > 0:
        out[:, :dx] = out[:, dx:dx + 1]
    elif dx < 0:
        out[:, dx:] = out[:, dx - 1:dx]
    return out


def ours_read(B, sheet, view, az3, picture=False):
    """our features for a read, drawn at the sheet's scale from its view's azimuth."""
    name, ppl, _ = SHEETS[sheet]
    cls = ours_classes(B, view, ppl, az3)
    eyes = ours_eye_px(B, view, ppl, az3)
    F = ours_features(cls, view, ppl, eyes)
    F['eye_masks'] = {s: eye_masks(a, ppl) for s, a in ours_eye_crops(B, view, ppl, az3, [s for s, _ in eyes])}
    F['cls'] = cls
    if picture:
        F['picture'] = draw_ours(B, view, ppl, az3)['rgba']
    return F


# ------------------------------------------------------------------------------------------------------------ checks
LIMITS = {                      # (pass, warn): ratios |ours / design - 1|, differences |ours - design|, or as noted; set
                                # at the thirds of the gap between the design's worst move and the flagged build
                                # (charkit/calib/records: the calibration rule, docs/workstreams/calib.md)
    'iris_fit': (0.10, 0.20),
    'lash_spikes': (0.70, 0.45),                # ours / design at least (fewer spikes than drawn: the block)
    'lash_gaps': (0.60, 0.35),                  # ours / design at least (the strokes run together)
    'lash_band': (0.20, 0.40),
    'brow_shape': (0.75, 0.60),                 # the brows' IoU, each centred on its centroid, at least
    'brow_thick': (0.12, 0.25),
    'brow_arch': (0.012, 0.022),
    'smile_width': (0.15, 0.30),
    'smile_curve': (0.02, 0.035),
    'smile_open': (1.6, 2.2),                   # ours' thickness over the drawn line's, at most
    'place3q': (0.02, 0.04),                    # L between the mouths' centres (from the leading contour, the eye line)
    'placeprof': (0.035, 0.06),                 # the mouth's height between the nose tip and the chin
    'nose': (0.35, 0.18),                       # ours' mark's ink over the drawn mark's: at least (and at most 1 / it)
    'nose_at': (0.015, 0.03),                   # L between the marks' centres
    'corner': (0.04, 0.06),                     # the far corner's height in the opening (share), ours less the design's
    'contour': (0.05, 0.10),                    # ratios: the three-quarter's far contour at the mouth's height
    'brow_len': (0.08, 0.15),                   # ratios: the brow's length (its column span) in the close-up's view
}


# reads reported, not graded (the reference can't resolve them: the triple's design moves don't hold, or a random
# stand-in passes; docs/workstreams/face6.md)
INFO = {
    ('iris', 'turnaround', 'profile'): "the head sheet's profile iris is about 15 px across: the design moved 1-2 px "
                                       "reads 0.98-1.12 against itself (graded on the close-up's profile)",
    ('lash_detail', 'turnaround', 'three_quarter'): "the head sheet's three-quarter lash line is drawn at 400 px per L "
                                                    "with the fringe's strands over it: its spikes read 0.6-0.8 against "
                                                    "themselves moved 1-2 px, and a smoothed lash keeps its 'gaps'",
}


def _st(v, lim, kind='abs'):
    p, w = lim
    if v is None:
        return 'FAIL'
    if kind == 'abs':
        return 'PASS' if abs(v) <= p else 'WARN' if abs(v) <= w else 'FAIL'
    if kind == 'ratio':
        return 'PASS' if abs(v - 1) <= p else 'WARN' if abs(v - 1) <= w else 'FAIL'
    if kind == 'min':
        return 'PASS' if v >= p else 'WARN' if v >= w else 'FAIL'
    if kind == 'max':
        return 'PASS' if v <= p else 'WARN' if v <= w else 'FAIL'
    if kind == 'band':                          # a ratio within [p, 1/p] PASS, [w, 1/w] WARN
        return 'PASS' if p <= v <= 1 / p else 'WARN' if w <= v <= 1 / w else 'FAIL'
    raise ValueError(kind)


RANKS = {'PASS': 0, 'WARN': 1, 'FAIL': 2}


def _worst(rows):
    """[(value, status, extra)] -> the worst row as a check dict."""
    rows = [r for r in rows if r is not None]
    if not rows:
        return None
    v, s, x = max(rows, key=lambda r: (RANKS[r[1]], 0))
    return dict(value=v, status=s, **x)


def _ratio(a, b):
    return round(a / b, 3) if a is not None and b not in (None, 0) else None


def compare(reads):
    """the flag checks from {(sheet, view): (design numbers, our numbers)} -> {check: dict}."""
    from .registry import flag_check
    C = {}
    reads = dict(reads)
    override = reads.pop(OVERRIDE, None)

    def put(name, flag, rows, info=None, **extra):
        c = _worst(rows)
        if c is None:
            C[name] = {'status': 'SKIPPED', 'why': 'not found on either side'}
            return
        c.update(extra)
        if info:                                # read, not graded: the reference can't resolve it (`info` says why)
            c['grade'], c['status'], c['why_info'] = c['status'], 'INFO', info
            C[name] = c
            return
        C[name] = flag_check(c, FLAG[flag])
    for (sheet, view), (Nd, No) in reads.items():
        sfx = _suffix(sheet, view)
        # the iris against the opening: every read
        rows = []
        for side, d in Nd['eyes'].items():
            o = No['eyes'].get(side) or {}
            r = _ratio(o.get('iris_fit'), d.get('iris_fit'))
            rows.append((r, _st(r, LIMITS['iris_fit'], 'ratio') if r is not None else 'FAIL',
                         dict(eye=side, ours=o.get('iris_fit'), design=d.get('iris_fit'),
                              ours_bottom=o.get('iris_bottom'), design_bottom=d.get('iris_bottom'))))
        put('eye_iris_fit_' + sfx, 'iris', rows, note="the iris's own height over the opening's, ours over the design's",
            info=INFO.get(('iris', sheet, view)))
        # the lashes: the close-up's front and profile (hair-free), the three-quarter's near eye (the sheet's only one)
        if sheet == 'construction' or view == 'three_quarter':
            sides = [s for s in Nd['eyes'] if view != 'three_quarter' or s == 'L']
            sp, bd, gp = [], [], []
            for side in sides:
                d, o = Nd['eyes'][side], No['eyes'].get(side) or {}
                r = _ratio(o.get('lash_spikes'), d.get('lash_spikes'))
                sp.append((r, _st(r, LIMITS['lash_spikes'], 'min'), dict(eye=side, ours=o.get('lash_spikes'),
                                                                         design=d.get('lash_spikes'))))
                r = _ratio(o.get('lash_gaps'), d.get('lash_gaps'))
                gp.append((r, _st(r, LIMITS['lash_gaps'], 'min'), dict(eye=side, ours=o.get('lash_gaps'),
                                                                       design=d.get('lash_gaps'))))
                r = _ratio(o.get('lash_band'), d.get('lash_band'))
                bd.append((r, _st(r, LIMITS['lash_band'], 'ratio'), dict(eye=side, ours=o.get('lash_band'),
                                                                         design=d.get('lash_band'))))
            put('eye_lash_spikes_' + sfx, 'lash', sp, note="the upper lash line's spikes and flicks, ours over the design's",
                info=INFO.get(('lash_detail', sheet, view)))
            put('eye_lash_band_' + sfx, 'lash', bd, note="the upper lash line's band thickness, ours over the design's")
            put('eye_lash_gaps_' + sfx, 'lash', gp, note="the skin between the lash line's strokes (separation), ours "
                                                         "over the design's", info=INFO.get(('lash_detail', sheet, view)))
        # the far corner's height in the opening: a symmetric model is read on both eyes' mean in front (the drawing's two
        # eyes differ by 0.04-0.09 of the opening), the near eye in three-quarter (the far eye's corner is foreshortened
        # to a few pixels) and in profile
        cd = {sd: e.get('corner') for sd, e in Nd['eyes'].items() if e.get('corner') is not None}
        co = {sd: e.get('corner') for sd, e in No['eyes'].items() if e.get('corner') is not None}
        pick = ('L', 'R') if view == 'front' else ('L',)
        dv = [cd[sd] for sd in pick if sd in cd]
        ov = [co[sd] for sd in pick if sd in co]
        if len(dv) == len(pick):
            if len(ov) == len(pick):
                a = round(float(np.mean(ov) - np.mean(dv)), 3)
                rows = [(a, _st(a, LIMITS['corner']), dict(ours=round(float(np.mean(ov)), 3),
                                                            design=round(float(np.mean(dv)), 3), eyes=list(pick)))]
            else:
                rows = [(None, 'FAIL', dict(why='no opening of ours found', design=round(float(np.mean(dv)), 3)))]
            put('eye_corner_' + sfx, 'corner', rows, note="the eye's far corner's height in its opening (share from its "
                                                          "bottom), ours less the design's")
        # the lower face's width at the mouth's height in three-quarter: the far cheek's contour from the eyes' midpoint
        if view == 'three_quarter' and Nd.get('contour_mouth') and No.get('contour_mouth') is not None:
            r = _ratio(No['contour_mouth'], Nd['contour_mouth'])
            put('face_contour_three_quarter', 'contour', [(r, _st(r, LIMITS['contour'], 'ratio'), dict(
                ours=No['contour_mouth'], design=Nd['contour_mouth'], rows=list(CONTOUR_ROWS)))],
                note="the far cheek's contour from the eyes' midpoint over the rows %.2f-%.2f L under the eye line "
                     "(the mouth's height), ours over the design's" % CONTOUR_ROWS)
        # the brows: the close-up (the turnaround's are under the fringe)
        if sheet == 'construction':
            ln = []
            for side, d in Nd['brows'].items():
                o = No['brows'].get(side)
                if o is not None:
                    r = _ratio(o['length'], d['length'])
                    ln.append((r, _st(r, LIMITS['brow_len'], 'ratio'), dict(eye=side, ours=o['length'],
                                                                            design=d['length'])))
            if ln:
                put('brow_len_' + sfx, 'forehead' if view == 'profile' else 'brow', ln,
                    note="the brow's length (its column span: in profile its depth on the forehead), ours over the "
                         "design's")
            sh, tk, ar = [], [], []
            for side, d in Nd['brows'].items():
                o = No['brows'].get(side)
                if o is None:
                    sh.append((None, 'FAIL', dict(eye=side, why='no brow of ours found')))
                    continue
                r = _ratio(o['thick'], d['thick'])
                tk.append((r, _st(r, LIMITS['brow_thick'], 'ratio'), dict(eye=side, ours=o['thick'], design=d['thick'])))
                a = round(o['arch'] - d['arch'], 3)
                ar.append((a, _st(a, LIMITS['brow_arch']), dict(eye=side, ours=o['arch'], design=d['arch'])))
                iou = (No.get('_brow_iou') or {}).get(side)
                sh.append((iou, _st(iou, LIMITS['brow_shape'], 'min'), dict(eye=side, ours_len=o['length'],
                           design_len=d['length'], ours_taper=o['taper'], design_taper=d['taper'])))
            put('brow_shape_' + sfx, 'brow', sh, note="the brows' IoU, each centred on its centroid (shape and thickness)")
            put('brow_thick_' + sfx, 'brow', tk, note="the brow's thickness, ours over the design's")
            put('brow_arch_' + sfx, 'brow', ar, note="the brow's arch (its middle over its chord, per length), ours less "
                                                     "the design's")
        # the default smile, in front (the turnaround: the mouth's authority; the close-up is read in the table)
        md, mo = Nd.get('mouth'), No.get('mouth')
        if view == 'front' and sheet == 'turnaround':
            if md and mo:
                r = _ratio(mo['width'], md['width'])
                put('mouth_smile_width', 'smile', [(r, _st(r, LIMITS['smile_width'], 'ratio'),
                                                    dict(ours=mo['width'], design=md['width']))])
                a = round(mo['sag'] - md['sag'], 3)
                put('mouth_smile_curve', 'smile', [(a, _st(a, LIMITS['smile_curve']), dict(ours=mo['sag'],
                                                                                           design=md['sag']))])
                r = _ratio(mo['thick'], md['thick'])
                put('mouth_smile_open', 'smile', [(r, _st(r, LIMITS['smile_open'], 'max'),
                                                   dict(ours=mo['thick'], design=md['thick']))])
        if view == 'three_quarter' and md and mo and md.get('lead') is not None and mo.get('lead') is not None:
            dd = round(float(np.hypot(mo['lead'] - md['lead'], mo['y'] - md['y'])), 4)
            put('mouth_place_three_quarter', 'place3q', [(dd, _st(dd, LIMITS['place3q']), dict(
                ours=[mo['lead'], mo['y']], design=[md['lead'], md['y']]))],
                note='L between the mouths: across from the leading contour at its row, down from the eye line')
        if view == 'profile' and md and mo and md.get('between') is not None and mo.get('between') is not None:
            a = round(mo['between'] - md['between'], 3)
            put('mouth_place_' + sfx, 'placeprof', [(a, _st(a, LIMITS['placeprof']), dict(
                ours=mo['between'], design=md['between'], ours_nose_chin=[mo.get('nose_y'), mo.get('chin_y')],
                design_nose_chin=[md.get('nose_y'), md.get('chin_y')]))],
                note="the mouth's height between the nose tip (0) and the chin (1), ours less the design's")
        # the nose's mark, front and three-quarter (the turnaround; the close-up's front in the table)
        nd, no = Nd.get('nose'), No.get('nose')
        if sheet == 'turnaround' and nd is not None and no is not None:
            r = _ratio(no['ink'], nd['ink'])
            put('nose_mark_' + view, 'nose', [(r, _st(r, LIMITS['nose'], 'band'), dict(ours=no['ink'], design=nd['ink'],
                ours_high=no['high'], design_high=nd['high'], ours_height=no.get('height'),
                design_height=nd.get('height')))], note="the nose mark's ink (1e-4 L^2), ours over the design's")
            if 'x' in no and 'x' in nd:
                dd = round(float(np.hypot(no['x'] - nd['x'], no['y'] - nd['y'])), 4)
                rows = [(dd, _st(dd, LIMITS['nose_at']), dict(ours=[no['x'], no['y']], design=[nd['x'], nd['y']]))]
            else:
                rows = [(None, 'FAIL', dict(why='no mark of ours' if 'x' in nd else 'no drawn mark'))]
            put('nose_mark_at_' + view, 'nose', rows, note="L between the marks' centres (from the eyes' midpoint)")
    if override is not None:                    # the three-quarter with the per-shot override on (mouth.VIEW's keys)
        (Nd, No), w = override[:2], (override[2] if len(override) > 2 else None)
        md, mo = Nd.get('mouth'), No.get('mouth')
        if md and mo and md.get('lead') is not None and mo.get('lead') is not None:
            dd = round(float(np.hypot(mo['lead'] - md['lead'], mo['y'] - md['y'])), 4)
            put('mouth_place_three_quarter_override', 'place3q', [(dd, _st(dd, LIMITS['place3q']), dict(
                ours=[mo['lead'], mo['y']], design=[md['lead'], md['y']], weights=w))],
                note="as mouth_place_three_quarter, with the drawn placement's per-shot keys (charkit.mouth.VIEW) at "
                     "their weights for the three-quarter's camera: the override a shot asks for (off by default)")
    return C


# ------------------------------------------------------------------------------------------------------------ shapes
def _moved(m, dy, dx):
    out = np.zeros_like(m)
    H, W = m.shape
    ys, xs = np.nonzero(m)
    y, x = ys + int(round(dy)), xs + int(round(dx))
    ok = (y >= 0) & (y < H) & (x >= 0) & (x < W)
    out[y[ok], x[ok]] = True
    return out


def _at(m, shape):
    """a mask cut or padded (bottom, right) to a shape."""
    out = np.zeros(shape, bool)
    h, w = min(shape[0], m.shape[0]), min(shape[1], m.shape[1])
    out[:h, :w] = m[:h, :w]
    return out


def _on_opening(E):
    """an eye's masks moved so its opening's centroid sits at the crop's middle."""
    yy, xx = np.nonzero(E['O'])
    H, W = E['O'].shape
    dy, dx = H / 2 - yy.mean(), W / 2 - xx.mean()
    return {k: _moved(v, dy, dx) for k, v in E.items()}


def pair(Fd, Fo, No):
    """what a read measures across both sides: our brows' IoU with the design's (each centred on its centroid) into
    No['_brow_iou'], and the pieces' shape IoUs for the anti-gaming guard -> {piece: IoU}: iris and lash (each eye's
    crop aligned on its opening: their shape in the eye), brow, mouth and nose (each centred on its centroid: their
    shape; lines thickened 0.006 L)."""
    ppl = Fd['ppl']
    size = int(round(0.4 * ppl))
    No['_brow_iou'] = {}
    for side, md in Fd['brow'].items():
        mo = Fo['brow'].get(side)
        if mo is not None:
            No['_brow_iou'][side] = round(_iou(_centred(md, size), _centred(mo, size)), 3)
    S = {}
    ious = {'iris': [], 'lash': [], 'brow': []}
    for side, Ed in (Fd.get('eye_masks') or {}).items():
        Eo = (Fo.get('eye_masks') or {}).get(side)
        if Ed is None or Eo is None:
            continue
        a, b = _on_opening(Ed), _on_opening(Eo)
        b = {k: _at(v, a['O'].shape) for k, v in b.items()}
        ious['iris'].append(_iou(a['I'], b['I']))
        ious['lash'].append(_iou(_grow(a['U'], 1), _grow(b['U'], 1)))
    ious['brow'] = list(No['_brow_iou'].values())
    for k, v in ious.items():
        v = [x for x in v if x is not None]
        if v:
            S[k] = round(float(np.mean(v)), 3)
    g = max(1, int(round(0.006 * ppl)))
    big = int(round(0.5 * ppl))
    if Fd.get('mouth') is not None and Fo.get('mouth') is not None:
        S['mouth'] = round(_iou(_centred(_grow(Fd['mouth'], g), big), _centred(_grow(Fo['mouth'], g), big)) or 0.0, 3)
    if 'nose_ink' in Fd and 'nose_ink' in Fo:
        a, b = (_grow(F['nose_ink'] | F['nose_high'], g) for F in (Fd, Fo))
        S['nose'] = round(_iou(_centred(a, big), _centred(b, big)), 3) if a.any() and b.any() else 0.0
    return S


SHAPE_READS = {'iris': ('turnaround',), 'lash': ('construction', 'turnaround'), 'brow': ('construction',),
               'mouth': ('turnaround',), 'nose': ('turnaround',)}


def shape_checks(per_read):
    """{(sheet, view): {piece: IoU}} -> the pieces' shape checks, INFO with `views` (the guard's reading): each piece
    from its reference sheet (SHAPE_READS: the close-up's for the lash's front and profile, where it has them)."""
    C = {}
    for piece, sheets in SHAPE_READS.items():
        views = {}
        for sheet in sheets:
            for (sh, view), S in per_read.items():
                if sh == sheet and piece in S and view not in views:
                    views[view] = S[piece]
        if views:
            C['face_piece_' + piece] = dict(value=round(float(np.mean(list(views.values()))), 3), status='INFO',
                                            views=views, note="the piece's shape IoU against the design per view (the "
                                                              "anti-gaming guard's reading)")
    return C


# ------------------------------------------------------------------------------------------------------------ the part
OVERRIDE = '_override'                          # reads' key of the three-quarter read with the per-shot override on


def view_override(B, az3):
    """the bundle with the drawn placement's per-shot keys (charkit.mouth.VIEW) at their weights for the three-quarter's
    camera, when the build has them -> (Bundle, weights) or None."""
    from . import mouth as mouthlib
    MK = mouthlib._knobs(B.spec.get('mouth'))
    sk = B.skin()
    if mouthlib.view_knobs(MK) is None or sk is None or not sk.has('base'):
        return None
    have = set(sk.keys('base'))
    w = {k: v for k, v in mouthlib.view_weights(MK, view_az('three_quarter', az3), 1.0).items() if k in have}
    if not any(w.values()):
        return None
    return B.keyed(w), w


def measure_reads(B, design=None, picture=False):
    """every read, both sides -> (reads {(sheet, view): (Nd, No)}, shapes {(sheet, view): {piece: IoU}}, features
    {(sheet, view): (Fd, Fo)}); with the per-shot mouth keys, reads[OVERRIDE] = (Nd, No, weights): the three-quarter
    read with them on (view_override)."""
    az3 = _az3(B, design)
    reads, shapes, feats = {}, {}, {}
    for sheet, view in READS:
        Fd = design_read(sheet, view)
        Fo = ours_read(B, sheet, view, az3, picture=picture)
        Nd, No = numbers(Fd), numbers(Fo)
        shapes[(sheet, view)] = pair(Fd, Fo, No)
        reads[(sheet, view)] = (Nd, No)
        feats[(sheet, view)] = (Fd, Fo)
    ov = view_override(B, az3)
    if ov is not None:
        Fo = ours_read(ov[0], 'turnaround', 'three_quarter', az3)
        reads[OVERRIDE] = (reads[('turnaround', 'three_quarter')][0], numbers(Fo), ov[1])
    return reads, shapes, feats


def checks_of(reads, shapes):
    C = compare(reads)
    C.update(shape_checks(shapes))
    return C


def _table(reads, shapes):
    strip = lambda N: {k: v for k, v in N.items() if not k.startswith('_')}
    T = {'%s_%s' % k: {'design': strip(r[0]), 'ours': strip(r[1]), 'shapes': shapes[k]}
         for k, r in reads.items() if k != OVERRIDE}
    if OVERRIDE in reads:
        r = reads[OVERRIDE]
        T['turnaround_three_quarter_override'] = {'design': strip(r[0]), 'ours': strip(r[1]), 'weights': r[2]}
    return T


from .registry import qa_part  # noqa: E402


@qa_part('face_flags', order=850, table='face_flags')
def part(B, design=None, out=None):
    """Michael's face flags (2026-09-30) measured against head_turnaround and head_construction per view (this module):
    the iris against the opening, the lashes' detail, the brows, the default smile, the mouth's place in three-quarter
    and profile, the nose's mark; each piece's shape IoU per view beside them (face_piece_*)."""
    reads, shapes, feats = measure_reads(B, design, picture=bool(out))
    if out:
        import os
        _save(os.path.join(out, 'qa_face_flags.png'), picture(feats))
    return _table(reads, shapes), checks_of(reads, shapes)


def overlay(F, bg):
    """a read's picture with its features drawn: the face region (green tint), brows (magenta), mouth (blue), nose ink
    (red) and highlight (cyan), the leading edge (orange), the eyes' irises (outlined orange) and lash lines (dark red)."""
    im = bg[..., :3] * (bg[..., 3:4] if bg.shape[-1] == 4 else 1) + (0.93 * (1 - bg[..., 3:4]) if bg.shape[-1] == 4
                                                                       else 0)
    im = np.array(im, float)
    im[F['face']] = im[F['face']] * 0.8 + 0.2 * np.array([0.5, 0.9, 0.5])
    for m in F['brow'].values():
        im[m] = (0.9, 0.2, 0.9)
    if F.get('mouth') is not None:
        im[F['mouth']] = (0.1, 0.3, 1.0)
    if 'nose_ink' in F:
        im[F['nose_ink']] = (1, 0, 0)
        im[F['nose_high']] = (0, 0.9, 0.9)
    for r, x in enumerate(F['lead']):
        if np.isfinite(x):
            im[r, int(x)] = (1, 0.5, 0)
    return im


def picture(feats):
    rows = []
    for key, (Fd, Fo) in feats.items():
        a = overlay(Fd, Fd['picture'])
        b = overlay(Fo, Fo['picture'] if 'picture' in Fo else np.concatenate([paint(Fo['cls']), np.ones(
            Fo['cls'].shape + (1,))], -1))
        h = max(a.shape[0], b.shape[0])
        pad = lambda x: np.pad(x, ((0, h - x.shape[0]), (0, 8), (0, 0)), constant_values=1.0)
        r = np.concatenate([pad(a), pad(b)], 1)
        if r.shape[0] > 400:                    # the close-up at the turnaround's scale
            k = int(np.ceil(r.shape[0] / 400))
            r = r[::k, ::k]
        rows.append(r)
    W = max(r.shape[1] for r in rows)
    rows = [np.pad(r, ((0, 8), (0, W - r.shape[1]), (0, 0)), constant_values=1.0) for r in rows]
    return np.concatenate(rows, 0)


def _save(path, im):
    from PIL import Image
    Image.fromarray((np.clip(im, 0, 1) * 255).astype(np.uint8)).save(path)
