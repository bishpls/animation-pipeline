"""Eye QA: our eyes against the design's, both measured the same way from a picture (pure numpy).

The design's eyes come from its 2D rig (the eye layers are drawn whole, under the hair); ours from an orthographic render
of the eye alone, head-on, at the rig's scale (pixels per head length). Colour says which pixel is what:

  sclera     white or cool grey           iris       amber-to-yellow (the character's iris hue), the ring and glow included
  pupil      dark inside the iris         highlight  bright inside the iris          line   dark outside the iris (lids)

Measured, in head lengths L and as ratios:

  opening    the visible eyeball (sclera + iris): width, height, aspect (height / width)
  iris       its extent (width, height); how much of the opening's height it fills; its centre in the opening
  pupil      height against the iris's (how far it runs), aspect (width / height: a slit is thin), share of the iris
  highlight  the largest highlight's share of the iris and where it sits (in iris radii from its centre)
  lid        the upper lid line's thickness above the opening's middle, and the mean gap (skin) between it and the
             opening's top edge across the middle 80% of the opening; its span against the opening's width
  tilt       the corner line's angle (degrees, the picture's right corner up), from the opening's end columns

    from charkit import eyeqa
    M = eyeqa.measure(rgba, ppl)             # rgba (H, W, 4) floats 0..1, ppl: pixels per head length
    C = eyeqa.compare(ours, design)          # graded checks

Per view (front, three-quarter, profile; `nasal` is the picture direction of the nose from the eye, -1 left, +1 right),
measured the same way on the design's eye and ours from the same azimuth (views(), a QA part: eye_view_*):

  gaze       front_gap: the sclera between the iris's nasal edge and the opening's, over the iris's middle rows, as a
             share of the opening's width (a forward-looking eye in profile: 0); gaze_off: the visible iris's centroid
             across the opening (+ toward the nose, in opening widths); behind: the sclera's share on the far side of
             the iris (1: all of it behind)
  pupil      from a coverage map (each pixel's darkness between the iris round it and the pupil's core: sub-pixel, a
             6 px pupil measures to a tenth of a pixel): its height; its width at 25/50/75% of its height over the
             iris's width at the same rows (a slit is thin and even, an ellipse widest at 50%, a lens pointed); its area
             over the visible iris's; the second-moment ellipse (axis ratio minor / major, tilt from vertical in degrees,
             fill: area over the moment ellipse's, 1 for an ellipse); its centroid in the iris (+ nasal, + up, in iris
             half-widths / half-heights); its width at 50% over the opening's width
  edge       the opening's nasal edge over the middle 80% of its height: its angle from vertical (+ the top toward the
             nose), its straightness (rms off a line, in opening heights)
  flick      the upper lash line's far tip against the opening's far corner: out (past the corner, in opening widths),
             up (above it, in opening heights) and its angle (degrees above the horizontal)
"""
import numpy as np

IRIS_HUE = (28.0, 65.0)                          # degrees; the design's amber (a character's iris hue range)
LIMITS = {                                       # |ours / design - 1|: (pass within, warn within); else fail
    'aspect': (0.10, 0.20), 'width': (0.08, 0.15), 'iris_fill': (0.10, 0.20),
    'pupil_run': (0.15, 0.30), 'pupil_aspect': (0.20, 0.40), 'iris_ratio': (0.10, 0.20), 'lid_span': (0.10, 0.20),
}
LID_GAP = (0.004, 0.010)                         # L between the upper lid line and the opening: (pass, warn)


def _hsv(rgb):
    from .target3d import hsv
    h, s, v = hsv(rgb.reshape(-1, 3))
    return h.reshape(rgb.shape[:2]), s.reshape(rgb.shape[:2]), v.reshape(rgb.shape[:2])


def _row_fill(m):
    """fill each row between its first and last set pixel (the iris and the opening are convex along rows)."""
    out = np.zeros_like(m)
    for r in np.nonzero(m.any(1))[0]:
        c = np.nonzero(m[r])[0]
        out[r, c[0]:c[-1] + 1] = True
    return out


def _largest(m):
    """the largest 4-connected component of a mask."""
    H, W = m.shape
    lab = np.zeros(m.shape, int)
    best, best_n, k = None, 0, 0
    for r0, c0 in zip(*np.nonzero(m)):
        if lab[r0, c0]:
            continue
        k += 1
        stack, pts = [(r0, c0)], []
        lab[r0, c0] = k
        while stack:
            r, c = stack.pop(); pts.append((r, c))
            for rr, cc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                if 0 <= rr < H and 0 <= cc < W and m[rr, cc] and not lab[rr, cc]:
                    lab[rr, cc] = k; stack.append((rr, cc))
        if len(pts) > best_n:
            best, best_n = pts, len(pts)
    out = np.zeros_like(m)
    if best:
        rr, cc = np.array(best).T
        out[rr, cc] = True
    return out


