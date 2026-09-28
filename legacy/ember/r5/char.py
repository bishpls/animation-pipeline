"""EMBER · Round 5 — the heroine as a production 3D anime character (Blender, headless).
Builds: skinned body (skin-modifier skeleton -> real mesh, auto-weighted), anime head with drawn-face decals,
clump hair, clothing, crimson cloak (cloth-ready), gun-scythe, toon materials + inverted-hull outlines.
Import build_character() from shot scripts, or run directly for a turntable/expression sheet."""
import bpy, bmesh, math, os, sys
from mathutils import Vector, Matrix, Euler, Quaternion
HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- palette
C = dict(
    skin=(0.97, 0.86, 0.80), skinS=(0.84, 0.60, 0.62),
    hair=(0.90, 0.91, 0.96), hairS=(0.58, 0.60, 0.80), streak=(0.80, 0.12, 0.16), streakS=(0.45, 0.05, 0.12),
    suit=(0.15, 0.14, 0.18), suitS=(0.07, 0.065, 0.09),
    legs=(0.29, 0.20, 0.16), legsS=(0.15, 0.10, 0.09),
    boot=(0.11, 0.10, 0.13), bootS=(0.05, 0.045, 0.06), steel=(0.72, 0.74, 0.80), steelS=(0.38, 0.40, 0.50),
    belt=(0.42, 0.27, 0.18), beltS=(0.22, 0.13, 0.09), buckle=(0.80, 0.80, 0.86),
    cloak=(0.72, 0.10, 0.15), cloakS=(0.40, 0.04, 0.10), lining=(0.10, 0.06, 0.09),
    scarf=(0.23, 0.22, 0.27), scarfS=(0.12, 0.11, 0.15), glove=(0.10, 0.095, 0.12),
    shaft=(0.10, 0.10, 0.12), stripe=(0.85, 0.12, 0.16), blade=(0.86, 0.88, 0.95), bladeS=(0.45, 0.48, 0.60),
)
LINE = (0.10, 0.05, 0.09)


def lin(c):  # sRGB-ish authoring -> linear
    return tuple(x ** 2.2 for x in c)


# ---------------------------------------------------------------- materials
MATS = {}
LDIR = (0.45, -0.55, 0.7)   # direction TO the light
FOG = dict(color=(0.30, 0.34, 0.55), start=8.0, end=60.0, amt=0.0)


def set_fog(color=None, start=None, end=None, amt=None):
    if color is not None: FOG['color'] = color
    if start is not None: FOG['start'] = start
    if end is not None: FOG['end'] = end
    if amt is not None: FOG['amt'] = amt
    for m in MATS.values():
        nt = m.node_tree
        if nt and 'fogmap' in nt.nodes:
            fm = nt.nodes['fogmap']
            fm.inputs['From Min'].default_value = FOG['start']; fm.inputs['From Max'].default_value = FOG['end']
            fm.inputs['To Max'].default_value = FOG['amt']
            nt.nodes['fogmix'].inputs['B'].default_value = (*lin(FOG['color']), 1)


def fogify(nt, color_socket, out_socket):
    cam = nt.nodes.new('ShaderNodeCameraData')
    fm = nt.nodes.new('ShaderNodeMapRange'); fm.name = 'fogmap'
    fm.inputs['From Min'].default_value = FOG['start']; fm.inputs['From Max'].default_value = FOG['end']
    fm.inputs['To Min'].default_value = 0.0; fm.inputs['To Max'].default_value = FOG['amt']
    nt.links.new(cam.outputs['View Z Depth'], fm.inputs['Value'])
    mx = nt.nodes.new('ShaderNodeMix'); mx.name = 'fogmix'; mx.data_type = 'RGBA'
    nt.links.new(fm.outputs['Result'], mx.inputs['Factor'])
    nt.links.new(color_socket, mx.inputs['A']); mx.inputs['B'].default_value = (*lin(FOG['color']), 1)
    nt.links.new(mx.outputs['Result'], out_socket)


def set_light(d):
    v = Vector(d).normalized()
    for m in MATS.values():
        if m.node_tree and 'ldir' in m.node_tree.nodes:
            n = m.node_tree.nodes['ldir']
            n.inputs[0].default_value, n.inputs[1].default_value, n.inputs[2].default_value = v


