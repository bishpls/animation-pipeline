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
BUN_BASE = len(FAMILIES) + 1   # hull hair the views draw as bun below the hull's bun pieces: the bun's base on the head,
                               # neither a bun's points nor the mass's envelope (it would swell up into the buns)
FAMILY_PHI = {'bangs': (0, 100), 'upper_back': (50, 180), 'lower_back': (50, 180)}
# |phi| a family may reach (what its name means: a fringe hangs in front, a back layer behind; the side locks are sided).
# The labels at the crown and far round a view's edge are the least sure (no view faces them squarely): these keep a
# stray one from carrying a family round the head
LAYER = {'bangs': 0.0, 'side_lock_L': 1.0, 'side_lock_R': 1.0, 'upper_back': 1.5, 'lower_back': 2.5}
BUN_CORE = 1.6          # a bun's points further than this many times their median distance from its median are dropped
OPTS = dict(shade_smooth=2.5, pole=20.0, crown_rows=24.0, crown_tilt=-10.0, dphi=4.0, dth=3.0, th_max=168.0, gap=0.006, up=24.0, side=1, step=1.5, crown_cap=20.0,
            chain=6, fine_tips=('bangs',), crown_blend=8.0, cap_top=0.006, side_lock_trim=True, trim_cut=False,
            trim_smooth=3.0, trim_margin=0.01, trim_sides='drawn', tuck_flyaways=True, bun_over={'profile': 1.0})
# (hair round 3's defaults: the crown's one cover (crown_cap 20, crown_blend 8, cap_top 0.006 L under the envelope at
# the pole: the pole's slivers gone), side_lock_trim pulling without cutting, from 0.01 L ahead of the drawn edge, smoothed
# over 3 cells, on the side the sheet's profile draws (her left: the mirrored edge on her right moved the three-
# quarter silhouette in), face in profile 0.63 -> 0.69 of the design's; the flyaways tucked; the bun fit weighing our
# bun over the drawing's other hair whole in profile (it stands in front of the head there);
# crown_blend 0 and crown_cap 8 give the old fan)
# (build's opts also: bun 'round' | 'block' (the design's bun template: a round shell or fitted block loops), bun_fit,
# carve_buns; clamp_side_locks (a taste call, off by default: the side locks held behind the drawn profile's front
# edge) with clamp_mode 'envelope' (side_lock_trim: the chart's side-lock cells cut before the locks are shaped;
# clamp_share 1 at the drawn edge, 0.5 half way) or 'shear' (the old clamp_to_view on built locks: it folds them),
# clamp_margin (L), clamp_keep_cheek; fine_tips: the pieces whose lower edge is the drawing's at the locks' own columns
# (the fringe's points over the eyes), not the chart's columns interpolated). Hair round 3: side_lock_trim (the
# side-lock cells ahead of the drawn profile's front edge pulled in along their rays, above the chin; trim_cut true /
# false / L: where even the skin's clearance is ahead, cut, pull to it, or cut beyond that; trim_smooth, trim_spread,
# trim_below_chin); crown_blend (deg) with crown_cap and cap_top (L: the cover's inset at the pole) for the crown's
# one smooth cover, cap_sectors (split by the part lines; off: its sectors shed shards); tuck_flyaways (default on:
# a blade starts under the lock surface where it clears it); bun 'ribbon' (bun_detail's knot and two loops) with
# bun_over (the fit's weight on our bun over the drawing's other hair, a number or per view) and bun_iters)


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
    spill = (fam == fam_id('buns')) & ~np.isin(pieces, bun_ids)
    fam[np.isin(pieces, bun_ids)] = fam_id('buns')
    fam[spill] = BUN_BASE              # (buns only where the outfit's bun pieces are; the drawn bun's base apart)
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


def surface_points(V, faces, spacing):
    """a mesh's surface as points no further apart than about `spacing`: its vertices and, per triangle (polygons fanned),
    a barycentric grid fine enough for its longest edge."""
    tris = []
    for f in faces:
        for k in range(1, len(f) - 1):
            tris.append((f[0], f[k], f[k + 1]))
    T = np.array(tris, np.int64)
    P = [V]
    e = np.maximum.reduce([np.linalg.norm(V[T[:, a]] - V[T[:, b]], axis=1) for a, b in ((0, 1), (1, 2), (2, 0))])
    n = np.clip(np.ceil(e / spacing).astype(int), 1, 32)
    for k in np.unique(n):
        if k < 2:
            continue
        sel = T[n == k]
        ii, jj = np.meshgrid(np.arange(k + 1), np.arange(k + 1))
        m = ii + jj <= k
        b1, b2 = ii[m] / k, jj[m] / k
        b0 = 1 - b1 - b2
        P.append((V[sel[:, 0]][:, None] * b0[None, :, None] + V[sel[:, 1]][:, None] * b1[None, :, None] +
                  V[sel[:, 2]][:, None] * b2[None, :, None]).reshape(-1, 3))
    return np.concatenate(P)


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


def _pole(A, G, deg):
    """a field made round near the chart's pole: each row within `deg` of it blended toward its mean, fully at the pole
    (its columns there are nearly one direction, filled apart)."""
    A = A.copy()
    for j in range(G.nth):
        w = G.th[j] / deg
        if w < 1:
            A[:, j] = w * A[:, j] + (1 - w) * A[:, j].mean()
    return A


def _mode_filter(L, nlab, size=3):
    """the majority label in each size x size neighbourhood (periodic in phi), empty cells voting for nothing."""
    from scipy.ndimage import uniform_filter
    votes = np.stack([uniform_filter((L == k).astype(float), size, mode=('wrap', 'nearest')) for k in range(1, nlab + 1)])
    return np.where(L > 0, votes.argmax(0) + 1, 0)


# ---------------------------------------------------------------------------------------------------------- the mass
def mass_fields(case, hullV_world, fam, opts):
    """the crown chart's envelope, skin and family fields, over the hair's region (charkit.geom.parts.hair_region: above
    the chin's cut, within the shoulders). A cell whose outermost hull point is not hair (the face, the neck, the collar)
    is not hair: the pieces never cover it, whatever family its neighbours have. -> dict(chart, grid, R (smoothed
    envelope), Rn (the normals' smoother envelope), S (skin, -inf where none), L (family per cell), reach (per column
    the envelope's last row), nothair (cells whose outermost point is something else))."""
    from scipy.ndimage import maximum_filter
    from .parts import hair_region
    Hd = case.A['head']
    L = case.L
    c = case.centre + np.array([0.0, (Hd['H'].db - Hd['H'].df) / 2, 0.06 * L])      # charkit.hair.Volume's centre
    ch = Chart(c, opts['crown_tilt'])
    G = Grid(opts['dphi'], opts['dth'], opts['th_max'])
    inreg = hair_region(case)(hullV_world)
    # every hull point of the region: the outermost one per cell says whether the cell is hair
    aph, ath, ar = ch.coords(hullV_world[inreg])
    ai, aj, aok = G.cell(aph, ath)
    cell = np.where(aok, ai * G.nth + aj, -1)
    o = np.lexsort((ar, cell))
    cell_o = cell[o]
    last = np.r_[cell_o[1:] != cell_o[:-1], True] & (cell_o >= 0)
    top_fam = np.zeros(G.nph * G.nth, np.int16)
    seen = np.zeros(G.nph * G.nth, bool)
    top_fam[cell_o[last]] = fam[inreg][o][last]
    seen[cell_o[last]] = True
    nothair = (seen & (top_fam == 0)).reshape(G.nph, G.nth)
    mass = np.isin(fam, [fam_id(f) for f in MASS]) & inreg
    ph, th, r = ch.coords(hullV_world[mass])
    i, j, ok = G.cell(ph, th)
    Rmax = _max_field(G, i, j, ok, r)
    valid = np.isfinite(Rmax)
    Rf, reach = _fill(np.where(valid, Rmax, 0.0), valid)
    # hanging hair: below each column's reach the envelope continues flat (the pieces stop at their own tips)
    R = _pole(_smooth(Rf, 1.0, 1.0), G, opts['pole'])
    Rn = _pole(_smooth(Rf, opts['shade_smooth'], opts['shade_smooth']), G, opts['pole'])   # the shading's envelope
    # families per cell: the majority of the labelled hair in it (the side locks split by side)
    fcell = np.zeros((G.nph, G.nth, len(FAMILIES) + 1))
    np.add.at(fcell, (i[ok], j[ok], fam[mass][ok]), 1)
    Lc = np.where(fcell.sum(2) > 0, fcell.argmax(2), 0)
    Lc = _mode_filter(Lc, len(FAMILIES))
    Lc[nothair] = 0
    # the skin inside the envelope: our body's outermost radius per cell among vertices inside it, grown by a cell
    # (conservative: the inner surfaces clear the skin's bumps within a cell's reach)
    B = surface_points(np.asarray(case.A['verts'], float), case.A['faces'], 0.008 * L)
    bph, bth, br = ch.coords(B)
    bi, bj, bok = G.cell(bph, bth)
    # (the head whole, above the chin: where it bulges past the hull the pieces are pushed out over it; below, only what
    # lies inside the envelope: not the shoulders the hanging hair falls in front of or behind)
    bok &= (B[:, 2] > case.chin_z) | (br < G.sample(R, bph, bth) + 0.02 * L)
    S = _max_field(G, bi, bj, bok, br)
    S = maximum_filter(np.where(np.isfinite(S), S, -1e3), size=3, mode=('wrap', 'nearest'))
    have = S > -1e2
    Ss = _smooth(np.where(have, S, 0.0), 1.2, 1.2) / np.maximum(_smooth(have.astype(float), 1.2, 1.2), 1e-6)
    S = np.where(have, np.maximum(Ss, S - 0.01 * L), -np.inf)    # smoothed, never more than 0.01 L under its bumps
    return dict(chart=ch, grid=G, R=R, Rn=Rn, S=S, L=Lc, reach=reach, valid=valid, nothair=nothair)


