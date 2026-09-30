"""charkit/partqa.py's measures (tool/pieceref: the bow's parts and the lines inside them, Michael 2026-09-30): each
separates the flagged shape (a knot with no outline, pillow lobes with no crease) from the drawn one and reads the same
on a shape moved against itself."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import partqa as P
from charkit import registry


def test_a_rectangle_knot_against_an_ellipse():
    y, x = np.mgrid[:60, :60]
    box = (abs(y - 30) <= 14) & (abs(x - 30) <= 10)
    ell = ((y - 30) / 14.5) ** 2 + ((x - 30) / 10.5) ** 2 <= 1
    kb, ke = P.knot_rect(box, 100), P.knot_rect(ell, 100)
    assert kb['fill'] > 0.95 and abs(ke['fill'] - np.pi / 4) < 0.03
    assert P.rect_err(kb, kb) == 0 and P.rect_err(ke, kb) > P.LIMITS['knot_rect'][1]


def test_the_knot_outlined_or_merged_into_the_lobes():
    knot = np.zeros((40, 60), bool); knot[10:30, 25:35] = True
    lobes = np.zeros((40, 60), bool); lobes[5:35, 5:24] = True; lobes[5:35, 36:55] = True
    line = np.zeros((40, 60), bool); line[:, 24] = True; line[:, 35] = True
    assert P.outline_share(knot, line, lobes) == 1.0
    merged = lobes.copy(); merged[5:35, 24] = True; merged[5:35, 35] = True
    assert P.outline_share(knot, np.zeros_like(line), merged) == 0.0


def test_a_crease_inside_a_lobe_and_none_in_a_pillow():
    y, x = np.mgrid[:120, :200]
    lobe = ((y - 60) / 50.0) ** 2 + ((x - 100) / 90.0) ** 2 <= 1
    outline = lobe & ~(((y - 60) / 47.0) ** 2 + ((x - 100) / 87.0) ** 2 <= 1)
    diag = (abs((y - 60) + 0.5 * (x - 100)) <= 1.0) & (abs(x - 100) <= 50)       # up toward the picture's right
    c0 = P.crease(lobe & ~outline, outline, 200, 'L')          # (200 px per L: the band 3.6 px, the ring 3)
    assert c0['len'] == 0 and c0['dir'] is None
    c1 = P.crease(lobe & ~outline & ~diag, outline | diag, 200, 'L')
    assert c1['len'] > 0.2 and abs(c1['dir'] - 26.6) < 3
    c2 = P.crease(np.roll(lobe & ~outline & ~diag, 2, 1), np.roll(outline | diag, 2, 1), 200, 'L')
    assert c2['len'] == c1['len'] and c2['dir'] == c1['dir']                           # moved: the same reading


def test_the_bow_mesh_splits_into_its_parts():
    def box(cx, cz, w=0.1, h=0.1):
        V = np.array([[cx + a * w, b * 0.02, cz + c * h] for a in (-1, 1) for b in (-1, 1) for c in (-1, 1)])
        T = np.array([[0, 1, 3], [0, 3, 2], [4, 5, 7], [4, 7, 6], [0, 1, 5], [0, 5, 4], [2, 3, 7], [2, 7, 6]])
        return V, T
    parts = [box(0, 0, 0.03), box(0.2, 0), box(-0.2, 0), box(0.1, -0.5), box(-0.1, -0.5)]
    V = np.concatenate([p[0] for p in parts]); T = np.concatenate([p[1] + 8 * i for i, p in enumerate(parts)])
    c = P.split(V, T)
    got = [int(c[8 * i]) for i in range(5)]
    assert got == [P.CODES[k] for k in ('knot', 'lobe_L', 'lobe_R', 'tail_L', 'tail_R')]


def test_the_checks_carry_the_flag_but_the_lobes_guard():
    assert registry.is_flag(P._check('crease_dir', 30.0)) and P._check('iou', 0.7)['status'] == 'PASS'


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f()
            print('ok', k)
