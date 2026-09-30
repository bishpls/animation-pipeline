"""charkit.evaldrift's comparison: the fast evaluator's checks against a box build's (venv: run this file, or pytest)."""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import evaldrift


def test_compare_flags_what_moves_past_its_tolerance():
    c = lambda v, s='PASS': {'value': v, 'status': s}
    box = {'body_front_hem': c(0.0424), 'body_back_hem': c(0.0236, 'WARN'), 'body_front_iou': c(0.851),
           'palette_skin': c(3.2), 'palette_hair': c(4.0), 'shape_iou': c(0.8), 'body_front_widest': c('shoulder'),
           'body_only_box': c(1.0), 'body_none': c(None, 'SKIPPED')}
    ev = {'body_front_hem': c(0.0164), 'body_back_hem': c(0.0496, 'FAIL'), 'body_front_iou': c(0.856),
          'palette_skin': c(3.5), 'palette_hair': c(4.9), 'shape_iou': c(0.8), 'body_front_widest': c('hip'),
          'body_only_eval': c(2.0), 'body_none': c(None, 'SKIPPED')}
    R = evaldrift.compare(box, ev)
    rows = {r['check']: r for r in R['rows']}
    # the hems 0.026 L apart (the body round's finding) drift; an IoU 0.005 apart doesn't
    assert set(R['drift']) == {'body_front_hem', 'body_back_hem', 'palette_hair', 'body_front_widest'}, R['drift']
    assert rows['body_front_hem']['diff'] == -0.026 and rows['body_back_hem']['diff'] == 0.026
    assert rows['body_front_iou']['tol'] == 0.01 and rows['palette_skin']['tol'] == 0.5        # CIEDE2000's own
    assert R['status'] == ['body_back_hem']
    assert R['only_box'] == ['body_only_box'] and R['only_eval'] == ['body_only_eval']
    assert R['compared'] == 7                                                                    # the value-less one left out
    assert [r['check'] for r in R['rows']][:1] == ['body_front_widest']        # drifted first; a non-number's first of them
    assert [r['check'] for r in R['rows']][1:4] == ['palette_hair', 'body_back_hem', 'body_front_hem'] and not R['rows'][-1]['drift']
    # one tolerance for every check
    assert set(evaldrift.compare(box, ev, tol=0.03)['drift']) == {'palette_skin', 'palette_hair', 'body_front_widest'}


def test_markdown_lists_every_compared_check():
    c = lambda v, s='PASS': {'value': v, 'status': s}
    R = evaldrift.compare({'a_hem': c(0.04)}, {'a_hem': c(0.01, 'WARN')})
    rep = dict(spec='s.json', build='out/x', git='abc1234', tol=None, tolerances=evaldrift.TOL, **R)
    md = evaldrift.markdown(rep)
    assert md.startswith('# evaldrift: s.json at abc1234: 1 of 1 checks drift') and '| a_hem | 0.04 PASS | 0.01 WARN | -0.0300' in md


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
