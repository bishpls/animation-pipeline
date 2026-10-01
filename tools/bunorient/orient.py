"""The buns' 3D orientation: is the fit's optimum one, and which drawing constraint fixes it (tool/bunorient).

    python tools/bunorient/orient.py capture BUILD HULL_DIR OUT.pkl
        bunstab's capture (both fit_block calls' arguments) plus bun_targets' inputs (the hair layers' masks, the views,
        the hull frame), so the targets can be rebuilt with other bun_views / bun_per_side
    python tools/bunorient/orient.py spread IN.pkl OUT.json [--variant NAME] [--sides L,R] [--angles 10,20]
        per bun, the fit from block_frame's pose and from starts rotated +-angles deg about each axis (fit_block's
        start=: the prior still centred on block_frame's pose): each fit's rotation from the default start's fit (deg),
        its centre's move (L), its soft loss, and its silhouette IoU in every view the sheet draws (front, three-quarter,
        profile, back: the per-side drawn bun), fitted in or not
        variants (the fit's targets):
          default   the build's own (style bun_views front, profile, back; bun_per_side off: the halves of the views'
                    buns either side of the head's axis)
          per_side  front, profile, back, each bun its own piece's pixels (the hair layers' VIEW__bun_L / _R)
          tq        per_side with the three-quarter added (its az from the sheet)
          tq_near   per_side with the three-quarter for the near bun only (the far bun's hidden part, without occlusion
                    in the soft fit, lands on the drawing's other hair)
    Determined: the starts land within ~1 deg of each other, or the lowest-loss basin is clear of the next by more than
    the 10 um noise. The guard: every view's IoU holds against the default's (within noise)."""
import json, os, pickle, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools', 'hull_local'))
os.chdir(ROOT)
import numpy as np

ALL = ('front', 'three_quarter', 'profile', 'back')


def capture(build, hull_dir, out):
    import bunstab
    from charkit.geom import hairpieces as hp
    rec, real = [], hp.bun_targets

    def bt(masks, views, hull_frame, head_c, side, *a, **k):
        rec.append(dict(masks={n: m for n, m in masks.items() if '__' in n}, views=views, hull_frame=hull_frame,
                        head_c=np.asarray(head_c, float), side=side))
        return real(masks, views, hull_frame, head_c, side, *a, **k)
    hp.bun_targets = bt
    try:
        bunstab.capture(build, hull_dir, out)
    finally:
        hp.bun_targets = real
    D = pickle.load(open(out, 'rb'))
    D['targets_in'] = rec
    pickle.dump(D, open(out, 'wb'))
    print('targets inputs', len(rec), [r['side'] for r in rec], len(rec[0]['masks']) if rec else 0, 'masks')


def targets_for(T, variant, sgn):
    from charkit.geom import hairpieces as hp
    if variant == 'default':
        return None
    names = {'per_side': ('front', 'profile', 'back'), 'tq': ALL, 'tq_near': ALL, 'all': ALL}[variant]
    tg = hp.bun_targets(T['masks'], T['views'], T['hull_frame'], T['head_c'], sgn, names, True)
    if variant == 'tq_near':
        # the near bun in the three-quarter: the one on the side the view turns toward (az > 0 shows her left, +x)
        az = T['views']['three_quarter'].az
        near = (sgn > 0) == (az > 0)
        tg = [t for t in tg if t[0] != 'three_quarter' or near]
    return tg


def ious(fit, P, head_c, style, kind, tg_all, views, hull_frame):
    """the fit's hard silhouette IoU against each view's drawn bun (fit_block's own: each part's projected points'
    convex outline) -> {view: IoU}."""
    from charkit.geom import hairpieces as hp
    U1, _ = hp.superellipsoid(np.ones(3), style.get('bun_e', 0.3), 16, 8)
    out = {}
    for name, az, mirror, m, other in tg_all:
        sm = np.zeros(m.shape, bool)
        for off, hs in hp.block_parts(fit['c'], fit['R'], fit['half'], head_c, style, fit['slab'], kind):
            cc, rr = hp.view_px(off + (U1 * hs) @ fit['R'].T, views[name], az, mirror, hull_frame)
            sm |= hp._hull_fill(cc, rr, m.shape)
        out[name] = round(float((sm & m).sum()) / max(1, (sm | m).sum()), 3)
    return out


