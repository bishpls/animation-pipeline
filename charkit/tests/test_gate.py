"""charkit.gate's QA comparison and charkit.manifest's spec resolution (venv: run this file, or pytest)."""
import json, os, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import gate, manifest


def test_compare_qa_verdicts():
    a = {'checks': {'a': {'value': 1, 'status': 'PASS'}, 'b': {'value': 0.7, 'status': 'FAIL'}, 'c': {'value': 2, 'status': 'WARN'},
                    'd': {'value': 3, 'status': 'PASS'}, 'e': {'value': 1, 'status': 'INFO'}, 'f': {'value': 5, 'status': 'PASS'}}}
    b = {'checks': {'a': {'value': 0.5, 'status': 'FAIL'}, 'b': {'value': 0.9, 'status': 'PASS'}, 'c': {'value': 2.5, 'status': 'WARN'},
                    'e': {'value': 2, 'status': 'INFO'}, 'f': {'value': 5, 'status': 'PASS'}, 'g': {'value': 1, 'status': 'PASS'}}}
    b['checks']['h'] = {'value': 1, 'status': 'INFO'}
    a['checks']['i'] = {'value': 1, 'status': 'INFO'}
    v = {r['check']: r['verdict'] for r in gate.compare_qa(a, b)}
    assert v == {'a': 'regressed', 'b': 'improved', 'c': 'value', 'd': 'gone', 'e': 'value', 'g': 'new', 'h': 'new',
                 'i': 'removed'}, v




def test_a_check_retired_by_a_measurement_step_is_removed_not_gone():
    a = {'checks': {'expr_laugh_mouth': {'value': 0.11, 'status': 'PASS'}, 'sheet_width': {'value': 1.0, 'status': 'PASS'}}}
    b = {'checks': {}}
    rows = {r['check']: r['verdict'] for r in gate.compare_qa(a, b, {'expr_*': 'no expression reference'})}
    assert rows == {'expr_laugh_mouth': 'removed', 'sheet_width': 'gone'}


def test_load_steps_reads_another_trees_registry():
    """the gate reads the merged tree's STEPS (a branch registers the steps it brings), without importing it."""
    import tempfile
    from charkit import history
    here = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'history.py')
    assert history.load_steps(here) == [tuple(x) for x in history.STEPS]
    p = os.path.join(tempfile.mkdtemp(), 'history.py')
    open(p, 'w').write("X = 1\nSTEPS = [\n    ('sheet_*', 'abc1234', 'a reason '\n     'split over lines'),\n]\n")
    assert history.load_steps(p) == [('sheet_*', 'abc1234', 'a reason split over lines')]
    assert history.load_steps(p + '.missing') is None


def test_manifest_resolves_refs():
    d = tempfile.mkdtemp()
    mp = os.path.join(d, 'manifest.json')
    json.dump({'name': 'x', 'references': {'rig': {'path': 'rigs/x'}, 'key3d': {'path': 'keys/x.png'},
                                           'trellis': {'path': 'out/x.glb'},
                                           'sheet': {'path': 'refs/x.png', 'figures': {'heads': {'front': [0, 0, 1, 1]}}}},
               'authority': {'chin': 'sheet'}}, open(mp, 'w'))
    spec = {'ref': {'manifest': mp, 'fit': ['face']}, 'hair': {'shape': {'glb': 'ref:trellis'}}}
    s = manifest.resolve(spec)
    assert s['ref']['rig'] == 'rigs/x' and s['ref']['image'] == 'keys/x.png'
    assert s['ref']['sheet']['image'] == 'refs/x.png' and s['ref']['sheet']['heads']['front'] == [0, 0, 1, 1]
    assert s['hair']['shape']['glb'] == 'out/x.glb' and s['ref']['authority'] == {'chin': 'sheet'}
    assert manifest.resolve({'ref': {'rig': 'r'}}) == {'ref': {'rig': 'r'}}          # no manifest: unchanged


