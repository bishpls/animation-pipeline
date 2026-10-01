"""The outfit graph for a character without a hand-built 2D rig (any but Clawd): from its manifest's palette and declared
pieces and its sheets, in charkit.outfit's format (outfit_graph.json beside outfit_masks.npz), so the hull's carving and
labels (charkit.geom.hull) and the authored body (charkit.bodypage, code_body) read it unchanged. charkit.outfit reads
Clawd's 2D rig (its layers and joints) and her notes; a second character has neither, and the producer failed at load_rig
(2026-09-30). A manifest whose `outfit_masks` entry says `produced_by: charkit.outfit_sheet` uses this instead.

  pieces    the manifest's `pieces`: [{"id", "type", "swatches": [names], "bone", "zone": [bones], "side": "C" | "split",
            "motion", "parent"?, "over"?: [ids]}]: a character description (which of its palette's colours draw which
            piece, the bones it is worn over; a 'split' piece is cut into _L and _R at each view's axis). Hair, skin
            and the iris are not pieces. A piece takes its swatches' aliases (ALIAS: one colour on a drawing) within
            its zone's heights; a rigid piece only its compact blobs.
  masks     per view of the body sheet (bodyqa.design_views grids, keys VIEW__PIECE): the figure's pixels whose nearest
            swatch is one of the piece's own; a piece drawn in the hair's colour (palette.SHARED) keeps the garment side
            of bodyqa.classes' split (regions centred below the shoulders); specks under MIN_PX dropped
  skeleton  from the front figure of the base body sheet (the manifest's base_body_turnaround when registered, else the
            body sheet): measured are the shoulder line (the body run widening past the head's width), the arms'
            parting (where they leave the torso), the waist (the torso's narrowest between), the crotch (where the legs
            part), the soles, the arms' and legs' centre lines; the chin, the neck's base and the shoulder joints are
            placed between those by figure-drawing proportions (SK). Bones are
            VRM's names, front-view segments in L from the eye line, x toward the character's left (image right)
  extents   per piece and view: its bbox, area and pixel count in L (the view's grid frame: bodyqa.design_views')

    python -m charkit.outfit_sheet SPEC [--out DIR]
"""
import json, math, os, sys, time

import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(ROOT)
VIEWS = ('front', 'three_quarter', 'profile', 'back')
MIN_PX = 30
# figure-drawing proportions for what the front silhouette doesn't show (as fractions between measured rows; checked
# against Clawd's rig-placed skeleton: chin 0.43 of the eye line to the shoulder line, -0.383 L against her -0.383)
SK = dict(shoulder_w=1.9,       # the shoulder line: the first row below the head whose body run is this many head widths
          chin=0.5,             # the chin: this share of the way from the eye line down to the shoulder line
          neck_base=0.92,       # the neck's base: this share of the way from the eye line to the shoulder line
          shoulder_down=0.25,   # the shoulder joint: this share down from the shoulder line toward the arms' parting
          elbow=0.42, wrist=0.76,           # along the arm's centre line, shoulder joint to fingertip
          leg_top=0.08,         # the hip joints: this share up from the crotch toward the waist
          knee=0.48,            # along the leg, hip joint (0) to ankle (1)
          ankle=0.045)          # the ankle: this share of the figure's height above the soles


def _p(p):
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def _runs(row, gap=3, min_w=4):
    """a bool row's runs -> [(c0, c1)] inclusive; runs `gap` px apart or less are one (a drawn stroke inside the figure
    reads as a gap), runs under min_w px are dropped (specks)."""
    d = np.diff(np.r_[0, row.astype(np.int8), 0])
    s, e = np.nonzero(d == 1)[0], np.nonzero(d == -1)[0] - 1
    out = []
    for a, b in zip(s.tolist(), e.tolist()):
        if out and a - out[-1][1] - 1 <= gap:
            out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return [r for r in out if r[1] - r[0] + 1 >= min_w]


