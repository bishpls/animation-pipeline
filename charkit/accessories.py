"""Hair accessories and small props (docs/CHARKIT.md §2): meshes placed on the hair and oriented to it. Kinds: 'bun'
(stacked rounded pads, the hair's own material), 'star' (a sparkle clip: n major points, optional minor points between
them, curved edges, a raised faceted middle), 'crab' (a little crab clip: a flattened body, two raised notched claws,
eyes on stalks, legs), 'crown' (a ring band with blades round its top and jewels: crown()), 'pin' (a round badge with a
domed face, a rim and its emblem's cells: pin()). charkit.accqa measures the clips against the design's, view by view.

An accessory spec:
  kind, size             size in L: a star's height tip to tip, a crab's body width, a bun pad's width
  shape                  the kind's own proportions (STAR, CRAB: each knob relative to the size)
  placement              'at' [x, y, z]: L from the head's centre (x her left, y toward her back, z up), the clip
                         anchored where the ray from the centre through it meets the hair's outer surface; else 'az',
                         'el' on the hair volume (degrees; az 0 the front, + toward her left)
  orientation            'facing' [az, el]: the direction its face looks (degrees, the head's frame), else the hair's
                         surface normal leaned 'lean' degrees toward up; 'tilt' spins it about that axis (0: its up as
                         near the world's up as it gets)
  seat                   with the hair's surfaces given (generate's `ground`), a clip is pushed out along its facing
                         until its lowest point rests on the outermost hair under it (and on the clips listed before
                         it: list the one drawn underneath first), plus 'lift' L; buns are the hair volume's pads and
                         keep the volume's placement
  conform                a clip drawn over another (the star over the crab): it rests on the hair alone and bends
                         over the clips listed before it where they lie under its outline (conform()): True, or
                         {'reach': L (how far the bend spreads round what it covers), 'clear': L (its back over them)}
  color, eye_color, material, line
"""
import math
import numpy as np

# a kind's shape knobs (the neutral defaults: a character's spec carries its measured ones)
STAR = dict(points=4, up=0.5, down=0.5, side=0.4, minor=0.0, inner=0.14, curve=0.3, depth=0.09, thick=0.03, segs=4,
            minor_at=45.0, rings=1)
CONFORM = dict(reach=0.1, clear=0.004, rings=8)   # conform's defaults (L; a conformed star's rings, so it can bend)
CRAB = dict(body_h=0.72, body_d=0.42, claw=0.3, claw_at=(0.62, 0.52), claw_notch=55.0, claw_up=35.0, arm=0.07,
            eyes=0.055, eye_at=(0.13, 0.36), stalk=0.1, legs=3, leg=0.28, leg_r=0.035, leg_span=(-10.0, -60.0))


CROWN = dict(points=8, band=0.36, thick=0.03, point_w=0.55, lobe=0.3, jewels=8, jewel_r=0.035, flare=0.05, segs=96)
PIN = dict(dome=0.12, rim=0.08, thick=0.06, segs=48)


# ------------------------------------------------------------------------------------------------------------ helpers
def rounded_box(sx, sy, sz, rad, segs=4):
    """a rounded box centred at the origin (a subdivided cube pushed onto the rounded shape). -> (verts, quads)."""
    n = segs * 2 + 2
    verts, index = [], {}

    def vid(i, j, k):
        key = (i, j, k)
        if key not in index:
            p = np.array([i, j, k], float) / (n - 1) * 2 - 1           # -1 .. 1
            half = np.array([sx, sy, sz]) / 2
            inner = half - rad
            q = p * half
            c = np.clip(q, -inner, inner)
            d = q - c
            ln = np.linalg.norm(d)
            verts.append(c + (d / ln * rad if ln > 1e-12 else d))
            index[key] = len(verts) - 1
        return index[key]
    faces = []
    r = range(n - 1)
    for a in r:
        for b in r:
            faces.append((vid(0, a, b), vid(0, a, b + 1), vid(0, a + 1, b + 1), vid(0, a + 1, b)))
            faces.append((vid(n - 1, a, b), vid(n - 1, a + 1, b), vid(n - 1, a + 1, b + 1), vid(n - 1, a, b + 1)))
            faces.append((vid(a, 0, b), vid(a + 1, 0, b), vid(a + 1, 0, b + 1), vid(a, 0, b + 1)))
            faces.append((vid(a, n - 1, b), vid(a, n - 1, b + 1), vid(a + 1, n - 1, b + 1), vid(a + 1, n - 1, b)))
            faces.append((vid(a, b, 0), vid(a, b + 1, 0), vid(a + 1, b + 1, 0), vid(a + 1, b, 0)))
            faces.append((vid(a, b, n - 1), vid(a + 1, b, n - 1), vid(a + 1, b + 1, n - 1), vid(a, b + 1, n - 1)))
    return np.array(verts), faces


