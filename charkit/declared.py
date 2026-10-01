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


def orientation(sk, s=1.5):
    """a skeleton's direction at each pixel, radians in [0, pi) (rows down, columns right): the structure tensor of the
    skeleton mask, whose gradient runs across the stroke, turned a quarter."""
    from scipy import ndimage
    f = ndimage.gaussian_filter(sk.astype(float), 1.0)
    gy, gx = np.gradient(f)
    Jxx, Jyy, Jxy = (ndimage.gaussian_filter(a, s) for a in (gx * gx, gy * gy, gx * gy))
    return (0.5 * np.arctan2(2 * Jxy, Jxx - Jyy) + np.pi / 2) % np.pi


_LOCKS = {}


def lock_image(spec, view, shape):
    """the splitter's lock image in a view (the produced hair_split, charkit.hairsplit) on the design grid, or None."""
    import os
    from . import manifest
    p = manifest.produced(spec, 'hair_split', log=lambda *a: None)
    z = os.path.splitext(p)[0] + '.npz' if p else None
    if not z or not os.path.exists(z):
        return None
    key = (z, os.path.getmtime(z))
    if key not in _LOCKS:
        from .geom.hairink import split_locks
        _LOCKS.clear()
        _LOCKS[key] = split_locks(spec)
    lock = _LOCKS[key].get(view)
    if lock is None:
        return None
    out = np.zeros(shape, lock.dtype)
    h, w = min(shape[0], lock.shape[0]), min(shape[1], lock.shape[1])
    out[:h, :w] = lock[:h, :w]
    return out


def lock_walls(spec, view, shape):
    """the splitter's lock boundaries in a view on the design grid (geom.hairink.lock_boundaries), or None."""
    from .geom.hairink import lock_boundaries
    lock = lock_image(spec, view, shape)
    return None if lock is None else lock_boundaries(lock)


def flow(sk, ppl, scale=0.03):
    """the drawn hair's flow on a design grid: its strokes' directions (orientation(), doubled angles) spread by a
    normalised Gaussian convolution at `scale` L -> (direction radians [0, pi), coherence 0..1, stroke density)."""
    from scipy import ndimage
    th = orientation(sk)
    w = sk.astype(float)
    s = max(1.0, scale * ppl)
    g = ndimage.gaussian_filter(w, s)
    c = ndimage.gaussian_filter(w * np.cos(2 * th), s) / np.maximum(g, 1e-9)
    n = ndimage.gaussian_filter(w * np.sin(2 * th), s) / np.maximum(g, 1e-9)
    return (0.5 * np.arctan2(n, c)) % np.pi, np.hypot(c, n), g