def skeleton_front(mask, eye, ppl):
    """the skeleton from a front figure's silhouette (bool image, the sheet's pixels), its eyes' middle (px) and scale
    -> ({bone: ((x, z), (x, z))} in L, the measured rows {name: z L})."""
    ex, ey = eye
    to = lambda px, py: (round((px - ex) / ppl, 4), round((ey - py) / ppl, 4))
    ys = np.nonzero(mask.any(1))[0]
    top, sole = int(ys[0]), int(ys[-1])
    cx = ex

    def body_run(rs):
        """the run containing the axis, else None (between the legs)."""
        for a, b in rs:
            if a <= cx <= b:
                return (a, b)
        return None
    # the shoulder line: the first row below the head whose body run is shoulder_w head widths (the head's at the eyes)
    hw = (lambda b: b[1] - b[0] + 1)(body_run(_runs(mask[int(ey)])) or (0, ppl))
    shoulder = next((r for r in range(int(ey + 0.3 * ppl), sole) for b in [body_run(_runs(mask[r]))]
                     if b and b[1] - b[0] + 1 >= SK['shoulder_w'] * hw), None)
    if shoulder is None:
        raise RuntimeError('outfit_sheet: no shoulder line on the front figure')
    # the armpits (where the arms part from the body): the first rows where a run stands apart on each side
    armpit = None
    for r in range(shoulder, sole):
        rs = _runs(mask[r])
        b = body_run(rs)
        if b and any(c1 < b[0] for c0, c1 in rs) and any(c0 > b[1] for c0, c1 in rs):
            if all(body_run(_runs(mask[r + k])) for k in range(1, 4)):
                armpit = r
                break
    if armpit is None:
        raise RuntimeError('outfit_sheet: no armpits on the front figure (arms not apart from the body)')
    # the crotch: going up from the soles, the last row where the axis lies between two runs (the legs)
    crotch = None
    for r in range(sole - int(0.3 * ppl), armpit, -1):
        rs = _runs(mask[r])
        if body_run(rs) is None and any(c1 < cx for c0, c1 in rs) and any(c0 > cx for c0, c1 in rs):
            continue
        crotch = r + 1
        break
    if crotch is None or crotch >= sole:
        raise RuntimeError('outfit_sheet: no crotch on the front figure')
    # the waist: the body run's narrowest between the armpits and the crotch (its middle half)
    a0, a1 = armpit + (crotch - armpit) // 4, crotch - (crotch - armpit) // 4
    widths = [(b[1] - b[0], r) for r in range(a0, a1) for b in [body_run(_runs(mask[r]))] if b]
    waist = min(widths)[1] if widths else (armpit + crotch) // 2
    # the arms' centre lines: from the armpits down, the run outside the body's (legs' below the crotch) on each side
    arms = {}
    for side in (-1, 1):                                   # image left (her right), image right (her left)
        pts, prev = [], None
        for r in range(armpit, sole + 1):
            rs = _runs(mask[r])
            b = body_run(rs)
            if b is None:                                  # below the crotch: the legs straddle the axis
                inner = [q for q in rs if (q[1] < cx if side < 0 else q[0] > cx)]
                inner = sorted(inner, key=lambda q: abs((q[0] + q[1]) / 2 - cx))
                limit = inner[0] if inner else None
            else:
                limit = b
            if limit is None:
                break
            out = [q for q in rs if (q[1] < limit[0] if side < 0 else q[0] > limit[1])]
            if not out:
                break
            q = min(out, key=lambda q: abs((q[0] + q[1]) / 2 - prev)) if prev is not None else \
                (max(out, key=lambda q: q[1]) if side < 0 else min(out, key=lambda q: q[0]))
            prev = (q[0] + q[1]) / 2
            pts.append((prev, r))
        if len(pts) < 5:
            raise RuntimeError('outfit_sheet: no %s arm on the front figure' % ('right' if side < 0 else 'left'))
        arms[side] = np.array(pts, float)
    # the legs' centre lines: the two runs straddling the axis below the crotch
    legs = {-1: [], 1: []}
    for r in range(crotch, sole + 1):
        rs = _runs(mask[r])
        for side in (-1, 1):
            q = [x for x in rs if (x[1] < cx if side < 0 else x[0] > cx)]
            if q:
                q = min(q, key=lambda x: abs((x[0] + x[1]) / 2 - cx))
                legs[side].append(((q[0] + q[1]) / 2, r))
    Z = {k: (ey - v) / ppl for k, v in dict(top=top, shoulder=shoulder, armpit=armpit, waist=waist, crotch=crotch,
                                             sole=sole).items()}
    chin = SK['chin'] * Z['shoulder']
    neck_base = SK['neck_base'] * Z['shoulder']
    chest_top = (Z['shoulder'] + Z['armpit']) / 2
    leg_top = Z['crotch'] + SK['leg_top'] * (Z['waist'] - Z['crotch'])
    mid = (Z['waist'] + leg_top) / 2
    ankle = Z['sole'] + SK['ankle'] * (Z['top'] - Z['sole'])
    x0 = round((cx - ex) / ppl, 4)
    sk = {'head': ((x0, round(chin, 4)), (x0, round(Z['top'], 4))),
          'neck': ((x0, round(neck_base, 4)), (x0, round(chin, 4))),
          'upperChest': ((x0, round(chest_top, 4)), (x0, round(neck_base, 4))),
          'chest': ((x0, round(Z['waist'], 4)), (x0, round(chest_top, 4))),
          'spine': ((x0, round(mid, 4)), (x0, round(Z['waist'], 4))),
          'hips': ((x0, round(leg_top, 4)), (x0, round(mid, 4)))}
    for side, name in ((-1, 'right'), (1, 'left')):
        A = arms[side]
        # the shoulder joint: the arm's centre line (its first 0.6 L) carried up above the armpits
        n = max(3, int(np.sum(A[:, 1] < armpit + 0.6 * ppl)))
        fit = np.polyfit(A[:n, 1], A[:n, 0], 1)
        jz = Z['shoulder'] + SK['shoulder_down'] * (Z['armpit'] - Z['shoulder'])
        jy = ey - jz * ppl
        J = np.array([np.polyval(fit, jy), jy])
        poly = np.vstack([J, A])
        seg = np.r_[0, np.cumsum(np.hypot(*np.diff(poly, axis=0).T))]
        at = lambda t: (np.interp(t * seg[-1], seg, poly[:, 0]), np.interp(t * seg[-1], seg, poly[:, 1]))
        el, wr, tip = at(SK['elbow']), at(SK['wrist']), at(1.0)
        root = (x0, round(neck_base, 4))
        sk[name + 'Shoulder'] = (root, to(*J))
        sk[name + 'UpperArm'] = (to(*J), to(*el))
        sk[name + 'LowerArm'] = (to(*el), to(*wr))
        sk[name + 'Hand'] = (to(*wr), to(*tip))
        Lg = np.array(legs[side], float)
        if len(Lg) >= 5:
            fit = np.polyfit(Lg[:, 1], Lg[:, 0], 1)
            yt, ya = ey - leg_top * ppl, ey - ankle * ppl
            ht, an = (np.polyval(fit, yt), yt), (np.polyval(fit, ya), ya)
            kn = (ht[0] + SK['knee'] * (an[0] - ht[0]), ht[1] + SK['knee'] * (an[1] - ht[1]))
            sk[name + 'UpperLeg'] = (to(*ht), to(*kn))
            sk[name + 'LowerLeg'] = (to(*kn), to(*an))
            sk[name + 'Foot'] = (to(*an), to(an[0], sole))
    return sk, {k: round(v, 4) for k, v in Z.items()}