def carve_under_buns(Vw, fam, masks, views, hull_frame, tol=0.01):
    """the visual hull's fill under the buns out of the mass: a mass point the front or back view draws inside a bun
    and beyond the head's outline there (above the eye line: the drawn mass's convex outline, grown by tol L, since the
    buns hide the head's top beneath them) is the hull's union of head and bun (it can't carve the notch between them),
    not hair of the head: it becomes BUN_BASE (the envelope fills over it from its column). -> (fam, points carved)."""
    from scipy.ndimage import binary_dilation, label
    from skimage.morphology import convex_hull_image
    _, tr = hull_frame
    Vw = np.asarray(Vw, float)
    mass = np.isin(fam, [fam_id(f) for f in MASS])
    out = np.zeros(len(Vw), bool)
    for name, az in (('front', 0.0), ('back', 180.0)):
        bm = masks.get('%s__buns' % name)
        if bm is None or name not in views:
            continue
        mm = np.zeros(bm.shape, bool)
        for f in MASS:
            if masks.get('%s__%s' % (name, f)) is not None:
                mm |= masks['%s__%s' % (name, f)]
        _, er = view_px(np.array([[0.0, 0.0, tr[2]]]), views[name], az, False, hull_frame)
        top = np.arange(bm.shape[0])[:, None] < er[0]
        if not (mm & top).any():
            continue
        lab, n = label(mm & top)                          # the largest part (the drawing's specks between the loops out)
        mm = lab == 1 + int(np.argmax(np.bincount(lab.ravel())[1:]))
        head = binary_dilation(convex_hull_image(mm), iterations=max(1, int(tol * views[name].ppl))) | ~top
        cc, rr = view_px(Vw, views[name], az, False, hull_frame)
        c, r = np.floor(cc).astype(int), np.floor(rr).astype(int)
        ok = mass & (c >= 0) & (c < bm.shape[1]) & (r >= 0) & (r < bm.shape[0])
        out[ok] |= bm[r[ok], c[ok]] & ~head[r[ok], c[ok]]
    fam = fam.copy()
    fam[out] = BUN_BASE
    return fam, int(out.sum())


def fill_families(Lc, reach, nothair=None):
    """the family of every cell of the hair (a column's cells down to its reach) that no hull point labels (under the
    buns, behind the ears): its nearest labelled cell's (periodic in phi). Cells in `nothair` stay empty."""
    from scipy import ndimage
    nph, nth = Lc.shape
    inside = np.arange(nth)[None, :] <= reach[:, None]
    P = np.concatenate([Lc, Lc, Lc])                                   # (phi wraps: three copies, the middle one kept)
    idx = ndimage.distance_transform_edt(P == 0, return_distances=False, return_indices=True)
    full = P[idx[0], idx[1]][nph:2 * nph]
    out = np.where(inside, np.where(Lc > 0, Lc, full), 0)
    if nothair is not None:
        out[nothair] = 0
    return out


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


def piece_regions(F, opts, trim=None):
    """the mass's pieces on the chart: per piece (a family's largest connected region, the side locks one per side) its
    columns in order round phi (contiguous: the columns between two it has take their interpolated top and tip) and per
    column the theta of its top (the crown, or `up` above its first cell) and of its tip (its last cell's far edge).
    trim(Lc) -> Lc: the families cut before the regions are found (side_lock_trim: the drawn profile's front edge)."""
    G = F['grid']
    Lc = fill_families(F['L'], F['reach'], F.get('nothair'))
    # the crown's rows: every column converges there and the buns hide it, so a column's crown takes the family it has
    # just below (the part line follows the measured partition, not the few labels at the pole)
    cr = int(round(opts['crown_rows'] / G.dth))
    for i in range(G.nph):
        below = Lc[i, cr:cr + 5]
        below = below[below > 0]
        if len(below):
            Lc[i, :cr] = np.bincount(below).argmax()
    if trim is not None:
        Lc = trim(Lc)
    F['Lfill'] = Lc
    out = {}
    specs = [('bangs', 'bangs', None), ('side_lock_L', 'side_locks', 1), ('side_lock_R', 'side_locks', -1),
             ('upper_back', 'upper_back', None), ('lower_back', 'lower_back', None)]
    for piece, fam, sgn in specs:
        m = Lc == fam_id(fam)
        if sgn is not None:
            m &= (np.sign(G.ph) == sgn)[:, None]
        if fam in FAMILY_PHI:
            lo_, hi_ = FAMILY_PHI[fam]
            m &= ((np.abs(G.ph) >= lo_) & (np.abs(G.ph) <= hi_))[:, None]
        from scipy import ndimage
        core = ndimage.binary_opening(np.concatenate([m, m, m]), np.ones((3, 3)))[G.nph:2 * G.nph]
        m = _largest(core if core.any() else m) | (ndimage.binary_dilation(
            np.concatenate([_largest(core if core.any() else m)] * 3), np.ones((3, 3)))[G.nph:2 * G.nph] & m)
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


def drawn_front(masks, mirror, hair_fams=MASS, look=3):
    """the drawn side lock's front edge per row of the profile (mirrored for her right: the flipped drawing's columns;
    nan where the row draws no side lock). Where other drawn hair lies just ahead of it (within `look` px toward the
    face: the fringe over the temple), the side lock's own front is hidden, so the row's edge is the whole drawn hair's
    front instead: a limit the drawing does show. -> (front (rows,) px, hidden (rows,) bool)."""
    m = masks['profile__side_locks']
    hair = np.zeros_like(m)
    for f in hair_fams:
        q = masks.get('profile__' + f)
        if q is not None:
            hair |= q
    if mirror:
        m, hair = m[:, ::-1], hair[:, ::-1]
    front = np.full(m.shape[0], np.nan)
    hidden = np.zeros(m.shape[0], bool)
    for r in np.nonzero(m.any(1))[0]:
        c = np.nonzero(m[r])[0]
        e = c.max() if mirror else c.min()
        ahead = hair[r, e + 1:e + 1 + look] if mirror else hair[r, max(0, e - look):e]
        if ahead.any():
            h = np.nonzero(hair[r])[0]
            e = h.max() if mirror else h.min()
            hidden[r] = True
        front[r] = e
    return front, hidden


def side_lock_trim(F, Lc, masks, views, hull_frame, margin=0.0, share=1.0, floor=None, pull=True, cut_ahead=True,
                   smooth=0.7, spread=0.0, zmin=None, sides='drawn'):
    """the side locks held to the drawn profile before any lock is shaped (Michael's flag, hair round 3: the visual
    hull fills the gap between a side lock and the cheek, which no view shows, so the locks stood in front of the face
    in profile; moving built locks back crumpled them). Per side, her own profile (the mirror for her right), per
    side-lock cell whose envelope point projects in front of the drawn front edge in its row (drawn_front, less margin
    L):
      pull   the cell's envelope radius drawn in along its own ray until it projects onto the drawn edge (`share` of the
             way: 1 onto it, 0.5 half way), never below `floor` (per cell: where the lock's outer surface would meet the
             skin's clearance). The lock then hangs beside the cheek, as the front view draws it, with its front where
             the profile draws it;
      cut    where even the floor is ahead (the drawing shows the cheek there, no lock can be over it): the cell and every
             cell below it in its column (a lock hangs from its top: the cut is its tip). pull=False cuts every one;
             cut_ahead=False pulls those to the floor instead (the lock hugs the cheek: the front view keeps it); a
             number cuts only where the floor is still ahead by more than that (L), pulling the rest to it.
    F['R'] and F['Rn'] take the pull (smoothed over `smooth` cells, never less than each cell's own); F['trim_cut'] keeps each
    column's cut (theta, deg; inf where none) for drawn_tips; F['trim'] counts. -> Lc."""
    from scipy.ndimage import gaussian_filter
    ch, G = F['chart'], F['grid']
    m = masks.get('profile__side_locks')
    k = fam_id('side_locks')
    cut = np.full(G.nph, np.inf)
    F['trim_cut'] = cut
    if m is None or 'profile' not in views or not (Lc == k).any():
        return Lc
    v = views['profile']
    PH, TH = np.meshgrid(G.ph, G.th, indexing='ij')
    R = F['R']
    Lc = Lc.copy()
    D = np.zeros_like(R)                                         # the pull per cell (world, >= 0)
    ncut = npull = 0
    dirn_of = {False: -1.0, True: 1.0}                           # toward the face (mirrored: +columns; else -columns)

    def over_at(ph, th, r, mirror, az, front):
        cc, rr = view_px(ch.point(ph, th, r), v, az, mirror, hull_frame)
        r_ = np.floor(rr).astype(int)
        ok = (r_ >= 0) & (r_ < len(front))
        fr = np.full(len(np.atleast_1d(cc)), np.nan)
        fr[ok] = front[r_[ok]]
        return (cc - fr) * dirn_of[mirror] - margin * v.ppl      # px beyond the drawn edge, toward the face
    Pz = ch.point(PH, TH, R)[..., 2]
    for sgn, az, mirror in ((1, 90.0, False), (-1, 270.0, True)):
        if mirror and sides == 'drawn':
            # (her right: the sheet draws no profile of it; the mirrored left one moved its front edge in from where the
            # three-quarter view draws it, at the silhouette beside the face: body_three_quarter_iou 0.851 -> 0.849)
            continue
        sel = (Lc == k) & (np.sign(PH) == sgn)
        if zmin is not None:                     # (the face's cells only: below the chin a side lock hangs beside
            sel &= Pz > zmin                     # the neck, in front of the lower back, as the front view draws it)
        if not sel.any():
            continue
        front, _ = drawn_front(masks, mirror)
        ii, jj = np.nonzero(sel)
        over = over_at(PH[ii, jj], TH[ii, jj], R[ii, jj], mirror, az, front)
        ahead = np.isfinite(over) & (over > 0)
        kill = np.zeros(len(ii), bool)
        if pull and ahead.any():
            a = np.nonzero(ahead)[0]
            lo = floor[ii[a], jj[a]] if floor is not None else R[ii[a], jj[a]] * 0.8
            lo = np.minimum(lo, R[ii[a], jj[a]])
            s = np.linspace(0.0, 1.0, 33)[1:]                     # radii from the envelope in toward the floor
            rad = R[ii[a], jj[a]][:, None] - s[None] * (R[ii[a], jj[a]] - lo)[:, None]
            ov = over_at(np.repeat(PH[ii[a], jj[a]], len(s)), np.repeat(TH[ii[a], jj[a]], len(s)), rad.ravel(),
                         mirror, az, front).reshape(rad.shape)
            fit = ~np.isfinite(ov) | (ov <= 0)
            got = fit.any(1)
            first = np.argmax(fit, 1)
            rstar = rad[np.arange(len(a)), first]
            # where no radius clears the edge: cut (cut_ahead True), or pull to the floor (False), or cut only where
            # the floor is still ahead by more than cut_ahead L (the cheek's front), else pull to the floor
            lim = 0.0 if cut_ahead is True else np.inf if cut_ahead is False else float(cut_ahead) * v.ppl
            soft_ = ~got & (ov[:, -1] <= lim)
            rstar[soft_] = lo[soft_]
            got |= soft_
            D[ii[a[got]], jj[a[got]]] = share * (R[ii[a[got]], jj[a[got]]] - rstar[got])
            kill[a[~got]] = True
            npull += int(got.sum())
        elif ahead.any():
            if share < 1.0:
                # half way: the cut at `share` of the distance from our own front (per row, the farthest forward) back
                cc, rr = view_px(ch.point(PH[ii, jj], TH[ii, jj], R[ii, jj]), v, az, mirror, hull_frame)
                r_ = np.floor(rr).astype(int)
                ours = {}
                for r, o in zip(r_[ahead], over[ahead]):
                    ours[r] = max(ours.get(r, -np.inf), o)
                lim = np.array([ours.get(r, 0.0) * (1 - share) for r in r_])
                ahead &= over - np.maximum(lim, 0.0) > 0
            kill = ahead
        for i in np.unique(ii[kill]):
            j0 = jj[kill & (ii == i)].min()
            ncut += int((Lc[i, j0:] == k).sum())
            Lc[i, j0:][Lc[i, j0:] == k] = 0
            cut[i] = min(cut[i], j0 * G.dth)
    if D.any() and spread > 0:
        # the cells round a pulled one (other families: the lower back beside a side lock) drawn in with it, less
        # `spread` (world: their layers' gap), so no layer behind comes out past the pulled lock
        from scipy.ndimage import grey_dilation
        near = grey_dilation(D, size=(5, 5), mode=('wrap', 'nearest')) - spread
        D = np.where(Lc == k, D, np.maximum(D, near))
    if D.any():
        Ds = np.maximum(D, gaussian_filter(D, smooth, mode=('wrap', 'nearest')))
        F['R'] = R - Ds
        F['Rn'] = F['Rn'] - gaussian_filter(Ds, 1.5, mode=('wrap', 'nearest'))
    F['trim_cut'] = cut
    F['trim'] = dict(pulled=npull, cut=ncut, pull_max=float(D.max()))
    return Lc


