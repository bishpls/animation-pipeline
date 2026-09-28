"""charkit.tune's acceptance and stop rules, charkit.triage's classifier and charkit.review's tickets, on synthetic QA
histories (venv: run this file, or pytest)."""
import json, os, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import checks, fitters, history, review, triage, tune


def qa(**kw):
    """{check: (value, status)} -> a qa.json-shaped dict."""
    return {'checks': {k: {'value': v, 'status': s} for k, (v, s) in kw.items()}}


# ------------------------------------------------------------------------------------------------------------ grading
def test_severity_and_score():
    assert checks.severity('sheet_width', 1.05) == 0                     # |0.05| inside the 0.08 pass limit
    assert abs(checks.severity('sheet_width', 0.85) - 1.0) < 1e-9        # at the 0.15 fail limit: one warn band
    assert checks.severity('hair_noise', 0.02) == 0 and abs(checks.severity('hair_noise', 0.12) - 2.0) < 1e-9
    assert checks.severity('shape_iou', 0.5) > 1                         # higher is better
    assert checks.severity('sheet_shown_front', 0.5) < checks.severity('sheet_shown_front', 0.4)   # warn-only: worse still shows
    assert checks.severity('no_such_check', None, 'FAIL') == 1.5         # graded by status alone
    assert checks.severity('sheet_width.d75', 0.85) == checks.severity('sheet_width', 0.85)
    q = qa(sheet_width=(0.85, 'WARN'), hair_noise=(0.12, 'FAIL'), mesh=(None, 'INFO'))
    assert abs(checks.score(q) - 3.0) < 1e-9
    assert checks.score(qa(face_folds=(99999, 'FAIL'))) == checks.CAP     # one wild check is capped
    # a check measured against a reference that isn't its measure's authority counts a quarter
    A = {'face_front': 'sheet'}
    q = qa(sheet_width=(0.85, 'WARN'), face_shape_width=(0.85, 'WARN'))
    assert abs(checks.score(q, authority=A) - 1.25) < 1e-9 and abs(checks.score(q) - 2.0) < 1e-9


# ------------------------------------------------------------------------------------------------------------ accept
RULES = [{'allow': ['face_shape_width'], 'when': ['sheet_width'], 'floor': 'FAIL', 'ratio': 3.0, 'why': 'the sheet is the authority'}]


def test_accept_rejects_a_regression_without_a_rule():
    a = qa(sheet_width=(0.80, 'FAIL'), eye_width=(1.0, 'PASS'))
    b = qa(sheet_width=(0.97, 'PASS'), eye_width=(0.86, 'WARN'))           # big gain, but a PASS went to WARN
    d = tune.accept(a, b, RULES)
    assert d['verdict'] == 'reject' and [r['check'] for r in d['regressed']] == ['eye_width'], d['why']


def test_accept_allows_a_regression_under_a_rule():
    a = qa(sheet_width=(0.80, 'FAIL'), face_shape_width=(0.95, 'PASS'))
    b = qa(sheet_width=(0.97, 'PASS'), face_shape_width=(0.89, 'WARN'))
    d = tune.accept(a, b, RULES)
    assert d['verdict'] == 'accept' and d['traded'][0]['check'] == 'face_shape_width' and d['traded'][0]['for'] == 'sheet_width', d


def test_accept_rule_bounds_the_cost():
    a = qa(sheet_width=(0.90, 'WARN'), face_shape_width=(1.0, 'PASS'))
    b = qa(sheet_width=(0.93, 'PASS'), face_shape_width=(0.50, 'FAIL'))  # gain 0.29 bands, cost ~5 bands: over ratio 3
    d = tune.accept(a, b, RULES)
    assert d['verdict'] == 'reject', d


