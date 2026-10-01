"""cross-sections of a build's objects through the shoulder, in L (x from the midline, y toward the back, z from the
eye line): vertical planes x = const (the y-z section) and horizontal planes z = const (the x-y section), the skin, the
jacket, the sleeves, the collar, the bow and the hair each a colour; one row per build.
    python tools/garments6/xsec.py OUT.png BUILD.. [--x 0.3,0.45,0.55] [--z -0.55,-0.65,-0.75] [--objects a,b]"""
import sys, os
sys.path.insert(0, '.')
import numpy as np
from charkit import bundle, qa3d
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt

args = sys.argv[1:]
def opt(k, d):
    if k in args:
        i = args.index(k); v = args[i + 1]; del args[i:i + 2]; return v
    return d
XS = [float(a) for a in opt('--x', '0.3,0.45,0.55').split(',') if a]
ZS = [float(a) for a in opt('--z', '-0.55,-0.65,-0.75').split(',') if a]
OBJ = opt('--objects', 'clawd_skin,top,sleeve_L,collar,bow,hair')
out, builds = args[0], args
builds = args[1:]
COL = {'clawd_skin': 'tan', 'top': 'darkorange', 'sleeve_L': 'green', 'collar': 'red', 'bow': 'purple', 'hair': 'sienna'}


def section(V, T, ax, c):
    """the segments where the plane coordinate `ax` == c cuts the triangles -> (n, 2, 3)."""
    d = V[T][:, :, ax] - c
    s = np.sign(d)
    cut = ~((s > 0).all(1) | (s < 0).all(1))
    segs = []
    for tri, dd in zip(V[T][cut], d[cut]):
        pts = []
        for a, b in ((0, 1), (1, 2), (2, 0)):
            if (dd[a] > 0) != (dd[b] > 0):
                t = dd[a] / (dd[a] - dd[b])
                pts.append(tri[a] + t * (tri[b] - tri[a]))
        if len(pts) >= 2:
            segs.append(pts[:2])
    return np.array(segs) if segs else np.zeros((0, 2, 3))


n = len(XS) + len(ZS)
fig, axs = plt.subplots(len(builds), n, figsize=(4.2 * n, 4.4 * len(builds)), squeeze=False)
for r, b in enumerate(builds):
    B = bundle.load(b + '/bundle')
    As = B.assembly
    L = As['L']
    ez = float(np.mean(np.array(qa3d.iris_centres(B))[:, 2]))
    objs = []
    for o in B.objects(visible=True):
        key = next((k for k in OBJ.split(',') if o.name == k or (k == 'hair' and o.name.startswith('hair'))), None)
        if key is None:
            continue
        V, T, _, _ = o.mesh('masked' if o.name == 'clawd_skin' and o.has('masked') else 'eval')
        V = np.asarray(V, float).copy()
        V[:, 0] /= L; V[:, 1] /= L; V[:, 2] = (V[:, 2] - ez) / L
        objs.append((key, V, np.asarray(T)))
    for j, c in enumerate(XS + ZS):
        ax = 0 if j < len(XS) else 2
        a = axs[r, j]
        for key, V, T in objs:
            k = (V[T][:, :, ax].min(1) <= c) & (V[T][:, :, ax].max(1) >= c)
            if not k.any():
                continue
            S = section(V, T[k], ax, c)
            u, w = (1, 2) if ax == 0 else (0, 1)
            for s in S:
                a.plot(s[:, u], s[:, w], '-', color=COL.get(key, 'k'), lw=0.8)
        if ax == 0:
            a.set_xlim(-0.45, 0.45); a.set_ylim(-1.0, -0.35); a.set_xlabel('y (front <- -> back)')
            a.set_title('%s x = %.2f (y-z)' % (os.path.basename(b), c), fontsize=8)
        else:
            a.set_xlim(-0.05, 0.85); a.set_ylim(0.4, -0.45); a.set_xlabel('x')
            a.set_title('%s z = %.2f (x-y; front up)' % (os.path.basename(b), c), fontsize=8)
        a.set_aspect('equal'); a.grid(alpha=0.3)
from matplotlib.lines import Line2D
fig.legend([Line2D([0], [0], color=v) for v in COL.values()], list(COL), loc='lower center', ncol=6)
fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig(out, dpi=80)
print(out)
