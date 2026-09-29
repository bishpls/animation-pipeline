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


def _cone_hull(seed=1):
    """a skirt-like hull: a cone from z 0 (radius 0.3) down to z -1 (radius 0.6), the back 0.2 longer; a band above it
    (z 0 .. 0.15, radius 0.28); a panel on her left side (theta 1.2 .. 2.0) hanging outside the skirt to z -1.3."""
    g = np.random.default_rng(seed)
    th = g.uniform(-np.pi, np.pi, 30000)
    back = (1 - np.cos(th)) / 2
    hem = 1.0 + 0.2 * back
    t = g.uniform(0, 1, len(th)) * hem
    r = 0.3 + 0.3 * t
    skirt = np.c_[r * np.sin(th), -r * np.cos(th), -t]
    thb = g.uniform(-np.pi, np.pi, 4000); zb = g.uniform(0, 0.15, 4000)
    band = np.c_[0.28 * np.sin(thb), -0.28 * np.cos(thb), zb]
    thp = g.uniform(1.2, 2.0, 5000); tp = g.uniform(0.2, 1.3, 5000); rp = 0.36 + 0.3 * tp
    panel = np.c_[rp * np.sin(thp), -rp * np.cos(thp), -tp]
    return {'skirt': skirt, 'waistband': band, 'overskirt_panel_L': panel}


def test_garments_lofted_from_the_hull_follow_its_points():
    from charkit import garments as gm
    H = _cone_hull()
    A = {'head': {'L': 1.0}, 'verts': np.zeros((1, 3)), 'weights': {'hips': np.ones(1)}}
    S = gm.skirt_hull(A, {'name': 'skirt', 'pleat': 0.0, 'under': 'waistband', 'tuck': 0.0}, H)
    V = S['verts']
    th = np.arctan2(V[:, 0], -V[:, 1]); r = np.hypot(V[:, 0], V[:, 1])
    assert np.percentile(np.abs(r - (0.3 + 0.3 * -V[:, 2])), 90) < 0.03                 # on the cone
    lo_front, lo_back = V[np.abs(th) < 0.3, 2].min(), V[np.abs(th) > np.pi - 0.3, 2].min()
    assert -1.05 < lo_front < -0.9 and -1.25 < lo_back < -1.1, (lo_front, lo_back)       # the back hangs longer
    B = gm.belt_hull(A, {'name': 'waistband'}, H)
    assert abs(np.hypot(B['verts'][:, 0], B['verts'][:, 1]).mean() - 0.28) < 0.02
    P = gm.panel_hull(A, {'name': 'overskirt_panel_L'}, H)
    thp = np.arctan2(P['verts'][:, 0], -P['verts'][:, 1])
    assert 1.1 < thp.min() and thp.max() < 2.1 and P['verts'][:, 2].min() < -1.2        # its own span and length


def test_gauss1d_is_scipys():
    from scipy.ndimage import gaussian_filter1d
    a = np.random.default_rng(0).normal(size=(7, 40))
    for mode in ('nearest', 'wrap'):
        for axis, sig in ((1, 1.5), (0, 1.0)):
            assert np.allclose(loft.gauss1d(a, sig, axis=axis, mode=mode), gaussian_filter1d(a, sig, axis=axis, mode=mode))


def test_the_hull_builders_run_without_scipy():
    """Blender's Python has no scipy: the garment builders (they run in the build) mustn't need it."""
    import subprocess, textwrap
    code = textwrap.dedent('''
        import sys, builtins
        real = builtins.__import__
        def guard(name, *a, **k):
            if name == 'scipy' or name.startswith('scipy.'):
                raise ImportError('no scipy here (as in Blender)')
            return real(name, *a, **k)
        builtins.__import__ = guard
        sys.path.insert(0, %r)
        import numpy as np
        from charkit.tests.test_loft import _cone_hull
        from charkit import garments as gm
        H = _cone_hull()
        A = {'head': {'L': 1.0}, 'verts': np.zeros((1, 3)), 'weights': {'hips': np.ones(1)}}
        gm.skirt_hull(A, {'name': 'skirt', 'under': 'waistband'}, H)
        gm.belt_hull(A, {'name': 'waistband'}, H)
        gm.panel_hull(A, {'name': 'overskirt_panel_L'}, H)
        print('ok')
    ''') % os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
    assert r.returncode == 0 and 'ok' in r.stdout, r.stderr[-1500:]



def test_field_degrades_on_marginal_coverage():
    """a piece measured on less than min_row of its circle in every row (a hull's labels wobbling at a boundary) lofts
    from its best rows with a warning and its coverage kept, instead of failing the build."""
    import warnings
    rng = np.random.default_rng(0)
    th = rng.uniform(-0.3, 0.3, 400)                       # a 10% arc
    t = rng.uniform(0, 1, 400)
    r = np.full(400, 0.1)
    del loft.LOW_COVERAGE[:]
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        F = loft.field(t, th, r, np.linspace(0, 1, 8), nth=48, min_row=0.15)
    assert np.isfinite(F.R).all() and abs(F.R.mean() - 0.1) < 0.02
    assert loft.LOW_COVERAGE and loft.LOW_COVERAGE[0] < 0.15 and F.coverage < 0.15
    assert any('stand in' in str(x.message) for x in w)


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok', name)
