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
  class_iou    a model-sheet class inside a window (L round the eye line): IoU of ours with the drawing's (the skin
               in the V above the bow)
  top_line     the upper edge of a union of pieces (the shoulder line) per column over x bands, ours against the drawn
               silhouette's where the lower edge isn't under hair: its height (dz), slope or trough (the dip)
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
            the panel's material on our skirt); ref: 'silhouette' compares with the drawn pieces as our surfaces
            would draw them (the drawing's lines inside the figure given to the nearest piece: bodymeasure.drawn_labels;
            area's default) instead of the outfit's fill masks
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


def top_line(Mo, Md, ctx, x=((-0.7, -0.15), (0.15, 0.7)), measure='dz', min_cols=8, round_=4):
    """the upper edge of a union of pieces (the shoulder line: the jacket, the collar and the sleeves) per column over
    signed x bands (L from the midline, one per side), ours against the drawn pieces' silhouettes (evaluate's `ref`
    'silhouette': the drawing's lines given to the nearest piece). A column whose lower edge of the two lies under hair
    (the label just above it hair) is left out: a shoulder under the hair isn't seen in that view, and the hair's tips
    resting on it are no shoulder. measure 'dz': per band the median of ours less the design's, the worse band's |.|;
    'slope': per band a line fitted against |x| (L per L), |ours - design's|, the worse; 'trough': per band the deepest
    trough of the edge (collarqa.trough: the water line between the higher points either side), ours beyond the
    design's (>= 0), the worse (Michael's dip between the collar and the puff)."""
    from . import bodyqa, collarqa, pieceqa
    ppl = ctx['ppl']
    Mo = np.any(Mo, 0) if isinstance(Mo, (list, tuple)) else Mo
    Md = np.any([fit(m, Mo.shape) for m in Md], 0) if isinstance(Md, (list, tuple)) else fit(Md, Mo.shape)
    if Md.sum() < pieceqa.MIN_PX:
        return None
    if Mo.sum() < pieceqa.MIN_PX:
        return dict(value=None, why=WHY_OURS)
    hair_o, hair_d = ctx.get('hair_ours'), ctx.get('hair_drawn')
    to, td = collarqa.top_edge(Mo), collarqa.top_edge(Md)
    per, vals = {}, []
    for k, (a, b) in enumerate(x):
        c0, c1 = sorted((collarqa._col(a, ppl), collarqa._col(b, ppl)))
        cs = np.arange(max(0, c0), min(Mo.shape[1] - 1, c1) + 1)
        ro, rd = to[cs], td[cs]
        ok = np.isfinite(ro) & np.isfinite(rd)
        lower_o = ok & (ro > rd)                  # (rows grow downward: ours lower)
        for lower, hair, r in ((lower_o, hair_o, ro), (ok & (rd > ro), hair_d, rd)):
            if hair is None:
                continue
            ri = np.clip(np.nan_to_num(r, nan=0).astype(int) - 2, 0, Mo.shape[0] - 1)
            under = hair[ri, cs]
            ok &= ~(lower & under)
        if ok.sum() < min_cols:
            per[k] = None
            continue
        xs = np.abs((cs[ok] + 0.5) / ppl - bodyqa.WIN['x'])
        zo, zd = collarqa._z(ro[ok], ppl), collarqa._z(rd[ok], ppl)
        if measure == 'dz':
            v = float(np.median(zo - zd))
            per[k] = dict(dz=round(v, 4), cols=int(ok.sum()))
            vals.append(abs(v))
        elif measure == 'slope':
            so, sd = np.polyfit(xs, zo, 1)[0], np.polyfit(xs, zd, 1)[0]
            per[k] = dict(slope=round(float(so), 3), slope_design=round(float(sd), 3), cols=int(ok.sum()))
            vals.append(abs(so - sd))
        else:
            o_, d_ = collarqa.trough(zo), collarqa.trough(zd)
            per[k] = dict(ours=round(o_, 4), design=round(d_, 4), cols=int(ok.sum()))
            vals.append(max(0.0, o_ - d_))
    if not vals:
        return None
    return dict(value=round(max(vals), round_), ours=per, design=None)


def class_iou(Mo, Md, ctx, cls='skin', window=(-0.2, 0.2, -0.4, -0.75), round_=4):
    """a model-sheet class inside a window (x0, x1 from the midline, z top, z bottom: L from the eye line): the IoU of
    our pixels of that class (pieceqa.our_classes) with the drawing's (its classes) there, higher better: the skin in
    the V between the collar's lapels above the bow (Michael's item 4: drawn skin, ours the jacket's orange). The
    piece only names where it's measured; its masks aren't read."""
    from . import bodyqa, pieceqa
    ppl = ctx['ppl']
    co, cd = ctx.get('cls_ours'), ctx.get('cls')
    if cd is None:
        return None
    if co is None:
        return dict(value=None, why=WHY_OURS)
    sh = co.shape
    x0, x1, zt, zb = window
    r0, r1 = int(round((bodyqa.WIN['top'] - zt) * ppl)), int(round((bodyqa.WIN['top'] - zb) * ppl))
    c0, c1 = int(round((x0 + bodyqa.WIN['x']) * ppl)), int(round((x1 + bodyqa.WIN['x']) * ppl))
    W = np.zeros(sh, bool)
    W[max(0, r0):r1, max(0, c0):c1] = True
    o = W & (co == bodyqa.CLASS[cls])
    d = W & (fit(cd, sh) if cd.dtype == bool else (lambda c: c)(np.pad(cd, ((0, max(0, sh[0] - cd.shape[0])), (0, max(0, sh[1] - cd.shape[1]))), constant_values=-1)[:sh[0], :sh[1]]) == bodyqa.CLASS[cls])
    if d.sum() < pieceqa.MIN_PX:
        return None
    u = (o | d).sum()
    return dict(value=round(float((o & d).sum()) / float(u), round_), ours=round(float(o.sum()) / ppl ** 2, 4),
                design=round(float(d.sum()) / ppl ** 2, 4))


def _runs(row):
    """a boolean row's runs -> [(start, end)] (end inclusive)."""
    d = np.diff(np.r_[0, row.astype(np.int8), 0])
    return list(zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0] - 1))


