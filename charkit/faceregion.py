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


def neck_crease(B, cols=36, dz=0.01, sector=math.radians(6), variant='masked'):
    """the sharpest local bend of the skin's outline down any column round the neck near the cut (JOIN): per column the
    skin's radius from the neck's axis per height, its slope angle, and how far it departs from its own smoothing over
    CREASE_SMOOTH (degrees) -> dict(max, median, worst column (degrees round from the front), per column). variant: the
    skin as it shows ('masked': the garments' mask on) or whole ('eval')."""
    c, L, _ = frame(B)
    try:
        V = _mesh(B.skin(), variant)[0]
    except (KeyError, ValueError):                 # (a bundle without the masked skin)
        V = _mesh(B.skin(), 'eval')[0]
    return crease_of(V, c, L, cols, dz, sector)


def crease_of(V, c, L, cols=36, dz=0.01, sector=math.radians(6)):
    """neck_crease on plain arrays: the skin's vertices V (world), the head's centre c and L."""
    zc = c[2] + CUT * L
    band = (V[:, 2] > zc - (JOIN[0] + 0.05) * L) & (V[:, 2] < zc + (JOIN[1] + 0.05) * L)
    P = V[band]
    if len(P) < 50:
        return None
    ring = P[np.abs(P[:, 2] - zc) < 0.02 * L]
    axis = ring[:, :2].mean(0) if len(ring) else c[:2]
    q = P[:, :2] - axis
    th = np.arctan2(q[:, 0], -q[:, 1])
    r = np.hypot(q[:, 0], q[:, 1])
    zs = np.arange(zc - JOIN[0] * L, zc + JOIN[1] * L + 1e-12, dz * L)
    per = {}
    for j in range(cols):
        a = -math.pi + 2 * math.pi * (j + 0.5) / cols
        m = np.abs(np.angle(np.exp(1j * (th - a)))) < sector
        if m.sum() < 10:
            continue
        rr = []
        for z in zs:
            mm = m & (np.abs(P[:, 2] - z) < 0.6 * dz * L)
            rr.append(r[mm].max() if mm.any() else np.nan)
        rr = np.array(rr)
        ok = np.isfinite(rr)
        if ok.sum() < 6:
            continue
        rr = np.interp(np.arange(len(rr)), np.nonzero(ok)[0], rr[ok])
        ang = np.degrees(np.arctan2(np.diff(rr), dz * L))            # the outline's slope per step (0: vertical)
        from scipy.ndimage import gaussian_filter1d
        bend = np.abs(ang - gaussian_filter1d(ang, CREASE_SMOOTH / dz, mode='nearest'))
        per[round(math.degrees(a))] = round(float(bend.max()), 1)
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
LEVEL_CAM = dict(dist=100.0, lift=0.0)          # the design's: level with the eyes, far out (all but orthographic)
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
RATIO = (0.15, 0.3)              # |ratio - 1|: PASS / WARN for the chin's V and the neck's width over the face's
UNDER = (6.0, 12.0)              # degrees: PASS / WARN for the chin's underside angle in profile against the design's
WIGGLE = (12.0, 18.0)            # degrees: PASS / WARN for the neck's front outline under the throat in profile, its
                                 # sharpest bend (a lip and a notch under the jaw bend it, 24 on the step-built chin; the
                                 # neck's own long curve doesn't; the design's own neck, read further down past its hanging
                                 # lock and into the shoulders' flare, is shown)
NECK_BAND = 0.1                  # L under the throat where the neck's front outline is read (the neck under the jaw)
DESIGN_NECK_BAND = 0.25          # ... on the design, the reference (a lock hangs in front of its neck under the jaw)


