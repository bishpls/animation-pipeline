"""Painted textures for charkit characters (docs/CHARKIT.md §2 "paint").

GPT Image paints finished views of the character OVER renders of the 3D model, so each painting is already aligned to
the geometry. The paintings are registered back onto the renders (ECC on silhouette + edges, then a small smoothed
flow), each pixel is trusted by how well its colour agrees with the render (so a part the painter redrew is not
projected onto the wrong surface), and they are projected onto the mesh's UVs from the same calibrated cameras:
visibility from each view's depth and ID passes, weights from facing with soft falloffs at silhouettes, depth/ID edges
and the image border, sampling prefiltered to each texel's footprint, views gain-matched on their overlap and blended
in two bands (so misregistered detail never doubles), unseen texels filled from their 3D neighbours, gutters dilated.
The cel shader then lights that texture: shadow tones are the texture times a warm shade colour (by default the old
material's own shade/lit ratio), so painted detail (skin gradients, blush, hair gradient and strands, cloth detail)
survives into shadow.

What worked, measured on Clawd (charkit/out/paint): the paint-over prompt must forbid restyling (STRICT: "colour the
clumps of image 1"); without it three-quarter views re-volume the hair (edge distance 3.8 px vs 1.5 px after
registration). Surfaces whose features live on other layers (the head skin under decal eyes and mouth) need
project_to_uv(feature_de=...) or painted lashes and a second smile land on the skin. The views and the texel
extraction must use exactly the rendered geometry: kit.add_outline's Solidify moves the visible skin inward.

    make_views(objs, specs, outdir)                    Blender   flat / depth / normal / ID passes + a camera JSON per view
    paint_views(view_dir, refs, style, out_dir)        venv      GPT Image paint-overs (tools/gptimage.py) + registration
    project_to_uv(obj, uv_map, views, size, out_png)   Blender   the projection bake (numpy only) + a coverage map
    apply_painted(obj, texture_png, uv_map, ...)       Blender   textured cel materials: toon3_tex / face_tex (+ hair ring)
    ensure_atlas(objs, uv_map)                         Blender   a paintable UV atlas (Smart UV Project, multi-object)

The demo on Clawd (writes charkit/out/paint/):
    blender -b --factory-startup --python charkit/paint.py -- views
    ~/animation-pipeline/.venv/bin/python charkit/paint.py paint [--only front,back] [--max-calls 4]
    blender -b charkit/out/paint/work/clawd_atlas.blend --python charkit/paint.py -- bake
    ~/animation-pipeline/.venv/bin/python charkit/paint.py board

Conventions: Blender's (metres, Z up, the character faces -Y, her left is +X; a camera looks down its -Z with +Y up).
Image arrays are row 0 = top; pixel (i, j) covers [j, j+1) x [i, i+1), so its centre is at (j + 0.5, i + 0.5). PNG
colours are sRGB. Azimuth is degrees around Z from her front, + toward her left; elevation is degrees up.
Top level imports numpy only, so the module loads both in Blender (numpy, no scipy/PIL) and in the venv.
"""
import json, math, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
TOOLS = os.environ.get('CHARKIT_TOOLS', os.path.expanduser('~/animation-pipeline/tools'))   # gptimage.py, rigkit.py
BG = (0.0, 0.694, 0.251)            # the flat chroma green behind the flat pass (sRGB); the painter is told to keep it
WARM_SHADE = (0.93, 0.78, 0.76)     # texture x this (sRGB-authored, like kit colours) = the shadow tone, when not derived


# ================================================================ small numpy tools (Blender-safe)
def smoothstep(e0, e1, x):
    t = np.clip((np.asarray(x, np.float32) - e0) / max(e1 - e0, 1e-9), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def lin(c):
    """sRGB-authored colour -> linear, the kit's way (x ** 2.2)."""
    return tuple(float(x) ** 2.2 for x in c)


def _box1(a, r, axis):
    if r < 1:
        return a
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(a, pad, mode='edge'), axis=axis, dtype=np.float64)
    n = a.shape[axis]
    hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(c, np.arange(0, n), axis=axis)
    return ((hi - lo) / (2 * r + 1)).astype(np.float32)


def blur(a, sigma):
    """Gaussian-ish blur over the first two axes (three box passes, cumulative sums)."""
    if sigma <= 0:
        return a.astype(np.float32)
    r = max(1, int(round((math.sqrt(4 * sigma * sigma + 1) - 1) / 2)))
    out = a.astype(np.float32)
    for _ in range(3):
        out = _box1(_box1(out, r, 0), r, 1)
    return out


def masked_blur(a, m, sigma):
    """blur of a using only the texels where m (normalised convolution)."""
    m = m.astype(np.float32)
    mm = m[..., None] if a.ndim == 3 else m
    num = blur(a * mm, sigma)
    den = blur(m, sigma)
    den = den[..., None] if a.ndim == 3 else den
    return num / np.maximum(den, 1e-6)


def pushpull(img, w):
    """img (H, W, C) filled where w == 0 from its weighted neighbourhood: a pyramid down (weighted means), then up."""
    img = img.astype(np.float32)
    w = np.clip(w.astype(np.float32), 0, None)

    def rec(c, w):                                  # c premultiplied by w
        H, W = w.shape
        if H <= 2 or W <= 2:
            t = c.reshape(-1, c.shape[-1]).sum(0) / max(float(w.sum()), 1e-8)
            return np.broadcast_to(t, c.shape).astype(np.float32)
        ph, pw = H % 2, W % 2
        c2 = np.pad(c, ((0, ph), (0, pw), (0, 0))); w2 = np.pad(w, ((0, ph), (0, pw)))
        cd = c2[0::2, 0::2] + c2[1::2, 0::2] + c2[0::2, 1::2] + c2[1::2, 1::2]
        wd = w2[0::2, 0::2] + w2[1::2, 0::2] + w2[0::2, 1::2] + w2[1::2, 1::2]
        f = rec(cd, wd)
        up = np.repeat(np.repeat(f, 2, 0), 2, 1)[:H, :W]
        up = blur(up, 1.0)
        a = np.clip(w, 0, 1)[..., None]
        own = c / np.maximum(w, 1e-8)[..., None]
        return np.where(w[..., None] > 0, own * a + up * (1 - a), up).astype(np.float32)
    return rec(img * w[..., None], w)


def _dilate(m):
    o = m.copy()
    o[1:] |= m[:-1]; o[:-1] |= m[1:]; o[:, 1:] |= m[:, :-1]; o[:, :-1] |= m[:, 1:]
    return o


def dist_to(mask, rmax):
    """(approximate) pixel distance to the nearest True pixel of mask, capped at rmax (alternating 4/8-neighbour
    dilations, numpy only)."""
    d = np.full(mask.shape, float(rmax), np.float32)
    cur = mask.astype(bool).copy()
    d[cur] = 0
    for k in range(1, int(rmax) + 1):
        nxt = _dilate(cur)
        if k % 2 == 0:                               # diagonal step on even rings: an octagon, close to Euclidean
            nxt[1:, 1:] |= cur[:-1, :-1]; nxt[:-1, :-1] |= cur[1:, 1:]; nxt[1:, :-1] |= cur[:-1, 1:]; nxt[:-1, 1:] |= cur[1:, :-1]
        d[nxt & ~cur] = k
        cur = nxt
    return d


def bilinear(img, x, y):
    """sample img (H, W, C) at continuous pixel coords where an integer is a pixel centre."""
    H, W = img.shape[:2]
    x = np.clip(x, 0, W - 1); y = np.clip(y, 0, H - 1)
    x0 = np.floor(x).astype(np.int64); y0 = np.floor(y).astype(np.int64)
    x1 = np.minimum(x0 + 1, W - 1); y1 = np.minimum(y0 + 1, H - 1)
    fx = (x - x0).astype(np.float32); fy = (y - y0).astype(np.float32)
    if img.ndim == 3:
        fx = fx[:, None]; fy = fy[:, None]
    return (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x1] * fx * (1 - fy) +
            img[y1, x0] * (1 - fx) * fy + img[y1, x1] * fx * fy)


def resize_nearest(a, H, W):
    ys = ((np.arange(H) + 0.5) * a.shape[0] / H).astype(np.int64)
    xs = ((np.arange(W) + 0.5) * a.shape[1] / W).astype(np.int64)
    return a[ys][:, xs]


def resize_area(a, H, W):
    """box-filtered resize for images (numpy only; integer ratios exact, others via nearest after box blur)."""
    h0, w0 = a.shape[:2]
    if (h0, w0) == (H, W):
        return a
    if h0 % H == 0 and w0 % W == 0:
        fy, fx = h0 // H, w0 // W
        return a.reshape(H, fy, W, fx, *a.shape[2:]).mean((1, 3)).astype(np.float32)
    return resize_nearest(blur(a, 0.5 * max(h0 / H, w0 / W)), H, W)


# ---------------------------------------------------------------- image IO: PIL outside Blender, bpy inside
def _have_pil():
    try:
        import PIL.Image  # noqa: F401
        return True
    except ImportError:
        return False


def read_png(path):
    """-> float32 (H, W, 4) in 0..1, row 0 = top, raw file values (no colour management)."""
    if _have_pil():
        from PIL import Image
        im = Image.open(path)
        a = np.asarray(im.convert('RGBA'))
        return a.astype(np.float32) / 255.0
    import bpy
    img = bpy.data.images.load(path, check_existing=False)
    img.colorspace_settings.name = 'Non-Color'
    W, H = img.size
    a = np.empty(W * H * 4, np.float32)
    img.pixels.foreach_get(a)
    bpy.data.images.remove(img)
    return a.reshape(H, W, 4)[::-1].copy()


def write_png(path, arr):
    """arr (H, W), (H, W, 3) or (H, W, 4), float 0..1 or uint8 -> 8-bit PNG."""
    a = np.asarray(arr)
    if a.dtype != np.uint8:
        a = (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)
    if a.ndim == 2:
        a = np.repeat(a[..., None], 3, 2)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if _have_pil():
        from PIL import Image
        Image.fromarray(a, 'RGBA' if a.shape[2] == 4 else 'RGB').save(path)
        return path
    import bpy
    H, W = a.shape[:2]
    rgba = np.ones((H, W, 4), np.float32)
    rgba[..., :a.shape[2]] = a / 255.0
    img = bpy.data.images.new('_charkit_write', W, H, alpha=True)
    img.colorspace_settings.name = 'Non-Color'
    img.pixels.foreach_set(rgba[::-1].ravel())
    img.filepath_raw = path; img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)
    return path


# ================================================================ cameras
def view_position(spec):
    """camera location for a view spec: target + distance along (azimuth, elevation)."""
    a, e = math.radians(spec.get('azimuth', 0.0)), math.radians(spec.get('elevation', 0.0))
    t = np.asarray(spec['target'], np.float64)
    d = float(spec['distance'])
    return t + d * np.array([math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)])


def _res(spec):
    r = spec.get('resolution', 1024)
    return (int(r), int(r)) if np.isscalar(r) else (int(r[0]), int(r[1]))


def camera_json(cam_obj, spec):
    """Full intrinsics and extrinsics of a Blender camera, plus the pixel-space K a numpy projector needs."""
    import bpy
    cd = cam_obj.data
    W, H = _res(spec)
    fit = cd.sensor_fit
    if fit == 'AUTO':
        fit = 'HORIZONTAL' if W >= H else 'VERTICAL'
    fit_px = W if fit == 'HORIZONTAL' else H
    sensor = cd.sensor_width if (cd.sensor_fit == 'AUTO' or fit == 'HORIZONTAL') else cd.sensor_height
    Mw = np.array(cam_obj.matrix_world, np.float64)
    if cd.type == 'ORTHO':
        f = fit_px / cd.ortho_scale                      # pixels per metre
    else:
        f = cd.lens / sensor * fit_px                    # pixels per unit of x/z
    K = [[f, 0, W / 2 - cd.shift_x * fit_px], [0, f, H / 2 + cd.shift_y * fit_px], [0, 0, 1]]
    dg = bpy.context.evaluated_depsgraph_get()
    Pm = cam_obj.calc_matrix_camera(dg, x=W, y=H, scale_x=1.0, scale_y=1.0)
    return {
        'name': spec['name'], 'type': cd.type, 'resolution': [W, H],
        'lens_mm': cd.lens, 'sensor_width_mm': cd.sensor_width, 'sensor_height_mm': cd.sensor_height,
        'sensor_fit': cd.sensor_fit, 'fit_axis': fit, 'ortho_scale': cd.ortho_scale,
        'shift_x': cd.shift_x, 'shift_y': cd.shift_y, 'clip_start': cd.clip_start, 'clip_end': cd.clip_end,
        'matrix_world': Mw.tolist(), 'world_to_camera': np.linalg.inv(Mw).tolist(),
        'location': list(cam_obj.matrix_world.translation), 'rotation_quaternion': list(cam_obj.matrix_world.to_quaternion()),
        'projection': [list(r) for r in Pm],
        'K': K,
        'azimuth': spec.get('azimuth', 0.0), 'elevation': spec.get('elevation', 0.0), 'distance': spec['distance'],
        'target': list(map(float, spec['target'])),
        'conventions': ('Blender camera: looks down local -Z, +Y up; matrix_world is camera->world. K is pixel space, '
                        'x right, y down, pixel centres at +0.5: persp px = K00*xc/(-zc) + K02, py = -K11*yc/(-zc) + K12; '
                        'ortho px = K00*xc + K02, py = -K11*yc + K12 (xc, yc, zc camera space). depth = -zc (view Z, '
                        'metres), inf on the background.'),
    }


