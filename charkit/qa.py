"""Review boards for charkit (docs/CHARKIT.md §4): orthographic and perspective views of a character or a lineup, rendered
with a neutral clay or the character's own materials, composed into one image.
    from charkit import qa; qa.lineup([objs...], out_png, views=('front','side','three_q'))
"""
import collections, contextlib, math, os
import numpy as np


def clay(name='clay', color=(0.72, 0.70, 0.74)):
    """a soft two-light clay (Blender's diffuse, EEVEE) for judging form, not the look."""
    import bpy
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    if b:
        b.inputs['Base Color'].default_value = (*color, 1)
        b.inputs['Roughness'].default_value = 0.6
    return m


def studio():
    """a three-point light rig and a neutral world for the clay boards."""
    import bpy
    from mathutils import Vector
    for name, loc, energy in (('key', (2.5, -3.0, 3.5), 900), ('fill', (-3.0, -2.0, 2.0), 350), ('rim', (0.0, 3.5, 3.0), 600)):
        ld = bpy.data.lights.new(name, 'AREA'); ld.energy = energy; ld.size = 2.0
        lo = bpy.data.objects.new(name, ld); lo.location = loc
        bpy.context.scene.collection.objects.link(lo)
        d = (Vector((0, 0, 0.9)) - Vector(loc)).normalized()
        lo.rotation_mode = 'QUATERNION'; lo.rotation_quaternion = d.to_track_quat('-Z', 'Y')
    w = bpy.context.scene.world or bpy.data.worlds.new('w'); bpy.context.scene.world = w
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.32, 0.33, 0.36, 1)
    w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.6


def render_view(cam, target, az, dist, height, path, lens=50, ortho=None):
    """a still from azimuth az (degrees, 0 in front of her), `dist` out and `height` up from the target, in the style's
    look for that view (charkit.shade.set_view: its light, and its outlines' width at this view's scale)."""
    import bpy
    from mathutils import Vector
    from . import shade
    a = math.radians(az)
    eye = Vector(target) + Vector((math.sin(a) * dist, -math.cos(a) * dist, height))
    d = (Vector(target) - eye).normalized()
    cam.location = eye; cam.rotation_mode = 'QUATERNION'; cam.rotation_quaternion = d.to_track_quat('-Z', 'Y')
    r = bpy.context.scene.render
    big = max(r.resolution_x, r.resolution_y)
    if ortho:
        cam.data.type = 'ORTHO'; cam.data.ortho_scale = ortho
        m_per_px = ortho / big
    else:
        cam.data.type = 'PERSP'; cam.data.lens = lens
        m_per_px = (Vector(target) - eye).length * cam.data.sensor_width / lens / big
    shade.set_view(az, m_per_px, r.resolution_y)
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


# a view for render_views: render_view's arguments, plus the state it's rendered in (a function setting it, such as an
# expression or a mouth shape), applied before the camera
View = collections.namedtuple('View', 'target az dist height path lens ortho state', defaults=(50, None, None))


def _aim(cam, v):
    """the camera where render_view puts it for View v. -> the view's metres per pixel at the target."""
    import bpy
    from mathutils import Vector
    a = math.radians(v.az)
    eye = Vector(v.target) + Vector((math.sin(a) * v.dist, -math.cos(a) * v.dist, v.height))
    d = (Vector(v.target) - eye).normalized()
    cam.location = eye; cam.rotation_mode = 'QUATERNION'; cam.rotation_quaternion = d.to_track_quat('-Z', 'Y')
    r = bpy.context.scene.render
    big = max(r.resolution_x, r.resolution_y)
    if v.ortho:
        cam.data.type = 'ORTHO'; cam.data.ortho_scale = v.ortho
        return v.ortho / big
    cam.data.type = 'PERSP'; cam.data.lens = v.lens
    return (Vector(v.target) - eye).length * cam.data.sensor_width / v.lens / big


def _scale(cam, v):
    """View v's camera type and metres per pixel, without moving the camera: consecutive views sharing them render as
    one batch (a per-view hook's line widths then hold within it)."""
    import bpy
    r = bpy.context.scene.render
    big = max(r.resolution_x, r.resolution_y)
    if v.ortho:
        return 'ORTHO', round(v.ortho / big, 12)
    return 'PERSP', round(math.hypot(v.dist, v.height) * cam.data.sensor_width / v.lens / big, 12)


