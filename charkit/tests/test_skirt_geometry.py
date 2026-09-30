"""charkit.garments' flap stair and the skirt's band rows (tool/skirt) on known answers (venv: run this file, or
pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import garments as gm


def test_flap_stair_treads():
    e, ln = gm.flap_stair({'steps': 4, 'outer': 0.1, 'inner': 0.4})
    assert np.allclose(e, [0, 0.25, 0.5, 0.75, 1]) and np.allclose(ln, [0.1, 0.2, 0.3, 0.4])
    e, ln = gm.flap_stair({'steps': 3, 'widths': [2, 1, 1], 'lengths': [0.2, 0.3, 0.5]})
    assert np.allclose(e, [0, 0.5, 0.75, 1]) and np.allclose(ln, [0.2, 0.3, 0.5])


def test_band_rows_levels_per_column():
    n = 144
    th = -np.pi + np.arange(n) * 2 * np.pi / n                     # the loft's column angles (0 the front)
    lenc = np.linspace(0.9, 1.1, n)
    stair = {'height': 0.14, 'stair': [[0, 0.44], [10, 0.34], [20, 0.24], [30, 0.14]]}
    V, hb = gm.band_rows(stair, th, np.radians(20), lenc, np.linspace(0, 1, 17), 1.0)
    thc = np.degrees(np.abs(th + np.pi / n))
    assert (hb[thc < 20] == 0).all()                                # the cream panel: no band
    assert np.isclose(hb[np.argmin(np.abs(thc - 25))], 0.44) and np.isclose(hb[np.argmin(np.abs(thc - 45))], 0.24)
    assert np.isclose(hb[np.argmin(np.abs(thc - 120))], 0.14)
    assert (np.diff(V, axis=0) > 0).all() and np.allclose(V[-1], 1)  # rows ascend in every column
    for h in (0.44, 0.34, 0.24, 0.14):                             # a row on each level in every column
        assert np.isclose(V, (1 - h / lenc)[None, :]).any(0).all()


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok', name)
