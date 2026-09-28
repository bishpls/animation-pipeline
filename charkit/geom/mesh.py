"""The triangle mesh the kernel passes around, and its topology (numpy only).

A Mesh is plain arrays: V (N,3) float64, F (M,3) int64, optional per-vertex attributes: vc (N,3) colour (sRGB 0..1),
vn (N,3) normals, uv (N,2). Every operation returns a new Mesh (or arrays); nothing is modified in place. Quads or
polygons given to `Mesh.from_polys` are fanned into triangles.
"""
import numpy as np


class Mesh:
    __slots__ = ('V', 'F', 'vc', 'vn', 'uv')

    def __init__(self, V, F, vc=None, vn=None, uv=None):
        self.V = np.ascontiguousarray(V, dtype=np.float64).reshape(-1, 3)
        self.F = np.ascontiguousarray(F, dtype=np.int64).reshape(-1, 3)
        self.vc = None if vc is None else np.ascontiguousarray(vc, dtype=np.float64)
        self.vn = None if vn is None else np.ascontiguousarray(vn, dtype=np.float64)
        self.uv = None if uv is None else np.ascontiguousarray(uv, dtype=np.float64)

    @classmethod
    def from_polys(cls, V, polys, **kw):
        """triangulate polygons (lists of vertex indices, any length >= 3) by fans."""
        tris = []
        for p in polys:
            p = list(p)
            for k in range(1, len(p) - 1):
                tris.append((p[0], p[k], p[k + 1]))
        return cls(V, np.array(tris, np.int64).reshape(-1, 3), **kw)

    def copy(self):
        c = lambda a: None if a is None else a.copy()
        return Mesh(self.V.copy(), self.F.copy(), c(self.vc), c(self.vn), c(self.uv))

    def with_(self, **kw):
        """a copy with some arrays replaced (V=..., F=..., vc=...)."""
        d = {k: getattr(self, k) for k in self.__slots__}
        d.update(kw)
        return Mesh(**d)

    @property
    def nv(self):
        return len(self.V)

    @property
    def nf(self):
        return len(self.F)

    def __repr__(self):
        return f'Mesh({self.nv} verts, {self.nf} tris)'

    def bounds(self):
        return self.V.min(0), self.V.max(0)

    def vattrs(self):
        """the per-vertex attribute names that are set."""
        return [k for k in ('vc', 'vn', 'uv') if getattr(self, k) is not None]


def as_mesh(m, F=None):
    if isinstance(m, Mesh):
        return m
    if F is not None:
        return Mesh(m, F)
    if isinstance(m, (tuple, list)) and len(m) == 2:
        return Mesh(np.asarray(m[0]), np.asarray(m[1]))
    raise TypeError('expected a Mesh or (V, F)')


# ------------------------------------------------------------------------------------------------------------ geometry
def face_normals(V, F, unit=True):
    """(M,3) face normals (unit, or area-weighted: |n| = 2 * area when unit=False)."""
    n = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    if not unit:
        return n
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    return n / np.maximum(ln, 1e-300)


def face_areas(V, F):
    return 0.5 * np.linalg.norm(face_normals(V, F, unit=False), axis=1)


def vertex_normals(V, F, weight='angle'):
    """per-vertex unit normals: 'angle' (angle-weighted: the pseudo-normal, good for signs) or 'area'."""
    n = face_normals(V, F, unit=False)
    if weight == 'area':
        w = np.ones((len(F), 3))
        nf = n
    else:
        nf = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-300)
        w = corner_angles(V, F)
    out = np.zeros_like(V)
    for k in range(3):
        np.add.at(out, F[:, k], nf * w[:, k:k + 1])
    ln = np.linalg.norm(out, axis=1, keepdims=True)
    return out / np.maximum(ln, 1e-300)


def corner_angles(V, F):
    """(M,3) interior angles of each triangle at its corners."""
    out = np.zeros((len(F), 3))
    for k in range(3):
        a = V[F[:, (k + 1) % 3]] - V[F[:, k]]
        b = V[F[:, (k + 2) % 3]] - V[F[:, k]]
        na = np.linalg.norm(a, axis=1); nb = np.linalg.norm(b, axis=1)
        c = np.einsum('ij,ij->i', a, b) / np.maximum(na * nb, 1e-300)
        out[:, k] = np.arccos(np.clip(c, -1, 1))
    return out


def signed_volume(V, F):
    """the enclosed volume (positive for a closed, outward-oriented mesh)."""
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    return float(np.einsum('ij,ij->i', a, np.cross(b, c)).sum() / 6.0)


def area(V, F):
    return float(face_areas(V, F).sum())


def edge_lengths(V, F):
    """(M,3) lengths of edges (F[:,k], F[:,k+1])."""
    return np.stack([np.linalg.norm(V[F[:, (k + 1) % 3]] - V[F[:, k]], axis=1) for k in range(3)], 1)


# ------------------------------------------------------------------------------------------------------------ topology
def half_edges(F):
    """(3M,2) directed edges (a -> b) in face order: row 3*f + k is (F[f,k], F[f,k+1])."""
    return np.stack([F, np.roll(F, -1, axis=1)], 2).reshape(-1, 2)


def unique_edges(F):
    """-> (E (K,2) sorted undirected edges, inverse (3M,) half-edge -> edge index, count (K,) faces per edge)."""
    he = half_edges(F)
    s = np.sort(he, axis=1)
    E, inv, cnt = np.unique(s, axis=0, return_inverse=True, return_counts=True)
    return E, inv.ravel(), cnt


def edge_key(a, b, n):
    """a unique int64 key per undirected edge (for n vertices)."""
    lo, hi = np.minimum(a, b), np.maximum(a, b)
    return lo.astype(np.int64) * np.int64(n) + hi.astype(np.int64)


