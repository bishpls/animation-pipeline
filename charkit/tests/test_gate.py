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
    v, block, R = _judge(a, b2, cpu_seconds=[100, 151], cpu_threads=[4, 4])
    assert v == 'FAIL'
    v, block, R = _judge(a, b2, cpu_seconds=[100, 251], cpu_threads=[None, 4])     # an uncapped baseline: reported
    assert v == 'PASS' and 'different thread caps' in R['notes'][0]
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
    v, block, R = _judge(base, base, qa=[], twobytwo={'rows': rows, 'errors': {}})
    assert [x['check'] for x in block] == ['art_band_lower'] and len(R['twobytwo']) == 2
    # a crossed QA that couldn't run blocks: its remeasured checks are unverified (the 2x2 never skips silently)
    v, block, R = _judge(base, base, qa=[], twobytwo={'rows': rows, 'errors': {'old measure on the new geometry': 'x'}})
    assert v == 'FAIL' and block[0]['kind'] == 'the 2x2 could not run the old measure on the new geometry', block
    for r in rows:
        r['accepted'] = True                                     # unless every row is accepted by name: a note
    v, block, R = _judge(base, base, qa=[], twobytwo={'rows': rows, 'errors': {'old measure on the new geometry': 'x'}})
    assert v == 'PASS' and R['notes'], block


def test_the_2x2_blocks_a_crossed_cell_it_could_not_measure():
    """tool/hairtag 37c09cf's gate (into 4de65ab): the baseline cached, so its worktree had never built and had no
    produced hair layers; the old measure's QA there skipped hair_pieces, and every old-measure cell read 'unmeasured'
    while the gate passed. Now a missing crossed cell of a check the old measure has blocks, read from the cells (so
    --rejudge catches the old report's rows too), and each tree's produced references are made before its crossed QA."""
    q = lambda **c: {'checks': {k: {'value': v, 'status': s} for k, (v, s) in c.items()}}
    base = q(hair_piece_bangs=(0.762, 'PASS'), hair_piece_ahoge=(0.267, 'INFO'), hair_tips_front=(5, 'INFO'))
    cand = q(hair_piece_bangs=(0.786, 'PASS'), hair_piece_ahoge=(0.323, 'INFO'), hair_tips_front=(5, 'INFO'),
             hair_piece_new=(0.5, 'PASS'))
    new_on_old = q(hair_piece_bangs=(0.786, 'PASS'), hair_piece_ahoge=(0.356, 'INFO'), hair_tips_front=(5, 'INFO'))
    old_on_new = {'checks': {'hair_pieces': {'status': 'SKIPPED', 'why': 'no hair_layers produced'}}}
    rem = {'hair_piece_*': 'the remade layers', 'hair_tips_*': 'the remade layers'}
    rows = {r['check']: r for r in gate.twobytwo(base, cand, old_on_new, new_on_old, rem)}
    assert rows['hair_piece_bangs']['old'] == 'unmeasured'
    assert rows['hair_piece_bangs']['unmeasured'] == ['old measure on the new geometry']
    assert 'hair_piece_new' not in rows          # a check the branch adds, unmeasured on the old geometry: no 2x2 row
    v, block, R = _judge(base, cand, qa=[], twobytwo={'rows': list(rows.values()), 'errors': {}})
    assert v == 'FAIL' and sorted(b['check'] for b in block) == ['hair_piece_ahoge', 'hair_piece_bangs',
                                                                 'hair_tips_front'], block
    assert "couldn't measure" in gate._why(block[0]) and 'old measure on the new geometry' in gate._why(block[0])
    # an old report's rows (no 'unmeasured' key, old_on_new None): read the same way
    old = [{k: v for k, v in r.items() if k != 'unmeasured'} for r in rows.values()]
    for r in old:
        r['old_on_new'] = None
    assert _judge(base, cand, qa=[], twobytwo={'rows': old, 'errors': {}})[0] == 'FAIL'
    # the new measure unmeasured on the old geometry blocks too, and a SKIPPED cell counts as unmeasured
    new_on_old2 = q(hair_piece_bangs=(None, 'SKIPPED'))
    rows = {r['check']: r for r in gate.twobytwo(base, cand, q(hair_piece_bangs=(0.7, 'PASS')), new_on_old2,
                                                   {'hair_piece_bangs': 'x'})}
    assert rows['hair_piece_bangs']['unmeasured'] == ['new measure on the old geometry']
    assert rows['hair_piece_bangs']['new'] == 'unmeasured'
    # everything measured: nothing blocks
    rows = gate.twobytwo(base, cand, base, new_on_old, rem)
    assert not any(r['unmeasured'] for r in rows)
    assert _judge(base, cand, qa=[], twobytwo={'rows': rows, 'errors': {}})[0] == 'PASS'


