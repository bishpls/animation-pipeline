"""A piece's shape truth on the turnarounds (Michael, 2026-10-01: each piece's shape truth is its layer without what lies
on it; "if we aren't yet comparing hair checks against the no-accessories references, we absolutely should be"). The
manifest's shape_truth[part] names a redraw of a turnaround without the pieces that cover the part (Clawd's hair
without its star and crab clips: hair_clips_layers' top row, the head turnaround's front, three-quarter and profile
heads). The turnaround stays the placement authority: its pixels stand everywhere but where a cover hides the part,
and there the redraw's pixels, registered on the view, stand in. The covers are the design's drawn accessories as the
QA finds them (charkit.accqa: the outfit graph's clip pieces, on the head and the body turnaround alike), so the same
rule serves another character's hair under his crown once his accessories are found.

  register   per view, the redraw's head placed on the turnaround's by the eyes (scale the two sheets' px per L, the
             eye points together), then refined (scale within SCALE, shift within SHIFT L) to the best IoU of the part's
             colour (the hair family) in a ring round the cover (RING L): the fill must join the turnaround's drawing
             where it meets it. Reported: the scale and shift, the ring's IoU, and the part's IoU over the whole head
             outside the cover (the refcheck: the two drawings agree away from the cover)
  composite  the turnaround with each view's cover (its found pixels grown by PAD L: the cover's outline ink) repainted
             from the registered redraw (resampled with a pre-blur when it shrinks), the figure's mask taken from the
             redraw there too
Views the redraw doesn't draw (Clawd's back: the clips don't reach it) keep the turnaround, and a view with no cover
found is the turnaround unchanged.

The QA's hair checks read the composite (qa3d.Design.shape_views, shape_head) and draw our hair without our
accessories (qa3d.Design.hides): each side's hair alone, compared where the drawing hides it too.

    python -m charkit.shapetruth SPEC [--part hair] [--out DIR]     the refcheck on both turnarounds, with pictures
"""
import json, os

import numpy as np

VIEWS = ('front', 'three_quarter', 'profile', 'back')
MODE = os.environ.get('CHARKIT_SHAPE_TRUTH', 'fill')    # 'off': the QA reads the turnarounds as drawn (a lab's before)
PAD = 0.012               # L: the fill reaches this past the cover's found pixels (its outline ink, the antialiasing)
RING = (0.02, 0.15)       # L: the registration ring round the cover (from the fill's edge outward)
SCALE = 0.04              # the scale refined within this either way of the two sheets' px per L ratio
SCALE_STEP = 0.01
SHIFT = 0.04              # L: the shift refined within this either way
HEAD = dict(x=1.2, top=1.4, bottom=-0.6)    # L round the eyes: the head the refcheck compares (the hair, not the dress)
MIN_COVER = 20            # px: a view's cover smaller than this isn't filled
REACH = 0.04              # L: round the cover, the turnaround's pixels that differ from the redraw (DIFF: the summed
DIFF = 0.35               # channels) and join the cover are what the finder missed (a crab's legs, the outline ink)
TOL = dict(ring_iou=0.85, hair_iou=0.85)    # the refcheck (declared before measuring the silhouette, 2026-10-01): the
                                            # fill joins the turnaround (the part's colour in the ring), and the hair's
                                            # silhouette (its colour closed, holes filled) agrees away from the cover


def _p(path):
    from .manifest import ROOT
    return path if os.path.isabs(path) else os.path.join(ROOT, path)


def entry(spec, part):
    """the manifest's shape_truth[part] when it names a picture of a turnaround redrawn without the part's covers ->
    dict(id, path, rows ('top', 'bottom' or None: the whole picture), views (the views it draws, or None: every view
    found), placement, manifest (its path)) or None."""
    ref = spec.get('ref') if isinstance(spec.get('ref'), dict) else {}
    man = ref.get('manifest')
    if not man:
        return None
    from . import manifest
    M = manifest.load(man)
    e = (M.get('shape_truth') or {}).get(part)
    if not isinstance(e, dict):
        return None
    sid = e.get('shape')
    r = (M.get('references') or {}).get(sid) or {}
    if not str(r.get('path', '')).endswith('.png'):
        return None
    return dict(id=sid, path=r['path'], rows=e.get('rows'), views=e.get('views'), placement=e.get('placement'),
                covers=e.get('covers', 'accessories'), manifest=man)


