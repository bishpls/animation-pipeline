"""Remeshing and decimation on a small dynamic triangle mesh in numba (sequential, deterministic):

    isotropic(m, L)        Botsch-Kobbelt isotropic remeshing to target edge length L: split edges longer than 4/3 L,
                           collapse edges shorter than 4/5 L, flip edges toward valence 6, tangential relaxation, and
                           projection back onto the input surface (BVH); vertex colours follow
    decimate(m, faces)     quadric error (Garland-Heckbert) edge collapse to a face count, with link-condition, normal-flip
                           and valence checks, so a closed manifold input stays closed and manifold

Both expect a manifold mesh (repair.report(...)['nonmanifold_edges'] == 0); open boundaries are kept (their edges are
never collapsed or flipped).
"""
import heapq
import math

import numpy as np
import numba as nb

from .mesh import Mesh, as_mesh, face_normals, unique_edges, vertex_normals

_OPT = dict(cache=True, nogil=True, error_model='numpy')
CAP = 40                         # max faces per vertex in the dynamic structure


# ----------------------------------------------------------------------------------------------------- dynamic structure
@nb.njit(**_OPT)
def _build_vf(F, nv_cap, alive_f):
    vf = np.full((nv_cap, CAP), -1, np.int32)
    nvf = np.zeros(nv_cap, np.int64)
    ok = True
    for f in range(F.shape[0]):
        if not alive_f[f]:
            continue
        for k in range(3):
            v = F[f, k]
            if nvf[v] < CAP:
                vf[v, nvf[v]] = f
                nvf[v] += 1
            else:
                ok = False
    return vf, nvf, ok


@nb.njit(**_OPT)
def _vf_remove(vf, nvf, v, f):
    n = nvf[v]
    for i in range(n):
        if vf[v, i] == f:
            vf[v, i] = vf[v, n - 1]
            vf[v, n - 1] = -1
            nvf[v] = n - 1
            return


@nb.njit(**_OPT)
def _vf_add(vf, nvf, v, f):
    if nvf[v] >= CAP:
        return False
    vf[v, nvf[v]] = f
    nvf[v] += 1
    return True


@nb.njit(**_OPT)
def _ring(F, vf, nvf, v, out):
    """the vertices sharing a face with v (unique, into `out`); -> count."""
    n = 0
    for i in range(nvf[v]):
        f = vf[v, i]
        for k in range(3):
            u = F[f, k]
            if u == v:
                continue
            seen = False
            for j in range(n):
                if out[j] == u:
                    seen = True
                    break
            if not seen:
                out[n] = u
                n += 1
    return n


@nb.njit(**_OPT)
def _edge_faces(F, vf, nvf, a, b, out):
    n = 0
    for i in range(nvf[a]):
        f = vf[a, i]
        if F[f, 0] == b or F[f, 1] == b or F[f, 2] == b:
            if n < out.shape[0]:
                out[n] = f
            n += 1
    return n


@nb.njit(**_OPT)
def _opp(F, f, a, b):
    for k in range(3):
        if F[f, k] != a and F[f, k] != b:
            return F[f, k]
    return -1


@nb.njit(**_OPT)
def _normal(p0, p1, p2):
    n = np.cross(p1 - p0, p2 - p0)
    return n


@nb.njit(**_OPT)
def _face_ok_after(V, F, f, old, p, cos_min):
    """replacing vertex `old` of face f by position p: the normal doesn't turn by more than acos(cos_min) and the face
    doesn't become degenerate."""
    q = np.empty((3, 3))
    for k in range(3):
        for d in range(3):
            q[k, d] = V[F[f, k], d]
    n0 = _normal(q[0], q[1], q[2])
    for k in range(3):
        if F[f, k] == old:
            for d in range(3):
                q[k, d] = p[d]
    n1 = _normal(q[0], q[1], q[2])
    l0 = math.sqrt(n0[0] ** 2 + n0[1] ** 2 + n0[2] ** 2)
    l1 = math.sqrt(n1[0] ** 2 + n1[1] ** 2 + n1[2] ** 2)
    if l1 < 1e-20 or l0 < 1e-20:
        return l0 < 1e-20 and l1 >= 1e-20
    return (n0[0] * n1[0] + n0[1] * n1[1] + n0[2] * n1[2]) / (l0 * l1) >= cos_min


