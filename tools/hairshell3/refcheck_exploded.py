"""Refcheck an exploded lock breakdown sheet (four views: front, three-quarter, profile, back; every lock its own
numbered flat-colour piece, pulled slightly outward) against the body turnaround and the 52-lock truth, by the
criteria pre-registered in charkit/out/hairshell3/ref/criteria.md:

  (i)   one scale: the views' registered S (px per L) within 5%
  (ii)  the pilot locks (side_locks/* in front, three-quarter, profile; lower_back/flick_* in back, profile): per view
        >= 70% matched at IoU >= 0.5, each sheet lock translated by at most 0.05 L (the explode offset) at its view's
        one scale
  (iii) identity: truth locks drawn in 2+ views; a view pair where the lock is matched in both holds when the two sheet
        locks are the same (colour dE76 <= 10; numbers agree where read); >= 80% of >= 8 evaluable pairs
  (iv)  reported: lock counts per scored family against the truth's; lock lines against the turnaround's (refcheck's
        line F with its random-partition floor); the closed silhouette's IoU; score5's lock IoU without translation

Reuses tools/hair5truth/refcheck.py (masks, figures, register, warp, regions, boundaries, line F, Voronoi floor),
tools/hair5truth/score5.py (the truth's floors) and charkit/hairlocks.py (the truth, fill_walls, fill_labels, score).

    python tools/hairshell3/refcheck_exploded.py SHEET.png OUTDIR [--ctx CTX5.pkl] [--numbers NUMBERS.json]

OUTDIR gets result.json, identity.json, regions.npz (the sheet's locks on the design grids) and the pictures
(VIEW_match.png: the registered sheet locks outlined in their colour over the truth's locks, matches labelled;
VIEW_regions.png: the panel's segmentation with region ids, for reading the numbers). NUMBERS.json (optional):
{view: {region id: number read on the sheet}}.
"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools', 'hair5truth'))
import refcheck as rc
from charkit import hairlocks as hk

VIEWS = ('front', 'three_quarter', 'profile', 'back')
TRUTH = os.path.join(ROOT, 'charkit/refs/clawd/hair_locks_truth.npz')
# pre-registered (criteria.md); not changed after the call
S_TOL = 0.05
SHIFT_L = 0.05
MATCH_IOU = 0.5
LOOSE_IOU = 0.3
PILOT_FRAC = 0.70
ID_FRAC = 0.80
ID_MIN_PAIRS = 8
ID_DE = 10.0
MIN_GRID_PX = 25
PILOT = {'front': ('side_locks',), 'three_quarter': ('side_locks',), 'profile': ('side_locks', 'lower_back'),
         'back': ('lower_back',)}
SCORED_FAMS = ('bangs', 'side_locks', 'lower_back', 'flyaways', 'ahoge')
# segmentation (criteria.md: may change only to follow the drawn pieces; logged in result.md)
CLOSE_R = 6           # sheet px: closing radius that bridges the explode gaps (white gap + two outlines)
MERGE_GAP = 4         # sheet px: same-colour pieces closer than this through black only (a number label) are one


def is_pilot(view, label):
    f = hk.family_of(label)
    return f in PILOT[view] and (f != 'lower_back' or label.split('/', 1)[1].startswith('flick'))


def disk(r):
    y, x = np.mgrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r


def segment(frgb, fh, fl, min_px):
    """the panel's pieces: refcheck's flat-colour regions (walls: black lines, white, colour steps), each region's
    holes (its number) filled, same-colour pieces parted only by black (a digit) merged. -> (reg, median Lab per id)."""
    from scipy import ndimage
    reg, L = rc.regions(frgb, fh, fl, min_px)
    n = reg.max()
    med = {k: np.median(L[reg == k], 0) for k in range(1, n + 1)}
    # merge same-colour pieces that touch through black pixels only (a digit or an outline stroke inside the lock)
    parent = list(range(n + 1))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    for k in range(1, n + 1):
        mk = reg == k
        grow = ndimage.binary_dilation(mk, disk(MERGE_GAP)) & ~mk
        # reachable through black only: the dilation restricted to line pixels and the region itself
        via = ndimage.binary_dilation(mk, iterations=MERGE_GAP, mask=(fl | mk))
        touch = np.unique(reg[ndimage.binary_dilation(via, iterations=1) & grow])
        for j in touch:
            if j > k and np.sqrt(((med[k] - med[j]) ** 2).sum()) <= ID_DE:
                parent[find(j)] = find(k)
    lut = np.array([find(k) for k in range(n + 1)])
    reg = lut[reg]
    ids = [k for k in np.unique(reg) if k > 0]
    lut2 = np.zeros(reg.max() + 1, np.int32)
    lut2[ids] = np.arange(1, len(ids) + 1)
    reg = lut2[reg]
    # fill each region's holes (its number label), only over black pixels
    out = reg.copy()
    for k in range(1, reg.max() + 1):
        mk = reg == k
        holes = ndimage.binary_fill_holes(mk) & ~mk & (fl | (reg == 0)) & (out == 0)
        out[holes] = k
    med = {k: np.median(L[out == k], 0) for k in range(1, out.max() + 1)}
    return out, med


def closed_hair(fh, fl):
    from scipy import ndimage
    m = fh | (fl & ndimage.binary_dilation(fh, iterations=4))
    c = ndimage.binary_closing(np.pad(m, CLOSE_R + 2), disk(CLOSE_R))[CLOSE_R + 2:-CLOSE_R - 2, CLOSE_R + 2:-CLOSE_R - 2]
    return ndimage.binary_fill_holes(c | m)


def best_shift_iou(ti, ok, sc, rad):
    """max over integer shifts |d| <= rad of IoU(ti, shift(ok) & sc). -> (iou, dy, dx)."""
    ys, xs = np.nonzero(ti); yo, xo = np.nonzero(ok)
    R = int(np.ceil(rad))
    if (yo.min() - R > ys.max() or yo.max() + R < ys.min() or xo.min() - R > xs.max() or xo.max() + R < xs.min()):
        return 0.0, 0, 0
    y0, y1 = min(ys.min(), yo.min()) - R - 1, max(ys.max(), yo.max()) + R + 2
    x0, x1 = min(xs.min(), xo.min()) - R - 1, max(xs.max(), xo.max()) + R + 2
    H, W = ti.shape
    py0, px0 = max(0, -y0), max(0, -x0)
    y0c, x0c, y1c, x1c = max(0, y0), max(0, x0), min(H, y1), min(W, x1)
    tw = ti[y0c:y1c, x0c:x1c]; sw = sc[y0c:y1c, x0c:x1c]
    ow = np.pad(ok[y0c:y1c, x0c:x1c], R)
    at = int(tw.sum())
    best = (0.0, 0, 0)
    h, w = tw.shape
    for dy in range(-R, R + 1):
        for dx in range(-R, R + 1):
            if dy * dy + dx * dx > rad * rad:
                continue
            sh = ow[R - dy:R - dy + h, R - dx:R - dx + w]
            inter = int((tw & sh).sum())
            if not inter:
                continue
            u = at + int((sh & sw).sum()) - inter
            v = inter / max(1, u)
            if v > best[0]:
                best = (v, dy, dx)
    return best


def match_view(T, labels, G, rad):
    """truth (filled) against the sheet's grid locks G (0 none): the best-translation IoU matrix and the Hungarian
    assignment. -> (per truth label: dict), M, tl, cand."""
    from scipy.optimize import linear_sum_assignment
    sc = T != -2
    tl = [i for i in range(len(labels)) if (T == i).any()]
    cand = [int(c) for c in np.unique(G[G > 0]) if (G == c).sum() >= MIN_GRID_PX]
    M = np.zeros((len(tl), len(cand))); D = {}
    for a, i in enumerate(tl):
        ti = T == i
        for b, c in enumerate(cand):
            v, dy, dx = best_shift_iou(ti, G == c, sc, rad)
            M[a, b] = v; D[(a, b)] = (dy, dx)
    per = {}
    if len(tl) and len(cand):
        ra, cb = linear_sum_assignment(-M)
        asg = dict(zip(ra, cb))
    else:
        asg = {}
    for a, i in enumerate(tl):
        b = asg.get(a)
        best_b = int(np.argmax(M[a])) if len(cand) else None
        d = dict(truth=labels[i], area=int((T == i).sum()))
        if b is not None and M[a, b] > 0:
            d.update(sheet=cand[b], iou=round(float(M[a, b]), 3), shift_px=list(D[(a, b)]),
                     shift_L=round(float(np.hypot(*D[(a, b)]) / hk_ppl()), 4))
        else:
            d.update(sheet=None, iou=0.0)
        if best_b is not None:
            d.update(best_sheet=cand[best_b], best_iou=round(float(M[a, best_b]), 3))
        per[labels[i]] = d
    return per, M, tl, cand


_PPL = [212.47]


def hk_ppl():
    return _PPL[0]


def lab_hex(lab_):
    """CIELAB -> sRGB hex (for the tables)."""
    L_, a, b = lab_
    fy = (L_ + 16) / 116; fx = fy + a / 500; fz = fy - b / 200
    e = 6 / 29
    inv = lambda t: t ** 3 if t > e else 3 * e * e * (t - 4 / 29)
    xyz = np.array([inv(fx) * 0.95047, inv(fy), inv(fz) * 1.08883])
    M = np.array([[3.2404542, -1.5371385, -0.4985314], [-0.9692660, 1.8760108, 0.0415560],
                  [0.0556434, -0.2040259, 1.0572252]])
    c = M @ xyz
    c = np.where(c <= 0.0031308, 12.92 * c, 1.055 * np.clip(c, 0, None) ** (1 / 2.4) - 0.055)
    c = np.clip(c, 0, 1)
    return '#%02x%02x%02x' % tuple(int(round(x * 255)) for x in c)


def run(sheet, outdir, C, numbers=None):
    from scipy import ndimage
    os.makedirs(outdir, exist_ok=True)
    Tim, Tlab, meta = hk.load_truth(TRUTH)
    ppl = meta['ppl']; _PPL[0] = ppl
    rad = SHIFT_L * ppl
    rgb = rc.load(sheet)
    hair, skin, line = rc.masks(rgb)
    figs = rc.figures(hair, len(VIEWS))
    res = dict(sheet=os.path.relpath(sheet, ROOT), criteria='charkit/out/hairshell3/ref/criteria.md',
               params=dict(S_TOL=S_TOL, SHIFT_L=SHIFT_L, MATCH_IOU=MATCH_IOU, PILOT_FRAC=PILOT_FRAC, ID_FRAC=ID_FRAC,
                           ID_MIN_PAIRS=ID_MIN_PAIRS, ID_DE=ID_DE, CLOSE_R=CLOSE_R, MERGE_GAP=MERGE_GAP,
                           MIN_GRID_PX=MIN_GRID_PX), views={})
    grids, gridsF, sheetinfo = {}, {}, {}
    for view, (c0, c1) in zip(VIEWS, figs):
        B = rc.body_view(C, view)
        fh0, fs0, fl0 = hair[:, c0:c1], skin[:, c0:c1], line[:, c0:c1]
        rows = np.nonzero(fh0.any(1))[0]
        r0, r1 = max(0, rows.min() - 40), min(fh0.shape[0], rows.max() + 200)
        fh, fs, fl = fh0[r0:r1], fs0[r0:r1], fl0[r0:r1]
        frgb = rgb[r0:r1, c0:c1]
        fc = closed_hair(fh, fl)
        # pass 1: the closed hair alone; pass 2: + the ghost's skin within the body skin mask's height band
        bh = np.nonzero(B['hair'].any(1))[0]
        hr = np.nonzero(fc.any(1))[0]
        f0 = (bh.max() - bh.min()) / max(1, hr.max() - hr.min())
        R1 = rc.register(fc, np.zeros_like(fs), B, (0.8 * f0, 1.2 * f0), s_step=0.4 * f0 / 40)
        zs = C['grid'][view]['zs']
        gi = np.round(np.arange(fs.shape[0]) * R1['f'] + R1['di']).astype(int)
        band = np.zeros(fs.shape[0], bool)
        okr = (gi >= 0) & (gi < len(zs))
        band[okr] = (zs[gi[okr]] > -0.6) & (zs[gi[okr]] < 1.25)
        fs2 = fs & band[:, None]
        f1 = R1['f']
        R = rc.register(fc, fs2, B, (0.9 * f1, 1.1 * f1), s_step=0.2 * f1 / 40)
        R.update(c0=int(c0), r0=int(r0), S_px_per_L=round(ppl / R['f'], 1), pass1_S=round(ppl / R1['f'], 1))
        shape = B['hair'].shape
        # silhouette
        H = rc.warp_mask(fc, R, shape)
        iou = lambda a, b: float((a & b).sum() / max(1, (a | b).sum()))
        low = B['zz'] < rc.BUN_ZONE
        sil = dict(iou=round(iou(H, B['hair']), 3), iou_below_buns=round(iou(H & low, B['hair'] & low), 3))
        # the pieces
        min_px = max(4, int(round(MIN_GRID_PX / R['f'] ** 2)))
        reg, med = segment(frgb, fh, fl, min_px)
        g = rc.warp_mask(reg, R, shape).astype(np.int32)
        reach = ndimage.binary_dilation(g > 0, iterations=2)
        g = hk.fill_labels(g, reach, 2)
        grids[view] = g
        # the gap-filled variant (informational): every closed-silhouette pixel to its nearest piece
        d_, idx = ndimage.distance_transform_edt(reg == 0, return_indices=True)
        full = np.where(fc, reg[idx[0], idx[1]], 0)
        gF = rc.warp_mask(full, R, shape).astype(np.int32)
        gridsF[view] = gF
        # the truth, filled as the scorer fills it
        T = hk.fill_walls(Tim[view], np.ones(shape, bool))
        per, M, tl, cand = match_view(T, Tlab[view], g, rad)
        perF, _, _, _ = match_view(T, Tlab[view], gF, rad)
        # diagnostic (informational, not a criterion): the matched locks' median shift taken into the view's offset,
        # each lock again free within 0.05 L of it
        sh = np.array([d['shift_px'] for d in per.values() if d.get('sheet') is not None and d['iou'] >= LOOSE_IOU])
        med_sh = [int(np.round(np.median(sh[:, 0]))), int(np.round(np.median(sh[:, 1])))] if len(sh) else [0, 0]
        gR = np.roll(np.roll(g, med_sh[0], 0), med_sh[1], 1)
        perR, _, _, _ = match_view(T, Tlab[view], gR, rad)
        # families of the sheet's pieces (the family truth's majority under them, as refcheck does)
        ft = C['fam_truth'][view]
        pieces = {}
        for k in range(1, reg.max() + 1):
            mk = g == k
            v = ft[mk]; v = v[v >= 0]
            fam = C['fam_sets'][np.bincount(v).argmax()][0] if len(v) else None
            ys, xs = np.nonzero(reg == k)
            pieces[k] = dict(id=k, lab=[round(float(x), 1) for x in med[k]], hex=lab_hex(med[k]),
                             area_sheet=int((reg == k).sum()), area_grid=int(mk.sum()), family=fam,
                             centroid_sheet=[int(r0 + ys.mean()), int(c0 + xs.mean())],
                             number=(numbers or {}).get(view, {}).get(str(k)))
        for q, d in per.items():
            if d.get('sheet') is not None and d['iou'] >= LOOSE_IOU:
                pieces[d['sheet']].setdefault('truth', q)
                pieces[d['sheet']].setdefault('truth_iou', d['iou'])
        # (iv) counts
        cnt_truth = {}
        for q in Tlab[view]:
            if (T == Tlab[view].index(q)).any():
                cnt_truth[hk.family_of(q)] = cnt_truth.get(hk.family_of(q), 0) + 1
        cnt_sheet = {}
        for p in pieces.values():
            if p['family'] in SCORED_FAMS and p['area_grid'] >= MIN_GRID_PX:
                cnt_sheet[p['family']] = cnt_sheet.get(p['family'], 0) + 1
        # (iv) lines on the gap-closed partition, with the random floor
        bd = rc.boundaries(full, fc, np.zeros_like(fl))
        Gl = rc.grid_boundary(bd, R, B)
        lf, lf5 = rc.line_f(Gl, B['lines']), rc.line_f(Gl, B['lines'], 5.0)
        fl_, fl5 = [], []
        for sd in range(5):
            vr = rc.voronoi(fc, max(2, reg.max()), sd)
            vb = rc.grid_boundary(rc.boundaries(vr, fc, np.zeros_like(fl)), R, B)
            fl_.append(rc.line_f(vb, B['lines'])['F']); fl5.append(rc.line_f(vb, B['lines'], 5.0)['F'])
        # (ii) pilot
        pl = [q for q in per if is_pilot(view, q)]
        pm = [q for q in pl if per[q]['iou'] >= MATCH_IOU]
        res['views'][view] = dict(
            registration=R, silhouette=sil, pieces=len(pieces),
            count_truth=cnt_truth, count_sheet=cnt_sheet,
            lines=lf, lines_floor_F=round(float(np.mean(fl_)), 3), lines_5px=lf5,
            lines_5px_floor_F=round(float(np.mean(fl5)), 3),
            pilot=dict(locks=len(pl), matched=len(pm), frac=round(len(pm) / max(1, len(pl)), 3),
                       need=int(np.ceil(PILOT_FRAC * len(pl) - 1e-9)), names=pl, matched_names=pm),
            locks=per, locks_gapfilled={q: dict(sheet=d.get('sheet'), iou=d['iou']) for q, d in perF.items()},
            diag=dict(median_shift_px=med_sh, median_shift_L=round(float(np.hypot(*med_sh)) / ppl, 4),
                      pilot_gapfilled=sum(1 for q in pl if perF[q]['iou'] >= MATCH_IOU),
                      pilot_recentred=sum(1 for q in pl if perR[q]['iou'] >= MATCH_IOU),
                      locks_recentred={q: dict(sheet=d.get('sheet'), iou=d['iou']) for q, d in perR.items()}),
            sheet_pieces=pieces)
        sheetinfo[view] = dict(reg=reg, frgb=frgb, r0=r0, c0=c0, R=R, B=B, T=T, g=g, labels=Tlab[view])
        print(view, 'S %.1f sil %.3f pieces %d pilot %d/%d lines F %.3f / floor %.3f; diag: median shift %s, pilot gap-filled %d, re-centred %d' % (
            R['S_px_per_L'], sil['iou'], len(pieces), len(pm), len(pl), lf['F'], np.mean(fl_), med_sh,
            res['views'][view]['diag']['pilot_gapfilled'], res['views'][view]['diag']['pilot_recentred']))
    # (i) scale
    S = [res['views'][v]['registration']['S_px_per_L'] for v in VIEWS]
    spread = (max(S) - min(S)) / min(S)
    crit = dict(i=dict(S=S, spread=round(spread, 4), pass_=bool(spread <= S_TOL)))
    # (ii)
    pv = {v: res['views'][v]['pilot'] for v in VIEWS}
    crit['ii'] = dict(per_view={v: '%d/%d (need %d)' % (p['matched'], p['locks'], p['need']) for v, p in pv.items()},
                      overall='%d/%d' % (sum(p['matched'] for p in pv.values()), sum(p['locks'] for p in pv.values())),
                      pass_=all(p['matched'] >= p['need'] for p in pv.values()))
    names = {}
    for v in VIEWS:
        for q in res['views'][v]['pilot']['names']:
            names.setdefault(q, []).append(v)
    crit['ii']['per_name_all_views'] = {q: all(res['views'][v]['locks'][q]['iou'] >= MATCH_IOU for v in vs)
                                        for q, vs in names.items()}
    # (iii) identity
    crit['iii'] = identity(res, numbers)
    crit['verdict'] = 'PASS' if (crit['i']['pass_'] and crit['ii']['pass_'] and crit['iii']['pass_']) else 'FAIL'
    res['criteria'] = crit
    # (iv) score5's lock IoU without translation, with the floors
    import score5
    hair1 = {v: np.ones(t.shape, bool) for v, t in Tim.items()}
    r5 = hk.score(grids, (Tim, Tlab, meta), hair1, ppl)
    res['score5'] = dict(sheet=score5.fam_table(r5))
    try:
        fl = score5.floors((Tim, Tlab, meta))
        res['score5'].update(shuffled=fl['shuffled'], shuffled_within_family=fl['shuffled_within_family'])
    except Exception as e:      # the floors are informational
        res['score5']['floors_error'] = str(e)
    # pictures
    for v in VIEWS:
        pics(outdir, v, sheetinfo[v], res['views'][v])
    np.savez_compressed(os.path.join(outdir, 'regions.npz'), **grids)
    json.dump(res, open(os.path.join(outdir, 'result.json'), 'w'), indent=1, default=_js)
    json.dump(identity_table(res), open(os.path.join(outdir, 'identity.json'), 'w'), indent=1, default=_js)
    return res


def _js(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    raise TypeError(type(o))


def same_piece(pa, pb):
    de = float(np.sqrt(((np.array(pa['lab']) - np.array(pb['lab'])) ** 2).sum()))
    na, nb = pa.get('number'), pb.get('number')
    # a region may hold two blended numbered pieces ('13+15'): the numbers agree when the sets meet
    num_ok = None if (na is None or nb is None) else bool(set(str(na).split('+')) & set(str(nb).split('+')))
    return (de <= ID_DE and num_ok is not False), round(de, 1), num_ok


def identity(res, numbers):
    import itertools
    names = {}
    for v in VIEWS:
        for q in res['views'][v]['locks']:
            names.setdefault(q, []).append(v)
    multi = {q: vs for q, vs in names.items() if len(vs) > 1}
    rows, out = [], {}
    for thr, key in ((MATCH_IOU, 'at_0.5'), (LOOSE_IOU, 'at_0.3')):
        ev = hold = 0; strict_hold = 0; n_all = 0; pil_ev = pil_hold = 0
        for q, vs in sorted(multi.items()):
            for a, b in itertools.combinations(vs, 2):
                n_all += 1
                la, lb = res['views'][a]['locks'][q], res['views'][b]['locks'][q]
                ma, mb = la['iou'] >= thr, lb['iou'] >= thr
                row = dict(truth=q, a=a, b=b, iou_a=la['iou'], iou_b=lb['iou'], sheet_a=la.get('sheet'),
                           sheet_b=lb.get('sheet'))
                if ma and mb:
                    pa = res['views'][a]['sheet_pieces'][la['sheet']]
                    pb = res['views'][b]['sheet_pieces'][lb['sheet']]
                    ok, de, num_ok = same_piece(pa, pb)
                    row.update(evaluable=True, holds=ok, dE=de, numbers=[pa.get('number'), pb.get('number')],
                               numbers_agree=num_ok, hex=[pa['hex'], pb['hex']])
                    ev += 1; hold += ok; strict_hold += ok
                    if hk.family_of(q) == 'side_locks':
                        pil_ev += 1; pil_hold += ok
                else:
                    row.update(evaluable=False, holds=False)
                if thr == MATCH_IOU:
                    rows.append(row)
        out[key] = dict(evaluable=ev, holding=hold, rate=round(hold / ev, 3) if ev else None,
                        strict='%d/%d' % (strict_hold, n_all), pilot='%d/%d' % (pil_hold, pil_ev))
    p = out['at_0.5']
    out['pass_'] = bool(p['evaluable'] >= ID_MIN_PAIRS and p['rate'] is not None and p['rate'] >= ID_FRAC)
    out['pairs'] = rows
    return out


def identity_table(res):
    """sheet pieces grouped across views by identity (colour within dE, numbers where read), each with its truth
    lock per view (matched at IoU >= 0.3; the IoU and shift given)."""
    items = []
    for v in VIEWS:
        for k, p in res['views'][v]['sheet_pieces'].items():
            items.append((v, k, p))
    # greedy: mutual-nearest same pieces across views
    groups = []
    for v, k, p in items:
        placed = False
        for gr in groups:
            if v in gr['views']:
                continue
            ref = gr['views'][next(iter(gr['views']))]['piece']
            ok, de, _ = same_piece(ref, p)
            if ok:
                gr['views'][v] = dict(piece=p, dE_to_first=de); placed = True; break
        if not placed:
            groups.append(dict(views={v: dict(piece=p, dE_to_first=0.0)}))
    out = []
    for gr in groups:
        e = dict(hex=next(iter(gr['views'].values()))['piece']['hex'], views={})
        for v, x in gr['views'].items():
            p = x['piece']
            lk = res['views'][v]['locks']
            tq = [q for q, d in lk.items() if d.get('sheet') == p['id'] and d['iou'] >= LOOSE_IOU]
            e['views'][v] = dict(region=p['id'], number=p.get('number'), hex=p['hex'], dE_to_first=x['dE_to_first'],
                                 family_majority=p['family'],
                                 truth=[dict(name=q, iou=lk[q]['iou'], shift_px=lk[q].get('shift_px'))
                                        for q in tq])
        out.append(e)
    return dict(note='sheet pieces grouped across views by colour (Lab dE76 <= %g, numbers where read); truth per '
                     'view = the Hungarian match at IoU >= %g after a <= %g L translation' % (ID_DE, LOOSE_IOU,
                                                                                             SHIFT_L),
                groups=out)


def pics(outdir, view, si, vr):
    """VIEW_match.png: the truth's locks (grey, dark outlines; unscored hatched) with the registered sheet pieces
    outlined in their own colour (shifted by their matched lock's best shift), each truth lock labelled with its name,
    the matched piece (region id, number) and the IoU (green >= 0.5, orange >= 0.3, red below). VIEW_regions.png: the
    panel's segmentation with the region ids, for reading the numbers."""
    from PIL import Image, ImageDraw
    from scipy import ndimage
    B, T, g, labels = si['B'], si['T'], si['g'], si['labels']
    ys, xs = np.nonzero(B['hair'] | (T >= 0) | (g > 0))
    r0, r1, c0, c1 = max(0, ys.min() - 25), ys.max() + 25, max(0, xs.min() - 25), xs.max() + 25
    Z = 2
    base = np.ones(T.shape + (3,)) * 0.97
    base[B['hair']] = (0.92, 0.92, 0.92)
    base[T >= 0] = (0.80, 0.80, 0.80)
    hatch = (np.add.outer(np.arange(T.shape[0]), np.arange(T.shape[1])) // 4) % 2 == 0
    base[(T == -2) & hatch] = (0.88, 0.88, 0.88)
    for i in np.unique(T[T >= 0]):
        m = T == i
        base[m & ~ndimage.binary_erosion(m)] = (0.2, 0.2, 0.2)
    shift = {}
    for q, d in vr['locks'].items():
        if d.get('sheet') is not None and d['iou'] >= LOOSE_IOU:
            shift[d['sheet']] = d['shift_px']
    for k, p in vr['sheet_pieces'].items():
        m = g == k
        if not m.any():
            continue
        dy, dx = shift.get(k, (0, 0))
        m = np.roll(np.roll(m, dy, 0), dx, 1)
        e = m & ~ndimage.binary_erosion(m, iterations=2)
        base[e] = tuple(int(p['hex'][j:j + 2], 16) / 255 for j in (1, 3, 5))
    im = Image.fromarray((np.clip(base[r0:r1, c0:c1], 0, 1) * 255).astype(np.uint8))
    im = im.resize((im.size[0] * Z, im.size[1] * Z), Image.NEAREST)
    dr = ImageDraw.Draw(im)
    for q, d in vr['locks'].items():
        i = labels.index(q)
        yy, xx = np.nonzero(T == i)
        if not len(yy):
            continue
        y, x = (yy.mean() - r0) * Z, (xx.mean() - c0) * Z
        pc = vr['sheet_pieces'].get(d.get('sheet')) if d.get('sheet') else None
        num = (pc or {}).get('number')
        col = (0, 140, 0) if d['iou'] >= MATCH_IOU else (220, 120, 0) if d['iou'] >= LOOSE_IOU else (200, 0, 0)
        t1 = dict(bangs='bg', side_locks='sl', lower_back='lb', flyaways='fa', ahoge='ah').get(
            hk.family_of(q), '?') + ':' + q.split('/', 1)[1]
        t2 = '%.2f r%s%s' % (d['iou'], d.get('sheet'), '#%s' % num if num is not None else '')
        for dx_, dy_ in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            dr.text((x - 20 + dx_, y - 10 + dy_), t1, fill=(255, 255, 255))
            dr.text((x - 20 + dx_, y + 2 + dy_), t2, fill=(255, 255, 255))
        dr.text((x - 20, y - 10), t1, fill=col)
        dr.text((x - 20, y + 2), t2, fill=col)
    dr.text((8, 8), '%s  S %.0f px/L  pilot %d/%d' % (view, vr['registration']['S_px_per_L'], vr['pilot']['matched'],
                                                    vr['pilot']['locks']), fill=(0, 0, 0))
    im.save(os.path.join(outdir, '%s_match.png' % view))
    reg, frgb = si['reg'], si['frgb']
    pic = 0.45 * frgb + 0.55
    for k in range(1, reg.max() + 1):
        m = reg == k
        pic[m & ~ndimage.binary_erosion(m, iterations=2)] = (0, 0, 0)
    im2 = Image.fromarray((np.clip(pic, 0, 1) * 255).astype(np.uint8))
    d2 = ImageDraw.Draw(im2)
    for k, p in vr['sheet_pieces'].items():
        y, x = p['centroid_sheet'][0] - si['r0'], p['centroid_sheet'][1] - si['c0']
        d2.text((x + 8, y + 6), 'r%d' % k, fill=(200, 0, 0))
    im2.save(os.path.join(outdir, '%s_regions.png' % view))


if __name__ == '__main__':
    import pickle
    a = sys.argv[1:]
    sheet, outdir = a[0], a[1]
    ctxp = a[a.index('--ctx') + 1] if '--ctx' in a else os.path.join(ROOT, 'charkit/out/hair5truth/ctx5.pkl')
    numbers = json.load(open(a[a.index('--numbers') + 1])) if '--numbers' in a else None
    C = pickle.load(open(ctxp, 'rb'))
    r = run(sheet, outdir, C, numbers)
    c = r['criteria']
    print('(i) S', c['i']['S'], 'spread %.3f' % c['i']['spread'], 'PASS' if c['i']['pass_'] else 'FAIL')
    print('(ii)', c['ii']['per_view'], 'overall', c['ii']['overall'], 'PASS' if c['ii']['pass_'] else 'FAIL')
    print('(iii)', {k: v for k, v in c['iii'].items() if k != 'pairs'}, 'PASS' if c['iii']['pass_'] else 'FAIL')
    print('verdict', c['verdict'])
