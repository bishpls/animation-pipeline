"""Environment kit: sky, moon/eclipse, snowfield, cel pines, wolves, King."""
import bpy, bmesh, math, random, sys, os
from mathutils import Vector, Matrix, Quaternion
import char as CH
from char import toon, flat, add_outline, mesh_from_bm, link, lin
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'b3d'))


def sky(top=(0.02, 0.02, 0.06), mid=(0.07, 0.08, 0.2), horizon=(0.22, 0.26, 0.46), stars=0.8):
    w = bpy.data.worlds.new('sky'); bpy.context.scene.world = w; w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputWorld'); bg = nt.nodes.new('ShaderNodeBackground')
    tc = nt.nodes.new('ShaderNodeTexCoord'); sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    ramp = nt.nodes.new('ShaderNodeValToRGB'); cr = ramp.color_ramp
    cr.elements[0].position = 0.0; cr.elements[0].color = (*lin(horizon), 1)
    cr.elements[1].position = 0.55; cr.elements[1].color = (*lin(top), 1)
    e = cr.elements.new(0.12); e.color = (*lin(mid), 1)
    nt.links.new(sep.outputs['Z'], ramp.inputs[0])
    # stars: sparse voronoi points
    vo = nt.nodes.new('ShaderNodeTexVoronoi'); vo.inputs['Scale'].default_value = 180
    nt.links.new(tc.outputs['Generated'], vo.inputs['Vector'])
    st = nt.nodes.new('ShaderNodeMapRange'); st.inputs['From Min'].default_value = 0.035; st.inputs['From Max'].default_value = 0.0
    st.inputs['To Max'].default_value = stars
    nt.links.new(vo.outputs['Distance'], st.inputs['Value'])
    ad = nt.nodes.new('ShaderNodeMix'); ad.data_type = 'RGBA'; ad.blend_type = 'ADD'
    nt.links.new(st.outputs['Result'], ad.inputs['Factor']); ad.inputs['B'].default_value = (0.9, 0.92, 1, 1)
    nt.links.new(ramp.outputs['Color'], ad.inputs['A'])
    nt.links.new(ad.outputs['Result'], bg.inputs['Color'])
    nt.links.new(bg.outputs[0], out.inputs['Surface'])
    return w


def moon_mat(name, color, strength, R):
    """emissive moon surface; the eclipse is a masked disk inside the shader (invisible against the sky, like the real one),
    with a thin cyan terminator.  Returns (material, value-node) — the value is the occluder centre x in object units."""
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    N = nt.nodes.new; Lk = nt.links.new
    out = N('ShaderNodeOutputMaterial'); em = N('ShaderNodeEmission'); em.inputs['Strength'].default_value = strength
    tc = N('ShaderNodeTexCoord'); val = N('ShaderNodeValue'); val.outputs[0].default_value = R * 2.1
    cx = N('ShaderNodeCombineXYZ'); Lk(val.outputs[0], cx.inputs['X'])
    sub = N('ShaderNodeVectorMath'); sub.operation = 'SUBTRACT'; Lk(tc.outputs['Object'], sub.inputs[0]); Lk(cx.outputs[0], sub.inputs[1])
    ln = N('ShaderNodeVectorMath'); ln.operation = 'LENGTH'; Lk(sub.outputs[0], ln.inputs[0])
    inside = N('ShaderNodeMath'); inside.operation = 'LESS_THAN'; Lk(ln.outputs['Value'], inside.inputs[0]); inside.inputs[1].default_value = R * 1.02
    rim = N('ShaderNodeMath'); rim.operation = 'COMPARE'; Lk(ln.outputs['Value'], rim.inputs[0]); rim.inputs[1].default_value = R * 1.02; rim.inputs[2].default_value = R * 0.022
    c1 = N('ShaderNodeMix'); c1.data_type = 'RGBA'; Lk(inside.outputs[0], c1.inputs['Factor'])
    c1.inputs['A'].default_value = (*lin(color), 1); c1.inputs['B'].default_value = (*lin((0.02, 0.018, 0.05)), 1)
    c2 = N('ShaderNodeMix'); c2.data_type = 'RGBA'; Lk(rim.outputs[0], c2.inputs['Factor'])
    Lk(c1.outputs['Result'], c2.inputs['A']); c2.inputs['B'].default_value = (*lin((0.45, 0.95, 1.0)), 1)
    Lk(c2.outputs['Result'], em.inputs['Color']); Lk(em.outputs[0], out.inputs['Surface'])
    return m, val


