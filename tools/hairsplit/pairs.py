"""What tells a right merge from a wrong one: every pair of adjacent regions (both mostly on the truth's scored locks)
with its features and the oracle's verdict (same truth lock or not). A probe for choosing the merge rule.

    python tools/hairsplit/pairs.py OUT.json [--set K=V ...]
"""
import json, math, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
from charkit import hairsplit as hs, hairlocks as hk
import dev


def pair_features(S, t):
    from scipy import ndimage
    R = S._grow(S.regions, S.H)
    ids = [int(i) for i in np.unique(R[R > 0])]
    truth_of, share = {}, {}
    for i in ids:
        m = R == i
        tt = t[m]
        ok = tt >= 0
        share[i] = ok.mean()
        truth_of[i] = int(np.bincount(tt[ok]).argmax()) if ok.any() else -1
    # adjacency over the walls: pixels within 2 px across
    out = []
    lk = S.lockwalls
    for i in ids:
        if share[i] < 0.5:
            continue
        mi = R == i
        ring = ndimage.binary_dilation(mi, iterations=3) & ~mi
        nb, cnt = np.unique(R[ring], return_counts=True)
        for j, n in zip(nb, cnt):
            j = int(j)
            if j <= i or j == 0 or share.get(j, 0) < 0.5 or n < 6:
                continue
            mj = R == j
            # the shared boundary: pixels of i next to j
            bd = mi & ndimage.binary_dilation(mj, iterations=3)
            bd |= mj & ndimage.binary_dilation(mi, iterations=3)
            zone = ndimage.binary_dilation(bd, iterations=1)
            ink = float((S.ink & zone).sum() / max(1, zone.sum()))
            ext = float((S.ext & zone).sum() / max(1, zone.sum()))
            # the boundary's direction against the flow (PCA of the shared boundary)
            rr, cc = np.nonzero(bd)
            X = np.stack([rr, cc], 1).astype(float); X -= X.mean(0)
            w, v = np.linalg.eigh(X.T @ X)
            tng = v[:, -1]
            f = S.down[:, rr, cc].mean(1); f /= max(1e-9, np.hypot(*f))
            along = abs(float(tng @ f))
            elong = float(math.sqrt(max(w[-1], 1e-9) / max(w[0], 1e-9)))
            # which lies downstream: the centroid offset along the flow
            ci, cj = np.array(np.nonzero(mi)).mean(1), np.array(np.nonzero(mj)).mean(1)
            dflow = float((cj - ci) @ f) / S.ppl
            same = truth_of[i] == truth_of[j] and truth_of[i] >= 0
            out.append(dict(view=S.view, i=i, j=j, same=bool(same), ink=round(ink, 3), ext=round(ext, 3),
                            along=round(along, 3), elong=round(elong, 2), bpx=int(bd.sum()), dflow=round(dflow, 3),
                            ai=int(mi.sum()), aj=int(mj.sum()), merged=bool(np.bincount(S.locks[mi]).argmax() ==
                                                                          np.bincount(S.locks[mj]).argmax())))
    return out


if __name__ == '__main__':
    a = sys.argv[1:]
    params = {}
    for i, q in enumerate(a):
        if q == '--set':
            k, v = a[i + 1].split('=')
            params[k] = json.loads(v)
    I = dev.load_inputs()
    T = hk.load_truth('charkit/refs/clawd/hair_locks_truth.npz')
    allp = []
    for name, V in I['views'].items():
        S = hs.Split(name, V, I['ppl'], params)
        S.pipeline()
        r0, r1, c0, c1 = S.box
        t = hk.fill_walls(T[0][name], np.ones(T[0][name].shape, bool))[r0:r1, c0:c1]
        allp += pair_features(S, t)
    json.dump(allp, open(a[0], 'w'), indent=0)
    import collections
    print('pairs', len(allp), 'same', sum(p['same'] for p in allp))
    print('ours merged: TP %d FP %d FN %d TN %d' % (
        sum(p['same'] and p['merged'] for p in allp), sum((not p['same']) and p['merged'] for p in allp),
        sum(p['same'] and not p['merged'] for p in allp), sum((not p['same']) and not p['merged'] for p in allp)))
    for key in ('ink', 'ext', 'along', 'elong', 'bpx'):
        s = [p[key] for p in allp if p['same']]; d = [p[key] for p in allp if not p['same']]
        print('%-6s same: median %.3f (q25 %.3f q75 %.3f)   differ: median %.3f (q25 %.3f q75 %.3f)' % (
            key, np.median(s), np.percentile(s, 25), np.percentile(s, 75), np.median(d), np.percentile(d, 25),
            np.percentile(d, 75)))
