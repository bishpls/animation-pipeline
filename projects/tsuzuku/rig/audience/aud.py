"""The shadow audience: every person on the two sheets (GPT Image, black paper silhouettes seen from behind) traced as its
own shape; lantern bodies are holes (lit indigo paper at render).

    ../../../../.venv/bin/python aud.py      -> audience.json {people: [{outline, holes, lantern, w, h}]} (px, origin = bottom centre)
"""
import json, os
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage import measure
HERE = os.path.dirname(os.path.abspath(__file__))


def trace(mask, tol=1.0):
    out = []
    for c in measure.find_contours(np.pad(mask, 2).astype(float), .5):
        c = measure.approximate_polygon(c, tol)
        if len(c) >= 4: out.append([[round(float(x) - 2, 1), round(float(y) - 2, 1)] for y, x in c])
    return out


people = []
for sheet in ['sheet_1.png', 'sheet_2.png']:
    ink = np.array(Image.open(os.path.join(HERE, sheet)).convert('L')) < 128
    lab, n = ndi.label(ndi.binary_closing(ink, iterations=4))
    for k, sl in enumerate(ndi.find_objects(lab)):
        m = (lab[sl] == k + 1) & ink[sl]
        if m.sum() < 20000: continue
        fig = ndi.binary_fill_holes(m); holes = fig & ~m
        hl, nh = ndi.label(holes); big = [i + 1 for i, s in enumerate(ndi.sum(holes, hl, range(1, nh + 1))) if s > 1500]
        holes = np.isin(hl, big)
        h, w = m.shape; o = lambda P: [[p[0] - w / 2, p[1] - h] for p in P]      # origin: bottom centre
        lc = None
        if big:                                                      # the lantern's centre and radius (from its round outline)
            ys, xs = np.where(ndi.binary_fill_holes(ndi.binary_closing(holes, iterations=6))); lc = [float(xs.mean() - w / 2), float(ys.mean() - h), float((xs.max() - xs.min()) / 2)]
        people.append({'outline': [o(p) for p in trace(fig)], 'holes': [o(p) for p in trace(holes, .8)], 'lantern': bool(big), 'lc': lc, 'w': w, 'h': h})
json.dump({'people': people}, open(os.path.join(HERE, 'audience.json'), 'w'))
print(len(people), 'people,', sum(p['lantern'] for p in people), 'with lanterns')
