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
    iw = np.array(qa3d.iris_centres(B))
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
