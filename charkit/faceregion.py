"""The face's region measures on a built character (a QA module; charkit/qa3d.py's part 'face_region'): what the head
checks graded alone against the head sheet can't see, measured on the final, assembled figure.

  eye_hollow_<side>       how far the eye sits back of the line from the brow to the cheek, along the vertical through its
                          centre (L; the visible front: the skin and the eye's plate): an anime face has no hollow there
  cheek_lead_<side>       how far the cheek under the eye stands in front of the eye (L): an anime cheek sits at the eye's
                          plane, not forward of it
  eye_bowl_<side>         the deepest local hollow round the eye: over a grid from the brow to the cheek and from the nose's
                          side to the temple, how far the visible front sits behind the mean of its neighbours BOWL_H L
                          away, across or down (L): a socket's bowl, however the column through the eye reads
  eye_width_<view>        the eye opening's width in three-quarter and profile against the design's (charkit.eyeqa on the
                          QA's eye render, the head sheet's eye at the same azimuth: charkit.eyepage)
  profile_edge            the rendered figure's front edge in profile, from the chin to the chest, against the body
                          sheet's, row by row (L; rms, with the worst row): the chin, the throat, the neck and the chest
                          as assembled
  neck_crease             the sharpest local bend of the visible skin's outline down any column round the neck, near where
                          the head meets the body (degrees; the slope less its smoothing over CREASE_SMOOTH): the join's
                          crease or ring as it shows, not the neck's flare (the skin with the garments' mask on: a flare
                          into the shoulders under a collar is hidden)
  neck_crease_all         the same on the whole skin, garments' mask off (INFO: what another costume could show)

    python -m charkit.faceregion BUILD_DIR          # the measures of one build, printed
"""
import json, math, os, sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUT = -0.52                  # L from the eye line: where the head meets the body (charkit.code_base.CUT)
JOIN = (0.10, 0.08)          # L below and above the cut the crease is looked for (below: before the shoulders flare; above: short of the jaw underside)
CREASE_SMOOTH = 0.03         # L: a crease is the outline's slope less its smoothing over this: a sharp bend, not the
                             # neck's gradual flare into the shoulders
HOLLOW = (0.02, 0.04)        # L: PASS / WARN limits for the eye's hollow and the cheek's lead
BOWL = (0.015, 0.03)         # L: PASS / WARN for the eye's bowl
BOWL_H = 0.06                # L: the bowl's neighbours, either side
CREASE = (15.0, 30.0)        # degrees: PASS / WARN for the neck's crease
EDGE = (0.03, 0.06)          # L: PASS / WARN for the profile edge's rms
WIDTH = (0.2, 0.4)           # |ratio - 1|: PASS / WARN for an eye's width against the design's in a view


def _grade(v, lim, lower=True):
    if v is None or not np.isfinite(v):
        return 'SKIPPED'
    v = abs(v) if lower else v
    return 'PASS' if v <= lim[0] else 'WARN' if v <= lim[1] else 'FAIL'


def _mesh(o, variant='eval'):
    V, T, _, _ = o.mesh(variant)
    return np.asarray(V, float), np.asarray(T)


def frame(B):
    """the head's frame: (centre (the head's axis at the eye line), L, the eyes' centres (x, z) world by side)."""
    A = B.assembly
    c = np.asarray(A['centre'], float)
    eyes = {('L' if E['side'] > 0 else 'R'): (float(E['c'][0]), float(E['c'][1])) for E in A['eyes']}
    return c, float(A['L']), eyes


def visible_front(B):
    """the points a front view can see on the face: the skin (as the face measures read it, whole) and the eyes' plates."""
    P = [_mesh(B.skin(), 'eval')[0]]
    for part in ('sclera', 'iris'):
        for side in ('L', 'R'):
            o = B.part(part, side)
            if o is not None:
                P.append(_mesh(o)[0])
    return np.concatenate(P)


def eye_hollow(B, span=0.2, step=0.02, w=0.012):
    """per eye: the visible front's depth along the vertical through its centre, from span above to span below (L):
    -> {side: dict(hollow (how far back of the brow-to-cheek chord the deepest point is), cheek_lead (how far the cheek
    below stands in front of the eye's centre), profile [(z, y)])}."""
    c, L, eyes = frame(B)
    P = visible_front(B)
    out = {}
    for side, (ex, ez) in eyes.items():
        zs = np.arange(span, -span - 1e-9, -step)
        ys = []
        for z in zs:
            m = (np.abs(P[:, 0] - ex) < w * L) & (np.abs(P[:, 2] - (ez + z * L)) < w * L) & (P[:, 1] < c[1] + 0.2 * L)
            ys.append((P[m, 1].min() - c[1]) / L if m.any() else np.nan)
        ys = np.array(ys)
        ok = np.isfinite(ys)
        if ok.sum() < 5:
            out[side] = dict(hollow=None, cheek_lead=None, profile=[])
            continue
        zo, yo = zs[ok], ys[ok]
        chord = np.interp(zo, [zo[-1], zo[0]], [yo[-1], yo[0]])
        hollow = float(np.max(yo - chord))                          # + : behind the chord (y grows backward)
        at = float(np.interp(0.0, zo[::-1], yo[::-1]))
        below = (zo < -0.03) & (zo > -0.16)
        lead = float(at - yo[below].min()) if below.any() else None  # + : the cheek in front of the eye
        out[side] = dict(hollow=round(hollow, 4), cheek_lead=None if lead is None else round(lead, 4),
                         profile=[(round(float(z), 3), round(float(y), 4)) for z, y in zip(zo, yo)])
    return out


def eye_bowl(B, step=0.02, w=0.012, h=BOWL_H):
    """per eye: the visible front's depth on a grid round it (x from the nose's side to the temple, z from the brow to
    the cheek) and its deepest local hollow -> {side: dict(bowl (L), at (x, z) from the eye's centre, L; across or down))}."""
    c, L, eyes = frame(B)
    P = visible_front(B)
    n = int(round(h / step))
    out = {}
    for side, (ex, ez) in eyes.items():
        sg = 1.0 if ex > c[0] else -1.0
        xs = np.arange(-0.14, 0.14 + 1e-9, step); zs = np.arange(0.18, -0.16 - 1e-9, -step)
        Y = np.full((len(zs), len(xs)), np.nan)
        near = P[(np.abs(P[:, 0] - ex) < 0.2 * L) & (np.abs(P[:, 2] - ez) < 0.22 * L) & (P[:, 1] < c[1])]
        for i, z in enumerate(zs):
            rowm = np.abs(near[:, 2] - (ez + z * L)) < w * L
            if not rowm.any():
                continue
            R = near[rowm]
            for j, x in enumerate(xs):
                m = np.abs(R[:, 0] - (ex + sg * x * L)) < w * L
                if m.any():
                    Y[i, j] = (R[m, 1].min() - c[1]) / L
        cx = Y[:, n:-n] - 0.5 * (Y[:, :-2 * n] + Y[:, 2 * n:])
        cz = Y[n:-n, :] - 0.5 * (Y[:-2 * n, :] + Y[2 * n:, :])
        best = (None, None)
        for arr, off, how in ((cx, (0, n), 'across'), (cz, (n, 0), 'down')):
            if np.isfinite(arr).any():
                i, j = np.unravel_index(np.nanargmax(arr), arr.shape)
                v = float(arr[i, j])
                if best[0] is None or v > best[0]:
                    best = (v, (round(float(xs[j + off[1]]), 2), round(float(zs[i + off[0]]), 2), how))
        out[side] = dict(bowl=None if best[0] is None else round(best[0], 4), at=best[1])
    return out


def eye_widths(B):
    """the eye opening's width per view against the design's (eyepage's measure: the QA's eye render and the head
    sheet's eye at the same azimuth) -> {view: dict(ours, design, ratio)}; the three-quarter's and profile's near eye."""
    from . import eyepage, eyeqa, qa3d
    Dz = qa3d.Design(B)
    got = Dz.sheet_measures()
    az3 = float(got[0].get('az_three_quarter', 35.0)) if got else 35.0
    des, ppl = eyepage.design_eyes(B.spec)
    views = {'front': 0.0, 'three_quarter': az3, 'profile': 90.0}
    out = {}
    for view, pairs in des.items():
        for side, px in pairs:
            if view != 'front' and side != 'L':
                continue
            md = eyeqa.measure(px, ppl)
            mo = eyeqa.measure(qa3d.eye_image(B, side, ppl, ss=3, az=views[view]), ppl)
            if not (md.get('found') and mo.get('found')):
                continue
            key = view if view != 'front' else 'front_' + side
            out[key] = dict(ours=round(float(mo['open_w']), 4), design=round(float(md['open_w']), 4),
                            ratio=round(float(mo['open_w'] / md['open_w']), 3))
    return out


def profile_edge(B, z_top=None, z_bottom=-0.85, step=0.01):
    """the rendered figure's front edge in profile against the body sheet's, row by row from the chin to the chest (L
    from the eye line) -> dict(rms, worst (the row and its difference), rows [(z, ours, design)]); + : ours behind."""
    from . import bodyqa, bodymeasure, qa3d
    from .faceqa import zbuffer
    Dz = qa3d.Design(B)
    ctx = Dz.sheet_context()
    if 'why' in ctx:
        return None
    dv = Dz.design_views()
    if 'profile' not in dv:
        return None
    meshes, _ = qa3d.scene_classes(B)
    az = bodyqa.azimuths(ctx['az3'])['profile']
    iw = eye_anchor(qa3d.iris_centres(B), float(B.assembly['eye_z']))     # (the head's eye line: the design's eye row)
    org = bodyqa.origin('profile', az, iw, B.assembly['centre'])
    W, ppl = bodyqa.WIN, ctx['ppl']
    ours = zbuffer(meshes, az, org, B.assembly['L'], 1.0 / ppl, W)[1] >= 0
    des = dv['profile']['fg']
    z_top = z_top if z_top is not None else float(B.assembly.get('head_chin_z', -0.36))

    def edge(m, z):
        r = int(round((W['top'] - z) * ppl))
        if not 0 <= r < m.shape[0]:
            return np.nan
        cols = np.nonzero(m[r])[0]
        return (cols.min() + 0.5) / ppl - W['x'] if len(cols) else np.nan
    rows = []
    for z in np.arange(z_top, z_bottom - 1e-9, -step):
        a, d = edge(ours, z), edge(des, z)
        if np.isfinite(a) and np.isfinite(d):
            rows.append((round(float(z), 3), round(float(a), 4), round(float(d), 4)))
    if not rows:
        return None
    diff = np.array([a - d for _, a, d in rows])
    k = int(np.argmax(np.abs(diff)))
    return dict(rms=round(float(np.sqrt(np.mean(diff ** 2))), 4), worst=[rows[k][0], round(float(diff[k]), 4)],
                rows=rows)


