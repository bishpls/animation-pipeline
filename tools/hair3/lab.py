"""scratch driver: hairlab's context loaded once, many variants. usage:
    python lab.py BUILD OUTDIR 'name|{"style":{},"opts":{}}' ...
writes OUTDIR/NAME.json (checks, edges, face shown, folds) and OUTDIR/NAME.png (edge picture)."""
import json, os, sys, time
sys.path.insert(0, os.path.expanduser('~/animation-pipeline-hair3'))
os.chdir(os.path.expanduser('~/animation-pipeline-hair3'))
import numpy as np
from charkit import hairlab as hl

build, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
t = time.time()
ctx = hl.context(os.path.abspath(build))
design = hl.design_edges(ctx)
print('context %.0f s' % (time.time() - t), flush=True)


def conv(x):
    if isinstance(x, dict):
        return {k: conv(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [conv(v) for v in x]
    if isinstance(x, np.generic):
        return x.item()
    return x


def bun_picture(ctx, hair, path, scale=3):
    from PIL import Image
    from charkit import bodymeasure, qa3d
    code = qa3d.HAIR_FAMILIES.index('buns') + 1
    labs = hl.labels_for(ctx, hair, views=('front', 'profile'))
    tiles = []
    for v in ('front', 'profile'):
        L = labs[v][1]
        m = ctx['masks'].get('%s__buns' % v)
        ours = L == code
        img = np.full(L.shape + (3,), 245.0)
        img[L > 0] = (200, 200, 200)
        img[ours] = (250, 190, 120)
        img[m & ~ours] = (170, 210, 250)
        img[bodymeasure.outline(m)] = (0, 80, 220)
        img[bodymeasure.outline(ours)] = (220, 40, 0)
        rr, cc = np.nonzero(m | ours)
        t = img[max(0, rr.min() - 10):rr.max() + 10, max(0, cc.min() - 10):cc.max() + 10]
        tiles.append(t)
    H = max(t.shape[0] for t in tiles)
    out = np.concatenate([np.pad(t, ((0, H - t.shape[0]), (0, 8), (0, 0)), constant_values=255) for t in tiles], 1)
    Image.fromarray(out.astype(np.uint8)).resize((out.shape[1] * scale, out.shape[0] * scale), Image.NEAREST).save(path)


def face_picture(ctx, hair, path):
    from charkit import bodyqa, qa3d
    B, D = ctx['B'], ctx['D']
    sc = D.sheet_context(); As = B.assembly
    V, T = B.skin().mesh('masked')[:2]
    meshes = [(V, T, np.ones(len(T), int))]
    for o in B.objects(groups=('eye', 'mouth')):
        if o.has('eval'):
            V, T = o.mesh('eval')[:2]; meshes.append((V, T, np.ones(len(T), int)))
    for o in B.objects(groups=('accessory', 'garment')):
        if o.has('eval'):
            V, T = o.mesh('eval')[:2]; meshes.append((V, T, np.full(len(T), 3)))
    for ev, _ in hair.values():
        meshes.append((ev[0], ev[1], np.full(len(ev[1]), 2)))
    dv = D.design_views()
    views = ['front', 'three_quarter', 'profile']
    lab = bodyqa.zbuffer_views(meshes, sc['az3'], np.array(qa3d.iris_centres(B)), As['centre'], As['L'], sc['ppl'], views)
    tiles = []
    from PIL import Image
    for v in views:
        lb = lab[v][1]
        z = bodyqa.WIN['top'] - (np.arange(lb.shape[0]) + 0.5) / sc['ppl']
        head = ((z > -0.42) & (z < 0.35))[:, None] & np.ones(lb.shape[1], bool)[None]
        ds = (dv[v]['cls'] == bodyqa.CLASS['skin']) & head
        os_ = (lb == 1) & head
        img = np.full(lb.shape + (3,), 245, np.uint8)
        img[lb == 2] = (170, 170, 170)
        img[ds & os_] = (60, 170, 60)
        img[os_ & ~ds] = (220, 40, 40)
        img[ds & ~os_] = (40, 90, 230)
        rr = np.nonzero(head.any(1))[0]
        cc = np.nonzero(((lb == 2) | ds).any(0))[0]
        tiles.append(img[max(0, rr.min() - 120):rr.max() + 10, cc.min() - 10:cc.max() + 10])
    H = max(t.shape[0] for t in tiles)
    out = np.concatenate([np.pad(t, ((0, H - t.shape[0]), (0, 8), (0, 0)), constant_values=255) for t in tiles], 1)
    Image.fromarray(out).resize((out.shape[1] * 2, out.shape[0] * 2), Image.NEAREST).save(path)


for arg in sys.argv[3:]:
    name, js = arg.split('|', 1)
    v = json.loads(js)
    t = time.time()
    R, Cq, fs, hair = hl.run(ctx, v.get('style'), v.get('opts'))
    t1 = time.time() - t
    ours = hl.our_edges(ctx, hair)
    C = hl.edge_checks(ours, design)
    extra = {}
    if hasattr(hl, 'extra_checks'):
        extra = hl.extra_checks(ctx, ours, design, hair)
    res = dict(variant=v, q={k: Cq[k] for k in hl.KEYS if k in Cq}, face=fs,
               folds={k: r.get('folds') for k, r in R['report']['pieces'].items()},
               edges=C, extra=extra, bun_fit=R['report'].get('bun_fit'))
    json.dump(conv(res), open(os.path.join(out, name + '.json'), 'w'), indent=1)
    hl.edge_picture(ctx, ours, design, os.path.join(out, name + '.png'))
    np.savez_compressed(os.path.join(out, name + '_labs.npz'), locks=np.array(['%s:%d' % l for l in
                        hl.head_labels.__globals__.get('_last_locks', [])] or ['']),
                        **{w: ours[w]['_lab'].astype(np.int16) for w in hl.EDGE_VIEWS})
    bun_picture(ctx, hair, os.path.join(out, name + '_bun.png'))
    face_picture(ctx, hair, os.path.join(out, name + '_face.png'))
    if 'side_lock_trim' in R['report']:
        print('   trim %s' % R['report']['side_lock_trim'])
    print('   bun outline views %s corners %s' % (Cq.get('hair_bun_outline', {}).get('views'),
                                                  Cq.get('hair_bun_corners', {}).get('views')))
    fr = ' '.join('%s' % C.get('hair_fragments_' + w, {}).get('value') for w in hl.EDGE_VIEWS)
    by = {w: C.get('hair_fragments_' + w, {}).get('by') for w in hl.EDGE_VIEWS}
    st = ' '.join('%s' % C.get(k, {}).get('value') for k in ('hair_rough_profile_front', 'hair_rough_profile_lower',
                                                            'hair_rough_three_quarter_lower', 'hair_rough_back_lower'))
    q = lambda k: Cq.get(k, {}).get('value')
    print('== %s (%.0f s build+qa, %.0f s all)' % (name, t1, time.time() - t))
    print('   frags f/3q/p/b %s | steps pf/pl/3ql/bl %s' % (fr, st))
    print('   by %s' % by)
    pk = ' '.join('%s' % C.get('hair_islands_' + w, {}).get('value') for w in hl.EDGE_VIEWS)
    fk = ' '.join('%s' % C.get('hair_islands_' + w, {}).get('flicks') for w in hl.EDGE_VIEWS)
    print('   islands f/3q/p/b %s (flicks %s) %s' % (pk, fk, {w: C.get('hair_islands_' + w, {}).get('by') for w in hl.EDGE_VIEWS}))
    for w in hl.EDGE_VIEWS:
        print('   shards %s %s' % (w, [(int(a), int(b), c, d, e) for a, b, c, d, e in ours[w]['shards']['where']]))
    from charkit import qa3d as _q
    fn = ['?'] + list(_q.HAIR_FAMILIES)
    for w, part in (('profile', 'front'), ('profile', 'lower'), ('three_quarter', 'lower'), ('back', 'lower')):
        E = ours[w]['_E']
        sel = (E['n'][:, 0] > 0.5) if part == 'lower' else (E['n'][:, 1] * ours[w].get('facing', 0) > 0.5)
        print('   steps %s_%s %s' % (w, part, [(a, b, c, dd, fn[e], f) for a, b, c, dd, e, f in hl.step_where(E, sel)]))
    print('   bangs %s side %s ub %s lb %s buns %s bun_outline %s fringe_low %s pen %s' % (
        q('hair_piece_bangs'), q('hair_piece_side_locks'), q('hair_piece_upper_back'), q('hair_piece_lower_back'),
        q('hair_piece_buns'), q('hair_bun_outline'), q('hair_fringe_low'), q('hair_penetration')))
    print('   face %s folds %s' % ({k: float(x) for k, x in fs.items()}, sum(v_ or 0 for v_ in res['folds'].values())),
          res['folds'])
    if extra:
        print('   extra %s' % {k: x.get('value') for k, x in extra.items()})
    sys.stdout.flush()
