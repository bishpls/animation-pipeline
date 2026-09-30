"""charkit/collarqa.py's measures (tool/collar: Michael's flags on the shoulders, the collar and the bow, 2026-09-30):
each separates the flagged shape from the drawn one, and reads zero on a shape against itself (the design's calibration:
the checks grade ours less the design's)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import collarqa as cq
from charkit import registry


def _disk_end_loop(h=40, w=120, round_end=True):
    """a loop mask (the bow's right half): a band w px long, h tall, its outer end rounded (a half disk) or cut straight."""
    m = np.zeros((h + 10, w + h + 10), bool)
    y, x = np.mgrid[:m.shape[0], :m.shape[1]]
    body = (y >= 5) & (y < 5 + h) & (x >= 5) & (x < 5 + w)
    if round_end:
        r = h / 2
        body |= (x >= 5 + w) & ((x - (5 + w)) ** 2 + (y - (5 + r)) ** 2 <= r * r)
    m |= body
    both = np.concatenate([m[:, ::-1], m], 1)             # both loops: mirror image either side of the knot
    return both


def test_a_straight_cut_loop_reads_far_straighter_than_a_rounded_one():
    ppl = 400.0
    cut, rnd = cq.loop_ends(_disk_end_loop(round_end=False), ppl), cq.loop_ends(_disk_end_loop(round_end=True), ppl)
    assert cut['L'] > 0.9 and cut['R'] > 0.9
    assert rnd['L'] < 0.45 and rnd['R'] < 0.45
    assert cut['L'] - rnd['L'] > cq.LIMITS['loop_end'][1]         # the flagged cut FAILs against a round end


def test_the_trough_is_the_water_line_between_higher_points():
    assert cq.trough([-0.50, -0.50, -0.50, -0.50]) == 0.0
    assert abs(cq.trough([-0.52, -0.55, -0.61, -0.57, -0.56]) - 0.05) < 1e-9     # the flagged dip beside the collar
    assert cq.trough([-0.50, -0.55, -0.60]) == 0.0                               # a steady fall holds no water


def test_a_square_panel_against_a_rounded_flap():
    ppl = 200.0
    y, x = np.mgrid[:120, :200]
    square = (np.abs(x - 100) < 70) & (y > 10) & (y < 100)
    flap = square & (((x - 100) / 70.0) ** 2 + ((y - 10) / 90.0) ** 2 <= 1.0)
    ps, pf = cq.panel(square, ppl), cq.panel(flap, ppl)
    assert abs(ps['square'] - 1.0) < 0.02
    assert ps['square'] - pf['square'] > cq.LIMITS['square'][1]
    assert cq.iou(square, square) == 1.0


def test_the_shoulder_line_and_its_measure_read_zero_against_itself():
    ppl = 212.47
    H, W = int(7.5 * ppl), int(4.6 * ppl)
    U = np.zeros((H, W), bool)
    r = int(round((1.3 + 0.51) * ppl))                                            # a level shoulder line at -0.51 L
    U[r:r + 100, int(1.6 * ppl):int(3.0 * ppl)] = True
    line = cq.shoulder_line(U, ppl)
    M = cq.line_measure(line, line)
    for s in 'LR':
        assert M[s]['dz'] == 0.0 and abs(M[s]['slope']) < 0.02
        assert abs(M[s]['z'] + 0.51) < 0.006


def test_edge_touch_finds_colour_against_colour_without_a_line():
    a = np.zeros((10, 10), bool); a[2:8, 2:5] = True
    b = np.zeros((10, 10), bool); b[2:8, 5:8] = True
    assert cq.edge_touch(a, b).sum() == 6
    b2 = np.zeros((10, 10), bool); b2[2:8, 6:8] = True                          # a line column between them
    assert cq.edge_touch(a, b2).sum() == 0


def test_the_flag_checks_carry_their_flag():
    c = cq._check('loops', 'loop_end', 0.6)
    assert registry.is_flag(c) and c['status'] == 'FAIL'
    assert cq._check('collar', 'iou', 0.9)['status'] == 'PASS'


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f()
            print('ok', k)
