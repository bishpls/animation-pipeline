"""A bounding-volume hierarchy over a triangle mesh and vectorised queries on large point / ray sets (numba, parallel over
queries; deterministic: each query is independent).

    B = BVH(mesh)                      # or BVH((V, F))
    d, f, q = B.nearest(P)             # distance, face, closest point per query point
    s = B.signed_distance(P)           # negative inside (sign by winding number: robust to holes and open input)
    w = B.winding_number(P)            # generalised winding number (fast dipole approximation, Barill et al. 2018)
    t, f = B.ray_cast(O, D)            # first hit (t = inf on a miss)
    n = B.ray_count(O, D)              # every crossing along each ray (for parity tests)
    inside = B.contains(P)             # winding number > 0.5
"""
import math

import numpy as np
import numba as nb

from .mesh import as_mesh, face_normals

# error_model='numpy': a division by zero gives inf / nan instead of raising (an exception inside a parallel loop can be
# swallowed and leave that thread's outputs unwritten)
_OPT = dict(cache=True, nogil=True, fastmath=False, error_model='numpy')


# ------------------------------------------------------------------------------------------------------------------ build
@nb.njit(**_OPT)
def _build(cen, tmin, tmax, leaf):
    n = cen.shape[0]
    perm = np.arange(n)
    cap = 2 * (n // max(1, leaf // 2) + 1) + 1
    bmin = np.empty((cap, 3)); bmax = np.empty((cap, 3))
    left = np.full(cap, -1, np.int64); right = np.full(cap, -1, np.int64)
    start = np.zeros(cap, np.int64); count = np.zeros(cap, np.int64)
    stack_n = np.empty(128, np.int64); stack_s = np.empty(128, np.int64); stack_e = np.empty(128, np.int64)
    sp = 0
    nn = 1
    stack_n[0] = 0; stack_s[0] = 0; stack_e[0] = n; sp = 1
    while sp > 0:
        sp -= 1
        node = stack_n[sp]; s = stack_s[sp]; e = stack_e[sp]
        lo = np.full(3, np.inf); hi = np.full(3, -np.inf)
        clo = np.full(3, np.inf); chi = np.full(3, -np.inf)
        for i in range(s, e):
            t = perm[i]
            for k in range(3):
                if tmin[t, k] < lo[k]:
                    lo[k] = tmin[t, k]
                if tmax[t, k] > hi[k]:
                    hi[k] = tmax[t, k]
                if cen[t, k] < clo[k]:
                    clo[k] = cen[t, k]
                if cen[t, k] > chi[k]:
                    chi[k] = cen[t, k]
        bmin[node] = lo; bmax[node] = hi
        if e - s <= leaf:
            start[node] = s; count[node] = e - s
            continue
        ax = 0
        ext = chi - clo
        if ext[1] > ext[ax]:
            ax = 1
        if ext[2] > ext[ax]:
            ax = 2
        seg = perm[s:e].copy()
        key = np.empty(e - s)
        for i in range(e - s):
            key[i] = cen[seg[i], ax]
        order = np.argsort(key, kind='mergesort')
        for i in range(e - s):
            perm[s + i] = seg[order[i]]
        m = (s + e) // 2
        l = nn; r = nn + 1; nn += 2
        left[node] = l; right[node] = r
        stack_n[sp] = r; stack_s[sp] = m; stack_e[sp] = e; sp += 1
        stack_n[sp] = l; stack_s[sp] = s; stack_e[sp] = m; sp += 1
    return perm, bmin[:nn].copy(), bmax[:nn].copy(), left[:nn].copy(), right[:nn].copy(), start[:nn].copy(), count[:nn].copy()


@nb.njit(**_OPT)
def _dipoles(V, F, perm, left, right, start, count, area_n, tri_c):
    """per node: the area-weighted normal sum (dipole), its area-weighted centre and the radius of a ball around the centre
    holding all its triangles (bottom-up: children have larger indices than parents)."""
    K = left.shape[0]
    N = np.zeros((K, 3)); C = np.zeros((K, 3)); A = np.zeros(K); R = np.zeros(K)
    for node in range(K - 1, -1, -1):
        if count[node] > 0:
            for i in range(start[node], start[node] + count[node]):
                t = perm[i]
                a = math.sqrt(area_n[t, 0] ** 2 + area_n[t, 1] ** 2 + area_n[t, 2] ** 2) * 0.5
                for k in range(3):
                    N[node, k] += area_n[t, k] * 0.5
                    C[node, k] += tri_c[t, k] * a
                A[node] += a
        else:
            l = left[node]; r = right[node]
            for k in range(3):
                N[node, k] = N[l, k] + N[r, k]
                C[node, k] = C[l, k] * A[l] + C[r, k] * A[r]
            A[node] = A[l] + A[r]
        if A[node] > 0:
            for k in range(3):
                C[node, k] /= A[node]
        # radius: over the triangles' vertices below this node (leaves directly; inner nodes from the children's balls)
        if count[node] > 0:
            rr = 0.0
            for i in range(start[node], start[node] + count[node]):
                t = perm[i]
                for j in range(3):
                    v = F[t, j]
                    d = math.sqrt((V[v, 0] - C[node, 0]) ** 2 + (V[v, 1] - C[node, 1]) ** 2 + (V[v, 2] - C[node, 2]) ** 2)
                    if d > rr:
                        rr = d
            R[node] = rr
        else:
            l = left[node]; r = right[node]
            dl = math.sqrt((C[l, 0] - C[node, 0]) ** 2 + (C[l, 1] - C[node, 1]) ** 2 + (C[l, 2] - C[node, 2]) ** 2) + R[l]
            dr = math.sqrt((C[r, 0] - C[node, 0]) ** 2 + (C[r, 1] - C[node, 1]) ** 2 + (C[r, 2] - C[node, 2]) ** 2) + R[r]
            R[node] = max(dl, dr)
    return N, C, R


# --------------------------------------------------------------------------------------------------------------- kernels
@nb.njit(**_OPT)
def _closest_on_tri(px, py, pz, ax, ay, az, bx, by, bz, cx, cy, cz):
    """closest point on triangle abc to p (Ericson, Real-Time Collision Detection 5.1.5). -> (x, y, z, region) region 0
    face, 1..3 vertex a b c, 4 edge ab, 5 bc, 6 ca."""
    abx, aby, abz = bx - ax, by - ay, bz - az
    acx, acy, acz = cx - ax, cy - ay, cz - az
    apx, apy, apz = px - ax, py - ay, pz - az
    d1 = abx * apx + aby * apy + abz * apz
    d2 = acx * apx + acy * apy + acz * apz
    if d1 <= 0.0 and d2 <= 0.0:
        return ax, ay, az, 1
    bpx, bpy, bpz = px - bx, py - by, pz - bz
    d3 = abx * bpx + aby * bpy + abz * bpz
    d4 = acx * bpx + acy * bpy + acz * bpz
    if d3 >= 0.0 and d4 <= d3:
        return bx, by, bz, 2
    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        v = d1 / (d1 - d3) if d1 - d3 > 0.0 else 0.0
        return ax + v * abx, ay + v * aby, az + v * abz, 4
    cpx, cpy, cpz = px - cx, py - cy, pz - cz
    d5 = abx * cpx + aby * cpy + abz * cpz
    d6 = acx * cpx + acy * cpy + acz * cpz
    if d6 >= 0.0 and d5 <= d6:
        return cx, cy, cz, 3
    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        w = d2 / (d2 - d6) if d2 - d6 > 0.0 else 0.0
        return ax + w * acx, ay + w * acy, az + w * acz, 6
    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        s_ = (d4 - d3) + (d5 - d6)
        w = (d4 - d3) / s_ if s_ > 0.0 else 0.0
        return bx + w * (cx - bx), by + w * (cy - by), bz + w * (cz - bz), 5
    if va + vb + vc <= 0.0:                         # a degenerate triangle: its nearest vertex
        return ax, ay, az, 1
    den = 1.0 / (va + vb + vc)
    v = vb * den
    w = vc * den
    return ax + abx * v + acx * w, ay + aby * v + acy * w, az + abz * v + acz * w, 0


@nb.njit(**_OPT)
def _box_d2(px, py, pz, lo, hi):
    d = 0.0
    for k, p in enumerate((px, py, pz)):
        if p < lo[k]:
            d += (lo[k] - p) ** 2
        elif p > hi[k]:
            d += (p - hi[k]) ** 2
    return d


@nb.njit(parallel=True, **_OPT)
def _nearest(P, V, F, perm, bmin, bmax, left, right, start, count, maxd2):
    n = P.shape[0]
    out_d = np.empty(n); out_f = np.empty(n, np.int64); out_q = np.empty((n, 3)); out_r = np.empty(n, np.int64)
    for i in nb.prange(n):
        px, py, pz = P[i, 0], P[i, 1], P[i, 2]
        best = maxd2
        bf = -1; bx = np.nan; by = np.nan; bz = np.nan; breg = -1
        stack = np.empty(96, np.int64)
        sp = 0
        stack[0] = 0; sp = 1
        while sp > 0:
            sp -= 1
            node = stack[sp]
            if _box_d2(px, py, pz, bmin[node], bmax[node]) >= best:
                continue
            if count[node] > 0:
                for j in range(start[node], start[node] + count[node]):
                    t = perm[j]
                    a, b, c = F[t, 0], F[t, 1], F[t, 2]
                    qx, qy, qz, reg = _closest_on_tri(px, py, pz, V[a, 0], V[a, 1], V[a, 2], V[b, 0], V[b, 1], V[b, 2],
                                                      V[c, 0], V[c, 1], V[c, 2])
                    d2 = (qx - px) ** 2 + (qy - py) ** 2 + (qz - pz) ** 2
                    if d2 < best:
                        best = d2; bf = t; bx = qx; by = qy; bz = qz; breg = reg
            else:
                l = left[node]; r = right[node]
                dl = _box_d2(px, py, pz, bmin[l], bmax[l]); dr = _box_d2(px, py, pz, bmin[r], bmax[r])
                if dl < dr:
                    if dr < best:
                        stack[sp] = r; sp += 1
                    if dl < best:
                        stack[sp] = l; sp += 1
                else:
                    if dl < best:
                        stack[sp] = l; sp += 1
                    if dr < best:
                        stack[sp] = r; sp += 1
        out_d[i] = math.sqrt(best) if bf >= 0 else np.inf
        out_f[i] = bf; out_q[i, 0] = bx; out_q[i, 1] = by; out_q[i, 2] = bz; out_r[i] = breg
    return out_d, out_f, out_q, out_r


@nb.njit(**_OPT)
def _ray_box(ox, oy, oz, ix, iy, iz, lo, hi, tmax):
    t0 = 0.0; t1 = tmax
    for k in range(3):
        o = (ox, oy, oz)[k]; inv = (ix, iy, iz)[k]
        ta = (lo[k] - o) * inv; tb = (hi[k] - o) * inv
        if ta > tb:
            ta, tb = tb, ta
        if ta > t0:
            t0 = ta
        if tb < t1:
            t1 = tb
        if t0 > t1:
            return np.inf
    return t0


@nb.njit(**_OPT)
def _ray_tri(ox, oy, oz, dx, dy, dz, ax, ay, az, bx, by, bz, cx, cy, cz):
    """Moller-Trumbore, two-sided. -> (t, u, v); t = inf on a miss."""
    e1x, e1y, e1z = bx - ax, by - ay, bz - az
    e2x, e2y, e2z = cx - ax, cy - ay, cz - az
    px_ = dy * e2z - dz * e2y; py_ = dz * e2x - dx * e2z; pz_ = dx * e2y - dy * e2x
    det = e1x * px_ + e1y * py_ + e1z * pz_
    if abs(det) < 1e-300:
        return np.inf, 0.0, 0.0
    inv = 1.0 / det
    tx, ty, tz = ox - ax, oy - ay, oz - az
    u = (tx * px_ + ty * py_ + tz * pz_) * inv
    if u < 0.0 or u > 1.0:
        return np.inf, 0.0, 0.0
    qx = ty * e1z - tz * e1y; qy = tz * e1x - tx * e1z; qz = tx * e1y - ty * e1x
    v = (dx * qx + dy * qy + dz * qz) * inv
    if v < 0.0 or u + v > 1.0:
        return np.inf, 0.0, 0.0
    t = (e2x * qx + e2y * qy + e2z * qz) * inv
    return t, u, v


@nb.njit(parallel=True, **_OPT)
def _raycast(O, D, tmax, V, F, perm, bmin, bmax, left, right, start, count, tmin_):
    n = O.shape[0]
    out_t = np.full(n, np.inf); out_f = np.full(n, -1, np.int64); out_uv = np.zeros((n, 2))
    for i in nb.prange(n):
        ox, oy, oz = O[i, 0], O[i, 1], O[i, 2]
        dx, dy, dz = D[i, 0], D[i, 1], D[i, 2]
        ix = 1.0 / dx if dx != 0 else 1e300
        iy = 1.0 / dy if dy != 0 else 1e300
        iz = 1.0 / dz if dz != 0 else 1e300
        best = tmax[i]
        stack = np.empty(96, np.int64); sp = 1; stack[0] = 0
        while sp > 0:
            sp -= 1
            node = stack[sp]
            if _ray_box(ox, oy, oz, ix, iy, iz, bmin[node], bmax[node], best) == np.inf:
                continue
            if count[node] > 0:
                for j in range(start[node], start[node] + count[node]):
                    t = perm[j]
                    a, b, c = F[t, 0], F[t, 1], F[t, 2]
                    tt, u, v = _ray_tri(ox, oy, oz, dx, dy, dz, V[a, 0], V[a, 1], V[a, 2], V[b, 0], V[b, 1], V[b, 2],
                                        V[c, 0], V[c, 1], V[c, 2])
                    if tt > tmin_ and tt < best:
                        best = tt; out_f[i] = t; out_uv[i, 0] = u; out_uv[i, 1] = v
            else:
                stack[sp] = left[node]; sp += 1
                stack[sp] = right[node]; sp += 1
        if out_f[i] >= 0:
            out_t[i] = best
    return out_t, out_f, out_uv


@nb.njit(parallel=True, **_OPT)
def _raycount(O, D, V, F, perm, bmin, bmax, left, right, start, count, tmin_):
    n = O.shape[0]
    out = np.zeros(n, np.int64)
    for i in nb.prange(n):
        ox, oy, oz = O[i, 0], O[i, 1], O[i, 2]
        dx, dy, dz = D[i, 0], D[i, 1], D[i, 2]
        ix = 1.0 / dx if dx != 0 else 1e300
        iy = 1.0 / dy if dy != 0 else 1e300
        iz = 1.0 / dz if dz != 0 else 1e300
        c = 0
        stack = np.empty(96, np.int64); sp = 1; stack[0] = 0
        while sp > 0:
            sp -= 1
            node = stack[sp]
            if _ray_box(ox, oy, oz, ix, iy, iz, bmin[node], bmax[node], 1e300) == np.inf:
                continue
            if count[node] > 0:
                for j in range(start[node], start[node] + count[node]):
                    t = perm[j]
                    a, b, cc = F[t, 0], F[t, 1], F[t, 2]
                    tt, u, v = _ray_tri(ox, oy, oz, dx, dy, dz, V[a, 0], V[a, 1], V[a, 2], V[b, 0], V[b, 1], V[b, 2],
                                        V[cc, 0], V[cc, 1], V[cc, 2])
                    if tt > tmin_ and tt < np.inf:
                        c += 1
            else:
                stack[sp] = left[node]; sp += 1
                stack[sp] = right[node]; sp += 1
        out[i] = c
    return out


@nb.njit(parallel=True, **_OPT)
def _rayhits(O, D, off, V, F, perm, bmin, bmax, left, right, start, count, tmin_):
    out = np.empty(off[-1])
    for i in nb.prange(O.shape[0]):
        ox, oy, oz = O[i, 0], O[i, 1], O[i, 2]
        dx, dy, dz = D[i, 0], D[i, 1], D[i, 2]
        ix = 1.0 / dx if dx != 0 else 1e300
        iy = 1.0 / dy if dy != 0 else 1e300
        iz = 1.0 / dz if dz != 0 else 1e300
        c = off[i]
        stack = np.empty(96, np.int64); sp = 1; stack[0] = 0
        while sp > 0:
            sp -= 1
            node = stack[sp]
            if _ray_box(ox, oy, oz, ix, iy, iz, bmin[node], bmax[node], 1e300) == np.inf:
                continue
            if count[node] > 0:
                for j in range(start[node], start[node] + count[node]):
                    t = perm[j]
                    a, b, cc = F[t, 0], F[t, 1], F[t, 2]
                    tt, u, v = _ray_tri(ox, oy, oz, dx, dy, dz, V[a, 0], V[a, 1], V[a, 2], V[b, 0], V[b, 1], V[b, 2],
                                        V[cc, 0], V[cc, 1], V[cc, 2])
                    if tt > tmin_ and tt < np.inf and c < off[i + 1]:
                        out[c] = tt; c += 1
            else:
                stack[sp] = left[node]; sp += 1
                stack[sp] = right[node]; sp += 1
    return out


@nb.njit(**_OPT)
def _solid_angle(px, py, pz, ax, ay, az, bx, by, bz, cx, cy, cz):
    """the signed solid angle of triangle abc seen from p (Van Oosterom and Strackee)."""
    ax -= px; ay -= py; az -= pz
    bx -= px; by -= py; bz -= pz
    cx -= px; cy -= py; cz -= pz
    la = math.sqrt(ax * ax + ay * ay + az * az)
    lb = math.sqrt(bx * bx + by * by + bz * bz)
    lc = math.sqrt(cx * cx + cy * cy + cz * cz)
    det = ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx)
    den = la * lb * lc + (ax * bx + ay * by + az * bz) * lc + (bx * cx + by * cy + bz * cz) * la + \
        (cx * ax + cy * ay + cz * az) * lb
    return 2.0 * math.atan2(det, den)


