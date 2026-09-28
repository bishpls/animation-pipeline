"""Character-build kit for headless Blender 5.2 (bpy): cel materials, inverted-hull outlines, mesh helpers, hair locks, a
VRM-humanoid armature from a joint table, and render setup. Lifted from EMBER Round 5 (legacy/ember/r5/char.py) and
generalised; a character script (clawd.py) supplies the joints, radii, palette and parts. Promote to engine/ or tools/ on
its second character (docs/PIPELINE_3D.md, phase 3).

Conventions: metres, Z up, the character faces -Y, her left is +X. Colours are authored as sRGB 0-1 and linearised here.
All shading is emission (an art-directed light vector, not scene lights), so renders have no sampling noise and the look is
set per shot with set_light().
"""
import math
import bpy, bmesh
from mathutils import Vector, Quaternion, Matrix

MATS = {}
LDIR = [0.35, -0.55, 0.75]      # direction TO the key light, world space
LINE = (0.23, 0.12, 0.10)


def lin(c):
    return tuple(x ** 2.2 for x in c)


def hexc(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _clear(nt):
    for n in list(nt.nodes):
        nt.nodes.remove(n)


def toon(name, base, shade, rim=(1.0, 0.95, 0.9), rim_amt=0.25, thresh=0.45, soft=0.015):
    """Two-tone cel ramp on N.L (N.L from the art-directed light) + a fresnel rim, as emission."""
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; _clear(nt)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    ld = nt.nodes.new('ShaderNodeCombineXYZ'); ld.name = 'ldir'
    for i in range(3):
        ld.inputs[i].default_value = LDIR[i]
    dot = nt.nodes.new('ShaderNodeVectorMath'); dot.operation = 'DOT_PRODUCT'
    nt.links.new(geo.outputs['Normal'], dot.inputs[0]); nt.links.new(ld.outputs[0], dot.inputs[1])
    half = nt.nodes.new('ShaderNodeMath'); half.operation = 'MULTIPLY_ADD'
    half.inputs[1].default_value = 0.5; half.inputs[2].default_value = 0.5
    nt.links.new(dot.outputs['Value'], half.inputs[0])
    ramp = nt.nodes.new('ShaderNodeValToRGB'); ramp.name = 'ramp'
    e0, e1 = ramp.color_ramp.elements
    e0.position, e1.position = thresh - soft, thresh + soft
    e0.color, e1.color = (0, 0, 0, 1), (1, 1, 1, 1)
    nt.links.new(half.outputs[0], ramp.inputs[0])
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'
    mix.inputs['A'].default_value = (*lin(shade), 1); mix.inputs['B'].default_value = (*lin(base), 1)
    nt.links.new(ramp.outputs['Color'], mix.inputs['Factor'])
    lw = nt.nodes.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.3
    rr = nt.nodes.new('ShaderNodeValToRGB')
    rr.color_ramp.elements[0].position, rr.color_ramp.elements[1].position = 0.62, 0.66
    rr.color_ramp.elements[0].color, rr.color_ramp.elements[1].color = (0, 0, 0, 1), (1, 1, 1, 1)
    nt.links.new(lw.outputs['Facing'], rr.inputs[0])
    lit = nt.nodes.new('ShaderNodeMath'); lit.operation = 'MULTIPLY'            # rim only on the lit side
    nt.links.new(rr.outputs['Color'], lit.inputs[0]); nt.links.new(ramp.outputs['Color'], lit.inputs[1])
    amt = nt.nodes.new('ShaderNodeMath'); amt.operation = 'MULTIPLY'; amt.inputs[1].default_value = rim_amt
    nt.links.new(lit.outputs[0], amt.inputs[0])
    rim_mix = nt.nodes.new('ShaderNodeMix'); rim_mix.data_type = 'RGBA'; rim_mix.blend_type = 'SCREEN'
    rim_mix.inputs['B'].default_value = (*lin(rim), 1)
    nt.links.new(amt.outputs[0], rim_mix.inputs['Factor']); nt.links.new(mix.outputs['Result'], rim_mix.inputs['A'])
    em = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(rim_mix.outputs['Result'], em.inputs['Color']); nt.links.new(em.outputs[0], out.inputs['Surface'])
    MATS[name] = m
    return m


def toon3(name, lit, shade, deep, thresh=0.5, deep_thresh=0.27, soft=0.012, rim=(1.0, 0.95, 0.9), rim_amt=0.18):
    """Three tones on half-lambert N.L: deep core shadow | shadow | lit, hard steps, plus a lit-side fresnel rim, as
    emission. The node named 'ramp' outputs the lit mask (0 in shadow, 1 lit) for extra terms (hair highlights)."""
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; _clear(nt)
    N = nt.nodes.new; L = nt.links.new
    out = N('ShaderNodeOutputMaterial'); geo = N('ShaderNodeNewGeometry')
    ld = N('ShaderNodeCombineXYZ'); ld.name = 'ldir'
    for i in range(3):
        ld.inputs[i].default_value = LDIR[i]
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
    m1 = N('ShaderNodeMix'); m1.data_type = 'RGBA'
    m1.inputs['A'].default_value = (*lin(deep), 1); m1.inputs['B'].default_value = (*lin(shade), 1)
    L(s_deep.outputs['Color'], m1.inputs['Factor'])
    m2 = N('ShaderNodeMix'); m2.data_type = 'RGBA'; m2.inputs['B'].default_value = (*lin(lit), 1)
    L(m1.outputs['Result'], m2.inputs['A']); L(s_lit.outputs['Color'], m2.inputs['Factor'])
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
    MATS[name] = m
    return m


def set_rim(color, amt=None):
    """Re-tint every cel material's rim light (a stage's colour), optionally with a new strength."""
    for m in MATS.values():
        nt = m.node_tree
        if nt and 'rim_mix' in nt.nodes:
            nt.nodes['rim_mix'].inputs['B'].default_value = (*lin(color), 1)
            if amt is not None and 'rim_amt' in nt.nodes:
                nt.nodes['rim_amt'].inputs[1].default_value = amt


def flat(name, color):
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; _clear(nt)
    out = nt.nodes.new('ShaderNodeOutputMaterial'); em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (*lin(color), 1)
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    MATS[name] = m
    return m


def decal(name, path):
    """An alpha-textured emission decal (face features); UVs come from the shell's projection."""
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; _clear(nt)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = bpy.data.images.load(path); tex.extension = 'CLIP'
    em = nt.nodes.new('ShaderNodeEmission'); tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mx = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(tex.outputs['Color'], em.inputs['Color']); nt.links.new(tex.outputs['Alpha'], mx.inputs['Fac'])
    nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(em.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs['Surface'])
    m.surface_render_method = 'BLENDED'
    m.use_backface_culling = True
    MATS[name] = m
    return m


def set_light(d):
    v = Vector(d).normalized()
    for m in MATS.values():
        if m.node_tree and 'ldir' in m.node_tree.nodes:
            n = m.node_tree.nodes['ldir']
            for i in range(3):
                n.inputs[i].default_value = v[i]


def add_outline(ob, thick=0.003, color=None):
    """Inverted hull: a flipped, back-face-culled solidify shell in the line colour."""
    m = flat('outline' if color is None else f'outline_{color}', color or LINE)
    m.use_backface_culling = True
    ob.data.materials.append(m)
    so = ob.modifiers.new('outline', 'SOLIDIFY')
    so.thickness = -thick; so.offset = 1.0; so.use_flip_normals = True; so.use_rim = False
    so.material_offset = len(ob.data.materials) - 1
    return so


def link(ob, coll=None):
    (coll or bpy.context.scene.collection).objects.link(ob)
    return ob


def mesh_from_bm(name, bm, mats=(), smooth=True):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    for m in mats:
        me.materials.append(m)
    for p in me.polygons:
        p.use_smooth = smooth
    return link(bpy.data.objects.new(name, me))


def bone_parent(ob, arm, bone):
    bpy.context.view_layer.update()
    mw = ob.matrix_world.copy()
    ob.parent = arm; ob.parent_type = 'BONE'; ob.parent_bone = bone
    ob.matrix_world = mw


def skin_to(ob, arm, weights):
    """Skin a mesh with explicit per-vertex weights: weights(co) -> {bone: w}."""
    groups = {}
    for v in ob.data.vertices:
        for b, w in weights(v.co).items():
            if w <= 1e-4:
                continue
            g = groups.get(b) or ob.vertex_groups.new(name=b)
            groups[b] = g
            g.add([v.index], w, 'REPLACE')
    mod = ob.modifiers.new('rig', 'ARMATURE'); mod.object = arm
    ob.parent = arm
    ob.modifiers.move(ob.modifiers.find(mod.name), 0)     # deform first, so the outline shell follows the pose
    return mod


def armature(name, bones, head_of, tail_of):
    """bones: {name: (head joint, tail joint or None, parent)}; head_of/tail_of map a joint to a Vector."""
    ad = bpy.data.armatures.new(name)
    arm = link(bpy.data.objects.new(name, ad))
    bpy.context.view_layer.objects.active = arm
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = ad.edit_bones
    for n, (h, t, par) in bones.items():
        b = eb.new(n)
        b.head = head_of(h)
        b.tail = tail_of(t) if t else head_of(h) + Vector((0, 0, 0.12))
    for n, (h, t, par) in bones.items():
        if par:
            eb[n].parent = eb[par]
            eb[n].use_connect = False
    # legs and spine roll to face forward; arms roll so the elbow hinge axis is consistent
    for n in eb.keys():
        eb[n].align_roll(Vector((0, -1, 0)))
    bpy.ops.object.mode_set(mode='OBJECT')
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    return arm


# hair: a tapered ribbon lock along a path (list of Vectors), flattened across `normal_from` (the head centre)
def lock(bm, pts, width, centre, thick=0.45, taper=0.9, tip=0.02):
    n = len(pts) - 1
    ring = []
    for i, c in enumerate(pts):
        d = (pts[min(i + 1, n)] - pts[max(i - 1, 0)]).normalized()
        out = (c - centre)
        out = out.normalized() if out.length > 1e-6 else Vector((0, -1, 0))
        side = d.cross(out)
        side = side.normalized() if side.length > 1e-6 else Vector((1, 0, 0))
        up = side.cross(d).normalized()
        u = i / n
        w = width * max((1 - u) ** taper, tip)
        th = w * thick
        ring.append([bm.verts.new(c + side * w), bm.verts.new(c + up * th), bm.verts.new(c - side * w), bm.verts.new(c - up * th)])
    for i in range(n):
        a, b = ring[i], ring[i + 1]
        for k in range(4):
            bm.faces.new((a[k], a[(k + 1) % 4], b[(k + 1) % 4], b[k]))
    bm.faces.new(list(reversed(ring[0])))
    bm.faces.new(ring[-1])


def rounded_box(size, radius, segs=3, xform=Matrix()):
    """A bevelled box (buns, soles, props) as its own bmesh, transformed by xform."""
    bm = bmesh.new()
    geom = bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=geom['verts'])
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=radius, segments=segs, affect='EDGES', profile=0.5)
    bmesh.ops.transform(bm, matrix=xform, verts=list(bm.verts))
    return bm


