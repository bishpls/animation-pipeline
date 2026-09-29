"""charkit.geom.headmesh: the authored head cage's topology (venv: run this file, or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit.geom import headmesh as hm


def almond(cx, cz, w, h, n=48):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return np.stack([cx + w / 2 * np.cos(t), cz + h / 2 * np.sin(t) * (1 + 0.2 * np.cos(t))], 1)


def a_cage(cap=True):
    ex = 0.168
    X = hm.lines(-0.4, 0.4, 0.045, must=[ex - 0.135, ex + 0.135, -ex - 0.135, -ex + 0.135, -0.09, 0.09, -0.135, 0.135])
    Y = hm.lines(-0.36, 0.5, 0.06, must=[-0.1, 0.2])
    Z = hm.lines(-0.45, 0.56, 0.045, must=[-0.09, 0.09, -0.33, -0.24])
    feats = [dict(name='eye_L', box=(ex - 0.135, ex + 0.135, -0.09, 0.09), outline=almond(ex, 0, 0.21, 0.13), rings=3, cap=cap),
             dict(name='eye_R', box=(-ex - 0.135, -ex + 0.135, -0.09, 0.09), outline=almond(-ex, 0, 0.21, 0.13), rings=3, cap=cap),
             dict(name='mouth', box=(-0.09, 0.09, -0.33, -0.24), outline=almond(0, -0.285, 0.12, 0.012), rings=2, cap=cap)]
    return hm.cage(X, Y, Z, feats, neck=dict(box=(-0.135, 0.135, -0.1, 0.2), rings=[(0.08, 1.0), (0.2, 1.0)], radius=(0.14, 0.14)))


def test_the_cage_is_a_clean_quad_surface_open_at_the_neck():
    C = a_cage()
    h = hm.check(C)
    assert C.F.shape[1] == 4 and h['unused_verts'] == 0
    assert h['nonmanifold_edges'] == 0 and h['misoriented_edges'] == 0, h
    neck = len(C.loops['neck'][-1])
    assert h['boundary_edges'] == neck and h['euler'] == 1 and h['volume'] > 0, h


def test_the_loops_step_in_to_each_outline():
    C = a_cage()
    for name, (cx, cz) in (('eye_L', (0.168, 0.0)), ('eye_R', (-0.168, 0.0)), ('mouth', (0.0, -0.285))):
        rings = C.loops[name]
        assert len({len(r) for r in rings}) == 1                       # matched vertex for vertex
        size = [np.abs(C.V[r][:, [0, 2]] - (cx, cz)).max(0) for r in rings]
        assert all((b <= a + 1e-9).all() for a, b in zip(size, size[1:])), size       # each loop inside the last
    inner = C.V[C.loops['eye_L'][-1]][:, [0, 2]]
    assert abs(np.ptp(inner[:, 0]) - 0.21) < 0.01                      # the innermost is the eye's outline


def test_without_caps_the_features_are_openings():
    h = hm.check(a_cage(cap=False))
    C = a_cage(cap=False)
    holes = sum(len(C.loops[k][-1]) for k in ('eye_L', 'eye_R', 'mouth'))
    assert h['boundary_edges'] == len(C.loops['neck'][-1]) + holes and h['misoriented_edges'] == 0, h


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
