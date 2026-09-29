"""Extra views of the body sheet's figure, checked before they carve (charkit.geom.hull's extra views; the QA side, no
build stage imports it). A candidate is a generated picture with more views of the figure: the sheet extended by an
edit (its four views redrawn beside the new ones) or a fresh picture drawn at the sheet's scale. Measured per candidate:

  drift         (an extended sheet) each of its redrawn original views against the true sheet's: the figure's
                placement (px), its scale (figure height), the silhouette IoU once registered (translation; and with
                the scale undone), the eye line and ground line (L), the pixels' mean difference and the classes'
                agreement where both draw. A candidate that redraws the originals beyond the tolerance is rejected
                however good its new views look: it is a different drawing of the character.
  registration  each new view against the sheet's lines: its scale (figure height against the sheet's back view) and
                its soles against the ground line (the extended sheet's own, and the true sheet's).
  hull          each new view calibrated (hull.extra_views: azimuth and axis fitted by silhouette) against the hull of the
                sheet's four views: the silhouette IoU there (the new view held out: predicted from the sheet), per band
                (buns, head and hair, bodice, skirt, legs), and the classes' IoU against the hull's surface classes seen
                from that azimuth (the buns' hair, the dark stepped hem, the cream panels and collar).
  loo           (--loo) the hull's leave-one-out with the new views, without each, and from the sheet alone: a new view
                is accepted only if every view's held-out IoU holds or improves with it.

    python -m charkit.refviews SPEC CAND.png --views NAME:FIGURE:AZ[,NAME:FIGURE:AZ] [--bands B:LO:HI,..] [--extends] [--loo] [--h 0.01]
                             [--out DIR]
    python -m charkit.refviews SPEC DETAIL.png --detail buns|skirt|bow [--against CAND.png --views .. --map FIG:NAME,..]
"""
import json, os, sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIFT_TOL = dict(iou=0.95, scale=0.02, eye_L=0.03, ground_L=0.03)   # an original view redrawn within these is kept
BANDS = {'buns': None, 'head_hair': (-0.8, None), 'bodice': (-1.4, -0.8), 'skirt': (-3.5, -1.4), 'legs': (None, -3.5)}
DETAIL_CLASSES = ('hair', 'skin', 'orange', 'cream', 'dark', 'white')
BUNS_L = 0.4                        # the buns: the figure's top this far down (Clawd's are ~0.4 L tall on the sheet)


def sheet_state(spec, h=0.01, log=print):
    """the body sheet calibrated as the hull's build does it (views, axes, pieces, the three-quarter's axis refined), with
    the hull of its own views and its lines -> dict."""
    from charkit import eyes as eyelib, manifest, refcheck, styles
    from charkit.geom import hull
    bs = spec['ref']['body_sheet']
    prior = styles.load(spec.get('style', 'anime'))['hull']
    ex = eyelib._knobs(spec.get('eyes'))['x']
    rgb = refcheck._load(bs['image'])
    views, info = hull.views_from_sheet(rgb, ex, bs.get('facing', -1))
    A = hull.axes_for(views, h)
    masks = manifest.produced(spec, 'outfit_masks', log)
    P = hull.attach_pieces(views, masks) if masks and os.path.exists(masks) else None
    info['refined_L'] = hull.refine(views, A, prior)
    V0 = hull.rounded(views, A, list(views), **prior)
    return dict(bs=bs, rgb=rgb, views=views, info=info, A=A, P=P, prior=prior, V0=V0, lines=hull.sheet_lines(views),
                ex=ex)