FAM_OF = {'bangs': 'bangs', 'side_lock_L': 'side_locks', 'side_lock_R': 'side_locks', 'upper_back': 'upper_back',
          'lower_back': 'lower_back'}


def drawn_tips(F, piece, phs, top, tip, masks, views, hull_frame, step=0.5, reach=18.0):
    """a piece's lower edge at any phi from the drawing: per phi, the view that faces it (the front within 50 degrees of
    phi 0, the profile (mirrored for her right) to 130, the back beyond), and down the envelope the lowest point that
    still shows inside the family's drawn mask there, searched from `reach` degrees above `tip` to `reach` below it,
    never past the column's reach (below it the envelope is only continued, and the skin isn't cleared). A phi whose
    edge the drawing doesn't show (hidden by another family) keeps `tip`. -> (tips, refined (bool per phi))."""
    from charkit.bodyqa import WIN
    ch, G = F['chart'], F['grid']
    s_, tr = hull_frame
    out, done = np.array(tip, float), np.zeros(len(phs), bool)
    for k, ph in enumerate(phs):
        a = abs(((ph + 180) % 360) - 180)
        view, mirror = ('front', False) if a < 50 else ('back', False) if a > 130 else ('profile', ph < 0)
        m = masks.get('%s__%s' % (view, FAM_OF[piece]))
        if m is None or view not in views:
            continue
        v = views[view]
        x0, y0 = int(round(v.grid_eye[0] - WIN['x'] * v.ppl)), int(round(v.grid_eye[1] - WIN['top'] * v.ppl))
        th = np.arange(max(top[k], tip[k] - reach), tip[k] + reach, step)
        if not len(th):
            continue
        P = ch.point(np.full(len(th), ph), th, G.sample(F['R'], np.full(len(th), ph), th))
        H = (P - tr) / s_
        if mirror:                                                 # her right: the profile seen from -x, mirrored
            H = H * np.array([-1.0, 1.0, 1.0])
        az = np.radians(v.az)
        u = H[:, 0] * np.cos(az) + H[:, 1] * np.sin(az)
        col = np.round(u * v.ppl + v.axis - x0).astype(int)
        row = np.round(v.eye_y - H[:, 2] * v.ppl - y0).astype(int)
        ok = (row >= 0) & (row < m.shape[0]) & (col >= 0) & (col < m.shape[1])
        inside = np.zeros(len(th), bool)
        inside[ok] = m[row[ok], col[ok]]
        if not inside.any() or not inside[:max(1, int(reach / step) // 2)].any():
            continue                                               # the drawing doesn't show this column's edge
        last = np.nonzero(inside)[0].max()
        ic = G.cell(ph, 0.0)[0]
        rc = F['reach'][ic]
        cap = (rc + 1.5) * G.dth if rc >= 0 else tip[k]
        out[k] = min(th[last] + step / 2, max(cap, tip[k]))
        if 'trim_cut' in F and FAM_OF[piece] == 'side_locks':
            out[k] = min(out[k], max(F['trim_cut'][ic], top[k] + 2 * step))     # (never below side_lock_trim's cut)
        done[k] = True
    return out, done


def refine_tips(F, regions, masks, views, hull_frame, step=0.5, reach=18.0):
    """each piece's lower edge at the drawing's resolution (drawn_tips at its columns). In place (tip);
    -> {piece: columns refined}."""
    done = {}
    for piece, Rg in regions.items():
        Rg['tip'], d = drawn_tips(F, piece, Rg['ph'], Rg['top'], Rg['tip'], masks, views, hull_frame, step, reach)
        done[piece] = int(d.sum())
    return done


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


def _ladder(a, b, ta, tb, out, flip=False):
    """triangles between two columns of vertices a (indices) and b, sampled at increasing thetas ta and tb from a shared
    start: advance along whichever column is behind, so no triangle spans more than one step of either."""
    i = j = 0
    while i < len(a) - 1 or j < len(b) - 1:
        if j == len(b) - 1 or (i < len(a) - 1 and ta[i + 1] <= tb[j + 1]):
            t = (a[i], b[j], a[i + 1]); i += 1
        else:
            t = (a[i], b[j], b[j + 1]); j += 1
        out.append(t[::-1] if flip else t)


def lock_shell(F, piece, ph0, ph1, ph_tip, ph_cols, top_cols, edge_cols, style, opts, L, edge_fn=None):
    """one lock's closed shell (see the module): columns every `step` degrees of phi, each sampled every `step` degrees
    of theta from its top down to its tip (the last sample exactly at the tip), neighbouring columns stitched by
    ladder, so a jagged tip edge shears no triangle. The outer surface is the envelope less the piece's inset (pushed
    out, smoothly, wherever it would come within gap + tip_thick of the skin); the inner one `thick` below it, tapering
    to tip_thick over the last `taper` of the lock's length, and never within `gap` of the skin. edge_fn(phs, top, tip):
    the lower edge at the lock's own columns (drawn_tips: the columns' edge interpolated rounds a drawn point off).
    -> dict(V, T, outer, strand, chain, vn_env, push (L, the most the outer surface moved out))."""
    from scipy.ndimage import gaussian_filter, maximum_filter
    ch, G = F['chart'], F['grid']
    step = opts['step']
    nu = max(2, int(np.ceil((ph1 - ph0) / step)))
    phs = np.linspace(ph0, ph1, nu + 1)
    top = np.maximum(np.interp(phs, ph_cols, top_cols), crown_top(opts))   # (the crown's cap covers the pole)
    tip = np.interp(phs, ph_cols, edge_cols)
    if edge_fn is not None:                     # the drawing's edge at the lock's own columns (its tips kept pointed)
        tip = edge_fn(phs, top, tip)
    tip = np.maximum(tip, top + step)
    inset = LAYER.get(piece, 1.0) * style['inset'] * L
    gap = opts['gap'] * L
    tt = style['tip_thick'] * L
    wrap = lambda p: ((p + 180) % 360) - 180
    # the push-out, on a regular grid over the lock (smoothed, grown first so it still clears the skin)
    gth = np.arange(top.min(), tip.max() + step, step / 2)
    PHg, THg = np.meshgrid(phs, gth, indexing='ij')
    Rg = G.sample(F['R'], wrap(PHg), THg) - inset
    Sg = G.sample(np.where(np.isfinite(F['S']), F['S'], -1e3), wrap(PHg), THg)
    push_g = np.maximum(Sg + gap + tt - Rg, 0.0)
    if push_g.any():
        push_g = np.maximum(push_g, gaussian_filter(maximum_filter(push_g, size=5, mode='nearest'), 1.5, mode='nearest'))
    taper = style.get('taper', 0.45)
    length = float((tip - top).max())
    Rog = Rg + push_g
    s_g = np.clip((np.interp(PHg, phs, tip) - THg) / max(1e-9, taper * length), 0, 1)
    thick_g = style['thick'] * L * s_g ** 0.6 + tt
    # the skin as the inner surface meets it: a smooth upper envelope (grown, then blurred), so an ear or a brow ridge
    # makes a gentle bump in the hidden surface, not a fold
    Su = gaussian_filter(maximum_filter(Sg, size=7, mode='nearest'), 2.0, mode='nearest')
    Rig = np.maximum(Rog - thick_g, np.minimum(Su + gap, Rog - tt))
    Rig = np.minimum(np.maximum(gaussian_filter(Rig, 1.5, mode='nearest'), Sg + gap), Rog - tt)   # smoothed, clear of
                                                                    # the skin, inside the outer surface
    cols, colth, Vo, Vi, strand, vn = [], [], [], [], [], []
    n = 0
    relief = style.get('relief', 0.0) * L       # each lock's ridge across it (0 at its edges): grooves between locks
    for k, ph in enumerate(phs):
        th = np.arange(top[k], tip[k], step)
        th = np.r_[th, tip[k]] if tip[k] - th[-1] > 1e-6 else th
        phk = np.full(len(th), wrap(ph))
        R = G.sample(F['R'], phk, th) - inset
        S = G.sample(np.where(np.isfinite(F['S']), F['S'], -1e3), phk, th)
        push = np.interp(th, gth, push_g[k])
        Ro = R + push
        if relief > 0 and ph1 > ph0:
            u = (ph - ph0) / (ph1 - ph0)
            grow = np.clip((th - top[k]) / max(1e-6, 0.3 * (tip[k] - top[k])), 0, 1)   # from the crown, where locks merge
            # and gone again by the tip: out along the chart's radius a hanging tip would dip into the shoulders
            fade = np.clip((tip[k] - th) / max(1e-6, 0.3 * (tip[k] - top[k])), 0, 1)
            Ro = Ro + relief * np.sin(np.pi * u) ** 0.6 * grow * fade
        if opts.get('crown_blend', 0) > 0:
            # the crown's cover over the lock's top: held just under it where the cover is outermost, the hold fading
            # over the cover's blend, so the lock comes out from under it (the cover may sit lower than the fringe)
            w = np.clip((th - (opts['crown_cap'] - opts['crown_blend'])) / opts['crown_blend'], 0, 1)
            cap = G.sample(F['R'], phk, th) - cap_inset(th, opts, style, L) - 0.003 * L
            Ro = np.maximum(np.minimum(Ro, cap + (w * w * (3 - 2 * w)) * L), np.maximum(S, -1e2) + gap + tt)
        Ri = np.minimum(np.interp(th, gth, Rig[k]), Ro - tt)
        Po, Pi = ch.point(phk, th, Ro), ch.point(phk, th, Ri)
        d = np.gradient(Po, axis=0) if len(th) > 1 else np.zeros_like(Po)
        strand.append(d / (np.linalg.norm(d, axis=1, keepdims=True) + 1e-12))
        # the envelope's normal (the smoother field) by finite differences on the chart
        # the envelope's normal: the shading's one smooth mass (no layer's inset, no push over the skin: the locks of every
        # piece shade as one surface, as an anime head of hair does)
        e = 0.5
        ep = e / np.maximum(np.sin(np.radians(th)), 0.05)             # (the same arc round the pole as down it)
        P = lambda a, b: ch.point(wrap(a), b, G.sample(F['Rn'], wrap(a), b))
        nrm = np.cross(P(phk + ep, th) - P(phk - ep, th), P(phk, th + e) - P(phk, np.maximum(th - e, 0.01)))
        nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
        if np.einsum('ij,ij->i', nrm, Po - ch.c).mean() < 0:
            nrm = -nrm
        vn.append(nrm)
        Vo.append(Po); Vi.append(Pi)
        cols.append(np.arange(n, n + len(th))); colth.append(th)
        n += len(th)
    no = n
    Vo, Vi = np.concatenate(Vo), np.concatenate(Vi)
    V = np.concatenate([Vo, Vi])
    T = []
    for k in range(nu):
        _ladder(cols[k], cols[k + 1], colth[k], colth[k + 1], T)                   # outer
        _ladder(cols[k] + no, cols[k + 1] + no, colth[k], colth[k + 1], T, flip=True)   # inner
    def quad(o0, o1):
        T.extend([(o0, o1, o1 + no), (o0, o1 + no, o0 + no)])
    for k in range(nu):
        quad(cols[k][0], cols[k + 1][0])                                      # the top edge
        quad(cols[k + 1][-1], cols[k][-1])                                    # the tip edge
    for c in (cols[0],):                                                      # the sides
        for a, b in zip(c[1:], c[:-1]):
            quad(a, b)
    for c in (cols[-1],):
        for a, b in zip(c[:-1], c[1:]):
            quad(a, b)
    T = np.array(T, np.int64)
    # orientation: the outer surface's normals away from the chart's centre
    outer_f = np.all(T < no, axis=1)
    tri = V[T[outer_f]]
    fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    if (np.einsum('ij,ij->i', fn, tri.mean(1) - ch.c) < 0).mean() > 0.5:
        T = T[:, [0, 2, 1]]
    vn = np.concatenate(vn)
    # the chain: at its tip's phi, halfway through its depth, root to tip
    kt = int(np.argmin(np.abs(phs - ph_tip)))
    c = cols[kt]
    sel = np.unique(np.linspace(0, len(c) - 1, opts['chain']).round().astype(int))
    chain = (Vo[c[sel]] + Vi[c[sel]]) / 2
    return dict(V=V, T=T, outer=np.r_[np.ones(no, bool), np.zeros(no, bool)],
                strand=np.concatenate([np.concatenate(strand)] * 2), vn_env=np.concatenate([vn, -vn]), chain=chain,
                push=float(push_g.max() / L), vn_shade=np.concatenate([vn, vn]))


def cap_inset(th, opts, style, L):
    """the crown's blended cover's inset under the envelope (world) at theta th (deg): `cap_top` L at the pole (default
    just outside the fringe's surface), kept to crown_cap - crown_blend, then easing (smoothstep) to under every
    layer by crown_cap."""
    th_cap, blend = opts['crown_cap'], opts['crown_blend']
    top_in = opts.get('cap_top', -0.002) * L
    deep = max(LAYER.values()) * style['inset'] * L + 0.01 * L
    w = np.clip((np.asarray(th, float) - (th_cap - blend)) / blend, 0, 1)
    return top_in + (deep - top_in) * (w * w * (3 - 2 * w))


def crown_top(opts):
    """the theta (deg) the locks that reach the crown start at: under the crown's cap."""
    if opts.get('crown_blend', 0) > 0:
        return max(1.5, opts['crown_cap'] - opts['crown_blend'] - 2 * opts['step'])
    return opts['crown_cap'] * 0.75


def crown_cap(F, style, opts, L):
    """the disc over the chart's pole (theta below crown_cap), part of the upper back. With crown_blend (deg) it is the
    crown's one smooth cover: outermost (a hair outside the fringe's surface) to crown_cap - crown_blend, then tucking
    under every layer by its rim, so the locks that meet at the crown start under it (crown_top) and come out from
    under it as they part: no lock's top converges to a sliver at the pole (hair round 3: the crown's shards), and the
    cap's rim is inside the locks, where its outline hull never shows. Without it: a fan at the upper back's layer."""
    ch, G = F['chart'], F['grid']
    n = 72 if opts.get('crown_blend', 0) > 0 else 36
    ring = np.linspace(-180, 180, n, endpoint=False)
    th_cap = opts['crown_cap']
    gap, tt = opts['gap'] * L, style['tip_thick'] * L
    Sk = np.where(np.isfinite(F['S']), F['S'], -1e3)
    blend = opts.get('crown_blend', 0.0)
    if blend > 0:
        ths = np.r_[np.arange(opts['step'], th_cap, opts['step']), th_cap]
        inset_at = lambda th: cap_inset(th, opts, style, L)    # (the rim under every layer's surface)
    else:
        ths = np.array([th_cap])
        inset_at = lambda th: LAYER['upper_back'] * style['inset'] * L + 0 * th

    # (blended: the outer face never nearer the skin than gap and half a tip: its rim, tucked deep under the locks,
    # would reach into the scalp where the envelope lies close over it; the locks are pushed out over it there too)
    floor = (lambda s: s + gap + 0.5 * tt) if blend > 0 else (lambda s: -np.inf)

    def surf(offset):
        # (the inner face as the locks' is: `offset` below the outer, never within gap of the skin nor above the outer)
        r0 = max(G.sample(F['R'], 0.0, 0.0) - inset_at(0.0), floor(G.sample(Sk, 0.0, 0.0)))
        if offset:
            r0 = min(max(r0 - offset, G.sample(Sk, 0.0, 0.0) + gap), r0 - tt)
        rings = []
        for th in ths:
            rr = np.maximum(G.sample(F['R'], ring, np.full(n, th)) - inset_at(th), floor(G.sample(Sk, ring, np.full(n, th))))
            if offset:
                rr = np.minimum(np.maximum(rr - offset, G.sample(Sk, ring, np.full(n, th)) + gap), rr - tt)
            rings.append(ch.point(ring, np.full(n, th), rr))
        return ch.point(np.array([0.0]), np.array([0.0]), np.array([r0]))[0], rings
    po, ro = surf(0.0)
    pi, ri = surf(style['thick'] * L * 0.5)
    nr = len(ths)
    V = np.concatenate([[po]] + ro + [[pi]] + ri)
    half = 1 + nr * n
    T = []
    idx = lambda base, r, k: base + 1 + r * n + (k % n)
    if nr == 1:                                 # (the plain fan, in its old order: the default build unchanged)
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
        outer = np.r_[np.ones(n + 1, bool), np.zeros(n + 1, bool)]
        strand = np.zeros_like(V); strand[:, 2] = -1
        return dict(V=V, T=T, outer=outer, strand=strand, vn_env=np.where(outer[:, None], vn, -vn), vn_shade=vn,
                    chain=np.array([po]), push=0.0)
    for k in range(n):
        T.append((0, idx(0, 0, k), idx(0, 0, k + 1)))
        T.append((half, idx(half, 0, k + 1), idx(half, 0, k)))
    for r in range(nr - 1):
        for k in range(n):
            a, b, c, d = idx(0, r, k), idx(0, r, k + 1), idx(0, r + 1, k), idx(0, r + 1, k + 1)
            T.extend([(a, c, d), (a, d, b)])
            a, b, c, d = idx(half, r, k), idx(half, r, k + 1), idx(half, r + 1, k), idx(half, r + 1, k + 1)
            T.extend([(a, d, c), (a, b, d)])
    for k in range(n):                                                  # the rim's wall
        a, b = idx(0, nr - 1, k), idx(0, nr - 1, k + 1)
        T.extend([(a, a + half, b + half), (a, b + half, b)])
    T = np.array(T, np.int64)
    tri = V[T[:n]]; fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    if np.einsum('ij,ij->i', fn, tri.mean(1) - ch.c).mean() < 0:
        T = T[:, [0, 2, 1]]
    d = V - ch.c
    vn = d / np.linalg.norm(d, axis=1, keepdims=True)
    outer = np.r_[np.ones(half, bool), np.zeros(half, bool)]
    strand = np.zeros_like(V); strand[:, 2] = -1
    return dict(V=V, T=T, outer=outer, strand=strand, vn_env=np.where(outer[:, None], vn, -vn), vn_shade=vn,
                chain=np.array([po]), push=0.0)


def cap_sectors(cap, F, regions, mode=True):
    """the crown's cover split round phi by the part lines: each face to the piece whose family the crown's rows take
    in its column (piece_regions' crown rows; the side locks by side; a family with no piece: the upper back). The cover
    stays one smooth surface; its sectors belong to the pieces whose locks they cover, so the fringe's crown is fringe
    (hair round 3: the cover as all upper back cost that family 0.013 IoU in profile). -> {piece: part}."""
    G, ch = F['grid'], F['chart']
    fam_at = F['Lfill'][:, 0]
    names = {fam_id('bangs'): 'bangs', fam_id('upper_back'): 'upper_back', fam_id('lower_back'): 'lower_back'}
    T = np.asarray(cap['T'])
    ph, th, _ = ch.coords(cap['V'][T].mean(1))
    i, _, _ = G.cell(ph, np.maximum(th, 1e-3))
    f = fam_at[i]
    piece = np.array([names.get(int(x), ('side_lock_L' if p_ > 0 else 'side_lock_R') if int(x) == fam_id('side_locks')
                                else 'upper_back') for x, p_ in zip(f, ph)])
    if mode == 'half':
        # (two sectors only: the front half the fringe's, the back half the upper back's; the part lines' sectors
        # showed as small pieces along the crown)
        piece = np.where(np.abs(ph) < 90, 'bangs', 'upper_back')
    piece = np.array([p_ if p_ in regions else 'upper_back' for p_ in piece])
    out = {}
    for name in np.unique(piece):
        sel = piece == name
        vids, Tn = np.unique(T[sel], return_inverse=True)
        part = {k: (np.asarray(v)[vids] if isinstance(v, np.ndarray) and len(v) == len(cap['V']) else v)
                for k, v in cap.items()}
        part['T'] = Tn.reshape(-1, 3)
        out[str(name)] = part
    return out


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


def superellipsoid(half, e=0.3, nu=40, nv=20):
    """a closed superellipsoid of half-sizes (a, b, c) along its own x, y, z: e near 0 is a box with rounded edges, 1 an
    ellipsoid. -> (V (n, 3), T (m, 3) outward)."""
    a, b, c = half
    sg = lambda x, p: np.sign(x) * np.abs(x) ** p
    V = [np.array([0.0, 0.0, -c])]
    for i in range(1, nv):
        v = -np.pi / 2 + np.pi * i / nv
        for j in range(nu):
            u = -np.pi + 2 * np.pi * j / nu
            V.append(np.array([a * sg(np.cos(v), e) * sg(np.cos(u), e), b * sg(np.cos(v), e) * sg(np.sin(u), e),
                               c * sg(np.sin(v), e)]))
    V.append(np.array([0.0, 0.0, c]))
    V = np.array(V)
    T = []
    ring = lambda i: 1 + (i - 1) * nu
    for j in range(nu):
        T.append((0, ring(1) + (j + 1) % nu, ring(1) + j))
    for i in range(1, nv - 1):
        for j in range(nu):
            a0, a1 = ring(i) + j, ring(i) + (j + 1) % nu
            b0, b1 = ring(i + 1) + j, ring(i + 1) + (j + 1) % nu
            T += [(a0, a1, b1), (a0, b1, b0)]
    top = len(V) - 1
    for j in range(nu):
        T.append((top, ring(nv - 1) + j, ring(nv - 1) + (j + 1) % nu))
    return V, np.array(T, np.int64)


def view_px(Vw, view, az, mirror, hull_frame):
    """world points' pixel (col, row, floats) in one of the hull's views (label_hull's frame and window; a mirrored view's
    columns are the flipped drawing's)."""
    from charkit.bodyqa import WIN as W
    s_, tr = hull_frame
    h = (np.asarray(Vw, float) - tr) / s_
    ppl = view.ppl
    a = np.radians(az)
    ox = (view.grid_eye[0] - view.axis) / ppl
    org = (-ox if mirror else ox, (view.eye_y - view.grid_eye[1]) / ppl)
    u = h[:, 0] * np.cos(a) + h[:, 1] * np.sin(a)
    return (u - org[0] + W['x']) * ppl, (W['top'] - (h[:, 2] - org[1])) * ppl


def _hull_fill(cols, rows, shape):
    """the filled convex hull of 2-d points (a convex part's silhouette)."""
    from scipy.spatial import ConvexHull
    from skimage.draw import polygon
    m = np.zeros(shape, bool)
    pts = np.c_[cols, rows]
    try:
        k = ConvexHull(pts).vertices
    except Exception:
        return m
    rr, cc = polygon(pts[k, 1], pts[k, 0], shape)
    m[rr, cc] = True
    return m


def bun_targets(masks, views, hull_frame, head_c, side):
    """the drawn bun one side, per view it's seen in: (view, az, mirror, drawn bun mask, other hair) — the front and back
    halves on her side of the head's axis, her own profile (the mirror for her right: its far bun is the near one's)."""
    out = []
    for name, az, mirror in (('front', 0.0, False), ('profile', 90.0 if side > 0 else 270.0, side < 0),
                             ('back', 180.0, False)):
        m = masks.get('%s__buns' % name)
        if m is None or name not in views:
            continue
        other = np.zeros_like(m, bool)
        for f in FAMILIES:
            if f != 'buns' and masks.get('%s__%s' % (name, f)) is not None:
                other |= masks['%s__%s' % (name, f)]
        if mirror:
            m, other = m[:, ::-1], other[:, ::-1]
        if name != 'profile':
            cc, _ = view_px(np.asarray(head_c, float)[None], views[name], az, mirror, hull_frame)
            cols = np.arange(m.shape[1])
            keep = (cols > cc[0]) if (side > 0) == (name == 'front') else (cols < cc[0])
            m = m & keep[None]
        out.append((name, az, mirror, m, other & ~m))
    return out


def fit_block(P, head_c, style, targets, views, hull_frame, iters=(600, 900), kind='block', over=0.25, loop_starts=1):
    """a block bun's pose and size fitted to the drawn bun: from bun_block's frame and extents (the hull's points), the
    centre, a rotation and the three half-sizes that best cover each view's drawn bun, then with the fold's slab free
    too (its place and size in the bun's frame) (Nelder-Mead on the silhouettes: the drawn bun missed and ours outside
    any drawn hair count whole, ours over the drawing's other hair (it may pass behind it) a quarter).
    -> (bun_block's fit {c, R, half, slab}, per-view IoU before/after)."""
    from scipy.optimize import minimize
    from scipy.spatial.transform import Rotation as Rot
    c0, R0, half0 = block_frame(P, head_c, style)
    o0, s0 = (loops_default if kind == 'ribbon' else slab_default)(c0, R0, head_c, style)
    e = style.get('bun_e', 0.3)
    U1, _ = superellipsoid(np.ones(3), e, 16, 8)

    def sil(c, R, half, slab, name, az, mirror, shp):
        m = np.zeros(shp, bool)
        for off, hs in block_parts(c, R, half, head_c, style, slab, kind):
            cc, rr = view_px(off + (U1 * hs) @ R.T, views[name], az, mirror, hull_frame)
            m |= _hull_fill(cc, rr, shp)
        return m

    nx = 16 if kind == 'ribbon' else 15              # (the ribbon: its two loops' asymmetry too)

    def unpack(x):
        x = np.r_[x, np.zeros(nx - len(x))]
        R = Rot.from_rotvec(x[3:6]).as_matrix() @ R0
        return c0 + x[:3] * np.linalg.norm(half0), R, half0 * np.exp(x[6:9]), (o0 + x[9:12], s0 * np.exp(x[12:15]),
                                                                                  *x[15:])

    w_over = over

    def loss(x, detail=False):
        c, R, half, slab = unpack(x)
        tot, per = 0.0, {}
        for name, az, mirror, m, other in targets:
            sm = sil(c, R, half, slab, name, az, mirror, m.shape)
            miss = (m & ~sm).sum(); out = (sm & ~m & ~other).sum(); over = (sm & other).sum()
            wv = w_over.get(name, 0.25) if isinstance(w_over, dict) else w_over
            tot += (miss + out + wv * over) / max(1, m.sum())
            per[name] = round(float((sm & m).sum()) / max(1, (sm | m).sum()), 3)
        return per if detail else tot
    before = loss(np.zeros(9), True)
    x = np.zeros(0)
    last = np.r_[[0.05] * 3, [0.08] * 3, [0.08] * 3, [0.3] * 3, [0.25] * 3] if kind != 'ribbon' else \
        np.r_[[0.05] * 3, [0.08] * 3, [0.08] * 3, [0.12] * 3, [0.25] * 3, [0.3]]
    for n, steps, fev in ((9, np.r_[[0.15] * 3, [0.25] * 3, [0.2] * 3], iters[0]), (nx, last, iters[1])):
        x0 = np.r_[x, np.zeros(n - len(x))]
        simplex = np.vstack([x0] + [x0 + d for d in np.eye(n) * steps])
        x = minimize(loss, x0, method='Nelder-Mead', options=dict(maxfev=fev, initial_simplex=simplex, xatol=1e-3,
                                                                   fatol=1e-4)).x
    if kind == 'ribbon' and loop_starts > 1:
        # (the loops' placement: the fit starts them set back; bun_detail's side view and the sheet's profile disagree
        # on which side the step shows, so a start set forward is fitted too and the better kept)
        x1 = np.r_[x[:9], np.zeros(nx - 9)]
        x1[10] = -2 * o0[1]
        simplex = np.vstack([x1] + [x1 + d for d in np.eye(nx) * last])
        x1 = minimize(loss, x1, method='Nelder-Mead', options=dict(maxfev=iters[1], initial_simplex=simplex, xatol=1e-3,
                                                                    fatol=1e-4)).x
        if loss(x1) < loss(x):
            x = x1
    c, R, half, slab = unpack(x)
    return dict(c=c, R=R, half=half, slab=slab), dict(before=before, after=loss(x, True))


def slab_default(mid, R, head_c, style):
    """the fold's slab by default, in the bun's frame as shares of its half-sizes: (centre, half-sizes) beside the block
    on the head's side and lower (bun_slab: its share of the width)."""
    sl = style.get('bun_slab', 0.38)
    s_in = -np.sign((mid - np.asarray(head_c, float)) @ R[:, 0]) or 1.0
    return np.array([s_in * (0.92 + 0.55 * sl), 0.0, -0.18]), np.array([sl, 0.85, 0.78])


def loops_default(mid, R, head_c, style):
    """the ribbon bun's loops by default (bun_detail's construction: a knot block, a ribbon loop either side of it,
    narrower, set back and lower, its top below the knot's), in the bun's frame as shares of its half-sizes: (the
    outer loop's centre, its half-sizes); the inner loop mirrors it across the knot."""
    w = style.get('bun_loop', 0.26)
    k = style.get('bun_knot', 0.6)
    return np.array([k + 0.55 * w, -0.25, -0.20]), np.array([w, 0.80, 0.74])


def block_frame(P, head_c, style):
    """a block bun's frame from its hull points: up out from the head's centre through the bun, front the viewer's side
    orthogonalised, lat their cross; the centre and half-sizes the points' bun_q..1-bun_q percentiles along each.
    -> (centre, R (own -> world columns), half)."""
    c = np.median(P, 0)
    up = c - np.asarray(head_c, float)
    up /= np.linalg.norm(up)
    front = np.array([0.0, -1.0, 0.0]) - up * (-up[1])
    front /= np.linalg.norm(front)
    lat = np.cross(front, up)                                   # (toward her left for the left bun; either way apart)
    R = np.stack([lat, front, up], 1)
    q = (P - c) @ R
    lo, hi = np.percentile(q, [100 * style.get('bun_q', 0.06), 100 * (1 - style.get('bun_q', 0.06))], axis=0)
    return c + R @ ((hi + lo) / 2), R, (hi - lo) / 2


def block_parts(mid, R, half, head_c, style, slab=None, kind='block'):
    """a block bun's boxes: (centre, half-sizes) of each. 'block': the main block and the fold's slab (slab: its
    centre and half-sizes in the bun's frame as shares of the block's half-sizes, else slab_default's). 'ribbon'
    (bun_detail's two loops): the knot (bun_knot of the width) and a loop either side (slab: the outer loop's centre
    and half-sizes as shares, and optionally their asymmetry a: the inner loop's size exp(a) the outer's, else
    loops_default's), the inner one mirrored across the knot in its lateral axis."""
    if kind == 'ribbon':
        o, sz, *a = slab if slab is not None else loops_default(mid, R, head_c, style)
        o, sz = np.asarray(o, float), np.asarray(sz, float)
        k = style.get('bun_knot', 0.6)
        g = np.exp(a[0]) if a else 1.0
        oi = o * np.array([-1.0, 1.0, 1.0])
        return [(mid, half * np.array([k, 0.95, 0.95])), (mid + R @ (o * half), half * sz),
                (mid + R @ (oi * half), half * sz * g)]
    o, sz = (slab if slab is not None else slab_default(mid, R, head_c, style))[:2]
    return [(mid, half * np.array([0.92, 0.95, 0.95])), (mid + R @ (np.asarray(o) * half), half * np.asarray(sz))]


def bun_block(P, head_c, style, side=1, fit=None, kind='block'):
    """a block bun (the design's buns as drawn: faceted loops, like a folded ribbon, not a round knot): two rounded
    boxes (superellipsoids, the style's bun_e: flat faces, bevelled edges) in the bun's own frame (up: out from the
    head's centre through the bun; front: the viewer's side, orthogonalised), the main block sized to the hull's bun
    points (their bun_q..1-bun_q percentiles along each axis: a visual hull's blob is the block's outline filled), and
    a thinner slab (bun_slab: its share of the width) beside it on the head's side and lower, the loop folded over.
    fit: fit_block's pose and size (else block_frame's).
    -> dict(V, T, vn_env, strand, chain, outer, push, vn_shade (its own normals: flat faces shade flat))."""
    mid, R, half = (fit['c'], fit['R'], fit['half']) if fit else block_frame(P, head_c, style)
    up = R[:, 2]
    e = style.get('bun_e', 0.3)
    Vs, Ts, n = [], [], 0
    for off, hs in block_parts(mid, R, half, head_c, style, (fit or {}).get('slab'), kind):
        V_, T_ = superellipsoid(hs, e)
        Vs.append(off + V_ @ R.T); Ts.append(T_ + n); n += len(V_)
    V = np.concatenate(Vs); T = np.concatenate(Ts)
    vn = geometric_normals(V, T)
    strand = np.tile(-up, (len(V), 1))
    return dict(V=V, T=T, vn_env=vn, strand=strand, chain=np.array([mid]), outer=np.ones(len(V), bool), push=0.0,
                vn_shade=vn, own_normals=True)


def tuck_blade(F, W3, wd, surface_inset, margin, up=1, soft=0.8):
    """a blade's centreline (root to tip) against the locks' outer surface on the crown chart (the envelope less
    surface_inset, world): the root's run, up to the first point from which the blade stays clear of the surface (its
    tube's half-width wd/2 plus margin outside it), sunk that far under it, so the blade leaves the lock once, cleanly,
    where the drawing's flick leaves the mass; a later point that comes back within reach (a curl over the lock) is
    lifted to lie that far over it. Without this a blade at the front view's mid-plane crossed the lock surface where
    the envelope dips (hair round 3: the "ʃ" slivers and loose shards over the side locks in profile). The root's run
    is dropped (the blade starts sunk just under the surface where it emerges: a dive from further in folded the
    tube), the lift smoothed along the line (`soft` samples); `up` resamples it finer (1: as drawn; finer rings fold
    at the bends). -> (centreline, widths)."""
    from scipy.ndimage import gaussian_filter1d
    ch, G = F['chart'], F['grid']
    n = len(W3)
    t = np.linspace(0, n - 1, up * (n - 1) + 1)
    W3 = np.stack([np.interp(t, np.arange(n), W3[:, k]) for k in range(3)], 1)
    wd = np.interp(t, np.arange(n), np.asarray(wd, float))
    ph, th, r = ch.coords(W3)
    Rs = G.sample(F['R'], ph, th) - surface_inset
    reach = wd / 2 + margin
    clear = r >= Rs + reach
    if clear.all():
        return W3, wd
    out = np.nonzero(clear)[0]
    if not len(out):
        return W3[:0], wd[:0]                                   # (all of it inside the locks: no flick shows)
    first = out[0]
    if first > 0:
        # the root's run dropped: the blade starts one sample before it clears, sunk under the surface there (a dive
        # from further in bent the tube tighter than its own width: folds)
        k = first - 1
        ph, th, r, Rs, reach, wd, W3 = ph[k:], th[k:], r[k:].copy(), Rs[k:], reach[k:], wd[k:], W3[k:]
        r[0] = min(r[0], Rs[0] - reach[0])
    rt = r.copy()
    rt[1:] = np.maximum(r[1:], Rs[1:] + reach[1:])              # the rest: over it
    dr = gaussian_filter1d(rt - r, soft, mode='nearest')
    dr[0] = 0.0
    return ch.point(ph, th, r + dr), wd


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
    if np.linalg.norm(ref) < 1e-9 * max(1e-9, np.linalg.norm(P[-1] - P[0]) ** 2):
        ref = np.cross(t[0], [0.0, 0.0, 1.0]) if abs(t[0][2]) < 0.9 else np.cross(t[0], [1.0, 0.0, 0.0])
    ref /= np.linalg.norm(ref)
    V, strand = [], []
    a = ref - t[0] * (ref @ t[0]); a /= np.linalg.norm(a) + 1e-12
    for k in range(n):
        if k:                                                                  # parallel transport: no flips
            a = a - t[k] * (a @ t[k]); a /= np.linalg.norm(a) + 1e-12
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


def centreline_2d(comp, root_dist, n):
    """a drawn stroke's centreline: its two ends (the farthest pair by path), the root the end with the smaller
    root_dist(cols, rows) (where it grows from); its pixels ordered by path from there, in n bins, each bin's centroid and
    width (twice its 85th percentile spread). -> (points (m, 2) as (col, row), widths (m,) px) or None."""
    rr, cc = np.nonzero(comp)
    if len(rr) < 6:
        return None
    pts = np.c_[cc, rr].astype(float)
    d0 = _order_by_path(pts, 0, k=6)
    a = int(np.nanargmax(np.where(np.isfinite(d0), d0, -1)))
    da = _order_by_path(pts, a, k=6)
    b = int(np.nanargmax(np.where(np.isfinite(da), da, -1)))
    rd = root_dist(cc, rr)
    root = a if rd[a] <= rd[b] else b
    dist = da if root == a else _order_by_path(pts, b, k=6)
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
    return (np.array(line), np.array(width)) if len(line) >= 3 else None


def _resample(P, n):
    """a polyline resampled to n points evenly in arc length."""
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    t = np.linspace(0, s[-1], n)
    return np.stack([np.interp(t, s, P[:, k]) for k in range(P.shape[1])], 1)


def ahoge_2d(masks, views, hull_frame, n=12):
    """the ahoge from the drawings: its front stroke gives x(s), its profile stroke y(s), both z(s) (averaged), s the
    arc length from where each grows out of the rest of the hair; its width is the front stroke's, tapering to the tip.
    -> a blade dict, or None without both strokes."""
    from scipy import ndimage
    from charkit.bodyqa import WIN
    lines = {}
    for name in ('front', 'profile'):
        m = masks.get('%s__ahoge' % name)
        if m is None or m.sum() < 20:
            return None
        # the topmost stroke of 50 px or more: the breakdown's ahoge teal also colours the buns' ribbon tails below
        lab, k = ndimage.label(m)
        sizes = np.bincount(lab.ravel())
        cand = [i for i in range(1, k + 1) if sizes[i] >= 50]
        if not cand:
            return None
        tops = {i: np.nonzero(lab == i)[0].min() for i in cand}
        near = [i for i in cand if tops[i] <= min(tops.values()) + 0.1 * views[name].ppl]
        comp = lab == max(near, key=lambda i: sizes[i])            # the largest stroke at the very top
        rest = np.zeros_like(m)
        for f in MASS + ('buns',):
            q = masks.get('%s__%s' % (name, f))
            if q is not None:
                rest |= q
        dt = ndimage.distance_transform_edt(~rest)
        got = centreline_2d(comp, lambda c, r: dt[r, c], n)
        if got is None:
            return None
        v = views[name]
        x0 = int(round(v.grid_eye[0] - WIN['x'] * v.ppl)); y0 = int(round(v.grid_eye[1] - WIN['top'] * v.ppl))
        P, w = got
        u = (x0 + P[:, 0] - v.axis) / v.ppl
        z = (v.eye_y - (y0 + P[:, 1])) / v.ppl
        lines[name] = (np.c_[u, z], w / v.ppl)
    F_, P_ = _resample(lines['front'][0], n), _resample(lines['profile'][0], n)
    w = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(lines['front'][1])), lines['front'][1])
    Ph = np.c_[F_[:, 0], P_[:, 0], (F_[:, 1] + P_[:, 1]) / 2]
    s_, tr = hull_frame
    return blade(Ph * s_ + tr, w * s_ * np.linspace(1.0, 0.15, n))


