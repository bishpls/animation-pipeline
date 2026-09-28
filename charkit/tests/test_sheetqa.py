"""charkit.sheetqa on a drawn face with known answers (venv: run this file, or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import sheetqa

BG, SKIN, LINE, IRIS, SHADE = (0.97, 0.97, 0.94), (0.98, 0.855, 0.757), (0.10, 0.08, 0.07), (0.95, 0.80, 0.10), (0.75, 0.62, 0.52)


def drawing(ppl=100.0, half_w=0.30, chin=0.40, neck=0.12):
    """a front face: an outlined skin ellipse (half-width half_w L, the chin `chin` L under the eye line), two iris dots
    0.168 L either side, a shaded neck `neck` L half-wide under a drawn jaw line."""
    n = 200
    im = np.ones((n, n, 3)) * BG
    yy, xx = np.mgrid[0:n, 0:n].astype(float)
    cx, ey = 100.0, 70.0
    top = ey - 0.3 * ppl
    cy, ry = (top + ey + chin * ppl) / 2, (ey + chin * ppl - top) / 2
    face = ((xx - cx) / (half_w * ppl)) ** 2 + ((yy - cy) / ry) ** 2 <= 1
    ring = (((xx - cx) / (half_w * ppl + 1.5)) ** 2 + ((yy - cy) / (ry + 1.5)) ** 2 <= 1) & ~face
    nk = (np.abs(xx - cx) <= neck * ppl) & (yy > cy) & ~face & ~ring
    im[nk] = SHADE; im[ring] = LINE; im[face] = SKIN
    for sx in (-1, 1):
        im[((xx - cx - sx * 0.168 * ppl) ** 2 + (yy - ey) ** 2) <= 16] = IRIS
    return im, [(cx - 0.168 * ppl, ey), (cx + 0.168 * ppl, ey)]


def test_front_measures():
    im, eyes = drawing()
    M = sheetqa.measure_figure(im, 'front', 100.0, eyes)
    assert abs(M['chin'] - (-0.40)) < 0.02, M['chin']
    # an ellipse's half-width at 55% of the way down from its centre-ish eye line: compare with the analytic value
    assert M['widths']['d55'] and 0.2 < M['widths']['d55'] < 0.31
    assert abs(M['neck'] - 0.12) < 0.02, M['neck']


def test_compare_catches_a_narrow_face_and_thick_neck():
    d_im, d_eyes = drawing()
    o_im, o_eyes = drawing(half_w=0.22, neck=0.18)
    D = {'front': sheetqa.measure_figure(d_im, 'front', 100.0, d_eyes)}
    O = {'front': sheetqa.measure_figure(o_im, 'front', 100.0, o_eyes)}
    C = sheetqa.compare(O, D)
    assert C['width']['status'] == 'FAIL' and C['neck_to_jaw']['status'] == 'FAIL'
    same = sheetqa.compare(D, D)
    assert same['width']['status'] == 'PASS' and same['neck_to_jaw']['status'] == 'PASS'


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
