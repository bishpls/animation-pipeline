"""The authored head's geometry, apart from how it's fitted to the design (charkit/geom/headfit.py): its sections, the
placement of chart points on them, the cage on the head's own chart (charkit.geom.headmesh.cylinder), and a fitted mesh's
health. The build's side (charkit/code_base.py, in Blender) reads only this and headmesh: the fitting reads the reference
images and the QA's measures, which a build stage mustn't depend on (charkit.cache: a QA edit would invalidate it)."""
import numpy as np

class Sections:
    """the head as one closed section per row: its radius r[k, j] at angle TH[j] round the row's centre (0, cy[k]),
    angle 0 toward the front (-y) and increasing toward her left (+x). zs descend (the skull's grid rows)."""
    N = 256

    def __init__(self, zs, cy, r):
        self.zs, self.cy, self.r = zs, cy, r
        self.th = np.linspace(-np.pi, np.pi, self.N, endpoint=False)

    def xy(self, k):
        return np.sin(self.th) * self.r[k], self.cy[k] - np.cos(self.th) * self.r[k]

    def solid(self, A):
        """the sections as occupancy on A's grid (A.zs must be the sections' rows)."""
        X, Yg = np.meshgrid(A.xs, A.ys, indexing='ij')
        V = np.zeros((len(A.xs), len(A.ys), len(self.zs)), bool)
        for k in range(len(self.zs)):
            if not np.isfinite(self.r[k]).all() or self.r[k].max() <= 0:
                continue
            dx, dy = X, Yg - self.cy[k]
            th = np.arctan2(dx, -dy)
            rr = np.interp(th, self.th, self.r[k], period=2 * np.pi)
            V[:, :, k] = np.hypot(dx, dy) <= rr
        return V

def _smooth_rows(v, sigma):
    """a Gaussian over rows (sigma in rows) of a series with NaNs (weights renormalised)."""
    from scipy.ndimage import gaussian_filter1d
    ok = np.isfinite(v)
    num = gaussian_filter1d(np.where(ok, v, 0.0), sigma)
    den = gaussian_filter1d(ok.astype(float), sigma)
    return np.where(ok, num / np.maximum(den, 1e-9), np.nan)

def _smoothstep(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)

def _row_at(S, z):
    """the sections interpolated to height z -> (cy, r (N,)) or None outside them."""
    ok = np.isfinite(S.cy) & np.isfinite(S.r).all(1)
    zs = S.zs[ok]
    if not (zs.min() <= z <= zs.max()):
        return None
    i = np.clip(np.searchsorted(-zs, -z), 1, len(zs) - 1)
    t = (zs[i - 1] - z) / (zs[i - 1] - zs[i])
    return (1 - t) * S.cy[ok][i - 1] + t * S.cy[ok][i], (1 - t) * S.r[ok][i - 1] + t * S.r[ok][i]

def place(S, theta, z):
    """chart points (theta round the head, 0 the front; z) onto the sections' surface -> (N, 3)."""
    out = np.full((len(theta), 3), np.nan)
    for zz in np.unique(z):
        row = _row_at(S, zz)
        if row is None:
            continue
        cy, r = row
        sel = z == zz
        rr = np.interp(theta[sel], S.th, r, period=2 * np.pi)
        out[sel] = np.stack([np.sin(theta[sel]) * rr, cy - np.cos(theta[sel]) * rr, np.full(sel.sum(), zz)], 1)
    return out

def theta_of(S, x, z):
    """the front angle at which the surface at height z reaches front-view x."""
    row = _row_at(S, z)
    cy, r = row
    front = np.abs(S.th) <= np.pi / 2
    xs = np.sin(S.th[front]) * r[front]
    o = np.argsort(xs)
    return float(np.interp(x, xs[o], S.th[front][o]))

def _inside(S, P):
    """points (N, 3) inside the sections' solid (each row's polar outline round its centre; rows interpolated)."""
    zs = S.zs
    k = np.clip(np.searchsorted(-zs, -P[:, 2]), 1, len(zs) - 1)       # zs descend
    t = np.clip((zs[k - 1] - P[:, 2]) / (zs[k - 1] - zs[k]), 0, 1)
    out = np.zeros(len(P), bool)
    valid = np.nonzero(np.isfinite(S.cy) & np.isfinite(S.r).all(1))[0]
    within = (P[:, 2] <= zs[valid[0]]) & (P[:, 2] >= zs[valid[-1]])   # above the top row or under the last: outside
    ok = np.isfinite(S.cy[k - 1]) & np.isfinite(S.cy[k]) & within
    cy = np.where(ok, (1 - t) * S.cy[k - 1] + t * S.cy[k], np.nan)
    dx, dy = P[:, 0], P[:, 1] - cy
    th = np.arctan2(dx, -np.nan_to_num(dy))
    j = np.round((th + np.pi) / (2 * np.pi) * len(S.th)).astype(int) % len(S.th)
    rr = (1 - t) * S.r[k - 1, j] + t * S.r[k, j]
    out[ok] = (np.hypot(dx, dy) <= rr)[ok]
    return out