def toon(name, base, shade, rim=(0.75, 0.82, 1.0), rim_amt=0.35, thresh=0.42, soft=0.02, emit_tex=None, spec=None):
    """Cel shader: diffuse lighting -> hard 2-tone ramp between shade/base, + fresnel rim, as emission (Eevee)."""
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    # NPR light term: N . L from the (art-directed) light direction -> no render noise, no acne
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    ld = nt.nodes.new('ShaderNodeCombineXYZ'); ld.name = 'ldir'
    ld.inputs[0].default_value, ld.inputs[1].default_value, ld.inputs[2].default_value = LDIR
    dot = nt.nodes.new('ShaderNodeVectorMath'); dot.operation = 'DOT_PRODUCT'
    nt.links.new(geo.outputs['Normal'], dot.inputs[0]); nt.links.new(ld.outputs[0], dot.inputs[1])
    bw = nt.nodes.new('ShaderNodeMath'); bw.operation = 'MULTIPLY_ADD'
    bw.inputs[1].default_value = 0.5; bw.inputs[2].default_value = 0.5
    nt.links.new(dot.outputs['Value'], bw.inputs[0])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.interpolation = 'LINEAR'
    e0, e1 = ramp.color_ramp.elements
    e0.position, e1.position = thresh - soft, thresh + soft
    e0.color, e1.color = (0, 0, 0, 1), (1, 1, 1, 1)
    nt.links.new(bw.outputs[0], ramp.inputs[0])
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    nt.links.new(ramp.outputs['Color'], mix.inputs['Factor'])
    if emit_tex:
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = bpy.data.images.load(emit_tex)
        nt.links.new(tex.outputs['Color'], mix.inputs['B'])
        dim = nt.nodes.new('ShaderNodeMix'); dim.data_type = 'RGBA'; dim.inputs['Factor'].default_value = 0.35
        nt.links.new(tex.outputs['Color'], dim.inputs['A']); dim.inputs['B'].default_value = (0.2, 0.1, 0.25, 1)
        nt.links.new(dim.outputs['Result'], mix.inputs['A'])
    else:
        mix.inputs['A'].default_value = (*lin(shade), 1)
        mix.inputs['B'].default_value = (*lin(base), 1)
    # rim light (fresnel, masked to the lit side a bit)
    lw = nt.nodes.new('ShaderNodeLayerWeight')
    lw.inputs['Blend'].default_value = 0.35
    rr = nt.nodes.new('ShaderNodeValToRGB')
    rr.color_ramp.elements[0].position, rr.color_ramp.elements[1].position = 0.55, 0.6
    rr.color_ramp.elements[0].color, rr.color_ramp.elements[1].color = (0, 0, 0, 1), (1, 1, 1, 1)
    nt.links.new(lw.outputs['Facing'], rr.inputs[0])
    rim_mix = nt.nodes.new('ShaderNodeMix'); rim_mix.data_type = 'RGBA'; rim_mix.blend_type = 'ADD'
    rim_node = nt.nodes.new('ShaderNodeValue'); rim_node.name = 'rim_amt'; rim_node.outputs[0].default_value = rim_amt
    mulr = nt.nodes.new('ShaderNodeMath'); mulr.operation = 'MULTIPLY'
    nt.links.new(rr.outputs['Color'], mulr.inputs[0]); nt.links.new(rim_node.outputs[0], mulr.inputs[1])
    nt.links.new(mulr.outputs[0], rim_mix.inputs['Factor'])
    nt.links.new(mix.outputs['Result'], rim_mix.inputs['A'])
    rim_mix.inputs['B'].default_value = (*lin(rim), 1)
    # warm key tint (keyable per shot: fire light)
    warm = nt.nodes.new('ShaderNodeMix'); warm.data_type = 'RGBA'; warm.blend_type = 'MULTIPLY'
    wv = nt.nodes.new('ShaderNodeValue'); wv.name = 'warm'; wv.outputs[0].default_value = 0.0
    nt.links.new(wv.outputs[0], warm.inputs['Factor'])
    nt.links.new(rim_mix.outputs['Result'], warm.inputs['A'])
    warm.inputs['B'].default_value = (1.0, 0.55, 0.35, 1)
    em = nt.nodes.new('ShaderNodeEmission')
    fogify(nt, warm.outputs['Result'], em.inputs['Color'])
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    MATS[name] = m
    return m


def flat(name, color, strength=1.0, alpha_tex=None):
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Strength'].default_value = strength
    if alpha_tex:
        tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = bpy.data.images.load(alpha_tex); tex.extension = 'CLIP'
        tr = nt.nodes.new('ShaderNodeBsdfTransparent'); mx = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(tex.outputs['Color'], em.inputs['Color'])
        nt.links.new(tex.outputs['Alpha'], mx.inputs['Fac'])
        nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(em.outputs[0], mx.inputs[2])
        nt.links.new(mx.outputs[0], out.inputs['Surface'])
        try:
            m.surface_render_method = 'BLENDED'
        except Exception:
            pass
        m.use_backface_culling = True
    else:
        rgb = nt.nodes.new('ShaderNodeRGB'); rgb.outputs[0].default_value = (*lin(color), 1)
        if name == 'outline':
            nt.links.new(rgb.outputs[0], em.inputs['Color'])
        else:
            fogify(nt, rgb.outputs[0], em.inputs['Color'])
        nt.links.new(em.outputs[0], out.inputs['Surface'])
    MATS[name] = m
    return m


def outline_mat():
    if 'outline' in MATS:
        return MATS['outline']
    m = flat('outline', LINE)
    m.use_backface_culling = True
    MATS['outline'] = m
    return m


def add_outline(ob, thick=0.004):
    ob.data.materials.append(outline_mat())
    idx = len(ob.data.materials) - 1
    so = ob.modifiers.new('outline', 'SOLIDIFY')
    so.thickness = -thick
    so.use_flip_normals = True
    so.material_offset = idx
    so.use_rim = False
    so.offset = 1.0
    return so


# ---------------------------------------------------------------- helpers
def link(ob, coll=None):
    (coll or bpy.context.scene.collection).objects.link(ob)
    return ob


def mesh_from_bm(name, bm, mats=(), smooth=True):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    for m in mats:
        me.materials.append(m)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return link(bpy.data.objects.new(name, me))


def bone_parent(ob, arm, bone):
    bpy.context.view_layer.update()
    mw = ob.matrix_world.copy()
    ob.parent = arm; ob.parent_type = 'BONE'; ob.parent_bone = bone
    ob.matrix_world = mw


# ---------------------------------------------------------------- skeleton
H = 1.62
J = {  # name: (pos, (rx, ry))
    'pelvis': ((0, 0, 0.90), (0.125, 0.092)), 'waist': ((0, 0.005, 1.03), (0.092, 0.074)),
    'chest': ((0, 0, 1.19), (0.112, 0.085)), 'uchest': ((0, 0.01, 1.30), (0.118, 0.075)),
    'neck': ((0, 0.012, 1.40), (0.036, 0.036)),
}
for s, sx in (('L', 1), ('R', -1)):
    J.update({
        f'shoulder.{s}': ((sx * 0.15, 0.012, 1.315), (0.045, 0.045)),
        f'elbow.{s}': ((sx * 0.30, 0.03, 1.12), (0.033, 0.033)),
        f'wrist.{s}': ((sx * 0.42, 0.0, 0.95), (0.026, 0.023)),
        f'handend.{s}': ((sx * 0.47, -0.012, 0.87), (0.028, 0.016)),
        f'hip.{s}': ((sx * 0.085, 0.0, 0.86), (0.074, 0.072)),
        f'thighm.{s}': ((sx * 0.088, 0.0, 0.68), (0.066, 0.066)),
        f'knee.{s}': ((sx * 0.09, -0.012, 0.47), (0.047, 0.048)),
        f'calf.{s}': ((sx * 0.09, 0.008, 0.31), (0.052, 0.05)),
        f'ankle.{s}': ((sx * 0.09, 0.02, 0.08), (0.032, 0.034)),
        f'toe.{s}': ((sx * 0.09, -0.11, 0.03), (0.036, 0.022)),
    })
