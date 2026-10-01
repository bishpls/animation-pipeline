"""Ceilings: a partition's best possible lock score when its parts are merged by an oracle (each part to the truth lock
it overlaps most, else its own) -- what a perfect merge could reach from the cells or the regions. A probe, never a
splitter's source.

    python tools/hairsplit/oracle.py [--set K=V ...]
"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
from charkit import hairsplit as hs, hairlocks as hk
import dev


def oracle(parts, t):
    out = np.zeros(parts.shape, np.int32)
    nxt = 1000
    for p in np.unique(parts[parts > 0]):
        m = parts == p
        tt = t[m]
        tt = tt[tt >= 0]
        if len(tt) and len(tt) >= 0.5 * m.sum():
            out[m] = np.bincount(tt).argmax() + 1
        else:
            out[m] = nxt; nxt += 1
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
    sets = {}
    for name, V in I['views'].items():
        S = hs.Split(name, V, I['ppl'], params)
        S.pipeline()
        r0, r1, c0, c1 = S.box
        t = hk.fill_walls(T[0][name], np.ones(T[0][name].shape, bool))[r0:r1, c0:c1]
        for k, parts in (('cells', S.cells), ('regions', S._grow(S.regions, S.H)), ('locks', S.locks)):
            sets.setdefault(k + ' (as is)', {})[name] = S.full(parts.astype(np.int32))
            sets.setdefault(k + ' (oracle merge)', {})[name] = S.full(oracle(parts, t))
    for k, x in sets.items():
        r = hs.score(x, T)
        print('%-24s all %.3f  %s  |  %s' % (k, r['all']['lock_iou'], ' '.join('%s %.3f' % (v[:5], r[v]['lock_iou']) for v in hs.VIEWS),
                                            ' '.join('%s %.2f' % (f[:5], y['lock_iou']) for f, y in r['all']['families'].items())))