def test_accept_noise_rule():
    """a flip at the limit inside the measurement's error, paid for by a net gain elsewhere."""
    noise = [{'allow': ['body_*'], 'noise': True, 'max_cost': 0.15, 'floor': 'WARN', 'why': 'noise'}]
    a = qa(body_profile_hair_width=(0.920, 'PASS'), body_front_hair_length=(-0.18, 'FAIL'))
    b = qa(body_profile_hair_width=(0.914, 'WARN'), body_front_hair_length=(-0.07, 'PASS'))
    assert tune.accept(a, b)['verdict'] == 'reject'
    d = tune.accept(a, b, noise)
    assert d['verdict'] == 'accept' and d['traded'][0]['for'] == 'noise', d
    c = qa(body_profile_hair_width=(0.80, 'FAIL'), body_front_hair_length=(-0.07, 'PASS'))     # past WARN: not noise
    assert tune.accept(a, c, noise)['verdict'] == 'reject'


def test_prescreen():
    regs = {'eye_width': ['PASS', 'FAIL'], 'face_shape_width': ['PASS', 'WARN'], 'sheet_cheek_chin': ['PASS', 'WARN']}
    assert tune.unallowed(regs, RULES) == {'eye_width': ['PASS', 'FAIL'], 'sheet_cheek_chin': ['PASS', 'WARN']}
    assert tune.unallowed({}, RULES) == {}


def test_accept_needs_a_gain_and_counts_gone_checks():
    a = qa(sheet_width=(0.85, 'WARN'), eye_width=(1.0, 'PASS'))
    assert tune.accept(a, a)['verdict'] == 'reject'                      # no change: no gain
    b = qa(sheet_width=(1.0, 'PASS'))                                     # eye_width disappeared
    d = tune.accept(a, b)
    assert d['verdict'] == 'reject' and d['regressed'][0]['verdict'] == 'gone'


def test_accept_ignores_a_remeasured_check():
    a = qa(hair_noise=(0.05, 'WARN'), sheet_width=(0.85, 'WARN'))
    b = qa(hair_noise=(0.31, 'FAIL'), sheet_width=(0.95, 'PASS'))         # hair_noise's measurement changed in between
    assert tune.accept(a, b)['verdict'] == 'reject'
    d = tune.accept(a, b, remeasured={'hair_noise': 'undithered'})
    assert d['verdict'] == 'accept' and not d['regressed'], d


def test_disagreement_between_the_fast_evaluator_and_the_build():
    fit = {'predicted': {'eye_aspect': [0.70, 0.95], 'sheet_width': [0.84, 0.95]}}
    start = tune.Checkpoint(_qa=qa(eye_aspect=(0.70, 'FAIL'), sheet_width=(0.70, 'FAIL')))
    cand = tune.Checkpoint(_qa=qa(eye_aspect=(0.80, 'FAIL'), sheet_width=(0.95, 'PASS')))
    d = tune.disagreement(fit, cand, start)
    # eye_aspect: predicted to pass, built still failing; sheet_width: the evaluator's start (0.84) isn't the build's (0.70)
    assert d == {'eye_aspect': [0.95, 0.80], 'sheet_width': [0.84, 0.70]}, d


# ------------------------------------------------------------------------------------------------------------ stop
def test_stop_rules():
    assert tune.stop_reason([10, 5], all_pass=True) == 'pass'
    assert tune.stop_reason([10, 5], builds_left=0) == 'budget'
    assert tune.stop_reason([10, 5], seconds_left=-1) == 'budget'
    assert tune.stop_reason([10, 5], changed=False) == 'converged'
    assert tune.stop_reason([10, 5]) is None                             # one round: too early to call a stall
    assert tune.stop_reason([10, 5, 4.8, 4.7], rounds=2, min_gain=0.5) == 'stalled'
    assert tune.stop_reason([10, 5, 4.0, 3.0], rounds=2, min_gain=0.5) is None
    # a synthetic history: the loop's scores per round until a rule fires
    hist, reasons = [20.0], []
    for s in (12.0, 9.0, 8.9, 8.85, 8.8):
        hist.append(s)
        r = tune.stop_reason(hist, rounds=2, min_gain=0.5)
        reasons.append(r)
        if r:
            break
    assert reasons == [None, None, None, 'stalled'] and hist[-1] == 8.85, (reasons, hist)


# ------------------------------------------------------------------------------------------------------------ triage
class F(fitters.Fitter):
    def __init__(self, name, targets, knobs, landed=True):
        self.name, self.targets, self.landed, self.owns = name, targets, landed, ()
        self.knobs = {k: {'path': tuple(k.split('.')), 'default': 1.0, 'step': 0.1, 'bounds': b, 'block': 'face'} for k, b in knobs.items()}


