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
    'teeth': 0.16,      # the upper teeth's visible height, a share of the opening's tallest (a shape's 'teeth' overrides)
    'tongue': 0.34,     # the tongue's visible height over the lower lip, a share of the opening's tallest (a shape's
                        # 'tongue' overrides)
    'line_lo': 0.5,     # the lower lip's line (open mouths: the drawn mouth's outline), a share of the upper line's width
    'jaw': 0.45,        # how much the jaw follows the lower lip when open
    'rest': {},         # the neutral (rest) mouth's own shape over SHAPES['neutral'] (no other shape inherits it): width
                        # (in widths), smile, gap (L), line_w (L), drop (L: the whole mouth set this much lower in the
                        # head's mouth block; every shape follows it). Michael's flag (2026-09-30): the default smile
                        # was off-model, a short open D; the design draws a long, thin, closed smile line
    'jaw_follow': 0.3,  # the same on an authored base, whose jaw region moves whole (the lips' rings take the rest): the
                        # dial between a jaw that drops (1) and the drawn heads' kept outline (0); 0.6 -> 0.3 took the
                        # laugh's chin drop 0.096 -> 0.069 L with every key's folds 0 (docs/workstreams/mouth.md)
    'view': {},         # the drawn placement as a per-shot override (VIEW; Michael, 2026-10-01): empty, none built
}

# The mouth's placement as the drawings place it, a per-shot override of the rigid head's (Michael, 2026-10-01: the rigid
# placement is the default; the three-quarter's drawn placement is the drawing's own, about 0.025 L of the 0.075 L
# miss, and a shot may ask for it). Two keys slide the whole mouth (the lips' loop and rings on the skin, the line, the
# teeth, the tongue) along the face toward her left (view_mouth_L) or her right (view_mouth_R), `slide` L of front-view x
# at weight 1. Nothing drives them by default: a shot sets their weights (view_weights: the curve at its camera's yaw
# times its setting), or binds Blender drivers to its camera (charkit.character.drive_view_mouth).
VIEW = {'slide': 0.0,                     # L of front-view x at weight 1 (0: no keys)
        'curve': [[0.0, 0.0], [35.7, 1.0], [90.0, 0.0]]}   # the weight per camera yaw from the face's front (degrees,
                                                           # |yaw|, linear between; the camera on her left (+yaw) slides
                                                           # the mouth toward her left: the drawn three-quarter's mouth
                                                           # sits nearer the eyes' midpoint than a rigid muzzle puts it)
VIEW_KEYS = ('view_mouth_L', 'view_mouth_R')


def view_knobs(K):
    """the view override's knobs (VIEW, the spec's mouth.view over them) -> dict, or None when it builds no keys."""
    V = dict(VIEW); V.update((K or {}).get('view') or {})
    return V if float(V.get('slide') or 0.0) != 0.0 else None


def view_weights(K, yaw, setting=1.0):
    """the view keys' weights for a camera at `yaw` degrees from the face's front (+ on her left, as the QA's azimuth)
    and a shot's setting (0: the rigid placement, the default; 1: the drawn) -> {key: weight}."""
    V = view_knobs(K)
    if V is None:
        return {}
    c = np.asarray(V['curve'], float)
    w = float(np.interp(min(abs(float(yaw)), 180.0), c[:, 0], c[:, 1])) * float(setting)
    return {'view_mouth_L': w if yaw > 0 else 0.0, 'view_mouth_R': w if yaw < 0 else 0.0}

RINGS = 9                                  # outer rings that can follow the lips (the spread decides how far)
JAW_CORE = 0.98                            # an authored base's jaw weight from which the skin moves with the jaw whole


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


def labels(base):
    """the mouth's topology from a derived base's stored labels (charkit/base_anime.py) instead of detect(): the same dict,
    plus 'cavity_src' {vertex: (loop vertex, depth share, pull)} for its compact cavity."""
    return base.mouth()


# ------------------------------------------------------------------------------------------------------------------ shapes
def _knobs(k):
    K = dict(DEFAULT_MOUTH); K.update(k or {})
    return K