def sphere(c, r, nu=12, nv=8):
    """a UV sphere: centre c, radii r (scalar or 3) -> (verts, faces: quads and pole triangles)."""
    r = np.broadcast_to(np.asarray(r, float), (3,))
    V = [np.array([0, 0, -1.0])]
    for j in range(1, nv):
        t = math.pi * j / nv - math.pi / 2
        for i in range(nu):
            a = 2 * math.pi * i / nu
            V.append(np.array([math.cos(t) * math.cos(a), math.cos(t) * math.sin(a), math.sin(t)]))
    V.append(np.array([0, 0, 1.0]))
    V = np.array(V) * r + np.asarray(c, float)
    F, top = [], len(V) - 1
    ring = lambda j, i: 1 + j * nu + i % nu
    for i in range(nu):
        F.append((0, ring(0, i + 1), ring(0, i)))
        F.append((top, ring(nv - 2, i), ring(nv - 2, i + 1)))
    for j in range(nv - 2):
        for i in range(nu):
            F.append((ring(j, i), ring(j, i + 1), ring(j + 1, i + 1), ring(j + 1, i)))
    return V, F


def tube(P, rad, sides=8):
    """a capped tube along a polyline P (k, 3) with a radius per point -> (verts, faces)."""
    P = np.asarray(P, float); rad = np.broadcast_to(np.asarray(rad, float), (len(P),))
    V = []
    ref = np.array([0, 0, 1.0])
    for i, p in enumerate(P):
        d = P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]
        d /= max(1e-12, np.linalg.norm(d))
        a = np.cross(d, ref)
        if np.linalg.norm(a) < 1e-6:
            a = np.cross(d, [1.0, 0, 0])
        a /= np.linalg.norm(a); b = np.cross(d, a)
        for k in range(sides):
            t = 2 * math.pi * k / sides
            V.append(p + rad[i] * (a * math.cos(t) + b * math.sin(t)))
    V += [P[0], P[-1]]
    s0, s1 = len(V) - 2, len(V) - 1
    F = []
    for i in range(len(P) - 1):
        for k in range(sides):
            a_, b_ = i * sides + k, i * sides + (k + 1) % sides
            F.append((a_, b_, b_ + sides, a_ + sides))
    n = len(P) - 1
    for k in range(sides):
        F.append((s0, (k + 1) % sides, k))
        F.append((s1, n * sides + k, n * sides + (k + 1) % sides))
    return np.array(V), F


def _join(parts):
    """[(verts, faces, material index)] -> (verts, faces, per-face material index)."""
    V, F, M, o = [], [], [], 0
    for v, f, m in parts:
        V.append(np.asarray(v, float)); F += [tuple(int(i) + o for i in q) for q in f]; M += [m] * len(f); o += len(v)
    return np.vstack(V), F, np.array(M, np.int32)


# -------------------------------------------------------------------------------------------------------------- kinds
def star_outline(shape=None):
    """a star's outline in its plane (x right, y up; the height tip to tip = up + down) -> (k, 2) points, tips and the
    curved edges between them and the valleys."""
    S = dict(STAR, **(shape or {}))
    n = int(S['points'])
    tips = []
    for k in range(n):
        a = 90.0 - 360.0 * k / n                               # the first major point up, then clockwise
        r = S['up'] if k == 0 else S['down'] if n % 2 == 0 and k == n // 2 else S['side']
        tips.append((a, r))
    if S['minor'] > 0:
        off = S['minor_at'] if n == 4 else 180.0 / n
        tips += [(90.0 - 360.0 * k / n - off, S['minor']) for k in range(n)]
    tips = sorted(tips, key=lambda t: (90.0 - t[0]) % 360.0)        # clockwise from the top
    pol = lambda a, r: np.array([math.cos(math.radians(a)) * r, math.sin(math.radians(a)) * r])
    out = []
    m = len(tips)
    segs = max(1, int(S['segs']))
    for i in range(m):
        a0, r0 = tips[i]
        a1, r1 = tips[(i + 1) % m]
        span = (a0 - a1) % 360.0
        va = a0 - span / 2
        T, Vl = pol(a0, r0), pol(va, S['inner'])
        for (P0, P1) in ((T, Vl), (Vl, pol(a1, r1))):
            for j in range(segs):
                t = j / segs
                # a concave edge: its points pulled toward the middle along their ray (never across a point's axis)
                out.append((P0 + (P1 - P0) * t) * (1 - S['curve'] * math.sin(math.pi * t)))
    return np.array(out)


