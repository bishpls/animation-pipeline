"""charkit.bowqa's profile measures on synthetic masks (Michael's flag, 2026-09-30: the ribbon tails as blades swung
forward, the loops as flat disks): the design against itself and moved 2 px reads within PASS; the tails swung
forward, slanted or sunk back, and the loops tipped, thinned or cut short read FAIL; the bow mesh splits into its
loops and its two tails (venv: run this file, or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import bowqa, garments as gm

PPL = 200.0
N = 400
FW = -1                              # forward is to the left, as on the profile grid


def ellipse_mask(cx, cy, a, b, lean=0.0):
    """an ellipse (semi-axes a across, b up, px) leaning `lean` degrees (its top toward larger columns)."""
    y, x = np.mgrid[:N, :N]
    t = np.radians(lean)
    u, v = x - cx, cy - y
    p, q = u * np.cos(t) - v * np.sin(t), u * np.sin(t) + v * np.cos(t)
    return (p / a) ** 2 + (q / b) ** 2 <= 1


def tails_mask(front, top, bottom, width, slant=0.0):
    """a ribbon hanging from row `top` to `bottom`, its front edge at column `front` at the top moving `slant` px
    forward (left) per row down, `width` px deep."""
    m = np.zeros((N, N), bool)
    for r in range(top, bottom + 1):
        f = int(round(front - slant * (r - top)))
        m[r, max(0, f):f + width] = True
    return m


def design():
    loops = ellipse_mask(200, 120, 45, 75, lean=25)       # a tall loop standing up, fullest low
    tails = tails_mask(170, 170, 330, 40)                  # hanging straight under it
    return loops, tails


def measure(lo, to, ld, td):
    return bowqa.profile_measure(lo, to, ld, td, PPL, FW, top_row=175)


def shift(a, dy, dx):
    return np.roll(np.roll(a, dy, 0), dx, 1)


def test_the_design_against_itself_and_moved_two_px_passes():
    ld, td = design()
    for dy, dx in ((0, 0), (2, 0), (-2, 0), (0, 2), (0, -2)):
        M = measure(shift(ld, dy, dx), shift(td, dy, dx), ld, td)
        for k in ('reach', 'hang', 'thick', 'lean'):
            assert bowqa.grade(k, M[k]['value']) == 'PASS', (dy, dx, k, M[k])


def test_tails_swung_forward_fail_the_reach():
    ld, td = design()
    M = measure(ld, shift(td, 0, -int(0.1 * PPL)), ld, td)          # 0.1 L forward
    assert bowqa.grade('reach', M['reach']['value']) == 'FAIL'
    assert M['reach']['median'] > 0.05                               # + ours forward


def test_tails_sunk_back_fail_the_reach_too():
    ld, td = design()
    M = measure(ld, shift(td, 0, int(0.08 * PPL)), ld, td)
    assert bowqa.grade('reach', M['reach']['value']) == 'FAIL'
    assert M['reach']['median'] < -0.03


def test_tails_slanting_forward_fail_the_hang():
    ld, td = design()
    blade = tails_mask(170, 170, 330, 40, slant=0.4)                  # ~22 degrees forward from the knot
    M = measure(ld, blade, ld, td)
    assert M['hang']['ours'] > M['hang']['design'] + 10
    assert bowqa.grade('hang', M['hang']['value']) == 'FAIL'


def test_loops_tipped_fail_the_lean_and_short_ones_the_thickness():
    ld, td = design()
    tipped = ellipse_mask(200, 120, 45, 75, lean=45)
    M = measure(tipped, td, ld, td)
    assert bowqa.grade('lean', M['lean']['value']) == 'FAIL'
    short = ellipse_mask(195, 95, 55, 45, lean=45)                  # a squat disk riding high, ending short
    M = measure(short, td, ld, td)
    assert bowqa.grade('thick', M['thick']['value']) == 'FAIL'
    assert M['thick']['ours'][-1] == 0.0                             # no loop at the drawn loops' foot


def test_the_bow_mesh_splits_into_loops_and_two_tails():
    G = gm._bow_mesh(np.zeros(3), 0.2, 0.62, 0.25, end=0.2, end_p=[4.0, 1.4],
                     ribbon=dict(turn=40, w=[0.25, 0.415], out=0.3, hinge=1.0))
    V, F = G['verts'], np.array([f[:3] for f in G['faces']] + [(f[0], f[2], f[3]) for f in G['faces'] if len(f) == 4])
    tail = bowqa.bow_parts(V, F)
    ts = G['tail_s']
    on_tail = np.isfinite(ts[F[:, 0]])
    assert tail is not None and (tail == on_tail).all()


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f()
            print('ok', k)
