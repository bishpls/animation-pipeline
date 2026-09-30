"""Detail checks for the midriff and the boots (tool/body round 5, docs/workstreams/garments.md).

Michael's review of round 4 found two faults that no check caught:
- **The midriff** looked sliced and shifted between the bust and the waistband: the top's hem stepped and stopped short
  of the band, the cream panel's bottom was torn, and the band stood out from the top as a separate ring.
- **The boots** looked twisted at the ankle, with a lateral jog. The front scrunch was a jagged spike, and the back had
  none. The soles were uneven and differed left to right, a doubled line ran along the toe, and there was no heel.

Each is measured on the design's grids (bodyqa's: the sheet's scale, aligned on the eyes) against the design's own figure
and drawn piece masks, measured the same way. Where the design has no view, the check is taken in 3D against an
absolute target (the sole from below: flat, and the same on both feet).

Checks (qa3d part 'details'; lengths in L, angles in degrees):
  body_{front,profile}_torso_jump_{L,R | front,back}
        the torso outline's largest row-to-row jump on that side, from under the bust (MID_TOP) to just above the skirt,
        beyond the design's. The edge is the torso pieces' outermost pixel where it is the silhouette (an arm, a
        sleeve or the bow beside it drops the row; a jump is taken across up to 0.03 L of dropped rows)
  body_{front,profile}_midriff_gap
        the top's hem against the waistband per column across the torso: a see-through gap between them (nothing, or
        something behind them), or the top hanging over the band; the larger
  body_front_skirt_overhang_{L,R}, body_front_skirt_overhang_mirror
        the skirt's top against the band, per side: level with the band's lower half, how far the skirt's outermost
        pixel stands past the band's outer edge (a ledge where the skirt juts out sideways; the design's skirt starts
        under the band), beyond the design's on that side; and the two sides' difference beyond the design's (a
        lopsided skirt: Michael's review of round 5, her right jutting out past the band and her left meeting it)
  body_profile_leg_back
        the bare leg's back edge in profile (our skin alone, no garments: the skin's run per row over the design's
        leg, from under its shorts to its boot cuffs; LEG_BAND): its largest outward bump against the design's once
        their median offset is taken out (a pointed bump behind the thigh, Michael's review of round 5: the hull's skin
        at the thigh's top rows ran the whole side run behind the leg, tool/hull-limbs). Bare, because a garment
        hanging against the thigh hides its edge in the dressed figure (the overskirt flaps did, on every build since
        3d0d5f2), and the design draws the leg whole. Calibrated: the design against itself 0; pipeline-3d db718ae's
        thigh (fitted to the hull's slab) 0.108 FAIL at z -2.80; tool/hull-limbs 0.019 PASS
  body_profile_leg_outline
        the dressed figure's outline behind the leg in profile: per row, the leg's skin run followed back through
        whatever touches it (a garment hanging against the thigh), its back end against the design's, the bare leg's
        offset taken out: the largest step outward (L), and how many rows have something against the leg that the
        design keeps clear (tool/skirt's flaps on pipeline-3d db718ae: 0.57 L, 82 of the leg's 242 rows; the design 3).
        Graded by tool/skirt: the step within 0.05 L (WARN 0.10), the hugging rows within 10 of the design's (WARN 30)
  body_front_panel_edge
        the cream panel's lower part above the band: its outline's roughness (how far it strays from its own smoothed
        outline: a staircase or a torn edge) beyond the design's, with its fragments and holes against the design's
  boot_{front,back}_ankle_jog_{L,R}, boot_{front,back}_ankle_bend_{L,R}
        the boot's centreline, with lines fitted to the shaft and the foot: their lateral offset at the ankle, and the
        angle between them, against the design's
  boot_profile_scrunch_{front,back}_{L,R}
        the ankle's fold on that edge in profile: the edge's largest outward bump off its local chord (size, height,
        width) against the design's. It's absent (FAIL) where the design has one; a spike larger than the design's is
        graded by the size difference
  boot_profile_heel_{L,R}
        the heel block in profile, from the dark sole: its height from the ground and its depth, against the design's;
        absent (FAIL) with no raised arch in front of it
  boot_profile_double_{L,R}
        doubled outline strokes on the boot in profile: two line strokes within DOUBLE_GAP of each other across a thin
        strip of surface (two surfaces drawing their outlines an outline's width apart), L of stroke beyond the design's
  boot_sole_flat_{L,R}, boot_sole_twist_{L,R}
        3D: the bottom face (its triangles facing down near its lowest point): their worst distance from their plane;
        the twist is the largest of its front and back halves' roll difference, its long axis' yaw off the foot's
        direction and its tilt off level
  boot_mirror_{front,back}, boot_sole_mirror
        the left boot against the right mirrored about the legs' midline: the front and back views' masks (aligned by
        their centroids) and the soles' outlines from below (in place). IoU; the design's front and back beside it

The profile checks are taken for both boots: the left from +x (the design's profile, az 90) and the right from -x
(az 270, mirrored onto the design's profile), each against the design's near boot.

    table, checks = detailqa.measure(B, design)      # charkit.qa3d's 'details' part
"""
import numpy as np

from . import bodyqa

WIN = bodyqa.WIN
CL = bodyqa.CLASS
MID_TOP = -0.95                     # L from the eye line: the torso band's top (under the bust and the bow's lobes)
PROFILE_FRONT_TOP = -1.22           # ... the profile's front edge's: the drawn bow tails hang free in front of it to -1.21
                                    # (their drawn masks run on down the bodice's front, which they cover in profile)
TORSO_PIECES = ('top', 'bodice_panel', 'waistband')   # the drawn pieces whose pixels are the torso's outline
TORSO_OBJECTS = ('top', 'bodice_panel', 'waistband')   # ours (the bib its own object: garments2)
CANDIDATES = ('top', 'bodice_panel', 'waistband', 'bow', 'bow_tail_L', 'bow_tail_R', 'collar', 'sleeve_L', 'sleeve_R',
              'sleeve_cuff_L', 'sleeve_cuff_R', 'cuff_L', 'cuff_R', 'skirt', 'skirt_panel', 'overskirt_panel_L',
              'overskirt_panel_R')                     # the drawn pieces an edge pixel of the torso band can belong to
LEG_BAND = (-2.6, -4.2)             # L from the eye line: the rows the legs' back edge is looked for in profile
CHORD = 0.08                        # L: half the chord a scrunch's bump is measured against
SCRUNCH_ZONE = (0.30, 0.64)         # fraction of the boot's height from its top: where the ankle's folds are looked for
                                    # (above the heel's top corner, at 0.72 of the design's)
SCRUNCH_MIN = 0.008                 # L: a bump smaller than this is no fold
SHAFT_ROWS = (0.10, 0.42)           # fraction of the boot's height from its top: the shaft's rows (the centreline fit)
FOOT_ROWS = (0.68, 0.90)            # ... the foot's (above the sole)
ANKLE_AT = 0.55                     # ... the ankle's row
DOUBLE_GAP = 0.025                  # L: two strokes this close across a strip of surface are one line drawn twice
STROKE_CLOSE = 0.0025               # L: a stroke's gaps up to twice this are its own (anti-aliasing), not a strip
HEEL_MIN = 0.10                     # L: a heel lower than this over the ground is none
ARCH_MIN = 0.02                     # L: a raised arch's least clearance over the ground
GROUND = 0.04                       # L: a column's lowest row this close to the lowest is on the ground (the drawing's
                                    # heel stands 0.033 L above its toe: a camera a little above)
