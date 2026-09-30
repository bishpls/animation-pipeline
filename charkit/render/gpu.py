"""charkit's toon renderer on wgpu (wgpu-py, BSD-2-Clause, on wgpu-native, MIT OR Apache-2.0): Metal on the Mac,
Vulkan on the render box's GPU, and on a machine without one Mesa's CPU drivers (llvmpipe through GL, or lavapipe through
Vulkan). No window: every frame renders into textures and is read back.

    from charkit.render import gpu, model, views
    R = gpu.Renderer(model.load(VRM))              # uploads the character once
    img = R.render(view)                           # a views.BoardView -> (H, W, 3) uint8, the board as EEVEE draws it

A frame: the main pass (the character's surfaces at this view's line width, the inverted hulls, then the alpha-blended
plates back to front) into an ss x ss supersampled target; for views with features through the hair, a second pass of
only the features with the skin as a depth holdout (charkit.qa.features_pass); then the resolve (resolve.wgsl): EEVEE's
film filter, the sRGB curve, the features laid over at `through` x their alpha.

The adapter: CHARKIT_RENDER_ADAPTER = auto (a GPU if there is one, else the CPU) | gpu | cpu | a substring of the
adapter's name or backend (e.g. 'lavapipe', 'llvmpipe', 'Vulkan', 'OpenGL').
"""
import math, os, time

import numpy as np

from . import model as model_, normals as normals_, views as views_

HERE = os.path.dirname(os.path.abspath(__file__))
FLOATS = 13                                 # interleaved vertex: pos 3, hull 3, ow 1, uv0 2, uv1 2, mask 1, ink 1
F_RIM, F_STREAKS, F_TEXTURE, F_FRINGE, F_BLUSH, F_INK, F_BLEND = 1, 2, 4, 8, 16, 32, 64
KIND = {'flat': 0, 'toon3': 1, 'hair': 1, 'face': 2, 'plate': 3}
FILTER = {'linear': 0, 'cubic': 1, 'closest': 2, 'smart': 1}
WRAP = {'extend': 0, 'clip': 1, 'repeat': 2, 'mirror': 2}
EEVEE_FILTER = 1.5                          # Blender's default film filter_size (px)
SIGMA_FAC = 0.284                           # EEVEE's Gaussian fitted to Blackman-Harris: sigma = 0.284 x radius

_DEVICE = {}


def adapter_info(a):
    i = a.info
    return {'device': i.get('device'), 'backend': i.get('backend_type'), 'type': i.get('adapter_type'),
            'vendor': i.get('vendor'), 'driver': i.get('driver_description') or i.get('driver')}


def adapters():
    import wgpu
    return [adapter_info(a) for a in wgpu.gpu.enumerate_adapters_sync()]


def device(pref=None):
    """the wgpu device for a preference (see the module doc) -> (device, adapter info). One per process and preference."""
    pref = (pref or os.environ.get('CHARKIT_RENDER_ADAPTER') or 'auto').strip()
    if pref in _DEVICE:
        return _DEVICE[pref]
    import wgpu
    ads = wgpu.gpu.enumerate_adapters_sync()
    if not ads:
        raise RuntimeError('no wgpu adapter')
    info = [adapter_info(a) for a in ads]
    gpu_rank = {'DiscreteGPU': 0, 'IntegratedGPU': 1, 'VirtualGPU': 2, 'Unknown': 3, 'CPU': 4}
    back_rank = {'Metal': 0, 'Vulkan': 0, 'D3D12': 0, 'OpenGL': 1}
    order = sorted(range(len(ads)), key=lambda i: (gpu_rank.get(info[i]['type'], 3), back_rank.get(info[i]['backend'], 2)))
    if pref == 'auto':
        pick = order[0]
    elif pref == 'gpu':
        pick = next((i for i in order if info[i]['type'] != 'CPU' and 'llvmpipe' not in str(info[i]['device'])), None)
    elif pref == 'cpu':
        pick = next((i for i in order if info[i]['type'] == 'CPU' or 'llvmpipe' in str(info[i]['device'])), None)
    else:
        key = pref.lower()
        pick = next((i for i in order if key in str(info[i]['device']).lower() or key in str(info[i]['backend']).lower()
                     or (key == 'lavapipe' and 'llvmpipe' in str(info[i]['device']) and info[i]['backend'] == 'Vulkan')),
                    None)
    if pick is None:
        raise RuntimeError(f'no adapter for {pref!r}; have {info}')
    a = ads[pick]
    lim = a.limits
    dev = a.request_device_sync(required_limits={'max-texture-dimension-2d': lim['max-texture-dimension-2d']})
    _DEVICE[pref] = (dev, info[pick])
    return _DEVICE[pref]


