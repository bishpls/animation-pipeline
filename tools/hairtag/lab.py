"""The hair layers' transfer run in variants against the truth, the context (breakdown segmentation, registration, the
sheet's views) made once and cached.

    python tools/hairtag/lab.py OUT_DIR [--outfit MASKS.npz] 'name|{"vote": 0, ...}' ...
  -> OUT_DIR/NAME.npz (the masks), OUT_DIR/lab.json (the scores); prints a line per variant. Each variant's keys
  over hairlayers.STRUCT_ON (the method); '{"vote": 0, "clips": false}' is the default transfer.
"""
import json, os, pickle, sys, time
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from charkit import hairlayers as hl


def context(cache):
    if os.path.exists(cache):
        return pickle.load(open(cache, 'rb'))
    from charkit import manifest
    from charkit.geom import hull
    spec = manifest.resolve(json.load(open(os.path.join(ROOT, 'charkit/spec/clawd.json'))))
    R = manifest.load(spec['ref']['manifest'])['references']
    rgb_k = hl.load_rgb(R['hair_breakdown']['path'])
    sw, fam, top = hl.legend(rgb_k)
    lab = hl.segment(rgb_k, sw, fam, top - 40)
    figs = hl.figures(lab)
    rgb_b = hl.load_rgb(R['body_turnaround']['path'])
    views, info = hull.views_from_sheet(rgb_b, (spec.get('eyes') or {}).get('x', 0.168), -1)
    reg = hl.register(lab, rgb_k, views, figs)
    lab = hl.fringe_rule(lab, reg, figs)
    C = dict(lab=lab, figs=figs, views=views, reg=reg)
    pickle.dump(C, open(cache, 'wb'))
    return C


def main(a):
    out = a[0]; os.makedirs(out, exist_ok=True)
    om_path = a[a.index('--outfit') + 1] if '--outfit' in a else os.path.join(ROOT, 'charkit/out/clawd/outfit/outfit_masks.npz')
    Z = np.load(om_path); om = {k: Z[k] for k in Z.files}
    C = context(os.path.join(out, '..', 'lab_context.pkl'))
    truth = hl.load_truth('charkit/refs/clawd/hair_truth.npz')
    res = json.load(open(os.path.join(out, 'lab.json'))) if os.path.exists(os.path.join(out, 'lab.json')) else {}
    for arg in a[1:]:
        if '|' not in arg:
            continue
        name, js = arg.split('|', 1)
        st = json.loads(js)
        t0 = time.time()
        masks, _ = hl.transfer(C["lab"].copy(), C["reg"], C["figs"], C["views"], om, struct=dict(hl.STRUCT_ON, **st))
        np.savez_compressed(os.path.join(out, name + '.npz'), **masks)
        r = hl.score(masks, truth)
        res[name] = dict(struct=st, outfit=om_path, score=r)
        print('%-14s %s  all %.4f  mIoU %.3f  %s | sides prof R %s | %.0fs' % (
            name, ' '.join('%s %.3f' % (v, r[v]['accuracy']) for v in ('front', 'profile', 'back')),
            r['all']['accuracy'], r['all']['mean_iou'], ' '.join('%s %.3f' % kv for kv in r['all']['iou'].items()),
            r['sides'].get('profile', {}).get('bun_R'), time.time() - t0))
    json.dump(res, open(os.path.join(out, 'lab.json'), 'w'), indent=1)


if __name__ == '__main__':
    main(sys.argv[1:])