def neck_crease(B, cols=36, dz=0.01, variant='masked'):
    """the sharpest local bend of the skin's outline down any column round the neck near the cut (JOIN): per column the
    skin's exact cut at that azimuth (crease_of), its slope angle per height, and how far it departs from its own
    smoothing over CREASE_SMOOTH (degrees) -> dict(max, median, worst column (degrees round from the front), per column).
    variant: the skin as it shows ('masked': the garments' mask on) or whole ('eval')."""
    c, L, _ = frame(B)
    try:
        V, T = _mesh(B.skin(), variant)
    except (KeyError, ValueError):                 # (a bundle without the masked skin)
        V, T = _mesh(B.skin(), 'eval')
    return crease_of(V, T, c, L, cols, dz)


CREASE_RUN = 4               # steps: a column's outline is read on its unbroken runs this long or longer (a garment's
                             # mask can cut a column into pieces; a bend is never read across a gap)


def section_outline(V, T, axis, a, zs):
    """the skin cut by the half-plane at azimuth a round the vertical axis through `axis` (the column's direction
    (sin a, -cos a): 0 the front): each triangle crossing the plane gives a segment in (r, z); the outline is the
    outermost crossing at each height of zs -> r (len(zs),), NaN where no surface crosses (a masked gap, or past the
    surface's edge). Exact on the mesh: no sector of azimuths blended, no slab of vertex rows sampled."""
    d = np.array([math.sin(a), -math.cos(a)])
    nrm = np.array([d[1], -d[0]])
    q = V[:, :2] - axis
    s, u = q @ nrm, q @ d
    side = s[T] >= 0
    cross = side.any(1) & ~side.all(1)
    Tc = T[cross]
    out = np.full(len(zs), np.nan)
    if not len(Tc):
        return out
    pts_u, pts_z, ok = [], [], []
    for i, j in ((0, 1), (1, 2), (2, 0)):
        a_, b_ = Tc[:, i], Tc[:, j]
        m = (s[a_] >= 0) != (s[b_] >= 0)
        den = np.where(m, s[a_] - s[b_], 1.0)
        f = np.where(m, s[a_] / den, 0.0)
        pts_u.append(u[a_] + f * (u[b_] - u[a_]))
        pts_z.append(V[a_, 2] + f * (V[b_, 2] - V[a_, 2]))
        ok.append(m)
    pu, pz, ok = np.stack(pts_u, 1), np.stack(pts_z, 1), np.stack(ok, 1)
    first = np.argmax(ok, 1)                                     # the triangle's two crossing edges: its segment
    second = 2 - np.argmax(ok[:, ::-1], 1)
    k = np.arange(len(Tc))
    u0, z0, u1, z1 = pu[k, first], pz[k, first], pu[k, second], pz[k, second]
    keep = (u0 > 0) & (u1 > 0) & (first != second) & (z0 != z1)  # the column's side of the axis
    u0, z0, u1, z1 = u0[keep], z0[keep], u1[keep], z1[keep]
    if not len(u0):
        return out
    lo, hi = np.minimum(z0, z1), np.maximum(z0, z1)
    Z = np.asarray(zs)[None, :]
    span = (lo[:, None] <= Z) & (hi[:, None] >= Z)
    f = (Z - z0[:, None]) / (z1 - z0)[:, None]
    R = np.where(span, u0[:, None] + f * (u1 - u0)[:, None], -np.inf)
    best = R.max(0)
    out[np.isfinite(best)] = best[np.isfinite(best)]
    return out


def crease_of(V, T, c, L, cols=36, dz=0.01):
    """neck_crease on plain arrays: the skin's vertices V (world) and triangles T, the head's centre c and L. Each column
    (cols round the neck's axis) is the skin's exact cut at its azimuth (section_outline) every dz L over the join
    window; its outline's slope per step (degrees, 0 vertical) less that slope's smoothing over CREASE_SMOOTH is the
    bend, read on each unbroken run of CREASE_RUN steps or more (a gap the garments' mask leaves splits a column: no
    bend is read across it, nor past a run's ends).
    (Before 2026-10-01 a column was the largest vertex radius within 6 degrees and 0.006 L of each height, the gaps
    interpolated: it read the vertex rows' spacing on a steep flare (two heights catching one row read flat, then a
    jump), the ends' clamped extrapolation and a mask's edge crossing the sector as bends of 27-55 degrees on a join
    whose exact cut bends 12-14.)"""
    from scipy.ndimage import gaussian_filter1d
    T = np.asarray(T)
    zc = c[2] + CUT * L
    vin = (V[:, 2] > zc - (JOIN[0] + 0.05) * L) & (V[:, 2] < zc + (JOIN[1] + 0.05) * L)
    if vin.sum() < 50:
        return None
    Tb = T[vin[T].all(1)]
    ring = V[vin & (np.abs(V[:, 2] - zc) < 0.02 * L)]
    axis = ring[:, :2].mean(0) if len(ring) else c[:2]
    zs = np.arange(zc - JOIN[0] * L, zc + JOIN[1] * L + 1e-12, dz * L)
    per = {}
    for j in range(cols):
        a = -math.pi + 2 * math.pi * (j + 0.5) / cols
        rr = section_outline(V, Tb, axis, a, zs)
        ok = np.isfinite(rr)
        okd = ok[1:] & ok[:-1]
        ang = np.degrees(np.arctan2(np.diff(np.where(ok, rr, 0.0)), dz * L))   # the outline's slope per step
        best, k, seen = 0.0, 0, False
        while k < len(okd):
            if not okd[k]:
                k += 1
                continue
            e = k
            while e < len(okd) and okd[e]:
                e += 1
            if e - k >= CREASE_RUN:
                seg = ang[k:e]
                b = np.abs(seg - gaussian_filter1d(seg, CREASE_SMOOTH / dz, mode='nearest'))
                best, seen = max(best, float(b.max())), True
            k = e
        if seen:
            per[round(math.degrees(a))] = round(best, 1)
    if not per:
        return None
    worst = max(per, key=per.get)
    return dict(max=per[worst], median=round(float(np.median(list(per.values()))), 1), worst=worst, per=per)


# ------------------------------------------------------------------------------------------------ the jaw and the chin
# The chin and jaw as the face boards show them, against the head sheet. The boards' camera (charkit.scene.boards: 85 mm,
# 1 m out, level at the eye line + 0.06 L) is emulated in perspective, and the look's outline (an inverted hull: the skin
# offset by the line's width, faces flipped, back faces culled; charkit.shade.outline) is drawn with it, so a jaw line
# shows only where the render would ink one: where the jaw's rim is a silhouette with the neck behind it. The design
# side is the head sheet's views (charkit.geom.hull.views_from_heads) classed by charkit.bodyqa.classes with the drawn
# lines kept. Both are on one grid round the eyes (the front's and three-quarter's middle, the profile's near eye).
JAW_WIN = dict(x=0.6, top=0.05, bottom=-0.8)   # L round the eyes' point
BOARD_CAM = dict(dist=1.0, lift=0.06)           # m out from the target (0, 0, eye line + lift L), level (charkit.scene)
LEVEL_CAM = dict(dist=None, lift=0.0)           # the design's projection: level with the eyes, orthographic (was 100 m
                                                # out, all but orthographic: a pixel's difference at most)
ORTHO_DEPTH = 100.0                             # (the orthographic view's depths: in front of the reference point by this)
INK_L = 0.004                    # the outline's width (L): the look's lines.frac 0.0022 of the board's 900 px at 85 mm, 1 m
INK = (4, 8, 10)                 # the drawing's ink classes (bodyqa.CLASS line, dark, other: the jaw's line and the wedge
                                 # under the chin read as line or other)
FACE_SEEDS = ((0.0, -0.15), (-0.09, -0.2), (0.09, -0.2))   # (u, z) L: skin on the face, between the nose and the mouth
PROFILE_SEEDS = ((0.0, -0.18), (0.06, -0.25))
JAW_ROWS = (-0.1, 0.005)         # the outline's rows: from the cheek (z) down to the design's chin point, every (L)
SCAN_TOP = -0.25                 # z (L): the columns' scan for the jaw starts here, under the mouth
JAW_V = 0.08                     # L either side of the chin point where the V's rise is read
NECK_BELOW = 0.1                 # L under / over the design's chin where the neck's / the face's width is read
REACH = 0.035                    # L under the face's lowest pixel a jaw line's ink, and the neck under the ink, are looked for
TAPER = (0.015, 0.03)            # L: PASS / WARN for the outline's rms against the design's, and for the chin point's height
JAW_LINE = (0.7, 0.4)            # ours over the design's jaw line over the neck: PASS at least / WARN at least
RATIO = (0.15, 0.3)              # (was chin_v's and neck_to_face's |ratio - 1| PASS / WARN, before face5 round 7)
UNDER = (6.0, 12.0)              # (was chin_underside's PASS / WARN, degrees, before face5 round 7)
# face5 round 7 (2026-09-30): limits from each check's calibration triple (charkit/calib/jaw.py; the records in
# charkit/calib/records/): PASS at most halfway from the design's own reading (its median over the 1-2 px moves) to the
# floor (the median of its random stand-ins' medians: calibrate.MARGIN), and under every floor generator's median, never
# under the design's worst move; WARN at most the floor; neither looser than before. The values are the graded
# deviations from the design's (the floor's median then reads a random stand-in's typical deviation, not the seed whose
# signed value lands nearest the design's). The PASS line: min(halfway from the design's median to the floor, midway
# from the design's worst move to the nearest floor generator's median), not under the design's worst move. The WARN lines
# are kept (each check's known-bad still FAILs: jaw0_flagged). Numbers: charkit/out/calib_jaw/calib_r7a.json, r7b.json
# (9 seeds; design median / worst move | floors' medians):
JAW_TAPER = (0.0102, 0.03)       # L rms. design 0.0020 / 0.0079 | affine 0.0582, widths 0.0125, other_view 0.0607 (was
                                 # TAPER's 0.015: widths_jaw passed it, 7 of 9 seeds)
CHIN_V = (0.042, 0.3)            # |rise over the design's - 1|, the rise sub-pixel (_outline_rise). design 0 / 0 |
                                 # affine 0.084, widths 0.084, other_view 1.0 (was RATIO's 0.15)
NECK_FACE = (0.0867, 0.24)       # |chin_share - the design's| (a new measure: WARN at the floor, 0.24). design 0.020 /
                                 # 0.081 | affine 0.388, other_view 0.092
UNDERSIDE = (0.4, 12.0)          # deg. design 0 / 0 | affine 1.5, widths 0.8 (was UNDER's 6)
WIGGLE = (12.0, 18.0)            # degrees: PASS / WARN for the neck's front outline under the throat in profile, its
                                 # sharpest bend (a lip and a notch under the jaw bend it, 24 on the step-built chin; the
                                 # neck's own long curve doesn't; the design's own neck, read further down past its hanging
                                 # lock and into the shoulders' flare, is shown)
DESIGN_NECK_BAND = 0.25          # L under the throat where the design's neck's front outline is read (a lock hangs in
                                 # front of its neck under the jaw: it shows from 0.13 L under the throat)
