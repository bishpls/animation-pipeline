"""What the QA reads of a frame, drawn by the toon renderer (docs/workstreams/toonrender.md, phase 2): the picture as the
boards draw it (EEVEE's film filter, over a transparent or the world's background) and, on the measuring grid, per pixel:
the part (the export's primitive, so its object), whether it is an outline hull, the tone class, the depth along the view
and the shading normal. The same passes and shader as the boards (toon.wgsl), with measure.wgsl's outputs beside them.

    from charkit.render import buffers, model
    Q = buffers.Frames(model.load('OUT/clawd.vrm'))                 # one per export: the character uploaded once
    cam = buffers.window(az, origin, pix, win)                        # charkit.geom.raster.window_project's window
    F = Q.frame(cam, light=ldir, aux_ss=3)                            # dict: picture, part, hull, tone, depth, normal
    Q.object_at(F, row, col)                                          # the object under a pixel (click-to-flag)

A measuring window is charkit.geom.raster's (and charkit.qa3d.Frame's, lookqa.HeadFrame's): orthographic from azimuth az
(0 in front, the camera on -y), the window centred on origin (u across the view, z up; metres), pixel (r, c) spanning u in
[c pix - win.x, (c + 1) pix - win.x) round origin[0] and z in (top - (r + 1) pix, top - r pix] round origin[1]. Every
position and direction here is in Blender's frame (Z up, facing -Y); the export's glTF frame stays inside.

Per frame, what to draw: `draw` (object names; None: every one), `off` (objects drawn without their outline: the surface
where it is, no hull; charkit.qa3d.surfaces(outline=False)), `paint` ({primitive index: (triangle mask, linear RGB)}: those
triangles in a flat colour, as the scalp measure paints the cranium), `line` (the view's screen-line width in metres,
times each region's factor; 0: every outline at its build width, charkit.qa3d's surfaces), `light` (toward the key, world;
None: the boards' light for az, charkit.shade.view_light).
"""
import math, os, time

import numpy as np

from . import gpu as gpu_, model as model_, views as views_

HERE = os.path.dirname(os.path.abspath(__file__))
RES_BYTES = 256                        # WebGPU's row alignment for texture reads


class Window(views_.Camera):
    """an orthographic measuring window (a views.Camera with its azimuth)."""
    az: float = 0.0


def window(az, origin, pix, win, depth=5.0, reach=3.0):
    """charkit.geom.raster's measuring window (window_project with L = 1: origin, pix, win in metres) as a camera
    -> Window. The camera sits `depth` m in front of the window's centre; near and far `reach` m either side of it."""
    W = int(round(2 * win['x'] / pix))
    H = int(round((win['top'] - win['bottom']) / pix))
    a = math.radians(az)
    rb = np.array([math.cos(a), math.sin(a), 0.0])           # across the view (u), Blender frame
    db = np.array([-math.sin(a), math.cos(a), 0.0])          # into the view
    uc = origin[0] - win['x'] + W * pix / 2
    zc = origin[1] + win['top'] - H * pix / 2
    eye_b = rb * uc + np.array([0, 0, zc]) - db * depth
    r, f, e = model_.to_gltf(rb), model_.to_gltf(db), model_.to_gltf(eye_b)
    u = np.array([0.0, 1.0, 0.0])
    Vm = np.eye(4)
    Vm[0, :3], Vm[1, :3], Vm[2, :3] = r, u, -f
    Vm[:3, 3] = -Vm[:3, :3] @ e
    hx, hy = W * pix / 2, H * pix / 2
    near, far = depth - reach, depth + reach
    P = np.zeros((4, 4))
    P[0, 0], P[1, 1] = 1 / hx, 1 / hy
    P[2, 2], P[2, 3] = -1 / (far - near), -near / (far - near)
    P[3, 3] = 1
    cam = Window(view=Vm, proj=P, eye=e, back=-f, ortho=True, m_per_px=pix, res=(W, H))
    cam.az = float(az)
    return cam


def board_window(v):
    """a board view (views.BoardView) as a camera with its azimuth (a perspective one's too) -> Window."""
    c = views_.camera(v)
    cam = Window(**{k: getattr(c, k) for k in ('view', 'proj', 'eye', 'back', 'ortho', 'm_per_px', 'res')})
    cam.az = float(v.az)
    return cam


def _pad(w, bpp):
    n = RES_BYTES // bpp
    return (w + n - 1) // n * n