@nb.njit(parallel=True, **_OPT)
def _winding(P, V, F, perm, left, right, start, count, DN, DC, DR, beta):
    n = P.shape[0]
    out = np.zeros(n)
    inv4pi = 1.0 / (4.0 * math.pi)
    for i in nb.prange(n):
        px, py, pz = P[i, 0], P[i, 1], P[i, 2]
        w = 0.0
        stack = np.empty(96, np.int64); sp = 1; stack[0] = 0
        while sp > 0:
            sp -= 1
            node = stack[sp]
            rx = DC[node, 0] - px; ry = DC[node, 1] - py; rz = DC[node, 2] - pz
            d = math.sqrt(rx * rx + ry * ry + rz * rz)
            if d > beta * DR[node] and d > 0:
                w += (rx * DN[node, 0] + ry * DN[node, 1] + rz * DN[node, 2]) / (d * d * d) * inv4pi
                continue
            if count[node] > 0:
                for j in range(start[node], start[node] + count[node]):
                    t = perm[j]
                    a, b, c = F[t, 0], F[t, 1], F[t, 2]
                    w += _solid_angle(px, py, pz, V[a, 0], V[a, 1], V[a, 2], V[b, 0], V[b, 1], V[b, 2],
                                      V[c, 0], V[c, 1], V[c, 2]) * inv4pi
            else:
                stack[sp] = left[node]; sp += 1
                stack[sp] = right[node]; sp += 1
        out[i] = w
    return out


