"""The lock map reference's refcheck (tool/hairident; the pass rule declared in docs/workstreams/hairident.md before the
calls): a redraw of the head turnaround with every lock a closed shape (`lines`: one flat orange cut by ink lines;
`colours`: each lock its own flat colour), registered per view on the body turnaround's design grids (the hair's
silhouette: scale and shift searched round the sheets' px-per-L ratio), its locks read as regions and measured:

  silhouette   hair IoU against the turnaround's hair (closed, holes filled), the views' scales within 5%
  structure    the back view's hair below the buns: closed regions >= 0.01 L^2, how many reach >= 0.3 L up from the
               hem; the profile's back mass (its upper and lower back families): such regions
  agreement    each of the back's hem-flick truth regions inside one region (>= 70%), how many distinct; the
               turnaround's drawn lock lines (the splitter's ink) within 2.5 px of a region boundary (recall)

    python tools/hairident/lockmap.py TAKE.png OUT [--kind lines|colours] [--ctx PKL] [--inputs PKL] [--swap A:B]
        (--swap: the known-bad, two views mislaid; the turnaround itself as TAKE: no structure it lacks)
        OUT/lockmap.json, OUT/VIEW.png (the turnaround | the take registered | its regions), OUT/regions.npz (each
        view's regions on the design grid: 0 none)
"""
import json, os, pickle, sys
import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from charkit import shapetruth as st, hairlocks as hk, bodyqa, sheetqa

VIEWS = ('front', 'three_quarter', 'profile', 'back')
GROW = 6               # px: a body-sheet take's hair is looked for this far round the turnaround's
FLAT = 0.12            # summed channels: neighbours this close in colour lie in one flat field
MIN_REGION = 0.002     # L^2: a region smaller than this (on the take) is antialiasing or a stray stroke
TOL = dict(hair_iou=0.80, scale_spread=0.05, back_regions=6, back_reaching=5, reach_L=0.3, region_L2=0.01,
           profile_back_regions=4, flick_inside=0.70, flicks_distinct=5, line_recall=0.50, line_px=2.5)


def _opt(a, k, d):
    return a[a.index(k) + 1] if k in a else d


def take_regions(rgb, src, view, kind):
    """the take's hair in one view's figure and its lock regions -> (hair bool, label int32 0 none)."""
    blob = src['blobs'][view]
    fam = bodyqa.family(rgb)
    dark = (rgb.max(-1) < 0.35)
    if kind == 'lines':
        part = src['part'] & blob
        hair = part | (dark & ndimage.binary_dilation(part, iterations=3) & blob)
        inner = part & ~dark
    else:
        skin = fam == bodyqa.CLASS['skin']
        bg = ~src['fg']
        cand = blob & ~skin & ~bg
        lab, n = ndimage.label(cand)
        sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
        keep = np.isin(lab, 1 + np.nonzero(sizes >= 0.02 * src['ppl'] ** 2)[0])
        hair = keep
        inner = keep & ~dark
    ppl = src['ppl']
    if kind == 'lines':
        lab, n = ndimage.label(inner)
    else:
        # flat colour fields: a pixel whose 4 neighbours all lie within FLAT of its colour (the take median-filtered
        # first: the antialiasing) is a field's interior; the fields are its connected parts (k-means on the colours,
        # the first reading, split the gradients the model painted into fragments: 55-61 regions a view)
        sm = np.stack([ndimage.median_filter(rgb[..., k], 3) for k in range(3)], -1)
        dif = np.zeros(inner.shape)
        for ax in (0, 1):
            for sh in (1, -1):
                dif = np.maximum(dif, np.abs(sm - np.roll(sm, sh, ax)).sum(-1))
        lab, n = ndimage.label(inner & (dif < FLAT))
    sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
    small = 1 + np.nonzero(sizes < MIN_REGION * ppl ** 2)[0]
    lab[np.isin(lab, small)] = 0
    if kind != 'lines':
        # the lines between the fields, the antialiasing and the small fields: the hair's unlabelled pixels go to the
        # nearest field
        if (lab > 0).any():
            _, (iy, ix) = ndimage.distance_transform_edt(lab == 0, return_indices=True)
            g = hair & (lab == 0)
            lab[g] = lab[iy[g], ix[g]]
    # relabel 1..k
    u = np.unique(lab[lab > 0])
    m = np.zeros(lab.max() + 1, np.int32)
    m[u] = np.arange(1, len(u) + 1)
    return hair, m[lab]