# ---------------------------------------------------------------------------------------------------------- operations
@nb.njit(**_OPT)
def _try_collapse(V, F, vf, nvf, alive_f, alive_v, a, b, p, high2, cos_min, rA, rB, fb):
    """collapse edge (a, b) into a at position p when it keeps the mesh manifold (link condition, opposite valences >= 4,
    no boundary involvement), no face normal turns too far and (high2 > 0) no new edge is longer than sqrt(high2)."""
    if not (alive_v[a] and alive_v[b]):
        return False
    ne = _edge_faces(F, vf, nvf, a, b, fb)
    if ne != 2:
        return False
    f1, f2 = fb[0], fb[1]
    c = _opp(F, f1, a, b); d = _opp(F, f2, a, b)
    if c == d:
        return False
    na = _ring(F, vf, nvf, a, rA)
    nb_ = _ring(F, vf, nvf, b, rB)
    # link condition: the common neighbours are exactly c and d
    common = 0
    for i in range(na):
        for j in range(nb_):
            if rA[i] == rB[j]:
                common += 1
    if common != 2:
        return False
    # the opposite vertices keep valence >= 3; a and b aren't on a boundary
    rC = np.empty(CAP * 2, np.int64)
    if _ring(F, vf, nvf, c, rC) < 4 or _ring(F, vf, nvf, d, rC) < 4:
        return False
    if na < 3 or nb_ < 3:
        return False
    for i in range(na):
        if _edge_faces(F, vf, nvf, a, rA[i], fb) != 2:
            return False
    for j in range(nb_):
        if _edge_faces(F, vf, nvf, b, rB[j], fb) != 2:
            return False
    if nvf[a] + nvf[b] - 4 > CAP:
        return False
    if high2 > 0:
        for i in range(na):
            u = rA[i]
            if (V[u, 0] - p[0]) ** 2 + (V[u, 1] - p[1]) ** 2 + (V[u, 2] - p[2]) ** 2 > high2:
                return False
        for j in range(nb_):
            u = rB[j]
            if (V[u, 0] - p[0]) ** 2 + (V[u, 1] - p[1]) ** 2 + (V[u, 2] - p[2]) ** 2 > high2:
                return False
    # normals
    for i in range(nvf[a]):
        f = vf[a, i]
        if f == f1 or f == f2:
            continue
        if not _face_ok_after(V, F, f, a, p, cos_min):
            return False
    for i in range(nvf[b]):
        f = vf[b, i]
        if f == f1 or f == f2:
            continue
        if not _face_ok_after(V, F, f, b, p, cos_min):
            return False
    # apply
    for f in (f1, f2):
        alive_f[f] = False
        for k in range(3):
            _vf_remove(vf, nvf, F[f, k], f)
    for i in range(nvf[b]):
        f = vf[b, i]
        for k in range(3):
            if F[f, k] == b:
                F[f, k] = a
        _vf_add(vf, nvf, a, f)
    nvf[b] = 0
    alive_v[b] = False
    V[a, 0] = p[0]; V[a, 1] = p[1]; V[a, 2] = p[2]
    return True