def strokes(Mo, Md, ctx, measure='density', strokes='strand', ours='ink', wall=0.012, tol=0.015, near=0.04,
            scale=0.06, edge_o=0.01, min_len=0.1, min_stroke=0.02, flow_scale=0.03, coherent=0.6, min_ours=0.05,
            round_=3):
    """the strokes drawn inside the hair's mass (tool/hairstrokes, Michael 2026-10-01: "detail in the bulk of the mass":
    strand lines and partial separations), against ours. The design's: its lines (the line class and the fainter
    strokes, hairflagqa.drawn_lines) skeletonized inside the mass (hairflagqa.design_side's keep: off the hair's outline,
    clear of the buns, the ahoge and the clips), pieces shorter than `min_stroke` L dropped (geom.hairink.drawn_strokes:
    the tracer's own reading); strokes 'strand' leaves out those within `wall` L of a boundary between two of the
    splitter's locks (the lock lines: the shells' outlines are the geometry's), 'all' keeps them. Ours: our ink strokes
    (ours 'ink': ctx 'ink', a piece's ink slot) or every line of ours (ours 'lines': outlines too) inside our hair's mass
    (off our outline by `edge_o` L), skeletonized.

    The turnaround draws its strand texture view by view (tool/hairstrokes: strokes placed from one view add 0.00-0.01
    to the recall in the others), so one 3D set of strokes matches each view's exact strokes only where it was taken
    from that view; the measures are the flag's intent in every view:
      density   the drawn strokes' and ours' density fields (length per area, a Gaussian at `scale` L, over both
                masses): the L1 difference over their sum (0 the same, 1 none where the other has them): strokes where
                the drawing has them, as many, at the scale of a lock (the drawn lines lie about 0.04 L apart, so a
                nearest-line recall at 0.04 L reads strokes moved at random 0.62-0.74)
      presence  the share of the drawn strokes' length with none of ours within `near` L (1 - recall)
      place     the same within `tol` L (where exactly: the view's own strokes; its cost in the other views)
      dir       the median angle (degrees) between our strokes and the drawn hair's flow (flow(): every drawn line inside
                the mass, lock lines included, at `flow_scale` L) where that flow is coherent (>= `coherent`): our
                strokes run with the hair
      extra     the share of our strokes' length with no drawn line (any: lock lines and the outline included) within
                `near` L (1 - precision: strokes where the drawing has none)
    A view whose drawn mass holds under `min_len` L of strokes is skipped; dir with under `min_ours` L of ours reads
    FAIL (too little of ours to read)."""
    from scipy import ndimage
    from skimage.morphology import skeletonize
    from . import hairflagqa
    from .geom.hairink import drawn_strokes
    ppl, view = ctx['ppl'], ctx['view']
    D = ctx.get('hair_D')
    if D is None or view not in D['keep']:
        return None
    sh = Mo.shape
    keep_d = fit(D['keep'][view], sh)
    lines_d = fit(D['lines'][view], sh)
    sk_d = drawn_strokes(lines_d, keep_d, ppl, None, 'all', wall, min_stroke)
    want = sk_d if strokes == 'all' else drawn_strokes(lines_d, keep_d, ppl, lock_image(ctx['spec'], view, sh),
                                                        strokes, wall, min_stroke)
    d_len = float(want.sum()) / ppl
    if d_len < min_len:
        return None
    src = ctx.get('ink') if ours == 'ink' else ctx.get('lines')
    if src is None or Mo.sum() < 12:
        return dict(value=None, why=WHY_OURS)
    other = ctx.get('hair_other')
    other = fit(other, sh) if other is not None else np.zeros(sh, bool)
    solid = ndimage.binary_fill_holes(ndimage.binary_closing(Mo | other, iterations=2))
    keep_o = ndimage.distance_transform_edt(solid) > edge_o * ppl
    if other.any():
        keep_o &= ndimage.distance_transform_edt(~other) > hairflagqa.CLEAR * ppl
    o_ = skeletonize(fit(src, sh) & keep_o & Mo)
    o_ &= ndimage.binary_dilation(keep_d, iterations=int(round(near * ppl)))      # (ours over the drawn mass)
    o_len = float(o_.sum()) / ppl
    dist_o = ndimage.distance_transform_edt(~o_) if o_.any() else np.full(sh, np.inf)
    all_d = skeletonize(lines_d)                       # (extra: near any drawn line, the hair's outline included)
    dist_d = ndimage.distance_transform_edt(~all_d) if all_d.any() else np.full(sh, np.inf)
    nwant = max(1, int(want.sum()))
    # the density fields: each stroke set's length per area at `scale` L (a normalised Gaussian over the masses), their
    # L1 difference over their sum (0 the same strokes, 1 none where the other has them)
    zone = ndimage.binary_dilation(keep_d | (keep_o & Mo), iterations=2)
    g = lambda m: ndimage.gaussian_filter(m.astype(float), max(1.0, scale * ppl)) * zone
    Dd, Do = g(want), g(o_)
    den = float((Dd + Do).sum())
    dens = float(np.abs(Do - Dd).sum()) / den if den > 0 else 1.0
    pres = float((want & (dist_o <= near * ppl)).sum()) / nwant
    place = float((want & (dist_o <= tol * ppl)).sum()) / nwant
    extra = float((o_ & (dist_d > near * ppl)).sum()) / max(1, int(o_.sum())) if o_.any() else 0.0
    ang = None
    if o_len >= min_ours:
        fth, coh, _ = flow(sk_d, ppl, flow_scale)
        m = o_ & (coh >= coherent)
        if m.sum() >= min_ours * ppl:
            dd = np.abs(orientation(o_)[m] - fth[m]) % np.pi
            ang = float(np.degrees(np.median(np.minimum(dd, np.pi - dd))))
    rec = dict(ours=round(o_len, 3), design=round(d_len, 3), recall=round(pres, 3), place=round(place, 3),
               precision=round(1.0 - extra, 3) if o_.any() else None, dir=None if ang is None else round(ang, 1),
               density=round(dens, 3))
    if measure == 'density':
        return dict(rec, value=round(dens, round_))
    if measure == 'presence':
        return dict(rec, value=round(1.0 - pres, round_))
    if measure == 'place':
        return dict(rec, value=round(1.0 - place, round_))
    if measure == 'dir':
        if ang is None:
            return dict(rec, value=None, why='too little of our strokes where the drawn flow is clear')
        return dict(rec, value=round(ang, 1))
    if measure == 'extra':
        return dict(rec, value=round(extra, round_))
    raise KeyError(measure)