def body_take(take_rgb, I, spec_path='charkit/spec/clawd.json'):
    """a take that edits the body turnaround in place (the same canvas): each view's design grid cut from it as the
    splitter's inputs cut the sheet (hull.views_from_sheet on the sheet, hairlayers.design_grid), its flat colour
    fields inside the turnaround's hair (grown GROW px), skin and background out -> {view: (rgb grid, hair, lab)}."""
    from charkit import manifest, hairlayers as hl
    from charkit.geom import hull
    spec = manifest.resolve(json.load(open(os.path.join(ROOT, spec_path))))
    R = manifest.load(spec['ref']['manifest'])['references']
    rgb_b = hl.load_rgb(R['body_turnaround']['path'])
    views, info = hull.views_from_sheet(rgb_b, (spec.get('eyes') or {}).get('x', 0.168), -1)
    out = {}
    for v in VIEWS:
        V = views[v]
        us, zs, shape, x0y0 = hl.design_grid(V, V.ppl)
        g = np.stack([V.sample(take_rgb[..., k], us, zs).T for k in range(3)], -1)
        d = I['views'][v]
        dst = d['hair'] | np.any([m for m in (d.get('pieces') or {}).values()] or [np.zeros_like(d['hair'])], 0)
        zone = ndimage.binary_dilation(dst, iterations=GROW)
        fam = bodyqa.family(g)
        dark = g.max(-1) < 0.35
        grey = (g.max(-1) - g.min(-1)) < 0.06                          # the background and neutral greys
        cand = zone & (fam != bodyqa.CLASS['skin']) & ~grey
        sm = np.stack([ndimage.median_filter(g[..., k], 3) for k in range(3)], -1)
        dif = np.zeros(shape)
        for ax in (0, 1):
            for sh in (1, -1):
                dif = np.maximum(dif, np.abs(sm - np.roll(sm, sh, ax)).sum(-1))
        lab, n = ndimage.label(cand & ~dark & (dif < FLAT))
        sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
        lab[np.isin(lab, 1 + np.nonzero(sizes < MIN_REGION * I['ppl'] ** 2)[0])] = 0
        hair = ndimage.binary_closing(lab > 0, iterations=2) & zone
        if (lab > 0).any():
            _, (iy, ix) = ndimage.distance_transform_edt(lab == 0, return_indices=True)
            gg = hair & (lab == 0)
            lab[gg] = lab[iy[gg], ix[gg]]
        u = np.unique(lab[lab > 0])
        mp_ = np.zeros(lab.max() + 1, np.int32)
        mp_[u] = np.arange(1, len(u) + 1)
        out[v] = (g, hair, mp_[lab])
    return out


def _sil(m, ppl):
    return ndimage.binary_fill_holes(ndimage.binary_closing(m, iterations=max(1, int(round(0.01 * ppl)))))


