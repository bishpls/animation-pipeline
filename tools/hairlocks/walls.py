"""The walls the labeller sees (the raw line class black, the faint ridges blue) over the hair, zoomed with a grid.

    python tools/hairlocks/walls.py VIEW OUT.png r0 r1 c0 c1 [ZOOM]
"""
import os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ctx as cx
from PIL import Image, ImageDraw, ImageFont
from charkit.bodyqa import CLASS
from charkit.outfit import ridges

a = sys.argv[1:]
view, out = a[0], a[1]
r0, r1, c0, c1 = (int(q) for q in a[2:6])
z = int(a[6]) if len(a) > 6 else 4
C = cx.make()
rgb = np.asarray(C['dv'][view]['rgb'], float)
rgb = rgb / 255 if rgb.max() > 1.5 else rgb
line = C['dv'][view]['raw'] == CLASS['line']
rid = ridges(rgb)
val = rgb.max(-1)
pic = np.stack([val] * 3, -1) * 0.35 + 0.65
h = C['hair'][view]
pic[h] = pic[h] * np.array([1, .85, .7])
pic[rid] = (0.1, 0.3, 0.9)
pic[line] = (0, 0, 0)
im = Image.fromarray((pic[r0:r1, c0:c1] * 255).astype(np.uint8)).resize(((c1 - c0) * z, (r1 - r0) * z), Image.NEAREST)
dr = ImageDraw.Draw(im, 'RGBA')
font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 12)
for x in range((c0 // 10 + 1) * 10, c1, 10):
    X = (x - c0) * z
    dr.line([(X, 0), (X, im.size[1])], fill=(0, 160, 0, 90 if x % 50 == 0 else 35))
    if x % 20 == 0:
        dr.text((X + 2, 2), str(x), fill=(0, 120, 0, 255), font=font)
for y in range((r0 // 10 + 1) * 10, r1, 10):
    Y = (y - r0) * z
    dr.line([(0, Y), (im.size[0], Y)], fill=(200, 0, 120, 90 if y % 50 == 0 else 35))
    if y % 20 == 0:
        dr.text((2, Y + 2), str(y), fill=(200, 0, 120, 255), font=font)
im.save(out)