def _align(ms, mc, search=(16, 10)):
    """two figure masks (the sheet's, a candidate's; full pictures) registered by translation: soles and torso axes
    matched, then the best shift within `search` px -> (IoU, dx, dy: the candidate's offset from the sheet's)."""
    def frame(m):
        rows, cols = np.nonzero(m)
        return rows.max(), np.median(cols)
    rs, cs = frame(ms); rc, cc = frame(mc)
    dy0, dx0 = int(round(rc - rs)), int(round(cc - cs))
    ys, xs = np.nonzero(ms)
    y0, y1, x0, x1 = ys.min() - 40, ys.max() + 40, xs.min() - 60, xs.max() + 60
    S = ms[max(0, y0):y1, max(0, x0):x1]
    best = (-1.0, dx0, dy0)
    H, W = mc.shape
    for dy in range(dy0 - search[1], dy0 + search[1] + 1, 2):
        for dx in range(dx0 - search[0], dx0 + search[0] + 1, 2):
            a0, b0 = max(0, y0) + dy, max(0, x0) + dx
            if a0 < 0 or b0 < 0 or a0 + S.shape[0] > H or b0 + S.shape[1] > W:
                continue
            C = mc[a0:a0 + S.shape[0], b0:b0 + S.shape[1]]
            s = (S & C).sum() / max(1, (S | C).sum())
            if s > best[0]:
                best = (float(s), dx, dy)
    s, dx, dy = best
    for ddy in (-1, 0, 1):                                        # the fine step
        for ddx in (-1, 0, 1):
            a0, b0 = max(0, y0) + dy + ddy, max(0, x0) + dx + ddx
            if a0 < 0 or b0 < 0 or a0 + S.shape[0] > H or b0 + S.shape[1] > W:
                continue
            C = mc[a0:a0 + S.shape[0], b0:b0 + S.shape[1]]
            t = (S & C).sum() / max(1, (S | C).sum())
            if t > best[0]:
                best = (float(t), dx + ddx, dy + ddy)
    return best


def _rescale(m, f, anchor):
    """a mask scaled by f about a pixel anchor (row, col), nearest neighbour."""
    H, W = m.shape
    r, c = np.mgrid[0:H, 0:W]
    rr = np.clip(np.round(anchor[0] + (r - anchor[0]) / f).astype(int), 0, H - 1)
    cc = np.clip(np.round(anchor[1] + (c - anchor[1]) / f).astype(int), 0, W - 1)
    return m[rr, cc]


def drift(S, cand_rgb, figs):
    """an extended sheet's redrawn originals (its first four full figures) against the true sheet's views -> per view
    {placement dx/dy px, scale, iou (translation), iou_scaled (scale undone), eye_dL, ground_dL, rgb_mae, class_agree},
    and 'ok' against DRIFT_TOL."""
    from charkit import bodyqa, sheetqa
    order = ('front', 'three_quarter', 'profile', 'back')
    ppl = S['info']['ppl']
    try:
        D = sheetqa.detect_figures(cand_rgb, ppl)
        eyes = {n: f for n, f in D['figures'].items()}
    except Exception:                                            # noqa: BLE001 - no eyes found: no eye-line numbers
        eyes = {}
    fgc = sheetqa.foreground(cand_rgb, sheetqa.background(cand_rgb))
    ey = eyes.get('front', {}).get('eye_y') or S['views']['front'].eye_y
    ccls = bodyqa.classes(cand_rgb, fgc, ey, ppl)[0]
    out = {}
    for i, n in enumerate(order):
        v = S['views'][n]
        box, mc = figs[i]
        ms = v.mask
        rs, rc = np.nonzero(ms.any(1))[0], np.nonzero(mc.any(1))[0]
        scale = (rc[-1] - rc[0]) / max(1, rs[-1] - rs[0])
        iou, dx, dy = _align(ms, mc)
        # the scale undone about the candidate's sole centre, then registered again
        cols = np.nonzero(mc[rc[-1] - 3:rc[-1] + 1].any(0))[0]
        mcs = _rescale(mc, 1.0 / scale, (rc[-1], float(np.median(cols)) if len(cols) else mc.shape[1] / 2))
        iou_s, _, _ = _align(ms, mcs)
        # pixels and classes where both draw, registered
        H, W = ms.shape
        ys, xs = np.nonzero(ms)
        ok = (ys + dy >= 0) & (ys + dy < cand_rgb.shape[0]) & (xs + dx >= 0) & (xs + dx < cand_rgb.shape[1])
        ys, xs = ys[ok], xs[ok]
        both = mc[ys + dy, xs + dx]
        mae = float(np.abs(S['rgb'][ys[both], xs[both]] - cand_rgb[ys[both] + dy, xs[both] + dx]).mean())
        cs = v.labels[ys[both], xs[both]]
        eye_c = eyes.get(n, {}).get('eye_y') if n != 'back' else None
        agree = float((cs == ccls[ys[both] + dy, xs[both] + dx]).mean())
        rec = dict(dx=int(dx), dy=int(dy), scale=round(float(scale), 4), iou=round(iou, 4), iou_scaled=round(iou_s, 4),
                   ground_dL=round(float((rc[-1] - dy - rs[-1]) / ppl), 4), rgb_mae=round(mae, 4),
                   class_agree=round(agree, 4))
        if eye_c:
            # the eye line against the ground line: the height of the eyes above the soles, the candidate's against the
            # sheet's (L at the sheet's scale)
            rec['eye_dL'] = round(float(((rc[-1] - eye_c) - (rs[-1] - v.eye_y)) / ppl), 4)
        out[n] = rec
    worst = dict(iou=min(r['iou'] for r in out.values()), scale=max(abs(r['scale'] - 1) for r in out.values()),
                 eye_L=max([abs(r['eye_dL']) for r in out.values() if 'eye_dL' in r] or [0.0]),
                 ground_L=max(abs(r['ground_dL']) for r in out.values()))
    fails = [k for k, t in DRIFT_TOL.items() if (worst[k] < t if k == 'iou' else worst[k] > t)]
    return dict(views=out, worst={k: round(float(x), 4) for k, x in worst.items()}, tol=DRIFT_TOL, fails=fails,
                ok=not fails)


