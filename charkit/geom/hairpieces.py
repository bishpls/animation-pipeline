"""The hair as authored pieces (Michael, 2026-09-29: cut-piece hair): the families of the hair breakdown (charkit.hairlayers:
bangs, side locks, upper and lower back, buns, ahoge, flyaways) built as separate clean meshes, each lock of a family its
own closed shell with a root on the scalp, a strand direction per vertex and a centreline chain from root to tip for the
spring bones to come. Their shape is measured from the visual hull (charkit.geom.hull), their partition from the
breakdown; the construction (layering, tips, thickness) is authored and read from the style profile (charkit.styles'
hair_pieces section).

The mass (bangs, side locks, upper and lower back) lives on the crown chart: round the hair's centre c, theta is the
angle from the crown direction k (the whorl every lock radiates from: straight up, tilted back by `crown_tilt`) and phi
the angle round it (0 the front, increasing toward her left). On that chart:
  envelope  the hull's outermost hair per cell (max radius), filled across cells no view shows (under the buns, behind
            the ears) along theta and round phi, then smoothed: one fair outer surface for the whole mass
  skin      our skin's outermost radius per cell inside the envelope: the inner surfaces keep `gap` clear of it
  families  per cell the majority family of the hull's labelled hair (charkit.hairlayers' masks carried onto the hull's
            vertices by the view that sees each one most squarely; the profile mirrored for the far side), mode-smoothed
  pieces    per family (the side locks split left and right) its columns of phi, in each the run of theta from the crown
            (or `up` degrees above its first visible cell, hidden under the piece above) down to its lowest visible cell:
            the piece's lower edge, its tips. The locks are the runs between the edge's notches (local minima of its
            reach, at least lock_min apart); each notch is deepened by `notch` so the tips read
  shell     a lock is a (u across, v down) grid on the chart: its outer surface the envelope less the piece's layer inset
            (bangs outermost, then the side locks, the upper back, the lower back), its inner surface `thick` below it
            (tapering to tip_thick at the tip) but never within `gap` of the skin; side, top and tip walls close it
The buns are closed radius fields round their own centres (the hull's bun pieces); the ahoge and the flyaways are
tapered blades along their centrelines (the ahoge's from its hull points, the flyaways' from the front view's masks).

Everything is in world metres on our assembled character (charkit.geom.parts.Case: the hull aligned by its eyes).

    R = build(case, layers, fam)             # fam: the hull's per-vertex family (label_hull)
    save(R, path)                            # -> .npz for the Blender stage (charkit.scene.hair_pieces_mesh)
"""
import json, os

import numpy as np

FAMILIES = ('bangs', 'side_locks', 'upper_back', 'lower_back', 'buns', 'ahoge', 'flyaways')   # charkit.hairlayers'
MASS = ('bangs', 'side_locks', 'upper_back', 'lower_back')
LAYER = {'bangs': 0.0, 'side_lock_L': 1.0, 'side_lock_R': 1.0, 'upper_back': 1.5, 'lower_back': 2.5}
BUN_CORE = 1.6          # a bun's points further than this many times their median distance from its median are dropped
OPTS = dict(crown_rows=24.0, crown_tilt=-10.0, dphi=4.0, dth=3.0, th_max=168.0, gap=0.006, up=24.0, side=1, step=1.5, crown_cap=8.0,
            chain=6)


def fam_id(name):
    return FAMILIES.index(name) + 1


# ------------------------------------------------------------------------------------------------ the hull's families
def label_hull(Vh, Fh, cls, pieces, piece_names, views, masks, ppl):
    """each hull vertex's family (0 none): the family mask (hairlayers' VIEW__FAMILY, design grids) at its pixel in the view
    that faces it most squarely among those that see it (front, profile and its mirror for her right side, back); the
    hull's bun pieces are buns; hair vertices no view labels take their nearest labelled neighbour's. Vh, Fh: the hull
    in its own frame (L, z up from the eye line: the views' frame). -> (fam (n,) int16, per-view counts)."""
    from scipy.spatial import cKDTree
    from charkit.bodyqa import WIN as W
    from . import raster
    fn = np.cross(Vh[Fh[:, 1]] - Vh[Fh[:, 0]], Vh[Fh[:, 2]] - Vh[Fh[:, 0]])
    N = np.zeros_like(Vh)
    for i in range(3):
        np.add.at(N, Fh[:, i], fn)
    N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-12
    best = np.full(len(Vh), -np.inf)
    fam = np.zeros(len(Vh), np.int16)
    counts = {}
    for name, az, mirror in (('front', 0.0, False), ('profile', 90.0, False), ('profile', 270.0, True),
                             ('back', 180.0, False)):
        v = views[name]
        ox = (v.grid_eye[0] - v.axis) / ppl
        org = (-ox if mirror else ox, (v.eye_y - v.grid_eye[1]) / ppl)
        depth, _ = raster.window_zbuffer([(Vh, Fh, np.zeros(len(Fh), int))], az, org, 1.0, 1.0 / ppl, W)
        a = np.radians(az)
        u = Vh[:, 0] * np.cos(a) + Vh[:, 1] * np.sin(a)
        z = Vh[:, 2]
        d = -Vh[:, 0] * np.sin(a) + Vh[:, 1] * np.cos(a)                  # (faceqa.view's: smaller is nearer)
        col = np.floor((u - org[0] + W['x']) * ppl).astype(int)
        row = np.floor((W['top'] - (z - org[1])) * ppl).astype(int)
        H, Wd = depth.shape
        ok = (col >= 0) & (col < Wd) & (row >= 0) & (row < H)
        vis = np.zeros(len(Vh), bool)
        vis[ok] = d[ok] <= depth[row[ok], col[ok]] + 0.01
        score = N @ np.array([np.sin(a), -np.cos(a), 0.0])
        img = np.zeros((H, Wd), np.int16)
        for k, f in enumerate(FAMILIES):
            m = masks.get('%s__%s' % (name, f))
            if m is not None and m.shape == img.shape:
                img[m] = k + 1
        if mirror:
            img = img[:, ::-1]
        got = np.zeros(len(Vh), np.int16)
        got[ok] = img[row[ok], col[ok]]
        take = vis & (score > best) & (got > 0)
        fam[take] = got[take]
        best[take] = score[take]
        counts['%s%s' % (name, ' (mirror)' if mirror else '')] = int(take.sum())
    bun_ids = [int(k) for k, n in piece_names.items() if n in ('bun_L', 'bun_R')]
    hair = (cls == 2) | np.isin(pieces, bun_ids)
    fam[np.isin(pieces, bun_ids)] = fam_id('buns')
    fam[(fam == fam_id('buns')) & ~np.isin(pieces, bun_ids)] = 0     # (buns only where the outfit's bun pieces are)
    lab = hair & (fam > 0)
    miss = hair & (fam == 0)
    if miss.any() and lab.any():
        fam[miss] = fam[lab][cKDTree(Vh[lab]).query(Vh[miss])[1]]
    fam[~hair] = 0
    counts['filled'] = int(miss.sum())
    return fam, counts


