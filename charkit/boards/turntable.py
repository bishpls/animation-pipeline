"""Board: a built character turned round, from its saved scene (a build without --no-blend), in the boards' own look
and cameras (scene.boards, qa.render_view: the style's look is stored in the scene, so each view gets its light and line
widths as the boards do): the full body (orthographic, as the body board) and the face (85 mm, as the face board, the
eyes and brows drawn through the fringe) at n azimuths each. Looping GIFs of each: gifs(), from the venv (Blender's
Python has no PIL).

    blender -b OUT/NAME.blend --python charkit/boards/turntable.py -- OUTDIR [--n 24] [--look JSON] [--only face|body]
        --look: a look laid over the scene's (charkit.styles' look section, e.g. '{"light": {"mode": "world"}}')
    python charkit/boards/turntable.py --gifs OUTDIR
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import numpy as np

FEATURES = ('sclera_', 'iris_', 'lash_', 'brow_')


def main(out, n=24, look=None, only=None):
    import bpy
    from charkit import qa, shade, styles
    os.makedirs(out, exist_ok=True)
    sc = bpy.context.scene
    if look:
        shade.set_look(styles.merge(shade.get_look(), look))
        shade.line_colors()
    skin = next(o for o in bpy.data.objects if o.type == 'MESH' and o.name.endswith('_skin'))
    zs = np.array([(skin.matrix_world @ v.co).z for v in skin.data.vertices])
    H = float(zs.max())
    irises = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('iris_')]
    eye_z = float(np.mean([(o.matrix_world @ v.co).z for o in irises for v in o.data.vertices])) if irises else 0.9 * H
    L = H / 5.9
    feats = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith(FEATURES) and not o.hide_render]
    covers = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('hair_') and not o.hide_render]
    cam = bpy.data.objects.get('board_cam')
    if cam is None:
        cam = bpy.data.objects.new('board_cam', bpy.data.cameras.new('board_cam'))
        sc.collection.objects.link(cam)
    sc.camera = cam
    frames = {'body': [], 'face': []}
    for i in range(n):
        az = 360.0 * i / n
        if only in (None, 'body'):
            sc.render.resolution_x, sc.render.resolution_y = 540, 900
            p = os.path.join(out, 'body_%03d.png' % i)
            qa.render_view(cam, (0, 0, H * 0.52), az, 6.0, 0.0, p, ortho=H * 1.12)
            frames['body'].append(p)
        if only in (None, 'face'):
            sc.render.resolution_x, sc.render.resolution_y = 700, 700
            p = os.path.join(out, 'face_%03d.png' % i)
            qa.render_view(cam, (0, 0, eye_z + 0.06 * L), az, 1.0, 0.0, p, lens=85)
            if covers and feats:
                qa.features_through(p, feats, covers, [skin])
            frames['face'].append(p)
    shade.set_view(0)
    json.dump({k: [os.path.basename(p) for p in v] for k, v in frames.items()}, open(os.path.join(out, 'frames.json'), 'w'))
    return frames


def gifs(out, ms=120):
    from PIL import Image
    fr = json.load(open(os.path.join(out, 'frames.json')))
    for k, ps in fr.items():
        if not ps:
            continue
        ims = [Image.open(os.path.join(out, p)).convert('RGB') for p in ps]
        ims[0].save(os.path.join(out, 'turntable_%s.gif' % k), save_all=True, append_images=ims[1:], duration=ms, loop=0)
        w, h = ims[0].size
        strip = Image.new('RGB', (w // 3 * min(8, len(ims)), h // 3), (240, 240, 244))
        for j, im in enumerate(ims[::max(1, len(ims) // 8)][:8]):
            strip.paste(im.resize((w // 3, h // 3)), (j * (w // 3), 0))
        strip.save(os.path.join(out, 'strip_%s.png' % k))


if __name__ == '__main__':
    if '--gifs' in sys.argv:
        gifs(sys.argv[sys.argv.index('--gifs') + 1])
    else:
        argv = sys.argv[sys.argv.index('--') + 1:]
        opt = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d
        main(argv[0], int(opt('--n', 24)), json.loads(opt('--look')) if opt('--look') else None, opt('--only'))
