"""charkit/bucketsync.py without the cloud: a directory stands in for the bucket, a temp dir for the box's /srv/work."""
import hashlib, json, os, stat, subprocess, sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bucketsync as bs  # noqa: E402


class FakeBucket:
    def __init__(self, root):
        self.root = root

    def _p(self, name):
        return os.path.join(self.root, name)

    def exists(self, name):
        return os.path.exists(self._p(name))

    def list(self, prefix):
        d = os.path.dirname(self._p(prefix))
        return [prefix + f for f in os.listdir(d)] if os.path.isdir(d) else []

    def upload(self, name, path=None, data=None, overwrite=False):
        p = self._p(name)
        if os.path.exists(p) and not overwrite:
            return 0
        os.makedirs(os.path.dirname(p), exist_ok=True)
        data = open(path, 'rb').read() if path else data
        open(p, 'wb').write(data)
        return len(data)

    def get(self, name):
        p = self._p(name)
        return open(p, 'rb').read() if os.path.exists(p) else None

    def download(self, name, dest, size=None, sha=None):
        data = self.get(name)
        if data is None:
            raise FileNotFoundError(name)
        open(dest, 'wb').write(data)
        assert sha is None or hashlib.sha256(data).hexdigest() == sha
        return len(data)


@pytest.fixture
def env(tmp_path, monkeypatch):
    bucket = FakeBucket(str(tmp_path / 'bucket'))
    work = tmp_path / 'work'
    work.mkdir()
    monkeypatch.setattr(bs, 'Bucket', lambda url: bucket)
    monkeypatch.setattr(bs, 'WORK', str(work))
    monkeypatch.setattr(bs, 'BOXCAS', str(work / '.cas'))
    monkeypatch.setattr(bs, 'CACHE_HOME', str(tmp_path / 'home'))
    monkeypatch.setenv('BUCKET', 'gs://test')
    return bucket, work, tmp_path


def write(p, s, mode=None):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'w').write(s)
    if mode:
        os.chmod(p, mode)


def repo(root):
    subprocess.run(['git', 'init', '-q', root], check=True)
    write(os.path.join(root, '.gitignore'), 'charkit/out/\n__pycache__/\nprojects/*/out/\n')
    write(os.path.join(root, 'charkit', 'a.py'), 'A = 1\n')
    write(os.path.join(root, 'charkit', 'same.txt'), 'shared\n')
    write(os.path.join(root, 'tools', 'same.txt'), 'shared\n')
    write(os.path.join(root, 'tools', 'run.sh'), '#!/bin/sh\n', 0o755)
    write(os.path.join(root, 'tools', 'plain.sh'), '#!/bin/sh\n', 0o644)
    subprocess.run(['git', '-C', root, 'add', '-A'], check=True)
    subprocess.run(['git', '-C', root, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'x'], check=True)
    write(os.path.join(root, 'notes.txt'), 'untracked\n')
    write(os.path.join(root, 'projects', 'p', 'out', 'big.bin'), 'ignored\n')
    write(os.path.join(root, 'charkit', 'out', 'i3d', 'field.npz'), 'field\n')
    write(os.path.join(root, 'charkit', 'out', 'remote', 'spec.json'), '{}\n')
    write(os.path.join(root, 'charkit', 'out', 'remote', 'repo.bundle'), 'bundle\n')
    write(os.path.join(root, 'charkit', 'out', 'build', 'x.glb'), 'output\n')
    write(os.path.join(root, 'charkit', '__pycache__', 'a.cpython-314.pyc'), 'pyc\n')
    write(os.path.join(root, 'charkit', '.cache', 'c'), 'c\n')
    os.symlink('a.py', os.path.join(root, 'charkit', 'link.py'))


def test_sync_paths_match_build_sh_rules(tmp_path):
    root = str(tmp_path / 'wt')
    repo(root)
    subprocess.run(['git', '-C', root, 'add', 'charkit/link.py'], check=True)
    rels, keep = bs.sync_paths(root)
    assert rels == sorted(['.gitignore', 'charkit/a.py', 'charkit/link.py', 'charkit/same.txt', 'tools/same.txt',
                           'tools/run.sh', 'tools/plain.sh', 'notes.txt', 'charkit/out/remote/spec.json'])
    assert 'projects/p/out/' in keep and not any(k.startswith('charkit/out') for k in keep)


def sync(root, work, name='wt'):
    rels, keep = bs.sync_paths(root)
    files, links, where = bs.scan(root, rels)
    bk, known = bs.Bucket('gs://test'), bs.known_set()
    bs.upload_blobs(bk, {f[1] for f in files}, known, where)
    m = dict(v=1, kind='sync', files=files, links=links, keep=keep)
    msha = bs.put_manifest(bk, m, known)
    return bs.box_materialize(msha, str(work / name))


