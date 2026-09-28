"""charkit.faceqa on shapes with known answers: two ellipsoid 'faces' (venv: run this file, or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import faceqa

SKIN_RGB = (0.98, 0.86, 0.80)                    # pale warm: inside faceqa.SKIN
HAIR_RGB = (0.84, 0.45, 0.25)


def ellipsoid(rx, ry, rz, centre, n=64):
    th, ph = np.meshgrid(np.linspace(0, np.pi, n), np.linspace(0, 2 * np.pi, 2 * n, endpoint=False), indexing='ij')
    V = np.stack([rx * np.sin(th) * np.cos(ph), ry * np.sin(th) * np.sin(ph), rz * np.cos(th)], -1).reshape(-1, 3) + centre
    idx = np.arange(n * 2 * n).reshape(n, 2 * n)
    a, b = idx[:-1], np.roll(idx, -1, 1)[:-1]
    c, d = idx[1:], np.roll(idx, -1, 1)[1:]
    T = np.concatenate([np.stack([a, c, b], -1).reshape(-1, 3), np.stack([b, c, d], -1).reshape(-1, 3)])
    return V, T


def test_zbuffer_nearest_wins():
    L = 1.0
    V1, T1 = ellipsoid(0.3, 0.3, 0.3, (0, 0, 0))
    V2, T2 = ellipsoid(0.1, 0.1, 0.1, (0, -0.5, 0))                  # in front (camera on -y)
    d, lab = faceqa.zbuffer([(V1, T1, np.ones(len(T1), int)), (V2, T2, np.zeros(len(T2), int))], 0, (0, 0), L)
    z = faceqa.row_z(lab.shape[0]); r = int(np.argmin(np.abs(z)))
    c = lab.shape[1] // 2
    assert lab[r, c] == 0                                               # the small one hides the big one's centre
    assert lab[r, c + int(0.2 / faceqa.PIX)] == 1                       # beside it the big one shows
    assert np.isinf(d[r, 5])                                            # outside both: nothing


def test_widths_and_depth_of_a_narrower_face():
    L = 1.0
    # the target: a face ellipsoid in skin colour; ours: 20% narrower, same height and depth
    VT, TT = ellipsoid(0.30, 0.28, 0.45, (0, 0, -0.2))
    CT = np.tile(SKIN_RGB, (len(VT), 1))
    VO, TO = ellipsoid(0.24, 0.28, 0.45, (0, 0, -0.2))
    lm = dict(L=L, eye_z=0.0, centre=(0.0, 0.0), mouth_z=-0.26)
    R = faceqa.measure([(VO, TO, np.ones(len(TO), bool), True)], (VT, TT, CT), lm)
    w = R['widths']['mouth']
    assert abs(w['ratio'] - 0.8) < 0.04, w
    C = faceqa.checks(R)
    assert C['width']['status'] == 'FAIL'
    same = faceqa.measure([(VT, TT, np.ones(len(TT), bool), True)], (VT, TT, CT), lm)
    assert abs(same['widths']['mouth']['ratio'] - 1) < 0.02
    assert faceqa.checks(same)['width']['status'] == 'PASS'


def test_hair_in_front_hides_the_edge():
    L = 1.0
    VT, TT = ellipsoid(0.30, 0.28, 0.45, (0, 0, -0.2))
    CT = np.tile(SKIN_RGB, (len(VT), 1))
    # a hair slab in front of the face's right edge, hair-coloured: the target's right edge there must not count
    VH, TH = ellipsoid(0.06, 0.02, 0.2, (0.27, -0.2, -0.26))
    V = np.vstack([VT, VH]); T = np.vstack([TT, TH + len(VT)])
    C = np.vstack([CT, np.tile(HAIR_RGB, (len(VH), 1))])
    lm = dict(L=L, eye_z=0.0, centre=(0.0, 0.0), mouth_z=-0.26)
    d, lab = faceqa.zbuffer([(V, T, (faceqa.skin_mask(C)[T].sum(1) >= 2).astype(int))], 0, (0, 0), L)
    face = faceqa.face_region(d, lab, 0.035)
    lo, hi = faceqa.extents(face, d, lab)
    z = faceqa.row_z(lab.shape[0]); r = int(np.argmin(np.abs(z + 0.26)))
    assert np.isfinite(lo[r]) and np.isnan(hi[r])


def test_chin_bottom():
    z = np.linspace(0, -0.6, 61)
    front = np.where(z > -0.4, -0.3 - 0.1 * (z / -0.4), 0.0)           # forward to the chin at -0.4, then back to the neck
    assert abs(faceqa.chin_bottom(front, z) - (-0.4)) < 0.011


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
