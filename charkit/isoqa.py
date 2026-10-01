"""Isolated-piece checks (Michael, 2026-09-30; tool/pieceref, docs/workstreams/pieceref.md): a piece's shape graded
against its isolated reference, one object drawn large and self-consistent (garment_breakdown's flat-lay, the
close-ups), while its placement, occlusion and silhouette in context stay the turnaround's (the piece checks, partqa).
The manifest splits the authority per piece: `shape_<piece>` names the isolated reference, `piece_placement` the
turnaround's outfit graph; a reference's `pieces` gives each piece's box on it and the view it is drawn from.

Ours is drawn alone (the piece's objects only, the build's outlines at the design's line scale), in the reference's
projection (its view: front for the flat-lay, orthographic), and both are scaled to the piece's own size: each mask is
cut to the box of its body (for the bow: its lobes and knot), scaled to BODY_W px wide and laid from the box's top left.
The breakdown is flattened, so only rigid pieces compare directly (the bow, cuffs, collar, boots); draped ones (the
skirt) wait for the sewing-pattern work.

A reference is split into parts by its ink: the cells between its black lines (a white ground), the bow's knot the
compact cell nearest its middle, its tails the two cells reaching lowest, its lobes the rest by side (her left is the
picture's right: the flat-lay and the close-ups draw the piece from the front); its lines are its ink and its fainter
strokes (outfit.ridges: the creases are drawn in a shade).

Checks (qa3d part 'iso_pieces'; the bow's outline from its shape authority `shape_bow`, the lines
inside it from `lines_bow` when the manifest names one: each graded against the reference that agrees with the
turnaround on that property, the refcheck):
  iso_bow_body       the lobes and knot scaled to their own width: IoU with the reference's
  iso_bow_tails      the tails in the same frame: IoU with the reference's
  iso_bow_knot_size  the knot's width over the body's, |ours / reference's - 1|
  iso_bow_knot_rect, iso_bow_knot_line, iso_bow_crease_len, iso_bow_crease_dir
                     partqa's measures on the isolated pictures, graded as partqa's
  iso_bow_refcheck   INFO: the turnaround's front bow (the outfit's part masks and the design's lines) against the
                     reference the same way (the generated reference's consistency with the turnaround)

    table, checks = isoqa.measure(B, design)
    R = isoqa.ref_piece(rgb, box)                 # a reference's piece: mask, parts, line
    M = isoqa.compare(ours, R)                    # the scaled comparison and partqa's measures
"""
import numpy as np

from .registry import flag_check, qa_part

from . import partqa as pqa

BODY_W = 300                        # px: both bodies scaled to this width
BAND_W = 1.5                        # a lobe's outline: its lines within this many line widths of its edge
INK_V = 0.35                        # a reference pixel whose brightest channel is under this is ink
GROUND_V = 0.92                     # ... whose darkest channel is over this is the white ground
LIMITS = {                          # (pass, warn): at least for IoU, within for the rest
    'body': (0.85, 0.75),
    'tails': (0.75, 0.6),
    'knot_size': (0.2, 0.35),
}
FLAG = pqa.FLAG


def grade(key, v):
    if key in pqa.LIMITS:
        return pqa.grade(key, v)
    p, w = LIMITS[key]
    if key in ('body', 'tails'):
        return 'PASS' if v >= p else 'WARN' if v >= w else 'FAIL'
    return 'PASS' if v <= p else 'WARN' if v <= w else 'FAIL'


INFO_KEYS = ('tails', 'knot_size', 'knot_rect')   # reported, not graded. Refcheck (the turnaround's front bow
                                    # against each reference): garment_breakdown's body 0.762, tails 0.759, knot 33%
                                    # wider, its inner lines the turnaround's (crease -39 against -37/-40 degrees,
                                    # length 1.5 against 1.45-1.53 widths): lines_bow. bow_closeup's body 0.871 (the
                                    # turnaround PASSes; g3_render3 0.659 FAILs): shape_bow; its tails 0.516 (drawn
                                    # ~20% longer) and knot 22% wider (the turnaround reads 0.18 against it, the flagged
                                    # builds 0.22): those two don't separate the flagged shape from the drawn one


def _check(key, v, flag=True, **kw):
    c = dict(value=None if v is None else round(float(v), 4), status='FAIL' if v is None else grade(key, v), **kw)
    if key in INFO_KEYS:
        return dict(c, status='INFO', graded_as=c['status'],
                    why="the reference's outline disagrees with the turnaround's (iso_bow_refcheck): reported only")
    return flag_check(c, FLAG) if flag else c


