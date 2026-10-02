"""the joined shoulder (code_body.SOCKET; tool/garments4 round 5, Michael's diagnosis 2026-10-01: the body had no
shoulder, its arms capped tubes beside the torso): a hole in the torso's side, a bridge of loops from its rim to the
arm's ring, the arm's columns matched to the rim's; stitched, the torso, the bridge and the arm are one closed surface
(but for the neck ring) wound outward."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import code_body as cb
from charkit.geom import loft


def synthetic(side='left'):
    rows = np.linspace(cb.CUT, -1.6, 30)
    ts = cb.CUT - rows
    nth = 72
    th = -np.pi + (np.arange(nth) + 0.5) * 2 * np.pi / nth
    R = np.full((len(rows), nth), 0.40)
    R[:3] = np.array([0.15, 0.30, 0.38])[:, None]            # the shoulders' top turning over under the neck
    ax = loft.Axis((0.0, 0.0, cb.CUT), (0, 0, -1), (0, -1, 0))
    T_ = dict(ax=ax, F=loft.Field(ts, th, R, np.zeros(R.shape, bool)))
    sg = 1.0 if side == 'left' else -1.0
    J = np.array([[sg * 0.55, 0.0, -0.88], [sg * 0.75, 0.0, -1.38], [sg * 1.0, 0.0, -2.0], [sg * 1.1, 0.0, -2.2]])
    ch = cb.Chain(J)
    arows = np.linspace(0, ch.total, 40)
    prm = np.tile([0.15, 0.15, 0.15, 2.0, 0.0], (len(arows), 1))
    L_ = dict(chain=ch, rows=arows, params=prm, th=-np.pi + (np.arange(48) + 0.5) * 2 * np.pi / 48)
    return T_, L_


SO = dict(cb.SOCKET, top=0.36, bottom=-1.0)


def test_the_rim_is_a_closed_loop_round_the_hole():
    T_, L_ = synthetic()
    rim = cb.socket_rim(T_, 'left', SO)
    loop = rim['loop']
    n = len(T_['F'].th)
    assert len(loop) == len(set(loop)) == 2 * (len(rim['cols']) - 1) + 2 * (rim['i1'] - rim['i0'])
    for (a, b), (c, d) in zip(loop, loop[1:] + loop[:1]):           # grid neighbours all the way round
        assert abs(a - c) + min(abs(b - d), n - abs(b - d)) == 1
    x = T_['ax'].point(T_['F'].ts[rim['i0']], T_['F'].th[rim['cols']], 1.0)[:, 0]
    assert (x > 0).all()                                            # her left side
    assert len(rim['drop_v']) == (rim['i1'] - rim['i0'] - 1) * (len(rim['cols']) - 2)


def test_the_bridge_matches_the_arms_columns_in_order_and_ends_on_its_ring():
    for side in ('left', 'right'):
        T_, L_ = synthetic(side)
        rim = cb.socket_rim(T_, side, SO)
        br = cb.shoulder_bridge(T_, L_, side, SO, rim)
        th0 = br['th'][0]
        assert np.all(np.diff(th0) > 0) and th0[-1] - th0[0] < 2 * np.pi    # one turn, in the arm's own direction
        ch = L_['chain']
        s, _, r, _ = ch.coords(br['A'][0])
        assert np.allclose(s, SO['s0'], atol=1e-6) and np.allclose(r, 0.15, atol=1e-6)
        assert br['P'].shape == (SO['loops'], len(rim['loop']), 3)
        # the evened columns: the last rings' angles step evenly round
        assert np.allclose(np.diff(br['th'][-1]), 2 * np.pi / len(th0), atol=1e-9)


def test_stitched_it_is_one_closed_surface_open_only_at_the_neck():
    T_, L_ = synthetic()
    rim = cb.socket_rim(T_, 'left', SO)
    br = cb.shoulder_bridge(T_, L_, 'left', SO, rim)
    F = T_['F']
    TT, TH = np.meshgrid(F.ts, F.th, indexing='ij')
    P = T_['ax'].point(TT, TH, F.R)
    V, faces, _, _, _, idx = cb._grid(P, (0, 0, 1, 1), False, True, holes=(rim['drop_v'], rim['drop_f']))
    nv = len(V)
    K, N = br['P'].shape[:2]
    Va, Fa, _, _, _ = cb._grid(br['A'], (0, 0, 1, 1), False, True)
    a0 = nv + K * N
    loops = [[int(idx[i, j]) for i, j in br['loop']]] + [nv + k * N + np.arange(N) for k in range(K)] + [a0 + np.arange(N)]
    fb, _ = cb.bridge_faces(loops)
    allV = np.concatenate([V, br['P'].reshape(-1, 3), Va])
    allF = list(faces) + fb + [tuple(v + a0 for v in f) for f in Fa]
    E = {}
    for f in allF:
        for k in range(len(f)):
            a, b = f[k], f[(k + 1) % len(f)]
            E.setdefault((min(a, b), max(a, b)), []).append(a < b)
    once = [e for e, v in E.items() if len(v) == 1]
    assert len(once) == len(F.th)                                     # the neck ring alone is open
    assert all(len(v) == 2 and v[0] != v[1] for e, v in E.items() if len(v) > 1)    # manifold, wound one way
    # wound outward: the closed surface's signed volume (the neck closed by its centre) is positive
    ring = [int(idx[0, j]) for j in range(len(F.th))]
    c = allV[ring].mean(0)
    vol = 0.0
    for f in allF:
        for k in range(1, len(f) - 1):
            a, b, d = allV[f[0]], allV[f[k]], allV[f[k + 1]]
            vol += np.dot(a, np.cross(b, d))
    for j in range(len(ring)):
        a, b = allV[ring[j]], allV[ring[(j + 1) % len(ring)]]
        vol += np.dot(c, np.cross(a, b))
    assert vol > 0


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f()
            print('ok', k)
