"""art_terminator_hair / art_peeks_hair over six sub-pixel placements of the head frame (charkit.render.calibrate's
OFFSETS; the hair worktrees' term6: the checks' own sampling noise) for each build given.
    python tools/acc6/term6.py [LABEL=]BUILD ... [--json OUT]"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
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
    return {k[4:]: (C[k]['value'], C[k].get('per_view')) for k in ('art_terminator_hair', 'art_peeks_hair') if k in C} or \
        {k: (C[k]['value'], C[k].get('per_view')) for k in ('terminator_hair', 'peeks_hair') if k in C}


a = sys.argv[1:]
js = None
if '--json' in a:
    i = a.index('--json'); js = a[i + 1]; del a[i:i + 2]
res = {}
for x in a:
    lab, d = x.split('=', 1) if '=' in x else (os.path.basename(x.rstrip('/')), x)
    B = bundle.load(os.path.join(d, 'bundle'))
    R = [reading(B, off) for off in OFFSETS[:6]]
    out = {}
    for k in R[0]:
        v = np.array([r[k][0] for r in R], float)
        pv = {vn: round(float(np.mean([r[k][1][vn] for r in R])), 3) for vn in (R[0][k][1] or {})}
        out[k] = dict(place=R[0][k][0], values=[round(float(x), 3) for x in v], mean=round(float(v.mean()), 3),
                      std=round(float(v.std()), 3), views=pv)
    res[lab] = out
    t = out.get('terminator_hair', {})
    print('%-14s terminator %s / %.3f +- %.3f  per view %s | peeks %s' % (
        lab, t.get('place'), t.get('mean', float('nan')), t.get('std', float('nan')), t.get('views'),
        out.get('peeks_hair', {}).get('mean')), flush=True)
if js:
    os.makedirs(os.path.dirname(os.path.abspath(js)), exist_ok=True)
    json.dump(res, open(js, 'w'), indent=1)
