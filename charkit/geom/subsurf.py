"""Blender's Subdivision Surface, in numpy (Michael's call J: subdivision leaves Blender). Catmull-Clark as OpenSubdiv
(Sdc, the Catmark scheme; Apache-2.0, its rules read, not its code) refines and evaluates it with the modifier's
settings as charkit builds them: limit surface on, creases on (sharp and semi-sharp edges, vertex creases), boundaries
smooth ('ALL': the open edges sharp, their corners not), UVs smoothed inside and kept linear along their boundaries
('PRESERVE_BOUNDARIES').

    R = subsurf.subdivide(V, polys, levels=1, creases={(a, b): 1.0}, uv=per_corner_uvs)
    R['V'] (n, 3) at the limit surface; R['quads'] (m, 4); R['parent'] (m,) the input polygon per quad;
    R['uv'] (m, 4, 2) per corner; R['carry'] per-vertex data carried as Blender carries vertex data (vertex groups;
    carry_rule='limit': through the positions' own stencil, the skin weights charkit ships)

The refined mesh's vertices are ordered as Blender's: the input vertices, then one per input edge, then one per polygon
(each level). Each child quad starts where Blender's does, so a fan triangulation cuts it along the same diagonal.

The rules (OpenSubdiv Sdc, Catmark, crease method uniform):
- an edge's sharpness s: Blender's crease c in 0..1 gives s = CREASE_TO_SHARPNESS(c); open edges and non-manifold edges
  are infinitely sharp (s = 10). A child edge has s - 1 (infinity stays).
- the edge point: smooth (a + b + the two face points) / 4; sharp (s >= 1) the midpoint; between, s of the way.
- the vertex point by rule: smooth (0 or 1 sharp edges: Q/n + 2R/n + (n - 3) v / n), crease (2: (a + 6 v + b) / 8),
  corner (3 or more, or a vertex crease: v). When the child's rule differs from the parent's (a semi-sharp edge decays
  to smooth), the two are blended by the mean sharpness of the edges that decayed.
- the limit: smooth (n^2 v + 4 sum(edge neighbours) + sum(diagonals)) / (n (n + 5)); crease (a + 4 v + b) / 6; corner v.
  Semi-sharp features are refined out first (the limit surface is the same at every level).
"""
import numpy as np

INF = 10.0                              # Sdc::Crease::SHARPNESS_INFINITE
UV_LIMIT = 1e-4                         # Blender's STD_UV_CONNECT_LIMIT: a vertex's corners this close share a UV value


def crease_sharpness(c):
    """Blender's edge crease (0..1) as OpenSubdiv's sharpness (BKE_subdiv_crease_to_sharpness_f)."""
    c = np.asarray(c, float)
    return np.minimum(c * c * 10.0, INF)


# ------------------------------------------------------------------------------------------------------------ topology
class Topo:
    """a polygon mesh's connectivity: loops (lv), polygon starts and counts, the edges (unique vertex pairs) and per loop
    the edge from its corner to the next."""

    def __init__(self, nv, lv, cnt):
        self.nv = nv
        self.lv = np.asarray(lv, np.int64)
        self.cnt = np.asarray(cnt, np.int64)
        self.nf = len(self.cnt)
        self.st = np.r_[0, np.cumsum(self.cnt)[:-1]].astype(np.int64) if self.nf else np.zeros(0, np.int64)
        self.fid = np.repeat(np.arange(self.nf), self.cnt)
        n = len(self.lv)
        self.nxt = np.arange(n) + 1
        self.prv = np.arange(n) - 1
        if self.nf:
            self.nxt[self.st + self.cnt - 1] = self.st
            self.prv[self.st] = self.st + self.cnt - 1
        a, b = self.lv, self.lv[self.nxt]
        self.lkey = np.minimum(a, b) * nv + np.maximum(a, b)
        self.ekey, self.einv, self.ecnt = np.unique(self.lkey, return_inverse=True, return_counts=True)
        self.ne = len(self.ekey)
        self.ea, self.eb = self.ekey // nv, self.ekey % nv

    def edge_index(self, pairs):
        """vertex pairs -> their edge indices (-1 where no such edge)."""
        P = np.asarray(pairs, np.int64).reshape(-1, 2)
        k = np.minimum(P[:, 0], P[:, 1]) * self.nv + np.maximum(P[:, 0], P[:, 1])
        i = np.clip(np.searchsorted(self.ekey, k), 0, max(self.ne - 1, 0))
        return np.where(self.ne and (self.ekey[i] == k), i, -1) if self.ne else np.full(len(k), -1)