def test_materialize_links_inputs_read_only_and_deletes_under_the_excludes(env):
    bucket, work, tmp = env
    root = str(tmp / 'wt')
    repo(root)
    assert sync(root, work) == 0
    d = work / 'wt'
    assert (d / 'charkit' / 'a.py').read_text() == 'A = 1\n'
    assert os.readlink(d / 'charkit' / 'link.py') == 'a.py'
    # identical content shares one cache blob; inputs are read-only, the exec bit has its own variant
    assert os.stat(d / 'charkit' / 'same.txt').st_ino == os.stat(d / 'tools' / 'same.txt').st_ino
    assert not os.stat(d / 'charkit' / 'a.py').st_mode & stat.S_IWUSR
    assert os.stat(d / 'tools' / 'run.sh').st_mode & stat.S_IXUSR
    assert not os.stat(d / 'tools' / 'plain.sh').st_mode & stat.S_IXUSR
    with pytest.raises(PermissionError):
        open(d / 'charkit' / 'a.py', 'w')
    assert not (d / 'charkit' / 'out' / 'build').exists() and not (d / 'projects').exists()
    # the box's own outputs, caches and ignored paths stay; a file the worktree dropped goes
    write(str(d / 'charkit' / 'out' / 'clawd' / 'body.glb'), 'box output\n')
    write(str(d / 'charkit' / 'out' / 'remote' / 'repo.bundle'), 'box bundle\n')
    write(str(d / 'charkit' / '__pycache__' / 'a.cpython-310.pyc'), 'pyc\n')
    write(str(d / 'projects' / 'p' / 'out' / 'render.png'), 'box render\n')
    write(str(d / 'stray.txt'), 'box stray\n')
    os.remove(os.path.join(root, 'notes.txt'))
    write(os.path.join(root, 'charkit', 'a.py'), 'A = 2\n')
    assert sync(root, work) == 0
    assert (d / 'charkit' / 'a.py').read_text() == 'A = 2\n'
    assert not (d / 'notes.txt').exists() and not (d / 'stray.txt').exists()
    assert (d / 'charkit' / 'out' / 'clawd' / 'body.glb').exists()
    assert (d / 'charkit' / 'out' / 'remote' / 'repo.bundle').exists()
    assert (d / 'projects' / 'p' / 'out' / 'render.png').exists()
    assert not (d / 'charkit' / '__pycache__' / 'a.cpython-310.pyc').exists()   # a.py changed: its bytecode went


def test_a_second_copy_links_the_same_blobs_and_never_writes_through(env):
    bucket, work, tmp = env
    root = str(tmp / 'wt')
    repo(root)
    assert sync(root, work, 'one') == 0 and sync(root, work, 'two') == 0
    a, b = work / 'one' / 'charkit' / 'a.py', work / 'two' / 'charkit' / 'a.py'
    assert os.stat(a).st_ino == os.stat(b).st_ino
    write(os.path.join(root, 'charkit', 'a.py'), 'A = 3\n')
    assert sync(root, work, 'one') == 0
    assert a.read_text() == 'A = 3\n' and b.read_text() == 'A = 1\n'


def test_i3d_is_not_sent_and_a_copys_own_is_left_alone(env):
    """decision 8: charkit/out/i3d (TRELLIS's output) isn't sent any more; a box copy's own, from the syncs that sent
    it, is left alone like the rest of charkit/out (nothing reads it; the sync doesn't delete what it doesn't manage)."""
    bucket, work, tmp = env
    root = str(tmp / 'wt')
    repo(root)
    assert sync(root, work) == 0
    assert not (work / 'wt' / 'charkit' / 'out' / 'i3d').exists()             # the laptop's isn't sent
    write(str(work / 'wt' / 'charkit' / 'out' / 'i3d' / 'old.glb'), 'old\n')   # a copy's own, sent by an older sync
    import shutil
    shutil.rmtree(os.path.join(root, 'charkit', 'out', 'i3d'))
    assert sync(root, work) == 0
    assert (work / 'wt' / 'charkit' / 'out' / 'i3d' / 'old.glb').read_text() == 'old\n'


def test_missing_blobs_are_reported(env):
    bucket, work, tmp = env
    root = str(tmp / 'wt')
    repo(root)
    rels, keep = bs.sync_paths(root)
    files, links, where = bs.scan(root, rels)
    bk, known = bs.Bucket('gs://test'), bs.known_set()
    msha = bs.put_manifest(bk, dict(v=1, kind='sync', files=files, links=links, keep=keep), known)
    assert bs.box_materialize(msha, str(work / 'wt')) == 3