EDGES = [('pelvis', 'waist'), ('waist', 'chest'), ('chest', 'uchest'), ('uchest', 'neck')]
for s in 'LR':
    EDGES += [('uchest', f'shoulder.{s}'), (f'shoulder.{s}', f'elbow.{s}'), (f'elbow.{s}', f'wrist.{s}'), (f'wrist.{s}', f'handend.{s}'),
              ('pelvis', f'hip.{s}'), (f'hip.{s}', f'thighm.{s}'), (f'thighm.{s}', f'knee.{s}'), (f'knee.{s}', f'calf.{s}'),
              (f'calf.{s}', f'ankle.{s}'), (f'ankle.{s}', f'toe.{s}')]
# bones: name -> (head joint, tail joint, parent)
BONES = {'hips': ('pelvis', 'waist', None), 'spine': ('waist', 'chest', 'hips'), 'chest': ('chest', 'uchest', 'spine'),
         'neck': ('uchest', 'neck', 'chest'), 'head': ('neck', None, 'neck')}
for s in 'LR':
    BONES.update({f'clav.{s}': ('uchest', f'shoulder.{s}', 'chest'), f'upperarm.{s}': (f'shoulder.{s}', f'elbow.{s}', f'clav.{s}'),
                  f'forearm.{s}': (f'elbow.{s}', f'wrist.{s}', f'upperarm.{s}'), f'hand.{s}': (f'wrist.{s}', f'handend.{s}', f'forearm.{s}'),
                  f'thigh.{s}': (f'hip.{s}', f'knee.{s}', 'hips'), f'shin.{s}': (f'knee.{s}', f'ankle.{s}', f'thigh.{s}'),
                  f'foot.{s}': (f'ankle.{s}', f'toe.{s}', f'shin.{s}')})


def P(j):
    return Vector(J[j][0])


def build_body():
    names = list(J.keys())
    me = bpy.data.meshes.new('body_skel')
    me.from_pydata([J[n][0] for n in names], [(names.index(a), names.index(b)) for a, b in EDGES], [])
    ob = link(bpy.data.objects.new('body', me))
    sk = ob.modifiers.new('skin', 'SKIN')
    sk.use_smooth_shade = True
    sk.branch_smoothing = 0.6
    for i, n in enumerate(names):
        ob.data.skin_vertices[0].data[i].radius = J[n][1]
        ob.data.skin_vertices[0].data[i].use_root = (n == 'pelvis')
    ss = ob.modifiers.new('sub', 'SUBSURF'); ss.levels = 2; ss.render_levels = 2
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.modifier_apply(modifier='skin')
    bpy.ops.object.modifier_apply(modifier='sub')
    # hand shape: flatten the hands into mitts; slight chest/hip shaping
    for v in ob.data.vertices:
        co = v.co
        for s, sx in (('L', 1), ('R', -1)):
            w = P(f'wrist.{s}')
            if (co - w).length < 0.09 and co.z < w.z + 0.01:
                d = co - w
                co.y = w.y + d.y * 0.55
        if 1.13 < co.z < 1.27 and co.y < -0.02:                 # bust
            k = math.exp(-((co.z - 1.2) / 0.05) ** 2) * math.exp(-((abs(co.x) - 0.055) / 0.05) ** 2)
            co.y -= 0.03 * k
        if 0.82 < co.z < 0.98:                                   # hips wider at the side
            co.x *= 1.0 + 0.06 * math.exp(-((co.z - 0.88) / 0.05) ** 2)
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def build_armature():
    ad = bpy.data.armatures.new('rig')
    arm = link(bpy.data.objects.new('rig', ad))
    bpy.context.view_layer.objects.active = arm
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = ad.edit_bones
    for n, (h, t, par) in BONES.items():
        b = eb.new(n)
        b.head = P(h)
        b.tail = P(t) if t else P(h) + Vector((0, 0, 0.2))
        if n.startswith('thigh') or n.startswith('shin'):
            b.roll = 0
    for n, (h, t, par) in BONES.items():
        if par:
            eb[n].parent = eb[par]
            eb[n].use_connect = False
    bpy.ops.object.mode_set(mode='OBJECT')
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    return arm


def assign_body_materials(body, arm):
    mats = ['suit', 'skin', 'legs', 'boot', 'glove']
    M = {'suit': toon('suit', C['suit'], C['suitS'], rim_amt=0.5), 'skin': toon('skin', C['skin'], C['skinS'], thresh=0.35),
         'legs': toon('legs', C['legs'], C['legsS']), 'boot': toon('boot', C['boot'], C['bootS'], rim_amt=0.5),
         'glove': toon('glove', C['glove'], C['bootS'], rim_amt=0.5)}
    for k in mats:
        body.data.materials.append(M[k])
    for p in body.data.polygons:
        c = p.center
        ax = abs(c.x)
        idx = 0
        if c.z < 0.40:
            idx = 3                                                        # boots (knee-high)
        elif c.z < 0.86 and ax > 0.02:
            idx = 2                                                        # leggings
        side = 'L' if c.x > 0 else 'R'
        sh, el = P(f'shoulder.{side}'), P(f'elbow.{side}')
        seg = el - sh
        tpar = (c - sh).dot(seg) / seg.length_squared
        if ax > 0.12 and c.z > 0.9 and tpar > 0.18:                        # bare arms beyond a clean sleeveless line
            idx = 1
            wr = P('wrist.L' if c.x > 0 else 'wrist.R')
            if (c - wr).length < 0.075 or c.z < wr.z:
                idx = 4                                                    # fingerless gloves
        if c.z > 1.35:
            idx = 1                                                        # neck
        p.material_index = idx


def skin_bind(body, arm):
    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True); arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')


# ---------------------------------------------------------------- head, face, hair
HC = Vector((0, 0.0, 1.515))          # head centre
def build_head(arm):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=28, radius=1.0)
    for v in bm.verts:
        x, y, z = v.co
        # cranium: wider than deep; jaw tapers to a small chin in front
        sx, sy, sz = 0.083, 0.092, 0.1
        if z < 0:
            t = -z
            sx *= 1 - 0.42 * t ** 1.3
            sy *= 1 - 0.18 * t
            if y < 0:
                y = y - 0.25 * t * t
        v.co = Vector((x * sx, y * sy, z * sz * (1.04 if z < 0 else 1.0)))
    for v in bm.verts:
        v.co += HC
    ob = mesh_from_bm('head', bm, [toon('skin_face', C['skin'], C['skinS'], thresh=0.12, rim_amt=0.25)])
    add_outline(ob, 0.0035)
    bone_parent(ob, arm, 'head')
    # neck-to-head blend: a little ear on each side
    for sx in (-1, 1):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=1.0)
        bmesh.ops.scale(bm, vec=(0.012, 0.022, 0.03), verts=bm.verts)
        bmesh.ops.translate(bm, vec=HC + Vector((sx * 0.08, 0.005, -0.012)), verts=bm.verts)
        e = mesh_from_bm(f'ear{sx}', bm, [MATS['skin_face']])
        add_outline(e, 0.003)
        bone_parent(e, arm, 'head')
    return ob