def class_render(S):
    """the hull of the sheet's views, its surface classed from the views (no pieces): per shell voxel its class."""
    from charkit.geom import hull
    plain = {}
    for n, v in S['views'].items():
        w = hull.View(n, v.az, v.mask, v.ppl, v.axis, v.eye_y, v.labels, v.rgb)
        plain[n] = w
    names = list(plain)
    for n, v in S['views'].items():
        if abs(np.sin(np.radians(v.az))) > 1e-9:
            plain[n + '_mirror'] = hull.mirrored(plain[n], None)
    L = hull.label_volume(S['V0'], S['A'], plain, list(plain))
    return dict(L, label=L['cls'].astype(np.int32))


def detail(S, v, Lc, top_L):
    """a calibrated new view against the sheet's hull: silhouette IoU overall and per band, classes' IoU -> dict, and the
    (hull, drawing) images on the (u, z) grid for the page."""
    from charkit import bodyqa
    from charkit.geom import hull
    A = S['A']
    Pm, us = hull.project(S['V0'], A, v.az)
    Dm = v.sample(v.mask, us, A.zs)
    rows = v.band(A.zs)
    out = {'iou': round(hull.iou(Pm[:, rows], Dm[:, rows]), 4), 'bands': {}, 'classes': {}}
    z = A.zs
    for b, rng in BANDS.items():
        lo, hi = (top_L - BUNS_L, None) if b == 'buns' else rng
        sel = np.ones(len(z), bool)
        if lo is not None:
            sel &= z >= lo
        if hi is not None:
            sel &= z < hi
        if b == 'head_hair':
            sel &= z < top_L - BUNS_L
        sel &= rows
        if sel.any():
            out['bands'][b] = round(hull.iou(Pm[:, sel], Dm[:, sel]), 4)
    img, _ = hull.render_labels(Lc, A, v.az)
    img = np.where(rows[None, :], img, 0)
    C = np.where(Dm, v.sample(v.labels, us, A.zs), 0)
    for c in DETAIL_CLASSES:
        k = bodyqa.CLASS[c]
        out['classes'][c] = round(hull.iou(img == k, C == k), 4)
    return out, Pm, Dm, img, C


