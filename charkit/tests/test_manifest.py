"""charkit.manifest's produced references: built where missing, and rebuilt when stale (venv: run this file, or
pytest)."""
import json, os, shlex, shutil, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import manifest

# these are one copy's own staleness and rebuilds; the shared cache in front of them is test_produced_cache.py's
os.environ['CHARKIT_PRODUCED_CACHE'] = 'off'


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


def _spec_setup(**entry):
    """a manifest whose produced reference 'made' declares spec sections (and whatever else `entry` gives it); its command
    copies the cut-down spec it is given ({spec}) to its path, so the output is what the producer read."""
    d = tempfile.mkdtemp(prefix='charkit-manifest-')
    out = os.path.join(d, 'made.json')
    code = 'import shutil, sys; shutil.copy(sys.argv[1], sys.argv[2]); open(sys.argv[3], "a").write("run\\n")'
    M = {'name': 't', 'references': {
        'made': dict({'kind': 'test', 'tracked': False, 'produced_by': 'charkit.manifest', 'path': out,
                      'reads_spec': ['name', 'eyes.x', 'garments[].{name,kind,side}', 'garments[].region[].0'],
                      'command': 'python -c %s {spec} %s %s' % (shlex.quote(code), out, os.path.join(d, 'runs'))},
                     **entry),
        'art': {'kind': 'picture', 'tracked': True, 'path': os.path.join(d, 'art.png'), 'sha256': 'a' * 64}}}
    mp = os.path.join(d, 'manifest.json')
    json.dump(M, open(mp, 'w'))
    spec = {'name': 't', 'ref': {'manifest': mp}, 'eyes': {'x': 0.17, 'width': 0.2}, 'body': {'height_m': 1.6},
            'garments': [{'name': 'skirt', 'kind': 'skirt', 'flare': 0.3},
                         {'name': 'boots', 'kind': 'shell', 'region': [['leftLowerLeg', 0.47, 1.5]]}]}
    return d, mp, out, spec


def _variant(spec, change):
    s = json.loads(json.dumps(spec))
    change(s)
    return s


def test_specs_that_differ_in_a_read_section_have_other_stamps_and_dont_reuse_each_others_outputs():
    """the bug (2026-09-30): the outfit graph was made from the default spec by name and its stamp left the spec out, so
    a copy that made it under one spec's garments reused it under another's. Now each spec's garments are in the
    stamp, the producer is given that spec's own, and switching specs in one copy rebuilds it."""
    d, mp, out, spec = _spec_setup()
    try:
        runs = lambda: open(os.path.join(d, 'runs')).read().count('run')
        other = _variant(spec, lambda s: s['garments'].append({'name': 'collar', 'kind': 'collar'}))
        R = manifest.load(mp)['references']
        assert manifest.stamp(spec, R['made']) != manifest.stamp(other, R['made'])
        quiet = lambda *a: None
        manifest.produced(spec, 'made', log=quiet)
        assert [g['name'] for g in json.load(open(out))['garments']] == ['skirt', 'boots'] and runs() == 1
        manifest.produced(other, 'made', log=quiet)                   # not the first spec's output
        assert [g['name'] for g in json.load(open(out))['garments']] == ['skirt', 'boots', 'collar'] and runs() == 2
        manifest.produced(other, 'made', log=quiet)                   # fresh for this spec: kept
        assert runs() == 2
        manifest.produced(spec, 'made', log=quiet)                    # back: rebuilt from the first spec's garments
        assert [g['name'] for g in json.load(open(out))['garments']] == ['skirt', 'boots'] and runs() == 3
    finally:
        shutil.rmtree(d)


def test_a_knob_outside_the_declared_sections_keeps_the_stamp():
    """a body or face tune, or a garment's shape knobs (a flare, a region's extent), change no declared section: the
    stamp holds (the hull isn't rebuilt), and the producer never sees them (the cut-down spec it is given lacks them)."""
    d, mp, out, spec = _spec_setup()
    try:
        R = manifest.load(mp)['references']
        st = manifest.stamp(spec, R['made'])
        for change in (lambda s: s['body'].update(height_m=1.7), lambda s: s['eyes'].update(width=0.25),
                       lambda s: s['garments'][0].update(flare=0.5), lambda s: s['garments'][1]['region'][0].__setitem__(1, 0.4),
                       lambda s: s.update(mouth={'width': 0.3}), lambda s: s.update(style='realistic')):
            assert manifest.stamp(_variant(spec, change), R['made']) == st
        for change in (lambda s: s['eyes'].update(x=0.18), lambda s: s['garments'][0].update(kind='panel'),
                       lambda s: s['garments'][1]['region'][0].__setitem__(0, 'leftUpperLeg'), lambda s: s.pop('garments')):
            assert manifest.stamp(_variant(spec, change), R['made']) != st
        manifest.produced(spec, 'made', log=lambda *a: None)
        cut = json.load(open(out))
        assert cut == {'name': 't', 'eyes': {'x': 0.17}, 'garments': [{'name': 'skirt', 'kind': 'skirt'},
                                                                       {'name': 'boots', 'kind': 'shell',
                                                                        'region': [['leftLowerLeg']]}]}
    finally:
        shutil.rmtree(d)


