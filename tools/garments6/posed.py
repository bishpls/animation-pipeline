"""the 90 degree raises with the garments on: the build's assembly (the fast evaluator at its spec, --set overrides)
and its jacket, puff, collar and bow (garments.py's own builders, with their weights), the left arm raised to the side
and forward by linear blend skinning on each piece's own weights about the rig's joint (tools/garments5/bodyj.pose),
and measured:
  skin_out    the skin of the bridge and the arm the puff holds at rest (inside it) coming out through it posed: count,
              depth (L; the puff is rigid on the upper arm, so the skin is read back in its rest frame)
  skin_vis    the skin left unmasked (not under the jacket) in the shoulder region that lies outside the puff posed:
              count (the skin a viewer could see by the shoulder)
  top_strain  the jacket's edges round the shoulder (within 0.45 L of the joint): p95 stretch (max(l1/l0, l0/l1)),
              folded faces' area share (posed normal against the rest normal carried by the face's own arm weight)
  puff_in     the puff's vertices inside the jacket's torso (the torso's radial field + the jacket's offset), posed
              against rest (the cap's inner side runs into the torso by design at rest): count and depth
and drawn (--png): rest, side raise from the front, forward raise from the side, each piece its colour.
    python tools/garments6/posed.py BUILD [--set PATH=JSON ..] [--png OUT.png] [--json OUT.json] [--name NAME]"""
import sys, os, json, math
sys.path.insert(0, '.')
sys.path.insert(0, os.path.join('tools', 'garments5'))
import numpy as np

args = sys.argv[1:]
def opt(k, d=None):
    if k in args:
        i = args.index(k); v = args[i + 1]; del args[i:i + 2]; return v
    return d
PNG, JS, NAME = opt('--png'), opt('--json'), opt('--name', 'posed')
sets = []
while '--set' in args:
    i = args.index('--set'); sets.append(args[i + 1]); del args[i:i + 2]
build = args[0]

import bodyj
from charkit import sweep, bodyeval, garments as gm
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
P = {}
P['top'] = gm.shell(A, dict(G['top'], _spec=spec), nrm, hull)
P['sleeve_L'] = gm.puff(A, dict(G['sleeve_L'], _spec=spec), hull)
if 'collar' in G:
    c = G['collar']
    P['collar'] = gm.collar_hull(A, dict(c, _spec=spec), nrm, hull) if c.get('source') == 'hull' else \
        gm.shell(A, dict(gm.COLLAR_TEMPLATE, **c, _spec=spec), nrm, hull)
if 'bow' in G:
    P['bow'] = gm.bow_hull(A, dict(G['bow'], _spec=spec), hull)
# the skin's mask (the jacket's: its source vertices less its border, as garments.build hides them)
src = np.asarray(P['top']['src'])
ins = np.zeros(len(A['verts']), bool); ins[src[src >= 0]] = True
border = set()
for f in A['faces']:
    if any(ins[v] for v in f) and not all(ins[v] for v in f):
        border.update(f)
hidden = ins.copy(); hidden[list(border)] = False
J = A['joints']
SKIN = dict(verts=np.asarray(A['verts'], float), joints=J, weights=A['weights'], head_len=L)
pc = P['sleeve_L']['frame']['origin']
jp = np.asarray(J['shoulder01.L____head'], float)
region = np.linalg.norm(SKIN['verts'] - jp, axis=1) < 0.45 * L
held = gm.body_part_mask(A, ('shoulder_', 'arm_'), 'left') & (np.linalg.norm(np.asarray(A['verts'], float) - np.asarray(A['joints']['shoulder01.L____head'], float), axis=1) < 0.3 * L)
spec_puff = dict(G['sleeve_L'], _spec=spec)


def inside_mesh(Vm, Tm, X):
    """points inside a closed mesh (a crossing count's parity along three skewed rays, the majority) and their
    distance to its surface (L)."""
    from charkit.geom.bvh import BVH
    bv = BVH((np.asarray(Vm, float), np.asarray(Tm, np.int64)))
    odd = sum((bv.ray_count(X, d) % 2 == 1).astype(int) for d in ((0.13, 0.21, 0.97), (0.91, -0.17, 0.37), (-0.3, 0.94, -0.16)))
    d, _, _ = bv.nearest(X)
    return odd >= 2, d / L


Tp = bodyj.tris(P['sleeve_L']['faces'])
in_rest, _ = inside_mesh(P['sleeve_L']['verts'], Tp, SKIN['verts'])


def posed(G_, tgt):
    V_ = np.asarray(G_['verts'], float)
    W_ = {k: np.broadcast_to(np.asarray(v, float), (len(V_),)) for k, v in G_['weights'].items()}
    W_.setdefault('leftUpperArm', np.zeros(len(V_)))
    return bodyj.pose(dict(verts=V_, joints=J, weights=W_, head_len=L), 'left', tgt)


def tris(F):
    return bodyj.tris(F)


