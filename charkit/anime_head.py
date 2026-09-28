"""Reshape MakeHuman's realistic head (CC0, artist topology: eyelid and mouth loops, the mouth cavity, ears, a seamless neck,
a proper face UV layout) into the anime head that charkit/head.py defines, so the kit gets professional topology AND
knob-driven anime shape.

  1. Smooth the head heavily (uniform Laplacian); the difference is its detail (nose, lips, lids, brow, ears, cavities).
  2. The outward-facing shell of the smooth head (face, sides, back, top; not under the jaw, not inside the mouth or the
     eye sockets) is pinned to the anime surface (head.Head.surface) at the same azimuth, with heights remapped by landmarks
     (chin -> chin, eye line -> eye line, top -> top) and a feature warp that moves and scales the realistic eye and mouth
     regions onto the anime ones (big eyes, a small mouth).
  3. Everything else (the jaw's underside, the cavities, the neck down to where the head bone lets go) follows by a harmonic
     displacement field, so nothing folds and the join to the body is seamless.
  4. The detail goes back on, scaled per region: a little on the face front (anime flatness: a soft nose, soft lips), the
     ears by the 'ear' knob, the cavities whole.
"""
import math
import numpy as np

from . import head as headlib

DETAIL = {'face': 0.25, 'nose': 0.45, 'bridge': 0.1, 'ear': 0.8, 'back': 0.8, 'eye': 0.05, 'nostril': 0.05, 'lips': 0.18,
          'wings': 0.1}
# realistic -> anime feature warp: the eye region grows and moves onto the anime eye; the mouth moves to the anime mouth line
# and narrows. Directions from the head's centre: (sx, sz) scales in azimuth/elevation, R the falloff radius (radians).
EYE_WARP = dict(sx=1.12, sz=2.1, R=0.26)
MOUTH_WARP = dict(sx=0.8, sz=1.0, R=0.16)
NOSE_WARP = dict(sx=0.8, sz=0.8, R=0.12)


def adjacency(n, faces):
    nb = [set() for _ in range(n)]
    for f in faces:
        for a, b in zip(f, f[1:] + f[:1]):
            if a < n and b < n:
                nb[a].add(b); nb[b].add(a)
    return [np.array(sorted(s), int) for s in nb]


def _table(nb, idx):
    deg = max(1, max(len(nb[i]) for i in idx))
    T = np.full((len(idx), deg), -1, int)
    for r, i in enumerate(idx):
        T[r, :len(nb[i])] = nb[i]
    valid = T >= 0
    return np.where(valid, T, 0), valid, np.maximum(valid.sum(1), 1)[:, None]


def laplacian_smooth(V, nb, mask, iters=60, lam=0.5, mu=None):
    """uniform Laplacian on the masked vertices (others fixed); vectorised over a padded neighbour table. With mu (< -lam),
    Taubin's lambda|mu smoothing: removes detail without shrinking the shape."""
    X = V.copy()
    idx = np.nonzero(mask)[0]
    Tc, valid, cnt = _table(nb, idx)
    for _ in range(iters):
        for f in ((lam, mu) if mu is not None else (lam,)):
            avg = (X[Tc] * valid[..., None]).sum(1) / cnt
            X[idx] += f * (avg - X[idx])
    return X


def harmonic(X, nb, free, iters=1500):
    """fill X on the free vertices with the harmonic interpolation of the fixed ones (Jacobi; X (N,k))."""
    X = X.copy()
    idx = np.nonzero(free)[0]
    if len(idx) == 0:
        return X
    Tc, valid, cnt = _table(nb, idx)
    for _ in range(iters):
        X[idx] = (X[Tc] * valid[..., None]).sum(1) / cnt
    return X


def vertex_normals(V, faces):
    tris = []
    for f in faces:
        for k in range(1, len(f) - 1):
            tris.append((f[0], f[k], f[k + 1]))
    T = np.array(tris)
    fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    n = np.zeros_like(V)
    for j in range(3):
        np.add.at(n, T[:, j], fn)
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def _warp(u, v, cu, cv, tu, tv, sx, sz, R):
    """move a region centred (cu, cv) to (tu, tv), scaled (sx, sz) at the centre, fading out by radius R (monotone: no fold
    for scales below ~3)."""
    du, dv = u - cu, v - cv
    f = np.exp(-(du * du + dv * dv) / (R * R))
    return u + ((tu - cu) + du * (sx - 1)) * f, v + ((tv - cv) + dv * (sz - 1)) * f


