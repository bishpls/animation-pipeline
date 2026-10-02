"""Michael's flags on the shoulders, the sailor collar and the bow (2026-09-30; tool/collar,
docs/workstreams/collar.md), each measured on the design's grids (bodyqa's: the body sheet's scale, pieceqa's labels and
the outfit's drawn piece masks) against the design measured the same way. Every check here carries its flag
(charkit.registry.flag_check): the merge gate blocks on its regressions.

Checks (qa3d part 'collar_flags'; lengths in L):
  shoulder_back_line, shoulder_back_slope
        the back view's shoulder line: per column over |x| in SHOULDER_X the upper garments' (top, collar, sleeves) top
        edge (the drawn pieces' union closed over the ink between them); the median of ours less the design's per side
        (the worse side's size). Michael: "shape on the shoulders is obviously wrong" (low, with a dip). The slope of
        a line fitted to it against |x| (L per L) less the design's is a guard, not a flag check (see its note)
  collar_back_iou, collar_back_square, collar_back_lay
        the sailor collar's back panel: its IoU with the drawn panel (both closed); its squareness (the panel's width
        at 90% of the way down it over at 50%) against the design's (the drawn panel is square, ours was a rounded flap);
        its lay: the deepest trough in the garments' top edge between the panel's outer edge and the shoulder (the
        water line between the higher points either side, SHOULDER_X), beyond the design's. Michael: "the cream blouse
        segment on the back isn't being shaped correctly, or laying well against the shoulder; that dip in between the
        shoulder and cream section of the blouse is a clear error"
  bow_front_loop_width, bow_front_loop_end
        the bow's loops in front: their span (ours over the design's, less one: a guard, not a flag check, the bow is
        sized to the drawn span), and how much of each loop's outer end is one straight vertical edge (the rows whose outermost column is within END_TOL of the loop's outermost, over
        the loop's height there), beyond the design's. Michael: "the sides of the loops are cut off"
  bow_front_bleed
        the bow's cream running into the jacket with no line between (the loops' open ends and their lower corners):
        the length of the bow's edge where its pixels touch the jacket's or a sleeve's directly, drawn with the build's
        outlines (charkit.lookqa's frame at the design's line scale), against the design's (its bow's cream touching
        orange with no ink between). Michael: "the colour bleeds out of the bow's bottom edges into the jacket"
  bow_profile_ribbon
        in profile, the ribbons merging into the jacket: per row over the drawn tails' rows 30-80% down them, whether
        the ribbon reads apart from the jacket: its widest run at least RUN_MIN wide and touching no jacket or sleeve
        pixel directly (an ink line between), drawn with the build's outlines (lookqa's frame at the design's line
        scale, as bow_front_bleed); the share of rows that don't, beyond the design's (its drawn tails' cream against
        orange). A sliver of ribbon hugging the jacket's front between two lines merges with it as surely as a ribbon
        with no line at all (the pre-M1 build). Michael: "the trailing ribbons merge into the jacket in side profile";
        his call C (2026-09-30): what the flag meant is the line between ribbon and jacket, not the ribbon's width in
        profile (the drawing's side view is deeper than its front view allows: bow2's measure asked for a depth the
        close-hung ribbons can't give)

    table, checks = collarqa.measure(B, design)      # charkit.qa3d's 'collar_flags' part
"""
import numpy as np

from .registry import flag_check, qa_part

from . import bodyqa