def test_produce_inputs_runs_the_trees_own_code():
    """the produced references made in a tree by that tree's charkit (a stand-in package), from the gate's spec; a
    failure is reported, not swallowed."""
    t = tempfile.mkdtemp()
    os.makedirs(os.path.join(t, 'charkit', 'spec'))
    open(os.path.join(t, 'charkit', '__init__.py'), 'w').write('')
    open(os.path.join(t, 'charkit', 'character.py'), 'w').write('def check_spec(s):\n    return s\n')
    open(os.path.join(t, 'charkit', 'manifest.py'), 'w').write(
        'import os\n'
        'def resolve(s):\n    return s\n'
        'def load(p):\n    return {"references": {"layers": {"path": "out/l.npz", "produced_by": "x"}, "sheet": {"path": "s"}}}\n'
        'def produced(s, k):\n'
        '    os.makedirs("out", exist_ok=True); open("out/%s.made" % k, "w").write(s["name"]); return "out/l.npz"\n')
    json.dump({'name': 'n', 'ref': {'manifest': 'm.json'}}, open(os.path.join(t, 'charkit', 'spec', 'n.json'), 'w'))
    assert gate.produce_inputs(t, 'charkit/spec/n.json') is None
    assert os.listdir(os.path.join(t, 'out')) == ['layers.made']                 # only the produced ones
    assert 'exit 1' in gate.produce_inputs(t, 'charkit/spec/missing.json')


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


def test_remote_gate_names_its_own_report_never_the_newest(tmp_path=None):
    """a gate job's report is the one in its own folder (by the gate's id) of its branch at its sha into its head,
    copied into charkit/out/gate and named; another branch's report, newer or not, is never taken for it, and a gate
    with none says so and doesn't exit 0 (tool/mouth3's follow printed tool/infra-auth's PASS, 2026-09-30)."""
    import io, contextlib
    from charkit import remote
    root = tmp_path or tempfile.mkdtemp()
    own = os.path.join(root, 'charkit', 'out', 'remote', 'gates', 'tool_mouth3-5b6fd763')
    os.makedirs(own)

    def put(folder, branch, tip, head, verdict, t):
        stem = os.path.join(folder, 'gate_%s_%s_into_%s' % (branch.replace('/', '-'), tip, head))
        json.dump(dict(branch=branch, tip=tip, head=head, verdict=verdict, t=t), open(stem + '.json', 'w'))
        json.dump(dict(verdict=verdict), open(stem + '.summary.json', 'w'))
        open(stem + '.md', 'w').write('# %s %s\n' % (branch, verdict))
        return stem + '.md'
    mine = put(own, 'tool/mouth3', 'b4f049f', '4007276', 'FAIL', '2026-09-30T14:18')
    # (an older report of the same branch at another sha, in the same folder: not this gate's)
    put(own, 'tool/mouth3', '1111111', '4007276', 'PASS', '2026-09-30T14:30')
    other = os.path.join(root, 'charkit', 'out', 'gate')
    os.makedirs(other)
    put(other, 'tool/infra-auth', 'c488918', '4007276', 'PASS', '2026-09-30T14:19')       # newer, another branch
    assert remote.gate_report(own, 'tool/mouth3', 'b4f049f074051ab7', '4007276b7a3e') == mine
    assert remote.gate_report(own, 'tool/infra-auth', 'c488918', '4007276') is None
    assert remote.gate_report(other, 'tool/mouth3', 'b4f049f', '4007276') is None
    old = remote.ROOT
    remote.ROOT = root
    try:
        what = dict(gate='tool_mouth3-5b6fd763', to=os.path.relpath(own, root), reports='charkit/out/gate',
                    report=dict(branch='tool/mouth3', tip='b4f049f0740', head='4007276b7a3', into='pipeline-3d'))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = remote.gate_result(what, 1)
        assert code == 1 and 'tool/mouth3 (b4f049f) into pipeline-3d (4007276): FAIL' in buf.getvalue(), buf.getvalue()
        assert os.path.exists(os.path.join(other, os.path.basename(mine)))
        # a job whose report didn't come back: named as missing, and no PASS claimed
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = remote.gate_result(dict(what, report=dict(what['report'], tip='2222222')), 0)
        assert code == 1 and 'no report of tool/mouth3 (2222222)' in buf.getvalue(), buf.getvalue()
    finally:
        remote.ROOT = old