def moon(pos, radius, bite=0.0, ring=0.0, cam=None, name='moon'):
    """Emissive moon disk whose shader carries the eclipse (see moon_mat) + a bright corona ring. Billboards to the camera."""
    mm, v1 = moon_mat(name + 'mat', (0.93, 0.97, 1.0), 1.0, radius)
    bm = bmesh.new(); bmesh.ops.create_circle(bm, cap_ends=True, segments=96, radius=radius)
    m = mesh_from_bm(name, bm, [mm], smooth=False)
    m.location = pos
    bm = bmesh.new()
    rnd = random.Random(3)
    # maria: irregular blobs (clusters of overlapping ellipses), low contrast
    for cl in range(5):
        a = rnd.uniform(0, 6.28); r = radius * rnd.uniform(0.1, 0.62)
        cx, cy = math.cos(a) * r, math.sin(a) * r
        for j in range(5):
            rr = radius * rnd.uniform(0.07, 0.17)
            ox, oy = cx + rnd.uniform(-1, 1) * radius * 0.13, cy + rnd.uniform(-1, 1) * radius * 0.13
            if math.hypot(ox, oy) + rr > radius * 0.95: continue
            bmesh.ops.create_circle(bm, cap_ends=True, segments=20, radius=rr,
                                    matrix=Matrix.Translation((ox, oy, 0.01 * radius)) @ Matrix.Diagonal((rnd.uniform(0.7, 1.4), 1, 1, 1)))
    ma, v2 = moon_mat(name + 'maria', (0.74, 0.8, 0.92), 1.0, radius)
    mar = mesh_from_bm(name + '_maria', bm, [ma], smooth=False); mar.parent = m
    ring_bm = bmesh.new()                       # corona: an annulus (real faces) hugging the limb
    N = 160; inner, outer = [], []
    for i in range(N):
        a = i / N * 6.28318
        inner.append(ring_bm.verts.new((math.cos(a) * radius * 1.0, math.sin(a) * radius * 1.0, -0.005 * radius)))
        outer.append(ring_bm.verts.new((math.cos(a) * radius * 1.055, math.sin(a) * radius * 1.055, -0.005 * radius)))
    for i in range(N):
        j = (i + 1) % N
        ring_bm.faces.new((inner[i], outer[i], outer[j], inner[j]))
    ringo = mesh_from_bm(name + '_ring', ring_bm, [flat('ringmat', (1.0, 0.95, 0.85), 3.0)], smooth=False)
    ringo.parent = m
    if cam:
        c = m.constraints.new('TRACK_TO'); c.target = cam; c.track_axis = 'TRACK_Z'; c.up_axis = 'UP_Y'
    def set_state(bite_, ring_, frame=None):
        x = 0.0 if ring_ > 0 else radius * 2.1 * (1 - bite_)
        for v in (v1, v2):
            v.outputs[0].default_value = x
            if frame is not None:
                v.outputs[0].keyframe_insert('default_value', frame=frame)
        ringo.hide_render = ring_ <= 0
        if frame is not None:
            ringo.keyframe_insert('hide_render', frame=frame)
    set_state(bite, ring)
    return m, set_state


def snowfield(size=300, center=(0, 0), flat_r=12):
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=160 if size <= 300 else 240, y_segments=160 if size <= 300 else 240, size=size / 2)
    rnd = random.Random(2)
    ph = [rnd.uniform(0, 6.28) for _ in range(4)]
    for v in bm.verts:
        x, y = v.co.x + center[0], v.co.y + center[1]
        d = math.hypot(x, y)
        a = min(1.0, max(0.0, (d - flat_r) / 30))
        v.co.z = a * (1.2 * math.sin(x * 0.05 + ph[0]) * math.cos(y * 0.045 + ph[1]) + 0.5 * math.sin(x * 0.13 + y * 0.09 + ph[2]))
    mat = toon('snowmat', (0.86, 0.88, 1.0), (0.55, 0.58, 0.85), rim_amt=0.0, thresh=0.5)
    forest_shade(mat, center)
    ob = mesh_from_bm('snow', bm, [mat])
    return ob


FOREST_SHADE = dict(col=(0.3, 0.32, 0.55), r0=11.0, r1=19.0)