SHOULDER_X = (0.25, 0.55)           # L from the midline: the shoulder line's columns (the collar's edge to the puffs)
END_TOL = 0.004                     # L: a loop's row counts as its straight end within this of its outermost column
RIBBON = (0.3, 0.8)                 # the share of the tails' height (from their top) the ribbons' line is read over
RUN_MIN = 0.03                      # L: a row's ribbon run narrower than this beside the jacket doesn't read apart from it
LIMITS = {                          # (pass within, warn within); else fail
    'line': (0.015, 0.03),          # L: the shoulder line's median height against the design's
    'slope': (0.10, 0.20),          # L per L: its slope against the design's
    'iou': (0.87, 0.81),            # IoU, at least (higher is better). Calibrated (tool/calib, 2026-09-30; was 0.80 /
                                    # 0.65, where the flagged build read 0.754 WARN): the design moved 1-2 px reads
                                    # 0.925-0.957, g3_render3 0.754; the limits at the thirds of that gap
    'square': (0.08, 0.15),         # |ours - design| of the panel's width at 90% down over at 50%
    'lay': (0.025, 0.036),          # L: the trough beside the panel beyond the design's. Calibrated (tool/calib; was
                                    # 0.01 / 0.02, which the design failed against itself): the design as ours reads
                                    # 0.0141 at every 1-2 px move (its own side is closed, pieceqa.clean, and ours
                                    # isn't: the drawn notch counts), g3_render3 0.0471; the limits at the thirds
    'loop_width': (0.06, 0.12),     # |ours / design - 1| of the loops' span
    'loop_end': (0.15, 0.30),       # the straight share of a loop's end beyond the design's
    'bleed': (0.03, 0.06),          # L of the bow's edge on the jacket with no line, beyond the design's
    'ribbon': (0.15, 0.30),         # the share of the tails' rows in profile whose ribbon doesn't read apart from the
                                    # jacket (narrower than RUN_MIN, or no line between), beyond the design's
}
FLAGS = {
    'shoulder': 'the back view: the shape on the shoulders is obviously wrong (steep, low; Michael 2026-09-30)',
    'collar': "the back view: the cream collar isn't shaped or lying against the shoulder; the dip between the shoulder "
              "and the collar (Michael 2026-09-30)",
    'loops': "the bow in front: the sides of the loops are cut off, straight vertical edges (Michael 2026-09-30)",
    'bleed': "the bow in front: the colour bleeds out of the bow's bottom edges into the jacket (Michael 2026-09-30)",
    'ribbon': 'the bow in profile: the trailing ribbons merge into the jacket (Michael 2026-09-30; remeasured as the '
              'line between ribbon and jacket, his call C)',
}
UPPER = ('top', 'collar', 'sleeve_L', 'sleeve_R')


def grade(key, v):
    p, w = LIMITS[key]
    if key == 'iou':
        return 'PASS' if v >= p else 'WARN' if v >= w else 'FAIL'
    return 'PASS' if v <= p else 'WARN' if v <= w else 'FAIL'


def _check(kind, key, v, **kw):
    c = dict(value=None if v is None else round(float(v), 4), status='FAIL' if v is None else grade(key, v), **kw)
    return flag_check(c, FLAGS[kind])


def _z(r, ppl):
    return bodyqa.WIN['top'] - (np.asarray(r, float) + 0.5) / ppl


def _col(x, ppl):
    return int(round((x + bodyqa.WIN['x']) * ppl - 0.5))


# ------------------------------------------------------------------------------------------------------------ measures
def top_edge(U):
    """per column the first row of mask U (NaN where the column is empty) -> (W,) rows."""
    has = U.any(0)
    r = np.argmax(U, 0).astype(float)
    r[~has] = np.nan
    return r


def shoulder_line(U, ppl, xr=SHOULDER_X):
    """the upper garments' top edge (U: their union) over |x| in xr, each side: {side: (|x| (n,), z (n,))}."""
    out = {}
    r = top_edge(U)
    for side, sgn in (('L', 1), ('R', -1)):
        c0, c1 = sorted((_col(sgn * xr[0], ppl), _col(sgn * xr[1], ppl)))
        cs = np.arange(c0, c1 + 1)
        x = np.abs((cs + 0.5) / ppl - bodyqa.WIN['x'])
        out[side] = (x, _z(r[cs], ppl))
    return out


def line_measure(o, d):
    """ours against the design's shoulder line, each side: the median height difference and the slopes. -> dict."""
    out = {}
    for side in ('L', 'R'):
        xo, zo = o[side]
        _, zd = d[side]
        ok = np.isfinite(zo) & np.isfinite(zd)
        if ok.sum() < 10:
            out[side] = None
            continue
        so, sd = np.polyfit(xo[ok], zo[ok], 1)[0], np.polyfit(xo[ok], zd[ok], 1)[0]
        out[side] = dict(dz=round(float(np.median(zo[ok] - zd[ok])), 4), slope=round(float(so), 3),
                         slope_design=round(float(sd), 3), z=round(float(np.median(zo[ok])), 4),
                         z_design=round(float(np.median(zd[ok])), 4))
    return out


def trough(z):
    """the deepest trough of a height profile (NaN skipped): the water line between its higher points either side, less
    the profile (L)."""
    z = np.asarray(z, float)
    ok = np.isfinite(z)
    if ok.sum() < 3:
        return None
    z = z[ok]
    left, right = np.maximum.accumulate(z), np.maximum.accumulate(z[::-1])[::-1]
    return float(np.max(np.minimum(left, right) - z))


