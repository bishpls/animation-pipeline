"""charkit.outfit on synthetic drawings, fields and bodies with known answers (venv: run this file, or pytest)."""
import json, math, os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import garments, outfit as O

ORANGE, SHADOW, CREAM, SKIN, DARK = (0.87, 0.47, 0.31), (0.62, 0.29, 0.2), (0.98, 0.92, 0.77), (0.99, 0.85, 0.76), (0.39, 0.32, 0.29)


def fam(rgb, body=None):
    return dict(rgb=np.array(rgb), lab=O.lab(np.array(rgb)), tones=[O.lab(np.array(rgb))], body=body)


def test_families_merge_shading_not_hue():
    rng = np.random.default_rng(0)
    jit = lambda c, n: np.clip(np.array(c) + rng.normal(0, 0.01, (n, 3)), 0, 1)
    F = O.families_from({'skirt': np.concatenate([jit(ORANGE, 600), jit(SHADOW, 300)]), 'bow': jit(CREAM, 500)},
                        {'skin': jit(SKIN, 500)})
    names = sorted(f['name'] for f in F)
    assert len(F) == 3, names                                   # orange and its shadow one family; cream apart from skin
    cls = O.classify(np.array([[ORANGE, SHADOW, CREAM, SKIN]]), F)[0]
    assert cls[0] == cls[1] and len(set(cls.tolist())) == 3, cls


