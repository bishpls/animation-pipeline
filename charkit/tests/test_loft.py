"""charkit.geom.loft on shapes with known answers (venv: run this file, or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit.geom import loft


def cone_points(n=20000, seed=0, gap=None):
    """points on a cone round the z axis, pointing down: radius 0.3 at z = 0 growing to 0.6 at z = -1; an elliptic
    section (1.3x wider across x); `gap`: a theta range no view shows (left out)."""
    g = np.random.default_rng(seed)
    t = g.uniform(0, 1, n)
    th = g.uniform(-np.pi, np.pi, n)
    if gap is not None:
        keep = ~((th > gap[0]) & (th < gap[1]))
        t, th = t[keep], th[keep]
    r = (0.3 + 0.3 * t) * np.hypot(1.3 * np.sin(th), np.cos(th))
    return np.c_[r * np.sin(th), -r * np.cos(th), -t], t, th, r


def test_axis_frame_matches_the_heads_convention():
    ax = loft.Axis((0, 0, 0), (0, 0, -1), (0, -1, 0))
    t, th, r = ax.coords(np.array([[1.0, 0, -0.5], [0, -1.0, 0]]))
    assert np.allclose(t, [0.5, 0]) and np.allclose(th, [np.pi / 2, 0]) and np.allclose(r, 1)   # +x is her left
    assert np.allclose(ax.point(0.5, np.pi / 2, 1.0), [1, 0, -0.5])


def test_field_recovers_a_cone_and_fills_a_hidden_side():
    P, t0, th0, r0 = cone_points(gap=(2.0, 2.6))
    ax = loft.Axis((0, 0, 0), (0, 0, -1), (0, -1, 0))
    t, th, r = ax.coords(P)
    F = loft.field(t, th, r, np.linspace(0.02, 0.98, 25), nth=72)
    assert np.percentile(np.abs(r - F.at(t, th)), 90) < 0.01
    tt, hh = np.meshgrid(np.linspace(0.1, 0.9, 5), np.linspace(2.05, 2.55, 5))
    truth = (0.3 + 0.3 * tt) * np.hypot(1.3 * np.sin(hh), np.cos(hh))
    assert np.abs(F.at(tt, hh) - truth).max() < 0.03                      # filled across the gap, not dropped
    assert not F.measured[:, 60:65].any() and F.measured.mean() > 0.85


def test_loft_is_a_closed_quad_grid():
    P, *_ = cone_points()
    ax = loft.Axis((0, 0, 0), (0, 0, -1), (0, -1, 0))
    F = loft.field(*ax.coords(P), np.linspace(0.02, 0.98, 10), nth=32)
    V, quads, uv = loft.loft(ax, F)
    assert V.shape == (320, 3) and len(quads) == 9 * 32 and uv.shape == (320, 2)
    edges = {}
    for q in quads:
        for a, b in zip(q, q[1:] + q[:1]):
            k = (min(a, b), max(a, b))
            edges[k] = edges.get(k, 0) + 1
    border = [k for k, n in edges.items() if n == 1]
    assert len(border) == 2 * 32                                            # open only at the top and bottom rows


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok', name)
