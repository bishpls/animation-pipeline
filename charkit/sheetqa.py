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

The sheet's figures are found from the picture (detect_figures): blobs off the paper; a figure is at least half as tall as
the tallest, its view from its eyes (a level pair centred in the head: front; off-centre: three-quarter; one: profile;
none under hair: back); a shorter blob in the hair's colour is an expression head; the rest (hand studies) is skipped.
Head boxes follow HEAD_BOX, the manifest's framing.

    from charkit import sheetqa
    F = sheetqa.detect_figures(rgb, ppl)                             # the figures, their head boxes, the expression heads
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
    from .target3d import hsv
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


def find_eyes(lab, box, n=2, facing=-1, max_tilt=None):
    """the iris blobs inside a head box (x0, y0, x1, y1) of a label image -> list of (x, y) pixel centroids, left to right
    (the two largest, grown a little so a pupil doesn't split one; blobs under a tenth of the largest are left out).
    max_tilt: a pair must lie within this slope (dy / dx) of level (a hair ornament beside one eye is not a pair)."""
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
            if not (0.1 * bw <= dx <= 0.6 * bw) or (max_tilt is not None and dy > max_tilt * dx):
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
        # how much skin shows down the midline under the chin (a drawn jaw line skipped) before anything else: the neck's
        # visible run (the neck check below reads one row of it, so a short run puts that row on the collar)
        if chin is not None:
            r0 = int(np.argmin(np.abs(z - chin))) + 1
            c0 = int(round(ex))
            col = (lab[:, c0] == 1) | (lab[:, c0] == 5) if 0 <= c0 < W else np.zeros(H, bool)
            k = r0
            while k < min(H, r0 + 5) and not col[k]:
                k += 1
            e = k
            while e < H and col[e]:
                e += 1
            out['neck_run'] = round((e - r0) / ppl, 4) if e > k else 0.0
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
        if O['front'].get('neck_run') is not None:
            C['neck_run'] = {'value': O['front']['neck_run'], 'design': D['front'].get('neck_run'), 'status': 'INFO',
                             'note': 'skin showing down the midline under the chin, L; neck_to_jaw reads its row at 0.06'}
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


