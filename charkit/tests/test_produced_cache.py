"""charkit.manifest's shared cache of produced references (venv: run this file, or pytest): a hit restores the producer's
files byte for byte, by copy; what the key covers (the stamp's inputs, the producer's code two imports deep) misses when
it changes; a damaged entry misses and is deleted; racing stores leave one whole entry; only what the producer wrote is
kept; the newest entries survive the prune. The producer is a fake: a command whose code is three temp modules
(charkit.fakeprod imports fakemid, which imports fakedeep), and whose output carries random bytes, so a restored file
can only have come from the cache."""
import glob, hashlib, json, os, shlex, shutil, subprocess, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.environ['CHARKIT_CACHE_DIR'] = tempfile.mkdtemp(prefix='charkit-pcache-code-')    # the code memo, not the kit's
from charkit import cache, manifest

QUIET = lambda *a: None
FAKE = {}                                       # charkit.fake* -> its temp source file
_module_file = cache._module_file
cache._module_file = lambda name: FAKE.get(name) or _module_file(name)


def _sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def _setup():
    """a temp copy: the fake producer's modules, a manifest whose reference 'made' lives in a folder it shares with an
    unrelated output, and its own cache root (CHARKIT_PRODUCED_CACHE). Its command copies the cut-down spec to made.json,
    writes sub/side.bin (random bytes), and counts its runs in a file outside the folder."""
    d = tempfile.mkdtemp(prefix='charkit-pcache-')
    FAKE.clear()
    for name, body in (('fakeprod', 'import charkit.fakemid\n\ndef make():\n    return charkit.fakemid.mid()\n'),
                       ('fakemid', 'import charkit.fakedeep\n\ndef mid():\n    return charkit.fakedeep.deep()\n'),
                       ('fakedeep', 'def deep():\n    return 1\n')):
        FAKE['charkit.' + name] = os.path.join(d, name + '.py')
        open(FAKE['charkit.' + name], 'w').write(body)
    folder = os.path.join(d, 'out', 'made')
    os.makedirs(folder)
    open(os.path.join(folder, 'unrelated.txt'), 'w').write("another output's")
    out = os.path.join(folder, 'made.json')
    code = ('import os, shutil, sys; spec, out, runs = sys.argv[1:4]; f = os.path.dirname(out); shutil.copy(spec, out); '
            'os.makedirs(os.path.join(f, "sub"), exist_ok=True); '
            'open(os.path.join(f, "sub", "side.bin"), "wb").write(os.urandom(64) * 512); open(runs, "a").write("run\\n")')
    M = {'name': 't', 'references': {
        'made': {'kind': 'test', 'tracked': False, 'produced_by': 'charkit.fakeprod', 'path': out,
                 'reads_spec': ['name', 'eyes.x'],
                 'command': 'python -c %s {spec} %s %s' % (shlex.quote(code), out, os.path.join(d, 'runs'))},
        'art': {'kind': 'picture', 'tracked': True, 'path': os.path.join(d, 'art.png'), 'sha256': 'a' * 64}}}
    mp = os.path.join(d, 'manifest.json')
    json.dump(M, open(mp, 'w'))
    os.environ['CHARKIT_PRODUCED_CACHE'] = os.path.join(d, 'cache')
    spec = {'name': 't', 'ref': {'manifest': mp}, 'eyes': {'x': 0.17, 'width': 0.2}, 'body': {'height_m': 1.6}}
    return d, spec, out


def _runs(d):
    p = os.path.join(d, 'runs')
    return open(p).read().count('run') if os.path.exists(p) else 0


OURS = ('made.json', 'sub/side.bin', 'made.json.stamp', 'made.json.stamp.json')     # what the producer and produced() write


def _made(out):
    """the producer's files in the folder, with their sha256s."""
    f = os.path.dirname(out)
    return {r: _sha(os.path.join(f, r)) for r in OURS if os.path.exists(os.path.join(f, r))}


def _fresh_copy(out):
    """the producer's files gone, as in a fresh gate clone (the folder's other outputs stay)."""
    f = os.path.dirname(out)
    for r in OURS:
        if os.path.exists(os.path.join(f, r)):
            os.remove(os.path.join(f, r))


def _entries(rid='made'):
    base = os.path.join(manifest.cache_root(), rid)
    return sorted(os.path.join(base, n) for n in os.listdir(base)) if os.path.isdir(base) else []


def _edit(name, body):
    time.sleep(0.01)                            # a new mtime for the code memo
    open(FAKE['charkit.' + name], 'w').write(body)


