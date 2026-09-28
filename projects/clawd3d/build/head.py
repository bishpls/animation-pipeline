"""An anime head (HoYoverse-style) built by script: shape from Clawd's drawn face contour, face shading by an SDF threshold
map (the Genshin method: the face's light/shadow edge comes from a painted map keyed on the light's angle to the head, not
from normals, so it is always a clean, designed shape), and the drawn eyes and mouths as decals.

Head space: origin at the eye line's centre, x = her left, y = back (front is -y), z = up; metres.
    import head; ob = head.build(centre, arm, bone='head'); head.face_material(...)
    ~/animation-pipeline/.venv/bin/python projects/clawd3d/build/head.py --maps   (writes out/tex/face_sdf.png, face_blush.png)
"""
import math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(os.path.dirname(HERE), 'out', 'tex')

# the drawn jaw contour: (drop below the eye line, half-width), metres (from the 2D rig's face layer, 1064 = face centre)
JAW = [(0.0, 0.0770), (0.003, 0.0752), (0.0205, 0.0716), (0.038, 0.0650), (0.0555, 0.0540), (0.073, 0.0367),
       (0.085, 0.0190), (0.092, 0.0)]
CHIN = 0.093                   # chin tip below the eye line
TOP = 0.117                    # skull top above the eye line (the hair adds its own volume)
FACE_WIN = (-0.092, 0.092, -0.102, 0.120)      # the face UV window: x0, x1, z0, z1 (head space)


def lerp_table(tab, x):
    if x <= tab[0][0]:
        return tab[0][1]
    for (x0, y0), (x1, y1) in zip(tab, tab[1:]):
        if x <= x1:
            u = (x - x0) / (x1 - x0)
            return y0 + (y1 - y0) * (u * u * (3 - 2 * u))
    return tab[-1][1]


def section(dz):
    """-> (front half-width, back half-width, front depth, back depth, front squareness) of the head at height dz."""
    if dz >= 0:
        k = max(0.0, 1 - (dz / TOP) ** 2) ** 0.5
        wf = (0.0770 + 0.006 * math.sin(min(1, dz / 0.05) * math.pi / 2)) * k        # the cranium swells a little above the eyes
        wb = wf * 1.02
        df = 0.0845 * max(0.0, 1 - (dz / (TOP * 1.02)) ** 2) ** 0.5
        db = 0.100 * max(0.0, 1 - (dz / (TOP * 1.04)) ** 2) ** 0.5
        n = 2.7
    else:
        d = -dz
        wf = lerp_table(JAW, d)
        wb = 0.077 - (0.077 - 0.036) * min(1, d / CHIN) ** 1.3                         # the skull narrows into the neck
        df = lerp_table([(0, 0.0845), (0.03, 0.0848), (0.055, 0.0800), (0.075, 0.0745), (0.092, 0.0690)], d)
        db = lerp_table([(0, 0.100), (0.03, 0.090), (0.06, 0.060), (0.093, 0.032)], d)
        n = 2.7 - 0.9 * min(1, d / CHIN)                                                # squarer face, rounder chin
    return wf, wb, df, db, n


def surface(a, dz):
    """head-space point at azimuth a (radians, 0 = the front, + = her left) and height dz."""
    wf, wb, df, db, n = section(dz)
    s, c = math.sin(a), math.cos(a)
    front = c > 0
    w = wf if front else (wf + (wb - wf) * min(1, -c * 2.5))
    dep = df if front else db
    ex = 2 / n if front else 1.0
    x = math.copysign(abs(s) ** ex, s) * w
    y = -math.copysign(abs(c) ** ex, c) * dep
    # nose: a small ridge down from between the eyes to a soft tip; the mouth sits back a touch
    if front:
        y -= 0.0055 * math.exp(-(x / 0.0065) ** 2 - ((dz + 0.029) / 0.010) ** 2)
        y -= 0.0018 * math.exp(-(x / 0.006) ** 2) * (1 if -0.029 < dz < 0.0 else 0)
        y += 0.0012 * math.exp(-(x / 0.018) ** 2 - ((dz + 0.057) / 0.008) ** 2)
    return x, y, dz


