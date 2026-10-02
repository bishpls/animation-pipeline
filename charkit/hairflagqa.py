"""Michael's flags on the hair (2026-09-30 evening review of preview 1580f95; tool/hair5, docs/workstreams/hair5.md),
each measured on the design's grids (bodyqa.design_views: the body sheet's scale) against the design measured the same
way. Ours: every hair component (a lock of a mass piece, a bun's part, the ahoge, each flyaway blade) z-buffered with
its own code in the QA's scene (skin, eyes, mouth, accessories and garments occlude), and our ink inside the hair: the
boundaries between two of our hair parts (where one lock's shell meets another, the outline hulls draw a line). The
design: the hand-checked hair truth (charkit/refs/clawd/hair_truth.npz; tool/hairtag) and the sheet's drawn lines
(bodyqa's raw line class and outfit.ridges' faint lines). Every check carries its flag (registry.flag_check): the merge
gate blocks on its regressions. Calibration: charkit/calib/hairflags.py.

Checks (qa3d part 'hair_flags'; lengths in L):
  hair_ahoge_shape
        the ahoge per view (front, three-quarter, profile, back): our visible ahoge against the drawn one (the truth's,
        cut at the head's outline, its drawn outline absorbed), as the boundary F-score within AHOGE_TOL at the best
        placement within AHOGE_SHIFT (its shape, not where each drawing puts it: the views place it inconsistently);
        the worst view graded, the placement offsets reported. Michael: "the ahoge has warped (it was a clean curved
        strand at the start of the day; now bent and jagged)"
  hair_ahoge_bend
        the ahoge's centreline per view (the centroids of its pixels in bins of path distance from its root): the
        turning that isn't one steady curl (total absolute turning less net turning, degrees; a crescent reads near 0,
        an S-bend or a kink high), beyond the design's; the worst view
  hair_attached
        every hair part that isn't a lock of the mass (the ahoge, each flyaway blade, each bun's part) against the rest
        of the hair, per view: the gap between its visible pixels and the other hair's (L; 0 where they touch); the
        worst part in its worst view. Michael: "the flyaway by the right bun is disconnected (floats in the air, front
        and back views)"
  hair_back_lines
        the back view's ink inside the mass (away from the hair's outline, the buns, the ahoge and the clips): L of line
        per L^2, ours less the design's. Michael: "vertical stripes (ink lines down the back mass) that are off-model"
  hair_back_hem
        the back view's hem: the lock tips along the hair's lower edge (qa3d.hair_tips: lower than their neighbours by
        HEM_PROM), ours against the drawing's; the edge's waviness (RMS about itself smoothed over HEM_SMOOTH, L)
        reported. Michael: "the design's back has a smooth mass with a wavy, flicked hem and flicks at the sides;
        ours is a smooth bob"
  hair_lock_lines_three_quarter, hair_lock_lines_profile
        the layering's structure: our ink inside the mass against the drawn lines there, as a line F-score within
        LINE_TOL (recall: the drawn locks we part; precision: our lines the drawing has). Michael: "much of the layering
        is a solid orange mass, or artifacting and janky, in three-quarter and side views"

    table, checks = hairflagqa.measure(B, design)            # charkit.qa3d's 'hair_flags' part
    hairflagqa.measure_labels(ours, pieces, D, ppl, lines)   # the measures on any label and line images
"""
import numpy as np

from .registry import flag_check, qa_part

VIEWS = ('front', 'three_quarter', 'profile', 'back')
OTHER = 1                   # our label images: 0 nothing, 1 another surface, PART0 + i hair part i
PART0 = 100
MASS = ('bangs', 'side_lock_L', 'side_lock_R', 'upper_back', 'lower_back')
FAMILY = {'bangs': 'bangs', 'side_lock_L': 'side_locks', 'side_lock_R': 'side_locks', 'upper_back': 'upper_back',
          'lower_back': 'lower_back', 'bun_L': 'buns', 'bun_R': 'buns', 'ahoge': 'ahoge', 'flyaways': 'flyaways'}
