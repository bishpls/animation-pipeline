"""Soft silhouettes with analytic gradients with respect to vertex positions (docs/workstreams/softras.md; the roadmap's
"differentiable silhouettes", hand-rolled: nvdiffrast is non-commercial). numpy + numba, no GPU, no new dependency.

What a pixel's soft coverage is. The hard silhouette C is the QA's: a pixel is covered when its centre is inside a
triangle (charkit.geom.raster._raster, the same kernel, the same tie tolerance). The soft one moves only the pixels near
the silhouette's contour: F(p) = k(sign(p) d(p) / s), where d(p) is the distance from p's centre to the nearest
contour segment, sign(p) is +1 where C covers p and -1 elsewhere, s is the softness (pixels) and k a step (the logistic
k(x) = 1 / (1 + exp(-4 x)), or 'linear': clip(0.5 + x, 0, 1), which at s = 1 is about a box filter's area coverage).
Every other pixel keeps C. So F is C where s -> 0 (every pixel with d > 0), and between, F is a smooth function of the
contour's vertices: dF/dvertex = k'(x) sign / s * dd/dvertex, analytic (d is a point-to-segment distance).

Why the contour and not SoftRas's per-triangle aggregation (1 - prod_j (1 - D_j), D_j a sigmoid of the distance to
triangle j): there every edge between two triangles is a soft edge too, so the silhouette's inside dips along each
internal edge (to 0.75 on it). A dense template at the QA's scale has triangles a few pixels across, and its interior
comes out far below 1 (measured on the flap: `aggregate` below, the numbers in the notes). The contour is the union's
own boundary, so the interior stays exactly 1.

Finding the contour: for every covered pixel p beside an uncovered one q (4-neighbours; hidden pixels, where an occluder
is nearer, don't count), the segment from p's centre to q's is walked through the union of the triangles over the two
pixels (each triangle's interval along it, chained from p): where the union ends is a contour point, on the edge of the
triangle it leaves through. Each such edge is kept over the part of it the contour points span (plus `margin` px at
each end: consecutive points along an edge are at most ~1.4 px apart), so an edge that runs on inside the union (a fold,
a shell's inner rim) isn't taken for contour there. Occlusion: an occluder's depth per pixel (occ, the nearest other
surface) hides the mesh where it is nearer; that boundary moves only with depth and is not differentiated (it stays
hard: the notes' "where the objective is non-smooth").

    view = softras.SheetView(az, origin, L, 1 / ppl, WIN)          # the QA's window (geom.raster.window_project)
    view = softras.CameraView(views.camera(board_view))            # charkit.render's camera (glTF frame)
    S = softras.silhouette(V, tris, view, s=0.5, occ=depth)        # S.cov in [0, 1], S.hard: a crop round the mesh (S.box)
    iou, g = S.iou(mask)                                           # a whole-view mask; g = d iou / d cov
    dV = S.backward(-g)                                            # d(1 - iou) / dV, (N, 3)
"""
import math

import numba as nb
import numpy as np

from charkit.geom.raster import _raster, window_project, window_shape

KERNELS = ('sigmoid', 'linear')
REACH = 3.0             # sigmoid: pixels beyond REACH * s from the contour keep C (k(-4 REACH) = 6e-6)
MARGIN = 1.5            # px: an edge is kept this far past the contour points found on it


# ------------------------------------------------------------------------------------------------------------ cameras
class SheetView:
    """the QA's measuring window (charkit.geom.raster.window_project: orthographic at azimuth az, Blender's frame; pixel
    (r, c) spans u in [c pix - win.x, (c + 1) pix - win.x) L round origin). Its Jacobian is one constant 2 x 3."""

    def __init__(self, az, origin, L, pix, win):
        self.az, self.origin, self.L, self.pix, self.win = float(az), tuple(origin), float(L), float(pix), dict(win)
        self.W, self.H = window_shape(pix, win)
        a, k = math.radians(az), 1.0 / (L * pix)
        self.J = np.array([[math.cos(a) * k, math.sin(a) * k, 0.0], [0.0, 0.0, -k]])

    @property
    def shape(self):
        return self.H, self.W

    def project(self, V):
        """-> (pixel xy (N, 2), depth (N,) smaller nearer)."""
        return window_project(V, self.az, self.origin, self.L, self.pix, self.win)

    def pullback(self, V, g2):
        """d/d(pixel xy) (N, 2) -> d/dV (N, 3)."""
        return g2 @ self.J


