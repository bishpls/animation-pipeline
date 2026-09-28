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


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
