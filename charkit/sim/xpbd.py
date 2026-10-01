"""XPBD cloth (Macklin, Mueller and Chentanez 2016, "XPBD: position-based simulation of compliant constrained dynamics";
Macklin et al. 2019, "Small steps in physics simulation": many substeps, one Gauss-Seidel pass each). numpy for the set
up, numba for the constraint loops; single-threaded and in a fixed order, so a run is bit-identical to any re-run.

    C = Cloth(V, polys, pins=idx)                    # rest mesh (m), quads split, lumped masses, pinned vertices
    S = Solver(C, settings.cloth('anime', L=L))      # dials from the style profile (charkit.sim.settings)
    S.set_frame(pins=P1, hold=T1, colliders=[...])   # the kinematic targets at the end of the next frame
    S.step(1 / 60)                                    # fixed timestep, `substeps` inside
    S.x                                              # positions

Constraints, per substep in this order:
  distance   every triangle edge (quad diagonals too): C = |xi - xj| - l0, compliance `stretch` (m/N)
  bending    every interior edge's dihedral angle: C = theta - theta0 (the rest mesh's own angle, so a template's drawn
             folds are its rest shape), compliance from the profile's bending length (settings.cloth)
  hold       each free vertex held toward its target (the template carried by the rig): C = |x - t|, compliance from
             `hold` (0: pure physics; the anime dial)
  layer      a vertex kept `gap` outside a triangle of another piece (a flap over the skirt), one-sided, both sides move
  collision  spheres, tapered capsules and signed-distance grids (static, or carried rigidly), projected last, with
             position-based static and kinetic friction (Macklin et al. 2014, "Unified particle physics")
Pins are kinematic (inverse mass 0), moved along a straight line through the frame. Self-collision isn't handled.
"""
import math

import numpy as np
import numba as nb

_OPT = dict(cache=True, nogil=True, fastmath=False, error_model='numpy')


# ------------------------------------------------------------------------------------------------------------ the mesh
def triangulate(polys):
    """polygons (lists of vertex indices) -> triangles (fan from each polygon's first corner)."""
    T = []
    for f in polys:
        f = [int(i) for i in f]
        for k in range(1, len(f) - 1):
            T.append((f[0], f[k], f[k + 1]))
    return np.asarray(T, np.int64).reshape(-1, 3)


def edges_and_hinges(F):
    """the unique edges of triangles F, and per interior (two-triangle) edge its hinge (a, b, c, d): a-b the shared edge,
    c opposite it in the first triangle (a, b, c in its winding), d in the second."""
    half = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    opp = np.concatenate([F[:, 2], F[:, 0], F[:, 1]])
    key = np.sort(half, 1)
    order = np.lexsort((key[:, 1], key[:, 0]))
    ks, hs, os_ = key[order], half[order], opp[order]
    same = np.all(ks[1:] == ks[:-1], 1)
    first = np.r_[True, ~same]
    E = ks[first]
    hinges = []
    i = 0
    n = len(ks)
    while i < n:
        j = i + 1
        while j < n and ks[j, 0] == ks[i, 0] and ks[j, 1] == ks[i, 1]:
            j += 1
        if j - i == 2:
            a, b = hs[i]
            hinges.append((a, b, os_[i], os_[i + 1]))
        i = j
    return np.ascontiguousarray(E, np.int64), np.asarray(hinges, np.int64).reshape(-1, 4)


@nb.njit(**_OPT)
def _dihedral(x0, x1, x2, x3):
    """the signed dihedral angle at hinge (x0, x1 shared; x2 in the first triangle (x0, x1, x2), x3 in the second
    (x1, x0, x3)) and its gradients. 0 when flat."""
    e = x1 - x0
    le = math.sqrt(e[0] * e[0] + e[1] * e[1] + e[2] * e[2])
    n1 = np.cross(e, x2 - x0)
    n2 = np.cross(x3 - x0, e)
    q1 = n1[0] * n1[0] + n1[1] * n1[1] + n1[2] * n1[2]
    q2 = n2[0] * n2[0] + n2[1] * n2[1] + n2[2] * n2[2]
    g = np.zeros((4, 3))
    if le < 1e-12 or q1 < 1e-24 or q2 < 1e-24:
        return 0.0, g, False
    m1 = n1 / math.sqrt(q1)
    m2 = n2 / math.sqrt(q2)
    c = np.cross(m1, m2)
    s = (c[0] * e[0] + c[1] * e[1] + c[2] * e[2]) / le
    co = m1[0] * m2[0] + m1[1] * m2[1] + m1[2] * m2[2]
    th = math.atan2(s, co)
    g2 = -le / q1 * n1
    g3 = -le / q2 * n2
    ee = le * le
    t2 = ((x2 - x0) * e).sum() / ee
    t3 = ((x3 - x0) * e).sum() / ee
    g[2] = g2
    g[3] = g3
    g[0] = -((1.0 - t2) * g2 + (1.0 - t3) * g3)
    g[1] = -(t2 * g2 + t3 * g3)
    return th, g, True