def band_edges(M, occ, r0, r1, near=2):
    """a two-sided band's edges per row (rows r0..r1): its outermost runs left and right -> [(row, side, inner, outer,
    ok)] in px: side -1 the picture's left band (inner its right end), +1 the right band; ok False where an occluder's
    pixel lies within `near` px of either end (the edge there is the occluder's, not the band's)."""
    out = []
    W = M.shape[1]
    for r in range(max(0, r0), min(M.shape[0], r1)):
        R = _runs(M[r])
        if len(R) < 2:
            continue
        o = occ[r] if occ is not None else np.zeros(W, bool)
        hit = lambda c: bool(o[max(0, c - near):min(W, c + near + 1)].any())
        (a0, a1), (b0, b1) = R[0], R[-1]
        out.append((r, -1, a1, a0, not (hit(a0) or hit(a1))))
        out.append((r, 1, b0, b1, not (hit(b0) or hit(b1))))
    return out


def band_rows(Mo, Md, ctx, z=(-0.47, -0.75), measure='width', occluders=('bow',), near=2, min_rows=5, round_=4):
    """a two-sided band row by row against the drawn one (the sailor collar's lapels framing the V: Michael's flat
    lapels, 2026-10-01): per row in z (L from the eye line, top to bottom) the piece's outermost runs left and right,
    each with its inner edge (toward the other) and its outer edge; a side whose edge touches an occluder (the bow:
    ours' or the drawing's own) is left out of that row. measure 'width': the RMS over the rows and sides both show of
    the band's width, ours less the design's (L); 'inner': of the inner edge's x (the V's line); 'outer': of the outer
    edge's x. ours / design: the band's mean width per side over those rows (L)."""
    from . import bodyqa, pieceqa
    ppl, view = ctx['ppl'], ctx['view']
    Md = fit(Md, Mo.shape)
    if Md.sum() < pieceqa.MIN_PX:
        return None
    r0, r1 = int(round((bodyqa.WIN['top'] - z[0]) * ppl)), int(round((bodyqa.WIN['top'] - z[1]) * ppl))
    od = np.zeros(Mo.shape, bool)
    oo = np.zeros(Mo.shape, bool)
    for o in occluders or ():
        m = (ctx.get('masks') or {}).get('%s__%s' % (view, o))
        if m is not None:
            od |= fit(m, Mo.shape)
        if ctx.get('pm') is not None:
            oo |= pieceqa.members(ctx['lab'], ctx['names'], ctx['pm'], o)
    D = {(r, s): (i, e, ok) for r, s, i, e, ok in band_edges(Md, od, r0, r1, near)}
    if len(D) < 2 * min_rows:
        return None
    O = {(r, s): (i, e, ok) for r, s, i, e, ok in band_edges(Mo, oo, r0, r1, near)}
    pairs = [(k, D[k], O[k]) for k in D if k in O and D[k][2] and O[k][2]]
    if len(pairs) < min_rows:
        return dict(value=None, why=WHY_OURS + ' (%d rows both show)' % len(pairs))
    wd = lambda q: abs(q[1] - q[0]) + 1
    if measure == 'width':
        d = np.array([wd(o) - wd(dd) for _, dd, o in pairs], float)
    elif measure == 'inner':
        d = np.array([o[0] - dd[0] for _, dd, o in pairs], float)
    else:
        d = np.array([o[1] - dd[1] for _, dd, o in pairs], float)
    mean_w = lambda P, side, j: round(float(np.mean([wd(q[j]) for k, *q in P if k[1] == side] or [0])) / ppl, 4)
    P2 = [(k, dd, o) for k, dd, o in pairs]
    return dict(value=round(float(np.sqrt((d ** 2).mean())) / ppl, round_),
                ours=[mean_w(P2, -1, 1), mean_w(P2, 1, 1)], design=[mean_w(P2, -1, 0), mean_w(P2, 1, 0)],
                count=len(pairs))


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