# ------------------------------------------------------------------------------------------------------------------- class
class BVH:
    """a BVH over a mesh's triangles (leaf size `leaf`). The mesh's arrays are kept (not copied); don't mutate them."""

    def __init__(self, m, leaf=8):
        m = as_mesh(m)
        self.mesh = m
        self.V = np.ascontiguousarray(m.V, np.float64)
        self.F = np.ascontiguousarray(m.F, np.int64)
        T = self.V[self.F]
        tmin, tmax = T.min(1), T.max(1)
        cen = T.mean(1)
        if len(self.F) == 0:
            raise ValueError('BVH of an empty mesh')
        self.perm, self.bmin, self.bmax, self.left, self.right, self.start, self.count = _build(cen, tmin, tmax, leaf)
        self._dip = None
        self._pn = None

    def _args(self):
        return (self.V, self.F, self.perm, self.bmin, self.bmax, self.left, self.right, self.start, self.count)

    def nearest(self, P, max_dist=np.inf, return_region=False):
        """closest surface point per query: -> (dist (inf beyond max_dist), face (-1), point (nan)) [, region: 0 inside the
        face, 1-3 at vertex a/b/c, 4-6 on edge ab/bc/ca]."""
        P = np.ascontiguousarray(np.asarray(P, np.float64).reshape(-1, 3))
        d, f, q, r = _nearest(P, *self._args(), float(max_dist) ** 2 if np.isfinite(max_dist) else np.inf)
        return (d, f, q, r) if return_region else (d, f, q)

    def ray_cast(self, O, D, tmax=np.inf, tmin=0.0, return_uv=False):
        """first hit along each ray O + t D (t > tmin): -> (t (inf on a miss), face (-1)) [, barycentric (u, v)]."""
        O = np.ascontiguousarray(np.asarray(O, np.float64).reshape(-1, 3))
        D = np.ascontiguousarray(np.broadcast_to(np.asarray(D, np.float64).reshape(-1, 3), O.shape))
        tm = np.ascontiguousarray(np.broadcast_to(np.asarray(tmax, np.float64), (len(O),)))
        t, f, uv = _raycast(O, D, tm, *self._args(), float(tmin))
        return (t, f, uv) if return_uv else (t, f)

    def ray_count(self, O, D, tmin=0.0):
        """the number of crossings along each ray (both directions of a face count)."""
        O = np.ascontiguousarray(np.asarray(O, np.float64).reshape(-1, 3))
        D = np.ascontiguousarray(np.broadcast_to(np.asarray(D, np.float64).reshape(-1, 3), O.shape))
        return _raycount(O, D, *self._args(), float(tmin))

    def ray_hits(self, O, D, tmin=0.0):
        """every crossing along each ray: -> (offsets (n+1,), t (total,)); ray i's hits are t[off[i]:off[i+1]] (unsorted)."""
        O = np.ascontiguousarray(np.asarray(O, np.float64).reshape(-1, 3))
        D = np.ascontiguousarray(np.broadcast_to(np.asarray(D, np.float64).reshape(-1, 3), O.shape))
        cnt = _raycount(O, D, *self._args(), float(tmin))
        off = np.r_[0, np.cumsum(cnt)].astype(np.int64)
        return off, _rayhits(O, D, off, *self._args(), float(tmin))

    def winding_number(self, P, beta=2.0):
        """the generalised winding number at each point (1 inside a closed outward-oriented surface, 0 outside, smooth and
        graceful across holes). beta: the far-field threshold (distance / node radius); 2 is accurate to ~1e-3."""
        if self._dip is None:
            an = face_normals(self.V, self.F, unit=False)
            self._dip = _dipoles(self.V, self.F, self.perm, self.left, self.right, self.start, self.count, an,
                                 self.V[self.F].mean(1))
        P = np.ascontiguousarray(np.asarray(P, np.float64).reshape(-1, 3))
        DN, DC, DR = self._dip
        return _winding(P, self.V, self.F, self.perm, self.left, self.right, self.start, self.count, DN, DC, DR,
                        float(beta))

    def contains(self, P, beta=2.0):
        return self.winding_number(P, beta) > 0.5

    def pseudo_normals(self):
        """angle-weighted vertex normals, edge normals and face normals (Baerentzen and Aanaes): the sign of (p - q) . n at
        the closest feature is exact for a closed, consistently oriented mesh."""
        if self._pn is None:
            from .mesh import vertex_normals, unique_edges
            fn = face_normals(self.V, self.F)
            vn = vertex_normals(self.V, self.F, 'angle')
            E, inv, cnt = unique_edges(self.F)
            en = np.zeros((len(E), 3))
            np.add.at(en, inv, np.repeat(fn, 3, axis=0))
            en /= np.maximum(np.linalg.norm(en, axis=1, keepdims=True), 1e-300)
            self._pn = (fn, vn, en, inv.reshape(-1, 3))
        return self._pn

    def signed_distance(self, P, sign='winding', beta=2.0):
        """distance to the surface, negative inside. sign: 'winding' (robust to holes, open and messy input), 'normal' (the
        pseudo-normal at the closest feature: exact and faster for a clean closed mesh)."""
        P = np.asarray(P, np.float64).reshape(-1, 3)
        d, f, q, reg = self.nearest(P, return_region=True)
        if sign == 'winding':
            s = np.where(self.winding_number(P, beta) > 0.5, -1.0, 1.0)
        else:
            fn, vn, en, fe = self.pseudo_normals()
            n = fn[f].copy()
            for r_, k in ((1, 0), (2, 1), (3, 2)):
                m = reg == r_
                n[m] = vn[self.F[f[m], k]]
            for r_, k in ((4, 0), (5, 1), (6, 2)):
                m = reg == r_
                n[m] = en[fe[f[m], k]]
            s = np.where(np.einsum('ij,ij->i', P - q, n) < 0, -1.0, 1.0)
        return d * s