def panel(m, ppl):
    """a back panel's shape: its width at 50% and 90% of the way down its rows, their ratio, its bottom (z) -> dict."""
    rr = np.nonzero(m.any(1))[0]
    if len(rr) < 5:
        return None
    r0, r1 = rr[0], rr[-1]
    w = lambda f: float(m[int(round(r0 + f * (r1 - r0)))].sum()) / ppl
    w50, w90 = w(0.5), w(0.9)
    return dict(w50=round(w50, 4), w90=round(w90, 4), square=round(w90 / w50, 3) if w50 else None,
                bottom=round(float(_z(r1, ppl)), 4))


def iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum()) / u if u else None


def loop_ends(lobes, ppl, tol=END_TOL):
    """each loop's outer end (the bow's lobes, one mask): the share of the loop's height at its end that is a straight
    vertical edge: the rows whose outermost column lies within tol of the loop's outermost column, over the rows the
    loop spans in its outer 15% -> {'L', 'R'} shares (her left is the image's right)."""
    rs, cs = np.nonzero(lobes)
    if len(rs) < 50:
        return None
    cx = 0.5 * (cs.min() + cs.max())
    out = {}
    for side, sgn in (('L', 1), ('R', -1)):
        sel = (cs - cx) * sgn > 0
        if not sel.any():
            out[side] = None
            continue
        ext = cs[sel] * sgn
        e = ext.max()
        rows = rs[sel]
        far = {}
        for r_, c_ in zip(rows, ext):
            far[r_] = max(far.get(r_, -1e9), c_)
        hw = e - cx * sgn
        end_rows = [r_ for r_, c_ in far.items() if c_ >= e - 0.15 * hw]
        flat = [r_ for r_, c_ in far.items() if c_ >= e - tol * ppl]
        out[side] = round(len(flat) / max(1, len(end_rows)), 3)
    return out


def edge_touch(a, b):
    """pixels of mask a with a 4-neighbour in mask b."""
    t = np.zeros_like(a)
    t[1:] |= b[:-1]
    t[:-1] |= b[1:]
    t[:, 1:] |= b[:, :-1]
    t[:, :-1] |= b[:, 1:]
    return a & t


# ------------------------------------------------------------------------------------------------------------ the part
@qa_part('collar_flags', order=1760, table='collar_flags', checks=9)
def collar_flags(B, design=None, out=None):
    """Michael's flags on the shoulders, the sailor collar and the bow (2026-09-30), calibrated checks: the back view's
    shoulder line, the collar's back panel and its lay, the bow's loops, its colour running into the jacket, its
    ribbons in profile."""
    return measure(B, design, out)


