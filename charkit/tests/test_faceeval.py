"""The fast face evaluator's numpy parts on synthetic inputs (venv: run this file): the rasteriser, texture lookup and
pixel filter behind its eye renders, jittered check averaging, the vectorised head surface against the scalar one, and
the binned ray cast against the brute force."""
import math, os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import anime_head, faceeval, head


def test_raster_nearest_and_barycentric():
    # two triangles over one pixel grid: the nearer (smaller y) wins where both cover
    far = (np.array([[0, 1.0, 0], [4, 1.0, 0], [0, 1.0, -4]]), np.array([[0, 1, 2]]))
    near = (np.array([[0, 0.0, 0], [2, 0.0, 0], [0, 0.0, -2]]), np.array([[0, 1, 2]]))
    M, T, b1, b2 = faceeval.raster([far, near], 0.0, 0.0, 0.5, 8, 8)
    assert M[0, 0] == 1 and M[5, 1] == 0 and M[7, 7] == -1
    # pixel (0, 0)'s centre (0.25, -0.25) in the near triangle: b1 = x / 2, b2 = -z / 2
    assert abs(b1[0, 0] - 0.125) < 1e-9 and abs(b2[0, 0] - 0.125) < 1e-9


def test_sample_clip_and_blur():
    tex = np.zeros((4, 4, 1)); tex[:2] = 1.0                    # the top half (v > 0.5) white
    v = faceeval._sample(tex, np.array([[0.5, 0.9], [0.5, 0.1], [1.5, 0.5]]))[:, 0]
    assert v[0] == 1.0 and v[1] == 0.0 and v[2] == 0.0          # outside [0, 1]: the plates' CLIP
    img = np.zeros((16, 16, 1)); img[:, 8:] = 1.0
    out = faceeval._blur_down(img, 4, 0.5)
    assert out.shape == (4, 4, 1) and out[0, 0, 0] < 0.05 and out[0, 3, 0] > 0.95 and 0.2 < out[0, 2, 0] < 0.95


def test_mean_checks():
    runs = [{'a': {'value': 1.0, 'status': 'PASS', 'ratios': {'x': 1.0}}, 'b': {'value': 2.0, 'status': 'FAIL'}},
            {'a': {'value': 3.0, 'status': 'FAIL', 'ratios': {'x': 2.0}}}]
    m = faceeval.mean_checks(runs)
    assert m['a']['value'] == 2.0 and m['a']['ratios']['x'] == 1.5 and m['a']['status'] == 'PASS'
    assert m['b']['missing'] == 0.5


def test_vectorised_head_matches_scalar():
    H = head.Head(0.25, {'flat': 0.8, 'low_flat': 1.4, 'jaw_w': 1.3, 'chin_fwd': 1.2, 'nose_tip': 0.05})
    rng = np.random.default_rng(0)
    a = rng.uniform(-math.pi, math.pi, 200); z = rng.uniform(-H.chin, H.top, 200)
    P = H.surfaces(a, z)
    Q = np.array([H.surface(ai, zi) for ai, zi in zip(a, z)])
    assert np.abs(P - Q).max() < 1e-12
    x = rng.uniform(-0.3, 0.3, 50) * 0.25; zz = rng.uniform(-0.35, 0.2, 50) * 0.25
    A = anime_head.surface_azimuths(H, x, zz, hi=math.pi * 0.62)
    B = np.array([anime_head.surface_azimuth(H, xi, zi, hi=math.pi * 0.62) for xi, zi in zip(x, zz)])
    assert np.abs(A - B).max() < 1e-12


def test_nose_relief():
    H = head.Head(0.25, {'nose_tip': 0.06})
    L = H.L
    tip = H.nose_relief(0.0, -0.35 * L, H.nose_z)
    assert abs(tip - 0.06 * L) < 0.01 * L                       # about the knob at the tip, on the midline, in front
    assert H.nose_relief(0.1 * L, -0.3 * L, H.nose_z) < 1e-6 * L  # not on the cheek
    assert H.nose_relief(0.0, 0.4 * L, H.nose_z) == 0            # not at the back of the head
    assert H.nose_relief(0.0, -0.35 * L, H.mouth_z) < 1e-4 * L   # not at the mouth
    assert head.Head(0.25).nose_relief(0.0, -0.35 * L, H.nose_z) == 0


def test_binned_raycast_is_the_brute_force():
    H = head.Head(0.25, {'jaw_w': 1.2}, features=False)
    TV, TT = anime_head.target_mesh(H)
    O = np.array([0.0, 0.02, 0.0])
    rng = np.random.default_rng(1)
    D = rng.normal(size=(3000, 3)); D /= np.linalg.norm(D, axis=1, keepdims=True)
    fast = anime_head.raycast(O, D, TV, TT)
    v0 = TV[TT[:, 0]]
    slow = anime_head._hits(O, D, v0, TV[TT[:, 1]] - v0, TV[TT[:, 2]] - v0)
    assert np.array_equal(np.isfinite(fast), np.isfinite(slow)) and np.allclose(fast[np.isfinite(fast)], slow[np.isfinite(slow)])


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
