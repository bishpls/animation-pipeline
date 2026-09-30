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
    body's), src (body vertex per shell vertex), faces_src (body face index per face))."""
    L = A['head']['L']
    V, F = A['verts'], A['faces']
    ins = region(A, spec['region'])
    cut = None
    if spec.get('source') == 'hull':
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
        h, tl = bone_seg(A, bone)
        zc = (h + (tl - h) * t)[2] + o * L
        ins &= (V[:, 2] >= zc) if side == 'above' else (V[:, 2] <= zc)
    ez = spec.get('ease')
    band = None
    if ez and hull is not None:
        bs = next((g for g in (spec.get('_spec') or {}).get('garments', []) if g['name'] == ez.get('under', 'waistband')),
                  None)
        if bs is not None:
            band = (bs, belt_hull(A, bs, hull))
            # its hem stays under the band: a dropped hem hung out below the band's lower edge at the front
            ins &= V[:, 2] >= band[1]['verts'][:, 2].min() + ez.get('above_bottom', 0.03) * L
    keep = [i for i, f in enumerate(F) if all(ins[v] for v in f)]
    used = sorted({v for i in keep for v in F[i]})
    remap = {o: n for n, o in enumerate(used)}
    nrm = normals if normals is not None else vertex_normals(V, F)
    off = spec.get('offset', 0.012) * L
    sv = V[used] + nrm[used] * off
    sf = [tuple(remap[v] for v in F[i]) for i in keep]
    if spec.get('hem_snap') and cut is not None:
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
    if band is not None:
        sv = ease_to_band(A, sv, ez, band)
    W = {b: w[used] for b, w in A['weights'].items() if w[used].max() > 1e-4}
    B = A['body']
    uvs = [[B['uvs'][ui] for ui in B['face_uv'][i]] for i in keep]
    G = dict(verts=sv, faces=sf, weights=W, uvs=uvs, src=np.array(used), faces_src=keep)
    if spec.get('source') == 'hull' and 'panel' in spec and hull and spec['panel'].get('mode') != 'texture':
        pp = hull.get(spec['panel'].get('piece', 'bodice_panel'))
        if pp is not None and len(pp) >= 10:
            G['panel_faces'] = panel_faces(sv, sf, pp, L)
    return G


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
    inward: the hull's section can sit inside the limb, and the skin showed through. Rigid on its bone.
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
    skirt's), `width` tall, lifted by `offset`, with a rounded face. Weighted to the hips. -> dict(verts, faces, weights,
    uv)."""
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
    return dict(verts=verts, faces=faces, weights={'hips': np.ones(len(verts))}, uv=uvs)


# ---------------------------------------------------------------------------------------------------- the hull's pieces
def hull_pieces(spec, A, source='shell'):
    """the visual hull's outfit pieces as world points on this character: the generated shape (the spec's hair.shape.glb,
    charkit.geom.hull's), aligned by its eyes as the build aligns its target (i3d.eye_target, i3d.align_by_eyes)
    -> {piece id: (n, 3)}, or None when the shape carries no pieces. The points are its labelled shell (hull.npz beside
    it: shell_points, one per surface voxel of the occupancy, on a regular grid), not the mesh's vertices: the mesh is
    decimated, and which vertices a decimation keeps (denser at curvature, fewer on flat stretches) moved the lofts'
    per-cell quantiles, hems and arcs (tool/hull-det's deterministic solve kept the skirt's width at every height to
    three decimals, yet its A-line check went -0.016 -> -0.133). source 'mesh' (or a hull without its labelled shell):
    the decimated mesh's vertices split by the per-vertex pieces the sidecar names, as before. Names come from the
    sidecar either way."""
    import json, os
    from . import i3d
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
    eye_mid, spacing = i3d.eye_target(A, shape)
    W = i3d.align_by_eyes(V, (np.asarray(J['eyes'][0], float), np.asarray(J['eyes'][1], float)), eye_mid, spacing)
    return {pid: W[lab == int(k)] for k, pid in (J.get('piece_names') or {}).items() if (lab == int(k)).any()}


STRAY = (0.05, 0.0064)     # a piece's label patch dropped as stray: under this share of its largest patch and this area
                           # (L^2; 64 voxels at the hull's 0.01 L). The views' labels leave small patches round a piece
                           # (a wrist cuff's up the forearm, a boot cuff's out on the skirt): a decimated mesh gave
                           # their flat stretches few vertices, but on the shell they count by area and moved the bands'
                           # spans and radii (wrist_R's start 0.055 L up the arm, boot_cuff_L's radius 0.27 -> 0.37 L)


def shell_points(Z, stray=STRAY):
    """the hull's labelled shell as points on its surface (hull.npz, charkit.geom.hull.build's: the occupancy V on the
    axes xs, ys, zs, its shell voxels' indices and their labels): per shell voxel (occupied, with an empty face
    neighbour; outside the grid is empty), the mean of the centres of its faces toward empty neighbours, so each point
    lies on the occupancy's boundary (where the mesh's surface is, within half a voxel: the mesh is that boundary
    blurred a voxel; median offset -0.0001 L on Clawd), one point per labelled voxel whatever the mesh's decimation.
    stray (share, area L^2): a label's patches (shell_patches) under both are left out (None keeps them). Numpy only (the
    build's Python has no scipy). -> (P (n, 3) in the hull's frame, labels (n,))."""
    V = np.asarray(Z['V'], bool)
    S = np.asarray(Z['shell'], np.int64)
    lab = np.asarray(Z['shell_label'])
    ax = [np.asarray(Z[k], float) for k in ('xs', 'ys', 'zs')]
    C = np.stack([ax[k][S[:, k]] for k in range(3)], 1)
    Vp = np.pad(V, 1)
    I = S + 1
    off = np.zeros_like(C)
    n = np.zeros(len(C))
    for k in range(3):
        step = ax[k][1] - ax[k][0]                               # the index's step in the frame (zs runs down)
        for sgn in (-1, 1):
            J = I.copy()
            J[:, k] += sgn
            empty = ~Vp[J[:, 0], J[:, 1], J[:, 2]]
            off[:, k] += np.where(empty, 0.5 * sgn * step, 0.0)
            n += empty
    P = C + off / np.maximum(n, 1)[:, None]
    if stray:
        size, largest = shell_patches(S, lab)
        h = abs(ax[0][1] - ax[0][0])
        keep = (size >= stray[0] * largest) | (size * h * h >= stray[1])
        P, lab = P[keep], lab[keep]
    return P, lab


def shell_patches(S, lab):
    """each shell voxel's patch: the voxels of its label it connects to (26-neighbours) -> (the patch's size, the size of
    its label's largest patch), per voxel. Numpy union-find: roots hooked to the least root they touch, then paths
    compressed, until every neighbour pair shares a root."""
    S = np.asarray(S, np.int64)
    n = len(S)
    if not n:
        return np.zeros(0, np.int64), np.zeros(0, np.int64)
    dim = S.max(0) + 3
    key = ((S[:, 0] + 1) * dim[1] + S[:, 1] + 1) * dim[2] + S[:, 2] + 1
    order = np.argsort(key, kind='stable')
    ks = key[order]
    a, b = [], []
    for d in [(i, j, k) for i in (-1, 0, 1) for j in (-1, 0, 1) for k in (-1, 0, 1) if (i, j, k) > (0, 0, 0)]:
        q = key + (d[0] * dim[1] + d[1]) * dim[2] + d[2]
        pos = np.minimum(np.searchsorted(ks, q), n - 1)
        hit = ks[pos] == q
        i_, j_ = np.nonzero(hit)[0], order[pos[hit]]
        same = lab[i_] == lab[j_]
        a.append(i_[same]); b.append(j_[same])
    a, b = np.concatenate(a), np.concatenate(b)
    root = np.arange(n)
    while True:
        ra, rb = root[a], root[b]
        diff = ra != rb
        if not diff.any():
            break
        np.minimum.at(root, np.maximum(ra, rb)[diff], np.minimum(ra, rb)[diff])
        while True:
            r2 = root[root]
            if (r2 == root).all():
                break
            root = r2
    size = np.bincount(root, minlength=n)[root]
    largest = np.zeros(int(lab.max()) - int(lab.min()) + 1, np.int64)
    np.maximum.at(largest, lab - lab.min(), size)
    return size, largest[lab - lab.min()]


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
    ez = A['head']['centre'][2] + A['head']['eye_knobs']['z'] * L
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
    a quarter of the way down. Weighted to the hips. -> dict(verts, faces, weights, uv, axis, ts, th, R)."""
    from .geom import loft
    L = A['head']['L']
    P = _hull_points(hull, spec)
    top_z = P[:, 2].max()
    ax = _vertical_axis(P, top_z)
    t, th, r = ax.coords(P)
    # L from the eye line -> t along the axis (read only when the spec gives rows by height)
    tz = lambda z: top_z - (A['head']['centre'][2] + A['head']['eye_knobs']['z'] * L + z * L)
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
    return dict(verts=V, faces=quads, weights={'hips': np.ones(len(V))}, uv=[tuple(x) for x in uv],
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
    off = spec.get('offset', 0.0) * L
    pleats = spec.get('pleats', 24); depth = spec.get('pleat', 0.05) * L
    TH = F.th[None, :]; VV = vs[:, None]
    ph = (TH + np.pi) / (2 * np.pi) * pleats
    zig = np.abs((ph % 1.0) - 0.5) * 2 - 0.5
    R = F.R + off + depth * zig * VV ** 0.7
    T = t0_at(TH) + VV * (hem_at(TH) - t0_at(TH))
    clear_info = None
    if spec.get('clear_hands'):
        R, clear_info = clear_arms(A, spec, hull, ax, T, np.broadcast_to(TH, T.shape), R)
    verts = ax.point(T, np.broadcast_to(TH, T.shape), R).reshape(-1, 3)
    faces = [(i * n + k, i * n + (k + 1) % n, (i + 1) * n + (k + 1) % n, (i + 1) * n + k)
             for i in range(rows) for k in range(n)]
    uvs = [((k + 0.5) / n, i / rows) for i in range(rows + 1) for k in range(n)]
    # the front panel: the skirt_panel's points' angular spread, else the knob
    pan_pts = hull.get('skirt_panel') if hull else None
    if pan_pts is not None and len(pan_pts) > 20:
        half = dense_arc(ax.coords(pan_pts)[1], spec.get('panel_mass', 0.8))[1]    # its densest arc (stray labels
                                                                                     # widened a percentile to 58 deg)
    else:
        half = spec.get('panel', 0.0)
    pan = [1 if abs(F.th[k]) < half else 0 for i in range(rows) for k in range(n)]
    vv = np.repeat(vs, n)
    sx = np.clip(verts[:, 0] / (0.08 * L), -1, 1)
    leg = 0.65 * vv ** 1.4
    Wt = {'hips': 1 - leg, 'leftUpperLeg': leg * (1 + sx) / 2, 'rightUpperLeg': leg * (1 - sx) / 2}
    return dict(verts=verts, faces=faces, weights=Wt, uv=uvs, panel=pan, z_waist=float(top - np.median(t0_at(F.th))),
                panel_half=half, axis=ax, grid=(rows + 1, n), clear=clear_info)


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
    sk = next((g for g in whole.get('garments', []) if g['name'] == spec.get('over', 'skirt')), None)
    if not sk or sk.get('source') != 'hull':
        raise ValueError('%s: a flap lies on a hull skirt (%s)' % (spec['name'], spec.get('over', 'skirt')))
    Gs = skirt_hull(A, dict(sk, _spec=whole), hull)
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
    Gs = skirt_hull(A, dict(sk, _spec=whole), hull)
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
                (0.28, 0.20, 0.18)), pleats=0):
    """RGBA texture for a skirt: the body colour with a dark band along the hem (v = 1) whose top edge rises and falls in
    pixel steps (a stair pattern repeated `repeat` times round the skirt); panel: optional (u0, u1) where no band is drawn."""
    u = (np.arange(n) + 0.5) / n
    U, Vv = np.meshgrid(u, u[::-1])
    ph = (U * repeat) % 1.0
    tri = 1 - np.abs(ph - 0.5) * 2                         # 0 .. 1 .. 0 across each repeat
    stair = np.floor(tri * steps) / steps                  # quantised: steps
    edge = 1 - band - stair * step_h * steps / 2
    dark = Vv >= edge
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
    # clear of the skin inside it (the wrist, the hand's base): a row whose section comes within `clear` L plus its
    # thickness of the limb's skin at some angle grows as a whole (its shape kept, so the sides stay straight)
    dom, _ = dominant(A)
    Q = A['verts'][np.isin(dom, limb_neighbours(bone))] - h
    if len(Q):
        tq = Q @ d / L
        xq, yq = Q @ o / L - sh[0], Q @ f / L - sh[1]
        need = spec.get('thick', 0.02) + spec.get('clear', 0.006)
        for i in range(len(ts)):
            k = np.abs(tq - ts[i]) < 0.5 * step + 1e-9
            if not k.any():
                continue
            a_q = np.arctan2(yq[k], xq[k])
            r_q = np.hypot(xq[k], yq[k])
            r_row = np.interp(a_q, th, np.hypot(X[i], Y[i]), period=2 * np.pi)
            g = float(np.max((r_q + need) / np.maximum(r_row, 1e-9)))
            if g > 1:
                X[i] *= g; Y[i] *= g
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


