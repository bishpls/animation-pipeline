"""Where hair_noise sits (hairtag round 3): hairlab's context over a build once, then per variant the pieces rebuilt and
hair_noise measured as qa3d.hair_noise measures it (hairlab.noise's drawing), with each piece's visible pixels and
tone-edge pixels per view, so a piece's share of the check is its edges over all the hair's pixels. usage:
    python tools/hairtag/noiselab.py BUILD OUT 'name|{"opts": {...}, "style": {...}}' ... [--png]
-> OUT/noiselab.json; OUT/NAME_AZ.png with --png (the view's hair, its tone edges red, each piece's pixels tinted)."""
import json, os, pickle, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
import numpy as np
from charkit import hairlab as hl, qa3d


def noise_counts(ctx, R, png=None):
    B = ctx['B']
    objs = {o.name: o for o in qa3d._visible(B, ('hair',))}
    hair = [hl._Piece(objs['hair_' + n], p['V'], p['T'], p['vn_shade']) for n, p in R['pieces'].items()
            if 'hair_' + n in objs]
    names = [o.name[5:] for o in hair]
    fr = qa3d.figure_frame(B, ss=qa3d.FIG_SS)
    surfs, owner = [], []
    for i, o in enumerate(hair):
        for x in qa3d.surfaces(B, o, outline=False):
            surfs.append(x); owner.append(i)
    occ = [x for o in B.objects() if o.group != 'hair' and o.has('eval')
           for x in qa3d.surfaces(B, o, 'masked' if o.group == 'skin' else 'eval', outline=False)]
    group = np.array([qa3d.hair_noise_group(o) for o in hair])
    out = {}
    for az in (0, 90, 180):
        px = qa3d.draw(B, surfs + occ, az, fr)
        items = [(s_['V'], s_['T'], np.full(len(s_['T']), owner[k] + 1 if k < len(surfs) else -1), s_['cull'])
                 for k, s_ in enumerate(surfs + occ)]
        lab = qa3d._to_shape(fr.zbuffer(items, az)[1], px.shape[:2])
        a = (px[..., 3] > 0.5) & (lab >= 1)
        grp = np.where(a, group[np.clip(lab - 1, 0, len(group) - 1)], 0)
        lum = px[..., :3] @ np.array([0.3, 0.59, 0.11])
        e, n = qa3d.tone_edges(lum, grp)
        e &= a
        # the edges between two pieces (a tone step at a lock's border) apart from those inside one piece
        pl = np.where(a, lab, 0)
        border = np.zeros_like(a)
        border[:, 1:] |= (pl[:, 1:] != pl[:, :-1]) & (pl[:, 1:] > 0) & (pl[:, :-1] > 0)
        border[1:] |= (pl[1:] != pl[:-1]) & (pl[1:] > 0) & (pl[:-1] > 0)
        v = dict(value=round(float(e.sum() / max(1, n)), 4), px=int(n), edges=int(e.sum()),
                 border_edges=int((e & border).sum()), pieces={})
        for i, nm in enumerate(names):
            m = a & (lab == i + 1)
            if m.sum():
                v['pieces'][nm] = dict(px=int(m.sum()), edges=int(e[m].sum()), border=int((e & border)[m].sum()),
                                       share=round(float(e[m].sum() / max(1, n)), 4))
        out[str(az)] = v
        if png:
            from PIL import Image
            rng = np.random.RandomState(3)
            tint = rng.uniform(0.35, 0.95, (len(names) + 1, 3))
            img = np.where(a[..., None], 0.55 * px[..., :3] + 0.45 * tint[np.clip(lab, 0, len(names))], 1.0)
            img[e] = (1.0, 0.0, 0.0)
            ys, xs = np.nonzero(a)
            if len(ys):
                img = img[max(0, ys.min() - 8):ys.max() + 8, max(0, xs.min() - 8):xs.max() + 8]
            Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save('%s_%d.png' % (png, az))
    out['value'] = round(float(np.mean([out[str(az)]['value'] for az in (0, 90, 180)])), 4)
    return out


def main(a):
    build, out = a[:2]
    os.makedirs(out, exist_ok=True)
    ctx = hl.context(build)
    res = {}
    for arg in [x for x in a[2:] if '|' in x]:
        name, js = arg.split('|', 1)
        v = json.loads(js)
        t = time.time()
        R, Cq, fs, hair = hl.run(ctx, v.get('style'), v.get('opts'))
        r = noise_counts(ctx, R, os.path.join(out, name) if '--png' in a else None)
        r['checks'] = {k: Cq[k].get('value') for k in hl.KEYS if k in Cq}
        r['folds'] = {k: p.get('folds') for k, p in R['report']['pieces'].items()}
        res[name] = dict(variant=v, **r)
        top = sorted(((p['edges'], az, nm) for az in ('0', '90', '180') for nm, p in r[az]['pieces'].items()), reverse=True)[:6]
        print('%-18s noise %.4f (%s) folds %d  top: %s  (%.0f s)' % (
            name, r['value'], ' '.join('%s:%.4f' % (az, r[az]['value']) for az in ('0', '90', '180')),
            sum(x or 0 for x in r['folds'].values()),
            ', '.join('%s@%s %d/%d' % (nm, az, ed, r[az]['px']) for ed, az, nm in top), time.time() - t))
        json.dump(res, open(os.path.join(out, 'noiselab.json'), 'w'), indent=1)


if __name__ == '__main__':
    main(sys.argv[1:])
