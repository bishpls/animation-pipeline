"""our piece labels per view, cropped to the shoulders, side by side for builds: python tools/garments5/labpng.py OUT.png BUILD.."""
import sys, os
sys.path.insert(0, '.')
import numpy as np
from charkit import bundle, qa3d, bodyqa, pieceqa
out, builds = sys.argv[1], sys.argv[2:]
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
VIEWS = ('front', 'three_quarter', 'profile', 'back')
fig, ax = plt.subplots(len(builds), 4, figsize=(18, 4.6 * len(builds)), squeeze=False)
cols = {}
pal = plt.get_cmap('tab20')
for i, b in enumerate(builds):
    B = bundle.load(b + '/bundle')
    D = qa3d.Design(B)
    ctx = D.sheet_context()
    ppl = ctx['ppl']
    O, names = pieceqa.our_labels(B, ppl, ctx['az3'])
    W = bodyqa.WIN
    r0, r1 = int((W['top'] + 0.3) * ppl), int((W['top'] + 1.3) * ppl)
    c0, c1 = int((W['x'] - 1.0) * ppl), int((W['x'] + 1.0) * ppl)
    for j, v in enumerate(VIEWS):
        lab = O[v]['lab'][r0:r1, c0:c1]
        im = np.ones(lab.shape + (3,))
        for k, n in enumerate(names):
            if (lab == k).any():
                if n not in cols:
                    cols[n] = pal(len(cols) % 20)[:3]
                im[lab == k] = cols[n]
        ax[i, j].imshow(im, extent=[-1.0, 1.0, -1.3, -0.3])
        ax[i, j].set_title('%s %s' % (os.path.basename(b), v), fontsize=9)
from matplotlib.patches import Patch
fig.legend([Patch(color=c) for c in cols.values()], list(cols), loc='lower center', ncol=8, fontsize=8)
fig.tight_layout(rect=(0, 0.05, 1, 1))
os.makedirs(os.path.dirname(out), exist_ok=True)
fig.savefig(out, dpi=90)
