"""charkit.geom.repair and .mesh topology on meshes with known answers."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: F401
from charkit.geom import mesh, primitives as pr, repair
from charkit.geom.mesh import Mesh


def test_report_closed_open_and_nonmanifold():
    r = repair.report(pr.icosphere(3))
    assert r['watertight'] and r['shells'] == 1 and r['genus'] == 0 and r['self_intersecting_faces_est'] == 0
    assert abs(r['volume'] - 4 / 3 * np.pi) < 0.05
    t = repair.report(pr.torus())
    assert t['watertight'] and t['genus'] == 1
    c = repair.report(pr.cylinder(n=16, capped=False))
    assert c['open_edges'] == 32 and c['boundary_loops'] == 2 and not c['watertight']
    # three triangles on one edge; a bow-tie vertex
    V = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1]], float)
    assert repair.report(Mesh(V, [[0, 1, 2], [1, 0, 3], [0, 1, 4]]))['nonmanifold_edges'] == 1
    V2 = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [-1, 0, 0], [-1, -1, 0]], float)
    assert repair.report(Mesh(V2, [[0, 1, 2], [0, 3, 4]]))['nonmanifold_verts'] == 1


def test_self_intersection_estimate():
    a = pr.icosphere(2); b = pr.icosphere(2, centre=(1.2, 0, 0))
    both = mesh.concatenate([a, b])
    r = repair.report(both)
    assert r['self_intersecting_faces_est'] > 0 and r['shells'] == 2
    assert repair.report(a)['self_intersecting_faces_est'] == 0


def test_merge_close_welds_a_triangle_soup():
    s = pr.icosphere(2)
    soup = Mesh(s.V[s.F].reshape(-1, 3), np.arange(3 * s.nf).reshape(-1, 3))
    assert repair.report(soup, self_intersections=False)['open_edges'] == 3 * s.nf
    w = repair.merge_close(soup, 1e-9)
    assert w.nv == s.nv and repair.report(w, self_intersections=False)['watertight']


def test_clean_drops_opposite_duplicates_and_degenerates():
    s = pr.icosphere(1)
    F = np.vstack([s.F, s.F[:3, ::-1], [[0, 0, 1]]])
    c = repair.clean(Mesh(s.V, F))
    assert c.nf == s.nf - 3                         # the pair cancels, the degenerate goes


def test_orient_consistent_and_outward():
    s = pr.icosphere(2)
    rng = np.random.default_rng(1)
    F = s.F.copy(); flip = rng.random(len(F)) < 0.4
    F[flip] = F[flip][:, ::-1]
    o = repair.orient(Mesh(s.V, F))
    r = repair.report(o, self_intersections=False)
    assert r['consistently_oriented'] and r['volume'] > 0
    inv = repair.orient(Mesh(s.V, s.F[:, ::-1]))
    assert mesh.signed_volume(inv.V, inv.F) > 0
    # an open cap (a hemisphere) turned outward too
    cap, _ = mesh.compact(s, s.V[s.F].mean(1)[:, 2] > 0)
    oc = repair.orient(cap.with_(F=cap.F[:, ::-1].copy()))
    n = mesh.face_normals(oc.V, oc.F)
    assert np.mean(np.einsum('ij,ij->i', n, oc.V[oc.F].mean(1))) > 0


def test_fill_holes_and_small_parts():
    s = pr.icosphere(3)
    holed, _ = mesh.compact(s, np.linalg.norm(s.V[s.F].mean(1) - [0, 0, 1], axis=1) > 0.25)
    assert repair.report(holed, self_intersections=False)['boundary_loops'] == 1
    f = repair.fill_holes(holed, 200)
    r = repair.report(f, self_intersections=False)
    assert r['watertight'] and abs(r['volume'] - mesh.signed_volume(s.V, s.F)) < 0.05
    both = mesh.concatenate([s, pr.icosphere(1, r=0.05, centre=(3, 0, 0))])
    assert repair.report(repair.remove_small_parts(both, keep_largest=1), self_intersections=False)['shells'] == 1
    assert repair.remove_small_parts(both, min_faces=100).nf == s.nf


def test_self_crossing_fixers():
    s = pr.icosphere(3)
    V = s.V.copy()
    i = int(np.argmax(V[:, 2]))
    V[i] = [0, 0, -1.2]                                  # a vertex pushed right through: its fan crosses the far side
    m = Mesh(V, s.F)
    assert repair.self_intersecting(m, np.arange(m.nf)).any()
    fixed, left = repair.fix_self_intersections(m)
    assert left == 0 and repair.report(fixed)['watertight']
    cut, left = repair.cut_intersections(m)
    assert left == 0 and repair.report(cut)['watertight']


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
