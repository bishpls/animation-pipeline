"""Model-sheet QA: our face against the design's model sheet (front, three-quarter, profile), both measured the same way
from pictures (pure numpy; the Blender side renders ours in flat class colours).

The sheet is scaled by its front figure's eye spacing (the kit's convention: eye centres 2 * eye_x * L apart) and each
view is aligned on its eyes. A model sheet is drawn at one scale, so the front's scale holds for the other figures. The
three-quarter view's angle comes from how much the eye spacing shortens (cos az). Colour says what each pixel is:

  skin   pale warm        hair   saturated orange (the character's hair hue)        iris   yellow        line   dark

In the drawing the face is the skin reached from under the eyes with the drawn lines as walls (the jaw line bounds it).
Ours comes from a z-buffer of the scene (charkit.faceqa) at the sheet's scale, each triangle labelled by class, and the
face is bounded where the depth jumps (the jaw's silhouette over the neck: what a drawn jaw line is).

Measured (head lengths L, from the eye line; x toward the face's front):

  front          the face's half-width at 55%, 75% and 90% of the way from the eye line to its own chin (the length is
                 the chin check's; 90% is reported, not graded), the chin's height, and the neck's half-width just
                 under the chin against the face's at 75% (a jaw line: the jaw clearly wider than the neck)
  profile        the face's front edge per row from the eye line to the chin; the nose's and the chin's reach in front
                 of the eye; the chin's height (the face's lowest row on its leading side)
  three_quarter  the leading (far-cheek) contour per row, and the chin's height

    from charkit import sheetqa
    D = sheetqa.measure_sheet(rgb, figures, eye_x)                   # the design
    O = sheetqa.measure_labels(lab, face, view, ppl, eyes)           # ours: a z-buffer's classes and its face (qa3d)
    C = sheetqa.compare(O, D)
"""
import numpy as np


SKIN = dict(h=(8.0, 42.0), s=(0.08, 0.40), v=0.80)
HAIR = dict(h=(0.0, 30.0), s=0.42, v=0.30)
IRIS = dict(h=(38.0, 66.0), s=0.35, v=0.55)
LINE_V = 0.38
CLASS = {'other': 0, 'skin': 1, 'hair': 2, 'iris': 3, 'line': 4, 'skin_shade': 5}
LIMITS = {'width': (0.08, 0.15), 'profile': (0.02, 0.04), 'reach': (0.02, 0.04), 'chin': (0.02, 0.04), 'cheek': (0.02, 0.04)}


def classes(rgb):
    """-> label image: 0 other, 1 skin, 2 hair, 3 iris, 4 line, 5 shaded skin (a drawn neck under the chin)."""
    from .i3d import hsv
    H, W, _ = rgb.shape
    h, s, v = (a.reshape(H, W) for a in hsv(rgb.reshape(-1, 3)))
    lab = np.zeros((H, W), int)
    lab[(h >= SKIN['h'][0]) & (h <= SKIN['h'][1]) & (s >= SKIN['s'][0]) & (s <= SKIN['s'][1]) & (v >= SKIN['v'])] = 1
    lab[(h >= HAIR['h'][0]) & (h <= HAIR['h'][1]) & (s > HAIR['s']) & (v > HAIR['v'])] = 2
    lab[(h >= SKIN['h'][0]) & (h <= SKIN['h'][1]) & (s >= SKIN['s'][0]) & (s <= 0.5) & (v >= 0.5) & (v < SKIN['v'])] = 5
    lab[(h > IRIS['h'][0]) & (h < IRIS['h'][1]) & (s > IRIS['s']) & (v > IRIS['v'])] = 3
    lab[v < LINE_V] = 4
    return lab


def _components(m):
    """4-connected components -> list of (count, rows, cols), largest first."""
    H, W = m.shape
    seen = np.zeros_like(m, bool)
    out = []
    for r0, c0 in zip(*np.nonzero(m)):
        if seen[r0, c0]:
            continue
        st = [(r0, c0)]; seen[r0, c0] = True; pts = []
        while st:
            r, c = st.pop(); pts.append((r, c))
            for rr, cc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                if 0 <= rr < H and 0 <= cc < W and m[rr, cc] and not seen[rr, cc]:
                    seen[rr, cc] = True; st.append((rr, cc))
        a = np.array(pts)
        out.append((len(pts), a[:, 0], a[:, 1]))
    return sorted(out, key=lambda t: -t[0])


