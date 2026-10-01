"""Garments (docs/CHARKIT.md §2): an outfit is a list of garment specs built on the assembled body, in two families.
  - shells: tight garments taken from the body's own surface (a region picked by bone and position along the bone), lifted
    off it and given thickness; they carry the body's weights exactly, and the body under them is masked away (no
    poke-through). Tops, shorts, boots, gloves, tights.
  - built pieces: a pleated skirt (a waist ring from the body's section, a hem by azimuth, pleats, panels, a patterned
    hem), a hanging panel (an overskirt panel or tail hung from the waist ring at an azimuth), puffy sleeves, bands
    (cuffs, wristbands, waistbands, boot tops), a sailor collar, a bow (with a tail length).
Built pieces are weighted by construction (a skirt blends the hips into each thigh by side and height, as a skirt should).
All sizes are in head lengths L unless noted. Each spec: {kind, name, color, shade (optional: the shadow tone as a
multiplier of the colour, SHADE_MUL by default), ...kind's knobs}.
"""
import math
import numpy as np

from . import mh


# ---------------------------------------------------------------------------------------------------------------- body info
def bone_seg(A, bone):
    h, t = mh.VRM_JOINTS[bone]
    return np.asarray(A['joints'][h], float), np.asarray(A['joints'][t], float)


def dominant(A):
    """per vertex: the bone with the largest weight and that weight."""
    names = list(A['weights'])
    Wm = np.stack([A['weights'][n] for n in names], 1)
    i = Wm.argmax(1)
    return np.array(names)[i], Wm.max(1)


def along(A, bone, P):
    """the parameter t of points P projected onto a bone (0 head .. 1 tail) and their distance from its axis."""
    h, t = bone_seg(A, bone)
    d = t - h
    ln = max(1e-9, np.linalg.norm(d))
    u = d / ln
    q = np.asarray(P) - h
    tt = q @ u / ln
    rad = np.linalg.norm(q - np.outer(q @ u, u), axis=1)
    return tt, rad


def body_weights(A, P, floor=1e-4):
    """the body's skin weights carried to points P from the nearest point of its surface (barycentric there), as
    production rigs transfer the body's weights to a garment that should bend with it: a waistband over the waist
    joint folds with the spine at a squat instead of riding the hips into the belly (docs/workstreams/xpbd.md, round 3).
    -> {bone: (len(P),)}, bones whose weight never passes `floor` left out, normalised."""
    from .geom.bvh import BVH
    V = np.asarray(A['verts'], float)
    T = np.array([(f[0], f[k], f[k + 1]) for f in A['faces'] for k in range(1, len(f) - 1)], np.int64)
    P = np.asarray(P, float)
    _, tri, q = BVH((V, T)).nearest(P)
    T = T[tri]
    a, b, c = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    v0, v1, v2 = b - a, c - a, q - a
    d00, d01, d11 = (v0 * v0).sum(1), (v0 * v1).sum(1), (v1 * v1).sum(1)
    d20, d21 = (v2 * v0).sum(1), (v2 * v1).sum(1)
    den = np.maximum(d00 * d11 - d01 * d01, 1e-30)
    bv = (d11 * d20 - d01 * d21) / den
    bw = (d00 * d21 - d01 * d20) / den
    bc = np.clip(np.stack([1 - bv - bw, bv, bw], 1), 0, 1)
    bc /= bc.sum(1, keepdims=True)
    W = {n: (np.asarray(w, float)[T] * bc).sum(1) for n, w in A['weights'].items()}
    W = {n: w for n, w in W.items() if w.max() > floor}
    tot = np.maximum(sum(W.values()), 1e-12)
    return {n: w / tot for n, w in W.items()}


def band_weights(A, spec, V, bone='hips'):
    """a band's weights by its spec's `weights`: 'body' (the body's under it: body_weights) or a bone (rigid on it,
    the default)."""
    w = spec.get('weights', bone)
    return body_weights(A, V) if w == 'body' else {w: np.ones(len(V))}


def limb_radius(A, bone, t, band=0.06):
    """the body's radius round a bone at t (the median distance of the vertices it owns near t)."""
    own = A['weights'].get(bone)
    if own is None:
        return 0.03
    idx = np.nonzero(own > 0.5)[0]
    tt, rad = along(A, bone, A['verts'][idx])
    m = np.abs(tt - t) < band
    if m.sum() < 6:
        m = np.argsort(np.abs(tt - t))[:12]
    return float(np.median(rad[m]))


def vertex_normals(V, faces):
    from .anime_head import vertex_normals as vn
    return vn(V, faces)


# ------------------------------------------------------------------------------------------------------------------- shells
def region(A, parts):
    """vertices in a region: parts = [[bone, t0, t1], ...] (the vertex's dominant bone, its position along that bone)."""
    dom, _ = dominant(A)
    V = A['verts']
    inside = np.zeros(len(V), bool)
    for bone, t0, t1 in parts:
        idx = np.nonzero(dom == bone)[0]
        if len(idx) == 0:
            continue
        tt, _ = along(A, bone, V[idx])
        inside[idx[(tt >= t0) & (tt <= t1)]] = True
    return inside


def hull_edge(P, ax, n=72, q=2.0, smooth=2.0, low=True, min_pts=5):
    """a piece's lower (or upper) edge per angle round an axis, from its hull points: per sector (with at least min_pts
    points) the q-th percentile of height (100 - q for the upper), filled round the circle and smoothed -> fn(theta) ->
    height (world z)."""
    from .geom import loft
    _, th, _ = ax.coords(P)
    j = np.clip(((th + np.pi) / (2 * np.pi) * n).astype(int), 0, n - 1)
    z = np.full(n, np.nan)
    for k in range(n):
        zk = P[j == k, 2]
        if len(zk) >= min_pts:
            z[k] = np.percentile(zk, q if low else 100 - q)
    z = loft._fill_periodic(z)
    if z is None:
        raise ValueError('too few hull points for an edge')
    z = loft.gauss1d(z, smooth, mode='wrap')
    th_c = -np.pi + (np.arange(n) + 0.5) * 2 * np.pi / n
    return lambda a: np.interp(a, th_c, z, period=2 * np.pi)


def _grow(M, n, grow=True):
    """a boolean grid dilated (or eroded) n cells (4-neighbours), numpy only (the build's Python has no scipy)."""
    for _ in range(n):
        nb = [np.roll(M, 1, 0), np.roll(M, -1, 0), np.roll(M, 1, 1), np.roll(M, -1, 1)]
        M = (M | nb[0] | nb[1] | nb[2] | nb[3]) if grow else (M & nb[0] & nb[1] & nb[2] & nb[3])
    return M


def panel_faces(V, faces, P, L, cell=0.03, close=2, facing=-0.3):
    """a shell's faces that are its front panel as the hull draws it: the face's centre, seen from the front, inside the
    panel's points' footprint (a grid of `cell` L, closed `close` cells), and the face turned toward the front (its
    normal's y under `facing`). Per face 1 or 0; no texture, so no dependence on the body's UVs."""
    c = cell * L
    # the design is symmetric: stray labels out to one side dropped (past 2.5 MADs of x), the rest mirrored
    mx = np.median(P[:, 0]); mad = np.median(np.abs(P[:, 0] - mx)) + 1e-9
    P = P[np.abs(P[:, 0] - mx) < 2.5 * 1.4826 * mad]
    P = np.concatenate([P, P * np.array([-1.0, 1.0, 1.0])])
    x0, z0 = P[:, 0].min() - 3 * c, P[:, 2].min() - 3 * c
    nx, nz = int((P[:, 0].max() - x0) / c) + 4, int((P[:, 2].max() - z0) / c) + 4
    M = np.zeros((nx, nz), bool)
    M[np.clip(((P[:, 0] - x0) / c).astype(int), 0, nx - 1), np.clip(((P[:, 2] - z0) / c).astype(int), 0, nz - 1)] = True
    M = _grow(_grow(M, close, True), close, False)
    N = vertex_normals(V, faces)
    out = np.zeros(len(faces), np.int32)
    for i, f in enumerate(faces):
        q = V[list(f)].mean(0)
        ix, iz = int((q[0] - x0) / c), int((q[2] - z0) / c)
        if 0 <= ix < nx and 0 <= iz < nz and M[ix, iz] and N[list(f), 1].mean() < facing:
            out[i] = 1
    return out


def shell(A, spec, normals=None, hull=None):
    """a tight garment: the region's faces lifted by `offset` along the body's normals. With `source` 'hull', its hem
    follows the hull's own piece: cut below the lower edge of its points (and its folded pieces', `fold`) per angle
    round the body (hull_edge), lowered by `hem_drop` L. -> dict(verts, faces, weights, uvs (per face corner, the
    body's), src (body vertex per shell vertex), faces_src (body face index per face)).

    Over a band (`ease` with `mode` 'over': a jacket's hem hung outside the waistband, garments2): the hem is the band's
    top edge less `hang` L (ease_over_band), not the hull's edge, and the shell drapes out to the band's face or a flare
    (ease_over_band). An `opening` (a jacket's open front) cuts the faces between its edges out; a shell `inside`
    another's opening (the bib behind the jacket) keeps only the faces there, `margin` L past its edges (under the
    jacket). Hem and opening are cut clean: the kept faces' border vertices moved onto the cut (snap_cuts). With
    `refine` n, the region's faces are refined n Catmull-Clark levels first (see below; no body UVs then)."""
    L = A['head']['L']
    V, F = A['verts'], A['faces']
    ins = region(A, spec['region'])
    cut = None
    ez = spec.get('ease')
    over = bool(ez) and ez.get('mode') == 'over'
    if spec.get('source') == 'hull' and not over:
        P = _hull_points(hull, spec)
        ax = _vertical_axis(P, P[:, 2].max())
        edge = hull_edge(P, ax, q=spec.get('hem_q', 2.0))
        cut = lambda X: edge(ax.coords(X)[1]) - spec.get('hem_drop', 0.0) * L
        if spec.get('hem_level'):
            # one height all round (the hull's lower edge wanders by azimuth, most round the inner thighs): the median
            # of its edge, less the drop
            zl = float(np.median(edge(np.linspace(-np.pi, np.pi, 72, endpoint=False)))) - spec.get('hem_drop', 0.0) * L
            cut = lambda X: np.full(len(X), zl)
        ins &= V[:, 2] >= cut(V)
    # height cuts at body landmarks: [bone, t, 'above' | 'below', offset in L]
    for bone, t, side, o in spec.get('cuts', []):
        if bone == 'eye':                                        # a height from the eye line (L)
            zc = _eye_z(A) + o * L
        else:
            h, tl = bone_seg(A, bone)
            zc = (h + (tl - h) * t)[2] + o * L
        ins &= (V[:, 2] >= zc) if side == 'above' else (V[:, 2] <= zc)
    body_of, Wr = None, None
    rf = spec.get('refine', 0)
    if rf:
        # its region refined (Catmull-Clark, `refine` levels) before the hem and the opening are cut: the body's faces
        # (0.038 L on the torso) left a jacket's front corners one vertex each, its hem slanting in steps between them.
        # The refined mesh carries the weights; its first vertices are the body's own (the vertex points)
        from . import subdiv
        k0 = [i for i, f in enumerate(F) if all(ins[v] for v in f)]
        u0 = sorted({v for i in k0 for v in F[i]})
        r0 = {o: n for n, o in enumerate(u0)}
        bones = [b for b, w in A['weights'].items() if w[u0].max() > 1e-4]
        D = np.c_[V[u0], np.stack([A['weights'][b][u0] for b in bones], 1)]
        D1, Q, par = subdiv.catmull_clark(D, [tuple(r0[v] for v in F[i]) for i in k0], limit=False, levels=rf)
        V, F = D1[:, :3], [tuple(int(v) for v in q) for q in Q]
        Wr = {b: np.clip(D1[:, 3 + j], 0, 1) for j, b in enumerate(bones)}
        body_of = np.full(len(V), -1)
        body_of[:len(u0)] = u0
        faces_body = np.asarray(k0)[par]
        ins = np.ones(len(V), bool)
        normals = None
    band = None
    cuts = []                                                    # signed cuts (>= 0 kept) whose edges are snapped
    # a lifted surface (the template collar: `stand` round the neck, `over` the layers under it): every region vertex's
    # place computed first (the body + `offset`, then the lifts), and the outline, the `top` and the snap evaluated on
    # it, so the cut edges land where the drawing puts them in projection (collar_lift)
    lifted, keep_skin, hide_u = None, None, None
    if spec.get('stand') or isinstance(spec.get('over'), (list, tuple)):     # (a puff's or a flap's `over` is theirs)
        nrm_l = normals if normals is not None else vertex_normals(V, F)
        base_l = V + nrm_l * spec.get('offset', 0.012) * L
        lifted = collar_lift(A, base_l, F, spec, hull)
        if spec.get('keep_skin'):
            # the skin kept under the vertices the lifts moved more than `keep_skin` L (masked, as a shell's, by
            # default: the stand covers the neck it unrolls from; kept, its junction's flare shows in neck_crease)
            mv = np.linalg.norm(lifted - base_l, axis=1) > spec['keep_skin'] * L
            keep_skin = set(int(b) for b in (body_of[mv] if body_of is not None else np.nonzero(mv)[0]) if b >= 0)
        V = lifted
        if spec.get('outline'):
            # the body under the outline at the unlifted place is masked too: the lifts move the collar's material out
            # along the shoulder, so the outline's edge falls on a vertex further in and the skin between (under the
            # collar still) was left unmasked (neck_crease read a stray shoulder vertex: 71 against 26)
            ins_u = ins & (outline_cut(A, spec['outline'])(base_l) >= 0)
            hide_u = body_of[ins_u] if body_of is not None else np.nonzero(ins_u)[0]
            hide_u = hide_u[hide_u >= 0]
    if ez and hull is not None:
        bs = next((g for g in (spec.get('_spec') or {}).get('garments', []) if g['name'] == ez.get('under', 'waistband')),
                  None)
        if bs is not None:
            band = (bs, belt_hull(A, bs, hull))
            if over:
                hz = hem_over_band(A, ez, band)
                cut = hz
                cuts.append(lambda X, hz=hz: X[:, 2] - hz(X))
                ins &= V[:, 2] >= hz(V)
            else:
                # its hem stays under the band: a dropped hem hung out below the band's lower edge at the front
                ins &= V[:, 2] >= band[1]['verts'][:, 2].min() + ez.get('above_bottom', 0.03) * L
    ol = spec.get('outline')
    if ol:
        g_ol = outline_cut(A, ol)
        cuts.append(g_ol)
        ins &= g_ol(V) >= 0
    op, inside = spec.get('opening'), spec.get('inside')
    if op:
        g_op = opening_cut(A, op)
        cuts.append(g_op)
        ins &= g_op(V) >= 0
    if inside:
        of = next((g for g in (spec.get('_spec') or {}).get('garments', []) if g['name'] == inside['of']), None)
        if of is None or not of.get('opening'):
            raise ValueError('%s: inside %s, which has no opening' % (spec['name'], inside['of']))
        g_of, m_ = opening_cut(A, of['opening']), inside.get('margin', 0.03) * L
        g_in = lambda X, g_of=g_of, m_=m_: m_ - g_of(X)
        cuts.append(g_in)
        ins &= g_in(V) >= 0
    keep = [i for i, f in enumerate(F) if all(ins[v] for v in f)]
    used = sorted({v for i in keep for v in F[i]})
    remap = {o: n for n, o in enumerate(used)}
    if lifted is not None:
        sv = V[used].copy()
    else:
        nrm = normals if normals is not None else vertex_normals(V, F)
        off = spec.get('offset', 0.012) * L
        sv = V[used] + nrm[used] * off
    sf = [tuple(remap[v] for v in F[i]) for i in keep]
    if cuts and spec.get('hem_snap') and cut is not None and not over:
        cuts.append(lambda X: X[:, 2] - cut(X))
    if cuts:
        sv = snap_cuts(V, F, used, keep, sv, cuts, ins)
    elif spec.get('hem_snap') and cut is not None:
        sv = hem_snap(V, F, used, keep, sv, cut, ins)
    sm = spec.get('smooth')
    if sm:
        # smooth the shell below a height (boots: the toes merge into one smooth toe box), then push back out to the body
        from .anime_head import adjacency, laplacian_smooth
        h, tl = bone_seg(A, sm['bone'])
        zc = (h + (tl - h) * sm.get('t', 0.0))[2]
        mask = sv[:, 2] < zc
        nb_ = adjacency(len(sv), sf)
        sv2 = laplacian_smooth(sv, nb_, mask, iters=sm.get('iters', 40), lam=0.6, mu=-0.62)
        grow = sm.get('grow', 0.02) * L
        nn = vertex_normals(sv2, sf)
        sv = np.where(mask[:, None], sv2 + nn * grow, sv)
    if rf:
        dom_r = np.array(list(Wr))[np.argmax(np.stack(list(Wr.values()), 1), 1)]
        tor = np.isin(dom_r[used], TORSO)
    else:
        tor = np.isin(dominant(A)[0][used], TORSO)
    if band is not None:
        sv = ease_over_band(A, sv, ez, band, tor) if over else ease_to_band(A, sv, ez, band)
    if spec.get('bed') and hull is not None:
        sv = bed(A, sv, sf, spec, hull)
    if spec.get('pad'):
        sv = shoulder_pad(A, sv, sf, spec['pad'])
    if rf:
        W = {b: w[used] for b, w in Wr.items() if w[used].max() > 1e-4}
        tot = np.maximum(sum(W.values()), 1e-9)
        # normalised, then held to 0.01: the refined weights interpolate, and _object adds a vertex group's vertices
        # once per distinct weight (a thousand calls a bone at 0.001 tripled the garments stage on the box)
        W = {b: np.round(w / tot, 2) for b, w in W.items()}
        W = {b: w for b, w in W.items() if w.max() > 0}
        src = body_of[used]
        G = dict(verts=sv, faces=sf, weights=W, uvs=None, src=src[src >= 0], faces_src=[int(faces_body[i]) for i in keep])
    else:
        W = {b: w[used] for b, w in A['weights'].items() if w[used].max() > 1e-4}
        B = A['body']
        uvs = [[B['uvs'][ui] for ui in B['face_uv'][i]] for i in keep]
        G = dict(verts=sv, faces=sf, weights=W, uvs=uvs, src=np.array(used), faces_src=keep)
    if keep_skin is not None:
        G['keep_skin'] = keep_skin
    if hide_u is not None:
        G['hide_also'] = np.asarray(hide_u, int)
    if spec.get('stripe') and ol and spec['stripe'].get('cut'):
        sv, sf, G['panel_faces'], G['weights'] = stripe_cut(A, sv, sf, ol, spec['stripe'], G['weights'])
        G['weights'] = {b: np.round(np.clip(w, 0, 1), 2) for b, w in G['weights'].items()}
        G['verts'], G['faces'], G['faces_src'] = sv, sf, None
        if G.get('uvs') is not None and len(G['uvs']) != len(sf):
            G['uvs'] = None
    elif spec.get('stripe') and ol:
        sv, G['panel_faces'] = stripe_faces(A, sv, sf, ol, spec['stripe'])
        G['verts'] = sv
    if spec.get('source') == 'hull' and 'panel' in spec and hull and spec['panel'].get('mode') != 'texture':
        pp = hull.get(spec['panel'].get('piece', 'bodice_panel'))
        if pp is not None and len(pp) >= 10:
            G['panel_faces'] = panel_faces(sv, sf, pp, L)
    return G


def shoulder_pad(A, sv, sf, pad):
    """a jacket's shoulders built up to a level line (Michael's flag, 2026-10-01: the shoulders still misshapen; the
    drawn shoulder line runs level from the collar to the puff, ours dipped 0.07-0.09 L between them): the shell's
    upward-facing vertices raised by the `lift` table's dz at their |x| ([[|x| L, dz L], ...], 0 outside it), times
    how much their surface faces up (`nz` [lo, hi]: the normal's z, 0 at lo or under, 1 at hi or over), the raise eased
    over the mesh (`smooth` passes of the 1-ring's mean) so the pad's edge has no step. The body is untouched (its
    neck join, the hair's clearance), and a collar lying `over` the jacket follows it (collar_drape). -> the moved
    points."""
    from scipy import sparse
    L = A['head']['L']
    sv = np.asarray(sv, float).copy()
    if not len(sv):
        return sv
    K = np.asarray(sorted(pad['lift']), float)
    lo, hi = pad.get('nz', (0.2, 0.7))
    nz = vertex_normals(sv, sf)[:, 2]
    dz = np.interp(np.abs(sv[:, 0]) / L, K[:, 0], K[:, 1], left=0.0, right=0.0)
    dz = dz * np.clip((nz - lo) / max(hi - lo, 1e-6), 0, 1)
    n = len(sv)
    rows = [v for f in sf for v in f]
    cols = [f[(k + 1) % len(f)] for f in sf for k in range(len(f))]
    Adj = sparse.coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(n, n)).tocsr()
    Adj = ((Adj + Adj.T) > 0).astype(float)
    deg = np.maximum(np.asarray(Adj.sum(1)).ravel(), 1)
    for _ in range(int(pad.get('smooth', 4))):
        dz = 0.5 * dz + 0.5 * (Adj @ dz) / deg
    sv[:, 2] += dz * L
    return sv


def bed(A, sv, sf, spec, hull):
    """a shell bedded under a piece lying on it (spec `bed` {under: the piece's garment name, default 'bow'; gap L;
    margin L; ease L; cell L; smooth: iterations}; tool/garments4): where the piece covers the shell in front (the
    front projection, x and z), the shell's vertices in front of the piece's back surface are set `gap` L behind it,
    and within `margin` L round its outline too (the outline's band: its line must show over the shell), easing back
    to the shell's own surface over `ease` L beyond. Only ever backward (+y), so the shell's back is untouched (it lies
    behind the piece already). The bow's lobes are wrapped onto the design's bow surface (the hull's), its pleat's strips
    behind the panels; the jacket, the body lifted, stood in front of their lower rims by up to 0.03 L (the bust comes
    toward the camera under them), so the bow's lower outline was drawn behind the jacket (bow_front_bleed). Placement
    rule: pieces don't interpenetrate; the piece lying on top keeps its drawn shape and the cloth under it gives (the
    bow presses on the jacket), where tool/pieceref's push of the lobes forward ballooned them. -> sv moved (m)."""
    L = A['head']['L']
    b = spec['bed']
    sa = spec.get('_spec') or {}
    ps = next((g for g in sa.get('garments', []) if g.get('name') == b.get('under', 'bow')), None)
    if ps is None or ps.get('kind') != 'bow' or ps.get('source') != 'hull':
        return sv
    ps = {k: v for k, v in ps.items() if k != 'clear'}           # (its clearance would rebuild this shell)
    G = bow_hull(A, dict(ps, _spec=sa), hull)
    P = np.asarray(G['verts'], float)
    F_ = [tuple(f) for f in G['faces']]
    if b.get('parts', 'lobes') == 'lobes' and G.get('tail_s') is not None:
        # the lobes alone (default): the knot's back and the tails' root behind it stand deep at the middle, and the
        # bib bedded under them fell back out of sight in profile (piece_bodice_panel's profile 0.34 -> 0.20)
        lob = np.isnan(np.asarray(G['tail_s'], float))
        if G.get('knot_v') is not None:
            lob[G['knot_v']] = False
        F_ = [f for f in F_ if lob[list(f)].all()]
        if not F_:
            return sv
    return bed_under(sv, sf, P, F_, L, b)


def bed_under(sv, sf, P, F_, L, b):
    """bed()'s geometry: the shell's vertices sv (faces sf) set behind the piece's surface (P, faces F_) where it covers
    them in the front projection, by b's gap, margin, ease, cell and smooth (L; see bed) -> sv moved."""
    from scipy import ndimage
    # the piece's surface sampled densely (its vertices, edge midpoints and face centres): its back per cell
    smp = [P[sorted({v for f in F_ for v in f})]] + \
        [0.5 * (P[[f[k] for f in F_]] + P[[f[(k + 1) % len(f)] for f in F_]]) for k in range(3)] + \
        [np.array([P[list(f)].mean(0) for f in F_])]
    S = np.concatenate(smp)
    c = b.get('cell', 0.005) * L
    gap, margin, ease = (b.get(k, d) * L for k, d in (('gap', 0.01), ('margin', 0.02), ('ease', 0.04)))
    pad = int(np.ceil((margin + ease) / c)) + 3
    x0, z0 = S[:, 0].min() - pad * c, S[:, 2].min() - pad * c
    nx = int(np.ceil((S[:, 0].max() + pad * c - x0) / c)) + 1
    nz = int(np.ceil((S[:, 2].max() + pad * c - z0) / c)) + 1
    ix = np.clip(((S[:, 0] - x0) / c).astype(int), 0, nx - 1)
    iz = np.clip(((S[:, 2] - z0) / c).astype(int), 0, nz - 1)
    back = np.full((nx, nz), -np.inf)
    np.maximum.at(back, (ix, iz), S[:, 1])
    back = ndimage.maximum_filter(back, size=3)                  # (cells between samples)
    foot = ndimage.binary_closing(np.isfinite(back), iterations=2) | np.isfinite(back)
    foot = ndimage.binary_fill_holes(foot)
    # every cell's nearest covered cell: its back depth (holes and the margin round the outline take their neighbour's)
    have = np.isfinite(back)
    dist, (ni, nk) = ndimage.distance_transform_edt(~have, return_indices=True)
    need = back[ni, nk] + gap
    dout = ndimage.distance_transform_edt(~foot) * c              # L outside the outline (0 under the piece)
    w = np.clip(1 - (dout - margin) / max(ease, 1e-9), 0, 1)
    w = w * w * (3 - 2 * w)
    jx = np.clip(np.rint((sv[:, 0] - x0) / c).astype(int), 0, nx - 1)
    jz = np.clip(np.rint((sv[:, 2] - z0) / c).astype(int), 0, nz - 1)
    inb = (sv[:, 0] >= x0) & (sv[:, 0] <= x0 + nx * c) & (sv[:, 2] >= z0) & (sv[:, 2] <= z0 + nz * c)
    dy = np.where(inb, np.maximum(0.0, need[jx, jz] - sv[:, 1]) * w[jx, jz], 0.0)
    if b.get('smooth', 3) and dy.any():
        nb = [set() for _ in range(len(sv))]
        for f in sf:
            for a_ in f:
                nb[a_].update(f)
        nb = [np.fromiter(n, int) for n in nb]
        under = inb & (dout[jx, jz] <= 0)
        raw = dy.copy()
        for _ in range(b.get('smooth', 3)):
            dy = np.array([dy[n].mean() if len(n) else dy[i] for i, n in enumerate(nb)])
            dy = np.where(under, np.maximum(dy, raw), dy)        # (under the piece never less than it needs)
    sv = np.asarray(sv, float).copy()
    sv[:, 1] += dy
    return sv


INK = '_ink'          # a material slot whose name ends so is ink: drawn lines, not cloth (qa3d.render_surfaces: a line)
OUTLINE_W = 'outline_w'   # a per-vertex outline width (shade.outline reads the group; 0: no hull), not a bone


def ink_strokes(G, cs, L, frame=None):
    """creases as a line layer (Michael, 2026-09-30: "creases, folds and pleats", tool/garments4): the outline renderer's
    inverted hulls draw silhouettes only, so a crease the design draws inside a piece (the skirt's cream panel's pleat
    folds, the bow's wrinkles) is a stroke: a thin ribbon lying on the piece's rendered surface. cs (a garment's
    `creases`): strokes [[[u, v], ...], ...] in the piece's own UV (G['uv'] per vertex, or G['uvs'] per face corner),
    `width` L (the ribbon), `lift` L off the surface, `taper` (the share of a stroke's length over which each end narrows
    to `tip` of its width), `step` L (samples along it). The surface is the piece's level-1 Subdivision (as it
    renders: a cage's folds round off under it), its outward side by charkit.geom.wind's rule. Each sample takes the
    weights of the surface point under it. `space` 'front': the strokes' points are (x, z) in L in the QA's front frame
    (`frame` (x0, z0): the midline and the eye line, garments._eye_z), each on the frontmost surface there (charkit.inkfit
    traces them from the design's front view). `space` 'panel': (f, v) across a skirt's front panel (G['panel_u'], its
    edge columns' u: f -1 and 1 its two edges (u rising), 0 its middle), v down the skirt: the strokes ride with
    the panel's shape (skirt_hull's panel_shape) and lie where our surface puts them in every view.
    -> dict(verts, faces, weights {bone: (n,)}, uv (n, 2)) or None."""
    from scipy.spatial import cKDTree
    from .geom import wind
    from .geom.subsurf import subdivide
    strokes = [np.asarray(s, float) for s in (cs.get('strokes') or []) if len(s) >= 2]
    if not strokes:
        return None
    if cs.get('space') == 'panel':
        if G.get('panel_u') is None:
            return None
        ul, ur = G['panel_u']
        strokes = [np.c_[(ul + ur) / 2 + s_[:, 0] * (ur - ul) / 2, s_[:, 1]] for s_ in strokes]
    V0 = np.asarray(G['verts'], float)
    F0 = [tuple(int(i) for i in f) for f in G['faces']]
    if G.get('uv') is not None:
        U0 = np.asarray(G['uv'], float)
        uvc = [U0[list(f)] for f in F0]
    elif G.get('uvs') is not None:
        uvc = [np.asarray(c, float) for c in G['uvs']]
    else:
        return None
    F0, uvc = wind.orient(V0, F0, uvc)[:2]
    wk = sorted(G['weights'])
    car = np.stack([np.asarray(G['weights'][k], float) for k in wk], 1) if wk else None
    R = subdivide(V0, F0, levels=1, uv=[[tuple(x) for x in c] for c in uvc], carry=car)
    V, Q = np.asarray(R['V'], float), np.asarray(R['quads'], int)
    UVq = np.asarray(R['uv'], float)                                 # (m, 4, 2) corner UVs of the subdivided quads
    W = np.asarray(R['carry'], float) if car is not None else None
    # triangles in UV (each quad's two), their corners' 3D points and weights
    tri = np.r_[Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]]
    tuv = np.r_[UVq[:, [0, 1, 2]], UVq[:, [0, 2, 3]]]
    fn = np.cross(V[tri[:, 1]] - V[tri[:, 0]], V[tri[:, 2]] - V[tri[:, 0]])
    fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-15)
    vn = np.zeros_like(V)
    np.add.at(vn, tri.ravel(), np.repeat(fn, 3, axis=0))
    vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-15)
    front = cs.get('space', 'uv') == 'front'
    if front:
        # strokes drawn in front, (x, z) in L in the QA's front frame, each point on the frontmost surface there
        x0, z0 = frame if frame is not None else (0.0, 0.0)
        tuv = np.stack([(V[tri][:, :, 0] - x0) / L, (V[tri][:, :, 2] - z0) / L], 2)
    T2 = cKDTree(tuv.mean(1))

    def locate(q):
        """the surface point at q (UV, or front x, z) -> (point, normal, weights) or None."""
        _, cand = T2.query(q, k=min(64 if front else 48, len(tuv)))
        best, bw, by = None, None, np.inf
        for c in np.atleast_1d(cand):
            a, b, d = tuv[c]
            m = np.array([[b[0] - a[0], d[0] - a[0]], [b[1] - a[1], d[1] - a[1]]])
            if abs(np.linalg.det(m)) < 1e-14:
                continue
            s, t = np.linalg.solve(m, q - a)
            w = np.array([1 - s - t, s, t])
            if w.min() >= -1e-6:
                if not front:
                    best, bw = c, w
                    break
                y_ = float((V[tri[c], 1] * w).sum())
                if y_ < by:
                    best, bw, by = c, w, y_
                continue
            if by == np.inf and (best is None or w.min() > bw.min()):
                best, bw = c, w
        if best is None or bw.min() < -0.05:
            return None
        bw = np.clip(bw, 0, None); bw /= bw.sum()
        ix = tri[best]
        n = (vn[ix] * bw[:, None]).sum(0)
        return (V[ix] * bw[:, None]).sum(0), n / max(np.linalg.norm(n), 1e-15), \
            ((W[ix] * bw[:, None]).sum(0) if W is not None else None)
    width, lift = cs.get('width', 0.004) * L, cs.get('lift', 0.002) * L
    taper, tip, step = cs.get('taper', 0.25), cs.get('tip', 0.15), cs.get('step', 0.004) * L
    verts, faces, wts, uvs = [], [], [], []
    for s_ in strokes:
        # the stroke's UV polyline resampled finely, mapped, then resampled at `step` along its 3D length
        seg = np.linalg.norm(np.diff(s_, axis=0), axis=1)
        tt = np.r_[0, np.cumsum(seg)]
        if tt[-1] <= 0:
            continue
        fine = np.linspace(0, tt[-1], max(8, int(tt[-1] * 2000)))
        q = np.c_[np.interp(fine, tt, s_[:, 0]), np.interp(fine, tt, s_[:, 1])]
        got = [locate(x) for x in q]
        ok = [g_ is not None for g_ in got]
        if sum(ok) < 2:
            continue
        P = np.array([g_[0] for g_ in got if g_ is not None])
        N = np.array([g_[1] for g_ in got if g_ is not None])
        Wg = np.array([g_[2] for g_ in got if g_ is not None]) if W is not None else None
        sl = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
        if sl[-1] < 2 * step:
            continue
        sa = np.linspace(0, sl[-1], max(3, int(round(sl[-1] / step)) + 1))
        Ps = np.stack([np.interp(sa, sl, P[:, k]) for k in range(3)], 1)
        Ns = np.stack([np.interp(sa, sl, N[:, k]) for k in range(3)], 1)
        Ns /= np.maximum(np.linalg.norm(Ns, axis=1, keepdims=True), 1e-15)
        Ws = np.stack([np.interp(sa, sl, Wg[:, k]) for k in range(Wg.shape[1])], 1) if Wg is not None else None
        Tg = np.gradient(Ps, axis=0)
        Sd = np.cross(Ns, Tg)
        Sd /= np.maximum(np.linalg.norm(Sd, axis=1, keepdims=True), 1e-15)
        f_ = sa / sa[-1]
        e_ = np.minimum(f_, 1 - f_) / max(taper / 2, 1e-9)
        hw = 0.5 * width * (tip + (1 - tip) * np.clip(e_, 0, 1))
        base = len(verts)
        for i in range(len(sa)):
            c_ = Ps[i] + Ns[i] * lift
            verts += [c_ + Sd[i] * hw[i], c_ - Sd[i] * hw[i]]
            uvs += [(f_[i], 0.0), (f_[i], 1.0)]
            if Ws is not None:
                wts += [Ws[i], Ws[i]]
        for i in range(len(sa) - 1):
            a_ = base + 2 * i
            faces.append((a_, a_ + 1, a_ + 3, a_ + 2))                # (normal along the surface's: outward)
    if not faces:
        return None
    verts = np.asarray(verts)
    Wd = {k: np.asarray(wts)[:, j] for j, k in enumerate(wk)} if wk else {}
    return dict(verts=verts, faces=faces, weights=Wd, uv=np.asarray(uvs, float))