def test_twobytwo_scores_a_remeasured_check_under_the_old_measure():
    """the known case (tool/body round 3, d35fbaf): the flaps' measure changed (same-colour layers) as their geometry
    did; 'remeasured' hid a drop the old measure shows. Numbers: the evaluator's 2 x 2 in docs/workstreams/garments.md."""
    q = lambda **c: {'checks': {k: {'value': v, 'status': s} for k, (v, s) in c.items()}}
    base = q(piece_overskirt_panel_L=(0.525, 'WARN'), piece_overskirt_panel_R=(0.582, 'WARN'), piece_skirt=(0.80, 'PASS'),
             sheet_width=(1.0, 'PASS'))
    old_on_new = q(piece_overskirt_panel_L=(0.312, 'FAIL'), piece_overskirt_panel_R=(0.381, 'FAIL'), piece_skirt=(0.80, 'PASS'))
    new_on_old = q(piece_overskirt_panel_L=(0.456, 'FAIL'), piece_overskirt_panel_R=(0.526, 'WARN'), piece_skirt=(0.81, 'PASS'))
    cand = q(piece_overskirt_panel_L=(0.348, 'FAIL'), piece_overskirt_panel_R=(0.449, 'FAIL'), piece_skirt=(0.81, 'PASS'),
             piece_skirt_extent=(0.1, 'WARN'), sheet_width=(0.9, 'PASS'))
    rem = {'piece_overskirt_panel_*': 'same-colour layers', 'piece_skirt': 'same-colour layers',
           'piece_*_extent': 'new: a spring piece\'s lowest row'}
    rows = {r['check']: r for r in gate.twobytwo(base, cand, old_on_new, new_on_old, rem)}
    assert set(rows) == {'piece_overskirt_panel_L', 'piece_overskirt_panel_R', 'piece_skirt'}   # a new check has no 2 x 2
    L, R = rows['piece_overskirt_panel_L'], rows['piece_overskirt_panel_R']
    assert L['old'] == 'regressed' and R['old'] == 'regressed'          # WARN -> FAIL under the old measure
    assert L['new'] == 'value' and R['new'] == 'regressed'
    assert L['old_on_new'] == [0.312, 'FAIL'] and L['new_on_old'] == [0.456, 'FAIL']
    assert rows['piece_skirt']['old'] == 'same' and rows['piece_skirt']['new'] == 'same'
    assert gate.twobytwo_drops(rows.values()) == [('piece_overskirt_panel_L', ['old']),
                                                   ('piece_overskirt_panel_R', ['old', 'new'])]
    acc = gate.twobytwo(base, cand, old_on_new, new_on_old, rem, ['*_R'])
    assert {r['check']: r['accepted'] for r in acc}['piece_overskirt_panel_R']
    assert gate.twobytwo_drops(acc) == [('piece_overskirt_panel_L', ['old'])]          # accepted by name
    # the old measure couldn't read the new bundle: no old-measure verdicts, nothing flagged
    rows = gate.twobytwo(base, cand, None, None, rem)
    assert all(r['old'] in ('unmeasured', None) for r in rows)


def test_geometry_is_the_bundles_arrays_not_its_metadata():
    """two builds of one geometry differ in their bundles' metadata (the resolved spec's output paths, the time): the
    2x2 asks whether the arrays changed."""
    d = tempfile.mkdtemp()
    for k, (spec, arr) in {'a': ('/x/a', 'h1'), 'b': ('/x/b', 'h1'), 'c': ('/x/a', 'h2')}.items():
        os.makedirs(os.path.join(d, k, 'bundle'))
        json.dump({'spec': {'head_code': spec}, 'hashes': {'o/skin/eval/V': arr, 'img/iris': 'i'}, 'content': k},
                  open(os.path.join(d, k, 'bundle', 'bundle.json'), 'w'))
    g = {k: gate.geometry(os.path.join(d, k))[0] for k in 'abc'}
    assert g['a'] == g['b'] != g['c'] and gate.geometry(os.path.join(d, 'none')) == (None, {})



def test_build_cpu_seconds_count_the_build_and_what_it_waited_for(tmp_path=None):
    """the gate's slowness check is on CPU seconds (the build and every process it reaped), which parallel gates on a
    shared box don't inflate the way they inflate wall time."""
    import json, pathlib, subprocess, sys
    from charkit import gate
    tmp_path = tmp_path or pathlib.Path(tempfile.mkdtemp())
    c0 = gate._cpu_children()
    subprocess.run([sys.executable, '-c', 's = 0\nfor i in range(2000000): s += i'], check=True)
    assert gate._cpu_children() - c0 > 0.02
    assert gate._cpu(str(tmp_path)) is None
    json.dump({'cpu_seconds': 12.5}, open(tmp_path / 'cpu_seconds.json', 'w'))
    assert gate._cpu(str(tmp_path)) == 12.5


# ------------------------------------------------------------------------------------------------- policy K (2026-09-30)
def _q(**c):
    """qa.json checks from NAME=(value, status[, grade[, flag]])."""
    out = {}
    for k, v in c.items():
        d = {'value': v[0], 'status': v[1]}
        if len(v) > 2 and v[2]:
            d['grade'] = v[2]
        if len(v) > 3 and v[3]:
            d['flag'] = v[3]
        out[k] = d
    return {'checks': out}


def _judge(a, b, **rep):
    rep.setdefault('qa', gate.compare_qa(a, b, rep.get('remeasured')))
    rep.setdefault('hard', [])
    return gate.judge(rep, a, b)


