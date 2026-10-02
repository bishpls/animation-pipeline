"""six-placement art_terminator_hair / art_peeks_hair for each row of a hair sweep (its pieces spliced into the base
build the sweep's way, outline_w honoured): per row the placement-0 reading, the six-placement mean +- std and the
per-view means.   python charkit/out/hairshell3/term6.py SWEEPDIR BASE [ROW ...]"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from charkit import bundle
from charkit.render.calibrate import OFFSETS
from termnoise import reading
from splice2x2 import splice
sw, base = sys.argv[1], sys.argv[2]
rows = sys.argv[3:] or sorted(d for d in os.listdir(sw) if os.path.isdir(os.path.join(sw, d, 'geom', 'hair_pieces')))
B0 = bundle.load(os.path.join(base, 'bundle'))
res = {}
for r in rows:
    B = splice(B0, os.path.join(sw, r, 'geom', 'hair_pieces'))
    R = [reading(B, off) for off in OFFSETS[:6]]
    out = {}
    for k in R[0]:
        v = np.array([x[k][0] for x in R], float)
        pv = {vn: round(float(np.mean([x[k][1][vn] for x in R])), 2) for vn in R[0][k][1]}
        out[k] = dict(place=R[0][k][0], mean=round(float(v.mean()), 3), std=round(float(v.std()), 3), max=round(float(v.max()), 3), views=pv)
    res[r] = out
    print(r, json.dumps(out), flush=True)
json.dump(res, open(os.path.join(sw, 'term6.json'), 'w'), indent=1)
