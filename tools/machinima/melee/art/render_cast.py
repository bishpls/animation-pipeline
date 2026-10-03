"""render_cast.py: render Melee fighter glTFs (from `datkit export`) in Blender, plainly lit, at a common scale.

  blender -b --python render_cast.py -- JOB.json

JOB.json:
  {"out": DIR, "size": [w, h], "views": {"front": 0, "q34": 45, "side": 90, "back": 180},
   "fighters": [{"code": "Mr", "gltf": ".../Mr.gltf", "scale": 1.1, "head": [23, 24], "hands": [10, 32]}, ...],
   "renders": [
     {"kind": "views",  "codes": ["Mr"], "ortho": 26, "wire": false},              # OUT/views_Mr_front.png ...
     {"kind": "lineup", "codes": ["Mr", "Fx", ...], "ortho": 30, "gap": 3},        # OUT/lineup.png (+ lineup.json: px per unit)
     {"kind": "head",   "codes": ["Mr"], "views": ["front", "q34"], "wire": true, "closest": true}   # OUT/head_Mr_front.png
   ]}

Materials are rebuilt from the exporter's sidecar (XX.melee.json): every UV texture layer is combined the way Melee's
TObj colormap/alphamap ops say (replace, modulate, blend, alpha_mask, add), starting from the material's diffuse colour
(or the vertex colour when the MObj's VERTEX flag is set). Reflection/highlight/toon-coordinate layers are left out
(listed in the sidecar). `scale` applies the fighter's ftData ModelScale so fighters stand at in-game size.
Views rotate the fighter about the vertical axis; the camera and the light stay put, so every view is lit alike.
"""
import bpy, json, math, os, sys
from mathutils import Vector, Matrix

job = json.load(open(sys.argv[sys.argv.index('--') + 1]))
OUT = job['out']; os.makedirs(OUT, exist_ok=True)
W, H = job.get('size', [900, 1200])


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    sc.view_settings.view_transform = 'Standard'
    try: sc.eevee.taa_render_samples = 32
    except Exception: pass
    world = bpy.data.worlds.new('w'); sc.world = world; world.use_nodes = True
    bg = world.node_tree.nodes['Background']; bg.inputs[0].default_value = (1, 1, 1, 1); bg.inputs[1].default_value = 0.55
    sun = bpy.data.lights.new('key', 'SUN'); sun.energy = 2.2; sun.angle = 0.2
    so = bpy.data.objects.new('key', sun); sc.collection.objects.link(so)
    so.rotation_euler = (math.radians(50), 0, math.radians(-30))   # from front-left-above
    fill = bpy.data.lights.new('fill', 'SUN'); fill.energy = 0.6
    fo = bpy.data.objects.new('fill', fill); sc.collection.objects.link(fo); fo.rotation_euler = (math.radians(70), 0, math.radians(150))
    cam = bpy.data.cameras.new('cam'); cam.type = 'ORTHO'
    co = bpy.data.objects.new('cam', cam); sc.collection.objects.link(co); sc.camera = co
    return sc, co


def img_ext(w):
    return {'GX_REPEAT': 'REPEAT', 'REPEAT': 'REPEAT', 'GX_MIRROR': 'MIRROR', 'MIRROR': 'MIRROR'}.get(w, 'EXTEND')