# a mouth shape: width (share of the neutral), open (height, in widths), up (upper lip rise share of the opening), corner
# (corner lift, in widths), upper_round/lower_round (0 flat .. 1 round), smile (the line's curve for closed shapes), wave
# (both lips' wobble, in widths, zero at the corners; `waves` across the mouth, symmetric about its middle), skew (her left
# corner raised this many widths, her right kept: a smirk); what the opening shows: teeth (the upper teeth's height, a
# share of the opening's tallest; default the 'teeth' knob), teeth_lo (the lower teeth's), tongue (the tongue's height
# over the lower lip, a share; default the 'tongue' knob)
SHAPES = {
    'neutral': dict(width=1.0, open=0.0),
    'aa': dict(width=0.78, open=0.62, up=0.18, corner=0.02, upper_round=0.35, lower_round=1.0),
    'ih': dict(width=1.05, open=0.20, up=0.35, corner=0.06, upper_round=0.2, lower_round=0.6),
    'ou': dict(width=0.46, open=0.32, up=0.4, corner=0.0, upper_round=0.9, lower_round=0.9),
    'ee': dict(width=0.98, open=0.32, up=0.3, corner=0.05, upper_round=0.25, lower_round=0.75),
    'oh': dict(width=0.62, open=0.48, up=0.3, corner=0.0, upper_round=0.8, lower_round=0.95),
    'smile': dict(width=1.08, open=0.0, smile=0.22),
    'grin': dict(width=1.12, open=0.36, up=0.12, corner=0.16, upper_round=0.1, lower_round=1.0),
    # the angry head's mouth on the model sheet: a short, gently downturned line (0.135 L wide, corners 0.07 of its width
    # under its middle)
    'frown': dict(width=1.0, open=0.0, smile=-0.1),
    'surprised': dict(width=0.5, open=0.5, up=0.35, corner=0.0, upper_round=0.9, lower_round=0.9),
    'pout': dict(width=0.62, open=0.0, smile=-0.04),
    # the model sheet's heads, at their drawn sizes (idol_D measured by charkit.exprqa, in the neutral's widths; the
    # authored head's lips follow these curves, where MakeHuman's lapped over about half of an open mouth). laugh: a wide
    # bowl (0.26 x 0.15 L: the top a smile's curve with the upper teeth along it, the bottom a round U, the tongue in it;
    # fitted to the drawn head with its shape, mouthlab.fit_shape: IoU 0.75 -> 0.92, round 2)
    'laugh': dict(width=2.0, open=1.0, up=0.0, corner=0.0, smile=0.06, upper_round=0.35, lower_round=1.0),
    # fluster: wide, low and wavy, both rows of teeth showing (0.27 x 0.07 L)
    'wavy': dict(width=2.0, open=0.55, up=0.45, corner=-0.03, smile=-0.02, upper_round=0.3, lower_round=0.45, wave=0.08,
                 waves=2.5, teeth=0.3, teeth_lo=0.3, tongue=0.0),
    # yawn: a tall oval (0.17 x 0.18 L), its corners at its middle's height, its sides round (fitted with its shape: IoU
    # 0.92 -> 0.97, round 2). Its upper lip rises 0.54 widths (open x up), the
    # old yawn's to the last bit: the mouth block's top. code_base.mouth_block sizes the head's cage by the library's
    # extremes (this top, the laugh's half-width): keep them, or the head's mesh moves round the mouth
    # (tests/test_mouth.py holds the block)
    'yawn': dict(width=1.28, open=1.38, up=0.391304347826087, corner=-0.07, smile=0.0, upper_round=0.6,
                 lower_round=0.95, teeth=0.1),
    # the action set (docs/workstreams/mouth.md; exprqa.TARGETS), each with its own smile (a shape without one takes the
    # spec's, Clawd's 0.22: a grin's curve). shout: wide open, a flatter top, the upper teeth and the tongue showing
    'shout': dict(width=1.6, open=1.3, up=0.3, corner=-0.04, smile=0.0, upper_round=0.35, lower_round=0.7, teeth=0.18,
                  tongue=0.3),
    # clench (effort): stretched wide, barely parted, both rows of teeth filling it, a dark seam between
    'clench': dict(width=1.45, open=0.32, up=0.45, corner=-0.03, smile=-0.02, upper_round=0.15, lower_round=0.15, teeth=0.5,
                   teeth_lo=0.42, tongue=0.0),
    # grimace (pain): as the clench, the corners pulled down
    'grimace': dict(width=1.4, open=0.36, up=0.4, corner=-0.12, smile=-0.08, upper_round=0.2, lower_round=0.35, teeth=0.48,
                    teeth_lo=0.4, tongue=0.0),
    # smirk (smug): closed, her left corner up
    'smirk': dict(width=1.0, open=0.0, smile=0.08, skew=0.16),
    # firm (focus): a short straight line, the corners a touch down
    'firm': dict(width=0.85, open=0.0, smile=-0.04),
    # wobble (embarrassed): small, a little open, wavy
    'wobble': dict(width=1.1, open=0.28, up=0.5, corner=-0.02, upper_round=0.4, lower_round=0.5, wave=0.07, waves=2.5,
                   teeth=0.0, tongue=0.25),
}


