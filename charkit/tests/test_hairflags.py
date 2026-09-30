"""charkit.hairflagqa: Michael's hair flags' measures on shapes with known answers (venv: run this file, or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import hairflagqa as hf

PPL = 212.5


def _strand(pts, width, shape=(120, 120)):
    """a strand drawn as discs along a polyline (row, col)."""
    yy, xx = np.mgrid[:shape[0], :shape[1]]
    m = np.zeros(shape, bool)
    P = np.asarray(pts, float)
    for a, b in zip(P[:-1], P[1:]):
        for t in np.linspace(0, 1, 20):
            p = a + (b - a) * t
            m |= (yy - p[0]) ** 2 + (xx - p[1]) ** 2 <= width ** 2
    return m


def _arc(sign=1, wave=0.0):
    th = np.linspace(0, 1.2, 25)
    r, c = 100 - 60 * np.sin(th), 40 + sign * 40 * (1 - np.cos(th))
    c = c + wave * np.sin(np.linspace(0, 3 * np.pi, 25))
    return np.c_[r, c]


def test_ahoge_shape():
    d = _strand(_arc(), 3)
    assert hf.ahoge_shape(d, d, PPL)['f'] == 1.0
    moved = hf.shift(d, 3, -2, False)                      # a placement off by a few px: the shape still agrees
    assert hf.ahoge_shape(moved, d, PPL)['f'] == 1.0
    assert hf.ahoge_shape(_strand(_arc(-1), 3), d, PPL)['f'] < 0.5     # curled the other way


def test_bend():
    root = np.zeros((120, 120), bool); root[104:, :] = True
    one = hf.bend(_strand(_arc(), 3), root)
    s = hf.bend(_strand(_arc(wave=8.0), 3), root)
    assert one is not None and one < 10 and s > 40, (one, s)


def test_gaps():
    lab = np.zeros((60, 60), np.int32)
    lab[30:, :] = hf.PART0                                  # the mass
    lab[10:20, 20:24] = hf.PART0 + 1                        # a flyaway 10 px above it
    lab[25:30, 40:43] = hf.PART0 + 2                        # one touching it
    g = hf.gaps(lab, ['upper_back', 'flyaways', 'flyaways'], PPL)
    assert abs(g[1] - 10 / PPL) < 1e-3 and g[2] == 0.0, g


def test_part_lines_and_hem():
    lab = np.zeros((60, 60), np.int32)
    lab[10:50, 10:30] = hf.PART0
    lab[10:50, 30:50] = hf.PART0 + 1
    b = hf.part_lines(lab)
    assert b[20, 29] and not b[20, 20] and not b[5, 29]
    hair = np.zeros((200, 400), bool)
    hair[20:150] = True
    for c in range(20, 400, 50):                            # eight tips 30 px deep
        hair[150:180, c - 6:c + 6] = True
    assert hf.hem(hair, PPL)['tips'] == 8
    assert hf.hem(hair[:, :] & (np.arange(200)[:, None] < 150), PPL)['tips'] == 0


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f()
            print(k, 'ok')