def build_face_decals(head, arm):
    """Front-projected decal shells (one per expression) over the face."""
    exprs = sorted(f[5:-4] for f in os.listdir(os.path.join(HERE, 'tex')) if f.startswith('face_') and f.endswith('.png'))
    src = head.data
    W, zlo, zhi = 0.17, 1.40, 1.62
    decals = {}
    for ex in exprs:
        bm = bmesh.new()
        bm.from_mesh(src)
        kill = [f for f in bm.faces if f.normal.y > -0.15 or f.calc_center_median().z < 1.395]
        bmesh.ops.delete(bm, geom=kill, context='FACES')
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
        for v in bm.verts:
            v.co += v.normal * 0.0012
        uv = bm.loops.layers.uv.new()
        for f in bm.faces:
            for l in f.loops:
                co = l.vert.co
                l[uv].uv = ((co.x + W / 2) / W, (co.z - zlo) / (zhi - zlo))
        ob = mesh_from_bm(f'face_{ex}', bm, [flat(f'facemat_{ex}', (1, 1, 1), 1.0, os.path.join(HERE, 'tex', f'face_{ex}.png'))])
        bone_parent(ob, arm, 'head')
        ob.hide_render = ex != 'neutral'
        ob.hide_viewport = ex != 'neutral'
        decals[ex] = ob
    return decals


# hair: tapered, curved clumps rooted on the skull. (azimuth deg around Z from front=-Y, elevation deg, length, width, curl, colour)
def clump(bm, root, direction, length, width, bend, twist=0.0, n=8, thick=0.35):
    d = direction.normalized()
    side = d.cross(Vector((0, 0, 1)))
    if side.length < 1e-3:
        side = Vector((1, 0, 0))
    side.normalize()
    up = side.cross(d).normalized()
    ring = []
    for i in range(n + 1):
        u = i / n
        c = root + d * length * u + bend * (u * u) * length
        w = width * (1 - u) ** 0.8 * (1 if i < n else 0.02)
        th = w * thick
        s2 = Quaternion(d, twist * u) @ side
        u2 = Quaternion(d, twist * u) @ up
        ring.append([bm.verts.new(c + s2 * w), bm.verts.new(c + u2 * th), bm.verts.new(c - s2 * w), bm.verts.new(c - u2 * th)])
    for i in range(n):
        a, b = ring[i], ring[i + 1]
        for k in range(4):
            bm.faces.new((a[k], a[(k + 1) % 4], b[(k + 1) % 4], b[k]))
    bm.faces.new(list(reversed(ring[0])))


def lock(bm, pts, width, thick=0.4, taper=0.8):
    """a hair lock along an arbitrary path (list of Vectors): flat ribbon with thickness, tapering to a point"""
    n = len(pts) - 1
    ring = []
    for i, c in enumerate(pts):
        d = (pts[min(i + 1, n)] - pts[max(i - 1, 0)]).normalized()
        out = (c - HC).normalized()
        side = d.cross(out).normalized()
        up = side.cross(d).normalized()
        u = i / n
        w = width * (1 - u) ** taper * (1 if i < n else 0.02)
        th = w * thick
        ring.append([bm.verts.new(c + side * w), bm.verts.new(c + up * th), bm.verts.new(c - side * w), bm.verts.new(c - up * th)])
    for i in range(n):
        a, b = ring[i], ring[i + 1]
        for k in range(4):
            bm.faces.new((a[k], a[(k + 1) % 4], b[(k + 1) % 4], b[k]))
    bm.faces.new(list(reversed(ring[0])))


def skull(az, el, r=1.06):
    a, e = math.radians(az), math.radians(el)
    return HC + Vector((math.sin(a) * math.cos(e) * 0.083 * r, -math.cos(a) * math.cos(e) * 0.092 * r, math.sin(e) * 0.1 * r))


