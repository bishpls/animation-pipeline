"""charkit.calibrate: the registry, the triple's verdict, the gate's calibration requirement, the anti-gaming guard and
Michael's recorded acceptances (venv: run this file, or pytest)."""
import json, os, sys, tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import calibrate, gate


def _tree(files):
    d = tempfile.mkdtemp(prefix='calib-test-')
    for p, t in files.items():
        os.makedirs(os.path.dirname(os.path.join(d, p)), exist_ok=True)
        open(os.path.join(d, p), 'w').write(t if isinstance(t, str) else json.dumps(t))
    return d


def test_the_registry_is_read_without_running_it():
    src = "import nothing_here\nCALIBRATION = [\n    dict(check='bow_*', part='collar_flags', adapter='A', " \
          "known_bad='g3', baseline=['v'], shape=['piece_bow']),\n    {'check': 'x', 'part': 'p'},\n]\n"
    d = _tree({'charkit/calib/m.py': src, 'charkit/calib/__init__.py': ''})
    E = calibrate.entries(d)
    assert [e['check'] for e in E] == ['bow_*', 'x'] and E[0]['module'] == 'charkit.calib.m'
    assert calibrate.entry_for('bow_profile_ribbon', E)['shape'] == ['piece_bow']
    assert calibrate.shapes_of('bow_profile_ribbon', E) == ['piece_bow']
    # no entry: piece_<first word> when a qa.json has it
    assert calibrate.shapes_of('collar_x', [], ({'checks': {'piece_collar': {}}},)) == ['piece_collar']


def test_this_trees_registry_names_its_adapters():
    import importlib
    for e in calibrate.entries():
        mod = importlib.import_module(e['module'])
        A = getattr(mod, e['adapter'])
        for g in list(e.get('baseline') or ()) + list(e.get('probes') or ()):
            assert g in A.generators, (e['check'], g)
        assert e.get('known_bad') or e.get('no_known_bad') or e.get('kind') == 'score', e['check']


def _rec(design, bad=None, floor=None, cur=None, kind='shape', shape=None):
    D = {'%+d,%+d' % m: [v, s] for m, (v, s) in zip(calibrate.MOVES, design)}
    vals = [v for v, _ in design]
    r = dict(kind=kind, shape=shape, design=dict(moves=D, min=min(vals), max=max(vals), spread=max(vals) - min(vals),
                                                  median=float(np.median(vals))),
             known_bad=dict(name='kb', value=bad[0], status=bad[1]) if bad else dict(name=None),
             floor={'g': dict(median=floor[0], status=floor[1])} if floor else {},
             current=dict(value=cur[0], status=cur[1], margin=cur[2]) if cur else {})
    return calibrate.verdict(r)[0]


def test_the_verdicts():
    ok = [(0.95, 'PASS')] * 8
    assert _rec(ok, (0.5, 'FAIL'), (0.2, 'FAIL'), (0.8, 'PASS', 0.8)) == 'calibrated'
    assert _rec([(0.95, 'PASS')] * 7 + [(0.55, 'WARN')], (0.5, 'FAIL'), (0.2, 'FAIL')) == 'miscalibrated'  # look5's chin
    assert _rec(ok, (0.79, 'PASS'), (0.2, 'FAIL'), (0.79, 'PASS', 0.8)) == 'blind'            # hair_piece_bangs
    assert _rec(ok, (0.5, 'FAIL'), (0.9, 'PASS'), (0.8, 'PASS', 0.8)) == 'coarse'             # a random floor passes
    assert _rec(ok, (0.5, 'FAIL'), (0.4, 'WARN'), (0.45, 'PASS', 0.1)) == 'coarse'            # passes at the floor
    assert _rec(ok, None, (0.2, 'FAIL'), (0.8, 'PASS', 0.8)) == 'guard'
    assert _rec(ok, None, None, (0.8, 'PASS', None)) == 'unmeasured'      # nothing it must fail (sleeve_standoff)
    # a defect detector: a random stand-in may pass (it lacks the defect); its shape is guarded
    assert _rec(ok, (0.6, 'FAIL'), (0.0, 'PASS'), (0.1, 'PASS', 1.0), kind='defect', shape=['piece_bow']) == \
        'calibrated'


