"""Fable three-quarter (room ending): fix up SAM's masks before tools/layers.py.
  - near-black cloth (sleeves, jacket) comes back from SAM speckled with pinholes: close and fill each such mask
  - the stick is too thin for SAM: its mask is the drawing's own dark pixels in its box, minus the hand and the lantern
    .venv/bin/python rig/fable_3q/mesh/masks.py
"""
import os
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

D = os.path.dirname(os.path.abspath(__file__)); P = lambda *a: os.path.join(D, *a)
B = np.array(Image.open(P('..', 'base_keyed.png')).convert('RGBA')); A = B[..., 3] > 128
rd = lambda n: np.array(Image.open(P('seg', n + '.png'))) > 127
wr = lambda n, m: Image.fromarray((m * 255).astype(np.uint8)).save(P('seg', n + '.png'))

for n in ('sleeve_L', 'sleeve_R', 'sleeve_R_back', 'jacket', 'hakama'):
    m = rd(n); m2 = ndi.binary_fill_holes(ndi.binary_closing(m, iterations=4)) & A
    wr(n, m2); print(f'{n:14s} {m.sum():8d} -> {m2.sum():8d}')

# the stick (tip at x 258, into her fist at ~575, y 1370-1414) and the brass ring on it that hooks the lantern's handle
# (x 286-314, y 1376-1436): everything opaque there that isn't skin. The wire handle below the ring stays with the lantern
# (it swings with it); the hand keeps the stick only between its fingers (x > 560)
lum = B[..., :3].astype(float) @ [.299, .587, .114]
skin = (B[..., 0].astype(int) > 170) & (lum > 150)
m = np.zeros_like(A); m[1368:1416, 250:562] = True; m[1374:1438, 285:316] = True
m &= A & ~skin
wr('stick', m); print('stick', m.sum())
h = rd('hand_R'); h[:, :562] &= ~m[:, :562]; wr('hand_R', h)
L = rd('lantern'); L &= ~m; L[1414:1530, 240:372] |= A[1414:1530, 240:372] & ~m[1414:1530, 240:372]; wr('lantern', L)
