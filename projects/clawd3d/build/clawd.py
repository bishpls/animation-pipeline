"""Clawd (TSUZUKU's idol) as a 3D cel-shaded character, built by script in headless Blender 5.2.

Everything is measured off the 2D rig's base drawing (~/animation-pipeline/projects/tsuzuku/rig/clawd/base.png, 2160x3840,
soles at y=3700) so the 3D model sits on the drawing in a front orthographic view (see --views: ref_overlay.png). The face is
the drawing's own: faces.py cuts the rig's eye and mouth layers into decals, swapped per expression like the 2D rig's variants.
The armature uses VRM 1.0 humanoid bone names (hips, spine, chest, upperChest, neck, head, leftUpperArm, ...), so motion
retargeted onto VRM humanoid lands here, and a VRM export needs no renaming.

    blender -b --factory-startup --python projects/clawd3d/build/clawd.py -- --views projects/clawd3d/out/views [--blend out.blend]
    (import it from a shot script: sys.path.insert(0, build dir); import clawd; C = clawd.build())
"""
import json, math, os, sys
import bpy, bmesh
from mathutils import Vector, Matrix, Euler, Quaternion

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kit
import head as headlib
import hair as hairlib
from kit import hexc, toon, flat, add_outline, mesh_from_bm, bone_parent, link

PROJ = os.path.dirname(HERE)
TEX = os.path.join(PROJ, 'out', 'tex')

# ---------------------------------------------------------------- the drawing's frame
S = 1.55 / 3550           # metres per drawing px (soles y=3700 to the top of the skull's hair y=150)
CX, SOLE = 1070, 3700      # the body's centre line in the drawing (legs 1071-1078, face 1064)
FCX, EYE_Y = 1064, 565     # the drawn face's centre and eye line


def D(x, y, depth=0.0):
    """drawing px -> world (her right is image-left, -X; front is -Y)."""
    return Vector(((x - CX) * S, depth, (SOLE - y) * S))


PAL = {  # sampled from base.png; shade = the cel shadow tone
    'orange': (hexc('e07b51'), hexc('b3503a')), 'cream': (hexc('fbebc4'), hexc('e2c69a')),
    'brown': (hexc('473632'), hexc('2c201e')), 'skin': (hexc('fddbc4'), hexc('eeaf9a')),
    'white': (hexc('f6f5f5'), hexc('cbc6d2')), 'cuff': (hexc('f3946a'), hexc('c9654a')),
    'hair': (hexc('e27c52'), hexc('b24f37')), 'star': (hexc('f7d23e'), hexc('d9a21f')),
    'crab': (hexc('e0513a'), hexc('a8322a')), 'navy': (hexc('3b3446'), hexc('241f2c')),
}
kit.LINE = hexc('3a2320')


def M(name, **kw):
    """a three-tone cel material from the palette: lit, shadow, and a deeper warm core shadow."""
    base, shade = PAL[name.split('_')[0]]
    deep = tuple(c * 0.82 for c in shade)
    return kit.toon3(name, base, shade, deep, **kw)


# ---------------------------------------------------------------- skeleton (drawing px, depth m, radii m)
J = {'pelvis': (1083, 1880, 0.0, 0.092, 0.074), 'waist': (1083, 1560, 0.004, 0.066, 0.054),
     'chest': (1083, 1300, 0.0, 0.078, 0.060), 'uchest': (1083, 1070, 0.006, 0.080, 0.056),
     'neckb': (1083, 885, 0.012, 0.028, 0.028), 'neckt': (1083, 800, 0.010, 0.026, 0.026)}
SIDE = {'shoulder': (800, 1012, 0.008, 0.034, 0.034), 'elbow': (611, 1373, 0.006, 0.027, 0.026),
        'wrist': (440, 1680, 0.0, 0.021, 0.017),
        'hip': (958, 1900, 0.0, 0.074, 0.072), 'thighm': (905, 2150, 0.0, 0.066, 0.066),
        'knee': (890, 2500, -0.004, 0.045, 0.048), 'calf': (890, 2790, 0.004, 0.055, 0.056),
        'ankle': (893, 3420, 0.012, 0.042, 0.044), 'heel': (893, 3640, 0.030, 0.034, 0.036),
        'toe': (893, 3650, -0.100, 0.036, 0.026)}
for s, sx in (('R', 1), ('L', -1)):          # SIDE is authored on her right (image-left); L mirrors it
    for k, (x, y, d, rx, ry) in SIDE.items():
        J[f'{k}.{s}'] = (x if s == 'R' else 2 * CX - x, y, d, rx, ry)


def P(j):
    x, y, d = J[j][:3]
    return D(x, y, d)


EDGES = [('pelvis', 'waist'), ('waist', 'chest'), ('chest', 'uchest'), ('uchest', 'neckb'), ('neckb', 'neckt')]
for s in 'LR':
    EDGES += [('uchest', f'shoulder.{s}'), (f'shoulder.{s}', f'elbow.{s}'), (f'elbow.{s}', f'wrist.{s}'),
              ('pelvis', f'hip.{s}'), (f'hip.{s}', f'thighm.{s}'), (f'thighm.{s}', f'knee.{s}'),
              (f'knee.{s}', f'calf.{s}'), (f'calf.{s}', f'ankle.{s}'), (f'ankle.{s}', f'heel.{s}'), (f'ankle.{s}', f'toe.{s}')]