@nb.njit(**_OPT)
def _dihedral_into(p, a, b, c, d, g):
    """_dihedral of hinge (p[a], p[b], p[c], p[d]) without allocating: the gradients written into g (4, 3); the same
    arithmetic in the same order (bit-identical: test_sim.test_the_scalar_kernels_are_bit_identical). -> (th, ok)."""
    e0 = p[b, 0] - p[a, 0]; e1 = p[b, 1] - p[a, 1]; e2 = p[b, 2] - p[a, 2]
    le = math.sqrt(e0 * e0 + e1 * e1 + e2 * e2)
    u0 = p[c, 0] - p[a, 0]; u1 = p[c, 1] - p[a, 1]; u2 = p[c, 2] - p[a, 2]
    v0 = p[d, 0] - p[a, 0]; v1 = p[d, 1] - p[a, 1]; v2 = p[d, 2] - p[a, 2]
    n10 = e1 * u2 - e2 * u1; n11 = e2 * u0 - e0 * u2; n12 = e0 * u1 - e1 * u0          # cross(e, x2 - x0)
    n20 = v1 * e2 - v2 * e1; n21 = v2 * e0 - v0 * e2; n22 = v0 * e1 - v1 * e0          # cross(x3 - x0, e)
    q1 = n10 * n10 + n11 * n11 + n12 * n12
    q2 = n20 * n20 + n21 * n21 + n22 * n22
    if le < 1e-12 or q1 < 1e-24 or q2 < 1e-24:
        return 0.0, False
    r1 = math.sqrt(q1); r2 = math.sqrt(q2)
    m10 = n10 / r1; m11 = n11 / r1; m12 = n12 / r1
    m20 = n20 / r2; m21 = n21 / r2; m22 = n22 / r2
    c0 = m11 * m22 - m12 * m21; c1 = m12 * m20 - m10 * m22; c2 = m10 * m21 - m11 * m20
    s = (c0 * e0 + c1 * e1 + c2 * e2) / le
    co = m10 * m20 + m11 * m21 + m12 * m22
    th = math.atan2(s, co)
    f2 = -le / q1
    f3 = -le / q2
    ee = le * le
    t2 = (u0 * e0 + u1 * e1 + u2 * e2) / ee
    t3 = (v0 * e0 + v1 * e1 + v2 * e2) / ee
    g[2, 0] = f2 * n10; g[2, 1] = f2 * n11; g[2, 2] = f2 * n12
    g[3, 0] = f3 * n20; g[3, 1] = f3 * n21; g[3, 2] = f3 * n22
    for j in range(3):
        g[0, j] = -((1.0 - t2) * g[2, j] + (1.0 - t3) * g[3, j])
        g[1, j] = -(t2 * g[2, j] + t3 * g[3, j])
    return th, True


def dihedral(x0, x1, x2, x3):
    th, g, ok = _dihedral(*(np.asarray(v, np.float64) for v in (x0, x1, x2, x3)))
    return th, g