def rows_of(rgb, rows):
    """the picture's rows a shape truth reads: 'top' / 'bottom' (split at the widest empty band of rows,
    charkit.layerref's reading of a two-row sheet), else the whole -> (rgb, row offset)."""
    if rows not in ('top', 'bottom'):
        return rgb, 0
    from .layerref import _rows_split
    cut = _rows_split(rgb)
    return (rgb[:cut], 0) if rows == 'top' else (rgb[cut:], cut)


def part_mask(rgb, fg):
    """the part's colour on a drawing (the hair: the orange family, bodyqa.family; the character's palette when one is
    active) within its figure."""
    from . import bodyqa
    return (bodyqa.family(rgb) == bodyqa.CLASS['orange']) & fg


def source(rgb, eye_x, facing=-1, rows=None, views=None):
    """the redraw's heads: dict(rgb (its rows), ppl, views {view: eye (x, y px)}, fg, part, blobs {view: its head's
    figure}) (accqa.sheet_views' eyes, the views it draws)."""
    from . import accqa, sheetqa
    rgb, _ = rows_of(np.asarray(rgb, float)[..., :3], rows)
    S = accqa.sheet_views(rgb, eye_x, 'head', facing)
    fg = sheetqa.foreground(rgb, sheetqa.background(rgb))
    vs = {v: sv['eye'] for v, sv in S['views'].items() if views is None or v in views}
    return dict(rgb=rgb, ppl=S['ppl'], views=vs, fg=fg, part=part_mask(rgb, fg),
                blobs={v: blob(fg, e) for v, e in vs.items()})


def blob(fg, eye):
    """the figure (a connected part of fg) holding the eye point (x, y), else the one nearest it."""
    from scipy import ndimage
    lab, n = ndimage.label(fg)
    if not n:
        return np.zeros(fg.shape, bool)
    r, c = int(round(eye[1])), int(round(eye[0]))
    H, W = fg.shape
    k = lab[min(max(r, 0), H - 1), min(max(c, 0), W - 1)]
    if k == 0:
        _, (iy, ix) = ndimage.distance_transform_edt(lab == 0, return_indices=True)
        k = lab[iy[min(max(r, 0), H - 1), min(max(c, 0), W - 1)], ix[min(max(r, 0), H - 1), min(max(c, 0), W - 1)]]
    return lab == k


def _box(m, pad, shape):
    r, c = np.nonzero(m)
    H, W = shape
    return (max(0, r.min() - pad), min(H, r.max() + pad + 1), max(0, c.min() - pad), min(W, c.max() + pad + 1))


def _grid(box, step=1):
    r0, r1, c0, c1 = box
    return np.mgrid[r0:r1:step, c0:c1:step].astype(float)


def _sample(img, src_eye, dst_eye, s, box, blur=True, order=1, step=1):
    """img (src) resampled onto the dst box (r0, r1, c0, c1; every `step` px): dst pixel (r, c) reads src (p - dst_eye)
    / s + src_eye (x, y order in the eyes), pre-blurred when it shrinks (s < 1) -> array (+ channels)."""
    from scipy import ndimage
    rr, cc = _grid(box, step)
    sr = (rr - dst_eye[1]) / s + src_eye[1]
    sc = (cc - dst_eye[0]) / s + src_eye[0]
    a = np.asarray(img, float)
    chans = [a] if a.ndim == 2 else [a[..., k] for k in range(a.shape[2])]
    out = []
    for ch in chans:
        if blur and s < 0.9:
            ch = ndimage.gaussian_filter(ch, 0.45 / s)
        out.append(ndimage.map_coordinates(ch, [sr, sc], order=order, mode='constant', cval=0.0))
    return out[0] if a.ndim == 2 else np.stack(out, -1)


def _iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 0.0