def _carry_repo():
    """a tiny repo: main at H0, a branch changing the code the build reads, and a gate report of it into H0 holding the
    three closures (the baseline and candidate read kit/core.py and kit/clawd.json; the tests read their file and
    kit/core.py)."""
    import subprocess
    root = tempfile.mkdtemp()
    g = lambda *a: subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@t', *a], cwd=root,
                                  capture_output=True, text=True, check=True).stdout.strip()
    files = {'kit/core.py': 'X = 1\n', 'kit/clawd.json': '{}\n', 'kit/unused.py': 'U = 1\n', 'docs/n.md': 'n\n',
             'kit/helper.py': 'H = 1\n', '.gitignore': 'charkit/out/\n',
             'charkit/tests/test_x.py': "assert 'BAD' not in open('kit/helper.py').read()\n"}
    for p, t in files.items():
        os.makedirs(os.path.dirname(os.path.join(root, p)) or root, exist_ok=True)
        open(os.path.join(root, p), 'w').write(t)
    g('init', '-q', '-b', 'main'); g('add', '-A'); g('commit', '-qm', 'h0')
    h0 = g('rev-parse', '--short', 'HEAD')
    g('checkout', '-qb', 'br'); open(os.path.join(root, 'kit/core.py'), 'w').write('X = 2\n')
    g('commit', '-qam', 'geometry'); tip = g('rev-parse', '--short', 'HEAD'); g('checkout', '-q', 'main')
    gd = os.path.join(root, 'charkit', 'out', 'gate')
    os.makedirs(gd)
    rep = dict(branch='br', tip=tip, into='main', head=h0, spec='kit/clawd.json', args=[], suffix='', t='2026-09-30T01:00',
               hard=[], blocking=[], report={}, verdict='PASS', tests={'test_x.py': 'ok'}, build={'candidate': 'built'},
               base_build={'ok': True}, cand_build={'ok': True}, qa=[], phases=[],
               closures={'base': {'reads': ['kit/core.py', 'kit/clawd.json']},
                         'cand': {'reads': ['kit/core.py', 'kit/clawd.json']},
                         'tests': {'paths': ['charkit/tests/test_x.py', 'kit/core.py', 'kit/helper.py'],
                                   'files': {'test_x.py': {'reads': [0, 1, 2], 'listed': [], 'scans': {}}}}})
    json.dump(rep, open(os.path.join(gd, 'gate_br_%s_into_%s.json' % (tip, h0)), 'w'))
    return root, g, gd


def test_a_gate_carries_over_when_the_target_moves_without_reaching_it():
    _carry_cases()


def test_the_carry_on_a_git_without_merge_tree_write_tree():
    """the build box's git (2.34) has no `merge-tree --write-tree`: the merge runs in a throwaway worktree instead."""
    gate._OLD_GIT.append(True)
    try:
        _carry_cases()
    finally:
        gate._OLD_GIT.clear()