def shape_of(K, shape):
    """a shape's parameters: SHAPES['neutral']'s, the shape's over them, and for the neutral itself the spec's `rest`
    over those (the rest mouth's own shape; no other shape inherits it)."""
    S = dict(SHAPES['neutral']); S.update(SHAPES[shape] if isinstance(shape, str) else shape)
    if shape == 'neutral':
        S.update({k: v for k, v in ((K or {}).get('rest') or {}).items() if k != 'drop'})
    return S


def curves(K, L, shape):
    """(upper(t), lower(t)): mouth-local (x, z) of the upper and lower lip edge at t (0 = her right corner .. 1 = her left)."""
    S = shape_of(K, shape)
    W = K['width'] * L * S['width']
    smile = S.get('smile', K['smile'])
    op = S['open'] * K['width'] * L
    up = S.get('up', 0.3)
    corner = S.get('corner', 0.0) * K['width'] * L

    skew = S.get('skew', 0.0) * K['width'] * L

    def base(t):
        x = -W / 2 + W * np.asarray(t, float)
        u = 2 * x / W
        return x, smile * W * u * u + corner * u * u + skew * (u + 1) / 2 * u * u
    gap = S.get('gap', K['gap']) * L

    def wave(t):
        t = np.asarray(t, float)
        if not S.get('wave'):
            return 0 * t
        return S['wave'] * K['width'] * L * np.cos(2 * np.pi * S.get('waves', 2.5) * (t - 0.5)) * np.sin(np.pi * t) ** 0.7

    def upper(t):
        x, z = base(t)
        s = np.sin(np.pi * np.asarray(t, float))
        prof = s ** (1.0 - 0.7 * S.get('upper_round', 0.5)) if op > 0 else 0 * s
        return x, z + op * up * prof + wave(t)

    def lower(t):
        x, z = base(t)
        s = np.sin(np.pi * np.asarray(t, float))
        prof = s ** (1.0 - 0.7 * S.get('lower_round', 0.8)) if op > 0 else 0 * s
        return x, z - gap * s ** 0.8 - op * (1 - up) * prof + wave(t)
    return upper, lower


# --------------------------------------------------------------------------------------------------------------- placement
def _params(V, chain):
    xs = V[chain, 0]
    return np.clip(np.maximum.accumulate((xs - xs[0]) / max(1e-9, xs[-1] - xs[0])), 0, 1)


def _arc_params(V, chain, fn, n=400):
    """each chain vertex's place on a curve by arc length: its share of the chain's length at rest (in the face's plane)
    -> the curve's parameter t with the same share of the curve's length. An open mouth's steep sides (a D, an O) keep
    their share of the lip's vertices, where spacing by x leaves them one long edge the rings beside it can't follow."""
    P = V[chain][:, [0, 2]]
    s = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    s /= max(s[-1], 1e-12)
    t = np.linspace(0, 1, n)
    x, z = fn(t)
    a = np.r_[0.0, np.cumsum(np.hypot(np.diff(x), np.diff(z)))]
    return np.interp(s, a / max(a[-1], 1e-12), t)