def strain(V0, V1, F, sel, w_arm, R):
    E = set()
    for f in F:
        for k in range(len(f)):
            a, b = int(f[k]), int(f[(k + 1) % len(f)])
            if sel[a] and sel[b]:
                E.add((min(a, b), max(a, b)))
    if not E:
        return None
    E = np.array(sorted(E))
    l0 = np.linalg.norm(V0[E[:, 0]] - V0[E[:, 1]], axis=1)
    l1 = np.linalg.norm(V1[E[:, 0]] - V1[E[:, 1]], axis=1)
    r = l1 / np.maximum(l0, 1e-12)
    long_ = l0 >= 0.01 * L
    rr = np.maximum(r, 1 / np.maximum(r, 1e-9))[long_]
    T = tris(F)
    T = T[sel[T].all(1)]
    n0 = np.cross(V0[T[:, 1]] - V0[T[:, 0]], V0[T[:, 2]] - V0[T[:, 0]])
    n1 = np.cross(V1[T[:, 1]] - V1[T[:, 0]], V1[T[:, 2]] - V1[T[:, 0]])
    a0 = np.linalg.norm(n0, axis=1)
    wf = w_arm[T].mean(1)
    ex = np.where((wf > 0.5)[:, None], n0 @ R.T, n0)
    fold = np.sum(ex * n1, 1) < 0
    return dict(p95=round(float(np.percentile(rr, 95)), 3) if len(rr) else None, max=round(float(rr.max()), 3) if len(rr) else None,
                folded=round(float(a0[fold].sum() / max(a0.sum(), 1e-12)), 4))


out = dict(name=NAME, sets=sets)
poses = {'rest': None, 'side': (1.0, 0.0, 0.0), 'front': (0.0, -1.0, 0.0)}
geo = {}
for key, tgt in poses.items():
    if tgt is None:
        geo[key] = {'skin': SKIN['verts'], **{k: np.asarray(v['verts'], float) for k, v in P.items()}}
        continue
    Vs = posed(SKIN, tgt)
    R = bodyj.pose.R
    piv = jp
    g = {'skin': Vs}
    for k, v in P.items():
        g[k] = posed(v, tgt)
    geo[key] = g
    # the skin against the posed puff itself (rigid on the upper arm, or with the body's weights on its cap)
    in_pose, dist = inside_mesh(g['sleeve_L'], Tp, Vs)
    out_ = held & in_rest & ~in_pose & (dist > 0.002)
    vis = region & ~hidden & ~in_pose
    w_top = sum(np.asarray(P['top']['weights'].get('left' + b, 0)) for b in bodyj.ARM_BONES)
    if np.isscalar(w_top):
        w_top = np.zeros(len(P['top']['verts']))
    Vt0 = np.asarray(P['top']['verts'], float)
    selt = np.linalg.norm(Vt0 - jp, axis=1) < 0.45 * L
    rec = dict(skin_out=dict(n=int(out_.sum()), depth=round(float(dist[out_].max()), 4) if out_.any() else 0.0),
               skin_vis=dict(n=int(vis.sum()), rest=int((region & ~hidden & ~in_rest).sum())),
               top_strain=strain(Vt0, g['top'], P['top']['faces'], selt, np.asarray(w_top), R))
    Vp0 = np.asarray(P['sleeve_L']['verts'], float)
    w_p = sum(np.broadcast_to(np.asarray(P['sleeve_L']['weights'].get('left' + b, 0.0), float), (len(Vp0),))
              for b in bodyj.ARM_BONES)
    rec['puff_strain'] = strain(Vp0, g['sleeve_L'], P['sleeve_L']['faces'], np.ones(len(Vp0), bool), np.asarray(w_p), R)
    if 'collar' in P:
        Vc0 = np.asarray(P['collar']['verts'], float)
        w_c = sum(np.asarray(P['collar']['weights'].get('left' + b, np.zeros(len(Vc0)))) for b in bodyj.ARM_BONES)
        rec['collar_strain'] = strain(Vc0, g['collar'], P['collar']['faces'], np.linalg.norm(Vc0 - jp, axis=1) < 0.45 * L,
                                      np.asarray(w_c), R)
    out[key] = rec
    print('%s %s: skin out of the puff %s, skin showing by the shoulder %s, jacket %s, puff %s, collar %s' % (
        NAME, key, rec['skin_out'], rec['skin_vis'], rec['top_strain'], rec['puff_strain'], rec.get('collar_strain')))
if JS:
    json.dump(out, open(JS, 'w'), indent=1, default=str)
if PNG:
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from charkit.faceqa import zbuffer
    COL = {'skin': (0.96, 0.82, 0.7), 'top': (0.95, 0.6, 0.35), 'sleeve_L': (0.45, 0.75, 0.4), 'collar': (1.0, 0.75, 0.75),
           'bow': (0.65, 0.5, 0.8)}
    Tsk = tris(A['faces'])
    Tsk = Tsk[~hidden[Tsk].all(1)]
    views = [('rest', 0.0, 'front'), ('rest', 90.0, 'side'), ('side', 0.0, 'front'), ('front', 90.0, 'side'),
             ('side', 180.0, 'back')]
    fig, ax = plt.subplots(1, len(views), figsize=(5.0 * len(views), 4.8))
    ez = float(A['head']['centre'][2]) if 'centre' in A['head'] else 0.0
    for j, (key, az, lab_) in enumerate(views):
        g = geo[key]
        objs = [(g['skin'], Tsk, np.zeros(len(Tsk), int))]
        names = ['skin']
        for k in P:
            objs.append((g[k], tris(P[k]['faces']), np.full(len(tris(P[k]['faces'])), len(names))))
            names.append(k)
        u0 = {0.0: float(jp[0]), 180.0: -float(jp[0]), 90.0: float(jp[1])}[az]   # (the joint's: u is x, -x or y)
        depth, lab = zbuffer(objs, az, (u0, float(jp[2])), L, 1.0 / 250, dict(x=0.75, top=0.6, bottom=-0.8))
        im = np.ones(lab.shape + (3,))
        for i, n in enumerate(names):
            im[lab == i] = COL.get(n, (0.5, 0.5, 0.5))
        ax[j].imshow(im)
        ax[j].set_title('%s %s (%s)' % (NAME, key, lab_), fontsize=9); ax[j].axis('off')
    fig.tight_layout(); fig.savefig(PNG, dpi=80); print(PNG)