def with_ink(G, s, mats, midx, L, line, frame=None, uv_key='uv'):
    """a piece with its creases (s['creases'], ink_strokes) appended: their faces on an ink material (the line colour,
    `line`), so the piece stays one object (the QA's piece masks, the evaluator's one object per garment) and its
    strokes are drawn as lines (qa3d.render_surfaces). The strokes take no outline and no thickness: the weights'
    OUTLINE_W group (1 the piece, 0 the strokes; _object makes the vertex group, shade.outline reads it), and the ink
    faces' Solidify copies are dropped (evalmesh.finalize). -> (G, mats, midx)."""
    cs = s.get('creases')
    if not cs:
        return G, mats, midx
    K = ink_strokes(G, cs, L, frame)
    if K is None:
        return G, mats, midx
    n0, nf0 = len(G['verts']), len(G['faces'])
    G = dict(G)
    G['verts'] = np.r_[np.asarray(G['verts'], float), K['verts']]
    G['faces'] = [tuple(f) for f in G['faces']] + [tuple(int(i) + n0 for i in f) for f in K['faces']]
    W = {}
    for b in set(G['weights']) | set(K['weights']):
        a_ = np.asarray(G['weights'].get(b, np.zeros(n0)), float)
        k_ = np.asarray(K['weights'].get(b, np.zeros(len(K['verts']))), float)
        W[b] = np.r_[a_, k_]
    G['weights'] = W
    if uv_key == 'uv' and G.get('uv') is not None:
        G['uv'] = [tuple(x) for x in np.asarray(G['uv'], float)] + [tuple(x) for x in K['uv']]
    elif G.get('uvs') is not None:
        G['uvs'] = list(G['uvs']) + [[tuple(K['uv'][i]) for i in f] for f in K['faces']]
    mats = list(mats) + [_toon(s['name'] + INK, cs.get('color', line), (1.0, 1.0, 1.0))]
    ink = len(mats) - 1
    midx = (list(midx) if midx is not None else [0] * nf0) + [ink] * len(K['faces'])
    G['weights'][OUTLINE_W] = np.r_[np.ones(n0), np.zeros(len(K['verts']))]
    return G, mats, midx


def hem_snap(V, F, used, keep, sv, cut, ins):
    """a shell's hem cut clean: whole faces kept above the cut left a staircase of the body's faces (the shorts' hem
    read notched); each vertex on the kept faces' lower border moved down its edges to the body's outside neighbours,
    to where they cross the cut (their mean), carrying the shell's offset. -> the moved shell vertices."""
    kept = np.zeros(len(V), bool)
    for i in keep:
        kept[list(F[i])] = True
    zc = cut(V)
    moves = {}
    for f in F:
        for a, b in zip(f, list(f[1:]) + [f[0]]):
            for u, w in ((a, b), (b, a)):
                if kept[u] and not ins[w] and V[w, 2] < zc[w] and V[u, 2] >= zc[u]:
                    du, dw = V[u, 2] - zc[u], V[w, 2] - zc[w]
                    k = du / max(1e-12, du - dw)
                    moves.setdefault(u, []).append(V[u] + (V[w] - V[u]) * k)
    idx = {o: n for n, o in enumerate(used)}
    sv = sv.copy()
    for u, ps in moves.items():
        if u in idx:
            sv[idx[u]] += np.mean(ps, 0) - V[u]
    return sv


def ease_to_band(A, sv, ez, band):
    """a shell's vertices eased onto a band over it (the top under the waistband): above the band's top edge, over
    `over` L, out to the band's face (its second row, under its rounded edge) less `gap` L, so the outline runs into
    the band without a step; under the band, within its outside down to `hold` L below its top edge (inside its
    thickness), then inside its inner surface by `clear` L (the band's thickness in its spec). Only ever outward above
    the band. band: (its spec, belt_hull's result). -> the moved vertices."""
    from .geom import loft
    L = A['head']['L']
    bs, Gb = band                                               # (its spec, belt_hull's)
    ax, Fb = Gb['axis'], loft.Field(Gb['ts'], Gb['th'], Gb['R'], None)
    t, th, r = ax.coords(sv)
    t0 = Gb['ts'][0]
    face = Fb.at(np.full(len(t), Gb['ts'][min(1, len(Gb['ts']) - 1)]), th) - ez.get('gap', 0.004) * L
    inner = Fb.at(np.clip(t, t0, Gb['ts'][-1]), th) - bs.get('thick', 0.025) * L - ez.get('clear', 0.004) * L
    over, hold = ez.get('over', 0.12) * L, ez.get('hold', 0.03) * L
    w = np.clip((t - (t0 - over)) / over, 0, 1)
    w = w * w * (3 - 2 * w)                                    # 0 at `over` above the edge .. 1 at it
    out = r + np.maximum(0.0, face - r) * w                    # above the edge: eased out to the band's face
    k = np.clip((t - t0 - hold) / (0.02 * L), 0, 1)            # under it: at its face down to `hold` (inside its
    under = (1 - k) * face + k * np.minimum(r, inner)          # thickness), then into its inner surface over 0.02 L
    r_new = np.where(t <= t0, out, under)
    return ax.point(t, th, r_new)


def snap_cuts(V, F, used, keep, sv, cuts, ins):
    """a shell's cuts made clean (hem_snap for any cut): each vertex on the kept faces' border moved toward the removed
    vertices it shares a face with that a cut drops (g(them) < 0 <= g(it), g one of `cuts`: a signed function of world
    points, >= 0 kept), to where that cut crosses the line between them (the mean over them and the cuts), carrying the
    shell's offset. -> the moved shell vertices."""
    V = np.asarray(V, float)
    kept = np.zeros(len(V), bool)
    for i in keep:
        kept[list(F[i])] = True
    G = [np.asarray(g(V), float) for g in cuts]
    # every ordered pair of vertices sharing a face (numpy: faces padded to their largest size)
    k = max(len(f) for f in F)
    P = np.full((len(F), k), -1, np.int64)
    for n in set(len(f) for f in F):
        sel = [i for i, f in enumerate(F) if len(f) == n]
        P[sel, :n] = np.array([F[i] for i in sel])
    U = np.repeat(P, k, 1).ravel()
    Wv = np.tile(P, (1, k)).ravel()
    ok = (U >= 0) & (Wv >= 0) & (U != Wv)
    U, Wv = U[ok], Wv[ok]
    ok = kept[U] & ~ins[Wv]
    U, Wv = U[ok], Wv[ok]
    acc = np.zeros((len(V), 3))
    cnt = np.zeros(len(V))
    for g in G:
        c = (g[Wv] < 0) & (g[U] >= 0)
        u, w = U[c], Wv[c]
        t = g[u] / np.maximum(1e-12, g[u] - g[w])
        np.add.at(acc, u, V[u] + (V[w] - V[u]) * t[:, None])
        np.add.at(cnt, u, 1)
    sv = sv.copy()
    idx = np.full(len(V), -1)
    idx[np.asarray(used)] = np.arange(len(used))
    m = (cnt > 0) & (idx >= 0)
    sv[idx[m]] += acc[m] / cnt[m, None] - V[m]
    return sv


def opening_cut(A, op):
    """a jacket's open front as a signed cut: |x| less the opening's half-width at the point's height on the body's
    front (y before the chest's head), else 1 L (kept). op: `half` [[z, half], ...] (L from the eye line; held past its
    ends). -> fn(world points) -> (n,) (>= 0 outside the opening)."""
    L = A['head']['L']
    ez = _eye_z(A)
    K = np.asarray(sorted(op['half']), float)
    yc = bone_seg(A, op.get('front_of', 'chest'))[0][1]

    def g(X):
        X = np.asarray(X, float)
        half = np.interp((X[:, 2] - ez) / L, K[:, 0], K[:, 1]) * L
        return np.where(X[:, 1] < yc, np.abs(X[:, 0]) - half, L)
    return g


def _eye_z(A):
    """the garments' eye line (world z), the one frame every height the builders read from the drawing is placed in
    (the cuts at 'eye', the opening, the collar's outline, the drape, the lofts' rows, the drawn extents, the hull's
    alignment): the QA's. The body QA (bodyqa.origin) registers our iris plates' mean on the design's eye row (the
    drawn irises' centroid), so the drawn heights are the irises' too; the head's knob line (eye_knobs.z, the face's
    and the body's frame) sits 0.0235 L under it on the authored head, and every garment landed that much low in the
    checks. Without irises (a bare assembly): the knob line."""
    L = A['head']['L']
    I = [np.asarray(E['iris'][0], float) for E in (A.get('eyes') or []) if E.get('iris') is not None]
    if I:
        return float(np.mean([i[:, 2].mean() for i in I]))
    return A['head']['centre'][2] + A['head']['eye_knobs']['z'] * L


def outline_dist(A, ol, X):
    """a sailor collar's outline (`outline`) at world points: (the signed distance inside it, L: > 0 inside, and the
    distance in from its outer edge). Front (y before the chest's head): the lapels between an inner edge (the V
    neckline) and an outer one, `front` [[z, inner half, outer half], ...] (L from the eye line; |x| between them);
    back: the flap, `back` [[z, half], ...] down to `bottom` (L from the eye line). Distances are in the front or back
    projection (x, z). Front from back: a plane at `front_of`'s head (default the chest's), or with `split` the halves
    blended by angle round the neck (split_weight). With `top`, its upper edge up the neck (outline_top). With `perp`,
    the lapels' distance in from the outer edge is measured square to it (_perp_out: the stripe's), not across x."""
    L = A['head']['L']
    X = np.asarray(X, float)
    z = (X[:, 2] - _eye_z(A)) / L
    ax_ = np.abs(X[:, 0]) / L
    yc = bone_seg(A, ol.get('front_of', 'chest'))[0][1]
    K = np.asarray(sorted(ol['front']), float)
    inner, outer = np.interp(z, K[:, 0], K[:, 1]), np.interp(z, K[:, 0], K[:, 2])
    top = K[:, 0].max()
    d_front_out = outer - ax_
    d_front = np.minimum(ax_ - inner, d_front_out)
    Kb = np.asarray(sorted(ol['back']), float)
    half = np.interp(z, Kb[:, 0], Kb[:, 1])
    d_back_out = np.minimum(half - ax_, z - ol['bottom'])
    w = split_weight(A, ol['split'], X, z) if ol.get('split') else (X[:, 1] < yc).astype(float)
    d = w * d_front + (1 - w) * d_back_out
    if ol.get('top') is not None:
        d = np.minimum(d, outline_top(A, ol, X) - z)
    if ol.get('perp'):                                       # the stripe's distance square to the lapel's outer edge
        d_front_out = _perp_out(K, ax_, z)
    return d * L, (w * d_front_out + (1 - w) * d_back_out) * L


def outline_top(A, ol, X):
    """a sailor collar's upper edge up the neck (`top`: L from the eye line, a number or [[degrees round the neck from
    the front, z], ...] mirrored, round the split's axis), the collar's cut up the neck as part of its outline: a signed
    cut, snapped with the outline (snap_cuts), so its edge is a smooth line and its height continuous. The `eye` height
    cut (a hard cut on the body's rows, before `refine`) put it on one body row or the next: the collar's cut snapped
    between two states (posts beside the neck in front, or none and a torn wedge in profile). Only in the signed
    distance: the stripe keeps to the outer edge. -> (n,) z, L from the eye line."""
    tp = ol['top']
    if not isinstance(tp, (list, tuple)):
        return np.full(len(X), float(tp))
    h = bone_seg(A, (ol.get('split') or {}).get('about', 'neck'))[0]
    th = np.degrees(np.arctan2(np.abs(X[:, 0] - h[0]), h[1] - X[:, 1]))      # 0 in front (-y), 180 behind
    K = np.asarray(sorted(tp), float)
    return np.interp(th, K[:, 0], K[:, 1])


def split_weight(A, sp, X, z):
    """a sailor collar's front/back partition by angle round an upright axis through a bone's head (`about`, the
    neck's: the lapels' share of the outline, 1 in front, 0 behind), not a plane: a plane at the chest's head wraps the
    whole neck in the back panel (neck_crease, the front torn), one at the neck's own head tears the profile where the
    halves meet. sp: {about, deg: the partition's angle from the front (degrees; a number or [[z, deg], ...], L from
    the eye line), soft: the width of its smoothstep (degrees)}; the outline's distance is the halves' blend by it, so
    the edge where they meet is continuous. -> (n,) in [0, 1]."""
    h = bone_seg(A, sp.get('about', 'neck'))[0]
    th = np.degrees(np.arctan2(np.abs(X[:, 0] - h[0]), h[1] - X[:, 1]))      # 0 in front (-y), 180 behind
    dg = sp['deg']
    if isinstance(dg, (list, tuple)):
        K = np.asarray(sorted(dg), float)
        dg = np.interp(z, K[:, 0], K[:, 1])
    s = max(float(sp.get('soft', 30.0)), 1e-6)
    u = np.clip((th - (dg - s / 2)) / s, 0, 1)
    return 1 - u * u * (3 - 2 * u)


def outline_cut(A, ol):
    """outline_dist's signed distance as a cut (>= 0 kept)."""
    return lambda X: outline_dist(A, ol, X)[0]


LAST_LIFT = {}      # the latest collar_lift's diagnostics (the stand's bins), for the harness


def collar_lift(A, S, F, spec, hull=None):
    """the template collar's lifted surface: the region's shell vertices S (the body + `offset`, before any cut) moved
    by the `stand` round the neck (collar_stand), then pushed clear of the layers under it, `over` (collar_drape).
    -> the moved vertices."""
    if spec.get('stand'):
        st = dict(spec['stand'])
        st.setdefault('top', (spec.get('outline') or {}).get('top'))
        S = collar_stand(A, S, st, spec.get('offset', 0.012))
        LAST_LIFT['stand'] = st.get('_bins')
    if isinstance(spec.get('over'), (list, tuple)):
        S = collar_drape(A, S, F, spec, hull)
    return S


def collar_stand(A, S, st, offset):
    """a sailor collar standing up round the neck and falling over the shoulders (Michael's round-5 flag: the drawn
    collar rises round the neck, about -0.42 L at the sides, and slopes down over the shoulder to its peak, 0.03-0.10 L
    above a shell on the level shoulders). In each half-plane round an upright axis through the neck's head (`about`)
    at azimuth theta, the shell's profile runs down the neck from the neckline `top` ([[degrees from the front, z],
    ...], L from the eye line; the outline's `top` by default) to the shoulder's start (the junction: the first point
    `junction` L out from the neck), then out along the shoulder (or down the chest, the back). Past the junction the
    shell is lifted straight up by `lift` ([[d rho from the neck, L], ...]), faded out below the junction's height over
    `fade` L (so a wall or the chest below keeps its place: the lift eases off down it). The neck's band above the
    junction is unrolled onto the line from the neck's surface less `gap` at the neckline to the lifted junction (by
    its L1 length from the neckline): the map keeps the profile's order (no fold where the band meets the shoulder)
    and meets the lift at the junction. Weighted by azimuth `w` ([[degrees, 0..1], ...]: 0 keeps the shell); profiles
    every `bin` degrees, a vertex blending its two bins. S: (n, 3) world points; offset: the shell's (L). -> the moved
    points."""
    L = A['head']['L']
    ez = _eye_z(A)
    h = bone_seg(A, st.get('about', 'neck'))[0]
    S = np.asarray(S, float)
    dx, dy = S[:, 0] - h[0], S[:, 1] - h[1]
    rr = np.maximum(np.hypot(dx, dy), 1e-12)
    th = np.degrees(np.arctan2(np.abs(dx), -dy))
    rho, z = rr / L, (S[:, 2] - ez) / L
    tp = st['top']
    Kt = np.asarray(sorted(tp), float) if isinstance(tp, (list, tuple)) else np.array([[0.0, tp], [180.0, tp]], float)
    Kw = np.asarray(sorted(st.get('w', [[0, 1], [180, 1]])), float)
    Kl = np.asarray(sorted(st['lift']), float)
    gap, step, fade = st.get('gap', 0.008), float(st.get('bin', 5.0)), st.get('fade', 0.12)
    dj = st.get('junction', 0.04)
    D = np.zeros((len(S), 2))
    st['_bins'] = bins = {}
    for c in np.arange(0.0, 180.0 + 1e-6, step):
        wc = float(np.interp(c, Kw[:, 0], Kw[:, 1]))
        lam = np.clip(1.0 - np.abs(th - c) / step, 0.0, 1.0)
        if wc <= 0 or not (lam > 0).any():
            continue
        sel = np.abs(th - c) <= max(2.5, 0.6 * step)
        zn = float(np.interp(c, Kt[:, 0], Kt[:, 1]))
        m = sel & (np.abs(z - zn) < 0.012)
        if m.sum() < 3:
            bins[c] = 'no neck at the neckline'
            continue
        rho_ref = float(np.median(rho[m & (rho < rho[m].min() + 0.03)]))    # the shell on the neck at the neckline
        rho0 = rho_ref - offset + gap                                        # the neck's own surface + gap
        u = (zn - z[sel]) + (rho[sel] - rho_ref)
        jn = (u > 0) & (rho[sel] > rho_ref + dj)
        if not jn.any():
            bins[c] = 'no junction'
            continue
        k = np.nonzero(jn)[0][np.argmin(u[jn])]
        uj, rj, zj = float(u[k]), float(rho[sel][k]), float(z[sel][k])
        Qz = zj + float(np.interp(rj - rho0, Kl[:, 0], Kl[:, 1], right=0.0))
        uv = (zn - z) + (rho - rho_ref)
        a = (lam > 0) & (uv > 0)
        band = a & (uv < uj)
        f = uv[band] / uj
        tr, tz = rho0 + f * (rj - rho0), zn + f * (Qz - zn)
        D[band, 0] += lam[band] * wc * (tr - rho[band])
        D[band, 1] += lam[band] * wc * (tz - z[band])
        out_ = a & (uv >= uj)
        lz = np.interp(rho[out_] - rho0, Kl[:, 0], Kl[:, 1], right=0.0)
        q = np.clip((zj - z[out_]) / fade, 0.0, 1.0)
        D[out_, 1] += lam[out_] * wc * lz * (1.0 - q * q * (3 - 2 * q))
        bins[c] = dict(zn=round(zn, 4), rho_ref=round(rho_ref, 4), junction=[round(rj, 4), round(zj, 4)],
                       Q=round(Qz, 4), uj=round(uj, 4), n=int(band.sum()))
    out = S.copy()
    rn = (rho + D[:, 0]) * L
    out[:, 0] = h[0] + dx / rr * rn
    out[:, 1] = h[1] + dy / rr * rn
    out[:, 2] = ez + (z + D[:, 1]) * L
    return out


def under_layers(A, spec, names, hull=None):
    """the outer surfaces of the garments a piece lies over (by name from the whole spec, `_spec`): the shells' and the
    template puffs' vertices (their Solidify goes inward: the vertices are the outside) and normals. -> (P, N)."""
    specs = {g['name']: g for g in (spec.get('_spec') or {}).get('garments', [])}
    nb = vertex_normals(A['verts'], A['faces'])
    P, N = [], []
    for nm in names:
        g = specs.get(nm)
        if g is None:
            continue
        if g['kind'] == 'shell':
            G = shell(A, dict(g, _spec=spec.get('_spec')), nb, hull)
        elif g['kind'] == 'sleeve' and g.get('source') == 'template':
            G = puff(A, dict(g, _spec=spec.get('_spec')), hull)
        else:
            continue
        P.append(np.asarray(G['verts'], float))
        N.append(vertex_normals(np.asarray(G['verts'], float), G['faces']))
    if not P:
        return np.zeros((0, 3)), np.zeros((0, 3))
    return np.vstack(P), np.vstack(N)


def collar_drape(A, S, F, spec, hull=None):
    """a collar lying over the layers under it (`over`: garment names, the jacket and the puffs), not through them:
    each vertex pushed out along its normal until its inner surface (its `thick` in from it) clears the under-layers'
    outer surfaces by `over_gap` L. The clearance is read from the under-layers' vertices near the vertex's normal ray
    (within `over_reach` L across it and `over_depth` along it, facing its way): the signed distance to their tangent
    planes, a push at most `over_cap` L; the pushes eased over the mesh
    (the 1-ring's largest, then averaged) so the collar doesn't dent round a stray vertex. -> the moved points."""
    from scipy.spatial import cKDTree
    from scipy import sparse
    L = A['head']['L']
    P, N = under_layers(A, spec, spec['over'], hull)
    S = np.asarray(S, float).copy()
    if not len(P):
        return S
    tree = cKDTree(P)
    need = (spec.get('over_gap', 0.004) + spec.get('thick', 0.005)) * L
    reach = spec.get('over_reach', 0.02) * L
    depth, cap = spec.get('over_depth', 0.08) * L, spec.get('over_cap', 0.08) * L
    n = len(S)
    rows = [v for f in F for v in f]
    cols = [f[(k + 1) % len(f)] for f in F for k in range(len(f))]
    Adj = sparse.coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(n, n)).tocsr()
    Adj = ((Adj + Adj.T) > 0).astype(float)
    deg = np.maximum(np.asarray(Adj.sum(1)).ravel(), 1)
    for _ in range(spec.get('over_iters', 3)):
        nS = vertex_normals(S, F)
        idx = tree.query_ball_point(S, reach + depth)
        t = np.zeros(n)
        for i, js in enumerate(idx):
            if not js:
                continue
            Q = P[js] - S[i]
            along_ = Q @ nS[i]
            lat = np.linalg.norm(Q - np.outer(along_, nS[i]), axis=1)
            c = N[js] @ nS[i]
            # the layer under this vertex: near its normal ray, within `over_depth` of it along the ray, facing the
            # same way (not the far side of an arm or the body)
            k = (lat < reach) & (np.abs(along_) < depth) & (c > 0.5)
            if not k.any():
                continue
            sd = -np.einsum('ij,ij->i', Q[k], N[js][k])      # the vertex over each tangent plane (+ outside)
            t[i] = min(cap, max(0.0, float(((need - sd) / c[k]).max())))
        if not t.any():
            break
        for _ in range(2):
            t = np.maximum(t, (Adj.multiply(t[None, :])).max(1).toarray().ravel())
        for _ in range(3):
            t = 0.5 * t + 0.5 * (Adj @ t) / deg
        S = S + nS * t[:, None]
    return S


def _perp_out(K, ax_, z):
    """the distance (L) in from a lapel's outer edge measured square to it: the outer edge as the polyline of the front
    table's (outer half-width, z) rows, the point (|x|, z)'s distance to it, + inside (|x| under the edge's half-width at
    its height). A slanted edge measured across x (outline_dist's own) widens a band along it by 1/cos of its slant."""
    E = K[:, [2, 0]]                                          # (outer, z) per row, z ascending
    P = np.c_[ax_, z]
    best = np.full(len(P), np.inf)
    for a, b in zip(E[:-1], E[1:]):
        ab = b - a
        t = np.clip(((P - a) @ ab) / max(float(ab @ ab), 1e-12), 0, 1)
        best = np.minimum(best, np.linalg.norm(P - (a + t[:, None] * ab), axis=1))
    return np.where(np.interp(z, K[:, 0], K[:, 2]) - ax_ >= 0, best, -best)


def stripe_cut(A, sv, sf, ol, st, W=None):
    """a collar's stripe cut into its mesh (Michael's round-5 flags: the lapels' stripe showed as triangular pieces, the
    back panel's as a jagged, stepped bar): every face its two edges cross (the outline's distance in from its outer
    edge at `in` and `in` + `width` L) split along them, the split points on the crossed edges shared by the faces
    either side and put on the line (a Newton step along the distance's gradient in the projection's plane), so the
    stripe's edges run along mesh edges and each face lies wholly on one side; vertices within `snap` of an edge's
    length of a line are moved onto it instead (no slivers). The faces between the lines take the second material.
    `front` {in, width}: the lapels' own (blended into the panel's as the outline blends its halves).
    W: the vertices' bone weights ({bone: (n,)}), carried to the new vertices along their edges. -> (vertices, faces,
    per face 0/1, weights)."""
    L = A['head']['L']
    V = np.asarray(sv, float).copy()
    F = [tuple(int(v) for v in f) for f in sf]
    W = {b: np.asarray(w, float) for b, w in (W or {}).items()}
    e = np.median([np.linalg.norm(V[f[0]] - V[f[1]]) for f in F[:500]]) if F else 0.01 * L
    hh = 1e-3 * L
    fr = st.get('front') or {}
    ez = _eye_z(A)
    yc = bone_seg(A, ol.get('front_of', 'chest'))[0][1]

    def lines(X):
        # the stripe's two edges' distances at X: the lapels' (`front` {in, width}) and the panel's blended as the
        # outline blends its halves
        if not fr:
            return np.full(len(X), st['in'] * L), np.full(len(X), (st['in'] + st['width']) * L)
        w = split_weight(A, ol['split'], X, (X[:, 2] - ez) / L) if ol.get('split') else (X[:, 1] < yc).astype(float)
        i0 = w * fr.get('in', st['in']) + (1 - w) * st['in']
        return i0 * L, (i0 + w * fr.get('width', st['width']) + (1 - w) * st['width']) * L

    def g_of(X, k):
        return outline_dist(A, ol, X)[1] - lines(X)[k]

    def onto(X, k):
        g = np.stack([(g_of(X + hh * np.eye(3)[j], k) - g_of(X - hh * np.eye(3)[j], k)) / (2 * hh) for j in (0, 2)], 1)
        step = -g_of(X, k) / np.maximum((g ** 2).sum(1), 1e-12)
        X = X.copy()
        X[:, 0] += step * g[:, 0]
        X[:, 2] += step * g[:, 1]
        return X
    for k_line in (0, 1):
        g = g_of(V, k_line)
        near = np.abs(g) < st.get('snap', 0.2) * e
        if near.any():
            V[near] = onto(V[near], k_line)
            g = g_of(V, k_line)
            g[near] = 0.0
        newv, NV, NW, out = {}, [], {b: [] for b in W}, []
        for f in F:
            gf = g[list(f)]
            if (gf >= 0).all() or (gf <= 0).all():
                out.append(f)
                continue
            pos, neg = [], []
            for k in range(len(f)):
                a, b = f[k], f[(k + 1) % len(f)]
                ga, gb = g[a], g[b]
                if ga >= 0:
                    pos.append(a)
                if ga <= 0:
                    neg.append(a)
                if ga * gb < 0:
                    key = (min(a, b), max(a, b))
                    if key not in newv:
                        t = g[key[0]] / (g[key[0]] - g[key[1]])
                        newv[key] = len(V) + len(NV)
                        NV.append(V[key[0]] + t * (V[key[1]] - V[key[0]]))
                        for bn in W:
                            NW[bn].append(W[bn][key[0]] + t * (W[bn][key[1]] - W[bn][key[0]]))
                    pos.append(newv[key])
                    neg.append(newv[key])
            out += [tuple(p) for p in (pos, neg) if len(p) >= 3]
        if NV:
            NV = onto(np.asarray(NV), k_line)
            V = np.vstack([V, NV])
            W = {bn: np.r_[W[bn], NW[bn]] for bn in W}
        F = out
    C = np.array([V[list(f)].mean(0) for f in F])
    return V, F, ((g_of(C, 0) >= 0) & (g_of(C, 1) <= 0)).astype(np.int32), W


def stripe_faces(A, sv, sf, ol, st):
    """a collar's stripe: the faces whose centre lies `in` to `in` + `width` L in from the outline's outer edge (a second
    material), with the vertices within half an edge of the stripe's two edges moved onto them along the distance's
    gradient (numerical), so its edges run straight rather than stepping with the faces. -> (vertices, per face 0/1)."""
    L = A['head']['L']
    sv = np.asarray(sv, float).copy()
    d0, d1 = st['in'] * L, (st['in'] + st['width']) * L
    e = np.median([np.linalg.norm(sv[f[0]] - sv[f[1]]) for f in sf[:500]]) if len(sf) else 0.01 * L
    h = 1e-3 * L
    for d_ in (d0, d1):
        dist = outline_dist(A, ol, sv)[1]
        near = np.abs(dist - d_) < 0.5 * e
        if not near.any():
            continue
        P = sv[near]
        g = np.stack([(outline_dist(A, ol, P + h * np.eye(3)[k])[1] - outline_dist(A, ol, P - h * np.eye(3)[k])[1]) /
                      (2 * h) for k in (0, 2)], 1)                    # in the projection's plane (x, z)
        gn = np.maximum((g ** 2).sum(1), 1e-12)
        step = (d_ - dist[near]) / gn
        sv[near, 0] += step * g[:, 0]
        sv[near, 2] += step * g[:, 1]
    C = np.array([sv[list(f)].mean(0) for f in sf])
    dc = outline_dist(A, ol, C)[1]
    return sv, ((dc >= d0) & (dc <= d1)).astype(np.int32)


def _by_azimuth(K, th):
    """a knot table [[degrees from the front, value], ...] (mirrored: |theta|) at angles th (radians)."""
    K = np.asarray(sorted(K), float)
    return np.interp(np.degrees(np.abs(np.angle(np.exp(1j * np.asarray(th, float))))), K[:, 0], K[:, 1])


def hem_over_band(A, ez, band):
    """the hem of a shell hung over a band (ease mode 'over'): the band's top edge less `hang` L, a number or a knot
    table by azimuth round the band's axis ([[degrees from the front, L], ...]: a jacket's fronts hang lower than its
    bib). -> fn(world points) -> the hem's height (world z) there."""
    L = A['head']['L']
    Gb = band[1]
    ax = Gb['axis']
    z_top = float(ax.o[2] - Gb['ts'][0])                      # the band's axis is upright: its top edge is level
    hang = ez.get('hang', 0.03)

    def hz(X):
        th = ax.coords(np.asarray(X, float))[1]
        h = _by_azimuth(hang, th) if isinstance(hang, (list, tuple)) else np.full(len(th), float(hang))
        return z_top - h * L
    return hz


def ease_over_band(A, sv, ez, band, source=None):
    """a shell's vertices hung over a band (a jacket's hem outside the waistband, garments2): the drape's radius round the
    band's axis is the band's face (its second row, under its rounded edge) plus `gap` L, or a flare (`flare`: a knot
    table [[degrees from the front, radius L from the band's axis], ...]: the jacket's hem standing off the waist, as
    the design's silhouettes show it) where that is further out. Above the band's top edge, over `over` L, eased out
    toward it (only ever outward); from the edge down, hung straight at it (the body narrows under the band; the
    drape doesn't). With `drape` {from: L from the eye line}, first hung from the bust (below: forward, per column
    across), from the vertices `source` marks (the torso's: a shoulder's or an arm's would hang the sides out to the
    arms), round the front only (`az` [a0, a1]: fully to a0 degrees from the front, out by a1: the design's back is
    fitted), with `taper` p coming back in to the band's drape by its top edge (the p-th power of the way down).
    band: (its spec,
    belt_hull's result). -> the moved vertices."""
    from .geom import loft
    L = A['head']['L']
    bs, Gb = band
    ax, Fb = Gb['axis'], loft.Field(Gb['ts'], Gb['th'], Gb['R'], None)
    t, th, r = ax.coords(sv)
    t0 = Gb['ts'][0]
    dr = ez.get('drape')
    if dr:
        # hung from the bust: below `from` (L from the eye line) the front hangs straight down from the furthest forward
        # it reaches above, per column across the body (its forward depth's running maximum down the axis, in columns
        # of `step` L sideways): a jacket's front panels fall from the bust, forward of the midriff (in profile they
        # stand before the bib, as drawn), and stay where they are across (the opening keeps its width in front)
        ez_ = _eye_z(A)
        t_from = float(ax.o[2] - (ez_ + dr['from'] * L))
        step = dr.get('step', 0.02) * L
        fwd, side = r * np.cos(th), r * np.sin(th)
        a0, a1 = dr.get('az', (60.0, 100.0))               # the fronts hang; the fitted back doesn't (in fully to a0
        deg = np.degrees(np.abs(th))                       # degrees from the front, out by a1)
        wa = np.clip((a1 - deg) / max(1e-6, a1 - a0), 0, 1)
        sel = (t >= t_from - step) & (wa > 0) & (source if source is not None else True)
        if sel.sum() > 20:
            ts = np.arange(t_from, max(t.max(), t_from + 2 * step) + step, step)
            bs = np.arange(side[sel].min() - step, side[sel].max() + 2 * step, step)
            it = np.clip(np.rint((t[sel] - ts[0]) / step).astype(int), 0, len(ts) - 1)
            ib = np.clip(np.rint((side[sel] - bs[0]) / step).astype(int), 0, len(bs) - 1)
            Y = np.full((len(ts), len(bs)), -np.inf)
            np.maximum.at(Y, (it, ib), fwd[sel])
            for i in range(len(ts)):                       # each row filled across from its measured columns
                ok = np.isfinite(Y[i])
                Y[i] = np.interp(np.arange(len(bs)), np.nonzero(ok)[0], Y[i, ok]) if ok.sum() >= 2 else \
                    (Y[i - 1] if i else Y[i])
            Y = np.maximum.accumulate(Y, axis=0)
            k = int(round(dr.get('spread', 0.0) * L / step))    # a panel, not a column: each column hangs from the
            if k:                                                # furthest forward within `spread` L across
                P_ = np.pad(Y, ((0, 0), (k, k)), mode='edge')
                Y = np.max(np.stack([P_[:, j:j + Y.shape[1]] for j in range(2 * k + 1)]), 0)
            Y = loft.gauss1d(Y, dr.get('smooth', 1.0), axis=1)
            jt = np.clip(np.rint((t - ts[0]) / step).astype(int), 0, len(ts) - 1)
            hang = np.array([np.interp(sb, bs, Y[k]) for sb, k in zip(side, jt)]) if len(t) else fwd
            if dr.get('taper'):
                # back in toward the band at the hem, as the `taper` power of the way down
                tgt = (Fb.at(np.full(len(t), Gb['ts'][min(1, len(Gb['ts']) - 1)]), th) + ez.get('gap', 0.015) * L) * \
                    np.cos(th)
                sw = np.clip((t - t_from) / max(1e-9, t0 - t_from), 0, 1) ** dr['taper']
                hang = hang + (np.minimum(hang, tgt) - hang) * sw
            fwd = np.where(t >= t_from, fwd + np.maximum(0.0, hang - fwd) * wa, fwd)
            r, th = np.hypot(fwd, side), np.arctan2(side, fwd)
    drape = Fb.at(np.full(len(t), Gb['ts'][min(1, len(Gb['ts']) - 1)]), th) + ez.get('gap', 0.015) * L
    if ez.get('flare'):
        drape = np.maximum(drape, _by_azimuth(ez['flare'], th) * L)
    over = ez.get('over', 0.25) * L
    w = np.clip((t - (t0 - over)) / over, 0, 1)
    w = w * w * (3 - 2 * w)                                    # 0 at `over` above the edge .. 1 at it
    r_new = np.where(t <= t0, r + np.maximum(0.0, drape - r) * w, np.maximum(r, drape))
    return ax.point(t, th, r_new)


