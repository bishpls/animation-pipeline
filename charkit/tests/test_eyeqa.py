"""charkit.eyeqa on drawn eyes with known answers (venv: run this file, or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import eyeqa

AMBER, WHITE, DARK, SKIN = (0.85, 0.6, 0.15), (0.97, 0.97, 0.99), (0.08, 0.05, 0.04), (1.0, 0.88, 0.82)


def eye(n=200, open_h=0.8, pupil=(0.25, 0.4), gap=0):
    """an eye drawing: an opening (ellipse, height open_h of its width), an iris 0.3 of the width filling the height,
    a pupil (its half-axes as shares of the iris's), a lid line `gap` px above the opening, skin around."""
    yy, xx = np.mgrid[0:n, 0:n] / n
    im = np.zeros((n, n, 4)); im[..., :3] = SKIN; im[..., 3] = 1
    op = ((xx - 0.5) / 0.4) ** 2 + ((yy - 0.5) / (0.4 * open_h)) ** 2 <= 1
    ir = (((xx - 0.5) / 0.12) ** 2 + ((yy - 0.5) / (0.4 * open_h)) ** 2 <= 1) & op
    pu = ((xx - 0.5) / (0.12 * pupil[0])) ** 2 + ((yy - 0.5) / (0.4 * open_h * pupil[1])) ** 2 <= 1
    im[op, :3] = WHITE; im[ir, :3] = AMBER; im[pu & ir, :3] = DARK
    # the upper lid line: a band following the opening's top edge, lifted `gap` px off it
    yl = yy + gap / n
    band = (((xx - 0.5) / 0.42) ** 2 + ((yl - 0.5) / (0.4 * open_h + 0.03)) ** 2 <= 1) & \
           ~(((xx - 0.5) / 0.4) ** 2 + ((yl - 0.5) / (0.4 * open_h)) ** 2 <= 1) & (yl < 0.5) & ~op
    im[band, :3] = DARK
    return im


def test_measures():
    M = eyeqa.measure(eye(), 200.0)                                   # 200 px per L
    assert abs(M['aspect'] - 0.8) < 0.05, M['aspect']
    assert abs(M['pupil_run'] - 0.4) < 0.06, M['pupil_run']
    assert M['lid_gap'] is not None and M['lid_gap'] < 0.01


def test_slit_and_flat_eye_fail():
    d = eyeqa.measure(eye(), 200.0)
    o = eyeqa.measure(eye(open_h=0.55, pupil=(0.12, 0.8), gap=8), 200.0)
    C = eyeqa.compare(o, d)
    assert C['aspect']['status'] == 'FAIL' and C['pupil_run']['status'] == 'FAIL' and C['pupil_aspect']['status'] == 'FAIL'
    assert C['lid_gap']['status'] in ('WARN', 'FAIL')
    same = eyeqa.compare(d, d)
    assert all(v['status'] == 'PASS' for v in same.values()), same


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
