"""six-placement art_terminator_hair / art_peeks_hair for pieces dirs spliced into a base build (the sweep's splice,
outline_w honoured): per dir the placement-0 reading, the mean +- std and the per-view means.
    python tools/hairshell3/term6p.py BASE [LABEL=]PIECES_DIR ... [--json OUT]   (PIECES_DIR '-' = the base as built)"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from charkit import bundle
from charkit.render.calibrate import OFFSETS
from termnoise import reading
from splice2x2 import splice
a = sys.argv[1:]
js = None
if '--json' in a:
    i = a.index('--json'); js = a[i + 1]; del a[i:i + 2]
B0 = bundle.load(os.path.join(a[0], 'bundle'))
res = {}
for x in a[1:]:
    lab, d = x.split('=', 1) if '=' in x else (x, x)
    B = B0 if d == '-' else splice(B0, d)
    R = [reading(B, off) for off in OFFSETS[:6]]
    out = {}
    for k in R[0]:
        v = np.array([r[k][0] for r in R], float)
        pv = {vn: round(float(np.mean([r[k][1][vn] for r in R])), 2) for vn in R[0][k][1]}
        out[k] = dict(place=R[0][k][0], mean=round(float(v.mean()), 3), std=round(float(v.std()), 3), views=pv)
    res[lab] = out
    print('%-14s terminator %.3f / %.3f +- %.3f  per view %s | peeks %s / %.1f' % (
        lab, out['terminator_hair']['place'], out['terminator_hair']['mean'], out['terminator_hair']['std'],
        out['terminator_hair']['views'], out['peeks_hair']['place'], out['peeks_hair']['mean']), flush=True)
if js:
    os.makedirs(os.path.dirname(os.path.abspath(js)), exist_ok=True)
    json.dump(res, open(js, 'w'), indent=1)
