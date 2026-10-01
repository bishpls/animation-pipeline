"""charkit.geom.lockshell: a lock's tube is closed and fold-free; a known lock drawn in two views (its silhouettes on
synthetic design grids) is recovered by the fit from them, within a pixel or two of its drawn centreline and at its
drawn shape; the fit is bit-identical when its float inputs move by 1e-10 m, as two machines' hulls do (tool/hairshell3:
the det fit, snapped inputs and parameters) (venv: run this file, or pytest). The lock shells on the design are a
measurement (tool/hairshell), not a test: they need the produced masks and a build; their laptop-vs-box check is
tools/hairshell3/xmachine.py, their 1e-10 check on a real build's inputs tools/hairshell3/determ.py.""",
import math, os, sys
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit.geom import hairpieces as hp, lockshell as ls

PPL = 200.0


def _world():
    from charkit.bodyqa import WIN
    shape = (int(round((WIN['top'] - WIN['bottom']) * PPL)), int(round(2 * WIN['x'] * PPL)))
    views = {n: SimpleNamespace(ppl=PPL, grid_eye=(500.0, 400.0), axis=500.0, eye_y=400.0) for n in ('front', 'profile')}
    ch = hp.Chart((0.0, 0.0, 0.0), 0.0)
    G = hp.Grid(4.0, 3.0, 168.0)
    F = dict(chart=ch, grid=G, R=np.full((G.nph, G.nth), 0.5), S=np.full((G.nph, G.nth), 0.3))
    return views, F, (1.0, np.zeros(3)), shape


def _known(F):
    """a lock on the head's side: down and round from (phi 50, theta 50) to (phi 75, theta 125), 0.46 out, widening
    from the root and tapering to its tip."""
    ch = F['chart']
    u = np.linspace(0, 1, 30)
    P = ch.point(50 + 25 * u, 50 + 75 * u, np.full(30, 0.46))
    W = 0.09 * np.sin(np.pi * np.clip(0.15 + 0.85 * u, 0, 1)) + 0.01
    return P, W, ls.tube(P, W, 0.35 * W, ch, 0.0, 10)


def test_tube_closed_and_unfolded():
    views, F, hf, shape = _world()
    P, W, part = _known(F)
    T = part['T']
    E = np.sort(np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]]), 1)
    _, cnt = np.unique(E, axis=0, return_counts=True)
    assert (cnt == 2).all(), 'every edge shared by two faces'
    assert hp.folds(part['V'], T, part['outer'], part['vn_env']) == 0


def test_fit_recovers_a_drawn_lock():
    views, F, hf, shape = _world()
    P, W, part = _known(F)
    o = dict(ls.DEFAULT, bins=12, widen_lw=1.0)   # (the fit alone: the side locks' overlap widening off)
    lk = ls.Lock('t', 'side_locks', 'front', F, views, hf, 1.0, o)
    for n, az in (('front', 0.0), ('profile', 90.0)):
        m = ls.silhouette(part['V'], part['T'], views[n], az, hf, shape)
        c, r = hp.view_px(P[:1], views[n], az, False, hf)
        assert lk.add_view(n, az, m, (r[0], c[0]), 1)
    lk.init()
    lk.fit()
    got = lk.shell()
    for n, d in lk.drawn.items():
        assert lk.cost[n] < 2.0, (n, lk.cost)
        sil = ls.silhouette(got['V'], got['T'], views[n], d['az'], hf, shape)
        iou = (sil & d['mask']).sum() / (sil | d['mask']).sum()
        assert iou > 0.7, (n, iou)


def _fit_moved(eps, seed, q=2.0 ** -12, **over):
    """the known lock fitted from front and profile with every float input moved by up to eps (the fields, the chart's
    centre, the hull's frame, the views' calibration), its inputs snapped as build_shells snaps them (q; 0: not
    snapped), with the lock_shells options `over` -> the shell."""
    import copy
    views, F, hf, shape = _world()
    P, W, part = _known(F)
    masks = {}
    for n, az in (('front', 0.0), ('profile', 90.0)):
        masks[n] = ls.silhouette(part['V'], part['T'], views[n], az, hf, shape)
    rng = np.random.default_rng(seed)
    F2 = dict(F, R=F['R'] + rng.uniform(-eps, eps, F['R'].shape), S=F['S'] + rng.uniform(-eps, eps, F['S'].shape))
    ch = copy.copy(F['chart']); ch.c = np.asarray(ch.c, float) + rng.uniform(-eps, eps, 3); F2['chart'] = ch
    hf2 = (hf[0] + rng.uniform(-eps, eps), np.asarray(hf[1], float) + rng.uniform(-eps, eps, 3))
    v2 = {n: SimpleNamespace(ppl=v.ppl + rng.uniform(-eps, eps), grid_eye=tuple(x + rng.uniform(-eps, eps) for x in
                                                                                  v.grid_eye),
                             axis=v.axis + rng.uniform(-eps, eps), eye_y=v.eye_y + rng.uniform(-eps, eps))
          for n, v in views.items()}
    F2, v2, hf2, L2 = ls.det_inputs(F2, v2, hf2, 1.0, q)
    o = dict(ls.DEFAULT, bins=12, widen_lw=1.0, **over)
    lk = ls.Lock('t', 'side_locks', 'front', F2, v2, hf2, L2, o)
    for n, az in (('front', 0.0), ('profile', 90.0)):
        c, r = hp.view_px(P[:1], views[n], az, False, hf)
        assert lk.add_view(n, az, masks[n], (r[0], c[0]), 1)
    lk.init()
    lk.fit()
    return lk.shell()


def test_fit_bit_identical_under_input_noise():
    """the fit's end is a function of its inputs, not of noise in them. (1) The det fit on unsnapped inputs moved 1e-12
    (an ulp-scale stand-in for another machine's arithmetic): the same bits; round 2's fit (det off) moves 1e-12..1e-11
    m under it (the test's calibration: it would catch the old fit). (2) Inputs moved 1e-10 m (two machines' hulls), as
    build_shells snaps them: the same bits (unsnapped, one seed in five straddles the tube's 2^-26 m grid)."""
    same = lambda a, b: all(np.array_equal(a[k], b[k]) for k in ('V', 'vn_env', 'strand'))
    base0 = _fit_moved(0.0, 0, q=0)
    for seed in (1, 2, 3):
        assert same(base0, _fit_moved(1e-12, seed, q=0)), seed
    old0 = _fit_moved(0.0, 0, q=0, det=False)
    assert not all(same(old0, _fit_moved(1e-12, seed, q=0, det=False)) for seed in (1, 2, 3)), 'calibration'
    base = _fit_moved(0.0, 0)
    for seed in (1, 2, 3, 4, 5):
        got = _fit_moved(1e-10, seed)
        assert same(base, got), (seed, float(np.abs(base['V'] - got['V']).max()))


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f()
            print(k, 'ok')
