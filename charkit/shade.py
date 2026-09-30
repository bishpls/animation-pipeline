"""charkit's cel shading (docs/CHARKIT.md §2, materials): three-tone toon on an art-directed light (emission, so the look is the
shader's, not the lights'), flat colours, alpha-textured plates (the eyes), and inverted-hull outlines. Blender-side; the
VRM export maps these onto MToon.

The style profile's `look` (charkit.styles) says how a view is lit and lined: set_look() keeps it (and stores it in the
scene, so a saved .blend's turntable renders it the same way), set_view() applies it for one camera: the light ('world':
fixed; 'camera': a key that turns with the camera) into every material's 'ldir' and 'ldir_head' node, and the outlines'
widths ('screen': the same share of the picture in every view; a thin shell's inward move capped at half its thickness,
and a closed thin piece's (the bow, the boots) at half its measured thickness, the rest of the width outward: outline()).
charkit.qa.render_view calls set_view for each shot.
"""
import json, math

import numpy as np

LDIR = np.array([-0.45, -0.55, 0.70])        # toward the key light (front-left-above), world
LDIR = LDIR / np.linalg.norm(LDIR)
MATS = {}
LOOK = {}                                    # the style profile's look (set_look); {} = the world light, build widths


def lin(c):
    c = np.asarray(c, float)
    return tuple(np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4))


def _new(name):
    import bpy
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    return m, nt


