"""Michael's cross-view lock links (the labelling page's passes) folded into one held-out truth file, self-contained:
every linked region as polygons on the body turnaround's design grids, point marks as points, not visible as such.
Held out from fitting: scoring only (tools/hairident/ident.py).

    python tools/hairident/truth.py OUT.json PASS1_DIR [PASS2_DIR ...]     (each DIR: task.json, answers.json)
    load(path) -> {item: dict(number, title, family, home (view, mask), views {view: mask | 'hidden' | points [[x, y]]},
                   pass {view: n})}   (masks on the design grids, 1594 x 977)
"""
import hashlib, json, os, sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
FORMAT = 'charkit-hair-lock-links/1'
GRID = (1594, 977)


def _family(rid, info):
    if rid.startswith('T:'):
        return rid[2:].split('/', 1)[0]
    return 'lower_back' if '(lower_back)' in (info or '') else 'side_locks'


def make(dirs, by):
    from charkit import label
    out, prov = {}, []
    for n, d in enumerate(dirs, 1):
        T = label.load_task(os.path.join(d, 'task.json'))
        A = json.load(open(os.path.join(d, 'answers.json')))
        prov.append(dict(task=os.path.relpath(os.path.join(d, 'task.json'), ROOT), task_sha=T['sha'],
                         answers_sha=hashlib.sha256(open(os.path.join(d, 'answers.json'), 'rb').read()).hexdigest()[:12],
                         seconds=round(sum(r.get('seconds', 0) for r in A['items'].values()), 1)))
        crop = {v['id']: v['crop'] for v in T['views']}
        regs = {v: {r['id']: r for r in rs} for v, rs in T['regions'].items()}

        def polys(v, rids):
            r0, c0 = crop[v][0], crop[v][1]
            return [[[round(x + c0, 2), round(y + r0, 2)] for x, y in ring] for rid in rids for ring in regs[v][rid]['rings']]
        for it in T['items']:
            hv, hr = it['home']['view'], it['home']['regions']
            q = out.setdefault(it['id'], dict(number=it['number'], title=it.get('title'),
                                              family=_family(hr[0], (regs[hv][hr[0]].get('info'))),
                                              home=dict(view=hv, regions=hr, polygons=polys(hv, hr)), views={}))
            for v, a in A['items'].get(it['id'], {}).get('views', {}).items():
                if a['verdict'] == 'unsure':
                    q['views'][v] = dict(verdict='unsure', **{'pass': n})
                elif a['verdict'] == 'point':
                    r0, c0 = crop[v][0], crop[v][1]
                    q['views'][v] = dict(verdict='point', points=[[p[0] + c0, p[1] + r0] for p in a['points']], **{'pass': n})
                elif a['verdict'] == 'hidden' or not a['regions']:
                    q['views'][v] = dict(verdict='hidden', **{'pass': n})
                else:
                    q['views'][v] = dict(verdict=a['verdict'], regions=a['regions'], polygons=polys(v, a['regions']),
                                         **{'pass': n})
    return dict(format=FORMAT, by=by, grid='the body turnaround\'s design grids (charkit.bodyqa.design_views: %d x %d)' % GRID,
                use='held out from fitting: scoring only (links right / wrong / missing / extra; points: the lock covers the point)',
                passes=prov, items=out)


def _raster(polys, shape=GRID):
    from skimage.draw import polygon
    m = np.zeros(shape, bool)
    for ring in polys:
        a = np.asarray(ring, float)
        rr, cc = polygon(a[:, 1], a[:, 0], shape)
        m[rr, cc] ^= True                                  # even-odd: a hole's ring clears
    return m


def load(path):
    J = json.load(open(path))
    out = {}
    for k, q in J['items'].items():
        vs = {}
        for v, a in q['views'].items():
            if a['verdict'] == 'unsure':
                continue
            vs[v] = 'hidden' if a['verdict'] == 'hidden' else (a['points'] if a['verdict'] == 'point' else _raster(a['polygons']))
        out[k] = dict(number=q['number'], title=q['title'], family=q['family'],
                      home=(q['home']['view'], _raster(q['home']['polygons'])), views=vs,
                      passes={v: a['pass'] for v, a in q['views'].items()})
    return out


if __name__ == '__main__':
    a = sys.argv[1:]
    J = make(a[1:], 'Michael Bishop on the labelling page (charkit label serve), 2026-10-01')
    json.dump(J, open(a[0], 'w'), indent=1)
    n = sum(1 for q in J['items'].values() for x in q['views'].values() if x['verdict'] not in ('unsure',))
    print('wrote', a[0], len(J['items']), 'items,', n, 'answered views')