AHOGE_TOL = 0.01            # L: an outline pixel this close to the other's agrees (two pixels at the sheet's scale)
AHOGE_SHIFT = 0.03          # L: the placements tried either way (the shape is graded; the placement is reported)
AHOGE_BINS = 10             # the centreline's bins along the ahoge
BASE_PX = 6                 # px: its root is where it touches the other hair within this of the lowest such pixel
EDGE = 0.02                 # L: ink within this of the hair's outline is the outline's, not inside it
CLEAR = 0.02                # L: ... and within this of a bun, the ahoge or a clip is theirs
LINE_TOL = 0.012            # L: a line pixel within this of the other's agrees
HEM_PROM = 0.03             # L: a hem tip hangs this far below its neighbours (qa3d.HAIR_TIP_PROM)
HEM_SMOOTH = 0.08           # L: the hem's waviness is its deviation from itself smoothed over this
MIN_PX = 12                 # a part showing fewer pixels in a view isn't measured there
LIMITS = {                  # (pass at, warn at); see each check for its direction. Calibrated (tool/hair5, 2026-09-30;
                            # charkit/calib/records): the design moved 1-2 px, the known-bad hair5_1580f95, the floors
    'ahoge_shape': (0.75, 0.55),        # F at least: the design 1.0 at every move; 1580f95 0.371; the floors (turned
                                        # 25-45 deg, a clump) 0.20 / 0.27; a 1.5-wave bend 0.55 (WARN)
    'ahoge_bend': (25.0, 50.0),         # degrees beyond the design's, at most: the design 0; 1580f95 107; turned 38; the
                                        # 1.5-wave bend 78
    'attached': (0.006, 0.015),         # L, at most (1.3 and 3.2 px): the design 0 at every move; 1580f95 0.033
    'back_lines': (0.5, 1.0),           # L per L^2 beyond the design's, at most: the design -0.07..0.26 over the moves
                                        # (the drawing's 1.30); 1580f95 4.56; the stripes probe 8.3
    'back_hem': (2, 4),                 # tips fewer or more than the drawing's, at most: the design 0 (8 tips);
                                        # 1580f95 5 (3 tips); a smoothed hem 8
    'lock_lines': (0.7, 0.45),          # F at least: the design 0.96-1.0 over the moves; 1580f95 0.18-0.21; a random
                                        # partition of the drawing's length 0.06-0.07; the thirds of the gap
}
FLAGS = {
    'ahoge': 'the ahoge has warped: a clean curved strand at the start of the day, now bent and jagged (Michael '
             '2026-09-30)',
    'attached': 'the flyaway by the right bun is disconnected, floating in the air in front and back (Michael '
                '2026-09-30)',
    'back_lines': 'the back view: vertical stripes, ink lines down the back mass, off-model (Michael 2026-09-30)',
    'back_hem': "the back view: the design's wavy, flicked hem and side flicks; ours a smooth bob (Michael 2026-09-30)",
    'lock_lines': 'the layering is a solid orange mass, or artifacting and janky, in three-quarter and side views '
                  '(Michael 2026-09-30)',
}


def _grade(key, v, higher=False):
    p, w = LIMITS[key]
    if higher:
        return 'PASS' if v >= p else 'WARN' if v >= w else 'FAIL'
    return 'PASS' if v <= p else 'WARN' if v <= w else 'FAIL'


def shift(a, dy, dx, fill=0):
    """an image moved dy rows down and dx columns right."""
    out = np.full_like(a, fill)
    H, W = a.shape[:2]
    ys, yd = (slice(0, H - dy), slice(dy, H)) if dy >= 0 else (slice(-dy, H), slice(0, H + dy))
    xs, xd = (slice(0, W - dx), slice(dx, W)) if dx >= 0 else (slice(-dx, W), slice(0, W + dx))
    out[yd, xd] = a[ys, xs]
    return out


def window(*ms, pad=20):
    m = np.zeros_like(ms[0], bool)
    for x in ms:
        m |= x
    r, c = np.nonzero(m)
    if not len(r):
        return None
    return (slice(max(0, r.min() - pad), r.max() + pad + 1), slice(max(0, c.min() - pad), c.max() + pad + 1))


def outline(m):
    from scipy import ndimage
    return m & ~ndimage.binary_erosion(m, border_value=0)


# ------------------------------------------------------------------------------------------------------------ the ahoge
def ahoge_shape(ours, drawn, ppl):
    """the boundary F-score of two masks within AHOGE_TOL at the best placement of ours within AHOGE_SHIFT
    -> dict(f, shift (L: rows down, columns right), f0 (in place))."""
    from scipy import ndimage
    w = window(ours, drawn, pad=int(AHOGE_SHIFT * ppl) + 4)
    if w is None or not ours.any() or not drawn.any():
        return None
    o, d = ours[w], drawn[w]
    bd = outline(d)
    to_d = ndimage.distance_transform_edt(~bd)
    tol = AHOGE_TOL * ppl
    S = int(round(AHOGE_SHIFT * ppl))
    best, f0 = (-1.0, 0, 0), None
    for dy in range(-S, S + 1):
        for dx in range(-S, S + 1):
            bo = outline(shift(o, dy, dx, False))
            if not bo.any():
                continue
            p = float((to_d[bo] <= tol).mean())
            r = float((ndimage.distance_transform_edt(~bo)[bd] <= tol).mean())
            f = 2 * p * r / (p + r) if p + r else 0.0
            if dy == 0 and dx == 0:
                f0 = f
            if f > best[0] + 1e-9 or (abs(f - best[0]) <= 1e-9 and dy * dy + dx * dx < best[1] ** 2 + best[2] ** 2):
                best = (f, dy, dx)
    return dict(f=round(best[0], 4), shift=[round(best[1] / ppl, 4), round(best[2] / ppl, 4)],
                f0=None if f0 is None else round(f0, 4))