class Cloth:
    """a piece of cloth: rest positions V (m), triangles, edges and hinges, lumped masses (area density `density`,
    kg/m2), pinned vertices (inverse mass 0)."""

    def __init__(self, V, polys, pins=(), density=0.2, rest=None):
        self.V = np.ascontiguousarray(np.asarray(V, np.float64))
        F = polys if isinstance(polys, np.ndarray) and polys.ndim == 2 and polys.shape[1] == 3 else triangulate(polys)
        self.F = np.ascontiguousarray(np.asarray(F, np.int64))
        self.E, self.H = edges_and_hinges(self.F)
        R = self.V if rest is None else np.asarray(rest, np.float64)       # the rest shape (lengths, angles)
        self.rest_len = np.linalg.norm(R[self.E[:, 0]] - R[self.E[:, 1]], axis=1)
        T = R[self.F]
        area = 0.5 * np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1)
        self.area = area
        m = np.zeros(len(self.V))
        np.add.at(m, self.F.ravel(), np.repeat(area / 3.0, 3))
        m = np.maximum(m, 1e-9 * max(1e-12, m.max()))                     # (a vertex on no face: a tiny mass)
        self.mass = m * density
        self.w = 1.0 / self.mass
        self.pins = np.asarray(sorted(set(int(i) for i in pins)), np.int64)
        self.w[self.pins] = 0.0
        self.order_from_pins()
        th = np.zeros(len(self.H))
        ok = np.ones(len(self.H), bool)
        for k, (a, b, c, d) in enumerate(self.H):
            t, _, o = _dihedral(R[a], R[b], R[c], R[d])
            th[k], ok[k] = t, o
        self.H, th = self.H[ok], th[ok]
        if len(self.H):
            hk = np.lexsort((self.H[:, 1], self.H[:, 0], np.minimum(self._hinge_key[self.H[:, 0]],
                                                                     self._hinge_key[self.H[:, 1]])))
            self.H, th = np.ascontiguousarray(self.H[hk]), th[hk]
        self.rest_angle = th
        # the hinge's weight in the discrete-shells bending energy: 3 |e|^2 / (A1 + A2)
        a1 = np.zeros(len(self.H))
        if len(self.H):
            e = R[self.H[:, 1]] - R[self.H[:, 0]]
            A1 = 0.5 * np.linalg.norm(np.cross(e, R[self.H[:, 2]] - R[self.H[:, 0]]), axis=1)
            A2 = 0.5 * np.linalg.norm(np.cross(e, R[self.H[:, 3]] - R[self.H[:, 0]]), axis=1)
            a1 = 3.0 * (e ** 2).sum(1) / np.maximum(A1 + A2, 1e-18)
        self.hinge_weight = a1

    @property
    def n(self):
        return len(self.V)

    def graph_distance(self):
        """each vertex's geodesic rest distance (along edges) to the nearest pin, and that pin (-1: none reachable)."""
        from scipy.sparse import coo_matrix
        from scipy.sparse.csgraph import dijkstra
        n = self.n
        if not len(self.pins):
            return np.full(n, np.inf), np.full(n, -1, np.int64)
        M = coo_matrix((np.r_[self.rest_len, self.rest_len], (np.r_[self.E[:, 0], self.E[:, 1]],
                                                              np.r_[self.E[:, 1], self.E[:, 0]])), shape=(n, n)).tocsr()
        D, _, src = dijkstra(M, directed=False, indices=self.pins, min_only=True, return_predecessors=True)
        return D, np.where(np.isfinite(D), src, -1).astype(np.int64)

    def order_from_pins(self):
        """edges and hinges sorted outward from the pins (Gauss-Seidel then carries a correction down a hanging piece in
        one pass), and each free vertex's tether (its nearest pin by the edges and the rest distance to it)."""
        D, src = self.graph_distance()
        Dk = np.where(np.isfinite(D), D, np.nanmax(np.where(np.isfinite(D), D, 0)) + 1)
        e = np.lexsort((self.E[:, 1], self.E[:, 0], np.minimum(Dk[self.E[:, 0]], Dk[self.E[:, 1]])))
        self.E = np.ascontiguousarray(self.E[e])
        if hasattr(self, 'rest_len'):
            self.rest_len = self.rest_len[e]
        free = np.nonzero((self.w > 0) & (src >= 0))[0]
        self.tether = (np.ascontiguousarray(free), np.ascontiguousarray(src[free]), np.ascontiguousarray(D[free]))
        self._hinge_key = Dk


# ------------------------------------------------------------------------------------------------------------ kernels
@nb.njit(**_OPT)
def _distance(p, w, E, rest, alpha, lam):
    for k in range(E.shape[0]):
        i, j = E[k, 0], E[k, 1]
        ws = w[i] + w[j]
        if ws == 0.0:
            continue
        dx = p[i, 0] - p[j, 0]; dy = p[i, 1] - p[j, 1]; dz = p[i, 2] - p[j, 2]
        l = math.sqrt(dx * dx + dy * dy + dz * dz)
        if l < 1e-15:
            continue
        C = l - rest[k]
        dl = (-C - alpha[k] * lam[k]) / (ws + alpha[k])
        lam[k] += dl
        s = dl / l
        p[i, 0] += w[i] * s * dx; p[i, 1] += w[i] * s * dy; p[i, 2] += w[i] * s * dz
        p[j, 0] -= w[j] * s * dx; p[j, 1] -= w[j] * s * dy; p[j, 2] -= w[j] * s * dz


@nb.njit(**_OPT)
def _bending(p, w, H, rest, alpha, lam):
    g = np.empty((4, 3))
    for k in range(H.shape[0]):
        a, b, c, d = H[k, 0], H[k, 1], H[k, 2], H[k, 3]
        if w[a] + w[b] + w[c] + w[d] == 0.0 or alpha[k] < 0.0:
            continue
        th, ok = _dihedral_into(p, a, b, c, d, g)          # (no allocation per hinge: round 3, 5.6 -> see notes)
        if not ok:
            continue
        C = th - rest[k]
        if C > math.pi:
            C -= 2 * math.pi
        elif C < -math.pi:
            C += 2 * math.pi
        den = (w[a] * (g[0, 0] * g[0, 0] + g[0, 1] * g[0, 1] + g[0, 2] * g[0, 2])
               + w[b] * (g[1, 0] * g[1, 0] + g[1, 1] * g[1, 1] + g[1, 2] * g[1, 2])
               + w[c] * (g[2, 0] * g[2, 0] + g[2, 1] * g[2, 1] + g[2, 2] * g[2, 2])
               + w[d] * (g[3, 0] * g[3, 0] + g[3, 1] * g[3, 1] + g[3, 2] * g[3, 2]))
        if den < 1e-24:
            continue
        dl = (-C - alpha[k] * lam[k]) / (den + alpha[k])
        lam[k] += dl
        sa, sb, sc, sd = w[a] * dl, w[b] * dl, w[c] * dl, w[d] * dl
        for j in range(3):
            p[a, j] += sa * g[0, j]
            p[b, j] += sb * g[1, j]
            p[c, j] += sc * g[2, j]
            p[d, j] += sd * g[3, j]


