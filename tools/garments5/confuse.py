"""per view, in the upper body window (z -0.35..-1.25), the drawn piece under each of our labels: the pixels (L^2) where
drawn piece X shows our object Y, for the pairs that moved between two builds: python tools/garments5/confuse.py A B"""
import sys, os
sys.path.insert(0, '.')
import numpy as np
from charkit import bundle, qa3d, bodyqa, declared

def conf(b):
    B = bundle.load(b + '/bundle')
    D = qa3d.Design(B)
    I = declared.inputs(B, D)
    ppl = I['ppl']; W = bodyqa.WIN
    r0, r1 = int((W['top'] + 0.35) * ppl), int((W['top'] + 1.25) * ppl)
    out = {}
    pieces = sorted({k.split('__', 1)[1] for k in I['masks']})
    for v, o in I['O'].items():
        lab = o['lab']
        names = I['names']
        dl = np.full(lab.shape, '', object)
        for p in pieces:
            m = I['masks'].get('%s__%s' % (v, p))
            if m is None:
                continue
            m = declared.fit(m, lab.shape)
            dl[m & (dl == '')] = p
        sub_l, sub_d = lab[r0:r1], dl[r0:r1]
        for i, n in enumerate(names + ['(none)']):
            mk = (sub_l == i) if i < len(names) else (sub_l < 0)
            if not mk.any():
                continue
            ds, cnt = np.unique(sub_d[mk], return_counts=True)
            for d_, c_ in zip(ds, cnt):
                out[(v, d_ or '(bg)', n)] = c_ / ppl ** 2
    return out

a, b = conf(sys.argv[1]), conf(sys.argv[2])
rows = []
for k in set(a) | set(b):
    d = b.get(k, 0) - a.get(k, 0)
    if abs(d) > 0.003:
        rows.append((k, a.get(k, 0), b.get(k, 0), d))
for (v, dp, ob), x, y, d in sorted(rows, key=lambda r: (r[0][0], -abs(r[3]))):
    print('%-13s drawn %-16s ours %-18s %.4f -> %.4f (%+.4f)' % (v, dp, ob, x, y, d))
