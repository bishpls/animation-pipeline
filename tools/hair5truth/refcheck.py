"""Refcheck a colour-coded hair sheet (hair_breakdown, a generated lock close-up) against the body turnaround, per view
and per lock, by numbers:

  silhouette  the sheet's hair registered onto the body sheet's design grid (per view a scale S and an offset, searched
              on the hair and the face's skin as hairlayers.register does; the per-view S's are reported, so a sheet
              that doesn't keep one scale shows it) -> hair IoU (all, and below the buns' zone)
  locks       the sheet's flat-colour regions: hair pixels split by its black lines and by colour steps (a 4-neighbour
              Lab step over STEP_DE); regions of MIN_GRID_PX or more (in design-grid px). Per region its colour spread
              (p90 Lab distance to its median): flat if under FLAT_DE. Reported: the regions, the flat share of the
              hair area, the adjacent regions' colour step (median Lab distance across their boundary), and the regions
              per family (the breakdown: its legend's families; a generic sheet: the family truth's first family under
              the region, after registration)
  lines       the regions' boundaries inside the hair, mapped onto the design grid and skeletonised, against the body
              sheet's drawn lines inside its hair (the raw line class and the faint ridges, outfit.ridges, as the
              structure labeller's walls; 3 px or more inside the hair's outline, skeletonised) -> precision, recall, F within TOL px; the floor: a random Voronoi partition of the
              sheet's hair into as many regions, scored the same (5 seeds); the ceiling check: the body sheet's lines
              moved 1 px against themselves

    python tools/hair5truth/refcheck.py SHEET.png OUT.json [--views front,profile,back] [--breakdown] [--pics DIR]

OUT_regions.npz: the sheet's regions warped onto the design grids (per view), for scoring against the lock truth
(tools/hair5truth/score5.py).
"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)

TOL = 2.5             # grid px: a boundary pixel this close to a drawn line matches it
STEP_DE = 7.0         # Lab: a neighbour step this large parts two flat regions
FLAT_DE = 6.0         # Lab: a region whose p90 distance to its median colour is under this is flat
MIN_GRID_PX = 25      # a region this large on the design grid counts (the truth's TRUTH_MIN)
LINE_V = 0.35         # value: darker is the sheet's black line
INNER = 3             # grid px: the body's lines this far inside its hair outline are lock lines
BUN_ZONE = 0.72       # L above the eye line: hairlayers' buns zone


def load(path):
    from PIL import Image
    return np.asarray(Image.open(path).convert('RGB')).astype(float) / 255


def masks(rgb):
    """-> (hair: coloured pixels, skin: pale grey, line: black)."""
    sat = rgb.max(2) - rgb.min(2); val = rgb.max(2)
    line = val < LINE_V
    skin = (sat < 0.06) & (val > 0.55) & (val < 0.93)
    hair = (sat > 0.12) & ~line
    return hair, skin, line


def figures(hair, n, min_gap=30):
    """the n figures' column ranges: split at the n - 1 widest runs of columns without hair, or, where figures touch,
    at the column with the least hair within a window round the even split."""
    cnt = hair.sum(0)
    cols = np.nonzero(cnt > 3)[0]
    gaps = np.nonzero(np.diff(cols) > min_gap)[0]
    if len(gaps) >= n - 1:
        gaps = sorted(gaps, key=lambda g: cols[g + 1] - cols[g])[-(n - 1):]
        cuts = sorted(int((cols[g] + cols[g + 1]) // 2) for g in gaps)
    else:
        a, b = cols.min(), cols.max()
        w = (b - a) / n
        cuts = []
        for k in range(1, n):
            c = a + k * w
            lo, hi = int(c - 0.3 * w), int(c + 0.3 * w)
            sm = np.convolve(cnt, np.ones(5) / 5, 'same')
            cuts.append(int(lo + np.argmin(sm[lo:hi])))
    b = [0] + cuts + [hair.shape[1]]
    return [(b[i], b[i + 1]) for i in range(n)]


def body_view(C, view):
    """the body sheet's view on its design grid: hair (closed over its lines), face skin above the neck, the drawn lock
    lines (skeleton), the grid's u, z."""
    from scipy import ndimage
    from skimage.morphology import skeletonize
    from charkit.bodyqa import CLASS
    dv, g = C['dv'][view], C['grid'][view]
    hair0 = C['hair'][view]
    raw = dv['raw']
    line = raw == CLASS['line']
    hairc = ndimage.binary_closing(hair0 | (line & ndimage.binary_dilation(hair0, iterations=3)), iterations=2)
    hairc = ndimage.binary_fill_holes(hairc) & (hair0 | line | ndimage.binary_dilation(hair0, iterations=1))
    zz = g['zs'][:, None] * np.ones((1, len(g['us'])))
    skin = (dv['cls'] == CLASS['skin']) & (zz > -0.6) & (zz < 1.25)
    interior = ndimage.binary_erosion(hairc, iterations=INNER)
    from charkit.outfit import ridges
    rgb = np.asarray(dv['rgb'], float)
    rgb = rgb / 255 if rgb.max() > 1.5 else rgb
    lines = skeletonize((line | (ridges(rgb) & hairc)) & interior)
    return dict(hair=hairc, skin=skin, lines=lines, interior=interior, zz=zz)