def project(cam, X):
    """world points X (M, 3) -> (px, py, depth, to_camera (M, 3) unit) for a camera JSON dict."""
    W2C = np.asarray(cam['world_to_camera'], np.float64)
    Xc = X.astype(np.float64) @ W2C[:3, :3].T + W2C[:3, 3]
    z = -Xc[:, 2]
    K = cam['K']
    if cam['type'] == 'ORTHO':
        px = K[0][0] * Xc[:, 0] + K[0][2]
        py = -K[1][1] * Xc[:, 1] + K[1][2]
        fwd = -np.asarray(cam['matrix_world'])[:3, 2]
        tocam = np.broadcast_to(-fwd, X.shape).astype(np.float32)
    else:
        zz = np.where(np.abs(z) < 1e-9, 1e-9, z)
        px = K[0][0] * Xc[:, 0] / zz + K[0][2]
        py = -K[1][1] * Xc[:, 1] / zz + K[1][2]
        loc = np.asarray(cam['matrix_world'])[:3, 3]
        tocam = loc[None] - X
        tocam = (tocam / np.linalg.norm(tocam, axis=1, keepdims=True)).astype(np.float32)
    return px, py, z.astype(np.float32), tocam


# ================================================================ Blender: atlases, meshes, views
def ensure_atlas(objs, uv_map='paint', angle=66.0, margin=0.004, force=False, pack=True):
    """Give objs a shared, non-overlapping UV atlas named uv_map (Smart UV Project, then all objects' islands packed
    together into one 0..1 square with Blender's concave packer), leaving each object's active/render UV as it was.
    Deterministic for the same meshes."""
    import bpy
    objs = [o for o in objs if o.type == 'MESH']
    if not force and all(uv_map in o.data.uv_layers for o in objs):
        return objs
    vl = bpy.context.view_layer
    prev_active = vl.objects.active
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for o in vl.objects:
        o.select_set(False)
    keep = {}
    for o in objs:
        lay = o.data.uv_layers
        keep[o] = (lay.active_index, [l.active_render for l in lay], o.hide_viewport, o.hide_get())
        o.hide_viewport = False; o.hide_set(False)
        uvl = lay.get(uv_map) or lay.new(name=uv_map)
        lay.active = uvl
        o.select_set(True)
    vl.objects.active = objs[0]
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=margin, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    if pack:
        bpy.ops.uv.select_all(action='SELECT')
        try:
            bpy.ops.uv.pack_islands(rotate=True, scale=True, margin_method='FRACTION', margin=margin, shape_method='CONCAVE')
        except TypeError:
            bpy.ops.uv.pack_islands(rotate=True, margin=margin)
    bpy.ops.object.mode_set(mode='OBJECT')
    for o, (ai, ren, hv, hs) in keep.items():
        lay = o.data.uv_layers
        lay.active_index = ai if ai < len(ren) else 0
        for l, r in zip(lay, ren + [False] * len(lay)):
            l.active_render = r
        o.hide_viewport = hv; o.hide_set(hs)
        o.select_set(False)
    vl.objects.active = prev_active
    return objs


def mesh_arrays(obj, uv_map):
    """The evaluated mesh as the renderer sees it (subdivision at render levels, modifiers as they render), minus the
    faces that carry an outline material: per triangle its UVs (T, 3, 2), world positions (T, 3, 3) and world corner
    normals (T, 3, 3). Keeping the outline modifier matters: kit.add_outline's Solidify (offset 1, negative thickness)
    moves the rendered skin inward by the outline width and leaves the hull at the modelled surface, so the surface a
    camera sees is not the modelled one. Its normals may come out flipped; project_to_uv uses |n . v|."""
    import bpy
    saved = []
    for md in obj.modifiers:
        if md.type == 'SUBSURF' and md.levels != md.render_levels:
            saved.append((md, 'levels', md.levels)); md.levels = md.render_levels
        if md.show_viewport != md.show_render:
            saved.append((md, 'show_viewport', md.show_viewport)); md.show_viewport = md.show_render
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    try:
        me.calc_loop_triangles()
        nv, nl, nt = len(me.vertices), len(me.loops), len(me.loop_triangles)
        co = np.empty(nv * 3, np.float32); me.vertices.foreach_get('co', co)
        tl = np.empty(nt * 3, np.int32); me.loop_triangles.foreach_get('loops', tl)
        mi = np.empty(nt, np.int32); me.loop_triangles.foreach_get('material_index', mi)
        skip = [i for i, m in enumerate(me.materials) if m is not None and m.name.startswith('outline')]
        lv = np.empty(nl, np.int32); me.loops.foreach_get('vertex_index', lv)
        cn = np.empty(nl * 3, np.float32); me.corner_normals.foreach_get('vector', cn)
        if uv_map not in me.uv_layers:
            raise KeyError(f'{obj.name} has no UV map {uv_map!r} (ensure_atlas first)')
        uv = np.empty(nl * 2, np.float32); me.uv_layers[uv_map].data.foreach_get('uv', uv)
        Mw = np.array(ev.matrix_world, np.float64)
    finally:
        ev.to_mesh_clear()
        for md, attr, v in saved:
            setattr(md, attr, v)
        dg.update()
    P = co.reshape(-1, 3) @ Mw[:3, :3].T + Mw[:3, 3]
    Nm = np.linalg.inv(Mw[:3, :3]).T
    N = cn.reshape(-1, 3) @ Nm.T
    N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
    tl = tl.reshape(-1, 3)[~np.isin(mi, skip)]
    return {'uv': uv.reshape(-1, 2)[tl], 'P': P[lv[tl]].astype(np.float32), 'N': N[tl].astype(np.float32)}


def _nodes(m):
    if m.node_tree is None:
        m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    return nt


def _material_alpha_copy(m, chain):
    """A copy of a see-through material (decals, drawn eyes) that emits chain(nt) instead of its colour and keeps a
    hard-cut version of its alpha, so a data pass sees through it exactly where a render does."""
    c = m.copy(); c.name = f'_paint_ovr_{m.name}'
    nt = c.node_tree
    sock = chain(nt)
    for n in list(nt.nodes):
        if n.type == 'EMISSION':
            for l in list(n.inputs['Color'].links):
                nt.links.remove(l)
            nt.links.new(sock, n.inputs['Color'])
        if n.type == 'MIX_SHADER' and n.inputs['Fac'].links:
            src = n.inputs['Fac'].links[0].from_socket
            gt = nt.nodes.new('ShaderNodeMath'); gt.operation = 'GREATER_THAN'; gt.inputs[1].default_value = 0.5
            nt.links.new(src, gt.inputs[0]); nt.links.new(gt.outputs[0], n.inputs['Fac'])
    c.surface_render_method = 'DITHERED'
    return c


def _is_see_through(m):
    return m and m.node_tree and any(n.type == 'BSDF_TRANSPARENT' for n in m.node_tree.nodes)


DEPTH_SCALE = 32.0     # depth pass: R = floor(z * 32), B = fract(z * 32): exact in EEVEE's half floats to ~15 um, z < 64 m