def evaluate(spec, path, views, extends=False, loo=False, S=None, out_dir=None, log=print):
    """one candidate: drift (extends), registration, the hull's checks, and with loo the leave-one-out -> dict."""
    from charkit import refcheck
    from charkit.geom import hull
    S = S or sheet_state(spec, log=log)
    rgb = refcheck._load(path)
    figs, _ = hull.figure_masks(rgb)
    rep = {'path': os.path.relpath(path, ROOT), 'size': [rgb.shape[1], rgb.shape[0]], 'figures': len(figs)}
    if extends:
        rep['drift'] = drift(S, rgb, figs)
    ev, ei = hull.extra_views(dict(path=path, views=views), S['lines'], S['info']['ppl'], S['V0'], S['A'])
    # registration: the new views' soles against the ground line (the candidate's own originals', else the sheet's)
    ppl = S['info']['ppl']
    ground_c = float(np.median([np.nonzero(f[1].any(1))[0][-1] for f in figs[:4]])) if extends else None
    ground_s = float(np.median([S['lines'][n]['sole'] for n in ('front', 'three_quarter', 'profile', 'back')]))
    Lc = class_render(S)
    rep['views'] = {}
    imgs = {}
    for n, v in ev.items():
        e = ei[n]
        sole = float(np.nonzero(v.mask.any(1))[0][-1])
        reg = dict(scale=e['scale'], ground_sheet_dL=round((sole - ground_s) / ppl, 4),
                   top_dL=round(float(e['top_L'] - S['lines']['back']['top_L']), 4))
        if ground_c is not None:
            reg['ground_own_dL'] = round((sole - ground_c) / ppl, 4)
        d, Pm, Dm, img, C = detail(S, v, Lc, e['top_L'])
        rep['views'][n] = dict(fit={k: e[k] for k in ('nominal_az', 'az', 'axis_L', 'iou', 'sweep')},
                               registration=reg, hull=d)
        imgs[n] = (Pm, Dm, img, C, v)
    if loo:
        rep['loo'] = loo_select(S, ev, log)
    if out_dir:
        _pictures(rep, imgs, rgb, figs, ev, out_dir)
    return rep


HOLD = 0.002                        # a sheet view's held-out IoU "holds" within this


def loo_select(S, ev, log=print):
    """the hull's leave-one-out with the new views: from the sheet's alone, with all of them, and a forward selection:
    each band (the views' bands of one kind together, in order; a view without bands is its own kind) joins if every
    sheet view's held-out IoU holds (within HOLD) or improves against the selection so far -> dict."""
    from charkit.geom import hull
    base, A, pr = dict(S['views']), S['A'], S['prior']

    def held(vs):
        r, _ = hull.validate(vs, A, 'rounded', **pr)
        return {n: r[n]['iou'] for n in vs}
    out = {'sheet_only': held(base), 'all': held(dict(base, **ev)), 'steps': []}
    kinds = list(dict.fromkeys(n.split('.', 1)[1] if '.' in n else n for n in ev))
    chosen, cur = {}, out['sheet_only']
    for k in kinds:
        add = {n: v for n, v in ev.items() if (n.split('.', 1)[1] if '.' in n else n) == k}
        trial = held(dict(base, **chosen, **add))
        d = {n: round(trial[n] - cur[n], 4) for n in base}
        ok = all(x >= -HOLD for x in d.values())
        out['steps'].append(dict(band=k, views=list(add), delta=d, held=trial, accepted=ok))
        log('loo: %s %s %s' % (k, 'accepted' if ok else 'rejected', d))
        if ok:
            chosen.update(add)
            cur = trial
    out['accepted'] = list(chosen)
    out['final'] = cur
    out['delta_vs_sheet'] = {n: round(cur[n] - out['sheet_only'][n], 4) for n in base}
    out['delta_all_vs_sheet'] = {n: round(out['all'][n] - out['sheet_only'][n], 4) for n in base}
    return out


def _pictures(rep, imgs, rgb, figs, ev, out_dir):
    """per new view: its crop, the hull of the sheet at its fitted azimuth over its silhouette (grey both, red the hull
    only, blue the drawing only), the hull's classes and the drawing's."""
    from PIL import Image
    from charkit.bodyqa import PALETTE
    os.makedirs(out_dir, exist_ok=True)
    rep['images'] = {}
    for n, (Pm, Dm, img, C, v) in imgs.items():
        im = np.full(Pm.shape + (3,), 0.96)
        im[Pm & Dm] = (0.55, 0.55, 0.6); im[Pm & ~Dm] = (0.9, 0.2, 0.2); im[Dm & ~Pm] = (0.2, 0.35, 0.95)
        cols = np.nonzero((Pm | Dm).any(1))[0]
        sl = slice(max(0, cols[0] - 10), cols[-1] + 10)
        pal = lambda K: np.array([[PALETTE.get(int(k), (0.5, 0.5, 0.5)) if k else (0.96, 0.96, 0.96) for k in row]
                                  for row in K])
        files = {}
        for tag, a in (('overlay', im[sl]), ('hull_classes', pal(img[sl])), ('drawn_classes', pal(C[sl]))):
            p = os.path.join(out_dir, '%s_%s.png' % (n, tag))
            Image.fromarray((np.clip(np.transpose(a, (1, 0, 2)), 0, 1) * 255).astype(np.uint8)).save(p)
            files[tag] = os.path.basename(p)
        rows, cols2 = np.nonzero(v.mask)
        crop = rgb[max(0, rows.min() - 10):rows.max() + 10, max(0, cols2.min() - 10):cols2.max() + 10]
        p = os.path.join(out_dir, '%s_crop.png' % n)
        Image.fromarray((crop * 255).astype(np.uint8)).save(p)
        files['crop'] = os.path.basename(p)
        rep['images'][n] = files