@nb.njit(**_OPT)
def _hold(p, w, T, alpha, lam):
    """each vertex with a finite compliance pulled toward its target: C = |p - t| (zero rest length)."""
    for i in range(p.shape[0]):
        if w[i] == 0.0 or alpha[i] < 0.0:
            continue
        dx = p[i, 0] - T[i, 0]; dy = p[i, 1] - T[i, 1]; dz = p[i, 2] - T[i, 2]
        l = math.sqrt(dx * dx + dy * dy + dz * dz)
        if l < 1e-15:
            continue
        dl = (-l - alpha[i] * lam[i]) / (w[i] + alpha[i])
        lam[i] += dl
        s = w[i] * dl / l
        p[i, 0] += s * dx; p[i, 1] += s * dy; p[i, 2] += s * dz


@nb.njit(**_OPT)
def _tethers(p, w, I, A, dmax):
    """long-range attachments (Kim, Chentanez and Mueller 2012): vertex I[k] no further than dmax[k] (its geodesic rest
    distance) from its anchor A[k] (a pinned vertex). Unilateral: only pulls in."""
    for k in range(I.shape[0]):
        i, a = I[k], A[k]
        if w[i] == 0.0:
            continue
        dx = p[i, 0] - p[a, 0]; dy = p[i, 1] - p[a, 1]; dz = p[i, 2] - p[a, 2]
        l = math.sqrt(dx * dx + dy * dy + dz * dz)
        if l <= dmax[k] or l < 1e-15:
            continue
        s = (l - dmax[k]) / l
        p[i, 0] -= s * dx; p[i, 1] -= s * dy; p[i, 2] -= s * dz


@nb.njit(**_OPT)
def _layer(p, w, P, I, tri, bary, gap):
    """vertex I[k] of this piece kept `gap` outside triangle tri[k] of piece P (its point at bary[k], its normal):
    C = n . (x - q) - gap >= 0. One-way (P doesn't move)."""
    for k in range(I.shape[0]):
        i = I[k]
        if w[i] == 0.0:
            continue
        a, b, c = P[tri[k, 0]], P[tri[k, 1]], P[tri[k, 2]]
        n = np.cross(b - a, c - a)
        ln = math.sqrt((n * n).sum())
        if ln < 1e-18:
            continue
        n = n / ln
        q = bary[k, 0] * a + bary[k, 1] * b + bary[k, 2] * c
        C = ((p[i] - q) * n).sum() - gap[k]
        if C < 0.0:
            p[i] -= C * n


@nb.njit(**_OPT)
def _layer2(p, w, I, tri, bary, gap):
    """vertex I[k] kept gap[k] outside triangle tri[k] of the same system (its point at bary[k], its normal (b - a) x
    (c - a) pointing out): C = n . (x - q) - gap >= 0, both sides moved by their inverse masses."""
    for k in range(I.shape[0]):
        i = I[k]
        a, b, c = tri[k, 0], tri[k, 1], tri[k, 2]
        n = np.cross(p[b] - p[a], p[c] - p[a])
        ln = math.sqrt((n * n).sum())
        if ln < 1e-18:
            continue
        n = n / ln
        q = bary[k, 0] * p[a] + bary[k, 1] * p[b] + bary[k, 2] * p[c]
        C = ((p[i] - q) * n).sum() - gap[k]
        if C >= 0.0:
            continue
        den = w[i] + bary[k, 0] ** 2 * w[a] + bary[k, 1] ** 2 * w[b] + bary[k, 2] ** 2 * w[c]
        if den <= 0.0:
            continue
        dl = -C / den
        p[i] += w[i] * dl * n
        p[a] -= w[a] * bary[k, 0] * dl * n
        p[b] -= w[b] * bary[k, 1] * dl * n
        p[c] -= w[c] * bary[k, 2] * dl * n