def cam_points(V, az, target, ref, L, dist=BOARD_CAM['dist']):
    """world points -> the board camera's view as points for raster.window_zbuffer at az 0: (u, depth, v) times L, u and v
    the picture's right and up in L at the reference point's depth (perspective), 0 at the reference point, depth L
    along the view. The camera (charkit.qa.render_view): at target + dist (sin az, -cos az, 0), level, looking at it."""
    a = math.radians(az)
    eye = np.asarray(target, float) + dist * np.array([math.sin(a), -math.cos(a), 0.0])
    r, f = np.array([math.cos(a), math.sin(a), 0.0]), np.array([-math.sin(a), math.cos(a), 0.0])
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
    out['rise'] = round(float(np.mean(rise)), 4) if rise else None
    zc_ref = zc if chin_z is None else chin_z

    def width(zz, mask):
        r = int(round((win['top'] - zz) * ppl - 0.5))
        if not 0 <= r < H or not mask[r].any():
            return None
        c0 = int(round(win['x'] * ppl))
        c = np.nonzero(mask[r])[0]
        runs = np.split(c, np.nonzero(np.diff(c) > 1)[0] + 1)
        run = min(runs, key=lambda q: 0 if q[0] <= c0 <= q[-1] else min(abs(q[0] - c0), abs(q[-1] - c0)))
        return (run[-1] - run[0] + 1) / ppl
    out['face_w'] = width(zc_ref + NECK_BELOW, face)
    out['neck_w'] = width(zc_ref - NECK_BELOW, skin)
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
        cut = np.nonzero(np.diff(rows) > 2)[0]                          # the longest run of rows from the throat down
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
        rows = np.nonzero((z <= JAW_ROWS[0]) & (z >= zc))[0][::max(1, int(JAW_ROWS[1] * ppl))]
        ours = np.nan_to_num(of['half'][rows], nan=0.0) if 'half' in of else np.zeros(len(rows))
        d = ours - df['half'][rows]
        ok = np.isfinite(d)
        rms = float(np.sqrt(np.mean(d[ok] ** 2))) if ok.any() else None
        worst = int(np.argmax(np.abs(np.where(ok, d, 0))))
        C['jaw_taper'] = dict(value=round(rms, 4) if rms is not None else None, worst=[round(float(z[rows[worst]]), 3),
                              round(float(d[worst]), 4)], status=_grade(rms, TAPER))
        oc = of.get('chin')
        dz = None if oc is None else oc[1] - zc
        C['chin_point_z'] = dict(value=None if dz is None else round(dz, 4), design=zc, ours=None if oc is None else oc[1],
                                 status=_grade(dz, TAPER))
        rd, ro = df.get('rise'), of.get('rise')
        rr = ro / rd if rd and ro is not None else None
        C['chin_v'] = dict(value=None if rr is None else round(rr, 3), design=rd, ours=ro,
                           status=_grade(None if rr is None else rr - 1, RATIO))
        if df.get('face_w') and df.get('neck_w') and of.get('face_w') and of.get('neck_w'):
            q = (of['neck_w'] / of['face_w']) / (df['neck_w'] / df['face_w'])
            C['neck_to_face'] = dict(value=round(q, 3), design=round(df['neck_w'] / df['face_w'], 3),
                                     ours=round(of['neck_w'] / of['face_w'], 3), status=_grade(q - 1, RATIO))
    for vn in ('front', 'three_quarter'):
        d_, o_ = D.get(vn) or {}, O.get(vn) or {}
        if d_.get('jaw_line_L'):
            q = (o_.get('jaw_line_L') or 0.0) / d_['jaw_line_L']
            C['jaw_line_' + vn] = dict(value=round(q, 3), design=d_['jaw_line_L'], ours=o_.get('jaw_line_L'),
                                       status='PASS' if q >= JAW_LINE[0] else 'WARN' if q >= JAW_LINE[1] else 'FAIL')
    dp, op = D.get('profile') or {}, O.get('profile') or {}
    if dp.get('underside_deg') is not None:
        a = op.get('underside_deg')
        C['chin_underside'] = dict(value=a, design=dp['underside_deg'], status=_grade(
            None if a is None else a - dp['underside_deg'], UNDER))
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
# the boards' camera (what the boards show), each with the level camera's value beside it (the drawing's projection).
TAPER_TOP = (-0.05, 0.1)         # the cheekbone row: the design's widest row under the first z and this far over its chin
TAPER_T = 0.02                   # the taper curve's step in t
TAPER_SHAPE = (0.025, 0.04)      # rms of w(t)/w(0) against the design's: PASS / WARN
TAPER_START = 0.9                # the taper starts where w(t)/w(0) first falls under this
ARMS = (0.4, 0.95)               # t: the jaw lines (their straightness and bends)
ARC_STEP = 0.25                  # px: the outline resampled by arc length this often, smoothed over ARC_SMOOTH
ARC_SMOOTH = 0.003               # L (a pixel's steps)
ARM_SMOOTH = 0.006               # L: the jaw lines smoothed this much more before their bends are read (the sheet's
                                 # 401 px per L steps a pixel's direction by 5-10 degrees)
