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



def armed():
    """a deep torso with an arm touching its side in front and drawn over it in profile: labels 1 arm, 2 torso."""
    xs = np.arange(-0.9, 0.9, 0.01); ys = np.arange(-0.7, 0.7, 0.01); zs = np.arange(0.2, -2.2, -0.01)
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing='ij')
    torso = ((X / 0.4) ** 2 + (Y / 0.5) ** 2 <= 1) & (Z <= 0.0) & (Z >= -2.0)
    arm = (((X - 0.5) / 0.1) ** 2 + (Y / 0.1) ** 2 <= 1) & (Z <= -0.2) & (Z >= -1.8)
    lab = np.where(arm, 1, np.where(torso, 2, 0))
    return lab, xs, ys, zs


def labelled_view(lab, xs, ys, zs, name, az, P, axis=300.0, eye_y=40.0):
    """a view of a labelled figure: its mask and, per pixel, the label nearest the camera."""
    a = np.radians(az)
    ix, iy, iz = np.nonzero(lab)
    u = xs[ix] * np.cos(a) + ys[iy] * np.sin(a)
    dep = xs[ix] * np.sin(a) - ys[iy] * np.cos(a)
    c = np.round(axis + u * PPL).astype(int); r = np.round(eye_y - zs[iz] * PPL).astype(int)
    o = np.argsort(dep)                                    # nearest the camera written last
    pieces = np.zeros((200, 600), np.int16)
    pieces[r[o], c[o]] = lab[ix, iy, iz][o]
    v = hull.View(name, az, pieces > 0, PPL, axis, eye_y, np.zeros(pieces.shape, np.uint8), np.zeros(pieces.shape + (3,)))
    v.pieces = pieces
    v.limbs = hull.limb_image(v, P)
    return v


def arm_pieces():
    return hull.Pieces({'pieces': [{'id': 'sleeve_L', 'side': 'L', 'pair': 'sleeve', 'attach': {'bone': 'leftUpperArm'}},
                                   {'id': 'top', 'side': 'C', 'attach': {'bone': 'chest'}},
                                   {'id': 'sleeve_R', 'side': 'R', 'pair': 'sleeve', 'attach': {'bone': 'rightUpperArm'}}]})


def test_a_limb_touching_the_body_takes_its_own_depth():
    lab, xs, ys, zs = armed()
    P = arm_pieces()
    views = {n: labelled_view(lab, xs, ys, zs, n, az, P) for n, az in (('front', 0), ('profile', 90), ('back', 180), ('three_quarter', 35))}
    A = hull.axes_for(views, H)
    use = ['front', 'profile', 'back']
    one = hull.score(hull.rounded(views, A, use, smooth=0.0, limbs=False), A, views['three_quarter'])['iou']
    split = hull.score(hull.rounded(views, A, use, smooth=0.0), A, views['three_quarter'])['iou']
    assert split > 0.93 and split > one + 0.03, (one, split)          # one run: the arm took the torso's depth


def test_the_labels_predict_a_held_out_view():
    lab, xs, ys, zs = armed()
    P = arm_pieces()
    views = {n: labelled_view(lab, xs, ys, zs, n, az, P) for n, az in (('front', 0), ('profile', 90), ('back', 180), ('three_quarter', 35))}
    A = hull.axes_for(views, H)
    V = hull.rounded(views, A, list(views), smooth=0.0)
    S, L = hull.validate_labels(V, A, views, P)
    assert S['held_out']['three_quarter']['agree'] > 0.95, S['held_out']['three_quarter']
    assert S['used']['front']['labels']['sleeve_L']['iou'] > 0.85, S['used']['front']['labels']


def test_a_mirrored_view_swaps_sides():
    P = arm_pieces()
    assert list(P.mirror) == [0, 3, 2, 1] and list(P.limb) == [hull.CORE, hull.ARM, hull.CORE, hull.ARM]
    pieces = np.zeros((4, 10), np.int16); pieces[1, 2] = 1; pieces[2, 7] = 2
    v = hull.View('profile', 90, pieces > 0, PPL, 3.0, 1.0, np.zeros(pieces.shape, np.uint8), np.zeros(pieces.shape + (3,)))
    v.pieces = pieces; v.limbs = hull.limb_image(v, P)
    m = hull.mirrored(v, P)
    assert m.az == 270.0 and m.axis == 6.0 and m.pieces[1, 7] == 3 and m.pieces[2, 2] == 2
    assert hull._split(np.array([0, 0, 0, 0, 1, 0, 0, 1, 1, 1, 1]), 2) == [(0, 6, 0), (7, 10, 1)]


def test_a_glb_sidecar_gives_its_eyes_exactly():
    import json, tempfile
    from charkit import i3d
    d = tempfile.mkdtemp()
    glb = os.path.join(d, 'x.glb')
    open(glb, 'wb').write(b'')
    json.dump({'eyes': [[0.168, -0.23, 0.0], [-0.168, -0.23, 0.0]]}, open(glb + '.json', 'w'))
    L, R = i3d.glb_eyes(glb, np.zeros((3, 3)), np.zeros((3, 3)))
    assert np.allclose(L, [0.168, -0.23, 0]) and np.allclose(R, [-0.168, -0.23, 0])


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
