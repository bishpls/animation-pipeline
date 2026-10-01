"""Probe handsheet.digits on the sheet's cells: numbers and a picture (tips red, clefts blue, digit axes green)."""
import sys
sys.path.insert(0, '.')
import numpy as np
from PIL import Image, ImageDraw
from charkit import handsheet
S = handsheet.cells()
tiles = []
for key in sorted(S, key=lambda k: (k[1], ['relaxed', 'open', 'fist', 'point'].index(k[0]))):
    h = S[key]
    D = handsheet.digits(h)
    print(key, 'reach %.3f' % D['reach'], 'tips', len(D['tips']), 'clefts', len(D['clefts']),
          'palm_w', None if D['palm_w'] is None else round(D['palm_w'], 3), 'knuckles',
          None if D['knuckles'] is None else round(D['knuckles'], 3))
    for d in D['digits']:
        print('    len %.3f widths %s round %.2f' % (d['length'], ' '.join('%.3f' % w for w in d['widths']), d['round']))
    m = h['mask']
    img = Image.fromarray(np.where(m[..., None], 200, 255).astype(np.uint8).repeat(3, 2))
    dr = ImageDraw.Draw(img)
    for t in D['tips']:
        dr.ellipse([t[0] - 5, t[1] - 5, t[0] + 5, t[1] + 5], fill=(220, 0, 0))
    for k in D['clefts']:
        dr.ellipse([k[0] - 5, k[1] - 5, k[0] + 5, k[1] + 5], fill=(0, 0, 220))
    for d in D['digits']:
        dr.line([tuple(d['base']), tuple(d['tip'])], fill=(0, 160, 0), width=2)
    dr.text((4, 4), '%s %s' % key, fill=(0, 0, 0))
    tiles.append(img.resize((img.size[0] // 2, img.size[1] // 2)))
H = max(t.size[1] for t in tiles)
W = sum(t.size[0] for t in tiles)
canvas = Image.new('RGB', (W, H), 'white')
x = 0
for t in tiles:
    canvas.paste(t, (x, 0)); x += t.size[0]
canvas.save('charkit/out/hands3/digits_probe.png')