def angle(Ra, Rb):
    return float(np.degrees(np.arccos(np.clip((np.trace(Ra @ Rb.T) - 1) / 2, -1, 1))))


def starts(angles):
    out = [('default', None)]
    for ax in range(3):
        for a in angles:
            for s in (1, -1):
                x = np.zeros(9)
                x[3 + ax] = s * np.radians(a)
                out.append(('%s%+g' % ('xyz'[ax], s * a), x))
    return out


def spread(inp, out, variant='default', sides=None, angles=(10, 20)):
    from charkit.geom import hairpieces as hp
    D = pickle.load(open(inp, 'rb'))
    L = D['L']
    res = dict(input=inp, variant=variant, angles=list(angles), sides={})
    TI = {('bun_L' if t['side'] > 0 else 'bun_R'): t for t in D.get('targets_in') or ()}
    for S in D['sides']:
        if sides and S['side'][-1] not in sides:
            continue
        a, k = list(S['args']), dict(S['kwargs'])
        P, head_c, style = a[0], np.asarray(a[1], float), a[2]
        kind = a[7] if len(a) > 7 else k.get('kind', 'block')
        sgn = 1 if S['side'] == 'bun_L' else -1
        T = TI.get(S['side'])
        if T is None and variant != 'default':
            raise SystemExit('orient: %s has no bun_targets inputs (re-capture with orient.py capture)' % inp)
        tg = targets_for(T, variant, sgn) if T is not None else None
        if tg is not None:
            a[3] = tg
        tg_all = hp.bun_targets(T['masks'], T['views'], T['hull_frame'], T['head_c'], sgn, ALL, True) if T else a[3]
        rows, base = {}, None
        for name, x0 in starts(angles):
            t = time.time()
            fit, rep = hp.fit_block(*a, **dict(k, start=x0))
            r = dict(loss=(rep.get('soft') or {}).get('loss'), fitted=rep.get('after'),
                     iou=ious(fit, P, head_c, style, kind, tg_all, a[4], a[5]), seconds=round(time.time() - t, 1),
                     R=fit['R'].tolist(), c=np.asarray(fit['c']).tolist())
            if base is None:
                base = fit
            r['deg'] = round(angle(fit['R'], base['R']), 2)
            r['move_L'] = float('%.3g' % (np.linalg.norm(np.asarray(fit['c']) - base['c']) / L))
            rows[name] = r
            print(S['side'], variant, name, 'deg %.2f' % r['deg'], 'move %.3g L' % r['move_L'], 'loss', r['loss'],
                  r['iou'], '%.1f s' % r['seconds'], flush=True)
        degs = [r['deg'] for r in rows.values()]
        losses = sorted(set(round(r['loss'], 4) for r in rows.values() if r['loss'] is not None))
        res['sides'][S['side']] = dict(starts=rows, max_deg=max(degs), median_deg=float(np.median(degs)),
                                       basins=losses, views=[t[0] for t in a[3]])
        print(S['side'], variant, 'spread max %.2f deg, median %.2f; losses %s' % (max(degs), np.median(degs), losses),
              flush=True)
    json.dump(res, open(out, 'w'), indent=1)
    return res


def main(a):
    if a[0] == 'capture':
        capture(*a[1:4])
    elif a[0] == 'spread':
        opt = lambda f, d=None: a[a.index(f) + 1] if f in a else d
        spread(a[1], a[2], opt('--variant', 'default'), opt('--sides', '').split(',') if opt('--sides') else None,
               tuple(float(x) for x in opt('--angles', '10,20').split(',')))


if __name__ == '__main__':
    main(sys.argv[1:])
