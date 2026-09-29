"""Pieces lofted through the visual hull's labelled points: a garment piece (a band, a skirt, a sleeve) as a radius field
r(t, theta) round its own axis, measured from the hull's points of that piece (charkit.geom.hull's per-vertex pieces,
bundle.target_pieces), smoothed and filled where no view shows it, then lofted into a clean quad grid. The piece's
construction (pleats, a stepped hem, gathers) is authored on top of the field by its builder (charkit.garments), so the
design's measured shape and the template's topology meet the way the head's sections and its cage do
(charkit.geom.headgeom). The shape comes from the hull, not the body: the body gives a piece its weights and, for a tight
shell, the surface under it.

Conventions (headgeom.Sections'): theta 0 toward the axis's front, increasing toward her left; t along the axis from its
origin (L or metres, as the points are).

    ax = Axis(origin, direction, front)
    t, th, r = ax.coords(P)
    F = field(t, th, r, ts, nth=96)          # -> Field(ts, th, R, measured)
    V, quads, uv = loft(ax, F)
"""
import numpy as np


class Axis:
    """a piece's axis: origin o, unit direction d (the piece's length runs along it: down a skirt, along an arm), and
    the front f (unit, perpendicular to d) where theta is 0. left = f x d (for a skirt: d down, f toward -y, left +x)."""

    def __init__(self, origin, direction, front):
        self.o = np.asarray(origin, float)
        d = np.asarray(direction, float)
        self.d = d / np.linalg.norm(d)
        f = np.asarray(front, float)
        f = f - self.d * (f @ self.d)
        self.f = f / np.linalg.norm(f)
        self.l = np.cross(self.f, self.d)

    def coords(self, P):
        """points -> (t along the axis, theta round it, r from it)."""
        q = np.asarray(P, float) - self.o
        t = q @ self.d
        a, b = q @ self.f, q @ self.l
        return t, np.arctan2(b, a), np.hypot(a, b)

    def point(self, t, th, r):
        """(t, theta, r) -> points."""
        t, th, r = (np.asarray(x, float) for x in (t, th, r))
        return (self.o + t[..., None] * self.d + (r * np.cos(th))[..., None] * self.f +
                (r * np.sin(th))[..., None] * self.l)


class Field:
    """a radius per row ts[i] and angle th[j] (R[i, j]), and which cells the points measured (the rest filled)."""

    def __init__(self, ts, th, R, measured):
        self.ts, self.th, self.R, self.measured = ts, th, R, measured

    def at(self, t, th):
        """the radius at (t, theta), bilinear (periodic in theta, clamped in t)."""
        t, th = np.broadcast_arrays(np.asarray(t, float), np.asarray(th, float))
        n = len(self.th)
        u = ((th - self.th[0]) / (2 * np.pi) * n) % n
        j0 = np.floor(u).astype(int) % n
        j1, fu = (j0 + 1) % n, u - np.floor(u)
        s = np.interp(t, self.ts, np.arange(len(self.ts)))
        i0 = np.clip(np.floor(s).astype(int), 0, len(self.ts) - 1)
        i1, ft = np.minimum(i0 + 1, len(self.ts) - 1), s - np.floor(s)
        R = self.R
        return ((1 - ft) * ((1 - fu) * R[i0, j0] + fu * R[i0, j1]) + ft * ((1 - fu) * R[i1, j0] + fu * R[i1, j1]))


def _fill_periodic(row):
    """a row's empty cells (NaN) filled by linear interpolation round the circle; None when it has fewer than two."""
    ok = np.isfinite(row)
    if ok.sum() < 2:
        return None
    n = len(row)
    x = np.arange(n)
    return np.interp(x, x[ok], row[ok], period=n)


def field(t, th, r, ts, nth=96, q=0.5, smooth=(1.0, 1.5), min_row=0.15):
    """the radius field of a piece's points: per cell (the row nearest each point's t, a theta sector) the q-quantile of
    their radii; a row whose cells are measured on at least min_row of the circle filled round it; rows without enough
    filled from their neighbours in t (clamped at the ends); then a Gaussian (smooth: sigma in rows, sigma in sectors;
    periodic round the circle). -> Field."""
    from scipy.ndimage import gaussian_filter1d
    ts = np.asarray(ts, float)
    th_c = -np.pi + (np.arange(nth) + 0.5) * 2 * np.pi / nth
    i = np.clip(np.rint(np.interp(t, ts, np.arange(len(ts)))).astype(int), 0, len(ts) - 1)
    j = np.clip(((th + np.pi) / (2 * np.pi) * nth).astype(int), 0, nth - 1)
    keep = (t >= ts[0] - 0.5 * (ts[1] - ts[0])) & (t <= ts[-1] + 0.5 * (ts[-1] - ts[-2])) if len(ts) > 1 else \
        np.ones(len(t), bool)
    R = np.full((len(ts), nth), np.nan)
    cell = i[keep] * nth + j[keep]
    rr = r[keep]
    order = np.argsort(cell, kind='stable')
    cell, rr = cell[order], rr[order]
    starts = np.r_[0, np.nonzero(np.diff(cell))[0] + 1]
    ends = np.r_[starts[1:], len(cell)]
    for a, b in zip(starts, ends):
        R.flat[cell[a]] = np.quantile(rr[a:b], q)
    measured = np.isfinite(R)
    rows_ok = measured.mean(1) >= min_row
    for k in range(len(ts)):
        if rows_ok[k]:
            R[k] = _fill_periodic(R[k])
        else:
            R[k] = np.nan
    good = np.nonzero(rows_ok)[0]
    if not len(good):
        raise ValueError('no row of the piece is measured on %.0f%% of its circle' % (100 * min_row))
    for jj in range(nth):
        R[:, jj] = np.interp(np.arange(len(ts)), good, R[good, jj])
    if smooth[1]:
        R = gaussian_filter1d(R, smooth[1], axis=1, mode='wrap')
    if smooth[0]:
        R = gaussian_filter1d(R, smooth[0], axis=0, mode='nearest')
    return Field(ts, th_c, R, measured)


def loft(ax, F, R=None, ts=None):
    """a quad grid through a field: rows ts (default the field's), one column per sector, closed round the axis.
    R: radii to use instead of the field's (a builder's modulated copy, same shape). -> (V (rows*cols, 3), quads (list of
    4-tuples), uv (u round from the back, v down the rows))."""
    ts = F.ts if ts is None else np.asarray(ts, float)
    R = F.R if R is None else R
    nt, nth = R.shape
    T, TH = np.meshgrid(ts, F.th, indexing='ij')
    V = ax.point(T, TH, R).reshape(-1, 3)
    quads = [(i * nth + j, i * nth + (j + 1) % nth, (i + 1) * nth + (j + 1) % nth, (i + 1) * nth + j)
             for i in range(nt - 1) for j in range(nth)]
    u = ((TH + np.pi) / (2 * np.pi)).reshape(-1)
    v = np.repeat((ts - ts[0]) / max(1e-12, ts[-1] - ts[0]), nth)
    return V, quads, np.c_[u, v]
