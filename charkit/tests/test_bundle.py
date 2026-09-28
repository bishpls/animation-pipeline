"""The geometry bundle and the venv QA's machinery on synthetic inputs (venv: run this file): a bundle made in memory and
read back from disk, what a measurement reads of it, the part cache keyed on those reads, the numba z-buffer's thin
lines and back-face culling, and the toon draw's tones."""
import os, sys, tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import bundle, faceqa, qa3d
from charkit.geom import raster


def small_bundle():
    """two quads of 'skin' (slots skin, line) with a key, an iris plate with UVs."""
    b = bundle.Builder({'name': 't', 'iris': {}}, {'L': 1.0, 'centre': [0, 0, 0], 'eyes': [], 'mouth': {}}, {'ppl': 100})
    b.material('skin', lit=(1.0, 0.9, 0.86))
    b.material('line', lit=(0.4, 0.2, 0.2), cull=True)
    b.material('iris', lit=(1, 1, 1), image='iris', kind='plate')
    b.image('iris', np.dstack([np.linspace(0, 1, 16)[None, :].repeat(16, 0)] * 3 + [np.ones((16, 16))]))
    V = np.array([[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1], [2, 0, 0], [2, 0, 1]], float)
    D = np.zeros((6, 3)); D[2, 2] = 0.1
    b.add('skin', 'skin', {'eval': dict(V=V, faces=[(0, 1, 2, 3), (1, 4, 5, 2)], pmat=[0, 0]),
                           'base': dict(V=V, faces=[(0, 1, 2, 3), (1, 4, 5, 2)], keys={'eye_blink': D})},
          materials=['skin', 'line'], outline=dict(slot=1))
    b.add('iris_L', 'eye', {'eval': dict(V=V[:4] + [0, -0.1, 0], faces=[(0, 1, 2, 3)], uv=V[:4, [0, 2]])},
          part='iris', side='L', materials=['iris'])
    return b


def test_builder_round_trip():
    b = small_bundle()
    B = b.build()
    sk = B.skin()
    T, poly, Tl = sk.tris('eval')
    loopv, starts, counts = sk.polys('eval')
    assert np.array_equal(T, faceqa.triangles(loopv, starts, counts)[0]) and len(T) == 4
    idx, d = sk.keys('base')['eye_blink']
    assert list(idx) == [2] and abs(d[0, 2] - 0.1) < 1e-7
    ir = B.part('iris', 'L')
    assert np.allclose(ir.puv('eval'), [[0.5, 0.5]])
    assert np.allclose(ir.corners('eval', 'luv')[0], [[0, 0], [1, 0], [1, 1]])
    # an image comes back top-down as bytes / 255, as Blender reads a byte image
    img = B.image('iris')
    assert img.shape == (16, 16, 4) and img[0, -1, 0] == 1.0 and img[0, 0, 0] == 0.0
    with tempfile.TemporaryDirectory() as d_:
        bundle.write(d_, b.meta, b.arrays)
        L = bundle.load(d_)
        assert np.array_equal(L.skin().tris('eval')[0], T)
        assert L.meta('hashes')['o/skin/eval/V'] == bundle.array_hash(B.array('o/skin/eval/V'))
        assert L.meta('content') == bundle.load(d_).meta('content')
    # moved: the geometry and the head's centre, not the key offsets
    M = B.moved([0.5, 0, 0])
    assert np.allclose(M.skin().V('eval')[0], [0.5, 0, 0]) and M.assembly['centre'][0] == 0.5
    assert np.allclose(M.skin().keys('base')['eye_blink'][1], d)


def test_reads_are_recorded():
    B = small_bundle().build()
    with B.recording() as r:
        B.skin().V('eval')
        B.spec.get('iris')
        B.materials.get('skin')
    assert 'o/skin/eval/V' in r.arrays and ('spec', 'iris') in r.meta and ('materials', 'skin') in r.meta
    assert ('objects',) in r.meta and ('spec', 'name') not in r.meta
    assert B.hash_of(('spec', 'iris')) == bundle.meta_hash({})


def test_memo_replays_its_reads():
    B = small_bundle().build()
    f = lambda: B.skin().V('eval').sum()
    with B.recording() as r1:
        a = B.memo('k', f)
    with B.recording() as r2:
        b = B.memo('k', lambda: 1 / 0)                  # not made again
    assert a == b and 'o/skin/eval/V' in r1.arrays and 'o/skin/eval/V' in r2.arrays


