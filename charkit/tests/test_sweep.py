"""charkit sweep (charkit/sweep.py) on synthetic inputs (venv: run this file): overrides by dotted path, the rows a
declaration expands to, a splice into a bundle, the qa stage's measurement patches, swap mode's attribution and the
guard; and, where the historical builds are on this machine, the acceptance reproduction of hair round 5's terminator
swap (tools/hair5/term.py's numbers, docs/workstreams/sweep.md)."""
import os, sys, tempfile, types

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import bundle, registry, sweep

os.environ.setdefault('CHARKIT_SLOT_HELD', str(os.getpid()))   # (the tests' sweeps take no machine build slot)
PROBE = sys.modules.setdefault('sweep_probe_mod', types.ModuleType('sweep_probe_mod'))
PROBE.scale = 1.0                 # the attribute a row's `qa:sweep_probe_mod.scale` patch sets while it is measured


@registry.qa_part('sweep_probe', order=987654)
def sweep_probe(B, design=None, out=None):
    """a test part: the hair objects' summed height (times sweep_probe_mod.scale) and a shape check per hair object."""
    z = sum(float(o.V('eval')[:, 2].sum()) for o in B.objects(groups=('hair',)))
    C = {'probe_z': dict(value=round(z * sys.modules['sweep_probe_mod'].scale, 6), status='PASS' if z < 5 else 'FAIL',
                         flag='a test flag')}
    for o in B.objects(groups=('hair',)):
        C['piece_' + o.name] = dict(value=1.0, status='PASS', views={'front': float(o.V('eval')[:, 0].max())})
    return None, C


def small(dz=0.0, extra=False):
    """a skin quad and two hair quads (hair_a, hair_b), outlined; dz lifts hair_b; extra adds hair_c."""
    b = bundle.Builder({'name': 't'}, {'L': 1.0, 'centre': [0, 0, 0], 'eyes': [], 'mouth': {}}, {'ppl': 100})
    b.material('skin', lit=(1.0, 0.9, 0.86))
    b.material('hair', lit=(0.5, 0.3, 0.2))
    b.material('line', lit=(0.1, 0.1, 0.1), cull=True)
    Q = np.array([[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1]], float)
    b.add('skin', 'skin', {'eval': dict(V=Q, faces=[(0, 1, 2, 3)], pmat=[0])}, materials=['skin'])
    for name, d in (('hair_a', 0.0), ('hair_b', dz)) + ((('hair_c', 0.5),) if extra else ()):
        b.add(name, 'hair', {'eval': dict(V=Q + [0, -0.1, d], faces=[(0, 1, 2, 3)], pmat=[0])}, materials=['hair', 'line'],
              outline=dict(slot=1, thickness=0.002, offset=1.0))
    return b


def build_dir(d, b):
    """a build folder holding the bundle (what sweep reads as a base)."""
    os.makedirs(os.path.join(d, 'bundle'), exist_ok=True)
    bundle.write(os.path.join(d, 'bundle'), b.meta, b.arrays)
    return d


def test_apply_overrides():
    spec = {'garments': [{'name': 'bow', 'pleat': {'tilt': 0.5}}, {'name': 'top', 'kind': 'jacket'}], 'hair': {}}
    s = sweep.apply(spec, {'garments.bow.pleat.tilt': 1.0, 'garments.jacket.len': 2, 'hair.shape.mode': 'pieces',
                           'garments.0.gone': None, 'qa:charkit.x.Y': 3, 'style.hair_pieces.notch': 3})
    assert s['garments'][0]['pleat']['tilt'] == 1.0 and spec['garments'][0]['pleat']['tilt'] == 0.5   # (a copy)
    assert s['garments'][1]['len'] == 2 and s['hair'] == {'shape': {'mode': 'pieces'}}
    assert 'qa:charkit.x.Y' not in s and 'style' not in s
    s = sweep.apply(spec, {'garments.bow.pleat': None})
    assert 'pleat' not in s['garments'][0]