def _carry_cases():
    import subprocess
    root, g, gd = _carry_repo()
    kw = dict(into='main', spec='kit/clawd.json', reports=gd, root=root)
    # main moves: docs and a module nothing read -> the PASS carries, and a report for the new head is written
    open(os.path.join(root, 'docs/n.md'), 'w').write('m\n'); open(os.path.join(root, 'kit/unused.py'), 'w').write('U=2\n')
    g('commit', '-qam', 'docs'); h1 = g('rev-parse', '--short', 'HEAD')
    r = gate.carry('br', **kw)
    assert r['carried'] and r['verdict'] == 'PASS' and r['report'].endswith('_into_%s.md' % h1), r
    S = json.load(open(r['report'][:-3] + '.summary.json'))
    assert S['verdict'] == 'PASS' and S['carried']['from_head'] != h1 and S['head'] == h1
    assert 'Carried over' in open(r['report']).read()
    # now gated into h1 (the carried report): asking again says so
    assert gate.carry('br', **kw)['why'].startswith('already gated')
    # main changes what the baseline reads -> not carried (the baseline and candidate would both differ)
    open(os.path.join(root, 'kit/clawd.json'), 'w').write('{"k": 1}\n'); g('commit', '-qam', 'spec')
    r = gate.carry('br', write=False, **kw)
    assert not r['carried'] and {'baseline', 'candidate'} <= set(r['hits']), r
    g('reset', '-q', '--hard', 'HEAD~1')
    # a test file added on main: it runs here, in a worktree of the merge; the builds carry
    open(os.path.join(root, 'charkit/tests/test_y.py'), 'w').write('pass\n'); g('add', '-A'); g('commit', '-qm', 't')
    r = gate.carry('br', write=False, **kw)
    assert r['carried'] and r['verdict'] == 'PASS' and r['tests_run']['files'] == ['test_y.py'], r
    assert not gate.carry('br', write=False, run_tests=False, **kw)['carried']
    # main changes what a test reads, and the test fails on the merge: carried as a FAIL
    open(os.path.join(root, 'kit/helper.py'), 'w').write('BAD\n'); g('commit', '-qam', 'h')
    r = gate.carry('br', **kw)
    assert r['carried'] and r['verdict'] == 'FAIL' and r['tests_run']['failed'] == ['test_x.py'], r
    assert json.load(open(r['report'][:-3] + '.summary.json'))['verdict'] == 'FAIL'
    assert subprocess.run(['git', 'worktree', 'list'], cwd=root, capture_output=True, text=True).stdout.count('\n') == 1
    g('reset', '-q', '--hard', 'HEAD~2')
    # the branch adds a notes commit after its gate: the earlier tip's report carries (the docs reach nothing)
    g('checkout', '-q', 'br'); open(os.path.join(root, 'docs/br.md'), 'w').write('branch notes\n')
    g('add', '-A'); g('commit', '-qm', 'notes'); g('checkout', '-q', 'main')
    r = gate.carry('br', **kw)
    assert r['carried'] and r['verdict'] == 'PASS' and r['report'], r
    assert json.load(open(r['report'][:-3] + '.summary.json'))['carried']['from_tip'] != r['tip']
    # then a code commit the candidate reads: not carried
    g('checkout', '-q', 'br'); open(os.path.join(root, 'kit/clawd.json'), 'w').write('{"b": 1}\n')
    g('commit', '-qam', 'code'); g('checkout', '-q', 'main')
    r = gate.carry('br', write=False, **kw)
    assert not r['carried'] and 'candidate' in r['hits'], r
    g('checkout', '-q', 'br'); g('reset', '-q', '--hard', 'HEAD~2'); g('checkout', '-q', 'main')
    # main edits the branch's line: the merge conflicts
    open(os.path.join(root, 'kit/core.py'), 'w').write('X = 3\n'); g('commit', '-qam', 'clash')
    r = gate.carry('br', write=False, **kw)
    assert not r['carried'] and 'cleanly' in r['why'], r