def measure_ours(meshes, covers, irc, centre, L, ppl, az3, below=-0.2, zbuffer=None, face_region=None):
    """our face measured as the design's is (charkit/qa3d.py hands over the scene's arrays; charkit/faceeval.py its own):
    meshes [(V world, tris, class per triangle)]: the skin, eyes, mouth and clothes (not the hair); covers: the hair and
    what it carries, the same way (only for how much face shows); irc: the iris plates' centres (world); centre: the head
    centre (world x, y); L the head length; ppl: the sheet's pixels per head length; az3: the three-quarter azimuth.
    Each view is z-buffered at the sheet's scale (charkit.faceqa), the face is the skin reached from under the eyes
    without crossing a depth jump, and every view's face is cut at the chin (faceqa.drawn_chin, the design's rule: where
    the front edge turns back steeply to the neck, searched from `below` L under the eye line: under the nose), as a
    drawn jaw line cuts the design's.
    zbuffer, face_region: faceqa's by default, or drop-ins giving the same pixels (zbuffer takes faceqa.zbuffer's `thin`).
    -> {view: measure_labels(...) + 'shown'}."""
    import math
    from . import faceqa
    zbuffer = zbuffer or faceqa.zbuffer
    face_region = face_region or faceqa.face_region
    cx, cy = centre[0], centre[1]
    ez = float(np.mean([c[2] for c in irc]))
    pix = 1.0 / ppl
    win = faceqa.WIN
    O, raw = {}, {}
    for view, az in (('profile', 90.0), ('front', 0.0), ('three_quarter', az3)):
        a = math.radians(az)
        org = (cx * math.cos(a) + cy * math.sin(a), ez)
        # the face's shape without the hair (we know it underneath); how much of it the hair leaves showing apart
        depth, lab = zbuffer(meshes, az, org, L, pix, win, thin=(CLASS['line'],))
        lab = np.where(lab < 0, CLASS['other'], lab)
        face = face_region(depth, np.where(lab == CLASS['skin'], 1, 0), 0.035 * L, pix=pix)
        if covers:
            dv, lv = zbuffer(meshes + covers, az, org, L, pix, win, thin=(CLASS['line'],))
        else:
            lv = lab
        def px(P):
            u, z, _ = faceqa.view(np.asarray(P, float)[None], az)
            return (float(((u[0] - org[0]) / L + win['x']) / pix), float((win['top'] - (z[0] - org[1]) / L) / pix))
        eyes = sorted(px(c) for c in irc)
        if view == 'profile':
            eyes = [px(max(irc, key=lambda c: c[0]))]                  # the near eye from +x: the character's left
        raw[view] = (lab, face, eyes, depth, lv)
    # our chin: where the profile's front edge turns back steeply to the neck (the under-chin runs smoothly into the neck,
    # so the face region alone doesn't stop there), read with the design's own rule; every view's face is cut below it,
    # as a drawn jaw line cuts the design's
    lab, face, eyes, depth, lv = raw['profile']
    M = measure_labels(lab, face, 'profile', ppl, eyes)
    chin = faceqa.drawn_chin(M['lead'], M['z'], below)                # the design's rule (refcheck.measure_heads)
    for view, (lab, face, eyes, depth, lv) in raw.items():
        zr = (np.mean([e[1] for e in eyes]) - np.arange(face.shape[0])) / ppl
        if chin is not None:
            # the skin below the chin out first, then the fill again: the neck beside the chin can then only be reached
            # across the jaw's depth jump
            skin = (lab == CLASS['skin']) & (zr >= chin)[:, None]
            face = face_region(depth, skin.astype(int), 0.035 * L, pix=pix)
        shown = face & (lv == CLASS['skin'])
        O[view] = measure_labels(lab, face, view, ppl, eyes)
        O[view]['shown'] = round(float(shown.sum() / max(1, face.sum())), 3)
    return O


def shown(O, D):
    """how much of our lower face the hair leaves showing against the design's (drawn as it shows: all of it); warns
    only. -> {'shown_' + view: check}."""
    C = {}
    for view in ('front', 'three_quarter', 'profile'):
        if view in O and view in D:
            dsh = float((D[view]['face'] & (D[view]['z'][:, None] < -0.02)).sum())
            osh = float((O[view]['face'] & (O[view]['z'][:, None] < -0.02)).sum()) * O[view]['shown']
            r = round(osh / max(1.0, dsh), 3)
            C['shown_' + view] = {'value': r, 'status': 'PASS' if abs(r - 1) <= 0.2 else 'WARN',
                                  'note': 'our lower face left showing by the hair, against the design\'s (warns only)'}
    return C


def sheet_ppl(sheet_rgb, front_box, rig_alpha, rig_ppl):
    """the sheet's pixels per head length from its front figure's height against the design rig's (the same drawing at a
    known scale): far steadier than the sheet's few-pixel eye spacing."""
    return rig_ppl * figure_height(sheet_rgb, box=front_box) / figure_height(alpha=rig_alpha)


# ------------------------------------------------------------------------------------------------------ figure detection
def label(m):
    """4-connected components of a bool mask (row runs joined by a union-find; pure numpy and python, fast enough for a
    whole sheet) -> (labels (H, W) int, 0 = background, n)."""
    H, W = m.shape
    pad = np.zeros((H, W + 2), np.int8); pad[:, 1:-1] = m
    d = np.diff(pad, axis=1)
    rs, cs = np.nonzero(d == 1)
    _, ce = np.nonzero(d == -1)                              # row-major: starts and ends pair up
    n = len(rs)
    out = np.zeros((H, W), np.int32)
    if not n:
        return out, 0
    parent = np.arange(n)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    first = np.searchsorted(rs, np.arange(H + 1))
    for r in range(H - 1):
        i, i1, j, j1 = first[r], first[r + 1], first[r + 1], first[r + 2]
        while i < i1 and j < j1:
            if cs[i] < ce[j] and cs[j] < ce[i]:
                a, b = find(i), find(j)
                if a != b:
                    parent[max(a, b)] = min(a, b)
            if ce[i] < ce[j]:
                i += 1
            else:
                j += 1
    roots = np.array([find(i) for i in range(n)])
    _, ids = np.unique(roots, return_inverse=True)
    ids = ids + 1
    ln = ce - cs
    rows = np.repeat(rs, ln)
    cols = np.repeat(cs, ln) + (np.arange(ln.sum()) - np.repeat(np.cumsum(ln) - ln, ln))
    out[rows, cols] = np.repeat(ids, ln)
    return out, int(ids.max())