def toon3(name, lit, shade, deep, thresh=0.5, deep_thresh=0.27, soft=0.015, rim=(1.0, 0.95, 0.92), rim_amt=0.16):
    """three tones on half-lambert N.L (deep | shade | lit) with hard steps and a lit-side rim, as emission."""
    if name in MATS:
        return MATS[name]
    m, nt = _new(name)
    N, L = nt.nodes.new, nt.links.new
    out = N('ShaderNodeOutputMaterial'); geo = N('ShaderNodeNewGeometry')
    ld = N('ShaderNodeCombineXYZ'); ld.name = 'ldir'
    for i in range(3):
        ld.inputs[i].default_value = float(LDIR[i])
    dot = N('ShaderNodeVectorMath'); dot.operation = 'DOT_PRODUCT'
    L(geo.outputs['Normal'], dot.inputs[0]); L(ld.outputs[0], dot.inputs[1])
    half = N('ShaderNodeMath'); half.operation = 'MULTIPLY_ADD'; half.inputs[1].default_value = 0.5
    half.inputs[2].default_value = 0.5
    L(dot.outputs['Value'], half.inputs[0])

    def step(at):
        r = N('ShaderNodeValToRGB')
        e0, e1 = r.color_ramp.elements
        e0.position, e1.position = at - soft, at + soft
        e0.color, e1.color = (0, 0, 0, 1), (1, 1, 1, 1)
        L(half.outputs[0], r.inputs[0])
        return r
    s_lit, s_deep = step(thresh), step(deep_thresh)
    m1 = N('ShaderNodeMix'); m1.data_type = 'RGBA'
    m1.inputs['A'].default_value = (*lin(deep), 1); m1.inputs['B'].default_value = (*lin(shade), 1)
    L(s_deep.outputs['Color'], m1.inputs['Factor'])
    m2 = N('ShaderNodeMix'); m2.data_type = 'RGBA'; m2.inputs['B'].default_value = (*lin(lit), 1)
    L(m1.outputs['Result'], m2.inputs['A']); L(s_lit.outputs['Color'], m2.inputs['Factor'])
    lw = N('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.3
    rr = N('ShaderNodeMapRange'); rr.inputs['From Min'].default_value = 0.64; rr.inputs['From Max'].default_value = 0.68
    L(lw.outputs['Facing'], rr.inputs['Value'])
    lm = N('ShaderNodeMath'); lm.operation = 'MULTIPLY'; lm.inputs[1].default_value = rim_amt
    L(rr.outputs['Result'], lm.inputs[0])
    lm2 = N('ShaderNodeMath'); lm2.operation = 'MULTIPLY'
    L(lm.outputs[0], lm2.inputs[0]); L(s_lit.outputs['Color'], lm2.inputs[1])
    rim_mix = N('ShaderNodeMix'); rim_mix.data_type = 'RGBA'; rim_mix.blend_type = 'SCREEN'
    rim_mix.inputs['B'].default_value = (*lin(rim), 1)
    L(lm2.outputs[0], rim_mix.inputs['Factor']); L(m2.outputs['Result'], rim_mix.inputs['A'])
    em = N('ShaderNodeEmission'); L(rim_mix.outputs['Result'], em.inputs['Color']); L(em.outputs[0], out.inputs['Surface'])
    MATS[name] = m
    return m


def hair_toon(name, lit, shade, deep, centre, hl=None, inner=0.0, rim_amt=0.0):
    """toon3 for the cut hair pieces (the look's hair section `hl`): its deep step at hl['deep_at'] (lower: the deep
    tone only where the hair turns right away from the light), an under layer's lit tone moved `inner` of the way to its
    shade (the layers under others a step darker, as drawn), and the drawn highlight: short streaks along the hair on
    the crown's lit side, as the design draws them. Round the head centre the hair is cut into `count` columns of azimuth;
    an integer hash of each column's index (streak_hash: Blender's White Noise, Jenkins' lookup3 on the index's float
    bits, the same on every GPU) keeps a share `keep` of them and shifts its streak's elevation by up to `jitter`
    degrees about `elevation`; a streak is `length` degrees of elevation long and `duty` of its column wide, tapered at
    both ends, and fades where the surface turns from the camera. Its parameters ride on the material ('ck_highlight',
    JSON, with hash 'lookup3') for the bundle and the export."""
    if name in MATS:
        return MATS[name]
    hl = dict(hl or {})
    lit_ = tuple(np.asarray(lit, float) * (1 - inner) + np.asarray(shade, float) * inner)
    m = toon3(name, lit_, shade, deep, deep_thresh=hl.get('deep_at', 0.27), rim_amt=rim_amt)
    if hl.get('highlight') != 'streaks':
        return m
    nt = m.node_tree; N, Lk = nt.nodes.new, nt.links.new
    em = next(n for n in nt.nodes if n.type == 'EMISSION')
    src = em.inputs['Color'].links[0].from_socket
    s_lit = next(n for n in nt.nodes if n.type == 'VALTORGB' and abs(n.color_ramp.elements[0].position - (0.5 - 0.015)) < 1e-6)
    P = dict(centre=[float(x) for x in centre], elevation=float(hl.get('elevation', 40.0)),
             length=float(hl.get('length', 9.0)), jitter=float(hl.get('jitter', 8.0)), count=int(hl.get('count', 40)),
             duty=float(hl.get('duty', 0.35)), keep=float(hl.get('keep', 0.5)), amount=float(hl.get('amount', 0.8)),
             color=[float(x) for x in hl.get('color', (1.0, 0.86, 0.74))], facing=[0.55, 0.25], hash='lookup3')

    def op(o, a=None, b=None, name=None):
        n = N('ShaderNodeMath'); n.operation = o
        for i, x in enumerate((a, b)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                n.inputs[i].default_value = float(x)
            else:
                Lk(x, n.inputs[i])
        if name:
            n.name = name
        return n.outputs[0]
    geo = N('ShaderNodeNewGeometry')
    rel = N('ShaderNodeVectorMath'); rel.operation = 'SUBTRACT'; rel.name = 'ck_hl_centre'
    rel.inputs[1].default_value = tuple(P['centre'])
    Lk(geo.outputs['Position'], rel.inputs[0])
    sp = N('ShaderNodeSeparateXYZ'); Lk(rel.outputs[0], sp.inputs[0])
    hx = N('ShaderNodeCombineXYZ'); Lk(sp.outputs['X'], hx.inputs[0]); Lk(sp.outputs['Y'], hx.inputs[1])
    hlen = N('ShaderNodeVectorMath'); hlen.operation = 'LENGTH'; Lk(hx.outputs[0], hlen.inputs[0])
    el = op('ARCTAN2', sp.outputs['Z'], hlen.outputs['Value'])
    az = op('ARCTAN2', sp.outputs['X'], op('MULTIPLY', sp.outputs['Y'], -1.0))       # 0 in front, + to her left
    col = op('MULTIPLY', op('ADD', az, math.pi), P['count'] / (2 * math.pi))           # the column coordinate
    idx = op('FLOOR', col)
    # the column's hashes (streak_hash): White Noise 1D is an integer hash of W's bits (uint arithmetic, exact on every
    # GPU): Value = hash_uint(bits(idx)) keeps the column, Color's green = hash_uint2(bits(idx), bits(1.0)) its elevation
    wn = N('ShaderNodeTexWhiteNoise'); wn.noise_dimensions = '1D'; wn.name = 'ck_hl_hash'
    Lk(idx, wn.inputs['W'])
    sep = N('ShaderNodeSeparateColor'); sep.mode = 'RGB'
    Lk(wn.outputs['Color'], sep.inputs['Color'])
    keep = op('LESS_THAN', wn.outputs['Value'], P['keep'], name='ck_hl_keep')
    el0 = op('ADD', math.radians(P['elevation'] - P['jitter']), op('MULTIPLY', sep.outputs['Green'], math.radians(2 * P['jitter'])))
    # along: 1 at the streak's middle elevation, 0 at +-length/2; across: 1 at the column's middle, 0 at +-duty/2
    along = op('SUBTRACT', 1.0, op('DIVIDE', op('ABSOLUTE', op('SUBTRACT', el, el0)), math.radians(P['length'] / 2)))
    across = op('SUBTRACT', 1.0, op('DIVIDE', op('ABSOLUTE', op('SUBTRACT', op('FRACT', col), 0.5)), P['duty'] / 2))
    sat = lambda x: op('MAXIMUM', op('MINIMUM', op('MULTIPLY', x, 3.0), 1.0), 0.0)     # each clamped before the product:
    shape = op('MULTIPLY', sat(along), sat(across))                                  # outside both is not inside
    lw = N('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.5
    fc = N('ShaderNodeMapRange'); fc.inputs['From Min'].default_value = 0.55; fc.inputs['From Max'].default_value = 0.25
    Lk(lw.outputs['Facing'], fc.inputs['Value'])
    f = op('MULTIPLY', op('MULTIPLY', shape, keep), fc.outputs['Result'])
    f = op('MULTIPLY', op('MULTIPLY', f, s_lit.outputs['Color']), P['amount'], name='ck_hl_amount')
    mx = N('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.name = 'ck_highlight'
    mx.inputs['B'].default_value = (*lin(P['color']), 1)
    Lk(f, mx.inputs['Factor']); Lk(src, mx.inputs['A'])
    Lk(mx.outputs['Result'], em.inputs['Color'])
    m['ck_highlight'] = json.dumps(P)
    return m


# the streaks' hash: Bob Jenkins' lookup3 (hash_uint / hash_uint2 and their `final` mix), as Blender's White Noise node
# computes it in EEVEE (gpu_shader_common_hash.glsl) and Cycles (util/hash.h): unsigned 32-bit arithmetic, so every GPU,
# charkit.render's toon.wgsl and look.js get the same bits. The float the node outputs is float(h) / float(0xFFFFFFFF),
# i.e. h rounded to float32 over 2^32.
_U32 = np.uint32


def _rot(x, k):
    return (x << _U32(k)) | (x >> _U32(32 - k))


def _final(a, b, c):
    c ^= b; c -= _rot(b, 14)
    a ^= c; a -= _rot(c, 11)
    b ^= a; b -= _rot(a, 25)
    c ^= b; c -= _rot(b, 16)
    a ^= c; a -= _rot(c, 4)
    b ^= a; b -= _rot(a, 14)
    c ^= b; c -= _rot(b, 24)
    return c


def hash_uint(kx):
    """lookup3's one-word hash of uint32s (array) -> uint32s."""
    kx = np.atleast_1d(np.asarray(kx, _U32))
    with np.errstate(over='ignore'):
        a = np.full(kx.shape, 0xdeadbeef + (1 << 2) + 13, _U32); b = a.copy(); c = a.copy()
        a += kx
        return _final(a, b, c)


def hash_uint2(kx, ky):
    kx, ky = np.broadcast_arrays(np.atleast_1d(np.asarray(kx, _U32)), np.atleast_1d(np.asarray(ky, _U32)))
    with np.errstate(over='ignore'):
        a = np.full(kx.shape, 0xdeadbeef + (2 << 2) + 13, _U32); b = a.copy(); c = a.copy()
        b += ky
        a += kx
        return _final(a, b, c)


def _unit(h):
    return (h.astype(np.float32) / np.float32(4294967296.0)).astype(np.float32)


def streak_hash(count):
    """the White Noise node's two hashes for column indices 0..count-1 (their float32 bits): (Value, Color's green),
    each float32 in [0, 1]."""
    bits = np.arange(count, dtype=np.float32).view(_U32)
    return _unit(hash_uint(bits)), _unit(hash_uint2(bits, np.float32(1.0).view(_U32)))


def streak_columns(P):
    """a highlight's per-column table (P: hair_toon's parameters, or the export's `highlight`): kept (0 / 1, float32) and
    the streak's middle elevation (rad, float32), for column indices 0..count-1."""
    h1, h2 = streak_hash(int(P['count']))
    keep = (h1 < np.float32(P['keep'])).astype(np.float32)
    el0 = (math.radians(P['elevation'] - P['jitter']) + h2.astype(np.float64) * math.radians(2 * P['jitter']))
    return keep, el0.astype(np.float32)


def flat(name, color):
    if name in MATS:
        return MATS[name]
    m, nt = _new(name)
    out = nt.nodes.new('ShaderNodeOutputMaterial'); em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (*lin(color), 1)
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    MATS[name] = m
    return m


def plate(name, image, alpha=True):
    """an emission plate from a packed image; alpha-blended (hashed) when the image has coverage."""
    if name in MATS:
        return MATS[name]
    m, nt = _new(name)
    N, L = nt.nodes.new, nt.links.new
    out = N('ShaderNodeOutputMaterial')
    tx = N('ShaderNodeTexImage'); tx.image = image; tx.extension = 'CLIP'; tx.interpolation = 'Cubic'
    uv = N('ShaderNodeUVMap'); uv.uv_map = 'uv'
    L(uv.outputs[0], tx.inputs['Vector'])
    em = N('ShaderNodeEmission'); L(tx.outputs['Color'], em.inputs['Color'])
    if alpha:
        tr = N('ShaderNodeBsdfTransparent'); mx = N('ShaderNodeMixShader')
        L(tx.outputs['Alpha'], mx.inputs['Fac']); L(tr.outputs[0], mx.inputs[1]); L(em.outputs[0], mx.inputs[2])
        L(mx.outputs[0], out.inputs['Surface'])
        try:
            m.surface_render_method = 'DITHERED'           # per-pixel, depth-tested (BLENDED plates sort by object)
        except Exception:
            m.blend_method = 'HASHED'
    else:
        L(em.outputs[0], out.inputs['Surface'])
    MATS[name] = m
    return m


SHELL_CAP = 0.5         # the outline's inward move is at most this share of a thin shell's thickness (Michael's call I)
THICK_PCT = 5           # a closed thin piece's thickness for its cap: this percentile of its vertices' (Michael's call M)
THICK_REACH = 0.05      # m: how far a vertex's inward ray looks for the piece's far side


def outline(ob, thick=0.0012, color=(0.30, 0.20, 0.22), name='line', region=None, cap=None):
    """inverted hull: a flipped, back-face-culled solidify shell in the line colour. The object keeps its build width
    and its region (skin, hair, garment, accessory) for set_view's screen-width lines.

    The SOLIDIFY (negative thickness -w, offset o) moves the surface inward by w (1 + o) / 2 and puts the hull
    w (1 - o) / 2 outside the original surface: a line w wide. A thin shell (a garment's own 'thick' SOLIDIFY, below
    this one) keeps its inward move under line_cap (SHELL_CAP of its thickness; its two layers moving toward each other
    would cross, and Blender's recomputed normals turn by up to 180 degrees there), and the rest of the width goes
    outward (line_offset). cap='measured': a closed thin piece without a shell modifier (the bow, the boots; Michael's
    call M) is capped the same way at SHELL_CAP of its measured thickness (measured_thickness, of the object as it is
    now: its modifiers so far, the outline not yet on). The cap is kept on the object ('ck_line_cap', m; a measured
    piece's thickness in 'ck_line_thick') for set_view and the export."""
    ob['ck_line_w'] = float(thick)
    ob['ck_line_region'] = region or _region(ob, name)
    shell = shell_of(ob)
    if shell > 0:
        ob['ck_line_cap'] = SHELL_CAP * shell
    elif cap == 'measured':
        t = measured_thickness(ob)
        if t:
            ob['ck_line_thick'] = t
            ob['ck_line_cap'] = SHELL_CAP * t
    elif cap is not None:
        raise ValueError('outline: cap is None or \'measured\', not %r' % (cap,))
    m = flat(name, color)
    ob['ck_line_mat'] = m.name                       # its build colour, kept for line_colors('build')
    m.use_fake_user = True
    m.use_backface_culling = True
    ob.data.materials.append(m)
    sol = ob.modifiers.new('outline', 'SOLIDIFY')
    sol.thickness = -thick; sol.offset = line_offset(thick, line_cap(ob)); sol.use_flip_normals = True
    sol.use_rim = False
    sol.material_offset = len(ob.data.materials) - 1
    if 'outline_w' in ob.vertex_groups:
        sol.vertex_group = 'outline_w'; sol.thickness_vertex_group = 0.0
    return sol


def shell_of(ob):
    """a thin shell's thickness (m): the object's own SOLIDIFY that gives it thickness (a garment's 'thick'; not the
    outline, which flips normals), or the shell the venv already made (a final mesh's 'ck_shell', call J), else 0 (a
    closed surface: the skin, the hair pieces, the boots)."""
    return max([abs(float(md.thickness)) for md in ob.modifiers if md.type == 'SOLIDIFY' and not md.use_flip_normals
                and md.name != 'outline'] + [abs(float(ob.get('ck_shell', 0.0)))])


def measured_thickness(ob, pct=THICK_PCT, reach=THICK_REACH):
    """a closed piece's thickness (m), measured as look.md round 3 measured it for call M: per vertex of its evaluated
    mesh (every modifier on but the outline), a ray from the vertex along its inward normal to the same mesh's far side
    (a face that faces along the ray) within `reach`; the `pct` percentile of the hits, to the micrometre. None without
    a hit (nothing thin: no cap)."""
    import bpy
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    mod = ob.modifiers.get('outline')
    shown = mod.show_viewport if mod is not None else None
    if mod is not None:
        mod.show_viewport = False
    try:
        bpy.context.view_layer.update()
        oe = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
        me = oe.to_mesh()
        try:
            nv, npoly = len(me.vertices), len(me.polygons)
            co = np.empty(3 * nv, np.float32); me.vertices.foreach_get('co', co)
            vn = np.empty(3 * nv, np.float32); me.vertices.foreach_get('normal', vn)
            fn = np.empty(3 * npoly, np.float32); me.polygons.foreach_get('normal', fn)
            co, vn, fn = co.reshape(-1, 3), vn.reshape(-1, 3), fn.reshape(-1, 3)
            bvh = BVHTree.FromPolygons(co.tolist(), [tuple(p.vertices) for p in me.polygons])
        finally:
            oe.to_mesh_clear()
    finally:
        if mod is not None:
            mod.show_viewport = shown
    d = []
    for p, n in zip(co.tolist(), vn.tolist()):
        n_ = Vector(n)
        loc, _, idx, dist = bvh.ray_cast(Vector(p) - n_ * 1e-6, -n_, reach)
        if loc is not None and float(np.dot(fn[idx], -np.asarray(n))) > 0:      # the far side, facing away from the start
            d.append(dist)
    return round(float(np.percentile(d, pct)), 6) if d else None


def line_cap(ob):
    """the outline's largest inward move (m) for an outlined object: SHELL_CAP of its shell's thickness (or, for a closed
    thin piece built with cap='measured', of its measured thickness: outline()), or None (no cap: the whole width goes
    inward, as before call I). Objects built before the cap was stored get it from their modifiers."""
    if 'ck_line_cap' in ob:
        return float(ob['ck_line_cap'])
    s = shell_of(ob)
    return SHELL_CAP * s if s > 0 else None


def line_inward(w, cap):
    """how far the outline moves the surface inward at line width w (m): w, capped at `cap`."""
    return min(w, cap) if cap is not None and cap > 0 else w


def line_offset(w, cap):
    """the outline SOLIDIFY's offset for width w: the surface inward by line_inward(w, cap), the hull outward by the
    rest (w (1 + o) / 2 = inward)."""
    if w <= 0:
        return 1.0
    return 2.0 * line_inward(w, cap) / w - 1.0


def _region(ob, line):
    """an outlined object's kind, from its line material (hair_line, garment_line) or name (NAME_skin)."""
    if ob.name.endswith('_skin'):
        return 'skin'
    return {'hair_line': 'hair', 'garment_line': 'garment'}.get(line, 'accessory')


def _deep_tone(m):
    """a toon3 material's deep tone (sRGB; its deep/shade mix's A), else its emission colour, else a brown."""
    nodes = m.node_tree.nodes if m is not None and m.use_nodes else []
    for n in nodes:
        if n.type == 'MIX' and getattr(n, 'data_type', '') == 'RGBA' and n.blend_type == 'MIX' and \
                n.inputs['Factor'].is_linked and not n.inputs['A'].is_linked and not n.inputs['B'].is_linked:
            c = np.clip(np.asarray(n.inputs['A'].default_value[:3], float), 0, None)
            return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)
    return np.array([0.3, 0.2, 0.2])


def line_colors(look=None):
    """the look's outline colours on every outlined object (after the build's stages): 'build' leaves each its own,
    'ink' gives every outline the look's one ink (a drawing's pen: the design's lines are one near-black brown), and
    'material' each object its own line, its main material's deep tone darkened by `darken`; `ink_regions` limits the
    mode to those regions (skin, hair, garment, accessory), the rest keeping their build colour."""
    import bpy
    ln = (look if look is not None else get_look()).get('lines') or {}
    regions = ln.get('ink_regions')                  # the regions the mode applies to (None: all); the rest keep
    for ob in bpy.data.objects:                      # their build colour
        mod = next((m for m in ob.modifiers if m.type == 'SOLIDIFY' and m.name == 'outline'), None) \
            if 'ck_line_w' in ob else None
        if mod is None or mod.material_offset >= len(ob.data.materials):
            continue
        mode = ln.get('color', 'build') if regions is None or ob.get('ck_line_region') in regions else 'build'
        if mode == 'build':
            m0 = bpy.data.materials.get(ob.get('ck_line_mat', ''))
            if m0 is not None and ob.data.materials[mod.material_offset] is not m0:
                ob.data.materials[mod.material_offset] = m0
            continue
        if mode == 'ink':
            m = flat('line_ink', tuple(ln.get('ink', (0.06, 0.024, 0.024))))
        else:
            base = _deep_tone(ob.data.materials[0])
            m = flat(ob.name + '_line', tuple(np.clip(np.asarray(base, float) * ln.get('darken', 0.45), 0, 1)))
        m.use_backface_culling = True
        ob.data.materials[mod.material_offset] = m


# ------------------------------------------------------------------------------------------------------ the view's look
def look_of(spec):
    """a spec's look: its resolved `look` (charkit.cli.resolve lays the style profile under it), else the profile's."""
    from . import styles
    if spec.get('look'):
        return styles.merge(styles.load(spec.get('style', 'anime'))['look'], spec['look'])
    return styles.load(spec.get('style', 'anime'))['look']


def set_look(look):
    """keep the look for set_view, and in the scene (a saved .blend renders its turntable in it)."""
    import bpy
    LOOK.clear(); LOOK.update(look or {})
    bpy.context.scene['charkit_look'] = json.dumps(LOOK)


def get_look():
    if not LOOK:
        try:
            import bpy
            LOOK.update(json.loads(bpy.context.scene.get('charkit_look', '{}')))
        except (ImportError, ValueError):
            pass
    return LOOK


def view_light(az, look=None):
    """toward the key light (world, unit) for a camera at azimuth az (degrees; charkit.qa.render_view's: 0 in front of
    her, increasing round to her left): the look's world light, or its camera key turned with the camera."""
    L = (look if look is not None else get_look()).get('light') or {}
    if L.get('mode') == 'camera':
        a0, el = (math.radians(x) for x in L.get('key', (39.3, 44.6)))
        d = np.array([-math.sin(a0) * math.cos(el), -math.cos(a0) * math.cos(el), math.sin(el)])   # the az 0 camera's
        a = math.radians(az)
        d = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1.0]]) @ d
    else:
        d = np.asarray(L.get('dir', LDIR), float)
    return d / np.linalg.norm(d)