# ------------------------------------------------------------------------------------------------------------ pieces
def ref_piece(rgb, box=None):
    """an isolated drawing's piece (rgb 0..1, a white ground; box (x0, y0, x1, y1) its region) -> dict(mask, line,
    parts {knot, lobe_L, lobe_R, tail_L, tail_R}) by its ink cells (see the module's docstring)."""
    from scipy import ndimage
    from . import outfit
    c = rgb if box is None else rgb[box[1]:box[3], box[0]:box[2]]
    fg = ndimage.binary_fill_holes(ndimage.binary_closing(c.min(2) < GROUND_V, iterations=2))
    ink = (c.max(2) < INK_V) & fg
    line = ink | (outfit.ridges(c) & fg)
    fill = fg & ~ink
    lab, n = ndimage.label(fill)
    area = np.bincount(lab.ravel())
    big = [i for i in range(1, n + 1) if area[i] >= 0.01 * fill.sum()]
    return dict(mask=fg, line=line, parts=bow_cells(lab, big, fg))


def bow_cells(lab, ids, fg):
    """the bow's cells named: the two reaching lowest its tails (when there are five or more), of the rest the
    compact one nearest the middle column its knot, the others its lobes by side (her left: the picture's right)."""
    cols = np.nonzero(fg.any(0))[0]
    mid = 0.5 * (cols[0] + cols[-1])
    info = {}
    for i in ids:
        ys, xs = np.nonzero(lab == i)
        info[i] = dict(low=ys.max(), cx=xs.mean(), n=len(ys), fill=len(ys) / ((np.ptp(ys) + 1) * (np.ptp(xs) + 1)))
    tails = sorted(ids, key=lambda i: -info[i]['low'])[:2] if len(ids) >= 5 else []
    rest = [i for i in ids if i not in tails]
    total = sum(info[i]['n'] for i in rest)
    small = [i for i in rest if info[i]['n'] <= 0.4 * total] or rest
    knot = min(small, key=lambda i: abs(info[i]['cx'] - mid))
    out = {k: np.zeros(lab.shape, bool) for k in ('knot', 'lobe_L', 'lobe_R', 'tail_L', 'tail_R')}
    out['knot'] = lab == knot
    for i in ids:
        if i == knot:
            continue
        side = 'L' if info[i]['cx'] >= info[knot]['cx'] else 'R'
        out[('tail_' if i in tails else 'lobe_') + side] |= lab == i
    return out


def our_piece(B, az, ppl_design, only=('bow', 'bow_knot')):
    """ours alone (the piece's objects only), drawn with the build's outlines from azimuth az -> ref_piece's dict."""
    from scipy import ndimage
    pic = pqa.line_picture(B, az, ppl_design, only=set(only))
    P = pic['part']
    parts = {k: P == c for k, c in pqa.CODES.items()}
    mask = ndimage.binary_fill_holes((P > 0) | pic['line'])
    return dict(mask=mask, line=pic['line'] & mask, parts=parts)


def _body(p):
    return p['parts']['knot'] | p['parts']['lobe_L'] | p['parts']['lobe_R']


def silhouette(p):
    """the body's silhouette: its parts' pixels with the lines next to them taken in (a line's width round them) and the
    holes filled, less the tails: the lines drawn inside it (the knot's outline, the creases) are not its shape, and a
    body read without them lost a share for every line the line checks ask for (tool/pieceref: the creases drawn, 0.74
    -> 0.60, the silhouette unchanged)."""
    from scipy import ndimage
    lw = max(1, int(np.ceil(pqa.line_width(p['line']))))
    b = _body(p)
    t = p['parts']['tail_L'] | p['parts']['tail_R']
    return ndimage.binary_fill_holes(b | (p['line'] & ndimage.binary_dilation(b, iterations=lw + 1))) & ~t


def scaled(m, box, k, shape):
    """mask m cut at box (x0, y0, x1, y1), scaled by k and laid at the top left of a canvas of `shape`."""
    from scipy import ndimage
    x0, y0 = box[0], box[1]
    sub = m[y0:, x0:].astype(float)
    z = ndimage.zoom(sub, k, order=1) > 0.5
    out = np.zeros(shape, bool)
    h, w = min(shape[0], z.shape[0]), min(shape[1], z.shape[1])
    out[:h, :w] = z[:h, :w]
    return out


def _box(m):
    ys, xs = np.nonzero(m)
    return (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)


