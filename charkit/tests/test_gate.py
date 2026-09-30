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
    acc = {r['check']: r['accepted'] for r in gate.twobytwo(base, cand, old_on_new, new_on_old, rem, ['*_R'])}
    assert acc['piece_overskirt_panel_R'] and not acc['piece_overskirt_panel_L']
    # the old measure couldn't read the new bundle: no old-measure verdicts, nothing flagged
    rows = gate.twobytwo(base, cand, None, None, rem)
    assert all(r['old'] in ('unmeasured', None) for r in rows)


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)


def test_build_cpu_seconds_count_the_build_and_what_it_waited_for(tmp_path):
    """the gate's slowness check is on CPU seconds (the build and every process it reaped), which parallel gates on a
    shared box don't inflate the way they inflate wall time."""
    import json, subprocess, sys
    from charkit import gate
    c0 = gate._cpu_children()
    subprocess.run([sys.executable, '-c', 's = 0\nfor i in range(2000000): s += i'], check=True)
    assert gate._cpu_children() - c0 > 0.02
    assert gate._cpu(str(tmp_path)) is None
    json.dump({'cpu_seconds': 12.5}, open(tmp_path / 'cpu_seconds.json', 'w'))
    assert gate._cpu(str(tmp_path)) == 12.5
