"""hair round 4's lab driver: hairlab's context loaded once, many variants over one build. usage:
    python tools/hair4/lab.py BUILD OUTDIR 'name|{"style":{},"opts":{},"shape":{}}' ...
Per variant, OUTDIR/NAME.json and pictures (NAME_edges.png: fragments and steps; NAME_buns.png: each bun per view) and a
summary line block: the hair checks, each bun per view (IoU / outline), fragments and steps per view, face shown,
folds, penetration (depth, piece, vertices) and the three-quarter figure's IoU as the body QA draws it (the QA scene,
z-buffered: body_three_quarter_iou's measure within ~0.003). 'built' as the name's JSON measures the build as built."""
import json, os, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
import numpy as np
from charkit import hairlab as hl, bodyqa, qa3d


def conv(x):
    if isinstance(x, dict):
        return {k: conv(v) for k, v in x.items() if not str(k).startswith('_')}
    if isinstance(x, (list, tuple)):
        return [conv(v) for v in x]
    if isinstance(x, np.generic):
        return x.item()
    if isinstance(x, np.ndarray):
        return x.tolist()
    return x


def body_iou(ctx, hair, views=('front', 'three_quarter', 'profile', 'back')):
    """per view the figure's IoU (foreground) and the hair class's, ours as the body QA draws it."""
    B, D = ctx['B'], ctx['D']
    dv = D.design_views()
    sc = D.sheet_context()
    As = B.assembly
    meshes = []
    V, T = B.skin().mesh('masked')[:2]
    meshes.append((V, T, np.full(len(T), 1)))
    for o in B.objects(groups=('eye', 'mouth', 'accessory', 'garment')):
        if o.has('eval'):
            V, T = o.mesh('eval')[:2]
            meshes.append((V, T, np.full(len(T), 5)))
    meshes += [(ev[0], ev[1], np.full(len(ev[1]), 2)) for ev, _ in hair.values()]
    vs = [v for v in views if v in dv]
    lab = bodyqa.zbuffer_views(meshes, sc['az3'], np.array(qa3d.iris_centres(B)), As['centre'], As['L'], sc['ppl'], vs)
    iou = lambda a, b: round(float((a & b).sum() / max(1, (a | b).sum())), 4)
    return {v: (iou(lab[v][1] >= 1, dv[v]['cls'] > 0), iou(lab[v][1] == 2, dv[v]['cls'] == 2)) for v in vs}


def penetration(ctx, hair):
    """qa3d's hair_penetration measure, with where: -> (deepest L, piece, vertices inside, the deepest point)."""
    from scipy.spatial import cKDTree
    B = ctx['B']
    L = B.assembly['L']
    Vs, Ts = B.skin().mesh('eval')[:2]
    fn = np.cross(Vs[Ts[:, 1]] - Vs[Ts[:, 0]], Vs[Ts[:, 2]] - Vs[Ts[:, 0]])
    fn /= np.linalg.norm(fn, axis=1, keepdims=True) + 1e-18
    cen = Vs[Ts].mean(1)
    tree = cKDTree(cen)
    deepest, where, inside, at, per = 0.0, None, 0, None, {}
    for name, (_, raw) in hair.items():
        V = np.asarray(raw[0], float)
        dd, j = tree.query(V, 4)
        near = dd[:, 0] < 0.05 * L
        sd = np.median(np.einsum('ikj,ikj->ik', V[near][:, None] - cen[j[near]], fn[j[near]]), axis=1) / L
        if len(sd):
            n_in = int((sd < -qa3d.HAIR_PENETRATION[0]).sum())
            inside += n_in
            per[name] = (round(float(-sd.min()), 4), n_in)
            if -sd.min() > deepest:
                deepest, where = float(-sd.min()), name
                at = (V[near][np.argmin(sd)] - B.assembly['centre']) / L
    return round(deepest, 4), where, inside, None if at is None else [round(float(a), 3) for a in at], per