def register(sh_hair, sh_skin, B, s_range, s_step=0.01):
    """the sheet figure (hair, skin masks) onto the body view's grid: f = grid px per sheet px, (di, dj) the offset.
    Maximises the hair's and the skin's Dice at once (the back: the hair alone). -> dict(f, di, dj, score)."""
    from scipy import ndimage, signal
    best = None
    tH, tS = B['hair'].astype(float), B['skin'].astype(float)
    use_skin = sh_skin.sum() > 500 and tS.sum() > 500
    for f in np.arange(s_range[0], s_range[1], s_step):
        kh = ndimage.zoom(sh_hair.astype(float), f, order=1) > 0.5
        cc = signal.fftconvolve(tH, kh[::-1, ::-1].astype(float)) * 2 / (kh.sum() + tH.sum())
        if use_skin:
            ks = ndimage.zoom(sh_skin.astype(float), f, order=1) > 0.5
            cs = signal.fftconvolve(tS, ks[::-1, ::-1].astype(float)) * 2 / (ks.sum() + tS.sum())
            sh = (max(cc.shape[0], cs.shape[0]), max(cc.shape[1], cs.shape[1]))
            cc = np.pad(cc, ((0, sh[0] - cc.shape[0]), (0, sh[1] - cc.shape[1]))) + \
                0.5 * np.pad(cs, ((0, sh[0] - cs.shape[0]), (0, sh[1] - cs.shape[1])))
        k = np.unravel_index(np.argmax(cc), cc.shape)
        if best is None or cc[k] > best['score']:
            best = dict(f=float(f), di=int(k[0] - (kh.shape[0] - 1)), dj=int(k[1] - (kh.shape[1] - 1)),
                        score=float(cc[k]))
    return best


def to_grid(rows, cols, R, shape):
    """sheet figure pixels (rows, cols within the figure) -> grid (i, j) ints, in range."""
    i = np.round(rows * R['f'] + R['di']).astype(int)
    j = np.round(cols * R['f'] + R['dj']).astype(int)
    ok = (i >= 0) & (i < shape[0]) & (j >= 0) & (j < shape[1])
    return i[ok], j[ok]


def warp_mask(m, R, shape):
    """a sheet figure mask onto the grid (nearest: each grid pixel samples the sheet)."""
    I, J = np.mgrid[0:shape[0], 0:shape[1]]
    r = np.round((I - R['di']) / R['f']).astype(int); c = np.round((J - R['dj']) / R['f']).astype(int)
    ok = (r >= 0) & (r < m.shape[0]) & (c >= 0) & (c < m.shape[1])
    out = np.zeros(shape, m.dtype)
    out[ok] = m[r[ok], c[ok]]
    return out