def star(shape=None):
    """a star clip, its back on the z = 0 plane, facing +z: the outline (star_outline) as a rim `thick` deep, the
    middle raised `depth` over it in facets from the rim to an apex (two per point: a drawn star's lit and shaded halves).
    `rings` > 1 splits the back and each facet into that many bands from the rim in (the same flat surface, vertices
    inside it for conform() to bend). -> (verts, faces), height (up + down) as in the shape (1 for the defaults). The
    vertices: the back's outline (m), the front's (m), the rings' (back then front, each ring m, the rim's first), the
    back's centre, the apex."""
    S = dict(STAR, **(shape or {}))
    R = star_outline(S)
    m = len(R)
    th, dp = S['thick'], S['depth']
    nr = max(1, int(S.get('rings', 1)))
    fr = [1.0 - j / nr for j in range(1, nr)]                  # the rings' share of the outline, the rim's first
    V = [(x, y, 0.0) for x, y in R] + [(x, y, th) for x, y in R]
    V += [(f * x, f * y, 0.0) for f in fr for x, y in R]
    V += [(f * x, f * y, th + dp * (1 - f)) for f in fr for x, y in R]
    V += [(0.0, 0.0, 0.0), (0.0, 0.0, th + dp)]
    cb, cf = len(V) - 2, len(V) - 1
    back = [list(range(m))] + [list(range(2 * m + j * m, 2 * m + (j + 1) * m)) for j in range(nr - 1)]
    front = [list(range(m, 2 * m))] + [list(range(2 * m + (nr - 1 + j) * m, 2 * m + (nr + j) * m)) for j in range(nr - 1)]
    F = []
    for k in range(m):
        k2 = (k + 1) % m
        F.append((cb, back[-1][k], back[-1][k2]))              # the back (faces -z: its outline's winding is clockwise)
        F.append((cf, front[-1][k2], front[-1][k]))            # the front facets (their innermost band: to the apex)
        F.append((k, m + k, m + k2, k2))                       # the rim
        for j in range(nr - 1):                                # the bands, rim inward (each in its facet's plane)
            F.append((back[j + 1][k], back[j][k], back[j][k2], back[j + 1][k2]))
            F.append((front[j + 1][k2], front[j][k2], front[j][k], front[j + 1][k]))
    return np.array(V, float), F


def _notched(V, c, axis_a, notch, depth=0.75):
    """a claw's pincer: vertices of a sphere round c whose direction (in the plane of axis_a and the view axis z) lies
    within notch/2 degrees of axis_a pulled toward the centre (a Pac-Man bite)."""
    V = V.copy()
    d = V - c
    a2 = np.array([axis_a[0], axis_a[1], 0.0]); a2 /= np.linalg.norm(a2)
    b2 = np.array([-a2[1], a2[0], 0.0])
    ang = np.degrees(np.arctan2(d @ b2, d @ a2))
    w = np.clip(1 - np.abs(ang) / (notch / 2), 0, 1)
    k = 1 - depth * w ** 0.7
    proj = (d @ a2)[:, None] * a2 + (d @ b2)[:, None] * b2
    return c + proj * k[:, None] + (d - proj)


def crab(shape=None):
    """a little crab clip, its back near the z = 0 plane, facing +z, the body 1 wide: a flattened ellipsoid body, two
    claws raised on arms (notched: the pincers), two eyes on stalks, legs along each side.
    -> (verts, faces, per-face material: 0 the shell, 1 the eyes)."""
    S = dict(CRAB, **(shape or {}))
    bw, bh, bd = 0.5, S['body_h'] / 2, S['body_d'] / 2
    parts = []
    V, F = sphere((0, 0, bd * 0.8), (bw, bh, bd), 16, 10)
    parts.append((V, F, 0))
    for sx in (-1, 1):
        cx, cy = S['claw_at'][0] * sx, S['claw_at'][1]
        cr = S['claw'] / 2
        c = np.array([cx, cy, bd * 0.9])
        # the arm: from the body's upper side out to the claw
        root = np.array([0.36 * sx, 0.12, bd * 0.9])
        mid = (root + c) / 2 + np.array([0.04 * sx, -0.02, 0])
        tv, tf = tube([root, mid, c - (c - root) / np.linalg.norm(c - root) * cr * 0.6], S['arm'], 8)
        parts.append((tv, tf, 0))
        cv, cf = sphere(c, (cr, cr * 0.95, cr * 0.7), 16, 10)
        up = math.radians(S['claw_up'])
        cv = _notched(cv, c, (math.sin(up) * -sx, math.cos(up)), S['claw_notch'])
        parts.append((cv, cf, 0))
        # an eye on its stalk
        ex, ey = S['eye_at'][0] * sx, S['eye_at'][1]
        base = np.array([ex * 0.9, bh * 0.55, bd * 1.2])
        top = np.array([ex, ey, bd * 1.3])
        sv, sf = tube([base, top], S['eyes'] * 0.35, 6)
        parts.append((sv, sf, 0))
        ev, ef = sphere(top, S['eyes'], 10, 6)
        parts.append((ev, ef, 1))
        # the legs: short bent sticks out and down the side
        n = int(S['legs'])
        a0, a1 = S['leg_span']
        for j in range(n):
            a = math.radians(a0 + (a1 - a0) * (j / max(1, n - 1)))
            r0 = np.array([bw * 0.85 * math.cos(a) * sx, bh * 0.85 * math.sin(a), bd * 0.7])
            dirv = np.array([math.cos(a) * sx, math.sin(a) - 0.25, 0.0]); dirv /= np.linalg.norm(dirv)
            knee = r0 + dirv * S['leg'] * 0.55 + np.array([0, 0.03, 0])
            foot = knee + (dirv + np.array([0, -0.6, 0])) / np.linalg.norm(dirv + np.array([0, -0.6, 0])) * S['leg'] * 0.5
            lv, lf = tube([r0, knee, foot], [S['leg_r'], S['leg_r'], S['leg_r'] * 0.6], 6)
            parts.append((lv, lf, 0))
    return _join(parts)


