"""A head's topology authored in code: a quad cage with concentric loops round each eye and round the mouth, and a neck
of rings under the jaw, so the head is all quads with the edge flow a face rig needs (lid loops, a mouth loop) and
nothing inherited from a scanned or realistic base. charkit.geom.headfit gives it the design's shape.

The cage is a box lattice in head space (L, origin on the eye line's middle, x her left, y back, z up): grid lines per
axis (`lines`), its surface split into quads. The box's front face (y = its front) is the front view's plane, so a
feature is placed where the front view draws it:

  loops    a feature's block of cells (bw x bh) is taken out of the front face; its boundary (2 (bw + bh) vertices) is
           the outermost loop, and `rings` loops step in from it to the feature's own outline (the eye's lid margin, the
           mouth's lip line), each step a band of quads matched vertex for vertex.
  caps     the innermost loop has the perimeter of a bw x bh grid, so a Coons patch fills it with quads: the eye's
           cap (where the eye plate sits) and the mouth's (the cavity attaches at its loop), as their own face groups a
           build can drop.
  neck     a block of the bottom face's cells opens into rings going down, open at the bottom (the body's neck joins
           there).

    cage(...) -> Cage(V, F (quads), group per face, groups (names), loops {name: [rings, outer to inner or top down]})
"""
import numpy as np


def lines(lo, hi, cell, must=()):
    """monotone grid lines from lo to hi about `cell` apart, passing through every value of `must` inside."""
    knots = sorted({float(lo), float(hi), *[float(m) for m in must if lo < m < hi]})
    out = [knots[0]]
    for a, b in zip(knots, knots[1:]):
        out += list(np.linspace(a, b, max(1, int(round((b - a) / cell))) + 1)[1:])
    return np.array(out)


class Cage:
    def __init__(self):
        self.V, self.F, self.group, self.groups, self.loops = [], [], [], [], {}
        self._key = {}

    def vert(self, p, key=None):
        if key is not None and key in self._key:
            return self._key[key]
        self.V.append(np.asarray(p, float))
        i = len(self.V) - 1
        if key is not None:
            self._key[key] = i
        return i

    def face(self, idx, group, outward):
        """a quad, wound so its normal points along `outward` (a vector, or a point it faces away from: ('from', p))."""
        P = np.array([self.V[i] for i in idx])
        n = np.cross(P[2] - P[0], P[3] - P[1])
        ref = (P.mean(0) - np.asarray(outward[1])) if outward[0] == 'from' else np.asarray(outward, float)
        if n @ ref < 0:
            idx = idx[::-1]
        if group not in self.groups:
            self.groups.append(group)
        self.F.append(list(idx))
        self.group.append(self.groups.index(group))

    def arrays(self):
        self.V, self.F, self.group = np.array(self.V), np.array(self.F, np.int64), np.array(self.group)
        return self


SIDES = {  # outward normal: (fixed axis, fixed index 0 or -1, the two free axes)
    'front': (1, 0, (0, 2)), 'back': (1, -1, (0, 2)), 'right': (0, 0, (1, 2)), 'left': (0, -1, (1, 2)),
    'bottom': (2, 0, (0, 1)), 'top': (2, -1, (0, 1)),
}


def _loop(ia, ib):
    """the lattice perimeter of cells ia[0]..ia[1] x ib[0]..ib[1] (index ranges, end exclusive), counter-clockwise in
    (a, b) from the (a0, b0) corner -> [(a, b)] (2 (wa + wb) points)."""
    a0, a1 = ia; b0, b1 = ib
    return ([(a, b0) for a in range(a0, a1)] + [(a1, b) for b in range(b0, b1)] +
            [(a, b1) for a in range(a1, a0, -1)] + [(a0, b) for b in range(b1, b0, -1)])