# ------------------------------------------------------------------------------------------------------ the chart
class Chart:
    """the crown chart round centre c (see the module): theta from the crown direction k, phi round it from the front."""

    def __init__(self, c, tilt_deg):
        self.c = np.asarray(c, float)
        t = np.radians(tilt_deg)
        self.k = np.array([0.0, np.sin(t), np.cos(t)])                  # up, tilted toward the back (+y)
        f = np.array([0.0, -1.0, 0.0]) - self.k * (-self.k[1])
        self.f = f / np.linalg.norm(f)
        self.l = np.cross(self.k, self.f)                                # her left (+x)

    def coords(self, P):
        q = np.asarray(P, float) - self.c
        r = np.linalg.norm(q, axis=-1)
        d = q / np.maximum(r, 1e-12)[..., None]
        th = np.degrees(np.arccos(np.clip(d @ self.k, -1, 1)))
        ph = np.degrees(np.arctan2(d @ self.l, d @ self.f))
        return ph, th, r

    def dirs(self, ph, th):
        p, t = np.radians(ph), np.radians(th)
        st = np.sin(t)[..., None]
        return np.cos(t)[..., None] * self.k + st * (np.cos(p)[..., None] * self.f + np.sin(p)[..., None] * self.l)

    def point(self, ph, th, r):
        return self.c + np.asarray(r, float)[..., None] * self.dirs(ph, th)


class Grid:
    """the chart's cells: phi in nph columns of dphi from -180, theta in nth rows of dth from the crown."""

    def __init__(self, dphi, dth, th_max):
        self.dphi, self.dth = dphi, dth
        self.nph, self.nth = int(round(360 / dphi)), int(round(th_max / dth))
        self.ph = -180 + dphi * (np.arange(self.nph) + 0.5)
        self.th = dth * (np.arange(self.nth) + 0.5)

    def cell(self, ph, th):
        i = np.floor((np.asarray(ph) + 180) / self.dphi).astype(int) % self.nph
        j = np.floor(np.asarray(th) / self.dth).astype(int)
        return i, j, (j >= 0) & (j < self.nth)

    def sample(self, A, ph, th):
        """a grid array at chart points, bilinear (periodic in phi, clamped in theta)."""
        x = (np.asarray(ph, float) + 180) / self.dphi - 0.5
        y = np.clip(np.asarray(th, float) / self.dth - 0.5, 0, self.nth - 1)
        i0 = np.floor(x).astype(int); fx = x - i0
        j0 = np.floor(y).astype(int); fy = y - j0
        i0 %= self.nph; i1 = (i0 + 1) % self.nph
        j1 = np.minimum(j0 + 1, self.nth - 1)
        return ((1 - fx) * ((1 - fy) * A[i0, j0] + fy * A[i0, j1]) + fx * ((1 - fy) * A[i1, j0] + fy * A[i1, j1]))


def _max_field(G, i, j, ok, r):
    A = np.full((G.nph, G.nth), -np.inf)
    np.maximum.at(A, (i[ok], j[ok]), r[ok])
    return A


def _fill(A, valid):
    """cells not valid filled along theta in their column (from the crown down to the column's last valid cell), then
    columns without any from their neighbours round phi. -> (filled, reach: the last valid row per column, -1 none)."""
    G = A.copy()
    nph, nth = A.shape
    reach = np.full(nph, -1)
    for i in range(nph):
        js = np.nonzero(valid[i])[0]
        if len(js) == 0:
            continue
        reach[i] = js.max()
        G[i] = np.interp(np.arange(nth), js, A[i, js])
    have = reach >= 0
    if not have.any():
        raise ValueError('no hair on the crown chart')
    idx = np.arange(nph)
    for j in range(nth):
        G[~have, j] = np.interp(idx[~have], idx[have], G[have, j], period=nph)
    return G, reach


