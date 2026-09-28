"""Anime eyes (docs/CHARKIT.md §2, face features): the eye opening, its lids and pocket re-shaped from MakeHuman's eye topology
onto a knob-driven anime outline; the eye plate behind it (a procedural iris: gaze, pupil, highlights); the lash ribbons; and
the lid shape keys (blink and the expression shapes), all from the same outline machinery.

MakeHuman's eye (hm08, a closed mesh): the lids wrap a pocket round the eyeball helper. The lid margin is the front edge of the
backward-facing inner-lid band; removing it cuts the pocket (a bag behind the opening) off from the face. The outer lid skin
round it comes in concentric edge rings.

Eye-local coordinates: x along the eye, 0 at its centre, + outward (away from the nose), in metres; z up.
"""
import math
from collections import defaultdict, deque

import numpy as np

from . import anime_head as ah, head as headlib

DEFAULT_EYE = {
    'x': 0.168,          # eye centre from the midline, in L
    'z': 0.0,            # eye centre above the eye line, in L
    'width': 0.19,       # opening width, in L
    'height': 0.62,      # opening height / width
    'lower': 0.42,       # share of the height below the corner line
    'tilt': 2.5,         # degrees, outer corner up
    'inner_drop': 0.05,  # inner corner below the corner line, in widths
    'peak': 0.40,        # where the upper lid peaks along the eye (0 inner .. 1 outer)
    'upper_full': 0.6,   # upper arc fullness (0 pointed .. 1 boxy)
    'lower_low': 0.55,   # where the lower lid is lowest (0 inner .. 1 outer)
    'lower_full': 0.45,  # lower arc fullness
    'depth': 0.006,      # the eye plate behind the face surface, in L
    'lash': 0.028,       # upper lash thickness, in L
    'lash_inner': 0.35,  # lash thickness at the inner corner (share)
    'flick': 0.16,       # outer flick length, in widths
    'flick_angle': 22.0, # degrees above the lid line
    'lower_lash': 0.6,   # lower lash extent from the outer corner (share of the width)
    'lower_lash_w': 0.36,  # lower lash thickness (share of the upper)
    'crease': 0.10,      # the double-lid crease line above the lash, in widths (0 = none)
    'crease_w': 0.004,   # its thickness, in L
}

RINGS = 6                                   # outer lid rings that can follow the margin (spread() decides how far)


# ---------------------------------------------------------------------------------------------------------------- topology
def _adj(n, faces):
    nb = defaultdict(set)
    for f in faces:
        for a, b in zip(f, f[1:] + f[:1]):
            nb[a].add(b); nb[b].add(a)
    return nb


def _components(S, nb):
    out, seen = [], set()
    for s in S:
        if s in seen:
            continue
        q, cc = [s], []
        seen.add(s)
        while q:
            u = q.pop(); cc.append(u)
            for w in nb[u]:
                if w in S and w not in seen:
                    seen.add(w); q.append(w)
        out.append(cc)
    return out