def _coons(loop, wa, wb):
    """a Coons patch's interior points for a loop of 2 (wa + wb) points laid out as _loop's (bottom, right, top, left)
    -> (wa + 1, wb + 1, 3) grid, the loop on its rim."""
    P = np.asarray(loop, float)
    bottom = P[0:wa + 1]
    right = P[wa:wa + wb + 1]
    top = P[wa + wb:2 * wa + wb + 1][::-1]
    left = np.concatenate([P[2 * wa + wb:], P[:1]])[::-1]
    G = np.zeros((wa + 1, wb + 1, P.shape[1]))
    for i in range(wa + 1):
        for j in range(wb + 1):
            s, t = i / wa, j / wb
            G[i, j] = ((1 - t) * bottom[i] + t * top[i] + (1 - s) * left[j] + s * right[j]
                       - ((1 - s) * (1 - t) * bottom[0] + s * (1 - t) * bottom[-1] + (1 - s) * t * top[0] + s * t * top[-1]))
    return G


def _outline_at(outline, centre, angles):
    """a closed outline (K, 2) sampled where rays from `centre` at `angles` cross it (a star-shaped outline)."""
    O = np.asarray(outline, float) - centre
    th = np.arctan2(O[:, 1], O[:, 0]); r = np.hypot(O[:, 0], O[:, 1])
    o = np.argsort(th)
    th, r = th[o], r[o]
    th = np.r_[th[-1] - 2 * np.pi, th, th[0] + 2 * np.pi]; r = np.r_[r[-1], r, r[0]]
    rr = np.interp(angles, th, r)
    return centre + np.stack([rr * np.cos(angles), rr * np.sin(angles)], 1)


