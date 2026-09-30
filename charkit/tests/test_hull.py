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


def labelled_view(lab, xs, ys, zs, name, az, P, axis=300.0, eye_y=40.0, shape=(200, 600)):
    """a view of a labelled figure: its mask and, per pixel, the label nearest the camera."""
    a = np.radians(az)
    ix, iy, iz = np.nonzero(lab)
    u = xs[ix] * np.cos(a) + ys[iy] * np.sin(a)
    dep = xs[ix] * np.sin(a) - ys[iy] * np.cos(a)
    c = np.round(axis + u * PPL).astype(int); r = np.round(eye_y - zs[iz] * PPL).astype(int)
    o = np.argsort(dep)                                    # nearest the camera written last
    pieces = np.zeros(shape, np.int16)
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



def side_pieces():
    return hull.Pieces({'pieces': [{'id': 'cuff_L', 'side': 'L', 'pair': 'cuff', 'attach': {'bone': 'leftLowerArm'}},
                                   {'id': 'boot_L', 'side': 'L', 'pair': 'boot', 'attach': {'bone': 'leftLowerLeg'}},
                                   {'id': 'skirt', 'side': 'C', 'attach': {'bone': 'hips'}},
                                   {'id': 'collar', 'side': 'C', 'attach': {'bone': 'upperChest'}}]})


def test_free_skin_takes_the_limb_of_the_piece_it_touches():
    """a profile's free skin, split by the drawn lines: a hand under its cuff (arm), a thigh over its boot (leg), a
    neck under the collar (body), the hand drawn against the thigh (split by the hand's outline: each its own), skin
    touching both a cuff and a boot (ambiguous), a speck of skin ringed by a line inside the thigh (its nearest
    component's), and a shin a crease cuts from everything but its boot's (the cut-off part: nothing places it)."""
    from charkit.bodyqa import CLASS
    P = side_pieces()
    H, W = 120, 100
    mask = np.zeros((H, W), bool); mask[5:115, 10:90] = True
    labels = np.where(mask, CLASS['orange'], 0).astype(np.uint8)
    pieces = np.zeros((H, W), np.int16)
    raw = labels.copy()

    def skin(r0, r1, c0, c1):
        labels[r0:r1, c0:c1] = CLASS['skin']; raw[r0:r1, c0:c1] = CLASS['skin']
    pieces[20:30, 10:30] = 1; skin(30, 50, 10, 30)                      # cuff, the hand under it
    skin(50, 52, 10, 30); raw[50:52, 10:30] = CLASS['line']             # the hand's outline
    skin(52, 70, 10, 30); pieces[70:80, 10:30] = 2                     # a thigh under it, over its boot
    raw[59:62, 19:22] = CLASS['line']; raw[60, 20] = CLASS['skin']                         # a speck in the thigh
    skin(90, 112, 10, 30); pieces[112:115, 10:30] = 2                  # a shin over its boot, cut by a crease
    raw[100:102, 10:30] = CLASS['line']
    pieces[5:10, 40:60] = 4; skin(10, 20, 40, 60)                      # the collar, the neck under it
    pieces[40:50, 40:60] = 1; skin(50, 60, 40, 60); pieces[60:70, 40:60] = 2   # between a cuff and a boot
    pieces[80:115, 40:90] = 3; skin(85, 100, 60, 80); pieces[85:100, 60:80] = 0   # skin inside the skirt: no seed
    labels[80:90, 10:30] = CLASS['orange']; raw[80:90, 10:30] = CLASS['orange']
    v = hull.View('profile', 90, mask, 50.0, 50.0, 10.0, labels, np.zeros((H, W, 3)))
    v.pieces, v.raw = pieces, raw
    L = hull.limb_image(v, P)
    assert (L[32:48, 12:28] == hull.ARM).all(), 'the hand under its cuff'
    assert (L[54:68, 12:28] == hull.LEG).all(), 'the thigh over its boot'
    assert L[60, 20] == hull.LEG, 'the speck: its nearest component\'s'
    assert (L[103:110, 12:28] == hull.LEG).all() and (L[92:98, 12:28] == hull.FREE_SKIN).all(), 'the crease\'s two sides'
    assert (L[12:18, 42:58] == hull.CORE).all(), 'the neck under the collar'
    assert (L[52:58, 42:58] == hull.FREE_SKIN).all(), 'touching a cuff and a boot: ambiguous'
    assert (L[88:98, 62:78] == hull.FREE_SKIN).all(), 'touching only the skirt: nothing places it'
    assert (L[50:52, 12:28] != hull.CORE).all(), 'the outline between hand and thigh is one of theirs'