def boxes(lab, n):
    """per component 1..n: (x0, y0, x1, y1) (x1, y1 exclusive) and its area -> (n, 4) int array, (n,) areas."""
    ys, xs = np.nonzero(lab)
    k = lab[ys, xs] - 1
    B = np.zeros((n, 4), int)
    B[:, 0] = B[:, 1] = 1 << 30
    np.minimum.at(B[:, 0], k, xs); np.minimum.at(B[:, 1], k, ys)
    np.maximum.at(B[:, 2], k, xs + 1); np.maximum.at(B[:, 3], k, ys + 1)
    return B, np.bincount(k, minlength=n)


def background(rgb):
    """the sheet's paper colour: the median of its border."""
    b = np.concatenate([rgb[:4].reshape(-1, 3), rgb[-4:].reshape(-1, 3), rgb[:, :4].reshape(-1, 3), rgb[:, -4:].reshape(-1, 3)])
    return np.median(b, 0)


def foreground(rgb, bg=None, thr=0.12, paper=0.012):
    """what is drawn: pixels away from the paper colour, with the regions they enclose filled (white boots on white
    paper), except enclosed paper (the gap between an arm and the body: within `paper` of the paper colour)."""
    bg = background(rgb) if bg is None else bg
    fg = np.abs(rgb - bg).sum(-1) > thr
    holes, n = label(~fg)
    if n:
        B, area = boxes(holes, n)
        H, W = fg.shape
        edge = (B[:, 0] == 0) | (B[:, 1] == 0) | (B[:, 2] == W) | (B[:, 3] == H)
        ys, xs = np.nonzero(holes)
        k = holes[ys, xs] - 1
        mean = np.stack([np.bincount(k, rgb[ys, xs, c], n) for c in range(3)], 1) / np.maximum(area, 1)[:, None]
        fill = ~edge & (np.abs(mean - bg).max(1) > paper)
        fg = fg | fill[np.maximum(holes - 1, 0)] & (holes > 0)
    return fg


# the head box convention (the framing the manifest's hand-typed boxes use, reproduced within 2 px on Clawd's sheet): a
# square `size` L on a side, its top `above` L over the eye line; across, centred on the head's axis, `back` L toward the
# back of the head (the sheet's facing). The axis: the eyes' midpoint from the front; `axis` L behind the eyes in a turned
# view (a drawn 3/4 keeps its eyes as far forward as the profile does, whatever its eye spacing says); the silhouette's
# centre round the eye line from the back
HEAD_BOX = dict(size=1.74, above=0.77, back=0.04, axis=0.27, band=0.2)
FIGURE_MIN = 0.002                  # blobs under this share of the sheet are specks (a boot's shadow, a sweat drop)


def _row_centre(mask, y0, y1):
    """the median over rows y0..y1 of each row's silhouette centre (midway between its first and last pixel)."""
    c = []
    for r in range(max(0, y0), min(mask.shape[0], y1)):
        xs = np.nonzero(mask[r])[0]
        if len(xs):
            c.append((xs[0] + xs[-1]) / 2)
    return float(np.median(c)) if c else None