def _box(m):
    ys, xs = np.nonzero(m)
    return (xs.min(), xs.max(), ys.min(), ys.max()) if len(xs) else None


def _grow(m, through, steps):
    """grow a mask by 4-neighbour steps, only into `through` pixels."""
    for _ in range(steps):
        g = m | np.roll(m, 1, 0) | np.roll(m, -1, 0) | np.roll(m, 1, 1) | np.roll(m, -1, 1)
        m = m | (g & through)
    return m


def _components(m, min_px):
    """the union of a mask's 4-connected components of at least min_px pixels."""
    out = np.zeros_like(m)
    rest = m.copy()
    while rest.any():
        c = _largest(rest)
        if c.sum() < min_px:
            break
        out |= c; rest &= ~c
    return out


def segment(rgba, iris_hue=IRIS_HUE):
    """-> dict of masks: sclera, iris (an ellipse fitted round its colour and dark ring; pupil and highlights inside),
    pupil, highlight, line (dark outside the iris: the lids), opening (sclera + iris, filled along rows)."""
    rgb, al = rgba[..., :3], rgba[..., 3]
    h, s, v = _hsv(rgb)
    on = al > 0.5
    dark = on & (v < 0.32)
    iris_col = _largest(on & (h >= iris_hue[0]) & (h <= iris_hue[1]) & (s > 0.25) & (v > 0.4))
    Hh, W = al.shape
    iris = np.zeros_like(on)
    if iris_col.any():
        ring = _grow(iris_col, dark | iris_col, max(2, int(0.02 * max(Hh, W))))
        x0, x1, y0, y1 = _box(ring)
        cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0 + 1) / 2, (y1 - y0 + 1) / 2
        yy, xx = np.mgrid[0:Hh, 0:W]
        iris = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1
    # white or cool grey (the lid's shadow on it); pale warm skin is not sclera
    white = (s < 0.07) | ((h >= 170) & (h <= 290) & (s < 0.3))
    sclera = _components(on & white & (v > 0.6) & ~iris, max(4, int(0.004 * on.sum())))
    opening = _row_fill(sclera | iris)
    # the pupil: dark inside the iris, clear of its ring (the inner 80% of the ellipse)
    inner = np.zeros_like(iris)
    if iris.any():
        inner = ((xx - cx) / (0.8 * rx)) ** 2 + ((yy - cy) / (0.88 * ry)) ** 2 <= 1
    pupil = _largest(dark & inner)
    highlight = _largest(iris & (v > 0.93) & (s < 0.1))
    line = dark & ~iris
    return dict(sclera=sclera, iris=iris, pupil=pupil, highlight=highlight, line=line, opening=opening)


