"""charkit.garments' boot template on a small stand-in assembly: one boot built, the other its mirror image; the sole
flat on the ground; the heel block under the heel; the fold at its height; the knots honoured (venv: run this file, or
pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import garments as gm, detailqa as dq

L = 1.0


def assembly():
    """two legs mirror images about x = 0.01 (not 0, as the authored body's), a few skin vertices on each."""
    J = {}
    for side, sx in (('L', 1), ('R', -1)):
        x = 0.01 + sx * 0.36
        J['lowerleg01.%s____head' % side] = [x, 0.17, 1.62]
        J['foot.%s____head' % side] = [x, 0.17, 0.56]
        J['toe1-1.%s____head' % side] = [x, -0.11, -0.06]
        J['toe1-1.%s____tail' % side] = [x, -0.34, -0.08]
    V = np.array([[0.37, 0.17, 0.2], [0.37, 0.17, 0.9], [0.37, 0.17, 1.4], [-0.35, 0.17, 0.2], [-0.35, 0.17, 1.4]])
    W = {'leftFoot': np.array([1, 0, 0, 0, 0.]), 'leftLowerLeg': np.array([0, 1, 1, 0, 0.]),
         'rightFoot': np.array([0, 0, 0, 1, 0.]), 'rightLowerLeg': np.array([0, 0, 0, 0, 1.])}
    return dict(head=dict(L=L), joints=J, verts=V, weights=W)


SPEC_L = dict(kind='boot', name='boot_L', side='left', ankle_h=0.66, top=1.2, step=0.03, cols=32,
              profile=[[0.02, -0.6, 0.165], [0.2, -0.58, 0.167], [0.3, -0.33, 0.168], [0.5, -0.18, 0.13],
                       [0.8, -0.15, 0.14], [1.2, -0.18, 0.2]],
              width=[[0.02, 0.12, -0.23], [0.3, 0.09, -0.2], [0.6, 0.066, -0.16], [1.2, 0.15, -0.2]],
              sole_t=0.06, heel=dict(lift=0.15, front=0.0, arch=-0.19, inset=0.012, flare=0.02),
              scrunch=dict(h=0.545, gap=0.045, width=0.014, front=[0.02, 0.02], back=[0.018, 0.02],
                           outer=[0.017, 0.006], inner=[0.02, 0.01]))
SPEC_R = dict(kind='boot', name='boot_R', side='right', mirror='boot_L')
WHOLE = dict(garments=[SPEC_L, SPEC_R])


def build():
    A = assembly()
    return A, gm.boot(A, dict(SPEC_L, _spec=WHOLE)), gm.boot(A, dict(SPEC_R, _spec=WHOLE))


def test_right_boot_is_the_left_mirrored():
    A, GL, GR = build()
    VL, VR = np.asarray(GL['verts']), np.asarray(GR['verts'])
    M = VL.copy()
    M[:, 0] = 0.02 - M[:, 0]                              # about the legs' midline, x = 0.01
    assert np.abs(M - VR).max() < 1e-9
    assert GR['faces'][0] == tuple(reversed(GL['faces'][0]))
    assert set(GR['weights']) == {'rightLowerLeg', 'rightFoot', 'rightToes'}


def test_sole_flat_on_the_ground_and_a_heel_under_the_heel():
    A, GL, _ = build()
    V = np.asarray(GL['verts'])
    ground = 0.56 - 0.66
    assert abs(V[:, 2].min() - ground) < 1e-9
    T = np.array([(f[0], f[k], f[k + 1]) for f in GL['faces'] for k in range(1, len(f) - 1)])
    s = dq.sole(V, T, L, (0.0, -1.0))
    assert s['flat'] < 0.004 and s['twist'] < 1.0, s       # (the arch's first faces rise a little)
    # the ground contact: the forefoot and the heel, with the arch between raised
    on = V[np.abs(V[:, 2] - ground) < 1e-9]
    y = on[:, 1] - 0.17
    assert y.min() < -0.55 and y.max() > 0.12, (y.min(), y.max())
    assert not ((y > -0.15) & (y < -0.02)).any()          # nothing on the ground under the arch
    assert sum(GL['sole']) > 0


def test_the_knots_are_the_silhouette():
    A, GL, _ = build()
    V = np.asarray(GL['verts'])
    ground = 0.56 - 0.66
    h = V[:, 2] - ground
    band = np.abs(h - 0.8) < 0.016                        # a shaft row: its extents are the knots'
    x, y = V[band, 0] - 0.37, V[band, 1] - 0.17
    (o, i), (f, b) = gm.hermite(SPEC_L['width'], [0.8])[0], gm.hermite(SPEC_L['profile'], [0.8])[0]
    assert abs(x.max() - o) < 0.006 and abs(x.min() - i) < 0.006, (x.min(), x.max(), i, o)
    assert abs(y.min() - f) < 0.006 and abs(y.max() - b) < 0.006, (y.min(), y.max(), f, b)


def test_the_fold_bulges_over_a_crease():
    s = dict(SPEC_L)
    x0, y0 = gm.boot_sections(dict(s, scrunch=None), np.array([0.0, 0.0]), np.array([0.5675, 0.5225]))
    x1, y1 = gm.boot_sections(s, np.array([0.0, 0.0]), np.array([0.5675, 0.5225]))
    assert y1[0] < y0[0] - 0.015 and y1[1] > y0[1] + 0.015    # (the front, -y: out above, in below)


def test_hides_the_leg_inside_it():
    A, GL, GR = build()
    assert set(GL['hide']) == {0, 1} and set(GR['hide']) == {3}   # the skin above its top stays


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok', name)
