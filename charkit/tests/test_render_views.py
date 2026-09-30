"""qa.render_views: a set of views rendered as one animation render gives the same pixels as a still per view (its
still path), with states set per frame and the features pass batched too, and leaves the scene as the still path does:
the state and camera of the last view, the frame, no handler and no stray files. A scene that moves with the frame
renders stills. Runs itself in Blender: EEVEE where the boards render, Cycles on the CPU where nothing can
(CHARKIT_NO_RENDER, the build box), which exercises the same batching.
"""
import functools, os, subprocess, sys, tempfile

BLENDER = os.environ.get('BLENDER', '/Applications/Blender.app/Contents/MacOS/Blender')
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _in_blender():
    sys.path.insert(0, ROOT)
    import bpy
    import numpy as np
    from charkit import qa
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    if os.environ.get('CHARKIT_NO_RENDER') == '1':
        sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = 4; sc.cycles.use_denoising = False
    else:
        sc.render.engine = 'BLENDER_EEVEE'; sc.eevee.taa_render_samples = 4
    sc.render.resolution_x = sc.render.resolution_y = 48
    w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.3, 0.3, 0.35, 1)
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sc.collection.objects.link(sun)
    sun.rotation_euler = (0.6, 0.2, 0.4)

    def mesh(name, size, loc):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=size, location=loc, segments=16, ring_count=8)
        ob = bpy.context.object; ob.name = name
        return ob
    body = mesh('body', 0.5, (0, 0, 0.5))
    body.modifiers.new('sub', 'SUBSURF')
    line = body.modifiers.new('outline', 'SOLIDIFY'); line.thickness = -0.02; line.use_flip_normals = True
    body.shape_key_add(name='Basis')
    for i, k in enumerate(('grin', 'frown')):
        kb = body.shape_key_add(name=k)
        for v in kb.data:
            v.co.z += 0.1 * (i + 1) * v.co.x
    feat = mesh('feat', 0.08, (0.15, -0.55, 0.6))
    cover = mesh('cover', 0.12, (0.15, -0.75, 0.62))
    for ob, c in ((body, (0.8, 0.5, 0.4, 1)), (feat, (0.1, 0.1, 0.6, 1)), (cover, (0.6, 0.6, 0.2, 1))):
        m = bpy.data.materials.new(ob.name); m.diffuse_color = c; ob.data.materials.append(m)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
    sc.frame_set(3)

    def shape(name):
        for kb in body.data.shape_keys.key_blocks[1:]:
            kb.value = 1.0 if kb.name == name else 0.0
    shape(None); body.data.update(); bpy.context.view_layer.update()   # the keys' edited data in effect before any run
    V = qa.View
    handlers = len(bpy.app.handlers.frame_change_pre)

    def run(tag):
        d = os.path.join(tmp, tag); os.makedirs(d)
        qa.render_views(cam, [V((0, 0, 0.5), az, 4.0, 0.3, os.path.join(d, 'turn_%d.png' % az), ortho=1.6)
                              for az in (0, 50, 130)])
        qa.render_views(cam, [V((0, 0, 0.6), 0, 2.0, 0.1, os.path.join(d, 'shape_%s.png' % k), lens=50,
                                state=functools.partial(shape, k)) for k in ('grin', 'frown', None)],
                        features=([feat], [cover], [body]))
        return (d, sorted(os.listdir(d)), tuple(round(x, 6) for x in cam.location), sc.frame_current,
                [kb.value for kb in body.data.shape_keys.key_blocks], len(bpy.app.handlers.frame_change_pre),
                [s_.material.name for s_ in body.material_slots], line.show_render, sc.render.film_transparent)
    tmp = tempfile.mkdtemp()
    static = qa._static
    qa._static = lambda sc_: False                                # the still path: the old per-view loop
    a = run('still')
    a2 = run('still2')
    qa._static = static
    cam.location = (9, 9, 9)                                      # somewhere else: the batch must place it
    b = run('batch')
    assert a[1] == b[1] == sorted(['turn_0.png', 'turn_50.png', 'turn_130.png', 'shape_grin.png', 'shape_frown.png',
                                   'shape_None.png']), (a[1], b[1])
    diffs = {}
    for f in a[1]:
        x, x2, y = (np.array(bpy.data.images.load(os.path.join(p, f)).pixels[:]) for p in (a[0], a2[0], b[0]))
        diffs[f] = (float(np.abs(x - x2).max()), float(np.abs(x - y).max()))
    print('DIFFS', diffs)
    assert all(v == (0.0, 0.0) for v in diffs.values()), diffs
    assert a[2:] == b[2:], (a[2:], b[2:])
    assert b[5] == handlers
    # anything that moves with the frame: stills
    assert qa._static(sc)
    body.keyframe_insert('location', frame=1)
    assert not qa._static(sc)
    print('CHARKIT_TEST_OK')


def test_render_views():
    if not os.path.exists(BLENDER):
        print('skip: no Blender'); return
    r = subprocess.run([BLENDER, '-b', '--factory-startup', '--python', os.path.abspath(__file__)], capture_output=True,
                       text=True, timeout=600)
    assert 'CHARKIT_TEST_OK' in r.stdout, (r.stdout + r.stderr)[-3000:]


if __name__ == '__main__':
    if 'bpy' in sys.modules:
        _in_blender()
    else:
        test_render_views(); print('ok')
