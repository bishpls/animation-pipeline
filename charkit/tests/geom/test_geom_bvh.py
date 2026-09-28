"""charkit.geom.bvh against brute force and analytic answers."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: F401
from charkit.geom import bvh, mesh, primitives as pr


def _brute_nearest(m, P):
    from charkit.geom.bvh import _closest_on_tri
    best = np.full(len(P), np.inf)
    for t in range(m.nf):
        a, b, c = m.V[m.F[t]]
        for i, p in enumerate(P):
            q = _closest_on_tri(*p, *a, *b, *c)[:3]
            d = np.linalg.norm(np.array(q) - p)
            if d < best[i]:
                best[i] = d
    return best


def test_nearest_matches_brute_force():
    t = pr.torus(nu=16, nv=8)
    P = np.random.default_rng(0).uniform(-1.6, 1.6, (60, 3))
    d, f, q = bvh.BVH(t).nearest(P)
    assert np.abs(d - _brute_nearest(t, P)).max() < 1e-12
    assert np.abs(np.linalg.norm(q - P, axis=1) - d).max() < 1e-12


def test_winding_signed_distance_and_rays():
    s = pr.icosphere(4)
    B = bvh.BVH(s)
    P = np.random.default_rng(1).normal(size=(20000, 3)) * 0.8
    sd_n = B.signed_distance(P, sign='normal')
    sd_w = B.signed_distance(P, sign='winding')
    assert np.array_equal(np.sign(sd_n), np.sign(sd_w))
    ins = sd_n < 0
    assert np.array_equal(B.contains(P), ins)
    # rays from outside toward the centre hit the sphere at distance ~ 2
    D = -P / np.linalg.norm(P, axis=1, keepdims=True)
    t, f = B.ray_cast(-3 * D, D)
    assert np.abs(t - 2).max() < 0.01 and (f >= 0).all()
    # one crossing from the inside, two through the whole thing, hits listed
    assert (B.ray_count(np.zeros((10, 3)), D[:10]) == 1).all()
    off, T = B.ray_hits(-3 * D[:10], D[:10])
    assert (np.diff(off) == 2).all() and len(T) == 20


def test_winding_number_is_robust_to_a_hole():
    s = pr.icosphere(3)
    holed, _ = mesh.compact(s, np.linalg.norm(s.V[s.F].mean(1) - [0, 0, 1], axis=1) > 0.4)
    w = bvh.BVH(holed).winding_number(np.array([[0, 0, 0], [0.3, 0.2, -0.4], [0, 0, 1.5], [2, 0, 0]]))
    assert w[0] > 0.8 and w[1] > 0.8 and w[2] < 0.2 and abs(w[3]) < 0.05


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
