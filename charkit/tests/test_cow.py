"""charkit.cow: a box copy's read-only hard-linked inputs get a file of their own when charkit writes them (the calibrate
PermissionError of 2026-10-01: 22 failed box jobs). The box's layout is made here with bucketsync's own placement (a
read-only blob in a cache, hard-linked into a copy); each case runs in a fresh interpreter, so the hook (which can't
be removed) never reaches the test process (venv: run this file, or pytest)."""
import json, os, shutil, subprocess, sys, tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
from charkit import bucketsync, cow

# the writes the failed jobs made, as they made them (calibrate.py before 8580945f and 204d1f7d), and the other forms
# a writer takes; each over a file the box copy holds as a read-only link
WRITES = r'''
import json, os, shutil, sys
import numpy as np
root = sys.argv[1]
rec = {'name': 'kb', 'why': 'rewritten'}
# calibrate store (calibrate-rom-1001-140800-f867: known_bad/rom_rigid_shoulder.json)
json.dump(rec, open(os.path.join(root, 'charkit/calib/known_bad/kb.json'), 'w'), indent=1)
# calibrate's records (calibrate-hands-1001-121804-4df9: records/hand_back_cleft_L.json)
json.dump(rec, open(os.path.join(root, 'charkit/calib/records/r.json'), 'w'), indent=1, default=str)
with open(os.path.join(root, 'notes.md'), 'a') as f:                    # an append keeps what was there
    f.write('more\n')
fd = os.open(os.path.join(root, 'raw.bin'), os.O_WRONLY)                # a write without truncation: r+ semantics
os.write(fd, b'AB')
os.close(fd)
np.save(os.path.join(root, 'arr.npy'), np.arange(3))
shutil.copyfile(os.path.join(root, 'notes.md'), os.path.join(root, 'copied.md'))
print('WROTE', __import__('charkit.cow', fromlist=['x']).unshared() if 'charkit.cow' in sys.modules else -1)
'''
FILES = {'charkit/calib/known_bad/kb.json': '{"name": "kb", "why": "old"}', 'charkit/calib/records/r.json': '{}',
         'notes.md': 'line\n', 'raw.bin': 'xyzw', 'arr.npy': 'not yet an array', 'copied.md': 'old copy'}


def _box(files=FILES, package=False):
    """a fake box: WORK/.cas/blobs with read-only blobs, a copy WORK/wt with each file hard-linked from its blob, and a
    second copy WORK/other sharing the same blobs -> (work, copy, other)."""
    work = tempfile.mkdtemp(prefix='cow-box-')
    files = dict(files)
    if package:                                     # the package itself synced as links: the box's import path
        for f in ('__init__.py', 'cow.py', 'closure.py'):
            files['charkit/' + f] = open(os.path.join(REPO, 'charkit', f)).read()
    for i, (rel, text) in enumerate(sorted(files.items())):
        blob = os.path.join(work, '.cas', 'blobs', '%02d' % i, 'b%d' % i)
        os.makedirs(os.path.dirname(blob), exist_ok=True)
        open(blob, 'w').write(text)
        os.chmod(blob, 0o444)                       # bucketsync.cache_blob's mode
        for copy in ('wt', 'other'):
            bucketsync.place(blob, os.path.join(work, copy, rel), copy=False)
    return work, os.path.join(work, 'wt'), os.path.join(work, 'other')


def _run(code, *args, env=None, cwd=None, path=REPO):
    e = dict(os.environ, PYTHONPATH=path)
    e.pop('CHARKIT_COW', None)
    e.update(env or {})
    return subprocess.run([sys.executable, '-c', code] + list(args), capture_output=True, text=True, env=e, cwd=cwd)


def _shared_untouched(other):
    for rel, text in FILES.items():
        p = os.path.join(other, rel)
        assert open(p).read() == text, rel
        assert os.stat(p).st_nlink >= 2 and not os.stat(p).st_mode & 0o200, rel