def _pose(V, M, F, K, L, mc, shape, outer=True, jaw_drop=0.0):
    """positions for the loop, the outer rings and the cavity for a shape. jaw_drop: the lower lip rides a jaw that
    dropped this far (an authored base's key): its curve is placed on the face in the jaw's frame (as high again), then
    carried down with it, so it keeps its depth instead of sinking onto the rest face under the mouth. An authored base
    (M['loops']) spaces its lips along the curves by arc length (_arc_params), the others by x.
    -> {v: position}."""
    up_f, lo_f = curves(K, L, shape)
    pos = {}
    for chain, fn, dj in ((M['upper'], up_f, 0.0), (M['lower'], lo_f, jaw_drop)):
        x, z = fn(_arc_params(V, chain, fn) if M.get('loops') else _params(V, chain))
        P = eyelib._world(F, mc[0], mc[1], 1.0, x, z + dj)
        P[:, 2] -= dj
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
            off = V[ov, 1] - F.y(V[ov, 0], V[ov, 2])
            x2, z2 = V[ov, 0] + mv[:, 0], V[ov, 2] + mv[:, 2]
            for v, p in zip(ov, np.stack([x2, F.y(x2, z2) + off, z2], 1)):
                pos[v] = p
    # the cavity: a funnel back from the loop toward a point behind the mouth's centre
    ctr = np.array([mc[0], 0.0, mc[1]])
    xs_open = new[:, [0, 2]]
    oc = xs_open.mean(0)
    depth = K['depth'] * L
    rmax = max(M['cavity'].values())
    csrc = M.get('cavity_src') or {}                   # an anime base's compact cavity: (loop vertex, depth share, pull) each
    cv, rows = list(M['cavity'].keys()), []
    for v in cv:
        r = M['cavity'][v]
        if v in csrc:
            src, f, pull = csrc[v]
            mp = new[idx[src]]
        else:
            sd = M['side'].get(v, 'u')
            ci = np.array([idx[u] for u in chains['l' if sd == 'l' else 'u']])
            j = ci[int(np.argmin(np.linalg.norm(old[ci] - V[v], axis=1)))]
            mp = new[j]
            f = min(1.0, r / max(3, rmax * 0.7))
            pull = 0.15 + 0.55 * f
        rows.append((mp[0] + (oc[0] - mp[0]) * pull, mp[2] + (oc[1] - mp[2]) * pull, depth * f ** 0.8))
    if cv:
        x2, z2, dd = np.array(rows).T
        for v, p in zip(cv, np.stack([x2, F.y(x2, z2) + 0.0015 + dd, z2], 1)):
            pos[v] = p
    return pos


def place(V, M, F, K, L, mc, faces=None):
    """the neutral mouth. An authored base (M['loops'], with the mesh's faces): the lips onto the neutral curves and the
    cage's own mouth rings harmonic between them and the block's rim (key()'s solve, the rest held). -> new V."""
    V = V.copy()
    if M.get('loops') and faces is not None:
        pos = _pose(V, M, F, K, L, mc, 'neutral', outer=False)
        D = np.zeros_like(V)
        for v, p in pos.items():
            D[v] = p - V[v]
        # at rest the lips only close the loop's lens: the mouth's own rings follow, the skin past its block stays on the
        # head's sections where the cage put it
        free = np.array(sorted({v for r in M['loops'][1:-1] for v in r} - set(pos)), int)
        if len(free):
            D[free] = harmonic(V, faces, free, lambda w: D[w])
        return V + D
    for v, p in _pose(V, M, F, K, L, mc, 'neutral').items():
        V[v] = p
    return V


_SYSTEMS = {}                             # harmonic()'s factored systems, by their mesh and free set (the keys share one)