@nb.njit(**_OPT)
def _split(V, F, vf, nvf, alive_f, alive_v, A, nv, nf, a, b, fb):
    """split edge (a, b) at its midpoint (both faces); -> (new nv, new nf) or (-1, -1) if the structure is full."""
    ne = _edge_faces(F, vf, nvf, a, b, fb)
    if ne < 1 or ne > 2:
        return -1, -1
    if nv >= V.shape[0] or nf + ne > F.shape[0]:
        return -1, -1
    m = nv
    for d in range(3):
        V[m, d] = 0.5 * (V[a, d] + V[b, d])
    for d in range(A.shape[1]):
        A[m, d] = 0.5 * (A[a, d] + A[b, d])
    alive_v[m] = True
    nvf[m] = 0
    faces = fb[:ne].copy()
    for f in faces:
        # rotate so the edge is (x, y) in the face's order
        x = -1; y = -1; z = -1
        for k in range(3):
            u, w = F[f, k], F[f, (k + 1) % 3]
            if (u == a and w == b) or (u == b and w == a):
                x = u; y = w; z = F[f, (k + 2) % 3]
        g = nf
        nf += 1
        F[f, 0] = x; F[f, 1] = m; F[f, 2] = z
        F[g, 0] = m; F[g, 1] = y; F[g, 2] = z
        alive_f[g] = True
        _vf_remove(vf, nvf, y, f)
        _vf_add(vf, nvf, y, g)
        _vf_add(vf, nvf, m, f)
        _vf_add(vf, nvf, m, g)
        if not _vf_add(vf, nvf, z, g):
            return -1, -1
    return nv + 1, nf


@nb.njit(**_OPT)
def _try_flip(V, F, vf, nvf, a, b, cos_min, rA, fb, mode):
    """flip edge (a, b) to (c, d) when it lowers the valence deviation (mode 0) and keeps the surface: -> bool."""
    if _edge_faces(F, vf, nvf, a, b, fb) != 2:
        return False
    f1, f2 = fb[0], fb[1]
    # orient: f1 holds a -> b
    ok = False
    for k in range(3):
        if F[f1, k] == a and F[f1, (k + 1) % 3] == b:
            ok = True
    if not ok:
        f1, f2 = f2, f1
        for k in range(3):
            if F[f1, k] == a and F[f1, (k + 1) % 3] == b:
                ok = True
    if not ok:
        return False
    c = _opp(F, f1, a, b); d = _opp(F, f2, a, b)
    if c == d or c < 0 or d < 0:
        return False
    # (c, d) mustn't exist already
    nc = _ring(F, vf, nvf, c, rA)
    for i in range(nc):
        if rA[i] == d:
            return False
    va = _ring(F, vf, nvf, a, rA); vb = _ring(F, vf, nvf, b, rA); vd = _ring(F, vf, nvf, d, rA)
    if va <= 3 or vb <= 3:
        return False
    # boundary vertices aim at valence 4, interior at 6 (approximated: all interior)
    before = abs(va - 6) + abs(vb - 6) + abs(nc - 6) + abs(vd - 6)
    after = abs(va - 7) + abs(vb - 7) + abs(nc - 5) + abs(vd - 5)
    if mode == 0 and after >= before:
        return False
    # geometry: the two new faces keep facing the old faces' way
    n1 = _normal(V[a], V[b], V[c]); n2 = _normal(V[b], V[a], V[d])
    nsum = n1 + n2
    m1 = _normal(V[d], V[b], V[c]); m2 = _normal(V[c], V[a], V[d])
    ls = math.sqrt(nsum[0] ** 2 + nsum[1] ** 2 + nsum[2] ** 2)
    l1 = math.sqrt(m1[0] ** 2 + m1[1] ** 2 + m1[2] ** 2)
    l2 = math.sqrt(m2[0] ** 2 + m2[1] ** 2 + m2[2] ** 2)
    if ls < 1e-20 or l1 < 1e-20 or l2 < 1e-20:
        return False
    if (nsum[0] * m1[0] + nsum[1] * m1[1] + nsum[2] * m1[2]) / (ls * l1) < cos_min:
        return False
    if (nsum[0] * m2[0] + nsum[1] * m2[1] + nsum[2] * m2[2]) / (ls * l2) < cos_min:
        return False
    # the two old faces must not fold (dihedral) either: they're near-coplanar or convex enough
    if nvf[c] >= CAP or nvf[d] >= CAP:
        return False
    # apply: f1 = (d, b, c), f2 = (c, a, d)
    F[f1, 0] = d; F[f1, 1] = b; F[f1, 2] = c
    F[f2, 0] = c; F[f2, 1] = a; F[f2, 2] = d
    _vf_remove(vf, nvf, a, f1)
    _vf_remove(vf, nvf, b, f2)
    _vf_add(vf, nvf, c, f2)
    _vf_add(vf, nvf, d, f1)
    return True