class CameraView:
    """charkit.render's camera (charkit.render.views.camera: view and projection matrices, glTF frame, WebGPU clip
    space): pixel x = (ndc x + 1) / 2 W, y = (1 - ndc y) / 2 H, pixel centres at + 0.5, as the rasteriser samples them.
    blender=True takes vertices in Blender's frame (converted by model.C3). Perspective or orthographic."""

    def __init__(self, cam, blender=False):
        self.cam = cam
        self.W, self.H = cam.res
        from .model import C3
        self.M = cam.viewproj @ (np.block([[C3, np.zeros((3, 1))], [np.zeros((1, 3)), np.ones((1, 1))]]) if blender
                                 else np.eye(4))
        self.Vm = cam.view @ (np.block([[C3, np.zeros((3, 1))], [np.zeros((1, 3)), np.ones((1, 1))]]) if blender
                              else np.eye(4))

    @property
    def shape(self):
        return self.H, self.W

    def project(self, V):
        V = np.asarray(V, float)
        c = V @ self.M[:, :3].T + self.M[:, 3]
        x = (c[:, 0] / c[:, 3] + 1) / 2 * self.W
        y = (1 - c[:, 1] / c[:, 3]) / 2 * self.H
        depth = -(V @ self.Vm[2, :3] + self.Vm[2, 3])                  # distance along the view (camera looks down -z)
        return np.stack([x, y], 1), depth

    def pullback(self, V, g2):
        V = np.asarray(V, float)
        c = V @ self.M[:, :3].T + self.M[:, 3]
        w = c[:, 3:4]
        Mx, My, Mw = self.M[0, :3], self.M[1, :3], self.M[3, :3]
        dx = (Mx[None] * w - c[:, 0:1] * Mw[None]) / w ** 2 * (self.W / 2)          # (N, 3)
        dy = -(My[None] * w - c[:, 1:2] * Mw[None]) / w ** 2 * (self.H / 2)
        return g2[:, 0:1] * dx + g2[:, 1:2] * dy


# ------------------------------------------------------------------------------------------------------------ kernels
@nb.njit(cache=True)
def _bins(P2, F, W, H):
    """the triangles over each pixel cell [x, x + 1) x [y, y + 1) (their bounding boxes'): CSR (start (W H + 1), tris)."""
    n = F.shape[0]
    cnt = np.zeros(W * H + 1, np.int64)
    for t in range(n):
        x0, x1, y0, y1, ok = _box(P2, F, t, W, H)
        if not ok:
            continue
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                cnt[y * W + x + 1] += 1
    for i in range(W * H):
        cnt[i + 1] += cnt[i]
    tris = np.empty(cnt[W * H], np.int64)
    pos = cnt[:-1].copy()
    for t in range(n):
        x0, x1, y0, y1, ok = _box(P2, F, t, W, H)
        if not ok:
            continue
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                tris[pos[y * W + x]] = t
                pos[y * W + x] += 1
    return cnt, tris


@nb.njit(cache=True)
def _box(P2, F, t, W, H):
    a, b, c = F[t, 0], F[t, 1], F[t, 2]
    xs = (P2[a, 0], P2[b, 0], P2[c, 0])
    ys = (P2[a, 1], P2[b, 1], P2[c, 1])
    for v in xs + ys:
        if not math.isfinite(v):
            return 0, 0, 0, 0, False
    x0 = int(math.floor(min(xs))); x1 = int(math.floor(max(xs)))
    y0 = int(math.floor(min(ys))); y1 = int(math.floor(max(ys)))
    if x1 < 0 or y1 < 0 or x0 >= W or y0 >= H:
        return 0, 0, 0, 0, False
    return max(0, x0), min(W - 1, x1), max(0, y0), min(H - 1, y1), True


