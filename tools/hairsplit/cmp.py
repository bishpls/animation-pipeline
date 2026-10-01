"""Per truth lock, the locks stage of several parameter variants side by side (sweep.py's form).

    python tools/hairsplit/cmp.py VIEW 'NAME:K=V,...' ...
"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
from charkit import hairsplit as hs, hairlocks as hk
import dev

if __name__ == '__main__':
    a = sys.argv[1:]
    views = a[0].split(',')
    I = dev.load_inputs()
    T = hk.load_truth('charkit/refs/clawd/hair_locks_truth.npz')
    cols = []
    for spec in a[1:]:
        name, _, kv = spec.partition(':')
        params = {}
        for q in filter(None, kv.split(',')):
            k, v = q.split('=')
            params[k] = json.loads(v)
        imgs = {}
        for v in views:
            S = hs.Split(v, I['views'][v], I['ppl'], params)
            S.pipeline()
            imgs[v] = S.full(S.locks.astype(np.int32))
        cols.append((name, hs.score(imgs, T)))
    for v in views:
        print('==', v, '  '.join('%s %.3f' % (n, r[v]['lock_iou']) for n, r in cols))
        for q in T[1][v]:
            print('  %-24s %s' % (q, '  '.join('%8.2f' % r[v]['locks'][q]['iou'] for n, r in cols)))
