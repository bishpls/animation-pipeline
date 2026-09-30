"""the ink inside the hair per view: the drawing's lines (blue) against each build's part boundaries (red), the hair's
interior (grey); one row per view, a column per build."""
import json, os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools', 'hair5'))
import ctx
from charkit import hairflagqa as hf
from PIL import Image
from skimage.morphology import skeletonize

out = sys.argv[1]
sets = [a.split('=', 1) for a in sys.argv[2:]]
B = ctx.load_build(os.path.join(ROOT, 'charkit/out/h4n_nocrown'))
Dz = ctx.design(B)
ppl = Dz['ppl']
D = hf.design_side(Dz['truth'], Dz['dv'], ppl)
builds = []
for n, p in sets:
    Z = np.load(p)
    builds.append((n, {v: Z[v] for v in hf.VIEWS if v in Z.files}))
rows = []
for v in hf.VIEWS:
    kd = hf.interior(D['hair'][v], ppl)
    ld = skeletonize(D['lines'][v]) & kd
    ms = [D['hair'][v]] + [L[v] >= hf.PART0 for _, L in builds]
    w = hf._window(*ms, pad=6)
    tiles = []
    t = np.ones(kd[w].shape + (3,)); t[D['hair'][v][w]] = (.93, .9, .86); t[kd[w]] = (.85, .85, .85); t[ld[w]] = (0, 0, .9)
    tiles.append(t)
    for n, L in builds:
        ko = hf.interior(L[v] >= hf.PART0, ppl)
        lo = skeletonize(hf.part_lines(L[v])) & ko
        t = np.ones(kd[w].shape + (3,)); t[(L[v] >= hf.PART0)[w]] = (.93, .9, .86); t[ko[w]] = (.85, .85, .85)
        t[ld[w] & ko[w]] = (.55, .55, 1); t[lo[w]] = (.9, 0, 0)
        tiles.append(t)
    rows.append(np.concatenate([np.pad(x, ((0, 0), (0, 4), (0, 0)), constant_values=1) for x in tiles], 1))
W = max(r.shape[1] for r in rows)
rows = [np.pad(r, ((0, 6), (0, W - r.shape[1]), (0, 0)), constant_values=1) for r in rows]
im = (np.concatenate(rows, 0) * 255).astype(np.uint8)
Image.fromarray(im).resize((im.shape[1] * 2, im.shape[0] * 2), Image.NEAREST).save(out)
print(out, im.shape)