def head_box(mask, eye_y, ppl, facing=-1, eyes_x=None, turned=False):
    """a figure's head box [x0, y0, x1, y1] by HEAD_BOX from its silhouette mask, eye line, eyes' columns and scale."""
    K = HEAD_BOX
    if eyes_x:
        c = float(np.mean(eyes_x)) - (facing * K['axis'] * ppl if turned else 0.0)
    else:
        c = _row_centre(mask, int(eye_y - K['band'] * ppl), int(eye_y + K['band'] * ppl) + 1)
    c -= facing * K['back'] * ppl
    half = K['size'] * ppl / 2
    y0 = eye_y - K['above'] * ppl
    return [int(round(c - half)), int(round(y0)), int(round(c + half)), int(round(y0 + 2 * half))]


def detect_figures(rgb, ppl=None, eye_x=0.168, facing=None):
    """the figures on a model sheet, found from the picture: the full figures (front, three_quarter, profile, back: each
    with its box, its head box by HEAD_BOX, its eyes and eye line) and the expression heads (left to right), hand studies
    and specks left out. rgb (H, W, 3) floats; ppl: the sheet's pixels per head length when known (sheet_ppl), else from
    the front figure's eye spacing (2 * eye_x L; +-4% on a small sheet); facing: the side views' direction, else found.

    A blob is a full figure when it is at least half as tall as the tallest; a head when it carries the hair's colour; else
    it is skipped (hands). Views: two eyes (a level pair) and a silhouette centred on them = front, off-centre =
    three_quarter; one eye = profile (facing the side its eye is on); none, mostly hair on top = back.
    -> dict(size, bg, ppl, scale, facing, figures {view: {...}}, expressions [...], skipped [...], _fg, _blobs)."""
    H, W, _ = rgb.shape
    bg = background(rgb)
    fg = foreground(rgb, bg)
    blobs, n = label(fg)
    B, area = boxes(blobs, n)
    lab = classes(rgb)
    keep = [i for i in range(n) if area[i] >= FIGURE_MIN * H * W]
    tall = max(B[i, 3] - B[i, 1] for i in keep)
    lowest = max(B[i, 3] for i in keep if B[i, 3] - B[i, 1] >= 0.5 * tall)
    figs, heads, skipped = [], [], []
    for i in keep:
        x0, y0, x1, y1 = (int(v) for v in B[i])
        m = blobs == i + 1
        info = dict(box=[x0, y0, x1, y1], _mask=m, area=int(area[i]))
        if y1 - y0 >= 0.5 * tall:
            band = (x0, y0, x1, int(y0 + 0.4 * tall))                   # the head: eyes in its upper part
            e2 = find_eyes(lab, band, 2, max_tilt=0.25)
            e1 = find_eyes(lab, band, 1) if not e2 else []
            hair = float(((lab == 2) & m)[y0:int(y0 + 0.25 * tall)].sum() / max(1, m[y0:int(y0 + 0.25 * tall)].sum()))
            info.update(eyes=e2 or e1, hair_share=round(hair, 3))
            figs.append(info)
        else:
            sub = m[y0:y1, x0:x1]
            hair = float((lab[y0:y1, x0:x1][sub] == 2).mean())
            if hair < 0.15:
                skipped.append(dict(box=[x0, y0, x1, y1], why='no hair (%.2f of it): a hand study or a prop' % hair))
                continue
            info.update(eyes=find_eyes(lab, (x0, y0, x1, y1), 2, max_tilt=0.25), hair_share=round(hair, 3))
            heads.append(info)
    # the scale: given, or the front figure's eye spacing (the most symmetric two-eyed figure)
    two = [f for f in figs if len(f['eyes']) == 2]
    for f in two:
        ex = [e[0] for e in f['eyes']]
        ey = float(np.mean([e[1] for e in f['eyes']]))
        c = _row_centre(f['_mask'], int(ey - 20), int(ey + 21))
        f['_off'] = (c - np.mean(ex)) / max(1.0, abs(ex[1] - ex[0]))     # silhouette centre off the eyes, in eye spacings
    front = min(two, key=lambda f: abs(f['_off'])) if two else None
    scale = 'given'
    if ppl is None:
        if front is None:
            raise RuntimeError('no two-eyed figure to scale the sheet by: pass ppl')
        ppl = abs(front['eyes'][1][0] - front['eyes'][0][0]) / (2 * eye_x)
        scale = 'eyes'
    # views
    out = dict(size=[W, H], bg=[round(float(v), 4) for v in bg], ppl=round(float(ppl), 2), scale=scale, figures={},
               expressions=[], skipped=skipped, _fg=fg, _blobs=blobs, _lab=lab)
    named = []
    for f in figs:
        e = f['eyes']
        if len(e) == 2:
            view = 'front' if f is front and abs(f['_off']) < 0.5 else 'three_quarter'
        elif len(e) == 1:
            view = 'profile'
        elif f['hair_share'] > 0.5:
            view = 'back'
        else:
            skipped.append(dict(box=f['box'], why='a full figure with no eyes and little hair on top'))
            continue
        named.append((view, f))
    fy = front and float(np.mean([e[1] for e in front['eyes']])) - front['box'][1]    # the eye line under the figure's top
    side = [f for v, f in named if v in ('profile', 'three_quarter')]
    if facing is None:                                                  # the side views' eyes lie toward their face
        votes = [np.sign(np.mean([e[0] for e in f['eyes']]) - _row_centre(f['_mask'], int(f['eyes'][0][1] - 20),
                                                                          int(f['eyes'][0][1] + 21))) for f in side]
        facing = int(np.sign(np.sum(votes))) or -1
    out['facing'] = facing
    for view, f in sorted(named, key=lambda t: t[1]['box'][0]):
        name = view if view not in out['figures'] else '%s_%d' % (view, sum(k.startswith(view) for k in out['figures']) + 1)
        e = f['eyes']
        if e:
            eye_y = float(np.mean([p[1] for p in e]))
        else:
            eye_y = f['box'][1] + (fy if fy is not None else 0.16 * (f['box'][3] - f['box'][1]))
        rec = dict(box=f['box'], head=head_box(f['_mask'], eye_y, ppl, facing, [p[0] for p in e], view != 'front'),
                   eyes=[[round(a, 2), round(b, 2)] for a, b in e], eye_y=round(eye_y, 2),
                   partial=bool(f['box'][3] < lowest - 0.1 * tall),
                   bottom_L=round((f['box'][3] - eye_y) / ppl, 3), _mask=f['_mask'])
        if view == 'back':
            rec['axis_x'] = round(_row_centre(f['_mask'], int(eye_y - 20), int(eye_y + 21)), 2)
        out['figures'][name] = rec
    # the expression heads, left to right: eye line from open eyes, else where the open-eyed heads have it
    rel = [(float(np.mean([e[1] for e in h['eyes']])) - h['box'][1]) / (h['box'][3] - h['box'][1]) for h in heads if h['eyes']]
    rel = float(np.median(rel)) if rel else 0.58
    fw = None
    if front is not None:                                               # the front figure's head width at its eyes
        ey = float(np.mean([e[1] for e in front['eyes']]))
        fw = _band_width(front['_mask'], ey, ppl)
    for h in sorted(heads, key=lambda h: h['box'][0]):
        x0, y0, x1, y1 = h['box']
        e = h['eyes']
        eye_y = float(np.mean([p[1] for p in e])) if e else y0 + rel * (y1 - y0)
        axis = _row_centre(h['_mask'], int(eye_y - 0.2 * ppl), int(eye_y + 0.2 * ppl) + 1)
        hw = _band_width(h['_mask'], eye_y, ppl)
        hp = ppl * hw / fw if fw else ppl                                # drawn at its own scale: by its head's width
        rec = dict(box=h['box'], eyes=[[round(a, 2), round(b, 2)] for a, b in e], eye_y=round(eye_y, 2),
                   eye_y_from=('eyes' if e else 'heads'), axis_x=round(axis, 2), ppl=round(hp, 2), _mask=h['_mask'])
        if len(e) == 2:
            rec['ppl_eyes'] = round(abs(e[1][0] - e[0][0]) / (2 * eye_x), 2)
        rec['head'] = head_box(h['_mask'], eye_y, hp, facing, [p[0] for p in e] or [axis])
        out['expressions'].append(rec)
    return out