def flyaways(mask, to_world, anchor_fn, min_px=40, n=7, depth_ratio=0.4, tuck=None):
    """the flyaways of the front view's family mask (a design grid): each connected piece a blade whose centreline runs by
    path from its pixel nearest the mass (anchor_fn: pixel -> distance to the mass) to its far end; to_world: (cols,
    rows) -> world points (at the envelope's side); tuck(centreline, widths) -> centreline: the blade's root kept under
    the locks it grows from (tuck_blade). -> [blade dicts]."""
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
        # one plane: the root's depth held along the strand (the mass's mid-plane jitters point to point), the line
        # smoothed along itself
        W3[:, 1] = W3[0, 1]
        if len(W3) >= 4:
            from scipy.ndimage import gaussian_filter1d
            W3 = np.r_[W3[:1], gaussian_filter1d(W3, 0.8, axis=0, mode='nearest')[1:]]
        px = np.linalg.norm(to_world(np.array([0.0, 1.0]), np.array([0.0, 0.0]))[1] - to_world(np.array([0.0]),
                                                                                                 np.array([0.0]))[0])
        wd = np.array(width) * px * np.linspace(1.0, 0.2, len(width))
        if tuck is not None:
            W3, wd = tuck(W3, wd)
            if len(W3) < 3:
                continue
        out.append(blade(W3, wd, depth_ratio))
    return out