def register(dst_rgb, dst_part, dst_blob, cover, dst_eye, ppl, src, view, log=None):
    """one view's registration of the redraw (source()) on the turnaround: dst_rgb, dst_part, dst_blob (the
    turnaround's picture, part colour and the view's figure, the whole sheet), cover (the cover's found pixels on the
    sheet), dst_eye (x, y), ppl (its px per L). The head first (scale within SCALE, shift within SHIFT L, every few px:
    the part's IoU over the head outside the cover, the two figures each its own), then the join (the shift within a
    step and the scale within half a percent: the part's IoU in the ring round the cover) -> dict(scale, shift (rows,
    cols px), head_iou, ring_iou, fill (the pixels to repaint), ...) or None."""
    from scipy import ndimage
    if view not in src['views'] or cover.sum() < MIN_COVER:
        return None
    s0 = ppl / src['ppl']
    se = src['views'][view]
    spart = (src['part'] & src['blobs'][view]).astype(float)
    sblob = src['blobs'][view].astype(float)
    H, W = dst_part.shape
    pad = max(1, int(round(PAD * ppl)))
    fill0 = ndimage.binary_dilation(cover, iterations=pad)
    rin, rout = int(round(RING[0] * ppl)), int(round(RING[1] * ppl))
    grown = ndimage.binary_dilation(fill0, iterations=rin)
    ring = ndimage.binary_dilation(fill0, iterations=rout) & ~grown & dst_blob
    R = int(round(SHIFT * ppl))
    k = max(1, int(round(ppl / 100.0)))
    # the head: the part over the view's figure, outside the grown cover
    hb = (max(0, int(round(dst_eye[1] - HEAD['top'] * ppl))), min(H, int(round(dst_eye[1] - HEAD['bottom'] * ppl))),
          max(0, int(round(dst_eye[0] - HEAD['x'] * ppl))), min(W, int(round(dst_eye[0] + HEAD['x'] * ppl))))
    big = (hb[0] - R, hb[1] + R, hb[2] - R, hb[3] + R)
    gr, gc = _grid(hb, k)
    gr, gc = gr.astype(int), gc.astype(int)
    Dp = dst_part[gr, gc]
    Db = dst_blob[gr, gc]
    keep = ~grown[gr, gc]
    nR = R // k
    best = None
    for ds in np.arange(-SCALE, SCALE + 1e-9, SCALE_STEP):
        s = s0 * (1 + ds)
        Sp = _sample(spart, se, dst_eye, s, big, step=k) > 0.5
        Sb = _sample(sblob, se, dst_eye, s, big, step=k) > 0.5
        h, w = Dp.shape
        for dy in range(-nR, nR + 1):
            for dx in range(-nR, nR + 1):
                sl = (slice(nR - dy, nR - dy + h), slice(nR - dx, nR - dx + w))
                m = keep & (Db | Sb[sl])
                v = _iou(Sp[sl][m], Dp[m])
                key = (round(v, 4), -abs(ds), -(dy * dy + dx * dx))
                if best is None or key > best[0]:
                    best = (key, s, dy * k, dx * k, v)
    _, s1, dy1, dx1, hv = best
    # the join: the ring round the cover at full resolution
    rb = _box(ring | fill0, k + 2, (H, W))
    D = dst_part[rb[0]:rb[1], rb[2]:rb[3]]
    rg = ring[rb[0]:rb[1], rb[2]:rb[3]]
    bigr = (rb[0] - k, rb[1] + k, rb[2] - k, rb[3] + k)
    best = None
    for ds in (-0.005, 0.0, 0.005):
        s = s1 * (1 + ds)
        S = _sample(spart, se, (dst_eye[0] + dx1, dst_eye[1] + dy1), s, bigr) > 0.5
        h, w = D.shape
        for dy in range(-k, k + 1):
            for dx in range(-k, k + 1):
                Sv = S[k - dy:k - dy + h, k - dx:k - dx + w]
                v = _iou(Sv[rg], D[rg])
                key = (round(v, 4), -abs(ds), -(dy * dy + dx * dx))
                if best is None or key > best[0]:
                    best = (key, s, dy, dx, v)
    _, s, dy, dx, iou = best
    eye = (dst_eye[0] + dx1 + dx, dst_eye[1] + dy1 + dy)
    # the refcheck: the hair's silhouette (its colour closed, holes filled) over the head window outside the grown
    # cover, the two figures each its own
    Sp = _sample(spart, se, eye, s, hb) > 0.5
    Sb = _sample(sblob, se, eye, s, hb) > 0.5
    sil = lambda m: ndimage.binary_fill_holes(ndimage.binary_closing(m, iterations=max(1, int(round(0.01 * ppl)))))
    Dh = dst_part[hb[0]:hb[1], hb[2]:hb[3]] & dst_blob[hb[0]:hb[1], hb[2]:hb[3]]
    kh = ~grown[hb[0]:hb[1], hb[2]:hb[3]]
    hair_iou = _iou(sil(Sp & Sb)[kh], sil(Dh)[kh])
    # the pixels to repaint: the cover grown by PAD, and what the cover finder missed round it (its legs, its outline
    # ink): the turnaround's pixels within REACH of the cover that differ from the registered redraw, joined to it
    rb2 = _box(cover, int(round(REACH * ppl)) + 2, (H, W))
    img = _sample(src['rgb'], se, eye, s, rb2)
    diff = np.abs(np.asarray(dst_rgb, float)[rb2[0]:rb2[1], rb2[2]:rb2[3], :3] - img).sum(-1) > DIFF
    near = ndimage.binary_dilation(cover[rb2[0]:rb2[1], rb2[2]:rb2[3]], iterations=int(round(REACH * ppl)))
    f0 = fill0[rb2[0]:rb2[1], rb2[2]:rb2[3]]
    lab, n = ndimage.label((diff & near) | f0)
    keepl = np.unique(lab[f0])
    fill = fill0.copy()
    fill[rb2[0]:rb2[1], rb2[2]:rb2[3]] |= np.isin(lab, keepl[keepl > 0])
    fb = _box(fill, 0, (H, W))
    Sf = _sample(spart, se, eye, s, fb) > 0.5
    rec = dict(view=view, scale=round(float(s), 5), scale_vs_ppl=round(float(s / s0), 4),
               shift=[int(dy1 + dy), int(dx1 + dx)], shift_L=[round((dy1 + dy) / ppl, 4), round((dx1 + dx) / ppl, 4)],
               hair_iou=round(hair_iou, 4), part_iou=round(hv, 4), ring_iou=round(iou, 4), cover_px=int(cover.sum()),
               fill_px=int(fill.sum()),
               grown_by_diff_px=int(fill.sum() - fill0.sum()), ppl=round(float(ppl), 3),
               fill_part=round(float(Sf[fill[fb[0]:fb[1], fb[2]:fb[3]]].mean()), 4))
    rec['pass'] = bool(rec['ring_iou'] >= TOL['ring_iou'] and rec['hair_iou'] >= TOL['hair_iou'])
    rec['_eye'], rec['_fill'] = eye, fill
    if log:
        log('%-14s scale x%.4f  shift %s px  hair IoU %.3f (colour %.3f)  ring IoU %.3f  cover %d px (+%d by '
            'difference)  drawn as the part %.2f  %s' % (view, rec['scale_vs_ppl'], rec['shift'], hair_iou, hv, iou,
                                                       rec['cover_px'], rec['grown_by_diff_px'], rec['fill_part'],
                                                       'PASS' if rec['pass'] else 'FAIL'))
    return rec