def measure(rgba, ppl, iris_hue=IRIS_HUE):
    """an eye picture's measures (see the module), lengths in head lengths L; None where a part isn't found. The
    opening's box is segment()'s; the iris's height is the whole iris's (refine: a lid's shadow can darken its top out
    of its lit colour); the pupil's run, aspect and share come from its coverage map (pupil_shape: a threshold cut its
    soft ends and read a 6 px width to a pixel)."""
    S = segment(rgba, iris_hue)
    out = {}
    ob, ib, pb, hb = (_box(S[k]) for k in ('opening', 'iris', 'pupil', 'highlight'))
    if ob is None or ib is None:
        return {'found': False}
    R = refine(rgba, S, iris_hue)
    fb = _box(R['iris_full'] & R['opening'])
    ow, oh = (ob[1] - ob[0] + 1) / ppl, (ob[3] - ob[2] + 1) / ppl
    iw, ih = (ib[1] - ib[0] + 1) / ppl, (fb[3] - fb[2] + 1) / ppl
    icx, icy = (ib[0] + ib[1]) / 2, (fb[2] + fb[3]) / 2
    out.update(found=True, open_w=round(ow, 4), open_h=round(oh, 4), aspect=round(oh / ow, 3),
               iris_w=round(iw, 4), iris_h=round(ih, 4), iris_fill=round(min(1.0, ih / oh), 3),
               iris_cx=round(((icx - (ob[0] + ob[1]) / 2) / ppl) / ow, 3), iris_cy=round(((icy - (ob[2] + ob[3]) / 2) / ppl) / oh, 3))
    P = pupil_shape(rgba, R, ppl) if pb else {}
    if P:
        pw, ph = P['pupil_w50_L'], P['pupil_h']
        out.update(pupil_w=round(pw, 4), pupil_h=round(ph, 4), pupil_run=round(ph / ih, 3), pupil_aspect=round(pw / ph, 3),
                   pupil_share=round(float(P['_cover'].sum() / max(1, (R['iris_full'] & R['opening']).sum())), 3))
    if hb:
        ys, xs = np.nonzero(S['highlight'])
        out.update(highlight_share=round(float(S['highlight'].sum() / max(1, S['iris'].sum())), 3),
                   highlight_at=[round(float((xs.mean() - icx) / ((ib[1] - ib[0]) / 2)), 2),
                                 round(float((icy - ys.mean()) / ((ib[3] - ib[2]) / 2)), 2)])
    # the upper lid line above the opening's middle: its thickness, and the gap between it and the opening (skin showing
    # between the lashes and the eye reads as a heavy, hooded lid; drawn eyes put the line on the opening)
    cx = int((ob[0] + ob[1]) / 2)
    col = S['line'][:ob[2] + 2, max(0, cx - 2):cx + 3].any(1)
    out['lid'] = round(float(col.sum()) / ppl, 4)
    # the gap per column across the opening's middle 80%: from the opening's top edge up to the nearest lid-line pixel
    gaps = []
    for c in range(int(ob[0] + 0.1 * (ob[1] - ob[0])), int(ob[1] - 0.1 * (ob[1] - ob[0])) + 1):
        top = np.nonzero(S['opening'][:, c])[0]
        if not len(top):
            continue
        above = np.nonzero(S['line'][:top.min(), c])[0]
        gaps.append((top.min() - above.max() - 1) if len(above) else top.min())
    out['lid_gap'] = round(float(np.mean(gaps)) / ppl, 4) if gaps else None
    # the upper lid line's span against the opening's width (a lash arc much wider than the eye floats past its corners)
    up = _largest(S['line'] & (np.arange(S['line'].shape[0])[:, None] < (ob[2] + ob[3]) / 2))
    lb = _box(up)
    out['lid_span'] = round((lb[1] - lb[0] + 1) / (ob[1] - ob[0] + 1), 3) if lb else None
    out['iris_ratio'] = round(iw / ow, 3)
    # the corner line's tilt (degrees, + = the picture's right corner up): the opening's end columns' middle rows
    rows = np.nonzero(S['opening'][:, ob[0]])[0], np.nonzero(S['opening'][:, ob[1]])[0]
    if len(rows[0]) and len(rows[1]):
        out['tilt'] = round(float(np.degrees(np.arctan2(rows[0].mean() - rows[1].mean(), max(1, ob[1] - ob[0])))), 1)
    out['_masks'] = S
    return out


def compare(ours, design):
    """graded: the opening's aspect and width, the iris's width in it, the pupil's run and aspect, the lid line's gap;
    the highlight's side warns only -> {name: check}."""
    C = {}
    if not ours.get('found') or not design.get('found'):
        return {'eye': {'status': 'SKIPPED', 'why': 'eye not found in %s' % ('ours' if not ours.get('found') else 'the design')}}
    g = ours.get('lid_gap')
    if g is not None:
        C['lid_gap'] = {'value': g, 'design': design.get('lid_gap'),
                        'status': 'PASS' if g <= LID_GAP[0] else 'WARN' if g <= LID_GAP[1] else 'FAIL'}
    ha, hb = ours.get('highlight_at'), design.get('highlight_at')
    if ha and hb:
        C['highlight_side'] = {'value': ha, 'design': hb, 'status': 'PASS' if np.sign(ha[0]) == np.sign(hb[0]) else 'WARN'}
    for k in ('aspect', 'width', 'iris_ratio', 'pupil_run', 'pupil_aspect', 'lid_span'):
        a, b = (ours.get('open_w'), design.get('open_w')) if k == 'width' else (ours.get(k), design.get(k))
        if a is None or b is None:
            C[k] = {'status': 'SKIPPED', 'why': 'not found', 'ours': a, 'design': b}
            continue
        r = a / b
        p, w = LIMITS[k]
        C[k] = {'value': round(r, 3), 'ours': a, 'design': b, 'status': 'PASS' if abs(r - 1) <= p else 'WARN' if abs(r - 1) <= w else 'FAIL'}
    return C