def _system(V, faces, free):
    """harmonic()'s system for these free vertices: the inverse of its matrix and each free vertex's weighted fixed
    neighbours (rows, vertices, weights); kept for the next call on the same mesh and free set (every mouth key of a
    character solves the same system with other fixed moves)."""
    import hashlib
    h = hashlib.sha1(np.ascontiguousarray(V, float).tobytes())
    h.update(np.asarray(free, np.int64).tobytes())
    h.update(str(len(faces)).encode())
    k = h.hexdigest()
    if k in _SYSTEMS:
        return _SYSTEMS[k]
    free = list(free)
    ix = {v: i for i, v in enumerate(free)}
    n = len(free)
    A = np.zeros((n, n))
    rows, cols, wts = [], [], []
    for f in faces:
        for a, c in zip(f, list(f[1:]) + [f[0]]):
            if a not in ix and c not in ix:
                continue
            w = 1.0 / max(float(np.linalg.norm(V[a] - V[c])), 1e-9)
            for u, v in ((a, c), (c, a)):
                i = ix.get(u)
                if i is None:
                    continue
                A[i, i] += w
                j = ix.get(v)
                if j is None:
                    rows.append(i); cols.append(v); wts.append(w)
                else:
                    A[i, j] -= w
    out = (np.linalg.inv(A), np.array(rows, np.int64), np.array(cols, np.int64), np.array(wts))
    if len(_SYSTEMS) > 4:
        _SYSTEMS.clear()
    _SYSTEMS[k] = out
    return out


def harmonic(V, faces, free, fixed):
    """the move of the `free` vertices that is harmonic over the mesh (each the mean of its neighbours', each edge weighted
    by its inverse length, so vertices close together move together, as they would by distance), given
    every other vertex's: fixed(v) -> its move (3,), or an (N, 3) array of every vertex's move. Numpy only (the build's
    Blender has no scipy); a dense system for a few hundred to a few thousand vertices, factored once per mesh and free
    set (_system). A harmonic map doesn't fold the way a spread by distance can: every vertex stays inside its
    neighbours' hull. -> (len(free), 3)."""
    Ainv, rows, cols, wts = _system(V, faces, free)
    if callable(fixed):
        uniq = np.unique(cols)
        mv = {int(v): np.asarray(fixed(int(v)), float) for v in uniq}
        F = np.array([mv[int(v)] for v in cols]) if len(cols) else np.zeros((0, 3))
    else:
        F = np.asarray(fixed, float)[cols]
    b = np.zeros((Ainv.shape[0], 3))
    np.add.at(b, rows, wts[:, None] * F)
    return Ainv @ b


def held(eyes):
    """the vertices another component's keys move that a mouth key holds still (charkit.expressions: the components add,
    so their keys mustn't share vertices): the eyes' lid loops, margins, pockets and sockets (an authored base's; its
    mouth's outer rings reach them) -> a set."""
    out = set()
    for E in eyes:
        e = E['eye'] if 'eye' in E else E
        for k in ('margin', 'upper', 'lower', 'pocket', 'socket'):
            out.update(int(v) for v in (e.get(k) or ()))
        for r in e.get('loops') or ():
            out.update(int(v) for v in r)
    return out


def key(V, M, F, K, L, mc, shape, jaw_w=None, faces=None, hold=None):
    """offsets (N, 3) from the placed neutral V to a shape (the jaw following the lower lip when it opens). An authored
    base (M['loops'], with the mesh's faces): the lips onto the shape's curves and the cavity after them, the jaw's core
    (its weight from JAW_CORE) moved whole by jaw_follow of the lower lip's drop, the skin with no jaw weight kept, and
    between them (the lips' rings, the jaw's edge) the move harmonic over the mesh in all three axes (harmonic()): the
    skin rides the jaw as it opens, rather than sliding over the rest face. Other bases: the rings by a spread from the
    lips, the rest of the jaw by the jaw. hold: vertices kept still (held(): the eyes' loops, which the eye keys move)."""
    D = np.zeros_like(V)
    if M.get('loops') and jaw_w is not None and faces is not None:
        _, lo_n = curves(K, L, 'neutral'); _, lo_s = curves(K, L, shape)
        drop = max(0.0, lo_n(0.5)[1] - lo_s(0.5)[1])
        D[:, 2] = -np.asarray(jaw_w, float) * drop * K['jaw_follow']
        pos = _pose(V, M, F, K, L, mc, shape, outer=False, jaw_drop=drop * K['jaw_follow'])
        for v, p in pos.items():
            D[v] = p - V[v]
        # free: the lips' rings and the jaw's edge (its weight between none and whole); the jaw's core moves whole
        jw = np.asarray(jaw_w, float)
        edge = np.nonzero((jw > 1e-3) & (jw < JAW_CORE))[0]
        free = np.array(sorted((set(M['outer']) | set(edge.tolist())) - set(pos) - set(hold or ())), int)
        if hold:
            D[np.array(sorted(set(hold) - set(pos)), int)] = 0.0
        if len(free):
            D[free] = harmonic(V, faces, free, D)
        return D
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
def _shape(shape):
    S = dict(SHAPES['neutral']); S.update(SHAPES[shape] if isinstance(shape, str) else shape)
    return S


