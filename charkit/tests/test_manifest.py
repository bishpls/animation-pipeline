"""charkit.manifest's produced references: built where missing, and rebuilt when stale (venv: run this file, or
pytest)."""
import json, os, shutil, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import manifest


def _setup():
    """a manifest in a temp dir with one produced reference whose command appends a line to it each run."""
    d = tempfile.mkdtemp(prefix='charkit-manifest-')
    out = os.path.join(d, 'made.txt')
    M = {'name': 't', 'references': {
        'made': {'kind': 'test', 'tracked': False, 'produced_by': 'charkit.manifest', 'path': out,
                 'command': 'python -c "open(%r, \'a\').write(\'run\\\\n\')"' % out},
        'art': {'kind': 'picture', 'tracked': True, 'path': os.path.join(d, 'art.png'), 'sha256': 'a' * 64}}}
    mp = os.path.join(d, 'manifest.json')
    json.dump(M, open(mp, 'w'))
    return d, mp, out, {'ref': {'manifest': mp}}


def test_built_once_then_kept_then_rebuilt_when_an_input_changes():
    d, mp, out, spec = _setup()
    try:
        runs = lambda: open(out).read().count('run')
        manifest.produced(spec, 'made', log=lambda *a: None)
        assert runs() == 1 and os.path.exists(out + '.stamp')
        manifest.produced(spec, 'made', log=lambda *a: None)          # fresh: kept
        assert runs() == 1
        M = json.load(open(mp))
        M['references']['art']['sha256'] = 'b' * 64                   # a tracked input changed
        json.dump(M, open(mp, 'w'))
        manifest.produced(spec, 'made', log=lambda *a: None)
        assert runs() == 2
        os.remove(out + '.stamp')                                      # made before stamps: rebuilt once
        msgs = []
        manifest.produced(spec, 'made', log=msgs.append)
        assert runs() == 3 and 'unstamped' in msgs[0]
    finally:
        shutil.rmtree(d)


def test_a_reads_input_makes_its_reader_stale():
    d, mp, out, spec = _setup()
    try:
        M = json.load(open(mp))
        M['references']['reader'] = dict(M['references']['made'], reads=['made'])
        M['references']['plain'] = dict(M['references']['made'])
        json.dump(M, open(mp, 'w'))
        R = manifest.load(mp)['references']
        a, b = manifest.stamp(spec, R['reader']), manifest.stamp(spec, R['plain'])
        assert a != b                                                  # the reader's stamp folds in what it reads
    finally:
        shutil.rmtree(d)


def test_a_read_references_view_settings_make_its_reader_stale():
    """the hull reads the extra views' reference: its bands, its pieces switch and its 'hull' switch change what the
    hull carves without changing the picture's hash, so each of them changes the hull's stamp; a reference nobody reads
    changes only its readers'."""
    d, mp, out, spec = _setup()
    try:
        M = json.load(open(mp))
        M['references']['extra'] = {'kind': 'generated_reference', 'tracked': True, 'path': os.path.join(d, 'x.png'),
                                    'sha256': 'c' * 64, 'extends': 'art', 'hull': False,
                                    'views': {'v': {'figure': 4, 'az': 150.0, 'bands': {'b': [-1.4, -0.8]}}}}
        M['references']['reader'] = dict(M['references']['made'], reads=['extra'])
        json.dump(M, open(mp, 'w'))
        st = lambda: {k: manifest.stamp(spec, manifest.load(mp)['references'][k]) for k in ('reader', 'made')}
        s0 = st()
        for change in (lambda e: e['views']['v']['bands'].update(c=[-2.3, -1.4]),
                       lambda e: e['views']['v'].update(pieces=False),
                       lambda e: e.update(hull=True)):
            M = json.load(open(mp))
            change(M['references']['extra'])
            json.dump(M, open(mp, 'w'))
            s1 = st()
            assert s1['reader'] != s0['reader']                         # the reader rebuilds
            assert s1['made'] == s0['made']                             # what doesn't read it doesn't
            s0 = s1
    finally:
        shutil.rmtree(d)


def test_the_hulls_stamp_follows_its_own_code_not_all_of_charkit():
    """the hull's stamp covers its build function and what it imports, one import deep: an edit to the garments or the
    QA doesn't make it stale (it had reached all 74 modules, so any edit rebuilt the hull)."""
    units = manifest._producer_code({'produced_by': 'charkit.geom.hull', 'produced_fn': 'charkit.geom.hull:build'})
    mods = {k for k in units if ':' not in k}
    assert 'charkit/geom/volume.py' in mods and 'charkit/refcheck.py' in mods
    assert 'charkit/garments.py' not in mods and 'charkit/qa3d.py' not in mods and len(mods) < 30, sorted(mods)


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok', name)