def regions(rgb, hair, line, min_px):
    """the flat-colour regions of a figure's hair: walls are the black lines and the colour steps."""
    from scipy import ndimage
    from charkit.outfit import lab
    L = lab(rgb)
    step = np.zeros(hair.shape, bool)
    for ax in (0, 1):
        d = np.sqrt((np.diff(L, axis=ax) ** 2).sum(-1)) > STEP_DE
        if ax == 0:
            step[1:] |= d; step[:-1] |= d
        else:
            step[:, 1:] |= d; step[:, :-1] |= d
    inner = hair & ~line & ~step
    lab_, n = ndimage.label(inner)
    area = np.bincount(lab_.ravel(), minlength=n + 1)
    keep = np.nonzero(area >= min_px)[0]
    keep = keep[keep > 0]
    lut = np.zeros(n + 1, np.int32)
    lut[keep] = np.arange(1, len(keep) + 1)
    return lut[lab_], L


def region_stats(reg, L):
    from scipy import ndimage
    out = []
    for r in range(1, reg.max() + 1):
        m = reg == r
        c = np.median(L[m], 0)
        d = np.sqrt(((L[m] - c) ** 2).sum(-1))
        out.append(dict(id=r, area=int(m.sum()), lab=[round(float(x), 1) for x in c],
                        spread=round(float(np.percentile(d, 90)), 2)))
    return out


def adjacent_steps(reg, L, gap=4):
    """median Lab distance between each pair of regions closer than `gap` px (across a line or a step)."""
    from scipy import ndimage
    idx = ndimage.distance_transform_edt(reg == 0, return_distances=False, return_indices=True)
    full = reg[idx[0], idx[1]]
    d = ndimage.distance_transform_edt(reg == 0)
    full[d > gap] = 0
    pairs = {}
    a, b = full[:, :-1], full[:, 1:]
    m = (a > 0) & (b > 0) & (a != b)
    for x, y in zip(a[m], b[m]):
        pairs[(min(x, y), max(x, y))] = pairs.get((min(x, y), max(x, y)), 0) + 1
    a, b = full[:-1], full[1:]
    m = (a > 0) & (b > 0) & (a != b)
    for x, y in zip(a[m], b[m]):
        pairs[(min(x, y), max(x, y))] = pairs.get((min(x, y), max(x, y)), 0) + 1
    med = {}
    for r in {q for p in pairs for q in p}:
        med[r] = np.median(L[reg == r], 0)
    return {p: float(np.sqrt(((med[p[0]] - med[p[1]]) ** 2).sum())) for p, n in pairs.items() if n >= 3}


def boundaries(reg, hair, line, gap=3):
    """the boundaries between regions inside the hair: the hair's walls (lines, steps) given to the nearest region within
    `gap` px; a pixel whose 3x3 holds two regions is a boundary, unless it is by the hair's outside."""
    from scipy import ndimage
    d, idx = ndimage.distance_transform_edt(reg == 0, return_indices=True)
    full = np.where((d <= gap) & (hair | line), reg[idx[0], idx[1]], 0)
    full = np.where(reg > 0, reg, full)
    mx = ndimage.maximum_filter(full, 3)
    mn = ndimage.minimum_filter(np.where(full > 0, full, 10 ** 6), 3)
    b = (full > 0) & (mx != mn) & (mn < 10 ** 6)
    outside = ~ndimage.binary_dilation(hair | line, iterations=1)
    near_out = ndimage.binary_dilation(outside, iterations=gap + 1)
    return b & ~near_out


def line_f(pred, truth, tol=TOL):
    from scipy import ndimage
    if not pred.any() or not truth.any():
        return dict(P=0.0, R=0.0, F=0.0, n_pred=int(pred.sum()), n_truth=int(truth.sum()))
    dt = ndimage.distance_transform_edt(~truth)
    dp = ndimage.distance_transform_edt(~pred)
    P = float((dt[pred] <= tol).mean()); Rc = float((dp[truth] <= tol).mean())
    F = 2 * P * Rc / max(1e-9, P + Rc)
    return dict(P=round(P, 3), R=round(Rc, 3), F=round(F, 3), n_pred=int(pred.sum()), n_truth=int(truth.sum()))


def grid_boundary(b, R, B):
    from scipy import ndimage
    from skimage.morphology import skeletonize
    rr, cc = np.nonzero(b)
    i, j = to_grid(rr, cc, R, B['hair'].shape)
    g = np.zeros(B['hair'].shape, bool)
    g[i, j] = True
    g = ndimage.binary_closing(g, iterations=1)
    return skeletonize(g) & B['interior']


