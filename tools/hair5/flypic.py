"""the flyaways in front and back: the hair layers' flyaways (green outline) over each lab variant's parts (flyaways
red, ahoge teal, other hair beige), one row per variant: python tools/hair5/flypic.py OUT.png NAME=LAB.npz ..."""
import json, os, pickle, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from PIL import Image
from charkit import hairflagqa as hf
M = pickle.load(open(os.path.join(ROOT, 'charkit/out/hair5/masks.pkl'), 'rb'))['masks']
rows = []
for spec in sys.argv[2:]:
    name, p = spec.split('=', 1)
    Z = np.load(p); pcs = json.loads(str(Z['pieces']))
    tiles = []
    for v in ('front', 'back'):
        L = Z[v]
        fl = hf.our_mask(L, pcs, ('flyaways',)); ah = hf.our_mask(L, pcs, ('ahoge',))
        dm = M['%s__flyaways' % v]
        w = (slice(0, 520), slice(150, 830))
        t = np.ones(L[w].shape + (3,)); t[(L >= hf.PART0)[w]] = (.92, .85, .75)
        t[fl[w]] = (.9, .1, .1); t[ah[w]] = (.1, .6, .55)
        t[hf.outline(dm)[w]] = (.1, .7, .1)
        tiles.append(np.pad(t, ((0, 0), (0, 6), (0, 0)), constant_values=1))
    rows.append(np.concatenate(tiles, 1))
im = np.concatenate([np.pad(r, ((0, 6), (0, 0), (0, 0)), constant_values=1) for r in rows], 0)
Image.fromarray((im * 255).astype(np.uint8)).resize((im.shape[1] * 2, im.shape[0] * 2), Image.NEAREST).save(sys.argv[1])