def bow_hull(A, spec, hull):
    """the bow placed and sized from the hull's points of it and its tails (fold: bow_tail_L, bow_tail_R): its size
    from the lobes' width (2 LOBE sizes), its centre at their middle, the tails' length from how low their points
    reach; the mesh is bow()'s, then (conform, default on) wrapped onto the hull's front there (front_surface), so the
    lobes follow the chest round as the design's do: flat, a bow wide enough from the front sticks out in profile."""
    L = A['head']['L']
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
    G = _bow_mesh(np.array([0.5 * (lo + hi), y, z]), sz, tail, L, depth=depth, knot=spec.get('knot', 0.35))
    if spec.get('conform', True):
        # the flat template wrapped onto the design's bow: each vertex moved in depth by where the hull's front is at its
        # (x, z) against where the template's front plane is, so the lobes follow the chest round as drawn
        S = np.concatenate([B] + tails)
        S = S[S[:, 1] < np.percentile(S[:, 1], 2) + spec.get('front_band', 0.3) * L]   # its front (stray labels behind)
        fy = front_surface(S, spec.get('cell', 0.04) * L, smooth=spec.get('front_smooth', 1.0))
        V = G['verts']
        dy = (fy(V[:, 0], V[:, 2]) - (y - depth)) * spec.get('conform_k', 1.0)
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
    G['fit'] = dict(size=sz / L, tail=tail, depth=depth / L, centre=[0.5 * (lo + hi), y, z])
    return G