# ------------------------------------------------------------------------------------------------------------ build
def build(case, fam, masks, style, views=None, hull_frame=None, opts=None, log=print):
    """every piece. case: charkit.geom.parts.Case (the hull aligned: case.gen, our character: case.A); fam: the hull's
    per-vertex family (label_hull); masks: hairlayers' VIEW__FAMILY; style: the profile's hair_pieces; hull_frame:
    (scale, translate) from the hull's frame to the world (the case's align) for the flyaways' front view.
    -> dict(pieces {name: dict(family, V, T, vn_env, strand, lock (per vertex), chains [joints], push)}, fields, report)."""
    from scipy.ndimage import median_filter
    o = dict(OPTS, **(opts or {}))
    style = dict(style, **(o.pop('style', None) or {}))      # (a design's own construction settings over the profile's)
    L = case.L
    V = np.asarray(case.gen.V, float)
    carved = 0
    if views is not None and hull_frame is not None and o.get('carve_buns', True):
        fam, carved = carve_under_buns(V, fam, masks, views, hull_frame)
    F = mass_fields(case, V, fam, o)
    trim = None
    # side_lock_trim (a quality fix: the hull's fill between lock and cheek out of the envelope before the locks are
    # shaped), or the clamp (Michael's call F, deferred) in its envelope mode
    if views is not None and hull_frame is not None and (o.get('side_lock_trim', False) or (
            o.get('clamp_side_locks', False) and o.get('clamp_mode', 'envelope') == 'envelope')):
        # the pull's floor per cell: where a side lock's outer surface (the envelope less its inset) would come within
        # the skin's clearance (gap and a tip); no skin in the cell (the hanging hair): 0.3 L in
        Sk = F['S']
        floor = np.where(np.isfinite(Sk), Sk + o['gap'] * L + style['tip_thick'] * L +
                         LAYER['side_lock_L'] * style['inset'] * L, F['R'] - 0.3 * L)
        trim = lambda Lc: side_lock_trim(F, Lc, masks, views, hull_frame, o.get('trim_margin', 0.0),
                                         o.get('clamp_share', 1.0), floor, o.get('trim_pull', True),
                                         o.get('trim_cut', True), o.get('trim_smooth', 0.7),
                                         o.get('trim_spread', -1.0) * L if o.get('trim_spread', -1.0) >= 0 else 0.0,
                                         None if o.get('trim_below_chin', False) else case.chin_z,
                                         o.get('trim_sides', 'drawn'))
    regions = piece_regions(F, o, trim)
    refined = refine_tips(F, regions, masks, views, hull_frame) if views is not None and hull_frame is not None else {}
    pieces, report = {}, {'pieces': {}, 'tips_from_drawing': refined, 'carved_under_buns': carved}
    if 'trim' in F:
        report['side_lock_trim'] = dict(F['trim'], pull_max=round(F['trim']['pull_max'] / L, 4))

    def add(name, family, parts):
        Vs, Ts, vn, vs, st, lk, chains, off, pushes, nf, ou = [], [], [], [], [], [], [], 0, [], 0, []
        own = any(p.get('own_normals') for p in parts)
        for k, p in enumerate(parts):
            Vs.append(p['V']); Ts.append(p['T'] + off); vn.append(p['vn_env']); st.append(p['strand'])
            vs.append(p.get('vn_shade', p['vn_env']))
            lk.append(np.full(len(p['V']), k)); chains.append(np.asarray(p['chain']).tolist())
            pushes.append(p.get('push', 0.0)); off += len(p['V'])
            ou.append(np.asarray(p.get('outer', np.ones(len(p['V']), bool)), bool))
            nf += folds(p['V'], p['T'], p.get('outer', np.ones(len(p['V']), bool)), p['vn_env'])
        pieces[name] = dict(family=family, V=np.concatenate(Vs), T=np.concatenate(Ts), vn_env=np.concatenate(vn),
                            vn_shade=np.concatenate(vs), own_normals=own, outer=np.concatenate(ou),
                            strand=np.concatenate(st), lock=np.concatenate(lk), chains=chains)
        report['pieces'][name] = dict(family=family, locks=len(parts), verts=int(off),
                                      tris=int(sum(len(t) for t in Ts)), push_L=round(float(max(pushes)), 4), folds=nf)
    sectors = {}
    if o.get('crown_blend', 0) > 0 and o.get('cap_sectors', False):
        sectors = cap_sectors(crown_cap(F, style, o, L), F, regions, o['cap_sectors'])
    for piece, R in regions.items():
        ph = _unwrap(R['ph'])
        L_, edge = locks(ph, R['tip'], style['lock_min'], style['notch'])
        efn = None
        if refined and piece in o.get('fine_tips', ()):
            efn = (lambda p_: lambda phs, top, tip: median_filter(drawn_tips(
                F, p_, ((phs + 180) % 360) - 180, top, tip, masks, views, hull_frame)[0], 3, mode='nearest'))(piece)
        parts = [lock_shell(F, piece, a, b, t, ph, R['top'], edge, style, o, L, efn) for a, b, t in L_]
        if sectors:
            if piece in sectors:
                parts.append(sectors[piece])
        elif piece == 'upper_back':
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
                kind = o.get('bun', style.get('bun', 'round'))
                if kind not in ('block', 'ribbon'):
                    add(side, 'buns', [bun(P)])
                    continue
                fit = None
                if views is not None and hull_frame is not None and o.get('bun_fit', True):
                    tg = bun_targets(masks, views, hull_frame, case.centre, sgn)
                    if tg:
                        fit, iou = fit_block(P, case.centre, style, tg, views, hull_frame,
                                             tuple(o.get('bun_iters', (600, 900))), kind, o['bun_over'],
                                             o.get('bun_loop_starts', 1))
                        report.setdefault('bun_fit', {})[side] = iou
                add(side, 'buns', [bun_block(P, case.centre, style, sgn, fit, kind)])
    # the ahoge: from the drawings' strokes (the hull carves so thin a crescent poorly), else its hull points
    ah = ahoge_2d(masks, views, hull_frame) if views is not None and hull_frame is not None else None
    ap = V[fam == fam_id('ahoge')]
    if ah is not None:
        add('ahoge', 'ahoge', [ah])
    elif len(ap) > 20:
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
        tk = None
        if o.get('tuck_flyaways', True):
            tk = lambda W3, wd: tuck_blade(F, W3, wd, LAYER['side_lock_L'] * style['inset'] * L, 0.004 * L)
        bl = flyaways(fm, to_world, anchor_fn, tuck=tk)
        if bl:
            add('flyaways', 'flyaways', bl)
    # the side locks held behind the drawing's front edge in profile: the hull fills the gap between a lock and the cheek
    # (no view shows it), so they stood in front of the face; each side's own view (her right: the mirrored profile).
    # Opt-in: moving a built lock folds it (per vertex 150-200 outer folds a side lock, sheared per height 40-130, and
    # the render crumples); the constraint belongs in the chart's envelope before the locks are lofted
    if views is not None and hull_frame is not None and masks.get('profile__side_locks') is not None and \
            o.get('clamp_side_locks', False) and o.get('clamp_mode', 'envelope') == 'shear':
        fr = skin_front(surface_points(np.asarray(case.A['verts'], float), case.A['faces'], 0.006 * L), 0.008 * L) \
            if o.get('clamp_keep_cheek', True) else None
        for name, az, mirror in (('side_lock_L', 90.0, False), ('side_lock_R', 270.0, True)):
            if name in pieces:
                V2, mv = clamp_to_view(pieces[name]['V'], pieces[name]['T'], masks['profile__side_locks'],
                                       views['profile'], az, mirror, hull_frame, margin=o.get('clamp_margin', 0.01),
                                       skin=fr, gap=o['gap'] * L)
                pieces[name]['V'] = V2
                report['pieces'][name]['clamped_L'] = round(mv, 4)
                report['pieces'][name]['folds'] = folds(V2, pieces[name]['T'], pieces[name]['outer'],
                                                        pieces[name]['vn_env'])      # (counted again once moved)
    if style.get('normals', 'envelope') == 'envelope':
        shade_normals(pieces, L, style)
    report['fields'] = dict(columns_with_hair=int((F['reach'] >= 0).sum()), cells=int(F['valid'].sum()),
                            crown_tilt=o['crown_tilt'])
    log('hair pieces: %s' % ', '.join('%s %d locks' % (k, r['locks']) for k, r in report['pieces'].items()))
    return dict(pieces=pieces, fields=F, report=report)


