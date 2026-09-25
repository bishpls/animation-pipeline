"""Invariant: a rig's layers composited at rest must reproduce the original illustration. Prints the mean and max difference
and writes a heat map of where they differ (fills that leak into view at rest show up here).

    .venv/bin/python tools/restcheck.py BASE.png BUILD_DIR OUT.png
"""
import json, os, sys
import numpy as np
from PIL import Image

base, bd, out = sys.argv[1:4]
B = np.array(Image.open(base).convert('RGBA')).astype(float) / 255
man = json.load(open(os.path.join(bd, 'manifest.json'))); C = np.zeros_like(B)
for l in man['layers']:
    t = np.array(Image.open(os.path.join(bd, l['name'] + '.png')).convert('RGBA')).astype(float) / 255
    y, x, h, w = l['y'], l['x'], l['h'], l['w']; a = t[:, :, 3:4]
    C[y:y + h, x:x + w, :3] = C[y:y + h, x:x + w, :3] * (1 - a) + t[:, :, :3] * a; C[y:y + h, x:x + w, 3:] = C[y:y + h, x:x + w, 3:] * (1 - a) + a
flat = lambda I: I[:, :, :3] * I[:, :, 3:] + .5 * (1 - I[:, :, 3:])
d = np.abs(flat(B) - flat(C)).max(2); big = d > .15
print(f'rest diff: mean {d.mean() * 255:.2f}  pixels > 15%: {big.sum()}')
ys, xs = np.where(big)
if len(ys):
    from scipy import ndimage as ndi
    lab, n = ndi.label(ndi.binary_dilation(big, iterations=4)); sz = ndi.sum(big, lab, range(1, n + 1)); com = ndi.center_of_mass(big, lab, range(1, n + 1))
    for s, c in sorted(zip(sz, com), reverse=True)[:8]: print(f'   {int(s):7d} px @ ({c[1]:.0f},{c[0]:.0f})')
hm = (flat(C) * 255 * .5).astype(np.uint8); hm[big] = [255, 0, 255]; Image.fromarray(hm).save(out)
