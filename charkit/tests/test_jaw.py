"""The chin and jaw with known answers: the front and profile jaw measures (charkit.faceregion.jaw_front, jaw_profile)
on drawn class images, the jaw's underside under one closed section per row (charkit.geom.headgeom.UnderJaw) on a head
over a neck, and a mesh's winding made consistent (orient_faces) (venv: run this file, or pytest)."""
import math, os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import faceregion as fr
from charkit.geom import headgeom
from charkit.geom.headgeom import Sections

PPL = 200.0


def _grid():
    W = fr.JAW_WIN
    H, Wd = int(round((W['top'] - W['bottom']) * PPL)), int(round(2 * W['x'] * PPL))
    z = W['top'] - (np.arange(H) + 0.5) / PPL
    u = (np.arange(Wd) + 0.5) / PPL - W['x']
    return np.meshgrid(u, z)


def _front(line=True):
    """a drawn front: the face down to a V (the chin at -0.36, rising 0.5 per L across) over a neck 0.12 L wide, the V
    inked (0.01 L) where `line`, the neck ending at -0.6."""
    U, Z = _grid()
    jaw = -0.36 + 0.5 * np.abs(U)
    cls = np.zeros(U.shape, int)
    cls[(Z < 0.0) & (Z > jaw) & (np.abs(U) < 0.3)] = 1
    cls[(np.abs(U) < 0.12) & (Z <= jaw) & (Z > -0.6)] = 1
    if line:
        cls[(Z <= jaw) & (Z > jaw - 0.01) & (np.abs(U) < 0.3)] = 4
    return cls


def test_jaw_front_reads_the_drawn_v():
    M = fr.jaw_front(_front(), PPL)
    assert abs(M['chin'][1] + 0.36) < 0.01 and abs(M['chin'][0]) < 0.01
    assert abs(M['rise'] - 0.5 * fr.JAW_V) < 0.01                  # the V's arms at JAW_V either side
    assert abs(M['jaw_line_L'] - 0.24) < 0.02                       # the line over the neck: the neck's width
    assert abs(M['neck_w'] / M['face_w'] - 0.24 / 0.4) < 0.05      # the neck 0.24 under a face 0.4 wide, 0.1 over the chin


def test_jaw_front_sees_no_jaw_where_the_face_runs_into_the_neck():
    M = fr.jaw_front(_front(line=False), PPL)
    assert M['jaw_line_L'] == 0.0
    assert M['chin'][1] < -0.55                                     # the face's skin runs on to the neck's foot


def _lower(bottom, kink=None):
    """a drawn front whose lower face ends at z = bottom(u) (|u| < 0.3), inked 0.01 L, over a neck 0.12 L wide."""
    U, Z = _grid()
    jaw = bottom(U)
    cls = np.zeros(U.shape, int)
    cls[(Z < 0.0) & (Z > jaw) & (np.abs(U) < 0.3)] = 1
    cls[(np.abs(U) < 0.12) & (Z <= jaw) & (Z > -0.6)] = 1
    cls[(Z <= jaw) & (Z > jaw - 0.01) & (np.abs(U) < 0.3)] = 4
    return cls


def test_taper_reads_a_v_against_a_u():
    """a V (straight arms rising 0.5 per L) reads its opening and a sharp point; a U (an ellipse's bottom) turns all the
    way round: a low tip share."""
    V = fr.taper_front(_lower(lambda u: -0.36 + 0.5 * np.abs(u)), PPL)
    assert abs(V['chin_angle'] - (180 - 2 * math.degrees(math.atan(0.5)))) < 3.0, V['chin_angle']
    assert V['tip_share'] > 0.7, V['tip_share']
    assert max(a['bend'] for a in V['arms'].values()) < 4.0         # straight arms
    Uc = fr.taper_front(_lower(lambda u: -0.36 + 0.16 * (1 - np.sqrt(np.clip(1 - (u / 0.3) ** 2, 0, 1)))), PPL)
    assert Uc['tip_share'] < 0.4, Uc['tip_share']
    assert Uc['r'][int(round(0.5 / fr.TAPER_T))] > V['r'][int(round(0.5 / fr.TAPER_T))]   # the U stays wide further down


