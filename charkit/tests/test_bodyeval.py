"""charkit.bodyeval and charkit.bodysens on synthetic fixtures with known answers (venv: run this file, or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import bodyeval, bodymeasure, bodysens


def grid_mesh(n=6, z=0.0):
    """an n x n vertex grid of quads in the xy plane."""
    xs, ys = np.meshgrid(np.arange(n, dtype=float), np.arange(n, dtype=float))
    V = np.stack([xs.ravel(), ys.ravel(), np.full(n * n, z)], 1)
    F = [(j * n + i, j * n + i + 1, (j + 1) * n + i + 1, (j + 1) * n + i) for j in range(n - 1) for i in range(n - 1)]
    return V, F


def test_knob_paths():
    spec = {'body': {'proportions': {'leg': 1.1}}, 'garments': [{'kind': 'skirt', 'name': 'skirt', 'flare': 40},
                                                                  {'kind': 'shell', 'name': 'top', 'cuts': [['hips', 0.0, 'above', 0.1]]}],
            'accessories': [{'kind': 'bun'}, {'kind': 'star', 'size': 0.16}]}
    assert bodyeval.get_knob(spec, 'garments.skirt.flare') == 40
    assert bodyeval.get_knob(spec, 'garments.top.cuts.0.3') == 0.1
    assert bodyeval.get_knob(spec, 'accessories.star.size') == 0.16
    assert bodyeval.get_knob(spec, 'body.proportions.hip', 'd') == 'd'
    S = bodyeval.with_knobs(spec, {'garments.skirt.flare': 30, 'body.proportions.hip': 0.9, 'accessories.1.size': 0.2,
                                   'garments.top.cuts.0.3': 0.2})
    assert S['garments'][0]['flare'] == 30 and S['body']['proportions']['hip'] == 0.9
    assert S['accessories'][1]['size'] == 0.2 and S['garments'][1]['cuts'][0][3] == 0.2
    assert spec['garments'][0]['flare'] == 40                                    # the original is untouched


def test_blender_smooth_is_the_midpoint_rule():
    V, F = grid_mesh(4)
    V[5, 2] = 1.0                                                                # one raised interior vertex (4 neighbours)
    S = bodyeval.blender_smooth(V, F, factor=0.5, iterations=1)
    # Blender: v' = v (1 - f) + f * mean of the edge midpoints = v + f/2 (mean of neighbours - v)
    assert abs(S[5, 2] - (1.0 + 0.25 * (0.0 - 1.0))) < 1e-12
    assert abs(S[1, 2] - 0.5 * 0.5 * (1.0 / 3.0)) < 1e-12                        # a border neighbour: 3 edges, one raised


def test_drop_small_parts_and_triangulate():
    V1, F1 = grid_mesh(5)                                                        # 16 quads
    V2, F2 = grid_mesh(2, z=5.0)                                                 # 1 quad
    V = np.vstack([V1, V2]); F = np.asarray(F1 + [tuple(i + len(V1) for i in f) for f in F2])
    T = bodyeval.triangulate(F)
    assert T.shape == (34, 3)
    v, f = bodyeval.drop_small_parts(V, T, 10)
    assert len(f) == 32 and np.all(v[:, 2] == 0)
    mixed = bodyeval.triangulate([(0, 1, 2), (0, 1, 2, 3), (0, 1, 2, 3, 4)])
    assert len(mixed) == 1 + 2 + 3


def test_bbox_norm_and_iou():
    a = np.zeros((100, 60), bool); a[10:90, 20:40] = True
    b = np.zeros((300, 300), bool); b[50:250, 100:150] = True                    # the same shape, scaled and moved
    assert bodymeasure.iou(bodymeasure.bbox_norm(a), bodymeasure.bbox_norm(b)) == 1.0


def test_pose_measures_known_angles():
    from charkit.geom.raster import Frame
    fr = Frame((0.0, 0.0, 1.0), 2.0, (400, 400))
    H, W = 400, 400
    z = bodymeasure._rows_z(fr)
    pix = 2.0 / H
    x = (np.arange(W) + 0.5 - W / 2) * pix
    m = np.zeros((H, W), bool)
    lm = dict(L=0.25, chin=1.6, waist=1.0, knee=0.5)
    t30, t5 = np.tan(np.radians(30)), np.tan(np.radians(5))
    for r in range(H):
        zz = z[r]
        if 1.0 < zz < 1.6:                                                        # a torso and two arms at 30 degrees
            m[r, np.abs(x) < 0.1] = True
            reach = 0.1 + (1.6 - zz) * t30
            m[r, (np.abs(x) > reach - 0.03) & (np.abs(x) < reach)] = True
        if 0.0 < zz < 0.5:                                                        # legs spreading 5 degrees, gap 0.1 at the knee
            c = 0.1 + (0.5 - zz) * t5
            m[r, np.abs(np.abs(x) - c) < 0.05] = True
    P = bodymeasure.pose_measures(m, fr, lm)
    assert abs(P['arm_angle'] - 30) < 1.0, P
    assert abs(P['leg_angle'] - 5) < 1.0, P
    # the gap between the inner edges, 0.1 + 2 (0.5 - z) tan 5, averaged over the rows 0.2 L .. 1.2 L below the knee
    assert abs(P['leg_gap'] - (0.1 + 2 * 0.175 * t5) / 0.25) < 0.03, P


def test_compose_carries_the_head_frame():
    """pure head vertices land on the old anime head moved by F (head centre, L); the body is the new body's."""
    from charkit import head as headlib
    rng = np.random.default_rng(1)
    n = 400
    V0 = rng.normal(size=(n, 3)) * 0.1
    hw = np.zeros(n); hw[:150] = 1.0; hw[150:200] = 0.3                         # a head, a neck blend, the body
    region = hw > 0.02
    Vo = V0.copy(); Vo[region] += rng.normal(size=(region.sum(), 3)) * 0.01     # the wrap moved the head region
    K = headlib._knobs({})
    L0, L1, s0, s1 = 0.25, 0.27, 1.0, 1.1
    t = np.array([0.0, 0.01, 0.2])
    V1 = s1 / s0 * V0 + t                                                        # the new body (a similarity everywhere)
    V1[200:] += rng.normal(size=(n - 200, 3)) * 0.02                             # ... but the body proper changed shape
    B0 = dict(verts=V0, head_w=hw, scale=s0, marks={'chin': np.zeros(3)})
    B1 = dict(verts=V1, head_w=hw, scale=s1, head_len=L1, joints={'a': np.zeros(3)}, weights={}, params={},
              marks={'chin': t})
    H0 = headlib.Head(L0, K)
    c0 = np.array([0.0, 0.0, H0.chin])
    A0 = dict(verts=Vo, faces=[], body=B0, joints={'a': np.zeros(3)}, weights={}, eyes=[],
              head=dict(L=L0, H=H0, centre=c0, info=dict(region=region, profile=[], target=(np.zeros((3, 3)), np.zeros((1, 3), int)))),
              mouth=dict(c=(0.0, c0[2]), teeth=(np.zeros((1, 3)), []), tongue=(np.zeros((1, 3)), []), line=(np.zeros((1, 3)), []),
                         keys={}, teeth_keys={}, line_keys={}, tongue_keys={}))
    A = bodyeval.compose(A0, None, B1)
    lam = L1 / L0
    c1 = A['head']['centre']
    assert abs(c1[2] - (t[2] + headlib.Head(L1, K).chin)) < 1e-12
    assert np.allclose(A['verts'][:150], c1 + lam * (Vo[:150] - c0), atol=1e-12)
    assert np.allclose(A['verts'][200:], V1[200:], atol=1e-12)                    # outside the wrap: the new body exactly


