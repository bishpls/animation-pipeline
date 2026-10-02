"""what comes through what at rest: for pairs (UNDER, OVER) of the build's pieces (the fast evaluator at its spec, --set
overrides; the skin with the jacket's mask), UNDER's vertices standing outside OVER's outer surface where OVER covers
them: each vertex's nearest point on OVER (inside its faces, not at its border) and the signed distance along that
face's normal (outward: away from the body's axis) -> count, depth p90/max (L), and where (x, z: L from the midline
and the eye line, the bounding box). A thin piece (the collar) reads its outer side; a closed one (the puff) is the
same test.
    python tools/garments6/poke.py BUILD [--set PATH=JSON ..] [--pairs top:collar,skin:collar,skin:top,top:sleeve_L]"""
import sys, os, json
sys.path.insert(0, '.')
sys.path.insert(0, os.path.join('tools', 'garments5'))
import numpy as np

args = sys.argv[1:]
def opt(k, d=None):
    if k in args:
        i = args.index(k); v = args[i + 1]; del args[i:i + 2]; return v
    return d
PAIRS = [p.split(':') for p in opt('--pairs', 'top:collar,skin:collar,skin:top,skin:sleeve_L,top:sleeve_L,top:bow').split(',')]
sets = []
while '--set' in args:
    i = args.index('--set'); sets.append(args[i + 1]); del args[i:i + 2]
build = args[0]

import bodyj
from charkit import sweep, bodyeval, garments as gm, qa3d
from charkit.geom.bvh import BVH
B0 = sweep.load_bundle(build, True)
spec = sweep.base_spec({'base': build, 'stage': 'garments'}, B0)
for s in sets:
    p, v = s.split('=', 1)
    bodyeval.set_knob(spec, p, json.loads(v))
E = bodyeval.Evaluator(spec)
A, how = E.assembly(spec)
hull = gm.hull_pieces(spec, A)
L = A['head']['L']
ez = float(np.mean(np.array(qa3d.iris_centres(B0))[:, 2]))
nrm = gm.vertex_normals(A['verts'], A['faces'])
G = {g['name']: g for g in spec['garments']}
need = {n for pr in PAIRS for n in pr}
P = {}
if 'top' in need or 'skin' in need:
    P['top'] = gm.shell(A, dict(G['top'], _spec=spec), nrm, hull)
if 'sleeve_L' in need:
    P['sleeve_L'] = gm.puff(A, dict(G['sleeve_L'], _spec=spec), hull)
if 'collar' in need:
    c = G['collar']
    P['collar'] = gm.collar_hull(A, dict(c, _spec=spec), nrm, hull) if c.get('source') == 'hull' else \
        gm.shell(A, dict(gm.COLLAR_TEMPLATE, **c, _spec=spec), nrm, hull)
if 'bow' in need:
    P['bow'] = gm.bow_hull(A, dict(G['bow'], _spec=spec), hull)
src = np.asarray(P['top']['src']) if 'top' in P else np.zeros(0, int)
ins = np.zeros(len(A['verts']), bool); ins[src[src >= 0]] = True
border = set()
for f in A['faces']:
    if any(ins[v] for v in f) and not all(ins[v] for v in f):
        border.update(f)
hidden = ins.copy(); hidden[list(border)] = False
skin_body = gm.body_part_mask(A, ('torso', 'shoulder_', 'arm_'))
P['skin'] = dict(verts=np.asarray(A['verts'], float)[skin_body & ~hidden], faces=[])
axis = np.array([0.0, float(np.mean(np.asarray(A['verts'])[:, 1]))])
for un, ov in PAIRS:
    if un not in P or ov not in P:
        continue
    X = np.asarray(P[un]['verts'], float)
    Vo = np.asarray(P[ov]['verts'], float)
    To = bodyj.tris(P[ov]['faces'])
    bv = BVH((Vo, To))
    d, f, q, reg = bv.nearest(X, return_region=True)
    n = np.cross(Vo[To[f, 1]] - Vo[To[f, 0]], Vo[To[f, 2]] - Vo[To[f, 0]])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    # outward: away from the body's upright axis (and up, for the shoulders' tops)
    rad = np.c_[q[:, :2] - axis, np.zeros(len(q))]
    rad /= np.maximum(np.linalg.norm(rad, axis=1, keepdims=True), 1e-12)
    if ov in ('collar', 'bow'):                          # (sheets of either winding: outward by the heuristic)
        flip = np.sum(n * (rad + np.array([0, 0, 0.5])), 1) < 0
        n[flip] *= -1
    sd = np.sum((X - q) * n, 1) / L
    # the border: faces with an edge used once (an open sheet's rim): a nearest point there isn't "covered"
    from collections import Counter
    ec = Counter()
    for t in To:
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            ec[(min(a, b), max(a, b))] += 1
    rim = {v for (a, b), c_ in ec.items() if c_ == 1 for v in (a, b)}
    on_rim = np.array([any(v in rim for v in To[ff]) for ff in f]) if rim else np.zeros(len(f), bool)
    cov = (reg == 0) & ~on_rim & (d / L < 0.08)
    out_ = cov & (sd > 0.002)
    if out_.any():
        for side, k in (('front', X[:, 1] < axis[1]), ('back', X[:, 1] >= axis[1])):
            o2 = out_ & k
            if not o2.any():
                continue
            xs, zs = X[o2, 0] / L, (X[o2, 2] - ez) / L
            print('%-8s through %-9s %-5s %5d vertices, depth p90 %.4f max %.4f L; x %.2f..%.2f z %.2f..%.2f' % (
                un, ov, side, o2.sum(), np.percentile(sd[o2], 90), sd[o2].max(), xs.min(), xs.max(), zs.min(), zs.max()))
    else:
        print('%-8s through %-9s none' % (un, ov))