NECK_BAND = DESIGN_NECK_BAND     # ... and ours (face5 round 7; was 0.1: the design, standing in for ours, showed no
                                 # neck front there, so the check couldn't be calibrated): the same rows
NECK_STEP = 0.01                 # L: a row-to-row jump of the neck's front edge this big ends the neck (the chest's line
                                 # meeting it: the design's foot of the neck at z -0.608 read as a 14.5 degree bend)
SHARE_BAND = 0.05                # L over the design's chin: the rows where the face's share of the width is read



def cam_points(V, az, target, ref, L, dist=BOARD_CAM['dist']):
    """world points -> the board camera's view as points for raster.window_zbuffer at az 0: (u, depth, v) times L, u and v
    the picture's right and up in L at the reference point's depth (perspective), 0 at the reference point, depth L
    along the view. The camera (charkit.qa.render_view): at target + dist (sin az, -cos az, 0), level, looking at it;
    dist None: orthographic along the same axis (the design's projection: the head sheet is drawn level and
    orthographic)."""
    a = math.radians(az)
    r, f = np.array([math.cos(a), math.sin(a), 0.0]), np.array([-math.sin(a), math.cos(a), 0.0])
    if dist is None:                    # orthographic (the design's projection): u, v the picture's plane through ref
        q = np.asarray(V, float) - np.asarray(ref, float)
        return np.stack([q @ r, q @ f + ORTHO_DEPTH, q[:, 2]], 1)
    eye = np.asarray(target, float) + dist * np.array([math.sin(a), -math.cos(a), 0.0])
    q = np.asarray(V, float) - eye
    X, Y, Z = q @ r, q @ f, q[:, 2]
    qr = np.asarray(ref, float) - eye
    Yr = float(qr @ f)
    u = X / Y * Yr - float(qr @ r)
    v = Z / Y * Yr - float(qr[2])
    return np.stack([u, Y, v], 1)


def vertex_normals(V, T):
    """area-weighted vertex normals (outward for counter-clockwise triangles)."""
    n = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    N = np.zeros_like(V)
    for i in range(3):
        np.add.at(N, T[:, i], n)
    return N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)


def board_view(meshes, skin, az, target, ref, L, ppl, ink=INK_L, win=JAW_WIN, dist=BOARD_CAM['dist']):
    """the board camera's picture of a scene on the jaw window at ppl: meshes [(V world, tris, class per triangle)]
    occluding each other, and the skin's outline (skin = (V, T): the inverted hull, INK_L wide, as the look draws it)
    -> class image (bodyqa.CLASS, 0 where empty; the outline as line) and depth (L, inf where empty)."""
    from .bodyqa import CLASS
    from .geom import raster
    P = [(cam_points(V, az, target, ref, L, dist), np.asarray(T), lab) for V, T, lab in meshes]
    if skin is not None:
        Vs, Ts = np.asarray(skin[0], float), np.asarray(skin[1])
        shell = Vs + ink * L * vertex_normals(Vs, Ts)
        P.append((cam_points(shell, az, target, ref, L, dist), Ts[:, ::-1], np.full(len(Ts), CLASS['line']), True))
    depth, lab = raster.window_zbuffer(P, 0.0, (0.0, 0.0), L, 1.0 / ppl, win)
    return np.where(lab >= 0, lab, 0), depth / L


def design_jaw_views(rgb, eye_x, facing=-1, win=JAW_WIN, which=('front', 'three_quarter', 'profile')):
    """the head sheet's front, three-quarter and profile on the jaw window, each round its eyes' point (the front's and
    three-quarter's middle, the profile's near eye) at the sheet's own px per L -> ({view: dict(cls (bodyqa classes, the
    lines kept), fg, az)}, ppl)."""
    from . import bodyqa, refcheck
    from .geom import hull
    rgb0, _ = refcheck.without_guides(np.asarray(rgb, float))
    views, info = hull.views_from_heads(rgb0, eye_x, facing, floor=win['bottom'] - 0.05)
    Hd = refcheck.detect_heads(rgb0, eye_x, facing)['heads']
    out = {}
    for vn in which:
        v = views.get(vn)
        if v is None:
            continue
        eyes = sorted(Hd[vn]['eyes'])
        ex = eyes[0][0] if vn == 'profile' else float(np.mean([e[0] for e in eyes]))
        raw = bodyqa.classes(rgb0, v.mask, v.eye_y, v.ppl)[1]
        raw = np.where(np.isin(raw, INK), bodyqa.CLASS['line'], raw)
        cls = bodyqa.crop(np.where(v.mask, raw, 0), (ex, v.eye_y), v.ppl, win)
        out[vn] = dict(cls=cls, fg=cls > 0, az=float(v.az))
    return out, float(info['ppl'])


def _px(u, z, ppl, win=JAW_WIN):
    return int(round((win['top'] - z) * ppl - 0.5)), int(round((u + win['x']) * ppl - 0.5))


def _region(cls, seeds, ppl, win=JAW_WIN):
    """the skin connected (4-way) to the seed points, the ink (grown a pixel: a drawn line's anti-aliased gaps closed) and
    every other class its walls -> bool image."""
    from scipy import ndimage
    skin = (cls == 1) & ~ndimage.binary_dilation(cls == 4)
    lab, _ = ndimage.label(skin)
    keep = set()
    for u, z in seeds:
        r, c = _px(u, z, ppl, win)
        if 0 <= r < cls.shape[0] and 0 <= c < cls.shape[1] and lab[r, c]:
            keep.add(int(lab[r, c]))
    return np.isin(lab, sorted(keep)) if keep else np.zeros_like(skin)


def _row_width(mask, ppl, zz, win=JAW_WIN):
    """the width (L) of mask's run at row z zz containing the window's middle column, or the nearest run; None if none."""
    H = mask.shape[0]
    r = int(round((win['top'] - zz) * ppl - 0.5))
    if not 0 <= r < H or not mask[r].any():
        return None
    c0 = int(round(win['x'] * ppl))
    c = np.nonzero(mask[r])[0]
    runs = np.split(c, np.nonzero(np.diff(c) > 1)[0] + 1)
    run = min(runs, key=lambda q: 0 if q[0] <= c0 <= q[-1] else min(abs(q[0] - c0), abs(q[-1] - c0)))
    return (run[-1] - run[0] + 1) / ppl


def _chin_share(face, sil, ppl, zc, win=JAW_WIN):
    """the face's share of the figure's width just over the chin (face5 round 7; Michael's flag on jaw_0: "the face ran
    straight into a neck as wide as the lower face"): per row from the chin zc (the design's) up SHARE_BAND, the face
    region's width over the skin-and-ink run's (the face, the jaw lines and the neck beside them), the rows' mean; a V
    chin over a neck reads low, a face running into the neck near 1 -> share or None."""
    shares = []
    for zz in np.arange(zc, zc + SHARE_BAND + 1e-9, 1.0 / ppl):
        a, b = _row_width(face, ppl, zz, win), _row_width(sil, ppl, zz, win)
        if b:
            shares.append((a or 0.0) / b)
    return round(float(np.mean(shares)), 4) if shares else None


def _outline_rise(face, ppl, uc, win=JAW_WIN, tip=0.02):
    """the V's rise on the face region's outline: the lowest outline crossing JAW_V either side of the chin's column uc
    over the outline's lowest point within `tip` L of it (L), the sides' mean; the outline by marching squares on the
    region (holes filled), so the crossings are sub-pixel -> rise or None."""
    from scipy import ndimage
    from skimage import measure as skm
    f = ndimage.binary_fill_holes(face)
    if not f.any():
        return None
    C = max(skm.find_contours(np.pad(f, 1).astype(float), 0.5), key=len) - 1
    X = np.stack([(C[:, 1] + 0.5) / ppl - win['x'], win['top'] - (C[:, 0] + 0.5) / ppl], 1)
    near = np.abs(X[:, 0] - uc) < tip
    if not near.any():
        return None
    zmin = float(X[near, 1].min())
    rise = []
    for s_ in (-1, 1):
        u0 = uc + s_ * JAW_V
        a, b = X[:-1], X[1:]
        k = np.nonzero((a[:, 0] - u0) * (b[:, 0] - u0) <= 0)[0]
        k = k[a[k, 0] != b[k, 0]]
        if not len(k):
            continue
        t = (u0 - a[k, 0]) / (b[k, 0] - a[k, 0])
        zc_ = a[k, 1] + t * (b[k, 1] - a[k, 1])
        rise.append(float(zc_.min()) - zmin)
    return round(float(np.mean(rise)), 4) if rise else None


def jaw_front(cls, ppl, chin_z=None, win=JAW_WIN, seeds=FACE_SEEDS):
    """a front or three-quarter picture's jaw (cls: classes on the jaw window, the ink as line). Down each column from
    SCAN_TOP (under the mouth) the face's skin runs until ink or another class: its lowest pixel, and a jaw line over
    the neck where ink stops it with skin under the ink (within 2 REACH: the wedge under a drawn chin is ink). From
    those: the chin point (the lowest within 0.15 L of the middle), the V's rise JAW_V either side, the jaw line's length
    over the neck; from the face region (the skin reached from the seeds, the lines its walls) its outline's half-width
    per row; and the face's and the neck's widths NECK_BELOW over and under chin_z (the design's chin; default its own)
    -> dict (L)."""
    H, W = cls.shape
    z = win['top'] - (np.arange(H) + 0.5) / ppl
    u = (np.arange(W) + 0.5) / ppl - win['x']
    skin, ink = cls == 1, cls == 4
    rs = int(round((win['top'] - SCAN_TOP) * ppl - 0.5))
    k = int(REACH * ppl)
    low = np.full(W, -1)
    over = np.zeros(W, bool)
    for c in np.nonzero(skin[rs])[0]:
        col = skin[rs:, c]
        stop = np.nonzero(~col)[0]
        if not len(stop):
            continue                                    # (skin to the window's foot)
        r = rs + stop[0] - 1
        low[c] = r
        if ink[r + 1, c]:
            run = np.nonzero(~ink[r + 1:min(H, r + 1 + 2 * k), c])[0]
            over[c] = bool(len(run)) and skin[r + 1 + run[0], c]
    out = dict(jaw_line_L=round(float(over.sum()) / ppl, 4), jaw_cols=over)
    face = _region(cls, seeds, ppl, win)
    half = np.full(H, np.nan)
    for r in np.nonzero(face.any(1))[0]:
        c = np.nonzero(face[r])[0]
        half[r] = (c[-1] - c[0] + 1) / ppl / 2
    out['half'] = half
    if chin_z is not None:                              # (read on the design's chin's rows even when ours has no chin)
        out['chin_share'] = _chin_share(face, skin | ink, ppl, chin_z, win)
    mid = np.abs(u) < 0.15
    cand = np.nonzero(mid & (low >= 0))[0]
    if not len(cand):
        return out
    cc = cand[np.argmax(low[cand])]
    out['chin'] = (round(float(u[cc]), 4), round(float(z[low[cc]]), 4))
    zc = out['chin'][1]
    rise = []
    for s_ in (-1, 1):
        c = int(round(cc + s_ * JAW_V * ppl))
        if 0 <= c < W and low[c] >= 0:
            rise.append(float(z[low[c]] - zc))
    out['rise_px'] = round(float(np.mean(rise)), 4) if rise else None
    # (face5 round 7) the rise on the face region's outline (marching squares, sub-pixel): the column scan's whole rows
    # read the design's V's rise (0.03 L, 12 px) in 1-pixel steps of 8%, ours one row over it as far off as a random
    # affine jaw's median
    out['rise'] = _outline_rise(face, ppl, float(u[cc]), win)
    if out['rise'] is None:
        out['rise'] = out['rise_px']
    zc_ref = zc if chin_z is None else chin_z

    width = lambda zz, mask: _row_width(mask, ppl, zz, win)
    out['face_w'] = width(zc_ref + NECK_BELOW, face)
    out['neck_w'] = width(zc_ref - NECK_BELOW, skin)
    if 'chin_share' not in out:
        out['chin_share'] = _chin_share(face, skin | ink, ppl, zc_ref, win)
    return out