def _band_width(mask, eye_y, ppl, band=0.2):
    """a head's silhouette width round its eye line: the median row width over +-band L."""
    w = []
    for r in range(int(eye_y - band * ppl), int(eye_y + band * ppl) + 1):
        xs = np.nonzero(mask[r])[0] if 0 <= r < mask.shape[0] else []
        if len(xs):
            w.append(xs[-1] - xs[0] + 1)
    return float(np.median(w)) if w else None


def manifest_figures(D, pad=8):
    """a detect_figures result as a manifest's `figures` (references.sheet.figures): the front figure's region (its box
    padded, so its border is paper), the head boxes of the front, three-quarter and profile views, the facing; plus the
    back's and the expression heads' boxes."""
    W, H = D['size']
    F = D['figures']
    fb = F['front']['box']
    out = {'front_figure': [max(0, fb[0] - pad), max(0, fb[1] - pad), min(W, fb[2] + pad), min(H, fb[3] + pad)],
           'heads': {v: F[v]['head'] for v in ('front', 'three_quarter', 'profile') if v in F},
           'facing': D['facing']}
    extra = {v: {'box': F[v]['box'], 'head': F[v]['head']} for v in F}
    out['figures'] = extra
    out['expressions'] = [{'box': e['box'], 'head': e['head']} for e in D['expressions']]
    return out


