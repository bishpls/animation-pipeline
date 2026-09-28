"""The anime mouth (docs/CHARKIT.md §2, face features): MakeHuman's mouth loop (the lips' parting, from corner to corner along
the upper and the lower lip) re-shaped onto knob-driven curves; the neutral mouth a closed line (a hair's gap onto the dark
cavity reads as the drawn mouth line); the visemes and expression mouths as other curves; the lip rings, the cavity funnel,
the jaw, the teeth and the tongue following. Mouth-local coordinates: x across (+ = her left), z up, metres, from the mouth
centre on the face.
"""
import heapq
import math
from collections import deque

import numpy as np

from . import anime_head as ah, eyes as eyelib

DEFAULT_MOUTH = {
    'width': 0.11,      # corner to corner, in L
    'smile': 0.08,      # corner lift of the neutral line, in widths
    'gap': 0.004,       # the closed mouth's line: the gap onto the cavity (at the middle), in L
    'depth': 0.05,      # the cavity's depth behind the lips, in L
    'teeth': 0.13,      # the upper teeth's visible height when open, in widths
    'jaw': 0.45,        # how much the jaw follows the lower lip when open
}

RINGS = 9                                  # outer rings that can follow the lips (the spread decides how far)


# ---------------------------------------------------------------------------------------------------------------- topology
def detect(Vb, faces, lips, upper_w, lower_w):
    """Vb the base mesh's body vertices; lips: the lips' centre; upper_w/lower_w (N,): the upper and lower lip bones' weights.
    -> dict(corners (left, right), upper, lower (left -> right, corners included), cavity {v: ring}, outer {v: ring})."""
    n = len(Vb)
    nb = eyelib._adj(n, faces)
    nrm = ah.vertex_normals(Vb, faces)
    reg = [i for i in range(n) if np.linalg.norm(Vb[i] - lips) < 0.035 and Vb[i, 1] < lips[1] + 0.012]
    fold = {i: min(float(nrm[i] @ nrm[j]) for j in nb[i]) for i in reg}
    cand = [i for i in reg if fold[i] < 0.2 and abs(Vb[i, 2] - lips[2]) < 0.006]
    corners = sorted((min(c, key=lambda u: Vb[u, 1]) for c in eyelib._components(set(cand), nb)), key=lambda u: Vb[u, 0])
    if len(corners) != 2:
        raise RuntimeError('mouth corners: expected 2, found %d' % len(corners))

    def path(allowed, zref=None):
        src, dst = corners
        dist, prev, pq = {src: 0.0}, {}, [(0.0, src)]
        while pq:
            d, u = heapq.heappop(pq)
            if u == dst:
                break
            if d > dist[u]:
                continue
            for w in nb[u]:
                if w not in allowed and w != dst:
                    continue
                c = np.linalg.norm(Vb[u] - Vb[w])
                if zref is not None:
                    c += 3.0 * abs(Vb[w, 2] - np.interp(Vb[w, 0], *zref))
                if d + c < dist.get(w, 1e9):
                    dist[w] = d + c; prev[w] = u; heapq.heappush(pq, (d + c, w))
        p = [dst]
        while p[-1] != src:
            p.append(prev[p[-1]])
        return p[::-1]
    near = [i for i in reg if abs(Vb[i, 2] - lips[2]) < 0.005]
    upper = path({i for i in near if upper_w[i] >= lower_w[i]})
    zref = (Vb[upper, 0], Vb[upper, 2])
    lower = path({i for i in near if lower_w[i] > upper_w[i]}, zref)
    loop = set(upper) | set(lower)
    # the cavity: what the loop cuts off, seeded behind the lips
    seed = int(np.argmin(np.linalg.norm(Vb - (lips + np.array([0, 0.035, 0.0])), axis=1)))
    cav, q = {seed}, deque([seed])
    while q:
        u = q.popleft()
        for w in nb[u]:
            if w not in loop and w not in cav:
                cav.add(w); q.append(w)
    if len(cav) > 3000:
        raise RuntimeError('mouth cavity not cut off by the loop (%d)' % len(cav))
    ring = {u: 0 for u in loop}
    q = deque(loop)
    while q:
        u = q.popleft()
        for w in nb[u]:
            if w in cav and w not in ring:
                ring[w] = ring[u] + 1; q.append(w)
    cavity = {u: r for u, r in ring.items() if r > 0}
    outer, q = {u: 0 for u in loop}, deque(loop)
    while q:
        u = q.popleft()
        if outer[u] >= RINGS:
            continue
        for w in nb[u]:
            if w not in outer and w not in cav:
                outer[w] = outer[u] + 1; q.append(w)
    outer = {u: r for u, r in outer.items() if r > 0}
    # which lip each outer and cavity vertex belongs to: geodesically nearest chain (corners count for both)
    side = {}
    q = deque()
    for u in upper[1:-1]:
        side[u] = 'u'; q.append(u)
    for u in lower[1:-1]:
        side[u] = 'l'; q.append(u)
    for u in corners:
        side[u] = 'c'
    keep = set(outer) | set(cavity)
    while q:
        u = q.popleft()
        for w in nb[u]:
            if w in keep and w not in side:
                side[w] = side[u]; q.append(w)
    return dict(corners=corners, upper=upper, lower=lower, cavity=cavity, outer=outer, side=side)


