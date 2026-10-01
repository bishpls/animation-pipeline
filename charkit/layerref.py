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

  top, collar_alone, bow_alone (garments8, 2026-10-01): the bodice kind's measure over LAYERS' table: the top without
         the collar and the bow (bodice_layers redrawn without the collar), and the collar alone and the bow alone each
         worn on base_body_turnaround's bodysuit (the kept parts the head and the legs; the turnaround's other pieces
         scored, the layer read as a cream piece with its stripes)

  collar_ghost, bow_ghost (garments8): one piece alone as worn over the costume by an invisible person, a view per
         blob (GHOSTS: drawn at their own place and scale, each view registered by one joint scale and its own shift;
         the piece drawn over what the turnaround shows in front of it is free, over anything else outside)

    python -m charkit.layerref SPEC SHEET.png --kind body|clips|skirt|bodice|top|collar_alone|bow_alone|collar_ghost|bow_ghost
                                              [--out DIR]
                                              (ghosts: [--views V,.. (the sheet's, left to right)] [--mirror V,..])
    python -m charkit.layerref truths SPEC [--out PATH]      # the manifest's shape_truth masks (build_truths)
    python -m charkit.layerref SPEC SHEET.png --kind edit --cover NAMES [--against REF] [--band z0,z1]
                                              [--revealed NAMES] [--ungraded cover_left] [--grade-views V,..]
    python -m charkit.layerref SPEC SHEET.png --kind alone --piece NAMES --views V,.. [--against REF] [--hidden NAMES]
                                              [--on mannequin|figure|object] [--band z0,z1] [--rows top] [--merge PX]
                                              [--sheet-mask saturated] [--rows bottom] [--scale figure]
                                              [--closing PX] [--main]
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
    return {v: dict(fg=d['fg'], cls=d['cls'], raw=d['raw']) for v, d in DV.items()}, s


def _crop_to(m, shape):
    out = np.zeros(shape, m.dtype)
    h, w = min(shape[0], m.shape[0]), min(shape[1], m.shape[1])
    out[:h, :w] = m[:h, :w]
    return out


# the separated layer sheets in the turnaround's layout (Clawd's: graded on the outfit truth). Per sheet: `layer` the
# pieces it draws (R: their turnaround pixels), `cover` what it leaves out or reveals under (DC: free), `low` the kept
# parts' top below the band (BODICE_LOW_Z: the waistband, skirt, legs and boots kept as drawn; LEGS_Z: only the legs and
# boots, the sheet drawn on base_body_turnaround), `read` how the sheet's layer is read ('garment': its orange, cream
# and dark; 'cream': a cream piece and its stripes, the base body's charcoal bodysuit not), `others` the turnaround's
# other pieces in the band ('kept': drawn on the sheet as they are, scored neither way; 'scored': absent from the
# sheet, so the layer drawn over them stands outside), `v` the V's skin graded (front, three-quarter).
LAYERS = {
    'bodice': dict(layer=BODICE_LAYER, cover=BODICE_COVER, low=BODICE_LOW_Z, read='garment', others='kept', v=True),
    # garments8 (2026-10-01): the top without the collar and the bow (bodice_layers redrawn without the collar)
    'top': dict(layer=('top', 'bodice_panel'), cover=('collar',) + BODICE_COVER, low=BODICE_LOW_Z, read='garment',
                others='kept', v=True),
    # the sailor collar alone, worn on base_body_turnaround's bodysuit (the hair kept in front as drawn)
    'collar_alone': dict(layer=('collar',), cover=BODICE_COVER, low=LEGS_Z, read='cream', others='scored', v=False),
    # the bow alone, worn on base_body_turnaround's bodysuit
    'bow_alone': dict(layer=BODICE_COVER, cover=(), low=LEGS_Z, read='cream', others='scored', v=False),
}
STRIPE_PX = 7                       # read 'cream': the collar's stripes closed into it (px at the turnaround's scale)
SPECK = 0.02                        # layer_pieces: a piece's components under this share of its largest are specks
SPLIT_PX = 2                        # layer_pieces: the cream eroded by this before its components are taken (a lapel's
                                    # tip touches the bodice front's cream through an anti-aliased line)


def _cream_layer(cls_c, fg_c):
    """a sheet's cream piece with its stripes and its drawn lines inside it: the cream (or paler: the colour classes'
    'white', which in the band nothing else is: the boots are kept parts) closed by STRIPE_PX, kept where
    the closing covers dark, line or cream pixels (not skin or the bodysuit's grey: the 'other' or 'none' classes),
    opened by 1 px; components under 1% of the largest dropped."""
    from scipy import ndimage
    from charkit import bodyqa
    cream = fg_c & np.isin(cls_c, [bodyqa.CLASS['cream'], bodyqa.CLASS['white']])    # (drawn paler: 'white')
    ok = np.isin(cls_c, [bodyqa.CLASS[c] for c in ('cream', 'white', 'dark', 'line')])
    C = ndimage.binary_closing(cream, iterations=STRIPE_PX) & fg_c & (ok | cream)
    C = ndimage.binary_opening(C, iterations=1)
    lab, n = ndimage.label(C)
    if n:
        sizes = np.bincount(lab.ravel())[1:]
        C = np.isin(lab, np.nonzero(sizes >= 0.01 * sizes.max())[0] + 1)
    return C


def check_bodice(spec, path, log=print, rgb=None):
    return check_layer(spec, path, 'bodice', log, rgb)


def check_layer(spec, path, kind, log=print, rgb=None, keep_masks=None):
    """a separated layer sheet in the turnaround's layout (LAYERS[kind]) against the turnaround's outfit truth.
    keep_masks: a dict filled with each view's registered layer mask (C, on the outfit truth's grid)."""
    from scipy import ndimage
    from charkit import bodyqa
    K = LAYERS[kind]
    TV = _truth_views(spec, log)
    SV, s = sheet_views(spec, path, rgb, log)
    out = {'kind': kind, 'path': os.path.relpath(path, ROOT) if os.path.isabs(path) else path, 'scale': round(s, 4),
           'views': {}, 'tol': TOL}
    if kind != 'bodice':
        out['layer'] = dict(K)
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
        head, low = (z >= HEAD_Z)[:, None], (z <= K['low'])[:, None]
        kept = head | low
        best = (-1.0, 0, 0)
        for dy in range(-8, 9):
            for dx in range(-8, 9):
                q = _iou(t['fg'] & kept, _shift(fg_c, dy, dx) & kept)
                if q > best[0]:
                    best = (q, dy, dx)
        fg_c, cls_c = _shift(fg_c, best[1], best[2]), _shift(cls_c, best[1], best[2])
        raw_c = _shift(_crop_to(SV[v]['raw'], (H, W)), best[1], best[2]) if 'raw' in SV[v] else None
        band = ~kept
        P = t['pieces']
        layer = np.zeros((H, W), bool)
        for p in K['layer']:
            layer |= P.get(p, False)
        cover = np.zeros((H, W), bool)
        for p in K['cover']:
            cover |= P.get(p, False)
        R = ndimage.binary_closing(layer, iterations=3) & t['fg'] & band
        cover = ndimage.binary_closing(cover, iterations=3) & t['fg'] & band & ~R
        # the kept pieces in the band (the sleeves, cuffs, hands, hair, the waistband's top) and their drawn rims score
        # neither way: the sheet keeps them as drawn (their silhouettes are the kept parts' business); a sheet that
        # draws the layer alone scores the layer over them (others 'scored'), the hair left out (in front on both)
        other = np.zeros((H, W), bool)
        if K['others'] == 'kept':
            for p, m in P.items():
                if p in K['layer'] or p in K['cover'] or p in ('none', 'unscored'):
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
        if K['read'] == 'cream':
            Cf = _cream_layer(cls_c, fg_c) & band & ~E
            C = Cf & S
        else:
            C = np.isin(cls_c, garment) & fg_c & S
            C = ndimage.binary_opening(ndimage.binary_closing(C, iterations=2), iterations=1) & S
            Cf = np.isin(cls_c, garment) & fg_c & band & ~E
            Cf = ndimage.binary_opening(ndimage.binary_closing(Cf, iterations=2), iterations=1) & band & ~E
        if keep_masks is not None:              # (Cfull: the sheet's layer before the truth's lines are left out)
            keep_masks[v] = dict(C=C, Cfull=Cf, R=R & S, DC=DC & S, band=band, shift=[best[1], best[2]], cls=cls_c,
                                 raw=raw_c, fg=fg_c)
        sc = scores(C, R & S, DC & S)
        rec = dict(shift=[best[1], best[2]],
                   kept_iou=dict(head=round(_iou(t['fg'] & head, fg_c & head), 4),
                                 lower=round(_iou(t['fg'] & low, fg_c & low), 4)), **sc)
        ok = (min(rec['kept_iou'].values()) >= TOL['kept_iou'] and sc['iou_dc'] >= TOL['iou_dc']
              and sc['outside'] <= TOL['outside'] and sc['recall'] >= TOL['recall'])
        if K['v'] and v in ('front', 'three_quarter'):
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


def layer_pieces(km, t, layer, cover, min_vote=20):
    """a registered layer sheet's layer (check_layer's keep_masks for one view: C, cls) cut into the layer's pieces by the
    sheet's own colours: its orange is the jacket ('top'); each cream component (the colour classes' cream or paler,
    split by the lines and the stripes) goes to the cream piece (collar, bodice_panel) the outfit truth labels most of
    its pixels where the turnaround shows them (the cover's pixels don't vote), one with fewer than min_vote votes (all
    of it under the cover) to the cream piece it shares the most border with; the collar takes its stripes (the cream
    closed by STRIPE_PX); the rest of the layer (lines, shading) goes to the nearest piece. -> {piece: mask}."""
    from scipy import ndimage
    from charkit import bodyqa
    C, cls = km.get('Cfull', km['C']), km['cls']
    raw = km['raw'] if km.get('raw') is not None else cls
    P = t['pieces']
    cov = np.zeros(C.shape, bool)
    for p in cover:
        cov |= P.get(p, False)
    img = np.full(C.shape, -1)
    if 'top' in layer:
        img[C & (cls == bodyqa.CLASS['orange'])] = layer.index('top')
    creams = [p for p in layer if p != 'top']
    if creams:
        cream = C & np.isin(raw, [bodyqa.CLASS['cream'], bodyqa.CLASS['white']])    # (split by the drawn lines,
        comps, n = ndimage.label(ndimage.binary_erosion(cream, iterations=SPLIT_PX))  # thin necks cut: a lapel's tip)
        if n:
            _, (iy, ix) = ndimage.distance_transform_edt(comps == 0, return_indices=True)
            comps = np.where(cream, comps[iy, ix], 0)
        votes = np.zeros((n + 1, len(creams)))
        for j, p in enumerate(creams):
            m = P.get(p, np.zeros(C.shape, bool)) & ~cov
            votes[:, j] = np.bincount(comps[m], minlength=n + 1)
        lab = np.full(n + 1, -1)
        ok = votes.sum(1) >= min_vote
        lab[ok] = votes[ok].argmax(1)
        lab[0] = -1
        for _ in range(20):                  # unvoted components: the cream piece they border most
            todo = [i for i in range(1, n + 1) if lab[i] < 0]
            if not todo:
                break
            ci = np.where(comps > 0, lab[comps], -1)
            changed = False
            for i in todo:
                ring = ndimage.binary_dilation(comps == i, iterations=STRIPE_PX) & (ci >= 0)
                if ring.any():
                    lab[i] = np.bincount(ci[ring]).argmax()
                    changed = True
            if not changed:
                break
        ci = np.where(comps > 0, lab[comps], -1)
        for j, p in enumerate(creams):
            m = ci == j
            if p == 'collar':                # its stripes and the lines between them
                m = ndimage.binary_closing(m, iterations=STRIPE_PX) & C & (img < 0)
            img[m & (img < 0)] = layer.index(p)
    if (img >= 0).any():                     # the rest of the layer: the nearest piece
        _, (iy, ix) = ndimage.distance_transform_edt(img < 0, return_indices=True)
        img = np.where(C, img[iy, ix], -1)
    out = {}
    for j, p in enumerate(layer):            # specks (a line's anti-aliasing read as fabric) dropped: components under
        m = img == j                         # SPECK of the piece's largest
        lab, n = ndimage.label(m)
        if n > 1:
            sz = np.bincount(lab.ravel())[1:]
            m = np.isin(lab, np.nonzero(sz >= SPECK * sz.max())[0] + 1)
        out[p] = m
    return out


# ghost-mannequin sheets (garments8, 2026-10-01): one piece alone, as worn over the costume by an invisible person, one
# view per blob left to right in the turnaround's view order (the whole drawing is the piece: what the turnaround hides
# of it drawn too). Drawn without a body the piece keeps neither the sheet's place nor its scale (the first takes: 2.3x
# larger, 200 px lower), so each view is registered by a similarity: a scale about the common one (the views' median
# of the turnaround's visible width over the sheet's, searched within GHOST_SCALE of it) and a shift (GHOST_SHIFT L
# round the boxes' middles), coarse at half resolution then fine, where iou_dc is best. Per view: R the turnaround's
# pixels of the piece (the outfit truth), DC what lies in front of it there (`front` pieces; the hair, and the neck's
# skin between `neck_z` and HEAD_Z: the collar's band behind the neck, each within GHOST_NEAR of R), the rest scored: the piece drawn over anything else the
# turnaround shows, or off the figure, stands outside. `hidden_views`: views where the body hides the piece (the bow
# from behind): reported, not graded. The fitted scales' spread is the sheet's one scale (TOL scale_spread).
GHOSTS = {
    'collar_ghost': dict(layer=('collar',), front=BODICE_COVER, neck_z=-0.56, hidden_views=()),
    'bow_ghost': dict(layer=BODICE_COVER, front=(), neck_z=None, hidden_views=('back',)),
}
GHOST_SCALE = 0.20                  # ghost: the per-view scale searched within +-20% of the common one
GHOST_SHIFT = 0.40                  # ghost: L searched either way round the boxes' middles
GHOST_NEAR = 0.10                   # ghost: the hair and the neck count as in front of the piece within this of it (L)


def _ghost_blobs(path, rgb=None, n=4):
    """a ghost sheet's pieces: its foreground's blobs of at least a fifth of the largest, left to right (blobs within
    12 px merged: a piece's parts) -> [mask cropped to its box]."""
    from charkit import bodyqa, sheetqa
    rgb = _load(path) if rgb is None else rgb
    fg = sheetqa.foreground(rgb, sheetqa.background(rgb))
    lab, k = sheetqa.label(bodyqa.dilate(fg, 6))
    if not k:
        return []
    B, area = sheetqa.boxes(lab, k)
    keep = sorted([i for i in range(k) if area[i] >= 0.2 * area.max()], key=lambda i: B[i][0])
    out = []
    for i in keep:
        x0, y0, x1, y1 = [int(v) for v in B[i]]
        m = (fg & (lab == i + 1))[y0:y1 + 1, x0:x1 + 1]
        out.append(m)
    return out


def _box(m):
    ys, xs = np.nonzero(m)
    return ys.min(), ys.max() + 1, xs.min(), xs.max() + 1


class _GhostView:
    """one view's registration of a ghost piece Cb (cropped to its box) on the truth grid round R's box: best(scale)
    the coarse shift (half resolution, GHOST_SHIFT L round the boxes' middles) and its iou_dc; fine(scale, at) the
    full-resolution polish (scale within FINE of it, +-4 px; FFT as best's) -> (score dict, scale, (row, col), the
    placed mask)."""
    FINE = 0.03                 # (the coarse scale step is 0.025: the fine search spans it)

    def __init__(self, Cb, R, DC, S, s0, ppl):
        H, W = R.shape
        self.Cb, self.H, self.W = Cb, H, W
        y0, y1, x0, x1 = _box(R)
        self.cy, self.cx = (y0 + y1) / 2, (x0 + x1) / 2
        self.reach = int(round(GHOST_SHIFT * ppl))
        pad = self.reach + int(max(Cb.shape) * s0 * (1 + GHOST_SCALE)) + 4
        self.wy0, wy1 = max(0, int(self.cy) - pad), min(H, int(self.cy) + pad)
        self.wx0, wx1 = max(0, int(self.cx) - pad), min(W, int(self.cx) + pad)
        Rw, Dw, Sw = (m[self.wy0:wy1, self.wx0:wx1] for m in (R, DC, S))
        self.Rs, self.Ds, self.Sw = Rw & Sw, Dw & Sw & ~Rw, Sw
        self.nR = self.Rs.sum()
        self.Rh, self.Dh, self.Sh = self.Rs[::2, ::2], self.Ds[::2, ::2], Sw[::2, ::2]
        self.nRh = self.Rh.sum()
        self.R, self.DC, self.S = R, DC, S

    def best(self, sc):
        """the best shift at scale sc, at half resolution: every placement's matched and outside pixels at once as
        cross-correlations of the placed piece with R and with the scored rest (FFT), over the +-reach box."""
        from scipy.signal import fftconvolve
        m = _resize_mask(self.Cb, sc / 2).astype(np.float32)
        h, w = m.shape
        oy0 = int(round((self.cy - self.wy0) / 2 - h / 2))
        ox0 = int(round((self.cx - self.wx0) / 2 - w / 2))
        if not hasattr(self, '_fp_img'):
            self._fp_img = (self.Sh & ~self.Rh & ~self.Dh).astype(np.float32)
            self._tp_img = self.Rh.astype(np.float32)
        k = m[::-1, ::-1]
        TP = np.rint(fftconvolve(self._tp_img, k, mode='full'))
        FP = np.rint(fftconvolve(self._fp_img, k, mode='full'))
        r = self.reach // 2
        oy = np.arange(oy0 - r, oy0 + r + 1)          # the piece's top-left rows and columns tried
        ox = np.arange(ox0 - r, ox0 + r + 1)
        iy, ix = oy + h - 1, ox + w - 1                # their indices in the 'full' correlation
        ok_y = (iy >= 0) & (iy < TP.shape[0])
        ok_x = (ix >= 0) & (ix < TP.shape[1])
        oy, ox, iy, ix = oy[ok_y], ox[ok_x], iy[ok_y], ix[ok_x]
        tp, fp = TP[np.ix_(iy, ix)], FP[np.ix_(iy, ix)]
        q = tp / np.maximum(1, self.nRh + fp)
        a, b = np.unravel_index(int(np.argmax(q)), q.shape)
        return float(q[a, b]), 2 * int(oy[a]), 2 * int(ox[b])

    def fine(self, sc0, oy0, ox0):
        from scipy.signal import fftconvolve
        if not hasattr(self, '_fp_full'):
            self._fp_full = (self.Sw & ~self.Rs & ~self.Ds).astype(np.float32)
            self._tp_full = self.Rs.astype(np.float32)
        out = None
        for sc in np.arange(sc0 * (1 - self.FINE), sc0 * (1 + self.FINE) + 1e-9, sc0 * 0.005):
            m = _resize_mask(self.Cb, sc)
            h, w = m.shape
            k = m.astype(np.float32)[::-1, ::-1]
            TP = np.rint(fftconvolve(self._tp_full, k, mode='full'))
            FP = np.rint(fftconvolve(self._fp_full, k, mode='full'))
            # the coarse place, its middle kept as the scale changes, +-4 px
            cy = oy0 + self.Cb.shape[0] * sc0 / 2 - h / 2
            cx = ox0 + self.Cb.shape[1] * sc0 / 2 - w / 2
            oy = np.arange(int(round(cy)) - 4, int(round(cy)) + 5)
            ox = np.arange(int(round(cx)) - 4, int(round(cx)) + 5)
            iy, ix = oy + h - 1, ox + w - 1
            ok_y, ok_x = (iy >= 0) & (iy < TP.shape[0]), (ix >= 0) & (ix < TP.shape[1])
            oy, ox, iy, ix = oy[ok_y], ox[ok_x], iy[ok_y], ix[ok_x]
            q = TP[np.ix_(iy, ix)] / np.maximum(1, self.nR + FP[np.ix_(iy, ix)])
            a_, b_ = np.unravel_index(int(np.argmax(q)), q.shape)
            if out is None or q[a_, b_] > out[0]:
                out = (float(q[a_, b_]), float(sc), int(oy[a_]), int(ox[b_]), m)
        _, sc, oy, ox, m = out
        P = _pad_to(m, self.Rs.shape[0], self.Rs.shape[1], (oy, ox))
        full = np.zeros((self.H, self.W), bool)
        full[self.wy0:self.wy0 + P.shape[0], self.wx0:self.wx0 + P.shape[1]] = P
        return (scores(full & self.S, self.R & self.S, self.DC & self.S), sc,
                (int(oy + self.wy0), int(ox + self.wx0)), full)


def check_ghost(spec, path, kind, log=print, rgb=None, keep_masks=None, given=None, views=VIEWS, mirror=()):
    """a ghost-mannequin sheet (GHOSTS[kind]) against the turnaround's outfit truth. given: [mask per view in `views`'
    order] in place of the sheet's blobs (calibration: the truth's own piece moved, scaled or widened). views: the
    sheet's views left to right (a close-up sheet of three: front, three_quarter, profile); mirror: views drawn turned
    the other way (flipped before fitting). keep_masks: filled with each view's placed mask on the truth's grid."""
    from scipy import ndimage
    from charkit import bodyqa
    K = GHOSTS[kind]
    TV = _truth_views(spec, log)
    blobs = given if given is not None else _ghost_blobs(path, rgb)
    out = {'kind': kind, 'path': os.path.relpath(path, ROOT) if os.path.isabs(path) else path, 'views': {},
           'tol': TOL, 'ghost': dict(K), 'blobs': len(blobs), 'sheet_views': list(views), 'mirror': list(mirror)}
    if len(blobs) != len(views):
        out['pass'] = False
        out['error'] = 'the sheet has %d pieces, %d views given' % (len(blobs), len(views))
        return out, {}
    blobs = [b[slice(*_box(b)[:2]), slice(*_box(b)[2:])] if b.any() else b for b in blobs]
    blobs = [b[:, ::-1] if v in mirror else b for v, b in zip(views, blobs)]
    prep = {}
    for v, Cb in zip(views, blobs):
        t = TV[v]
        H, W = t['fg'].shape
        P = t['pieces']
        layer = np.zeros((H, W), bool)
        for p in K['layer']:
            layer |= P.get(p, False)
        R = ndimage.binary_closing(layer, iterations=3) & t['fg']
        front = np.zeros((H, W), bool)
        for p in K['front']:
            front |= P.get(p, False)
        front = ndimage.binary_closing(front, iterations=3) & t['fg']
        # the hair and the neck in front of the piece only next to it (GHOST_NEAR L): left free everywhere they'd
        # let the fit slide the piece into the head
        near = ndimage.binary_dilation(R, iterations=int(round(GHOST_NEAR * t['ppl'])))
        front |= t['fg'] & (t['cls'] == bodyqa.CLASS['hair']) & near
        if K['neck_z'] is not None:
            zz = t['z'][:, None]
            front |= t['fg'] & (t['cls'] == bodyqa.CLASS['skin']) & (zz >= K['neck_z']) & (zz <= HEAD_Z) & near
        front &= ~R
        rim = P['unscored'] & ndimage.binary_dilation(R | front, iterations=4) & ~R
        DC = front | rim
        S = ~(P['unscored'] & ~R & ~DC)                     # (the truth's drawn lines elsewhere score neither way)
        prep[v] = (t, Cb, R, DC, S)
    # the common scale: the views' median of the turnaround's visible width over the sheet's (graded views)
    ws = [_box(R)[3] - _box(R)[2] for v, (t, Cb, R, DC, S) in prep.items()
          if v not in K['hidden_views'] and R.sum() >= 50]
    wc = [Cb.shape[1] for v, (t, Cb, R, DC, S) in prep.items() if v not in K['hidden_views'] and R.sum() >= 50]
    s0 = float(np.median([a / b for a, b in zip(ws, wc)])) if ws else 1.0
    out['scale0'] = round(s0, 4)
    imgs, scales = {}, []
    # one scale for the sheet: the scale (within GHOST_SCALE of s0) whose views' best shifts sum the highest iou_dc;
    # then each view polished within _GhostView.FINE of it (its own scale reported: the sheet's spread)
    G = {v: _GhostView(Cb, R, DC, S, s0, t['ppl']) for v, (t, Cb, R, DC, S) in prep.items()
         if v not in K['hidden_views'] and R.sum() >= 50}
    joint, every = None, []
    for f in np.arange(1 - GHOST_SCALE, 1 + GHOST_SCALE + 1e-9, 0.025):
        got = {v: g.best(s0 * f) for v, g in G.items()}
        every.append((s0 * f, got))
        tot = sum(q for q, _, _ in got.values())
        if joint is None or tot > joint[0]:
            joint = (tot, s0 * f, got)
    out['scale'] = round(joint[1], 4) if joint else None
    for v, (t, Cb, R, DC, S) in prep.items():
        if v not in G:
            rec = dict(graded=False, px=int(Cb.sum()), note='the body hides the piece here on the turnaround')
            out['views'][v] = rec
            log('%-14s hidden on the turnaround: %d px drawn (sheet px)' % (v, rec['px']))
            continue
        _, oy, ox = joint[2][v]
        sc, k, at, C = G[v].fine(joint[1], oy, ox)
        free = max((got[v] + (sc_,) for sc_, got in every), key=lambda r: r[0])
        scales.append(k)
        if keep_masks is not None:
            keep_masks[v] = dict(C=C, R=R & S, DC=DC & S, scale=k, at=list(at))
        rec = dict(scale=round(k, 4), scale_rel=round(k / joint[1], 4), at=list(at),
                   free_scale_rel=round(free[3] / joint[1], 3), free_iou_dc_half=round(free[0], 4), **sc)
        rec['pass'] = bool(sc['iou_dc'] >= TOL['iou_dc'] and sc['outside'] <= TOL['outside']
                           and sc['recall'] >= TOL['recall'])
        out['views'][v] = rec
        imgs[v] = _overlay(t['fg'] | C, C, R & S, DC & S)
        log('%-14s iou_dc %.4f  recall %.4f  outside %.4f  hidden %.4f  scale %.4f (its own best %.3f of it)  %s' % (
            v, sc['iou_dc'], sc['recall'], sc['outside'], sc['hidden'], k, free[3] / joint[1],
            'PASS' if rec['pass'] else 'FAIL'))
    # the sheet's one scale: the views' own best scales (free, coarse) spread round the joint one
    fr = [r['free_scale_rel'] for r in out['views'].values() if 'free_scale_rel' in r]
    spread = (max(fr) - min(fr)) / float(np.median(fr)) if fr else None
    out['scale_spread'] = None if spread is None else round(spread, 4)
    graded = [r for r in out['views'].values() if r.get('graded', True)]
    out['pass'] = bool(graded and all(r.get('pass') for r in graded))
    out['one_scale'] = bool(spread is not None and spread <= TOL['scale_spread'])
    log('the joint scale %.4f; each view at its own best scale spread %s (reported: a free fit drifts into what the '
        'turnaround hides)  %s' % (joint[1] if joint else float('nan'), out['scale_spread'], 'PASS' if out['pass'] else 'FAIL'))
    return out, imgs


# ------------------------------------------------------------------------------------------------- the shape truths
# A piece's shape truth (Michael, 2026-10-01: each piece's shape truth is its layer without what lies on it; the
# manifest's `shape_truth`, manifest.shape_sheet): the registered layer sheet's piece, cut into the layer's pieces
# (layer_pieces) on the outfit truth's grids, stored as masks VIEW__NAME (charkit/refs/NAME/shape_truth.npz, the
# manifest's reference `shape_truth_masks`), so the QA reads them as it reads the outfit's masks. An entry:
#   {"shape": REF, "kind": a LAYERS or GHOSTS kind, "piece": the truth's piece (default: the entry's name),
#    "views": [...], "without": [the pieces the sheet leaves out: ours is drawn without them to compare],
#    "class": "skin" + "window": the V's skin in V_WIN instead of a piece (the neck's V)}
def build_truths(spec, out=None, log=print):
    """every shape_truth entry's masks -> (path, {name: {view: px}}). Each sheet registered once."""
    from charkit import manifest, bodyqa
    M = manifest.load(spec['ref']['manifest'])
    R = M['references']
    ST = M.get('shape_truth') or {}
    TV = _truth_views(spec, lambda *a: None)
    regs, masks, meta = {}, {}, {}
    for name, e in sorted(ST.items()):
        if not e.get('kind'):                # (a note: the piece is its own truth on the turnaround)
            continue
        sid, kind = e['shape'], e['kind']
        if (sid, kind) not in regs:
            km = {}
            path = os.path.join(ROOT, R[sid]['path'])
            if kind in GHOSTS:
                rep, _ = check_ghost(spec, path, kind, log=lambda *a: None, keep_masks=km)
            else:
                rep, _ = check_layer(spec, path, kind, log=lambda *a: None, keep_masks=km)
            regs[(sid, kind)] = (km, rep)
            log('%s (%s): registered %s' % (sid, kind, {v: r.get('iou_dc') for v, r in rep['views'].items()}))
        km, rep = regs[(sid, kind)]
        meta[name] = {}
        for v in e.get('views') or VIEWS:
            if v not in km:
                continue
            t = TV[v]
            if e.get('class') == 'skin':
                mid = int(round(bodyqa.WIN['x'] * t['ppl']))
                H, W = t['fg'].shape
                xs = (np.arange(W) - mid + 0.5) / t['ppl']
                w = e.get('window') or V_WIN
                win = (np.abs(xs) <= w['x'])[None, :] & ((t['z'] <= w['top']) & (t['z'] >= w['bottom']))[:, None]
                m = np.isin(km[v]['cls'], [bodyqa.CLASS['skin'], 5]) & km[v]['fg'] & win
            elif kind in GHOSTS:
                m = km[v]['C']
            else:
                K = LAYERS[kind]
                m = layer_pieces(km[v], t, K['layer'], K['cover'])[e.get('piece', name)]
            masks['%s__%s' % (v, name)] = m
            meta[name][v] = int(m.sum())
    out = out or os.path.join(os.path.dirname(R['outfit_truth']['path']), 'shape_truth.npz')
    path = out if os.path.isabs(out) else os.path.join(ROOT, out)
    np.savez_compressed(path, **masks)
    return path, meta


def load_truths(spec):
    """the manifest's shape truths: ({name: entry}, {VIEW__NAME: mask}) or ({}, {}) when none are registered."""
    from charkit import manifest
    ref = spec.get('ref') if isinstance(spec.get('ref'), dict) else {}
    if not ref.get('manifest'):
        return {}, {}
    M = manifest.load(ref['manifest'])
    ST, R = M.get('shape_truth') or {}, M['references']
    if not ST or 'shape_truth_masks' not in R:
        return {}, {}
    p = R['shape_truth_masks']['path']
    with np.load(p if os.path.isabs(p) else os.path.join(ROOT, p)) as z:
        return ST, {k: z[k] for k in z.files}


# ---------------------------------------------------------------------------------------------------------------- main
# ------------------------------------------------------------------ any character: edits and pieces alone, by palette
# The kinds above read Clawd's pieces (her clips, skirt, bodice; her bands in L). These two read any character with a
# palette (charkit.palette, the manifest's): the pieces are named by their swatches (a name matches every swatch whose
# name contains it), so a sheet is checked by what it draws, in the character's own colours.
#
#   edit   the turnaround (or head turnaround) redrawn in place with pieces removed (--cover): per view, once registered
#          (a scale within EDIT_SCALE and a shift within EDIT_SHIFT, fitted on what the edit keeps): the kept parts'
#          silhouette IoU outside the cover (kept_iou), the cover's own colours left where it was (cover_left: the share
#          of its pixels still drawn in them), and the edit standing outside the turnaround's silhouette and the cover
#          (outside). --band z0,z1 (L from the eye line) bounds the cover to rows (a beard drawn in the hair's colour).
#   alone  a piece drawn alone (--piece), on a mannequin (--on mannequin: its colour sampled from the mannequin's head)
#          or as an object, in views matched to the authority's (--views, '-' for a view it has no counterpart for):
#          per matched view the piece's shape IoU against its pixels on the authority sheet (--hidden: what covers it
#          there, left out), both brought to one size (the piece's height) and aligned (shape_iou), and its height
#          against the authority's (size: the piece's height over the authority's, at the sheet's own figure scale when
#          the piece is on a mannequin of the figures' height).
EDIT_SCALE = (0.96, 1.04)           # edit: the scale searched (an edit is redrawn in place)
EDIT_SHIFT = 12                     # edit: px searched either way
GEN_TOL = dict(kept_iou=0.90,       # edit: the kept parts' silhouette IoU outside the cover (declared 2026-10-01, before
               cover_left=0.10,     #   any c3 sheet was measured; layerref.TOL's values where one exists)
               outside=0.03,
               revealed=0.30,       # edit with --revealed: the cover's core drawn in what it hid (declared before
                                    #   any sheet was read: a beard's core holds the jaw and neck, and a tunic's neckline)
               shape_iou=0.60,      # alone: the piece's shape (layerref.TOL['clip_shape'])
               size=0.15)           # alone: |height ratio - 1| where the piece shares the figures' scale


def _pal(spec):
    from charkit import palette
    P = palette.active()
    if P is None:
        raise SystemExit('layerref edit/alone: the manifest declares no palette (charkit.palette)')
    return P


def _names_mask(P, k, names):
    """pixels whose nearest swatch's name contains one of names."""
    idx = [i for i, n in enumerate(P.names) if any(x in n for x in names)]
    if not idx:
        raise SystemExit('no swatch named like %s in %s' % (names, P.names))
    return np.isin(k, idx)


def _figures(rgb, min_share=0.15):
    """the sheet's figures or heads: foreground blobs at least min_share the largest, left to right -> [(box, mask)]."""
    from charkit import sheetqa
    fg = sheetqa.foreground(rgb, sheetqa.background(rgb))
    lab, n = sheetqa.label(fg)
    B, area = sheetqa.boxes(lab, n)
    if not n:
        return []
    keep = [i for i in range(n) if area[i] >= min_share * area.max()]
    return [([int(v) for v in B[i]], lab == i + 1) for i in sorted(keep, key=lambda i: B[i][0])]


def _eye_line(rgb, layout, ex):
    """per figure, left to right, its eye line (px) and the sheet's px per L, from the character's detection."""
    from charkit import refcheck, sheetqa
    if layout == 'heads':
        H = refcheck.detect_heads(rgb, ex)
        return [(h['box'], h['eye_y']) for h in sorted(H['heads'].values(), key=lambda h: h['box'][0])], H['ppl']
    D = sheetqa.detect_figures(rgb, None, ex, -1)
    return [(f['box'], f['eye_y']) for f in sorted(D['figures'].values(), key=lambda f: f['box'][0])], D['ppl']


def _crop_fig(m, box, pad=16):
    x0, y0, x1, y1 = box
    return m[max(0, y0 - pad):y1 + pad + 1, max(0, x0 - pad):x1 + pad + 1], (max(0, y0 - pad), max(0, x0 - pad))


def _resize_mask(m, s):
    from PIL import Image
    im = Image.fromarray(m.astype(np.uint8) * 255)
    return np.asarray(im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.NEAREST)) > 127


def _pad_to(m, H, W, at):
    out = np.zeros((H, W), bool)
    y, x = at
    h, w = min(H - y, m.shape[0]), min(W - x, m.shape[1])
    if h > 0 and w > 0:
        out[max(0, y):y + h, max(0, x):x + w] = m[max(0, -y):h, max(0, -x):w]
    return out


def check_edit(spec, path, args=(), log=print):
    """the 'edit' kind (see above). args: --cover NAMES (comma), --against REF (body_turnaround), --band z0,z1."""
    from charkit import bodyqa, eyes as eyelib, manifest
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    P = _pal(spec)
    R = manifest.load(spec['ref']['manifest'])['references']
    against = opt('--against', 'body_turnaround')
    layout = R[against].get('layout', 'figures')
    cover = opt('--cover').split(',')
    band = [float(v) for v in opt('--band').split(',')] if opt('--band') else None
    revealed = opt('--revealed').split(',') if opt('--revealed') else None
    ungraded = opt('--ungraded').split(',') if opt('--ungraded') else ()
    ex = eyelib._knobs(spec.get('eyes'))['x']
    T, S = _load(R[against]['path']), _load(path)
    eT, ppl = _eye_line(T, layout, ex) if band else (None, None)
    rep, imgs = edit_views(T, S, P, cover, band, eT, ppl, log, revealed=revealed, ungraded=ungraded)
    rep.update(sheet=os.path.relpath(path, ROOT), against=against)
    if opt('--grade-views'):                # the cover's removal graded where it faces the viewer (a beard: front and
        gv = opt('--grade-views').split(',')    # three-quarter); the kept parts in every view
        for v, r in rep['views'].items():
            if v not in gv:
                r['pass'] = bool(r['kept_iou'] >= GEN_TOL['kept_iou'] and r['outside'] <= GEN_TOL['outside'])
                r['graded'] = 'kept parts only'
        rep['pass'] = all(r['pass'] for r in rep['views'].values())
    return rep, imgs


def edit_views(T, S, P, cover, band=None, eT=None, ppl=None, log=print, revealed=None, ungraded=()):
    """check_edit's measure on two pictures (the authority T, the edit S) with palette P -> (report, overlays).
    revealed: swatch names the edit should draw where the cover was (reported: the share of the cover's core drawn in
    them); ungraded: measures reported but not graded (cover_left where the cover shares a colour with what it hides:
    a beard over a white tunic's neckline)."""
    from charkit import bodyqa
    kT, kS = P.nearest(T), P.nearest(S)
    fT, fS = _figures(T), _figures(S)
    eT = eT or [(None, None)] * len(fT)
    views = list(VIEWS)[:len(fT)]
    rep = dict(kind='edit', cover=cover, band=band, views={}, revealed=revealed, ungraded=list(ungraded),
               tol={k: GEN_TOL[k] for k in ('kept_iou', 'cover_left', 'outside')})
    imgs = {}
    if len(fS) != len(fT):
        rep['pass'] = False
        rep['error'] = 'the edit has %d figures, the turnaround %d' % (len(fS), len(fT))
        return rep, imgs
    for v, (bt, mt), (bs, ms), (_, ey) in zip(views, fT, fS, eT):
        cov = _names_mask(P, kT, cover) & mt
        if band:
            z = (ey - np.arange(T.shape[0]))[:, None] / ppl
            cov &= (z <= band[1]) & (z >= band[0])
        cov = bodyqa.dilate(cov, 2) & mt
        ct, ot = _crop_fig(mt, bt)
        cc, _ = _crop_fig(cov, bt)
        Hc, Wc = ct.shape
        cs, os_ = _crop_fig(ms, bs)
        kcs, _ = _crop_fig(_names_mask(P, kS, cover) & ms, bs)
        best = None
        for sc in np.arange(EDIT_SCALE[0], EDIT_SCALE[1] + 1e-9, 0.01):
            m = _resize_mask(cs, sc)
            # bottoms and centres aligned, then a shift search
            y0 = (bt[3] - ot[0]) - round((bs[3] - os_[0]) * sc)
            x0 = round((bt[0] + bt[2]) / 2 - ot[1] - ((bs[0] + bs[2]) / 2 - os_[1]) * sc)
            for dy in range(-EDIT_SHIFT, EDIT_SHIFT + 1, 2):
                for dx in range(-EDIT_SHIFT, EDIT_SHIFT + 1, 2):
                    mm = _pad_to(m, Hc, Wc, (y0 + dy, x0 + dx))
                    k = _iou(mm & ~cc, ct & ~cc)
                    if best is None or k > best[0]:
                        best = (k, sc, y0 + dy, x0 + dx)
        k, sc, yy, xx = best
        mm = _pad_to(_resize_mask(cs, sc), Hc, Wc, (yy, xx))
        kc = _pad_to(_resize_mask(kcs, sc), Hc, Wc, (yy, xx))
        core = bodyqa.erode(cc, 2) & ~bodyqa.dilate(ct & ~cc, 1)
        left = float((kc & core).sum() / max(1, core.sum()))
        outside = float((mm & ~ct & ~cc).sum() / max(1, mm.sum()))
        rec = dict(kept_iou=round(k, 4), cover_left=round(left, 4), outside=round(outside, 4), scale=round(float(sc), 3),
                   cover_share=round(float(cc.sum() / max(1, ct.sum())), 4))
        if revealed:
            rv, _ = _crop_fig(_names_mask(P, kS, revealed) & ms, bs)
            rv = _pad_to(_resize_mask(rv, sc), Hc, Wc, (yy, xx))
            rec['revealed'] = round(float((rv & core).sum() / max(1, core.sum())), 4)
        rec['pass'] = bool(rec['kept_iou'] >= GEN_TOL['kept_iou'] and rec['outside'] <= GEN_TOL['outside']
                           and ('cover_left' in ungraded or rec['cover_left'] <= GEN_TOL['cover_left'])
                           and (not revealed or rec['revealed'] >= GEN_TOL['revealed']))
        rep['views'][v] = rec
        log('%s: kept %.3f cover left %.3f outside %.3f scale %.2f %s' % (v, k, left, outside, sc,
                                                                           'PASS' if rec['pass'] else 'FAIL'))
        imgs['edit_' + v] = _overlay(ct, mm, R=None, DC=cc, crop=False)
    rep['pass'] = all(r['pass'] for r in rep['views'].values())
    return rep, imgs


def check_alone(spec, path, args=(), log=print):
    """the 'alone' kind (see above). args: --piece NAMES, --against REF, --views v1,v2,.. ('-': none),
    --hidden NAMES, --on mannequin|object, --band z0,z1 (on the authority, L from its eye line), --rows top|all."""
    from charkit import bodyqa, eyes as eyelib, manifest
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    P = _pal(spec)
    R = manifest.load(spec['ref']['manifest'])['references']
    against = opt('--against', 'body_turnaround')
    layout = R[against].get('layout', 'figures')
    piece = opt('--piece').split(',')
    hidden = opt('--hidden').split(',') if opt('--hidden') else []
    on = opt('--on', 'object')
    band = [float(v) for v in opt('--band').split(',')] if opt('--band') else None
    want = opt('--views').split(',')
    ex = eyelib._knobs(spec.get('eyes'))['x']
    T, S = _load(R[against]['path']), _load(path)
    kT, kS = P.nearest(T), P.nearest(S)
    eT, ppl = _eye_line(T, layout, ex)
    fT = _figures(T)
    tv = dict(zip(VIEWS, zip(fT, eT)))
    smask = opt('--sheet-mask')             # 'saturated': the sheet draws the piece in coded colours (a breakdown)
    from charkit.bodyqa import _hsv
    sat = (lambda im: (_hsv(im)[1] > 0.3) & (_hsv(im)[2] > 0.3)) if smask == 'saturated' else None
    if on in ('mannequin', 'figure'):       # figure: the sheet's own figures, nothing excluded (a breakdown's heads)
        figs = _figures(S)
    else:                                   # objects: the piece's own blobs (--merge N: blobs N px apart are one)
        from charkit import sheetqa
        pm = sat(S) if sat else _names_mask(P, kS, piece)
        pm = bodyqa.dilate(pm, 2 + int(opt('--merge', 0)))
        lab, n = sheetqa.label(pm)
        B, area = sheetqa.boxes(lab, n)
        keep = [i for i in range(n) if area[i] >= 0.1 * area.max()] if n else []
        figs = [([int(v) for v in B[i]], lab == i + 1) for i in sorted(keep, key=lambda i: B[i][0])]
    if opt('--rows') in ('top', 'bottom') and figs:     # one row of the sheet: its topmost or bottommost figures
        if opt('--rows') == 'top':
            top = min(b[1] for b, _ in figs)
            h0 = max(b[3] - b[1] for b, _ in figs if b[1] - top < 40)
            figs = [f for f in figs if f[0][1] - top < 0.3 * h0]
        else:
            bot = max(b[3] for b, _ in figs)
            h0 = max(b[3] - b[1] for b, _ in figs if bot - b[3] < 40)
            figs = [f for f in figs if bot - f[0][3] < 0.3 * h0]
    rep = dict(kind='alone', sheet=os.path.relpath(path, ROOT), against=against, piece=piece, hidden=hidden, on=on,
               band=band, figures=len(figs), views={}, tol={k: GEN_TOL[k] for k in ('shape_iou', 'size')})
    imgs = {}
    for v, (bs, ms) in zip(want, figs):
        if v == '-' or v not in tv:
            continue
        (bt, mt), (_, ey) = tv[v]
        pt = _names_mask(P, kT, piece) & mt
        if band:
            z = (ey - np.arange(T.shape[0]))[:, None] / ppl
            pt &= (z <= band[1]) & (z >= band[0])
        dc = (_names_mask(P, kT, hidden) & mt) if hidden else np.zeros_like(mt)
        ps = (sat(S) if sat else _names_mask(P, kS, piece)) & ms
        if on == 'mannequin':                # the mannequin's own colours (its bare head and feet, lit and shaded) are
            x0, y0, x1, y1 = bs              # not the piece
            from charkit.palette import lab as tolab
            L = tolab(S)
            hh = max(4, (y1 - y0) // 12)
            for ya, yb in ((y0, y0 + hh), (y1 - hh, y1 + 1)):
                cut = L[ya:yb, x0:x1 + 1][ms[ya:yb, x0:x1 + 1]]
                if len(cut):
                    for q in (25, 50, 75):           # its lit, mid and shaded greys
                        col = np.percentile(cut, q, axis=0)
                        ps &= np.sqrt(((L - col) ** 2).sum(-1)) > 8
        ps = bodyqa.dilate(bodyqa.erode(ps, 1), 1)
        pt = bodyqa.dilate(bodyqa.erode(pt, 1), 1)
        cl = int(opt('--closing', 0))               # fill a piece's shading (its shadow tones read as other colours)
        if cl:
            ps, pt = (bodyqa.erode(bodyqa.dilate(m, cl), cl) & (ms if m is ps else mt) for m in (ps, pt))
        if '--main' in args:                        # the piece's main blob on each side (stray specks of its colours)
            from charkit import sheetqa
            def main_blob(m):
                lab, n = sheetqa.label(m)
                if not n:
                    return m
                _, area = sheetqa.boxes(lab, n)
                return lab == int(np.argmax(area)) + 1
            ps, pt = main_blob(ps), main_blob(pt)
        if pt.sum() < 50 or ps.sum() < 50:
            rep['views'][v] = dict(note='too few pixels', px_sheet=int(ps.sum()), px_authority=int(pt.sum()))
            continue
        yt, xt = np.nonzero(pt); ys, xs = np.nonzero(ps)
        ht, hs = np.ptp(yt) + 1, np.ptp(ys) + 1
        size = None
        fs = (bt[3] - bt[1]) / max(1, bs[3] - bs[1])           # the figures' scale (sheet to authority)
        if on == 'mannequin':                # the figures share a scale: compare the piece's height at the figures'
            size = round(float(hs * fs / ht), 4)
        H, W = T.shape[:2]
        if opt('--scale') == 'figure':       # the whole figure's scale and place (a breakdown drawn in the figure's
            sc = fs                          # frame: the piece's own extent may differ, a band may cut it)
            m = _resize_mask(ps[bs[1]:bs[3] + 1, bs[0]:bs[2] + 1], sc)
            cy, cx = bt[1], int(round((bt[0] + bt[2]) / 2 - m.shape[1] / 2))
        else:
            sc = ht / hs
            m = _resize_mask(ps[ys.min():ys.max() + 1, xs.min():xs.max() + 1], sc)
            cy, cx = yt.min(), int(np.mean(xt) - np.nonzero(m)[1].mean())
        best = None
        for dy in range(-8, 9, 2):
            for dx in range(-12, 13, 2):
                mm = _pad_to(m, H, W, (cy + dy, cx + dx))
                sc_ = scores(mm, pt & ~dc, dc)
                if best is None or sc_['iou_dc'] > best[0]['iou_dc']:
                    best = (sc_, mm)
        rec = dict(shape_iou=best[0]['iou_dc'], recall=best[0]['recall'], outside=best[0]['outside'],
                   height_px=[int(hs), int(ht)], size=size)
        rec['pass'] = bool(rec['shape_iou'] >= GEN_TOL['shape_iou'] and (size is None or abs(size - 1) <= GEN_TOL['size']))
        rep['views'][v] = rec
        log('%s: shape %.3f size %s %s' % (v, rec['shape_iou'], size, 'PASS' if rec['pass'] else 'FAIL'))
        x0, y0, x1, y1 = bt
        sl = (slice(max(0, y0 - 10), y1 + 10), slice(max(0, x0 - 10), x1 + 10))
        imgs['alone_' + v] = _overlay(pt[sl], best[1][sl], R=None, DC=dc[sl], crop=False)
    graded = [r for r in rep['views'].values() if 'pass' in r]
    rep['pass'] = bool(graded) and all(r['pass'] for r in graded)
    return rep, imgs


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
    if args and args[0] == 'truths':                 # python -m charkit.layerref truths SPEC [--out PATH]
        spec = manifest.resolve(json.load(open(args[1] if os.path.isabs(args[1]) else os.path.join(ROOT, args[1]))))
        path, meta = build_truths(spec, opt('--out'))
        print(json.dumps(meta, indent=1))
        print(path)
        return
    spec = manifest.resolve(json.load(open(args[0] if os.path.isabs(args[0]) else os.path.join(ROOT, args[0]))))
    path = os.path.abspath(args[1])
    kind = opt('--kind')
    if kind in ('edit', 'alone'):
        rep, imgs = dict(edit=check_edit, alone=check_alone)[kind](spec, path, args)
    else:
        fn = dict(body=check_body, clips=check_clips, skirt=check_skirt, bodice=check_bodice).get(kind)
        gv = dict(views=opt('--views').split(','), mirror=(opt('--mirror') or '').split(',')) if opt('--views') else {}
        rep, imgs = fn(spec, path) if fn else check_ghost(spec, path, kind, **gv) if kind in GHOSTS else \
            check_layer(spec, path, kind)
    out = opt('--out', os.path.join(ROOT, 'charkit/out/layerref', os.path.splitext(os.path.basename(path))[0]))
    rep['images'] = {k: os.path.relpath(p, ROOT) for k, p in save_images(imgs, out).items()}
    json.dump(rep, open(os.path.join(out, 'layerref.json'), 'w'), indent=1)
    print('%s: %s' % (kind, 'PASS' if rep['pass'] else 'FAIL'))
    print(os.path.join(out, 'layerref.json'))


if __name__ == '__main__':
    main(sys.argv[1:])
