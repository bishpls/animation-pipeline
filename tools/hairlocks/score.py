"""Lock scores: a build's locks, the structure labeller's lock regions, the truth against itself and a shuffled
partition (the calibration), against the lock truth, per view.

    python tools/hairlocks/score.py OUT.json [NAME=BUILD_LOCKS.npz ...]
  BUILD_LOCKS.npz: tools/hairlocks/ours.py's (a build's locks on the design grids)
"""
import json, os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ctx as cx, ours as ou
from charkit import hairlocks as hk
from charkit.bodyqa import CLASS


def fillable(C):
    return {v: C['hair'][v] | (C['dv'][v]['raw'] == CLASS['line']) for v in C['hair']}


def run(sets, out=None):
    C = cx.make()
    T = hk.load_truth('charkit/refs/clawd/hair_locks_truth.npz')
    hair = fillable(C)
    ppl = T[2]['ppl']
    res = {}
    res['truth'] = hk.score({v: np.where(hk.fill_walls(t, hair[v]) >= 0, hk.fill_walls(t, hair[v]) + 1, 0)
                             for v, t in T[0].items()}, T, hair, ppl)
    sh = [hk.score({v: hk.shuffled(hk.fill_walls(t, hair[v]), s) for v, t in T[0].items()}, T, hair, ppl)
          for s in range(5)]
    res['shuffled'] = {v: {k: round(float(np.mean([x[v][k] for x in sh])), 3) for k in ('lock_iou', 'lock_iou_in', 'purity')}
                       for v in sh[0]}
    res['shuffled_0'] = sh[0]
    res['labeller'] = hk.score({v: hk.fill_labels(C['regions'][v], hair[v]) for v in T[0]}, T, hair, ppl)
    for name, path in sets:
        img, names, ppl_o = ou.load(path)
        res[name] = hk.score(img, T, hair, ppl, names)
    if out:
        json.dump(res, open(out, 'w'), indent=1)
    return res


def table(res):
    rows = []
    for name, r in res.items():
        if name == 'shuffled_0':
            continue
        for v in ('front', 'three_quarter', 'profile', 'all'):
            if v not in r:
                continue
            x = r[v]
            rows.append('%-10s %-14s locks %s ours %-24s matched %-3s lockIoU %.3f in %.3f  bnd %s  line %s  tip %s  tipw %s  purity %.3f  merge %s' % (
                name, v, x.get('truth_locks', '-'), json.dumps(x.get('count_ours', '-')), x.get('matched', '-'),
                x['lock_iou'], x.get('lock_iou_in', 0), x.get('boundary_L'), x.get('line_L'), x.get('tip_L'), x.get('tip_width_L'),
                x['purity'], x.get('best_merge_iou')))
    return '\n'.join(rows)


if __name__ == '__main__':
    a = sys.argv[1:]
    res = run([q.split('=', 1) for q in a[1:]], a[0])
    print(table(res))
