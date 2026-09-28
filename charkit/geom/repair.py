"""Mesh repair and a health report.

    merge_close(m, tol)            weld vertices closer than tol (world units); drops the faces that collapse and duplicates
    clean(m)                       degenerate / duplicate faces and unused vertices out
    orient(m)                      consistent winding across manifold edges, then each part facing outward
    fill_holes(m, max_edges)       close boundary loops up to max_edges long (a fan to the loop's centre)
    remove_small_parts(m, ...)     drop loose parts by face count, area share or size
    report(m)                      open / non-manifold edges, parts, holes, orientation, volume, self-intersection estimate
"""
import numpy as np

from .mesh import (Mesh, as_mesh, boundary_loops, compact, components, face_adjacency, face_areas, face_normals,
                   half_edges, signed_volume, unique_edges)


# ------------------------------------------------------------------------------------------------------------------ welding
def merge_close(m, tol=1e-6, attr='first'):
    """weld vertices within `tol` of each other (clusters by connectivity of close pairs; each cluster takes its lowest
    index's position and attributes, or their mean with attr='mean'), then drop collapsed and duplicate faces."""
    m = as_mesh(m)
    from scipy.spatial import cKDTree
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    n = m.nv
    pairs = cKDTree(m.V).query_pairs(tol, output_type='ndarray') if tol > 0 else np.zeros((0, 2), np.int64)
    if len(pairs) == 0:
        return clean(m)
    A = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(n, n))
    k, lab = connected_components(A, directed=False)
    # the representative: the lowest vertex index of each cluster (deterministic)
    rep = np.full(k, n, np.int64)
    np.minimum.at(rep, lab, np.arange(n))
    new_of_cluster = np.argsort(np.argsort(rep))          # clusters numbered in the order of their representatives
    idx = new_of_cluster[lab]
    order = np.argsort(rep)
    kw = {}
    if attr == 'mean':
        cnt = np.bincount(idx, minlength=k)[:, None]
        V = np.zeros((k, 3)); np.add.at(V, idx, m.V); V /= cnt
        for a in m.vattrs():
            X = np.zeros((k, getattr(m, a).shape[1])); np.add.at(X, idx, getattr(m, a)); X /= cnt
            kw[a] = X
        if 'vn' in kw:
            kw['vn'] /= np.maximum(np.linalg.norm(kw['vn'], axis=1, keepdims=True), 1e-300)
    else:
        V = m.V[rep[order]]
        for a in m.vattrs():
            kw[a] = getattr(m, a)[rep[order]]
    return clean(Mesh(V, idx[m.F], **kw))


def clean(m, area_eps=0.0):
    """drop faces with a repeated vertex, (optionally) near-zero area, and duplicates (the same three vertices in any
    order: of a pair wound opposite ways both go, as they cancel), then unused vertices."""
    m = as_mesh(m)
    F = m.F
    ok = (F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 2] != F[:, 0])
    if area_eps > 0:
        ok &= face_areas(m.V, F) > area_eps
    F2 = F[ok]
    s = np.sort(F2, axis=1)
    _, first, inv, cnt = np.unique(s, axis=0, return_index=True, return_inverse=True, return_counts=True)
    inv = inv.ravel()
    keep = np.zeros(len(F2), bool)
    keep[first] = True
    # duplicates wound opposite ways (a two-sided sliver) cancel: drop the whole group when its windings disagree
    if (cnt > 1).any():
        dup_groups = np.nonzero(cnt > 1)[0]
        g = np.isin(inv, dup_groups)
        fi = np.nonzero(g)[0]
        # canonical winding sign: parity of the permutation from F2 to its sorted order
        par = _perm_parity(F2[fi])
        gi = inv[fi]
        pos = np.bincount(gi, weights=(par == 0), minlength=len(cnt))
        neg = np.bincount(gi, weights=(par == 1), minlength=len(cnt))
        bad = (pos > 0) & (neg > 0)
        keep[np.isin(inv, np.nonzero(bad)[0])] = False
    idx = np.nonzero(ok)[0][np.sort(np.nonzero(keep)[0])]
    out, _ = compact(m, idx)
    return out


def _perm_parity(F):
    """0 when (a, b, c) is an even rotation of its sorted order, else 1."""
    a, b, c = F[:, 0], F[:, 1], F[:, 2]
    even = ((a < b) & (b < c)) | ((b < c) & (c < a)) | ((c < a) & (a < b))
    return np.where(even, 0, 1)


