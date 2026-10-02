"""The hair's cross-view lock identity as a labelling task (charkit.label; tool/hairident step 2): ~20 drawn locks (the
side locks, the side flicks and strands, the back's hem flicks), each in its home view, with the agent's proposal for
the same lock in every other view, its reason and confidence. Michael confirms or fixes them on the page; the answers
are the held-out correspondence truth (scoring only, never fitted).

Proposals from geometry:
  the hull's projection  the home region's pixels cast onto the hair's envelope (the crown chart's R: the visual hull's
                         hair, lockshell.envelope_points), projected into the other view and kept where they are the
                         front-most envelope there (within VIS_TOL L): the share landing in each drawn region
  tip heights            the regions' lowest rows against the eye line (one vertical scale in every view), in L
  layer order            the splitter's T-junction ranks (the regions' majority lock): a pair of neighbouring locks
                         keeps its order in the other view
  names                  the lock truth's names (rule 7, calls C/H: the same physical lock read across views): a second
                         opinion, reported beside the geometry; where they disagree the confidence drops

    python tools/hairident/mktask.py [--ctx charkit/out/hairident/ctx_r2.pkl] [--out charkit/out/hairident/label]
"""
import json, math, os, pickle, sys
import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import regions as rg
from charkit.geom import lockshell as ls
from charkit.geom.hairpieces import view_px

VIEWS = rg.VIEWS
NAMES = {'front': 'Front', 'three_quarter': 'Three-quarter', 'profile': 'Profile (her left)', 'back': 'Back'}
VIS_TOL = 0.04             # L: a projected point this far behind the view's front-most envelope still shows
PAD = 0.10                 # L: the crops' margin round the hair
SAMPLE = 2                 # px: the home region's pixels sampled every this many

# the items: (group, home view, home region, title); her right/left as in the lock truth (rule 14)
ITEMS = [
    ('Side locks', 'front', 'T:side_locks/R_front', 'her right face-framing lock (by her right eye)'),
    ('Side locks', 'front', 'T:side_locks/R_jaw', 'her right jaw lock, the next one out and down'),
    ('Side locks', 'front', 'OUTER_R1', 'her right outer side lock, upper'),
    ('Side locks', 'front', 'OUTER_R2', 'her right outer side lock, lower'),
    ('Side locks', 'front', 'T:side_locks/L_front', 'her left face-framing lock (under the star)'),
    ('Side locks', 'front', 'T:side_locks/L_jaw', 'her left jaw lock, the next one out and down'),
    ('Side locks', 'front', 'OUTER_L1', 'her left outer side lock, upper'),
    ('Side locks', 'front', 'OUTER_L2', 'her left outer side lock, lower'),
    ('Side flicks and strands', 'front', 'T:flyaways/flick_R1', 'her right upper side flick'),
    ('Side flicks and strands', 'front', 'T:flyaways/flick_R2', 'her right middle side flick'),
    ('Side flicks and strands', 'front', 'T:flyaways/flick_L1', 'her left upper side flick'),
    ('Side flicks and strands', 'front', 'T:flyaways/flick_L2', 'her left middle side flick'),
    ('Side flicks and strands', 'front', 'T:flyaways/under_bun_R', 'the strand under her right bun'),
    ('Side flicks and strands', 'front', 'T:flyaways/under_bun_L', 'the strand under her left bun'),
    ('Back hem flicks', 'back', 'T:lower_back/flick_L3', 'the hem\'s outermost flick on her left'),
    ('Back hem flicks', 'back', 'T:lower_back/flick_L2', 'the hem flick second from her left'),
    ('Back hem flicks', 'back', 'T:lower_back/flick_L1', 'the hem flick third from her left'),
    ('Back hem flicks', 'back', 'T:lower_back/flick_C', 'the hem\'s centre flick'),
    ('Back hem flicks', 'back', 'T:lower_back/flick_R1', 'the hem flick third from her right'),
    ('Back hem flicks', 'back', 'T:lower_back/flick_R2', 'the hem flick second from her right'),
    ('Back hem flicks', 'back', 'T:lower_back/flick_R3', 'the hem\'s outermost flick on her right'),
]


