"""where the skin shows round the shoulders and why: the build's assembly and garments (the fast evaluator at its spec,
--set overrides; the jacket's mask as garments.build makes it), z-buffered per view on the design's grid with the skin's
triangles labelled by body part (torso, bridge, arm, head) and by why the jacket left them (in its region but on its
border / tucked under a puff / cut by the neck / never in its region), and per view the skin pixels in a window
(--win x0,x1,z0,z1, L) counted by part and reason, with their extent; --png the labelled picture.
    python tools/garments6/skinwhere.py BUILD [--set PATH=JSON ..] [--win 0.15,0.6,-0.45,-1.0] [--png OUT.png]"""
import sys, os, json
sys.path.insert(0, '.')
sys.path.insert(0, os.path.join('tools', 'garments5'))
import numpy as np

args = sys.argv[1:]
def opt(k, d=None):
    if k in args:
        i = args.index(k); v = args[i + 1]; del args[i:i + 2]; return v
    return d
PNG = opt('--png')
WINL = [float(x) for x in opt('--win', '-0.6,0.6,-0.42,-1.0').split(',')]
sets = []
while '--set' in args:
    i = args.index('--set'); sets.append(args[i + 1]); del args[i:i + 2]
build = args[0]

import bodyj
from charkit import sweep, bodyeval, garments as gm, qa3d, bodyqa, pieceqa
from charkit.faceqa import zbuffer
B0 = sweep.load_bundle(build, True)
spec = sweep.base_spec({'base': build, 'stage': 'garments'}, B0)
for s in sets:
    p, v = s.split('=', 1)
    bodyeval.set_knob(spec, p, json.loads(v))
E = bodyeval.Evaluator(spec)
A, how = E.assembly(spec)
hull = gm.hull_pieces(spec, A)
L = A['head']['L']
nrm = gm.vertex_normals(A['verts'], A['faces'])
G = {g['name']: g for g in spec['garments']}
P = {'top': gm.shell(A, dict(G['top'], _spec=spec), nrm, hull)}
for s in ('sleeve_L', 'sleeve_R'):
    P[s] = gm.puff(A, dict(G[s], _spec=spec), hull)
c = G['collar']
P['collar'] = gm.collar_hull(A, dict(c, _spec=spec), nrm, hull)
P['bow'] = gm.bow_hull(A, dict(G['bow'], _spec=spec), hull)
V = np.asarray(A['verts'], float)
nV = len(V)
src = np.asarray(P['top']['src']); src = src[src >= 0]
ins = np.zeros(nV, bool); ins[src] = True
border = set()
for f in A['faces']:
    if any(ins[v] for v in f) and not all(ins[v] for v in f):
        border.update(f)
bord = np.zeros(nV, bool); bord[list(border)] = True
hidden = ins & ~bord
reg = gm.region(A, G['top']['region'])
tk = gm.tucked(A, G['top']['tuck'], spec, hull) if G['top'].get('tuck') else np.zeros(nV, bool)
part = np.full(nV, 'head', object)
for k, (a_, b_) in A['body']['parts'].items():
    part[a_:b_] = 'torso' if k == 'torso' else 'bridge' if k.startswith('shoulder_') else 'arm' if k.startswith('arm_') \
        else 'hand' if k.startswith('hand_') else 'leg'
