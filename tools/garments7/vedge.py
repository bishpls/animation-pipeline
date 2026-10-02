"""the jacket's V edge in front view (fast evaluator, the build's spec + variants): the jacket alone z-buffered on a
fine grid over the V window; per row the innermost jacket column each side (the opening's visible edge) and its
roughness: the 95th percentile of the edge's distance from its own smoothed self (L), the count of rows where it steps
by more than 0.01 L; plus the jacket vertices inside the opening (as vjacket).
    python tools/garments7/vedge.py BUILD [--var NAME 'PATH=JSON;..' ..] [--png OUT.png]"""
import sys, os, json
sys.path.insert(0, '.')
import numpy as np
from scipy import ndimage
from charkit import sweep, bodyeval, garments as gm
from charkit.geom import raster
args = sys.argv[1:]
PNG = None
if '--png' in args:
    i = args.index('--png'); PNG = args[i + 1]; del args[i:i + 2]
build = args[0]
vars_ = [('as built', '')]
while '--var' in args:
    i = args.index('--var'); vars_.append((args[i + 1], args[i + 2])); del args[i:i + 3]
B0 = sweep.load_bundle(build, True)
spec0 = sweep.base_spec({'base': build, 'stage': 'garments'}, B0)
pics = []
for name, sets in vars_:
    spec = json.loads(json.dumps(spec0))
    for s in [s for s in sets.split(';') if s]:
        p, v = s.split('=', 1)
        bodyeval.set_knob(spec, p, json.loads(v))
    E = bodyeval.Evaluator(spec); A, _ = E.assembly(spec); hull = gm.hull_pieces(spec, A)
    L = A['head']['L']; ez = gm._eye_z(A)
    nrm = gm.vertex_normals(A['verts'], A['faces'])
    G = {g['name']: g for g in spec['garments']}
    T = gm.shell(A, dict(G['top'], _spec=spec), nrm, hull)
    V = np.asarray(T['verts'], float)
    F = np.array([f[:3] for f in T['faces']] + [(f[0], f[2], f[3]) for f in T['faces'] if len(f) == 4])
    # front view: x right, z up; nearest = least y. Rasterise on a grid (L units from the midline and the eye line)
    ppl = 800
    x0, x1, z0, z1 = -0.25, 0.25, -0.5, -0.8
    W, H = int((x1 - x0) * ppl), int((z0 - z1) * ppl)
    P2 = np.c_[(V[:, 0] / L - x0) * ppl, (z0 - (V[:, 2] - ez) / L) * ppl]
    front = (V[:, 1] < np.median(V[:, 1]))
    Fm = F[front[F].all(1)]
    cov = np.zeros((H, W), bool)
    yy, xx = np.mgrid[0:H, 0:W] + 0.5
    for tri in Fm:
        p = P2[tri]
        lo = np.floor(p.min(0)).astype(int); hi = np.ceil(p.max(0)).astype(int)
        if hi[0] < 0 or hi[1] < 0 or lo[0] >= W or lo[1] >= H:
            continue
        lo = np.maximum(lo, 0); hi = np.minimum(hi, [W, H])
        X_, Y_ = xx[lo[1]:hi[1], lo[0]:hi[0]], yy[lo[1]:hi[1], lo[0]:hi[0]]
        (a, b, c) = p
        d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(d) < 1e-12:
            continue
        l1 = ((b[1] - c[1]) * (X_ - c[0]) + (c[0] - b[0]) * (Y_ - c[1])) / d
        l2 = ((c[1] - a[1]) * (X_ - c[0]) + (a[0] - c[0]) * (Y_ - c[1])) / d
        cov[lo[1]:hi[1], lo[0]:hi[0]] |= (l1 >= 0) & (l2 >= 0) & (1 - l1 - l2 >= 0)
    mid = W // 2
    rows = []
    for side, sl in (('right', cov[:, mid:]), ('left', cov[:, :mid][:, ::-1])):
        e = np.array([np.argmax(r) if r.any() else np.nan for r in sl], float) / ppl
        ok = np.isfinite(e)
        es = e.copy(); es[ok] = ndimage.gaussian_filter1d(e[ok], 6)
        dev = np.abs(e - es)[ok]
        steps = (np.abs(np.diff(e[ok])) > 0.01).sum()
        rows.append('%s: rough p95 %.4f L, steps > 0.01 L %d' % (side, np.percentile(dev, 95) if len(dev) else np.nan, steps))
    op = gm.opening_cut(A, G['top']['opening']); yc = gm.bone_seg(A, 'chest')[0][1]
    z = (V[:, 2] - ez) / L
    ins = (np.abs(V[:, 0]) - np.interp(z, *np.asarray(sorted(G['top']['opening']['half'])).T) * L < -0.005 * L) & (V[:, 1] < yc) & (z > -0.75) & (z < -0.45)
    print('== %-20s inside the opening %3d | %s' % (name, ins.sum(), ' | '.join(rows)))
    pics.append((name, cov))
if PNG:
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, len(pics), figsize=(4 * len(pics), 3.4))
    for a_, (n, c) in zip(np.atleast_1d(ax), pics):
        a_.imshow(c, extent=[x0, x1, z1, z0], cmap='Oranges'); a_.set_title(n, fontsize=9); a_.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(PNG, dpi=90); print(PNG)