def target_mesh(H, cols=128, rows=100, neck_r=0.15, neck_y=0.05, skirt=10):
    """the anime head surface (head space) as a triangle mesh for the wrap: columns of head.Head.surface from the skull top
    down to the jawline (chin at the front, the jaw corner at the sides, the nape behind), the lowest rows behind the jaw
    curving in to the neck (the occipital curve), then a skirt under the jaw from the jawline in to the neck (neck_r, neck_y:
    the neck's radius and centre depth, in L). -> (verts (M,3), tris (T,3))."""
    L = H.L
    A = np.linspace(-math.pi, math.pi, cols, endpoint=False)
    w = (1 - np.cos(np.linspace(0, math.pi, rows))) / 2              # dense at the top and the jawline
    nr, ny = neck_r * L, neck_y * L
    V = []
    for a in A:
        zb = headlib.jaw_z(H, a) * 1.02
        c = math.cos(a)
        backness = min(1.0, max(0.0, 0.35 - c) / 1.35)
        col = []
        for t in w:
            z = H.top - (H.top - zb) * t
            p = H.surface(a, z) if t > 0 else np.array([0.0, 0.0, H.top])
            u = max(0.0, (t - 0.6) / 0.4)
            if backness > 0 and u > 0:
                q = np.array([math.sin(a) * nr, ny - c * nr, z])
                p = p + (q - p) * backness * u * u * 0.85
            col.append(p)
        # under the jaw: from the jawline in to where it meets the neck (front: just above the chin; sides: below the jaw
        # corner), easing so the jawline stays a crisp edge
        zn = (-0.34 + (-0.42 + 0.34) * c) * L if c >= 0 else (-0.34 - 0.02 * (-c)) * L
        n_pt = np.array([math.sin(a) * nr, ny - c * nr, zn])
        e_pt = col[-1]
        for j in range(1, skirt + 1):
            t = j / skirt
            e = 1 - (1 - t) ** 2
            col.append(e_pt + (n_pt - e_pt) * e)
        V.extend(col)
    V = np.array(V)
    R = rows + skirt
    T = []
    for k in range(cols):
        k2 = (k + 1) % cols
        for r in range(R - 1):
            a0, a1, b0, b1 = k * R + r, k2 * R + r, k * R + r + 1, k2 * R + r + 1
            T.append((a0, a1, b1)); T.append((a0, b1, b0))
    return V, np.array(T)


def raycast(O, D, TV, T, chunk=48):
    """first hit distance of rays from one origin O along directions D (M,3) on triangles; inf where they miss."""
    v0 = TV[T[:, 0]]; e1 = TV[T[:, 1]] - v0; e2 = TV[T[:, 2]] - v0
    s = O[None] - v0
    q = np.cross(s, e1)
    ok = np.linalg.norm(np.cross(e1, e2), axis=1) > 1e-14
    out = np.full(len(D), np.inf)
    for i in range(0, len(D), chunk):
        d = D[i:i + chunk]
        p = np.cross(d[:, None, :], e2[None])
        det = (e1[None] * p).sum(-1)
        good = (np.abs(det) > 1e-14) & ok[None]
        inv = np.where(good, 1 / np.where(good, det, 1), 0)
        u = (s[None] * p).sum(-1) * inv
        v = (d[:, None, :] * q[None]).sum(-1) * inv
        t = (e2 * q).sum(-1)[None] * inv
        hit = good & (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9) & (t > 1e-9)
        out[i:i + chunk] = np.where(hit, t, np.inf).min(1)
    return out


