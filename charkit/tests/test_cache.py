"""charkit.cache: exact digests, recorded reads, the code closure, the file memo, and invalidation by a changed code file,
input file or spec section (venv: run this file, or pytest). test_blender_restore runs this file again inside Blender for a
stage checkpointed and restored onto a rebuilt 'upstream' (a vertex group and a modifier replayed on an earlier object).
The full builds (cold, warm, a face-only and a garment-only change, a changed GLB and code file) are
charkit/tests/cache_builds.py."""
import json, os, shutil, subprocess, sys, tempfile, time, types

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from charkit import cache  # noqa: E402

BLENDER = os.environ.get('BLENDER', '/Applications/Blender.app/Contents/MacOS/Blender')


def test_digest_exact():
    d = cache.digest
    assert d({'a': 1, 'b': 2}) != d({'b': 2, 'a': 1})                     # order counts (it can change what a stage makes)
    assert d(0.0) != d(-0.0) and d(1.0) != d(1) and d(True) != d(1)
    assert d([1.0] * 20) != d([1] * 20) and d([(1, 2)] * 20) != d([[1, 2]] * 20)
    a = np.linspace(0, 1, 7)
    b = a.copy(); b[3] = np.nextafter(b[3], 2)                              # one ulp
    assert d(a) != d(b) and d(a) == d(a.copy())
    assert d(np.zeros((2, 3))) != d(np.zeros((3, 2))) and d(np.zeros(3, np.float32)) != d(np.zeros(3))
    assert d({1, 2, 3}) == d({3, 2, 1})
    assert d(cache.TrackedDict({'x': 1}, ('S', 'x'))) == d({'x': 1})


def test_recorded_reads():
    rec = cache.Recorder(None, 'probe', {'data.verts': lambda v, S: v[:2]}, None)
    A = cache.TrackedDict({'verts': np.arange(6.0), 'head': {'L': 0.25}, 'joints': {'a': 1, 'b': 2}}, ('S', 'data'))
    cache.adopt(types.SimpleNamespace(data=A), ['data'])
    cache._REC = rec
    try:
        A['verts']; A['head']['L']; 'c' in A['joints']; A.get('missing'); list(A['joints'])
        A['new'] = 1; A['new']
        (A.get('head') or {}).get('L')                                    # truthiness: whether it's empty, not all of it
    finally:
        cache._REC = None
    got = {cache.readable(p) for p in rec.reads}
    assert got == {'data.verts', 'data.head.L', 'data.joints.c?', 'data.missing', 'data.joints[*]', 'data.joints[len]',
                   'data.head[empty?]'}, got
    # the declared part: verts keyed on their first two rows only
    assert rec.reads[('S', 'data', 'verts')] == cache.digest(np.arange(2.0))
    assert ('S', 'data', 'new') in rec.writes and ('S', 'data', 'new') not in rec.reads


def _kit(tmp):
    """a copy of charkit's sources to edit, with cache.py pointed at it."""
    kit = os.path.join(tmp, 'charkit')
    shutil.copytree(os.path.join(ROOT, 'charkit'), kit, ignore=shutil.ignore_patterns('out', '__pycache__', 'assets',
                                                                                        'tests', 'refs', 'spec'))
    os.makedirs(os.path.join(kit, 'assets'))
    return kit


class _Patch:
    def __init__(self, tmp, kit):
        self.v = dict(ROOT=cache.ROOT, KIT=cache.KIT, env=os.environ.get('CHARKIT_CACHE_DIR'))
        cache.ROOT, cache.KIT = tmp, kit
        os.environ['CHARKIT_CACHE_DIR'] = os.path.join(tmp, 'cache')
        cache._MODS.clear(); cache._DISK[:] = [None, False]

    def undo(self):
        cache.ROOT, cache.KIT = self.v['ROOT'], self.v['KIT']
        if self.v['env'] is None:
            os.environ.pop('CHARKIT_CACHE_DIR', None)
        else:
            os.environ['CHARKIT_CACHE_DIR'] = self.v['env']
        cache._MODS.clear(); cache._DISK[:] = [None, False]


def _fn(module, name):
    return types.SimpleNamespace(__module__=module, __name__=name)


