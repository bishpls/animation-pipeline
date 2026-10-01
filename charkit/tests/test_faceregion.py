"""The face region's pieces with known answers: the eye region's fill (charkit.geom.headfit.eye_fill), the neck's crease
measure (charkit.faceregion.crease_of) and the torso's top eased into the head's neck (charkit.code_base) (venv: run this
file, or pytest)."""
import math, os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import code_base, faceregion
from charkit.geom import headfit
from charkit.geom.headgeom import Sections

EYE_X = 0.168
W = dict(mode='window', a=0.12, b=0.11, zc=0.03, tan=0.5, reach=[0.2, 0.3], margin=0.03, hold=True,
         curve=2.0)


def _face(bulge=0.05):
    """a face's front as the head fit leaves it before the eye region, on the sections' grid (rows 0.004 L apart, columns
    from the midline round to the side): Clawd-like, a round front (y = 0.9 x^2, the midline 0.05 L forward of the eye's
    depth, the face at the eye 0.025 L forward of it) with a cheek under the eye standing `bulge` L further forward.
    -> zs, X, Y."""
    zs = np.arange(0.4, -0.45, -0.004)
    th = np.linspace(0, np.pi / 2, 65)
    x = 0.4 * np.sin(th)
    X = np.repeat(x[None], len(zs), 0)
    Y = np.stack([-0.05 + 0.9 * x ** 2 - bulge * np.exp(-0.5 * ((x - EYE_X) / 0.06) ** 2 - 0.5 * ((z + 0.12) / 0.05) ** 2)
                  for z in zs])
    return zs, X, Y


def _fill(face):
    zs, X, Y = face
    D = headfit.eye_fill(zs, X, Y, EYE_X, W)
    return X, np.repeat(zs[:, None], X.shape[1], 1), D, Y + D


def test_eye_fill_lays_the_opening_on_the_plane():
    X, Z, D, Yn = _fill(_face())
    core = np.hypot((X - EYE_X) / (W['a'] - W['margin'] / 2), (Z - W['zc']) / (W['b'] - W['margin'] / 2)) <= 1
    assert np.abs(Yn[core] - (X[core] - EYE_X) * W['tan']).max() < 1e-6


def test_eye_fill_leaves_the_midline_and_the_edges():
    X, Z, D, _ = _fill(_face())
    assert np.abs(D[:, 0]).max() == 0 and np.abs(D[:, -1]).max() == 0   # the midline (the profile's) and the side
    assert np.abs(D[Z[:, 0] > W['zc'] + W['b'] + W['reach'][0]]).max() == 0
    assert np.abs(D[Z[:, 0] < W['zc'] - W['b'] - W['reach'][1]]).max() == 0


def test_eye_fill_holds_the_cheek_behind_the_plane():
    """the cheek under the eye, 0.05 L proud of the face, is held behind the plane (within its allowance)."""
    X, Z, D, Yn = _fill(_face(0.05))
    rho = np.hypot((X - EYE_X) / W['a'], (Z - W['zc']) / W['b'])
    allow = W['curve'] * (np.maximum(0, rho - 1) * math.sqrt(W['a'] * W['b'])) ** 2
    held = (X >= EYE_X - W['a'] / 2) & (np.abs(Z - W['zc']) < W['b'] + 0.2)    # (toward the midline the hold lets go)
    assert (Yn - ((X - EYE_X) * W['tan'] - allow))[held].min() > -1e-3
    i, j = np.unravel_index(np.argmin(np.abs(X - EYE_X) + np.abs(Z + 0.12)), X.shape)
    assert D[i, j] > 0.03                                # the cheek went back


def _bowl(Y, n=6):
    """the deepest local hollow of a depth grid: how far a node sits behind the mean of its neighbours n nodes away,
    across or down."""
    cx = Y[:, n:-n] - 0.5 * (Y[:, :-2 * n] + Y[:, 2 * n:])
    cz = Y[n:-n] - 0.5 * (Y[:-2 * n] + Y[2 * n:])
    return max(np.nanmax(cx), np.nanmax(cz))