def surface_azimuth(H, x, z, lo=0.0, hi=math.pi / 2):
    """the front azimuth parameter at which the anime surface at height z reaches x (bisection)."""
    sg = 1.0 if x >= 0 else -1.0
    x = abs(x)
    for _ in range(40):
        m = (lo + hi) / 2
        if H.surface(m, z)[0] < x:
            lo = m
        else:
            hi = m
    return sg * (lo + hi) / 2


def _dir_angles(d):
    """(azimuth: 0 front (-y), + her left; elevation) of directions (M,3)."""
    return np.arctan2(d[:, 0], -d[:, 1]), np.arctan2(d[:, 2], np.hypot(d[:, 0], d[:, 1]))


def _angles_dir(a, e):
    return np.stack([np.sin(a) * np.cos(e), -np.cos(a) * np.cos(e), np.sin(e)], -1)


def reshape(V, faces, head_w, marks, L, knobs=None, detail=None, eye_warp=None, mouth_warp=None, target=None, eye_w=None, lips_w=None, wings_w=None):
    """Wrap MakeHuman's head onto the anime head.
    V (N,3) the stylised body with MakeHuman's head (Blender frame, metres); head_w (N,) the head bone's weight; marks:
    dict(eye_l, eye_r, chin, top, mouth) of the realistic head; L the anime head length; target: optional (verts, tris) in head
    space to wrap onto instead of head.Head's surface (a sculpt, a generated head).
    -> (new V, H (the anime head), centre (head-space origin in world: x 0, the face plane at the eyes, the eye line), info)."""
    D = dict(DETAIL); D.update(detail or {})
    EW = dict(EYE_WARP); EW.update(eye_warp or {})
    MW = dict(MOUTH_WARP); MW.update(mouth_warp or {})
    H = headlib.Head(L, knobs)
    ear_k = D['ear'] * H.K.get('ear', 1.0)
    region = head_w > 0.02
    nb = adjacency(len(V), faces)
    S = laplacian_smooth(V, nb, region, iters=120, lam=0.6, mu=-0.64)
    det = V - S
    nS = vertex_normals(S, faces)
    # the landmarks ride the smoothing (it shrinks the head), so directions are measured on the smooth head
    keys = list(marks)
    chin_real = float(marks['chin'][2])
    mk = dict(zip(keys, follow([marks[k] for k in keys], V, S, k=6)))
    eye_c = (np.asarray(mk['eye_l']) + np.asarray(mk['eye_r'])) / 2
    head = region & (head_w > 0.5)
    # the realistic centre: on the eye line, midway between the face and the back of the skull
    band = head & (np.abs(S[:, 2] - eye_c[2]) < 0.01) & (np.abs(S[:, 0]) < 0.01)
    c_r = np.array([0.0, (S[band, 1].min() + S[band, 1].max()) / 2, eye_c[2]])
    # the anime head in world: head-space origin on the eye line, the chin on the realistic chin, the face plane over the eyes
    # depth: fit the anime face's midline profile (eye line to chin, nose excluded) to the smooth realistic one
    centre_z = chin_real + H.chin
    mid = np.nonzero(head & (np.abs(S[:, 0]) < 0.006) & (S[:, 2] < eye_c[2]) & (S[:, 2] > mk['chin'][2]))[0]
    samples = []                                                 # (share of eye line -> chin, the profile's front y)
    for zz in np.linspace(eye_c[2], mk['chin'][2], 12)[1:-1]:
        near_ = mid[np.abs(S[mid, 2] - zz) < 0.006]
        if len(near_) and abs(zz - mk['nose'][2]) > 0.015:
            samples.append(((eye_c[2] - zz) / max(1e-6, eye_c[2] - mk['chin'][2]), float(S[near_, 1].min())))
    centre = head_centre(H, chin_real, samples, eye_c[1] + H.df)
    c_a = centre + np.array([0.0, (H.db - H.df) / 2, 0.0])
    # the neck where the head bone lets go: its radius and centre (for the target's under-jaw skirt)
    ring = (head_w > 0.03) & (head_w < 0.2)
    nc = V[ring].mean(0)
    n_r = np.median(np.hypot(V[ring, 0] - nc[0], V[ring, 1] - nc[1]))
    TV, TT = target if target is not None else target_mesh(headlib.Head(L, knobs, features=False),
                                                            neck_r=n_r * H.K['neck_r'] / L, neck_y=(nc[1] - centre[1]) / L)
    TVw = TV + centre
    # landmark directions: chin (the elevation remap), eyes and mouth (the feature warps)
    lm_r = dict(chin=_ang(mk['chin'], c_r)[1], eyes=[_ang(mk['eye_l'], c_r), _ang(mk['eye_r'], c_r)],
                mouth=_ang(mk['mouth'], c_r), nose=_ang(mk['nose'], c_r))
    lm_a = anime_marks(H, centre, c_a)
    eye_pts = lm_a['eye_pts']
    # the shell: head-owned, facing outward from the centre, not the jaw's underside
    rad = S - c_r
    rad /= np.maximum(np.linalg.norm(rad, axis=1, keepdims=True), 1e-9)
    # the nose zone (the nostrils too) is always wrapped, so the nostrils flatten away
    nz = np.linalg.norm(V - np.asarray(marks['nose']), axis=1) < 0.075 * L
    below_mouth = S[:, 2] < mk['mouth'][2]
    shell = head & (((nS * rad).sum(1) > 0.3) | nz)
    si = np.nonzero(shell)[0]
    dirs = remap_dirs(rad[si], lm_r, lm_a, EW, MW)
    t = raycast(c_a, dirs, TVw, TT)
    hit = np.isfinite(t)
    si, dirs, t, a0 = si[hit], dirs[hit], t[hit], _dir_angles(rad[si[hit]])[0]
    P = c_a + dirs * t[:, None]
    # detail back on the shell: a little on the face, the nose a touch more, the ears whole, the back mostly
    fr = np.maximum(0.0, np.cos(a0))
    mid = np.exp(-(S[si, 0] / (0.05 * L)) ** 2)
    tip = np.exp(-((S[si, 2] - mk['nose'][2]) / (0.05 * L)) ** 2)
    nose = mid * tip
    bridge = mid * (1 - tip) * smoothstep(mk['nose'][2], eye_c[2], S[si, 2])
    zr = S[si, 2] - eye_c[2]
    earness = smoothstep(0.8, 0.95, np.abs(np.sin(a0))) * smoothstep(-0.35 * L, -0.2 * L, zr) * smoothstep(0.12 * L, 0.02 * L, zr)
    k_face = D['face'] + (D['nose'] - D['face']) * nose + (D['bridge'] - D['face']) * bridge
    k_side = D['back'] + (ear_k - D['back']) * earness
    k = k_face * fr + k_side * (1 - fr)
    inward = (nS[si] * rad[si]).sum(1) < 0.3                         # the nostrils' insides (forced into the shell)
    k = np.where(inward & nz[si], D['nostril'], k)
    # the eye zone (the lids, the orbit, the lid creases and bags): flat, anime-smooth; by angle round each realistic eye
    a_s, e_s = _dir_angles(rad[si])
    dz = np.min([np.hypot(a_s - cu, e_s - cv) for cu, cv in lm_r['eyes']], axis=0)
    ew = np.exp(-(dz / 0.2) ** 2)
    if eye_w is not None:
        ew = np.maximum(ew, np.clip(eye_w[si] * 1.6, 0, 1))
    k = k + (D['eye'] - k) * ew
    for w_, key in ((lips_w, 'lips'), (wings_w, 'wings')):         # the lips and the nose wings (MakeHuman's oris, levator06)
        if w_ is not None:
            m_ = np.clip(w_[si] * 1.5, 0, 1)
            k = k + (D[key] - k) * m_
    final = P + det[si] * k[:, None]
    # everything else in the region (the lips' inner rolls, the mouth cavity, the jaw's underside, the neck's top) moves
    # with the shell around it in 3D (inverse-distance interpolation of the shell's displacement and of the fixed neck), so
    # interior parts keep their place behind the surface they sit under
    pinned = np.zeros(len(V), bool); pinned[si] = True
    free = region & ~pinned
    fixed = np.nonzero(~region & (np.linalg.norm(V - c_r, axis=1) < 1.0 * L))[0]
    src = np.vstack([V[si], V[fixed]])
    dsp = np.vstack([final - V[si], np.zeros((len(fixed), 3))])
    out = V.copy()
    out[si] = final
    fi = np.nonzero(free)[0]
    out[fi] = V[fi] + idw(V[fi], src, dsp, power=4)
    # what charkit/base_anime.py needs to re-wrap a derived base to other knobs: each shell vertex's realistic direction and
    # its (detail-free) surface point, the realistic landmarks' directions and the face profile
    info = dict(pinned=pinned, region=region, eye_world=eye_pts, c_real=c_r, c_anime=c_a, target=(TV, TT),
                shell=si, shell_rad=rad[si], shell_P=P, lm_real=lm_r, profile=samples, warps=(EW, MW))
    return out, H, centre, info