CONTACT = 0.03                      # L: the underside within this of its lowest point is the ground contact
LIMITS = {                          # (pass within, warn within); else fail
    'torso_jump': (0.01, 0.02),
    'midriff_gap': (0.005, 0.015),
    'panel_edge': (0.01, 0.02),
    'overhang': (0.02, 0.04),
    'leg_back': (0.03, 0.06),
    'leg_outline': (0.05, 0.10),     # (and the rows hugging the leg beyond the design's: 10, 30)
    'ankle_jog': (0.015, 0.03),
    'ankle_bend': (4.0, 8.0),
    'scrunch': (0.012, 0.025),
    'heel': (0.03, 0.06),
    'double': (0.02, 0.05),
    'sole_flat': (0.004, 0.01),
    'sole_twist': (3.0, 6.0),
    'mirror': (0.93, 0.85),         # IoU: higher is better
}


def grade(key, v):
    p, w = LIMITS[key]
    if key == 'mirror':
        return 'PASS' if v >= p else 'WARN' if v >= w else 'FAIL'
    return 'PASS' if v <= p else 'WARN' if v <= w else 'FAIL'


def worst(*ss):
    order = {'FAIL': 0, 'WARN': 1, 'PASS': 2}
    ss = [s for s in ss if s in order]
    return min(ss, key=lambda s: order[s]) if ss else 'SKIPPED'


def rows_z(H, ppl, win=WIN):
    return win['top'] - (np.arange(H) + 0.5) / ppl


def row_of(z, ppl, win=WIN):
    return int(round((win['top'] - z) * ppl - 0.5))


def _run_at(row, c):
    """the run of True in a row holding column c (or the nearest run), -> (a, b) or None."""
    cols = np.nonzero(row)[0]
    if not len(cols):
        return None
    parts = np.split(cols, np.nonzero(np.diff(cols) > 1)[0] + 1)
    for p in parts:
        if p[0] <= c <= p[-1]:
            return p[0], p[-1]
    p = min(parts, key=lambda p: min(abs(p[0] - c), abs(p[-1] - c)))
    return p[0], p[-1]


# ----------------------------------------------------------------------------------------------------------- midriff
def nearest_piece(masks, view, names, box):
    """per pixel of a box (r0, r1, c0, c1) of a view, the drawn piece it belongs to or lies nearest: an index into
    names, -1 where no piece is within reach. The drawn masks leave the lines between pieces out, so an outline pixel
    takes its nearest piece."""
    from scipy import ndimage
    r0, r1, c0, c1 = box
    best = np.full((r1 - r0, c1 - c0), np.inf)
    idx = np.full((r1 - r0, c1 - c0), -1)
    for i, n in enumerate(names):
        m = masks.get('%s__%s' % (view, n))
        if m is None or not m[r0:r1, c0:c1].any():
            continue
        d = ndimage.distance_transform_edt(~m[r0:r1, c0:c1])
        closer = d < best
        best[closer], idx[closer] = d[closer], i
    idx[best > 6] = -1
    return idx


def torso_edges(fg, torso, ppl, z_hi, z_lo, win=WIN):
    """the torso's outline per row from z_hi down to z_lo: its outermost pixels (torso: the torso pieces' pixels) on
    either side, kept where they are the figure's silhouette (the pixel beyond is background: an arm, a sleeve or a bow
    tail beside or in front of the edge drops the row). -> (rows, left, right) columns, NaN where dropped."""
    H, W = fg.shape
    rows = np.arange(max(0, row_of(z_hi, ppl, win)), min(H, row_of(z_lo, ppl, win) + 1))
    left, right = np.full(len(rows), np.nan), np.full(len(rows), np.nan)
    for i, r in enumerate(rows):
        c = np.nonzero(torso[r] & fg[r])[0]
        if not len(c):
            continue
        a, b = c.min(), c.max()
        if a == 0 or not fg[r, a - 1]:
            left[i] = a
        if b == W - 1 or not fg[r, b + 1]:
            right[i] = b
    return rows, left, right


def largest_jump(e, rows, ppl, sign=1, bridge=0.03, win=WIN):
    """an edge's largest steps (px, NaN where not measured) between measured rows at most `bridge` L apart (a step can
    hide behind a dropped row or two), outward and inward (sign: +1 when a larger column is further out, the image's
    right edge; -1 the left). -> dict(out, out_z, inward, in_z) in L (0 when none), or None."""
    idx = np.nonzero(np.isfinite(e))[0]
    k = max(1, int(round(bridge * ppl)))
    best = {'out': (0.0, None), 'inward': (0.0, None)}
    n = 0
    for i, j in zip(idx, idx[1:]):
        if j - i <= k:
            n += 1
            d = sign * (e[j] - e[i])
            key = 'out' if d > 0 else 'inward'
            if abs(d) > best[key][0]:
                best[key] = (abs(d), rows[j])
    if not n:
        return None
    z = lambda r: None if r is None else round(float(win['top'] - (r + 0.5) / ppl), 3)
    return dict(out=round(best['out'][0] / ppl, 4), out_z=z(best['out'][1]), inward=round(best['inward'][0] / ppl, 4),
                in_z=z(best['inward'][1]))


def skirt_top(skirt, centre_c, ppl, half=0.15):
    """the skirt's highest row within `half` L of the centre column, or None."""
    c0, c1 = int(centre_c - half * ppl), int(centre_c + half * ppl)
    r = np.nonzero(skirt[:, max(0, c0):c1 + 1].any(1))[0]
    return int(r.min()) if len(r) else None


def junction(lab, depth, top_ids, band_ids, ppl, L, cols):
    """the top's hem against the band's top edge per column: for each column holding both, the rows between the top's
    lowest pixel and the band's highest where one sees through (nothing, or a surface more than 0.02 L behind the band),
    and the top's rows showing below the band's top (the top over the band). -> dict(gap, over (L, the largest over the
    columns), share (of the columns with a gap), cols (measured))."""
    gaps, overs, n = [], [], 0
    for c in cols:
        col = lab[:, c]
        t = np.nonzero(np.isin(col, top_ids))[0]
        b = np.nonzero(np.isin(col, band_ids))[0]
        if not len(t) or not len(b):
            continue
        bt = b.min()
        tt = t[t < bt]
        if not len(tt):
            continue
        n += 1
        t_low = tt.max()
        ref = depth[bt, c]
        between = np.arange(t_low + 1, bt)
        see = [r for r in between if col[r] < 0 or depth[r, c] > ref + 0.02 * L]
        gaps.append(len(see))
        overs.append(int((t > bt).sum()))
    if not n:
        return None
    gaps, overs = np.array(gaps), np.array(overs)
    return dict(gap=round(float(gaps.max()) / ppl, 4), over=round(float(overs.max()) / ppl, 4),
                share=round(float((gaps > 0).mean()), 3), cols=n)


def outline_roughness(m, ppl, sigma=0.01):
    """how far a mask's outline strays from its smoothed self (the mask blurred by `sigma` L and cut at a half): the
    95th percentile of its outline pixels' distance to the smoothed outline, L. A staircase or a torn edge strays; a
    clean curve doesn't."""
    from scipy import ndimage
    if not m.any():
        return None
    sm = ndimage.gaussian_filter(m.astype(float), sigma * ppl) > 0.5
    a = m & ~ndimage.binary_erosion(m)
    b = sm & ~ndimage.binary_erosion(sm)
    if not b.any():
        return None
    d = ndimage.distance_transform_edt(~b)
    return round(float(np.percentile(d[a], 95)) / ppl, 4)


def fragments(m, min_share=0.02):
    """a mask's pieces: its connected parts smaller than min_share of the largest (fragments) and the holes inside it
    (components of the rest it encloses, of 3 px or more). -> (fragments, holes)."""
    from scipy import ndimage
    lab, n = ndimage.label(m, structure=np.ones((3, 3)))
    if not n:
        return 0, 0
    sz = np.bincount(lab.ravel())[1:]
    frag = int((sz < min_share * sz.max()).sum())
    holes = ndimage.binary_fill_holes(m) & ~m
    hl, hn = ndimage.label(holes)
    hs = np.bincount(hl.ravel())[1:] if hn else np.zeros(0)
    return frag, int((hs >= 3).sum())