# VRM 1.0 humanoid: bone -> (head joint, tail joint, parent)
BONES = {'hips': ('pelvis', 'waist', None), 'spine': ('waist', 'chest', 'hips'), 'chest': ('chest', 'uchest', 'spine'),
         'upperChest': ('uchest', 'neckb', 'chest'), 'neck': ('neckb', 'neckt', 'upperChest'), 'head': ('neckt', None, 'neck')}
for s, side in (('L', 'left'), ('R', 'right')):
    BONES.update({f'{side}Shoulder': (f'clav.{s}', f'shoulder.{s}', 'upperChest'),
                  f'{side}UpperArm': (f'shoulder.{s}', f'elbow.{s}', f'{side}Shoulder'),
                  f'{side}LowerArm': (f'elbow.{s}', f'wrist.{s}', f'{side}UpperArm'),
                  f'{side}Hand': (f'wrist.{s}', f'handend.{s}', f'{side}LowerArm'),
                  f'{side}UpperLeg': (f'hip.{s}', f'knee.{s}', 'hips'),
                  f'{side}LowerLeg': (f'knee.{s}', f'ankle.{s}', f'{side}UpperLeg'),
                  f'{side}Foot': (f'ankle.{s}', f'toe.{s}', f'{side}LowerLeg'),
                  f'{side}Toes': (f'toe.{s}', f'toetip.{s}', f'{side}Foot')})


# ---------------------------------------------------------------- hands: a hand frame at each wrist, fingers in it
FINGERS = {  # name: (base across the knuckles -1..1, base along from the wrist, segment lengths, radius, splay deg)
    'Index': (0.62, 0.078, (0.027, 0.018, 0.016), 0.0062, 6), 'Middle': (0.2, 0.082, (0.030, 0.020, 0.017), 0.0064, 1),
    'Ring': (-0.22, 0.078, (0.027, 0.018, 0.016), 0.0060, -4), 'Little': (-0.62, 0.070, (0.021, 0.014, 0.013), 0.0053, -10)}
THUMB = ((0.62, 0.030), (0.026, 0.022, 0.019), 0.0075)            # base (across, along), segments, radius


def hand_frame(s):
    w, e = P(f'wrist.{s}'), P(f'elbow.{s}')
    along = (w - e).normalized()
    inward = Vector((1 if s == 'R' else -1, 0, 0))                  # toward the body: palms face the thighs
    palm = (inward - along * inward.dot(along)).normalized()
    across = along.cross(palm).normalized()                         # the thumb side should face forward (-Y)
    if across.y > 0:
        across = -across
    return w, along, palm, across


HANDJ = {}
for _s in 'LR':
    w, al, pa, ac = hand_frame(_s)
    HANDJ[f'palm.{_s}'] = w + al * 0.045
    HANDJ[f'knuckle.{_s}'] = w + al * 0.082
    for fn, (x, base, segs, r, splay) in FINGERS.items():
        q = Matrix.Rotation(math.radians(splay) * (1 if _s == 'L' else -1), 3, pa)
        d = q @ al
        p = w + al * base + ac * x * 0.042
        HANDJ[f'{fn}0.{_s}'] = p
        for i, L_ in enumerate(segs):
            d = (Matrix.Rotation(math.radians(9), 3, ac) @ d).normalized()          # a relaxed curl
            p = p + d * L_
            HANDJ[f'{fn}{i + 1}.{_s}'] = p
    (tx, ta), tsegs, tr = THUMB
    p = w + al * ta + ac * tx * 0.040 + pa * 0.010
    HANDJ[f'Thumb0.{_s}'] = p
    d = (al * 0.7 + ac * 0.55 + pa * 0.42).normalized()
    for i, L_ in enumerate(tsegs):
        p = p + d * L_
        HANDJ[f'Thumb{i + 1}.{_s}'] = p
        d = (d + al * 0.25).normalized()

BONES['hairSpring'] = ('hairpivot', 'hairtip', 'head')             # secondary motion (motion.bake springs)
BONES['skirtSpring'] = ('skirtpivot', 'skirttip', 'hips')
SPRINGS = {'hairSpring': (90.0, 11.0, 14.0), 'skirtSpring': (140.0, 13.0, 12.0)}
for s, side in (('L', 'left'), ('R', 'right')):
    BONES[f'{side}Hand'] = (f'wrist.{s}', f'knuckle.{s}', f'{side}LowerArm')
    BONES[f'{side}ThumbMetacarpal'] = (f'Thumb0.{s}', f'Thumb1.{s}', f'{side}Hand')
    BONES[f'{side}ThumbProximal'] = (f'Thumb1.{s}', f'Thumb2.{s}', f'{side}ThumbMetacarpal')
    BONES[f'{side}ThumbDistal'] = (f'Thumb2.{s}', f'Thumb3.{s}', f'{side}ThumbProximal')
    for fn in FINGERS:
        BONES[f'{side}{fn}Proximal'] = (f'{fn}0.{s}', f'{fn}1.{s}', f'{side}Hand')
        BONES[f'{side}{fn}Intermediate'] = (f'{fn}1.{s}', f'{fn}2.{s}', f'{side}{fn}Proximal')
        BONES[f'{side}{fn}Distal'] = (f'{fn}2.{s}', f'{fn}3.{s}', f'{side}{fn}Intermediate')