# ------------------------------------------------------------------------------------------------------------ placing
def _frame(V, az, el, tilt=0.0, lean=0.0):
    """a frame on the hair volume: origin on it, z = its outward normal leaned toward 'up', x across."""
    p = V.point(az, el)
    n = V.normal(az, el)
    up = np.array([0, 0, 1.0])
    x = np.cross(up, n)
    if np.linalg.norm(x) < 1e-6:
        x = np.array([1.0, 0, 0])
    x /= np.linalg.norm(x)
    y = np.cross(n, x)
    t = math.radians(tilt)
    x, y = x * math.cos(t) + y * math.sin(t), y * math.cos(t) - x * math.sin(t)
    lz = math.radians(lean)
    n2 = n * math.cos(lz) + y * math.sin(lz)
    y2 = y * math.cos(lz) - n * math.sin(lz)
    return p, np.stack([x, y2, n2], 1)          # columns: local x, y, z in world


def _dir(az, el):
    a, e = math.radians(az), math.radians(el)
    return np.array([math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)])


def _axes(z, tilt=0.0):
    """columns x, y, z: z the facing, y its up (the world's up made perpendicular), spun `tilt` degrees about z."""
    z = z / np.linalg.norm(z)
    up = np.array([0, 0, 1.0])
    x = np.cross(up, z)
    if np.linalg.norm(x) < 1e-6:
        x = np.array([1.0, 0, 0])
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    t = math.radians(tilt)
    x, y = x * math.cos(t) + y * math.sin(t), y * math.cos(t) - x * math.sin(t)
    return np.stack([x, y, z], 1)


class Ground:
    """the surfaces clips rest on (the hair's, then each clip placed): ray casts in world, charkit.hair's (Blender's BVH
    in Blender, charkit.geom's in the venv)."""

    def __init__(self, meshes=()):
        self.meshes = [(np.asarray(v, float), [tuple(int(i) for i in f) for f in F]) for v, F in meshes if len(v)]
        self._bvh = {}                                        # (venv) a mesh's BVH by its vertex array's identity
        self._added = set()                                   # (the clips placed on it: not kept)

    def add(self, V, F):
        V = np.asarray(V, float)
        self.meshes.append((V, [tuple(int(i) for i in f) for f in F]))
        self._added.add(id(V))

    def copy(self, n=None):
        """a new ground on the first n surfaces (all), sharing their BVHs (a fit places the clips many times on one
        hair)."""
        G = Ground()
        G.meshes = list(self.meshes[:n] if n is not None else self.meshes)
        G._bvh = getattr(self, '_bvh', {})
        G._added = set(getattr(self, '_added', ()))
        return G

    def _cast_one(self, V, F, O, D, R):
        try:
            import mathutils  # noqa: F401  (Blender: its own BVH, charkit.hair's)
        except ImportError:
            cache = getattr(self, '_bvh', None)
            if cache is not None and id(V) not in getattr(self, '_added', ()):
                key = id(V)
                if key not in cache or cache[key][0] is not V:
                    from .geom.bvh import BVH
                    from .geom.mesh import Mesh
                    cache[key] = (V, BVH(Mesh.from_polys(np.asarray(V, float), [tuple(f) for f in F])))
                t, _ = cache[key][1].ray_cast(O, D, R)
                return np.where(np.isfinite(t), t, np.nan)
        from .hair import _cast_in
        return _cast_in(V, F, O, D, R)

    def cast(self, O, D, R):
        """the nearest hit distance of each ray O + t D (t <= R) over every surface, NaN on a miss."""
        O, D = np.atleast_2d(O), np.atleast_2d(D)
        best = np.full(len(O), np.nan)
        for V, F in self.meshes:
            t = self._cast_one(V, F, O, np.broadcast_to(D, O.shape).copy(), R)
            best = np.where(np.isnan(best) | (t < best), np.where(np.isnan(t), best, t), best)
        return best

    def normal(self, p, r, out):
        """the area-weighted normal of the surfaces' triangles within r of p, each turned to face `out` (a thin lock's
        two sides agree) -> unit vector or None."""
        acc = np.zeros(3)
        for V, F in self.meshes:
            T = np.array([f[:3] for f in F if len(f) >= 3])
            if not len(T):
                continue
            for q in [f for f in F if len(f) == 4]:
                T = np.vstack([T, [q[0], q[2], q[3]]])
            c = V[T].mean(1)
            sel = np.linalg.norm(c - p, axis=1) < r
            if sel.any():
                a, b, cc = V[T[sel, 0]], V[T[sel, 1]], V[T[sel, 2]]
                nn = np.cross(b - a, cc - a)
                acc += (nn * np.sign(nn @ out)[:, None]).sum(0)
        ln = np.linalg.norm(acc)
        return acc / ln if ln > 1e-12 else None


def anchor(s, L, V=None, centre=None):
    """a clip's anchor and the direction out from the head there -> (p, out): 'at' is the point itself (seating then
    sets its depth along the facing), else the hair volume's surface at az / el."""
    if s.get('at') is not None and centre is not None:
        d = np.asarray(s['at'], float)
        return np.asarray(centre, float) + d * L, d / max(1e-12, np.linalg.norm(d))
    if V is None:
        raise ValueError('%s: no volume to place it on by az / el (give it "at")' % s.get('kind'))
    o = np.asarray(V.c, float)
    p = V.point(s['az'], s['el'])
    return p, (p - o) / max(1e-12, np.linalg.norm(p - o))


