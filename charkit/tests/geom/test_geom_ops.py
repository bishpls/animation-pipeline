"""charkit.geom: exact booleans with the volume fallback, smoothing, envelope normals, remeshing, decimation and the
rasteriser."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: F401
from charkit.geom import boolean, mesh, primitives as pr, raster, remesh, repair, smooth
from charkit.geom.mesh import Mesh


def _lens(r1, r2, d):
    return np.pi * (r1 + r2 - d) ** 2 * (d ** 2 + 2 * d * (r1 + r2) - 3 * (r1 - r2) ** 2) / (12 * d)


def test_exact_booleans_and_fallback():
    a = pr.icosphere(4); b = pr.icosphere(4, r=0.8, centre=(0.9, 0, 0))
    va, vb, vi = mesh.signed_volume(a.V, a.F), mesh.signed_volume(b.V, b.F), _lens(1.0, 0.8, 0.9)
    for op, want in (('union', va + vb - vi), ('difference', va - vi), ('intersection', vi)):
        m, how = boolean.boolean(a, b, op)
        r = repair.report(m)
        assert how == 'exact' and r['watertight'] and r['shells'] == 1
        assert abs(r['volume'] - want) / want < 0.02, op
    holed, _ = mesh.compact(a, np.arange(a.nf) > 10)            # not manifold: the volume path takes it
    m, how = boolean.boolean(holed, b, 'difference', h=0.03)
    assert how == 'volume' and repair.report(m)['watertight']
    assert not boolean.is_manifold(holed) and boolean.is_manifold(a)


def test_taubin_keeps_volume_and_removes_noise():
    s = pr.icosphere(4)
    rng = np.random.default_rng(0)
    noisy = s.with_(V=s.V + rng.normal(scale=0.02, size=s.V.shape))
    t = smooth.taubin(noisy, iters=20)
    lap = smooth.laplacian(noisy, iters=40)
    rn = lambda m: np.linalg.norm(m.V, axis=1)
    assert rn(t).std() < 0.4 * rn(noisy).std()
    assert abs(mesh.signed_volume(t.V, t.F) - mesh.signed_volume(s.V, s.F)) < 0.04 * mesh.signed_volume(s.V, s.F)
    assert mesh.signed_volume(lap.V, lap.F) < mesh.signed_volume(t.V, t.F)       # plain Laplacian shrinks


def test_bilateral_normal_filter_keeps_edges():
    b = pr.box((1, 1, 1), n=12)
    rng = np.random.default_rng(1)
    noisy = b.with_(V=b.V + rng.normal(scale=0.006, size=b.V.shape))
    f = smooth.bilateral_normals(noisy, iters=5)
    axis_dev = lambda m: 1 - np.abs(mesh.face_normals(m.V, m.F)).max(1)
    assert axis_dev(f).mean() < 0.5 * axis_dev(noisy).mean()


def test_envelope_normals():
    s = pr.icosphere(3)
    N = smooth.envelope_normals(s, h=0.04, close=0.1, blur=0.1)
    assert (np.einsum('ij,ij->i', N, s.V) > 0.97).all()
    # two blobs close together shade as one mass: normals in the gap turn up/down, not toward each other
    two = mesh.concatenate([pr.icosphere(3, r=0.5, centre=(-0.52, 0, 0)), pr.icosphere(3, r=0.5, centre=(0.52, 0, 0))])
    N2 = smooth.envelope_normals(two, h=0.03, close=0.25, blur=0.15)
    gap = np.abs(two.V[:, 0]) < 0.08
    assert np.abs(N2[gap, 0]).mean() < 0.5 * np.abs(mesh.vertex_normals(two.V, two.F)[gap, 0]).mean()


def test_isotropic_remesh_and_decimate():
    s = pr.icosphere(5)
    r = remesh.isotropic(s, 0.08, iters=4)
    el = mesh.edge_lengths(r.V, r.F)
    rep = repair.report(r)
    assert abs(el.mean() - 0.08) < 0.012 and el.std() < 0.2 * el.mean()
    assert rep['watertight'] and rep['self_intersecting_faces_est'] == 0
    assert np.abs(np.linalg.norm(r.V, axis=1) - 1).max() < 0.01
    t = pr.torus(nu=120, nv=48)
    d = remesh.decimate(t, 1500)
    rd = repair.report(d)
    assert rd['faces'] <= 1502 and rd['watertight'] and rd['genus'] == 1 and rd['self_intersecting_faces_est'] == 0


def test_raster_silhouette_and_iou():
    s = pr.icosphere(4)
    fr = raster.Frame(np.zeros(3), 2.5, (250, 250))
    m = raster.silhouette(s, 30, fr)
    px = (250 / 2.5) ** 2
    assert abs(m.sum() / px - np.pi) / np.pi < 0.03
    assert raster.iou(m, raster.silhouette(s, 30, fr)) == 1.0
    img = raster.render([(s, dict(shade='toon'))], 0, fr)
    assert img.shape == (250, 250, 3) and img.min() >= 0 and img.max() <= 1


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
