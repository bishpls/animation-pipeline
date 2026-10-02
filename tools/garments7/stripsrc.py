"""the skin showing in a window, traced to the body: the front-most skin triangles of the build's masked skin there
(per view), their nearest body vertices on the fast evaluator's assembly (the build's spec), and for those: the body
part, the puff margin (L inside the left/right puff: > 0 inside), whether the jacket's region keeps them (src) and the
collar's hide_under covers them; plus x/z extent.
    python tools/garments7/stripsrc.py BUILD [--views front,three_quarter] [--win x0,x1,z0,z1] [--ppl 600]"""
import sys, os, json
sys.path.insert(0, '.')
import numpy as np
from scipy.spatial import cKDTree
from charkit import bundle, qa3d, bodyqa, sweep, bodyeval, garments as gm
from charkit.faceqa import zbuffer
args = sys.argv[1:]
def opt(k, d):
    if k in args:
        i = args.index(k); v = args[i + 1]; del args[i:i + 2]; return v
    return d
VIEWS = opt('--views', 'front,three_quarter').split(',')
WIN = [float(x) for x in opt('--win', '0.15,0.47,-0.5,-0.6').split(',')]
PPL = float(opt('--ppl', '600'))
b = args[0]
B = bundle.load(b + '/bundle')
D = qa3d.Design(B)
az = bodyqa.azimuths(D.sheet_context()['az3'])
iw = np.array(qa3d.iris_centres(B))
objs, keys, skinV, skinT = [], [], None, None
for o in B.objects():
    var = 'masked' if o.group == 'skin' and o.has('masked') else 'eval'
    if not o.has(var):
        continue
    V, T, _, _ = o.mesh(var)
    V, T = np.asarray(V, float), np.asarray(T)
    if o.group == 'skin':
        skinV, skinT = V, T
        objs.append((V, T, np.arange(len(T))))
    else:
        objs.append((V, T, np.full(len(T), -1)))
B0 = sweep.load_bundle(b, True)
spec = sweep.base_spec({'base': b, 'stage': 'garments'}, B0)
E = bodyeval.Evaluator(spec); A, _ = E.assembly(spec); hull = gm.hull_pieces(spec, A)
L = A['head']['L']
G = {g['name']: g for g in spec['garments']}
nrm = gm.vertex_normals(A['verts'], A['faces'])
T_ = gm.shell(A, dict(G['top'], _spec=spec), nrm, hull)
src = np.asarray(T_['src']); inj = np.zeros(len(A['verts']), bool); inj[src[src >= 0]] = True
pm = np.full(len(A['verts']), -np.inf)
for nm in ('sleeve_L', 'sleeve_R'):
    pm = np.maximum(pm, gm.puff_margin(A, dict(G[nm], _spec=spec), hull, A['verts']))
parts = (A.get('body') or {}).get('parts') or {}
pname = np.array(['?'] * len(A['verts']), object)
for k, (a, c) in parts.items():
    pname[a:c] = k
hu = None
cs = G['collar']
if cs.get('hide_under'):
    try:
        Gc = gm.collar_hull(A, dict(cs, _spec=spec), nrm, hull)
        hu = np.zeros(len(A['verts']), bool)
        hu[np.asarray(gm.under_sheet(A, Gc, cs['hide_under']), int)] = True
    except Exception as e:
        print('collar hide_under not evaluated:', e)
kd = cKDTree(np.asarray(A['verts'], float))
win = dict(x=0.5, top=-0.3, bottom=-0.9)
for v in VIEWS:
    org = bodyqa.origin(v, az[v], iw, B.assembly['centre'])
    d, lab = zbuffer(objs, az[v], org, B.assembly['L'], 1.0 / PPL, win)
    H, W = lab.shape
    X, Z = np.meshgrid(np.linspace(-0.5, 0.5, W), np.linspace(-0.3, -0.9, H))
    inwin = (X >= WIN[0]) & (X <= WIN[1]) & (Z <= WIN[2]) & (Z >= WIN[3])
    tri = np.unique(lab[inwin & (lab >= 0)])
    if not len(tri):
        print('== %s: no skin in the window' % v); continue
    P = skinV[skinT[tri]].mean(1)
    dist, vi = kd.query(P)
    print('== %s: %d skin triangles visible in the window (%d px); nearest body vertex dist p50 %.4f L' % (
        v, len(tri), (inwin & (lab >= 0)).sum(), np.median(dist) / L))
    for k in sorted(set(pname[vi])):
        m = pname[vi] == k
        u = vi[m]
        print('   %-14s %4d  in jacket region %3d  hidden by collar %s  puff margin p10/p50/p90 %s  x %.2f..%.2f z %.2f..%.2f' % (
            k, m.sum(), inj[u].sum(), 'n/a' if hu is None else hu[u].sum(),
            np.round(np.percentile(np.clip(pm[u], -1, 1), [10, 50, 90]), 3),
            P[m, 0].min() / L, P[m, 0].max() / L, (P[m, 2].min() - gm._eye_z(A)) / L, (P[m, 2].max() - gm._eye_z(A)) / L))