def detect(Vb, faces, eyeball):
    """Vb the base mesh's body vertices (any consistent frame, y = back, z = up); eyeball: the eyeball helper's centre.
    -> dict(margin: ordered loop starting at the inner corner and running over the top; upper/lower: the two halves (inner ->
    outer, both including the corners); pocket: {vertex: ring}; outer: {vertex: ring} for rings 1..RINGS)."""
    n = len(Vb)
    nb = _adj(n, faces)
    nrm = ah.vertex_normals(Vb, faces)
    dist = np.linalg.norm(Vb - eyeball, axis=1)
    band = set(np.nonzero((dist < 0.025) & (nrm[:, 1] > 0.05))[0].tolist())
    A = set(max(_components(band, nb), key=len))
    bnd = {u for u in A if any(w not in A for w in nb[u])}
    margin_set = set(min(_components(bnd, nb), key=lambda c: Vb[c, 1].mean()))
    # walk the loop
    start = next(iter(margin_set))
    loop, prev = [start], None
    while True:
        nxt = [w for w in nb[loop[-1]] if w in margin_set and w != prev and (w != loop[0] or len(loop) > 2)]
        if not nxt or nxt[0] == loop[0]:
            break
        prev = loop[-1]
        loop.append(min(nxt, key=lambda w: np.linalg.norm(Vb[w] - Vb[loop[-1]])))
    # inner corner (nearest the midline), then run over the top
    side = 1.0 if eyeball[0] >= 0 else -1.0
    out_x = Vb[loop, 0] * side
    k0 = int(np.argmin(out_x)); loop = loop[k0:] + loop[:k0]
    k1 = int(np.argmax(Vb[loop, 0] * side))
    a, b = loop[:k1 + 1], [loop[0]] + loop[k1:][::-1]
    upper, lower = (a, b) if Vb[a, 2].mean() > Vb[b, 2].mean() else (b, a)
    margin = upper + lower[1:-1][::-1]
    # the pocket: what the margin cuts off; rings by BFS from the margin
    ms = set(margin)
    back = int(np.argmin(np.linalg.norm(Vb - (eyeball + np.array([0, 0.012, 0])), axis=1)))
    pocket, q = {back: None}, deque([back])
    while q:
        u = q.popleft()
        for w in nb[u]:
            if w not in ms and w not in pocket:
                pocket[w] = None; q.append(w)
    if len(pocket) > 2000:
        raise RuntimeError('eye pocket not cut off by the margin loop (%d vertices)' % len(pocket))
    ring = {u: 0 for u in margin}
    q = deque(margin)
    while q:
        u = q.popleft()
        for w in nb[u]:
            if w not in ring and (w in pocket or len(ring) < 0):
                ring[w] = ring[u] + 1; q.append(w)
    pocket = {u: r for u, r in ring.items() if u in pocket}
    outer, q = {u: 0 for u in margin}, deque(margin)
    while q:
        u = q.popleft()
        if outer[u] >= RINGS:
            continue
        for w in nb[u]:
            if w not in outer and w not in pocket:
                outer[w] = outer[u] + 1; q.append(w)
    outer = {u: r for u, r in outer.items() if r > 0}
    return dict(margin=margin, upper=upper, lower=lower, pocket=pocket, outer=outer)


# ----------------------------------------------------------------------------------------------------------------- outline
def _knobs(k):
    K = dict(DEFAULT_EYE); K.update(k or {})
    return K


def _arc(t, peak, full):
    """a lid arc on t in [0, 1]: 0 at both corners, 1 at t = peak; full (0..1) squares it off."""
    t = np.clip(t, 0, 1)
    g = math.log(0.5) / math.log(min(0.95, max(0.05, peak)))
    s = np.sin(np.pi * t ** g)
    return s ** (1.0 - 0.75 * full)


def outline(K, L, t, which):
    """eye-local (x, z) of the upper or lower lid at t (0 inner corner .. 1 outer corner)."""
    W = K['width'] * L
    Hh = K['height'] * W
    t = np.asarray(t, float)
    x = -W / 2 + W * t
    tl = math.tan(math.radians(K['tilt']))
    base = x * tl - K['inner_drop'] * W * (1 - t) ** 2
    if which == 'upper':
        z = base + Hh * (1 - K['lower']) * _arc(t, K['peak'], K['upper_full'])
    else:
        z = base - Hh * K['lower'] * _arc(t, K['lower_low'], K['lower_full'])
    return x, z


def closed_line(K, L, t, happy=False):
    """the closed eye: a gentle downward arc (blink) or an upward one (a smile's closed eye)."""
    W = K['width'] * L
    x, zb = outline(K, L, t, 'lower')
    base = x * math.tan(math.radians(K['tilt'])) - K['inner_drop'] * W * (1 - np.asarray(t)) ** 2
    arc = np.sin(np.pi * np.asarray(t)) * 0.10 * W
    return x, (base + arc * 1.6 if happy else base - arc)


