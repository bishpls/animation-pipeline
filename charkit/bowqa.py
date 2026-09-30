"""Michael's flag on the bow in profile (2026-09-30; tool/bow2, docs/workstreams/bow2.md): "in profile, the bow's ribbon
tails project far forward of the chest as flat blades; the design hangs them close to the chest, nearly vertical, under
puffy loops. Our loops read as flat disks in profile." Measured on the design's grids (bodyqa's: the body sheet's
scale, registered on the eyes as every piece check is) against the design's drawn piece masks measured the same way.
Every check here carries the flag (charkit.registry.flag_check: the merge gate blocks on its regressions).

Ours is our z-buffer with the bow split in two (split_labels): its tails (the bow mesh's two connected parts that reach
lowest: charkit.garments._bow_mesh builds each lobe, each tail and the knot as a part of its own) and its loops (the
rest: the lobes and the knot). The design's are its drawn masks: `bow` (the lobes and the knot) and `bow_tail_L|R`.

The tails' rows: from where they leave the knot (KNOT L above the drawn tails' top in the front view, where the whole
tail shows; in profile the drawn loops hide their top) down TAIL_FOOT of the way to the drawn tails' lowest row in
profile (their cut ends left out). Over those rows the bow's front edge is read: its forward-most pixel, loops or tails
(the drawn loops' lower tips hang in front of the tails' top, and the front edge they make with the tails is what reads
as the ribbons' hang).

Checks (qa3d part 'bow_profile'; lengths in L; forward: toward the face):
  bow_profile_tail_reach
        the forward projection: the front edge per row, ours less the design's; the value is the TAIL_Q percentile of
        its size over the rows (the signed median beside it: + ours forward)
  bow_profile_tail_hang
        the hang: the angle from the vertical (+ the lower end forward, degrees) of the chord from the front edge where
        the tails leave the knot (the rows KNOT..KNOT_IN L above the drawn tails' top) to the front edge at their foot
        (the lowest fifth of the rows), ours less the design's
  bow_profile_loop_thick
        the loops' thickness in profile where it is: their run per row (depth, L; the median over +-BAND L) at tenths
        of the drawn loops' height, RMS against the design's; where ours has no loop the run is 0 (the drawn loops hang
        fullest low; the flat lobes sat high and ended short)
  bow_profile_loop_lean
        the loops' lean in profile: the angle from the vertical of their silhouette's equivalent-ellipse major axis
        (second moments), ours less the design's (degrees). A lobe lying round the chest reads as a disk tipped along
        it; the drawn loops stand up. (Its roundness, the minor over major axis, is in the table: it reads the same on
        the flat disks and the design, 0.57 against 0.55, so it isn't a check.)
Both sides' loops are closed by pieceqa.clean (the drawing's fold strokes inside them are slits in the mask).

    table, checks = bowqa.measure(B, design)      # charkit.qa3d's 'bow_profile' part
    M = bowqa.profile_measure(loops, tails, loops_drawn, tails_drawn, ppl, fw, top_row)   # on masks alone
"""
import math

import numpy as np

from .registry import flag_check, qa_part

from . import bodyqa

KNOT = 0.04                         # L above the drawn tails' top (front view): the tails' rows start at the knot
KNOT_IN = 0.01                      # the hang's attachment: the front edge over the rows KNOT..KNOT_IN L above that top
TAIL_FOOT = 0.9                     # the rows end this share of the way down to the drawn tails' lowest row in profile
TAIL_Q = 90                         # the reach: this percentile of |ours - design| over the rows
BAND = 0.02                         # L: a loop station's run is the median over the rows within this
MIN_ROWS = 8                        # fewer rows where both show the bow: no reading (FAIL)
LOOP_MIN_PX = 150                   # a loops mask smaller than this (either side): no reading (FAIL)
TAILS, LOOPS = 5000, 5001           # split_labels' codes for our bow's tails and loops (other objects keep pieceqa's)
LIMITS = {                          # (pass within, warn within); else fail
    'reach': (0.03, 0.06),          # L: the front edge's distance from the design's (TAIL_Q percentile over the rows)
    'hang': (5.0, 10.0),            # degrees: the tails' chord from the vertical against the design's
    'thick': (0.03, 0.05),          # L: RMS of the loops' run per row at tenths against the design's
    'lean': (8.0, 15.0),            # degrees: the loops' major axis from the vertical against the design's
}
FLAG = ("the bow in profile: the ribbon tails project far forward of the chest as flat blades (the design hangs them "
        "close to the chest, nearly vertical, under puffy loops); our loops read as flat disks (Michael 2026-09-30)")