def test_cull_face_matches_scene():
    """the vectorised face cull against scene.cull_face on random points round a real anime head."""
    from charkit import head as headlib, scene
    L = 0.25
    H = headlib.Head(L, {})
    c = np.array([0.0, -0.03, 1.4])
    A = dict(head=dict(H=H, centre=c, L=L))
    rng = np.random.default_rng(3)
    P = c + rng.uniform([-0.3 * L, -0.5 * L, -0.5 * L], [0.3 * L, 0.2 * L, 0.3 * L], size=(160, 3))
    F = np.arange(160).reshape(-1, 1).repeat(3, 1)                              # one degenerate face per point
    v1, _ = bodyeval.cull_face(A, P, F, {})
    v2, _ = scene.cull_face(bodyeval._S({}, A), P, [tuple(f) for f in F], {})
    kept1 = {tuple(np.round(p, 9)) for p in v1}
    kept2 = {tuple(np.round(p, 9)) for p in v2}
    assert len(kept1 ^ kept2) <= 2, (len(kept1), len(kept2), len(kept1 ^ kept2))  # (the grid's interpolation at the edge)


def test_volume_cast_matches_numpy():
    from charkit import anime_head as ah, hair
    th, ph = np.meshgrid(np.linspace(0, np.pi, 24), np.linspace(0, 2 * np.pi, 48, endpoint=False), indexing='ij')
    V = np.stack([np.sin(th) * np.cos(ph), np.sin(th) * np.sin(ph), np.cos(th)], -1).reshape(-1, 3)
    idx = np.arange(24 * 48).reshape(24, 48)
    a, b = idx[:-1], np.roll(idx, -1, 1)[:-1]
    cc, d = idx[1:], np.roll(idx, -1, 1)[1:]
    T = np.concatenate([np.stack([a, cc, b], -1).reshape(-1, 3), np.stack([b, cc, d], -1).reshape(-1, 3)])
    D = np.random.default_rng(0).normal(size=(300, 3)); D /= np.linalg.norm(D, axis=1, keepdims=True)
    O = np.array([0.1, -0.05, 0.02])
    t1, t2 = ah.raycast(O, D, V, T), hair._cast_from(O, D, V, T)
    assert np.array_equal(np.isfinite(t1), np.isfinite(t2)) and np.allclose(t1, t2)