def test_the_carry_by_definition():
    """the move and the branch both touch files the builds read: at the level of definitions an infra-only move and a
    change beside the branch's carry, a move that meets the branch's change doesn't, and the file rule refused all."""
    import subprocess
    root = tempfile.mkdtemp()
    g = lambda *a: subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@t', *a], cwd=root,
                                  capture_output=True, text=True, check=True).stdout.strip()
    files = {'charkit/__init__.py': '', 'charkit/tests/test_x.py': 'assert True\n', '.gitignore': 'charkit/out/\n',
             'charkit/geo.py': 'def area():\n    return 1\n\n\ndef build():\n    return area() + 1\n\n\n'
                               'def trim():\n    return 0\n',
             'charkit/gate.py': 'def verdict():\n    return "PASS"\n', 'charkit/clawd.json': '{}\n'}
    for p, t in files.items():
        os.makedirs(os.path.dirname(os.path.join(root, p)), exist_ok=True)
        open(os.path.join(root, p), 'w').write(t)
    g('init', '-q', '-b', 'main'); g('add', '-A'); g('commit', '-qm', 'h0')
    h0 = g('rev-parse', '--short', 'HEAD')

    def edit(p, a, b):
        s = open(os.path.join(root, p)).read()
        assert a in s
        open(os.path.join(root, p), 'w').write(s.replace(a, b))
    g('checkout', '-qb', 'br'); edit('charkit/geo.py', 'return area() + 1', 'return area() + 2')   # the branch: build
    g('commit', '-qam', 'br'); tip = g('rev-parse', '--short', 'HEAD'); g('checkout', '-q', 'main')
    gd = os.path.join(root, 'charkit', 'out', 'gate')
    os.makedirs(gd)
    reads = ['charkit/geo.py', 'charkit/gate.py', 'charkit/clawd.json']      # (the old hashing read gate.py too)
    rep = dict(branch='br', tip=tip, into='main', head=h0, spec='charkit/clawd.json', args=[], suffix='',
               t='2026-09-30T01:00', hard=[], blocking=[], report={}, verdict='PASS', tests={'test_x.py': 'ok'},
               build={'candidate': 'skipped'}, base_build={'ok': True}, cand_build={'ok': True}, qa=[], phases=[],
               closures={'base': {'reads': reads}, 'cand': {'reads': reads},
                         'tests': {'paths': ['charkit/tests/test_x.py'],
                                   'files': {'test_x.py': {'reads': [0], 'listed': [], 'scans': {}}}}})
    json.dump(rep, open(os.path.join(gd, 'gate_br_%s_into_%s.json' % (tip, h0)), 'w'))
    kw = dict(into='main', spec='charkit/clawd.json', reports=gd, root=root, write=False)
    # an infra-only move (gate.py): carries by definition; the file rule refused it (the baseline read gate.py)
    edit('charkit/gate.py', '"PASS"', '"FAIL"'); g('commit', '-qam', 'infra')
    assert gate.carry('br', **kw)['carried']
    r = gate.carry('br', rule='files', **kw)
    assert not r['carried'] and 'baseline' in r['hits'], r
    # a move in the branch's own file, beside its change (trim: neither reaches the other): carries
    edit('charkit/geo.py', 'return 0', 'return 1'); g('commit', '-qam', 'trim')
    assert gate.carry('br', **kw)['carried']
    # a move changing what the branch's change calls (area): the two meet, not carried
    edit('charkit/geo.py', 'return 1\n\n\ndef build', 'return 3\n\n\ndef build'); g('commit', '-qam', 'area')
    r = gate.carry('br', **kw)
    assert not r['carried'] and 'charkit/geo.py:area' in str(r['hits'].get('definitions')), r
    g('reset', '-q', '--hard', 'HEAD~1')
    # the branch itself changes code the build reads after its gate: its candidate isn't the gated one, not carried
    g('checkout', '-q', 'br'); edit('charkit/geo.py', 'area() + 2', 'area() + 9'); g('commit', '-qam', 'more')
    g('checkout', '-q', 'main')
    r = gate.carry('br', **kw)
    assert not r['carried'] and 'charkit/geo.py' in str(r['hits'].get('candidate')), r
    g('checkout', '-q', 'br'); g('reset', '-q', '--hard', 'HEAD~1'); g('checkout', '-q', 'main')
    # a data file the builds read: as before, not carried
    edit('charkit/clawd.json', '{}', '{"a": 1}'); g('commit', '-qam', 'data')
    r = gate.carry('br', **kw)
    assert not r['carried'] and 'baseline' in r['hits'], r


