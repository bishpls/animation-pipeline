"""Anime hair (HoYoverse-style) built by script: thick lens-section clumps that grow from the crown and lie on a hair
volume, overlapping in two layers, waving and curling out at the tips; bangs over the forehead; face-framing locks; and a
hair shader with a three-tone ramp and an angel-ring highlight broken lock by lock.

Every lock carries a UV layer 'lock': u across the clump (-1 edge, 0 centre, +1 edge), v along it (0 root, 1 tip).
    import hair; objs = hair.build(HC, arm, volume=hair.Volume(...), ...)
"""
import math, random
import bpy, bmesh
from mathutils import Vector, Matrix
import kit


class Volume:
    """The hair mass's outer surface around the head centre: a round crown, full at the cheeks, curling in at the ends.
    az: degrees around Z from the front (+ = her left); el: degrees from the eye line (-65 = the ends)."""

    def __init__(self, top=0.168, rx=0.152, ry_front=0.104, ry_back=0.150, bulge=0.26, drop=0.128):
        self.top, self.rx, self.ryf, self.ryb, self.bulge, self.drop = top, rx, ry_front, ry_back, bulge, drop

    def point(self, az, el, r=1.0):
        a, e = math.radians(az), math.radians(el)
        back = 0.5 - 0.5 * math.cos(a)
        ry = self.ryf + (self.ryb - self.ryf) * back
        if e >= 0:
            c = math.cos(e) ** 0.78
            x, y, z = math.sin(a) * c * self.rx, -math.cos(a) * c * ry, math.sin(e) ** 0.95 * self.top
        else:
            f = min(1.2, -e / math.radians(62))
            k = 1 + self.bulge * math.sin(min(1.0, f) * math.pi * 0.62) - 0.12 * max(0.0, f - 0.85)
            x, y, z = math.sin(a) * self.rx * k, -math.cos(a) * ry * k, -self.drop * f
        return Vector((x * r, y * r, z * r))

    def normal(self, az, el):
        p = self.point(az, el)
        da = self.point(az + 1, el) - self.point(az - 1, el)
        de = self.point(az, el + 1) - self.point(az, el - 1)
        n = de.cross(da)
        if n.dot(p) < 0:
            n = -n
        return n.normalized() if n.length > 1e-9 else p.normalized()


def clump(bm, uvl, path, normals, width, thick=0.38, root_taper=0.45, tip=0.8, sides=10):
    """a tapered clump along path (Vectors) with its outward normals; lens cross-section, pointed tip."""
    n = len(path) - 1
    rings = []
    for i, c in enumerate(path):
        s = i / n
        d = (path[min(i + 1, n)] - path[max(i - 1, 0)]).normalized()
        nr = normals[i]
        side = d.cross(nr)
        side = side.normalized() if side.length > 1e-6 else Vector((1, 0, 0))
        up = side.cross(d).normalized()
        if up.dot(nr) < 0:
            up = -up
        wr = root_taper + (1 - root_taper) * min(1.0, s / 0.2)                   # thin at the root
        belly = 1 + 0.25 * math.sin(math.pi * min(1.0, s / 0.85))                 # fattest low down, like a wave's belly
        tl = tip * 0.28
        wt = max(0.02, 1 - max(0.0, (s - (1 - tl)) / tl)) ** 0.9                  # a short, sharp point
        w = width * wr * wt * belly
        th = w * thick
        ring = []
        for k in range(sides):
            ph = 2 * math.pi * k / sides
            cx = math.cos(ph); sy = math.sin(ph)
            px = math.copysign(abs(cx) ** 0.75, cx) * w
            py = sy * th * (1.0 if sy > 0 else 0.55)                            # fuller on the outside
            ring.append((bm.verts.new(c + side * px + up * py), cx, s))
        rings.append(ring)
    for i in range(n):
        a, b = rings[i], rings[i + 1]
        for k in range(sides):
            f = bm.faces.new((a[k][0], a[(k + 1) % sides][0], b[(k + 1) % sides][0], b[k][0]))
            for l in f.loops:
                for (v, cx, s) in (a[k], a[(k + 1) % sides], b[(k + 1) % sides], b[k]):
                    if v == l.vert:
                        l[uvl].uv = (cx, s)
    cap = bm.faces.new([r[0] for r in reversed(rings[0])])
    for l in cap.loops:
        l[uvl].uv = (0, 0)