def _smooth(A, s_ph, s_th):
    from scipy.ndimage import gaussian_filter
    return gaussian_filter(A, (s_ph, s_th), mode=('wrap', 'nearest'))


def _mode_filter(L, nlab, size=3):
    """the majority label in each size x size neighbourhood (periodic in phi), empty cells voting for nothing."""
    from scipy.ndimage import uniform_filter
    votes = np.stack([uniform_filter((L == k).astype(float), size, mode=('wrap', 'nearest')) for k in range(1, nlab + 1)])
    return np.where(L > 0, votes.argmax(0) + 1, 0)


# ---------------------------------------------------------------------------------------------------------- the mass
def mass_fields(case, hullV_world, fam, opts):
    """the crown chart's envelope, skin and family fields. -> dict(chart, grid, R (smoothed envelope), Rn (the normals'
    smoother envelope), S (skin, -inf where none), L (family per cell), reach (per column the envelope's last row))."""
    Hd = case.A['head']
    L = case.L
    c = case.centre + np.array([0.0, (Hd['H'].db - Hd['H'].df) / 2, 0.06 * L])      # charkit.hair.Volume's centre
    ch = Chart(c, opts['crown_tilt'])
    G = Grid(opts['dphi'], opts['dth'], opts['th_max'])
    mass = np.isin(fam, [fam_id(f) for f in MASS])
    ph, th, r = ch.coords(hullV_world[mass])
    i, j, ok = G.cell(ph, th)
    Rmax = _max_field(G, i, j, ok, r)
    valid = np.isfinite(Rmax)
    Rf, reach = _fill(np.where(valid, Rmax, 0.0), valid)
    # hanging hair: below each column's reach the envelope continues flat (the pieces stop at their own tips)
    R = _smooth(Rf, 1.0, 1.0)
    Rn = _smooth(Rf, 2.5, 2.5)
    # families per cell: the majority of the labelled hair in it (the side locks split by side)
    fcell = np.zeros((G.nph, G.nth, len(FAMILIES) + 1))
    np.add.at(fcell, (i[ok], j[ok], fam[mass][ok]), 1)
    Lc = np.where(fcell.sum(2) > 0, fcell.argmax(2), 0)
    Lc = _mode_filter(Lc, len(FAMILIES))
    # the skin inside the envelope: our body's outermost radius per cell among vertices inside it
    B = np.asarray(case.A['verts'], float)
    bph, bth, br = ch.coords(B)
    bi, bj, bok = G.cell(bph, bth)
    bok &= br < G.sample(R, bph, bth) + 0.02 * L
    S = _max_field(G, bi, bj, bok, br)
    S = np.maximum(S, -np.inf)
    return dict(chart=ch, grid=G, R=R, Rn=Rn, S=S, L=Lc, reach=reach, valid=valid)


def fill_families(Lc, reach):
    """the family of every cell of the hair (a column's cells down to its reach) that no hull point labels (under the
    buns, behind the ears): its nearest labelled cell's (periodic in phi)."""
    from scipy import ndimage
    nph, nth = Lc.shape
    inside = np.arange(nth)[None, :] <= reach[:, None]
    P = np.concatenate([Lc, Lc, Lc])                                   # (phi wraps: three copies, the middle one kept)
    idx = ndimage.distance_transform_edt(P == 0, return_distances=False, return_indices=True)
    full = P[idx[0], idx[1]][nph:2 * nph]
    return np.where(inside, np.where(Lc > 0, Lc, full), 0)


def _largest(m):
    """the largest 8-connected component of a (phi, theta) mask, phi periodic."""
    from scipy import ndimage
    nph = m.shape[0]
    P = np.concatenate([m, m])
    lab, n = ndimage.label(P, np.ones((3, 3)))
    if n == 0:
        return m & False
    # components seen in the doubled grid: fold them back, the largest by its cells in one period
    out, best = np.zeros_like(m), 0
    for k in range(1, n + 1):
        cells = np.nonzero(lab == k)
        ii = cells[0] % nph
        mk = np.zeros_like(m); mk[ii, cells[1]] = True
        if mk.sum() > best:
            best, out = mk.sum(), mk
    return out


def piece_regions(F, opts):
    """the mass's pieces on the chart: per piece (a family's largest connected region, the side locks one per side) its
    columns in order round phi (contiguous: the columns between two it has take their interpolated top and tip) and per
    column the theta of its top (the crown, or `up` above its first cell) and of its tip (its last cell's far edge)."""
    G = F['grid']
    Lc = fill_families(F['L'], F['reach'])
    # the crown's rows: every column converges there and the buns hide it, so a column's crown takes the family it has
    # just below (the part line follows the measured partition, not the few labels at the pole)
    cr = int(round(opts['crown_rows'] / G.dth))
    for i in range(G.nph):
        below = Lc[i, cr:cr + 5]
        below = below[below > 0]
        if len(below):
            Lc[i, :cr] = np.bincount(below).argmax()
    F['Lfill'] = Lc
    out = {}
    specs = [('bangs', 'bangs', None), ('side_lock_L', 'side_locks', 1), ('side_lock_R', 'side_locks', -1),
             ('upper_back', 'upper_back', None), ('lower_back', 'lower_back', None)]
    for piece, fam, sgn in specs:
        m = Lc == fam_id(fam)
        if sgn is not None:
            m &= (np.sign(G.ph) == sgn)[:, None]
        m = _largest(m)
        cols = np.nonzero(m.any(1))[0]
        if len(cols) < 2:
            continue
        c_sorted = np.sort(cols)
        gaps = np.diff(np.r_[c_sorted, c_sorted[0] + G.nph])
        start = c_sorted[(np.argmax(gaps) + 1) % len(c_sorted)]
        span = (c_sorted[np.argmax(gaps)] - start) % G.nph + 1
        run = [(start + k) % G.nph for k in range(-opts['side'], span + opts['side'])]
        crown = m[:, :2].any()
        have = np.array([m[c].any() for c in run])
        lo = np.array([np.nonzero(m[c])[0][0] if m[c].any() else -1 for c in run], float)
        hi = np.array([np.nonzero(m[c])[0][-1] if m[c].any() else -1 for c in run], float)
        x = np.arange(len(run))
        lo = np.interp(x, x[have], lo[have]); hi = np.interp(x, x[have], hi[have])
        top = np.zeros(len(run)) if crown else np.maximum(0.0, lo * G.dth - opts['up'])
        tip = (hi + 1) * G.dth
        out[piece] = dict(family=fam, cols=np.array(run), ph=G.ph[run], top=top, tip=tip, cells=int(m.sum()))
    return out


