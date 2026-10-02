"""the collar alone (garments.collar_hull at a build's spec + variants, the fast evaluator's assembly), drawn in the
front and three-quarter views (faces shaded by how they face the camera; folded faces, facing away, red) over the
jacket's outline, with the crumple measured: the share of the front panel's area (|x| < 0.45, z -0.42..-0.8) in folded
faces, and its front-view area.
    python tools/garments7/lapelview.py BUILD OUT.png [--var NAME 'PATH=JSON;..' ..]"""
import sys, os, json, math
sys.path.insert(0, '.')
import numpy as np
from charkit import sweep, bodyeval, garments as gm
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
args = sys.argv[1:]
build, out = args[0], args[1]
vars_ = [('as built', '')]
while '--var' in args:
    i = args.index('--var'); vars_.append((args[i + 1], args[i + 2])); del args[i:i + 3]
B0 = sweep.load_bundle(build, True)
spec0 = sweep.base_spec({'base': build, 'stage': 'garments'}, B0)
fig, ax = plt.subplots(2, len(vars_), figsize=(5 * len(vars_), 9), squeeze=False)
for c, (name, sets) in enumerate(vars_):
    spec = json.loads(json.dumps(spec0))
    for s in [s for s in sets.split(';') if s]:
        p, v = s.split('=', 1)
        bodyeval.set_knob(spec, p, json.loads(v))
    E = bodyeval.Evaluator(spec); A, _ = E.assembly(spec); hull = gm.hull_pieces(spec, A)
    L = A['head']['L']; ez = gm._eye_z(A)
    nrm = gm.vertex_normals(A['verts'], A['faces'])
    G = {g['name']: g for g in spec['garments']}
    C = gm.collar_hull(A, dict(G['collar'], _spec=spec), nrm, hull)
    V = np.asarray(C['verts'], float); F = [list(f) for f in C['faces']]
    T = gm.shell(A, dict(G['top'], _spec=spec), nrm, hull)
    Vt = np.asarray(T['verts'], float)
    for r, (vname, az) in enumerate((('front', 0.0), ('three_quarter', 35.5))):
        a = math.radians(az)
        # view: camera at -y rotated by az about z (her left toward the camera for +az)
        R = np.array([[math.cos(a), math.sin(a), 0], [-math.sin(a), math.cos(a), 0], [0, 0, 1]])
        P = (V - [0, 0, ez]) @ R.T / L
        Pt = (Vt - [0, 0, ez]) @ R.T / L
        polys, cols, depth = [], [], []
        fold_area, area = 0.0, 0.0
        for f in F:
            q = P[f]
            n = np.cross(q[1] - q[0], q[2] - q[0])
            facing = -n[1] / (np.linalg.norm(n) + 1e-12)
            xz = q[:, [0, 2]]
            cr = lambda u, v: u[0] * v[1] - u[1] * v[0]
            ar = 0.5 * abs(cr(xz[1] - xz[0], xz[2] - xz[0])) + (0.5 * abs(cr(xz[2] - xz[0], xz[3] - xz[0])) if len(f) > 3 else 0)
            cen = q.mean(0)
            front_panel = abs(cen[0]) < 0.45 and -0.8 < cen[2] < -0.42 and (V[f].mean(0)[1] < gm.bone_seg(A, 'neck')[0][1] - 0.05 * L)
            if vname == 'front' and front_panel:
                area += ar
                if facing < 0:
                    fold_area += ar
            polys.append(xz); depth.append(cen[1])
            cols.append((0.95, 0.2, 0.2) if facing < 0 else tuple(np.clip([0.55 + 0.4 * facing] * 3, 0, 1) * np.array([1.0, 0.95, 0.8])))
        o = np.argsort(depth)[::-1]
        ax[r, c].scatter(Pt[:, 0], Pt[:, 2], s=0.2, c='#e8b090', zorder=0)
        ax[r, c].add_collection(PolyCollection([polys[i] for i in o], facecolors=[cols[i] for i in o], edgecolors='none'))
        ax[r, c].set_xlim(-0.5, 0.5); ax[r, c].set_ylim(-0.85, -0.35); ax[r, c].set_aspect('equal')
        ax[r, c].set_title('%s %s' % (name, vname) + ('  folded %.0f%% of %.4f L^2' % (100 * fold_area / max(area, 1e-9), area) if vname == 'front' else ''), fontsize=8)
        if vname == 'front':
            print('%-22s front panel area %.4f L^2, folded %.1f%%' % (name, area, 100 * fold_area / max(area, 1e-9)))
fig.tight_layout(); fig.savefig(out, dpi=80); print(out)