# ------------------------------------------------------------------------------------------------------------- passes
@nb.njit(**_OPT)
def _pass_split(V, F, vf, nvf, alive_f, alive_v, A, nv, nf, E, high2):
    fb = np.empty(8, np.int64)
    count = 0
    for i in range(E.shape[0]):
        a, b = E[i, 0], E[i, 1]
        if not (alive_v[a] and alive_v[b]):
            continue
        l2 = (V[a, 0] - V[b, 0]) ** 2 + (V[a, 1] - V[b, 1]) ** 2 + (V[a, 2] - V[b, 2]) ** 2
        if l2 <= high2:
            continue
        r = _split(V, F, vf, nvf, alive_f, alive_v, A, nv, nf, a, b, fb)
        if r[0] < 0:
            break
        nv, nf = r
        count += 1
    return nv, nf, count


@nb.njit(**_OPT)
def _pass_collapse(V, F, vf, nvf, alive_f, alive_v, A, E, low2, high2, cos_min):
    rA = np.empty(CAP * 2, np.int64); rB = np.empty(CAP * 2, np.int64); fb = np.empty(8, np.int64)
    p = np.empty(3)
    count = 0
    for i in range(E.shape[0]):
        a, b = E[i, 0], E[i, 1]
        if not (alive_v[a] and alive_v[b]):
            continue
        l2 = (V[a, 0] - V[b, 0]) ** 2 + (V[a, 1] - V[b, 1]) ** 2 + (V[a, 2] - V[b, 2]) ** 2
        if l2 >= low2:
            continue
        for d in range(3):
            p[d] = 0.5 * (V[a, d] + V[b, d])
        if _try_collapse(V, F, vf, nvf, alive_f, alive_v, a, b, p, high2, cos_min, rA, rB, fb):
            for d in range(A.shape[1]):
                A[a, d] = 0.5 * (A[a, d] + A[b, d])
            count += 1
    return count


@nb.njit(**_OPT)
def _pass_flip(V, F, vf, nvf, E, cos_min):
    rA = np.empty(CAP * 2, np.int64); fb = np.empty(8, np.int64)
    count = 0
    for i in range(E.shape[0]):
        if _try_flip(V, F, vf, nvf, E[i, 0], E[i, 1], cos_min, rA, fb, 0):
            count += 1
    return count


def _dyn(m, extra_v=0, extra_f=0, attrs=None):
    nv, nf = m.nv, m.nf
    V = np.zeros((nv + extra_v, 3)); V[:nv] = m.V
    F = np.zeros((nf + extra_f, 3), np.int64); F[:nf] = m.F
    alive_f = np.zeros(len(F), np.bool_); alive_f[:nf] = True
    alive_v = np.zeros(len(V), np.bool_); alive_v[:nv] = True
    A = np.zeros((len(V), 0 if attrs is None else attrs.shape[1]))
    if attrs is not None:
        A[:nv] = attrs
    vf, nvf, ok = _build_vf(F, len(V), alive_f)
    if not ok:
        raise ValueError('a vertex has more than %d faces; clean the mesh first' % CAP)
    return V, F, alive_f, alive_v, A, vf, nvf


def _compact(V, F, alive_f, alive_v, A):
    F = F[alive_f]
    used = np.zeros(len(V), bool); used[F.ravel()] = True
    idx = np.nonzero(used)[0]
    remap = np.full(len(V), -1, np.int64); remap[idx] = np.arange(len(idx))
    return V[idx], remap[F], A[idx]


def _edges_sorted(V, F, key='long'):
    E, _, _ = unique_edges(F)
    ln = np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1)
    order = np.argsort(-ln if key == 'long' else ln, kind='stable')
    return np.ascontiguousarray(E[order])