def _sum_at(n, idx, vals):
    out = np.zeros((n,) + vals.shape[1:])
    np.add.at(out, idx, vals)
    return out


def _rules(T, es, vs):
    """per vertex: its rule (0 smooth, 1 crease, 2 corner) from the edges' and its own sharpness, and per vertex the sum
    of the other ends of its sharp edges (for the crease masks)."""
    sharp = es > 0
    ns = np.bincount(np.r_[T.ea[sharp], T.eb[sharp]], minlength=T.nv)
    rule = np.where((vs > 0) | (ns > 2), 2, np.where(ns == 2, 1, 0))
    return rule, sharp


def _decay(s):
    return np.where(s >= INF, INF, np.maximum(s - 1.0, 0.0))


# ------------------------------------------------------------------------------------------------------------ refine
def refine(V, T, es, vs, rotate=True):
    """one level of Catmark. V (n, d); T: Topo; es (ne,) edge sharpness; vs (n,) vertex sharpness. -> (V1, lv1, cnt1,
    es-by-child-edge as (pairs, sharpness), vs1, parent polygon per child)."""
    V = np.asarray(V, float)
    n, ne, nf = T.nv, T.ne, T.nf
    d = V.shape[1:]
    FP = _sum_at(nf, T.fid, V[T.lv]) / T.cnt.reshape((-1,) + (1,) * len(d))
    # edge points
    mid = (V[T.ea] + V[T.eb]) / 2
    efs = _sum_at(ne, T.einv, FP[T.fid])
    two = T.ecnt == 2
    smooth_e = np.where(two.reshape((-1,) + (1,) * len(d)), (V[T.ea] + V[T.eb] + efs) / 4, mid)
    w = np.clip(es, 0.0, 1.0).reshape((-1,) + (1,) * len(d))
    EP = w * mid + (1 - w) * smooth_e
    # vertex points
    val = np.bincount(np.r_[T.ea, T.eb], minlength=n)
    nfv = np.bincount(T.lv, minlength=n)
    shp = lambda x: x.reshape((-1,) + (1,) * len(d))
    Q = _sum_at(n, T.lv, FP[T.fid]) / shp(np.maximum(nfv, 1))
    R = (_sum_at(n, T.ea, mid) + _sum_at(n, T.eb, mid)) / shp(np.maximum(val, 1))
    nn = shp(np.maximum(val, 1).astype(float))
    smooth_v = (Q + 2 * R + (nn - 3) * V) / nn

    def crease_v(sharp):
        oth = _sum_at(n, T.ea[sharp], V[T.eb[sharp]]) + _sum_at(n, T.eb[sharp], V[T.ea[sharp]])
        return (oth + 6 * V) / 8

    es1, vs1 = _decay(es), _decay(vs)
    pr, psh = _rules(T, es, vs)
    cr, csh = _rules(T, es1, vs1)
    masks = lambda rule, sharp: np.where(shp(rule == 2), V, np.where(shp(rule == 1), crease_v(sharp), smooth_v))
    VPp = masks(pr, psh)
    VP = VPp
    tr = pr != cr
    if tr.any():
        VPc = masks(cr, csh)
        # the fractional weight: the mean parent sharpness of what decays to smooth at the vertex (edges and itself)
        de = (es > 0) & (es1 <= 0)
        tsum = _sum_at(n, T.ea[de], es[de]) + _sum_at(n, T.eb[de], es[de])
        tcnt = np.bincount(np.r_[T.ea[de], T.eb[de]], minlength=n).astype(float)
        dv = (vs > 0) & (vs1 <= 0)
        tsum = tsum + np.where(dv, vs, 0.0); tcnt = tcnt + dv
        wv = np.where(tcnt > 0, np.minimum(tsum / np.maximum(tcnt, 1), 1.0), 0.0)
        VP = np.where(shp(tr), shp(wv) * VPp + (1 - shp(wv)) * VPc, VPp)
    VP = np.where(shp(val == 0), V, VP)
    V1 = np.concatenate([VP, EP, FP])
    # the child quads: per corner (v, its next edge's point, the face point, its previous edge's point)
    lv = T.lv
    Qd = np.stack([lv, n + T.einv, n + ne + T.fid, n + T.einv[T.prv]], 1)
    if rotate:
        # OpenSubdiv's child j of a quad starts j corners on (its parametric origin); an n-gon's children start at their
        # corner vertex (see tests: charkit/tests/test_subsurf.py)
        corner = np.arange(len(lv)) - T.st[T.fid]
        r = np.where(T.cnt[T.fid] == 4, corner, 0)
        Qd = Qd[np.arange(len(Qd))[:, None], (np.arange(4)[None, :] - r[:, None]) % 4]
    # child edge sharpness: each parent edge's two halves; the new interior edges are smooth
    sel = es1 > 0
    e_ = np.nonzero(sel)[0]
    pairs = np.concatenate([np.stack([T.ea[e_], n + e_], 1), np.stack([n + e_, T.eb[e_]], 1)])
    sh = np.r_[es1[e_], es1[e_]]
    vs_next = np.r_[vs1, np.zeros(ne + nf)]
    return V1, Qd, (pairs, sh), vs_next, T.fid