def test_taper_sees_a_kink_in_the_arms():
    """arms rising 0.3 per L to the neck's edge, then 0.9: a kink where they meet, read as a bend."""
    kinked = lambda u: -0.36 + np.where(np.abs(u) < 0.12, 0.3 * np.abs(u), 0.036 + 0.9 * (np.abs(u) - 0.12))
    K = fr.taper_front(_lower(kinked), PPL)
    assert max(a['bend'] for a in K['arms'].values()) > fr.ARM_BEND[0], K['arms']


def _hairy_front(lock=True, behind=True, mouth=False):
    """a drawn front: the V of _lower (rising 0.5 per L) over a neck, its sides at |u| 0.3 up to z -0.21 and widening 0.3
    per L above, inked; hair `behind` the jaw (beside the face and under its arms, the jaw's ink between: the head
    sheet's jaw is drawn over its hanging locks); a side lock over each side of the face from z -0.2 up, its tip at
    |u| 0.22, z -0.16 (`lock`); a mouth line across the chin's column at z -0.2 (`mouth`)."""
    U, Z = _grid()
    A = np.abs(U)
    jaw = -0.36 + 0.5 * A
    side = 0.3 + 0.3 * np.clip(Z + 0.21, 0, None)
    cls = np.zeros(U.shape, int)
    if behind:
        cls[(A < 0.45) & (Z < 0.0) & (Z > -0.4)] = 2
    face = (Z < 0.0) & (Z > jaw) & (A < side)
    cls[face] = 1
    cls[(A < 0.12) & (Z <= jaw) & (Z > -0.6)] = 1
    cls[(Z <= jaw) & (Z > jaw - 0.01) & (A < 0.3)] = 4
    cls[face & (A >= side - 0.01)] = 4
    if lock:
        cls[(A >= 0.22 + 0.5 * np.clip(Z + 0.16, 0, None)) & (Z >= -0.16 - 0.5 * (A - 0.22)) & (Z < 0.0) & (A < 0.45)] = 2
    if mouth:
        cls[(A < 0.05) & (np.abs(Z + 0.2) < 0.004)] = 4
    return cls


def test_taper_drops_the_rows_the_hair_covers():
    """hair behind the jaw masks nothing (the widest row in view is near the window's top, -0.05: the face's region runs
    to 0.015 L inside its drawn side, 0.335); a lock over each side of the face takes the rows from under its tip up (it
    meets the region's edge at z -0.19), and the taper is normalised on the face's own width under it (0.29, not the
    lock's inner edge, 0.26-0.28 over the tip)."""
    bare = fr.taper_front(_hairy_front(lock=False), PPL)
    assert bare['top'] is None and bare['z0'] > -0.08 and abs(bare['w0'] - 0.333) < 0.006, (bare['z0'], bare['w0'])
    lock = fr.taper_front(_hairy_front(), PPL)
    assert lock['top'] is not None and -0.21 < lock['top'] < -0.19, lock['top']
    assert lock['z0'] <= lock['top'] and abs(lock['w0'] - 0.29) < 0.006, (lock['z0'], lock['w0'])
    # the old reading: the lock's inner edge had set the row and its width (a running maximum over the tip)
    z, xl, xr, top = fr._half_widths(_hairy_front(), PPL, lock['chin'])
    assert np.all(np.isnan(xl[z > top])) and np.all(np.isfinite(xl[(z <= top) & (z > -0.3)]))


def test_half_widths_close_over_the_mouth():
    """a mouth line across the chin's column doesn't cut its rows short (the scan runs through the region's holes)."""
    a = fr.taper_front(_hairy_front(lock=False), PPL)
    b = fr.taper_front(_hairy_front(lock=False, mouth=True), PPL)
    assert np.allclose(a['r'], b['r'], atol=1e-6), np.abs(a['r'] - b['r']).max()


def test_the_level_camera_is_orthographic():
    """the design's projection: a point's place in the picture doesn't depend on its depth (the boards' camera, 1 m out
    in perspective, draws a point 0.1 m nearer 11% further out)."""
    ref = np.array([0.0, 0.0, 1.5])
    P = np.array([[0.05, -0.1, 1.45], [0.05, 0.1, 1.45]])
    o = fr.cam_points(P, 0.0, ref, ref, 0.2, dist=None)
    assert np.allclose(o[:, 0], 0.05) and np.allclose(o[:, 2], -0.05) and o[0, 1] < o[1, 1]
    b = fr.cam_points(P, 0.0, ref, ref, 0.2, dist=1.0)
    assert b[0, 0] > 0.055 and b[1, 0] < 0.046


