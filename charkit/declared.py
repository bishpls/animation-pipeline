"""Declared checks (tool/sweep, 2026-09-30): a check as a declaration (the piece, its views, a family, the family's
parameters, the limits) instead of measuring code, and calibrated by one generic path (`python -m charkit calibrate`),
so a new flag needs neither a measure nor a calibration adapter written for it. Most of the checks written on
2026-09-30 fell into a few families; each is one function here, built on the QA's own primitives (charkit.pieceqa's
masks, edges, closing and spikes), so a declared check measures as the hand-written ones it replaces.

Families (FAMILIES; lengths in L, ours against the design's own drawn piece measured the same way):
  shape_iou    the piece's shape against the drawn piece's as qa3d.sheet_pieces measures it (iou_tol, piece_<id>'s
               per-view value: the guard's measure), or with close the plain IoU of both closed (higher is better)
  width        the piece's median row width over its middle columns' rows (pieceqa.edges): ours over the design's,
               less one, |.| (params mid, round); mode 'rms': the widths at tenths down the piece, RMS of the difference
  edge         a piece's top or bottom edge (the median of its middle columns' first or last rows, pieceqa.edges) in L
               from the eye line: |ours - design| (params edge, mid, round)
  tips         spikes on the piece's silhouette (pieceqa.spikes: what an opening by a disk of radius r L cuts off that
               stands min_depth L out): the deepest one's depth beyond the design's deepest; graded the worse of that and
               the count beyond the design's (one more: WARN, two: FAIL)
  angle        the piece's principal axis (its pixels' PCA) in degrees from vertical: |ours - design| (mod 180)
  ink_between  the boundary between pieces a and b with no ink between (L): ours drawn with the build's outlines
               (our_lines), the design's drawn masks less its line class; ours beyond the design's
  position     a piece's centroid against the design's (L from the eye line and the midline): the larger of |dx|, |dz|
               (params axis 'x', 'z' or 'both')
  area         the piece's pixels over the drawn piece's, |ratio - 1| (a size: the wrist cuffs 1.5-2.4x the drawn)
  ink_inside   the lines drawn inside a piece (its creases, folds, pleats), or along a region's outline (edge): 1 -
               recall of the drawn skeleton by ours within tol; relative: within the region's own span (remap_rows)
  stair        a piece's stepped hem band (the skirt's and the flaps' dark staircase): the face/band boundary traced
               as risers and treads (stair_of); measure 'corner' (how far its corners are from square, degrees),
               'crossed' (the zigzag's steps a fold crosses: Michael, 2026-10-01, "a fold bends a step that spans it") or 'spacing'
               (our folds' spacing where they meet the band against the drawn steps' widths, |ratio - 1|); our folds
               are our lines and our geometry's (our_folds)

A declaration is a dict in a module-level literal DECLARED_CHECKS = [...] in any charkit module (read with ast,
nothing imported: the gate and `calibrate` read a tree's without running it; no central list to conflict on):
  check     the name; '{view}' expands per view (shorts_{view}_width)
  family    one of FAMILIES
  piece     the outfit graph's piece id (pieceqa.members on our labels; the drawn masks' VIEW__PIECE); ink_between: [a, b]
  views     where it is measured (default the four; a view the design doesn't draw the piece in is skipped)
  params    the family's parameters; fold: the drawn pieces we don't build folded into the piece (bodymeasure.folded:
            the bow's drawn tails into the bow, as our bow object has them); round: the value's decimals; drawn: the
            drawn piece to compare against in place of `piece`'s (a region we build as part of a piece: the skirt's
            cream panel); ours_cls: our piece's pixels of that model-sheet class only (pieceqa.our_classes: 'cream',
            the panel's material on our skirt)
  limits    [pass, warn] (within: PASS, WARN; beyond: FAIL), or a reference to a part's own table
            ('charkit.pieceqa.LIMITS.rows'); better 'lower' (default; shape_iou 'higher') or 'higher' (at least)
  part      the QA part that reports it: 'declared' (default: this module's part) or a part that evaluates its own
            (charkit.pieceqa's piece_details: evaluate_part)
  flag      Michael's flag it was built from (registry.flag_check: the gate blocks on its regressions)
  note      what it measures (qa.json's note)
  calibrate its calibration: {known_bad, baseline [floor generators], probes, shape [guarding shape checks], kind,
            no_known_bad}. charkit.calibrate derives the registry entry from it (entries()), with the part's label
            stand-in as the adapter (ADAPTERS: Declared for 'declared'), so `charkit calibrate CHECK` runs the triple
  extra     `CHARKIT_DECLARED=FILE.json` (a list of declarations) adds declarations from outside the tree: a draft flag
            measured and calibrated before it is committed (`charkit calibrate CHECK --declared FILE.json`)

    T, C = declared.evaluate(decls, ctx)          # ctx: inputs(B, design) or a part's own (pieceqa.measure's)
"""
import ast, json, os

import numpy as np

from .registry import flag_check, qa_part

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = 'DECLARED_CHECKS'
VIEWS = ('front', 'three_quarter', 'profile', 'back')
ENV = 'CHARKIT_DECLARED'
ADAPTERS = {                          # a part -> its calibration stand-in (module, class): the generic one for 'declared'
    'declared': ('charkit.declared', 'Declared'),
    'piece_details': ('charkit.calib.details', 'Details'),
    'collar_flags': ('charkit.calib.labels', 'Garments'),
    'sheet_pieces': ('charkit.calib.labels', 'Pieces'),
}
WHY_OURS = 'ours shows too little of the piece here'


# ------------------------------------------------------------------------------------------------------- declarations
def _literal(src, name=NAME):
    if name not in src:
        return None
    for node in ast.parse(src).body:
        targets = node.targets if isinstance(node, ast.Assign) else []
        if any(getattr(t, 'id', None) == name for t in targets):
            from .calibrate import _lit
            return _lit(node.value)
    return None


def declarations(root=None, files=None):
    """every declaration: each charkit module's DECLARED_CHECKS (charkit/*.py, in name order; root: another tree's
    directory, files: {relative path: source} as calibrate.read_tree gives a git revision's), then CHARKIT_DECLARED's
    -> [dict], each with 'module'."""
    if files is None:
        kit = os.path.join(root, 'charkit') if root else HERE
        files = {}
        for f in sorted(os.listdir(kit)):
            if f.endswith('.py'):
                files[os.path.join('charkit', f)] = open(os.path.join(kit, f), encoding='utf-8').read()
    out = []
    for path, src in sorted(files.items()):
        if not path.endswith('.py') or NAME not in src:
            continue
        for d in _literal(src) or ():
            out.append(dict(d, module='charkit.' + os.path.basename(path)[:-3]))
    extra = os.environ.get(ENV)
    if extra and os.path.exists(extra):
        for d in json.load(open(extra)):
            out.append(dict(d, module='file:' + os.path.basename(extra)))
    return out


def expand(decls):
    """the declarations per view: [(check name, view, declaration)] in their order."""
    out = []
    for d in decls:
        for v in d.get('views') or VIEWS:
            out.append((d['check'].format(view=v), v, d))
    return out


