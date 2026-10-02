"""the neck region's outline corners (artifactqa's art_outline_neck: the skin from the chin 0.5 L down, its outline's
corners per L) per view, located: each corner's x, z (L from the midline and the eye line), clustered by 0.04 L, with
the outline's kept length; builds side by side.
    python tools/garments7/neckcorners.py BUILD.. [--views front,three_quarter] [--region neck]"""
import sys, os
sys.path.insert(0, '.')
import numpy as np
from charkit import bundle, artifactqa as aq
args = sys.argv[1:]
def opt(k, d):
    if k in args:
        i = args.index(k); v = args[i + 1]; del args[i:i + 2]; return v
    return d
VIEWS = opt('--views', 'front,three_quarter').split(',')
REG = opt('--region', 'neck')
for b in args:
    B = bundle.load(b + '/bundle')
    pics = []
    M = aq.ours(B, pictures=pics)
    ppl = aq.HEAD_PPL
    hw, above, below = aq.HEAD_WIN
    for (frame, v, ppl_, kimg_pic, P) in [p for p in pics if p[0] == 'head']:
        if v not in VIEWS or REG not in P:
            continue
        rec = M['head'][v][REG]['outline']
        pts = []
        for d, keep, h, p, ck in P[REG]['outline']:
            for r_, c_ in p[ck[0]]:
                pts.append((c_ / ppl_ - hw, above - r_ / ppl_))
        pts = np.array(pts) if pts else np.zeros((0, 2))
        print('== %s %s: corners/L %s, n %s, len %.3f L' % (os.path.basename(b), v, rec and rec.get('corners'),
              rec and rec.get('n_corners'), rec and rec.get('len') or 0))
        # cluster
        used = np.zeros(len(pts), bool)
        for i in range(len(pts)):
            if used[i]:
                continue
            m = (np.abs(pts[:, 0] - pts[i, 0]) < 0.04) & (np.abs(pts[:, 1] - pts[i, 1]) < 0.04) & ~used
            used |= m
            print('   x %+.3f z %+.3f  x%d' % (pts[m, 0].mean(), -pts[m, 1].mean(), m.sum()))
