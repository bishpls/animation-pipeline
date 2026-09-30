"""Full-body model-sheet QA: the whole character against the design's front, three-quarter, profile and back figures, both
measured the same way from a class image (pure numpy; ours is the scene z-buffered with a class per triangle).

The drawing is segmented by colour into skin, hair, iris, line and the garment colour families (orange dress, cream bow /
panel / cuffs, dark brown hems and shorts, white boots). Hair and the dress share their orange, so an orange region (the
drawn lines are its walls) is hair when its centre lies above HAIR_SPLIT (the shoulders), else dress; a cream fold's
shadow has skin's hue, so a pale region is skin or cream by its majority. Dark regions thick enough to survive an erosion
are garment (shorts, hems, soles); thin ones are line. Lines are then absorbed into the classes they separate, as ours has
none.

Both sides share one grid: the sheet's scale (pixels per head length L) and an origin on the eyes, so heights run from the
eye line. Aligned on the eyes, not the feet: every other sheet check is measured from the eye line, and a proportion error
then shows where it is (legs too long put the feet low) instead of being spread over the whole figure. The back view has no
eyes: its eye line is the front's (the figures stand on one baseline at one scale) and its axis the head's silhouette.

Per view (lengths in L from the eye line; x from the eyes, or the axis from the back):
  iou            silhouette, hair, skin and outfit (every garment family) IoU; each family's IoU as information
  feet / top     the figure's lowest and highest rows
  hair           its lowest row (length), its width and its reach either side
  skirt          its widest row (the garment run through the body's axis between the waist and the knee, rows with a
                 hand resting against it left out) and the hem (the fabric's lowest row, dark trim excluded), overall
                 and at the middle
  leg            where the legs first show under the skirt near the axis, to the sole; boot: its white top to the sole
  arms           each arm's angle off the vertical, shoulder to hand (front and back; information: the build pose)
  sleeves        the widest garment run through the axis at the shoulders (across both puffs)

    from charkit import bodyqa
    design = bodyqa.design_views(rgb, D, ppl)               # the sheet's views as data (classes, figure, grid) per view
    labels = bodyqa.zbuffer_views(meshes, az3, iris, centre, L, ppl)     # ours on the same grids ({view: (depth, label)})
    table, checks, views = bodyqa.evaluate(labels, design)  # measure (measure()) and grade (compare()) both, per view
"""
import numpy as np

CLASS = {'none': 0, 'skin': 1, 'hair': 2, 'iris': 3, 'line': 4, 'orange': 6, 'cream': 7, 'dark': 8, 'white': 9, 'other': 10}
GARMENT = (6, 7, 8, 9)
FABRIC = (6, 7)                    # the skirt's cloth (its dark trim is a family of its own)
HAIR_SPLIT = -0.8                  # L from the eye line: an orange region centred above it is hair (the shoulders)
WIN = dict(x=2.3, top=1.3, bottom=-6.2)   # the full-body window, L round the eyes
BANDS = dict(skirt=(-1.4, -3.5), sleeves=(-0.55, -1.35), torso=(-0.95, -1.3))
LIMITS = {                          # (pass within, warn within); else fail
    'iou': (0.85, 0.70),            # silhouette IoU (higher is better)
    'iou_part': (0.70, 0.50),       # hair, skin, outfit IoU
    'length': (0.08, 0.16),         # |ours - design| of a height, L
    'width': (0.08, 0.15),          # |ours / design - 1| of a width
    'leg_gap': (0.01, 0.03),        # L of rows where the design's legs stand apart and ours join (a bridge)
    'boot_step': (0.015, 0.03),     # L: a boot outline's largest row-to-row jump beyond the design's
    'aline': (0.05, 0.12),          # |ours - design| of the skirt's width near its hem over its widest
    'chest': (0.03, 0.06),          # |mean| L the chest's front edge in profile stands behind (or before) the design's
    'waist_skin': (0.01, 0.03),     # share of the waist's rows, across the body, that are skin beyond the design's
}
MIN_PX = 150                        # a part measured from fewer pixels (either side) is cautioned


# ------------------------------------------------------------------------------------------------------------ classes
def _hsv(rgb):
    from .target3d import hsv
    s = rgb.shape[:-1]
    h, sat, v = hsv(np.asarray(rgb, float).reshape(-1, 3))
    return h.reshape(s), sat.reshape(s), v.reshape(s)


def family(rgb):
    """class ids of colours by their family (any shape (..., 3), sRGB 0..1): skin, orange, cream, dark, white, yellow
    (iris; a star clip too), else other."""
    h, s, v = _hsv(rgb)
    out = np.full(h.shape, CLASS['other'])
    out[(v < 0.45) & (s < 0.6)] = CLASS['dark']
    out[(s < 0.1) & (v > 0.8)] = CLASS['white']
    out[(h >= 32) & (h <= 62) & (s >= 0.1) & (s < 0.45) & (v > 0.7)] = CLASS['cream']
    out[(h >= 5) & (h < 32) & (s >= 0.08) & (s < 0.45) & (v > 0.6)] = CLASS['skin']
    out[((h < 30) | (h > 345)) & (s >= 0.45) & (v >= 0.45)] = CLASS['orange']
    out[(h >= 38) & (h <= 66) & (s > 0.45) & (v > 0.55)] = CLASS['iris']
    return out


