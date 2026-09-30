"""The hair's layers: the generated breakdown (the manifest's `hair_breakdown`: the hair as colour-coded families in front,
profile and back, with a legend) turned into per-view family masks on the body sheet's hair, so the hair's pieces have
targets the way the outfit's pieces do (charkit.outfit's `outfit_masks`).

  legend     the legend's swatches: saturated runs in its band, grouped into families by the gaps between its boxes
  segment    each drawing pixel's family: its nearest swatch in Lab within MAX_DE, saturated enough (not the grey
             skin, the white paper or the lines); the lower back's pink above the eye line is the fringe's lightest
             tone (the two families share it there)
  register   the breakdown's three views onto the body sheet's calibrated views (charkit.geom.hull.views_from_sheet): one
             scale and one eye row for all three (the breakdown is a turnaround), each view's axis column its own; fitted
             by the hair's overlap (the buns' zone left out: the two drawings place the buns differently) and the face's
             skin, by FFT correlation over a scale sweep
  masks      per view (front, profile, back) the body sheet's hair pixels on bodyqa.design_views grids, each taking the
             family of the nearest breakdown family pixel at the registered position; the buns are the outfit's bun
             pieces (outfit_masks' bun_L / bun_R), not the breakdown's. The three-quarter has no breakdown view: a 3D
             labelling predicts it (charkit.geom.hairpieces).
  bun sides  per view, the three-quarter too, each bun apart (VIEW__bun_L, VIEW__bun_R): the bun fit's targets.

The body sheet stays the authority for the hair's silhouettes; the breakdown decides only which family a hair pixel
belongs to. Its registration overlap (hair about 0.67-0.79, face 0.57-0.69 on Clawd) is reported: two generations of
one design, not one drawing.

    python -m charkit hairlayers SPEC [--out DIR] [--no-struct]
                                                      -> DIR/hair_layers.npz (VIEW__FAMILY), hair_layers.json, index.html
                                                         (the drawing's structure by default, STRUCT; --no-struct:
                                                          the plain transfer, STRUCT_OFF; needs --out)
"""
import json, os, sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAMILIES = ('bangs', 'side_locks', 'upper_back', 'lower_back', 'buns', 'ahoge', 'flyaways')
BUNS = FAMILIES.index('buns') + 1
MAX_DE = 22.0                  # Lab: a pixel this close to a swatch takes its family
MIN_SAT = 0.12                 # max - min channel: below it the grey skin, the paper, the lines
BUN_ZONE = 0.72                # L above the eye line: the buns' zone, left out of the registration's hair
NECK = -0.6                    # L: the face's skin is compared above it
BUN_RIM = 3                    # px: the outfit's bun masks grown into the hair by this much
VIEWS = ('front', 'profile', 'back')
# the drawing's own structure over the transferred families (docs/workstreams/hairtag.md): the sheet's hair split into
# lock regions by its drawn lines, its faint ridges and its two cel tones (Otsu on the hair's value), each tone's runs cut
# at their necks (a watershed of the distance to those walls, markers the h-maxima); a region whose transferred families
# agree to `vote` takes that family whole, else keeps them per pixel. Clips drawn in the hair colour (the outfit's
# pieces other than the buns) are not hair, except within the buns' rim (clip_rim: the rim is bun, as without the clip
# rule; hairtag round 2: the field's outfit masks call 52 px of the profile's left bun pin_star, which the hair truth
# and the sheet-only outfit masks call bun, and the bun fit moved to another optimum without them).
STRUCT_ON = dict(vote=0.6, h=1.5, clips=True, tone=True, bun_vote=False, clip_rim=True)
# the produced hair layers' default: on (Michael, 2026-09-30: 0.892 -> 0.958 against the truth). STRUCT_OFF is the plain
# transfer (the breakdown's nearest family per pixel, clips kept as hair): `hairlayers SPEC --no-struct --out DIR` makes
# it (off the manifest's path), for the 2x2's old measure and comparisons.
STRUCT_OFF = dict(STRUCT_ON, vote=0, clips=False)
STRUCT = dict(STRUCT_ON)


def _p(path):
    return path if os.path.isabs(path) else os.path.join(ROOT, path)


def load_rgb(path):
    from PIL import Image
    return np.asarray(Image.open(_p(path)).convert('RGB')).astype(float) / 255


def legend(rgb, sat_min=0.15, gap=40):
    """the legend's swatches -> (colours (n, 3), family index (n,), legend top row). The legend is the lowest band of
    saturated rows; a run of saturated columns is a swatch, runs further apart than `gap` px belong to different boxes."""
    sat = rgb.max(2) - rgb.min(2)
    rows = np.nonzero((sat > sat_min).sum(1) > 50)[0]
    # the lowest block of consecutive saturated rows
    blocks = np.split(rows, np.nonzero(np.diff(rows) > 5)[0] + 1)
    band = blocks[-1]
    seg = rgb[band[0]:band[-1] + 1]
    s = seg.max(2) - seg.min(2)
    cols = np.nonzero((s > sat_min).any(0))[0]
    runs = np.split(cols, np.nonzero(np.diff(cols) > 3)[0] + 1)
    sw = np.array([np.median(seg[:, r[0]:r[-1] + 1][s[:, r[0]:r[-1] + 1] > sat_min], 0) for r in runs])
    fam = np.cumsum([0] + [runs[i + 1][0] - runs[i][-1] > gap for i in range(len(runs) - 1)])
    if fam[-1] + 1 != len(FAMILIES):
        raise ValueError('the legend has %d boxes, %d families expected' % (fam[-1] + 1, len(FAMILIES)))
    return sw, fam, int(band[0])


