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
    # the eye's surface behind its opening (Surface; the style profile's `eyes` section sets it): 'plate' lies on the
    # face `depth` behind it; 'turned' bends it round a vertical fold at the iris's nasal edge, the lids, lashes, pocket
    # and the skin round the opening following it, every (x, z) kept (the front view is the plate's)
    'surface': 'plate',
    'turn': (-5.0, 10.0, 45.0),   # 'turned': the surface's angle from facing front (degrees, + toward the eye's own
                                  # side) nasal of the fold, just past it, and at the outer corner (linear between)
    'fold_at': 0.0,      # the fold from the iris's nasal edge, in eye widths (+ outward)
    'fold_soft': 0.03,   # the fold's rounding, half-width in eye widths
    'fold_reach': 0.035, # L: how far outside the opening the skin follows the surface (fading to the face's own)
    'fold_follow': 0.0,  # each row's fold at one depth (0: the profile's front edge upright) or at the face's depth
                         # there (1: the edge follows the iris's outline as the face recedes)
    'anchor': 'min',     # the surface's depth: 'min' never in front of `depth`; 'mean' its mean over the opening
                         # there; 'corners' the opening's two corners there (their mean); 'fold' the fold there
    'flick_turn': None,  # 'turned': the flick's own angle from facing front (degrees; None: the surface's at the corner)
    'converge': 0.0,     # the irises' rest place toward the nose (eye widths) when the spec's iris doesn't set it
    'iris': (0.285, 0.54, -0.01, 0.0),  # the iris at rest: half-width, half-height, centre height and convergence, in
                                        # eye widths (knobs() takes them from the iris knobs): the fold follows its
                                        # nasal outline, the plates are laid with it
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


def knobs(spec):
    """a spec's eye knobs: DEFAULT_EYE, the style profile's `eyes` section (charkit/styles), the spec's own `eyes`; the
    iris's nasal edge from its knobs (charkit.eyetex: half-width and convergence). The eye surface bends only on a base
    whose eye loops the lids ride (base 'code'); elsewhere it is the plate."""
    from . import eyetex, styles
    st = {k: v for k, v in (styles.load(spec.get('style', 'anime')).get('eyes') or {}).items() if k != 'iris'}
    K = _knobs({**st, **(spec.get('eyes') or {})})
    if spec.get('base') != 'code':
        K['surface'] = 'plate'
    IK = eyetex._knobs(spec.get('iris'))
    conv = (spec.get('iris') or {}).get('converge')
    if conv is None:                                # the style's, with a surface that turns (a plate's far eye in
        conv = K['converge'] if K['surface'] == 'turned' else 0.0     # three-quarter would lose its nasal white)
    K['iris'] = tuple(float(IK[k]) for k in ('rx', 'rz', 'cz')) + (float(conv),)
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


