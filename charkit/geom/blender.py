"""The Blender side of charkit.geom: numpy + bpy only (no scipy / numba), so it runs in Blender's bundled Python.

    ob, meta = load_part('charkit/out/geom/clawd/hair.npz', 'hair_geom')    # a mesh object in world space

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