def test_code_closure():
    tmp = tempfile.mkdtemp()
    kit = _kit(tmp)
    P = _Patch(tmp, kit)
    try:
        g = cache.code_units(_fn('charkit.scene', 'stage_garments'))
        h = cache.code_units(_fn('charkit.scene', 'stage_hair'))
        assert 'charkit/garments.py' in g and 'charkit/scene.py:stage_garments' in g and 'charkit/qa3d.py' not in g
        assert 'charkit/hair.py' in h and 'charkit/garments.py:' not in ''.join(h)

        def edit(rel, old, new):
            p = os.path.join(kit, rel)
            s = open(p).read()
            assert old in s, (rel, old)
            open(p, 'w').write(s.replace(old, new, 1))
            st = os.stat(p); os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
            cache._MODS.clear()
        edit('garments.py', '"""Garments', '# a comment\n"""Garments (a docstring edit)')
        assert cache.code_units(_fn('charkit.scene', 'stage_garments')) == g             # comments and docs don't count
        edit('garments.py', "sol.thickness = 0.01 * L", "sol.thickness = 0.011 * L")
        g2 = cache.code_units(_fn('charkit.scene', 'stage_garments'))
        assert [u for u in g if g[u] != g2.get(u)] == ['charkit/garments.py']
        assert cache.code_units(_fn('charkit.scene', 'stage_hair')) == h                 # hair doesn't run garments.py
        edit('scene.py', "S.garments = garments.build(", "S.garments = garments.build(  ")   # formatting only
        assert cache.code_units(_fn('charkit.scene', 'stage_garments')) == g2
        edit('scene.py', "    if S.spec.get('hair') is None:\n        return", "    if not S.spec.get('hair'):\n        return")
        assert cache.code_units(_fn('charkit.scene', 'stage_garments')) == g2              # another stage's function
        assert cache.code_units(_fn('charkit.scene', 'stage_hair')) != h
    finally:
        P.undo()
        shutil.rmtree(tmp, ignore_errors=True)


def test_file_memo():
    tmp = tempfile.mkdtemp()
    try:
        p = os.path.join(tmp, 'a.bin')
        open(p, 'wb').write(b'one')
        F = cache.Files(tmp)
        h1 = F.get(p)
        old = time.time() - 10
        os.utime(p, (old, old))
        F2 = cache.Files(tmp); h1b = F2.get(p); F2.save()
        open(p, 'wb').write(b'two')                                       # same size, new content, mtime restored
        os.utime(p, (old, old))
        assert cache.Files(tmp).get(p) == h1b == h1                      # (the one blind spot of a stat memo, as git's)
        os.utime(p, None)
        assert cache.Files(tmp).get(p) != h1                             # any stamp change: hashed again
        assert cache.Files(tmp).get(os.path.join(tmp, 'nope')) == 'absent'
        assert cache.spec_paths({'x': [os.path.relpath(p, cache.ROOT) if p.startswith(cache.ROOT) else p, 'bun']}) == {p}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _probe_fit(spec, n):
    """(the probe step: reads spec.a and a file, writes spec.b)"""
    spec['b'] = spec['a'] * n + len(open(spec['path'], 'rb').read())
    return spec