# ------------------------------------------------------------------------------------------------------------ placement
class Face:
    """the anime face surface in world: surf(x, z) -> the point on it at world x, z (front half), for placing features."""

    def __init__(self, H, centre):
        self.H = headlib.Head(H.L, H.K, features=False)
        self.c = np.asarray(centre)

    def point(self, x, z):
        zr = z - self.c[2]
        a = ah.surface_azimuth(self.H, x, zr, hi=math.pi * 0.62)
        return self.H.surface(a, zr) + self.c

    def y(self, x, z):
        return self.point(x, z)[1]

    def normal(self, x, z, e=1e-4):
        p = self.point(x, z)
        dx = self.point(x + e, z) - p; dz = self.point(x, z + e) - p
        n = np.cross(dz, dx)
        return n / np.linalg.norm(n) * (-1 if n[1] > 0 else 1)


def spread(src_old, disp, pts, floor=0.003, k=1.6):
    """a margin's displacement spread onto nearby points: nearest-weighted, fading by a Gaussian whose radius scales with the
    largest move (k times it), so the field's gradient stays below 1 and the skin can't fold over the opening."""
    amp = float(np.linalg.norm(disp, axis=1).max()) if len(disp) else 0.0
    R = max(floor, k * amp)
    out = np.zeros((len(pts), disp.shape[1]))
    for i, p in enumerate(pts):
        d = np.linalg.norm(src_old - p, axis=1)
        w = 1 / np.maximum(d, 1e-5) ** 3
        out[i] = (w[:, None] * disp).sum(0) / w.sum() * math.exp(-(d.min() / R) ** 2)
    return out


def _world(F, ex, ez, side, x, z, depth=0.0):
    """eye-local (x, z) -> world, on the face surface, pushed back by depth along the view (y)."""
    X = ex + side * np.asarray(x); Z = ez + np.asarray(z)
    P = np.array([F.point(a, b) for a, b in zip(np.atleast_1d(X), np.atleast_1d(Z))])
    P[:, 1] += depth
    return P


def _margin_params(V, eye, side):
    """t (0 inner .. 1 outer) for each margin vertex of the upper and lower halves, by x along the eye."""
    out = {}
    for which in ('upper', 'lower'):
        ch = eye[which]
        xs = V[ch, 0] * side
        t = (xs - xs[0]) / max(1e-9, xs[-1] - xs[0])
        out[which] = np.clip(np.maximum.accumulate(t), 0, 1)
    return out


def place(V, eye, F, K, L, side, eye_c):
    """move one eye's margin onto the anime outline, the outer rings after it (on the face surface), the pocket into a funnel
    behind the plate. -> (new V, margin targets {vertex: world})."""
    V = V.copy()
    ex, ez = eye_c
    tp = _margin_params(V, eye, side)
    tgt = {}
    for which in ('upper', 'lower'):
        x, z = outline(K, L, tp[which], which)
        P = _world(F, ex, ez, side, x, z)
        for v, p in zip(eye[which], P):
            tgt[v] = p
    m = np.array(eye['margin'])
    old = V[m].copy()
    new = np.array([tgt[v] for v in m])
    dxz = (new - old)[:, [0, 2]]
    # outer rings: the margin's in-surface motion, fading; re-seated on the face at their old depth offset
    ov = np.array(list(eye['outer'].keys()))
    mvs = spread(old[:, [0, 2]], dxz, V[ov][:, [0, 2]])
    for v, mv in zip(ov, mvs):
        off = V[v, 1] - F.y(V[v, 0], V[v, 2])
        x2, z2 = V[v, 0] + mv[0], V[v, 2] + mv[1]
        V[v] = [x2, F.y(x2, z2) + off, z2]
    for v, p in tgt.items():
        V[v] = p
    # the pocket: a funnel from the margin back behind the plate (the lid's thickness, then the back wall). An anime base's
    # shallow socket (charkit/base_anime.py) says per vertex: its margin vertex, the pull toward the centre and the depth.
    depth = K['depth'] * L
    cen = np.array([ex, ez])
    sock = eye.get('socket') or {}
    mi = {v: j for j, v in enumerate(m)}
    for v, r in eye['pocket'].items():
        if v in sock:
            src, pull, dz = sock[v]
            mp = new[mi[src]]
        else:
            j = int(np.argmin(np.linalg.norm(old - V[v], axis=1)))    # nearest margin vertex (by old positions)
            mp = new[j]
            pull = min(0.92, 0.05 + 0.13 * (r - 1))
            dz = 0.0012 + 0.0022 * (r - 1) ** 0.8
        x2 = mp[0] + (cen[0] - mp[0]) * pull
        z2 = mp[2] + (cen[1] - mp[2]) * pull
        V[v] = [x2, F.y(x2, z2) + depth + dz, z2]
    return V, tgt