def _sheet(path, eye_x):
    from PIL import Image
    from . import sheetqa
    rgb = np.asarray(Image.open(_p(path)).convert('RGB')).astype(float) / 255
    D = sheetqa.detect_figures(rgb, None, eye_x, -1)
    return rgb, D


ALIAS = 8.0                 # Lab distance: swatches this close are one colour on a drawing (a tunic's white and the
                            # hair's, sandals' brown and the eye's): a piece takes its swatches' aliases, and its zone
                            # (the bones it is worn over) says which pixels of the shared colour are its own
ZONE_PAD = 0.35             # L: a zone's heights reach this far past its bones' ends


def zone_band(sk, bones):
    """the heights (z0, z1) in L a piece's zone covers: its bones' segments (a name without a side takes both sides),
    padded by ZONE_PAD; None when the zone names no known bone."""
    zs = []
    for b in bones or ():
        for name, seg in sk.items():
            if name == b or name[0].lower() + name[1:] == b or name.endswith(b[0].upper() + b[1:]):
                zs += [seg[0][1], seg[1][1]]
    return (min(zs) - ZONE_PAD, max(zs) + ZONE_PAD) if zs else None


def piece_masks(design, pieces, P, sk=None):
    """per view and piece its mask on the view's grid -> {VIEW__ID: bool}; a 'split' piece as ID_L and ID_R."""
    from .bodyqa import CLASS, dilate, erode
    out = {}
    from .palette import lab as tolab
    own_of = {pc['id']: [i for i, n in enumerate(P.names) if n in pc['swatches']] for pc in pieces}
    bands = {pc['id']: zone_band(sk or {}, pc.get('zone')) for pc in pieces}
    body = [i for i, r in enumerate(P.roles) if r in ('skin', 'skin_shade', 'hair', 'hair_shade')]
    for vn, dv in design.items():
        Lv = tolab(dv['rgb'])
        fg = dv['fg']
        H, W = fg.shape
        u = (np.arange(W) + 0.5) / dv['ppl'] - dv['win']['x']
        z = dv['win']['top'] - (np.arange(H) + 0.5) / dv['ppl']
        for pc in pieces:
            own = own_of[pc['id']]
            idx = sorted({j for i in own for j in range(len(P.names)) if np.linalg.norm(P.lab[i] - P.lab[j]) < ALIAS})
            # what can be drawn at its heights: its own colours, the pieces whose zones meet its zone, skin and hair
            b0 = bands[pc['id']]
            rivals = set(body)
            for q in pieces:
                bq = bands[q['id']]
                if q['id'] != pc['id'] and (b0 is None or bq is None or (bq[0] <= b0[1] and b0[0] <= bq[1])):
                    rivals |= set(own_of[q['id']])
            k = P.nearest_among(Lv, sorted(set(idx) | rivals))
            m = np.isin(k, idx) & fg
            if any(P.reads[i] in ('hair', 'hair_shade') for i in idx):
                m &= dv['cls'] != CLASS['hair']             # the garment side of the hair split
            band = zone_band(sk or {}, pc.get('zone'))
            if band:
                m &= ((z >= band[0]) & (z <= band[1]))[:, None]
            if pc.get('motion') == 'rigid':                 # a rigid piece is compact: no fold lines of its colours
                m = dilate(erode(m, 2), 2) & m
                m = _despeck(m, rel=0.25)
            m = _despeck(m)
            if pc.get('side') == 'split':
                left = (u > 0) if vn != 'back' else (u < 0)   # the character's left: image right, mirrored in the back
                if vn == 'profile':                           # the profile (facing the viewer's left) shows the left
                    out['%s__%s_L' % (vn, pc['id'])] = m
                    out['%s__%s_R' % (vn, pc['id'])] = np.zeros_like(m)
                    continue
                out['%s__%s_L' % (vn, pc['id'])] = m & left[None, :]
                out['%s__%s_R' % (vn, pc['id'])] = m & ~left[None, :]
            else:
                out['%s__%s' % (vn, pc['id'])] = m
    return out