def forest_shade(mat, center=(0, 0)):
    """moonlit clearing, shadowed forest floor: repurpose the snow's 'warm' multiply as a radial shade"""
    nt = mat.node_tree
    warm = [n for n in nt.nodes if n.type == 'MIX' and n.blend_type == 'MULTIPLY'][0]
    for l in list(warm.inputs['Factor'].links): nt.links.remove(l)
    geo = nt.nodes.new('ShaderNodeNewGeometry'); sep = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(geo.outputs['Position'], sep.inputs[0])
    cmb = nt.nodes.new('ShaderNodeCombineXYZ')
    sx = nt.nodes.new('ShaderNodeMath'); sx.operation = 'SUBTRACT'; nt.links.new(sep.outputs['X'], sx.inputs[0]); sx.inputs[1].default_value = center[0]
    sy = nt.nodes.new('ShaderNodeMath'); sy.operation = 'SUBTRACT'; nt.links.new(sep.outputs['Y'], sy.inputs[0]); sy.inputs[1].default_value = center[1]
    nt.links.new(sx.outputs[0], cmb.inputs['X']); nt.links.new(sy.outputs[0], cmb.inputs['Y'])
    ln = nt.nodes.new('ShaderNodeVectorMath'); ln.operation = 'LENGTH'; nt.links.new(cmb.outputs[0], ln.inputs[0])
    mr = nt.nodes.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = FOREST_SHADE['r0']; mr.inputs['From Max'].default_value = FOREST_SHADE['r1']
    mr.interpolation_type = 'SMOOTHSTEP'
    nt.links.new(ln.outputs['Value'], mr.inputs['Value']); nt.links.new(mr.outputs['Result'], warm.inputs['Factor'])
    warm.inputs['B'].default_value = (*lin(FOREST_SHADE['col']), 1)


def pine_mesh(name, rnd, h):
    bm = bmesh.new()
    tiers = rnd.randint(5, 7)
    trunkM, needM, capM = 0, 1, 2
    bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=h * 0.03, radius2=h * 0.02, depth=h * 0.3, matrix=Matrix.Translation((0, 0, h * 0.15)))
    for f in bm.faces: f.material_index = trunkM
    for k in range(tiers):
        u = k / tiers
        z0 = h * (0.18 + 0.72 * u)
        r = h * (0.3 - 0.24 * u) * rnd.uniform(0.9, 1.1)
        hh = h * 0.26
        new = bmesh.ops.create_cone(bm, cap_ends=True, segments=9, radius1=r, radius2=0.0, depth=hh, matrix=Matrix.Translation((0, 0, z0 + hh / 2)))
        for v in new['verts']:
            if v.co.z < z0 + 0.01 and (len(v.link_edges) > 0):
                ang = math.atan2(v.co.y, v.co.x)
                v.co.z -= h * 0.03 * (1 + math.sin(ang * 4.5))       # drooping tips
        for f in {f for v in new['verts'] for f in v.link_faces}:
            c = f.calc_center_median()
            f.material_index = capM if (c.z > z0 + hh * 0.45 and f.normal.z > 0.3) else needM
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for mat in (toon('bark', (0.12, 0.10, 0.16), (0.06, 0.05, 0.09), rim_amt=0.2),
                toon('needles', (0.16, 0.21, 0.42), (0.07, 0.09, 0.22), rim=(0.5, 0.7, 1.0), rim_amt=0.25, thresh=0.5),
                toon('needlesnow', (0.86, 0.9, 1.0), (0.5, 0.55, 0.82), rim_amt=0.0, thresh=0.45)):
        me.materials.append(mat)
    return me


def forest(n=260, rmin=11, rmax=85, seed=4, avoid=(), outline_near=18, center=(0, 0)):
    rnd = random.Random(seed)
    variants = [pine_mesh(f'pine{i}', rnd, 1.0) for i in range(6)]
    coll = bpy.data.collections.new('forest'); bpy.context.scene.collection.children.link(coll)
    placed = 0; tries = 0
    obs = []
    while placed < n and tries < n * 30:
        tries += 1
        r = rmin + (rmax - rmin) * math.sqrt(rnd.random()); a = rnd.uniform(0, 6.28)
        x, y = center[0] + math.cos(a) * r, center[1] + math.sin(a) * r
        if any((x - ax) ** 2 + (y - ay) ** 2 < ar ** 2 for ax, ay, ar in avoid):
            continue
        me = rnd.choice(variants)
        ob = bpy.data.objects.new(f'pine_{placed}', me)
        h = rnd.uniform(7, 14)
        ob.location = (x, y, -0.3); ob.scale = (h, h, h * rnd.uniform(0.95, 1.15)); ob.rotation_euler = (0, 0, rnd.uniform(0, 6.28))
        coll.objects.link(ob)
        obs.append(ob)
        placed += 1
    return obs