def calibration_entries(decls=None):
    """the calibration registry entries the declarations carry (charkit.calibrate.entries reads them after the
    calib modules' own, which keep their priority): the check (its '{view}' a wildcard), its part and that part's
    stand-in as the adapter, and its `calibrate` block -> [dict]."""
    out = []
    for d in declarations() if decls is None else decls:
        cal = d.get('calibrate')
        if not cal:
            continue
        part = d.get('part', 'declared')
        mod, cls = ADAPTERS.get(part, ADAPTERS['declared'])
        out.append(dict(cal, check=d['check'].replace('{view}', '*'), part=part, adapter=cls, module=mod,
                        better=d.get('better', 'lower'), declared=d.get('module')))
    return out


# ------------------------------------------------------------------------------------------------------------ families
def _edges(m, ppl, mid):
    from . import pieceqa
    if not m.any():
        return None
    return pieceqa.edges(pieceqa.clean(m, ppl), tuple(mid))


def shape_iou(Mo, Md, ctx, metric='iou_tol', close=False, round_=4):
    """the piece's shape against the drawn piece's in a view: as qa3d.sheet_pieces measures it (the default:
    bodymeasure.piece_shapes, the drawn masks folded into the pieces we build and same-coloured overlaps left out;
    metric 'iou_tol' is what piece_<id>'s `views` report and the anti-gaming guard reads, or 'iou', 'f'), or with
    close, the plain IoU of both masks closed (pieceqa.clean: collarqa's collar_back_iou way)."""
    from . import bodymeasure, pieceqa
    ppl = ctx['ppl']
    Md = fit(Md, Mo.shape)
    if Md.sum() < pieceqa.MIN_PX:
        return None
    if close or ctx.get('graph') is None:
        if close:
            Md, Mo = pieceqa.clean(Md, ppl), (pieceqa.clean(Mo, ppl) if Mo.any() else Mo)
        u = (Mo | Md).sum()
        return dict(value=round(float((Mo & Md).sum()) / u, round_) if u else None, ours=int(Mo.sum()),
                    design=int(Md.sum()))
    S = bodymeasure.piece_shapes({ctx['view']: ctx['lab']}, ctx['names'], ctx['masks'], ctx['graph'], ctx['spec'], ppl)
    r = ((S.get(ctx['piece']) or {}).get('views') or {}).get(ctx['view'])
    if r is None:
        return None
    return dict(value=round(float(r[metric]), round_), ours=r['px'][0], design=r['px'][1])


def width(Mo, Md, ctx, mid=(0.2, 0.8), mode='ratio', round_=3):
    """the piece's median row width (pieceqa.edges over its middle columns), ours over the design's less one; 'rms':
    the RMS of the row widths at tenths of the way down the piece."""
    ppl = ctx['ppl']
    ed = _edges(Md, ppl, mid)
    if ed is None:
        return None
    eo = _edges(Mo, ppl, mid)
    if eo is None:
        return dict(value=None, why=WHY_OURS)
    if mode == 'rms':
        wo, wd = tenths(Mo, eo), tenths(Md, ed)
        d = np.array(wo) - np.array(wd)
        return dict(value=round(float(np.sqrt((d ** 2).mean())) / ppl, round_ + 1), ours=[round(w / ppl, 4) for w in wo],
                    design=[round(w / ppl, 4) for w in wd])
    zo, zd = round(eo['width'] / ppl, 4), round(ed['width'] / ppl, 4)
    return dict(value=round(abs(zo / max(zd, 1e-6) - 1), round_), ours=zo, design=zd)


def tenths(m, e):
    """a mask's row widths (px) at 0.1 .. 0.9 of the way from its top edge to its bottom edge (edges()'s rows)."""
    out = []
    for f in np.linspace(0.1, 0.9, 9):
        r = int(round(e['top'] + f * (e['bottom'] - e['top'])))
        cs = np.nonzero(m[r])[0] if 0 <= r < m.shape[0] else []
        out.append(float(np.ptp(cs) + 1) if len(cs) else 0.0)
    return out


def edge(Mo, Md, ctx, edge='bottom', mid=(0.2, 0.8), round_=4):
    """a piece's top or bottom edge in L from the eye line (pieceqa.z_of), |ours - design|."""
    from . import pieceqa
    ppl = ctx['ppl']
    ed = _edges(Md, ppl, mid)
    if ed is None:
        return None
    eo = _edges(Mo, ppl, mid)
    if eo is None:
        return dict(value=None, why=WHY_OURS)
    zo, zd = round(pieceqa.z_of(eo[edge], ppl), 4), round(pieceqa.z_of(ed[edge], ppl), 4)
    return dict(value=round(abs(zo - zd), round_), ours=zo, design=zd)


def tips(Mo, Md, ctx, r=None, min_depth=None, silhouette=True, round_=4):
    """spikes on the piece's outline (pieceqa.spikes; silhouette: only those on the figure's silhouette): the deepest
    beyond the design's deepest (L), the counts beside it; graded the worse of the depth and the count's excess."""
    from . import pieceqa
    ppl = ctx['ppl']
    if Md.sum() < pieceqa.MIN_PX:
        return None
    if Mo.sum() < pieceqa.MIN_PX:
        return dict(value=None, why=WHY_OURS)
    kw = dict(r=pieceqa.SPIKE_R if r is None else r, min_depth=pieceqa.SPIKE_MIN if min_depth is None else min_depth)
    Md, Mo = pieceqa.clean(Md, ppl), pieceqa.clean(Mo, ppl)
    fg = ctx.get('dv_fg')
    wd = pieceqa.silhouette(Md, fit(fg, Md.shape), ppl) if silhouette and fg is not None else None
    wo = pieceqa.silhouette(Mo, ctx['lab'] >= 0, ppl) if silhouette and ctx.get('lab') is not None else None
    sd, so = pieceqa.spikes(Md, ppl, where=wd, **kw), pieceqa.spikes(Mo, ppl, where=wo, **kw)
    v = round(max(0.0, so['depth'] - sd['depth']), round_)
    dn = so['n'] - sd['n']
    return dict(value=v, count=[so['n'], sd['n']], ours=so['depths'], design=sd['depths'],
                count_status='PASS' if dn <= 0 else 'WARN' if dn == 1 else 'FAIL')


def axis_angle(m):
    """a mask's principal axis in degrees from vertical (-90, 90], or None."""
    rs, cs = np.nonzero(m)
    if len(rs) < 10:
        return None
    P = np.c_[cs, rs].astype(float)
    w, U = np.linalg.eigh(np.cov((P - P.mean(0)).T))
    u = U[:, np.argmax(w)]
    a = float(np.degrees(np.arctan2(u[0], u[1])))       # (x, y-down): 0 = vertical
    a = (a + 90) % 180 - 90
    return 90.0 if a == -90 else a


def angle(Mo, Md, ctx, round_=1):
    """the piece's principal axis (degrees from vertical), |ours - design| modulo 180."""
    ad = axis_angle(Md)
    if ad is None:
        return None
    ao = axis_angle(Mo)
    if ao is None:
        return dict(value=None, why=WHY_OURS)
    d = abs(ao - ad) % 180
    return dict(value=round(min(d, 180 - d), round_), ours=round(ao, 1), design=round(ad, 1))


