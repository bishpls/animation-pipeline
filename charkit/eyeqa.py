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

    from charkit import eyeqa
    M = eyeqa.measure(rgba, ppl)             # rgba (H, W, 4) floats 0..1, ppl: pixels per head length
    C = eyeqa.compare(ours, design)          # graded checks
"""
import numpy as np

IRIS_HUE = (28.0, 65.0)                          # degrees; the design's amber (a character's iris hue range)
LIMITS = {                                       # |ours / design - 1|: (pass within, warn within); else fail
    'aspect': (0.10, 0.20), 'width': (0.08, 0.15), 'iris_fill': (0.10, 0.20),
    'pupil_run': (0.15, 0.30), 'pupil_aspect': (0.20, 0.40), 'iris_ratio': (0.10, 0.20), 'lid_span': (0.10, 0.20),
}
LID_GAP = (0.004, 0.010)                         # L between the upper lid line and the opening: (pass, warn)


def _hsv(rgb):
    from .i3d import hsv
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
    """an eye picture's measures (see the module), lengths in head lengths L; None where a part isn't found."""
    S = segment(rgba, iris_hue)
    out = {}
    ob, ib, pb, hb = (_box(S[k]) for k in ('opening', 'iris', 'pupil', 'highlight'))
    if ob is None or ib is None:
        return {'found': False}
    ow, oh = (ob[1] - ob[0] + 1) / ppl, (ob[3] - ob[2] + 1) / ppl
    iw, ih = (ib[1] - ib[0] + 1) / ppl, (ib[3] - ib[2] + 1) / ppl
    icx, icy = (ib[0] + ib[1]) / 2, (ib[2] + ib[3]) / 2
    out.update(found=True, open_w=round(ow, 4), open_h=round(oh, 4), aspect=round(oh / ow, 3),
               iris_w=round(iw, 4), iris_h=round(ih, 4), iris_fill=round(ih / oh, 3),
               iris_cx=round(((icx - (ob[0] + ob[1]) / 2) / ppl) / ow, 3), iris_cy=round(((icy - (ob[2] + ob[3]) / 2) / ppl) / oh, 3))
    if pb:
        pw, ph = (pb[1] - pb[0] + 1) / ppl, (pb[3] - pb[2] + 1) / ppl
        out.update(pupil_w=round(pw, 4), pupil_h=round(ph, 4), pupil_run=round(ph / ih, 3), pupil_aspect=round(pw / ph, 3),
                   pupil_share=round(float(S['pupil'].sum() / max(1, S['iris'].sum())), 3))
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
