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


def hull_edge(P, ax, n=72, q=2.0, smooth=2.0, low=True):
    """a piece's lower (or upper) edge per angle round an axis, from its hull points: per sector the q-th percentile of
    height (100 - q for the upper), filled round the circle and smoothed -> fn(theta) -> height (world z)."""
    from scipy.ndimage import gaussian_filter1d
    from .geom import loft
    _, th, _ = ax.coords(P)
    j = np.clip(((th + np.pi) / (2 * np.pi) * n).astype(int), 0, n - 1)
    z = np.full(n, np.nan)
    for k in range(n):
        zk = P[j == k, 2]
        if len(zk) >= 5:
            z[k] = np.percentile(zk, q if low else 100 - q)
    z = loft._fill_periodic(z)
    if z is None:
        raise ValueError('too few hull points for an edge')
    z = gaussian_filter1d(z, smooth, mode='wrap')
    th_c = -np.pi + (np.arange(n) + 0.5) * 2 * np.pi / n
    return lambda a: np.interp(a, th_c, z, period=2 * np.pi)


def shell(A, spec, normals=None, hull=None):
    """a tight garment: the region's faces lifted by `offset` along the body's normals. With `source` 'hull', its hem
    follows the hull's own piece: cut below the lower edge of its points (and its folded pieces', `fold`) per angle
    round the body (hull_edge), lowered by `hem_drop` L. -> dict(verts, faces, weights, uvs (per face corner, the
    body's), src (body vertex per shell vertex), faces_src (body face index per face))."""
    L = A['head']['L']
    V, F = A['verts'], A['faces']
    ins = region(A, spec['region'])
    if spec.get('source') == 'hull':
        P = _hull_points(hull, spec)
        ax = _vertical_axis(P, P[:, 2].max())
        edge = hull_edge(P, ax, q=spec.get('hem_q', 2.0))
        ins &= V[:, 2] >= edge(ax.coords(V)[1]) - spec.get('hem_drop', 0.0) * L
    # height cuts at body landmarks: [bone, t, 'above' | 'below', offset in L]
    for bone, t, side, o in spec.get('cuts', []):
        h, tl = bone_seg(A, bone)
        zc = (h + (tl - h) * t)[2] + o * L
        ins &= (V[:, 2] >= zc) if side == 'above' else (V[:, 2] <= zc)
    keep = [i for i, f in enumerate(F) if all(ins[v] for v in f)]
    used = sorted({v for i in keep for v in F[i]})
    remap = {o: n for n, o in enumerate(used)}
    nrm = normals if normals is not None else vertex_normals(V, F)
    off = spec.get('offset', 0.012) * L
    sv = V[used] + nrm[used] * off
    sf = [tuple(remap[v] for v in F[i]) for i in keep]
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
    W = {b: w[used] for b, w in A['weights'].items() if w[used].max() > 1e-4}
    B = A['body']
    uvs = [[B['uvs'][ui] for ui in B['face_uv'][i]] for i in keep]
    return dict(verts=sv, faces=sf, weights=W, uvs=uvs, src=np.array(used), faces_src=keep)


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
def hull_pieces(spec, A):
    """the visual hull's outfit pieces as world points on this character: the generated shape (the spec's hair.shape.glb,
    charkit.geom.hull's), aligned by its eyes as the build aligns its target (i3d.eye_target, i3d.align_by_eyes),
    split by the per-vertex pieces its sidecar names -> {piece id: (n, 3)}, or None when the shape carries no pieces."""
    import json, os
    from . import i3d
    from .geom import io as gio
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
    V = np.asarray(gio.load(path).V, float)
    lab = np.load(os.path.join(os.path.dirname(path), J['pieces']))
    if len(lab) != len(V):
        raise ValueError('%s: %d piece labels for %d vertices' % (J['pieces'], len(lab), len(V)))
    eye_mid, spacing = i3d.eye_target(A, shape)
    W = i3d.align_by_eyes(V, (np.asarray(J['eyes'][0], float), np.asarray(J['eyes'][1], float)), eye_mid, spacing)
    return {pid: W[lab == int(k)] for k, pid in (J.get('piece_names') or {}).items() if (lab == int(k)).any()}