# ---------------------------------------------------------------------------------------------------------------- plate
def outline_polygon(K, L, n=24):
    """the closed outline (upper inner -> outer, lower outer -> inner), eye-local (M, 2)."""
    t = np.linspace(0, 1, n)
    xu, zu = outline(K, L, t, 'upper')
    xl, zl = outline(K, L, t[::-1], 'lower')
    return np.concatenate([np.stack([xu, zu], 1), np.stack([xl, zl], 1)[1:-1]])


def plate(F, K, L, side, eye_c, na=48, nr=10, reach=1.18, shift=(0.0, 0.0), bias=0.0):
    """the eye plate behind the opening: a patch shaped like the outline (rings out to `reach` times it), recessed and bending
    back at its rim so it never shows through the skin; UV in eye units (u = x / W + 0.5, outward; v = z / W + 0.5).
    shift: move it in the eye plane (gaze). -> (verts, faces, uvs per vertex)."""
    W = K['width'] * L
    poly = outline_polygon(K, L)
    oc = poly.mean(0)                                           # the outline's centre (eye-local)
    ang = np.arctan2(poly[:, 1] - oc[1], poly[:, 0] - oc[0])
    rad = np.linalg.norm(poly - oc, axis=1)
    o = np.argsort(ang)
    ang, rad = ang[o], rad[o]
    ang = np.concatenate([ang[-1:] - 2 * np.pi, ang, ang[:1] + 2 * np.pi])
    rad = np.concatenate([rad[-1:], rad, rad[:1]])
    th = np.linspace(-np.pi, np.pi, na, endpoint=False)
    R = np.interp(th, ang, rad)
    ex, ez = eye_c
    D0 = K['depth'] * L - bias
    pts, uvs = [], []
    loc = [oc]
    for j in range(1, nr + 1):
        rho = reach * j / nr
        for k in range(na):
            loc.append(oc + rho * R[k] * np.array([math.cos(th[k]), math.sin(th[k])]))
    loc = np.array(loc)
    rho_of = np.concatenate([[0.0], np.repeat(reach * np.arange(1, nr + 1) / nr, na)])
    depth = D0 + 0.004 * L * np.clip((rho_of - 0.92) / (reach - 0.92), 0, 1) ** 2
    for (x, z), d in zip(loc, depth):
        pts.append(_world(F, ex, ez, side, [x + shift[0]], [z + shift[1]], depth=d)[0])
        uvs.append((x / W + 0.5, z / W + 0.5))
    faces = []
    for k in range(na):                                         # the centre fan
        f = (0, 1 + k, 1 + (k + 1) % na)
        faces.append(f if side > 0 else f[::-1])
    for j in range(nr - 1):
        for k in range(na):
            a0 = 1 + j * na + k; a1 = 1 + j * na + (k + 1) % na
            f = (a0, a0 + na, a1 + na, a1)
            faces.append(f[::-1] if side > 0 else f)
    return np.array(pts), faces, uvs


