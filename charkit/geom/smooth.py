"""Smoothing and normal fields (numpy + scipy.sparse, vectorised).

    taubin(m, iters, lam, mu)              low-pass smoothing without shrinking (Taubin 1995)
    laplacian(m, iters, lam)               plain umbrella smoothing (shrinks; for small touch-ups)
    bilateral_normals(m, iters, ...)       feature-preserving denoise: filter face normals, then move vertices to fit
                                           (Zheng et al. 2011 normal filtering, Sun et al. 2007 vertex update)
    envelope_normals(m, ...)               per-vertex normals from a smoothed envelope of the shape (its closing, blurred):
                                           big clean shadow shapes, the anime way ("shade like one mass")
    smooth_normals(m, vn, iters)           diffuse a per-vertex normal field over the surface
"""
import numpy as np

from .mesh import Mesh, as_mesh, face_normals, face_areas, vertex_normals, boundary_edges


def _umbrella(F, n, weights='uniform', V=None):
    """row-normalised adjacency W (CSR): (W @ V)[i] is the mean of i's neighbours."""
    from scipy.sparse import coo_matrix, diags
    a = np.concatenate([F[:, 0], F[:, 1], F[:, 2], F[:, 1], F[:, 2], F[:, 0]])
    b = np.concatenate([F[:, 1], F[:, 2], F[:, 0], F[:, 0], F[:, 1], F[:, 2]])
    if weights == 'cotan' and V is not None:
        w = np.concatenate([_cot(V, F, k) for k in (2, 0, 1)] * 2)
        w = np.maximum(w, 1e-6)
    else:
        w = np.ones(len(a))
    A = coo_matrix((w, (a, b)), shape=(n, n)).tocsr()
    if weights != 'cotan':
        A.data[:] = 1.0                       # duplicates (edges seen from two faces) summed to 2: back to 1
    deg = np.asarray(A.sum(1)).ravel()
    return diags(1.0 / np.maximum(deg, 1e-12)) @ A


def _cot(V, F, k):
    """cotangent of the angle at corner k (opposite edge (k+1, k+2))."""
    a = V[F[:, (k + 1) % 3]] - V[F[:, k]]
    b = V[F[:, (k + 2) % 3]] - V[F[:, k]]
    c = np.einsum('ij,ij->i', a, b)
    s = np.linalg.norm(np.cross(a, b), axis=1)
    return c / np.maximum(s, 1e-12)


def _pinned(m, pin_boundary):
    if not pin_boundary:
        return None
    B = boundary_edges(m.F)
    p = np.zeros(m.nv, bool)
    p[B.ravel()] = True
    return p


def laplacian(m, iters=5, lam=0.5, pin_boundary=True, mask=None):
    """umbrella smoothing: V += lam (mean of neighbours - V). mask: (N,) weights 0..1 (0 = fixed)."""
    m = as_mesh(m)
    W = _umbrella(m.F, m.nv)
    V = m.V.copy()
    w = np.full(m.nv, lam) if mask is None else lam * np.asarray(mask, float)
    p = _pinned(m, pin_boundary)
    if p is not None:
        w = np.where(p, 0.0, w)
    for _ in range(iters):
        V += w[:, None] * (W @ V - V)
    return m.with_(V=V)


def taubin(m, iters=10, lam=0.5, mu=-0.53, pin_boundary=True, mask=None):
    """Taubin lambda|mu smoothing: alternate a shrinking (lam) and an inflating (mu) umbrella step; removes noise and voxel
    steps while keeping the volume. mask: (N,) 0..1 per-vertex strength."""
    m = as_mesh(m)
    W = _umbrella(m.F, m.nv)
    V = m.V.copy()
    s = np.ones(m.nv) if mask is None else np.asarray(mask, float)
    p = _pinned(m, pin_boundary)
    if p is not None:
        s = np.where(p, 0.0, s)
    for _ in range(iters):
        V += (lam * s)[:, None] * (W @ V - V)
        V += (mu * s)[:, None] * (W @ V - V)
    return m.with_(V=V)


