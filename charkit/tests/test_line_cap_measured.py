"""shade.outline's cap='measured' (Michael's call M: the bow and the boots, closed thin pieces without a shell modifier,
get the outline's inward move capped at half their measured thickness). On stand-ins with known answers, in Blender:
- a closed slab 4 mm thick measures 4 mm (its p5 vertex thickness), so its cap is 2 mm, and a wide line's offset sends
  the rest of the width outward (line_offset);
- a thin lens (an ellipsoid 6 mm thick at its middle) at the body boards' width: without the cap its surface moves
  inward past its own thickness and faces turn over (the flips look.md counts); with the measured cap fewer do;
- a closed piece outlined without cap='measured' (the crab, the star) stays uncapped, and a shell keeps its shell's cap.
Runs itself in Blender (venv: run this file, or pytest; skipped without Blender).
"""
import os, subprocess, sys

BLENDER = os.environ.get('BLENDER', '/Applications/Blender.app/Contents/MacOS/Blender')
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
W_BODY = 0.0036171               # the body boards' line width at Clawd's height (look.md round 3), m


def _in_blender():
    sys.path.insert(0, ROOT)
    import bmesh, bpy
    import numpy as np
    from charkit import shade
    bpy.ops.wm.read_factory_settings(use_empty=True)

    def closed(name, make):
        me = bpy.data.meshes.new(name)
        bm = bmesh.new(); make(bm); bm.to_mesh(me); bm.free()
        ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
        return ob

    def slab(bm):
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=7, use_grid_fill=True)
        bmesh.ops.scale(bm, vec=(0.06, 0.06, 0.004), verts=bm.verts[:])

    def lens(bm):
        bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=24, radius=0.5)
        bmesh.ops.scale(bm, vec=(0.06, 0.06, 0.006), verts=bm.verts[:])

    def faces_turned(ob, w, cap):
        """faces whose normal turns over (dot < 0) with the outline at width w and inward move min(w, cap)."""
        mod = ob.modifiers['outline']
        mod.show_viewport = False
        bpy.context.view_layer.update()
        me = ob.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
        n0 = np.array([tuple(p.normal) for p in me.polygons]); nf = len(n0)
        ob.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh_clear()
        mod.show_viewport = True
        mod.thickness = -w; mod.offset = shade.line_offset(w, cap)
        bpy.context.view_layer.update()
        oe = ob.evaluated_get(bpy.context.evaluated_depsgraph_get()); me = oe.to_mesh()
        n1 = np.array([tuple(p.normal) for p in me.polygons][:nf])
        oe.to_mesh_clear()
        return int((np.einsum('ij,ij->i', n0, n1) < 0).sum())

    # the slab: 4 mm measured, a 2 mm cap, the rest of a wide line outward
    s = closed('slab', slab)
    shade.outline(s, thick=0.0012, name='garment_line', cap='measured')
    assert abs(s['ck_line_thick'] - 0.004) <= 2e-6, s['ck_line_thick']
    assert abs(shade.line_cap(s) - 0.002) <= 1e-6, shade.line_cap(s)
    o = shade.line_offset(W_BODY, shade.line_cap(s))
    assert abs(W_BODY * (1 + o) / 2 - shade.line_cap(s)) < 1e-9 and o < 1
    assert s.modifiers['outline'].offset == 1.0                 # at the build width (1.2 mm < 2 mm) nothing changes

    # the lens: the cap turns fewer faces over at the body boards' width
    ln = closed('lens', lens)
    ln.modifiers.new('sub', 'SUBSURF').levels = 1
    shade.outline(ln, thick=0.0012, name='garment_line', cap='measured')
    t = ln['ck_line_thick']
    assert 0 < t <= 0.006, t
    uncapped, capped = faces_turned(ln, W_BODY, None), faces_turned(ln, W_BODY, shade.line_cap(ln))
    print('LENS thickness %.3f mm, faces turned: uncapped %d, capped %d' % (t * 1e3, uncapped, capped))
    assert uncapped > 0 and capped < uncapped, (uncapped, capped)

    # no cap asked (the crab, the star): uncapped; a shell: its shell's cap
    c = closed('crab', lens)
    shade.outline(c, thick=0.001, name='crab_line')
    assert 'ck_line_cap' not in c and shade.line_cap(c) is None
    g = closed('sleeve', slab)
    sol = g.modifiers.new('thick', 'SOLIDIFY'); sol.thickness = 0.002; sol.offset = -1
    shade.outline(g, thick=0.0012, name='garment_line', cap='measured')
    assert abs(shade.line_cap(g) - 0.001) < 1e-9 and 'ck_line_thick' not in g
    try:
        shade.outline(closed('x', slab), cap='half')
        raise AssertionError('an unknown cap was accepted')
    except ValueError:
        pass
    print('CHARKIT_TEST_OK')


def test_line_cap_measured():
    if not os.path.exists(BLENDER):
        print('skip: no Blender'); return
    r = subprocess.run([BLENDER, '-b', '--factory-startup', '--python', os.path.abspath(__file__)], capture_output=True,
                       text=True, timeout=300)
    assert 'CHARKIT_TEST_OK' in r.stdout, (r.stdout + r.stderr)[-3000:]
    print([x for x in r.stdout.splitlines() if x.startswith('LENS')][0])


if __name__ == '__main__':
    if 'bpy' in sys.modules:
        _in_blender()
    else:
        test_line_cap_measured(); print('ok')
