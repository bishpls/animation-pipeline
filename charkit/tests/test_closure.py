"""charkit.closure: a build's input closure, recorded while it runs, and which of a merge's changes can reach it (the
gate's no-build path). venv: run this file, or pytest."""
import json, os, subprocess, sys, tempfile, textwrap

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, HERE)
from charkit import closure


def _git(root, *a):
    return subprocess.run(['git', *a], cwd=root, capture_output=True, text=True, check=True).stdout


def _repo():
    """a tiny repo: a package whose 'build' imports a module, reads a spec and a picture, scans for a marker, lists
    a folder, writes outputs and runs a script; plus docs, a test and a module the build never touches."""
    root = tempfile.mkdtemp()
    files = {
        'kit/__init__.py': '',
        'kit/core.py': 'X = 1\n',
        'kit/unused.py': 'Y = 2\n',
        'kit/part_a.py': '@mark(1)\ndef a(): pass\n',
        'kit/plain.py': 'Z = 3\n',
        'kit/spec.json': '{"k": 1}\n',
        'kit/pic.png': 'png',
        'kit/extra.bin': 'data',
        'kit/steps/one.txt': 'one',
        'kit/tests/test_x.py': 'pass\n',
        'kit/tool.py': 'print("tool")\n',
        'docs/notes.md': 'notes\n',
        'far/away.dat': 'far',
        'build.py': textwrap.dedent('''
            import os, re, subprocess, sys
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from kit import core                       # imported: read
            open('kit/spec.json').read(); open('kit/pic.png', 'rb').read()
            open('out.bin', 'w').write('x'); open('out.bin').read()        # written, then read: an output
            os.listdir('kit/steps')                    # listed
            from charkit import closure
            with closure.scanning('kit', r'^@mark\\('):
                for f in sorted(os.listdir('kit')):
                    if f.endswith('.py'):
                        open(os.path.join('kit', f)).read()
            subprocess.run([sys.executable, 'kit/tool.py'], capture_output=True)
            open('gen/input.npz').read()                 # an untracked input
            os.makedirs('kit/__pycache__', exist_ok=True)   # numba's cache beside the code: derived, not an input
            open('kit/__pycache__/core.f-1.py314.nbi', 'w').write('x'); open('kit/__pycache__/core.f-1.py314.nbi').read()
        '''),
    }
    for p, t in files.items():
        os.makedirs(os.path.dirname(os.path.join(root, p)) or root, exist_ok=True)
        open(os.path.join(root, p), 'w').write(t)
    os.makedirs(os.path.join(root, 'gen'))
    open(os.path.join(root, 'gen', 'input.npz'), 'w').write('v1')
    open(os.path.join(root, '.gitignore'), 'w').write('gen/\nout.bin\n*.log\n__pycache__/\n')
    _git(root, 'init', '-q')
    _git(root, 'add', '-A')
    _git(root, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'base')
    return root


def _record(root):
    """build.py run with the recorder on (started for root, as charkit/__init__ starts it for the worktree)."""
    log = os.path.join(root, 'closure.log')
    boot = ('import sys; sys.path.insert(0, %r); from charkit import closure; closure.start(%r, root=%r); '
            'import runpy; runpy.run_path("build.py", run_name="__main__")' % (HERE, log, root))
    subprocess.run([sys.executable, '-c', boot], cwd=root, check=True, env=dict(os.environ, CHARKIT_CLOSURE=''))
    return log


def test_the_record_holds_what_the_build_read_wrote_listed_scanned_and_ran():
    root = _repo()
    lines = set(open(_record(root)).read().splitlines())
    assert 'R kit/core.py' in lines and 'R kit/spec.json' in lines and 'R kit/pic.png' in lines, lines
    assert 'W out.bin' in lines and 'L kit/steps' in lines and 'X kit/tool.py' in lines
    assert 'S kit\t^@mark\\(' in lines
    assert not any(l.startswith('R kit/plain.py') or l.startswith('R kit/part_a.py') for l in lines), \
        'a scan records the scan, not a read of every file'
    assert not any('unused' in l for l in lines)
    C = closure.summarise(os.path.join(root, 'closure.log'), root)
    assert 'kit/core.py' in C['reads'] and 'out.bin' not in C['reads'] and 'closure.log' not in C['reads']
    assert list(C['untracked']) == ['gen/input.npz'] and C['scans'] == {'kit': ['^@mark\\(']}, C
    assert not any('__pycache__' in l for l in lines)
    assert C['listed'] == ['kit/steps']