def ink_between(Mo, Md, ctx, round_=4):
    """the boundary between pieces a and b with no ink between: ours drawn with the build's outlines (ctx 'lines': our
    line pixels on the grid), the design's drawn masks less its line class (ctx 'cls'); ours beyond the design's (L).
    Mo, Md: pairs (a, b)."""
    from . import bodyqa, collarqa
    ppl = ctx['ppl']
    (ao, bo), (ad, bd) = Mo, Md
    ad, bd = fit(ad, ao.shape), fit(bd, ao.shape)
    if not (ad.any() and bd.any()):
        return None
    if not (ao.any() and bo.any()):
        return dict(value=None, why=WHY_OURS)
    ink_d = fit(ctx['cls'] == bodyqa.CLASS['line'], ad.shape) if ctx.get('cls') is not None else np.zeros(ad.shape, bool)
    ink_o = ctx.get('lines') if ctx.get('lines') is not None else np.zeros(ao.shape, bool)
    d_len = float(collarqa.edge_touch(ad & ~ink_d, bd & ~ink_d).sum()) / ppl
    o_len = float(collarqa.edge_touch(ao & ~ink_o, bo & ~ink_o).sum()) / ppl
    return dict(value=round(max(0.0, o_len - d_len), round_), ours=round(o_len, 4), design=round(d_len, 4))


def area(Mo, Md, ctx, round_=3, ref='silhouette'):
    """the piece's size: its pixels over the drawn piece's, less one, |.| (ours / design reported as `ratio`). The
    visible pixels both sides (piece_<id>'s same-colour rule, tried, reads the design moved 1-2 px 0.23 off itself: the
    drawn skirt's mask runs under the drawn cuff, so it takes from ours alone). ref 'silhouette' (the default): the
    drawn piece as our surfaces would draw it, its outline included (bodymeasure.drawn_labels: the drawing's lines inside
    the figure given to the nearest piece; our geometry has no ink between pieces, so its pixels compare with the drawn
    piece's silhouette: the wrist cuffs' silhouette is ~1.23x their fill); 'fill': the outfit's piece mask alone."""
    from . import pieceqa
    Md = fit(Md, Mo.shape)
    if Md.sum() < pieceqa.MIN_PX:
        return None
    fill = int(Md.sum())
    if ref == 'silhouette' and ctx.get('silhouette') is not None:
        S = ctx['silhouette']()
        if S is not None:
            Md = fit(S, Mo.shape)
    if Mo.sum() < pieceqa.MIN_PX:
        return dict(value=None, why=WHY_OURS)
    r = float(Mo.sum()) / float(Md.sum())
    return dict(value=round(abs(r - 1), round_), ours=int(Mo.sum()), design=int(Md.sum()), ratio=round(r, 3),
                fill=fill, ratio_fill=round(float(Mo.sum()) / fill, 3))


def position(Mo, Md, ctx, axis='both', round_=4):
    """the piece's centroid (L from the midline and the eye line: pieceqa.x_of, z_of) against the design's: the larger of
    |dx| and |dz| (axis 'both'), or one of them."""
    from . import pieceqa
    ppl = ctx['ppl']
    if Md.sum() < pieceqa.MIN_PX:
        return None
    if Mo.sum() < pieceqa.MIN_PX:
        return dict(value=None, why=WHY_OURS)
    c = lambda m: (lambda rs, cs: (pieceqa.x_of(cs.mean(), ppl), pieceqa.z_of(rs.mean(), ppl)))(*np.nonzero(m))
    (xo, zo), (xd, zd) = c(Mo), c(Md)
    dx, dz = abs(xo - xd), abs(zo - zd)
    v = {'x': dx, 'z': dz}.get(axis, max(dx, dz))
    return dict(value=round(float(v), round_), ours=[round(float(xo), 4), round(float(zo), 4)],
                design=[round(float(xd), 4), round(float(zd), 4)])


def _spans(R):
    """each row's first and last column of a mask (-1 where the row is empty) -> (lo, hi)."""
    any_ = R.any(1)
    lo = np.where(any_, R.argmax(1), -1)
    hi = np.where(any_, R.shape[1] - 1 - R[:, ::-1].argmax(1), -1)
    return lo, hi


def remap_rows(m, Ro, Rd):
    """a mask's pixels moved row by row from region Ro's span onto region Rd's, keeping their share across it (rows
    where either region is empty dropped): ours compared within the drawn region's frame."""
    out = np.zeros(m.shape, bool)
    (lo, ho), (ld, hd) = _spans(Ro), _spans(Rd)
    r, c = np.nonzero(m)
    ok = (lo[r] >= 0) & (ld[r] >= 0) & (ho[r] > lo[r])
    r, c = r[ok], c[ok]
    t = (c - lo[r]) / (ho[r] - lo[r])
    c2 = np.rint(ld[r] + t * (hd[r] - ld[r])).astype(int)
    k = (c2 >= 0) & (c2 < m.shape[1])
    out[r[k], c2[k]] = True
    return out