def _shift(m, dy, dx, fill=False):
    out = np.full_like(m, fill)
    H, W = m.shape
    out[max(0, dy):H + min(0, dy), max(0, dx):W + min(0, dx)] = m[max(0, -dy):H + min(0, -dy), max(0, -dx):W + min(0, -dx)]
    return out


def erode(m, r):
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out &= _shift(m, dy, dx, False)
    return out


def dilate(m, r):
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out |= _shift(m, dy, dx, False)
    return out


def absorb(cls, fg, drop=(CLASS['line'], CLASS['other']), steps=6):
    """lines (and unclassed anti-aliasing) handed to the class most of their neighbours have, a few pixels deep; what is
    left stays as it was."""
    from .bodymeasure import window
    out = cls.copy()
    keep = [c for c in range(1, 11) if c not in drop]
    w = window(fg & np.isin(cls, drop))    # (only these pixels change, each from its 8 neighbours: their window, padded
    if w is None:                          # by one, reads as the whole grid does)
        return out
    cls, fg = out[w], fg[w]                # (a view: the window's changes are the copy's)
    for _ in range(steps):
        todo = fg & np.isin(cls, drop)
        if not todo.any():
            break
        best, cnt = np.zeros_like(cls), np.zeros(cls.shape, int)
        for c in keep:
            m = cls == c
            n = sum(_shift(m, dy, dx).astype(int) for dy in (-1, 0, 1) for dx in (-1, 0, 1))
            better = n > cnt
            best[better], cnt[better] = c, n[better]
        take = todo & (cnt > 0)
        cls[take] = best[take]
    return out


def classes(rgb, fg, eye_y, ppl, split=HAIR_SPLIT, thick=2):
    """a drawing's class image over its figure (fg): colour families, dark split into garment (thick) and line (thin),
    orange split into hair and dress by where each line-bounded region's centre lies, then the lines absorbed.
    -> (cls, raw) where raw keeps the lines."""
    from .sheetqa import label
    cls = np.where(fg, family(rgb), CLASS['none'])
    # skin and cream: a cream garment's shadow is skin's hue, so each pale region between the lines takes its majority
    pale = (cls == CLASS['skin']) | (cls == CLASS['cream'])
    reg, n = label(pale)
    if n:
        k = reg[pale] - 1
        sk = np.bincount(k, cls[pale] == CLASS['skin'], n) > 0.5 * np.bincount(k, None, n)
        cls[pale] = np.where(sk[k], CLASS['skin'], CLASS['cream'])
    for c in (CLASS['skin'], CLASS['orange'], CLASS['cream'], CLASS['white']):     # slivers: anti-aliasing between two
        m = cls == c                                                             # colours reads as a third
        cls[m & ~dilate(erode(m, 1), 1)] = CLASS['other']
    dark = cls == CLASS['dark']
    thick_dark = dilate(erode(dark, thick), thick) & dark
    cls[dark & ~thick_dark] = CLASS['line']
    orange = cls == CLASS['orange']
    reg, n = label(orange)
    if n:
        ys, xs = np.nonzero(reg)
        k = reg[ys, xs] - 1
        cy = np.bincount(k, ys, n) / np.maximum(np.bincount(k, None, n), 1)
        hair = (eye_y - cy) / ppl > split
        cls[orange & hair[np.maximum(reg - 1, 0)]] = CLASS['hair']
    raw = cls.copy()
    return absorb(cls, fg), raw