def find_eyes(lab, box, n=2, facing=-1):
    """the iris blobs inside a head box (x0, y0, x1, y1) of a label image -> list of (x, y) pixel centroids, left to right
    (the two largest, grown a little so a pupil doesn't split one; blobs under a tenth of the largest are left out)."""
    x0, y0, x1, y1 = box
    y1 = y0 + int(0.62 * (y1 - y0))                          # eyes sit in the head box's upper part (not the collar)
    m = lab[y0:y1, x0:x1] == 3
    grow = max(2, int(0.015 * (x1 - x0)))                    # bridge the pupil that splits an iris in two
    for _ in range(grow):
        m = m | np.roll(m, 1, 0) | np.roll(m, -1, 0) | np.roll(m, 1, 1) | np.roll(m, -1, 1)
    comps = [c for c in _components(m) if c[0] >= 12]
    if not comps:
        return []
    cents = [(float(c[2].mean() + x0), float(c[1].mean() + y0), c[0]) for c in comps[:8]]
    if n == 1:                                               # profile: the blob nearest the face's front
        return [min(cents, key=lambda e: e[0] * -facing)[:2]]
    # a pair: level with each other, a plausible distance apart, similar in size (a hair clip is none of these)
    bw = x1 - x0
    best, score = None, np.inf
    for i in range(len(cents)):
        for j in range(i + 1, len(cents)):
            a, b = cents[i], cents[j]
            dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
            if not (0.1 * bw <= dx <= 0.6 * bw):
                continue
            sc = dy / dx + abs(np.log(a[2] / b[2]))
            if sc < score:
                best, score = (a, b), sc
    return sorted([e[:2] for e in best]) if best else []


def face_region(lab, eye, ppl):
    """the face's skin: the skin component reached from under the eye (0.12 L below it), lines as walls."""
    H, W = lab.shape
    x, y = int(round(eye[0])), int(round(eye[1] + 0.12 * ppl))
    skin = lab == 1
    # the nearest skin pixel to the seed
    ys, xs = np.nonzero(skin[max(0, y - 10):y + 10, max(0, x - 10):x + 10])
    if not len(ys):
        return np.zeros_like(skin)
    k = int(np.argmin((ys - 10) ** 2 + (xs - 10) ** 2))
    r0, c0 = ys[k] + max(0, y - 10), xs[k] + max(0, x - 10)
    out = np.zeros_like(skin); out[r0, c0] = True; st = [(r0, c0)]
    while st:
        r, c = st.pop()
        for rr, cc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
            if 0 <= rr < H and 0 <= cc < W and skin[rr, cc] and not out[rr, cc]:
                out[rr, cc] = True; st.append((rr, cc))
    return out


def measure_figure(rgb, view, ppl, eyes, facing=-1):
    """one view of a face in a drawing: rgb (H, W, 3) floats; eyes: [(x, y)] pixel centres (one in profile); facing: the
    image direction the face points (-1 = left). The face is the skin reached from under the eyes, the drawn lines as
    walls. -> dict of curves and measures in L from the eye line."""
    lab = classes(rgb)
    near = min(eyes, key=lambda e: e[0] * -facing) if view != 'front' else eyes[0]
    face = face_region(lab, near, ppl)
    if view == 'front' and len(eyes) > 1:
        face |= face_region(lab, eyes[1], ppl)
    return measure_labels(lab, face, view, ppl, eyes, facing)


