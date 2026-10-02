"""the shape-truth pictures for a garment variant of a build, without a build: the sweep's garments stage (the fast
evaluator at the variant's spec, spliced into the base bundle), then truthlab's checks and pictures and vlab's V.
    python tools/garments8/truthvar.py BASE_BUILD OUT_DIR SWEEP_DECL.json ROW [ROW ..]   (rows by name; 'control')"""
import json, os, sys
sys.path.insert(0, os.getcwd())
import numpy as np
from PIL import Image
from charkit import sweep, qa3d, declared, bodyqa

base, out, decl_p = sys.argv[1:4]
names = sys.argv[4:]
decl = json.load(open(decl_p))
decl['base'] = base
B0 = sweep.load_bundle(base, True)
spec = sweep.base_spec(decl, B0)
sweep.produce(spec)
S = sweep.GarmentStage(decl, B0, spec)
ctrl = S.objects(dict(name='control', set=dict(decl.get('set') or {})), os.path.join(out, 'control'))
for nm in names:
    st = {} if nm == 'control' else decl['variants'][nm]
    objs = S.objects(dict(name=nm, set=dict(decl.get('set') or {}, **st)), os.path.join(out, nm))
    keep = {n: o for n, o in objs.items() if n == sweep.SKIN_MASK or sweep._changed(o, ctrl.get(n)) or nm == 'control'}
    B = S.bundle(keep)
    D = qa3d.Design(B)
    I = declared.inputs(B, D, declared.VIEWS, classes=True, truth=True)
    ds = [d for d in declared.declarations() if 'truth' in (d.get('params') or {})]
    _, C = declared.evaluate(ds, I)
    print(nm, {k: c.get('value') for k, c in sorted(C.items())})
    od = os.path.join(out, nm)
    os.makedirs(od, exist_ok=True)
    tiles = []
    for name in ('collar', 'top'):
        e = I['truth']['entries'][name]
        row = []
        for v in declared.VIEWS:
            got = declared._truth_pair(I, v, name, [e.get('piece', name)], 'shape_iou')
            if got is None:
                continue
            Mo, Md, _ = got
            im = np.full(Mo.shape + (3,), 0.97)
            im[Mo & Md] = (0.5, 0.5, 0.55); im[Mo & ~Md] = (0.9, 0.15, 0.15); im[Md & ~Mo] = (0.2, 0.35, 0.95)
            ys, xs = np.nonzero(Mo | Md)
            row.append(im[max(0, ys.min() - 15):ys.max() + 15, max(0, xs.min() - 15):xs.max() + 15])
        H = max(r.shape[0] for r in row)
        cv = np.ones((H, sum(r.shape[1] for r in row) + 10 * len(row), 3))
        x = 0
        for r in row:
            cv[:r.shape[0], x:x + r.shape[1]] = r; x += r.shape[1] + 10
        Image.fromarray((cv * 255).astype(np.uint8)).save(os.path.join(od, 'truth_%s.png' % name))
    # the V without the bow
    e = I['truth']['entries']['neck_v']
    excl = sorted({n for p in e['without'] for n, _ in I['pm'].get(p, [])})
    vt = []
    for v in ('front', 'three_quarter'):
        co = I['without'](v, excl, classes=True)
        T = declared.fit(I['truth']['masks']['%s__neck_v' % v], co.shape)
        sk = co == bodyqa.CLASS['skin']
        im = np.full(co.shape + (3,), 0.97)
        im[co == bodyqa.CLASS['orange']] = (0.95, 0.75, 0.6)
        im[co == bodyqa.CLASS['cream']] = (0.95, 0.93, 0.8)
        im[co == bodyqa.CLASS['dark']] = (0.6, 0.55, 0.5)
        im[sk & T] = (0.5, 0.5, 0.55); im[sk & ~T] = (0.9, 0.15, 0.15); im[T & ~sk] = (0.2, 0.35, 0.95)
        ppl = I['ppl']
        r0, r1 = int((bodyqa.WIN['top'] + 0.30) * ppl), int((bodyqa.WIN['top'] + 1.1) * ppl)
        c0, c1 = int((bodyqa.WIN['x'] - 0.5) * ppl), int((bodyqa.WIN['x'] + 0.5) * ppl)
        vt.append(im[r0:r1, c0:c1])
    cv = np.concatenate([np.pad(t, ((0, 0), (0, 10), (0, 0)), constant_values=1) for t in vt], 1)
    Image.fromarray((cv * 255).astype(np.uint8)).save(os.path.join(od, 'v.png'))
    print(od)