def ink_inside(Mo, Md, ctx, region=None, band=0.02, faint=True, min_len=0.1, tol=0.015, edge=False, relative=None,
               round_=3):
    """the lines drawn inside a piece (its creases, folds and pleats: tool/garments4, Michael 2026-09-30): the design's
    ink, with its fainter strokes (faint: outfit.ridges, as partqa.design_lines reads the bow's creases), inside the drawn
    region (the piece's mask, or the drawn piece `region`'s: the skirt's cream panel; closed, holes filled, its outline's
    band `band` L left out), against ours drawn with outlines and ink strokes (ctx 'lines') inside the same region and on
    our piece; each skeletonized. The share of the drawn lines' length with none of ours within `tol` L (1 - recall:
    where the lines are, not only how much; `ours` and `design` their lengths in L, `precision` the share of ours near a
    drawn one). A view whose drawn region holds under `min_len` L of lines is skipped. edge: the lines along the
    region's outline instead (a band `band` L either side of it: the folds that bound a pleat's panel), not inside it.
    relative (a class: 'cream'): where the lines lie within the region, not where the region lies: ours read inside our
    own region (our piece's pixels of that class, closed, filled), then moved row by row from its span onto the drawn
    region's at the same share across it (remap_rows), so a region drawn view-dependently (the skirt's cream panel, drawn
    face-on in three-quarter: wider than any 3D panel turned 35 degrees can show) still grades its lines' arrangement,
    and the region's own shape is the shape check's."""
    from scipy import ndimage
    from skimage.morphology import skeletonize
    from . import bodyqa, outfit
    ppl, view = ctx['ppl'], ctx['view']
    sh = Mo.shape
    R = fit(ctx['masks'].get('%s__%s' % (view, region)), sh) if region else fit(Md, sh)
    if R is None or not R.any():
        return None
    R = ndimage.binary_fill_holes(ndimage.binary_closing(R, iterations=3))
    b_ = max(1, int(round(band * ppl)))
    inner = ndimage.binary_erosion(R, iterations=b_)
    if edge:
        inner = ndimage.binary_dilation(R, iterations=b_) & ~inner
    dv = ctx.get('dv') or {}
    raw = dv.get('raw')
    if raw is None:
        return None
    ink = raw == bodyqa.CLASS['line']
    if faint and dv.get('rgb') is not None:
        ink = ink | (outfit.ridges(dv['rgb']) & (raw != bodyqa.CLASS['skin']))
    d_ = skeletonize(fit(ink, sh) & inner)
    d_len = float(d_.sum()) / ppl
    if d_len < min_len:
        return None
    lines = ctx.get('lines')
    if lines is None or not Mo.any():
        return dict(value=None, why=WHY_OURS)
    zone_o = inner
    if relative:
        clo = ctx.get('cls_ours')
        Ro = np.zeros(sh, bool)
        if clo is not None:
            h, w = min(sh[0], clo.shape[0]), min(sh[1], clo.shape[1])
            Ro[:h, :w] = clo[:h, :w] == bodyqa.CLASS[relative]
            Ro &= Mo
        if not Ro.any():
            return dict(value=None, why=WHY_OURS)
        Ro = ndimage.binary_fill_holes(ndimage.binary_closing(Ro, iterations=3))
        zone_o = ndimage.binary_erosion(Ro, iterations=b_)
        if edge:
            zone_o = ndimage.binary_dilation(Ro, iterations=b_) & ~zone_o
    o_ = skeletonize(fit(lines, sh) & zone_o & ndimage.binary_dilation(Mo, iterations=2))
    o_len = float(o_.sum()) / ppl
    if relative:
        # the drawn region's span by the same rule as ours (its pixels of that class, closed, filled): the drawn mask
        # closed takes in what lies between its parts (dark pixels under the panel's hem in three-quarter)
        cld = ctx.get('cls')
        Rs = R.copy()
        if cld is not None:
            h, w = min(sh[0], cld.shape[0]), min(sh[1], cld.shape[1])
            c_ = np.zeros(sh, bool)
            c_[:h, :w] = cld[:h, :w] == bodyqa.CLASS[relative]
            Rs = ndimage.binary_fill_holes(ndimage.binary_closing(R & c_, iterations=3))
        o_ = remap_rows(o_, Ro, Rs)
    r = tol * ppl
    near_o = ndimage.distance_transform_edt(~o_) <= r if o_.any() else np.zeros(sh, bool)
    near_d = ndimage.distance_transform_edt(~d_) <= r
    recall = float((d_ & near_o).sum()) / max(1, int(d_.sum()))
    prec = float((o_ & near_d).sum()) / max(1, int(o_.sum())) if o_.any() else 0.0
    return dict(value=round(1.0 - recall, round_), ours=round(o_len, 3), design=round(d_len, 3),
                precision=round(prec, 3))


# ------------------------------------------------------------------------------------------------- the stepped band
STAIR_GAP = 0.03          # L: the band within this of the face (the drawing's line between them: skirtqa.BAND_GAP)
STAIR_EPS = 2.0           # px: the boundary simplified to a polyline within this (skirtqa.EDGE_EPS)
STAIR_RISE = 0.015        # L: a riser at least this long (skirtqa.MIN_RISE) ...
STAIR_TREAD = 0.02        # L: ... a tread at least this long (skirtqa.MIN_TREAD); shorter pieces join their neighbours


def stair_runs(face, band, ppl, gap=STAIR_GAP, eps=STAIR_EPS, min_rise=STAIR_RISE, min_tread=STAIR_TREAD,
               min_run=0.05):
    """a piece's stepped band in one view (face: the piece's pixels above its band, its drawn lines kept; band: the
    dark pixels): the face's outline (skimage find_contours, sub-pixel) where the band lies within `gap` L of it, in
    runs at least `min_run` L long, each simplified to a polyline (skirtqa.rdp, eps px) whose pieces are classed risers
    ('r': steeper than 45 degrees) or treads ('t'), consecutive ones of a class merged, and a piece shorter than its
    class's minimum (min_rise, min_tread L) joined with its neighbours (between two of the other class: the three as
    one; at a run's end: dropped), so the classes alternate. The outline, not the band's top per column (skirtqa's
    band_edge): a riser leaning over its band reads too. -> [dict(P (k, 2) the run's points (row, col), cum (k,) arc
    length px, segs [dict(k, i0, i1, a (row, col), b, len L)])]."""
    from scipy import ndimage
    from skimage.measure import find_contours
    from .skirtqa import rdp
    if not face.any() or not band.any():
        return []
    g_ = max(1.0, gap * ppl)
    hi_ = np.array(face.shape) - 1
    out = []
    for C in find_contours(np.pad(face, 1).astype(float), 0.5):
        C = C - 1
        # the band beyond the outline along its outward normal (within gap), not merely near it: a face's side edge
        # with its band diagonally below is no riser
        T = np.gradient(C, axis=0)
        Nn = np.c_[T[:, 1], -T[:, 0]] / np.maximum(1e-9, np.hypot(T[:, 0], T[:, 1]))[:, None]
        q = np.clip(np.rint(C + 1.5 * Nn).astype(int), 0, hi_)
        Nn[face[q[:, 0], q[:, 1]]] *= -1                       # (pointing out of the face)
        ok = np.zeros(len(C), bool)
        for t_ in np.arange(1.0, g_ + 0.5, 1.0):
            q = np.clip(np.rint(C + t_ * Nn).astype(int), 0, hi_)
            ok |= band[q[:, 0], q[:, 1]]
        if not ok.any():
            continue
        closed = np.allclose(C[0], C[-1])
        if closed and ok.all():
            k0 = 0
        elif closed:                                     # (start the walk where the boundary leaves the band)
            k0 = int(np.nonzero(~ok)[0][0])
            C, ok = np.roll(C[:-1], -k0, 0), np.roll(ok[:-1], -k0)
        idx = np.nonzero(ok)[0]
        for run in np.split(idx, np.nonzero(np.diff(idx) > 1)[0] + 1):
            P = C[run]
            if len(P) < 3:
                continue
            cum = np.r_[0, np.cumsum(np.hypot(*np.diff(P, axis=0).T))]
            if cum[-1] < min_run * ppl:
                continue
            keep = rdp(P[:, ::-1], eps)
            g = []
            for i0, i1 in zip(keep[:-1], keep[1:]):
                dr, dc = P[i1] - P[i0]
                k = 'r' if abs(dr) > abs(dc) else 't'
                if g and g[-1]['k'] == k:
                    g[-1]['i1'] = int(i1)
                else:
                    g.append(dict(k=k, i0=int(i0), i1=int(i1)))
            while g:
                ln = [float(np.hypot(*(P[s['i1']] - P[s['i0']]))) / ppl for s in g]
                short = [(ln[i] / (min_rise if s['k'] == 'r' else min_tread), i) for i, s in enumerate(g)
                         if ln[i] < (min_rise if s['k'] == 'r' else min_tread)]
                if not short:
                    break
                i = min(short)[1]
                if 0 < i < len(g) - 1:
                    g[i - 1:i + 2] = [dict(k=g[i - 1]['k'], i0=g[i - 1]['i0'], i1=g[i + 1]['i1'])]
                else:
                    g.pop(i)
                    # (a run's end piece dropped; neighbours of a class merged)
                h = []
                for s in g:
                    if h and h[-1]['k'] == s['k']:
                        h[-1]['i1'] = s['i1']
                    else:
                        h.append(dict(s))
                g = h
            for s in g:
                s['a'], s['b'] = P[s['i0']], P[s['i1']]
                s['len'] = float(np.hypot(*(s['b'] - s['a']))) / ppl
            if g:
                out.append(dict(P=P, cum=cum, segs=g))
    return out