def _bow_mesh(c, sz, tail, L, depth=None, knot=0.35):
    """bow()'s mesh round centre c at size sz (m) with tails `tail` sizes long, lobes `depth` (m) deep either side of the
    centre (default 0.09 sizes), each lobe's height at the knot `knot` of its full height."""
    depth = 0.09 * sz if depth is None else depth
    verts, faces, uvs = [], [], []

    def add(vs, fs, us):
        o = len(verts); verts.extend(vs); uvs.extend(us); faces.extend([tuple(i + o for i in f) for f in fs])
    nu, nv = 24, 14
    for sx in (-1, 1):
        # a lobe: an ellipsoid along x, tapering toward the knot, tilted up a touch, with a fold
        vs, us = [], []
        for i in range(nv + 1):
            th = math.pi * i / nv                       # 0 .. pi along the lobe
            for j in range(nu):
                ph = 2 * math.pi * j / nu
                u_ = (1 - math.cos(th)) / 2              # 0 at the knot end .. 1 at the far end
                taper = knot + (1 - knot) * math.sin(min(math.pi, th * 1.15)) ** 0.8
                x = sx * (0.05 + (LOBE - 0.05) * u_) * sz
                zz = math.sin(ph) * 0.20 * sz * taper + 0.05 * sz * u_
                yy = -math.cos(ph) * depth * taper
                fold = -0.03 * sz * math.exp(-((math.sin(ph) - 0.1) / 0.25) ** 2) * math.sin(th) if math.cos(ph) > 0 else 0.0
                vs.append(c + np.array([x, yy - fold, zz])); us.append((j / nu, u_))
        fs = []
        for i in range(nv):
            for j in range(nu):
                j2 = (j + 1) % nu
                fs.append((i * nu + j, i * nu + j2, (i + 1) * nu + j2, (i + 1) * nu + j))
        add(vs, fs, us)
        # a tail: a flat ribbon with thickness, out and down, widening, a V notch at the end
        M = 10
        vs, us = [], []
        for i in range(M + 1):
            s_ = i / M
            p = c + np.array([sx * sz * (0.05 + 0.2 * s_), -0.01 * L * s_, -sz * (TAIL0 + tail * s_)])
            w = sz * (0.13 + 0.09 * s_)
            notch = sz * 0.10 if i == M else 0.0
            for (dx, dz, dy) in ((-w / 2, 0, -0.01 * L), (0, notch, -0.01 * L), (w / 2, 0, -0.01 * L),
                                 (w / 2, 0, 0.004 * L), (0, notch, 0.004 * L), (-w / 2, 0, 0.004 * L)):
                vs.append(p + np.array([dx, dy, dz])); us.append((0.5, s_))
        fs = []
        for i in range(M):
            for k in range(6):
                k2 = (k + 1) % 6
                fs.append((i * 6 + k, i * 6 + k2, (i + 1) * 6 + k2, (i + 1) * 6 + k))
        add(vs, fs, us)
    from .accessories import rounded_box
    kv, kf = rounded_box(0.19, 0.16, 0.24, 0.07, segs=2)
    add(list(kv * sz + c + np.array([0, -0.012 * L, 0.01 * sz])), kf, [(0.5, 0.5)] * len(kv))
    verts = np.array(verts)
    return dict(verts=verts, faces=faces, weights={'upperChest': np.ones(len(verts))}, uv=uvs)


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