def centreline(m, root, n=AHOGE_BINS):
    """a strand's centreline: its pixels in n bins of path distance (8-connected, within the strand) from its root (its
    pixels touching `root`, a mask: where it grows from; else its pixel nearest it), each bin's centroid -> ((k, 2)
    rows, cols; (k,) half-widths px) or None."""
    from scipy import ndimage
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import dijkstra
    r, c = np.nonzero(m)
    if len(r) < MIN_PX:
        return None
    idx = -np.ones(m.shape, int)
    idx[r, c] = np.arange(len(r))
    rows, cols, ws = [], [], []
    for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
        rr, cc = r + dy, c + dx
        ok = (rr >= 0) & (rr < m.shape[0]) & (cc >= 0) & (cc < m.shape[1])
        j = np.where(ok, idx[np.clip(rr, 0, m.shape[0] - 1), np.clip(cc, 0, m.shape[1] - 1)], -1)
        k = j >= 0
        rows += list(np.arange(len(r))[k]); cols += list(j[k]); ws += [float(np.hypot(dy, dx))] * int(k.sum())
    G = coo_matrix((ws, (rows, cols)), shape=(len(r), len(r))).tocsr()
    start = None
    if root is not None and root.any():
        touch = ndimage.binary_dilation(root, iterations=1)[r, c]
        if touch.any():
            # every pixel on its root, within BASE_PX of the lowest (it grows up from the crown: a side lying over a bun
            # or a lock isn't its root), so a base cut across starts mid-way
            touch &= r >= r[touch].max() - BASE_PX
            start = np.nonzero(touch)[0]
        else:
            start = [int(np.argmin(ndimage.distance_transform_edt(~root)[r, c]))]
    if start is None:
        start = [int(np.argmax(r))]                        # (no root: its lowest pixel)
    d = dijkstra(G, directed=False, indices=start, min_only=True)
    ok = np.isfinite(d)
    r, c, d = r[ok], c[ok], d[ok]
    edges = np.linspace(0, d.max() + 1e-9, n + 1)
    P, W = [], []
    for a, b in zip(edges[:-1], edges[1:]):
        s = (d >= a) & (d < b)
        if s.sum() < 2:
            continue
        p = np.array([r[s].mean(), c[s].mean()])
        P.append(p)
        W.append(float(np.percentile(np.hypot(r[s] - p[0], c[s] - p[1]), 85)))
    return (np.array(P), np.array(W)) if len(P) >= 4 else None


def bend(m, root):
    """the centreline's turning that isn't one steady curl: sum |turn| - |sum turn| (degrees) -> float or None."""
    got = centreline(m, root)
    if got is None:
        return None
    d = np.diff(got[0], axis=0)
    turn = np.diff(np.unwrap(np.arctan2(d[:, 0], d[:, 1])))
    return float(np.degrees(np.abs(turn).sum() - abs(turn.sum())))


# ------------------------------------------------------------------------------------------------------------ attached
def gaps(lab, pieces, ppl):
    """per visible part that isn't a mass lock (MIN_PX pixels or more): the gap between it and every other hair pixel
    (L) -> {part index: gap}."""
    from scipy import ndimage
    hair = lab >= PART0
    out = {}
    for i, pc in enumerate(pieces):
        if pc in MASS or pc not in FAMILY:
            continue
        m = lab == PART0 + i
        if m.sum() < MIN_PX:
            continue
        w = window(m, pad=int(0.2 * ppl))
        rest = (hair & ~m)[w]
        if not rest.any():
            out[i] = 0.2
            continue
        g = float(ndimage.distance_transform_edt(~rest)[m[w]].min()) - 1.0     # (8-adjacent: 1 or 1.41 apart: 0)
        out[i] = round(max(0.0, g) / ppl, 4)
    return out


# ------------------------------------------------------------------------------------------------------------ lines
def part_lines(lab):
    """the boundaries between two different hair parts (both hair): where one lock's shell meets another."""
    b = np.zeros(lab.shape, bool)
    for a0, a1 in (((slice(None, -1), slice(None)), (slice(1, None), slice(None))),
                   ((slice(None), slice(None, -1)), (slice(None), slice(1, None)))):
        x, y = lab[a0], lab[a1]
        b[a0] |= (x != y) & (x >= PART0) & (y >= PART0)
    return b


def mass_interior(hair, other, ppl):
    """the mass's inside: the hair (its silhouette's gaps closed) further than EDGE from its outline and CLEAR from
    `other` (the buns, the ahoge, the clips)."""
    from scipy import ndimage
    solid = ndimage.binary_fill_holes(ndimage.binary_closing(hair, iterations=2))
    keep = ndimage.distance_transform_edt(solid) > EDGE * ppl
    if other is not None and other.any():
        keep &= ndimage.distance_transform_edt(~other) > CLEAR * ppl
    return keep