def stair_creases(lines, region, runs, ppl, above=0.08, clear=2.0, min_len=0.03):
    """the folds meeting a stepped band (stair_runs'): the drawn lines inside the piece (`region`) within `above` L
    of the band's boundary but more than `clear` px from it (the boundary's own line: a riser's outline is no fold),
    as 8-connected pieces at least `min_len` L across; each one's meeting point is its pixel nearest the boundary,
    placed on the nearest run point -> [dict(at (row, col), run, i (the run point's index), d px)]."""
    from scipy import ndimage
    if lines is None or not runs:
        return []
    Pall = np.concatenate([r['P'] for r in runs])
    which = np.concatenate([np.full(len(r['P']), j) for j, r in enumerate(runs)])
    pos = np.concatenate([np.arange(len(r['P'])) for r in runs])
    seed = np.zeros(lines.shape, bool)
    ri = np.clip(np.rint(Pall).astype(int), 0, np.array(lines.shape) - 1)
    seed[ri[:, 0], ri[:, 1]] = True
    dist = ndimage.distance_transform_edt(~seed)
    zone = lines & region & (dist <= above * ppl) & (dist > clear)
    lab, n = ndimage.label(zone, np.ones((3, 3)))
    out = []
    if not n:
        return out
    from scipy.spatial import cKDTree
    tree = cKDTree(Pall)
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        rr, cc = np.nonzero(lab[sl] == i)
        rr, cc = rr + sl[0].start, cc + sl[1].start
        if max(np.ptp(rr), np.ptp(cc)) + 1 < min_len * ppl:
            continue
        k = int(np.argmin(dist[rr, cc]))
        d, j = tree.query([rr[k], cc[k]])
        out.append(dict(at=(float(rr[k]), float(cc[k])), run=int(which[j]), i=int(pos[j]), d=float(d)))
    return out


def seg_dir(P, s, trim=0.15):
    """a stair segment's direction (unit, row-col): the principal axis of its boundary points, `trim` of its length
    left out at each end (a drawn corner's rounding), else its ends' chord."""
    Q = P[s['i0']:s['i1'] + 1]
    k = int(round(trim * len(Q)))
    Q = Q[k:len(Q) - k] if len(Q) - 2 * k >= 4 else Q
    d = s['b'] - s['a']
    if len(Q) >= 4:
        _, _, vt = np.linalg.svd(Q - Q.mean(0), full_matrices=False)
        e = vt[0] * (1 if vt[0] @ d >= 0 else -1)
    else:
        e = d
    return e / max(1e-9, np.hypot(*e))


def stair_read(runs, creases, ppl, tol=0.02, margin=0.035):
    """a stepped band's numbers: each corner's departure from square (90 less the acute angle between a riser's and the
    next tread's lines, degrees), each tread a fold meets more than `margin` L inside its ends (crossed: a fold bends the
    step), each riser no fold meets within `tol` L of it (off), and the folds' spacing (L, straight across between
    consecutive meeting points along a run; meeting points within `tol` L of each other one fold) -> dict(corners, crossed, off, risers, treads,
    spacing, creases, tread_len (L))."""
    corners, crossed, off, spacing, tl = [], 0, 0, [], []
    nr = nt = nf = steps_crossed = 0
    t_, m_ = tol * ppl, margin * ppl
    for j, r in enumerate(runs):
        cum, g = r['cum'], r['segs']
        for s, u in zip(g[:-1], g[1:]):
            a, b = seg_dir(r['P'], s), seg_dir(r['P'], u)
            corners.append(90.0 - float(np.degrees(np.arccos(min(1.0, abs(a @ b))))))
        at, pts = [], []
        for x, i in sorted((cum[c['i']], c['i']) for c in creases if c['run'] == j):
            if not at or x - at[-1][-1] > t_:          # (a fold's two edges, or a line and a fold: one fold)
                at.append([x])
                pts.append([i])
            else:
                at[-1].append(x)
                pts[-1].append(i)
        at = [float(np.mean(a)) for a in at]
        nf += len(at)
        Q = np.array([r['P'][ii].mean(0) for ii in pts]) if pts else np.zeros((0, 2))
        spacing += list(np.hypot(*np.diff(Q, axis=0).T) / ppl) if len(Q) > 1 else []
        for q, s in enumerate(g):
            lo, hi = cum[s['i0']], cum[s['i1']]
            if s['k'] == 't':
                nt += 1
                tl.append(round(s['len'], 4))
                x_ = int(any(lo + m_ < x < hi - m_ for x in at))
                crossed += x_
                if 0 < q < len(g) - 1:                  # (a step of the zigzag: a riser at either end)
                    steps_crossed += x_
            else:
                nr += 1
                off += int(not any(lo - t_ <= x <= hi + t_ for x in at))
    return dict(corners=[round(c, 1) for c in corners], crossed=crossed, off=off, risers=nr, treads=nt,
                spacing=[round(float(s), 4) for s in spacing], creases=nf, tread_len=tl, steps_crossed=steps_crossed)


def stair_inputs(M, cls, lines, ppl, reach=0.4, inset=3):
    """a piece's face and band from its pixels and the model-sheet classes over them: the face the piece's pixels
    neither dark nor cream (the skirt's cream panel has no band; the drawing's lines inside it kept, so a fold doesn't
    cut it), the band the dark pixels (the class image's: the drawn masks leave the band out) with the face above
    them within `reach` L in their column (the band under the piece, not a band over it: the skirt's over a flap's
    top), our ink strokes left out of it (dark geometry: lines, not band); and the piece's inside, `inset` px in from
    the outline of it and its band (where a line is a fold, not its outline) -> (face, band, lines, inside)."""
    from scipy import ndimage
    from . import bodyqa
    sh = M.shape
    c = np.zeros(sh, int)
    h, w = min(sh[0], cls.shape[0]), min(sh[1], cls.shape[1])
    c[:h, :w] = cls[:h, :w]
    ln = fit(lines, sh) if lines is not None else np.zeros(sh, bool)
    dark = c == bodyqa.CLASS['dark']
    face = M & ~dark & (c != bodyqa.CLASS['cream'])
    face = ndimage.binary_opening(face, iterations=1)
    dark &= ~ln
    under = np.zeros(sh, bool)
    for d in range(1, max(2, int(round(reach * ppl))) + 1):
        under[d:] |= face[:-d]
    band = dark & under
    whole = ndimage.binary_closing(np.pad(M | band, 4), iterations=4)[4:-4, 4:-4]     # (closed over drawn lines)
    inside = ndimage.binary_erosion(ndimage.binary_fill_holes(whole), iterations=inset)
    return face, band, (ln if lines is not None else None), inside


