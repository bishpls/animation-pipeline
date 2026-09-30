"""Blender's Solidify modifier (simple mode), in numpy (Michael's call J: Solidify leaves Blender). The settings charkit
builds with: offset -1 (the shell goes in against the normals), even thickness off, quality normals off, normals not
flipped, the rim on or off, the edge creases the rims take (garments._thick: the flat, square rims of call L).

    R = solidify.solidify(V, polys, thickness=0.002, uv=corner_uvs, use_rim=True, crease_outer=1.0, crease_inner=1.0)
    R['V'] (2n, 3); R['loopv'], R['counts']; R['parent'] (the input polygon per polygon); R['uv'] per corner;
    R['creases'] (pairs (k, 2), creases (k,)) for the Subdivision Surface after it

As Blender lays it out (measured, charkit/evalmesh.py): the input vertices first, where the offset puts them (offset -1:
unmoved), then their copies moved along the vertex normals (offset -1: t in); the input polygons, then their copies
reversed with their first corner kept (as Blender flips a face), then a rim quad per open edge (b, a, a + n, b + n) for
the edge a -> b as its polygon runs it, its corner UVs those of that polygon at b and a. The vertex normals are
Blender's: the polygons' unit normals weighted by their corner angles. Creases: edge_crease_outer on the input
polygons' open edges, edge_crease_inner on their copies', edge_crease_rim on the rim's cross edges.
"""
import numpy as np


def vertex_normals(V, lv, st, cnt):
    """Blender's vertex normals: each polygon's unit normal (Newell's, which for a quad is the cross of its diagonals, as
    Blender's), weighted by the polygon's angle at the vertex, summed and normalised. Where the sum has no length (a
    loose vertex, on no polygon), Blender's fallback: the vertex's position normalised (measured: the template flaps'
    loose vertices, to 1.2e-7 L)."""
    V = np.asarray(V, float)
    nf = len(cnt)
    fid = np.repeat(np.arange(nf), cnt)
    nxt = np.arange(len(lv)) + 1
    prv = np.arange(len(lv)) - 1
    if nf:
        nxt[st + cnt - 1] = st
        prv[st] = st + cnt - 1
    FN = np.zeros((nf, 3)); np.add.at(FN, fid, np.cross(V[lv], V[lv[nxt]]))
    FN /= np.maximum(np.linalg.norm(FN, axis=1, keepdims=True), 1e-30)
    e1 = V[lv[prv]] - V[lv]; e2 = V[lv[nxt]] - V[lv]
    e1 /= np.maximum(np.linalg.norm(e1, axis=1, keepdims=True), 1e-30)
    e2 /= np.maximum(np.linalg.norm(e2, axis=1, keepdims=True), 1e-30)
    ang = np.arccos(np.clip((e1 * e2).sum(1), -1, 1))
    N = np.zeros_like(V); np.add.at(N, lv, FN[fid] * ang[:, None])
    ln = np.linalg.norm(N, axis=1)
    zero = ln == 0
    N[zero], ln[zero] = V[zero], np.linalg.norm(V[zero], axis=1)
    return N / np.maximum(ln, 1e-30)[:, None]


def _loops(polys):
    if isinstance(polys, tuple) and len(polys) == 2 and np.ndim(polys[1]) == 1 and np.ndim(polys[0]) == 1 and \
            len(polys[1]) and int(np.sum(polys[1])) == len(polys[0]):
        lv, cnt = np.asarray(polys[0], np.int64), np.asarray(polys[1], np.int64)
    elif isinstance(polys, np.ndarray) and polys.ndim == 2:
        lv, cnt = polys.astype(np.int64).ravel(), np.full(len(polys), polys.shape[1], np.int64)
    else:
        cnt = np.array([len(f) for f in polys], np.int64)
        lv = np.concatenate([np.asarray(f, np.int64) for f in polys]) if len(polys) else np.zeros(0, np.int64)
    st = np.r_[0, np.cumsum(cnt)[:-1]].astype(np.int64) if len(cnt) else np.zeros(0, np.int64)
    return lv, st, cnt


