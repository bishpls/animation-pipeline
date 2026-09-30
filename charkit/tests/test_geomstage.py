"""charkit.geomstage: the garments stage's recording (garments.build's Blender calls, venv-side), its product on disk, and
its replay, on stand-ins with known answers (venv: run this file, or pytest). The whole-outfit check (every garment of a
spec, per-piece recordings against the build's one) is `python -m charkit.stagedrift` on a build."""
import json, os, sys, tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import eyetex, garments, geomstage, shade


def _build_like(skin, arm):
    """what garments.build does through its seam for one textured piece with a second material, a Solidify, the
    subdivision, the outline, a custom property and the skin mask."""
    V = np.random.default_rng(0).normal(size=(12, 3))
    faces = [(0, 1, 2, 3), (4, 5, 6), (7, 8, 9, 10), (1, 2, 11), (0, 3, 4), (5, 6, 7), (8, 9, 10), (2, 3, 4),
             (6, 7, 8), (9, 10, 11)]
    uvc = [[(0.1 * i, 0.2 * j) for j in range(len(f))] for i, f in enumerate(faces)]
    img = eyetex.to_blender_image('skirt_tex', np.full((4, 4, 4), 0.5))
    mats = [garments._toon_tex('skirt', img, None), garments._toon('skirt_panel', (0.2, 0.3, 0.4), [0.7, 0.6, 0.6])]
    ob = garments._object('skirt', V, faces, {'hips': np.linspace(0, 1, 12)}, arm, mats, uv_corner=uvc,
                          mat_idx=[0, 1] * 5)
    sol = ob.modifiers.new('thick', 'SOLIDIFY'); sol.thickness = 0.01 * 0.25; sol.offset = -1
    sub = ob.modifiers.new('sub', 'SUBSURF'); sub.levels = 1; sub.render_levels = 1
    shade.outline(ob, thick=0.0012, color=(0.3, 0.18, 0.16), name='garment_line')
    ob['charkit_coverage'] = 0.4
    hide = np.zeros(20, bool); hide[[3, 5, 8]] = True
    garments.mask_skin(skin, hide)
    return V, faces, uvc


def test_record_and_read_back():
    before = {fn: getattr(m, fn) for m, fn in ((garments, '_object'), (garments, '_toon'), (shade, 'outline'))}
    with geomstage.recording() as rec:
        V, faces, uvc = _build_like(geomstage._Ref(rec, 'skin', 'the skin'), geomstage._Ref(rec, 'arm', 'the armature'))
    assert all(getattr(m, fn) is before[fn] for m, fn in ((garments, '_object'), (garments, '_toon'), (shade, 'outline')))
    P = geomstage.product('garments', rec)
    with tempfile.TemporaryDirectory() as d:
        geomstage.save(P, os.path.join(d, 'g.npz'))
        Q = geomstage.load(os.path.join(d, 'g.npz'))
    assert geomstage.digest(P) == geomstage.digest(Q)
    obs, hide = geomstage.pieces(Q)
    assert len(obs) == 1 and np.nonzero(hide)[0].tolist() == [3, 5, 8]
    o = obs[0]
    assert o['name'] == 'skirt' and np.array_equal(o['V'], V) and o['polys'] == faces       # exact, as tuples
    assert o['uv_corner'] == uvc and o['mat_idx'] == [0, 1] * 5
    assert [m['fn'] for m in o['materials']] == ['toon_tex', 'toon']
    assert o['materials'][1]['color'] == (0.2, 0.3, 0.4) and o['materials'][1]['shade'] == [0.7, 0.6, 0.6]
    assert o['materials'][0]['image'].dtype == np.float32
    assert o['mods'] == {'thick': dict(type='SOLIDIFY', settings=dict(thickness=0.0025, offset=-1)),
                         'sub': dict(type='SUBSURF', settings=dict(levels=1, render_levels=1))}
    assert o['outline'] == dict(thick=0.0012, color=(0.3, 0.18, 0.16), name='garment_line')
    assert o['props'] == {'charkit_coverage': 0.4}


def test_replay_calls_the_seam_in_order():
    """replay() makes the recorded calls for real, in the recorded order and with the recorded values."""
    with geomstage.recording() as rec:
        _build_like(geomstage._Ref(rec, 'skin', 'the skin'), geomstage._Ref(rec, 'arm', 'the armature'))
    P = geomstage.product('garments', rec)
    P = json.loads(json.dumps(P['meta'])), P['arrays']
    P = dict(meta=P[0], arrays=P[1])
    log = []

    class Mod:
        def __init__(self, name):
            object.__setattr__(self, 'name', name)

        def __setattr__(self, k, v):
            log.append(('set', self.name, k, v))

    class Mods:
        def new(self, name, type_):
            log.append(('mod', name, type_))
            return Mod(name)

    class Ob(dict):
        def __init__(self):
            super().__init__()
            self.modifiers = Mods()

        def __setitem__(self, k, v):
            log.append(('item', k, v))

    def fake(fn):
        def f(*a, **k):
            log.append((fn, a, k))
            return Ob() if fn == '_object' else 'img' if fn == 'to_blender_image' else 'mat:' + str(a[0]) if fn in (
                '_toon', '_toon_tex') else None
        return f
    saved = [(m, fn, getattr(m, fn)) for m, fn in ((garments, '_object'), (garments, '_toon'), (garments, '_toon_tex'),
                                                   (garments, 'mask_skin'), (eyetex, 'to_blender_image'),
                                                   (shade, 'outline'))]
    try:
        for m, fn, _ in saved:
            setattr(m, fn, fake(fn))
        obs = geomstage.replay(P, {'arm': 'ARM', 'skin': 'SKIN'})
    finally:
        for m, fn, f in saved:
            setattr(m, fn, f)
    kinds = [e[0] for e in log]
    assert kinds == ['to_blender_image', '_toon_tex', '_toon', '_object', 'mod', 'set', 'set', 'mod', 'set', 'set',
                     'outline', 'item', 'mask_skin']
    obj = next(e for e in log if e[0] == '_object')
    assert obj[1][4] == 'ARM' and obj[1][5] == ['mat:skirt', 'mat:skirt_panel'] and len(obs) == 1
    assert next(e for e in log if e[0] == 'mask_skin')[1][0] == 'SKIN'
    assert ('set', 'thick', 'thickness', 0.0025) in log


def test_outside_the_seam_fails_loudly():
    with geomstage.recording() as rec:
        ob = garments._object('x', np.zeros((3, 3)), [(0, 1, 2)], {}, geomstage._Ref(rec, 'arm', 'a'), [])
        for f in (lambda: ob.data, lambda: ob.modifiers.find('x'), lambda: geomstage._Ref(rec, 'skin', 's').vertex_groups):
            try:
                f()
            except geomstage.SeamError:
                continue
            raise AssertionError('no SeamError')


def test_images_are_shared():
    """a recorded texture is kept once per content (the evaluator records a skirt for every body a fit tries)."""
    a = np.random.default_rng(1).random((8, 8, 4))
    with geomstage.recording() as r1:
        eyetex.to_blender_image('t', a)
    with geomstage.recording() as r2:
        eyetex.to_blender_image('t', a.copy())
    x1 = next(iter(r1.arrays.values())); x2 = next(iter(r2.arrays.values()))
    assert x1 is x2 and x1.dtype == np.float32 and np.array_equal(x1, a.astype(np.float32))


if __name__ == '__main__':
    for k, v in list(globals().items()):
        if k.startswith('test_'):
            v()
            print('ok', k)