def stair_of(M, cls, lines, ppl, gap=STAIR_GAP, above=0.08, tol=0.02, folds=None):
    """stair_runs, stair_creases and stair_read on a piece's mask, the classes over it, the lines (ink: the band left
    out under them) and folds (geometry's: read as folds with the lines) -> (read, runs, creases) or None (no band under
    the face)."""
    face, band, ln, inside = stair_inputs(M, cls, lines, ppl)
    runs = stair_runs(face, band, ppl, gap)
    if not runs:
        return None
    if folds is not None:
        ln = fit(folds, M.shape) | (ln if ln is not None else False)
    cr = stair_creases(ln, inside & ~band, runs, ppl, above) if ln is not None else []
    return stair_read(runs, cr, ppl, tol), runs, cr


def _pool(reads):
    """stair_read's readings over several pieces in one view, pooled."""
    out = dict(corners=[], crossed=0, off=0, risers=0, treads=0, spacing=[], creases=0, tread_len=[], steps_crossed=0)
    for r in reads:
        for k in out:
            out[k] = out[k] + r[k]
    return out


def stair(Mo, Md, ctx, measure='corner', above=0.08, tol=0.02, round_=2):
    """the stepped band (stair_of) on ours and the drawn piece (or pieces: a list, their readings pooled): ours from our
    piece's pixels, our model-sheet classes (ctx cls_ours), our drawn lines (ctx lines: outlines and ink strokes) and our
    geometry's folds (ctx folds: our_folds: the pleats' folds show as shading where the design draws lines), the
    design's from the drawn piece, its classes and its ink with its fainter strokes (outfit.ridges, skin left out: as
    ink_inside reads them). measure 'corner': the corners' median departure from square, ours beyond the design's
    (degrees); 'crossed': the zigzag's steps (treads with a riser at either end) a fold crosses (Michael, 2026-10-01:
    "our zigzag runs across a crease ... a fold bends a step that spans it"), ours beyond the design's (a count; every
    tread a fold crosses, the flat band beyond the stair too, reported beside it); 'spacing': our folds' median spacing where they meet the band against the drawn
    steps' median width (the drawn pleat widths: a step is a pleat), |ours / design - 1|. A view where no drawn piece
    shows a band under it is skipped; ours showing none: FAIL."""
    from . import bodyqa, outfit
    dv = ctx.get('dv') or {}
    raw = dv.get('raw')
    cld = ctx.get('cls')
    Mos, Mds = (Mo, Md) if isinstance(Md, (list, tuple)) else ([Mo], [Md])
    if cld is None:
        return None
    ink = (raw if raw is not None else cld) == bodyqa.CLASS['line']
    if dv.get('rgb') is not None:
        ink = ink | (outfit.ridges(dv['rgb']) & ((raw if raw is not None else cld) != bodyqa.CLASS['skin']))
    D = [stair_of(m, cld, ink, ctx['ppl'], above=above, tol=tol) for m in Mds if m is not None and m.any()]
    D = [g[0] for g in D if g is not None]
    if not D:
        return None
    d = _pool(D)
    if (measure == 'corner' and not d['corners']) or (measure == 'spacing' and not d['tread_len']):
        return None
    clo = ctx.get('cls_ours')
    O = [stair_of(m, clo, ctx.get('lines'), ctx['ppl'], above=above, tol=tol, folds=ctx.get('folds'))
         for m in Mos if clo is not None and m.any()]
    O = [g[0] for g in O if g is not None]
    if not O:
        return dict(value=None, why='ours shows no band under the piece here')
    o = _pool(O)
    if measure == 'corner':
        if not o['corners']:
            return dict(value=None, why='ours shows no step here')
        mo, md = float(np.median(o['corners'])), float(np.median(d['corners']))
        return dict(value=round(max(0.0, mo - md), round_), ours=round(mo, round_), design=round(md, round_),
                    count=[len(o['corners']), len(d['corners'])])
    if measure == 'crossed':
        # the zigzag's steps (a tread with a riser at either end) a fold crosses; count: [steps crossed, every tread
        # crossed (the flat band beyond the stair too), treads] ours, then the design's
        return dict(value=max(0, o['steps_crossed'] - d['steps_crossed']), ours=o['steps_crossed'],
                    design=d['steps_crossed'], count=[[o['steps_crossed'], o['crossed'], o['treads']],
                                                      [d['steps_crossed'], d['crossed'], d['treads']]])
    if measure == 'spacing':
        if not o['spacing']:
            return dict(value=None, why='ours shows fewer than two folds meeting the band here')
        so, sd = float(np.median(o['spacing'])), float(np.median(d['tread_len']))
        return dict(value=round(abs(so / sd - 1), round_), ours=round(so, 4), design=round(sd, 4),
                    ratio=round(so / sd, 3))
    raise KeyError(measure)


FAMILIES = dict(shape_iou=shape_iou, width=width, edge=edge, tips=tips, angle=angle, ink_between=ink_between,
                position=position, ink_inside=ink_inside, area=area, stair=stair)
HIGHER = ('shape_iou',)                 # families whose value is better higher (a declaration's `better` overrides)
LINE_FAMILIES = ('ink_between', 'ink_inside', 'stair')     # families that read our drawn lines (inputs' lines)
CLASS_FAMILIES = ('stair',)             # families that read our model-sheet classes (inputs' classes)
FOLD_FAMILIES = ('stair',)              # families that read our geometry's folds (inputs' folds: our_folds)


def grade(v, limits, better='lower'):
    p, w = limits
    if better == 'higher':
        return 'PASS' if v >= p else 'WARN' if v >= w else 'FAIL'
    return 'PASS' if v <= p else 'WARN' if v <= w else 'FAIL'


# ------------------------------------------------------------------------------------------------------------ measuring
def inputs(B, design, views=VIEWS, lines=False, classes=False, folds=False):
    """what the families read, on the design's grids (the body sheet's scale): ours z-buffered (pieceqa.our_labels: the
    calibration's stand-ins patch it), the drawn piece masks, the piece map, the design's views; with lines, our
    outline pixels per view (our_lines) -> dict, or None when the design or the outfit masks are missing."""
    from . import bodymeasure, pieceqa
    ctx = design.sheet_context()
    if 'why' in ctx:
        return None
    got = bodymeasure.piece_masks(B.spec)
    if got is None:
        return None
    masks, graph, paths = got
    for p in paths:
        design._rec(p)
    dv = design.design_views()
    O, names = pieceqa.our_labels(B, ctx['ppl'], ctx['az3'], views=tuple(v for v in views if v in dv))
    out = dict(O=O, names=names, masks=masks, pm=bodymeasure.piece_map(graph, B.spec), ppl=ctx['ppl'], dv=dv,
               graph=graph, spec=B.spec, skin=[o.name for o in B.objects(groups=('skin',))])
    if lines:
        out['lines'] = our_lines(B, ctx['ppl'], ctx['az3'], tuple(O))
    if classes:                                   # (a declaration's ours_cls: our model-sheet classes per view)
        out['cls_ours'] = pieceqa.our_classes(B, ctx['ppl'], ctx['az3'], tuple(O))
    if folds:                                     # (the stair family: our geometry's folds, as the design's lines)
        out['folds'] = our_folds(B, ctx['ppl'], ctx['az3'], tuple(O))
    return out


