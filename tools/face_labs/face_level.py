"""a built character's head in the design's projection: orthographic, level with the head's eye line (the head sheet is
drawn so), in the boards' look (charkit.qa.render_view: the style's light and outline for the view), front,
three-quarter and profile, with the hair and without it (the hair's accessories hidden with it). One pixel is
1 / PPL of a head length L, the picture's middle the head's eye line at x 0 (the three-quarter and the profile turned
about the same point), so a page can lay the head sheet's views over them at one scale.

    blender -b OUT/NAME.blend --python face_level.py -- OUTDIR EYE_Z L AZ3 ROOT [PPL]

EYE_Z and L: the build's (its bundle's assembly: eye_z, L; world metres). Writes OUTDIR/level_{view}_{hair|bare}.png
and OUTDIR/level.json (eye_z, L, ppl, the views' azimuths, the picture's size)."""
import json, os, sys
argv = sys.argv[sys.argv.index('--') + 1:]
out, eye_z, L, az3, root = argv[0], float(argv[1]), float(argv[2]), float(argv[3]), argv[4]
ppl = float(argv[5]) if len(argv) > 5 else 600.0
sys.path.insert(0, root)
import bpy
from charkit import qa

os.makedirs(out, exist_ok=True)
sc = bpy.context.scene
SIZE = 720
sc.render.resolution_x, sc.render.resolution_y = SIZE, SIZE
cam = bpy.data.objects.get('board_cam')
if cam is None:
    cam = bpy.data.objects.new('board_cam', bpy.data.cameras.new('board_cam'))
    sc.collection.objects.link(cam)
sc.camera = cam
hair = [o for o in bpy.data.objects if o.type == 'MESH' and ('hair' in o.name.lower() or
                                                            o.name.lower().startswith(('bun', 'ahoge', 'bang', 'lock', 'fly')))]
acc = [o for o in bpy.data.objects if o.type == 'MESH' and o not in hair and o.get('ck_line_region') == 'accessory']
views = (('front', 0.0), ('three_quarter', az3), ('profile', 90.0))
for with_hair in (True, False):
    for o in hair + acc:
        o.hide_render = not with_hair
    tag = 'hair' if with_hair else 'bare'
    for name, az in views:
        qa.render_view(cam, (0.0, 0.0, eye_z), az, 5.0, 0.0, os.path.join(out, 'level_%s_%s.png' % (name, tag)),
                       ortho=SIZE / ppl * L)
json.dump(dict(eye_z=eye_z, L=L, ppl=ppl, size=SIZE, views=dict(views), hair=[o.name for o in hair],
               accessories=[o.name for o in acc]), open(os.path.join(out, 'level.json'), 'w'))