def joint(j):
    if j in HANDJ:
        return HANDJ[j]
    if j == 'hairpivot':
        return HC + Vector((0, 0.01, 0.10))
    if j == 'hairtip':
        return HC + Vector((0, 0.06, -0.10))
    if j == 'skirtpivot':
        return D(CX, 1372) + Vector((0, 0.004, 0))
    if j == 'skirttip':
        return D(CX, 2000) + Vector((0, 0.004, 0))
    if j.startswith('clav.'):
        s = j[-1]
        return P('uchest') + Vector((0.022 * (1 if s == 'L' else -1), 0.0, 0.035))
    if j.startswith('toetip.'):
        return P('toe.' + j[-1]) + Vector((0, -0.045, 0))
    return P(j)


# ---------------------------------------------------------------- body
def build_body():
    names = list(J.keys())
    me = bpy.data.meshes.new('body_skel')
    me.from_pydata([P(n) for n in names], [(names.index(a), names.index(b)) for a, b in EDGES], [])
    ob = link(bpy.data.objects.new('body', me))
    sk = ob.modifiers.new('skin', 'SKIN'); sk.use_smooth_shade = True; sk.branch_smoothing = 0.7
    for i, n in enumerate(names):
        ob.data.skin_vertices[0].data[i].radius = J[n][3:5]
        ob.data.skin_vertices[0].data[i].use_root = (n == 'pelvis')
    ss = ob.modifiers.new('sub', 'SUBSURF'); ss.levels = ss.render_levels = 2
    bpy.context.view_layer.objects.active = ob; ob.select_set(True)
    bpy.ops.object.modifier_apply(modifier='skin'); bpy.ops.object.modifier_apply(modifier='sub')
    for v in ob.data.vertices:
        co = v.co
        if 1.08 < co.z < 1.20 and co.y < -0.02:                       # a little bust under the jacket
            k = math.exp(-((co.z - 1.13) / 0.035) ** 2) * math.exp(-((abs(co.x) - 0.045) / 0.035) ** 2)
            co.y -= 0.018 * k
        if 0.74 < co.z < 0.92 and abs(co.x) < 0.14:                   # hips
            co.x *= 1.0 + 0.05 * math.exp(-((co.z - 0.83) / 0.05) ** 2)
    for p in ob.data.polygons:
        p.use_smooth = True
    mats = [M('skin', thresh=0.36), M('orange', rim_amt=0.3), M('cream'), M('brown'), M('white', thresh=0.5),
            M('brown_sole'), flat('skin_neck', hexc('eeac9a'))]
    for m in mats:
        ob.data.materials.append(m)
    for p in ob.data.polygons:
        c = p.center; ax = abs(c.x); side = 'L' if c.x > 0 else 'R'
        idx = 0
        on_arm = ax > 0.105 and c.z > 0.78
        if not on_arm:
            if c.z > 1.19:
                idx = 6 if c.z > HC.z - 0.118 else 0                    # the chin's shadow on the neck, always
            elif c.z > 1.0:
                idx = 2 if (c.y < -0.02 and ax < 0.028) else 1          # jacket, cream blouse down the front
            elif c.z > 0.70:
                idx = 3                                                 # shorts (under the skirt)
            elif c.z > 0.38:
                idx = 0                                                 # thighs and knees
            else:
                idx = 5 if c.z < 0.016 else 4                           # soles, white boots
        else:
            sh, el = P(f'shoulder.{side}'), P(f'elbow.{side}')
            t = (c - sh).dot(el - sh) / (el - sh).length_squared
            idx = 1 if t < 0.45 else 0                                   # sleeve over the shoulder, bare arm below
        p.material_index = idx
    add_outline(ob, 0.0028)
    return ob


def build_hands(arm):
    """Each hand: a skin-modifier graph (wrist, palm, knuckles, three joints per finger, the thumb) with slender radii,
    subdivided, bound to the hand and finger bones."""
    out = []
    for s in 'LR':
        w, al, pa, ac = hand_frame(s)
        names, pts, rad = [], [], []

        def add(n, p, r):
            names.append(n); pts.append(p); rad.append(r)
        add('w', w - al * 0.012, (0.021, 0.017))
        add('palm', HANDJ[f'palm.{s}'], (0.034, 0.012))
        edges = [(0, 1)]
        for fn, (x, base, segs, r, splay) in FINGERS.items():
            i0 = len(names)
            add(fn + '0', HANDJ[f'{fn}0.{s}'], (r * 1.25, r * 1.05))
            edges.append((1, i0))
            for i in range(3):
                add(fn + str(i + 1), HANDJ[f'{fn}{i + 1}.{s}'], (r * (0.92 - 0.12 * i), r * (0.88 - 0.12 * i)))
                edges.append((i0 + i, i0 + i + 1))
        i0 = len(names)
        add('t0', HANDJ[f'Thumb0.{s}'], (0.0095, 0.0085))
        edges.append((0, i0))
        for i in range(3):
            add('t' + str(i + 1), HANDJ[f'Thumb{i + 1}.{s}'], (0.0074 - 0.0008 * i, 0.0068 - 0.0008 * i))
            edges.append((i0 + i, i0 + i + 1))
        me = bpy.data.meshes.new(f'hand.{s}')
        me.from_pydata(pts, edges, [])
        ob = link(bpy.data.objects.new(f'hand.{s}', me))
        sk = ob.modifiers.new('skin', 'SKIN'); sk.use_smooth_shade = True; sk.branch_smoothing = 0.4
        for i, r in enumerate(rad):
            ob.data.skin_vertices[0].data[i].radius = r
            ob.data.skin_vertices[0].data[i].use_root = (i == 0)
        ss = ob.modifiers.new('sub', 'SUBSURF'); ss.levels = ss.render_levels = 2
        bpy.ops.object.select_all(action='DESELECT'); bpy.context.view_layer.objects.active = ob; ob.select_set(True)
        bpy.ops.object.modifier_apply(modifier='skin'); bpy.ops.object.modifier_apply(modifier='sub')
        for p in ob.data.polygons:
            p.use_smooth = True
        ob.data.materials.append(M('skin', thresh=0.36))
        add_outline(ob, 0.0014, hexc('9a5a4a'))
        bind(ob, arm)
        out.append(ob)
    return out


