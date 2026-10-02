"""the body's sections through the shoulder by part (head blue, torso green, bridge red, arm orange), per variant
(bodyj's body data: the build's spec with body.* overrides, the head's neck included): frontal planes y = const (x-z)
and sagittal planes x = const (y-z), in L from the neck axis's frame (x from the midline, z from the eye line as the
measures read it).
    python tools/garments6/bodysec.py BUILD VARIANTS.json OUT.png [--only a,b] [--y -0.05,0.1] [--x 0.25,0.4]"""
import sys, os, json, copy
sys.path.insert(0, '.')
sys.path.insert(0, os.path.join('tools', 'garments5'))
sys.path.insert(0, os.path.join('tools', 'garments6'))
import numpy as np
import bodyj
from xsec import section
from charkit import bundle, qa3d

args = sys.argv[1:]
def opt(k, d=None):
    if k in args:
        i = args.index(k); v = args[i + 1]; del args[i:i + 2]; return v
    return d
only = opt('--only')
YS = [float(a) for a in opt('--y', '-0.05,0.1').split(',')]
XS = [float(a) for a in opt('--x', '0.25,0.4').split(',')]
build, var, out = args[0], json.load(open(args[1])), args[2]
Bk = bundle.load(build + '/bundle')
ez = float(np.mean(np.array(qa3d.iris_centres(Bk))[:, 2]))
spec0 = json.load(open(os.path.join(build, 'clawd.spec.json')))
names = [n for n in var if not n.startswith('_') and (not only or n in only.split(','))]
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
nc = len(YS) + len(XS)
fig, ax = plt.subplots(len(names), nc, figsize=(5 * nc, 4 * len(names)), squeeze=False)
COL = {'head': 'tab:blue', 'torso': 'tab:green', 'shoulder': 'tab:red', 'arm': 'tab:orange'}
for r, name in enumerate(names):
    spec = copy.deepcopy(spec0)
    for k, v in (var[name] or {}).items():
        bodyj.setp(spec, k, v)
    sd = os.path.join(os.path.dirname(out) or '.', '_bodysec')
    os.makedirs(sd, exist_ok=True)
    Bd = bodyj.body_data(spec, os.path.join(sd, name + '.npz'))
    L = float(Bd['head_len'])
    V = np.asarray(Bd['verts'], float).copy()
    V[:, 0] /= L; V[:, 1] /= L; V[:, 2] = (V[:, 2] - ez) / L
    T = bodyj.tris(Bd['faces'])
    T = T[np.isfinite(V[T]).all((1, 2))]
    lab = np.full(len(V), 'head', object)
    for k, (a_, b_) in Bd['parts'].items():
        lab[a_:b_] = 'torso' if k == 'torso' else 'shoulder' if k.startswith('shoulder_') else 'arm' if k.startswith(
            ('arm_', 'hand_')) else 'torso'
    tl = lab[T[:, 0]]
    for j, c in enumerate(YS + XS):
        axis = 1 if j < len(YS) else 0
        a = ax[r, j]
        for part, col in COL.items():
            Tp = T[tl == part]
            k = (V[Tp][:, :, axis].min(1) <= c) & (V[Tp][:, :, axis].max(1) >= c)
            S = section(V, Tp[k], axis, c)
            u = 0 if axis == 1 else 1
            for s in S:
                a.plot(s[:, u], s[:, 2], '-', color=col, lw=0.9)
        if axis == 1:
            a.set_xlim(-0.05, 0.75); a.set_title('%s y = %.2f (x-z)' % (name, c), fontsize=8)
        else:
            a.set_xlim(-0.4, 0.4); a.set_title('%s x = %.2f (y-z, front left)' % (name, c), fontsize=8)
        a.set_ylim(-0.85, -0.35); a.set_aspect('equal'); a.grid(alpha=0.3)
        a.axhline(-0.544, color='k', lw=0.5, ls=':')
fig.tight_layout()
fig.savefig(out, dpi=80)
print(out)