# -------------------------------------------------------------------------------------------------------------- orientation
def orient(m, outward=True):
    """flip faces so neighbours across manifold edges agree (a breadth-first walk per part), then, with outward=True, turn
    each part to face outward: closed parts by their signed volume, open ones by a winding-number test on both sides of
    their faces. Non-orientable parts keep the walk's best effort."""
    m = as_mesh(m)
    F = m.F.copy()
    P, E = face_adjacency(F, manifold_only=True)
    if len(P):
        # consistent iff the shared edge runs opposite ways in the two faces
        def direction(fids, e):
            f = F[fids]
            d = np.zeros(len(fids), np.int64)
            for k in range(3):
                a, b = f[:, k], f[:, (k + 1) % 3]
                d[(a == e[:, 0]) & (b == e[:, 1])] = 1
                d[(a == e[:, 1]) & (b == e[:, 0])] = -1
            return d
        same = direction(P[:, 0], E) == direction(P[:, 1], E)          # same direction: one must flip
        flip = _propagate(len(F), P, same)
        F[flip] = F[flip][:, ::-1]
    out = m.with_(F=F)
    if outward:
        out = _outward(out)
    return out


def _propagate(nf, P, parity):
    """BFS over the face graph: flip[f] so that for every link (i, j, parity) flip[i] ^ flip[j] == parity where possible."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import breadth_first_order, connected_components
    w = parity.astype(np.int8) + 1                                   # 1 = keep, 2 = flip (0 would drop the entry)
    A = coo_matrix((np.r_[w, w], (np.r_[P[:, 0], P[:, 1]], np.r_[P[:, 1], P[:, 0]])), shape=(nf, nf)).tocsr()
    k, lab = connected_components(A, directed=False)
    flip = np.zeros(nf, bool)
    seen = np.zeros(nf, bool)
    firsts = np.unique(lab, return_index=True)[1]
    for root in firsts:
        order, pred = breadth_first_order(A, root, directed=False, return_predecessors=True)
        seen[order] = True
        o = order[1:]
        p = pred[o]
        par = np.asarray(A[o, p]).ravel() == 2
        # flip[o] = flip[p] ^ par, in BFS order (parents first)
        for i in range(len(o)):
            flip[o[i]] = flip[p[i]] ^ par[i]
    return flip


def _outward(m):
    lab, k = components(m.F, by='face')
    F = m.F.copy()
    E, inv, cnt = unique_edges(F)
    open_face = np.zeros(len(F), bool)
    open_face[np.nonzero(cnt[inv] == 1)[0] // 3] = True
    bvh = None
    for c in range(k):
        fi = np.nonzero(lab == c)[0]
        closed = not open_face[fi].any()
        if closed:
            vol = signed_volume(m.V, F[fi])
            if vol < 0:
                F[fi] = F[fi][:, ::-1]
            continue
        # open part: the winding number flips sign with the orientation, and an outward part has it positive on the side
        # its faces turn away from (inside its would-be volume) and about zero on the other: the sum over both sides
        # just off each (sampled) face, weighted by area, is positive when the part faces outward
        if bvh is None:
            from .bvh import BVH
            bvh = BVH(m.with_(F=F))
        s = fi if len(fi) <= 2000 else fi[np.linspace(0, len(fi) - 1, 2000).astype(int)]
        n = face_normals(m.V, F[s]); c_ = m.V[F[s]].mean(1)
        ar = face_areas(m.V, F[s])
        eps = 1e-3 * np.sqrt(ar.sum() / max(1, len(s))) + 1e-9
        wo = bvh.winding_number(c_ + n * eps); wi = bvh.winding_number(c_ - n * eps)
        if np.sum(ar * (wi + wo)) < 0:
            F[fi] = F[fi][:, ::-1]
    return m.with_(F=F)


# -------------------------------------------------------------------------------------------------------------------- holes
def fill_holes(m, max_edges=64, max_size=None):
    """close boundary loops of up to `max_edges` edges (and, with max_size, no wider than it in world units): a triangle for
    a 3-loop, else a fan to a new vertex at the loop's centre (colour and normal averaged from the loop)."""
    m = as_mesh(m)
    loops = boundary_loops(m.F)
    V = [m.V]; Fn = [m.F]
    attrs = {a: [getattr(m, a)] for a in m.vattrs()}
    nv = m.nv
    filled = 0
    for lp in loops:
        if len(lp) > max_edges:
            continue
        P = m.V[lp]
        if max_size is not None and np.linalg.norm(P.max(0) - P.min(0)) > max_size:
            continue
        lp = np.asarray(lp)
        if len(lp) == 3:
            Fn.append(lp[::-1][None])
        else:
            c = P.mean(0)
            V.append(c[None])
            for a in attrs:
                x = getattr(m, a)[lp].mean(0)
                if a == 'vn':
                    x = x / max(np.linalg.norm(x), 1e-300)
                attrs[a].append(x[None])
            nxt = np.roll(lp, -1)
            Fn.append(np.stack([nxt, lp, np.full(len(lp), nv)], 1))      # opposite to the boundary's direction
            nv += 1
        filled += 1
    out = Mesh(np.vstack(V), np.vstack(Fn), **{a: np.vstack(x) for a, x in attrs.items()})
    return out


