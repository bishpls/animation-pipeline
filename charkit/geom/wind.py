"""The garments' winding, decided once in the venv (GEOM_TRUTH rollout step 7a). garments._object used to leave it to
Blender (bmesh.ops.recalc_face_normals) and the evaluator re-derived it with a port (bodyeval.recalc_normals); the two
disagreed on the hull puff sleeves (0 of 1,856 polygons), putting the Solidify shell on opposite sides. Now the
recording winds each piece here and Blender takes the faces as given.

The rule: each region (polygons joined through manifold edges, as BMesh groups them) wound consistently from its first
polygon, then turned so its normals face away from the region's centre: the sign of the area-weighted sum of
(polygon centre - region centre) . polygon normal, a flux through the surface that is the enclosed volume for a closed
region and stays well away from zero for the garments' open tubes and curved sheets. A reversed polygon keeps its first
corner ([v0, v(n-1), ..., v1], as BMesh reverses it), so the evaluated meshes' child quads start where they did.

numpy only (it also runs in Blender's Python for the old in-Blender garments path).
"""
import numpy as np


def _loops(polys):
    cnt = np.array([len(f) for f in polys], np.int64)
    lv = np.concatenate([np.asarray(f, np.int64) for f in polys]) if len(polys) else np.zeros(0, np.int64)
    st = np.r_[0, np.cumsum(cnt)[:-1]].astype(np.int64) if len(cnt) else np.zeros(0, np.int64)
    return lv, st, cnt


def reverse(f):
    """a polygon reversed as BMesh reverses it: its first corner kept."""
    f = list(f)
    return f[:1] + f[:0:-1]


def consistent(V, polys):
    """per polygon whether to reverse it so that each region (joined through edges with exactly two polygons) is wound
    consistently from its first polygon, and the region per polygon. -> (flip (nf,) bool, region (nf,) int)."""
    lv, st, cnt = _loops(polys)
    nf, n = len(cnt), len(V)
    fid = np.repeat(np.arange(nf), cnt)
    nxt = np.arange(len(lv)) + 1
    if nf:
        nxt[st + cnt - 1] = st
    a, b = lv, lv[nxt]
    key = np.minimum(a, b) * n + np.maximum(a, b)
    order = np.argsort(key, kind='stable')
    ks = key[order]
    _, first, count = np.unique(ks, return_index=True, return_counts=True)
    two = first[count == 2]
    i, j = order[two], order[two + 1]                       # the two loops over each manifold edge
    rel = a[i] == a[j]                                       # both run the edge the same way: one must turn
    adj = [[] for _ in range(nf)]
    for x, y, r in zip(fid[i].tolist(), fid[j].tolist(), rel.tolist()):
        adj[x].append((y, r)); adj[y].append((x, r))
    flip = np.zeros(nf, bool)
    region = np.full(nf, -1, np.int64)
    nr = 0
    for f0 in range(nf):
        if region[f0] >= 0:
            continue
        region[f0] = nr
        stack = [f0]
        while stack:
            f = stack.pop()
            for g, r in adj[f]:
                if region[g] < 0:
                    region[g] = nr
                    flip[g] = flip[f] ^ r
                    stack.append(g)
        nr += 1
    return flip, region


def flux(V, polys, flip, region):
    """per region the area-weighted sum of (polygon centre - region centre) . unit normal (the normals as `flip` winds
    them), and the sum of its absolute terms (its conditioning). -> (flux (nr,), scale (nr,))."""
    V = np.asarray(V, float)
    lv, st, cnt = _loops(polys)
    nf = len(cnt)
    fid = np.repeat(np.arange(nf), cnt)
    nxt = np.arange(len(lv)) + 1
    if nf:
        nxt[st + cnt - 1] = st
    N = np.zeros((nf, 3)); np.add.at(N, fid, np.cross(V[lv], V[lv[nxt]]))      # Newell: 2 x area x unit normal
    N[flip] *= -1
    area = np.linalg.norm(N, axis=1) / 2
    C = np.zeros((nf, 3)); np.add.at(C, fid, V[lv]); C /= np.maximum(cnt, 1)[:, None]
    nr = int(region.max()) + 1 if nf else 0
    w = np.bincount(region, area, minlength=nr)
    RC = np.stack([np.bincount(region, C[:, k] * area, minlength=nr) for k in range(3)], 1) / np.maximum(w, 1e-30)[:, None]
    t = ((C - RC[region]) * N).sum(1) / 2                   # area x (c - centre) . unit normal
    return np.bincount(region, t, minlength=nr), np.bincount(region, np.abs(t), minlength=nr)


def orient(V, polys, uv_corner=None):
    """polys wound consistently per region with the normals facing out (the module's rule). uv_corner: per-polygon
    corner UVs, reversed alongside. -> (polys [tuple], uv_corner or None, flip (nf,) bool, dict(regions, flux, scale))."""
    flip, region = consistent(V, polys)
    fx, sc = flux(V, polys, flip, region)
    turn = fx < 0
    flip = flip ^ turn[region]
    P = [tuple(int(x) for x in (reverse(f) if fl else f)) for f, fl in zip(polys, flip)]
    U = None
    if uv_corner is not None:
        U = [(np.concatenate([np.asarray(u)[:1], np.asarray(u)[:0:-1]]) if fl else u) for u, fl in zip(uv_corner, flip)]
        if not isinstance(uv_corner[0], np.ndarray) if len(uv_corner) else False:
            U = [[tuple(c) for c in u] if isinstance(u, np.ndarray) else u for u in U]
    info = dict(regions=int(len(fx)), flux=np.where(turn, -fx, fx), scale=sc)
    return P, U, flip, info