def locks(ph, tip, lock_min, notch):
    """a piece's locks from its lower edge: notches at the edge's local minima of reach at least lock_min apart; each lock
    (ph0, ph1, its tip's phi); the edge with every notch deepened by `notch` degrees tapering to 0 at the tips.
    ph must increase (a piece's columns unwrapped). -> (locks [(ph0, ph1, ph_tip)], the deepened edge on ph)."""
    from scipy.ndimage import median_filter
    e = median_filter(tip, 3, mode='nearest')
    n = len(e)
    cand = [k for k in range(1, n - 1) if e[k] <= e[k - 1] and e[k] <= e[k + 1] and (e[k] < e[k - 1] or e[k] < e[k + 1])]
    cuts = []
    for k in sorted(cand, key=lambda k: e[k]):                     # the deepest notches first
        if ph[k] - ph[0] >= lock_min and ph[-1] - ph[k] >= lock_min and all(abs(ph[k] - ph[q]) >= lock_min for q in cuts):
            cuts.append(k)
    cuts = sorted(cuts)
    bounds = [0] + cuts + [n - 1]
    L_ = []
    edge = e.astype(float).copy()
    for a, b in zip(bounds[:-1], bounds[1:]):
        seg = np.arange(a, b + 1)
        t = seg[np.argmax(e[seg])]
        L_.append((float(ph[a]), float(ph[b]), float(ph[t])))
        for q in seg:                                              # deepen toward the notches, 0 at the tip
            if q < t:
                w = (ph[t] - ph[q]) / max(1e-9, ph[t] - ph[a]) if a in cuts else 0.0
            else:
                w = (ph[q] - ph[t]) / max(1e-9, ph[b] - ph[t]) if b in cuts else 0.0
            edge[q] = min(edge[q], e[q] - notch * w ** 1.5)
    return L_, edge


def _unwrap(ph):
    out = np.array(ph, float)
    for k in range(1, len(out)):
        while out[k] < out[k - 1]:
            out[k] += 360.0
    return out