def test_the_taper_checks_grade_the_level_camera():
    """the chin's and the taper's checks are graded on ours in the design's projection, the boards' value beside."""
    t = np.arange(0.0, 1.0 + 1e-9, fr.TAPER_T)
    r = 1.0 - t
    arms = {'L': dict(rms=0.001, bow=0.0, bend=3.0, bend_z=-0.3)}
    D = {'front': dict(t=t, r=r, z0=-0.18, w0=0.26, w90=0.05, chin_angle=129.7, tip_share=0.83, arms=arms)}
    lvl = dict(D['front'], chin_angle=129.0, tip_share=0.8)
    brd = dict(D['front'], r=r * 0.9, chin_angle=118.0, tip_share=0.4, arms={'L': dict(arms['L'], bend=12.0)})
    C = fr.taper_compare(D, {'front': lvl}, {'front': brd})
    # (the value is |ours - the design's| since face5 round 7; ours beside)
    assert C['chin_angle']['value'] == 0.7 and C['chin_angle']['ours'] == 129.0 and C['chin_angle']['board'] == 118.0
    assert C['chin_angle']['status'] == 'PASS'
    assert fr.taper_compare(D, {'front': dict(lvl, chin_angle=127.0)})['chin_angle']['status'] == 'WARN'
    assert C['chin_tip']['status'] == 'PASS' and C['chin_tip']['board'] == 0.4
    assert C['jaw_taper_shape']['value'] == 0.0 and C['jaw_taper_shape']['board'] > 0.05
    assert C['jaw_line_bend']['value'] == 3.0 and C['jaw_line_bend']['board'] == 12.0


def test_the_outer_extent_reads_past_an_eye_on_the_edge():
    """an eye whose lines run out to the face's edge (not a hole the fill closes) stops the scan from the chin's column
    (_extents) at the eye, but not the region's outermost extent (_outer), which reads the outline past it."""
    cls = _hairy_front(lock=False, behind=False)
    U, Z = _grid()
    e = ((U - 0.15) / 0.05) ** 2 + ((Z + 0.07) / 0.02) ** 2
    cls[e < 1.3] = 4
    cls[e < 0.7] = 3
    cls[(np.abs(U - 0.15) < 0.003) & (Z > -0.07)] = 4                  # (its lashes up to the face's top edge)
    chin = fr.jaw_front(cls, PPL)['chin']
    z, xl, xr, _, _ = fr._extents(cls, PPL, chin)
    zo, ol, orr = fr._outer(cls, PPL, chin)
    r = int(np.argmin(np.abs(z + 0.07)))
    assert xr[r] < 0.12 and abs(orr[r] - xl[r]) < 0.01, (xr[r], orr[r], xl[r])


def test_the_hidden_outline_passes_the_design_and_fails_a_face_curving_in():
    """ours against head_construction's outline over the rows the sheet's hair covers: 0 on the design itself; a face
    whose sides curve in under the hair (0.015 L at the rows' middle) FAILs; below the rows nothing counts."""
    zg = np.arange(-0.36, -0.05 + 1e-9, fr.HIDDEN_DZ)
    w = 0.28 + 0.1 * (zg + 0.18)
    H = dict(z=zg, xl=w, xr=w, rows=[-0.18, -0.05], fit=0.002, sx=0.97, sz=0.92)
    same = fr.hidden_compare(H, dict(z=zg, xl=w, xr=w))
    assert same['value'] == 0.0 and same['status'] == 'PASS' and same['flag']
    dent = w - 0.015 * np.sin(np.clip((zg + 0.18) / 0.13, 0, 1) * np.pi)
    bad = fr.hidden_compare(H, dict(z=zg, xl=dent, xr=dent))
    assert bad['status'] == 'FAIL' and bad['mean'] < 0, bad
    low = fr.hidden_compare(H, dict(z=zg, xl=np.where(zg < -0.2, w - 0.05, w), xr=w))
    assert low['value'] == 0.0


