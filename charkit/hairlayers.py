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

The body sheet stays the authority for the hair's silhouettes; the breakdown decides only which family a hair pixel
belongs to. Its registration overlap (hair about 0.67-0.79, face 0.57-0.69 on Clawd) is reported: two generations of
one design, not one drawing.

    python -m charkit hairlayers SPEC [--out DIR]     -> DIR/hair_layers.npz (VIEW__FAMILY), hair_layers.json, index.html
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


def transfer(fam_img, reg, figs, views, outfit_masks=None):
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
        fam = np.where(hair, fam, 0)
        buns = np.zeros(shape, bool)
        if outfit_masks is not None:
            for b in ('bun_L', 'bun_R'):
                k = '%s__%s' % (name, b)
                if k in outfit_masks and outfit_masks[k].shape == shape:
                    buns |= outfit_masks[k]
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
    return out, rep


def produce(spec, out, page=True, log=print):
    """the breakdown's families on the body sheet's hair -> out/hair_layers.npz (VIEW__FAMILY on design grids) and
    hair_layers.json (the registration and the counts)."""
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
    try:
        p = manifest.produced(spec, 'outfit_masks', log)
        if p and os.path.exists(p):
            Z = np.load(p)
            om = {k: Z[k] for k in Z.files}
    except Exception as e:                                           # (the buns then stay the breakdown's nearest)
        log('hair layers: no outfit masks (%s)' % e)
    masks, counts = transfer(lab, reg, figs, views, om)
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


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return 0
    from . import manifest
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    spec = manifest.resolve(json.load(open(_p(args[0]))))
    out = _p(opt('--out', os.path.join('charkit', 'out', spec.get('name', 'char'), 'hair')))
    produce(spec, out, page='--no-page' not in args)
    print(os.path.join(out, 'index.html'))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
