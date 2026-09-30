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


def _three_quarter(notch=0.0, dent=0.0):
    """a three-quarter facing -u: the face's lower edge rising 0.3 per L from the chin (u 0) to u 0.25, `notch` L lower
    beyond u 0.2 (a step where the jaw meets the neck); the far cheek's contour at u -0.2 + 0.5 (z + 0.36) under z -0.2,
    dented `dent` L inward at z -0.28."""
    U, Z = _grid()
    edge = -0.36 + 0.3 * np.clip(U, 0, None) - np.where(U > 0.2, notch, 0.0)
    far = np.where(Z < -0.2, -0.18 * (Z + 0.36) / 0.16 + 0.0, -0.18) + dent * np.exp(-0.5 * ((Z + 0.28) / 0.015) ** 2)
    far = np.minimum(far, 0.0)
    cls = np.zeros(U.shape, int)
    face = (Z < 0.0) & (Z > edge) & (U > far) & (U < 0.3)
    cls[face] = 1
    cls[(Z <= edge) & (Z > edge - 0.01) & (U >= 0) & (U < 0.3)] = 4
    cls[(U > 0.1) & (U < 0.28) & (Z <= edge - 0.01) & (Z > -0.6)] = 1          # the neck behind the jaw line
    return cls


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


def test_under_jaw_leaves_the_rows_under_its_band_on_the_sections():
    """rows under the band's foot (the neck down to the join) are the sections' own, not the meridians' end."""
    S, jaw = _head()
    U = headgeom.UnderJaw(S, jaw, -0.2, -0.45)
    th, z = np.zeros(3), np.array([-0.3, -0.5, -0.55])
    P = U.place(th, z)
    ref = headgeom.place(S, th, z)
    assert np.abs(P[1:] - ref[1:]).max() < 1e-9                      # under the foot: the sections'
    assert abs(P[0, 2] - (-0.3)) > 1e-3 or np.abs(P[0] - ref[0]).max() > 1e-3   # in the band: along the meridian


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
