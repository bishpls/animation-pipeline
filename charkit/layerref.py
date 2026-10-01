"""Separated layer references checked against the turnaround before they are registered (Michael, 2026-10-01: wherever
one piece covers another, a reference of the cover alone and of the covered layer WITHOUT it, as worn, in several views;
docs/workstreams/layerrefs.md). A layer sheet is a generated picture; what it adds is what the turnaround can't show,
so what it can be checked on is what both draw:

  visible   the covered layer where the turnaround shows it (R: its pixels there) must be drawn there, and nothing of
            the layer may stand where the turnaround shows something else that isn't in front of it; where a cover hides
            it on the turnaround (DC: the occluders' pixels in that view) the sheet is free, that being its point.
            Per view, once registered: iou_dc = |C & R| / (|C & R| + |C - (R | DC)| + |R - C|) (the IoU with the
            hidden region left out), recall |C & R| / |R|, outside |C - (R | DC)| / |C|, hidden |C & DC| / |C| (the
            share of the drawing the turnaround can't show: what the sheet is for).
  scale     one scale across the sheet (the fitted scales' spread) and, where the sheet keeps the turnaround's layout,
            the eye line above the soles.

Kinds:
  body   a base body sheet (the body turnaround redrawn in its layout and pose, the costume replaced by a fitted
         bodysuit; the head, hair, clips, hands and boots kept): registered by the eyes and the axis (the sheet's own
         calibration, hull.views_from_sheet) with a +-8 px refinement on the kept parts; the kept parts' IoU (the head
         and hair above the collar, the legs and boots below the costume); in the costume's band R the turnaround's
         visible skin, DC its garments, so outside is the body standing out of the costume (and its most, L).
  clips  a hair-clip layer sheet (top row: the head without its clips at the head turnaround's front, three-quarter and
         profile; bottom row: each clip alone, straight on and edge-on): per head the silhouette IoU against the head
         turnaround's once registered by the eyes, the clips charkit.accqa still finds on it (none expected), the share
         of the turnaround's clip pixels drawn as hair; per clip its straight-on shape against the turnaround's
         (accqa.shape_iou, the crab's partly hidden there), the star's arms (fractions of its height).
  skirt  a skirt layer sheet (two rows of front, three-quarter, profile, back: the skirt without the flaps, the flaps
         alone; on dress forms, scale fitted per figure): R and DC from the hand-checked outfit truth (outfit_truth)
         on the turnaround's views, the occluders per view in OCCLUDERS.
  bodice a bodice sheet (tool/garments4, 2026-10-01: the turnaround redrawn in its layout without the bow and its tails,
         what the bow hides drawn as worn: the sailor collar's lapels flat on the chest along the V, the V's skin down
         to the knot's place, the bodice front): registered as the body kind (the figures' heights, the eyes, +-8 px on
         the kept parts); the kept parts' IoU (the head and hair above HEAD_Z, the waistband, skirt, legs and boots
         below BODICE_LOW_Z); in the band between, the layer (the sheet's garment pixels) against the outfit truth's
         collar, top and bodice_panel (R) with the bow and its tails free (DC) and the kept pieces round them left out;
         the V (front and three-quarter: the skin in V_WIN) against the turnaround's visible skin there, the bow free.

    python -m charkit.layerref SPEC SHEET.png --kind body|clips|skirt|bodice [--out DIR]
"""
import json, os, sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# declared before any sheet was measured (2026-10-01): a sheet passes when every view holds these
TOL = dict(kept_iou=0.90,           # body: the kept parts (head and hair, legs and boots) once registered
           scale=0.02,              # body: px per L against the turnaround's; skirt: the fitted scales' spread
           eye_L=0.03,              # body: the eye line above the soles, L (refviews.DRIFT_TOL's)
           outside=0.03,            # every kind: the layer standing where the turnaround shows something not in front
           protrude_L=0.04,         # body: the most it stands out of the costume, L
           recall=0.85,             # the turnaround's visible pixels of the layer drawn
           head_iou=0.90,           # clips: the head without its clips against the head turnaround's
           clips_px=0.002,          # clips: clip pixels found on the clip-free heads, share of the head
           hair_fill=0.85,          # clips: the turnaround's clip pixels drawn as hair (or its lines)
           clip_shape=0.60,         # clips: a clip's straight-on shape IoU (shape only)
           iou_dc=0.80,             # skirt, bodice: per view
           scale_spread=0.06,       # skirt: the eight figures' fitted scales, (max - min) / median
           v_recall=0.80,           # bodice: the turnaround's visible skin in the V drawn as skin (front, three-quarter)
           v_outside=0.10)          # bodice: the sheet's V skin where the turnaround shows the garment (not the bow)