def build(centre, arm=None, bone='head', segs=(72, 56), mats=()):
    import bpy, bmesh
    from mathutils import Vector
    import kit
    bm = bmesh.new()
    NA, NZ = segs
    rows = []
    top = bm.verts.new(centre + Vector((0, 0.004, TOP)))
    for i in range(1, NZ):
        e = math.pi / 2 - math.pi * i / NZ                  # +90 .. -90 degrees
        dz = TOP * math.sin(e) if e >= 0 else -CHIN * math.sin(-e) ** 0.85
        ring = [bm.verts.new(centre + Vector(surface(2 * math.pi * k / NA, dz))) for k in range(NA)]
        rows.append(ring)
    bot = bm.verts.new(centre + Vector((0, -0.012, -CHIN + 0.003)))
    for k in range(NA):
        bm.faces.new((top, rows[0][(k + 1) % NA], rows[0][k]))
    for i in range(len(rows) - 1):
        for k in range(NA):
            bm.faces.new((rows[i][k], rows[i][(k + 1) % NA], rows[i + 1][(k + 1) % NA], rows[i + 1][k]))
    last = rows[-1]
    for k in range(NA):
        bm.faces.new((last[k], last[(k + 1) % NA], bot))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    uv = bm.loops.layers.uv.new('face')
    x0, x1, z0, z1 = FACE_WIN
    for f in bm.faces:
        for l in f.loops:
            p = l.vert.co - centre
            l[uv].uv = ((p.x - x0) / (x1 - x0), (p.z - z0) / (z1 - z0))
    ob = kit.mesh_from_bm('head', bm, list(mats))
    sub = ob.modifiers.new('sub', 'SUBSURF'); sub.levels = 1; sub.render_levels = 2
    if arm:
        kit.bone_parent(ob, arm, bone)
    return ob


# ---------------------------------------------------------------- the SDF face-shadow threshold map
def maps(size=512):
    """face_sdf.png: per face pixel, the light angle t in [0,1] (0 = light from the front, 0.5 = from her left side, 1 =
    from behind) past which the pixel falls into shadow, for light from HER LEFT (+x); the shader mirrors u for the other
    side. The edge sweeps from her right cheek across as the light comes round, following the jaw's width so it wraps the
    chin, with a small nose shadow that appears early and a lit triangle kept on the far cheek until well past side-on.
    face_blush.png: soft cheek blush (alpha)."""
    import numpy as np
    from PIL import Image
    x0, x1, z0, z1 = FACE_WIN
    u = (np.arange(size) + 0.5) / size
    v = (np.arange(size) + 0.5) / size
    U, Vv = np.meshgrid(u, v[::-1])                          # image row 0 = the top of the window
    X = x0 + U * (x1 - x0); Z = z0 + Vv * (z1 - z0)
    wid = np.vectorize(lambda z: section(z)[0])(Z[:, 0])[:, None] + 1e-4
    # normalised across the face at this height: -1 = her right edge (far from the light), +1 = her left edge
    s = np.clip(X / wid, -1.3, 1.3)
    # the terminator on a flattened face: the edge reaches the centre line when the light is side-on (t = 0.5)
    t_edge = 0.5 + 0.5 * np.sign(s) * np.abs(s) ** 1.25
    t_edge = 0.06 + (1 - 0.1) * t_edge                        # a front light leaves the whole face lit
    thr = np.clip(t_edge, 0, 1)
    # the nose's shadow on her right cheek: early, small, a soft triangle under and beside the tip
    nx, nz = X / 0.018, (Z + 0.036) / 0.016
    nose = (nx < 0.2) & (nx > -1.1) & (np.abs(nz) < 1.0 - 0.6 * np.abs(nx + 0.3))
    thr = np.where(nose, np.minimum(thr, 0.22 + 0.08 * np.abs(nx)), thr)
    # the lit triangle on the far cheek under the eye (Rembrandt), held until the light is well behind side-on
    tri_x, tri_z = (X + 0.035) / 0.022, (Z + 0.030) / 0.020
    tri = (np.abs(tri_x) < 1) & (tri_z > -1) & (tri_z < 1 - np.abs(tri_x) * 1.2)
    thr = np.where(tri & (s < 0), np.maximum(thr, 0.52), thr)
    try:
        from scipy.ndimage import gaussian_filter
        thr = gaussian_filter(thr, 2.0)
    except ImportError:
        pass
    os.makedirs(TEX, exist_ok=True)
    Image.fromarray((np.clip(thr, 0, 1) * 65535).astype(np.uint16)).save(os.path.join(TEX, 'face_sdf.png'))
    # blush: two soft ovals under the eyes
    b = np.zeros_like(X)
    for sx in (-1, 1):
        b += np.exp(-(((X - sx * 0.045) / 0.020) ** 2 + ((Z + 0.022) / 0.010) ** 2))
    a = (np.clip(b, 0, 1) * 0.55 * 255).astype(np.uint8)
    rgba = np.dstack([np.full_like(a, 255), np.full_like(a, 150), np.full_like(a, 150), a])
    Image.fromarray(rgba, 'RGBA').save(os.path.join(TEX, 'face_blush.png'))
    print('face maps ->', TEX)