def jaw_profile(cls, ppl, win=JAW_WIN, seeds=PROFILE_SEEDS, neck_band=NECK_BAND):
    """a profile picture's chin (cls on the jaw window, facing -u):
      - the chin point: where the front edge steps back furthest within 0.03 L of rows, under the mouth;
      - the underside: per column behind the chin, the foot of the skin-and-ink run down from 0.15 L over the chin (or under the hair),
        until a column's run reaches 0.06 L under the chin (the neck: the throat); its angle by a line fit (+ rising
        toward the throat);
      - the neck's front edge under the throat, down `neck_band` L (NECK_BAND; the design's is read further down, where its
        neck shows under a hanging lock), in rows where the first skin has only ink or nothing in
        front of it (a hair lock or a collar in front hides it): its wiggle (L: the largest departure from a quadratic
        over the rows, the neck's long curve taken out), its backtracking (L: its travel less its net) and its sharpest
        bend, the slope's angle less its smoothing over CREASE_SMOOTH (degrees) -> dict."""
    from scipy.ndimage import gaussian_filter1d
    H, W = cls.shape
    z = win['top'] - (np.arange(H) + 0.5) / ppl
    u = (np.arange(W) + 0.5) / ppl - win['x']
    fg = cls > 0
    body = (cls == 1) | (cls == 4)
    edge = np.full(H, np.nan)
    for r in range(H):
        c = np.nonzero(fg[r])[0]
        if len(c):
            edge[r] = u[c[0]]
    out = {}
    band = np.nonzero((z < -0.22) & (z > -0.6) & np.isfinite(edge))[0]
    if len(band) < 10:
        return out
    k = max(1, int(0.03 * ppl))
    step = np.full(H, -np.inf)
    for r in band:
        if r + k < H and np.isfinite(edge[r + k]):
            step[r] = edge[r + k] - edge[r]
    r_c = int(np.argmax(step))
    if step[r_c] < 0.05:
        return out
    win_r = np.arange(r_c, r_c + k + 1)
    win_r = win_r[np.isfinite(edge[win_r])]
    front = float(np.min(edge[win_r]))
    rc = int(max(r for r in win_r if edge[r] <= front + 0.004))
    cc = int(round((edge[rc] + win['x']) * ppl - 0.5))
    out['chin'] = (round(float(edge[rc]), 4), round(float(z[rc]), 4))
    r_top = max(0, rc - int(0.15 * ppl))
    zu, throat = [], None
    for c in range(cc + 1, W):
        top = np.nonzero(body[r_top:rc + 1, c])[0]         # (from under the hair where it hangs over the jaw)
        if not len(top):
            continue
        r = r_top + top[0]
        while r + 1 < H and body[r + 1, c]:
            r += 1
        if z[r] < z[rc] - 0.06:
            throat = c
            break
        if z[r] < z[rc] + 0.1:                              # (a sliver of skin between hair locks: not the underside)
            zu.append((u[c], z[r]))
    if len(zu) >= 4 and throat is not None:
        zu = np.array(zu)
        lo, hi = zu[0, 0] + 0.15 * (zu[-1, 0] - zu[0, 0]), zu[0, 0] + 0.85 * (zu[-1, 0] - zu[0, 0])
        s = (zu[:, 0] >= lo) & (zu[:, 0] <= hi)
        slope = np.polyfit(zu[s, 0], zu[s, 1], 1)[0] if s.sum() >= 3 else np.nan
        out['underside_deg'] = round(float(np.degrees(np.arctan(slope))), 1)
        out['underside'] = zu
        out['throat'] = (round(float(zu[-1, 0]), 4), round(float(zu[-1, 1]), 4))
    # (under the chin's lowest point: a rising underside's throat is above it, and the rows between have the chin in front)
    zt = min(out['throat'][1], float(out['underside'][:, 1].min())) if 'throat' in out else z[rc]
    ut = out['throat'][0] - 0.05 if 'throat' in out else edge[rc]
    rows, es = [], []
    for r in np.nonzero((z <= min(zt, z[rc]) - 0.005) & (z >= min(zt, z[rc]) - neck_band))[0]:
        c = np.nonzero(cls[r] == 1)[0]
        c = c[u[c] > ut] if len(c) else c
        if not len(c):
            continue
        c0 = c[0]
        lead = cls[r, max(0, c0 - int(0.02 * ppl)):c0]
        if np.isin(lead, (0, 4)).all():
            rows.append(r); es.append(u[c0])
    if len(rows) >= 8:
        rows, es = np.array(rows), np.array(es)
        cut = np.nonzero((np.diff(rows) > 2) | (np.abs(np.diff(es)) >= NECK_STEP))[0]   # the longest run of rows from
                                                                        # the throat down, ended at the neck's foot
        runs = np.split(np.arange(len(rows)), cut + 1)
        run = max(runs, key=len)
        if len(run) >= 8:
            rr, ee = rows[run], es[run]
            e = np.interp(np.arange(rr[0], rr[-1] + 1), rr, ee)
            ang = np.degrees(np.arctan(np.diff(e) * ppl))                    # 0: vertical (u per row, both in pixels)
            ang = gaussian_filter1d(ang, 0.006 * ppl)                       # (the drawing's and the raster's pixel steps)
            bend = np.abs(ang - gaussian_filter1d(ang, CREASE_SMOOTH * ppl, mode='nearest'))
            out['neck_bend_deg'] = round(float(bend.max()), 1)
            es = gaussian_filter1d(e, 0.004 * ppl, mode='nearest')          # (a pixel's step isn't a wiggle)
            out['neck_backtrack'] = round(float(np.abs(np.diff(es)).sum() - abs(es[-1] - es[0])), 4)
            zz = z[rr[0]:rr[-1] + 1]
            out['neck_wiggle'] = round(float(np.abs(es - np.polyval(np.polyfit(zz, es, 2), zz)).max()), 4)
            out['neck_edge'] = np.stack([z[rr[0]:rr[-1] + 1], e], 1)
    return out


def jaw_compare(D, O, ppl):
    """the jaw's checks: the design's measures D and ours O ({view: jaw_front / jaw_profile's}) -> checks."""
    C = {}
    df, of = D.get('front') or {}, O.get('front') or {}
    if 'chin' in df:
        zc = df['chin'][1]
        z = JAW_WIN['top'] - (np.arange(len(df['half'])) + 0.5) / ppl
        top = (df.get('taper') or {}).get('top')                  # (the rows the drawing's hair leaves in view)
        z_hi = JAW_ROWS[0] if top is None else min(JAW_ROWS[0], top)
        rows = np.nonzero((z <= z_hi) & (z >= zc))[0][::max(1, int(JAW_ROWS[1] * ppl))]
        ours = np.nan_to_num(of['half'][rows], nan=0.0) if 'half' in of else np.zeros(len(rows))
        d = ours - df['half'][rows]
        ok = np.isfinite(d)
        rms = float(np.sqrt(np.mean(d[ok] ** 2))) if ok.any() else None
        worst = int(np.argmax(np.abs(np.where(ok, d, 0))))
        C['jaw_taper'] = dict(value=round(rms, 4) if rms is not None else None, worst=[round(float(z[rows[worst]]), 3),
                              round(float(d[worst]), 4)], rows=[round(float(z_hi), 3), round(float(zc), 3)],
                              status=_grade(rms, JAW_TAPER))
        oc = of.get('chin')
        dz = None if oc is None else oc[1] - zc
        C['chin_point_z'] = dict(value=None if dz is None else round(dz, 4), design=zc, ours=None if oc is None else oc[1],
                                 status=_grade(dz, TAPER))
        rd, ro = df.get('rise'), of.get('rise')
        rr = ro / rd if rd and ro is not None else None
        C['chin_v'] = dict(value=None if rr is None else round(abs(rr - 1), 3), ratio=None if rr is None else
                           round(rr, 3), design=rd, ours=ro, status=_grade(None if rr is None else rr - 1, CHIN_V),
                           note="|ours' V's rise over the design's - 1| (the rise %.2f L either side of the chin point)"
                                % JAW_V)
        if df.get('chin_share') is not None and of.get('chin_share') is not None:
            q = of['chin_share'] - df['chin_share']
            old = None
            if df.get('face_w') and df.get('neck_w') and of.get('face_w') and of.get('neck_w'):
                old = round((of['neck_w'] / of['face_w']) / (df['neck_w'] / df['face_w']), 3)
            C['neck_to_face'] = dict(value=round(abs(q), 4), ours=of['chin_share'], design=df['chin_share'],
                                     widths_ratio=old, status=_grade(q, NECK_FACE),
                                     note="|ours - the design's| share of the figure's width the face takes over the "
                                          "rows %.2f L over the design's chin (a V chin over the neck reads low; a "
                                          "face running into a neck as wide as it, near 1); widths_ratio: the old "
                                          "measure (the neck's width %.1f L under the chin over the face's over it, "
                                          "over the design's)" % (SHARE_BAND, NECK_BELOW))
    for vn in ('front', 'three_quarter'):
        d_, o_ = D.get(vn) or {}, O.get(vn) or {}
        if d_.get('jaw_line_L'):
            q = (o_.get('jaw_line_L') or 0.0) / d_['jaw_line_L']
            qb = (o_.get('jaw_line_L_board') or 0.0) / d_['jaw_line_L'] if 'jaw_line_L_board' in o_ else None
            C['jaw_line_' + vn] = dict(value=round(q, 3), design=d_['jaw_line_L'], ours=o_.get('jaw_line_L'),
                                       board=None if qb is None else round(qb, 3),
                                       status='PASS' if q >= JAW_LINE[0] else 'WARN' if q >= JAW_LINE[1] else 'FAIL',
                                       note="ours' jaw line over the neck over the design's (L), in the level camera "
                                            "(board: the boards' camera)")
    h = hidden_compare(df.get('hidden'), of.get('extents'))
    if h:
        C['jaw_outline_hidden'] = h
    dp, op = D.get('profile') or {}, O.get('profile') or {}
    if dp.get('underside_deg') is not None:
        a = op.get('underside_deg')
        C['chin_underside'] = dict(value=None if a is None else round(abs(a - dp['underside_deg']), 1), ours=a,
                                   design=dp['underside_deg'], status=_grade(
            None if a is None else round(a - dp['underside_deg'], 1), UNDERSIDE),     # (graded as reported: 0.1 deg)
                                   note="|ours - the design's| underside angle in profile (deg)")
    if op.get('neck_bend_deg') is not None or 'chin' in op:
        b = op.get('neck_bend_deg')
        C['neck_front_wiggle'] = dict(value=b, design=dp.get('neck_bend_deg'), residual_L=op.get('neck_wiggle'),
                                      backtrack_L=op.get('neck_backtrack'), status=_grade(b, WIGGLE))
    return C