def test_a_limb_track_keeps_the_limb_and_interpolates_what_is_hidden():
    """one limb in a side view: skin at heights 0-9 (y 10-15) and 30-39 (y 12-19), a piece of it at 20-24 on the skin's
    track (y 11-16) and a decoy of its pieces far in front (y 0-5) at 5-9 and 20-24; nothing at 25-29; the front shows
    only this limb at 40-44 (the whole side row counts)."""
    ny, nz = 30, 45
    E = np.zeros((ny, nz), bool); skin = np.zeros((ny, nz), bool)
    skin[10:16, 0:10] = True; skin[12:20, 30:40] = True
    E |= skin
    E[11:17, 20:25] = True                                             # the limb's own piece
    E[0:6, 5:10] = True; E[0:6, 20:25] = True                          # a decoy: a piece mask on another garment
    E[5:25, 26:28] = True                                              # a puff: a piece much deeper than the skin
    side_runs = [[(0, 25)] if k >= 40 else [(0, 29)] for k in range(nz)]
    only = [k >= 40 for k in range(nz)]
    width = [6] * nz
    width[26] = width[27] = 12                                         # the puff is wide in front too
    T = hull.LimbTrack(E, skin, side_runs, only, width, window=3)
    assert T.at(3) == ([(10, 15)], 'limb')
    assert T.at(7) == ([(10, 15)], 'limb') and T.rejected[7] == [(0, 5)], (T.at(7), T.rejected[7])
    runs, src = T.at(22)
    assert src == 'piece' and T.rejected[22] == [(0, 5)] and runs[0][0] >= 10 and runs[-1][1] <= 20, (runs, src)
    runs, src = T.at(27)                                               # the puff holds the track: it counts
    assert src == 'piece' and runs[0][0] <= 5 and runs[-1][1] >= 24, (runs, src)
    T2 = hull.LimbTrack(E, skin, side_runs, only, [6] * nz, window=3)  # as deep, but narrow in front: a mask across the body
    assert T2.rejected[27] == [(5, 24)], T2.rejected[27]
    runs, src = T.at(29)                                               # between y 10-15 and 12-19, depth ~6-8
    assert src == 'interp' and len(runs) == 1 and 10 <= runs[0][0] <= 13 and 15 <= runs[0][1] <= 19, runs
    assert T.at(42) == ([(0, 25)], 'only')
    assert T.at(15)[1] == 'interp'


def test_a_hole_in_a_limb_is_the_limb():
    xs = np.arange(-1.0, 1.0, 0.01)
    parts = [(120, 130, hull.LEG), (131, 135, hull.CORE), (136, 150, hull.LEG)]      # all at x > 0
    assert hull._enclosed(parts, xs) == [(120, 150, hull.LEG)]
    parts = [(40, 60, hull.ARM), (61, 140, hull.CORE), (141, 160, hull.ARM)]         # the torso between two arms
    assert hull._enclosed(parts, xs) == parts


def test_a_piece_on_the_wrong_garment_does_not_move_the_limb():
    """the armed figure, with the profile's arm piece mask painted over the torso's front too (as Clawd's profile has
    the cuffs on the skirt's front panel): the arm keeps its own depth, from its skin."""
    from charkit.bodyqa import CLASS
    lab, xs, ys, zs = armed()
    P = hull.Pieces({'pieces': [{'id': 'cuff_L', 'side': 'L', 'pair': 'cuff', 'attach': {'bone': 'leftLowerArm'}},
                                {'id': 'top', 'side': 'C', 'attach': {'bone': 'chest'}}]})
    views = {n: labelled_view(lab, xs, ys, zs, n, az, P) for n, az in (('front', 0), ('profile', 90), ('back', 180), ('three_quarter', 35))}
    for v in views.values():                                           # the arm drawn as skin, the torso as cloth
        v.labels = np.where(v.pieces == 1, CLASS['skin'], np.where(v.mask, CLASS['orange'], 0)).astype(np.uint8)
        v.raw = v.labels.copy()
        v.pieces = np.where(v.pieces == 2, 2, 0).astype(np.int16)
    s = views['profile']
    rows = np.nonzero(s.labels == CLASS['skin'])[0]
    s.pieces[rows.min():rows.min() + 6][s.mask[rows.min():rows.min() + 6]] = 1       # a cuff at the top of the skin
    front = s.mask & (s.labels != CLASS['skin'])
    cols = np.nonzero(front.any(0))[0]
    decoy = front & (np.arange(s.mask.shape[1])[None, :] < cols.min() + 8)
    s.pieces[decoy] = 1                                                # the cuff's mask on the torso's front too
    for n in ('front', 'back'):
        views[n].pieces = np.where(views[n].labels == CLASS['skin'], 0, 2).astype(np.int16)
        views[n].pieces[~views[n].mask] = 0
    P.skeleton = {'leftLowerArm': np.array([[0.5, -0.2], [0.5, -1.8]]), 'rightLowerArm': np.array([[-0.5, -0.2], [-0.5, -1.8]]),
                  'spine': np.array([[0.0, 0.0], [0.0, -2.0]])}
    for v in views.values():
        v.limbs = hull.limb_image(v, P)
    A = hull.axes_for(views, H)
    use = ['front', 'profile', 'back']
    T = {}
    S = hull.sections(views, A, use, tracks=T)
    arm = [(k, ys, src) for k, x0, x1, t, ys, src in S if t == hull.ARM and A.xs[x0] > 0.3]
    assert arm and all(src in ('limb', 'piece', 'interp') for _, _, src in arm), {src for _, _, src in arm}
    for k, ys, src in arm:                                             # the arm is y -0.1..0.1
        assert A.ys[ys[0][0]] >= -0.16 and A.ys[ys[-1][1]] <= 0.16, (A.zs[k], [(A.ys[a], A.ys[b]) for a, b in ys], src)
    assert any(T[hull.ARM].rejected), 'the decoy is seen and set aside'
    split = hull.score(hull.rounded(views, A, use, smooth=0.0), A, views['three_quarter'])['iou']
    assert split > 0.93, split