def _three_quarter(notch=0.0, dent=0.0, lock=False):
    """a three-quarter facing -u: the face's lower edge rising 0.3 per L from the chin (u 0) to u 0.25, `notch` L lower
    beyond u 0.2 (a step where the jaw meets the neck); the far cheek's contour at u -0.2 + 0.5 (z + 0.36) under z -0.2,
    dented `dent` L inward at z -0.28; `lock`: hair behind the far cheek and a lock over it."""
    U, Z = _grid()
    edge = -0.36 + 0.3 * np.clip(U, 0, None) - np.where(U > 0.2, notch, 0.0)
    far = np.where(Z < -0.2, -0.18 * (Z + 0.36) / 0.16 + 0.0, -0.18) + dent * np.exp(-0.5 * ((Z + 0.28) / 0.015) ** 2)
    far = np.minimum(far, 0.0)
    cls = np.zeros(U.shape, int)
    face = (Z < 0.0) & (Z > edge) & (U > far) & (U < 0.3)
    cls[face] = 1
    cls[(Z <= edge) & (Z > edge - 0.01) & (U >= 0) & (U < 0.3)] = 4
    cls[(U > 0.1) & (U < 0.28) & (Z <= edge - 0.01) & (Z > -0.6)] = 1          # the neck behind the jaw line
    if lock:                        # hair behind the far cheek, and a lock over it, its tip at u -0.09, z -0.26
        cls[(U <= far) & (U > -0.45) & (Z < 0.0) & (Z > -0.4)] = 2
        cls[(U <= -0.09 - 0.5 * np.clip(Z + 0.26, 0, None)) & (Z >= -0.215 + 0.5 * U) & (Z < 0.0) & (U > -0.45)] = 2
    return cls


def test_tq_jaw_stops_the_far_cheek_under_a_lock():
    """a lock over the far cheek (its lower edge meets the contour at z -0.267) ends the contour there: the hollow is
    the cheek's (none), not the lock's tip, which read as one when the contour ran on up its edge."""
    got = fr.tq_jaw(_three_quarter(lock=True), PPL)
    assert -0.29 < got['top'] < -0.26 and got['hollow'] < 0.003, (got['top'], got['hollow'])
    keep = fr.OCC_DROP
    try:
        fr.OCC_DROP = 1.0                                           # (the edge followed up the lock, as before)
        old = fr.tq_jaw(_three_quarter(lock=True), PPL)
    finally:
        fr.OCC_DROP = keep
    assert old['hollow'] > 0.005, old['hollow']


def test_tq_jaw_reads_the_notch_and_the_hollow():
    clean = fr.tq_jaw(_three_quarter(), PPL)
    assert clean['notch'] < 0.004 and clean['hollow'] < 0.003, clean
    step = fr.tq_jaw(_three_quarter(notch=0.02), PPL)
    assert abs(step['notch'] - 0.02) < 0.006, step['notch']
    dent = fr.tq_jaw(_three_quarter(dent=0.012), PPL)
    assert dent['hollow'] > 0.005 and abs(dent['hollow_z'] + 0.28) < 0.02, (dent['hollow'], dent['hollow_z'])


def _profile(rise=15.0):
    """a drawn profile facing -u: the face down to the chin (front u -0.05, bottom -0.36), its underside rising `rise`
    degrees back to a neck whose front is at u 0.18, down to -0.8."""
    U, Z = _grid()
    under = -0.36 + math.tan(math.radians(rise)) * np.maximum(U + 0.05, 0.0)
    cls = np.zeros(U.shape, int)
    cls[(U > -0.05) & (U < 0.45) & (Z < 0.02) & (Z > under)] = 1
    cls[(U >= 0.18) & (U < 0.45) & (Z < 0.02) & (Z > -0.8)] = 1
    return cls


def test_jaw_profile_reads_the_underside_and_a_clean_neck():
    for rise in (-5.0, 15.0):
        M = fr.jaw_profile(_profile(rise), PPL)
        assert abs(M['chin'][0] + 0.05) < 0.01
        assert abs(M['underside_deg'] - rise) < 2.5, (rise, M['underside_deg'])
        assert abs(M['throat'][0] - 0.18) < 0.02
        assert M['neck_bend_deg'] < 5.0                               # a straight neck front