def test_the_gate_asks_new_and_remeasured_checks_for_records():
    qa_a = {'checks': {'old': {'value': 1, 'status': 'PASS'}, 'rem': {'value': 1, 'status': 'PASS'},
                       'rem2': {'value': 1, 'status': 'PASS'}}}
    qa_b = {'checks': dict(qa_a['checks'], new1={'value': 0.1, 'status': 'PASS'}, new2={'value': 5, 'status': 'FAIL'},
                           info={'value': 1, 'status': 'INFO'})}
    rep = {'qa': [{'check': 'rem', 'verdict': 'remeasured', 'base': [1, 'PASS'], 'cand': [1.1, 'PASS']},
                  {'check': 'rem2', 'verdict': 'remeasured', 'base': [1, 'PASS'], 'cand': [1.2, 'PASS']}]}
    good = {'check': 'new1', 'verdict': 'calibrated'}
    head = _tree({'charkit/calib/records/rem.json': {'check': 'rem', 'verdict': 'calibrated', 'at': 'then'},
                  'charkit/calib/records/rem2.json': {'check': 'rem2', 'verdict': 'calibrated', 'at': 'then'}})
    merged = _tree({'charkit/calib/records/new1.json': good,
                    'charkit/calib/records/rem.json': {'check': 'rem', 'verdict': 'calibrated', 'at': 'then'},
                    'charkit/calib/records/rem2.json': {'check': 'rem2', 'verdict': 'blind', 'at': 'now'}})
    got = {r['check']: r for r in calibrate.requirements(merged, head, qa_a, qa_b, rep)['rows']}
    assert set(got) == {'new1', 'new2', 'rem', 'rem2'}                        # (the INFO check needs none)
    assert got['new1']['ok'] and got['new2']['record'] == 'missing' and not got['new2']['ok']
    assert got['rem']['record'] == 'stale' and got['rem2']['record'] == 'blind' and not got['rem2']['ok']
    # judged: each blocks with a one-line message
    rep = dict(rep, calibration={'rows': list(got.values())}, guard=[], hard=[])
    v, block, R = gate.judge(rep, qa_a, qa_b)
    msgs = [gate._why(b) for b in block]
    assert v == 'FAIL' and len(block) == 3, msgs
    assert any(m.startswith('no calibration record: new2 (a new check') for m in msgs), msgs
    assert any('not refreshed: rem ' in m for m in msgs) and any('says blind: rem2' in m for m in msgs), msgs
    assert [r['check'] for r in R['calibration']] == ['new1']


def _bow_pair():
    """tool/bow cbca3ad into 3ebc3fb, as its gate read it: bow_profile_ribbon new (0.8684 FAIL on the old geometry
    under the new measure, 0.0789 PASS on the new) while piece_bow's profile fell 0.5535 -> 0.3406."""
    qa_a = {'checks': {'piece_bow': {'value': 0.696, 'status': 'WARN', 'views': {'front': 0.8025, 'three_quarter':
                                                                                   0.6284, 'profile': 0.5535}},
                       'art_outline_collar': {'value': 0.743, 'status': 'PASS', 'flag': 'x'}}}
    qa_b = {'checks': {'piece_bow': {'value': 0.735, 'status': 'WARN', 'views': {'front': 0.8671, 'three_quarter':
                                                                                   0.7455, 'profile': 0.3406}},
                       'bow_profile_ribbon': {'value': 0.0789, 'status': 'PASS', 'flag': 'the ribbons'},
                       'art_outline_collar': {'value': 0.742, 'status': 'PASS', 'flag': 'x'}}}
    rep = {'hard': [], 'qa': [{'check': 'bow_profile_ribbon', 'base': [None, None], 'cand': [0.0789, 'PASS'],
                               'verdict': 'new'},
                              {'check': 'piece_bow', 'base': [0.696, 'WARN'], 'cand': [0.735, 'WARN'], 'verdict': 'value'},
                              {'check': 'art_outline_collar', 'base': [0.743, 'PASS'], 'cand': [0.742, 'PASS'],
                               'verdict': 'value'},
                              {'check': 'bow_front_loop_width', 'base': [None, None], 'cand': [0.002, 'PASS'],
                               'verdict': 'new'}],
           'twobytwo': {'rows': [{'check': 'bow_profile_ribbon', 'base': None, 'old_on_new': None,
                                  'new_on_old': [0.8684, 'FAIL'], 'cand': [0.0789, 'PASS'], 'old': None,
                                  'new': 'improved', 'accepted': False},
                                 # (read on both geometries and no better: not an improvement, though it's new)
                                 {'check': 'bow_front_loop_width', 'base': None, 'old_on_new': None,
                                  'new_on_old': [0.0, 'PASS'], 'cand': [0.002, 'PASS'], 'old': None, 'new': 'value',
                                  'accepted': False}]}}
    return rep, qa_a, qa_b


