"""The hand breakdown sheet (charkit/refs/clawd/gen/hand_breakdown.png, a generated reference: relaxed, open, fist and
point, from the back of the hand and from the thumb's side) cut into hands, and checked against the turnaround's
A-pose hands before it grades anything (Michael's rule for generated references: refcheck first).

Each drawn figure on the sheet is a hand coming out of the wrist cuff; the sheet's scale per figure comes from its
cuff's width across the arm against the turnaround's cuffs' (the same garment), so a hand is compared at the
turnaround's scale. The relaxed hands are the A-pose's: the back view against the profile's hand (the back of her left
hand faces the viewer there), the side view against the front and back views' hands (seen from the thumb's side, turned
some way toward the viewer).

    python -m charkit.handref --build BUILD SHEET.png [...] [--out DIR]    the refcheck (a build for its spec and grids)
"""
import json, os, sys

import numpy as np

from . import handqa

POSES = ('relaxed', 'open', 'fist', 'point')          # the sheet's columns, left to right
ROWS = ('back', 'side')                               # its rows: the back of the hand, the thumb's side


def classes(rgb):
    """a sheet's pixels -> dict(skin, cuff (orange or cream), line, fg): bodyqa's colour families, the dark ink as line."""
    from .bodyqa import CLASS, family
    f = family(np.asarray(rgb, float)[..., :3] / (255.0 if np.asarray(rgb).max() > 1 else 1.0))
    skin, cuff, line = f == CLASS['skin'], (f == CLASS['orange']) | (f == CLASS['cream']), f == CLASS['dark']
    return dict(skin=skin, cuff=cuff, line=line, fg=skin | cuff | line)


def figures(rgb, min_px=4000):
    """the sheet's figures (a cuff and its hand each), in reading order -> [dict(row, col, box, skin, cuff, line)]:
    each the ink-closed blob of skin, cuff and line pixels, its masks cropped to its box."""
    from scipy import ndimage
    C = classes(rgb)
    fg = ndimage.binary_closing(C['fg'], iterations=2)
    lab, n = ndimage.label(fg)
    out = []
    for k, sl in enumerate(ndimage.find_objects(lab), 1):
        m = lab[sl] == k
        if m.sum() < min_px or not (C['cuff'][sl] & m).any() or not (C['skin'][sl] & m).any():
            continue
        out.append(dict(box=(sl[1].start, sl[0].start, sl[1].stop, sl[0].stop), mask=m,
                        **{c: C[c][sl] & m for c in ('skin', 'cuff', 'line')}))
    if not out:
        return out
    ys = np.array([(f['box'][1] + f['box'][3]) / 2 for f in out])
    split = ys.min() + 0.5 * (ys.max() - ys.min())
    for f, y in zip(out, ys):
        f['row'] = 0 if y < split else 1
    for r in (0, 1):
        row = sorted([f for f in out if f['row'] == r], key=lambda f: f['box'][0])
        for c, f in enumerate(row):
            f['col'] = c
    return sorted(out, key=lambda f: (f['row'], f['col']))


def cuff_width_px(f):
    """a figure's cuff: its widest across the arm (px), pieceqa.cuff_shape's at 1 px per L."""
    from .pieceqa import cuff_shape
    cr = f['cuff']
    return (cuff_shape(cr, f['skin'], np.zeros_like(cr), 1.0, reach=200) or {}).get('widest')


def design_cuff_width(design, masks, dv):
    """the turnaround's cuffs' widest across the arm (L), the median over the front and back views."""
    from .bodyqa import CLASS
    from .pieceqa import cuff_shape
    ppl = design.sheet_context()['ppl']
    ws = []
    for v in ('front', 'back'):
        for s in ('L', 'R'):
            m = masks.get('%s__cuff_%s' % (v, s))
            if m is None:
                continue
            cls = dv[v]['cls']
            m = m[:cls.shape[0], :cls.shape[1]]
            r = cuff_shape(m, cls == CLASS['skin'], cls == CLASS['cream'], ppl)
            if r:
                ws.append(r['widest'])
    return float(np.median(ws)) if ws else None


def resample(m, k):
    """a mask scaled by k (nearest)."""
    from scipy import ndimage
    return ndimage.zoom(m.astype(np.uint8), k, order=0).astype(bool)


def sheet_hands(rgb, cuff_L, ppl):
    """the sheet's hands at the turnaround's scale: per figure its hand mask resampled to ppl px per L (its cuff's width
    in px against cuff_L), its reach past the cuff (L), digits (its ink) and cleft -> {(row, col): dict}."""
    out = {}
    for f in figures(rgb):
        wpx = cuff_width_px(f)
        if not wpx:
            continue
        ppl_s = wpx / cuff_L
        from scipy import ndimage
        sk = ndimage.binary_fill_holes(ndimage.binary_closing(f['skin'], iterations=3) & ~f['cuff'])
        h = handqa.hand_mask(sk, f['cuff'], ppl_s)
        if h is None:
            continue
        n, per = handqa.digits(h, f['line'], ppl_s)
        cd, pk = handqa.cleft(h['mask'], ppl_s)
        out[(f['row'], f['col'])] = dict(mask=resample(h['mask'], ppl / ppl_s), ppl_sheet=round(ppl_s, 2), u=h['u'],
                                         reach=round(handqa.reach(h, ppl_s), 4), digits=n, per_band=per,
                                         cleft=round(cd, 4), box=f['box'])
    return out