def build_material(mat, info, gdir, uvnames, colname, closest):
    mat.use_nodes = True
    nt = mat.node_tree; nt.nodes.clear()
    N = lambda t, x, y: (lambda n: (setattr(n, 'location', (x, y)), n)[1])(nt.nodes.new(t))
    out = N('ShaderNodeOutputMaterial', 900, 0)
    flags = info.get('flags', [])
    dif = info.get('dif') or [255, 255, 255, 255]
    col = N('ShaderNodeRGB', -1200, 200); col.outputs[0].default_value = (dif[0] / 255, dif[1] / 255, dif[2] / 255, 1)
    c = col.outputs[0]
    if 'VERTEX' in flags and colname:
        a = N('ShaderNodeVertexColor', -1200, 0); a.layer_name = colname; c = a.outputs[0]
    alpha_v = N('ShaderNodeValue', -1200, -200); alpha_v.outputs[0].default_value = info.get('alpha', 1.0); a_out = alpha_v.outputs[0]
    uses_alpha = info.get('alpha', 1.0) < 0.999 or 'XLU' in flags
    x = -900
    for L in info.get('layers', []):
        t = L['info']
        # only diffuse-lightmap UV layers make the surface colour; specular-lightmap layers (Melee's specular maps, often on
        # a second UV set) scale the highlight, and reflection/highlight/toon coordinates are environment lookups
        if t['coord'] != 'uv' or not ('diffuse' in t['lightmaps'] or not t['lightmaps']):
            continue
        if not os.path.exists(os.path.join(gdir, L['png'])): continue
        uvn = N('ShaderNodeUVMap', x - 300, -400); uvn.uv_map = uvnames[min(t['uv'], len(uvnames) - 1)] if uvnames else ''
        mp = N('ShaderNodeMapping', x - 150, -400)
        sc_, off = L['xf']['sc'], L['xf']['off']
        mp.inputs['Scale'].default_value = (sc_[0], sc_[1], 1)
        mp.inputs['Location'].default_value = (off[0], 1 - sc_[1] - off[1], 0)   # glTF v-down to Blender v-up
        tx = N('ShaderNodeTexImage', x, -400)
        tx.image = bpy.data.images.load(os.path.join(gdir, L['png']), check_existing=True)
        tx.image.alpha_mode = 'STRAIGHT'
        tx.extension = img_ext(t['wrap'][0]); tx.interpolation = 'Closest' if closest else 'Linear'
        nt.links.new(uvn.outputs[0], mp.inputs[0]); nt.links.new(mp.outputs[0], tx.inputs[0])
        cm = t['colormap']
        if True:
            mix = N('ShaderNodeMix', x + 200, 100); mix.data_type = 'RGBA'
            if cm == 'replace': mix.blend_type = 'MIX'; mix.inputs[0].default_value = 1.0
            elif cm == 'modulate': mix.blend_type = 'MULTIPLY'; mix.inputs[0].default_value = 1.0
            elif cm == 'add': mix.blend_type = 'ADD'; mix.inputs[0].default_value = 1.0
            elif cm == 'sub': mix.blend_type = 'SUBTRACT'; mix.inputs[0].default_value = 1.0
            elif cm == 'blend': mix.blend_type = 'MIX'; mix.inputs[0].default_value = t.get('blend', 1.0)
            elif cm == 'alpha_mask': mix.blend_type = 'MIX'; nt.links.new(tx.outputs['Alpha'], mix.inputs[0])
            elif cm == 'rgb_mask': mix.blend_type = 'MIX'; nt.links.new(tx.outputs['Color'], mix.inputs[0])
            else: mix.inputs[0].default_value = 0.0
            nt.links.new(c, mix.inputs[6]); nt.links.new(tx.outputs['Color'], mix.inputs[7]); c = mix.outputs[2]
        am = t['alphamap']
        if am != 'none':
            uses_alpha = True
            m2 = N('ShaderNodeMath', x + 200, -150)
            if am == 'replace': m2.operation = 'MAXIMUM'; m2.inputs[0].default_value = 0; nt.links.new(tx.outputs['Alpha'], m2.inputs[1])
            elif am == 'modulate': m2.operation = 'MULTIPLY'; nt.links.new(a_out, m2.inputs[0]); nt.links.new(tx.outputs['Alpha'], m2.inputs[1])
            else: m2.operation = 'MAXIMUM'; nt.links.new(a_out, m2.inputs[0]); nt.links.new(tx.outputs['Alpha'], m2.inputs[1])
            a_out = m2.outputs[0]
        x += 450
    if 'CONSTANT' in flags and 'DIFFUSE' not in flags:
        sh = N('ShaderNodeEmission', 500, 0); nt.links.new(c, sh.inputs[0])
        shader = sh.outputs[0]
    else:
        sh = N('ShaderNodeBsdfPrincipled', 500, 0)
        nt.links.new(c, sh.inputs['Base Color'])
        sh.inputs['Roughness'].default_value = 0.55 if 'SPECULAR' in flags else 0.9
        try: sh.inputs['Specular IOR Level'].default_value = 0.35 if 'SPECULAR' in flags else 0.1
        except Exception: pass
        shader = sh.outputs[0]
        if uses_alpha: nt.links.new(a_out, sh.inputs['Alpha'])
    nt.links.new(shader, out.inputs[0])
    if uses_alpha:
        try: mat.surface_render_method = 'DITHERED'
        except Exception: mat.blend_method = 'HASHED'
    mat.use_backface_culling = False


