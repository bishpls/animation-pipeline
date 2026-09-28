"""Board: three body types from the one base (petite idol, the default heroine, a tall action heroine), front / side /
three-quarter, in clay. Proves the proportion knobs. (Heads come from charkit/head.py; here the neck is open.)
    blender -b --factory-startup --python charkit/boards/body_lineup.py -- OUTDIR
"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import bpy
from mathutils import Vector
from charkit import body, qa

TYPES = {
    'petite': {'height_m': 1.48, 'heads_tall': 5.8, 'age': 0.7,
               'proportions': {'leg': 1.02, 'torso': 0.95, 'shoulder': 0.84, 'arm_slim': 0.82, 'leg_slim': 0.95, 'hand': 0.85}},
    'default': {},
    'tall': {'height_m': 1.70, 'heads_tall': 7.3, 'muscle': 0.6,
             'proportions': {'leg': 1.18, 'shin': 1.06, 'torso': 0.96, 'shoulder': 0.92, 'arm': 1.04, 'arm_slim': 0.86, 'leg_slim': 0.9}},
}


def main(out):
    os.makedirs(out, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = 720, 1280
    sc.view_settings.view_transform = 'Standard'
    qa.studio()
    m = qa.clay()
    xs = {'petite': -0.9, 'default': 0.0, 'tall': 0.9}
    for name, spec in TYPES.items():
        arm, ob, D = body.build_body(spec, name=name, material=m)
        arm.location.x = xs[name]
        print(name, 'height to neck', round(float(D['verts'][:, 2].max()), 3), 'faces', len(D['faces']))
    cd = bpy.data.cameras.new('cam'); cam = bpy.data.objects.new('cam', cd); sc.collection.objects.link(cam); sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
    paths = []
    for view, az in (('front', 0), ('three_q', 35), ('side', 90)):
        p = os.path.join(out, f'body_{view}.png')
        qa.render_view(cam, (0, 0, 0.8), az, 6, 0.1, p, ortho=2.6)
        paths.append(p)
    print('views:', paths)             # compose with the venv: charkit/qa.py sheet (Blender's Python has no PIL)


if __name__ == '__main__':
    main(sys.argv[sys.argv.index('--') + 1])
