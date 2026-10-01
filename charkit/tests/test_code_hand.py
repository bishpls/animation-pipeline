"""charkit.code_hand's hand template with known answers (venv: run this file, or pytest)."""
import json, os, sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from charkit import code_body as cb, code_hand as ch


def _hands():
    P = ch.params(json.load(open(os.path.join(ROOT, 'charkit', 'spec', 'clawd.json'))))
    out = {}
    for side, s in (('left', 1.0), ('right', -1.0)):
        J = np.array([[0.5 * s, 0, -1.0], [0.6 * s, 0, -1.8], [0.65 * s, 0, -2.5], [0.67 * s, 0, -2.8]])
        out[side] = ch.hand(J, side, P)
    return out


def _volume(V, F):
    """a closed mesh's signed volume (quads and fan triangles split from their first corner): + when its faces point out."""
    V = np.asarray(V, float)
    tot = 0.0
    for f in F:
        for k in range(1, len(f) - 1):
            tot += np.dot(V[f[0]], np.cross(V[f[k]], V[f[k + 1]]))
    return tot / 6


def test_every_part_faces_out_on_both_hands():
    """each part's faces point out, as the body's limbs do (b1's right hand was inside out: the frame is mirrored
    there, which turned its rings the other way; its outline hull went inside the skin). The sign of a part's volume
    through code_body._grid against a cylinder whose faces point out (test_code_body.test_grid_faces_point_out's)."""
    th = -np.pi + (np.arange(24) + 0.5) * 2 * np.pi / 24
    P = np.stack([np.stack([np.sin(th) * 0.3, -np.cos(th) * 0.3, np.full(24, zz)], 1) for zz in np.linspace(0, -1, 6)])
    V, F, _, _, _ = cb._grid(P, (0, 0, 1, 1), True, True)
    ref = np.sign(_volume(V, F))
    assert ref != 0
    for side, H in _hands().items():
        for name in ch.PARTS:
            V, F, _, _, _ = cb._grid(H['parts'][name][0], (0, 0, 1, 1), True, True)
            assert np.sign(_volume(V, F)) == ref, (side, name)


def test_no_face_folds_over():
    """every quad between two rings faces away from the digit's axis there (b1's left hand folded over at each knuckle:
    the knuckle loops' frames were right-handed between its mirrored segment frames, so their rings ran the other way
    round: knobs, back faces showing)."""
    for side, H in _hands().items():
        for name in ch.PARTS:
            R = H['parts'][name][0]
            C = R.mean(1)
            a, b = R[:-1], R[1:]
            a2, b2 = np.roll(a, -1, 1), np.roll(b, -1, 1)
            n = np.cross(a2 - a, b - a) + np.cross(b - b2, a2 - b2)
            mid = (a + a2 + b + b2) / 4 - ((C[:-1] + C[1:]) / 2)[:, None]
            out = np.sign((n * mid).sum(-1))
            frac = (out == np.sign(out.sum())).mean()
            assert frac == 1.0, (side, name, frac)


def test_the_hands_mirror():
    """the right hand is the left mirrored in x (the template has no handedness of its own), weights alike."""
    H = _hands()
    for name in ch.PARTS:
        A, B = H['left']['parts'][name], H['right']['parts'][name]
        M = B[0][:, ::-1] * np.array([-1.0, 1.0, 1.0])
        assert np.allclose(np.sort(A[0].reshape(-1, 3), 0), np.sort(M.reshape(-1, 3), 0), atol=1e-9), name
        assert np.allclose(A[1], B[1]) and np.allclose(A[1].sum(1), 1)


def test_weights_valid_on_every_finger_bone():
    """each part's rings' weights sum to 1 and every one of the 15 finger bones per hand (30 in all) carries weight."""
    bones = set()
    for side, H in _hands().items():
        for name in ch.PARTS:
            rings, Wt, B = H['parts'][name]
            assert len(Wt) == len(rings) and np.allclose(Wt.sum(1), 1), (side, name)
            bones |= {b for i, b in enumerate(B) if Wt[:, i].max() > 0.5 and 'Hand' not in b}
    assert len(bones) == 30, sorted(bones)


