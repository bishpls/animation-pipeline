"""Is it ours? (the canonical rule's step 1 for cross-view identity): does one 3D ribbon fit two views where the tube
can't? Each linked lock (a drawn lock and the same lock in the other views, from LINKS) is fitted with the lock
template's variants: alone in each view, then jointly in every view it shows in. A template that follows the views
together where the tube can't is ours to fix; if no template can, the links or the drawing disagree.

Targets are the linked drawn regions (tools/hairident/regions.py: the lock truth's named locks, the splitter's over the
rest), so the test reads the template, not the association.

    python tools/hairident/ribbon.py BUILD OUT [--links tools/hairident/links_proposed.json] [--variants a,b] [--jobs N]
        BUILD: a build with geom/pieces.spec.json and its hull (lockshell.context); OUT: ribbon.json, ribbon.md
"""
import json, math, os, pickle, sys, time
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from charkit.geom import lockshell as ls, lockident as li

VARIANTS = {
    'tube': {},                                                     # the pilot's template: lens 0.35, one twist
    'flat': {'depth_ratio': 0.15},                                  # a flat ribbon section
    'twist': {'twist_axis': True},                                  # + a twist along the lock
    'curl': {'tip_curl': True},                                     # + the tip's curl
    'ribbon': {'depth_ratio': 0.15, 'twist_axis': True, 'tip_curl': True},
    'ribbon_wide': {'depth_ratio': 0.15, 'twist_axis': True, 'tip_curl': True, 'twist_max': 1.5},
    # the envelope's depth freed (the canonical rule's step 1: the relevant freedom opened): no view's envelope pulls
    # the lock to its first surface; the views themselves place it in depth
    'free': {'view_depth': 0.0},
    'free_weak': {'view_depth': 0.0, 'prior_depth': 0.03},
    'ribbon_free': {'depth_ratio': 0.15, 'twist_axis': True, 'tip_curl': True, 'view_depth': 0.0},
}
FAMILY_OPTS = {'lower_back': {'prior_depth': 10.0, 'contain': 5.0, 'hug_free': 0.3}}   # the pilot's hem group
G = {}


def _opt(a, k, d):
    return a[a.index(k) + 1] if k in a else d


def setup(build, out):
    from charkit import hairsplit, manifest
    import regions as rg
    ctx = ls.context(build, cache=os.path.join(out, 'ctx.pkl'))
    spec = manifest.resolve(json.load(open(os.path.join(ROOT, 'charkit/spec/clawd.json'))))
    I = hairsplit.inputs(spec, cache=os.path.join(out, 'inputs.pkl'))
    R = rg.regions(I, ctx['masks'])
    return ctx, R


def one(job):
    """one lock, one variant: alone in each linked view, then jointly -> dict."""
    item, var = job
    sc, R, links = G['scene'], G['R'], G['links']
    L_ = links[item]
    fam = L_['family']
    opts = dict(FAMILY_OPTS.get(fam, {}), **VARIANTS[var])
    off = -sc.o['over'] * sc.L if fam == 'lower_back' else 0.0
    masks = {}
    for vn, rids in L_['views'].items():
        if not rids or vn not in R:
            continue
        m = np.zeros(R[vn]['img'].shape, bool)
        for rid in rids:
            if rid in R[vn]['ids']:
                m |= R[vn]['img'] == R[vn]['ids'].index(rid) + 1
        if m.sum() >= 30:
            masks[vn] = m
    home = L_['home']
    res = dict(item=item, variant=var, family=fam, home=home, views=sorted(masks), solo={}, joint=None)
    t0 = time.time()
    for vn, m in masks.items():
        lk = sc.lock(item, fam if fam != 'flyaways' else 'side_locks', vn, m, li.root_of(m), opts=opts, offset=off)
        if lk is None:
            continue
        sc.fit(lk)
        res['solo'][vn] = dict(cost=lk.cost.get(vn), iou=sc.iou(lk)[vn])
    fam_ = fam if fam != 'flyaways' else 'side_locks'

    def joint(vs):
        lk = sc.lock(item, fam_, vs[0], masks[vs[0]], li.root_of(masks[vs[0]]), opts=opts, offset=off)
        if lk is None:
            return None
        sc.fit(lk)
        for vn in vs[1:]:
            sc.add(lk, vn, masks[vn], li.root_of(masks[vn]))
        sc.fit(lk)
        part = lk.shell()
        return dict(cost=dict(lk.cost), iou=sc.iou(lk, part), twist=round(math.degrees(lk.twist), 1),
                    slope=round(math.degrees(lk.slope), 1), curl=round(math.degrees(lk.curl), 1),
                    nfev=getattr(lk, 'status', (0, 0))[1], folds=part['fit']['folds'])
    if home in masks and len(masks) > 1:
        order = [home] + [v for v in masks if v != home]
        res['joint'] = joint(order)
        res['pairs'] = {}
        import itertools
        for a_, b_ in itertools.combinations(order, 2):
            res['pairs']['%s+%s' % (a_, b_)] = joint([a_, b_])
    res['s'] = round(time.time() - t0, 1)
    return res