def _ray(p0, d, c, a, b):
    """how far from p0 along unit d a ray leaves the ellipse centred c with semi-axes (a, b) (p0 inside)."""
    q = p0 - c
    A = (d[0] / a) ** 2 + (d[1] / b) ** 2
    B = 2 * (q[0] * d[0] / a ** 2 + q[1] * d[1] / b ** 2)
    C = (q[0] / a) ** 2 + (q[1] / b) ** 2 - 1
    return (-B + math.sqrt(B * B - 4 * A * C)) / (2 * A)


def _head(chin=-0.36, rows_chin=-0.37):
    """one closed section per row round (0, 0.3): a neck (a circle radius 0.12 about y 0.35) and, above the chin, a head
    (an ellipse about y 0.15, 0.2 deep, as wide as the V: 2 (z - chin), at most 0.28) as their union's outline: the air
    under the chin filled, as the head fit leaves it. -> (Sections, jaw)."""
    zs = np.arange(0.1, -0.6, -0.004)
    th = np.linspace(-np.pi, np.pi, Sections.N, endpoint=False)
    p0 = np.array([0.0, 0.3])
    R = np.zeros((len(zs), len(th)))
    for k, z in enumerate(zs):
        w = min(0.28, 2 * (z - rows_chin))
        for j, t in enumerate(th):
            d = np.array([math.sin(t), -math.cos(t)])
            r = _ray(p0, d, np.array([0.0, 0.35]), 0.12, 0.12)
            if w > 0.004:
                r = max(r, _ray(p0, d, np.array([0.0, 0.15]), w, 0.2))
            R[k, j] = r
    S = Sections(zs, np.full(len(zs), 0.3), R)
    xs = np.arange(0.0, 0.281, 0.005)
    return S, dict(x=list(xs), z=list(chin + xs / 2), chin=chin, neck=0.12, rise=15.0)


def test_under_jaw_carves_the_chin_off_the_neck():
    S, jaw = _head()
    U = headgeom.UnderJaw(S, jaw, -0.2, -0.55)
    P, s, info = U.meridian(0.0)
    (r_r, z_r), (r_j, z_j) = info['rim'], info['throat']
    assert abs(z_r + 0.36) < 0.01                                   # the rim at the chin
    assert abs((0.3 - r_j) - 0.23) < 0.01                           # the throat on the neck's front (y 0.23)
    slope = math.degrees(math.atan2(z_j - z_r, r_r - r_j))
    assert abs(slope - 15.0) < 3.0, slope                           # rising back at the jaw's rise
    assert np.abs(P[0] - headgeom.place(S, np.array([0.0]), np.array([-0.2]))[0]).max() < 1e-6
    assert np.abs(P[-1] - headgeom.place(S, np.array([0.0]), np.array([-0.55]))[0]).max() < 1e-6
    assert U.meridian(np.pi)[2]['rim'] is None                      # the nape: no pocket


def test_under_jaw_keeps_the_rim_on_the_v():
    """across the chin the rim follows the drawn V (its height at each x), up to the neck's edge."""
    S, jaw = _head()
    U = headgeom.UnderJaw(S, jaw, -0.2, -0.55)
    for deg in (0, 10, 20, 30):
        P, s, info = U.meridian(math.radians(deg))
        k = int(np.argmin(np.abs(P[:, 2] - info['rim'][1])))
        assert abs(P[k, 2] - (-0.36 + abs(P[k, 0]) / 2)) < 0.01, (deg, P[k])