def load_fighter(f, closest=False):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=f['gltf'])
    new = [o for o in bpy.data.objects if o not in before]
    gdir = os.path.dirname(f['gltf'])
    sp = f['gltf'].rsplit('.', 1)[0] + '.melee.json'      # datkit's sidecar; a model from Blender keeps its own materials
    byname = {m['name']: m for m in json.load(open(sp))['materials']} if os.path.exists(sp) else {}
    root = bpy.data.objects.new('root_' + f['code'], None); bpy.context.scene.collection.objects.link(root)
    for o in new:
        if o.parent is None: o.parent = root
    meshes = [o for o in new if o.type == 'MESH' and any(m.type == 'ARMATURE' for m in o.modifiers)]
    if not meshes: meshes = [o for o in new if o.type == 'MESH']   # an unskinned model
    for o in new:   # the importer's bone-display shapes (an icosphere) are not part of the fighter
        if o.type == 'MESH' and o not in meshes: o.hide_render = True; o.hide_viewport = True
    for o in meshes:
        me = o.data
        uvn = [u.name for u in me.uv_layers]
        coln = me.color_attributes[0].name if len(me.color_attributes) else None
        for m in me.materials:
            info = byname.get(m.name.split('.')[0])
            if info: build_material(m, info, gdir, uvn, coln, closest)
    s = f.get('scale', 1.0)
    root.scale = (s, s, s)
    bpy.context.view_layer.update()
    return root, meshes


def bbox(meshes, groups=None):
    """world bbox of the meshes; with groups (joint indices), only vertices whose strongest weight is in that set."""
    lo = Vector((1e9, 1e9, 1e9)); hi = Vector((-1e9, -1e9, -1e9)); n = 0
    for o in meshes:
        dg = bpy.context.evaluated_depsgraph_get(); ev = o.evaluated_get(dg); me = ev.to_mesh()
        names = {vg.index: vg.name for vg in o.vertex_groups}
        want = None if groups is None else {f'J{g:02d}' for g in groups}
        for v in me.vertices:
            if want is not None:
                if not v.groups: continue
                g = max(v.groups, key=lambda g: g.weight)
                if names.get(g.group) not in want: continue
            p = o.matrix_world @ v.co
            lo = Vector(map(min, lo, p)); hi = Vector(map(max, hi, p)); n += 1
        ev.to_mesh_clear()
    return lo, hi, n


def add_wire(meshes, thick):
    wm = bpy.data.materials.get('wire') or bpy.data.materials.new('wire')
    wm.use_nodes = True; nt = wm.node_tree; nt.nodes.clear()
    e = nt.nodes.new('ShaderNodeEmission'); e.inputs[0].default_value = (0.02, 0.02, 0.05, 1); o = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(e.outputs[0], o.inputs[0])
    wires = []
    for m in meshes:
        w = m.copy(); w.data = m.data.copy(); bpy.context.scene.collection.objects.link(w)
        w.data.materials.clear(); w.data.materials.append(wm)
        md = w.modifiers.new('wf', 'WIREFRAME'); md.thickness = thick; md.use_replace = True; md.use_even_offset = True; md.offset = 0.6
        w.parent = m.parent; w.matrix_world = m.matrix_world.copy()
        wires.append(w)
    return wires


def frame(cam, center, ortho, yaw_deg=0):
    cam.data.ortho_scale = ortho; cam.data.sensor_fit = 'HORIZONTAL'   # ortho_scale spans the width
    cam.location = center + Vector((0, -200, 0))
    cam.rotation_euler = (math.radians(90), 0, 0)
    cam.data.clip_start = 1; cam.data.clip_end = 1000


def render(path):
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


