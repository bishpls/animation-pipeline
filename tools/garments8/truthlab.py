"""the shape-truth checks on a build (this tree's code): each declared check reading a `truth`, its value per view, and
a picture per view (ours drawn the truth's way | the truth | the overlap: grey both, red ours only, blue truth only).

    python tools/garments8/truthlab.py BUILD_DIR [OUT_DIR]      # BUILD_DIR holds bundle/ (a fetched build)
"""
import json, os, sys
sys.path.insert(0, os.getcwd())
import numpy as np
from PIL import Image
from charkit import bundle, qa3d, declared, gate

b = os.path.abspath(sys.argv[1])
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join('charkit/out/garments8/truthlab', os.path.basename(b.rstrip('/')))
os.makedirs(out, exist_ok=True)
bd = gate.rebased_bundle(os.path.join(b, 'bundle'), os.path.join(out, 'rebased'))
B = bundle.load(bd)
D = qa3d.Design(B)
ds = [d for d in declared.declarations() if 'truth' in (d.get('params') or {})]
views = declared.VIEWS
I = declared.inputs(B, D, views, classes=True, truth=True)
T, C = declared.evaluate(ds, I)
rows = {k: (c.get('value'), c['status']) for k, c in sorted(C.items())}
for k, v in rows.items():
    print('%-32s %s %s' % (k, v[0], v[1]))
json.dump(rows, open(os.path.join(out, 'truth_checks.json'), 'w'), indent=1)
# pictures: per truth name and view
tiles = []
for name, e in sorted((I['truth']['entries'] or {}).items()):
    if not e.get('kind') or e.get('class') or e.get('alone'):
        continue
    piece = e.get('piece', name)
    row = []
    for v in views:
        Md = I['truth']['masks'].get('%s__%s' % (v, name))
        if Md is None or v not in I['O']:
            continue
        got = declared._truth_pair(I, v, name, [piece], 'shape_iou')
        if got is None:
            continue
        Mo, Md, _ = got
        im = np.full(Mo.shape + (3,), 0.97)
        im[Mo & Md] = (0.5, 0.5, 0.55)
        im[Mo & ~Md] = (0.9, 0.15, 0.15)
        im[Md & ~Mo] = (0.2, 0.35, 0.95)
        ys, xs = np.nonzero(Mo | Md)
        if not len(ys):
            continue
        row.append(im[max(0, ys.min() - 15):ys.max() + 15, max(0, xs.min() - 15):xs.max() + 15])
    if row:
        H = max(r.shape[0] for r in row)
        W = sum(r.shape[1] for r in row) + 10 * len(row)
        canvas = np.ones((H, W, 3))
        x = 0
        for r in row:
            canvas[:r.shape[0], x:x + r.shape[1]] = r
            x += r.shape[1] + 10
        p = os.path.join(out, 'truth_%s.png' % name)
        Image.fromarray((canvas * 255).astype(np.uint8)).save(p)
        print(p)