# ------------------------------------------------------------------------------------------------------- detail sheets
# A detail sheet draws one piece larger from several angles (the buns, the skirt, the bow), in one picture anchored by
# the body sheet. Its views at the sheet's own angles are checked against the sheet's drawing of that piece: the piece's
# region cut from both, the detail's scaled and shifted onto the sheet's (the scale fitted), the IoU there.
DETAILS = {
    # piece: (which region of a view, the detail sheet's figures in reading order -> the sheet's view at that angle)
    'buns': dict(region='head_top', views={0: 'front', 1: 'three_quarter', 2: 'profile', 3: 'back'}),
    'skirt': dict(region='skirt', views={0: 'front', 1: 'three_quarter', 2: 'profile', 4: 'back'}),
    'bow': dict(region='bow', views={0: 'front', 1: 'three_quarter', 2: 'profile'}),
}
HEAD_TOP_L = 1.0                    # the head's top region: the figure's top this far down (the buns and the crown)
SKIRT_TOP_L = -1.3                  # the skirt region: the garment's pixels below this (the waistband's top) ...
SKIRT_BOTTOM_L = -3.9               # ... to above the boots' cuffs
BOW_BAND_L = (-0.5, -1.4)           # the bow: on the bust's garment, neck to waist (the bow stands out in the profile)


def reading_order(figs, row_gap=0.25):
    """figures (box, mask) in reading order: rows by their top (a new row where a top lies `row_gap` of the picture's
    height below the row's first), left to right in each."""
    H = max(f[0][3] for f in figs)
    figs = sorted(figs, key=lambda f: f[0][1])
    rows, cur = [], []
    for f in figs:
        if cur and f[0][1] - cur[0][0][1] > row_gap * H:
            rows.append(cur); cur = []
        cur.append(f)
    rows.append(cur)
    return [f for r in rows for f in sorted(r, key=lambda f: f[0][0])]


def region(kind, mask, cls, eye_y, ppl):
    """a piece's region of a figure: 'head_top' the silhouette's top HEAD_TOP_L; 'skirt' the garment classes between
    the waistband and the boots; 'bow' the garment classes on the bust, neck to waist (eye_y None: a detail sheet's
    figure, the whole of its garment pixels) -> bool mask."""
    from charkit.bodyqa import CLASS
    rows = np.nonzero(mask.any(1))[0]
    out = np.zeros_like(mask)
    if kind == 'head_top':
        r1 = rows[0] + int(HEAD_TOP_L * ppl)
        out[rows[0]:r1] = mask[rows[0]:r1]
        return out
    g = mask & np.isin(cls, [CLASS['orange'], CLASS['cream'], CLASS['dark']])
    if kind == 'skirt':
        if eye_y is not None:
            g[:int(eye_y - SKIRT_TOP_L * ppl)] = False
            g[int(eye_y - SKIRT_BOTTOM_L * ppl):] = False
    else:
        if eye_y is not None:
            g[:int(eye_y - BOW_BAND_L[0] * ppl)] = False
            g[int(eye_y - BOW_BAND_L[1] * ppl):] = False
    from charkit import sheetqa
    lab, n = sheetqa.label(g)
    if not n:
        return g
    sizes = np.bincount(lab.ravel())[1:]
    keep = np.nonzero(sizes >= 0.05 * sizes.max())[0] + 1                 # the piece's parts, not specks
    return np.isin(lab, keep)


