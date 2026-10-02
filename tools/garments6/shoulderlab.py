"""the shoulder window per view, the drawn pieces against ours, for builds side by side: one row per build (and a first
row for the design), columns the views; each piece one colour (top, sleeves, collar, bow, skin, hair, cuffs); a third
image per build marks where ours differs from the drawing for the pieces named (--pieces top,sleeve_L,..: ours-only red,
drawn-only blue). Prints each piece's IoU in the window per view.
    python tools/garments6/shoulderlab.py OUT.png BUILD.. [--pieces top,sleeve_L,sleeve_R,collar] [--win z0,z1,x0,x1]"""
import sys, os
sys.path.insert(0, '.')
import numpy as np
from charkit import bundle, qa3d, bodyqa, declared, pieceqa
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt

args = [a for a in sys.argv[1:]]
def opt(k, d):
    if k in args:
        i = args.index(k); v = args[i + 1]; del args[i:i + 2]; return v
    return d
PIECES = opt('--pieces', 'top,sleeve_L,sleeve_R,collar,bow').split(',')
WIN = [float(x) for x in opt('--win', '-0.35,-1.15,-0.9,0.9').split(',')]
out, builds = args[0], args[1:]
VIEWS = ('front', 'three_quarter', 'profile', 'back')
COL = {'top': (0.98, 0.72, 0.45), 'sleeve_L': (0.55, 0.85, 0.5), 'sleeve_R': (0.35, 0.7, 0.35), 'collar': (1.0, 0.6, 0.6),
       'bow': (0.6, 0.45, 0.75), 'skin': (0.85, 0.75, 0.65), 'hair': (0.9, 0.45, 0.1), 'sleeve_cuff_L': (0.85, 0.15, 0.15),
       'sleeve_cuff_R': (0.85, 0.15, 0.15), 'bodice_panel': (0.2, 0.6, 0.2)}
fig, ax = plt.subplots(1 + 2 * len(builds), 4, figsize=(16, 3.6 * (1 + 2 * len(builds))), squeeze=False)
for i, b in enumerate(builds):
    B = bundle.load(b + '/bundle')
    D = qa3d.Design(B)
    I = declared.inputs(B, D)
    ppl, W, names, pm = I['ppl'], bodyqa.WIN, I['names'], I['pm']
    r0, r1 = int((W['top'] - WIN[0]) * ppl), int((W['top'] - WIN[1]) * ppl)
    c0, c1 = int((W['x'] + WIN[2]) * ppl), int((W['x'] + WIN[3]) * ppl)
    ext = [WIN[2], WIN[3], WIN[1], WIN[0]]
    print('==', os.path.basename(b))
    for j, v in enumerate(VIEWS):
        lab = I['O'][v]['lab']
        imd = np.ones(lab.shape + (3,)) * 0.97
        imo = imd.copy()
        imx = np.ones(lab.shape + (3,)) * 0.97
        ious = []
        skin_o = np.zeros(lab.shape, bool)
        for k, n in enumerate(names):
            if 'skin' in n:
                skin_o |= lab == k
            if 'hair' in n:
                imo[lab == k] = COL['hair']
        imo[skin_o] = COL['skin']
        for p in COL:
            m = I['masks'].get('%s__%s' % (v, p))
            if m is not None:
                Md = declared.fit(m, lab.shape)
                imd[Md] = COL[p]
            if p in pm:
                Mo = pieceqa.members(lab, names, pm, p)
                imo[Mo] = COL[p]
            if p in PIECES and m is not None and p in pm:
                w = np.zeros(lab.shape, bool); w[r0:r1, c0:c1] = True
                a, d_ = Mo & w, Md & w
                if d_.sum() > 20:
                    ious.append('%s %.3f' % (p, (a & d_).sum() / max(1, (a | d_).sum())))
                imx[a & ~d_] = (0.9, 0.2, 0.2)
                imx[d_ & ~a] = (0.2, 0.3, 0.9)
                imx[a & d_ & (imx.sum(-1) > 2.8)] = (0.8, 0.8, 0.8)
        print('  %-14s %s' % (v, '  '.join(ious)))
        if i == 0:
            ax[0, j].imshow(imd[r0:r1, c0:c1], extent=ext); ax[0, j].set_title('design %s' % v, fontsize=9)
        ax[1 + 2 * i, j].imshow(imo[r0:r1, c0:c1], extent=ext)
        ax[1 + 2 * i, j].set_title('%s %s' % (os.path.basename(b), v), fontsize=9)
        ax[2 + 2 * i, j].imshow(imx[r0:r1, c0:c1], extent=ext)
        ax[2 + 2 * i, j].set_title('%s diff (red ours-only, blue drawn-only): %s' % (os.path.basename(b), ' '.join(PIECES)),
                                   fontsize=7)
        for a_ in (ax[1 + 2 * i, j], ax[2 + 2 * i, j], ax[0, j]):
            a_.grid(alpha=0.3)
fig.tight_layout()
os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
fig.savefig(out, dpi=80)
print(out)