def build_armature():
    return kit.armature('clawd_rig', BONES, joint, joint)


def bind(ob, arm):
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True); arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    ob.modifiers.move(ob.modifiers.find('Armature'), 0)


# ---------------------------------------------------------------- head and face
HC = Vector((0.0, 0.004, (SOLE - EYE_Y) * S))     # head centre: the eye line, on the body's centre line
HR = Vector((0.077, 0.0845, 0.117))              # the head's half-extents at the eye line (head.py builds the real shape)


def build_head(arm):
    face = headlib.face_material('skin_face', PAL['skin'][0], hexc('f2b6a6'))
    ob = headlib.build(HC, arm, 'head', mats=[face])
    add_outline(ob, 0.0018, hexc('9a5a4a'))
    return ob


def build_face(head, arm):
    """Decal shells, one per eye state and per mouth shape, front-projected with faces.py's window, cut from the head's
    subdivided surface so they sit on it."""
    win = json.load(open(os.path.join(TEX, 'window.json')))
    x0, y0, s = win['window']
    u0, u1 = (x0 - FCX) * S, (x0 + s - FCX) * S
    zt, zb = HC.z + (EYE_Y - y0) * S, HC.z + (EYE_Y - (y0 + s)) * S
    split = HC.z + (EYE_Y - 640) * S                    # eyes above, mouth below
    dg = bpy.context.evaluated_depsgraph_get()
    ev = head.evaluated_get(dg)
    src = bpy.data.meshes.new_from_object(ev)
    mw = head.matrix_world.copy()
    shells = {}
    for kind, names in (('eyes', win['eyes']), ('mouth', win['mouths'])):
        for nm in names:
            bm = bmesh.new(); bm.from_mesh(src)
            bmesh.ops.transform(bm, matrix=mw, verts=bm.verts)
            bm.normal_update()
            kill = [f for f in bm.faces if f.normal.y > -0.3 or not (u0 < f.calc_center_median().x < u1) or
                    (f.calc_center_median().z < split if kind == 'eyes' else f.calc_center_median().z > split + 0.012)]
            bmesh.ops.delete(bm, geom=kill, context='FACES')
            bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
            for v in bm.verts:
                v.co += v.normal * 0.0007
            for lyr in list(bm.loops.layers.uv):
                bm.loops.layers.uv.remove(lyr)
            uv = bm.loops.layers.uv.new()
            for f in bm.faces:
                for l in f.loops:
                    co = l.vert.co
                    l[uv].uv = ((co.x - u0) / (u1 - u0), (co.z - zb) / (zt - zb))
            ob = mesh_from_bm(f'{kind}_{nm}', bm, [kit.decal(f'{kind}_{nm}', os.path.join(TEX, f'{kind}_{nm}.png'))])
            bone_parent(ob, arm, 'head')
            shells[(kind, nm)] = ob
    bpy.data.meshes.remove(src)
    set_face(shells, 'open', 'rest')
    return shells


def set_face(shells, eyes, mouth, frame=None):
    for (kind, nm), ob in shells.items():
        on = nm == (eyes if kind == 'eyes' else mouth)
        ob.hide_render = not on; ob.hide_viewport = not on
        if frame is not None:
            ob.keyframe_insert('hide_render', frame=frame); ob.keyframe_insert('hide_viewport', frame=frame)


# ---------------------------------------------------------------- hair
def skull(az, el, r=1.0):
    """a point on the hair shell: az degrees around Z from the front (+ = her left), el degrees up from the eye line."""
    a, e = math.radians(az), math.radians(el)
    return HC + Vector((math.sin(a) * math.cos(e) * HR.x * 1.08 * r, -math.cos(a) * math.cos(e) * HR.y * 1.06 * r,
                        math.sin(e) * HR.z * 1.05 * r + 0.004))


def wavy(p0, p1, bulge, waves, amp, n=14, flick=Vector()):
    """points from p0 to p1 bowed by `bulge` (a vector at mid-length), with a sideways wave and a flicked tip."""
    d = (p1 - p0)
    side = d.cross(Vector((0, 0, 1)))
    side = side.normalized() if side.length > 1e-6 else Vector((1, 0, 0))
    pts = []
    for i in range(n + 1):
        u = i / n
        c = p0 + d * u + bulge * (4 * u * (1 - u)) + side * amp * math.sin(waves * math.pi * u) * u + flick * u ** 4
        pts.append(c)
    return pts