def test_eye_fill_leaves_no_bowl():
    """round the eye (from the nose's side to the temple, the brow to the cheek) the filled face has no hollow deeper
    than 0.01 L where the same face with a socket's dip (headfit.SOCKET's shape, 0.05 L deep) has one."""
    X, Z, D, Yn = _fill(_face(0.05))
    # resampled to an even (x, z) grid 0.01 L apart, as the QA's bowl reads the figure
    from scipy.interpolate import griddata
    xs, zs = np.arange(0.04, 0.3, 0.01), np.arange(0.2, -0.16, -0.01)
    gx, gz = np.meshgrid(xs, zs)
    at = lambda A: griddata((X.ravel(), Z.ravel()), A.ravel(), (gx, gz))
    assert _bowl(at(Yn)) < 0.01
    Yd = Yn - D + 0.05 * np.exp(-0.5 * ((X - EYE_X) / headfit.SOCKET[0]) ** 2 - 0.5 * (Z / headfit.SOCKET[1]) ** 2)
    assert _bowl(at(Yd)) > 0.02


def test_eye_fill_is_smooth():
    """no ring round the window: the correction's second differences stay small everywhere on the face."""
    X, Z, D, Yn = _fill(_face(0.05))
    hx, hz = np.diff(X[0]), abs(Z[1, 0] - Z[0, 0])
    dxx = np.abs(np.diff(D, 2, axis=1)) / (hx[1:] * hx[:-1])
    dzz = np.abs(np.diff(D, 2, axis=0)) / hz ** 2
    assert max(dxx.max(), dzz.max()) < 40.0              # 1/L: a radius of curvature over 0.025 L


def _tris(nrows, ncols):
    """a closed band of rows (each ncols vertices round the axis) as triangles."""
    T = []
    for i in range(nrows - 1):
        for j in range(ncols):
            a, b = i * ncols + j, i * ncols + (j + 1) % ncols
            T += [(a, b, a + ncols), (b, b + ncols, a + ncols)]
    return np.array(T)


def _neck(bump=0.0, flare=True, step=0.005, steep=False):
    """a body of revolution round the z axis, rows `step` L apart: a neck of radius 0.12 flaring into shoulders below
    z = -0.55 (steep: as our join does, its outline turning smoothly from vertical to 70 degrees over 0.08 L: the slope
    a smoothstep), with a ring `bump` L proud at the cut (z = -0.52) -> (V, T)."""
    th = np.linspace(-np.pi, np.pi, 180, endpoint=False)
    V = []
    zs = np.arange(-0.3, -0.8, -step)
    k, w = math.tan(math.radians(70)), 0.08
    for z in zs:
        d = max(0.0, -0.55 - z)
        x = min(d / w, 1.0)
        fl = (0.25 * d ** 1.5 if not steep else k * (w * (x ** 3 - x ** 4 / 2) + max(0.0, d - w))) if flare else 0.0
        r = 0.12 + fl + bump * math.exp(-0.5 * ((z + 0.52) / 0.006) ** 2)
        V.append(np.stack([np.sin(th) * r, -np.cos(th) * r, np.full(len(th), z)], 1))
    return np.concatenate(V), _tris(len(zs), len(th))


def test_crease_reads_a_ring_not_a_flare():
    c = np.array([0.0, 0.0, 0.0])
    smooth = faceregion.crease_of(*_neck(), c, 1.0)
    ring = faceregion.crease_of(*_neck(0.02), c, 1.0)
    assert smooth['max'] < faceregion.CREASE[0]
    assert ring['max'] > faceregion.CREASE[1]


def test_crease_reads_the_surface_not_its_rows():
    """a steep smooth flare (our join's: vertical to 70 degrees within 0.08 L) reads the same with rows 0.019 L apart
    (the torso's subdivided rows) as with rows 0.004 L apart, and passes; with a ring at the cut it fails either way.
    (The vertex measure read the coarse rows' corners on the steep flare: two heights catching one row read flat, then
    a jump.)"""
    c = np.zeros(3)
    fine = faceregion.crease_of(*_neck(steep=True, step=0.004), c, 1.0)
    coarse = faceregion.crease_of(*_neck(steep=True, step=0.019), c, 1.0)
    assert fine['max'] < faceregion.CREASE[0] and coarse['max'] < faceregion.CREASE[0]
    assert abs(fine['max'] - coarse['max']) < 6
    assert faceregion.crease_of(*_neck(0.02, steep=True, step=0.004), c, 1.0)['max'] > faceregion.CREASE[1]