@nb.njit(**_OPT)
def _friction(p, x, i, n, depth, surf_disp, mu_s, mu_k):
    """position-based friction for vertex i pushed `depth` out along n: its tangential move relative to the surface
    this substep removed (static) or reduced (kinetic)."""
    rx = p[i, 0] - x[i, 0] - surf_disp[0]
    ry = p[i, 1] - x[i, 1] - surf_disp[1]
    rz = p[i, 2] - x[i, 2] - surf_disp[2]
    dn = rx * n[0] + ry * n[1] + rz * n[2]
    tx = rx - dn * n[0]; ty = ry - dn * n[1]; tz = rz - dn * n[2]
    lt = math.sqrt(tx * tx + ty * ty + tz * tz)
    if lt < 1e-15:
        return
    if lt < mu_s * depth:
        f = 1.0
    else:
        f = min(mu_k * depth / lt, 1.0)
    p[i, 0] -= f * tx; p[i, 1] -= f * ty; p[i, 2] -= f * tz


@nb.njit(**_OPT)
def _collide_capsules(p, x, w, rad, C0, C1, a, mu_s, mu_k, hit):
    """tapered capsules (ax ay az bx by bz ra rb) at the substep's start C0 and end C1; a in [0, 1] the substep's end
    within the frame is already applied to C1. Vertex radius rad (the cloth's half thickness plus clearance)."""
    n = np.empty(3)
    sd = np.empty(3)
    for i in range(p.shape[0]):
        if w[i] == 0.0:
            continue
        for k in range(C1.shape[0]):                  # (scalar: no allocation unless in contact; bit-identical)
            A0_, A1_, A2_ = C1[k, 0], C1[k, 1], C1[k, 2]
            ab0 = C1[k, 3] - A0_; ab1 = C1[k, 4] - A1_; ab2 = C1[k, 5] - A2_
            L2 = ab0 * ab0 + ab1 * ab1 + ab2 * ab2
            t = 0.0
            if L2 > 1e-24:
                t = ((p[i, 0] - A0_) * ab0 + (p[i, 1] - A1_) * ab1 + (p[i, 2] - A2_) * ab2) / L2
                t = min(1.0, max(0.0, t))
            c0 = A0_ + t * ab0; c1 = A1_ + t * ab1; c2 = A2_ + t * ab2
            r = C1[k, 6] + t * (C1[k, 7] - C1[k, 6])
            d0 = p[i, 0] - c0; d1 = p[i, 1] - c1; d2 = p[i, 2] - c2
            ld = math.sqrt(d0 * d0 + d1 * d1 + d2 * d2)
            pen = r + rad[i] - ld
            if pen <= 0.0 or ld < 1e-15:
                continue
            n[0] = d0 / ld; n[1] = d1 / ld; n[2] = d2 / ld
            p[i, 0] += pen * n[0]; p[i, 1] += pen * n[1]; p[i, 2] += pen * n[2]
            # the surface point's own move this substep (the capsule's at the same t)
            sd[0] = c0 - (C0[k, 0] + t * (C0[k, 3] - C0[k, 0]))
            sd[1] = c1 - (C0[k, 1] + t * (C0[k, 4] - C0[k, 1]))
            sd[2] = c2 - (C0[k, 2] + t * (C0[k, 5] - C0[k, 2]))
            _friction(p, x, i, n, pen, sd, mu_s, mu_k)
            hit[i] += 1


@nb.njit(**_OPT)
def _trilinear(G, o, h, q):
    """grid G (nx, ny, nz) of values at o + h * (i, j, k): the value and gradient at q (clamped inside)."""
    nx, ny, nz = G.shape
    fx = (q[0] - o[0]) / h; fy = (q[1] - o[1]) / h; fz = (q[2] - o[2]) / h
    out = False
    if fx < 0 or fy < 0 or fz < 0 or fx > nx - 1 or fy > ny - 1 or fz > nz - 1:
        out = True
    fx = min(max(fx, 0.0), nx - 1.000001); fy = min(max(fy, 0.0), ny - 1.000001); fz = min(max(fz, 0.0), nz - 1.000001)
    i = int(fx); j = int(fy); k = int(fz)
    u = fx - i; v = fy - j; t = fz - k
    c000 = G[i, j, k]; c100 = G[i + 1, j, k]; c010 = G[i, j + 1, k]; c110 = G[i + 1, j + 1, k]
    c001 = G[i, j, k + 1]; c101 = G[i + 1, j, k + 1]; c011 = G[i, j + 1, k + 1]; c111 = G[i + 1, j + 1, k + 1]
    c00 = c000 * (1 - u) + c100 * u; c10 = c010 * (1 - u) + c110 * u
    c01 = c001 * (1 - u) + c101 * u; c11 = c011 * (1 - u) + c111 * u
    c0 = c00 * (1 - v) + c10 * v; c1 = c01 * (1 - v) + c11 * v
    val = c0 * (1 - t) + c1 * t
    gx = ((c100 - c000) * (1 - v) + (c110 - c010) * v) * (1 - t) + ((c101 - c001) * (1 - v) + (c111 - c011) * v) * t
    gy = ((c010 - c000) * (1 - u) + (c110 - c100) * u) * (1 - t) + ((c011 - c001) * (1 - u) + (c111 - c101) * u) * t
    gz = c1 - c0
    g = np.empty(3)
    g[0] = gx / h; g[1] = gy / h; g[2] = gz / h
    return val, g, out