HAIR_TOP, HAIR_BOT = 0.165, 0.135       # the mass's height above the eye line, and its drop below it at the sides
HAIR_RX = 0.148                          # half-width at the eye line (the drawing's hair is ~0.3 m across)


def shell(az, el, r=1.0):
    """The hair mass's surface: a full dome (wide at the sides, close over the forehead) that bulges a little below the
    eye line and hangs to the collar. az degrees around Z from the front (+ = her left), el degrees from the eye line
    (-60 = the bottom edge)."""
    a, e = math.radians(az), math.radians(el)
    back = 0.5 - 0.5 * math.cos(a)                          # 0 at the front, 1 at the back
    ry0 = 0.101 + 0.032 * back
    if e >= 0:
        c = math.cos(e) ** 0.6
        x, y, z = math.sin(a) * c * HAIR_RX, -math.cos(a) * c * ry0, math.sin(e) * HAIR_TOP
    else:
        f = min(1.0, -e / math.radians(60))
        rr = 1 + 0.2 * math.sin(f * math.pi * 0.85)          # bulges at the cheeks, curls back in at the ends
        x, y, z = math.sin(a) * HAIR_RX * rr, -math.cos(a) * ry0 * rr, -HAIR_BOT * f
    return HC + Vector((x * r, y * r, z * r + 0.004))


def face_cut(az):
    """the lowest elevation the mass reaches at this azimuth: above the brows over the face, down to the collar beside it."""
    a = abs(((az + 180) % 360) - 180)
    if a < 50:
        return 26.0
    if a < 78:
        return 26.0 - 86.0 * ((a - 50) / 28) ** 1.4
    return -60.0


def skull(az, el, r=1.0):
    return shell(az, el, r)


def build_hair(arm):
    V = hairlib.Volume()
    global HAIRV
    HAIRV = V
    hm = hairlib.hair_material('hair', hexc('e8825a'), hexc('c65c42'), hexc('9c3f33'), head_z=HC.z)
    um = kit.toon3('hair_under', hexc('c65c42'), hexc('a8483a'), hexc('86332c'))
    objs = hairlib.build(HC, arm, 'head', hm, um, V, spring_bone='hairSpring')
    hairM = hm

    def shell(az, el, r=1.0):
        return HC + V.point(az, el, r)
    skull = shell
    # the buns: chunky rounded blocks (her pixel claws), a slab with a smaller one behind, tilted out
    parts = []
    for sx in (-1, 1):
        c = shell(sx * 66, 56, 1.24)
        rot = Euler((math.radians(-8), sx * math.radians(6), sx * math.radians(-22)), 'XYZ').to_matrix().to_4x4()
        bm = kit.rounded_box((0.088, 0.056, 0.082), 0.022, 4, Matrix.Translation(c) @ rot)
        bm2 = kit.rounded_box((0.070, 0.046, 0.062), 0.018, 4,
                              Matrix.Translation(c + Vector((sx * 0.014, 0.024, -0.030))) @ rot)
        tmp = bpy.data.meshes.new('tmp'); bm2.to_mesh(tmp); bm2.free(); bm.from_mesh(tmp); bpy.data.meshes.remove(tmp)
        bun = mesh_from_bm(f'bun.{"L" if sx > 0 else "R"}', bm, [kit.toon3('hair_bun', hexc('e8825a'), hexc('c65c42'), hexc('9c3f33'))])
        sub = bun.modifiers.new('sub', 'SUBSURF'); sub.levels = sub.render_levels = 2          # soft pillows, not blocks
        add_outline(bun, 0.0022, hexc('7a3524')); bone_parent(bun, arm, 'head'); parts.append(bun)
    # the clip on her left: a little crab and an eight-point star
    cc = D(1238, 330, -0.0)
    cc.y = skull(38, 34, 1.12).y
    bm = bmesh.new()
    for off, sc_, r in (((0, 0, 0), (0.013, 0.007, 0.009), 1), ((-0.014, -0.002, 0.008), (0.006, 0.005, 0.007), 1),
                        ((0.014, -0.002, 0.008), (0.006, 0.005, 0.007), 1), ((-0.005, -0.006, 0.006), (0.0025,) * 3, 1),
                        ((0.005, -0.006, 0.006), (0.0025,) * 3, 1)):
        g = bmesh.ops.create_uvsphere(bm, u_segments=14, v_segments=9, radius=1.0)
        for v in g['verts']:
            v.co = cc + Vector(off) + Vector((v.co.x * sc_[0], v.co.y * sc_[1], v.co.z * sc_[2]))
    crab = mesh_from_bm('clip_crab', bm, [M('crab', rim_amt=0.4)]); add_outline(crab, 0.0010); bone_parent(crab, arm, 'head')
    sc = D(1305, 318) ; sc.y = skull(48, 36, 1.13).y
    bm = bmesh.new()
    rim = []
    for i in range(16):
        a = math.pi / 2 + i * math.pi / 8
        r = 0.038 if i % 2 == 0 else 0.011
        if i % 4 == 2:
            r = 0.024
        rim.append(bm.verts.new(sc + Vector((math.cos(a) * r, -0.006, math.sin(a) * r))))
    ctr = bm.verts.new(sc + Vector((0, -0.012, 0)))
    for i in range(16):
        bm.faces.new((ctr, rim[i], rim[(i + 1) % 16]))
    star = mesh_from_bm('clip_star', bm, [M('star', rim_amt=0.5)], smooth=False)
    add_outline(star, 0.0012); bone_parent(star, arm, 'head')
    return objs + [crab, star] + parts