# ------------------------------------------------------------------------------------ the taper's shape: a V, not a U
# Michael (2026-09-30), the head sheet against the boards: the design's jaw lines run from the cheekbones to a sharp V
# chin; ours "rounds sharply into a broad, blunt, shallow chin: a U, not a V", and in three-quarter a hollow under the
# cheek and a notch where the jaw meets the neck. The row-by-row widths (jaw_taper) and the chin's height don't see a
# shape. These read the outline as a curve: in front its half-width w(t) from the cheekbone row (t 0) to the chin point
# (t 1) and its direction along its arc length (the arms' bends, the V's opening near the chin, how much of the V's turn
# its point makes); in three-quarter the far cheek's contour (a local hollow) and the near jaw line (a notch). Graded in
# the level camera, orthographic (the design's projection; Michael, 2026-09-30), each with the boards' camera's value
# beside it (what the boards show: 6 degrees over the chin, in perspective, which shortens the chin's V).
TAPER_TOP = (-0.05, 0.1)         # t 0: the design's widest row in view (its hair leaves it: _occluded) under the first z
                                 # and this far over its chin (on the head sheet -0.179, under the side locks' tips)
TAPER_T = 0.02                   # the taper curve's step in t
TAPER_SHAPE = (0.0141, 0.04)     # rms of w(t)/w(0) against the design's: PASS / WARN (face5 round 7, from the triple:
                                 # design 0.0032 / 0.0105 | widths 0.0251; was 0.025, the floor's median)
TAPER_START = 0.9                # the taper starts where w(t)/w(0) first falls under this
ARMS = (0.2, 0.95)               # t: the jaw lines (their straightness and bends): z -0.215 to -0.354 on the head
                                 # sheet, the window t 0.4-0.95 had been while t 0 sat on the hair's edge (-0.113)
ARC_STEP = 0.25                  # px: the outline resampled by arc length this often, smoothed over ARC_SMOOTH
ARC_SMOOTH = 0.003               # L (a pixel's steps)
ARM_SMOOTH = 0.006               # L: the jaw lines smoothed this much more before their bends are read (the sheet's
                                 # 401 px per L steps a pixel's direction by 5-10 degrees)
BEND_SMOOTH = 0.03               # L of arc: a bend is the direction less its smoothing over this
ARM_BEND = (6.0, 10.0)           # deg: the jaw lines' sharpest local bend (a kink where the silhouette jumps in depth;
                                 # the design's own 4.4)
CHIN_ARMS = (0.06, 0.12)         # L of arc from the chin point: the V's arms, fitted as lines
CHIN_ANGLE = (1.45, 20.0)        # deg: |ours - design| of the V's opening between them (face5 round 7, from the
                                 # triple: design 0 / 0 | affine 4.8, widths 2.9, other_view 12.0; was 10)
TIP_ARC = 0.02                   # L of arc either side of the chin point: the V's point
TIP_SHARE = (0.7, 0.55)          # the share of the V's turn its point makes: PASS / WARN at least (a U turns all
                                 # the way round its bottom; the design's arms run straight to within TIP_ARC of it)
TQ_TOP = -0.12                   # z: the three-quarter's far contour read from the chin up to here
HOLLOW_ARC = 0.05                # L of arc either side: the far contour's local chord
TQ_HOLLOW = (0.005, 0.008)       # L: the far contour's deepest local hollow (inside its local chord)
TQ_NOTCH = (0.008, 0.016)        # L: the near jaw line's largest drop under its own rise
NOTCH_JUMP = 0.05                # L: the near jaw line ends where the next column's foot jumps this far (hair, a gap)
# Where the drawing's hair covers the face's edge (Michael, 2026-09-30: the head sheet's side locks overlap the face at
# z -0.14 to -0.18, and the outline followed the locks' edges). Hair can only hide skin, and the face's outline widens
# from the chin up to the cheekbone, so going up a side from the chin the visible edge first falls back where a lock's tip
# crosses it; from there up the edge is the hair's (the locks' inner edges), not the face's. The hair also hangs *behind*
# the jaw (the drawing's jaw line is drawn over it down to z -0.3), so hair beside the edge alone marks nothing.
OCC_DROP = 0.006                 # L: a side's visible extent this far under its running maximum from the chin up ...
OCC_REACH = 0.03                 # ... with hair within this far beyond the edge (at that row or OCC_MARGIN either side):
OCC_MARGIN = 0.008               # the lock's tip; the rows from this far under it up are dropped (its ink meets the jaw
                                 # line's a few pixels before the edge falls back)


def face_outline(cls, ppl, win=JAW_WIN, seeds=FACE_SEEDS):
    """the face region's outline (the skin reached from the seeds, the ink its walls, holes filled) as a closed
    polyline by marching squares, and the chin point (jaw_front's) -> (X (n, 2) (u, z) L, chin (u, z)) or None."""
    from scipy import ndimage
    from skimage import measure as skm
    face = ndimage.binary_fill_holes(_region(cls, seeds, ppl, win))
    M = jaw_front(cls, ppl, win=win, seeds=seeds)
    if not face.any() or 'chin' not in M:
        return None
    c = max(skm.find_contours(np.pad(face, 1).astype(float), 0.5), key=len) - 1
    return np.stack([(c[:, 1] + 0.5) / ppl - win['x'], win['top'] - (c[:, 0] + 0.5) / ppl], 1), M['chin']


def _walk(X, i0, dirn, stop):
    """indices along a closed polyline from i0 one way (dirn +-1) until stop(point)."""
    out, j, n = [], i0, len(X)
    for _ in range(n):
        if stop(X[j]):
            break
        out.append(j)
        j = (j + dirn) % n
    return out


def _by_arc(P, ppl, anchor=None):
    """a polyline resampled by arc length (ARC_STEP px) and smoothed (ARC_SMOOTH) -> (points, step L). anchor: the index
    of a point the samples keep (the grid's phase set there, not at the line's start: the chin's measures then don't
    move with where the outline is cut)."""
    from scipy.ndimage import gaussian_filter1d
    s = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(P, axis=0).T))])
    step = ARC_STEP / ppl
    if anchor is None:
        sg = np.arange(0.0, s[-1] + 1e-12, step)
    else:
        sa = s[anchor]
        sg = sa + step * np.arange(-np.floor(sa / step + 1e-9), np.floor((s[-1] - sa) / step + 1e-9) + 1)
    Q = np.stack([np.interp(sg, s, P[:, 0]), np.interp(sg, s, P[:, 1])], 1)
    return gaussian_filter1d(Q, ARC_SMOOTH / step, axis=0, mode='nearest'), step


def _direction(Q):
    """the direction of a polyline (degrees, unwrapped) at each point."""
    d = np.gradient(Q, axis=0)
    return np.degrees(np.unwrap(np.arctan2(d[:, 1], d[:, 0])))


def _extents(cls, ppl, chin, win=JAW_WIN, seeds=FACE_SEEDS):
    """per row above the chin, the face region's extent either side of the chin's column, scanned out from it through
    the region with its holes filled (the mouth's and the nose's lines closed over: the scan had stopped on the mouth's
    line and read its rows 0.01-0.08 L wide), and whether hair lies within OCC_REACH beyond each end
    -> (z (rows), left, right (L; nan off the face), hair left, hair right)."""
    from scipy import ndimage
    from .bodyqa import CLASS
    face = ndimage.binary_fill_holes(_region(cls, seeds, ppl, win))
    H, W = cls.shape
    z = win['top'] - (np.arange(H) + 0.5) / ppl
    u = (np.arange(W) + 0.5) / ppl - win['x']
    uc, zc = chin
    c0 = int(round((uc + win['x']) * ppl - 0.5))
    xl, xr = np.full(H, np.nan), np.full(H, np.nan)
    hl, hr = np.zeros(H, bool), np.zeros(H, bool)
    hair = cls == CLASS['hair']
    k = max(1, int(round(OCC_REACH * ppl)))
    for r in range(H):
        if z[r] < zc - 0.5 / ppl or not face[r, c0]:
            continue
        run = face[r]
        a = c0
        while a > 0 and run[a - 1]:
            a -= 1
        b = c0
        while b < W - 1 and run[b + 1]:
            b += 1
        xl[r], xr[r] = uc - u[a] + 0.5 / ppl, u[b] - uc + 0.5 / ppl
        hl[r], hr[r] = hair[r, max(0, a - k):a].any(), hair[r, b + 1:b + 1 + k].any()
    return z, xl, xr, hl, hr


def _occluded(z, x, hair, zc, ppl):
    """where a side's edge goes under the drawing's hair (see OCC_DROP): from the chin up, the first row whose visible
    extent falls OCC_DROP under its running maximum with hair beyond the edge there (or within OCC_MARGIN of it) -> the
    highest row still the face's own edge (z: that row less OCC_MARGIN), or None (the edge is the face's throughout)."""
    rows = np.nonzero(np.isfinite(x) & (z >= zc - 0.5 / ppl))[0][::-1]          # from the chin up
    if not len(rows):
        return None
    m = np.maximum.accumulate(x[rows])
    k = int(round(OCC_MARGIN * ppl))
    for i in np.nonzero(x[rows] < m - OCC_DROP)[0]:
        r = rows[i]
        if hair[max(0, r - k):r + k + 1].any():
            return float(z[r] - OCC_MARGIN)
    return None


def _half_widths(cls, ppl, chin, win=JAW_WIN, seeds=FACE_SEEDS):
    """the face's half-width either side of the chin's column per row (_extents), nan where the drawing's hair covers
    that side's edge (_occluded: from a lock's tip up) -> (z (rows), left, right (L), top (the highest row whose both
    edges are the face's own, or None))."""
    z, xl, xr, hl, hr = _extents(cls, ppl, chin, win, seeds)
    tops = [t for t in (_occluded(z, xl, hl, chin[1], ppl), _occluded(z, xr, hr, chin[1], ppl)) if t is not None]
    top = min(tops) if tops else None
    if top is not None:
        xl, xr = np.where(z <= top, xl, np.nan), np.where(z <= top, xr, np.nan)
    return z, xl, xr, top


