"""charkit.geom.det and the hull's deterministic stages: a local proxy for "the same bits on every machine". Other
machines differ from this one by an ulp here and there (per-CPU SIMD and BLAS, fused multiply-adds on arm64), so each
stage that feeds a discrete decision must give the same discrete output when its inputs move by an ulp, and the
helpers must not depend on memory layout or on the library path numpy takes."""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from charkit.geom import det  # noqa: E402


def _ulp_noise(x, seed=0):
    """x with each element moved one ulp up or down at random."""
    rng = np.random.default_rng(seed)
    x = np.asarray(x, float)
    up = rng.random(x.shape) < 0.5
    return np.where(up, np.nextafter(x, np.inf), np.nextafter(x, -np.inf))


def test_cs_exact_on_the_quadrants_and_stable_off_them():
    for az in (0.0, 90.0, 180.0, 270.0, -90.0):             # numpy's own values, the old hulls' rounding on half bins
        assert det.cs(az) == (float(np.cos(np.radians(az % 360))), float(np.sin(np.radians(az % 360))))
    for az in (35.0, 36.9, 324.0):
        c, s = det.cs(az)
        assert abs(c - math.cos(math.radians(az))) < 1e-12 and abs(s - math.sin(math.radians(az))) < 1e-12
        # an ulp's difference in the angle (a drawing's measured azimuth on another machine) gives the same bits
        assert det.cs(np.nextafter(az, 400.0)) == (c, s) and det.cs(np.nextafter(az, -1.0)) == (c, s)


def test_gaussian_matches_scipy_and_ignores_memory_layout():
    from scipy.ndimage import gaussian_filter
    rng = np.random.default_rng(1)
    x = (rng.random((21, 17, 30)) > 0.5).astype(np.float32)
    for mode in ('reflect', 'nearest'):                          # the edge modes are scipy's, reflect its default
        for sig in (1.0, 1.5, (0.6, 0.6, 2.0), (2.7, 2.7, 9.0)):
            a = det.gaussian(x, sig, mode=mode)
            assert np.abs(a - gaussian_filter(x, sig, mode=mode)).max() < 1e-6
            b = det.gaussian(np.asfortranarray(x), sig, mode=mode)  # another layout: the same elementwise sums
            assert a.tobytes() == np.ascontiguousarray(b).tobytes()
    assert det.gaussian(x, 1.5).tobytes() == det.gaussian(x, 1.5, mode='reflect').tobytes()
    w = det.kernel(1.5)
    assert w.tobytes() == det.kernel(np.nextafter(1.5, 2.0)).tobytes()   # weights snapped: an ulp in sigma is nothing


def test_dot_and_norm_are_termwise():
    rng = np.random.default_rng(2)
    P = rng.normal(size=(1000, 3))
    v = (0.3, -0.7, 0.2)
    ref = P[:, 0] * v[0] + P[:, 1] * v[1] + P[:, 2] * v[2]
    assert det.dot3(P, v).tobytes() == ref.tobytes()
    assert det.dot3(np.asfortranarray(P), v).tobytes() == ref.tobytes()
    assert np.allclose(det.norm3(P), np.linalg.norm(P, axis=1), rtol=1e-15, atol=0)


def test_solve3_matches_lapack():
    from charkit.geom import remesh
    rng = np.random.default_rng(3)
    for _ in range(200):
        M = rng.normal(size=(3, 3)); A = M @ M.T + 0.1 * np.eye(3); r = rng.normal(size=3)
        d, p = remesh._solve3(A[0, 0], A[0, 1], A[0, 2], A[1, 1], A[1, 2], A[2, 2], r[0], r[1], r[2])
        assert abs(d - np.linalg.det(A)) <= 1e-10 * max(1.0, abs(d))
        assert np.allclose(p, np.linalg.solve(A, r), rtol=1e-9, atol=1e-12)


def test_steps_are_arange_without_fusion():
    from charkit.geom.hull import _steps
    for a, b, h in ((-1.23, 1.27, 0.01), (2.5, -3.1, -0.01), (0.3, 0.33, 0.01)):
        s = _steps(a, b, h)
        assert len(s) == len(np.arange(a, b, h)) and np.allclose(s, np.arange(a, b, h), rtol=0, atol=1e-12)
        assert s.tobytes() == (a + np.arange(len(s), dtype=float) * ((a + h) - a)).tobytes()


def test_surface_snap_makes_decimation_independent_of_ulp_noise():
    """marching cubes' positions, an ulp apart (another machine's fused interpolation), snap to the same grid points, so
    the greedy decimation takes the same path: the stage that diverged across machines before (2026-09-29)."""
    from charkit.geom import hull, remesh, volume
    zz, yy, xx = np.mgrid[-1:1:36j, -1:1:36j, -1:1:36j]
    occ = (xx / 0.8) ** 2 + (yy / 0.6) ** 2 + (zz / 0.9) ** 2 + 0.3 * np.sin(3 * xx) * yy <= 1
    G = volume.Grid((-1.0, -1.0, -1.0), 2.0 / 35, occ)
    m = volume.to_mesh(G, blur=1.0)
    a = m.with_(V=det.snap(m.V, hull.VERTEX_Q))
    b = m.with_(V=det.snap(_ulp_noise(m.V), hull.VERTEX_Q))
    assert a.V.tobytes() == b.V.tobytes()
    da, db = remesh.decimate(a, len(m.F) // 4), remesh.decimate(b, len(m.F) // 4)
    assert da.V.tobytes() == db.V.tobytes() and da.F.tobytes() == db.F.tobytes()


def test_facing_view_is_the_first_on_an_exact_tie():
    """a normal exactly between the front (camera on -y) and the profile (camera on +x) faces both equally: the first
    view in order wins, on every machine, since the dot products are the same termwise sums."""
    from charkit.geom import hull
    from charkit.geom.mesh import Mesh

    class _V:
        def __init__(self, az):
            self.az = az

        def band(self, z):
            return np.ones(np.shape(z), bool)
    # one triangle whose normal is (1, -1, 0) / sqrt 2: 45 degrees between the front's and the profile's cameras
    m = Mesh(np.array([[0.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 0.0, 1.0]]), np.array([[0, 1, 2]]))
    assert list(hull._facing(m, {'front': _V(0.0), 'profile': _V(90.0)})) == [0, 0, 0]
    assert list(hull._facing(m, {'profile': _V(90.0), 'front': _V(0.0)})) == [0, 0, 0]
