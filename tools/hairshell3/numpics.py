"""Per panel: the sheet at full resolution with each segmented piece's boundary (thin red) and its region id (blue,
large), for reading the sheet's own lock numbers by eye into NUMBERS.json ({view: {region id: number}}).

    python tools/hairshell3/numpics.py SHEET.png RESULT_DIR
"""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sheet, d = sys.argv[1], sys.argv[2]
r = json.load(open(os.path.join(d, 'result.json')))
rgb = Image.open(sheet).convert('RGB')
try:
    font = ImageFont.load_default(size=22)
except TypeError:
    font = ImageFont.load_default()
for v, x in r['views'].items():
    R = x['registration']
    c0, r0 = R['c0'], R['r0']
    ps = x['sheet_pieces']
    ys = [p['centroid_sheet'][0] for p in ps.values()]; xs = [p['centroid_sheet'][1] for p in ps.values()]
    box = (max(0, min(xs) - 260), max(0, min(ys) - 200), min(rgb.size[0], max(xs) + 260), min(rgb.size[1], max(ys) + 200))
    im = rgb.crop(box).copy()
    dr = ImageDraw.Draw(im)
    for k, p in ps.items():
        y, x_ = p['centroid_sheet'][0] - box[1], p['centroid_sheet'][1] - box[0]
        t = 'r%s' % k
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            dr.text((x_ + 10 + dx, y + 10 + dy), t, fill=(255, 255, 255), font=font)
        dr.text((x_ + 10, y + 10), t, fill=(0, 0, 230), font=font)
        dr.ellipse((x_ - 4, y - 4, x_ + 4, y + 4), fill=(0, 0, 230))
    im.save(os.path.join(d, '%s_numbers.png' % v))
    print(v, box)
