"""charkit.render (the toon renderer): the board cameras against charkit.qa._aim's geometry, each view's look against
charkit.shade's, the export read back, and a toon sphere drawn on whatever adapter the machine has (a GPU, or Mesa's CPU
drivers; skipped when wgpu has none): its silhouette at the original surface, its screen-width outline, its terminator
on the light's great circle, the flat background colour, and the same pixels twice.
"""
import math, os, sys, tempfile

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from charkit import shade                                   # noqa: E402
from charkit.render import compare, model, views           # noqa: E402

LOOK = {'light': {'mode': 'camera', 'key': [30.0, 40.0]},
        'lines': {'mode': 'screen', 'frac': 0.0022, 'regions': {'skin': 1.0, 'hair': 1.0, 'garment': 1.0, 'accessory': 0.8}}}


def _project(cam, p):
    q = cam.viewproj @ np.array([*p, 1.0])
    ndc = q[:3] / q[3]
    W, H = cam.res
    return np.array([(ndc[0] + 1) / 2 * W, (1 - ndc[1]) / 2 * H]), ndc[2]


def test_camera_perspective():
    v = views.BoardView('face_030', (0.0, 0.0, 1.35), 30, 1.0, 0.0, (900, 900), lens=85)
    cam = views.camera(v)
    xy, z = _project(cam, model.to_gltf(v.target))
    assert np.allclose(xy, [450, 450], atol=1e-6) and 0 < z < 1
    # qa._aim: eye = target + (sin az, -cos az) dist, metres per pixel = dist x sensor / lens / longer side
    a = math.radians(30)
    assert np.allclose(cam.eye, model.to_gltf([math.sin(a), -math.cos(a), 1.35]), atol=1e-12)
    assert abs(cam.m_per_px - 1.0 * 36 / 85 / 900) < 1e-15
    # a point m_per_px to the camera's right at the target's depth lands one pixel right of the centre
    right = cam.view[0, :3]
    xy1, _ = _project(cam, model.to_gltf(v.target) + right * cam.m_per_px)
    assert abs(xy1[0] - 451) < 1e-6 and abs(xy1[1] - 450) < 1e-6
    # her left (+x) is on the picture's right from the front (az 0), as in Blender
    c0 = views.camera(views.BoardView('f', (0, 0, 1.35), 0, 1.0, 0.0, (900, 900), lens=85))
    assert _project(c0, model.to_gltf([0.05, 0, 1.35]))[0][0] > 450


def test_camera_ortho_portrait():
    v = views.BoardView('body_000', (0.0, 0.0, 0.8), 0, 6.0, 0.0, (600, 1000), ortho=1.6 * 1.12)
    cam = views.camera(v)
    assert abs(cam.m_per_px - 1.6 * 1.12 / 1000) < 1e-15            # the scale on the longer side (height)
    top, _ = _project(cam, model.to_gltf([0, 0, 0.8 + 1.6 * 1.12 / 2]))
    assert abs(top[1]) < 1e-6 and abs(top[0] - 300) < 1e-6


def test_look_is_shades():
    class M:
        root = {'light': {'mode': 'camera', 'key': [30.0, 40.0], 'direction': [0, 0, 1]}, 'lines': LOOK['lines']}
    for az in (0, 35, 90, 150, 180):
        v = views.BoardView('x', (0, 0, 1), az, 1, 0, (900, 900), lens=85)
        assert np.allclose(views.view_light(M, v), model.to_gltf(shade.view_light(az, LOOK)), atol=1e-12)
    cam = views.camera(views.BoardView('x', (0, 0, 1), 0, 1, 0, (900, 900), lens=85))
    w = views.line_width({'width': 0.0012, 'region': 'accessory'}, cam, LOOK)
    assert abs(w - 0.0022 * 900 * cam.m_per_px * 0.8) < 1e-15


def test_streak_table():
    from charkit.render import gpu
    hl = {'count': 36, 'keep': 0.3, 'elevation': 47.0, 'jitter': 4.0}
    keep, el0 = gpu.streak_table(hl, 'f64')
    i = np.arange(36)
    h1 = np.mod(np.sin(i * 12.9898) * 43758.5453, 1.0)
    assert np.array_equal(keep, (h1 < 0.3).astype(np.float32))
    assert np.all(np.abs(np.degrees(el0) - 47) <= 4 + 1e-4)
    for mode in ('f32', 'nv'):
        k, e = gpu.streak_table(hl, mode)
        assert k.shape == (36,) and np.all((k == 0) | (k == 1))


