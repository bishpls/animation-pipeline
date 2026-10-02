import json, os, sys
sys.path.insert(0, '.')
import numpy as np
from PIL import Image
from charkit import sweep, qa3d, declared, bodyqa, pieceqa, bodymeasure
decl = json.load(open('tools/garments8/l1.json')); decl['base'] = 'charkit/out/g8_c0'
B0 = sweep.load_bundle(decl['base'], True); spec = sweep.base_spec(decl, B0)
S = sweep.GarmentStage(decl, B0, spec)
ctrl = S.objects(dict(name='control', set={}), 'charkit/out/garments8/recon/control')
iou = lambda a, b: float((a & b).sum()) / max(1, int((a | b).sum()))
res = {}
for nm in ('control', 'T0'):
    objs = ctrl if nm == 'control' else S.objects(dict(name=nm, set=decl['variants'][nm]), 'charkit/out/garments8/recon/' + nm)
    keep = objs if nm == 'control' else {n: o for n, o in objs.items() if n == sweep.SKIN_MASK or sweep._changed(o, ctrl.get(n))}
    B = S.bundle(keep); D = qa3d.Design(B)
    I = declared.inputs(B, D, ('front', 'three_quarter'), truth=True)
    tiles = []
    for v in ('front', 'three_quarter'):
        lab = I['O'][v]['lab']; sh = lab.shape; f = lambda m: declared.fit(m, sh)
        M = {k[len(v) + 2:]: f(m) for k, m in I['masks'].items() if k.startswith(v + '__')}
        Dbow = np.zeros(sh, bool)
        for k, m in M.items():
            if k.startswith('bow'):
                Dbow |= m
        Dc = M['collar']; T = f(I['truth']['masks']['%s__collar' % v])
        O = pieceqa.members(lab, I['names'], I['pm'], 'collar')
        Obow = pieceqa.members(lab, I['names'], I['pm'], 'bow')
        skin_d = f(I['dv'][v]['cls'] == bodyqa.CLASS['skin'])
        line_d = f(np.isin(I['dv'][v]['cls'], [bodyqa.CLASS['line'], bodyqa.CLASS['dark']]))
        other = np.zeros(sh, bool)
        for k, m in M.items():
            if not k.startswith('bow') and k != 'collar':
                other |= m
        fp = O & ~Dc; fn = Dc & ~O
        r = dict(guard_iou_tol=round(bodymeasure.iou_tol(O, Dc, bodymeasure.OUTLINE_TOL * I['ppl']), 3),
                 iou=round(iou(O, Dc), 3),
                 ours_only=dict(total=int(fp.sum()), on_drawn_bow=int((fp & Dbow).sum()), on_drawn_skin=int((fp & skin_d & ~Dbow).sum()),
                                on_other_pieces=int((fp & other & ~Dbow & ~skin_d).sum()), on_lines=int((fp & line_d & ~Dbow & ~skin_d & ~other).sum())),
                 drawn_only=dict(total=int(fn.sum()), under_our_bow=int((fn & Obow).sum()), elsewhere=int((fn & ~Obow).sum())),
                 bow_iou=round(iou(Obow, Dbow), 3),
                 truth_vs_drawn_outside_drawn_bow=round(iou(T & ~Dbow, Dc & ~Dbow), 3),
                 truth_on_drawn_skin=int((T & skin_d & ~Dbow).sum()))
        res['%s/%s' % (nm, v)] = r
        print(nm, v, json.dumps(r))
        im = np.full(sh + (3,), 0.97)
        im[Dbow] = (0.85, 0.95, 0.85)
        im[O & Dc] = (0.5, 0.5, 0.55); im[fp & Dbow] = (1.0, 0.6, 0.1); im[fp & ~Dbow] = (0.9, 0.15, 0.15)
        im[fn] = (0.2, 0.35, 0.95)
        ob = Obow & ~np.roll(Obow, 1, 0) | Obow & ~np.roll(Obow, 1, 1)
        im[ob] = (0.6, 0.2, 0.8)
        ys, xs = np.nonzero(O | Dc | Dbow)
        sl = (slice(ys.min() - 10, ys.max() + 10), slice(xs.min() - 10, xs.max() + 10))
        tiles.append(im[sl])
    H = max(t.shape[0] for t in tiles)
    cv = np.ones((H, sum(t.shape[1] for t in tiles) + 20, 3)); x = 0
    for t in tiles:
        cv[:t.shape[0], x:x + t.shape[1]] = t; x += t.shape[1] + 20
    Image.fromarray((cv * 255).astype(np.uint8)).resize((cv.shape[1] * 2, cv.shape[0] * 2), Image.NEAREST).save('charkit/out/garments8/recon/recon2_%s.png' % nm)
json.dump(res, open('charkit/out/garments8/recon/recon2.json', 'w'), indent=1)
