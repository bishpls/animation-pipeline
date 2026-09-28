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
    import bpy
    from mathutils import Vector
    a = math.radians(az)
    eye = Vector(target) + Vector((math.sin(a) * dist, -math.cos(a) * dist, height))
    d = (Vector(target) - eye).normalized()
    cam.location = eye; cam.rotation_mode = 'QUATERNION'; cam.rotation_quaternion = d.to_track_quat('-Z', 'Y')
    if ortho:
        cam.data.type = 'ORTHO'; cam.data.ortho_scale = ortho
    else:
        cam.data.type = 'PERSP'; cam.data.lens = lens
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