def skin_front(P, cell):
    """our skin's front (its least y) over the front view's plane: a function (x, z) -> y (inf where no skin), from
    surface points P binned in cells of `cell` (world), each cell the least of its 3x3 neighbourhood's."""
    from scipy.ndimage import minimum_filter
    lo = P[:, [0, 2]].min(0) - 2 * cell
    ij = np.floor((P[:, [0, 2]] - lo) / cell).astype(int)
    shp = ij.max(0) + 3
    Y = np.full(shp, np.inf)
    np.minimum.at(Y, (ij[:, 0], ij[:, 1]), P[:, 1])
    Y = minimum_filter(Y, size=3, mode='constant', cval=np.inf)

    def f(x, z):
        i = np.floor((np.asarray(x) - lo[0]) / cell).astype(int); j = np.floor((np.asarray(z) - lo[1]) / cell).astype(int)
        ok = (i >= 0) & (i < shp[0]) & (j >= 0) & (j < shp[1])
        out = np.full(len(i), np.inf)
        out[ok] = Y[i[ok], j[ok]]
        return out
    return f


def clamp_to_view(V, T, mask, view, az, mirror, hull_frame, margin=0.01, smooth=2.0, skin=None, gap=0.0,
                  band=0.01):
    """a piece held behind the drawing's front edge in one view: its vertices that project in front of the drawn mask's
    front-most column in their row (toward the face) are moved back along the view's horizontal to it, less `margin` L:
    the piece sheared, one move per `band` L of height (smoothed over `smooth` bands), so the lock bends as a whole. The view's frame and pixels
    are label_hull's (the hull's views, a mirrored profile for her right side). skin: skin_front's function: when a
    side view's move is backward (+y): a vertex in front of the skin there stays `gap` (world) in front of it, since
    the front view draws the lock over the cheek (a face wider than the drawing's keeps it forward rather than behind
    the cheek). -> (moved V, the largest move, L)."""
    from charkit.bodyqa import WIN as W
    s_, tr = hull_frame
    h = (np.asarray(V, float) - tr) / s_
    ppl = view.ppl
    a = np.radians(az)
    ox = (view.grid_eye[0] - view.axis) / ppl
    org = (-ox if mirror else ox, (view.eye_y - view.grid_eye[1]) / ppl)
    u = h[:, 0] * np.cos(a) + h[:, 1] * np.sin(a)
    col = (u - org[0] + W['x']) * ppl
    row = np.floor((W['top'] - (h[:, 2] - org[1])) * ppl).astype(int)
    img = mask[:, ::-1] if mirror else mask
    H, Wd = img.shape
    front = np.full(H, np.nan)
    rows = np.nonzero(img.any(1))[0]
    for r in rows:
        c = np.nonzero(img[r])[0]
        front[r] = c.max() if mirror else c.min()
    ok = (row >= 0) & (row < H)
    fr = np.full(len(h), np.nan)
    fr[ok] = front[row[ok]]
    lim = fr + (margin * ppl if mirror else -margin * ppl)
    ahead = np.isfinite(fr) & ((col > lim) if mirror else (col < lim))
    du = np.zeros(len(h))
    du[ahead] = (lim[ahead] - col[ahead]) / ppl
    if not ahead.any():
        return np.asarray(V, float), 0.0
    step = np.array([np.cos(a), np.sin(a), 0.0])
    if skin is not None:
        # the most each may move (hull units along the view's horizontal): to gap in front of the skin behind it
        Vw = np.asarray(V, float)
        fy = skin(Vw[:, 0], Vw[:, 2])
        dy = step[1] * np.sign(du) * s_                          # world y per hull unit of |du| (+: backward)
        room = np.where(np.isfinite(fy) & (Vw[:, 1] < fy - gap) & (dy > 0), (fy - gap - Vw[:, 1]) / np.maximum(dy, 1e-12),
                        np.inf)
        ahead &= room > 0
        if not ahead.any():
            return np.asarray(V, float), 0.0
    # one move per height (a shear of the whole piece, rows of `band` L): the most any vertex in the row needs, never
    # more than the row's least room in front of the cheek, smoothed down the piece. Per-vertex moves folded the lock
    # over itself (150-200 outer folds a side lock), since a lock's front and back vertices then moved apart.
    zb = np.floor(h[:, 2] / band).astype(int)
    z0 = zb.min()
    nbins = zb.max() - z0 + 1
    need = np.zeros(nbins)
    np.maximum.at(need, zb[ahead] - z0, np.abs(du[ahead]))
    if skin is not None:
        cap = np.full(nbins, np.inf)
        np.minimum.at(cap, zb - z0, room)
        need = np.minimum(need, cap)
    from scipy.ndimage import gaussian_filter1d, maximum_filter1d
    need = gaussian_filter1d(maximum_filter1d(need, 3), smooth, mode='nearest')
    du = np.sign(du[ahead].mean()) * need[zb - z0]
    h = h + np.outer(du, step)
    return h * s_ + tr, float(np.abs(du).max())