def bilateral_normals(m, iters=5, sigma_s=None, sigma_r=0.35, vertex_iters=10, ring=2):
    """feature-preserving denoise: face normals are filtered by their neighbours' (faces sharing a vertex, `ring` rings),
    weighted by area, spatial distance (sigma_s, default the mean edge length x 1.5) and normal difference (sigma_r, as
    |n_i - n_j|); then vertices move so the faces follow the filtered normals."""
    from scipy.sparse import coo_matrix
    m = as_mesh(m)
    V = m.V.copy(); F = m.F
    # face-face neighbourhood through shared vertices
    nf = len(F)
    VF = coo_matrix((np.ones(3 * nf), (F.ravel(), np.repeat(np.arange(nf), 3))), shape=(m.nv, nf)).tocsr()
    A = (VF.T @ VF).tocsr()
    if ring > 1:
        A = (A @ A).tocsr()
    A.data[:] = 1.0
    A = A.tocoo()
    I, J = A.row, A.col
    el = np.linalg.norm(V[F[:, 1]] - V[F[:, 0]], axis=1).mean()
    ss = sigma_s if sigma_s is not None else 1.5 * el
    for _ in range(iters):
        n = face_normals(V, F)
        c = V[F].mean(1)
        ar = face_areas(V, F)
        ds = np.linalg.norm(c[I] - c[J], axis=1)
        dr = np.linalg.norm(n[I] - n[J], axis=1)
        w = ar[J] * np.exp(-ds ** 2 / (2 * ss ** 2)) * np.exp(-dr ** 2 / (2 * sigma_r ** 2))
        W = coo_matrix((w, (I, J)), shape=(nf, nf)).tocsr()
        nn = W @ n
        nn /= np.maximum(np.linalg.norm(nn, axis=1, keepdims=True), 1e-12)
        V = _fit_normals(V, F, nn, vertex_iters)
    return m.with_(V=V)


def _fit_normals(V, F, N, iters=10):
    """move vertices so faces agree with target normals N (Sun et al. 2007): x_i += 1/|F_i| sum_j n_j (n_j . (c_j - x_i))."""
    V = V.copy()
    nv = len(V)
    cnt = np.bincount(F.ravel(), minlength=nv).astype(float)
    for _ in range(iters):
        c = V[F].mean(1)
        acc = np.zeros_like(V)
        for k in range(3):
            d = np.einsum('ij,ij->i', N, c - V[F[:, k]])
            np.add.at(acc, F[:, k], N * d[:, None])
        V += acc / np.maximum(cnt, 1)[:, None]
    return V


def smooth_normals(m, vn=None, iters=10, lam=0.5):
    """diffuse a per-vertex normal field over the surface (umbrella averaging, renormalised)."""
    m = as_mesh(m)
    N = (vn if vn is not None else (m.vn if m.vn is not None else vertex_normals(m.V, m.F))).copy()
    W = _umbrella(m.F, m.nv)
    for _ in range(iters):
        N = (1 - lam) * N + lam * (W @ N)
        N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
    return N


def envelope_normals(m, h=None, close=None, blur=None, grid=None, occ=None, fallback_mix=0.0, at=None):
    """per-vertex normals from a smoothed envelope: the mesh's solid (winding number; or `occ`, an occupancy Grid), closed
    by `close` (fills the gaps between locks), blurred by `blur` (world units; the shadow shapes' scale), and the normal at
    each vertex = the blurred field's gradient there. Defaults scale with the mesh: h = 1/150 of its size, close = 6 h,
    blur = 8 h. fallback_mix: blend with the geometric normal (0 = pure envelope). at: another mesh whose vertices take
    the normals (m is then only the solid: a shading proxy). -> (N,3) unit normals (at's vertices', given at)."""
    from . import volume
    m = as_mesh(m)
    lo, hi = m.bounds()
    size = float(np.max(hi - lo))
    h = h or size / 150.0
    close = 6 * h if close is None else close
    blur = 8 * h if blur is None else blur
    pad = int(np.ceil((close + 3 * blur) / h)) + 3
    if occ is None:
        G = grid if grid is not None else volume.lattice(lo, hi, h, pad=pad)
        occ = volume.fill_cavities(volume.occupancy(m, grid=G))
    elif close > 0 or blur > 0:
        # room round the solid for the closing and the blur
        occ = occ.like(np.pad(occ.data, pad)) if occ.data.dtype == np.bool_ else occ
        occ.origin = occ.origin - pad * occ.h
    S = volume.as_sdf(occ)
    if close > 0:
        S = volume.closing(S, close)
    S = volume.blur(S, blur)
    q = m if at is None else as_mesh(at)
    g = S.gradient(q.V)
    gn = np.linalg.norm(g, axis=1, keepdims=True)
    geo = vertex_normals(q.V, q.F)
    N = np.where(gn > 1e-6, g / np.maximum(gn, 1e-12), geo)
    if fallback_mix > 0:
        N = (1 - fallback_mix) * N + fallback_mix * geo
        N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
    return N