def _crop(m):
    ys, xs = np.nonzero(m)
    return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def match(ref, cand, s0=None, scales=np.arange(0.86, 1.141, 0.02), shift=12, buns_px=None, top_crop=False):
    """a detail's region onto the sheet's: the detail scaled by 1/s (s round s0, else its bounding box's height against
    the sheet's) and shifted (tops and centres matched, then +-shift px) where the IoU is best; top_crop: the detail cut
    to the sheet region's height from its top once scaled (a head's top) -> dict(iou, scale, buns)."""
    R, C = _crop(ref), _crop(cand)
    s0 = s0 or C.shape[0] / R.shape[0]
    best = dict(iou=-1.0)
    for f in scales:
        s = s0 * f
        h, w = max(1, int(round(C.shape[0] / s))), max(1, int(round(C.shape[1] / s)))
        rr = np.clip((np.arange(h) * s).astype(int), 0, C.shape[0] - 1)
        cc = np.clip((np.arange(w) * s).astype(int), 0, C.shape[1] - 1)
        Cs = C[np.ix_(rr, cc)]
        if top_crop:
            Cs = Cs[:R.shape[0]]
            if not Cs.any():
                continue
            Cs = _crop(Cs)
            h, w = Cs.shape
        H, W = max(R.shape[0], h) + 2 * shift + 2, max(R.shape[1], w) + 2 * shift + 2
        Rp = np.zeros((H, W), bool)
        r0, c0 = shift + 1, (W - R.shape[1]) // 2
        Rp[r0:r0 + R.shape[0], c0:c0 + R.shape[1]] = R
        for dy in range(-shift, shift + 1, 2):
            for dx in range(-shift, shift + 1, 2):
                Cp = np.zeros((H, W), bool)
                a, b = r0 + dy, (W - w) // 2 + dx
                if a < 0 or b < 0 or a + h > H or b + w > W:
                    continue
                Cp[a:a + h, b:b + w] = Cs
                i = (Rp & Cp).sum() / max(1, (Rp | Cp).sum())
                if i > best['iou']:
                    best = dict(iou=float(i), scale=float(s), dx=dx, dy=dy)
                    if buns_px:
                        top = slice(r0, r0 + buns_px)
                        best['buns'] = float((Rp[top] & Cp[top]).sum() / max(1, (Rp[top] | Cp[top]).sum()))
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in best.items()}


def detail_check(S, path, piece, extra_views=None):
    """a detail sheet's views at the sheet's angles against the sheet's drawing of the piece -> dict per view (and the
    detail sheet's other views listed, unchecked unless `extra_views` maps a figure to a calibrated extra View)."""
    from charkit import bodyqa, refcheck, sheetqa
    from charkit.geom import hull
    D = DETAILS[piece]
    rgb = refcheck._load(path)
    figs, fg = hull.figure_masks(rgb)
    figs = reading_order(figs)
    cls_d = bodyqa.classes(rgb, fg, -1e9, 1.0)[0]
    ppl = S['info']['ppl']
    s0 = eye_d = None
    if piece == 'buns':                                 # the heads' scale and eye line from the front head's eyes
        fe = sheetqa.find_eyes(sheetqa.classes(rgb), tuple(figs[0][0]), 2, max_tilt=0.25)
        if fe:
            s0 = abs(fe[1][0] - fe[0][0]) / (2 * S['ex'] * ppl)
            eye_d = float(np.mean([e[1] for e in fe]))
    out = {'path': os.path.relpath(path, ROOT), 'figures': len(figs), 'views': {}}
    if piece == 'buns':
        out['scale_from_eyes'] = s0 and round(float(s0), 4)
    targets = dict((k, S['views'][n]) for k, n in D['views'].items())
    targets.update(extra_views or {})
    for k, v in targets.items():
        if k >= len(figs):
            continue
        box, m = figs[k]
        ref = region(D['region'], v.mask, v.labels, v.eye_y, v.ppl)
        cand = region(D['region'], m, cls_d, None, ppl) if D['region'] != 'head_top' else m
        if piece == 'buns' and eye_d is not None:      # the heads above their eye lines (the detail's row shares one)
            ref = v.mask.copy(); ref[int(v.eye_y):] = False
            cand = m.copy(); cand[int(eye_d):] = False
        if not ref.any() or not cand.any():
            out['views'][v.name] = dict(iou=0.0, note='no region')
            continue
        if piece == 'buns':
            r = match(ref, cand, s0, scales=np.arange(0.9, 1.101, 0.02) if s0 else np.exp(np.arange(0.2, 1.4, 0.03)),
                      buns_px=int(BUNS_L * v.ppl), top_crop=eye_d is None)
        else:
            r = match(ref, cand)
        out['views'][v.name] = dict(r, figure=k)
    out['mean_iou'] = round(float(np.mean([r['iou'] for r in out['views'].values()])), 4) if out['views'] else 0.0
    return out