def register(src_hair, src_eye, src_ppl, dst_hair, dst_ppl, log=None):
    """the take's hair on the design grid: dst p = (src p - src_eye) * s + e (searched: s within 6% of the px-per-L
    ratio, e by the hair's centre then a shift search) -> (s, e (x, y), IoU)."""
    s0 = dst_ppl / src_ppl
    ys, xs = np.nonzero(src_hair)
    yd, xd = np.nonzero(dst_hair)
    S = _sil(src_hair, src_ppl).astype(float)
    D = _sil(dst_hair, dst_ppl)
    H, W = D.shape
    k = 3                                          # px: the coarse search's step

    def iou_at(s, e, step):
        rr, cc = np.mgrid[0:H:step, 0:W:step].astype(float)
        sr = (rr - e[1]) / s + src_eye[1]
        sc = (cc - e[0]) / s + src_eye[0]
        Sv = ndimage.map_coordinates(S, [sr, sc], order=1, mode='constant') > 0.5
        Dv = D[::step, ::step]
        u = (Sv | Dv).sum()
        return float((Sv & Dv).sum() / u) if u else 0.0
    best = None
    for ds in np.arange(-0.06, 0.0601, 0.02):
        s = s0 * (1 + ds)
        # the centres matched at this scale
        e0 = (xd.mean() - (xs.mean() - src_eye[0]) * s, yd.mean() - (ys.mean() - src_eye[1]) * s)
        for dy in range(-30, 31, 6):
            for dx in range(-30, 31, 6):
                v = iou_at(s, (e0[0] + dx, e0[1] + dy), k)
                if best is None or v > best[0]:
                    best = (v, s, (e0[0] + dx, e0[1] + dy))
    v, s, e = best
    for ds in (-0.01, -0.005, 0.0, 0.005, 0.01):
        for dy in range(-6, 7, 2):
            for dx in range(-6, 7, 2):
                s2, e2 = s * (1 + ds), (e[0] + dx, e[1] + dy)
                v2 = iou_at(s2, e2, 2)
                if v2 > best[0] or (best[1] == s and best[2] == e):
                    best = (v2, s2, e2)
    v, s, e = best
    return s, e, iou_at(s, e, 1)


def to_grid(img, src_eye, s, e, shape, order=0):
    H, W = shape
    rr, cc = np.mgrid[0:H, 0:W].astype(float)
    sr = (rr - e[1]) / s + src_eye[1]
    sc = (cc - e[0]) / s + src_eye[0]
    return ndimage.map_coordinates(np.asarray(img, float), [sr, sc], order=order, mode='constant')


def boundary(lab, hair):
    """the regions' boundaries inside the hair (a pixel whose 3x3 neighbourhood holds another region or a gap)."""
    mx = ndimage.maximum_filter(lab, 3)
    mn = ndimage.minimum_filter(np.where(lab > 0, lab, 10 ** 6), 3)
    return hair & ((mx != lab) | (mn != lab) | (lab == 0))


def measure(view, lab, hair_grid, I, masks, T, TL, split):
    """the pass rule's structure and agreement on one view (lab: the take's regions on the design grid)."""
    ppl = I['ppl']
    d = I['views'][view]
    out = {}
    A = ppl ** 2 * TOL['region_L2']
    ids = [k for k in np.unique(lab[lab > 0])]
    big = [k for k in ids if (lab == k).sum() >= A]
    out['regions'] = len(ids)
    out['regions_big'] = len(big)
    if view == 'back':
        bun = np.zeros(lab.shape, bool)
        for m in (d.get('pieces') or {}).values():
            bun |= m
        r_b = np.nonzero(bun.any(1))[0].max() if bun.any() else 0
        hem = np.nonzero(hair_grid.any(1))[0].max()
        below = [k for k in big if np.nonzero((lab == k).any(1))[0].max() > r_b]
        reach = []
        for k in below:
            rows = np.nonzero((lab == k).any(1))[0]
            if rows.max() >= hem - 0.25 * ppl and rows.max() - max(rows.min(), r_b) >= TOL['reach_L'] * ppl:
                reach.append(k)
        out['below_buns'] = len(below)
        out['reaching'] = len(reach)
        # the hem flicks of the lock truth
        t = T[view]
        fl = [i for i, l in enumerate(TL[view]) if l.startswith('lower_back/flick')]
        inside, best = [], []
        for i in fl:
            m = t == i
            if not m.any():
                continue
            v, c = np.unique(lab[m], return_counts=True)
            c = np.where(v > 0, c, 0)
            j = int(np.argmax(c))
            inside.append(round(float(c[j]) / m.sum(), 3))
            best.append(int(v[j]))
        out['flicks_inside'] = inside
        out['flicks_ok'] = sum(1 for x in inside if x >= TOL['flick_inside'])
        out['flicks_distinct'] = len(set(b for b, x in zip(best, inside) if x >= TOL['flick_inside']))
    if view == 'profile':
        fm = np.zeros(lab.shape, bool)
        for f in ('lower_back', 'upper_back'):
            m = masks.get('profile__' + f)
            if m is not None:
                fm |= m
        pb = [k for k in big if ((lab == k) & fm).sum() >= A]
        out['back_mass_regions'] = len(pb)
    # the drawn lock lines recalled
    ink = (split[view + '__walls'] & 1).astype(bool) & d['hair']
    bd = boundary(lab, hair_grid)
    near = ndimage.distance_transform_edt(~bd) <= TOL['line_px']
    out['line_recall'] = round(float((ink & near).sum() / max(1, ink.sum())), 3)
    out['line_floor'] = round(float(near[d['hair']].mean()), 3)      # a random line's chance to be near a boundary
    return out