def test_a_crossed_qa_reads_a_moved_builds_own_files():
    """a cached baseline's bundle names its build's files by the folder it was built in (another gate's clone, gone):
    the crossed QA measures a copy whose paths point where the build's folder is now, the export still beside it."""
    root = tempfile.mkdtemp()
    out = os.path.join(root, 'gate-out', 'base_abc_clawd_default')
    os.makedirs(os.path.join(out, 'bundle')); os.makedirs(os.path.join(out, 'geom', 'hair_pieces'))
    open(os.path.join(out, 'geom', 'hair_pieces', 'pieces.json'), 'w').write('{}')
    open(os.path.join(out, 'clawd.look.glb'), 'w').write('glb')
    open(os.path.join(out, 'bundle', 'arrays.npz'), 'w').write('npz')
    gone = '/srv/work/gates/old.tmp/charkit-gate-base-x/charkit/out/gate/base_abc_clawd_default'
    meta = {'schema': 1, 'spec': {'hair': {'shape': {'pieces': gone + '/geom/hair_pieces'}}, 'name': 'clawd',
                                  'other': '/nowhere/else.npz'}}
    json.dump(meta, open(os.path.join(out, 'bundle', 'bundle.json'), 'w'))
    b = gate.rebased_bundle(os.path.join(out, 'bundle'), os.path.join(root, 'x'))
    assert b != os.path.join(out, 'bundle')
    m = json.load(open(os.path.join(b, 'bundle.json')))
    assert m['spec']['hair']['shape']['pieces'] == os.path.join(os.path.realpath(out), 'geom', 'hair_pieces')
    assert m['spec']['other'] == '/nowhere/else.npz'                    # (not the build's: left alone)
    assert open(os.path.join(os.path.dirname(b), 'clawd.look.glb')).read() == 'glb'
    assert open(os.path.join(b, 'arrays.npz')).read() == 'npz'
    # a bundle whose paths resolve is measured where it is
    meta['spec']['hair']['shape']['pieces'] = os.path.join(out, 'geom', 'hair_pieces')
    json.dump(meta, open(os.path.join(out, 'bundle', 'bundle.json'), 'w'))
    assert gate.rebased_bundle(os.path.join(out, 'bundle'), os.path.join(root, 'y')) == os.path.join(out, 'bundle')


def test_both_sides_draw_from_the_same_export():
    q = lambda f: {'measured': {'draw': {'setting': 'render', 'export': f}}}
    assert gate.draw_exports(q('clawd.look.glb'), q('clawd.look.glb')) is None
    assert 'different exports' in gate.draw_exports(q('clawd.look.glb'), q('clawd.vrm'))
    assert gate.draw_exports({'checks': {}}, q('clawd.vrm')) is None           # (a report from before the record)
    import inspect
    from charkit import cli
    src = inspect.getsource(cli._build)
    assert "(['--vrm'] if '--vrm' in args else []) + ([] if '--no-look' in args else ['--look'])" in src


def test_docs_and_tests_can_reach_no_build():
    from charkit import closure
    C = {'reads': ['charkit/x.py', 'charkit/README.md'], 'listed': ['charkit/notes']}
    assert closure.unreadable([('M', 'docs/a.md'), ('A', 'charkit/tests/test_q.py')])
    assert closure.unreadable([('M', 'charkit/other.md')], C)
    assert not closure.unreadable([('M', 'charkit/other.md')])                 # no closure to check a doc against
    assert not closure.unreadable([('M', 'charkit/README.md')], C)             # a doc the build read
    assert not closure.unreadable([('A', 'charkit/notes/x.txt')], C)           # in a folder the build lists
    assert not closure.unreadable([('M', 'docs/a.md'), ('M', 'charkit/gate.py')], C)

if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