def test_publish_and_pull_write_new_files_never_through_links(env, tmp_path):
    bucket, work, tmp = env
    out = work / 'wt' / 'charkit' / 'out' / 'build'
    write(str(out / 'a.png'), 'png1\n')
    write(str(out / 'sub' / 'b.json'), '{}\n')
    write(str(out / 'dup.png'), 'png1\n')
    assert bs.box_publish(str(out), name='t1') == 0
    local = tmp_path / 'local' / 'build'
    ref = bucket.get('cas/n/t1').decode()
    nf, nb, got_f, got_b = bs.pull(bucket, ref, str(local))
    assert (nf, got_f) == (3, 3)
    assert (local / 'a.png').read_text() == 'png1\n' and (local / 'sub' / 'b.json').read_text() == '{}\n'
    assert os.stat(local / 'a.png').st_ino != os.stat(local / 'dup.png').st_ino
    # unchanged: nothing downloaded
    assert bs.pull(bucket, ref, str(local))[2] == 0
    # a local output hard-linked elsewhere is replaced, not written through
    other = tmp_path / 'other.png'
    os.link(local / 'a.png', other)
    write(str(out / 'a.png'), 'png2\n')
    assert bs.box_publish(str(out), name='t1') == 0
    bs.pull(bucket, bucket.get('cas/n/t1').decode(), str(local))
    assert (local / 'a.png').read_text() == 'png2\n' and other.read_text() == 'png1\n'


def test_managed():
    kf, kd = {'x/ignored.txt'}, {'projects/p/out'}
    assert bs.managed('charkit/a.py', kf, kd)
    assert not bs.managed('charkit/out/i3d/f', kf, kd) and not bs.managed('charkit/out/i3d', kf, kd)
    assert bs.managed('charkit/out/remote/s.json', kf, kd)
    assert not bs.managed('charkit/out/remote/r.bundle', kf, kd)
    assert not bs.managed('charkit/out/clawd', kf, kd)
    assert not bs.managed('x/ignored.txt', kf, kd) and not bs.managed('projects/p/out/a', kf, kd)
    assert not bs.managed('a/__pycache__/m.pyc', kf, kd) and not bs.managed('.git', kf, kd)


def test_push_copies_one_off_files_without_caching_them(env, tmp_path):
    bucket, work, tmp = env
    f = tmp_path / 'repo-x.bundle'
    f.write_bytes(b'bundle bytes')
    files, links, where = bs.scan(str(tmp_path), ['repo-x.bundle'])
    bk, known = bs.Bucket('gs://test'), bs.known_set()
    bs.upload_blobs(bk, {x[1] for x in files}, known, where)
    msha = bs.put_manifest(bk, dict(v=1, kind='push', files=files, links=links, as_file=True), known)
    dest = work / 'repo-x.bundle'
    assert bs.box_materialize(msha, str(dest), copy=True, delete=False) == 0
    assert dest.read_bytes() == b'bundle bytes' and os.stat(dest).st_mode & stat.S_IWUSR
    assert not (work / '.cas' / 'blobs').exists()
    # a directory's contents, linked as inputs, into an existing directory
    d = tmp_path / 'inputs'
    write(str(d / 'a.npz'), 'a\n')
    write(str(d / 'sub' / 'b.glb'), 'b\n')
    files, links, where = bs.scan(str(d), bs.walk_paths(str(d)))
    bs.upload_blobs(bk, {x[1] for x in files}, known, where)
    msha = bs.put_manifest(bk, dict(v=1, kind='push', files=files, links=links), known)
    assert bs.box_materialize(msha, str(work / 'g.inputs'), delete=False) == 0
    assert (work / 'g.inputs' / 'sub' / 'b.glb').read_text() == 'b\n'
    assert os.stat(work / 'g.inputs' / 'a.npz').st_nlink == 2


def test_blobs_the_bucket_lacks_are_adopted_from_the_boxs_copies(env, tmp_path, capsys):
    bucket, work, tmp = env
    root = str(tmp / 'wt')
    repo(root)
    # an rsync-era copy of another worktree on the box, writable, with the same untracked notes
    write(str(work / 'old' / 'notes.txt'), 'untracked\n')
    os.makedirs(str(work / 'old' / 'charkit'))                                  # (a worktree copy: it has charkit/)
    rels, keep = bs.sync_paths(root)
    files, links, where = bs.scan(root, rels)
    bk, known = bs.Bucket('gs://test'), bs.known_set()
    field = next(f[1] for f in files if f[0] == 'notes.txt')
    others = {f[1] for f in files} - {field}
    bs.upload_blobs(bk, others, known, where)
    msha = bs.put_manifest(bk, dict(v=1, kind='sync', files=files, links=links, keep=keep), known)
    assert bs.box_materialize(msha, str(work / 'wt')) == 0
    assert 'BUCKETSYNC-ADOPTED %s' % field in capsys.readouterr().out
    assert bucket.exists(bs.blob(field))
    new = work / 'wt' / 'notes.txt'
    assert new.read_text() == 'untracked\n'
    assert os.stat(new).st_ino != os.stat(work / 'old' / 'notes.txt').st_ino