def test_invalidation():
    """a spec-only step, run then restored; a change to the code file it runs, the input file it reads, or the spec section
    it reads makes it run again (and says why); a section it doesn't read doesn't."""
    tmp = tempfile.mkdtemp()
    kit = _kit(tmp)
    probe = os.path.join(kit, 'probe.py')
    open(probe, 'w').write(
        "def _probe_fit(spec, n):\n    spec['b'] = spec['a'] * n + len(open(spec['path'], 'rb').read())\n    return spec\n")
    _probe_fit.__module__ = 'charkit.probe'
    inp = os.path.join(tmp, 'input.bin')
    open(inp, 'wb').write(b'12345')
    P = _Patch(tmp, kit)
    try:
        def build(spec):
            C = cache.Cache('on', 'probe')
            out = C.spec_step('probe', _probe_fit, dict(spec), 3)
            C.finish()
            return dict(out), ('hit' if 'probe' not in C.ran else 'miss'), C
        spec = {'a': 2, 'c': 'x', 'path': inp}
        out, r, _ = build(spec)
        assert r == 'miss' and out['b'] == 11
        out, r, _ = build(spec)
        assert r == 'hit' and out['b'] == 11, (r, out)                      # restored: b set without running
        out, r, _ = build(dict(spec, c='y'))
        assert r == 'hit'                                                   # a section it never read
        out, r, _ = build(dict(spec, a=3))
        assert r == 'miss' and out['b'] == 14                               # spec.a
        open(inp, 'wb').write(b'123456')                                     # the input file's content
        out, r, _ = build(spec)
        assert r == 'miss' and out['b'] == 12, (r, out)
        open(probe, 'a').write('\n\nX = 1\n')                                 # the code file it runs
        old = time.time() - 5                                                  # (edited before the next build starts)
        os.utime(probe, (old, old)); cache._MODS.clear()
        C = cache.Cache('on', 'probe')
        E, why = C.lookup('stages', 'probe', *C.static('stages', 'probe', [_probe_fit], extra=[3]), types.SimpleNamespace(
            spec=cache.TrackedDict(spec, ('spec',))), None)
        assert E is None and why.startswith('code charkit/probe.py'), why
        out, r, _ = build(spec)
        assert r == 'miss'
        out, r, _ = build(spec)
        assert r == 'hit'
        # a source edited while a build runs: the keys read the file, the build ran the code it had loaded, so it stores
        # nothing (the next build runs it again)
        C = cache.Cache('on', 'probe')
        open(probe, 'a').write('\nY = 2\n'); cache._MODS.clear()
        C.spec_step('probe', _probe_fit, dict(spec), 3); C.finish()
        assert 'probe' in C.ran and C.now['probe']['entry'] is None and C.edited() == 'charkit/probe.py', C.now
        old = time.time() - 5
        os.utime(probe, (old, old))
        out, r, _ = build(spec)
        assert r == 'miss'
        out, r, _ = build(spec)
        assert r == 'hit'
    finally:
        P.undo()
        _probe_fit.__module__ = __name__
        shutil.rmtree(tmp, ignore_errors=True)