def solidify(V, polys, thickness, offset=-1.0, use_rim=True, uv=None, crease_outer=0.0, crease_inner=0.0,
             crease_rim=0.0, use_even_offset=False, use_quality_normals=False, use_flip_normals=False,
             edge_crease_outer=None, edge_crease_inner=None, edge_crease_rim=None):
    """Blender's Solidify (simple; its settings by the modifier's names too: edge_crease_outer ...) -> dict(V, loopv,
    counts, parent, uv (loops, 2) or None, creases (pairs, values), rim (per polygon: a rim quad))."""
    crease_outer = crease_outer if edge_crease_outer is None else edge_crease_outer
    crease_inner = crease_inner if edge_crease_inner is None else edge_crease_inner
    crease_rim = crease_rim if edge_crease_rim is None else edge_crease_rim
    if use_even_offset or use_quality_normals or use_flip_normals:
        raise NotImplementedError('solidify: even offset, quality normals and flipped normals are not ported')
    V = np.asarray(V, float)
    n = len(V)
    lv, st, cnt = _loops(polys)
    nf = len(cnt)
    fid = np.repeat(np.arange(nf), cnt)
    nxt = np.arange(len(lv)) + 1
    if nf:
        nxt[st + cnt - 1] = st
    t = float(thickness)
    ofs_orig = -((1.0 - float(offset)) * 0.5) * t                   # Blender's ofs_orig and ofs_new
    ofs_new = t + ofs_orig
    N = vertex_normals(V, lv, st, cnt)
    # which copy takes which offset (INIT_VERT_ARRAY_OFFSETS, flip off): the first ofs_new when ofs_new >= ofs_orig
    first, second = (ofs_new, ofs_orig) if ofs_new >= ofs_orig else (ofs_orig, ofs_new)
    NV = np.concatenate([V + first * N, V + second * N])
    # the copies: reversed, first corner kept
    rl = np.arange(len(lv))
    k = rl - st[fid]
    rev = st[fid] + np.where(k == 0, 0, cnt[fid] - k)                # corner k of the copy is corner -k of the input
    lv2 = lv[rev] + n
    out_lv = [lv, lv2]
    out_cnt = [cnt, cnt]
    parent = [np.arange(nf), np.arange(nf)]
    U = None
    if uv is not None:
        Uc = np.asarray(uv, float).reshape(-1, 2) if isinstance(uv, np.ndarray) else \
            np.concatenate([np.asarray(c, float).reshape(-1, 2) for c in uv])
        U = [Uc, Uc[rev]]
    a, b = lv, lv[nxt]
    key = np.minimum(a, b) * n + np.maximum(a, b)
    _, inv, ecnt = np.unique(key, return_inverse=True, return_counts=True)
    open_ = np.nonzero(ecnt[inv] == 1)[0]                           # the loops running open edges
    pairs, vals = [], []
    if use_rim and len(open_):
        ra, rb = a[open_], b[open_]
        out_lv.append(np.stack([rb, ra, ra + n, rb + n], 1).ravel())
        out_cnt.append(np.full(len(open_), 4, np.int64))
        parent.append(fid[open_])
        if U is not None:
            ua, ub = Uc[open_], Uc[nxt[open_]]
            U.append(np.stack([ub, ua, ua, ub], 1).reshape(-1, 2))
        if crease_rim > 0:
            cr = np.unique(np.concatenate([ra, rb]))
            pairs.append(np.stack([cr, cr + n], 1)); vals.append(np.full(len(cr), float(crease_rim)))
    if len(open_):
        oe = np.stack([a[open_], b[open_]], 1)
        if crease_outer > 0:
            pairs.append(oe); vals.append(np.full(len(oe), float(crease_outer)))
        if crease_inner > 0:
            pairs.append(oe + n); vals.append(np.full(len(oe), float(crease_inner)))
    creases = (np.concatenate(pairs).astype(np.int64), np.concatenate(vals)) if pairs else \
        (np.zeros((0, 2), np.int64), np.zeros(0))
    rim = np.concatenate([np.zeros(2 * nf, bool), np.ones(len(open_) if use_rim else 0, bool)])
    return dict(V=NV, loopv=np.concatenate(out_lv), counts=np.concatenate(out_cnt), parent=np.concatenate(parent),
                uv=np.concatenate(U) if U is not None else None, creases=creases, rim=rim)