def jaw_drop(K, L, shape):
    """how far an authored base's key carries the lower lip down in the jaw's frame (key(): jaw_follow of the lower lip's
    drop at the middle): the lower lip keeps the depth it had that far up on the rest face, so what rides it (the lower
    teeth, the tongue, the lower lip's line) is placed the same way."""
    _, lo_n = curves(K, L, 'neutral'); _, lo_s = curves(K, L, shape)
    return max(0.0, float(lo_n(0.5)[1] - lo_s(0.5)[1])) * K['jaw_follow']


def _at(F, mc, x, z, depth=0.0, dj=0.0):
    """mouth-local (x, z) -> world on the face, `depth` behind it; dj: in the jaw's frame (the rest face dj higher up)."""
    P = eyelib._world(F, mc[0], mc[1], 1.0, x, np.asarray(z, float) + dj, depth=depth)
    P[:, 2] -= dj
    return P


def _opening(K, L, shape, t):
    """the opening's height along the mouth at t, and its tallest."""
    up_f, lo_f = curves(K, L, shape)
    g = np.maximum(up_f(t)[1] - lo_f(t)[1], 0.0)
    gt = up_f(np.linspace(0, 1, 101))[1] - lo_f(np.linspace(0, 1, 101))[1]
    return g, float(max(gt.max(), 0.0))


def line(F, K, L, mc, shape='neutral', n=32, authored=False):
    """the drawn mouth line: a ribbon along the upper lip's edge, fullest in the middle, tapering into the corners (the
    anime mouth is a line; open shapes keep it as the opening's top edge), and a thinner one along the lower lip's edge
    that an open mouth shows (the drawn open mouth's outline: `line_lo` of the upper's width as the lips part, tucked
    behind the upper line while they meet). authored: the lower lip rides the jaw's frame (jaw_drop). -> (verts, quads)."""
    up_f, lo_f = curves(K, L, shape)
    t = np.linspace(0.02, 0.98, n)
    x, z = up_f(t)
    th = shape_of(K, shape).get('line_w', K.get('line_w', 0.0075)) * L * (0.35 + 0.65 * np.sin(np.pi * t) ** 0.6)
    uv, uq = eyelib._ribbon(F, 1.0, mc, np.stack([x, z], 1), th, 1.0, lift=-0.0004, tuck=0.6)
    # the lower line: as wide as the lips are apart (up to line_lo of the upper line's width by an opening of 0.03 L)
    g, gmax = _opening(K, L, shape, t)
    part = np.clip(gmax / (0.03 * L), 0.0, 1.0)
    xl, zl = lo_f(t)
    thl = th * (0.15 + (K['line_lo'] - 0.15) * part) * np.sin(np.pi * t) ** 0.5
    P = np.stack([xl, zl], 1)
    tan = np.gradient(P, axis=0)
    tan /= np.maximum(np.linalg.norm(tan, axis=1, keepdims=True), 1e-12)
    nrm = np.stack([tan[:, 1], -tan[:, 0]], 1)                  # down, out of the opening
    tuck = 0.35
    dj = jaw_drop(K, L, shape) if authored else 0.0
    inner = P - nrm * thl[:, None] * tuck
    outer = P + nrm * thl[:, None] * (1 - tuck)
    Vi = _at(F, mc, inner[:, 0], inner[:, 1], -0.0003, dj)
    Vo = _at(F, mc, outer[:, 0], outer[:, 1], -0.0003, dj)
    m, k = len(uv), len(t)
    lq = [(m + i, m + k + i, m + k + i + 1, m + i + 1) for i in range(k - 1)]
    return np.vstack([uv, Vi, Vo]), list(uq) + lq