# ------------------------------------------------------------------------------------------------------ per view
PUPIL_W = 0.5                    # px: a row belongs to the pupil while its coverage sums to this much (the tips' cut)
VIEW_LIMITS = {                  # |ours - design| (absolute measures) or |ours / design - 1| (ratios): (pass, warn)
    'front_gap': (0.05, 0.10), 'gaze_off': (0.05, 0.10), 'behind': (0.15, 0.30),
    'pupil_w50': (0.15, 0.30), 'pupil_area': (0.20, 0.40), 'pupil_axis': (0.15, 0.30), 'pupil_h': (0.15, 0.30),
    'pupil_open': (0.15, 0.30), 'pupil_taper': (0.10, 0.20),
    'pupil_cy': (0.10, 0.20), 'edge_angle': (10.0, 20.0), 'edge_rms': (0.01, 0.02), 'flick_out': (0.10, 0.20),
}
RATIO = ('pupil_w50', 'pupil_area', 'pupil_axis', 'pupil_h', 'pupil_open')


def _rows(m):
    """per row of a mask: (first, last) set column, or (-1, -1)."""
    any_ = m.any(1)
    first = np.where(any_, np.argmax(m, 1), -1)
    last = np.where(any_, m.shape[1] - 1 - np.argmax(m[:, ::-1], 1), -1)
    return first, last


def pupil_cover(rgba, S):
    """the pupil as a coverage map (H, W) in 0..1: each pixel near the pupil's mask, its value placed between the iris's
    round it on its row (the median over a ring 2-6 px out, clear of highlights) and the pupil's core (its darkest
    fifth). Anti-aliased edges count by how dark they are, so widths and areas are sub-pixel. None when no pupil."""
    p = S['pupil']
    if not p.any():
        return None
    _, _, v = _hsv(rgba[..., :3])
    iris = S['iris']
    band = _grow(p, iris, 2)
    ring = _grow(band, iris, 4) & ~band & iris & ~S['highlight']
    core = float(np.percentile(v[p], 20))
    ref_all = float(np.median(v[ring])) if ring.any() else float(np.median(v[iris & ~band]))
    c = np.zeros(v.shape)
    for r in np.nonzero(band.any(1))[0]:
        rr = v[max(0, r - 1):r + 2][ring[max(0, r - 1):r + 2]]
        ref = float(np.median(rr)) if len(rr) >= 2 else ref_all
        if ref - core < 0.05:
            continue
        cols = band[r]
        c[r, cols] = np.clip((ref - v[r, cols]) / (ref - core), 0, 1)
    return c


