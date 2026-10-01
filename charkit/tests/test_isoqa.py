"""charkit/isoqa.py's pieces (tool/pieceref: a piece's shape against its isolated reference, Michael 2026-09-30): an
isolated drawing splits into its named cells by its ink, and the comparison in the common frame reads a drawing
against itself scaled and moved as the same shape."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import isoqa as I
from charkit import registry


def _bow(k=1.0, dx=0, dy=0, shape=(420, 520)):
    """a five-cell bow drawn flat (pink cells, black outlines 1-2 px, a grey crease in each lobe) on white, scaled by k
    about the canvas's origin and moved by (dx, dy) -> rgb 0..1."""
    y, x = np.mgrid[:shape[0], :shape[1]].astype(float)
    y, x = (y - dy) / k, (x - dx) / k
    lab = np.zeros(shape, int)
    knot = (abs(x - 260) <= 22) & (abs(y - 90) <= 30)
    t = np.clip((abs(x - 260) - 22) / 150.0, 0, 1)                      # lobes: trapezoids widening outward
    lobe = (abs(x - 260) > 22) & (abs(x - 260) <= 172) & (abs(y - 90) <= 30 + 35 * t)
    tail = (y > 125) & (y <= 330) & (abs(abs(x - 260) - 40 - 0.25 * (y - 125)) <= 22)
    lab[tail & (x > 260)] = 4
    lab[tail & (x < 260)] = 5
    lab[lobe & (x > 260)] = 2
    lab[lobe & (x < 260)] = 3
    lab[knot] = 1
    from scipy import ndimage
    edge = np.zeros(shape, bool)
    for i in range(1, 6):                                               # each cell's own 1 px rim: a 2 px line between cells
        m = lab == i
        edge |= m & ~ndimage.binary_erosion(m, iterations=1, border_value=1)
    rgb = np.ones(shape + (3,))
    rgb[lab > 0] = (0.95, 0.55, 0.65)
    s = np.sign(x - 260)
    crease = (lab == 2) | (lab == 3)
    crease &= abs((y - 90) - 0.6 * s * (x - 260 - s * 40)) <= 1.8 * k
    crease &= (abs(x - 260) > 40) & (abs(x - 260) < 150)
    rgb[crease] = (0.62, 0.35, 0.42)                                    # a shade: not ink, a ridge
    rgb[edge] = 0.0
    return rgb


def test_a_five_cell_bow_splits_into_its_named_parts():
    R = I.ref_piece(_bow())
    P = R['parts']
    cx = lambda m: np.nonzero(m)[1].mean()
    assert all(P[k].sum() > 200 for k in ('knot', 'lobe_L', 'lobe_R', 'tail_L', 'tail_R'))
    assert abs(cx(P['knot']) - 260) < 3                                         # the compact middle cell
    assert cx(P['lobe_L']) > 260 > cx(P['lobe_R'])                              # her left: the picture's right
    assert cx(P['tail_L']) > 260 > cx(P['tail_R'])
    assert np.nonzero(P['tail_L'])[0].max() > np.nonzero(P['lobe_L'])[0].max()  # the tails reach lowest
    assert R['line'][85:95, 236:240].any()                                      # the knot's outline is a line


def test_the_same_bow_scaled_and_moved_reads_itself():
    R = I.ref_piece(_bow())
    for k, dx, dy in ((0.8, 7, 3), (1.25, -40, 11), (1.0, 13, -9)):
        M = I.compare(I.ref_piece(_bow(k, dx, dy, shape=(560, 700))), R)
        assert M['body'] > 0.95 and M['tails'] > 0.9, (k, M['body'], M['tails'])
        ko, kr = M['knot_size']
        assert abs(ko / kr - 1) < 0.05
        assert M['ours']['knot_line'] == M['ref']['knot_line'] == 1.0                 # outlined all round
        for side in ('L', 'R'):
            co, cr = M['ours']['crease'][side], M['ref']['crease'][side]
            assert abs(co['len'] / cr['len'] - 1) < 0.08 and abs(co['dir'] - cr['dir']) < 1.0


def test_a_rounder_bow_reads_worse():
    R = I.ref_piece(_bow())
    rgb = _bow()
    from scipy import ndimage
    pillow = ndimage.binary_opening(rgb.min(2) < 0.92, iterations=18)          # the lobes' corners rounded away
    soft = rgb.copy()
    soft[(rgb.min(2) < 0.92) & ~pillow] = 1.0
    M = I.compare(I.ref_piece(soft), R)
    assert M is None or M['body'] < 0.95


def test_the_info_checks_report_their_grade_and_the_graded_ones_carry_the_flag():
    c = I._check('tails', 0.5)
    assert c['status'] == 'INFO' and c['graded_as'] == 'FAIL'
    assert registry.is_flag(I._check('crease_dir', 30.0)) and registry.is_flag(I._check('body', 0.6))
    assert I._check('body', 0.871)['status'] == 'PASS' and I._check('body', 0.659)['status'] == 'FAIL'


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f()
            print('ok', k)


def test_the_body_is_its_silhouette_lines_drawn_inside_it_cost_nothing():
    """iso_bow_body compares silhouettes: the same bow with ink creases drawn across its lobes (lines the line checks
    ask for) reads as itself, where the parts' pixels alone lost a share per line (tool/pieceref round 3)."""
    rgb = _bow()
    inked = rgb.copy()
    y, x = np.mgrid[:rgb.shape[0], :rgb.shape[1]].astype(float)
    s = np.sign(x - 260)
    lobes = (abs(x - 260) > 40) & (abs(x - 260) < 150) & (abs(y - 90) < 40)
    inked[lobes & (abs((y - 95) - 0.3 * s * (x - 260)) <= 2.5)] = 0.0         # a 5 px ink crease in each lobe
    R, Ri = I.ref_piece(rgb), I.ref_piece(inked)
    assert I.compare(Ri, R)['body'] > 0.97
    parts_only = I.iou(I.normalised(Ri)['lobe_L'], I.normalised(R)['lobe_L'])
    assert parts_only < I.compare(Ri, R)['body']
