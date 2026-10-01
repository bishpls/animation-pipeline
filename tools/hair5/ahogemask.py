"""the builder's view of the ahoge: per view the hair layers' VIEW__ahoge (teal), the region ahoge_region takes (light
teal), the base under the outline cut (brown), the truth's ahoge outline (red), the centreline (black, the first bigger)."""
import os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from PIL import Image
from charkit import hairlab, hairflagqa as hf
from charkit.geom import hairpieces as hp

ctx = hairlab.context(os.path.join(ROOT, 'charkit/out/h5_base'))
masks, views = ctx['masks'], ctx['views']
Dd, ppl = hf.design_inputs(ctx['B'], ctx['D'])
tiles = []
for name in ('front', 'profile', 'back'):
    m = masks['%s__ahoge' % name]
    rg = hp.ahoge_region(masks, name, views[name].ppl)
    tr = Dd['ahoge'][name]
    w = hf.window(rg[0], tr, pad=12)
    t = np.ones(m[w].shape + (3,))
    hair = np.zeros_like(m)
    for f in hp.FAMILIES:
        if masks.get('%s__%s' % (name, f)) is not None:
            hair |= masks['%s__%s' % (name, f)]
    t[hair[w]] = (.9, .8, .7)
    t[rg[1][w]] = (.75, .6, .45)
    t[rg[0][w]] = (.55, .85, .8)
    t[m[w] & rg[0][w]] = (.1, .6, .55)
    t[hf.outline(tr)[w]] = (.9, .1, .1)
    got = hp._drawn_stroke(masks, name, views, 12)
    if got is not None:
        for k, (c, r) in enumerate(got[0]):
            rr, cc = int(round(r)) - w[0].start, int(round(c)) - w[1].start
            s = 2 if k == 0 else 1
            t[max(0, rr - s):rr + s + 1, max(0, cc - s):cc + s + 1] = 0
        print(name, 'widths', np.round(got[1], 1).tolist())
    tiles.append(np.pad(t, ((0, 0), (0, 4), (0, 0)), constant_values=1))
H = max(x.shape[0] for x in tiles)
im = np.concatenate([np.pad(x, ((0, H - x.shape[0]), (0, 0), (0, 0)), constant_values=1) for x in tiles], 1)
Image.fromarray((im * 255).astype(np.uint8)).resize((im.shape[1] * 5, im.shape[0] * 5), Image.NEAREST).save(sys.argv[1])