def composite(rgb, fg, covers, eyes, ppl, src, log=None):
    """the turnaround with its covers repainted from the redraw: rgb (H, W, 3) floats, fg its figure (the whole sheet,
    or None: found here), covers {view: the cover's pixels on the sheet}, eyes {view: (x, y)} (each view's grid
    origin), ppl -> (rgb, fg, {view: register()'s record}, {view: the repainted pixels on the sheet})."""
    from . import sheetqa
    rgb0 = np.asarray(rgb, float)[..., :3]
    rgb = rgb0.copy()
    fg0 = sheetqa.foreground(rgb0, sheetqa.background(rgb0)) if fg is None else np.asarray(fg, bool)
    out_fg = fg0.copy()
    part = part_mask(rgb0, fg0)
    src_fg = src['fg'].astype(float)
    rep, filled = {}, {}
    for v, cov in covers.items():
        if v not in eyes:
            continue
        r = register(rgb0, part, blob(fg0, eyes[v]), cov, eyes[v], ppl, src, v, log=log)
        if r is None:
            continue
        fill = r.pop('_fill')
        eye = r.pop('_eye')
        b = _box(fill, 0, fill.shape)
        se = src['views'][v]
        img = _sample(src['rgb'], se, eye, r['scale'], b)
        m = fill[b[0]:b[1], b[2]:b[3]]
        rgb[b[0]:b[1], b[2]:b[3]][m] = np.clip(img[m], 0, 1)
        f = _sample(src_fg, se, eye, r['scale'], b, blur=False) > 0.5
        out_fg[b[0]:b[1], b[2]:b[3]][m] = f[m]
        rep[v], filled[v] = r, fill
    return rgb, out_fg, rep, filled


def fill_labels(lab, covered, part):
    """a label image (0 unlabelled, else a label: the hair's families, a truth's regions) under the repainted pixels:
    the part's pixels there (the redraw's) take the label nearest them outside (the drawn locks round the cover), the
    rest there none -> the new label image."""
    from scipy import ndimage
    lab = np.array(lab)
    src = (lab > 0) & ~covered
    if not covered.any() or not src.any():
        return lab
    _, (iy, ix) = ndimage.distance_transform_edt(~src, return_indices=True)
    out = lab.copy()
    out[covered] = 0
    m = covered & part
    out[m] = lab[iy[m], ix[m]]
    return out