def place(v, s, L, V=None, centre=None, ground=None, frame=False):
    """a clip's local geometry (its back on z = 0, facing +z, in L) placed: anchored on the hair (anchor()), facing
    s['facing'] or the surface's normal, spun by 'tilt', and with the ground given, pushed out along its facing until
    its lowest point rests on the ground, plus 'lift'. -> world verts (and its axes, columns x, y, z, with frame)."""
    p, out = anchor(s, L, V, centre)
    size = s.get('size', 0.2) * L
    if s.get('facing') is not None:
        f = _dir(*s['facing'])
    else:
        n = None
        if ground is not None and ground.meshes:
            n = ground.normal(p, 0.5 * size, out)
        if n is None and V is not None and s.get('az') is not None:
            n = V.normal(s['az'], s['el'])
        n = out if n is None else n
        lz = math.radians(s.get('lean', 0.0))
        up = np.array([0, 0, 1.0])
        y = up - (up @ n) * n
        y = y / np.linalg.norm(y) if np.linalg.norm(y) > 1e-9 else np.array([0, 1.0, 0])
        f = n * math.cos(lz) + y * math.sin(lz)
    Rm = _axes(f, s.get('tilt', 0.0))
    w = p + (v * size) @ Rm.T
    if ground is not None and ground.meshes:
        fz = Rm[:, 2]
        R = 2.0 * L
        t = ground.cast(w + fz * R, -fz, 2 * R)
        h = t - R                                              # each vertex's height over the ground under it
        ok = np.isfinite(h)
        if ok.any():
            w = w + fz * (s.get('lift', 0.0) * L - h[ok].min())
    else:
        w = w + Rm[:, 2] * s.get('lift', 0.0) * L
    return (w, Rm) if frame else w


def _inside(P, poly):
    """points (n, 2) inside a closed polygon (k, 2) (even-odd) -> bool (n,)."""
    x, y = P[:, 0][:, None], P[:, 1][:, None]
    a, b = poly, np.roll(poly, -1, 0)
    cross = (a[:, 1] > y) != (b[:, 1] > y)
    xi = a[:, 0] + (y - a[:, 1]) * (b[:, 0] - a[:, 0]) / np.where(b[:, 1] == a[:, 1], 1e-12, b[:, 1] - a[:, 1])
    return ((cross & (x < xi)).sum(1) % 2) == 1


def conform(w, Rm, outline, under, L, reach=0.1, clear=0.004):
    """a placed clip bent over what lies under it (the star over the crab, Michael's call: shaped to the clip under
    it, so it neither floats on it nor lets it poke through): w its world verts (seated on the hair), Rm its axes
    (columns x, y, z = its facing), outline the indices of its back's outline, under [(verts, faces)] the clips it is
    drawn over. Each point of those clips inside the outline (or within `clear` of it) that rises above the clip's back
    needs the back `clear` L over it there; every vertex is lifted along the facing by the smooth envelope of those
    needs, each spread over `reach` L round its point ((1 - s^2)^2), so the back and the front move together (its
    thickness kept) and the rest stays on the hair. -> (world verts, the largest lift in L)."""
    q = (np.asarray(w, float) - w[outline[0]]) @ Rm                  # the clip's own frame (z along its facing)
    back = q[outline, 2].min()
    poly = q[outline, :2]
    pts = []
    for V, F in under:
        V = np.asarray(V, float)
        T = [f for f in F if len(f) >= 3]
        cen = np.array([V[list(f)].mean(0) for f in T]) if T else np.zeros((0, 3))
        pts.append(np.vstack([V, cen]))
    if not pts:
        return w, 0.0
    c = (np.vstack(pts) - w[outline[0]]) @ Rm
    near = _inside(c[:, :2], poly)
    if not near.all():                                              # within `clear` of the outline: the rim too
        d = np.min(np.linalg.norm(c[~near, None, :2] - poly[None], axis=2), 1)
        near[np.nonzero(~near)[0][d < clear * L]] = True
    # and exactly under each of the clip's own vertices: the top of what lies under it, cast down along the facing
    G = Ground(); G.meshes = [(np.asarray(V, float), F) for V, F in under]
    H = 4.0 * L
    top = (H - G.cast(np.asarray(w, float) + Rm[:, 2] * (H - (q[:, 2] - back)[:, None]), -Rm[:, 2], 2 * H)) + back
    hit = np.isfinite(top)
    c = np.vstack([c, np.c_[q[hit, :2], top[hit]]])
    near = np.r_[near, np.ones(hit.sum(), bool)]
    need = c[:, 2] - back + clear * L
    sel = near & (need > 0)
    if not sel.any():
        return w, 0.0
    c, need = c[sel], need[sel]
    r = reach * L
    lift = np.zeros(len(q))
    for i0 in range(0, len(c), 256):
        dd = np.linalg.norm(q[:, None, :2] - c[None, i0:i0 + 256, :2], axis=2) / r
        k = np.clip(1 - dd ** 2, 0, None) ** 2
        lift = np.maximum(lift, (k * need[None, i0:i0 + 256]).max(1))
    return w + Rm[:, 2][None] * lift[:, None], float(lift.max() / L)