FAMILIES = dict(shape_iou=shape_iou, width=width, edge=edge, tips=tips, angle=angle, ink_between=ink_between,
                position=position, ink_inside=ink_inside, area=area, strokes=strokes)
HIGHER = ('shape_iou',)                 # families whose value is better higher (a declaration's `better` overrides)
LINE_FAMILIES = ('ink_between', 'ink_inside', 'strokes')     # families that read our drawn lines (inputs' lines)
HAIR = 'hair'                           # the hair as a piece: our hair_* objects, the drawing's hair class (no graph piece)
HAIR_OTHER = ('hair_bun', 'hair_ahoge')  # our hair objects that aren't the mass (with the clips: hairflagqa's `other`)


def grade(v, limits, better='lower'):
    p, w = limits
    if better == 'higher':
        return 'PASS' if v >= p else 'WARN' if v >= w else 'FAIL'
    return 'PASS' if v <= p else 'WARN' if v <= w else 'FAIL'


# ------------------------------------------------------------------------------------------------------------ measuring
def inputs(B, design, views=VIEWS, lines=False, classes=False, hair=False):
    """what the families read, on the design's grids (the body sheet's scale): ours z-buffered (pieceqa.our_labels: the
    calibration's stand-ins patch it), the drawn piece masks, the piece map, the design's views; with lines, our
    outline pixels per view (our_lines); with hair, the hair as a piece (HAIR: our hair_* objects against the drawing's
    hair class, VIEW__hair) and hairflagqa's design side (hair_D: the mass's inside, its drawn lines) -> dict, or None
    when the design or the outfit masks are missing."""
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
    if hair:
        _with_hair(B, design, out)
    if lines:
        out['lines'] = our_lines(B, ctx['ppl'], ctx['az3'], tuple(O))
        if hair:
            out['ink'] = our_ink(B, ctx['ppl'], ctx['az3'], tuple(O))
    if classes:                                   # (a declaration's ours_cls: our model-sheet classes per view)
        out['cls_ours'] = pieceqa.our_classes(B, ctx['ppl'], ctx['az3'], tuple(O))
    return out


