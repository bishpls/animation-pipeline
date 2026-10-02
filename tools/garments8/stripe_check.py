import json, os, sys
sys.path.insert(0, '.')
import numpy as np
from PIL import Image
from charkit import sweep, qa3d, declared, bodyqa, pieceqa, bodymeasure
decl = json.load(open('tools/garments8/l1.json')); decl['base'] = 'charkit/out/g8_c0'
B0 = sweep.load_bundle(decl['base'], True); spec = sweep.base_spec(decl, B0)
S = sweep.GarmentStage(decl, B0, spec)
ctrl = S.objects(dict(name='control', set={}), 'charkit/out/garments8/recon/control')
res = {}
for nm in ('control', 'T0'):
    objs = ctrl if nm == 'control' else S.objects(dict(name=nm, set=decl['variants'][nm]), 'charkit/out/garments8/recon/' + nm)
    keep = objs if nm == 'control' else {n: o for n, o in objs.items() if n == sweep.SKIN_MASK or sweep._changed(o, ctrl.get(n))}
    B = S.bundle(keep); D = qa3d.Design(B)
    I = declared.inputs(B, D, ('front', 'three_quarter'), truth=True)
    for v in ('front', 'three_quarter'):
        lab = I['O'][v]['lab']; sh = lab.shape; f = lambda m: declared.fit(m, sh)
        O = pieceqa.members(lab, I['names'], I['pm'], 'collar')
        Dc = f(I['masks']['%s__collar' % v]); T = f(I['truth']['masks']['%s__collar' % v])
        cls = f(I['dv'][v]['cls'] == bodyqa.CLASS['dark']) | f(I['dv'][v]['cls'] == bodyqa.CLASS['line'])
        Db = f(I['masks']['%s__bow' % v])
        other = {k[len(v) + 2:]: f(m) for k, m in I['masks'].items() if k.startswith(v + '__')}
        gap = T & ~Dc & ~Db
        fp = O & ~Dc
        who = {p: int((fp & m).sum()) for p, m in other.items() if (fp & m).sum() > 20}
        res['%s/%s' % (nm, v)] = dict(T_not_D_outside_bow=int(gap.sum()), of_which_dark_stripe=int((gap & cls).sum()),
                                      ours_only=int(fp.sum()), ours_only_on_stripe=int((fp & cls).sum()),
                                      ours_only_on_masks=who,
                                      D_dark=int((Dc & cls).sum()))
        print(nm, v, res['%s/%s' % (nm, v)])
    if nm == 'control':
        v = 'front'; lab = I['O'][v]['lab']; sh = lab.shape; f = lambda m: declared.fit(m, sh)
        Dc = f(I['masks']['front__collar']); T = f(I['truth']['masks']['front__collar'])
        cls = f(I['dv']['front']['cls'] == bodyqa.CLASS['dark'])
        im = np.full(sh + (3,), 0.97); im[T] = (0.75, 0.85, 1.0); im[Dc] = (0.5, 0.5, 0.55); im[cls & T & ~Dc] = (0.1, 0.1, 0.1)
        ys, xs = np.nonzero(T | Dc)
        im = im[ys.min() - 10:ys.max() + 10, xs.min() - 10:xs.max() + 10]
        Image.fromarray((im * 255).astype(np.uint8)).resize((im.shape[1] * 2, im.shape[0] * 2), Image.NEAREST).save('charkit/out/garments8/recon/stripe_front.png')
json.dump(res, open('charkit/out/garments8/recon/stripe.json', 'w'), indent=1)