def test_the_guard_blocks_the_bow_pair():
    rep, qa_a, qa_b = _bow_pair()
    E = [dict(check='bow_*', shape=['piece_bow'])]
    is_flag = lambda k: bool((qa_b['checks'].get(k) or {}).get('flag'))
    G = calibrate.guard(rep, qa_a, qa_b, is_flag, E=E, R={})
    assert [(g['check'], g['shape'], g['view']) for g in G] == [('bow_profile_ribbon', 'piece_bow', 'profile')], G
    assert abs(G[0]['rel'] + 0.385) < 0.01
    v, block, R = gate.judge(dict(rep, guard=G), qa_a, qa_b)
    assert v == 'FAIL' and block[0]['kind'] == 'anti-gaming guard'
    assert 'piece_bow fell in profile 0.553 -> 0.341 (-38%)' in gate._why(block[0]), gate._why(block[0])
    # a 10% drop doesn't block; neither does a flag check that didn't improve
    qa_b2 = json.loads(json.dumps(qa_b))
    qa_b2['checks']['piece_bow']['views']['profile'] = 0.50
    assert not calibrate.guard(rep, qa_a, qa_b2, is_flag, E=E, R={})
    # Michael's acceptance (recorded in the merged tree) reports it instead, with who, when and why
    acc = {'bow_profile_ribbon': dict(check='bow_profile_ribbon', by='Michael', at='2026-09-30T20:00:00', why='as drawn')}
    v, block, R = gate.judge(dict(rep, guard=G, accepted=acc), qa_a, qa_b)
    assert v == 'PASS' and R['accepted'][0]['accepted']['by'] == 'Michael'


def test_an_accepted_new_fail_is_reported_not_blocking():
    qa_a = {'checks': {'c': {'value': 0.1, 'status': 'PASS'}}}
    qa_b = {'checks': {'c': {'value': 0.5, 'status': 'FAIL'}}}
    rep = {'hard': [], 'branch': 'tool/x', 'qa': gate.compare_qa(qa_a, qa_b), 'guard': []}
    assert gate.judge(rep, qa_a, qa_b)[0] == 'FAIL'
    d = tempfile.mkdtemp()
    a = calibrate.accept('c', by='Michael', why='the drawing is ambiguous there', value=0.5, branch='tool/x', root=d)
    assert json.load(open(os.path.join(d, calibrate.ACCEPTED, 'c.json')))['by'] == 'Michael'
    acc = calibrate.accepted(d)
    v, block, R = gate.judge(dict(rep, accepted=acc), qa_a, qa_b)
    assert v == 'PASS' and R['accepted'][0]['accepted']['why'] == 'the drawing is ambiguous there'
    # an acceptance for another branch doesn't cover this one
    assert gate.judge(dict(rep, branch='tool/y', accepted=acc), qa_a, qa_b)[0] == 'FAIL'
    try:
        calibrate.accept('c', by='', why='')
        raise AssertionError('accept without who and why')
    except SystemExit:
        pass