def measure(ctx, design, name, out, R, Cq, fs, hair):
    ours = hl.our_edges(ctx, hair)
    C = hl.edge_checks(ours, design)
    bv = hl.bun_views(ctx, hair)
    bi = body_iou(ctx, hair)
    pen = penetration(ctx, hair)
    cr = hl.crown_rise(ctx, hair)
    folds = {k: r.get('folds') for k, r in R['report']['pieces'].items()} if R else None
    res = dict(q={k: Cq[k] for k in hl.KEYS if k in Cq}, face=fs, folds=folds, edges=C, buns=bv, body_iou=bi, crown=cr,
               penetration=pen, bun_fit=R['report'].get('bun_fit') if R else None,
               trim=R['report'].get('side_lock_trim') if R else None,
               crown_trim=R['report'].get('crown_trim') if R else None,
               body_clear=(R['report'].get('fields') or {}).get('body_clear') if R else None)
    json.dump(conv(res), open(os.path.join(out, name + '.json'), 'w'), indent=1)
    hl.edge_picture(ctx, ours, design, os.path.join(out, name + '_edges.png'))
    hl.bun_picture(ctx, bv, os.path.join(out, name + '_buns.png'))
    q = lambda k: Cq.get(k, {}).get('value')
    fr = ' '.join('%s' % C.get('hair_fragments_' + w, {}).get('value') for w in hl.EDGE_VIEWS)
    st = ' '.join('%s' % C.get(k, {}).get('value') for k in ('hair_rough_profile_front', 'hair_rough_profile_lower',
                                                            'hair_rough_three_quarter_lower', 'hair_rough_back_lower'))
    print('== %s' % name)
    print('   bangs %s side %s ub %s lb %s buns %s | bun_outline %s %s | fringe_low %s' % (
        q('hair_piece_bangs'), q('hair_piece_side_locks'), q('hair_piece_upper_back'), q('hair_piece_lower_back'),
        q('hair_piece_buns'), q('hair_bun_outline'), Cq.get('hair_bun_outline', {}).get('views'), q('hair_fringe_low')))
    print('   ub per view %s' % Cq.get('hair_piece_upper_back', {}).get('views'))
    for v in hl.BUN_VIEWS:
        if v in bv:
            print('   bun %-13s %s' % (v, '  '.join('%s %.3f/%.3f' % (s, r['iou'], r['f']) for s, r in bv[v].items())))
    print('   bun pooled %s' % bv['pooled'])
    print('   frags f/3q/p/b %s | steps pf/pl/3ql/bl %s' % (fr, st))
    print('   frags by %s' % {w: C.get('hair_fragments_' + w, {}).get('by') for w in hl.EDGE_VIEWS})
    print('   islands %s' % ' '.join('%s' % C.get('hair_islands_' + w, {}).get('value') for w in hl.EDGE_VIEWS))
    print('   body fg/hair IoU %s' % bi)
    print('   penetration %s' % (pen,))
    print('   crown rise (L, ours over drawn) %s' % {v: (c['median'], c['p90'], c['max'], c['over']) for v, c in cr.items()})
    print('   face %s folds %s %s' % (fs, None if folds is None else sum(v_ or 0 for v_ in folds.values()), folds))
    if R and R['report'].get('bun_fit'):
        print('   bun fit %s' % json.dumps(conv(R['report']['bun_fit'])))
    if R and 'side_lock_trim' in R['report']:
        print('   trim %s' % R['report']['side_lock_trim'])
    if R and 'crown_trim' in R['report']:
        print('   crown trim %s' % R['report']['crown_trim'])
    if R and (R['report'].get('fields') or {}).get('body_clear'):
        print('   body clear %s' % R['report']['fields']['body_clear'])
    sys.stdout.flush()
    return res


if __name__ == '__main__':
    build, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    os.makedirs(out, exist_ok=True)
    t = time.time()
    ctx = hl.context(build)
    design = hl.design_edges(ctx)
    print('context %.0f s' % (time.time() - t), flush=True)
    for arg in sys.argv[3:]:
        name, js = arg.split('|', 1)
        t = time.time()
        if js.strip() == 'built':
            hair = hl.built_hair(ctx)
            _, Cq = qa3d.hair_pieces_measure(ctx['B'], ctx['D'], hair)
            measure(ctx, design, name, out, None, Cq, hl.face_shown(ctx, hair), hair)
        else:
            v = json.loads(js)
            if v.get('shape'):
                ctx2 = hl.context(build, v['shape'])
            else:
                ctx2 = ctx
            R, Cq, fs, hair = hl.run(ctx2, v.get('style'), v.get('opts'))
            measure(ctx2, design, name, out, R, Cq, fs, hair)
        print('   (%.0f s)' % (time.time() - t), flush=True)