def normalised(p):
    """a piece's parts in the common frame: cut to its body's box, scaled to BODY_W wide -> {part: mask}."""
    b = _body(p)
    if b.sum() < 30:
        return None
    bx = _box(b)
    k = BODY_W / float(bx[2] - bx[0])
    shape = (int(BODY_W * 1.6), int(BODY_W * 1.1))
    return {n: scaled(m, bx, k, shape) for n, m in p['parts'].items()}


def iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum()) / u if u else None


def compare(o, r):
    """ours against a reference piece (ref_piece's / our_piece's dicts) -> dict(body, tails (IoU in the common
    frame), knot_size (the knot's width over the body's: [ours, reference's]), ours, ref (partqa.part_measures'))."""
    No, Nr = normalised(o), normalised(r)
    out = {}
    if No is None or Nr is None:
        return None
    # the body as its silhouette (silhouette(): its inner lines taken in), in the parts' frame
    So, Sr = (normalised(dict(p, parts=dict(p['parts'], knot=silhouette(p), lobe_L=np.zeros_like(p['mask']),
                                             lobe_R=np.zeros_like(p['mask'])))) for p in (o, r))
    out['body'] = iou(So['knot'], Sr['knot'])
    out['tails'] = iou(No['tail_L'] | No['tail_R'], Nr['tail_L'] | Nr['tail_R'])
    ks = []
    for p in (o, r):
        kb, bb = p['parts']['knot'], _body(p)
        ks.append(None if not kb.any() else (np.ptp(np.nonzero(kb)[1]) + 1) / float(np.ptp(np.nonzero(bb)[1]) + 1))
    out['knot_size'] = ks
    for name, p in (('ours', o), ('ref', r)):
        bw = float(_box(_body(p))[2] - _box(_body(p))[0])
        # lengths in body widths; a lobe's outline is the lines within 1.5 line widths of its edge (a picture's scale
        # unknown: the flat-lay's lines are its own)
        # the knot's outline: its cells a line apart, so reach at least that line's width (the close-up's lines are 5-6
        # px at 2560 wide: at 2 px its knot read no edge near the lobes, None)
        lw = pqa.line_width(p['line'])
        out[name] = pqa.part_measures(p['parts']['knot'], {'L': p['parts']['lobe_L'], 'R': p['parts']['lobe_R']},
                                      p['line'], bw, band_px=BAND_W * lw, reach=max(2, int(np.ceil(lw))))
    return out


def design_piece(design, masks, view='front'):
    """the turnaround's piece in one view: the outfit's part masks and the design's lines -> ref_piece's dict."""
    dv = design.design_views()[view]
    sh = dv['cls'].shape
    f = lambda k: pqa._fit(masks.get('%s__%s' % (view, k)), sh)
    parts = {'knot': f('bow.knot'), 'lobe_L': f('bow.lobe_L'), 'lobe_R': f('bow.lobe_R'), 'tail_L': f('bow_tail_L'),
             'tail_R': f('bow_tail_R')}
    mask = np.zeros(sh, bool)
    for m in parts.values():
        mask |= m
    return dict(mask=mask, line=pqa.design_lines(dv, sh), parts=parts)


# ------------------------------------------------------------------------------------------------------------ the part
def reference(design, key, kind='shape'):
    """the manifest's authority for a piece's `kind` ('shape': `shape_<key>`, its outline; 'lines': `lines_<key>`, the
    lines inside it, else the shape's) and its box and view on that reference -> (rgb, its name, its piece entry) or
    None."""
    from PIL import Image
    from . import manifest
    ref = design.ref()
    M = manifest.load(ref['manifest']) if ref.get('manifest') else None
    A = (M or {}).get('authority') or {}
    auth = A.get('%s_%s' % (kind, key)) or A.get('shape_' + key)
    if not auth or not M:
        return None
    R = M['references'].get(auth) or {}
    pc = (R.get('pieces') or {}).get(key)
    if not pc:
        return None
    path = manifest._p(R['path'])
    design._rec(R['path'])
    rgb = np.asarray(Image.open(path).convert('RGB')).astype(float) / 255.0
    return rgb, auth, pc


@qa_part('iso_pieces', order=1776, table='iso_pieces', checks=8)
def iso_pieces(B, design=None, out=None):
    """rigid pieces alone against their isolated shape references (Michael, 2026-09-30)."""
    return measure(B, design)