def sheet_covers(design_clips, ppl, shape):
    """a sheet's covers per view on the whole sheet from charkit.accqa's design() of it (masks on windows round each
    view's eye: accqa.crop's grid) -> ({view: mask}, {view: eye (x, y)})."""
    from . import accqa
    W = accqa.WIN
    covers, eyes = {}, {}
    H_, W_ = shape
    for v, dv in (design_clips.get('views') or {}).items():
        m = np.zeros(shape, bool)
        x0 = int(round(dv['eye'][0] - W['x'] * ppl))
        y0 = int(round(dv['eye'][1] - W['top'] * ppl))
        for x in (dv.get('masks') or {}).values():
            ys, xs = np.nonzero(x)
            ok = (ys + y0 >= 0) & (ys + y0 < H_) & (xs + x0 >= 0) & (xs + x0 < W_)
            m[ys[ok] + y0, xs[ok] + x0] = True
        if m.any():
            covers[v] = m
        eyes[v] = tuple(dv['eye'])
    return covers, eyes


def make(rgb, fg, design_clips, ppl, src_rgb, eye_x, facing, rows, views):
    """the composite of a sheet (rgb, its figure fg or None; design_clips: accqa.design() of it) with the shape truth's
    redraw (src_rgb, its rows and views) -> dict(rgb, fg, report {view: record}, filled {view: mask}). Pure in its
    arguments (the QA memoises it)."""
    src = source(src_rgb, eye_x, facing, rows, views)
    covers, eyes = sheet_covers(design_clips, ppl, np.asarray(rgb).shape[:2])
    out, ofg, rep, filled = composite(rgb, fg, covers, eyes, ppl, src)
    return dict(rgb=out, fg=ofg, report=rep, filled=filled, src_ppl=round(float(src['ppl']), 3),
                src_views=sorted(src['views']))


# ------------------------------------------------------------------------------------------------------------ the CLI
REF_MARGIN = 0.03     # the refcheck on a turnaround the redraw wasn't made from: its hair silhouette IoU within this of
                      # the placement sheet's own (the head turnaround registered on the body turnaround the same way:
                      # two drawings of one head disagree by that much already)
SWAP = {'front': 'three_quarter', 'three_quarter': 'profile', 'profile': 'front'}   # the known-bad: views mislaid