def test_an_accepted_flag_regression_covers_its_reading_only():
    from charkit import registry
    qa_a = {'checks': {'f': {'value': 1.804, 'status': 'PASS', registry.FLAG: 'a flag'}}}
    qa_b = {'checks': {'f': {'value': 2.111, 'status': 'WARN', registry.FLAG: 'a flag'}}}
    rep = {'hard': [], 'branch': 'tool/x', 'qa': gate.compare_qa(qa_a, qa_b), 'guard': []}
    v, block, _ = gate.judge(rep, qa_a, qa_b)
    assert v == 'FAIL' and block[0]['kind'] == 'flag check regressed'
    d = tempfile.mkdtemp()
    calibrate.accept('f', by='Michael', why='the side locks', value=2.111, status='WARN', branch='tool/x', root=d)
    acc = calibrate.accepted(d)
    v, block, R = gate.judge(dict(rep, accepted=acc), qa_a, qa_b)
    assert v == 'PASS' and R['accepted'][0]['check'] == 'f'
    # a further regression (another value, or FAIL) is not covered
    qa_c = {'checks': {'f': {'value': 2.4, 'status': 'WARN', registry.FLAG: 'a flag'}}}
    rep_c = dict(rep, qa=gate.compare_qa(qa_a, qa_c), accepted=acc)
    assert gate.judge(rep_c, qa_a, qa_c)[0] == 'FAIL'
    # an acceptance recorded for a new FAIL (status FAIL) doesn't cover a WARN regression
    calibrate.accept('f', by='Michael', why='x', value=2.111, branch='tool/x', root=d)
    assert gate.judge(dict(rep, accepted=calibrate.accepted(d)), qa_a, qa_b)[0] == 'FAIL'


def test_the_stand_ins():
    from charkit.calib import labels
    a = np.zeros((20, 20), int) - 1
    a[5:10, 5:10] = 3
    s = labels._shift(a, 2, -1, -1)
    assert (s == 3).sum() == 25 and s[7, 4] == 3 and s[5, 9] == -1
    rng = np.random.default_rng(0)
    region = np.zeros((40, 40), bool)
    region[5:35, 5:35] = True
    V = labels.voronoi(region, [1, 2, 3], [1, 1, 1], 9, rng)
    assert set(np.unique(V[region])) <= {1, 2, 3} and (V[~region] == -1).all()
    m = np.zeros((60, 60), bool)
    m[20:40, 20:40] = True
    b = labels.affine(m, np.random.default_rng(1), ppl=100)
    assert b.any() and not np.array_equal(b, m) and abs(b.sum() / m.sum() - 1) < 0.3


def test_store_and_accept_write_through_read_only_hard_links():
    """a box's copy of the worktree hard-links its synced files read-only from a blob cache (charkit/bucketsync.py): storing
    a known-bad (or accepting a check, or writing a record) over an existing file raised PermissionError and failed 22 box
    calibrate jobs on 2026-10-01. Each write replaces the file; the shared blob is untouched."""
    root = tempfile.mkdtemp(prefix='calib-ro-')
    blobs = os.path.join(root, 'blobs')
    os.makedirs(blobs)
    src = os.path.join(root, 'out', 'b1')
    for sub, f, body in (('bundle', 'bundle.json', {'spec': {'p': src + '/geom/x'}}), ('qa', 'qa.json', {'checks': {'a': {}}})):
        os.makedirs(os.path.join(src, sub))
        json.dump(body, open(os.path.join(src, sub, f), 'w'))
    old = (calibrate.ROOT, calibrate.STORE)
    calibrate.ROOT, calibrate.STORE = root, os.path.join(root, 'store')
    try:
        for target, call in (
                (os.path.join(root, calibrate.KNOWN, 'kb.json'), lambda: calibrate.store('kb', src, why='first')),
                (os.path.join(root, calibrate.ACCEPTED, 'chk.json'), lambda: calibrate.accept('chk', 'm', 'why', root=root))):
            os.makedirs(os.path.dirname(target), exist_ok=True)
            blob = os.path.join(blobs, os.path.basename(target))
            open(blob, 'w').write('{"old": 1}')
            os.link(blob, target)
            os.chmod(blob, 0o444)                           # the cache's mode: a write through the link would fail
            call()
            assert json.load(open(blob)) == {'old': 1}, 'the shared blob was written through'
            assert 'old' not in json.load(open(target))
        # the stored bundle's own metadata too (store/NAME/bundle/bundle.json, a link into a previous store)
        calibrate.store('kb', src, why='second')
        assert json.load(open(os.path.join(root, calibrate.KNOWN, 'kb.json')))['why'] == 'second'
    finally:
        calibrate.ROOT, calibrate.STORE = old


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