def _despeck(m, rel=0.0):
    """components under MIN_PX (and under rel times the largest) dropped."""
    from .sheetqa import boxes, label
    lab, n = label(m)
    if not n:
        return m
    _, area = boxes(lab, n)
    keep = np.r_[False, (area >= MIN_PX) & (area >= rel * area.max())]
    return keep[lab]


def extent(m, dv):
    if not m.any():
        return None
    ys, xs = np.nonzero(m)
    ppl, win = dv['ppl'], dv['win']
    x = (xs + 0.5) / ppl - win['x']
    z = win['top'] - (ys + 0.5) / ppl
    return dict(bbox=[round(float(x.min()), 4), round(float(z.min()), 4), round(float(x.max()), 4),
                      round(float(z.max()), 4)], area=round(float(m.sum() / ppl ** 2), 4), px=int(m.sum()))


def build(spec, out, log=print):
    """the graph and masks for a resolved spec into out -> (graph, paths)."""
    from . import bodyqa, eyes as eyelib, manifest, palette
    P = palette.active()
    if P is None:
        raise SystemExit('outfit_sheet: the manifest declares no palette (charkit.palette)')
    M = manifest.load(spec['ref']['manifest'])
    R = M['references']
    decl = M.get('pieces')
    if not decl:
        raise SystemExit('outfit_sheet: the manifest declares no pieces')
    ex = eyelib._knobs(spec.get('eyes'))['x']
    bs = spec['ref'].get('body_sheet') or {}
    rgb, D = _sheet(bs['image'], ex)
    design = bodyqa.design_views(rgb, D, D['ppl'])
    base = R.get('base_body_turnaround')
    if base:
        brgb, BD = _sheet(base['path'], ex)
        src = base['path']
    else:
        brgb, BD = rgb, D
        src = bs['image']
    f = BD['figures']['front']
    eye = (float(np.mean([e[0] for e in f['eyes']])), f['eye_y'])
    sk, rows = skeleton_front(f['_mask'], eye, BD['ppl'])
    log('skeleton from %s: %s' % (src, ', '.join('%s %.2f' % kv for kv in rows.items())))
    masks = piece_masks(design, decl, P, sk)
    pieces = []
    for pc in decl:
        ids = [pc['id']] if pc.get('side') != 'split' else [pc['id'] + '_L', pc['id'] + '_R']
        for pid in ids:
            side = pid[-1] if pc.get('side') == 'split' else 'C'
            bone = pc.get('bone')
            if side in 'LR' and bone and not bone.startswith(('left', 'right')):
                bone = ('left' if side == 'L' else 'right') + bone[0].upper() + bone[1:]
            idx = [i for i, n in enumerate(P.names) if n in pc['swatches']]
            c = P.rgb[idx[0]] if idx else np.zeros(3)
            ext = {vn: extent(masks.get('%s__%s' % (vn, pid), np.zeros((1, 1), bool)), design[vn]) for vn in design}
            pieces.append(dict(id=pid, type=pc['type'], name=pc.get('name', pc['type']), side=side,
                               pair=pc['id'] if side in 'LR' else None,
                               colour=dict(srgb=[round(float(v), 3) for v in c],
                                           hex='#%02x%02x%02x' % tuple(int(round(v * 255)) for v in c),
                                           name=pc['swatches'][0] if pc['swatches'] else None),
                               swatches=pc['swatches'], trims=[],
                               attach=dict(bone=bone, region=pc.get('region', bone), parent=pc.get('parent'),
                                           parent_from='manifest'),
                               layer=dict(over=pc.get('over', []), under=[]),
                               extent={vn: e for vn, e in ext.items() if e},
                               motion=dict(**{'class': pc.get('motion', 'rigid')}, why='declared in the manifest')))
    G = dict(name=spec['name'], format='charkit-outfit/1', version=1,
             generated_by=dict(tool='charkit.outfit_sheet', version=1,
                               command='python -m charkit.outfit_sheet %s' % spec.get('_path', 'SPEC')),
             frame=dict(units='head lengths L', z='up from the eye line',
                        x='per sheet view: toward the image\'s right from the view\'s origin (bodyqa.design_views); the '
                          'skeleton: toward the character\'s left from the front eyes\' middle'),
             sources=dict(sheet=dict(path=bs['image'], ppl=round(float(D['ppl']), 2), views=list(design)),
                          skeleton=dict(path=src, ppl=round(float(BD['ppl']), 2), rows=rows, proportions=SK)),
             pieces=pieces, skeleton={b: [list(h), list(t)] for b, (h, t) in sk.items()}, unmatched=[], flags=[],
             templates=dict(garments=[], gaps=sorted({p['type'] for p in decl})), comparison={}, springs=[])
    os.makedirs(out, exist_ok=True)
    paths = {'graph': os.path.join(out, 'outfit_graph.json'), 'masks': os.path.join(out, 'outfit_masks.npz')}
    json.dump(G, open(paths['graph'], 'w'), indent=1)
    np.savez_compressed(paths['masks'], **masks)
    for vn in design:
        log('%s: %s' % (vn, ', '.join('%s %d' % (k.split('__')[1], v.sum()) for k, v in masks.items()
                                         if k.startswith(vn + '__') and v.any())))
    return G, paths


