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


def test_cast_shadow_overhang():
    # a floor under a roof overhanging its front half: points under the roof are in its shadow for a light from above,
    # the points in front of it lit; a light from below (el < 0) shadows nothing
    from charkit import faceshade as fs
    xs, ys = np.meshgrid(np.linspace(-0.4, 0.4, 9), np.linspace(-0.4, 0.4, 9))
    P = np.stack([xs.ravel(), ys.ravel(), np.zeros(xs.size)], 1)
    N = np.tile([0.0, 0.0, 1.0], (len(P), 1))
    roof = (np.array([[-1, 0.0, 0.3], [1, 0.0, 0.3], [1, 1, 0.3], [-1, 1, 0.3]]), [(0, 1, 2, 3)])
    up = np.array([[0.0, 0.0, 1.0]]); down = np.array([[0.0, 0.2, -1.0]])
    c = fs.cast_shadow(P, N, [roof], np.concatenate([up, down]), 1.0, px=0.02)
    under = P[:, 1] > 0.05
    front = P[:, 1] < -0.05
    assert (c[under, 0] > 0.9).all() and (c[front, 0] < 0.1).all()
    assert (c[:, 1] == 0).all()
    # the baked azimuths: phi = atan2(x, -y), 0 in front of her; qa3d._cast interpolates between them
    D = fs.cast_dirs(16, 40.0)
    assert np.allclose(np.degrees(np.arctan2(D[4, 0], -D[4, 1])), 90.0) and np.allclose(D[:, 2], np.sin(np.radians(40)))
    smp = np.zeros((1, 16), np.float32); smp[0, 4] = 1.0
    P_ = dict(k=16, at=0.5, width=0.12)
    assert qa3d._cast(P_, smp, D[4])[0] == 1.0 and qa3d._cast(P_, smp, D[6])[0] == 0.0
    mid = D[4] + D[5]
    assert abs(qa3d._cast(P_, smp, mid / np.linalg.norm(mid))[0] - 0.5) < 1e-6      # half way: the step's middle


def test_smooth_vertex_keeps_constants():
    from charkit import faceshade as fs
    T = np.array([[0, 1, 2], [1, 3, 2]])
    X = np.ones((4, 3), np.float32)
    assert np.allclose(fs.smooth_vertex(X, T, np.ones(4, bool), 3), 1.0)
    X[0] = 0.0
    Y = fs.smooth_vertex(X, T, np.array([True, True, True, False]), 1)
    assert Y[3].tolist() == [1.0, 1.0, 1.0] and 0 < Y[0, 0] < 1


def test_chin_separates_the_v_from_the_band():
    """face_shadow_chin_edge on the jaw (lookqa.jaw_frame, chin_on_jaw) on shapes: a V under a V-shaped jaw against
    itself moved 1-2 px against its jaw grades PASS; a band of the same thickness low on the neck, and the neck shaded
    to its base (round 1's smear), FAIL. The jaw is found per column: the design's by its ink run, ours by the step back
    in depth."""
    from charkit import lookqa
    ppl, H, W = 200, 200, 200
    rows, cols = np.mgrid[:H, :W]
    jaw = (40 + 0.5 * (40 - np.abs(cols[0] + 0.5 - 100))).astype(int)      # the jaw: a V, its point at column 100
    neck_c = (cols >= 60) & (cols < 140)
    skin = neck_c & (rows < 170)
    under = rows >= jaw[None, :]
    line = neck_c & (rows >= jaw[None, :] - 2) & (rows < jaw[None, :])        # the drawn jaw: 2 px of ink over it
    Jd = lookqa.jaw_drawn(skin & ~line, line, 45, 100, ppl)
    assert set(Jd.values()) <= set(jaw.tolist()) and len(Jd) >= 60
    depth = np.where(under, 2.0, 1.9)                                          # ours: the neck 0.1 behind the jaw
    Jo = lookqa.jaw_depth(skin, depth, 45, 100, ppl, 1.0)
    assert all(Jo[c] == jaw[c] for c in Jo) and len(Jo) >= 60
    V = skin & under & (rows < jaw[None, :] + 26)                            # the V: 0.13 L under the jaw
    grade = lambda c: lookqa._grade_chin(c['edge'], lookqa.CHIN_EDGE, False)
    gd = lookqa.jaw_frame(V, skin, Jd, ppl)
    c = lookqa.chin_on_jaw(gd, gd, ppl)
    assert c['iou'] == 1.0 and c['edge'] == 0.0
    for sh in ((1, 0), (2, 0), (0, 2), (-2, 0), (0, -2)):
        c = lookqa.chin_on_jaw(lookqa.jaw_frame(np.roll(V, sh, (0, 1)) & skin, skin, Jd, ppl), gd, ppl)
        assert grade(c) == 'PASS' and c['iou'] >= 0.8, (sh, c)
    band = skin & (rows >= 110) & (rows < 136)                               # as thick, low on the neck
    assert grade(lookqa.chin_on_jaw(lookqa.jaw_frame(band, skin, Jo, ppl), gd, ppl)) == 'FAIL'
    smear = skin & under                                                     # the neck shaded to its base
    assert grade(lookqa.chin_on_jaw(lookqa.jaw_frame(smear, skin, Jo, ppl), gd, ppl)) == 'FAIL'


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