def test_a_hit_restores_the_producers_files_byte_for_byte_by_copy():
    d, spec, out = _setup()
    try:
        msgs = []
        manifest.produced(spec, 'made', log=msgs.append)
        assert _runs(d) == 1 and any(m.startswith('CHARKIT_PRODUCED made: miss') for m in msgs), msgs
        assert any('CHARKIT_PRODUCED made: built in' in m and 'stored' in m for m in msgs), msgs
        first = _made(out)
        assert set(first) == {'made.json', 'sub/side.bin', 'made.json.stamp', 'made.json.stamp.json'}
        _fresh_copy(out)
        msgs = []
        manifest.produced(spec, 'made', log=msgs.append)
        assert _runs(d) == 1, 'rebuilt, not restored'
        assert _made(out) == first                                     # random bytes too: they came from the cache
        hit = [m for m in msgs if 'CHARKIT_PRODUCED made: hit' in m]
        assert hit and 'saved' in hit[0], msgs
        # copied, not linked: writing the restored file leaves the entry whole
        e, = _entries()
        cached = os.path.join(e, 'files', 'sub', 'side.bin')
        mine = os.path.join(os.path.dirname(out), 'sub', 'side.bin')
        assert os.stat(mine).st_ino != os.stat(cached).st_ino and os.stat(mine).st_nlink == 1
        open(mine, 'ab').write(b'x')
        assert _sha(cached) == json.load(open(os.path.join(e, 'entry.json')))['files']['sub/side.bin'][1]
        ev = [json.loads(l) for l in open(os.path.join(manifest.cache_root(), 'events.jsonl'))]
        assert [x['event'] for x in ev] == ['miss', 'hit'] and ev[1]['built_seconds'] is not None
        # fresh in this copy now: neither the cache nor the producer is asked again
        manifest.produced(spec, 'made', log=QUIET)
        assert _runs(d) == 1 and len(open(os.path.join(manifest.cache_root(), 'events.jsonl')).readlines()) == 2
    finally:
        shutil.rmtree(d)


def test_only_the_producers_files_are_cached():
    """the hair layers share their folder with other outputs: an entry holds what the build wrote (and the stamp and
    its parts), never a file that was there before and untouched, nor produced()'s lock or cut-down spec."""
    d, spec, out = _setup()
    try:
        f = os.path.dirname(out)
        open(os.path.join(f, 'older.npz'), 'w').write('made by something else, earlier')
        manifest.produced(spec, 'made', log=QUIET)
        e, = _entries()
        files = json.load(open(os.path.join(e, 'entry.json')))['files']
        assert set(files) == {'made.json', 'sub/side.bin', 'made.json.stamp', 'made.json.stamp.json'}, sorted(files)
        on_disk = {os.path.relpath(p, os.path.join(e, 'files')) for p in glob.glob(os.path.join(e, 'files', '**', '*'),
                                                                                   recursive=True) if os.path.isfile(p)}
        assert on_disk == set(files)
        _fresh_copy(out)
        manifest.produced(spec, 'made', log=QUIET)                     # a hit leaves the others alone
        assert open(os.path.join(f, 'unrelated.txt')).read() == "another output's"
        assert open(os.path.join(f, 'older.npz')).read() == 'made by something else, earlier'
        assert not [p for p in os.listdir(f) if p.endswith('.tmp')]
    finally:
        shutil.rmtree(d)


def test_a_code_change_two_imports_down_misses():
    """the stamp follows the producer's code one import deep; the key two. A branch that edits a module two down keeps
    the stamp (this copy doesn't rebuild what it has) but gets another key: a fresh clone builds instead of restoring
    what the older code made."""
    d, spec, out = _setup()
    try:
        R = manifest.load(spec['ref']['manifest'])['references']
        st, k2 = manifest.stamp(spec, R['made']), manifest.code2(R, 'made')
        manifest.produced(spec, 'made', log=QUIET)
        _edit('fakemid', 'import charkit.fakedeep\n\ndef mid():\n    return charkit.fakedeep.deep() + 1\n')
        assert manifest.stamp(spec, R['made']) == st                    # one import deep: unchanged
        assert manifest.code2(R, 'made') != k2                          # two: another key
        manifest.produced(spec, 'made', log=QUIET)
        assert _runs(d) == 1                                            # this copy's own is fresh by its stamp
        _fresh_copy(out)
        msgs = []
        manifest.produced(spec, 'made', log=msgs.append)
        assert _runs(d) == 2 and any('made: miss' in m for m in msgs), msgs
        assert len(_entries()) == 2
        # a reader's key follows the code of what it reads (its outputs are the reader's inputs)
        M = json.load(open(spec['ref']['manifest']))
        M['references']['reader'] = dict(M['references']['made'], reads=['made'], path=out + '.reader',
                                         produced_by='charkit.fakedeep')      # its own code doesn't reach fakemid
        json.dump(M, open(spec['ref']['manifest'], 'w'))
        R = manifest.load(spec['ref']['manifest'])['references']
        r0 = manifest.code2(R, 'reader')
        _edit('fakemid', 'import charkit.fakedeep\n\ndef mid():\n    return charkit.fakedeep.deep() + 2\n')
        assert manifest.code2(R, 'reader') != r0
        # one import deep changes both
        s0, k0 = manifest.stamp(spec, R['made']), manifest.code2(R, 'made')
        _edit('fakeprod', 'import charkit.fakemid\n\ndef make():\n    return charkit.fakemid.mid() * 2\n')
        assert manifest.stamp(spec, R['made']) != s0 and manifest.code2(R, 'made') != k0
    finally:
        shutil.rmtree(d)