def boundary_edges(F):
    """directed boundary half-edges (used by exactly one face), oriented as in their face."""
    he = half_edges(F)
    E, inv, cnt = unique_edges(F)
    return he[cnt[inv] == 1]


def nonmanifold_edges(F):
    E, inv, cnt = unique_edges(F)
    return E[cnt > 2]


def face_adjacency(F, manifold_only=True):
    """pairs of faces sharing an edge: (P (K,2) face pairs, edge (K,2) the shared vertex pair). manifold_only: only edges
    with exactly two faces."""
    he = half_edges(F)
    s = np.sort(he, axis=1)
    key = s[:, 0].astype(np.int64) * (int(F.max()) + 1 if len(F) else 1) + s[:, 1]
    order = np.argsort(key, kind='stable')
    ks = key[order]
    fid = order // 3
    if manifold_only:
        # runs of length exactly 2
        start = np.r_[True, ks[1:] != ks[:-1]]
        idx = np.nonzero(start)[0]
        runlen = np.diff(np.r_[idx, len(ks)])
        two = idx[runlen == 2]
        P = np.stack([fid[two], fid[two + 1]], 1)
        return P, s[order[two]]
    same = ks[1:] == ks[:-1]
    i = np.nonzero(same)[0]
    P = np.stack([fid[i], fid[i + 1]], 1)
    return P, s[order[i]]


def components(F, nv=None, by='vertex'):
    """connected components: -> (labels, count). by='vertex': per vertex, connected through faces (unused vertices get
    their own labels); by='face': per face, faces connected through shared edges."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    if by == 'face':
        P, _ = face_adjacency(F, manifold_only=False)
        n = len(F)
        A = coo_matrix((np.ones(len(P)), (P[:, 0], P[:, 1])), shape=(n, n))
    else:
        n = int(nv if nv is not None else (F.max() + 1 if len(F) else 0))
        he = half_edges(F)
        A = coo_matrix((np.ones(len(he)), (he[:, 0], he[:, 1])), shape=(n, n))
    k, lab = connected_components(A, directed=False)
    return lab, k


def vertex_adjacency(F, n):
    """the symmetric vertex adjacency as a scipy CSR matrix (1 per edge)."""
    from scipy.sparse import coo_matrix
    he = half_edges(F)
    A = coo_matrix((np.ones(len(he)), (he[:, 0], he[:, 1])), shape=(n, n)).tocsr()
    A = ((A + A.T) > 0).astype(np.float64)
    return A


def boundary_loops(F):
    """the boundary as closed loops of vertex indices (lists), following the faces' orientation. Vertices where several
    loops touch are split greedily."""
    B = boundary_edges(F)
    if len(B) == 0:
        return []
    nxt = {}
    for a, b in B:
        nxt.setdefault(int(a), []).append(int(b))
    loops = []
    used = set()
    for a0, b0 in B:
        a0, b0 = int(a0), int(b0)
        if (a0, b0) in used:
            continue
        loop = [a0]
        used.add((a0, b0))
        cur = b0
        guard = 0
        while cur != a0 and guard < len(B) + 2:
            loop.append(cur)
            cands = [c for c in nxt.get(cur, []) if (cur, c) not in used]
            if not cands:
                break
            c = cands[0]
            used.add((cur, c))
            cur = c
            guard += 1
        if cur == a0 and len(loop) >= 3:
            loops.append(loop)
    return loops


def compact(m, keep_faces=None):
    """drop faces (keep_faces: bool (M,) or indices) and then unused vertices; per-vertex attributes follow.
    -> (Mesh, old vertex index per new vertex)."""
    F = m.F if keep_faces is None else m.F[keep_faces]
    used = np.zeros(m.nv, bool)
    used[F.ravel()] = True
    idx = np.nonzero(used)[0]
    remap = np.full(m.nv, -1, np.int64)
    remap[idx] = np.arange(len(idx))
    kw = {k: getattr(m, k)[idx] for k in m.vattrs()}
    return Mesh(m.V[idx], remap[F], **kw), idx


def concatenate(meshes):
    """one mesh from several (attributes kept only when every mesh has them)."""
    meshes = [as_mesh(x) for x in meshes]
    off = np.cumsum([0] + [x.nv for x in meshes])[:-1]
    kw = {}
    for k in ('vc', 'vn', 'uv'):
        if all(getattr(x, k) is not None for x in meshes):
            kw[k] = np.vstack([getattr(x, k) for x in meshes])
    return Mesh(np.vstack([x.V for x in meshes]), np.vstack([x.F + o for x, o in zip(meshes, off)]), **kw)


def transform(m, M):
    """apply a 4x4 (or 3x3) matrix to the vertices (normals rotated by the inverse transpose)."""
    M = np.asarray(M, float)
    if M.shape == (3, 3):
        R, t = M, np.zeros(3)
    else:
        R, t = M[:3, :3], M[:3, 3]
    kw = {}
    if m.vn is not None:
        N = m.vn @ np.linalg.inv(R)
        kw['vn'] = N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-300)
    out = m.with_(V=m.V @ R.T + t, **kw)
    if np.linalg.det(R) < 0:
        out = out.with_(F=out.F[:, ::-1].copy())
    return out


def y_up_to_z_up(m):
    """glTF's frame (y up, -z forward... the front faces +z) to Blender's (z up): (x, y, z) -> (x, -z, y), as Blender's
    glTF importer does."""
    R = np.array([[1.0, 0, 0], [0, 0, -1.0], [0, 1.0, 0]])
    return transform(m, R)


def z_up_to_y_up(m):
    R = np.array([[1.0, 0, 0], [0, 0, 1.0], [0, -1.0, 0]])
    return transform(m, R)
