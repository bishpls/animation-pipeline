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
        render's shading normals with the outline on against off: faces whose normal turns more than 90 degrees (their
        corners' mean), the p90 / max turn, and the surface's inward move and the hull's outward move (median, m)
        -> OUT/normals.json
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
    """the evaluated mesh: (vertex positions (n, 3), face corner normals averaged per face (f, 3), loop totals)."""
    import bpy
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    oe = ob.evaluated_get(dg)
    me = oe.to_mesh()
    nv, nl, nf = len(me.vertices), len(me.loops), len(me.polygons)
    co = np.empty(nv * 3, np.float32); me.vertices.foreach_get('co', co)
    cn = np.empty(nl * 3, np.float32); me.corner_normals.foreach_get('vector', cn)
    ls = np.empty(nf, np.int32); me.polygons.foreach_get('loop_start', ls)
    lt = np.empty(nf, np.int32); me.polygons.foreach_get('loop_total', lt)
    fn = np.empty(nf * 3, np.float32); me.polygons.foreach_get('normal', fn)
    oe.to_mesh_clear()
    cn = cn.reshape(-1, 3)
    face_of = np.repeat(np.arange(nf), lt)
    acc = np.zeros((nf, 3)); np.add.at(acc, face_of, cn)
    acc /= np.maximum(np.linalg.norm(acc, axis=1, keepdims=True), 1e-12)
    return co.reshape(-1, 3), acc, fn.reshape(-1, 3)


def normals(out, bundle=None, height=None):
    """outline on against off, per outlined object and board width (module doc)."""
    import bpy
    from charkit import shade
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
        co0, n0, f0 = _eval(ob)
        mod.show_viewport = True
        for key, (mpp, ry) in widths.items():
            shade.set_view(0, mpp, ry)
            co, n1, f1 = _eval(ob)
            nf, nv = len(n0), len(co0)
            if len(n1) < nf or len(co) < 2 * nv:
                r['widths'][key] = {'unmatched': True}
                continue
            ang = np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i', n0, n1[:nf]), -1, 1)))
            angf = np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i', f0, f1[:nf]), -1, 1)))
            d_s, d_h = co[:nv] - co0, co[nv:2 * nv] - co0              # the surface's and the hull's moves
            span = d_h - d_s
            u = span / np.maximum(np.linalg.norm(span, axis=1, keepdims=True), 1e-12)
            inward = -np.einsum('ij,ij->i', d_s, u)
            outward = np.einsum('ij,ij->i', d_h, u)
            moved = np.linalg.norm(span, axis=1) > 1e-7
            r['widths'][key] = {
                'w_m': round(float(shade.line_width(ob, mpp, ry)), 7), 'offset': round(float(mod.offset), 5),
                'faces': int(nf), 'flipped_90': int((ang > 90).sum()), 'flipped_90_geom': int((angf > 90).sum()),
                'turn_p90': round(float(np.percentile(ang, 90)), 2), 'turn_max': round(float(ang.max()), 2),
                'turn_mean': round(float(ang.mean()), 3),
                'inward_m': round(float(np.median(inward[moved])), 7) if moved.any() else 0.0,
                'outward_m': round(float(np.median(outward[moved])), 7) if moved.any() else 0.0}
        shade.set_view(0)
    tot = {}
    for nm, r in rep['objects'].items():
        for key, w in r['widths'].items():
            t = tot.setdefault(r['region'] or '?', {}).setdefault(key, {'faces': 0, 'flipped_90': 0})
            t['faces'] += w.get('faces', 0); t['flipped_90'] += w.get('flipped_90', 0)
    rep['totals'] = tot
    json.dump(rep, open(os.path.join(out, 'normals.json'), 'w'), indent=1)
    print('LOOKPROBE normals', json.dumps(tot))
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
