"""geom.blender.set_normals (face round 4): a hair piece's envelope normals exact per vertex under its outline, where the
proxy transfer (transfer_normals, by position) can't tell coincident vertices apart. On a stand-in with a known answer,
in Blender: two sheets whose edges coincide vertex for vertex (a lock's inner and outer surfaces meeting at its edge),
each with its own normals (the twins 8 degrees apart), outlined as the hair is (shade.outline, the inverted hull):
- the transfer gives some edge corners their twin's normal (degrees off);
- set_normals gives every surface corner its own vertex's normal (well under a degree), and they follow a posed bone.
Runs itself in Blender (venv: run this file, or pytest; skipped without Blender).
"""
import os, subprocess, sys

BLENDER = os.environ.get('BLENDER', '/Applications/Blender.app/Contents/MacOS/Blender')
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _in_blender():
    sys.path.insert(0, ROOT)
    import math
    import bpy
    import numpy as np
    from charkit import shade
    from charkit.geom.blender import set_normals, transfer_normals
    bpy.ops.wm.read_factory_settings(use_empty=True)
    # two 5 x 2 cm sheets, bowed apart in the middle and meeting along their long edges (vertex for vertex, not merged)
    nx, ny = 26, 9
    xs, ys = np.linspace(-0.025, 0.025, nx), np.linspace(-0.01, 0.01, ny)
    X, Y = np.meshgrid(xs, ys, indexing='ij')
    bow = 0.002 * (1 - (Y / 0.01) ** 2)
    top = np.stack([X, Y, bow], -1).reshape(-1, 3)
    bot = np.stack([X, Y, -bow], -1).reshape(-1, 3)
    V = np.concatenate([top, bot])
    n = nx * ny
    F = []
    for i in range(nx - 1):
        for j in range(ny - 1):
            a, b, c, d = i * ny + j, (i + 1) * ny + j, (i + 1) * ny + j + 1, i * ny + j + 1
            F += [(a, b, c), (a, c, d), (n + a, n + c, n + b), (n + a, n + d, n + c)]
    t = math.radians(4.0)                        # each sheet's normals tilted 4 degrees its own way: twins 8 apart
    N = np.concatenate([np.tile([math.sin(t), 0.0, math.cos(t)], (n, 1)), np.tile([-math.sin(t), 0.0, -math.cos(t)], (n, 1))])

    def mesh(name, custom=None):
        me = bpy.data.meshes.new(name)
        me.from_pydata(V.tolist(), [], F)
        me.shade_smooth()
        if custom is not None:
            me.normals_split_custom_set_from_vertices([tuple(v) for v in custom])
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        return ob

    def surface_error(ob, R=np.eye(3)):
        """degrees between each surface corner's normal (the outline's hull left out) and its vertex's N (rotated R)."""
        oe = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
        me = oe.to_mesh()
        cn = np.empty(len(me.loops) * 3, np.float32); me.corner_normals.foreach_get('vector', cn)
        lv = np.empty(len(me.loops), np.int64); me.loops.foreach_get('vertex_index', lv)
        oe.to_mesh_clear()
        nl = 3 * len(F)
        cn, lv = cn.reshape(-1, 3)[:nl], lv[:nl]
        want = N[lv] @ R.T
        return np.degrees(np.arccos(np.clip((cn * want).sum(1) / np.linalg.norm(cn, axis=1), -1, 1)))

    proxy = mesh('proxy', N)
    moved = mesh('transfer')
    shade.outline(moved, thick=0.0014, name='hair_line')
    transfer_normals(moved, proxy)
    e_t = surface_error(moved)
    exact = mesh('exact')
    shade.outline(exact, thick=0.0014, name='hair_line')
    md = set_normals(exact, N)
    assert md is not None, 'no Set Mesh Normal node in this Blender'
    e_s = surface_error(exact)
    print('TRANSFER mean %.3f max %.2f over 3 deg %d; SET mean %.4f max %.3f' % (e_t.mean(), e_t.max(), (e_t > 3).sum(),
                                                                                  e_s.mean(), e_s.max()))
    assert e_t.max() > 3.0, e_t.max()             # (the transfer's twins: the known-bad case)
    assert e_s.max() < 0.5, e_s.max()
    # an armature after it (character._to_head): the normals follow a posed bone
    ad = bpy.data.armatures.new('arm'); arm = bpy.data.objects.new('arm', ad)
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    b = ad.edit_bones.new('head'); b.head = (0, 0, 0); b.tail = (0, 0, 0.1)
    bpy.ops.object.mode_set(mode='OBJECT')
    exact.parent = arm
    g = exact.vertex_groups.new(name='head'); g.add(list(range(len(V))), 1.0, 'REPLACE')
    exact.modifiers.new('rig', 'ARMATURE').object = arm
    pb = arm.pose.bones['head']; pb.rotation_mode = 'XYZ'; pb.rotation_euler = (0.0, 0.0, math.radians(30))
    bpy.context.view_layer.update()
    R = np.array((arm.matrix_world @ pb.matrix @ pb.bone.matrix_local.inverted()).to_3x3())
    e_p = surface_error(exact, R)
    print('POSED mean %.4f max %.3f' % (e_p.mean(), e_p.max()))
    assert e_p.max() < 0.5, e_p.max()
    print('CHARKIT_TEST_OK')


def test_set_normals_exact_under_the_outline():
    if not os.path.exists(BLENDER):
        print('skip: no Blender'); return
    r = subprocess.run([BLENDER, '-b', '--factory-startup', '--python', os.path.abspath(__file__)], capture_output=True,
                       text=True, timeout=300)
    assert 'CHARKIT_TEST_OK' in r.stdout, (r.stdout + r.stderr)[-3000:]
    print([x for x in r.stdout.splitlines() if x.startswith('TRANSFER')][0])


if __name__ == '__main__':
    if 'bpy' in sys.modules:
        _in_blender()
    else:
        test_set_normals_exact_under_the_outline(); print('ok')