def verdict(rec):
    ok = rec['hair_iou'] >= TOL['hair_iou'] and rec['line_recall'] >= TOL['line_recall']
    if rec['view'] == 'back':
        ok = ok and rec['below_buns'] >= TOL['back_regions'] and rec['reaching'] >= TOL['back_reaching'] and \
            rec['flicks_ok'] >= 6 and rec['flicks_distinct'] >= TOL['flicks_distinct']
    if rec['view'] == 'profile':
        ok = ok and rec['back_mass_regions'] >= TOL['profile_back_regions']
    return ok


def main(a):
    take, out = a[0], a[1]
    kind = _opt(a, '--kind', 'colours' if 'colour' in os.path.basename(take) else 'lines')
    os.makedirs(out, exist_ok=True)
    I = pickle.load(open(_opt(a, '--inputs', os.path.join(ROOT, 'charkit/out/hairsplit/inputs.pkl')), 'rb'))
    C = pickle.load(open(_opt(a, '--ctx', os.path.join(ROOT, 'charkit/out/hairident/ctx_r2.pkl')), 'rb'))
    T, TL, _ = hk.load_truth(os.path.join(ROOT, 'charkit/refs/clawd/hair_locks_truth.npz'))
    split = np.load(os.path.join(ROOT, 'charkit/out/clawd/hair/split/hairsplit.npz'))
    rgb = np.asarray(Image.open(take).convert('RGB'), float) / 255
    if _opt(a, '--sheet', 'head') == 'body':
        return main_body(a, take, out, rgb, I, C, T, TL, split)
    src = st.source(rgb, 0.168, -1)
    sw = _opt(a, '--swap', None)
    if sw:
        # the known-bad: two views mislaid (each read as the other)
        x_, y_ = sw.split(':')
        for k_ in ('views', 'blobs'):
            src[k_][x_], src[k_][y_] = src[k_][y_], src[k_][x_]
    recs, regs = {}, {}
    for v in VIEWS:
        if v not in src['views']:
            recs[v] = dict(view=v, error='no head found')
            continue
        hair_s, lab_s = take_regions(rgb, src, v, kind)
        d = I['views'][v]
        dst = d['hair'] | np.any([m for m in (d.get('pieces') or {}).values()] or [np.zeros_like(d['hair'])], 0)
        s, e, iou = register(hair_s, src['views'][v], src['ppl'], dst, I['ppl'])
        lab = to_grid(lab_s, src['views'][v], s, e, dst.shape).astype(np.int32)
        hg = to_grid(hair_s.astype(float), src['views'][v], s, e, dst.shape, order=1) > 0.5
        lab[~hg] = 0
        rec = dict(view=v, scale=round(float(s), 5), scale_vs_ppl=round(float(s / (I['ppl'] / src['ppl'])), 4),
                   eye=[round(e[0], 1), round(e[1], 1)], hair_iou=round(iou, 3))
        rec.update(measure(v, lab, hg, I, C['masks'], T, TL, split))
        rec['pass'] = verdict(rec)
        recs[v], regs[v] = rec, lab
        # the picture: the turnaround | the take registered | its regions
        ys, xs = np.nonzero(dst | hg)
        r0, r1, c0, c1 = max(0, ys.min() - 20), ys.max() + 20, max(0, xs.min() - 20), xs.max() + 20
        A_ = (np.clip(d['rgb'], 0, 1) * 255).astype(np.uint8)[r0:r1, c0:c1]
        Bv = np.stack([to_grid(rgb[..., k], src['views'][v], s, e, dst.shape, order=1) for k in range(3)], -1)
        B_ = (np.clip(Bv, 0, 1) * 255).astype(np.uint8)[r0:r1, c0:c1]
        rng = np.random.RandomState(5)
        pal = rng.randint(40, 235, (lab.max() + 1, 3)).astype(np.uint8)
        Cc = np.where((lab > 0)[..., None], pal[lab], (0.5 * np.clip(d['rgb'], 0, 1) * 255 + 120).astype(np.uint8))
        Cc[boundary(lab, hg) & (lab > 0)] = 0
        Cc[(split[v + '__walls'] & 1).astype(bool) & d['hair']] = (255, 255, 255)
        Cc = Cc[r0:r1, c0:c1]
        Image.fromarray(np.concatenate([A_, B_, Cc], 1)).save(os.path.join(out, '%s.png' % v))
    sc = [r['scale_vs_ppl'] for r in recs.values() if 'scale_vs_ppl' in r]
    res = dict(take=os.path.relpath(take, ROOT), kind=kind, tol=TOL, views=recs,
               scale_spread=round(float(max(sc) - min(sc)), 4) if sc else None)
    res['scale_ok'] = bool(sc) and res['scale_spread'] <= TOL['scale_spread']
    json.dump(res, open(os.path.join(out, 'lockmap.json'), 'w'), indent=1)
    np.savez_compressed(os.path.join(out, 'regions.npz'), **regs)
    for v, r in recs.items():
        print(v, json.dumps({k: x for k, x in r.items() if k != 'view'}))
    print('scale spread', res['scale_spread'])
    return 0


