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


# lookup3 of the float32 bits of 0..3 as EEVEE's White Noise 1D computes them (Blender 5.2.2, Metal and the T4: read
# back bit for bit by charkit/boards/lookprobe.py --hash): Value's and Color green's u32s
LOOKUP3_VALUE = [0x9519dc65, 0x25faf412, 0xe287f2c0, 0xcb321163]
LOOKUP3_GREEN = [0x264988ab, 0x9f7812d3, 0x92dd9b5e, 0xa0afc6ce]


def test_streak_hash():
    """charkit.shade.streak_hash: Jenkins' lookup3 on the column index's float bits (Blender's White Noise), pinned to
    the node's own values; the per-column table (kept, elevation) the streaks use."""
    b = np.arange(4, dtype=np.float32).view(np.uint32)
    assert [int(x) for x in shade.hash_uint(b)] == LOOKUP3_VALUE
    assert [int(x) for x in shade.hash_uint2(b, np.float32(1.0).view(np.uint32))] == LOOKUP3_GREEN
    h1, h2 = shade.streak_hash(4)
    assert np.array_equal(h1, (np.array(LOOKUP3_VALUE, np.float64).astype(np.float32) / np.float32(2 ** 32)))
    hl = {'count': 36, 'keep': 0.3, 'elevation': 47.0, 'jitter': 4.0}
    keep, el0 = shade.streak_columns(hl)
    assert keep.shape == (36,) and set(np.unique(keep)) <= {0.0, 1.0} and 6 <= keep.sum() <= 16
    assert np.all(np.abs(np.degrees(el0) - 47) <= 4 + 1e-4)


def test_line_cap():
    """Michael's call I: a thin shell's outline moves its surface inward by at most its cap, the rest outward; the
    SOLIDIFY's offset says so (surface w (1 + o) / 2 in, hull w (1 - o) / 2 out)."""
    assert shade.line_inward(0.0036, 0.001) == 0.001 and shade.line_inward(0.0009, 0.001) == 0.0009
    assert shade.line_inward(0.0036, None) == 0.0036
    for w, cap in ((0.0036, 0.001), (0.0009, 0.001), (0.0012, 0.00075), (0.002, None)):
        o = shade.line_offset(w, cap)
        assert abs(w * (1 + o) / 2 - shade.line_inward(w, cap)) < 1e-12
        assert abs(w * (1 - o) / 2 - (w - shade.line_inward(w, cap))) < 1e-12
    assert shade.line_offset(0.0012, None) == 1.0


def sphere_glb(path, r=0.1, w=0.002, n=96, cap=None, streaks=None, cast=None, bare=None):
    """a UV sphere at the origin (glTF frame) with a toon3 material and an outline, written by charkit/gltf.py's own
    Writer as the export writes a mesh: POSITION the surface moved inward by the build width (at most `cap`, a thin
    shell's maxInward); `streaks`: the material's highlight (charkit.shade.hair_toon's); `cast`: (the material's cast
    {k, at, width, half}, fn(unit normals (n, 3), glTF) -> (n, k) the baked values: _CK_CAST0..3); `bare`: a radius for a
    second sphere written as the object's 'bare' variant (a mesh without a node, as gltf.export look_only writes the
    skin's)."""
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
    if streaks:
        look['highlight'] = dict(streaks)
    if cast:
        look['cast'] = dict(cast[0], attributes=['_CK_CAST%d' % i for i in range(4)])
    Wr.js['materials'].append({'name': 'ball', 'extensions': {EXT: look}})
    for name, rad, variant in [('ball', r, None)] + ([('ball.bare', bare, 'bare')] if bare else []):
        attrs = {'POSITION': Wr.accessor((N * (rad - shade.line_inward(w, cap))).astype(np.float32), 'VEC3', minmax=True),
                 'NORMAL': Wr.accessor(N.astype(np.float32), 'VEC3')}
        if cast:
            c = np.zeros((len(N), 16), np.float32)
            c[:, :cast[0]['k']] = cast[1](N)
            for i in range(4):
                attrs['_CK_CAST%d' % i] = Wr.accessor(np.ascontiguousarray(c[:, 4 * i:4 * i + 4]), 'VEC4')
        mx = {'object': 'ball', 'outline': dict({'width': w, 'color': [0.0, 0.0, 0.0], 'region': 'skin'},
                                                **({'maxInward': cap} if cap else {}))}
        if variant:
            mx['variant'] = variant
        Wr.js['meshes'].append({'name': name, 'primitives': [{'attributes': attrs, 'indices': Wr.accessor(F.ravel(), 'SCALAR'),
                                                             'material': 0}], 'extensions': {EXT: mx}})
        if not variant:
            Wr.js['nodes'].append({'name': name, 'mesh': len(Wr.js['meshes']) - 1})
            Wr.js['scenes'][0]['nodes'].append(len(Wr.js['nodes']) - 1)
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
        sphere_glb(p, w=0.002, cap=0.0005)                                        # a thin shell: moved in by its cap
        P = model.load(p).prims[0]
        assert np.allclose(np.linalg.norm(P.position, axis=1), 0.0995, atol=1e-6)
        assert np.allclose(np.linalg.norm(P.co(), axis=1), 0.1, atol=1e-6) and P.inward(0.0036) == 0.0005