# ------------------------------------------------------------------------------------------------------------------ parts
def remove_small_parts(m, min_faces=None, min_area_frac=None, min_size=None, keep_largest=None, by='vertex'):
    """drop loose parts: fewer than min_faces faces, less than min_area_frac of the total area, a bounding box diagonal
    below min_size, or beyond the keep_largest biggest (by area). -> Mesh."""
    m = as_mesh(m)
    if m.nf == 0:
        return m
    if by == 'vertex':
        vl, k = components(m.F, m.nv)
        fl = vl[m.F[:, 0]]
    else:
        fl, k = components(m.F, by='face')
    ar = face_areas(m.V, m.F)
    parea = np.bincount(fl, weights=ar, minlength=k)
    pcount = np.bincount(fl, minlength=k)
    keep = np.ones(k, bool)
    if min_faces is not None:
        keep &= pcount >= min_faces
    if min_area_frac is not None:
        keep &= parea >= min_area_frac * parea.sum()
    if min_size is not None:
        lo = np.full((k, 3), np.inf); hi = np.full((k, 3), -np.inf)
        P = m.V[m.F[:, 0]]
        for ax in range(3):
            np.minimum.at(lo[:, ax], fl, m.V[m.F].min(1)[:, ax]); np.maximum.at(hi[:, ax], fl, m.V[m.F].max(1)[:, ax])
        keep &= np.linalg.norm(hi - lo, axis=1) >= min_size
    if keep_largest is not None:
        order = np.argsort(-parea, kind='stable')
        top = np.zeros(k, bool); top[order[:keep_largest]] = True
        keep &= top
    out, _ = compact(m, keep[fl])
    return out