def test_inventory_covers_every_builder_knob():
    keys = bodysens.builder_keys()
    for kind, ks in keys.items():
        listed = {k.split('.')[0] for k in bodysens.GARMENT[kind]}
        missing = ks - listed - set(bodysens.NOT_KNOBS) - set(bodysens.COLOURS)
        assert not missing, (kind, missing)
    spec = {'body': {}, 'garments': [{'kind': k, 'name': k + '_x', 'side': 'left'} for k in bodysens.GARMENT],
            'hair': {'shape': {'glb': 'x.glb', 'mode': 'mesh', 'select': 'outside'}},
            'accessories': [{'kind': 'bun', 'az': 0, 'el': 60}, {'kind': 'star', 'az': 30, 'el': 30}]}
    K = bodysens.inventory(spec)
    paths = {k['path'] for k in K}
    for kind in bodysens.GARMENT:
        for k in bodysens.GARMENT[kind]:
            assert 'garments.%s_x.%s' % (kind, k) in paths
    assert 'body.proportions.leg' in paths and 'body.heads_tall' in paths and 'hair.shape.below' in paths
    assert any(p.startswith('hair.bangs.tips.') for p in paths)                   # the analytic locks, walked
    assert next(k for k in K if k['path'] == 'accessories.0.size')['kind'] == 'inactive'      # carried by the shape


def test_capabilities_flags_unmoved_measures():
    T = {'base': {'iou': 0.5, 'arm_angle': 12.0, 'leg_angle': 5.0, 'leg_gap': 0.001, 'bottom': 0.3, 'top': 0.2},
         'knobs': [dict(path='a', kind='geometry', value=1.0, step=0.1, lo=0.0, hi=2.0,
                        d={'iou': 0.05, 'arm_angle': 0.01, 'leg_angle': 1.0, 'bottom': -0.05, 'top': 0.001}),
                   dict(path='b', kind='geometry', value=1.0, step=0.1, lo=0.0, hi=2.0, d={'top': -0.01, 'bottom': 0.2})]}
    C = {c['measure']: c['status'] for c in bodysens.capabilities(T)}
    assert C['iou'] == 'left to the fit' and C['arm_angle'] == 'no knob moves it' and C['leg_gap'] == 'ok'
    assert C['leg_angle'] == 'no knob turns a limb'
    assert C['bottom'] == 'a knob reaches it'                 # 'b' closes bottom and costs little elsewhere ...
    assert C['top'] == 'only at a cost', C                    # ... but closing top with 'b' wrecks bottom