def _ctx(spec, table, fitters_, recs=(), config=None, **kw):
    return dict({'fitters': fitters_, 'spec': spec, 'tables': {'face': table}, 'knobs': {f.name: f.knobs for f in fitters_},
                 'records': list(recs), 'config': config or {}, 'disagree': {}, 'nondeterministic': [],
                 'inventory': fitters.inventory(spec)}, **kw)


def _m(at, minus, plus):
    return {'at': at, 'minus': minus, 'plus': plus, 'per_step': (plus - minus) / 2}


def test_triage_classes():
    spec = {'name': 'x', 'head': {'jaw_w': 1.6, 'chin': 1.0, 'cheek': 1.0}}
    face = F('face', ('sheet_*', 'eye_*'), {'head.jaw_w': (0.7, 1.6), 'head.chin': (0.5, 2.0), 'head.cheek': (0.7, 1.4)})
    table = {
        # jaw_w: at its upper bound, and more would widen the lower face (sheet_width 0.80 -> 0.84)
        'head.jaw_w': {'x': 1.6, 'step': 0.1, 'measures': {'sheet_width': _m(0.80, 0.76, 0.84)}},
        # chin: lengthens the profile's chin (better) but pushes the nose's reach out (worse)
        'head.chin': {'x': 1.0, 'step': 0.1, 'measures': {'sheet_profile_chin': _m(-0.05, -0.06, -0.04),
                                                          'sheet_nose_reach': _m(0.0, 0.0, 0.05)}},
        # cheek: moves the cheek with no cost, but no fitter targets eye_... ; sheet_cheek is targeted
        'head.cheek': {'x': 1.0, 'step': 0.1, 'measures': {'eye_width': _m(0.80, 0.78, 0.84), 'sheet_cheek': _m(0.03, 0.03, 0.03)}},
    }
    ctx = _ctx(spec, table, [face], accepted={'face': True})
    c = lambda k, v, s: triage.classify(k, {'value': v, 'status': s}, ctx)
    cls, detail, ev, _ = c('sheet_width', 0.80, 'FAIL')
    assert cls == 'knob at a bound' and 'head.jaw_w' in detail and ev['bounds'][0]['bound'] == 1.6, (cls, detail)
    cls, detail, ev, _ = c('sheet_profile_chin', -0.05, 'WARN')
    assert cls == 'trade-off' and 'sheet_nose_reach' in detail, (cls, detail)
    cls, detail, _, _ = c('sheet_cheek', 0.03, 'WARN')                   # in the table, but nothing moves it
    assert cls == 'needs a knob' and 'none of the face' in detail, (cls, detail)
    cls, _, _, _ = c('hair_noise', 0.31, 'FAIL')                         # no table measures it; a template matter
    assert cls == 'needs a capability'
    cls, detail, _, _ = c('shape_iou', 0.58, 'FAIL')                     # no table, no capability: a knob is missing
    assert cls == 'needs a knob' and 'no fitter measures it' in detail
    # eye_width: cheek improves it at no cost, moving away from its default (1.0 -> up): the fit's pull to the defaults
    cls, detail, _, _ = c('eye_width', 0.80, 'FAIL')
    assert cls == 'trade-off' and 'default' in detail, (cls, detail)
    # the same, but the face fit was never accepted from here: its joint fit trades it (or the build rejected it)
    cls, detail, _, _ = triage.classify('eye_width', {'value': 0.80, 'status': 'FAIL'}, _ctx(spec, table, [face]))
    assert cls == 'trade-off' and "wasn't accepted" in detail, (cls, detail)
    face2 = F('face', ('sheet_*',), face.knobs and {'head.jaw_w': (0.7, 1.6), 'head.chin': (0.5, 2.0), 'head.cheek': (0.7, 1.4)})
    cls, detail, _, _ = triage.classify('eye_width', {'value': 0.80, 'status': 'FAIL'}, _ctx(spec, table, [face2]))
    assert cls == 'not in the objective' and 'head.cheek' in detail, (cls, detail)