def taper_front(cls, ppl, z0=None, win=JAW_WIN, seeds=FACE_SEEDS):
    """the front's lower outline, from the cheekbone row z0 (default: the picture's own, its widest row under
    TAPER_TOP[0] and TAPER_TOP[1] over its chin) to the chin point -> dict:
      t, r        the taper curve: w(t) / w(0) on t = 0..1 (TAPER_T), w the half-width, t = (z0 - z) / (z0 - chin);
      w0, w90     the half-width at t 0 and 0.9 (L); start: the t where r first falls under TAPER_START;
      arms        per side ('L' the picture's left, 'R'), over t in ARMS: a line's fit (rms, orthogonal, L), its bow (the
                  mean distance from the chord, + outward: convex) and its sharpest local bend (degrees: the direction
                  less its smoothing over BEND_SMOOTH of arc) and where (z);
      chin_angle  the V's opening between its arms fitted as lines CHIN_ARMS of arc from the chin point (degrees);
      tip_share   how much of the V's turn (180 less the opening) the outline makes within TIP_ARC of the chin point;
      outline     the lower outline by arc length (u, z)."""
    got = face_outline(cls, ppl, win, seeds)
    if got is None:
        return None
    X, (uc, zc) = got
    z, xl, xr, top = _half_widths(cls, ppl, (uc, zc), win, seeds)
    w = 0.5 * (xl + xr)
    if z0 is None:                                     # the widest row the drawing shows (lowest of the ties)
        sel = (z <= TAPER_TOP[0]) & (z >= zc + TAPER_TOP[1]) & np.isfinite(w)
        if not sel.any():
            return None
        z0 = float(z[sel][np.nonzero(w[sel] >= np.nanmax(w[sel]) - 1e-9)[0].max()])
    t = (z0 - z) / (z0 - zc)
    ok = np.isfinite(w) & (t >= -1e-9) & (t <= 1 + 1e-9)
    if ok.sum() < 10:
        return None
    o = np.argsort(t[ok])
    tg = np.arange(0.0, 1.0 + 1e-9, TAPER_T)
    wg = np.interp(tg, t[ok][o], w[ok][o])
    wg[-1] = 0.0                                                   # (the chin point)
    wg[tg < t[ok].min() - 1.5 / ppl / (z0 - zc)] = np.nan          # (over this picture's visible rows: not compared)
    r = wg / wg[0]
    below = np.nonzero(r < TAPER_START)[0]
    out = dict(z0=round(z0, 4), chin=(round(float(uc), 4), round(float(zc), 4)), t=tg, r=r, w0=round(float(wg[0]), 4),
               w90=round(float(np.interp(0.9, tg, wg)), 4), start=round(float(tg[below[0]]), 3) if len(below) else None,
               top=None if top is None else round(top, 4))
    # the outline under z0, from the picture's left through the chin to its right, by arc length
    i0 = int(np.argmin(np.hypot(X[:, 0] - uc, X[:, 1] - zc)))
    a, b = _walk(X, i0, -1, lambda p: p[1] > z0), _walk(X, i0, 1, lambda p: p[1] > z0)
    P = X[a[::-1] + b[1:]]
    if len(P) < 10:
        return out
    ia = len(a) - 1                                                # (the chin's point in P)
    if P[0, 0] > P[-1, 0]:
        P, ia = P[::-1], len(P) - 1 - ia
    Q, step = _by_arc(P, ppl, ia)
    psi = _direction(Q)
    from scipy.ndimage import gaussian_filter1d
    k0 = int(np.argmin(np.hypot(Q[:, 0] - uc, Q[:, 1] - zc)))
    out['outline'] = Q
    z_hi, z_lo = z0 - ARMS[0] * (z0 - zc), z0 - ARMS[1] * (z0 - zc)
    arms = {}
    for side, idx in (('L', np.arange(0, k0)), ('R', np.arange(k0 + 1, len(Q)))):
        idx = idx[(Q[idx, 1] <= z_hi) & (Q[idx, 1] >= z_lo)]
        if len(idx) < 8:
            continue
        A = Q[idx]
        c = A.mean(0)
        e = np.linalg.svd(A - c)[2][0]
        res = (A - c) @ np.array([-e[1], e[0]])
        p0, p1 = A[np.argmax(A[:, 1])], A[np.argmin(A[:, 1])]
        tc = (p1 - p0) / max(np.linalg.norm(p1 - p0), 1e-12)
        nrm = np.array([-tc[1], tc[0]])
        if nrm[0] * (p0[0] - uc) < 0:                              # outward: away from the chin's column
            nrm = -nrm
        As = gaussian_filter1d(A, ARM_SMOOTH / step, axis=0, mode='nearest')      # (on the arm alone: the hair
        pa = _direction(As)                                                      # over the cheek stays out)
        bd = np.abs(pa - gaussian_filter1d(pa, BEND_SMOOTH / step, mode='nearest'))
        m = min(int(0.01 / step), len(bd) // 4)
        k = m + int(np.argmax(bd[m:len(bd) - m]))
        arms[side] = dict(rms=round(float(np.sqrt(np.mean(res ** 2))), 4), bow=round(float(np.mean((A - p0) @ nrm)), 4),
                          bend=round(float(bd[k]), 1), bend_z=round(float(As[k, 1]), 3))
    out['arms'] = arms
    # the chin: the V's arms as lines CHIN_ARMS of arc either side of its point; the turn its point makes
    n0, n1 = int(round(CHIN_ARMS[0] / step)), int(round(CHIN_ARMS[1] / step))
    nt = int(round(TIP_ARC / step))
    if k0 - n1 >= 0 and k0 + n1 < len(Q):
        rise = []
        for seg in (Q[k0 - n1:k0 - n0 + 1], Q[k0 + n0:k0 + n1 + 1]):
            e = np.linalg.svd(seg - seg.mean(0))[2][0]
            rise.append(math.degrees(math.atan2(abs(e[1]), abs(e[0]))))    # each arm's angle over the horizontal
        opening = 180.0 - sum(rise)
        out['chin_angle'] = round(opening, 1)
        out['chin_arms'] = [round(v, 1) for v in rise]
        turn = abs(psi[k0 + nt] - psi[k0 - nt])
        out['tip_share'] = round(float(turn / max(sum(rise), 1e-6)), 3)
    return out


def tq_jaw(cls, ppl, facing=-1, win=JAW_WIN, seeds=FACE_SEEDS, top=None):
    """a three-quarter's jaw -> dict:
      hollow      the far contour (from the chin up, on the facing side, to TQ_TOP, to where the drawing's hair covers
                  its edge (_occluded: the head sheet's lock crosses the far cheek at z -0.146, and its tip had read as
                  the design's own hollow) and to `top` (the design's, so both are read on the same rows), whichever is
                  lowest: 'top') its deepest local hollow: how far a point lies inside the chord between the points
                  HOLLOW_ARC of arc either side (L, + a hollow), and where (z); curv: its most concave signed curvature
                  (1/L, - concave);
      notch       the near jaw line (per column from the chin away from the facing side, the face's foot: its lowest skin
                  before ink or another class, from under the mouth) its largest drop under its own running maximum (L),
                  and where (u from the chin); line: [(du, z)] (to where a column's foot jumps NOTCH_JUMP: hair, a gap)."""
    got = face_outline(cls, ppl, win, seeds)
    if got is None:
        return None
    X, (uc, zc) = got
    out = dict(chin=(round(float(uc), 4), round(float(zc), 4)))
    i0 = int(np.argmin(np.hypot(X[:, 0] - uc, X[:, 1] - zc)))
    n = len(X)
    far = max((-1, 1), key=lambda d: facing * X[(i0 + 12 * d) % n, 0])       # the way round toward the facing side
    z_, xl, xr, hl, hr = _extents(cls, ppl, (uc, zc), win, seeds)
    occ = _occluded(z_, xl, hl, zc, ppl) if facing < 0 else _occluded(z_, xr, hr, zc, ppl)
    zt = min([TQ_TOP] + [v for v in (occ, top) if v is not None])
    out['top'] = round(float(zt), 4)
    idx = _walk(X, i0, far, lambda p: p[1] > zt)
    if len(idx) > 10:
        Q, step = _by_arc(X[idx], ppl)
        m = int(round(HOLLOW_ARC / step))
        if len(Q) > 2 * m + 2:
            A, Bp, C = Q[:-2 * m], Q[2 * m:], Q[m:-m]
            t = Bp - A
            t = t / np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-12)
            nrm = np.stack([-t[:, 1], t[:, 0]], 1)
            nrm = np.where((nrm[:, :1] * -facing) > 0, nrm, -nrm)   # inward: toward the face (away from its facing side)
            dev = np.einsum('ij,ij->i', C - A, nrm)
            k = int(np.argmax(dev))
            from scipy.ndimage import gaussian_filter1d
            psi = np.radians(gaussian_filter1d(_direction(Q), HOLLOW_ARC / step / 2, mode='nearest'))
            kap = np.gradient(psi) / step
            s = np.sign(np.median(kap)) or 1.0                     # (the contour's own convex turning: +)
            out['hollow'] = round(float(dev[k]), 4)
            out['hollow_z'] = round(float(C[k, 1]), 3)
            out['curv'] = round(float(np.min(s * kap[m:-m])), 2)
            out['far'] = Q
    # the near jaw line, column by column
    skin = cls == 1
    H, W = cls.shape
    z = win['top'] - (np.arange(H) + 0.5) / ppl
    rs = int(round((win['top'] - SCAN_TOP) * ppl - 0.5))
    c0 = int(round((uc + win['x']) * ppl - 0.5))
    line, prev = [], None
    for c in range(c0, W) if facing < 0 else range(c0, -1, -1):
        if not skin[rs, c]:
            break
        stop = np.nonzero(~skin[rs:, c])[0]
        if not len(stop):
            break
        zf = float(z[rs + stop[0] - 1])
        if prev is not None and abs(zf - prev) > NOTCH_JUMP:
            break
        line.append((abs(c - c0) / ppl, zf))
        prev = zf
    if len(line) > 5:
        L_ = np.array(line)
        drop = np.maximum.accumulate(L_[:, 1]) - L_[:, 1]
        k = int(np.argmax(drop))
        out['notch'] = round(float(drop[k]), 4)
        out['notch_du'] = round(float(L_[k, 0]), 3)
        out['line'] = L_
    return out


