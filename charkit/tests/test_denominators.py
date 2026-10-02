"""Declared denominators (infra round 5, 2026-10-01): every QA part declares how many checks it measures; qa3d.run records
each part's status against it, and the merge gate blocks a candidate whose part crashed, measured fewer checks than it
declares, or was left out by a QA profile. Motion QA crashed ('skirt: not a grid') from 0d53cb8 to e9cb156 and the gates
read its checks as gone, not blocking. (venv: run this file, or pytest)"""
import os, sys, tempfile

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, HERE)
from charkit import bundle, gate, qa3d, registry


def _ok(B, design=None, out=None):
    return None, {'a': {'value': 1.0, 'status': 'PASS'}, 'b': {'value': 2.0, 'status': 'WARN'}}


def _short(B, design=None, out=None):            # (one of its two checks not measured: a silent partial skip)
    return None, {'a': {'value': 1.0, 'status': 'PASS'}, 'b': {'status': 'SKIPPED', 'why': 'no input'}}


def _boom(B, design=None, out=None):
    raise ValueError('skirt: not a grid')


def _heavy(B, design=None, out=None):
    return None, {'x': {'value': 0.0, 'status': 'PASS'}}


def _counted(B, design=None):
    return 1


PLANTED = [registry.Part('t_ok', _ok, 't_ok_', None, 1, False, None, 't_ok', 2, ()),
           registry.Part('t_short', _short, 't_short_', None, 2, False, None, 't_short', 2, ()),
           registry.Part('t_boom', _boom, 't_boom_', None, 3, False, None, 't_boom', 3, ()),
           registry.Part('t_heavy', _heavy, 't_heavy_', None, 4, False, None, 't_heavy', _counted, ('iterate',)),
           registry.Part('t_free', _ok, 't_free_', None, 5, False, None, 't_free', None, ())]


class _Design:
    def __init__(self, B):
        pass

    def ref(self):
        return {}


def _run(profile=None):
    saved = registry.parts, qa3d.Design
    registry.parts = lambda: list(PLANTED)
    qa3d.Design = _Design
    try:
        B = bundle.Bundle({'spec': {}, 'objects': []}, {})
        return qa3d.run(B, tempfile.mkdtemp(), mode='off', profile=profile)
    finally:
        registry.parts, qa3d.Design = saved


def test_every_part_declares_its_count():
    """each registered QA part declares its denominator (an int, or a function of the spec)."""
    missing = [P.name for P in registry.parts() if P.checks is None]
    assert not missing, 'QA parts with no `checks` count: %s' % missing


def test_run_records_each_parts_status_against_its_count():
    rep = _run()
    S = rep['measured']['part_status']
    assert S['t_ok'] == dict(status='ok', checks=2, expected=2), S['t_ok']
    assert S['t_short']['status'] == 'short' and S['t_short']['checks'] == 1 and S['t_short']['expected'] == 2
    assert S['t_boom']['status'] == 'crashed' and 'not a grid' in S['t_boom']['why']
    assert S['t_heavy'] == dict(status='ok', checks=1, expected=1)          # (a function's count)
    assert S['t_free']['status'] == 'undeclared'
    assert rep['measured']['profile'] == 'full'
    assert rep['checks']['t_boom']['status'] == 'SKIPPED'                    # (the old record stays)


def test_the_iterate_profile_skips_explicitly():
    """a profile leaves out the parts that declare it, reported as skipped by it, never silently (motion QA)."""
    rep = _run('iterate')
    assert rep['measured']['part_status']['t_heavy']['status'] == 'skipped'
    assert rep['checks']['t_heavy'] == {'status': 'SKIPPED', 'why': 'skipped by profile iterate'}
    assert rep['measured']['profile'] == 'iterate'
    assert 't_heavy_x' not in rep['checks']
    try:
        qa3d.profile_of('fast')
        raise AssertionError('an unknown profile should raise')
    except ValueError:
        pass


def test_the_gate_blocks_a_crashed_short_or_skipped_part():
    """K plus the denominators: the candidate's crashed, short and profile-skipped parts block; --accept part:NAME
    reports one instead; the baseline's own are reported; a planted crash blocks the whole gate."""
    base, cand = _run(), _run('iterate')
    block, rep = gate.part_findings(base, cand)
    kinds = {b['part']: b['kind'] for b in block}
    assert kinds == {'t_short': gate.PART_BLOCKS['short'], 't_boom': gate.PART_BLOCKS['crashed'],
                     't_heavy': gate.PART_BLOCKS['skipped']}, kinds
    block, rep = gate.part_findings(base, cand, accept=['part:t_boom'])
    assert 't_boom' not in {b['part'] for b in block}
    assert any(r['part'] == 't_boom' and 'accepted' in r['note'] for r in rep)
    assert any(r['part'] == 't_free' and r['status'] == 'undeclared' for r in rep)
    # judged as a whole: the planted crash is a blocking item with its reason
    v, blocking, R = gate.judge({'qa': gate.compare_qa(base, cand), 'hard': []}, base, cand)
    assert v == 'FAIL' and any(b.get('part') == 't_boom' for b in blocking)
    assert any('skirt: not a grid' in gate._why(b) for b in blocking)
    # nothing wrong on either side: nothing blocks
    ok = {'checks': {}, 'measured': {'part_status': {'p': dict(status='ok', checks=3, expected=3)}}}
    assert gate.part_findings(ok, ok) == ([], [])


def test_an_older_qa_shows_its_crash_by_its_skipped_entry():
    """a qa.json from before the part status (the base built by older code): a part whose only entry is its SKIPPED
    key with an exception's text reads as crashed (motion's 2026-10-01 record)."""
    q = {'checks': {'motion': {'status': 'SKIPPED', 'why': "ValueError: skirt: not a grid"},
                    'body_x': {'status': 'SKIPPED', 'why': 'no design sheet'}},
         'measured': {'part_checks': {'motion': ['motion'], 'sheet_body': ['body_x']}}}
    st = gate.part_status(q)
    assert set(st) == {'motion'} and st['motion']['status'] == 'crashed'


def test_motion_declares_its_checks_per_loose_skirt():
    from charkit.sim import motionqa
    B = bundle.Bundle({'spec': {'style': 'anime', 'garments': [{'name': 'skirt', 'kind': 'skirt'},
                                                                {'name': 'top', 'kind': 'top'}]},
                       'objects': []}, {})
    n = motionqa.expected_checks(B)
    gm = motionqa.settings(B)
    loose = motionqa.loose_pieces(B, gm)
    assert n == (2 * len(motionqa.POSES) if 'skirt' in (loose or ['skirt']) else 0), (n, loose)


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
