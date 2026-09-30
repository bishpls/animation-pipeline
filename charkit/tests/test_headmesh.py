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


def _dome_turned_over(V0, V, F, groups):
    """the dome's quads (over the face's top row) that the fit turned over: their normal against their placed one."""
    n = 0
    for f, g in zip(F, groups):
        if g not in ('skull', 'crown'):
            continue
        a, b = V0[list(f)], V[list(f)]
        n += int(np.cross(a[2] - a[0], a[3] - a[1]) @ np.cross(b[2] - b[0], b[3] - b[1]) < 0)
    return n


def test_the_limit_fit_keeps_the_crown_facing_out():
    """fitting the cage to its limit surface moved freely, the crown's cap folds over on a plain ellipsoid (the fit
    reproduces where along the surface each vertex was placed, and the cap's grid, its corners three-valent, can't: 60
    quads turned in, as on the code head, where hair_penetration read them); along the placed surface's normal only (the
    dome: code_base.SKULL_NORMAL) none do, and the limit surface still passes through the placed points."""
    from charkit import code_base, subdiv
    from charkit.geom import headfit
    S = ellipsoid_sections()
    Cg, ctr = headfit.cylinder_cage(S, {'eye_x': 0.168, 'nose_z': -0.1}, z_top=0.25, z_bottom=-0.55)
    V, F = np.asarray(Cg.V), [list(f) for f in Cg.F]
    groups = [Cg.groups[g] for g in Cg.group]
    movable = np.ones(len(V), bool)
    movable[Cg.loops['neck'][0]] = False
    free, _ = code_base.fit_limit(V, F, movable)
    assert _dome_turned_over(V, free, F, groups) > 20                   # the known-bad fit
    dome = code_base.dome_vertices(len(V), F, groups)
    fitted, gaps = code_base.fit_limit(V, F, movable, normal=dome)
    assert _dome_turned_over(V, fitted, F, groups) == 0
    Vs = np.asarray(subdiv.catmull_clark(fitted, F, [])[0])[:len(V)]
    d = V[dome] - ctr
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    assert np.abs(np.einsum('ij,ij->i', Vs[dome] - V[dome], d)).max() < 0.003      # (the code head: 0.0013)


def test_the_fairness_measure_sees_a_bump_and_not_a_sphere():
    from charkit.geom import headfit
    S = ellipsoid_sections()
    r, ang = headfit.normal_fairness(S)
    assert all(v['rms_deg'] < 0.6 for k, v in r.items() if k != 'jaw_neck'), r      # (the neck's join is a real crease)
    j = np.abs(S.th - np.radians(55)) < 0.12                           # a 0.004 L bump on the cheek at z = -0.1
    k = np.abs(S.zs + 0.1) < 0.02
    S.r[np.ix_(k, j)] += 0.004 * np.outer(np.hanning(k.sum()), np.hanning(j.sum()))
    r2, _ = headfit.normal_fairness(S)
    assert r2['cheeks']['max_deg'] > 3 * r['cheeks']['max_deg'] and r2['forehead']['rms_deg'] < 0.6, (r, r2)


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