def _ang(p, c):
    a, e = _dir_angles((np.asarray(p) - c)[None])
    return float(a[0]), float(e[0])


def head_centre(H, chin_z, samples, fallback_y):
    """the anime head's origin in world: x 0, the chin on the realistic chin (chin_z), depth fitting the anime face's midline
    profile to the realistic one's samples [(share of eye line -> chin, front y)] (the nose excluded)."""
    fronts = [y - H.surface(0.0, -H.chin * d)[1] for d, y in samples]
    cy = float(np.median(fronts)) if fronts else fallback_y
    return np.array([0.0, cy, chin_z + H.chin])


def anime_marks(H, centre, c_a):
    """the anime head's landmark directions from c_a: chin elevation, the eyes, the mouth and the nose (the feature warps)."""
    eye_pts = [centre + H.surface(surface_azimuth(H, s * H.eye_x, H.eye_z), H.eye_z) for s in (1, -1)]
    return dict(chin=_ang(centre + H.surface(0.0, -H.chin), c_a)[1], eyes=[_ang(p, c_a) for p in eye_pts],
                mouth=_ang(centre + H.surface(0.0, H.mouth_z), c_a), nose=_ang(centre + H.surface(0.0, H.nose_z), c_a),
                eye_pts=eye_pts)


def remap_dirs(rad, lm_r, lm_a, EW=None, MW=None):
    """realistic directions (from the realistic centre) -> the directions to cast from the anime centre: elevations below the
    eye line remapped so the chin lands on the chin (strongest at the front), then the eye, mouth and nose regions moved (and
    the eyes grown) onto the anime ones."""
    EW = EW or EYE_WARP; MW = MW or MOUTH_WARP
    e_rc, e_ac = lm_r['chin'], lm_a['chin']
    a, e = _dir_angles(rad)
    front = np.maximum(0.0, np.cos(a))
    ratio = 1 + (e_ac / e_rc - 1) * np.sqrt(front)
    e = np.where(e < 0, e * ratio, e)
    for (cu, cv), (tu, tv) in zip(lm_r['eyes'], lm_a['eyes']):
        a, e = _warp(a, e, cu, cv * (e_ac / e_rc if cv < 0 else 1), tu, tv, EW['sx'], EW['sz'], EW['R'])
    m_r, m_a, n_r_, n_a_ = lm_r['mouth'], lm_a['mouth'], lm_r['nose'], lm_a['nose']
    a, e = _warp(a, e, m_r[0], m_r[1] * e_ac / e_rc, m_a[0], m_a[1], MW['sx'], MW['sz'], MW['R'])
    a, e = _warp(a, e, n_r_[0], n_r_[1] * e_ac / e_rc, n_a_[0], n_a_[1], NOSE_WARP['sx'], NOSE_WARP['sz'], NOSE_WARP['R'])
    return _angles_dir(a, e)