def test_side_pocket_follows_the_jaw_round_its_sides():
    """the per-column form (side): every column up to the jaw's angle (z -0.25 here: the V at x 0.22) has a rim on the
    drawn V (its height at the rim's x) and a throat on the neck (a circle radius 0.12 about y 0.35) over the rim (the
    underside rises inward); past the angle the pocket fades out; round the sides the rim keeps its chart row."""
    S, jaw = _head()
    rows = (-0.24, -0.33)
    U = headgeom.UnderJaw(S, jaw, -0.2, -0.55, side=dict(z_angle=-0.25, rows=rows))
    seen = []
    for deg in range(0, 90, 5):
        t = math.radians(deg)
        P, s, info = U.meridian(t)
        if info['rim'] is None:
            continue
        k = int(np.argmin(np.abs(s - info['s_rim'])))
        assert abs(P[k, 2] - (-0.36 + abs(P[k, 0]) / 2)) < 0.012, (deg, P[k])          # on the V
        j = int(np.argmin(np.abs(s - info['s_throat'])))
        assert abs(math.hypot(P[j, 0], P[j, 1] - 0.35) - 0.12) < 0.012, (deg, P[j])     # on the neck
        assert P[j, 2] > P[k, 2], deg                                                    # rising inward
        seen.append((deg, float(P[k, 0]), info['w']))
    assert seen[0][0] == 0 and max(x for _, x, _ in seen) > 0.19, seen                # the chin round to the angle
    t = math.radians(40)                                  # (past SIDE_EASE and short of the angle: the fixed row)
    P, s, info = U.meridian(t)
    assert info['rim'] is not None and U.side_weight(t) == 1.0
    got = U.place(np.array([t]), np.array([rows[0]]))[0]
    k = int(np.argmin(np.abs(s - info['s_rim'])))
    assert np.abs(got - P[k]).max() < 0.003, (got, P[k])


def test_the_chin_columns_rims_land_on_the_v():
    """the per-column form hangs each column's underside from its point of the jaw's edge, but the rim (where the
    column's envelope crosses it) lands off the edge's height where the envelope's front isn't through the edge's point:
    0.0014-0.0019 L over it here. Re-hung by the gap (SIDE_RIMFIT, the chin's columns under SIDE_RIMFIT_A), every chin
    column's rim is on the drawn V at its own x."""
    S, jaw = _head()
    got = {}
    keep = headgeom.SIDE_RIMFIT, headgeom.SIDE_RIMFIT_A, headgeom.SIDE_RIMFIT_FADE
    try:
        for fit in (0, 3):
            headgeom.SIDE_RIMFIT, headgeom.SIDE_RIMFIT_A, headgeom.SIDE_RIMFIT_FADE = fit, 0.3, 0.0
            U = headgeom.UnderJaw(S, jaw, -0.2, -0.55, side=dict(z_angle=-0.25, rows=(-0.24, -0.33)))
            err = []
            for deg in range(0, 17, 2):
                t = math.radians(deg)
                info = U.meridian(t)[2]
                x = info['rim'][0] * math.sin(t)
                err.append(abs(info['rim'][1] - float(np.interp(x, U.jx, U.jz))))
            got[fit] = max(err)
    finally:
        headgeom.SIDE_RIMFIT, headgeom.SIDE_RIMFIT_A, headgeom.SIDE_RIMFIT_FADE = keep
    assert got[0] > 0.0013 and got[3] < 0.001, got


def test_the_rim_refit_fades_by_its_share():
    """SIDE_RIMFIT_FADE: a chin column refitted by a share w of its rim's gap keeps (1 - w) of it (the default hangs the
    point's neighbour whole, the next column 0.59 of the way: the boards' taper stays under its FAIL line)."""
    S, jaw = _head()
    keep = headgeom.SIDE_RIMFIT, headgeom.SIDE_RIMFIT_A, headgeom.SIDE_RIMFIT_FADE
    gap = {}
    t = math.radians(12)
    try:
        for fit, fade in ((0, 0.0), (3, 0.4)):
            headgeom.SIDE_RIMFIT, headgeom.SIDE_RIMFIT_A, headgeom.SIDE_RIMFIT_FADE = fit, t + 0.2, fade
            U = headgeom.UnderJaw(S, jaw, -0.2, -0.55, side=dict(z_angle=-0.25, rows=(-0.24, -0.33)))
            info = U.meridian(t)[2]
            x = info['rim'][0] * math.sin(t)
            gap[fit] = info['rim'][1] - float(np.interp(x, U.jx, U.jz))
    finally:
        headgeom.SIDE_RIMFIT, headgeom.SIDE_RIMFIT_A, headgeom.SIDE_RIMFIT_FADE = keep
    assert abs(gap[0]) > 0.001 and abs(gap[3] - 0.5 * gap[0]) < 0.25 * abs(gap[0]), gap


