"""charkit.accessories' crown and pin templates: their geometry follows their knobs (sizes in L, counts, materials)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import accessories  # noqa: E402


def test_crown_sizes_points_and_jewels():
    v, f, m = accessories.crown(dict(rx=0.5, ry=0.4, height=0.6, points=7, jewels=7))
    assert abs(v[:, 2].max() - 0.6) < 1e-9 and abs(v[:, 2].min()) < 1e-9          # its height, its base at 0
    w = v[:, 0].max() - v[:, 0].min(); d = v[:, 1].max() - v[:, 1].min()
    jr = 2 * accessories.CROWN['jewel_r'] * 0.6                                     # (the jewels stand on its face)
    assert 1.0 <= w <= (1 + accessories.CROWN['flare']) + jr and 0.8 <= d <= 0.8 * (1 + accessories.CROWN['flare']) + jr
    assert set(m.tolist()) == {0, 1, 2} and len(f) == len(m)                        # metal and two jewel materials
    tips = v[np.isclose(v[:, 2], 0.6)]
    assert len(tips) == 2 * 7                                                        # each blade's tip, out and in


def test_pin_radius_dome_and_emblem():
    yy, xx = np.mgrid[0:12, 0:12] - 5.5
    cells = np.where(np.hypot(yy, xx) < 2.5, 2, np.where(np.hypot(yy, xx) < 4.0, 1, 0)).tolist()   # a ring, a disc
    v, f, m = accessories.pin(dict(r=0.15, emblem=dict(cells=cells)))
    assert abs(np.hypot(v[:, 0], v[:, 1]).max() - 0.15) < 1e-9
    assert v[:, 2].min() == 0.0 and v[:, 2].max() > 0.15 * accessories.PIN['thick']   # its back flat, its face domed
    assert set(m.tolist()) == {0, 1, 2, 3}                                           # face, rim, the emblem's colours


if __name__ == '__main__':
    for k, fn in list(globals().items()):
        if k.startswith('test_'):
            fn(); print('ok', k)
