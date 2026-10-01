"""charkit.rom (the range-of-motion suite's measures) on synthetic meshes with known answers (venv: run this file, or
pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import rom, pose as P
from charkit.geom.bvh import BVH


def tube(n_rings=41, nth=32, length=2.0, r=0.2):
    """a capped tube along -z from z = 0 (its rings, then the two cap centres) -> (V, F)."""
    z = -np.linspace(0, length, n_rings)
    th = np.linspace(0, 2 * np.pi, nth, endpoint=False)
    V = np.stack([np.cos(th)[None] * r + 0 * z[:, None], np.sin(th)[None] * r + 0 * z[:, None],
                  z[:, None] + 0 * th[None]], -1).reshape(-1, 3)
    F = []
    for i in range(n_rings - 1):
        for j in range(nth):
            a, b = i * nth + j, i * nth + (j + 1) % nth
            c, d = a + nth, b + nth
            F += [(a, c, b), (b, c, d)]
    top, bot = len(V), len(V) + 1
    V = np.vstack([V, [0, 0, 0], [0, 0, -length]])
    for j in range(nth):
        F.append((top, j, (j + 1) % nth))
        a, b = (n_rings - 1) * nth + j, (n_rings - 1) * nth + (j + 1) % nth
        F.append((bot, b, a))
    return V, np.array(F)


def two_bone(V, blend=0.2):
    """weights of a tube on bones 0 (z > -1) and 1 (below), blended over `blend` either side of the joint."""
    t = np.clip((-V[:, 2] - 1.0 + blend) / (2 * blend), 0, 1) if blend > 0 else (-V[:, 2] > 1.0).astype(float)
    return np.stack([1 - t, t], 1)


def lbs2(V, W, R1, joint):
    X1 = (V - joint) @ R1.T + joint
    return W[:, :1] * V + W[:, 1:] * X1


def test_closed_tube_winding():
    V, F = tube()
    keep = V[:, 2] > -1.0                       # the upper half: open at its bottom ring
    C = rom.Closed(F, keep)
    assert len(C.loops) == 1
    bv = C.bvh(V)
    w = bv.winding_number(np.array([[0, 0, -0.5], [0, 0, -1.5], [0.5, 0, -0.5]]))
    assert w[0] > 0.99 and w[1] < 0.01 and w[2] < 0.01


def test_ring_keeps_volume_under_a_smooth_bend_and_loses_it_on_a_twist():
    V, F = tube()
    joint = np.array([0.0, 0, -1.0])
    rings = rom._plane_loops(V, F, joint, np.array([0, 0, -1.0]))
    assert len(rings) == 1
    a0 = rom.ring_area(rom._ring_points(V, rings[0]))
    assert abs(a0 - np.pi * 0.2 ** 2) / (np.pi * 0.04) < 0.02
    W = two_bone(V, 0.25)
    bent = lbs2(V, W, P.rotation([1, 0, 0], 90), joint)
    r_bend = rom.ring_area(rom._ring_points(bent, rings[0])) / a0
    twisted = lbs2(V, W, P.rotation([0, 0, 1], 180), joint)
    r_twist = rom.ring_area(rom._ring_points(twisted, rings[0])) / a0
    assert 0.6 < r_bend < 0.95                   # LBS loses some at a 90 deg bend
    assert r_twist < 0.05                        # the candy-wrapper: a half turn collapses the middle ring


def test_dqs_keeps_the_ring_lbs_loses():
    V, F = tube()
    joint = np.array([0.0, 0, -1.0])
    rings = rom._plane_loops(V, F, joint, np.array([0, 0, -1.0]))
    a0 = rom.ring_area(rom._ring_points(V, rings[0]))
    W = two_bone(V, 0.25)
    J = np.tile([0, 1], (len(V), 1))
    for R1, lbs_max in ((P.rotation([1, 0, 0], 135), 0.6), (P.rotation([0, 0, 1], 150), 0.3)):
        R = np.stack([np.eye(3), R1])
        t = np.stack([np.zeros(3), joint - R1 @ joint])
        X = rom.dqs(V, J, W, R, t)
        assert rom.ring_area(rom._ring_points(X, rings[0])) / a0 > 0.9
        Xl = lbs2(V, W, R1, joint)
        assert rom.ring_area(rom._ring_points(Xl, rings[0])) / a0 < lbs_max
    # rigid: one bone's motion exactly
    X = rom.dqs(V, np.zeros_like(J), np.c_[np.ones(len(V)), np.zeros(len(V))], R, t)
    assert np.allclose(X, V, atol=1e-12)


def test_inside_new_and_crossings():
    V, F = tube()
    bv0 = BVH((V, F))
    Q0 = np.array([[0.5, 0, -0.5], [0.0, 0.0, -0.5], [0.3, 0, -1.0]])         # outside, inside (at rest), outside
    Q1 = Q0 + np.array([[-0.45, 0, 0], [0, 0, 0], [-0.15, 0, 0]])            # into it 0.15 deep; stays; into 0.05
    r = rom.inside_new(Q0, Q1, bv0, bv0, L=1.0, tol=0.01)
    assert r['n'] == 2 and abs(r['depth'] - 0.15) < 0.01                      # (the one inside at rest is not new)
    E = np.array([[0, 1], [2, 3]])
    X0 = np.array([[0.5, 0, -0.5], [0.6, 0, -0.5], [0.5, 0, -1], [0.6, 0, -1]])
    X1 = X0.copy()
    X1[0] = [0.1, 0, -0.5]                                                      # the first edge now crosses the wall
    c = rom.crossings_new(X0, X1, E, bv0, bv0)
    assert c['n'] == 1 and c['share'] == 0.5


def test_boundary_loops_and_caps_close():
    V, F = tube()
    keep = (V[:, 2] > -1.5) & (V[:, 2] < -0.5)                                 # a band: two open rings
    C = rom.Closed(F, keep)
    assert len(C.loops) == 2
    Xc, Fc = rom.capped(V, C.F, C.loops)
    E = np.sort(np.concatenate([Fc[:, [0, 1]], Fc[:, [1, 2]], Fc[:, [2, 0]]]), 1)
    _, cnt = np.unique(E, axis=0, return_counts=True)
    assert (cnt == 2).all()                                                     # watertight


def test_strain_and_grades():
    V = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0.0]])
    E = np.array([[0, 1], [0, 2]])
    s = rom.strain(V, V * [1.5, 1, 1], E)
    assert abs(s['max'] - 0.5) < 1e-9
    assert rom.grade('vol_elbow', 0.85) == 'PASS' and rom.grade('vol_elbow', 0.7) == 'WARN' \
        and rom.grade('vol_elbow', 0.5) == 'FAIL'
    assert rom.grade('arm_torso', 0.005) == 'PASS' and rom.grade('arm_torso', 0.04) == 'FAIL'
    assert rom.grade('sleeve_top_L', 0.02) == 'FAIL' and rom.grade('nothing', 1.0) == 'INFO'


class _Rig:
    """a stand-in rig for weight_sanity: one tube skinned on two bones."""

    def __init__(self, stray=False):
        V, F = tube()
        W = two_bone(V)
        J = np.tile([0, 1], (len(V), 1))
        if stray:                                    # a patch near the top weighted to the far bone
            m = V[:, 2] > -0.2
            W[m] = [0.6, 0.4]
        H = {'leftUpperArm': (0, 0, 0.0), 'leftLowerArm': (0, 0, -1.0)}
        T = {'leftUpperArm': (0, 0, -1.0), 'leftLowerArm': (0, 0, -2.0)}
        self.sk = P.Skeleton(H, T)
        self.bones = ['leftUpperArm', 'leftLowerArm']
        self.objs = {'clawd_skin': rom.Obj('clawd_skin', 'skin', V, F, J, W, [])}

    def bone_names(self):
        return list(dict.fromkeys(self.bones))


def test_weight_sanity_finds_stray_influence():
    ok = rom.weight_sanity(_Rig(), L=1.0, step_len=0.1)['clawd_skin']
    bad = rom.weight_sanity(_Rig(stray=True), L=1.0, step_len=0.1)['clawd_skin']
    assert ok['stray'] == 0 and ok['sum_err'] < 1e-9
    assert bad['stray'] > 0 and bad['stray_w'] >= 0.4
    assert bad['step_max'] > ok['step_max']


def test_qa_checks_calibrated_or_info():
    """every graded rom_* check has a calibrated record; the rest report INFO beside their grade."""
    import json
    from charkit import romqa
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for k in romqa.CALIBRATED:
        assert k in romqa.CHECKS or k in romqa.WEIGHT_CHECKS, k
        r = json.load(open(os.path.join(root, 'charkit', 'calib', 'records', k + '.json')))
        assert r['verdict'] == 'calibrated', (k, r['verdict'])
    rep = {'poses': {'elbows_135': {'summary': {'vol_elbow': 0.38}}, 'head_turn': {'summary': {'neck_strain': 0.6}}},
           'weights': {'clawd_skin': {'stray_share': 0.0}}}
    C = romqa.checks_of(rep)
    assert C['rom_vol_elbow']['status'] == 'FAIL' and C['rom_neck_strain']['status'] == 'INFO'
    assert C['rom_neck_strain']['grade'] == 'FAIL' and C['rom_weights_stray']['status'] == 'PASS'


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f()
            print('ok', k)
