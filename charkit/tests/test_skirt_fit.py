"""charkit.garments' skirt fitting on synthetic points with known answers: the waist ring's axis (ring_axis), the
hem's cut sectors (hem_cut) and the mirror (mirror_sectors) (venv: run this file, or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import garments as gm
from charkit.geom import loft

L = 1.0


def _assembly(hips_x=0.0):
    """the least of an assembly ring_axis reads: the hips bone's joints (bone_seg) and the head's L."""
    from charkit import mh
    h, t = mh.VRM_JOINTS['hips']
    return {'head': {'L': L}, 'joints': {h: (hips_x, 0.0, 0.0), t: (hips_x, 0.0, 1.0)}}


def test_ellipse_axis_ignores_where_the_ring_crowds():
    # a waist ring (an ellipse 0.8 x 0.6 round (0.02, -0.05)) with its front hidden (no points in -40..40 deg) and its
    # left back crowded (5x the points): the median is pulled off, the ellipse fit isn't
    rng = np.random.default_rng(3)
    th = rng.uniform(-np.pi, np.pi, 4000)
    th = th[np.abs(th) > np.radians(40)]
    th = np.r_[th, rng.uniform(np.radians(100), np.radians(170), 6000)]
    c = np.array([0.02, -0.05])
    P = np.c_[c[0] + 0.8 * np.sin(th), c[1] - 0.6 * np.cos(th), np.zeros_like(th)]
    A = _assembly()
    med = gm.ring_axis(A, P, 0.0, 'median').o
    ell = gm.ring_axis(A, P, 0.0, 'ellipse').o
    assert np.hypot(*(med[:2] - c)) > 0.1, med
    assert np.hypot(*(ell[:2] - c)) < 1e-6, ell


def test_midline_axis_takes_the_hips_x():
    th = np.linspace(-np.pi, np.pi, 400, endpoint=False)
    P = np.c_[0.03 + 0.8 * np.sin(th), -0.05 - 0.6 * np.cos(th), np.zeros_like(th)]
    o = gm.ring_axis(_assembly(hips_x=0.0), P, 0.0, 'midline').o
    assert abs(o[0]) < 1e-12 and abs(o[1] + 0.05) < 1e-6, o


def test_mirror_sectors():
    x = np.array([1.0, 2.0, np.nan, 4.0, np.nan, np.nan])
    m = gm.mirror_sectors(x)
    assert np.allclose(m, m[::-1], equal_nan=True)
    assert m[0] == 1.0 and m[5] == 1.0 and m[1] == 2.0 and m[2] == 4.0 and np.isnan(gm.mirror_sectors([np.nan, np.nan])).all()


def _cone(n_th=720, t1=1.0, cut=()):
    """a cone skirt's surface points (r = 0.5 + 0.4 t) down to t1, and another piece's continuing its surface below
    t1 to t1 + 0.3 in the sectors `cut` (degree ranges) -> (skirt points, others), in the axis' frame (t down)."""
    ax = loft.Axis((0, 0, 0), (0, 0, -1), (0, -1, 0))
    th = np.radians(np.linspace(-180, 180, n_th, endpoint=False) + 0.25)
    T, TH = np.meshgrid(np.linspace(0, t1, 60), th)
    S = ax.point(T.ravel(), TH.ravel(), 0.5 + 0.4 * T.ravel())
    O = []
    for a, b in cut:
        m = (np.degrees(th) >= a) & (np.degrees(th) < b)
        T2, TH2 = np.meshgrid(np.linspace(t1 + 0.01, t1 + 0.3, 20), th[m])
        O.append(ax.point(T2.ravel(), TH2.ravel(), 0.5 + 0.4 * T2.ravel()))
    return ax, S, np.concatenate(O)


def test_hem_cut_where_the_surface_carries_on():
    # the back half's label stops at t 1 but another piece carries its surface on (a flap, the dark band labelled
    # apart); the front's t 1 is a true edge; one 2.5 deg sector inside the cut stretch has nothing below it
    ax, S, O = _cone(cut=((-180, -95), (-92.5, 0), (90, 180)))
    t, th, r = ax.coords(S)
    n = 144
    j = np.clip(((th + np.pi) / (2 * np.pi) * n).astype(int), 0, n - 1)
    hem = np.array([np.percentile(t[j == k], 97) for k in range(n)])
    cut = gm.hem_cut(ax, t, th, r, hem, O, L)
    deg = -180 + (np.arange(n) + 0.5) * 2.5
    assert cut[(deg > -180) & (deg < -95)].all() and cut[(deg > 90) & (deg < 180)].all()
    assert not cut[(deg > 2) & (deg < 88)].any()
    assert cut[(deg > -95) & (deg < -92.5)].all()          # the lone sector the test kept, taken with its stretch
    keep = gm.hem_cut(ax, t, th, r, hem, O, L, min_arc=0)
    assert not keep[(deg > -95) & (deg < -92.5)].any()


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
