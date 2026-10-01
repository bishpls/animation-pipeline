"""The splitter's stages against the 52-lock truth, per view and family, beside the floors and today's sources:

  random                  the truth's locks re-cut into as many random Voronoi cells per view (5 seeds)
  random within family    each family re-cut into as many random cells as it has locks (the family edges kept)
  h5_base                 the build's locks (pipeline-3d 004efc3; tools/hair5truth/ours5.py)
  labeller                the structure labeller's regions (hairlayers.lock_regions: the drawing's lines and two tones)
  ink cells               trapped balls on the drawn ink alone (no extensions)
  closing                 + each upstream stroke end extended along the flow (the cells: stage 'cells')
  + tips and flow         every pixel to the tip it reaches along the flow (stage 'tips')
  + merge / split         the regions: several tips split along the flow, the tipless own or merged (stage 'locks')

    python tools/hairsplit/ablation.py OUT_DIR [--set K=V ...]     -> OUT_DIR/ablation.json, stages.npz
"""
import json, os, pickle, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
from charkit import hairsplit as hs, hairlocks as hk
import dev

FAMS = ('bangs', 'side_locks', 'lower_back', 'flyaways', 'ahoge')


def tab(r):
    out = {}
    for v in hs.VIEWS + ('all',):
        if v not in r:
            continue
        out[v] = {f: r[v]['families'][f]['lock_iou'] for f in r[v].get('families', {})}
        out[v]['_all'] = r[v]['lock_iou']
        if 'matched' in r[v]:
            out[v]['_matched'] = r[v]['matched']
    return out


if __name__ == '__main__':
    a = sys.argv[1:]
    out = a[0]
    os.makedirs(out, exist_ok=True)
    params = {}
    for i, q in enumerate(a):
        if q == '--set':
            k, v = a[i + 1].split('=')
            params[k] = json.loads(v)
    I = dev.load_inputs()
    T = hk.load_truth('charkit/refs/clawd/hair_locks_truth.npz')
    hair = {v: np.ones(t.shape, bool) for v, t in T[0].items()}
    res = {}
    fl = hs.floors(T)
    for k, x in fl.items():
        res[k] = {v: dict({f: y['lock_iou'] for f, y in x[v]['families'].items()}, _all=x[v]['lock_iou']) for v in x}
    # today's sources
    Z = np.load(os.path.join(ROOT, 'charkit/out/hairsplit/ref/h5_base.npz'))
    names = {int(k): q for k, q in json.loads(str(Z['names'])).items()}
    res['h5_base'] = tab(hk.score({v: Z[v] for v in T[0]}, T, hair, T[2]['ppl'], names))
    C = pickle.load(open(os.path.join(ROOT, 'charkit/out/hairsplit/ctx5.pkl'), 'rb'))
    from scipy import ndimage
    lab = {}
    for v in T[0]:
        g = C['regions'][v]
        lab[v] = hk.fill_labels(g, ndimage.binary_dilation(g > 0, iterations=2), 2)
    res['labeller'] = tab(hk.score(lab, T, hair, T[2]['ppl']))
    # the stages
    stages = {}
    for name, V in I['views'].items():
        S = hs.Split(name, V, I['ppl'], params)
        S.pipeline()
        # ink cells: trapped balls on the drawn ink alone
        S2 = hs.Split(name, V, I['ppl'], dict(params, ext_cap=1e-6, ext_keep_cap=False))
        S2.measure_ink(); S2.strokes(); S2.flow(); S2.tips(); S2.flow(S2.tip_list); S2.tips(); S2.close()
        for st, im in (('ink cells', S2.cells), ('closing', S.cells), ('+ tips and flow', S.locks_tips),
                       ('+ merge / split', S.locks)):
            stages.setdefault(st, {})[name] = S.full(im.astype(np.int32))
    for st, x in stages.items():
        res[st] = tab(hs.score(x, T))
    np.savez_compressed(os.path.join(out, 'stages.npz'), **{'%s__%s' % (st, v): im for st, x in stages.items()
                                                            for v, im in x.items()})
    json.dump(dict(params=dict(hs.P, **params), table=res), open(os.path.join(out, 'ablation.json'), 'w'), indent=1)
    cols = ['random', 'random_within_family', 'h5_base', 'labeller', 'ink cells', 'closing', '+ tips and flow',
            '+ merge / split']
    print('%-14s %-11s %s' % ('view', 'family', ' '.join('%9s' % c[:9] for c in cols)))
    for v in hs.VIEWS + ('all',):
        for f in FAMS + ('_all',):
            row = [res[c].get(v, {}).get(f) for c in cols]
            if row[0] is None:
                continue
            print('%-14s %-11s %s' % (v, f, ' '.join('%9s' % ('-' if q is None else '%.3f' % q) for q in row)))