# ------------------------------------------------------------------------------- drafting the accessories' templates
EMBLEM_CELLS = 28           # a pin's emblem: its drawing resampled to this many cells across the face


def _peaks(top, min_prom):
    """the tips of a top outline (heights per column, nan where empty): its peaks standing at least min_prom above the
    outline either side (scipy.signal.find_peaks' prominence) -> their count."""
    from scipy.signal import find_peaks
    t = np.asarray(top, float)
    ok = np.isfinite(t)
    if ok.sum() < 3:
        return 0
    t = np.where(ok, t, np.nanmin(t))
    return int(len(find_peaks(t, prominence=min_prom)[0]))


def draft_crown(pc, masks, ppl, P):
    """a crown accessory spec from its piece's front and profile masks (L from the eyes' middle)."""
    from .accessories import CROWN
    f, pr = masks.get('front__' + pc['id']), masks.get('profile__' + pc['id'])
    if f is None or not f.any():
        return None
    win = None
    ys, xs = np.nonzero(f)
    top = np.full(f.shape[1], np.nan)
    for c in np.unique(xs):
        top[c] = -ys[xs == c].min()
    H = (ys.max() - ys.min() + 1)
    k = _peaks(top, 0.18 * H)                               # the tips the front shows
    widths = f.sum(1)[ys.min():ys.max() + 1]
    band = float(np.sum(widths >= 0.85 * widths.max()) / H)
    return dict(xs=xs, ys=ys, H=H, k=k, band=band, pr=pr)


def _tips_on_sheet(spec, pc, P):
    """the points round a ring piece (a crown) from its own shape sheet (its shape_ref): the tips its first (front) view
    draws (peaks of its top outline), at x = R sin(phi) from the middle; 360 degrees over the nearest pair's angle
    -> count, or None."""
    from . import manifest
    from .palette import lab as tolab
    from .sheetqa import boxes, label
    ref = pc.get('shape_ref')
    R = manifest.load(spec['ref']['manifest'])['references'] if ref else {}
    if ref not in R:
        return None
    from PIL import Image
    rgb = np.asarray(Image.open(_p(R[ref]['path'])).convert('RGB')).astype(float) / 255
    idx = [P.names.index(n) for n in pc['swatches'] if n in P.names]
    m = np.isin(P.nearest_among(tolab(rgb), idx), idx)
    from .bodyqa import dilate
    lab_, n = label(dilate(m, 3))
    if not n:
        return None
    B, area = boxes(lab_, n)
    keep = [i for i in range(n) if area[i] >= 0.2 * area.max()]
    i = min(keep, key=lambda i: B[i][0])                       # the leftmost: its front view
    x0, y0, x1, y1 = (int(v) for v in B[i])
    sub = (lab_ == i + 1)[y0:y1 + 1, x0:x1 + 1] & m[y0:y1 + 1, x0:x1 + 1]
    top = np.full(sub.shape[1], np.nan)
    for c in range(sub.shape[1]):
        r = np.nonzero(sub[:, c])[0]
        if len(r):
            top[c] = -r.min()
    from scipy.signal import find_peaks
    t = np.where(np.isfinite(top), top, np.nanmin(top))
    pk = find_peaks(t, prominence=0.18 * (y1 - y0 + 1))[0]
    if len(pk) < 2:
        return None
    # the ring's points from their spacing: tips seen at x = R sin(phi) from the middle; the nearest pair's angle
    half = 0.5 * sub.shape[1]
    phi = np.degrees(np.arcsin(np.clip((pk - half) / half, -1, 1)))
    gap = float(np.min(np.diff(np.sort(phi))))
    return int(np.clip(round(360.0 / max(gap, 1e-6)), 4, 24))


