"""charkit.geom.lockshell: a lock's tube is closed and fold-free; a known lock drawn in two views (its silhouettes on
synthetic design grids) is recovered by the fit from them, within a pixel or two of its drawn centreline and at its
drawn shape (venv: run this file, or pytest). The lock shells on the design are a measurement (tool/hairshell), not a
test: they need the produced masks and a build."""
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


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f()
            print(k, 'ok')