BEND_SMOOTH = 0.03               # L of arc: a bend is the direction less its smoothing over this
ARM_BEND = (6.0, 10.0)           # deg: the jaw lines' sharpest local bend (a kink where the silhouette jumps in depth;
                                 # the design's own 4.4)
CHIN_ARMS = (0.06, 0.12)         # L of arc from the chin point: the V's arms, fitted as lines
CHIN_ANGLE = (10.0, 20.0)        # deg: |ours - design| of the V's opening between them
TIP_ARC = 0.02                   # L of arc either side of the chin point: the V's point
TIP_SHARE = (0.7, 0.55)          # the share of the V's turn its point makes: PASS / WARN at least (a U turns all
                                 # the way round its bottom; the design's arms run straight to within TIP_ARC of it)
TQ_TOP = -0.12                   # z: the three-quarter's far contour read from the chin up to here
HOLLOW_ARC = 0.05                # L of arc either side: the far contour's local chord
TQ_HOLLOW = (0.005, 0.008)       # L: the far contour's deepest local hollow (inside its local chord)
TQ_NOTCH = (0.008, 0.016)        # L: the near jaw line's largest drop under its own rise
NOTCH_JUMP = 0.05                # L: the near jaw line ends where the next column's foot jumps this far (hair, a gap)


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


def _by_arc(P, ppl):
    """a polyline resampled by arc length (ARC_STEP px) and smoothed (ARC_SMOOTH) -> (points, step L)."""
    from scipy.ndimage import gaussian_filter1d
    s = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(P, axis=0).T))])
    step = ARC_STEP / ppl
    sg = np.arange(0.0, s[-1] + 1e-12, step)
    Q = np.stack([np.interp(sg, s, P[:, 0]), np.interp(sg, s, P[:, 1])], 1)
    return gaussian_filter1d(Q, ARC_SMOOTH / step, axis=0, mode='nearest'), step


def _direction(Q):
    """the direction of a polyline (degrees, unwrapped) at each point."""
    d = np.gradient(Q, axis=0)
    return np.degrees(np.unwrap(np.arctan2(d[:, 1], d[:, 0])))


def _half_widths(cls, ppl, chin, win=JAW_WIN, seeds=FACE_SEEDS):
    """the face's half-width either side of the chin's column per row, scanned out through the face region from that
    column, above the chin; a hair lock's tip cutting a row short bridged (each side's running maximum from the chin
    up) -> (z (rows), left, right) L."""
    face = _region(cls, seeds, ppl, win)
    H, W = cls.shape
    z = win['top'] - (np.arange(H) + 0.5) / ppl
    u = (np.arange(W) + 0.5) / ppl - win['x']
    uc, zc = chin
    c0 = int(round((uc + win['x']) * ppl - 0.5))
    xl, xr = np.full(H, np.nan), np.full(H, np.nan)
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
    ok = np.nonzero(np.isfinite(xl))[0][::-1]                  # from the chin up
    if len(ok):
        xl[ok] = np.maximum.accumulate(xl[ok]); xr[ok] = np.maximum.accumulate(xr[ok])
    return z, xl, xr


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
    z, xl, xr = _half_widths(cls, ppl, (uc, zc), win, seeds)
    w = 0.5 * (xl + xr)
    if z0 is None:
        sel = (z <= TAPER_TOP[0]) & (z >= zc + TAPER_TOP[1]) & np.isfinite(w)
        if not sel.any():
            return None
        z0 = float(z[sel][np.nonzero(w[sel] >= 0.98 * np.nanmax(w[sel]))[0].max()])
    t = (z0 - z) / (z0 - zc)
    ok = np.isfinite(w) & (t >= -1e-9) & (t <= 1 + 1e-9)
    if ok.sum() < 10:
        return None
    o = np.argsort(t[ok])
    tg = np.arange(0.0, 1.0 + 1e-9, TAPER_T)
    wg = np.interp(tg, t[ok][o], w[ok][o])
    wg[-1] = 0.0                                                   # (the chin point)
    r = wg / wg[0]
    below = np.nonzero(r < TAPER_START)[0]
    out = dict(z0=round(z0, 4), chin=(round(float(uc), 4), round(float(zc), 4)), t=tg, r=r, w0=round(float(wg[0]), 4),
               w90=round(float(np.interp(0.9, tg, wg)), 4), start=round(float(tg[below[0]]), 3) if len(below) else None)
    # the outline under z0, from the picture's left through the chin to its right, by arc length
    i0 = int(np.argmin(np.hypot(X[:, 0] - uc, X[:, 1] - zc)))
    a, b = _walk(X, i0, -1, lambda p: p[1] > z0), _walk(X, i0, 1, lambda p: p[1] > z0)
    P = X[a[::-1] + b[1:]]
    if len(P) < 10:
        return out
    if P[0, 0] > P[-1, 0]:
        P = P[::-1]
    Q, step = _by_arc(P, ppl)
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