def _static(sc):
    """nothing in the file changes with the frame: no action or NLA on any datablock, no driver reading the frame, no
    motion blur. An animation render's frames are then stills of what each frame's handler set (else render_views
    renders stills)."""
    import bpy
    if sc.render.use_motion_blur:
        return False
    ids = [sc, sc.world] + list(bpy.data.objects) + list(bpy.data.meshes) + list(bpy.data.shape_keys) + \
        list(bpy.data.cameras) + list(bpy.data.lights) + list(bpy.data.armatures) + list(bpy.data.node_groups) + \
        [m for m in bpy.data.materials] + [m.node_tree for m in bpy.data.materials if m.node_tree] + \
        ([sc.world.node_tree] if sc.world and sc.world.node_tree else [])
    for i in ids:
        ad = getattr(i, 'animation_data', None) if i is not None else None
        if ad is None:
            continue
        if ad.action or len(ad.nla_tracks) or any('frame' in (f.driver.expression or '') for f in ad.drivers):
            return False
    return True


def _animate(cam, views, paths, view=None):
    """views rendered as the frames of one animation, into paths. Each frame's state, camera and hook are set by a
    frame_change_pre handler, so the render's depsgraph re-evaluates only what they change (a still re-evaluates every
    modifier in the file). -> False, with nothing written, if the handler didn't set every frame."""
    import bpy
    sc = bpy.context.scene; r = sc.render
    res_y = r.resolution_y

    def frame(i):
        v = views[i]
        if v.state:
            v.state()
        m = _aim(cam, v)
        if view is not None:
            view(v.az, m, res_y)
    done = [0]

    def pre(scene, depsgraph=None):
        i = scene.frame_current - 1
        if i == len(done) and i < len(views):   # each frame once, in order: not the return to the scene's frame after
            frame(i); done.append(i)
    saved = (sc.frame_start, sc.frame_end, sc.frame_step, r.filepath, r.use_overwrite, r.use_placeholder)
    tmp = os.path.join(os.path.dirname(os.path.abspath(paths[0])), '.frames_%d_####' % os.getpid())
    bpy.app.handlers.frame_change_pre.append(pre)
    try:
        sc.frame_start, sc.frame_end, sc.frame_step = 1, len(views), 1
        r.use_overwrite, r.use_placeholder = True, False
        frame(0)
        r.filepath = tmp
        files = [r.frame_path(frame=i + 1) for i in range(len(views))]
        bpy.ops.render.render(animation=True)
    finally:
        bpy.app.handlers.frame_change_pre.remove(pre)
        sc.frame_start, sc.frame_end, sc.frame_step, r.filepath, r.use_overwrite, r.use_placeholder = saved
    if len(done) != len(views):
        for f in files:
            if os.path.exists(f):
                os.remove(f)
        return False
    for f, p in zip(files, paths):
        os.replace(f, p)
    return True


def render_views(cam, views, view=None, features=None):
    """render Views (render_view's pictures), consecutive ones sharing a camera type and scale as one animation render.
    A still re-evaluates every modifier in the file (for Clawd ~2 s a frame); an animation's later frames re-evaluate
    only what changed (the camera, a state's shape keys): 0.5 s. The frames match stills bit for bit.
    view: the per-view hook f(az, m_per_px, res_y) that render_view applies to its stills (charkit.shade.set_view, the
    look's light and line widths), applied here to batched frames from a frame handler. It must leave values it doesn't
    change unwritten: any write re-evaluates that object on the next frame.
    features: (feature_objs, hide_objs, holdout_objs), features_through on every view, as a second batch.
    -> the paths."""
    import bpy
    from . import trace
    sc = bpy.context.scene
    views = [v if isinstance(v, View) else View(*v) for v in views]
    groups = []
    for v in views:
        k = _scale(cam, v)
        if groups and groups[-1][0] == k:
            groups[-1][1].append(v)
        else:
            groups.append((k, [v]))
    batch = _static(sc)
    for _, g in groups:
        paths = [v.path for v in g]
        if batch and len(g) > 1:
            with trace.span('board_batch', n=len(g), first=os.path.basename(paths[0])) as rec:
                ok = _animate(cam, g, paths, view)
                if ok and features:
                    tmps = [p[:-4] + '_feat.png' for p in paths]
                    with features_pass(features[0], features[2]):
                        ok = _animate(cam, g, tmps, view)
                    if ok:
                        for p, t in zip(paths, tmps):
                            features_blend(p, t)
                rec['batched'] = ok
            if ok:
                continue
            print('render_views: frame handler missed frames; rendering %d stills' % len(g))
        for v in g:
            with trace.span('board', path=os.path.basename(v.path)):
                if v.state:
                    v.state()
                render_view(cam, v.target, v.az, v.dist, v.height, v.path, lens=v.lens, ortho=v.ortho)
                if features:
                    features_through(v.path, *features)
    return [v.path for v in views]


