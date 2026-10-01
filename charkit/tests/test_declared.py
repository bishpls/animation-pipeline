"""Declared checks (charkit/declared.py) on synthetic masks (venv: run this file): each family's reading, a declaration's
expansion, grading and FAIL/skip semantics, the literal read with ast and from CHARKIT_DECLARED, the calibration entries
it derives, and the port of piece_details' shorts checks: the declared hem and width equal the hand-written waist()'s
(its code kept here as it was) on the same label images."""
import json, os, sys, tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import calibrate, declared, pieceqa

PPL = 100.0
H, W = 400, 300


def rect(r0, r1, c0, c1, shape=(H, W)):
    m = np.zeros(shape, bool)
    m[r0:r1, c0:c1] = True
    return m


def test_families():
    ctx = dict(ppl=PPL, lab=np.zeros((H, W), int), dv_fg=None, cls=None, lines=None)
    a = rect(100, 300, 100, 200)
    assert declared.shape_iou(a, a, ctx, close=True)['value'] == 1.0
    assert abs(declared.shape_iou(rect(100, 300, 150, 250), a, ctx, close=True)['value'] - 1 / 3) < 0.01
    w = declared.width(rect(100, 300, 50, 250), a, ctx)                    # twice as wide: 2 - 1
    assert w['value'] == 1.0 and w['ours'] == 2.0 and w['design'] == 1.0
    e = declared.edge(rect(100, 305, 100, 200), a, ctx)                    # 5 px lower at 100 px per L
    assert e['value'] == 0.05
    assert declared.edge(np.zeros((H, W), bool), a, ctx)['value'] is None  # ours missing: FAIL with why
    assert declared.edge(a, np.zeros((H, W), bool), ctx) is None           # the design doesn't draw it: skipped
    spike = a.copy()
    spike[60:100, 148:152] = True                                          # a 0.4 L horn, 0.04 L wide
    t = declared.tips(spike, a, dict(ctx, lab=np.where(spike, 0, -1), dv_fg=a))  # (the corners: both, 0.014 L)
    assert t['count'] == [5, 4] and t['value'] > 0.3 and t['count_status'] == 'WARN'
    th = np.radians(30)
    yy, xx = np.mgrid[:H, :W]
    u = (xx - 150) * np.cos(th) - (yy - 200) * np.sin(th)
    v = (xx - 150) * np.sin(th) + (yy - 200) * np.cos(th)
    tilted = (np.abs(u) < 20) & (np.abs(v) < 120)
    assert abs(declared.angle(tilted, rect(80, 320, 130, 170), ctx)['value'] - 30) < 1.5
    top, bot = rect(100, 200, 100, 200), rect(200, 300, 100, 200)
    cls = np.zeros((H, W), int)
    cls[199:201, 100:200] = 4                                              # the drawing's ink between them
    ib = declared.ink_between((top, bot), (top, bot), dict(ctx, cls=cls))
    assert ib['design'] == 0.0 and ib['ours'] == 1.0 and ib['value'] == 1.0  # ours touch along 1 L (a's edge row)
    ib = declared.ink_between((top, bot), (top, bot), dict(ctx, cls=cls, lines=cls == 4))
    assert ib['value'] == 0.0
    p = declared.position(rect(110, 310, 100, 200), a, ctx)
    assert p['value'] == 0.1


def inputs(ours, drawn, piece='shorts'):
    """a part's inputs with one object 'shorts_obj' standing for the piece in every view."""
    O = {v: dict(lab=np.where(ours[v], 0, -1)) for v in ours}
    return dict(O=O, names=['shorts_obj'], masks={'%s__%s' % (v, piece): m for v, m in drawn.items()},
                pm={piece: [('shorts_obj', None)]}, ppl=PPL, dv={v: dict(fg=m, cls=None) for v, m in drawn.items()})


