"""charkit's cel shading (docs/CHARKIT.md §2, materials): three-tone toon on an art-directed light (emission, so the look is the
shader's, not the lights'), flat colours, alpha-textured plates (the eyes), and inverted-hull outlines. Blender-side; the
VRM export maps these onto MToon.
"""
import numpy as np

LDIR = np.array([-0.45, -0.55, 0.70])        # toward the key light (front-left-above), world
LDIR = LDIR / np.linalg.norm(LDIR)
MATS = {}


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


def outline(ob, thick=0.0012, color=(0.30, 0.20, 0.22), name='line'):
    """inverted hull: a flipped, back-face-culled solidify shell in the line colour."""
    m = flat(name, color)
    m.use_backface_culling = True
    ob.data.materials.append(m)
    sol = ob.modifiers.new('outline', 'SOLIDIFY')
    sol.thickness = -thick; sol.offset = 1.0; sol.use_flip_normals = True; sol.use_rim = False
    sol.material_offset = len(ob.data.materials) - 1
    return sol