def table(rows, variants):
    by = {}
    for r in rows:
        by.setdefault(r['item'], {})[r['variant']] = r
    L = ['| lock | views | ' + ' | '.join(variants) + ' |', '|---|---|' + '---|' * len(variants)]
    for item, vs in by.items():
        r0 = next(iter(vs.values()))
        cells = []
        for v in variants:
            r = vs.get(v)
            if not r:
                cells.append('-'); continue
            solo = ' '.join('%s %.1f' % (k[:2], x['cost']) for k, x in r['solo'].items())
            if r['joint']:
                j = r['joint']
                cells.append('alone %s; joint %s; IoU %s' % (
                    solo, ' '.join('%s %.1f' % (k[:2], c) for k, c in j['cost'].items()),
                    ' '.join('%s %.2f' % (k[:2], x) for k, x in j['iou'].items())))
            else:
                cells.append('alone %s' % solo)
        L.append('| %s | %s | %s |' % (item, ','.join(v_[:2] for v_ in r0['views']), ' | '.join(cells)))
    return '\n'.join(L)


def summary(rows, variants, max_cost=4.0):
    """per variant: locks whose joint fit keeps every view within max_cost px, the mean joint cost over the
    other views, the home view's cost rise (joint - alone), the mean joint IoU."""
    out = {}
    for v in variants:
        rs = [r for r in rows if r['variant'] == v and r['joint']]
        ok = sum(1 for r in rs if all(c <= max_cost for c in r['joint']['cost'].values()))
        rise = [r['joint']['cost'][r['home']] - r['solo'][r['home']]['cost'] for r in rs if r['home'] in r['solo']]
        oth = [c for r in rs for k, c in r['joint']['cost'].items() if k != r['home']]
        oth_solo = [r['solo'][k]['cost'] for r in rs for k in r['joint']['cost'] if k != r['home'] and k in r['solo']]
        iou = [x for r in rs for x in r['joint']['iou'].values()]
        prs = [p for r in rs for p in (r.get('pairs') or {}).values() if p]
        pok = sum(1 for p in prs if all(c <= max_cost for c in p['cost'].values()))
        multi = [r for r in rs if len(r['joint']['cost']) > 2]
        mok = sum(1 for r in multi if all(c <= max_cost for c in r['joint']['cost'].values()))
        out[v] = dict(locks=len(rs), all_views_within=ok, home_rise_px=round(float(np.mean(rise)), 2) if rise else None,
                      other_joint_px=round(float(np.mean(oth)), 2) if oth else None,
                      other_alone_px=round(float(np.mean(oth_solo)), 2) if oth_solo else None,
                      joint_iou=round(float(np.mean(iou)), 3) if iou else None,
                      pairs=len(prs), pairs_within=pok, three_plus=len(multi), three_plus_within=mok)
    return out


def main(a):
    build, out = a[0], a[1]
    os.makedirs(out, exist_ok=True)
    links = json.load(open(_opt(a, '--links', os.path.join(ROOT, 'tools/hairident/links_proposed.json'))))['links']
    variants = _opt(a, '--variants', ','.join(VARIANTS)).split(',')
    items = _opt(a, '--items', None)
    items = items.split(',') if items else [k for k, v in links.items() if sum(1 for x in v['views'].values() if x) > 1]
    ctx, R = setup(build, out)
    G['scene'] = li.Scene(ctx)
    G['R'], G['links'] = R, links
    jobs = [(it, v) for it in items for v in variants]
    n = int(_opt(a, '--jobs', min(len(jobs), os.cpu_count() or 1)))
    t0 = time.time()
    if n > 1:
        import multiprocessing as mp
        with mp.get_context('fork').Pool(n) as pool:
            rows = pool.map(one, jobs, chunksize=1)
    else:
        rows = [one(j) for j in jobs]
    S = summary(rows, variants)
    json.dump(dict(rows=rows, summary=S, variants={v: VARIANTS[v] for v in variants}), open(os.path.join(out, 'ribbon.json'), 'w'), indent=1)
    md = ['# ribbon test (%d locks, %d variants, %.0f s)' % (len(items), len(variants), time.time() - t0), '',
          '| variant | locks | all views within 4 px | pairs within 4 px | 3+ views within 4 px | home rise px | other views joint px | other views alone px | joint IoU |',
          '|---|---|---|---|---|---|---|---|---|']
    for v, s in S.items():
        md.append('| %s | %d | %d | %d / %d | %d / %d | %s | %s | %s | %s |' % (
            v, s['locks'], s['all_views_within'], s['pairs_within'], s['pairs'], s['three_plus_within'], s['three_plus'],
            s['home_rise_px'], s['other_joint_px'], s['other_alone_px'], s['joint_iou']))
    md += ['', table(rows, variants)]
    open(os.path.join(out, 'ribbon.md'), 'w').write('\n'.join(md) + '\n')
    print('\n'.join(md[:3 + len(S) + 1]))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