def test_subdivide_cube():
    """Catmull-Clark on a cube: a corner's vertex point is 5/9 and an edge's point (v0 + v1 + two face points) / 4."""
    V = np.array([[x, y, z] for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)], float)
    F = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    NV, Q, parent, _ = bodyeval.subdivide(V, F, limit=False)
    assert Q.shape == (24, 4) and len(NV) == 8 + 6 + 12 and sorted(set(parent.tolist())) == list(range(6))
    assert np.allclose(NV[0], [-5 / 9] * 3)
    edge = NV[8 + 6:]
    assert np.any(np.all(np.isclose(edge, [-0.75, -0.75, 0.0]), 1))
    NL, _, _, _ = bodyeval.subdivide(V, F, limit=True)                    # the limit surface lies further in
    assert np.linalg.norm(NL, axis=1).max() < np.linalg.norm(NV, axis=1).max()


def test_zsplat_is_faceqa_zbuffer():
    from charkit import faceqa
    V1, T1 = sphere(0.3, (0, 0, 0))
    V2, T2 = sphere(0.12, (0.1, -0.4, 0.05))
    meshes = [(V1, T1, np.full(len(T1), 1)), (V2, T2, np.full(len(T2), 2))]
    win = dict(x=0.5, top=0.5, bottom=-0.5)
    for az in (0.0, 37.0, 90.0):
        d1, l1 = faceqa.zbuffer(meshes, az, (0.0, 0.0), 1.0, 0.01, win)
        d2, l2 = bodymeasure.zsplat(meshes, az, (0.0, 0.0), 1.0, 0.01, win)
        assert (l1 != l2).sum() <= 2 and np.allclose(np.where(np.isfinite(d1), d1, 0), np.where(np.isfinite(d2), d2, 0))


def sphere(r, c, n=24):
    th, ph = np.meshgrid(np.linspace(0, np.pi, n), np.linspace(0, 2 * np.pi, 2 * n, endpoint=False), indexing='ij')
    V = r * np.stack([np.sin(th) * np.cos(ph), np.sin(th) * np.sin(ph), np.cos(th)], -1).reshape(-1, 3) + np.asarray(c)
    idx = np.arange(n * 2 * n).reshape(n, 2 * n)
    a, b = idx[:-1], np.roll(idx, -1, 1)[:-1]
    cc, d = idx[1:], np.roll(idx, -1, 1)[1:]
    return V, np.concatenate([np.stack([a, cc, b], -1).reshape(-1, 3), np.stack([b, cc, d], -1).reshape(-1, 3)])


def test_rest_pose_turns_the_limbs():
    """the pose knobs turn each bone by their angle in the frontal plane; at zero nothing moves."""
    from charkit import body, mh
    a = body.build_body_data({}, keep_head=True)
    b = body.build_body_data({'pose': {'arm_down': 10.0, 'leg_in': 4.0, 'elbow': 0.0}}, keep_head=True)
    c = body.build_body_data({'pose': {'arm_down': 0.0}}, keep_head=True)
    assert np.array_equal(a['verts'], c['verts'])
    ang = lambda D, bn: np.degrees(np.arctan2(*(lambda d: (abs(d[0]), -d[2]))(
        np.asarray(D['joints'][mh.VRM_JOINTS[bn][1]]) - np.asarray(D['joints'][mh.VRM_JOINTS[bn][0]]))))
    for bn, d in (('leftUpperArm', 10.0), ('rightUpperArm', 10.0), ('leftUpperLeg', 4.0), ('rightUpperLeg', 4.0)):
        assert abs((ang(a, bn) - ang(b, bn)) - d) < 0.3, (bn, ang(a, bn), ang(b, bn))
    hw = a['head_w'] > 0.5                                         # the head only rescales with the feet's height
    assert np.abs(a['verts'][hw] - b['verts'][hw]).max() < 0.002