# ----------------------------------------------------------------------------------------------------------- boots
def boot_rows(M, cuff=None):
    """a boot's mask with its cuff taken off: the rows from the cuff's lowest row (in the boot's columns) + 2 down to its
    lowest. -> (M, top row, bottom row) or None."""
    M = M.copy()
    if cuff is not None:
        cols = np.nonzero(M.any(0))[0]
        if len(cols):
            cr = np.nonzero(cuff[:, cols.min():cols.max() + 1].any(1))[0]
            if len(cr):
                M[:cr.max() + 3] = False
    r = np.nonzero(M.any(1))[0]
    if len(r) < 20:
        return None
    return M, int(r.min()), int(r.max())


def edges(M, r0, r1):
    """per row r0..r1 the mask's leftmost and rightmost columns (NaN where empty)."""
    rows = np.arange(r0, r1 + 1)
    lo, hi = np.full(len(rows), np.nan), np.full(len(rows), np.nan)
    for i, r in enumerate(rows):
        c = np.nonzero(M[r])[0]
        if len(c):
            lo[i], hi[i] = c.min(), c.max()
    return rows, lo, hi


def _fit(rows, x, a, b, n):
    """a line x = p0 + p1 * row fitted on the rows between fractions a and b of n."""
    i0, i1 = int(a * n), max(int(a * n) + 3, int(b * n))
    s = slice(i0, i1)
    ok = np.isfinite(x[s])
    if ok.sum() < 3:
        return None
    return np.polyfit(rows[s][ok].astype(float), x[s][ok], 1)


def ankle(M, top, bot, ppl):
    """front or back view: the boot's centreline (the middle of its extent per row) with a line fitted to the shaft's
    rows and one to the foot's: their lateral offset at the ankle's row and the angle between them.
    -> dict(jog (L), bend (deg), ankle_z_frac)."""
    rows, lo, hi = edges(M, top, bot)
    mid = (lo + hi) / 2
    n = len(rows)
    ps, pf = _fit(rows, mid, *SHAFT_ROWS, n), _fit(rows, mid, *FOOT_ROWS, n)
    if ps is None or pf is None:
        return None
    ra = rows[int(ANKLE_AT * n)]
    jog = (np.polyval(pf, ra) - np.polyval(ps, ra)) / ppl
    bend = np.degrees(np.arctan(ps[0]) - np.arctan(pf[0]))
    return dict(jog=round(float(jog), 4), bend=round(float(bend), 2))


def facing(M, top, bot):
    """+1 when the boot's toe points to the image's right (the foot's rows reach further right than the shaft's)."""
    rows, lo, hi = edges(M, top, bot)
    n = len(rows)
    sh = np.nanmean((lo + hi)[int(0.1 * n):int(0.4 * n)] / 2)
    ft = np.nanmean((lo + hi)[int(0.85 * n):] / 2)
    return 1 if ft > sh else -1


def scrunch(M, top, bot, ppl, side):
    """profile: the ankle's fold on one edge ('front': the toe's side; 'back'): the edge measured outward, its bump off
    the chord CHORD L either side, largest over SCRUNCH_ZONE of the boot's height. -> dict(size (L), at (fraction of
    the height from the top), z (L above the sole), width (L, where the bump is over half its size), present)."""
    rows, lo, hi = edges(M, top, bot)
    f = facing(M, top, bot)
    toe_right = f > 0
    e = hi if (side == 'front') == toe_right else lo
    out = e if (side == 'front') == toe_right else -e          # larger = further out on that edge
    n = len(rows)
    w = max(2, int(round(CHORD * ppl)))
    prom = np.full(n, np.nan)
    for i in range(int(SCRUNCH_ZONE[0] * n), int(SCRUNCH_ZONE[1] * n)):
        if i - w < 0 or i + w >= n or not np.isfinite(out[[i - w, i, i + w]]).all():
            continue
        prom[i] = out[i] - (out[i - w] + out[i + w]) / 2
    if not np.isfinite(prom).any():
        return None
    i = int(np.nanargmax(prom))
    size = float(prom[i]) / ppl
    half = prom >= 0.5 * prom[i]
    j0 = i
    while j0 > 0 and half[j0 - 1]:
        j0 -= 1
    j1 = i
    while j1 < n - 1 and half[j1 + 1]:
        j1 += 1
    return dict(size=round(size, 4), at=round(i / n, 3), z=round((bot - rows[i]) / ppl, 4),
                width=round((j1 - j0 + 1) / ppl, 4), present=bool(size >= SCRUNCH_MIN))


def heel(M, dark, top, bot, ppl, low=0.35):
    """profile: the heel block from the dark sole: per column of the boot's lower `low` L, its lowest row and the dark
    run up from its lowest dark pixel (within 3 px of it: the drawing's outline under the sole isn't dark). The ground
    is the lowest row; the heel is the back half's columns on the ground (away from the toe) whose dark run stands
    HEEL_MIN or more; the arch is the columns between it and the forefoot raised ARCH_MIN or more.
    -> dict(height, depth, arch (L), present)."""
    f = facing(M, top, bot)
    r_low = max(top, bot - int(low * ppl))
    cols = np.nonzero(M[r_low:bot + 1].any(0))[0]
    if not len(cols):
        return None
    lows = np.full(M.shape[1], -1)
    run = np.zeros(M.shape[1])
    for c in cols:
        r = np.nonzero(M[:bot + 1, c])[0]
        b = r.max()
        lows[c] = b
        k0 = b
        while k0 > b - 3 and not dark[k0, c]:
            k0 -= 1
        if not dark[k0, c]:
            continue
        k = k0
        while k >= top and dark[k, c]:
            k -= 1
        run[c] = b - k
    g = lows[cols].max()
    contact = cols[lows[cols] >= g - GROUND * ppl]
    lift = (g - lows) / ppl
    toe_c = cols.max() if f > 0 else cols.min()
    back_c = cols.min() if f > 0 else cols.max()
    span = abs(toe_c - back_c)
    back = [c for c in contact if abs(c - back_c) < 0.5 * span]
    hh = max((run[c] for c in back), default=0) / ppl
    heel_cols = [c for c in back if run[c] / ppl >= max(HEEL_MIN, 0.5 * hh)]
    if hh < HEEL_MIN or not heel_cols:
        mid = [c for c in cols if 0.3 * span < abs(c - back_c) < 0.7 * span]
        return dict(height=round(hh, 4), depth=0.0, arch=round(float(lift[mid].max()) if mid else 0.0, 4),
                    present=False)
    depth = (max(heel_cols) - min(heel_cols) + 1) / ppl
    front_edge = min(heel_cols, key=lambda c: abs(c - toe_c))
    between = [c for c in cols if (c - front_edge) * (toe_c - front_edge) > 0 and abs(c - front_edge) < 0.6 * span]
    arch = float(lift[between].max()) if between else 0.0
    return dict(height=round(hh, 4), depth=round(depth, 4), arch=round(arch, 4), present=bool(arch >= ARCH_MIN + GROUND))