def _edge_sharp(T, pairs_sharp, boundary=True):
    """per edge of T: the given sharpness (pairs, values) with open and non-manifold edges infinitely sharp."""
    es = np.zeros(T.ne)
    if pairs_sharp is not None and len(pairs_sharp[0]):
        i = T.edge_index(pairs_sharp[0])
        ok = i >= 0
        np.maximum.at(es, i[ok], np.asarray(pairs_sharp[1], float)[ok])
    if boundary:
        es[T.ecnt != 2] = INF
    return es


def _nonmanifold_vertices(T):
    """vertices OpenSubdiv makes corners: on a non-manifold edge, or whose polygons don't form one fan (the faces round a
    manifold vertex number its edges, or one fewer on a border)."""
    val = np.bincount(np.r_[T.ea, T.eb], minlength=T.nv)
    nfv = np.bincount(T.lv, minlength=T.nv)
    bad = (nfv != val) & (nfv != val - 1) & (val > 0)
    nm = T.ecnt > 2
    bad[T.ea[nm]] = True; bad[T.eb[nm]] = True
    return bad


# ------------------------------------------------------------------------------------------------------------ limit
def limit(V, T, es, vs):
    """the limit masks on an all-quad mesh's vertices, as OpenSubdiv's patches evaluate them at the level they are
    applied on: smooth and dart (n^2 v + 4 sum(edge neighbours) + sum(diagonals)) / (n (n + 5)); crease (two infinitely
    sharp edges) (a + 4 v + b) / 6, except a border vertex with a single face, which stays (the end cap's corner);
    corner v. Sharpness short of infinite counts as smooth (what is left of a semi-sharp edge at the isolation level)."""
    V = np.asarray(V, float)
    n = T.nv
    d = V.shape[1:]
    shp = lambda x: x.reshape((-1,) + (1,) * len(d))
    es = np.where(es >= INF, INF, 0.0)
    vs = np.where(vs >= INF, INF, 0.0)
    val = np.bincount(np.r_[T.ea, T.eb], minlength=n)
    nfv = np.bincount(T.lv, minlength=n)
    E = _sum_at(n, T.ea, V[T.eb]) + _sum_at(n, T.eb, V[T.ea])
    # diagonals: per corner, the corner two on (all quads)
    D = _sum_at(n, T.lv, V[T.lv[T.nxt[T.nxt]]])
    nn = shp(np.maximum(val, 1).astype(float))
    sm = (nn * nn * V + 4 * E + D) / (nn * (nn + 5))
    rule, sharp = _rules(T, es, vs)
    rule = np.where((rule == 1) & (nfv == 1), 2, rule)
    oth = _sum_at(n, T.ea[sharp], V[T.eb[sharp]]) + _sum_at(n, T.eb[sharp], V[T.ea[sharp]])
    cr = (oth + 4 * V) / 6
    out = np.where(shp(rule == 2), V, np.where(shp(rule == 1), cr, sm))
    return np.where(shp(val == 0), V, out)