BODICE_LOW_Z = -1.40                # bodice: L from the eye line; below it the waistband, skirt, legs and boots (kept)
BODICE_LAYER = ('collar', 'top', 'bodice_panel')        # bodice: the layer's pieces on the outfit truth
BODICE_COVER = ('bow', 'bow_tail_L', 'bow_tail_R')      # bodice: what the sheet leaves out (free: DC)
V_WIN = dict(x=0.25, top=-0.40, bottom=-0.90)           # bodice: the V's window, L round the midline and the eye line
HEAD_Z = -0.45                      # body: L from the eye line; above it the head, hair and buns (kept)
LEGS_Z = -3.2                       # body: below it the legs and boots (kept); the costume's band between
SKIRT_TOP_Z, SKIRT_BOTTOM_Z = -1.2, -3.6    # skirt: the band the layers live in on the turnaround
NEUTRAL_RB = 0.025                  # skirt: a dark pixel this neutral (R - B) is the dress form's pole, not the trim
HANDS = ('cuff_L', 'cuff_R')        # skirt: the 'none' components touching these are the arms and hands
OCCLUDERS = {                       # skirt: per layer and view, what hides the layer on the turnaround
    'skirt': {'front': ('hands',), 'three_quarter': ('hands',),
              'profile': ('hands', 'overskirt_panel_L', 'overskirt_panel_R'),
              'back': ('hands', 'overskirt_panel_L', 'overskirt_panel_R')},
    'flaps': {'front': ('hands', 'skirt', 'skirt_panel', 'shorts', 'legs'),
              'three_quarter': ('hands', 'skirt', 'skirt_panel', 'shorts', 'legs'),
              'profile': ('hands', 'skirt', 'skirt_panel', 'shorts', 'legs'),
              'back': ('hands',)},
}
LAYER_PIECES = {'skirt': ('skirt', 'skirt_panel', 'waistband'),
                'flaps': ('overskirt_panel_L', 'overskirt_panel_R', 'waistband')}
VIEWS = ('front', 'three_quarter', 'profile', 'back')


def _load(path):
    from charkit import refcheck
    return refcheck._load(path)


def _place(m, s, src, H, W, dst):
    """an image moved into another frame: dst pixel (r, c) reads src + ((r, c) - dst) / s (nearest), outside 0."""
    r, c = np.mgrid[0:H, 0:W]
    rr = np.round(src[0] + (r - dst[0]) / s).astype(int)
    cc = np.round(src[1] + (c - dst[1]) / s).astype(int)
    ok = (rr >= 0) & (rr < m.shape[0]) & (cc >= 0) & (cc < m.shape[1])
    out = np.zeros((H, W), m.dtype)
    out[ok] = m[rr[ok], cc[ok]]
    return out


def _shift(m, dy, dx):
    out = np.zeros_like(m)
    H, W = m.shape
    ys, yd = (slice(0, H - dy), slice(dy, H)) if dy >= 0 else (slice(-dy, H), slice(0, H + dy))
    xs, xd = (slice(0, W - dx), slice(dx, W)) if dx >= 0 else (slice(-dx, W), slice(0, W + dx))
    out[yd, xd] = m[ys, xs]
    return out


def _iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 0.0


def scores(C, R, DC):
    """the layer C against its visible pixels R with the hidden region DC left out -> dict (see the module)."""
    C, R, DC = C.astype(bool), R.astype(bool), DC.astype(bool) & ~R
    tp, fp, fn = (C & R).sum(), (C & ~R & ~DC).sum(), (R & ~C).sum()
    n = max(1, C.sum())
    return dict(iou_dc=round(float(tp / max(1, tp + fp + fn)), 4), recall=round(float(tp / max(1, R.sum())), 4),
                outside=round(float(fp / n), 4), hidden=round(float((C & DC).sum() / n), 4), px=int(C.sum()))


# ---------------------------------------------------------------------------------------------------------------- body
def check_body(spec, path, log=print):
    from scipy import ndimage
    from charkit import bodyqa, eyes as eyelib
    from charkit.geom import hull
    ex = eyelib._knobs(spec.get('eyes'))['x']
    bs = spec['ref']['body_sheet']
    T, ti = hull.views_from_sheet(_load(bs['image']), ex, bs.get('facing', -1))
    rgb = _load(path)
    Cv, ci = hull.views_from_sheet(rgb, ex, bs.get('facing', -1))
    # the scale from the figures' heights, as refviews.drift registers a redrawn sheet (the eyes' spacing is ~70 px: a
    # pixel there is 1.4%, against 0.07% of a figure's ~1340 px); the eyes' spacing kept as information
    ext = lambda m: np.ptp(np.nonzero(m.any(1))[0])
    s = float(np.median([ext(T[n].mask) / ext(Cv[n].mask) for n in VIEWS if n in T and n in Cv]))
    out = {'kind': 'body', 'path': os.path.relpath(path, ROOT), 'scale': round(s, 4),
           'eye_spacing_ratio': round(float(ci['ppl'] / ti['ppl']), 4), 'views': {}, 'tol': TOL}
    skin = bodyqa.CLASS['skin']
    imgs = {}
    for n in VIEWS:
        if n not in T or n not in Cv:
            out['views'][n] = dict(note='view not found')
            continue
        t, c = T[n], Cv[n]
        H, W = t.mask.shape
        Cm = _place(c.mask, s, (c.eye_y, c.axis), H, W, (t.eye_y, t.axis)).astype(bool)
        z = (t.eye_y - np.arange(H)) / t.ppl
        kept = (z >= HEAD_Z) | (z <= LEGS_Z)
        best = (-1.0, 0, 0)
        Tk = t.mask & kept[:, None]
        for dy in range(-8, 9):
            for dx in range(-8, 9):
                v = _iou(Tk, _shift(Cm, dy, dx) & kept[:, None])
                if v > best[0]:
                    best = (v, dy, dx)
        Cm = _shift(Cm, best[1], best[2])
        head, legs = z >= HEAD_Z, z <= LEGS_Z
        band = ~head & ~legs
        Tm = t.mask
        R = Tm & (t.labels == skin) & band[:, None]
        DC = Tm & (t.labels != skin) & band[:, None]
        sc = scores(Cm & band[:, None], R, DC)
        # the most the body stands out of the costume (L): the distance from the turnaround's figure, over the band
        dist = ndimage.distance_transform_edt(~Tm) / t.ppl
        o = Cm & band[:, None] & ~Tm
        rt, rc0 = np.nonzero(Tm.any(1))[0], np.nonzero(c.mask.any(1))[0]
        rec = dict(shift=[best[1], best[2]],
                   kept_iou=dict(head=round(_iou(Tm & head[:, None], Cm & head[:, None]), 4),
                                 legs=round(_iou(Tm & legs[:, None], Cm & legs[:, None]), 4)),
                   # the eye line above the soles, the sheet's against the turnaround's (L at the turnaround's
                   # scale, as refviews.drift's eye_dL): the candidate's own rows, its scale undone
                   eye_over_sole_dL=round(float(((rc0[-1] - c.eye_y) * s - (rt[-1] - t.eye_y)) / t.ppl), 4),
                   protrude_L=round(float(dist[o].max()) if o.any() else 0.0, 4),
                   protrude_p99_L=round(float(np.percentile(dist[o], 99)) if o.sum() > 20 else 0.0, 4), **sc)
        ok = (min(rec['kept_iou'].values()) >= TOL['kept_iou'] and rec['outside'] <= TOL['outside']
              and rec['protrude_L'] <= TOL['protrude_L'] and rec['recall'] >= TOL['recall']
              and abs(rec['eye_over_sole_dL']) <= TOL['eye_L'])
        rec['pass'] = bool(ok)
        out['views'][n] = rec
        imgs[n] = _overlay(Tm, Cm, R, DC)
        log('%-14s kept %s  outside %.4f (most %.3f L)  skin recall %.3f  hidden %.3f  eye/sole %+.4f L  shift %s  %s' % (
            n, rec['kept_iou'], rec['outside'], rec['protrude_L'], rec['recall'], rec['hidden'],
            rec['eye_over_sole_dL'], rec['shift'], 'PASS' if ok else 'FAIL'))
    out['pass'] = bool(abs(s - 1) <= TOL['scale'] and all(v.get('pass') for v in out['views'].values()))
    return out, imgs