# ---------------------------------------------------------------- clothes
def build_sleeves(arm):
    out = []
    for s, side in (('L', 'left'), ('R', 'right')):
        sh, el = P(f'shoulder.{s}'), P(f'elbow.{s}')
        d = (el - sh).normalized()
        c = sh + (el - sh) * 0.22
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=16, radius=1.0)
        q = d.to_track_quat('Z', 'Y').to_matrix().to_4x4()
        for v in bm.verts:                                          # a puff: round, gathered at the cuff end
            x, y, z = v.co
            k = 1.0 - 0.35 * max(0.0, z) ** 2
            v.co = Vector((x * 0.058 * k, y * 0.056 * k, z * 0.070))
        bmesh.ops.transform(bm, matrix=Matrix.Translation(c) @ q, verts=bm.verts)
        puff = mesh_from_bm(f'sleeve.{s}', bm, [M('orange_sleeve', rim_amt=0.3)])
        add_outline(puff, 0.0024); bone_parent(puff, arm, f'{side}UpperArm')
        bm = bmesh.new()
        kit.band(bm, sh + (el - sh) * 0.47, d, 0.036, 0.033, 0.026, bulge=0.004)
        cuff = mesh_from_bm(f'sleevecuff.{s}', bm, [M('cream_cuff')])
        add_outline(cuff, 0.0018); bone_parent(cuff, arm, f'{side}UpperArm')
        wr = P(f'wrist.{s}'); el2 = P(f'elbow.{s}')
        bm = bmesh.new()
        kit.band(bm, el2 + (wr - el2) * 0.80, (wr - el2), 0.030, 0.031, 0.040, bulge=0.002)
        wc = mesh_from_bm(f'wristcuff.{s}', bm, [M('orange_cuff')])
        add_outline(wc, 0.0018); bone_parent(wc, arm, f'{side}LowerArm')
        out += [puff, cuff, wc]
    return out


def build_top(arm):
    """Sailor collar over the shoulders and the big cream bow."""
    out = []
    nb = P('neckb')
    body = bpy.data.objects['body']
    bpy.context.view_layer.update()

    def on_body(p, lift=0.006):
        """drop a point onto the shoulders from above (they slope); only hits within 10 cm under the neck count, so a ray
        that slips past the chest can't land on a thigh and stretch the collar to the boots."""
        hit, loc, nrm, _ = body.ray_cast(p + Vector((0, 0, 0.3)), Vector((0, 0, -1)), distance=0.4)
        if hit:
            return loc + nrm * lift
        r = Vector((p.x, p.y - nb.y)).length
        return Vector((p.x, p.y, nb.z - 0.55 * max(0.0, r - 0.03)))

    # a sailor collar: a ring round the neck over the shoulders, open in a V at the front, a square flap down the back
    NA = 48
    rings = []
    bm = bmesh.new()
    for j, r in enumerate((0.030, 0.058, 0.086, 0.104)):
        ring = []
        for i in range(NA):
            a = 2 * math.pi * i / NA
            p = Vector((math.sin(a) * r * 1.12, -math.cos(a) * r * 0.9 + nb.y, nb.z))
            q = on_body(p)
            if j == 0:
                q.z = max(q.z, nb.z - 0.004)
            ring.append(bm.verts.new(q))
        rings.append(ring)
    for j in range(3):
        for i in range(NA):
            deg = abs(((i + 0.5) / NA * 360 + 180) % 360 - 180)
            if deg < 30 + 4 * j:                                            # the V at the front
                continue
            if deg > 150 and j == 2:                                        # the back flap takes over here
                continue
            bm.faces.new((rings[j][i], rings[j][(i + 1) % NA], rings[j + 1][(i + 1) % NA], rings[j + 1][i]))
    # the back flap: follows the upper back from the collar ring down, square cut
    cols, rows = 9, 7
    flap = []
    for jr in range(rows):
        row = []
        z = nb.z - 0.03 - jr * 0.017
        for ic in range(cols):
            x = -0.066 + 0.132 * ic / (cols - 1)
            hit, loc, nrm, _ = body.ray_cast(Vector((x, 0.4, z)), Vector((0, -1, 0)))
            p = loc + Vector((0, 0.006, 0)) if hit else Vector((x, 0.06, z))
            row.append(bm.verts.new(p))
        flap.append(row)
    for jr in range(rows - 1):
        for ic in range(cols - 1):
            bm.faces.new((flap[jr][ic], flap[jr][ic + 1], flap[jr + 1][ic + 1], flap[jr + 1][ic]))
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    col = mesh_from_bm('collar', bm, [M('cream_collar', thresh=0.4), M('navy')])
    for p in col.data.polygons:
        c = p.center
        edge_ring = 0.080 < (Vector((c.x / 1.12, (c.y - nb.y) / 0.9))).length < 0.090 and c.y < 0.03
        edge_flap = c.y > 0.03 and (abs(abs(c.x) - 0.052) < 0.006 or abs(c.z - (nb.z - 0.03 - 5 * 0.017 + 0.004)) < 0.006)
        p.material_index = 1 if (edge_ring or edge_flap) else 0
    add_outline(col, 0.0018); bone_parent(col, arm, 'upperChest'); out.append(col)
    # the bow: two loops, a knot, two tails
    bc = D(CX, 1000, -0.068)
    bm = bmesh.new()
    for sx in (-1, 1):
        g = bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=1.0)
        vs = g['verts']
        for v in vs:
            x, y, z = v.co
            w = 1 - 0.45 * (1 - (x * sx + 1) / 2)                       # pinched toward the knot
            v.co = bc + Vector((sx * 0.052 + x * 0.052, y * 0.016 - 0.004, z * 0.034 * w + sx * 0.0))
    g = bmesh.ops.create_uvsphere(bm, u_segments=14, v_segments=10, radius=1.0)
    for v in g['verts']:
        v.co = bc + Vector((v.co.x * 0.018, v.co.y * 0.016 - 0.012, v.co.z * 0.020))
    for sx in (-1, 1):
        kit.lock(bm, [bc + Vector((sx * (0.008 + 0.025 * u), -0.004 + 0.012 * u, -0.012 - 0.11 * u)) for u in [i / 8 for i in range(9)]],
                 0.022, bc + Vector((0, 0.1, 0)), thick=0.18, taper=0.25, tip=0.6)
    bow = mesh_from_bm('bow', bm, [M('cream_bow', rim_amt=0.3)])
    add_outline(bow, 0.0018); bone_parent(bow, arm, 'upperChest'); out.append(bow)
    return out