# ------------------------------------------------------------------------------------------------------------------ shapes
def _knobs(k):
    K = dict(DEFAULT_MOUTH); K.update(k or {})
    return K


# a mouth shape: width (share of the neutral), open (height, in widths), up (upper lip rise share of the opening), corner
# (corner lift, in widths), upper_round/lower_round (0 flat .. 1 round), smile (the line's curve for closed shapes)
SHAPES = {
    'neutral': dict(width=1.0, open=0.0),
    'aa': dict(width=0.78, open=0.62, up=0.18, corner=0.02, upper_round=0.35, lower_round=1.0),
    'ih': dict(width=1.05, open=0.20, up=0.35, corner=0.06, upper_round=0.2, lower_round=0.6),
    'ou': dict(width=0.46, open=0.32, up=0.4, corner=0.0, upper_round=0.9, lower_round=0.9),
    'ee': dict(width=0.98, open=0.32, up=0.3, corner=0.05, upper_round=0.25, lower_round=0.75),
    'oh': dict(width=0.62, open=0.48, up=0.3, corner=0.0, upper_round=0.8, lower_round=0.95),
    'smile': dict(width=1.08, open=0.0, smile=0.22),
    'grin': dict(width=1.12, open=0.36, up=0.12, corner=0.16, upper_round=0.1, lower_round=1.0),
    'frown': dict(width=0.92, open=0.0, smile=-0.18),
    'surprised': dict(width=0.5, open=0.5, up=0.35, corner=0.0, upper_round=0.9, lower_round=0.9),
    'pout': dict(width=0.62, open=0.0, smile=-0.04),
}


def curves(K, L, shape):
    """(upper(t), lower(t)): mouth-local (x, z) of the upper and lower lip edge at t (0 = her right corner .. 1 = her left)."""
    S = dict(SHAPES['neutral']); S.update(SHAPES[shape] if isinstance(shape, str) else shape)
    W = K['width'] * L * S['width']
    smile = S.get('smile', K['smile'])
    op = S['open'] * K['width'] * L
    up = S.get('up', 0.3)
    corner = S.get('corner', 0.0) * K['width'] * L

    def base(t):
        x = -W / 2 + W * np.asarray(t, float)
        u = 2 * x / W
        return x, smile * W * u * u + corner * u * u
    gap = K['gap'] * L

    def upper(t):
        x, z = base(t)
        s = np.sin(np.pi * np.asarray(t, float))
        prof = s ** (1.0 - 0.7 * S.get('upper_round', 0.5)) if op > 0 else 0 * s
        return x, z + op * up * prof

    def lower(t):
        x, z = base(t)
        s = np.sin(np.pi * np.asarray(t, float))
        prof = s ** (1.0 - 0.7 * S.get('lower_round', 0.8)) if op > 0 else 0 * s
        return x, z - gap * s ** 0.8 - op * (1 - up) * prof
    return upper, lower


# --------------------------------------------------------------------------------------------------------------- placement
def _params(V, chain):
    xs = V[chain, 0]
    return np.clip(np.maximum.accumulate((xs - xs[0]) / max(1e-9, xs[-1] - xs[0])), 0, 1)


def _pose(V, M, F, K, L, mc, shape, outer=True):
    """positions for the loop, the outer rings and the cavity for a shape. -> {v: position}."""
    up_f, lo_f = curves(K, L, shape)
    pos = {}
    for chain, fn in ((M['upper'], up_f), (M['lower'], lo_f)):
        x, z = fn(_params(V, chain))
        P = eyelib._world(F, mc[0], mc[1], 1.0, x, z)
        for v, p in zip(chain, P):
            if v not in pos:
                pos[v] = p
    loop = np.array(list(pos.keys()))
    new = np.array([pos[v] for v in loop])
    old = V[loop]
    d = new - old
    # each lip's skin follows its own edge (the lips are millimetres apart; mixing them folds the skin over the opening)
    chains = {'u': np.array(M['upper']), 'l': np.array(M['lower'])}
    idx = {v: i for i, v in enumerate(loop)}
    if outer:
        for sd in ('u', 'l'):
            ov = np.array([v for v in M['outer'] if M['side'].get(v, 'u') == sd], int)
            if not len(ov):
                continue
            ch = chains[sd]
            ci = np.array([idx[v] for v in ch])
            mv = eyelib.spread(old[ci], d[ci], V[ov])
            for v, m_ in zip(ov, mv):
                off = V[v, 1] - F.y(V[v, 0], V[v, 2])
                x2, z2 = V[v, 0] + m_[0], V[v, 2] + m_[2]
                pos[v] = np.array([x2, F.y(x2, z2) + off, z2])
    # the cavity: a funnel back from the loop toward a point behind the mouth's centre
    ctr = np.array([mc[0], 0.0, mc[1]])
    xs_open = new[:, [0, 2]]
    oc = xs_open.mean(0)
    depth = K['depth'] * L
    rmax = max(M['cavity'].values())
    for v, r in M['cavity'].items():
        sd = M['side'].get(v, 'u')
        ci = np.array([idx[u] for u in chains['l' if sd == 'l' else 'u']])
        j = ci[int(np.argmin(np.linalg.norm(old[ci] - V[v], axis=1)))]
        mp = new[j]
        f = min(1.0, r / max(3, rmax * 0.7))
        pull = 0.15 + 0.55 * f
        x2 = mp[0] + (oc[0] - mp[0]) * pull
        z2 = mp[2] + (oc[1] - mp[2]) * pull
        pos[v] = np.array([x2, F.y(x2, z2) + 0.0015 + depth * f ** 0.8, z2])
    return pos