def test_k_blocks_only_new_fails_flag_regressions_and_cpu():
    a = _q(iou=(0.9, 'PASS'), width=(1.0, 'PASS'), chin=(0.5, 'WARN'), info=(3, 'INFO'), gone_ok=(1, 'PASS'),
           art_spikes_boots=(0.01, 'PASS', 'PASS', 'boots'), art_points_sleeves=(1.2, 'WARN', 'WARN', 'sleeves'),
           art_mirror_waist=(1.1, 'WARN', 'WARN', 'waist'), art_bumps_legs=(0.3, 'WARN', 'WARN', 'thigh'))
    b = _q(iou=(0.7, 'FAIL'), width=(0.97, 'WARN'), chin=(0.52, 'WARN'), info=(4, 'INFO'), new_bad=(0, 'FAIL'),
           new_ok=(1, 'PASS'), art_spikes_boots=(0.05, 'WARN', 'WARN', 'boots'),
           art_points_sleeves=(2.4, 'WARN', 'FAIL', 'sleeves'),         # capped at WARN, its grade FAIL: a regression
           art_mirror_waist=(1.15, 'WARN', 'WARN', 'waist'))             # art_bumps_legs gone: a regression
    v, block, R = _judge(a, b, cpu_seconds=[100, 140])
    kinds = {(x['kind'], x.get('check')) for x in block}
    assert v == 'FAIL' and kinds == {('new FAIL', 'iou'), ('flag check regressed', 'art_spikes_boots'),
                                     ('flag check regressed', 'art_points_sleeves'),
                                     ('flag check regressed', 'art_bumps_legs')}, kinds
    assert [r['check'] for r in R['warn']] == ['width'] and [r['check'] for r in R['gone']] == ['gone_ok']
    assert [r['check'] for r in R['flag_values']] == ['art_mirror_waist'] and R['flag_values'][0]['flag'] == 'waist'
    assert [r['check'] for r in R['values']] == ['info', 'chin']         # the biggest move first (+33% before +4%)
    assert R['values'][0]['delta'] == 1 and abs(R['values'][1]['rel'] - 0.04) < 1e-9
    assert [r['check'] for r in R['new']] == ['new_ok'] and [r['check'] for r in R['new_failing']] == ['new_bad']
    # the same moves without the FAILs and flag regressions pass, reported
    b2 = _q(iou=(0.85, 'PASS'), width=(0.97, 'WARN'), chin=(0.52, 'WARN'), info=(4, 'INFO'),
            art_spikes_boots=(0.01, 'PASS', 'PASS', 'boots'), art_points_sleeves=(1.3, 'WARN', 'WARN', 'sleeves'),
            art_mirror_waist=(1.15, 'WARN', 'WARN', 'waist'), art_bumps_legs=(0.2, 'PASS', 'PASS', 'thigh'),
            gone_ok=(1, 'PASS'))
    v, block, R = _judge(a, b2, cpu_seconds=[100, 149])
    assert v == 'PASS' and not block and [r['check'] for r in R['improved']] == ['art_bumps_legs']
    v, block, R = _judge(a, b2, cpu_seconds=[100, 151])
    assert v == 'FAIL' and [x['kind'] for x in block] == ['build CPU']
    # the hard failures still block
    v, block, R = _judge(a, a, hard=[{'kind': 'tests failing', 'files': ['test_x.py']}])
    assert v == 'FAIL' and gate._why(block[0]) == 'tests failing: test_x.py'


def test_k_reads_the_2x2():
    base = _q(p_l=(0.52, 'WARN'), p_r=(0.58, 'WARN'), art_band_lower=(1.2, 'WARN', 'WARN', 'band'))
    rows = [dict(check='p_l', base=[0.52, 'WARN'], old_on_new=[0.31, 'FAIL'], new_on_old=[0.45, 'WARN'],
                 cand=[0.44, 'WARN'], old='regressed', new='value', accepted=False),
            dict(check='p_r', base=[0.58, 'WARN'], old_on_new=[0.50, 'WARN'], new_on_old=[0.60, 'PASS'],
                 cand=[0.55, 'WARN'], old='value', new='regressed', accepted=False),
            dict(check='art_band_lower', base=[1.2, 'WARN'], old_on_new=[1.3, 'WARN'], new_on_old=[0.9, 'PASS'],
                 cand=[1.25, 'WARN'], old='value', new='regressed', accepted=False)]
    rem = {'p_*': 'a new measure', 'art_band_lower': 'a new measure'}
    v, block, R = _judge(base, base, qa=[], twobytwo={'rows': rows, 'errors': {}}, remeasured=rem)
    assert [(x['check'], x['kind'][:8]) for x in block] == [('p_l', 'new FAIL'), ('art_band_lower', 'flag che')], block
    assert [r['check'] for r in R['twobytwo']] == ['p_r']
    rows[0]['accepted'] = True
    v, block, R = _judge(base, base, qa=[], twobytwo={'rows': rows, 'errors': {'old measure on the new geometry': 'x'}})
    assert [x['check'] for x in block] == ['art_band_lower'] and len(R['twobytwo']) == 2 and R['notes']