def save(R, path, meta=None):
    """the pieces for the Blender stage: one .npz, per piece NAME/V, NAME/F, NAME/vn (the envelope's normals),
    NAME/strand, NAME/lock, and a json meta (families, chains, the report)."""
    arrays = {}
    info = dict(meta or {}, report=R['report'], pieces={})
    for name, p in R['pieces'].items():
        arrays[name + '/V'] = p['V'].astype(np.float32)
        arrays[name + '/F'] = p['T'].astype(np.int32)
        arrays[name + '/vn'] = p['vn_shade'].astype(np.float32)
        arrays[name + '/strand'] = p['strand'].astype(np.float32)
        arrays[name + '/lock'] = p['lock'].astype(np.int16)
        info['pieces'][name] = dict(family=p['family'], chains=p['chains'])
    arrays['meta'] = np.frombuffer(json.dumps(info).encode(), np.uint8)
    np.savez_compressed(path, **arrays)
    return path


def folds(V, T, outer, vn_env):
    """faces folded over: on the outer or the inner surface (the walls between them left out), a face turned against
    the normal its corners should have (vn_env: the envelope's, reversed on the inner surface) by more than 120 degrees,
    or one whose neighbours on average face the other way. A steep face (the inner surface dipping past an ear) is not
    a fold. -> count."""
    T = np.asarray(T)
    fo = outer[T]
    surf = fo.all(1) | ~fo.any(1)
    fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    fn /= np.linalg.norm(fn, axis=1, keepdims=True) + 1e-18
    ref = vn_env[T].mean(1)
    ref /= np.linalg.norm(ref, axis=1, keepdims=True) + 1e-18
    against = np.einsum('ij,ij->i', fn, ref) < -0.5
    E = np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]])
    f = np.tile(np.arange(len(T)), 3)
    key = np.sort(E, 1)
    o = np.lexsort((key[:, 1], key[:, 0]))
    key, f = key[o], f[o]
    same = np.all(key[1:] == key[:-1], axis=1)
    a, b = f[:-1][same], f[1:][same]
    d = np.einsum('ij,ij->i', fn[a], fn[b])
    tot = np.bincount(a, d, len(T)) + np.bincount(b, d, len(T))
    cnt = np.bincount(a, None, len(T)) + np.bincount(b, None, len(T))
    flipped = (cnt > 0) & (tot / np.maximum(cnt, 1) < 0)
    return int((surf & (against | flipped)).sum())


