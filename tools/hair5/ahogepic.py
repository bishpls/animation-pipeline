"""the ahoge per view, zoomed: the design's (lines absorbed) | each build's (standing out of its hair), centrelines."""
import json, os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools', 'hair5'))
import ctx
from charkit import hairflagqa as hf
from PIL import Image

out = sys.argv[1]
sets = [a.split('=', 1) for a in sys.argv[2:]]
B = ctx.load_build(os.path.join(ROOT, 'charkit/out/h4n_nocrown'))
Dz = ctx.design(B)
ppl = Dz['ppl']
lab, pcs = hf.design_labels(Dz['truth'], Dz['dv'])
srcs = [('design', lab, pcs)]
for n, p in sets:
    Z = np.load(p)
    srcs.append((n, {v: Z[v] for v in hf.VIEWS if v in Z.files}, json.loads(str(Z['pieces']))))
rows = []
for v in hf.VIEWS:
    tiles = []
    ms = []
    for n, L, P in srcs:
        code = [hf.PART0 + i for i, p in enumerate(P) if p == 'ahoge']
        ah = np.isin(L[v], code)
        rest = (L[v] >= hf.PART0) & ~ah
        ms.append((ah & ~rest, rest, ah))
    w = hf._window(*[m[0] for m in ms], pad=15)
    for (a, r, full) in ms:
        t = np.ones(a[w].shape + (3,))
        t[r[w]] = (.9, .8, .7)
        t[full[w]] = (.6, .9, .85)
        t[a[w]] = (.1, .6, .55)
        P = hf.centreline(a[w])
        if P is not None:
            for y, x in P.astype(int):
                t[y, x] = (.9, .1, .1)
        tiles.append(np.pad(t, ((0, 0), (0, 3), (0, 0)), constant_values=1))
    rows.append(np.concatenate(tiles, 1))
W = max(r.shape[1] for r in rows)
rows = [np.pad(r, ((0, 4), (0, W - r.shape[1]), (0, 0)), constant_values=1) for r in rows]
im = (np.concatenate(rows, 0) * 255).astype(np.uint8)
Image.fromarray(im).resize((im.shape[1] * 5, im.shape[0] * 5), Image.NEAREST).save(out)
print(out, im.shape)