def project(S, origins, dirs, reach=1.2, step=0.002):
    """each ray (origin inside the head, direction) marched out to where it leaves the sections' solid -> (N, 3)."""
    d = dirs / np.maximum(np.linalg.norm(dirs, axis=1, keepdims=True), 1e-12)
    ts = np.arange(0, reach, step)
    last = np.zeros(len(origins))
    for t in ts:
        ins = _inside(S, origins + t * d)
        last = np.where(ins, t, last)
    return origins + last[:, None] * d

def front_point(S, x, z):
    """the surface's front point at front-view (x, z) (arrays): per row, the angle where the outline reaches x."""
    zs = S.zs
    out = np.full((len(x), 3), np.nan)
    for i, (xx, zz) in enumerate(zip(x, z)):
        k = int(np.argmin(np.abs(zs - zz)))
        if not np.isfinite(S.cy[k]):
            continue
        front = np.abs(S.th) <= np.pi / 2
        xs = np.sin(S.th[front]) * S.r[k, front]
        ys = S.cy[k] - np.cos(S.th[front]) * S.r[k, front]
        o = np.argsort(xs)
        if xs.min() <= xx <= xs.max():
            out[i] = (xx, np.interp(xx, xs[o], ys[o]), zz)
    return out

def sections_mesh(S, step=2):
    """the sections as a closed-top mesh: rows of the (angle, height) grid joined as quads (split to triangles), the top
    closed by a fan to its centre, the bottom (the neck) open -> Mesh."""
    from .mesh import Mesh
    rows = [k for k in range(0, len(S.zs), step) if np.isfinite(S.cy[k]) and np.isfinite(S.r[k]).all()]
    n = len(S.th)
    V = []
    for k in rows:
        x, y = S.xy(k)
        V.append(np.stack([x, y, np.full(n, S.zs[k])], 1))
    V = np.concatenate(V + [[[0.0, S.cy[rows[0]], S.zs[rows[0]]]]])
    F = []
    for i in range(len(rows) - 1):
        a, b = i * n, (i + 1) * n
        for j in range(n):
            j1 = (j + 1) % n
            F += [[a + j, b + j, b + j1], [a + j, b + j1, a + j1]]
    top = len(V) - 1
    F += [[top, j, (j + 1) % n] for j in range(n)]
    m = Mesh(V, np.array(F))
    from .mesh import signed_volume
    if signed_volume(m.V, m.F) < 0:
        m.F = m.F[:, ::-1]
    return m

def quality(V, F, O=None):
    """a fitted quad mesh's health: faces flipped against the way out (each face's normal against the direction from its
    rays' origins, or from the mesh's centroid), and each quad's worst corner (the smallest signed sine of its four
    corners in its own plane: 1 a square, 0 a degenerate corner, < 0 a folded one) -> dict."""
    P = V[F]
    n = np.cross(P[:, 2] - P[:, 0], P[:, 3] - P[:, 1])
    c = P.mean(1)
    out = c - (O[F].mean(1) if O is not None else V.mean(0))
    flipped = (np.einsum('ij,ij->i', n, out) < 0)
    nn = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    worst = np.full(len(F), np.inf)
    for i in range(4):
        a, b, d = P[:, i], P[:, (i + 1) % 4], P[:, (i - 1) % 4]
        e1, e2 = b - a, d - a
        s = np.einsum('ij,ij->i', np.cross(e1, e2), nn) / np.maximum(np.linalg.norm(e1, axis=1) * np.linalg.norm(e2, axis=1), 1e-12)
        worst = np.minimum(worst, s)
    return {'faces': len(F), 'flipped': int(flipped.sum()), 'folded_corners': int((worst < 0).sum()),
            'corner_p05': round(float(np.percentile(worst, 5)), 3), 'corner_min': round(float(worst.min()), 3),
            'flipped_idx': np.nonzero(flipped | (worst < 0))[0]}

def _neighbours(F, n):
    """vertex adjacency of a quad mesh -> (indices (E,), offsets (n + 1,)) in CSR form."""
    E = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 3]], F[:, [3, 0]]])
    E = np.unique(np.sort(np.concatenate([E, E[:, ::-1]]), 1), axis=0)
    E = np.concatenate([E, E[:, ::-1]])
    o = np.argsort(E[:, 0], kind='stable')
    E = E[o]
    off = np.searchsorted(E[:, 0], np.arange(n + 1))
    return E[:, 1], off

def _harmonic(values, fixed, nb, off, iters=300):
    """values (n, k) relaxed to the mean of their neighbours where not fixed (Jacobi iterations)."""
    V = values.copy()
    deg = np.diff(off)
    owner = np.repeat(np.arange(len(V)), deg)
    free = ~fixed
    for _ in range(iters):
        acc = np.zeros_like(V)
        np.add.at(acc, owner, V[nb])
        mean = acc / np.maximum(deg, 1)[:, None]
        V[free] = mean[free]
    return V

