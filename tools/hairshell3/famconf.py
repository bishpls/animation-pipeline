"""the hair families' confusion per view (hair_pieces' grids: our pieces z-buffered by family against the hair_layers
masks): for a drawn family, the share of its pixels each of our families (or none) shows; and a picture.
    python tools/hairshell3/famconf.py BUILD [--pieces DIR] [--family lower_back] [--views profile,front,back] [--png OUT]"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import numpy as np
from charkit import qa3d, bodyqa, bundle

def labels_of(B, design):
    from charkit.qa3d import HAIR_FAMILIES, HAIR_PIECE_FAMILY, iris_centres
    objs = {o.name[5:]: o for o in qa3d._visible(B, ('hair',)) if o.name.startswith('hair_') and o.name[5:] in HAIR_PIECE_FAMILY}
    ctx = design.sheet_context(); As = B.assembly; L = As['L']
    fam_k = {f: k + 1 for k, f in enumerate(HAIR_FAMILIES)}
    meshes = []
    sk = B.skin(); V, T = sk.mesh('masked')[:2]; meshes.append((V, T, np.zeros(len(T), int)))
    for o in B.objects(groups=('eye', 'mouth', 'accessory', 'garment')):
        if o.has('eval'):
            V, T = o.mesh('eval')[:2]; meshes.append((V, T, np.full(len(T), 50 if o.part == 'brow' else 0)))
    for name, o in objs.items():
        V, T = o.mesh('eval')[:2]; meshes.append((V, T, np.full(len(T), fam_k[HAIR_PIECE_FAMILY[name]])))
    dv = design.design_views()
    views = [v for v in ('front', 'profile', 'back', 'three_quarter') if v in dv]
    return bodyqa.zbuffer_views(meshes, ctx['az3'], np.array(iris_centres(B)), As['centre'], L, ctx['ppl'], views), fam_k

if __name__ == '__main__':
    a = sys.argv[1:]
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    B = bundle.load(os.path.join(a[0], 'bundle'))
    if opt('--pieces'):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from splice2x2 import splice
        B = splice(B, opt('--pieces'))
    D = qa3d.Design(B)
    masks = qa3d.hair_layers_masks(B, D)
    labels, fam_k = labels_of(B, D)
    inv = {k: f for f, k in fam_k.items()}
    fam = opt('--family', 'lower_back')
    for v in opt('--views', 'profile,front,back').split(','):
        m = masks.get('%s__%s' % (v, fam)); lab = labels[v][1]
        ours = lab == fam_k[fam]
        iou = (ours & m).sum() / max(1, (ours | m).sum())
        shown = {inv.get(int(k), 'none' if k == 0 else str(int(k))): round(float(((lab == k) & m).sum() / m.sum()), 3)
                 for k in np.unique(lab[m])}
        drawn_under_ours = {}
        for f2 in fam_k:
            mm = masks.get('%s__%s' % (v, f2))
            if mm is not None and mm.shape == ours.shape:
                drawn_under_ours[f2] = round(float((ours & mm).sum() / max(1, ours.sum())), 3)
        drawn_under_ours['no hair'] = round(float((ours & ~np.logical_or.reduce([masks[k] for k in masks if k.startswith(v + '__') and masks[k].shape == ours.shape])).sum() / max(1, ours.sum())), 3)
        print('%s %s IoU %.3f  ours %d px, drawn %d px | drawn %s shows: %s | ours %s lies over drawn: %s' % (
            v, fam, iou, ours.sum(), m.sum(), fam, dict(sorted(shown.items(), key=lambda x: -x[1])), fam,
            dict(sorted(drawn_under_ours.items(), key=lambda x: -x[1]))))
        if opt('--png') and v == 'profile':
            from PIL import Image
            img = np.ones(lab.shape + (3,))
            img[m & ours] = (0.2, 0.7, 0.2); img[m & ~ours] = (0.9, 0.2, 0.2); img[~m & ours] = (0.2, 0.3, 0.9)
            sl = lab == fam_k.get('side_locks', -1)
            img[m & sl] = (0.95, 0.75, 0.1)
            ys, xs = np.nonzero(m | ours)
            img = img[ys.min() - 5:ys.max() + 5, xs.min() - 5:xs.max() + 5]
            Image.fromarray((img * 255).astype(np.uint8)).resize((img.shape[1] * 2, img.shape[0] * 2), Image.NEAREST).save(opt('--png'))
