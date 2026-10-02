"""reconcile the collar's two measures (coordinator, 2026-10-01): the in-context guard (piece_collar: ours with
everything drawn against the turnaround's collar, the bow over both) and the shape truth (collar_*_truth: ours without
the bow against bodice_layers' collar). Per view, for the base and each variant of a sweep:
  in context  ours' visible collar O against the turnaround's D (iou, iou_tol); ours only (O - D) split by what the
              turnaround shows there (its bow, its top, skin, other), the turnaround's only (D - O) by what ours shows
              there (our bow, our top, our skin, nothing)
  the covers  the bows: ours against the turnaround's (iou), and the share of the truth's collar each bow hides
  the truth   bodice_layers' collar T against the turnaround's D where the turnaround's bow doesn't hide it (iou_dc:
              is the reference consistent with the turnaround), and ours without the bow W against T
and a picture per view: in context (grey both, red ours only, blue the turnaround's only; the turnaround's bow outlined
green, ours yellow) beside the truth (W against T).
    python tools/garments8/recon.py BASE_BUILD OUT_DIR SWEEP_DECL.json ROW [ROW ..]"""
import json, os, sys
sys.path.insert(0, os.getcwd())
import numpy as np
from scipy import ndimage
from PIL import Image
from charkit import sweep, qa3d, declared, bodyqa, bodymeasure, pieceqa

base, out, decl_p = sys.argv[1:4]
names = sys.argv[4:]
decl = json.load(open(decl_p))
decl['base'] = base
B0 = sweep.load_bundle(base, True)
spec = sweep.base_spec(decl, B0)
sweep.produce(spec)
S = sweep.GarmentStage(decl, B0, spec)
ctrl = S.objects(dict(name='control', set=dict(decl.get('set') or {})), os.path.join(out, 'control'))
VIEWS = ('front', 'three_quarter')
iou = lambda a, b: float((a & b).sum()) / max(1, int((a | b).sum()))
edge = lambda m: m & ~ndimage.binary_erosion(m)
rep = {}
for nm in names:
    st = {} if nm == 'control' else decl['variants'][nm]
    objs = S.objects(dict(name=nm, set=dict(decl.get('set') or {}, **st)), os.path.join(out, nm))
    keep = {n: o for n, o in objs.items() if n == sweep.SKIN_MASK or sweep._changed(o, ctrl.get(n)) or nm == 'control'}
    B = S.bundle(keep)
    D = qa3d.Design(B)
    I = declared.inputs(B, D, VIEWS, truth=True)
    names_, pm, M = I['names'], I['pm'], I['masks']
    excl = sorted({n for p in ('bow', 'bow_tail_L', 'bow_tail_R') for n, _ in pm.get(p, [])})
    rep[nm] = {}
    tiles = []
    for v in VIEWS:
        lab = I['O'][v]['lab']
        sh = lab.shape
        f = lambda m: declared.fit(m, sh)
        O = pieceqa.members(lab, names_, pm, 'collar')
        Obow = pieceqa.members(lab, names_, pm, 'bow')
        Otop = pieceqa.members(lab, names_, pm, 'top')
        Oskin = np.isin(lab % 1000, [i for i, n in enumerate(names_) if 'skin' in n]) & (lab >= 0)
        Dc = f(M['%s__collar' % v])
        Db = f(M['%s__bow' % v]) | f(M.get('%s__bow_tail_L' % v, np.zeros(sh, bool))) | \
            f(M.get('%s__bow_tail_R' % v, np.zeros(sh, bool)))
        Dt = f(M['%s__top' % v])
        dcls = f(I['dv'][v]['cls'] == bodyqa.CLASS['skin'])
        T = f(I['truth']['masks']['%s__collar' % v])
        W = pieceqa.members(I['without'](v, excl), names_, pm, 'collar')
        fp, fn = O & ~Dc, Dc & ~O
        r = dict(iou=round(iou(O, Dc), 3), iou_tol=round(bodymeasure.iou_tol(O, Dc, bodymeasure.OUTLINE_TOL * I['ppl']), 3),
                 ours_only=int(fp.sum()), ours_only_on={'design_bow': int((fp & Db).sum()), 'design_top': int((fp & Dt).sum()),
                                                        'design_skin': int((fp & dcls).sum())},
                 design_only=int(fn.sum()), design_only_under={'our_bow': int((fn & Obow).sum()), 'our_top': int((fn & Otop).sum()),
                                                                 'our_skin': int((fn & Oskin).sum()), 'nothing': int((fn & (lab < 0)).sum())},
                 bow_iou=round(iou(Obow, Db), 3),
                 truth_hidden_by={'design_bow': round(float((T & Db).sum()) / max(1, T.sum()), 3),
                                  'our_bow': round(float((W & Obow).sum()) / max(1, W.sum()), 3)},
                 truth_vs_turnaround=round(float((T & Dc & ~Db).sum()) / max(1, int(((T | Dc) & ~Db).sum())), 3),
                 ours_without_bow_vs_truth=round(iou(W, T), 3), px=dict(O=int(O.sum()), D=int(Dc.sum()), T=int(T.sum()), W=int(W.sum())))
        rep[nm][v] = r
        def pic(A, Bm, out1, out2):
            im = np.full(sh + (3,), 0.97)
            im[A & Bm] = (0.5, 0.5, 0.55); im[A & ~Bm] = (0.9, 0.15, 0.15); im[Bm & ~A] = (0.2, 0.35, 0.95)
            im[edge(out1)] = (0.1, 0.7, 0.2)
            if out2 is not None:
                im[edge(out2)] = (0.95, 0.8, 0.1)
            return im
        a = pic(O, Dc, Db, Obow)
        b = pic(W, T, np.zeros(sh, bool), None)
        ys, xs = np.nonzero(O | Dc | T | W | Db)
        sl = (slice(max(0, ys.min() - 15), ys.max() + 15), slice(max(0, xs.min() - 15), xs.max() + 15))
        tiles += [a[sl], np.ones((a[sl].shape[0], 8, 3)), b[sl], np.ones((a[sl].shape[0], 24, 3))]
    H = max(t.shape[0] for t in tiles)
    cv = np.ones((H, sum(t.shape[1] for t in tiles), 3))
    x = 0
    for t in tiles:
        cv[:t.shape[0], x:x + t.shape[1]] = t; x += t.shape[1]
    os.makedirs(out, exist_ok=True)
    p = os.path.join(out, 'recon_%s.png' % nm)
    Image.fromarray((cv * 255).astype(np.uint8)).save(p)
    print(nm, json.dumps(rep[nm]))
    print(p)
json.dump(rep, open(os.path.join(out, 'recon.json'), 'w'), indent=1)
