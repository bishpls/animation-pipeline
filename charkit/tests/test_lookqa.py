"""The look QA's machinery on synthetic inputs (venv: run this file): a view drawn once and lit many times is draw() each
time, bit for bit; the line widths cut to their box are the whole mask's; the design's widths measured group by group
are the whole sheet's."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import bundle, lookqa, qa3d


def toon_bundle():
    """a toon3 sphere-ish patch (a bent grid) and a flat 'line' quad behind it."""
    b = bundle.Builder({}, {'L': 1.0, 'centre': [0, 0, 0], 'eyes': [], 'mouth': {}})
    b.material('skin', kind='toon3', shading=dict(ldir=[0.3, -0.8, 0.5], lit=[1.0, 0.8, 0.7], shade=[0.7, 0.5, 0.45],
                                                  deep=[0.4, 0.3, 0.3], lit_at=[0.485, 0.515], deep_at=[0.255, 0.285],
                                                  rim=[1, 1, 1], rim_amt=0.3, blend=0.3, rim_from=[0.64, 0.68],
                                                  strength=1.0))
    b.material('line', lit=(0.1, 0.05, 0.05), cull=True)
    n = 9
    u = np.linspace(-0.8, 0.8, n)
    X, Z = np.meshgrid(u, u)
    Y = -np.sqrt(np.clip(1.2 - X ** 2 - Z ** 2, 0.05, None))
    V = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1)
    F = [(i * n + j, i * n + j + 1, (i + 1) * n + j + 1, (i + 1) * n + j) for i in range(n - 1) for j in range(n - 1)]
    b.add('ball', 'skin', {'eval': dict(V=V, faces=F)}, materials=['skin'])
    Q = np.array([[-1, 0.5, -1], [1, 0.5, -1], [1, 0.5, 1], [-1, 0.5, 1]], float)
    b.add('back', 'hair', {'eval': dict(V=Q, faces=[(0, 1, 2, 3)])}, materials=['line'])
    return b.build()


def test_view_lit_is_draw():
    B = toon_bundle()
    fr = qa3d.Frame(-1.2, 1.2, res=(48, 48), ss=3)
    surfs = [x for o in B.objects() for x in qa3d.surfaces(B, o)]
    for az in (0, 30):
        view = qa3d.draw_view(B, surfs, az, fr)
        for ld in (None, lookqa.key_light(az, -35, 35), lookqa.key_light(az, 70, 35)):
            a1, a2 = {}, {}
            p1 = qa3d.draw(B, surfs, az, fr, ss=3, ldir=ld, aux=a1)
            p2 = qa3d.draw_lit(B, view, ld, ss=3, aux=a2)
            assert np.array_equal(p1, p2)
            assert np.array_equal(a1['tone'], a2['tone'], equal_nan=True) and np.array_equal(a1['mesh'], a2['mesh'])
            a3 = {}                                             # the skin alone, no picture: the skin's tones the same
            assert qa3d.draw_lit(B, view, ld, ss=3, aux=a3, only=(0,), picture=False) is None
            m = a1['mesh'] == 0
            assert m.any() and np.array_equal(a1['tone'][m], a3['tone'][m], equal_nan=True)


def _widths_whole(mask, ss=1):
    from scipy import ndimage
    from skimage.morphology import skeletonize
    d = ndimage.distance_transform_edt(mask)
    sk = skeletonize(mask)
    return (2 * d[sk] - 1) / ss if ss > 1 else 2 * d[sk] - 1


def test_widths_cut_is_whole():
    rng = np.random.default_rng(3)
    m = np.zeros((60, 80), bool)
    yy, xx = np.mgrid[:60, :80]
    m |= np.abs(np.hypot(yy - 30, xx - 35) - 14) < 1.6              # a ring
    m[5:8, 50:78] = True                                             # a bar
    m[0:12, 2:5] = True                                              # a bar on the mask's edge
    m |= rng.random(m.shape) > 0.995                                 # dots
    assert np.array_equal(np.sort(lookqa.widths(m, 1)), np.sort(_widths_whole(m, 1)))
    assert np.array_equal(np.sort(lookqa.design_widths(m, 2)),
                          np.sort(_widths_whole(np.repeat(np.repeat(m, 2, 0), 2, 1), 2)))


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