def pupil_shape(rgba, S, ppl, nasal=-1):
    """the pupil's shape and size (see the module): from pupil_cover, the iris's row widths (the opening less its
    sclera) and the opening -> dict, or {} when there's no pupil."""
    c = pupil_cover(rgba, S)
    if c is None or c.sum() < 1:
        return {}
    O = S['opening']
    I = O & ~S['sclera']
    w = c.sum(1)
    on = w >= PUPIL_W
    if not on.any():
        return {}
    # the longest run of rows at the pupil's width or more; its ends where the width crosses PUPIL_W (sub-pixel)
    r = np.nonzero(on)[0]
    splits = np.split(r, np.nonzero(np.diff(r) > 1)[0] + 1)
    run = max(splits, key=lambda a: w[a].sum())
    r0, r1 = int(run[0]), int(run[-1])
    top = r0 - (w[r0] - PUPIL_W) / max(1e-9, w[r0] - w[r0 - 1]) if r0 > 0 else float(r0)
    bot = r1 + (w[r1] - PUPIL_W) / max(1e-9, w[r1] - w[r1 + 1]) if r1 + 1 < len(w) else float(r1)
    top, bot = max(top, r0 - 1.0), min(bot, r1 + 1.0)
    h = bot - top
    iw = I.sum(1).astype(float)
    rows = np.arange(len(w))
    out = {'pupil_h': round(h / ppl, 4)}
    for f in (0.25, 0.5, 0.75):
        rf = top + f * h
        pw, ww = float(np.interp(rf, rows, w)), float(np.interp(rf, rows, iw))
        out['pupil_w%d' % int(f * 100)] = round(pw / ww, 4) if ww > 0 else None
    out['pupil_w50_L'] = round(float(np.interp(top + 0.5 * h, rows, w)) / ppl, 4)
    if out['pupil_w50']:
        out['pupil_taper'] = round(0.5 * ((out['pupil_w25'] or 0) + (out['pupil_w75'] or 0)) / out['pupil_w50'], 3)
    out['pupil_area'] = round(float(c.sum() / max(1, I.sum())), 4)
    # the second-moment ellipse
    yy, xx = np.mgrid[0:c.shape[0], 0:c.shape[1]]
    m = c.sum()
    cx, cy = float((c * xx).sum() / m), float((c * yy).sum() / m)
    cxx = float((c * (xx - cx) ** 2).sum() / m); cyy = float((c * (yy - cy) ** 2).sum() / m)
    cxy = float((c * (xx - cx) * (yy - cy)).sum() / m)
    ev, evec = np.linalg.eigh(np.array([[cxx, cxy], [cxy, cyy]]))
    major = evec[:, 1] if evec[1, 1] <= 0 else -evec[:, 1]                # pointing up the picture (rows run down)
    tilt = float(np.degrees(np.arctan2(major[0], -major[1])))           # + : the top toward the picture's right
    out['pupil_axis'] = round(float(np.sqrt(max(ev[0], 0) / max(ev[1], 1e-12))), 4)
    out['pupil_tilt'] = round(tilt * nasal, 1)                          # + : the top toward the nose
    out['pupil_fill'] = round(float(m / (4 * np.pi * np.sqrt(max(ev[0], 1e-12) * max(ev[1], 1e-12)))), 3)
    out['pupil_ellipse'] = [round(cx, 2), round(cy, 2), round(2 * float(np.sqrt(max(ev[1], 0))), 2),
                            round(2 * float(np.sqrt(max(ev[0], 0))), 2), round(tilt, 1)]   # px: centre, semi-axes, tilt
    # the centroid in the iris: across, at its row (+ nasal); up, in the visible iris's rows
    i0, i1 = _rows(I)
    k = int(round(cy))
    if 0 <= k < len(i0) and i0[k] >= 0:
        half = (i1[k] - i0[k] + 1) / 2
        out['pupil_cx'] = round(float((cx - (i0[k] + i1[k]) / 2) / half * nasal), 3)
    ir = np.nonzero(I.any(1))[0]
    if len(ir):
        out['pupil_cy'] = round(float(((ir[0] + ir[-1]) / 2 - cy) / ((ir[-1] - ir[0] + 1) / 2)), 3)
    ob = _box(O)
    if ob is not None:
        out['pupil_open'] = round(float(np.interp(top + 0.5 * h, rows, w)) / (ob[1] - ob[0] + 1), 4)
    out['_cover'] = c
    out['_pupil_rows'] = (top, bot)
    return out


def gaze(S, nasal=-1, mid=0.6):
    """where the iris sits in the opening (see the module): over the visible iris's middle `mid` of its rows -> dict."""
    O = S['opening']
    I = O & ~S['sclera']
    ob = _box(O)
    ir = np.nonzero(I.any(1))[0]
    if ob is None or not len(ir):
        return {}
    ow = ob[1] - ob[0] + 1
    lo, hi = ir[0] + (1 - mid) / 2 * (ir[-1] - ir[0]), ir[-1] - (1 - mid) / 2 * (ir[-1] - ir[0])
    o0, o1 = _rows(O)
    i0, i1 = _rows(I)
    gaps, backs, rows = [], [], []
    for r in range(int(np.ceil(lo)), int(np.floor(hi)) + 1):
        if i0[r] < 0 or o0[r] < 0:
            continue
        g, b = (i0[r] - o0[r], o1[r] - i1[r]) if nasal < 0 else (o1[r] - i1[r], i0[r] - o0[r])
        gaps.append(g); backs.append(b); rows.append(r)
    if not rows:
        return {}
    ys, xs = np.nonzero(I)
    off = (xs.mean() - (ob[0] + ob[1]) / 2) / ow * nasal
    tot = sum(gaps) + sum(backs)
    return {'front_gap': round(float(np.median(gaps)) / ow, 3), 'gaze_off': round(float(off), 3),
            'behind': round(sum(backs) / tot, 3) if tot else None, '_gaze_rows': rows, '_gaps': gaps}


def front_edge(S, nasal=-1, mid=0.8):
    """the opening's nasal edge over the middle `mid` of its height: a line fitted to it -> dict(edge_angle (degrees from
    vertical, + the top toward the nose), edge_rms (rms off the line, in opening heights), the line's ends in px)."""
    O = S['opening']
    ob = _box(O)
    if ob is None:
        return {}
    oh = ob[3] - ob[2] + 1
    o0, o1 = _rows(O)
    e = o0 if nasal < 0 else o1
    lo, hi = ob[2] + (1 - mid) / 2 * oh, ob[3] - (1 - mid) / 2 * oh
    rows = np.array([r for r in range(int(np.ceil(lo)), int(np.floor(hi)) + 1) if e[r] >= 0])
    if len(rows) < 3:
        return {}
    x = e[rows].astype(float)
    a, b = np.polyfit(rows, x, 1)
    res = x - (a * rows + b)
    ang = float(np.degrees(np.arctan(a))) * -nasal
    return {'edge_angle': round(ang, 1), 'edge_rms': round(float(np.sqrt(np.mean(res ** 2))) / oh, 4),
            '_edge': [(float(a * rows[0] + b), float(rows[0])), (float(a * rows[-1] + b), float(rows[-1]))]}


