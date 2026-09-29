"""charkit.bodymeasure's per-piece shape measures on masks with known answers (venv: run this file, or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import bodymeasure as bm

GRAPH = {'pieces': [
    {'id': 'top', 'type': 'top', 'attach': {'parent': None}},
    {'id': 'bodice_panel', 'type': 'bodice panel', 'attach': {'parent': 'top'}},
    {'id': 'bow', 'type': 'bow', 'attach': {'parent': 'top'}},
    {'id': 'bow_tail_L', 'type': 'bow tail', 'attach': {'parent': 'bow'}},
    {'id': 'cuff_L', 'type': 'cuff', 'side': 'L', 'attach': {'parent': None}},
], 'comparison': {'matched': []}}
SPEC = {'garments': [{'name': 'top'}, {'name': 'cuff_L'}]}


def rect(shape, r0, r1, c0, c1):
    m = np.zeros(shape, bool)
    m[r0:r1, c0:c1] = True
    return m


def test_outline_f_same_and_shifted():
    a = rect((100, 100), 20, 80, 20, 80)
    same = bm.outline_f(a, a, 2)
    assert same['f'] == 1.0 and same['d_ours'] == 0.0
    near = bm.outline_f(rect((100, 100), 22, 82, 20, 80), a, 3)        # 2 px down: within a 3 px tolerance
    assert near['f'] == 1.0
    far = bm.outline_f(rect((100, 100), 30, 90, 20, 80), a, 3)         # 10 px down: the top and bottom edges miss
    assert 0.3 < far['f'] < 0.8, far


def test_iou_tol_forgives_the_line_not_the_shape():
    a = rect((200, 200), 50, 150, 90, 102)                              # a cuff, 12 px wide
    b = rect((200, 200), 50, 150, 92, 104)                              # 2 px over: within a line's width
    plain = (a & b).sum() / (a | b).sum()
    assert plain < 0.75
    assert bm.iou_tol(a, b, 3) > 0.95
    c = rect((200, 200), 50, 150, 120, 132)                             # somewhere else: no tolerance saves it
    assert bm.iou_tol(c, b, 3) == 0.0
    thin_a, thin_b = rect((200, 200), 50, 150, 90, 94), rect((200, 200), 50, 150, 90, 94)   # 4 px: the band shrinks
    assert bm.iou_tol(thin_a, thin_b, 3) == 1.0


def test_unbuilt_pieces_fold_into_their_built_parent():
    pm = bm.piece_map(GRAPH, SPEC)
    assert set(pm) == {'top', 'cuff_L'}
    up = bm.built_parent(GRAPH, pm)
    assert up == {'bodice_panel': 'top', 'bow': 'top', 'bow_tail_L': 'top'}
    shape = (60, 60)
    masks = {'front__top': rect(shape, 10, 30, 10, 50), 'front__bodice_panel': rect(shape, 10, 30, 25, 35),
             'front__bow_tail_L': rect(shape, 30, 40, 28, 32), 'front__cuff_L': rect(shape, 40, 50, 0, 5)}
    F = bm.folded(masks, GRAPH, pm)
    assert F['front__top'].sum() == masks['front__top'].sum() + masks['front__bow_tail_L'].sum()
    assert F['front__bodice_panel'].sum() == masks['front__bodice_panel'].sum()        # kept for the count


def test_piece_shapes_on_an_exact_build():
    shape = (60, 60)
    masks = {'front__top': rect(shape, 10, 30, 10, 50), 'front__bodice_panel': rect(shape, 10, 30, 25, 35),
             'front__cuff_L': rect(shape, 40, 50, 0, 10)}
    whole_top = masks['front__top'] | masks['front__bodice_panel']
    lab = np.full(shape, -1)
    lab[whole_top] = 0                                                  # our top covers its panel: one object
    lab[masks['front__cuff_L']] = 1
    S = bm.piece_shapes({'front': lab}, ['top', 'cuff_L'], masks, GRAPH, SPEC, ppl=100.0, min_px=10)
    assert S['top']['views']['front']['iou'] == 1.0 and S['top']['with'] == ['bodice_panel', 'bow', 'bow_tail_L']
    assert S['cuff_L']['views']['front']['iou_tol'] == 1.0
    assert S['bodice_panel']['members'] is None and S['bodice_panel']['part_of'] == 'top'
    conf = bm.piece_confusion({'front': lab}, ['top', 'cuff_L'], masks, GRAPH, SPEC, 'front')
    assert conf['bodice_panel'] == {'top': 200}


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok', name)