def level_dependent(T, es, vs):
    """the vertices whose limit mask gives a different point at a finer level: darts (a smooth vertex on one
    infinitely sharp edge), border vertices with a single face, and any vertex on a semi-sharp edge or itself
    semi-sharp. The rest (smooth, crease, corner) are exact at any level."""
    semi_e = (es > 0) & (es < INF)
    semi = np.zeros(T.nv, bool)
    semi[T.ea[semi_e]] = True; semi[T.eb[semi_e]] = True
    semi |= (vs > 0) & (vs < INF)
    inf = es >= INF
    ninf = np.bincount(np.r_[T.ea[inf], T.eb[inf]], minlength=T.nv)
    nfv = np.bincount(T.lv, minlength=T.nv)
    dart = (ninf == 1) & ~(vs >= INF)
    return semi | dart | ((nfv == 1) & ~(vs >= INF))


def evaluate(V, T, es, vs, level, quality=3, rings=4):
    """the positions Blender's modifier gives T's vertices (T at `level` of refinement): the limit masks at the adaptive
    isolation level `quality` (the modifier's Quality). Vertices whose mask depends on the level are refined there
    locally, in the `rings` of polygons round them."""
    out = limit(V, T, es, vs)
    extra = quality - level
    if extra <= 0:
        return out
    sp = np.nonzero(level_dependent(T, es, vs))[0]
    if not len(sp):
        return out
    V = np.asarray(V, float)
    near = np.zeros(T.nv, bool); near[sp] = True
    for _ in range(rings):
        fm = np.logical_or.reduceat(near[T.lv], T.st) if T.nf else np.zeros(0, bool)
        near[T.lv[np.repeat(fm, T.cnt)]] = True
    fm = np.logical_or.reduceat(near[T.lv], T.st)
    loops = np.repeat(fm, T.cnt)
    used = np.unique(T.lv[loops])
    remap = np.full(T.nv, -1, np.int64); remap[used] = np.arange(len(used))
    S = Topo(len(used), remap[T.lv[loops]], T.cnt[fm])
    sh = es > 0
    keep = sh & (remap[T.ea] >= 0) & (remap[T.eb] >= 0)
    ps = (np.stack([remap[T.ea[keep]], remap[T.eb[keep]]], 1), es[keep])
    Vs, ess, vss = V[used], _edge_sharp(S, ps), vs[used]
    # (the ring's own border is artificial: sharp, `rings` away, beyond what `extra` levels carry inward)
    for _ in range(extra):
        Vs, Qd, ps, vss, _ = refine(Vs, S, ess, vss)
        S = Topo(len(Vs), Qd.ravel(), np.full(len(Qd), 4))
        ess = _edge_sharp(S, ps)
    L = limit(Vs, S, ess, vss)
    out = out.copy()
    out[sp] = L[remap[sp]]
    return out