FLICK_BELOW = 0.15               # opening heights under the far corner's row that the flick's window reaches


def flick(S, nasal=-1):
    """the upper lash line's far tip against the opening's far corner (see the module) -> dict."""
    O = S['opening']
    ob = _box(O)
    if ob is None:
        return {}
    ow, oh = ob[1] - ob[0] + 1, ob[3] - ob[2] + 1
    H, W = O.shape
    yy, xx = np.mgrid[0:H, 0:W]
    cxc = ob[1] if nasal < 0 else ob[0]
    cy = float(np.nonzero(O[:, cxc])[0].mean())
    # the window reaches FLICK_BELOW opening heights under the far corner's row (and at least the opening's middle row):
    # the flick leaves the corner, so its tip lies near the corner's row. (It ended at the middle row until tool/face6:
    # a flick whose tip lay on that row read its notch instead, -0.34 against 0.53, as the opening's box moved a pixel.)
    bottom = max((ob[2] + ob[3]) / 2, cy + FLICK_BELOW * oh)
    win = (yy < bottom) & (yy > ob[2] - 0.6 * oh) & (xx > ob[0] - 0.6 * ow) & (xx < ob[1] + 0.9 * ow)
    line = S['line'] & win
    # the lash line: the dark component lying most along the opening's top edge (not a hair strand or the face's line)
    o0, o1 = _rows(O)
    top = np.full(W, -1)
    for cc in range(ob[0], ob[1] + 1):
        rr = np.nonzero(O[:, cc])[0]
        if len(rr):
            top[cc] = rr[0]
    rest, best, best_n = line.copy(), None, 0
    while rest.any():
        comp = _largest(rest)
        rest &= ~comp
        if comp.sum() < 4:
            break
        n = sum(int(comp[max(0, top[cc] - 4):top[cc] + 1, cc].any()) for cc in range(ob[0], ob[1] + 1) if top[cc] >= 0)
        if n > best_n:
            best, best_n = comp, n
    if best is None:
        return {}
    ys, xs = np.nonzero(best)
    far = xs * -nasal
    k = np.nonzero(far == far.max())[0]
    k = k[np.argmin(ys[k])]
    tx, ty = float(xs[k]), float(ys[k])
    out_ = (tx - cxc) * -nasal
    return {'flick_out': round(out_ / ow, 3), 'flick_up': round((cy - ty) / oh, 3),
            'flick_angle': round(float(np.degrees(np.arctan2(cy - ty, out_))), 1), '_tip': (tx, ty), '_corner': (float(cxc), cy)}


def refine(rgba, S, iris_hue=IRIS_HUE):
    """segment()'s masks with the iris taken whole for the per-view measures: its colour's dark shades too (the top a
    lid's shadow darkens: the iris's hue, saturated, however dark, connected to its lit colour within its columns and
    up to 0.8 of its height above it), filled along rows (the pupil and highlights inside), and the opening re-filled
    from it. The lash line (a red-black) and skin (unsaturated) stay out. -> a new dict of masks."""
    ib = _box(S['iris'])
    if ib is None:
        return S
    h, s, v = _hsv(rgba[..., :3])
    on = rgba[..., 3] > 0.5
    H, W = on.shape
    yy, xx = np.mgrid[0:H, 0:W]
    ih = ib[3] - ib[2] + 1
    box = (xx >= ib[0] - 2) & (xx <= ib[1] + 2) & (yy >= ib[2] - 0.8 * ih) & (yy <= ib[3] + 2)
    amber = on & box & (h >= iris_hue[0] - 13) & (h <= iris_hue[1] + 5) & (s > 0.45) & (v > 0.12)
    seed = S['iris'] & amber
    grown = _grow(seed, amber, int(ih))
    iris = _row_fill(grown | (S['pupil'] & box)) | S['iris']
    out = dict(S)
    out['iris_full'] = iris
    out['opening'] = _row_fill(S['sclera'] | iris)
    return out