@nb.njit(cache=True)
def _interval(P2, F, t, px, py, ex, ey):
    """the segment X(u) = p + u e inside triangle t: (a, b, the edge it leaves through (0, 1, 2: corner k to k + 1), ok)."""
    i0, i1, i2 = F[t, 0], F[t, 1], F[t, 2]
    ax, ay, bx, by, cx, cy = P2[i0, 0], P2[i0, 1], P2[i1, 0], P2[i1, 1], P2[i2, 0], P2[i2, 1]
    area = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    if not (abs(area) > 1e-12):
        return 0.0, 0.0, -1, False
    o = 1.0 if area > 0 else -1.0
    lo, hi, kx = -1e300, 1e300, -1
    for k in range(3):
        if k == 0:
            qx, qy, rx, ry = ax, ay, bx, by
        elif k == 1:
            qx, qy, rx, ry = bx, by, cx, cy
        else:
            qx, qy, rx, ry = cx, cy, ax, ay
        dx, dy = rx - qx, ry - qy
        f0 = o * (dx * (py - qy) - dy * (px - qx))
        f1 = o * (dx * ey - dy * ex)
        if abs(f1) < 1e-15:
            if f0 < -1e-12:
                return 0.0, 0.0, -1, False
            continue
        u = -f0 / f1
        if f1 > 0:
            if u > lo:
                lo = u
        else:
            if u < hi:
                hi = u; kx = k
    if hi <= lo or kx < 0:
        return 0.0, 0.0, -1, False
    return lo, hi, kx, True


@nb.njit(cache=True)
def _crossings(P2, F, start, tris, cov, vis, W, H):
    """the contour points: for every visible pixel p beside a pixel q no triangle covers, where the union of the
    triangles over p and q ends along the segment from p's centre to q's. -> (n, 4) float rows (x, y (the point),
    triangle, edge) and the edge's global vertex ids (n, 2)."""
    cap = 0
    for y in range(H):
        for x in range(W):
            if vis[y, x]:
                cap += 4
    out = np.empty((cap, 4))
    ev = np.empty((cap, 2), np.int64)
    n = 0
    A = np.empty(512); B = np.empty(512); T = np.empty(512, np.int64); K = np.empty(512, np.int64)
    for y in range(H):
        for x in range(W):
            if not vis[y, x]:
                continue
            for d in range(4):
                dx = 1 if d == 0 else (-1 if d == 1 else 0)
                dy = 1 if d == 2 else (-1 if d == 3 else 0)
                qx, qy = x + dx, y + dy
                if qx < 0 or qy < 0 or qx >= W or qy >= H or cov[qy, qx]:
                    continue
                px, py = x + 0.5, y + 0.5
                m = 0
                for cell in (y * W + x, qy * W + qx):
                    for j in range(start[cell], start[cell + 1]):
                        if m >= 512:
                            break
                        a, b, k, ok = _interval(P2, F, tris[j], px, py, float(dx), float(dy))
                        if ok and b > 0.0 and a < 1.0:
                            A[m] = a; B[m] = b; T[m] = tris[j]; K[m] = k
                            m += 1
                cur, bt, bk = 0.0, -1, -1
                for i in range(m):                                 # the triangle(s) covering p's centre
                    if A[i] <= 1e-7 and B[i] > cur:
                        cur = B[i]; bt = T[i]; bk = K[i]
                if bt < 0:
                    continue
                more = True
                while more:                                        # chained through the triangles it runs on into
                    more = False
                    for i in range(m):
                        if A[i] <= cur + 1e-7 and B[i] > cur + 1e-12:
                            cur = B[i]; bt = T[i]; bk = K[i]; more = True
                if cur >= 1.0 - 1e-9:
                    continue
                out[n, 0] = px + cur * dx; out[n, 1] = py + cur * dy; out[n, 2] = bt; out[n, 3] = bk
                ev[n, 0] = F[bt, bk]; ev[n, 1] = F[bt, (bk + 1) % 3]
                n += 1
    return out[:n], ev[:n]