def test_fit_terms_and_paired_knobs():
    from charkit import bodyfit
    spec = {'garments': [{'kind': 'sleeve', 'name': 'sleeve_L', 'side': 'left'}, {'kind': 'sleeve', 'name': 'sleeve_R', 'side': 'right'},
                         {'kind': 'skirt', 'name': 'skirt'}]}
    K = {k.name: k for k in bodyfit.knobs(spec)}
    k = K['sleeve.puff']
    assert k.paths == ['garments.sleeve_L.puff', 'garments.sleeve_R.puff'] and k.get(spec) == k.default
    k.put(spec, 1.3)
    assert spec['garments'][0]['puff'] == 1.3 and spec['garments'][1]['puff'] == 1.3
    t = bodyfit.Term('x', None, 'floor', 0.15, 'body_silhouette', 'sheet', 'front', 'body', floor=0.85)
    assert t.residual({'x': {'value': 0.55, 'status': 'FAIL'}})[0] == (0.85 - 0.55) / 0.15
    assert t.residual({'x': {'value': 0.9, 'status': 'PASS'}})[0] == 0.0
    assert t.residual({})[0] == 3.0
    R = bodyfit.residuals({'x': {'value': 0.55, 'status': 'FAIL'}}, [t, bodyfit.Term('x', None, 'floor', 0.15, 'body_silhouette',
                                                                                   'trellis', 'shape', 'body', floor=0.85)])
    assert R[0]['w'] == 1.0 and R[1]['w'] == 0.25                 # the sheet decides the body's silhouette


def test_palette_members_by_family():
    from charkit import bodyfit
    spec = {'hair': {}, 'garments': [{'kind': 'skirt', 'name': 'skirt', 'color': [0.86, 0.42, 0.24], 'hem_color': [0.3, 0.22, 0.2],
                                      'panel_color': [0.97, 0.9, 0.72]}]}
    M = bodyfit.palette_members(spec)
    assert ('garments.skirt.color', 'garment') in M['orange'] and ('garments.skirt.hem_color', 'garment') in M['dark']
    assert ('garments.skirt.panel_color', 'garment') in M['cream'] and M['skin'] == [('skin', 'toon3')]


def test_face_region_is_faceqa_face_region():
    """the vectorised flood (connected components) against faceqa's stack flood on a z-buffered head and neck."""
    from charkit import faceqa
    V1, T1 = sphere(0.45, (0, 0, -0.2))                              # a face
    V2, T2 = sphere(0.2, (0, 0.25, -0.8))                            # a neck behind it (a depth jump at the jaw)
    V3, T3 = sphere(0.08, (0.2, -0.5, -0.1))                         # something in front of a cheek (not skin)
    meshes = [(V1, T1, np.ones(len(T1), int)), (V2, T2, np.ones(len(T2), int)), (V3, T3, np.zeros(len(T3), int))]
    d, lab = faceqa.zbuffer(meshes, 0, (0, 0), 1.0)
    lab = np.where(lab < 0, 0, lab)
    a = faceqa.face_region(d, lab, 0.035)
    b = bodymeasure.face_region(d, lab, 0.035)
    assert a.any() and np.array_equal(a, b)


def test_outfit_graph_start_and_pieces():
    """the fit's start from an outfit graph's draft (pieces added, measured knobs taken), and the graph's pieces mapped to
    ours (a two-sided boots shell split by side, with the side's shoe)."""
    from charkit import bodyfit, bodymeasure
    spec = {'garments': [{'kind': 'skirt', 'name': 'skirt', 'back': 0.55, 'flare': 42},
                         {'kind': 'shell', 'name': 'boots', 'region': [['leftLowerLeg', 0.3, 1.5], ['rightLowerLeg', 0.3, 1.5]]},
                         {'kind': 'shoe', 'name': 'shoe_L', 'side': 'left'}]}
    graph = {'pieces': [{'id': 'skirt', 'type': 'skirt', 'side': 'C'}, {'id': 'boot_L', 'type': 'boot', 'side': 'L'},
                        {'id': 'panel_L', 'type': 'overskirt panel', 'side': 'L'}],
             'templates': {'garments': [{'kind': 'skirt', 'name': 'skirt', 'back': 0.06, 'flare': 41.4},
                                        {'kind': 'panel', 'name': 'panel_L', 'az': 146.0, 'length': 1.7}],
                           'knobs': {'skirt': {'back': 'measured (the back hem)', 'flare': 'default'}}},
             'comparison': {'matched': [{'draft': 'skirt', 'hand': 'skirt'}],
                            'missed_by_hand': [{'draft': 'panel_L', 'kind': 'panel'}]}}
    S, changed = bodyfit.outfit_start(spec, graph, log=lambda *a: None)
    assert [g['name'] for g in S['garments']][-1] == 'panel_L' and changed['garments.panel_L'] == [None, 'added']
    assert S['garments'][0]['back'] == 0.06 and S['garments'][0]['flare'] == 42          # measured taken, default not
    assert spec['garments'][0]['back'] == 0.55                                           # the input is untouched
    M = bodymeasure.piece_map(graph, S)
    assert M['boot_L'] == [('boots', 1), ('shoe_L', None)] and M['skirt'] == [('skirt', None)]
    assert M['panel_L'] == [('panel_L', None)]
    K = {k.name: k for k in bodyfit.knobs(S)}
    assert K['panel.az'].get(S) == 146.0 and K['panel.length'].group == 'skirt'
    two = dict(S, garments=S['garments'] + [{'kind': 'panel', 'name': 'panel_R', 'az': -146.0}])
    k = {k.name: k for k in bodyfit.knobs(two)}['panel.az']
    assert k.get(two) == 146.0
    k.put(two, 150.0)
    assert [g.get('az') for g in two['garments'][-2:]] == [150.0, -150.0]                # a mirror pair
    ext = {'skirt': {'front': {'d': [0.1, -0.2, 0.0, 0.05], 'px': [900, 800]}, 'back': {'d': [0, 0, 0, 0], 'px': [900, 100]}}}
    T = bodyfit.piece_terms(ext, graph)
    assert len(T) == 4 and {t.view for t in T} == {'front'} and T[0].scale == 1.0         # back: too few pixels