def build_hair(arm):
    hairM = toon('hair', C['hair'], C['hairS'], rim=(1, 1, 1), rim_amt=0.5, thresh=0.45)
    redM = toon('streak', C['streak'], C['streakS'], rim=(1, 0.7, 0.7), rim_amt=0.4)
    # cap
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=36, v_segments=24, radius=1.0)
    for v in bm.verts:
        x, y, z = v.co
        v.co = HC + Vector((x * 0.089, y * 0.099, z * 0.107 + 0.004))
    kill = [f for f in bm.faces if (f.calc_center_median() - HC).z < -0.035 or
            ((f.calc_center_median() - HC).y < -0.035 and (f.calc_center_median() - HC).z < 0.055)]
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    cap = mesh_from_bm('hair_cap', bm, [hairM])
    add_outline(cap, 0.003)
    bone_parent(cap, arm, 'head')
    bm = bmesh.new(); bm_red = bmesh.new()
    import random
    R = random.Random(7)
    # bangs: pointed locks that stop at the brow, parted over the eyes so both read at three-quarter;
    # two longer strands fall between/beside the eyes (the red one is her streak)
    for i, (az, el_end, w) in enumerate([(-56, 26, 0.02), (-42, 18, 0.024), (-28, 24, 0.022), (-14, 14, 0.02), (-3, 20, 0.018),
                                         (9, 12, 0.02), (21, 22, 0.022), (35, 16, 0.024), (50, 26, 0.02)]):
        root = skull(az * 0.75, 64)
        tip = skull(az * 1.02 + (4 if az > 0 else -4), el_end, 1.1)
        direction = tip - root
        clump(bm, root, direction, direction.length, w * 1.1, Vector((0, -0.05, -0.01)), twist=0.25 * (R.random() - 0.5), thick=0.3)
    lock(bm_red, [skull(10 + 44 * u ** 1.3, 72 - 94 * u, 1.13 + 0.1 * u) for u in [i / 14 for i in range(15)]], 0.02, thick=0.4)
    root = skull(-10, 60); tip = skull(-22, -8, 1.1)
    clump(bm, root, tip - root, (tip - root).length, 0.013, Vector((-0.02, -0.05, 0.0)), twist=-0.4, n=10, thick=0.45)
    # side locks framing the face in front of the ears, to the jaw
    for sx in (-1, 1):
        for k, (az, L, w) in enumerate([(72, 0.2, 0.024), (84, 0.22, 0.028), (96, 0.19, 0.03)]):
            root = skull(sx * az, 42)
            clump(bm, root, Vector((sx * 0.08, 0.02 * k, -1)), L, w, Vector((sx * 0.04, -0.02, 0.0)), twist=sx * 0.4, thick=0.45)
    # crown + back: long overlapping locks falling to the shoulders, flicking out at the ends
    for layer, (el, L, w, n) in enumerate([(62, 0.27, 0.05, 11), (38, 0.24, 0.05, 12), (12, 0.19, 0.045, 11)]):
        for k in range(n):
            az = 95 + k * (170 / (n - 1)) + R.uniform(-7, 7) + layer * 6
            root = skull(az, el + R.uniform(-6, 6))
            out = (root - HC); out.z = 0; out.normalize()
            dvec = out * (0.12 + 0.08 * layer) + Vector((0, 0, -1))
            clump(bm, root, dvec, L * (0.85 + 0.3 * R.random()), w * (0.9 + 0.3 * R.random()),
                  out * 0.18 + Vector((0, 0, 0.04)), twist=0.6 * (R.random() - 0.5), thick=0.55)
    hair = mesh_from_bm('hair', bm, [hairM]); add_outline(hair, 0.0025); bone_parent(hair, arm, 'head')
    red = mesh_from_bm('hair_red', bm_red, [redM]); add_outline(red, 0.0025); bone_parent(red, arm, 'head')
    return [cap, hair, red]


# ---------------------------------------------------------------- clothing
def torus_band(name, center, rx, ry, tube, mat, arm, bone, tilt=0.0, m=4, hz=2.2, smooth=False, droop=0.0):
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=False, segments=32, radius=1.0)
    verts = list(bm.verts)
    bm2 = bmesh.new()
    rings = []
    for i in range(32):
        a = 2 * math.pi * i / 32
        c = Vector((math.cos(a) * rx, math.sin(a) * ry, 0))
        n = Vector((math.cos(a), math.sin(a), 0))
        c = c + Vector((0, 0, -droop * max(0.0, -math.sin(a)) ** 2))          # sag at the front (-y)
        ring = [bm2.verts.new(c + n * tube * math.cos(b) + Vector((0, 0, tube * hz * math.sin(b))))
                for b in [2 * math.pi * k / m + math.pi / m for k in range(m)]]
        rings.append(ring)
    for i in range(32):
        a, b = rings[i], rings[(i + 1) % 32]
        for k in range(m):
            bm2.faces.new((a[k], b[k], b[(k + 1) % m], a[(k + 1) % m]))
    bm.free()
    ob = mesh_from_bm(name, bm2, [mat], smooth=smooth)
    ob.location = center
    ob.rotation_euler = (tilt, 0, 0)
    add_outline(ob, 0.002)
    bone_parent(ob, arm, bone)
    return ob


def build_clothing(arm):
    beltM = toon('belt', C['belt'], C['beltS'], rim_amt=0.3)
    torus_band('belt1', Vector((0, 0.0, 0.975)), 0.1, 0.083, 0.008, beltM, arm, 'hips', tilt=0.08)
    torus_band('belt2', Vector((0, 0.0, 0.915)), 0.118, 0.098, 0.007, beltM, arm, 'hips', tilt=-0.12)
    for s, sx in (('L', 1), ('R', -1)):
        torus_band(f'thighstrap.{s}', Vector((sx * 0.088, 0, 0.70)), 0.072, 0.072, 0.006, beltM, arm, f'thigh.{s}')
        torus_band(f'bootcuff.{s}', Vector((sx * 0.09, 0.006, 0.405)), 0.056, 0.055, 0.007, toon('boot', C['boot'], C['bootS']), arm, f'shin.{s}')
        # steel toe cap
        bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=14, v_segments=10, radius=1.0)
        bmesh.ops.scale(bm, vec=(0.038, 0.045, 0.026), verts=bm.verts)
        bmesh.ops.translate(bm, vec=Vector((sx * 0.09, -0.11, 0.03)), verts=bm.verts)
        cap = mesh_from_bm(f'toecap.{s}', bm, [toon('steel', C['steel'], C['steelS'], rim=(1, 1, 1), rim_amt=0.6)])
        add_outline(cap, 0.002); bone_parent(cap, arm, f'foot.{s}')
    # chest cross-strap (diagonal band) and buckle
    bm = bmesh.new()
    pts = [Vector((0.13, 0.02, 1.33)), Vector((0.06, -0.085, 1.22)), Vector((-0.04, -0.09, 1.1)), Vector((-0.11, -0.04, 0.99))]
    prev = None
    for i, p in enumerate(pts):
        d = (pts[min(i + 1, 3)] - pts[max(i - 1, 0)]).normalized()
        side = d.cross(Vector((0, -1, 0))).normalized() * 0.014
        a, b = bm.verts.new(p + side), bm.verts.new(p - side)
        if prev:
            bm.faces.new((prev[0], prev[1], b, a))
        prev = (a, b)
    st = mesh_from_bm('crossstrap', bm, [beltM])
    so = st.modifiers.new('thick', 'SOLIDIFY'); so.thickness = 0.004
    bone_parent(st, arm, 'chest')
    # scarf: a thick soft ring around the neck + short tails
    torus_band('scarf', Vector((0, 0.012, 1.36)), 0.064, 0.06, 0.02, toon('scarf', C['scarf'], C['scarfS'], rim_amt=0.4), arm, 'neck',
               m=10, hz=1.25, smooth=True, droop=0.018)
    # ember clasp (emissive gem) at the collar
    bm = bmesh.new()                                     # a faceted hex gem, table facing out, in a dark setting
    R_ = Matrix.Rotation(-math.pi / 2, 4, 'X')
    bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.016, radius2=0.009, depth=0.008, matrix=R_ @ Matrix.Translation((0, 0, 0.004)))
    bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.016, radius2=0.0, depth=0.012, matrix=R_ @ Matrix.Translation((0, 0, -0.006)) @ Matrix.Rotation(math.pi, 4, 'X'))
    bmesh.ops.scale(bm, vec=(1.0, 1.0, 1.25), verts=bm.verts)
    clasp = mesh_from_bm('clasp', bm, [flat('clasp', (1.0, 0.62, 0.2), 6.0)], smooth=False)
    clasp.location = Vector((0, -0.078, 1.33))
    bone_parent(clasp, arm, 'chest')
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.021, radius2=0.021, depth=0.006, matrix=R_)
    bmesh.ops.scale(bm, vec=(1.0, 1.0, 1.25), verts=bm.verts)
    setting = mesh_from_bm('clasp_setting', bm, [toon('setting', (0.3, 0.26, 0.24), (0.1, 0.08, 0.08), rim_amt=0.6)], smooth=False)
    setting.location = Vector((0, -0.072, 1.33)); add_outline(setting, 0.0015)
    bone_parent(setting, arm, 'chest')
    return clasp


