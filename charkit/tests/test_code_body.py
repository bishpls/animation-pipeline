"""charkit.code_body's pieces with known answers (venv: run this file, or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import code_body as cb, garments as gm


def test_grid_faces_point_out():
    """a part's rings run down with columns round toward her left; its faces must face out (shells lift along the
    normals, the collar's ray finds the surface)."""
    th = -np.pi + (np.arange(24) + 0.5) * 2 * np.pi / 24
    z = np.linspace(0, -1, 6)
    P = np.stack([np.stack([np.sin(th) * 0.3, -np.cos(th) * 0.3, np.full(24, zz)], 1) for zz in z])
    V, F, FUV, UV, row = cb._grid(P, (0, 0, 1, 1), True, True)
    N = gm.vertex_normals(V, F)
    radial = V[:, :2] - V[:, :2].mean(0)
    side = np.linalg.norm(radial, axis=1) > 0.1
    assert (((radial * N[:, :2]).sum(1))[side] > 0).all()
    assert all(len(f) == len(q) for f, q in zip(F, FUV))


def test_blend_weights_sum_to_one_and_ease_at_the_joint():
    x = np.linspace(0, 2, 201)
    W = cb._blend(x, [1.0], 2)
    assert np.allclose(W.sum(1), 1)
    assert W[x < 1 - cb.BLEND, 0].min() == 1 and W[x > 1 + cb.BLEND, 1].min() == 1
    assert abs(W[100, 0] - 0.5) < 1e-9


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok', name)
