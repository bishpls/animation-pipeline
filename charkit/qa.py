"""Review boards for charkit (docs/CHARKIT.md §4): orthographic and perspective views of a character or a lineup, rendered
with a neutral clay or the character's own materials, composed into one image.
    from charkit import qa; qa.lineup([objs...], out_png, views=('front','side','three_q'))
"""
import math, os
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
    hold = bpy.data.materials.get('holdout')
    if hold is None:
        hold = bpy.data.materials.new('holdout'); hold.use_nodes = True
        nt = hold.node_tree
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        o = nt.nodes.new('ShaderNodeOutputMaterial'); h = nt.nodes.new('ShaderNodeHoldout')
        nt.links.new(h.outputs[0], o.inputs['Surface'])
    saved_mats = {ob.name: [s_.material for s_ in ob.material_slots] for ob in holdout_objs}
    saved_hide = {ob.name: ob.hide_render for ob in hide_objs}
    feat = set(ob.name for ob in feature_objs)
    others = [ob for ob in sc.objects if ob.type == 'MESH' and ob.name not in feat and ob not in holdout_objs]
    saved_other = {ob.name: ob.hide_render for ob in others}
    mods = {}
    try:
        for ob in holdout_objs:
            for s_ in ob.material_slots:
                s_.material = hold
            for m in ob.modifiers:
                if m.type == 'SOLIDIFY':
                    mods[(ob.name, m.name)] = m.show_render; m.show_render = False
        for ob in others:
            ob.hide_render = True
        film = sc.render.film_transparent
        sc.render.film_transparent = True
        tmp = path[:-4] + '_feat.png'
        sc.render.filepath = tmp
        bpy.ops.render.render(write_still=True)
        sc.render.film_transparent = film
    finally:
        for ob in holdout_objs:
            for s_, m in zip(ob.material_slots, saved_mats[ob.name]):
                s_.material = m
            for m in ob.modifiers:
                if (ob.name, m.name) in mods:
                    m.show_render = mods[(ob.name, m.name)]
        for ob in others:
            ob.hide_render = saved_other[ob.name]
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