# ------------------------------------------------------------------------------------------------------------ UVs
def uv_values(T, luv, limit_=UV_LIMIT, use_winding=True):
    """face-varying UV topology as Blender's converter builds it: per vertex, its corners grouped by UV (within
    STD_UV_CONNECT_LIMIT of the group's first corner, and the same UV winding), a value per group. -> (value index per
    loop, value UVs (the last corner written wins, as Blender sets them))."""
    luv = np.asarray(luv, float).reshape(-1, 2)
    nl = len(T.lv)
    # the polygons' UV winding as Blender's uv_vert_map takes it: cross_poly_v2 (the trapezium rule, float32, summed
    # in corner order from the last corner's edge) > 0
    u32 = luv.astype(np.float32)
    term = (u32[:, 0] - u32[T.prv, 0]) * (u32[:, 1] + u32[T.prv, 1])
    cross = np.zeros(T.nf, np.float32)
    for k in range(int(T.cnt.max()) if T.nf else 0):
        has = T.cnt > k
        cross[has] = cross[has] + term[T.st[has] + k]
    wind = np.ones(T.nf, bool) if not use_winding else cross > 0
    order = np.lexsort((np.arange(nl), T.fid, T.lv))            # by vertex, then face order (Blender's list order)
    vals = np.full(nl, -1, np.int64)
    lvs = T.lv[order]
    starts = np.r_[0, np.nonzero(np.diff(lvs))[0] + 1]
    ends = np.r_[starts[1:], nl]
    nval = 0
    # the common case: every corner of the vertex within the limit of its first and the same winding
    first = np.repeat(starts, ends - starts)
    same = (np.abs(luv[order] - luv[order[first]]) < limit_).all(1) & (wind[T.fid[order]] == wind[T.fid[order[first]]])
    allsame = np.logical_and.reduceat(same, starts) if nl else np.zeros(0, bool)
    for gi, (s, e) in enumerate(zip(starts, ends)):
        ls = order[s:e]
        if allsame[gi]:
            vals[ls] = nval; nval += 1
            continue
        rest = list(ls)
        while rest:
            h = rest[0]
            grp = [x for x in rest if (np.abs(luv[x] - luv[h]) < limit_).all() and wind[T.fid[x]] == wind[T.fid[h]]]
            for x in grp:
                vals[x] = nval
            nval += 1
            rest = [x for x in rest if vals[x] < 0]
    # value UVs: set per corner in loop order, the last write wins
    U = np.zeros((nval, 2))
    U[vals] = luv                                                # (numpy: the last of repeated indices wins)
    return vals, U


