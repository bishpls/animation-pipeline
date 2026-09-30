"""The skirt and the overskirt flaps against the design (tool/skirt, docs/workstreams/skirt.md).

Michael's review of round 6 found three faults the piece IoUs and the hem checks didn't separate:
- **The flaps' shape and drape** (the most severe): in profile each flap was a big curved orange lobe hanging from the
  back waist, where the design draws a stepped panel; in the back view they started wide at the centre back.
- **The stepped band** on the skirt's hem and on the flaps: fine pixel-stairs, or a dark tip on the flaps, where the
  design has a few clean, larger steps.
- **The back**: the flaps parting into a pointed V gap showing the dark underlayer, and the back outline.

Each is measured on the design's grids (bodyqa's: the sheet's scale, aligned on the eyes) against the design measured the
same way. The outfit masks hold only the flaps' tails where the flaps lie over the skirt (the same colour: the flap's
upper part was cut as the skirt), so the drawn flap is its face filled between the drawn lines from a seed inside it
(the character's `skirt_marks.json` beside its manifest: seeds in L per view; the lines' gaps closed by CLOSE_PX), plus
the outfit mask's tail. Where a view shows no seed, the outfit mask is the drawn flap (front and three-quarter: only the
tails show below the skirt).

Checks (QA part 'skirt'; lengths in L, angles in degrees; SIDE L or R):
  flap_{view}_iou_{SIDE}      the flap's visible pixels against the drawn flap's (IoU), per view
  flap_{view}_width_{SIDE}    its width row by row down its length against the drawn flap's: the mean difference (a
                              lobe wider than the drawing, or a narrow top drawn wide)
  flap_{back,profile}_attach_{SIDE}
                              where it hangs from: its top row and the middle of its top 0.05 L against the drawing's
                              (where the drawing shows the attach: the back and the profile)
  flap_{view}_hang_{SIDE}     the angle of its centreline (the middle of each row, a weighted line fit) against the
                              drawing's
  flap_profile_clear_{SIDE}   the tail's clearance behind the leg in profile: per row where the drawing shows the flap
                              hanging clear behind the leg (the background between the leg's back edge and the flap),
                              how much less clearance ours has (L; 0 where ours has as much or no flap there), the
                              median (tool/hull-limbs: round 6's train hung against the thigh on 82 of 114 rows, where
                              the drawn flaps hang 0.55-1.0 L clear of it)
  flap_profile_sweep_{SIDE}   the train's sweep in profile: its lowest point's distance behind its attach (+ ours
                              further back than the drawing; Michael's call is "hang": no sweep beyond the skirt's flare)
  hemband_{piece}_steps / _step / _height
                              the stepped band on the skirt's hem and on each flap, per view (the worst view decides):
                              the band's top edge (the orange/dark boundary) simplified to a polyline of treads and
                              risers: the step count (risers at least MIN_RISE high between treads at least MIN_TREAD
                              wide), the step size (the median rise and tread), and the band's height (its median
                              thickness), against the drawing's. The drawing's band is its dark pixels nearest each
                              drawn piece (the outfit masks leave the trims out)
  skirt_back_outline          the lower garments' silhouette in the back view (skirt and flaps), row by row: the mean
                              offset of its left and right edges against the drawing's (rows a hand touches left out)
  skirt_back_flap_gap         the gap between the flaps in the back view row by row (the right one's inner edge less the
                              left one's; negative where they overlap), against the drawing's: its mean difference
  skirt_back_gap_dark         what shows in that gap above the skirt's hem: the share of dark pixels (the band, the
                              shorts) against the drawing's, where the skirt's orange centre-back panel is drawn

    table, checks = skirtqa.measure(B, design)            # charkit.qa3d's 'skirt' part
    table, checks = skirtqa.measure_geometry(bundle, sheet, spec)   # the evaluator's (bodyeval.Geometry.bundle)
"""
import json, os

import numpy as np

from . import bodyqa

WIN = bodyqa.WIN
CL = bodyqa.CLASS
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLAPS = ('overskirt_panel_L', 'overskirt_panel_R')
VIEWS = ('front', 'three_quarter', 'profile', 'back')
LOWER = ('skirt', 'skirt_panel') + FLAPS             # the lower garments' pieces (the back outline)
MIN_PX = 200                  # a flap a view shows with fewer drawn pixels than this isn't measured there
CLOSE_PX = 2                  # the drawn lines' gaps closed by this many pixels before the fill
LINE_LUM = 0.22               # a drawn line: darker than this (mean sRGB) ...
THICK_PX = 3                  # ... and thinner than this opening (thicker dark regions are the bands and the shorts)
TOP_BAND = 0.05               # L: the rows under a flap's top read as its attach
MIN_TREAD = 0.02              # L: a tread of the stepped band at least this wide
MIN_RISE = 0.015              # L: a riser at least this high (about three pixels of the grid)
EDGE_EPS = 2.0                # px: the band's top edge simplified to a polyline within this
BAND_REACH = 0.15             # L: a drawn dark pixel this close to a drawn piece can be its band
BAND_MIN_PX = 40              # a band with fewer pixels is left out (specks, a sliver past an occluder)
BAND_GAP = 0.03               # L: the band's top within this under the face (the drawing's line between them)
LEG_ROWS = (-2.62, -3.4)      # L from the eye line: the rows the flap's clearance behind the leg is read over (profile)
GAP_ROWS = (-1.5, -2.45)      # L from the eye line: the rows the back's flap gap and its content are compared over
                              # (the waist to the drawn skirt's centre-back hem)