def crop(a, eye, ppl, win=WIN, fill=0):
    """the window round an eye point (x, y pixels) of an image at ppl: the same grid as faceqa.zbuffer's at pix = 1 / ppl
    with the origin on the eyes."""
    Wd = int(round(2 * win['x'] * ppl)); Hd = int(round((win['top'] - win['bottom']) * ppl))
    x0 = int(round(eye[0] - win['x'] * ppl)); y0 = int(round(eye[1] - win['top'] * ppl))
    out = np.full((Hd, Wd) + a.shape[2:], fill, a.dtype)
    H, W = a.shape[:2]
    sx0, sy0, sx1, sy1 = max(0, x0), max(0, y0), min(W, x0 + Wd), min(H, y0 + Hd)
    if sx1 > sx0 and sy1 > sy0:
        out[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = a[sy0:sy1, sx0:sx1]
    return out


# ------------------------------------------------------------------------------------------------------------ measures
def _run(row, c, gap=3):
    """the run of True in a bool row containing column c (gaps up to `gap` bridged) -> (lo, hi) or None."""
    W = len(row)
    if not (0 <= c < W) or not row[max(0, c - gap):c + gap + 1].any():
        return None
    lo = hi = c
    while True:
        nxt = np.nonzero(row[max(0, lo - gap - 1):lo])[0]
        if not len(nxt):
            break
        lo = max(0, lo - gap - 1) + nxt[0]
    while True:
        nxt = np.nonzero(row[hi + 1:hi + gap + 2])[0]
        if not len(nxt):
            break
        hi = hi + 1 + nxt[-1]
    return lo, hi


def _rows(z, band):
    return np.nonzero((z <= band[0]) & (z >= band[1]))[0]


def measure(cls, fg, ppl, view, cut=None, win=WIN):
    """one view's measures from a class image on the shared grid (origin on the eyes: column win.x * ppl, row win.top *
    ppl). cut: the row z (L) below which the drawing is missing (a partial figure). -> dict (see the module)."""
    H, W = cls.shape
    z = win['top'] - (np.arange(H) + 0.5) / ppl
    u = (np.arange(W) + 0.5) / ppl - win['x']
    if cut is not None:
        fg = fg & (z >= cut)[:, None]
        cls = np.where(fg, cls, 0)
    M = {'view': view, 'ppl': ppl, 'cut': cut, 'px': {}}
    rows = np.nonzero(fg.any(1))[0]
    if not len(rows):
        return M
    M['top'] = round(float(z[rows[0]]), 4)
    M['feet'] = round(float(z[rows[-1]]), 4) if cut is None else None
    for name, cs in (('hair', (2,)), ('skin', (1,)), ('outfit', GARMENT), ('white', (9,)), ('orange', (6,)),
                     ('cream', (7,)), ('dark', (8,))):
        M['px'][name] = int(np.isin(cls, cs).sum())
    # the body's axis: the centre of the widest garment run per row across the torso
    gar = np.isin(cls, GARMENT)
    cs_ = []
    for r in _rows(z, BANDS['torso']):
        c = np.nonzero(gar[r])[0]
        if len(c):
            runs = np.split(c, np.nonzero(np.diff(c) > 3)[0] + 1)
            best = max(runs, key=len)
            cs_.append((best[0] + best[-1]) / 2)
    ax = int(round(np.median(cs_))) if cs_ else W // 2
    M['axis'] = round(float(u[ax]), 4)
    # hair
    hm = cls == 2
    if hm.any():
        hr, hc = np.nonzero(hm)
        M['hair'] = {'bottom': round(float(z[hr.max()]), 4), 'top': round(float(z[hr.min()]), 4),
                     'left': round(float(u[hc.min()]), 4), 'right': round(float(u[hc.max()]), 4),
                     'width': round(float(u[hc.max()] - u[hc.min()]), 4)}
    # the sleeves: the widest garment run through the axis at the shoulders (across both puffs); the skirt: the widest
    # garment run through the axis between the waist and the knee, rows where an arm reaches it left out (skin just past
    # either end within 0.25 L up or down: a wrist cuff against the skirt would join the run)
    skin = cls == 1
    dy, dx = int(0.25 * ppl), int(0.15 * ppl)

    def widest(band, clear=False, rows_out=None):
        best = None
        for r in _rows(z, band):
            run = _run(gar[r], ax)
            if not run:
                continue
            blocked = clear and (skin[max(0, r - dy):r + dy + 1, max(0, run[0] - dx):max(0, run[0] - 1)].any() or
                                 skin[max(0, r - dy):r + dy + 1, run[1] + 2:run[1] + dx + 1].any())
            if rows_out is not None:
                rows_out[int(r)] = ((run[1] - run[0] + 1) / ppl, bool(blocked))
            if blocked:
                continue
            if best is None or run[1] - run[0] > best[1] - best[0]:
                best = (run[0], run[1], r)
        return best
    for name, band, clear in (('sleeves', BANDS['sleeves'], False), ('skirt', BANDS['skirt'], True)):
        rows_out = {} if name == 'skirt' else None
        b = widest(band, clear, rows_out)
        if b:
            M[name] = {'width': round(float((b[1] - b[0] + 1) / ppl), 4), 'left': round(float(u[b[0]]), 4),
                       'right': round(float(u[b[1]]), 4), 'z': round(float(z[b[2]]), 4)}
        if rows_out:
            M.setdefault(name, {})['_rows'] = rows_out           # per row: its run's width and whether a hand blocks it
    # the hem: the fabric's lowest row in the skirt band, and at the middle
    fab = np.isin(cls, FABRIC)
    rr = _rows(z, BANDS['skirt'])
    if len(rr) and fab[rr].any():
        sub = fab[rr]
        sk = M.setdefault('skirt', {})
        sk['hem'] = round(float(z[rr[np.nonzero(sub.any(1))[0].max()]]), 4)
        mid = sub[:, max(0, ax - int(0.12 * ppl)):ax + int(0.12 * ppl) + 1].any(1)
        if mid.any():
            sk['hem_mid'] = round(float(z[rr[np.nonzero(mid)[0].max()]]), 4)
        sk['clipped'] = bool(sub[-1].any())                             # fabric still at the band's bottom (the knee)
    # the legs: where their skin first shows under the skirt near the axis (a leg's width of skin), to the sole; the boot:
    # its white top to the sole
    if cut is None:
        near = skin[:, max(0, ax - int(0.45 * ppl)):ax + int(0.45 * ppl) + 1].sum(1) >= 0.08 * ppl
        lr = np.nonzero(near & (z <= -1.8) & (z >= -4.5))[0]
        if len(lr):
            M['leg_top'] = round(float(z[lr.min()]), 4)
            M['leg'] = round(M['leg_top'] - M['feet'], 4)
        wr = np.nonzero(((cls == 9).sum(1) >= 0.1 * ppl) & (z < -3.0))[0]           # rows with a boot's width of white
        if len(wr):
            M['boot_top'] = round(float(z[wr.min()]), 4)
            M['boot'] = round(M['boot_top'] - M['feet'], 4)
    # the arms (front and back): each side's hand, the skin farthest out beside the skirt band, its angle from the
    # shoulder (the sleeves' outer end) off the vertical
    if view in ('front', 'back') and 'sleeves' in M:
        arms = {}
        for side, sgn in (('left', -1), ('right', 1)):
            sh = np.array([M['sleeves'][side], M['sleeves']['z']])
            rs = _rows(z, (-1.0, -3.2))
            m = skin[rs] & ((sgn * u)[None, :] > abs(sh[0]))
            if m.sum() >= 20:
                ys, xs = np.nonzero(m)
                far = np.argsort(-sgn * u[xs])[:max(5, len(xs) // 10)]            # the outermost tenth: the hand
                hp = np.array([u[xs[far]].mean(), z[rs[ys[far]]].mean()])
                d = hp - sh
                arms[side] = round(float(np.degrees(np.arctan2(abs(d[0]), -d[1]))), 1)
        if arms:
            M['arms'] = arms
    return M


# ------------------------------------------------------------------------------------------------------------ grading
def _iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else None


def _grade(key, v):
    p, w = LIMITS[key]
    if key.startswith('iou'):
        return 'PASS' if v >= p else 'WARN' if v >= w else 'FAIL'
    return 'PASS' if v <= p else 'WARN' if v <= w else 'FAIL'


LEG_BAND = (-3.4, 0.05)             # L: from below the knee to this far above the feet: the lower legs and boots
LEG_SPAN = 0.55                      # L either side of the axis: the legs (the overskirt tails hang further out)


def _runs(row, min_px=2):
    """the runs of True in a row, at least min_px long -> [(start, end)]."""
    c = np.nonzero(row)[0]
    if not len(c):
        return []
    parts = np.split(c, np.nonzero(np.diff(c) > 1)[0] + 1)
    return [(p[0], p[-1]) for p in parts if len(p) >= min_px]


def legs(ofg, dfg, ocls, dcls, ppl, axis_u, feet, win=WIN):
    """the lower legs and boots row by row (front and back views): where the design's legs stand apart (two runs of the
    figure within LEG_SPAN of the axis) and ours are one (a bridge: the feet or soles joined), and each boot's outline
    (the white run on its side of the axis) as it steps from row to row. -> dict(bridge (L), bridge_rows [z top, z bottom]
    or None, apart (L of rows the design shows apart), step {side: (ours, design) largest row-to-row jump of either edge,
    L})."""
    H, W = ofg.shape
    z = win['top'] - (np.arange(H) + 0.5) / ppl
    u = (np.arange(W) + 0.5) / ppl - win['x']
    band = np.nonzero((z <= LEG_BAND[0]) & (z >= feet + LEG_BAND[1]))[0]
    cols = np.abs(u - axis_u) <= LEG_SPAN
    bridge, apart = [], 0
    for r in band:
        nd, no = len(_runs(dfg[r] & cols)), len(_runs(ofg[r] & cols))
        if nd == 2:
            apart += 1
            if no == 1:
                bridge.append(r)
    # each boot's outline: on its side of the axis, the figure's run within LEG_SPAN (the one holding most of the side's
    # boot white), over the rows its white spans less two at either end; the largest row-to-row jump of either edge
    ax_c = int(round((axis_u + win['x']) * ppl))
    step = {}
    for side, sl in (('image_left', slice(0, ax_c)), ('image_right', slice(ax_c, W))):
        jumps = []
        for fg, cls in ((ofg, ocls), (dfg, dcls)):
            wh = [r for r in band if (cls[r, sl] == CLASS['white']).any()]
            edges = []
            for r in range(wh[0] + 2, wh[-1] - 1) if len(wh) > 5 else []:
                rr = _runs(fg[r, sl] & cols[sl])
                white = cls[r, sl] == CLASS['white']
                if rr:
                    best = max(rr, key=lambda x: (white[x[0]:x[1] + 1].sum(), x[1] - x[0]))
                    # a row whose run ends on the cuff (orange: its rounded lower edge over the narrower shaft) is
                    # the cuff's outline, not the boot's
                    if CLASS['orange'] in (cls[r, sl][best[0]], cls[r, sl][best[1]]):
                        continue
                    edges.append((r, best[0], best[1]))
            j = 0.0
            for (r0, a0, b0), (r1, a1, b1) in zip(edges, edges[1:]):
                if r1 == r0 + 1:
                    j = max(j, abs(a1 - a0), abs(b1 - b0))
            jumps.append(round(j / ppl, 4))
        step[side] = jumps
    # the design's boots are mirror images: its cleaner side is the reference for both (the other's outline breaks where
    # the drawing's shading splits the white)
    ref = min(v[1] for v in step.values())
    step = {k: (v[0], ref) for k, v in step.items()}
    return dict(bridge=round(len(bridge) / ppl, 4),
                bridge_rows=[round(float(z[min(bridge)]), 3), round(float(z[max(bridge)]), 3)] if bridge else None,
                apart=round(apart / ppl, 4), step=step)


CHEST_BAND = (-0.6, -0.95)           # L: the chest in profile, from the collarbone to under the bow
WAIST_BAND = (-1.1, -1.6)            # L: the waist, from under the chest to the skirt's top


def aline(M, ppl, win=WIN):
    """the skirt's width near its hem (the 0.15 L above its hem at the middle, or the lowest row its run through the
    axis reaches: the median run) over its widest row, the rows with no hand against it (else all): about 1 for an
    A-line flaring to its hem, under 1 for a bubble."""
    sk = M.get('skirt') or {}
    rows, hem = sk.get('_rows') or {}, sk.get('hem_mid', sk.get('hem'))
    if not rows or hem is None:
        return None
    z = {r: win['top'] - (r + 0.5) / ppl for r in rows}
    hem = max(hem, min(z.values()))           # (the hem at the middle; the lowest orange row can be a panel's tail)
    use = [r for r in rows if not rows[r][1] and z[r] >= hem] or [r for r in rows if z[r] >= hem]
    near = [rows[r][0] for r in use if z[r] <= hem + 0.15]
    if not use or not near:
        return None
    return float(np.median(near)) / max(rows[r][0] for r in use)


def front_edge(fg, cls, ppl, band, win=WIN):
    """in profile, the figure's front edge (its hair left out) per row of a band, L from the grid's left, turned so + is
    toward the front: the face side is where the skin at the eyes stands off the hair. -> (per-row edge, facing -1/+1)."""
    H, W = fg.shape
    z = win['top'] - (np.arange(H) + 0.5) / ppl
    eye = np.nonzero(np.abs(z) < 0.2)[0]
    sk, hr = np.nonzero(cls[eye] == CLASS['skin'])[1], np.nonzero(cls[eye] == CLASS['hair'])[1]
    face = -1 if (len(sk) and len(hr) and sk.mean() < hr.mean()) else 1
    rows = np.nonzero((z <= band[0]) & (z >= band[1]))[0]
    out = []
    for r in rows:
        c = np.nonzero(fg[r] & (cls[r] != CLASS['hair']))[0]
        out.append(np.nan if not len(c) else (c.min() if face < 0 else c.max()) / ppl)
    return np.array(out), face


def waist_skin(fg, cls, ppl, axis_u, win=WIN):
    """the share of the waist's rows (WAIST_BAND), across the body (the figure's run through the axis), that is skin."""
    H, W = fg.shape
    z = win['top'] - (np.arange(H) + 0.5) / ppl
    ac = int(round((axis_u + win['x']) * ppl))
    tot = sk = 0
    for r in np.nonzero((z <= WAIST_BAND[0]) & (z >= WAIST_BAND[1]))[0]:
        run = _run(fg[r], ac)
        if run:
            seg = cls[r, run[0]:run[1] + 1]
            tot += len(seg); sk += int((seg == CLASS['skin']).sum())
    return sk / tot if tot else None


def compare(O, D, ocls, dcls, ofg, dfg, view, caution=None):
    """ours against the design for one view -> {name: check}. O, D: measure()'s dicts; *cls, *fg: the class images and
    figures on the shared grid. caution: a note every check of this view carries (scale disagreement, a partial figure)."""
    C = {}
    cut = D.get('cut')
    if cut is not None:
        z = WIN['top'] - (np.arange(ofg.shape[0]) + 0.5) / D['ppl']
        ofg = ofg & (z >= cut)[:, None]; dfg = dfg & (z >= cut)[:, None]
        ocls = np.where(ofg, ocls, 0); dcls = np.where(dfg, dcls, 0)

    def add(name, chk):
        if caution:
            chk.setdefault('caution', caution)
        C[name] = chk
    v = _iou(ofg, dfg)
    add('iou', {'value': round(v, 3), 'status': _grade('iou', v)})
    for name, cs, graded in (('hair', (2,), True), ('skin', (1,), True), ('outfit', GARMENT, True),
                             ('orange', (6,), False), ('cream', (7,), False), ('dark', (8,), False), ('white', (9,), False)):
        a, b = np.isin(ocls, cs), np.isin(dcls, cs)
        v = _iou(a, b)
        if v is None:
            continue
        chk = {'value': round(v, 3), 'status': _grade('iou_part', v) if graded else 'INFO',
               'px': {'ours': int(a.sum()), 'design': int(b.sum())}}
        if min(a.sum(), b.sum()) < MIN_PX:
            chk['caution'] = 'few pixels (%d ours, %d design)' % (a.sum(), b.sum())
            if graded:
                chk['status'] = 'INFO'
        add('iou_' + name, chk)

    def length(name, a, b, note=None):
        if a is None or b is None:
            add(name, {'status': 'SKIPPED', 'why': 'not found in %s' % ('ours' if a is None else 'the design'),
                       'ours': a, 'design': b})
            return
        d = round(a - b, 4)
        chk = {'value': d, 'ours': a, 'design': b, 'status': _grade('length', abs(d))}
        if note:
            chk['note'] = note
        add(name, chk)

    def width(name, a, b, note=None):
        if not a or not b:
            add(name, {'status': 'SKIPPED', 'why': 'not found in %s' % ('ours' if not a else 'the design'),
                       'ours': a, 'design': b})
            return
        r = round(a / b, 3)
        chk = {'value': r, 'ours': a, 'design': b, 'status': _grade('width', abs(r - 1))}
        if note:
            chk['note'] = note
        add(name, chk)
    g = lambda M, *k: (M.get(k[0]) or {}).get(k[1]) if len(k) == 2 else M.get(k[0])
    if cut is None:
        length('feet', g(O, 'feet'), g(D, 'feet'), '- = ours lower (taller below the eyes)')
    length('top', g(O, 'top'), g(D, 'top'))
    length('hair_length', g(O, 'hair', 'bottom'), g(D, 'hair', 'bottom'), "the hair's lowest row; - = ours longer")
    width('hair_width', g(O, 'hair', 'width'), g(D, 'hair', 'width'))
    # the skirt's width on the rows neither figure's hand touches: where the hands hang differently (ours are the
    # hull's, the drawing's where the artist put them), the widest free row of each could sit at different heights
    ro, rd = (O.get('skirt') or {}).get('_rows') or {}, (D.get('skirt') or {}).get('_rows') or {}
    common = [r for r in ro if r in rd and not ro[r][1] and not rd[r][1]]
    if common:
        width('skirt_width', round(max(ro[r][0] for r in common), 4), round(max(rd[r][0] for r in common), 4),
              'the widest garment row through the axis between waist and knee, on the rows neither figure has a hand '
              'against')
    elif [r for r in rd if not rd[r][1] and r in ro]:
        # no row free in both (ours' hands hang against every row the design's leave free): the design's free rows and
        # ours on the same rows, the row whose ratio is their median. Each figure's own widest over those rows sat at
        # different heights (clawd_mh's back: the design's free rows are the waist, widening downward, and ours' widest
        # was its top row against the design's bottom one), and one row alone (the design's widest) fell where ours'
        # run through the axis breaks for a few rows at the waist
        fd = [r for r in rd if not rd[r][1] and r in ro]
        by = sorted(fd, key=lambda r: (ro[r][0] / rd[r][0] if rd[r][0] else 0.0, r))
        r_ = by[len(by) // 2]
        width('skirt_width', round(ro[r_][0], 4), round(rd[r_][0], 4),
              "the garment row through the axis between waist and knee on the design's rows free of hands, ours on the "
              "same rows: the row whose ratio is the median (no row is free in both: ours measured there with a hand "
              "against it)")
        C['skirt_width']['z'] = round(float(WIN['top'] - (r_ + 0.5) / D['ppl']), 4)
        C['skirt_width']['rows'] = len(fd)
    else:
        width('skirt_width', g(O, 'skirt', 'width'), g(D, 'skirt', 'width'), 'the widest garment row through the '
              'axis between waist and knee, rows with a hand against it left out (no row free in both)')
    length('hem', g(O, 'skirt', 'hem'), g(D, 'skirt', 'hem'), "the skirt fabric's lowest row; - = ours longer")
    if view in ('front', 'back', 'three_quarter'):
        length('hem_mid', g(O, 'skirt', 'hem_mid'), g(D, 'skirt', 'hem_mid'), 'the hem at the middle')
        width('sleeves', g(O, 'sleeves', 'width'), g(D, 'sleeves', 'width'), 'across both puffs at the shoulders')
    a_o, a_d = aline(O, D['ppl']), aline(D, D['ppl'])
    if a_o is not None and a_d is not None:
        add('skirt_aline', {'value': round(a_o - a_d, 3), 'ours': round(a_o, 3), 'design': round(a_d, 3),
                            'status': _grade('aline', abs(a_o - a_d)),
                            'note': "the skirt's width near its hem over its widest row, ours less the design's: - = ours "
                                    'narrows toward its hem (a bubble) where the design flares (an A-line)'})
    if view == 'profile':
        eo, fo = front_edge(ofg, ocls, D['ppl'], CHEST_BAND)
        ed, fd = front_edge(dfg, dcls, D['ppl'], CHEST_BAND)
        ok = np.isfinite(eo) & np.isfinite(ed)
        if ok.sum() >= 5:
            dd = (eo[ok] - ed[ok]) * fd                          # + = ours further toward the front
            v_ = round(float(-np.mean(dd)), 4)
            add('chest', {'value': v_, 'status': _grade('chest', abs(v_)), 'worst': round(float(-dd.min()), 4),
                          'note': "the chest's front edge (hair left out) against the design's, mean over z %.2f .. %.2f "
                                  'L: + = ours behind (flatter)' % CHEST_BAND})
    if view in ('front', 'back', 'three_quarter') and D.get('axis') is not None:
        wo, wd = waist_skin(ofg, ocls, D['ppl'], D['axis']), waist_skin(dfg, dcls, D['ppl'], D['axis'])
        if wo is not None and wd is not None:
            v_ = round(max(0.0, wo - wd), 4)
            add('waist_skin', {'value': v_, 'status': _grade('waist_skin', v_), 'ours': round(wo, 4),
                               'design': round(wd, 4), 'note': "the share of the waist's rows (z %.1f .. %.1f L), across "
                               "the body, that is skin, beyond the design's: a bare band" % WAIST_BAND})
    if cut is None and view in ('front', 'back'):
        length('leg', g(O, 'leg'), g(D, 'leg'), 'where the legs show under the skirt, to the sole; + = ours longer')
        if D.get('feet') is not None and D.get('axis') is not None:
            lg = legs(ofg, dfg, ocls, dcls, D['ppl'], D['axis'], D['feet'])
            add('leg_gap', {'value': lg['bridge'], 'status': _grade('leg_gap', lg['bridge']), 'rows': lg['bridge_rows'],
                            'apart': lg['apart'], 'note': "L of rows over the lower legs and boots where the design's "
                            'legs stand apart and ours join (a bridge); rows: its span (z top, bottom, L)'})
            her = {'image_left': 'R', 'image_right': 'L'} if view == 'front' else {'image_left': 'L', 'image_right': 'R'}
            for side, (a_, b_) in lg['step'].items():
                d_ = round(max(0.0, a_ - b_), 4)
                add('boot_step_' + her[side], {'value': d_, 'status': _grade('boot_step', d_), 'ours': a_, 'design': b_,
                                          'note': "the boot's outline (its white run) on this side of the image: its "
                                          "largest row-to-row jump of either edge beyond the design's cleaner side's "
                                          "(L): a step where the shaft meets the foot (her side's boot)"})
        if O.get('arms') and D.get('arms'):
            dv = {k: round(O['arms'][k] - D['arms'][k], 1) for k in O['arms'] if k in D['arms']}
            if dv:
                add('arms', {'value': max(dv.values(), key=abs), 'ours': O['arms'], 'design': D['arms'], 'status': 'INFO',
                             'note': "each arm's angle off the vertical, shoulder to hand (degrees); the build pose is "
                                     "not the sheet's, so the skin and silhouette IoUs carry the difference"})
        length('boot', g(O, 'boot'), g(D, 'boot'), "the boot's top to the sole")
    hb = (D.get('hair') or {}).get('bottom')
    if hb is not None and hb < HAIR_SPLIT + 0.12:
        for k in ('iou_hair', 'hair_length', 'hair_width'):
            if k in C:
                C[k]['caution'] = (C[k].get('caution', '') + '; ' if C[k].get('caution') else '') + \
                    "the drawing's hair reaches the hair/dress split (%.2f L): its lowest rows are hair by position" % HAIR_SPLIT
    for k in ('hem', 'skirt_width'):
        if k in C and ((O.get('skirt') or {}).get('clipped') or (D.get('skirt') or {}).get('clipped')):
            C[k]['caution'] = (C[k].get('caution', '') + '; ' if C[k].get('caution') else '') + \
                'garment continues past the band\'s bottom (knee): the lowest row is the band\'s'
    return C


AZ = {'front': 0.0, 'three_quarter': None, 'profile': 90.0, 'back': 180.0}   # None: the sheet's own 3/4 angle


def azimuths(az3):
    return {v: (az3 if a is None else a) for v, a in AZ.items()}


def view_eye(view, f):
    """the sheet pixel a figure's design_views grid is centred on: the eyes' middle (the profile's near eye, the back's
    head axis) at the eye line."""
    if view == 'profile':
        return (f['eyes'][0][0], f['eye_y'])
    if view == 'back':
        return (f['axis_x'], f['eye_y'])
    return (float(np.mean([e[0] for e in f['eyes']])), f['eye_y'])


def design_views(rgb, D, ppl):
    """the sheet's full figures as data on the shared grid, one per view found: {view: dict(cls (classes, lines
    absorbed), raw (lines kept), fg (the figure), rgb (the picture), ppl, eye (the sheet pixel the grid's origin sits on:
    the eyes, the back's head axis at the eye line), cut (L from the eye line where a cut figure's drawing stops, or
    None), win)}. D: sheetqa.detect_figures' result. Cells hold CLASS ids; row r is z = win.top - (r + 0.5) / ppl L."""
    out = {}
    for view in AZ:
        f = D['figures'].get(view)
        if f is None:
            continue
        eye = view_eye(view, f)
        cr = crop(rgb, eye, ppl)
        fg = crop(f['_mask'], eye, ppl, fill=False)
        cls, raw = classes(cr, fg, WIN['top'] * ppl, ppl)
        out[view] = dict(cls=cls, raw=raw, fg=fg, rgb=cr, ppl=ppl, eye=eye, win=dict(WIN),
                         cut=(-f['bottom_L'] + 0.05) if f['partial'] else None)
    return out


def origin(view, az, iris, centre):
    """our z-buffer origin (u, z world) for a view: the eyes' midpoint seen from az (the profile: the near eye from +x;
    the back: the head's centre line), at the eye line. iris: our iris centres (world, one row per eye)."""
    from .faceqa import view as proj
    ez = float(np.mean(iris[:, 2]))
    if view == 'profile':
        P = iris[np.argmax(iris[:, 0])][None]
    elif view == 'back':
        P = np.array([[0.0, centre[1], ez]])
    else:
        P = iris.mean(0)[None]
    u, _, _ = proj(P, az)
    return float(u[0]), ez


def zbuffer_views(meshes, az3, iris, centre, L, ppl, views=AZ):
    """ours z-buffered for each view on the design's grid: meshes [(V world, tris, CLASS per triangle)] ->
    {view: (depth, label)} (faceqa.zbuffer's: label -1 where nothing is)."""
    from .faceqa import zbuffer
    az = azimuths(az3)
    return {v: zbuffer(meshes, az[v], origin(v, az[v], iris, centre), L, 1.0 / ppl, WIN, thin=(CLASS['line'],))
            for v in views}


def ours(label, depth=None):
    """our label image (faceqa.zbuffer's, -1 = nothing) as classes with the lines absorbed, and the figure -> (cls, fg).
    depth is accepted for a caller holding both (unused: the classes are the silhouette's)."""
    fg = label >= 0
    return absorb(np.where(fg, label, 0), fg), fg


def evaluate(labels, design, caution=None):
    """ours against the design, view by view, without Blender: labels {view: label image or (depth, label)} on the
    design's grid (zbuffer_views, or any caller's own z-buffer at the same scale and origin); design: design_views()'s.
    -> (table, checks {view_name: check}, views for picture())."""
    table, C, views = {'views': {}}, {}, []
    for view, dv in design.items():
        if view not in labels:
            continue
        lab = labels[view][1] if isinstance(labels[view], tuple) else labels[view]
        ocls, ofg = ours(lab)
        dcls, dfg = dv['cls'], dv['fg']
        H_, W_ = min(ofg.shape[0], dfg.shape[0]), min(ofg.shape[1], dfg.shape[1])
        ocls, ofg, dcls, dfg = ocls[:H_, :W_], ofg[:H_, :W_], dcls[:H_, :W_], dfg[:H_, :W_]
        cut, ppl = dv['cut'], dv['ppl']
        Mo, Md = measure(ocls, ofg, ppl, view, cut=cut), measure(dcls, dfg, ppl, view, cut=cut)
        cv = caution
        if cut is not None:
            cv = ((cv + '; ') if cv else '') + 'the drawing stops at %.2f L (the figure is cut): compared above it' % cut
        for k, v in compare(Mo, Md, ocls, dcls, ofg, dfg, view, cv).items():
            C['%s_%s' % (view, k)] = v
        for M_ in (Mo, Md):                                  # (the per-row widths are the comparison's, not the report's)
            (M_.get('skirt') or {}).pop('_rows', None)
        table['views'][view] = {'ours': {k: v for k, v in Mo.items() if k != 'ppl'},
                                'design': {k: v for k, v in Md.items() if k != 'ppl'}}
        views.append((view, Mo, Md, ocls, dcls, ofg, dfg))
    return table, C, views


def sheet_views(meshes, rgb, D, ppl, az3, iris, centre, L, caution=None):
    """the whole pass: the design's views (design_views), ours z-buffered on the same grid (zbuffer_views), graded
    (evaluate). -> (table, checks, views)."""
    design = design_views(rgb, D, ppl)
    labels = zbuffer_views(meshes, az3, iris, centre, L, ppl, [v for v in AZ if v in design])
    table, C, views = evaluate(labels, design, caution)
    table.update(ppl=round(ppl, 2), az=azimuths(round(az3, 1)))
    for v in D['figures']:
        if v in AZ and v not in design:
            C[v] = {'status': 'SKIPPED', 'why': 'no %s figure on the sheet' % v}
    for v in AZ:
        if v not in D['figures']:
            C[v] = {'status': 'SKIPPED', 'why': 'no %s figure on the sheet' % v}
    return table, C, views


# ------------------------------------------------------------------------------------------------------------ pictures
PALETTE = {0: (0.97, 0.97, 0.95), 1: (0.98, 0.83, 0.74), 2: (0.85, 0.42, 0.25), 3: (0.95, 0.8, 0.1), 4: (0.2, 0.15, 0.15),
           6: (0.9, 0.55, 0.2), 7: (0.97, 0.9, 0.62), 8: (0.35, 0.25, 0.22), 9: (0.75, 0.8, 0.95), 10: (0.6, 0.2, 0.7)}


def paint(cls):
    im = np.zeros(cls.shape + (3,))
    for c, col in PALETTE.items():
        im[cls == c] = col
    return im


def picture(views, scale=1):
    """per view (a row): the design's classes, ours, the silhouettes (grey both, red ours only, blue the design only) with
    the hair outlined (blue design, red ours), the measured heights as ticks (blue design, red ours: feet, hem, where the
    legs show, boot top, hair bottom) and the skirt's and sleeves' widest rows as lines. views: [(name, O, D, ocls, dcls, ofg, dfg)]."""
    rows = []
    for name, O, D, oc, dc, of, df in views:
        ov = np.full(of.shape + (3,), 0.95)
        ov[of & df] = (0.6, 0.6, 0.64); ov[of & ~df] = (0.92, 0.3, 0.3); ov[df & ~of] = (0.3, 0.45, 0.95)
        for m, col in ((dc == 2, (0.1, 0.2, 0.9)), (oc == 2, (0.9, 0.1, 0.1))):
            edge = m & ~erode(m, 1)
            ov[edge] = col
        H = of.shape[0]
        for M, col, x0 in ((D, (0.1, 0.2, 0.9), 0), (O, (0.9, 0.1, 0.1), 12)):
            for zz in (M.get('feet'), (M.get('skirt') or {}).get('hem'), M.get('leg_top'), M.get('boot_top'),
                       (M.get('hair') or {}).get('bottom')):
                if zz is not None:
                    r = int((WIN['top'] - zz) * M['ppl'])
                    if 0 <= r < H:
                        ov[r, x0:x0 + 10] = col
            for k in ('skirt', 'sleeves'):
                w = M.get(k) or {}
                if 'left' in w:
                    r = int((WIN['top'] - w['z']) * M['ppl'])
                    c0, c1 = (int((WIN['x'] + w[s_]) * M['ppl']) for s_ in ('left', 'right'))
                    if 0 <= r < H:
                        ov[r, max(0, c0):c1 + 1:2] = col
        sep = np.ones((H, 4, 3))
        rows.append(np.concatenate([paint(dc), sep, paint(oc), sep, ov], 1))
    Wm = max(r.shape[1] for r in rows)
    rows = [np.pad(r, ((0, 6), (0, Wm - r.shape[1]), (0, 0)), constant_values=1.0) for r in rows]
    im = np.concatenate(rows, 0)
    return np.repeat(np.repeat(im, scale, 0), scale, 1) if scale > 1 else im
