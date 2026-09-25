"""The two reed clumps as their own flats (rocksL.png, rocksR.png), cut from rocks.png. The flat's thin ground strip runs its whole
width, so a straight crop leaves a vertical cut edge at a clump's foot; here the strip ends in a rounded stone instead.

    ../../../../.venv/bin/python split_rocks.py
"""
import os
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
a = np.array(Image.open(os.path.join(HERE, 'rocks.png')).convert('L')); H, W = a.shape
for name, (x0, x1), side in [('rocksL', (0, .2406), 1), ('rocksR', (.8458, 1), -1)]:
    c = a[:, int(W * x0):int(W * x1)].copy(); h, w = c.shape; ink = c < 128
    # the cut side: every column within R of it keeps only ink above a quarter-circle rising to the cut (a stone's rounded end)
    R = 90; cols = range(w - R, w) if side > 0 else range(0, R)
    for x in cols:
        d = (x - (w - R)) if side > 0 else (R - x)                      # 0 .. R toward the cut
        lift = R - np.sqrt(max(0, R * R - d * d))                        # how far the rounded end has risen here
        top = int(h - 1 - (h * .06) * (lift / R) * 3)                    # the strip is ~6% of the height; the end curls it away
        c[top:, x][ink[top:, x]] = 255 if d > R * .15 else c[top:, x][ink[top:, x]]
        if d >= R * .95: c[:, x] = 255                                     # nothing touches the cut itself
    Image.fromarray(c).save(os.path.join(HERE, name + '.png')); print(name, c.shape)