# ------------------------------------------------------------------------------------------------------------------ report
def report(m, self_intersections=True, sample=20000, seed=0):
    """a health report (dict). The counts charkit.trace.health gives a build's trace, under the same names (verts, faces,
    edges, open_edges, nonmanifold_edges, shells, closed_shells, inverted_shells, degenerate_faces, loose_verts, area),
    so kernel numbers and trace numbers compare, plus: parts (= shells), nonmanifold_verts (bow-ties), misoriented_edges,
    boundary_loops, duplicate_faces, watertight, consistently_oriented, volume / euler / genus when watertight, and an
    estimate of self-intersecting faces (from up to `sample` faces)."""
    from ..trace import health
    m = as_mesh(m)
    F = m.F
    r = health(m.V, F)
    if m.nf == 0:
        r.update(parts=0, watertight=False)
        return r
    E, inv, cnt = unique_edges(F)
    r['parts'] = r['shells']
    he = half_edges(F)
    fwd = he[:, 0] < he[:, 1]
    nf_ = np.bincount(inv, weights=fwd, minlength=len(E))
    r['misoriented_edges'] = int(((cnt == 2) & (nf_ != 1)).sum())
    r['boundary_loops'] = len(boundary_loops(F)) if r['open_edges'] else 0
    r['nonmanifold_verts'] = _nonmanifold_verts(F, m.nv)
    s = np.sort(F, axis=1)
    r['duplicate_faces'] = int(len(s) - len(np.unique(s, axis=0)))
    r['watertight'] = bool(r['open_edges'] == 0 and r['nonmanifold_edges'] == 0)
    r['consistently_oriented'] = bool(r['misoriented_edges'] == 0)
    lo, hi = m.bounds()
    r['bounds'] = [lo.round(6).tolist(), hi.round(6).tolist()]
    if r['watertight']:
        r['volume'] = signed_volume(m.V, F)
        chi = m.nv - r['loose_verts'] - len(E) + m.nf
        r['euler'] = int(chi)
        r['genus'] = int((2 * r['shells'] - chi) // 2)
    if self_intersections and m.nf >= 2:
        from .bvh import BVH
        rng = np.random.default_rng(seed)
        idx = np.arange(m.nf) if m.nf <= sample else np.sort(rng.choice(m.nf, sample, replace=False))
        hit = self_intersecting(m, idx, BVH(m))
        frac = float(hit.mean()) if len(idx) else 0.0
        r['self_intersecting_faces_est'] = int(round(frac * m.nf))
        r['self_intersecting_frac'] = round(frac, 5)
        r['self_intersection_sampled'] = int(len(idx))
    return r


def _nonmanifold_verts(F, nv):
    """vertices whose faces don't form one fan (bow-ties): the corners at a vertex, linked when their faces share an edge
    through it, fall into more than one group."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    corners_v = F.ravel().astype(np.int64)
    corner_id = np.arange(len(corners_v))
    nxt = np.roll(F, -1, axis=1).ravel().astype(np.int64)
    prv = np.roll(F, 1, axis=1).ravel().astype(np.int64)
    # the corner's two edges keyed by (vertex, other end): corners with the same key share that edge
    k = np.concatenate([corners_v * nv + nxt, corners_v * nv + prv])
    c = np.concatenate([corner_id, corner_id])
    o = np.argsort(k, kind='stable')
    k, c = k[o], c[o]
    same = np.nonzero(k[1:] == k[:-1])[0]
    A = coo_matrix((np.ones(len(same)), (c[same], c[same + 1])), shape=(len(corner_id), len(corner_id)))
    _, lab = connected_components(A, directed=False)
    groups = np.unique(np.stack([corners_v, lab], 1), axis=0)
    per_v = np.bincount(groups[:, 0], minlength=nv)
    return int((per_v > 1).sum())


def self_intersecting(m, faces, bvh=None):
    """bool per face in `faces`: does it cross another face of the mesh that shares no vertex with it?"""
    from .bvh import BVH, _self_hits
    m = as_mesh(m)
    bvh = bvh or BVH(m)
    faces = np.ascontiguousarray(np.asarray(faces, np.int64))
    return _self_hits(faces, *bvh._args())


def repair(m, weld=None, hole_edges=64, min_part_faces=None, min_part_frac=None, outward=True):
    """the usual chain: weld (tol default 1e-6 of the bbox diagonal), clean, drop small parts, orient, fill small holes."""
    m = as_mesh(m)
    lo, hi = m.bounds()
    diag = float(np.linalg.norm(hi - lo))
    m = merge_close(m, weld if weld is not None else 1e-6 * diag)
    if min_part_faces or min_part_frac:
        m = remove_small_parts(m, min_faces=min_part_faces, min_area_frac=min_part_frac)
    m = orient(m, outward=outward)
    if hole_edges:
        m = fill_holes(m, hole_edges)
    return m


def fix_self_intersections(m, iters=16, rings=1, lam=0.5, steps=3):
    """relax the surface where it crosses itself: the vertices of self-intersecting faces (and `rings` rings round them,
    one more every four rounds that don't clear it) get a few umbrella-smoothing steps, until no face crosses another or
    `iters` rounds pass. -> (Mesh, faces still crossing)."""
    from .smooth import laplacian
    from .mesh import vertex_adjacency
    m = as_mesh(m)
    A = None
    for i in range(iters):
        hit = self_intersecting(m, np.arange(m.nf))
        if not hit.any():
            return m, 0
        mask = np.zeros(m.nv)
        mask[np.unique(m.F[hit])] = 1.0
        if A is None:
            A = vertex_adjacency(m.F, m.nv)
        for _ in range(rings + i // 4):
            mask = np.maximum(mask, (A @ mask > 0).astype(float))
        m = laplacian(m, iters=steps, lam=lam, mask=mask)
    return m, int(self_intersecting(m, np.arange(m.nf)).sum())


def _bad_faces(m):
    """faces that cross another, or sit on a non-manifold edge."""
    hit = self_intersecting(m, np.arange(m.nf))
    E, inv, cnt = unique_edges(m.F)
    nm = cnt[inv] > 2
    if nm.any():
        hit[np.nonzero(nm)[0] // 3] = True
    return hit


def cut_intersections(m, iters=8, grow=1, smooth_steps=4):
    """remove self-crossings that smoothing can't untangle (folds in features thinner than an edge): the crossing faces
    (and any on a non-manifold edge) and `grow` rings round them are cut out, the holes filled with fans, the patches
    relaxed; loose bits the cut frees are dropped. Repeats up to `iters` times. -> (Mesh, faces still bad)."""
    from .smooth import laplacian
    from .mesh import vertex_adjacency
    m = as_mesh(m)
    for i in range(iters):
        hit = _bad_faces(m)
        if not hit.any():
            return m, 0
        vm = np.zeros(m.nv, bool)
        vm[np.unique(m.F[hit])] = True
        A = vertex_adjacency(m.F, m.nv)
        for _ in range(grow + i // 3):
            vm |= (A @ vm.astype(float)) > 0
        drop = vm[m.F].any(1)
        cut, _ = compact(m, ~drop)
        nv0 = cut.nv
        cut = fill_holes(cut, max_edges=10 ** 6)
        cut = remove_small_parts(cut, keep_largest=1)
        # relax the patches: the fan centres and their rings
        mask = np.zeros(cut.nv)
        mask[nv0:] = 1.0
        if cut.nv > nv0:
            A2 = vertex_adjacency(cut.F, cut.nv)
            mask = np.maximum(mask, (A2 @ mask > 0).astype(float))
        m = laplacian(cut, iters=smooth_steps, lam=0.5, mask=mask, pin_boundary=False)
    return m, int(_bad_faces(m).sum())