def test_evaluate_and_grade():
    d = dict(check='x_{view}_width', family='width', piece='shorts', views=['front', 'back', 'profile'],
             params=dict(round=3), limits=[0.05, 0.10], flag='a test flag', note='n')
    I = inputs({'front': rect(100, 300, 100, 210), 'back': np.zeros((H, W), bool)},
               {'front': rect(100, 300, 100, 200), 'back': rect(100, 300, 100, 200)})
    T, C = declared.evaluate([d], I)
    assert set(C) == {'x_front_width', 'x_back_width'}                     # profile: no labels there, skipped
    assert C['x_front_width']['value'] == 0.1 and C['x_front_width']['status'] == 'WARN'
    assert C['x_front_width']['flag'] == 'a test flag' and C['x_front_width']['note'] == 'n'
    assert C['x_back_width'] == {'value': None, 'status': 'FAIL', 'why': declared.WHY_OURS, 'flag': 'a test flag'}
    d2 = dict(d, check='y_{view}', family='shape_iou', limits=[0.9, 0.8], flag=None, views=['front'],
              params=dict(close=True))
    assert declared.evaluate([d2], I)[1]['y_front']['status'] == 'PASS'   # IoU 0.909: higher is better
    assert declared.limits_of(dict(limits='charkit.pieceqa.LIMITS.rows')) == pieceqa.LIMITS['rows']


def test_declarations_and_entries():
    src = "X = 1\nDECLARED_CHECKS = [dict(check='a_{view}_hem', family='edge', piece='shorts', limits=[0.02, 0.04],\n" \
          "    calibrate=dict(known_bad='kb', baseline=['voronoi_pieces'])),\n" \
          "    dict(check='b', family='width', piece='top', part='piece_details', limits=[1, 2])]\n"
    ds = declared.declarations(files={'charkit/zz.py': src, 'charkit/other.py': 'nothing here'})
    assert [d['check'] for d in ds] == ['a_{view}_hem', 'b'] and ds[0]['module'] == 'charkit.zz'
    E = declared.calibration_entries(ds)
    assert len(E) == 1 and E[0]['check'] == 'a_*_hem' and E[0]['adapter'] == 'Declared' and \
        E[0]['module'] == 'charkit.declared' and E[0]['known_bad'] == 'kb' and E[0]['part'] == 'declared'
    assert [n for n, _, _ in declared.expand(ds[:1])] == ['a_front_hem', 'a_three_quarter_hem', 'a_profile_hem',
                                                           'a_back_hem']
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, 'draft.json')
        json.dump([dict(check='draft_x', family='edge', piece='shorts', limits=[0.1, 0.2],
                        calibrate=dict(known_bad=None, baseline=['affine_pieces']))], open(f, 'w'))
        os.environ[declared.ENV] = f
        try:
            assert any(d_['check'] == 'draft_x' for d_ in declared.declarations())
            assert any(e['check'] == 'draft_x' and e['adapter'] == 'Declared' for e in calibrate.entries())
        finally:
            del os.environ[declared.ENV]
    # the tree's own: the ported shorts checks, their calibration entries after calib/details.py's own
    names = [d['check'] for d in declared.declarations()]
    assert 'shorts_{view}_hem' in names and 'shorts_{view}_width' in names
    e = calibrate.entry_for('shorts_back_width')
    assert e['module'] == 'charkit.calib.details' and e['adapter'] == 'Details'


