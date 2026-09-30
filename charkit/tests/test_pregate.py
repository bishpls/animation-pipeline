"""charkit.pregate: K on the evaluator's two check sets, and the agreement with a real gate's rows (venv: run this file,
or pytest)."""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import pregate


def _c(**kw):
    return {'checks': {k: {'value': v, 'status': s} for k, (v, s) in kw.items()}}


def test_judge_is_the_gates_k():
    base = _c(shape_iou=(0.90, 'PASS'), body_waist=(0.97, 'PASS'), palette_skin=(2.0, 'PASS'))
    cand = _c(shape_iou=(0.91, 'PASS'), body_waist=(0.70, 'FAIL'), palette_skin=(2.0, 'PASS'))
    v, block, R, rows = pregate.judge(base, cand, {})
    assert v == 'FAIL' and [b['check'] for b in block] == ['body_waist']
    assert {r['check'] for r in rows} == {'shape_iou', 'body_waist'}
    v, block, R, rows = pregate.judge(base, cand, {'body_*': 'a new measure'})
    assert v == 'PASS' and [r['verdict'] for r in rows if r['check'] == 'body_waist'] == ['remeasured']


def test_agreement_with_a_gate():
    base = _c(shape_iou=(0.90, 'PASS'), body_waist=(0.97, 'PASS'), body_hem=(0.5, 'WARN'), palette_skin=(2.0, 'PASS'))
    cand = _c(shape_iou=(0.91, 'PASS'), body_waist=(0.95, 'PASS'), body_hem=(0.5, 'WARN'), palette_skin=(2.1, 'PASS'))
    rows = pregate.judge(base, cand, {})[3]
    gate_rep = {'verdict': 'PASS', 'qa': [
        {'check': 'shape_iou', 'base': [0.88, 'PASS'], 'cand': [0.89, 'PASS'], 'verdict': 'value'},      # same way (up)
        {'check': 'body_waist', 'base': [0.96, 'PASS'], 'cand': [0.97, 'PASS'], 'verdict': 'value'},     # other way
        {'check': 'body_hem', 'base': [0.5, 'WARN'], 'cand': [0.6, 'PASS'], 'verdict': 'improved'},      # gate only
        {'check': 'art_spikes_boots', 'base': [0.1, 'PASS'], 'cand': [0.2, 'PASS'], 'verdict': 'value'}]}  # unseen
    A = pregate.agreement(gate_rep, rows, base, cand)
    assert (A['measured'], A['gate_moved'], A['pregate_moved'], A['both'], A['same_way']) == (4, 3, 3, 2, 1), A
    assert A['gate_only'] == ['body_hem'] and A['pregate_only'] == ['palette_skin'] and A['unseen'] == 1
    assert [d['check'] for d in A['disagree']] == ['body_waist']
    assert A['recall'] == round(2 / 3, 3) and A['precision'] == round(2 / 3, 3)
    md = pregate.markdown(dict(tag='t', into='pipeline-3d', head='abc', spec='s', verdict='PASS', checks=4,
                               seconds=dict(total=60, baseline=None, candidate=55, evaluator=50), blocking=[], qa=rows,
                               against='gate_x.json', agreement=dict(A, verdict=['PASS', 'PASS'])))
    assert 'recall' in md and 'body_waist' in md


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