def idw(X, src, disp, power=4, chunk=256):
    """inverse-distance (Shepard) interpolation at X of displacements given at src."""
    out = np.zeros_like(X)
    for i in range(0, len(X), chunk):
        x = X[i:i + chunk]
        d2 = ((x[:, None, :] - src[None]) ** 2).sum(-1) + 1e-12
        w = d2 ** (-power / 2)
        out[i:i + chunk] = (w @ disp) / w.sum(1, keepdims=True)
    return out


def follow(points, V0, V1, k=8):
    """move points (M,3) with the displacement of their k nearest mesh vertices (inverse-distance weighted)."""
    P = np.asarray(points, float)
    out = P.copy()
    d = V1 - V0
    for j, p in enumerate(P):
        dist = np.linalg.norm(V0 - p, axis=1)
        nn = np.argpartition(dist, k)[:k]
        w = 1 / np.maximum(dist[nn], 1e-5) ** 2
        out[j] = p + (d[nn] * w[:, None]).sum(0) / w.sum()
    return out


def rewrap(q0, region, shell, shell_rad, shell_P, lm_r, profile, warps, Vbody, marks, neck, L, knobs=None, ear=None):
    """Re-wrap a derived anime base (charkit/base_anime.py) to a spec's head knobs: reshape()'s wrap without MakeHuman's head.
    The base was wrapped at neutral knobs; each shell vertex keeps its realistic direction, so the knobs' anime surface is
    ray-cast along the knobs' remapped directions and the vertex moves by the surface's change (its detail rides along);
    everything else in the region (the sockets, the cavity, the under-jaw, the neck's top) follows the shell and the body in
    3D (inverse-distance), as reshape() does.
    q0 (N,3): the base in head space in units of its head length (origin: its head's centre); region (N,): the vertices the
    wrap moves; shell (S,): indices, with shell_rad (S,3) their realistic directions and shell_P (S,3) their neutral surface
    points (head space, units of L); lm_r: the realistic landmarks' directions; profile [(share of eye line -> chin, front y -
    eye y, in L)]: the realistic face's midline; warps: (eye, mouth) warp settings; Vbody (N,3): the spec's body where the
    base has a MakeHuman vertex (NaN elsewhere); marks: the spec's realistic marks (chin, eye_l); neck: (radius, centre) of
    the neck where the head bone lets go; L the head length; ear: optional (indices, relief in L) for the 'ear' knob.
    -> (V, H, centre, info) as reshape()."""
    H = headlib.Head(L, knobs)
    ey = float(marks['eye_l'][1])
    centre = head_centre(H, float(marks['chin'][2]), [(d, ey + y * L) for d, y in profile], ey + H.df)
    c_a = centre + np.array([0.0, (H.db - H.df) / 2, 0.0])
    n_r, nc = neck
    TV, TT = target_mesh(headlib.Head(L, knobs, features=False), neck_r=n_r * H.K['neck_r'] / L, neck_y=(nc[1] - centre[1]) / L)
    lm_a = anime_marks(H, centre, c_a)
    shell = np.asarray(shell)
    dirs = remap_dirs(np.asarray(shell_rad), lm_r, lm_a, *warps)
    t = raycast(c_a, dirs, TV + centre, TT)
    P0 = centre + L * np.asarray(shell_P)
    P = np.where(np.isfinite(t)[:, None], c_a + dirs * np.where(np.isfinite(t), t, 0)[:, None], P0)
    R = centre + L * np.asarray(q0)                                  # the neutral base, placed rigidly on this head
    out = R.copy()
    region = np.asarray(region, bool)
    out[shell] = R[shell] + (P - P0)
    body = ~region
    out[body] = Vbody[body]
    pinned = np.zeros(len(R), bool); pinned[shell] = True
    free = np.nonzero(region & ~pinned)[0]
    fixed = np.nonzero(body & (np.linalg.norm(R - centre, axis=1) < 1.0 * L))[0]
    src = np.vstack([R[shell], R[fixed]])
    dsp = np.vstack([out[shell] - R[shell], Vbody[fixed] - R[fixed]])
    out[free] = R[free] + idw(R[free], src, dsp, power=4)
    if ear is not None and H.K.get('ear', 1.0) != 1.0:
        ei, ed = ear
        out[ei] += (H.K['ear'] - 1.0) * L * np.asarray(ed)
    info = dict(pinned=pinned, region=region, eye_world=lm_a['eye_pts'], c_real=None, c_anime=c_a, target=(TV, TT))
    return out, H, centre, info
