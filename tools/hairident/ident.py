"""The cross-view lock fit (charkit.geom.lockident) run on a build's context and scored against cross-view links: the
held-out correspondence truth (Michael's answers on the labelling page) or the agent's proposals.

    python tools/hairident/ident.py BUILD OUT [--cfg JSON|@FILE] [--truth charkit/refs/clawd/hair_lock_links.json]
                                    [--holdout] [--pilot]
        OUT/ident.json: the fit's report, the links scored (right / wrong / missing / extra per item and view), and
        with --holdout each view held out in turn (the locks fitted on the other three, then assigned in the held-out
        view without refitting: its link accuracy and the assigned targets' IoU); --pilot scores the pilot's own
        association (lockshell.build_shells on the same context) the same way.
"""
import json, os, pickle, sys, time
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ribbon as rb
from charkit.geom import lockident as li, lockshell as ls

PILOT = {"families": ["side_locks"], "groups": [{"family": "lower_back", "view": "back", "phi": [100, 175],
                                                 "replace": False, "opts": {"prior_depth": 10.0, "contain": 5.0,
                                                                            "hug_free": 0.3}}]}


def region_mask(R, vn, rids):
    m = np.zeros(R[vn]['img'].shape, bool)
    for rid in rids:
        if rid in R[vn]['ids']:
            m |= R[vn]['img'] == R[vn]['ids'].index(rid) + 1
    return m


def score(locks, T, views=None, share=0.3, near_px=3):
    """locks: [dict(name, assign {view: mask})]; T: the held-out truth (tools/hairident/truth.load: per item its home
    (view, mask) and per answered view a mask, 'hidden' or points) -> dict(items, counts per view and all).
    A lock is an item's when its mask in the item's home view covers `share` of the home region (the most covering);
    an item no lock covers is 'unmatched' (the fit has no lock there: coverage, not identity). Per answered view:
    a positive link (a region, or points) is right when the lock's mask there lies `share` or more on the truth's
    region (points: the mask covers a point, within near_px), wrong when it lies elsewhere, missing when the lock isn't
    assigned there; a negative link (not visible) is right when the lock isn't assigned there, extra when it is."""
    from scipy import ndimage
    out, cnt = {}, {}

    def add(k, v):
        c = cnt.setdefault(k, {})
        c[v] = c.get(v, 0) + 1
    for item, q in T.items():
        hv, H = q['home']
        if not H.any():
            continue
        best = (0.0, None)
        for lk in locks:
            m = lk['assign'].get(hv)
            if m is None:
                continue
            c = float((m & H).sum()) / H.sum()
            if c > best[0]:
                best = (c, lk)
        lk = best[1] if best[0] >= share else None
        res = dict(lock=None if lk is None else lk['name'], cover=round(best[0], 3), views={})
        for vn, ans in q['views'].items():
            if vn == hv or (views and vn not in views):
                continue
            if lk is None:
                v = 'unmatched'
            else:
                m = lk['assign'].get(vn)
                if isinstance(ans, str):
                    v = 'right_neg' if m is None else 'extra'
                elif m is None:
                    v = 'missing'
                elif isinstance(ans, list):
                    mm = ndimage.binary_dilation(m, iterations=near_px)
                    ok = any(0 <= int(round(y)) < mm.shape[0] and 0 <= int(round(x)) < mm.shape[1] and
                             mm[int(round(y)), int(round(x))] for x, y in ans)
                    v = 'right_pos' if ok else 'wrong'
                else:
                    on = float((m & ans).sum()) / max(1, m.sum())
                    v = 'right_pos' if on >= share else 'wrong'
            res['views'][vn] = v
            add(vn, v)
            add('all', v)
            add('fam:' + q['family'], v)
        out[item] = res
    for k, c in cnt.items():
        npos = c.get('right_pos', 0) + c.get('wrong', 0) + c.get('missing', 0)
        nneg = c.get('right_neg', 0) + c.get('extra', 0)
        c['positives'], c['negatives'] = npos, nneg
        c['pos_accuracy'] = round(c.get('right_pos', 0) / npos, 3) if npos else None
        c['neg_accuracy'] = round(c.get('right_neg', 0) / nneg, 3) if nneg else None
        n = npos + nneg
        c['accuracy'] = round((c.get('right_pos', 0) + c.get('right_neg', 0)) / n, 3) if n else None
    return dict(items=out, counts=cnt)


