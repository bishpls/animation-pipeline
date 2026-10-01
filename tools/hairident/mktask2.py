"""The identity task's second pass (Michael 2026-10-01, via the coordinator): only the (lock, view) pairs pass 1 left
open or coarse, each asked again with the point mark available (P: the lock is there but no region covers it).

  unsure       every view he marked unsure
  hidden       a view he marked not visible where the hull's projection shows >= HIDDEN_VIS of the lock
  shared       a back-mass view (three-quarter, profile, back) whose answer region he gave to two or more locks: the
               region holds several locks; the proposal is his own answer (Enter keeps it), a point marks the lock

The other views show pass 1's answers as context (not asked).

    python tools/hairident/mktask2.py [--pass1 charkit/out/hairident/label] [--out charkit/out/hairident/label2]
"""
import json, os, shutil, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HIDDEN_VIS = 0.30
BACKMASS = ('three_quarter', 'profile', 'back')


def _opt(a, k, d):
    return a[a.index(k) + 1] if k in a else d


LOCKMAP_VIEWS = ('three_quarter', 'profile')     # the views hair_lock_map is registered for (the manifest)
LOCKMAP_MIN = 0.006                              # L^2: a lock map region's part on the uncovered hair, at least


def lockmap_regions(out, T, regions_npz, ctx_path, log=print):
    """the registered lock map's locks (tools/hairident/lockmap.py's regions on the design grids) added where pass 1's
    partition has no region (the back mass the splitter never cut) in LOCKMAP_VIEWS: new index masks under out/img,
    the task's regions updated -> {view: (full-grid index image, ids)} for the projections."""
    import pickle
    import numpy as np
    from PIL import Image
    from scipy import ndimage
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import regions as rg
    I = pickle.load(open(os.path.join(ROOT, 'charkit/out/hairsplit/inputs.pkl'), 'rb'))
    C = pickle.load(open(ctx_path, 'rb'))
    R = rg.regions(I, C['masks'])
    M = np.load(regions_npz)
    T_, TL, _ = rg.load_truth()
    from charkit import hairlocks as hk
    full = {}
    for v in [w['id'] for w in T['views']]:
        img, ids = R[v]['img'].copy(), list(R[v]['ids'])
        if v in LOCKMAP_VIEWS and v in M.files:
            d = I['views'][v]
            t = hk.fill_walls(T_[v], d['hair'])
            other = np.zeros(img.shape, bool)
            for i, l in enumerate(TL[v]):
                if hk.family_of(l) not in rg.TRUTH_FAMS:
                    other |= t == i
            for pm in (d.get('pieces') or {}).values():
                other |= pm
            free = d['hair'] & (img == 0) & ~other
            lab = M[v]
            n0 = len(ids)
            for k in np.unique(lab[free & (lab > 0)]):
                m = free & (lab == k)
                cl, n = ndimage.label(m)
                for j in range(1, n + 1):
                    mj = cl == j
                    if mj.sum() < LOCKMAP_MIN * I['ppl'] ** 2:
                        continue
                    ids.append('M:%d' % k if n == 1 else 'M:%d.%d' % (k, j))
                    img[mj] = len(ids)
            log('%s: %d lock map regions added on the uncovered hair' % (v, len(ids) - n0))
            vw = next(w for w in T['views'] if w['id'] == v)
            r0, c0, H, W = vw['crop']
            assert len(ids) < 255
            Image.fromarray(img[r0:r0 + H, c0:c0 + W].astype(np.uint8)).save(os.path.join(out, 'img', '%s_regions.png' % v))
            info = dict(T['regions'][v].get('info') or {})
            for rid in ids[n0:]:
                info[rid] = 'a lock of the lock map (hair_lock_map, registered for this view)'
            T['regions'][v] = dict(mask='img/%s_regions.png' % v, ids=ids, info=info)
        full[v] = (img, ids)
    return full, I, C


def reproposed(it, v, full, I, C):
    """the hull's projection of an item's home region onto a view's new partition -> (region or None, share, visible)."""
    import numpy as np
    import mktask as mk
    hv, hr = it['home']['view'], it['home']['regions'][0]
    img, ids = full[hv]
    m = img == ids.index(hr) + 1
    rr, cc = np.nonzero(m)
    sel = (rr % 2 == 0) & (cc % 2 == 0)
    P = mk.Projector(C)
    Pw = P.lift(hv, rr[sel], cc[sel])
    img2, ids2 = full[v]
    r, c, vis = P.project(Pw, v, img2.shape)
    nv = int(vis.sum())
    if not nv:
        return None, 0.0, 0.0
    lab = img2[np.clip(np.round(r[vis]).astype(int), 0, img2.shape[0] - 1), np.clip(np.round(c[vis]).astype(int), 0, img2.shape[1] - 1)]
    u, n = np.unique(lab[lab > 0], return_counts=True)
    if not len(u):
        return None, 0.0, nv / max(1, len(Pw))
    k = int(np.argmax(n))
    return ids2[u[k] - 1], float(n[k]) / nv, nv / max(1, len(Pw))