# ---------------------------------------------------------------- wolves (EMBER II gait rig, restyled cel-black)
WOLF_RIM = 0.9          # per-shot: lower it to sink the pack into the dark


def wolf_materials():
    wm = toon('wolfmat', (0.06, 0.06, 0.1), (0.015, 0.015, 0.03), rim=(0.35, 0.95, 1.0), rim_amt=WOLF_RIM, thresh=0.55)
    em = flat('wolfeye', (0.6, 0.97, 1.0), 6.0)
    return wm, em


def build_wolf(name, s=1.1, seed=0):
    """Void wolf v5: hunched shoulders, deep chest, tucked waist, big wedge head with a real jaw, heavy forelegs,
    a mane of swept shards, a flame-like tail.  Same part frames as b3d/kin.Wolf.transforms()."""
    import blib, bmesh, random
    from mathutils import Matrix
    from blib import bm_loft_y, bm_cone, bm_capsule
    rnd = random.Random(seed)
    wm, em = wolf_materials()
    parts = {}
    SP = {}
    def sp(k):
        if k not in SP: SP[k] = bmesh.new()
        return SP[k]
    def mk(k, bm, mat=wm, sub=True):
        me = bpy.data.meshes.new(f'{name}_{k}'); bm.to_mesh(me); bm.free()
        for pl in me.polygons: pl.use_smooth = True
        ob = bpy.data.objects.new(f'{name}_{k}', me); bpy.context.scene.collection.objects.link(ob)
        me.materials.append(mat)
        if sub:
            m = ob.modifiers.new('sub', 'SUBSURF'); m.levels = m.render_levels = 1
        ob.visible_shadow = False; ob.rotation_mode = 'QUATERNION'; ob.scale = (s, s, s)
        parts[k] = ob
    L = lambda rings: [(y, rx, rz, cx, -cz) for (y, rx, rz, cx, cz) in rings]   # blib loft: +cz means down
    # ---- body
    bm = bmesh.new()
    bm_loft_y(bm, L([(-0.64, 0.05, 0.05, 0, 0.08), (-0.54, 0.13, 0.14, 0, 0.05), (-0.40, 0.16, 0.18, 0, 0.04),
                     (-0.18, 0.11, 0.13, 0, 0.06), (0.06, 0.15, 0.2, 0, 0.0), (0.30, 0.18, 0.26, 0, 0.04),
                     (0.48, 0.14, 0.19, 0, 0.13), (0.62, 0.10, 0.12, 0, 0.21), (0.72, 0.08, 0.09, 0, 0.24)]), n=18)
    for (x, y, z, r, sx, sy, sz) in [(0.12, 0.38, -0.05, 0.15, 0.75, 1.1, 1.35), (-0.12, 0.38, -0.05, 0.15, 0.75, 1.1, 1.35),
                                     (0.12, -0.44, -0.02, 0.15, 0.7, 1.3, 1.2), (-0.12, -0.44, -0.02, 0.15, 0.7, 1.3, 1.2)]:
        bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=r, matrix=Matrix.Translation((x, y, z)) @ Matrix.Diagonal((sx, sy, sz, 1)))
    # mane: big shards on neck + shoulders fanning back and out, smaller down the spine
    for i in range(46):
        u = i / 45
        y = 0.7 - 1.25 * u
        top = 0.3 if y > 0.2 else 0.22 + 0.1 * max(0, y + 0.1)
        zc = top + (0.04 if y > 0.45 else 0)
        big = max(0.0, 1 - abs(y - 0.42) / 0.45)
        h = (0.07 + 0.3 * big ** 1.3) * rnd.uniform(0.7, 1.25)
        x = rnd.uniform(-0.12, 0.12) * (0.5 + big)
        M = (Matrix.Translation((x, y, zc - 0.03)) @ Matrix.Rotation(-1.15 + rnd.uniform(-0.25, 0.2), 4, 'X') @
             Matrix.Rotation(x * 4.5, 4, 'Y'))
        bm_cone(sp('body'), 0.03 + 0.02 * big, h, M, seg=4)
    mk('body', bm)
    # ---- head (origin at skull base, +Y forward)
    bm = bmesh.new()
    bm_loft_y(bm, L([(-0.10, 0.10, 0.11, 0, 0.01), (0.02, 0.14, 0.135, 0, 0.03), (0.13, 0.12, 0.11, 0, 0.01),
                     (0.25, 0.075, 0.07, 0, -0.03), (0.36, 0.052, 0.048, 0, -0.045), (0.43, 0.03, 0.03, 0, -0.05),
                     (0.46, 0.01, 0.012, 0, -0.052)]), n=14)
    for sd in (-1, 1):
        bm_cone(sp('head'), 0.06, 0.26, Matrix.Translation((sd * 0.07, -0.02, 0.08)) @ Matrix.Rotation(-1.05, 4, 'X') @ Matrix.Rotation(sd * 0.35, 4, 'Y'), seg=4)   # ears
        bm_cone(sp('head'), 0.03, 0.16, Matrix.Translation((sd * 0.12, 0.02, -0.02)) @ Matrix.Rotation(-1.4, 4, 'X') @ Matrix.Rotation(sd * 0.9, 4, 'Y'), seg=4)   # cheek spikes
        bm_cone(sp('head'), 0.025, 0.1, Matrix.Translation((sd * 0.06, 0.16, 0.06)) @ Matrix.Rotation(-1.2, 4, 'X') @ Matrix.Rotation(sd * 0.3, 4, 'Y'), seg=4)  # brow
        for i in range(4):                                         # upper fangs
            bm_cone(sp('head'), 0.012, 0.05 + (0.03 if i == 0 else 0), Matrix.Translation((sd * (0.045 - i * 0.007), 0.34 - i * 0.06, -0.07)) @ Matrix.Rotation(math.pi, 4, 'X'), seg=3)
    mk('head', bm)
    bm = bmesh.new()
    bm_loft_y(bm, L([(-0.02, 0.09, 0.04, 0, -0.08), (0.18, 0.065, 0.032, 0, -0.1), (0.3, 0.04, 0.022, 0, -0.1), (0.38, 0.02, 0.015, 0, -0.095)]), n=10)
    for sd in (-1, 1):
        for i in range(4):
            bm_cone(sp('jaw'), 0.011, 0.045 + (0.02 if i == 0 else 0), Matrix.Translation((sd * (0.04 - i * 0.006), 0.3 - i * 0.06, -0.08)), seg=3)
    mk('jaw', bm)
    bm = bmesh.new()
    for sd in (-1, 1):
        bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=6, radius=0.03,
                                  matrix=Matrix.Translation((sd * 0.09, 0.15, 0.045)) @ Matrix.Rotation(sd * 0.45, 4, 'Z') @ Matrix.Rotation(sd * -0.25, 4, 'Y') @ Matrix.Diagonal((0.55, 1.9, 0.42, 1)))
    mk('eyes', bm, em, sub=False)
    # ---- legs: heavy tapered upper, thin lower, big clawed paw
    for k in ('fr', 'fl', 'hr', 'hl'):
        hind = k[0] == 'h'
        bm = bmesh.new()
        bm_capsule(bm, 0.12 if hind else 0.105, 0.05, 0.36, seg=10)
        mk('up_' + k, bm)
        bm = bmesh.new()
        bm_capsule(bm, 0.05, 0.034, 0.40, seg=8)
        P = Matrix.Translation((0, 0, 0.40)) @ Matrix.Rotation(-1.35, 4, 'X')
        bm_capsule(bm, 0.055, 0.04, 0.12, seg=8, M=P)
        for cx in (-0.03, 0, 0.03):
            bm_cone(sp('lo_' + k), 0.012, 0.07, P @ Matrix.Translation((cx, 0, 0.12)) @ Matrix.Rotation(0.5, 4, 'X'), seg=3)
        mk('lo_' + k, bm)
    # ---- tail: a tongue of ink shards
    bm = bmesh.new()
    bm_loft_y(bm, L([(0.0, 0.06, 0.06, 0, 0), (-0.22, 0.09, 0.08, 0, -0.04), (-0.48, 0.07, 0.06, 0, -0.06), (-0.72, 0.01, 0.01, 0, -0.02)]), n=8)
    for i in range(14):
        y = -0.05 - 0.05 * i
        bm_cone(sp('tail'), 0.03, 0.08 + 0.1 * math.sin(math.pi * i / 13), Matrix.Translation((rnd.uniform(-0.05, 0.05), y, 0.02)) @
                Matrix.Rotation(-1.9 + rnd.uniform(-0.4, 0.4), 4, 'X') @ Matrix.Rotation(rnd.uniform(-0.8, 0.8), 4, 'Y'), seg=3)
    mk('tail', bm)
    for k, b in SP.items():
        mk(k + '_sp', b, sub=False)
    return parts