def measure_view(rgba, ppl, nasal=-1, iris_hue=IRIS_HUE):
    """measure() with the per-view measures (gaze, pupil, edge, flick; see the module) for an eye whose nose lies
    `nasal` (-1 the picture's left, +1 its right), on the masks refine() makes."""
    M = measure(rgba, ppl, iris_hue)
    if not M.get('found'):
        return M
    S = M['_masks'] = refine(rgba, M['_masks'], iris_hue)
    for part in (gaze(S, nasal), pupil_shape(rgba, S, ppl, nasal), front_edge(S, nasal), flick(S, nasal)):
        M.update(part)
    M['nasal'] = nasal
    return M


def compare_view(ours, design, keys):
    """graded per-view checks for the named measures (VIEW_LIMITS; ratios in RATIO) -> {name: check}."""
    C = {}
    for k in keys:
        a, b = ours.get(k), design.get(k)
        if a is None or b is None:
            C[k] = {'status': 'SKIPPED', 'why': 'not found', 'ours': a, 'design': b}
            continue
        p, w = VIEW_LIMITS[k]
        d = (a / b - 1) if k in RATIO else (a - b)
        C[k] = {'value': round(float(a / b if k in RATIO else a - b), 3), 'ours': a, 'design': b,
                'status': 'PASS' if abs(d) <= p else 'WARN' if abs(d) <= w else 'FAIL'}
    return C


# what each view grades: the front keeps its flat read (its pupil is the design's size and shape); three-quarter and
# profile follow from the geometry (where the iris sits; the profile's edge and flick)
VIEW_CHECKS = {
    'front': ('front_gap', 'gaze_off', 'pupil_w50', 'pupil_taper', 'pupil_area', 'pupil_axis', 'pupil_h', 'pupil_open',
              'pupil_cy'),
    'three_quarter': ('front_gap', 'gaze_off', 'behind'),
    'profile': ('front_gap', 'gaze_off', 'behind', 'edge_angle', 'edge_rms', 'flick_out'),
}
NASAL = {('front', 'L'): -1, ('front', 'R'): 1, ('three_quarter', 'L'): -1, ('three_quarter', 'R'): 1,
         ('profile', 'L'): -1}


def views(B, design=None, out=None, ss=3):
    """the QA part: each eye the head sheet draws (front both, three-quarter both, profile), ours rendered from the same
    azimuth (charkit.qa3d.eye_image) at the sheet's scale, both measured by measure_view and graded (VIEW_CHECKS): the
    front's pupil, where the iris sits in every view, the profile's edge and flick -> (table, checks view_<view>_<k>)."""
    from . import eyepage, qa3d
    des, ppl = eyepage.design_eyes(B.spec)
    if not des:
        return None, {'view': {'status': 'SKIPPED', 'why': 'no eyes sheet'}}
    Dz = design or qa3d.Design(B)
    got = Dz.sheet_measures()
    az3 = float(got[0].get('az_three_quarter', 35.0)) if got else 35.0
    azs = {'front': 0.0, 'three_quarter': az3, 'profile': 90.0}
    table, C = {'ppl': ppl, 'az_three_quarter': az3}, {}
    for view, pairs in des.items():
        for side, px in pairs:
            if not B.skin().has('render_eye_' + side):
                continue
            n = NASAL.get((view, side), -1)
            md = measure_view(px, ppl, n)
            mo = measure_view(qa3d.eye_image(B, side, ppl, ss=ss, az=azs[view]), ppl, n)
            strip = lambda M: {k: v for k, v in M.items() if not k.startswith('_')}
            table['%s_%s' % (view, side)] = {'ours': strip(mo), 'design': strip(md)}
            if not (mo.get('found') and md.get('found')):
                continue
            for k, v in compare_view(mo, md, VIEW_CHECKS[view]).items():
                name = 'view_%s_%s' % (view, k)
                prev = C.get(name)
                if prev is None or qa3d.STATUS.index(v['status']) > qa3d.STATUS.index(prev['status']):
                    C[name] = dict(v, eye=side)
    return table, C


