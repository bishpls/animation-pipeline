"""charkit.eyes.Surface on a flat, yawed face with known answers (venv: run this file, or pytest)."""
import math, os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import eyes as eyelib

EX, EZ, L, YAW = 0.042, 1.3, 0.25, 26.9


class Window:
    """a face that is one plane at each eye, turned back toward the outer corner by YAW (the eye window)."""

    def points(self, X, Z):
        X, Z = np.asarray(X, float), np.asarray(Z, float)
        return np.stack([X, (np.abs(X) - EX) * math.tan(math.radians(YAW)), Z], 1)

    def y(self, X, Z):
        return self.points(*np.broadcast_arrays(np.atleast_1d(X), np.atleast_1d(Z)))[:, 1]


def knobs(**k):
    K = eyelib._knobs(dict(width=0.192, height=0.9156, tilt=4.0, lower=0.3393, peak=0.4744, upper_full=0.5663,
                           lower_low=0.517, lower_full=0.3048, inner_drop=0.0))
    K.update(iris=(0.285, 0.54, -0.01, 0.09), **k)
    return K


def test_plate_is_flat():
    S = eyelib.Surface(Window(), knobs(), L, 1, (EX, EZ))
    assert not S.on and np.all(S(np.linspace(-0.02, 0.02, 5), np.zeros(5)) == 0)


def test_turned_follows_the_window_past_the_fold_and_faces_front_before_it():
    """turn (0, yaw, yaw) with the fold as the anchor: past the fold the surface is the window itself (no extra depth);
    nasal of it the surface faces the front, so it falls behind the window by (fold - x) tan(yaw)."""
    K = knobs(surface='turned', turn=(0.0, YAW, YAW), anchor='fold', fold_soft=0.001, fold_follow=0.0)
    S = eyelib.Surface(Window(), K, L, 1, (EX, EZ))
    W = K['width'] * L
    xf = float(S.fold_x(np.array([-0.01]))[0])              # the fold on the iris's middle row, eye widths
    assert abs(xf - (-(0.285 + 0.09))) < 1e-9
    zc = -0.01 * W                                          # (the iris's middle row)
    past = S(np.array([xf + 0.1, xf + 0.3, 0.4]) * W, np.full(3, zc))
    assert np.all(np.abs(past) < 1e-4) and np.ptp(past) < 1e-6, past       # (the fold's rounding on the grid: 0.03 mm)
    x = np.array([xf - 0.05, xf - 0.1]) * W
    want = (xf * W - x) * math.tan(math.radians(YAW))
    assert np.allclose(S(x, np.full(2, zc)), want, atol=1e-4), (S(x, np.full(2, zc)), want)


def test_side_view_cannot_see_nasal_of_the_fold():
    """the surface's world depth rises toward the nose from the fold (turn[0] < 0): a camera on the eye's own side sees
    the region nasal of the fold edge-on or from behind."""
    K = knobs(surface='turned', turn=(-5.0, 10.0, 45.0), anchor='corners', fold_follow=1.0)
    S = eyelib.Surface(Window(), K, L, 1, (EX, EZ))
    W = K['width'] * L
    rows = 0
    for z in (-0.2, -0.1, 0.0, 0.15, 0.3):
        xf = float(S.fold_x(np.array([z]))[0])
        x = np.linspace(-0.5, xf - 0.04, 24) * W
        x = x[eyelib._inside(np.stack([x, np.full(len(x), z * W)], 1), S.poly)]     # (inside the opening)
        if len(x) < 3:                                      # (the lids close in on the fold there)
            continue
        rows += 1
        y = Window().y(EX + x, np.full(len(x), EZ)) + S(x, np.full(len(x), z * W))
        assert np.all(np.diff(y) <= 1e-9), (z, np.diff(y))    # deeper toward the nose (x falls)
    assert rows >= 3, rows


def test_front_view_unchanged():
    """the plates' vertices keep their (x, z) whatever the surface: only the depth moves."""
    F = Window()
    K0, K1 = knobs(), knobs(surface='turned', turn=(-5.0, 10.0, 45.0), anchor='corners', fold_follow=1.0)
    v0, f0, uv0 = eyelib.plate(F, K0, L, 1, (EX, EZ))
    v1, f1, uv1 = eyelib.plate(F, K1, L, 1, (EX, EZ))
    assert np.allclose(v0[:, [0, 2]], v1[:, [0, 2]]) and f0 == f1 and uv0 == uv1
    assert np.abs(v1[:, 1] - v0[:, 1]).max() > 0.001


def test_no_scipy_in_the_eye_engine():
    """charkit.eyes runs in Blender's Python, which has no scipy."""
    src = open(eyelib.__file__).read()
    assert 'scipy' not in src.replace('has no scipy', '')


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