def band(bm, centre, axis, r0, r1, height, segs=32, bulge=0.0):
    """A short open tube (cuffs, waistbands): radius r0 at the bottom, r1 at the top, along `axis`."""
    axis = axis.normalized()
    ref = Vector((1, 0, 0)) if abs(axis.x) < 0.9 else Vector((0, 1, 0))
    s = axis.cross(ref).normalized(); t = axis.cross(s)
    rings = []
    for j, (h, r) in enumerate(((-height / 2, r0), (0, (r0 + r1) / 2 + bulge), (height / 2, r1))):
        ring = []
        for i in range(segs):
            a = 2 * math.pi * i / segs
            ring.append(bm.verts.new(centre + axis * h + (s * math.cos(a) + t * math.sin(a)) * r))
        rings.append(ring)
    for j in range(2):
        for i in range(segs):
            a, b = rings[j], rings[j + 1]
            bm.faces.new((a[i], a[(i + 1) % segs], b[(i + 1) % segs], b[i]))


# ---------------------------------------------------------------- render
def setup_render(res=(1920, 1080), pct=50, bg=(0.93, 0.92, 0.95), transparent=False):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = pct
    sc.render.film_transparent = transparent
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.look = 'None'
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA' if transparent else 'RGB'
    sc.eevee.taa_render_samples = 16
    w = sc.world or bpy.data.worlds.new('world'); sc.world = w
    w.use_nodes = True
    bgn = w.node_tree.nodes.get('Background') or w.node_tree.nodes.new('ShaderNodeBackground')
    bgn.inputs['Color'].default_value = (*lin(bg), 1); bgn.inputs['Strength'].default_value = 1.0
    return sc


def camera(name='cam', lens=50, ortho=None):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens; cd.clip_start = 0.02; cd.clip_end = 200
    if ortho:
        cd.type = 'ORTHO'; cd.ortho_scale = ortho
    cam = link(bpy.data.objects.new(name, cd))
    bpy.context.scene.camera = cam
    return cam


def aim(cam, eye, target, roll=0.0):
    eye, target = Vector(eye), Vector(target)
    d = (target - eye).normalized()
    q = d.to_track_quat('-Z', 'Y')
    if roll:
        q = Quaternion(d, roll) @ q
    cam.location = eye
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = q