def taper_compare(D, O, Ob=None):
    """the taper's checks: the design's taper_front / tq_jaw measures D ({'front': , 'three_quarter': }) against ours O
    (the level camera's: the design's projection, graded; Michael, 2026-09-30), Ob (the boards' camera's, shown beside
    as 'board') -> checks."""
    C = {}
    df, of = D.get('front'), O.get('front')
    bf = (Ob or {}).get('front') or {}

    def shape_rms(o):
        if o is None or o.get('r') is None:
            return None, None
        dr = o['r'] - df['r']
        ok = np.isfinite(dr)                                       # (the t both pictures show)
        if not ok.any():
            return None, None
        return float(np.sqrt(np.mean(dr[ok] ** 2))), int(np.argmax(np.where(ok, np.abs(dr), -1.0)))
    if df and of:
        rms, k = shape_rms(of)
        brd = shape_rms(bf)[0] if bf else None
        C['jaw_taper_shape'] = dict(value=None if rms is None else round(rms, 4),
                                    worst=None if k is None else [round(float(df['t'][k]), 2),
                                                                  round(float(of['r'][k] - df['r'][k]), 4)],
                                    start=[of.get('start'), df.get('start')], w0=[of['w0'], df['w0']],
                                    top=df.get('top'), board=None if brd is None else round(brd, 4),
                                    status=_grade(rms, TAPER_SHAPE),
                                    note='rms of w(t)/w(0), t 0 at the design\'s widest row its hair leaves in view %.3f, 1 '
                                         'at the chin, in the level camera (board: the boards\' camera); worst [t, ours - '
                                         'design]; start [ours, design]: where it first falls under %.1f' % (
                                             df['z0'], TAPER_START))
        if of.get('arms') and df.get('arms'):
            b = max(a['bend'] for a in of['arms'].values())
            bb = max(a['bend'] for a in bf['arms'].values()) if bf.get('arms') else None
            C['jaw_line_bend'] = dict(value=b, board=bb, design=max(a['bend'] for a in df['arms'].values()),
                                      arms=of['arms'], arms_board=bf.get('arms'), arms_design=df['arms'],
                                      status=_grade(b, ARM_BEND),
                                      note='the jaw lines (t %.2f-%.2f) sharpest local bend (deg), in the level camera '
                                           '(board: the boards\' camera); per side a line fit\'s rms (L) and bow (L, + '
                                           'convex)' % ARMS)
        if of.get('chin_angle') is not None and df.get('chin_angle') is not None:
            d = of['chin_angle'] - df['chin_angle']
            C['chin_angle'] = dict(value=round(abs(d), 1), ours=of['chin_angle'], design=df['chin_angle'],
                                   arms=of.get('chin_arms'), board=bf.get('chin_angle'), w90=[of['w90'], df['w90']],
                                   status=_grade(round(d, 1), CHIN_ANGLE),     # (graded as reported: 0.1 deg)
                                   note="|ours - the design's| V opening between its arms %.2f-%.2f L of arc from the "
                                        "chin point (deg), in the level camera (board: ours in the boards' camera); "
                                        'w90 [ours, design]: the half-width at t 0.9 (L)' % CHIN_ARMS)
        if of.get('tip_share') is not None and df.get('tip_share') is not None:
            v = of['tip_share']
            C['chin_tip'] = dict(value=v, design=df['tip_share'], board=bf.get('tip_share'),
                                 status='PASS' if v >= TIP_SHARE[0] else 'WARN' if v >= TIP_SHARE[1] else 'FAIL',
                                 note="the share of the V's turn made within %.3f L of arc of its point (1 a sharp V, "
                                      "low a round U), in the level camera (board: the boards' camera)" % TIP_ARC)
    dq, oq = D.get('three_quarter'), O.get('three_quarter')
    bq = (Ob or {}).get('three_quarter') or {}
    if dq and oq:
        if oq.get('hollow') is not None:
            h = oq['hollow']
            C['tq_cheek_hollow'] = dict(value=h, board=bq.get('hollow'), z=oq.get('hollow_z'), z_board=bq.get('hollow_z'),
                                        curv=oq.get('curv'), design=dq.get('hollow'), status=_grade(max(0.0, h), TQ_HOLLOW),
                                        note='the far cheek contour\'s deepest local hollow inside its chord over %.2f L of arc '
                                             'either side (L), in the level camera (board: the boards\' camera); curv: its '
                                             'most concave curvature (1/L)' % HOLLOW_ARC)
        if oq.get('notch') is not None:
            nn = oq['notch']
            C['tq_jaw_notch'] = dict(value=nn, board=bq.get('notch'), du=oq.get('notch_du'), du_board=bq.get('notch_du'),
                                     design=dq.get('notch'), status=_grade(nn, TQ_NOTCH),
                                     note="the near jaw line's largest drop under its own rise from the chin (L), in the "
                                          "level camera (board: the boards' camera): a notch or step where the jaw meets "
                                          "the neck")
    return C


# ------------------------------------------------------------ the face's outline under the hair: head_construction
# Michael (2026-09-30): the head sheet's side locks cover the face's edge from z -0.179 up, and the face runs on under
# them, widening to the cheek under the ear, where our fit had followed the locks' tips in. head_construction (the bald
# head, front and profile) draws that outline. Measured against the head sheet where both show the face (face round 5):
# its face is 0.030 L longer (the chin lower) and its widths 0.036 L wider on those rows as drawn; registered on the
# chin (its rows scaled about the eye line so its chin meets the sheet's) and its widths by one factor fitted over those
# rows, it reads the sheet's outline to a few thousandths of L. So it is the authority for the front outline from the
# sheet's hair-occlusion row up to its own widest row under the eyes (the jaw's side, the ramus in front of the ear),
# the sheet where the sheet shows the face. Both read by their region's outermost extent per row (_outer): a scan from
# the chin's column stops where an eye's lines meet the region's edge.
CONS_REF = 'head_construction'
HIDDEN = (0.006, 0.01)           # L: PASS / WARN for ours against head_construction's outline under the sheet's hair (rms):
                                 # the two references agree to 0.002 where both show the face (registered), so PASS within
                                 # 3x that; the flagged head (pipeline-3d d60486a, the face curving in under the locks)
                                 # reads 0.011, FAIL
HIDDEN_DZ = 0.0025               # L: the rows compared
HIDDEN_ZMAX = 0.05               # z: construction_front's rows run up to here (the head's fit reads them past the check's)
HIDDEN_FLAG = ("the face curving in where the head sheet's hair covers its edge (Michael, 2026-09-30): the outline "
               "there is head_construction's")


def _outer(cls, ppl, chin, win=JAW_WIN, seeds=FACE_SEEDS):
    """per row from the chin up, the face region's (holes filled) outermost extent either side of the chin's column:
    the outline itself, which the scan from the chin's column (_extents) loses where an eye's lines meet the region's
    edge -> (z (rows), left, right (L; nan off the face))."""
    from scipy import ndimage
    face = ndimage.binary_fill_holes(_region(cls, seeds, ppl, win))
    H, W = cls.shape
    z = win['top'] - (np.arange(H) + 0.5) / ppl
    u = (np.arange(W) + 0.5) / ppl - win['x']
    xl, xr = np.full(H, np.nan), np.full(H, np.nan)
    for r in np.nonzero(face.any(1) & (z >= chin[1] - 0.5 / ppl))[0]:
        c = np.nonzero(face[r])[0]
        xl[r], xr[r] = chin[0] - u[c[0]] + 0.5 / ppl, u[c[-1]] - chin[0] + 0.5 / ppl
    return z, xl, xr


def _rows_on(z, v, zg):
    """a per-row series (z descending or not) on the rows zg, nan outside its finite rows."""
    ok = np.isfinite(v)
    if ok.sum() < 2:
        return np.full(len(zg), np.nan)
    o = np.argsort(z[ok])
    return np.interp(zg, z[ok][o], v[ok][o], left=np.nan, right=np.nan)


def construction_front(spec, eye_x, facing, chin, top, cls_t, ppl_t):
    """head_construction's front outline registered on the head sheet's front (its chin `chin`, its hair-occlusion row
    `top`, its classes cls_t at ppl_t) -> dict(z (rows, L, up to HIDDEN_ZMAX), xl, xr (the half-widths either side of the
    chin's column, L; nan off the face), rows [top, the construction's widest row under the eyes]: where the check
    compares, sz (its rows'
    scale about the eye line: the chins meet), sx (its widths' scale, fitted over the rows both show), fit (the rms of the
    registered half-widths against the sheet's there; fit_raw unregistered), outline (its registered outline (u, z))),
    or None without the reference."""
    from . import manifest, refcheck
    M = manifest.load(spec['ref']['manifest'])['references']
    if CONS_REF not in M:
        return None
    Vc, pc = design_jaw_views(refcheck._load(M[CONS_REF]['path']), eye_x, facing, which=('front',))
    clsc = Vc['front']['cls']
    chc = jaw_front(clsc, pc)['chin']
    zc, cl, cr = _outer(clsc, pc, chc)
    zt, tl, tr = _outer(cls_t, ppl_t, chin)
    sz = chin[1] / chc[1]
    zg = np.arange(chin[1], HIDDEN_ZMAX + 1e-9, HIDDEN_DZ)
    cl_r, cr_r = _rows_on(zc * sz, cl, zg), _rows_on(zc * sz, cr, zg)
    cl_o, cr_o = _rows_on(zc, cl, zg), _rows_on(zc, cr, zg)
    tl_g, tr_g = _rows_on(zt, tl, zg), _rows_on(zt, tr, zg)
    shown = (zg >= chin[1] + 0.01) & (zg <= (top if top is not None else TAPER_TOP[0]))
    wt, wc = 0.5 * (tl_g + tr_g), 0.5 * (cl_r + cr_r)
    ok = shown & np.isfinite(wt) & np.isfinite(wc)
    if ok.sum() < 10:
        return None
    sx = float(np.sum(wt[ok] * wc[ok]) / np.sum(wc[ok] ** 2))
    fit = float(np.sqrt(np.mean((sx * wc[ok] - wt[ok]) ** 2)))
    okr = shown & np.isfinite(wt) & np.isfinite(cl_o + cr_o)
    fit_raw = float(np.sqrt(np.mean((0.5 * (cl_o + cr_o)[okr] - wt[okr]) ** 2)))
    rows = None
    if top is not None:
        up = (zg > top) & (zg <= TAPER_TOP[0] + 1e-9) & np.isfinite(wc)
        if up.any():
            k = np.nonzero(up)[0][np.argmax(wc[up])]
            rows = [round(float(top), 4), round(float(zg[k]), 4)]
    X = face_outline(clsc, pc)
    return dict(z=zg, xl=sx * cl_r, xr=sx * cr_r, rows=rows, sz=round(sz, 4), sx=round(sx, 4), fit=round(fit, 4),
                fit_raw=round(fit_raw, 4), chin=chc, ppl=round(pc, 1),
                outline=None if X is None else X[0] * np.array([sx, sz]))