def skeleton(line):
    from skimage.morphology import skeletonize
    return skeletonize(line)


def line_f(ours, drawn, keep, ppl, tol=LINE_TOL):
    """two line images' agreement within keep (skeletons; a pixel within tol of the other's agrees) -> dict(p, r, f,
    ours_L, drawn_L)."""
    from scipy import ndimage
    a, b = skeleton(ours) & keep, skeleton(drawn) & keep
    rec = dict(ours_L=round(float(a.sum()) / ppl, 3), drawn_L=round(float(b.sum()) / ppl, 3))
    if not a.any() or not b.any():
        return dict(rec, p=0.0, r=0.0, f=0.0)
    p = float((ndimage.distance_transform_edt(~b)[a] <= tol * ppl).mean())
    r = float((ndimage.distance_transform_edt(~a)[b] <= tol * ppl).mean())
    return dict(rec, p=round(p, 4), r=round(r, 4), f=round(2 * p * r / (p + r) if p + r else 0.0, 4))


# ------------------------------------------------------------------------------------------------------------ the hem
def hem(hair, ppl, prom=HEM_PROM):
    """the hair's lower edge: its tips (qa3d.hair_tips) and its waviness (L RMS about itself smoothed over
    HEM_SMOOTH) -> dict(tips, wave)."""
    from scipy.ndimage import gaussian_filter1d
    from . import qa3d
    cols = np.nonzero(hair.any(0))[0]
    if len(cols) < 5:
        return None
    rows = np.arange(hair.shape[0])
    low = np.array([rows[hair[:, c]].max() for c in cols], float)
    wave = low - gaussian_filter1d(low, HEM_SMOOTH * ppl / 2.355, mode='nearest')
    return dict(tips=qa3d.hair_tips(hair, ppl, prom), wave=round(float(np.sqrt((wave ** 2).mean())) / ppl, 4))


# ------------------------------------------------------------------------------------------------------------ the design
PIECE_OF = {'bangs': 'bangs', 'side_locks': 'side_lock_L', 'upper_back': 'upper_back', 'lower_back': 'lower_back',
            'buns': 'bun_L', 'bun_L': 'bun_L', 'bun_R': 'bun_R', 'ahoge': 'ahoge', 'flyaways': 'flyaways'}


def drawn_hair(dv):
    """a design view's drawn hair: its hair class (lines absorbed) in the figure, the clips out."""
    from .bodyqa import CLASS
    h = (dv['cls'] == CLASS['hair']) & dv['fg']
    acc = dv.get('accessory')
    return h & ~acc if acc is not None and acc.shape == h.shape else h


def drawn_lines(dv):
    """the drawing's lines: its line class and faint drawn lines (outfit.ridges), skin left out."""
    from .bodyqa import CLASS
    from . import outfit
    raw = dv['raw']
    return ((raw == CLASS['line']) | (outfit.ridges(dv['rgb']) & (raw != CLASS['skin']))) & dv['fg']


def design_labels(truth, dvs, views=VIEWS):
    """the design as our label images: each region of the hair truth (a connected run of one label set) a part, its
    piece the set's first label's (PIECE_OF); the drawn hair's other pixels (lines, cut paths, unscored bits) go to the
    nearest part, as our shells meet with no ink between them. -> ({view: label image}, [piece per part])."""
    from scipy import ndimage
    T, sets, _ = truth
    out, pieces = {}, []
    for v in views:
        if v not in T or v not in dvs:
            continue
        t, dv = T[v], dvs[v]
        lab = np.zeros(t.shape, np.int32)
        for k in np.unique(t[t >= 0]):
            comp, n = ndimage.label(t == k)
            pc = PIECE_OF.get(sets[int(k)][0], sets[int(k)][0])
            for c in range(1, n + 1):
                m = comp == c
                if m.sum() < 3:
                    continue
                lab[m] = PART0 + len(pieces)
                pieces.append(pc)
        todo = drawn_hair(dv) & (lab == 0)
        if todo.any() and (lab >= PART0).any():
            _, (iy, ix) = ndimage.distance_transform_edt(lab < PART0, return_indices=True)
            lab[todo] = lab[iy[todo], ix[todo]]
        lab[(lab == 0) & dv['fg']] = OTHER
        out[v] = lab
    return out, pieces