def place(V, M, F, K, L, mc):
    """the neutral mouth. -> new V."""
    V = V.copy()
    for v, p in _pose(V, M, F, K, L, mc, 'neutral').items():
        V[v] = p
    return V


def key(V, M, F, K, L, mc, shape, jaw_w=None):
    """offsets (N, 3) from the placed neutral V to a shape (the jaw following the lower lip when it opens)."""
    D = np.zeros_like(V)
    for v, p in _pose(V, M, F, K, L, mc, shape).items():
        D[v] = p - V[v]
    if jaw_w is not None:
        _, lo_n = curves(K, L, 'neutral'); _, lo_s = curves(K, L, shape)
        drop = lo_n(0.5)[1] - lo_s(0.5)[1]
        if drop > 0:
            mv = set(M['upper']) | set(M['lower']) | set(M['outer']) | set(M['cavity'])
            free = np.array([i for i in np.nonzero(jaw_w > 1e-3)[0] if i not in mv], int)
            D[free, 2] -= jaw_w[free] * drop * K['jaw']
    return D


# ------------------------------------------------------------------------------------------------------ teeth and tongue
def line(F, K, L, mc, shape='neutral', n=32):
    """the drawn mouth line: a thin ribbon along the upper lip's edge, fullest in the middle, tapering into the corners
    (the anime mouth is a line; open shapes keep it as the opening's top edge). -> (verts, quads)."""
    up_f, _ = curves(K, L, shape)
    t = np.linspace(0.02, 0.98, n)
    x, z = up_f(t)
    th = K.get('line_w', 0.0075) * L * (0.35 + 0.65 * np.sin(np.pi * t) ** 0.6)
    return eyelib._ribbon(F, 1.0, mc, np.stack([x, z], 1), th, 1.0, lift=-0.0004, tuck=0.6)


def teeth(F, K, L, mc, shape='neutral', n=24):
    """the upper teeth: a white band just behind the upper lip's edge, following its curve. -> (verts, quads)."""
    up_f, _ = curves(K, L, shape)
    S = dict(SHAPES['neutral']); S.update(SHAPES[shape])
    t = np.linspace(0.12, 0.88, n)
    x, z = up_f(t)
    h = K['teeth'] * K['width'] * L * min(1.0, S['open'] / 0.3)       # closed: tucked up behind the upper lip
    top = eyelib._world(F, mc[0], mc[1], 1.0, x * 0.97, z + K['teeth'] * K['width'] * L * 0.6, depth=0.0022)
    bot = eyelib._world(F, mc[0], mc[1], 1.0, x * 0.97, z - h + (0.0015 if h > 0 else 0.006) * L, depth=0.0022)
    verts = np.vstack([top, bot])
    quads = [(i, n + i, n + i + 1, i + 1) for i in range(n - 1)]
    return verts, quads


def tongue(F, K, L, mc, shape='neutral', nu=14, nv=6):
    """the tongue: a rounded pad at the bottom of the cavity, riding the lower lip. -> (verts, quads)."""
    _, lo_f = curves(K, L, shape)
    W = K['width'] * L
    t = np.linspace(0.2, 0.8, nu)
    x, zl = lo_f(t)
    verts = []
    for j in range(nv):
        s = j / (nv - 1)
        zz = zl + 0.002 * L + s * 0.06 * W - (1 - np.sin(np.pi * (t - 0.2) / 0.6)) * 0.03 * W
        verts.append(eyelib._world(F, mc[0], mc[1], 1.0, x * (0.9 - 0.25 * s), zz, depth=0.004 + 0.012 * L * s))
    verts = np.vstack(verts)
    quads = [(j * nu + i, j * nu + i + 1, (j + 1) * nu + i + 1, (j + 1) * nu + i) for j in range(nv - 1) for i in range(nu - 1)]
    return verts, quads