def sheet(paths, out, cols, cell=(360, 640), labels=None):
    from PIL import Image, ImageDraw
    rows = math.ceil(len(paths) / cols)
    S = Image.new('RGB', (cols * cell[0], rows * cell[1]), (40, 40, 44))
    d = ImageDraw.Draw(S)
    for i, p in enumerate(paths):
        im = Image.open(p).convert('RGB').resize(cell)
        S.paste(im, ((i % cols) * cell[0], (i // cols) * cell[1]))
        if labels:
            d.text(((i % cols) * cell[0] + 8, (i // cols) * cell[1] + 6), labels[i], fill=(240, 240, 240))
    S.save(out)
    return out


def features_through(path, feature_objs, hide_objs, holdout_objs, amount=0.55):
    """anime eyes and brows through the hair: re-render only the features (the skin as a holdout, so it still hides what it
    should; the hair hidden), then lay them over the saved image at `amount` (where the features were visible anyway the
    two agree, so only the hair-covered parts change)."""
    import bpy
    sc = bpy.context.scene
    tmp = path[:-4] + '_feat.png'
    with features_pass(feature_objs, holdout_objs):
        sc.render.filepath = tmp
        bpy.ops.render.render(write_still=True)
    features_blend(path, tmp, amount)


@contextlib.contextmanager
def features_pass(feature_objs, holdout_objs):
    """the scene as features_through's second render sees it: only the features and the holdouts (a holdout material,
    their outlines off), on a transparent film; all restored after."""
    import bpy
    sc = bpy.context.scene
    hold = bpy.data.materials.get('holdout')
    if hold is None:
        hold = bpy.data.materials.new('holdout'); hold.use_nodes = True
        nt = hold.node_tree
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        o = nt.nodes.new('ShaderNodeOutputMaterial'); h = nt.nodes.new('ShaderNodeHoldout')
        nt.links.new(h.outputs[0], o.inputs['Surface'])
    saved_mats = {ob.name: [s_.material for s_ in ob.material_slots] for ob in holdout_objs}
    feat = set(ob.name for ob in feature_objs)
    others = [ob for ob in sc.objects if ob.type == 'MESH' and ob.name not in feat and ob not in holdout_objs]
    saved_other = {ob.name: ob.hide_render for ob in others}
    mods = {}
    film = sc.render.film_transparent
    try:
        for ob in holdout_objs:
            for s_ in ob.material_slots:
                s_.material = hold
            for m in ob.modifiers:
                if m.type == 'SOLIDIFY':
                    mods[(ob.name, m.name)] = m.show_render; m.show_render = False
        for ob in others:
            ob.hide_render = True
        sc.render.film_transparent = True
        yield
    finally:
        sc.render.film_transparent = film
        for ob in holdout_objs:
            for s_, m in zip(ob.material_slots, saved_mats[ob.name]):
                s_.material = m
            for m in ob.modifiers:
                if (ob.name, m.name) in mods:
                    m.show_render = mods[(ob.name, m.name)]
        for ob in others:
            ob.hide_render = saved_other[ob.name]


def features_blend(path, tmp, amount=0.55):
    """the features pass (tmp, removed after) laid over the picture at path, at `amount` of its alpha."""
    import bpy
    a = bpy.data.images.load(path); b = bpy.data.images.load(tmp)
    w, h = a.size
    A = np.array(a.pixels[:], dtype=np.float32).reshape(h, w, 4)
    Bf = np.array(b.pixels[:], dtype=np.float32).reshape(h, w, 4)
    k = (amount * Bf[..., 3:4])
    A[..., :3] = A[..., :3] * (1 - k) + Bf[..., :3] * k
    a.pixels.foreach_set(A.ravel())
    a.filepath_raw = path; a.file_format = 'PNG'; a.save()
    bpy.data.images.remove(a); bpy.data.images.remove(b)
    os.remove(tmp)