def pose_wolf(parts, state, frame=None):
    X = state.transforms()
    for k, ob in parts.items():
        kk = k[:-3] if k.endswith('_sp') else k
        loc, q = X[kk] if kk in X else X['body']
        ob.location = Vector(loc); ob.rotation_mode = 'QUATERNION'; ob.rotation_quaternion = Quaternion(q)
        if frame is not None:
            ob.keyframe_insert('location', frame=frame); ob.keyframe_insert('rotation_quaternion', frame=frame)


def set_visible(parts, vis, frame):
    for ob in parts.values():
        ob.hide_render = not vis
        ob.keyframe_insert('hide_render', frame=frame)


def build_king(name='king', s=45.0):
    """The Hollow King: a colossal void wolf with a crown of long shards and a mane like a burning hedge."""
    import bmesh, random
    from mathutils import Matrix
    from blib import bm_cone
    parts = build_wolf(name, s, seed=99)
    wm, em = wolf_materials()
    rnd = random.Random(7)
    bm = bmesh.new()
    for i in range(15):                      # crown: long shards fanning up and back from the skull
        a = -1.0 + 2.0 * i / 14
        L = 0.35 + 0.35 * (1 - abs(a)) + rnd.uniform(-0.05, 0.08)
        M = (Matrix.Translation((a * 0.11, -0.02 - 0.03 * abs(a), 0.1)) @ Matrix.Rotation(-0.45 - 0.35 * abs(a), 4, 'X') @
             Matrix.Rotation(a * 0.9, 4, 'Y'))
        bm_cone(bm, 0.035, L, M, seg=4)
    me = bpy.data.meshes.new(name + '_crown'); bm.to_mesh(me); bm.free()
    crown = bpy.data.objects.new(name + '_crown', me); bpy.context.scene.collection.objects.link(crown)
    me.materials.append(wm); crown.visible_shadow = False
    crown.parent = parts['head']
    parts_extra = {'crown': crown}
    return parts, parts_extra


