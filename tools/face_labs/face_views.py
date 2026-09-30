"""a built character's face and neck, close, from its saved scene in the boards' look (charkit.qa.render_view: the
board lights, 85 mm): front, three-quarter and profile, with the hair and without it (the face's own shading; the hair's
accessories hidden with it).

    blender -b OUT/NAME.blend --python face_views.py -- OUTDIR AZ3 ROOT
"""
import os, sys
argv = sys.argv[sys.argv.index('--') + 1:]
out, az3, root = argv[0], float(argv[1]), argv[2]
sys.path.insert(0, root)
import bpy
import numpy as np
from charkit import qa

os.makedirs(out, exist_ok=True)
sc = bpy.context.scene
skin = next(o for o in bpy.data.objects if o.type == 'MESH' and o.name.endswith('_skin'))
zs = np.array([(skin.matrix_world @ v.co).z for v in skin.data.vertices])
H = float(zs.max())
irises = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('iris_')]
eye_z = float(np.mean([(o.matrix_world @ v.co).z for o in irises for v in o.data.vertices]))
L = H / 5.9
cam = bpy.data.objects.get('board_cam')
if cam is None:
    cam = bpy.data.objects.new('board_cam', bpy.data.cameras.new('board_cam'))
    sc.collection.objects.link(cam)
sc.camera = cam
sc.render.resolution_x, sc.render.resolution_y = 720, 720
hair = [o for o in bpy.data.objects if o.type == 'MESH' and ('hair' in o.name.lower() or o.name.lower().startswith(('bun', 'ahoge', 'bang', 'lock', 'fly')))]
# the hair's accessories (the clips: charkit.accessories, outlined as region 'accessory') go with it: bare, they'd float
acc = [o for o in bpy.data.objects if o.type == 'MESH' and o not in hair and o.get('ck_line_region') == 'accessory']
print('face_views: hair objects', [o.name for o in hair], 'accessories', [o.name for o in acc])
views = (('front', 0.0), ('three_quarter', az3), ('profile', 90.0))
for with_hair in (True, False):
    for o in hair + acc:
        o.hide_render = not with_hair
    tag = 'hair' if with_hair else 'bare'
    for name, az in views:
        qa.render_view(cam, (0, 0, eye_z - 0.1 * L), az, 1.0, 0.0, os.path.join(out, 'face_%s_%s.png' % (name, tag)), lens=85)
        qa.render_view(cam, (0, 0, eye_z - 0.55 * L), az, 1.0, 0.0, os.path.join(out, 'neck_%s_%s.png' % (name, tag)), lens=85)
import json
json.dump(dict(eye_z=eye_z, L=L, H=H, az3=az3, hair=[o.name for o in hair], accessories=[o.name for o in acc]),
          open(os.path.join(out, 'views.json'), 'w'))
