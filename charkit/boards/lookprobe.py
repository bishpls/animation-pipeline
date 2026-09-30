"""The look's measurements in Blender (calls H and I, docs/workstreams/look.md): what EEVEE itself computes, on this
machine's GPU, from a saved build or a scratch scene.

    blender -b --factory-startup --python charkit/boards/lookprobe.py -- OUT --hash
        the streaks' hash: White Noise 1D (charkit.shade.hair_toon's) rendered for column indices 0..63 and read back in
        three 11-bit windows fract(v 2^(11 k)) (EEVEE's film is half float), against charkit.shade.streak_hash
        -> OUT/hash.json {value, green: columns matching, worst difference in fp16 steps; device}
    blender -b BUILD/NAME.blend --python charkit/boards/lookprobe.py -- OUT --boards views,body [--bundle DIR]
            [--height M] [--streaks off] [--cap 0]
        scene.boards' views and body boards re-rendered from the saved scene on this machine (the build's own code path:
        scene.boards with the scene's objects), into OUT/NAME.png. --streaks off: the hair highlight's amount 0 (EEVEE's
        own picture without streaks, to find them); --cap 0: a scene saved before call I rendered without the cap
        -> OUT/boards.json {device, boards}
    blender -b BUILD/NAME.blend --python charkit/boards/lookprobe.py -- OUT --normals [--bundle DIR] [--height M]
        per outlined object and line width (the build's, the face boards', the body boards': shade.set_view's), the
        render's shading normals with the outline on against off: faces whose shading turns more than 90 degrees (their
        corners' mean cos < 0), on a thin shell's two layers and on its rim band apart, and away from its rounded edge
        (the rim and two rings of faces round it: edge_zone), geometric flips, the layers' p90 / max corner turn, and
        the surface's inward move and the hull's outward move (median, m)
        -> OUT/normals.json
    blender -b BUILD/NAME.blend --python charkit/boards/lookprobe.py -- OUT --thickness
        per outlined object its measured thickness (shade.measured_thickness: the p5 of its vertices' inward rays to its
        far side, the outline off), beside what the build stored (ck_line_thick, ck_line_cap) and its shell
        -> OUT/thickness.json
"""
import json, math, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import numpy as np


def _device():
    try:
        import gpu
        return {'device': gpu.platform.renderer_get(), 'backend': gpu.platform.backend_type_get(),
                'vendor': gpu.platform.vendor_get()}
    except Exception as e:                                          # noqa: BLE001
        return {'device': repr(e)}