def crown(sh=None):
    """a crown in L (placed by generate: its base ring's centre at the origin, up +z, the front toward -y): a band of
    height `height` * `band` round an ellipse of outer radii rx (x) and ry (y), `thick` thick, flaring `flare` of its
    radius wider at its top; `points` blades round its top edge (each `point_w` of the gap between points wide at its
    base, with side lobes `lobe` up its height: a fleur's three-part outline), up to `height`; `jewels` hemispheres
    round the band's middle, between the points, alternating two jewel materials.
    -> (verts, faces, per-face material: 0 the metal, 1 and 2 the jewels)."""
    K = dict(CROWN, **(sh or {}))
    rx, ry, H = K['rx'], K['ry'], K['height']
    hb, th, n, M = H * K['band'], K['thick'] * H, int(K['points']), int(K['segs'])
    V, F, Mt = [], [], []

    def ring(theta, z, inset=0.0):
        g = 1 + K['flare'] * min(z, hb) / max(hb, 1e-9)          # (the blades rise straight from the band's top)
        x, y = rx * g * np.sin(theta), -ry * g * np.cos(theta)
        r = np.hypot(x, y) + 1e-12
        return np.stack([x - inset * x / r, y - inset * y / r, np.full_like(theta, z)], -1)
    th_ = np.linspace(0, 2 * np.pi, M, endpoint=False)
    rows = [ring(th_, 0.0), ring(th_, hb), ring(th_, hb, th), ring(th_, 0.0, th)]   # outer bottom, top, inner top, bottom
    for r_ in rows:
        V += r_.tolist()
    for a in range(4):
        b = (a + 1) % 4
        for k in range(M):
            k2 = (k + 1) % M
            F.append((a * M + k, a * M + k2, b * M + k2, b * M + k)); Mt.append(0)
    # the points: a blade each (outer and inner faces, its sides), with side lobes
    for i in range(n):
        phi = 2 * np.pi * i / n
        half = K['point_w'] * np.pi / n
        t = np.array([phi - half, phi - 0.45 * half, phi, phi + 0.45 * half, phi + half])
        zs = np.array([hb, hb + K['lobe'] * (H - hb) * 1.1, H, hb + K['lobe'] * (H - hb) * 1.1, hb])
        o = np.array([ring(np.array([a]), z)[0] for a, z in zip(t, zs)])
        inn = np.array([ring(np.array([a]), z, th)[0] for a, z in zip(t, zs)])
        b0 = len(V)
        V += o.tolist() + inn.tolist()
        # the outline (the base, the lobes, the tip) as a fan from the base's middle on each face
        base_o = len(V); V.append(ring(np.array([phi]), hb)[0].tolist())
        base_i = len(V); V.append(ring(np.array([phi]), hb, th)[0].tolist())
        for j in range(4):
            F.append((base_o, b0 + j, b0 + j + 1)); Mt.append(0)
            F.append((base_i, b0 + 5 + j + 1, b0 + 5 + j)); Mt.append(0)
            F.append((b0 + j, b0 + 5 + j, b0 + 5 + j + 1, b0 + j + 1)); Mt.append(0)
    # the jewels: low hemispheres on the band's outer face, between the points
    for i in range(int(K['jewels'])):
        phi = 2 * np.pi * (i + 0.5) / K['jewels']
        c = ring(np.array([phi]), 0.5 * hb)[0]
        nrm = c[:2] / (np.linalg.norm(c[:2]) + 1e-12)
        nrm = np.array([nrm[0], nrm[1], 0.0])
        up = np.array([0, 0, 1.0]); side = np.cross(up, nrm)
        jr = K['jewel_r'] * H
        b0 = len(V)
        rings_ = 3; segs = 8
        for a in range(rings_):
            el = np.pi / 2 * a / rings_
            for k in range(segs):
                az = 2 * np.pi * k / segs
                d = np.cos(el) * (np.cos(az) * side + np.sin(az) * up) + np.sin(el) * nrm
                V.append((c + jr * d).tolist())
        top = len(V); V.append((c + jr * nrm).tolist())
        for a in range(rings_ - 1):
            for k in range(segs):
                k2 = (k + 1) % segs
                F.append((b0 + a * segs + k, b0 + a * segs + k2, b0 + (a + 1) * segs + k2, b0 + (a + 1) * segs + k))
                Mt.append(1 + i % 2)
        for k in range(segs):
            F.append((b0 + (rings_ - 1) * segs + k, b0 + (rings_ - 1) * segs + (k + 1) % segs, top)); Mt.append(1 + i % 2)
    return np.asarray(V, float), F, np.asarray(Mt, np.int32)