def waist_shorts(O, names, masks, pm, ppl):
    """piece_details' shorts checks as waist() measured them before the port (pipeline-3d 342e88c, kept verbatim)."""
    from charkit.pieceqa import clean, edges, grade, members, z_of
    T, C = {}, {}
    for view in ('front', 'three_quarter', 'profile', 'back'):
        if view not in O:
            continue
        for pid in ('shorts',):
            Md = masks.get('%s__%s' % (view, pid))
            if Md is None or pid not in pm:
                continue
            ed = edges(clean(Md, ppl))
            if ed is None:
                continue
            eo = edges(clean(members(O[view]['lab'], names, pm, pid), ppl))
            if eo is None:
                why = {'value': None, 'status': 'FAIL', 'why': 'ours shows too little of the piece here'}
                C['shorts_%s_hem' % view] = dict(why)
                if view in ('front', 'back'):
                    C['shorts_%s_width' % view] = dict(why)
                continue
            zo = dict(top=z_of(eo['top'], ppl), bottom=z_of(eo['bottom'], ppl), width=eo['width'] / ppl)
            zd = dict(top=z_of(ed['top'], ppl), bottom=z_of(ed['bottom'], ppl), width=ed['width'] / ppl)
            zo = {k: round(v, 4) for k, v in zo.items()}
            zd = {k: round(v, 4) for k, v in zd.items()}
            v_ = round(abs(zo['bottom'] - zd['bottom']), 4)
            C['shorts_%s_hem' % view] = {
                'value': v_, 'status': grade('rows', v_), 'ours': zo['bottom'], 'design': zd['bottom'],
                'note': "the shorts' lower edge (their middle columns' last rows, L from the eye line) against the "
                        "design's"}
            if view in ('front', 'back'):
                v_ = round(abs(zo['width'] / max(zd['width'], 1e-6) - 1), 3)
                C['%s_%s_width' % (pid, view)] = {
                    'value': v_, 'status': grade('width', v_), 'ours': zo['width'], 'design': zd['width'],
                    'note': "the piece's median row width over its middle columns' rows, ours over the design's, less "
                            "one"}
    return C


def test_port_identity():
    rng = np.random.default_rng(7)
    for trial in range(12):
        ours, drawn = {}, {}
        for v in declared.VIEWS:
            if rng.random() < 0.15:
                continue                                   # (a view without the drawn piece: both skip it)
            r0, c0 = rng.integers(150, 250), rng.integers(60, 120)
            drawn[v] = rect(r0, r0 + rng.integers(60, 140), c0, c0 + rng.integers(60, 160))
            dr, dc = rng.integers(-12, 12, size=2)
            ours[v] = rect(r0 + dr, r0 + dr + rng.integers(40, 150), c0 + dc, c0 + dc + rng.integers(40, 170)) \
                if rng.random() > 0.1 else np.zeros((H, W), bool)
        I = inputs(ours, drawn)
        want = waist_shorts(I['O'], I['names'], I['masks'], I['pm'], PPL)
        _, got = declared.evaluate_part('piece_details', I)
        assert json.dumps(want, sort_keys=True) == json.dumps(got, sort_keys=True), (trial, want, got)


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)


def test_a_region_of_a_piece_by_its_class_and_the_lines_along_a_region():
    # drawn: the region compared in place of the piece's (the skirt's cream panel); ours_cls: our piece's pixels of
    # that class (its material there)
    from charkit import bodyqa
    ours = rect(100, 300, 50, 250)
    cls = np.zeros((H, W), int)
    cls[100:300, 100:200] = bodyqa.CLASS['cream']
    I = inputs({'front': ours}, {'front': rect(100, 300, 50, 250)})
    I['masks']['front__panel'] = rect(100, 300, 100, 200)
    I['cls_ours'] = {'front': cls}
    d = dict(check='p_{view}_shape', family='shape_iou', piece='shorts', views=['front'], limits=[0.9, 0.8],
             params=dict(drawn='panel', ours_cls='cream', close=True))
    assert declared.evaluate([d], I)[1]['p_front_shape']['value'] == 1.0
    I['cls_ours'] = {'front': np.zeros((H, W), int)}
    assert declared.evaluate([d], I)[1]['p_front_shape']['status'] == 'FAIL'   # no cream of ours there
    # ink_inside's edge: the drawn lines along a region's outline, not inside it
    R = rect(100, 300, 100, 200)
    raw = np.zeros((H, W), int)
    raw[100:300, 98:100] = bodyqa.CLASS['line']                              # a fold along its left edge
    raw[100:300, 149:151] = bodyqa.CLASS['line']                             # a crease down its middle
    ctx = dict(ppl=PPL, view='front', masks={'front__panel': R}, dv=dict(raw=raw, rgb=None))
    ours_l = np.zeros((H, W), bool)
    ours_l[100:300, 99] = True
    e = declared.ink_inside(R, R, dict(ctx, lines=ours_l), region='panel', band=0.05, faint=False, edge=True)
    assert e['value'] < 0.1                                                   # the fold found along the edge
    i = declared.ink_inside(R, R, dict(ctx, lines=ours_l), region='panel', band=0.05, faint=False)
    assert i['value'] == 1.0                                                  # the crease inside: none of ours