def tq_jaw(cls, ppl, facing=-1, win=JAW_WIN, seeds=FACE_SEEDS):
    """a three-quarter's jaw -> dict:
      hollow      the far contour (from the chin up to TQ_TOP, on the facing side) its deepest local hollow: how far a
                  point lies inside the chord between the points HOLLOW_ARC of arc either side (L, + a hollow), and where
                  (z); curv: its most concave signed curvature (1/L, - concave);
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
    idx = _walk(X, i0, far, lambda p: p[1] > TQ_TOP)
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


def taper_compare(D, O, Ol=None):
    """the taper's checks: the design's taper_front / tq_jaw measures D ({'front': , 'three_quarter': }) against ours O
    (the boards' camera), Ol (the level camera's, shown beside) -> checks."""
    C = {}
    df, of = D.get('front'), O.get('front')
    lf = (Ol or {}).get('front') or {}
    if df and of:
        dr = of['r'] - df['r']
        k = int(np.argmax(np.abs(dr)))
        rms = float(np.sqrt(np.mean(dr ** 2)))
        lvl = float(np.sqrt(np.mean((lf['r'] - df['r']) ** 2))) if lf.get('r') is not None else None
        C['jaw_taper_shape'] = dict(value=round(rms, 4), worst=[round(float(df['t'][k]), 2), round(float(dr[k]), 4)],
                                    start=[of.get('start'), df.get('start')], w0=[of['w0'], df['w0']],
                                    level=None if lvl is None else round(lvl, 4), status=_grade(rms, TAPER_SHAPE),
                                    note='rms of w(t)/w(0), t 0 at the cheekbone row %.3f, 1 at the chin; worst [t, ours - '
                                         'design]; start [ours, design]: where it first falls under %.1f' % (df['z0'], TAPER_START))
        if of.get('arms') and df.get('arms'):
            bb = max(a['bend'] for a in of['arms'].values())
            bl = max(a['bend'] for a in lf['arms'].values()) if lf.get('arms') else None
            b = max(bb, bl or 0.0)
            C['jaw_line_bend'] = dict(value=b, board=bb, level=bl, design=max(a['bend'] for a in df['arms'].values()),
                                      arms=of['arms'], arms_level=lf.get('arms'), arms_design=df['arms'],
                                      status=_grade(b, ARM_BEND),
                                      note='the jaw lines (t %.2f-%.2f) sharpest local bend (deg), the worse camera\'s; per '
                                           'side a line fit\'s rms (L) and bow (L, + convex)' % ARMS)
        if of.get('chin_angle') is not None and df.get('chin_angle') is not None:
            d = of['chin_angle'] - df['chin_angle']
            C['chin_angle'] = dict(value=of['chin_angle'], design=df['chin_angle'], arms=of.get('chin_arms'),
                                   level=lf.get('chin_angle'), w90=[of['w90'], df['w90']], status=_grade(d, CHIN_ANGLE),
                                   note="the V's opening between its arms %.2f-%.2f L of arc from the chin point (deg); "
                                        'w90 [ours, design]: the half-width at t 0.9 (L)' % CHIN_ARMS)
        if of.get('tip_share') is not None and df.get('tip_share') is not None:
            v = of['tip_share']
            C['chin_tip'] = dict(value=v, design=df['tip_share'], level=lf.get('tip_share'),
                                 status='PASS' if v >= TIP_SHARE[0] else 'WARN' if v >= TIP_SHARE[1] else 'FAIL',
                                 note="the share of the V's turn made within %.3f L of arc of its point (1 a sharp V, "
                                      'low a round U)' % TIP_ARC)
    dq, oq = D.get('three_quarter'), O.get('three_quarter')
    lq = (Ol or {}).get('three_quarter') or {}
    if dq and oq:
        if oq.get('hollow') is not None:
            h = max(oq['hollow'], lq.get('hollow') or -1.0)
            C['tq_cheek_hollow'] = dict(value=h, board=oq['hollow'], level=lq.get('hollow'), z=oq.get('hollow_z'),
                                        z_level=lq.get('hollow_z'), curv=oq.get('curv'), design=dq.get('hollow'),
                                        status=_grade(max(0.0, h), TQ_HOLLOW),
                                        note='the far cheek contour\'s deepest local hollow inside its chord over %.2f L of arc '
                                             'either side (L), the worse camera\'s; curv: its most concave curvature (1/L)'
                                             % HOLLOW_ARC)
        if oq.get('notch') is not None:
            nn = max(oq['notch'], lq.get('notch') or 0.0)
            C['tq_jaw_notch'] = dict(value=nn, board=oq['notch'], level=lq.get('notch'), du=oq.get('notch_du'),
                                     du_level=lq.get('notch_du'), design=dq.get('notch'), status=_grade(nn, TQ_NOTCH),
                                     note="the near jaw line's largest drop under its own rise from the chin (L), the worse "
                                          "camera's: a notch or step where the jaw meets the neck")
    return C


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


def ours_jaw(meshes, skin, iris, eye_z, L, ppl, az, design_chin=None, design_z0=None, facing=-1):
    """our jaw measures from a scene (meshes [(V, T, class)], skin (V, T) for the outline, the iris centres (world), the
    eye line's z), each view at its azimuth az {view: degrees}, registered on the eyes at the head's eye line
    (eye_anchor), in two cameras: the jaw's lines (does the jaw line draw over the neck, in front and three-quarter) in
    the boards' camera, as the boards show them; its shape (the outline, the chin, the V, the widths, the profile's
    underside and neck) in a level camera far out (LEVEL_CAM), as the design is drawn: the boards' look down 6 degrees at
    the chin in perspective, which alone raises the V's arms 0.01 L and narrows the cheeks, further back than the eyes,
    by 5%. The taper's shape (taper_front from design_z0, the design's cheekbone row; tq_jaw) in both: 'taper' the
    boards', 'taper_level' the level's -> ({view: measures}, {view: the board's classes}, {view: the level's classes})."""
    iris = eye_anchor(iris, eye_z)
    O, P, Q = {}, {}, {}
    for vn, a in az.items():
        ref = iris[np.argmax(iris[:, 0])] if vn == 'profile' else iris.mean(0)
        cams = {}
        for cam, cfg in (('board', BOARD_CAM), ('level', LEVEL_CAM)):
            target = np.array([0.0, 0.0, eye_z + cfg['lift'] * L])
            cams[cam] = board_view(meshes, skin, a, target, ref, L, ppl, dist=cfg['dist'])[0]
        P[vn], Q[vn] = cams['board'], cams['level']
        if vn == 'profile':
            O[vn] = jaw_profile(cams['level'], ppl)
        else:
            M = jaw_front(cams['level'], ppl, design_chin if vn == 'front' else None)
            Mb = jaw_front(cams['board'], ppl)
            M.update(jaw_line_L=Mb['jaw_line_L'], jaw_cols=Mb['jaw_cols'])
            if vn == 'front':
                M['taper'] = taper_front(cams['board'], ppl, design_z0)
                M['taper_level'] = taper_front(cams['level'], ppl, design_z0)
            else:
                M['taper'] = tq_jaw(cams['board'], ppl, facing)
                M['taper_level'] = tq_jaw(cams['level'], ppl, facing)
            O[vn] = M
    return O, P, Q


def taper_checks(D, O):
    """the taper's checks from design_jaw's and ours_jaw's measures."""
    pick = lambda M, k: {vn: (M.get(vn) or {}).get(k) for vn in ('front', 'three_quarter')}
    return taper_compare(pick(D, 'taper'), pick(O, 'taper'), pick(O, 'taper_level'))


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
                 (B.spec.get('ref') or {}).get('face_sheet', {}).get('facing', -1))[0]
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
