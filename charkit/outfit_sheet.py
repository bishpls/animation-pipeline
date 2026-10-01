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
import json, os, sys, time

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