def phi_of(v):
    """angle from her front (-Y), degrees, + toward her left."""
    return math.degrees(math.atan2(v.x, -v.y))


def build_skirt(arm):
    """The A-line skirt: orange pleats with the pixel-staircase hem band, the cream front panel, and a dark underskirt
    whose stepped tails hang longer at the back."""
    zw = D(CX, 1372).z
    wx, wy = 0.074, 0.062
    out = []
    for layer, (hx, hy, name) in enumerate(((0.285, 0.235, 'skirt'), (0.262, 0.215, 'underskirt'))):
        NR, NA = 18, 96
        bm = bmesh.new()
        grid = []
        for i in range(NR + 1):
            t = 1 - (1 - i / NR) ** 1.5
            ring = []
            for k in range(NA):
                th = 2 * math.pi * k / NA
                ph = math.degrees(th)                          # 0 = front
                f = math.sin(t * math.pi / 2) ** 0.85
                rx, ry = wx + (hx - wx) * f, wy + (hy - wy) * f
                if layer == 0:                                  # box pleats: flat panels, sharp folds (a triangle wave)
                    u = (th * 10 / (2 * math.pi)) % 1.0
                    tri = 1 - 4 * abs(u - 0.5)                  # -1 at the fold in, +1 at the fold out
                    pleat = 1 + 0.075 * t ** 1.1 * tri
                else:
                    pleat = 1 + 0.01 * t * math.sin(18 * th)     # a softer ruffle on the underskirt
                if layer == 0:
                    zh = D(CX, 2000).z + 0.012 * min(1, abs(((ph + 180) % 360) - 180) / 180)
                else:
                    a = abs(((ph + 180) % 360) - 180)
                    step = math.floor(a / 18)
                    zh = D(CX, 1990).z - 0.14 * min(1, max(0, (step * 18 - 50) / 110)) ** 1.2
                z = zw + (zh - zw) * t
                ring.append(bm.verts.new(Vector((math.sin(th) * rx * pleat, -math.cos(th) * ry * pleat + 0.004, z))))
            grid.append(ring)
        for i in range(NR):
            for k in range(NA):
                bm.faces.new((grid[i][k], grid[i + 1][k], grid[i + 1][(k + 1) % NA], grid[i][(k + 1) % NA]))
        bm.normal_update()                                   # face outward (the lining and the outline depend on it)
        inward = [f for f in bm.faces if f.normal.dot(Vector((f.calc_center_median().x, f.calc_center_median().y, 0))) < 0]
        bmesh.ops.reverse_faces(bm, faces=inward)
        mats = [M('orange_skirt', rim_amt=0.25), M('brown_hem'), M('cream_panel')]
        ob = mesh_from_bm(name, bm, mats if layer == 0 else [M('brown_under')])
        # the folds are hard edges: the cel ramp then lights the pleat panels in alternating tones
        ob.data.set_sharp_from_angle(angle=math.radians(14))
        if layer == 0:
            for p in ob.data.polygons:
                c = p.center; ph = phi_of(c); a = abs(ph)
                sector = math.floor((ph + 180) / 15)
                band_top = D(CX, 2000).z + 0.03 + 0.024 * ((sector * 5) % 3)
                if a < 17:
                    p.material_index = 2
                elif c.z < band_top:
                    p.material_index = 1
        add_outline(ob, 0.0024)

        def weights(co, zw=zw):
            t = min(1.0, max(0.0, (zw - co.z) / 0.28))
            w_leg = 0.45 * t ** 1.3
            w_spr = 0.40 * t ** 1.6
            wl = min(1.0, max(0.0, 0.5 + co.x / 0.14))
            return {'hips': 1 - w_leg - w_spr, 'skirtSpring': w_spr, 'leftUpperLeg': w_leg * wl,
                    'rightUpperLeg': w_leg * (1 - wl)}
        kit.skin_to(ob, arm, weights)
        out.append(ob)
        if layer == 0:
            # the lining: the skirt's surface a few millimetres inside, facing in, darker (seen when the skirt lifts)
            me = ob.data.copy(); me.name = 'skirt_lining'
            for v in me.vertices:
                v.co -= v.normal * 0.0035
            me.flip_normals()
            me.materials.clear(); me.materials.append(M('brown_lining'))
            for pp in me.polygons:
                pp.material_index = 0
            lin_ob = link(bpy.data.objects.new('skirt_lining', me))
            for g in ob.vertex_groups:
                lin_ob.vertex_groups.new(name=g.name)
            kit_mod = lin_ob.modifiers.new('rig', 'ARMATURE'); kit_mod.object = arm; lin_ob.parent = arm
            out.append(lin_ob)
    # waistband
    bm = bmesh.new()
    kit.band(bm, Vector((0, 0.004, zw)), Vector((0, 0, 1)), 0.078, 0.076, 0.03, bulge=0.003)
    for v in bm.verts:
        v.co.y = 0.004 + (v.co.y - 0.004) * 0.84
    wb = mesh_from_bm('waistband', bm, [M('orange_band')])
    add_outline(wb, 0.0018); bone_parent(wb, arm, 'hips'); out.append(wb)
    return out