def voronoi(hair, k, seed):
    from scipy import ndimage
    rng = np.random.RandomState(seed)
    ys, xs = np.nonzero(hair)
    j = rng.choice(len(ys), k, replace=False)
    mk = np.zeros(hair.shape, np.int32)
    mk[ys[j], xs[j]] = np.arange(1, k + 1)
    _, idx = ndimage.distance_transform_edt(mk == 0, return_indices=True)
    return np.where(hair, mk[idx[0], idx[1]], 0)


def check(sheet, views, C, breakdown=False, pics=None, s_range=None):
    from charkit import hairlayers as hl
    rgb = load(sheet)
    hair, skin, line = masks(rgb)
    fam = None
    if breakdown:
        sw, famk, top = hl.legend(rgb)
        f_ = hl.segment(rgb, sw, famk, top - 40)
        fam = np.zeros(hair.shape, np.uint8)
        fam[:f_.shape[0]] = f_
        skin[top - 40:] = False; line[top - 40:] = False
        hair = fam > 0
    figs = figures(hair, len(views))
    out = dict(sheet=os.path.relpath(sheet, ROOT), views={}, tol_px=TOL, step_de=STEP_DE, flat_de=FLAT_DE)
    ppl = C['ppl']
    grids = {}
    for view, (c0, c1) in zip(views, figs):
        B = body_view(C, view)
        fh, fs, fl = hair[:, c0:c1], skin[:, c0:c1], line[:, c0:c1]
        # the figure's own rows: crop to the hair's rows (+ margin)
        rows = np.nonzero(fh.any(1))[0]
        r0, r1 = max(0, rows.min() - 40), min(fh.shape[0], rows.max() + 200)
        fh, fs, fl = fh[r0:r1], fs[r0:r1], fl[r0:r1]
        frgb = rgb[r0:r1, c0:c1]
        # the sheet's hair height against the body's: the scale's search range
        bh = np.nonzero(B['hair'].any(1))[0]
        f0 = (bh.max() - bh.min()) / max(1, rows.max() - rows.min())
        rng = s_range or (0.8 * f0, 1.2 * f0)
        R = register(fh, fs, B, rng, s_step=(rng[1] - rng[0]) / 40)
        R.update(c0=int(c0), r0=int(r0), S_px_per_L=round(ppl / R['f'], 1))
        from scipy import ndimage
        H = warp_mask(fh | (fl & ndimage.binary_dilation(fh, iterations=3)), R, B['hair'].shape)
        H = ndimage.binary_fill_holes(ndimage.binary_closing(H, iterations=2)) & ndimage.binary_dilation(
            warp_mask(fh, R, B['hair'].shape), iterations=2)
        iou = lambda a, b: float((a & b).sum() / max(1, (a | b).sum()))
        low = B['zz'] < BUN_ZONE
        sil = dict(iou=round(iou(H, B['hair']), 3), iou_below_buns=round(iou(H & low, B['hair'] & low), 3))
        # flat-colour regions
        min_px = int(round(MIN_GRID_PX / R['f'] ** 2))
        reg, L = regions(frgb, fh, fl, min_px)
        st = region_stats(reg, L)
        flat_area = sum(s['area'] for s in st if s['spread'] < FLAT_DE)
        tot_area = int(fh.sum())
        steps = adjacent_steps(reg, L)
        # families per region
        fams = {}
        if fam is not None:
            ff = fam[r0:r1, c0:c1]
            for s in st:
                v = ff[reg == s['id']]
                v = v[v > 0]
                s['family'] = hl.FAMILIES[np.bincount(v).argmax() - 1] if len(v) else None
        else:
            ft = C['fam_truth'][view]
            for s in st:
                rr, cc = np.nonzero(reg == s['id'])
                i, j = to_grid(rr, cc, R, ft.shape)
                v = ft[i, j]
                v = v[v >= 0]
                s['family'] = C['fam_sets'][np.bincount(v).argmax()][0] if len(v) else None
        for s in st:
            fams[s['family']] = fams.get(s['family'], 0) + 1
        same = [d for (a, b), d in steps.items() if st[a - 1]['family'] == st[b - 1]['family']]
        # lines
        bd = boundaries(reg, fh, fl)
        G = grid_boundary(bd, R, B)
        lf = line_f(G, B['lines'])
        lf5 = line_f(G, B['lines'], 5.0)
        floor, floor5 = [], []
        for sd in range(5):
            vr = voronoi(fh, max(2, len(st)), sd)
            vb = grid_boundary(boundaries(vr, fh, np.zeros_like(fl)), R, B)
            floor.append(line_f(vb, B['lines'])['F'])
            floor5.append(line_f(vb, B['lines'], 5.0)['F'])
        self_ = line_f(np.roll(B['lines'], 1, axis=1), B['lines'])['F']
        out['views'][view] = dict(
            registration=R, silhouette=sil, regions=len(st), regions_per_family=fams,
            flat_share=round(flat_area / max(1, tot_area), 3), region_area_share=round(sum(s['area'] for s in st) /
                                                                                     max(1, tot_area), 3),
            spread_median=round(float(np.median([s['spread'] for s in st])), 2) if st else None,
            adjacent_step_median=round(float(np.median(list(steps.values()))), 1) if steps else None,
            adjacent_step_same_family_median=round(float(np.median(same)), 1) if same else None,
            adjacent_same_family_under_10=round(float(np.mean(np.array(same) < 10)), 3) if same else None,
            lines=lf, lines_floor_F=round(float(np.mean(floor)), 3), lines_floor_F_seeds=floor, lines_self_1px_F=self_,
            lines_5px=lf5, lines_5px_floor_F=round(float(np.mean(floor5)), 3))
        print(view, json.dumps({k: v for k, v in out['views'][view].items() if k not in ('lines_floor_F_seeds',)}))
        if pics:
            save_pics(pics, view, C, B, G, H, frgb, reg, R)
        grids[view] = warp_mask(reg, R, B['hair'].shape).astype(np.int32)
    out['_grids'] = grids
    return out