def panel_inside(A, P_, X, Z):
    """a shell's front panel (the spec's `panel`) at world x, z: its half-width is either a knot table (`profile`
    [[dz, half], ...]: L over the `at` bone's head, default the upper chest; held past its ends, so it runs on under a
    band below) or the trapezoid from `from` to `to` (`half_top`, `half_bottom`). -> (inside (bool), z range of the
    texture (lo, hi))."""
    L = A['head']['L']
    X, Z = np.asarray(X, float), np.asarray(Z, float)
    if 'profile' in P_:
        at = P_.get('at', ['upperChest', 0.0])
        za = bone_seg(A, at[0])[0][2] + at[1] * L
        K = np.asarray(sorted(P_['profile']), float)
        half = np.interp((Z - za) / L, K[:, 0], K[:, 1]) * L
        return np.abs(X) < half, (za + (K[0, 0] - 0.4) * L, za + (K[-1, 0] + 0.1) * L)
    z0_ = bone_seg(A, P_['from'][0])[0][2] + P_['from'][1] * L
    z1_ = bone_seg(A, P_['to'][0])[0][2] + P_['to'][1] * L
    t_ = np.clip((z1_ - Z) / max(1e-6, z1_ - z0_), 0, 1)
    hw = (P_['half_top'] + (P_['half_bottom'] - P_['half_top']) * t_) * L
    return (Z >= z0_) & (Z <= z1_) & (np.abs(X) < hw), (z0_ - 0.2 * L, z1_ + 0.2 * L)


# -------------------------------------------------------------------------------------------------------------------- bands
def band(A, spec):
    """a ring round a limb (or the torso) at bone t: radius = the body's there + offset, `width` along the bone, a soft
    bevel, an optional flare (the far edge wider). Rigid on its bone. -> dict(verts, faces, weights, uv per vertex)."""
    L = A['head']['L']
    bone, t = spec['bone'], spec.get('t', 0.5)
    h, tl = bone_seg(A, bone)
    ax = (tl - h) / np.linalg.norm(tl - h)
    c = h + (tl - h) * t
    r = spec.get('radius', None)
    r = r * L if r is not None else limb_radius(A, bone, t) + spec.get('offset', 0.01) * L
    w = spec.get('width', 0.08) * L
    flare = spec.get('flare', 0.0) * L
    thick = spec.get('thick', 0.02) * L
    n = spec.get('segs', 48)
    ref = np.array([0, -1.0, 0]) if abs(ax[1]) < 0.9 else np.array([1.0, 0, 0])
    e1 = ref - ax * (ref @ ax); e1 /= np.linalg.norm(e1)
    e2 = np.cross(ax, e1)
    # the profile across the band: (offset along the axis, extra radius): outer face with a bevel, back inside
    prof = [(-w / 2, 0.0), (-w / 2 + thick * 0.3, thick), (w / 2 - thick * 0.3, thick + flare), (w / 2, flare),
            (w / 2, flare - thick * 0.2), (-w / 2, -thick * 0.2)]
    verts, uvs = [], []
    for k in range(n):
        a = 2 * math.pi * k / n
        d = e1 * math.cos(a) + e2 * math.sin(a)
        for j, (dz, dr) in enumerate(prof):
            verts.append(c + ax * dz + d * (r + dr)); uvs.append((k / n, j / (len(prof) - 1)))
    m = len(prof)
    faces = []
    for k in range(n):
        k2 = (k + 1) % n
        for j in range(m):
            j2 = (j + 1) % m
            faces.append((k * m + j, k2 * m + j, k2 * m + j2, k * m + j2))
    return dict(verts=np.array(verts), faces=faces, weights={bone: np.ones(len(verts))}, uv=uvs)


LIMB = ('UpperArm', 'LowerArm', 'Hand', None, 'UpperLeg', 'LowerLeg', 'Foot', 'Toes')   # the humanoid limbs' chains


def limb_neighbours(bone):
    """a humanoid limb bone and the ones before and after it in its chain (leftLowerArm -> leftUpperArm, leftLowerArm,
    leftHand); another bone alone."""
    for side in ('left', 'right'):
        if bone.startswith(side) and bone[len(side):] in LIMB:
            i = LIMB.index(bone[len(side):])
            return [side + LIMB[j] for j in (i - 1, i, i + 1) if 0 <= j < len(LIMB) and LIMB[j]]
    return [bone]


def band_hull(A, spec, hull):
    """a band lofted round its bone's axis through the hull's points of its `piece` (a cuff, a sleeve's end, a boot's
    cuff), between their `span` percentiles along the bone, `offset` L out. Each section is drawn `round_xs` of the way
    to the ellipse fitted to it (a visual hull's sections are polygons: the cuffs read as blocks), its ends rolled in
    over `roll` of its rows by `round` of its thickness (a quarter circle), and it clears the skin under it (its limb's
    vertices there, as a field on the same rows and angles) by `clear` L plus its thickness, which the Solidify grows
    inward: the hull's section can sit inside the limb, and the skin showed through. `bell` (L, default 0) grows its
    top rows out, tapering to its bottom (the drawn wrist cuffs flare toward the elbow; the hull's are near straight).
    Rigid on its bone.
    -> dict(verts, faces, weights, uv, clear (per cell: the inner surface's distance out from the skin, m))."""
    from .geom import loft
    L = A['head']['L']
    bone = spec['bone']
    P = _hull_points(hull, spec)
    h, tl = bone_seg(A, bone)
    ax = loft.Axis(h, tl - h, (0, -1, 0))
    t, th, r = ax.coords(P)
    lo, hi = np.percentile(t, spec.get('span', (2, 98)))
    rows = max(3, int(round((hi - lo) / (spec.get('step', 0.015) * L))) + 1)
    ts = np.linspace(lo, hi, rows)
    nth = spec.get('cols', 48)
    F = loft.field(t, th, r, ts, nth=nth, min_row=0.2, name=spec['name'], prior=float(np.median(r)) if len(r) else None)
    R = F.R + spec.get('offset', 0.0) * L
    if spec.get('bell'):                               # grown by `bell` L at its top (the bone's head end), to 0 at its
        R = R + spec['bell'] * L * np.linspace(1.0, 0.0, len(R))[:, None]       # bottom: a wrist cuff's flare, as drawn
    k = spec.get('round_xs', 0.3)
    if k > 0:                                          # toward each row's ellipse: 1/r^2 = cos^2/a^2 + sin^2/b^2
        M = np.stack([np.cos(F.th) ** 2, np.sin(F.th) ** 2], 1)
        for i in range(len(R)):
            c = np.maximum(np.linalg.lstsq(M, 1.0 / np.maximum(R[i], 1e-6) ** 2, rcond=None)[0], 1e-9)
            R[i] = (1 - k) * R[i] + k / np.sqrt(M @ c)
    thick = spec.get('thick', 0.02) * L
    n_roll = max(1, int(round(spec.get('roll', 0.25) * rows)))
    pull = spec.get('round', 0.8) * thick
    for i in range(n_roll):
        u = (n_roll - i) / n_roll                          # 1 at the end row, toward 0 inward
        d = pull * (1 - math.sqrt(max(0.0, 1 - u * u)))
        R[i] -= d; R[-1 - i] -= d
    dom, _ = dominant(A)
    Q = A['verts'][np.isin(dom, limb_neighbours(bone))]
    tq, thq, rq = ax.coords(Q)
    near = (tq >= lo - 0.01 * L) & (tq <= hi + 0.01 * L) & (rq < 3 * np.median(R))
    gap = np.full(R.shape, np.inf)
    if near.sum() >= 12:
        # the skin's outermost point per cell, spread a cell round (the thumb's base at a wrist cuff's end)
        S = loft.field(tq[near], thq[near], rq[near], ts, nth=nth, q=1.0, smooth=(0.3, 0.3), min_row=0.2).R
        S = np.maximum.reduce([S, np.roll(S, 1, 1), np.roll(S, -1, 1), np.r_[S[:1], S[:-1]], np.r_[S[1:], S[-1:]]])
        R = np.maximum(R, S + thick + spec.get('clear', 0.006) * L)
        gap = R - thick - S
    V, quads, uv = loft.loft(ax, F, R)
    return dict(verts=V, faces=quads, weights={bone: np.ones(len(V))}, uv=[tuple(x) for x in uv], clear=gap)


def shoe_hull(A, spec, hull):
    """a boot's foot lofted through the hull's points of the boot below the ankle (its `piece`, default boot_<side>):
    sections stacked from `overlap` L above the ankle down to the sole round a vertical axis (geom.loft), capped
    underneath; its bottom `sole` band (by height, the sole's) on the second material. Weighted to the foot, its
    front to the toes. The template shoe sized itself round the body's foot plus an instep and read as a balloon; the
    drawn boot is a straight shaft on a close foot.
    Each foot keeps to its own side of the body's midline, `gap` L off it: the hull's resolution closes the narrow gap
    between the feet at the sole, and lofted through it the two feet (and their soles) joined. Its top `blend` L meets
    the shaft (the shell over the lower leg, from the whole spec in `_spec`: the leg's skin plus the shell's offset)
    radius for radius, easing into the hull's section below: the two lofts' radii differed at the seam and the boot's
    outline stepped halfway down. -> dict(verts, faces, weights, uv, sole (per face))."""
    from .geom import loft
    L = A['head']['L']
    side = spec['side']
    suf = '_L' if side == 'left' else '_R'
    sgn = 1.0 if side == 'left' else -1.0
    P = hull[spec.get('piece', 'boot' + suf)]
    ank, ball = bone_seg(A, side + 'Foot')
    mid = float(bone_seg(A, 'hips')[0][0])
    gap = spec.get('gap', 0.03) * L
    P = P[sgn * (P[:, 0] - mid) >= gap]
    top = ank[2] + spec.get('overlap', 0.04) * L
    P = P[P[:, 2] <= top + 0.02 * L]
    sole_z = float(P[:, 2].min())
    c = np.median(P[P[:, 2] < top - 0.05 * L], 0)
    ax = loft.Axis((c[0], c[1], top), (0, 0, -1), (0, -1, 0))
    t, th, r = ax.coords(P)
    rows = max(4, int(round((top - sole_z) / (spec.get('step', 0.02) * L))) + 1)
    ts = np.linspace(0.0, top - sole_z, rows)
    F = loft.field(t, th, r, ts, nth=spec.get('cols', 48), min_row=0.2, name=spec['name'],
                    prior=float(np.median(r)) if len(r) else None)
    R = F.R + spec.get('offset', 0.0) * L
    # the seam with the shaft: the shell's radius at the top, eased into the hull's over `blend` L
    shaft = next((g for g in (spec.get('_spec') or {}).get('garments', []) if g.get('kind') == 'shell' and
                  any(rg[0] == side + 'LowerLeg' for rg in g.get('region', []))), None)
    blend = spec.get('blend', 0.12) * L
    if shaft is not None and blend > 0:
        dom, _ = dominant(A)
        Q = A['verts'][np.isin(dom, [side + 'LowerLeg', side + 'Foot'])]
        tq, thq, rq = ax.coords(Q)
        near = (tq >= -0.02 * L) & (tq <= blend + 0.02 * L)
        if near.sum() >= 12:
            S = loft.field(tq[near], thq[near], rq[near], ts, nth=len(F.th), q=1.0, smooth=(0.5, 1.0), min_row=0.2).R
            w = np.clip(1 - ts / blend, 0, 1)[:, None]
            w = w * w * (3 - 2 * w)                                # smoothstep: 1 at the top, 0 at `blend` down
            R = np.where(w > 0, w * (S + shaft.get('offset', 0.016) * L) + (1 - w) * R, R)
    V, quads, uv = loft.loft(ax, F, R)
    V[:, 0] = mid + sgn * np.maximum(sgn * (V[:, 0] - mid), gap)          # its own side of the midline
    nth = len(F.th)
    # the underside: a fan to the bottom ring's centre (the sole)
    ci = len(V)
    V = np.vstack([V, V[-nth:].mean(0)[None]])
    base = (rows - 1) * nth
    faces = [tuple(reversed(q)) for q in quads]                  # (rows run down: reversed, the faces face out)
    faces += [(ci, base + j, base + (j + 1) % nth) for j in range(nth)]
    uv = [tuple(x) for x in uv] + [(0.5, 1.0)]
    zf = np.array([V[list(f), 2].mean() for f in faces])
    sole = [1 if z < sole_z + spec.get('sole', 0.06) * L else 0 for z in zf]
    d = ball - ank; d[2] = 0; d /= max(1e-9, np.linalg.norm(d))
    u = (V - ank) @ d
    toe = np.clip((u - 0.55 * u.max()) / max(1e-9, 0.2 * u.max()), 0, 1)
    return dict(verts=V, faces=faces, weights={side + 'Foot': 1 - toe, side + 'Toes': toe}, uv=uv, sole=sole)


def belt(A, spec):
    """a band round the torso following its section at a height (between the hips and spine joints by `waist`, like the
    skirt's), `width` tall, lifted by `offset`, with a rounded face. Weighted to the hips (`weights` 'body': the body's
    under it, band_weights). -> dict(verts, faces, weights, uv)."""
    L = A['head']['L']
    hj = bone_seg(A, 'hips')[0]; sj = bone_seg(A, 'spine')[1]
    zw = hj[2] + (sj[2] - hj[2]) * spec.get('waist', 0.55)
    n = spec.get('cols', 96)
    c, rad = body_section(A, zw, n=n)
    off = spec.get('offset', 0.03) * L; w = spec.get('width', 0.12) * L; th = spec.get('thick', 0.02) * L
    prof = [(w / 2, 0.0), (w / 2 - th * 0.4, th), (-w / 2 + th * 0.4, th), (-w / 2, 0.0), (-w / 2, -th * 0.3), (w / 2, -th * 0.3)]
    verts, uvs = [], []
    for k in range(n):
        a = -math.pi + 2 * math.pi * k / n
        for j, (dz, dr) in enumerate(prof):
            r = rad[k] + off + dr
            verts.append((c[0] + math.sin(a) * r, c[1] - math.cos(a) * r, zw + dz)); uvs.append((k / n, j / 5))
    m = len(prof)
    faces = [(k * m + j, ((k + 1) % n) * m + j, ((k + 1) % n) * m + (j + 1) % m, k * m + (j + 1) % m)
             for k in range(n) for j in range(m)]
    verts = np.array(verts)
    return dict(verts=verts, faces=faces, weights=band_weights(A, spec, verts), uv=uvs)


# ---------------------------------------------------------------------------------------------------- the hull's pieces
def hull_target(A, shape):
    """where the hull's eyes land on ours for the garments (target3d.eye_target): at our irises' height, _eye_z's frame,
    so the hull's pieces, the drawn heights and the QA agree. -> (eye_mid (3,), spacing)."""
    from . import target3d
    return target3d.eye_target(A, dict(shape, eye_anchor='iris'))


def hull_pieces(spec, A, source='shell'):
    """the visual hull's outfit pieces as world points on this character: the generated shape (the spec's hair.shape.glb,
    charkit.geom.hull's), aligned by its eyes as the build aligns its target (target3d.eye_target, target3d.align_by_eyes)
    -> {piece id: (n, 3)}, or None when the shape carries no pieces. The points are its labelled shell (hull.npz beside
    it: shell_points, one per surface voxel of the occupancy, on a regular grid), not the mesh's vertices: the mesh is
    decimated, and which vertices a decimation keeps (denser at curvature, fewer on flat stretches) moved the lofts'
    per-cell quantiles, hems and arcs (tool/hull-det's deterministic solve kept the skirt's width at every height to
    three decimals, yet its A-line check went -0.016 -> -0.133). source 'mesh' (or a hull without its labelled shell):
    the decimated mesh's vertices split by the per-vertex pieces the sidecar names, as before. Names come from the
    sidecar either way."""
    import json, os
    from . import target3d
    shape = ((spec.get('hair') or {}).get('shape') or {})
    glb = shape.get('glb')
    if not glb:
        return None
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = glb if os.path.isabs(glb) else os.path.join(root, glb)
    side = path + '.json'
    if not os.path.exists(side):
        return None
    J = json.load(open(side))
    if not J.get('pieces') or not J.get('eyes'):
        return None
    npz = os.path.join(os.path.dirname(path), 'hull.npz')
    Z = np.load(npz) if source == 'shell' and os.path.exists(npz) else None
    if Z is not None and 'shell' in Z.files and 'shell_label' in Z.files:
        V, lab = shell_points(Z)
    else:
        from .geom import io as gio
        V = np.asarray(gio.load(path).V, float)
        lab = np.load(os.path.join(os.path.dirname(path), J['pieces']))
        if len(lab) != len(V):
            raise ValueError('%s: %d piece labels for %d vertices' % (J['pieces'], len(lab), len(V)))
    eye_mid, spacing = hull_target(A, shape)
    W = target3d.align_by_eyes(V, (np.asarray(J['eyes'][0], float), np.asarray(J['eyes'][1], float)), eye_mid, spacing)
    return {pid: W[lab == int(k)] for k, pid in (J.get('piece_names') or {}).items() if (lab == int(k)).any()}


from .geom.hullshell import STRAY, shell_points, shell_patches   # noqa: F401 (the hull shell, moved there)


def drawn_extent(spec, A, pid, view='front'):
    """a piece's drawn extent in one view from the outfit graph (the produced outfit masks' graph: its bbox per view, L
    from the eye line) as world (x0, z0, x1, z1), or None. Read as JSON through the spec's manifest (importing the
    manifest module would pull the QA into the build's code)."""
    import json, os
    ref = spec.get('ref') if isinstance(spec.get('ref'), dict) else {}
    mp = ref.get('manifest')
    if not mp:
        return None
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ab = lambda p: p if os.path.isabs(p) else os.path.join(root, p)
    r = (json.load(open(ab(mp))).get('references') or {}).get('outfit_masks')
    if not r:
        return None
    gp = os.path.join(os.path.dirname(ab(r['path'])), 'outfit_graph.json')
    if not os.path.exists(gp):
        return None
    pc = next((p for p in json.load(open(gp))['pieces'] if p['id'] == pid), None)
    e = ((pc or {}).get('extent') or {}).get(view)
    if not e:
        return None
    L = A['head']['L']
    ez = _eye_z(A)
    x0, z0, x1, z1 = e['bbox']
    return (x0 * L, ez + z0 * L, x1 * L, ez + z1 * L)


def _hull_points(hull, s, fold=()):
    """a garment's points from the hull: its `piece` (default its name) with the pieces it carries (`fold`)."""
    if not hull:
        raise ValueError('%s: source hull, but the shape carries no pieces' % s['name'])
    ids = [s.get('piece', s['name'])] + list(s.get('fold', fold))
    P = [hull[i] for i in ids if i in hull and len(hull[i])]
    if not P:
        raise ValueError('%s: no hull points for %s' % (s['name'], ids))
    return np.concatenate(P)


def front_surface(P, cell, fill=3, smooth=0.0):
    """a piece's front (its least y, toward the viewer) over a grid of (x, z) cells of size `cell`, from its hull points,
    empty cells filled from their neighbours `fill` times and then from the nearest, then (smooth: sigma in cells)
    Gaussian-smoothed -> fn(x, z) -> y."""
    x0, z0 = P[:, 0].min() - cell, P[:, 2].min() - cell
    nx = int((P[:, 0].max() - x0) / cell) + 3
    nz = int((P[:, 2].max() - z0) / cell) + 3
    ix = np.clip(((P[:, 0] - x0) / cell).astype(int), 0, nx - 1)
    iz = np.clip(((P[:, 2] - z0) / cell).astype(int), 0, nz - 1)
    Y = np.full((nx, nz), np.inf)
    np.minimum.at(Y, (ix, iz), P[:, 1])
    Y[~np.isfinite(Y)] = np.nan
    for _ in range(fill):
        nb = np.stack([np.roll(Y, s_, a) for a in (0, 1) for s_ in (-1, 1)])
        with np.errstate(all='ignore'):
            fillv = np.nanmean(nb, 0)
        Y = np.where(np.isnan(Y), fillv, Y)
    ok = np.isfinite(Y)
    if not ok.all():
        gi, gj = np.nonzero(ok)
        bi, bj = np.nonzero(~ok)
        near = ((bi[:, None] - gi[None]) ** 2 + (bj[:, None] - gj[None]) ** 2).argmin(1)
        Y[bi, bj] = Y[gi[near], gj[near]]
    if smooth:
        from .geom import loft
        Y = loft.gauss1d(loft.gauss1d(Y, smooth, axis=0), smooth, axis=1)

    def fn(x, z):
        u = np.clip((np.asarray(x) - x0) / cell - 0.5, 0, nx - 1.001)
        v = np.clip((np.asarray(z) - z0) / cell - 0.5, 0, nz - 1.001)
        i, j = u.astype(int), v.astype(int)
        fu, fv = u - i, v - j
        return ((1 - fu) * (1 - fv) * Y[i, j] + fu * (1 - fv) * Y[i + 1, j] + (1 - fu) * fv * Y[i, j + 1] +
                fu * fv * Y[i + 1, j + 1])
    return fn


