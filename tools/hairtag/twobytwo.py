"""The 2x2 for the hair pieces under a change of hair layers (Michael's no-gaming rule): the pieces built from each mask
set (the geometry) scored against each mask set (the measure), over one build's bundle and hull (hairlab's context).

    python tools/hairtag/twobytwo.py BUILD OUT OLD.npz NEW.npz ['name|{"opts": {...}, "style": {...}, "masks": "new"}' ...]

  BUILD  a build with its hair in pieces (hairlab's context: its bundle, pieces.spec.json and the hull it read)
  OLD    the hair layers before (e.g. pipeline-3d's), NEW after (hairlayers' produced masks on this branch)
  -> OUT/twobytwo.json and a table: per geometry (built from OLD, from NEW, the build as built, and each extra variant:
     opts/style over the committed defaults, built from the masks named) and per measure (OLD, NEW): the hair_piece_*
     checks pooled and per view, hair_bun_outline with its views, hair_fringe_low; per geometry (measure-free): the
     builder's folds per piece, the hair class's IoU against the drawn hair per view (all four views: the shape) and
     the buns per view (IoU / outline against each measure's bun sides).
The masks' own move (each family's IoU, OLD against NEW, per view) is printed first."""
import json, os, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools', 'hair4'))
import numpy as np
from charkit import hairlab as hl, manifest, qa3d

KEYS = ['hair_piece_' + f for f in qa3d.HAIR_FAMILIES] + ['hair_bun_outline', 'hair_fringe_low']
VIEWS = ('front', 'profile', 'back')


def load(p):
    Z = np.load(p)
    return {k: Z[k] for k in Z.files}


def context(build, masks_path):
    """hairlab's context with the hair layers read from masks_path (the hull labelled by them, the build fed them)."""
    orig = manifest.produced
    manifest.produced = lambda spec, rid, log=print: masks_path if rid == 'hair_layers' else orig(spec, rid, log)
    try:
        return hl.context(build)
    finally:
        manifest.produced = orig


def score(ctx, hair, masks):
    """the QA's hair checks for hair against masks (qa3d.hair_pieces_measure with its hair layers swapped)."""
    orig = qa3d.hair_layers_masks
    qa3d.hair_layers_masks = lambda B, design: masks
    try:
        _, Cq = qa3d.hair_pieces_measure(ctx['B'], ctx['D'], hair)
    finally:
        qa3d.hair_layers_masks = orig
    out = {}
    for k in KEYS:
        if k in Cq:
            c = Cq[k]
            out[k] = {'value': c.get('value'), 'status': c.get('status'), 'views': c.get('views')}
    bv = hl.bun_views(dict(ctx, masks=masks), hair)
    out['buns_per_view'] = {v: {s: [round(r['iou'], 3), round(r['f'], 3)] for s, r in bv[v].items()}
                            for v in hl.BUN_VIEWS if v in bv}
    return out


def masks_move(old, new):
    rows = {}
    for f in qa3d.HAIR_FAMILIES:
        per, I, U, n0, n1 = {}, 0, 0, 0, 0
        for v in VIEWS:
            a, b = old.get('%s__%s' % (v, f)), new.get('%s__%s' % (v, f))
            if a is None or b is None:
                continue
            i, u = int((a & b).sum()), int((a | b).sum())
            per[v] = round(i / max(1, u), 3)
            I, U, n0, n1 = I + i, U + u, n0 + int(a.sum()), n1 + int(b.sum())
        rows[f] = dict(pooled=round(I / max(1, U), 3), views=per, px=[n0, n1])
    return rows


def main(a):
    build, out, p_old, p_new = (os.path.abspath(x) for x in a[:4])
    os.makedirs(out, exist_ok=True)
    import lab as h4lab                               # tools/hair4/lab.py: the figure's IoU as the body QA draws it
    M = {'old': load(p_old), 'new': load(p_new)}
    res = {'build': build, 'masks': {'old': p_old, 'new': p_new}, 'move': masks_move(M['old'], M['new']), 'geom': {}}
    for f, r in res['move'].items():
        print('masks %-11s pooled IoU %.3f views %s px %s' % (f, r['pooled'], r['views'], r['px']))
    t = time.time()
    ctxs = {'old': context(build, p_old), 'new': context(build, p_new)}
    print('contexts %.0f s' % (time.time() - t), flush=True)
    geoms = [('built', None, None), ('old', 'old', {}), ('new', 'new', {})]
    for arg in a[4:]:
        name, js = arg.split('|', 1)
        v = json.loads(js)
        geoms.append((name, v.get('masks', 'new'), v))
    for name, mk, v in geoms:
        t = time.time()
        if mk is None:
            ctx, R = ctxs['old'], None
            hair = hl.built_hair(ctx)
        else:
            ctx = ctxs[mk]
            R, _, _, hair = hl.run(ctx, v.get('style'), v.get('opts'))
        g = {'masks': mk, 'variant': v, 'score': {s: score(ctx, hair, M[s]) for s in ('old', 'new')}}
        g['folds'] = {k: r.get('folds') for k, r in R['report']['pieces'].items()} if R else None
        g['shape'] = {vw: {'figure': x[0], 'hair': x[1]} for vw, x in h4lab.body_iou(ctx, hair).items()}
        res['geom'][name] = g
        print('== %s (built from %s masks) %.0f s' % (name, mk or 'old, as built', time.time() - t))
        for k in KEYS:
            print('   %-24s old %-6s new %-6s   views old %s new %s' % (
                k, g['score']['old'].get(k, {}).get('value'), g['score']['new'].get(k, {}).get('value'),
                g['score']['old'].get(k, {}).get('views'), g['score']['new'].get(k, {}).get('views')))
        if g['folds'] is not None:
            print('   folds %s %s' % (sum(x or 0 for x in g['folds'].values()), g['folds']))
        print('   shape (figure, hair IoU) %s' % g['shape'])
        print('   buns per view old %s' % g['score']['old']['buns_per_view'])
        print('   buns per view new %s' % g['score']['new']['buns_per_view'], flush=True)
        json.dump(h4lab.conv(res), open(os.path.join(out, 'twobytwo.json'), 'w'), indent=1)
    print('\n| check | old geom, old masks | new geom, old masks | old geom, new masks | new geom, new masks |')
    for k in KEYS:
        c = lambda gn, s: res['geom'][gn]['score'][s].get(k, {}).get('value')
        print('| %s | %s | %s | %s | %s |' % (k, c('old', 'old'), c('new', 'old'), c('old', 'new'), c('new', 'new')))


if __name__ == '__main__':
    main(sys.argv[1:])