def _along(J, f):
    """the point at arc-length share f along a chain of joints."""
    seg = np.linalg.norm(np.diff(J, axis=0), axis=1)
    s0 = np.r_[0.0, np.cumsum(seg)]
    return np.array([np.interp(f * s0[-1], s0, J[:, k]) for k in range(3)])


def test_fingers_held_together():
    """neighbouring fingers touch along their length (round 4: de2fa87's four tubes fanned apart read as a comb, the
    fingertips' gaps 0.11-0.18 of the hand's span where the drawn hands show none): across the hand (the palm's plane),
    the centre lines' distance at every station of the shorter finger is at most the two radii's sum (and a seam: a gap
    the outline fills, code_hand.SEAM_MAX), and the
    fingertips converge (the tips' span narrower than the knuckles')."""
    P = ch.params(json.load(open(os.path.join(ROOT, 'charkit', 'spec', 'clawd.json'))))
    for side, H in _hands().items():
        W, R = H['frame']
        D = H['digits']
        for a, b in zip(ch.FINGERS[:-1], ch.FINGERS[1:]):
            (Ja, _, wa), (Jb, _, wb) = D[a], D[b]
            for f in np.linspace(0.05, 0.95, 10):
                pa, pb = _along(Ja, f), _along(Jb, f)
                gap = abs((pa - pb) @ R[:, 1])
                ra = 0.5 * (wa[0] + (wa[1] - wa[0]) * f)
                rb = 0.5 * (wb[0] + (wb[1] - wb[0]) * f)
                assert gap <= ra + rb + ch.SEAM_MAX, (side, a, b, f, gap, ra + rb)
        across = lambda k: [D[n][0][k] @ R[:, 1] for n in ch.FINGERS]
        assert np.ptp(across(3)) < np.ptp(across(0)), side


def test_the_thumb_opens():
    """the thumb is its own prong (round 4: a nub folded against the palm, the drawn V cleft missing): its tip lies
    outside the palm's radial edge."""
    P = ch.params(json.load(open(os.path.join(ROOT, 'charkit', 'spec', 'clawd.json'))))
    for side, H in _hands().items():
        W, R = H['frame']
        tip = H['digits']['thumb'][0][-1]
        assert (tip - W) @ R[:, 1] > 0.5 * P['palm_w'], side


def test_fist_precheck():
    """a fist (80 deg per finger joint, the thumb 40) keeps the knuckle loops' section (>= 0.7 of rest) and adds
    little interpenetration between neighbours beyond what they share at rest (held together, overlapping by
    `overlap` of their width)."""
    for side, H in _hands().items():
        rep = ch.fist_report(H)
        assert min(rep['knuckle_area'].values()) >= 0.7, rep['knuckle_area']
        for k, v in rep['overlap'].items():
            assert v['deepest'] <= rep['rest_overlap'][k]['deepest'] + 0.006, (k, v, rep['rest_overlap'][k])


def test_ratio_mode_is_live():
    """the ratio mode (body.hand.palm_len): the hand built from its structural ratios at its size, derived when the hand
    is built (ratio2 moved palm_len to its bound with no effect: the knobs had been derived once at params())."""
    spec = json.load(open(os.path.join(ROOT, 'charkit', 'spec', 'clawd.json')))
    P = ch.params(spec, palm_len=0.3, wrist_offset=0.034)
    J = np.array([[0.5, 0, -1.0], [0.6, 0, -1.8], [0.65, 0, -2.5], [0.67, 0, -2.8]])
    tip = lambda P_: ch.hand(J, 'left', P_)['digits']['middle'][0][-1]
    a, b = tip(P), tip(dict(P, palm_len=0.35))
    assert np.linalg.norm(b - J[2]) > np.linalg.norm(a - J[2]) + 0.05
    R = dict(P['ratios'], middle=P['ratios']['middle'] * 1.2)
    c = tip(dict(P, ratios=R))
    assert np.linalg.norm(c - J[2]) > np.linalg.norm(a - J[2]) + 0.02
    G = ch.geometry(P)
    assert abs(G['palm_w'] - P['ratios']['span'] * 0.3) < 1e-9 and abs(G['palm'] * G['length'] - (0.034 + 0.3)) < 1e-9


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok', name)
