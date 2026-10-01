"""a layerref output's per-view overlays cut to their drawn boxes, side by side: python ovstrip.py DIR OUT.png"""
import sys
import numpy as np
from PIL import Image
d, outp = sys.argv[1], sys.argv[2]
cr = []
for v in ('front', 'three_quarter', 'profile', 'back'):
    try:
        im = Image.open('%s/%s.png' % (d, v)).convert('RGB')
    except FileNotFoundError:
        continue
    a = np.asarray(im).astype(int)
    m = np.abs(a - 247).sum(-1) > 20
    ys, xs = np.nonzero(m)
    y0, x0 = max(0, ys.min() - 5), max(0, xs.min() - 5)
    cr.append(im.crop((x0, y0, xs.max() + 5, min(y0 + 300, ys.max() + 5))))
W = sum(i.width for i in cr) + 10 * len(cr)
out = Image.new('RGB', (W, max(i.height for i in cr)), 'white')
x = 0
for i in cr:
    out.paste(i, (x, 0)); x += i.width + 10
out.save(outp)
print(outp, out.size)
