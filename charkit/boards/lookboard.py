"""Board: a built character's head at the design's own scale and angles (head_turnaround: front, three-quarter, profile,
back), orthographic, from its saved scene in its look (qa.render_view: each view's light and line widths), for the look
review page to set beside the design's panels at matching scale. Each view is `ppl` px per L (the design sheet's own,
charkit.lookqa.design_heads' native_ppl), `win` L across and down round the eye line; view.json records where the eye
line and the head's axis land.

    blender -b OUT/NAME.blend --python charkit/boards/lookboard.py -- OUTDIR [--ppl 399.4] [--az3 35.7] [--L 0.25]
        [--look JSON]
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import numpy as np

WIN = (1.6, 1.25, 1.35)            # L: width, above the eye line, below it


def main(out, ppl=399.4, az3=35.7, look=None, L=None):
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
    eye_z = float(np.mean([(o.matrix_world @ v.co).z for o in irises for v in o.data.vertices]))
    L = float(L) if L else H / 5.9                    # (pass the bundle's assembly L: H / 5.9 is approximate)
    feats = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith(('sclera_', 'iris_', 'lash_', 'brow_'))
             and not o.hide_render]
    covers = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('hair_') and not o.hide_render]
    cam = bpy.data.objects.get('board_cam')
    if cam is None:
        cam = bpy.data.objects.new('board_cam', bpy.data.cameras.new('board_cam'))
        sc.collection.objects.link(cam)
    sc.camera = cam
    w, up, down = WIN
    rx, ry = int(round(w * ppl)), int(round((up + down) * ppl))
    sc.render.resolution_x, sc.render.resolution_y = rx, ry
    target = (0.0, 0.0, eye_z + (up - down) / 2 * L)
    views = {}
    for name, az in (('front', 0.0), ('three_quarter', az3), ('profile', 90.0), ('back', 180.0)):
        p = os.path.join(out, '%s.png' % name)
        qa.render_view(cam, target, az, 3.0, 0.0, p, ortho=max(w, up + down) * L)
        if covers and feats and name != 'back':
            qa.features_through(p, feats, covers, [skin])
        views[name] = dict(file=os.path.basename(p), az=az)
    shade.set_view(0)
    json.dump(dict(ppl=ppl, L=L, eye_row=up * ppl, centre_col=rx / 2, views=views), open(os.path.join(out, 'view.json'), 'w'),
              indent=1)
    return views


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:]
    opt = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d
    main(argv[0], float(opt('--ppl', 399.4)), float(opt('--az3', 35.7)), json.loads(opt('--look')) if opt('--look') else None,
         opt('--L'))
