"""A small idol stage for 3D tests: a dark floor with glowing rings, a gradient backdrop with light bars, swaying beams, and a
soft contact shadow that follows the performer's hips. All emission, so it matches the cel characters."""
import math
import bpy, bmesh
from mathutils import Vector, Matrix
import kit
from kit import hexc


def _mat(name, build):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    build(nt)
    return m


def floor_mat():
    def b(nt):
        N, L = nt.nodes.new, nt.links.new
        out = N('ShaderNodeOutputMaterial'); em = N('ShaderNodeEmission')
        tc = N('ShaderNodeTexCoord'); sep = N('ShaderNodeSeparateXYZ'); L(tc.outputs['Object'], sep.inputs[0])
        xy = N('ShaderNodeCombineXYZ'); L(sep.outputs['X'], xy.inputs[0]); L(sep.outputs['Y'], xy.inputs[1])
        r = N('ShaderNodeVectorMath'); r.operation = 'LENGTH'; L(xy.outputs[0], r.inputs[0])
        k = N('ShaderNodeMath'); k.operation = 'MULTIPLY'; k.inputs[1].default_value = 1.6; L(r.outputs['Value'], k.inputs[0])
        fr = N('ShaderNodeMath'); fr.operation = 'FRACT'; L(k.outputs[0], fr.inputs[0])
        ring = N('ShaderNodeMapRange'); ring.inputs['From Min'].default_value = 0.035; ring.inputs['From Max'].default_value = 0.0
        L(fr.outputs[0], ring.inputs['Value'])
        pool = N('ShaderNodeMapRange'); pool.inputs['From Min'].default_value = 1.6; pool.inputs['From Max'].default_value = 0.0
        L(r.outputs['Value'], pool.inputs['Value'])
        c1 = N('ShaderNodeMix'); c1.data_type = 'RGBA'
        c1.inputs['A'].default_value = (*kit.lin(hexc('1c1830')), 1); c1.inputs['B'].default_value = (*kit.lin(hexc('3b2d5c')), 1)
        L(pool.outputs['Result'], c1.inputs['Factor'])
        hue = N('ShaderNodeMix'); hue.data_type = 'RGBA'
        hue.inputs['A'].default_value = (*kit.lin(hexc('ff6fb5')), 1); hue.inputs['B'].default_value = (*kit.lin(hexc('5fe3ff')), 1)
        rr = N('ShaderNodeMapRange'); rr.inputs['From Min'].default_value = 0.5; rr.inputs['From Max'].default_value = 3.0
        L(r.outputs['Value'], rr.inputs['Value']); L(rr.outputs['Result'], hue.inputs['Factor'])
        c2 = N('ShaderNodeMix'); c2.data_type = 'RGBA'
        L(ring.outputs['Result'], c2.inputs['Factor']); L(c1.outputs['Result'], c2.inputs['A']); L(hue.outputs['Result'], c2.inputs['B'])
        L(c2.outputs['Result'], em.inputs['Color']); L(em.outputs[0], out.inputs['Surface'])
    return _mat('stage_floor', b)


