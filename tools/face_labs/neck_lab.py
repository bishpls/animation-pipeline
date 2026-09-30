"""the neck lab: assemble the authored spec with the face worktree's code and a build's head and body code, subdivide
it as the bundle's eval mesh is (charkit.subdiv, 1 level: the viewport's), and measure the join's crease as the QA does, with the side and 45
degree columns' radius per height.
    python neck_lab.py BUILD_GEOM_DIR"""
import json, math, os, sys
sys.path.insert(0, os.path.expanduser('~/animation-pipeline-face'))
import numpy as np
from charkit import character, manifest, subdiv, faceregion as fr

g = sys.argv[1]
spec = manifest.resolve(json.load(open(os.path.expanduser('~/animation-pipeline-face/charkit/spec/clawd_body.json'))))
spec['head_code'] = os.path.join(g, 'head_code.npz'); spec['body_code'] = os.path.join(g, 'body_code.npz')
A = character.assemble(spec, keys=False)
V0 = np.asarray(A['verts'], float); c = np.asarray(A['head']['centre']); L = A['head']['L']
zc = c[2] + fr.CUT * L
# only the neck's neighbourhood, subdivided (the faces touching the band, closed enough for the band's interior)
band = (V0[:, 2] > zc - 0.35 * L) & (V0[:, 2] < zc + 0.3 * L)
F = [f for f in A['faces'] if band[list(f)].all()]
used = sorted({v for f in F for v in f}); re = {o: n for n, o in enumerate(used)}
Vs, Fs = subdiv.catmull_clark(V0[used], [tuple(re[v] for v in f) for f in F], levels=1)[:2]
Vs = np.asarray(Vs, float)
K = fr.crease_of(Vs, c, L)
print('crease max %.1f median %.1f worst col %s' % (K['max'], K['median'], K['worst']))
q = Vs[:, :2] - Vs[np.abs(Vs[:, 2] - zc) < 0.02 * L][:, :2].mean(0)
th = np.degrees(np.arctan2(q[:, 0], -q[:, 1])); r = np.hypot(q[:, 0], q[:, 1])
for deg in (0, 45, 90, 135):
    m = np.abs(((th - deg + 180) % 360) - 180) < 3
    zz = (Vs[m, 2] - zc) / L; rr = r[m] / L
    out = []
    for z in np.arange(0.12, -0.16, -0.02):
        s = np.abs(zz - z) < 0.006
        out.append('%.3f' % rr[s].max() if s.any() else '  -  ')
    print('%4d' % deg, ' '.join(out))
print('   z', ' '.join('%5.2f' % z for z in np.arange(0.12, -0.16, -0.02)))
if os.environ.get('RAW'):
    q0 = V0[:, :2] - V0[np.abs(V0[:, 2] - zc) < 0.02 * L][:, :2].mean(0)
    t0 = np.degrees(np.arctan2(q0[:, 0], -q0[:, 1])); r0 = np.hypot(q0[:, 0], q0[:, 1])
    for deg in [int(d) for d in os.environ['RAW'].split(',')]:
        m = (np.abs(((t0 - deg + 180) % 360) - 180) < 4) & (np.abs(V0[:, 2] - zc) < 0.25 * L)
        zz = (V0[m, 2] - zc) / L; o = np.argsort(-zz)
        print('raw %d:' % deg, ' '.join('%.3f:%.3f' % (a, b) for a, b in zip(zz[o], r0[m][o] / L)))
if os.environ.get('RINGS'):
    q0 = V0[:, :2] - V0[np.abs(V0[:, 2] - zc) < 0.02 * L][:, :2].mean(0)
    t0 = np.degrees(np.arctan2(q0[:, 0], -q0[:, 1])); r0 = np.hypot(q0[:, 0], q0[:, 1])
    for z in [float(v) for v in os.environ['RINGS'].split(',')]:
        m = (np.abs((V0[:, 2] - zc) / L - z) < 0.004) & (np.abs(t0) < 40)
        o = np.argsort(t0[m])
        print('ring %.3f:' % z, ' '.join('%.0f:%.3f' % (a, b) for a, b in zip(t0[m][o], r0[m][o] / L)))