# ------------------------------------------------------------------------------------------------------ self-intersection
@nb.njit(**_OPT)
def _seg_tri(p, q, a, b, c):
    """does segment pq cross triangle abc (strictly inside the segment)?"""
    dx, dy, dz = q[0] - p[0], q[1] - p[1], q[2] - p[2]
    t, u, v = _ray_tri(p[0], p[1], p[2], dx, dy, dz, a[0], a[1], a[2], b[0], b[1], b[2], c[0], c[1], c[2])
    return t > 1e-9 and t < 1.0 - 1e-9


@nb.njit(parallel=True, **_OPT)
def _self_hits(Q, V, F, perm, bmin, bmax, left, right, start, count):
    n = Q.shape[0]
    out = np.zeros(n, np.bool_)
    for i in nb.prange(n):
        f = Q[i]
        a0, a1, a2 = F[f, 0], F[f, 1], F[f, 2]
        A = np.empty((3, 3))
        for k in range(3):
            A[0, k] = V[a0, k]; A[1, k] = V[a1, k]; A[2, k] = V[a2, k]
        lo = np.empty(3); hi = np.empty(3)
        for k in range(3):
            lo[k] = min(A[0, k], A[1, k], A[2, k]); hi[k] = max(A[0, k], A[1, k], A[2, k])
        stack = np.empty(96, np.int64); sp = 1; stack[0] = 0
        B = np.empty((3, 3))
        found = False
        while sp > 0 and not found:
            sp -= 1
            node = stack[sp]
            ov = True
            for k in range(3):
                if bmin[node, k] > hi[k] or bmax[node, k] < lo[k]:
                    ov = False
            if not ov:
                continue
            if count[node] > 0:
                for j in range(start[node], start[node] + count[node]):
                    g = perm[j]
                    if g == f:
                        continue
                    b0, b1, b2 = F[g, 0], F[g, 1], F[g, 2]
                    if b0 == a0 or b0 == a1 or b0 == a2 or b1 == a0 or b1 == a1 or b1 == a2 or \
                            b2 == a0 or b2 == a1 or b2 == a2:
                        continue
                    for k in range(3):
                        B[0, k] = V[b0, k]; B[1, k] = V[b1, k]; B[2, k] = V[b2, k]
                    hit = False
                    for e in range(3):
                        if _seg_tri(A[e], A[(e + 1) % 3], B[0], B[1], B[2]) or \
                                _seg_tri(B[e], B[(e + 1) % 3], A[0], A[1], A[2]):
                            hit = True
                            break
                    if hit:
                        found = True
                        break
            else:
                stack[sp] = left[node]; sp += 1
                stack[sp] = right[node]; sp += 1
        out[i] = found
    return out
