"""charkit.romvideo's interpolation (the motion video check): quaternions, slerp, the clip's schedule, and poses as local
rotations composed back, on a synthetic skeleton with known answers (venv: run this file, or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import romvideo as RV, pose as P


def skeleton():
    """a small A-posed humanoid in Blender's frame (Z up, facing -Y, her left +X)."""
    H = {'hips': (0, 0, 1.0), 'spine': (0, 0, 1.1), 'chest': (0, 0, 1.2), 'upperChest': (0, 0, 1.3),
         'neck': (0, 0, 1.45), 'head': (0, 0, 1.55)}
    for s, x in (('left', 1.0), ('right', -1.0)):
        H.update({s + 'Shoulder': (0.04 * x, 0, 1.40), s + 'UpperArm': (0.16 * x, 0, 1.40),
                  s + 'LowerArm': (0.36 * x, 0, 1.18), s + 'Hand': (0.55 * x, 0, 0.98),
                  s + 'UpperLeg': (0.09 * x, 0, 0.95), s + 'LowerLeg': (0.09 * x, 0, 0.52),
                  s + 'Foot': (0.09 * x, 0, 0.09), s + 'Toes': (0.09 * x, -0.1, 0.02)})
    return P.Skeleton({b: np.array(v, float) for b, v in H.items()})


def angle(R):
    return float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))))


def axis(R):
    a = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]])
    return a / np.linalg.norm(a)


def test_quaternion_round_trip_including_near_half_turns():
    rng = np.random.default_rng(0)
    Rs = [P.rotation(rng.normal(size=3), d) for d in (0.0, 1.0, 45.0, 120.0, 179.0, 179.99, 180.0)]
    Rs += [P.rotation(rng.normal(size=3), rng.uniform(0, 180)) for _ in range(50)]
    R = np.array(Rs)
    q = RV.quat(R)
    assert np.allclose(np.linalg.norm(q, axis=1), 1.0)
    assert (q[:, 0] >= 0).all()
    assert np.abs(RV.matrix(q) - R).max() < 1e-9


def test_slerp_ends_halfway_and_constant_speed():
    R1 = P.rotation((0.3, -0.5, 0.8), 100.0)
    q0, q1 = RV.quat(np.eye(3)), RV.quat(R1)
    assert np.allclose(RV.matrix(RV.slerp(q0, q1, 0.0)), np.eye(3), atol=1e-12)
    assert np.allclose(RV.matrix(RV.slerp(q0, q1, 1.0)), R1, atol=1e-12)
    for s in (0.1, 0.25, 0.5, 0.9):                  # the angle grows linearly, about the same axis
        R = RV.matrix(RV.slerp(q0, q1, s))
        assert abs(angle(R) - 100.0 * s) < 1e-9
        assert np.allclose(axis(R), axis(R1), atol=1e-9)
    # between two non-identity keys: halfway is A turned half the relative rotation
    A, B = P.rotation((1, 0, 0), 30.0), P.rotation((0, 0, 1), 70.0)
    M = RV.matrix(RV.slerp(RV.quat(A), RV.quat(B), 0.5))
    rel = A.T @ B
    assert abs(angle(A.T @ M) - angle(rel) / 2) < 1e-9 and abs(angle(M.T @ B) - angle(rel) / 2) < 1e-9


def test_slerp_takes_the_shorter_way_round():
    q0, q1 = RV.quat(np.eye(3)), RV.quat(P.rotation((0, 0, 1), 170.0))
    a = RV.slerp(q0, q1, 0.5)
    b = RV.slerp(q0, -q1, 0.5)                       # the same rotation, the other sign: the same path
    assert np.allclose(RV.matrix(a), RV.matrix(b), atol=1e-12)
    assert abs(angle(RV.matrix(a)) - 85.0) < 1e-9


def test_slerp_is_vectorised_over_bones():
    rng = np.random.default_rng(1)
    R = np.array([P.rotation(rng.normal(size=3), rng.uniform(0, 170)) for _ in range(8)])
    I = np.tile([1.0, 0, 0, 0], (8, 1))
    Q = RV.slerp(I, RV.quat(R), 0.3)
    for i in range(8):
        assert np.allclose(Q[i], RV.slerp(I[i], RV.quat(R[i]), 0.3))


def test_ease_and_schedule():
    assert RV.ease(0.0) == 0.0 and RV.ease(1.0) == 1.0 and abs(RV.ease(0.5) - 0.5) < 1e-12
    assert RV.ease(1e-3) < 1e-5 and 1 - RV.ease(1 - 1e-3) < 1e-5        # flat at both ends
    fr = RV.schedule((1.0, 0.5, 1.0), 24)
    assert len(fr) == 60
    ph = [p for p, _ in fr]
    assert ph.count('in') == 24 and ph.count('hold') == 12 and ph.count('out') == 24
    w = np.array([x for _, x in fr])
    assert w[0] == 0.0 and w[-1] == 0.0
    assert (w[24:36] == 1.0).all()
    assert (np.diff(w[:24]) > 0).all() and (np.diff(w[36:]) < 0).all()
    assert np.allclose(w[36:], w[:24][::-1])          # the out is the in reversed (the renders shared)


def test_local_rotations_compose_back_to_the_solve():
    sk = skeleton()
    for preset in ({'bones': {'UpperArm': {'aim': 'up'}, 'LowerArm': {'bend': 90}, 'spine': {'turn': 20},
                              'chest': {'nod': 10}}},
                   {'bones': {'hips': {'nod': 15}, 'UpperLeg': {'swing': 105}, 'LowerLeg': {'bend': 125},
                              'Foot': {'bend': -35}, 'neck': {'tilt': 10}, 'head': {'turn': 35}}}):
        D = P.solve(sk, preset)
        L = RV.local_rotations(sk, D)
        D2 = RV.compose(sk, L)
        for b in sk.order:
            assert np.abs(D[b] - D2[b]).max() < 1e-9, b


def test_a_key_halfway_bends_the_elbow_half_way():
    sk = skeleton()
    D = P.solve(sk, {'bones': {'LowerArm': {'bend': 90}}})
    key = RV.Key(RV.local_rotations(sk, D))
    d0 = sk.dir('leftLowerArm')

    def turned(w):                                   # the forearm's turn from its rest direction (deg)
        H, T = P.posed_joints(sk, RV.compose(sk, key.at(w)))
        d = (T['leftLowerArm'] - H['leftLowerArm']) / np.linalg.norm(T['leftLowerArm'] - H['leftLowerArm'])
        return float(np.degrees(np.arccos(np.clip(d @ d0, -1, 1))))
    assert abs(turned(1.0) - 90.0) < 1e-6
    assert abs(turned(0.5) - 45.0) < 1e-6
    assert abs(turned(0.2) - 18.0) < 1e-6
    # every frame of the clip within the pose's range (no overshoot), the hold at the pose
    for _, w in RV.schedule():
        assert -1e-9 <= turned(w) <= 90.0 + 1e-9
    D1 = RV.compose(sk, key.at(1.0))
    assert all(np.abs(D1[b] - D[b]).max() < 1e-9 for b in sk.order)


def test_the_rest_key_is_the_identity():
    sk = skeleton()
    D = RV.compose(sk, RV.Key({}).at(0.7))
    assert all(np.allclose(D[b], np.eye(4)) for b in sk.order)


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f()
            print('ok', k)