def doubled(lines, fg, ppl, gap=DOUBLE_GAP, where=False):
    """two line strokes within `gap` L of each other across a strip of surface (not background), counted along rows and
    columns: each crossing of such a pair is one pixel of doubled stroke. The strokes are closed over STROKE_CLOSE L
    first (a drawn stroke's anti-aliased speckle is one stroke). -> L of doubled stroke (the larger scan); with
    where=True also the pixels either side of each crossing."""
    from scipy import ndimage
    g = max(1, int(round(gap * ppl)))
    k = max(1, int(round(STROKE_CLOSE * ppl)))
    lines = ndimage.binary_closing(lines, iterations=k, border_value=0) | lines
    hit = np.zeros(lines.shape, bool)

    def scan(Lm, F, H):
        hits = 0
        for r in range(Lm.shape[0]):
            c = np.nonzero(Lm[r])[0]
            if len(c) < 2:
                continue
            parts = np.split(c, np.nonzero(np.diff(c) > 1)[0] + 1)
            for a, b in zip(parts, parts[1:]):
                s0, s1 = a[-1] + 1, b[0]
                if 0 < s1 - s0 <= g and F[r, s0:s1].all():
                    hits += 1
                    H[r, a[-1]] = H[r, b[0]] = True
        return hits
    n = max(scan(lines, fg, hit), scan(lines.T, fg.T, hit.T))
    v = round(n / ppl, 4)
    return (v, hit) if where else v


# ------------------------------------------------------------------------------------------------------------ 3D soles
def underside(V, T, cell, box=None):
    """the lowest surface height per xy cell (a z-buffer looking up) over the mesh's extent, or `box` (x0, x1, y0, y1)
    -> (z (ny, nx) NaN where none, x0, y0)."""
    from .geom import raster
    P = np.stack([V[:, 0], V[:, 2], V[:, 1]], 1)          # (x, z, y): az 0 sees x across, y up, depth = height
    if box is None:
        box = (P[:, 0].min() - cell, P[:, 0].max() + cell, P[:, 2].min() - cell, P[:, 2].max() + cell)
    x0, x1, y0, y1 = box
    win = dict(x=(x1 - x0) / 2, top=(y1 - y0) / 2, bottom=-(y1 - y0) / 2)
    org = ((x0 + x1) / 2, (y0 + y1) / 2)
    z, lab = raster.window_zbuffer([(P, T, 0)], 0, org, 1.0, cell, win)
    z = np.where(lab >= 0, z, np.nan)[::-1]                # row 0 = y0
    return z, x0, y0


def sole(V, T, L, fwd, down=0.985):
    """a boot's bottom face: its triangles facing down (normal within 10 degrees of straight down: the arch's slope and
    the subdivision's rounded rim are out) within CONTACT of its lowest point, area-weighted. The worst distance of
    their centres from their fitted plane (flat); that plane's tilt off level; the roll of its front and back halves
    (about the foot's axis `fwd`, xy); its long axis' yaw off `fwd`; twist the largest of the roll difference, the yaw
    and the tilt. -> dict(flat (L), tilt, roll_front, roll_back, yaw, twist (deg), faces) or None."""
    V, T = np.asarray(V, float), np.asarray(T)
    N = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    area = 0.5 * np.linalg.norm(N, axis=1)
    N = N / np.maximum(2 * area, 1e-18)[:, None]
    C = V[T].mean(1)
    sel = (N[:, 2] < -down) & (C[:, 2] < V[:, 2].min() + CONTACT * L) & (area > 0)
    if sel.sum() < 2:
        return None
    X, Y, Z, w = C[sel, 0], C[sel, 1], C[sel, 2], area[sel]
    sw = np.sqrt(w)

    def plane(m):
        A = np.stack([X[m], Y[m], np.ones(m.sum())], 1)
        return np.linalg.lstsq(A * sw[m, None], Z[m] * sw[m], rcond=None)[0]
    allm = np.ones(len(X), bool)
    p = plane(allm)
    flat = float(np.abs(Z - (p[0] * X + p[1] * Y + p[2])).max()) / L
    tilt = float(np.degrees(np.arctan(np.hypot(p[0], p[1]))))
    f = np.asarray(fwd, float)[:2]
    f = f / np.linalg.norm(f)
    lat = np.array([-f[1], f[0]])
    uu, vv = np.stack([X, Y], 1) @ f, np.stack([X, Y], 1) @ lat
    mid = np.average(uu, weights=w)

    def roll(m):
        if m.sum() < 3 or np.ptp(vv[m]) < 0.03 * L:
            return np.nan
        q = plane(m)
        return float(np.degrees(np.arctan(q[0] * lat[0] + q[1] * lat[1])))
    rf, rb = roll(uu > mid), roll(uu <= mid)
    Q = np.stack([X, Y], 1) - np.average(np.stack([X, Y], 1), axis=0, weights=w)
    _, vec = np.linalg.eigh((Q * w[:, None]).T @ Q)
    yaw = float(np.degrees(np.arccos(min(1.0, abs(vec[:, -1] @ f)))))
    tw = max(abs(rf - rb) if np.isfinite(rf) and np.isfinite(rb) else 0.0, yaw, tilt)
    return dict(flat=round(flat, 4), tilt=round(tilt, 2), roll_front=round(rf, 2), roll_back=round(rb, 2),
                yaw=round(yaw, 2), twist=round(tw, 2), faces=int(sel.sum()))


def mirror_iou(a, b, align=True):
    """IoU of mask a against mask b mirrored left to right (both on one grid, b already mirrored about the midline
    when align is False); align=True shifts b's mirror so the centroids meet."""
    bm = b[:, ::-1] if align else b
    if align:
        ca = np.nonzero(a.any(0))[0]
        cb = np.nonzero(bm.any(0))[0]
        if not len(ca) or not len(cb):
            return None
        sx = int(round(np.nonzero(a)[1].mean() - np.nonzero(bm)[1].mean()))
        sy = int(round(np.nonzero(a)[0].mean() - np.nonzero(bm)[0].mean()))
        bm = np.roll(np.roll(bm, sx, 1), sy, 0)
    u = (a | bm).sum()
    return round(float((a & bm).sum() / u), 4) if u else None


def footprints_mirror(Va, Ta, Vb, Tb, mid, L, cell=0.01):
    """the left sole's footprint (its underside seen from below) against the right's mirrored about x = mid, in place,
    both drawn on one grid. -> IoU."""
    Vm = Vb.copy()
    Vm[:, 0] = 2 * mid - Vm[:, 0]
    c = cell * L
    both = np.concatenate([Va, Vm])
    box = (both[:, 0].min() - c, both[:, 0].max() + c, both[:, 1].min() - c, both[:, 1].max() + c)
    A = np.isfinite(underside(Va, Ta, c, box)[0])
    B = np.isfinite(underside(Vm, Tb[:, ::-1], c, box)[0])
    u = (A | B).sum()
    return round(float((A & B).sum() / u), 4) if u else None


# ------------------------------------------------------------------------------------------------------------ measuring
class _Window:
    """an orthographic window centred on a world point seen from az (a Frame for qa3d.draw_view)."""

    def __init__(self, c, az, hx, hz, pix):
        from .faceqa import view
        u, _, _ = view(np.asarray([c], float), az)
        self.pix = pix
        self.win = dict(x=hx, top=hz, bottom=-hz)
        self.origin = (float(u[0]), float(c[2]))

    def zbuffer(self, items, az, ids=False):
        from .geom import raster
        return raster.window_zbuffer(items, az, self.origin, 1.0, self.pix, self.win, ids=ids)


def bare_skin(B):
    """the skin alone, whole (its 'eval' variant: no garments' mask), every triangle skin -> (V, T, labels) or None."""
    try:
        sk = B.skin()
    except StopIteration:
        return None
    if not sk.has('eval'):
        return None
    V, T = sk.mesh('eval')[:2]
    return V, T, np.full(len(T), CL['skin'])


