"""where the bow's cream touches the jacket or a sleeve with no line between (collarqa.bleed's measure), drawn: per
build the bow-region crop with the bow (cream), the jacket and sleeves (orange), the outline hulls (black) and the
touching pixels (red), and their rows' heights. python tools/garments6/bleedpic.py OUT.png BUILD.."""
import sys, os
sys.path.insert(0, '.')
import numpy as np
from charkit import bundle, collarqa as cq, lookqa, artifactqa
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
out, builds = sys.argv[1], sys.argv[2:]
fig, ax = plt.subplots(1, len(builds), figsize=(7 * len(builds), 6), squeeze=False)
for j, b in enumerate(builds):
    B = bundle.load(b + '/bundle')
    fr = lookqa.HeadFrame(B, ppl=cq.BLEED_PPL, ss=1, win=cq.BLEED_WIN)
    from charkit import bodyqa
    surfs = lookqa._scene(B, skin_outline=True, line_scale=lookqa.line_scale(B, 400, 1440))
    mesh, _ = artifactqa.buffers(B, surfs, 0.0, fr)
    nm = np.array([s['o'].name for s in surfs] + [''])
    hull = np.array([bool(s['hull']) for s in surfs] + [False])
    idx = np.where(mesh >= 0, mesh, len(surfs))
    name, line = nm[idx], hull[idx]
    bow = (name == 'bow') & ~line
    jk = np.isin(name, cq.JACKET) & ~line
    t = cq.edge_touch(bow, jk)
    im = np.ones(bow.shape + (3,))
    im[jk] = (0.95, 0.6, 0.35); im[bow] = (0.97, 0.9, 0.7); im[line] = (0.1, 0.1, 0.1)
    from scipy import ndimage
    im[ndimage.binary_dilation(t, iterations=2)] = (1, 0, 0)
    rr, cc = np.nonzero(t)
    print(os.path.basename(b), 'touch length', round(t.sum() / cq.BLEED_PPL, 4), 'L; pixels by column band:',
          np.histogram(cc, bins=8, range=(0, bow.shape[1]))[0].tolist() if len(cc) else '-')
    r0, r1 = (rr.min() - 120, rr.max() + 120) if len(rr) else (0, bow.shape[0])
    ax[0, j].imshow(im[max(0, r0):r1]); ax[0, j].set_title('%s: bow touching jacket/sleeve (red) %.4f L' % (
        os.path.basename(b), t.sum() / cq.BLEED_PPL), fontsize=9)
fig.tight_layout(); fig.savefig(out, dpi=70); print(out)
