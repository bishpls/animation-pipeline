"""Per truth lock: the matched lock's IoU at each stage of a dev run (tools/hairsplit/dev.py --save).

    python tools/hairsplit/perlock.py RUN_DIR [VIEW]
"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from charkit import hairlocks as hk, hairsplit as hs

if __name__ == '__main__':
    run = sys.argv[1]
    views = sys.argv[2:] or None
    Z = np.load(os.path.join(run, 'stages.npz'))
    T = hk.load_truth('charkit/refs/clawd/hair_locks_truth.npz')
    stages = sorted({k.split('__')[0] for k in Z.files})
    res = {}
    for st in stages:
        imgs = {k.split('__')[1]: Z[k] for k in Z.files if k.startswith(st + '__')}
        res[st] = hs.score(imgs, T)
    for v in T[0]:
        if views and v not in views:
            continue
        print('==', v)
        if v not in res[stages[0]]:
            continue
        for q in T[1][v]:
            print('  %-24s %s' % (q, '  '.join('%s %.2f' % (st[:5], res[st][v]['locks'][q]['iou']) for st in stages)))