def _change(root, edits):
    for p, t in edits.items():
        full = os.path.join(root, p)
        if t is None:
            _git(root, 'rm', '-q', p)
            continue
        os.makedirs(os.path.dirname(full), exist_ok=True)
        open(full, 'w').write(t)
        _git(root, 'add', p)
    return closure.changes(root)


def test_only_changes_that_reach_the_build_count():
    root = _repo()
    C = closure.summarise(_record(root), root)
    # nothing the build reads: docs, a test, a module it never imports, a module its scan passes over
    ch = _change(root, {'docs/notes.md': 'more\n', 'kit/tests/test_x.py': 'assert 1\n', 'kit/unused.py': 'Y = 3\n',
                        'kit/plain.py': 'Z = 4\n', 'kit/new_tool.py': 'pass\n'})
    assert len(ch) == 5 and closure.affected(C, ch, root) == [], closure.affected(C, ch, root)
    # each of these does
    for edit, why in [({'kit/core.py': 'X = 2\n'}, 'read'), ({'kit/spec.json': '{}'}, 'read'),
                      ({'kit/tool.py': 'pass\n'}, 'read'), ({'kit/steps/two.txt': 'two'}, 'lists'),
                      ({'kit/plain.py': '@mark(2)\ndef p(): pass\n'}, 'scans'),
                      ({'kit/part_a.py': 'def a(): pass\n'}, 'scans'),             # loses the marker
                      ({'kit/extra.bin': 'other'}, 'data file'), ({'kit/core.py': None}, 'read')]:
        _git(root, 'reset', '-q', '--hard')
        hits = closure.affected(C, _change(root, edit), root)
        assert len(hits) == 1 and why in hits[0][1], (edit, hits)
    _git(root, 'reset', '-q', '--hard')
    # an untracked input whose content differs
    open(os.path.join(root, 'gen', 'input.npz'), 'w').write('v2')
    assert closure.affected(C, [], root) == [('gen/input.npz', 'an untracked input whose content differs')]
    open(os.path.join(root, 'gen', 'input.npz'), 'w').write('v1')
    # a data file outside a sparse checkout's cone can't be read
    ch = _change(root, {'far/away.dat': 'moved'})
    assert closure.affected(C, ch, root, cone_dirs=['kit']) == [] and closure.affected(C, ch, root, cone_dirs=None)


def test_changes_between_two_commits_and_scans_at_the_old_one():
    root = _repo()
    C = closure.summarise(_record(root), root)
    first = _git(root, 'rev-parse', 'HEAD').strip()
    _change(root, {'docs/notes.md': 'x\n'})
    _git(root, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'docs')
    ch = closure.changes(root, first, 'HEAD')
    assert ch == [('M', 'docs/notes.md')] and closure.affected(C, ch, root, rev=first, new='HEAD') == []
    _change(root, {'kit/part_a.py': 'def a(): pass\n'})             # the marker was there at `first`
    _git(root, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'unmark')
    ch = closure.changes(root, first, 'HEAD')
    assert [h[0] for h in closure.affected(C, ch, root, rev=first, new='HEAD')] == ['kit/part_a.py']


def test_paused_reads_are_not_recorded():
    root = _repo()
    log = os.path.join(root, 'p.log')
    code = ('import sys; sys.path.insert(0, %r); from charkit import closure; closure.start(%r, root=%r)\n'
            'with closure.paused():\n    open("kit/core.py").read()\nopen("kit/spec.json").read()\n' % (HERE, log, root))
    subprocess.run([sys.executable, '-c', code], cwd=root, check=True)
    lines = open(log).read().splitlines()
    assert 'R kit/spec.json' in lines and 'R kit/core.py' not in lines, lines


def test_charkit_starts_the_recorder_from_the_environment():
    log = os.path.join(tempfile.mkdtemp(), 'c.log')
    subprocess.run([sys.executable, '-c', 'import charkit, json; json.load(open("charkit/spec/clawd.json"))'], cwd=HERE,
                   check=True, env=dict(os.environ, CHARKIT_CLOSURE=log))
    lines = open(log).read().splitlines()
    assert 'R charkit/spec/clawd.json' in lines and 'R charkit/closure.py' in lines, lines[:20]


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