def our_views(B, ppl, az3):
    """ours on the design's grids: per view (front, profile, back, and profile_R: the profile from -x, mirrored onto
    the design's profile) the object labels (index into names; + 1000 for a two-sided object's right half), their
    depth and the classes (lines absorbed); the profile also the bare skin's classes (bare_skin: 'bare').
    -> ({view: dict(lab, depth, cls, fg[, bare])}, names)."""
    from . import qa3d
    from .faceqa import zbuffer, view as proj
    meshes, names = qa3d.scene_objects(B)
    obj = [(V, T, np.where(V[T].mean(1)[:, 0] >= 0, i, i + 1000)) for i, (V, T, _) in enumerate(meshes)]
    As = B.assembly
    iw = np.array(qa3d.iris_centres(B))
    az = bodyqa.azimuths(az3)
    az['profile_R'] = 270.0
    out = {}
    for v in ('front', 'profile', 'back', 'profile_R'):
        if v == 'profile_R':
            P = iw[np.argmin(iw[:, 0])][None]
            org = (float(proj(P, 270.0)[0][0]), float(np.mean(iw[:, 2])))
        else:
            org = bodyqa.origin(v, az[v], iw, As['centre'])
        depth, lab = zbuffer(obj, az[v], org, As['L'], 1.0 / ppl, WIN)
        _, cl = zbuffer(meshes, az[v], org, As['L'], 1.0 / ppl, WIN, thin=(CL['line'],))
        cls, fg = bodyqa.ours(cl)
        if v == 'profile_R':
            depth, lab, cls, fg = depth[:, ::-1], lab[:, ::-1], cls[:, ::-1], fg[:, ::-1]
        out[v] = dict(lab=lab, depth=depth, cls=cls, fg=fg, az=az[v], org=org)
        if v == 'profile':
            bare = bare_skin(B)
            if bare is not None:
                out[v]['bare'] = bodyqa.ours(zbuffer([bare], az[v], org, As['L'], 1.0 / ppl, WIN)[1])[0]
    return out, names


def _members(lab, idx, members):
    from .bodymeasure import member_mask
    return member_mask(lab, idx, members)


def _torso(O, D, masks, view, ppl, idx, pm):
    """the torso outline and junction for one view, ours and the design's."""
    H, W = D['fg'].shape
    res = {}
    # in profile the bow's tails hang in front of the torso: its front edge is taken below PROFILE_FRONT_TOP in both
    front_top = PROFILE_FRONT_TOP if view == 'profile' else MID_TOP
    for who in ('ours', 'design'):
        if who == 'ours':
            lab = O['lab']
            torso = _members(lab, idx, [m for p in TORSO_OBJECTS for m in pm.get(p, [])])
            band = _members(lab, idx, pm.get('waistband', []))
            skirt = _members(lab, idx, pm.get('skirt', []))
            fg = O['fg']
        else:
            band = masks.get('%s__waistband' % view)
            sk = [masks.get('%s__%s' % (view, p)) for p in ('skirt', 'skirt_panel')]
            skirt = np.logical_or.reduce([m for m in sk if m is not None])
            fg = D['fg']
            r0, r1 = max(0, row_of(MID_TOP + 0.1, ppl)), min(H, row_of(-1.9, ppl))
            near = nearest_piece(masks, view, CANDIDATES, (r0, r1, 0, W))
            torso = np.zeros((H, W), bool)
            torso[r0:r1] = np.isin(near, [CANDIDATES.index(p) for p in TORSO_PIECES])
            torso &= D['cls'] != CL['skin']
        if band is None or not band.any():
            return None
        bc = np.nonzero(band)[1]
        centre = int(np.median(bc))
        st = skirt_top(skirt, centre, ppl)
        z_lo = (WIN['top'] - (st - 2 + 0.5) / ppl) if st is not None else -1.4
        rows, lo, hi = torso_edges(fg, torso, ppl, MID_TOP, z_lo)
        lo[WIN['top'] - (rows + 0.5) / ppl > front_top] = np.nan          # (the profile's front: the image's left)
        res[who] = dict(left=largest_jump(lo, rows, ppl, -1), right=largest_jump(hi, rows, ppl, 1),
                        z_lo=round(float(z_lo), 3), left_top=round(front_top, 3),
                        rows=[int(np.isfinite(lo).sum()), int(np.isfinite(hi).sum())])
    return res