def test_expand_rows():
    d = dict(base='/b', set={'a.x': 1}, variants={'v1': {'a.y': 2}}, grid={'p.q.tilt': [0, 1], 'r.shear': [5]},
             oat={'a.z': [7, 8]})
    rows = sweep.expand(d)
    names = [r['name'] for r in rows]
    assert names == ['control', 'v1', 'tilt=0,shear=5', 'tilt=1,shear=5', 'z=7', 'z=8'], names
    assert all(r['set']['a.x'] == 1 for r in rows) and rows[1]['set']['a.y'] == 2 and rows[0].get('control')
    assert sweep.expand(dict(base='/b', control=False, oat={'a': [1]}))[0]['name'] == 'a=1'
    try:
        sweep.expand(dict(base='/b', variants={'z=7': {}}, oat={'a.z': [7]}))
        raise AssertionError('a row named twice must stop the sweep')
    except SystemExit:
        pass


def test_splice_and_garment_arrays():
    B0 = small().build()
    V = np.array([[0, 0, 0], [2, 0, 0], [2, 0, 1], [0, 0, 1]], float) + [0, -0.1, 0]
    F = np.array([[0, 1, 2], [0, 2, 3]])
    rep, drop = sweep.garment_arrays(B0, 'hair_a', V, F)
    B = sweep.spliced(B0, rep, drop + ['o/hair_b/eval/V'])
    assert B.path is None and B.meta('content') is None
    Va, T = B.obj('hair_a').mesh('eval')[:2]
    assert np.allclose(Va, V) and len(T) == 2 and not B.has('o/hair_b/eval/V')
    assert np.allclose(B0.obj('hair_a').V('eval')[:, 0].max(), 1.0)                 # (the base untouched)
    sh = B.array('o/hair_a/eval/shrink') if B.has('o/hair_a/eval/shrink') else None
    if sh is not None:                                                                 # |thickness| (1 + offset) / 2
        assert np.allclose(np.linalg.norm(sh, axis=1), 0.002, atol=1e-6)


def test_qa_stage_patches_and_table():
    with tempfile.TemporaryDirectory() as d:
        base = build_dir(os.path.join(d, 'base'), small())
        decl = dict(base=base, stage='qa', parts=['sweep_probe'], checks=['probe_*'], shape_parts=[],
                    oat={'qa:sweep_probe_mod.scale': [2.0]})
        res = sweep.run(decl, os.path.join(d, 'out'), log=lambda *a: None)
        v = {r['name']: r['checks']['probe_z']['value'] for r in res['rows']}
        assert v == {'control': 4.0, 'scale=2.0': 8.0}, v
        assert PROBE.scale == 1.0                               # (restored)
        assert res['rows'][1]['checks']['piece_hair_a']['views'] == {'front': 1.0}
        md = open(os.path.join(d, 'out', 'sweep.md')).read()
        assert 'probe_z [F]' in md and '(+' in md and os.path.exists(os.path.join(d, 'out', 'control', 'res.json'))


def test_guard():
    c = dict(name='control', control=True, set={}, objects=[], checks={
        'x_check': dict(value=0.3, status='FAIL'), 'piece_bow': dict(value=0.8, views={'front': 0.9, 'profile': 0.5})})
    good = dict(name='ok', set={'a': 1}, objects=['bow'], checks={
        'x_check': dict(value=0.1, status='PASS'), 'piece_bow': dict(value=0.8, views={'front': 0.88, 'profile': 0.49})})
    gamed = dict(name='gamed', set={'a': 2}, objects=['bow'], checks={
        'x_check': dict(value=0.1, status='PASS'), 'piece_bow': dict(value=0.7, views={'front': 0.9, 'profile': 0.34})})
    res = dict(decl=dict(base='/b', stage='garments', checks=['x_*']), rows=[c, good, gamed])
    G = sweep.guard(res)
    assert [(g['row'], g['shape'], g['view']) for g in G] == [('gamed', 'piece_bow', 'profile')], G
    res['guard'] = G
    md = sweep.table(res)
    assert '**Guard:**' in md and 'piece_bow profile' in md


