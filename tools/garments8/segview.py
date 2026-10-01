"""the layer sheets cut into pieces (layerref.layer_pieces) drawn per view: python segview.py SHEET KIND OUT.png"""
import json, os, sys
sys.path.insert(0, os.getcwd())
import numpy as np
from PIL import Image
from charkit import layerref as lr, manifest
spec = manifest.resolve(json.load(open('charkit/spec/clawd.json')))
path, kind, outp = sys.argv[1:4]
TV = lr._truth_views(spec, lambda *a: None)
km = {}
lr.check_layer(spec, path, kind, log=lambda *a: None, keep_masks=km)
K = lr.LAYERS[kind]
COL = {'collar': (0.95, 0.9, 0.6), 'top': (0.9, 0.45, 0.2), 'bodice_panel': (0.6, 0.8, 0.95)}
tiles = []
for v in lr.VIEWS:
    t = TV[v]
    P = lr.layer_pieces(km[v], t, K['layer'], K['cover'])
    im = np.full(t['fg'].shape + (3,), 0.97)
    im[t['fg']] = 0.85
    for p, m in P.items():
        im[m] = COL.get(p, (0.5, 0.5, 0.5))
    ys, xs = np.nonzero(km[v]['C'])
    tiles.append(im[max(0, ys.min() - 20):ys.max() + 20, max(0, xs.min() - 20):xs.max() + 20])
    print(v, {p: int(m.sum()) for p, m in P.items()})
H = max(t.shape[0] for t in tiles)
W = sum(t.shape[1] for t in tiles)
out = np.full((H, W, 3), 1.0)
x = 0
for t in tiles:
    out[:t.shape[0], x:x + t.shape[1]] = t
    x += t.shape[1]
Image.fromarray((out * 255).astype(np.uint8)).save(outp)
print(outp)