def grade(key, v):
    p, w = LIMITS[key]
    return 'PASS' if v <= p else 'WARN' if v <= w else 'FAIL'


def _check(key, v, **kw):
    c = dict(value=None if v is None else round(float(v), 4), status='FAIL' if v is None else grade(key, v), **kw)
    return flag_check(c, FLAG)


# ------------------------------------------------------------------------------------------------------------ ours
def bow_parts(V, T):
    """the bow mesh's triangles by part: its connected parts, the two that reach lowest its tails, the rest its loops
    (the lobes and the knot). -> bool per triangle: True on a tail; None when it has fewer than three parts."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    T = np.asarray(T)
    n = len(V)
    r = np.concatenate([T[:, 0], T[:, 1], T[:, 2]])
    c = np.concatenate([T[:, 1], T[:, 2], T[:, 0]])
    k, lab = connected_components(coo_matrix((np.ones(len(r)), (r, c)), shape=(n, n)), directed=False)
    parts = [j for j in range(k) if (lab == j).sum() >= 3]
    if len(parts) < 3:
        return None
    low = {j: float(V[lab == j][:, 2].min()) for j in parts}
    tails = sorted(parts, key=lambda j: low[j])[:2]
    return np.isin(lab[T[:, 0]], tails)


def split_labels(B, ppl, az3, views=('profile',), bow='bow'):
    """our objects z-buffered on the design's grids (pieceqa.our_labels' labels) with the bow split: its tails TAILS,
    its loops LOOPS (bow_parts). -> ({view: label image}, names), or (None, names) without a bow of three parts."""
    from . import qa3d
    from .faceqa import zbuffer
    meshes, names = qa3d.scene_objects(B)
    obj = []
    split = False
    for i, (V, T, _) in enumerate(meshes):
        code = np.where(V[T].mean(1)[:, 0] >= 0, i, i + 1000)
        if names[i] == bow:
            tail = bow_parts(V, T)
            if tail is not None:
                code = np.where(tail, TAILS, LOOPS)
                split = True
        obj.append((V, T, code))
    if not split:
        return None, names
    As = B.assembly
    iw = np.array(qa3d.iris_centres(B))
    az = bodyqa.azimuths(az3)
    out = {}
    for v in views:
        out[v] = zbuffer(obj, az[v], bodyqa.origin(v, az[v], iw, As['centre']), As['L'], 1.0 / ppl, bodyqa.WIN)[1]
    return out, names


# ------------------------------------------------------------------------------------------------------------ measures
def front_edge(m, rows, fw):
    """per row the mask's forward-most column (fw -1: forward is to the left), NaN where it has none."""
    out = np.full(len(rows), np.nan)
    for i, r in enumerate(rows):
        c = np.nonzero(m[r])[0] if 0 <= r < m.shape[0] else ()
        if len(c):
            out[i] = c.min() if fw < 0 else c.max()
    return out


def chord(m, top, foot, fw):
    """the angle (degrees) from the vertical of the chord from a mask's front edge over rows `top` (median) to its front
    edge over rows `foot` (median), + the lower end forward; None where either has none."""
    a, b = front_edge(m, top, fw), front_edge(m, foot, fw)
    if not np.isfinite(a).any() or not np.isfinite(b).any():
        return None
    dc = np.nanmedian(b) - np.nanmedian(a)
    dr = np.mean(foot) - np.mean(top)
    return math.degrees(math.atan2(fw * dc, dr))


def ellipse(m, ppl):
    """a mask's equivalent ellipse from its second moments -> dict(major, minor (full axes, L), round (minor / major),
    lean (degrees of the major axis from the vertical, + its top toward larger columns), height, depth (extents, L),
    area (L^2)) or None."""
    rs, cs = np.nonzero(m)
    if len(rs) < 3:
        return None
    P = np.c_[cs, -rs] / ppl                               # (across, up)
    w, U = np.linalg.eigh(np.cov(P.T))
    lo, hi = max(w[0], 0.0), max(w[1], 1e-12)
    ax = U[:, 1] if U[1, 1] >= 0 else -U[:, 1]              # the major axis, pointing up
    return dict(major=round(4 * math.sqrt(hi), 4), minor=round(4 * math.sqrt(lo), 4), round=round(math.sqrt(lo / hi), 4),
                lean=round(math.degrees(math.atan2(ax[0], ax[1])), 2),
                height=round((np.ptp(rs) + 1) / ppl, 4), depth=round((np.ptp(cs) + 1) / ppl, 4),
                area=round(len(rs) / ppl ** 2, 5))


