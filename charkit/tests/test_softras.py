"""charkit.render.softras: the soft silhouette's gradients against finite differences, its convergence to the hard
silhouette (its own, the QA's raster, and charkit.render's at the same camera) as the softness goes to 0, the box
filter it approximates at s = 1 ('linear'), and its time per view at the QA's scale (docs/workstreams/softras.md).

    python charkit/tests/test_softras.py
"""
import math, os, sys, tempfile, time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from charkit.render import softras, views                   # noqa: E402

WIN = dict(x=0.8, top=0.8, bottom=-0.8)                      # a 1.6 x 1.6 window


def sheet(n=24, m=30, twist=0.6, bulge=0.25, seed=0):
    """an open, curved, twisted panel (a flap-like template): a grid in x-z bent round z and twisted, Blender's frame."""
    u, v = np.meshgrid(np.linspace(-0.3, 0.3, n), np.linspace(-0.5, 0.5, m), indexing='xy')
    a = twist * v
    x = u * np.cos(a)
    y = u * np.sin(a) + bulge * (u ** 2 - 0.09) + 0.05 * np.sin(3 * v)
    z = v + 0.05 * u
    rng = np.random.default_rng(seed)
    V = np.stack([x, y, z], -1).reshape(-1, 3) + rng.normal(0, 0.002, (n * m, 3))
    F = []
    for j in range(m - 1):
        for i in range(n - 1):
            F.append((j * n + i, j * n + i + 1, (j + 1) * n + i + 1, (j + 1) * n + i))
    return V, F