# ------------------------------------------------------------------------------------------------------------ surface
def _smooth(e0, e1, x):
    t = np.clip((np.asarray(x, float) - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def _inside(P, poly):
    """points (M, 2) inside a closed polygon (N, 2) (even-odd) -> bool (M,)."""
    x, y = P[:, 0][:, None], P[:, 1][:, None]
    a, b = poly, np.roll(poly, -1, 0)
    ya, yb = a[:, 1][None], b[:, 1][None]
    cross = (ya > y) != (yb > y)
    xi = a[:, 0][None] + (y - ya) * (b[:, 0] - a[:, 0])[None] / np.where(yb == ya, 1e-30, yb - ya)
    return (cross & (x < xi)).sum(1) % 2 == 1


def _seg_dist(P, poly):
    """points' distance (M,) to a closed polygon's edges."""
    a, b = poly[None], np.roll(poly, -1, 0)[None]
    d = b - a
    t = np.clip(((P[:, None] - a) * d).sum(-1) / np.maximum((d * d).sum(-1), 1e-30), 0, 1)
    q = a + t[..., None] * d
    return np.sqrt(((P[:, None] - q) ** 2).sum(-1)).min(1)


class Surface:
    """the eye's surface behind its opening, as a depth field on the face F (metres, + back), a function of eye-local
    (x outward, z up): zero for the plate. 'turned' (K['surface']): along each row the surface faces a little toward
    the nose (turn[0]) up to a fold that follows the iris's nasal outline (K['iris'], moved by fold_at), then turns
    outward from turn[1] just past it to turn[2] at the outer corner; every row's fold sits at one depth (the profile's
    front edge is upright), and the whole is set against the face so that inside the opening it never comes in front
    of the plate's depth (anchor 'min'; or 'mean', 'fold'). Outside the opening it fades to the face's own over
    K['fold_reach'] L. Everything of the eye (lids, lashes, the pocket, the plates, the skin round the opening) takes the
    field at its own (x, z), so the front view is unchanged, and from the side the part of the opening nasal of the fold
    faces away: the iris sits at the front edge in profile, the sclera behind it."""

    def __init__(self, F, K, L, side, eye_c):
        self.on = K.get('surface') == 'turned'
        self.side, self.ex, self.ez = side, float(eye_c[0]), float(eye_c[1])
        if not self.on:
            return
        self.W = W = K['width'] * L
        self.poly = outline_polygon(K, L, n=48)
        self.reach = float(K['fold_reach']) * L
        rx, rz, cz, conv = K['iris']
        self.iris = (rx, rz, cz, conv)
        self.at, self.soft = float(K['fold_at']), max(1e-3, float(K['fold_soft']))
        self.follow = float(K.get('fold_follow', 0.0))
        tn, tf, tc = (math.radians(a) for a in K['turn'])
        # G(u): the surface's depth (eye widths, + back) at u eye widths outward of the row's fold, 0 at the fold
        e0 = -(rx + conv) + self.at                          # the fold at the iris's middle row
        u = np.linspace(-1.5, 1.8, 661)
        th_t = np.minimum(tf + (tc - tf) * np.maximum(u, 0) / max(1e-3, 0.5 - e0), math.radians(80))
        th = tn + (th_t - tn) * _smooth(-self.soft, self.soft, u)
        slope = np.tan(th)
        G = np.concatenate([[0.0], np.cumsum(0.5 * (slope[1:] + slope[:-1]) * np.diff(u))])
        self.u, self.G = u, G - np.interp(0.0, u, G)
        # the face's own depth over the eye (eye widths, relative to the eye's centre), on a grid round the opening
        gx = np.linspace(-0.8, 0.8, 97); gz = np.linspace(-0.8, 0.8, 97)
        GX, GZ = np.meshgrid(gx, gz, indexing='ij')
        yF = (F.y(self.ex + side * GX.ravel() * W, self.ez + GZ.ravel() * W) - F.y(self.ex, self.ez)) / W
        self.gx, self.gz, self.yF = gx, gz, yF.reshape(GX.shape)
        # the anchor: over the opening (its polygon, sampled), the surface's offset from the face
        P = self.poly / W
        inside = _inside(np.stack([GX.ravel(), GZ.ravel()], 1), P).reshape(GX.shape)
        off = self._raw(GX[inside], GZ[inside]) - self.yF[inside]
        a = K.get('anchor', 'min')
        if a == 'corners':                                  # the opening's two corners on the face (their mean)
            cx = np.array([-0.5, 0.5]); czs = outline(K, 1.0, np.array([0.0, 1.0]), 'upper')[1] / K['width']
            self.c0 = -float(np.mean(self._raw(cx, czs) - self._face(cx, czs)))
        elif a == 'fold':                                   # the middle row's fold on the face
            fz = np.array([cz]); fx = self.fold_x(fz)
            self.c0 = -float((self._raw(fx, fz) - self._face(fx, fz))[0])
        else:
            self.c0 = -(off.min() if a == 'min' else off.mean())
        self.info = dict(fold_mid=round(e0, 3), fold_min=round(float((off.min() + self.c0) * W / L), 4),
                         fold_max=round(float((off.max() + self.c0) * W / L), 4))

    def fold_x(self, z):
        """the fold's x (eye widths) on rows z (eye widths): the iris's nasal outline, fold_at outward of it."""
        rx, rz, cz, conv = self.iris
        q = np.clip(1 - ((np.asarray(z, float) - cz) / rz) ** 2, 0.05, 1)
        return -(conv + rx * np.sqrt(q)) + self.at

    def _raw(self, x, z):
        """the surface's depth (eye widths, + back) relative to the frontal plane through its middle row's fold."""
        xf = self.fold_x(z)
        out = np.interp(np.asarray(x, float) - xf, self.u, self.G)
        if self.follow:
            z = np.asarray(z, float)
            out = out + self.follow * (self._face(xf, z) - self._face(self.fold_x(np.zeros(1)), np.zeros(1)))
        return out

    def _face(self, x, z):
        """the face's depth at (x, z) eye widths, bilinear on the grid (numpy: Blender's Python has no scipy)."""
        n, m = self.yF.shape
        i = np.clip((np.asarray(x, float) - self.gx[0]) / (self.gx[1] - self.gx[0]), 0, n - 1 - 1e-9)
        j = np.clip((np.asarray(z, float) - self.gz[0]) / (self.gz[1] - self.gz[0]), 0, m - 1 - 1e-9)
        i0, j0 = np.floor(i).astype(int), np.floor(j).astype(int)
        a, b = i - i0, j - j0
        Y = self.yF
        return ((1 - a) * (1 - b) * Y[i0, j0] + a * (1 - b) * Y[i0 + 1, j0] + (1 - a) * b * Y[i0, j0 + 1]
                + a * b * Y[i0 + 1, j0 + 1])

    def __call__(self, x, z):
        """the extra depth at eye-local (x, z) (arrays, metres) -> the same shape."""
        x, z = np.broadcast_arrays(np.atleast_1d(np.asarray(x, float)), np.atleast_1d(np.asarray(z, float)))
        if not self.on:
            return np.zeros(x.shape)
        P = np.stack([x.ravel(), z.ravel()], 1)
        d = _seg_dist(P, self.poly)
        w = np.where(_inside(P, self.poly), 1.0, 1 - _smooth(0.0, self.reach, d))
        xw, zw = P[:, 0] / self.W, P[:, 1] / self.W
        f = (self._raw(xw, zw) + self.c0 - self._face(xw, zw)) * self.W
        return (f * w).reshape(x.shape)

    def world(self, X, Z):
        """the extra depth at world (X, Z)."""
        return self(self.side * (np.asarray(X, float) - self.ex), np.asarray(Z, float) - self.ez)


def surface(F, K, L, side, eye_c):
    """the eye's Surface, made once per face, knobs and eye."""
    cache = F.__dict__.setdefault('_surfaces', {})
    key = (side, float(eye_c[0]), float(eye_c[1]), L,
           tuple(sorted((k, str(v)) for k, v in K.items())))
    if key not in cache:
        cache[key] = Surface(F, K, L, side, eye_c)
    return cache[key]


# ------------------------------------------------------------------------------------------------------------ placement
class Face:
    """the anime face surface in world: surf(x, z) -> the point on it at world x, z (front half), for placing features."""

    def __init__(self, H, centre):
        # the analytic head is rebuilt without its features; another surface (charkit.code_base.SectionsHead) as it is
        self.H = headlib.Head(H.L, H.K, features=False) if isinstance(H, headlib.Head) else H
        self.c = np.asarray(centre)

    def points(self, x, z):
        """point() over arrays of world x and z -> (M, 3)."""
        zr = np.asarray(z, float) - self.c[2]
        a = ah.surface_azimuths(self.H, x, zr, hi=math.pi * 0.62)
        return self.H.surfaces(a, zr) + self.c

    def point(self, x, z):
        return self.points(np.atleast_1d(float(x)), np.atleast_1d(float(z)))[0]

    def y(self, x, z):
        """the surface's y at world x, z (scalars or arrays)."""
        if np.ndim(x) == 0 and np.ndim(z) == 0:
            return float(self.point(x, z)[1])
        return self.points(*np.broadcast_arrays(np.asarray(x, float), np.asarray(z, float)))[:, 1]

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


def spokes(V, eye, F, moved, surf=None, rest=False):
    """an authored base's eye loops (eye['loops']: the block's rim first, the lid's margin last, index-aligned) following
    the margin: each ring vertex takes the share of its spoke's margin move that its place along the spoke has at rest
    (0 at the rim, which stays, 1 at the margin), in the face's plane, re-seated on the face at its old depth offset. The
    rings stay nested (a lid closing stretches them, it can't fold them), and nothing past the rim moves.
    surf: the eye's Surface, its depth added where the vertex lands (rest: V already carries it, taken out first).
    moved: {margin vertex: its move (3,)} -> {ring vertex: its move (3,)}."""
    loops = eye['loops']
    rim, mar = loops[0], loops[-1]
    out = {}
    xs, zs, offs, vs = [], [], [], []
    for k in range(1, len(loops) - 1):
        for i, v in enumerate(loops[k]):
            m, b = mar[i], rim[i]
            d = moved.get(m)
            if d is None:
                continue
            sp = V[m, [0, 2]] - V[b, [0, 2]]
            t = float(np.clip((V[v, [0, 2]] - V[b, [0, 2]]) @ sp / max(sp @ sp, 1e-18), 0.0, 1.0))
            xs.append(V[v, 0] + t * d[0]); zs.append(V[v, 2] + t * d[2]); vs.append(v)
    if vs:
        vs = np.array(vs)
        off = V[vs, 1] - F.y(V[vs, 0], V[vs, 2])
        x2, z2 = np.array(xs), np.array(zs)
        if surf is not None and surf.on:
            if rest:
                off = off - surf.world(V[vs, 0], V[vs, 2])
            off = off + surf.world(x2, z2)
        P = np.stack([x2, F.y(x2, z2) + off, z2], 1)
        for v, p in zip(vs, P):
            out[int(v)] = p - V[v]
    return out


def _world(F, ex, ez, side, x, z, depth=0.0, surf=None):
    """eye-local (x, z) -> world, on the face surface, pushed back by depth along the view (y), and by the eye's
    Surface there when given."""
    X = ex + side * np.asarray(x); Z = ez + np.asarray(z)
    P = F.points(*np.broadcast_arrays(np.atleast_1d(X).astype(float), np.atleast_1d(Z).astype(float)))
    P[:, 1] += depth
    if surf is not None and surf.on:
        P[:, 1] += surf(*np.broadcast_arrays(np.atleast_1d(np.asarray(x, float)), np.atleast_1d(np.asarray(z, float))))
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
    S = surface(F, K, L, side, eye_c)
    tp = _margin_params(V, eye, side)
    tgt = {}
    for which in ('upper', 'lower'):
        x, z = outline(K, L, tp[which], which)
        P = _world(F, ex, ez, side, x, z, surf=S)
        for v, p in zip(eye[which], P):
            tgt[v] = p
    m = np.array(eye['margin'])
    old = V[m].copy()
    new = np.array([tgt[v] for v in m])
    dxz = (new - old)[:, [0, 2]]
    if eye.get('loops'):
        # an authored base's own loops: along their spokes (spokes()), nothing past the block's rim moves
        for v, d in spokes(V, eye, F, {v: tgt[v] - V[v] for v in m}, surf=S).items():
            V[v] = V[v] + d
    else:
        # outer rings: the margin's in-surface motion, fading; re-seated on the face at their old depth offset
        ov = np.array(list(eye['outer'].keys()))
        mvs = spread(old[:, [0, 2]], dxz, V[ov][:, [0, 2]])
        off = V[ov, 1] - F.y(V[ov, 0], V[ov, 2])
        x2, z2 = V[ov, 0] + mvs[:, 0], V[ov, 2] + mvs[:, 1]
        V[ov] = np.stack([x2, F.y(x2, z2) + off, z2], 1)
    for v, p in tgt.items():
        V[v] = p
    # the pocket: a funnel from the margin back behind the plate (the lid's thickness, then the back wall). An anime base's
    # shallow socket (charkit/base_anime.py) says per vertex: its margin vertex, the pull toward the centre and the depth.
    depth = K['depth'] * L
    cen = np.array([ex, ez])
    sock = eye.get('socket') or {}
    mi = {v: j for j, v in enumerate(m)}
    pv, rows = list(eye['pocket'].keys()), []
    for v in pv:
        r = eye['pocket'][v]
        if v in sock:
            src, pull, dz = sock[v]
            mp = new[mi[src]]
        else:
            j = int(np.argmin(np.linalg.norm(old - V[v], axis=1)))    # nearest margin vertex (by old positions)
            mp = new[j]
            pull = min(0.92, 0.05 + 0.13 * (r - 1))
            dz = 0.0012 + 0.0022 * (r - 1) ** 0.8
        rows.append((mp[0] + (cen[0] - mp[0]) * pull, mp[2] + (cen[1] - mp[2]) * pull, dz))
    if pv:
        x2, z2, dz = np.array(rows).T
        V[np.array(pv)] = np.stack([x2, F.y(x2, z2) + depth + dz + S.world(x2, z2), z2], 1)
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
    pts = _world(F, ex, ez, side, loc[:, 0] + shift[0], loc[:, 1] + shift[1], surf=surface(F, K, L, side, eye_c))
    pts[:, 1] += depth
    uvs = [(x / W + 0.5, z / W + 0.5) for x, z in loc]
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
def _ribbon(F, side, eye_c, pts, thick, normal_sign, lift=-0.0006, tuck=0.35, surf=None, at=None):
    """a ribbon along eye-local points (N,2) with per-point thickness, offset along the 2D normal (away from the eye); its
    inner edge tucked a little over the opening; on the eye's Surface when given, or `at` (N,): each point's extra
    depth, both edges alike (a lash stands off its lid line, it doesn't sink into the skin behind). -> (verts, quads)."""
    pts = np.asarray(pts)
    tan = np.gradient(pts, axis=0)
    tan /= np.maximum(np.linalg.norm(tan, axis=1, keepdims=True), 1e-12)
    nrm = np.stack([-tan[:, 1], tan[:, 0]], 1) * normal_sign
    inner = pts - nrm * thick[:, None] * tuck
    outer = pts + nrm * thick[:, None] * (1 - tuck)
    ex, ez = eye_c
    Vi = _world(F, ex, ez, side, inner[:, 0], inner[:, 1], depth=lift, surf=None if at is not None else surf)
    Vo = _world(F, ex, ez, side, outer[:, 0], outer[:, 1], depth=lift, surf=None if at is not None else surf)
    if at is not None:
        Vi[:, 1] += at; Vo[:, 1] += at
    n = len(pts)
    verts = np.vstack([Vi, Vo])
    quads = []
    for i in range(n - 1):
        q = (i, i + 1, n + i + 1, n + i)
        quads.append(q if side * normal_sign > 0 else q[::-1])
    return verts, quads


def _flick_depth(F, S, eye_c, side, xc, zc, fx, fz, h=0.05, turn=None):
    """the flick's extra depth: the eye's surface at the outer corner (xc, zc), carried on at its slope there along
    x (world y's rise per eye-local x over the last h of the eye's width; or at `turn` degrees from facing front), less
    the face's own depth under the flick."""
    ex, ez = eye_c
    y = lambda x, z: F.y(ex + side * np.asarray(x, float), ez + np.asarray(z, float)) + S(x, z)
    xb = xc - h * S.W
    yc, yb = float(y(np.array([xc]), np.array([zc]))[0]), float(y(np.array([xb]), np.array([zc]))[0])
    slope = (yc - yb) / (xc - xb) if turn is None else math.tan(math.radians(turn))
    return yc + slope * (fx - xc) - F.y(ex + side * fx, ez + fz)


def lashes(F, K, L, side, eye_c, upper_fn=None, lower_fn=None, n=40):
    """upper lash line (thick, tapering in toward the inner corner, a flick past the outer corner) and a lower lash (the
    outer part), along the outline or along given lid curves (functions t -> eye-local (x, z), for the shape keys).
    -> list of (verts, quads) ribbons."""
    W = K['width'] * L
    S = surface(F, K, L, side, eye_c)
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
    at = None
    if S.on:
        # on a turned surface the lash stands at its lid line's depth, and the flick goes on along the surface's own
        # slope at the corner (not the face's steep turn behind it)
        at = np.concatenate([S(x, z), _flick_depth(F, S, eye_c, side, x[-1], z[-1], fx, fz, turn=K.get('flick_turn'))])
    up = _ribbon(F, side, eye_c, np.stack([np.concatenate([x, fx]), np.concatenate([z, fz])], 1),
                 np.concatenate([th, fth]), 1.0, surf=S, at=at)
    t2 = np.linspace(1 - K['lower_lash'], 1.0, 16)
    x2, z2 = lower_fn(t2)
    th2 = K['lash'] * L * K['lower_lash_w'] * np.sin(np.pi * 0.5 * (t2 - t2[0]) / (t2[-1] - t2[0])) ** 0.8 + 1e-5
    lo = _ribbon(F, side, eye_c, np.stack([x2, z2], 1), th2, -1.0, surf=S, at=S(x2, z2) if S.on else None)
    out = [up, lo]
    if K.get('crease', 0) > 0:
        # the double-lid crease: a thin line above the lash over its middle and outer part, following the lid
        t3 = np.linspace(0.22, 0.92, 24)
        x3, z3 = upper_fn(t3)
        lift_ = K['lash'] * L + K['crease'] * W
        th3 = K['crease_w'] * L * np.sin(np.pi * (t3 - t3[0]) / (t3[-1] - t3[0])) ** 0.7 + 1e-5
        out.append(_ribbon(F, side, eye_c, np.stack([x3, z3 + lift_ * np.sin(np.pi * (0.2 + 0.8 * t3)) ** 0.3], 1), th3,
                           1.0, tuck=0.5, surf=S))
    return out


# ------------------------------------------------------------------------------------------------------------ shape keys
def lid_key(V, eye, F, K, L, side, eye_c, upper_to=None, lower_to=None):
    """offsets (N,3) moving the upper and/or lower margin to target curves (functions t -> (x, z) eye-local), the outer rings
    and the near pocket after them, on the face surface. The base pose is V (already placed)."""
    ex, ez = eye_c
    S = surface(F, K, L, side, eye_c)
    D = np.zeros_like(V)
    tp = _margin_params(V, eye, side)
    moved = {}
    for which, fn in (('upper', upper_to), ('lower', lower_to)):
        if fn is None:
            continue
        x, z = fn(tp[which])
        P = _world(F, ex, ez, side, x, z, surf=S)
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
    if eye.get('loops'):
        for v, d in spokes(V, eye, F, moved, surf=S, rest=True).items():   # the loops follow their spokes (nothing
            D[v] = d                                                        # past the rim moves)
    else:
        ov = np.array(list(eye['outer'].keys()))
        d = spread(src, md, V[ov])
        x2, z2 = V[ov, 0] + d[:, 0], V[ov, 2] + d[:, 2]
        off = V[ov, 1] - F.y(V[ov, 0], V[ov, 2])
        D[ov] = np.stack([x2, F.y(x2, z2) + off, z2], 1) - V[ov]
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
        'half': (up({'height': K['height'] * 0.66, 'lower': K['lower'] / 0.66}), None),
        'wide': (up({'height': K['height'] * 1.14, 'lower': K['lower'] / 1.14}), lo({'height': K['height'] * 1.06})),
        'angry': (up({'peak': min(0.85, K['peak'] + 0.3), 'tilt': K['tilt'] + 9, 'height': K['height'] * 0.86,
                      'lower': K['lower'] / 0.86}), None),
        'sad': (up({'peak': max(0.15, K['peak'] - 0.2), 'tilt': K['tilt'] - 9, 'height': K['height'] * 0.9,
                    'lower': K['lower'] / 0.9}), None),
        'squint': (up({'height': K['height'] * 0.8, 'lower': K['lower'] / 0.8}),
                   lo({'height': K['height'] * 0.72, 'lower': K['lower'] * 0.6})),
        # shocked (asked for by the model sheet's flustered head, charkit/exprqa.py): the lids as they are, the iris
        # shrunk (IRIS_SCALE)
        'shock': (None, None),
    }


# expressions that also scale the iris about its centre, as a share of its size (a shocked eye's shrunken iris)
IRIS_SCALE = {'shock': 0.33}


def iris_scale(verts, uvs, cz, s):
    """offsets (N, 3) scaling an iris plate by s about the iris's centre (uv (0.5, 0.5 + cz)): the plate's point there,
    interpolated from its nearest vertices in uv."""
    V, U = np.asarray(verts, float), np.asarray(uvs, float)
    d = np.linalg.norm(U - np.array([0.5, 0.5 + cz]), axis=1)
    k = np.argsort(d)[:4]
    w = 1 / np.maximum(d[k], 1e-6)
    c = (V[k] * w[:, None]).sum(0) / w.sum()
    return (V - c) * (s - 1)