def test_a_banded_view_carves_only_its_heights_and_fits_its_azimuth():
    """an extra view limited to a height band (View.zband) carves there and nowhere else, and fit_view finds the
    azimuth it was drawn at from its band's silhouette against the hull of the others."""
    occ, xs, ys, zs = figure()
    views = {n: view(occ, xs, ys, zs, n, az) for n, az in (('front', 0), ('profile', 90), ('back', 180))}
    A = hull.axes_for(views, H)
    V0 = hull.carve(views, A, list(views))
    empty = hull.View('blank', 135.0, np.zeros((260, 600), bool), PPL, 300.0, 40.0)
    empty.zband = (-1.6, 0.3)                                      # the torso's heights: an empty drawing there
    V = hull.carve(dict(views, blank=empty), A, list(views) + ['blank'])
    band = empty.band(A.zs)
    assert not V[:, :, band].any() and (V[:, :, ~band] == V0[:, :, ~band]).all()
    drawn = view(occ, xs, ys, zs, 'extra', 140.0)
    drawn.zband = (-1.6, 0.3)
    drawn.mask &= drawn.band((drawn.eye_y - np.arange(260)) / PPL)[:, None]
    drawn.az = 125.0                                               # its nominal angle, 15 degrees off
    fit = hull.fit_view(drawn, hull.rounded(views, A, list(views), p=2.0, smooth=0.0), A, 125.0)
    assert abs(fit['az'] - 140.0) <= 2.5 and fit['iou'] > 0.9, fit


def flapped():
    """hips in shorts on two bare legs, with a flap hanging behind each hip at the side, clear of the body in profile
    (Clawd's flap train), and boots: labels 1 flap_L (her left, +x), 2 flap_R, 3 shorts, 4 boots, 5 the legs' skin."""
    xs = np.arange(-1.0, 1.0, 0.01); ys = np.arange(-0.8, 0.8, 0.01); zs = np.arange(0.4, -3.2, -0.01)
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing='ij')
    hips = ((X / 0.45) ** 2 + ((Y - 0.05) / 0.28) ** 2 <= 1) & (Z <= 0.3) & (Z >= -1.6)
    legs = ((((X - 0.18) / 0.12) ** 2 + (Y / 0.12) ** 2 <= 1) | (((X + 0.18) / 0.12) ** 2 + (Y / 0.12) ** 2 <= 1)) & \
        (Z < -1.6) & (Z >= -3.0)
    flap = (np.abs(X) >= 0.3) & (np.abs(X) <= 0.6) & (Y >= 0.45) & (Y <= 0.6) & (Z <= -1.0) & (Z >= -2.2)
    lab = np.where(flap, np.where(X > 0, 1, 2), np.where(hips, 3, np.where(legs, np.where(Z < -2.6, 4, 5), 0)))
    return lab, xs, ys, zs