@nb.njit(cache=True)
def _sdf(P2, EA, EB, U0, U1, W, H, R, dmin, eid, ucl):
    """each pixel within R of a contour segment: its distance to the nearest (dmin), which (eid), and where on it (ucl,
    the parameter from EA to EB)."""
    for e in range(EA.shape[0]):
        ax, ay, bx, by = P2[EA[e], 0], P2[EA[e], 1], P2[EB[e], 0], P2[EB[e], 1]
        dx, dy = bx - ax, by - ay
        l2 = dx * dx + dy * dy
        sx, sy = ax + U0[e] * dx, ay + U0[e] * dy
        tx, ty = ax + U1[e] * dx, ay + U1[e] * dy
        x0 = max(0, int(math.floor(min(sx, tx) - R - 0.5))); x1 = min(W - 1, int(math.ceil(max(sx, tx) + R - 0.5)))
        y0 = max(0, int(math.floor(min(sy, ty) - R - 0.5))); y1 = min(H - 1, int(math.ceil(max(sy, ty) + R - 0.5)))
        for y in range(y0, y1 + 1):
            Y = y + 0.5
            for x in range(x0, x1 + 1):
                X = x + 0.5
                u = ((X - ax) * dx + (Y - ay) * dy) / l2 if l2 > 1e-18 else 0.0
                u = min(U1[e], max(U0[e], u))
                cx, cy = ax + u * dx, ay + u * dy
                dd = math.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
                if dd <= R and dd < dmin[y, x]:
                    dmin[y, x] = dd; eid[y, x] = e; ucl[y, x] = u


@nb.njit(cache=True)
def _back(P2, EA, EB, eid, ucl, dmin, cov, g, s, linear, out):
    """d loss / d (pixel xy) of the contour's vertices, from g = d loss / d F per pixel (visibility applied)."""
    H, W = eid.shape
    for y in range(H):
        for x in range(W):
            e = eid[y, x]
            if e < 0 or g[y, x] == 0.0:
                continue
            d = dmin[y, x]
            if d < 1e-12:
                continue
            sg = 1.0 if cov[y, x] else -1.0
            xx = sg * d / s
            if linear:
                dk = 1.0 if abs(xx) < 0.5 else 0.0
            else:
                f = 1.0 / (1.0 + math.exp(-4.0 * xx))
                dk = 4.0 * f * (1.0 - f)
            w = g[y, x] * dk * sg / s
            u = ucl[y, x]
            a, b = EA[e], EB[e]
            cx = P2[a, 0] + u * (P2[b, 0] - P2[a, 0])
            cy = P2[a, 1] + u * (P2[b, 1] - P2[a, 1])
            gx, gy = (cx - (x + 0.5)) / d, (cy - (y + 0.5)) / d     # d dist / d (closest point)
            out[a, 0] += w * (1 - u) * gx; out[a, 1] += w * (1 - u) * gy
            out[b, 0] += w * u * gx; out[b, 1] += w * u * gy


@nb.njit(cache=True)
def _aggregate(P2, F, W, H, s, R):
    """SoftRas's probabilistic union (forward only, for comparison): 1 - prod_j (1 - k(sd_j / s)), sd_j the signed
    distance to triangle j (+ inside), over the pixels within R of it."""
    lg = np.zeros((H, W))
    for t in range(F.shape[0]):
        i0, i1, i2 = F[t, 0], F[t, 1], F[t, 2]
        xs = (P2[i0, 0], P2[i1, 0], P2[i2, 0]); ys = (P2[i0, 1], P2[i1, 1], P2[i2, 1])
        area = (xs[1] - xs[0]) * (ys[2] - ys[0]) - (ys[1] - ys[0]) * (xs[2] - xs[0])
        if not (abs(area) > 1e-12):
            continue
        o = 1.0 if area > 0 else -1.0
        x0 = max(0, int(math.floor(min(xs) - R))); x1 = min(W - 1, int(math.ceil(max(xs) + R)))
        y0 = max(0, int(math.floor(min(ys) - R))); y1 = min(H - 1, int(math.ceil(max(ys) + R)))
        for y in range(y0, y1 + 1):
            Y = y + 0.5
            for x in range(x0, x1 + 1):
                X = x + 0.5
                inside = True
                dm = 1e300
                for k in range(3):
                    qx, qy = xs[k], ys[k]
                    rx, ry = xs[(k + 1) % 3], ys[(k + 1) % 3]
                    dx, dy = rx - qx, ry - qy
                    if o * (dx * (Y - qy) - dy * (X - qx)) < 0:
                        inside = False
                    l2 = dx * dx + dy * dy
                    u = min(1.0, max(0.0, ((X - qx) * dx + (Y - qy) * dy) / l2))
                    dd = math.sqrt((X - qx - u * dx) ** 2 + (Y - qy - u * dy) ** 2)
                    if dd < dm:
                        dm = dd
                sd = dm if inside else -dm
                if sd < -R:
                    continue
                D = 1.0 / (1.0 + math.exp(-4.0 * sd / s))
                lg[y, x] += math.log(max(1e-300, 1.0 - D))
    return 1.0 - np.exp(lg)