def half_mat(src, sign, name):
    """copy of a toon/flat material that keeps only object-space x*sign >= 0 (for splitting the King down the middle)"""
    m = src.copy(); m.name = name
    nt = m.node_tree
    out = [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'][0]
    sh = out.inputs['Surface'].links[0].from_socket
    tc = nt.nodes.new('ShaderNodeTexCoord'); sep = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(tc.outputs['Object'], sep.inputs[0])
    mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; nt.links.new(sep.outputs['X'], mul.inputs[0]); mul.inputs[1].default_value = sign
    gt = nt.nodes.new('ShaderNodeMath'); gt.operation = 'GREATER_THAN'; nt.links.new(mul.outputs[0], gt.inputs[0]); gt.inputs[1].default_value = 0.0
    tr = nt.nodes.new('ShaderNodeBsdfTransparent'); mx = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(gt.outputs[0], mx.inputs['Fac']); nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(sh, mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs['Surface'])
    try:
        m.surface_render_method = 'DITHERED'
    except Exception:
        pass
    return m


def build_king_half(name, s, sign):
    """one half of the King: split parts masked by object-space x; limbs/eyes of the other side hidden"""
    parts, extra = build_king(name, s)
    side_keep = 'r' if sign > 0 else 'l'          # kin: 'fr'/'hr' are the wolf's right (+x in its body frame)
    cache = {}
    for k, ob in list(parts.items()) + list(extra.items()):
        base = k.replace('_sp', '')
        if base.startswith(('up_', 'lo_')):
            ob.hide_render = base[-1] != side_keep
            continue
        for i, mat in enumerate(ob.data.materials):
            key = mat.name
            if key not in cache:
                cache[key] = half_mat(mat, sign, f'{key}_{name}')
            ob.data.materials[i] = cache[key]
    return parts, extra
