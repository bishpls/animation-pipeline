"""famdiff.py OUT 'name|json' 'name|json': per view (front, profile, back) the upper back's and bangs' pixels that differ
between two variants against the drawn families: where ours is ub and drawn isn't, etc. Prints the IoU parts."""
import json, os, sys
sys.path.insert(0, os.path.expanduser('~/animation-pipeline-hair3'))
os.chdir(os.path.expanduser('~/animation-pipeline-hair3'))
import numpy as np
from PIL import Image
from charkit import hairlab as hl, qa3d
out = os.path.abspath(sys.argv[1])
VF = [x.split(':') for x in os.environ.get('FAMDIFF', 'profile:upper_back,profile:bangs,back:upper_back').split(',')]
ctx = hl.context(os.path.abspath('charkit/out/h3_base'))
res = []
for arg in sys.argv[2:4]:
    name, js = arg.split('|', 1)
    v_ = json.loads(js)
    R, Cq, fs, hair = hl.run(ctx, v_.get('style'), v_.get('opts'))
    res.append(hl.labels_for(ctx, hair, views=('front', 'profile', 'back')))
fam = {f: k + 1 for k, f in enumerate(qa3d.HAIR_FAMILIES)}
tiles = []
for v, f in VF:
    A, B = res[0][v][1], res[1][v][1]
    if True:
        m = ctx['masks'].get('%s__%s' % (v, f))
        if m is None:
            continue
        a, b = A == fam[f], B == fam[f]
        print(v, f, 'A iou %.4f B iou %.4f' % ((a & m).sum() / (a | m).sum(), (b & m).sum() / (b | m).sum()),
              'gained-in-drawn', int((b & ~a & m).sum()), 'gained-outside', int((b & ~a & ~m).sum()),
              'lost-in-drawn', int((a & ~b & m).sum()), 'lost-outside', int((a & ~b & ~m).sum()))
        img = np.full(A.shape + (3,), 245, np.uint8)
        img[(A > 0)] = (200, 200, 200)
        img[m] = (170, 200, 240)
        img[b & ~a & ~m] = (230, 30, 30)      # gained outside drawn: red
        img[b & ~a & m] = (30, 170, 30)       # gained inside: green
        img[a & ~b & m] = (240, 150, 0)       # lost inside: orange
        img[a & ~b & ~m] = (120, 0, 160)      # lost outside: purple
        rr, cc = np.nonzero((A > 0) | m)
        tiles.append(img[rr.min():rr.min() + 250, cc.min():cc.max()])
H = max(t.shape[0] for t in tiles)
o = np.concatenate([np.pad(t, ((0, H - t.shape[0]), (0, 6), (0, 0)), constant_values=255) for t in tiles], 1)
Image.fromarray(o).resize((o.shape[1] * 2, o.shape[0] * 2), Image.NEAREST).save(out)