def shade_normals(pieces, L, style):
    """every piece's shading normals from the whole hair's envelope (charkit.geom.smooth.envelope_normals, as the geom
    hair's are): the union of the pieces as a solid, closed by the style's shade_close and blurred by shade_blur (L), the
    normal at each vertex the blurred field's gradient. The locks, the buns and the strands then shade as one mass, as
    anime hair does; their outlines tell them apart. In place (vn_shade)."""
    from .mesh import Mesh
    from .smooth import envelope_normals
    names = list(pieces)
    V = np.concatenate([pieces[n]['V'] for n in names])
    off = np.cumsum([0] + [len(pieces[n]['V']) for n in names])
    T = np.concatenate([np.asarray(pieces[n]['T']) + off[k] for k, n in enumerate(names)])
    close, blur = style.get('shade_close', 0.30) * L, style.get('shade_blur', 0.25) * L
    N = envelope_normals(Mesh(V, T), h=max(0.008, blur / 6.0) if L > 0.1 else blur / 6.0, close=close, blur=blur)
    w = style.get('lock_shading', 0.0)          # the locks' own normals blended in: their relief shades as drawn
    for k, n in enumerate(names):
        p = pieces[n]
        if p.get('own_normals'):                 # a template part (a block bun) shades with its own flat faces
            continue
        Ne = N[off[k]:off[k + 1]]
        if w > 0 and p.get('outer') is not None:
            # each lock's outer surface's own normal, smoothed within it (across outer edges only, so the walls' and
            # the ladder's facets don't crinkle the cel shading: its ridge and grooves are what's left), blended in
            out = p['outer']
            T_ = np.asarray(p['T'])
            G_ = geometric_normals(p['V'], T_)
            E = np.concatenate([T_[:, [0, 1]], T_[:, [1, 2]], T_[:, [2, 0]]])
            E = E[out[E[:, 0]] & out[E[:, 1]] & (p['lock'][E[:, 0]] == p['lock'][E[:, 1]])]
            for _ in range(style.get('lock_shading_smooth', 8)):
                acc = G_.copy()
                np.add.at(acc, E[:, 0], G_[E[:, 1]]); np.add.at(acc, E[:, 1], G_[E[:, 0]])
                G_ = acc / (np.linalg.norm(acc, axis=1, keepdims=True) + 1e-12)
            G_ = np.where((np.einsum('ij,ij->i', G_, Ne) < 0)[:, None], -G_, G_)
            Ne = np.where(out[:, None], (1 - w) * Ne + w * G_, Ne)
            Ne /= np.linalg.norm(Ne, axis=1, keepdims=True) + 1e-12
        p['vn_shade'] = Ne


def geometric_normals(V, T):
    fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    N = np.zeros_like(V)
    for i in range(3):
        np.add.at(N, T[:, i], fn)
    return N / (np.linalg.norm(N, axis=1, keepdims=True) + 1e-12)


def save_parts(R, out, meta=None):
    """the pieces as the Blender stage loads parts (charkit.geom.blender.load_part): out/NAME.npz per piece (V, F, vn:
    the shading normals for its custom normals (a lock shades its outside, inside and walls with the mass's outward
    normal: one cel-shaded mass, its locks told apart by their outlines), vn_geom, strand, lock; meta: family, chains,
    report) and
    out/pieces.json (the pieces in order, their families and files). -> pieces.json's path."""
    from .io import save_npz
    from .mesh import Mesh
    os.makedirs(out, exist_ok=True)
    index = dict(meta or {}, pieces=[], report=R['report'])
    for name, p in R['pieces'].items():
        path = os.path.join(out, name + '.npz')
        save_npz(Mesh(p['V'], p['T'], vn=p['vn_shade']), path,
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