def _object(name, verts, faces, weights, arm, mats, uv=None, uv_corner=None, mat_idx=None, smooth=True):
    from . import character
    ob = character._mesh(name, verts, faces, None, mats)
    me = ob.data
    if uv is not None or uv_corner is not None:
        lay = me.uv_layers.new(name='uv')
        for pi, p in enumerate(me.polygons):
            for k, li in enumerate(p.loop_indices):
                lay.data[li].uv = uv_corner[pi][k] if uv_corner is not None else uv[me.loops[li].vertex_index]
    for pi, p in enumerate(me.polygons):
        p.use_smooth = smooth
        if mat_idx is not None:
            p.material_index = mat_idx[pi]
    import bmesh
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    for b, w in weights.items():
        if b not in arm.data.bones:
            continue
        g = ob.vertex_groups.new(name=b)
        for w_ in np.unique(np.round(w, 3)):
            if w_ <= 1e-4:
                continue
            g.add([int(i) for i in np.nonzero(np.round(w, 3) == w_)[0]], float(w_), 'REPLACE')
    mod = ob.modifiers.new('rig', 'ARMATURE'); mod.object = arm
    ob.parent = arm
    return ob


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
                mats.append(_toon(nm + '_panel', s['panel']['color'], sh))
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
            sol = ob.modifiers.new('thick', 'SOLIDIFY'); sol.thickness = s.get('thick', 0.008) * L; sol.offset = -1
            sol.use_rim = True
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
            sol = ob.modifiers.new('thick', 'SOLIDIFY'); sol.thickness = s.get('thick', 0.02) * L; sol.offset = -1
            sol.use_rim = True
        elif k == 'band':
            G = band_hull(A, s, hull) if s.get('source') == 'hull' else band(A, s)
            ob = _object(nm, G['verts'], G['faces'], G['weights'], arm, [_toon(nm, col, sh)], uv=G['uv'])
            if s.get('source') == 'hull':                            # the loft is the band's outside: its thickness
                sol = ob.modifiers.new('thick', 'SOLIDIFY'); sol.thickness = s.get('thick', 0.02) * L; sol.offset = -1
                sol.use_rim = True
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
                sol = ob.modifiers.new('thick', 'SOLIDIFY'); sol.thickness = s.get('thick', 0.025) * L; sol.offset = -1
                sol.use_rim = True
        elif k == 'sleeve':
            G = puff(A, dict(s, _spec=spec_all), hull) if s.get('source') == 'template' else \
                sleeve_hull(A, s, hull) if s.get('source') == 'hull' else sleeve(A, s)
            ob = _object(nm, G['verts'], G['faces'], G['weights'], arm, [_toon(nm, col, sh)], uv=G['uv'])
            sol = ob.modifiers.new('thick', 'SOLIDIFY'); sol.thickness = 0.008 * L; sol.offset = -1
        elif k == 'skirt':
            G = skirt_hull(A, dict(s, _spec=spec_all), hull) if s.get('source') == 'hull' else skirt(A, s)
            pw = G.get('panel_half', s.get('panel', 0.0)) / (2 * math.pi)
            tex = stepped_hem(colors=(col, s.get('hem_color', (0.28, 0.2, 0.18))), panel=(0.5 - pw, 0.5 + pw),
                              repeat=s.get('repeat', 8), pleats=s.get('pleats', 24))
            img = eyetex.to_blender_image(nm + '_tex', tex)
            mats = [_toon_tex(nm, img, sh), _toon(nm + '_panel', s.get('panel_color', col), sh)]
            ob = _object(nm, G['verts'], G['faces'], G['weights'], arm, mats, uv=G['uv'], mat_idx=G['panel'])
            sol = ob.modifiers.new('thick', 'SOLIDIFY'); sol.thickness = 0.01 * L; sol.offset = -1
        elif k == 'collar' and s.get('source') == 'hull':
            G = collar_hull(A, s, nrm, hull)
            mats = [_toon(nm, col, sh), _toon(nm + '_stripe', s.get('stripe_color', (0.3, 0.2, 0.18)), sh)]
            ob = _object(nm, G['verts'], G['faces'], G['weights'], arm, mats, uv=G['uv'], mat_idx=G['edge'])
            sol = ob.modifiers.new('thick', 'SOLIDIFY'); sol.thickness = 0.012 * L; sol.offset = -1; sol.use_rim = True
        elif k == 'collar':
            G = collar(A, s, nrm)
            mats = [_toon(nm, col, sh), _toon(nm + '_stripe', s.get('stripe_color', (0.3, 0.2, 0.18)), sh)]
            ob = _object(nm, G['verts'], G['faces'], G['weights'], arm, mats, uv=G['uv'], mat_idx=G['edge'])
            sol = ob.modifiers.new('thick', 'SOLIDIFY'); sol.thickness = 0.012 * L; sol.offset = -1; sol.use_rim = True
        elif k == 'bow' and s.get('source') == 'hull':
            G = bow_hull(A, dict(s, _spec=spec_all), hull)
            ob = _object(nm, G['verts'], G['faces'], G['weights'], arm, [_toon(nm, col, sh)], uv=G['uv'])
        elif k == 'bow':
            G = bow(A, s)
            ob = _object(nm, G['verts'], G['faces'], G['weights'], arm, [_toon(nm, col, sh)], uv=G['uv'])
        elif k == 'panel':
            if s.get('source') == 'flap':
                G = flap(A, dict(s, _spec=spec_all), hull)
            else:
                G = panel_hull(A, s, hull) if s.get('source') == 'hull' else panel(A, s)
            if s.get('hem') == 'stepped':
                tex = stepped_hem(colors=(col, s.get('hem_color', (0.28, 0.2, 0.18))), repeat=s.get('repeat', 1),
                                  steps=s.get('steps', 6), **{k_: s[k_] for k_ in ('band', 'step_h') if k_ in s})
                mats = [_toon_tex(nm, eyetex.to_blender_image(nm + '_tex', tex), sh)]
            else:
                mats = [_toon(nm, col, sh)]
            ob = _object(nm, G['verts'], G['faces'], G['weights'], arm, mats, uv=G['uv'])
            sol = ob.modifiers.new('thick', 'SOLIDIFY'); sol.thickness = 0.01 * L; sol.offset = -1
        else:
            raise ValueError(k)
        sub = ob.modifiers.new('sub', 'SUBSURF'); sub.levels = 1; sub.render_levels = 1
        shade.outline(ob, thick=s.get('line', 0.0012), color=line, name='garment_line')
        if _loft.LOW_COVERAGE:                                   # built from marginal hull coverage: kept as a number
            ob['charkit_coverage'] = min(_loft.LOW_COVERAGE)
            print('garments: %s lofted from marginal hull coverage (its best row measured on %.0f%% of its circle)'
                  % (nm, 100 * min(_loft.LOW_COVERAGE)))
            _loft.LOW_COVERAGE.clear()
        obs.append(ob)
    if hide.any():
        g = skin.vertex_groups.new(name='under_garments')
        g.add([int(i) for i in np.nonzero(hide)[0]], 1.0, 'REPLACE')
        mk = skin.modifiers.new('under_garments', 'MASK'); mk.vertex_group = 'under_garments'; mk.invert_vertex_group = True
        while skin.modifiers.find('under_garments') > 0:              # first in the stack
            import bpy
            with bpy.context.temp_override(object=skin):
                bpy.ops.object.modifier_move_up(modifier='under_garments')
    return obs