def measure(B, design, out=None):
    """the details' checks on a bundle against the design (qa3d.Design) -> (table, checks)."""
    from . import bodymeasure, qa3d
    ctx = design.sheet_context()
    if 'why' in ctx:
        return None, {'details': {'status': 'SKIPPED', 'why': ctx['why']}}
    got = bodymeasure.piece_masks(B.spec)
    if got is None:
        return None, {'details': {'status': 'SKIPPED', 'why': 'no outfit_masks produced for this spec'}}
    masks, graph, paths = got
    for p in paths:
        design._rec(p)
    ppl = ctx['ppl']
    dv = design.design_views()
    O, names = our_views(B, ppl, ctx['az3'])
    idx = {n: i for i, n in enumerate(names)}
    pm = bodymeasure.piece_map(graph, B.spec)
    L = float(B.assembly['L'])
    C, T = {}, {}

    # ---- the midriff
    for view in ('front', 'profile'):
        if view not in dv:
            continue
        r = _torso(O[view], dv[view], masks, view, ppl, idx, pm)
        if not r or 'ours' not in r or 'design' not in r:
            continue
        T['torso_' + view] = r
        sides = (('left', 'R'), ('right', 'L')) if view == 'front' else (('left', 'front'), ('right', 'back'))
        for k, nm in sides:
            a, b = r['ours'][k], r['design'][k]
            if a is None or b is None:
                continue
            v_ = round(max(0.0, a['out'] - b['out'], a['inward'] - b['inward']), 4)
            C['body_%s_torso_jump_%s' % (view, nm)] = {
                'value': v_, 'status': grade('torso_jump', v_), 'ours': a, 'design': b,
                'note': "the torso outline's largest step on this side (the image's %s) from z %.2f down to just above "
                        "the skirt, outward and inward (L, the lower row further out or in), each beyond the design's: "
                        "a step between the top and the band" % (k, MID_TOP if (view, k) != ('profile', 'left') else
                                                                   PROFILE_FRONT_TOP)}
        lab = O[view]['lab']
        top_ids = [idx[n] + s for n in ('top', 'bodice_panel') if n in idx for s in (0, 1000)]
        band_ids = [idx[n] + s for n in ('waistband',) if n in idx for s in (0, 1000)]
        bc = np.nonzero(np.isin(lab, band_ids))[1]
        if len(bc) and top_ids:
            c0, c1 = np.percentile(bc, [5, 95]).astype(int)
            j = junction(lab, O[view]['depth'], top_ids, band_ids, ppl, L, range(c0, c1 + 1))
            if j:
                v_ = max(j['gap'], j['over'])
                C['body_%s_midriff_gap' % view] = dict(j, value=v_, status=grade('midriff_gap', v_),
                                                       note="the top's hem against the band's top per column: the "
                                                            "largest see-through gap or the top over the band (L)")
    if 'front' in dv:
        pe = panel_edge(O['front'], dv['front'], masks, ppl, idx, pm)
        if pe:
            T['panel_edge'] = pe
            a, b = pe['ours'], pe['design']
            v_ = round(max(0.0, a['rough'] - b['rough']), 4)
            df, dh = a['fragments'] - b['fragments'], a['holes'] - b['holes']
            st_f = 'PASS' if df <= 0 and dh <= 0 else 'WARN' if df + dh <= 2 else 'FAIL'
            C['body_front_panel_edge'] = {'value': v_, 'status': worst(grade('panel_edge', v_), st_f), 'ours': a,
                                          'design': b, 'note': "the cream panel's lower %.2f L above the band: its "
                                          "outline's roughness (the 95th percentile of its distance to its own smoothed "
                                          "outline) beyond the design's (L); its fragments and holes against the "
                                          "design's (a torn or stepped edge)" % 0.25}

    if 'front' in dv:
        sk = [masks.get('front__' + p) for p in ('skirt', 'skirt_panel')]
        dsk = np.logical_or.reduce([m for m in sk if m is not None]) if any(m is not None for m in sk) else None
        a = skirt_overhang(_members(O['front']['lab'], idx, pm.get('waistband', [])),
                           _members(O['front']['lab'], idx, [m for p in ('skirt', 'skirt_panel') for m in pm.get(p, [])]),
                           ppl)
        b = skirt_overhang(masks.get('front__waistband'), dsk, ppl)
        if a and b:
            T['skirt_overhang'] = dict(ours=a, design=b)
            C.update(overhang_checks(a, b))

    if 'profile' in dv:
        lb = leg_back_check(O['profile'].get('bare', O['profile']['cls']), dv['profile']['cls'], ppl)
        if lb:
            C['body_profile_leg_back'] = lb
            lo = leg_outline_check(O['profile']['cls'], dv['profile']['cls'], ppl, offset=lb['offset'])
            if lo:
                C['body_profile_leg_outline'] = lo

    # ---- the boots, per view
    boots = {}
    for side in ('L', 'R'):
        pid = 'boot_' + side
        if pid not in pm:
            continue
        for view in ('front', 'back', 'profile'):
            ov = view if not (view == 'profile' and side == 'R') else 'profile_R'
            if view not in dv:
                continue
            M = _members(O[ov]['lab'], idx, pm[pid])
            cuff = _members(O[ov]['lab'], idx, pm.get('boot_cuff_' + side, []))
            dside = side if view != 'profile' else 'L'          # the design's near boot in profile
            Md = masks.get('%s__boot_%s' % (view, dside))
            cd = masks.get('%s__boot_cuff_%s' % (view, dside))
            bo, bd = boot_rows(M, cuff), boot_rows(Md, cd) if Md is not None else None
            boots[(side, view)] = (bo, bd)
            if bo is None or bd is None:
                continue
            if view in ('front', 'back'):
                a, b = ankle(*bo, ppl), ankle(*bd, ppl)
                if a and b:
                    dj, db = round(abs(a['jog'] - b['jog']), 4), round(abs(a['bend'] - b['bend']), 2)
                    C['boot_%s_ankle_jog_%s' % (view, side)] = {
                        'value': dj, 'status': grade('ankle_jog', dj), 'ours': a['jog'], 'design': b['jog'],
                        'note': "the lateral offset (L) at the ankle between lines fitted to the boot's centreline on "
                                "the shaft and on the foot, against the design's"}
                    C['boot_%s_ankle_bend_%s' % (view, side)] = {
                        'value': db, 'status': grade('ankle_bend', db), 'ours': a['bend'], 'design': b['bend'],
                        'note': 'the angle (deg) between the shaft and foot centrelines, against the design\'s'}
            else:
                dk_o = O[ov]['cls'] == CL['dark']
                dk_d = dv[view]['cls'] == CL['dark']
                a, b = heel(bo[0], dk_o, bo[1], bo[2], ppl), heel(bd[0], dk_d, bd[1], bd[2], ppl)
                if a and b:
                    v_ = round(max(abs(a['height'] - b['height']), abs(a['depth'] - b['depth'])), 4)
                    st = grade('heel', v_)
                    if b['present'] and not a['present']:
                        st = 'FAIL'
                    C['boot_profile_heel_%s' % side] = {
                        'value': v_, 'status': st, 'ours': a, 'design': b,
                        'note': 'the heel block in profile (from the dark sole): its height over the ground and its '
                                "depth (L) against the design's, the larger difference; absent (no raised arch in "
                                'front of it) fails'}
    # the render's profile of each boot: its doubled strokes, and its scrunches (a fold thinner than the grid's pixel
    # still draws, with its outline, in the boards)
    for side in ('L', 'R'):
        if 'boot_' + side not in pm or 'profile' not in dv:
            continue
        try:
            R = profile_render(B, pm['boot_' + side], pm.get('boot_cuff_' + side, []), ppl, 90.0 if side == 'L' else 270.0,
                               others=pm.get('boot_' + ('R' if side == 'L' else 'L'), []))
        except Exception as e:                               # (a render fault leaves the others standing)
            C['boot_profile_double_' + side] = {'status': 'SKIPPED', 'why': '%s: %s' % (type(e).__name__, e)}
            continue
        if R is None:
            continue
        if side == 'R':                                      # (onto the design's profile: the toe to the image's left)
            R = {k: (v[:, ::-1] if isinstance(v, np.ndarray) else v) for k, v in R.items()}
        a = doubled(R['lines'] & R['region'], R['fg'], R['ppl'])
        Md, cd = masks.get('profile__boot_L'), masks.get('profile__boot_cuff_L')
        b = double_design(dv['profile'], Md, cd, ppl) if Md is not None else None
        C['boot_profile_double_' + side] = {
            'value': a, 'status': grade('double', a), 'design': b,
            'note': 'doubled outline strokes on the boot in profile, as drawn: two strokes within %.3f L across a '
                    'strip of surface (L of stroke, the larger of the row and column scans); the design\'s drawn lines '
                    'measured the same way beside it' % DOUBLE_GAP}
        bo, bd = boot_rows(R['boot'], R['cuff']), (boot_rows(Md, cd) if Md is not None else None)
        if bo is None or bd is None:
            continue
        for edge in ('front', 'back'):
            a, b = scrunch(*bo, R['ppl'], edge), scrunch(*bd, ppl, edge)
            if not a or not b:
                continue
            v_ = round(abs(a['size'] - b['size']), 4)
            st = grade('scrunch', v_)
            if b['present'] and not a['present']:
                st = 'FAIL'
            C['boot_profile_scrunch_%s_%s' % (edge, side)] = {
                'value': v_, 'status': st, 'ours': a, 'design': b,
                'note': "the ankle's fold on the %s edge in profile (ours as drawn, outline included, with the far boot "
                        "where it shows past the near one): the edge's "
                        "largest bump off its chord (size L, at: fraction of the boot's height from its top, width "
                        "L), against the design's; absent where the design has one fails" % edge}

    # mirror symmetry in front and back (2D)
    for view in ('front', 'back'):
        a, b = boots.get(('L', view)), boots.get(('R', view))
        if not a or not b or a[0] is None or b[0] is None:
            continue
        io = mirror_iou(a[0][0], b[0][0])
        idd = mirror_iou(a[1][0], b[1][0]) if a[1] is not None and b[1] is not None else None
        if io is not None:
            C['boot_mirror_' + view] = {'value': io, 'status': grade('mirror', io), 'design': idd,
                                        'note': "the left boot's mask against the right's mirrored (centroids "
                                                "aligned), IoU; the design's own beside it"}
    # the soles in 3D
    S3 = {}
    for side in ('L', 'R'):
        pid = 'boot_' + side
        if pid not in pm:
            continue
        V, Tt = boot_mesh(B, pm[pid])
        if V is None:
            continue
        s = sole(V, Tt, L, (0.0, -1.0))
        if s is None:
            continue
        S3[side] = (s, V, Tt)
        C['boot_sole_flat_' + side] = {'value': s['flat'], 'status': grade('sole_flat', s['flat']),
                                       'tilt': s['tilt'], 'faces': s['faces'],
                                       'note': "the bottom face (its triangles facing down within 10 degrees, within %.2f "
                                               'L of its lowest point): their worst distance from their plane (L)' % CONTACT}
        C['boot_sole_twist_' + side] = {'value': s['twist'], 'status': grade('sole_twist', s['twist']),
                                        'roll_front': s['roll_front'], 'roll_back': s['roll_back'], 'yaw': s['yaw'],
                                        'tilt': s['tilt'],
                                        'note': "the bottom face's twist (deg): the largest of its front and back halves' "
                                                "roll difference, its long axis' yaw off the foot's direction and its "
                                                'tilt off level'}
    if 'L' in S3 and 'R' in S3:
        top = lambda V: V[V[:, 2] > V[:, 2].max() - 0.05 * L]
        mid = float((top(S3['L'][1])[:, 0].mean() + top(S3['R'][1])[:, 0].mean()) / 2)
        io = footprints_mirror(S3['L'][1], S3['L'][2], S3['R'][1], S3['R'][2], mid, L)
        if io is not None:
            C['boot_sole_mirror'] = {'value': io, 'status': grade('mirror', io), 'mid': round(mid / L, 4),
                                     'note': "the soles' outlines from below, the left against the right mirrored "
                                             "about the boots' shafts' midline (x %.4f L), in place: IoU" % (mid / L)}
    T['boots'] = {'%s_%s' % k: None if v[0] is None else dict(top=v[0][1], bottom=v[0][2]) for k, v in boots.items()}
    return T, C