class _Grid:
    """the design's grid for a view (bodyqa.WIN round the eyes at ppl px per L) in world units: a frame for
    charkit.qa3d.draw (as charkit.detailqa._Window), its pixels pieceqa.our_labels' pixels."""

    def __init__(self, org, L, ppl):
        from . import bodyqa
        self.origin, self.pix = org, L / ppl
        self.win = {k: v * L for k, v in bodyqa.WIN.items()}

    def zbuffer(self, items, az, ids=False):
        from .geom import raster
        return raster.window_zbuffer(items, az, self.origin, 1.0, self.pix, self.win, ids=ids)


def our_lines(B, ppl, az3, views=VIEWS):
    """our outline pixels per view on the design's grids: the build's surfaces drawn with their outline hulls
    (charkit.qa3d.draw, numpy) and the pixels whose nearest surface is a hull -> {view: bool image}. The generic
    calibration's stand-in patches it (the drawing's own ink moved with the labels, or none for a random floor)."""
    from . import bodyqa, qa3d
    As = B.assembly
    iw = np.array(qa3d.iris_centres(B))
    az = bodyqa.azimuths(az3)
    surfs = []
    for o in B.objects():
        variant = 'masked' if o.group == 'skin' and o.has('masked') else 'eval'
        if o.has(variant):
            surfs += qa3d.surfaces(B, o, variant)
    hull = np.array([bool(s['hull']) for s in surfs] + [False])
    out = {}
    for v in views:
        fr = _Grid(bodyqa.origin(v, az[v], iw, As['centre']), float(As['L']), ppl)
        aux = {}
        qa3d.draw(B, surfs, az[v], fr, ss=1, aux=aux)
        mesh = aux['mesh']
        out[v] = hull[np.where(mesh >= 0, mesh, len(surfs))]
    return out


FOLD_DEG = 15.0          # degrees: a fold where the surface turns by at least this ...
FOLD_PX = 4              # ... between pixels this far either side (a subdivided fold turns over a few pixels)
FOLD_SIGMA = 1.5         # px: the normals smoothed first (the facets' jitter)


def fold_lines(n, own, depth, k=FOLD_PX, min_deg=FOLD_DEG, step=1.5, pix=1.0, sigma=FOLD_SIGMA):
    """the folds in a view's normal image (n (H, W, 3), own the object per pixel (-1 none), depth; smoothed by a gaussian
    sigma px: a subdivided surface's facets turn a little at every edge): along each axis the
    surface's turn between the pixels k either side, where both are the same object and continuous with the middle one
    (depths within step pixels a pixel), kept where it reaches min_deg and is the largest of its neighbours along that
    axis (thinned to the fold's line) -> bool image."""
    from scipy import ndimage
    H, W = own.shape
    c = np.cos(np.radians(min_deg))
    out = np.zeros((H, W), bool)
    if sigma:                                            # (a subdivided mesh's flat facets: their jitter smoothed out)
        m = (own >= 0).astype(float)
        w = ndimage.gaussian_filter(m, sigma)
        n = np.stack([ndimage.gaussian_filter(n[..., i] * m, sigma) for i in range(3)], -1) / np.maximum(1e-9, w)[..., None]
        n /= np.maximum(1e-9, np.linalg.norm(n, axis=-1))[..., None]
    for ax in (0, 1):
        t = np.zeros((H, W))
        a = [slice(None)] * 2
        lo, mid, hi = list(a), list(a), list(a)
        lo[ax], mid[ax], hi[ax] = slice(None, -2 * k), slice(k, -k), slice(2 * k, None)
        lo, mid, hi = tuple(lo), tuple(mid), tuple(hi)
        ok = (own[lo] == own[mid]) & (own[hi] == own[mid]) & (own[mid] >= 0) & \
            (np.abs(depth[lo] - depth[mid]) < step * k * pix) & (np.abs(depth[hi] - depth[mid]) < step * k * pix)
        d = np.abs((n[lo] * n[hi]).sum(-1))
        t[mid] = np.where(ok, 1.0 - d, 0.0)              # (1 - cos: grows with the turn)
        prev, nxt = np.roll(t, 1, ax), np.roll(t, -1, ax)
        out |= (t >= 1.0 - c) & (t >= prev) & (t >= nxt)
    return out


def our_folds(B, ppl, az3, views=VIEWS, min_deg=FOLD_DEG, k=FOLD_PX):
    """our geometry's folds per view on the design's grids (tool/garments4, the staircase): the faces z-buffered by
    their index (pieceqa.our_labels' objects), their normals, and fold_lines on them -> {view: bool image}. The skirt's
    pleat folds show in the render as its cel shading's edges, not as ink, where the design draws them as lines: the
    stair family reads them with our lines. The generic calibration's stand-in patches it as it patches our_lines."""
    from . import bodyqa, qa3d
    from .faceqa import zbuffer
    meshes, _ = qa3d.scene_objects(B)
    obj, N, own, base = [], [], [], 0
    for i, (V, T, _) in enumerate(meshes):
        V, T = np.asarray(V, float), np.asarray(T)
        if not len(T):
            continue
        n = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
        n /= np.maximum(1e-12, np.linalg.norm(n, axis=1))[:, None]
        obj.append((V, T, base + np.arange(len(T))))
        N.append(n)
        own.append(np.full(len(T), i))
        base += len(T)
    if not obj:
        return {}
    N, own = np.concatenate(N + [np.zeros((1, 3))]), np.concatenate(own + [np.array([-1])])
    As = B.assembly
    iw = np.array(qa3d.iris_centres(B))
    az = bodyqa.azimuths(az3)
    out = {}
    for v in views:
        org = bodyqa.origin(v, az[v], iw, As['centre'])
        depth, lab = zbuffer(obj, az[v], org, As['L'], 1.0 / ppl, bodyqa.WIN)
        kk = np.where(lab >= 0, lab, base)
        out[v] = fold_lines(N[kk], own[kk], np.where(np.isfinite(depth), depth, 0.0), k, min_deg,
                            pix=As['L'] / ppl)
    return out


def silhouette(I, view, pid):
    """the drawn piece's silhouette in a view: its pixels in the drawing drawn as our label image
    (bodymeasure.drawn_labels, cached on I: the drawing's lines inside the figure given to the nearest piece), or None
    when the inputs lack the outfit graph."""
    from . import bodymeasure
    if I.get('graph') is None or I.get('dv') is None:
        return None
    if '_drawn' not in I:
        names = I['names']
        skin = I.get('skin') or [n for n in names if 'skin' in n]
        I['_drawn'] = bodymeasure.drawn_labels(I['masks'], I['graph'], I['pm'], names, I['dv'], skin,
                                               [n for n in names if n.startswith('hair')])
    got = I['_drawn'].get(view)
    if got is None:
        return None
    idx = {n: i for i, n in enumerate(I['names'])}
    return bodymeasure.member_mask(got[0], idx, I['pm'].get(pid, []))


def fit(m, shape):
    """a mask cropped or padded to shape (the drawn masks against our label image's grid)."""
    out = np.zeros(shape, bool)
    h, w = min(shape[0], m.shape[0]), min(shape[1], m.shape[1])
    out[:h, :w] = m[:h, :w]
    return out