why = np.where(bord, 'border', np.where(tk, 'tucked', np.where(reg & ~ins, 'cut', np.where(~reg, 'not_region', 'hidden'))))
T = bodyj.tris(A['faces'])
# the masked skin's neck crease (as faceregion.neck_crease reads the build's: faces on a hidden vertex dropped)
from charkit import faceregion
c_, L_, _ = faceregion.frame(B0)
Tv = T[~hidden[T].any(1)]
K = faceregion.crease_of(V, Tv, c_, L_)
if K:
    print('neck crease (masked, unsubdivided): max %s median %s worst %s' % (K['max'], K['median'],
          sorted(K['per'].items(), key=lambda kv: -kv[1])[:6]))
    import math
    zc = c_[2] + faceregion.CUT * L_
    zs = np.arange(zc - faceregion.JOIN[0] * L_, zc + faceregion.JOIN[1] * L_ + 1e-12, 0.01 * L_)
    Tb = Tv
    ring = V[np.abs(V[:, 2] - zc) < 0.02 * L_]
    axis = ring[:, :2].mean(0)
    for col in [k for k, _ in sorted(K['per'].items(), key=lambda kv: -kv[1])[:2]]:
        rr = faceregion.section_outline(V, Tb, axis, math.radians(col), zs)
        rw = faceregion.section_outline(V, T, axis, math.radians(col), zs)
        print('  column %d: z (L from the cut) / r masked / r whole:' % col)
        print('   ' + ' '.join('%+.2f:%s/%s' % ((z - zc) / L_, 'nan' if not np.isfinite(a) else '%.3f' % (a / L_),
                                             'nan' if not np.isfinite(b) else '%.3f' % (b / L_)) for z, a, b in zip(zs, rr, rw)))
T = T[~hidden[T].all(1)]
cats = sorted({(part[t[0]], why[t[0]]) for t in T})
cid = {c_: i for i, c_ in enumerate(cats)}
lab_s = np.array([cid[(part[t[0]], why[t[0]])] for t in T])
objs = [(V, T, lab_s)]
names = ['%s/%s' % c_ for c_ in cats]
for k, g in P.items():
    Tg = bodyj.tris(g['faces'])
    objs.append((np.asarray(g['verts'], float), Tg, np.full(len(Tg), len(names))))
    names.append(k)
D = qa3d.Design(B0)
ctx = D.sheet_context()
ppl = ctx['ppl']
az = bodyqa.azimuths(ctx['az3'])
iw = np.array(qa3d.iris_centres(B0))
W = bodyqa.WIN
out_imgs = []
for v in ('front', 'three_quarter', 'back'):
    org = bodyqa.origin(v, az[v], iw, B0.assembly['centre'])
    depth, lab = zbuffer(objs, az[v], org, L, 1.0 / ppl, W)
    r0, r1 = int((W['top'] - WINL[2]) * ppl), int((W['top'] - WINL[3]) * ppl)
    c0, c1 = int((W['x'] + WINL[0]) * ppl), int((W['x'] + WINL[1]) * ppl)
    sub = lab[r0:r1, c0:c1]
    print('== %s: skin showing in x %.2f..%.2f z %.2f..%.2f (L^2):' % (v, *WINL))
    for i, n in enumerate(names[:len(cats)]):
        m = sub == i
        if m.sum() > 3:
            rr, cc = np.nonzero(m)
            print('   %-22s %.4f  x %.2f..%.2f z %.2f..%.2f' % (n, m.sum() / ppl ** 2, (cc.min() + c0) / ppl - W['x'],
                  (cc.max() + c0) / ppl - W['x'], W['top'] - (rr.max() + r0) / ppl, W['top'] - (rr.min() + r0) / ppl))
    out_imgs.append((v, sub))
if PNG:
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    cmap = plt.get_cmap('tab20')
    fig, ax = plt.subplots(1, len(out_imgs), figsize=(7 * len(out_imgs), 6))
    for j, (v, sub) in enumerate(out_imgs):
        im = np.ones(sub.shape + (3,))
        for i, n in enumerate(names):
            m = sub == i
            if m.any():
                im[m] = (0.85, 0.85, 0.85) if i >= len(cats) and n != 'top' else (0.97, 0.75, 0.55) if n == 'top' else \
                    cmap(i % 20)[:3]
        ax[j].imshow(im, extent=[WINL[0], WINL[1], WINL[3], WINL[2]])
        ax[j].set_title(v, fontsize=9)
    from matplotlib.patches import Patch
    fig.legend([Patch(color=cmap(i % 20)[:3]) for i in range(len(cats))], names[:len(cats)], loc='lower center', ncol=6,
               fontsize=8)
    fig.tight_layout(rect=(0, 0.08, 1, 1)); fig.savefig(PNG, dpi=80); print(PNG)