def hash_check(out):
    import bpy
    from charkit import shade
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.view_settings.view_transform = 'Standard'
    sc.render.resolution_x, sc.render.resolution_y = 64, 4
    sc.render.image_settings.file_format = 'OPEN_EXR'; sc.render.image_settings.color_depth = '32'
    sc.render.filter_size = 0.0
    sc.world = bpy.data.worlds.new('w')
    bpy.ops.mesh.primitive_plane_add(size=2)
    pl = bpy.context.active_object
    mat = bpy.data.materials.new('h'); mat.use_nodes = True; nt = mat.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    N, L = nt.nodes.new, nt.links.new
    o = N('ShaderNodeOutputMaterial'); em = N('ShaderNodeEmission')
    tc = N('ShaderNodeTexCoord'); sx = N('ShaderNodeSeparateXYZ'); L(tc.outputs['UV'], sx.inputs[0])
    mul = N('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = 64.0; L(sx.outputs['X'], mul.inputs[0])
    fl = N('ShaderNodeMath'); fl.operation = 'FLOOR'; L(mul.outputs[0], fl.inputs[0])
    wn = N('ShaderNodeTexWhiteNoise'); wn.noise_dimensions = '1D'; L(fl.outputs[0], wn.inputs['W'])
    sep = N('ShaderNodeSeparateColor'); L(wn.outputs['Color'], sep.inputs['Color'])
    cmb = N('ShaderNodeCombineColor')
    L(cmb.outputs[0], em.inputs['Color']); L(em.outputs[0], o.inputs['Surface'])
    pl.data.materials.append(mat)
    cam = bpy.data.objects.new('c', bpy.data.cameras.new('c')); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = 2.0; cam.location = (0, 0, 1)
    res = {'device': _device()}
    h1, h2 = shade.streak_hash(64)
    for name, src, ref in (('value', wn.outputs['Value'], h1), ('green', sep.outputs['Green'], h2)):
        for k, ch in enumerate(('Red', 'Green', 'Blue')):
            m = N('ShaderNodeMath'); m.operation = 'MULTIPLY'; m.inputs[1].default_value = float(2 ** (11 * k))
            L(src, m.inputs[0])
            f = N('ShaderNodeMath'); f.operation = 'FRACT'; L(m.outputs[0], f.inputs[0])
            L(f.outputs[0], cmb.inputs[ch])
        p = os.path.join(out, 'hash_%s.exr' % name)
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(p)
        row = np.array(img.pixels[:], np.float32).reshape(4, 64, 4)[2, :, :3]
        bpy.data.images.remove(img)
        ok = np.ones(64, bool); worst = 0.0
        for k in range(3):
            want = np.mod(ref.astype(np.float32) * np.float32(2 ** (11 * k)), np.float32(1.0))
            step = np.maximum(np.spacing(np.float16(np.maximum(want, 2 ** -14))).astype(np.float32), 2 ** -24)
            d = np.abs(row[:, k] - want)
            ok &= d <= step * 1.0001
            worst = max(worst, float((d / step).max()))
        res[name] = {'columns_matching': int(ok.sum()), 'of': 64, 'worst_in_fp16_steps': round(worst, 3)}
    json.dump(res, open(os.path.join(out, 'hash.json'), 'w'), indent=1)
    print('LOOKPROBE hash', json.dumps(res))
    return res


def _bundle_meta(bundle):
    p = os.path.join(bundle, 'bundle.json') if bundle else None
    return json.load(open(p)) if p and os.path.exists(p) else {}


class _Scene:
    """what scene.boards reads of a build's Scene, found in a saved scene (and its bundle's assembly)."""

    def __init__(self, meta, height):
        import bpy
        a = meta.get('assembly') or {}
        objs = [o for o in bpy.data.objects if o.type == 'MESH']
        skin = next(o for o in objs if o.name.endswith('_skin'))
        groups = {r['name']: r.get('group') for r in meta.get('objects') or []}
        irises = [o for o in objs if o.name.startswith('iris_')]
        eye_z = a.get('eye_z')
        if eye_z is None:
            eye_z = float(np.mean([(o.matrix_world @ v.co).z for o in irises for v in o.data.vertices]))
        L = a.get('L') or float(max((skin.matrix_world @ v.co).z for v in skin.data.vertices)) / 5.9
        self.character = {'data': {'head': {'eye_z': float(eye_z), 'L': float(L)}}, 'skin': skin}
        self.features = [o for o in objs if o.name.startswith(('sclera_', 'iris_', 'lash_', 'brow_')) and not o.hide_render]
        self.covers = [o for o in objs if not o.hide_render and (groups.get(o.name) in ('hair', 'accessory')
                                                                or (not groups and o.name.startswith('hair_')))]
        self.spec = {'body': {'height_m': float(height)}}


def boards(out, which, bundle=None, height=None, streaks=True):
    import bpy
    from charkit import scene
    meta = _bundle_meta(bundle)
    if height is None:
        height = (meta.get('spec') or {}).get('body', {}).get('height_m') or 1.6
    S = _Scene(meta, height)
    if not streaks:
        for m in bpy.data.materials:
            nd = m.node_tree.nodes.get('ck_hl_amount') if m.use_nodes and m.node_tree else None
            if nd is not None:
                nd.inputs[1].default_value = 0.0
    made = scene.boards(S, out, which)
    rep = {'device': _device(), 'boards': [os.path.basename(p) for p in made], 'eye_z': S.character['data']['head'],
           'height': height, 'streaks': streaks, 'covers': len(S.covers), 'features': len(S.features)}
    json.dump(rep, open(os.path.join(out, 'boards.json'), 'w'), indent=1)
    print('LOOKPROBE boards', json.dumps(rep))
    return rep


def _eval(ob):
    """the evaluated mesh -> dict: co (n, 3); per corner: vertex, face, normal (the render's shading normal); per face:
    normal (geometric), loop_total."""
    import bpy
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    oe = ob.evaluated_get(dg)
    me = oe.to_mesh()
    nv, nl, nf = len(me.vertices), len(me.loops), len(me.polygons)
    co = np.empty(nv * 3, np.float32); me.vertices.foreach_get('co', co)
    cn = np.empty(nl * 3, np.float32); me.corner_normals.foreach_get('vector', cn)
    lv = np.empty(nl, np.int32); me.loops.foreach_get('vertex_index', lv)
    lt = np.empty(nf, np.int32); me.polygons.foreach_get('loop_total', lt)
    fn = np.empty(nf * 3, np.float32); me.polygons.foreach_get('normal', fn)
    oe.to_mesh_clear()
    return dict(co=co.reshape(-1, 3), lv=lv, lf=np.repeat(np.arange(nf), lt), ln=cn.reshape(-1, 3), fn=fn.reshape(-1, 3),
                lt=lt)


def _faces(ob, **show):
    """the evaluated face count with some modifiers shown or hidden (name=True/False), restored after."""
    import bpy
    saved = {k: ob.modifiers[k].show_viewport for k in show if k in ob.modifiers}
    try:
        for k, v in show.items():
            if k in ob.modifiers:
                ob.modifiers[k].show_viewport = v
        bpy.context.view_layer.update()
        oe = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
        me = oe.to_mesh()
        lt = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get('loop_total', lt)
        oe.to_mesh_clear()
        return lt
    finally:
        for k, v in saved.items():
            ob.modifiers[k].show_viewport = v


def rim_faces(ob, nf):
    """which of the rendered faces (outline off, nf of them) are a thin shell's rim: the 'thick' SOLIDIFY's rim faces
    (its output after the two layers) as the subdivision after it splits them (each face into its corner count, in
    order, so they come last) -> bool (nf,)."""
    rim = np.zeros(nf, bool)
    th = ob.modifiers.get('thick')
    if th is None or th.type != 'SOLIDIFY' or not th.use_rim:
        return rim
    base = _faces(ob, thick=False, sub=False, outline=False)
    lt = _faces(ob, thick=True, sub=False, outline=False)
    sub = ob.modifiers.get('sub')
    k = int(lt.sum()) if sub is not None and sub.show_viewport and sub.levels == 1 else len(lt)
    n_rim = int(lt[2 * len(base):].sum()) if k == int(lt.sum()) else len(lt) - 2 * len(base)
    if k != nf:
        return None                                              # not the layout assumed: unknown
    rim[nf - n_rim:] = True
    return rim


def edge_zone(off, rim, rings=2):
    """the rim band and the faces within `rings` rings of it (their vertices shared): the rounded edge the subdivision
    makes of a shell's rim -> bool (nf,)."""
    z = rim.copy()
    nv = int(off['lv'].max()) + 1 if len(off['lv']) else 0
    for _ in range(rings):
        vz = np.zeros(nv, bool); vz[off['lv'][z[off['lf']]]] = True
        z = np.zeros_like(z); np.logical_or.at(z, off['lf'], vz[off['lv']])
        z |= rim
    return z


def _match(off, on):
    """the outline-on mesh's corners on the original faces, matched to the outline-off mesh's by (face, vertex) (the
    SOLIDIFY keeps the original faces and vertices first) -> (off corner index, on corner index)."""
    nf = len(off['lt'])
    sel = np.nonzero(on['lf'] < nf)[0]
    ka = off['lf'].astype(np.int64) * (1 << 32) + off['lv']
    kb = on['lf'][sel].astype(np.int64) * (1 << 32) + on['lv'][sel]
    ia, ib = np.argsort(ka, kind='stable'), np.argsort(kb, kind='stable')
    if len(ia) != len(ib) or not np.array_equal(ka[ia], kb[ib]):
        return None
    return ia, sel[ib]


def normals(out, bundle=None, height=None):
    """outline on against off, per outlined object and board width (module doc): a face's shading is flipped where its
    corners' normals turn more than 90 degrees on average (mean cos < 0); geometric flips by its face normal; a thin
    shell's rim band (rim_faces) apart from its two layers."""
    from charkit import shade
    import bpy
    meta = _bundle_meta(bundle)
    if height is None:
        height = (meta.get('spec') or {}).get('body', {}).get('height_m') or 1.6
    face_mpp = 1.0 * 36.0 / 85.0 / 900.0                           # scene.boards: 85 mm at 1.0 m, 900 px
    body_mpp = height * 1.12 / 1000.0                              # orthographic, 1000 px tall
    widths = {'build': (None, None), 'face': (face_mpp, 900), 'body': (body_mpp, 1000)}
    obs = [o for o in bpy.data.objects if o.type == 'MESH' and 'ck_line_w' in o and not o.hide_render]
    rep = {'device': _device(), 'cap_share': shade.SHELL_CAP, 'objects': {}}
    for ob in obs:
        mod = ob.modifiers.get('outline')
        if mod is None:
            continue
        r = rep['objects'].setdefault(ob.name, {'region': ob.get('ck_line_region'), 'shell_m': shade.shell_of(ob),
                                                'cap_m': shade.line_cap(ob), 'widths': {}})
        mod.show_viewport = False
        off = _eval(ob)
        mod.show_viewport = True
        nf, nv = len(off['lt']), len(off['co'])
        rim = rim_faces(ob, nf)
        r['rim_faces'] = None if rim is None else int(rim.sum())
        if rim is None:
            rim = np.zeros(nf, bool)
        edge = edge_zone(off, rim)
        r['edge_faces'] = int(edge.sum())
        for key, (mpp, ry) in widths.items():
            shade.set_view(0, mpp, ry)
            on = _eval(ob)
            m = _match(off, on) if len(on['co']) >= 2 * nv else None
            if m is None:
                r['widths'][key] = {'unmatched': True}
                continue
            ia, ib = m
            cos = np.einsum('ij,ij->i', off['ln'][ia], on['ln'][ib])
            fcos = np.bincount(off['lf'][ia], cos, minlength=nf) / np.maximum(off['lt'], 1)
            flip = fcos < 0                                         # the face's shading turned > 90 degrees
            gflip = np.einsum('ij,ij->i', off['fn'], on['fn'][:nf]) < 0
            turn = np.degrees(np.arccos(np.clip(cos, -1, 1)))
            layer_c = ~rim[off['lf'][ia]]
            d_s, d_h = on['co'][:nv] - off['co'], on['co'][nv:2 * nv] - off['co']   # the surface's and the hull's moves
            span = d_h - d_s
            u = span / np.maximum(np.linalg.norm(span, axis=1, keepdims=True), 1e-12)
            moved = np.linalg.norm(span, axis=1) > 1e-7
            r['widths'][key] = {
                'w_m': round(float(shade.line_width(ob, mpp, ry)), 7), 'offset': round(float(mod.offset), 5),
                'faces': int(nf), 'flipped_90': int(flip.sum()), 'flipped_90_layers': int((flip & ~rim).sum()),
                'flipped_90_rim': int((flip & rim).sum()), 'flipped_90_away': int((flip & ~edge).sum()),
                'geom_flipped_layers': int((gflip & ~rim).sum()), 'geom_flipped_away': int((gflip & ~edge).sum()),
                'geom_flipped_rim': int((gflip & rim).sum()),
                'turn_p90_layers': round(float(np.percentile(turn[layer_c], 90)), 2) if layer_c.any() else 0.0,
                'turn_max_layers': round(float(turn[layer_c].max()), 2) if layer_c.any() else 0.0,
                'inward_m': round(float(np.median(-np.einsum('ij,ij->i', d_s, u)[moved])), 7) if moved.any() else 0.0,
                'outward_m': round(float(np.median(np.einsum('ij,ij->i', d_h, u)[moved])), 7) if moved.any() else 0.0}
        shade.set_view(0)
    tot = {}
    for nm, r in rep['objects'].items():
        for key, w in r['widths'].items():
            t = tot.setdefault(r['region'] or '?', {}).setdefault(key, {'faces': 0, 'flipped_90': 0, 'flipped_90_layers': 0,
                                                                         'flipped_90_rim': 0, 'flipped_90_away': 0})
            for k in t:
                t[k] += w.get(k, 0)
    rep['totals'] = tot
    json.dump(rep, open(os.path.join(out, 'normals.json'), 'w'), indent=1)
    print('LOOKPROBE normals', json.dumps(tot))
    return rep


def thickness(out):
    """per outlined object: its measured thickness now (the saved scene's evaluated mesh), and what the build stored."""
    from charkit import shade
    import bpy
    rep = {}
    for ob in [o for o in bpy.data.objects if o.type == 'MESH' and 'ck_line_w' in o and not o.hide_render]:
        rep[ob.name] = {'region': ob.get('ck_line_region'), 'shell_m': shade.shell_of(ob),
                        'thickness_m': shade.measured_thickness(ob), 'stored_thick_m': ob.get('ck_line_thick'),
                        'cap_m': shade.line_cap(ob)}
    json.dump(rep, open(os.path.join(out, 'thickness.json'), 'w'), indent=1)
    print('LOOKPROBE thickness', json.dumps({k: v for k, v in rep.items() if v['stored_thick_m'] is not None}))
    return rep


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:]
    opt = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d
    out = os.path.abspath(argv[0])
    os.makedirs(out, exist_ok=True)
    if opt('--cap') is not None:
        from charkit import shade
        shade.SHELL_CAP = float(opt('--cap'))
    if '--hash' in argv:
        hash_check(out)
    height = float(opt('--height')) if opt('--height') else None
    if '--boards' in argv:
        boards(out, tuple(opt('--boards').split(',')), opt('--bundle'), height, opt('--streaks', 'on') != 'off')
    if '--normals' in argv:
        normals(out, opt('--bundle'), height)
    if '--thickness' in argv:
        thickness(out)