def limits_of(d):
    """a declaration's [pass, warn]: a list, or a reference 'charkit.MODULE.NAME.KEY' to a part's own limits (a
    ported check grades by its part's table: pieceqa's LIMITS['rows'])."""
    L = d['limits']
    if not isinstance(L, str):
        return L
    import importlib
    ks = L.split('.')
    for i in range(len(ks), 0, -1):
        try:
            x = importlib.import_module('.'.join(ks[:i]))
        except ImportError:
            continue
        for k in ks[i:]:
            x = x[k] if isinstance(x, dict) else getattr(x, k)
        return x
    raise KeyError(L)


def evaluate(decls, I):
    """the declarations measured on the inputs I (inputs(), or a part's own: O, names, masks, pm, ppl, dv, lines?) ->
    (table {check: dict(ours, design)}, checks {check: qa.json's dict}). A view the design doesn't draw the piece in, or
    without our labels, is skipped (as the hand-written checks skip it); ours missing there: FAIL with why."""
    from . import pieceqa
    T, C = {}, {}
    if I is None:
        return T, C
    O, names, masks, pm, ppl, dv = I['O'], I['names'], I['masks'], I['pm'], I['ppl'], I['dv']
    for name, view, d in expand(decls):
        if view not in O:
            continue
        lab = O[view]['lab']
        pieces = d['piece'] if isinstance(d['piece'], (list, tuple)) else [d['piece']]
        if any(p not in pm for p in pieces):
            continue
        params = dict(d.get('params') or {})
        M = masks
        if params.pop('fold', False) and I.get('graph') is not None:      # (the drawn pieces we don't build folded in)
            from .bodymeasure import folded
            M = folded(masks, I['graph'], pm)
        drawn = params.pop('drawn', None)                 # (a region of the piece: the drawn piece compared)
        Md = [M.get('%s__%s' % (view, drawn or p)) for p in pieces]
        if any(m is None for m in Md):                    # (the design doesn't draw it here)
            continue
        Mo = [pieceqa.members(lab, names, pm, p) for p in pieces]
        oc = params.pop('ours_cls', None)
        if oc is not None:                                # (our piece's pixels of one class: its material there)
            from . import bodyqa
            cl = (I.get('cls_ours') or {}).get(view)
            if cl is None:
                continue
            Mo = [m & (cl[:m.shape[0], :m.shape[1]] == bodyqa.CLASS[oc]) for m in Mo]
        ctx = dict(ppl=ppl, view=view, lab=lab, dv_fg=(dv.get(view) or {}).get('fg'), cls=(dv.get(view) or {}).get('cls'),
                   dv=dv.get(view),
                   lines=(I.get('lines') or {}).get(view), piece=pieces[0], names=names, masks=masks,
                   cls_ours=(I.get('cls_ours') or {}).get(view), folds=(I.get('folds') or {}).get(view),
                   graph=I.get('graph'), spec=I.get('spec'))
        ctx['silhouette'] = (lambda v=view, ps=pieces: silhouette(I, v, ps[0]))
        fam = FAMILIES[d['family']]
        if 'round' in params:
            params['round_'] = params.pop('round')
        r = fam(Mo if len(pieces) > 1 else Mo[0], Md if len(pieces) > 1 else Md[0], ctx, **params)
        if r is None:
            continue
        better = d.get('better') or ('higher' if d['family'] in HIGHER else 'lower')
        if r.get('value') is None:
            c = {'value': None, 'status': 'FAIL', 'why': r.get('why') or WHY_OURS}
        else:
            st = grade(r['value'], limits_of(d), better)
            if r.get('count_status'):
                st = pieceqa.worst(st, r['count_status'])
            c = {'value': r['value'], 'status': st, 'ours': r.get('ours'), 'design': r.get('design')}
            for k in ('count', 'ratio', 'fill', 'ratio_fill'):
                if k in r:
                    c[k] = r[k]
            if d.get('note'):
                c['note'] = d['note']
            T[name] = dict(ours=r.get('ours'), design=r.get('design'))
        if d.get('flag'):
            flag_check(c, d['flag'])
        C[name] = c
    return T, C


def evaluate_part(part, I, decls=None):
    """a part's own declarations (part == `part`) measured on its inputs -> (table, checks)."""
    ds = [d for d in (declarations() if decls is None else decls) if d.get('part', 'declared') == part]
    return evaluate(ds, I) if ds else ({}, {})


@qa_part('declared', order=1790, table='declared')
def declared(B, design=None, out=None):
    """the declared checks of no other part (DECLARED_CHECKS with part 'declared', and CHARKIT_DECLARED's): each family
    on our labels against the drawn pieces. Nothing declared: nothing measured."""
    ds = [d for d in declarations() if d.get('part', 'declared') == 'declared']
    if not ds:
        return None, {}
    views = tuple(v for v in VIEWS if any(v in (d.get('views') or VIEWS) for d in ds))
    I = inputs(B, design, views, lines=any(d['family'] in LINE_FAMILIES for d in ds),
               classes=any({'ours_cls', 'relative'} & set(d.get('params') or {}) or d['family'] in CLASS_FAMILIES
                           for d in ds),
               folds=any(d['family'] in FOLD_FAMILIES for d in ds))
    if I is None:
        return None, {d['check'].format(view=v): {'status': 'SKIPPED', 'why': 'no design sheet or outfit masks'}
                      for d in ds for v in (d.get('views') or VIEWS)}
    return evaluate(ds, I)


# ------------------------------------------------------------------------------------------------- the generic stand-in
def _calib_base():
    from .calib.details import Details
    return Details


class Declared(_calib_base()):
    """the generic calibration stand-in for the 'declared' part: charkit.calib.details.Details (calib.labels.Garments:
    the drawn piece masks as our labels, moved 1-2 px or a random floor's; the drawn band's overhang handed to the
    jacket, the drawing's classes moved with the labels), and our outline pixels (our_lines) the drawing's own ink moved
    with the labels for the design, none for a floor (a random stand-in has no line between its pieces)."""
    part = 'declared'

    def patches(self, L, kind='design', arg=None):
        import sys
        from .calib.labels import _shift
        from . import bodyqa
        line = bodyqa.CLASS['line']

        def drawn(v):
            # the drawing's lines as it draws them: its ink, and its fainter strokes (a crease drawn in a shade:
            # outfit.ridges; ink_inside reads both), skin left out
            from . import outfit
            d = self.dv.get(v) or {}
            raw = d.get('raw')
            if raw is None:
                return self.cls[v] == line
            m = raw == line
            if d.get('rgb') is not None:
                m = m | (outfit.ridges(d['rgb']) & (raw != bodyqa.CLASS['skin']))
            return fit(m, self.cls[v].shape)

        def lines(B, ppl, az3, views=VIEWS):
            if kind == 'design':
                return {v: _shift(drawn(v), arg[0], arg[1], False) for v in views if v in self.cls}
            return {v: np.zeros(self.cls[v].shape, bool) for v in views if v in self.cls}

        def folds(B, ppl, az3, views=VIEWS, **kw):
            return lines(B, ppl, az3, views)            # (the drawing draws its folds as lines)
        return super().patches(L, kind, arg) + [(sys.modules[__name__], 'our_lines', lines),
                                                (sys.modules[__name__], 'our_folds', folds)]
