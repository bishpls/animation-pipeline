"""charkit.pose (the pose presets as data) on a synthetic humanoid with known answers (venv: run this file, or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import pose as P
from charkit.mh import VRM_PARENT


def skeleton():
    """a little humanoid in Blender's frame (Z up, facing -Y, her left +X): arms hanging 20 deg out, hands with palms
    toward the thighs (thumbs forward), legs straight."""
    H = {'hips': (0, 0, 1.0), 'spine': (0, 0, 1.1), 'chest': (0, 0, 1.2), 'upperChest': (0, 0, 1.3),
         'neck': (0, 0, 1.45), 'head': (0, 0, 1.55)}
    T = {'hips': (0, 0, 1.1), 'spine': (0, 0, 1.2), 'chest': (0, 0, 1.3), 'upperChest': (0, 0, 1.45),
         'neck': (0, 0, 1.55), 'head': (0, 0, 1.75)}
    for s, x in (('left', 1.0), ('right', -1.0)):
        a = np.radians(20)
        sh = np.array([0.18 * x, 0, 1.4])
        el = sh + 0.3 * np.array([np.sin(a) * x, 0, -np.cos(a)])
        wr = el + 0.25 * np.array([np.sin(a) * x, 0, -np.cos(a)])
        H[s + 'Shoulder'], T[s + 'Shoulder'] = (0.03 * x, 0, 1.42), tuple(sh)
        H[s + 'UpperArm'], T[s + 'UpperArm'] = tuple(sh), tuple(el)
        H[s + 'LowerArm'], T[s + 'LowerArm'] = tuple(el), tuple(wr)
        down = np.array([np.sin(a) * x, 0, -np.cos(a)])
        H[s + 'Hand'], T[s + 'Hand'] = tuple(wr), tuple(wr + 0.08 * down)
        # the knuckles: the index in front (-y), the little behind; palm toward the midline
        for i, f in enumerate(('Index', 'Middle', 'Ring', 'Little')):
            k = wr + 0.08 * down + np.array([0, -0.03 + 0.02 * i, 0])
            for j, seg in enumerate(('Proximal', 'Intermediate', 'Distal')):
                H[s + f + seg] = tuple(k + 0.03 * j * down)
                T[s + f + seg] = tuple(k + 0.03 * (j + 1) * down)
        th = wr + 0.03 * down + np.array([0, -0.04, 0])
        for j, seg in enumerate(('Metacarpal', 'Proximal', 'Distal')):
            H[s + 'Thumb' + seg] = tuple(th + 0.025 * j * down)
            T[s + 'Thumb' + seg] = tuple(th + 0.025 * (j + 1) * down)
        hip = np.array([0.1 * x, 0, 1.0])
        H[s + 'UpperLeg'], T[s + 'UpperLeg'] = tuple(hip), tuple(hip + [0, 0, -0.45])
        H[s + 'LowerLeg'], T[s + 'LowerLeg'] = tuple(hip + [0, 0, -0.45]), tuple(hip + [0, 0, -0.9])
        H[s + 'Foot'], T[s + 'Foot'] = tuple(hip + [0, 0, -0.9]), tuple(hip + [0, -0.12, -0.97])
    return P.Skeleton(H, T)


def dirs(sk, D, b):
    H, T = P.posed_joints(sk, D)
    return P._unit(T[b] - H[b])


def test_rest_is_identity():
    sk = skeleton()
    D = P.solve(sk, {'bones': {}})
    assert all(np.allclose(M, np.eye(4)) for M in D.values())
    D = P.solve(sk, P.library()['elbows_90'], f=0.0)
    assert all(np.allclose(M, np.eye(4)) for M in D.values())


def test_aim_and_mirror():
    sk = skeleton()
    D = P.solve(sk, {'bones': {'UpperArm': {'aim': 'forward'}}})
    assert np.allclose(dirs(sk, D, 'leftUpperArm'), [0, -1, 0], atol=1e-9)        # forward is -y
    assert np.allclose(dirs(sk, D, 'rightUpperArm'), [0, -1, 0], atol=1e-9)
    D = P.solve(sk, {'bones': {'UpperArm': {'aim': 'out'}}})
    assert np.allclose(dirs(sk, D, 'leftUpperArm'), [1, 0, 0], atol=1e-9)
    assert np.allclose(dirs(sk, D, 'rightUpperArm'), [-1, 0, 0], atol=1e-9)        # mirrored
    # the children are carried: the forearm points where the upper arm does (the elbow straight but for its rest bend)
    assert dirs(sk, D, 'leftLowerArm')[0] > 0.99


def test_bend_is_anatomical():
    sk = skeleton()
    D = P.solve(sk, P.library()['elbows_90'])
    for s in ('left', 'right'):
        assert abs(P.angle_between(sk, D, s + 'UpperArm', s + 'LowerArm') - 90) < 1e-6
        assert dirs(sk, D, s + 'LowerArm')[1] < -0.9                               # the forearm comes forward
    D = P.solve(sk, P.library()['knees_90'])
    assert dirs(sk, D, 'leftLowerLeg')[1] > 0.99                                    # the shin goes back
    # half way: half the angle
    D = P.solve(sk, P.library()['elbows_90'], f=0.5)
    assert abs(P.angle_between(sk, D, 'leftUpperArm', 'leftLowerArm') - 45) < 1e-6


def test_fist_curls_toward_the_palm():
    sk = skeleton()
    n, k = sk.palm('left')
    assert n[0] < -0.9 and k[1] < -0.9              # the left palm faces the midline, the knuckles run back to front
    n, _ = sk.palm('right')
    assert n[0] > 0.9
    D = P.solve(sk, P.library()['hand_fist'])
    for s, sx in (('left', -1), ('right', 1)):
        d = dirs(sk, D, s + 'IndexProximal')
        assert d[0] * sx > 0.9                       # the proximal phalanx turned 85 deg toward the palm


def test_spread_and_twist_signs():
    sk = skeleton()
    D = P.solve(sk, {'bones': {'IndexProximal': {'spread': 20}, 'LittleProximal': {'spread': 20}}})
    assert dirs(sk, D, 'leftIndexProximal')[1] < -0.3                              # the index toward the thumb (front)
    assert dirs(sk, D, 'leftLittleProximal')[1] > 0.3                              # the little away (back)
    # twist: internal rotation turns the arm's front toward the midline, mirrored per side
    D = P.solve(sk, {'bones': {'UpperArm': {'twist': 90}, 'LowerArm': {'bend': 90}}})
    assert dirs(sk, D, 'leftLowerArm')[0] < -0.8 and dirs(sk, D, 'rightLowerArm')[0] > 0.8


def test_turn_nod_tilt():
    sk = skeleton()
    D = P.solve(sk, {'bones': {'head': {'nod': 30}}})
    assert dirs(sk, D, 'head')[1] < -0.45                                           # the head bows forward
    D = P.solve(sk, {'bones': {'head': {'tilt': 30}}})
    assert dirs(sk, D, 'head')[0] > 0.45                                            # toward her left
    D = P.solve(sk, {'bones': {'spine': {'turn': 90}}})
    H, _ = P.posed_joints(sk, D)
    assert H['leftShoulder'][1] > 0.02 and H['rightShoulder'][1] < -0.02         # turning left: her right comes forward


def test_library_keys_name_bones():
    lib = P.library()
    assert 'rest' in lib and len(lib) >= 25
    allb = [b for b in VRM_PARENT]
    import fnmatch
    for name, pr in lib.items():
        assert pr.get('group') and pr.get('what'), name
        for key, ops in pr['bones'].items():
            assert set(ops) <= set(P.OPS), (name, key)
            assert any(b == key or fnmatch.fnmatchcase(P.bare(b), key) for b in allb), (name, key)


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f()
            print('ok', k)