def design_side(truth, dvs, ppl, views=VIEWS):
    """the design's inputs to measure_labels: per view the drawn hair, its mass's inside, its lines there and its ahoge
    (the truth's, its drawn outline absorbed), and the design's own values (its ahoge's bend)."""
    from scipy import ndimage
    lab, pieces = design_labels(truth, dvs, views)
    D = dict(hair={}, keep={}, lines={}, ahoge={}, ahoge_root={}, design={'ahoge_bend': {}})
    for v in views:
        if v not in dvs or v not in lab:
            continue
        L = lab[v]
        lut = np.array(['-'] * (int(L.max()) + 1), object)
        for i, p in enumerate(pieces):
            if PART0 + i < len(lut):
                lut[PART0 + i] = p
        piece_img = lut[L]
        hair = drawn_hair(dvs[v])
        other = np.isin(piece_img, ['bun_L', 'bun_R', 'ahoge'])
        acc = dvs[v].get('accessory')
        if acc is not None and acc.shape == other.shape:
            other |= acc
        D['hair'][v] = hair
        D['keep'][v] = mass_interior(hair | other, other, ppl)
        D['lines'][v] = drawn_lines(dvs[v])
        ah = piece_img == 'ahoge'
        D['ahoge'][v] = ah
        D['ahoge_root'][v] = ndimage.binary_dilation(ah, iterations=2) & (L >= PART0) & ~ah
        b = bend(ah, D['ahoge_root'][v]) if ah.sum() >= MIN_PX else None
        D['design']['ahoge_bend'][v] = None if b is None else round(b, 1)
    return D


# ------------------------------------------------------------------------------------------------------------ measures
def our_mask(ours, pieces, names):
    code = [PART0 + i for i, p in enumerate(pieces) if p in names]
    return np.isin(ours, code)


def measure_labels(ours, pieces, D, ppl, lines=None, views=VIEWS):
    """every measure on label images: ours {view: label image (0 nothing, OTHER, PART0 + i hair part i)}, pieces [piece
    of part i], lines {view: our ink inside the hair} (default: part_lines); D: design_side()'s -> (table, checks)."""
    from scipy import ndimage
    pieces = list(pieces)
    table, C = {}, {}
    # the ahoge
    shp, bnd = {}, {}
    for v in views:
        if v not in ours or v not in D['ahoge'] or D['ahoge'][v].sum() < MIN_PX:
            continue
        lab = ours[v]
        ah = our_mask(lab, pieces, ('ahoge',))
        root = ndimage.binary_dilation(ah, iterations=2) & (lab >= PART0) & ~ah
        s = ahoge_shape(ah, D['ahoge'][v], ppl) if ah.sum() >= MIN_PX else None
        b = bend(ah, root) if ah.sum() >= MIN_PX else None
        db = D['design']['ahoge_bend'].get(v)
        shp[v] = dict(s or dict(f=0.0, shift=None, f0=0.0), px=[int(ah.sum()), int(D['ahoge'][v].sum())])
        bnd[v] = dict(ours=None if b is None else round(b, 1), design=db,
                      excess=None if b is None or db is None else round(b - db, 1))
    table['ahoge'] = dict(shape=shp, bend=bnd)
    if shp:
        worst = min(shp, key=lambda v: shp[v]['f'])
        f = shp[worst]['f']
        C['hair_ahoge_shape'] = flag_check(dict(value=f, worst=worst, views={v: x['f'] for v, x in shp.items()},
                                                shift_L={v: x['shift'] for v, x in shp.items()},
                                                status=_grade('ahoge_shape', f, higher=True)), FLAGS['ahoge'])
    ex = {v: x['excess'] for v, x in bnd.items() if x['excess'] is not None}
    if ex:
        worst = max(ex, key=ex.get)
        x = round(max(0.0, ex[worst]), 1)
        C['hair_ahoge_bend'] = flag_check(dict(value=x, worst=worst, views=ex, status=_grade('ahoge_bend', x)),
                                          FLAGS['ahoge'])
    # attached
    att = {}
    for v in views:
        if v in ours:
            att[v] = {'%s.%d' % (pieces[i], i): x for i, x in gaps(ours[v], pieces, ppl).items()}
    table['attached'] = att
    allg = [(x, v, p) for v, g in att.items() for p, x in g.items()]
    if allg:
        x, v, p = max(allg)
        C['hair_attached'] = flag_check(dict(value=x, worst=[v, p], detached=sum(1 for y, _, _ in allg if y > 0),
                                             views={v: max(g.values()) if g else 0.0 for v, g in att.items()},
                                             status=_grade('attached', x)), FLAGS['attached'])
    # the ink inside the mass
    ln = {}
    for v in views:
        if v not in ours or v not in D['keep']:
            continue
        lab = ours[v]
        other = our_mask(lab, pieces, ('bun_L', 'bun_R', 'ahoge')) | (lab == OTHER)
        keep_o = mass_interior(lab >= PART0, other, ppl)
        lo = skeleton(part_lines(lab) if lines is None or v not in lines else lines[v]) & keep_o
        lo_len = float(lo.sum()) / ppl
        ld_len = float((skeleton(D['lines'][v]) & D['keep'][v]).sum()) / ppl
        ao, ad = keep_o.sum() / ppl ** 2, D['keep'][v].sum() / ppl ** 2
        rec = dict(ours=round(float(lo_len / max(ao, 1e-6)), 3), design=round(float(ld_len / max(ad, 1e-6)), 3))
        rec['excess'] = round(rec['ours'] - rec['design'], 3)
        rec.update(line_f(lo, D['lines'][v], keep_o & D['keep'][v], ppl))
        ln[v] = rec
    table['lines'] = ln
    if 'back' in ln:
        x = ln['back']['excess']
        C['hair_back_lines'] = flag_check(dict(value=x, ours=ln['back']['ours'], design=ln['back']['design'],
                                               views={v: r['excess'] for v, r in ln.items()},
                                               status=_grade('back_lines', x)), FLAGS['back_lines'])
    for v in ('three_quarter', 'profile'):
        if v in ln:
            f = ln[v]['f']
            C['hair_lock_lines_' + v] = flag_check(dict(value=f, p=ln[v]['p'], r=ln[v]['r'],
                                                        status=_grade('lock_lines', f, higher=True)),
                                                   FLAGS['lock_lines'])
    # the back's hem
    if 'back' in ours and 'back' in D['hair']:
        ho = hem(ours['back'] >= PART0, ppl)
        hd = hem(D['hair']['back'], ppl)
        if ho and hd:
            d = abs(ho['tips'] - hd['tips'])
            table['hem'] = dict(ours=ho, design=hd)
            C['hair_back_hem'] = flag_check(dict(value=d, tips=[ho['tips'], hd['tips']],
                                                 wave_L=[ho['wave'], hd['wave']], status=_grade('back_hem', d)),
                                            FLAGS['back_hem'])
    return table, C