def measure(B, design):
    from . import bodymeasure
    ctx = design.sheet_context()
    if 'why' in ctx:
        return None, {'iso_pieces': {'status': 'SKIPPED', 'why': ctx['why']}}
    got = reference(design, 'bow')
    if got is None:
        return None, {'iso_pieces': {'status': 'SKIPPED', 'why': 'no shape_bow authority with a box on its reference'}}
    rgb, auth, pc = got
    R = ref_piece(rgb, pc['box'])
    az = {'front': 0.0}.get(pc.get('view', 'front'), 0.0)
    O = our_piece(B, az, ctx['ppl'])
    M = compare(O, R)
    # the lines inside the piece from their own authority (lines_bow: the reference whose knot outline and creases
    # agree with the turnaround's; the close-up's outline does, its creases run longer)
    lg = reference(design, 'bow', 'lines')
    lauth = lg[1] if lg else auth
    Rl = R if lauth == auth else ref_piece(lg[0], lg[2]['box'])
    Ml = M if lauth == auth else compare(our_piece(B, {'front': 0.0}.get(lg[2].get('view', 'front'), 0.0), ctx['ppl'])
                                         if lg[2].get('view', 'front') != pc.get('view', 'front') else O, Rl)
    T, C = {'bow': dict(reference=auth, lines=lauth, box=pc['box'], view=pc.get('view', 'front'), measures=M,
                        line_measures=Ml)}, {}
    if M is None or Ml is None:
        C['iso_bow_body'] = _check('body', None, why='no bow body drawn')
        return T, C
    C['iso_bow_body'] = _check('body', M['body'], reference=auth,
                               note="the bow's lobes and knot alone, both scaled to their own width (%d px), against "
                                    "%s's: IoU" % (BODY_W, auth))
    C['iso_bow_tails'] = _check('tails', M['tails'], reference=auth,
                                note="the bow's tails in the same frame against %s's: IoU" % auth)
    ko, kr = M['knot_size']
    C['iso_bow_knot_size'] = _check('knot_size', None if ko is None or kr is None else abs(ko / kr - 1),
                                    ours=ko and round(ko, 3), ref=kr and round(kr, 3),
                                    note="the knot's width over the lobes' span, |ours / %s's - 1|" % auth)
    Om, Rm = Ml['ours'], Ml['ref']
    C['iso_bow_knot_rect'] = _check('knot_rect', pqa.rect_err(Om['knot'], Rm['knot']), ours=Om['knot'],
                                    ref=Rm['knot'], reference=lauth,
                                    note="partqa's knot rectangle on the isolated pictures (%s's)" % lauth)
    kl_o, kl_r = Om['knot_line'], Rm['knot_line']
    C['iso_bow_knot_line'] = _check('knot_line', None if kl_o is None or kl_r is None else max(0.0, kl_r - kl_o),
                                    ours=kl_o and round(kl_o, 3), ref=kl_r and round(kl_r, 3), reference=lauth,
                                    note="the knot's edge against the lobes with a line between, %s's share less "
                                         "ours" % lauth)
    lens, dirs = {}, {}
    for s in ('L', 'R'):
        co, cr = Om['crease'].get(s), Rm['crease'].get(s)
        if not cr or not cr.get('len'):
            continue
        lens[s] = 1.0 if not co else abs(co['len'] / cr['len'] - 1)
        dirs[s] = None if not co or co.get('dir') is None or cr.get('dir') is None else abs(co['dir'] - cr['dir'])
    C['iso_bow_crease_len'] = _check('crease_len', max(lens.values()) if lens else None, per_side=lens,
                                     note="each lobe's crease length over its width, |ours / the reference's - 1|")
    dd = list(dirs.values())
    C['iso_bow_crease_dir'] = _check('crease_dir', None if not dd or any(x is None for x in dd) else max(dd),
                                     per_side=dirs, note="each lobe's crease direction, ours less the reference's")
    got = bodymeasure.piece_masks(B.spec)
    if got is not None and any(k.endswith('__bow.knot') for k in got[0]):
        Dp = design_piece(design, got[0])
        Dm = compare(Dp, R)
        T['bow']['refcheck'] = Dm
        C['iso_bow_refcheck'] = dict(value=None if Dm is None else round(Dm['body'], 4), status='INFO',
                                     tails=None if Dm is None else Dm['tails'],
                                     knot_size=None if Dm is None else Dm['knot_size'],
                                     note="the turnaround's front bow (the outfit's part masks) against %s the same "
                                          "way: body IoU (tails and the knot's size beside): the reference's "
                                          "consistency with the turnaround" % auth)
        if lauth != auth:
            Dl = compare(Dp, Rl)
            T['bow']['refcheck_lines'] = Dl and {k: Dl[k] for k in ('ours', 'ref')}
    return T, C
