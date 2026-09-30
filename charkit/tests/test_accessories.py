"""charkit.accessories and charkit.accqa on synthetic fixtures with known answers (venv: run this file, or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import accessories, accqa


def test_star_outline_tips():
    R = accessories.star_outline(dict(up=0.5, down=0.6, side=0.3, minor=0.2, inner=0.1, curve=0.0, segs=2))
    r = np.hypot(R[:, 0], R[:, 1])
    assert abs(R[:, 1].max() - 0.5) < 1e-9 and abs(R[:, 1].min() + 0.6) < 1e-9 and abs(R[:, 0].max() - 0.3) < 1e-9
    assert abs(np.sort(r)[0] - 0.1) < 1e-9                                  # the valleys
    assert len(R) == 8 * 2 * 2                                              # 8 tips, 2 edges each, 2 segments an edge
    # four-point with concave edges: the edge's middle is pulled in, inside the straight edge's
    S = accessories.star_outline(dict(minor=0.0, curve=0.3, segs=4))
    S0 = accessories.star_outline(dict(minor=0.0, curve=0.0, segs=4))
    assert np.hypot(*S[2]) < np.hypot(*S0[2])


def test_star_mesh_faces_out():
    V, F = accessories.star()
    assert V[:, 2].min() == 0.0 and V[:, 2].max() > 0                     # its back on z = 0, facing +z
    apex = len(V) - 1
    n = [np.cross(V[f[1]] - V[f[0]], V[f[2]] - V[f[0]]) for f in F if f[0] == apex]
    assert all(x[2] > 0 for x in n)                                         # the front facets face +z


def test_crab_parts_and_materials():
    V, F, M = accessories.crab()
    assert len(F) == len(M) and set(np.unique(M)) == {0, 1}                # the shell and the eyes
    w = V[:, 0].max() - V[:, 0].min()
    assert 1.2 < w < 2.0                                                    # the claws reach past the 1-wide body
    assert abs(V[:, 0].max() + V[:, 0].min()) < 1e-9                       # symmetric


def test_place_rests_on_the_ground():
    # a flat ground at y = -1 (facing -y, the front); a clip 'at' the origin facing front is pushed out to rest on it
    g = np.array([[-5, -1.0, -5], [5, -1.0, -5], [5, -1.0, 5], [-5, -1.0, 5]])
    V, F = accessories.star()
    V = V / (V[:, 1].max() - V[:, 1].min())
    s = dict(kind='star', at=[0.0, -0.5, 0.0], facing=[0.0, 0.0], size=0.5, lift=0.0)
    w = accessories.place(V, s, 1.0, centre=np.zeros(3), ground=accessories.Ground([(g, [(0, 1, 2, 3)])]))
    assert abs(w[:, 1].max() - (-1.0)) < 1e-6                              # its back on the plane, in front of it
    assert abs((w[:, 2].max() - w[:, 2].min()) - 0.5) < 1e-6              # its height: size L
    s['lift'] = 0.1
    w2 = accessories.place(V, s, 1.0, centre=np.zeros(3), ground=accessories.Ground([(g, [(0, 1, 2, 3)])]))
    assert abs(w2[:, 1].max() - (-1.1)) < 1e-6


def test_star_rings_keep_its_surface():
    V1, F1 = accessories.star()
    V, F = accessories.star(dict(rings=4))
    S = accessories.STAR
    m = len(accessories.star_outline())
    assert np.array_equal(V[:2 * m], V1[:2 * m]) and np.array_equal(V[-2:], V1[-2:])   # the rim, the centres kept
    assert len(V) == 2 * m + 2 * 3 * m + 2 and len(F) == m * (3 + 2 * 3)
    R = np.hypot(V1[:m, 0], V1[:m, 1])
    for j in range(3):                                      # every ring on its facet's plane: th + dp (1 - share)
        f = 1 - (j + 1) / 4
        back, front = V[2 * m + j * m:2 * m + (j + 1) * m], V[2 * m + (3 + j) * m:2 * m + (4 + j) * m]
        assert np.allclose(np.hypot(back[:, 0], back[:, 1]), f * R) and np.allclose(back[:, 2], 0)
        assert np.allclose(front[:, 2], S['thick'] + S['depth'] * (1 - f))
    n = [np.cross(V[q[1]] - V[q[0]], V[q[2]] - V[q[0]]) for q in F if len(q) == 4 and q[0] >= 2 * m + 3 * m]
    assert n and all(x[2] > 0 for x in n)                   # the front bands face +z as the facets do


def test_conform_bends_over_the_clip_under_it():
    # a flat ground at y = -1 (facing -y), a block on it under the star's lower half: a star listed after the block
    # rests on the block (floats over the ground); with conform it rests on the ground and bends over the block
    g = (np.array([[-5, -1.0, -5], [5, -1.0, -5], [5, -1.0, 5], [-5, -1.0, 5]]), [(0, 1, 2, 3)])
    bv, bf = accessories.rounded_box(0.3, 0.3, 0.1, 0.02, segs=2)
    bv = bv @ np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0.0]]).T + np.array([0.0, -1.05, -0.2])  # 0.1 deep along -y
    star = dict(kind='star', at=[0.0, -0.5, 0.0], facing=[0.0, 0.0], size=1.0)
    blk = lambda: [(bv, bf)]

    def gen(s):
        G = accessories.Ground([g]); nh = 1
        G.add(*blk()[0])
        V, F = accessories.star(dict(rings=8) if s.get('conform') else None)
        V = V / (V[:, 1].max() - V[:, 1].min())
        if s.get('conform'):
            gh = accessories.Ground(); gh.meshes = G.meshes[:nh]
            w, Rm = accessories.place(V, s, 1.0, centre=np.zeros(3), ground=gh, frame=True)
            m = len(accessories.star_outline(dict(rings=8)))
            return accessories.conform(w, Rm, np.arange(m), G.meshes[nh:], 1.0, reach=0.2, clear=0.01)
        return accessories.place(V, s, 1.0, centre=np.zeros(3), ground=G), 0.0
    w0, _ = gen(star)
    assert abs(w0[:, 1].max() - (bv[:, 1].min())) < 1e-6         # rigid: its back on the block, 0.1 over the ground
    w, lift = gen(dict(star, conform=True))
    assert abs(w[:, 1].max() - (-1.0)) < 1e-6                     # conformed: its back's top still on the ground
    assert 0.1 < lift < 0.13                                       # bent over the block (0.1 deep, + clear)
    V, F = accessories.star(dict(rings=8)); m = len(accessories.star_outline())
    back = np.r_[np.arange(m), 2 * m + np.arange(7 * m), len(V) - 2]
    t = accessories.Ground(blk()).cast(w[back], np.array([0, 1.0, 0]), 1.0)     # down (+y) from its back to the block
    over = np.isfinite(t)
    assert over.sum() > 20 and (t[over] >= 0.01 - 1e-6).all()                   # clear of the block wherever over it
    top = w[back, 2] > 0.2                                         # its upper half, away from the block, not lifted
    assert np.allclose(w[back][top, 1], -1.0, atol=1e-6)


def _canvas():
    rgb = np.full((200, 300, 3), 0.8)                                       # grey paper
    rgb[20:180, 20:280] = (0.84, 0.48, 0.33)                                # hair, lit
    rgb[110:180, 20:280] = (0.66, 0.33, 0.22)                               # and in shade
    yy, xx = np.mgrid[0:200, 0:300]
    rgb[(yy - 60) ** 2 + (xx - 200) ** 2 < 15 ** 2] = (0.98, 0.86, 0.47)    # a yellow disc: the star
    rgb[(yy - 60) ** 2 + (xx - 150) ** 2 < 10 ** 2] = (0.83, 0.38, 0.26)    # a red disc: the crab
    return rgb


def test_design_clips_by_colour():
    pieces = {'pin_star': dict(srgb=np.array([0.988, 0.875, 0.451])), 'pin_crab': dict(srgb=np.array([0.886, 0.376, 0.267]))}
    win = dict(x=1.5, top=1.0, bottom=-1.0)                                 # 300 x 200 at 100 px/L round (150, 100)
    m, info = accqa.design_clips(_canvas(), 100.0, pieces, (), win)
    star, crab = m['pin_star'], m['pin_crab']
    assert abs(star.sum() - np.pi * 15 ** 2) < 60 and abs(crab.sum() - np.pi * 10 ** 2) < 40
    M = accqa.measure(star, 100.0, win)
    assert abs(M['u'] - 0.5) < 0.01 and abs(M['z'] - 0.4) < 0.01          # (200, 60) px from (150, 100)


def test_shape_iou_ignores_place_and_scale():
    a = np.zeros((100, 100), bool); a[20:40, 30:70] = True
    b = np.zeros((300, 300), bool); b[100:160, 50:170] = True               # 3x, moved
    assert accqa.shape_iou(a, b) > 0.93                                     # (resampling a 20 px edge)
    c = np.zeros((300, 300), bool); c[50:170, 100:160] = True               # turned 90 degrees
    assert accqa.shape_iou(a, c) < 0.5


def test_measure_angle_and_triangulate():
    m = np.zeros((200, 200), bool)
    yy, xx = np.mgrid[0:200, 0:200]
    m[np.abs((xx - 100) - 0.3 * (100 - yy)) < 5] = True                     # a bar leaning right at the top
    m[:40] = m[160:] = False
    ang = accqa.measure(m, 100.0, dict(x=1.0, top=1.0, bottom=-1.0))['angle']
    assert abs(ang - np.degrees(np.arctan(0.3))) < 1.0
    P = np.array([0.3, 0.2, 0.4]); a = 36.0
    M = {'front': dict(px=1, u=P[0], z=P[2]), 'profile': dict(px=1, u=P[1], z=P[2]),
         'three_quarter': dict(px=1, u=P[0] * np.cos(np.radians(a)) + P[1] * np.sin(np.radians(a)), z=P[2])}
    xyz, res = accqa.triangulate(M, a)
    assert np.allclose(xyz, P) and res < 1e-9


def test_window_to_grid_and_reclass():
    from charkit.bodyqa import WIN as BW
    ppl, eye = 20.0, (100.3, 80.6)
    m = np.zeros((int(round((accqa.WIN['top'] - accqa.WIN['bottom']) * ppl)), int(round(2 * accqa.WIN['x'] * ppl))), bool)
    m[5, 7] = True
    g = accqa.window_to_grid(m, eye, ppl)
    # the same sheet pixel: crop()'s origin in each window
    sheet_px = (7 + int(round(eye[0] - accqa.WIN['x'] * ppl)), 5 + int(round(eye[1] - accqa.WIN['top'] * ppl)))
    r, c = np.argwhere(g)[0]
    assert (c + int(round(eye[0] - BW['x'] * ppl)), r + int(round(eye[1] - BW['top'] * ppl))) == sheet_px
    dv = {'front': dict(cls=np.full(g.shape, 2), raw=np.full(g.shape, 2), fg=np.ones(g.shape, bool))}
    out = accqa.reclass(dv, {'front': {'pin_crab': g}})
    assert out['front']['cls'][r, c] == accqa.ACCESSORY and (out['front']['cls'] == 2).sum() == g.size - 1
    assert dv['front']['cls'][r, c] == 2                                    # the input untouched


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)


def test_hair_by_outside_sign_is_tie_free():
    """the shared hair selection's signed distance takes the pseudo-normal at the nearest feature: a point just outside a
    cube's edge or corner is outside whichever face the BVH reaches first (evalmesh R3: the face's own normal flipped
    1,804 of 75,006 hull vertices at such ties)."""
    import numpy as np
    from charkit.bodyeval import hair_by_outside
    s = 0.5
    V = np.array([(x, y, z) for x in (-s, s) for y in (-s, s) for z in (-s, s)], float)
    F = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    # points just outside the +x+y edge and the +x+y+z corner, and one inside
    P = np.array([(s + 0.02, s + 0.02, 0.0), (s + 0.02, s + 0.02, s + 0.02), (0.0, 0.0, 0.0)], float)
    C = np.full((len(P), 3), 0.5)
    hv, hf = hair_by_outside(P, C, np.array([(0, 1, 2)]), V, F, chin_z=-10.0, shoulder_x=10.0, clear=0.01, grow=0)
    # the face (0, 1, 2) needs all three kept to survive: the inside point isn't, so nothing is
    assert len(hf) == 0
    hv, hf = hair_by_outside(P[:2], C[:2], np.array([(0, 1, 1)]), V, F, chin_z=-10.0, shoulder_x=10.0, clear=0.01, grow=0)
    assert len(hv) == 2 and len(hf) == 1