# ------------------------------------------------------------------------------------------------------------ the part
def our_labels(B, design, hair=None):
    """our hair on the design's grids: every hair object's connected components (a lock, a bun's part, the ahoge, a
    flyaway blade) z-buffered with its own code among the QA's occluders (hair_pieces_measure's: skin, eyes, mouth,
    accessories, garments); hair: {piece: (V, T)} in place of the bundle's hair objects (a lab's rebuilt pieces)
    -> ({view: label image}, [piece of each part])."""
    from . import bodyqa, qa3d
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    sc = design.sheet_context()
    As = B.assembly
    meshes = []
    V, T = B.skin().mesh('masked')[:2]
    meshes.append((V, T, np.full(len(T), OTHER)))
    hide = design.hidden('hair')                 # (against the hair's shape truth: ours without our clips)
    for o in B.objects(groups=('eye', 'mouth', 'accessory', 'garment')):
        if o.has('eval') and o.name not in hide:
            V, T = o.mesh('eval')[:2]
            meshes.append((V, T, np.full(len(T), OTHER)))
    pieces = []
    if hair is None:
        hair = {o.name[5:]: _surface(o) for o in B.objects(groups=('hair',))
                if o.name.startswith('hair_') and o.name[5:] in FAMILY and o.has('eval')}
    for pc, (V, T) in hair.items():
        if pc not in FAMILY:
            continue
        T = np.asarray(T)
        E = np.r_[T[:, [0, 1]], T[:, [1, 2]]]
        k, comp = connected_components(coo_matrix((np.ones(len(E)), (E[:, 0], E[:, 1])), shape=(len(V), len(V))),
                                       directed=False)
        tc = comp[T[:, 0]]
        for c in range(k):
            t = T[tc == c]
            if len(t):
                meshes.append((np.asarray(V, float), t, np.full(len(t), PART0 + len(pieces))))
                pieces.append(pc)
    dv = design.shape_views('hair')
    lab = bodyqa.zbuffer_views(meshes, sc['az3'], np.array(qa3d.iris_centres(B)), As['centre'], As['L'], sc['ppl'],
                               [v for v in VIEWS if v in dv])
    return {v: np.maximum(l[1], 0).astype(np.int32) for v, l in lab.items()}, pieces


def _ink_slots(o):
    from .qa3d import is_ink
    return [k for k, m in enumerate(o.materials or []) if is_ink(m)]


def _surface(o):
    """a hair object's surface (its eval mesh) without its ink strokes (charkit.geom.hairink's ribbons on an ink slot:
    lines, not hair) -> (V, T)."""
    V, T, tm, _ = o.mesh('eval')
    ink = _ink_slots(o)
    return (V, T) if not ink else (V, np.asarray(T)[~np.isin(tm, ink)])


INK = 4                     # our ink's label in our_ink's z-buffer (an outline hull's visible face; bodyqa's line
                            # class, which the raster draws at least a pixel wide)
LINE_W = 0.0014             # m: the hair's outline width (scene.hair_pieces_objects' shade.outline), for rebuilt pieces


