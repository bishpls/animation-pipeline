"""Cut the generated audience rows into single-person sprites (split at empty columns), and find each one's lantern (the
saturated blue glow) so the stage can bloom it and sway it. -> sprites/NN.png + sprites/meta.json [{file, w, h, lantern:[x, y]}]"""
import json, os
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
os.makedirs('sprites', exist_ok=True); meta = []
for row in ('row_1.png', 'row_2.png'):
    im = np.array(Image.open(row).convert('RGBA')); a = im[:, :, 3] > 24
    # people are separate 2-D components (arm, stick and lantern connect to the body); tiny bits join the nearest person
    lab, n = ndi.label(ndi.binary_closing(a, iterations=2)); sz = ndi.sum(a, lab, range(1, n + 1))
    big = [i + 1 for i in range(n) if sz[i] > 20000]
    for i in big:
        m = lab == i; ys, xs = np.nonzero(m); x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        sub = im[y0:y1, x0:x1].copy(); sub[~m[y0:y1, x0:x1], 3] = 0
        rgb = sub[:, :, :3].astype(float); blue = (rgb[:, :, 2] > 150) & (rgb[:, :, 2] - rgb[:, :, 0] > 60) & (sub[:, :, 3] > 200)
        L, k = ndi.label(blue); best = max(range(1, k + 1), key=lambda j: (L == j).sum()) if k else None
        ly, lx = ndi.center_of_mass(L == best) if best else (0, sub.shape[1] / 2)
        f = f'{len(meta):02d}.png'; Image.fromarray(sub).save('sprites/' + f)
        meta.append({'file': f, 'w': int(sub.shape[1]), 'h': int(sub.shape[0]), 'lantern': [round(float(lx)), round(float(ly))]})
json.dump(meta, open('sprites/meta.json', 'w'), indent=1); print(len(meta), 'sprites', [ (m['w'], m['h']) for m in meta ])