def measure_labels(lab, face, view, ppl, eyes, facing=-1):
    """the measures of a face mask in a class image (either a drawing's or a z-buffer of ours) -> dict (see
    measure_figure)."""
    ex = float(np.mean([e[0] for e in eyes])); ey = float(np.mean([e[1] for e in eyes]))
    near = min(eyes, key=lambda e: e[0] * -facing) if view != 'front' else (ex, ey)
    H, W = lab.shape
    rows = np.arange(H)
    z = (ey - rows) / ppl                                            # L up from the eye line
    out = {'view': view, 'z': z, 'face': face, 'lab': lab, 'ppl': ppl, 'eye_x': ex if view == 'front' else near[0]}
    if view == 'front':
        left, right = np.full(H, np.nan), np.full(H, np.nan)
        for r in np.nonzero(face.any(1))[0]:
            c = np.nonzero(face[r])[0]
            left[r], right[r] = (ex - c[0]) / ppl, (c[-1] - ex) / ppl
        out['half_left'], out['half_right'] = left, right
        mid = np.abs(np.arange(W) - ex) <= 0.05 * ppl
        rr = np.nonzero(face[:, mid].any(1))[0]
        chin = round(float(z[rr.max()]), 4) if len(rr) else None
        out['chin'] = chin
        # half-widths at fractions of the face's own eye-to-chin height (the chin check covers the length; above half
        # way the ears and the hair confound the contour)
        m = {}
        if chin is not None:
            for k, d in (('d55', 0.55), ('d75', 0.75), ('d90', 0.90)):
                sel = np.abs(z - d * chin) <= 0.012
                vals = [np.nanmean(a[sel]) for a in (left, right) if np.isfinite(a[sel]).any()]
                m[k] = round(float(max(vals)), 4) if vals else None
        out['widths'] = m
        # the neck just under the chin: the skin connected to the midline 0.06 L below the chin, its half-width (a drawn
        # jaw sits clearly wider than the neck; a face that runs into the neck with no jaw line doesn't)
        if chin is not None:
            r = int(round(ey - (chin - 0.06) * ppl))
            if 0 <= r < H:
                row = (lab[r] == 1) | (lab[r] == 5)
                c0 = int(round(ex))
                if 0 <= c0 < W and row[c0]:
                    lft, rgt = c0, c0
                    while lft > 0 and row[lft - 1]:
                        lft -= 1
                    while rgt < W - 1 and row[rgt + 1]:
                        rgt += 1
                    out['neck'] = round((rgt - lft + 1) / 2 / ppl, 4)
        return out
    # the leading contour: the face's front-most pixel per row, measured forward from the eye
    lead = np.full(H, np.nan)
    for r in np.nonzero(face.any(1))[0]:
        c = np.nonzero(face[r])[0]
        edge = c[0] if facing < 0 else c[-1]
        lead[r] = ((near[0] - edge) if facing < 0 else (edge - near[0])) / ppl
    out['lead'] = lead
    # the chin: the face's lowest row on its leading side (the drawn jaw line, or on a render the line where the skin
    # turns under, bounds the face)
    lead_cols = np.nonzero(face.any(0))[0]
    chin = None
    if len(lead_cols):
        span = lead_cols.max() - lead_cols.min()
        side = (np.arange(W) <= lead_cols.min() + 0.4 * span) if facing < 0 else (np.arange(W) >= lead_cols.max() - 0.4 * span)
        rr = np.nonzero(face[:, side].any(1))[0]
        chin = round(float(z[rr.max()]), 4) if len(rr) else None
    out['chin'] = chin
    below = (z < -0.02) & (z > -0.2)
    out['nose_reach'] = round(float(np.nanmax(lead[below])), 4) if np.isfinite(lead[below]).any() else None
    if chin is not None:
        cz = (z <= chin + 0.08) & (z >= chin)
        out['chin_reach'] = round(float(np.nanmax(lead[cz])), 4) if np.isfinite(lead[cz]).any() else None
    return out


def figure_height(rgb=None, alpha=None, box=None):
    """a figure's height in pixels: its alpha, or its difference from the background (the box's border colour)."""
    if alpha is not None:
        fg = alpha > 0.5
    else:
        x0, y0, x1, y1 = box
        im = rgb[y0:y1, x0:x1]
        bg = np.median(np.concatenate([im[:4].reshape(-1, 3), im[-4:].reshape(-1, 3), im[:, :4].reshape(-1, 3)]), 0)
        fg = np.abs(im - bg).sum(-1) > 0.12
    rows = np.nonzero(fg.sum(1) > 2)[0]
    return int(rows.max() - rows.min() + 1)


def measure_sheet(rgb, figures, eye_x, facing=-1, ppl=None):
    """the design's model sheet: figures {view: (x0, y0, x1, y1) head boxes}; eye_x: the kit's eye centre offset in L;
    ppl: pixels per head length when known better than from the small front eyes (sheet_ppl()).
    -> {view: measures}, with 'ppl', 'ppl_eyes' and the three-quarter view's estimated azimuth."""
    lab = classes(rgb)
    fe = find_eyes(lab, figures['front'])
    if len(fe) < 2:
        raise RuntimeError('the front figure needs two eyes, found %d' % len(fe))
    ppl_eyes = abs(fe[1][0] - fe[0][0]) / (2 * eye_x)
    ppl = ppl or ppl_eyes
    D = {'ppl': ppl, 'ppl_eyes': round(ppl_eyes, 2), 'front': measure_figure(rgb, 'front', ppl, fe, facing)}
    if 'three_quarter' in figures:
        te = find_eyes(lab, figures['three_quarter'])
        if len(te) == 2:
            D['az_three_quarter'] = round(float(np.degrees(np.arccos(np.clip(abs(te[1][0] - te[0][0]) / (2 * eye_x * ppl), 0, 1)))), 1)
            D['three_quarter'] = measure_figure(rgb, 'three_quarter', ppl, te, facing)
    if 'profile' in figures:
        pe = find_eyes(lab, figures['profile'], n=1, facing=facing)
        if pe:
            D['profile'] = measure_figure(rgb, 'profile', ppl, pe[:1], facing)
    return D