def test_part_cache_keys_on_what_it_read():
    from charkit import cache
    ran = []

    def part(B, design, out):
        ran.append(1)
        return None, {'x': {'value': float(B.skin().V('eval')[:, 0].sum()), 'status': 'INFO'}}
    old = os.environ.get('CHARKIT_CACHE_DIR')
    with tempfile.TemporaryDirectory() as d_:
        os.environ['CHARKIT_CACHE_DIR'] = d_
        try:
            b = small_bundle()
            B = b.build()
            a = cache.qa_part('t', part, B, None, None)
            assert cache.qa_part('t', part, b.build(), None, None) == a and len(ran) == 1      # restored
            b.arrays['o/iris_L/eval/V'] = b.arrays['o/iris_L/eval/V'] + 1                       # not read: still restored
            cache.qa_part('t', part, b.build(), None, None)
            assert len(ran) == 1
            b.arrays['o/skin/eval/V'] = b.arrays['o/skin/eval/V'] + 1                           # read: runs again
            c = cache.qa_part('t', part, b.build(), None, None)
            assert len(ran) == 2 and c[1]['x']['value'] == a[1]['x']['value'] + 6
        finally:
            if old is None:
                os.environ.pop('CHARKIT_CACHE_DIR', None)
            else:
                os.environ['CHARKIT_CACHE_DIR'] = old


def test_thin_lines_and_culling():
    # a sliver 0.3 px wide across a 20 px window: at pixel centres it breaks up, drawn thin it stays a line
    V = np.array([[-1.0, 0, 0.013], [1.0, 0, 0.013], [1.0, 0, 0.016], [-1.0, 0, 0.016]])
    T = np.array([[0, 1, 2], [0, 2, 3]])
    win = dict(x=1.0, top=1.0, bottom=-1.0)
    _, lab = raster.window_zbuffer([(V, T, 4)], 0, (0, 0), 1.0, 0.1, win)
    _, lab_t = raster.window_zbuffer([(V, T, 4)], 0, (0, 0), 1.0, 0.1, win, thin=(4,))
    assert (lab == 4).sum() < 5 and (lab_t == 4).sum() >= 20
    # a triangle facing away (clockwise from the front camera) drops out when culled, stays when not
    Q = np.array([[-0.5, 0, -0.5], [0.5, 0, -0.5], [0, 0, 0.5]])
    back = np.array([[0, 2, 1]])
    assert (raster.window_zbuffer([(Q, back, 1, False)], 0, (0, 0), 1.0, 0.1, win)[1] == 1).any()
    assert not (raster.window_zbuffer([(Q, back, 1, True)], 0, (0, 0), 1.0, 0.1, win)[1] == 1).any()
    assert (raster.window_zbuffer([(Q, back[:, ::-1], 1, True)], 0, (0, 0), 1.0, 0.1, win)[1] == 1).any()


def test_toon_draw_tones():
    # a quad facing the camera, toon3-shaded: lit where the light is in front, deep where it's behind; straight alpha
    b = bundle.Builder({}, {'L': 1.0, 'centre': [0, 0, 0], 'eyes': [], 'mouth': {}})
    for name, ld in (('front', [0, -1, 0]), ('back', [0, 1, 0])):
        b.material(name, kind='toon3', shading=dict(ldir=ld, lit=[1.0, 0.5, 0.25], shade=[0.5, 0.25, 0.1], deep=[0.2, 0.1, 0.05],
                                                    lit_at=[0.485, 0.515], deep_at=[0.255, 0.285], rim=[1, 1, 1], rim_amt=0.0,
                                                    blend=0.3, rim_from=[0.64, 0.68], strength=1.0))
    V = np.array([[-0.5, 0, -0.5], [0.5, 0, -0.5], [0.5, 0, 0.5], [-0.5, 0, 0.5]])
    b.add('front', 'hair', {'eval': dict(V=V - [0.6, 0, 0], faces=[(0, 1, 2, 3)])}, materials=['front'])
    b.add('back', 'hair', {'eval': dict(V=V + [0.6, 0, 0], faces=[(0, 1, 2, 3)])}, materials=['back'])
    B = b.build()
    fr = qa3d.Frame(-1.0, 1.0, res=(40, 40), ss=3)
    surfs = [x for o in B.objects() for x in qa3d.surfaces(B, o)]
    px = qa3d.draw(B, surfs, 0, fr, ss=3)
    r, c1, c2 = 20, 20 - 11, 20 + 11
    assert np.allclose(px[r, c1, :3], np.round(qa3d._srgb([1.0, 0.5, 0.25]) * 255) / 255, atol=1 / 255)
    assert np.allclose(px[r, c2, :3], np.round(qa3d._srgb([0.2, 0.1, 0.05]) * 255) / 255, atol=1 / 255)
    assert px[r, c1, 3] == 1.0 and px[0, 0, 3] == 0.0


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