def test_a_flap_behind_the_hips_pairs_only_with_its_own_columns():
    """a flap hanging behind each hip at the side, clear of the body in profile: the front shows the flaps only at the
    sides, so the flaps' side run pairs with those columns (Owners), not the whole width. Paired with the whole width
    (as before) it made a slab behind the shorts and the thighs, whose underside the labels called skin (Clawd's thigh
    bulged back to it: tool/body's body_profile_leg_back)."""
    from charkit.bodyqa import CLASS
    lab, xs, ys, zs = flapped()
    P = hull.Pieces({'pieces': [{'id': 'flap_L', 'side': 'L', 'pair': 'flap', 'attach': {'bone': 'hips'}},
                                {'id': 'flap_R', 'side': 'R', 'pair': 'flap', 'attach': {'bone': 'hips'}},
                                {'id': 'shorts', 'side': 'C', 'attach': {'bone': 'hips'}},
                                {'id': 'boots', 'side': 'C', 'attach': {'bone': 'leftLowerLeg'}}],
                     'skeleton': {'leftUpperLeg': [[0.18, -1.6], [0.18, -3.0]], 'rightUpperLeg': [[-0.18, -1.6], [-0.18, -3.0]],
                                  'spine': [[0.0, 0.3], [0.0, -1.5]]}})
    P5 = hull.Pieces({'pieces': [{'id': str(i)} for i in range(5)]})       # the legs drawn as a label, then skin
    views = {}
    for n, az in (('front', 0), ('profile', 90), ('back', 180), ('three_quarter', 35)):
        v = labelled_view(lab, xs, ys, zs, n, az, P5, shape=(260, 600))
        skin = v.pieces == 5
        v.labels = np.where(skin, CLASS['skin'], np.where(v.mask, CLASS['orange'], 0)).astype(np.uint8)
        v.raw = v.labels.copy()
        v.pieces = np.where(skin, 0, v.pieces).astype(np.int16)
        v.limbs = hull.limb_image(v, P)
        v.partner = P.mirror
        views[n] = v
    assert (views['profile'].limbs[views['profile'].labels == CLASS['skin']] == hull.LEG).all()
    A = hull.axes_for(views, H)
    use = ['front', 'profile', 'back']
    T = {}
    S = hull.sections(views, A, use, tracks=T)
    assert T['owners'].log, 'the flaps\' run is kept to their columns'
    V = hull.rounded(views, A, use, smooth=0.0)
    ix = lambda x: int(np.argmin(np.abs(A.xs - x))); iy = lambda y: int(np.argmin(np.abs(A.ys - y)))
    for z in (-1.2, -1.5, -1.8):                                        # the hips, and the thighs under the flaps
        k = int(np.argmin(np.abs(A.zs - z)))
        assert not V[ix(-0.2):ix(0.2) + 1, iy(0.42):, k].any(), z       # nothing behind the middle
        assert V[ix(0.5), iy(0.52), k] and V[ix(-0.5), iy(0.52), k], z  # each flap where it hangs
    held = hull.score(V, A, views['three_quarter'])['iou']
    assert held > 0.84, held            # paired with the whole width: 0.838; with the front's columns (the flaps' inner
                                        # halves hidden behind the hips): 0.822; the back sees them whole: 0.842


def test_the_refined_axis_does_not_move_with_the_limb_labels():
    """the three-quarter's axis is refined against the silhouettes' hull alone: the same with the limb split as without
    it (the outfit masks' limb labels once moved it half a voxel, which turned the hair's flyaways)."""
    lab, xs, ys, zs = armed()
    P = arm_pieces()
    got = []
    for with_pieces in (True, False):
        views = {n: labelled_view(lab, xs, ys, zs, n, az, P) for n, az in (('front', 0), ('profile', 90), ('back', 180),
                                                                             ('three_quarter', 35))}
        if not with_pieces:
            for v in views.values():
                v.pieces = v.limbs = None
        A = hull.axes_for(views, H)
        views['three_quarter'].axis -= 0.04 * PPL
        got.append(hull.refine(views, A, dict(p=2.0, smooth=0.0)))
    assert got[0] == got[1] and abs(got[0]['three_quarter'] - 0.04) <= 0.02, got


def test_the_sidecar_carries_the_contract_version():
    """docs/HULL_CONTRACT.md: the sidecar names its contract version; one written before the field reads as 1."""
    import json, tempfile
    from charkit import i3d
    J = hull.sidecar(0.168, -0.23, labels='hull_labels.npy')
    assert J['contract'] == hull.CONTRACT and hull.contract_of(J) == hull.CONTRACT and J['units'] == 'L', J
    assert J['eyes'][0][0] > 0 and J['eyes'][0][2] == 0.0 and J['labels'] == 'hull_labels.npy', J
    assert hull.contract_of({'eyes': J['eyes']}) == 1
    d = tempfile.mkdtemp()
    glb = os.path.join(d, 'hull.glb')
    json.dump(J, open(glb + '.json', 'w'))
    assert hull.contract_of(glb + '.json') == hull.CONTRACT
    L, R = i3d.glb_eyes(glb, np.zeros((3, 3)), np.zeros((3, 3)))
    assert L[0] > 0 > R[0]


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