LIMITS = {                    # (pass within, warn within); else fail
    'iou': (0.70, 0.50),      # higher is better
    'width': (0.04, 0.08),
    'attach': (0.04, 0.08),
    'hang': (4.0, 8.0),
    'sweep': (0.08, 0.16),
    'steps': (1, 3),
    'step': (0.02, 0.04),
    'band_h': (0.015, 0.03),
    'outline': (0.025, 0.045),
    'gap': (0.04, 0.08),
    'gap_dark': (0.05, 0.12),
    'clear': (0.10, 0.25),
}


def grade(key, v):
    if v is None:
        return 'FAIL'
    p, w = LIMITS[key]
    if key == 'iou':
        return 'PASS' if v >= p else 'WARN' if v >= w else 'FAIL'
    v = abs(v)
    return 'PASS' if v <= p else 'WARN' if v <= w else 'FAIL'


def worst(*ss):
    order = {'FAIL': 0, 'WARN': 1, 'PASS': 2}
    ss = [s for s in ss if s in order]
    return min(ss, key=lambda s: order[s]) if ss else 'SKIPPED'


def rows_z(H, ppl):
    return WIN['top'] - (np.arange(H) + 0.5) / ppl


def cols_u(W, ppl):
    return (np.arange(W) + 0.5) / ppl - WIN['x']


def to_px(x, z, ppl):
    """a point (L: x from the grid's origin, z from the eye line) -> (row, column)."""
    return int((WIN['top'] - z) * ppl), int((WIN['x'] + x) * ppl)


# ------------------------------------------------------------------------------------------------------ the drawn flaps
def marks_path(spec):
    """the character's skirt marks (skirt_marks.json beside its manifest), or None."""
    ref = spec.get('ref') if isinstance(spec.get('ref'), dict) else {}
    mp = ref.get('manifest')
    if not mp:
        return None
    p = os.path.join(os.path.dirname(mp if os.path.isabs(mp) else os.path.join(ROOT, mp)), 'skirt_marks.json')
    return p if os.path.exists(p) else None


def line_walls(rgb, close=CLOSE_PX):
    """the drawing's lines (dark, thin: thick dark regions are bands and shorts, not lines) grown by `close` pixels, and
    the thick dark regions -> (walls, thick)."""
    from scipy import ndimage
    dark = np.asarray(rgb, float).mean(2) < LINE_LUM
    thick = ndimage.binary_opening(dark, iterations=THICK_PX)
    line = dark & ~ndimage.binary_dilation(thick, iterations=1)
    return ndimage.binary_dilation(line, iterations=close), thick