def draft_accessories(spec, design, masks, pieces, P, hull_dir=None, log=print):
    """the accessories' template specs from the outfit graph's crown and pin pieces (accessories.crown / pin): sizes,
    places and counts from their masks on the body sheet's views (L from the eyes), a pin's depth and facing from the
    hull's front surface, its emblem from its own sheet's drawing -> [spec]."""
    from .accessories import CROWN
    out = []
    for pc in pieces:
        if pc['type'] == 'crown':
            fdv, pdv = design['front'], design.get('profile')
            ppl, win = fdv['ppl'], fdv['win']
            f = masks.get('front__' + pc['id'])
            if f is None or not f.any():
                continue
            d = draft_crown(pc, masks, ppl, P)
            ring = _tips_on_sheet(spec, pc, P)               # its own sheet's front view: the points' spacing
            X = lambda c, dv: (c + 0.5) / dv['ppl'] - dv['win']['x']
            Z = lambda r, dv: dv['win']['top'] - (r + 0.5) / dv['ppl']
            x0, x1 = X(d['xs'].min(), fdv), X(d['xs'].max(), fdv)
            z0, z1 = Z(d['ys'].max(), fdv), Z(d['ys'].min(), fdv)
            rx = 0.5 * (x1 - x0) / (1 + CROWN['flare'])
            ry, yc = rx, 0.0
            pr = d['pr']
            if pr is not None and pr.any():
                py, px = np.nonzero(pr)
                q0, q1 = X(px.min(), pdv), X(px.max(), pdv)
                ry, yc = 0.5 * (q1 - q0) / (1 + CROWN['flare']), 0.5 * (q0 + q1)
            n = ring or (int(max(4, 2 * (d['k'] - 1))) if d['k'] >= 2 else CROWN['points'])
            col = lambda name: [round(float(v), 4) for v in P.rgb[P.names.index(name)]] if name in P.names else None
            jewels = [c for c in (col(nm) for nm in pc['swatches'] if 'jewel' in nm) if c] or [[0.8, 0.2, 0.2]]
            out.append(dict(kind='crown', name=pc['id'], from_eyes=[round(0.5 * (x0 + x1), 4), round(yc, 4), round(z0, 4)],
                            shape=dict(rx=round(rx, 4), ry=round(ry, 4), height=round(z1 - z0, 4),
                                       band=round(min(0.7, max(0.15, d['band'])), 3), points=n, jewels=n),
                            color=col(pc['swatches'][0]), colors=(jewels * 2)[:2],
                            line=[round(float(v) * 0.5, 4) for v in P.rgb[P.names.index(pc['swatches'][min(1, len(
                                pc['swatches']) - 1)])]],
                            drafted='from its masks (band %.2f of its height); %d points from its own sheet\'s tips\' spacing'
                                    % (d['band'], n)))
        elif pc['type'] == 'pin':
            fdv = design['front']
            f = masks.get('front__' + pc['id'])
            if f is None or not f.any():
                continue
            ys, xs = np.nonzero(f)
            X = lambda c: (c + 0.5) / fdv['ppl'] - fdv['win']['x']
            Z = lambda r: fdv['win']['top'] - (r + 0.5) / fdv['ppl']
            xc, zc = 0.5 * (X(xs.min()) + X(xs.max())), 0.5 * (Z(ys.min()) + Z(ys.max()))
            r = float(np.sqrt(f.sum() / np.pi)) / fdv['ppl']     # by its area: specks of its colours don't widen it
            y, facing = _surface(hull_dir, xc, zc, r, pc['id']) if hull_dir else (-0.5, (0.0, 0.0))
            sh = dict(r=round(r, 4))
            em = _emblem(spec, pc, P)
            if em:
                sh['emblem'] = em
            names = pc['swatches']
            col = lambda name: [round(float(v), 4) for v in P.rgb[P.names.index(name)]]
            bone = pc.get('bone') or 'upperChest'               # the armature's bones carry VRM names (body.build_armature)
            out.append(dict(kind='pin', name=pc['id'], from_eyes=[round(xc, 4), round(y, 4), round(zc, 4)],
                            facing=[round(facing[0], 2), round(facing[1], 2)], shape=sh, color=col(names[0]),
                            colors=[[0.62, 0.62, 0.66]] + [col(n) for n in names[1:]], bone=bone,
                            drafted='from its front mask; depth and facing from the hull\'s front surface'))
    return out


def _col(P, name):
    return [round(float(v), 4) for v in P.rgb[P.names.index(name)]]


def _shade(P, pc):
    """a piece's shade multiplier: its second swatch (its shadow) over its first (lit), else none."""
    sw = pc['swatches']
    if len(sw) < 2:
        return None
    a, b = P.rgb[P.names.index(sw[0])], P.rgb[P.names.index(sw[1])]
    return [round(float(v), 4) for v in np.clip(b / np.maximum(a, 1e-3), 0.3, 1.0)]