def overlay(rgba, M, scale=4, bg=0.93):
    """an eye picture with its per-view measures drawn (measure_view's M), `scale` times up -> RGB floats: the opening's
    outline (magenta), the pupil's width lines at 25/50/75% of its height (cyan) and its second-moment ellipse (yellow),
    the front gap per row (red: the sclera between the opening's nasal edge and the iris's), the fitted front edge
    (green), the lash flick's tip and the far corner (blue)."""
    from PIL import Image, ImageDraw
    im = rgba[..., :3] * rgba[..., 3:4] + bg * (1 - rgba[..., 3:4])
    H, W = im.shape[:2]
    pic = Image.fromarray((np.clip(im, 0, 1) * 255).astype(np.uint8)).resize((W * scale, H * scale), Image.NEAREST)
    d = ImageDraw.Draw(pic)
    s = float(scale)
    P = lambda x, y: ((x + 0.5) * s, (y + 0.5) * s)
    S = M.get('_masks') or {}
    if 'opening' in S:
        o = S['opening']
        e = o & ~(np.roll(o, 1, 0) & np.roll(o, -1, 0) & np.roll(o, 1, 1) & np.roll(o, -1, 1))
        for y, x in zip(*np.nonzero(e)):
            d.rectangle([x * s + s / 2 - 1, y * s + s / 2 - 1, x * s + s / 2, y * s + s / 2], fill=(220, 30, 160))
    nasal = M.get('nasal', -1)
    # the front gap, per row
    if M.get('_gaze_rows') and 'opening' in S:
        o0, o1 = _rows(S['opening'])
        for r, g in zip(M['_gaze_rows'], M['_gaps']):
            if g > 0:
                x0 = o0[r] if nasal < 0 else o1[r] - g + 1
                d.line([P(x0 - 0.5, r), P(x0 + g - 0.5, r)], fill=(230, 20, 20), width=max(1, scale // 2))
    # the front edge's line
    if M.get('_edge'):
        (xa, ya), (xb, yb) = M['_edge']
        d.line([P(xa, ya), P(xb, yb)], fill=(20, 170, 60), width=max(1, scale // 2))
    # the pupil: width lines and the moment ellipse
    if M.get('_pupil_rows') and M.get('_cover') is not None:
        c = M['_cover']
        top, bot = M['_pupil_rows']
        w = c.sum(1)
        for f in (0.25, 0.5, 0.75):
            r = top + f * (bot - top)
            k = int(np.clip(round(r), 0, H - 1))
            if c[k].sum() <= 0:
                continue
            cx = float((c[k] * np.arange(W)).sum() / c[k].sum())
            half = float(np.interp(r, np.arange(H), w)) / 2
            d.line([P(cx - half - 0.5, r), P(cx + half - 0.5, r)], fill=(0, 220, 255), width=max(1, scale // 3))
        cx, cy, a, b, tilt = M['pupil_ellipse']
        t = np.linspace(0, 2 * np.pi, 64)
        th = np.radians(tilt)
        # the major axis runs up the picture, tilted `tilt` degrees toward its right
        xs = cx + b * np.cos(t) * np.cos(th) + a * np.sin(t) * np.sin(th)
        ys = cy + b * np.cos(t) * np.sin(th) - a * np.sin(t) * np.cos(th)
        d.line([P(x, y) for x, y in zip(xs, ys)], fill=(255, 210, 0), width=1)
    if M.get('_tip'):
        for (x, y), col in ((M['_tip'], (30, 60, 230)), (M['_corner'], (30, 60, 230))):
            d.ellipse([P(x, y)[0] - 3, P(x, y)[1] - 3, P(x, y)[0] + 3, P(x, y)[1] + 3], outline=col, width=2)
        d.line([P(*M['_corner']), P(*M['_tip'])], fill=(30, 60, 230), width=1)
    return np.asarray(pic, float) / 255


def picture(ours_rgba, design_rgba, ours, design, scale=3):
    """the two eyes side by side, each above its segmentation (sclera blue, iris amber, pupil black, highlight white,
    lid line grey, opening outlined)."""
    def seg(M, shape):
        im = np.full(shape[:2] + (3,), 0.93)
        S = M.get('_masks')
        if S:
            im[S['line']] = 0.45; im[S['sclera']] = (0.6, 0.8, 1.0); im[S['iris']] = (1.0, 0.7, 0.1)
            im[S['highlight']] = 1.0; im[S['pupil']] = 0.05
            o = S['opening']; edge = o & ~(np.roll(o, 1, 0) & np.roll(o, -1, 0) & np.roll(o, 1, 1) & np.roll(o, -1, 1))
            im[edge] = (0.9, 0.1, 0.5)
        return im

    def flat(rgba):
        return rgba[..., :3] * rgba[..., 3:4] + 0.93 * (1 - rgba[..., 3:4])
    cols = []
    for rgba, M in ((design_rgba, design), (ours_rgba, ours)):
        cols.append(np.concatenate([flat(rgba), seg(M, rgba.shape)], 0))
    Hm = max(c.shape[0] for c in cols)
    cols = [np.pad(c, ((0, Hm - c.shape[0]), (0, 6), (0, 0)), constant_values=1.0) for c in cols]
    im = np.concatenate(cols, 1)
    return np.repeat(np.repeat(im, scale, 0), scale, 1)
