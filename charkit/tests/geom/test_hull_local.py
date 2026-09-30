"""The hull's decimation is local (tool/hull-local): an edit to the occupancy in one place leaves the decimated mesh
bit-identical away from it under the quadric-error bound (charkit.geom.hull.decimate_hull), where a fixed face budget
moved vertices anywhere (the face round 5 trace: a jaw change moved the torso's vertices, the body fit and the collar)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: F401
from charkit.geom import det, hull, remesh, repair, volume


def _body(dent):
    """an ellipsoid's occupancy (a stand-in figure, 0.02 voxels) with a dent pressed into its top when dent. (No
    straight walls: an exact cylinder's zero-cost collapses chain along its lines from end to end, which the hull,
    rounded from its views, doesn't have: tool/hull-local measured its torso and legs bit-identical.)"""
    h = 0.02
    x, y, z = np.meshgrid(*(np.arange(-0.6, 0.6 + h / 2, h),) * 2, np.arange(-1.6, 1.6 + h / 2, h), indexing='ij')
    occ = (x / 0.45) ** 2 + (y / 0.35) ** 2 + (z / 1.45) ** 2 < 1.0
    if dent:
        occ &= ((x - 0.1) ** 2 + (y + 0.3) ** 2 + (z - 0.9) ** 2) > 0.12 ** 2       # the 'face': the front of the top
    m = volume.to_mesh(volume.Grid((-0.6, -0.6, -1.6), h, occ), blur=1.0)
    return m.with_(V=det.snap(m.V, hull.VERTEX_Q)), np.array([0.1, -0.3, 0.9])


def _moved_far(a, b, centre, reach):
    """vertices of mesh b not bit-identical in mesh a, farther than reach from the edit's centre -> (far, all)."""
    key = lambda V: np.ascontiguousarray(V, np.float64).view(np.dtype((np.void, 24))).ravel()
    only = ~np.isin(key(b.V), key(a.V))
    return int((only & (np.linalg.norm(b.V - centre, axis=1) > reach)).sum()), int(only.sum())


def test_the_hull_decimation_is_local():
    (s0, c), (s1, _) = _body(False), _body(True)
    info0, info1 = {}, {}
    d0 = remesh.decimate(s0, 0, max_cost=2e-9, info=info0)
    d1 = remesh.decimate(s1, 0, max_cost=2e-9, info=info1)
    assert len(d0.F) < len(s0.F) / 3                            # it decimates
    assert repair.report(d1)['watertight']
    far, moved = _moved_far(d0, d1, c, 0.12 + 0.3)
    assert moved > 0 and far == 0                               # the dent moved its own vertices, nothing far off
    # the same density as a face budget (the old rule) moves vertices across the whole figure (measured: 59 of them
    # beyond 0.42, up to 2.27 from the dent; the bound's farthest 0.26, the surface's own change 0.24)
    b0, b1 = remesh.decimate(s0, info0['faces']), remesh.decimate(s1, info0['faces'])
    assert len(b0.F) == info0['faces'] and _moved_far(b0, b1, c, 0.12 + 0.3)[0] > 10


def test_decimate_hull_rules():
    s, _ = _body(False)
    assert len(hull.decimate_hull(s, 2000).F) == 2000            # an explicit count, for labs
    info = {}
    d = hull.decimate_hull(s, info=info)                         # the default: the error bound
    assert info['last_cost'] <= hull.DECIMATE_COST and len(d.F) == info['faces']