def _overlay(Tm, Cm, R=None, DC=None, crop=True):
    """the turnaround's figure against the sheet's layer: grey both, red the sheet only (outside), blue the turnaround
    only; DC (hidden on the turnaround) tinted green, R's misses blue."""
    im = np.full(Tm.shape + (3,), 0.97)
    if DC is not None:
        im[DC & ~Cm] = (0.86, 0.93, 0.86)
        im[DC & Cm] = (0.55, 0.75, 0.55)
    im[Tm & Cm & (R if R is not None else Tm)] = (0.5, 0.5, 0.55)
    im[Cm & ~Tm] = (0.9, 0.15, 0.15)
    if R is not None:
        im[R & ~Cm] = (0.2, 0.35, 0.95)
        im[Cm & Tm & ~R & (~DC if DC is not None else True)] = (0.95, 0.55, 0.2)
    else:
        im[Tm & ~Cm] = (0.2, 0.35, 0.95)
    if crop:
        ys, xs = np.nonzero(Tm | Cm)
        im = im[max(0, ys.min() - 10):ys.max() + 10, max(0, xs.min() - 10):xs.max() + 10]
    return im


# --------------------------------------------------------------------------------------------------------------- clips
def _rows_split(rgb):
    """a two-row sheet cut at the widest empty band of rows in its middle half -> row index."""
    from charkit import sheetqa
    fg = sheetqa.foreground(rgb, sheetqa.background(rgb))
    used = fg.sum(1) > 3
    H = len(used)
    best, cur, start = (0, H // 2), 0, None
    for r in range(H // 4, 3 * H // 4):
        if not used[r]:
            start = r if start is None else start
            cur = r - start + 1
            if cur > best[0]:
                best = (cur, start + cur // 2)
        else:
            start, cur = None, 0
    return best[1]


def _blobs(rgb, min_share=0.05):
    from scipy import ndimage
    from charkit import sheetqa
    fg = sheetqa.foreground(rgb, sheetqa.background(rgb))
    lab, n = ndimage.label(fg)
    if not n:
        return []
    sizes = np.bincount(lab.ravel())[1:]
    keep = [i + 1 for i in np.nonzero(sizes >= min_share * sizes.max())[0]]
    out = []
    for k in keep:
        m = ndimage.binary_fill_holes(lab == k)
        ys, xs = np.nonzero(m)
        col = rgb[m].mean(0)
        out.append(dict(mask=m, box=[int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())], colour=col))
    return sorted(out, key=lambda b: b['box'][0])


def star_arms(m):
    """a star's arm lengths from its centroid (up, down, the sides' mean, the four diagonals' mean) as fractions of its
    height (up + down) -> dict."""
    ys, xs = np.nonzero(m)
    cy, cx = ys.mean(), xs.mean()
    R = {}
    for name, ang in (('up', 0), ('ur', 45), ('right', 90), ('dr', 135), ('down', 180), ('dl', 225), ('left', 270),
                      ('ul', 315)):
        a = np.radians(ang)
        dy, dx = -np.cos(a), np.sin(a)
        r = 0.0
        for t in np.arange(0, max(m.shape), 0.5):
            y, x = int(round(cy + dy * t)), int(round(cx + dx * t))
            if 0 <= y < m.shape[0] and 0 <= x < m.shape[1] and m[y, x]:
                r = t
        R[name] = r
    h = R['up'] + R['down']
    f = lambda v: round(float(v / h), 3) if h else None
    return dict(up=f(R['up']), down=f(R['down']), side=f((R['left'] + R['right']) / 2),
                minor=f((R['ur'] + R['dr'] + R['dl'] + R['ul']) / 4), height_px=round(float(h), 1))


def check_clips(spec, path, log=print):
    from charkit import accqa, bodyqa, eyes as eyelib, refcheck, sheetqa
    from charkit.bodymeasure import load_graph
    ex = eyelib._knobs(spec.get('eyes'))['x']
    fs = spec['ref']['face_sheet']
    pieces = accqa.clip_pieces(load_graph(spec))
    rgb_t = _load(fs['image'])
    DT = accqa.design(rgb_t, ex, pieces, 'head', fs.get('facing', -1))
    HT = refcheck.detect_heads(rgb_t, ex, fs.get('facing', -1))
    ST = accqa.sheet_views(rgb_t, ex, 'head', fs.get('facing', -1))
    rgb = _load(path)
    cut = _rows_split(rgb)
    top, bottom = rgb[:cut], rgb[cut:]
    DC_ = accqa.design(top, ex, pieces, 'head', fs.get('facing', -1))
    HC = refcheck.detect_heads(top, ex, fs.get('facing', -1))
    SC = accqa.sheet_views(top, ex, 'head', fs.get('facing', -1))
    s = HT['ppl'] / HC['ppl']
    fg_t = sheetqa.foreground(top, sheetqa.background(top))
    ey_c = float(np.mean([h['eye_y'] for h in HC['heads'].values()]))
    cls_c = bodyqa.classes(top, fg_t, ey_c, HC['ppl'])[0]
    out = {'kind': 'clips', 'path': os.path.relpath(path, ROOT), 'scale': round(float(s), 4), 'row_cut': int(cut),
           'heads': {}, 'clips': {}, 'tol': TOL}
    imgs = {}
    W = accqa.WIN
    for n in ('front', 'three_quarter', 'profile'):
        if n not in HT['heads'] or n not in HC['heads'] or n not in ST['views'] or n not in SC['views']:
            out['heads'][n] = dict(note='view not found')
            continue
        mt, mc = HT['heads'][n]['_mask'], HC['heads'][n]['_mask']
        ot, oc = ST['views'][n]['eye'], SC['views'][n]['eye']           # (x, y) px: the eyes' middle, the near eye
        H, Wd = mt.shape
        Cm = _place(mc, s, (oc[1], oc[0]), H, Wd, (ot[1], ot[0])).astype(bool)
        Cc = _place(cls_c, s, (oc[1], oc[0]), H, Wd, (ot[1], ot[0]))
        best = (-1.0, 0, 0)
        for dy in range(-8, 9):
            for dx in range(-8, 9):
                v = _iou(mt, _shift(Cm, dy, dx))
                if v > best[0]:
                    best = (v, dy, dx)
        Cm, Cc = _shift(Cm, best[1], best[2]), _shift(Cc, best[1], best[2])
        # the turnaround's clips on its sheet: the window grid's origin sits on the view's eye point
        clip = np.zeros_like(mt)
        y0, x0 = int(round(ot[1] - W['top'] * HT['ppl'])), int(round(ot[0] - W['x'] * HT['ppl']))
        for p, m in DT['views'].get(n, {}).get('masks', {}).items():
            ys, xs = np.nonzero(m)
            ok = (ys + y0 >= 0) & (ys + y0 < H) & (xs + x0 >= 0) & (xs + x0 < Wd)
            clip[ys[ok] + y0, xs[ok] + x0] = True
        found = int(sum(m.sum() for m in DC_['views'].get(n, {}).get('masks', {}).values()))
        hair_ok = np.isin(Cc, [bodyqa.CLASS['hair'], bodyqa.CLASS['line']])
        rec = dict(head_iou=round(best[0], 4), shift=[best[1], best[2]], clips_found_px=found,
                   clips_found_share=round(found / max(1, mc.sum()), 5),
                   hair_fill=round(float((hair_ok & clip).sum() / max(1, clip.sum())), 4), clip_px=int(clip.sum()))
        rec['pass'] = bool(rec['head_iou'] >= TOL['head_iou'] and rec['clips_found_share'] <= TOL['clips_px']
                           and rec['hair_fill'] >= TOL['hair_fill'])
        out['heads'][n] = rec
        im = _overlay(mt, Cm)
        imgs['head_' + n] = _overlay(mt, Cm, crop=True)
        imgs['clipfill_' + n] = _clipfill(top, Cc, clip, mt)
        log('%-14s head IoU %.4f  clips found %d px  hair fill %.3f (%d px)  shift %s  %s' % (
            n, rec['head_iou'], found, rec['hair_fill'], rec['clip_px'], rec['shift'], 'PASS' if rec['pass'] else 'FAIL'))
    # the clips alone: straight on (the wider of each pair) and edge-on, told apart by colour
    B = _blobs(bottom)
    is_yellow = [bool(b['colour'][1] > 0.6 * b['colour'][0] and b['colour'][2] < 0.75 * b['colour'][1]) for b in B]
    yellow = [b for b, y in zip(B, is_yellow) if y]
    red = [b for b, y in zip(B, is_yellow) if not y]
    face = lambda L: max(L, key=lambda b: (b['box'][2] - b['box'][0]) / max(1, b['box'][3] - b['box'][1])) if L else None
    edge = lambda L: min(L, key=lambda b: (b['box'][2] - b['box'][0]) / max(1, b['box'][3] - b['box'][1])) if len(L) > 1 else None
    tm = DT['views'].get('front', {}).get('masks', {})
    pc, ps = accqa.PIECE['crab'], accqa.PIECE['star']
    for kind, L, piece in (('crab', red, pc), ('star', yellow, ps)):
        f, e = face(L), edge(L)
        rec = {'figures': len(L)}
        if f is not None:
            rec['shape_iou'] = {}
            for n in ('front', 'three_quarter', 'profile'):
                m = DT['views'].get(n, {}).get('masks', {}).get(piece)
                if m is not None and m.any():
                    rec['shape_iou'][n] = round(accqa.shape_iou(f['mask'], m), 4)
            ys, xs = np.nonzero(f['mask'])
            rec['w_px'], rec['h_px'] = int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)
            if e is not None:
                ye, xe = np.nonzero(e['mask'])
                rec['edge_thickness_of_height'] = round(float((xe.max() - xe.min() + 1) / rec['h_px']), 3)
            if kind == 'star':
                rec['arms'] = star_arms(f['mask'])
                if tm.get(ps) is not None and tm[ps].any():
                    rec['arms_turnaround_front'] = star_arms(tm[ps])
            rec['pass'] = bool(rec['shape_iou'].get('front', 0) >= TOL['clip_shape'])
            imgs['clip_' + kind] = _clipcmp(f['mask'], DT['views'].get('front', {}).get('masks', {}).get(piece))
        out['clips'][kind] = rec
        log('%-6s %s' % (kind, json.dumps(rec)))
    if 'crab' in out['clips'] and 'star' in out['clips'] and 'w_px' in out['clips']['crab'] and 'h_px' in out['clips']['star']:
        mc_, ms_ = tm.get(pc), tm.get(ps)
        if mc_ is not None and ms_ is not None and mc_.any() and ms_.any():
            wt = np.ptp(np.nonzero(mc_)[1]) + 1
            ht = np.ptp(np.nonzero(ms_)[0]) + 1
            out['clips']['crab_w_over_star_h'] = dict(
                sheet=round(out['clips']['crab']['w_px'] / out['clips']['star']['h_px'], 3),
                turnaround=round(float(wt / ht), 3), note='the turnaround\'s crab is partly under the star')
    out['pass'] = bool(all(v.get('pass') for v in out['heads'].values()))
    out['clips_pass'] = bool(all(v.get('pass') for k, v in out['clips'].items() if isinstance(v, dict) and 'pass' in v))
    return out, imgs


def _clipfill(rgb, Cc, clip, mt):
    from charkit.bodyqa import PALETTE
    im = np.array([[PALETTE.get(int(k), (0.6, 0.6, 0.6)) if k else (0.97, 0.97, 0.95) for k in row] for row in Cc])
    from scipy import ndimage
    edge = clip & ~ndimage.binary_erosion(clip, iterations=2)
    im[edge] = (0.1, 0.4, 1.0)
    ys, xs = np.nonzero(clip)
    if not len(ys):
        return im
    pad = 120
    return im[max(0, ys.min() - pad):ys.max() + pad, max(0, xs.min() - pad):xs.max() + pad]


def _clipcmp(a, b):
    from charkit import accqa
    A = accqa.normalised(a, S=96)
    Bm = accqa.normalised(b, S=96) if b is not None and b.any() else np.zeros_like(A)
    return _overlay(Bm, A)


# --------------------------------------------------------------------------------------------------------------- skirt
def _truth_views(spec, log=print):
    """the turnaround's views on the outfit truth's grids: {view: dict(fg, cls, pieces {piece: may-be mask}, ppl, z)}."""
    from charkit import bodyqa, eyes as eyelib, manifest, outfit, sheetqa
    from scipy import ndimage
    ex = eyelib._knobs(spec.get('eyes'))['x']
    bs = spec['ref']['body_sheet']
    rgb = _load(bs['image'])
    D = sheetqa.detect_figures(rgb, None, ex, bs.get('facing', -1))
    ppl = D['ppl']
    R = manifest.load(spec['ref']['manifest'])['references']
    T, sets, meta = outfit.load_truth(R['outfit_truth']['path'])
    if abs(ppl - meta['ppl']) > 0.05:
        raise ValueError('the sheet calibrates to %.2f px/L, the truth was drawn at %.2f' % (ppl, meta['ppl']))
    DV = bodyqa.design_views(rgb, D, ppl)
    out = {}
    for v, t in T.items():
        dv = DV[v]
        names = sorted({p for s in sets for p in s})
        pieces = {p: np.isin(t, [i for i, s in enumerate(sets) if p in s]) for p in names}
        z = bodyqa.WIN['top'] - (np.arange(t.shape[0]) + 0.5) / ppl
        # the arms and hands: the skin (the turnaround's colour classes: the truth labels only the garments' cells)
        # next to a wrist cuff, across its drawn line; the legs: the rest of the skin below the hips
        none = dv['fg'] & (dv['cls'] == bodyqa.CLASS['skin'])
        lab, n = ndimage.label(none)
        cuffs = np.zeros_like(none)
        for c in HANDS:
            if c in pieces:
                cuffs |= ndimage.binary_dilation(pieces[c], iterations=6)
        ids = np.unique(lab[cuffs & none])
        hands = np.isin(lab, ids[ids > 0])
        for c in HANDS:
            hands |= pieces.get(c, False)
        legs = none & ~hands & (z < -2.4)[:, None]
        pieces.update(hands=hands, legs=legs, unscored=dv['fg'] & (t < 0))     # the truth's drawn lines: no piece
        out[v] = dict(fg=dv['fg'], pieces=pieces, ppl=ppl, z=z, rgb=dv['rgb'], cls=dv['cls'])
    return out


def _fit(R, DC, C, s0, scales=np.arange(0.84, 1.17, 0.02), shift=24, step=3):
    """the layer C (cropped to itself) scaled by 1 / s and placed on R's frame where iou_dc is best: the boxes' tops and
    centres matched, then +-shift px -> (score dict, s, the placed mask)."""
    ys, xs = np.nonzero(R | DC)
    cy, cx = ys.min(), (xs.min() + xs.max()) / 2
    cyc, cxc = np.nonzero(C)
    Cc = C[cyc.min():cyc.max() + 1, cxc.min():cxc.max() + 1]
    H, W = R.shape
    best = None
    for f in scales:
        s = s0 * f
        h, w = int(round(Cc.shape[0] / s)), int(round(Cc.shape[1] / s))
        rr = np.clip((np.arange(h) * s).astype(int), 0, Cc.shape[0] - 1)
        cc = np.clip((np.arange(w) * s).astype(int), 0, Cc.shape[1] - 1)
        Cs = Cc[np.ix_(rr, cc)]
        for dy in range(-shift, shift + 1, step):
            for dx in range(-shift, shift + 1, step):
                a, b = int(cy + dy), int(round(cx - w / 2 + dx))
                P = np.zeros((H, W), bool)
                a0, b0, a1, b1 = max(0, a), max(0, b), min(H, a + h), min(W, b + w)
                if a1 <= a0 or b1 <= b0:
                    continue
                P[a0:a1, b0:b1] = Cs[a0 - a:a1 - a, b0 - b:b1 - b]
                sc = scores(P, R, DC)
                if best is None or sc['iou_dc'] > best[0]['iou_dc']:
                    best = (sc, s, P)
    return best


def check_skirt(spec, path, log=print, keep_masks=None):
    from charkit import bodyqa, sheetqa
    from charkit.geom import hull
    from charkit.refviews import reading_order
    TV = _truth_views(spec, log)
    rgb = _load(path)
    figs, fg = hull.figure_masks(rgb)
    figs = reading_order(figs)
    cls = bodyqa.classes(rgb, fg, -1e9, 1.0)[0]
    garment = np.isin(cls, [bodyqa.CLASS[c] for c in ('orange', 'cream', 'dark')])
    out = {'kind': 'skirt', 'path': os.path.relpath(path, ROOT), 'figures': len(figs), 'layers': {}, 'tol': TOL}
    imgs = {}
    scales = []

    def setup(row, layer, k, v):
        i = row * 4 + k
        if i >= len(figs) or v not in TV:
            return None
        box, m = figs[i]
        C = _layer_mask(garment & m, cls, rgb)
        if keep_masks is not None:
            keep_masks['%s_%s' % (layer, v)] = C
        t = TV[v]
        band = ((t['z'] <= SKIRT_TOP_Z) & (t['z'] >= SKIRT_BOTTOM_Z))[:, None]
        R = np.zeros_like(t['fg'])
        for p in LAYER_PIECES[layer]:
            R |= t['pieces'].get(p, False)
        from scipy import ndimage
        R = ndimage.binary_closing(R, iterations=3) & t['fg'] & band     # the truth's drawn lines between cells
        DC = np.zeros_like(R)
        for p in OCCLUDERS[layer][v]:
            DC |= t['pieces'].get(p, False)
        # the truth's unscored rim round the layer's cells (their drawn outline, 4 px) scores neither way, as
        # outfit.score leaves unscored pixels out (the truth leaves the hair, skin and boots unscored too: only the rim)
        rim = t['pieces']['unscored'] & ndimage.binary_dilation(R, iterations=4)
        DC = (ndimage.binary_closing(DC, iterations=3) | rim) & t['fg'] & band & ~R
        # the search on a window round the turnaround's layer and its occluders (the band, 0.5 L either side)
        yy, xx = np.nonzero(R | DC)
        pad = int(0.5 * t['ppl'])
        win = (slice(max(0, yy.min() - pad), yy.max() + pad), slice(max(0, xx.min() - pad), xx.max() + pad))
        return i, C, t, band, R, DC, win

    # one scale for the sheet (its promise): from the skirt's front and three-quarter, where only the hands hide it
    # (the heights' ratio, then fitted +-16%); every figure is then fitted within +-6% of it
    free = []
    for k, v in ((0, 'front'), (1, 'three_quarter')):
        S_ = setup(0, 'skirt', k, v)
        if S_ is None:
            continue
        i, C, t, band, R, DC, win = S_
        ys, yr = np.nonzero(C.any(1))[0], np.nonzero((R | DC).any(1))[0]
        free.append(_fit(R[win], DC[win], C, (ys[-1] - ys[0]) / max(1, yr[-1] - yr[0]))[1])
    s_c = float(np.median(free))
    out['scale_common'] = round(s_c, 4)
    out['scale_free'] = [round(float(x), 4) for x in free]
    for row, layer in enumerate(('skirt', 'flaps')):
        out['layers'][layer] = {}
        for k, v in enumerate(VIEWS):
            S_ = setup(row, layer, k, v)
            if S_ is None:
                continue
            i, C, t, band, R, DC, win = S_
            sc, s, Pw = _fit(R[win], DC[win], C, s_c, scales=np.arange(0.94, 1.061, 0.02))
            P = np.zeros_like(R)
            P[win] = Pw
            scales.append(s)
            rec = dict(sc, scale=round(float(s), 4), figure=i)
            # the layer's lowest drawn row per column, L under its top on the turnaround (its hem; for the skirt at
            # the back, the hem the flaps hide on the turnaround)
            top_z = t['z'][np.nonzero((P & R).any(1))[0][0]] if (P & R).any() else None
            cols = np.nonzero(P.any(0))[0]
            if top_z is not None and len(cols) > 10:
                low = np.array([t['z'][np.nonzero(P[:, c])[0][-1]] for c in cols])
                mid = low[len(low) // 3: 2 * len(low) // 3]
                rec['hem_below_top_L'] = dict(middle=round(float(top_z - np.median(mid)), 3),
                                              lowest=round(float(top_z - low.min()), 3))
            rec['pass'] = bool(sc['iou_dc'] >= TOL['iou_dc'] and sc['outside'] <= TOL['outside']
                               and sc['recall'] >= TOL['recall'])
            out['layers'][layer][v] = rec
            imgs['%s_%s' % (layer, v)] = _overlay(t['fg'] & band, P, R, DC)
            log('%-6s %-14s iou_dc %.4f  recall %.4f  outside %.4f  hidden %.4f  scale %.3f  %s  %s' % (
                layer, v, sc['iou_dc'], sc['recall'], sc['outside'], sc['hidden'], s, rec.get('hem_below_top_L'),
                'PASS' if rec['pass'] else 'FAIL'))
    med = float(np.median(scales)) if scales else 0.0
    out['scale_spread'] = round(float((max(scales) - min(scales)) / med), 4) if scales else None
    out['pass_by_layer'] = {L: bool(all(r['pass'] for r in V.values())) for L, V in out['layers'].items()}
    out['pass'] = bool(all(out['pass_by_layer'].values()) and out['scale_spread'] is not None
                       and out['scale_spread'] <= TOL['scale_spread'])
    return out, imgs


def _layer_mask(g, cls, rgb=None):
    """a figure's garment pixels as one layer: the fabric (orange, cream) and the dark trim that touches it (not the
    dress form's dark pole), closed over the drawn lines and opened by 4 px (the pole's strip where it meets the hem),
    the components of a fifth of the largest or more, holes filled."""
    from scipy import ndimage
    from charkit.bodyqa import CLASS
    fab = g & np.isin(cls, [CLASS['orange'], CLASS['cream']])
    dark = g & (cls == CLASS['dark'])
    if rgb is not None:                 # the dress form's pole is neutral grey (R - B ~ 0), the trim warm brown (~0.06)
        dark &= (rgb[..., 0] - rgb[..., 2]) > NEUTRAL_RB
    lab, n = ndimage.label(dark)
    ids = np.unique(lab[ndimage.binary_dilation(fab, iterations=3) & dark])
    g = fab | np.isin(lab, ids[ids > 0])
    g = ndimage.binary_opening(ndimage.binary_closing(g, iterations=2), iterations=4)   # the pole's last strip
    lab, n = ndimage.label(g)
    if not n:
        return g
    sizes = np.bincount(lab.ravel())[1:]
    keep = np.nonzero(sizes >= 0.2 * sizes.max())[0] + 1
    return ndimage.binary_fill_holes(np.isin(lab, keep))


# -------------------------------------------------------------------------------------------------------------- bodice
def sheet_views(spec, path, rgb=None, log=print):
    """a sheet in the turnaround's layout on the turnaround's design grids (bodyqa.design_views at the turnaround's ppl
    over the figures' height ratio, as check_body registers a redrawn sheet) -> ({view: dict(fg, cls)}, scale)."""
    from charkit import bodyqa, eyes as eyelib, sheetqa
    from charkit.geom import hull
    ex = eyelib._knobs(spec.get('eyes'))['x']
    bs = spec['ref']['body_sheet']
    T, _ = hull.views_from_sheet(_load(bs['image']), ex, bs.get('facing', -1))
    rgb = _load(path) if rgb is None else rgb
    Cv, _ = hull.views_from_sheet(rgb, ex, bs.get('facing', -1))
    ext = lambda m: np.ptp(np.nonzero(m.any(1))[0])
    s = float(np.median([ext(T[n].mask) / ext(Cv[n].mask) for n in VIEWS if n in T and n in Cv]))
    ppl_t = sheetqa.detect_figures(_load(bs['image']), None, ex, bs.get('facing', -1))['ppl']
    D = sheetqa.detect_figures(rgb, ppl_t / s, ex, bs.get('facing', -1))
    DV = bodyqa.design_views(rgb, D, ppl_t / s)
    return {v: dict(fg=d['fg'], cls=d['cls']) for v, d in DV.items()}, s


def _crop_to(m, shape):
    out = np.zeros(shape, m.dtype)
    h, w = min(shape[0], m.shape[0]), min(shape[1], m.shape[1])
    out[:h, :w] = m[:h, :w]
    return out


def check_bodice(spec, path, log=print, rgb=None):
    from scipy import ndimage
    from charkit import bodyqa
    TV = _truth_views(spec, log)
    SV, s = sheet_views(spec, path, rgb, log)
    out = {'kind': 'bodice', 'path': os.path.relpath(path, ROOT) if os.path.isabs(path) else path, 'scale': round(s, 4),
           'views': {}, 'tol': TOL}
    imgs = {}
    garment = [bodyqa.CLASS[c] for c in ('orange', 'cream', 'dark')]
    skin = [bodyqa.CLASS['skin'], 5]
    for v in VIEWS:
        if v not in TV or v not in SV:
            out['views'][v] = dict(note='view not found')
            continue
        t = TV[v]
        H, W = t['fg'].shape
        fg_c, cls_c = _crop_to(SV[v]['fg'], (H, W)), _crop_to(SV[v]['cls'], (H, W))
        z = t['z']
        head, low = (z >= HEAD_Z)[:, None], (z <= BODICE_LOW_Z)[:, None]
        kept = head | low
        best = (-1.0, 0, 0)
        for dy in range(-8, 9):
            for dx in range(-8, 9):
                q = _iou(t['fg'] & kept, _shift(fg_c, dy, dx) & kept)
                if q > best[0]:
                    best = (q, dy, dx)
        fg_c, cls_c = _shift(fg_c, best[1], best[2]), _shift(cls_c, best[1], best[2])
        band = ~kept
        P = t['pieces']
        layer = np.zeros((H, W), bool)
        for p in BODICE_LAYER:
            layer |= P.get(p, False)
        cover = np.zeros((H, W), bool)
        for p in BODICE_COVER:
            cover |= P.get(p, False)
        R = ndimage.binary_closing(layer, iterations=3) & t['fg'] & band
        cover = ndimage.binary_closing(cover, iterations=3) & t['fg'] & band & ~R
        # the kept pieces in the band (the sleeves, cuffs, hands, hair, the waistband's top) and their drawn rims score
        # neither way: the sheet keeps them as drawn (their silhouettes are the kept parts' business)
        other = np.zeros((H, W), bool)
        for p, m in P.items():
            if p in BODICE_LAYER or p in BODICE_COVER or p in ('none', 'unscored'):
                continue
            other |= m
        hair = t['cls'] == bodyqa.CLASS['hair']
        # where the turnaround's own truth and its colour classes disagree (a cell the truth leaves 'none', the hair's
        # ends or a shadow, that the classes call fabric) neither side is scored
        amb = P.get('none', np.zeros((H, W), bool)) & np.isin(t['cls'], garment)
        E = ndimage.binary_dilation(other | hair | amb, iterations=2) & ~R
        rim = P['unscored'] & ndimage.binary_dilation(R | cover, iterations=4) & ~R
        DC = (cover | rim) & ~E
        S = band & ~E & ~(P['unscored'] & ~R & ~cover)          # (the truth's drawn lines score neither way)
        C = np.isin(cls_c, garment) & fg_c & S
        C = ndimage.binary_opening(ndimage.binary_closing(C, iterations=2), iterations=1) & S
        sc = scores(C, R & S, DC & S)
        rec = dict(shift=[best[1], best[2]],
                   kept_iou=dict(head=round(_iou(t['fg'] & head, fg_c & head), 4),
                                 lower=round(_iou(t['fg'] & low, fg_c & low), 4)), **sc)
        ok = (min(rec['kept_iou'].values()) >= TOL['kept_iou'] and sc['iou_dc'] >= TOL['iou_dc']
              and sc['outside'] <= TOL['outside'] and sc['recall'] >= TOL['recall'])
        if v in ('front', 'three_quarter'):
            mid = int(round(bodyqa.WIN['x'] * t['ppl']))
            xs = (np.arange(W) - mid + 0.5) / t['ppl']
            win = (np.abs(xs) <= V_WIN['x'])[None, :] & ((z <= V_WIN['top']) & (z >= V_WIN['bottom']))[:, None]
            Tv = np.isin(t['cls'], skin) & t['fg'] & win & ~cover
            Cv = np.isin(cls_c, skin) & fg_c & win
            gar_t = np.isin(t['cls'], garment) & win & ~cover
            rec['v'] = dict(recall=round(float((Cv & Tv).sum() / max(1, Tv.sum())), 4),
                            outside=round(float((Cv & gar_t).sum() / max(1, Cv.sum())), 4),
                            under_bow=round(float((Cv & cover).sum() / max(1, Cv.sum())), 4),
                            px=[int(Cv.sum()), int(Tv.sum())])
            rows = np.nonzero(Cv.any(1))[0]
            rows_t = np.nonzero(Tv.any(1))[0]
            rec['v']['lowest_z'] = [round(float(z[rows[-1]]), 3) if len(rows) else None,
                                    round(float(z[rows_t[-1]]), 3) if len(rows_t) else None]
            ok = ok and rec['v']['recall'] >= TOL['v_recall'] and rec['v']['outside'] <= TOL['v_outside']
        rec['pass'] = bool(ok)
        out['views'][v] = rec
        imgs[v] = _overlay(t['fg'] & band, C, R & S, DC & S)
        log('%-14s kept %s  iou_dc %.4f  recall %.4f  outside %.4f  hidden %.4f  V %s  shift %s  %s' % (
            v, rec['kept_iou'], sc['iou_dc'], sc['recall'], sc['outside'], sc['hidden'], rec.get('v'), rec['shift'],
            'PASS' if ok else 'FAIL'))
    out['pass'] = bool(abs(s - 1) <= TOL['scale'] and all(r.get('pass') for r in out['views'].values()))
    return out, imgs


# ---------------------------------------------------------------------------------------------------------------- main
def save_images(imgs, out_dir):
    from PIL import Image
    os.makedirs(out_dir, exist_ok=True)
    files = {}
    for k, a in imgs.items():
        p = os.path.join(out_dir, k + '.png')
        Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).save(p)
        files[k] = p
    return files


def main(args):
    from charkit import manifest
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    spec = manifest.resolve(json.load(open(args[0] if os.path.isabs(args[0]) else os.path.join(ROOT, args[0]))))
    path = os.path.abspath(args[1])
    kind = opt('--kind')
    fn = dict(body=check_body, clips=check_clips, skirt=check_skirt, bodice=check_bodice)[kind]
    rep, imgs = fn(spec, path)
    out = opt('--out', os.path.join(ROOT, 'charkit/out/layerref', os.path.splitext(os.path.basename(path))[0]))
    rep['images'] = {k: os.path.relpath(p, ROOT) for k, p in save_images(imgs, out).items()}
    json.dump(rep, open(os.path.join(out, 'layerref.json'), 'w'), indent=1)
    print('%s: %s' % (kind, 'PASS' if rep['pass'] else 'FAIL'))
    print(os.path.join(out, 'layerref.json'))


if __name__ == '__main__':
    main(sys.argv[1:])