def test_triage_reads_the_fitkit_schema():
    """charkit.fitkit's table (schema charkit.sensitivity/1: knobs carry their value, step, bounds and group)."""
    spec = {'name': 'x', 'iris': {'pupil_rz': 0.30}}
    face = F('face', ('eye_*',), {})
    table = {'schema': 'charkit.sensitivity/1', 'knobs': {
        'iris.pupil_rz': {'value': 0.30, 'step': 0.015, 'bounds': [0.06, 0.30], 'group': 'eyes', 'at_bound': 'upper',
                          'measures': {'eye_pupil_run': _m(0.60, 0.55, 0.62), 'eye_pupil_aspect': _m(0.60, 0.58, 0.63)}}}}
    ctx = _ctx(spec, table, [face])
    cls, detail, ev, _ = triage.classify('eye_pupil_aspect', {'value': 0.60, 'status': 'FAIL'}, ctx)
    assert cls == 'knob at a bound' and ev['bounds'][0]['bound'] == 0.30, (cls, detail)
    assert triage.movers('eye_lid_gap', {'face': table}, {}, spec) is None          # the table doesn't measure it


def test_options_and_partial_specs():
    d = tempfile.mkdtemp()
    sp = os.path.join(d, 'x.json')
    json.dump({'name': 'x', 'hair': {'shape': {'mode': 'mesh'}}, 'head': {'chin': 1.0}, 'eyes': {'width': 0.2}}, open(sp, 'w'))
    O = fitters.OptionsFitter([{'name': 'geom', 'set': {'hair.shape.mode': 'geom'}, 'targets': ['hair_noise']},
                               {'name': 'anime', 'set': {'base': 'anime'}, 'args': ['--vrm'], 'targets': ['face_folds']}])
    assert [o['name'] for o in O.pending(['hair_noise'])] == ['geom']            # only the options whose targets fail
    r = O.run(sp, [], d, option=O.options[0])
    assert r['status'] == 'fitted' and json.load(open(r['spec']))['hair']['shape']['mode'] == 'geom'
    assert r['changed'] == {'hair.shape.mode': ['mesh', 'geom']} and O.pending(None)[0]['name'] == 'anime'
    r = O.run(sp, ['--base', 'makehuman'], d, option=O.options[1])
    assert r['args'] == ['--base', 'makehuman', '--vrm'] and json.load(open(r['spec']))['base'] == 'anime'
    # a fit's eyes block alone
    fp = os.path.join(d, 'x.fit.json')
    json.dump({'name': 'x', 'hair': {'shape': {'mode': 'mesh'}}, 'head': {'chin': 1.3}, 'eyes': {'width': 0.22}}, open(fp, 'w'))
    K = {'head.chin': {'path': ('head', 'chin'), 'default': 1.0, 'step': 0.1, 'bounds': (0.5, 2.0), 'block': 'face'},
         'eyes.width': {'path': ('eyes', 'width'), 'default': 0.19, 'step': 0.01, 'bounds': (0.15, 0.25), 'block': 'eyes'}}
    S = json.load(open(fitters.with_block(sp, fp, K, 'eyes', os.path.join(d, 'x.eyes.json'))))
    assert S['eyes']['width'] == 0.22 and S['head']['chin'] == 1.0
    res = fitters.read_fit(d, sp, fp, K)
    assert res['changed'] == {'head.chin': [1.0, 1.3], 'eyes.width': [0.2, 0.22]} and set(res['blocks']) == {'face', 'eyes'}


def test_triage_decisions():
    spec = {'name': 'x'}
    cfg = {'decisions': [{'checks': ['sheet_shown_*'], 'class': 'needs a capability', 'by': 'a reviewer',
                          'why': 'cull_face takes the cheek locks'}]}
    cls, detail, ev, also = triage.classify('sheet_shown_front', {'value': 0.4, 'status': 'WARN'}, _ctx(spec, {}, [], config=cfg))
    assert cls == 'needs a capability' and 'cull_face' in detail and 'by a reviewer' in detail and 'needs a knob' in also, (cls, also)