def our_ink(B, design, hair=None, weights=None):
    """our hair's ink as the render draws it, on the design's grids: each hair object's surface pulled in by its
    outline (the bundle's per-vertex shrink: the outline's SOLIDIFY with its vertex-group widths) and its hull on the
    original surface, flipped and back-face culled per view (qa3d.render_surfaces), z-buffered among the QA's other
    surfaces, with its ink strokes (an ink slot's faces: charkit.geom.hairink) as ink where they lie; the pixels where
    a hull or a stroke shows. hair {piece: (V, T)}: rebuilt pieces (a lab's), their shrink made from the
    angle-weighted normals and LINE_W, times weights {piece: per-vertex 0..1} (the outline_w vertex group) where given.
    -> {view: bool image}."""
    from . import bodyqa, qa3d
    from .geom.mesh import vertex_normals
    sc = design.sheet_context()
    As = B.assembly
    others = []
    V, T = B.skin().mesh('masked')[:2]
    others.append((V, T, np.full(len(T), OTHER)))
    hide = design.hidden('hair')
    for o in B.objects(groups=('eye', 'mouth', 'accessory', 'garment')):
        if o.has('eval') and o.name not in hide:
            V, T = o.mesh('eval')[:2]
            others.append((V, T, np.full(len(T), OTHER)))
    surf, hulls, strokes = [], [], []
    if hair is None:
        for o in B.objects(groups=('hair',)):
            if not (o.name.startswith('hair_') and o.name[5:] in FAMILY and o.has('eval')):
                continue
            V, T, tm, _ = o.mesh('eval')
            sh = o.a('eval', 'shrink')
            T = np.asarray(T)
            ink = np.isin(tm, _ink_slots(o))
            if ink.any():                     # (its ink strokes, charkit.geom.hairink: drawn as ink where they lie)
                strokes.append((np.asarray(V, float), T[ink]))
                T = T[~ink]
            surf.append((V + sh if sh is not None else V, T))
            if sh is not None:
                # (a hull face with no width at any corner lies on the surface it came from: no ink; the outline_w
                # group's zeros. Drawn at least a pixel wide, its edge-on slivers would read as dashes)
                wd = np.linalg.norm(sh, axis=1)[T].max(1)
                hulls.append((np.asarray(V, float), T[wd > 0.1 * LINE_W][:, ::-1]))
    else:
        for pc, (V, T) in hair.items():
            if pc not in FAMILY:
                continue
            V, T = np.asarray(V, float), np.asarray(T)
            w = LINE_W * (np.asarray(weights[pc], float) if weights and pc in weights else np.ones(len(V)))
            n = vertex_normals(V, T)
            surf.append((V - n * w[:, None], T))
            hulls.append((V, T[w[T].max(1) > 0.1 * LINE_W][:, ::-1]))
    dv = design.shape_views('hair')
    out = {}
    az = bodyqa.azimuths(sc['az3'])
    iw = np.array(qa3d.iris_centres(B))
    for v in VIEWS:
        if v not in dv:
            continue
        a = np.radians(az[v])
        view_d = np.array([-np.sin(a), np.cos(a), 0.0])
        meshes = list(others) + [(V, T, np.full(len(T), PART0)) for V, T in surf] + \
            [(V, T, np.full(len(T), INK)) for V, T in strokes]
        for V, T in hulls:
            fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
            keep = fn @ view_d <= 0
            meshes.append((V, T[keep], np.full(int(keep.sum()), INK)))
        lab = bodyqa.zbuffer_views(meshes, sc['az3'], iw, As['centre'], As['L'], sc['ppl'], [v])[v][1]
        out[v] = lab == INK
    return out


def our_lines(B, design, ours, hair=None, weights=None):
    """our ink inside the hair per view (our_ink; the calibration patches this with its stand-ins)."""
    return our_ink(B, design, hair, weights)


def truth_path(B):
    from . import manifest
    ref = B.spec.get('ref') if isinstance(B.spec.get('ref'), dict) else {}
    if not ref.get('manifest'):
        return None
    r = manifest.load(ref['manifest'])['references'].get('hair_truth')
    return r['path'] if r else None


def truth_for(design, truth):
    """the hair truth as the hair's shape truth reads it (charkit.shapetruth): its labels under the drawn clips cleared,
    so the redraw's hair there joins the nearest drawn lock (design_labels' rule for the drawn hair it doesn't label);
    the truth itself where the hair declares none."""
    if not design.hidden('hair'):
        return truth
    T, sets, meta = truth
    sv = design.shape_views('hair')
    out = {}
    for v, t in T.items():
        cov = (sv.get(v) or {}).get('covered')
        if cov is not None and cov.shape == t.shape and cov.any():
            t = np.where(cov, -1, t)
        out[v] = t
    return out, sets, meta


def design_inputs(B, design):
    """design_side() for the bundle's references, made once per Design -> (D, ppl) or (None, why)."""
    from . import hairlayers
    if ('hair_flags', 'D') in design._m:
        return design._m[('hair_flags', 'D')]
    ctx = design.sheet_context()
    tp = truth_path(B)
    if 'why' in ctx or not tp:
        got = (None, ctx.get('why') or 'no hair_truth in the manifest')
    else:
        p = hairlayers._p(tp)
        design._rec(p)
        got = (design_side(truth_for(design, hairlayers.load_truth(p)), design.shape_views('hair'), ctx['ppl']),
               ctx['ppl'])
    design._m[('hair_flags', 'D')] = got
    return got