def set_light(d, head_matrix=None):
    """every cel material's light: 'ldir' (world) and the face's 'ldir_head' (head space; head_matrix the head bone's
    world 3x3 rotation, None at rest)."""
    import bpy
    d = np.asarray(d, float) / np.linalg.norm(d)
    dh = np.asarray(head_matrix).T @ d if head_matrix is not None else d
    for m in bpy.data.materials:
        nt = m.node_tree if m.use_nodes else None
        if nt is None:
            continue
        for key, v in (('ldir', d), ('ldir_head', dh)):
            nd = nt.nodes.get(key)
            if nd is not None:
                for i in range(3):
                    x = float(np.float32(v[i]))              # written only when it changes (a write re-tags the
                    if nd.inputs[i].default_value != x:      # material for evaluation)
                        nd.inputs[i].default_value = x


def line_width(ob, m_per_px=None, res_y=None, look=None):
    """an outlined object's width (m) in a view: its build width, or ('screen' lines) the look's share of the picture's
    height times its region's factor, at the view's metres per pixel."""
    ln = (look if look is not None else get_look()).get('lines') or {}
    w0 = float(ob.get('ck_line_w', 0.0012))
    if ln.get('mode') != 'screen' or not m_per_px or not res_y:
        return w0
    return ln.get('frac', 0.0025) * res_y * m_per_px * (ln.get('regions') or {}).get(ob.get('ck_line_region', ''), 1.0)


def set_view(az, m_per_px=None, res_y=None, look=None):
    """the look for one camera (azimuth az, degrees; m_per_px at the target, res_y the picture's height): the light,
    and with 'screen' lines every outline's width (and its offset: a thin shell's inward move capped). -> the light used."""
    import bpy
    look = look if look is not None else get_look()
    d = view_light(az, look)
    set_light(d)
    for ob in bpy.data.objects:
        if 'ck_line_w' not in ob:
            continue
        mod = next((m for m in ob.modifiers if m.type == 'SOLIDIFY' and m.name == 'outline'), None)
        if mod is not None:
            w = line_width(ob, m_per_px, res_y, look)
            t32 = float(np.float32(-w))
            if mod.thickness != t32:                     # only when it changes: a write re-evaluates the object's
                mod.thickness = t32                      # modifier stack (~1.5 s a frame over 47 outlined objects)
            o32 = float(np.float32(line_offset(w, line_cap(ob))))
            if mod.offset != o32:                        # a thin shell's inward move capped (outline())
                mod.offset = o32
    return d