# ------------------------------------------------------------------------------------------------ the streaks' hash
def streak_table(hl, mode='f64'):
    """charkit.shade.hair_toon's per-column hash, evaluated once on the CPU: kept (0 / 1) and the streak's middle
    elevation (rad) for each column. Blender computes fract(sin(i k) 43758.5453) per pixel on the GPU, where sin of an
    argument in the thousands is only as good as the GPU's range reduction, so the pattern differs between GPUs; here it
    is exact ('f64'), float32 with a correctly rounded sin ('f32'), or NVIDIA's MUFU.SIN emulated ('nv': the argument
    scaled to revolutions in float32 first)."""
    n = int(hl['count'])
    idx = np.arange(n, dtype=np.float64)

    def h(k):
        if mode == 'f64':
            return np.mod(np.sin(idx * k) * 43758.5453, 1.0)
        x = (idx.astype(np.float32) * np.float32(k)).astype(np.float32)
        if mode == 'nv':
            rev = (x * np.float32(1 / (2 * math.pi))).astype(np.float32)
            s = np.sin(2 * math.pi * (rev.astype(np.float64) - np.floor(rev))).astype(np.float32)
        else:
            s = np.sin(x.astype(np.float64)).astype(np.float32)
        m = (s * np.float32(43758.5453)).astype(np.float32)
        return (m - np.floor(m)).astype(np.float64)
    keep = (h(12.9898) < hl['keep']).astype(np.float32)
    el0 = math.radians(hl['elevation'] - hl['jitter']) + h(78.233) * math.radians(2 * hl['jitter'])
    return keep, el0.astype(np.float32)


def _facing_exp(b):
    b = min(max(float(b), 0.0), 0.99999)
    return 1.0 if b == 0.5 else (2 * b if b < 0.5 else 0.5 / (1 - b))


def material_uniform(L, outline=None, region_factor=1.0, hash_mode='f64', streaks=True, part=0):
    """a material's look (+ its mesh's outline) -> the MatU block (toon.wgsl), as 204 float32 words."""
    u = np.zeros(204, np.float32)
    ui = u.view(np.uint32)
    kind = L.get('kind', 'flat')
    flags = 0
    ui[0] = KIND.get(kind, 1)
    fld = lambda i, v: u.__setitem__(slice(12 + 4 * i, 12 + 4 * i + len(v)), v)   # vec4 fields after the 3 u32 vec4s
    col = lambda c: np.asarray(list(c)[:3], np.float32)
    samp = lambda info: FILTER.get((info or {}).get('filter', 'linear'), 0) | (WRAP.get((info or {}).get('wrap', 'extend'), 0) << 4)
    if kind == 'flat':
        fld(3, col(L.get('color', (0.8, 0.8, 0.8))))
    if kind in ('toon3', 'hair', 'face'):
        fld(0, col(L['lit'])); fld(1, col(L['shade'])); fld(2, col(L['deep']))
        rim = L.get('rim') or {}
        fld(4, [L.get('threshold', 0.5), L.get('deepThreshold', 0.27), L.get('softness', 0.015), rim.get('amount', 0.0)])
        if rim.get('amount', 0) > 0:
            flags |= F_RIM
            fld(5, col(rim['color']))
            fld(6, [_facing_exp(rim.get('facing', 0.3)), *rim.get('range', (0.64, 0.68))])
        hl = L.get('highlight')
        if hl and hl.get('kind') == 'streaks' and streaks:
            flags |= F_STREAKS
            n = int(hl['count'])
            if n > 64:
                raise ValueError('streaks: at most 64 columns')
            fld(7, [*hl['centre'], n])
            fld(8, [math.radians(hl['length']), hl['duty'], hl['amount']])
            fld(9, [*hl.get('facing', (0.55, 0.25)), _facing_exp(hl.get('facingBlend', 0.5))])
            fld(10, col(hl['color']))
            keep, el0 = streak_table(hl, hash_mode)
            u[76:76 + n] = keep
            u[140:140 + n] = el0
        if L.get('texture'):
            flags |= F_TEXTURE
            ui[8] = samp(L['texture'])
    if kind == 'face':
        F = L['face']
        fld(11, [F.get('softness', 0.012), *F.get('fringeRange', (0.35, 0.55))])
        fld(12, col(F['lit'])); fld(13, col(F['shade']))
        ui[4] = samp(F.get('sdf'))
        if F.get('fringe'):
            flags |= F_FRINGE; ui[5] = samp(F['fringe'])
        if F.get('blush'):
            flags |= F_BLUSH; ui[6] = samp(F['blush'])
        if F.get('ink'):
            flags |= F_INK; ui[7] = samp(F['ink'])
    if kind == 'plate':
        ui[8] = samp(L.get('texture'))
        if L.get('alpha') == 'blend':
            flags |= F_BLEND
    if outline:
        fld(14, [float(outline['width']), float(region_factor), 1.0])
        fld(15, col(outline.get('color', (0.05, 0.03, 0.03))))
    ui[1] = flags
    ui[3] = part
    return u