def backdrop_mat():
    def b(nt):
        N, L = nt.nodes.new, nt.links.new
        out = N('ShaderNodeOutputMaterial'); em = N('ShaderNodeEmission')
        tc = N('ShaderNodeTexCoord'); sep = N('ShaderNodeSeparateXYZ'); L(tc.outputs['Generated'], sep.inputs[0])
        g = N('ShaderNodeValToRGB'); e = g.color_ramp.elements
        e[0].position, e[1].position = 0.0, 1.0
        e[0].color = (*kit.lin(hexc('7a2a78')), 1); e[1].color = (*kit.lin(hexc('120f26')), 1)
        mid = g.color_ramp.elements.new(0.35); mid.color = (*kit.lin(hexc('3a2166')), 1)
        L(sep.outputs['Z'], g.inputs[0])
        # vertical light bars
        k = N('ShaderNodeMath'); k.operation = 'MULTIPLY'; k.inputs[1].default_value = 18.0; L(sep.outputs['X'], k.inputs[0])
        fr = N('ShaderNodeMath'); fr.operation = 'FRACT'; L(k.outputs[0], fr.inputs[0])
        bar = N('ShaderNodeMapRange'); bar.inputs['From Min'].default_value = 0.06; bar.inputs['From Max'].default_value = 0.0
        L(fr.outputs[0], bar.inputs['Value'])
        fade = N('ShaderNodeMapRange'); fade.inputs['From Min'].default_value = 0.1; fade.inputs['From Max'].default_value = 0.7
        fade.inputs['To Min'].default_value = 0.9; fade.inputs['To Max'].default_value = 0.0
        L(sep.outputs['Z'], fade.inputs['Value'])
        bm = N('ShaderNodeMath'); bm.operation = 'MULTIPLY'; L(bar.outputs['Result'], bm.inputs[0]); L(fade.outputs['Result'], bm.inputs[1])
        mx = N('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.blend_type = 'ADD'
        mx.inputs['B'].default_value = (*kit.lin(hexc('ff8fd0')), 1)
        L(bm.outputs[0], mx.inputs['Factor']); L(g.outputs['Color'], mx.inputs['A'])
        L(mx.outputs['Result'], em.inputs['Color']); L(em.outputs[0], out.inputs['Surface'])
    return _mat('stage_backdrop', b)


def beam_mat(color):
    def b(nt):
        N, L = nt.nodes.new, nt.links.new
        out = N('ShaderNodeOutputMaterial'); em = N('ShaderNodeEmission'); tr = N('ShaderNodeBsdfTransparent')
        em.inputs['Color'].default_value = (*kit.lin(color), 1); em.inputs['Strength'].default_value = 1.0
        tc = N('ShaderNodeTexCoord'); sep = N('ShaderNodeSeparateXYZ'); L(tc.outputs['Generated'], sep.inputs[0])
        a = N('ShaderNodeMapRange'); a.inputs['From Min'].default_value = 0.0; a.inputs['From Max'].default_value = 1.0
        a.inputs['To Min'].default_value = 0.0; a.inputs['To Max'].default_value = 0.22
        L(sep.outputs['Z'], a.inputs['Value'])
        lw = N('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.5
        edge = N('ShaderNodeMath'); edge.operation = 'SUBTRACT'; edge.inputs[0].default_value = 1.0; L(lw.outputs['Facing'], edge.inputs[1])
        am = N('ShaderNodeMath'); am.operation = 'MULTIPLY'; L(a.outputs['Result'], am.inputs[0]); L(edge.outputs[0], am.inputs[1])
        mx = N('ShaderNodeMixShader'); L(am.outputs[0], mx.inputs['Fac']); L(tr.outputs[0], mx.inputs[1]); L(em.outputs[0], mx.inputs[2])
        L(mx.outputs[0], out.inputs['Surface'])
    m = _mat(f'beam_{color}', b)
    m.surface_render_method = 'BLENDED'
    return m


def shadow_mat():
    def b(nt):
        N, L = nt.nodes.new, nt.links.new
        out = N('ShaderNodeOutputMaterial'); em = N('ShaderNodeEmission'); tr = N('ShaderNodeBsdfTransparent')
        em.inputs['Color'].default_value = (*kit.lin(hexc('0c0a18')), 1)
        tc = N('ShaderNodeTexCoord'); sep = N('ShaderNodeSeparateXYZ'); L(tc.outputs['Object'], sep.inputs[0])
        xy = N('ShaderNodeCombineXYZ'); L(sep.outputs['X'], xy.inputs[0]); L(sep.outputs['Y'], xy.inputs[1])
        r = N('ShaderNodeVectorMath'); r.operation = 'LENGTH'; L(xy.outputs[0], r.inputs[0])
        a = N('ShaderNodeMapRange'); a.inputs['From Min'].default_value = 0.34; a.inputs['From Max'].default_value = 0.12
        a.inputs['To Max'].default_value = 0.55
        L(r.outputs['Value'], a.inputs['Value'])
        mx = N('ShaderNodeMixShader'); L(a.outputs['Result'], mx.inputs['Fac']); L(tr.outputs[0], mx.inputs[1]); L(em.outputs[0], mx.inputs[2])
        L(mx.outputs[0], out.inputs['Surface'])
    m = _mat('contact_shadow', b)
    m.surface_render_method = 'BLENDED'
    return m


def build(arm=None, beats=None):
    """beats: song-time beat seconds mapped to frames by the caller (for the beams' sway); returns the objects."""
    objs = {}
    bpy.ops.mesh.primitive_circle_add(vertices=96, radius=4.5, fill_type='TRIFAN', location=(0, 0, 0))
    fl = bpy.context.active_object; fl.name = 'floor'; fl.data.materials.append(floor_mat()); objs['floor'] = fl
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=7.5, depth=7.0, location=(0, 0, 3.0), end_fill_type='NOTHING')
    bd = bpy.context.active_object; bd.name = 'backdrop'
    bm = bmesh.new(); bm.from_mesh(bd.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_center_median().y < -3.0], context='FACES')
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(bd.data); bm.free()
    bd.data.materials.append(backdrop_mat()); objs['backdrop'] = bd
    beams = []
    for i, (x, col) in enumerate([(-3.2, 'ff6fb5'), (-1.6, '5fe3ff'), (0.0, 'ffd36f'), (1.6, '5fe3ff'), (3.2, 'ff6fb5')]):
        bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=0.9, radius2=0.05, depth=7.0, end_fill_type='NOTHING',
                                        location=(0, 0, 0))
        c = bpy.context.active_object; c.name = f'beam{i}'
        c.data.materials.append(beam_mat(hexc(col)))
        # the cone's tip at the rig above and behind the stage, its mouth on the floor
        c.data.transform(Matrix.Translation((0, 0, -3.5)))
        c.location = (x, 3.8, 6.2)
        c.rotation_euler = (math.radians(-28), math.radians(-x * 4), 0)
        beams.append(c)
    objs['beams'] = beams
    if arm is not None:
        bpy.ops.mesh.primitive_plane_add(size=0.8, location=(0, 0, 0.002))
        sh = bpy.context.active_object; sh.name = 'contact_shadow'; sh.data.materials.append(shadow_mat())
        con = sh.constraints.new('COPY_LOCATION'); con.target = arm; con.subtarget = 'hips'; con.use_z = False
        objs['shadow'] = sh
    return objs


def sway_beams(beams, frames, fps, beat_s, phase=0.0):
    for f in range(1, frames + 1, 2):
        t = (f - 1) / fps
        for i, c in enumerate(beams):
            x0 = [-3.2, -1.6, 0.0, 1.6, 3.2][i]
            c.rotation_euler = (math.radians(-28 + 6 * math.sin(2 * math.pi * t / (beat_s * 4) + i)),
                                math.radians(-x0 * 4 + 10 * math.sin(2 * math.pi * t / (beat_s * 8) + i * 1.7 + phase)), 0)
            c.keyframe_insert('rotation_euler', frame=f)