def pin(sh=None):
    """a round pin-back badge in L, its back on z = 0 facing +z: a disc of radius r, `thick` of r thick, its face domed
    `dome` of r, with a rim `rim` of r wide; `emblem` (optional): {'cells': rows of colour indices (0 none), 'colors'}
    over the face, square cells raised a little (an image's pixels: the badge's own drawing).
    -> (verts, faces, per-face material: 0 the face, 1 the rim, 2.. the emblem's colours)."""
    K = dict(PIN, **(sh or {}))
    r, M = K['r'], int(K['segs'])
    t, dome, rimw = K['thick'] * r, K['dome'] * r, K['rim'] * r
    a = np.linspace(0, 2 * np.pi, M, endpoint=False)
    V, F, Mt = [], [], []
    circ = lambda rr, z: np.stack([rr * np.cos(a), rr * np.sin(a), np.full(M, z)], -1)
    rings = [(r, 0.0, 1), (r, t, 1), (r - rimw, t + 0.3 * dome, 0)]
    for k in range(1, 5):                                     # the dome: rings rising to the centre
        f = k / 5
        rings.append(((r - rimw) * (1 - f), t + 0.3 * dome + dome * 0.7 * np.sin(f * np.pi / 2), 0))
    for rr, z, _ in rings:
        V += circ(rr, z).tolist()
    for j in range(len(rings) - 1):
        for k in range(M):
            k2 = (k + 1) % M
            F.append((j * M + k, j * M + k2, (j + 1) * M + k2, (j + 1) * M + k)); Mt.append(1 if j < 2 else 0)
    c = len(V); V.append([0.0, 0.0, t + dome]); last = (len(rings) - 1) * M
    for k in range(M):
        F.append((last + k, last + (k + 1) % M, c)); Mt.append(0)
    b = len(V); V.append([0.0, 0.0, 0.0])
    for k in range(M):
        F.append(((k + 1) % M, k, b)); Mt.append(1)
    em = K.get('emblem')
    if em and em.get('cells'):
        C = np.asarray(em['cells'], int)
        n = C.shape[0]
        cell = 2 * (r - rimw) / n
        for i in range(n):
            for j in range(C.shape[1]):
                if C[i, j] <= 0:
                    continue
                x0, y0 = -(r - rimw) + j * cell, (r - rimw) - (i + 1) * cell
                if max(np.hypot(x0 + a_ * cell, y0 + b_ * cell) for a_ in (0, 1) for b_ in (0, 1)) > r - rimw:
                    continue                                    # (only cells wholly on the face)
                d = (x0 + cell / 2) ** 2 + (y0 + cell / 2) ** 2
                z = t + 0.3 * dome + dome * 0.7 * np.sin(np.pi / 2 * (1 - np.sqrt(d) / (r - rimw))) + 0.004 * r
                b0 = len(V)
                V += [[x0, y0, z], [x0 + cell, y0, z], [x0 + cell, y0 + cell, z], [x0, y0 + cell, z]]
                F.append((b0, b0 + 1, b0 + 2, b0 + 3)); Mt.append(1 + int(C[i, j]))
    return np.asarray(V, float), F, np.asarray(Mt, np.int32)


def from_eyes(s, L, head):
    """a placement given from the eyes' middle ('from_eyes': [x, y, z] L, x her left, y toward her back, z up), the
    head's frame -> world point. head: the assembly's head info (centre, L, H, eye_knobs)."""
    c = np.asarray(head['centre'], float)
    ez = c[2] + head['eye_knobs']['z'] * L
    ey = c[1] - head['H'].df
    d = np.asarray(s['from_eyes'], float) * L
    return np.array([c[0], ey, ez]) + d