def lock_shell(F, piece, ph0, ph1, ph_tip, ph_cols, top_cols, edge_cols, style, opts, L):
    """one lock's closed shell (see the module). -> dict(V, T (triangles), outer (bool per vertex), strand (unit, per
    vertex), chain (joints, root to tip), vn_env (the envelope's normal per vertex), push (L: how far the outer surface had
    to move out to clear the skin, max))."""
    ch, G = F['chart'], F['grid']
    step = opts['step']
    nu = max(3, int(np.ceil((ph1 - ph0) / step)))
    phs = np.linspace(ph0, ph1, nu + 1)
    top = np.interp(phs, ph_cols, top_cols)
    tip = np.interp(phs, ph_cols, edge_cols)
    top = np.maximum(top, opts['crown_cap'] * 0.75)                # (the crown's cap covers the pole)
    nv = max(4, int(np.ceil((tip.max() - top.min()) / step)))
    v = np.linspace(0, 1, nv + 1)
    PH = np.repeat(phs[:, None], nv + 1, 1)
    TH = top[:, None] + v[None] * (tip - top)[:, None]
    phw = ((PH + 180) % 360) - 180
    inset = LAYER.get(piece, 1.0) * style['inset'] * L
    R = G.sample(F['R'], phw, TH) - inset
    S = G.sample(np.where(np.isfinite(F['S']), F['S'], -1e3), phw, TH)
    gap = opts['gap'] * L
    thick = style['thick'] * L * (1 - v[None]) ** 0.6 + style['tip_thick'] * L
    need = S + gap + style['tip_thick'] * L
    push = np.maximum(need - R, 0.0)
    Ro = R + push
    Ri = np.maximum(Ro - thick, np.minimum(S + gap, Ro - style['tip_thick'] * L))
    Po = ch.point(phw, TH, Ro)
    Pi = ch.point(phw, TH, Ri)
    n0 = Po.reshape(-1, 3)
    n1 = Pi.reshape(-1, 3)
    V = np.concatenate([n0, n1])
    idx = lambda a, b, inner=False: (a * (nv + 1) + b) + (len(n0) if inner else 0)
    T = []
    for a in range(nu):
        for b in range(nv):
            q = (idx(a, b), idx(a + 1, b), idx(a + 1, b + 1), idx(a, b + 1))
            T += [(q[0], q[2], q[1]), (q[0], q[3], q[2])]              # outer: faces outward (checked below)
            qi = tuple(x + len(n0) for x in q)
            T += [(qi[0], qi[1], qi[2]), (qi[0], qi[2], qi[3])]
    def wall(pairs):
        for (a0, b0), (a1, b1) in pairs:
            o0, o1, i0, i1 = idx(a0, b0), idx(a1, b1), idx(a0, b0, True), idx(a1, b1, True)
            T.extend([(o0, o1, i1), (o0, i1, i0)])
    wall([((a, 0), (a + 1, 0)) for a in range(nu)])                    # the top edge
    wall([((a + 1, nv), (a, nv)) for a in range(nu)])                  # the tip edge
    wall([((0, b + 1), (0, b)) for b in range(nv)])                    # the sides
    wall([((nu, b), (nu, b + 1)) for b in range(nv)])
    T = np.array(T, np.int64)
    # orientation: the outer surface's normals away from the chart's centre
    tri = V[T[:len(T) // 1]]
    fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    outer_f = np.all(T < len(n0), axis=1)
    cen = tri.mean(1) - ch.c
    if (np.einsum('ij,ij->i', fn[outer_f], cen[outer_f]) < 0).mean() > 0.5:
        T = T[:, [0, 2, 1]]
    # strand direction: down the lock (d/dv), the envelope's normal (the smoother field) for custom normals
    dP = np.gradient(Po, axis=1)
    strand = dP / (np.linalg.norm(dP, axis=2, keepdims=True) + 1e-12)
    Rn = G.sample(F['Rn'], phw, TH) - inset + push
    Pn = ch.point(phw, TH, Rn)
    du = np.gradient(Pn, axis=0); dv = np.gradient(Pn, axis=1)
    nrm = np.cross(du, dv)
    nrm /= np.linalg.norm(nrm, axis=2, keepdims=True) + 1e-12
    if np.einsum('ijk,ijk->ij', nrm, Pn - ch.c).mean() < 0:
        nrm = -nrm
    vn = np.concatenate([nrm.reshape(-1, 3), -nrm.reshape(-1, 3)])
    # the chain: the lock's middle (at its tip's phi) halfway through its depth, root to tip
    ut = np.clip((ph_tip - ph0) / max(1e-9, ph1 - ph0), 0, 1)
    vs = np.linspace(0, 1, opts['chain'])
    pht = ((ph0 + ut * (ph1 - ph0) + 180) % 360) - 180
    ttop, ttip = np.interp(ph_tip, phs, top), np.interp(ph_tip, phs, tip)
    thc = ttop + vs * (ttip - ttop)
    rc = G.sample(F['R'], np.full_like(vs, pht), thc) - inset
    chain = ch.point(np.full_like(vs, pht), thc, rc - 0.5 * (style['thick'] * L * (1 - vs) ** 0.6))
    return dict(V=V, T=T, outer=np.r_[np.ones(len(n0), bool), np.zeros(len(n1), bool)],
                strand=np.concatenate([strand.reshape(-1, 3)] * 2), vn_env=vn, chain=chain, push=float(push.max() / L))


def crown_cap(F, style, opts, L):
    """the disc over the chart's pole (theta below crown_cap), part of the upper back: a fan round the pole's vertex."""
    ch, G = F['chart'], F['grid']
    n = 36
    ring = np.linspace(-180, 180, n, endpoint=False)
    th = opts['crown_cap']
    inset = LAYER['upper_back'] * style['inset'] * L
    def surf(offset):
        pole = ch.point(np.array([0.0]), np.array([0.0]), np.array([G.sample(F['R'], 0.0, 0.0) - inset - offset]))[0]
        rr = G.sample(F['R'], ring, np.full(n, th)) - inset - offset
        return pole, ch.point(ring, np.full(n, th), rr)
    po, ro = surf(0.0)
    pi, ri = surf(style['thick'] * L * 0.5)
    V = np.concatenate([[po], ro, [pi], ri])
    T = []
    for k in range(n):
        a, b = 1 + k, 1 + (k + 1) % n
        T.append((0, a, b))
        T.append((n + 1, n + 1 + b, n + 1 + a))
        T.extend([(a, n + 1 + a, n + 1 + b), (a, n + 1 + b, b)])
    T = np.array(T, np.int64)
    tri = V[T]; fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    if np.einsum('ij,ij->i', fn[:n * 1:4], (tri.mean(1) - ch.c)[:n * 1:4]).mean() < 0:
        T = T[:, [0, 2, 1]]
    d = V - ch.c
    vn = d / np.linalg.norm(d, axis=1, keepdims=True)
    strand = np.zeros_like(V); strand[:, 2] = -1
    return dict(V=V, T=T, outer=np.r_[np.ones(n + 1, bool), np.zeros(n + 1, bool)], strand=strand, vn_env=vn,
                chain=np.array([po]), push=0.0)


# --------------------------------------------------------------------------------------------- buns, ahoge, flyaways
def icosphere(sub=3):
    t = (1 + 5 ** 0.5) / 2
    V = np.array([[-1, t, 0], [1, t, 0], [-1, -t, 0], [1, -t, 0], [0, -1, t], [0, 1, t], [0, -1, -t], [0, 1, -t],
                  [t, 0, -1], [t, 0, 1], [-t, 0, -1], [-t, 0, 1]], float)
    F = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6),
         (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7),
         (9, 8, 1)]
    V = [v / np.linalg.norm(v) for v in V]
    for _ in range(sub):
        mid, F2 = {}, []
        def m(a, b):
            k = (min(a, b), max(a, b))
            if k not in mid:
                p = V[a] + V[b]; V.append(p / np.linalg.norm(p)); mid[k] = len(V) - 1
            return mid[k]
        for a, b, c in F:
            ab, bc, ca = m(a, b), m(b, c), m(c, a)
            F2 += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        F = F2
    return np.array(V), np.array(F, np.int64)