def test_crease_reads_no_bend_across_a_mask_gap():
    """the flare with a V cut out of its front (the garments' mask: an edge crossing the columns diagonally, as the
    opened neckline's does) reads as the whole surface does: a column is read on its unbroken runs, never across the
    gap or past a run's end."""
    c = np.zeros(3)
    V, T = _neck(steep=True, step=0.01)
    whole = faceregion.crease_of(V, T, c, 1.0)
    th = np.arctan2(V[:, 0], -V[:, 1])
    hidden = (V[:, 2] < -0.47) & (np.abs(th) > np.radians(12) + 1.5 * (-0.47 - V[:, 2]))   # the V: wider going down
    Tm = T[~hidden[T].any(1)]
    masked = faceregion.crease_of(V, Tm, c, 1.0)
    assert masked['max'] < faceregion.CREASE[0]
    assert masked['max'] <= whole['max'] + 1.0


def _surface(rows, th):
    """rows [(z, r (len(th),))] round the z axis -> (V, T)."""
    V = np.concatenate([np.stack([np.sin(th) * r, -np.cos(th) * r, np.full(len(th), z)], 1) for z, r in rows])
    return V, _tris(len(rows), len(th))


def test_neck_join_is_one_curve():
    """the head's neck (radius 0.12) lofted into a torso ring of 0.26, NECK_BASE under the cut, that flares at 1 L per L:
    each column leaves the head with the head's slope and lands on the ring with the ring's, with no waist or bulge
    between, and the outline turns with less of a bend than the old flat easing into a wide top ring left."""
    zs = np.arange(0.4, -0.7, -0.004)
    N = Sections.N
    S = Sections(zs, np.zeros(len(zs)), np.full((len(zs), N), 0.12))
    cut, width, base = code_base.CUT, code_base.NECK_BLEND, code_base.NECK_BASE
    z_low = cut - base
    f = code_base.neck_curve(S, cut + width, (z_low, np.full(N, 0.26), np.full(N, -1.0)))
    zz = np.arange(cut + width, z_low - 1e-9, -0.004)
    r = np.array([f(z)[0] for z in zz])
    assert abs(r[0] - 0.12) < 1e-6 and abs(r[-1] - 0.26) < 1e-6
    assert abs((r[1] - r[0]) / 0.004) < 0.1                               # the head's (flat) slope at the top
    assert abs((r[-1] - r[-2]) / 0.004 - 1.0) < 0.1                       # the ring's at the bottom
    assert (np.diff(r) >= -1e-12).all()                                   # widening all the way: no waist
    below = [(z, np.full(N, 0.26 + (z_low - z))) for z in np.arange(z_low - 0.004, z_low - 0.3, -0.004)]
    head = [(z, S.r[i]) for i, z in enumerate(zs) if z > cut + width]
    K = faceregion.crease_of(*_surface(head + [(z, np.full(N, v)) for z, v in zip(zz, r)] + below, S.th), np.zeros(3), 1.0)
    assert K['max'] < faceregion.CREASE[0]
    # the old join: the head eased flat into a top ring at the cut as wide as the torso gets 0.06 L lower
    ring = 0.26 - (base - 0.06)
    flat = code_base.blend_neck(S, cut, 0.0, np.full(N, ring))
    kf = [i for i in range(len(zs)) if np.isfinite(flat.cy[i]) and zs[i] >= cut]
    old = [(zs[i], flat.r[i]) for i in kf] + [(z, np.full(N, ring + (cut - z) * (0.26 - ring) / base))
                                            for z in np.arange(cut - 0.004, z_low, -0.004)] + below
    assert faceregion.crease_of(*_surface(old, S.th), np.zeros(3), 1.0)['max'] > K['max'] + 3


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok', name)