def draft_garments(design, masks, pieces, P, sk, log=print):
    """the garments' template specs (charkit.garments' kinds) for the piece types that have one, from the pieces' masks
    on the front view and the skeleton (L from the eye line): a tunic as a shell over the torso and upper arms with a
    skirt from the waist to its hem (its length and flare from the mask), a belt (its height and width), sandals as
    shoes. Types with no template (a drape) are left out and listed. -> (specs, [types without a template])."""
    f = design['front']
    X = lambda c: (c + 0.5) / f['ppl'] - f['win']['x']
    Z = lambda r: f['win']['top'] - (r + 0.5) / f['ppl']
    hips_z, spine_z = sk['hips'][0][1], sk['spine'][1][1]
    frac = lambda z: float(np.clip((z - hips_z) / max(1e-6, spine_z - hips_z), 0.0, 1.2))
    specs, missing = [], []
    for pc in pieces:
        t = pc['type']
        m = masks.get('front__' + pc['id']) if pc.get('side') != 'split' else None
        if t == 'tunic' and m is not None and m.any():
            ys, xs = np.nonzero(m)
            hem_z = Z(ys.max())
            waist = 0.55
            zw = hips_z + (spine_z - hips_z) * waist
            r_w = [r for r in range(m.shape[0]) if abs(Z(r) - zw) < 0.04]
            hw_w = np.mean([np.ptp(np.nonzero(m[r])[0]) / 2 / f['ppl'] for r in r_w if m[r].any()]) if r_w else 0.5
            r_h = [r for r in range(m.shape[0]) if hem_z + 0.02 < Z(r) < hem_z + 0.12 and m[r].any()]
            hw_h = np.mean([np.ptp(np.nonzero(m[r])[0]) / 2 / f['ppl'] for r in r_h]) if r_h else hw_w
            length = max(0.2, zw - hem_z)
            flare = float(np.degrees(np.arctan2(max(0.0, hw_h - hw_w), length)))
            col, shade = _col(P, pc['swatches'][0]), _shade(P, pc)
            specs.append(dict(kind='shell', name=pc['id'] + '_top', region=[[b, -1, 3] for b in ('hips', 'spine', 'chest', 'upperChest')] +
                              [['neck', -1, 0.6], ['leftShoulder', -1, 3], ['rightShoulder', -1, 3],
                               ['leftUpperArm', -1, 0.45], ['rightUpperArm', -1, 0.45]],
                              offset=0.02, thick=0.008, color=col, shade=shade,
                              cuts=[['neck', 0.0, 'below', 0.04]], drafted='tunic: its top over the torso and upper arms'))
            specs.append(dict(kind='skirt', name=pc['id'] + '_skirt', waist=waist, length=round(length, 4),
                              flare=round(flare, 2), pleats=24, pleat=0.025, offset=0.02, color=col, hem_color=col,
                              panel=0.0, shade=shade,
                              drafted='tunic: its skirt, hem %.2f L under the eye line, flare %.1f deg (its front mask)'
                                      % (hem_z, flare)))
        elif t == 'belt' and m is not None and m.any():
            ys, xs = np.nonzero(m)
            zc = 0.5 * (Z(ys.min()) + Z(ys.max()))
            specs.append(dict(kind='belt', name=pc['id'], waist=round(frac(zc), 4),
                              width=round(float((ys.max() - ys.min() + 1) / f['ppl']), 4), offset=0.04, thick=0.02,
                              color=_col(P, pc['swatches'][0]), drafted='its front mask: height and middle'))
        elif t == 'sandal':
            for side, S_ in (('left', 'L'), ('right', 'R')):
                specs.append(dict(kind='shoe', name='%s_%s' % (pc['id'], S_), side=side, offset=0.01, sole=0.04,
                                  color=_col(P, pc['swatches'][0]),
                                  sole_color=[round(v * 0.7, 4) for v in _col(P, pc['swatches'][0])],
                                  drafted='a shoe template (no strapped-sandal template)'))
        elif t == 'drape' and m is not None and m.any():
            ys, xs = np.nonzero(m)
            # its diagonal: the mask's row centres over the chest (the eye line to the waist) rise toward one shoulder
            rows = [r for r in range(m.shape[0]) if spine_z < Z(r) < sk['chest'][1][1] and m[r].any()]   # the chest
            cx = np.array([np.nonzero(m[r])[0].mean() for r in rows]) if rows else np.array([0.0])
            zr = np.array([Z(r) for r in rows]) if rows else np.array([0.0])
            slope = np.polyfit(zr, X(cx), 1)[0] if len(rows) > 3 else -1.0
            shoulder = 'right' if slope < 0 else 'left'        # x toward the character's left: rising to its right, x falls
            width = float(np.percentile([np.ptp(np.nonzero(m[r])[0]) for r in rows], 10) / f['ppl'] *
                          abs(math.cos(math.atan(slope)))) if rows else 0.45
            col, shade = _col(P, pc['swatches'][0]), _shade(P, pc)
            specs.append(dict(kind='sash', name=pc['id'], shoulder=shoulder, hip=0.4, width=round(min(0.8, width), 4),
                              offset=0.05, thick=0.012, color=col, shade=shade,
                              drafted="a sash over the %s shoulder (the front mask's diagonal), %.2f L wide" % (
                                  shoulder, width)))
            # its hanging end: what falls below the hips, as a panel from the waist at its azimuth
            low = np.array([Z(r) < hips_z for r in ys])
            if low.any():
                lx, lz = X(xs[low]), Z(ys[low])
                hw = float(np.median([np.ptp(xs[low][ys[low] == r]) for r in np.unique(ys[low])]) / f['ppl']) / 2
                xm = float(np.mean(lx))
                ring = max(0.3, abs(xm) + 1e-3)
                az = float(np.degrees(np.arcsin(np.clip(xm / ring, -1, 1))))
                specs.append(dict(kind='panel', name=pc['id'] + '_end', az=round(az, 1), width=round(2 * hw, 4),
                                  length=round(float(hips_z + 0.3 - lz.min()), 4), waist=0.5, flare=8, spread=0.1,
                                  offset=0.06, color=col, shade=shade,
                                  drafted='the drape\'s hanging end: the front mask below the hips'))
        elif t not in ('crown', 'pin'):
            missing.append(t)
    return specs, missing