def test_triage_uncertain_and_built_evidence():
    spec = {'name': 'x'}
    face = F('face', ('sheet_*',), {})
    ctx = _ctx(spec, {}, [face], config={'uncertain': {'sheet': {'ratio': 0.03}}})
    cls, detail, _, _ = triage.classify('sheet_width', {'value': 0.90, 'status': 'WARN'}, ctx)   # |0.10|-0.08 <= 0.03
    assert cls == 'measurement uncertain' and 'stated error' in detail, (cls, detail)
    cls, _, _, _ = triage.classify('sheet_width', {'value': 0.80, 'status': 'FAIL', 'missing': 0.4}, ctx)
    assert cls == 'measurement uncertain'
    # a standing scale caution is soft, unless the check is within the error it states
    cau = "scale: the sheet's eye spacing reads +3.5% against its figure height (used)"
    cls, _, _, also = triage.classify('body_front_feet', {'value': -0.45, 'design': -5.19, 'status': 'FAIL', 'caution': cau}, ctx)
    assert cls == 'needs a knob' and 'measurement uncertain' in also, (cls, also)
    cls, detail, _, _ = triage.classify('body_front_feet', {'value': -0.2, 'design': -5.19, 'status': 'FAIL', 'caution': cau}, ctx)
    assert cls == 'measurement uncertain' and 'own stated error' in detail, (cls, detail)   # 0.2 - 0.08 <= 3.5% of 5.19
    cls, _, _, _ = triage.classify('palette_dark_lit', {'value': 11.0, 'status': 'FAIL', 'caution': 'few design pixels (40)'}, ctx)
    assert cls == 'measurement uncertain'
    # an expression the template has nothing close to: a template addition
    cls, detail, _, _ = triage.classify('expr_yawn_mouth', {'value': 1.4, 'status': 'FAIL', 'match': 'laugh',
                                                            'missing': 'the library has nothing within tolerance: add it to the template'}, ctx)
    assert cls == 'needs a capability' and 'add it to the template' in detail, (cls, detail)
    # a rejected checkpoint that improved the check while another regressed: a measured trade-off
    recs = [{'event': 'compare', 'verdict': 'reject', 'checkpoint': 3, 'against': 1,
             'rows': [{'check': 'sheet_width', 'base': [0.80, 'FAIL'], 'cand': [0.95, 'PASS'], 'verdict': 'improved'}],
             'regressed': [{'check': 'eye_width', 'base': [1.0, 'PASS'], 'cand': [0.85, 'WARN'], 'verdict': 'regressed'}]}]
    recs.insert(0, {'event': 'checkpoint', 'id': 3, 'label': 'face'})
    # a trivial gain in the same rejected move is no evidence of a trade-off
    tiny = [dict(recs[1], rows=[{'check': 'sheet_width', 'base': [0.80, 'FAIL'], 'cand': [0.801, 'FAIL'], 'verdict': 'value'}])]
    assert triage.build_evidence(tiny, 'sheet_width') == ([], [])
    cls, detail, ev, _ = triage.classify('sheet_width', {'value': 0.80, 'status': 'FAIL'}, _ctx(spec, {}, [face], recs))
    assert cls == 'trade-off' and 'eye_width PASS -> WARN' in detail and '(face)' in detail and ev['built_conflicts'], (cls, detail)


def test_blocked_moves():
    face = F('face', ('sheet_*',), {})
    recs = [{'event': 'checkpoint', 'id': 4, 'label': 'face'},
            {'event': 'compare', 'checkpoint': 4, 'against': 1, 'verdict': 'reject', 'score': [142.3, 134.8],
             'regressed': [{'check': 'sheet_profile_chin', 'base': [-0.006, 'PASS'], 'cand': [-0.03, 'WARN']},
                           {'check': 'expr_yawn_eye', 'base': [0.1, 'PASS'], 'cand': [0.3, 'WARN']}]},
            {'event': 'compare', 'checkpoint': 5, 'against': 1, 'verdict': 'reject', 'score': [142.3, 150.0], 'regressed': []}]
    M = triage.blocked_moves(recs, [face])
    assert len(M) == 1 and M[0]['gain'] == 7.5 and M[0]['label'] == 'face'
    assert [b['objective'] for b in M[0]['blocked_by']] == [['face'], None]
    md = triage.markdown([], 't', moves=M)
    assert 'outside every objective' in md and 'in face' in md


