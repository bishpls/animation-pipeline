"""the authored torso's shoulders as a template (code_body.shoulder_width, shoulders; tool/collar): a level top out to
the shoulder point, a rounded edge, eased back into the fitted torso below; the neck ring (the head's zip) untouched and
the chest's front depth kept."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import code_body as cb


SH = dict(z=-0.525, x=0.47, round=0.05, hold=0.05, fall=0.15)


def test_the_width_is_level_then_rounded_then_eased_out():
    z = np.array([-0.50, -0.525, -0.55, -0.575, -0.60, -0.70, -0.80, -0.90])
    a, w = cb.shoulder_width(z, SH)
    assert np.isnan(a[0]) and w[0] == 0.0                         # above the shoulders' top: nothing
    assert abs(a[1] - (0.47 - 0.05)) < 1e-9                      # the top's outer end before its rounding
    assert abs(a[3] - 0.47) < 1e-9 and a[4] == 0.47              # the shoulder point, held below the round
    assert w[3] == 1.0 and 0.0 < w[5] < 1.0 and w[7] == 0.0       # eased out over `fall` under `hold`
    assert np.all(np.diff(a[1:4]) > 0)                           # widening down the round


class _Env:
    def __init__(self, r):
        self.r = r

    def at(self, t, th):
        return np.full(np.shape(t), self.r)


def test_the_rows_are_added_and_widened_but_the_neck_ring_and_the_front_hold():
    rows = np.linspace(-0.52, -1.2, 18)
    ts = rows[0] - rows
    nth = 72
    th = -np.pi + (np.arange(nth) + 0.5) * 2 * np.pi / nth
    ay = 0.05
    P = np.tile([0.30, 0.25, 0.25, 2.3, ay], (len(rows), 1))
    P[0] = [0.2, 0.2, 0.2, 2.0, ay]
    R = np.stack([cb.section_r(p, th, ay) for p in P])
    meas = np.zeros(R.shape, bool)
    Bh = np.full(R.shape, np.inf)
    rows2, ts2, R2, P2, M2 = cb.shoulders(SH, rows, ts, th, R, P, meas, ay, _Env(2.0), Bh)
    assert len(rows2) == len(rows) + len(cb.SHOULDER_ROWS) and np.all(np.diff(rows2) < 0)
    assert np.allclose(R2[0], R[0])                             # the cut's ring: the head's zip
    side = np.argmin(np.abs(th - np.pi / 2))
    front = np.argmin(np.abs(th))
    k = int(np.argmin(np.abs(rows2 - (-0.60))))
    assert abs(R2[k, side] - 0.47) < 0.02                        # the shoulder point at the side
    assert abs(R2[k, front] - cb.section_r(P2[k], th, ay)[front]) < 0.01     # the chest's front depth kept (2.5 deg off)
    assert R2.shape == (len(rows2), nth) and M2.shape == R2.shape and P2.shape == (len(rows2), 5)


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f()
            print('ok', k)
