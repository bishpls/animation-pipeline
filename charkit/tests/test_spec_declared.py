"""A spec declares what it builds on (docs/CHARKIT_HANDOFF.md, decision 7): its base and its body's source, with no
default. A second character's spec with only `name` and `ref.manifest` once built MakeHuman's bald default and reported
success; now it stops at load, before any build work. And a produced reference whose producer ran without making it stops
the build rather than being stamped (venv: run this file, or pytest)."""
import glob, json, os, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from charkit import bodyeval, character, cli, manifest

MANIFEST = 'charkit/refs/clawd/manifest.json'
BARE = {'name': 'second', 'ref': {'manifest': MANIFEST}}
# every spec in charkit/spec, as it builds: (base, body source). A spec added there must be listed (and declare both)
DECLARED = {'clawd': ('code', 'code'), 'clawd_body': ('code', 'code'), 'clawd_body_pieces': ('code', 'code'),
            'clawd_code': ('code', 'makehuman'), 'clawd_mh': ('makehuman', 'makehuman'),
            'clawd_locks': ('makehuman', 'makehuman')}
NOT_SPECS = {'clawd_ref'}      # the design rig's measurements (charkit.refs writes it), not a character spec


def _raises(fn, *args, **kw):
    try:
        fn(*args, **kw)
    except character.SpecError as e:
        return str(e)
    raise AssertionError('%s did not raise SpecError' % fn.__name__)


def test_a_bare_spec_raises_naming_it_and_the_allowed_values():
    e = _raises(character.base_of, dict(BARE))
    assert "'second'" in e and "'base' is missing" in e and "'code' | 'anime' | 'makehuman'" in e, e
    e = _raises(character.body_source, dict(BARE, base='code'))
    assert "'second'" in e and "'body.source' is missing" in e and "'code' | 'makehuman'" in e, e
    assert "set to 'mh'" in _raises(character.base_of, dict(BARE, base='mh'))
    assert "set to 'hull'" in _raises(character.body_source, dict(BARE, base='code', body={'source': 'hull'}))
    # a code body on another base would build MakeHuman's body: that's a fallback too
    assert "needs base 'code'" in _raises(character.body_source, dict(BARE, base='anime', body={'source': 'code'}))
    _raises(character.check_spec, dict(BARE))
    _raises(character.assemble, dict(BARE), keys=False)


def test_a_bare_spec_stops_before_any_build_work():
    """cli.resolve (build, fit) and the evaluator's resolve raise before manifest.produce makes a reference."""
    d = tempfile.mkdtemp(prefix='charkit-spec-')
    p = os.path.join(d, 'second.json')
    json.dump(BARE, open(p, 'w'))
    made = []
    real = manifest.produce
    manifest.produce = lambda spec: made.append(spec) or spec
    try:
        _raises(cli.resolve, p, d)
        _raises(bodyeval.resolve, p, check=True)
        _raises(bodyeval.Evaluator, dict(BARE))
        # --base alone isn't enough: the body's source is declared too
        assert "'body.source' is missing" in _raises(cli.resolve, p, d, base='makehuman')
    finally:
        manifest.produce = real
    assert not made, 'a reference was produced for an undeclared spec'
    assert os.listdir(d) == ['second.json'], os.listdir(d)


def test_every_spec_declares_its_base_and_body():
    found = {os.path.basename(f)[:-5] for f in glob.glob(os.path.join(ROOT, 'charkit', 'spec', '*.json'))}
    assert found == set(DECLARED) | NOT_SPECS, 'charkit/spec changed: list %s' % sorted(found ^ (set(DECLARED) | NOT_SPECS))
    for n in NOT_SPECS:
        assert 'name' not in json.load(open(os.path.join(ROOT, 'charkit', 'spec', n + '.json'))), n
    for n, (base, body) in DECLARED.items():
        S = manifest.resolve(json.load(open(os.path.join(ROOT, 'charkit', 'spec', n + '.json'))))
        assert character.check_spec(S) is S
        assert (character.base_of(S), character.body_source(S)) == (base, body), (n, S.get('base'), S['body'].get('source'))


def test_a_producer_that_makes_nothing_stops_the_build():
    """manifest.produced: a producer that runs without error but writes no output raises, and nothing is stamped."""
    d = tempfile.mkdtemp(prefix='charkit-produced-')
    out = os.path.join(d, 'made.txt')
    M = {'name': 't', 'references': {'made': {'kind': 'test', 'tracked': False, 'produced_by': 'charkit.manifest',
                                              'path': out, 'command': 'python -c "pass"'}}}
    mp = os.path.join(d, 'manifest.json')
    json.dump(M, open(mp, 'w'))
    spec = {'name': 't', 'ref': {'manifest': mp}, 'x': out}
    env = os.environ.get('CHARKIT_PRODUCED_CACHE')
    os.environ['CHARKIT_PRODUCED_CACHE'] = 'off'
    try:
        manifest.produced(spec, 'made', log=lambda *a: None)
    except RuntimeError as e:
        assert 'made no' in str(e), e
    else:
        raise AssertionError('a producer that made nothing passed')
    finally:
        if env is None:
            os.environ.pop('CHARKIT_PRODUCED_CACHE')
        else:
            os.environ['CHARKIT_PRODUCED_CACHE'] = env
    assert not os.path.exists(out + '.stamp')


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok', name)