def test_a_change_in_a_declared_spec_section_misses_and_a_knob_outside_it_hits():
    d, spec, out = _setup()
    try:
        manifest.produced(spec, 'made', log=QUIET)
        other = json.loads(json.dumps(spec))
        other['eyes']['x'] = 0.18
        manifest.produced(other, 'made', log=QUIET)                     # rebuilt in place (its stamp differs)
        assert _runs(d) == 2 and json.load(open(out))['eyes']['x'] == 0.18
        manifest.produced(spec, 'made', log=QUIET)                      # switching back: restored, not rebuilt
        assert _runs(d) == 1 + 1 and json.load(open(out))['eyes']['x'] == 0.17
        _fresh_copy(out)
        knob = json.loads(json.dumps(spec))
        knob['body']['height_m'] = 1.9
        knob['eyes']['width'] = 0.3
        manifest.produced(knob, 'made', log=QUIET)                      # not a section it reads: the same entry
        assert _runs(d) == 2 and len(_entries()) == 2
    finally:
        shutil.rmtree(d)


def test_a_damaged_or_partial_entry_is_a_miss_and_is_deleted():
    d, spec, out = _setup()
    try:
        manifest.produced(spec, 'made', log=QUIET)
        damage = [('a byte flipped', lambda e: _flip(os.path.join(e, 'files', 'sub', 'side.bin'))),
                  ('a file missing', lambda e: os.remove(os.path.join(e, 'files', 'made.json'))),
                  ('a file cut short', lambda e: open(os.path.join(e, 'files', 'sub', 'side.bin'), 'r+b').truncate(9)),
                  ('its record garbled', lambda e: open(os.path.join(e, 'entry.json'), 'w').write('{"files": ')),
                  ('its record for another key', lambda e: _rekey(e)),
                  ('a path outside the folder', lambda e: _escape(e))]
        for i, (what, fn) in enumerate(damage):
            e, = _entries()
            fn(e)
            _fresh_copy(out)
            msgs = []
            manifest.produced(spec, 'made', log=msgs.append)
            assert _runs(d) == i + 2, what                               # rebuilt
            assert any('damaged' in m and 'deleted' in m for m in msgs), (what, msgs)
            e2, = _entries()                                            # the damaged one gone, the rebuild stored
            E = json.load(open(os.path.join(e2, 'entry.json')))
            assert all(_sha(os.path.join(e2, 'files', k)) == v[1] for k, v in E['files'].items()), what
            assert _made(out)['sub/side.bin'] == E['files']['sub/side.bin'][1], what
            assert not os.path.exists(os.path.join(d, 'escaped')), what
        assert not [p for p in os.listdir(os.path.dirname(out)) if p.endswith('.tmp')]
    finally:
        shutil.rmtree(d)


def _flip(p):
    b = bytearray(open(p, 'rb').read())
    b[100] ^= 0xFF
    open(p, 'wb').write(bytes(b))


def _rekey(e):
    p = os.path.join(e, 'entry.json')
    E = json.load(open(p))
    E['stamp'] = '0' * 40
    json.dump(E, open(p, 'w'))


def _escape(e):
    p = os.path.join(e, 'entry.json')
    E = json.load(open(p))
    E['files']['../../escaped'] = E['files']['made.json']
    shutil.copy(os.path.join(e, 'files', 'made.json'), os.path.join(e, 'escaped'))
    json.dump(E, open(p, 'w'))


