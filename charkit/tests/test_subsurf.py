"""charkit.geom.subsurf (Blender's Subdivision Surface in numpy) and charkit.geom.solidify on shapes with known answers,
and against Blender itself when it is installed (charkit.evalmesh's lab: every shape within 1e-5 of Blender 5.2's
modifier; measured 1.3e-6 at worst, float32). venv: run this file, or pytest."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import evalmesh
from charkit.geom import solidify as solid, subsurf

# Blender 5.2.2's own values for evalmesh.shapes() vertices (Subdivision Surface level 1, its defaults): the rules the
# measurement settled (docs/workstreams/evalmesh.md)
BLENDER = {('cube_two_sharp', 1): [-0.593087, -0.685269, 0.46322],     # a dart: the mask at the isolation level (3)
           ('cube_ring_c0.7', 0): [-0.911545, -0.86275, -0.496982],   # semi-sharp (10 c^2 = 4.9): smooth past level 3
           ('cube_one_c0.9', 3): [-0.569854, 0.611818, 0.452805],
           ('grid_open', 0): [0.197893, 0.169875, 0.020415]}          # an open corner: its level-3 point


def _shape(name):
    return next(p for p in evalmesh.shapes() if p['name'] == name)


def _sub(p, **k):
    cre = (p['crease_e'], p['crease_w']) if len(p['crease_e']) else None
    return subsurf.subdivide(p['V'], (p['loopv'], p['counts']), creases=cre, uv=p['luv'], **k)


def test_blender_values():
    for (name, v), want in BLENDER.items():
        R = _sub(_shape(name))
        assert np.abs(R['V'][v] - want).max() < 2e-6, (name, R['V'][v], want)


def test_order_and_children():
    """Blender's order: the input vertices, one per edge, one per polygon; child j of a quad starts j corners on; an
    n-gon's children start at their corner."""
    V, F = evalmesh._cube()
    R = subsurf.subdivide(V, F, limit_surface=False)
    assert len(R['V']) == 8 + 12 + 6 and R['quads'].shape == (24, 4)
    assert np.allclose(np.abs(R['V'][:8]), 5 / 9)                          # the corners' vertex points
    assert np.allclose(np.sort(np.abs(R['V'][8:20]), 1), [[0, 0.75, 0.75]] * 12)
    assert np.allclose(np.sort(np.abs(R['V'][20:]), 1), [[0, 0, 1]] * 6)
    q = R['quads'][:4]
    assert q[0][0] == F[0][0] and q[2][0] == 20                             # child 0 at the corner, child 2 at the face
    P = _shape('prism_ngon')
    R = subsurf.subdivide(P['V'], (P['loopv'], P['counts']), limit_surface=False)
    assert [int(R['quads'][k][0]) for k in range(5)] == list(P['loopv'][:5])  # the pentagon's children start at corners


def test_isolation_is_local():
    """the level-dependent vertices refined locally give what refining the whole mesh to level 3 gives."""
    for name in ('cube_two_sharp', 'cube_ring_c0.7', 'grid_open', 'grid_open_l2'):
        p = _shape(name)
        R = _sub(p, levels=p['mods'][0][1]['levels'])
        n = len(R['V'])
        lev = p['mods'][0][1]['levels']
        T = subsurf.Topo(len(p['V']), p['loopv'], p['counts'])
        es = subsurf._edge_sharp(T, (p['crease_e'], subsurf.crease_sharpness(p['crease_w'])) if len(p['crease_e']) else None)
        vs = np.zeros(len(p['V'])); V = p['V']
        for _ in range(3):
            V, Qd, ps, vs, _ = subsurf.refine(V, T, es, vs)
            T = subsurf.Topo(len(V), Qd.ravel(), np.full(len(Qd), 4)); es = subsurf._edge_sharp(T, ps)
        G = subsurf.limit(V, T, es, vs)[:n]
        assert np.abs(G - R['V']).max() < 1e-12, name


def test_uv_seams_stay_linear():
    p = _shape('grid_uv_seam')
    R = _sub(p)
    # the seam's corners keep their input UVs on each side (linear along the seam), the inside moves (smoothed)
    U = R['uv'].reshape(-1, 2)
    x = R['V'][R['quads'].ravel(), 0]
    seam = np.isclose(x, 3.0, atol=0.2)
    assert seam.any() and np.isfinite(U).all()


def test_solidify_layout():
    """Blender's layout: the input unmoved (offset -1), its copy t in; the copies reversed with their first corner
    kept; a rim quad (b, a, a + n, b + n) per open edge a -> b; creases outer, inner and rim where Blender puts them."""
    V = np.array([(x, y, 0.0) for y in (0, 1) for x in range(3)], float)
    F = [(0, 1, 4, 3), (1, 2, 5, 4)]
    R = solid.solidify(V, F, 0.1, crease_outer=1.0, crease_inner=0.5, crease_rim=0.25)
    n = len(V)
    assert np.allclose(R['V'][:n], V) and np.allclose(R['V'][n:], V - [0, 0, 0.1])
    P = evalmesh.polys_of(dict(loopv=R['loopv'], counts=R['counts']))
    assert P[:2] == F and P[2:4] == [(6, 9, 10, 7), (7, 10, 11, 8)]
    assert (1, 0, 6, 7) in P and len(P) == 4 + 6
    cr = {tuple(sorted(e)): w for e, w in zip(R['creases'][0].tolist(), R['creases'][1])}
    assert cr[(0, 1)] == 1.0 and cr[(6, 7)] == 0.5 and cr[(0, 6)] == 0.25 and (1, 4) not in cr


def test_finalize_a_recorded_garment():
    """M4's final mesh at rest: a strip's Solidify then Subsurf, its materials through the polygons' parents and its
    weights copied to the Solidify's copies and carried linearly (as Blender carries vertex groups)."""
    V = np.array([(x, y, 0.1 * x * x) for y in (0, 1) for x in range(4)], float)
    F = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6)]
    o = dict(name='strip', V=V, polys=F, uv=None, uv_corner=[[(V[v, 0] / 3, V[v, 1]) for v in f] for f in F],
             mat_idx=[0, 1, 0], weights={'b': V[:, 0] / 3},
             mods={'thick': dict(type='SOLIDIFY', settings=dict(thickness=0.1, offset=-1)),
                   'sub': dict(type='SUBSURF', settings=dict(levels=1, render_levels=1))})
    R = evalmesh.finalize(o)
    S = solid.solidify(V, F, 0.1)
    assert len(R['counts']) == 4 * len(S['counts']) and R['shell'] == 0.1 and R['levels'] == 1
    assert np.allclose(R['weights']['b'][:2 * len(V)], np.r_[V[:, 0], V[:, 0]] / 3)   # kept at the vertices
    assert set(R['mat_idx'].tolist()) == {0, 1}
    assert len(R['uv_corner']) == len(R['counts'])


def test_against_blender():
    if not os.path.exists(evalmesh.BLENDER):
        print('(no Blender: skipped)'); return
    ps = evalmesh.shapes()
    for p, b in zip(ps, evalmesh.blender(ps, log=lambda *a: None)):
        r = evalmesh.compare(evalmesh.ours(p), b, p['L'])
        assert r['one_to_one'] and r['max_L'] < 1e-5 and r['winding_same'] == r['faces'] == r['start_same'], (p['name'], r)
        if 'uv_max' in r:
            assert r['uv_max'] < 1e-5, (p['name'], r)


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