@nb.njit(**_OPT)
def _collide_sdf(p, x, w, rad, G, o, h, R0, t0, R1, t1, mu_s, mu_k, hit):
    """a signed-distance grid (negative inside) carried rigidly: world = R local + t, at the substep's start (R0, t0)
    and end (R1, t1)."""
    for i in range(p.shape[0]):
        if w[i] == 0.0:
            continue
        ql = R1.T @ (p[i] - t1)
        val, g, out = _trilinear(G, o, h, ql)
        if out:
            continue
        pen = rad[i] - val
        if pen <= 0.0:
            continue
        lg = math.sqrt((g * g).sum())
        if lg < 1e-12:
            continue
        n = R1 @ (g / lg)
        p[i] += pen * n
        depth = pen
        for _ in range(3):                           # (Newton on the trilinear field: out to the radius, not its tangent)
            ql2 = R1.T @ (p[i] - t1)
            val2, g2, out2 = _trilinear(G, o, h, ql2)
            pen2 = rad[i] - val2
            lg2 = math.sqrt((g2 * g2).sum())
            if out2 or pen2 <= 0.0 or lg2 < 1e-12:
                break
            p[i] += (pen2 / lg2) * (R1 @ (g2 / lg2))
            depth += pen2 / lg2
        # the surface point's own move this substep (this local point carried from the start's transform to the end's)
        sd = (R1 @ ql + t1) - (R0 @ ql + t0)
        _friction(p, x, i, n, depth, sd, mu_s, mu_k)
        hit[i] += 1


# ------------------------------------------------------------------------------------------------------------ colliders
class Capsules:
    """tapered capsules: rows (a (3), b (3), ra, rb), set per frame (the rig carries them)."""

    def __init__(self, rows, names=None):
        self.rows = np.ascontiguousarray(np.asarray(rows, np.float64).reshape(-1, 8))
        self.prev = self.rows.copy()
        self.names = list(names or [])

    def move(self, rows):
        self.prev = self.rows
        self.rows = np.ascontiguousarray(np.asarray(rows, np.float64).reshape(-1, 8))

    def distance(self, P):
        """signed distance from each point to the union (negative inside)."""
        P = np.asarray(P, float)
        best = np.full(len(P), np.inf)
        for r in self.rows:
            A, B, ra, rb = r[:3], r[3:6], r[6], r[7]
            ab = B - A
            t = np.clip(((P - A) @ ab) / max(1e-24, ab @ ab), 0, 1)
            c = A + t[:, None] * ab
            best = np.minimum(best, np.linalg.norm(P - c, axis=1) - (ra + t * (rb - ra)))
        return best


class SDFGrid:
    """a signed-distance grid (negative inside) over a box, carried rigidly (R, t: world = R local + t)."""

    def __init__(self, G, origin, h):
        self.G = np.ascontiguousarray(np.asarray(G, np.float64))
        self.o = np.asarray(origin, np.float64)
        self.h = float(h)
        self.R = np.eye(3); self.t = np.zeros(3)
        self.R0, self.t0 = self.R, self.t

    @classmethod
    def from_mesh(cls, V, F, h, pad=0.0, box=None, sign='normal', band=None):
        """sampled from a closed mesh's signed distance (charkit.geom.bvh) on a grid of spacing h over its bounding box
        (or `box` (lo, hi)) grown by pad. band: beyond it from the surface only the sign matters (values clamped)."""
        from ..geom.bvh import BVH
        V = np.asarray(V, float)
        lo, hi = (V.min(0), V.max(0)) if box is None else (np.asarray(box[0], float), np.asarray(box[1], float))
        lo, hi = lo - pad, hi + pad
        n = np.maximum(2, np.ceil((hi - lo) / h).astype(int) + 1)
        axes = [lo[k] + h * np.arange(n[k]) for k in range(3)]
        Q = np.stack(np.meshgrid(*axes, indexing='ij'), -1).reshape(-1, 3)
        B = BVH((V, np.asarray(F, np.int64)))
        d = B.signed_distance(Q, sign=sign)
        if band is not None:
            d = np.clip(d, -band, band)
        return cls(d.reshape(tuple(n)), lo, h)

    def move(self, R, t):
        self.R0, self.t0 = self.R, self.t
        self.R, self.t = np.asarray(R, float), np.asarray(t, float)

    def distance(self, P):
        P = np.asarray(P, float)
        out = np.empty(len(P))
        for k, p in enumerate(P):
            out[k] = _trilinear(self.G, self.o, self.h, self.R.T @ (p - self.t))[0]
        return out