def test_relative_lines_are_read_where_they_lie_within_the_region():
    # relative: ours moved row by row from our region's span onto the drawn one's (the same share across it)
    from charkit import bodyqa
    Ro, Rd = rect(100, 300, 100, 200), rect(100, 300, 50, 250)              # ours half as wide as the drawn
    m = np.zeros((H, W), bool)
    m[100:300, 125] = True                                                   # a quarter of the way across ours
    got = declared.remap_rows(m, Ro, Rd)
    assert set(np.nonzero(got)[1]) == {100}                                  # a quarter across the drawn (50 + 50)
    raw = np.zeros((H, W), int)
    raw[100:300, 99:101] = bodyqa.CLASS['line']                               # the drawn crease a quarter across
    cls = np.where(Ro, bodyqa.CLASS['cream'], 0)
    ctx = dict(ppl=PPL, view='front', masks={'front__panel': Rd}, dv=dict(raw=raw, rgb=None), cls_ours=cls, lines=m)
    a = declared.ink_inside(Ro, Rd, ctx, region='panel', band=0.05, faint=False)
    r = declared.ink_inside(Ro, Rd, ctx, region='panel', band=0.05, faint=False, relative='cream')
    assert a['value'] == 1.0 and r['value'] < 0.05                           # absolute: 0.25 L off; relative: found


def test_area_against_the_drawn_silhouette():
    # the drawn cuff's fill with a line round it (the drawing's ink between it and the sleeve above, and its outer
    # outline): our geometry has no ink between pieces, so its size compares with the fill plus the lines given to the
    # nearest piece (bodymeasure.drawn_labels), not with the fill alone
    from charkit import bodyqa
    sleeve, cuff = rect(100, 196, 100, 200), rect(204, 300, 100, 200)       # an 8 px line between them
    fg = rect(96, 304, 96, 204)                                              # a 4 px outline round both
    cls = np.where(fg, bodyqa.CLASS['line'], 0)
    cls[sleeve | cuff] = 2
    graph = dict(pieces=[dict(id='sleeve'), dict(id='cuff', layer=dict(over=['sleeve']))])
    I = dict(O={'front': dict(lab=np.where(rect(200, 304, 96, 204), 1, np.where(fg, 0, -1)))},
             names=['sleeve_obj', 'cuff_obj'], masks={'front__sleeve': sleeve, 'front__cuff': cuff},
             pm={'sleeve': [('sleeve_obj', None)], 'cuff': [('cuff_obj', None)]}, ppl=PPL,
             dv={'front': dict(fg=fg, cls=cls)}, graph=graph, skin=[])
    d = dict(check='c_{view}_size', family='area', piece='cuff', views=['front'], params=dict(round=3),
             limits=[0.2, 0.4])
    c = declared.evaluate([d], I)[1]['c_front_size']
    # ours: the cuff's fill, half the line above it and its outline (104 x 108 px) against the drawn silhouette (the same)
    assert c['value'] == 0.0 and c['status'] == 'PASS' and c['design'] == 104 * 108
    assert c['fill'] == 96 * 100 and abs(c['ratio_fill'] - 104 * 108 / 9600) < 1e-3
    f = declared.evaluate([dict(d, params=dict(round=3, ref='fill'))], I)[1]['c_front_size']
    assert f['design'] == 96 * 100 and f['status'] == 'PASS' and f['value'] == round(104 * 108 / 9600 - 1, 3)