FAMILIES = dict(shape_iou=shape_iou, width=width, edge=edge, tips=tips, angle=angle, ink_between=ink_between,
                position=position, ink_inside=ink_inside, area=area, top_line=top_line, class_iou=class_iou,
                band_rows=band_rows)
HIGHER = ('shape_iou', 'class_iou')                 # families whose value is better higher (a declaration's `better` overrides)
LINE_FAMILIES = ('ink_between', 'ink_inside')     # families that read our drawn lines (inputs' lines)
HAIR_FAMILIES = ('top_line',)
CLASS_FAMILIES = ('class_iou',)                   # families that read our model-sheet classes (inputs' classes)                     # families that read where the hair lies (ctx hair_ours, hair_drawn)


def grade(v, limits, better='lower'):
    p, w = limits
    if better == 'higher':
        return 'PASS' if v >= p else 'WARN' if v >= w else 'FAIL'
    return 'PASS' if v <= p else 'WARN' if v <= w else 'FAIL'


# ------------------------------------------------------------------------------------------------------------ measuring
def inputs(B, design, views=VIEWS, lines=False, classes=False):
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


def silhouette(I, view, pid):
    """the drawn piece's silhouette in a view: its pixels in the drawing drawn as our label image
    (bodymeasure.drawn_labels, cached on I: the drawing's lines inside the figure given to the nearest piece), or None
    when the inputs lack the outfit graph."""
    from . import bodymeasure
    lab = drawn_lab(I, view)
    if lab is None:
        return None
    idx = {n: i for i, n in enumerate(I['names'])}
    return bodymeasure.member_mask(lab, idx, I['pm'].get(pid, []))


def drawn_lab(I, view):
    """the drawing as our label image in a view (bodymeasure.drawn_labels, cached on I), or None without the outfit
    graph."""
    from . import bodymeasure
    if I.get('graph') is None or I.get('dv') is None:
        return None
    if '_drawn' not in I:
        names = I['names']
        skin = I.get('skin') or [n for n in names if 'skin' in n]
        I['_drawn'] = bodymeasure.drawn_labels(I['masks'], I['graph'], I['pm'], names, I['dv'], skin,
                                               [n for n in names if n.startswith('hair')])
    got = I['_drawn'].get(view)
    return None if got is None else got[0]


def hair_of(lab, names):
    """the pixels of a label image that are hair (an object named hair*)."""
    h = [i for i, n in enumerate(names) if n.startswith('hair')]
    return (lab >= 0) & np.isin(lab % 1000, h) if h else np.zeros(lab.shape, bool)


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
                   graph=I.get('graph'), spec=I.get('spec'), pm=pm)
        ctx['silhouette'] = (lambda v=view, ps=pieces: silhouette(I, v, ps[0]))
        ref = params.pop('ref', None) if d['family'] != 'area' else None
        if ref == 'silhouette':                           # (the drawn pieces with the drawing's lines given to them)
            S = [silhouette(I, view, p) for p in pieces]
            Md = [m if s_ is None else s_ for s_, m in zip(S, Md)]
        if d['family'] in HAIR_FAMILIES:                  # (what lies under hair in each view isn't seen)
            dl = drawn_lab(I, view)
            ctx['hair_ours'] = hair_of(lab, names)
            ctx['hair_drawn'] = None if dl is None else fit(hair_of(dl, names), lab.shape)
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
                           for d in ds))
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
        return super().patches(L, kind, arg) + [(sys.modules[__name__], 'our_lines', lines)]