# ------------------------------------------------------------------------------------------------------------ solver
class Solver:
    """a cloth under gravity with kinematic pins and hold targets, colliders and layers. `settings` a dict from
    charkit.sim.settings.cloth: gravity (m/s2 vector), substeps, stretch (compliance), bend (per hinge compliance or
    scalar), hold (per vertex compliance, or None), damping (1/s), hang, mu_s, mu_k, radius (m)."""

    def __init__(self, cloth, settings):
        self.c = cloth
        s = dict(settings)
        self.s = s
        n = cloth.n
        self.x = cloth.V.copy()
        self.v = np.zeros((n, 3))
        self.w = cloth.w.copy()
        self.substeps = int(s.get('substeps', 20))
        self.iterations = int(s.get('iterations', 1))
        self.tethers = bool(s.get('tethers', True)) and len(cloth.pins) > 0 and len(cloth.tether[0]) > 0
        self.gravity = np.asarray(s.get('gravity', (0.0, 0.0, -9.81)), float)
        self.damping = float(s.get('damping', 0.0))
        self.hang = float(s.get('hang', 0.0))
        self.mu_s, self.mu_k = float(s.get('mu_s', 0.0)), float(s.get('mu_k', 0.0))
        self.rad = np.broadcast_to(np.asarray(s.get('radius', 0.0), float), (n,)).copy()
        ne, nh = len(cloth.E), len(cloth.H)
        self.a_str = np.broadcast_to(np.asarray(s.get('stretch', 0.0), float), (ne,)).copy()
        bend = s.get('bend', -1.0)                  # -1: no bending constraints
        self.a_bend = np.broadcast_to(np.asarray(bend, float), (nh,)).copy()
        hold = s.get('hold')
        self.a_hold = np.full(n, -1.0) if hold is None else np.broadcast_to(np.asarray(hold, float), (n,)).copy()
        self.pin_x0 = self.x[cloth.pins].copy()
        self.pin_x1 = self.pin_x0.copy()
        self.T0 = cloth.V.copy()
        self.T1 = cloth.V.copy()
        self.colliders = []
        self.layers = []
        self.self_layers = []
        # rest angles eased from `rest_from` to the cloth's own over `rest_ramp` s (a flat pattern let go from the
        # template's shape: the same equilibrium, reached without one huge first projection)
        self.rest_to = cloth.rest_angle.copy()
        self.rest_from = np.asarray(s['rest_from'], float) if s.get('rest_from') is not None else None
        self.rest_ramp = float(s.get('rest_ramp', 0.0))
        self.hits = np.zeros(n, np.int64)
        self.t = 0.0

    # the frame's kinematic targets (at its end; the start is the last frame's end)
    def set_frame(self, pins=None, hold=None, colliders=None):
        if pins is not None:
            self.pin_x0 = self.pin_x1
            self.pin_x1 = np.asarray(pins, float).reshape(-1, 3)
        else:
            self.pin_x0 = self.pin_x1
        if hold is not None:
            self.T0 = self.T1
            self.T1 = np.asarray(hold, float)
        else:
            self.T0 = self.T1
        if colliders is not None:
            self.colliders = list(colliders)

    def add_self_layer(self, I, tri, bary, gap):
        """keep vertices I outside triangles tri (barycentric bary, outward normal by their winding) of this same cloth
        (a flap over the skirt, simulated together): two-way."""
        self.self_layers.append((np.ascontiguousarray(I, np.int64), np.ascontiguousarray(tri, np.int64),
                                 np.ascontiguousarray(bary, np.float64),
                                 np.ascontiguousarray(np.broadcast_to(np.asarray(gap, float), (len(I),)))))

    def add_layer(self, P_ref, I, tri, bary, gap):
        """keep vertices I outside triangles tri (barycentric bary) of the positions P_ref() (a callable: another
        piece's current positions)."""
        self.layers.append((P_ref, np.asarray(I, np.int64), np.asarray(tri, np.int64), np.asarray(bary, float),
                            np.broadcast_to(np.asarray(gap, float), (len(I),)).copy()))

    def step(self, dt):
        c = self.c
        h = dt / self.substeps
        pins = c.pins
        up = -self.gravity / max(1e-12, np.linalg.norm(self.gravity))
        free = self.w > 0
        a_str = self.a_str / (h * h)
        a_bend = np.where(self.a_bend < 0, -1.0, self.a_bend / (h * h))
        a_hold = np.where(self.a_hold < 0, -1.0, self.a_hold / (h * h))
        use_hold = bool((self.a_hold >= 0).any())
        lam_e = np.zeros(len(c.E)); lam_b = np.zeros(len(c.H)); lam_h = np.zeros(c.n)
        caps = [k for k in self.colliders if isinstance(k, Capsules)]
        sdfs = [k for k in self.colliders if isinstance(k, SDFGrid)]
        for k in range(self.substeps):
            a0, a1 = k / self.substeps, (k + 1) / self.substeps
            if self.rest_from is not None:
                f = max(0.0, 1.0 - (self.t + a1 * dt) / max(1e-12, self.rest_ramp))
                c.rest_angle = self.rest_to + f * (self.rest_from - self.rest_to)
            g = np.tile(self.gravity, (c.n, 1))
            if self.hang:
                rising = (self.v @ up) > 0
                g[rising] *= (1.0 - self.hang)
            self.v[free] += h * g[free]
            p = self.x + h * self.v
            if len(pins):
                p[pins] = (1 - a1) * self.pin_x0 + a1 * self.pin_x1
            lam_e[:] = 0.0; lam_b[:] = 0.0; lam_h[:] = 0.0
            T = np.ascontiguousarray((1 - a1) * self.T0 + a1 * self.T1) if use_hold else None
            lay = [(np.ascontiguousarray(P_ref(), np.float64), I, tri, bary, gap)
                   for P_ref, I, tri, bary, gap in self.layers]
            capk = [((1 - a0) * cap.prev + a0 * cap.rows, (1 - a1) * cap.prev + a1 * cap.rows) for cap in caps]
            sdfk = [(sd, _lerp_xf(sd.R0, sd.t0, sd.R, sd.t, a0), _lerp_xf(sd.R0, sd.t0, sd.R, sd.t, a1)) for sd in sdfs]
            for it in range(self.iterations):          # (lambda accumulated: converges to the implicit Euler step)
                _distance(p, self.w, c.E, c.rest_len, a_str, lam_e)
                if self.tethers:
                    _tethers(p, self.w, *c.tether)
                if len(c.H):
                    _bending(p, self.w, c.H, c.rest_angle, a_bend, lam_b)
                if use_hold:
                    _hold(p, self.w, T, a_hold, lam_h)
                for P_, I, tri, bary, gap in lay:
                    _layer(p, self.w, P_, I, tri, bary, gap)
                for I, tri, bary, gap in self.self_layers:
                    _layer2(p, self.w, I, tri, bary, gap)
                for C0, C1 in capk:
                    _collide_capsules(p, self.x, self.w, self.rad, C0, C1, a1, self.mu_s, self.mu_k, self.hits)
                for sd, (R0, t0), (R1, t1) in sdfk:
                    _collide_sdf(p, self.x, self.w, self.rad, sd.G, sd.o, sd.h, R0, t0, R1, t1, self.mu_s, self.mu_k,
                                 self.hits)
            self.v = (p - self.x) / h
            if self.damping:
                self.v *= max(0.0, 1.0 - self.damping * h)
            self.x = p
        self.t += dt

    # measures
    def kinetic(self):
        return 0.5 * float((self.c.mass[:, None] * self.v ** 2).sum())

    def potential(self):
        return -float((self.c.mass * (self.x @ self.gravity)).sum())

    def bending_energy(self):
        """0.5 C^2 / alpha over the compliant hinges."""
        e = 0.0
        for k, (a, b, c_, d) in enumerate(self.c.H):
            if self.a_bend[k] <= 0:
                continue
            th, _, ok = _dihedral(self.x[a], self.x[b], self.x[c_], self.x[d])
            C = (th - self.c.rest_angle[k] + np.pi) % (2 * np.pi) - np.pi
            e += 0.5 * C * C / self.a_bend[k]
        return e

    def strain(self):
        """per edge |l / l0 - 1|."""
        l = np.linalg.norm(self.x[self.c.E[:, 0]] - self.x[self.c.E[:, 1]], axis=1)
        return np.abs(l / np.maximum(self.c.rest_len, 1e-15) - 1.0)


def _lerp_xf(R0, t0, R1, t1, a):
    """a rigid transform a of the way from (R0, t0) to (R1, t1) (rotation by the axis-angle of R1 R0^T)."""
    if a <= 0:
        return np.ascontiguousarray(R0), np.asarray(t0, float)
    if a >= 1:
        return np.ascontiguousarray(R1), np.asarray(t1, float)
    D = R1 @ R0.T
    ang = math.acos(max(-1.0, min(1.0, (np.trace(D) - 1) / 2)))
    if ang < 1e-12:
        Ra = R0
    else:
        ax = np.array([D[2, 1] - D[1, 2], D[0, 2] - D[2, 0], D[1, 0] - D[0, 1]]) / (2 * math.sin(ang))
        Ra = rotation(ax, a * ang) @ R0
    return np.ascontiguousarray(Ra), (1 - a) * np.asarray(t0, float) + a * np.asarray(t1, float)


def rotation(axis, ang):
    """Rodrigues: the rotation by `ang` radians about `axis`."""
    ax = np.asarray(axis, float)
    ax = ax / max(1e-300, np.linalg.norm(ax))
    K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
    return np.eye(3) + math.sin(ang) * K + (1 - math.cos(ang)) * K @ K
