"""where our skin shows in the shoulder window per view (pieceqa.our_labels), and the objects' top heights at the
shoulder: python tools/garments5/skinpeek.py BUILD.."""
import sys, os, json
sys.path.insert(0, '.')
import numpy as np
from charkit import bundle, qa3d, bodyqa, pieceqa

WIN = (-0.42, -0.75, 0.12, 0.75)       # z top, z bottom, |x| from, to
for b in sys.argv[1:]:
    B = bundle.load(b + '/bundle')
    D = qa3d.Design(B)
    ctx = D.sheet_context()
    ppl = ctx['ppl']
    O, names = pieceqa.our_labels(B, ppl, ctx['az3'])
    W = bodyqa.WIN
    print('==', os.path.basename(b))
    for v, o in O.items():
        lab = o['lab']
        r0, r1 = int((W['top'] - WIN[0]) * ppl), int((W['top'] - WIN[1]) * ppl)
        cs = np.arange(lab.shape[1]); xs = (cs + 0.5) / ppl - W['x']
        cm = (np.abs(xs) >= WIN[2]) & (np.abs(xs) <= WIN[3])
        sub = lab[r0:r1][:, cm]
        out = {}
        for i, n in enumerate(names):
            k = int((sub == i).sum())
            if k:
                out[n] = round(k / ppl ** 2, 4)
        skin = [n for n in names if 'skin' in n]
        sk = sum(out.get(n, 0) for n in skin)
        # where: rows of skin pixels
        rows = np.nonzero(np.isin(sub, [names.index(n) for n in skin]))[0]
        zr = (round(W['top'] - (r0 + rows.min() + 0.5) / ppl, 3), round(W['top'] - (r0 + rows.max() + 0.5) / ppl, 3)) if len(rows) else None
        print('  %-13s skin %.4f L^2 at z %s | %s' % (v, sk, zr, {k: v_ for k, v_ in sorted(out.items(), key=lambda t: -t[1])[:8]}))
    L = float(B.assembly['L']); iris = np.array(qa3d.iris_centres(B)); ez = iris[:, 2].mean()
    for o in B.objects():
        if o.name.split('_')[-1] in ('skin',) or o.name in ('top', 'collar', 'sleeve_L', 'sleeve_R', 'clawd_skin') or o.group == 'skin':
            V = o.V('eval')
            if V is None:
                continue
            x = V[:, 0] / L; z = (V[:, 2] - ez) / L
            row = []
            for a, c in ((0.15, 0.25), (0.25, 0.35), (0.35, 0.45), (0.45, 0.55)):
                m = (np.abs(x) >= a) & (np.abs(x) < c) & (z < -0.40) & (z > -0.8)
                row.append(round(float(z[m].max()), 3) if m.any() else None)
            print('  top z by |x| band 0.15-0.25/0.25-0.35/0.35-0.45/0.45-0.55: %-18s %s' % (o.name, row))