def runs(m, r0, r1, ppl, n=11, band=BAND):
    """a mask's run per row (its pixel count in the row, L) at n stations from row r0 to r1, each the median over the
    rows within `band` L."""
    b = max(1, int(round(band * ppl)))
    out = []
    for t in np.linspace(0.0, 1.0, n):
        r = int(round(r0 + t * (r1 - r0)))
        rr = [q for q in range(r - b, r + b + 1) if 0 <= q < m.shape[0]]
        out.append(float(np.median([np.count_nonzero(m[q]) for q in rr])) / ppl)
    return np.array(out)


def profile_measure(loops, tails, loops_d, tails_d, ppl, fw, top_row=None):
    """the profile's measures on masks alone (ours: loops, tails; the design's: loops_d, tails_d, one grid; top_row: the
    drawn tails' top row in the front view, else their top in profile) -> dict(reach, hang, thick, lean: each
    dict(value (None: no reading), ...), rows, loops)."""
    from . import pieceqa as pq
    out = {}
    z = lambda r: bodyqa.WIN['top'] - (r + 0.5) / ppl
    rr = np.nonzero(tails_d.any(1))[0]
    if len(rr) >= MIN_ROWS:
        t0 = rr[0] if top_row is None else int(top_row)
        r0 = int(round(t0 - KNOT * ppl))
        r1 = int(round(t0 + TAIL_FOOT * (rr[-1] - t0)))
        rows = np.arange(r0, r1 + 1)
        fo = front_edge(loops | tails, rows, fw)
        fd = front_edge(loops_d | tails_d, rows, fw)
        ok = np.isfinite(fo) & np.isfinite(fd)
        d = fw * (fo - fd) / ppl                           # + ours forward
        out['rows'] = dict(z=[round(float(z(r0)), 3), round(float(z(r1)), 3)], n=int(len(rows)), both=int(ok.sum()))
        if ok.sum() >= MIN_ROWS:
            ad = np.abs(d[ok])
            out['reach'] = dict(value=float(np.percentile(ad, TAIL_Q)), median=round(float(np.median(d[ok])), 4),
                                max=round(float(ad.max()), 4),
                                per_row=[[round(float(z(r)), 3), round(float(x), 4)]
                                         for r, x in zip(rows[ok][::3], d[ok][::3])])
            top = np.arange(int(round(t0 - KNOT * ppl)), int(round(t0 - KNOT_IN * ppl)) + 1)
            foot = rows[-max(3, len(rows) // 5):]
            ho, hd = chord(loops | tails, top, foot, fw), chord(loops_d | tails_d, top, foot, fw)
            out['hang'] = dict(value=None if ho is None or hd is None else abs(ho - hd),
                               ours=None if ho is None else round(ho, 2), design=None if hd is None else round(hd, 2))
        else:
            why = '%d rows where both show the bow (under %d)' % (ok.sum(), MIN_ROWS)
            out['reach'], out['hang'] = dict(value=None, why=why), dict(value=None, why=why)
    ld = pq.clean(loops_d, ppl) if loops_d.sum() >= LOOP_MIN_PX else None
    if ld is not None:
        lo = pq.clean(loops, ppl) if loops.sum() >= LOOP_MIN_PX else None
        lr = np.nonzero(ld.any(1))[0]
        Pd = runs(ld, lr[0], lr[-1], ppl)
        Po = runs(lo, lr[0], lr[-1], ppl) if lo is not None else None
        out['thick'] = dict(value=None if Po is None else float(np.sqrt(np.mean((Po - Pd) ** 2))),
                            ours=None if Po is None else [round(float(x), 3) for x in Po],
                            design=[round(float(x), 3) for x in Pd],
                            z=[round(float(z(lr[0])), 3), round(float(z(lr[-1])), 3)])
        eo, ed = (ellipse(lo, ppl) if lo is not None else None), ellipse(ld, ppl)
        out['lean'] = dict(value=None if eo is None else abs(eo['lean'] - ed['lean']),
                           ours=eo and eo['lean'], design=ed['lean'])
        out['loops'] = dict(ours=eo, design=ed)
    return out


def forward(loops_d, jacket_d):
    """which way is forward on a profile grid: the drawn bow lies in front of the drawn jacket. -> -1 (left) or 1."""
    return -1 if np.nonzero(loops_d)[1].mean() < np.nonzero(jacket_d)[1].mean() else 1


# ------------------------------------------------------------------------------------------------------------ the part
@qa_part('bow_profile', order=1765, table='bow_profile')
def bow_profile(B, design=None, out=None):
    """Michael's flag on the bow in profile (2026-09-30): the tails' forward projection and hang, the loops' thickness
    and lean, against the design's."""
    return measure(B, design)


def measure(B, design):
    """the checks on a bundle against the design (qa3d.Design) -> (table, checks)."""
    from . import bodymeasure
    ctx = design.sheet_context()
    if 'why' in ctx:
        return None, {'bow_profile': {'status': 'SKIPPED', 'why': ctx['why']}}
    got = bodymeasure.piece_masks(B.spec)
    if got is None:
        return None, {'bow_profile': {'status': 'SKIPPED', 'why': 'no outfit_masks produced for this spec'}}
    masks, graph, paths = got
    for p in paths:
        design._rec(p)
    dv = design.design_views()
    if 'profile' not in dv:
        return None, {'bow_profile': {'status': 'SKIPPED', 'why': 'the design has no profile view'}}
    ppl = ctx['ppl']
    O, names = split_labels(B, ppl, ctx['az3'])
    sh = dv['profile']['cls'].shape if O is None else O['profile'].shape

    def drawn(pid, view='profile'):
        m = masks.get('%s__%s' % (view, pid))
        o = np.zeros(sh, bool)
        if m is not None:
            h, w = min(sh[0], m.shape[0]), min(sh[1], m.shape[1])
            o[:h, :w] = m[:h, :w]
        return o
    loops_d, tails_d = drawn('bow'), drawn('bow_tail_L') | drawn('bow_tail_R')
    if loops_d.sum() < LOOP_MIN_PX or tails_d.sum() < 50:
        return None, {'bow_profile': {'status': 'SKIPPED', 'why': "the design's profile shows too little of the bow"}}
    tf = drawn('bow_tail_L', 'front') | drawn('bow_tail_R', 'front')
    top_row = int(np.nonzero(tf.any(1))[0][0]) if tf.any() else None
    fw = forward(loops_d, drawn('top') | drawn('bodice_panel'))
    if O is None:
        loops = tails = np.zeros(sh, bool)
    else:
        loops, tails = O['profile'] == LOOPS, O['profile'] == TAILS
    M = profile_measure(loops, tails, loops_d, tails_d, ppl, fw, top_row)
    C = {}
    rows = M.get('rows') or {}
    rt = M.get('reach') or {'value': None}
    C['bow_profile_tail_reach'] = _check('reach', rt['value'], median=rt.get('median'), max=rt.get('max'),
                                         rows=rows, why=rt.get('why'),
                                         note="the ribbons' forward projection: the bow's front edge per row from the "
                                              "knot (%.2f L above the drawn tails' top in front) to %d%% of the way "
                                              "down the drawn tails, ours less the design's (L), the %dth percentile "
                                              "of its size; median beside (+ ours forward)" % (
                                                  KNOT, 100 * TAIL_FOOT, TAIL_Q))
    hg = M.get('hang') or {'value': None}
    C['bow_profile_tail_hang'] = _check('hang', hg['value'], ours=hg.get('ours'), design=hg.get('design'),
                                        why=hg.get('why'),
                                        note="the ribbons' hang: the chord of the front edge from where they leave the "
                                             "knot to their foot, from the vertical (degrees, + the lower end "
                                             "forward), ours less the design's")
    th = M.get('thick') or {'value': None}
    C['bow_profile_loop_thick'] = _check('thick', th['value'], ours=th.get('ours'), design=th.get('design'),
                                         note="the loops' thickness in profile: their run per row at tenths of the "
                                              "drawn loops' height, RMS against the design's (L; 0 where ours has none)")
    ln = M.get('lean') or {'value': None}
    C['bow_profile_loop_lean'] = _check('lean', ln['value'], ours=ln.get('ours'), design=ln.get('design'),
                                        note="the loops' lean in profile: their silhouette's equivalent-ellipse major "
                                             "axis from the vertical, ours less the design's (degrees; a lobe lying "
                                             "round the chest reads as a tipped disk)")
    T = dict(M, fw=fw, top_row=top_row)
    return T, C
