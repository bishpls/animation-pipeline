"""charkit.geom.wind: the garments' winding, decided venv-side (GEOM_TRUTH step 7a), on shapes with known answers
(venv: run this file, or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit.geom import wind


def _tube(n=12, rows=4, r=1.0):
    V = np.array([(r * np.cos(2 * np.pi * i / n), r * np.sin(2 * np.pi * i / n), z) for z in range(rows) for i in range(n)])
    F = [(k * n + i, k * n + (i + 1) % n, (k + 1) * n + (i + 1) % n, (k + 1) * n + i) for k in range(rows - 1) for i in range(n)]
    return V, F


def _normals(V, P):
    return np.array([np.cross(V[f[1]] - V[f[0]], V[f[-1]] - V[f[0]]) for f in P])


def test_tube_outward_whatever_the_input():
    V, F = _tube()
    rng = np.random.default_rng(0)
    for trial in range(4):
        G = [tuple(wind.reverse(f)) if rng.random() < 0.5 else f for f in F]      # a random mix of windings
        P, _, flip, info = wind.orient(V, G)
        N = _normals(V, P)
        C = np.array([V[list(f)].mean(0) for f in P])
        assert ((N[:, :2] * C[:, :2]).sum(1) > 0).all()                       # every polygon faces out
        assert info['regions'] == 1 and info['flux'][0] > 0.99 * info['scale'][0]


def test_reverse_keeps_the_first_corner_and_uvs_follow():
    assert wind.reverse((4, 5, 6, 7)) == [4, 7, 6, 5]
    V, F = _tube()
    G = [wind.reverse(f) for f in F]                                          # all inward
    uvc = [[(float(v), 0.5 * float(v)) for v in f] for f in G]
    P, U, flip, _ = wind.orient(V, G, uvc)
    assert flip.all() and all(p[0] == g[0] for p, g in zip(P, G))
    # each corner keeps its UV: the UV of a vertex is where it goes
    for p, u in zip(P, U):
        assert [tuple(c) for c in u] == [(float(v), 0.5 * float(v)) for v in p]
    P2 = wind.orient(V, P)[0]                                                 # already right: untouched
    assert P2 == [tuple(f) for f in P]


def test_closed_regions_each_by_their_volume():
    """two separate closed boxes: each region turned on its own (the flux is its volume)."""
    Vb = np.array([(x, y, z) for x in (0, 1) for y in (0, 1) for z in (0, 1)], float)
    F = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]   # outward
    V = np.vstack([Vb, Vb + 3])
    G = F + [tuple(wind.reverse(f)) for f in (np.array(F) + 8).tolist()]                      # the second inward
    P, _, flip, info = wind.orient(V, G)
    assert info['regions'] == 2 and not flip[:6].any() and flip[6:].all()
    assert np.allclose(info['flux'], [3.0, 3.0])                            # 3 x their unit volumes
    Fa = np.array(F)
    Pa = wind.orient(V[:8], Fa[:, ::-1].copy())[0]
    assert [tuple(f) for f in Pa] == [tuple(wind.reverse(f)) for f in Fa[:, ::-1].tolist()]


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