def _with_hair(B, design, I):
    """the hair as a piece in the inputs I (in place): pm[HAIR] our hair_* objects, masks VIEW__hair the drawing's hair
    class in its figure (hairflagqa.drawn_hair), hair_D hairflagqa's design side (None without the hair truth), and per
    view our hair objects that aren't the mass (HAIR_OTHER) with the clips (hair_other, from the labels: read when
    measured, so a stand-in's labels give theirs)."""
    from . import hairflagqa
    names = I['names']
    I['pm'] = dict(I['pm'], **{HAIR: [(n, None) for n in names if n.startswith('hair_')]})
    masks = dict(I['masks'])
    for v, d in I['dv'].items():
        masks['%s__%s' % (v, HAIR)] = hairflagqa.drawn_hair(d)
    I['masks'] = masks
    I['hair_D'] = hairflagqa.design_inputs(B, design)[0]
    oth = [(n, None) for n in names if n.startswith(HAIR_OTHER)] + \
        [(o.name, None) for o in B.objects(groups=('accessory',)) if o.name in names]
    I['hair_other_members'] = oth


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
    (charkit.qa3d.draw, numpy) and the pixels whose nearest surface is a hull (an ink stroke's too) -> {view: bool
    image}. The generic calibration's stand-in patches it (the drawing's own ink moved with the labels, or none for a
    random floor)."""
    return _line_images(B, ppl, az3, tuple(views))


def our_ink(B, ppl, az3, views=VIEWS):
    """our ink strokes' pixels per view on the design's grids (a piece's ink slot, qa3d.is_ink: the creases, the
    hair's strokes), drawn at least a pixel wide where nothing of ours is nearer (a stroke thinner than a pixel still
    shows, as the drawing's faint strokes do: geom.raster's thin labels), without the outlines -> {view: bool image}.
    The stand-in patches it as it does our_lines."""
    def make():
        from . import bodyqa, qa3d
        from .geom import raster
        As = B.assembly
        iw = np.array(qa3d.iris_centres(B))
        az = bodyqa.azimuths(az3)
        items, ink = [], []
        for o in B.objects():
            variant = 'masked' if o.group == 'skin' and o.has('masked') else 'eval'
            if not o.has(variant):
                continue
            for s_ in qa3d.surfaces(B, o, variant):
                k = len(items)
                is_ink = bool(s_['hull']) and len(s_['slots']) > 0 and \
                    all(qa3d.is_ink(o.materials[int(t)]) for t in np.unique(s_['slots']))
                items.append((s_['V'], s_['T'], k, s_['cull']))
                if is_ink:
                    ink.append(k)
        out = {}
        for v in views:
            if not ink:
                out[v] = None
                continue
            org = bodyqa.origin(v, az[v], iw, As['centre'])
            _, lab = raster.window_zbuffer(items, az[v], org, float(As['L']), 1.0 / ppl, bodyqa.WIN, thin=tuple(ink))
            out[v] = np.isin(lab, ink)
        shape = next((x.shape for x in out.values() if x is not None), None)
        return {v: (x if x is not None else np.zeros(shape or (1, 1), bool)) for v, x in out.items()}
    return B.memo(('declared_ink', float(ppl), float(az3), tuple(views)), make)


def _line_images(B, ppl, az3, views):
    def make():
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
    return B.memo(('declared_lines', float(ppl), float(az3), views), make)


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
                   cls_ours=(I.get('cls_ours') or {}).get(view),
                   graph=I.get('graph'), spec=I.get('spec'))
        ctx['silhouette'] = (lambda v=view, ps=pieces: silhouette(I, v, ps[0]))
        if HAIR in pieces:                                # (the hair as a piece: its design side, our non-mass parts)
            from .bodymeasure import member_mask
            ctx['hair_D'] = I.get('hair_D')
            ctx['ink'] = (I.get('ink') or {}).get(view)
            ctx['hair_other'] = member_mask(lab, {n: i for i, n in enumerate(names)}, I.get('hair_other_members') or [])
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
            for k in ('count', 'ratio', 'fill', 'ratio_fill') + (('recall', 'place', 'precision', 'dir', 'density') if d['family'] == 'strokes' else ()):
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
               classes=any({'ours_cls', 'relative'} & set(d.get('params') or {}) for d in ds),
               hair=any(HAIR in (d['piece'] if isinstance(d['piece'], (list, tuple)) else [d['piece']]) for d in ds))
    if I is None:
        return None, {d['check'].format(view=v): {'status': 'SKIPPED', 'why': 'no design sheet or outfit masks'}
                      for d in ds for v in (d.get('views') or VIEWS)}
    return evaluate(ds, I)


# ------------------------------------------------------------------------------------------------- the generic stand-in
def _calib_base():
    from .calib.details import Details
    return Details


STROKE_FLOORS = {
    'moved_strokes': "the drawn strands inside the hair's mass each moved 0.05-0.15 L at random (kept inside the mass)",
    'scattered_strokes': "the drawn strands inside the hair's mass each put anywhere in the mass at random (their length "
                         "and direction kept: strokes in the wrong places)",
    'turned_strokes': "the drawn strands inside the hair's mass each turned 30-90 degrees about its middle (in their "
                      "places, across the hair's flow)",
}


class Declared(_calib_base()):
    """the generic calibration stand-in for the 'declared' part: charkit.calib.details.Details (calib.labels.Garments:
    the drawn piece masks as our labels, moved 1-2 px or a random floor's; the drawn band's overhang handed to the
    jacket, the drawing's classes moved with the labels), and our outline pixels (our_lines) the drawing's own ink moved
    with the labels for the design, none for a floor (a random stand-in has no line between its pieces). Our ink strokes
    (our_ink: the hair's line layer) are the drawing's strands (the strokes family's 'strand' set: its lines inside the
    hair's mass off the splitter's lock lines), moved with the labels; the stroke floors (STROKE_FLOORS) keep the
    design's labels and lines in place and move, scatter or turn the strands."""
    part = 'declared'
    generators = dict(_calib_base().generators, **STROKE_FLOORS)

    def labels(self, kind, arg):
        if kind in STROKE_FLOORS:
            return super().labels('design', (0, 0))
        return super().labels(kind, arg)

    def _drawn(self, v):
        """the drawing's lines as it draws them: its ink, and its fainter strokes (a crease drawn in a shade:
        outfit.ridges; ink_inside reads both), skin left out."""
        from . import bodyqa, outfit
        line = bodyqa.CLASS['line']
        d = self.dv.get(v) or {}
        raw = d.get('raw')
        if raw is None:
            return self.cls[v] == line
        m = raw == line
        if d.get('rgb') is not None:
            m = m | (outfit.ridges(d['rgb']) & (raw != bodyqa.CLASS['skin']))
        return fit(m, self.cls[v].shape)

    def _strands(self, v):
        """the drawing's strands in a view (the strokes family's 'strand' set, geom.hairink.drawn_strokes) as line
        pixels, and the hair's mass inside (hairflagqa's keep) -> (pixels, keep) or (None, None) without the hair truth."""
        from scipy import ndimage
        from . import hairflagqa
        from .geom.hairink import drawn_strokes
        memo = self.__dict__.setdefault('_strand_memo', {})
        if v not in memo:
            D = hairflagqa.design_inputs(self.B, self.design)[0]
            if D is None or v not in D['keep']:
                memo[v] = (None, None)
            else:
                sh = self.cls[v].shape
                keep, lines = fit(D['keep'][v], sh), fit(D['lines'][v], sh)
                sk = drawn_strokes(lines, keep, self.ppl, lock_image(self.B.spec, v, sh), 'strand')
                memo[v] = (lines & ndimage.binary_dilation(sk, iterations=1), keep)
        return memo[v]

    def stroke_floor(self, v, kind, seed):
        """the drawing's strands in a view moved, scattered or turned (STROKE_FLOORS) inside the mass -> pixels."""
        from scipy import ndimage
        m, keep = self._strands(v)
        if m is None:
            return np.zeros(self.cls[v].shape, bool)
        rng = np.random.default_rng(5000 + 97 * int(seed) + VIEWS.index(v))
        out = np.zeros(m.shape, bool)
        ky, kx = np.nonzero(keep)
        lab, n = ndimage.label(m, structure=np.ones((3, 3)))
        for k in range(1, n + 1):
            rr, cc = np.nonzero(lab == k)
            c = np.array([rr.mean(), cc.mean()])
            for _ in range(50):
                if kind == 'moved_strokes':
                    t = rng.uniform(0, 2 * np.pi)
                    P = np.c_[rr, cc] + rng.uniform(0.05, 0.15) * self.ppl * np.array([np.sin(t), np.cos(t)])
                elif kind == 'scattered_strokes':
                    j = rng.integers(len(ky))
                    P = np.c_[rr, cc] - c + np.array([ky[j], kx[j]])
                else:
                    t = np.radians(rng.uniform(30, 90) * rng.choice([-1, 1]))
                    Rm = np.array([[np.cos(t), -np.sin(t)], [np.sin(t), np.cos(t)]])
                    P = (np.c_[rr, cc] - c) @ Rm.T + c
                P = np.round(P).astype(int)
                ok = (P[:, 0] >= 0) & (P[:, 0] < m.shape[0]) & (P[:, 1] >= 0) & (P[:, 1] < m.shape[1])
                if ok.all() and keep[P[:, 0], P[:, 1]].mean() > 0.9:
                    q = np.zeros(m.shape, bool)
                    q[P[:, 0], P[:, 1]] = True
                    out |= ndimage.binary_closing(q, iterations=1) | q
                    break
        return out

    def patches(self, L, kind='design', arg=None):
        import sys
        from .calib.labels import _shift

        def lines(B, ppl, az3, views=VIEWS):
            if kind == 'design':
                return {v: _shift(self._drawn(v), arg[0], arg[1], False) for v in views if v in self.cls}
            if kind in STROKE_FLOORS:
                out = {}
                for v in views:
                    if v in self.cls:
                        m, _ = self._strands(v)
                        rest = self._drawn(v) & ~m if m is not None else self._drawn(v)
                        out[v] = rest | self.stroke_floor(v, kind, arg)
                return out
            return {v: np.zeros(self.cls[v].shape, bool) for v in views if v in self.cls}

        def ink(B, ppl, az3, views=VIEWS):
            if kind == 'design':
                return {v: _shift(self._strands(v)[0] if self._strands(v)[0] is not None else
                                  np.zeros(self.cls[v].shape, bool), arg[0], arg[1], False) for v in views if v in self.cls}
            if kind in STROKE_FLOORS:
                return {v: self.stroke_floor(v, kind, arg) for v in views if v in self.cls}
            return {v: np.zeros(self.cls[v].shape, bool) for v in views if v in self.cls}
        return super().patches(L, kind, arg) + [(sys.modules[__name__], 'our_lines', lines),
                                                (sys.modules[__name__], 'our_ink', ink)]