def masks_of(idt):
    """the joint fit's locks with their assigned targets' masks per view."""
    out = []
    for lk, mt in zip(idt.locks, idt.meta):
        A = {}
        for vn, tid in mt['assign'].items():
            for t in idt.targets(vn, mt['family']):
                if t['id'] == tuple(tid):
                    A[vn] = t['mask']
        out.append(dict(name=lk.name, assign=A))
    return out


def pilot_masks(sc, ctx):
    """the pilot's own association (lockshell.build_shells: each lock's drawn views) as masks per view."""
    res = ls.build_shells(ctx['F'], ctx['masks'], ctx['views'], ctx['hull_frame'], ctx['L'],
                          dict(PILOT, split=ctx['split']), log=None)
    out = []
    for fam, parts in res['parts'].items():
        for p in parts:
            out.append(dict(name=p['fit']['name'], assign=dict(p.get('_drawn') or {})))
    return out, res['report']


def run(build, out, cfg, T, holdout=False, pilot=False, log=print):
    ctx, R = rb.setup(build, out)
    sc = li.Scene(ctx)
    t0 = time.time()
    idt = li.Ident(sc, cfg, log=log).run()
    rep = idt.report()
    rep['seconds'] = round(time.time() - t0, 1)
    rep['score'] = score(masks_of(idt), T)
    res = dict(cfg=cfg, fit=rep)
    if holdout:
        res['holdout'] = {}
        for hv in li.VIEWS:
            vs = [v for v in li.VIEWS if v != hv]
            sc2 = li.Scene(ctx)
            idt2 = li.Ident(sc2, cfg, views=vs, log=log).run()
            # the held-out view: the fitted locks assigned there without a refit
            idt2.views = li.VIEWS
            A = idt2.assign(hv)
            for i, t in A.items():
                idt2.meta[i]['assign'][hv] = t['id']
            ms = masks_of(idt2)
            sc_ = score(ms, T, views=[hv])
            ious = []
            for i, t in A.items():
                lk = idt2.locks[i]
                part = lk.shell()
                ious.append(sc2.iou(lk, part, {hv: t['mask']})[hv])
            res['holdout'][hv] = dict(score=sc_['counts'].get(hv), assigned=len(A),
                                      iou_mean=round(float(np.mean(ious)), 3) if ious else None,
                                      in_fit=rep['score']['counts'].get(hv))
    if pilot:
        pm, prep = pilot_masks(sc, ctx)
        res['pilot'] = dict(score=score(pm, T), fitted_2plus=prep.get('fitted_2plus'), n=len(prep['locks']))
    return res


def main(a):
    build, out = a[0], a[1]
    os.makedirs(out, exist_ok=True)
    cfg = rb._opt(a, '--cfg', None)
    cfg = json.load(open(cfg[1:])) if cfg and cfg.startswith('@') else (json.loads(cfg) if cfg else dict(PILOT))
    import truth as tr
    T = tr.load(rb._opt(a, '--truth', os.path.join(ROOT, 'charkit/refs/clawd/hair_lock_links.json')))
    res = run(build, out, cfg, T, '--holdout' in a, '--pilot' in a)
    json.dump(res, open(os.path.join(out, 'ident.json'), 'w'), indent=1, default=str)
    f = res['fit']
    print('locks %d, in 2+ views %d, %.0f s; links: %s' % (f['n'], f['fitted_2plus'], f['seconds'],
                                                           json.dumps(f['score']['counts'].get('all'))))
    if 'pilot' in res:
        print('pilot: in 2+ views %s; links %s' % (res['pilot']['fitted_2plus'],
                                                  json.dumps(res['pilot']['score']['counts'].get('all'))))
    for hv, h in (res.get('holdout') or {}).items():
        print('held out %s: %s (in fit %s), IoU %s' % (hv, json.dumps(h['score']), json.dumps(h['in_fit']), h['iou_mean']))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
