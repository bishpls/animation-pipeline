"""the side locks' stability under an edit elsewhere (the coordinator's item, 2026-09-30: a face-only edit moved
side_lock_L's tips 38/58/74 -> 34/58/82 deg through the hull's labels): two builds' side locks compared, each lock's
tip phi (the builder's report) and, per view (front, three-quarter, profile), each lock of A z-buffered on the design
grids against its best match in B (IoU); the worst lock's IoU and the largest tip move.

    python tools/hair5/stability.py BUILD_A BUILD_B [--pieces side_lock_L,side_lock_R]
"""
import json, os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from charkit import hairlocks as hk


def tips(build, pieces):
    P = json.load(open(os.path.join(build, 'geom', 'hair_pieces', 'pieces.json')))
    rep = P['report']['pieces']
    return {p: rep.get(p, {}).get('tips_deg') for p in pieces}


def lock_imgs(build, pieces):
    img, names, ppl = hk.build_locks(build)
    return img, names


if __name__ == '__main__':
    a, b = sys.argv[1], sys.argv[2]
    pieces = (sys.argv[sys.argv.index('--pieces') + 1].split(',') if '--pieces' in sys.argv
              else ['side_lock_L', 'side_lock_R'])
    ta, tb = tips(a, pieces), tips(b, pieces)
    out = {'tips': {p: [ta[p], tb[p]] for p in pieces}}
    moves = [abs(x - y) for p in pieces if ta[p] and tb[p] and len(ta[p]) == len(tb[p]) for x, y in zip(ta[p], tb[p])]
    out['tip_move_max_deg'] = max(moves) if moves else None
    out['lock_counts'] = {p: [len(ta[p] or []), len(tb[p] or [])] for p in pieces}
    IA, NA = lock_imgs(a, pieces)
    IB, NB = lock_imgs(b, pieces)
    worst = {}
    for v in ('front', 'three_quarter', 'profile'):
        if v not in IA or v not in IB:
            continue
        for code, name in NA.items():
            if not any('/%s.' % p in name for p in pieces):
                continue
            m = IA[v] == code
            if m.sum() < 30:
                continue
            best = 0.0
            for c2, n2 in NB.items():
                if n2.split('.')[0] != name.split('.')[0]:
                    continue
                q = IB[v] == c2
                best = max(best, float((m & q).sum() / max(1, (m | q).sum())))
            worst.setdefault(v, []).append((round(best, 3), name))
    out['lock_iou'] = {v: sorted(x)[:3] for v, x in worst.items()}
    out['worst_lock_iou'] = min((x[0][0] for x in [sorted(w) for w in worst.values()] if x), default=None)
    print(json.dumps(out, indent=1))