# ---------------------------------------------------------------------------------------------------------------- lashes
def _ribbon(F, side, eye_c, pts, thick, normal_sign, lift=-0.0006, tuck=0.35):
    """a ribbon along eye-local points (N,2) with per-point thickness, offset along the 2D normal (away from the eye); its
    inner edge tucked a little over the opening. -> (verts, quads)."""
    pts = np.asarray(pts)
    tan = np.gradient(pts, axis=0)
    tan /= np.maximum(np.linalg.norm(tan, axis=1, keepdims=True), 1e-12)
    nrm = np.stack([-tan[:, 1], tan[:, 0]], 1) * normal_sign
    inner = pts - nrm * thick[:, None] * tuck
    outer = pts + nrm * thick[:, None] * (1 - tuck)
    ex, ez = eye_c
    Vi = _world(F, ex, ez, side, inner[:, 0], inner[:, 1], depth=lift)
    Vo = _world(F, ex, ez, side, outer[:, 0], outer[:, 1], depth=lift)
    n = len(pts)
    verts = np.vstack([Vi, Vo])
    quads = []
    for i in range(n - 1):
        q = (i, i + 1, n + i + 1, n + i)
        quads.append(q if side * normal_sign > 0 else q[::-1])
    return verts, quads


def lashes(F, K, L, side, eye_c, upper_fn=None, lower_fn=None, n=40):
    """upper lash line (thick, tapering in toward the inner corner, a flick past the outer corner) and a lower lash (the
    outer part), along the outline or along given lid curves (functions t -> eye-local (x, z), for the shape keys).
    -> list of (verts, quads) ribbons."""
    W = K['width'] * L
    upper_fn = upper_fn or (lambda t: outline(K, L, t, 'upper'))
    lower_fn = lower_fn or (lambda t: outline(K, L, t, 'lower'))
    t = np.linspace(0.03, 1.0, n)
    x, z = upper_fn(t)
    th = K['lash'] * L * (K['lash_inner'] + (1 - K['lash_inner']) * np.clip(t / 0.45, 0, 1) ** 0.7)
    # the flick: continue past the outer corner, up and out, tapering
    ang = math.radians(K['flick_angle'] + K['tilt'])
    s = np.linspace(0, 1, 11)[1:]
    fx = x[-1] + np.cos(ang) * K['flick'] * W * s
    fz = z[-1] + np.sin(ang) * K['flick'] * W * s ** 1.6          # curving up at its end
    fth = th[-1] * (1 - s) ** 1.2 + 1e-5
    up = _ribbon(F, side, eye_c, np.stack([np.concatenate([x, fx]), np.concatenate([z, fz])], 1),
                 np.concatenate([th, fth]), 1.0)
    t2 = np.linspace(1 - K['lower_lash'], 1.0, 16)
    x2, z2 = lower_fn(t2)
    th2 = K['lash'] * L * K['lower_lash_w'] * np.sin(np.pi * 0.5 * (t2 - t2[0]) / (t2[-1] - t2[0])) ** 0.8 + 1e-5
    lo = _ribbon(F, side, eye_c, np.stack([x2, z2], 1), th2, -1.0)
    out = [up, lo]
    if K.get('crease', 0) > 0:
        # the double-lid crease: a thin line above the lash over its middle and outer part, following the lid
        t3 = np.linspace(0.22, 0.92, 24)
        x3, z3 = upper_fn(t3)
        lift_ = K['lash'] * L + K['crease'] * W
        th3 = K['crease_w'] * L * np.sin(np.pi * (t3 - t3[0]) / (t3[-1] - t3[0])) ** 0.7 + 1e-5
        out.append(_ribbon(F, side, eye_c, np.stack([x3, z3 + lift_ * np.sin(np.pi * (0.2 + 0.8 * t3)) ** 0.3], 1), th3,
                           1.0, tuck=0.5))
    return out