def build_boot_cuffs(arm):
    out = []
    for s, side in (('L', 'left'), ('R', 'right')):
        kn, an = P(f'knee.{s}'), P(f'ankle.{s}')
        c = kn + (an - kn) * 0.30
        c.z = D(CX, 2840).z
        bm = bmesh.new()
        kit.band(bm, c, kn - an, 0.063, 0.066, 0.05, bulge=0.003)
        ob = mesh_from_bm(f'bootcuff.{s}', bm, [M('cuff_boot', rim_amt=0.3)])
        add_outline(ob, 0.002); bone_parent(ob, arm, f'{side}LowerLeg'); out.append(ob)
    return out


# ---------------------------------------------------------------- everything
def build(clear=True):
    if clear:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        kit.MATS.clear()
    arm = build_armature()
    body = build_body(); bind(body, arm)
    hands = build_hands(arm)
    head = build_head(arm)
    face = build_face(head, arm)
    hair = build_hair(arm)
    clothes = build_sleeves(arm) + build_top(arm) + build_skirt(arm) + build_boot_cuffs(arm)
    return {'arm': arm, 'body': body, 'hands': hands, 'head': head, 'face': face, 'hair': hair, 'clothes': clothes}


def render_views(outdir):
    os.makedirs(outdir, exist_ok=True)
    sc = kit.setup_render(res=(1080, 1920), pct=50, bg=(1, 1, 1))
    cam = kit.camera('cam', ortho=3840 * S)
    ctr = D(1080, 1920)
    kit.aim(cam, ctr + Vector((0, -4, 0)), ctr)
    sc.render.filepath = os.path.join(outdir, 'front_ortho.png'); bpy.ops.render.render(write_still=True)
    sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
    cam.data.type = 'PERSP'; cam.data.lens = 50
    tgt = Vector((0, 0, 0.82))
    for name, az in (('front', 0), ('three_q', 35), ('side', 90), ('back', 180), ('three_q_back', 215)):
        a = math.radians(az)
        kit.aim(cam, tgt + Vector((math.sin(a) * 3.6, -math.cos(a) * 3.6, 0.35)), tgt)
        sc.render.filepath = os.path.join(outdir, f'{name}.png'); bpy.ops.render.render(write_still=True)
    # face close-ups: front and the drawn three-quarter, then a light sweep at three-quarters
    h = HC + Vector((0, 0, -0.01))
    sc.render.resolution_x, sc.render.resolution_y = 1080, 1080
    cam.data.lens = 85
    for name, az, light in (('face_front', 0, None), ('face', 32, None), ('face_l0', 32, (0.0, -1, 0.35)),
                            ('face_l45', 32, (0.7, -0.7, 0.4)), ('face_l90', 32, (1, 0.0, 0.35)),
                            ('face_r60', 32, (-0.86, -0.5, 0.35)), ('face_back', 32, (0.5, 0.86, 0.3))):
        if light:
            kit.set_light(light)
        a = math.radians(az)
        kit.aim(cam, h + Vector((math.sin(a) * 1.1, -math.cos(a) * 1.1, 0.02)), h)
        sc.render.filepath = os.path.join(outdir, f'{name}.png'); bpy.ops.render.render(write_still=True)
    kit.set_light(kit.LDIR)
    for s_ in 'RL':
        w, al, pa, ac = hand_frame(s_)
        c = w + al * 0.06
        kit.aim(cam, c + Vector((0.0, -0.28, 0.06)) - pa * 0.28, c)
        sc.render.filepath = os.path.join(outdir, f'hand_{s_}.png'); bpy.ops.render.render(write_still=True)


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    C = build()
    if '--views' in argv:
        render_views(argv[argv.index('--views') + 1])
    if '--blend' in argv:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(argv[argv.index('--blend') + 1]))