def skirt_overhang(band, skirt, ppl):
    """the skirt's top beside the band per side of the image: the band's outer edge (its outermost pixel per row over its
    lower half, the median), and over those rows down to the band's lowest row at that edge, the skirt's outermost pixel
    past it (L, 0 when the skirt stays inside: it starts under the band): a ledge, the skirt jutting out sideways level
    with the band. -> dict(left, right, rows (z top, bottom)) or None."""
    if band is None or skirt is None or not band.any() or not skirt.any():
        return None
    rows = np.nonzero(band.any(1))[0]
    low = rows[rows >= rows.max() - (rows.max() - rows.min()) // 2]
    out = {}
    for side, sgn in (('left', -1), ('right', 1)):
        e = [(np.nonzero(band[r])[0].min() if sgn < 0 else np.nonzero(band[r])[0].max()) for r in low]
        edge = float(np.median(e))
        near = np.abs(np.arange(band.shape[1]) - edge) <= 0.1 * ppl
        rb = int(np.nonzero(band[:, near].any(1))[0].max())
        best = 0.0
        for r in range(int(low.min()), rb + 1):
            c = np.nonzero(skirt[r])[0]
            if len(c):
                best = max(best, sgn * ((c.min() if sgn < 0 else c.max()) - edge) / ppl)
        out[side] = round(float(best), 4)
        out.setdefault('rows', [round(float(WIN['top'] - (int(low.min()) + 0.5) / ppl), 3)]).append(
            round(float(WIN['top'] - (rb + 0.5) / ppl), 3))
    return out


def overhang_checks(ours, design):
    """skirt_overhang's for ours and the design's front view -> the checks (the image's left is her right)."""
    if not ours or not design:
        return {}
    C = {}
    for side, her in (('left', 'R'), ('right', 'L')):
        v_ = round(max(0.0, ours[side] - design[side]), 4)
        C['body_front_skirt_overhang_' + her] = {
            'value': v_, 'status': grade('overhang', v_), 'ours': ours[side], 'design': design[side],
            'note': "the skirt's top against the band on her %s side (the image's %s): how far the skirt stands past the "
                    "band's outer edge, level with the band's lower half (L: a ledge jutting out sideways), beyond the "
                    "design's" % ('right' if her == 'R' else 'left', side)}
    a, b = abs(ours['left'] - ours['right']), abs(design['left'] - design['right'])
    v_ = round(max(0.0, a - b), 4)
    C['body_front_skirt_overhang_mirror'] = {
        'value': v_, 'status': grade('overhang', v_), 'ours': round(a, 4), 'design': round(b, 4),
        'note': "the skirt's overhang past the band, left against right: the sides' difference beyond the design's (L)"}
    return C


def face_side(cls, ppl, win=WIN):
    """which way a profile faces: -1 when the skin at the eyes lies left of the hair (the face on the image's left),
    else +1 (as bodyqa.front_edge finds it)."""
    z = win['top'] - (np.arange(cls.shape[0]) + 0.5) / ppl
    eye = np.nonzero(np.abs(z) < 0.2)[0]
    sk, hr = np.nonzero(cls[eye] == CL['skin'])[1], np.nonzero(cls[eye] == CL['hair'])[1]
    return -1 if (len(sk) and len(hr) and sk.mean() < hr.mean()) else 1


def leg_back(cls, ppl, band=LEG_BAND, win=WIN, face=None):
    """in profile, the legs' back edge per row of `band`: the widest skin run's end away from the face (face_side's,
    unless given), runs under 0.1 L left out. -> {row: L from the grid's left edge, + toward the back}."""
    H, W = cls.shape
    z = win['top'] - (np.arange(H) + 0.5) / ppl
    face = face_side(cls, ppl, win) if face is None else face
    out = {}
    for r in np.nonzero((z <= band[0]) & (z >= band[1]))[0]:
        c = np.nonzero(cls[r] == CL['skin'])[0]
        if not len(c):
            continue
        p = max(np.split(c, np.nonzero(np.diff(c) > 2)[0] + 1), key=len)
        if len(p) >= 0.1 * ppl:
            out[int(r)] = (p[-1] if face < 0 else -p[0]) / ppl
    return out


LEG_EDGE = 0.02                     # L: the rows this close to either figure's first or last leg row are left out (the
                                    # shorts' hem and the boot cuff's top cut the skin's row there: a drawn cuff line that
                                    # slopes cut the design's last two rows short at the back, 0.13-0.21 L, on every build)


def leg_rows(rows):
    """the leg's rows among a figure's back-edge rows: the longest run of consecutive rows (a hand above the shorts
    reads as skin in the band too, cut off from the leg by the shorts' rows)."""
    rows = sorted(rows)
    if not rows:
        return []
    runs = np.split(np.asarray(rows), np.nonzero(np.diff(rows) > 1)[0] + 1)
    return [int(r) for r in max(runs, key=len)]


def leg_back_check(ocls, dcls, ppl, win=WIN):
    """body_profile_leg_back from the profile's class images, ours (the bare leg: our_views' 'bare') and the design's
    (None when they share < 10 rows). Both figures' back edges are taken on the design's facing: ours is drawn on the
    design's grid, facing the same way, and face_side can misread ours (a side lock in front of the eyes: it then
    measured the front edge, offset -5.3 L). The rows are the design's leg (leg_rows: its hand above the shorts left
    out), LEG_EDGE in from either figure's ends."""
    fd = face_side(dcls, ppl, win)
    a, b = leg_back(ocls, ppl, win=win, face=fd), leg_back(dcls, ppl, win=win, face=fd)
    b = {r: b[r] for r in leg_rows(b)}
    z = lambda r: round(float(win['top'] - (r + 0.5) / ppl), 3)
    if not a or not b:
        return None
    lo, hi = max(min(a), min(b)) + LEG_EDGE * ppl, min(max(a), max(b)) - LEG_EDGE * ppl
    rows = sorted(r for r in set(a) & set(b) if lo <= r <= hi)
    if len(rows) < 10:
        return None
    d = np.array([a[r] - b[r] for r in rows])
    off = float(np.median(d))
    k = int(np.argmax(d - off))
    v_ = round(max(0.0, float(d[k] - off)), 4)
    return {'value': v_, 'status': grade('leg_back', v_), 'at': z(rows[k]), 'offset': round(off, 4),
            'rows': [z(rows[0]), z(rows[-1])],
            'note': "the bare leg's back edge in profile (our skin alone, no garments) against the design's, row by "
                    "row over the design's leg from under its shorts to its boot cuffs (%.2f L from either end left "
                    "out): its largest outward bump (L) once the median offset between them is taken out" % LEG_EDGE}


OUTLINE_GAP = 2                     # px: a gap this wide or narrower in the outline behind the leg is bridged
OUTLINE_HUG = 0.02                  # L: the outline running this far past the leg's own skin: something against the leg


def outline_back(cls, ppl, face, edges, gap=OUTLINE_GAP):
    """per row of `edges` (leg_back's), the figure's outline behind the leg: from the leg's back edge on, back through
    whatever touches it (any class but none; gaps up to `gap` px bridged) -> {row: L, + toward the back}."""
    out = {}
    step = 1 if face < 0 else -1
    for r, v in edges.items():
        row = cls[r] > 0
        k = int(round(v * ppl)) * (1 if face < 0 else -1)
        miss = 0
        while 0 <= k + step < len(row) and miss <= gap:
            k += step
            miss = 0 if row[k] else miss + 1
        end = k - step * miss
        out[r] = (end if face < 0 else -end) / ppl
    return out


def leg_outline_check(ocls, dcls, ppl, offset=0.0, win=WIN):
    """body_profile_leg_outline from the dressed profile's class images, ours and the design's: the outline behind the
    leg (outline_back) against the design's on the design's leg rows, `offset` (the bare leg's) taken out. Graded
    (tool/skirt, the flaps' clearance target): its largest step outward within LIMITS['leg_outline'], and the rows
    hugging the leg beyond the design's within 10 (WARN 30). Calibrated: the design against itself 0 and its own 3
    rows; pipeline-3d 120d197's flaps 0.57 L, 82 rows."""
    fd = face_side(dcls, ppl, win)
    a, b = leg_back(ocls, ppl, win=win, face=fd), leg_back(dcls, ppl, win=win, face=fd)
    b = {r: b[r] for r in leg_rows(b)}
    if not a or not b:
        return None
    lo, hi = max(min(a), min(b)) + LEG_EDGE * ppl, min(max(a), max(b)) - LEG_EDGE * ppl
    rows = sorted(r for r in set(a) & set(b) if lo <= r <= hi)
    if len(rows) < 10:
        return None
    oa = outline_back(ocls, ppl, fd, {r: a[r] for r in rows})
    ob = outline_back(dcls, ppl, fd, {r: b[r] for r in rows})
    d = np.array([oa[r] - ob[r] - offset for r in rows])
    k = int(np.argmax(d))
    z = lambda r: round(float(win['top'] - (r + 0.5) / ppl), 3)
    hug = int(sum(oa[r] - a[r] > OUTLINE_HUG for r in rows))
    hug_d = int(sum(ob[r] - b[r] > OUTLINE_HUG for r in rows))
    v_ = round(max(0.0, float(d[k])), 4)
    extra = hug - hug_d
    st = worst(grade('leg_outline', v_), 'PASS' if extra <= 10 else 'WARN' if extra <= 30 else 'FAIL')
    return {'value': v_, 'status': st, 'at': z(rows[k]), 'rows': len(rows),
            'hugging': hug, 'hugging_design': hug_d,
            'note': "the dressed figure's outline behind the leg in profile (the leg's skin run followed back through "
                    "whatever touches it) against the design's, the bare leg's offset taken out: its largest step "
                    "outward (L); hugging: the rows where something runs over %.2f L past the leg's skin (a garment "
                    "against the thigh), ours and the design's" % OUTLINE_HUG}


def panel_edge(O, D, masks, ppl, idx, pm, near=0.25):
    """the cream panel's lower part (the cream of the top and the bow, the design's of its bodice panel, bow and top,
    within `near` L above the band's top: the median of its columns' top rows), ours and the design's: its outline's
    roughness (outline_roughness), fragments and holes. -> dict(ours, design) or None."""
    from scipy import ndimage
    H, W = D['fg'].shape
    res = {}
    for who in ('ours', 'design'):
        if who == 'ours':
            band = _members(O['lab'], idx, pm.get('waistband', []))
            own = _members(O['lab'], idx, [m for p in ('top', 'bodice_panel', 'bow') for m in pm.get(p, [])])
            cream = own & (O['cls'] == CL['cream'])
        else:
            band = masks.get('front__waistband')
            pan = np.zeros((H, W), bool)
            for p in ('bodice_panel', 'bow', 'bow_tail_L', 'bow_tail_R', 'top'):
                m = masks.get('front__' + p)
                if m is not None:
                    pan |= m
            cream = ndimage.binary_dilation(pan, iterations=3) & (D['cls'] == CL['cream'])
        if band is None or not band.any():
            return None
        bt = int(np.median([np.nonzero(band[:, c])[0].min() for c in np.unique(np.nonzero(band)[1])]))
        win = np.zeros((H, W), bool)
        win[max(0, bt - int(near * ppl)):bt] = True
        m = cream & win
        r = outline_roughness(m, ppl)
        if r is None:
            return None
        fr, ho = fragments(m)
        res[who] = dict(rough=r, fragments=fr, holes=ho, band_z=round(float(WIN['top'] - (bt + 0.5) / ppl), 3))
    return res


def boot_mesh(B, members):
    """a boot's triangles in world (eval): its members' meshes, a two-sided object's half by side (x >= 0 her left).
    -> (V, T) or (None, None)."""
    Vs, Ts, off = [], [], 0
    for name, sgn in members:
        try:
            o = B.obj(name)
        except KeyError:
            continue
        if not o.has('eval'):
            continue
        V, T, _, _ = o.mesh('eval')
        if sgn is not None:
            cx = V[T].mean(1)[:, 0]
            T = T[cx >= 0] if sgn > 0 else T[cx < 0]
        Vs.append(V); Ts.append(T + off); off += len(V)
    if not Vs:
        return None, None
    return np.concatenate(Vs), np.concatenate(Ts)


def profile_render(B, members, cuff_members, ppl, az, ss=3, others=()):
    """our boot drawn in profile as the boards draw it (qa3d.draw_view: each object's surface pulled in, its outline
    hull drawn), in a window round the boot at the design's scale x ss. -> dict(lines (every outline pixel), fg, boot
    (the boot's surface and outline pixels, with the far boot's, `others`: where it shows past the near one, the
    profile shows it), region (the near boot's pixels grown by the doubled-stroke gap, below its cuff), cuff (its
    cuff's pixels), ppl (the render's)) or None."""
    from . import qa3d
    from scipy import ndimage
    L = float(B.assembly['L'])
    V, _ = boot_mesh(B, members)
    if V is None:
        return None
    c = (V.min(0) + V.max(0)) / 2
    fr = _Window(c, az, 0.7 * L, 0.8 * L, L / ppl / ss)
    surfs = []
    for o in B.objects():
        variant = 'masked' if o.group == 'skin' and o.has('masked') else 'eval'
        if o.has(variant) and o.group in ('skin', 'garment'):
            surfs += qa3d.surfaces(B, o, variant)
    mi = qa3d.draw_view(B, surfs, az, fr)['mesh']
    hull = np.array([s['hull'] for s in surfs])
    nm = np.array([s['o'].name for s in surfs])
    ok = mi >= 0
    k = np.maximum(mi, 0)
    lines = ok & hull[k]
    names = [m[0] for m in members]
    own = ok & np.isin(nm[k], names) & ~hull[k]
    boot = ok & np.isin(nm[k], names + [m[0] for m in others])
    cuff = ok & np.isin(nm[k], [m[0] for m in cuff_members])
    g = int(round(DOUBLE_GAP * ppl * ss))
    region = ndimage.binary_dilation(own, iterations=g + 3)
    cr = np.nonzero(cuff.any(1))[0]
    if len(cr):
        region[:cr.max() + int(0.05 * ppl * ss)] = False
    return dict(lines=lines, fg=ok, boot=boot, region=region, cuff=cuff, ppl=ppl * ss)


def double_design(D, M, cuff, ppl):
    """the design's drawn lines (its raw classes' line pixels) on its boot in profile, below the cuff: doubled()."""
    from scipy import ndimage
    region = ndimage.binary_dilation(M, iterations=int(round(DOUBLE_GAP * ppl)) + 3)
    if cuff is not None:
        cr = np.nonzero(cuff[:, np.nonzero(M.any(0))[0]].any(1))[0] if M.any() else []
        if len(cr):
            region[:cr.max() + int(0.05 * ppl)] = False
    lines = (D['raw'] == CL['line']) & region
    return doubled(lines, M, ppl)
