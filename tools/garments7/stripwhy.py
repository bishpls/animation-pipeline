"""why skin shows in a window: per view, the skin pixels in --win x0,x1,z0,z1 (L), and at each the jacket's (top's)
depth behind the skin (top hidden behind skin: by how much) or no jacket there (a hole), the collar likewise; plus the
skin's vertex groups (body parts by bone weight) under those pixels.
    python tools/garments7/stripwhy.py BUILD [--views front,three_quarter] [--win 0.15,0.47,-0.57,-0.66] [--ppl 600]"""
import sys, os
sys.path.insert(0, '.')
import numpy as np
from charkit import bundle, qa3d, bodyqa
from charkit.faceqa import zbuffer
args = sys.argv[1:]
def opt(k, d):
    if k in args:
        i = args.index(k); v = args[i + 1]; del args[i:i + 2]; return v
    return d
VIEWS = opt('--views', 'front,three_quarter').split(',')
WIN = [float(x) for x in opt('--win', '0.15,0.47,-0.57,-0.66').split(',')]
PPL = float(opt('--ppl', '600'))
b = args[0]
B = bundle.load(b + '/bundle')
D = qa3d.Design(B)
az = bodyqa.azimuths(D.sheet_context()['az3'])
iw = np.array(qa3d.iris_centres(B))
G = {}
for o in B.objects():
    var = 'masked' if o.group == 'skin' and o.has('masked') else 'eval'
    if not o.has(var):
        continue
    V, T, _, _ = o.mesh(var)
    n = o.name
    k = 'skin' if o.group == 'skin' else n if n in ('collar', 'top', 'bow') else 'sleeve' if n.startswith('sleeve') \
        else 'hair' if n.startswith('hair') else 'other'
    G.setdefault(k, []).append((np.asarray(V, float), np.asarray(T)))
win = dict(x=0.5, top=-0.3, bottom=-0.9)
for v in VIEWS:
    org = bodyqa.origin(v, az[v], iw, B.assembly['centre'])
    dep, labs = {}, {}
    allobjs, keys = [], []
    for k, L in G.items():
        objs = [(V, T, np.full(len(T), 0)) for V, T in L]
        d, l = zbuffer(objs, az[v], org, B.assembly['L'], 1.0 / PPL, win)
        dep[k] = np.where(l >= 0, d, np.inf)
        for V, T in L:
            allobjs.append((V, T, np.full(len(T), len(keys))))
        keys.append(k)
    d, lab = zbuffer([o for o in allobjs], az[v], org, B.assembly['L'], 1.0 / PPL, win)
    H, W = lab.shape
    xs = np.linspace(-0.5, 0.5, W); zs = np.linspace(-0.3, -0.9, H)
    X, Z = np.meshgrid(xs, zs)
    inwin = (X >= WIN[0]) & (X <= WIN[1]) & (Z <= WIN[2]) & (Z >= WIN[3])
    front = np.full(lab.shape, -1)
    best = np.full(lab.shape, np.inf)
    names = list(dep)
    for q, k in enumerate(names):
        m = dep[k] < best
        best[m] = dep[k][m]; front[m] = q
    skin = (front == names.index('skin')) & inwin if 'skin' in names else np.zeros_like(inwin)
    px = 1.0 / PPL ** 2
    print('== %s: window x %.2f..%.2f z %.2f..%.2f: skin showing %.5f L^2 (%d px)' % (v, WIN[0], WIN[1], WIN[2], WIN[3],
          skin.sum() * px, skin.sum()))
    for k in ('top', 'collar', 'sleeve', 'bow'):
        if k not in dep:
            continue
        behind = skin & np.isfinite(dep[k])
        gap = (dep[k] - dep['skin'])[behind]
        print('   %-7s present behind the skin at %d px (%.0f%%), depth behind p10/p50/p90 %s L; absent (hole) %d px' % (
            k, behind.sum(), 100 * behind.sum() / max(skin.sum(), 1),
            np.round(np.percentile(gap, [10, 50, 90]), 4) if behind.any() else '-', (skin & ~np.isfinite(dep[k])).sum()))
    if skin.any():
        zz, xx = Z[skin], X[skin]
        for z0 in np.arange(WIN[2], WIN[3] - 1e-9, -0.01):
            m = (zz <= z0) & (zz > z0 - 0.01)
            if m.any():
                print('     z %.2f: %4d px, x %.3f..%.3f' % (z0, m.sum(), xx[m].min(), xx[m].max()))
    if '--png' in sys.argv:
        import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
        COL = {'skin': (0.98, 0.82, 0.72), 'collar': (1.0, 1.0, 0.75), 'top': (0.95, 0.55, 0.3), 'bow': (0.75, 0.65, 0.95),
               'sleeve': (0.4, 0.75, 0.4), 'hair': (0.6, 0.3, 0.15), 'other': (0.6, 0.6, 0.6)}
        im = np.ones(lab.shape + (3,))
        for q, k in enumerate(names):
            im[front == q] = COL[k]
        im[skin] = (1, 0, 0)
        plt.figure(figsize=(10, 6)); plt.imshow(im, extent=[-0.5, 0.5, -0.9, -0.3]); plt.grid(alpha=.3)
        plt.savefig(sys.argv[sys.argv.index('--png') + 1].replace('.png', '_%s.png' % v), dpi=80); plt.close()
