"""charkit.hairsplit: the lock splitter on a drawing with known locks (a bob with three locks, its lock lines drawn open
from the hem's notches as a turnaround draws them), the head-centred coordinates on a known shell, the interval and
rank helpers (venv: run this file, or pytest). The splitter's score on the design against the 52-lock truth is a
measurement (docs/workstreams/hairsplit.md, tools/hairsplit/ablation.py), not a test: it needs the produced masks."""
import math, os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import hairsplit as hs

LINE = 4          # charkit.bodyqa.CLASS['line']


def _bob():
    """a 220 x 220 drawing at 200 px per L: a bob (rows 30-175, cols 40-180) whose hem has three tips (cols 63, 110,
    157) and two notches (cols 87, 133); a lock line drawn up from each notch, stopping 60% of the way to the top (open,
    as the sheets draw them); the outline in ink."""
    from skimage import draw
    H, W = 220, 220
    hair = np.zeros((H, W), bool)
    rr, cc = draw.ellipse(70, 110, 45, 70, (H, W))
    hair[rr, cc] = True
    hair[70:150, 40:181] = True
    # the hem: three tips (triangles under the mass) between the sides
    for c0, c, c1 in ((40, 63, 86), (87, 110, 133), (134, 157, 180)):
        r_, c_ = draw.polygon([149, 175, 149], [c0, c, c1], (H, W))
        hair[r_, c_] = True
    rgb = np.ones((H, W, 3))
    rgb[hair] = (0.85, 0.47, 0.32)
    from scipy import ndimage
    edge = hair & ~ndimage.binary_erosion(hair, iterations=2)
    ink = edge.copy()
    for c in (87, 133):
        r_, c_ = draw.line(150, c, 95, c)
        ink[r_, c_] = True
        ink[r_, c_ + 1] = True
    rgb[ink] = (0.05, 0.03, 0.03)
    raw = np.where(hair, 2, 0)
    raw[ink] = LINE
    return dict(rgb=rgb, raw=raw, hair=hair & ~edge, az=0.0, col_axis=110.0, row_eye=200.0, ppl=200.0,
                pieces={}, occ=np.zeros((H, W), bool))


def test_bob_three_locks():
    V = _bob()
    S = hs.Split('front', V, 200.0)
    S.run('locks')
    L = S.full(S.locks)
    # the three locks below the drawn lines' tops are three different locks, each one lock down to its tip
    a, b, c = L[130, 63], L[130, 110], L[130, 157]
    assert a and b and c and len({a, b, c}) == 3, (a, b, c)
    assert L[165, 63] == a and L[165, 110] == b and L[165, 157] == c
    # the extensions closed the lines toward the crown: the locks stay apart above the drawn lines' tops
    assert L[80, 80] != L[80, 140]
    # three tips found on the hem, at the drawn tips
    r0, _, c0, _ = S.box                                         # the split's arrays are on a crop round the hair
    hem = [t for t in S.tip_list if t['rc'][0] + r0 > 165]
    cols = sorted(round(t['rc'][1] + c0) for t in hem)
    assert len(cols) == 3 and all(abs(x - y) <= 4 for x, y in zip(cols, (63, 110, 157))), cols


def test_bob_stages_order():
    """closing alone leaves the hem's locks joined above the drawn lines' tops only where nothing closes them; the
    full splitter never scores below the cells on this drawing (its three locks)."""
    V = _bob()
    S = hs.Split('front', V, 200.0)
    S.pipeline()
    truth = np.zeros(S.H.shape, np.int32)
    rr, cc = np.nonzero(S.H)
    R0, _, C0, _ = S.box                                         # crop -> drawing coordinates
    for k, (c0, c1) in enumerate(((0, 87), (87, 133), (133, 999)), 1):
        sel = (cc + C0 >= c0) & (cc + C0 < c1) & (rr + R0 > 95)
        truth[rr[sel], cc[sel]] = k

    def best(lab):
        s = []
        for k in (1, 2, 3):
            m = truth == k
            v, n = np.unique(lab[m], return_counts=True)
            j = v[np.argmax(n)]
            s.append((m & (lab == j)).sum() / (m | ((lab == j) & (truth > 0))).sum())
        return np.mean(s)
    assert best(S.locks) >= best(S.cells) - 1e-9
    assert best(S.locks) > 0.8


class _Shell(hs.Shell):
    def __init__(self):
        self.z = np.linspace(-1, 1, 21)
        self.x0 = np.zeros(21); self.a = np.full(21, 0.5)
        self.y0 = np.full(21, 0.1); self.b = np.full(21, 0.4)


def test_shell_azimuths():
    sh = _Shell()
    # the front (az 0) sees u = x: a point at phi 30 deg on the ellipse shows at u = a sin 30
    assert abs(sh.phi(0.5 * math.sin(math.radians(30)), 0.0, 0.0) - 30.0) < 0.5
    # the profile (az 90, from her left) sees u = y: the point at phi 90 (her left side) shows at u = y0
    assert abs(sh.phi(0.1, 0.0, 90.0) - 90.0) < 0.5
    # the back (az 180) sees u = -x: her left (phi 90..180) on the picture's left
    assert 90.0 < sh.phi(-0.3, 0.0, 180.0) <= 180.0
    # past the limb: the limb's azimuth
    assert abs(abs(sh.phi(0.9, 0.0, 0.0)) - 90.0) < 1.0


def test_intervals_and_ranks():
    assert hs._gap([80, 100], [95, 120]) == 0.0
    assert abs(hs._gap([80, 100], [110, 120]) - 10.0) < 1e-9
    assert hs._gap([170, 190], [-175, -160]) == 0.0              # across +-180
    assert hs._visible([85, 115], 180.0) and not hs._visible([-30, 30], 180.0)
    r = hs._ranks([1, 2, 3], {(1, 2): 2, (2, 3): 1})
    assert r[1] > r[2] > r[3]


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f()
            print(k, 'ok')