def main_body(a, take, out, rgb, I, C, T, TL, split):
    """the refcheck of a take drawn on the body turnaround's canvas (no registration: its grids are the sheet's)."""
    B = body_take(rgb, I)
    recs, regs = {}, {}
    for v, (g, hg, lab) in B.items():
        d = I['views'][v]
        dst = d['hair'] | np.any([m for m in (d.get('pieces') or {}).values()] or [np.zeros_like(d['hair'])], 0)
        Sh, Dh = _sil(hg, I['ppl']), _sil(dst, I['ppl'])
        iou = float((Sh & Dh).sum() / max(1, (Sh | Dh).sum()))
        rec = dict(view=v, scale_vs_ppl=1.0, hair_iou=round(iou, 3))
        rec.update(measure(v, lab, hg, I, C['masks'], T, TL, split))
        rec['pass'] = verdict(rec)
        recs[v], regs[v] = rec, lab
        ys, xs = np.nonzero(dst | hg)
        r0, r1, c0, c1 = max(0, ys.min() - 20), ys.max() + 20, max(0, xs.min() - 20), xs.max() + 20
        A_ = (np.clip(d['rgb'], 0, 1) * 255).astype(np.uint8)[r0:r1, c0:c1]
        B_ = (np.clip(g, 0, 1) * 255).astype(np.uint8)[r0:r1, c0:c1]
        rng = np.random.RandomState(5)
        pal = rng.randint(40, 235, (lab.max() + 1, 3)).astype(np.uint8)
        Cc = np.where((lab > 0)[..., None], pal[lab], (0.5 * np.clip(d['rgb'], 0, 1) * 255 + 120).astype(np.uint8))
        Cc[boundary(lab, hg) & (lab > 0)] = 0
        Cc[(split[v + '__walls'] & 1).astype(bool) & d['hair']] = (255, 255, 255)
        Image.fromarray(np.concatenate([A_, B_, Cc[r0:r1, c0:c1]], 1)).save(os.path.join(out, '%s.png' % v))
    res = dict(take=os.path.relpath(take, ROOT), kind='colours', sheet='body', tol=TOL, views=recs, scale_spread=0.0,
               scale_ok=True)
    json.dump(res, open(os.path.join(out, 'lockmap.json'), 'w'), indent=1)
    np.savez_compressed(os.path.join(out, 'regions.npz'), **regs)
    for v, r in recs.items():
        print(v, json.dumps({k: x for k, x in r.items() if k != 'view'}))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
