"""charkit.code_body's pieces with known answers (venv: run this file, or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import code_body as cb, garments as gm


def test_grid_faces_point_out():
    """a part's rings run down with columns round toward her left; its faces must face out (shells lift along the
    normals, the collar's ray finds the surface)."""
    th = -np.pi + (np.arange(24) + 0.5) * 2 * np.pi / 24
    z = np.linspace(0, -1, 6)
    P = np.stack([np.stack([np.sin(th) * 0.3, -np.cos(th) * 0.3, np.full(24, zz)], 1) for zz in z])
    V, F, FUV, UV, row = cb._grid(P, (0, 0, 1, 1), True, True)
    N = gm.vertex_normals(V, F)
    radial = V[:, :2] - V[:, :2].mean(0)
    side = np.linalg.norm(radial, axis=1) > 0.1
    assert (((radial * N[:, :2]).sum(1))[side] > 0).all()
    assert all(len(f) == len(q) for f, q in zip(F, FUV))


def test_blend_weights_sum_to_one_and_ease_at_the_joint():
    x = np.linspace(0, 2, 201)
    W = cb._blend(x, [1.0], 2)
    assert np.allclose(W.sum(1), 1)
    assert W[x < 1 - cb.BLEND, 0].min() == 1 and W[x > 1 + cb.BLEND, 1].min() == 1
    assert abs(W[100, 0] - 0.5) < 1e-9


def test_the_collars_back_flap_holds_the_torso_behind_it():
    """the collar is IN_FRONT only by its points behind the torso's axis, within the back view's drawn extent: the back
    flap caps the torso at its surface less the collar's depth; its lapels in front and a stray label below the flap
    don't (tool/garments3: the jacket beside the flap, labelled top by the sheet-only masks, had pulled the torso's back
    out through the flap)."""
    from charkit.geom import loft

    class Stub:
        def __init__(self, P):
            self.P = P

        def points(self, name):
            return self.P.get(name, np.zeros((0, 3)))

        shell_points = points

    ax = loft.Axis((0.0, 0.0, cb.CUT), (0, 0, -1), (0, -1, 0))
    nz, nth = 12, 72
    ts = np.linspace(0, 0.66, nz)
    th = -np.pi + (np.arange(nth) + 0.5) * 2 * np.pi / nth
    a = np.radians(np.linspace(150, 210, 13))
    flap = np.array([(0.30 * np.sin(x), -0.30 * np.cos(x), z) for x in a for z in (-0.62, -0.70, -0.78)])  # behind
    lapel = np.array([(0.20 * np.sin(x), -0.20 * np.cos(x), -0.62) for x in np.radians(np.linspace(-20, 20, 5))])
    stray = np.array([[0.30, 0.10, -0.95]])                          # behind, below the flap's drawn extent
    H = Stub({'collar': np.vstack([flap, lapel, stray])})
    B = cb._behind(H, ax, ts, th, nz, nth, drawn={'collar': (-0.4, -0.7, 0.4, -0.35)},
                   drawn_back={'collar': (-0.4, -0.91, 0.4, -0.5)})
    back = np.abs(np.abs(th) - np.pi) < np.radians(20)
    front = np.abs(th) < np.radians(40)
    CUT_ = cb.CUT
    rows = CUT_ - np.array([-0.62, -0.70, -0.78])
    ii = [int(np.argmin(np.abs(ts - r))) for r in rows]
    assert np.allclose(B[np.ix_(ii, np.nonzero(back)[0])], 0.30 - cb.IN_FRONT['collar'], atol=1e-6)
    assert np.isinf(B[:, front]).all()                               # the lapels don't cap the chest
    i_st = int(np.argmin(np.abs(ts - (CUT_ + 0.95))))
    assert 0 < i_st < nz - 1 and np.isinf(B[i_st]).all()             # the stray label below the flap doesn't count


