"""A smooth (LANCZOS) zoom of the sheet with a light 10 px grid, labels every 20 px: for reading lock lines by eye.

    python tools/hairlocks/raw.py VIEW OUT.png r0 r1 c0 c1 [ZOOM] [--walls]
"""
import os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ctx as cx
from PIL import Image, ImageDraw, ImageFont

a = sys.argv[1:]
view, out = a[0], a[1]
r0, r1, c0, c1 = (int(q) for q in a[2:6])
z = int(a[6]) if len(a) > 6 and not a[6].startswith('-') else 6
C = cx.make()
rgb = np.asarray(C['dv'][view]['rgb'], float)
rgb = rgb / 255 if rgb.max() > 1.5 else rgb
if '--walls' in a:
    from charkit.bodyqa import CLASS
    from charkit.outfit import ridges
    w = (C['dv'][view]['raw'] == CLASS['line']) | ridges(rgb)
    rgb = rgb.copy(); rgb[w] = 0.5 * rgb[w] + 0.5 * np.array([0, 0.3, 1])
im = Image.fromarray((np.clip(rgb[r0:r1, c0:c1], 0, 1) * 255).astype(np.uint8)).resize(((c1 - c0) * z, (r1 - r0) * z),
                                                                                       Image.LANCZOS)
dr = ImageDraw.Draw(im, 'RGBA')
font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 12)
for x in range((c0 // 10 + 1) * 10, c1, 10):
    X = (x - c0) * z
    dr.line([(X, 0), (X, im.size[1])], fill=(0, 90, 255, 70 if x % 20 == 0 else 25))
    if x % 20 == 0:
        dr.text((X + 2, 2), str(x), fill=(0, 60, 220, 255), font=font)
for y in range((r0 // 10 + 1) * 10, r1, 10):
    Y = (y - r0) * z
    dr.line([(0, Y), (im.size[0], Y)], fill=(255, 0, 90, 70 if y % 20 == 0 else 25))
    if y % 20 == 0:
        dr.text((2, Y + 2), str(y), fill=(220, 0, 60, 255), font=font)
im.save(out)