def hidden_compare(H, E):
    """the front outline under the head sheet's hair: ours (E: _outer of ours, level, hair hidden: dict z, xl, xr)
    against head_construction's registered outline (H: construction_front's) over its rows -> the check or None."""
    if not H or not H.get('rows') or not E:
        return None
    lo, hi = H['rows']
    sel = (H['z'] > lo) & (H['z'] <= hi + 1e-9)
    zz = zr = H['z'][sel]
    # the half-width: the mean of the two sides (the full width over 2), so the drawing's chin off its face's middle
    # (the construction's by 0.004 L, the sheet's 0.013) isn't read as a side too wide and the other too narrow
    d = 0.5 * (_rows_on(E['z'], E['xl'], zz) + _rows_on(E['z'], E['xr'], zz)) - 0.5 * (H['xl'][sel] + H['xr'][sel])
    ok = np.isfinite(d)
    if ok.sum() < 5:
        return None
    rms = float(np.sqrt(np.mean(d[ok] ** 2)))
    k = int(np.argmax(np.where(ok, np.abs(d), -1.0)))
    from .registry import flag_check
    return flag_check(dict(value=round(rms, 4), mean=round(float(np.mean(d[ok])), 4),
                           worst=[round(float(zr[k]), 3), round(float(d[k]), 4)], rows=[lo, hi], fit=H['fit'],
                           sx=H['sx'], sz=H['sz'], status=_grade(rms, HIDDEN),
                           note="ours' front half-width (level, hair hidden; the two sides' mean) against "
                                "head_construction's outline (its "
                                "rows scaled so its chin meets the head sheet's, its widths by sx, fitted where both "
                                "show the face: fit, rms L) from the head sheet's hair-occlusion row to the "
                                "construction's widest row under the eyes (rows, z): rms L, mean (+ ours wider), worst "
                                "[z, ours - design]"), HIDDEN_FLAG)


def design_jaw(spec, eye_x):
    """the head sheet's jaw measures -> ({view: measures}, ppl, {view: class image}, {view: azimuth}); the front's and
    the three-quarter's taper (taper_front, tq_jaw) under 'taper'."""
    from . import refcheck
    fs = spec['ref']['face_sheet']
    views, ppl = design_jaw_views(refcheck._load(fs['image']), eye_x, fs.get('facing', -1))
    D = {vn: jaw_profile(v["cls"], ppl, neck_band=DESIGN_NECK_BAND) if vn == 'profile' else jaw_front(v['cls'], ppl)
         for vn, v in views.items()}
    if 'front' in views:
        D['front']['taper'] = taper_front(views['front']['cls'], ppl)
        if D['front'].get('chin') and D['front']['taper']:
            D['front']['hidden'] = construction_front(spec, eye_x, fs.get('facing', -1), D['front']['chin'],
                                                      D['front']['taper'].get('top'), views['front']['cls'], ppl)
    if 'three_quarter' in views:
        D['three_quarter']['taper'] = tq_jaw(views['three_quarter']['cls'], ppl, fs.get('facing', -1))
    return D, ppl, {vn: v['cls'] for vn, v in views.items()}, {vn: v['az'] for vn, v in views.items()}


def eye_anchor(iris, eye_z):
    """the iris centres (world, one row per eye) set on the head's eye line: the eyes' point the QA registers ours on,
    level with the head frame's eye line (the design's eye row, which the head is built on). The iris plates' vertex mean
    sits 0.0235 L over it on the authored head (their visible centre 0.018 L), which read every measure under the eyes
    that much low against the design's."""
    P = np.array(iris, float)
    P[:, 2] = eye_z
    return P


def bare(meshes):
    """a scene's meshes without its hair (the objects all hair class: the pieces, and an accessory drawn as hair)."""
    from .bodyqa import CLASS
    return [m for m in meshes if not (np.asarray(m[2]) == CLASS['hair']).all()]


def ours_jaw(meshes, skin, iris, eye_z, L, ppl, az, design_chin=None, design_z0=None, facing=-1, design_tq_top=None):
    """our jaw measures from a scene (meshes [(V, T, class)], skin (V, T) for the outline, the iris centres (world), the
    eye line's z), each view at its azimuth az {view: degrees}, registered on the eyes at the head's eye line
    (eye_anchor), in two cameras: the jaw's lines (does the jaw line draw over the neck, in front and three-quarter) in
    the boards' camera, as the boards show them; its shape (the outline, the chin, the V, the widths, the profile's
    underside and neck) in a level camera far out (LEVEL_CAM), as the design is drawn: the boards' look down 6 degrees at
    the chin in perspective, which alone raises the V's arms 0.01 L and narrows the cheeks, further back than the eyes,
    by 5%. The outline's shape (the taper: taper_front from design_z0, the design's widest row in view; tq_jaw up to
    design_tq_top, the design's far cheek in view; and the front's half-widths per row) is read with the hair hidden
    (bare): the face's own edge, as the design's is read only where its hair leaves it in view. In both cameras: 'taper'
    the boards', 'taper_level' the level's -> ({view: measures}, {view: the board's classes}, {view: the level's
    classes})."""
    iris = eye_anchor(iris, eye_z)
    O, P, Q = {}, {}, {}
    nohair = bare(meshes)
    for vn, a in az.items():
        ref = iris[np.argmax(iris[:, 0])] if vn == 'profile' else iris.mean(0)
        cams = {}
        for cam, cfg in (('board', BOARD_CAM), ('level', LEVEL_CAM)):
            target = np.array([0.0, 0.0, eye_z + cfg['lift'] * L])
            cams[cam] = board_view(meshes, skin, a, target, ref, L, ppl, dist=cfg['dist'])[0]
            if vn != 'profile':
                cams[cam + '_bare'] = (cams[cam] if len(nohair) == len(meshes) else
                                       board_view(nohair, skin, a, target, ref, L, ppl, dist=cfg['dist'])[0])
        P[vn], Q[vn] = cams['board'], cams['level']
        if vn == 'profile':
            O[vn] = jaw_profile(cams['level'], ppl)
        else:
            M = jaw_front(cams['level'], ppl, design_chin if vn == 'front' else None)
            Mb = jaw_front(cams['board'], ppl)
            M.update(jaw_line_L_board=Mb['jaw_line_L'], jaw_cols_board=Mb['jaw_cols'])
            if vn == 'front':
                Mlb = jaw_front(cams['level_bare'], ppl)
                M['half'] = Mlb['half']
                if Mlb.get('chin'):
                    ze, xl, xr = _outer(cams['level_bare'], ppl, Mlb['chin'])
                    M['extents'] = dict(z=ze, xl=xl, xr=xr)
                M['taper'] = taper_front(cams['board_bare'], ppl, design_z0)
                M['taper_level'] = taper_front(cams['level_bare'], ppl, design_z0)
            else:
                M['taper'] = tq_jaw(cams['board_bare'], ppl, facing, top=design_tq_top)
                M['taper_level'] = tq_jaw(cams['level_bare'], ppl, facing, top=design_tq_top)
            O[vn] = M
    return O, P, Q


def taper_checks(D, O):
    """the taper's checks from design_jaw's and ours_jaw's measures."""
    pick = lambda M, k: {vn: (M.get(vn) or {}).get(k) for vn in ('front', 'three_quarter')}
    return taper_compare(pick(D, 'taper'), pick(O, 'taper_level'), pick(O, 'taper'))


def jaw(B):
    """the jaw's checks on a built character: the scene (qa3d.scene_classes) in the board camera against the head
    sheet -> (table, checks)."""
    from . import qa3d
    Dz = qa3d.Design(B)
    ex = B.assembly['eye_knobs']['x']
    D, ppl, _, az = Dz.memo(design_jaw, B.spec, ex)
    meshes, _ = qa3d.scene_classes(B)
    V, T, _, _ = B.skin().mesh('masked')
    z0 = ((D.get('front') or {}).get('taper') or {}).get('z0')
    O = ours_jaw(meshes, (V, T), qa3d.iris_centres(B), float(B.assembly['eye_z']), float(B.assembly['L']), ppl, az,
                 (D.get('front') or {}).get('chin', (0, None))[1], z0,
                 (B.spec.get('ref') or {}).get('face_sheet', {}).get('facing', -1),
                 ((D.get('three_quarter') or {}).get('taper') or {}).get('top'))[0]
    C = jaw_compare(D, O, ppl)
    C.update(taper_checks(D, O))

    arr = lambda v: isinstance(v, np.ndarray)
    slim = lambda M: {vn: {k: ({a: b for a, b in v.items() if not arr(b)} if isinstance(v, dict) else v)
                           for k, v in m.items() if not arr(v)} for vn, m in M.items()}
    return dict(design=slim(D), ours=slim(O)), C


def measure(B):
    """-> (table, checks)."""
    T, C = {}, {}
    H = eye_hollow(B)
    T['hollow'] = H
    for side, h in H.items():
        C['eye_hollow_' + side] = dict(value=h['hollow'], status=_grade(h['hollow'], HOLLOW) if h['hollow'] is not None
                                       and h['hollow'] > 0 else ('PASS' if h['hollow'] is not None else 'SKIPPED'))
        lead = h['cheek_lead']
        C['cheek_lead_' + side] = dict(value=lead, status=_grade(lead, HOLLOW) if lead is not None and lead > 0 else
                                       ('PASS' if lead is not None else 'SKIPPED'))
    Bw = eye_bowl(B)
    T['bowl'] = Bw
    for side, b in Bw.items():
        C['eye_bowl_' + side] = dict(value=b['bowl'], at=b['at'], status=_grade(max(0.0, b['bowl']), BOWL)
                                     if b['bowl'] is not None else 'SKIPPED')
    try:
        Wd = eye_widths(B)
    except Exception as e:                    # (a build without the eyes sheet)
        Wd = {}
        T['widths_error'] = '%s: %s' % (type(e).__name__, e)
    T['widths'] = Wd
    for view in ('three_quarter', 'profile'):
        if view in Wd:
            C['eye_width_' + view] = dict(value=Wd[view]['ratio'], ours=Wd[view]['ours'], design=Wd[view]['design'],
                                          status=_grade(Wd[view]['ratio'] - 1, WIDTH))
    E = profile_edge(B)
    T['profile_edge'] = E
    if E:
        C['profile_edge'] = dict(value=E['rms'], worst=E['worst'], status=_grade(E['rms'], EDGE))
    K = neck_crease(B)
    T['neck_crease'] = K
    if K:
        C['neck_crease'] = dict(value=K['max'], median=K['median'], worst_column=K['worst'], status=_grade(K['max'], CREASE))
    Ka = neck_crease(B, variant='eval')
    T['neck_crease_all'] = Ka
    if Ka:
        C['neck_crease_all'] = dict(value=Ka['max'], median=Ka['median'], worst_column=Ka['worst'], status='INFO')
    try:
        Tj, Cj = jaw(B)
        T['jaw'] = Tj
        C.update(Cj)
    except Exception as e:                    # (a build without the head sheet)
        T['jaw_error'] = '%s: %s' % (type(e).__name__, e)
    return T, C


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return 0
    from . import bundle as bl
    B = bl.load(os.path.join(args[0], 'bundle'))
    T, C = measure(B)
    for k, v in C.items():
        print('%-26s %-8s %s  %s' % (k, v.get('value'), v.get('status'), {a: b for a, b in v.items() if a not in ('value', 'status')}))
    if T.get('widths_error'):
        print('widths:', T['widths_error'])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