def _near(mask, nb, off, k):
    """the vertices within k rings of a mask."""
    out = mask.copy()
    owner = np.repeat(np.arange(len(mask)), np.diff(off))
    for _ in range(k):
        grow = np.zeros(len(mask), bool)
        grow[owner[out[nb]]] = True
        out |= grow
    return out

EYE_GAP = 0.035          # L between an eye's outline and its block's edge: room for its rings (0.012 L apart at 3)
EYE_BLOCK = (0.135, 0.09)   # the eye block's least half-width and half-height (L), round the eye centre


def cylinder_cage(S, C, nth=64, dz=0.03, z_top=0.25, z_bottom=-0.6, dome=7, eye_w=0.21, eye_h=0.13, mouth_w=0.12,
                  mouth_h=0.03, rings=(3, 2), caps=True, eye_outline=None):
    """the authored cage on the head's own chart (charkit.geom.headmesh.cylinder): rows of the sections from z_top down
    the neck, a dome of rays from the head's centre above, the eyes' and the mouth's blocks where the front view draws
    them. eye_outline: her left eye's opening (K, 2) in L round its centre (x outward, z up; charkit.eyes.
    outline_polygon), the right's mirrored: the lid margin's loop is authored on it, and each eye's block grows to
    hold it with EYE_GAP for the rings; None: an almond eye_w x eye_h. -> (Cage, the dome's centre)."""
    from . import headmesh as hm
    ex, mz = C['eye_x'], C['nose_z'] - 0.11
    mh = 0.045
    if eye_outline is None:
        a = np.linspace(0, 2 * np.pi, 64, endpoint=False)
        eye_outline = np.stack([eye_w / 2 * np.cos(a), eye_h / 2 * np.sin(a) * (1 + 0.15 * np.cos(a))], 1)
    eo = np.asarray(eye_outline, float)
    bw = max(EYE_BLOCK[0], np.abs(eo[:, 0]).max() + EYE_GAP)
    bt, bb = max(EYE_BLOCK[1], eo[:, 1].max() + EYE_GAP), max(EYE_BLOCK[1], -eo[:, 1].min() + EYE_GAP)
    zs = hm.lines(z_bottom, z_top, dz, must=[-bb, bt, mz - mh, mz + mh])[::-1]
    th = 2 * np.pi * np.arange(nth) / nth - np.pi
    col = lambda t: int(np.argmin(np.abs(th - t)))
    row = lambda z: int(np.argmin(np.abs(zs - z)))
    okr = np.isfinite(S.cy)
    ctr = np.array([0.0, float(np.interp(-z_top, -S.zs[okr], S.cy[okr])), z_top])

    def dome_place(t, phi):
        d = np.stack([np.sin(t) * np.cos(phi), -np.cos(t) * np.cos(phi), np.sin(phi)], 1)
        return project(S, np.repeat(ctr[None], len(t), 0), d)

    def almond(cx, cz, w, h, n=64):
        a = np.linspace(0, 2 * np.pi, n, endpoint=False)
        return np.stack([cx + w / 2 * np.cos(a), cz + h / 2 * np.sin(a) * (1 + 0.15 * np.cos(a))], 1)

    def chart(outline):
        return np.array([(theta_of(S, x, z), z) for x, z in outline])
    def radius(z):
        cy, r = _row_at(S, z)
        return float(r[int(np.argmin(np.abs(S.th)))])
    feats = []
    for name, cx, sd in (('eye_L', ex, 1.0), ('eye_R', -ex, -1.0)):
        j0, j1 = sorted((col(theta_of(S, cx - bw, 0.0)), col(theta_of(S, cx + bw, 0.0))))
        feats.append(dict(name=name, block=(j0, j1, row(bt), row(-bb)), outline_tz=chart(np.stack([cx + sd * eo[:, 0], eo[:, 1]], 1)),
                          rings=rings[0], theta_scale=radius(0.0), cap=caps))
    j0, j1 = col(theta_of(S, -0.09, mz)), col(theta_of(S, 0.09, mz))
    feats.append(dict(name='mouth', block=(j0, j1, row(mz + mh), row(mz - mh)), outline_tz=chart(almond(0.0, mz, mouth_w, mouth_h)),
                      rings=rings[1], theta_scale=radius(mz), cap=caps))
    Cg = hm.cylinder(nth, zs, dome, lambda t, z: place(S, t, z), dome_place, feats)
    # each vertex's way out, for checking the fit: from the head's axis at its height, or the dome's centre above it
    O = np.stack([np.zeros(len(Cg.V)), np.interp(-np.minimum(Cg.V[:, 2], z_top), -S.zs[okr], S.cy[okr]),
                  np.minimum(Cg.V[:, 2], z_top)], 1)
    Cg.origins = O
    return Cg, ctr
