"""Board: the assembled character (body + head + lofted neck) in clay: a full-body front/three-quarter/side, and head close-ups
(85 mm: front, 30, 60, 90, 150 degrees) for the default head and two variants.
    blender -b --factory-startup --python charkit/boards/head_board.py -- OUTDIR [variant ...]
"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import bpy
from charkit import character, qa

VARIANTS = {
    'default': {},
    'soft': {'head': {'chin': 1.4, 'jaw_w': 1.08, 'cheek': 1.25, 'face_len': 0.94, 'width': 1.04}},
    'sharp': {'head': {'chin': 0.65, 'jaw_w': 0.92, 'cheek': 0.8, 'face_len': 1.06, 'width': 0.96, 'flat': 1.15}},
}


def main(out, names):
    os.makedirs(out, exist_ok=True)
    for name in names:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        sc = bpy.context.scene
        sc.render.engine = 'BLENDER_EEVEE'
        sc.view_settings.view_transform = 'Standard'
        qa.studio()
        for o in bpy.data.objects:
            if o.type == 'LIGHT':
                o.data.energy *= 0.1
        C = character.build(dict(VARIANTS[name], name=name), clay=qa.clay())
        A = C['data']; eye_z = A['head']['eye_z']; L = A['head']['L']
        cd = bpy.data.cameras.new('cam'); cam = bpy.data.objects.new('cam', cd); sc.collection.objects.link(cam); sc.camera = cam
        sc.render.resolution_x, sc.render.resolution_y = 720, 1280
        for view, az in (('front', 0), ('three_q', 35), ('side', 90)):
            qa.render_view(cam, (0, 0, 0.82), az, 5, 0.1, os.path.join(out, f'{name}_body_{view}.png'), ortho=1.9)
        sc.render.resolution_x, sc.render.resolution_y = 900, 900
        tgt = (0, 0, eye_z - 0.02 * L)
        for az in (0, 30, 60, 90, 150):
            qa.render_view(cam, tgt, az, 0.8, 0.02, os.path.join(out, f"{name}_head_{az:03d}.png"), lens=85)


if __name__ == '__main__':
    a = sys.argv[sys.argv.index('--') + 1:]
    main(a[0], a[1:] or ['default'])