def test_products_store_only_clean_runs():
    """a product is restored by copy when nothing changed; a run that printed a traceback (a check that failed on an
    error it caught), or one with too little disk left, isn't stored; a PNG's date stamp doesn't count as content."""
    tmp = tempfile.mkdtemp()
    env0 = os.environ.get('CHARKIT_CACHE_DIR')
    os.environ['CHARKIT_CACHE_DIR'] = os.path.join(tmp, 'cache')
    out = os.path.join(tmp, 'out'); os.makedirs(out)
    try:
        def build(run, name='probe'):
            C = cache.Cache('on', 'probe', out)
            C.chain, C.spec = [('stage', 'entry1')], {'name': 'probe'}
            hit = C.product(name, run, [cache.content_digest])
            C.finish()
            return hit

        def ok():
            open(os.path.join(out, 'a.txt'), 'w').write('made')
            print('CHARKIT_PROBE made')
        assert build(ok) is False and build(ok) is True                     # stored, then restored
        os.remove(os.path.join(out, 'a.txt'))
        assert build(ok) is True and open(os.path.join(out, 'a.txt')).read() == 'made'

        def caught():
            try:
                raise OSError(28, 'No space left on device')
            except OSError:
                import traceback
                traceback.print_exc()                                        # (as qa3d does, then records SKIPPED)
            open(os.path.join(out, 'b.txt'), 'w').write('half')
        assert build(caught, 'probe2') is False and build(caught, 'probe2') is False
        os.environ['CHARKIT_CACHE_MIN_FREE_GB'] = '1e9'
        assert build(ok, 'probe3') is False and build(ok, 'probe3') is False
        del os.environ['CHARKIT_CACHE_MIN_FREE_GB']
        # PNG content: the text and time chunks left out
        import struct, zlib

        def png(date):
            def chunk(t, d):
                return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d))
            raw = b'\x00\xff\x00\x00'
            return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)) +
                    chunk(b'tEXt', b'Date\x00' + date) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))
        a, b = os.path.join(tmp, 'a.png'), os.path.join(tmp, 'b.png')
        open(a, 'wb').write(png(b'2026/09/28 10:20:18')); open(b, 'wb').write(png(b'2026/09/28 11:00:00'))
        assert cache.content_digest(a) == cache.content_digest(b) and open(a, 'rb').read() != open(b, 'rb').read()
        # large state is stored compressed and reads back
        big = os.urandom(16) * (1 << 19)
        cache._write_state(os.path.join(tmp, 's.pkl'), big)
        assert cache._read_state(os.path.join(tmp, 's.pkl')) == big and os.path.getsize(os.path.join(tmp, 's.pkl')) < len(big)
    finally:
        if env0 is None:
            os.environ.pop('CHARKIT_CACHE_DIR', None)
        else:
            os.environ['CHARKIT_CACHE_DIR'] = env0
        os.environ.pop('CHARKIT_CACHE_MIN_FREE_GB', None)
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------------------- Blender
def _in_blender():
    """(run inside Blender) an 'upstream' stage makes a mesh; a stage under test adds two objects, a material in
    shade.MATS, a vertex group and a MASK modifier (first in the stack) on the upstream mesh, and a Scene attribute. Built
    once (stored), the upstream is rebuilt with other geometry and the stage restored onto it: the trace records and the
    replayed group, modifier and attribute must match a fresh run's."""
    import bpy
    from charkit import scene, shade, trace
    tmp = tempfile.mkdtemp()
    os.environ['CHARKIT_CACHE_DIR'] = os.path.join(tmp, 'cache')

    def up(S, z=0.0):
        me = bpy.data.meshes.new('base'); me.from_pydata([(0, 0, z), (1, 0, z), (0, 1, z), (1, 1, z + 0.5)], [],
                                                         [(0, 1, 3, 2)])
        ob = bpy.data.objects.new('base', me); bpy.context.scene.collection.objects.link(ob)
        ob.modifiers.new('sub', 'SUBSURF')
        S.base = ob

    def stage(S):
        ob = S.base
        m = shade.flat('probe_mat', (0.2, 0.4, 0.6))
        for i in range(2):
            me = bpy.data.meshes.new('piece%d' % i); me.from_pydata([(i, 0, 1), (i + 1, 0, 1), (i, 1, 1)], [], [(0, 1, 2)])
            me.materials.append(m)
            o = bpy.data.objects.new('piece%d' % i, me); bpy.context.scene.collection.objects.link(o); o.parent = ob
        g = ob.vertex_groups.new(name='hide'); g.add([0, 1], 1.0, 'REPLACE')
        mk = ob.modifiers.new('hide', 'MASK'); mk.vertex_group = 'hide'; mk.invert_vertex_group = True
        with bpy.context.temp_override(object=ob):
            bpy.ops.object.modifier_move_to_index(modifier='hide', index=0)
        S.pieces = [bpy.data.objects['piece0'], bpy.data.objects['piece1']]
    stage.__module__ = 'charkit.scene'                       # (its code key: scene.py's top level)
    deps = {'base': 'structure'}

    def build(z, mode):
        from charkit import cache
        scene.reset()
        trace.begin(os.path.join(tmp, 'trace_%s_%s.jsonl' % (z, mode)))
        C = cache.Cache(mode, 'probe', tmp)
        S = types.SimpleNamespace(spec=cache.TrackedDict({'name': 'probe'}, ('spec',)))
        with trace.stage('up', S):
            up(S, z)
        C.stage('probe', stage, S, deps)
        C.finish()
        rec = trace.last()
        trace.end()
        ob = bpy.data.objects['base']
        return (rec, [m.name for m in ob.modifiers], sorted((v.index, g.weight) for v in ob.data.vertices for g in v.groups),
                sorted(dict.keys(shade.MATS)), [o.name for o in S.pieces], 'probe' not in C.ran)
    a = build(0.0, 'on')                                    # stored
    assert not a[-1]
    b = build(0.3, 'on')                                    # the upstream moved (its structure didn't): restored onto it
    c = build(0.3, 'off')                                   # the same, run
    assert b[-1], 'not restored'
    for x, y in zip(b[1:-1], c[1:-1]):
        assert x == y, (x, y)
    from charkit.cache import _record_diff, _norm
    assert not _record_diff(_norm(c[0]), _norm(b[0])), _record_diff(_norm(c[0]), _norm(b[0]))
    shutil.rmtree(tmp, ignore_errors=True)
    print('CHARKIT_TEST_OK')


def test_blender_restore():
    if not os.path.exists(BLENDER):
        print('skip: no Blender'); return
    r = subprocess.run([BLENDER, '-b', '--factory-startup', '--python', os.path.abspath(__file__)], capture_output=True,
                       text=True, timeout=600)
    assert 'CHARKIT_TEST_OK' in r.stdout, (r.stdout + r.stderr)[-3000:]


if __name__ == '__main__':
    if 'bpy' in sys.modules:
        _in_blender()
    else:
        for k, f in list(globals().items()):
            if k.startswith('test_'):
                f(); print('ok', k)