class Frames:
    """measuring frames of one character on one device: gpu.Renderer's upload (its buffers, materials and live garment
    normals) with the measurement pipelines beside the colour ones."""

    def __init__(self, M, adapter=None, ss=4, R=None):
        import wgpu
        self.wgpu = wgpu
        t0 = time.time()
        self.R = R if R is not None else gpu_.Renderer(M, adapter=adapter, ss=ss)
        self.M, self.dev, self.info, self.ss = self.R.M, self.R.dev, self.R.info, self.R.ss
        self.prims = [it['P'] for it in self.R.items]
        self.objects = [P.object for P in self.prims]           # per part (primitive): its object
        self._build()
        self._overlays = {}
        self._targets = {}
        self._no_streaks = {}
        self.timing = {'setup_s': round(time.time() - t0, 3), 'frames': []}

    # ---- setup
    def _build(self):
        wgpu, dev, R = self.wgpu, self.dev, self.R
        toon = open(os.path.join(HERE, 'toon.wgsl')).read()
        co = 'inward(build_w())' if 'fn inward(' in toon else 'build_w()'
        src = toon + '\nfn co_w() -> f32 { return %s; }\n' % co + open(os.path.join(HERE, 'measure.wgsl')).read()
        sm = dev.create_shader_module(code=src)
        attrs = [{'format': wgpu.VertexFormat.float32x3, 'offset': 0, 'shader_location': 0},
                 {'format': wgpu.VertexFormat.float32x3, 'offset': 12, 'shader_location': 2},
                 {'format': wgpu.VertexFormat.float32, 'offset': 24, 'shader_location': 3},
                 {'format': wgpu.VertexFormat.float32x2, 'offset': 28, 'shader_location': 4},
                 {'format': wgpu.VertexFormat.float32x2, 'offset': 36, 'shader_location': 5},
                 {'format': wgpu.VertexFormat.float32, 'offset': 44, 'shader_location': 6},
                 {'format': wgpu.VertexFormat.float32, 'offset': 48, 'shader_location': 7}]
        vbuf = [{'array_stride': gpu_.FLOATS * 4, 'step_mode': wgpu.VertexStepMode.vertex, 'attributes': attrs},
                {'array_stride': 12, 'step_mode': wgpu.VertexStepMode.vertex,
                 'attributes': [{'format': wgpu.VertexFormat.float32x3, 'offset': 0, 'shader_location': 1}]}]
        over = {'color': {'src_factor': wgpu.BlendFactor.one, 'dst_factor': wgpu.BlendFactor.one_minus_src_alpha,
                          'operation': wgpu.BlendOperation.add},
                'alpha': {'src_factor': wgpu.BlendFactor.one, 'dst_factor': wgpu.BlendFactor.one_minus_src_alpha,
                          'operation': wgpu.BlendOperation.add}}
        self.hdr, self.aux_fmt = wgpu.TextureFormat.rgba16float, wgpu.TextureFormat.rgba32float

        def pipe(vs, fs, cull, targets, write=True):
            return dev.create_render_pipeline(
                layout=R.layout, vertex={'module': sm, 'entry_point': vs, 'buffers': vbuf},
                primitive={'topology': wgpu.PrimitiveTopology.triangle_list, 'front_face': wgpu.FrontFace.ccw,
                           'cull_mode': cull},
                depth_stencil={'format': wgpu.TextureFormat.depth32float, 'depth_write_enabled': write,
                               'depth_compare': wgpu.CompareFunction.less},
                multisample={'count': 1}, fragment={'module': sm, 'entry_point': fs, 'targets': targets})
        C = wgpu.CullMode
        col = [{'format': self.hdr}]
        colb = [{'format': self.hdr, 'blend': over}]
        mrt = [{'format': self.aux_fmt}, {'format': self.aux_fmt}]
        P = {}
        for cull in ('none', 'back'):
            cm = getattr(C, cull)
            P[('colour', 'surface', cull)] = pipe('vs_surface', 'fs_surface', cm, col)
            P[('colour', 'co', cull)] = pipe('vs_co', 'fs_surface', cm, col)
            P[('colour', 'blend', cull)] = pipe('vs_surface', 'fs_surface', cm, colb, write=False)
            P[('aux', 'surface', cull)] = pipe('vs_surface', 'fs_measure', cm, mrt)
            P[('aux', 'co', cull)] = pipe('vs_co', 'fs_measure', cm, mrt)
            P[('aux', 'blend', cull)] = pipe('vs_surface', 'fs_measure_plate', cm, mrt, write=False)
        P[('colour', 'hull', 'front')] = pipe('vs_hull', 'fs_hull', C.front, col)
        P[('aux', 'hull', 'front')] = pipe('vs_hull', 'fs_measure_hull', C.front, mrt)
        self.pipes = P
        rm = dev.create_shader_module(code=open(os.path.join(HERE, 'qa_resolve.wgsl')).read())
        tex_entry = lambda b: {'binding': b, 'visibility': wgpu.ShaderStage.FRAGMENT,
                               'texture': {'sample_type': wgpu.TextureSampleType.unfilterable_float,
                                           'view_dimension': wgpu.TextureViewDimension.d2}}
        self.bgl_res = dev.create_bind_group_layout(entries=[
            {'binding': 0, 'visibility': wgpu.ShaderStage.FRAGMENT, 'buffer': {'type': wgpu.BufferBindingType.uniform}},
            tex_entry(1)])
        self.res_pipe = dev.create_render_pipeline(
            layout=dev.create_pipeline_layout(bind_group_layouts=[self.bgl_res]),
            vertex={'module': rm, 'entry_point': 'vs_full', 'buffers': []},
            primitive={'topology': wgpu.PrimitiveTopology.triangle_list}, depth_stencil=None, multisample={'count': 1},
            fragment={'module': rm, 'entry_point': 'fs_resolve', 'targets': [{'format': self.aux_fmt}]})
        self.res_buf = dev.create_buffer(size=16, usage=wgpu.BufferUsage.UNIFORM | wgpu.BufferUsage.COPY_DST)

    def _overlay(self, k, mask, rgb):
        """primitive k's triangles under mask drawn flat in rgb (linear): an item of its own (the part's id, its outline
        for the vertex stage), and the primitive's index buffer without them. Cached per (k, mask, colour)."""
        wgpu, dev = self.wgpu, self.dev
        mask = np.asarray(mask, bool)
        key = (k, hash(mask.tobytes()), tuple(np.round(np.asarray(rgb, float), 6)))
        if key in self._overlays:
            return self._overlays[key]
        it = self.R.items[k]
        P = it['P']
        tri = np.asarray(P.index, np.uint32).reshape(-1, 3)
        ub = gpu_.material_uniform({'kind': 'flat', 'color': [float(x) for x in rgb]}, P.outline, part=k + 1)
        mb = dev.create_buffer_with_data(data=ub.tobytes(), usage=wgpu.BufferUsage.UNIFORM)
        dummy = self.R._texture(np.zeros((1, 1, 4), np.float32))
        bg = dev.create_bind_group(layout=self.R.bgl_mat, entries=[
            {'binding': 0, 'resource': {'buffer': mb, 'offset': 0, 'size': ub.nbytes}}] +
            [{'binding': b, 'resource': dummy} for b in range(1, 6)])

        def ib(t):
            return dev.create_buffer_with_data(data=np.ascontiguousarray(t.ravel(), np.uint32).tobytes(),
                                               usage=wgpu.BufferUsage.INDEX) if len(t) else None
        got = (dict(it, ib=ib(tri[mask]), n=int(mask.sum()) * 3, bg=bg, mb=mb, blend=False),
               dict(it, ib=ib(tri[~mask]), n=int((~mask).sum()) * 3))
        while len(self._overlays) >= 8:
            self._overlays.pop(next(iter(self._overlays)))
        self._overlays[key] = got
        return got

    def _target(self, kind, W, H):
        key = (kind, W, H)
        if key not in self._targets:
            wgpu, dev = self.wgpu, self.dev
            RA = wgpu.TextureUsage.RENDER_ATTACHMENT | wgpu.TextureUsage.TEXTURE_BINDING | wgpu.TextureUsage.COPY_SRC
            mk = lambda fmt, use, w=W, h=H: dev.create_texture(size=(w, h, 1), format=fmt, usage=use)
            T = {'depth': mk(wgpu.TextureFormat.depth32float, wgpu.TextureUsage.RENDER_ATTACHMENT)}
            if kind == 'colour':
                T['main'] = mk(self.hdr, RA)
            elif kind == 'aux':
                T['aux'], T['nor'] = mk(self.aux_fmt, RA), mk(self.aux_fmt, RA)
            elif kind == 'resolve':
                T = {'out': mk(self.aux_fmt, RA, _pad(W, 16), H)}
            while len(self._targets) >= 6:
                self._targets.pop(next(iter(self._targets)))
            self._targets[key] = T
        return self._targets[key]

    # ---- a frame
    def view_uniform(self, cam, light_b, line):
        u = np.zeros(36, np.float32)
        u[0:16] = (cam.proj @ cam.view).T.ravel()
        u[16:19] = cam.eye; u[19] = 1.0 if cam.ortho else 0.0
        u[20:23] = cam.back
        lg = model_.to_gltf(np.asarray(light_b, float))
        u[24:27] = lg
        u[28:31] = lg                                           # the head's rest frame: the build pose
        u[32] = line
        return u

    def light_for(self, az):
        """the boards' key light for a view from azimuth az (charkit.shade.view_light on the export's look), world."""
        from charkit import shade
        return np.asarray(shade.view_light(az, views_.look_of(self.M)), float)

    def _plain(self, k):
        """item k with its material's streaks off (a bind group of its own, made once)."""
        if k not in self._no_streaks:
            wgpu, dev, it = self.wgpu, self.dev, self.R.items[k]
            P = it['P']
            if not (P.look.get('highlight') or {}):
                self._no_streaks[k] = it
            else:
                regions = (self.M.root.get('lines') or {}).get('regions') or {}
                ub = gpu_.material_uniform(P.look, P.outline, regions.get((P.outline or {}).get('region', ''), 1.0),
                                           streaks=False, part=k + 1)
                mb = dev.create_buffer_with_data(data=ub.tobytes(), usage=wgpu.BufferUsage.UNIFORM)
                entries = [{'binding': 0, 'resource': {'buffer': mb, 'offset': 0, 'size': ub.nbytes}}]
                texv = self._tex_views(k)
                entries += [{'binding': b, 'resource': texv[b - 1]} for b in range(1, 6)]
                self._no_streaks[k] = dict(it, bg=dev.create_bind_group(layout=self.R.bgl_mat, entries=entries), mb=mb)
        return self._no_streaks[k]

    def _tex_views(self, k):
        """item k's five texture views (sdf, fringe, blush, ink, the material's), as gpu.Renderer bound them."""
        if not hasattr(self, '_texv'):
            self._dummy = self.R._texture(np.zeros((1, 1, 4), np.float32))
            self._texv = {i: self.R._texture(a) for i, a in self.M.textures.items()}
        L = self.prims[k].look
        F = L.get('face') or {}
        slot = lambda info: self._texv.get(info['index'], self._dummy) if info else self._dummy
        return [slot(F.get('sdf')), slot(F.get('fringe')), slot(F.get('blush')), slot(F.get('ink')), slot(L.get('texture'))]

    def _items(self, draw, off, paint, streaks=True):
        """-> [(item, 'surface' | 'co', is_blend)], [hull items] for a frame's choices."""
        draw = None if draw is None else set(draw)
        off = set(off or ())
        paint = paint or {}
        surf, hulls = [], []
        items = self.R.items if streaks else [self._plain(k) for k in range(len(self.R.items))]
        for k, it in enumerate(items):
            name = it['P'].object
            if draw is not None and name not in draw:
                continue
            mode = 'co' if name in off else 'surface'
            if k in paint:
                p_it, rest = self._overlay(k, *paint[k])
                for x in (rest, p_it):
                    if x['ib'] is not None:
                        surf.append((x, mode, False))
            else:
                surf.append((it, mode, it['blend']))
            if it['outline'] and name not in off:
                hulls.append(it)
        return surf, hulls

    def _encode(self, enc, kind, T, cam, surf, hulls, clear):
        wgpu, R = self.wgpu, self.R
        if kind == 'colour':
            att = [{'view': T['main'].create_view(), 'clear_value': clear, 'load_op': wgpu.LoadOp.clear,
                    'store_op': wgpu.StoreOp.store}]
        else:
            att = [{'view': T['aux'].create_view(), 'clear_value': (0.0, 0.0, -1.0, float('inf')),
                    'load_op': wgpu.LoadOp.clear, 'store_op': wgpu.StoreOp.store},
                   {'view': T['nor'].create_view(), 'clear_value': (0.0, 0.0, 0.0, 0.0), 'load_op': wgpu.LoadOp.clear,
                    'store_op': wgpu.StoreOp.store}]
        rp = enc.begin_render_pass(color_attachments=att, depth_stencil_attachment={
            'view': T['depth'].create_view(), 'depth_clear_value': 1.0, 'depth_load_op': wgpu.LoadOp.clear,
            'depth_store_op': wgpu.StoreOp.store})
        rp.set_bind_group(0, R.view_bg)

        def draw(it, key):
            rp.set_pipeline(self.pipes[key])
            rp.set_bind_group(1, it['bg'])
            rp.set_vertex_buffer(0, it['vb'])
            rp.set_vertex_buffer(1, it['nb'])
            rp.set_index_buffer(it['ib'], wgpu.IndexFormat.uint32)
            rp.draw_indexed(it['n'])
        for it, mode, blend in surf:
            if not blend:
                draw(it, (kind, mode, it['cull']))
        for it in hulls:
            draw(it, (kind, 'hull', 'front'))
        for it in R._blend_order([x[0] for x in surf if x[2]], cam):
            draw(it, (kind, 'blend', it['cull']))
        rp.end()

    def _read(self, tex, w, h, bpp, dtype):
        wp = _pad(w, bpp)
        raw = self.dev.queue.read_texture({'texture': tex, 'mip_level': 0, 'origin': (0, 0, 0)},
                                          {'offset': 0, 'bytes_per_row': wp * bpp, 'rows_per_image': h}, (w, h, 1))
        n = bpp // np.dtype(dtype).itemsize
        return np.frombuffer(raw, dtype).reshape(h, wp, n)[:, :w].astype(np.float32)

    def frame(self, cam, draw=None, off=(), paint=None, light=None, line=0.0, transparent=True, aux_ss=1,
              picture=True, aux=True, colour=False, world=views_.BG, streaks=True):
        """one measuring frame -> dict:
          picture  (H, W, 4) floats: sRGB colour and straight alpha at 8 bits (as a saved PNG reads back; charkit.qa3d.draw's),
                   from ss x ss samples a pixel through EEVEE's film filter; over `world` (linear) unless transparent
          part     (H a, W a) int: the primitive each pixel shows (-1 none), a = aux_ss; self.objects[part] its object
          hull     (H a, W a) bool: the part's outline hull
          tone     (H a, W a) float: 0 lit .. 1 shade .. 2 deep; NaN off the toon materials and under the face's ink
          depth    (H a, W a) float: along the view from the camera (m), inf where empty
          normal   (H a, W a, 3): the shading normal (world, Blender frame), toward the viewer
          colour   with colour=True: (H a, W a, 4) linear premultiplied colour and coverage, one sample a pixel
        the buffers one sample at each pixel centre of the measuring grid (the window at aux_ss x its resolution).
        streaks=False: the hair's drawn streaks off (charkit.shade.hair_toon's highlight)."""
        wgpu, dev, R = self.wgpu, self.dev, self.R
        t0 = time.time()
        W, H = cam.res
        light = self.light_for(cam.az) if light is None else np.asarray(light, float)
        light = light / max(np.linalg.norm(light), 1e-12)
        R._update_normals(line)
        surf, hulls = self._items(draw, off, paint, streaks)
        out = {'light': light, 'line': line, 'res': (W, H), 'aux_ss': aux_ss}
        clear = (0.0, 0.0, 0.0, 0.0) if transparent else (*[float(x) for x in world], 1.0)
        jobs = []
        if picture:
            jobs.append(('picture', 'colour', self.ss))
        if colour:
            jobs.append(('colour', 'colour', aux_ss))
        if aux:
            jobs.append(('aux', 'aux', aux_ss))
        for name, kind, k in jobs:
            c = self._scaled(cam, k)
            dev.queue.write_buffer(R.view_buf, 0, self.view_uniform(c, light, line).tobytes())
            T = self._target(kind, W * k, H * k)
            enc = dev.create_command_encoder()
            self._encode(enc, kind, T, c, surf, hulls, clear)
            if name == 'picture':
                sigma = gpu_.SIGMA_FAC * gpu_.EEVEE_FILTER
                dev.queue.write_buffer(self.res_buf, 0, np.array([k, sigma, gpu_.EEVEE_FILTER, 0], np.float32).tobytes())
                To = self._target('resolve', W, H)
                bg = dev.create_bind_group(layout=self.bgl_res, entries=[
                    {'binding': 0, 'resource': {'buffer': self.res_buf, 'offset': 0, 'size': 16}},
                    {'binding': 1, 'resource': T['main'].create_view()}])
                rp = enc.begin_render_pass(color_attachments=[{'view': To['out'].create_view(), 'clear_value': (0, 0, 0, 0),
                                                               'load_op': wgpu.LoadOp.clear, 'store_op': wgpu.StoreOp.store}])
                rp.set_pipeline(self.res_pipe)
                rp.set_bind_group(0, bg)
                rp.set_viewport(0, 0, W, H, 0, 1)
                rp.draw(3)
                rp.end()
            dev.queue.submit([enc.finish()])
            if name == 'picture':
                img = self._read(To['out'], W, H, 16, np.float32)
                out['picture'] = picture_from(img)
            elif name == 'colour':
                out['colour'] = self._read(T['main'], W * k, H * k, 8, np.float16)
            else:
                a = self._read(T['aux'], W * k, H * k, 16, np.float32)
                n = self._read(T['nor'], W * k, H * k, 16, np.float32)
                part = np.rint(a[..., 0]).astype(np.int64) - 1
                out['part'] = part
                out['hull'] = (a[..., 1] > 0.5) & (part >= 0)
                tone = a[..., 2].astype(np.float64)
                out['tone'] = np.where(tone < -0.5, np.nan, tone)
                out['depth'] = np.where(part >= 0, a[..., 3], np.inf).astype(np.float64)
                out['normal'] = n[..., :3].astype(np.float64) @ model_.C3        # glTF -> Blender
        self.timing['frames'].append(round(time.time() - t0, 4))
        return out

    def _scaled(self, cam, k):
        """the camera at k x its resolution (the same window)."""
        if k == 1:
            return cam
        W, H = cam.res
        c = Window(view=cam.view, proj=cam.proj, eye=cam.eye, back=cam.back, ortho=cam.ortho, m_per_px=cam.m_per_px / k,
                   res=(W * k, H * k))
        c.az = cam.az
        return c

    # ---- reading a frame
    def object_of(self, part):
        """part indices (any shape) -> object names ('' for none)."""
        names = np.array(self.objects + [''], object)
        return names[np.where(np.asarray(part) >= 0, part, len(self.objects))]

    def object_at(self, F, row, col):
        """the object (and whether its outline) under a pixel of the frame's output grid (click-to-flag) -> dict or None."""
        a = F['aux_ss']
        r, c = int(row * a + a // 2), int(col * a + a // 2)
        if not (0 <= r < F['part'].shape[0] and 0 <= c < F['part'].shape[1]):
            return None
        k = int(F['part'][r, c])
        if k < 0:
            return None
        P = self.prims[k]
        return {'object': P.object, 'mesh': P.mesh, 'part': k, 'hull': bool(F['hull'][r, c]),
                'material': P.look.get('kind'), 'depth': float(F['depth'][r, c])}

    def triangles(self, k):
        """primitive k's triangles on the original surface (the outline off), world Blender frame -> (V (n, 3), T (m, 3))."""
        P = self.prims[k]
        return P.co().astype(np.float64) @ model_.C3, np.asarray(P.index, np.int64).reshape(-1, 3)


def picture_from(img):
    """a resolved frame (H, W, 4: linear premultiplied colour, coverage) -> charkit.qa3d.draw's picture: sRGB and
    straight alpha, 8 bits."""
    al = img[..., 3:4].astype(np.float64)
    rgb = np.where(al > 1e-6, img[..., :3] / np.maximum(al, 1e-6), 0.0)
    s = np.clip(rgb, 0, None)
    s = np.where(s <= 0.0031308, s * 12.92, 1.055 * s ** (1 / 2.4) - 0.055)
    out = np.concatenate([s, al], -1)
    return np.floor(np.clip(out, 0, 1) * 255 + 0.5) / 255.0


def load(path, adapter=None, ss=4):
    """an export -> Frames (one per process and export: cached)."""
    key = (os.path.abspath(path), os.path.getmtime(path), adapter, ss)
    got = _CACHE.get(key)
    if got is None:
        _CACHE.clear()
        got = _CACHE[key] = Frames(model_.load(path), adapter=adapter, ss=ss)
    return got


_CACHE = {}
