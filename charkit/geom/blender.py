"""The Blender side of charkit.geom: numpy + bpy only (no scipy / numba), so it runs in Blender's bundled Python.

    ob, meta = load_part('charkit/out/geom/clawd/hair.npz', 'hair_geom')    # a mesh object in world space
    # with an inverted-hull outline: the outline first, then the envelope normals by transfer (see transfer_normals)
    ob, meta = load_part(path, 'hair', material=m, normals=None); shade.outline(ob)
    transfer_normals(ob, normals_proxy(path, 'hair_normals'))

A part saved by charkit.geom.parts.save_part is V (world, metres, z up: the assembled character's rest pose), F
(triangles), vn (the envelope normals: set as custom split normals, so the toon ramp sees one smooth mass) and vn_geom
(the plain vertex normals, kept for reference), with a JSON `meta` (the alignment, the extraction's numbers, the health
report). The surface is closed and manifold: no backface culling or remesh is needed; an inverted-hull outline works.
"""
import numpy as np

from .io import load_npz


def load_part(path, name, material=None, normals='envelope', link=True):
    """a saved part as a Blender mesh object (smooth shaded). normals: 'envelope' (the stored vn as custom split
    normals), 'geometric' (vn_geom), or None (Blender's own). -> (object, meta dict)."""
    import bpy
    m, meta, extra = load_npz(path, with_meta=True)
    me = bpy.data.meshes.new(name)
    me.vertices.add(m.nv)
    me.vertices.foreach_set('co', m.V.astype(np.float32).ravel())
    me.loops.add(3 * m.nf)
    me.loops.foreach_set('vertex_index', m.F.astype(np.int32).ravel())
    me.polygons.add(m.nf)
    me.polygons.foreach_set('loop_start', np.arange(0, 3 * m.nf, 3, dtype=np.int32))
    if hasattr(me.polygons, 'foreach_set') and 'loop_total' in me.polygons[0].bl_rna.properties and \
            not me.polygons[0].bl_rna.properties['loop_total'].is_readonly:
        me.polygons.foreach_set('loop_total', np.full(m.nf, 3, np.int32))
    me.update(calc_edges=True)
    me.validate(clean_customdata=False)
    if hasattr(me, 'shade_smooth'):
        me.shade_smooth()
    else:
        me.polygons.foreach_set('use_smooth', np.ones(m.nf, bool))
    N = m.vn if normals == 'envelope' else extra.get('vn_geom') if normals == 'geometric' else None
    if N is not None:
        if hasattr(me, 'use_auto_smooth'):                    # Blender < 4.1
            me.use_auto_smooth = True
        me.normals_split_custom_set_from_vertices([tuple(n) for n in np.asarray(N, float)])
    if material is not None:
        me.materials.append(material)
    ob = bpy.data.objects.new(name, me)
    if link:
        bpy.context.scene.collection.objects.link(ob)
    return ob, meta


def normals_proxy(path, name):
    """a hidden copy of a saved part carrying its envelope normals as custom normals, for transfer_normals()."""
    ob, _ = load_part(path, name, normals='envelope')
    ob.hide_render = True
    ob.hide_viewport = True
    return ob


SET_NORMALS_GROUP = 'ck_set_normals'
SET_NORMALS_ATTR = 'ck_vn'


def set_normals(ob, N, name='volume_normals'):
    """custom normals onto `ob`, exactly one per vertex: N (the mesh's vertices in order) kept as a point attribute and set
    by a Geometry Nodes modifier (Set Mesh Normal in tangent space: they follow an armature after it, as custom normals
    do). Add it after an inverted-hull outline (Solidify), as transfer_normals: the Solidify copies the attribute to the
    hull's vertices, so the surface's corners get their own vertex's normal and the hull's its source vertex's.
    transfer_normals maps by position, which can't tell apart vertices that coincide or lie within the outline's inward
    move of each other: a hair lock's inner and outer surfaces meet at its edges (on the Clawd hair's side locks 210
    vertices coincide with a twin whose normal differs by 7.6 degrees (median)), and 400 of a side lock's 5,280
    vertices took a neighbour's normal (up to 12.7 degrees off), which any sub-millimetre change to the hair re-seeds
    (face round 4: the crown's skin moved the side locks <= 0.3 mm and art_terminator_hair's front 8.90 -> 9.55 kinks
    per L, all of it these corners). Here: 0.003 degrees mean, 0.35 at most (Blender 5.2). -> the modifier, or None
    where Blender has no Set Mesh Normal node (the caller falls back to transfer_normals)."""
    import bpy
    if not hasattr(bpy.types, 'GeometryNodeSetMeshNormal'):
        return None
    N = np.asarray(N, np.float32)
    if N.shape != (len(ob.data.vertices), 3):
        raise ValueError('set_normals: %s normals for %d vertices' % (N.shape, len(ob.data.vertices)))
    at = ob.data.attributes.get(SET_NORMALS_ATTR) or ob.data.attributes.new(SET_NORMALS_ATTR, 'FLOAT_VECTOR', 'POINT')
    at.data.foreach_set('vector', N.ravel())
    ng = bpy.data.node_groups.get(SET_NORMALS_GROUP)
    if ng is None:
        ng = bpy.data.node_groups.new(SET_NORMALS_GROUP, 'GeometryNodeTree')
        ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
        gi, go = ng.nodes.new('NodeGroupInput'), ng.nodes.new('NodeGroupOutput')
        sn = ng.nodes.new('GeometryNodeSetMeshNormal')
        sn.mode = 'TANGENT_SPACE'
        sn.domain = 'POINT'
        na = ng.nodes.new('GeometryNodeInputNamedAttribute')
        na.data_type = 'FLOAT_VECTOR'
        na.inputs['Name'].default_value = SET_NORMALS_ATTR
        ng.links.new(gi.outputs[0], sn.inputs['Mesh'])
        ng.links.new(na.outputs['Attribute'], sn.inputs['Custom Normal'])
        ng.links.new(sn.outputs[0], go.inputs[0])
    md = ob.modifiers.new(name, 'NODES')
    md.node_group = ng
    return md


def transfer_normals(ob, proxy, name='volume_normals', mapping='NEAREST_NORMAL'):
    """custom normals onto `ob` from `proxy` (the same surface) by a Data Transfer modifier. Add it after an
    inverted-hull outline (Solidify): Solidify re-derives the surface's corner normals and loses custom ones set on the
    mesh itself (measured on the Clawd hair: mean 2 degrees off, 1 % of corners over 24 degrees). A transfer after it
    keeps them: with 'NEAREST_NORMAL' (the default) they come out 0.02 degrees off on average, 0.08 at the 99th
    percentile, in 0.24 s per evaluation of a 100 k-face part. 'POLYINTERP_NEAREST' is 0.08 / 0.9 degrees and takes twice
    as long."""
    dt = ob.modifiers.new(name, 'DATA_TRANSFER')
    dt.object = proxy
    dt.use_loop_data = True
    dt.data_types_loops = {'CUSTOM_NORMAL'}
    dt.loop_mapping = mapping
    return dt