def test_garment_shade_knob():
    """a garment's 'shade' multiplier replaces the fixed one (the deep tone kept in the defaults' ratio); unset, the tones
    are exactly the old ones."""
    from charkit import garments as gm
    assert gm._muls() == (gm.SHADE_MUL, gm.DEEP_MUL)
    sm, dm = gm._muls((0.74, 0.64, 0.64))
    assert np.allclose(sm, (0.74, 0.64, 0.64)) and np.allclose(np.array(dm) / np.array(sm), np.array(gm.DEEP_MUL) / gm.SHADE_MUL)
    A = {'head': {'L': 0.25}}
    G = {'faces': [(0, 1, 2)], 'verts': np.zeros((3, 3)), 'sole': [0]}
    lit, shade, _ = bodyeval.garment_tones(A, {'kind': 'shoe', 'color': [0.5, 0.5, 0.5]}, G)
    assert np.allclose(shade, lit * gm.SHADE_MUL)
    lit, shade, _ = bodyeval.garment_tones(A, {'kind': 'shoe', 'color': [0.5, 0.5, 0.5], 'shade': [0.7, 0.6, 0.6]}, G)
    assert np.allclose(shade, lit * np.array([0.7, 0.6, 0.6]))


def test_ties_follow_attachments():
    """a piece hung from the waistband shares its waist line (the tied knob moves both, at their offset); a cuff sits at
    its sleeve's end."""
    from charkit import bodyfit
    spec = {'garments': [{'kind': 'skirt', 'name': 'skirt', 'waist': 0.5}, {'kind': 'belt', 'name': 'waistband', 'waist': 0.55},
                         {'kind': 'sleeve', 'name': 'sleeve_L', 'side': 'left', 't1': 0.45},
                         {'kind': 'band', 'name': 'cuff_L', 'bone': 'leftUpperArm', 't': 0.48}]}
    graph = {'pieces': [{'id': 'waistband', 'type': 'waistband', 'attach': {}}, {'id': 'skirt', 'type': 'skirt', 'attach': {'parent': 'waistband'}},
                        {'id': 'sleeve_L', 'type': 'sleeve', 'attach': {'parent': 'top'}},
                        {'id': 'sleeve_cuff_L', 'type': 'sleeve cuff', 'attach': {'parent': 'sleeve_L'}}],
             'comparison': {'matched': [{'draft': 'sleeve_cuff_L', 'hand': 'cuff_L'}]}}
    K = {k.name: k for k in bodyfit.tie(bodyfit.knobs(spec), spec, graph)}
    assert 'skirt.waist' not in K and 'cuff.t' not in K
    w = K['waistband.waist']
    assert w.group == 'skirt' and w.get(spec) == 0.55
    w.put(spec, 0.8)
    assert spec['garments'][1]['waist'] == 0.8 and abs(spec['garments'][0]['waist'] - 0.75) < 1e-9     # its offset kept
    K['sleeve.t1'].put(spec, 0.5)
    assert abs(spec['garments'][3]['t'] - 0.53) < 1e-9


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
