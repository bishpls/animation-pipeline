"""A lean working context for the hair-5 truth work, cut from tools/hairlocks/ctx.py's cache: per view the body sheet's
design view (rgb, raw, fg, cls), the hair as the hair layers' transfer sees it, the grid (us, zs, x0y0, axis, ppl), the
structure labeller's regions and the family truth's image and sets.

    python tools/hair5truth/ctx5.py
"""
import json, os, pickle, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools', 'hairlocks'))

CACHE = os.path.join(ROOT, 'charkit/out/hair5truth/ctx5.pkl')


def make(cache=CACHE):
    if os.path.exists(cache):
        return pickle.load(open(cache, 'rb'))
    import ctx as cx
    from charkit import hairlayers as hl
    C = cx.make()
    FT, sets, _ = hl.load_truth('charkit/refs/clawd/hair_truth.npz')
    out = dict(ppl=C['ppl'], dv=C['dv'], hair=C['hair'], grid=C['grid'], regions=C['regions'],
               fam_truth={v: np.asarray(t) for v, t in FT.items()}, fam_sets=sets)
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    pickle.dump(out, open(cache, 'wb'))
    return out


if __name__ == '__main__':
    C = make()
    for v in C['dv']:
        h = C['hair'][v]
        ys, xs = np.nonzero(h)
        print(v, h.shape, int(h.sum()), 'hair px; bbox rows %d-%d cols %d-%d' % (ys.min(), ys.max(), xs.min(), xs.max()),
              C['grid'][v]['x0y0'], 'axis', C['grid'][v]['axis'], 'ppl', C['grid'][v]['ppl'])
