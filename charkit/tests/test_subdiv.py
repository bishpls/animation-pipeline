"""charkit.subdiv (Catmull-Clark as Blender's modifier evaluates it) on shapes with known answers (venv: run this file)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import subdiv


def cube():
    V = np.array([(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)], float)
    idx = {tuple(v): i for i, v in enumerate(V.astype(int))}
    F = []
    for ax in range(3):
        for s in (-1, 1):
            corners = []
            for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                p = [0, 0, 0]; p[ax] = s; p[(ax + 1) % 3] = a; p[(ax + 2) % 3] = b
                corners.append(idx[tuple(p)])
            F.append(tuple(corners) if s > 0 else tuple(corners[::-1]))
    return V, F


def test_cube_refinement():
    V, F = cube()
    V1, q, parent = subdiv.catmull_clark(V, F, limit=False)
    assert len(V1) == 8 + 12 + 6 and len(q) == 24 and (np.bincount(parent) == 4).all()
    # the classic values: a corner goes to 5/9, an edge point to 3/4 (0 along the edge), a face point to the face centre
    assert np.allclose(np.abs(V1[:8]), 5 / 9)
    ep = np.sort(np.abs(V1[8:20]), 1)
    assert np.allclose(ep, [[0, 0.75, 0.75]] * 12)
    assert np.allclose(np.sort(np.abs(V1[20:]), 1), [[0, 0, 1]] * 6)


def test_limit_inside_the_hull_and_symmetric():
    V, F = cube()
    V1, q, _ = subdiv.catmull_clark(V, F)
    r = np.linalg.norm(V1, axis=1)
    assert (np.abs(V1) <= 1 + 1e-12).all()
    # every corner alike, every edge point alike, every face point alike (the cube's symmetry)
    for a, b in ((0, 8), (8, 20), (20, 26)):
        assert np.ptp(r[a:b]) < 1e-12


def test_planar_patch_stays_planar_and_creases_hold():
    n = 5
    V = np.array([(x, y, 0.0) for y in range(n) for x in range(n)], float)
    F = [(y * n + x, y * n + x + 1, (y + 1) * n + x + 1, (y + 1) * n + x) for y in range(n - 1) for x in range(n - 1)]
    V1, q, _ = subdiv.catmull_clark(V, F)
    assert np.allclose(V1[:, 2], 0)
    # a sharp edge along a ridge: its crease keeps the ridge's points on the ridge line
    V[:, 2] = -np.abs(V[:, 0] - 2)
    sharp = [(y * n + 2, (y + 1) * n + 2) for y in range(n - 1)]
    S1, _, _ = subdiv.catmull_clark(V, F, sharp)
    ridge = np.isclose(S1[:, 0], 2) & (S1[:, 1] > 0.5) & (S1[:, 1] < n - 1.5)
    assert ridge.any() and np.allclose(S1[ridge, 2], 0)
    S0, _, _ = subdiv.catmull_clark(V, F)
    assert (S0[ridge, 2] < -1e-3).all()                   # smooth: the ridge is rounded off


def test_child_quads_keep_the_parent_origin():
    """Blender (OpenSubdiv) starts child j of a quad j corners on: the first corner of each child sits at the parent's
    parametric origin side, which fixes the diagonal a fan triangulation takes."""
    V = np.array([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], float)
    V1, q, _ = subdiv.catmull_clark(V, [(0, 1, 2, 3)], limit=False)
    face_pt = 4 + 4
    starts = [int(q[j][0]) for j in range(4)]
    assert starts[0] == 0 and starts[2] == face_pt              # child 0 at the corner, child 2 at the face point
    assert all(len(set(map(int, c))) == 4 for c in q)


def test_region():
    V, F = cube()
    keep = V[:, 2] > 0
    Vr, fr, fi, used = subdiv.region(V, F, keep)
    assert len(fr) == 1 and len(Vr) == 4 and (V[used, 2] > 0).all()


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