def test_triage_ranks_visible_and_far_first():
    spec = {'name': 'x'}
    ctx = _ctx(spec, {}, [])
    its = triage.items(qa(face_folds=(1014, 'FAIL'), eye_aspect=(0.70, 'FAIL'), sheet_width=(0.90, 'WARN'), shape_iou=(0.9, 'PASS')), ctx)
    assert [i['check'] for i in its] == ['eye_aspect', 'face_folds', 'sheet_width'], [(i['check'], i['rank_score']) for i in its]
    assert all(i['rank'] == n + 1 for n, i in enumerate(its))


# ------------------------------------------------------------------------------------------------------------ history
def test_measurement_steps():
    steps = [('hair_noise', 'aee5426', 'undithered')]
    if history.contains('aee5426', '4fbfb92') is None:
        print('  (skipped: the commits are not in this checkout)'); return
    assert history.contains('aee5426', 'aee5426') and history.contains('4fbfb92', 'aee5426') is False
    assert history.remeasured('4fbfb92', 'aee5426+dirty', ['hair_noise', 'sheet_width'], steps) == {'hair_noise': 'undithered'}
    assert history.remeasured('aee5426', 'aee5426', ['hair_noise'], steps) == {}
    rows = [{'git': '4fbfb92', 'checks': {'hair_noise': [0.6, 'FAIL']}}, {'git': 'aee5426', 'checks': {'hair_noise': [0.31, 'FAIL']}},
            {'git': 'aee5426+dirty', 'checks': {'hair_noise': [0.19, 'FAIL']}}]
    assert [p[1] for p in history.trend(rows, 'hair_noise', steps)] == [0.31, 0.19]


# ------------------------------------------------------------------------------------------------------------ review
def test_review_note_to_tickets():
    d = tempfile.mkdtemp()
    json.dump({'name': 'x', 'references': {}, 'authority': {'face_front': 'sheet'}}, open(os.path.join(d, 'manifest.json'), 'w'))
    b = os.path.join(d, 'build')
    os.makedirs(os.path.join(b, 'qa'))
    spec = {'name': 'x', 'ref': {'manifest': os.path.join(d, 'manifest.json'), 'authority': {'face_front': 'sheet'}}}
    json.dump(spec, open(os.path.join(b, 'x.spec.json'), 'w'))
    Q = qa(sheet_width=(1.02, 'PASS'), sheet_profile_chin=(-0.01, 'PASS'), face_shape_chin=(0.0, 'PASS'), eye_aspect=(0.7, 'FAIL'),
           shape_iou_hair=(0.97, 'PASS'), hair_noise=(0.3, 'FAIL'))
    Q['sheet'] = {'ours': {'front': {'chin': -0.40, 'widths': {'d55': 0.26, 'd75': 0.19}}},
                  'design': {'front': {'chin': -0.36, 'widths': {'d55': 0.27, 'd75': 0.20}}}}
    json.dump(Q, open(os.path.join(b, 'qa', 'qa.json'), 'w'))
    n1 = review.add_note(b, 'The face reads long', view='front')
    n2 = review.add_note(b, 'the eyes look too narrow')
    assert n1['region'] == 'face' and n2['region'] == 'eyes'
    t1 = review.ticket(b, n1['id'])                                     # its checks all pass: the metrics missed it
    assert t1['kind'] == 'measure' and t1['proposed']['check'] == 'sheet_face_length', t1
    assert set(t1['missed_by']) == {'sheet_width', 'sheet_profile_chin', 'face_shape_chin'}
    p = t1['proposed']['prototype']                                     # the face's length over width, ours / design's
    assert abs(p['value'] - (0.40 / 0.26) / (0.36 / 0.27)) < 1e-3 and p['status'] == 'FAIL', p
    assert t1['reference']['authority'] == 'sheet'
    t2 = review.ticket(b, n2['id'])                                     # eye_aspect fails: a work item on it
    assert t2['kind'] == 'work' and t2['checks'] == ['eye_aspect'], t2
    assert review.load_notes(b)['notes'][0]['ticket'] == t1['id']
    # "flat" bangs are the hair's shape (which passes), not its shading (which fails): the metrics missed it
    t3 = review.ticket(b, review.add_note(b, 'the bangs read as a flat helmet')['id'])
    assert t3['kind'] == 'measure' and t3['proposed']['check'] == 'hair_front_outline' and t3['missed_by'] == ['shape_iou_hair'], t3
    t4 = review.ticket(b, review.add_note(b, 'the hair shading looks noisy')['id'])
    assert t4['kind'] == 'work' and t4['checks'] == ['hair_noise'], t4
    # the triage lists the missing measurement, and the eye note ranks eye_aspect up
    ctx = _ctx(spec, {}, [], tickets=review.load_tickets(spec)['tickets'])
    its = triage.items(Q, ctx)
    m = next(i for i in its if i['check'] == 'sheet_face_length')
    assert m['class'] == 'needs a measurement' and m['status'] == 'PROVISIONAL FAIL', m     # measured again on this build
    # a later build whose face isn't long any more: the provisional number follows it
    Q2 = json.loads(json.dumps(Q))
    Q2['sheet']['ours']['front']['chin'] = -0.345
    m2 = next(i for i in triage.items(Q2, ctx) if i['check'] == 'sheet_face_length')
    assert m2['status'] == 'PROVISIONAL PASS' and m2['rank_score'] < m['rank_score'], m2
    e = next(i for i in its if i['check'] == 'eye_aspect')
    assert e['evidence']['review'][0]['ticket'] == t2['id']
    # once a check of that name exists, the ticket is landed
    Q['checks']['sheet_face_length'] = {'value': 1.15, 'status': 'FAIL'}
    json.dump(Q, open(os.path.join(b, 'qa', 'qa.json'), 'w'))
    assert [t['id'] for t in review.sync(spec, b)] == [t1['id']]