# ------------------------------------------------------------------------------------------------------------ main
def subdivide(V, polys, levels=1, creases=None, vcreases=None, uv=None, limit_surface=True, carry=None,
              uv_smooth='PRESERVE_BOUNDARIES', sharpness=None, quality=3, carry_rule='linear'):
    """Blender's Subdivision Surface on a mesh. polys: index tuples, or (loopv, counts); creases: {(a, b): crease 0..1}
    or (pairs (k, 2), creases (k,)); vcreases: per-vertex crease (n,) or None; sharpness: (pairs, sharpness) given as
    OpenSubdiv sharpness directly (instead of creases); uv: per-corner UVs ([(u, v) per corner] per polygon, or
    (loops, 2)); carry: per-vertex data (n, k), by carry_rule: 'linear' as Blender interpolates vertex data (kept at
    the vertices, the mean of the ends and of the corners; no limit), 'limit' through the same refinement and limit
    stencil as the positions (the limit-stencil skin weights call J ships: an affine, non-negative mask, so weights
    that sum to 1 still do).
    -> dict(V, quads, parent, uv (m, 4, 2) or None, carry or None, sharp (the final level's sharp edges: pairs,
    sharpness))."""
    V = np.asarray(V, float)
    if isinstance(polys, tuple) and len(polys) == 2 and not np.isscalar(polys[0]) and np.ndim(polys[1]) == 1 and \
            len(polys[1]) and np.sum(polys[1]) == len(polys[0]):
        lv, cnt = np.asarray(polys[0], np.int64), np.asarray(polys[1], np.int64)
    elif isinstance(polys, np.ndarray) and polys.ndim == 2:
        lv, cnt = polys.astype(np.int64).ravel(), np.full(len(polys), polys.shape[1])
    else:
        cnt = np.array([len(f) for f in polys], np.int64)
        lv = np.concatenate([np.asarray(f, np.int64) for f in polys]) if len(polys) else np.zeros(0, np.int64)
    if sharpness is None and creases is not None:
        if isinstance(creases, dict):
            pairs = np.array(list(creases.keys()), np.int64).reshape(-1, 2)
            cw = np.array(list(creases.values()), float)
        else:
            pairs, cw = np.asarray(creases[0], np.int64).reshape(-1, 2), np.asarray(creases[1], float)
        keep = cw > 0
        sharpness = (pairs[keep], crease_sharpness(cw[keep]))
    n = len(V)
    T = Topo(n, lv, cnt)
    es = _edge_sharp(T, sharpness)
    vs = np.zeros(n) if vcreases is None else crease_sharpness(vcreases)
    vs = np.where(_nonmanifold_vertices(T), INF, vs)
    # UVs: their own topology (values), sharp along their boundaries and at every boundary value (linear there)
    UVT = None
    if uv is not None:
        luv = np.asarray(uv, float).reshape(-1, 2) if isinstance(uv, np.ndarray) else \
            np.concatenate([np.asarray(c, float).reshape(-1, 2) for c in uv])
        vals, U = uv_values(T, luv)
        UT = Topo(len(U), vals, cnt)
        # the mesh's own sharpness carries over to the UV edges over the same mesh edge
        ues = np.zeros(UT.ne)
        me = T.einv                                               # per loop: its mesh edge
        np.maximum.at(ues, UT.einv, np.where(T.ecnt[me] == 2, es[me], 0.0))
        ues[UT.ecnt != 2] = INF
        uvs = np.zeros(len(U))
        if uv_smooth == 'PRESERVE_BOUNDARIES':
            ub = UT.ecnt != 2
            uvs[UT.ea[ub]] = INF; uvs[UT.eb[ub]] = INF
        elif uv_smooth == 'NONE':
            uvs[:] = INF; ues[:] = INF
        else:
            raise NotImplementedError('uv_smooth %s' % uv_smooth)
        uvs = np.maximum(uvs, np.where(_nonmanifold_vertices(UT), INF, 0.0))
        UVT = [U, UT, ues, uvs]
    C = None if carry is None else np.asarray(carry, float).reshape(n, -1)
    if carry_rule not in ('linear', 'limit'):
        raise ValueError('carry_rule %r' % carry_rule)
    nd = V.shape[1]
    if C is not None and carry_rule == 'limit':         # the carried data rides with the positions, column for column
        V, C = np.concatenate([V, C], 1), None
    parent = np.arange(T.nf)
    for lev in range(levels):
        V1, Qd, ps, vs1, par = refine(V, T, es, vs)
        if UVT is not None:
            U, UT, ues, uvs = UVT
            U1, UQ, ups, uvs1, _ = refine(U, UT, ues, uvs)
        if C is not None:
            C = _carry(C, T)
        parent = par if lev == 0 else parent[par]
        V, vs = V1, vs1
        T = Topo(len(V), Qd.ravel(), np.full(len(Qd), 4))
        es = _edge_sharp(T, ps)
        if UVT is not None:
            UT1 = Topo(len(U1), UQ.ravel(), np.full(len(UQ), 4))
            UVT = [U1, UT1, _edge_sharp(UT1, ups), uvs1]
    quads = T.lv.reshape(-1, 4) if levels else None
    sharp_final = (np.stack([T.ea[es > 0], T.eb[es > 0]], 1), es[es > 0])
    if limit_surface and levels:
        V = evaluate(V, T, es, vs, levels, quality)
        if UVT is not None:
            U, UT, ues, uvs = UVT
            UVT[0] = evaluate(U, UT, ues, uvs, levels, quality)
    uv_out = UVT[0][UVT[1].lv].reshape(-1, 4, 2) if UVT is not None and levels else None
    if carry is not None and carry_rule == 'limit':
        V, C = V[:, :nd], V[:, nd:]
    return dict(V=V, quads=quads, parent=parent, uv=uv_out, carry=C, sharp=sharp_final)


def _carry(C, T):
    """vertex data through one level as Blender's subdivided mesh interpolates it: kept at the vertices, the mean of the
    ends at an edge's point, the mean of the corners at a face's."""
    n, ne, nf = T.nv, T.ne, T.nf
    E = (C[T.ea] + C[T.eb]) / 2
    F = _sum_at(nf, T.fid, C[T.lv]) / T.cnt[:, None]
    return np.concatenate([C, E, F])
