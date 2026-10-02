"""the neck's surroundings per view, labelled by object at a fine scale: each object a colour (skin by part: the
masked skin; the collar, the jacket, the bow, the hair, the puffs), to see what borders the skin round the neck.
    python tools/garments6/necklab.py OUT.png BUILD.. [--views front,three_quarter] [--ppl 600]"""
import sys, os
sys.path.insert(0, '.')
import numpy as np
from charkit import bundle, qa3d, bodyqa
from charkit.faceqa import zbuffer
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
args = sys.argv[1:]
def opt(k, d):
    if k in args:
        i = args.index(k); v = args[i + 1]; del args[i:i + 2]; return v
    return d
VIEWS = opt('--views', 'front,three_quarter').split(',')
PPL = float(opt('--ppl', '600'))
out, builds = args[0], args[1:]
COL = {'skin': (0.98, 0.82, 0.72), 'collar': (1.0, 1.0, 0.75), 'top': (0.95, 0.55, 0.3), 'bow': (0.75, 0.65, 0.95),
       'sleeve': (0.4, 0.75, 0.4), 'hair': (0.6, 0.3, 0.15), 'other': (0.6, 0.6, 0.6)}
fig, ax = plt.subplots(len(builds), len(VIEWS), figsize=(7 * len(VIEWS), 5.5 * len(builds)), squeeze=False)
for i, b in enumerate(builds):
    B = bundle.load(b + '/bundle')
    D = qa3d.Design(B)
    az = bodyqa.azimuths(D.sheet_context()['az3'])
    iw = np.array(qa3d.iris_centres(B))
    objs, keys = [], []
    for o in B.objects():
        var = 'masked' if o.group == 'skin' and o.has('masked') else 'eval'
        if not o.has(var):
            continue
        V, T, _, _ = o.mesh(var)
        n = o.name
        k = 'skin' if o.group == 'skin' else 'collar' if n == 'collar' else 'top' if n == 'top' else 'bow' if n == 'bow' \
            else 'sleeve' if n.startswith('sleeve') else 'hair' if n.startswith('hair') else 'other'
        objs.append((np.asarray(V, float), np.asarray(T), np.full(len(T), len(keys))))
        keys.append(k)
    for j, v in enumerate(VIEWS):
        org = bodyqa.origin(v, az[v], iw, B.assembly['centre'])
        depth, lab = zbuffer(objs, az[v], org, B.assembly['L'], 1.0 / PPL, dict(x=0.45, top=-0.3, bottom=-0.8))
        im = np.ones(lab.shape + (3,))
        for q, k in enumerate(keys):
            im[lab == q] = COL[k]
        ax[i, j].imshow(im, extent=[-0.45, 0.45, -0.8, -0.3])
        ax[i, j].set_title('%s %s' % (os.path.basename(b), v), fontsize=9); ax[i, j].grid(alpha=0.3)
fig.tight_layout(); fig.savefig(out, dpi=80); print(out)
