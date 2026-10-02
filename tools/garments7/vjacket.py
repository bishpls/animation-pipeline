"""the jacket inside its own V opening: the front jacket vertices (y before the chest's head) whose |x| is less than the
opening's half-width at their height, per --set variant, and where (z bands); the jacket built by garments.shell on the
fast evaluator's assembly at the build's spec.
    python tools/garments7/vjacket.py BUILD [--var NAME 'PATH=JSON;PATH=JSON' ..]"""
import sys, os, json
sys.path.insert(0, '.')
import numpy as np
from charkit import sweep, bodyeval, garments as gm, qa3d
args = sys.argv[1:]
build = args[0]
vars_ = [('as built', '')]
while '--var' in args:
    i = args.index('--var'); vars_.append((args[i + 1], args[i + 2])); del args[i:i + 3]
B0 = sweep.load_bundle(build, True)
spec0 = sweep.base_spec({'base': build, 'stage': 'garments'}, B0)
for name, sets in vars_:
    spec = json.loads(json.dumps(spec0))
    for s in [s for s in sets.split(';') if s]:
        p, v = s.split('=', 1)
        bodyeval.set_knob(spec, p, json.loads(v))
    E = bodyeval.Evaluator(spec)
    A, how = E.assembly(spec)
    hull = gm.hull_pieces(spec, A)
    L = A['head']['L']
    ez = gm._eye_z(A)
    nrm = gm.vertex_normals(A['verts'], A['faces'])
    G = {g['name']: g for g in spec['garments']}
    T = gm.shell(A, dict(G['top'], _spec=spec), nrm, hull)
    V = np.asarray(T['verts'], float)
    op = gm.opening_cut(A, G['top']['opening'])
    yc = gm.bone_seg(A, 'chest')[0][1]
    z = (V[:, 2] - ez) / L
    inside = (op(V) < -0.005 * L) & (V[:, 1] < yc) & (z > -0.75) & (z < -0.45)
    print('== %s: jacket vertices inside the opening (by > 0.005 L): %d' % (name, inside.sum()))
    for z0 in np.arange(-0.45, -0.75, -0.05):
        m = inside & (z <= z0) & (z > z0 - 0.05)
        if m.any():
            print('   z %.2f..%.2f: %3d  |x| %.3f..%.3f  depth into the opening p50 %.3f L' % (
                z0, z0 - 0.05, m.sum(), np.abs(V[m, 0]).min() / L, np.abs(V[m, 0]).max() / L, np.median(-op(V[m])) / L))