def draft(spec, log=print):
    """the outfit's template specs drafted from the character's own references: its produced outfit graph and masks
    (charkit.outfit_sheet) and hull -> dict(garments, accessories, missing (piece types with no template))."""
    from . import bodyqa, eyes as eyelib, manifest, palette
    P = palette.active()
    M = manifest.load(spec['ref']['manifest'])
    mp = manifest.produced(spec, 'outfit_masks', log)
    G = json.load(open(os.path.join(os.path.dirname(mp), 'outfit_graph.json')))
    masks = dict(np.load(mp))
    ex = eyelib._knobs(spec.get('eyes'))['x']
    rgb, D = _sheet(spec['ref']['body_sheet']['image'], ex)
    design = bodyqa.design_views(rgb, D, D['ppl'])
    sk = {b: (tuple(s_[0]), tuple(s_[1])) for b, s_ in G['skeleton'].items()}
    hull = manifest.produced(spec, 'hull', log)
    acc = draft_accessories(spec, design, masks, M['pieces'], P, os.path.dirname(hull), log)
    gar, missing = draft_garments(design, masks, M['pieces'], P, sk, log)
    return dict(garments=gar, accessories=acc, missing=missing)


def _surface(hull_dir, x, z, r, piece=None):
    """the hull's front surface at (x, z) L from its eyes' middle (its sidecar's units, L): its depth y (L, toward the
    back +) and facing (az, el degrees), from the piece's own labelled vertices there when the hull carries them
    -> (y, (az, el))."""
    from .geom import io as gio
    side = json.load(open(os.path.join(hull_dir, 'hull.glb.json')))
    M = gio.load(os.path.join(hull_dir, 'hull.glb'))
    V = np.asarray(M.V if hasattr(M, 'V') else M[0], float)
    mid = np.asarray(side['eyes'], float).mean(0)
    Q = V - mid
    near = (np.abs(Q[:, 0] - x) < 0.6 * r) & (np.abs(Q[:, 2] - z) < 0.6 * r)
    pf = os.path.join(hull_dir, side.get('pieces') or 'hull_pieces.npy')
    if piece and os.path.exists(pf):
        lab = np.load(pf)
        ids = [int(k) for k, v in (side.get('piece_names') or {}).items() if v == piece]
        if ids and len(lab) == len(V) and (near & np.isin(lab, ids)).sum() >= 3:
            near &= np.isin(lab, ids)
    if not near.any():
        return -0.5, (0.0, 0.0)
    fr = Q[near]
    y = float(fr[:, 1].min())
    pts = fr[fr[:, 1] < y + 0.05]
    if len(pts) >= 3:                                        # the facing: the front points' plane, toward -y
        c = pts.mean(0)
        _, _, vt = np.linalg.svd(pts - c)
        nrm = vt[-1] if vt[-1][1] < 0 else -vt[-1]
    else:
        nrm = np.array([0.0, -1.0, 0.0])
    az = float(np.degrees(np.arctan2(nrm[0], -nrm[1])))
    el = float(np.degrees(np.arcsin(np.clip(nrm[2], -1, 1))))
    return y, (az, el)


def _emblem(spec, pc, P):
    """a pin's emblem cells from its own sheet's drawing (the piece's shape_ref, its row): the drawing's main blob of the
    pin's colours, resampled to EMBLEM_CELLS across, each cell its nearest of the pin's swatches (0 the face's)."""
    from . import manifest
    ref = pc.get('shape_ref')
    if not ref:
        return None
    R = manifest.load(spec['ref']['manifest'])['references']
    if ref not in R:
        return None
    from PIL import Image
    rgb = np.asarray(Image.open(_p(R[ref]['path'])).convert('RGB')).astype(float) / 255
    idx = [P.names.index(n) for n in pc['swatches']]
    k = P.nearest_among(__import__('charkit.palette', fromlist=['lab']).lab(rgb), idx)
    m = np.isin(k, idx)
    H = rgb.shape[0]
    if pc.get('shape_row') == 'bottom':
        m[:H // 2] = False
    elif pc.get('shape_row') == 'top':
        m[H // 2:] = False
    from .sheetqa import boxes, label
    lab_, n = label(m)
    if not n:
        return None
    B, area = boxes(lab_, n)
    order = np.argsort(-area)
    i = int(order[0])                                          # the face-on drawing: the largest (an edge view is thin)
    x0, y0, x1, y1 = (int(v) for v in B[i])
    s = max(x1 - x0, y1 - y0) + 1
    cells = np.zeros((EMBLEM_CELLS, EMBLEM_CELLS), int)
    for a in range(EMBLEM_CELLS):
        for b in range(EMBLEM_CELLS):
            ya, yb = y0 + a * s // EMBLEM_CELLS, y0 + (a + 1) * s // EMBLEM_CELLS
            xa, xb = x0 + b * s // EMBLEM_CELLS, x0 + (b + 1) * s // EMBLEM_CELLS
            sub = k[ya:max(yb, ya + 1), xa:max(xb, xa + 1)]
            vals = [idx.index(v) for v in sub.ravel() if v in idx]
            if vals:
                cells[a, b] = int(np.bincount(vals).argmax())
    return dict(cells=cells.tolist())


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return 0
    from . import manifest
    spec = manifest.resolve(json.load(open(_p(args[0]))))
    spec['_path'] = os.path.relpath(_p(args[0]), ROOT)
    out = args[args.index('--out') + 1] if '--out' in args else os.path.join(ROOT, 'charkit', 'out', spec['name'], 'outfit')
    t0 = time.time()
    G, paths = build(spec, _p(out))
    print('%d pieces, %d bones (%.1f s)' % (len(G['pieces']), len(G['skeleton']), time.time() - t0))
    for k, v in paths.items():
        print(k, v)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