CLOAK_FLIP = False


CK_NC, CK_NS, CK_V0 = 7, 3, 0.1          # cloak rig: columns, segments per column, v where the free part starts


def cloak_point(u, v):
    """rest shape of the cloak: u 0 = her right front .. 1 = her left front (wrapping round the back), v 0 = collar .. 1 = hem"""
    ang = math.radians(-110 + 220 * u)
    rad = 0.13 + 0.22 * v ** 1.1 + 0.02 * math.cos(ang) ** 2
    return Vector((math.sin(ang) * rad, math.cos(ang) * rad * 0.95 + 0.02, 1.34 - 0.62 * v))


def build_cloak(arm):
    """Crimson half-cloak on a bone rig (Xrd-style): CK_NC columns x CK_NS segments, each bone damped-tracking
    a simulated point (see cloak.py).  Never uses Blender cloth, so it can't crumple through the body."""
    cols, rows = 21, 16
    bm = bmesh.new()
    grid = []
    for r in range(rows):
        row = []
        v = r / (rows - 1)
        for c in range(cols):
            p = cloak_point(c / (cols - 1), v)
            if r == rows - 1:                        # tattered hem
                p.z += (0.05 if c % 2 else -0.02) + 0.03 * math.sin(c * 2.7)
            row.append(bm.verts.new(p))
        grid.append(row)
    for r in range(rows - 1):
        for c in range(cols - 1):
            bm.faces.new((grid[r][c], grid[r][c + 1], grid[r + 1][c + 1], grid[r + 1][c]))
    if CLOAK_FLIP:
        for f in bm.faces:
            f.normal_flip()
    ob = mesh_from_bm('cloak', bm, [toon('cloak', C['cloak'], C['cloakS'], rim=(1, 0.6, 0.6), rim_amt=0.35, thresh=0.4),
                                    toon('lining', C['lining'], C['lining'], rim_amt=0.1)])
    for m in ob.data.materials:
        m.use_backface_culling = True
    # bones
    bpy.context.view_layer.objects.active = arm
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.data.edit_bones
    vs = [CK_V0 + (1 - CK_V0) * k / CK_NS for k in range(CK_NS + 1)]
    for c in range(CK_NC):
        u = c / (CK_NC - 1)
        for k in range(CK_NS):
            b = eb.new(f'ck{c}_{k}')
            b.head, b.tail = cloak_point(u, vs[k]), cloak_point(u, vs[k + 1])
            b.parent = eb['chest'] if k == 0 else eb[f'ck{c}_{k - 1}']
            b.use_connect = k > 0
    bpy.ops.object.mode_set(mode='OBJECT')
    for c in range(CK_NC):
        for k in range(CK_NS):
            pb = arm.pose.bones[f'ck{c}_{k}']
            pb.rotation_mode = 'QUATERNION'
    # weights: chest near the collar, else bilinear over columns x (blended) segments
    G = {n: ob.vertex_groups.new(name=n) for n in ['chest'] + [f'ck{c}_{k}' for c in range(CK_NC) for k in range(CK_NS)]}
    for r in range(rows):
        v = r / (rows - 1)
        for c in range(cols):
            i = r * cols + c
            u = c / (cols - 1)
            if v <= CK_V0:
                G['chest'].add([i], 1.0, 'REPLACE'); continue
            sv = (v - CK_V0) / (1 - CK_V0) * CK_NS
            sk = min(int(sv), CK_NS - 1); fs = sv - sk
            segw = {sk: 1.0}
            if fs < 0.3:                              # blend across the joint above
                w = 0.5 + fs / 0.6
                segw = {sk: w}
                if sk > 0: segw[sk - 1] = 1 - w
                else: G['chest'].add([i], 1 - w, 'REPLACE')
            cu = u * (CK_NC - 1); c0 = min(int(cu), CK_NC - 2); fc = cu - c0
            for kk, ws in segw.items():
                for cc, wc in ((c0, 1 - fc), (c0 + 1, fc)):
                    if wc * ws > 1e-4:
                        G[f'ck{cc}_{kk}'].add([i], wc * ws, 'ADD')
    ob.visible_shadow = False
    am = ob.modifiers.new('arm', 'ARMATURE'); am.object = arm
    ob.parent = arm
    sol = ob.modifiers.new('solid', 'SOLIDIFY'); sol.thickness = 0.006; sol.material_offset = 1
    add_outline(ob, 0.003)
    build_hood(arm)
    return ob