def lock_on_volume(V, az_path, el_path, r_path, wave=0.0, waves=1.5, phase=0.0, curl=0.0, n=22, lift=0.0, bob=0.0):
    """a path over the volume: az/el/r are functions of s in [0,1]; wave swings it sideways along the surface; curl lifts
    the last quarter outward and up."""
    pts, nrs = [], []
    for i in range(n + 1):
        s = i / n
        az, el, r = az_path(s), el_path(s), r_path(s)
        p = V.point(az, el, r)
        nr = V.normal(az, el)
        tang = (V.point(az + 1, el, r) - V.point(az - 1, el, r)).normalized()
        p = p + tang * wave * math.sin(2 * math.pi * waves * s + phase) * s ** 0.8
        p = p + nr * bob * math.sin(2 * math.pi * waves * s + phase + 1.3) * s ** 0.7          # in and out: waves
        if curl and s > 0.72:
            u = (s - 0.72) / 0.28
            p = p + nr * curl * 0.6 * u * u + Vector((0, 0, curl * 1.1 * u ** 2.0))
        p = p + nr * lift
        pts.append(p); nrs.append(nr)
    return pts, nrs


def build(centre, arm, bone, hair_mat, under_mat, V=None, seed=5, spring_bone=None):
    V = V or Volume()
    R = random.Random(seed)
    out = []

    # a smooth proxy of the whole mass: the clumps shade with ITS normals (large clean shadow shapes, the anime look);
    # the outlines round each clump carry the clump detail
    bm = bmesh.new()
    NA, NE = 72, 40
    rows = [[bm.verts.new(V.point(-180 + 360 * k / NA, 90 - 160 * i / NE, 1.0)) for k in range(NA)] for i in range(NE + 1)]
    for i in range(NE):
        for k in range(NA):
            bm.faces.new((rows[i][k], rows[i][(k + 1) % NA], rows[i + 1][(k + 1) % NA], rows[i + 1][k]))
    bmesh.ops.remove_doubles(bm, verts=rows[0], dist=1e-6)
    bm.normal_update()
    inward = [f for f in bm.faces if f.normal.dot(f.calc_center_median()) < 0]
    bmesh.ops.reverse_faces(bm, faces=inward)                  # open at the bottom, so orient by hand: outward
    bmesh.ops.transform(bm, matrix=Matrix.Translation(centre), verts=bm.verts)
    proxy = kit.mesh_from_bm('hair_normals_proxy', bm, [])
    proxy.hide_render = True; proxy.hide_viewport = True
    kit.bone_parent(proxy, arm, bone)

    def finish(name, bm, mat, outline=0.0018, smooth_normals=0.85, follow=None):
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)      # clumps wound outward, or transferred normals invert
        tr = Matrix.Translation(centre)
        bmesh.ops.transform(bm, matrix=tr, verts=bm.verts)
        ob = kit.mesh_from_bm(name, bm, [mat])
        if smooth_normals:
            dt = ob.modifiers.new('volume_normals', 'DATA_TRANSFER')
            dt.object = proxy; dt.use_loop_data = True; dt.data_types_loops = {'CUSTOM_NORMAL'}
            dt.loop_mapping = 'POLYINTERP_NEAREST'; dt.mix_factor = smooth_normals
        kit.add_outline(ob, outline, kit.hexc('7a3524'))
        kit.bone_parent(ob, arm, follow or bone)
        out.append(ob)
        return ob

    # a smooth cap under everything, so no scalp shows between clumps
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('lock')
    NA, NE = 64, 26
    grid = []
    for i in range(NE + 1):
        el = 90 - (90 - (-40)) * i / NE
        grid.append([bm.verts.new(V.point(-180 + 360 * k / NA, el, 0.965)) for k in range(NA)])
    for i in range(NE):
        for k in range(NA):
            az = -180 + 360 * (k + 0.5) / NA
            el = 90 - 130 * (i + 0.5) / NE
            if abs(az) < 58 and el < 32:
                continue                                                # open over the face
            bm.faces.new((grid[i][k], grid[i][(k + 1) % NA], grid[i + 1][(k + 1) % NA], grid[i + 1][k]))
    bmesh.ops.remove_doubles(bm, verts=grid[0], dist=1e-6)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    finish('hair_cap', bm, under_mat, 0.0, 1.0)

    # under layer: fat, darker clumps filling the mass from the sides round the back
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('lock')
    for k in range(16):
        az0 = 66 + (360 - 132) * k / 15 + R.uniform(-4, 4)
        el_end = -60 + R.uniform(-8, 6)
        pts, nrs = lock_on_volume(V, lambda s, a=az0: a + 5 * s, lambda s, e=el_end: 72 - (72 - e) * s,
                                  lambda s: 0.972 + 0.02 * s, wave=0.012, bob=0.006, phase=R.uniform(0, 6), curl=0.02)
        clump(bm, uvl, pts, nrs, 0.034 + 0.006 * R.random(), thick=0.42)
    finish('hair_under', bm, under_mat, follow=spring_bone)

    # main layer: fat clumps from the crown down the sides and back, overlapping, in waves, the tips curling out
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('lock')
    N = 22
    for k in range(N):
        az0 = 60 + (360 - 120) * k / (N - 1) + R.uniform(-3, 3)
        swirl = R.uniform(-10, 10)
        el_end = -60 + (0, -12, 5, -7, 9, -3, -14, 3)[k % 8] + R.uniform(-3, 3)
        width = 0.028 + 0.006 * R.random()
        pts, nrs = lock_on_volume(V, lambda s, a=az0, w=swirl: a + w * s,
                                  lambda s, e=el_end: 86 - (86 - e) * s, lambda s: 1.0 + 0.012 * math.sin(s * 3),
                                  wave=0.020 + 0.012 * R.random(), bob=0.014 + 0.008 * R.random(),
                                  waves=1.5 + 0.5 * R.random(), phase=R.uniform(0, 6), curl=0.05 + 0.035 * R.random())
        clump(bm, uvl, pts, nrs, width, thick=0.44, tip=0.85)
    finish('hair_main', bm, hair_mat, follow=spring_bone)

    # bangs: a few big pointed clumps from the part over the forehead, sweeping out, one long between the eyes
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('lock')
    for az_t, el_t, w, r_t, sweep in [(-52, 14, 0.020, 1.02, -8), (-37, 6, 0.024, 0.98, -10), (-21, 12, 0.024, 0.95, -8),
                                      (-5, -4, 0.018, 0.94, -3), (10, 10, 0.022, 0.94, 4), (25, 6, 0.024, 0.96, 8),
                                      (40, 12, 0.022, 0.99, 10), (54, 18, 0.018, 1.02, 8)]:
        az_r = az_t * 0.3 + 8
        pts, nrs = lock_on_volume(V, lambda s, a0=az_r, a1=az_t, sw=sweep: a0 + (a1 - a0) * s ** 0.8 + sw * s ** 3,
                                  lambda s, e=el_t: 72 - (72 - e) * s ** 0.9,
                                  lambda s, rt=r_t: 1.0 + (rt - 1.0) * s ** 1.5, wave=0.002, waves=0.5,
                                  phase=R.uniform(0, 3), n=18)
        clump(bm, uvl, pts, nrs, w, thick=0.34, tip=1.2)
    # face-framing locks in front of the ears, waving down past the chin and curling out
    for sx in (-1, 1):
        for az, w, el_end, cu in ((60, 0.018, -66, 0.03), (70, 0.022, -58, 0.04)):
            pts, nrs = lock_on_volume(V, lambda s, a=az, x=sx: x * (a * 0.72 + a * 0.28 * s),
                                      lambda s, e=el_end: 42 - (42 - e) * s, lambda s: 1.02 + 0.03 * s,
                                      wave=0.012, bob=0.006, waves=1.3, phase=0.0 if sx > 0 else math.pi, curl=cu)
            clump(bm, uvl, pts, nrs, w, thick=0.42)
    # the ahoge
    base = V.point(-6, 88, 0.99)
    pts = [base + Vector((0.045 * u ** 1.6, 0.004 * u, 0.075 * math.sin(u * 2.5))) for u in [i / 14 for i in range(15)]]
    clump(bm, uvl, pts, [Vector((0, 0, 1))] * len(pts), 0.007, thick=0.6, root_taper=0.8)
    finish('hair_bangs', bm, hair_mat)
    return out


