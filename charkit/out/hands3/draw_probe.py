"""Probe: the current template (spec knobs) drawn in the sheet's back and side rows, its digits read as the sheet's."""
import sys, json
sys.path.insert(0, '.')
import numpy as np
from PIL import Image
from charkit import handsheet, code_hand as ch
P = ch.params(json.load(open('charkit/spec/clawd.json')), **(json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}))
J = np.array([[0.5, 0, -1.0], [0.6, 0, -1.8], [0.62, 0, -2.5], [0.63, 0, -2.8]])
H = ch.hand(J, 'left', P)
tiles = []
for row in ('back', 'side'):
    h = handsheet.draw(H, row, 600.0, cuff_end=0.034)
    D = handsheet.digits(h)
    print(row, 'reach %.3f L' % D['reach'], 'tips', len(D['tips']), [round(d['length'], 3) for d in sorted(D['digits'], key=lambda d: d['tip'][0])])
    tiles.append((h['mask'] * 200).astype(np.uint8))
Hh = max(t.shape[0] for t in tiles)
Image.fromarray(np.concatenate([np.pad(t, ((0, Hh - t.shape[0]), (0, 10))) for t in tiles], 1)).save('charkit/out/hands3/draw_probe.png')