def generate(V, L, specs, ground=None, centre=None, with_mats=False, head=None):
    """accessory meshes: list of (name, verts, faces, spec) (and per-face material indices with_mats: 0 the main
    colour, 1 a crab's eyes). V: the hair volume (charkit.hair.Volume; the buns', and any clip placed by az / el); ground:
    the hair's surfaces [(verts, faces)] in world, which the clips rest on (each clip then on the ones before it too);
    centre: the head's centre ('at' placements)."""
    out = []
    G = ground.copy() if isinstance(ground, Ground) else Ground(ground) if ground is not None else None
    nh = len(G.meshes) if G is not None else 0                   # the hair's surfaces (then the clips placed so far)
    for i, s in enumerate(specs or []):
        k = s['kind']
        size = s.get('size', 0.2) * L
        mats = None
        if k == 'bun':
            p, R = _frame(V, s['az'], s['el'], s.get('tilt', 0.0), s.get('lean', 0.0))
            p = p + R[:, 2] * s.get('lift', 0.0) * L
            # stacked pads: a big square pad, a second behind and above it, a third behind that
            vs, fs, o = [], [], 0
            for j, (dy, dz, sc) in enumerate(((0.0, 0.0, 1.0), (0.12, 0.30, 0.86), (0.22, 0.52, 0.7))):
                v, f = rounded_box(1.0 * sc, 1.0 * sc, 0.42 * sc, 0.16 * sc, segs=3)
                v = v + np.array([0.0, dy, -dz]) * 1.0
                vs.append(v); fs += [tuple(a + o for a in q) for q in f]; o += len(v)
            v = np.vstack(vs); f = fs
            # the pad lies across the head: its thin axis (z) along the surface normal
            v = v * size + np.array([0, 0, 0.28 * size])
            w = p + v @ R.T
        elif k in ('star', 'crab'):
            cf = s.get('conform')
            cf = dict(CONFORM, **(cf if isinstance(cf, dict) else {})) if cf else None
            if k == 'star':
                sh = dict(s.get('shape') or {})
                if cf and 'rings' not in sh:
                    sh['rings'] = cf['rings']
                v, f = star(sh)
                v = v / max(1e-9, v[:, 1].max() - v[:, 1].min())       # the height tip to tip: 1 (then size L)
                rim = np.arange(len(star_outline(sh)))
            else:
                v, f, mats = crab(s.get('shape'))                         # the body 1 wide (size L)
                rim = None
            if cf and k == 'star' and G is not None and nh:
                # resting on the hair alone, then bent over the clips placed before it (conform())
                gh = G.copy(nh)
                w, Rm = place(v, s, L, V, centre, gh, frame=True)
                lift = 0.0
                if len(G.meshes) > nh:
                    w, lift = conform(w, Rm, rim, G.meshes[nh:], L, cf['reach'], cf['clear'])
                s = dict(s, conform_lift=round(lift, 4))                  # (the bend, L)
            else:
                w = place(v, s, L, V, centre, G)
            if G is not None:
                G.add(w, f)
        elif k == 'crown':                                    # round the head, its base ring placed from the eyes
            v, f, mats = crown(s.get('shape'))
            Rm = _axes(np.array([0.0, -1.0, 0.0]) if not s.get('facing') else _dir(*s['facing']), 0.0)
            base = from_eyes(s, L, head) if head is not None and s.get('from_eyes') is not None else \
                np.asarray(centre, float) + np.asarray(s.get('at', (0, 0, 0.5)), float) * L
            tilt = math.radians(s.get('tilt', 0.0))             # forward tilt about x
            Rt = np.array([[1, 0, 0], [0, math.cos(tilt), -math.sin(tilt)], [0, math.sin(tilt), math.cos(tilt)]])
            w = base + (v * L) @ Rt.T
        elif k == 'pin':                                      # on a garment's surface: placed, not seated on hair
            v, f, mats = pin(s.get('shape'))
            p = from_eyes(s, L, head) if head is not None and s.get('from_eyes') is not None else \
                np.asarray(centre, float) + np.asarray(s['at'], float) * L
            Rm = _axes(_dir(*s.get('facing', (0.0, 0.0))), s.get('tilt', 0.0))
            w = p + (v * L) @ Rm.T
        else:
            raise ValueError(k)
        rec = (s.get('name', f'{k}_{i}'), w, f, s)
        out.append(rec + ((mats if mats is not None else np.zeros(len(f), np.int32)),) if with_mats else rec)
    return out


def hair_ground(objects):
    """the hair's surfaces for generate's `ground` from Blender objects (world, the base meshes: no outline shell)."""
    out = []
    for ob in objects:
        if ob.type != 'MESH' or not len(ob.data.vertices):
            continue
        me = ob.data
        co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get('co', co)
        Mw = np.array(ob.matrix_world)
        V = co.reshape(-1, 3).astype(float) @ Mw[:3, :3].T + Mw[:3, 3]
        out.append((V, [tuple(p.vertices) for p in me.polygons]))
    return out


def build(A, arm, V, specs, mats, ground=None):
    """Blender objects for the accessories, parented to the head. mats: {kind: material} (or a spec's own 'material');
    ground: the hair's surfaces the clips rest on (hair_ground())."""
    from . import character, shade
    L = A['head']['L']
    obs = []
    for name, v, f, s, fm in generate(V, L, specs, ground=ground, centre=A['head']['centre'], with_mats=True,
                                      head=A['head']):
        m = mats.get(s.get('material', s['kind'])) or shade.flat(name + '_mat', s.get('color', (0.9, 0.9, 0.9)))
        ms = [m]
        if s.get('colors'):                                   # a kind with several materials (a crown's jewels, a
            ms += [shade.flat('%s_%d' % (name, j + 1), tuple(c)) for j, c in enumerate(s['colors'])]   # pin's emblem)
        elif (fm > 0).any():
            ms.append(shade.flat(name + '_eyes', s.get('eye_color', (0.12, 0.07, 0.07))))
        ob = character._mesh(name, v, f, None, ms)
        for p, mi in zip(ob.data.polygons, fm):
            p.use_smooth = s['kind'] != 'star'
            p.material_index = int(mi)
        import bmesh
        bm = bmesh.new(); bm.from_mesh(ob.data)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(ob.data); bm.free()
        shade.outline(ob, thick=0.0010, color=s.get('line', (0.35, 0.16, 0.12)), name=f'{name}_line')
        if s.get('bone'):                                     # rides its bone (a pin on the chest), else the head
            ob.parent = arm
            g = ob.vertex_groups.new(name=s['bone'])
            g.add(list(range(len(ob.data.vertices))), 1.0, 'REPLACE')
            md = ob.modifiers.new('rig', 'ARMATURE'); md.object = arm
        else:
            character._to_head(ob, arm)
        obs.append(ob)
    return obs