def hair_material(name, lit, shade, deep, ring=(1.0, 0.80, 0.62), head_z=0.0, ring_el=40.0, thresh=0.5):
    """Three-tone ramp on N.L plus an angel-ring highlight: a band at ring_z above the eye line, on each clump's centre,
    on the lit side, brighter where the hair faces the camera."""
    m = kit.toon3(name, lit, shade, deep, thresh=thresh)
    nt = m.node_tree; N = nt.nodes.new; L = nt.links.new
    em = next(n for n in nt.nodes if n.type == 'EMISSION')
    src = em.inputs['Color'].links[0].from_socket
    uv = N('ShaderNodeUVMap'); uv.uv_map = 'lock'
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
    # a lens per clump: the band is widest on the clump's centre line and pinches to a point at its edges
    u2 = N('ShaderNodeMath'); u2.operation = 'POWER'; u2.inputs[1].default_value = 2.0; L(across.outputs[0], u2.inputs[0])
    wid = N('ShaderNodeMath'); wid.operation = 'MULTIPLY_ADD'; wid.inputs[1].default_value = -math.radians(5.0)
    wid.inputs[2].default_value = math.radians(5.0); L(u2.outputs[0], wid.inputs[0])            # 5 deg * (1 - u^2)
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
    fade = N('ShaderNodeMath'); fade.operation = 'MULTIPLY'; fade.inputs[1].default_value = 0.6
    L(m3.outputs[0], fade.inputs[0])
    hi = N('ShaderNodeMix'); hi.data_type = 'RGBA'; hi.inputs['B'].default_value = (*kit.lin(ring), 1)
    L(fade.outputs[0], hi.inputs['Factor']); L(src, hi.inputs['A'])
    L(hi.outputs['Result'], em.inputs['Color'])
    return m