def save_pics(pics, view, C, B, G, H, frgb, reg, R):
    from PIL import Image
    os.makedirs(pics, exist_ok=True)
    rgb = np.asarray(C['dv'][view]['rgb'], float)
    rgb = rgb / 255 if rgb.max() > 1.5 else rgb
    ys, xs = np.nonzero(B['hair'])
    r0, r1, c0, c1 = ys.min() - 10, ys.max() + 10, xs.min() - 10, xs.max() + 10
    pic = 0.5 * rgb + 0.5
    pic[B['lines']] = (0, 0, 0)
    from scipy import ndimage
    pic[G] = (1, 0, 0)
    pic[G & ndimage.binary_dilation(B['lines'], iterations=2)] = (0, 0.7, 0)
    edge = H & ~ndimage.binary_erosion(H)
    pic[edge] = (0, 0.4, 1)
    im = Image.fromarray((np.clip(pic[r0:r1, c0:c1], 0, 1) * 255).astype(np.uint8))
    im = im.resize((im.size[0] * 2, im.size[1] * 2), Image.NEAREST)
    im.save(os.path.join(pics, '%s_lines.png' % view))
    rng = np.random.RandomState(1)
    col = rng.uniform(0.2, 1, (reg.max() + 1, 3)); col[0] = 1
    Image.fromarray((col[reg] * 255).astype(np.uint8)).save(os.path.join(pics, '%s_regions.png' % view))


if __name__ == '__main__':
    import ctx5
    a = sys.argv[1:]
    sheet, out = a[0], a[1]
    views = a[a.index('--views') + 1].split(',') if '--views' in a else ['front', 'profile', 'back']
    pics = a[a.index('--pics') + 1] if '--pics' in a else None
    C = ctx5.make()
    r = check(sheet, views, C, breakdown='--breakdown' in a, pics=pics)
    grids = r.pop('_grids')
    np.savez_compressed(out.replace('.json', '_regions.npz'), **grids)     # the sheet's regions on the design grids
    json.dump(r, open(out, 'w'), indent=1)
    print('wrote', out)