def refcheck(B, design, sheet_path, out=None):
    """the sheet's relaxed hands against the turnaround's A-pose hands at matching scale -> dict: per pairing the IoU
    (centroid-aligned, turned to the drawn arm's direction; the better of it and its mirror: the sheet draws one hand), the reach, digits and cleft beside the
    drawn hand's, and the cells found."""
    from PIL import Image
    from . import bodymeasure
    from .bodyqa import CLASS
    ctx = design.sheet_context()
    ppl = ctx['ppl']
    masks, graph, _ = bodymeasure.piece_masks(B.spec)
    dv = design.design_views()
    cuff_L = design_cuff_width(design, masks, dv)
    rgb = np.asarray(Image.open(sheet_path).convert('RGB'))
    S = sheet_hands(rgb, cuff_L, ppl)
    drawn = {}
    seams = handqa.design_seams(dv)
    for v in handqa.VIEWS:
        cls, fg = dv[v]['cls'], dv[v]['fg']
        for s in handqa.sides(v):
            m = masks.get('%s__cuff_%s' % (v, s))
            if m is None:
                continue
            h = handqa.hand_mask(fg & (cls == CLASS['skin']), m[:cls.shape[0], :cls.shape[1]], ppl)
            if h is not None:
                drawn[(v, s)] = dict(mask=h['mask'], u=h['u'], **handqa.features(h, seams[v], ppl))
    pairs = {'back': [('profile', 'L')], 'side': [('front', 'L'), ('front', 'R'), ('back', 'L'), ('back', 'R'),
                                                  ('three_quarter', 'L')]}
    rep = dict(sheet=sheet_path, cuff_L=round(cuff_L, 4), cells=len(S), poses={}, pairs=[])
    for (r, c), h in sorted(S.items()):
        name = '%s_%s' % (POSES[c] if c < len(POSES) else c, ROWS[r])
        rep['poses'][name] = {k: h[k] for k in ('ppl_sheet', 'reach', 'digits', 'cleft', 'box')}
        if c != 0:
            continue
        for key in pairs[ROWS[r]]:
            if key not in drawn:
                continue
            d = drawn[key]
            hm = [handqa.rotated(h['mask'], h['u'], d['u']), handqa.rotated(h['mask'][:, ::-1], h['u'] * [-1, 1], d['u'])]
            ious = [handqa.shape_iou(d['mask'], m_) for m_ in hm]
            rep['pairs'].append(dict(sheet=name, drawn='%s_%s' % key, iou=round(max(ious), 4),
                                     mirrored=bool(ious[1] > ious[0]), reach=[h['reach'], d['reach']],
                                     digits=[h['digits'], d['digits']], cleft=[h['cleft'], d['cleft']]))
    if out:
        _picture(rep, S, drawn, out)
    return rep


def _picture(rep, S, drawn, out):
    """refcheck_NAME.png: each pairing's drawn hand (grey) and the sheet's at its scale (red outline), the IoU above."""
    from PIL import Image, ImageDraw
    from scipy import ndimage
    tiles = []
    for p in rep['pairs']:
        r = ROWS.index(p['sheet'].split('_')[1])
        v, s = p['drawn'].rsplit('_', 1)
        H = S[(r, 0)]
        h = handqa.rotated(H['mask'][:, ::-1], H['u'] * [-1, 1], drawn[(v, s)]['u']) if p['mirrored'] else \
            handqa.rotated(H['mask'], H['u'], drawn[(v, s)]['u'])
        A, Bm = handqa.aligned_pair(drawn[(v, s)]['mask'], h)
        img = np.full(A.shape + (3,), 255, np.uint8)
        img[A] = (170, 170, 170)
        img[Bm & ~ndimage.binary_erosion(Bm)] = (220, 30, 30)
        img = np.kron(img, np.ones((2, 2, 1), np.uint8))
        canvas = np.full((img.shape[0] + 16, max(img.shape[1], 150), 3), 255, np.uint8)
        canvas[16:, :img.shape[1]] = img
        im = Image.fromarray(canvas)
        ImageDraw.Draw(im).text((2, 2), '%s~%s %.2f' % (p['sheet'], p['drawn'], p['iou']), fill=(0, 0, 0))
        tiles.append(np.asarray(im))
    if not tiles:
        return
    H = max(t.shape[0] for t in tiles)
    row = np.concatenate([np.pad(t, ((0, H - t.shape[0]), (0, 6), (0, 0)), constant_values=255) for t in tiles], 1)
    name = os.path.splitext(os.path.basename(rep['sheet']))[0]
    Image.fromarray(row).save(os.path.join(out, 'refcheck_%s.png' % name))


def main(args):
    from . import bundle, qa3d
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    build = opt('--build')
    out = opt('--out')
    sheets = [a for a in args if a.endswith('.png')]
    B = bundle.load(os.path.join(build, 'bundle'))
    D = qa3d.Design(B)
    reps = [refcheck(B, D, p, out) for p in sheets]
    s = json.dumps(reps, indent=1)
    if out:
        open(os.path.join(out, 'refcheck.json'), 'w').write(s)
    print(s)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