# ------------------------------------------------------------------------------------------------------------ the API
def triangles(faces):
    """faces (triangles, quads or a mix, as lists) -> (n, 3) int64 triangles (a quad split on its 0-2 diagonal, as the
    QA's own splits: skirt_scratch/fast.py, bodymeasure)."""
    if isinstance(faces, np.ndarray) and faces.ndim == 2 and faces.shape[1] == 3:
        return np.ascontiguousarray(faces, np.int64)
    out = []
    for f in faces:
        for k in range(1, len(f) - 1):
            out.append((f[0], f[k], f[k + 1]))
    return np.asarray(out, np.int64).reshape(-1, 3)


class Silhouette:
    """one view's soft silhouette (silhouette()), on a crop of the view round the mesh (box: rows y0:y1, columns x0:x1;
    the rest of the view is empty): cov the visible soft coverage in [0, 1], hard the visible hard one (the QA's), both
    (y1 - y0, x1 - x0); full(a) puts a crop's array into the whole view; iou(mask) the soft IoU against a whole-view
    mask and its gradient on the crop; backward(g) -> d loss / dV (N, 3) from g = d loss / d cov (crop); seconds per
    stage."""

    def __init__(self, **k):
        self.__dict__.update(k)

    def full(self, a, fill=0):
        y0, y1, x0, x1 = self.box
        out = np.full(self.view.shape, fill, np.asarray(a).dtype)
        out[y0:y1, x0:x1] = a
        return out

    def iou(self, mask, cov=None):
        """soft IoU against a whole-view bool mask -> (iou, d iou / d cov on the crop)."""
        y0, y1, x0, x1 = self.box
        m = np.asarray(mask, bool)
        c = self.cov if cov is None else cov
        mc = m[y0:y1, x0:x1].astype(float)
        I = float((c * mc).sum())
        U = float(c.sum() + m.sum() - I)
        if U <= 0:
            return 0.0, np.zeros_like(c)
        return I / U, (mc * U - I * (1 - mc)) / U ** 2

    def backward(self, g):
        import time
        t = time.time()
        g = np.where(self.vis_soft, np.asarray(g, float), 0.0)
        out = np.zeros((len(self.P2), 2))
        if len(self.EA):
            _back(self.P2, self.EA, self.EB, self.eid, self.ucl, self.dmin, self.cov_hard, g, self.s,
                  self.kernel == 'linear', out)
        dV = self.view.pullback(self.V, out)
        self.seconds['backward'] = time.time() - t
        return dV


def crop(P2, shape, pad):
    """the rows and columns of a view round projected points, pad px beyond them: (y0, y1, x0, x1)."""
    H, W = shape
    ok = np.isfinite(P2).all(1)
    if not ok.any():
        return 0, 0, 0, 0
    lo, hi = P2[ok].min(0), P2[ok].max(0)
    x0, y0 = max(0, int(np.floor(lo[0] - pad))), max(0, int(np.floor(lo[1] - pad)))
    x1, y1 = min(W, int(np.ceil(hi[0] + pad)) + 1), min(H, int(np.ceil(hi[1] + pad)) + 1)
    return y0, max(y0, y1), x0, max(x0, x1)


