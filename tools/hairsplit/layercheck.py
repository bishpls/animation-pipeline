"""The layer order's sanity against the truth's families: each T-junction vote (front lock F in front of B) between two
of our locks matched to truth locks of different families, read against the drawing's evident order per view (front,
three-quarter, profile: the bangs over the side locks, the side locks over the lower back and the flyaways' roots;
the back: the flyaways over the lower back). Reports the votes and their agreement; no truth of the layering exists,
so this is a coarse check, not a score.

    python tools/hairsplit/layercheck.py OUT.json
"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
from charkit import hairsplit as hs, hairlocks as hk
import dev

ORDER = {'bangs': 3, 'side_locks': 2, 'flyaways': 1, 'lower_back': 1, 'ahoge': 0}

if __name__ == '__main__':
    out = sys.argv[1]
    I = dev.load_inputs()
    T = hk.load_truth('charkit/refs/clawd/hair_locks_truth.npz')
    splits, shell, xid, matches = hs.split_views(I, log=lambda *x: None)
    r = hs.score(hs.lock_images(splits), T)
    res = {}
    agree = total = 0
    for v, S in splits.items():
        fam = {}
        for q, x in r[v]['locks'].items():
            if x.get('ours') is not None and x['iou'] >= 0.3:
                fam[int(x['ours'])] = hk.family_of(q)
        n = len(S.layer_votes)
        judged = [(a, b, w) for (a, b), w in S.layer_votes.items() if a in fam and b in fam and fam[a] != fam[b]
                  and ORDER[fam[a]] != ORDER[fam[b]]]
        ok = sum(w for a, b, w in judged if ORDER[fam[a]] > ORDER[fam[b]])
        tot = sum(w for a, b, w in judged)
        agree += ok; total += tot
        res[v] = dict(t_junctions=S.report.get('t_junctions'), near_t=S.report.get('near_t'), votes=n,
                      judged=tot, agree=ok, pairs=[[fam[a], fam[b], w] for a, b, w in judged])
        print('%-14s T-junctions %s, near-T %s, votes %d; between truth families %d, agreeing with the drawn order %d'
              % (v, S.report.get('t_junctions'), S.report.get('near_t'), n, tot, ok))
    print('all: %d of %d agree' % (agree, total))
    json.dump(res, open(out, 'w'), indent=1)
