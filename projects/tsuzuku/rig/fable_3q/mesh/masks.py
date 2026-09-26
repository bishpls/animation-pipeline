"""Fable three-quarter (room ending): fix up SAM's masks before tools/layers.py (padded canvas: the base is 600 px lower).
  - near-black cloth (the far sleeve, jacket, hakama) comes back from SAM speckled with pinholes: close and fill each such mask
  - the NEAR SLEEVE is defined by the drawing itself (as rig/fable_stage/mesh/sleeves.py): a kimono sleeve over a black jacket has
    no drawn line to cut along, so the sleeve is what the base has and the no-arms companion (under/noarms_al.png) doesn't (its
    bare arm counts as 'doesn't': skin), minus the hand, grown 30 px into the body so it covers the jacket's side at rest (the
    jacket there is the companion's own drawn side, build.json fromimg)
  - the stick is too thin for SAM: the drawing's own dark pixels in its box, minus the hand; its brass ring stays with it, the
    lantern keeps its wire handle (it swings with it)
    .venv/bin/python projects/tsuzuku/rig/fable_3q/mesh/masks.py
"""
import os
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

D = os.path.dirname(os.path.abspath(__file__)); P = lambda *a: os.path.join(D, *a)
B = np.array(Image.open(P('..', 'base_keyed.png')).convert('RGBA')); A = B[..., 3] > 128
rd = lambda n: np.array(Image.open(P('seg', n + '.png'))) > 127
wr = lambda n, m: Image.fromarray((m * 255).astype(np.uint8)).save(P('seg', n + '.png'))
lum = B[..., :3].astype(float) @ [.299, .587, .114]
isskin = lambda I: (I[..., 0].astype(int) > 170) & (I[..., 0].astype(int) - I[..., 2].astype(int) > 8) & ((I[..., :3].astype(float) @ [.299, .587, .114]) > 150)

for n in ('sleeve_R', 'sleeve_R_back', 'jacket', 'hakama'):
    m = rd(n); m2 = ndi.binary_fill_holes(ndi.binary_closing(m, iterations=4)) & A
    wr(n, m2); print(f'{n:14s} {m.sum():8d} -> {m2.sum():8d}')

# the near sleeve: the drop-shoulder seam and the sleeve's drawn back edge (a polygon along the lines; the front edge is the
# silhouette), minus the far arm and both hands. (A no-arms difference, as the stage rig's sleeves.py did, doesn't work here: the
# companion's vest shows its front panel past a bare arm, under the sleeve's front half.) The jacket under it comes from the
# no-arms companion (build.json fromimg)
import cv2
SLEEVE = [[700, 1560], [995, 1585], [1050, 1600], [1100, 1625], [1140, 1660], [1170, 1710], [1185, 1800], [1192, 1900], [1198, 1985],
          [1205, 2100], [1210, 2300], [1208, 2500], [1206, 2640], [1215, 2690], [740, 2480], [640, 2400], [640, 1560]]
pm = np.zeros(A.shape, np.uint8); cv2.fillPoly(pm, [np.array(SLEEVE, np.int32)], 1)
other = ndi.binary_dilation(rd('sleeve_R') | rd('hand_R') | rd('hand_L') | rd('lantern'), iterations=2)
sl = (pm > 0) & A & ~other
wr('sleeve_L', sl); print('sleeve_L (polygon)', sl.sum())
j = rd('jacket'); j &= ~sl; wr('jacket', j)

# the stick (tip at x 258, into her fist at ~575, y 1968-2014) and its brass ring (x 286-314, y 1974-2036)
m = np.zeros_like(A); m[1968:2016, 250:562] = True; m[1974:2038, 285:316] = True
m &= A & ~isskin(B)
wr('stick', m); print('stick', m.sum())
h = rd('hand_R'); h[:, :562] &= ~m[:, :562]; wr('hand_R', h)
L = rd('lantern'); L &= ~m; L[2014:2130, 240:372] |= A[2014:2130, 240:372] & ~m[2014:2130, 240:372]; wr('lantern', L)
