"""charkit.geom.lockident and the ribbon options of charkit.geom.lockshell (tool/hairident): the assignment's costs
order a lock's own drawn centreline first; a twist along the lock equals the old one when constant; the tip curl
leaves the root and turns the tip outward; the ribbon's extra parameters are fitted and carried through the shell."""
import math, os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit.geom import hairpieces as hp, lockident as li, lockshell as ls
from charkit.tests.test_lockshell import _known, _world


def test_centre_cost_orders_the_own_lock_first():
    o = dict(li.IDENT)
    t = np.linspace(0, 1, 30)
    own = np.c_[100 + 20 * t, 50 + 80 * t]
    near = own + [12.0, 0.0]
    short = np.c_[100 + 20 * t[:8], 50 + 80 * t[:8]] + [0.0, 120.0]       # heights not shared
    proj = own + [1.0, 0.5]
    c = [li.centre_cost(proj, D, o) for D in (own, near, short)]
    assert c[0] < 2.0 and c[1] > c[0] + 8.0 and not np.isfinite(c[2]), c
    h = [li.height_cost(proj + [30.0, 0.0], D, 40.0, o) for D in (own, own + [0.0, 25.0])]
    assert h[0] < h[1], h                                                   # the heights decide, the side slides


def test_frames_constant_twist_array_matches_scalar():
    views, F, hf, shape = _world()
    P, W, part = _known(F)
    a = ls.frames(P, F['chart'], 0.3)
    b = ls.frames(P, F['chart'], np.full(len(P), 0.3))
    for x, y in zip(a, b):
        assert np.allclose(x, y, atol=1e-12)


def test_tip_curl_keeps_the_root_and_turns_the_tip_out():
    views, F, hf, shape = _world()
    P, W, part = _known(F)
    assert np.allclose(ls.curl_tip(P, F['chart'], 0.0), P)
    Q = ls.curl_tip(P, F['chart'], 1.0, 0.3)
    assert np.allclose(Q[:15], P[:15], atol=1e-12)                         # the first 70% untouched
    r = lambda X: np.linalg.norm(X - F['chart'].c, axis=1)
    assert r(Q)[-1] > r(P)[-1] + 0.01                                       # the tip turned away from the head


def test_ribbon_parameters_fitted_and_kept():
    views, F, hf, shape = _world()
    P, W, part = _known(F)
    o = dict(ls.DEFAULT, bins=12, widen_lw=1.0, twist_axis=True, tip_curl=True, depth_ratio=0.15)
    lk = ls.Lock('t', 'side_locks', 'front', F, views, hf, 1.0, o)
    for n, az in (('front', 0.0), ('profile', 90.0)):
        m = ls.silhouette(part['V'], part['T'], views[n], az, hf, shape)
        c, r = hp.view_px(P[:1], views[n], az, False, hf)
        assert lk.add_view(n, az, m, (r[0], c[0]), 1)
    lk.init()
    lk.fit()
    assert all(c < 2.5 for c in lk.cost.values()), lk.cost
    keep = lk.state()
    lk.slope, lk.curl = 0.0, 0.0
    lk.restore(keep)
    assert (lk.slope, lk.curl) == (keep[3], keep[4])
    got = lk.shell()
    assert 'twist_slope_deg' in got['fit'] and 'curl_deg' in got['fit']