def main(a):
    p1 = _opt(a, '--pass1', os.path.join(ROOT, 'charkit/out/hairident/label'))
    out = _opt(a, '--out', os.path.join(ROOT, 'charkit/out/hairident/label2'))
    T = json.load(open(os.path.join(p1, 'task.json')))
    A = json.load(open(os.path.join(p1, 'answers.json')))
    os.makedirs(out, exist_ok=True)
    if os.path.exists(os.path.join(out, 'img')):
        shutil.rmtree(os.path.join(out, 'img'))
    shutil.copytree(os.path.join(p1, 'img'), os.path.join(out, 'img'))
    shared = defaultdict(list)
    for it in T['items']:
        for v, x in A['items'].get(it['id'], {}).get('views', {}).items():
            for rid in x['regions']:
                shared[(v, rid)].append(it['number'])
        shared[(it['home']['view'], it['home']['regions'][0])].append(it['number'])
    full = None
    lm = _opt(a, '--lockmap', os.path.join(ROOT, 'charkit/out/hairident/refgen/check_lines_2/regions.npz'))
    if lm and os.path.exists(lm):
        full, I, C = lockmap_regions(out, T, lm, _opt(a, '--ctx', os.path.join(ROOT, 'charkit/out/hairident/ctx_r2.pkl')))
    items = []
    for it in T['items']:
        rec = A['items'].get(it['id'], {}).get('views', {})
        ask, why, tag = [], {}, {}
        for v, x in rec.items():
            p = it['proposals'][v]
            vis = p['evidence']['visible']
            if x['verdict'] == 'unsure':
                ask.append(v); why[v] = 'pass 1: unsure'; tag[v] = 'unsure in pass 1'
            elif x['verdict'] == 'hidden' and vis >= HIDDEN_VIS:
                ask.append(v); why[v] = 'pass 1: not visible, but the hull\'s projection shows %d%% of it here' % round(100 * vis)
                tag[v] = 'not visible in pass 1, the hull shows %d%%' % round(100 * vis)
            elif v in BACKMASS and x['regions'] and any(len(shared[(v, r)]) > 1 for r in x['regions']):
                others = sorted({n for r in x['regions'] for n in shared[(v, r)]} - {it['number']})
                ask.append(v)
                tag[v] = 'its region shared with lock%s %s' % ('s' if len(others) > 1 else '', ', '.join(map(str, others)))
                why[v] = 'pass 1: this region, also given for lock%s %s: if lock %d is only part of it, mark where (P)' % (
                    's' if len(others) > 1 else '', ', '.join(map(str, others)), it['number'])
        if not ask:
            continue
        q = dict(it)
        q['ask'] = [v for v in [w['id'] for w in T['views']] if v in ask]
        props, ctx = {}, {}
        for v in [w['id'] for w in T['views']]:
            if v == it['home']['view']:
                continue
            x = rec.get(v)
            if v in ask:
                p = dict(it['proposals'][v])
                if x and x['verdict'] in ('accept', 'fixed'):
                    # his own pass-1 answer as the proposal: Enter keeps it
                    p = dict(p, regions=list(x['regions']), confidence=None,
                             reason=why[v] + '. Enter keeps your pass-1 answer.')
                else:
                    p = dict(p, reason=why[v] + '. The agent: ' + p['reason'])
                    if full is not None and v in LOCKMAP_VIEWS:
                        # the lock map's regions now cover the back mass: the hull's projection asked again
                        rid, share, vis_ = reproposed(it, v, full, I, C)
                        if rid and share >= 0.15:
                            p = dict(p, regions=[rid], confidence=round(min(0.9, 0.3 + share), 2),
                                     reason=why[v] + '. The agent, on the lock map\'s regions: the hull\'s projection '
                                     'puts %d%% of it on %s' % (round(100 * share), rid))
                props[v] = p
            else:
                note = 'pass 1: ' + ('not visible' if not x or x['verdict'] == 'hidden' else
                                     '%s %s' % (x['verdict'], ' + '.join(x['regions'])))
                ctx[v] = dict(regions=list(x['regions']) if x else [], note=note)
        q['proposals'], q['context'] = props, ctx
        q['reason'] = 'Asked again: ' + '; '.join('%s (%s)' % (v.replace('_', '-'), tag[v]) for v in q['ask'])
        items.append(q)
    task = dict(T, id='clawd_hair_identity_pass2', title='Clawd\'s hair, second pass: the open and coarse links',
                summary=dict(asked='Only the views pass 1 left open or coarse. New: P marks where a lock is when no '
                                   'region covers it (the back mass the splitter never cut). Enter keeps the proposal; '
                                   'Y / N / H / U / P per view.', minutes=max(3, round(len(items) * 0.5)),
                             used_for='Scoring only: the held-out cross-view truth, with point marks as location truth '
                                      '(the fitted lock must cover the point).'),
                answers='answers.json', items=items,
                provenance=dict(T.get('provenance', {}), pass1=os.path.relpath(p1, ROOT), hidden_vis=HIDDEN_VIS))
    json.dump(task, open(os.path.join(out, 'task.json'), 'w'), indent=1)
    for q in items:
        print(q['number'], q['id'], q['ask'], '|', q['reason'])
    print('wrote', os.path.join(out, 'task.json'), len(items), 'items,', sum(len(q['ask']) for q in items), 'views')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