def _curve_gap(a, b, za, zb, lo, hi, step=0.01):
    """mean |a - b| over heights lo..hi (L), both curves sampled on a common grid."""
    g = np.arange(hi, lo, -step)
    def at(c, z):
        ok = np.isfinite(c)
        if ok.sum() < 3:
            return np.full(len(g), np.nan)
        o = np.argsort(z[ok])
        return np.interp(g, z[ok][o], c[ok][o], left=np.nan, right=np.nan)
    d = at(a, za) - at(b, zb)
    d = d[np.isfinite(d)]
    return (round(float(np.mean(np.abs(d))), 4), round(float(np.mean(d)), 4), int(len(d))) if len(d) else (None, None, 0)


def compare(O, D):
    """ours against the design, per view -> {name: check} (status PASS / WARN / FAIL against LIMITS)."""
    def grade(k, v):
        p, w = LIMITS[k]
        return 'PASS' if v <= p else 'WARN' if v <= w else 'FAIL'
    C = {}
    if 'front' in O and 'front' in D:
        wo, wd = O['front']['widths'], D['front']['widths']
        rat = {k: round(wo[k] / wd[k], 3) for k in wd if wo.get(k) and wd.get(k)}
        graded = {k: v for k, v in rat.items() if k != 'd90'}          # at 90% a face with no jaw line is the neck's width
        if graded:
            worst = max(graded.values(), key=lambda r: abs(r - 1))
            C['width'] = {'value': worst, 'status': grade('width', abs(worst - 1)), 'ratios': rat, 'ours': wo, 'design': wd}
        no, nd = O['front'].get('neck'), D['front'].get('neck')
        if no and nd and wo.get('d75') and wd.get('d75'):
            ro, rd = no / wo['d75'], nd / wd['d75']
            C['neck_to_jaw'] = {'value': round(ro / rd, 3), 'ours': round(ro, 3), 'design': round(rd, 3),
                                'status': grade('width', abs(ro / rd - 1)),
                                'note': "the neck's half-width under the chin over the face's at 75%: near 1 = no jaw line"}
    for view, key in (('profile', 'profile'), ('three_quarter', 'cheek')):
        if view not in O or view not in D:
            continue
        o, d = O[view], D[view]
        lo = max(v for v in (o.get('chin'), d.get('chin'), -0.5) if v is not None)
        gap, mean, n = _curve_gap(o['lead'], d['lead'], o['z'], d['z'], lo, -0.03)
        if gap is not None:
            C[key] = {'value': gap, 'mean': mean, 'rows': n, 'status': grade(key, gap), 'note': '+ mean = ours reaches further forward'}
        if o.get('chin') is not None and d.get('chin') is not None:
            dz = round(o['chin'] - d['chin'], 4)
            C[key + '_chin'] = {'value': dz, 'ours': o['chin'], 'design': d['chin'], 'status': grade('chin', abs(dz))}
        if view == 'profile':
            for k in ('nose_reach', 'chin_reach'):
                if o.get(k) is not None and d.get(k) is not None:
                    dv = round(o[k] - d[k], 4)
                    C[k] = {'value': dv, 'ours': o[k], 'design': d[k], 'status': grade('reach', abs(dv))}
    return C


def picture(O, D, scale=2):
    """per view, the design's and our face regions overlaid on a common grid round the eye line (grey both, red ours
    only, blue the design only) with the leading contours."""
    tiles = []
    for view in ('front', 'three_quarter', 'profile'):
        if view not in O or view not in D:
            continue
        g = 0.005
        zs = np.arange(0.35, -0.6, -g); xs = np.arange(-0.55, 0.55, g)
        im = np.full((len(zs), len(xs), 3), 0.95)
        masks = []
        for M in (O[view], D[view]):
            f, z = M['face'], M['z']
            rows = np.clip(np.searchsorted(-z, -zs), 0, len(z) - 1)
            ccols = np.clip((xs * M['ppl'] + M['eye_x']).astype(int), 0, f.shape[1] - 1)
            inside = (xs * M['ppl'] + M['eye_x'] >= 0) & (xs * M['ppl'] + M['eye_x'] < f.shape[1])
            masks.append(f[rows][:, ccols] & inside[None, :] & ((-zs >= -z[0]) & (-zs <= -z[-1]))[:, None])
        mo, md = masks
        im[mo & md] = (0.55, 0.55, 0.6); im[mo & ~md] = (0.9, 0.2, 0.2); im[md & ~mo] = (0.2, 0.35, 0.95)
        tiles += [im, np.ones((len(zs), 4, 3))]
    if not tiles:
        return np.ones((10, 10, 3))
    im = np.concatenate(tiles[:-1], 1)
    return np.repeat(np.repeat(im, scale, 0), scale, 1)


def sheet_ppl(sheet_rgb, front_box, rig_alpha, rig_ppl):
    """the sheet's pixels per head length from its front figure's height against the design rig's (the same drawing at a
    known scale): far steadier than the sheet's few-pixel eye spacing."""
    return rig_ppl * figure_height(sheet_rgb, box=front_box) / figure_height(alpha=rig_alpha)
