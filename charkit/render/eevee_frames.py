"""EEVEE's pictures of the QA's measuring frames (Blender side; charkit/render/qaref.py writes the list and reads them):
the reference the QA's two drawings (charkit.qa3d's numpy one, charkit.render's) are measured against, each frame as the
QA frames it: its orthographic window, its light, each object's outline at its build width or off.

    blender -b BUILD/NAME.blend --python charkit/render/eevee_frames.py -- FRAMES.json

FRAMES.json: {"frames": [{"path": PNG, "az": deg, "origin": [u, z], "pix": m, "win": {"x", "top", "bottom"} (m),
"light": [x, y, z] (world, toward the key), "off": [objects drawn without their outline], "transparent": bool,
"streaks": bool, "point": bool}]}. point: one sample at each pixel's centre and no film filter (the measuring grid's
samples, as the QA's buffers are); else the boards' film (64 samples, the 1.5 px filter). No dither (the boards' 1 level
of it on flat tones reads as tone edges to the QA's percentile cuts).
"""
import json, math, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main(path):
    import bpy
    from mathutils import Vector
    from charkit import shade
    job = json.load(open(path))
    sc = bpy.context.scene
    r = sc.render
    cam = bpy.data.objects.get('qa_frames_cam')
    if cam is None:
        cam = bpy.data.objects.new('qa_frames_cam', bpy.data.cameras.new('qa_frames_cam'))
        sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.type = 'ORTHO'
    cam.data.clip_start, cam.data.clip_end = 0.5, 20.0
    outlines = {}
    for ob in bpy.data.objects:
        mod = next((m for m in ob.modifiers if m.type == 'SOLIDIFY' and m.name == 'outline'), None)
        if mod is not None:
            outlines[ob.name] = (ob, mod)
    amounts = [n for m in bpy.data.materials if m.node_tree for n in m.node_tree.nodes if n.name == 'ck_hl_amount']
    amount0 = {id(n): n.inputs[1].default_value for n in amounts}
    look = shade.get_look()
    for F in job['frames']:
        W = int(round(2 * F['win']['x'] / F['pix']))
        H = int(round((F['win']['top'] - F['win']['bottom']) / F['pix']))
        r.resolution_x, r.resolution_y, r.resolution_percentage = W, H, 100
        a = math.radians(F['az'])
        rb = Vector((math.cos(a), math.sin(a), 0.0))
        db = Vector((-math.sin(a), math.cos(a), 0.0))
        uc = F['origin'][0] - F['win']['x'] + W * F['pix'] / 2
        zc = F['origin'][1] + F['win']['top'] - H * F['pix'] / 2
        cam.location = rb * uc + Vector((0, 0, zc)) - db * 5.0
        cam.rotation_mode = 'QUATERNION'
        cam.rotation_quaternion = db.to_track_quat('-Z', 'Y')
        cam.data.ortho_scale = max(W, H) * F['pix']
        # the build's line widths, then the frame's own light and outlines
        shade.set_view(F['az'], None, None, look)
        shade.set_light(Vector(F['light']).normalized())
        off = set(F.get('off') or ())
        for name, (ob, mod) in outlines.items():
            mod.show_render = name not in off
        for n in amounts:
            n.inputs[1].default_value = amount0[id(n)] if F.get('streaks', True) else 0.0
        r.film_transparent = bool(F.get('transparent', True))
        r.dither_intensity = 0.0                         # (EEVEE's 8-bit dither: noise a measure on flat tones reads as
                                                         # edges; the boards keep theirs)
        if F.get('point'):
            r.filter_size = 0.0
            sc.eevee.taa_render_samples = 1
        else:
            r.filter_size = 1.5
            sc.eevee.taa_render_samples = 64
        r.image_settings.file_format = 'PNG'
        r.image_settings.color_mode = 'RGBA'
        r.image_settings.color_depth = '8'
        r.filepath = F['path']
        bpy.ops.render.render(write_still=True)
        print('EEVEE_FRAME', F['path'], W, H, flush=True)
    for n in amounts:
        n.inputs[1].default_value = amount0[id(n)]


if __name__ == '__main__':
    main(sys.argv[sys.argv.index('--') + 1])