def test_the_report_and_its_summary(tmp_path=None):
    import pathlib
    d = str(tmp_path or pathlib.Path(tempfile.mkdtemp()))
    a = _q(iou=(0.9, 'PASS'), width=(1.0, 'PASS'))
    b = _q(iou=(0.9, 'PASS'), width=(0.97, 'WARN'))
    rep = dict(branch='tool/x', tip='abc1234', into='pipeline-3d', head='def5678', spec='charkit/spec/clawd.json',
               args=[], suffix='', t='2026-09-30T23:00:00', hard=[], tests={'test_a.py': 'ok'}, test_seconds={'test_a.py': 3.0},
               phases=[{'phase': 'setup', 'start': 0, 'seconds': 2.0, 'note': ''}], cpu_seconds=[100, 110],
               build={'candidate': 'built', 'why': 'the merge changes what the build reads: charkit/x.py (the build read it)'},
               base_build={'ok': True, 'cached': True}, cand_build={'ok': True, 'seconds': 200, 'cpu': 110,
                                                                   'steps': {'resolve': 20.5}, 'parts': {'blender': 70}},
               seconds=30.0)
    rep['qa'] = gate.compare_qa(a, b)
    rep['verdict'], rep['blocking'], rep['report'] = gate.judge(rep, a, b)
    rep['verdict_pre_k'] = gate.verdict_pre_k(rep)
    assert (rep['verdict'], rep['verdict_pre_k']) == ('PASS', 'FAIL')
    gate._write(rep, d, 'tool-x_abc1234')
    md = open(os.path.join(d, 'gate_tool-x_abc1234_into_def5678.md')).read()
    S = json.load(open(os.path.join(d, 'gate_tool-x_abc1234_into_def5678.summary.json')))
    assert '**PASS**' in md and 'Before K: FAIL' in md and '## Report (not blocking)' in md and '| width |' in md
    assert '| resolve | | 20.5 |' in md or 'resolve' in md
    assert S['verdict'] == 'PASS' and S['counts'] == {'warn': 1} and S['report']['warn'][0]['check'] == 'width'
    assert S['tests'] == {'n': 1, 'failed': [], 'seconds': 3.0} and S['cpu_ratio'] == 1.1
    full = json.load(open(os.path.join(d, 'gate_tool-x_abc1234_into_def5678.json')))
    assert full['summary']['verdict'] == 'PASS'


def test_rejudge_reads_an_old_report_under_k(tmp_path=None):
    import pathlib
    d = str(tmp_path or pathlib.Path(tempfile.mkdtemp()))
    a = _q(iou=(0.9, 'PASS'), art_spikes_boots=(0.01, 'PASS', 'PASS', 'boots'))
    b = _q(iou=(0.88, 'WARN'), art_spikes_boots=(0.01, 'PASS', 'PASS', 'boots'))
    for name, q, cpu in (('base_def5678_clawd_default', a, 100), ('cand_tool-x_abc1234_into_def5678_default', b, 120)):
        os.makedirs(os.path.join(d, name, 'qa'))
        json.dump(q, open(os.path.join(d, name, 'qa', 'qa.json'), 'w'))
        json.dump({'cpu_seconds': cpu}, open(os.path.join(d, name, 'cpu_seconds.json'), 'w'))
    old = dict(branch='tool/x', tip='abc1234', into='pipeline-3d', head='def5678', spec='charkit/spec/clawd.json', args=[],
               suffix='', verdict='FAIL', why='checks worse: iou', tests={'test_a.py': 'ok'}, qa=gate.compare_qa(a, b))
    p = os.path.join(d, 'gate_tool-x_abc1234_into_def5678.json')
    json.dump(old, open(p, 'w'))
    r = gate.rejudge(p)
    assert (r['verdict_then'], r['verdict_k'], r['flags_read'], r['counts'], r['cpu_ratio']) == \
        ('FAIL', 'PASS', True, {'warn': 1}, 1.2), r


def test_remote_reads_a_gate_jobs_branch_and_spec():
    from charkit import remote
    assert remote._gate_label('tool/x into pipeline-3d') == ('tool/x', None)
    assert remote._gate_label("tool/x into pipeline-3d --spec charkit/spec/clawd_mh.json --args '--base anime'") == \
        ('tool/x', 'charkit/spec/clawd_mh.json')
    assert remote._gate_label('tool/x into pipeline-3d --build (gate code tool/infra3)') == ('tool/x', None)


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