def cage(X, Y, Z, features=(), neck=None):
    """the head's cage on the box lattice of grid lines X, Y, Z (L). features: [dict(name, box (x0, x1, z0, z1): the
    block, on grid lines, outline (K, 2) front-view (x, z) points round it, rings, cap (bool), spacing (the rings' steps
    toward the outline, 0..1, default even))]; neck: dict(box (x0, x1, y0, y1) on grid lines, rings: [(z drop, radius
    scale)], radius (the ring's target (rx, ry)) -> Cage."""
    C = Cage()
    N = (len(X) - 1, len(Y) - 1, len(Z) - 1)
    L = (X, Y, Z)
    centre = np.array([(X[0] + X[-1]) / 2, (Y[0] + Y[-1]) / 2, (Z[0] + Z[-1]) / 2])

    def lat(i, j, k):
        return C.vert((X[i], Y[j], Z[k]), ('lat', i, j, k))

    def index(axis, v):
        k = int(np.argmin(np.abs(L[axis] - v)))
        if abs(L[axis][k] - v) > 1e-9:
            raise ValueError('%s = %.4f is not a grid line' % ('xyz'[axis], v))
        return k
    holes = {'front': [], 'bottom': []}
    for f in features:
        x0, x1, z0, z1 = f['box']
        holes['front'].append((index(0, x0), index(0, x1), index(2, z0), index(2, z1)))
    if neck:
        x0, x1, y0, y1 = neck['box']
        holes['bottom'].append((index(0, x0), index(0, x1), index(1, y0), index(1, y1)))
    for side, (ax, at, (fa, fb)) in SIDES.items():
        fixed = 0 if at == 0 else N[ax]
        nrm = np.zeros(3); nrm[ax] = -1 if at == 0 else 1
        for a in range(N[fa]):
            for b in range(N[fb]):
                if any(h[0] <= a < h[1] and h[2] <= b < h[3] for h in holes.get(side, [])):
                    continue
                q = []
                for da, db in ((0, 0), (1, 0), (1, 1), (0, 1)):
                    ijk = [0, 0, 0]; ijk[ax] = fixed; ijk[fa] = a + da; ijk[fb] = b + db
                    q.append(lat(*ijk))
                C.face(q, 'face' if side == 'front' else 'skull' if side != 'bottom' else 'jaw', nrm)
    for f, (i0, i1, k0, k1) in zip(features, holes['front']):
        wa, wb = i1 - i0, k1 - k0
        ring0 = [lat(i, 0, k) for i, k in _loop((i0, i1), (k0, k1))]
        B = np.array([C.V[i] for i in ring0])[:, [0, 2]]
        c = np.array([(X[i0] + X[i1]) / 2, (Z[k0] + Z[k1]) / 2])
        inner = _outline_at(f['outline'], c, np.arctan2(B[:, 1] - c[1], B[:, 0] - c[0]))
        R = int(f.get('rings', 3))
        ts = f.get('spacing') or [r / R for r in range(1, R + 1)]
        rings = [ring0]
        for r, t in enumerate(ts, 1):
            P = (1 - t) * B + t * inner
            rings.append([C.vert((p[0], Y[0], p[1])) for p in P])
        for r in range(R):
            o, n = rings[r], rings[r + 1]
            for i in range(len(o)):
                j = (i + 1) % len(o)
                C.face([o[i], o[j], n[j], n[i]], '%s_r%d' % (f['name'], r), (0, -1, 0))
        C.loops[f['name']] = rings
        if f.get('cap', True):
            G = _coons([C.V[i] for i in rings[-1]], wa, wb)
            rim = {p: rings[-1][n] for n, p in enumerate(_loop((0, wa), (0, wb)))}
            gi = {}
            for i in range(wa + 1):
                for j in range(wb + 1):
                    gi[i, j] = rim.get((i, j)) if (i, j) in rim else C.vert(G[i, j])
            for i in range(wa):
                for j in range(wb):
                    C.face([gi[i, j], gi[i + 1, j], gi[i + 1, j + 1], gi[i, j + 1]], f['name'] + '_cap', (0, -1, 0))
    if neck:
        i0, i1, j0, j1 = holes['bottom'][0]
        top = [lat(i, j, 0) for i, j in _loop((i0, i1), (j0, j1))]
        P = np.array([C.V[i] for i in top])
        c = np.array([(X[i0] + X[i1]) / 2, (Y[j0] + Y[j1]) / 2])
        ang = np.arctan2(P[:, 1] - c[1], P[:, 0] - c[0])
        rx, ry = neck['radius']
        rings = [top]
        for r, (drop, scale) in enumerate(neck['rings'], 1):
            circle = c + np.stack([rx * scale * np.cos(ang), ry * scale * np.sin(ang)], 1)
            w = min(1.0, r / 2)                                      # the box's square opening rounds within two rings
            xy = (1 - w) * P[:, :2] + w * circle
            rings.append([C.vert((p[0], p[1], Z[0] - drop)) for p in xy])
        for r in range(len(rings) - 1):
            o, n = rings[r], rings[r + 1]
            for i in range(len(o)):
                j = (i + 1) % len(o)
                ctr = np.array([c[0], c[1], (C.V[o[i]][2] + C.V[n[i]][2]) / 2])
                C.face([o[i], o[j], n[j], n[i]], 'neck', ('from', ctr))
        C.loops['neck'] = rings
    C.centre = centre
    return C.arrays()


def edges(F):
    """directed edges of quads -> (E, 2)."""
    return np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 3]], F[:, [3, 0]]])


def check(C):
    """the cage's health: quads only, every edge in at most two faces and wound oppositely there, the boundary loops,
    Euler characteristic, signed volume -> dict."""
    E = edges(C.F)
    und = np.sort(E, 1)
    key, cnt = np.unique(und[:, 0] * len(C.V) + und[:, 1], return_counts=True)
    dkey, dcnt = np.unique(E[:, 0] * len(C.V) + E[:, 1], return_counts=True)
    boundary = key[cnt == 1]
    V, F = C.V, C.F
    vol = 0.0
    for a, b, c in ((0, 1, 2), (0, 2, 3)):
        vol += np.einsum('ij,ij->i', V[F[:, a]], np.cross(V[F[:, b]], V[F[:, c]])).sum() / 6
    used = np.unique(F)
    return {'verts': len(V), 'quads': len(F), 'unused_verts': int(len(V) - len(used)),
            'nonmanifold_edges': int((cnt > 2).sum()), 'misoriented_edges': int((dcnt > 1).sum()),
            'boundary_edges': int(len(boundary)), 'euler': int(len(used) - len(key) + len(F)), 'volume': float(vol)}