def _laplace(vals, F, known, iters=60, smooth=6):
    """values on a mesh's vertices: unknown ones filled by Jacobi iterations of their neighbours' mean, then all smoothed."""
    n = len(vals)
    E = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    E = np.concatenate([E, E[:, ::-1]])
    deg = np.bincount(E[:, 0], minlength=n)
    x = np.where(known, vals, np.nanmean(vals[known]) if known.any() else 0.0)
    for _ in range(iters):
        s = np.bincount(E[:, 0], weights=x[E[:, 1]], minlength=n) / np.maximum(deg, 1)
        x = np.where(known, x, s)
    for _ in range(smooth):
        s = np.bincount(E[:, 0], weights=x[E[:, 1]], minlength=n) / np.maximum(deg, 1)
        x = 0.5 * x + 0.5 * s
    return x


def bun(P, cone_deg=10.0, sub=3):
    """a closed smooth shell through a bun's points: an icosphere round their centre, each direction's radius the
    outermost point within cone_deg of it, unseen directions filled and all smoothed. -> dict(V, T, vn_env, strand, chain)."""
    c = P.mean(0)
    D, T = icosphere(sub)
    q = P - c
    r = np.linalg.norm(q, axis=1)
    u = q / r[:, None]
    cosc = np.cos(np.radians(cone_deg))
    dots = D @ u.T
    near = dots > cosc
    known = near.any(1)
    vals = np.where(known, np.where(near, r[None], -np.inf).max(1), np.nan)
    rad = _laplace(vals, T, known)
    V = c + D * rad[:, None]
    strand = np.zeros_like(V); strand[:, 2] = -1
    return dict(V=V, T=T, vn_env=D.copy(), strand=strand, chain=np.array([c]), outer=np.ones(len(V), bool), push=0.0)