# ------------------------------------------------------------------------------------------------------------ shape keys
def lid_key(V, eye, F, K, L, side, eye_c, upper_to=None, lower_to=None):
    """offsets (N,3) moving the upper and/or lower margin to target curves (functions t -> (x, z) eye-local), the outer rings
    and the near pocket after them, on the face surface. The base pose is V (already placed)."""
    ex, ez = eye_c
    D = np.zeros_like(V)
    tp = _margin_params(V, eye, side)
    moved = {}
    for which, fn in (('upper', upper_to), ('lower', lower_to)):
        if fn is None:
            continue
        x, z = fn(tp[which])
        P = _world(F, ex, ez, side, x, z)
        for v, p in zip(eye[which], P):
            if v not in moved:
                moved[v] = p - V[v]
    if not moved:
        return D
    mv = np.array(list(moved.keys()))
    md = np.array([moved[v] for v in mv])
    for v, d in zip(mv, md):
        D[v] = d
    src = V[mv]
    ov = np.array(list(eye['outer'].keys()))
    for v, d in zip(ov, spread(src, md, V[ov])):
        x2, z2 = V[v, 0] + d[0], V[v, 2] + d[2]
        off = V[v, 1] - F.y(V[v, 0], V[v, 2])
        D[v] = np.array([x2, F.y(x2, z2) + off, z2]) - V[v]
    sock = eye.get('socket') or {}
    dm = D[np.array(eye['margin'])].mean(0)
    for v, r in eye['pocket'].items():
        if v in sock:                                              # a socket vertex: its margin vertex's move, the cap the mean
            m_, pull, _ = sock[v]
            D[v] = D[m_] * (1 - pull) + dm * pull
            continue
        dd = np.linalg.norm(src - V[v], axis=1)
        w = 1 / np.maximum(dd, 1e-5) ** 4
        D[v] = (w[:, None] * md).sum(0) / w.sum() * max(0.0, 1.0 - 0.18 * (r - 1))
    return D


def labels(base, side):
    """an eye's topology from a derived base's stored labels (charkit/base_anime.py) instead of detect(): the same dict, plus
    'socket' {vertex: (margin vertex, pull, depth)} for its shallow socket. side: 1 her left, -1 her right."""
    return base.eye(side)


def expressions(K, L):
    """named lid shapes: {name: (upper_to, lower_to)} as eye-local curve functions of t."""
    def up(k):
        return lambda t: outline(_knobs({**K, **k}), L, t, 'upper')

    def lo(k):
        return lambda t: outline(_knobs({**K, **k}), L, t, 'lower')

    def closed(happy=False):
        return lambda t: closed_line(K, L, t, happy)
    return {
        # closed: the upper lid comes down a touch past the lower one (the lash line covers the seam)
        'blink': (lambda t: (closed_line(K, L, t)[0], closed_line(K, L, t)[1] - 0.003 * L), closed()),
        'happy': (lambda t: (closed_line(K, L, t, True)[0], closed_line(K, L, t, True)[1] - 0.003 * L), closed(True)),
        'half': (up({'height': K['height'] * 0.72, 'lower': K['lower'] / 0.72 * 1.0}), None),
        'wide': (up({'height': K['height'] * 1.14, 'lower': K['lower'] / 1.14}), lo({'height': K['height'] * 1.06})),
        'angry': (up({'peak': min(0.85, K['peak'] + 0.3), 'tilt': K['tilt'] + 9, 'height': K['height'] * 0.86,
                      'lower': K['lower'] / 0.86}), None),
        'sad': (up({'peak': max(0.15, K['peak'] - 0.2), 'tilt': K['tilt'] - 9, 'height': K['height'] * 0.9,
                    'lower': K['lower'] / 0.9}), None),
        'squint': (up({'height': K['height'] * 0.8, 'lower': K['lower'] / 0.8}),
                   lo({'height': K['height'] * 0.72, 'lower': K['lower'] * 0.6})),
    }