def measure(B, design, out=None):
    """the checks on a bundle against the design (qa3d.Design) -> (table, checks)."""
    from . import bodymeasure, pieceqa as pq
    ctx = design.sheet_context()
    if 'why' in ctx:
        return None, {'collar_flags': {'status': 'SKIPPED', 'why': ctx['why']}}
    got = bodymeasure.piece_masks(B.spec)
    if got is None:
        return None, {'collar_flags': {'status': 'SKIPPED', 'why': 'no outfit_masks produced for this spec'}}
    masks, graph, paths = got
    for p in paths:
        design._rec(p)
    ppl = ctx['ppl']
    dv = design.design_views()
    O, names = pq.our_labels(B, ppl, ctx['az3'], views=('front', 'profile', 'back'))
    pm = bodymeasure.piece_map(graph, B.spec)
    T, C = {}, {}
    ours = lambda v, pid: pq.members(O[v]['lab'], names, pm, pid)

    def drawn(v, pid, shape):
        m = masks.get('%s__%s' % (v, pid))
        if m is None:
            return np.zeros(shape, bool)
        out_ = np.zeros(shape, bool)
        h, w = min(shape[0], m.shape[0]), min(shape[1], m.shape[1])
        out_[:h, :w] = m[:h, :w]
        return out_
    # the back view: the shoulder line and the collar's panel
    if 'back' in dv and 'back' in O:
        sh = O['back']['lab'].shape
        Uo = np.zeros(sh, bool)
        Ud = np.zeros(sh, bool)
        for pid in UPPER:
            Uo |= ours('back', pid)
            Ud |= drawn('back', pid, sh)
        Ud = pq.clean(Ud, ppl)              # (the drawn pieces' union closed over the ink lines between them)
        lo, ld = shoulder_line(Uo, ppl), shoulder_line(Ud, ppl)
        M = line_measure(lo, ld)
        T['shoulder_back'] = M
        ok = [m for m in M.values() if m]
        v_line = max(abs(m['dz']) for m in ok) if ok else None
        v_slope = max(abs(m['slope'] - m['slope_design']) for m in ok) if ok else None
        C['shoulder_back_line'] = _check('shoulder', 'line', v_line, per_side=M,
                                         note="the back view's shoulder line (the upper garments' top edge over |x| "
                                              "%.2f-%.2f L): the median of ours less the design's, the worse side "
                                              "(- = ours lower)" % SHOULDER_X)
        C['shoulder_back_slope'] = dict(value=None if v_slope is None else round(v_slope, 4),
                                        status='FAIL' if v_slope is None else grade('slope', v_slope),
                                        note="a guard, not a flag check (a line fitted over the collar's edge to the "
                                             "puffs reads nearly flat on the flagged build: its dip and the puffs' rise "
                                             "cancel; collar_back_lay measures the dip): the shoulder line's slope "
                                             "against |x| (L per L; - falls outward), ours less the design's, the worse "
                                             "side")
        co, cd = ours('back', 'collar'), pq.clean(drawn('back', 'collar', sh), ppl)
        if cd.sum() >= pq.MIN_PX:
            co_c = pq.clean(co, ppl) if co.any() else co
            v_iou = iou(co_c, cd)
            po, pd = panel(co_c, ppl), panel(cd, ppl)
            T['collar_back'] = dict(ours=po, design=pd, iou=v_iou)
            C['collar_back_iou'] = _check('collar', 'iou', v_iou, ours=po, design=pd,
                                          note="the collar's back panel against the drawn panel (both closed): IoU")
            v_sq = abs(po['square'] - pd['square']) if po and pd and po['square'] is not None else None
            C['collar_back_square'] = _check('collar', 'square', v_sq,
                                             ours=po and po['square'], design=pd and pd['square'],
                                             note="the panel's width 90% of the way down it over at 50% (square: near "
                                                  "1; a rounded flap narrows), |ours - design's|")
            # the lay: the trough in the garments' top edge from the panel's outer edge out to the shoulder
            lay = {}
            for side in ('L', 'R'):
                xo, zo = lo[side]
                _, zd = ld[side]
                lay[side] = dict(ours=trough(zo), design=trough(zd))
            vals = [max(0.0, v['ours'] - v['design']) for v in lay.values()
                    if v['ours'] is not None and v['design'] is not None]
            T['collar_back_lay'] = lay
            C['collar_back_lay'] = _check('collar', 'lay', max(vals) if vals else None, per_side=lay,
                                          note="the deepest trough in the upper garments' top edge over |x| %.2f-%.2f "
                                               "L (the collar's edge to the puff: the water line between the higher "
                                               "points either side, L) beyond the design's, the worse side" % SHOULDER_X)
    # the bow in front: its loops, its colour on the jacket
    if 'front' in dv and 'front' in O:
        sh = O['front']['lab'].shape
        lob_d = pq.clean(drawn('front', 'bow', sh), ppl)
        tails_d = drawn('front', 'bow_tail_L', sh) | drawn('front', 'bow_tail_R', sh)
        if lob_d.sum() >= pq.MIN_PX and tails_d.any():
            F, fnames = pq.fine_labels(B, ppl, ctx['az3'], views=('front',))
            fp = ppl * pq.FINE
            Mo = pq.members(F['front'], fnames, pm, 'bow')
            # ours in one object: the loops above the design's tails' top
            zt = _z(np.nonzero(tails_d.any(1))[0].min(), ppl)
            rt = int(round((pq.CHEST['top'] - zt) * fp))
            lob_o = Mo.copy()
            lob_o[rt:] = False
            wd = (np.ptp(np.nonzero(lob_d.any(0))[0]) + 1) / ppl
            wo = (np.ptp(np.nonzero(lob_o.any(0))[0]) + 1) / fp if lob_o.any() else None
            eo, ed = loop_ends(lob_o, fp), loop_ends(pq.crop_win(lob_d, ppl), ppl)
            T['bow_loops'] = dict(width=[wo, round(wd, 4)], ends=dict(ours=eo, design=ed))
            v_w = None if wo is None else abs(wo / wd - 1)
            C['bow_front_loop_width'] = dict(value=None if v_w is None else round(v_w, 4),
                                             status='FAIL' if v_w is None else grade('loop_width', v_w),
                                             ours=None if wo is None else round(wo, 4), design=round(wd, 4),
                                             note="a guard, not a flag check (the bow is sized to the drawn span, so "
                                                  "the flagged build reads 0 too): the bow's loops' span in front, ours "
                                                  "over the design's, less one (rounding the loops' ends mustn't "
                                                  "shorten them)")
            ve = [max(0.0, eo[s] - ed[s]) for s in 'LR' if eo and ed and eo.get(s) is not None and ed.get(s) is not None]
            C['bow_front_loop_end'] = _check('loops', 'loop_end', max(ve) if ve else None, ours=eo, design=ed,
                                             note="the share of each loop's outer end that is one straight vertical "
                                                  "edge (its rows' outermost column within %.3f L of the loop's) beyond "
                                                  "the design's, the worse side" % END_TOL)
            b = bleed(B, design, dv['front'], lob_d | pq.clean(tails_d, ppl), ppl)
            if b is not None:
                T['bow_bleed'] = b
                C['bow_front_bleed'] = _check('bleed', 'bleed', max(0.0, b['ours'] - b['design']), ours=b['ours'],
                                              design=b['design'],
                                              note="L of the bow's edge where its cream touches the jacket or a sleeve "
                                                   "with no line between, drawn with the build's outlines, beyond the "
                                                   "design's (its bow's cream on orange with no ink between)")
    # the ribbons in profile: the line between them and the jacket
    if 'profile' in dv and 'profile' in O:
        sh = O['profile']['lab'].shape
        tails_d = pq.clean(drawn('profile', 'bow_tail_L', sh) | drawn('profile', 'bow_tail_R', sh), ppl)
        if tails_d.sum() >= 50:
            rr = np.nonzero(tails_d.any(1))[0]
            r0, r1 = rr[0], rr[-1]
            ra, rb = int(r0 + RIBBON[0] * (r1 - r0)), int(r0 + RIBBON[1] * (r1 - r0))
            zs = (float(_z(ra, ppl)), float(_z(rb, ppl)))
            az = bodyqa.azimuths(ctx['az3'])['profile']
            r = ribbon_line(B, dv['profile'], drawn('profile', 'bow_tail_L', sh) | drawn('profile', 'bow_tail_R', sh),
                            (ra, rb), zs, ppl, az)
            if r is not None:
                T['bow_ribbon_profile'] = r
                C['bow_profile_ribbon'] = _check('ribbon', 'ribbon', max(0.0, r['ours'] - r['design']),
                                                 ours=r['ours'], design=r['design'], width=[r['ours_w'], r['design_w']],
                                                 touch=[r['ours_touch'], r['design_touch']], thin=r['ours_thin'],
                                                 rows=[round(zs[0], 3), round(zs[1], 3)],
                                                 note="in profile, the ribbons merging into the jacket: the share of "
                                                      "the rows %d-%d%% down the drawn tails whose widest ribbon run is "
                                                      "narrower than %.2f L or touches the jacket or a sleeve with no "
                                                      "line between, drawn with the build's outlines, beyond the "
                                                      "design's (its tails' cream against orange); width: the runs' "
                                                      "median (L), touch: the share of rows touching, [ours, design]"
                                                      % (100 * RIBBON[0], 100 * RIBBON[1], RUN_MIN))
    return T, C