def _hull_points(hull, s, fold=()):
    """a garment's points from the hull: its `piece` (default its name) with the pieces it carries (`fold`)."""
    if not hull:
        raise ValueError('%s: source hull, but the shape carries no pieces' % s['name'])
    ids = [s.get('piece', s['name'])] + list(s.get('fold', fold))
    P = [hull[i] for i in ids if i in hull and len(hull[i])]
    if not P:
        raise ValueError('%s: no hull points for %s' % (s['name'], ids))
    return np.concatenate(P)


def _vertical_axis(P, top):
    """a vertical axis down through a piece's points (its median x and y), from height `top`, front toward -y."""
    from .geom import loft
    c = np.median(P, 0)
    return loft.Axis((c[0], c[1], top), (0, 0, -1), (0, -1, 0))


def belt_hull(A, spec, hull):
    """a band round the torso lofted through the hull's points of its piece (charkit.geom.loft): rows every `step` L
    between the points' `span` percentiles of height, the section measured per angle and filled where no view shows it;
    its top and bottom rows pulled in by `round` of its thickness so the edge reads rounded; `offset` L out from the hull's
    surface. Weighted to the hips. -> dict(verts, faces, weights, uv)."""
    from .geom import loft
    L = A['head']['L']
    P = _hull_points(hull, spec)
    ax = _vertical_axis(P, P[:, 2].max())
    t, th, r = ax.coords(P)
    lo, hi = np.percentile(t, spec.get('span', (2, 98)))
    rows = max(3, int(round((hi - lo) / (spec.get('step', 0.02) * L))) + 1)
    F = loft.field(t, th, r, np.linspace(lo, hi, rows), nth=spec.get('cols', 96))
    R = F.R + spec.get('offset', 0.0) * L
    pull = spec.get('round', 0.4) * spec.get('thick', 0.025) * L
    R[0] -= pull; R[-1] -= pull
    V, quads, uv = loft.loft(ax, F, R)
    return dict(verts=V, faces=quads, weights={'hips': np.ones(len(V))}, uv=[tuple(x) for x in uv],
                hide=wrapped(A, V[:, 2].min(), V[:, 2].max()))


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
    half-width measured from the panel's points (else the spec's `panel`). UV and weights as skirt()'s.
    -> dict(verts, faces, weights, uv, panel, z_waist)."""
    from scipy.ndimage import gaussian_filter1d
    from .geom import loft
    L = A['head']['L']
    P = _hull_points(hull, spec, fold=('skirt_panel',))
    top = np.percentile(P[:, 2], 99.5)
    ax = _vertical_axis(P[P[:, 2] > top - 0.1 * L], top)
    t, th, r = ax.coords(P)
    n = spec.get('cols', 144); rows = spec.get('rows', 16)
    # the hem: per sector, where the points end (a high percentile of t), filled round and smoothed
    j = np.clip(((th + np.pi) / (2 * np.pi) * n).astype(int), 0, n - 1)
    hem = np.full(n, np.nan)
    for k in range(n):
        tk = t[j == k]
        if len(tk) >= 5:
            hem[k] = np.percentile(tk, spec.get('hem_q', 97))
    hem = loft._fill_periodic(hem)
    if hem is None:
        raise ValueError('%s: too few hull points to find its hem' % spec['name'])
    hem = gaussian_filter1d(hem, spec.get('hem_smooth', 2.0), mode='wrap')
    th_c = -np.pi + (np.arange(n) + 0.5) * 2 * np.pi / n
    hem_at = lambda a: np.interp(a, th_c, hem, period=2 * np.pi)
    # the waist line per angle: where the skirt's points start, or tucked `tuck` L under a hull-sourced band's lower edge
    top_z = hull_edge(P, ax, q=spec.get('waist_q', 3.0), low=False)
    band = spec.get('under')
    if band and hull and band in hull and len(hull[band]):
        low = hull_edge(hull[band], ax, q=5.0)
        top_z_ = top_z
        top_z = lambda a: np.minimum(top_z_(a), low(a) + spec.get('tuck', 0.03) * L)
    t0_at = lambda a: top - top_z(a)
    v = np.clip((t - t0_at(th)) / np.maximum(1e-9, hem_at(th) - t0_at(th)), -0.2, 1.2)
    vs = np.linspace(0, 1, rows + 1)
    F = loft.field(v, th, r, vs, nth=n, smooth=(1.0, 1.0))
    off = spec.get('offset', 0.0) * L
    pleats = spec.get('pleats', 24); depth = spec.get('pleat', 0.05) * L
    TH = F.th[None, :]; VV = vs[:, None]
    ph = (TH + np.pi) / (2 * np.pi) * pleats
    zig = np.abs((ph % 1.0) - 0.5) * 2 - 0.5
    R = F.R + off + depth * zig * VV ** 0.7
    T = t0_at(TH) + VV * (hem_at(TH) - t0_at(TH))
    verts = ax.point(T, np.broadcast_to(TH, T.shape), R).reshape(-1, 3)
    faces = [(i * n + k, i * n + (k + 1) % n, (i + 1) * n + (k + 1) % n, (i + 1) * n + k)
             for i in range(rows) for k in range(n)]
    uvs = [((k + 0.5) / n, i / rows) for i in range(rows + 1) for k in range(n)]
    # the front panel: the skirt_panel's points' angular spread, else the knob
    pan_pts = hull.get('skirt_panel') if hull else None
    if pan_pts is not None and len(pan_pts) > 20:
        half = float(np.percentile(np.abs(ax.coords(pan_pts)[1]), 95))
    else:
        half = spec.get('panel', 0.0)
    pan = [1 if abs(F.th[k]) < half else 0 for i in range(rows) for k in range(n)]
    vv = np.repeat(vs, n)
    sx = np.clip(verts[:, 0] / (0.08 * L), -1, 1)
    leg = 0.65 * vv ** 1.4
    Wt = {'hips': 1 - leg, 'leftUpperLeg': leg * (1 + sx) / 2, 'rightUpperLeg': leg * (1 - sx) / 2}
    return dict(verts=verts, faces=faces, weights=Wt, uv=uvs, panel=pan, z_waist=float(top - np.median(t0_at(F.th))),
                panel_half=half)


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
    c = np.array([0.0, y, z])
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
                taper = 0.35 + 0.65 * math.sin(min(math.pi, th * 1.15)) ** 0.8
                x = sx * (0.05 + 0.47 * u_) * sz
                zz = math.sin(ph) * 0.20 * sz * taper + 0.05 * sz * u_
                yy = -math.cos(ph) * 0.09 * sz * taper
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
            p = c + np.array([sx * sz * (0.05 + 0.2 * s_), -0.01 * L * s_, -sz * (0.08 + spec.get('tail', 0.62) * s_)])
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


def collar(A, spec, normals=None):
    """a sailor collar that drapes: from the neckline, at each azimuth, a walk along the body surface outward and down
    (over the shoulders at the sides, down the chest in front, down the back behind) to a length by azimuth; a V opening at
    the front, a square flap behind; lifted by `offset`. The stripe runs `stripe` (a share of the length) in from its
    edge. -> dict(verts, faces, weights, uv, edge (per face: 1 on the stripe))."""
    from .anime_head import raycast
    L = A['head']['L']
    V, F = A['verts'], A['faces']
    N = normals if normals is not None else vertex_normals(V, F)
    nb, _ = bone_seg(A, 'neck')
    z0 = nb[2] + spec.get('rise', 0.0) * L
    cy = nb[1] + 0.02 * L
    vd, sd, bd = (spec.get(k, d) * L for k, d in (('v_depth', 0.62), ('side_depth', 0.30), ('back_depth', 0.5)))
    v_half = math.radians(spec.get('v_half', 36.0))
    near = (np.abs(V[:, 2] - z0) < 0.08 * L) & (N[:, 2] > -0.45)
    # walk on the neck and torso only (the jaw's underside is close to the neck's front: never snap to the head)
    hw_ = A['weights'].get('head', np.zeros(len(V)))
    tor = (hw_ < 0.3) & (V[:, 2] < z0 + 0.04 * L) & (V[:, 2] > z0 - 1.2 * L) & (N[:, 2] > -0.45)   # no under-jaw
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
        o = np.array([0.0, cy, z0])
        t = raycast(o, d[None], V, T)[0] if len(T) else np.inf
        p0 = o + d * (t if np.isfinite(t) else 0.06 * L)
        ln = length(a)
        path = surface_walk(Vt, Nt, p0, d * 0.7 + np.array([0, 0, -0.3]), ln / (nr * 2), nr * 2,
                            bias=np.array([0, 0, -0.25]))
        for j in range(nr + 1):
            i_ = int(np.argmin(((Vt - path[2 * j]) ** 2).sum(1)))
            grid[j, k] = path[2 * j] + Nt[i_] * off
    verts = grid.reshape(-1, 3)
    uvs = [(k / na, j / nr) for j in range(nr + 1) for k in range(na)]
    faces, edge = [], []
    st0, st1 = spec.get('stripe', (0.72, 0.86))
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


def build(C, specs, line=(0.30, 0.18, 0.16), hull=None):
    """Blender objects for an outfit on a built character C (charkit.character.build): each garment rigged to C's armature,
    toon-shaded and outlined; the body under the tight shells masked away. hull: hull_pieces()' points, for the garments
    whose `source` is 'hull'. -> [objects]."""
    from . import eyetex, shade
    A, arm, skin = C['data'], C['arm'], C['skin']
    L = A['head']['L']
    nrm = vertex_normals(A['verts'], A['faces'])
    hide = np.zeros(len(A['verts']), bool)
    obs = []
    for s in specs or []:
        k, nm = s['kind'], s['name']
        col = s.get('color', (0.8, 0.8, 0.8))
        sh = s.get('shade')                                         # its own shade multiplier (else SHADE_MUL)
        if k == 'shell':
            G = shell(A, s, nrm, hull)
            mats = [_toon(nm, col, sh)]
            midx = None
            if 'sole' in s:                                           # boots: the bottom as a dark sole
                mats.append(_toon(nm + '_sole', s['sole']['color'], sh))
                zmin = G['verts'][:, 2].min()
                midx = [1 if G['verts'][list(f), 2].max() < zmin + s['sole']['height'] * L else 0 for f in G['faces']]
            uvc = G['uvs']
            if 'panel' in s:                                          # a front panel in another colour (a bib, a placket)
                # a front-projected UV and a mask texture: a smooth-edged panel on the front, the plain colour elsewhere
                P_ = s['panel']
                z0_ = bone_seg(A, P_['from'][0])[0][2] + P_['from'][1] * L
                z1_ = bone_seg(A, P_['to'][0])[0][2] + P_['to'][1] * L
                cyf = A['head']['centre'][1]
                zlo, zhi = z0_ - 0.2 * L, z1_ + 0.2 * L
                n_ = 512
                U_, V_ = np.meshgrid((np.arange(n_) + 0.5) / n_, ((np.arange(n_) + 0.5) / n_)[::-1])
                X_ = (U_ - 0.5) * L; Z_ = zlo + V_ * (zhi - zlo)
                t_ = np.clip((z1_ - Z_) / max(1e-6, z1_ - z0_), 0, 1)
                hw = (P_['half_top'] + (P_['half_bottom'] - P_['half_top']) * t_) * L
                inside_ = (Z_ >= z0_) & (Z_ <= z1_) & (np.abs(X_) < hw)
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
        elif k == 'band':
            G = band(A, s)
            ob = _object(nm, G['verts'], G['faces'], G['weights'], arm, [_toon(nm, col, sh)], uv=G['uv'])
        elif k == 'shoe':
            G = shoe(A, s)
            mats = [_toon(nm, col, sh), _toon(nm + '_sole', s.get('sole_color', (0.26, 0.21, 0.21)), sh)]
            ob = _object(nm, G['verts'], G['faces'], G['weights'], arm, mats, uv=G['uv'], mat_idx=G['sole'])
            # the body's foot is inside it: mask it
            dom_, _ = dominant(A)
            for b_ in (f"{s['side']}Foot", f"{s['side']}Toes"):
                hide[np.nonzero(dom_ == b_)[0]] = True
        elif k == 'belt':
            G = belt_hull(A, s, hull) if s.get('source') == 'hull' else belt(A, s)
            ob = _object(nm, G['verts'], G['faces'], G['weights'], arm, [_toon(nm, col, sh)], uv=G['uv'])
            if 'hide' in G:
                hide[G['hide']] = True
            if s.get('source') == 'hull':                            # the loft is the band's outside: give it a thickness
                sol = ob.modifiers.new('thick', 'SOLIDIFY'); sol.thickness = s.get('thick', 0.025) * L; sol.offset = -1
                sol.use_rim = True
        elif k == 'sleeve':
            G = sleeve(A, s)
            ob = _object(nm, G['verts'], G['faces'], G['weights'], arm, [_toon(nm, col, sh)], uv=G['uv'])
            sol = ob.modifiers.new('thick', 'SOLIDIFY'); sol.thickness = 0.008 * L; sol.offset = -1
        elif k == 'skirt':
            G = skirt_hull(A, s, hull) if s.get('source') == 'hull' else skirt(A, s)
            pw = G.get('panel_half', s.get('panel', 0.0)) / (2 * math.pi)
            tex = stepped_hem(colors=(col, s.get('hem_color', (0.28, 0.2, 0.18))), panel=(0.5 - pw, 0.5 + pw),
                              repeat=s.get('repeat', 8), pleats=s.get('pleats', 24))
            img = eyetex.to_blender_image(nm + '_tex', tex)
            mats = [_toon_tex(nm, img, sh), _toon(nm + '_panel', s.get('panel_color', col), sh)]
            ob = _object(nm, G['verts'], G['faces'], G['weights'], arm, mats, uv=G['uv'], mat_idx=G['panel'])
            sol = ob.modifiers.new('thick', 'SOLIDIFY'); sol.thickness = 0.01 * L; sol.offset = -1
        elif k == 'collar':
            G = collar(A, s, nrm)
            mats = [_toon(nm, col, sh), _toon(nm + '_stripe', s.get('stripe_color', (0.3, 0.2, 0.18)), sh)]
            ob = _object(nm, G['verts'], G['faces'], G['weights'], arm, mats, uv=G['uv'], mat_idx=G['edge'])
            sol = ob.modifiers.new('thick', 'SOLIDIFY'); sol.thickness = 0.012 * L; sol.offset = -1; sol.use_rim = True
        elif k == 'bow':
            G = bow(A, s)
            ob = _object(nm, G['verts'], G['faces'], G['weights'], arm, [_toon(nm, col, sh)], uv=G['uv'])
        elif k == 'panel':
            G = panel(A, s)
            if s.get('hem') == 'stepped':
                tex = stepped_hem(colors=(col, s.get('hem_color', (0.28, 0.2, 0.18))), repeat=s.get('repeat', 1),
                                  steps=s.get('steps', 6))
                mats = [_toon_tex(nm, eyetex.to_blender_image(nm + '_tex', tex), sh)]
            else:
                mats = [_toon(nm, col, sh)]
            ob = _object(nm, G['verts'], G['faces'], G['weights'], arm, mats, uv=G['uv'])
            sol = ob.modifiers.new('thick', 'SOLIDIFY'); sol.thickness = 0.01 * L; sol.offset = -1
        else:
            raise ValueError(k)
        sub = ob.modifiers.new('sub', 'SUBSURF'); sub.levels = 1; sub.render_levels = 1
        shade.outline(ob, thick=s.get('line', 0.0012), color=line, name='garment_line')
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