def test_under_jaw_leaves_the_rows_under_its_band_on_the_sections():
    """rows under the band's foot (the neck down to the join) are the sections' own, not the meridians' end."""
    S, jaw = _head()
    U = headgeom.UnderJaw(S, jaw, -0.2, -0.45)
    th, z = np.zeros(3), np.array([-0.3, -0.5, -0.55])
    P = U.place(th, z)
    ref = headgeom.place(S, th, z)
    assert np.abs(P[1:] - ref[1:]).max() < 1e-9                      # under the foot: the sections'
    assert abs(P[0, 2] - (-0.3)) > 1e-3 or np.abs(P[0] - ref[0]).max() > 1e-3   # in the band: along the meridian


def test_jaw_envelope_puts_the_edge_at_the_designs_depth():
    """with the design's depth (the edge 0.9 L back per L out from the chin), each row's outline passes through the
    edge's point (the V's half-width at the depth the recession gives it, placed at our chin's own), the midline (the
    profile) where it was; without it, the sections unchanged."""
    S, jaw = _head()
    xs = np.arange(0.03, 0.2, 0.01)
    jaw = dict(jaw, depth=[list(xs), list(0.9 * xs)])
    Se, info = headgeom.jaw_envelope(S, jaw)
    Dfn = headgeom.jaw_depth(jaw)
    j0 = int(np.argmin(np.abs(S.th)))
    for z in (-0.33, -0.3, -0.27):
        k = int(np.argmin(np.abs(S.zs - z)))
        xV = float(np.interp(S.zs[k], jaw['z'], jaw['x']))
        yJ = info['y_ref'] + float(Dfn(xV))
        x, y = Se.xy(k)
        near = np.min(np.hypot(x - xV, y - yJ))
        assert near < 0.006, (z, near)                               # the outline through the edge's point
        assert abs(Se.r[k, j0] - S.r[k, j0]) < 1e-9                  # the midline unmoved
    assert headgeom.jaw_envelope(S, dict(jaw, depth=None))[0] is S


def test_orient_faces_makes_the_winding_consistent():
    V = np.array([[x, y, z] for x in (0.0, 1.0) for y in (0.0, 1.0) for z in (0.0, 1.0)]) - 0.5
    V[:, 2] += 0.15                                                 # (the forehead's seed near z 0.15)
    F = [[0, 1, 3, 2], [4, 6, 7, 5], [0, 4, 5, 1], [2, 3, 7, 6], [0, 2, 6, 4], [1, 5, 7, 3]]
    # outward first (each face's normal away from the centre), then one turned round
    F = [f if np.cross(V[f[2]] - V[f[0]], V[f[3]] - V[f[1]]) @ (V[f].mean(0) - V.mean(0)) > 0 else f[::-1] for f in F]
    G = [list(f) for f in F]
    G[3] = G[3][::-1]
    H = headgeom.orient_faces(V, G)
    assert all(np.cross(V[f[2]] - V[f[0]], V[f[3]] - V[f[1]]) @ (V[f].mean(0) - V.mean(0)) > 0 for f in H)


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok', name)


def test_the_face_share_over_the_chin_reads_a_face_running_into_the_neck():
    """neck_to_face (face5 round 7): over the rows just above the design's chin, the face's share of the figure's width:
    a V chin with its jaw lines over the neck reads low; a face running straight into a neck as wide as it (no jaw line,
    Michael's jaw_0 flag) reads near 1."""
    from scipy.ndimage import binary_erosion
    U, Z = _grid()
    head = (Z > -0.2) & (np.abs(U) < 0.25)
    neck = (Z <= -0.2) & (np.abs(U) < 0.12)
    v_ = (Z <= -0.2) & (Z > -0.36) & (np.abs(U) < 0.25 * (Z + 0.36) / 0.16)
    V = np.where(head | neck | v_, 1, 0)
    V[v_ & ~binary_erosion(v_) & (Z < -0.21)] = 4                                # the V's jaw lines
    run = np.where(head | neck, 1, 0)                                            # no jaw line: the face into the neck
    a = fr.jaw_front(V, PPL, -0.36)['chin_share']
    b = fr.jaw_front(run, PPL, -0.36)['chin_share']
    assert a is not None and b is not None and a < 0.6 and b > 0.9, (a, b)