BLEED_WIN = (0.7, -0.3, 1.1)        # L round the eye line: the chest frame the bow is drawn in (half-width, above, below)
BLEED_PPL = 400                     # its px per L (the head frame's)
JACKET = ('top', 'sleeve_L', 'sleeve_R')


def bleed(B, design, dvf, bow_d, ppl):
    """the bow's cream against the jacket with no line between: ours drawn with the build's outlines (lookqa's frame at
    BLEED_PPL, the design's line scale) -> the length (L) of bow pixels 4-touching a jacket or sleeve pixel; the
    design's: its bow's cream pixels (the drawn bow, lines kept) 4-touching orange. -> dict(ours, design) or None."""
    from . import artifactqa, bodyqa as bq, lookqa
    raw = dvf.get('raw')
    if raw is None:
        return None
    CL = bq.CLASS
    h, w = min(raw.shape[0], bow_d.shape[0]), min(raw.shape[1], bow_d.shape[1])
    cream = (raw[:h, :w] == CL['cream']) & bow_d[:h, :w]
    orange = raw[:h, :w] == CL['orange']
    d_len = float(edge_touch(cream, orange).sum()) / ppl
    fr = lookqa.HeadFrame(B, ppl=BLEED_PPL, ss=1, win=BLEED_WIN)
    surfs = lookqa._scene(B, skin_outline=True, line_scale=lookqa.line_scale(B, ppl, 1440))
    mesh, _ = artifactqa.buffers(B, surfs, 0.0, fr)
    nm = np.array([s['o'].name for s in surfs] + [''])
    hull = np.array([bool(s['hull']) for s in surfs] + [False])
    idx = np.where(mesh >= 0, mesh, len(surfs))
    name, line = nm[idx], hull[idx]
    bow = (name == 'bow') & ~line
    jk = np.isin(name, JACKET) & ~line
    o_len = float(edge_touch(bow, jk).sum()) / BLEED_PPL
    return dict(ours=round(o_len, 4), design=round(d_len, 4))


