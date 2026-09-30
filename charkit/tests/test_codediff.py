"""charkit.codediff: the QA parts' measuring code and changes' definitions compared between trees (a throwaway git
repository with a tiny charkit package; venv: run this file, or pytest)."""
import os, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import cache, codediff, gate

QA = '''from .registry import qa_part
from . import geom
LIMIT = 0.5
OTHER = 3


class Design:
    def ref(self):
        return {}


def _check_name(P, k):
    return P.prefix + k


def helper(x):
    return x * 2


@qa_part('poke', order=300)
def poke(B, design=None, out=None):
    return None, {'poke_share': {'value': helper(1) > LIMIT}}


@qa_part('mesh', order=600, prefix='mesh_')
def mesh(B, design=None, out=None):
    return None, {'count': {'value': OTHER + geom.area()}}
'''
GEOM = '''def area():
    return 1.0


def build():
    return area() + 1
'''


def _repo():
    root = tempfile.mkdtemp(prefix='charkit-codediff-')
    g = lambda *a: subprocess.run(['git', *a], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    g('init', '-q', '-b', 'main')
    g('config', 'user.email', 't@t'); g('config', 'user.name', 't')
    os.makedirs(os.path.join(root, 'charkit'))
    for n, t in (('__init__.py', ''), ('registry.py', 'def qa_part(*a, **k):\n    return lambda f: f\n'),
                 ('checks.py', 'def authorize(c, a):\n    return c\n'), ('qa3d.py', QA), ('geom.py', GEOM)):
        open(os.path.join(root, 'charkit', n), 'w').write(t)
    g('add', '-A'); g('commit', '-qm', 'a')

    def commit(path, old, new):
        p = os.path.join(root, path)
        s = open(p).read()
        assert old in s
        open(p, 'w').write(s.replace(old, new))
        g('commit', '-qam', 'x')
        return g('rev-parse', 'HEAD')
    return root, g('rev-parse', 'HEAD'), commit


def test_measure_changes_name_the_part_whose_code_changed():
    root, a, commit = _repo()
    T = lambda r: cache.Tree(repo=root, rev=r)
    assert [p['name'] for p in codediff.part_defs(T(a))] == ['mesh', 'poke']
    b = commit('charkit/qa3d.py', 'return x * 2', 'return x * 3')           # poke's helper
    assert list(codediff.measure_changes(T(a), T(b))) == ['poke']
    assert codediff.measure_changes(T(a), T(b))['poke']['units'] == ['charkit/qa3d.py:helper']
    c = commit('charkit/qa3d.py', 'OTHER = 3', 'OTHER = 4')                  # a constant only mesh names
    assert list(codediff.measure_changes(T(b), T(c))) == ['mesh']
    d = commit('charkit/geom.py', 'return area() + 1', 'return area() + 2')  # geometry code no part reaches
    assert codediff.measure_changes(T(c), T(d)) == {}
    e = commit('charkit/qa3d.py', 'return {}', 'return {1: 2}')              # the design side: every part
    assert sorted(codediff.measure_changes(T(d), T(e))) == ['mesh', 'poke']
    f = commit('charkit/qa3d.py', 'LIMIT = 0.5', '# a comment\nLIMIT = 0.5')  # comments don't count
    assert codediff.measure_changes(T(e), T(f)) == {}
    # a worktree's files read the same as its commit's
    assert codediff.measure_units(root) == codediff.measure_units(T(f))


def test_definitions_that_meet_and_that_dont():
    root, a, commit = _repo()
    T = lambda r: cache.Tree(repo=root, rev=r)
    b = commit('charkit/geom.py', 'return 1.0', 'return 2.0')               # area (build and mesh reach it)
    move = codediff.changed(T(a), T(b), repo=root)
    assert move == ['charkit/geom.py:area'], move
    # a branch changing build: build calls area (the move's): they meet
    c = commit('charkit/geom.py', 'return area() + 1', 'return area() + 5')
    branch = codediff.changed(T(b), T(c), repo=root)
    assert branch == ['charkit/geom.py:build']
    assert codediff.interacts(move, branch, [T(b)], [T(c)])
    # a branch changing only poke's helper: neither reaches the other's change
    br2 = ['charkit/qa3d.py:helper']
    assert not codediff.interacts(move, br2, [T(c)], [T(c)])
    # the move changes a caller of the branch's change: they meet only with the symmetric half
    assert codediff.interacts(['charkit/geom.py:build'], ['charkit/geom.py:area'], [T(c)], [T(c)])
    assert not codediff.interacts(['charkit/geom.py:build'], ['charkit/geom.py:area'], [T(c)], [T(c)],
                                  symmetric=False)
    # a constant is its own unit
    d = commit('charkit/qa3d.py', 'OTHER = 3', 'OTHER = 4')
    assert codediff.changed(T(c), T(d), repo=root) == ['charkit/qa3d.py:=OTHER']


def test_the_cache_keys_are_the_coarse_walk():
    """the fine walk is the gate's; a cache key (code_units without fine) is unchanged by it."""
    from charkit import qa3d
    a = cache.code_units(qa3d.poke, modules=('charkit.bundle',))
    assert not any(':=' in k for k in a)
    assert any(k.endswith('qa3d.py:<top>') for k in a)
    b = cache.code_units(qa3d.poke, modules=('charkit.bundle',), fine=True)
    assert any(':=' in k for k in b)


def test_the_gate_scores_an_unregistered_remeasure_both_ways():
    """a check whose measuring code changed without a step: the crossed cells that read differently on one geometry
    name it, the 2x2 scores it, and a drop to FAIL under the old measure blocks with the ask to register it."""
    ck = lambda **kw: {'checks': {k: {'value': v[0], 'status': v[1]} for k, v in kw.items()}}
    base = ck(poke_share=(0.003, 'PASS'), mesh_count=(4, 'PASS'))
    cand = ck(poke_share=(0.003, 'PASS'), mesh_count=(4, 'PASS'))       # the direct comparison sees nothing
    old_on_new = ck(poke_share=(0.02, 'FAIL'), mesh_count=(4, 'PASS'))  # the old measure: the new geometry pokes
    new_on_old = ck(poke_share=(0.0005, 'PASS'), mesh_count=(4, 'PASS'))
    moved = gate.measure_moved(base, cand, old_on_new, new_on_old, ['poke_share', 'mesh_count'])
    assert moved == ['poke_share'], moved
    rows = gate.twobytwo(base, cand, old_on_new, new_on_old, {}, detected=moved)
    assert [(r['check'], r['old'], r.get('detected')) for r in rows] == [('poke_share', 'regressed', True)]
    rep = {'hard': [], 'qa': gate.compare_qa(base, cand), 'twobytwo': {'rows': rows, 'errors': {}},
           'unregistered': {'parts': {'poke': ['charkit/qa3d.py:poke']}, 'owners': {'poke': None},
                            'geometry': 'changed', 'checks': moved}}
    v, block, R = gate.judge(rep, base, cand)
    assert v == 'FAIL' and 'register a remeasure' in block[0]['kind'], block
    assert R['unregistered'][0]['checks'] == ['poke_share']
    # registered, the same rows block the same way (without the ask)
    rows2 = gate.twobytwo(base, cand, old_on_new, new_on_old, {'poke_*': 'why'})
    v2, block2, _ = gate.judge(dict(rep, twobytwo={'rows': rows2, 'errors': {}}, unregistered=None), base, cand)
    assert v2 == 'FAIL' and 'register' not in block2[0]['kind']


def test_part_owners_from_the_record_or_the_naming():
    meas = {'poke': {'units': [], 'part': {'name': 'poke', 'prefix': '', 'keep': None, 'skip_key': 'poke'}},
            'mesh': {'units': [], 'part': {'name': 'mesh', 'prefix': 'mesh_', 'keep': None, 'skip_key': 'mesh'}}}
    q = {'checks': {'poke_share': {}, 'mesh_count': {}, 'eye_x': {}}}
    assert gate.part_owners(meas, q) == {'poke': None, 'mesh': ['mesh_count']}
    q2 = dict(q, measured={'part_checks': {'poke': ['poke_share'], 'mesh': ['mesh_count']}})
    assert gate.part_owners(meas, q2, q) == {'poke': ['poke_share'], 'mesh': ['mesh_count']}


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
