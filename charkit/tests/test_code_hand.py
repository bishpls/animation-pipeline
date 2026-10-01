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


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok', name)
