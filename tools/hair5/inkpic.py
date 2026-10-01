"""our ink in one view for lab variants (their saved pieces, NAME.pieces.npz): the hair beige, the ink dark red, the
drawn lines blue: python tools/hair5/inkpic.py OUT.png VIEW NAME=PIECES.npz ..."""
import json, os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from PIL import Image
from charkit import calibrate, qa3d, hairflagqa as hf
B = calibrate.load_bundle(os.path.join(ROOT, 'charkit/out/h5_base')); D = qa3d.Design(B)
Dd, ppl = hf.design_inputs(B, D)
v = sys.argv[2]
tiles = []
for spec in sys.argv[3:]:
    name, p = spec.split('=', 1)
    Z = np.load(p); names = json.loads(str(Z['names']))
    hair = {n: (Z[n + '__V'], Z[n + '__T']) for n in names}
    wts = {n: Z[n + '__outline_w'] for n in names if n + '__outline_w' in Z.files}
    ours, pcs = hf.our_labels(B, D, hair)
    ink = hf.our_ink(B, D, hair, wts)
    L = ours[v]; h = L >= hf.PART0
    w = hf.window(h, pad=6)
    t = np.ones(L[w].shape + (3,)); t[h[w]] = (.93, .85, .75)
    t[(hf.skeleton(Dd['lines'][v]) & Dd['keep'][v])[w]] = (.3, .45, 1)
    t[ink[v][w]] = (.45, .05, .05)
    tiles.append(np.pad(t, ((0, 0), (0, 6), (0, 0)), constant_values=1))
    print(name, 'ink px in hair', int((ink[v] & h).sum()))
H = max(x.shape[0] for x in tiles)
im = np.concatenate([np.pad(x, ((0, H - x.shape[0]), (0, 0), (0, 0)), constant_values=1) for x in tiles], 1)
Image.fromarray((im * 255).astype(np.uint8)).resize((im.shape[1] * 2, im.shape[0] * 2), Image.NEAREST).save(sys.argv[1])