def test_steps_tell_stairs_from_curves():
    x = np.arange(400)
    stair = (x // 50) * 30.0                                    # treads 50 wide, risers 30 high
    curve = 0.002 * (x - 200) ** 2
    s, share = O._steps(stair, tol=15, run=10)
    c, _ = O._steps(curve, tol=15, run=10)
    assert s >= 6 and share > 0.5, (s, share)
    assert c <= 1, c


def test_sub_regions_panel_band_trim():
    """a skirt-like piece: family 0 cloth, a full-length panel of family 1 down its middle, a stair-stepped band of
    family 2 along its hem; and a boot-like piece: family 0 shaft with a wider band of family 3 on top."""
    fams = [fam(ORANGE), fam(CREAM), fam(DARK), fam((0.9, 0.5, 0.3)), fam(SKIN, 'skin')]
    ppl = 100.0
    f = np.full((200, 300), -1)
    f[20:180, 20:280] = 0
    f[20:180, 130:170] = 1
    x = np.arange(300)
    for c in range(20, 280):
        if 130 <= c < 170:
            continue
        top = 150 - ((c - 20) // 40 % 2) * 12
        f[top:180, c] = 2
    region = f >= 0
    kinds = {s['fam']: s for s in O.sub_regions(f, region, 0, fams, ppl)}
    assert kinds[1]['kind'] == 'panel', kinds[1]['kind']
    assert kinds[2]['kind'] == 'trim' and kinds[2]['edge'] == 'bottom', kinds[2]
    b = np.full((300, 120), -1)
    b[40:290, 30:90] = 0
    b[10:40, 20:100] = 3
    kinds = {s['fam']: s for s in O.sub_regions(b, b >= 0, 0, fams, ppl)}
    assert kinds[3]['kind'] == 'band', kinds[3]


def test_hanging_parts_find_tails_and_a_centre_panel():
    """a bow: a knot, two lobes, two long tails hanging from under the knot either side, a strip between them."""
    L = np.zeros((400, 400), int)
    L[60:120, 170:230] = 1                                       # knot
    L[40:140, 40:168] = 2; L[40:140, 232:360] = 3               # lobes
    L[122:380, 110:168] = 4; L[122:380, 232:290] = 5            # tails
    L[122:360, 172:228] = 6                                      # the strip between them
    parts = O.hanging_parts(L, 6, ppl=200.0, line_r=2)
    kinds = sorted(k for _, k in parts)
    assert kinds == ['panel', 'tail', 'tail'], kinds


def test_split_pair_needs_an_empty_gap():
    reg = np.zeros((100, 400), bool)
    reg[10:90, 20:120] = True; reg[10:90, 280:380] = True
    assert O.split_pair(reg, 200, ppl=100.0) is not None
    amodal = reg.copy(); amodal[10:90, 120:280] = True           # one piece hidden under something in the middle
    assert O.split_pair(reg, 200, ppl=100.0, amodal=amodal) is None
    near = np.zeros((100, 400), bool)
    near[10:90, 100:195] = True; near[10:90, 205:300] = True     # a narrow gap (a V-neck): one piece
    assert O.split_pair(near, 200, ppl=100.0) is None


def test_motion_rules():
    geo = lambda h, w, fl=1.0, x=0.4: dict(height=h, width=w, flare=fl, aspect=h / w, bbox=[-x / 2, -h, x / 2, 0.0])
    assert O.motion(geo(0.1, 0.1, x=0.1), None, None, 'head', None)[0] == 'rigid'                 # a clip
    assert O.motion(geo(1.0, 1.4, 2.4), 0.9, 1.8, 'hips', 'waistband')[0] == 'cloth'           # a skirt
    assert O.motion(geo(0.2, 0.7), 0.9, 1.0, 'spine', None)[0] == 'rigid'                      # a waistband
    assert O.motion(geo(0.5, 0.12), 0.2, 1.0, 'chest', 'bow')[0] == 'spring'                   # a bow tail
    assert O.motion(geo(0.5, 0.12), 0.2, 1.0, 'chest', 'bow', tucked='waistband')[0] == 'rigid'
    assert O.motion(geo(0.5, 0.25), 0.2, 1.0, 'head', None, hair=0.9)[0] == 'rigid'            # a bun on the hair
    assert O.motion(geo(1.3, 0.4, 1.5), 0.9, 1.5, 'leftLowerLeg', None)[0] == 'rigid'          # a boot: rigid


def test_match_view_cells_and_splits():
    cl = np.zeros((40, 80), np.int32)
    cl[5:35, 5:35] = 1; cl[5:35, 45:75] = 2
    cells = [dict(id=1, cls=7, area=900, box=(5, 5, 35, 35), cx=20, cy=20),
             dict(id=2, cls=7, area=900, box=(45, 5, 75, 35), cx=60, cy=20)]
    pred = np.full((40, 80), -1)
    pred[5:35, 8:35] = 0                                         # cell 1: all piece 0 (a few px off)
    pred[5:35, 45:60] = 1; pred[5:35, 60:75] = 2                 # cell 2: two pieces, no line between
    A, res = O.match_view(cl, cells, pred, {7: {0, 1, 2}}, ppl=100.0)
    assert (A[cl == 1] == 0).all() and not res[1]['split']
    assert res[2]['split'] and set(np.unique(A[cl == 2])) == {1, 2}


def test_dtw_follows_a_stretch():
    """the height warp's alignment: rows of a drawing against the same rows with a band stretched to twice its height
    (the sheet's skirt hanging lower than the rig's): the path maps each stretched row back to its source."""
    rows = np.array([0] * 20 + [1] * 10 + [2] * 30 + [3] * 20)
    other = np.array([0] * 20 + [1] * 20 + [2] * 20 + [3] * 20)       # band 1 twice as tall, band 2 shorter
    cost = (rows[:, None] != other[None]).astype(float)
    path = O.dtw(cost, 30, 0.05)
    assert path[0] == (0, 0) and path[-1] == (79, 79)
    assert all(rows[i] == other[j] for i, j in path)                    # every step pairs rows of one band
    assert all(i2 >= i1 and j2 >= j1 for (i1, j1), (i2, j2) in zip(path, path[1:]))


def test_a_cell_no_drawn_line_divides_is_one_piece():
    """a cell predicted as two pieces is split only along a drawn line (the back's sleeves and bodice, one cell whose
    seams don't close); else it is one piece, the one lying over the other (the back panels over the skirt: one cell
    from the waistband into the tails), or the larger."""
    O.SHEET_FIELD['line_tol'] = 0.02                                     # 2 px at 100 px/L
    cl = np.zeros((40, 80), np.int32)
    cl[5:35, 5:75] = 1
    cells = [dict(id=1, cls=7, area=2100, box=(5, 5, 75, 35), cx=40, cy=20)]
    pred = np.full((40, 80), -1)
    pred[5:35, 5:45] = 0; pred[5:35, 45:75] = 1                         # 0 the larger, 1 over it where they meet
    A, res = O.match_view(cl, cells, pred, {7: {0, 1}}, ppl=100.0, lines=np.zeros((40, 80), bool),
                          over=lambda a, b, box: -1 if (a, b) == (0, 1) else 1 if (a, b) == (1, 0) else 0)
    assert not res[1]['split'] and res[1]['label'] == 1 and (A[cl == 1] == 1).all() and 'one piece' in res[1]['why']
    A, res = O.match_view(cl, cells, pred, {7: {0, 1}}, ppl=100.0, lines=np.zeros((40, 80), bool), over=None)
    assert res[1]['label'] == 0 and (A[cl == 1] == 0).all()             # nothing over the other: the larger
    ln = np.zeros((40, 80), bool)
    ln[5:30, 45] = True                                                  # a seam most of the way down
    A, res = O.match_view(cl, cells, pred, {7: {0, 1}}, ppl=100.0, lines=ln, over=None)
    assert res[1]['split'] and set(np.unique(A[cl == 1])) == {0, 1}
    O.SHEET_FIELD['line_tol'] = 0.03


def test_score_accepts_a_set_and_refuses_another_grid():
    t = np.full((10, 10), -1, np.int16)
    t[0:5] = 0; t[5:10, 0:5] = 1; t[5:10, 5:10] = 2
    sets = [['skirt'], ['bow_tail_L', 'bow_tail_R'], ['none']]
    m = {'front__skirt': np.zeros((10, 10), bool), 'front__bow_tail_R': np.zeros((10, 10), bool)}
    m['front__skirt'][0:5] = True; m['front__bow_tail_R'][5:10, 0:5] = True
    r = O.score(m, ({'front': t}, sets, {}))
    assert r['front']['accuracy'] == 1.0 and r['front']['iou'] == {'bow_tail_R': 1.0, 'skirt': 1.0}
    m['front__skirt'][5:10, 5:10] = True                                  # a piece where the truth has none
    r = O.score(m, ({'front': t}, sets, {}))
    assert r['front']['wrong'] == 25 and r['all']['confusions'][0]['got'] == 'skirt'
    try:
        O.score({'front__skirt': np.zeros((9, 10), bool)}, ({'front': t}, sets, {}))
        assert False, 'another grid scored'
    except ValueError:
        pass


def test_clawds_masks_against_the_truth():
    """Clawd's produced outfit masks (built from the rig and body_turnaround alone) against the hand-checked truth:
    0.972 of the garment pixels at 2026-09-30, where the TRELLIS-steered masks scored 0.865 and the no-field ones 0.729.
    Calibrated: the same masks with every piece's sides swapped (a known-bad) fail it. Builds the masks when this copy
    has none (about 45 s)."""
    from charkit import manifest
    spec = manifest.resolve(json.load(open(os.path.join(O.ROOT, 'charkit', 'spec', 'clawd.json'))))
    p = manifest.produced(spec, 'outfit_masks', log=lambda *a: None)
    Z = np.load(p)
    M = {k: Z[k] for k in Z.files}
    truth = O.load_truth(manifest.load(spec['ref']['manifest'])['references']['outfit_truth']['path'])
    r = O.score(M, truth)
    views = {v: r[v]['accuracy'] for v in O.VIEWS}
    assert r['all']['accuracy'] >= 0.96 and min(views.values()) >= 0.9 and r['all']['mean_iou'] >= 0.9, (r['all'], views)
    swap = lambda k: k[:-2] + {'_L': '_R', '_R': '_L'}[k[-2:]] if k.endswith(('_L', '_R')) else k
    bad = O.score({swap(k): v for k, v in M.items()}, truth)
    assert bad['all']['accuracy'] < 0.9, bad['all']['accuracy']


def test_coverage_round_a_bone():
    a = np.tile(np.linspace(-np.pi, np.pi, 72, endpoint=False), 10)
    ring = np.stack([0.3 * np.sin(a), 0.3 * np.cos(a), np.repeat(np.linspace(-1.2, -1.8, 10), 72)], 1)
    body = np.concatenate([ring, ring * np.array([0.5, 0.5, 1.0])])
    seg = ((0.0, -1.0), (0.0, -2.0))
    full, _ = O.coverage(body, np.arange(720), seg)
    arc, _ = O.coverage(body, np.nonzero(np.abs(a) < 0.5)[0], seg)
    assert full > 0.9 and arc < 0.25, (full, arc)


def test_compare_spec_sorts_matches_misses_extras():
    D = dict(garments=[dict(kind='skirt', name='skirt', length=1.0), dict(kind='panel', name='tail_L', az=150),
                       dict(kind='band', name='cuff_L', bone='leftLowerArm', t=0.8)], accessories=[dict(kind='star', name='s', az=30)])
    spec = dict(garments=[dict(kind='skirt', name='sk', length=0.9, panel=0.5), dict(kind='band', name='w', bone='leftLowerArm', t=0.84),
                          dict(kind='belt', name='belt')], accessories=[dict(kind='star', az=36), dict(kind='crab', az=20)])
    G = dict(pieces=[dict(id='front_panel', type='skirt panel', motion={'class': 'spring'})])
    C = O.compare_spec(D, spec, G)
    assert {(m['draft'], m['hand']) for m in C['matched']} == {('skirt', 'sk'), ('cuff_L', 'w'), ('s', 'accessories[0] star')}
    assert [m['draft'] for m in C['missed_by_hand']] == ['tail_L']
    assert sorted(x['kind'] for x in C['extra_in_hand']) == ['belt', 'crab']
    assert C['knob_only'][0]['hand'] == 'sk.panel'
    sk = next(m for m in C['matched'] if m['draft'] == 'skirt')
    assert abs(sk['knobs']['length']['delta'] - 0.1) < 1e-9


def test_panel_template_hangs_at_its_azimuth():
    """garments.panel on a cylinder body: hangs from the waist ring at the back, its length below it."""
    zz, aa = np.meshgrid(np.linspace(0.7, 1.3, 30), np.linspace(-np.pi, np.pi, 48, endpoint=False))
    V = np.stack([0.12 * np.sin(aa.ravel()), -0.12 * np.cos(aa.ravel()), zz.ravel()], 1)
    A = dict(head=dict(L=0.25), verts=V, weights={'hips': np.ones(len(V))},
             joints={'spine05____head': [0, 0, 0.9], 'spine04____head': [0, 0, 1.0], 'spine03____head': [0, 0, 1.1]})
    G = garments.panel(A, dict(az=180, width=0.4, length=1.0, offset=0.02, flare=20))
    v = G['verts']
    assert abs(G['z_waist'] - 1.0) < 1e-6                        # halfway from the hips joint to the spine's tail
    assert v[:, 1].mean() > 0.1                                 # at the back (+y)
    assert abs((G['z_waist'] - v[:, 2].min()) - 0.25) < 0.03     # one L long
    w = sum(G['weights'].values())
    assert np.allclose(w, 1.0)


def test_chain_runs_down_the_piece():
    pts = np.stack([np.zeros(300), np.zeros(300), np.linspace(-1.0, -1.9, 300)], 1)
    j = O._chain(pts, 0.15)
    assert 3 <= len(j) <= 8 and all(a[2] > b[2] for a, b in zip(j, j[1:]))


def test_dumps_compact_and_exact():
    o = dict(a=[1, 2.5, None], b=dict(c=[[0.1, 0.2], [0.3, 0.4]], d='x'), e=[dict(f=1)])
    s = O.dumps(o)
    assert json.loads(s) == o and '[[0.1, 0.2], [0.3, 0.4]]' in s


def test_verify_flags_disagreements():
    mask = lambda y0, x0: O.Mask(y0=y0, x0=x0, m=np.ones((10, 10), bool))
    P = [dict(id='bow', layer='bow', type='bow', side='C', fam=0, mask=mask(0, 0)),
         dict(id='bow_tail_L', layer='bow', type='bow tail', side='L', fam=0, mask=mask(20, 0))]
    img = np.full((40, 40), -1); img[0:10, 0:10] = 0; img[20:30, 0:10] = 1
    A = dict(pieces=P, n=2, fams=[fam(CREAM)], assigned={'front': img, 'back': np.full((40, 40), -1)})
    st = [dict(parent='collar', parent_why='', bone='upperChest', motion='rigid', motion_why=''),
          dict(parent='bow', parent_why='', bone='chest', motion='spring', motion_why='')]
    notes = dict(pieces=[dict(id='bow', type='bow', side='C', colour='cream', rig='bow', parent='collar', bone='upperChest',
                              motion='rigid', views=['front']),
                         dict(id='tail', type='bow tail', side='L', colour='cream', rig='bow', parent='bow', bone='upperChest',
                              motion='spring', views=['front', 'back']),
                         dict(id='star', type='hair accessory', side='L', colour='yellow', rig='pin_star')])
    match, flags = O.verify(A, st, notes)
    assert match == {'bow': 0, 'tail': 1}
    got = {(f['piece'], f['field']) for f in flags}
    assert ('tail', 'bone') in got and ('tail', 'views') in got and ('star', 'found') in got
    assert ('bow', 'parent') not in got and ('tail', 'parent') not in got


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)


def test_the_bow_is_cut_into_its_knot_and_lobes_by_its_drawn_cells():
    # a bow drawn as three cells: two lobes either side of a small knot, lines (0) between them
    cl = np.zeros((40, 100), np.int32)
    cl[5:35, 5:44] = 1; cl[12:28, 46:54] = 2; cl[5:35, 56:95] = 3
    M = cl > 0
    P, rows = O.bow_parts(M, cl, 'front', 100.0)
    assert P['knot'].sum() == (cl == 2).sum() and rows == (12, 27)
    assert (P['lobe_L'] == (cl == 3)).all() and (P['lobe_R'] == (cl == 1)).all()   # her left: the picture's right
    Pp, _ = O.bow_parts(M, cl, 'profile', 100.0, rows)
    assert Pp['knot'].sum() == (cl == 2).sum() and not Pp['lobe_R'].any()
    assert O.is_part('front__bow.knot') and not O.is_part('front__bow_tail_L')
    r = O.score_parts({'front__bow.knot': P['knot'], 'front__bow.lobe_L': P['lobe_R'], 'front__bow.lobe_R': P['lobe_L']},
                      ({'front': np.where(cl == 2, 0, np.where(cl == 3, 1, np.where(cl == 1, 2, -1)))},
                       [['bow.knot'], ['bow.lobe_L'], ['bow.lobe_R']]))
    assert r['front']['iou']['bow.knot'] == 1.0 and r['front']['iou']['bow.lobe_L'] == 0.0     # the sides swapped
