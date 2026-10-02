"""the V without the bow on a build: ours drawn without the bow (its classes) against the V's shape truth, per view:
skin both grey, ours only red, the truth only blue, and our other classes faint (orange jacket, cream collar).
    python tools/garments8/vlab.py BUILD_DIR OUT.png"""
import os, sys
sys.path.insert(0, os.getcwd())
import numpy as np
from PIL import Image
from charkit import bundle, qa3d, declared, gate, bodyqa

b, outp = os.path.abspath(sys.argv[1]), sys.argv[2]
bd = gate.rebased_bundle(os.path.join(b, 'bundle'), os.path.join(os.path.dirname(outp), 'rebased_' + os.path.basename(b)))
B = bundle.load(bd)
D = qa3d.Design(B)
I = declared.inputs(B, D, ('front', 'three_quarter'), classes=True, truth=True)
e = I['truth']['entries']['neck_v']
excl = sorted({n for p in e['without'] for n, _ in I['pm'].get(p, [])})
tiles = []
for v in ('front', 'three_quarter'):
    co = I['without'](v, excl, classes=True)
    T = declared.fit(I['truth']['masks']['%s__neck_v' % v], co.shape)
    sk = co == bodyqa.CLASS['skin']
    im = np.full(co.shape + (3,), 0.97)
    im[co == bodyqa.CLASS['orange']] = (0.95, 0.75, 0.6)
    im[co == bodyqa.CLASS['cream']] = (0.95, 0.93, 0.8)
    im[co == bodyqa.CLASS['dark']] = (0.6, 0.55, 0.5)
    im[sk & T] = (0.5, 0.5, 0.55)
    im[sk & ~T] = (0.9, 0.15, 0.15)
    im[T & ~sk] = (0.2, 0.35, 0.95)
    ppl = I['ppl']
    r0, r1 = int((bodyqa.WIN['top'] + 0.30) * ppl), int((bodyqa.WIN['top'] + 1.1) * ppl)
    c0, c1 = int((bodyqa.WIN['x'] - 0.5) * ppl), int((bodyqa.WIN['x'] + 0.5) * ppl)
    tiles.append(im[r0:r1, c0:c1])
canvas = np.concatenate([np.pad(t, ((0, 0), (0, 10), (0, 0)), constant_values=1) for t in tiles], 1)
Image.fromarray((canvas * 255).astype(np.uint8)).resize((canvas.shape[1] * 2, canvas.shape[0] * 2), Image.NEAREST).save(outp)
print(outp)
