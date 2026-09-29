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


def ellipsoid_sections(a=0.33, b=0.42, c=0.5, z0=0.1, cy=0.3):
    """an ellipsoid head as headfit.Sections (semi-axes a across, b deep, c tall, centred z0 above the eye line) on a
    cylindrical neck of radius 0.12 under it."""
    from charkit.geom import headfit
    zs = np.arange(z0 + c - 0.002, -0.7, -0.004)
    th = np.linspace(-np.pi, np.pi, headfit.Sections.N, endpoint=False)
    r = np.zeros((len(zs), len(th)))
    for k, z in enumerate(zs):
        s = np.sqrt(max(0.0, 1 - ((z - z0) / c) ** 2))
        ra, rb = max(a * s, 0.12 if z < z0 else 0.0), max(b * s, 0.12 if z < z0 else 0.0)
        r[k] = 1 / np.sqrt((np.sin(th) / ra) ** 2 + (np.cos(th) / rb) ** 2)
    return headfit.Sections(zs, np.full(len(zs), cy), r)


def test_the_cylinder_cage_fits_a_head_without_folds():
    from charkit.geom import headfit
    S = ellipsoid_sections()
    C = {'eye_x': 0.168, 'nose_z': -0.1}
    Cg, ctr = headfit.cylinder_cage(S, C, z_top=0.25, z_bottom=-0.55)
    h = hm.check(Cg)
    assert h['nonmanifold_edges'] == 0 and h['misoriented_edges'] == 0 and h['unused_verts'] == 0, h
    assert h['boundary_edges'] == len(Cg.loops['neck'][0]) and h['euler'] == 1, h
    q = headfit.quality(Cg.V, Cg.F, Cg.origins)
    assert q['flipped'] == 0 and q['folded_corners'] == 0, q
    inner = Cg.V[Cg.loops['eye_L'][-1]]                                # the eye's opening where the front view draws it
    mid = (inner.min(0) + inner.max(0)) / 2
    assert abs(mid[0] - 0.168) < 0.01 and abs(np.ptp(inner[:, 0]) - 0.21) < 0.02, (mid, np.ptp(inner[:, 0]))
    assert abs(mid[2]) < 0.01, mid


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