def blob(n=64, r=0.1):
    """a closed, non-convex blob round the origin (a sphere with lobes), glTF frame, counter-clockwise from outside."""
    th, ph = np.meshgrid(np.linspace(0, math.pi, n // 2 + 1), np.linspace(0, 2 * math.pi, n + 1), indexing='ij')
    N = np.stack([np.sin(th) * np.cos(ph), np.cos(th), np.sin(th) * np.sin(ph)], -1).reshape(-1, 3)
    rad = r * (1 + 0.25 * np.sin(3 * ph) * np.sin(th) ** 2 + 0.15 * np.cos(2 * th)).reshape(-1)
    P = N * rad[:, None]
    rows, cols = th.shape
    F = []
    for a in range(rows - 1):
        for b in range(cols - 1):
            i0, i1, i2, i3 = a * cols + b, a * cols + b + 1, (a + 1) * cols + b, (a + 1) * cols + b + 1
            F += [[i0, i2, i1], [i1, i2, i3]]
    F = np.array(F, np.int64)
    fn = np.cross(P[F[:, 1]] - P[F[:, 0]], P[F[:, 2]] - P[F[:, 0]])
    ok = np.linalg.norm(fn, axis=1) > 1e-14
    F = F[ok]
    if (np.einsum('ij,ij->i', fn[ok], P[F].mean(1)) < 0).mean() > 0.5:
        F = F[:, [0, 2, 1]]
    return P, F


def ellipse(shape, cx, cy, rx, ry):
    H, W = shape
    yy, xx = np.mgrid[:H, :W] + 0.5
    return ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1


def loss_and_grad(V, F, view, mask, s, occ=None):
    S = softras.silhouette(V, F, view, s=s, occ=occ)
    iou, g = S.iou(mask)
    return 1 - iou, S.backward(-g), S


def fd_check(V, F, view, mask, s, occ=None, n=40, h=1e-6, seed=1):
    """the analytic gradient against central differences on the n coordinates it is largest on and n random others
    -> (cosine over them, median relative error, 95th percentile)."""
    L0, G, S = loss_and_grad(V, F, view, mask, s, occ)
    rng = np.random.default_rng(seed)
    big = np.argsort(-np.abs(G).ravel())[:n]
    idx = np.unique(np.r_[big, rng.choice(G.size, n, replace=False)])
    a, f = [], []
    for k in idx:
        i, c = divmod(int(k), 3)
        Vp, Vm = V.copy(), V.copy()
        Vp[i, c] += h; Vm[i, c] -= h
        lp = 1 - softras.silhouette(Vp, F, view, s=s, occ=occ).iou(mask)[0]
        lm = 1 - softras.silhouette(Vm, F, view, s=s, occ=occ).iou(mask)[0]
        a.append(G[i, c]); f.append((lp - lm) / (2 * h))
    a, f = np.array(a), np.array(f)
    cos = float(a @ f / max(1e-30, np.linalg.norm(a) * np.linalg.norm(f)))
    sig = np.abs(a) > 1e-3 * np.abs(a).max()
    rel = np.abs(a - f)[sig] / np.maximum(np.abs(a), np.abs(f))[sig]
    return cos, float(np.median(rel)), float(np.percentile(rel, 95)), int(sig.sum())


def test_gradient_sheet():
    """the twisted panel in the QA's window at 30 deg against an ellipse, at s 1 and 0.5 px: the gradient matches
    central differences (h = 1e-4 px)."""
    V, F = sheet()
    view = softras.SheetView(30.0, (0.0, 0.0), 1.0, 0.01, WIN)
    mask = ellipse(view.shape, 85, 78, 30, 55)
    for s in (1.0, 0.5):
        cos, med, p95, k = fd_check(V, F, view, mask, s)
        print('  sheet s %.1f: cosine %.6f, relative error median %.2e, p95 %.2e (%d coordinates)' % (s, cos, med, p95, k))
        assert cos > 0.9999 and med < 1e-4 and p95 < 1e-2, (s, cos, med, p95)


def test_gradient_occluded():
    """the same with an occluder in front of the panel's left half (a depth plane, as the QA's frozen scene holds the
    skirt and legs): the occlusion boundary stays hard and the gradient still matches."""
    V, F = sheet()
    view = softras.SheetView(30.0, (0.0, 0.0), 1.0, 0.01, WIN)
    H, W = view.shape
    occ = np.full((H, W), np.inf)
    occ[:, :70] = -1.0                                          # nearer than everything there
    mask = ellipse(view.shape, 85, 78, 30, 55)
    cos, med, p95, k = fd_check(V, F, view, mask, 0.5, occ=occ)
    print('  occluded s 0.5: cosine %.6f, median %.2e, p95 %.2e (%d)' % (cos, med, p95, k))
    assert cos > 0.9999 and med < 1e-4 and p95 < 1e-2


def test_gradient_perspective():
    """the blob through charkit.render's perspective camera (views.camera, 85 mm): the pullback through the
    projection's Jacobian."""
    P, F = blob()
    v = views.BoardView('blob', (0.0, 0.0, 0.0), 20, 0.6, 0.05, (160, 160), lens=85)
    view = softras.CameraView(views.camera(v))
    mask = ellipse(view.shape, 84, 76, 38, 30)
    cos, med, p95, k = fd_check(P, F, view, mask, 0.5, h=1e-7)
    print('  perspective s 0.5: cosine %.6f, median %.2e, p95 %.2e (%d)' % (cos, med, p95, k))
    assert cos > 0.9999 and med < 1e-4 and p95 < 1e-2


def test_converges_to_hard():
    """as s -> 0 the soft coverage is the hard one (the QA's raster at pixel centres): the summed difference shrinks
    with s, and past the contour band nothing differs at all."""
    V, F = sheet()
    view = softras.SheetView(30.0, (0.0, 0.0), 1.0, 0.01, WIN)
    prev = None
    for s in (2.0, 1.0, 0.5, 0.1, 0.01, 0.001):
        S = softras.silhouette(V, F, view, s=s)
        diff = float(np.abs(S.cov - S.hard).sum())
        assert np.array_equal(S.cov[S.eid < 0], S.hard[S.eid < 0].astype(float))
        hard_iou = float(((S.cov >= 0.5) & S.hard).sum() / ((S.cov >= 0.5) | S.hard).sum())
        print('  s %6.3f: sum |F - C| %8.3f px over %d contour points; IoU(F >= 0.5, C) %.6f' %
              (s, diff, len(S.contour), hard_iou))
        if prev is not None:
            assert diff <= prev + 1e-9
        prev = diff
    assert prev < 0.01 * len(S.contour)


def test_box_filter():
    """'linear' at s = 1 px is the box filter's area coverage across a straight edge: a square from x 10.3 to 50.3 px
    covers 0.7 of column 10 and 0.3 of column 50."""
    V = np.array([[-0.8 + 0.103, 0, 0.8 - 0.103], [-0.8 + 0.503, 0, 0.8 - 0.103], [-0.8 + 0.503, 0, 0.8 - 0.503],
                  [-0.8 + 0.103, 0, 0.8 - 0.503]])
    view = softras.SheetView(0.0, (0.0, 0.0), 1.0, 0.01, WIN)
    S = softras.silhouette(V, [(0, 1, 2, 3)], view, s=1.0, kernel='linear')
    c = S.full(S.cov)
    assert abs(c[30, 10] - 0.7) < 1e-9 and abs(c[30, 50] - 0.3) < 1e-9 and c[30, 30] == 1.0, (c[30, 9:12], c[30, 49:52])
    assert abs(c[10, 30] - 0.7) < 1e-9 and abs(c[50, 30] - 0.3) < 1e-9


def blob_glb(path, P, F, w=0.002):
    """the blob written as the export writes a mesh (charkit/gltf.py's Writer, the tests' sphere_glb): POSITION the
    surface moved inward by the build width along its normal, so the original surface (the outline's hull, the
    silhouette) is P."""
    from charkit import shade
    from charkit.gltf import EXT, Writer
    from charkit.tests.test_render import LOOK
    N = np.zeros_like(P)
    fn = np.cross(P[F[:, 1]] - P[F[:, 0]], P[F[:, 2]] - P[F[:, 0]])
    for k in range(3):
        np.add.at(N, F[:, k], fn)
    N /= np.maximum(1e-12, np.linalg.norm(N, axis=1))[:, None]
    Wr = Writer()
    look = {'kind': 'toon3', 'role': 'ball', 'doubleSided': True, 'alpha': 'opaque', 'lit': [0.9, 0.5, 0.3],
            'shade': [0.4, 0.2, 0.1], 'deep': [0.2, 0.1, 0.05], 'threshold': 0.5, 'deepThreshold': 0.27, 'softness': 0.015}
    Wr.js['materials'].append({'name': 'ball', 'extensions': {EXT: look}})
    attrs = {'POSITION': Wr.accessor((P - N * shade.line_inward(w, None)).astype(np.float32), 'VEC3', minmax=True),
             'NORMAL': Wr.accessor(N.astype(np.float32), 'VEC3')}
    mx = {'object': 'ball', 'outline': {'width': w, 'color': [0.0, 0.0, 0.0], 'region': 'skin'}}
    Wr.js['meshes'].append({'name': 'ball', 'primitives': [{'attributes': attrs, 'indices': Wr.accessor(
        F.astype(np.uint32).ravel(), 'SCALAR'), 'material': 0}], 'extensions': {EXT: mx}})
    Wr.js['nodes'].append({'name': 'ball', 'mesh': 0})
    Wr.js['scenes'][0]['nodes'].append(0)
    Wr.js['extensions'][EXT] = {'version': 1, 'light': {'direction': [1.0, 0.0, 0.0]}, 'lines': LOOK['lines'],
                                'head': {'centre': [0, 0, 0], 'L': 0.25}}
    Wr.js['extensionsUsed'].append(EXT)
    Wr.glb(path)


def test_against_render():
    """the hard silhouette, and the soft one at s -> 0 thresholded at 0.5, against charkit.render's (gpu.ids at ss 1:
    the part or its outline hull at each pixel centre, the hull on the original surface) at the same camera, orthographic
    and perspective: IoU >= 0.999 (only rasteriser ties on the contour may differ)."""
    try:
        from charkit.render import gpu, model
        gpu.device()
    except Exception as e:                                                          # no wgpu, or no adapter
        print('  skipped (no wgpu adapter):', repr(e)[:200])
        return
    P, F = blob()
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 'blob.glb')
        blob_glb(p, P, F)
        M = model.load(p)
        R = gpu.Renderer(M, ss=1)
        co = M.prims[0].co().astype(float)
        idx = M.prims[0].index.reshape(-1, 3).astype(np.int64)
        for v in (views.BoardView('ortho', (0.0, 0.0, 0.0), 35, 1.0, 0.1, (200, 160), ortho=0.36),
                  views.BoardView('persp', (0.0, 0.0, 0.0), -50, 0.55, 0.08, (160, 200), lens=85)):
            part, _ = R.ids(v, ss=1)
            ref = part >= 0
            view = softras.CameraView(views.camera(v))
            for s in (0.5, 0.01):
                S = softras.silhouette(co, idx, view, s=s)
                hard, soft = S.full(S.hard), S.full(S.cov) >= 0.5
                i_h = (hard & ref).sum() / (hard | ref).sum()
                i_s = (soft & ref).sum() / (soft | ref).sum()
                print('  %s s %.2f: IoU against charkit.render: hard %.5f, soft >= 0.5 %.5f (%d px, %d differ)' %
                      (v.name, s, i_h, i_s, ref.sum(), (soft != ref).sum()))
                assert i_h >= 0.999
                if s <= 0.01:
                    assert i_s >= 0.999


def test_timing():
    """one view at the QA's scale (the full-body window at 212 px per L, 977 x 1594; a ~1000-vertex panel covering
    ~30k px, as the flap does): forward and backward, warm."""
    V, F = sheet(n=26, m=40)
    V = V * np.array([0.6, 0.6, 1.1]) + np.array([0.3, 0.0, -2.3])
    view = softras.SheetView(180.0, (0.0, 0.0), 1.0, 1 / 212.47, dict(x=2.3, top=1.3, bottom=-6.2))
    mask = ellipse(view.shape, 480, 1030, 70, 120)
    softras.silhouette(V, F, view, s=0.5)                                           # (numba's first call compiles)
    ts, tb = [], []
    for _ in range(5):
        t = time.perf_counter()
        S = softras.silhouette(V, F, view, s=0.5)
        ts.append(time.perf_counter() - t)
        _, g = S.iou(mask)
        t = time.perf_counter()
        S.backward(-g)
        tb.append(time.perf_counter() - t)
    print('  one view %dx%d, %d vertices, %d px covered: forward %.1f ms, backward %.1f ms (median of 5); stages %s' %
          (view.W, view.H, len(V), S.hard.sum(), 1e3 * np.median(ts), 1e3 * np.median(tb),
           {k: round(1e3 * x, 2) for k, x in S.seconds.items()}))
    assert np.median(ts) < 0.5


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