def _data_chain(nt):
    """emission for the data passes: mode 0 -> (floor(32 z), object index, fract(32 z)) with z the view Z depth (EEVEE
    stores half floats and clamps negative emission, so the depth is split to stay exact); mode 1 -> world normal."""
    N, L = nt.nodes.new, nt.links.new
    geo = N('ShaderNodeNewGeometry'); cd = N('ShaderNodeCameraData'); oi = N('ShaderNodeObjectInfo')
    mode = N('ShaderNodeValue'); mode.name = 'paint_mode'
    zs = N('ShaderNodeMath'); zs.operation = 'MULTIPLY'; zs.inputs[1].default_value = DEPTH_SCALE
    L(cd.outputs['View Z Depth'], zs.inputs[0])
    fl = N('ShaderNodeMath'); fl.operation = 'FLOOR'; L(zs.outputs[0], fl.inputs[0])
    fr = N('ShaderNodeMath'); fr.operation = 'FRACT'; L(zs.outputs[0], fr.inputs[0])
    cmb = N('ShaderNodeCombineXYZ'); L(fl.outputs[0], cmb.inputs[0]); L(oi.outputs['Object Index'], cmb.inputs[1])
    L(fr.outputs[0], cmb.inputs[2])
    inv = N('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0; L(mode.outputs[0], inv.inputs[1])
    a = N('ShaderNodeVectorMath'); a.operation = 'SCALE'; L(cmb.outputs[0], a.inputs[0]); L(inv.outputs[0], a.inputs['Scale'])
    b = N('ShaderNodeVectorMath'); b.operation = 'SCALE'; L(geo.outputs['Normal'], b.inputs[0]); L(mode.outputs[0], b.inputs['Scale'])
    s = N('ShaderNodeVectorMath'); s.operation = 'ADD'; L(a.outputs[0], s.inputs[0]); L(b.outputs[0], s.inputs[1])
    return s.outputs[0]


def _ldir_materials():
    import bpy
    return [m for m in bpy.data.materials if m.node_tree and 'ldir' in m.node_tree.nodes]


def _is_sdf_face(m):
    return any(n.type == 'TEX_IMAGE' and n.image and 'sdf' in n.image.name.lower() for n in m.node_tree.nodes)


def set_light_all(d, face_forward=None):
    """Point every cel material's art-directed light ('ldir' node) along d (world, toward the light); SDF face
    materials get face_forward instead when given (the flat pass lights the face from its front, fully lit)."""
    v = np.asarray(d, np.float64); v = v / np.linalg.norm(v)
    for m in _ldir_materials():
        n = m.node_tree.nodes['ldir']
        u = v
        if face_forward is not None and _is_sdf_face(m):
            u = np.asarray(face_forward, np.float64); u = u / np.linalg.norm(u)
        for i in range(3):
            n.inputs[i].default_value = float(u[i])


def _get_lights():
    return {m.name: tuple(m.node_tree.nodes['ldir'].inputs[i].default_value for i in range(3)) for m in _ldir_materials()}


def _set_lights(saved):
    import bpy
    for name, v in saved.items():
        m = bpy.data.materials.get(name)
        if m:
            for i in range(3):
                m.node_tree.nodes['ldir'].inputs[i].default_value = v[i]


def _place_camera(cam, spec):
    from mathutils import Vector
    eye = Vector(view_position(spec)); tgt = Vector(spec['target'])
    cam.location = eye
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = (tgt - eye).normalized().to_track_quat('-Z', 'Y')
    cd = cam.data
    if spec.get('ortho_scale'):
        cd.type = 'ORTHO'; cd.ortho_scale = float(spec['ortho_scale'])
    else:
        cd.type = 'PERSP'; cd.lens = float(spec.get('lens', 50.0))
    cd.sensor_fit = 'AUTO'; cd.sensor_width = 36.0; cd.shift_x = cd.shift_y = 0.0
    cd.clip_start = 0.01; cd.clip_end = 100.0
    import bpy
    bpy.context.view_layer.update()


def _read_exr(path):
    import bpy
    img = bpy.data.images.load(path, check_existing=False)
    W, H = img.size
    a = np.empty(W * H * 4, np.float32)
    img.pixels.foreach_get(a)
    bpy.data.images.remove(img)
    return a.reshape(H, W, 4)[::-1].copy()


def make_views(objs, specs, outdir, light='camera', bg=BG, samples=16, face_forward=(0.0, -1.0, 0.25)):
    """Render each view spec {name, azimuth, elevation, distance, lens | ortho_scale, target, resolution} as:
      <name>_flat.png     the materials as they are (outlines on), lit from the camera ('camera'; the SDF face from its
                          front) so it is nearly all lit tone, on a flat green background: the image the painter edits
      <name>_depth.npy    view Z depth (metres, float32, inf on the background) + a _depth.png preview
      <name>_normal.npy   world normals (float16) + a _normal.png preview (0.5 + 0.5 n)
      <name>_id.npy       object ID (uint16, 0 = background; see views.json 'ids') + an _id.png preview
      <name>_cam.json     camera intrinsics and extrinsics (camera_json)
    Data passes are material-override renders (EEVEE, 1 sample, no pixel filter, float EXR) of exactly the rendered
    geometry: the outline hulls stay (culled as in the render: kit's outline Solidify moves the visible skin inward, so
    turning it off would change what occludes what); see-through materials (decals, drawn eyes) keep a hard-cut alpha
    so the passes see through them where renders do.
    objs: the meshes to render (others are hidden meanwhile); None = every mesh that renders."""
    import bpy
    os.makedirs(outdir, exist_ok=True)
    sc = bpy.context.scene
    meshes = [o for o in (objs if objs is not None else sc.objects) if o.type == 'MESH']
    shown = sorted([o for o in meshes if not o.hide_render], key=lambda o: o.name)
    others = [o for o in sc.objects if o.type == 'MESH' and o not in meshes and not o.hide_render]
    ids = {o.name: i + 1 for i, o in enumerate(shown)}
    r, ev = sc.render, sc.eevee
    state = dict(engine=r.engine, rx=r.resolution_x, ry=r.resolution_y, pct=r.resolution_percentage,
                 transparent=r.film_transparent, filt=r.filter_size, taa=ev.taa_render_samples,
                 fmt=r.image_settings.file_format, mode=r.image_settings.color_mode, depth=r.image_settings.color_depth,
                 vt=sc.view_settings.view_transform, look=sc.view_settings.look, cam=sc.camera, world=sc.world,
                 path=r.filepath, pidx={o.name: o.pass_index for o in shown})
    for o in others:
        o.hide_render = True
    for o in shown:
        o.pass_index = ids[o.name]
    cd = bpy.data.cameras.new('_paint_cam')
    cam = bpy.data.objects.new('_paint_cam', cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    world = bpy.data.worlds.new('_paint_world'); sc.world = world
    if world.node_tree is None:
        world.use_nodes = True
    bgn = world.node_tree.nodes.get('Background') or world.node_tree.nodes.new('ShaderNodeBackground')
    bgn.inputs['Strength'].default_value = 1.0
    r.engine = 'BLENDER_EEVEE'; r.resolution_percentage = 100
    sc.view_settings.view_transform = 'Standard'; sc.view_settings.look = 'None'
    lights = _get_lights()
    rims, slots, mods, ovr_mats = {}, {}, [], []
    try:
        # ---- flat pass: the materials as they are, lit from the camera, rim lights off
        for m in bpy.data.materials:
            if m.node_tree and 'rim_amt' in m.node_tree.nodes:
                rims[m.name] = m.node_tree.nodes['rim_amt'].inputs[1].default_value
                m.node_tree.nodes['rim_amt'].inputs[1].default_value = 0.0
        bgn.inputs['Color'].default_value = (*lin(bg), 1)
        r.film_transparent = False; r.filter_size = 1.5; ev.taa_render_samples = samples
        r.image_settings.file_format = 'PNG'; r.image_settings.color_mode = 'RGB'; r.image_settings.color_depth = '8'
        for spec in specs:
            _place_camera(cam, spec)
            r.resolution_x, r.resolution_y = _res(spec)
            if light == 'camera':
                d = view_position(spec) - np.asarray(spec['target'])
                set_light_all(d, face_forward)
            r.filepath = os.path.join(outdir, f"{spec['name']}_flat.png")
            bpy.ops.render.render(write_still=True)
        _set_lights(lights)
        # ---- data passes: overrides
        ovr = bpy.data.materials.new('_paint_ovr')
        _data_chain(_nodes(ovr))
        out = ovr.node_tree.nodes.new('ShaderNodeOutputMaterial'); em = ovr.node_tree.nodes.new('ShaderNodeEmission')
        src = next(n for n in ovr.node_tree.nodes if n.type == 'VECT_MATH' and n.operation == 'ADD').outputs[0]
        ovr.node_tree.links.new(src, em.inputs['Color']); ovr.node_tree.links.new(em.outputs[0], out.inputs['Surface'])
        ovr_cull = ovr.copy(); ovr_cull.name = '_paint_ovr_cull'; ovr_cull.use_backface_culling = True
        ovr_mats += [ovr, ovr_cull]
        copies = {}
        for o in shown:
            slots[o.name] = list(o.data.materials)
            for i, m in enumerate(o.data.materials):
                if m is not None and m.name.startswith('outline'):
                    o.data.materials[i] = ovr_cull            # the inverted hull, culled as in the render
                    continue
                if _is_see_through(m):
                    if m.name not in copies:
                        copies[m.name] = _material_alpha_copy(m, _data_chain); ovr_mats.append(copies[m.name])
                    o.data.materials[i] = copies[m.name]
                else:
                    o.data.materials[i] = ovr
        bgn.inputs['Color'].default_value = (0, 0, 0, 1)
        r.film_transparent = True; r.filter_size = 0.0; ev.taa_render_samples = 1
        r.image_settings.file_format = 'OPEN_EXR'; r.image_settings.color_mode = 'RGBA'; r.image_settings.color_depth = '32'
        views = []
        for spec in specs:
            name = spec['name']
            _place_camera(cam, spec)
            W, H = _res(spec)
            r.resolution_x, r.resolution_y = W, H
            res = {}
            for mode in (0, 1):
                for m in ovr_mats:
                    m.node_tree.nodes['paint_mode'].outputs[0].default_value = float(mode)
                p = os.path.join(outdir, f'_{name}_pass{mode}.exr')
                r.filepath = p
                bpy.ops.render.render(write_still=True)
                res[mode] = _read_exr(p)
                os.remove(p)
            a0, a1 = res[0], res[1]
            fg = (a0[..., 3] > 0.5) & (np.round(a0[..., 1]) > 0)
            depth = np.where(fg, (a0[..., 0] + a0[..., 2]) / DEPTH_SCALE, np.inf).astype(np.float32)
            idm = np.where(fg, np.round(a0[..., 1]), 0).astype(np.uint16)
            nrm = np.where(fg[..., None], a1[..., :3], 0).astype(np.float16)
            np.save(os.path.join(outdir, f'{name}_depth.npy'), depth)
            np.save(os.path.join(outdir, f'{name}_id.npy'), idm)
            np.save(os.path.join(outdir, f'{name}_normal.npy'), nrm)
            dv = depth[fg]
            prev = np.zeros(depth.shape, np.float32)
            if dv.size:
                lo_, hi_ = np.percentile(dv, 1), np.percentile(dv, 60)
                prev[fg] = 1 - np.clip((depth[fg] - lo_) / max(hi_ - lo_, 1e-6), 0, 1) * 0.85
            write_png(os.path.join(outdir, f'{name}_depth.png'), prev)
            write_png(os.path.join(outdir, f'{name}_normal.png'), np.where(fg[..., None], 0.5 + 0.5 * nrm.astype(np.float32), 0))
            pal = np.random.RandomState(7).rand(max(ids.values()) + 1, 3).astype(np.float32) * 0.8 + 0.2
            pal[0] = 0
            write_png(os.path.join(outdir, f'{name}_id.png'), pal[idm])
            cj = camera_json(cam, spec)
            cj['ids'] = ids
            cj['files'] = {k: f'{name}_{k}' + ('.png' if k == 'flat' else '.npy') for k in ('flat', 'depth', 'normal', 'id')}
            # self-check: our projector against Blender's own, on the target and a few offsets
            from bpy_extras.object_utils import world_to_camera_view
            from mathutils import Vector
            errs = []
            for off in ((0, 0, 0), (0.05, 0.02, 0.03), (-0.04, -0.03, -0.05)):
                P = np.asarray(spec['target']) + np.asarray(off)
                px, py, z, _ = project(cj, P[None])
                v = world_to_camera_view(sc, cam, Vector(P))
                errs.append(max(abs(px[0] - v.x * W), abs(py[0] - (1 - v.y) * H), abs(z[0] - v.z)))
            cj['projector_check_px'] = float(max(errs))
            json.dump(cj, open(os.path.join(outdir, f'{name}_cam.json'), 'w'), indent=1)
            views.append({'name': name, 'spec': {k: (list(v) if isinstance(v, (tuple, list, np.ndarray)) else v) for k, v in spec.items()}})
            print(f'[paint] view {name}: {W}x{H}, projector check {cj["projector_check_px"]:.4f} px')
        json.dump({'views': views, 'ids': ids, 'bg': list(bg)}, open(os.path.join(outdir, 'views.json'), 'w'), indent=1)
    finally:
        _set_lights(lights)
        for name, v in rims.items():
            bpy.data.materials[name].node_tree.nodes['rim_amt'].inputs[1].default_value = v
        for o in shown:
            for i, m in enumerate(slots.get(o.name, [])):
                o.data.materials[i] = m
        for md in mods:
            md.show_render = True
        for m in ovr_mats:
            bpy.data.materials.remove(m)
        for o in others:
            o.hide_render = False
        for o in shown:
            o.pass_index = state['pidx'][o.name]
        bpy.data.objects.remove(cam); bpy.data.cameras.remove(cd)
        sc.world = state['world']; bpy.data.worlds.remove(world)
        r.engine = state['engine']; r.resolution_x, r.resolution_y = state['rx'], state['ry']
        r.resolution_percentage = state['pct']; r.film_transparent = state['transparent']; r.filter_size = state['filt']
        ev.taa_render_samples = state['taa']; r.image_settings.file_format = state['fmt']
        r.image_settings.color_mode = state['mode']; r.image_settings.color_depth = state['depth']
        sc.view_settings.view_transform = state['vt']; sc.view_settings.look = state['look']
        sc.camera = state['cam']; r.filepath = state['path']
    return os.path.join(outdir, 'views.json')


def render_stills(specs, outdir, prefix='', light=None, samples=32, bg=(0.93, 0.92, 0.95)):
    """Plain renders of the scene as it is (outlines on) from view specs, on a flat bg: for review boards. light: None
    keeps each material's light; 'camera' lights from each camera; or a world direction."""
    import bpy
    sc = bpy.context.scene
    r = sc.render
    keep = (sc.camera, r.resolution_x, r.resolution_y, r.resolution_percentage, r.filepath, r.image_settings.color_mode,
            r.film_transparent, sc.world, r.engine, sc.view_settings.view_transform)
    cd = bpy.data.cameras.new('_still_cam'); cam = bpy.data.objects.new('_still_cam', cd)
    sc.collection.objects.link(cam); sc.camera = cam
    world = bpy.data.worlds.new('_still_world'); sc.world = world
    if world.node_tree is None:
        world.use_nodes = True
    bgn = world.node_tree.nodes.get('Background') or world.node_tree.nodes.new('ShaderNodeBackground')
    bgn.inputs['Color'].default_value = (*lin(bg), 1)
    r.engine = 'BLENDER_EEVEE'; sc.view_settings.view_transform = 'Standard'
    r.image_settings.file_format = 'PNG'; r.image_settings.color_depth = '8'
    lights = _get_lights()
    r.resolution_percentage = 100; r.image_settings.color_mode = 'RGB'; r.film_transparent = False
    sc.eevee.taa_render_samples = samples
    out = []
    try:
        for spec in specs:
            _place_camera(cam, spec)
            r.resolution_x, r.resolution_y = _res(spec)
            if light == 'camera':
                set_light_all(view_position(spec) - np.asarray(spec['target']), (0, -1, 0.25))
            elif light is not None:
                set_light_all(light)
            r.filepath = os.path.join(outdir, f"{prefix}{spec['name']}.png")
            bpy.ops.render.render(write_still=True)
            out.append(r.filepath)
    finally:
        _set_lights(lights)
        bpy.data.objects.remove(cam); bpy.data.cameras.remove(cd)
        (sc.camera, r.resolution_x, r.resolution_y, r.resolution_percentage, r.filepath, r.image_settings.color_mode,
         r.film_transparent, sc.world, r.engine, sc.view_settings.view_transform) = keep
        bpy.data.worlds.remove(world)
    return out


# ================================================================ paint-overs (venv: GPT Image + registration)
PROMPT = (
    "Image 1 is a 3D render of an anime character, {view}. The other images are the character's reference art. "
    "Repaint image 1 as a finished HoYoverse-style (Genshin Impact, Honkai: Star Rail) anime illustration of the "
    "character in the reference: the same character, face, hair, outfit and colours as the reference, drawn in its "
    "line and colour style. Keep every silhouette, position and proportion of image 1 exactly: the same camera and "
    "framing, every hair clump, bun, clip, the face and the eyes exactly where and as big as they are in image 1; "
    "paint inside the shapes of image 1, add nothing outside them, move and resize nothing. "
    "Flat, even lighting like a colour model sheet: no cast shadows, no light side or dark side, no rim light, no "
    "shading from a light direction (lighting is added later by a shader). "
    "Put the detail into the colours instead: {style} "
    "Keep the flat green background of image 1 exactly as it is, edge to edge.")
STYLE = ("soft warm skin with a gentle gradient toward the cheeks, a light blush on the cheeks, a faint peach tint at "
         "the nose tip and the chin; a soft lid shadow along the top of each eye white; hair with a colour gradient "
         "from a slightly deeper root to lighter, warmer tips and fine painted strand lines that follow each clump; "
         "thin warm-brown line art at part edges; clean painterly anime rendering.")
STRICT = (" Treat image 1 like line art to colour: every hair lock you paint is one of the clumps of image 1 with the "
          "same outline, and its strands run inside that clump, along it; do not restyle the hair, add volume, or "
          "draw locks, wisps or gaps that image 1 does not have.")


def describe_view(az, el=0.0):
    a = ((az + 180) % 360) - 180
    if abs(a) < 20:
        s = 'seen from the front'
    elif abs(a) > 160:
        s = 'seen from directly behind (the back of her head, her face hidden)'
    elif abs(a) < 70:
        s = f"in a three-quarter view turned to show her {'left' if a > 0 else 'right'} side"
    elif abs(a) <= 110:
        s = f"in profile, seen from her {'left' if a > 0 else 'right'}"
    else:
        s = f"in a three-quarter back view from her {'left' if a > 0 else 'right'}"
    if el > 15:
        s += ', seen from a little above'
    return s + ', a close-up of her head and shoulders'


def key_alpha(rgb, bg=BG):
    """1 on the character, 0 on the flat background: distance from the background colour (plus the chroma tool's
    greenness test), softened by a pixel."""
    rgb = rgb[..., :3].astype(np.float32)
    d = np.linalg.norm(rgb - np.asarray(bg, np.float32), axis=-1)
    g = rgb[..., 1] - np.maximum(rgb[..., 0], rgb[..., 2])
    a = np.maximum(smoothstep(0.10, 0.28, d), 1 - smoothstep(0.12, 0.38, g))
    return np.clip(a, 0, 1).astype(np.float32)


def _features(rgb, sil):
    """the image registration looks at: the silhouette plus normalised edge strength, both softened."""
    import cv2
    L = (rgb[..., :3] @ np.float32([.299, .587, .114])).astype(np.float32)
    Lb = cv2.GaussianBlur(L, (0, 0), 1.2)
    g = np.hypot(cv2.Sobel(Lb, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(Lb, cv2.CV_32F, 0, 1, ksize=3))
    inside = sil > 0.5
    k = np.percentile(g[inside], 97) if inside.any() else 1.0
    g = np.clip(g / max(k, 1e-6), 0, 1) * cv2.dilate(inside.astype(np.uint8), np.ones((5, 5), np.uint8))
    F = 0.5 * cv2.GaussianBlur(sil.astype(np.float32), (0, 0), 2.0) + 0.5 * cv2.GaussianBlur(g, (0, 0), 1.2)
    return F.astype(np.float32), g > 0.35


def _metrics(F_r, E_r, sil_r, F_p, E_p, sil_p, mask):
    import cv2
    sys.path.insert(0, TOOLS)
    import rigkit
    rgba = lambda F: np.dstack([np.repeat((np.clip(F, 0, 1) * 255)[..., None], 3, 2), np.full(F.shape, 255)]).astype(np.uint8)
    a, b = sil_r > 0.5, sil_p > 0.5
    iou = float((a & b).sum() / max((a | b).sum(), 1))
    dp = cv2.distanceTransform((~E_p).astype(np.uint8), cv2.DIST_L2, 3)
    dr = cv2.distanceTransform((~E_r).astype(np.uint8), cv2.DIST_L2, 3)
    ch = 0.5 * (np.minimum(dp[E_r], 20).mean() + np.minimum(dr[E_p], 20).mean()) if E_r.any() and E_p.any() else 99.0
    return {'residual': round(rigkit.residual(rgba(F_p), rgba(F_r), mask), 3), 'silhouette_iou': round(iou, 4),
            'edge_chamfer_px': round(float(ch), 3)}


def trust_map(flat, painting, sigma=3.0, de=(28.0, 44.0)):
    """How far each painted pixel can be trusted to belong to the surface the render shows there: 1 - smoothstep of
    the CIELAB distance between the render and the painting, both blurred by sigma px. The blur ignores thin painted
    detail (strands, line art, blush); what it catches is the painter redrawing a part (hair painted across a gap
    where the model shows forehead, skin where the model has a clump)."""
    import cv2
    lab = lambda im: cv2.cvtColor(cv2.GaussianBlur(np.ascontiguousarray(im[..., :3], np.float32), (0, 0), sigma), cv2.COLOR_RGB2Lab)
    dE = np.linalg.norm(lab(flat) - lab(painting), axis=2)
    return (1 - smoothstep(de[0], de[1], dE)).astype(np.float32), dE


def register_painting(painting_png, view_dir, name, out_png, bg=BG, local=True, max_flow_px=6.0, trust=True):
    """Align a painting back onto its render: ECC (affine, coarse to fine; rigkit.register) on silhouette + edge
    features, then (local=True) a small, heavily smoothed optical-flow correction for parts the painter nudged,
    capped at max_flow_px and kept only if it lowers the edge distance. Writes out_png as RGBA, alpha = the painting's
    keyed silhouette x trust_map (its agreement with the render; project_to_uv weights by it), plus <name>_check.png
    (render edges in cyan over the aligned painting) and <name>_trust.png; returns the residuals."""
    import cv2
    sys.path.insert(0, TOOLS)
    import rigkit
    flat = read_png(os.path.join(view_dir, f'{name}_flat.png'))[..., :3]
    ID = np.load(os.path.join(view_dir, f'{name}_id.npy'))
    H, W = ID.shape
    P = read_png(painting_png)[..., :3]
    if P.shape[:2] != (H, W):
        P = cv2.resize(P, (W, H), interpolation=cv2.INTER_AREA)
    sil_r = (ID > 0).astype(np.float32)
    a_p = key_alpha(P, bg)
    F_r, E_r = _features(flat, sil_r)
    F_p, E_p = _features(P, a_p)
    mask = cv2.dilate(((sil_r > 0.5) | (a_p > 0.5)).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))) > 0
    rep = {'before': _metrics(F_r, E_r, sil_r, F_p, E_p, a_p, mask)}
    rgba = lambda F: np.dstack([np.repeat((np.clip(F, 0, 1) * 255)[..., None], 3, 2), np.full(F.shape, 255)]).astype(np.uint8)
    _, warp = rigkit.register(rgba(F_p), rgba(F_r), mask)
    wa = lambda im, bv: cv2.warpAffine(im, warp, (W, H), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                                       borderMode=cv2.BORDER_CONSTANT, borderValue=bv)
    P_al = wa(P, tuple(float(x) for x in bg)); a_al = wa(a_p, 0.0)
    F_al, E_al = _features(P_al, a_al)
    rep['affine'] = [[round(float(x), 5) for x in row] for row in warp]
    rep['after_ecc'] = _metrics(F_r, E_r, sil_r, F_al, E_al, a_al, mask)
    rep['local'] = False
    if local:
        dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
        u8 = lambda F: (np.clip(F, 0, 1) * 255).astype(np.uint8)
        flow = dis.calc(u8(F_r), u8(F_al), None)                     # render pixel -> where it sits in the painting
        wm = cv2.GaussianBlur(mask.astype(np.float32), (0, 0), 3)
        fl = np.dstack([cv2.GaussianBlur(flow[..., c] * wm, (0, 0), 14) for c in range(2)]) / \
            np.maximum(cv2.GaussianBlur(wm, (0, 0), 14), 1e-3)[..., None]
        mag = np.linalg.norm(fl, axis=2, keepdims=True)
        fl = fl * np.minimum(1.0, max_flow_px / np.maximum(mag, 1e-6))
        gx, gy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
        mx, my = gx + fl[..., 0], gy + fl[..., 1]
        P_lo = cv2.remap(P_al, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=tuple(float(x) for x in bg))
        a_lo = cv2.remap(a_al, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0.0)
        F_lo, E_lo = _features(P_lo, a_lo)
        m_lo = _metrics(F_r, E_r, sil_r, F_lo, E_lo, a_lo, mask)
        rep['after_local'] = m_lo
        rep['flow_px_mean'] = round(float(np.linalg.norm(fl, axis=2)[mask].mean()), 3)
        if m_lo['edge_chamfer_px'] < rep['after_ecc']['edge_chamfer_px'] - 0.02:
            P_al, a_al, rep['local'] = P_lo, a_lo, True
    rep['final'] = rep['after_local'] if rep['local'] else rep['after_ecc']
    if trust:
        tr, dE = trust_map(flat, P_al)
        inside = (sil_r > 0.5) & (a_al > 0.5)
        rep['trust'] = {'rejected_frac': round(float((tr[inside] < 0.5).mean()), 4),
                        'median_dE': round(float(np.median(dE[inside])), 2)}
        write_png(out_png.replace('.png', '_trust.png'), tr * (sil_r > 0.5))
        a_al = a_al * tr
    write_png(out_png, np.dstack([P_al, a_al]))
    chk = P_al.copy()
    chk[E_r] = chk[E_r] * 0.3 + np.float32([0, 1, 1]) * 0.7
    write_png(out_png.replace('.png', '_check.png'), chk)
    json.dump(rep, open(out_png.replace('.png', '_reg.json'), 'w'), indent=1)
    return rep


def paint_views(view_dir, reference_images, style_prompt=None, out_dir=None, views=None, model='gpt-image-2.5-sunburst',
                quality='high', max_calls=8, force=False, local=True, refs_per_view=None):
    """For each view in view_dir/views.json: GPT Image repaints the flat render (the image to edit, first) with the
    reference images, then the painting is registered back onto the render. A view whose <name>_raw.png already
    exists is not repainted unless force (each call costs about $0.10-0.20; max_calls guards the run).
    refs_per_view: {view name: [extra reference images first]} (e.g. the matching drawn three-quarter).
    Writes out_dir/<name>_raw.png (the painting), <name>_paint.png (registered, RGBA), _check.png, _reg.json, and
    paint.json (a summary with the number of calls made)."""
    sys.path.insert(0, TOOLS)
    import gptimage
    out_dir = out_dir or os.path.join(os.path.dirname(os.path.abspath(view_dir)), 'paint')
    os.makedirs(out_dir, exist_ok=True)
    meta = json.load(open(os.path.join(view_dir, 'views.json')))
    bg = tuple(meta.get('bg', BG))
    calls, results = 0, {}
    for v in meta['views']:
        name, spec = v['name'], v['spec']
        if views and name not in views:
            continue
        raw = os.path.join(out_dir, f'{name}_raw.png')
        if force or not os.path.exists(raw):
            if calls >= max_calls:
                raise RuntimeError(f'paint_views: max_calls={max_calls} reached before {name}')
            W, H = _res(spec)
            size = f'{W // 16 * 16}x{H // 16 * 16}'
            prompt = PROMPT.format(view=describe_view(spec.get('azimuth', 0), spec.get('elevation', 0)),
                                   style=style_prompt or (STYLE + STRICT))
            refs = [os.path.join(view_dir, f'{name}_flat.png')] + list((refs_per_view or {}).get(name, [])) + list(reference_images)
            calls += 1
            print(f'[paint] GPT Image call {calls}: {name} ({size}, {quality})')
            if not gptimage.generate(prompt, raw, model=model, size=size, quality=quality, refs=refs):
                raise RuntimeError(f'GPT Image failed for {name}')
            json.dump({'prompt': prompt, 'refs': refs, 'model': model, 'size': size, 'quality': quality},
                      open(os.path.join(out_dir, f'{name}_raw.json'), 'w'), indent=1)
        rep = register_painting(raw, view_dir, name, os.path.join(out_dir, f'{name}_paint.png'), bg=bg, local=local)
        results[name] = rep
        f = rep['final']
        print(f"[paint] {name}: residual {rep['before']['residual']} -> {f['residual']}, silhouette IoU "
              f"{rep['before']['silhouette_iou']} -> {f['silhouette_iou']}, edge distance {rep['before']['edge_chamfer_px']} "
              f"-> {f['edge_chamfer_px']} px{' (local flow kept)' if rep['local'] else ''}")
    summ = os.path.join(out_dir, 'paint.json')
    old = json.load(open(summ)) if os.path.exists(summ) else {}
    old.setdefault('views', {}).update(results)
    old['calls_this_run'] = calls
    old['calls_total'] = old.get('calls_total', 0) + calls
    json.dump(old, open(summ, 'w'), indent=1)
    return results


# ================================================================ projection bake (numpy only)
def raster_uv(tri_uv, size, chunk=4_000_000):
    """Rasterise UV triangles (T, 3, 2) into a size x size map: -> (tri index (S, S) int32, -1 = none; barycentrics
    (S, S, 3)). Texel (i, j) (row 0 = top, v = 1) is sampled at its centre. Triangles are bucketed by bounding-box size
    and processed in vectorised batches."""
    S = int(size)
    x = tri_uv[..., 0].astype(np.float64) * S - 0.5
    y = (1.0 - tri_uv[..., 1].astype(np.float64)) * S - 0.5
    x0 = np.clip(np.ceil(x.min(1) - 1e-7), 0, S - 1).astype(np.int64); x1 = np.clip(np.floor(x.max(1) + 1e-7), 0, S - 1).astype(np.int64)
    y0 = np.clip(np.ceil(y.min(1) - 1e-7), 0, S - 1).astype(np.int64); y1 = np.clip(np.floor(y.max(1) + 1e-7), 0, S - 1).astype(np.int64)
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    ax, ay = x[:, 0], y[:, 0]
    ex1, ey1 = x[:, 1] - ax, y[:, 1] - ay
    ex2, ey2 = x[:, 2] - ax, y[:, 2] - ay
    den = ex1 * ey2 - ex2 * ey1
    ok = (bw > 0) & (bh > 0) & (np.abs(den) > 1e-12) & (x.max(1) >= -0.5) & (x.min(1) <= S) & (y.max(1) >= -0.5) & (y.min(1) <= S)
    tid = np.full((S, S), -1, np.int32)
    bary = np.zeros((S, S, 3), np.float32)
    B = np.maximum(bw, bh)
    lo = 0
    for b in [2 ** k for k in range(0, 14)]:
        sel = np.nonzero(ok & (B > lo) & (B <= b))[0]
        lo = b
        if not len(sel):
            continue
        oy, ox = np.divmod(np.arange(b * b), b)
        step = max(1, chunk // (b * b))
        for s in range(0, len(sel), step):
            t = sel[s:s + step]
            gx = x0[t, None] + ox[None]; gy = y0[t, None] + oy[None]
            px = gx - ax[t, None]; py = gy - ay[t, None]
            l1 = (px * ey2[t, None] - ex2[t, None] * py) / den[t, None]
            l2 = (ex1[t, None] * py - px * ey1[t, None]) / den[t, None]
            l0 = 1 - l1 - l2
            e = -1e-6
            ins = (l0 >= e) & (l1 >= e) & (l2 >= e) & (gx <= x1[t, None]) & (gy <= y1[t, None])
            r, c = np.nonzero(ins)
            tid[gy[r, c], gx[r, c]] = t[r]
            bary[gy[r, c], gx[r, c]] = np.stack([l0[r, c], l1[r, c], l2[r, c]], 1)
    return tid, bary


def _vkey(X, h):
    q = np.floor(X / h).astype(np.int64) + (1 << 20)
    return (q[:, 0] << 42) | (q[:, 1] << 21) | q[:, 2]


def fill3d(X, col, known, h0=0.0015, levels=9):
    """colours for the texels not known, from the known texels around them in 3D: a 3D push-pull over voxel grids from
    coarse (h0 * 2^(levels-1)) to fine (h0), each level gathered with trilinear weights and laid over the coarser one
    by its occupancy, so the fill is smooth and ignores UV seams and islands."""
    out = col.copy()
    unk = np.nonzero(~known)[0]
    if not len(unk) or not known.any():
        return out
    Xk, Ck, Xq = X[known].astype(np.float64), col[known], X[unk].astype(np.float64)
    C = col.shape[1]
    val = np.broadcast_to(Ck.mean(0), (len(unk), C)).astype(np.float32).copy()
    for lev in reversed(range(levels)):
        h = h0 * 2 ** lev
        uniq, inv = np.unique(_vkey(Xk, h), return_inverse=True)
        cnt = np.bincount(inv).astype(np.float32)
        mean = np.stack([np.bincount(inv, Ck[:, c], len(uniq)) for c in range(C)], 1) / cnt[:, None]
        g = Xq / h - 0.5
        b = np.floor(g); f = (g - b).astype(np.float32)
        acc = np.zeros((len(unk), C), np.float32); wsum = np.zeros(len(unk), np.float32)
        for dx in (0, 1):
            for dy in (0, 1):
                for dz in (0, 1):
                    k = _vkey((b + (dx, dy, dz) + 0.5) * h, h)
                    pos = np.clip(np.searchsorted(uniq, k), 0, len(uniq) - 1)
                    hit = uniq[pos] == k
                    w = (f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1]) * (f[:, 2] if dz else 1 - f[:, 2])
                    w = np.where(hit, w, 0).astype(np.float32)
                    acc += w[:, None] * mean[pos]; wsum += w
        a = np.clip(wsum, 0, 1)[:, None]
        val = np.where(wsum[:, None] > 0, a * acc / np.maximum(wsum, 1e-8)[:, None] + (1 - a) * val, val)
    out[unk] = val
    return out


def _diffuse(tex, free, valid, iters=80):
    """Jacobi smoothing of tex on the free texels (4-neighbours inside valid only); other texels stay fixed."""
    t = tex.copy()
    v = valid.astype(np.float32)
    for _ in range(iters):
        s = np.zeros_like(t); n = np.zeros(valid.shape, np.float32)
        for sl_dst, sl_src in (((slice(1, None),), (slice(None, -1),)), ((slice(None, -1),), (slice(1, None),)),
                               ((slice(None), slice(1, None)), (slice(None), slice(None, -1))),
                               ((slice(None), slice(None, -1)), (slice(None), slice(1, None)))):
            s[sl_dst] += t[sl_src] * v[sl_src][..., None]
            n[sl_dst] += v[sl_src]
        avg = s / np.maximum(n, 1e-6)[..., None]
        t = np.where((free & (n > 0))[..., None], avg, t)
    return t


def srgb_to_lab(rgb):
    """sRGB 0..1 (..., 3) -> CIELAB (D65), numpy only."""
    c = np.asarray(rgb, np.float32)
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    M = np.float32([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ M.T / np.float32([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def _erode(w, r):
    for _ in range(int(r)):
        o = w.copy()
        o[1:] = np.minimum(o[1:], w[:-1]); o[:-1] = np.minimum(o[:-1], w[1:])
        o[:, 1:] = np.minimum(o[:, 1:], w[:, :-1]); o[:, :-1] = np.minimum(o[:, :-1], w[:, 1:])
        w = o
    return w


VIEW_TINTS = np.float32([[1.0, 0.45, 0.35], [0.35, 0.8, 0.4], [0.35, 0.55, 1.0], [1.0, 0.85, 0.3], [0.8, 0.4, 1.0],
                         [0.3, 0.9, 0.9], [0.95, 0.6, 0.8], [0.6, 0.6, 0.6]])


def _load_view(v):
    """(image, camera_json, depth) -> dict; the ID map is found next to the depth (<name>_id.npy)."""
    image, camj, depth = v[:3]
    cam = json.load(open(camj)) if isinstance(camj, str) else camj
    D = np.load(depth) if isinstance(depth, str) else np.asarray(depth, np.float32)
    ID = None
    if isinstance(depth, str) and depth.endswith('_depth.npy') and os.path.exists(depth[:-10] + '_id.npy'):
        ID = np.load(depth[:-10] + '_id.npy')
    flat = None
    if isinstance(depth, str) and depth.endswith('_depth.npy') and os.path.exists(depth[:-10] + '_flat.png'):
        flat = read_png(depth[:-10] + '_flat.png')[..., :3]
    img = read_png(image) if isinstance(image, str) else np.asarray(image, np.float32)
    if img.shape[2] == 3:
        img = np.dstack([img, np.ones(img.shape[:2], np.float32)])
    H, W = D.shape
    if img.shape[:2] != (H, W):
        img = resize_area(img, H, W)
    return {'cam': cam, 'D': D.astype(np.float32), 'ID': ID, 'img': img, 'flat': flat,
            'name': cam.get('name', os.path.basename(str(image)))}


def _view_masks(D, ID, jump=0.006, sil_px=(1.5, 12.0), edge_px=24.0):
    """per-pixel weight factors for a view: soft falloff near silhouettes and depth/ID discontinuities, and near the
    image border; plus the local depth slope (for the visibility tolerance)."""
    fin = np.isfinite(D)
    Df = np.where(fin, D, 1e3)
    disc = ~fin
    slope = np.zeros(D.shape, np.float32)
    for ax in (0, 1):
        a = np.take(Df, np.arange(D.shape[ax] - 1), axis=ax); b = np.take(Df, np.arange(1, D.shape[ax]), axis=ax)
        dd = np.abs(a - b)
        e = dd > jump
        if ID is not None:
            ia = np.take(ID, np.arange(D.shape[ax] - 1), axis=ax); ib = np.take(ID, np.arange(1, D.shape[ax]), axis=ax)
            e |= ia != ib
        pad0 = [(0, 0), (0, 0)]; pad0[ax] = (0, 1)
        pad1 = [(0, 0), (0, 0)]; pad1[ax] = (1, 0)
        disc |= np.pad(e, pad0) | np.pad(e, pad1)
        ds = np.where(e, 0, dd).astype(np.float32)
        slope = np.maximum(slope, np.maximum(np.pad(ds, pad0), np.pad(ds, pad1)))
    d = dist_to(disc, int(math.ceil(sil_px[1])))
    wsil = smoothstep(sil_px[0], sil_px[1], d)
    H, W = D.shape
    yy, xx = np.mgrid[0:H, 0:W]
    db = np.minimum(np.minimum(xx + 0.5, W - 0.5 - xx), np.minimum(yy + 0.5, H - 0.5 - yy))
    wb = smoothstep(0, edge_px, db)
    return (wsil * wb).astype(np.float32), slope


def project_to_uv(obj, uv_map, views, size=2048, out_png=None, power=3.0, tol=0.003, harmonise=True, bands=True,
                  band_sigma=None, sharp=4.0, jump=0.006, sil_px=(1.5, 12.0), edge_px=24.0, confident=0.12,
                  feature_de=None, max_gain=0.15, coverage_png=None):
    """Bake paintings onto obj's UV map uv_map. obj: one object, or a list sharing one atlas (every object's texels
    are tested against its own ID). views: [(image, camera_json, depth), ...] (paths or arrays; the ID map is read
    from <name>_id.npy beside the depth). For each texel of the UV map (rasterised in numpy at the evaluated,
    render-subdivided surface): its 3D point and normal are projected into each view and it counts where the view's
    depth agrees (tol + the local depth slope) and the view's ID is its object's; its weight is facing^power
    (|n . to camera|: visibility is the depth/ID test's job, and an outline Solidify can flip the rendered layer's
    normals) times a soft falloff near silhouettes / depth and ID edges and the image border, times the painting's
    alpha (register_painting's keyed silhouette x trust). It samples the painting through a pyramid matched to its
    footprint in pixels (no aliased staircases where the texture is coarser than the painting). Views are
    colour-harmonised on their overlap (a clamped gain per channel on the overlap's medians, the first view as anchor),
    then blended in two bands (low frequencies by the weights, detail by the weights^sharp), so slightly misregistered
    detail never doubles. Texels no view saw confidently are filled from their 3D neighbours
    and smoothed; the gutters are dilated. Writes out_png (RGB) and a coverage map (views tinted by their weight;
    magenta = no view; dark = no surface). feature_de=(lo, hi): also reject painted pixels whose own colour (not
    blurred) is more than lo..hi CIELAB from the render's there, eroded 2 px: for surfaces whose features belong to
    other layers (the head skin, whose eyes, lashes, brows and mouth are decals), so painted features and stray wisps
    never land on them while gradients and blush (small distances) do. Needs <name>_flat.png beside the depth.
    Returns stats (also written as <out_png>.json)."""
    objs = obj if isinstance(obj, (list, tuple)) else [obj]
    S = int(size)
    tris = [mesh_arrays(o, uv_map) for o in objs]
    VW = [_load_view(v) for v in views]
    ids = VW[0]['cam'].get('ids', {})
    uv = np.concatenate([t['uv'] for t in tris]); Pt = np.concatenate([t['P'] for t in tris]); Nt = np.concatenate([t['N'] for t in tris])
    oid = np.concatenate([np.full(len(t['uv']), ids.get(o.name, -1), np.int32) for t, o in zip(tris, objs)])
    tid, bary = raster_uv(uv, S)
    valid = tid >= 0
    vi = np.nonzero(valid.ravel())[0]
    t = tid.ravel()[vi]; b = bary.reshape(-1, 3)[vi]
    X = np.einsum('mk,mkc->mc', b, Pt[t]).astype(np.float32)
    Nn = np.einsum('mk,mkc->mc', b, Nt[t]).astype(np.float32)
    Nn /= np.maximum(np.linalg.norm(Nn, axis=1, keepdims=True), 1e-9)
    tex_oid = oid[t]
    # each texel's size on the surface (metres), for the prefilter: sqrt(world area / UV area in texels) of its triangle
    e1, e2 = Pt[:, 1] - Pt[:, 0], Pt[:, 2] - Pt[:, 0]
    aw = 0.5 * np.linalg.norm(np.cross(e1, e2), axis=1)
    u1, u2 = (uv[:, 1] - uv[:, 0]) * S, (uv[:, 2] - uv[:, 0]) * S
    auv = 0.5 * np.abs(u1[:, 0] * u2[:, 1] - u1[:, 1] * u2[:, 0])
    tsize = np.sqrt(aw / np.maximum(auv, 1e-12)).astype(np.float32)[t]
    del bary
    M = len(vi)
    cols, ws, stats_v = [], [], []
    for V in VW:
        cam, D, ID, img = V['cam'], V['D'], V['ID'], V['img']
        H, W = D.shape
        wmap, slope = _view_masks(D, ID, jump, sil_px, edge_px)
        if feature_de is not None and V['flat'] is not None:
            dE = np.linalg.norm(srgb_to_lab(img[..., :3]) - srgb_to_lab(V['flat']), axis=-1)
            wmap = wmap * _erode(1 - smoothstep(feature_de[0], feature_de[1], dE), 2)
        px, py, z, tocam = project(cam, X)
        inb = (px >= 0) & (px < W) & (py >= 0) & (py < H) & (z > 0)
        ix = np.clip(np.floor(px), 0, W - 1).astype(np.int64); iy = np.clip(np.floor(py), 0, H - 1).astype(np.int64)
        vis = inb & (z <= D[iy, ix] + tol + 1.5 * slope[iy, ix])
        if ID is not None:
            vis &= ID[iy, ix] == tex_oid
        facing = np.clip(np.abs(np.einsum('mc,mc->m', Nn, tocam)), 0, 1)
        w = facing ** power * wmap[iy, ix]
        # prefilter: a texel covering fp pixels samples the painting blurred to match (a Gaussian pyramid, sigma = fp/2,
        # levels lerped), so thin painted lines don't alias into staircases on a texture coarser than the painting
        f_px = cam['K'][0][0]
        fp = tsize * (f_px if cam['type'] == 'ORTHO' else f_px / np.maximum(z, 1e-6)) / np.sqrt(np.maximum(facing, 0.25))
        lev = np.clip(np.log2(np.maximum(fp, 1.0)), 0, 4)
        pyr = [img] + [blur(img, 0.5 * 2 ** k) for k in range(1, 5)]
        l0 = np.floor(lev).astype(np.int64); fr = (lev - l0).astype(np.float32)[:, None]
        rgba = np.zeros((M, 4), np.float32)
        for k in range(5):
            for sel, wk in ((l0 == k, 1 - fr), (l0 + 1 == k, fr)):
                if sel.any():
                    rgba[sel] += wk[sel] * bilinear(pyr[k], px[sel] - 0.5, py[sel] - 0.5)
        del pyr
        w = np.where(vis, w * np.clip(rgba[:, 3], 0, 1), 0).astype(np.float32)
        cols.append(rgba[:, :3].astype(np.float32)); ws.append(w)
        stats_v.append({'view': V['name'], 'visible_frac': round(float(vis.mean()), 4), 'weight_sum': round(float(w.sum()) / max(M, 1), 4),
                        'footprint_px_median': round(float(np.median(fp[vis])), 3) if vis.any() else None})
    gains = {}
    if harmonise and len(VW) > 1:
        done = [0]                                  # the first view (by convention the front) is the anchor
        gains[VW[0]['name']] = 'anchor'
        todo = list(range(1, len(VW)))
        while todo:
            wr = sum(ws[d] for d in done)
            ovs = [((ws[v] > 0.15) & (wr > 0.15)).sum() for v in todo]
            v = todo.pop(int(np.argmax(ovs)))           # next: the view overlapping the anchored set most
            cr = sum(ws[d][:, None] * cols[d] for d in done) / np.maximum(wr, 1e-6)[:, None]
            ov = (ws[v] > 0.15) & (wr > 0.15)
            if ov.sum() < 400:
                gains[VW[v]['name']] = f'overlap {int(ov.sum())} texels: left as painted'
                done.append(v)
                continue
            g = []
            for c in range(3):                      # a per-channel gain on the overlap's medians (exposure and white
                ms = float(np.median(cols[v][ov, c]))     # balance), clamped: robust where the painter drew different
                mr = float(np.median(cr[ov, c]))          # detail (strands, lines) in each view
                a = float(np.clip(mr / max(ms, 1e-4), 1 - max_gain, 1 + max_gain))
                cols[v][:, c] = cols[v][:, c] * a
                g.append(round(a, 3))
            gains[VW[v]['name']] = {'gain': g, 'overlap_texels': int(ov.sum())}
            done.append(v)
    Wt = sum(ws)
    seen = Wt > 1e-4

    def to_tex(vals, C=3):
        o = np.zeros((S * S, C), np.float32); o[vi] = vals.reshape(M, C); return o.reshape(S, S, C)
    if bands and len(VW) > 1:
        sig = band_sigma or S / 256.0
        numL = np.zeros((S, S, 3), np.float32); numH = np.zeros((S, S, 3), np.float32)
        denL = np.zeros((S, S), np.float32); denH = np.zeros((S, S), np.float32)
        for c, w in zip(cols, ws):
            Tw = to_tex(w, 1)[..., 0]
            T = to_tex(c)
            m = Tw > 1e-4
            Lo = masked_blur(T, m, sig)
            Hi = T - Lo
            numL += Tw[..., None] * Lo; denL += Tw
            ws_ = Tw ** sharp
            numH += ws_[..., None] * Hi; denH += ws_
        blend = numL / np.maximum(denL, 1e-8)[..., None] + np.where(denH[..., None] > 1e-12, numH / np.maximum(denH, 1e-12)[..., None], 0)
        col = blend.reshape(-1, 3)[vi]
        del numL, numH, denL, denH
    else:
        col = sum(w[:, None] * c for c, w in zip(cols, ws)) / np.maximum(Wt, 1e-8)[:, None]
    col = np.clip(col, 0, 1)
    conf = Wt >= confident
    filled = fill3d(X, col, conf)
    ft = to_tex(filled)
    free = valid & ~to_tex(conf.astype(np.float32), 1)[..., 0].astype(bool)
    ft = _diffuse(ft, free, valid, iters=60)
    filled = ft.reshape(-1, 3)[vi]
    k = smoothstep(0.0, confident, Wt)[:, None]
    final = col * k + filled * (1 - k)
    tex = to_tex(final)
    tex = pushpull(tex, valid.astype(np.float32))
    stats = {'size': S, 'texels': int(M), 'seen_frac': round(float(seen.mean()), 4), 'confident_frac': round(float(conf.mean()), 4),
             'views': stats_v, 'harmonise': gains, 'objects': [o.name for o in objs]}
    if out_png:
        write_png(out_png, tex)
        cov = np.full((S, S, 3), 0.12, np.float32)
        best = np.argmax(np.stack(ws), 0)
        tint = VIEW_TINTS[best % len(VIEW_TINTS)] * np.clip(Wt / max(confident * 2, 1e-6), 0.15, 1)[:, None]
        tint[~seen] = (1, 0, 1)
        cov.reshape(-1, 3)[vi] = tint
        write_png(coverage_png or out_png.replace('.png', '_coverage.png'), cov)
        stats['legend'] = {VW[i]['name']: [round(float(x), 2) for x in VIEW_TINTS[i % len(VIEW_TINTS)]] for i in range(len(VW))}
        json.dump(stats, open(out_png.replace('.png', '.json'), 'w'), indent=1)
    print(f"[paint] baked {', '.join(stats['objects'])} -> {out_png}: {M} texels, seen {stats['seen_frac']:.1%}, "
          f"confident {stats['confident_frac']:.1%}")
    return stats


# ================================================================ materials (Blender)
def _registry():
    k = sys.modules.get('kit')
    return k.MATS if k is not None and hasattr(k, 'MATS') else None


def _image(path):
    import bpy
    ap = os.path.abspath(path)
    for im in bpy.data.images:
        if im.filepath and os.path.abspath(bpy.path.abspath(im.filepath)) == ap:
            im.reload()
            return im
    im = bpy.data.images.load(ap)
    im.colorspace_settings.name = 'sRGB'
    return im


def _tex_colour(nt, tex_path, uv_map):
    N, L = nt.nodes.new, nt.links.new
    uvn = N('ShaderNodeUVMap'); uvn.uv_map = uv_map
    tex = N('ShaderNodeTexImage'); tex.image = _image(tex_path); tex.name = 'paint_tex'
    tex.interpolation = 'Linear'; tex.extension = 'EXTEND'
    L(uvn.outputs['UV'], tex.inputs['Vector'])
    return tex.outputs['Color']


def _mul(nt, sock, colour):
    m = nt.nodes.new('ShaderNodeMix'); m.data_type = 'RGBA'; m.blend_type = 'MULTIPLY'
    m.inputs['Factor'].default_value = 1.0
    nt.links.new(sock, m.inputs['A']); m.inputs['B'].default_value = (*lin(colour), 1)
    return m.outputs['Result']


def toon3_tex(name, tex_path, uv_map='paint', shade_mul=WARM_SHADE, deep_mul=None, thresh=0.5, deep_thresh=0.27,
              soft=0.012, rim=(1.0, 0.95, 0.9), rim_amt=0.18, registry=None):
    """kit.toon3 with a painted texture for its base colour: deep | shadow | lit on half-lambert N.L, hard steps, where
    lit = the texture, shadow = texture x shade_mul, deep = texture x deep_mul (sRGB-authored multipliers, default
    deep = shade x 0.82), so painted detail survives into shadow; plus kit's lit-side fresnel rim. Node names match
    toon3 ('ldir', 'ramp', 'rim_mix', 'rim_amt') so kit.set_light and kit.set_rim drive it."""
    import bpy
    deep_mul = deep_mul or tuple(c * 0.82 for c in shade_mul)
    m = bpy.data.materials.new(name); nt = _nodes(m)
    N, L = nt.nodes.new, nt.links.new
    out = N('ShaderNodeOutputMaterial'); geo = N('ShaderNodeNewGeometry')
    ld = N('ShaderNodeCombineXYZ'); ld.name = 'ldir'
    kit = sys.modules.get('kit')
    for i, v in enumerate(getattr(kit, 'LDIR', (0.35, -0.55, 0.75))):
        ld.inputs[i].default_value = v
    dot = N('ShaderNodeVectorMath'); dot.operation = 'DOT_PRODUCT'
    L(geo.outputs['Normal'], dot.inputs[0]); L(ld.outputs[0], dot.inputs[1])
    half = N('ShaderNodeMath'); half.operation = 'MULTIPLY_ADD'; half.inputs[1].default_value = 0.5; half.inputs[2].default_value = 0.5
    L(dot.outputs['Value'], half.inputs[0])

    def step(at, nm=None):
        r = N('ShaderNodeValToRGB')
        if nm:
            r.name = nm
        e0, e1 = r.color_ramp.elements
        e0.position, e1.position = at - soft, at + soft
        e0.color, e1.color = (0, 0, 0, 1), (1, 1, 1, 1)
        L(half.outputs[0], r.inputs[0])
        return r
    s_lit, s_deep = step(thresh, 'ramp'), step(deep_thresh)
    base = _tex_colour(nt, tex_path, uv_map)
    m1 = N('ShaderNodeMix'); m1.data_type = 'RGBA'
    L(_mul(nt, base, deep_mul), m1.inputs['A']); L(_mul(nt, base, shade_mul), m1.inputs['B'])
    L(s_deep.outputs['Color'], m1.inputs['Factor'])
    m2 = N('ShaderNodeMix'); m2.data_type = 'RGBA'
    L(m1.outputs['Result'], m2.inputs['A']); L(base, m2.inputs['B']); L(s_lit.outputs['Color'], m2.inputs['Factor'])
    lw = N('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.3
    rr = N('ShaderNodeMapRange'); rr.inputs['From Min'].default_value = 0.64; rr.inputs['From Max'].default_value = 0.68
    L(lw.outputs['Facing'], rr.inputs['Value'])
    lm = N('ShaderNodeMath'); lm.operation = 'MULTIPLY'; lm.inputs[1].default_value = rim_amt; lm.name = 'rim_amt'
    L(rr.outputs['Result'], lm.inputs[0])
    lm2 = N('ShaderNodeMath'); lm2.operation = 'MULTIPLY'
    L(lm.outputs[0], lm2.inputs[0]); L(s_lit.outputs['Color'], lm2.inputs[1])
    rim_mix = N('ShaderNodeMix'); rim_mix.data_type = 'RGBA'; rim_mix.blend_type = 'SCREEN'; rim_mix.name = 'rim_mix'
    rim_mix.inputs['B'].default_value = (*lin(rim), 1)
    L(lm2.outputs[0], rim_mix.inputs['Factor']); L(m2.outputs['Result'], rim_mix.inputs['A'])
    em = N('ShaderNodeEmission'); L(rim_mix.outputs['Result'], em.inputs['Color']); L(em.outputs[0], out.inputs['Surface'])
    reg = registry if registry is not None else _registry()
    if reg is not None:
        reg[name] = m
    return m


def add_ring(m, ring=(1.0, 0.80, 0.62), head_z=0.0, ring_el=40.0, amount=0.6, lock_uv='lock'):
    """hair.hair_material's angel ring on a (textured) toon3 material: a band at ring_el degrees above the head
    centre, a lens on each clump's centre line ('lock' UV), on the lit side, where the hair faces the camera."""
    nt = m.node_tree; N = nt.nodes.new; L = nt.links.new
    em = next(n for n in nt.nodes if n.type == 'EMISSION')
    src = em.inputs['Color'].links[0].from_socket
    uv = N('ShaderNodeUVMap'); uv.uv_map = lock_uv
    sep = N('ShaderNodeSeparateXYZ'); L(uv.outputs[0], sep.inputs[0])
    across = N('ShaderNodeMath'); across.operation = 'ABSOLUTE'; L(sep.outputs['X'], across.inputs[0])
    mid = N('ShaderNodeMapRange'); mid.inputs['From Min'].default_value = 0.95; mid.inputs['From Max'].default_value = 0.85
    L(across.outputs[0], mid.inputs['Value'])
    tc = N('ShaderNodeTexCoord')
    rel = N('ShaderNodeVectorMath'); rel.operation = 'SUBTRACT'; rel.inputs[1].default_value = (0, 0, head_z)
    L(tc.outputs['Object'], rel.inputs[0])
    sp = N('ShaderNodeSeparateXYZ'); L(rel.outputs[0], sp.inputs[0])
    hx = N('ShaderNodeCombineXYZ'); L(sp.outputs['X'], hx.inputs[0]); L(sp.outputs['Y'], hx.inputs[1])
    hl = N('ShaderNodeVectorMath'); hl.operation = 'LENGTH'; L(hx.outputs[0], hl.inputs[0])
    el = N('ShaderNodeMath'); el.operation = 'ARCTAN2'; L(sp.outputs['Z'], el.inputs[0]); L(hl.outputs['Value'], el.inputs[1])
    dz = N('ShaderNodeMath'); dz.operation = 'SUBTRACT'; dz.inputs[1].default_value = math.radians(ring_el); L(el.outputs[0], dz.inputs[0])
    adz = N('ShaderNodeMath'); adz.operation = 'ABSOLUTE'; L(dz.outputs[0], adz.inputs[0])
    u2 = N('ShaderNodeMath'); u2.operation = 'POWER'; u2.inputs[1].default_value = 2.0; L(across.outputs[0], u2.inputs[0])
    wid = N('ShaderNodeMath'); wid.operation = 'MULTIPLY_ADD'; wid.inputs[1].default_value = -math.radians(5.0)
    wid.inputs[2].default_value = math.radians(5.0); L(u2.outputs[0], wid.inputs[0])
    lens = N('ShaderNodeMath'); lens.operation = 'SUBTRACT'; L(wid.outputs[0], lens.inputs[0]); L(adz.outputs[0], lens.inputs[1])
    band = N('ShaderNodeMapRange'); band.inputs['From Min'].default_value = 0.0; band.inputs['From Max'].default_value = math.radians(1.2)
    L(lens.outputs[0], band.inputs['Value'])
    lw = N('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.5
    face = N('ShaderNodeMapRange'); face.inputs['From Min'].default_value = 0.55; face.inputs['From Max'].default_value = 0.25
    L(lw.outputs['Facing'], face.inputs['Value'])
    lit_mask = nt.nodes['ramp'].outputs['Color']
    m1 = N('ShaderNodeMath'); m1.operation = 'MULTIPLY'; L(mid.outputs[0], m1.inputs[0]); L(band.outputs[0], m1.inputs[1])
    m2 = N('ShaderNodeMath'); m2.operation = 'MULTIPLY'; L(m1.outputs[0], m2.inputs[0]); L(face.outputs[0], m2.inputs[1])
    m3 = N('ShaderNodeMath'); m3.operation = 'MULTIPLY'; L(m2.outputs[0], m3.inputs[0]); L(lit_mask, m3.inputs[1])
    fade = N('ShaderNodeMath'); fade.operation = 'MULTIPLY'; fade.inputs[1].default_value = amount; fade.name = 'ring_amt'
    L(m3.outputs[0], fade.inputs[0])
    hi = N('ShaderNodeMix'); hi.data_type = 'RGBA'; hi.inputs['B'].default_value = (*lin(ring), 1)
    L(fade.outputs[0], hi.inputs['Factor']); L(src, hi.inputs['A'])
    L(hi.outputs['Result'], em.inputs['Color'])
    return m


def face_tex(name, tex_path, sdf_path, uv_map='paint', face_uv='face', shade_mul=WARM_SHADE, line_soft=0.012,
             rim=(1, 0.92, 0.88), rim_amt=0.18, registry=None):
    """head.face_material with a painted texture: the SDF face shadow (the light's angle to the head, in head object
    space, against a threshold map on the face UV, mirrored for a light on her right) switches between the texture
    and texture x shade_mul. The painted texture carries the blush, so there is no separate blush layer."""
    import bpy
    m = bpy.data.materials.new(name); nt = _nodes(m)
    N, L = nt.nodes.new, nt.links.new
    out = N('ShaderNodeOutputMaterial')
    ld = N('ShaderNodeCombineXYZ'); ld.name = 'ldir'
    kit = sys.modules.get('kit')
    for i, v in enumerate(getattr(kit, 'LDIR', (0.35, -0.55, 0.75))):
        ld.inputs[i].default_value = v
    vt = N('ShaderNodeVectorTransform'); vt.vector_type = 'VECTOR'; vt.convert_from = 'WORLD'; vt.convert_to = 'OBJECT'
    L(ld.outputs[0], vt.inputs[0])
    sep = N('ShaderNodeSeparateXYZ'); L(vt.outputs[0], sep.inputs[0])
    negy = N('ShaderNodeMath'); negy.operation = 'MULTIPLY'; negy.inputs[1].default_value = -1.0; L(sep.outputs['Y'], negy.inputs[0])
    absx = N('ShaderNodeMath'); absx.operation = 'ABSOLUTE'; L(sep.outputs['X'], absx.inputs[0])
    ang = N('ShaderNodeMath'); ang.operation = 'ARCTAN2'; L(absx.outputs[0], ang.inputs[0]); L(negy.outputs[0], ang.inputs[1])
    t = N('ShaderNodeMath'); t.operation = 'DIVIDE'; t.inputs[1].default_value = math.pi; L(ang.outputs[0], t.inputs[0])
    uvn = N('ShaderNodeUVMap'); uvn.uv_map = face_uv
    suv = N('ShaderNodeSeparateXYZ'); L(uvn.outputs[0], suv.inputs[0])
    flipu = N('ShaderNodeMath'); flipu.operation = 'SUBTRACT'; flipu.inputs[0].default_value = 1.0; L(suv.outputs['X'], flipu.inputs[1])
    right = N('ShaderNodeMath'); right.operation = 'LESS_THAN'; right.inputs[1].default_value = 0.0; L(sep.outputs['X'], right.inputs[0])
    mu = N('ShaderNodeMix'); mu.data_type = 'FLOAT'
    L(right.outputs[0], mu.inputs['Factor']); L(suv.outputs['X'], mu.inputs['A']); L(flipu.outputs[0], mu.inputs['B'])
    cuv = N('ShaderNodeCombineXYZ'); L(mu.outputs['Result'], cuv.inputs[0]); L(suv.outputs['Y'], cuv.inputs[1])
    sdf = N('ShaderNodeTexImage'); sdf.image = bpy.data.images.load(sdf_path, check_existing=True)
    sdf.image.colorspace_settings.name = 'Non-Color'; sdf.extension = 'EXTEND'; sdf.interpolation = 'Cubic'
    L(cuv.outputs[0], sdf.inputs['Vector'])
    diff = N('ShaderNodeMath'); diff.operation = 'SUBTRACT'; L(t.outputs[0], diff.inputs[0]); L(sdf.outputs['Color'], diff.inputs[1])
    edge = N('ShaderNodeMapRange'); edge.inputs['From Min'].default_value = -line_soft; edge.inputs['From Max'].default_value = line_soft
    L(diff.outputs[0], edge.inputs['Value'])
    base = _tex_colour(nt, tex_path, uv_map)
    col = N('ShaderNodeMix'); col.data_type = 'RGBA'
    L(base, col.inputs['A']); L(_mul(nt, base, shade_mul), col.inputs['B']); L(edge.outputs['Result'], col.inputs['Factor'])
    lw = N('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.25
    rr = N('ShaderNodeMapRange'); rr.inputs['From Min'].default_value = 0.72; rr.inputs['From Max'].default_value = 0.76
    rr.inputs['To Max'].default_value = 1.0
    L(lw.outputs['Facing'], rr.inputs['Value'])
    lm = N('ShaderNodeMath'); lm.operation = 'MULTIPLY'; lm.inputs[1].default_value = rim_amt; lm.name = 'rim_amt'
    L(rr.outputs['Result'], lm.inputs[0])
    rim_mix = N('ShaderNodeMix'); rim_mix.data_type = 'RGBA'; rim_mix.blend_type = 'SCREEN'; rim_mix.name = 'rim_mix'
    rim_mix.inputs['B'].default_value = (*lin(rim), 1)
    L(lm.outputs[0], rim_mix.inputs['Factor']); L(col.outputs['Result'], rim_mix.inputs['A'])
    em = N('ShaderNodeEmission'); L(rim_mix.outputs['Result'], em.inputs['Color']); L(em.outputs[0], out.inputs['Surface'])
    reg = registry if registry is not None else _registry()
    if reg is not None:
        reg[name] = m
    return m


def _unlinked(sock):
    return not sock.is_linked


def material_tones(m):
    """(lit, shade, deep) linear colours of a kit cel material (toon3: via its 'ramp' step; face_material: its one
    two-colour mix), or None."""
    nt = m.node_tree if m else None
    if nt is None:
        return None
    if 'ramp' in nt.nodes:
        for l in nt.nodes['ramp'].outputs['Color'].links:
            m2 = l.to_node
            if m2.type == 'MIX' and l.to_socket.name == 'Factor' and _unlinked(m2.inputs['B']) and m2.inputs['A'].is_linked:
                m1 = m2.inputs['A'].links[0].from_node
                if m1.type == 'MIX' and _unlinked(m1.inputs['A']) and _unlinked(m1.inputs['B']):
                    return (tuple(m2.inputs['B'].default_value[:3]), tuple(m1.inputs['B'].default_value[:3]),
                            tuple(m1.inputs['A'].default_value[:3]))
    for n in nt.nodes:
        if n.type == 'MIX' and n.data_type == 'RGBA' and n.blend_type == 'MIX' and _unlinked(n.inputs['A']) and \
                _unlinked(n.inputs['B']) and n.inputs['Factor'].is_linked:
            lit, sh = tuple(n.inputs['A'].default_value[:3]), tuple(n.inputs['B'].default_value[:3])
            return lit, sh, tuple(c * 0.82 ** 2.2 for c in sh)
    return None


def _ratio(a, b):
    """sRGB-authored multiplier that takes linear a to linear b."""
    return tuple(min(1.0, max(0.05, (bb / max(aa, 1e-4)))) ** (1 / 2.2) for aa, bb in zip(a, b))


def apply_painted(obj, texture_png, uv_map='paint', behaviour='auto', shade_mul=None, deep_mul=None, ring=None,
                  ring_amt=0.0, sdf_path=None, **kw):
    """Swap each cel material on obj (or a list) for its painted twin, the baked texture as base colour.
    behaviour: 'toon3' (three tones on N.L), 'face' (the SDF face shadow; the SDF map from the old material unless
    sdf_path), 'hair' (toon3 + the angel ring on the 'lock' UV; ring=(r, g, b) or the old material's), 'flat'
    (emission of the texture), or 'auto' (face if the old material has an SDF map, hair if it reads a 'lock' UV, else
    toon3; the ring is off unless ring_amt > 0: the painting carries its own highlights and the kit's ring band reads
    as a smear over them). shade_mul / deep_mul default to the old material's own shade/lit and deep/lit ratios (its palette's warm
    shadow hue), else WARM_SHADE. Outline materials are left alone. Returns the new materials."""
    import bpy
    objs = obj if isinstance(obj, (list, tuple)) else [obj]
    made = {}
    for o in objs:
        for i, m in enumerate(o.data.materials):
            if m is None or m.name.startswith('outline') or m.name.endswith('_painted'):
                continue
            beh = behaviour
            nt = m.node_tree
            if beh == 'auto':
                if nt and any(n.type == 'TEX_IMAGE' and n.image and 'sdf' in n.image.name.lower() for n in nt.nodes):
                    beh = 'face'
                elif nt and any(n.type == 'UVMAP' and n.uv_map == 'lock' for n in nt.nodes):
                    beh = 'hair'
                else:
                    beh = 'toon3'
            key = (m.name, os.path.abspath(texture_png), beh)
            if key not in made:
                tones = material_tones(m)
                sm = shade_mul or (_ratio(tones[0], tones[1]) if tones else WARM_SHADE)
                dm = deep_mul or (_ratio(tones[0], tones[2]) if tones else None)
                nm = f'{m.name}_painted'
                if beh == 'face':
                    sp = sdf_path or next((bpy.path.abspath(n.image.filepath) for n in nt.nodes if n.type == 'TEX_IMAGE'
                                           and n.image and 'sdf' in n.image.name.lower()), None)
                    new = face_tex(nm, texture_png, sp, uv_map=uv_map, shade_mul=sm, **kw)
                elif beh == 'flat':
                    new = bpy.data.materials.new(nm); tn = _nodes(new)
                    em = tn.nodes.new('ShaderNodeEmission'); ou = tn.nodes.new('ShaderNodeOutputMaterial')
                    tn.links.new(_tex_colour(tn, texture_png, uv_map), em.inputs['Color']); tn.links.new(em.outputs[0], ou.inputs['Surface'])
                else:
                    new = toon3_tex(nm, texture_png, uv_map=uv_map, shade_mul=sm, deep_mul=dm, **kw)
                    if beh == 'hair':
                        rc, hz = ring, 0.0
                        if nt:
                            for n in nt.nodes:
                                if n.type == 'VECT_MATH' and n.operation == 'SUBTRACT' and not n.inputs[1].is_linked:
                                    hz = n.inputs[1].default_value[2]
                                if rc is None and n.type == 'MIX' and n.inputs['A'].is_linked and not n.inputs['B'].is_linked \
                                        and n.inputs['Factor'].is_linked and n.inputs['Factor'].links[0].from_node.type == 'MATH' \
                                        and n.inputs['Factor'].links[0].from_node.operation == 'MULTIPLY':
                                    rc = tuple(c ** (1 / 2.2) for c in n.inputs['B'].default_value[:3])
                        if rc is not None and ring_amt > 0:
                            add_ring(new, rc, head_z=hz, amount=ring_amt)
                made[key] = new
            o.data.materials[i] = made[key]
    return list(made.values())


# ================================================================ the demo on Clawd
OUT = os.path.join(HERE, 'out', 'paint')
CLAWD = os.path.join(REPO, 'projects', 'clawd3d', 'build')
REF_DIR = os.path.expanduser('~/animation-pipeline/projects/tsuzuku/rig/clawd')
REF_FRONT = os.path.join(REF_DIR, 'base.png')
REF_HALF_L = os.path.join(REF_DIR, 'views', 'half_left_1.png')
REF_HALF_R = os.path.join(REF_DIR, 'views', 'half_right_1.png')
HEAD_CROP = (560, 0, 1600, 1040)           # the head and hair in the 2160x3840 drawings (x0, y0, x1, y1)


def demo_specs(HC, res=1024):
    t = [float(HC[0]), float(HC[1]), float(HC[2]) + 0.04]
    base = dict(elevation=5.0, distance=1.2, lens=85.0, target=t, resolution=res)
    return [dict(base, name='front', azimuth=0.0), dict(base, name='q_left', azimuth=45.0),
            dict(base, name='q_right', azimuth=-45.0), dict(base, name='back', azimuth=180.0)]


def board_specs(HC, res=1024):
    t = [float(HC[0]), float(HC[1]), float(HC[2]) + 0.03]
    base = dict(elevation=4.0, distance=1.1, lens=85.0, target=t, resolution=res)
    return [dict(base, name='front', azimuth=0.0), dict(base, name='q_left', azimuth=35.0),
            dict(base, name='q_right', azimuth=-35.0), dict(base, name='back', azimuth=180.0)]


def _demo_parts():
    import bpy
    head = bpy.data.objects['head']
    hair = [bpy.data.objects[n] for n in ('hair_cap', 'hair_under', 'hair_main', 'hair_bangs', 'bun.L', 'bun.R')]
    return head, hair


def demo_views(out=OUT):
    import bpy
    sys.path.insert(0, CLAWD)
    import clawd
    clawd.build()
    head, hair = _demo_parts()
    ensure_atlas([head], 'paint', angle=60.0, margin=0.006)
    ensure_atlas(hair, 'paint', angle=60.0, margin=0.004)
    os.makedirs(os.path.join(out, 'work'), exist_ok=True)
    blend = os.path.join(out, 'work', 'clawd_atlas.blend')
    bpy.ops.file.make_paths_absolute()
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=blend, relative_remap=False)
    json.dump({'HC': list(clawd.HC)}, open(os.path.join(out, 'work', 'clawd.json'), 'w'))
    make_views(None, demo_specs(clawd.HC), os.path.join(out, 'views'))
    print('[paint] views ->', os.path.join(out, 'views'), '; scene ->', blend)


def demo_refs(out=OUT):
    """head crops of the reference drawings on white (the painter's references)."""
    from PIL import Image
    d = os.path.join(out, 'refs'); os.makedirs(d, exist_ok=True)
    res = {}
    for k, p in (('front', REF_FRONT), ('half_left', REF_HALF_L), ('half_right', REF_HALF_R)):
        im = Image.open(p).convert('RGBA').crop(HEAD_CROP)
        bg = Image.new('RGBA', im.size, (255, 255, 255, 255)); bg.alpha_composite(im)
        res[k] = os.path.join(d, f'{k}_head.png'); bg.convert('RGB').save(res[k])
    return res


def demo_paint(out=OUT, only=None, max_calls=4, force=False, strict=True, sub='paint'):
    refs = demo_refs(out)
    per = {'q_left': [refs['half_left']], 'q_right': [refs['half_right']]}
    return paint_views(os.path.join(out, 'views'), [refs['front']], STYLE + (STRICT if strict else ''),
                       os.path.join(out, sub), views=only, max_calls=max_calls, force=force, refs_per_view=per)


def demo_bake(out=OUT, size_head=2048, size_hair=4096):
    """(run in Blender on work/clawd_atlas.blend) bake the head and the hair, render before/after, save the scene."""
    import bpy
    sys.path.insert(0, CLAWD)
    import kit
    kit.MATS.clear()
    kit.MATS.update({m.name: m for m in bpy.data.materials if m.node_tree and 'ldir' in m.node_tree.nodes})
    HC = json.load(open(os.path.join(out, 'work', 'clawd.json')))['HC']
    head, hair = _demo_parts()
    ensure_atlas([head], 'paint', angle=60.0, margin=0.006, force=True)
    ensure_atlas(hair, 'paint', angle=60.0, margin=0.004, force=True)
    vd, pd, td = os.path.join(out, 'views'), os.path.join(out, 'paint'), os.path.join(out, 'tex')
    names = [v['name'] for v in json.load(open(os.path.join(vd, 'views.json')))['views']]
    views = [(os.path.join(pd, f'{n}_paint.png'), os.path.join(vd, f'{n}_cam.json'), os.path.join(vd, f'{n}_depth.npy'))
             for n in names if os.path.exists(os.path.join(pd, f'{n}_paint.png'))]
    print('[paint] views to bake:', [os.path.basename(v[0]) for v in views])
    st_h = project_to_uv(head, 'paint', views, size_head, os.path.join(td, 'head.png'), feature_de=(14.0, 24.0))
    st_r = project_to_uv(hair, 'paint', views, size_hair, os.path.join(td, 'hair.png'), feature_de=(36.0, 50.0))
    bd = os.path.join(out, 'board')
    specs = board_specs(HC)
    close = [dict(s, name=s['name'] + '_zoom', distance=0.55, resolution=1024,
                  target=[HC[0], HC[1], HC[2] - 0.01]) for s in specs[:2]]
    render_stills(specs + close, bd, 'before_')
    render_stills(specs[:3], bd, 'before_flat_', light='camera')
    keep = {o: list(o.data.materials) for o in [head] + hair}
    apply_painted(head, os.path.join(td, 'head_coverage.png'), 'paint', behaviour='flat')
    apply_painted(hair, os.path.join(td, 'hair_coverage.png'), 'paint', behaviour='flat')
    render_stills(specs, bd, 'coverage_')
    for o, ms in keep.items():
        for i, m in enumerate(ms):
            o.data.materials[i] = m
    apply_painted(head, os.path.join(td, 'head.png'), 'paint', behaviour='face')
    apply_painted(hair, os.path.join(td, 'hair.png'), 'paint', behaviour='auto')
    render_stills(specs + close, bd, 'after_')
    render_stills(specs[:3], bd, 'after_flat_', light='camera')
    for d in ((0.0, -1, 0.35), (0.86, -0.5, 0.35), (-0.86, -0.5, 0.35), (1, 0.0, 0.35)):
        tag = f'{int(round(math.degrees(math.atan2(d[0], -d[1]))))}'
        render_stills([dict(specs[1], name=f'light{tag}')], bd, 'after_', light=d)
    bpy.ops.file.make_paths_absolute()
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, 'work', 'clawd_painted.blend'), relative_remap=False)
    json.dump({'head': st_h, 'hair': st_r}, open(os.path.join(out, 'bake.json'), 'w'), indent=1)


def demo_board(out=OUT):
    """compose the before/after board (venv, PIL)."""
    from PIL import Image, ImageDraw, ImageFont
    bd = os.path.join(out, 'board')
    font = ImageFont.load_default(size=26)
    cols = ['front', 'q_left', 'q_right', 'back']
    rows = [('before (flat colours, key light)', 'before_'), ('after (painted, key light)', 'after_'),
            ('before, lit from camera', 'before_flat_'), ('after, lit from camera (the texture)', 'after_flat_'),
            ('coverage: tint = the view that painted it (front red, q_left green, q_right blue, back yellow), '
             'dim = low weight, magenta = no view (filled)', 'coverage_')]
    tile = 640
    im = Image.new('RGB', (tile * 4, (tile + 40) * len(rows)), 'white')
    dr = ImageDraw.Draw(im)
    for r, (label, pre) in enumerate(rows):
        dr.text((12, r * (tile + 40) + 8), label, fill=(20, 20, 20), font=font)
        for c, v in enumerate(cols):
            p = os.path.join(bd, f'{pre}{v}.png')
            if os.path.exists(p):
                im.paste(Image.open(p).convert('RGB').resize((tile, tile), Image.LANCZOS), (c * tile, r * (tile + 40) + 40))
    im.save(os.path.join(out, 'board.png'))
    z = Image.new('RGB', (2048, 2048 + 80), 'white'); dz = ImageDraw.Draw(z)
    for c, (pre, lab) in enumerate((('before_', 'before'), ('after_', 'after'))):
        for r, v in enumerate(('front_zoom', 'q_left_zoom')):
            p = os.path.join(bd, f'{pre}{v}.png')
            if os.path.exists(p):
                z.paste(Image.open(p).convert('RGB'), (c * 1024, 40 + r * 1024 + (40 if r else 0)))
        dz.text((c * 1024 + 12, 8), lab + ' (85 mm, 0.55 m)', fill=(20, 20, 20), font=font)
    z.save(os.path.join(out, 'board_zoom.png'))
    L = Image.new('RGB', (4 * 768, 768 + 40), 'white'); dl = ImageDraw.Draw(L)
    for c, tag in enumerate(('0', '60', '-60', '90')):
        p = os.path.join(bd, f'after_light{tag}.png')
        if os.path.exists(p):
            L.paste(Image.open(p).convert('RGB').resize((768, 768), Image.LANCZOS), (c * 768, 40))
            dl.text((c * 768 + 12, 8), f'key light at {tag} deg', fill=(20, 20, 20), font=font)
    L.save(os.path.join(out, 'board_lights.png'))
    print('[paint] boards ->', out)


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    cmd = argv[0] if argv else ''
    opt = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d
    out = opt('--out', OUT)
    if cmd == 'views':
        demo_views(out)
    elif cmd == 'paint':
        o = opt('--only')
        demo_paint(out, only=o.split(',') if o else None, max_calls=int(opt('--max-calls', 4)), force='--force' in argv,
                   strict='--loose' not in argv, sub=opt('--sub', 'paint'))
    elif cmd == 'register':                 # re-run registration only (no image calls)
        for n in (opt('--only') or 'front,q_left,q_right,back').split(','):
            raw = os.path.join(out, 'paint', f'{n}_raw.png')
            if os.path.exists(raw):
                rep = register_painting(raw, os.path.join(out, 'views'), n, os.path.join(out, 'paint', f'{n}_paint.png'))
                print(n, json.dumps({k: rep.get(k) for k in ('before', 'after_ecc', 'final', 'local', 'trust')}))
    elif cmd == 'bake':
        demo_bake(out, int(opt('--head', 2048)), int(opt('--hair', 4096)))
    elif cmd == 'board':
        demo_board(out)
    elif cmd:
        print(__doc__)