def refcheck(spec, part='hair', out=None, log=print, known_bad=True):
    """the shape truth registered on both turnarounds (the head sheet; the body sheet the hair checks read) -> dict(
    sheets {name: per view the registration}, reference (the placement sheet itself registered on the others: the level
    two drawings of the head agree to), known_bad (the redraw's views mislaid, SWAP: must FAIL), pass), with pictures in
    out: per view the turnaround, the composite and the repainted pixels. A view passes when the fill joins the
    turnaround (ring_iou) and the hair's silhouette agrees outside the cover (hair_iou >= TOL, and within REF_MARGIN of
    the placement sheet's own agreement on a sheet it wasn't drawn from)."""
    from . import accqa, eyes as eyelib, refcheck as rc
    from .bodymeasure import load_graph
    e = entry(spec, part)
    if e is None:
        raise SystemExit('shapetruth: no shape_truth[%s] picture in the manifest' % part)
    ex = eyelib._knobs(spec.get('eyes'))['x']
    pieces = accqa.clip_pieces(load_graph(spec))
    load = lambda p: np.asarray(rc._load(_p(p)), float)[..., :3]
    items = [(n, k, g, f, p, load(p)) for n, p, k, g, f in accqa.sheets(spec)]
    D = accqa.design_sheets(items, ex, pieces)
    src_rgb = load(e['path'])
    res = {'shape': e['id'], 'rows': e['rows'], 'tol': dict(TOL, ref_margin=REF_MARGIN), 'sheets': {}, 'reference': {}}
    pics = []
    place = next((it for it in items if it[0] == e.get('placement')), None)
    for name, kind, graded, facing, path, rgb in items:
        log('%s (%s sheet, %.1f px/L):' % (name, kind, D[name]['ppl']))
        got = make(rgb, None, D[name], D[name]['ppl'], src_rgb, ex, facing, e['rows'], e['views'])
        res['sheets'][name] = dict(kind=kind, ppl=round(D[name]['ppl'], 3), src_ppl=got['src_ppl'],
                                   views=got['report'])
        if place is not None and place[0] != name:
            ref = make(rgb, None, D[name], D[name]['ppl'], place[5], ex, place[3], None, sorted(got['report']))
            res['reference'][name] = {v: dict(source=place[0], hair_iou=r['hair_iou'], ring_iou=r['ring_iou'])
                                      for v, r in ref['report'].items()}
            for v, r in got['report'].items():
                rr = res['reference'][name].get(v)
                if rr is not None:
                    r['vs_placement'] = round(r['hair_iou'] - rr['hair_iou'], 4)
                    r['pass'] = bool(r['ring_iou'] >= TOL['ring_iou'] and (r['hair_iou'] >= TOL['hair_iou'] or
                                                                           r['vs_placement'] >= -REF_MARGIN))
        for v, r in got['report'].items():
            log('  %-14s scale x%.4f  shift %s  hair silhouette IoU (outside the cover) %.3f (its colour %.3f)  ring IoU '
                '%.3f  cover %d px (+%d px by difference)  drawn as the part %.2f  %s' % (
                    v, r['scale_vs_ppl'], r['shift'], r['hair_iou'], r['part_iou'], r['ring_iou'], r['cover_px'],
                    r['grown_by_diff_px'], r['fill_part'], 'PASS' if r['pass'] else 'FAIL'))
            f = got['filled'][v]
            b = _box(f, int(0.25 * D[name]['ppl']), f.shape)
            pics.append((name, v, rgb[b[0]:b[1], b[2]:b[3]], got['rgb'][b[0]:b[1], b[2]:b[3]], f[b[0]:b[1], b[2]:b[3]]))
    res['pass'] = bool(all(r['pass'] for s in res['sheets'].values() for r in s['views'].values()))
    for name, rr in res['reference'].items():
        log('%s, the placement sheet itself registered the same way: %s' % (name, ', '.join(
            '%s hair IoU %.3f' % (v, r['hair_iou']) for v, r in rr.items())))
    if known_bad:
        # the calibration's known-bad: the redraw's views mislaid (front drawn on the three-quarter, ...): must FAIL
        kb = {}
        for name, kind, graded, facing, path, rgb in items:
            src = source(src_rgb, ex, facing, e['rows'], e['views'])
            src = dict(src, views={SWAP.get(v, v): x for v, x in src['views'].items()},
                       blobs={SWAP.get(v, v): x for v, x in src['blobs'].items()})
            covers, eyes = sheet_covers(D[name], D[name]['ppl'], rgb.shape[:2])
            _, _, rep_, _ = composite(rgb, None, covers, eyes, D[name]['ppl'], src)
            kb[name] = {v: dict(hair_iou=r['hair_iou'], ring_iou=r['ring_iou'], pass_=r['pass']) for v, r in rep_.items()}
        res['known_bad'] = dict(what='the redraw\'s views mislaid (%s)' % SWAP, views=kb,
                                fails=bool(all(not r['pass_'] for x in kb.values() for r in x.values())))
        log('known-bad (views mislaid): %s' % ('FAIL in every view, as it must' if res['known_bad']['fails'] else
                                              'PASSES somewhere: the refcheck is blind to it'))
    if out:
        os.makedirs(out, exist_ok=True)
        from PIL import Image
        for name, v, a, b, f in pics:
            from scipy import ndimage
            edge = f & ~ndimage.binary_erosion(f, iterations=1)
            c = b.copy()
            c[edge] = (0.1, 0.4, 1.0)
            img = np.concatenate([a, np.ones((a.shape[0], 6, 3)), b, np.ones((a.shape[0], 6, 3)), c], 1)
            k = max(1, int(round(300 / max(1, a.shape[0]))))
            im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
            im.resize((im.width * k, im.height * k), Image.NEAREST).save(os.path.join(out, '%s_%s.png' % (name, v)))
        json.dump(res, open(os.path.join(out, 'shapetruth_%s.json' % part), 'w'), indent=1)
    log('shapetruth %s: %s' % (part, 'PASS' if res['pass'] else 'FAIL'))
    return res


def main(args):
    from . import manifest
    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
        return
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    spec = manifest.resolve(json.load(open(_p(args[0]))))
    refcheck(spec, opt('--part', 'hair'), opt('--out'))


if __name__ == '__main__':
    import sys
    main(sys.argv[1:])
