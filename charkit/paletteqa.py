"""Palette QA: the design's colours against ours, class by class (pure numpy).

The design's come from the model sheet's own pixels: the full figures' class images (charkit.bodyqa.design_views, lines
kept apart), each class's pixels a pixel in from its edges (anti-aliasing is neither colour; the iris, a few pixels
at the sheet's scale, whole, and only round the eyes, not the star clip that shares its yellow), split into a lit and a shade tone at the lightness that best separates
them (Otsu on L*); a tone is its pixels' median. Ours are the materials' flat tones as they render unlit
(charkit.qa3d.material_tones: toon3's lit and shade, a texture sampled where it is used), the area-weighted median over
the class's triangles.

Graded: CIEDE2000 (dE00) between each class's lit tones, and between its shade tones where both have one; the lightness
and chroma differences ride along (+dL = ours lighter; paler = lighter and less chroma).

    from charkit import paletteqa
    D = paletteqa.extract([(rgb, cls), ...])                 # any pictures with class images (bodyqa.CLASS ids)
    O = paletteqa.ours(cols)                                  # charkit.qa3d.scene_classes' colours
    C = paletteqa.compare(O, D)
"""
import numpy as np

CLASSES = {'skin': 1, 'hair': 2, 'iris': 3, 'orange': 6, 'cream': 7, 'dark': 8, 'white': 9}
LIMITS = {'lit': (5.0, 10.0), 'shade': (7.0, 14.0)}      # dE00: (pass within, warn within); else fail
MIN_PX = 60                                               # a tone from fewer pixels is cautioned
SHADE_MIN = 0.08                                          # a darker group under this share is not a shade tone