def test_a_reader_is_given_the_sections_of_what_it_reads():
    """the hull builds the outfit's masks from the spec it is given: its cut-down spec carries the outfit's sections
    too, and its stamp follows them through the outfit's."""
    d, mp, out, spec = _spec_setup()
    try:
        M = json.load(open(mp))
        M['references']['reader'] = dict(M['references']['made'], reads=['made'], reads_spec=['name', 'style'])
        json.dump(M, open(mp, 'w'))
        R = manifest.load(mp)['references']
        assert manifest.spec_reads(R, 'reader') == ['name', 'style', 'eyes.x', 'garments[].{name,kind,side}',
                                                     'garments[].region[].0']
        other = _variant(spec, lambda s: s['garments'].append({'name': 'collar', 'kind': 'collar'}))
        assert manifest.stamp(spec, R['reader']) != manifest.stamp(other, R['reader'])
    finally:
        shutil.rmtree(d)


def test_a_declared_file_coming_or_going_makes_it_stale():
    """the outfit reads the TRELLIS field when the copy has it (gitignored; some copies do, some don't), and the masks
    differ with it: 074d9a3f with, bc0f48dc without, under one stamp (2026-09-30). Its sha256, or its absence, is in
    the stamp now."""
    d = tempfile.mkdtemp(prefix='charkit-manifest-')
    try:
        _, mp, out, spec = _spec_setup(reads_files=[os.path.join(d, 'ext', '*', 'field.npz')])
        R = manifest.load(mp)['references']
        none = manifest.stamp(spec, R['made'])
        os.makedirs(os.path.join(d, 'ext', 'runA'))
        f = os.path.join(d, 'ext', 'runA', 'field.npz')
        open(f, 'w').write('a')
        a = manifest.stamp(spec, R['made'])
        open(f, 'w').write('bb')
        b = manifest.stamp(spec, R['made'])
        assert len({none, a, b}) == 3
        msgs = []
        manifest.produced(spec, 'made', log=msgs.append)
        assert any('runA/field.npz' in m for m in msgs)                # the build says which field it read
        assert json.load(open(out + '.stamp.json'))['files'][0][0][1] == manifest.sha256(f)
        # a copy that made it without the field rebuilds it on its own once the field arrives (the box copies whose
        # sync had wiped charkit/out/i3d kept their landmark masks under the field's stamp)
        runs = lambda: open(os.path.join(os.path.dirname(mp), 'runs')).read().count('run')
        os.remove(f)
        manifest.produced(spec, 'made', log=lambda *a: None)
        n = runs()
        manifest.produced(spec, 'made', log=lambda *a: None)
        assert runs() == n                                              # fresh without it
        open(f, 'w').write('a')
        msgs = []
        manifest.produced(spec, 'made', log=msgs.append)
        assert runs() == n + 1 and 'stale' in msgs[0]
    finally:
        shutil.rmtree(d)


def test_a_rebuild_never_writes_through_a_hard_link():
    """produced outputs are unshared before a rebuild (cache.unshare): a copy seeded with `cp -al` keeps its own."""
    d, mp, out, spec = _spec_setup()
    try:
        manifest.produced(spec, 'made', log=lambda *a: None)
        twin = os.path.join(d, 'twin.json')
        os.link(out, twin)
        before = open(twin).read()
        manifest.produced(_variant(spec, lambda s: s['eyes'].update(x=0.2)), 'made', log=lambda *a: None)
        assert open(twin).read() == before and open(out).read() != before
    finally:
        shutil.rmtree(d)


def test_the_clawd_specs_share_their_produced_references():
    """the four Clawd specs differ in body, face and garment knobs, not in the sections the produced references read:
    one hull and one outfit serve them all (a switch between them rebuilds nothing), and a face or body knob doesn't
    move the hull's stamp."""
    R = manifest.load('charkit/refs/clawd/manifest.json')['references']
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    specs = [manifest.resolve(json.load(open(os.path.join(root, 'charkit', 'spec', n + '.json'))))
             for n in ('clawd', 'clawd_body', 'clawd_body_pieces', 'clawd_code')]
    for rid in ('outfit_masks', 'hull', 'hair_layers'):
        cuts = {json.dumps(manifest.sections(s, manifest.spec_reads(R, rid)), sort_keys=True) for s in specs}
        assert len(cuts) == 1, rid
    s = specs[1]
    base = manifest.sections(s, manifest.spec_reads(R, 'hull'))
    for change in (lambda s: s['eyes'].update(width=0.3), lambda s: s['head'].update(face_len=1.1),
                   lambda s: s['body'].update(height_m=1.8), lambda s: s['garments'][0].update(offset=0.02)):
        assert manifest.sections(_variant(s, change), manifest.spec_reads(R, 'hull')) == base


def test_a_read_references_data_counts_its_prose_doesnt():
    """what a producer reads of a reference beyond its picture (the rig's scale, a sheet's layout) is in its readers'
    stamps; its role, cautions and provenance aren't."""
    d, mp, out, spec = _spec_setup()
    try:
        M = json.load(open(mp))
        M['references']['made']['reads'] = ['art']
        M['references']['art']['scale'] = {'eye_x': 0.168}
        json.dump(M, open(mp, 'w'))
        st = lambda: manifest.stamp(spec, manifest.load(mp)['references']['made'])
        s0 = st()
        for change, moves in ((lambda e: e.update(role='the design'), False),
                              (lambda e: e.update(cautions=['drawn twice']), False),
                              (lambda e: e['scale'].update(eye_x=0.17), True),
                              (lambda e: e.update(layout='figures'), True)):
            M = json.load(open(mp))
            change(M['references']['art'])
            json.dump(M, open(mp, 'w'))
            s1 = st()
            assert (s1 != s0) == moves
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