def verify_figures(D, figures, tol=5):
    """detected head boxes against a manifest's (hand-typed) ones -> {view: {'detected', 'typed', 'off' (max |px|), 'ok'}}."""
    out = {}
    for v, typed in (figures.get('heads') or {}).items():
        det = D['figures'].get(v, {}).get('head')
        if det is None:
            out[v] = {'typed': typed, 'detected': None, 'ok': False}
            continue
        off = int(max(abs(a - b) for a, b in zip(det, typed)))
        out[v] = {'typed': list(typed), 'detected': det, 'off': off, 'ok': off <= tol}
    return out


def figures_picture(rgb, D):
    """the sheet with what detect_figures found: figure boxes blue, head boxes green, expression heads orange, skipped
    blobs grey, eyes red (row 0 = top)."""
    im = rgb.copy() * 0.85 + 0.15

    def rect(b, c, t=2):
        x0, y0, x1, y1 = (int(v) for v in b)
        H, W = im.shape[:2]
        x0, x1, y0, y1 = max(0, x0), min(W - 1, x1), max(0, y0), min(H - 1, y1)
        im[y0:y0 + t, x0:x1] = c; im[y1 - t + 1:y1 + 1, x0:x1] = c
        im[y0:y1, x0:x0 + t] = c; im[y0:y1, x1 - t + 1:x1 + 1] = c
    for v, f in D['figures'].items():
        rect(f['box'], (0.15, 0.3, 0.95)); rect(f['head'], (0.1, 0.7, 0.2))
        for x, y in f['eyes']:
            im[int(y) - 2:int(y) + 3, int(x) - 2:int(x) + 3] = (0.95, 0.1, 0.1)
        im[int(f['eye_y']), f['box'][0]:f['box'][2]:3] = (0.95, 0.1, 0.1)
    for e in D['expressions']:
        rect(e['box'], (0.95, 0.55, 0.1)); rect(e['head'], (0.1, 0.7, 0.2), 1)
        for x, y in e['eyes']:
            im[int(y) - 2:int(y) + 3, int(x) - 2:int(x) + 3] = (0.95, 0.1, 0.1)
        im[int(e['eye_y']), e['box'][0]:e['box'][2]:3] = (0.95, 0.1, 0.1)
    for s in D['skipped']:
        rect(s['box'], (0.5, 0.5, 0.5))
    return np.clip(im, 0, 1)