def _knn_mean(Q, P, k, chunk=2048):
    """for each point of Q, the mean of its k nearest points of P and the distance to the nearest (numpy, chunked: the
    build's Python has no scipy). Chunked to about 2.5M point pairs at once (the hull's shell gives a piece ~4x the
    decimated mesh's points)."""
    mean, near = np.empty((len(Q), 3)), np.empty(len(Q))
    chunk = max(64, min(chunk, int(2.5e6 // max(1, len(P)))))
    for a in range(0, len(Q), chunk):
        q = Q[a:a + chunk]
        d2 = ((q[:, None, :] - P[None, :, :]) ** 2).sum(-1)
        kk = min(k, len(P))
        idx = np.argpartition(d2, kk - 1, axis=1)[:, :kk]
        mean[a:a + chunk] = P[idx].mean(1)
        near[a:a + chunk] = np.sqrt(d2.min(1))
    return mean, near


def conform(V, faces, P, L, reach=0.12, k=8, smooth=3):
    """a thin piece laid onto its hull points: each vertex moved along its normal by how far the local hull surface (the
    mean of its k nearest points) is from it, fully within `reach` L of the points and fading out by twice that; the
    moves smoothed over the mesh `smooth` times so the points' spacing doesn't show. -> the moved vertices."""
    V = np.asarray(V, float)
    N = vertex_normals(V, faces)
    mean, near = _knn_mean(V, P, k)
    w = np.clip(2 - near / (reach * L), 0, 1)
    d = ((mean - V) * N).sum(1) * w
    nb = [set() for _ in range(len(V))]
    for f in faces:
        for a in f:
            nb[a].update(f)
    for _ in range(smooth):
        d = np.array([d[list(n)].mean() if n else d[i] for i, n in enumerate(nb)])
    return V + N * d[:, None]


def _vertical_axis(P, top):
    """a vertical axis down through a piece's points (its median x and y), from height `top`, front toward -y."""
    from .geom import loft
    c = np.median(P, 0)
    return loft.Axis((c[0], c[1], top), (0, 0, -1), (0, -1, 0))


def ring_axis(A, R, top, how='median'):
    """a vertical axis down through a ring of a piece's points (a skirt's waist), from height `top`, front toward -y:
    'median' their median x and y (_vertical_axis); 'ellipse' the centre of the axis-aligned ellipse fitted to them
    (algebraic least squares), which a partial ring doesn't pull toward where its points crowd (the median of the
    skirt's waist, whose front the bow and panel hide, sat 0.05 L to her left and 0.1 L forward of it: the skirt's right
    back read 0.1 L further out than its left); 'midline' the ellipse's y on the body's midline x (the hips', 0: the
    design is aligned on its eyes, and the band's and the waist's extents are centred on it; the legs' midline, which
    the boots mirror about, stands 0.011 L to her left of it, and a skirt centred there jutted out past the band on her
    left). A fit that isn't an ellipse falls back to the median."""
    from .geom import loft
    if how == 'median' or len(R) < 20:
        return _vertical_axis(R, top)
    x, y = R[:, 0], R[:, 1]
    a, b, c, d = np.linalg.lstsq(np.c_[x * x, y * y, x, y], np.ones_like(x), rcond=None)[0]
    if a <= 0 or b <= 0:
        return _vertical_axis(R, top)
    cx, cy = -c / (2 * a), -d / (2 * b)
    if how == 'midline':
        cx = float(bone_seg(A, 'hips')[0][0])
    return loft.Axis((cx, cy, top), (0, 0, -1), (0, -1, 0))


def hem_cut(ax, t, th, r, hem, others, L, gap=0.12, reach=0.08, share=0.3, min_arc=7.5):
    """which sectors of a piece's measured hem (per sector: where its points end, `hem` over the circle's n sectors) are
    where its label stops but its surface carries on: another piece's points (`others`) lie within `gap` L below that
    end and within `reach` L of the piece's radius there, at least `share` of the piece's own points in the `gap` above
    it. There the label's end isn't the hem: a flap lying over the skirt, a hand before it, or the skirt's own dark hem
    band labelled as the shorts (both dark; at the skirt's radius, well outside the shorts'). A stretch the test keeps
    between cut sectors narrower than `min_arc` degrees is cut too: a hem the design shows runs over a stretch, and one
    sector the test missed in a hand's notch (0.92 L against 1.18 at the front) pinned the whole filled back.
    -> bool per sector."""
    n = len(hem)
    j = np.clip(((th + np.pi) / (2 * np.pi) * n).astype(int), 0, n - 1)
    tq, thq, rq = ax.coords(others)
    jq = np.clip(((thq + np.pi) / (2 * np.pi) * n).astype(int), 0, n - 1)
    cut = np.zeros(n, bool)
    for k in np.nonzero(np.isfinite(hem))[0]:
        own = (j == k) & (t > hem[k] - gap * L) & (t <= hem[k])
        if own.sum() < 5:
            continue
        rh = np.median(r[own])
        more = (jq == k) & (tq > hem[k] - 0.02 * L) & (tq < hem[k] + gap * L) & (np.abs(rq - rh) < reach * L)
        cut[k] = more.sum() >= share * own.sum()
    keep = ~cut & np.isfinite(hem)
    if cut.any() and keep.any():
        short = int(np.ceil(min_arc / 360.0 * n))
        k0 = int(np.argmax(~keep))                        # start the walk on a sector that isn't kept (periodic runs)
        k = 0
        while k < n:
            i = (k0 + k) % n
            if keep[i]:
                e = k
                while e + 1 < n and keep[(k0 + e + 1) % n]:
                    e += 1
                if e - k + 1 < short:
                    cut[[(k0 + x) % n for x in range(k, e + 1)]] = True
                k = e + 1
            else:
                k += 1
    return cut


def mirror_sectors(x):
    """a per-sector array (sector k centred on -pi + (k + 0.5) 2pi / n; theta 0 the axis's front) averaged with its mirror
    about the axis's front-back plane (theta -> -theta: sector k <-> n - 1 - k), NaN where both are; along the last
    axis."""
    x = np.asarray(x, float)
    m = x[..., ::-1]
    both = np.isfinite(x) & np.isfinite(m)
    return np.where(both, (x + m) / 2, np.where(np.isfinite(x), x, m))


def belt_hull(A, spec, hull):
    """a band round the torso lofted through the hull's points of its piece (charkit.geom.loft): rows every `step` L
    between the points' `span` percentiles of height, or (`rows` [top, bottom], L from the eye line) the drawn band's
    edges, the section measured per angle and filled where no view shows it; its top and bottom rows pulled in by
    `round` of its thickness so the edge reads rounded; `offset` L out from the hull's surface. With `straight`, each
    column stands upright; with `fit_rows` [top, bottom] (L from the eye line) at the median of the field over those
    rows (the hull's rows where only the band shows: above them the top's flared hem overhangs the band, and the hull,
    which can't see under it, took its width for the band's), else at the radius a straight line through the column has
    a quarter of the way down. Weighted to the hips (`weights` 'body': the body's under it, band_weights). -> dict(verts,
    faces, weights, uv, axis, ts, th, R)."""
    from .geom import loft
    L = A['head']['L']
    P = _hull_points(hull, spec)
    top_z = P[:, 2].max()
    ax = _vertical_axis(P, top_z)
    t, th, r = ax.coords(P)
    # L from the eye line -> t along the axis (read only when the spec gives rows by height)
    tz = lambda z: top_z - (_eye_z(A) + z * L)
    if spec.get('rows'):
        lo, hi = tz(spec['rows'][0]), tz(spec['rows'][1])
    else:
        lo, hi = np.percentile(t, spec.get('span', (2, 98)))
    rows = max(3, int(round((hi - lo) / (spec.get('step', 0.02) * L))) + 1)
    fr = spec.get('fit_rows')
    flo, fhi = (tz(fr[0]), tz(fr[1])) if fr else (lo, hi)
    tf = np.linspace(min(lo, flo), max(hi, fhi), max(rows, int(round((max(hi, fhi) - min(lo, flo)) /
                                                                       (spec.get('step', 0.02) * L))) + 1))
    F = loft.field(t, th, r, tf, nth=spec.get('cols', 96), name=spec['name'],
                   prior=float(np.median(r)) if len(r) else None)
    ts = np.linspace(lo, hi, rows)
    R = np.stack([np.array([np.interp(x, F.ts, F.R[:, j]) for x in ts]) for j in range(F.R.shape[1])], 1)
    R = R + spec.get('offset', 0.0) * L
    if spec.get('straight'):
        if fr:
            k = (F.ts >= flo - 1e-9) & (F.ts <= fhi + 1e-9)
            R[:] = np.median(F.R[k], 0)[None, :] + spec.get('offset', 0.0) * L
        else:
            # each column upright at the radius a straight line through it has a quarter of the way down, smoothed
            # round: the hull's rows flared its top edge into a lip standing off the top, and narrowed it 0.07 L to its
            # lower edge, where the drawn band is a belt with upright sides (round 4's midriff)
            tt = ts - ts.mean()
            tq = tt[0] + spec.get('straight_at', 0.25) * (tt[-1] - tt[0])
            for j in range(R.shape[1]):
                R[:, j] = np.polyval(np.polyfit(tt, R[:, j], 1), tq)
        R = loft.gauss1d(R, spec.get('smooth_round', 1.5), axis=1, mode='wrap')
    pull = spec.get('round', 0.4) * spec.get('thick', 0.025) * L
    R[0] -= pull; R[-1] -= pull
    F2 = loft.Field(ts, F.th, R, None)
    V, quads, uv = loft.loft(ax, F2, R)
    return dict(verts=V, faces=quads, weights=band_weights(A, spec, V), uv=[tuple(x) for x in uv],
                hide=wrapped(A, V[:, 2].min(), V[:, 2].max()), axis=ax, ts=ts, th=F.th, R=R)


TORSO = ('hips', 'spine', 'chest', 'upperChest')


def wrapped(A, z0, z1, bones=TORSO):
    """the body's vertices a band wrapping the torso between heights z0 and z1 covers (their dominant bone in `bones`):
    hidden, since the band follows the design's section and the body, not the design's, can stand out of it."""
    dom, _ = dominant(A)
    V = A['verts']
    return np.nonzero((V[:, 2] >= z0) & (V[:, 2] <= z1) & np.isin(dom, bones))[0]


# -------------------------------------------------------------------------------------------------------------------- skirt
def body_section(A, z, band=0.012, n=72):
    """the body's horizontal section at height z (torso only): its radius by azimuth from the torso axis. -> (centre xy,
    radii (n,))."""
    V = A['verts']
    dom, _ = dominant(A)
    torso = np.isin(dom, ['hips', 'spine', 'chest', 'leftUpperLeg', 'rightUpperLeg'])
    m = torso & (np.abs(V[:, 2] - z) < band)
    P = V[m]
    c = np.array([0.0, P[:, 1].mean()])
    az = np.arctan2(P[:, 0] - c[0], -(P[:, 1] - c[1]))
    rr = np.hypot(P[:, 0] - c[0], P[:, 1] - c[1])
    bins = np.linspace(-math.pi, math.pi, n + 1)
    out = np.zeros(n)
    for i in range(n):
        s = (az >= bins[i]) & (az < bins[i + 1])
        out[i] = rr[s].max() if s.any() else np.nan
    good = ~np.isnan(out)
    out = np.interp(np.arange(n), np.nonzero(good)[0], out[good], period=n)
    return c, out


def skirt(A, spec):
    """a pleated skirt: the waist ring at a height between the hips and spine joints (the body's section plus `offset`), rows
    down to a hem whose length depends on azimuth (a longer back: `back`), flaring by `flare` (degrees), with `pleats`
    radial folds of depth `pleat` deepening toward the hem. UV: u round the waist (0 at the back, 0.5 at the front), v 0 at
    the waist .. 1 at the hem. Weights: the hips at the waist blending into each thigh by side and height.
    -> dict(verts, faces, weights, uv, panel (per face: 1 inside the front panel)."""
    L = A['head']['L']
    hj = bone_seg(A, 'hips')[0]; sj = bone_seg(A, 'spine')[1]
    zw = hj[2] + (sj[2] - hj[2]) * spec.get('waist', 0.55)
    n = spec.get('cols', 144); rows = spec.get('rows', 16)
    c, rad = body_section(A, zw, n=n)
    off = spec.get('offset', 0.015) * L
    length = spec.get('length', 0.9) * L
    back = spec.get('back', 0.0) * L
    fl = math.tan(math.radians(spec.get('flare', 38.0)))
    pleats = spec.get('pleats', 24); depth = spec.get('pleat', 0.05) * L
    panel = spec.get('panel', 0.0)                       # the front panel's half-width, radians of azimuth
    verts, uvs = [], []
    for j in range(rows + 1):
        v = j / rows
        for k in range(n):
            a = -math.pi + 2 * math.pi * k / n
            back_w = (1 - math.cos(a)) / 2                # 0 at the front .. 1 at the back
            ln = length + back * back_w ** 1.5
            r0 = rad[k] + off
            # pleats: a zigzag in radius, sharp at the folds, deepening down the skirt
            ph = (a + math.pi) / (2 * math.pi) * pleats
            zig = abs((ph % 1.0) - 0.5) * 2 - 0.5
            r = r0 + ln * fl * v ** 0.85 + depth * zig * v ** 0.7
            z = zw - ln * v * (1 - 0.12 * fl * v)
            verts.append((c[0] + math.sin(a) * r, c[1] - math.cos(a) * r, z))
            uvs.append((k / n, v))
    faces, pan = [], []
    for j in range(rows):
        for k in range(n):
            k2 = (k + 1) % n
            faces.append((j * n + k, j * n + k2, (j + 1) * n + k2, (j + 1) * n + k))
            a = -math.pi + 2 * math.pi * (k + 0.5) / n
            pan.append(1 if abs(a) < panel else 0)
    verts = np.array(verts)
    # weights: the hips at the waist; each side's thigh takes over going down (half-and-half at the front and back centre)
    vv = np.array([u[1] for u in uvs])
    sx = np.clip(verts[:, 0] / (0.08 * L), -1, 1)
    leg = 0.65 * vv ** 1.4
    Wt = {'hips': 1 - leg, 'leftUpperLeg': leg * (1 + sx) / 2, 'rightUpperLeg': leg * (1 - sx) / 2}
    return dict(verts=verts, faces=faces, weights=Wt, uv=uvs, panel=pan, z_waist=zw)


def panel_warp(th, half, VV, ps):
    """a skirt's vertex angles with its front panel tapered (skirt_hull's `panel_shape`): th the columns' angles (n,),
    half the panel's half-angle (its faces: |th| < half), VV each vertex's v (rows, n); ps {top, power, scale}: the
    panel's edge columns at scale x (top + (1 - top) v ** power) of their own angle from its middle, the columns outside
    spread evenly over the rest of the circle -> angles (rows, n)."""
    th = np.asarray(th, float)
    n = len(th)
    ks = np.nonzero(np.abs(th) < half)[0]                     # the panel's faces' first columns
    bl, br = th[ks.min()], th[(ks.max() + 1) % n]            # its edge columns
    c, h0 = (bl + br) / 2, (br - bl) / 2
    f = float(ps.get('scale', 1.0)) * (float(ps.get('top', 0.1)) + (1 - float(ps.get('top', 0.1)))
                                       * np.clip(VV, 0, 1) ** float(ps.get('power', 1.0)))
    f = np.clip(f, 0.01, (np.pi - 1e-3) / h0)
    d = np.mod(th[None, :] - c + np.pi, 2 * np.pi) - np.pi                       # from the panel's middle, (-pi, pi]
    inside = np.abs(d) <= h0 + 1e-12
    hn = h0 * f
    out = np.where(inside, d * f, np.sign(d) * (hn + (np.abs(d) - h0) * (np.pi - hn) / (np.pi - h0)))
    return c + out


def _field_at(F, vs, VV, TH):
    """a loft field's radius at each (v, angle) (bilinear: rows vs, columns F.th, periodic round)."""
    th = np.asarray(F.th, float)
    n = len(th)
    step = 2 * np.pi / n
    x = np.mod(np.asarray(TH, float) - th[0], 2 * np.pi) / step
    k0 = np.floor(x).astype(int) % n
    k1 = (k0 + 1) % n
    fx = x - np.floor(x)
    y = np.interp(np.asarray(VV, float), vs, np.arange(len(vs)))
    i0 = np.clip(np.floor(y).astype(int), 0, len(vs) - 1)
    i1 = np.clip(i0 + 1, 0, len(vs) - 1)
    fy = y - i0
    Rf = np.asarray(F.R, float)
    a = Rf[i0, k0] * (1 - fx) + Rf[i0, k1] * fx
    b = Rf[i1, k0] * (1 - fx) + Rf[i1, k1] * fx
    return a * (1 - fy) + b * fy


def skirt_hull(A, spec, hull):
    """a pleated skirt lofted through the hull's points of the skirt and its front panel (fold: skirt_panel): the waist at
    the points' top, a hem per angle where they end (the back longer, as drawn), and between them the measured section
    row by row (geom.loft, in v = 0 at the waist .. 1 at the hem, per column); `pleats` knife folds of depth `pleat` L
    deepening toward the hem on top (the hull's section can't show them: a visual hull fills folds); the front panel's
    half-width measured from the panel's points (else the spec's `panel`); with `aline`, each column never narrowing
    toward the hem. `axis`: ring_axis's way to its waist ring's centre ('median', the default; 'ellipse'; 'midline').
    `hem_cut` (True or hem_cut()'s knobs): the hem's sectors where the skirt's label stops but its surface carries on
    (a flap over it, a hand, its dark hem band labelled as the shorts) are filled round the circle from the rest, in
    place of the `occluders` / `occluded_span` test. `symmetric`: the hem, the waist line and the radius field averaged
    with their mirror images about the axis's front-back plane (the design's skirt is its own mirror image). UV and
    weights as skirt()'s.
    -> dict(verts, faces, weights, uv, panel, z_waist)."""
    from .geom import loft
    L = A['head']['L']
    P = _hull_points(hull, spec, fold=('skirt_panel',))
    top = np.percentile(P[:, 2], 99.5)
    ax = ring_axis(A, P[P[:, 2] > top - 0.1 * L], top, spec.get('axis', 'median'))
    t, th, r = ax.coords(P)
    n = spec.get('cols', 144); rows = spec.get('rows', 16)
    sym = bool(spec.get('symmetric'))              # the design's skirt is its own mirror image about the axis's plane
    # the hem: per sector, where the points end (a high percentile of t), filled round and smoothed
    j = np.clip(((th + np.pi) / (2 * np.pi) * n).astype(int), 0, n - 1)
    hem = np.full(n, np.nan)
    for k in range(n):
        tk = t[j == k]
        if len(tk) >= 5:
            hem[k] = np.percentile(tk, spec.get('hem_q', 97))
    # where the skirt's label stops but its surface carries on (a flap over it, a hand before it, its dark hem band
    # labelled as the shorts), its points' end isn't the hem: those sectors are filled round the circle from the rest
    cut = spec.get('hem_cut')                     # True, or hem_cut()'s gap / reach / share
    cut = None if cut is None or cut is False else cut
    if cut is not None:
        own = {spec.get('piece', spec['name'])} | set(spec.get('fold', ('skirt_panel',)))
        others = [hull[k] for k in hull if k not in own and len(hull[k])]
        if others:
            hem[hem_cut(ax, t, th, r, hem, np.concatenate(others), L, **(cut if isinstance(cut, dict) else {}))] = np.nan
    # where a piece hangs over the skirt (the overskirt panels), the skirt's points stop at its edge, not at the hem: those
    # sectors' hems are hidden, and filled round the circle from the ones the design shows
    for occ in (() if cut is not None else spec.get('occluders', ('overskirt_panel_L', 'overskirt_panel_R'))):
        Po = hull.get(occ) if hull else None
        if Po is None or not len(Po):
            continue
        to, tho, _ = ax.coords(Po)
        jo = np.clip(((tho + np.pi) / (2 * np.pi) * n).astype(int), 0, n - 1)
        lo_, hi_ = (math.radians(a) for a in spec.get('occluded_span', (70, 110)))   # the sides (from the front)
        for k in np.unique(jo):
            tk = to[jo == k]
            ak = abs(-math.pi + (k + 0.5) * 2 * math.pi / n)
            if len(tk) >= 5 and np.isfinite(hem[k]) and np.percentile(tk, 90) > hem[k] and lo_ <= ak <= hi_:
                hem[k] = np.nan
    if sym:
        hem = mirror_sectors(hem)
    hem = loft._fill_periodic(hem)
    if hem is None:
        raise ValueError('%s: too few hull points to find its hem' % spec['name'])
    hem = loft.gauss1d(hem, spec.get('hem_smooth', 2.0), mode='wrap')
    th_c = -np.pi + (np.arange(n) + 0.5) * 2 * np.pi / n
    hem_at = lambda a: np.interp(a, th_c, hem, period=2 * np.pi)
    # the waist line per angle: where the skirt's points start, or tucked `tuck` L under a hull-sourced band's lower edge
    top_z = hull_edge(P, ax, q=spec.get('waist_q', 3.0), low=False)
    band = spec.get('under')
    if band and hull and band in hull and len(hull[band]):
        # tucked under the band all round: its own points start lower in places (the front panel's top), which left
        # skin showing between the band and the skirt
        low = hull_edge(hull[band], ax, q=5.0)
        top_z = lambda a: low(a) + spec.get('tuck', 0.01) * L
    if sym:
        top_z0 = top_z
        top_z = lambda a: (top_z0(a) + top_z0(-np.asarray(a))) / 2
    t0_at = lambda a: top - top_z(a)
    v = np.clip((t - t0_at(th)) / np.maximum(1e-9, hem_at(th) - t0_at(th)), -0.2, 1.2)
    vs = np.linspace(0, 1, rows + 1)
    F = loft.field(v, th, r, vs, nth=n, q=spec.get('q', 0.5), smooth=(1.0, 1.0), name=spec['name'],
                   prior=float(np.median(r)) if len(r) else None)
    if sym:
        F.R = mirror_sectors(F.R)
    if spec.get('aline'):
        # an A-line flares to its hem: each column's radius never narrows going down (a visual hull rounds the
        # hem's corners in, where the views' silhouettes cut it, and the skirt read as a bubble)
        F.R = np.maximum.accumulate(F.R, axis=0)
        al = spec['aline']
        if isinstance(al, dict):
            # the A-line as a template (templates first): each column a line from its top radius to its hem radius,
            # shaped by `shape` (v ** shape: 1 straight, under 1 flaring early, over 1 late), the hull giving only the
            # two ends. The hull's rows just under the band flared the skirt out at once into a bell (the sheet-only
            # masks start the skirt's label under the band): body_front_skirt_aline -0.161 (tool/garments3)
            line = F.R[:1] + (F.R[-1:] - F.R[:1]) * (vs[:, None] ** float(al.get('shape', 1.0)))
            # `sides` k: the template weighted |sin th| ** k round the body (the front view's outline is the sides'
            # columns; the front and back columns keep the hull's shape, which the profile's outline and the flaps
            # lying on the skirt's back fit); None: every column
            k_ = al.get('sides')
            w_ = np.ones_like(F.th) if k_ is None else np.abs(np.sin(F.th)) ** float(k_)
            F.R = F.R + (line - F.R) * w_[None, :]
    off = spec.get('offset', 0.0) * L
    pleats = spec.get('pleats', 24); depth = spec.get('pleat', 0.05) * L
    TH = F.th[None, :]; VV = vs[:, None]
    ph = (TH + np.pi) / (2 * np.pi) * pleats
    zig = np.abs((ph % 1.0) - 0.5) * 2 - 0.5
    R = F.R + off + depth * zig * VV ** 0.7
    T = t0_at(TH) + VV * (hem_at(TH) - t0_at(TH))
    # the front panel: the skirt_panel's points' angular spread, else the knob
    pan_pts = hull.get('skirt_panel') if hull else None
    if pan_pts is not None and len(pan_pts) > 20:
        half = dense_arc(ax.coords(pan_pts)[1], spec.get('panel_mass', 0.8))[1]    # its densest arc (stray labels
                                                                                     # widened a percentile to 58 deg)
    else:
        half = spec.get('panel', 0.0)
    band = None
    VVg = np.broadcast_to(VV, R.shape)
    if spec.get('band'):
        # the dark hem band as geometry: rows placed per column on its top edge's levels, its faces a third material
        VVg, hb = band_rows(spec['band'], F.th, half, hem_at(F.th) - t0_at(F.th), vs, L)
        R = np.array([np.interp(VVg[:, k], vs, F.R[:, k]) for k in range(n)]).T + off + depth * zig * VVg ** 0.7
        T = t0_at(TH) + VVg * (hem_at(TH) - t0_at(TH))
        lenc = hem_at(F.th) - t0_at(F.th)
        vb = 1 - hb / np.maximum(1e-9, lenc)                                     # per face column: the band's top (v)
        band = [int(hb[k] > 0 and VVg[i, k] >= vb[k] - 1e-9 and abs(F.th[k]) >= half)
                for i in range(VVg.shape[0] - 1) for k in range(n)]
    THv = np.broadcast_to(TH, R.shape)
    warped = bool(spec.get('panel_shape')) and half > 0
    if warped:
        # the front panel as a template (tool/garments4, Michael's "the skirt's cream section"): the drawn panel is an
        # inverted box pleat, a triangle from the waist widening to the hem, where a constant angle made a band as wide
        # at the waist as at the hem (skirt_panel_*_shape). Each vertex row's columns are re-spaced round the axis so the
        # panel's edge columns sit at `scale` x (top + (1 - top) v ** power) of their own angle, the rest spread over the
        # remaining circle: the panel's faces keep their columns (a clean edge, its UV and creases ride with it), the
        # surface is the same field read at the new angles; the knife pleats fan with the columns (a recessed or
        # protruding box pleat was tried, sweeps k2/k3: it hid the panel's cream in profile and fought its pleats)
        THv = panel_warp(F.th, half, VVg, spec['panel_shape'])
        R = _field_at(F, vs, VVg, THv) + off + depth * zig * VVg ** 0.7
        T = t0_at(THv) + VVg * (hem_at(THv) - t0_at(THv))
    nrow = VVg.shape[0] - 1
    tuck = None
    under = spec.get('under')
    if spec.get('tuck_fit') not in (None, False) and under and hull and under in hull:
        # the skirt comes out from under the band: at the band's lower edge no further out than `inset` of the band's
        # thickness inside its outer surface, easing back to its own shape over `blend` L below; above that edge inside
        # the band's inner surface (Michael's review of round 6: at the back the skirt came out 0.04-0.05 L past the
        # band, its top rim and pleats standing outside the band: "a strangely warping tuck-in")
        tuck = tuck_under(A, spec, hull, ax, F.th, T, L)
        if tuck:
            R = tuck_pull(R, T, tuck, A=THv if warped else None)
    clear_info = None
    if spec.get('clear_hands'):
        R, clear_info = clear_arms(A, spec, hull, ax, T, np.broadcast_to(THv, T.shape), R)
    verts = ax.point(T, np.broadcast_to(THv, T.shape), R).reshape(-1, 3)
    faces = [(i * n + k, i * n + (k + 1) % n, (i + 1) * n + (k + 1) % n, (i + 1) * n + k)
             for i in range(nrow) for k in range(n)]
    uvs = [((k + 0.5) / n, float(VVg[i, k])) for i in range(nrow + 1) for k in range(n)]
    pan = [1 if abs(F.th[k]) < half else 0 for i in range(nrow) for k in range(n)]
    vv = VVg.ravel()
    sx = np.clip(verts[:, 0] / (0.08 * L), -1, 1)
    leg = 0.65 * vv ** 1.4
    Wt = {'hips': 1 - leg, 'leftUpperLeg': leg * (1 + sx) / 2, 'rightUpperLeg': leg * (1 - sx) / 2}
    out = dict(verts=verts, faces=faces, weights=Wt, uv=uvs, panel=pan, z_waist=float(top - np.median(t0_at(F.th))),
               panel_half=half, axis=ax, grid=(nrow + 1, n), clear=clear_info)
    kp = np.nonzero(np.abs(F.th) < half)[0]
    if len(kp):                                  # the panel's edge columns' u (ink_strokes' space 'panel')
        out['panel_u'] = ((kp.min() + 0.5) / n, (kp.max() + 1.5) / n)
    if band is not None:
        out['band'] = band
    if tuck:
        out['tuck'] = tuck
    return out


def tuck_under(A, spec, hull, ax, th, T, L):
    """the band a skirt tucks under (`under`), read in the skirt's frame per column th: its lower edge's t and outer
    radius (its three lowest vertices within 5 deg), with the pull's knobs (`tuck_fit`: inset (of the band's thickness,
    0.5), clear (L, 0.005), blend (L, 0.25)). -> dict or None (the band isn't a hull belt)."""
    whole = spec.get('_spec') or {}
    bs = next((g for g in whole.get('garments', []) if g['name'] == spec.get('under')), None)
    if not bs or bs.get('kind') != 'belt' or bs.get('source') != 'hull':
        return None
    tf = spec['tuck_fit'] if isinstance(spec['tuck_fit'], dict) else {}
    Gb = belt_hull(A, bs, hull)
    tb, thb, rb = ax.coords(np.asarray(Gb['verts']))
    n = len(th)
    t_lo, r_lo = np.zeros(n), np.zeros(n)
    for k in range(n):
        m = np.nonzero(np.abs(np.angle(np.exp(1j * (thb - th[k])))) < np.radians(5))[0]
        i = m[np.argsort(tb[m])[-3:]]
        t_lo[k], r_lo[k] = tb[i].mean(), rb[i].mean()
    thick = bs.get('thick', 0.025) * L
    return dict(th=np.asarray(th, float), t_lo=t_lo, r_lo=r_lo, thick=thick, inset=tf.get('inset', 0.5) * thick,
                cap=r_lo - thick - tf.get('clear', 0.005) * L, blend=tf.get('blend', 0.25) * L)


def tuck_pull(R, T, tk, dr=0.0, A=None):
    """a radius grid (rows down) pulled in under a band (tuck_under): by its excess at the band's lower edge over the
    edge's radius less the inset (plus `dr`: a flap lying over the skirt), easing to nothing over blend below; capped
    inside the band's inner surface (plus dr) above the edge. Its columns are tk's th, or with A (azimuths per vertex,
    the grid's shape) the band's values are read at each vertex's own azimuth (a flap's columns turn going down)."""
    if A is None:
        t_lo, r_lo, cap = (tk[k][None, :] * np.ones_like(R) for k in ('t_lo', 'r_lo', 'cap'))
    else:
        o = np.argsort(tk['th'])
        at_ = lambda k: np.interp(np.mod(A + np.pi, 2 * np.pi) - np.pi, tk['th'][o], tk[k][o], period=2 * np.pi)
        t_lo, r_lo, cap = at_('t_lo'), at_('r_lo'), at_('cap')
    n = R.shape[1]
    at = np.array([np.interp(t_lo[0, k], T[:, k], R[:, k]) for k in range(n)])
    excess = np.maximum(0.0, at - (r_lo[0] - tk['inset'] + dr))
    d = T - t_lo
    x = np.clip(d / max(1e-9, tk['blend']), 0, 1)
    w = 1 - x * x * (3 - 2 * x)
    R = R - excess[None, :] * w
    return np.where(d < 0, np.minimum(R, cap + dr), R)


def band_rows(bs, th, half, lenc, vs, L):
    """a skirt's dark hem band as rows: its height per column (`height` L, or from `stair`: knots [degrees out from the
    front panel's edge, height L], a step function: the band's top climbing in steps toward the panel, as drawn; none on
    the panel), and the rows per column: the loft's rows above the tallest band, then one row on each of the band's
    levels (v = 1 - height / the column's length) and one between each two, then the hem. -> (v per row and column,
    height per column (L))."""
    n = len(th)
    thc = th + np.pi / n                                                         # each face column's centre
    d = np.degrees(np.abs(np.angle(np.exp(1j * thc)))) - np.degrees(half)
    hb = np.full(n, float(bs.get('height', 0.14)))
    if bs.get('stair'):
        K = sorted(bs['stair'])
        for k, (d0, h) in enumerate(K):
            d1 = K[k + 1][0] if k + 1 < len(K) else np.inf
            hb[(d >= d0) & (d < d1)] = h
    hb[d < 0] = 0.0                                                              # (the panel: cream, no band)
    hb *= L
    levels = np.unique(hb[hb > 0])[::-1]                                         # tallest first (v ascending)
    lv = 1 - levels[:, None] / np.maximum(1e-9, lenc)[None, :]                   # (levels, n)
    vtop = float(lv.min()) - 0.03
    top = vs[vs < vtop]
    rows_ = [np.tile(v_, n) for v_ in top]
    for i in range(len(levels)):
        if i:
            rows_.append(0.5 * (lv[i - 1] + lv[i]))
        elif len(top):
            rows_.append(0.5 * (top[-1] + lv[0]))
        rows_.append(lv[i])
    rows_ += [0.5 * (lv[-1] + 1), np.ones(n)]
    return np.array(rows_), hb


ARM_BONES = ('LowerArm', 'Hand', 'Thumb', 'Index', 'Middle', 'Ring', 'Little')


def arm_points(A, spec=None, hull=None, w_min=0.3):
    """the hands', fingers' and forearms' skin at bind (their bones' weight over w_min), and (clear_bands, default) the
    wrist bands built on the forearms (band_hull, from the whole spec in `_spec`): what a skirt hanging beside the arms
    must clear."""
    W = A['weights']
    w = sum((np.asarray(W[b]) for b in W if any(k in b for k in ARM_BONES)), np.zeros(len(A['verts'])))
    P = [A['verts'][w > w_min]]
    whole = (spec or {}).get('_spec') or {}
    for g in (whole.get('garments', []) if (spec or {}).get('clear_bands', True) else []):
        if g.get('kind') == 'band' and 'LowerArm' in g.get('bone', '') and g.get('source') == 'hull' and hull:
            P.append(np.asarray(band_hull(A, g, hull)['verts']))
        elif g.get('kind') == 'band' and 'LowerArm' in g.get('bone', '') and g.get('source') == 'template':
            P.append(np.asarray(cuff(A, g)['verts']))
    return np.concatenate(P)


def clear_arms(A, spec, hull, ax, T, TH, R, chunk=256):
    """a skirt's radius field capped clear of the arms hanging beside it (the hands rest in its flare at bind, and the
    rig's skin went through the cloth): at each cell no more than the arm point's radius less `clear_hands` L, the cap
    easing back out by `clear_slope` of the distance (a cone round each point, so the dent is smooth), over the arm points
    within the skirt's height. -> (R, dict(points, cells capped, max dent (L)))."""
    L = A['head']['L']
    P = arm_points(A, spec, hull)
    tp, thp, rp = ax.coords(P)
    keep = (tp > T.min() - 0.1 * L) & (tp < T.max() + 0.1 * L)
    tp, thp, rp = tp[keep], thp[keep], rp[keep]
    c = spec['clear_hands'] * L
    k = spec.get('clear_slope', 0.6)
    cap = np.full(R.shape, np.inf)
    Tf, THf = T.reshape(-1), TH.reshape(-1)
    for a in range(0, len(tp), chunk):
        dt = Tf[:, None] - tp[None, a:a + chunk]
        dth = np.angle(np.exp(1j * (THf[:, None] - thp[None, a:a + chunk]))) * rp[None, a:a + chunk]
        cc = rp[None, a:a + chunk] - c + k * np.hypot(dt, dth)
        cap = np.minimum(cap, cc.min(1).reshape(R.shape))
    R2 = np.minimum(R, cap)
    dent = (R - R2) / L
    return R2, dict(points=int(len(tp)), cells=int((dent > 1e-6).sum()), max_dent=round(float(dent.max()), 4))


def panel(A, spec):
    """a panel hanging from the waist ring (an overskirt panel, a coat's tail): centred on azimuth `az` (degrees; 0 the
    front, + toward her left, 180 the back), `width` L round the ring, `length` L down, spreading by `flare` degrees
    away from the body as it falls and widening by `spread` (a share of its width) at the hem; lifted `offset` L off
    the body's section at the waist (under a skirt: less than the skirt's). UV: u across 0 .. 1, v 0 at the waist .. 1
    at the hem. Weights: the hips at the waist, its side's thigh taking over down its length (as the skirt's).
    -> dict(verts, faces, weights, uv, z_waist)."""
    L = A['head']['L']
    hj = bone_seg(A, 'hips')[0]; sj = bone_seg(A, 'spine')[1]
    zw = hj[2] + (sj[2] - hj[2]) * spec.get('waist', 0.5)
    n_ring = 144
    c, rad = body_section(A, zw, n=n_ring)
    off = spec.get('offset', 0.02) * L
    length = spec.get('length', 1.0) * L
    fl = math.tan(math.radians(spec.get('flare', 30.0)))
    a0 = math.radians(spec.get('az', 180.0))
    cols, rows = spec.get('cols', 24), spec.get('rows', 16)
    spread = spec.get('spread', 0.2)
    r_mid = float(np.interp((a0 + math.pi) % (2 * math.pi), np.linspace(0, 2 * math.pi, n_ring, endpoint=False), rad,
                            period=2 * math.pi)) + off
    half = spec.get('width', 0.4) * L / 2 / max(1e-6, r_mid)          # radians either side at the waist
    verts, uvs = [], []
    for j in range(rows + 1):
        v = j / rows
        for i in range(cols + 1):
            u = i / cols
            a = a0 + (2 * u - 1) * half * (1 + spread * v)
            k = ((a + math.pi) % (2 * math.pi)) / (2 * math.pi) * n_ring
            r0 = float(np.interp(k, np.arange(n_ring), rad, period=n_ring)) + off
            r = r0 + length * fl * v ** 0.85
            z = zw - length * v * (1 - 0.12 * fl * v)
            verts.append((c[0] + math.sin(a) * r, c[1] - math.cos(a) * r, z))
            uvs.append((u, v))
    faces = [(j * (cols + 1) + i, j * (cols + 1) + i + 1, (j + 1) * (cols + 1) + i + 1, (j + 1) * (cols + 1) + i)
             for j in range(rows) for i in range(cols)]
    verts = np.array(verts)
    vv = np.array([u[1] for u in uvs])
    sx = np.clip(verts[:, 0] / (0.08 * L), -1, 1)
    leg = 0.65 * vv ** 1.4
    Wt = {'hips': 1 - leg, 'leftUpperLeg': leg * (1 + sx) / 2, 'rightUpperLeg': leg * (1 - sx) / 2}
    return dict(verts=verts, faces=faces, weights=Wt, uv=uvs, z_waist=zw)


def flap(A, spec, hull):
    """a flap over the skirt, its own piece with its own spring chain (an overskirt panel): laid on the skirt's outside
    from its waist (tucked under the band, as the skirt is) to its hem, `clear` L plus its thickness off the pleats'
    crests, then carried on below the hem as a longer section of the skirt's cone: each column continues the skirt's
    own slope there, tilted `out` further out and `sweep` toward the centre back, for `length` L at its front edge and
    `train` more at its lowest: its back edge (a stepped diagonal in front, a train sweeping back in profile), or with
    `tip` < 1 a V pointing down `tip` of the way from its front edge to its back edge (the design's flaps: their hems
    rise to the side and to the centre back from a point at the back corner); `stair` treads a side make that hem a
    staircase in silhouette (0: straight). Centred on azimuth `az` (degrees, 0 the front, + her left) at the skirt's
    hem and `az_waist` (default az) at the waist, `width` L wide at the skirt's hem and `narrow` of that angle at the
    waist (above 1: wider at the waist).
    Needs the hull skirt it lies on (`over`, default skirt, from the whole spec in `_spec`). Its chain as data: `bones`
    bones joint to joint along its middle column, the first from the waist to the skirt's hem (parent hips), the rest
    along the tail, named NAME_0, NAME_1, ... (charkit.flapchains writes the path into the outfit graph; the rig stage
    makes the bones and the weights, tool/rig). Until it does the flap rides the hips. UV: u across 0 .. 1; v 0 at the
    waist .. 1 at the tail's end, the last `trim` L of each column on the stepped hem texture's band (`band` of v).
    -> dict(verts, faces, weights, uv, z_waist, chain=dict(parent, bones, joints, arc (per vertex: its row's arc length
    along the middle, m)), reach (lowest point, m))."""
    L = A['head']['L']
    whole = spec.get('_spec') or {}
    if spec.get('mirror'):
        return flap_mirror(A, spec, hull)
    if spec.get('shape') == 'template':
        return flap_template(A, spec, hull)
    sk = next((g for g in whole.get('garments', []) if g['name'] == spec.get('over', 'skirt')), None)
    if not sk or sk.get('source') != 'hull':
        raise ValueError('%s: a flap lies on a hull skirt (%s)' % (spec['name'], spec.get('over', 'skirt')))
    Gs = skirt_hull(A, dict(sk, band=None, _spec=whole), hull)
    ax = Gs['axis']
    nr, n = Gs['grid']
    t, th, r = ax.coords(np.asarray(Gs['verts']))
    T, R = t.reshape(nr, n), r.reshape(nr, n)
    th_c = th.reshape(nr, n)[0]
    order = np.argsort(th_c)
    th_s = th_c[order]
    pw = max(1, int(round(n / max(1, sk.get('pleats', 24)))))
    Rc = np.maximum.reduce([np.roll(R, k, 1) for k in range(-pw, pw + 1)])       # the pleats' crests
    lift = (spec.get('clear', 0.03) + spec.get('thick', 0.01)) * L
    a0 = math.radians(spec.get('az', 120.0))
    a0w = math.radians(spec.get('az_waist', spec.get('az', 120.0)))          # its centre at the waist
    cols = spec.get('cols', 16)
    at = lambda Z, i, a: np.interp(np.mod(a + math.pi, 2 * math.pi) - math.pi, th_s, Z[i][order], period=2 * math.pi)
    half1 = spec.get('width', 0.4) * L / 2 / max(1e-6, float(at(Rc, nr - 1, a0)))
    half0 = half1 * spec.get('narrow', 0.6)
    u = np.linspace(-1, 1, cols + 1)
    over = []
    for i in range(nr):
        v = i / (nr - 1)
        a = a0w + (a0 - a0w) * v + u * (half0 + (half1 - half0) * v)
        over.append(ax.point(at(T, i, a), a, at(Rc, i, a) + lift))
    over = np.array(over)                                                        # (nr, cols + 1, 3)
    # the tail: each column carries on along the skirt's slope at its hem, longer toward the back edge
    hem, prev = over[-1], over[-2]
    slope = hem - prev
    slope /= np.maximum(1e-9, np.linalg.norm(slope, axis=1))[:, None]
    ah = a0 + u * half1
    sgn = 1.0 if a0 >= 0 else -1.0
    e_out = np.stack([np.sin(ah), -np.cos(ah), np.zeros_like(ah)], 1)
    e_back = sgn * np.stack([np.cos(ah), np.sin(ah), np.zeros_like(ah)], 1)
    dirs = slope + spec.get('out', 0.3) * e_out + spec.get('sweep', 0.3) * e_back
    dirs /= np.linalg.norm(dirs, axis=1)[:, None]
    back = (u * sgn + 1) / 2                                                  # 0 at the front edge .. 1 at the back
    # the hem's profile across the flap, 0 at its edges' rise .. 1 at its lowest: a diagonal down to the back edge
    # (tip 1), or a V whose point is `tip` of the way from the front edge to the back; `stair` treads a side make the
    # hem's silhouette a staircase (the design's stepped hem), each tread level across its columns
    tip = float(spec.get('tip', 1.0))
    prof = back if tip >= 1 else np.where(back <= tip, back / max(tip, 1e-9), (1 - back) / max(1 - tip, 1e-9))
    stair = int(spec.get('stair', 0))
    if stair:
        prof = np.minimum(1.0, (np.floor(prof * stair + 1e-9) + 1) / stair)
    lens = spec.get('length', 0.6) * L * (1 + spec.get('train', 1.0) * prof)
    m = spec.get('tail_rows', 12)
    rows_t = [hem + (s_ * lens)[:, None] * dirs for s_ in np.linspace(0, 1, m + 1)[1:]]
    S = float(lens[cols // 2])
    G = np.concatenate([over, np.array(rows_t)], 0)                              # (nr + m, cols + 1, 3)
    NR = len(G)
    verts = G.reshape(-1, 3)
    faces = [(j * (cols + 1) + i, j * (cols + 1) + i + 1, (j + 1) * (cols + 1) + i + 1, (j + 1) * (cols + 1) + i)
             for j in range(NR - 1) for i in range(cols)]
    # arc length along the centre, per row
    cen = G[:, cols // 2]
    arc = np.r_[0, np.cumsum(np.linalg.norm(np.diff(cen, axis=0), axis=1))]
    tot = float(arc[-1])
    trim = min(spec.get('trim', 0.15) * L, 0.9 * S)          # (on the middle column; the others' in proportion)
    band = spec.get('band', 0.16)
    vv = np.where(arc <= tot - trim, arc / max(1e-9, tot - trim) * (1 - band),
                  1 - band + band * (arc - (tot - trim)) / max(1e-9, trim))
    uvs = [((u_ + 1) / 2, float(vv[j])) for j in range(NR) for u_ in u]
    # the chain: the waist, the skirt's hem, then the tail at equal arc lengths
    nb = max(2, spec.get('bones', 5))
    s_j = np.r_[0.0, arc[nr - 1], arc[nr - 1] + np.linspace(0, S, nb)[1:]]
    joints = np.stack([np.interp(s_j, arc, cen[:, k]) for k in range(3)], 1)
    names = ['%s_%d' % (spec['name'], i) for i in range(nb)]
    return dict(verts=verts, faces=faces, weights={'hips': np.ones(len(verts))}, uv=uvs,
                z_waist=float(over[0, cols // 2, 2]), reach=float(verts[:, 2].min()),
                chain=dict(parent='hips', bones=names, joints=joints, arc=np.repeat(arc, cols + 1)))


def flap_mirror(A, spec, hull):
    """a flap as the mirror image of another (`mirror`: its name) about the skirt's plane (a `symmetric` skirt's axis;
    else the legs' midline, boot_frame's), lifted clear of the skirt where the skirt's side stands further out than its
    mirror (the rows over the skirt pushed out to its
    pleats' crests plus the flap's clearance, the tail carried with its hem): the flaps built each round the skirt's
    hull axis, which sits 0.14 L off the body's midline, and the right one hung 0.2 L further back than the left.
    Its chain is the mirrored chain, its bones named after it. -> flap()'s dict."""
    L = A['head']['L']
    whole = spec.get('_spec') or {}
    src = next(g for g in whole.get('garments', []) if g['name'] == spec['mirror'])
    G = flap(A, dict(src, _spec=whole), hull)
    sk = next(g for g in whole.get('garments', []) if g['name'] == src.get('over', 'skirt'))
    Gs = skirt_hull(A, dict(sk, band=None, _spec=whole), hull)
    ax = Gs['axis']
    # the plane: a symmetric skirt's own (its axis), else the legs' midline
    xm = float(ax.o[0]) if sk.get('symmetric') else boot_frame(A)[1]
    V = np.asarray(G['verts'], float).copy()
    V[:, 0] = 2 * xm - V[:, 0]
    nr, n = Gs['grid']
    t, th, r = ax.coords(np.asarray(Gs['verts']))
    R = r.reshape(nr, n)
    pw = max(1, int(round(n / max(1, sk.get('pleats', 24)))))
    Rc = np.maximum.reduce([np.roll(R, k, 1) for k in range(-pw, pw + 1)])
    th_c = th.reshape(nr, n)[0]
    o = np.argsort(th_c)
    lift = (src.get('clear', 0.03) + src.get('thick', 0.01)) * L
    cols = src.get('cols', 16) + 1
    NR = len(V) // cols
    tv, thv, rv = ax.coords(V)
    Tn = t.reshape(nr, n)
    push = np.zeros(len(V))
    if src.get('shape') == 'template':                     # (laid on its own skirt rows: a symmetric skirt needs none)
        NR = 0
    for i in range(min(nr, NR)):                           # the rows over the skirt: at least its crests plus lift
        k = slice(i * cols, (i + 1) * cols)
        need = np.interp(thv[k], th_c[o], Rc[min(i, nr - 1)][o], period=2 * np.pi) + lift
        push[k] = np.maximum(0.0, need - rv[k])
    for i in range(nr, NR):                                # the tail carried with its hem
        push[i * cols:(i + 1) * cols] = push[(nr - 1) * cols:nr * cols]
    V = ax.point(tv, thv, rv + push) if push.any() else V
    faces = [tuple(reversed(f)) for f in G['faces']]
    ch = G['chain']
    J = np.asarray(ch['joints'], float).copy()
    J[:, 0] = 2 * xm - J[:, 0]
    names = ['%s_%d' % (spec['name'], i) for i in range(len(ch['bones']))]
    return dict(G, verts=V, faces=faces, z_waist=float(G['z_waist']), reach=float(V[:, 2].min()),
                chain=dict(ch, bones=names, joints=J), mirrored=float(push.max() / L))


def knot(K, x, col=1):
    """a knot table's column at x (piecewise linear, clamped): K rows [x, y1, y2, ...]."""
    K = np.asarray(K, float)
    return np.interp(x, K[:, 0], K[:, col])


def flap_stair(tail):
    """a flap tail's stepped lower edge: `steps` treads across it (0 its outer edge .. 1 its inner), their widths from
    `widths` (shares, default equal), their lengths below the skirt's hem from `outer` (the first) to `inner` (the
    last) L, listed in `lengths`, or from `first` rising by `rise` a tread. -> (edges (steps + 1,), lengths
    (steps,))."""
    n = int(tail.get('steps', 4))
    w = np.asarray(tail.get('widths') or [1.0] * n, float)
    e = np.r_[0.0, np.cumsum(w) / w.sum()]
    if tail.get('lengths'):
        ln = np.asarray(tail['lengths'], float)
    elif 'rise' in tail:
        ln = tail['first'] + tail['rise'] * np.arange(n)
    else:
        ln = tail['outer'] + (tail['inner'] - tail['outer']) * (np.arange(n) / max(1, n - 1))
    return e, ln


def flap_template(A, spec, hull):
    """an overskirt flap as a template (Michael's review of round 6: the flaps' drape and shape; the design's flap is a
    stepped panel): every number a knob, fitted to the design's silhouettes in back, three-quarter, profile and front.
    Over the skirt (`over`, from its waist line under the band, s 0, to its hem, s 1) the flap lies on the pleats'
    crests, `clear` plus `thick` L off them plus `stand` (a knot table [s, L]), between its outer and inner edges'
    azimuths (`edges`: knots [s, outer deg, inner deg]; 0 the front, + her left; the outer edge toward her side, the
    inner toward the centre back). Below the hem each column hangs on as a tail: the skirt's slope at its hem turned
    `droop` of the way to plumb (Michael's call: hang, no sweep beyond the skirt's flare), `out` L per L further out
    and `twist` L per L round toward its outer edge's side,
    for its tread's length (`tail`: flap_stair's steps, widths, outer and inner lengths, L): a stepped lower edge in
    silhouette, descending from the outer corner to the tip at the inner corner, as drawn. The dark band is geometry, a
    second material on the faces within `band` L of that stepped edge (the treads, the risers and the outer edge below
    the hem), the mesh's rows and columns set on the stair's corners and the band's edges, so it is as crisp as drawn
    in the render and exactly what the QA reads (it labels faces at their UV centre: a texture's steps were quantised
    to faces). Not subdivided (a subdivision surface rounds the stair's corners): `rows` rows over the skirt, `cols`
    columns across at least, `tail_rows` down the tail at least. The chain and weights as flap()'s.
    -> flap()'s dict, with band (per face: 1 on the band) and subdiv 0."""
    L = A['head']['L']
    whole = spec.get('_spec') or {}
    sk = next((g for g in whole.get('garments', []) if g['name'] == spec.get('over', 'skirt')), None)
    if not sk or sk.get('source') != 'hull':
        raise ValueError('%s: a flap lies on a hull skirt (%s)' % (spec['name'], spec.get('over', 'skirt')))
    Gs = skirt_hull(A, dict(sk, band=None, _spec=whole), hull)                  # (its surface: the band only adds rows)
    ax = Gs['axis']
    nr, n = Gs['grid']
    t, th, r = ax.coords(np.asarray(Gs['verts']))
    T, R = t.reshape(nr, n), r.reshape(nr, n)
    th_c = th.reshape(nr, n)[0]
    o = np.argsort(th_c)
    pw = max(1, int(round(n / max(1, sk.get('pleats', 24)))))
    Rc = np.maximum.reduce([np.roll(R, k, 1) for k in range(-pw, pw + 1)])       # the pleats' crests
    lift = (spec.get('clear', 0.02) + spec.get('thick', 0.01)) * L
    vs = np.linspace(0, 1, nr)

    def skirt_at(Z, v, a):
        """a skirt grid (rows v, columns theta) at (v, a), bilinear, periodic in a."""
        v, a = np.broadcast_arrays(np.atleast_1d(np.clip(np.asarray(v, float), 0, 1)),
                                   np.atleast_1d(np.mod(np.asarray(a, float) + np.pi, 2 * np.pi) - np.pi))
        rows = np.array([np.interp(a, th_c[o], Z[i][o], period=2 * np.pi) for i in range(nr)])   # (nr, m)
        f = v * (nr - 1)
        i0 = np.clip(np.floor(f).astype(int), 0, nr - 2)
        w = f - i0
        idx = np.arange(len(v))
        return (1 - w) * rows[i0, idx] + w * rows[i0 + 1, idx]

    E = spec['edges']
    tail = spec['tail']
    band = spec.get('band', 0.15) * L
    ue, ln = flap_stair(tail)
    ln = ln * L
    rows = int(spec.get('rows', 20))
    # the columns: evenly at least `cols`, and on the stair's risers and the band's edges beside them
    a_out1, a_in1 = np.radians(knot(E, 1.0, 1)), np.radians(knot(E, 1.0, 2))
    r_hem = float(np.mean(skirt_at(Rc, np.ones(3), np.linspace(a_out1, a_in1, 3)))) + lift
    width_hem = abs(a_in1 - a_out1) * r_hem
    bu = band / max(1e-6, width_hem)                                             # the band's width across, in u
    us = np.unique(np.round(np.r_[np.linspace(0, 1, int(spec.get('cols', 24)) + 1), ue, np.clip(ue[:-1] + bu, 0, 1)],
                            6))
    # the rows over the skirt, then down the tail: evenly at least `tail_rows`, and on the treads and the band's top
    sv = np.linspace(0, 1, rows + 1)
    tl = np.unique(np.round(np.r_[np.linspace(0, ln.max(), int(spec.get('tail_rows', 12)) + 1)[1:], ln,
                                  np.clip(ln - band, 0, None)], 9))
    tl = tl[tl > 1e-9]
    # over the skirt
    S, U = np.meshgrid(sv, us, indexing='ij')
    Aaz = np.radians(knot(E, S.ravel(), 1) * (1 - U.ravel()) + knot(E, S.ravel(), 2) * U.ravel())
    Tt = skirt_at(T, S.ravel(), Aaz)
    Rr = skirt_at(Rc, S.ravel(), Aaz) + lift + knot(spec.get('stand', [[0, 0.0], [1, 0.0]]), S.ravel()) * L
    tk = Gs.get('tuck')
    if tk:                                                    # its top tucked under the band, just over the skirt's
        Rr = tuck_pull(Rr.reshape(len(sv), len(us)), Tt.reshape(len(sv), len(us)), tk,
                       dr=tk['inset'] - 0.2 * tk['thick'], A=Aaz.reshape(len(sv), len(us))).ravel()
    over = ax.point(Tt, Aaz, Rr).reshape(len(sv), len(us), 3)
    # the tail: from each column's hem point along its hang
    hem, prev = over[-1], over[-2]
    slope = hem - prev
    slope /= np.maximum(1e-9, np.linalg.norm(slope, axis=1))[:, None]
    ah = np.radians(knot(E, 1.0, 1) * (1 - us) + knot(E, 1.0, 2) * us)
    e_out = np.stack([ax.point(0.0, a_, 1.0) - ax.point(0.0, a_, 0.0) for a_ in ah])  # radially out (the skirt's axis)
    down = np.tile(-ax.d if ax.d[2] > 0 else ax.d, (len(us), 1))
    dr = spec.get('droop', 0.3)
    dirs = (1 - dr) * slope + dr * down
    dirs /= np.linalg.norm(dirs, axis=1)[:, None]
    dirs = dirs + spec.get('out', 0.0) * e_out
    if spec.get('twist'):                                     # turning toward its outer edge's side as it falls
        e_th = np.stack([ax.point(0.0, a_ + 1e-3, 1.0) - ax.point(0.0, a_, 1.0) for a_ in ah]) / 1e-3
        dirs = dirs + spec['twist'] * np.sign(knot(E, 1.0, 1) - knot(E, 1.0, 2)) * e_th
    tails = np.array([hem + l_ * dirs for l_ in tl])                              # (len(tl), len(us), 3)
    G = np.concatenate([over, tails], 0)
    NR, NC = G.shape[:2]
    verts = G.reshape(-1, 3)
    ell = np.r_[np.zeros(len(sv)), tl]                                          # each row's length below the hem
    uc = 0.5 * (us[1:] + us[:-1])
    k_of = np.clip(np.searchsorted(ue, uc, side='right') - 1, 0, len(ln) - 1)    # the tread under each column of faces
    lim = ln[k_of]
    faces, bandf = [], []
    for j in range(NR - 1):
        lc = 0.5 * (ell[j] + ell[j + 1])
        tail_row = j >= len(sv) - 1
        for i in range(NC - 1):
            if tail_row and lc > lim[i] + 1e-9:
                continue                                                         # below its tread: not the flap
            faces.append((j * NC + i, j * NC + i + 1, (j + 1) * NC + i + 1, (j + 1) * NC + i))
            dark = False
            if tail_row:
                k = k_of[i]
                if lc > lim[i] - band:
                    dark = True                                                  # under its tread
                for q in range(len(ln)):                                         # beside a riser (q 0: the outer edge)
                    top = 0.0 if q == 0 else ln[q - 1] - band
                    if ue[q] - 1e-9 <= uc[i] <= ue[q] + bu + 1e-9 and lc >= top:
                        dark = True
            bandf.append(int(dark))
    # UV: u across, v down the whole length (the middle's arc)
    uvs = [(float(us[i]), float(j / (NR - 1))) for j in range(NR) for i in range(NC)]
    # the chain: the middle column (u 0.5) from the waist, through the hem, down its tail
    mid = np.array([np.array([np.interp(0.5, us, G[j, :, k]) for k in range(3)]) for j in range(NR)])
    lm = ln[min(len(ln) - 1, int(np.searchsorted(ue, 0.5, side='right')) - 1)]
    cen = mid[:len(sv) + int(np.searchsorted(tl, lm + 1e-12))]
    arc = np.r_[0, np.cumsum(np.linalg.norm(np.diff(cen, axis=0), axis=1))]
    nb = max(2, spec.get('bones', 5))
    a_hem = arc[len(sv) - 1]
    s_j = np.r_[0.0, a_hem, a_hem + np.linspace(0, arc[-1] - a_hem, nb)[1:]]
    joints = np.stack([np.interp(s_j, arc, cen[:, k]) for k in range(3)], 1)
    names = ['%s_%d' % (spec['name'], i) for i in range(nb)]
    row_arc = np.interp(np.arange(NR), np.arange(len(arc)), arc)
    used = np.unique(np.asarray(faces).ravel())
    return dict(verts=verts, faces=faces, weights={'hips': np.ones(len(verts))}, uv=uvs, band=bandf, subdiv=0,
                z_waist=float(over[0, NC // 2, 2]), reach=float(verts[used, 2].min()),
                chain=dict(parent='hips', bones=names, joints=joints, arc=np.repeat(row_arc, NC)),
                stair=dict(edges=ue.tolist(), lengths=(ln / L).tolist(), band_u=float(bu)))


def dense_arc(th, mass=0.8):
    """the smallest arc of the circle holding `mass` of the angles th -> (centre, half-width): a piece's span round an
    axis robust to its stray labels (the hull labels a panel's voxels from several views, and some land round the
    hem)."""
    a = np.sort(np.mod(th, 2 * np.pi))
    n = len(a)
    k = max(1, int(np.ceil(mass * n)) - 1)
    ext = np.r_[a, a + 2 * np.pi]
    widths = ext[k:k + n] - ext[:n]
    i = int(np.argmin(widths))
    lo, hi = ext[i], ext[i + k]
    return float(np.angle(np.exp(1j * (lo + hi) / 2))), float((hi - lo) / 2)


def panel_hull(A, spec, hull):
    """an open panel lofted through the hull's points of its piece (an overskirt panel): the densest arc its points span
    round the skirt's axis (dense_arc: `mass` of them; stray labels round the hem left out), per column its own top and
    bottom edge (where its points start and end), and the measured section between (geom.loft), `offset` L out. UV and
    weights as panel()'s. -> dict(verts, faces, weights, uv, z_waist)."""
    from .geom import loft
    L = A['head']['L']
    P = _hull_points(hull, spec)
    around = [hull[k] for k in ('skirt', 'skirt_panel') if hull and k in hull and len(hull[k])]
    Q = np.concatenate(around) if around else P
    top = P[:, 2].max()
    ax = _vertical_axis(Q[Q[:, 2] > np.percentile(Q[:, 2], 90)], top)
    t, th, r = ax.coords(P)
    mid, half = dense_arc(th, spec.get('mass', 0.8))
    rel = np.angle(np.exp(1j * (th - mid)))
    keep = np.abs(rel) <= half
    t, th, r, rel = t[keep], th[keep], r[keep], rel[keep]
    lo, hi = -half, half
    cols, rows = spec.get('cols', 24), spec.get('rows', 16)
    a = np.linspace(lo, hi, cols + 1)
    # per column its top and bottom: where the points in its sector start and end
    nb = 2 * cols
    edges = np.linspace(lo, hi, nb + 1)
    tt0, tt1 = np.full(nb, np.nan), np.full(nb, np.nan)
    for k in range(nb):
        m = (rel >= edges[k]) & (rel < edges[k + 1])
        if m.sum() >= 5:
            tt0[k], tt1[k] = np.percentile(t[m], 3), np.percentile(t[m], spec.get('hem_q', 97))
    ok = np.isfinite(tt0)
    if ok.sum() < 2:
        raise ValueError('%s: too few hull points across the panel' % spec['name'])
    cen = 0.5 * (edges[:-1] + edges[1:])
    sm = spec.get('hem_smooth', 1.0)
    t0 = loft.gauss1d(np.interp(a, cen[ok], tt0[ok]), sm, mode='nearest')
    t1 = loft.gauss1d(np.interp(a, cen[ok], tt1[ok]), sm, mode='nearest')
    v = np.clip((t - np.interp(rel, a, t0)) / np.maximum(1e-9, np.interp(rel, a, t1) - np.interp(rel, a, t0)), -0.2, 1.2)
    vs = np.linspace(0, 1, rows + 1)
    F = loft.field(v, th, r, vs, nth=spec.get('nth', 144), smooth=(1.0, 1.0), min_row=0.02)   # (a panel spans part of
    TH = mid + a[None, :]                                                                     # the circle: its own)
    R = F.at(np.broadcast_to(vs[:, None], (rows + 1, cols + 1)), np.broadcast_to(TH, (rows + 1, cols + 1)))
    R = R + spec.get('offset', 0.0) * L
    T = t0[None, :] + vs[:, None] * (t1 - t0)[None, :]
    verts = ax.point(T, np.broadcast_to(TH, T.shape), R).reshape(-1, 3)
    faces = [(j * (cols + 1) + i, j * (cols + 1) + i + 1, (j + 1) * (cols + 1) + i + 1, (j + 1) * (cols + 1) + i)
             for j in range(rows) for i in range(cols)]
    uvs = [(i / cols, j / rows) for j in range(rows + 1) for i in range(cols + 1)]
    vv = np.repeat(vs, cols + 1)
    sx = np.clip(verts[:, 0] / (0.08 * L), -1, 1)
    leg = 0.65 * vv ** 1.4
    Wt = {'hips': 1 - leg, 'leftUpperLeg': leg * (1 + sx) / 2, 'rightUpperLeg': leg * (1 - sx) / 2}
    return dict(verts=verts, faces=faces, weights=Wt, uv=uvs, z_waist=float(top - np.median(t0)))


def stepped_hem(n=1024, band=0.16, steps=6, step_h=0.045, repeat=10, panel=None, colors=((0.86, 0.42, 0.24),
                (0.28, 0.20, 0.18)), pleats=0, dark=True):
    """RGBA texture for a skirt: the body colour with a dark band along the hem (v = 1) whose top edge rises and falls in
    pixel steps (a stair pattern repeated `repeat` times round the skirt); panel: optional (u0, u1) where no band is drawn."""
    u = (np.arange(n) + 0.5) / n
    U, Vv = np.meshgrid(u, u[::-1])
    ph = (U * repeat) % 1.0
    tri = 1 - np.abs(ph - 0.5) * 2                         # 0 .. 1 .. 0 across each repeat
    stair = np.floor(tri * steps) / steps                  # quantised: steps
    edge = 1 - band - stair * step_h * steps / 2
    dark = (Vv >= edge) & dark                             # (dark False: the fold lines only, the band as geometry)
    if panel is not None:
        dark &= ~((U > panel[0]) & (U < panel[1]))
    img = np.empty((n, n, 4))
    img[..., :3] = np.where(dark[..., None], np.array(colors[1]), np.array(colors[0]))
    if pleats:
        # a fold line at each pleat's outer edge, fading up toward the waist
        fp = (U * pleats) % 1.0
        line = np.clip(1 - np.abs(fp - 0.5) * 2 / 0.06, 0, 1) * np.clip((1 - Vv) / 0.5, 0, 1) ** 0.7
        img[..., :3] *= (1 - 0.28 * line)[..., None]
    img[..., 3] = 1.0
    return img


# -------------------------------------------------------------------------------------------------------------------- shoes
def shoe(A, spec):
    """a shoe (or a boot's foot) as a built last: rings from the heel to the toe along the foot's direction, each a
    rounded-rectangle section (flat sole) whose width and height follow the foot (narrow heel, widest at the ball, a
    rounded toe; tall at the instep, low at the toe), sized from the foot's own vertices plus `offset`; the bottom band is
    the sole. Weighted to the foot, the toe end to the toes. -> dict(verts, faces, weights, uv, sole (per face))."""
    L = A['head']['L']
    side = spec['side']
    foot, toes = f'{side}Foot', f'{side}Toes'
    V = A['verts']
    dom, _ = dominant(A)
    fv = V[np.isin(dom, [foot, toes])]
    ank, ball = bone_seg(A, foot)
    d = ball - ank; d[2] = 0; d /= np.linalg.norm(d)
    lat = np.cross(np.array([0, 0, 1.0]), d)
    q = fv - ank
    u = q @ d; w_ = q @ lat
    off = spec.get('offset', 0.02) * L
    u0, u1 = u.min() - off, u.max() + off * 1.4
    zs = fv[:, 2].min() - spec.get('sole', 0.03) * L * 0.5
    W = (w_.max() - w_.min()) / 2 + off
    wc = (w_.max() + w_.min()) / 2
    Hin = (ank[2] - zs) + spec.get('instep', 0.10) * L
    nu, nv = spec.get('rows', 22), spec.get('segs', 28)
    verts, uvs = [], []
    for i in range(nu + 1):
        s_ = i / nu
        uu = u0 + (u1 - u0) * s_
        wid = W * (0.72 + 0.28 * math.sin(min(1.0, s_ / 0.72) * math.pi / 2))
        hgt = Hin * (1 - 0.62 * max(0.0, (s_ - 0.35) / 0.65) ** 0.9)
        end = 1.0
        if s_ > 0.82:
            end = math.sqrt(max(0.0, 1 - ((s_ - 0.82) / 0.18) ** 2))
        if s_ < 0.1:
            end = math.sqrt(max(0.0, 1 - ((0.1 - s_) / 0.1) ** 2))
        wid *= max(end, 0.02); hgt_e = hgt * (0.35 + 0.65 * max(end, 0.02))
        for j in range(nv):
            ph = 2 * math.pi * j / nv
            cx, sy = math.cos(ph), math.sin(ph)
            y = math.copysign(abs(cx) ** 0.55, cx) * wid           # a rounded rectangle (flat sides and sole)
            z = (math.copysign(abs(sy) ** 0.55, sy) + 1) / 2 * hgt_e
            verts.append(ank + d * (uu - 0) + lat * (wc + y) + np.array([0, 0, zs - ank[2] + z]))
            uvs.append((j / nv, s_))
    faces, sole = [], []
    for i in range(nu):
        for j in range(nv):
            j2 = (j + 1) % nv
            f = (i * nv + j, i * nv + j2, (i + 1) * nv + j2, (i + 1) * nv + j)
            faces.append(f)
    faces.append(tuple(range(nv - 1, -1, -1))); faces.append(tuple(nu * nv + j for j in range(nv)))
    verts = np.array(verts)
    zsole = zs + spec.get('sole', 0.03) * L
    sole = [1 if verts[list(f), 2].max() <= zsole + 1e-6 or verts[list(f), 2].mean() < zsole else 0 for f in faces]
    ss = np.array([uv[1] for uv in uvs])
    wt = np.clip((ss - 0.55) / 0.3, 0, 1)
    return dict(verts=verts, faces=faces, weights={foot: 1 - wt, toes: wt}, uv=uvs, sole=sole)


# ------------------------------------------------------------------------------------------------------------------ boots
def hermite(K, h):
    """a knot table [[h, v1, v2, ...], ...] (heights ascending) at heights h: a cubic Hermite through the knots (their
    slopes by central differences), straight on past its ends at the end slopes. -> (len(h), k)."""
    K = np.asarray(K, float)
    x, Y = K[:, 0], K[:, 1:]
    h = np.atleast_1d(np.asarray(h, float))
    m = np.gradient(Y, x, axis=0) if len(x) > 1 else np.zeros_like(Y)
    hc = np.clip(h, x[0], x[-1])
    i = np.clip(np.searchsorted(x, hc) - 1, 0, max(0, len(x) - 2))
    j = np.minimum(i + 1, len(x) - 1)
    dx = np.maximum(x[j] - x[i], 1e-9)[:, None]
    t = ((hc - x[i]) / dx[:, 0])[:, None]
    t2, t3 = t * t, t * t * t
    out = (2 * t3 - 3 * t2 + 1) * Y[i] + (t3 - 2 * t2 + t) * dx * m[i] + (-2 * t3 + 3 * t2) * Y[j] + (t3 - t2) * dx * m[j]
    lo, hi = h < x[0], h > x[-1]
    out[lo] = Y[0] + (h[lo] - x[0])[:, None] * m[0]
    out[hi] = Y[-1] + (h[hi] - x[-1])[:, None] * m[-1]
    return out


def _smoothstep(e0, e1, x):
    t = np.clip((np.asarray(x, float) - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def boot_frame(A):
    """the boots' frame: the left ankle (the two ankle joints made mirror images about their midline) and the legs'
    midline x (the body's legs stand symmetric about x = 0.0107 L, not 0). -> (ankle (3,), midline x)."""
    aL, aR = bone_seg(A, 'leftFoot')[0], bone_seg(A, 'rightFoot')[0]
    xm = float((aL[0] + aR[0]) / 2)
    return np.array([xm + (aL[0] - aR[0]) / 2, (aL[1] + aR[1]) / 2, (aL[2] + aR[2]) / 2]), xm


def boot_sections(s, theta, z, L=1.0):
    """the boot's section points: at angles theta (0 the toe's side, -y; + toward her outside) and heights z over the
    ground (L), each an offset from the ankle (x out, y back; L). The section is a superellipse quadrant by quadrant:
    its extents are the knot tables' (`profile` [h, front, back]: y; `width` [h, outer, inner]: x), so its outline in
    the front, back and profile views is those tables; the widest point sits at the section's middle in the shaft and
    `ball` of the way back from the toe in the foot (below FOOT (h0, h1): the ball's width, the heel's narrower), the
    toe's side squarer (`round_toe`) and the heel's rounder (`round_heel`) than the shaft (`round`); the ankle's fold
    (`scrunch`) added to each quadrant's extent. -> (x, y) offsets."""
    th, z = np.broadcast_arrays(np.asarray(theta, float), np.asarray(z, float))
    shape = th.shape
    th, z = th.ravel(), z.ravel()
    fb = hermite(s['profile'], z)
    ow = hermite(s['width'], z)
    f, b = fb[:, 0], fb[:, 1]
    o, i = ow[:, 0], ow[:, 1]
    beta = 1 - _smoothstep(*s.get('foot', (0.28, 0.52)), z)             # 1 in the foot, 0 in the shaft
    phi = 0.5 + beta * (s.get('ball', 0.42) - 0.5)
    cy = f + phi * (b - f)
    af, ab = cy - f, b - cy
    cx = (o + i) / 2
    ao = ai = (o - i) / 2
    sc = s.get('scrunch')
    if sc:
        hs, gap, w = sc.get('h', 0.55), sc.get('gap', 0.045), sc.get('width', 0.016)
        up = np.exp(-((z - (hs + gap / 2)) / w) ** 2)
        dn = np.exp(-((z - (hs - gap / 2)) / w) ** 2)
        d = {k: sc.get(k, (0.0, 0.0))[0] * up - sc.get(k, (0.0, 0.0))[1] * dn for k in ('front', 'back', 'outer', 'inner')}
        af, ab, ao, ai = af + d['front'], ab + d['back'], ao + d['outer'], ai + d['inner']
    ns = s.get('round', 2.3)
    nf = ns + beta * (s.get('round_toe', 2.6) - ns)
    nb = ns + beta * (s.get('round_heel', 2.2) - ns)
    sn, cs = np.sin(th), np.cos(th)
    n = np.where(cs >= 0, nf, nb)
    x = cx + np.where(sn >= 0, ao, ai) * np.sign(sn) * np.abs(sn) ** (2 / n)
    y = np.where(cs >= 0, cy - af * np.abs(cs) ** (2 / n), cy + ab * np.abs(cs) ** (2 / n))
    return x.reshape(shape), y.reshape(shape)


def boot_bottom(s, y):
    """the sole's underside over the ground (L) at a y offset from the ankle: on the ground under the forefoot, rising
    through the arch (from `heel.arch` to `heel.front`, a smoothstep) to `heel.lift`, level over the heel."""
    H = s.get('heel') or {}
    if not H:
        return np.zeros_like(np.asarray(y, float))
    return H.get('lift', 0.15) * _smoothstep(H.get('arch', -0.19), H.get('front', -0.02), y)


def boot(A, spec):
    """a boot as a template (Michael's direct control; the hull-lofted boots twisted at the ankle and sole, differed
    left to right and drew their outlines twice): one watertight upper and a heel block, from a handful of knots and
    numbers in the spec.
    - The upper: rows of sections (boot_sections) from `top` L over the ground down to the sole's underside
      (boot_bottom): the rows above `warp` L are level, the ones below bend down onto the underside, so the forefoot
      stands on the ground, the arch is raised and the heel's underside is level at the heel's top. Capped by rings
      on the underside. Its faces within `sole_t` L of the underside are the sole (the second material).
    - The heel block (`heel`): the section at the heel's top behind its front face (`heel.front`), set in by
      `heel.inset` at the top and flared out by `heel.flare` toward the ground, down to the ground; the sole's
      material.
    - The ankle's fold (`scrunch`): a bulge over a crease on each quadrant, at the design's size.
    Everything is offsets from the left ankle (boot_frame, the joints made symmetric) and heights over the ground
    (`ankle_h` L under the ankle). A boot with `mirror` is the named boot mirrored about the legs' midline: one boot is
    built, the other is its mirror image. Weighted to the lower leg above the ankle, the foot below, the toes in front
    of the ball. -> dict(verts, faces, weights, uv, sole (per face), hide (the body's vertices inside it))."""
    L = A['head']['L']
    s = spec
    if spec.get('mirror'):
        s = next(g for g in (spec.get('_spec') or {}).get('garments', []) if g['name'] == spec['mirror'])
    ank, xm = boot_frame(A)
    g = ank[2] - s['ankle_h'] * L
    top = s.get('top', 1.25)
    step = s.get('step', 0.015)
    nc = s.get('cols', 48)
    warp = s.get('warp', 0.36)
    sole_t = s.get('sole_t', 0.06)
    H = s.get('heel') or {}
    nr = max(8, int(round(top / step)))
    lev = np.linspace(top, 0.0, nr + 1)
    th = 2 * np.pi * np.arange(nc) / nc
    TH, LV = np.meshgrid(th, lev)
    Z = LV.copy()
    for _ in range(6):                                  # the rows below `warp` bent onto the underside (a fixed point)
        X, Y = boot_sections(s, TH, Z)
        zb = boot_bottom(s, Y)
        Z = np.where(LV < warp, zb + LV * (warp - zb) / warp, LV)
    X, Y = boot_sections(s, TH, Z)
    up = np.stack([X, Y, Z], -1).reshape(-1, 3)
    faces = [(r * nc + (c + 1) % nc, r * nc + c, (r + 1) * nc + c, (r + 1) * nc + (c + 1) % nc)
             for r in range(nr) for c in range(nc)]
    uvs = [(c / nc, r / nr) for r in range(nr + 1) for c in range(nc)]
    # the cap: rings on the underside toward the bottom row's middle
    K = s.get('cap_rings', 6)
    bot = up[nr * nc:(nr + 1) * nc]
    c0 = bot[:, :2].mean(0)
    base = len(up)
    ring_prev = np.arange(nr * nc, (nr + 1) * nc)
    pts = [up]
    for k in range(1, K):
        xy = c0 + (1 - k / K) * (bot[:, :2] - c0)
        ring = np.column_stack([xy, boot_bottom(s, xy[:, 1])])
        idx = np.arange(base, base + nc)
        pts.append(ring); base += nc
        faces += [(ring_prev[(c + 1) % nc], ring_prev[c], idx[c], idx[(c + 1) % nc]) for c in range(nc)]   # (facing down)
        uvs += [(c / nc, 1.0 + k / K) for c in range(nc)]
        ring_prev = idx
    ci = base
    pts.append(np.array([[c0[0], c0[1], float(boot_bottom(s, np.array([c0[1]]))[0])]])); base += 1
    faces += [(ring_prev[(c + 1) % nc], ring_prev[c], ci) for c in range(nc)]
    uvs.append((0.5, 2.0))
    n_up = len(faces)
    # the heel block
    if H:
        lift, front = H.get('lift', 0.15), H.get('front', -0.02)
        tt = np.linspace(np.pi / 2 - 0.3, 3 * np.pi / 2 + 0.3, 721)
        hx, hy = boot_sections(s, tt, np.full(len(tt), lift + 0.01))
        behind = hy >= front
        j = np.nonzero(behind)[0]
        arc = np.column_stack([hx[j], hy[j]])
        m_arc, m_ch = H.get('cols', 28), H.get('chord_cols', 8)
        cum = np.r_[0, np.cumsum(np.linalg.norm(np.diff(arc, axis=0), axis=1))]
        arc = np.column_stack([np.interp(np.linspace(0, cum[-1], m_arc), cum, arc[:, k]) for k in (0, 1)])
        arc[0, 1] = arc[-1, 1] = front
        chord = np.column_stack([np.linspace(arc[-1, 0], arc[0, 0], m_ch + 2)[1:-1], np.full(m_ch, front)])
        loop = np.vstack([arc, chord])
        cen = loop.mean(0)
        dirs = loop - cen
        rr = np.linalg.norm(dirs, axis=1, keepdims=True)
        unit = dirs / np.maximum(rr, 1e-9)
        levels = np.linspace(0.0, lift + H.get('overlap', 0.03), H.get('rows', 5))
        m = len(loop)
        h0 = base
        for kz, zz in enumerate(levels):
            grow = -H.get('inset', 0.012) + H.get('flare', 0.02) * (1 - min(1.0, zz / lift))
            ring = loop + unit * grow
            ring[m_arc:, 1] = front                       # (its front face stands upright)
            pts.append(np.column_stack([ring, np.full(m, zz)])); base += m
            uvs += [(q / m, 3.0 + kz) for q in range(m)]
        for kz in range(len(levels) - 1):
            r0, r1 = h0 + kz * m, h0 + (kz + 1) * m
            faces += [(r0 + q, r0 + (q + 1) % m, r1 + (q + 1) % m, r1 + q) for q in range(m)]
        cb, ct = base, base + 1
        pts.append(np.array([[cen[0], cen[1], levels[0]], [cen[0], cen[1], levels[-1]]])); base += 2
        uvs += [(0.5, 3.0), (0.5, 3.0 + len(levels))]
        rb, rt = h0, h0 + (len(levels) - 1) * m
        faces += [(rb + (q + 1) % m, rb + q, cb) for q in range(m)]
        faces += [(rt + q, rt + (q + 1) % m, ct) for q in range(m)]
    P = np.vstack(pts)
    # the sole: the upper's faces within sole_t of the underside, the cap and the heel
    sole = []
    for fi, f in enumerate(faces):
        if fi >= n_up - (K - 1) * nc - nc:
            sole.append(1)
            continue
        q = P[list(f)].mean(0)
        sole.append(1 if q[2] < float(boot_bottom(s, np.array([q[1]]))[0]) + sole_t else 0)
    # world: offsets from the left ankle, heights over the ground; the right boot mirrored about the legs' midline
    V = np.column_stack([ank[0] + P[:, 0] * L, ank[1] + P[:, 1] * L, g + P[:, 2] * L])
    side = spec['side']
    if side == 'right':
        V[:, 0] = 2 * xm - V[:, 0]
        faces = [tuple(reversed(f)) for f in faces]
    pre = side
    ah = s['ankle_h']
    wl = _smoothstep(ah - 0.12, ah + 0.08, P[:, 2])
    ball = (H or {}).get('arch', -0.19)
    wt = (1 - wl) * _smoothstep(ball + 0.06, ball - 0.08, P[:, 1])
    W = {pre + 'LowerLeg': wl, pre + 'Foot': 1 - wl - wt, pre + 'Toes': wt}
    dom, _ = dominant(A)
    Vb = A['verts']
    zt = g + (top - s.get('hide_below_top', 0.0)) * L
    hide = np.nonzero(((dom == pre + 'LowerLeg') & (Vb[:, 2] < zt)) | np.isin(dom, [pre + 'Foot', pre + 'Toes']))[0]
    return dict(verts=V, faces=faces, weights=W, uv=uvs, sole=sole, hide=hide)


# ------------------------------------------------------------------------------------------------------------------ sleeves
def sleeve(A, spec):
    """a puffy sleeve: a tube down the upper arm from the shoulder, swelling by `puff` and gathered at both ends. Weights
    blend the shoulder into the upper arm. -> dict(verts, faces, weights, uv)."""
    L = A['head']['L']
    side = spec['side']
    ua = f'{side}UpperArm'; sh = f'{side}Shoulder'
    h, tl = bone_seg(A, ua)
    ax = (tl - h) / np.linalg.norm(tl - h)
    t0, t1 = spec.get('t0', -0.02), spec.get('t1', 0.45)
    puff = spec.get('puff', 0.9)
    off = spec.get('offset', 0.012) * L
    rows, n = spec.get('rows', 14), spec.get('segs', 40)
    ref = np.array([0, 0, 1.0]) if abs(ax[2]) < 0.9 else np.array([0, -1.0, 0])
    e1 = ref - ax * (ref @ ax); e1 /= np.linalg.norm(e1)
    e2 = np.cross(ax, e1)
    verts, uvs = [], []
    for j in range(rows + 1):
        s = j / rows
        t = t0 + (t1 - t0) * s
        base = limb_radius(A, ua, 0.6) + off                    # the slim arm: the shoulder's mass is inside the puff
        swell = 1 + puff * math.sin(math.pi * s ** 0.75) ** 1.1
        gather = 1 - 0.06 * math.cos(math.pi * s * 2)
        c = h + (tl - h) * t
        # near the root the ring turns toward the armhole (a near-vertical plane at the body's side), so the sleeve cap
        # sits on the shoulder instead of standing square above it
        sgn = 1.0 if h[0] >= 0 else -1.0
        tilt = max(0.0, 1 - s / 0.35) ** 1.5 * spec.get('armhole', 0.65)
        axr = ax * (1 - tilt) + np.array([sgn, 0, 0]) * tilt; axr /= np.linalg.norm(axr)
        f1 = ref - axr * (ref @ axr); f1 /= np.linalg.norm(f1)
        f2 = np.cross(axr, f1)
        for k in range(n):
            a = 2 * math.pi * k / n
            ripple = 1 + 0.035 * math.sin(a * 9) * math.sin(math.pi * s)     # soft gathers
            r = base * swell * gather * ripple
            verts.append(c + (f1 * math.cos(a) + f2 * math.sin(a)) * r); uvs.append((k / n, s))
    faces = []
    for j in range(rows):
        for k in range(n):
            k2 = (k + 1) % n
            faces.append((j * n + k, j * n + k2, (j + 1) * n + k2, (j + 1) * n + k))
    verts = np.array(verts)
    ss = np.array([u[1] for u in uvs])
    wsh = np.clip(1 - ss / 0.35, 0, 1) * 0.6
    return dict(verts=verts, faces=faces, weights={sh: wsh, ua: 1 - wsh}, uv=uvs)


# ---------------------------------------------------------------------------------------------------------------------- bow
def sleeve_hull(A, spec, hull):
    """a sleeve lofted through the hull's points of its piece round the upper arm's axis (geom.loft): rows from where its
    points start (over the shoulder's cap, before the joint: t < 0) to where they end, the measured section between,
    `offset` L out; weighted to the upper arm. -> dict(verts, faces, weights, uv)."""
    from .geom import loft
    L = A['head']['L']
    side = spec.get('side', 'left')
    P = _hull_points(hull, spec)
    h, t_ = bone_seg(A, side + 'UpperArm')
    ax = loft.Axis(h, t_ - h, (0, -1, 0))
    t, th, r = ax.coords(P)
    lo, hi = np.percentile(t, spec.get('span', (1, 99)))
    rows = max(4, int(round((hi - lo) / (spec.get('step', 0.02) * L))) + 1)
    F = loft.field(t, th, r, np.linspace(lo, hi, rows), nth=spec.get('cols', 64), min_row=0.15, name=spec['name'],
                    prior=float(np.median(r)) if len(r) else None)
    V, quads, uv = loft.loft(ax, F, F.R + spec.get('offset', 0.0) * L)
    return dict(verts=V, faces=quads, weights={side + 'UpperArm': np.ones(len(V))}, uv=[tuple(x) for x in uv])


# ------------------------------------------------------------------------------------------ the wrist cuff (template)
def grow_line(u, g):
    """the lowest straight line over the points (u, g) (least mean over u; every g at most it), floored at 1 ->
    its value at each u. A row needing no growth (g <= 1) still sits under it."""
    u, g = np.asarray(u, float), np.maximum(np.asarray(g, float), 1.0)
    best, bv = np.full(len(u), g.max()), g.max()
    for i in range(len(u)):
        for j in range(i + 1, len(u)):
            if u[j] - u[i] < 1e-9:
                continue
            b = (g[j] - g[i]) / (u[j] - u[i])
            line = g[i] + b * (u - u[i])
            if (line >= g - 1e-9).all() and line.mean() < bv:
                best, bv = line, line.mean()
    return np.maximum(best, 1.0)


def cuff(A, spec):
    """a flared wrist cuff as a template (the design's: a cup wider at its top, the elbow's side, with a cream top band
    and a tab hanging from it at the front: sleeve_closeup's cuffs, garment_breakdown's; the hull-lofted band read as a
    blocky, bulging ring): a frustum round its bone from `span` [t0, t1] (L along the bone from its head) with radii
    `top` and `bottom` [out, front, in, back] (L), superellipse sections (`round`), its centre moved `shift` [out,
    front] (L) off the bone's axis, each row grown as a whole where it comes within `clear` L plus its `thick` of the
    limb's skin (the wrist, the hand's base); its ends rolled in over `roll` L by `bevel` L (a crisp rim); a second
    material (`trim`: per face) on the top `band` share of its height and on the front tab (`tab` [width L, length
    share]), whose edges lie on the mesh's columns and rows, so they stay straight. Rigid on its bone.
    -> dict(verts, faces, weights, uv, trim)."""
    L = A['head']['L']
    bone = spec['bone']
    h, tl = bone_seg(A, bone)
    d = (tl - h) / np.linalg.norm(tl - h)
    sgn = 1.0 if h[0] >= 0 else -1.0
    o = np.array([sgn, 0.0, 0.0]) - d * (d[0] * sgn)
    o /= np.linalg.norm(o)
    f = np.cross(d, o)
    if f[1] > 0:
        f = -f
    t0, t1 = spec['span']
    top, bot = np.asarray(spec['top'], float), np.asarray(spec['bottom'], float)
    band, (tab_w, tab_len) = spec.get('band', 0.25), spec.get('tab', (0.1, 0.55))
    sh = np.asarray(spec.get('shift', (0.0, 0.0)), float)
    n = spec.get('round', 2.2)
    nth = spec.get('cols', 48)
    a_tab = tab_w / 2 / max(1e-6, 0.5 * (top[1] + bot[1]))           # the tab's half-angle round the front
    th = np.linspace(-np.pi, np.pi, nth, endpoint=False) + np.pi / nth
    th = np.sort(np.concatenate([th[np.abs(np.angle(np.exp(1j * (th - np.pi / 2)))) > a_tab + 0.5 * np.pi / nth],
                                 np.pi / 2 + np.array([-a_tab, a_tab]),
                                 np.pi / 2 + np.linspace(-a_tab, a_tab, 5)[1:-1]]))
    roll, bevel = spec.get('roll', 0.02), spec.get('bevel', 0.008)
    step = spec.get('step', 0.02)
    us = set(np.linspace(0, 1, max(3, int(round((t1 - t0) / step)) + 1)))
    us |= {band, tab_len, roll / (t1 - t0), 1 - roll / (t1 - t0), 0.5 * roll / (t1 - t0), 1 - 0.5 * roll / (t1 - t0)}
    us = np.array(sorted(u for u in us if 0 <= u <= 1))
    ts = t0 + us * (t1 - t0)
    E = top[None, :] + us[:, None] * (bot - top)[None, :]            # (rows, 4): out, front, in, back
    # the rims rolled in: a quarter circle over `roll` at each end
    dist = np.minimum(ts - t0, t1 - ts)
    pull = bevel * (1 - np.sqrt(np.clip(1 - (1 - np.clip(dist / roll, 0, 1)) ** 2, 0, 1)))
    TT, TH = np.meshgrid(ts, th, indexing='ij')
    cs, sn = np.cos(TH), np.sin(TH)
    ax_ = np.where(cs >= 0, E[:, 0:1], E[:, 2:3]) - pull[:, None]
    ay_ = np.where(sn >= 0, E[:, 1:2], E[:, 3:4]) - pull[:, None]
    X = ax_ * np.sign(cs) * np.abs(cs) ** (2 / n)
    Y = ay_ * np.sign(sn) * np.abs(sn) ** (2 / n)
    # clear of the skin inside it (the wrist, the hand's base): each row's section must stay `clear` L plus its
    # thickness off the limb's skin at every angle; the rows grow by the lowest straight line over what each needs
    # (grow_line), so the sides stay straight (row by row, the rows the forearm bulged into stood out as ripples)
    dom, _ = dominant(A)
    Q = A['verts'][np.isin(dom, limb_neighbours(bone))] - h
    if len(Q):
        tq = Q @ d / L
        xq, yq = Q @ o / L - sh[0], Q @ f / L - sh[1]
        need = spec.get('thick', 0.02) + spec.get('clear', 0.006)
        gs = np.ones(len(ts))
        for i in range(len(ts)):
            k = np.abs(tq - ts[i]) < 0.5 * step + 1e-9
            if not k.any():
                continue
            a_q = np.arctan2(yq[k], xq[k])
            r_q = np.hypot(xq[k], yq[k])
            r_row = np.interp(a_q, th, np.hypot(X[i], Y[i]), period=2 * np.pi)
            gs[i] = float(np.max((r_q + need) / np.maximum(r_row, 1e-9)))
        if gs.max() > 1:
            gl = grow_line(us, gs)
            X *= gl[:, None]; Y *= gl[:, None]
    X, Y = X + sh[0], Y + sh[1]
    P = h[None, None, :] + (TT[..., None] * d + X[..., None] * o + Y[..., None] * f) * L
    nr, nc = P.shape[:2]
    V = P.reshape(-1, 3)
    faces, trim = [], []
    for i in range(nr - 1):
        um = 0.5 * (us[i] + us[i + 1])
        for j in range(nc):
            j2 = (j + 1) % nc
            faces.append((i * nc + j, i * nc + j2, (i + 1) * nc + j2, (i + 1) * nc + j))
            am = np.angle(np.exp(1j * (0.5 * (th[j] + (th[j2] if j2 else th[j2] + 2 * np.pi)) - np.pi / 2)))
            trim.append(1 if um < band or (um < tab_len and abs(am) < a_tab) else 0)
    C_ = V[[f_[0] for f_ in faces]]
    Fn = np.cross(V[[f_[1] for f_ in faces]] - C_, V[[f_[2] for f_ in faces]] - C_)
    rad = C_ - h - ((C_ - h) @ d)[:, None] * d
    if (Fn * rad).sum(1).mean() < 0:
        faces = [tuple(reversed(f_)) for f_ in faces]
    uv = [((j + 0.5) / nc, us[i]) for i in range(nr) for j in range(nc)]
    return dict(verts=V, faces=faces, weights={bone: np.ones(len(V))}, uv=uv, trim=trim)


# ------------------------------------------------------------------------------------------ the puff sleeve (template)
def puff_frame(A, side):
    """a puff sleeve's frame on its upper arm: the shoulder joint (origin), d down the arm, o out across it (away from
    the body's midline), f toward her front. The two sides' frames are mirror images when their joints are, so one knot
    table makes mirror-image sleeves. -> (origin, d, o, f)."""
    h, e = bone_seg(A, side + 'UpperArm')
    d = (e - h) / np.linalg.norm(e - h)
    sgn = 1.0 if h[0] >= 0 else -1.0
    o = np.array([sgn, 0.0, 0.0]) - d * (d[0] * sgn)
    o /= np.linalg.norm(o)
    f = np.cross(d, o)
    if f[1] > 0:
        f = -f
    return h, d, o, f


def puff_extents(s, t):
    """the puff's section extents at stations t (L down the arm from the shoulder joint): (out, front, in, back) L, from
    the knot table `profile` [[t, out, front, in, back], ...] (a cubic through the knots); above the table's first
    station the cap, a quarter ellipse `cap` L long closing to the apex (a round dome: a knot at zero would end in a
    point). -> (len(t), 4)."""
    K = np.asarray(s['profile'], float)
    t = np.atleast_1d(np.asarray(t, float))
    E = np.maximum(hermite(K, t), 0.0)
    cap = s.get('cap', 0.12)
    tc = K[0, 0]
    k = t < tc
    if k.any():
        u = np.clip((tc - t[k]) / cap, 0, 1)
        E[k] = K[0, 1:] * np.sqrt(1 - u * u)[:, None]
    return E


def puff_sections(s, th, t):
    """the puff's section offsets (along o, along f; L) at angles th (0 out, pi/2 front, pi in, -pi/2 back) and stations
    t: superellipse quadrants whose extents are puff_extents' (exponent `round`, 2 an ellipse), scalloped by `lobes`
    [n, amp] (the balloon's panels, as sleeve_closeup's cross-section: its outline 0.77 .. 1 of its radius) and gathered
    by `gathers` [n, amp_cap, amp_band, reach L] (fine folds fading in over `reach` from the cap's seam and the band).
    -> (x, y) arrays of th's broadcast shape with t."""
    th, t = np.broadcast_arrays(np.asarray(th, float), np.asarray(t, float))
    sh = th.shape
    th, t = th.ravel(), t.ravel()
    E = puff_extents(s, t)
    n = s.get('round', 2.0)
    cs, sn = np.cos(th), np.sin(th)
    ax_ = np.where(cs >= 0, E[:, 0], E[:, 2])
    ay_ = np.where(sn >= 0, E[:, 1], E[:, 3])
    x = ax_ * np.sign(cs) * np.abs(cs) ** (2 / n)
    y = ay_ * np.sign(sn) * np.abs(sn) ** (2 / n)
    K = np.asarray(s['profile'], float)
    t0, t1 = K[0, 0] - s.get('cap', 0.12), K[-1, 0]
    mod = np.ones_like(t)
    lo = s.get('lobes')
    if lo:
        body = np.sin(np.pi * np.clip((t - t0) / max(1e-9, t1 - t0), 0, 1))        # 0 at the ends, 1 mid-puff
        mod *= 1 - lo[1] * body * (0.5 - 0.5 * np.cos(lo[0] * th))
    g = s.get('gathers')
    if g:
        reach = g[3]
        w = g[1] * np.exp(-np.maximum(0, t - t0) / reach) + g[2] * np.exp(-np.maximum(0, t1 - t) / reach)
        mod *= 1 - w * (0.5 - 0.5 * np.cos(g[0] * th))
    return (x * mod).reshape(sh), (y * mod).reshape(sh)


def puff(A, spec, hull=None):
    """a puff sleeve as a template (Michael's direct control; the sleeve lofted through the hull was an open tube cut
    across the arm at the cap, whose rim stood up as a pointed corner over the shoulder, and whose lower rim poked out
    past the cuff): one closed balloon from a knot table in the spec (puff_sections), on its upper arm's frame
    (puff_frame), from a round dome over the shoulder (the cap, its apex on the arm's axis `cap` L above the table's
    first station) down to its band (spec `band`: the cream sleeve cuff, its garment name); `mirror` (a garment name)
    takes that sleeve's knots in this side's frame. Past the table's last
    station each column rounds under (a quarter ellipse) to the band's outside at the band's top, `over` L proud of it,
    then runs `tuck` L on inside the band's inner surface, `clear` L in, so its lower rim hides under the band (the
    gathers into the band). The cap's inner side runs into the torso under the top. `cols` columns, rows every `step`
    L (and `cap_rows` round the dome). Rigid on its upper arm. -> dict(verts, faces, weights, uv)."""
    L = A['head']['L']
    side = spec.get('side', 'left')
    if spec.get('mirror'):
        # the other sleeve's knots (one table for both: mirror images, as the two frames are)
        src = next((g for g in (spec.get('_spec') or {}).get('garments', []) if g['name'] == spec['mirror']), None)
        if src is None:
            raise ValueError('%s: mirror %s not in the outfit' % (spec['name'], spec['mirror']))
        spec = dict(src, **{k: spec[k] for k in ('name', 'side', 'band', '_spec') if k in spec})
    h, d, o, f = puff_frame(A, side)
    K = np.asarray(spec['profile'], float)
    cap = spec.get('cap', 0.12)
    nth = spec.get('cols', 64)
    th = -np.pi + (np.arange(nth) + 0.5) * 2 * np.pi / nth
    t_last = K[-1, 0]
    t_b0, t_end, rout = None, t_last, None
    bname = spec.get('band')
    bs = next((g for g in (spec.get('_spec') or {}).get('garments', []) if g['name'] == bname), None) if bname else None
    if bs is not None and hull is not None:
        # the band round the arm: its top along the arm and its outside per column (its lofted surface)
        Gb = band_hull(A, bs, hull) if bs.get('source') == 'hull' else band(A, bs)
        Vb = np.asarray(Gb['verts'], float) - h
        tb = Vb @ d / L
        thb = np.arctan2(Vb @ f, Vb @ o)
        rb = np.hypot(Vb @ o, Vb @ f) / L
        t_b0 = float(tb.min())
        upper = tb <= t_b0 + 0.35 * (tb.max() - t_b0)
        dth = np.abs(np.angle(np.exp(1j * (thb[upper][None, :] - th[:, None]))))
        near = dth < 2 * np.pi / nth + 0.05
        rout = np.array([rb[upper][k].max() if k.any() else np.nan for k in near])
        rout = np.where(np.isfinite(rout), rout, np.nanmedian(rout))
        t_end = t_b0 + spec.get('tuck', 0.03)
    step = spec.get('step', 0.015)
    t_top = K[0, 0]
    nb = max(2, int(round((t_end - t_top) / step)))
    ncap = spec.get('cap_rows', 8)
    phis = np.pi / 2 * np.arange(1, ncap) / ncap                     # the dome's rows by angle (0 the apex)
    ts = np.array([t_top - cap * math.cos(p_) for p_ in phis] + list(t_top + (t_end - t_top) * np.arange(nb + 1) / nb))
    TT, TH = np.meshgrid(ts, th, indexing='ij')
    X, Y = puff_sections(spec, TH, np.minimum(TT, t_last))
    if rout is not None:
        R = np.hypot(X, Y)
        tgt = (rout + spec.get('over', 0.004))[None, :]
        u = np.clip((TT - t_last) / max(1e-6, t_b0 - t_last), 0, 1)
        Rn = np.where(R > tgt, tgt + (R - tgt) * np.sqrt(np.maximum(0.0, 1 - u * u)), R)
        inside = rout[None, :] - bs.get('thick', 0.02) - spec.get('clear', 0.006)
        w = _smoothstep(t_b0, t_b0 + min(0.012, 0.5 * spec.get('tuck', 0.03)), TT)
        Rn = np.where(TT > t_b0, (1 - w) * np.minimum(Rn, tgt) + w * np.minimum(Rn, inside), Rn)
        k = np.where(R > 1e-9, Rn / np.maximum(R, 1e-9), 1.0)
        X, Y = X * k, Y * k
    P = (h[None, None, :] + (TT[..., None] * d + X[..., None] * o + Y[..., None] * f) * L)
    nr = len(ts)
    V = np.concatenate([(h + (t_top - cap) * L * d)[None], P.reshape(-1, 3)])
    faces = [(0, 1 + (j + 1) % nth, 1 + j) for j in range(nth)]                 # the apex fan
    for i in range(nr - 1):
        for j in range(nth):
            j2 = (j + 1) % nth
            faces.append((1 + i * nth + j, 1 + i * nth + j2, 1 + (i + 1) * nth + j2, 1 + (i + 1) * nth + j))
    # outward: the faces' normals away from the arm's axis
    C_ = V[np.array([f_[0] for f_ in faces[nth:]])]
    Fn = np.cross(V[[f_[1] for f_ in faces[nth:]]] - C_, V[[f_[2] for f_ in faces[nth:]]] - C_)
    rad = C_ - h - ((C_ - h) @ d)[:, None] * d
    if (Fn * rad).sum(1).mean() < 0:
        faces = [tuple(reversed(f_)) for f_ in faces]
    uv = [(0.5, 0.0)] + [((j + 0.5) / nth, i / max(1, nr - 1)) for i in range(nr) for j in range(nth)]
    return dict(verts=V, faces=faces, weights={side + 'UpperArm': np.ones(len(V))}, uv=uv,
                frame=dict(origin=h, d=d, o=o, f=f), t_band=t_b0, t_end=t_end)


def puff_knots(A, hull, side, t_step=0.05, cap=0.12, q=90, smooth=1.0):
    """a puff's knot table measured from the hull's points of its sleeve, for a spec (the numbers then live in the spec,
    as the boots' do): per station every `t_step` L along the arm, the `q` percentile of the points' distance from the
    axis in each quadrant (out, front, in, back), smoothed along the arm; the inner quadrant, which the torso hides near
    the cap, takes the arm's radius there plus 0.03 L. The first station sits `cap` L below the points' top (the dome
    above it). -> [[t, out, front, in, back], ...] (L)."""
    from .geom import loft
    L = A['head']['L']
    sid = 'L' if side == 'left' else 'R'
    h, d, o, f = puff_frame(A, side)
    P = hull['sleeve_' + sid] - h
    t, x, y = P @ d / L, P @ o / L, P @ f / L
    th, r = np.arctan2(y, x), np.hypot(x, y)
    top, bot = np.percentile(t, 1), np.percentile(t, 99)
    ts = np.arange(top + cap, bot + 1e-9, t_step)
    dom, _ = dominant(A)
    Va = A['verts'][np.isin(dom, [side + 'UpperArm'])] - h
    ta, ra = Va @ d / L, np.hypot(Va @ o, Va @ f) / L
    E = np.full((len(ts), 4), np.nan)
    for i, a in enumerate(ts):
        k = np.abs(t - a) <= t_step / 2
        for qd, c in enumerate((0.0, np.pi / 2, np.pi, -np.pi / 2)):
            m = k & (np.abs(np.angle(np.exp(1j * (th - c)))) < np.pi / 4)
            if m.sum() >= 5:
                E[i, qd] = np.percentile(r[m], q)
        near = np.abs(ta - a) < 0.03
        arm = float(np.median(ra[near])) if near.any() else 0.12
        if not np.isfinite(E[i, 2]) or E[i, 2] < arm + 0.03:
            E[i, 2] = arm + 0.03
    for qd in range(4):
        ok = np.isfinite(E[:, qd])
        E[:, qd] = np.interp(np.arange(len(ts)), np.nonzero(ok)[0], E[ok, qd])
    E = loft.gauss1d(E, smooth, axis=0)
    return [[round(float(a), 4)] + [round(float(v), 4) for v in e] for a, e in zip(ts, E)]


def bow(A, spec):
    """a big ribbon bow on the chest: two puffy lobes (squashed, tapering into the knot, a soft fold down their face), a
    rounded knot, two tails hanging out and down with notched ends (`tail`: their length, a share of the size; 0.62).
    -> dict(verts, faces, weights, uv)."""
    L = A['head']['L']
    sz = spec.get('size', 0.5) * L
    uc = bone_seg(A, 'upperChest'); ch = bone_seg(A, 'chest')
    z = ch[0][2] + (uc[1][2] - ch[0][2]) * spec.get('height', 0.72)
    V = A['verts']
    near = (np.abs(V[:, 2] - z) < 0.012) & (np.abs(V[:, 0]) < 0.03)
    y = V[near, 1].min() - spec.get('offset', 0.03) * L if near.any() else -0.12
    return _bow_mesh(np.array([0.0, y, z]), sz, spec.get('tail', 0.62), L)


LOBE = 0.52                     # a lobe's far end: this share of the bow's size out from its centre (_bow_mesh)
TAIL0 = 0.08                    # the tails start this share of the size under the centre


def bow_spec(spec):
    """the bow's spec with its pleat resolved (round 5, coordinator: land the measurement, hold the geometry): `pleat`
    with `on` false is dropped, and the knobs that belong to it with it; on (the default when present), its `knot_box`
    is the bow's knot and its `tails` (the tails' root under the knot: root, root_back, root_seat) join the ribbon's
    keys, and its `pillow` keys (the pillow lobes' knot, end, end_p, drop) are dropped. So one switch turns the pleated
    bow and the fixes that go with it on together. `close_hung` the same way (Michael's choice, tool/bow2: the tails
    hung close, turned 20 deg, narrower, the pillow's lower edge dropped): on, its `ribbon` keys join the ribbon's and
    its other keys (drop) the bow's; off, it is dropped (deferred with the pleat, round 5: on pipeline-3d's
    geometry the close-hung pillows read bow_front_bleed 0.205 F and loop_end 0.244 W). -> a copy (or the spec itself
    when it has neither)."""
    C = spec.get('close_hung')
    if C:
        spec = dict(spec)
        spec.pop('close_hung')
        if C.get('on', True) is not False:
            for k, v in C.items():
                if k == 'ribbon':
                    spec['ribbon'] = dict(spec.get('ribbon') or {}, **v)
                elif k != 'on':
                    spec[k] = v
    P = spec.get('pleat')
    if not P:
        return spec
    out = dict(spec)
    if P.get('on', True) is False:
        out.pop('pleat')
        return out
    P = dict(P)
    for k in ('on', 'knot_box', 'tails'):
        P.pop(k, None)
    out['pleat'] = P
    if spec['pleat'].get('knot_box') is not None:
        out['knot_box'] = spec['pleat']['knot_box']
    if spec['pleat'].get('tails'):
        out['ribbon'] = dict(spec.get('ribbon') or {}, **spec['pleat']['tails'])
    for k in ('knot', 'end', 'end_p', 'drop', 'drop_p'):
        out.pop(k, None)
    return out


def bow_hull(A, spec, hull):
    """the bow placed and sized from the hull's points of it and its tails (fold: bow_tail_L, bow_tail_R): its size
    from the lobes' width (2 LOBE sizes), its centre at their middle, the tails' length from how low their points
    reach; the mesh is bow()'s, then (conform, default on) wrapped onto the hull's front there (front_surface), so the
    lobes follow the chest round as the design's do: flat, a bow wide enough from the front sticks out in profile."""
    L = A['head']['L']
    spec = bow_spec(spec)
    B = _hull_points(hull, {'name': spec['name'], 'piece': spec.get('piece', spec['name'])}, fold=())
    tails = [hull[k] for k in spec.get('fold', ('bow_tail_L', 'bow_tail_R')) if k in hull and len(hull[k])]
    lo, hi = np.percentile(B[:, 0], [2, 98])
    z = float(np.median(B[:, 2]))
    ext = drawn_extent(spec.get('_spec') or {}, A, spec.get('piece', spec['name'])) if spec.get('drawn', True) else None
    if ext is not None:
        # the drawn bow's width and height, not its hull points': the hull labels part of the collar's lapels as bow
        # (both cream), which made the bow too big and set it over the lapels
        lo, hi = ext[0], ext[2]
        z = 0.5 * (ext[1] + ext[3])
    z += spec.get('lift', 0.0) * L
    sz = (hi - lo) / (2 * LOBE)
    depth = spec.get('depth', 0.06) * sz                          # the lobes' half-depth, sizes (the drawn bow is flat)
    y = float(np.percentile(B[:, 1], 2)) + depth                  # (conform then puts the front on the hull's)
    tail = spec.get('tail', 0.62)
    tail_ext = [drawn_extent(spec.get('_spec') or {}, A, k) for k in ('bow_tail_L', 'bow_tail_R')] \
        if spec.get('drawn', True) else []
    tail_ext = [e for e in tail_ext if e is not None]
    if tail_ext:
        tail = max(0.1, (z - min(e[1] for e in tail_ext)) / sz - TAIL0)
    elif tails:
        zmin = np.percentile(np.concatenate(tails)[:, 2], 2)
        tail = max(0.1, (z - zmin) / sz - TAIL0)                  # the tails' outer corners are their lowest point
    G = _bow_mesh(np.array([0.5 * (lo + hi), y, z]), sz, tail, L, depth=depth, knot=spec.get('knot', 0.35),
                  wing=spec.get('wing'), ribbon=spec.get('ribbon'), end=spec.get('end', 0.0),
                  end_p=spec.get('end_p', 2.0), drop=spec.get('drop', 0.0), drop_p=spec.get('drop_p', 1.5),
                  pleat=spec.get('pleat'), knot_box=spec.get('knot_box'))
    if spec.get('conform', True):
        # the flat template wrapped onto the design's bow: each vertex moved in depth by where the hull's front is at its
        # (x, z) against where the template's front plane is, so the lobes follow the chest round as drawn
        S = np.concatenate([B] + tails)
        S = S[S[:, 1] < np.percentile(S[:, 1], 2) + spec.get('front_band', 0.3) * L]   # its front (stray labels behind)
        fy = front_surface(S, spec.get('cell', 0.04) * L, smooth=spec.get('front_smooth', 1.0))
        V = G['verts']
        ze = V[:, 2].copy()
        if (spec.get('pleat') or {}).get('wrap') == 'row' and G.get('lobe_v') is not None:
            # pleat.wrap 'row': pleated lobes wrapped by their centre row only (stiff up and down; tried in p3 against
            # the crease's missing line: it didn't bring it, and the profile fell 0.58 -> 0.46)
            ze[G['lobe_v']] = z
        dy = (fy(V[:, 0], ze) - (y - depth)) * spec.get('conform_k', 1.0)
        # the shift smoothed over the mesh (neighbours' mean): the grid's cells stepped the lobes' edges, which read
        # torn in profile, and pushed the lobes' backs into the collar under them
        nb = [set() for _ in range(len(V))]
        for f in G['faces']:
            for a in f:
                nb[a].update(f)
        nb = [np.fromiter(n, int) for n in nb]
        for _ in range(spec.get('conform_smooth', 4)):
            dy = np.array([dy[n].mean() if len(n) else dy[i] for i, n in enumerate(nb)])
        V[:, 1] += dy
    stand = (spec.get('ribbon') or {}).get('stand', 0.0)
    if stand:
        # the tails hung `stand` L in front of where the wrap puts them (the jacket's front there: flush, they read as a
        # torn sliver along its edge in profile and the jacket showed through them in three-quarter), eased in over
        # the first `stand_in` of their length from the knot
        ts = G['tail_s']
        k_ = np.clip(np.nan_to_num(ts, nan=0.0) / (spec.get('ribbon') or {}).get('stand_in', 0.3), 0.0, 1.0)
        e_ = k_ * k_ * (3 - 2 * k_)
        G['verts'][:, 1] -= stand * L * e_
        back = (spec.get('ribbon') or {}).get('back', 0.0)
        if back:
            # back (L): the tails' tops set back this far toward the loops behind them, easing out over the same
            # `stand_in` (round 5: they hung 0.02-0.04 L in front of the pleat's lower layer by the knot, a see-through
            # slit in profile)
            on = ~np.isnan(ts)
            G['verts'][on, 1] += back * L * (1 - e_[on])
    kst = (spec.get('pleat') or {}).get('stand')
    seat = (spec.get('pleat') or {}).get('seat')
    if (kst is not None or seat is not None) and G.get('knot_v') is not None:
        # the knot stood in front of the lobes (after the wrap: the chest's round moved the lobes' middles forward of
        # their pinch): its back in front of the lobes' surface at its sides, so its outline (the hull's back faces,
        # round its edge) draws against the lobes as the design's line does, and in profile it shows in front
        V = G['verts']
        kv = G['knot_v']
        lv = G['lobe_v']
        zk0, zk1 = V[kv, 2].min(), V[kv, 2].max()
        xk = np.abs(V[kv, 0]).max()
        near = lv[(V[lv, 2] > zk0) & (V[lv, 2] < zk1) & (np.abs(V[lv, 0]) < xk + 0.03 * L)]
        allz = lv[(V[lv, 2] > zk0) & (V[lv, 2] < zk1)]
        side = V[near, 1].min() if len(near) else V[kv, 1].max()      # the lobes' front at the knot's sides
        front = V[allz, 1].min() if len(allz) else side                # ... and anywhere at its height (profile)
        # its back `stand` L behind the lobes' frontmost at its height (so in profile it stands in front of them by
        # its depth less that, with no gap between), but at least 0.004 L in front of them by its sides (its outline)
        if seat is None:
            dyk = min(front + kst * L, side - 0.004 * L) - V[kv, 1].max()
        else:
            # pleat.seat (L): the knot's back just this far in front of the lobes by its sides (its outline there), the
            # lobes' middles left to stand round it (pleat.bulge): in profile it sits in the loops, as drawn, where
            # `stand` followed the lobes' frontmost and floated it in front of them
            dyk = side - seat * L - V[kv, 1].max()
        V[kv, 1] += dyk
    if G.get('root_v') is not None and G.get('knot_v') is not None:
        # ribbon.root: the tails' root rows (from just above the knot's bottom up) set to the knot's centre depth after
        # the wrap, flat: hidden inside the knot and the panels by its sides (the turned ribbon's inner edge stood
        # 0.02 L in front of the knot's face there and covered its lower half: knot IoU 1.0 -> 0.6, round 5's t1)
        yk = float(np.mean(G['verts'][G['knot_v'], 1]))
        rbk = (spec.get('ribbon') or {}).get('root_back')
        if rbk is not None:
            # root_back (L): the root behind the knot's back by this much instead: at its centre depth it hid the back
            # half of the knot's outline shell (the line round its sides and bottom thinned or went: t9, t10)
            yk = float(np.max(G['verts'][G['knot_v'], 1])) + rbk * L
        G['verts'][G['root_v'], 1] = yk
        seat = (spec.get('ribbon') or {}).get('root_seat', 0.0)
        if seat and G.get('seat_v') is not None:
            # root_seat (0..1): the tails' top row (just under the knot) moved that share of the way back to the knot's
            # centre depth (never forward): the turned ribbon's inner edge stood in front of the knot's face there and
            # hid the knot's lower outline (round 5's t9: the knot merged into the tails in front)
            sv = G['seat_v']
            y0 = G['verts'][sv, 1]
            G['verts'][sv, 1] = np.maximum(y0, y0 + seat * (yk - y0))
    clr = spec.get('clear')
    if clr:
        # pieces don't interpenetrate (the placement rules outrank the reference's exact placement): the lobes held
        # off the jacket. The wrap puts the bow's front on the hull's, so its lower layer's back sank up to 0.03 L into
        # the jacket and the lower edge's outline, drawn behind the jacket's surface, didn't show (bow_front_bleed).
        # Off in the default spec (round 4): bleed 0.25 -> 0.018 at gap 0.018, but every gap tried (0.006-0.018) folds
        # the strips (110-300 triangles flipped against the bake alone; crumpled lower outer corners in front): the
        # soft floor squeezes the strips' backs, buried up to 0.03 L, against their fronts along differing normals
        sel = np.ones(len(G['verts']), bool)
        if clr.get('parts', 'lobes') == 'lobes':
            if G.get('knot_v') is not None:
                sel[G['knot_v']] = False
            sel[~np.isnan(np.asarray(G['tail_s'], float))] = False
        if clr.get('bake', True):
            # cleared as it renders: the build's Subdivision (level 1, limit) baked into the mesh first, the piece then
            # built without one. Clearing the cage left the subdivided strip's lower edge 0.0016 L into the jacket
            # where the cage's vertices stood 0.0096 L clear (the cage's edges, 0.014 L, span the bust's round)
            from .geom.subsurf import subdivide
            wk = sorted(G['weights'])
            car = np.c_[np.asarray(G['uv'], float).reshape(len(G['verts']), -1), sel.astype(float),
                        np.stack([np.asarray(G['weights'][k], float) for k in wk], 1)]
            R = subdivide(np.asarray(G['verts'], float), [tuple(f) for f in G['faces']], levels=1, carry=car)
            nuv = car.shape[1] - 1 - len(wk)
            G['verts'] = np.asarray(R['V'], float)
            G['faces'] = [tuple(int(i) for i in q) for q in R['quads']]
            G['uv'] = [tuple(x) for x in R['carry'][:, :nuv]]
            sel = R['carry'][:, nuv] > 0.5                       # (the parts are disconnected: exact)
            G['weights'] = {k: R['carry'][:, nuv + 1 + i] for i, k in enumerate(wk)}
            G['subdiv'] = 0
            for k in ('knot_v', 'lobe_v', 'tail_s'):
                G.pop(k, None)
        if clr.get('mode') == 'column':
            G['verts'] = clear_column(G['verts'], sel, A, spec, hull, clr)
        else:
            G['verts'][sel] = clear_of(G['verts'][sel], A, spec, hull, clr)
    G['fit'] = dict(size=sz / L, tail=tail, depth=depth / L, centre=[0.5 * (lo + hi), y, z])
    return G


def _shell_front(A, spec, hull, c):
    """the shells a clearance is measured against (c['of'], default the jacket 'top'), rebuilt from the spec as the build
    makes them, at their level-1 Subdivision (as they render: c['limit'], default True) -> (triangle centres, outward
    unit normals), or None."""
    sa = spec.get('_spec') or {}
    names = c.get('of', ['top'])
    nrm = vertex_normals(A['verts'], A['faces'])
    from scipy.spatial import cKDTree
    C, N = [], []
    for g in sa.get('garments', []):
        if g.get('name') not in names or g.get('kind') != 'shell':
            continue
        S = shell(A, dict(g, _spec=sa), nrm, hull)
        SV, SF = np.asarray(S['verts'], float), S['faces']
        if c.get('limit', True):
            from .geom.subsurf import subdivide
            R = subdivide(SV, [tuple(f) for f in SF], levels=1)
            SV, SF = np.asarray(R['V'], float), [tuple(q) for q in R['quads']]
        out = nrm[cKDTree(A['verts']).query(SV)[1]]
        Tr = np.array([(f[0], f[k], f[k + 1]) for f in SF for k in range(1, len(f) - 1)], np.int64).reshape(-1, 3)
        a, b, d = SV[Tr[:, 0]], SV[Tr[:, 1]], SV[Tr[:, 2]]
        n_ = np.cross(b - a, d - a)
        ln = np.linalg.norm(n_, axis=1)
        ok = ln > 1e-15
        n_ = n_[ok] / ln[ok, None]
        n_ *= np.where((n_ * out[Tr[ok]].sum(1)).sum(1) < 0, -1.0, 1.0)[:, None]
        C.append(((a + b + d) / 3)[ok]); N.append(n_)
    if not C:
        return None
    return np.concatenate(C), np.concatenate(N)


def clear_column(V, sel, A, spec, hull, c):
    """the bow's `clear` with mode 'column' (round 5): the lobes (`sel`) brought toward the camera (-y) by one smoothed
    offset per column (x), so every vertex of a column moves alike: nothing is squeezed and no triangle flips (clear_of's
    soft floor along the jacket's normal pressed the strips' buried backs against their fronts: 110-300 flips). The
    offset is measured where the line must show: per column bin (`bin` L wide) the lobes' lowest vertices (within `rim`
    L of the bin's lowest) against the jacket's rendered front `below` L under them, which must stand `gap` L behind
    them (the bust comes toward the camera under the lobes' lower edge and hid its outline: bow_front_bleed). The
    offsets are smoothed over x (`smooth` L), and with `ramp` (L) fade out over that height above the lower edge (a
    tilt; None: the whole column). Rim points the knot or a tail covers in front (within `cover` L) set none. -> V
    moved (m)."""
    from scipy.spatial import cKDTree
    L = A['head']['L']
    got = _shell_front(A, spec, hull, c)
    V = np.asarray(V, float).copy()
    if got is None or not np.any(sel):
        return V
    C, N = got
    front = C[N[:, 1] < -0.2]                                   # the jacket's camera-facing triangles
    if not len(front):
        return V
    T2 = cKDTree(front[:, [0, 2]])
    P = V[sel]
    # the rest of the bow (its knot and tails): a rim point with one of theirs in front of it within `cover` L (x, z) is
    # hidden in front, its line not drawn there, so it sets no offset (the strips' rims behind the tails are buried
    # deep in the bust: counted, they pushed whole columns 0.08 L forward, in front of the tails)
    # (off unless set: with `cover` 0.012-0.02 the offsets jumped between covered and open columns and 323-327
    # triangles flipped, round 5's c3/c4)
    O = V[~np.asarray(sel, bool)]
    TO = cKDTree(O[:, [0, 2]]) if len(O) and c.get('cover') else None
    cover = (c.get('cover') or 0.0) * L
    bw, rim = c.get('bin', 0.01) * L, c.get('rim', 0.012) * L
    below, gap = c.get('below', 0.006) * L, c.get('gap', 0.015) * L
    xb = np.floor(P[:, 0] / bw).astype(int)
    bins = np.unique(xb)
    need = np.zeros(len(bins))
    zlow = np.zeros(len(bins))
    for i, b in enumerate(bins):
        m = xb == b
        z0 = P[m, 2].min()
        zlow[i] = z0
        r = P[m][P[m, 2] <= z0 + rim]
        if TO is not None and len(r):
            hid = np.array([any(O[j, 1] < y for j in TO.query_ball_point([x, z], cover))
                            for x, y, z in r[:, :3]])
            r = r[~hid]
            if not len(r):
                continue
        q = np.c_[r[:, 0], r[:, 2] - below]
        _, j = T2.query(q, k=8)
        yj = front[j, 1].min(1)                                  # the jacket's front there (frontmost of the near ones)
        need[i] = max(0.0, float((r[:, 1] - (yj - gap)).max()))
    xc = (bins + 0.5) * bw
    sm = c.get('smooth', 0.03) * L
    w = np.exp(-0.5 * ((xc[:, None] - xc[None, :]) / max(sm, 1e-9)) ** 2)
    # smoothed as an upper envelope (a column never gets less than its own need): the max of the need and its blur
    blur = (w * need[None, :]).sum(1) / w.sum(1)
    k_ = c.get('envelope', 1.0)
    field = np.maximum(need * k_, blur)
    dy = np.interp(P[:, 0], xc, field)
    if c.get('ramp'):
        zl = np.interp(P[:, 0], xc, zlow)
        dy *= 1 - np.array([_smooth(t) for t in (P[:, 2] - zl) / (c['ramp'] * L)])
    P[:, 1] -= dy
    V[sel] = P
    return V


def clear_of(P, A, spec, hull, c):
    """points held off other garments' surfaces: each moved out along the surface's normal (the nearest faces' planes,
    inverse-distance weighted over 6) to at least `gap` L in front of it by a soft floor (d -> gap + soft log(1 +
    e^((d - gap) / soft)), L: monotone, so a thin layer's front and back keep their order, and points more than a few
    `soft` clear barely move). c: dict(of=[garment names, shells; default the jacket 'top'], gap (L, 0.006), soft (L,
    0.002), limit (default True: against the shells' level-1 Subdivision, as they render; a concave cage renders in
    front of itself)). The shells are rebuilt from the spec (`_spec`) as the build makes them. -> P moved (m)."""
    from scipy.spatial import cKDTree
    L = A['head']['L']
    sa = spec.get('_spec') or {}
    names = c.get('of', ['top'])
    nrm = vertex_normals(A['verts'], A['faces'])
    C, N = [], []
    for g in sa.get('garments', []):
        if g.get('name') not in names or g.get('kind') != 'shell':
            continue
        S = shell(A, dict(g, _spec=sa), nrm, hull)
        SV, SF = np.asarray(S['verts'], float), S['faces']
        if c.get('limit', True):
            # the surface as it renders: the build's Subdivision (level 1, limit), which pushes a concave cage out (the
            # chest under the bow's lower edge: the render up to 0.007 L in front of the cage)
            from .geom.subsurf import subdivide
            R = subdivide(SV, [tuple(f) for f in SF], levels=1)
            SV, SF = np.asarray(R['V'], float), [tuple(q) for q in R['quads']]
        out = nrm[cKDTree(A['verts']).query(SV)[1]]               # outward: the body's normal under each vertex
        Tr = np.array([(f[0], f[k], f[k + 1]) for f in SF for k in range(1, len(f) - 1)], np.int64).reshape(-1, 3)
        a, b, d = SV[Tr[:, 0]], SV[Tr[:, 1]], SV[Tr[:, 2]]
        n_ = np.cross(b - a, d - a)
        ln = np.linalg.norm(n_, axis=1)
        ok = ln > 1e-15
        n_ = n_[ok] / ln[ok, None]
        n_ *= np.where((n_ * out[Tr[ok]].sum(1)).sum(1) < 0, -1.0, 1.0)[:, None]
        C.append(((a + b + d) / 3)[ok]); N.append(n_)
    if not C:
        return P
    C, N = np.concatenate(C), np.concatenate(N)
    P = np.asarray(P, float).copy()
    _, j = cKDTree(C).query(P, k=6)
    dist = np.linalg.norm(P[:, None, :] - C[j], axis=2)
    w = 1 / np.maximum(dist, 1e-6)
    d = (((P[:, None, :] - C[j]) * N[j]).sum(2) * w).sum(1) / w.sum(1)
    n = (N[j] * w[..., None]).sum(1)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-15)
    gap, soft = c.get('gap', 0.006) * L, c.get('soft', 0.002) * L
    f = gap + soft * np.logaddexp(0.0, (d - gap) / soft)
    return P + (f - d)[:, None] * n


def _bow_mesh(c, sz, tail, L, depth=None, knot=0.35, wing=None, ribbon=None, end=0.0, end_p=2.0, drop=0.0, drop_p=1.5,
              pleat=None, knot_box=None):
    """bow()'s mesh round centre c at size sz (m) with tails `tail` sizes long, lobes `depth` (m) deep either side of the
    centre (default 0.09 sizes), each lobe's height at the knot `knot` of its full height. `wing` (dict, sizes): the
    lobes as a bow tie's wings (the design's: pinched at the knot, flaring to tall ends cut nearly square), their half-
    height `knot` at the knot growing to `end` at the far end (`power` shapes the growth), the end closed over its last
    `cap` share by a quarter ellipse (a flat end with round corners), the end's middle raised by `rise`; else the old
    pillow (fattest mid-lobe). `ribbon` (dict, sizes): the tails' width `w` [at the knot, at the end], their spread
    `out` (how far out their ends swing) and the ends' cut `slant` (the outer corner lower); else the old tails. Its
    `turn` (degrees, default 0): each tail's section turned about its length, its outer edge back and its inner edge
    forward (a ribbon falling over the bust's round shows its face in profile, as the design's do; 0 flat to the front).
    Its `hinge` (0 .. 1, default 0): each row brought forward by that share of its turned half-depth, so at 1 the outer
    edge stays on the wrap (the jacket's front) where a turn about the middle sank it into the jacket with no line
    between; `stand` is then the outer edge's clearance. Its `root` (sizes, default 0): each tail's top carried up
    behind the knot by that much (the tails come from under the knot).
    `drop` (sizes, default 0): the pillow lobes' lower edge lowered toward their outer ends by drop u^drop_p (u 0 at the
    knot .. 1 at the end; the top edge kept), shrinking with the end cap: the drawn loops flare to tall ends, their
    lower corners hanging (in profile they hang fullest low; the pillows sat high and read as tipped disks).
    `pleat` (dict, sizes; tool/pieceref, Michael 2026-09-30: the lobes read as pillows): each lobe a trapezoid in front
    (the design's: pinched at the knot, its top rising to a square upper outer corner, its bottom falling to a rounder
    lower one) folded along its crease, a straight line from the knot's lower corner to the lower outer corner: the
    panel above it stands in front of a strip below it (the fold's underside, sagging `sag` below the line mid-lobe),
    `step` of the panel's half-depth behind, so the panel's lower edge is a silhouette its outline draws (inverted hulls
    draw silhouettes only). Its keys: knot (the half-height at the knot), top, bottom (the outer end's top above and
    bottom below the centre), sag, rise, cap and end_p (the outer end's cap share and [upper, lower] powers), pinch (the
    half-depth at the knot over the fullest), step, thin (the strip's half-depth over the panel's), overlap (the panel
    reaching under the line), x0 (the lobes' inner end), stand (bow_hull: the knot's back this far (L) in front of the
    lobes by its sides), cup (the lobes' outer ends this far forward of their pinch: in profile they reach past the
    knot's back, as drawn, while by its sides they stay behind it); top_p, bottom_p (the upper and lower edges' rise
    and fall along the lobe, u^p: under 1 fuller by the knot, as drawn); crease [at the knot, at the outer end] (the
    crease its own line above the lower edge, as a share of the lobe's height; crease_p how late it falls; the strip
    below it shows as the loop's lower layer, closing onto it over `close` before the end cap), almond (dict: the drawn
    upper fold, _almond), bulge [amount, u] (the lobes' middles forward: _bulge), seat (L: bow_hull stands the knot's
    back this far in front of the lobes by its sides; without stand or seat the knot stays where the wrap puts it, its
    front `-0.012 L` proud). `knot_box` (sizes: wide, deep, tall): the knot (else the wing's box or the old one).
    The tails' vertices' share of their length (0 at the knot .. 1 at the end; NaN off the tails) -> the result's
    'tail_s', and the knot's and the lobes' vertex indices ('knot_v', 'lobe_v')."""
    depth = 0.09 * sz if depth is None else depth
    verts, faces, uvs = [], [], []
    tail_s = {}

    def add(vs, fs, us):
        o = len(verts); verts.extend(vs); uvs.extend(us); faces.extend([tuple(i + o for i in f) for f in fs])
    nu, nv = 24, 14
    lobe_v, root_v, seat_v = [], [], []
    for sx in (-1, 1):
        vs, us = [], []
        if pleat:
            l0 = len(verts)
            for kind in ('panel', 'strip'):
                vs, us, fs = _pleat_band(pleat, kind, sx, sz, depth, nu)
                add([c + v for v in vs], fs, us)
            lobe_v.extend(range(l0, len(verts)))
            if pleat.get('almond') is not None:
                vs, us, fs = _pleat_band(pleat, 'almond', sx, sz, depth, nu)
                add([c + v for v in vs], fs, us)
            vs, us = [], []
        elif wing:
            # a bow tie's wing: sections along x from the knot (u 0) to the end (u 1), each an ellipse in (depth,
            # height), its half-height growing from the knot's to the end's, closed at the end by a quarter ellipse
            nw = 18
            capw = wing.get('cap', 0.12)
            hk, he = wing.get('knot', 0.09), wing.get('end', 0.2)
            pw_, rise = wing.get('power', 1.0), wing.get('rise', 0.02)
            for i in range(nw + 1):
                u = i / nw
                x = sx * (0.05 + (LOBE - 0.05) * u) * sz
                hh = hk + (he - hk) * min(1.0, u / (1 - capw)) ** pw_
                if u > 1 - capw:
                    e = (u - (1 - capw)) / capw
                    k_ = math.sqrt(max(0.0, 1 - e * e))
                else:
                    k_ = 1.0
                dd = depth * (0.7 + 0.3 * math.sin(math.pi * min(1.0, u)))
                for j in range(nu):
                    ph = 2 * math.pi * j / nu
                    zz = math.sin(ph) * hh * sz * k_ + rise * sz * u
                    yy = -math.cos(ph) * dd * max(k_, 0.25)
                    vs.append(c + np.array([x, yy, zz])); us.append((j / nu, u))
            fs = []
            for i in range(nw):
                for j in range(nu):
                    j2 = (j + 1) % nu
                    fs.append((i * nu + j, i * nu + j2, (i + 1) * nu + j2, (i + 1) * nu + j))
            add(vs, fs, us)
        else:
            # a lobe: an ellipsoid along x, tapering toward the knot, tilted up a touch, with a fold. With `end` (a share
            # of its length) its far end is closed round: the section shrinks by a quarter ellipse over that share to a
            # point (a fan), where the old open ring read as a straight cut with no line (Michael, 2026-09-30). `end_p`:
            # the cap's superellipse power (2 a quarter ellipse; higher, a flatter end with rounder corners, as drawn), or
            # [upper, lower]: the powers at the section's top and bottom, blended round it (the drawn loops' upper outer
            # corners are square, their lower ones round)
            u_rows = [(1 - math.cos(math.pi * i / nv)) / 2 for i in range(nv + 1)]
            if end:
                # the old rows up to the cap, then rows closing it (denser toward its tip)
                u_rows = [u for u in u_rows if u < 1 - end]
                u_rows += [1 - end + end * math.sin(0.5 * math.pi * q / 8) for q in range(8)]
            p_up, p_lo = (end_p, end_p) if np.isscalar(end_p) else end_p
            for i, u_ in enumerate(u_rows):
                th = math.acos(max(-1.0, min(1.0, 1 - 2 * u_)))      # 0 .. pi along the lobe
                k_up = k_lo = 1.0
                if end and u_ > 1 - end:
                    e_ = (u_ - (1 - end)) / end
                    k_up = max(0.0, 1 - e_ ** p_up) ** (1.0 / p_up)
                    k_lo = max(0.0, 1 - e_ ** p_lo) ** (1.0 / p_lo)
                for j in range(nu):
                    ph = 2 * math.pi * j / nu
                    k_ = k_lo + (k_up - k_lo) * 0.5 * (1 + math.sin(ph))
                    taper = (knot + (1 - knot) * math.sin(min(math.pi, th * 1.15)) ** 0.8) * k_
                    x = sx * (0.05 + (LOBE - 0.05) * u_) * sz
                    zz = math.sin(ph) * 0.20 * sz * taper + 0.05 * sz * u_
                    if drop and math.sin(ph) < 0:
                        zz += math.sin(ph) * drop * sz * u_ ** drop_p * k_
                    yy = -math.cos(ph) * depth * taper
                    fold = -0.03 * sz * math.exp(-((math.sin(ph) - 0.1) / 0.25) ** 2) * math.sin(th) * k_ \
                        if math.cos(ph) > 0 else 0.0
                    vs.append(c + np.array([x, yy - fold, zz])); us.append((j / nu, u_))
            nr_ = len(u_rows) - 1
            fs = []
            for i in range(nr_):
                for j in range(nu):
                    j2 = (j + 1) % nu
                    fs.append((i * nu + j, i * nu + j2, (i + 1) * nu + j2, (i + 1) * nu + j))
            if end:
                # the tip: a fan from the last ring to one point on the lobe's end
                tip = len(vs)
                vs.append(c + np.array([sx * (0.05 + (LOBE - 0.05)) * sz, 0.0, 0.05 * sz])); us.append((0.5, 1.0))
                fs += [(nr_ * nu + j, nr_ * nu + (j + 1) % nu, tip) for j in range(nu)]
            add(vs, fs, us)
        # a tail: a flat ribbon with thickness, out and down, widening, a V notch at the end (or, with `ribbon`, its
        # own width and spread and a slanted cut)
        M = 10
        vs, us = [], []
        rb = ribbon or {}
        w0, w1 = rb.get('w', (0.13, 0.22))
        out_, slant = rb.get('out', 0.2), rb.get('slant', None)
        ct, st = math.cos(math.radians(rb.get('turn', 0.0))), math.sin(math.radians(rb.get('turn', 0.0)))
        hinge = rb.get('hinge', 0.0)
        t0_ = len(verts)
        # root (sizes, default 0): each tail's top carried up this far behind the knot, as drawn (the tails come from
        # under it). Under a knot fitted to the drawn one (pleat's knot_box) the tops, TAIL0 under the centre, left a
        # hole below the knot and gaps by its corners where the jacket and the collar showed through: torn edges and
        # collar fragments (round 5, harness torndiag.py)
        root = rb.get('root', 0.0)
        rows_ = ([(0.0, root), (0.0, 0.3 * root)] if root else []) + [(i / M, 0.0) for i in range(M + 1)]
        if root:
            root_v.extend(range(len(verts), len(verts) + 12))    # (bow_hull sets them inside the knot after the wrap)
            seat_v.extend(range(len(verts) + 12, len(verts) + 18))   # ... and seats the top row (root_seat)
        for i, (s_, up) in enumerate(rows_):
            last = i == len(rows_) - 1
            p = c + np.array([sx * sz * (0.05 + out_ * s_), -0.01 * L * s_, -sz * (TAIL0 + tail * s_ - up)])
            w = sz * (w0 + (w1 - w0) * s_)
            if slant is None:
                notch = sz * 0.10 if last else 0.0
                cut = ((-w / 2, 0), (0, notch), (w / 2, 0))
            else:
                # the end cut on a slant: its outer corner `slant` sizes lower than its inner one
                d_ = slant * sz if last else 0.0
                cut = ((-w / 2, -d_ / 2 * sx), (0, 0.0), (w / 2, d_ / 2 * sx))
            for (dx, dz), dy in ((cut[0], -0.01 * L), (cut[1], -0.01 * L), (cut[2], -0.01 * L),
                                 (cut[2], 0.004 * L), (cut[1], 0.004 * L), (cut[0], 0.004 * L)):
                u_, y_ = dx * sx, dy + 0.003 * L                  # outward across the tail; depth from its mid-plane
                dx, dy = sx * (u_ * ct - y_ * st), u_ * st + y_ * ct - 0.003 * L - hinge * 0.5 * w * st
                vs.append(p + np.array([dx, dy, dz])); us.append((0.5, s_))
        fs = []
        for i in range(len(rows_) - 1):
            for k in range(6):
                k2 = (k + 1) % 6
                fs.append((i * 6 + k, i * 6 + k2, (i + 1) * 6 + k2, (i + 1) * 6 + k))
        add(vs, fs, us)
        tail_s.update(zip(range(t0_, len(verts)), np.repeat([r[0] for r in rows_], 6)))
    from .accessories import rounded_box
    kb = knot_box or (wing or {}).get('box', (0.19, 0.16, 0.24))     # the knot (sizes: wide, deep, tall)
    kv, kf = rounded_box(kb[0], kb[1], kb[2], kb[3] if len(kb) > 3 else 0.07, segs=2)   # (4th: the corners' radius)
    k0 = len(verts)
    add(list(kv * sz + c + np.array([0, -0.012 * L, 0.01 * sz])), kf, [(0.5, 0.5)] * len(kv))
    knot_v = np.arange(k0, len(verts))
    verts = np.array(verts)
    ts = np.full(len(verts), np.nan)
    for k, v in tail_s.items():
        ts[k] = v
    return dict(verts=verts, faces=faces, weights={'upperChest': np.ones(len(verts))}, uv=uvs, tail_s=ts, knot_v=knot_v,
                lobe_v=np.array(lobe_v, int) if lobe_v else None, root_v=np.array(root_v, int) if root_v else None,
                seat_v=np.array(seat_v, int) if seat_v else None)


def _ring_faces(nr, nu, vs, us, rows):
    """quads between nr rings of nu points, each end closed by a fan to its ring's mean (added to vs, us)."""
    fs = []
    for i in range(nr - 1):
        for j in range(nu):
            j2 = (j + 1) % nu
            fs.append((i * nu + j, i * nu + j2, (i + 1) * nu + j2, (i + 1) * nu + j))
    for i, u in ((0, rows[0]), (nr - 1, rows[-1])):
        ring = np.array(vs[i * nu:(i + 1) * nu])
        tip = len(vs)
        vs.append(ring.mean(0)); us.append((0.5, u))
        fs += [((i * nu + (j + 1) % nu), i * nu + j, tip) if i == 0 else (i * nu + j, i * nu + (j + 1) % nu, tip)
               for j in range(nu)]
    return fs


def _almond(P, sx, sz, depth, nu, top, bot, crease, ov, pinch, nw):
    """pleat.almond (dict, sizes): the drawn upper fold, an almond across the lobe's upper half from the knot (the
    design's, the breakdown's and the close-up's alike: two strokes meeting at points), as a thin lens standing `gap`
    in front of the panel's front, so its outline draws it (inverted hulls draw silhouettes only). Keys: u [from, to]
    along the lobe, f [at its ends] its middle's height above the lower edge as a share of the lobe's height, h its
    half-height, d its half-depth, gap. -> (verts, uvs, faces)."""
    A = P['almond']
    a0, a1 = A.get('u', (0.06, 0.5))
    f0, f1 = A.get('f', (0.66, 0.72))
    ah, ad, gap = A.get('h', 0.025), A.get('d', 0.012), A.get('gap', 0.004)
    rows = [a0 + (a1 - a0) * 0.5 * (1 - math.cos(math.pi * i / nw)) for i in range(nw + 1)]
    vs, us = [], []
    for u in rows:
        s_ = (u - a0) / max(1e-9, a1 - a0)
        t, b = top(u), crease(u) - ov
        zm, hh = 0.5 * (t + b), 0.5 * (t - b)
        dd = depth * (pinch + (1 - pinch) * math.sin(math.pi * min(0.999, 0.15 + 0.85 * u)) ** 0.5)
        yc = -P.get('cup', 0.0) * sz * u ** 0.7 - _bulge(P, u) * sz
        zc = bot(u) + (f0 + (f1 - f0) * s_) * (top(u) - bot(u))
        sn = max(-0.99, min(0.99, (zc - zm) / max(1e-9, hh)))
        yf = yc - math.sqrt(1 - sn * sn) * dd                   # the panel's front at the almond's height
        w = math.sin(math.pi * s_)
        h_, d_ = ah * w ** 0.7, max(0.15, w ** 0.5) * ad
        y0 = yf / sz - gap - d_ if sz else 0.0
        x = sx * (P.get('x0', 0.05) + (LOBE - P.get('x0', 0.05)) * u) * sz
        for j in range(nu):
            ph = 2 * math.pi * j / nu
            vs.append(np.array([x, (y0 - math.cos(ph) * d_) * sz, (zc + math.sin(ph) * h_) * sz]))
            us.append((j / nu, u))
    fs = _ring_faces(len(rows), nu, vs, us, rows)
    return vs, us, fs


def _smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def _bulge(P, u):
    """pleat.bulge [amount (sizes), u at its fullest]: how far forward the lobe puffs at u (0 at the knot .. 1 the outer
    end), sin(pi u^q)^2 with q putting its peak at the given u: nothing by the knot's sides (its outline there needs the
    lobes behind it) and in the outer end, so in profile the loops' middles stand round the knot as drawn."""
    b = P.get('bulge')
    if not b:
        return 0.0
    q = math.log(0.5) / math.log(min(0.95, max(0.05, b[1])))
    return b[0] * math.sin(math.pi * min(1.0, max(0.0, u)) ** q) ** 2


def _pleat_band(P, kind, sx, sz, depth, nu, nw=20):
    """one band of a pleated lobe (_bow_mesh's `pleat`), round the origin: 'panel' (above the crease line, in front) or
    'strip' (the fold's underside below it, behind), a ring of nu points per row along the lobe (u 0 at the knot .. 1 at
    the outer end), closed at both ends by a fan -> (verts, uvs, quad and triangle faces)."""
    x0 = P.get('x0', 0.05)
    hk, ht, hb = P.get('knot', 0.07), P.get('top', 0.22), P.get('bottom', 0.2)
    rise, sag, ov = P.get('rise', 0.0), P.get('sag', 0.05), P.get('overlap', 0.015)
    capw = P.get('cap', 0.15)
    pu, pl = P.get('end_p', (4.0, 1.4))
    pinch, step, thin = P.get('pinch', 0.4), P.get('step', 0.7), P.get('thin', 0.5)
    tp = P.get('top_p', 1.0)
    bp = P.get('bottom_p', 1.0)
    bot = lambda u: -(hk + (hb - hk) * u ** bp)                    # the lobe's lower edge
    top = lambda u: hk + (ht - hk) * u ** tp + rise * u             # ... and its upper edge
    cr = P.get('crease')
    if cr:
        # the crease its own line above the lower edge, [at the knot, at the outer end] as a share of the lobe's height
        # (crease_p: how late it falls from the one to the other): the strip below it shows as the drawn loop's lower
        # layer (the design's: a quarter of the height mid-lobe, closing at the lower outer corner), so the panel's
        # lower edge is inside the lobe's silhouette and its outline draws the crease
        cp = P.get('crease_p', 1.0)
        crease = lambda u: bot(u) + (cr[0] + (cr[1] - cr[0]) * u ** cp) * (top(u) - bot(u))
    else:
        crease = bot
    if kind == 'panel':
        zt = top
        zb = lambda u: crease(u) - ov
    elif cr:
        # the strip's lower edge the lobe's, closing onto the crease over `close` before the panel's end cap starts (the
        # drawn crease meets the lower outer corner)
        e0, e1 = 1 - capw - P.get('close', 0.2), 1 - capw
        g_ = lambda u: 1 - _smooth((u - e0) / max(1e-9, e1 - e0))
        # strip_ov (sizes, default overlap): the strip's top reaching this far up behind the panel (in three-quarter the
        # strip's step back opened a slit under the panel's lower edge by the tails, round 5); the panel keeps its edge
        sov = P.get('strip_ov', ov)
        zt = lambda u: crease(u) + sov
        hg = P.get('hang')
        # hang [amount, u, width] (sizes): the loop's lower layer hanging lower by the knot, behind the tails in front
        # (the drawn profile's loops reach a fifth lower than its front view's lobes show)
        hang = (lambda u: hg[0] * math.exp(-((u - hg[1]) / hg[2]) ** 2) * g_(u)) if hg else (lambda u: 0.0)
        zb = lambda u: crease(u) - (crease(u) - bot(u)) * g_(u) - ov * (1 - g_(u)) - sag * math.sin(math.pi * u) ** 0.8 \
            - hang(u)
    else:
        zt = lambda u: crease(u) + ov
        zb = lambda u: bot(u) - sag * math.sin(math.pi * u) ** 0.8
    if kind == 'almond':
        return _almond(P, sx, sz, depth, nu, top, bot, crease, ov, pinch, nw)
    zend = 0.5 * (top(1.0) + bot(1.0))                  # the outer end's middle (shear's pivot)
    tilt = P.get('tilt', 0.0)
    rows = [0.5 * (1 - math.cos(math.pi * i / nw)) * (1 - capw) for i in range(nw)]
    if kind == 'panel':
        rows += [1 - capw + capw * math.sin(0.5 * math.pi * q / 8) for q in range(9)]
    else:
        rows += [1 - capw]                  # the strip ends where the panel's end cap starts (no spur past its corner)
    vs, us = [], []
    for u in rows:
        e = max(0.0, (u - (1 - capw)) / capw) if kind == 'panel' else 0.0
        k_up = max(0.0, 1 - e ** pu) ** (1.0 / pu)
        k_lo = max(0.0, 1 - e ** pl) ** (1.0 / pl)
        t, b = zt(u), zb(u)
        zm, hh = 0.5 * (t + b), 0.5 * (t - b)
        # the half-depth: pinched at the knot, fullest past mid-lobe, thinning into the end's cap
        dd = depth * (pinch + (1 - pinch) * math.sin(math.pi * min(0.999, 0.15 + 0.85 * u)) ** 0.5)
        yc = (0.0 if kind == 'panel' else step * dd) - P.get('cup', 0.0) * sz * u ** 0.7   # cup: the ends forward
        yc -= _bulge(P, u) * sz
        if kind == 'strip':
            dd *= thin
        x = sx * (x0 + (LOBE - x0) * u) * sz
        # shear: the outer end leaning out at its top (the drawn ends slant, their upper corners furthest out), x moved
        # by shear * (height - the end's middle) over the lobe's outer part
        sh_ = P.get('shear', 0.0) * _smooth((u - 0.55) / 0.45)
        for j in range(nu):
            ph = 2 * math.pi * j / nu
            k_ = k_lo + (k_up - k_lo) * 0.5 * (1 + math.sin(ph))
            zs_ = zm + math.sin(ph) * hh * k_
            zz = zs_ * sz
            yy = yc - math.cos(ph) * dd * max(k_, 0.25)
            if kind == 'strip' and P.get('tuck'):
                # tuck [amount (sizes), u-width]: the lower layer's lower half brought forward by the knot, behind the
                # tails (they hang 0.02-0.04 L in front of it there: a slit between them in profile and the jacket
                # through the gap in three-quarter, round 5), none at its top (the panel keeps the crease's line)
                tk = P['tuck']
                yy -= tk[0] * sz * math.exp(-(u / tk[1]) ** 2) * (0.5 * (1 - math.sin(ph)))
            if kind == 'strip' and tilt:
                # tilt: the lower layer's bottom brought forward (tilt half-depths at its lower edge, none at the
                # crease): the panel still overlaps its top (the crease's line), its lower edge stands off the jacket
                # (its outline there: bow_front_bleed) and in profile the loops' lower rows come forward, as drawn
                yy -= tilt * dd / thin * (0.5 * (1 - math.sin(ph)))
            vs.append(np.array([x + sx * sh_ * (zs_ - zend) * sz, yy, zz])); us.append((j / nu, u))
    nr = len(rows)
    fs = []
    for i in range(nr - 1):
        for j in range(nu):
            j2 = (j + 1) % nu
            fs.append((i * nu + j, i * nu + j2, (i + 1) * nu + j2, (i + 1) * nu + j))
    for i, u in ((0, 0.0), (nr - 1, rows[-1])):
        ring = np.array(vs[i * nu:(i + 1) * nu])
        tip = len(vs)
        vs.append(ring.mean(0)); us.append((0.5, u))
        fs += [((i * nu + (j + 1) % nu), i * nu + j, tip) if i == 0 else (i * nu + j, i * nu + (j + 1) % nu, tip)
               for j in range(nu)]
    return vs, us, fs


# ------------------------------------------------------------------------------------------------------------------- collar
def surface_walk(V, N, p0, d0, step, n, bias=None):
    """walk along the body surface from p0 in direction d0 (kept on the local tangent plane, nudged by `bias` each step, e.g.
    gravity), snapping to the surface through the nearest vertex's tangent plane. -> (n + 1, 3) points."""
    pts = [p0]
    d = d0 / np.linalg.norm(d0)
    p = p0
    for _ in range(n):
        q = p + d * step
        i = int(np.argmin(((V - q) ** 2).sum(1)))
        nv = N[i]
        q = q - ((q - V[i]) @ nv) * nv                       # onto the tangent plane at the nearest vertex
        dn = q - p
        if bias is not None:
            dn = dn / max(1e-9, np.linalg.norm(dn)) + bias
        dn = dn - (dn @ nv) * nv
        d = dn / max(1e-9, np.linalg.norm(dn))
        p = q
        pts.append(p)
    return np.array(pts)


def collar(A, spec, normals=None, neckline=None):
    """a sailor collar that drapes: from the neckline, at each azimuth, a walk along the body surface outward and down
    (over the shoulders at the sides, down the chest in front, down the back behind) to a length by azimuth; a V opening at
    the front, a square flap behind; lifted by `offset`. The stripe runs `stripe` (a share of the length) in from its
    edge. The neckline: level at the neck bone's head plus `rise` L, or `neckline` (fn(azimuth) -> world z: the design's,
    collar_hull's), where the collar starts on the body at each azimuth; with `keep_edge` (default) each column's walk is
    shortened by how far below the level ring it starts, so the collar's outer edge stays. -> dict(verts, faces, weights,
    uv, edge (per face: 1 on the stripe))."""
    from .anime_head import raycast
    L = A['head']['L']
    V, F = A['verts'], A['faces']
    N = normals if normals is not None else vertex_normals(V, F)
    nb, _ = bone_seg(A, 'neck')
    z_ref = nb[2] + spec.get('rise', 0.0) * L
    keep = neckline is not None and spec.get('keep_edge', True)
    if neckline is None:
        neckline = lambda a: z_ref
    zs = np.array([float(neckline(a)) for a in np.linspace(-math.pi, math.pi, 73)])
    z_lo, z_hi = float(zs.min()), float(zs.max())
    cy = nb[1] + 0.02 * L
    vd, sd, bd = (spec.get(k, d) * L for k, d in (('v_depth', 0.62), ('side_depth', 0.30), ('back_depth', 0.5)))
    v_half = math.radians(spec.get('v_half', 36.0))
    near = (V[:, 2] > z_lo - 0.08 * L) & (V[:, 2] < z_hi + 0.08 * L) & (N[:, 2] > -0.45)
    # walk on the neck and torso only (the jaw's underside is close to the neck's front: never snap to the head)
    hw_ = A['weights'].get('head', np.zeros(len(V)))
    tor = (hw_ < 0.3) & (V[:, 2] < z_hi + 0.04 * L) & (V[:, 2] > z_lo - 1.2 * L) & (N[:, 2] > -0.45)   # no under-jaw
    Vt, Nt = V[tor], N[tor]
    T = np.array([(f[0], f[k], f[k + 1]) for f in F if all(near[v] for v in f) for k in range(1, len(f) - 1)])
    na, nr = spec.get('cols', 96), spec.get('rows', 12)

    def length(a):
        ab = abs(a)
        if ab < math.radians(80):
            return sd + (vd - sd) * max(0.0, 1 - ab / math.radians(80)) ** 1.2
        if ab < math.radians(120):
            return sd + (bd - sd) * max(0.0, (ab - math.radians(100)) / math.radians(20))
        return bd
    off = spec.get('offset', 0.03) * L
    grid = np.zeros((nr + 1, na, 3))
    for k in range(na):
        a = -math.pi + 2 * math.pi * (k + 0.5) / na
        d = np.array([math.sin(a), -math.cos(a), 0.0])
        o = np.array([0.0, cy, float(neckline(a))])
        t = raycast(o, d[None], V, T)[0] if len(T) else np.inf
        p0 = o + d * (t if np.isfinite(t) else 0.06 * L)
        ln = length(a)
        if keep:
            # a neckline below the level ring (rise) keeps the collar's outer edge where the ring's walk put it: each
            # column shorter by how much lower it starts (the back flap's square bottom stays level)
            ln = max(0.2 * ln, ln - max(0.0, z_ref - float(neckline(a))))
        path = surface_walk(Vt, Nt, p0, d * 0.7 + np.array([0, 0, -0.3]), ln / (nr * 2), nr * 2,
                            bias=np.array([0, 0, -0.25]))
        for j in range(nr + 1):
            i_ = int(np.argmin(((Vt - path[2 * j]) ** 2).sum(1)))
            grid[j, k] = path[2 * j] + Nt[i_] * off
    st0, st1 = spec.get('stripe', (0.72, 0.86))
    faces, edge = [], []
    if spec.get('v_edge', 'exact') == 'exact':
        # the V opening's edges as lines: each row resampled round from the V's edge on her left, by the back, to its
        # edge on her right (an open strip), rather than the V cut by whole quads, whose staircase edge read as a torn
        # lapel tip beside the neck
        m = na
        rows_ = []
        for j in range(nr + 1):
            av = min(v_half * (1 - j / nr), math.radians(60))
            phi = av + (2 * math.pi - 2 * av) * np.arange(m + 1) / m          # 0 the front, + her left, round the back
            u = (np.mod(phi + math.pi, 2 * math.pi) / (2 * math.pi)) * na - 0.5
            k0 = np.floor(u).astype(int)
            f = (u - k0)[:, None]
            rows_.append((1 - f) * grid[j, k0 % na] + f * grid[j, (k0 + 1) % na])
        verts = np.concatenate(rows_)
        uvs = [(i / m, j / nr) for j in range(nr + 1) for i in range(m + 1)]
        for j in range(nr):
            s_mid = (j + 0.5) / nr
            for i in range(m):
                faces.append((j * (m + 1) + i, j * (m + 1) + i + 1, (j + 1) * (m + 1) + i + 1, (j + 1) * (m + 1) + i))
                edge.append(1 if st0 <= s_mid <= st1 else 0)
    else:
        verts = grid.reshape(-1, 3)
        uvs = [(k / na, j / nr) for j in range(nr + 1) for k in range(na)]
        for j in range(nr):
            for k in range(na):
                a = -math.pi + 2 * math.pi * (k + 0.5) / na
                s_mid = (j + 0.5) / nr
                if abs(a) < v_half * (1 - s_mid) and abs(a) < math.radians(60):
                    continue                                       # the V opening
                k2 = (k + 1) % na
                faces.append((j * na + k, j * na + k2, (j + 1) * na + k2, (j + 1) * na + k))
                edge.append(1 if st0 <= s_mid <= st1 else 0)
    from .body import nearest
    nn = nearest(verts, V)
    W = {b: w[nn] for b, w in A['weights'].items() if w[nn].max() > 1e-4}
    return dict(verts=verts, faces=faces, weights=W, uv=uvs, edge=edge)


def collar_hull(A, spec, normals, hull):
    """collar() laid onto the hull's collar (conform): the sailor collar walked on the body as before, then each vertex
    moved along its normal onto the design's collar surface where the hull shows it (the back flap lies flat on the
    back, the lapels follow the neckline); `offset` L out from it."""
    P = _hull_points(hull, spec)
    L = A['head']['L']
    neckline = None
    if spec.get('neckline', 'hull') == 'hull':
        # seated where the design's collar starts on the body, per azimuth round the neck: its hull points' upper edge
        # (lower at the back and the sides than in front, on the neck's flare into the shoulders), not one level ring
        # round the neck, which rode up it like a turtleneck
        from .geom import loft
        nb, _ = bone_seg(A, 'neck')
        ax = loft.Axis((nb[0], nb[1], 0.0), (0, 0, -1), (0, -1, 0))
        top = hull_edge(P, ax, n=spec.get('neck_sectors', 36), q=spec.get('neck_q', 3.0), low=False,
                        smooth=spec.get('neck_smooth', 1.5), min_pts=spec.get('neck_min_pts', 10))
        drop = spec.get('neck_drop', 0.0) * L
        neckline = lambda a: top(a) - drop
    G = collar(A, spec, normals, neckline)
    V = conform(G['verts'], G['faces'], P, L, reach=spec.get('reach', 0.12), k=spec.get('conform_k', 8),
                smooth=spec.get('conform_smooth', 3))
    G['verts'] = V + vertex_normals(V, G['faces']) * spec.get('lift', 0.005) * L
    if spec.get('pad'):                       # (the jacket's shoulder pad under it: the same lift, so it lies on it)
        G['verts'] = shoulder_pad(A, G['verts'], G['faces'], spec['pad'])
    if isinstance(spec.get('over'), (list, tuple)):   # (lying over the layers under it: collar_drape)
        G['verts'] = collar_drape(A, G['verts'], G['faces'], dict(spec, thick=spec.get('thick', 0.012)), hull)
    return G


# ----------------------------------------------------------------------------------------------------------------- Blender
SHADE_MUL = (0.86, 0.80, 0.84)      # a garment's shade tone: its colour times this (a spec's 'shade' replaces it)
DEEP_MUL = (0.70, 0.62, 0.70)       # the deep tone, kept in this ratio to the shade's


def _muls(shade_mul=None):
    """(shade, deep) multipliers: the defaults, or a garment's own shade with the deep tone in the defaults' ratio."""
    if shade_mul is None:
        return SHADE_MUL, DEEP_MUL
    sm = np.asarray(shade_mul, float)
    return tuple(sm), tuple(sm * np.array(DEEP_MUL) / np.array(SHADE_MUL))


def _toon(name, color, shade_mul=None):
    from . import shade
    c = np.asarray(color, float)
    sm, dm = _muls(shade_mul)
    return shade.toon3(name, tuple(c), tuple(c * np.array(sm)), tuple(c * np.array(dm)))


def _toon_tex(name, image, shade_mul=None):
    """toon3 whose three tones come from a texture (multiplied for the shadow tones)."""
    from . import shade
    sm, dm = _muls(shade_mul)
    m = shade.toon3(name, (1, 1, 1), sm, dm)
    nt = m.node_tree
    tx = nt.nodes.new('ShaderNodeTexImage'); tx.image = image; tx.interpolation = 'Linear'; tx.extension = 'EXTEND'
    uv = nt.nodes.new('ShaderNodeUVMap'); uv.uv_map = 'uv'
    nt.links.new(uv.outputs[0], tx.inputs['Vector'])
    em = next(n for n in nt.nodes if n.type == 'EMISSION')
    src = em.inputs['Color'].links[0].from_socket
    mul = nt.nodes.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'
    mul.inputs['Factor'].default_value = 1.0
    nt.links.new(src, mul.inputs['A']); nt.links.new(tx.outputs['Color'], mul.inputs['B'])
    nt.links.new(mul.outputs['Result'], em.inputs['Color'])
    return m


def group_weights(w):
    """a bone's weights as a garment's vertex group holds them: to 3 decimals, 1e-4 and under left out (0), over 1
    clamped (as vertex_groups.add clamps). The venv's final meshes carry these through the Subdivision (call J)."""
    r = np.round(np.asarray(w, float), 3)
    return np.clip(np.where(r > 1e-4, r, 0.0), 0.0, 1.0)


def _object(name, verts, faces, weights, arm, mats, uv=None, uv_corner=None, mat_idx=None, smooth=True, wound=False,
            final=False, layer=None):
    """a garment piece as a rigged mesh object. Its faces are wound as charkit.geom.wind.orient decides (each region
    consistent, its normals out): the garments product's recording winds them venv-side and passes wound=True, so
    Blender takes them as given (GEOM_TRUTH step 7a); the in-Blender path winds them here with the same function.
    final: the venv's final mesh at rest (geomstage.finalize, call J): its weights already group_weights' carried
    through the Subdivision, taken as they are; layer: per face 0 the surface, 1 the Solidify's inner copy, 2 its rim
    (the face attribute 'ck_layer': the QA's poke-through reads the surface)."""
    from . import character
    if not wound:
        from .geom import wind
        faces, uv_corner = wind.orient(verts, faces, uv_corner)[:2]
    ob = character._mesh(name, verts, faces, None, mats)
    me = ob.data
    if uv is not None or uv_corner is not None:
        lay = me.uv_layers.new(name='uv')
        if uv_corner is not None:                               # (from_pydata keeps the polygons' corners in order)
            U = np.concatenate([np.asarray(c, np.float32).reshape(-1, 2) for c in uv_corner])
        else:
            lv = np.empty(len(me.loops), np.int32); me.loops.foreach_get('vertex_index', lv)
            U = np.asarray(uv, np.float32)[lv]
        lay.data.foreach_set('uv', U.ravel())
    me.polygons.foreach_set('use_smooth', np.full(len(me.polygons), bool(smooth)))
    if mat_idx is not None:
        me.polygons.foreach_set('material_index', np.asarray(mat_idx, np.int32))
    if layer is not None:
        me.attributes.new('ck_layer', 'INT', 'FACE').data.foreach_set('value', np.asarray(layer, np.int32))
    for b, w in weights.items():
        if b not in arm.data.bones and b != OUTLINE_W:
            continue
        g = ob.vertex_groups.new(name=b)
        wr = np.clip(np.asarray(w, float), 0.0, 1.0) if final else group_weights(w)
        vals, inv = np.unique(wr, return_inverse=True)
        order = np.argsort(inv, kind='stable')
        for k, idx in enumerate(np.split(order, np.cumsum(np.bincount(inv, minlength=len(vals)))[:-1])):
            if vals[k] > (0.0 if final else 1e-4):
                g.add(idx.tolist(), float(vals[k]), 'REPLACE')
    mod = ob.modifiers.new('rig', 'ARMATURE'); mod.object = arm
    ob.parent = arm
    return ob


COLLAR_TEMPLATE = dict(       # the template collar's shell (build: kind 'collar', source 'template'), under its own knobs
    region=[['neck', -1, 0.6], ['upperChest', -1, 3], ['chest', -1, 3], ['spine', -1, 3], ['leftShoulder', -1, 3],
            ['rightShoulder', -1, 3]],
    offset=0.03, thick=0.005)
RIM_CREASE = 1.0    # a thin shell's open rim kept flat and square under the Subdivision (Michael's call L; 0: rounded)


def _thick(ob, t):
    """a garment's thickness: a SOLIDIFY t (m) inward from its surface (offset -1) with a rim across each open edge,
    both layers' open borders creased (edge_crease_outer: the surface's, edge_crease_inner: the inner layer's), so the
    Subdivision after it keeps the rim a flat band meeting the layers square (Michael's call L). Uncreased, the
    Subdivision rounds the rim into a bead of about a third of the shell, which the outline's inward move (up to half the
    shell, call I) turns inside out: every rim face flipped (charkit/boards/lookprobe.py --normals). The rim's own
    cross edges stay smooth, so the hem line keeps its curve along the edge. charkit.bodyeval's solidify/subdivide read
    the same creases."""
    sol = ob.modifiers.new('thick', 'SOLIDIFY'); sol.thickness = t; sol.offset = -1; sol.use_rim = True
    if RIM_CREASE:
        sol.edge_crease_inner = RIM_CREASE; sol.edge_crease_outer = RIM_CREASE
    return sol


LINE_CAP_MEASURED = ('bow', 'boot')   # closed thin pieces (no shell modifier) whose outline's inward move is capped at
                                      # half their measured thickness (shade.outline's cap='measured'; Michael's call M)


def build(C, specs, line=(0.30, 0.18, 0.16), hull=None, spec_all=None):
    """Blender objects for an outfit on a built character C (charkit.character.build): each garment rigged to C's armature,
    toon-shaded and outlined; the body under the tight shells masked away. hull: hull_pieces()' points, for the garments
    whose `source` is 'hull'. -> [objects]."""
    from . import eyetex, shade
    A, arm, skin = C['data'], C['arm'], C['skin']
    L = A['head']['L']
    from .geom import loft as _loft
    nrm = vertex_normals(A['verts'], A['faces'])
    hide = np.zeros(len(A['verts']), bool)
    obs = []
    _loft.LOW_COVERAGE.clear()
    for s in specs or []:
        k, nm = s['kind'], s['name']
        col = s.get('color', (0.8, 0.8, 0.8))
        sh = s.get('shade')                                         # its own shade multiplier (else SHADE_MUL)
        if k == 'shell':
            G = shell(A, dict(s, _spec=spec_all), nrm, hull)
            mats = [_toon(nm, col, sh)]
            midx = None
            if 'sole' in s:                                           # boots: the bottom as a dark sole
                mats.append(_toon(nm + '_sole', s['sole']['color'], sh))
                zmin = G['verts'][:, 2].min()
                midx = [1 if G['verts'][list(f), 2].max() < zmin + s['sole']['height'] * L else 0 for f in G['faces']]
            uvc = G['uvs']
            if 'panel_faces' in G:                                    # the hull's panel: a second material by face
                mats.append(_toon(nm + '_panel', (s.get('stripe') or s.get('panel'))['color'], sh))
                midx = [int(v) for v in G['panel_faces']]
            elif 'panel' in s:                                        # a front panel in another colour (a bib, a placket)
                # a front-projected UV and a mask texture: a smooth-edged panel on the front, the plain colour elsewhere
                P_ = s['panel']
                cyf = A['head']['centre'][1]
                zlo, zhi = panel_inside(A, P_, 0.0, 0.0)[1]
                n_ = 512
                U_, V_ = np.meshgrid((np.arange(n_) + 0.5) / n_, ((np.arange(n_) + 0.5) / n_)[::-1])
                X_ = (U_ - 0.5) * L; Z_ = zlo + V_ * (zhi - zlo)
                inside_ = panel_inside(A, P_, X_, Z_)[0]
                tex = np.empty((n_, n_, 4)); tex[..., 3] = 1
                tex[..., :3] = np.where(inside_[..., None], np.array(P_['color']), np.array(col))
                img = eyetex.to_blender_image(nm + '_panel', tex)
                mats[0] = _toon_tex(nm + '_tex', img, sh)
                uvc = []
                for f in G['faces']:
                    front = G['verts'][list(f)].mean(0)[1] < cyf + 0.02
                    uvc.append([((G['verts'][v][0] / L + 0.5) if front else 5.0,
                                 (G['verts'][v][2] - zlo) / (zhi - zlo)) for v in f])
            ob = _object(nm, G['verts'], G['faces'], G['weights'], arm, mats, uv_corner=uvc, mat_idx=midx)
            _thick(ob, s.get('thick', 0.008) * L)
            # mask the body under it, but keep its border vertices (so no gap shows at the hem)
            src = G['src']; inside = np.zeros(len(A['verts']), bool); inside[src] = True
            border = set()
            for f in A['faces']:
                if any(inside[v] for v in f) and not all(inside[v] for v in f):
                    border.update(f)
            for v in src:
                if v not in border:
                    hide[v] = True
        elif k == 'band' and s.get('source') == 'template':
            G = cuff(A, s)
            mats = [_toon(nm, col, sh), _toon(nm + '_trim', s.get('trim_color', (0.97, 0.9, 0.72)), sh)]
            ob = _object(nm, G['verts'], G['faces'], G['weights'], arm, mats, uv=G['uv'], mat_idx=G['trim'])
            _thick(ob, s.get('thick', 0.02) * L)
        elif k == 'band':
            G = band_hull(A, s, hull) if s.get('source') == 'hull' else band(A, s)
            ob = _object(nm, G['verts'], G['faces'], G['weights'], arm, [_toon(nm, col, sh)], uv=G['uv'])
            if s.get('source') == 'hull':                            # the loft is the band's outside: its thickness
                _thick(ob, s.get('thick', 0.02) * L)
        elif k == 'shoe':
            G = shoe_hull(A, dict(s, _spec=spec_all), hull) if s.get('source') == 'hull' else shoe(A, s)
            mats = [_toon(nm, col, sh), _toon(nm + '_sole', s.get('sole_color', (0.26, 0.21, 0.21)), sh)]
            ob = _object(nm, G['verts'], G['faces'], G['weights'], arm, mats, uv=G['uv'], mat_idx=G['sole'])
            # the body's foot is inside it: mask it
            dom_, _ = dominant(A)
            for b_ in (f"{s['side']}Foot", f"{s['side']}Toes"):
                hide[np.nonzero(dom_ == b_)[0]] = True
        elif k == 'boot':
            G = boot(A, dict(s, _spec=spec_all))
            mats = [_toon(nm, col, sh), _toon(nm + '_sole', s.get('sole_color', (0.26, 0.21, 0.21)), sh)]
            ob = _object(nm, G['verts'], G['faces'], G['weights'], arm, mats, uv=G['uv'], mat_idx=G['sole'])
            hide[G['hide']] = True                              # the body's leg and foot inside it
        elif k == 'belt':
            G = belt_hull(A, s, hull) if s.get('source') == 'hull' else belt(A, s)
            ob = _object(nm, G['verts'], G['faces'], G['weights'], arm, [_toon(nm, col, sh)], uv=G['uv'])
            if 'hide' in G:
                hide[G['hide']] = True
            if s.get('source') == 'hull':                            # the loft is the band's outside: give it a thickness
                _thick(ob, s.get('thick', 0.025) * L)
        elif k == 'sleeve':
            G = puff(A, dict(s, _spec=spec_all), hull) if s.get('source') == 'template' else \
                sleeve_hull(A, s, hull) if s.get('source') == 'hull' else sleeve(A, s)
            ob = _object(nm, G['verts'], G['faces'], G['weights'], arm, [_toon(nm, col, sh)], uv=G['uv'])
            _thick(ob, 0.008 * L)
        elif k == 'skirt':
            G = skirt_hull(A, dict(s, _spec=spec_all), hull) if s.get('source') == 'hull' else skirt(A, s)
            pw = G.get('panel_half', s.get('panel', 0.0)) / (2 * math.pi)
            tex = stepped_hem(colors=(col, s.get('hem_color', (0.28, 0.2, 0.18))), panel=(0.5 - pw, 0.5 + pw),
                              repeat=s.get('repeat', 8), pleats=s.get('pleats', 24), dark='band' not in G)
            img = eyetex.to_blender_image(nm + '_tex', tex)
            mats = [_toon_tex(nm, img, sh), _toon(nm + '_panel', s.get('panel_color', col), sh)]
            midx = G['panel']
            if 'band' in G:                                            # the band as geometry (band_rows)
                mats.append(_toon(nm + '_band', s.get('hem_color', (0.28, 0.2, 0.18)), sh))
                midx = [2 if b_ else p_ for p_, b_ in zip(G['panel'], G['band'])]
            G, mats, midx = with_ink(G, s, mats, midx, L, line, (0.0, _eye_z(A)))   # its creases (the panel's folds)
            ob = _object(nm, G['verts'], G['faces'], G['weights'], arm, mats, uv=G['uv'], mat_idx=midx)
            _thick(ob, 0.01 * L)
        elif k == 'collar' and s.get('source') == 'template':
            # the sailor collar as a template (tool/collar): a shell over the neck's base, the shoulders and the upper
            # back and chest, cut to its outline (outline_dist: the lapels' V in front, the square back panel), its
            # stripe a band in from the outline's edge in a second material; it lies over the jacket (`offset`)
            G = shell(A, dict(COLLAR_TEMPLATE, **s, _spec=spec_all), nrm, hull)
            st_ = s.get('stripe') or {}
            mats = [_toon(nm, col, sh), _toon(nm + '_stripe', st_.get('color', s.get('stripe_color', (0.3, 0.2, 0.18))), sh)]
            ob = _object(nm, G['verts'], G['faces'], G['weights'], arm, mats, uv_corner=G['uvs'],
                         mat_idx=[int(v) for v in G.get('panel_faces', np.zeros(len(G['faces']), int))])
            _thick(ob, s.get('thick', 0.005) * L)
            src = G['src']; inside = np.zeros(len(A['verts']), bool); inside[src] = True
            if G.get('hide_also') is not None:                       # (the body under the unlifted outline: shell)
                inside[G['hide_also']] = True
                src = np.nonzero(inside)[0]
            border = set()
            for f in A['faces']:
                if any(inside[v] for v in f) and not all(inside[v] for v in f):
                    border.update(f)
            ks_ = G.get('keep_skin') or ()
            for v in src:
                if v not in border and v not in ks_:
                    hide[v] = True
        elif k == 'collar' and s.get('source') == 'hull':
            G = collar_hull(A, dict(s, _spec=spec_all), nrm, hull)
            mats = [_toon(nm, col, sh), _toon(nm + '_stripe', s.get('stripe_color', (0.3, 0.2, 0.18)), sh)]
            ob = _object(nm, G['verts'], G['faces'], G['weights'], arm, mats, uv=G['uv'], mat_idx=G['edge'])
            _thick(ob, 0.012 * L)
        elif k == 'collar':
            G = collar(A, s, nrm)
            mats = [_toon(nm, col, sh), _toon(nm + '_stripe', s.get('stripe_color', (0.3, 0.2, 0.18)), sh)]
            ob = _object(nm, G['verts'], G['faces'], G['weights'], arm, mats, uv=G['uv'], mat_idx=G['edge'])
            _thick(ob, 0.012 * L)
        elif k == 'bow' and s.get('source') == 'hull':
            G = bow_hull(A, dict(s, _spec=spec_all), hull)
            G, mats, midx = with_ink(G, s, [_toon(nm, col, sh)], None, L, line, (0.0, _eye_z(A)))   # its wrinkles
            ob = _object(nm, G['verts'], G['faces'], G['weights'], arm, mats, uv=G['uv'], mat_idx=midx)
        elif k == 'bow':
            G = bow(A, s)
            ob = _object(nm, G['verts'], G['faces'], G['weights'], arm, [_toon(nm, col, sh)], uv=G['uv'])
        elif k == 'panel':
            if s.get('source') == 'flap':
                G = flap(A, dict(s, _spec=spec_all), hull)
            else:
                G = panel_hull(A, s, hull) if s.get('source') == 'hull' else panel(A, s)
            midx = None
            if 'band' in G:                                         # the band as geometry (flap_template)
                mats = [_toon(nm, col, sh), _toon(nm + '_band', s.get('hem_color', (0.28, 0.2, 0.18)), sh)]
                midx = [int(b_) for b_ in G['band']]
            elif s.get('hem') == 'stepped':
                tex = stepped_hem(colors=(col, s.get('hem_color', (0.28, 0.2, 0.18))), repeat=s.get('repeat', 1),
                                  steps=s.get('steps', 6), **{k_: s[k_] for k_ in ('band', 'step_h') if k_ in s})
                mats = [_toon_tex(nm, eyetex.to_blender_image(nm + '_tex', tex), sh)]
            else:
                mats = [_toon(nm, col, sh)]
            ob = _object(nm, G['verts'], G['faces'], G['weights'], arm, mats, uv=G['uv'], mat_idx=midx)
            _thick(ob, 0.01 * L)
        else:
            raise ValueError(k)
        if G.get('subdiv', 1):                                   # (a template with crisp corners asks for none)
            sub = ob.modifiers.new('sub', 'SUBSURF'); sub.levels = 1; sub.render_levels = 1
        shade.outline(ob, thick=s.get('line', 0.0012), color=line, name='garment_line',
                      **({'cap': 'measured'} if k in LINE_CAP_MEASURED else {}))
        if _loft.LOW_COVERAGE:                                   # built from marginal hull coverage: kept as a number
            ob['charkit_coverage'] = min(_loft.LOW_COVERAGE)
            print('garments: %s lofted from marginal hull coverage (its best row measured on %.0f%% of its circle)'
                  % (nm, 100 * min(_loft.LOW_COVERAGE)))
            _loft.LOW_COVERAGE.clear()
        obs.append(ob)
    if hide.any():
        mask_skin(skin, no_loose(hide, A['faces']))
    return obs


def no_loose(hide, faces):
    """the hidden vertices plus those the mask would leave in no face (every face on them dropped: a face goes when any
    of its vertices does): Blender's Mask keeps them, with the edges between them, as loose geometry, and its
    Subdivision Surface evaluates loose vertices and edges on a threaded path whose last bit varies from one evaluation
    to the next (k, docs/workstreams/infra5.md: clawd_mh's 65 loose vertices, 1 float32 ulp, 7-18 of them per read; with
    -t 1 or no loose geometry, bit-identical). Nothing renders there. The default spec's mask leaves none (unchanged).
    -> (N,) bool."""
    hide = np.asarray(hide, bool)
    if not len(faces):
        return hide
    cnt = np.array([len(f) for f in faces], np.int64)
    lv = np.concatenate([np.asarray(f, np.int64) for f in faces])
    fkeep = np.logical_and.reduceat(~hide[lv], np.r_[0, np.cumsum(cnt)[:-1]])
    used = np.zeros(len(hide), bool)
    used[lv[np.repeat(fkeep, cnt)]] = True
    return hide | ~used


def mask_skin(skin, hide):
    """the body under the garments masked away: the hidden vertices in the skin's 'under_garments' group, a Mask modifier
    first in its stack."""
    g = skin.vertex_groups.new(name='under_garments')
    g.add([int(i) for i in np.nonzero(hide)[0]], 1.0, 'REPLACE')
    mk = skin.modifiers.new('under_garments', 'MASK'); mk.vertex_group = 'under_garments'; mk.invert_vertex_group = True
    while skin.modifiers.find('under_garments') > 0:              # first in the stack
        import bpy
        with bpy.context.temp_override(object=skin):
            bpy.ops.object.modifier_move_up(modifier='under_garments')