def test_the_failure_reproduced_without_the_hook():
    """the box's layout alone: the calibrate jobs' write raises PermissionError (the known-bad side of the test)."""
    work, wt, other = _box()
    r = _run(WRITES, wt, env={'CHARKIT_COW': '0'})
    assert r.returncode != 0 and 'PermissionError' in r.stderr and 'known_bad/kb.json' in r.stderr, r.stderr[-500:]
    _shared_untouched(other)


def test_every_write_lands_in_this_copy_only():
    work, wt, other = _box()
    r = _run('import sys; sys.argv = sys.argv[:2]; from charkit import cow; assert cow.install(root=sys.argv[1], '
             'force=True)\n' + WRITES, wt)
    assert r.returncode == 0, r.stderr[-800:]
    assert 'WROTE 6' in r.stdout, r.stdout
    assert json.load(open(os.path.join(wt, 'charkit/calib/known_bad/kb.json')))['why'] == 'rewritten'
    assert json.load(open(os.path.join(wt, 'charkit/calib/records/r.json')))['name'] == 'kb'
    assert open(os.path.join(wt, 'notes.md')).read() == 'line\nmore\n'
    assert open(os.path.join(wt, 'raw.bin'), 'rb').read() == b'ABzw'
    assert open(os.path.join(wt, 'copied.md')).read() == 'line\nmore\n'
    import numpy as np
    assert np.load(os.path.join(wt, 'arr.npy')).tolist() == [0, 1, 2]
    for rel in FILES:
        st = os.stat(os.path.join(wt, rel))
        assert st.st_nlink == 1 and st.st_mode & 0o200, rel
    _shared_untouched(other)                         # the blobs, and the other copy linked to them


def test_only_under_its_root_and_only_read_only_links():
    """a read-only link outside the copy still fails as before; a writable file, or a read-only one with no other
    link, is left to the open (nothing widened beyond the box copy's inputs)."""
    work, wt, other = _box()
    code = ('import os, sys; from charkit import cow; cow.install(root=sys.argv[1], force=True)\n'
            'try:\n    open(os.path.join(sys.argv[2], "notes.md"), "a").write("x")\n    print("OUTSIDE WROTE")\n'
            'except PermissionError:\n    print("OUTSIDE REFUSED")\n'
            'p = os.path.join(sys.argv[1], "lone.txt"); open(p, "w").write("a"); os.chmod(p, 0o444)\n'
            'try:\n    open(p, "w").write("b")\n    print("LONE WROTE")\nexcept PermissionError:\n    print("LONE REFUSED")\n'
            'print("N", cow.unshared())')
    r = _run(code, wt, other)
    assert r.returncode == 0, r.stderr[-800:]
    assert 'OUTSIDE REFUSED' in r.stdout and 'N 0' in r.stdout, r.stdout
    assert 'LONE REFUSED' in r.stdout or os.geteuid() == 0, r.stdout


def test_importing_charkit_in_a_box_copy_installs_it():
    """end to end through the import a box job makes: the package synced as read-only links (so box_copy holds), then
    `import charkit` and the failing write. Not in a worktree (writable files), off with CHARKIT_COW=0."""
    work, wt, other = _box(package=True)
    assert cow.box_copy(wt) and not cow.box_copy(REPO)
    code = 'import sys; import charkit\n' + WRITES
    r = _run(code, wt, path=wt, cwd=wt)
    assert r.returncode == 0 and 'WROTE 6' in r.stdout, (r.stdout, r.stderr[-800:])
    _shared_untouched(other)
    work, wt, other = _box(package=True)
    r = _run(code, wt, path=wt, cwd=wt, env={"CHARKIT_COW": "0"})
    assert r.returncode != 0 and 'PermissionError' in r.stderr
    r = _run('import charkit, charkit.cow as c; print("ON", bool(c._STATE.get("root")))', path=REPO)
    assert 'ON False' in r.stdout, r.stdout + r.stderr


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
