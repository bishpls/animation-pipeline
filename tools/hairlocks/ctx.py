"""The lock-level truth's working context, made once and cached: the body sheet's design views (the hair truth's grids),
the sheet's hull views, per view the hair as the hair layers' transfer sees it (clips out, the buns' rim kept) and the
structure labeller's lock regions (hairlayers.lock_regions, the candidate source).

    python tools/hairlocks/ctx.py [CACHE.pkl]
"""
import json, os, pickle, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from charkit import hairlayers as hl

CACHE = os.path.join(ROOT, 'charkit/out/hairlocks/ctx.pkl')
VIEWS = ('front', 'three_quarter', 'profile', 'back')


def hair_of(v, us, zs, om, name, shape):
    """the view's hair as hairlayers.transfer takes it (the sheet's hair class in the view's figure, the clips out
    except within the buns' rim)."""
    from scipy import ndimage
    hair = (v.sample(v.labels, us, zs).T == 2) & (v.sample(v.mask.astype(np.uint8), us, zs).T > 0)
    buns = np.zeros(shape, bool)
    for b in ('bun_L', 'bun_R'):
        k = '%s__%s' % (name, b)
        if k in om and om[k].shape == shape:
            buns |= om[k]
    keep = ndimage.binary_dilation(buns, iterations=hl.BUN_RIM) if buns.any() else np.zeros(shape, bool)
    for k, m in om.items():
        if k.startswith(name + '__') and k.split('__', 1)[1] not in ('bun_L', 'bun_R') and m.shape == shape:
            hair &= ~(m & ~keep)
    return hair


def make(cache=CACHE):
    if os.path.exists(cache):
        return pickle.load(open(cache, 'rb'))
    from charkit import manifest
    from charkit.geom import hull
    spec = manifest.resolve(json.load(open(os.path.join(ROOT, 'charkit/spec/clawd.json'))))
    R = manifest.load(spec['ref']['manifest'])['references']
    dv, ppl = hl.design(spec)
    rgb_b = hl.load_rgb(R['body_turnaround']['path'])
    views, info = hull.views_from_sheet(rgb_b, (spec.get('eyes') or {}).get('x', 0.168), -1)
    Z = np.load(manifest.produced(spec, 'outfit_masks'))
    om = {k: Z[k] for k in Z.files}
    Zh = np.load(manifest.produced(spec, 'hair_layers'))
    layers = {k: Zh[k] for k in Zh.files}
    out = dict(ppl=ppl, dv={}, hair={}, regions={}, grid={})
    for name in VIEWS:
        if name not in views or name not in dv:
            continue
        v = views[name]
        us, zs, shape, x0y0 = hl.design_grid(v, v.ppl)
        hair = hair_of(v, us, zs, om, name, shape)
        out['hair'][name] = hair
        out['regions'][name] = hl.lock_regions(v, us, zs, hair, hl.STRUCT_ON['h'], hl.STRUCT_ON['tone'])
        out['grid'][name] = dict(us=us, zs=zs, shape=shape, x0y0=x0y0, axis=v.axis, eye_y=v.eye_y, ppl=v.ppl)
        d = dv[name]
        out['dv'][name] = {k: d[k] for k in ('rgb', 'raw', 'fg', 'cls') if k in d}
    out['layers'] = layers
    out['outfit'] = om
    pickle.dump(out, open(cache, 'wb'))
    return out


if __name__ == '__main__':
    C = make(sys.argv[1] if len(sys.argv) > 1 else CACHE)
    for v in C['hair']:
        r = C['regions'][v]
        print(v, C['hair'][v].shape, int(C['hair'][v].sum()), 'hair px;', int(r.max()), 'regions')