# ------------------------------------------------------------------------------------------------------------ colour
def srgb_to_lab(c):
    """sRGB 0..1 (..., 3) -> CIE L*a*b* (D65)."""
    c = np.asarray(c, float)
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750], [0.0193339, 0.1191920, 0.9503041]])
    xyz = lin @ M.T / np.array([0.95047, 1.0, 1.08883])
    d = 6 / 29
    f = np.where(xyz > d ** 3, np.cbrt(xyz), xyz / (3 * d * d) + 4 / 29)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def ciede2000(lab1, lab2):
    """the CIEDE2000 colour difference (Sharma, Wu and Dalal 2005), kL = kC = kH = 1."""
    L1, a1, b1 = (float(v) for v in lab1)
    L2, a2, b2 = (float(v) for v in lab2)
    Cb = (np.hypot(a1, b1) + np.hypot(a2, b2)) / 2
    G = 0.5 * (1 - np.sqrt(Cb ** 7 / (Cb ** 7 + 25.0 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360 if C1p else 0.0
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360 if C2p else 0.0
    dLp, dCp = L2 - L1, C2p - C1p
    dhp = 0.0
    if C1p * C2p:
        dhp = h2p - h1p
        dhp = dhp - 360 if dhp > 180 else dhp + 360 if dhp < -180 else dhp
    dHp = 2 * np.sqrt(C1p * C2p) * np.sin(np.radians(dhp / 2))
    Lbp, Cbp = (L1 + L2) / 2, (C1p + C2p) / 2
    if C1p * C2p == 0:
        hbp = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hbp = (h1p + h2p) / 2
    else:
        hbp = (h1p + h2p + 360) / 2 if h1p + h2p < 360 else (h1p + h2p - 360) / 2
    r = np.radians
    T = 1 - 0.17 * np.cos(r(hbp - 30)) + 0.24 * np.cos(r(2 * hbp)) + 0.32 * np.cos(r(3 * hbp + 6)) - 0.20 * np.cos(r(4 * hbp - 63))
    dth = 30 * np.exp(-((hbp - 275) / 25) ** 2)
    RC = 2 * np.sqrt(Cbp ** 7 / (Cbp ** 7 + 25.0 ** 7))
    SL = 1 + 0.015 * (Lbp - 50) ** 2 / np.sqrt(20 + (Lbp - 50) ** 2)
    SC, SH = 1 + 0.045 * Cbp, 1 + 0.015 * Cbp * T
    RT = -np.sin(r(2 * dth)) * RC
    return float(np.sqrt((dLp / SL) ** 2 + (dCp / SC) ** 2 + (dHp / SH) ** 2 + RT * (dCp / SC) * (dHp / SH)))


def _hex(c):
    return '#%02x%02x%02x' % tuple(int(round(v * 255)) for v in np.clip(c, 0, 1))


# ------------------------------------------------------------------------------------------------------------ tones
def tones(px, w=None):
    """a class's pixels (n, 3) sRGB (weights w, e.g. areas) -> dict(lit, shade (None: one tone), shade_share, px): split
    at the L* threshold with the largest between-group variance, each group's weighted median."""
    px = np.asarray(px, float)
    w = np.ones(len(px)) if w is None else np.asarray(w, float)
    if not len(px):
        return None
    L = srgb_to_lab(px)[:, 0]
    edges = np.linspace(L.min(), L.max(), 64)
    best, thr = -1.0, None
    for t in edges[1:-1]:
        lo = L < t
        w0, w1 = w[lo].sum(), w[~lo].sum()
        if w0 <= 0 or w1 <= 0:
            continue
        v = w0 * w1 * (np.average(L[lo], weights=w[lo]) - np.average(L[~lo], weights=w[~lo])) ** 2
        if v > best:
            best, thr = v, t
    out = {'px': int(len(px))}
    if thr is None:
        out.update(lit=_wmedian(px, w), shade=None, shade_share=0.0)
        return out
    lo = L < thr
    share = float(w[lo].sum() / w.sum())
    lit, shade = _wmedian(px[~lo], w[~lo]), _wmedian(px[lo], w[lo])
    if share < SHADE_MIN or srgb_to_lab(lit)[0] - srgb_to_lab(shade)[0] < 4:
        out.update(lit=_wmedian(px[L >= np.percentile(L, 30)], w[L >= np.percentile(L, 30)]), shade=None, shade_share=share)
    else:
        out.update(lit=lit, shade=shade, shade_share=round(share, 3))
    return out


def _wmedian(px, w):
    out = []
    for c in range(3):
        o = np.argsort(px[:, c])
        cw = np.cumsum(w[o])
        out.append(float(px[o, c][np.searchsorted(cw, cw[-1] / 2)]))
    return np.array(out)


def extract(pairs, names=CLASSES, inset=1, iris_band=None):
    """the design's tones per class from pictures and their class images: pairs [(rgb (H, W, 3), cls (H, W))] (lines
    kept as their own class), each class a pixel `inset` in from its edges; iris_band [(row0, row1, col0, col1)] per pair:
    where the eyes are (the iris class elsewhere is an ornament). -> {name: tones()}."""
    from .bodyqa import erode
    pool = {n: [] for n in names}
    for i, (rgb, cls) in enumerate(pairs):
        for n, c in names.items():
            m = erode(cls == c, inset) if inset and n != 'iris' else cls == c      # an iris is a few pixels: all of it
            if n == 'iris' and iris_band is not None:
                b = iris_band[i]
                if b is None:
                    continue
                band = np.zeros_like(m); band[b[0]:b[1], b[2]:b[3]] = True
                m &= band
            if m.any():
                pool[n].append(rgb[m])
    return {n: tones(np.concatenate(p)) for n, p in pool.items() if p}


def extract_views(design, eye_band=0.12, eye_reach=0.45):
    """extract() over bodyqa.design_views()'s figures (their pictures and line-kept class images), the iris only within
    eye_band L of the eye line and eye_reach L of the eyes across."""
    pairs, bands = [], []
    for v, dv in design.items():
        pairs.append((dv['rgb'], dv['raw']))
        p, w = dv['ppl'], dv['win']
        r, c = w['top'] * p, w['x'] * p
        bands.append((int(r - eye_band * p), int(r + eye_band * p), int(c - eye_reach * p), int(c + eye_reach * p))
                     if v != 'back' else None)
    return extract(pairs, iris_band=bands)


def ours(cols, names=CLASSES, painted=('iris',)):
    """our tones per class from charkit.qa3d.scene_classes' colours {class id: [(lit, shade, area)]}: the area-weighted
    median of the triangles' lit and shade colours; a painted class (the iris plate: its tones are in its texture, not
    its shading) is split into lit and shade as the design's is (tones()), over the texels the sheet's colour rule gives
    that class (charkit.bodyqa.family: the pupil and ring are line on the sheet). -> {name: dict(lit, shade, area)}."""
    out = {}
    for n, c in names.items():
        rows = cols.get(c) or cols.get(str(c))
        if not rows:
            continue
        lit = np.array([r[0] for r in rows], float); shd = np.array([r[1] for r in rows], float)
        w = np.maximum(np.array([r[2] for r in rows], float), 1e-12)
        if n in painted:
            from .bodyqa import family
            keep = family(lit) == c                   # the texels the sheet's own colour rule calls this class (its
            if keep.sum() >= 3:                       # pupil and ring are line there)
                lit, w = lit[keep], w[keep]
            T = tones(lit, w)
            out[n] = {'lit': T['lit'], 'shade': T['shade'], 'area': float(w.sum())}
        else:
            out[n] = {'lit': _wmedian(lit, w), 'shade': _wmedian(shd, w), 'area': float(w.sum())}
    return out


def compare(O, D):
    """dE00 per class and tone -> {name: check} ('<class>_lit', '<class>_shade')."""
    C = {}
    for n in CLASSES:
        if n not in O or n not in D or D[n] is None:
            continue
        for tone in ('lit', 'shade'):
            a, b = O[n].get(tone), D[n].get(tone)
            if a is None or b is None:
                if tone == 'shade' and b is None:
                    C['%s_%s' % (n, tone)] = {'status': 'SKIPPED', 'why': 'the design shows one tone'}
                continue
            la, lb = srgb_to_lab(a), srgb_to_lab(b)
            dE = ciede2000(la, lb)
            p, w_ = LIMITS[tone]
            chk = {'value': round(dE, 2), 'status': 'PASS' if dE <= p else 'WARN' if dE <= w_ else 'FAIL',
                   'ours': _hex(a), 'design': _hex(b), 'dL': round(float(la[0] - lb[0]), 2),
                   'dC': round(float(np.hypot(*la[1:]) - np.hypot(*lb[1:])), 2),
                   'dh': round(float((np.degrees(np.arctan2(la[2], la[1])) - np.degrees(np.arctan2(lb[2], lb[1])) + 180) % 360 - 180), 1)}
            if D[n]['px'] < MIN_PX:
                chk['caution'] = 'few design pixels (%d)' % D[n]['px']
            C['%s_%s' % (n, tone)] = chk
    return C


def picture(O, D, size=48):
    """per class a column: the design's lit tone over ours, then the design's shade over ours; a bar under each pair in
    its grade's colour (green pass, amber warn, red fail; grey: not compared)."""
    C = compare(O, D)
    cols = []
    for n in CLASSES:
        if n not in O and n not in D:
            continue
        blocks = []
        for tone in ('lit', 'shade'):
            for src in (D.get(n) or {}, O.get(n) or {}):
                c = src.get(tone)
                blocks.append(np.ones((size, size, 3)) * (np.asarray(c) if c is not None else 0.9))
            st = C.get('%s_%s' % (n, tone), {}).get('status')
            col = {'PASS': (0.2, 0.7, 0.3), 'WARN': (0.95, 0.65, 0.1), 'FAIL': (0.9, 0.2, 0.2)}.get(st, (0.75, 0.75, 0.75))
            blocks.append(np.ones((6, size, 3)) * np.array(col))
            blocks.append(np.ones((6, size, 3)))
        cols.append(np.concatenate(blocks, 0))
        cols.append(np.ones((cols[-1].shape[0], 6, 3)))
    return np.concatenate(cols[:-1], 1) if cols else np.ones((8, 8, 3))