def face_material(name, lit, shade, rim=(1, 0.92, 0.88), line_soft=0.012, blush=True):
    """Emission face shader: the SDF threshold (sampled mirrored when the light is on her right) against the light's angle
    to the head, in the head object's space, so the shadow shape turns with the head."""
    import bpy
    import kit
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    N = nt.nodes.new; L = nt.links.new
    out = N('ShaderNodeOutputMaterial')
    ld = N('ShaderNodeCombineXYZ'); ld.name = 'ldir'
    for i in range(3):
        ld.inputs[i].default_value = kit.LDIR[i]
    vt = N('ShaderNodeVectorTransform'); vt.vector_type = 'VECTOR'; vt.convert_from = 'WORLD'; vt.convert_to = 'OBJECT'
    L(ld.outputs[0], vt.inputs[0])
    sep = N('ShaderNodeSeparateXYZ'); L(vt.outputs[0], sep.inputs[0])
    negy = N('ShaderNodeMath'); negy.operation = 'MULTIPLY'; negy.inputs[1].default_value = -1.0
    L(sep.outputs['Y'], negy.inputs[0])                                    # forward component
    absx = N('ShaderNodeMath'); absx.operation = 'ABSOLUTE'; L(sep.outputs['X'], absx.inputs[0])
    ang = N('ShaderNodeMath'); ang.operation = 'ARCTAN2'
    L(absx.outputs[0], ang.inputs[0]); L(negy.outputs[0], ang.inputs[1])
    t = N('ShaderNodeMath'); t.operation = 'DIVIDE'; t.inputs[1].default_value = math.pi; L(ang.outputs[0], t.inputs[0])
    # uv, mirrored when the light is on her right (x < 0)
    uvn = N('ShaderNodeUVMap'); uvn.uv_map = 'face'
    suv = N('ShaderNodeSeparateXYZ'); L(uvn.outputs[0], suv.inputs[0])
    flipu = N('ShaderNodeMath'); flipu.operation = 'SUBTRACT'; flipu.inputs[0].default_value = 1.0; L(suv.outputs['X'], flipu.inputs[1])
    right = N('ShaderNodeMath'); right.operation = 'LESS_THAN'; right.inputs[1].default_value = 0.0; L(sep.outputs['X'], right.inputs[0])
    mu = N('ShaderNodeMix'); mu.data_type = 'FLOAT'
    L(right.outputs[0], mu.inputs['Factor']); L(suv.outputs['X'], mu.inputs['A']); L(flipu.outputs[0], mu.inputs['B'])
    cuv = N('ShaderNodeCombineXYZ'); L(mu.outputs['Result'], cuv.inputs[0]); L(suv.outputs['Y'], cuv.inputs[1])
    sdf = N('ShaderNodeTexImage'); sdf.image = bpy.data.images.load(os.path.join(TEX, 'face_sdf.png'))
    sdf.image.colorspace_settings.name = 'Non-Color'; sdf.extension = 'EXTEND'; sdf.interpolation = 'Cubic'
    L(cuv.outputs[0], sdf.inputs['Vector'])
    diff = N('ShaderNodeMath'); diff.operation = 'SUBTRACT'
    L(t.outputs[0], diff.inputs[0]); L(sdf.outputs['Color'], diff.inputs[1])
    edge = N('ShaderNodeMapRange'); edge.inputs['From Min'].default_value = -line_soft; edge.inputs['From Max'].default_value = line_soft
    L(diff.outputs[0], edge.inputs['Value'])
    # the light's height matters too: a light from well below or above dims the whole face a little
    col = N('ShaderNodeMix'); col.data_type = 'RGBA'
    col.inputs['A'].default_value = (*kit.lin(lit), 1); col.inputs['B'].default_value = (*kit.lin(shade), 1)
    L(edge.outputs['Result'], col.inputs['Factor'])
    last = col.outputs['Result']
    if blush:
        bt = N('ShaderNodeTexImage'); bt.image = bpy.data.images.load(os.path.join(TEX, 'face_blush.png')); bt.extension = 'CLIP'
        L(uvn.outputs[0], bt.inputs['Vector'])
        bm = N('ShaderNodeMix'); bm.data_type = 'RGBA'; bm.blend_type = 'MULTIPLY'
        L(bt.outputs['Alpha'], bm.inputs['Factor']); L(last, bm.inputs['A']); L(bt.outputs['Color'], bm.inputs['B'])
        last = bm.outputs['Result']
    lw = N('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.25
    rr = N('ShaderNodeMapRange'); rr.inputs['From Min'].default_value = 0.72; rr.inputs['From Max'].default_value = 0.76
    rr.inputs['To Max'].default_value = 0.18
    L(lw.outputs['Facing'], rr.inputs['Value'])
    rim_mix = N('ShaderNodeMix'); rim_mix.data_type = 'RGBA'; rim_mix.blend_type = 'SCREEN'
    rim_mix.inputs['B'].default_value = (*kit.lin(rim), 1)
    L(rr.outputs['Result'], rim_mix.inputs['Factor']); L(last, rim_mix.inputs['A'])
    em = N('ShaderNodeEmission'); L(rim_mix.outputs['Result'], em.inputs['Color']); L(em.outputs[0], out.inputs['Surface'])
    kit.MATS[name] = m
    return m


if __name__ == '__main__':
    if '--maps' in sys.argv:
        maps()