def segment(rgb, sw, fam, rows):
    """the drawing's pixels above row `rows` -> family image (0 none, k + 1 family k)."""
    from .outfit import lab
    top = rgb[:rows]
    sat = top.max(2) - top.min(2)
    L = lab(top.reshape(-1, 3))
    S = lab(sw)
    best = np.full(len(L), np.inf); j = np.zeros(len(L), int)
    for k in range(len(S)):                                  # (a loop keeps the memory to one distance column)
        d = np.sqrt(((L - S[k]) ** 2).sum(1))
        m = d < best
        best[m] = d[m]; j[m] = k
    out = np.where((best < MAX_DE) & (sat.reshape(-1) > MIN_SAT), fam[j] + 1, 0)
    return out.reshape(top.shape[:2]).astype(np.uint8)


def figures(fam_img, min_gap=30):
    """the three figures' column ranges, split at the widest runs of columns without any family pixel."""
    cols = np.nonzero((fam_img > 0).any(0))[0]
    gaps = np.nonzero(np.diff(cols) > min_gap)[0]
    if len(gaps) < 2:
        raise ValueError('the breakdown shows %d figures, 3 expected' % (len(gaps) + 1))
    gaps = sorted(gaps, key=lambda g: cols[g + 1] - cols[g])[-2:]
    cuts = sorted(int((cols[g] + cols[g + 1]) // 2) for g in gaps)
    b = [0] + cuts + [fam_img.shape[1]]
    return {v: (b[i], b[i + 1]) for i, v in enumerate(VIEWS)}


def skin(rgb):
    """the breakdown's grey skin: unsaturated, neither paper nor line."""
    sat = rgb.max(2) - rgb.min(2); val = rgb.max(2)
    return (sat < 0.06) & (val > 0.55) & (val < 0.93)


def register(fam_img, rgb, views, figs, s_range=(430, 640), s_step=3):
    """the breakdown's views onto the body sheet's (hull.View): breakdown column = C0 + S u, row = R0 - S z (u, z in L,
    the view's own). One S and R0 for all three, C0 per view. -> {view: dict(S, C0, R0, iou_hair, iou_face)}."""
    from scipy import ndimage, signal
    ppl = next(iter(views.values())).ppl
    us = np.arange(-1.3, 1.3, 1 / ppl); zs = np.arange(1.25, -0.75, -1 / ppl)
    zz = zs[:, None] * np.ones((1, len(us)))
    sk = skin(rgb[:fam_img.shape[0]])
    hair_k = (fam_img > 0) & (fam_img != BUNS)
    tgt = {}
    for name in figs:
        Lb = views[name].sample(views[name].labels, us, zs).T
        Lb = np.where(views[name].sample(views[name].mask.astype(np.uint8), us, zs).T > 0, Lb, 0)   # its own figure
        tgt[name] = ((Lb == 2) & (zz < BUN_ZONE), (Lb == 1) & (zz > NECK))

    def corr(k, t):
        return signal.fftconvolve(k.astype(float), t[::-1, ::-1].astype(float)) / max(1, k.sum() + t.sum())
    best = None
    for S in np.arange(s_range[0], s_range[1], s_step):
        f = ppl / S
        maps = {}
        for name, (c0, c1) in figs.items():
            Hb, Sb = tgt[name]
            kh = ndimage.zoom(hair_k[:, c0:c1].astype(float), f, order=1) > 0.5
            cc = corr(kh, Hb)
            if name != 'back':
                ks = ndimage.zoom(sk[:, c0:c1].astype(float), f, order=1) > 0.5
                cs = corr(ks, Sb)
                sh = (max(cc.shape[0], cs.shape[0]), max(cc.shape[1], cs.shape[1]))
                cc = np.pad(cc, ((0, sh[0] - cc.shape[0]), (0, sh[1] - cc.shape[1]))) + \
                    np.pad(cs, ((0, sh[0] - cs.shape[0]), (0, sh[1] - cs.shape[1])))
            maps[name] = cc
        nr = min(m.shape[0] for m in maps.values())
        rowbest = sum(m[:nr].max(1) for m in maps.values())
        ri = int(np.argmax(rowbest))
        if best is None or rowbest[ri] > best[0]:
            best = (rowbest[ri], S, ri, {n: int(np.argmax(m[ri])) for n, m in maps.items()})
    _, S, ri, cis = best
    out = {}
    for name, (c0, c1) in figs.items():
        Hb = tgt[name][0]
        dr, dc = ri - (Hb.shape[0] - 1), cis[name] - (Hb.shape[1] - 1)
        r = dict(S=float(S), C0=float(c0 + (dc - us[0] * ppl) * S / ppl), R0=float((dr + zs[0] * ppl) * S / ppl))
        rows = np.arange(fam_img.shape[0]); cols = np.arange(c0, c1)
        u = (cols - r['C0']) / S; z = (r['R0'] - rows) / S
        L2 = views[name].sample(views[name].labels, u, z).T
        Z2 = z[:, None] * np.ones((1, len(cols)))
        iou = lambda a, b: float((a & b).sum() / max(1, (a | b).sum()))
        r['iou_hair'] = round(iou(hair_k[:, c0:c1] & (Z2 < BUN_ZONE), (L2 == 2) & (Z2 < BUN_ZONE)), 4)
        r['iou_face'] = round(iou(sk[:, c0:c1] & (Z2 > NECK), (L2 == 1) & (Z2 > NECK)), 4) if name != 'back' else None
        out[name] = r
    return out


def fringe_rule(fam_img, reg, figs):
    """the lower back's pink above the eye line is the fringe's lightest tone: relabelled bangs, in place."""
    lb, bangs = FAMILIES.index('lower_back') + 1, FAMILIES.index('bangs') + 1
    for name, (c0, c1) in figs.items():
        if name == 'back':
            continue
        R0 = reg[name]['R0']
        sub = fam_img[:int(R0), c0:c1]
        sub[sub == lb] = bangs
    return fam_img


def design_grid(view, ppl):
    """a body-sheet view's bodyqa.design_views grid as (u (W,), z (H,)) in the view's L, and its shape."""
    from .bodyqa import WIN
    H = int(round((WIN['top'] - WIN['bottom']) * ppl)); W = int(round(2 * WIN['x'] * ppl))
    x0 = int(round(view.grid_eye[0] - WIN['x'] * ppl)); y0 = int(round(view.grid_eye[1] - WIN['top'] * ppl))
    cols = x0 + np.arange(W); rows = y0 + np.arange(H)
    return (cols - view.axis) / ppl, (view.eye_y - rows) / ppl, (H, W), (x0, y0)


def lock_regions(v, us, zs, hair, h=STRUCT_ON['h'], tone=True):
    """the sheet's hair on a design grid split into lock regions by its drawing: walls are the drawn lines (the raw
    class) and faint ridges (outfit.ridges); the hair's two cel tones apart (Otsu on its value); each tone's runs cut at
    their necks (watershed of the distance to the walls, markers its h-maxima). -> region image (0 none)."""
    from scipy import ndimage
    from skimage import filters, morphology, segmentation
    from .bodyqa import CLASS
    from .outfit import ridges
    rgb = np.swapaxes(v.sample(v.rgb, us, zs), 0, 1).astype(float)
    if rgb.max() > 1.5:
        rgb = rgb / 255
    raw = v.sample(v.raw, us, zs).T
    inner = hair & (raw != CLASS['line']) & ~ridges(rgb)
    val = rgb.max(-1)
    if inner.sum() < 100:
        return np.zeros(hair.shape, np.int32)
    dark = (val < filters.threshold_otsu(val[inner])) if tone else np.zeros(hair.shape, bool)
    out = np.zeros(hair.shape, np.int32)
    for m in (inner & dark, inner & ~dark):
        d = ndimage.distance_transform_edt(m)
        mk, _ = ndimage.label(morphology.h_maxima(d, h) & m)
        ws = segmentation.watershed(-d, mk, mask=m)
        out[ws > 0] = ws[ws > 0] + out.max()
    return out


def vote_regions(fam, regions, hair, vote=STRUCT_ON['vote']):
    """each lock region whose transferred families agree to `vote` takes that family whole; the walls inside the
    hair (lines, ridges) take their nearest region pixel's family. -> family image."""
    from scipy import ndimage
    out = fam.copy()
    r = regions.ravel(); f = fam.ravel()
    ok = (r > 0) & (f > 0)
    n, k = int(regions.max()) + 1, len(FAMILIES) + 1
    cnt = np.bincount(r[ok] * k + f[ok], minlength=n * k).reshape(n, k)
    tot = cnt.sum(1)
    top = cnt.argmax(1)
    win = np.where((tot > 0) & (cnt.max(1) >= vote * np.maximum(tot, 1)), top, 0)
    wv = win[regions]
    out = np.where((regions > 0) & (wv > 0), wv, out)
    wall = hair & (regions == 0)
    if wall.any() and (regions > 0).any():
        idx = ndimage.distance_transform_edt(regions == 0, return_distances=False, return_indices=True)
        out[wall] = out[idx[0][wall], idx[1][wall]]
    return np.where(hair, out, 0)


def transfer(fam_img, reg, figs, views, outfit_masks=None, struct=None):
    """per view, the body sheet's hair pixels on its design grid, each with the family of the nearest breakdown family
    pixel (the buns left out) at its registered position; the outfit's bun pieces are the buns.
    -> {VIEW__FAMILY: bool image}, {view: hair pixels, per-family counts}."""
    from scipy import ndimage
    out, rep = {}, {}
    for name in VIEWS:
        v, r = views[name], reg[name]
        us, zs, shape, _ = design_grid(v, v.ppl)
        # rows z, cols u, on the design grid; the view's own figure only (the grid is wide enough to take in a
        # neighbouring figure's hair)
        hair = (v.sample(v.labels, us, zs).T == 2) & (v.sample(v.mask.astype(np.uint8), us, zs).T > 0)
        c0, c1 = figs[name]
        sub = fam_img[:, c0:c1].copy()
        sub[sub == BUNS] = 0
        # nearest family pixel of the breakdown, indexed at every breakdown pixel of the figure
        idx = ndimage.distance_transform_edt(sub == 0, return_distances=False, return_indices=True)
        cols = np.clip(np.round(r['C0'] + r['S'] * us).astype(int) - c0, 0, sub.shape[1] - 1)
        rows = np.clip(np.round(r['R0'] - r['S'] * zs).astype(int), 0, sub.shape[0] - 1)
        RR, CC = np.meshgrid(rows, cols, indexing='ij')
        fam = sub[idx[0][RR, CC], idx[1][RR, CC]]
        st = dict(STRUCT, **(struct or {}))
        buns = np.zeros(shape, bool)
        if outfit_masks is not None:
            for b in ('bun_L', 'bun_R'):
                k = '%s__%s' % (name, b)
                if k in outfit_masks and outfit_masks[k].shape == shape:
                    buns |= outfit_masks[k]
        if st.get('clips') and outfit_masks is not None:    # clips drawn in the hair colour: not hair
            # (the buns' rim stays hair: it is bun below, as it was before the clip rule)
            keep = ndimage.binary_dilation(buns, iterations=BUN_RIM) if st.get('clip_rim') and buns.any() else None
            for k, m in outfit_masks.items():
                if k.startswith(name + '__') and k.split('__', 1)[1] not in ('bun_L', 'bun_R') and m.shape == shape:
                    hair &= ~(m & ~keep) if keep is not None else ~m
        fam = np.where(hair, fam, 0)
        if st.get('vote'):
            if st.get('bun_vote'):                           # the buns vote too: a region mostly bun is bun whole
                fam[buns & hair] = BUNS
            fam = vote_regions(fam, lock_regions(v, us, zs, hair, st['h'], st.get('tone', True)), hair, st['vote'])
            if st.get('bun_vote'):
                buns = fam == BUNS
        # the bun pieces' masks stop a pixel or two inside the drawn hair's outline: their rim is bun too
        buns = ndimage.binary_dilation(buns, iterations=BUN_RIM) & hair if buns.any() else buns
        fam[buns] = BUNS
        fam[(fam == BUNS) & ~buns] = 0
        counts = {}
        for k, f in enumerate(FAMILIES):
            m = fam == k + 1
            if m.any():
                out['%s__%s' % (name, f)] = m
                counts[f] = int(m.sum())
        rep[name] = dict(hair_px=int(hair.sum()), families=counts)
    out.update(bun_sides(views, outfit_masks, out))
    return out, rep


def bun_sides(views, outfit_masks, fams):
    """each bun apart, in every view the sheet draws (front, three-quarter, profile, back): VIEW__bun_L / VIEW__bun_R,
    the outfit's bun pieces rimmed into the view's hair as the buns are (BUN_RIM), each rim pixel to the nearer piece;
    where the view has a buns family (front, profile, back) the two sides partition it exactly. The bun fit's targets
    (charkit.geom.hairpieces.bun_targets): the sides without splitting at the head's axis, and the three-quarter, which
    has no breakdown view (hair round 4). No VIEW__buns is added for the three-quarter: the QA's hair_bun_outline keeps
    its views. -> {VIEW__bun_S: bool image}."""
    from scipy import ndimage
    out = {}
    if outfit_masks is None:
        return out
    for name in ('front', 'three_quarter', 'profile', 'back'):
        if name not in views:
            continue
        v = views[name]
        us, zs, shape, _ = design_grid(v, v.ppl)
        side = {b: outfit_masks.get('%s__%s' % (name, b)) for b in ('bun_L', 'bun_R')}
        side = {b: m for b, m in side.items() if m is not None and m.shape == shape and m.any()}
        if not side:
            continue
        buns = fams.get('%s__buns' % name)
        if buns is None:
            hair = (v.sample(v.labels, us, zs).T == 2) & (v.sample(v.mask.astype(np.uint8), us, zs).T > 0)
            anyb = np.zeros(shape, bool)
            for m in side.values():
                anyb |= m
            buns = ndimage.binary_dilation(anyb, iterations=BUN_RIM) & hair
        # each pixel to the nearer piece's own pixels
        d = {b: ndimage.distance_transform_edt(~m) for b, m in side.items()}
        for b in side:
            other = [d[o] for o in d if o != b]
            out['%s__%s' % (name, b)] = buns & ((d[b] <= other[0]) if other else True)
    return out


def produce(spec, out, page=True, log=print, struct=None):
    """the breakdown's families on the body sheet's hair -> out/hair_layers.npz (VIEW__FAMILY on design grids) and
    hair_layers.json (the registration and the counts). struct: transfer's (STRUCT_ON: the drawing's structure)."""
    from . import manifest
    from .geom import hull
    M = manifest.load(spec['ref']['manifest'])
    R = M['references']
    rgb_k = load_rgb(R['hair_breakdown']['path'])
    sw, fam, top = legend(rgb_k)
    lab = segment(rgb_k, sw, fam, top - 40)
    figs = figures(lab)
    rgb_b = load_rgb(R['body_turnaround']['path'])
    eye_x = (spec.get('eyes') or {}).get('x', 0.168)
    views, info = hull.views_from_sheet(rgb_b, eye_x, -1)
    reg = register(lab, rgb_k, views, figs)
    lab = fringe_rule(lab, reg, figs)
    om = None
    p = manifest.produced(spec, 'outfit_masks', log)     # declared by the manifest: made, or this stops (no silent
    if p:                                                # layers without them); none declared: the buns stay the
        Z = np.load(p)                                   # breakdown's nearest
        om = {k: Z[k] for k in Z.files}
    masks, counts = transfer(lab, reg, figs, views, om, struct)
    os.makedirs(out, exist_ok=True)
    np.savez_compressed(os.path.join(out, 'hair_layers.npz'), **masks)
    rep = dict(families=list(FAMILIES), registration=reg, figures=figs, counts=counts, ppl=info['ppl'],
               swatches={f: [[round(float(c), 4) for c in sw[i]] for i in np.nonzero(fam == k)[0]]
                         for k, f in enumerate(FAMILIES)})
    json.dump(rep, open(os.path.join(out, 'hair_layers.json'), 'w'), indent=1)
    np.save(os.path.join(out, 'breakdown_families.npy'), lab)
    log('hair layers: registration %s' % json.dumps({k: {q: v[q] for q in ('S', 'iou_hair', 'iou_face')}
                                                      for k, v in reg.items()}))
    if page:
        _page(rep, lab, rgb_k, masks, views, out)
    return rep


PAL = np.array([[1, 1, 1], [.85, .2, .2], [1, .8, .2], [.55, .3, .9], [1, .5, .7], [.2, .4, 1], [.1, .8, .7],
                [.5, .9, .1]])


def _page(rep, lab, rgb_k, masks, views, out):
    from PIL import Image
    img = os.path.join(out, 'img'); os.makedirs(img, exist_ok=True)
    seg = np.where(lab[..., None] > 0, PAL[lab], 0.5 * rgb_k[:lab.shape[0]] + 0.5)
    Image.fromarray((seg * 255).astype(np.uint8)).resize((lab.shape[1] // 2, lab.shape[0] // 2)).save(
        os.path.join(img, 'breakdown.png'))
    tiles = []
    for name in VIEWS:
        v = views[name]
        us, zs, shape, (x0, y0) = design_grid(v, v.ppl)
        rgb = v.rgb[np.clip(y0 + np.arange(shape[0]), 0, v.rgb.shape[0] - 1)][:, np.clip(x0 + np.arange(shape[1]), 0,
                                                                                            v.rgb.shape[1] - 1)]
        pic = 0.55 * rgb + 0.45
        for k, f in enumerate(FAMILIES):
            m = masks.get('%s__%s' % (name, f))
            if m is not None:
                pic[m] = 0.35 * rgb[m] + 0.65 * PAL[k + 1]
        rr = np.nonzero(pic.min(2) < 0.99)[0]
        crop = pic[:int(1.8 * v.ppl + (1.3 * v.ppl))]
        Image.fromarray((np.clip(crop, 0, 1) * 255).astype(np.uint8)).save(os.path.join(img, 'sheet_%s.png' % name))
        tiles.append(name)
    rows = ''.join('<tr><td>%s</td><td>%.0f</td><td>%.3f</td><td>%s</td><td>%s</td></tr>' % (
        n, r['S'], r['iou_hair'], '' if r['iou_face'] is None else '%.3f' % r['iou_face'],
        ', '.join('%s %d' % kv for kv in rep['counts'][n]['families'].items())) for n, r in rep['registration'].items())
    legend_ = ' '.join('<span style="background:rgb(%d,%d,%d);padding:1px 6px">%s</span>' % (
        *(PAL[k + 1] * 255).astype(int), f) for k, f in enumerate(FAMILIES))
    html = ['<!doctype html><meta charset="utf-8"><title>hair layers</title><style>body{font:14px/1.45 -apple-system,'
            'system-ui,sans-serif;margin:24px;background:#fafafa;color:#222}table{border-collapse:collapse;font-size:13px}'
            'td,th{border:1px solid #ddd;padding:3px 8px}img{border:1px solid #ddd;background:#fff}.row{display:flex;'
            'gap:12px;flex-wrap:wrap;align-items:flex-end}.note{color:#666;font-size:12px}</style>',
            '<h1>Hair layers: the breakdown\'s families on the body sheet\'s hair</h1><p>%s</p>' % legend_,
            '<p class="note">The breakdown segmented by its legend (nearest swatch in Lab), registered onto the body '
            'sheet\'s calibrated views (one scale and eye row for all three; the buns\' zone left out, the face\'s skin '
            'in), then each body-sheet hair pixel takes the nearest breakdown family; the buns are the outfit\'s bun '
            'pieces. The overlaps say how alike the two generations are, not how good the transfer is.</p>',
            '<table><tr><th>view</th><th>px/L</th><th>hair IoU</th><th>face IoU</th><th>family pixels on the sheet</th>'
            '</tr>%s</table>' % rows,
            '<h2>The breakdown, segmented</h2><img src="img/breakdown.png" width="1100">',
            '<h2>On the body sheet</h2><div class="row">%s</div>' % ''.join(
                '<div><img src="img/sheet_%s.png" height="420"><br>%s</div>' % (t, t) for t in tiles)]
    open(os.path.join(out, 'index.html'), 'w').write('\n'.join(html))


# ------------------------------------------------------------------------------------------------------------ the truth
# A hand-checked labelling of the body sheet's hair by family (docs/workstreams/hairtag.md), the way the outfit's truth
# labels its pieces. Its source is a JSON of cuts and seeds (refs/<name>/hair_truth.json): the sheet's hair cells
# (outfit.cells: 4-connected runs of the hair class, drawn lines and faint ridges as walls) are cut further along the
# annotator's polylines (snapped to the drawn lines between their waypoints: the cheapest path over the picture's value,
# so a cut follows a partial stroke and crosses its gap straight), and every piece of 12 px or more takes the family set
# of the seed inside it. Lines, cut paths and slivers are unscored.
TRUTH_LABELS = FAMILIES + ('bun_L', 'bun_R', 'none')    # bun_L / bun_R: the buns by side (a family score reads buns)
TRUTH_MIN = 25                 # px: cells this large are labelled (as the outfit's truth)
TRUTH_SLIVER = 12              # px: a cut piece smaller than this is unscored
SNAP_BAND = 6                  # px: a snapped cut stays this close to its waypoints' box


def design(spec):
    """the body sheet's design views (bodyqa.design_views: the grids the masks are on) -> ({view: dv}, ppl)."""
    from . import bodyqa, manifest, sheetqa
    R = manifest.load(spec['ref']['manifest'])['references']
    rgb = load_rgb(R['body_turnaround']['path'])
    eye_x = (spec.get('eyes') or {}).get('x', 0.168)
    D = sheetqa.detect_figures(rgb, None, eye_x, -1)
    ppl = float(D['ppl'])
    return bodyqa.design_views(rgb, D, ppl), ppl


def _cut_path(val, pts, snap=True):
    """a cut through (x, y) waypoints -> (rows, cols): straight, or snapped (the cheapest path over the value between
    consecutive waypoints, within SNAP_BAND of their box: drawn lines are dark, so it runs along them)."""
    from skimage import draw, graph
    rr, cc = [], []
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
        x0, y0, x1, y1 = int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1))
        if not snap:
            r, c = draw.line(y0, x0, y1, x1)
        else:
            b = SNAP_BAND
            ra, rb = max(0, min(y0, y1) - b), min(val.shape[0], max(y0, y1) + b + 1)
            ca, cb = max(0, min(x0, x1) - b), min(val.shape[1], max(x0, x1) + b + 1)
            cost = 0.05 + val[ra:rb, ca:cb] ** 3
            path, _ = graph.route_through_array(cost, (y0 - ra, x0 - ca), (y1 - ra, x1 - ca), fully_connected=True,
                                                geometric=True)
            path = np.array(path)
            r, c = path[:, 0] + ra, path[:, 1] + ca
        rr.append(r); cc.append(c)
    return np.concatenate(rr), np.concatenate(cc)


def truth_regions(dv, src):
    """one view's truth from its source (dict(cuts=[{p: [[x, y], ...], snap}], seeds=[[x, y, 'a|b'], ...])) ->
    (region label image (0 unscored), [(region id, label set, area)], cut mask, problems [str])."""
    from scipy import ndimage
    from .outfit import cells
    from .bodyqa import CLASS
    lbl, cl = cells(dv['raw'], dv['fg'], dv['rgb'])
    hair = np.zeros(lbl.shape, bool)
    for c in cl:
        if c['cls'] == CLASS['hair'] and c['area'] >= TRUTH_MIN:
            hair |= lbl == c['id']
    val = np.asarray(dv['rgb']).max(-1)
    cut = np.zeros(lbl.shape, bool)
    for k in src.get('cuts', []):
        k = k if isinstance(k, dict) else dict(p=k)
        r, c = _cut_path(val, k['p'], k.get('snap', True))
        cut[r, c] = True
    # a cell's pieces: 4-connected runs of one cell's pixels off the cuts (a cut never joins two cells)
    base = np.where(hair & ~cut, lbl, 0)
    # tone zones: the under layer is drawn in the shadow tone; within a zone (rows r0..r1, cols c0..c1) the hair darker
    # than v (cleaned: opened and closed a pixel) is split from the lighter, and its pieces take the zone's label
    # unless a seed says otherwise
    dark = np.zeros(lbl.shape, bool)
    tone_label = np.zeros(lbl.shape, np.int32)
    zone_id = np.zeros(lbl.shape, np.int32)
    for i, z in enumerate(src.get('tones', [])):
        r0, r1, c0, c1 = z['zone']
        zm = np.zeros(lbl.shape, bool); zm[r0:r1, c0:c1] = True
        zone_id[zm] = i + 1
        dk = ndimage.binary_closing(ndimage.binary_opening((val < z.get('v', 0.75)) & zm & (base > 0)),
                                    iterations=1) & (base > 0) & zm
        dark |= dk
        tone_label[dk] = i + 1
    base = np.where(dark, base + lbl.max() + 1, base)
    reg = np.zeros(lbl.shape, np.int32)
    n = 0
    for cid in np.unique(base[base > 0]):
        l, m = ndimage.label(base == cid)
        reg[l > 0] = l[l > 0] + n
        n += m
    area = np.bincount(reg.ravel(), minlength=n + 1)
    sets, problems = {}, []
    for x, y, s in src.get('seeds', []):
        x, y = int(round(x)), int(round(y))
        rid = reg[y, x]
        if rid == 0:                                          # on a line or a cut: the nearest region within 3 px
            ys, xs = np.nonzero(reg[max(0, y - 3):y + 4, max(0, x - 3):x + 4])
            if len(ys):
                i = np.argmin((ys + max(0, y - 3) - y) ** 2 + (xs + max(0, x - 3) - x) ** 2)
                rid = reg[ys[i] + max(0, y - 3), xs[i] + max(0, x - 3)]
        st = tuple(s.split('|'))
        bad = [q for q in st if q not in TRUTH_LABELS]
        if bad:
            problems.append('seed (%d, %d): unknown label %s' % (x, y, bad))
        if rid == 0:
            problems.append('seed (%d, %d) %s: on no region' % (x, y, s))
        elif rid in sets and sets[rid] != st:
            problems.append('seed (%d, %d) %s: region %d already %s (a cut does not close)' % (x, y, s, rid,
                                                                                               '|'.join(sets[rid])))
        else:
            sets[rid] = st
    out = []
    for rid in range(1, n + 1):
        if area[rid] < TRUTH_SLIVER:
            reg[reg == rid] = 0
            continue
        if rid not in sets:
            m = reg == rid
            tl = np.bincount(tone_label[m]).argmax()
            zl = np.unique(zone_id[m])
            if tl:
                sets[rid] = tuple(src['tones'][tl - 1]['dark'].split('|'))
            elif len(zl) == 1 and zl[0] and src['tones'][zl[0] - 1].get('light'):     # a light piece inside a zone
                sets[rid] = tuple(src['tones'][zl[0] - 1]['light'].split('|'))
        if rid not in sets:
            ys, xs = np.nonzero(reg == rid)
            problems.append('region %d (%d px) at (%d, %d): no seed' % (rid, area[rid], int(xs.mean()), int(ys.mean())))
            continue
        out.append((rid, sets[rid], int(area[rid])))
    return reg, out, cut, problems


def build_truth(spec, src_path, out_path, log=print):
    """the hair truth's source (JSON) -> its npz (charkit-hair-truth/1: per view an index image into `sets`, -1
    unscored; the grids the masks are on). Stops on any problem (a region without a seed, a cut that doesn't close)."""
    src = json.load(open(_p(src_path)))
    dv, ppl = design(spec)
    sets, imgs, problems, n_reg = [], {}, [], 0
    for view, vs in src['views'].items():
        reg, regions, _, pr = truth_regions(dv[view], vs)
        problems += ['%s: %s' % (view, q) for q in pr]
        img = np.full(reg.shape, -1, np.int16)
        for rid, st, _ in regions:
            if list(st) not in sets:
                sets.append(list(st))
            img[reg == rid] = sets.index(list(st))
        imgs[view] = img
        n_reg += len(regions)
        log('%s: %d regions, %d px labelled' % (view, len(regions), int((img >= 0).sum())))
    if problems:
        raise ValueError('the hair truth has %d problems:\n  %s' % (len(problems), '\n  '.join(problems)))
    meta = dict(format='charkit-hair-truth/1', name=spec.get('name'), sheet='body_turnaround', ppl=ppl,
                grids={v: list(i.shape) for v, i in imgs.items()}, source=src_path, regions=n_reg,
                labels=list(TRUTH_LABELS), provenance=src.get('provenance'), rules=src.get('rules'),
                calls=src.get('calls'))
    np.savez_compressed(_p(out_path), sets=json.dumps(sets), meta=json.dumps(meta), **imgs)
    return meta


def load_truth(path):
    """the hair truth (charkit-hair-truth/1) -> (images {view}, sets [[label]], meta)."""
    Z = np.load(_p(path))
    meta = json.loads(str(Z['meta']))
    if meta.get('format') != 'charkit-hair-truth/1':
        raise ValueError('%s: not a charkit-hair-truth/1 file' % path)
    return {v: Z[v] for v in meta['grids'] if v in Z.files}, json.loads(str(Z['sets'])), meta


def _fam(label):
    return 'buns' if label in ('bun_L', 'bun_R') else label


def score(masks, truth):
    """hair layer masks ({VIEW__FAMILY} and {VIEW__bun_L/_R}) against the truth (load_truth's).
    families: per view and in all the hair accuracy (of the scored pixels where the truth or the masks put a family,
    the share whose family the truth accepts) and the wrong pixels; per family the IoU with the truth resolved per pixel
    (the masks' family where the truth accepts it, else the truth's first); the largest confusions.
    sides: per view and side the IoU of VIEW__bun_S with the truth's bun_S (resolved the same way, 'buns' in a set
    without a side counting for neither). A view the masks don't cover is left out (the three-quarter has bun sides
    only). -> dict."""
    T, sets, _ = truth
    fsets = [sorted({_fam(q) for q in s}, key=lambda q: [_fam(x) for x in s].index(q)) for s in sets]
    out, acc_f, conf, sides = {}, {}, [], {}
    for v, t in T.items():
        ks = [k for k in masks if k.startswith(v + '__') and k.split('__', 1)[1] in FAMILIES]
        if ks and masks[ks[0]].shape != t.shape:
            raise ValueError('%s: masks on a %s grid, the truth on %s' % (v, masks[ks[0]].shape, t.shape))
        scored = t >= 0
        if ks:
            names = [k.split('__', 1)[1] for k in ks] + ['none']
            L = np.full(t.shape, len(names) - 1, np.int32)
            for i, k in enumerate(ks):
                L[masks[k]] = i
            got = np.array(names, object)[L]
            ok = np.zeros(t.shape, bool)
            resolved = np.full(t.shape, 'none', object)
            for i, st in enumerate(fsets):
                m = t == i
                if not m.any():
                    continue
                inset = m & np.isin(got, st)
                ok |= inset
                resolved[inset] = got[inset]
                resolved[m & ~inset] = st[0]
                bad = m & ~inset
                if bad.any():
                    vals, cnt = np.unique(got[bad], return_counts=True)
                    conf += [(v, '|'.join(st), str(a), int(b)) for a, b in zip(vals, cnt)]
            hairpx = scored & ((resolved != 'none') | (got != 'none'))
            iou = {}
            for f in FAMILIES:
                a, b = scored & (got == f), scored & (resolved == f)
                u = int((a | b).sum())
                if u:
                    iou[f] = round(float((a & b).sum() / u), 3)
                    acc_f.setdefault(f, [0, 0])
                    acc_f[f][0] += int((a & b).sum()); acc_f[f][1] += u
            out[v] = dict(accuracy=round(float(ok[hairpx].mean()), 4), wrong=int((hairpx & ~ok).sum()),
                          hair=int(hairpx.sum()), iou=iou)
        sm = {q: masks.get('%s__%s' % (v, q)) for q in ('bun_L', 'bun_R')}
        if any(m is not None for m in sm.values()):
            # each pixel's side: the masks' where the truth accepts it, else the truth's first side (none: no side)
            gs = np.full(t.shape, '', object)
            for q, m in sm.items():
                if m is not None:
                    gs[m & (gs == '')] = q
            rs = np.full(t.shape, '', object)
            for i, st in enumerate(sets):
                m = t == i
                sd = [q for q in st if q in ('bun_L', 'bun_R')]
                if not m.any() or not sd:
                    continue
                ok_ = m & np.isin(gs, sd)
                rs[ok_] = gs[ok_]
                rs[m & ~ok_] = sd[0] if st[0] in ('bun_L', 'bun_R') else ''
            for q, m in sm.items():
                if m is None:
                    continue
                a, b = scored & (gs == q), scored & (rs == q)
                u = int((a | b).sum())
                sides.setdefault(v, {})[q] = round(float((a & b).sum() / u), 3) if u else None
    if acc_f:
        wrong, hp = sum(r['wrong'] for r in out.values()), sum(r['hair'] for r in out.values())
        fiou = {f: round(a / b, 3) for f, (a, b) in acc_f.items()}
        out['all'] = dict(accuracy=round(1 - wrong / max(1, hp), 4), wrong=wrong, hair=hp,
                          mean_iou=round(float(np.mean(list(fiou.values()))), 3), iou=fiou,
                          confusions=[dict(view=a, truth=b, got=c, px=d)
                                      for a, b, c, d in sorted(conf, key=lambda x: -x[3])[:15]])
    out['sides'] = sides
    return out


def score_main(args):
    """python -m charkit hairlayers score [SPEC] [--masks HAIR_LAYERS.npz] [--json OUT]: the produced hair layers (or
    the given ones) against the manifest's hair_truth: per view and family, the confusions, the bun sides."""
    from . import manifest
    spec_path = next((a for a in args if a.endswith('.json') and 'spec' in a), 'charkit/spec/clawd.json')
    spec = manifest.resolve(json.load(open(_p(spec_path))))
    R = manifest.load(spec['ref']['manifest'])['references']
    mp = args[args.index('--masks') + 1] if '--masks' in args else R['hair_layers']['path']
    if not os.path.exists(_p(mp)):
        raise SystemExit('%s: not made yet (python -m charkit hairlayers SPEC)' % mp)
    Z = np.load(_p(mp))
    r = score({k: Z[k] for k in Z.files}, load_truth(R['hair_truth']['path']))
    print('%s against %s' % (mp, R['hair_truth']['path']))
    print('  '.join('%s %.3f (%d wrong)' % (v, x['accuracy'], x['wrong']) for v, x in r.items() if 'accuracy' in x) +
          '; mean family IoU %.3f' % r['all']['mean_iou'])
    print('  families: ' + ', '.join('%s %.3f' % kv for kv in r['all']['iou'].items()))
    print('  bun sides: ' + '; '.join('%s %s' % (v, ', '.join('%s %s' % kv for kv in s.items()))
                                      for v, s in r['sides'].items()))
    for c in r['all']['confusions']:
        print('  %6d px  %-8s truth %-24s got %s' % (c['px'], c['view'], c['truth'], c['got']))
    if '--json' in args:
        json.dump(r, open(_p(args[args.index('--json') + 1]), 'w'), indent=1)
    return r


def truth_main(args):
    """python -m charkit hairlayers truth [SPEC]: the manifest's hair_truth rebuilt from its source (hair_truth.json)."""
    from . import manifest
    spec_path = next((a for a in args if a.endswith('.json')), 'charkit/spec/clawd.json')
    spec = manifest.resolve(json.load(open(_p(spec_path))))
    ent = manifest.load(spec['ref']['manifest'])['references']['hair_truth']
    meta = build_truth(spec, ent['source'], ent['path'])
    print('%s: %d regions' % (ent['path'], meta['regions']))


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return 0
    if args[0] == 'score':
        return score_main(args[1:]) and 0
    if args[0] == 'truth':
        return truth_main(args[1:])
    from . import manifest
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    spec = manifest.resolve(json.load(open(_p(args[0]))))
    out = _p(opt('--out', os.path.join('charkit', 'out', spec.get('name', 'char'), 'hair')))
    if '--no-struct' in args and '--out' not in args:
        raise SystemExit('hairlayers --no-struct: give --out DIR (the manifest\'s produced layers stay the default method\'s)')
    produce(spec, out, page='--no-page' not in args, struct=STRUCT_OFF if '--no-struct' in args else None)
    print(os.path.join(out, 'index.html'))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