def test_quad_normals():
    """normals.Group: the export's triangles paired back into quads, each vertex's normal the corner-angle-weighted sum
    of its faces' (Newell's for a quad), as Blender computes them; the surface moved inward by w before."""
    from charkit.render import normals

    class P:                                                          # a Prim's fields Group reads
        def __init__(self, pos, idx, n):
            self.position, self.index, self.normal = pos, idx, n
            self.outline, self.hull_normal, self.outline_w = {'width': 0.0}, None, None
            self.look = {'kind': 'toon3'}

        def co(self):
            return self.position

        def hull_dir(self):
            return self.normal

        def width_factor(self):
            return np.ones(len(self.position), np.float32)
    # a twisted quad (0, 1, 2, 3) split on its diagonal, and a lone triangle after it
    V = np.array([[0, 0, 0], [1, 0, 0.3], [1, 1, 0], [0, 1, 0.3], [2, 0, 0], [2, 1, 0]], np.float32)
    T = np.array([[0, 1, 2], [0, 2, 3], [1, 4, 5]], np.uint32)
    G = normals.Group([P(V, T.ravel(), np.tile([0, 0, 1.0], (6, 1)).astype(np.float32))])
    tris, quads = G.polys
    assert len(quads) == 1 and len(tris) == 1 and sorted(quads[0].tolist()) == [0, 1, 2, 3]
    n = G.normals(0.0)[0]
    q = V[quads[0]].astype(float)
    newell = sum(np.cross(q[j], q[(j + 1) % 4]) for j in range(4))
    newell /= np.linalg.norm(newell)
    assert np.allclose(n[3], newell, atol=1e-6) and np.allclose(n[0], n[3], atol=1e-6)   # vertices only in the quad
    # moved inward by w along the hull direction: a flat plane's normals don't change
    assert np.allclose(G.normals(0.01)[0][[0, 2, 3]], n[[0, 2, 3]], atol=1e-6)


def _hash_wgsl():
    """toon.wgsl's streak hash functions (between its 'the streaks' hash' and 'the look' sections)."""
    src = open(os.path.join(ROOT, 'charkit', 'render', 'toon.wgsl')).read()
    a = src.index("// ------------------------------------------------------------------------------------------------ the streaks' hash")
    b = src.index('// ------------------------------------------------------------------------------------------------ the look')
    return src[a:b]