def test_knob_inventory():
    spec = {'name': 'x', 'ref': {'rig': 'r'}, 'head': {'chin': 1.0, 'low_wf': [0.3, 0.2]},
            'garments': [{'kind': 'shell', 'name': 'top', 'region': [['hips', -1, 3]], 'offset': 0.01},
                         {'kind': 'skirt', 'name': 'skirt', 'flare': 42}, {'kind': 'bow', 'size': 0.8}],
            'hair': {'hem': [[50, -58], [75, -70]], 'silhouette': {'hair_z': [0.1]}}}
    inv = fitters.inventory(spec)
    assert set(inv) == {'head.chin', 'head.low_wf', 'garments.top.offset', 'garments.skirt.flare', 'garments.bow_2.size',
                        'hair.hem'}, sorted(inv)


def test_probe_headroom():
    """the probe: the fit objective at the table's point against its best single knob step."""
    from charkit import fitkit
    K = [fitkit.Knob('head.cheek', ('head', 'cheek'), 1.0, 0.1, (0.5, 1.5), 'face')]
    T = [fitkit.Term('sheet_width', 'd55', 'ratio', 0.08, 'face_front', 'sheet', 'front', 'face')]
    spec = {'head': {'cheek': 1.0}}
    # a step up widens the face from 0.80 toward 1: headroom
    far = {'schema': 'charkit.sensitivity/1', 'knobs': {'head.cheek': {'value': 1.0, 'step': 0.1, 'group': 'face',
           'measures': {'sheet_width.d55': {'at': 0.80, 'minus': 0.75, 'plus': 0.86}}}}}
    r = fitters.probe_headroom(far, spec, T, K)
    assert r['best'][:2] == ['head.cheek', 'plus'] and r['headroom'] > 0.2, r
    # at the optimum both steps cost more: no headroom
    opt = {'schema': 'charkit.sensitivity/1', 'knobs': {'head.cheek': {'value': 1.0, 'step': 0.1, 'group': 'face',
           'measures': {'sheet_width.d55': {'at': 1.0, 'minus': 0.95, 'plus': 1.05}}}}}
    assert fitters.probe_headroom(opt, spec, T, K)['headroom'] <= 0


def test_merge_args():
    assert fitters.merge_args(['--base', 'anime', '--hair', 'mesh'], ['--hair', 'geom']) == ['--base', 'anime', '--hair', 'geom']
    assert fitters.merge_args([], ['--vrm']) == ['--vrm']


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
