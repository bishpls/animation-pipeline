"""charkit.geom.hull on synthetic figures with known answers (venv: run this file, or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit.geom import hull

PPL, H = 60.0, 0.02


def figure():
    """a round figure: an elliptical torso (wider than deep) on two round legs, as occupancy on a fine grid (L)."""
    xs = np.arange(-1.0, 1.0, 0.01); ys = np.arange(-0.8, 0.8, 0.01); zs = np.arange(0.4, -3.2, -0.01)
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing='ij')
    torso = ((X / 0.45) ** 2 + ((Y - 0.05) / 0.28) ** 2 <= 1) & (Z <= 0.3) & (Z >= -1.6)
    legs = ((((X - 0.18) / 0.12) ** 2 + (Y / 0.12) ** 2 <= 1) | (((X + 0.18) / 0.12) ** 2 + (Y / 0.12) ** 2 <= 1)) & \
        (Z < -1.6) & (Z >= -3.0)
    return torso | legs, xs, ys, zs


def view(occ, xs, ys, zs, name, az, axis=300.0, eye_y=40.0):
    """the figure's orthographic picture at az (its mask, calibrated as the module expects)."""
    a = np.radians(az)
    ix, iy, iz = np.nonzero(occ)
    u = xs[ix] * np.cos(a) + ys[iy] * np.sin(a)
    c = np.round(axis + u * PPL).astype(int); r = np.round(eye_y - zs[iz] * PPL).astype(int)
    m = np.zeros((260, 600), bool)
    m[r, c] = True
    labels = np.zeros(m.shape, np.uint8)
    return hull.View(name, az, m, PPL, axis, eye_y, labels, np.zeros(m.shape + (3,)))


def test_the_round_prior_predicts_an_unseen_view():
    occ, xs, ys, zs = figure()
    views = {n: view(occ, xs, ys, zs, n, az) for n, az in (('front', 0), ('profile', 90), ('back', 180), ('three_quarter', 35))}
    A = hull.axes_for(views, H)
    use = ['front', 'profile', 'back']
    plain = hull.score(hull.carve(views, A, use), A, views['three_quarter'])['iou']
    prior = hull.score(hull.rounded(views, A, use, p=2.0, smooth=0.0), A, views['three_quarter'])['iou']
    assert prior > 0.93 and prior > plain + 0.03, (plain, prior)       # a round body: the ellipses predict it
    used = hull.score(hull.rounded(views, A, use, p=2.0, smooth=0.06), A, views['front'])['iou']
    assert used > 0.97, used                                            # smoothing keeps the drawn silhouettes


def test_refine_recovers_a_three_quarter_axis_error():
    occ, xs, ys, zs = figure()
    views = {n: view(occ, xs, ys, zs, n, az) for n, az in (('front', 0), ('profile', 90), ('back', 180), ('three_quarter', 35))}
    A = hull.axes_for(views, H)
    views['three_quarter'].axis -= 0.06 * PPL                            # the eyes' error: 0.06 L
    off = hull.refine(views, A, dict(p=2.0, smooth=0.0))
    assert abs(views['three_quarter'].axis - 300.0) <= 0.02 * PPL, (off, views['three_quarter'].axis)


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