def vertex_array(P):
    """a Prim -> ((n, 13) float32 interleaved: pos, hull, ow, uv0, uv1, face mask, ink weight; (n, 3) float32 normals).
    The normals are a stream of their own: an outlined object without custom normals gets its per view (normals.py)."""
    n = len(P.position)
    V = np.zeros((n, FLOATS), np.float32)
    V[:, 0:3] = P.position
    V[:, 3:6] = P.hull_dir()
    V[:, 6] = P.width_factor() if P.outline else 0.0
    if P.uv0 is not None:
        V[:, 7:9] = P.uv0
    if P.uv1 is not None:
        V[:, 9:11] = P.uv1
    if P.face_mask is not None:
        V[:, 11] = P.face_mask
    V[:, 12] = P.ink_w if P.ink_w is not None else 1.0
    nrm = P.normal / np.maximum(np.linalg.norm(P.normal, axis=1, keepdims=True), 1e-12)
    return V, np.ascontiguousarray(nrm, np.float32)


# ------------------------------------------------------------------------------------------------ the renderer
class Renderer:
    """one character on one device: its buffers, materials and pipelines; render(view) per board."""

    def __init__(self, M, adapter=None, ss=4, sigma=None, radius=EEVEE_FILTER, hash_mode='f64', through=None,
                 streaks=True, live_normals=True):
        import wgpu
        self.wgpu = wgpu
        t0 = time.time()
        self.M = M
        self.dev, self.info = device(adapter)
        self.ss, self.radius = int(ss), float(radius)
        self.sigma = float(sigma) if sigma else SIGMA_FAC * self.radius
        self.hash_mode = hash_mode
        self.streaks = streaks
        self.live_normals = live_normals
        self.through = float(through if through is not None else (M.root.get('features') or {}).get('through', 0.55))
        self.look = views_.look_of(M)
        self.timing = {}
        self._targets = {}
        self._build_pipelines()
        self._upload()
        self.timing['setup_s'] = round(time.time() - t0, 3)

    # ---- setup
    def _build_pipelines(self):
        wgpu, dev = self.wgpu, self.dev
        src = open(os.path.join(HERE, 'toon.wgsl')).read()
        self.sm = dev.create_shader_module(code=src)
        self.rm = dev.create_shader_module(code=open(os.path.join(HERE, 'resolve.wgsl')).read())
        tex_entry = lambda b: {'binding': b, 'visibility': wgpu.ShaderStage.FRAGMENT,
                               'texture': {'sample_type': wgpu.TextureSampleType.unfilterable_float,
                                           'view_dimension': wgpu.TextureViewDimension.d2}}
        vis = wgpu.ShaderStage.VERTEX | wgpu.ShaderStage.FRAGMENT
        self.bgl_view = dev.create_bind_group_layout(entries=[
            {'binding': 0, 'visibility': vis, 'buffer': {'type': wgpu.BufferBindingType.uniform}}])
        self.bgl_mat = dev.create_bind_group_layout(entries=[
            {'binding': 0, 'visibility': vis, 'buffer': {'type': wgpu.BufferBindingType.uniform}}] +
            [tex_entry(b) for b in range(1, 6)])
        self.layout = dev.create_pipeline_layout(bind_group_layouts=[self.bgl_view, self.bgl_mat])
        attrs = [{'format': wgpu.VertexFormat.float32x3, 'offset': 0, 'shader_location': 0},
                 {'format': wgpu.VertexFormat.float32x3, 'offset': 12, 'shader_location': 2},
                 {'format': wgpu.VertexFormat.float32, 'offset': 24, 'shader_location': 3},
                 {'format': wgpu.VertexFormat.float32x2, 'offset': 28, 'shader_location': 4},
                 {'format': wgpu.VertexFormat.float32x2, 'offset': 36, 'shader_location': 5},
                 {'format': wgpu.VertexFormat.float32, 'offset': 44, 'shader_location': 6},
                 {'format': wgpu.VertexFormat.float32, 'offset': 48, 'shader_location': 7}]
        vbuf = [{'array_stride': FLOATS * 4, 'step_mode': wgpu.VertexStepMode.vertex, 'attributes': attrs},
                {'array_stride': 12, 'step_mode': wgpu.VertexStepMode.vertex,
                 'attributes': [{'format': wgpu.VertexFormat.float32x3, 'offset': 0, 'shader_location': 1}]}]
        self.hdr = wgpu.TextureFormat.rgba16float
        blend_over = {'color': {'src_factor': wgpu.BlendFactor.one, 'dst_factor': wgpu.BlendFactor.one_minus_src_alpha,
                                'operation': wgpu.BlendOperation.add},
                      'alpha': {'src_factor': wgpu.BlendFactor.one, 'dst_factor': wgpu.BlendFactor.one_minus_src_alpha,
                                'operation': wgpu.BlendOperation.add}}

        def pipe(vs, fs, cull, write=True, blend=None):
            return dev.create_render_pipeline(
                layout=self.layout,
                vertex={'module': self.sm, 'entry_point': vs, 'buffers': vbuf},
                primitive={'topology': wgpu.PrimitiveTopology.triangle_list, 'front_face': wgpu.FrontFace.ccw,
                           'cull_mode': cull},
                depth_stencil={'format': wgpu.TextureFormat.depth32float, 'depth_write_enabled': write,
                               'depth_compare': wgpu.CompareFunction.less},
                multisample={'count': 1},
                fragment={'module': self.sm, 'entry_point': fs,
                          'targets': [{'format': self.hdr, 'blend': blend}]})
        C = wgpu.CullMode
        self.pipes = {
            ('surface', 'none'): pipe('vs_surface', 'fs_surface', C.none),
            ('surface', 'back'): pipe('vs_surface', 'fs_surface', C.back),
            ('blend', 'none'): pipe('vs_surface', 'fs_surface', C.none, write=False, blend=blend_over),
            ('blend', 'back'): pipe('vs_surface', 'fs_surface', C.back, write=False, blend=blend_over),
            ('hull', 'front'): pipe('vs_hull', 'fs_hull', C.front),
            ('holdout', 'none'): pipe('vs_hull', 'fs_holdout', C.none),
            ('surface_id', 'none'): pipe('vs_surface', 'fs_surface_id', C.none),
            ('surface_id', 'back'): pipe('vs_surface', 'fs_surface_id', C.back),
            ('hull_id', 'front'): pipe('vs_hull', 'fs_hull_id', C.front),
        }
        self.bgl_res = dev.create_bind_group_layout(entries=[
            {'binding': 0, 'visibility': wgpu.ShaderStage.FRAGMENT, 'buffer': {'type': wgpu.BufferBindingType.uniform}},
            tex_entry(1), tex_entry(2)])
        self.res_pipe = dev.create_render_pipeline(
            layout=dev.create_pipeline_layout(bind_group_layouts=[self.bgl_res]),
            vertex={'module': self.rm, 'entry_point': 'vs_full', 'buffers': []},
            primitive={'topology': wgpu.PrimitiveTopology.triangle_list},
            depth_stencil=None, multisample={'count': 1},
            fragment={'module': self.rm, 'entry_point': 'fs_resolve',
                      'targets': [{'format': wgpu.TextureFormat.rgba8unorm}]})
        self.view_buf = dev.create_buffer(size=144, usage=wgpu.BufferUsage.UNIFORM | wgpu.BufferUsage.COPY_DST)
        self.view_bg = dev.create_bind_group(layout=self.bgl_view, entries=[
            {'binding': 0, 'resource': {'buffer': self.view_buf, 'offset': 0, 'size': 144}}])
        self.res_buf = dev.create_buffer(size=32, usage=wgpu.BufferUsage.UNIFORM | wgpu.BufferUsage.COPY_DST)

    def _texture(self, a):
        wgpu = self.wgpu
        h, w = a.shape[:2]
        t = self.dev.create_texture(size=(w, h, 1), format=wgpu.TextureFormat.rgba32float,
                                    usage=wgpu.TextureUsage.TEXTURE_BINDING | wgpu.TextureUsage.COPY_DST)
        self.dev.queue.write_texture({'texture': t, 'mip_level': 0, 'origin': (0, 0, 0)},
                                     np.ascontiguousarray(a, np.float32),
                                     {'offset': 0, 'bytes_per_row': w * 16, 'rows_per_image': h}, (w, h, 1))
        return t.create_view()

    def _upload(self):
        wgpu, dev, M = self.wgpu, self.dev, self.M
        dummy = self._texture(np.zeros((1, 1, 4), np.float32))
        texv = {i: self._texture(a) for i, a in M.textures.items()}
        regions = (M.root.get('lines') or {}).get('regions') or {}
        self.items = []
        for P in M.prims:
            L = P.look
            F = L.get('face') or {}
            slot = lambda info: texv.get(info['index'], dummy) if info else dummy
            ub = material_uniform(L, P.outline, regions.get((P.outline or {}).get('region', ''), 1.0), self.hash_mode,
                                    self.streaks, part=len(self.items) + 1)
            mb = dev.create_buffer_with_data(data=ub.tobytes(), usage=wgpu.BufferUsage.UNIFORM)
            bg = dev.create_bind_group(layout=self.bgl_mat, entries=[
                {'binding': 0, 'resource': {'buffer': mb, 'offset': 0, 'size': ub.nbytes}},
                {'binding': 1, 'resource': slot(F.get('sdf'))},
                {'binding': 2, 'resource': slot(F.get('fringe'))},
                {'binding': 3, 'resource': slot(F.get('blush'))},
                {'binding': 4, 'resource': slot(F.get('ink'))},
                {'binding': 5, 'resource': slot(L.get('texture'))}])
            V, Nn = vertex_array(P)
            vb = dev.create_buffer_with_data(data=V.tobytes(), usage=wgpu.BufferUsage.VERTEX)
            nb = dev.create_buffer_with_data(data=Nn.tobytes(), usage=wgpu.BufferUsage.VERTEX | wgpu.BufferUsage.COPY_DST)
            ib = dev.create_buffer_with_data(data=np.ascontiguousarray(P.index, np.uint32).tobytes(),
                                             usage=wgpu.BufferUsage.INDEX)
            self.items.append(dict(P=P, vb=vb, nb=nb, ib=ib, n=len(P.index), bg=bg, mb=mb,
                                   blend=L.get('alpha') == 'blend' and L.get('kind') == 'plate',
                                   cull='none' if L.get('doubleSided', True) else 'back',
                                   feature=bool(P.mx.get('feature')), holdout=bool(P.mx.get('holdout')),
                                   outline=bool(P.outline), centre=P.position.mean(0) if len(P.position) else np.zeros(3)))
        # objects shaded with their moved surface's normals (normals.py): one group per object, updated per line width
        self.groups = []
        if self.live_normals:
            by = {}
            for it in self.items:
                if normals_.needs_recompute(it['P']):
                    by.setdefault(it['P'].object, []).append(it)
            for name, its in by.items():
                self.groups.append(dict(name=name, items=its, G=normals_.Group([i['P'] for i in its]), w=None,
                                        region=(its[0]['P'].outline or {}).get('region', ''),
                                        build=float(its[0]['P'].outline['width'])))

    def _update_normals(self, line):
        """the per-view normals of the groups (the surface moved inward by this view's width): written only when the
        width changes."""
        regions = (self.look.get('lines') or {}).get('regions') or {}
        t = time.time()
        for g in self.groups:
            w = line * regions.get(g['region'], 1.0) if line > 0 else g['build']
            if g['w'] is not None and abs(g['w'] - w) < 1e-12:
                continue
            for it, n in zip(g['items'], g['G'].normals(w)):
                self.dev.queue.write_buffer(it['nb'], 0, n.tobytes())
            g['w'] = w
        self.timing['normals_s'] = self.timing.get('normals_s', 0.0) + (time.time() - t)

    def _target(self, W, H):
        key = (W, H)
        if key not in self._targets:
            wgpu, dev = self.wgpu, self.dev
            ss = self.ss
            RA = wgpu.TextureUsage.RENDER_ATTACHMENT | wgpu.TextureUsage.TEXTURE_BINDING | wgpu.TextureUsage.COPY_SRC
            mk = lambda fmt, use, w=W * ss, h=H * ss: dev.create_texture(size=(w, h, 1), format=fmt, usage=use)
            Wp = (W + 63) // 64 * 64                    # 256-byte rows: one read, no per-row copies
            T = dict(main=mk(self.hdr, RA), feat=mk(self.hdr, RA),
                     depth=mk(wgpu.TextureFormat.depth32float, wgpu.TextureUsage.RENDER_ATTACHMENT),
                     out=mk(wgpu.TextureFormat.rgba8unorm, wgpu.TextureUsage.RENDER_ATTACHMENT | wgpu.TextureUsage.COPY_SRC,
                            Wp, H), Wp=Wp)
            T['res_bg'] = dev.create_bind_group(layout=self.bgl_res, entries=[
                {'binding': 0, 'resource': {'buffer': self.res_buf, 'offset': 0, 'size': 32}},
                {'binding': 1, 'resource': T['main'].create_view()},
                {'binding': 2, 'resource': T['feat'].create_view()}])
            while len(self._targets) >= 2:             # the two board sizes (face, body); the hi-res targets are large
                self._targets.pop(next(iter(self._targets)))
            self._targets[key] = T
        return self._targets[key]

    # ---- a frame
    def view_uniform(self, v, cam):
        light = views_.view_light(self.M, v, self.look)
        lines = self.look.get('lines') or {}
        line = lines.get('frac', 0.0) * cam.res[1] * cam.m_per_px if lines.get('mode') == 'screen' else 0.0
        u = np.zeros(36, np.float32)
        u[0:16] = cam.viewproj.T.ravel()               # column-major
        u[16:19] = cam.eye; u[19] = 1.0 if cam.ortho else 0.0
        u[20:23] = cam.back
        u[24:27] = light
        u[28:31] = light                               # the head's rest frame: the build pose
        u[32] = line
        return u, light, line

    def _pass(self, enc, T, which, clear):
        wgpu = self.wgpu
        rp = enc.begin_render_pass(
            color_attachments=[{'view': T[which].create_view(), 'clear_value': clear,
                                'load_op': wgpu.LoadOp.clear, 'store_op': wgpu.StoreOp.store}],
            depth_stencil_attachment={'view': T['depth'].create_view(), 'depth_clear_value': 1.0,
                                      'depth_load_op': wgpu.LoadOp.clear, 'depth_store_op': wgpu.StoreOp.store})
        rp.set_bind_group(0, self.view_bg)
        return rp

    def _draw(self, rp, it, pipe):
        rp.set_pipeline(self.pipes[pipe])
        rp.set_bind_group(1, it['bg'])
        rp.set_vertex_buffer(0, it['vb'])
        rp.set_vertex_buffer(1, it['nb'])
        rp.set_index_buffer(it['ib'], self.wgpu.IndexFormat.uint32)
        rp.draw_indexed(it['n'])

    def _blend_order(self, items, cam):
        d = [float((cam.view @ np.array([*it['centre'], 1.0]))[2]) for it in items]    # view z (negative in front)
        return [it for _, it in sorted(zip(d, items), key=lambda x: x[0])]            # farthest first

    def render(self, v, features=None, keep=None):
        """one board view -> (H, W, 3) uint8. features: lay the features through the hair (default v.features).
        keep: a dict to receive the hi-res linear frame ('main', (H ss, W ss, 4) float) for measurement."""
        wgpu, dev = self.wgpu, self.dev
        t0 = time.time()
        cam = views_.camera(v)
        W, H = cam.res
        T = self._target(W, H)
        u, light, line = self.view_uniform(v, cam)
        dev.queue.write_buffer(self.view_buf, 0, u.tobytes())
        self._update_normals(line)
        feats = v.features if features is None else features
        feats = feats and any(it['feature'] for it in self.items)
        bg = [float(x) for x in views_.BG]
        enc = dev.create_command_encoder()
        rp = self._pass(enc, T, 'main', (*bg, 1.0))
        for it in self.items:
            if not it['blend']:
                self._draw(rp, it, ('surface', it['cull']))
        for it in self.items:
            if it['outline']:
                self._draw(rp, it, ('hull', 'front'))
        for it in self._blend_order([i for i in self.items if i['blend']], cam):
            self._draw(rp, it, ('blend', it['cull']))
        rp.end()
        if feats:
            rp = self._pass(enc, T, 'feat', (0.0, 0.0, 0.0, 0.0))
            for it in self.items:
                if it['holdout']:
                    self._draw(rp, it, ('holdout', 'none'))
            for it in self.items:
                if it['feature'] and not it['blend']:
                    self._draw(rp, it, ('surface', it['cull']))
            for it in self._blend_order([i for i in self.items if i['feature'] and i['blend']], cam):
                self._draw(rp, it, ('blend', it['cull']))
            rp.end()
        r = np.array([self.ss, self.sigma, self.radius, self.through, 1.0 if feats else 0.0, 0, 0, 0], np.float32)
        dev.queue.write_buffer(self.res_buf, 0, r.tobytes())
        rp = enc.begin_render_pass(color_attachments=[{'view': T['out'].create_view(), 'clear_value': (0, 0, 0, 1),
                                                       'load_op': wgpu.LoadOp.clear, 'store_op': wgpu.StoreOp.store}])
        rp.set_pipeline(self.res_pipe)
        rp.set_bind_group(0, T['res_bg'])
        rp.set_viewport(0, 0, W, H, 0, 1)
        rp.draw(3)
        rp.end()
        dev.queue.submit([enc.finish()])
        Wp = T['Wp']
        raw = dev.queue.read_texture({'texture': T['out'], 'mip_level': 0, 'origin': (0, 0, 0)},
                                     {'offset': 0, 'bytes_per_row': Wp * 4, 'rows_per_image': H}, (Wp, H, 1))
        img = np.frombuffer(raw, np.uint8).reshape(H, Wp, 4)[:, :W, :3].copy()
        if keep is not None:
            keep['main'] = self.read_hdr(T['main'], W * self.ss, H * self.ss)
            if feats:
                keep['feat'] = self.read_hdr(T['feat'], W * self.ss, H * self.ss)
            keep.update(light=light, line=line, cam=cam)
        self.timing.setdefault('frames', []).append(round(time.time() - t0, 4))
        return img

    def ids(self, v, ss=1):
        """which part each pixel (at ss x the view's resolution, its centre) shows: -> (part (H, W) int, -1 the
        background, an index into self.items / the model's prims; hull (H, W) bool, the part's outline there). Blended
        plates count as opaque here."""
        wgpu, dev = self.wgpu, self.dev
        cam = views_.camera(v)
        W, H = cam.res[0] * ss, cam.res[1] * ss
        u, _, line = self.view_uniform(v, cam)
        dev.queue.write_buffer(self.view_buf, 0, u.tobytes())
        self._update_normals(line)
        RA = wgpu.TextureUsage.RENDER_ATTACHMENT | wgpu.TextureUsage.COPY_SRC
        col = dev.create_texture(size=(W, H, 1), format=self.hdr, usage=RA)
        dep = dev.create_texture(size=(W, H, 1), format=wgpu.TextureFormat.depth32float,
                                 usage=wgpu.TextureUsage.RENDER_ATTACHMENT)
        enc = dev.create_command_encoder()
        rp = enc.begin_render_pass(
            color_attachments=[{'view': col.create_view(), 'clear_value': (0, 0, 0, 0), 'load_op': wgpu.LoadOp.clear,
                                'store_op': wgpu.StoreOp.store}],
            depth_stencil_attachment={'view': dep.create_view(), 'depth_clear_value': 1.0,
                                      'depth_load_op': wgpu.LoadOp.clear, 'depth_store_op': wgpu.StoreOp.store})
        rp.set_bind_group(0, self.view_bg)
        for it in self.items:
            self._draw(rp, it, ('surface_id', it['cull']))
        for it in self.items:
            if it['outline']:
                self._draw(rp, it, ('hull_id', 'front'))
        rp.end()
        dev.queue.submit([enc.finish()])
        a = self.read_hdr(col, W, H)
        return np.round(a[..., 0]).astype(int) - 1, a[..., 1] > 0.5

    def read_hdr(self, tex, w, h):
        raw = self.dev.queue.read_texture({'texture': tex, 'mip_level': 0, 'origin': (0, 0, 0)},
                                          {'offset': 0, 'bytes_per_row': w * 8, 'rows_per_image': h}, (w, h, 1))
        return np.frombuffer(raw, np.float16).reshape(h, w, 4).astype(np.float32)