def test_check_finds_what_a_copy_gets_wrong(env, capsys):
    bucket, work, tmp = env
    root = str(tmp / 'wt')
    repo(root)
    assert sync(root, work) == 0
    rels, keep = bs.sync_paths(root)
    files, links, where = bs.scan(root, rels)
    msha = bs.put_manifest(bs.Bucket('gs://test'), dict(v=1, kind='sync', files=files, links=links, keep=keep),
                           bs.known_set())
    assert bs.box_check(msha, str(work / 'wt')) == 0
    d = work / 'wt'
    os.remove(d / 'tools' / 'plain.sh')
    write(str(d / 'extra.txt'), 'x\n')
    write(str(d / 'charkit' / 'out' / 'clawd' / 'out.glb'), "box output: not the sync's\n")
    assert bs.box_check(msha, str(d)) == 1
    out = capsys.readouterr().out
    assert 'missing 1' in out and 'extra 1' in out and 'content 0' in out


def private_repo(root):
    """repo() plus a gitignored private character (charkit/private/: references, spec, manifest) and its outputs."""
    repo(root)
    write(os.path.join(root, '.gitignore'), 'charkit/out/\n__pycache__/\nprojects/*/out/\ncharkit/private/\n')
    write(os.path.join(root, 'charkit', 'private', 'cx', 'spec.json'), '{"name": "cx"}\n')
    write(os.path.join(root, 'charkit', 'private', 'cx', 'refs', 'gen', 'sheet.png'), 'png\n')
    write(os.path.join(root, 'charkit', 'private', 'cx', 'out', 'b1', 'body.glb'), 'private output\n')
    write(os.path.join(root, 'charkit', 'private', 'cx', '__pycache__', 'g.pyc'), 'pyc\n')


def test_private_inputs_are_synced_and_their_outputs_are_not(tmp_path):
    """charkit/private/ is gitignored (a private character stays out of the public repo) but the box needs its inputs:
    they are synced; its outputs (charkit/private/<name>/out) are not, as charkit/out's aren't."""
    root = str(tmp_path / 'wt')
    private_repo(root)
    rels, keep = bs.sync_paths(root)
    assert 'charkit/private/cx/spec.json' in rels and 'charkit/private/cx/refs/gen/sheet.png' in rels
    assert not any(r.startswith('charkit/private/cx/out') or '__pycache__' in r for r in rels)
    assert not any(k.startswith('charkit/private') for k in keep)        # synced, so not an ignored path to keep
    assert 'projects/p/out/' in keep                                       # other ignored paths still stay home
    assert bs.private_out('charkit/private/cx/out') and bs.private_out('charkit/private/cx/out/b1/body.glb')
    assert not bs.private_out('charkit/private/cx/spec.json') and not bs.private_out('charkit/out/x')


def test_private_inputs_reach_the_box_and_its_private_outputs_stay(env):
    bucket, work, tmp = env
    root = str(tmp / 'wt')
    private_repo(root)
    assert sync(root, work) == 0
    d = work / 'wt'
    assert (d / 'charkit' / 'private' / 'cx' / 'spec.json').read_text() == '{"name": "cx"}\n'
    assert not (d / 'charkit' / 'private' / 'cx' / 'out').exists()
    # a box build's private outputs stay; a private input the worktree dropped goes
    write(str(d / 'charkit' / 'private' / 'cx' / 'out' / 'b2' / 'qa.json'), 'box output\n')
    os.remove(os.path.join(root, 'charkit', 'private', 'cx', 'refs', 'gen', 'sheet.png'))
    assert sync(root, work) == 0
    assert (d / 'charkit' / 'private' / 'cx' / 'out' / 'b2' / 'qa.json').exists()
    assert not (d / 'charkit' / 'private' / 'cx' / 'refs' / 'gen' / 'sheet.png').exists()
    assert (d / 'charkit' / 'private' / 'cx' / 'spec.json').exists()


def test_managed_private():
    kf, kd = set(), {'projects/p/out'}
    assert bs.managed('charkit/private/cx/spec.json', kf, kd)
    assert not bs.managed('charkit/private/cx/out', kf, kd) and not bs.managed('charkit/private/cx/out/b/x.glb', kf, kd)


if __name__ == '__main__':          # the gate runs each test file as a script: without this it ran nothing
    sys.exit(pytest.main([__file__, '-q']))