def main(args):
    from charkit import bodyeval
    from charkit.geom import hull
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    spec = bodyeval.resolve(args[0])
    if '--detail' in args:
        # a detail sheet: its views at the sheet's angles against the sheet's piece; with --against PICTURE --views
        # N:F:AZ,.. --map DETAIL_FIG:N,.. its other views against an extra view's piece too
        S = sheet_state(spec)
        ex = {}
        if opt('--against'):
            views = {t.split(':')[0]: dict(figure=int(t.split(':')[1]), az=float(t.split(':')[2]))
                     for t in opt('--views').split(',')}
            ev, _ = hull.extra_views(dict(path=os.path.abspath(opt('--against')), views=views), S['lines'],
                                     S['info']['ppl'], S['V0'], S['A'])
            ex = {int(t.split(':')[0]): ev[t.split(':')[1]] for t in opt('--map').split(',')}
        rep = detail_check(S, os.path.abspath(args[1]), opt('--detail'), ex)
        out = opt('--out', os.path.join(ROOT, 'charkit/out/refviews', os.path.splitext(os.path.basename(args[1]))[0]))
        os.makedirs(out, exist_ok=True)
        json.dump(rep, open(os.path.join(out, 'detail.json'), 'w'), indent=1)
        print(json.dumps(rep, indent=1))
        return
    views = {}
    bands = None
    if opt('--bands'):                  # NAME:LO:HI,.. (L from the eye line; empty = open)
        bands = {}
        for t in opt('--bands').split(','):
            b, lo, hi = t.split(':')
            bands[b] = [float(lo) if lo else None, float(hi) if hi else None]
    for t in opt('--views').split(','):
        n, f, az = t.split(':')
        views[n] = dict(figure=int(f), az=float(az), **({'bands': bands} if bands else {}))
    out = opt('--out', os.path.join(ROOT, 'charkit/out/refviews', os.path.splitext(os.path.basename(args[1]))[0]))
    S = sheet_state(spec, float(opt('--h', 0.01)))
    rep = evaluate(spec, os.path.abspath(args[1]), views, '--extends' in args, '--loo' in args, S=S, out_dir=out)
    os.makedirs(out, exist_ok=True)
    json.dump(rep, open(os.path.join(out, 'refviews.json'), 'w'), indent=1)
    if 'drift' in rep:
        d = rep['drift']
        print('drift: %s (worst %s)' % ('ok' if d['ok'] else 'FAILS ' + ', '.join(d['fails']), d['worst']))
        for n, r in d['views'].items():
            print('  %-14s %s' % (n, r))
    for n, r in rep['views'].items():
        print('%-10s az %.1f (nominal %.0f) axis %+.3f L  fit IoU %.4f  reg %s' % (
            n, r['fit']['az'], r['fit']['nominal_az'], r['fit']['axis_L'], r['fit']['iou'], r['registration']))
        print('           bands %s' % r['hull']['bands'])
        print('           classes %s' % r['hull']['classes'])
    if 'loo' in rep:
        L = rep['loo']
        print('loo sheet only %s' % L['sheet_only'])
        print('loo all %s' % L['all'])
        for st in L['steps']:
            print('  %-10s %s %s' % (st['band'], 'accepted' if st['accepted'] else 'rejected', st['delta']))
        print('accepted %s; final %s; vs sheet %s' % (L['accepted'], L['final'], L['delta_vs_sheet']))
    print(os.path.join(out, 'refviews.json'))


if __name__ == '__main__':
    main(sys.argv[1:])