def build_hood(arm):
    """the hood, down: a soft fold lying across the back of the neck and shoulders only (open at the throat)"""
    bm = bmesh.new(); rings = []
    n, m = 22, 8
    for i in range(n + 1):
        u = i / n
        a = 0.35 + (math.pi - 0.7) * u                        # back half only (y > 0 is her back)
        sw = math.sin(u * math.pi)
        c = Vector((math.cos(a) * 0.105, 0.03 + math.sin(a) * 0.1, 1.345 - 0.06 * sw))
        rad = 0.012 + 0.03 * sw ** 0.6
        out = Vector((math.cos(a), math.sin(a), 0)); up = Vector((0, 0, 1))
        rings.append([bm.verts.new(c + out * rad * math.cos(t) * 1.1 + up * rad * math.sin(t) * 1.4)
                      for t in [2 * math.pi * k / m for k in range(m)]])
    for i in range(n):
        for k in range(m):
            bm.faces.new((rings[i][k], rings[i + 1][k], rings[i + 1][(k + 1) % m], rings[i][(k + 1) % m]))
    bm.faces.new(list(reversed(rings[0]))); bm.faces.new(rings[-1])
    ob = mesh_from_bm('hood', bm, [MATS['cloak']])
    add_outline(ob, 0.002)
    bone_parent(ob, arm, 'chest')
    return ob


# ---------------------------------------------------------------- weapon (built along +Z from the butt; blade at the top pointing +X)
def build_weapon():
    """Gun-scythe with a working mechanism: shaft telescopes (3 segments), head block rides the top,
    blade swings out on a hinge. Local frame: butt at origin, shaft +Z, blade opens toward +X."""
    shaftM = toon('shaft', C['shaft'], (0.04, 0.04, 0.05), rim_amt=0.5)
    L = 1.55
    root = link(bpy.data.objects.new('weapon', None)); root.empty_display_size = 0.2
    segs = []
    for i, (z0, z1, r) in enumerate([(0.0, 0.62, 0.017), (0.0, 0.52, 0.0155), (0.0, 0.52, 0.014)]):
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=r, radius2=r, depth=z1 - z0, matrix=Matrix.Translation((0, 0, (z1 - z0) / 2)))
        bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=r + 0.005, radius2=r + 0.005, depth=0.03, matrix=Matrix.Translation((0, 0, z1 - 0.015)))
        seg = mesh_from_bm(f'w_seg{i}', bm, [shaftM]); add_outline(seg, 0.002)
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1, matrix=Matrix.Translation((r * 0.85, 0, (z1 - z0) * 0.5)) @ Matrix.Diagonal((0.006, r * 0.7, (z1 - z0) * 0.8, 1)))
        st = mesh_from_bm(f'w_stripe{i}', bm, [flat('stripe', C['stripe'], 1.2)], smooth=False); st.parent = seg
        seg.parent = root if i == 0 else segs[-1]
        segs.append(seg)
    head = link(bpy.data.objects.new('w_head', None)); head.parent = segs[-1]
    # receiver + barrel + magazine (ride on the head)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1, matrix=Matrix.Translation((0, 0, -0.14)) @ Matrix.Diagonal((0.05, 0.036, 0.28, 1)))
    bmesh.ops.create_cube(bm, size=1, matrix=Matrix.Translation((-0.036, 0, -0.2)) @ Matrix.Diagonal((0.04, 0.025, 0.09, 1)))
    bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.014, radius2=0.014, depth=0.2, matrix=Matrix.Translation((0.012, 0, 0.1)))
    rec = mesh_from_bm('w_receiver', bm, [shaftM], smooth=False); add_outline(rec, 0.002); rec.parent = head
    muzzle = link(bpy.data.objects.new('w_muzzle', None)); muzzle.parent = head; muzzle.location = (0.012, 0, 0.21)
    # hinge + blade (blade built pointing +X from the hinge, curving down); folded = rotated -150deg about Y
    hinge = link(bpy.data.objects.new('w_hinge', None)); hinge.parent = head; hinge.location = (0.02, 0, -0.01)
    hinge.rotation_mode = 'XYZ'
    bm = bmesh.new()
    spine, edge = [], []
    N = 22
    for i in range(N + 1):
        s = i / N
        x = 0.78 * math.sin(s * 1.25) / math.sin(1.25)
        z = -0.42 * s ** 2.2
        th = 0.12 * (1 - s ** 1.1) + 0.003
        spine.append((x, z + th * 0.35)); edge.append((x, z - th * 0.65))
    outline = spine + edge[::-1]
    vf = [bm.verts.new((x, 0.006, z)) for x, z in outline]
    vb = [bm.verts.new((x, -0.006, z)) for x, z in outline]
    bm.faces.new(vf); bm.faces.new(list(reversed(vb)))
    n = len(vf)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((vf[i], vb[i], vb[j], vf[j]))
    blade = mesh_from_bm('w_blade', bm, [toon('blade', C['blade'], C['bladeS'], rim=(1, 1, 1), rim_amt=0.7, thresh=0.5)], smooth=False)
    add_outline(blade, 0.002); blade.parent = hinge
    bm = bmesh.new(); pv = None
    for (x, z) in edge:
        a, b2 = bm.verts.new((x, 0.0075, z)), bm.verts.new((x, 0.0075, z + 0.007))
        if pv:
            bm.faces.new((pv[0], a, b2, pv[1]))
        pv = (a, b2)
    eo = mesh_from_bm('w_edge', bm, [flat('edge', (1.0, 0.55, 0.2), 3.0)], smooth=False); eo.parent = hinge
    tip = link(bpy.data.objects.new('w_tip', None)); tip.parent = hinge; tip.location = (0.78, 0, -0.42)
    root['segs'] = [sg.name for sg in segs]
    return root, L


def set_weapon_state(root, extend=1.0, open_=1.0):
    """extend 0..1 telescopes the shaft (0.55 m .. 1.55 m); open 0..1 swings the blade out."""
    segs = [bpy.data.objects[n] for n in root['segs']]
    e = max(0.0, min(1.0, extend))
    segs[1].location = (0, 0, 0.1 + 0.52 * e)
    segs[2].location = (0, 0, 0.0 + 0.52 * e)
    head = bpy.data.objects['w_head']
    head.location = (0, 0, 0.52)
    hinge = bpy.data.objects['w_hinge']
    hinge.rotation_euler = (0, 1.077 * (1 - max(0.0, min(1.15, open_))), 0)   # folded: tip lies back along the shaft


def weapon_length(extend):
    return 0.62 + 1.04 * max(0.0, min(1.0, extend))