def segment_mask(shape, segs, ppl, width=2):
    """line segments [[x0, z0, x1, z1], ...] (L on the grid) drawn `width` px wide -> bool image."""
    m = np.zeros(shape, bool)
    for x0, z0, x1, z1 in segs:
        (r0, c0), (r1, c1) = to_px(x0, z0, ppl), to_px(x1, z1, ppl)
        n = 2 * max(abs(r1 - r0), abs(c1 - c0)) + 1
        for t in np.linspace(0, 1, n):
            r, c = int(round(r0 + t * (r1 - r0))), int(round(c0 + t * (c1 - c0)))
            m[max(0, r - width // 2):r + width // 2 + 1, max(0, c - width // 2):c + width // 2 + 1] = True
    return m


def face_fill(D, seeds, ppl, close=CLOSE_PX, walls_extra=()):
    """the drawn cells holding the seeds (L), bounded by the drawing's lines (and the marks' wall segments, bridging a
    line the drawing lets fade), its thick dark regions and the figure's edge. A seed on a wall takes the nearest free
    pixel within 0.03 L."""
    from scipy import ndimage
    walls, thick = line_walls(D['rgb'], close)
    if len(walls_extra):
        walls = walls | segment_mask(walls.shape, walls_extra, ppl)
    free = ~walls & ~thick & D['fg']
    lab, _ = ndimage.label(free)
    m = np.zeros(free.shape, bool)
    reach = int(0.03 * ppl)
    for x, z in seeds:
        r, c = to_px(x, z, ppl)
        win = lab[max(0, r - reach):r + reach + 1, max(0, c - reach):c + reach + 1]
        if lab[r, c]:
            m |= lab == lab[r, c]
        elif win.any():
            rr, cc = np.nonzero(win)
            k = np.argmin((rr - min(r, reach)) ** 2 + (cc - min(c, reach)) ** 2)
            m |= lab == win[rr[k], cc[k]]
    return m


def drawn_flaps(dv, masks, marks, ppl):
    """each view's drawn flaps: {view: {flap: mask}}: the outfit mask (the tails), plus its face filled between the
    drawn lines where the marks give seeds."""
    seeds = (marks or {}).get('flap_faces') or {}
    close = int((marks or {}).get('close_px', CLOSE_PX))
    out = {}
    for view in VIEWS:
        if view not in dv:
            continue
        for pid in FLAPS:
            m = masks.get('%s__%s' % (view, pid))
            m = np.zeros(dv[view]['fg'].shape, bool) if m is None else m.copy()
            s = (seeds.get(view) or {}).get(pid)
            if s:
                m |= face_fill(dv[view], s, ppl, close, ((marks or {}).get('walls') or {}).get(view) or ())
            out.setdefault(view, {})[pid] = m
    return out


def drawn_pieces(dv, masks, marks, ppl):
    """the drawing's lower pieces per view, each whole: {view: dict(full, face, band)} of {piece: mask}: the flaps as
    drawn_flaps gives them and the others as the outfit masks (the skirt less the flaps' faces over it), each with its
    band (design_bands' cells, plus the dark pixels its mask already holds); face: its pixels that aren't band."""
    F = drawn_flaps(dv, masks, marks, ppl)
    out = {}
    for view in VIEWS:
        if view not in dv:
            continue
        dk = dv[view]['cls'] == CL['dark']
        H, W = dk.shape
        full = {k.split('__', 1)[1]: m for k, m in masks.items() if k.startswith(view + '__') and
                not k.endswith('__shorts')}
        fl = np.logical_or.reduce([F[view][f] for f in FLAPS])
        full['skirt'] = full.get('skirt', np.zeros((H, W), bool)) & ~fl        # (the flaps' faces over it aren't it)
        full.update(F[view])
        face = {p: m & ~dk for p, m in full.items()}
        cells = design_bands(face, dv[view]['rgb'], dk, ppl)
        none = np.zeros((H, W), bool)
        band_ = {}
        for p in full:                      # a band cell's owner keeps it where another piece's mask covers it too
            others = np.logical_or.reduce([cells.get(q, none) for q in full if q != p] + [none])
            band_[p] = cells.get(p, none) | (full[p] & dk & ~others)
        whole = {p: (full[p] & ~np.logical_or.reduce([band_[q] for q in full if q != p] + [none])) | band_[p]
                 for p in full}
        out[view] = dict(full=whole, face=face, band=band_,
                         shorts=masks.get(view + '__shorts', np.zeros((H, W), bool)))
    return out


# ------------------------------------------------------------------------------------------------------------ ours
def our_views(meshes, names, ppl, az3, iris, centre, L):
    """ours on the design's grids: per view (front, three_quarter, profile, back, and profile_R: the profile from -x,
    mirrored onto the design's profile) the object labels (index into names), their depth and the classes (lines
    absorbed). meshes: [(V, tris, class per triangle)] -> {view: dict(lab, depth, cls, fg)}."""
    from .faceqa import zbuffer, view as proj
    obj = [(V, T, np.full(len(T), i)) for i, (V, T, _) in enumerate(meshes)]
    iris = np.asarray(iris, float)
    az = bodyqa.azimuths(az3)
    az['profile_R'] = 270.0
    out = {}
    for v in VIEWS + ('profile_R',):
        if v == 'profile_R':
            P = iris[np.argmin(iris[:, 0])][None]
            org = (float(proj(P, 270.0)[0][0]), float(np.mean(iris[:, 2])))
        else:
            org = bodyqa.origin(v, az[v], iris, centre)
        depth, lab = zbuffer(obj, az[v], org, L, 1.0 / ppl, WIN)
        _, cl = zbuffer(meshes, az[v], org, L, 1.0 / ppl, WIN, thin=(CL['line'],))
        cls, fg = bodyqa.ours(cl)
        if v == 'profile_R':
            depth, lab, cls, fg = depth[:, ::-1], lab[:, ::-1], cls[:, ::-1], fg[:, ::-1]
        out[v] = dict(lab=lab, depth=depth, cls=cls, fg=fg)
    return out


def obj_mask(lab, names, which):
    ids = [i for i, n in enumerate(names) if n in which]
    return np.isin(lab, ids) if ids else np.zeros(lab.shape, bool)


# ------------------------------------------------------------------------------------------------------------ shapes
def shape(m, ppl):
    """a flap's shape in one view: its rows' widths, its top (the attach: the top row and the middle of the top
    TOP_BAND), its centreline's angle (the middle of each row, a line fitted weighted by the row's width; + the centre
    moving to the image's right going down), its lowest point. -> dict or None."""
    if m.sum() < 3:
        return None
    H, W = m.shape
    z, u = rows_z(H, ppl), cols_u(W, ppl)
    cnt = m.sum(1)
    rows = np.nonzero(cnt >= 3)[0]
    if len(rows) < 3:
        return None
    r0 = rows[0]
    top = m[r0:r0 + max(1, int(TOP_BAND * ppl))]
    tc = np.nonzero(top)[1]
    mid = np.array([np.nonzero(m[r])[0].mean() for r in rows])
    w = cnt[rows].astype(float)
    A = np.c_[rows, np.ones(len(rows))]
    k = np.linalg.lstsq(A * w[:, None], mid * w, rcond=None)[0][0]
    rl = np.nonzero(cnt > 0)[0][-1]
    return dict(rows=rows, width=cnt / ppl, top_z=float(z[r0]), top_x=float(u[int(round(tc.mean()))]),
                angle=float(np.degrees(np.arctan(k))), low_z=float(z[rl]),
                low_x=float(u[int(round(np.nonzero(m[rl])[0].mean()))]))


def iou(a, b):
    un = (a | b).sum()
    return float((a & b).sum() / un) if un else 0.0


def width_diff(a, b):
    """the mean difference of two shapes' row widths over the rows either shows (L)."""
    rows = np.nonzero((a['width'] > 0) | (b['width'] > 0))[0]
    return float(np.abs(a['width'][rows] - b['width'][rows]).mean()) if len(rows) else None


def leg_clearance(cls, fg, ppl, z0=LEG_ROWS[0], z1=LEG_ROWS[1], facing=-1):
    """in profile (the figure facing the image's left: facing -1), per row over z0..z1 the background between the legs'
    back edge (the skin's last column toward the back) and the next figure pixel behind it (L), None where nothing is
    behind the leg. -> {row: gap}."""
    z = rows_z(cls.shape[0], ppl)
    out = {}
    for r in np.nonzero((z <= z0) & (z >= z1))[0]:
        sk = np.nonzero(cls[r] == CL['skin'])[0]
        if not len(sk):
            continue
        if facing < 0:
            c = sk.max()
            behind = np.nonzero(fg[r, c + 1:])[0]
            out[int(r)] = (behind[0] / ppl) if len(behind) else None
        else:
            c = sk.min()
            behind = np.nonzero(fg[r, :c][::-1])[0]
            out[int(r)] = (behind[0] / ppl) if len(behind) else None
    return out


def clearance_diff(ours, design):
    """per row where the drawing shows a flap clear behind the leg: how much less clearance ours has (0 where ours has
    as much, or nothing behind the leg) -> (median L, share of those rows where ours hangs within 0.05 L of the leg,
    rows)."""
    rows = [r for r, g in design.items() if g is not None and g > 0.05 and r in ours]
    if not rows:
        return None
    d = [max(0.0, design[r] - (ours[r] if ours[r] is not None else np.inf)) for r in rows]
    hug = [ours[r] is not None and ours[r] < 0.05 for r in rows]
    return round(float(np.median(d)), 4), round(float(np.mean(hug)), 3), len(rows)


# ------------------------------------------------------------------------------------------------------ the band
def design_bands(faces, rgb, dark, ppl, close=1, reach=BAND_REACH, touch=3):
    """the drawing's bands per piece: the outfit masks leave the trims out (the skirt's band almost wholly), and cut
    the skirt's band as the shorts where both are dark, so the bands are read as cells: the dark regions between the
    drawn lines (their gaps closed by `close` px), each given to the drawn face (faces {piece: mask}, dark pixels out)
    it borders most (within `touch` px), clipped to `reach` L of that face (a cell the band shares with the shorts
    through a gap in their line) and grown back over the line it was cut from. -> {piece: band mask}."""
    from scipy import ndimage
    walls, _ = line_walls(rgb, close)
    lab, n = ndimage.label(dark & ~walls)
    ps = [p for p, m in faces.items() if m is not None and m.any()]
    if not ps or not n:
        return {}
    cnt = np.zeros((len(ps), n + 1))
    for i, p in enumerate(ps):
        ring = ndimage.binary_dilation(faces[p], iterations=touch + close) & ~faces[p]
        cnt[i] = np.bincount(lab[ring], minlength=n + 1)
    cnt[:, 0] = 0
    own = np.argmax(cnt, 0)
    ok = cnt.max(0) >= touch
    out = {}
    for i, p in enumerate(ps):
        cells = np.isin(lab, np.nonzero(ok & (own == i))[0])
        near = ndimage.distance_transform_edt(~faces[p]) <= reach * ppl
        out[p] = ndimage.binary_dilation(cells & near, iterations=close + 1) & dark & near & ~faces[p]
    return out


def rdp(P, eps):
    """a polyline simplified (Ramer-Douglas-Peucker): the points kept -> indices."""
    keep = np.zeros(len(P), bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(P) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        a, b = P[i], P[j]
        d = b - a
        n = np.hypot(*d)
        q = P[i + 1:j] - a
        dist = np.abs(q[:, 0] * d[1] - q[:, 1] * d[0]) / n if n else np.hypot(q[:, 0], q[:, 1])
        k = int(np.argmax(dist))
        if dist[k] > eps:
            m = i + 1 + k
            keep[m] = True
            stack += [(i, m), (m, j)]
    return np.nonzero(keep)[0]


def band_edge(face, B, gap):
    """per column the band's top edge: the row under the face's lowest pixel where the band lies directly beneath it
    (within `gap` px: the drawing's line between them), and the band's run there (its bottom row). -> (top, bottom),
    -1 where a column has none (the band wrapping a riser's outside has no face over it)."""
    H, W = B.shape
    top = np.full(W, -1); bot = np.full(W, -1)
    for c in np.nonzero(B.any(0) & face.any(0))[0]:
        f = np.nonzero(face[:, c])[0][-1]
        r = np.nonzero(B[f + 1:f + 2 + gap, c])[0]
        if not len(r):
            continue
        t = f + 1 + r[0]
        rr = np.nonzero(B[t:, c])[0]
        e = int(np.nonzero(np.diff(rr) > 1)[0][0]) if (np.diff(rr) > 1).any() else len(rr) - 1
        top[c], bot[c] = f + 1, t + rr[e]
    return top, bot


def steps_of(cols, rows, ppl, eps=EDGE_EPS):
    """the steps along one run of a band's top edge (its row per column): the edge simplified to a polyline (rdp,
    eps px), its segments classed as treads (flatter than 45 deg) and risers, consecutive ones of a class merged; a
    step is a riser at least MIN_RISE high between two treads at least MIN_TREAD wide (the drawn stairs tilt with the
    flap's hem: a tread need not be level). -> dict(steps, risers [L], treads [L])."""
    if len(cols) < 3:
        return dict(steps=0, risers=[], treads=[])
    P = np.c_[cols, rows].astype(float)
    Q = P[rdp(P, eps)]
    g = []                                                   # (kind, dc, dr): merged segments
    for dc, dr in np.diff(Q, axis=0):
        k = 'r' if abs(dr) > abs(dc) else 't'
        if g and g[-1][0] == k:
            g[-1] = (k, g[-1][1] + dc, g[-1][2] + dr)
        else:
            g.append((k, dc, dr))
    risers, tr = [], [abs(x[1]) / ppl for x in g if x[0] == 't']
    for i in range(1, len(g) - 1):
        k, dc, dr = g[i]
        if (k == 'r' and abs(dr) >= MIN_RISE * ppl and g[i - 1][0] == 't' and g[i + 1][0] == 't' and
                abs(g[i - 1][1]) >= MIN_TREAD * ppl and abs(g[i + 1][1]) >= MIN_TREAD * ppl):
            risers.append(round(abs(dr) / ppl, 4))
    return dict(steps=len(risers), risers=risers, treads=[round(t, 4) for t in tr if t >= MIN_TREAD])


def band(face, B, ppl, min_px=BAND_MIN_PX, gap=BAND_GAP):
    """a piece's stepped band in one view (face: the piece's other pixels; B: its band's): its top edge (band_edge)
    over the columns where it runs under the face, split where columns are missing; the steps along each run
    (steps_of) summed; the median rise and tread, and the band's height (its median thickness under the face, L).
    -> dict or None (fewer than min_px band pixels)."""
    if B.sum() < min_px:
        return None
    top, bot = band_edge(face, B, int(round(gap * ppl)))
    cols = np.nonzero(top >= 0)[0]
    if not len(cols):
        return None
    steps, risers, treads = 0, [], []
    for run in np.split(cols, np.nonzero(np.diff(cols) > 1)[0] + 1):
        r = steps_of(run, top[run], ppl)
        steps += r['steps']; risers += r['risers']; treads += r['treads']
    return dict(steps=steps, rise=round(float(np.median(risers)), 4) if risers else None,
                tread=round(float(np.median(treads)), 4) if treads else None,
                height=round(float(np.median((bot[cols] - top[cols] + 1) / ppl)), 4), risers=risers,
                px=int(B.sum()), cols=int(len(cols)))


# ------------------------------------------------------------------------------------------------------ the back
def edges(m, rows):
    """per row the leftmost and rightmost columns of a mask (-1 where empty)."""
    lo = np.full(len(rows), -1); hi = np.full(len(rows), -1)
    for i, r in enumerate(rows):
        c = np.nonzero(m[r])[0]
        if len(c):
            lo[i], hi[i] = c[0], c[-1]
    return lo, hi


def outline_diff(ours, drawn, skin_o, skin_d, ppl, z0=-1.5, z1=-3.3):
    """the silhouette's left and right edges per row over z0..z1 (rows where either figure's skin touches its edge
    within 0.05 L left out) -> dict(left, right (mean |difference|, L), iou)."""
    H = ours.shape[0]
    z = rows_z(H, ppl)
    rows = np.nonzero((z <= z0) & (z >= z1) & ours.any(1) & drawn.any(1))[0]
    lo_o, hi_o = edges(ours, rows)
    lo_d, hi_d = edges(drawn, rows)
    k = max(1, int(0.05 * ppl))
    ok = np.ones(len(rows), bool)
    for i, r in enumerate(rows):
        for sk, lo, hi in ((skin_o, lo_o[i], hi_o[i]), (skin_d, lo_d[i], hi_d[i])):
            if sk[r, max(0, lo - k):lo].any() or sk[r, hi + 1:hi + 1 + k].any():
                ok[i] = False
    if not ok.any():
        return None
    dl = np.abs(lo_o[ok] - lo_d[ok]) / ppl
    dr = np.abs(hi_o[ok] - hi_d[ok]) / ppl
    band = np.zeros(ours.shape, bool)
    band[rows] = True
    return dict(left=round(float(dl.mean()), 4), right=round(float(dr.mean()), 4), rows=int(ok.sum()),
                iou=round(iou(ours & band, drawn & band), 4))


def flap_gap(left, right, ppl, z0=GAP_ROWS[0], z1=GAP_ROWS[1]):
    """per row over z0..z1 where both flaps show: the image-right flap's inner (left) edge less the image-left flap's
    inner (right) edge (L; negative: they overlap). -> {row: gap}."""
    z = rows_z(left.shape[0], ppl)
    out = {}
    for r in np.nonzero((z <= z0) & (z >= z1))[0]:
        a, b = np.nonzero(left[r])[0], np.nonzero(right[r])[0]
        if len(a) and len(b):
            out[int(r)] = (b[0] - a[-1] - 1) / ppl
    return out


def gap_region(left, right, ppl, z0=GAP_ROWS[0], z1=GAP_ROWS[1]):
    """the pixels between the two flaps' inner edges over z0..z1 (rows where both show)."""
    m = np.zeros(left.shape, bool)
    for r, g in flap_gap(left, right, ppl, z0, z1).items():
        if g > 0:
            a, b = np.nonzero(left[r])[0][-1], np.nonzero(right[r])[0][0]
            m[r, a + 1:b] = True
    return m


# ------------------------------------------------------------------------------------------------------ the checks
def evaluate(O, names, dv, masks, marks, ppl, only=None, memo=None):
    """every check from our views (our_views) and the design's (bodyqa.design_views) with the outfit masks and the
    marks -> (table, checks). only: the groups to measure ('flaps', 'band', 'back'; the band's pieces as 'band:PIECE'),
    default all; memo: a dict the design's side is kept in across calls on one design (a fit's)."""
    C, T = {}, {'flaps': {}, 'band': {}, 'back': {}}
    memo = {} if memo is None else memo
    want = lambda g: only is None or g in only or (g.startswith('band:') and 'band' in only)

    def kept(key, fn):
        if key not in memo:
            memo[key] = fn()
        return memo[key]
    P = kept('pieces', lambda: drawn_pieces(dv, masks, marks, ppl))
    D = {v: {f: P[v]['full'][f] for f in FLAPS} for v in P}
    dark = CL['dark']

    # ---- the flaps' shape, per view
    for view in (VIEWS if want('flaps') else ()):
        if view not in dv:
            continue
        for pid in FLAPS:
            side = pid[-1]
            ov = 'profile_R' if (view == 'profile' and side == 'R') else view
            dp = 'overskirt_panel_L' if (view == 'profile' and side == 'R') else pid    # the drawing's near flap
            d = D[view][dp]
            if d.sum() < MIN_PX:
                continue
            o = obj_mask(O[ov]['lab'], names, (pid,))
            a, b = shape(o, ppl), kept(('shape', view, dp), lambda: shape(d, ppl))
            rec = dict(px=[int(o.sum()), int(d.sum())])
            T['flaps'].setdefault(pid, {})[view] = rec
            v_ = round(iou(o, d), 4)
            C['flap_%s_iou_%s' % (view, side)] = {'value': v_, 'status': grade('iou', v_), 'px': rec['px'],
                                                  'note': "the flap's visible pixels against the drawn flap's (its face "
                                                          "between the drawn lines and its tail), IoU"}
            if a is None or b is None:
                for k in ('width', 'hang'):
                    C['flap_%s_%s_%s' % (view, k, side)] = {'value': None, 'status': 'FAIL', 'why': 'no flap of ours'
                                                            if a is None else 'no drawn flap'}
                continue
            wd = width_diff(a, b)
            C['flap_%s_width_%s' % (view, side)] = {
                'value': round(wd, 4), 'status': grade('width', wd),
                'ours': [round(float(a['width'][a['rows']].max()), 3), round(a['top_z'], 3), round(a['low_z'], 3)],
                'design': [round(float(b['width'][b['rows']].max()), 3), round(b['top_z'], 3), round(b['low_z'], 3)],
                'note': "its width row by row against the drawn flap's, the mean difference (L); beside it each one's "
                        "widest row, top and lowest point (L)"}
            dh = round(a['angle'] - b['angle'], 2)
            C['flap_%s_hang_%s' % (view, side)] = {
                'value': dh, 'status': grade('hang', dh), 'ours': round(a['angle'], 2), 'design': round(b['angle'], 2),
                'note': "its centreline's angle off the vertical (deg; + its middle moving to the image's right going "
                        "down) against the drawn flap's"}
            if b['top_z'] > -1.75:                                  # the drawing shows where it hangs from
                dz, dx = a['top_z'] - b['top_z'], a['top_x'] - b['top_x']
                v_ = round(max(abs(dz), abs(dx)), 4)
                C['flap_%s_attach_%s' % (view, side)] = {
                    'value': v_, 'status': grade('attach', v_), 'ours': [round(a['top_x'], 3), round(a['top_z'], 3)],
                    'design': [round(b['top_x'], 3), round(b['top_z'], 3)],
                    'note': "where it hangs from: its top row and the middle of its top %.2f L (x, z L) against the "
                            "drawing's; the larger difference" % TOP_BAND}
            if view == 'profile':
                gd = kept(('clear',), lambda: leg_clearance(dv['profile']['cls'], dv['profile']['fg'], ppl))
                r_ = clearance_diff(leg_clearance(O[ov]['cls'], O[ov]['fg'], ppl), gd)
                if r_:
                    C['flap_profile_clear_%s' % side] = {
                        'value': r_[0], 'status': grade('clear', r_[0]), 'hug': r_[1], 'rows': r_[2],
                        'note': "the tail's clearance behind the leg in profile: per row where the drawing shows the "
                                "flap hanging clear of the leg, how much less clearance ours has (L), the median; "
                                "beside it the share of those rows where ours hangs within 0.05 L of the leg"}
                sw_o, sw_d = a['low_x'] - a['top_x'], b['low_x'] - b['top_x']
                v_ = round(sw_o - sw_d, 4)
                C['flap_profile_sweep_%s' % side] = {
                    'value': v_, 'status': grade('sweep', v_), 'ours': round(sw_o, 3), 'design': round(sw_d, 3),
                    'note': "the train's sweep in profile: its lowest point's distance behind its attach (L), ours less "
                            "the drawing's (+ ours further back); Michael's call: hang, no sweep beyond the skirt's flare"}

    # ---- the stepped band, per piece and view
    for piece in [p_ for p_ in ('skirt',) + FLAPS if want('band:' + p_)]:
        per = {}
        for view in VIEWS:
            if view not in dv:
                continue
            side = piece[-1] if piece in FLAPS else None
            ov = 'profile_R' if (view == 'profile' and side == 'R') else view
            dp = 'overskirt_panel_L' if (view == 'profile' and side == 'R') else piece
            db = P[view]['band'].get(dp)
            b = kept(('band', view, dp), lambda: band(P[view]['face'][dp], db, ppl) if db is not None else None)
            if b is None:
                continue
            om = obj_mask(O[ov]['lab'], names, (piece,))
            ok_ = O[ov]['cls'] == dark
            a = band(om & ~ok_, om & ok_, ppl)
            per[view] = dict(ours=a, design=b)
        if not per:
            continue
        T['band'][piece] = per
        name = 'hemband_' + piece
        ds, dz, dh = {}, {}, {}
        for view, r in per.items():
            a, b = r['ours'], r['design']
            if a is None:
                ds[view] = dz[view] = dh[view] = None
                continue
            ds[view] = a['steps'] - b['steps']
            if a['rise'] is None or b['rise'] is None:
                dz[view] = None if (a['rise'] is None) != (b['rise'] is None) else 0.0
            else:
                dz[view] = round(max(abs(a['rise'] - b['rise']), abs(a['tread'] - b['tread'])), 4)
            dh[view] = round(a['height'] - b['height'], 4)

        def pick(d, key):
            vs = {v: x for v, x in d.items()}
            bad = [v for v, x in vs.items() if x is None]
            if bad:
                return None, bad[0]
            v = max(vs, key=lambda k: abs(vs[k]))
            return vs[v], v
        for suffix, d, key, note in (
                ('steps', ds, 'steps', "the band's steps (a riser between treads) ours less the drawing's, the worst "
                                       "view"),
                ('step', dz, 'step', "the step size: the larger of the median rise and median tread differences (L), "
                                     "the worst view"),
                ('height', dh, 'band_h', "the band's median thickness ours less the drawing's (L), the worst view")):
            v, at = pick(d, key)
            C['%s_%s' % (name, suffix)] = {
                'value': v, 'status': grade(key, v), 'view': at,
                'views': {vw: dict(ours={k: (r['ours'] or {}).get(k) for k in ('steps', 'rise', 'tread', 'height')},
                                   design={k: r['design'].get(k) for k in ('steps', 'rise', 'tread', 'height')})
                          for vw, r in per.items()},
                'note': note}

    # ---- the back
    if 'back' in dv and want('back'):
        Ob, Db = O['back'], dv['back']
        ours = obj_mask(Ob['lab'], names, LOWER)
        drawn = np.logical_or.reduce([P['back']['full'][p] for p in LOWER if p in P['back']['full']])
        r = outline_diff(ours, drawn, Ob['cls'] == CL['skin'], Db['cls'] == CL['skin'], ppl)
        if r:
            v_ = round(max(r['left'], r['right']), 4)
            T['back']['outline'] = r
            C['skirt_back_outline'] = dict(r, value=v_, status=grade('outline', v_),
                                     note="the skirt and flaps' silhouette in the back view: its left and right edges' "
                                          "mean offset from the drawing's per row (L, the larger side), rows a hand "
                                          "touches left out; the IoU over those rows beside it")
        # the image's left flap is her left (the back view)
        ol, orr = obj_mask(Ob['lab'], names, ('overskirt_panel_L',)), obj_mask(Ob['lab'], names, ('overskirt_panel_R',))
        dl, dr = D['back']['overskirt_panel_L'], D['back']['overskirt_panel_R']
        go, gd = flap_gap(ol, orr, ppl), flap_gap(dl, dr, ppl)
        rows = sorted(set(go) & set(gd))
        if gd:
            miss = len(set(gd) - set(go))
            v_ = round(float(np.mean([abs(go[r] - gd[r]) for r in rows])), 4) if rows else None
            T['back']['gap'] = dict(ours={k: round(v, 3) for k, v in list(go.items())[::20]},
                                    design={k: round(v, 3) for k, v in list(gd.items())[::20]})
            C['skirt_back_flap_gap'] = {
                'value': v_, 'status': worst(grade('gap', v_), 'PASS' if miss <= 0.1 * len(gd) else 'WARN'),
                'rows': [len(rows), len(gd)],
                'ours': [round(min(go.values()), 3), round(max(go.values()), 3)] if go else None,
                'design': [round(min(gd.values()), 3), round(max(gd.values()), 3)],
                'note': "the gap between the flaps in the back view per row from the waist to the drawn skirt's "
                        "centre-back hem (the right flap's inner edge less the left's, L; negative where they overlap), "
                        "the mean difference; beside it each one's narrowest and widest"}
            go_m, gd_m = gap_region(ol, orr, ppl), gap_region(dl, dr, ppl)
            if gd_m.sum() >= 20:
                sd = float((Db['cls'][gd_m] == dark).mean())
                so = float((Ob['cls'][go_m] == dark).mean()) if go_m.sum() else 1.0
                v_ = round(so - sd, 4)
                C['skirt_back_gap_dark'] = {
                    'value': v_, 'status': grade('gap_dark', max(0.0, v_)), 'ours': round(so, 3), 'design': round(sd, 3),
                    'px': [int(go_m.sum()), int(gd_m.sum())],
                    'note': "what shows between the flaps above the skirt's hem in the back view: the share of dark "
                            "pixels (the band, the shorts), ours less the drawing's (the drawing shows the skirt's "
                            "orange centre-back panel)"}
    return T, C


def design_as_ours(dv, masks, marks, ppl):
    """the drawing labelled as our views are (the calibration: every check passes on the design itself): per view the
    drawn pieces (drawn_pieces: whole, with their bands) as objects, the flaps first, and the design's classes;
    profile_R is the profile with the drawn near flap as her right one (ours is compared that way). -> (O, names)."""
    names = ['overskirt_panel_L', 'overskirt_panel_R', 'skirt', 'skirt_panel', 'waistband', 'shorts']
    P = drawn_pieces(dv, masks, marks, ppl)
    O = {}
    for view in VIEWS:
        if view not in P:
            continue
        H, W = dv[view]['cls'].shape
        lab = np.full((H, W), -1)
        for i, k in enumerate(names):
            m = P[view]['shorts'] if k == 'shorts' else P[view]['full'].get(k, np.zeros((H, W), bool))
            lab[m & (lab < 0)] = i
        lab[dv[view]['fg'] & (lab < 0)] = len(names)
        O[view] = dict(lab=lab, cls=dv[view]['cls'], fg=dv[view]['fg'], depth=None)
    if 'profile' in O:
        lab = O['profile']['lab'].copy()
        lab[lab == 0] = 1
        O['profile_R'] = dict(O['profile'], lab=lab)
    return O, names + ['other']


def measure(B, design, out=None):
    """the checks on a bundle against the design (qa3d.Design) -> (table, checks)."""
    from . import bodymeasure, qa3d
    ctx = design.sheet_context()
    if 'why' in ctx:
        return None, {'skirt': {'status': 'SKIPPED', 'why': ctx['why']}}
    got = bodymeasure.piece_masks(B.spec)
    if got is None:
        return None, {'skirt': {'status': 'SKIPPED', 'why': 'no outfit_masks produced for this spec'}}
    masks, graph, paths = got
    for p in paths:
        design._rec(p)
    mp = marks_path(B.spec)
    marks = None
    if mp:
        design._rec(mp)
        marks = json.load(open(mp))
    meshes, names = qa3d.scene_objects(B)
    As = B.assembly
    O = our_views(meshes, names, ctx['ppl'], ctx['az3'], np.array(qa3d.iris_centres(B)), As['centre'], As['L'])
    T, C = evaluate(O, names, design.design_views(), masks, marks, ctx['ppl'])
    if out:
        from .qa3d import _save_rgb
        _save_rgb(os.path.join(out, 'qa_skirt.png'), picture(O, names, design.design_views(), masks, marks, ctx['ppl']))
    return T, C


def measure_geometry(bundle, sheet, spec):
    """the checks on the evaluator's geometry (bodyeval.Geometry.bundle: plain objects) against a bodymeasure.Sheet ->
    (table, checks)."""
    from . import bodymeasure
    got = bodymeasure.piece_masks(spec)
    if got is None:
        return None, {}
    masks = got[0]
    mp = marks_path(spec)
    marks = json.load(open(mp)) if mp else None
    objs = bodymeasure.objects(bundle)
    meshes = [(o['V'], o['F'][o['label'] >= 0], o['label'][o['label'] >= 0]) for o in objs]
    names = [o['name'] for o in objs]
    lm = bundle['landmarks']
    O = our_views(meshes, names, sheet.ppl, sheet.az3, np.asarray(lm['iris'], float), lm['centre'], lm['L'])
    return evaluate(O, names, sheet.design, masks, marks, sheet.ppl)


# ------------------------------------------------------------------------------------------------------ picture
def picture(O, names, dv, masks, marks, ppl, z0=-1.3, z1=-3.4):
    """per view over the skirt's rows: the drawing dimmed with its flaps tinted (blue her left, green her right), and
    ours beside it the same way; the drawn flaps' outlines on ours (white)."""
    from . import bodymeasure
    P = drawn_pieces(dv, masks, marks, ppl)
    D = {v: {f: P[v]['full'][f] for f in FLAPS} for v in P}
    r0, r1 = to_px(0, z0, ppl)[0], to_px(0, z1, ppl)[0]
    cols = []
    tint = {'overskirt_panel_L': (0.2, 0.4, 1.0), 'overskirt_panel_R': (0.2, 0.8, 0.3)}
    for view in VIEWS:
        if view not in dv:
            continue
        d = 0.5 + 0.5 * np.asarray(dv[view]['rgb'], float)
        o = 0.5 + 0.5 * np.asarray(bodyqa.paint(O[view]['cls']), float) if hasattr(bodyqa, 'paint') else d * 0
        for pid, c in tint.items():
            dm = D[view][pid]
            d[dm] = 0.5 * d[dm] + 0.5 * np.array(c)
            om = obj_mask(O[view]['lab'], names, (pid,))
            o[om] = 0.5 * o[om] + 0.5 * np.array(c)
            o[bodymeasure.outline(dm)] = (1.0, 1.0, 1.0)
        cols += [d[r0:r1], o[r0:r1], np.ones((r1 - r0, 6, 3))]
    return np.concatenate(cols, 1)