def silhouette(V, F, view, s=0.5, occ=None, kernel='sigmoid', margin=MARGIN):
    """V (N, 3) in view's frame, F triangles (or faces: triangles() splits them), view a SheetView or CameraView, s the
    softness (px), occ (H, W) the depth of whatever else is in the view (inf where nothing: this mesh shows where it is
    nearer, as the QA composites by depth), kernel 'sigmoid' or 'linear'. -> Silhouette (on a crop round the mesh)."""
    import time
    assert kernel in KERNELS
    t0 = time.time()
    V = np.asarray(V, float)
    F = triangles(F)
    P2f, dep = view.project(V)
    R = (REACH * s if kernel == 'sigmoid' else 0.5 * s) + 1e-9
    y0, y1, x0, x1 = crop(P2f, view.shape, R + 2)
    H, W = y1 - y0, x1 - x0
    P2 = np.ascontiguousarray(P2f - np.array([x0, y0], float))
    dep = np.ascontiguousarray(dep)
    zb, fb, _, _ = _raster(P2, dep, F, W, H)
    cov = fb >= 0
    occ = np.full((H, W), np.inf) if occ is None else np.asarray(occ, float)[y0:y1, x0:x1]
    vis = cov & (zb < occ)
    t1 = time.time()
    start, tris = _bins(P2, F, W, H)
    X, ev = _crossings(P2, F, start, tris, cov, vis, W, H)
    t2 = time.time()
    # the contour's edges, each over the span of its points (+ margin), as (lower id, higher id)
    dmin = np.full((H, W), np.inf); eid = np.full((H, W), -1, np.int64); ucl = np.zeros((H, W))
    if len(X):
        lo, hi = ev.min(1), ev.max(1)
        key = lo * (len(V) + 1) + hi
        uk, inv = np.unique(key, return_inverse=True)
        EA, EB = uk // (len(V) + 1), uk % (len(V) + 1)
        d = P2[EB] - P2[EA]
        ln = np.maximum(1e-12, np.hypot(d[:, 0], d[:, 1]))
        u = np.einsum('ij,ij->i', X[:, :2] - P2[EA[inv]], d[inv]) / ln[inv] ** 2
        U0 = np.full(len(uk), np.inf); U1 = np.full(len(uk), -np.inf)
        np.minimum.at(U0, inv, u); np.maximum.at(U1, inv, u)
        U0 = np.clip(U0 - margin / ln, 0, 1); U1 = np.clip(U1 + margin / ln, 0, 1)
        _sdf(P2, EA, EB, U0, U1, W, H, R, dmin, eid, ucl)
    else:
        EA = EB = np.zeros(0, np.int64); U0 = U1 = np.zeros(0)
    band = eid >= 0
    sg = np.where(cov, 1.0, -1.0)
    x = np.where(band, sg * np.where(band, dmin, 0) / s, 0.0)
    k = np.clip(0.5 + x, 0, 1) if kernel == 'linear' else 1 / (1 + np.exp(-4 * x))
    Fs = np.where(band, k, cov.astype(float))
    # visibility: a covered pixel at its own depth; a band pixel outside at its contour point's
    dz = zb.copy()
    if len(EA):
        e = np.where(band, eid, 0)
        de = dep[EA[e]] * (1 - ucl) + dep[EB[e]] * ucl
        dz = np.where(band & ~cov, de, dz)
    vis_soft = dz < occ
    t3 = time.time()
    return Silhouette(V=V, F=F, view=view, box=(y0, y1, x0, x1), s=float(s), kernel=kernel, P2=P2, depth=dep,
                      zbuf=zb, face=fb, cov_hard=cov, hard=vis, vis_soft=vis_soft, cov=Fs * vis_soft, EA=EA, EB=EB,
                      U0=U0, U1=U1, dmin=dmin, eid=eid, ucl=ucl, contour=X,
                      seconds={'raster': t1 - t0, 'contour': t2 - t1, 'field': t3 - t2})


def soft_iou(cov, mask, weight=None):
    """soft IoU of a whole-view coverage (H, W) in [0, 1] against a bool mask: sum(cov m) / sum(cov + m - cov m) (the
    hard IoU when cov is 0 / 1). -> (iou, d iou / d cov (H, W))."""
    m = np.asarray(mask, float)
    I = float((cov * m).sum())
    U = float(cov.sum() + m.sum() - I)
    if U <= 0:
        return 0.0, np.zeros_like(cov)
    return I / U, (m * U - I * (1 - m)) / U ** 2


def aggregate(V, F, view, s=0.5):
    """SoftRas's per-triangle probabilistic union at softness s (forward only): the comparison the module's note gives."""
    P2, _ = view.project(np.asarray(V, float))
    H, W = view.shape
    return _aggregate(np.ascontiguousarray(P2), triangles(F), W, H, float(s), REACH * s + 1)