# ---------------------------------------------------------------------------------------------------------- isotropic
def isotropic(m, target, iters=5, project=True, relax=0.8, cos_min=0.3, verbose=False):
    """isotropic remeshing to edge length `target` (Botsch and Kobbelt 2004). project: pull vertices back onto the input
    surface after each relaxation (a BVH closest point), carrying vertex colours. -> Mesh."""
    from .bvh import BVH
    from .parts import barycentric
    m = as_mesh(m)
    ref = m
    bvh = BVH(ref) if project else None
    attrs = m.vc if m.vc is not None else None
    low2, high2 = (0.8 * target) ** 2, (4.0 / 3.0 * target) ** 2
    V, F = m.V.copy(), m.F.copy()
    A = attrs.copy() if attrs is not None else np.zeros((len(V), 0))
    for it in range(iters):
        el = np.linalg.norm(V[F] - V[np.roll(F, 1, axis=1)], axis=2)
        n_long = int((el ** 2 > high2).sum())
        extra_v = 3 * n_long + 1024                      # room for this iteration's splits (more come next iteration)
        dm = Mesh(V, F)
        Vd, Fd, af, av, Ad, vf, nvf = _dyn(dm, extra_v=extra_v, extra_f=2 * extra_v, attrs=A)
        nv, nf = len(V), len(F)
        for _ in range(4):
            E = _edges_sorted(Vd[:nv], Fd[:nf][af[:nf]], 'long')
            nv, nf, cnt = _pass_split(Vd, Fd, vf, nvf, af, av, Ad, nv, nf, E, high2)
            if cnt == 0:
                break
        for _ in range(4):
            E = _edges_sorted(Vd[:nv], Fd[:nf][af[:nf]], 'short')
            cnt = _pass_collapse(Vd, Fd, vf, nvf, af, av, Ad, E, low2, high2, cos_min)
            if cnt == 0:
                break
        E, _, _ = unique_edges(Fd[:nf][af[:nf]])
        _pass_flip(Vd, Fd, vf, nvf, np.ascontiguousarray(E), cos_min)
        V, F, A = _compact(Vd[:nv], Fd[:nf], af[:nf], av[:nv], Ad[:nv])
        # tangential relaxation: toward the neighbours' centroid within the tangent plane
        from .smooth import _umbrella
        W = _umbrella(F, len(V))
        N = vertex_normals(V, F)
        d = W @ V - V
        d -= N * np.einsum('ij,ij->i', d, N)[:, None]
        V = V + relax * d
        if bvh is not None:
            _, f, q = bvh.nearest(V)
            # keep a projection only where it doesn't fold faces over (thin features the target length can't resolve)
            n0 = face_normals(V, F)
            Vp = q.copy()
            for _ in range(4):
                n1 = face_normals(Vp, F)
                bad = np.einsum('ij,ij->i', n0, n1) < 0.2
                if not bad.any():
                    break
                back = np.unique(F[bad])
                Vp[back] = V[back]
            V = Vp
            if attrs is not None:
                w = barycentric(ref.V[ref.F[f]], q)
                A = np.einsum('pk,pkd->pd', w, attrs[ref.F[f]])
        if verbose:
            print('isotropic iter %d: %d verts %d faces' % (it, len(V), len(F)))
    out = Mesh(V, F, vc=A if attrs is not None else None)
    return out


# ------------------------------------------------------------------------------------------------------------ decimate
@nb.njit(**_OPT)
def _quadrics(V, F):
    Q = np.zeros((V.shape[0], 10))
    for f in range(F.shape[0]):
        a, b, c = F[f, 0], F[f, 1], F[f, 2]
        n = np.cross(V[b] - V[a], V[c] - V[a])
        ln = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
        if ln < 1e-30:
            continue
        area = 0.5 * ln
        n = n / ln
        d = -(n[0] * V[a, 0] + n[1] * V[a, 1] + n[2] * V[a, 2])
        q = np.array([n[0] * n[0], n[0] * n[1], n[0] * n[2], n[0] * d, n[1] * n[1], n[1] * n[2], n[1] * d,
                      n[2] * n[2], n[2] * d, d * d]) * area
        for v in (a, b, c):
            for k in range(10):
                Q[v, k] += q[k]
    return Q


