"""charkit.geom.volume: occupancy, SDF, marching cubes, grid booleans and morphology against analytic shapes."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: F401
from charkit.geom import mesh, primitives as pr, repair, volume
from charkit.geom.mesh import Mesh

SPHERE = 4 / 3 * np.pi


def test_occupancy_fast_equals_full_and_parity():
    s = pr.icosphere(4)
    G = volume.grid_for(s, 0.05)
    fast = volume.occupancy(s, grid=G)
    full = volume.occupancy(s, grid=G, fast=False)
    par = volume.occupancy(s, grid=G, method='parity')
    assert np.array_equal(fast.data, full.data)
    assert (fast.data != par.data).sum() <= 1e-3 * fast.data.size     # voxel centres a hair off the surface may differ
    assert abs(fast.voxel_volume() - SPHERE) / SPHERE < 0.03


def test_sdf_and_marching_cubes_round_trip():
    s = pr.icosphere(4)
    S = volume.sdf(s, h=0.04)
    P = S.points()
    near = np.abs(S.data.ravel()) < 0.1
    assert np.abs(S.data.ravel()[near] - (np.linalg.norm(P[near], axis=1) - 1)).max() < 0.01
    m = volume.to_mesh(S)
    r = repair.report(m)
    assert r['watertight'] and r['shells'] == 1 and r['nonmanifold_verts'] == 0 and r['self_intersecting_faces_est'] == 0
    assert abs(r['volume'] - SPHERE) / SPHERE < 0.02 and r['volume'] > 0


def _lens(r1, r2, d):
    """the volume of the intersection of two spheres."""
    return np.pi * (r1 + r2 - d) ** 2 * (d ** 2 + 2 * d * (r1 + r2) - 3 * (r1 - r2) ** 2) / (12 * d)


def test_grid_booleans():
    a = pr.icosphere(4); b = pr.icosphere(4, r=0.8, centre=(0.9, 0, 0))
    G = volume.lattice([-1.1, -1.1, -1.1], [1.8, 1.1, 1.1], 0.03)
    A, B = volume.sdf(a, grid=G), volume.sdf(b, grid=G)
    va, vb, vi = SPHERE, 4 / 3 * np.pi * 0.8 ** 3, _lens(1.0, 0.8, 0.9)
    for fn, want in ((volume.union, va + vb - vi), (volume.intersection, vi), (volume.difference, va - vi)):
        v = mesh.signed_volume(*(lambda m: (m.V, m.F))(volume.to_mesh(fn(A, B))))
        assert abs(v - want) / want < 0.03, fn.__name__
    # grids of different extent but the same voxel size line up exactly
    Ga = volume.sdf(a, h=0.05); Gb = volume.sdf(b, h=0.05)
    U = volume.union(Ga, Gb)
    assert abs(volume.to_mesh(U).V.max(0)[0] - 1.7) < 0.03


def test_offsets_and_morphology():
    s = pr.icosphere(4)
    S = volume.sdf(s, h=0.03, band=6)
    for f, r in ((volume.dilate, 1.1), (volume.erode, 0.9)):
        m = volume.to_mesh(f(S, 0.1))
        assert abs(np.linalg.norm(m.V, axis=1).mean() - r) < 0.01
    # opening drops a thin fin, closing bridges a narrow gap
    fin = volume.union(volume.sdf(pr.box((1, 1, 1)), h=0.02), volume.sdf(pr.box((0.03, 1, 0.8), centre=(0.7, 0, 0)), h=0.02))
    op = volume.opening(fin, 0.04)
    assert volume.to_mesh(op).V[:, 0].max() < 0.56
    two = volume.union(volume.sdf(pr.box((1, 1, 1), centre=(-0.53, 0, 0)), h=0.02),
                       volume.sdf(pr.box((1, 1, 1), centre=(0.53, 0, 0)), h=0.02))
    assert volume.component_count(two) == 2 and volume.component_count(volume.closing(two, 0.05)) == 1


def test_solid_of_a_hollow_shell_and_cavities():
    """a TRELLIS-style thin double wall (outer sphere, inner inverted sphere 1 % smaller): the winding number sees only the
    wall; solid() and fill_cavities see the whole ball."""
    outer = pr.icosphere(4); inner = pr.icosphere(4, r=0.99)
    shell = mesh.concatenate([outer, inner.with_(F=inner.F[:, ::-1].copy())])
    G = volume.grid_for(shell, 0.04)
    wall = volume.occupancy(shell, grid=G)
    assert wall.voxel_volume() < 0.2 * SPHERE
    sol = volume.solid(shell, grid=G)
    assert abs(sol.voxel_volume() - SPHERE) / SPHERE < 0.05
    assert abs(volume.fill_cavities(volume.solid(shell, grid=G)).voxel_volume() - sol.voxel_volume()) < 1e-9
    # a small hole in the double wall: sealed by `seal`
    keep = np.linalg.norm(shell.V[shell.F].mean(1) - [0, 0, 1], axis=1) > 0.08
    holed, _ = mesh.compact(shell, keep)
    leak = volume.solid(holed, grid=G)
    sealed = volume.solid(holed, grid=G, seal=0.12)
    assert leak.voxel_volume() < 0.3 * SPHERE and abs(sealed.voxel_volume() - SPHERE) / SPHERE < 0.08


def test_weld_bridges_close_pieces_only():
    a = volume.sdf(pr.box((1, 1, 1), centre=(-0.53, 0, 0)), h=0.02)
    b = volume.sdf(pr.box((1, 1, 1), centre=(0.53, 0, 0)), h=0.02)
    far = volume.sdf(pr.box((0.5, 0.5, 0.5), centre=(2.0, 0, 0)), h=0.02)
    two = volume.union(volume.union(a, b), far)
    w, apart = volume.weld(two, 0.05)
    assert volume.component_count(w) == 2 and apart == 1          # the near pair joined, the far box left alone
    assert repair.report(volume.to_mesh(w), self_intersections=False)['shells'] == 2


def test_thicken_sheet_and_components():
    sheet = pr.grid(10, 1.0)
    S = volume.thicken(sheet, 0.05, h=0.02)
    m = volume.to_mesh(S)
    r = repair.report(m)
    assert r['watertight'] and r['shells'] == 1
    want = 1.0 * 0.1 + 4.0 * np.pi * 0.05 ** 2 / 2              # area x 2r, plus the half-round rim
    assert abs(r['volume'] - want) / want < 0.03
    two = volume.union(volume.sdf(pr.icosphere(3), h=0.05), volume.sdf(pr.icosphere(3, r=0.3, centre=(2, 0, 0)), h=0.05))
    k = volume.keep_components(two, largest=1)
    assert volume.component_count(k) == 1


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
