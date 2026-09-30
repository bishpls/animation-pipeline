"""charkit.geom.hairpieces.fit_block, the buns' fit, under tiny input moves (tool/hull-local; face round 5's terminator:
a 0.8 um move of the head's centre moved a bun 0.027 L through the fit, and the back view's terminator 0.45 with it).

A drawn ribbon bun (its knot and two loops, a known pose) in the sheet's three bun views, the hull's bun points a noisy,
inflated sampling of it (a visual hull's blob), the rest of the hair a disc round the head. The fit, then the fit with its
inputs moved by 1 um (4e-6 L): the head's centre along each axis, every bun point in a random direction. The bun must move
under 1e-4 L each time, and still fit the drawing. Calibrated: the Nelder-Mead fit (method 'nm', the fit until
2026-09-30) fails it on the same scene.

    python charkit/tests/test_bun_fit.py        (venv; or pytest)
"""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit.geom import hairpieces as hp, hull, raster      # noqa: E402

PPL = 60.0                        # px per L (the sheet's is about 212: a coarser grid, the test's time)
EPS = 4e-6                        # L: 1 um on a 0.25 m L
MOVE = 1e-4                       # L: the most the bun may move
STYLE = dict(bun_e=0.3, bun_q=0.06, bun_knot=0.6, bun_loop=0.26, bun_tails=0)
FRAME = (1.0, np.zeros(3))        # the hull's frame is the world's (L units)
HEAD_C = np.array([0.0, 0.02, 0.1])
SIDE = 1


def _views():
    from charkit.bodyqa import WIN
    W, H = raster.window_shape(1.0 / PPL, WIN)
    out = {}
    for name, az in (('front', 0.0), ('profile', 90.0), ('back', 180.0)):
        v = hull.View(name, az, np.zeros((H, W), bool), PPL, W / 2.0, WIN['top'] * PPL)
        v.grid_eye = (v.axis, v.eye_y)
        out[name] = v
    return out


def _mesh(parts, e=0.3, nu=40, nv=20):
    Vs, Ts, n = [], [], 0
    for off, hs, R in parts:
        U, T = hp.superellipsoid(hs, e, nu, nv)
        Vs.append(off + U @ R.T); Ts.append(T + n); n += len(U)
    return np.concatenate(Vs), np.concatenate(Ts)


def scene(seed=0):
    """-> (P, head_c, targets, views): the drawn bun's views as fit_block takes them (bun_targets' tuples). As a drawing
    is, no one pose reproduces them all: each view drawn from its own pose (a few degrees and a few hundredths of L
    apart) and rounder than our boxes (the drawing's bun_e 0.55)."""
    from scipy.spatial.transform import Rotation as Rot
    views = _views()
    c = np.array([0.52, 0.12, 0.62])
    up = (c - HEAD_C) / np.linalg.norm(c - HEAD_C)
    front = np.array([0.0, -1.0, 0.0]) - up * (-up[1]); front /= np.linalg.norm(front)
    R = Rot.from_rotvec([0.12, -0.08, 0.15]).as_matrix() @ np.stack([np.cross(front, up), front, up], 1)
    half = np.array([0.19, 0.15, 0.17])
    drawn = {'front': ([0.0, 0.0, 0.0], [0.0, 0.0, 0.0], 1.0), 'profile': ([0.02, -0.03, 0.01], [0.0, 0.1, 0.05], 1.06),
             'back': ([-0.015, 0.0, 0.02], [0.06, 0.0, -0.08], 0.95)}
    rng = np.random.default_rng(seed)
    targets, P = [], None
    for name, v in views.items():
        dc, rv, k = drawn[name]
        Rv = Rot.from_rotvec(rv).as_matrix() @ R
        cv = c + np.asarray(dc)
        parts = [(off, hs, Rv) for off, hs in hp.block_parts(cv, Rv, half * k, HEAD_C, STYLE, None, 'ribbon')]
        V, T = _mesh(parts, e=0.55)
        if P is None:                     # the hull's bun points: the front's pose, inflated and noisy (a visual hull)
            P = c + (V[rng.choice(len(V), 900)] - c) * 1.12 + rng.normal(0, 0.012, (900, 3))
        win = hp.view_window(v, v.az, False, FRAME)
        d, _ = raster.window_zbuffer([(V, T, 1)], v.az, *win)
        m = np.isfinite(d)
        # the rest of the hair: a disc round the head's centre, under the bun
        cc, rr = hp.view_px(HEAD_C[None], v, v.az, False, FRAME)
        yy, xx = np.mgrid[:m.shape[0], :m.shape[1]]
        other = ((xx - cc[0]) ** 2 + (yy - rr[0]) ** 2 < (0.95 * PPL) ** 2) & ~m
        targets.append((name, v.az, False, m, other))
    return P, HEAD_C.copy(), targets, views


def _fit(P, head_c, targets, views, method):
    fit, rep = hp.fit_block(P, head_c, STYLE, targets, views, FRAME, (600, 900), 'ribbon', {'profile': 1.0},
                            method=method)
    return hp.bun_block(P, head_c, STYLE, SIDE, fit, 'ribbon')['V'], rep


def _moved(P, head_c):
    rng = np.random.default_rng(7)
    d = rng.normal(size=P.shape); d /= np.linalg.norm(d, axis=1, keepdims=True)
    yield 'head +x', P, head_c + [EPS, 0, 0]
    yield 'points', P + EPS * d, head_c
    yield 'head -y', P, head_c - [0, EPS, 0]
    yield 'head +z', P, head_c + [0, 0, EPS]


_RUNS = {}


def moves(method, n=4):
    """-> ({perturbation: the bun's largest vertex move, L}, the unperturbed fit's report), cached per method."""
    if (method, n) not in _RUNS:
        P, hc, targets, views = scene()
        V0, rep = _fit(P, hc, targets, views, method)
        out = {}
        for name, P1, h1 in list(_moved(P, hc))[:n]:
            V1, _ = _fit(P1, h1, targets, views, method)
            out[name] = float(np.linalg.norm(V1 - V0, axis=1).max())
        _RUNS[method, n] = out, rep
    return _RUNS[method, n]


def test_the_bun_fit_is_stable_under_a_1um_move_of_its_inputs():
    mv, rep = moves('soft')
    assert rep['method'] == 'soft'
    assert max(mv.values()) < MOVE, mv
    # and it fits: in every view well up from the start's IoU, and within 0.03 of Nelder-Mead's (which fits the drawing
    # as closely but lands anywhere in a spread of near-equal poses)
    _, nm = moves('nm', 2)
    for name, iou in rep['after'].items():
        assert iou > rep['before'][name] + 0.05 and iou > nm['after'][name] - 0.03, (name, rep, nm['after'])


def test_the_nelder_mead_bun_fit_fails_it():
    # (calibration: the fit until 2026-09-30, on pixel counts; its path forks at the first pixel that flips)
    mv, rep = moves('nm', 2)
    assert rep['method'] == 'nm'
    assert max(mv.values()) > MOVE, mv


if __name__ == '__main__':
    import time
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            t = time.time()
            fn()
            print('ok', name, '%.1f s' % (time.time() - t))
