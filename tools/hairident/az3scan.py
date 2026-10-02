"""Which three-quarter rotation do the drawn locks imply? Each lock drawn in the front, three-quarter and profile (the
lock truth's names: ahoge, bangs, side locks; LINKS for the rest) fitted in all three at once with the three-quarter's
azimuth set to each of AZ (the envelope's depth freed: view_depth 0, no containment, so only the cameras and the drawn
centrelines speak). The sheet's own azimuth (hull.views_from_sheet: the eyes' separation, 35.5 deg) is one reading;
a lock that fits the three views only at another azimuth is drawn view-dependently (or the camera is wrong, if every
lock agrees).

    python tools/hairident/az3scan.py BUILD OUT [--az 25,30,...] [--links tools/hairident/links_proposed.json]
"""
import json, os, pickle, sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ribbon as rb, regions as rg
from charkit import hairlocks as hk
from charkit.geom import lockident as li

VIEWS3 = ('front', 'three_quarter', 'profile')
TRUTH_LOCKS = ('ahoge/ahoge', 'bangs/l', 'bangs/l_clip', 'bangs/c', 'bangs/r', 'side_locks/L_front', 'side_locks/L_jaw',
               'flyaways/under_bun_L')
G = {}


def one(job):
    name, az = job
    sc, masks = G['sc'], G['masks'][name]
    sc.S['views']['three_quarter']['az'] = az
    vs = list(masks)
    lk = sc.lock(name, 'side_locks', vs[0], masks[vs[0]], li.root_of(masks[vs[0]]))
    sc.fit(lk)
    for b in vs[1:]:
        sc.add(lk, b, masks[b], li.root_of(masks[b]))
    sc.fit(lk)
    return dict(lock=name, az=az, cost=dict(lk.cost), views=vs)


def main(a):
    build, out = a[0], a[1]
    os.makedirs(out, exist_ok=True)
    azs = [float(x) for x in rb._opt(a, '--az', '20,25,30,35.47,40,45,50,55,60,65,70,75').split(',')]
    links = json.load(open(rb._opt(a, '--links', os.path.join(ROOT, 'tools/hairident/links_proposed.json'))))['links']
    ctx, R = rb.setup(build, out)
    I = pickle.load(open(os.path.join(out, 'inputs.pkl'), 'rb'))
    T, TL, _ = rg.load_truth()
    masks = {}
    for nm in TRUTH_LOCKS:
        mm = {}
        for vn in VIEWS3:
            if nm in TL[vn]:
                m = hk.fill_walls(T[vn], I['views'][vn]['hair']) == TL[vn].index(nm)
                if m.sum() > 30:
                    mm[vn] = m
        if len(mm) == 3:
            masks['truth:' + nm] = mm
    for k, L_ in links.items():
        if all(L_['views'].get(v) for v in VIEWS3) and not k.replace('.', '/') in TRUTH_LOCKS:
            mm = {}
            for vn in VIEWS3:
                m = np.zeros(R[vn]['img'].shape, bool)
                for rid in L_['views'][vn]:
                    m |= R[vn]['img'] == R[vn]['ids'].index(rid) + 1
                mm[vn] = m
            masks['link:' + k] = mm
    G['sc'] = li.Scene(ctx, {'view_depth': 0.0, 'contain': 0.0})
    G['masks'] = masks
    jobs = [(n, az) for n in masks for az in azs]
    import multiprocessing as mp
    with mp.get_context('fork').Pool(min(len(jobs), int(rb._opt(a, '--jobs', 8)))) as pool:
        rows = pool.map(one, jobs, chunksize=1)
    best = {}
    for n in masks:
        rs = [r for r in rows if r['lock'] == n]
        r = min(rs, key=lambda r: max(r['cost'].values()))
        r35 = min(rs, key=lambda r: abs(r['az'] - 35.47))
        best[n] = dict(best_az=r['az'], best_max_px=max(r['cost'].values()), best=r['cost'],
                       at_sheet_az_max_px=max(r35['cost'].values()), at_sheet=r35['cost'])
    json.dump(dict(rows=rows, best=best, az=azs), open(os.path.join(out, 'az3scan.json'), 'w'), indent=1)
    L = ['| lock | best az | worst view px there | worst view px at 35.5 | ' + ' | '.join('%g' % z for z in azs) + ' |',
         '|---|---|---|---|' + '---|' * len(azs)]
    for n, b in best.items():
        rs = {r['az']: max(r['cost'].values()) for r in rows if r['lock'] == n}
        L.append('| %s | %g | %.1f | %.1f | %s |' % (n, b['best_az'], b['best_max_px'], b['at_sheet_az_max_px'],
                                                    ' | '.join('%.1f' % rs[z] for z in azs)))
    open(os.path.join(out, 'az3scan.md'), 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