def teeth(F, K, L, mc, shape='neutral', n=28, authored=False):
    """the teeth: the upper row a white band just behind the upper lip's edge, following its curve, as tall as the
    shape's `teeth` share of the opening's tallest (and never more than most of the opening where it narrows toward the
    corners); the lower row the same behind the lower lip (`teeth_lo`, most shapes none: it stays tucked under the lip).
    Closed: both tucked behind the lips. -> (verts, quads): the upper band's n top then n bottom vertices, then the lower
    band's."""
    S = _shape(shape)
    up_f, lo_f = curves(K, L, shape)
    t = np.linspace(0.07, 0.93, n)
    xu, zu = up_f(t)
    xl, zl = lo_f(t)
    g, gmax = _opening(K, L, shape, t)
    tuck = 0.006 * L                                  # how far each band reaches back behind its lip
    hu = np.minimum(S.get('teeth', K['teeth']) * gmax, 0.85 * g)
    hl = np.minimum(S.get('teeth_lo', 0.0) * gmax, np.maximum(0.85 * g - hu, 0.0))
    dj = jaw_drop(K, L, shape) if authored else 0.0
    d = 0.0022
    top = _at(F, mc, xu * 0.97, zu + tuck, d)
    bot = _at(F, mc, xu * 0.97, zu - np.maximum(hu, 0.0) + (0.0 if hu.max() > 0 else tuck), d)
    ltop = _at(F, mc, xl * 0.97, zl + np.maximum(hl, 0.0) - (0.0 if hl.max() > 0 else tuck), d, dj)
    lbot = _at(F, mc, xl * 0.97, zl - tuck, d, dj)
    verts = np.vstack([top, bot, ltop, lbot])
    quads = [(i, n + i, n + i + 1, i + 1) for i in range(n - 1)] + \
        [(2 * n + i, 3 * n + i, 3 * n + i + 1, 2 * n + i + 1) for i in range(n - 1)]
    return verts, quads


def tongue(F, K, L, mc, shape='neutral', nu=16, nv=6, authored=False):
    """the tongue: a pad riding the lower lip, its front edge tucked under the lip, rising to an arched top `tongue` of
    the opening's tallest over the lower lip (never past most of the opening beside the teeth), sloping back as it rises;
    shallow enough to stand in front of the cavity's funnel (whose first rings pull in toward the opening's middle), so an
    open mouth shows it in its lower part. Closed: tucked behind the lower lip. -> (verts, quads)."""
    S = _shape(shape)
    up_f, lo_f = curves(K, L, shape)
    t = np.linspace(0.12, 0.88, nu)
    x, zl = lo_f(t)
    g, gmax = _opening(K, L, shape, t)
    hu = np.minimum(S.get('teeth', K['teeth']) * gmax, 0.85 * g)
    arch = np.sin(np.pi * (t - t[0]) / (t[-1] - t[0])) ** 0.35
    h = np.minimum(S.get('tongue', K['tongue']) * gmax * arch, np.maximum(0.9 * g - hu, 0.0))
    dj = jaw_drop(K, L, shape) if authored else 0.0
    tuck = 0.008 * L
    verts = []
    for j in range(nv):
        s = j / (nv - 1)
        zz = zl - tuck + (tuck + h) * s
        verts.append(_at(F, mc, x * (1.0 - 0.08 * s), zz, (0.004 + 0.008 * s) * L, dj))
    verts = np.vstack(verts)
    quads = [(j * nu + i, j * nu + i + 1, (j + 1) * nu + i + 1, (j + 1) * nu + i) for j in range(nv - 1) for i in range(nu - 1)]
    return verts, quads