@qa_part('hair_flags', order=1450, table='hair_flags', checks=7)
def measure(B, design=None, out=None):
    """Michael's hair flags (the module's docstring) -> (table, checks)."""
    from . import qa3d
    design = design or qa3d.Design(B)
    if not any(o.name.startswith('hair_') and o.name[5:] in FAMILY for o in B.objects(groups=('hair',))):
        return None, {'hair_flags': {'status': 'SKIPPED', 'why': 'the hair is not built in pieces'}}
    D, ppl = design_inputs(B, design)
    if D is None:
        return None, {'hair_flags': {'status': 'SKIPPED', 'why': ppl}}
    ours, pieces = our_labels(B, design)
    lines = our_lines(B, design, ours)
    table, C = measure_labels(ours, pieces, D, ppl, lines=lines)
    if out:
        import os
        from .qa3d import _save_rgb
        _save_rgb(os.path.join(out, 'qa_hair_flags.png'), picture(ours, pieces, D, ppl, lines))
    return table, C


def picture(ours, pieces, D, ppl, lines=None, views=VIEWS):
    """per view the hair cropped: ours (each part a shade, detached parts red), the drawn lines inside the mass (blue)
    and our ink (dark red: lines, else our parts' boundaries); the drawn ahoge's outline (green) at our ahoge."""
    rows = []
    rng = np.random.default_rng(5)
    shade = rng.uniform(0.75, 1.0, len(pieces) + 1)
    for v in views:
        if v not in ours or v not in D['hair']:
            continue
        lab = ours[v]
        hair = lab >= PART0
        w = window(hair, D['hair'][v], pad=8)
        if w is None:
            continue
        L = lab[w]
        img = np.ones(L.shape + (3,))
        img[L == OTHER] = (0.92, 0.9, 0.87)
        h = L >= PART0
        s = shade[np.clip(L - PART0, 0, len(pieces))]
        img[h] = np.c_[0.95 * s[h], 0.6 * s[h], 0.45 * s[h]]
        g = gaps(lab, pieces, ppl)
        for i, x in g.items():
            if x > 0:
                img[L == PART0 + i] = (0.9, 0.05, 0.05)
        keep = D['keep'][v][w]
        img[(skeleton(D['lines'][v][w]) & keep)] = (0.2, 0.35, 1.0)
        ink = lines[v][w] if lines is not None and v in lines else part_lines(L)
        img[(skeleton(ink) & mass_interior(h, None, ppl))] = (0.35, 0.05, 0.05)
        img[outline(D['ahoge'][v][w])] = (0.1, 0.7, 0.2)
        rows.append(np.pad(img, ((0, 0), (0, 8), (0, 0)), constant_values=1.0))
    if not rows:
        return np.ones((8, 8, 3))
    H = max(r.shape[0] for r in rows)
    return np.concatenate([np.pad(r, ((0, H - r.shape[0]), (0, 0), (0, 0)), constant_values=1.0) for r in rows], 1)


# ------------------------------------------------------------------------------------------------------------ the lab
LAB_KEYS = ('hair_ahoge_shape', 'hair_ahoge_bend', 'hair_attached', 'hair_back_lines', 'hair_back_hem',
            'hair_lock_lines_three_quarter', 'hair_lock_lines_profile', 'hair_piece_bangs', 'hair_piece_side_locks',
            'hair_piece_upper_back', 'hair_piece_lower_back', 'hair_piece_buns', 'hair_piece_ahoge',
            'hair_piece_flyaways', 'hair_bun_outline', 'hair_tips_back', 'hair_tips_front', 'hair_fringe_low',
            'hair_penetration')


def lab_measure(B, design, hair, weights=None):
    """the hair flags and the hair pieces' checks (every family's IoU per view: the anti-gaming guard's shapes) for
    hair {piece: (V, T)} over a bundle (charkit.hairlab's rebuilt pieces) -> (checks, ours, pieces)."""
    from . import qa3d
    _, Cq = qa3d.hair_pieces_measure(B, design, {n: (vt, vt) for n, vt in hair.items()})
    D, ppl = design_inputs(B, design)
    ours, pieces = our_labels(B, design, hair)
    _, Cf = measure_labels(ours, pieces, D, ppl, lines=our_lines(B, design, ours, hair, weights))
    keep = ('value', 'status', 'views', 'tips', 'worst', 'p', 'r', 'ours', 'design', 'wave_L', 'detached', 'drawn')
    out = {k: {a: b for a, b in c.items() if a in keep} for k, c in list(Cf.items()) + list(Cq.items())
           if k in LAB_KEYS}
    return out, ours, pieces