def _opt(a, k, d):
    return a[a.index(k) + 1] if k in a else d


def crops(I, R):
    """one crop size for every view (one scale), each round its own hair -> {view: (r0, c0)}, (H, W)."""
    ppl = I['ppl']
    boxes = {}
    for v in VIEWS:
        m = I['views'][v]['hair'] | (R[v]['img'] > 0)
        ys, xs = np.nonzero(m)
        boxes[v] = (ys.min(), ys.max(), xs.min(), xs.max())
    pad = int(PAD * ppl)
    H = max(b[1] - b[0] for b in boxes.values()) + 2 * pad
    W = max(b[3] - b[2] for b in boxes.values()) + 2 * pad
    shape = I['views']['front']['hair'].shape
    org = {}
    for v, (y0, y1, x0, x1) in boxes.items():
        cy, cx = (y0 + y1) // 2, (x0 + x1) // 2
        r0 = int(min(max(cy - H // 2, 0), shape[0] - H))
        c0 = int(min(max(cx - W // 2, 0), shape[1] - W))
        org[v] = (r0, c0)
    return org, (int(H), int(W))


class Projector:
    """the hull's projection of a view's pixels into another view (lockshell's envelope: the hair's visual hull)."""

    def __init__(self, ctx):
        self.F, self.views, self.hf, self.L = ctx['F'], ctx['views'], ctx['hull_frame'], ctx['L']
        self.depth = {}

    def lift(self, v, rows, cols):
        return ls.envelope_points(self.F, self.views[v], self.views[v].az, self.hf, cols, rows, self.L)

    def project(self, P, v, shape):
        """world points -> (rows, cols, visible) in view v (visible: within VIS_TOL L of the front-most envelope)."""
        az = self.views[v].az
        c, r = view_px(P, self.views[v], az, False, self.hf)
        Q = ls.envelope_points(self.F, self.views[v], az, self.hf, c, r, self.L)
        a = math.radians(az)
        e = np.array([math.sin(a), -math.cos(a), 0.0])
        s_ = self.hf[0]
        vis = (P @ e) >= (Q @ e) - VIS_TOL * s_
        inside = (r >= 0) & (r < shape[0]) & (c >= 0) & (c < shape[1])
        return r, c, vis & inside


def layer_of(S, v, mask):
    img = S['views'][v]['img']
    ids = img[mask & (img > 0)]
    if not len(ids):
        return None
    lid = int(np.bincount(ids).argmax())
    x = S['views'][v]['locks'].get(lid)
    return None if x is None else float(x.get('layer') or 0.0)


def main(args):
    ctx_path = _opt(args, '--ctx', os.path.join(ROOT, 'charkit/out/hairident/ctx_r2.pkl'))
    out = _opt(args, '--out', os.path.join(ROOT, 'charkit/out/hairident/label'))
    os.makedirs(os.path.join(out, 'img'), exist_ok=True)
    I = pickle.load(open(os.path.join(ROOT, 'charkit/out/hairsplit/inputs.pkl'), 'rb'))
    C = pickle.load(open(ctx_path, 'rb'))
    R = rg.regions(I, C['masks'])
    S = ls.load_split(os.path.join(ROOT, rg.SPLIT))
    ppl = I['ppl']
    org, (H, W) = crops(I, R)
    P = Projector(C)

    # the outer side locks: the front's two largest splitter regions per side
    front = R['front']
    axis = I['views']['front']['col_axis']
    sides = {'R': [], 'L': []}
    for k, rid in enumerate(front['ids']):
        if not rid.startswith('S:') or front['family'].get(rid) != 'side_locks':
            continue
        m = front['img'] == k + 1
        ys, xs = np.nonzero(m)
        # her right is the viewer's left in front
        sides['R' if xs.mean() < axis else 'L'].append((int(m.sum()), ys.mean(), rid))
    pick = {}
    for s, q in sides.items():
        top = sorted(sorted(q, reverse=True)[:2], key=lambda t: t[1])
        for j, (_, _, rid) in enumerate(top):
            pick['OUTER_%s%d' % (s, j + 1)] = rid

    def mask(v, rid):
        return R[v]['img'] == R[v]['ids'].index(rid) + 1

    def tip_z(v, m):
        ys, _ = np.nonzero(m)
        return (ys.max() - I['views'][v]['row_eye']) / ppl

    items = []
    for n, (grp, hv, hr, title) in enumerate(ITEMS, 1):
        hr = pick.get(hr, hr)
        if hr not in R[hv]['ids']:
            print('skipped (no region):', hr)
            continue
        m = mask(hv, hr)
        rr, cc = np.nonzero(m)
        sel = (rr % SAMPLE == 0) & (cc % SAMPLE == 0)
        rr, cc = rr[sel], cc[sel]
        Pw = P.lift(hv, rr, cc)
        zt = tip_z(hv, m)
        lay = layer_of(S, hv, m)
        name = hr[2:] if hr.startswith('T:') else None
        props = {}
        for v in VIEWS:
            if v == hv:
                continue
            r, c, vis = P.project(Pw, v, R[v]['img'].shape)
            nv = int(vis.sum())
            hits = {}
            if nv:
                sh = R[v]['img'].shape
                lab = R[v]['img'][np.clip(np.round(r[vis]).astype(int), 0, sh[0] - 1),
                                  np.clip(np.round(c[vis]).astype(int), 0, sh[1] - 1)]
                for k in np.unique(lab[lab > 0]):
                    hits[R[v]['ids'][k - 1]] = float((lab == k).sum()) / nv
            vshare = nv / max(1, len(Pw))
            ranked = sorted(hits.items(), key=lambda t: -t[1])
            geo = ranked[0][0] if ranked and ranked[0][1] >= 0.15 else None
            same = 'T:' + name if name and ('T:' + name) in R[v]['ids'] else None
            # where to look (the projection's box, in the crop's pixels)
            where = None
            # where to look: the visible projection's box, else where the hidden points project (the crop's pixels)
            sel_ = vis if nv else np.isfinite(r) & np.isfinite(c)
            if sel_.any():
                r0, c0 = org[v]
                where = [float(c[sel_].min() - c0), float(r[sel_].min() - r0), float(c[sel_].max() - c0),
                         float(r[sel_].max() - r0)]
            reasons = []
            if same and geo == same:
                choice, conf = same, 0.6 + 0.4 * min(1.0, hits[same] / 0.5)
                reasons.append('the hull\'s projection puts %d%% of it here' % round(100 * hits[same]))
                reasons.append('the lock truth names both %s' % name.split('/')[1])
            elif same:
                choice = same
                conf = 0.45 + 0.3 * min(1.0, hits.get(same, 0) / 0.3)
                reasons.append('the lock truth names both %s' % name.split('/')[1])
                if geo:
                    reasons.append('but the hull\'s projection puts %d%% on %s (%d%% here)' % (
                        round(100 * hits[geo]), geo[2:].split('/')[-1], round(100 * hits.get(same, 0))))
                else:
                    reasons.append('the hull\'s projection shows %d%% of it in this view' % round(100 * vshare))
            elif geo and vshare >= 0.2:
                choice = geo
                second = ranked[1][1] if len(ranked) > 1 else 0.0
                conf = max(0.15, min(0.9, hits[geo] * (1 - second / max(hits[geo], 1e-6)) + 0.2))
                reasons.append('the hull\'s projection puts %d%% of it here%s' % (
                    round(100 * hits[geo]), (' (next: %d%%)' % round(100 * second)) if second else ''))
            else:
                choice = None
                conf = 0.5 + 0.45 * (1 - min(1.0, vshare / 0.2))
                reasons.append('the hull\'s projection hides %d%% of it in this view' % round(100 * (1 - vshare)))
            if choice:
                mc = mask(v, choice)
                dz = tip_z(v, mc) - zt
                reasons.append('tips %.2f L apart in height' % abs(dz))
                # tips far apart in height: a different lock, or a region holding several (the confidence falls
                # linearly to 0.3x at 0.3 L)
                conf *= max(0.3, 1.0 - max(0.0, abs(dz) - 0.05) / 0.36)
                lb = layer_of(S, v, mc)
                if lay is not None and lb is not None:
                    reasons.append('layer %.1f there, %.1f here' % (lay, lb))
            props[v] = dict(regions=[choice] if choice else [], confidence=round(float(conf), 2),
                            reason='; '.join(reasons), where=where,
                            evidence=dict(visible=round(vshare, 3), hits={k: round(x, 3) for k, x in ranked[:4]},
                                          tip_z=round(float(zt), 3)))
        items.append(dict(id=hr.replace('T:', '').replace('/', '.').replace(':', ''), number=n, group=grp, title=title,
                          home=dict(view=hv, regions=[hr]),
                          reason='tip %.2f L below the eye line; %s' % (zt, 'named %s in the lock truth' % name.split('/')[1]
                                                                         if name else 'a splitter lock of the side locks'),
                          proposals=props))
    # layer order between neighbouring items (their home regions touching) in each other view
    for it in items:
        hv = it['home']['view']
        m = ndimage.binary_dilation(mask(hv, it['home']['regions'][0]), iterations=4)
        for v, p in it['proposals'].items():
            if not p['regions']:
                continue
            agree = dis = 0
            la = layer_of(S, hv, mask(hv, it['home']['regions'][0]))
            lb = layer_of(S, v, mask(v, p['regions'][0]))
            for jt in items:
                if jt is it or jt['home']['view'] != hv or not jt['proposals'].get(v, {}).get('regions'):
                    continue
                if not (m & mask(hv, jt['home']['regions'][0])).any():
                    continue
                ja = layer_of(S, hv, mask(hv, jt['home']['regions'][0]))
                jb = layer_of(S, v, mask(v, jt['proposals'][v]['regions'][0]))
                if None in (la, lb, ja, jb) or abs(la - ja) < 0.3 or abs(lb - jb) < 0.3:
                    continue
                if (la - ja) * (lb - jb) > 0:
                    agree += 1
                else:
                    dis += 1
            if agree or dis:
                p['reason'] += '; layer order %s with %d of %d neighbours' % ('agrees' if not dis else 'disagrees',
                                                                             dis or agree, agree + dis)
                if dis:
                    p['confidence'] = round(p['confidence'] * 0.85, 2)

    # pictures and region masks, cropped
    views = []
    regions = {}
    for v in VIEWS:
        r0, c0 = org[v]
        rgb = (np.clip(I['views'][v]['rgb'], 0, 1) * 255).astype(np.uint8)[r0:r0 + H, c0:c0 + W]
        Image.fromarray(rgb).save(os.path.join(out, 'img', '%s.png' % v))
        idx = R[v]['img'][r0:r0 + H, c0:c0 + W]
        assert len(R[v]['ids']) < 255
        Image.fromarray(idx.astype(np.uint8)).save(os.path.join(out, 'img', '%s_regions.png' % v))
        views.append(dict(id=v, name=NAMES[v], image='img/%s.png' % v, crop=[int(r0), int(c0), H, W]))
        regions[v] = dict(mask='img/%s_regions.png' % v, ids=R[v]['ids'], info=R[v]['info'])
    task = dict(format='charkit-label-task/1', id='clawd_hair_identity',
                title='Clawd\'s hair: which lock is which across the views',
                summary=dict(asked='For each numbered lock (outlined solid blue in its home view), is the dashed '
                                   'outline in each other view the same lock? Enter accepts every proposal; Y / N / H '
                                   '(not visible) / U (unsure) per view; N then click the right one.',
                             minutes=15,
                             used_for='Scoring only: the held-out truth the cross-view lock fit is scored against '
                                      '(links right / wrong / missing). Never fitted to.'),
                answers='answers.json', views=views, regions=regions, items=items,
                provenance=dict(by='tools/hairident/mktask.py', ctx=os.path.relpath(ctx_path, ROOT),
                                truth=rg.TRUTH, split=rg.SPLIT, vis_tol_L=VIS_TOL))
    json.dump(task, open(os.path.join(out, 'task.json'), 'w'), indent=1)
    for it in items:
        print('%2d %-22s %s' % (it['number'], it['id'], '  '.join(
            '%s=%s(%.2f)' % (v[:2], (p['regions'][0][2:].split('/')[-1] if p['regions'] else '-'), p['confidence'])
            for v, p in it['proposals'].items())))
    print('wrote', os.path.join(out, 'task.json'))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