def test_streak_hash_gpu():
    """toon.wgsl's lookup3 on this machine's adapter, bit for bit against charkit.shade's (= Blender's White Noise):
    columns 0..255, both hashes, as u32."""
    gpu = _gpu()
    if gpu is None:
        return
    import wgpu
    dev, _ = gpu.device()
    n = 256
    code = _hash_wgsl() + """
@group(0) @binding(0) var<storage, read_write> out: array<u32>;
@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
  if (id.x >= %du) { return; }
  let bits = bitcast<u32>(f32(id.x));
  out[2u * id.x] = hash_uint(bits);
  out[2u * id.x + 1u] = hash_uint2(bits, bitcast<u32>(1.0));
}""" % n
    sm = dev.create_shader_module(code=code)
    buf = dev.create_buffer(size=8 * n, usage=wgpu.BufferUsage.STORAGE | wgpu.BufferUsage.COPY_SRC)
    pipe = dev.create_compute_pipeline(layout='auto', compute={'module': sm, 'entry_point': 'main'})
    bg = dev.create_bind_group(layout=pipe.get_bind_group_layout(0),
                               entries=[{'binding': 0, 'resource': {'buffer': buf, 'offset': 0, 'size': 8 * n}}])
    enc = dev.create_command_encoder()
    cp = enc.begin_compute_pass(); cp.set_pipeline(pipe); cp.set_bind_group(0, bg); cp.dispatch_workgroups(n // 64); cp.end()
    dev.queue.submit([enc.finish()])
    got = np.frombuffer(dev.queue.read_buffer(buf), np.uint32).reshape(n, 2)
    b = np.arange(n, dtype=np.float32).view(np.uint32)
    assert np.array_equal(got[:, 0], shade.hash_uint(b))
    assert np.array_equal(got[:, 1], shade.hash_uint2(b, np.float32(1.0).view(np.uint32)))


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
        # screen lines: 0.22% of the picture's height at this view's scale (the surface moved inward by it)
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
        col = H[..., :3]
        is_lit = np.abs(col - np.array([0.9, 0.5, 0.3])).max(-1) < 0.02
        sure = inside & (np.abs(h - 0.5) > 0.02)
        agree = (is_lit[sure] == (h[sure] > 0.5)).mean()
        assert agree > 0.999, agree


def test_sphere_thin_shell():
    """a thin shell's outline (maxInward under the view's width): the surface moves in by the cap and the hull goes
    the rest of the width out, so the silhouette grows by width - cap and the line keeps its width."""
    gpu = _gpu()
    if gpu is None:
        return
    with tempfile.TemporaryDirectory() as d:
        v = views.BoardView('ball', (0.0, 0.0, 0.0), 0, 1.0, 0.0, (160, 160), ortho=0.32)
        mpp = 0.32 / 160
        radius, surface = {}, {}
        for cap in (None, 0.0005):
            p = os.path.join(d, 'ball.glb')
            sphere_glb(p, r=0.1, w=0.002, cap=cap)
            R = gpu.Renderer(model.load(p), ss=4)
            keep = {}
            R.render(v, keep=keep)
            part, hull = R.ids(v, ss=8)                                                  # at 8 x: sub-pixel areas
            a = (mpp / 8) ** 2
            radius[cap] = math.sqrt((part >= 0).sum() * a / math.pi)                    # the silhouette (m)
            surface[cap] = math.sqrt(((part >= 0) & ~hull).sum() * a / math.pi)          # the surface inside the line
        line = keep['line']                                                                # 0.0022 x 160 px x mpp
        assert abs(radius[None] - 0.1) < 0.05 * mpp and abs(surface[None] - (0.1 - line)) < 0.05 * mpp, (radius, surface)
        assert abs(radius[0.0005] - (0.1 + line - 0.0005)) < 0.05 * mpp, (radius, line)
        assert abs(surface[0.0005] - (0.1 - 0.0005)) < 0.05 * mpp, (surface, line)       # the line keeps its width


def test_sphere_streaks():
    """streaks on the toon sphere: the columns toon.wgsl keeps are charkit.shade.streak_columns' (the lookup3 hash):
    every kept column facing the camera shows its streak, no other column does."""
    gpu = _gpu()
    if gpu is None:
        return
    hl = {'kind': 'streaks', 'centre': [0.0, 0.0, 0.0], 'elevation': 20.0, 'length': 16.0, 'jitter': 4.0, 'count': 24,
          'duty': 0.5, 'keep': 0.5, 'amount': 1.0, 'color': [0.0, 1.0, 0.0], 'facing': [0.9, 0.0], 'facingBlend': 0.5,
          'hash': 'lookup3'}
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 'ball.glb')
        sphere_glb(p, r=0.1, w=0.0, streaks=hl)
        M = model.load(p)
        M.root['light'] = {'direction': [0.0, 0.0, 1.0]}                               # from the camera: all lit
        M.root.pop('lines', None)
        R = gpu.Renderer(M, ss=2)
        v = views.BoardView('ball', (0.0, 0.0, 0.0), 0, 1.0, 0.0, (240, 240), ortho=0.24)
        keep = {}
        R.render(v, keep=keep)
        H = keep['main'][..., :3]
        green = (H[..., 1] > 0.6) & (H[..., 0] < 0.3)                                    # the streak colour
        ss, mpp = R.ss, 0.24 / 240 / 2
        yy, xx = np.mgrid[:H.shape[0], :H.shape[1]]
        px, py = (xx + 0.5) * mpp - 0.12, 0.12 - (yy + 0.5) * mpp                         # glTF x (her left), y up
        pz = np.sqrt(np.clip(0.1 ** 2 - px ** 2 - py ** 2, 0, None))
        az = np.arctan2(px, pz)
        col = np.floor((az + math.pi) * 24 / (2 * math.pi)).astype(int)
        kept, el0 = shade.streak_columns(hl)
        seen = np.array([green[col == c].sum() for c in range(24)])
        facing = [c for c in range(24) if abs(((c + 0.5) * 2 * math.pi / 24 - math.pi)) < math.radians(50)]
        assert all(seen[c] > 20 for c in facing if kept[c]), (seen, kept)
        assert all(seen[c] == 0 for c in range(24) if not kept[c]), (seen, kept)


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