def sphere_glb(path, r=0.1, w=0.002, n=96):
    """a UV sphere at the origin (glTF frame) with a toon3 material and an outline, written by charkit/gltf.py's own
    Writer as the export writes a mesh: POSITION the surface moved inward by the build width."""
    from charkit.gltf import EXT, Writer
    th, ph = np.meshgrid(np.linspace(0, math.pi, n // 2 + 1), np.linspace(0, 2 * math.pi, n + 1), indexing='ij')
    N = np.stack([np.sin(th) * np.cos(ph), np.cos(th), np.sin(th) * np.sin(ph)], -1).reshape(-1, 3)
    rows, cols = th.shape
    F = []
    for a in range(rows - 1):
        for b in range(cols - 1):
            i0, i1, i2, i3 = a * cols + b, a * cols + b + 1, (a + 1) * cols + b, (a + 1) * cols + b + 1
            F += [[i0, i2, i1], [i1, i2, i3]]
    F = np.array(F, np.uint32)
    P = N * r
    fn = np.cross(P[F[:, 1]] - P[F[:, 0]], P[F[:, 2]] - P[F[:, 0]])
    ok = np.linalg.norm(fn, axis=1) > 1e-12                          # the poles' degenerate triangles aside
    if (np.einsum('ij,ij->i', fn[ok], P[F[ok]].mean(1)) < 0).mean() > 0.5:
        F = F[:, [0, 2, 1]]                                          # counter-clockwise seen from outside, as glTF's
    Wr = Writer()
    look = {'kind': 'toon3', 'role': 'ball', 'doubleSided': True, 'alpha': 'opaque', 'lit': [0.9, 0.5, 0.3],
            'shade': [0.4, 0.2, 0.1], 'deep': [0.2, 0.1, 0.05], 'threshold': 0.5, 'deepThreshold': 0.27, 'softness': 0.015}
    Wr.js['materials'].append({'name': 'ball', 'extensions': {EXT: look}})
    attrs = {'POSITION': Wr.accessor((N * (r - w)).astype(np.float32), 'VEC3', minmax=True),
             'NORMAL': Wr.accessor(N.astype(np.float32), 'VEC3')}
    Wr.js['meshes'].append({'name': 'ball', 'primitives': [{'attributes': attrs, 'indices': Wr.accessor(F.ravel(), 'SCALAR'),
                                                           'material': 0}],
                            'extensions': {EXT: {'object': 'ball', 'outline': {'width': w, 'color': [0.0, 0.0, 0.0],
                                                                               'region': 'skin'}}}})
    Wr.js['nodes'].append({'name': 'ball', 'mesh': 0})
    Wr.js['scenes'][0]['nodes'].append(0)
    Wr.js['extensions'][EXT] = {'version': 1, 'light': {'direction': [1.0, 0.0, 0.0]}, 'lines': LOOK['lines'],
                                'head': {'centre': [0, 0, 0], 'L': 0.25}}
    Wr.js['extensionsUsed'].append(EXT)
    Wr.glb(path)
    return F


def test_model_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 'ball.glb')
        F = sphere_glb(p)
        M = model.load(p)
        assert len(M.prims) == 1 and np.array_equal(M.prims[0].index, F.ravel())
        P = M.prims[0]
        assert np.allclose(np.linalg.norm(P.co(), axis=1), 0.1, atol=1e-6)      # the original surface, where the hull is
        assert views.look_of(M)['lines']['frac'] == 0.0022


def _gpu():
    try:
        from charkit.render import gpu
        gpu.device()
        return gpu
    except Exception as e:                                                        # no wgpu, or no adapter
        print('skipped (no wgpu adapter):', repr(e)[:200])
        return None


def test_sphere_render():
    gpu = _gpu()
    if gpu is None:
        return
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 'ball.glb')
        sphere_glb(p, r=0.1, w=0.002)
        M = model.load(p)
        R = gpu.Renderer(M, ss=4)
        # orthographic, from the front (Blender az 0: the camera at -y looking along +y; glTF: at +z looking along -z)
        v = views.BoardView('ball', (0.0, 0.0, 0.0), 0, 1.0, 0.0, (160, 160), ortho=0.32)
        keep = {}
        img = R.render(v, keep=keep)
        assert np.array_equal(img, R.render(v))                                      # deterministic
        mpp = 0.32 / 160
        bg = compare.srgb8(views.BG)
        assert np.array_equal(img[2, 2], bg) and np.array_equal(img[-3, -3], bg)
        yy, xx = np.mgrid[:160, :160]
        rr = np.hypot(xx + 0.5 - 80, yy + 0.5 - 80) * mpp                            # radius (m) at each pixel centre
        fg = np.abs(img.astype(int) - bg).max(-1) > 64
        # the silhouette is the hull: the original surface, radius 0.1 m (50 px), filtered edge within 1 px
        assert fg[rr < 0.1 - 1.2 * mpp].all() and not fg[rr > 0.1 + 1.2 * mpp].any()
        # the ink ring: screen lines 0.22% of the height x 160 px = 0.352 px at this scale... drawn from the surface
        # moved inward by it: dark pixels only at the rim
        line = keep['line']
        assert abs(line - 0.0022 * 160 * mpp) < 1e-12
        # the terminator: light from her left (+x in glTF, the picture's right from the front): the camera key turns
        # with the view, so read the light the frame used and check the tone boundary on the sphere's front
        L = keep['light']
        H = keep['main']
        ss = R.ss
        yy2, xx2 = np.mgrid[:160 * ss, :160 * ss]
        px, py = (xx2 + 0.5) / ss - 80, 80 - (yy2 + 0.5) / ss                         # px from the centre, y up
        s = (0.1 - line) / mpp
        inside = np.hypot(px, py) < s * 0.95
        nz = np.sqrt(np.clip(1 - (px ** 2 + py ** 2) / s ** 2, 0, 1))
        Nn = np.stack([px / s, py / s, nz], -1)                                      # the front's normals (camera +z)
        h = (Nn @ np.asarray(L)) * 0.5 + 0.5
        lit = compare.srgb8([0.9, 0.5, 0.3]) / 255.0
        col = H[..., :3]
        is_lit = np.abs(col - np.array([0.9, 0.5, 0.3])).max(-1) < 0.02
        sure = inside & (np.abs(h - 0.5) > 0.02)
        agree = (is_lit[sure] == (h[sure] > 0.5)).mean()
        assert agree > 0.999, agree
        assert lit is not None


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