def _order_by_path(P, root, k=8):
    """points ordered by their shortest-path distance from `root` over a k-nearest-neighbour graph."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import dijkstra
    from scipy.spatial import cKDTree
    d, j = cKDTree(P).query(P, min(k + 1, len(P)))
    rows = np.repeat(np.arange(len(P)), j.shape[1])
    Gm = coo_matrix((d.ravel(), (rows, j.ravel())), shape=(len(P), len(P))).tocsr()
    return dijkstra(Gm, directed=False, indices=root)


def blade(line, width, depth_ratio=0.45, n_ring=8):
    """a tapered tube along a centreline (root to tip): elliptic sections `width` wide (per joint, tapering to a point) and
    depth_ratio as deep, the broad side across the line's plane of curvature. -> dict(V, T, strand, vn_env, chain)."""
    P = np.asarray(line, float)
    n = len(P)
    t = np.gradient(P, axis=0)
    t /= np.linalg.norm(t, axis=1, keepdims=True) + 1e-12
    ref = np.cross(P[-1] - P[0], P[n // 2] - P[0])
    if np.linalg.norm(ref) < 1e-9:
        ref = np.array([0.0, -1.0, 0.0])
    ref /= np.linalg.norm(ref)
    V, strand = [], []
    for k in range(n):
        a = ref - t[k] * (ref @ t[k]); a /= np.linalg.norm(a) + 1e-12        # the depth axis (out of the curl's plane)
        b = np.cross(t[k], a)                                                   # the broad axis
        w = width[k] / 2
        for s in range(n_ring):
            ang = 2 * np.pi * s / n_ring
            V.append(P[k] + b * w * np.cos(ang) + a * w * depth_ratio * np.sin(ang))
            strand.append(t[k])
    V.append(P[-1] + t[-1] * 1e-4); strand.append(t[-1])                         # the tip
    V.append(P[0] - t[0] * 1e-4); strand.append(t[0])                            # the root's cap
    V = np.array(V); tip, rootc = len(V) - 2, len(V) - 1
    T = []
    for k in range(n - 1):
        for s in range(n_ring):
            a0, a1 = k * n_ring + s, k * n_ring + (s + 1) % n_ring
            b0, b1 = a0 + n_ring, a1 + n_ring
            T += [(a0, a1, b1), (a0, b1, b0)]
    for s in range(n_ring):
        T.append(((n - 1) * n_ring + s, (n - 1) * n_ring + (s + 1) % n_ring, tip))
        T.append((rootc, (s + 1) % n_ring, s))
    T = np.array(T, np.int64)
    # outward: the rings' faces away from the centreline
    tri = V[T[:(n - 1) * n_ring * 2]]
    fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    cen = np.repeat(P[:-1], n_ring * 2, 0)
    if (np.einsum('ij,ij->i', fn, tri.mean(1) - cen) < 0).mean() > 0.5:
        T = T[:, [0, 2, 1]]
    vn = V - np.r_[np.repeat(P, n_ring, 0), [P[-1], P[0]]]
    vn /= np.linalg.norm(vn, axis=1, keepdims=True) + 1e-12
    return dict(V=V, T=T, strand=np.array(strand), vn_env=vn, chain=P[np.linspace(0, n - 1, min(n, 6)).astype(int)],
                outer=np.ones(len(V), bool), push=0.0)


def ahoge(P, anchor, n=10):
    """the ahoge's blade through its points: its root the point nearest `anchor` (the crown's surface), ordered by path
    from there, n joints (the bins' centroids), each as wide as its bin's spread, tapering to the tip."""
    root = int(np.argmin(np.linalg.norm(P - anchor, axis=1)))
    dist = _order_by_path(P, root)
    ok = np.isfinite(dist)
    P, dist = P[ok], dist[ok]
    edges = np.linspace(0, dist.max() + 1e-9, n + 1)
    line, width = [], []
    for a, b in zip(edges[:-1], edges[1:]):
        m = (dist >= a) & (dist < b)
        if m.sum() < 2:
            continue
        c = P[m].mean(0)
        line.append(c)
        width.append(2 * np.percentile(np.linalg.norm(P[m] - c, axis=1), 80))
    line = np.array(line)
    width = np.array(width) * np.linspace(1.0, 0.15, len(width))
    line = np.r_[[anchor], line]
    width = np.r_[width[:1], width]
    return blade(line, width)


def flyaways(mask, to_world, anchor_fn, min_px=40, n=7, depth_ratio=0.4):
    """the flyaways of the front view's family mask (a design grid): each connected piece a blade whose centreline runs by
    path from its pixel nearest the mass (anchor_fn: pixel -> distance to the mass) to its far end; to_world: (cols,
    rows) -> world points (at the envelope's side). -> [blade dicts]."""
    from scipy import ndimage
    lab, k = ndimage.label(mask)
    out = []
    for i in range(1, k + 1):
        rr, cc = np.nonzero(lab == i)
        if len(rr) < min_px:
            continue
        pts = np.c_[cc, rr].astype(float)
        root = int(np.argmin(anchor_fn(cc, rr)))
        dist = _order_by_path(pts, root, k=6)
        ok = np.isfinite(dist)
        pts, dist = pts[ok], dist[ok]
        edges = np.linspace(0, dist.max() + 1e-9, n + 1)
        line, width = [], []
        for a, b in zip(edges[:-1], edges[1:]):
            m = (dist >= a) & (dist < b)
            if m.sum() < 2:
                continue
            c = pts[m].mean(0)
            line.append(c)
            width.append(2 * np.percentile(np.linalg.norm(pts[m] - c, axis=1), 85))
        if len(line) < 3:
            continue
        line = np.array(line)
        W3 = to_world(line[:, 0], line[:, 1])
        px = np.linalg.norm(to_world(np.array([0.0, 1.0]), np.array([0.0, 0.0]))[1] - to_world(np.array([0.0]),
                                                                                                 np.array([0.0]))[0])
        wd = np.array(width) * px * np.linspace(1.0, 0.2, len(width))
        out.append(blade(W3, wd, depth_ratio))
    return out


# ------------------------------------------------------------------------------------------------------------ build
def build(case, fam, masks, style, views=None, hull_frame=None, opts=None, log=print):
    """every piece. case: charkit.geom.parts.Case (the hull aligned: case.gen, our character: case.A); fam: the hull's
    per-vertex family (label_hull); masks: hairlayers' VIEW__FAMILY; style: the profile's hair_pieces; hull_frame:
    (scale, translate) from the hull's frame to the world (the case's align) for the flyaways' front view.
    -> dict(pieces {name: dict(family, V, T, vn_env, strand, lock (per vertex), chains [joints], push)}, fields, report)."""
    o = dict(OPTS, **(opts or {}))
    L = case.L
    V = np.asarray(case.gen.V, float)
    F = mass_fields(case, V, fam, o)
    regions = piece_regions(F, o)
    pieces, report = {}, {'pieces': {}}

    def add(name, family, parts):
        Vs, Ts, vn, st, lk, chains, off, pushes = [], [], [], [], [], [], 0, []
        for k, p in enumerate(parts):
            Vs.append(p['V']); Ts.append(p['T'] + off); vn.append(p['vn_env']); st.append(p['strand'])
            lk.append(np.full(len(p['V']), k)); chains.append(np.asarray(p['chain']).tolist())
            pushes.append(p.get('push', 0.0)); off += len(p['V'])
        pieces[name] = dict(family=family, V=np.concatenate(Vs), T=np.concatenate(Ts), vn_env=np.concatenate(vn),
                            strand=np.concatenate(st), lock=np.concatenate(lk), chains=chains)
        report['pieces'][name] = dict(family=family, locks=len(parts), verts=int(off),
                                      tris=int(sum(len(t) for t in Ts)), push_L=round(float(max(pushes)), 4))
    for piece, R in regions.items():
        ph = _unwrap(R['ph'])
        L_, edge = locks(ph, R['tip'], style['lock_min'], style['notch'])
        parts = [lock_shell(F, piece, a, b, t, ph, R['top'], edge, style, o, L) for a, b, t in L_]
        if piece == 'upper_back':
            parts.append(crown_cap(F, style, o, L))
        add(piece, R['family'], parts)
        report['pieces'][piece]['tips_deg'] = [round(t, 1) for _, _, t in L_]
    # the buns: the hull's bun points, one shell each side
    bp = V[fam == fam_id('buns')]
    if len(bp):
        for side, sgn in (('bun_L', 1), ('bun_R', -1)):
            P = bp[np.sign(bp[:, 0] - case.centre[0]) == sgn]
            if len(P) > 30:
                # the bun's core: its labels spill over the top of the head, so the points far from their median go
                c = np.median(P, 0)
                d = np.linalg.norm(P - c, axis=1)
                P = P[d < BUN_CORE * np.median(d)]
                add(side, 'buns', [bun(P)])
    # the ahoge: its hull points, a blade from the crown
    ap = V[fam == fam_id('ahoge')]
    if len(ap) > 20:
        ch, G = F['chart'], F['grid']
        aph, ath, _ = ch.coords(ap)
        k = int(np.argmin(ath))
        anchor = ch.point(np.array([aph[k]]), np.array([ath[k]]),
                          np.array([G.sample(F['R'], aph[k], ath[k]) - 0.02 * L]))[0]
        add('ahoge', 'ahoge', [ahoge(ap, anchor)])
    # the flyaways: the front view's mask, lifted onto the envelope's side
    fm = masks.get('front__flyaways')
    if fm is not None and views is not None and hull_frame is not None:
        v = views['front']
        from charkit.bodyqa import WIN
        ppl = v.ppl
        x0 = int(round(v.grid_eye[0] - WIN['x'] * ppl)); y0 = int(round(v.grid_eye[1] - WIN['top'] * ppl))
        s, tr = hull_frame
        mh = V[np.isin(fam, [fam_id(f) for f in MASS])]
        from scipy.spatial import cKDTree
        hx = (mh - tr) / s                                            # the mass in the hull's frame
        tree2 = cKDTree(hx[:, [0, 2]])

        def to_world(cols, rows):
            x = (x0 + np.asarray(cols) - v.axis) / ppl
            z = (v.eye_y - (y0 + np.asarray(rows))) / ppl
            _, j = tree2.query(np.c_[x, z], 24)
            y = np.median(hx[j, 1], axis=1)                         # the mass's mid-plane there (front and back averaged)
            return np.c_[x, y, z] * s + tr

        def anchor_fn(cc, rr):
            x = (x0 + cc - v.axis) / ppl; z = (v.eye_y - (y0 + rr)) / ppl
            return tree2.query(np.c_[x, z])[0]
        bl = flyaways(fm, to_world, anchor_fn)
        if bl:
            add('flyaways', 'flyaways', bl)
    report['fields'] = dict(columns_with_hair=int((F['reach'] >= 0).sum()), cells=int(F['valid'].sum()),
                            crown_tilt=o['crown_tilt'])
    log('hair pieces: %s' % ', '.join('%s %d locks' % (k, r['locks']) for k, r in report['pieces'].items()))
    return dict(pieces=pieces, fields=F, report=report)


def save(R, path, meta=None):
    """the pieces for the Blender stage: one .npz, per piece NAME/V, NAME/F, NAME/vn (the envelope's normals),
    NAME/strand, NAME/lock, and a json meta (families, chains, the report)."""
    arrays = {}
    info = dict(meta or {}, report=R['report'], pieces={})
    for name, p in R['pieces'].items():
        arrays[name + '/V'] = p['V'].astype(np.float32)
        arrays[name + '/F'] = p['T'].astype(np.int32)
        arrays[name + '/vn'] = p['vn_env'].astype(np.float32)
        arrays[name + '/strand'] = p['strand'].astype(np.float32)
        arrays[name + '/lock'] = p['lock'].astype(np.int16)
        info['pieces'][name] = dict(family=p['family'], chains=p['chains'])
    arrays['meta'] = np.frombuffer(json.dumps(info).encode(), np.uint8)
    np.savez_compressed(path, **arrays)
    return path


def geometric_normals(V, T):
    fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    N = np.zeros_like(V)
    for i in range(3):
        np.add.at(N, T[:, i], fn)
    return N / (np.linalg.norm(N, axis=1, keepdims=True) + 1e-12)


def save_parts(R, out, meta=None):
    """the pieces as the Blender stage loads parts (charkit.geom.blender.load_part): out/NAME.npz per piece (V, F, vn:
    the envelope's normals for its custom normals, vn_geom, strand, lock; meta: family, chains, report) and
    out/pieces.json (the pieces in order, their families and files). -> pieces.json's path."""
    from .io import save_npz
    from .mesh import Mesh
    os.makedirs(out, exist_ok=True)
    index = dict(meta or {}, pieces=[], report=R['report'])
    for name, p in R['pieces'].items():
        path = os.path.join(out, name + '.npz')
        save_npz(Mesh(p['V'], p['T'], vn=p['vn_env']), path,
                 meta=dict(family=p['family'], chains=p['chains'], report=R['report']['pieces'].get(name)),
                 vn_geom=geometric_normals(p['V'], np.asarray(p['T'])), strand=p['strand'], lock=p['lock'])
        index['pieces'].append(dict(name=name, family=p['family'], file=name + '.npz', locks=len(p['chains'])))
    path = os.path.join(out, 'pieces.json')
    json.dump(index, open(path, 'w'), indent=1)
    return path


def load(path):
    """save()'s file -> (pieces {name: dict(family, V, F, vn, strand, lock, chains)}, meta)."""
    Z = np.load(path)
    info = json.loads(bytes(Z['meta']).decode())
    out = {}
    for name, rec in info['pieces'].items():
        out[name] = dict(rec, V=Z[name + '/V'].astype(float), F=Z[name + '/F'], vn=Z[name + '/vn'].astype(float),
                         strand=Z[name + '/strand'].astype(float), lock=Z[name + '/lock'])
    return out, info