RIBBON_WIN = (0.8, -0.3, 1.6)       # L round the eye line: the profile frame the tails are drawn in


def runs_rows(bow, jk, rows, ppl, sgn=None):
    """per row of `rows`: the widest run of bow pixels (L) and whether that run touches a jacket pixel (4-neighbours,
    no line between). -> (widths (n,), touching (n,) bool)."""
    t = edge_touch(bow, jk)
    W, touch = [], []
    for r in rows:
        if not (0 <= r < bow.shape[0]):
            W.append(0.0); touch.append(False)
            continue
        c = np.nonzero(bow[r])[0]
        if not len(c):
            W.append(0.0); touch.append(False)
            continue
        br = np.nonzero(np.diff(c) > 1)[0]
        segs = np.split(c, br + 1)
        g = max(segs, key=len)
        W.append(len(g) / ppl)
        touch.append(bool(t[r, g].any()))
    return np.array(W), np.array(touch)


def ribbon_line(B, dvp, tails_d, rows, zs, ppl, az):
    """the ribbons against the jacket in profile, per row of the design's rows (ra, rb) (zs: their heights, L from the eye
    line): a row reads the ribbon apart from the jacket when its widest ribbon run is at least RUN_MIN L and touches no
    jacket pixel directly (an ink line between). Ours drawn with the build's outlines (lookqa's frame at BLEED_PPL, the
    design's line scale): the bow's pixels against the jacket's and sleeves'; the design's: its drawn tails' cream pixels
    against orange. -> dict(ours, design (the share of the rows that don't read apart), ours_w, design_w (the runs'
    median width, L), ours_touch, design_touch (the share of rows whose run touches the jacket)) or None."""
    from . import artifactqa, bodyqa as bq, lookqa
    raw = dvp.get('raw')
    if raw is None:
        return None
    CL = bq.CLASS
    ra, rb = rows
    h, w = min(raw.shape[0], tails_d.shape[0]), min(raw.shape[1], tails_d.shape[1])
    cream = (raw[:h, :w] == CL['cream']) & tails_d[:h, :w]
    orange = raw[:h, :w] == CL['orange']
    Wd, Td = runs_rows(cream, orange, range(ra, rb + 1), ppl)
    fr = lookqa.HeadFrame(B, ppl=BLEED_PPL, ss=1, win=RIBBON_WIN)
    surfs = lookqa._scene(B, skin_outline=True, line_scale=lookqa.line_scale(B, ppl, 1440))
    mesh, _ = artifactqa.buffers(B, surfs, az, fr)
    nm = np.array([s['o'].name for s in surfs] + [''])
    hull = np.array([bool(s['hull']) for s in surfs] + [False])
    idx = np.where(mesh >= 0, mesh, len(surfs))
    name, line = nm[idx], hull[idx]
    oa, ob = (int(round(fr.row(fr.eye_z + z * fr.L))) for z in zs)
    bow = (name == 'bow') & ~line
    jk = np.isin(name, JACKET) & ~line
    Wo, To = runs_rows(bow, jk, range(oa, ob + 1), BLEED_PPL)
    bad = lambda W_, T_: float(np.mean((W_ < RUN_MIN) | T_))
    return dict(ours=round(bad(Wo, To), 3), design=round(bad(Wd, Td), 3),
                ours_w=round(float(np.median(Wo)), 4), design_w=round(float(np.median(Wd)), 4),
                ours_touch=round(float(np.mean(To)), 3), design_touch=round(float(np.mean(Td)), 3),
                ours_thin=round(float(np.mean(Wo < RUN_MIN)), 3))
