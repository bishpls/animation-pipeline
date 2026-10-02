"""art_terminator_hair / art_peeks_hair under sub-pixel placements of the head frame (charkit.render.calibrate's
offsets): the checks' own sampling noise on a build (or a build with a pieces dir spliced in)."""
import sys, os, json
import numpy as np
from charkit import bundle, artifactqa, lookqa, qa3d
from charkit.render.calibrate import OFFSETS

def reading(B, off):
    frame = artifactqa._frame
    artifactqa._frame = lambda B_, ppl, win: lookqa.HeadFrame(B_, ppl=ppl, ss=1, win=win, off=off)
    try:
        _, C = artifactqa.measure(B, qa3d.Design(B), None)
    finally:
        artifactqa._frame = frame
    return {k: (C[k]['value'], C[k].get('per_view')) for k in ('terminator_hair', 'peeks_hair') if k in C} or \
        {k[4:]: (C[k]['value'], C[k].get('per_view')) for k in ('art_terminator_hair', 'art_peeks_hair') if k in C}

if __name__ == '__main__':
    b = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    B = bundle.load(os.path.join(b, 'bundle'))
    if len(sys.argv) > 3:
        sys.path.insert(0, os.path.dirname(__file__))
        from splice2x2 import splice
        B = splice(B, sys.argv[3])
    R = []
    for off in OFFSETS[:n]:
        r = reading(B, off)
        R.append(r)
        print(off, json.dumps(r), flush=True)
    for k in R[0]:
        v = np.array([r[k][0] for r in R], float)
        pv = {vn: np.array([r[k][1][vn] for r in R], float) for vn in R[0][k][1]}
        print('%s: mean %.3f std %.3f (min %.3f max %.3f); per view mean/std %s' % (
            k, v.mean(), v.std(), v.min(), v.max(), {vn: (round(x.mean(), 3), round(x.std(), 3)) for vn, x in pv.items()}))