F = {f['code']: f for f in job['fighters']}
VIEWS = job.get('views', {'front': 0, 'q34': 45, 'side': 90, 'back': 180})
meta = {}
for R in job['renders']:
    kind = R['kind']
    if kind == 'lineup':
        # rows of fighters side by side at in-game scale; every row shares one scale (the widest row fills the frame)
        rows = R.get('rows') or [R['codes']]; yaw = math.radians(R.get('yaw', 0)); gap = R.get('gap', 3)
        widths = []; maxh = 0
        for row in rows:
            tot = 0
            for code in row:
                reset(); root, meshes = load_fighter(F[code]); root.rotation_euler = (0, 0, yaw); bpy.context.view_layer.update()
                lo, hi, _ = bbox(meshes); tot += hi.x - lo.x + gap; maxh = max(maxh, hi.z)
            widths.append(tot - gap)
        ortho = max(widths) * 1.03
        # frame height: the tallest fighter plus 8% headroom above, floor 8% above the bottom
        aspect = maxh * 1.08 / 0.92 / ortho
        for ri, row in enumerate(rows):
            sc, cam = reset()
            sc.render.resolution_x = R.get('w', 3000); sc.render.resolution_y = int(R.get('w', 3000) * aspect)
            x = 0; placed = []; hmax = 0
            for code in row:
                root, meshes = load_fighter(F[code]); root.rotation_euler = (0, 0, yaw); bpy.context.view_layer.update()
                lo, hi, _ = bbox(meshes)
                root.location.x += x - lo.x; root.location.y += (ri % 2) * 0.0
                placed.append([code, x, x + hi.x - lo.x, hi.z - lo.z, lo.z]); x += hi.x - lo.x + gap
            total = x - gap
            ortho_h = ortho * sc.render.resolution_y / sc.render.resolution_x
            frame(cam, Vector((total / 2, 0, ortho_h / 2 - ortho_h * 0.08)), ortho)
            name = f"{R.get('name', 'lineup')}_{ri}"
            render(os.path.join(OUT, name + '.png'))
            ppu = sc.render.resolution_x / ortho
            meta[name] = {'ppu': ppu, 'floor_px': sc.render.resolution_y * 0.92, 'x0_px': sc.render.resolution_x / 2 - total / 2 * ppu,
                          'placed': placed, 'res': [sc.render.resolution_x, sc.render.resolution_y]}
    elif kind in ('views', 'head'):
        asp = R.get('size', [W, H])[1] / R.get('size', [W, H])[0]
        common = None
        if R.get('common') and kind == 'views':   # one scale for every fighter in this render: fit the largest
            common = 0
            for code in R.get('measure', R['codes']):   # measure may list more fighters than this run renders
                reset(); _, meshes = load_fighter(F[code]); lo, hi, _ = bbox(meshes)
                common = max(common, max(hi.x - lo.x, hi.y - lo.y), (hi.z - lo.z) / asp)
            common *= R.get('pad', 1.08)
        for code in R['codes']:
            sc, cam = reset()
            sc.render.resolution_x, sc.render.resolution_y = R.get('size', [W, H])
            root, meshes = load_fighter(F[code], closest=R.get('closest', False))
            lo, hi, n = bbox(meshes, F[code]['head']) if kind == 'head' else bbox(meshes)
            ctr = (lo + hi) / 2
            wid = max(hi.x - lo.x, hi.y - lo.y); hgt = hi.z - lo.z
            ortho = R.get('ortho') or common or max(wid, hgt / asp) * R.get('pad', 1.2)
            if R.get('wire'):   # line width a fixed fraction of the frame, in the fighter's own (unscaled) units
                add_wire(meshes, R.get('thick', 0.0012) * ortho / F[code].get('scale', 1.0))
            if kind == 'views':   # feet on a common floor 6% above the bottom edge
                center = Vector((ctr.x, 0, lo.z - ortho * asp * 0.06 + ortho * asp / 2))
            else:
                center = ctr
            for vname in R.get('views', list(VIEWS)):
                rot = Matrix.Rotation(math.radians(VIEWS[vname]), 4, 'Z')
                root.rotation_euler = (0, 0, math.radians(VIEWS[vname]))
                pivot = Vector((ctr.x, ctr.y, 0))                 # turn about the fighter's (or head's) vertical axis
                root.location = pivot - rot @ pivot
                bpy.context.view_layer.update()
                frame(cam, center, ortho)
                render(os.path.join(OUT, f"{R.get('name', kind)}_{code}_{vname}.png"))
            meta[f"{R.get('name', kind)}_{code}"] = {'ortho': ortho, 'res': [sc.render.resolution_x, sc.render.resolution_y],
                                                     'ppu': sc.render.resolution_x / ortho, 'bbox': [list(lo), list(hi)], 'n': n}
json.dump(meta, open(os.path.join(OUT, job.get('meta', 'render_meta.json')), 'w'), indent=1)