# ---------------------------------------------------------------- everything
def build_character(with_cloak=True):
    arm = build_armature()
    body = build_body()
    assign_body_materials(body, arm)
    skin_bind(body, arm)
    add_outline(body, 0.0035)
    body.modifiers['outline'].show_in_editmode = False
    head = build_head(arm)
    decals = build_face_decals(head, arm)
    hair = build_hair(arm)
    clasp = build_clothing(arm)
    cloak = build_cloak(arm) if with_cloak else None
    weapon, WL = build_weapon()
    return dict(arm=arm, body=body, head=head, decals=decals, hair=hair, cloak=cloak, weapon=weapon, WL=WL, clasp=clasp)


# ---------------------------------------------------------------- render setup
def setup_render(res=(1920, 1080), pct=50, samples=16):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = pct
    sc.eevee.taa_render_samples = samples
    sc.eevee.use_raytracing = False
    sc.eevee.use_shadows = True
    sc.view_settings.view_transform = 'Standard'
    sc.render.film_transparent = False
    sc.render.fps = 24


def key_light(direction=(-0.5, 0.6, -0.65), energy=3.0, color=(0.85, 0.9, 1.0)):
    ld = bpy.data.lights.new('key', 'SUN'); ld.energy = energy; ld.color = color; ld.angle = 0.02
    lo = link(bpy.data.objects.new('key', ld))
    lo.rotation_mode = 'QUATERNION'
    lo.rotation_quaternion = Vector(direction).to_track_quat('-Z', 'Y')
    return lo


def camera(name='cam', lens=50):
    cd = bpy.data.cameras.new(name); cd.lens = lens; cd.clip_start = 0.01
    co = link(bpy.data.objects.new(name, cd)); bpy.context.scene.camera = co
    co.rotation_mode = 'QUATERNION'
    return co


def aim(cam, eye, tgt, roll=0.0):
    cam.location = Vector(eye)
    q = (Vector(tgt) - Vector(eye)).to_track_quat('-Z', 'Y')
    cam.rotation_quaternion = q @ Quaternion((0, 0, 1), roll)


if __name__ == '__main__':
    bpy.ops.wm.read_factory_settings(use_empty=True)
    setup_render(pct=60)
    w = bpy.data.worlds.new('w'); bpy.context.scene.world = w; w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.5, 0.52, 0.6, 1)
    key_light()
    ch = build_character(with_cloak=True)
    ch['weapon'].location = (0.55, 0.12, 0.05); ch['weapon'].rotation_euler = (0, -0.12, 0)
    cam = camera(lens=40)
    out = os.path.join(HERE, 'look'); os.makedirs(out, exist_ok=True)
    for i, az in enumerate([0, 40, 90, 180]):
        a = math.radians(az)
        eye = Vector((math.sin(a) * 3.2, -math.cos(a) * 3.2, 1.0))
        aim(cam, eye, (0, 0, 0.85))
        bpy.context.scene.render.filepath = os.path.join(out, f'turn_{i}.png')
        bpy.ops.render.render(write_still=True)
    # face close-ups with expressions
    cam.data.lens = 85
    for ex in ['neutral', 'fierce', 'shout', 'smile']:
        for k, o in ch['decals'].items():
            o.hide_render = k != ex
        aim(cam, (0.35, -0.95, 1.52), (0, 0, 1.49))
        bpy.context.scene.render.filepath = os.path.join(out, f'face_{ex}.png')
        bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, 'char.blend'))
    print('CHAR_OK')


# ---------------------------------------------------------------- wings of fire (one rig, so every shot matches)
def build_wings(arm):
    """Two fans of flame-feathers from the shoulder blades, parented to the chest bone.  Returns {'L': ob, 'R': ob}.
    Each wing: an outer layer (long, orange->red) and an inner layer (shorter, yellow-white), all emissive."""
    import random
    outer = flat('wing_out', (1.0, 0.3, 0.08), 1.6)
    inner = flat('wing_in', (1.0, 0.62, 0.2), 1.8)
    core = flat('wing_core', (1.0, 0.9, 0.6), 2.2)
    R_ = random.Random(21)
    W = {}
    for side, sx in (('L', 1), ('R', -1)):
        bm = bmesh.new()
        root = Vector((sx * 0.07, 0.07, 1.27))
        mats = []
        for layer, (n, L0, L1, w, mi) in enumerate([(9, 1.2, 2.3, 0.1, 0), (8, 0.8, 1.45, 0.08, 1), (6, 0.4, 0.7, 0.055, 2)]):
            for k in range(n):
                u = k / (n - 1)
                el = math.radians(62 - 80 * u + R_.uniform(-4, 4))             # a wing: up-and-out down to out-and-down
                az = math.radians(20 + 30 * u)                                  # swept back, lower feathers more
                d = Vector((sx * math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el))).normalized()
                L = (L1 - (L1 - L0) * u ** 1.4) * R_.uniform(0.92, 1.08)        # long primaries at the top edge
                pts = []
                for j in range(9):
                    t = j / 8
                    bend = Vector((0, 0.18 * t * t, -0.12 * t * t))            # tips curl back and down like flame licks
                    pts.append(root + d * L * t + bend * L)
                nv = len(bm.verts)
                lock_ribbon(bm, pts, w, mi)
        me = bpy.data.meshes.new('wing' + side); bm.to_mesh(me); bm.free()
        me.transform(Matrix.Translation(-root))                          # pivot at the shoulder blade
        for m in (outer, inner, core): me.materials.append(m)
        ob = link(bpy.data.objects.new('wing' + side, me)); ob.location = root
        ob.visible_shadow = False
        bone_parent(ob, arm, 'chest')
        W[side] = ob
    return W


def lock_ribbon(bm, pts, width, mat_index):
    """flat double-sided tapered ribbon along pts (for flame feathers)"""
    n = len(pts) - 1
    prev = None
    for i, c in enumerate(pts):
        d = (pts[min(i + 1, n)] - pts[max(i - 1, 0)]).normalized()
        side = d.cross(Vector((0, 1, 0)))
        if side.length < 1e-3: side = d.cross(Vector((1, 0, 0)))
        side.normalize()
        u = i / n
        w = width * math.sin(math.pi * min(1.0, 0.15 + u * 0.95)) ** 0.7 * (1 if i < n else 0.05)
        a, b = bm.verts.new(c + side * w), bm.verts.new(c - side * w)
        if prev:
            f = bm.faces.new((prev[0], a, b, prev[1])); f.material_index = mat_index
        prev = (a, b)
