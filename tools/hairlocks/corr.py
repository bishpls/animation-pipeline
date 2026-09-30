"""Correspondence across views, measured: the drawn locks (the lock truth) read back onto our bangs surface. Each bangs
triangle takes, in each view that shows it (2 px or more), the truth lock most of its pixels lie in; over the
triangles two views both label, the share whose labels agree (the same lock name), and the confusions. Our surface is
the 3D proxy, so its own misfit (the lock IoU) reads as disagreement too: the floor for lifting the drawn locks into 3D
through the hull without a per-view reconciliation.

    python tools/hairlocks/corr.py BUILD OUT.json
"""
import json, os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ctx as cx, score as sc, wedge as wd
from charkit import hairlocks as hk

if __name__ == '__main__':
    build, out = sys.argv[1], sys.argv[2]
    C = cx.make()
    T, TL, meta = hk.load_truth('charkit/refs/clawd/hair_locks_truth.npz')
    hair = sc.fillable(C)
    S = wd.setup(build)
    n = len(S['ph'])
    lab = {}
    for v, t in S['tri'].items():
        f = hk.fill_walls(T[v], hair[v])
        m = (t >= 0) & (f >= 0)
        names = np.array(TL[v] + ['-'], object)
        k = len(TL[v])
        cnt = np.zeros((n, k + 1), np.int32)
        np.add.at(cnt, (t[m], f[m]), 1)
        tot = cnt.sum(1)
        best = cnt.argmax(1)
        L = np.where(tot >= 2, names[best], None)
        lab[v] = L
    res = {}
    views = list(lab)
    for i, a in enumerate(views):
        for b in views[i + 1:]:
            both = np.array([x is not None and y is not None for x, y in zip(lab[a], lab[b])])
            if not both.any():
                continue
            agree = np.array([x == y for x, y in zip(lab[a][both], lab[b][both])])
            pairs = {}
            for x, y in zip(lab[a][both], lab[b][both]):
                pairs['%s|%s' % (x, y)] = pairs.get('%s|%s' % (x, y), 0) + 1
            # weigh each triangle by its surface area in chart degrees (ph, th spread): count triangles
            res['%s~%s' % (a, b)] = dict(triangles=int(both.sum()), agree=round(float(agree.mean()), 3),
                                         pairs=dict(sorted(pairs.items(), key=lambda kv: -kv[1])[:12]))
            print(a, b, res['%s~%s' % (a, b)])
    json.dump(res, open(out, 'w'), indent=1)