def test_the_arm_pose_turns_the_forearm_out_and_mirrors():
    """body.arm (code_body.pose_arm): no knobs leave the hull's chain as it is; elbow_out turns the forearm and hand away
    from her side about the elbow in her frontal plane (the shoulder and elbow stay, the bones keep their lengths, the
    forearm's angle off vertical grows by the knob), the right arm mirroring the left; elbow_fwd swings them toward her
    front (-y); out turns the whole arm at the shoulder."""
    import math
    JL = np.array([[0.54, 0.1, -0.89], [0.75, 0.1, -1.38], [1.01, 0.1, -2.02], [1.13, 0.1, -2.30]])
    JR = JL * np.array([-1, 1, 1])
    assert np.allclose(cb.pose_arm(JL, 'left', None), JL) and np.allclose(cb.pose_arm(JL, 'left', {}), JL)
    off = lambda J: math.degrees(math.atan2(abs(J[2, 0] - J[1, 0]), J[1, 2] - J[2, 2]))
    L_ = cb.pose_arm(JL, 'left', {'elbow_out': 5.0})
    R_ = cb.pose_arm(JR, 'right', {'elbow_out': 5.0})
    assert np.allclose(L_[:2], JL[:2])
    assert np.allclose(np.linalg.norm(np.diff(L_, axis=0), axis=1), np.linalg.norm(np.diff(JL, axis=0), axis=1))
    assert abs(off(L_) - off(JL) - 5.0) < 1e-6 and L_[2, 0] > JL[2, 0]
    assert np.allclose(R_ * np.array([-1, 1, 1]), L_)
    F = cb.pose_arm(JL, 'left', {'elbow_fwd': 4.0})
    assert F[2, 1] < JL[2, 1] and np.allclose(F[:2], JL[:2])
    S = cb.pose_arm(JL, 'left', {'out': 3.0})
    assert np.allclose(S[0], JL[0]) and S[1, 0] > JL[1, 0] and S[3, 0] > JL[3, 0]


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok', name)


def _hull_dir(pieces):
    """a tiny hull folder: 8 points (two hair, two at the neckline, four down a bare torso), with or without pieces."""
    import json, tempfile
    from charkit.geom import io as gio
    from charkit.geom.mesh import Mesh
    d = tempfile.mkdtemp(prefix='charkit-hull-')
    V = np.array([[0, 0, 0.3], [0.1, 0, 0.3], [0.1, -0.2, -0.7], [-0.1, -0.2, -0.7], [0.8, -0.2, -1.6],
                  [-0.8, -0.2, -1.6], [0.7, 0.2, -2.4], [-0.7, 0.2, -2.4]], float)
    gio.save(Mesh(V, np.array([[0, 1, 2]])), os.path.join(d, 'hull.ply'))
    np.save(os.path.join(d, 'hull_labels.npy'), np.array([2, 2, 1, 1, 1, 3, 1, 1], np.int16))   # one underwear 'iris'
    J = dict(eyes=[[0.168, -0.5, 0], [-0.168, -0.5, 0]], labels='hull_labels.npy')
    if pieces:
        np.save(os.path.join(d, 'hull_pieces.npy'), np.array([1002, 1002, 1001, 1001, 5, 5, 5, 5]))
        J.update(pieces='hull_pieces.npy', piece_names={'5': 'top', '1001': 'skin', '1002': 'hair'})
    json.dump(J, open(os.path.join(d, 'hull.glb.json'), 'w'))
    return d


def test_a_hull_with_no_pieces_is_bare_skin_and_hair():
    """a base body's hull (carved with no pieces: manifest.body_hull) reads as the body's own surface: its hair 'hair',
    every other vertex 'skin' (an underwear colour too). Calibrated: it raised KeyError 'pieces' (2026-10-01)."""
    H = cb.Hull(_hull_dir(False))
    assert H.bare and set(H.ids) == {'skin', 'hair'}
    assert len(H.points('hair')) == 2 and len(H.points('skin')) == 6
    D = cb.Hull(_hull_dir(True))
    assert not D.bare and len(D.points('top')) == 4 and len(D.points('skin')) == 2


def test_a_bare_torso_is_measured_by_all_its_skin_a_dressed_one_by_its_neckline():
    """torso_skin: on a dressed hull the skin within TORSO_SKIN_X between -1.0 L and the cut (the tight pieces measure
    the rest); on a bare hull all of it from the cut down. Calibrated: a bare torso measured by its neckline was fitted
    as a narrow waist (shape IoU against the base body sheet 0.77 front, 0.89 with its skin)."""
    B, D = cb.Hull(_hull_dir(False)), cb.Hull(_hull_dir(True))
    assert len(cb.torso_skin(B, B.points('skin'))) == 6        # the neckline pair, the waist pair, the hips' pair
    Q = np.array([[0.1, -0.2, -0.7], [0.8, -0.2, -1.6], [0.1, -0.2, -1.2]])
    assert len(cb.torso_skin(D, Q)) == 1 and len(cb.torso_skin(B, Q)) == 3