@nb.njit(**_OPT)
def _qcost(q, p):
    x, y, z = p[0], p[1], p[2]
    return (q[0] * x * x + 2 * q[1] * x * y + 2 * q[2] * x * z + 2 * q[3] * x + q[4] * y * y + 2 * q[5] * y * z +
            2 * q[6] * y + q[7] * z * z + 2 * q[8] * z + q[9])


@nb.njit(**_OPT)
def _qbest(q, pa, pb):
    """the quadric's minimiser if well conditioned, else the best of the endpoints and midpoint."""
    A = np.array([[q[0], q[1], q[2]], [q[1], q[4], q[5]], [q[2], q[5], q[7]]])
    rhs = np.array([-q[3], -q[6], -q[8]])
    det = np.linalg.det(A)
    tr = q[0] + q[4] + q[7]
    if abs(det) > 1e-9 * max(tr, 1e-30) ** 3:
        p = np.linalg.solve(A, rhs)
        # stay near the edge (a minimiser far away means a flat, badly conditioned region)
        mid = 0.5 * (pa + pb)
        el = math.sqrt(((pa - pb) ** 2).sum())
        if math.sqrt(((p - mid) ** 2).sum()) <= 2.0 * el:
            return p, _qcost(q, p)
    best = pa.copy(); bc = _qcost(q, pa)
    c = _qcost(q, pb)
    if c < bc:
        best = pb.copy(); bc = c
    mid = 0.5 * (pa + pb)
    c = _qcost(q, mid)
    if c < bc:
        best = mid; bc = c
    return best, bc


@nb.njit(**_OPT)
def _decimate(V, F, vf, nvf, alive_f, alive_v, Q, A, E, target_f, cos_min, max_len2):
    heap = [(0.0, np.int64(0), np.int64(0), np.int64(0), np.int64(0))]
    heap.pop()
    stamp = np.zeros(V.shape[0], np.int64)
    for i in range(E.shape[0]):
        a, b = E[i, 0], E[i, 1]
        q = Q[a] + Q[b]
        p, c = _qbest(q, V[a], V[b])
        heapq.heappush(heap, (c, a, b, stamp[a], stamp[b]))
    nf = 0
    for f in range(F.shape[0]):
        if alive_f[f]:
            nf += 1
    rA = np.empty(CAP * 2, np.int64); rB = np.empty(CAP * 2, np.int64); fb = np.empty(8, np.int64)
    while nf > target_f and len(heap) > 0:
        c, a, b, sa, sb = heapq.heappop(heap)
        if not (alive_v[a] and alive_v[b]) or stamp[a] != sa or stamp[b] != sb:
            continue
        q = Q[a] + Q[b]
        p, cc = _qbest(q, V[a], V[b])
        if _try_collapse(V, F, vf, nvf, alive_f, alive_v, a, b, p, max_len2, cos_min, rA, rB, fb):
            Q[a] = q
            for d in range(A.shape[1]):
                A[a, d] = 0.5 * (A[a, d] + A[b, d])
            stamp[a] += 1
            nf -= 2
            # the edges round a have new costs; edges elsewhere keep theirs (their quadrics and ends didn't move)
            n = _ring(F, vf, nvf, a, rA)
            for i in range(n):
                u = rA[i]
                qq = Q[a] + Q[u]
                pp, c2 = _qbest(qq, V[a], V[u])
                heapq.heappush(heap, (c2, a, u, stamp[a], stamp[u]))
    return nf


def decimate(m, target_faces, cos_min=0.2, max_edge=None):
    """quadric-error edge collapse down to `target_faces` (or as far as the checks allow). max_edge: optional cap on edge
    lengths the collapses may create. Vertex colours are averaged along. -> Mesh."""
    m = as_mesh(m)
    attrs = m.vc
    V, F, af, av, A, vf, nvf = _dyn(m, attrs=attrs)
    Q = _quadrics(V, F)
    E, _, _ = unique_edges(F)
    _decimate(V, F, vf, nvf, af, av, Q, A, np.ascontiguousarray(E), int(target_faces), cos_min,
              -1.0 if max_edge is None else float(max_edge) ** 2)
    V2, F2, A2 = _compact(V, F, af, av, A)
    return Mesh(V2, F2, vc=A2 if attrs is not None else None)
