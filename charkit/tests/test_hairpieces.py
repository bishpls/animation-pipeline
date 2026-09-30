"""charkit.geom.hairpieces on shapes with known answers (venv: run this file, or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit.geom import hairpieces as hp

STYLE = dict(notch=6.0, thick=0.2, tip_thick=0.01, inset=0.01, lock_min=8.0, normals='envelope')


def _edges(T):
    E = np.sort(np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]]), 1)
    _, n = np.unique(E, axis=0, return_counts=True)
    return n


def sphere_fields(r=1.0, skin=None, tilt=0.0):
    """a crown chart over a sphere of radius r round the origin (the envelope, and its smoother copy), the skin a
    smaller sphere (or none)."""
    ch = hp.Chart(np.zeros(3), tilt)
    G = hp.Grid(4.0, 3.0, 168.0)
    R = np.full((G.nph, G.nth), r)
    S = np.full((G.nph, G.nth), -np.inf if skin is None else skin)
    return dict(chart=ch, grid=G, R=R, Rn=R.copy(), S=S)


def test_chart_round_trip_and_front():
    ch = hp.Chart(np.array([0.1, 0.2, 0.3]), 12.0)
    ph = np.array([-150.0, -20.0, 0.0, 45.0, 170.0]); th = np.array([10.0, 50.0, 80.0, 120.0, 160.0])
    P = ch.point(ph, th, np.array([1.0, 2.0, 0.5, 1.5, 0.8]))
    a, b, r = ch.coords(P)
    assert np.allclose(a, ph) and np.allclose(b, th) and np.allclose(r, [1.0, 2.0, 0.5, 1.5, 0.8])
    d = ch.dirs(np.array([0.0]), np.array([90.0]))[0]
    assert d[1] < -0.9                                               # phi 0 on the equator faces the front (-y)
    assert ch.dirs(np.array([90.0]), np.array([90.0]))[0][0] > 0.9   # phi 90 toward her left (+x)


def test_locks_split_at_notches_and_deepen_them():
    ph = np.arange(0, 60, 2.0)
    tip = 100 + 10 * np.abs(((ph / 20.0) % 1) - 0.5) * -2 + 10        # three tips, notches at 0, 20, 40 (sawtooth)
    L_, edge = hp.locks(ph, tip, lock_min=8.0, notch=6.0)
    assert len(L_) == 3, L_
    assert all(a < t < b for a, b, t in L_)
    assert (edge <= tip + 1e-9).all() and edge.min() < tip.min() - 3   # the notches deepened, the tips kept


def test_a_lock_is_a_closed_outward_fold_free_shell_clear_of_the_skin():
    F = sphere_fields(1.0, skin=0.8)
    ph = np.arange(-30, 31, 4.0)
    top = np.zeros(len(ph)); edge = 80 + 10 * np.cos(np.radians(ph * 6))
    opts = dict(hp.OPTS)
    S = hp.lock_shell(F, 'bangs', -30.0, 30.0, 0.0, ph, top, edge, STYLE, opts, L=1.0)
    V, T = S['V'], S['T']
    n = _edges(T)
    assert (n == 2).all(), np.bincount(n)                            # closed: every edge shared by two faces
    assert hp.folds(V, T, S['outer'], S['vn_env']) == 0
    ph_, th_, r_ = F['chart'].coords(V[S['outer']])
    assert np.allclose(r_, 1.0 - hp.LAYER['bangs'] * STYLE['inset'], atol=1e-6)   # the envelope less its layer's inset
    _, _, ri = F['chart'].coords(V[~S['outer']])
    assert ri.min() >= 0.8 + opts['gap'] - 1e-9                      # the inner one clears the skin by `gap`
    fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    out = np.all(S['outer'][T], axis=1)
    assert (np.einsum('ij,ij->i', fn[out], V[T[out]].mean(1)) > 0).all()   # outer faces point out
    assert len(S['chain']) >= 3 and np.linalg.norm(S['chain'][-1]) < 1.0    # a chain inside the lock, root to tip


def test_a_lock_is_pushed_out_over_skin_that_bulges_past_the_envelope():
    F = sphere_fields(1.0, skin=1.05)
    ph = np.arange(-20, 21, 4.0)
    S = hp.lock_shell(F, 'bangs', -20.0, 20.0, 0.0, ph, np.zeros(len(ph)), np.full(len(ph), 60.0), STYLE,
                      dict(hp.OPTS), L=1.0)
    _, _, ri = F['chart'].coords(S['V'][~S['outer']])
    assert ri.min() >= 1.05 + hp.OPTS['gap'] - 1e-9 and S['push'] > 0.05


def test_a_blade_is_closed_and_points_out():
    t = np.linspace(0, 1, 8)
    line = np.c_[0.3 * np.sin(2 * t), np.zeros(8), t]                 # a gentle curl
    B = hp.blade(line, np.linspace(0.1, 0.02, 8))
    n = _edges(B['T'])
    assert (n == 2).all()
    V, T = B['V'], B['T']
    fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    side = T[:len(T) - 16]
    cen = np.repeat(line[:-1], 16, 0)
    assert (np.einsum('ij,ij->i', fn[:len(side)], V[side].mean(1) - cen) > 0).mean() > 0.95


def test_a_block_bun_is_two_closed_outward_rounded_boxes():
    P = np.random.default_rng(0).uniform(-1, 1, (400, 3)) * [0.1, 0.08, 0.09] + [0.3, 0.0, 0.5]
    B = hp.bun_block(P, np.zeros(3), dict(bun_e=0.3, bun_q=0.02, bun_slab=0.38))
    V, T = B['V'], B['T']
    assert (_edges(T) == 2).all()                                       # closed
    fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    half = len(T) // 2                                                  # (each box's faces point out of its own centre)
    for part, c in ((slice(0, half), V[:len(V) // 2].mean(0)), (slice(half, None), V[len(V) // 2:].mean(0))):
        assert (np.einsum('ij,ij->i', fn[part], V[T[part]].mean(1) - c) > 0).mean() > 0.99
    assert B['own_normals']
    # flat faces: most of a box's vertices lie within 5% of its bounding box's faces (an ellipsoid's don't)
    for e, want in ((0.3, lambda f: f > 0.5), (1.0, lambda f: f < 0.3)):
        Vs, _ = hp.superellipsoid(np.array([0.1, 0.07, 0.09]), e)
        assert want((np.abs(Vs) > 0.95 * np.abs(Vs).max(0)).any(1).mean()), e


def test_the_hair_qa_counts_tips_and_corners():
    from charkit import qa3d
    m = np.zeros((200, 300), bool)
    x = np.arange(300)
    low = 100 + (40 * np.abs(((x / 100.0) % 1) - 0.5) * -2 + 40).astype(int)   # three V tips along the lower edge
    for c in x:
        m[20:low[c], c] = True
    assert qa3d.hair_tips(m, ppl=200.0) == 3
    sq = np.zeros((200, 200), bool); sq[50:150, 50:150] = True
    yy, xx = np.mgrid[:200, :200]
    disc = (yy - 100) ** 2 + (xx - 100) ** 2 < 60 ** 2
    assert qa3d.silhouette_corners(sq, ppl=200.0) == 4 and qa3d.silhouette_corners(disc, ppl=200.0) == 0


def test_hair_noise_cuts_each_tone_group_apart():
    from charkit import qa3d
    lum = np.tile(np.linspace(0.2, 0.6, 60), (40, 1))                  # the mass: one smooth gradient
    grp = np.ones(lum.shape, int)
    lum2, grp2 = lum.copy(), grp.copy()
    lum2[:, 40:] = 0.95; grp2[:, 40:] = 2                               # a flat bright block beside it, its own group
    e, n = qa3d.tone_edges(lum, grp)
    e2, n2 = qa3d.tone_edges(lum2, grp2)
    mass = grp2 == 1
    # the mass keeps its two tone edges per row wherever its own percentiles fall, whatever the block does
    assert (e2 & mass).sum(1).min() == 2 and (e2 & ~mass).sum() == 0 and n2 == n


def test_a_ribbon_bun_is_a_knot_and_two_loops_set_back_and_lower():
    R = np.eye(3)
    half = np.array([1.0, 1.0, 1.0])
    parts = hp.block_parts(np.zeros(3), R, half, np.array([0.0, 0.0, -5.0]), STYLE, None, 'ribbon')
    assert len(parts) == 3
    (c0, h0), (c1, h1), (c2, h2) = parts
    assert np.allclose(c1[0], -c2[0]) and c1[0] > h0[0] * 0.9          # a loop either side of the knot, mirrored
    assert c1[1] < 0 and c1[2] < 0 and h1[2] < h0[2] and h1[0] < h0[0]   # set back, lower, smaller
    B = hp.bun_block(np.random.default_rng(0).normal(size=(200, 3)) * 0.1 + [0, 0, 1], np.zeros(3), STYLE,
                     kind='ribbon')
    assert (_edges(B['T']) == 2).all()                                  # closed boxes


def test_a_tucked_blade_starts_under_the_surface_and_leaves_it_once():
    F = sphere_fields(1.0)
    ch = F['chart']
    r = np.linspace(0.85, 1.3, 9)
    W3 = ch.point(np.full(9, 80.0), np.full(9, 90.0) + np.arange(9) * 2.0, r)
    wd = np.full(9, 0.04)
    V, w = hp.tuck_blade(F, W3, wd, 0.01, 0.004)
    _, _, rr = ch.coords(V)
    lim = 1.0 - 0.01
    assert rr[0] < lim - 0.02 + 1e-9                                    # the root sunk under the lock's surface
    assert (rr[1:] > lim).all() and len(V) < 9                          # the rest clear of it; the root's run dropped


def test_the_crown_cover_is_outermost_then_under_every_layer():
    o = dict(hp.OPTS, crown_cap=20.0, crown_blend=8.0)
    ins = hp.cap_inset(np.array([0.0, 10.0, 12.0, 16.0, 20.0]), o, STYLE, 1.0)
    assert ins[0] < 0 and ins[1] == ins[0] and ins[2] == ins[0]         # outside the fringe to cap - blend
    assert np.all(np.diff(ins[2:]) > 0) and ins[-1] > max(hp.LAYER.values()) * STYLE['inset']   # then under all


def test_islands_count_a_lock_showing_inside_another():
    from charkit import hairlab as hl
    lab = np.zeros((200, 200), int)
    lab[20:180, 20:180] = 1
    lab[90:110, 90:110] = 2                                             # lock 2 inside lock 1
    depth = np.full(lab.shape, 1.0)
    I = hl.lock_islands(lab, depth, [('side_lock_L', 0), ('upper_back', 0)], 400.0, 1.0)
    assert I['n'] == 1 and I['pokes'] == 1                              # flush along its rim: a poke
    depth[90:110, 90:110] = 0.9
    I = hl.lock_islands(lab, depth, [('side_lock_L', 0), ('flyaways', 0)], 400.0, 1.0)
    assert I['n'] == 0 and I['flicks'] == 1                             # a blade lying over it: a flick


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok', name)