def test_swap_attribution():
    with tempfile.TemporaryDirectory() as d:
        A = build_dir(os.path.join(d, 'A'), small(0.0))
        B = build_dir(os.path.join(d, 'B'), small(1.0, extra=True))
        res = sweep.swap(A, B, 'probe_z', part='sweep_probe', drop=True, out=os.path.join(d, 'out'),
                         log=lambda *a: None)
        R = {r['name']: r for r in res['rows']}
        # each quad's heights sum to 2; B lifts hair_b by 1 (+4) and adds hair_c at 0.5 (+4): A 4, B 12
        assert R['A']['value'] == 4.0 and R['B']['value'] == 12.0
        assert R['A + B.hair_b']['value'] == 8.0 and R['A + B.hair_b']['carries'] == 0.5
        assert R['B + A.hair_b']['value'] == 8.0 and R['B + A.hair_b']['carries'] == 0.5
        assert R['B - hair_c']['value'] == 8.0 and R['A + B.hair_c']['value'] == 8.0 and R['B - hair_c']['carries'] == 0.5
        assert R['B - hair_b']['kind'] == 'drop' and R['B - hair_b']['delta'] == -6.0 and R['B - hair_b']['carries'] is None
        assert R['A - hair_a']['value'] == 2.0
        assert res['moves']['hair_b']['max_move_L'] == 1.0 and res['moves']['hair_c'] == {'only': 'B'}
        assert os.path.exists(os.path.join(d, 'out', 'swap.md'))


def test_moves_rotation():
    b1, b2 = small(), small()
    B1 = b1.build()
    th = np.radians(10)
    R = np.array([[np.cos(th), -np.sin(th), 0], [np.sin(th), np.cos(th), 0], [0, 0, 1]])
    V = B1.obj('hair_a').V('eval')
    b2.arrays['o/hair_a/eval/V'] = (V - V.mean(0)) @ R.T + V.mean(0)
    m = sweep.moves(B1, b2.build(), ('hair',))
    assert abs(m['hair_a']['rot_deg'] - 10) < 1e-3 and m['hair_a']['nonrigid_L'] < 1e-6 and m['hair_b']['max_move_L'] == 0


H5 = os.path.expanduser('~/animation-pipeline-hair4/charkit/out')


def test_reproduces_hair5_terminator_swap():
    """the acceptance (docs/workstreams/sweep.md): tools/hair5/term.py's attribution of art_terminator_hair 1.804 ->
    2.575 (h5_base -> hair5_b) to the fitted ahoge: B without its ahoge 1.900, A with B's ahoge 3.262, B with A's
    1.899, per view exactly. Skipped where those builds aren't (the gate's clones)."""
    A, B = os.path.join(H5, 'h5_base'), os.path.join(H5, 'hair5_b')
    if not (os.path.isdir(os.path.join(A, 'bundle')) and os.path.isdir(os.path.join(B, 'bundle'))):
        print('skip: the hair round 5 builds are not on this machine')
        return
    with tempfile.TemporaryDirectory() as d:
        res = sweep.swap(A, B, 'art_terminator_hair', objects=['hair_ahoge'], drop=True, out=d, log=lambda *a: None)
    R = {r['name']: r for r in res['rows']}
    assert (R['A']['value'], R['B']['value']) == (1.804, 2.575)
    assert R['B - hair_ahoge']['value'] == 1.9 and R['A + B.hair_ahoge']['value'] == 3.262
    assert R['B + A.hair_ahoge']['value'] == 1.899
    assert R['A + B.hair_ahoge']['ratio'] == {'front': 1.806, 'three_quarter': 1.637, 'profile': 0.876, 'back': 3.262}
    assert R['B - hair_ahoge']['ratio'] == {'front': 1.9, 'three_quarter': 1.559, 'profile': 0.965, 'back': 0.964}


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