def test_racing_stores_leave_one_whole_entry():
    """eight builds of one key store at once, each its own bytes (a hull differs across machines): one wins whole, the
    others are discarded, and no temporary is left behind."""
    d, spec, out = _setup()
    try:
        root = manifest.cache_root()
        key = 'a' * 40 + '-' + 'b' * 40
        srcs = []
        for i in range(8):
            f = os.path.join(d, 'copy%d' % i, 'made')
            os.makedirs(os.path.join(f, 'sub'))
            for rel in ('made.json', 'sub/side.bin', 'made.json.stamp', 'made.json.stamp.json'):
                open(os.path.join(f, rel), 'wb').write(('writer %d ' % i).encode() * (200000 if 'side' in rel else 10))
            srcs.append(os.path.join(f, 'made.json'))
        t = time.time() + 1.5
        code = ('import sys, time; sys.path.insert(0, %r); from charkit import manifest; time.sleep(max(0, %r - time.time())); '
                'print(manifest.cache_store(%r, "made", %r, sys.argv[1], ["made.json", "sub/side.bin", "made.json.stamp", '
                '"made.json.stamp.json"], seconds=1.0))' % (ROOT, t, root, key))
        ps = [subprocess.Popen([sys.executable, '-c', code, p], stdout=subprocess.PIPE, text=True) for p in srcs]
        res = sorted(p.communicate()[0].strip() for p in ps)
        assert res.count('stored') == 1 and res.count('exists') == 7, res
        assert os.listdir(os.path.join(root, 'made')) == [key]           # no .tmp-PID left
        e = os.path.join(root, 'made', key)
        E = json.load(open(os.path.join(e, 'entry.json')))
        writers = set()
        for rel, (size, sha) in E['files'].items():
            b = open(os.path.join(e, 'files', rel), 'rb').read()
            assert len(b) == size and hashlib.sha256(b).hexdigest() == sha, rel
            writers.add(b.split(b' ')[1])
        assert len(writers) == 1                                        # every file from the one winner
    finally:
        shutil.rmtree(d)


def test_the_newest_entries_are_kept_and_leftovers_cleared():
    d, spec, out = _setup()
    try:
        root = manifest.cache_root()
        f = os.path.dirname(out)
        for rel in ('made.json', 'made.json.stamp'):
            open(os.path.join(f, rel), 'w').write(rel)
        now = time.time()
        for i in range(5):
            assert manifest.cache_store(root, 'made', '%040d-%040d' % (i, i), out, ['made.json', 'made.json.stamp']) == 'stored'
            os.utime(os.path.join(root, 'made', '%040d-%040d' % (i, i)), (now - 100 + i, now - 100 + i))
        left = os.path.join(root, 'made', '%040d-%040d.tmp-99999' % (7, 7))
        os.makedirs(left)
        os.utime(left, (now - 7200, now - 7200))                        # a store cut short two hours ago
        assert manifest.cache_prune(root, 'made', keep=3) == 2
        assert sorted(os.listdir(os.path.join(root, 'made'))) == ['%040d-%040d' % (i, i) for i in (2, 3, 4)]
    finally:
        shutil.rmtree(d)


def test_off_turns_it_off():
    d, spec, out = _setup()
    try:
        os.environ['CHARKIT_PRODUCED_CACHE'] = 'off'
        assert manifest.cache_root() is None
        msgs = []
        manifest.produced(spec, 'made', log=msgs.append)
        _fresh_copy(out)
        manifest.produced(spec, 'made', log=QUIET)
        assert _runs(d) == 2 and not os.path.exists(os.path.join(d, 'cache'))
        assert not any('CHARKIT_PRODUCED' in m for m in msgs) and 'building' in msgs[0]
    finally:
        shutil.rmtree(d)


def test_the_clawd_references_keys_reach_deeper_than_their_stamps():
    """on the real producers: the key's code (two imports) holds more modules than the stamp's (one), and the hull's key
    folds in the outfit's (it reads the masks)."""
    R = manifest.load('charkit/refs/clawd/manifest.json')['references']
    for rid, deeper in (('hair_layers', 'charkit/outfit.py'), ('outfit_masks', 'charkit/target3d.py'),
                        ('hull', 'charkit/bodymeasure.py')):
        one = {k.split(':')[0] for k in manifest._producer_code(R[rid])}
        two = {k.split(':')[0] for k in manifest._producer_code(R[rid], manifest.CACHE_DEPTH)}
        assert one < two and deeper in two - one, (rid, sorted(two - one))
    assert 'outfit_masks' in R['hull']['reads'] and 'outfit_masks' in R['hair_layers']['reads']


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok', name)
