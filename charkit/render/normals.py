"""The shading normals Blender renders an outlined object with, per line width.

The outline SOLIDIFY (charkit.shade.outline: offset 1, negative thickness) moves an object's surface inward by the view's
line width, and Blender computes the moved surface's normals afresh: an object without custom normals (the garments,
most accessories) is shaded with the normals of the moved surface, not the ones the export stores (the surface with the
outline off). Where the width passes half a thin shell's thickness (the garments' 'thick' SOLIDIFY is 1.5-3 mm; the body
boards' screen lines are 3.6 mm) the two layers cross and the normals turn by up to 180 degrees (measured on a Clawd
build: the collar's p90 147 degrees). Objects whose export carries _HULL_NORMAL have custom normals transferred after
the outline (the skin's proxy normals, the hair's envelope ones): those don't change with the width.

    G = normals.Group(prims)          # one object's primitives (they share vertices along material seams)
    per_prim = G.normals(w)           # [ (n_i, 3) float32 ] for the surface moved inward by w x the outline factor

Blender's vertex normals: each face's normal (Newell's, for a quad) weighted by its corner angle, summed per vertex (the
mesh's vertices: the export's primitives welded back by their original position), normalised. The export triangulates;
a quad's two triangles come consecutively (Blender's loop triangles) and share an edge, so they are paired back into it.
Where the crossed layers twist a quad, its normal and its halves' differ by up to 90 degrees: with the quads the normals
match Blender's to p99 0.05 degrees (the collar, skirt, top and overskirt at the body boards' width); with triangles to
p99 1-93 degrees.
"""
import numpy as np


def needs_recompute(P):
    """an outlined primitive whose render normals follow its surface (no custom normals: no _HULL_NORMAL)."""
    return bool(P.outline) and P.hull_normal is None and P.look.get('kind') not in ('flat', 'plate')


class Group:
    def __init__(self, prims):
        self.prims = prims
        co = [p.co().astype(np.float32) for p in prims]
        self.sizes = [len(c) for c in co]
        self.off = np.concatenate([[0], np.cumsum(self.sizes)])
        self.co = np.concatenate(co)
        self.hull = np.concatenate([p.hull_dir() for p in prims]).astype(np.float64)
        self.ow = np.concatenate([p.width_factor() for p in prims]).astype(np.float64)
        key = np.ascontiguousarray(self.co).view(np.dtype((np.void, 12))).ravel()
        _, self.weld = np.unique(key, return_inverse=True)
        self.nw = int(self.weld.max()) + 1 if len(self.weld) else 0
        self.tri = np.concatenate([p.index.reshape(-1, 3).astype(np.int64) + o for p, o in zip(prims, self.off[:-1])])
        self.polys = quads(self.tri, self.weld)
        self._cache = {}

    def normals(self, w):
        """per primitive, (n, 3) float32 normals of the surface moved inward by w (m) x each vertex's outline factor."""
        k = round(float(w), 9)
        if k in self._cache:
            return self._cache[k]
        P = self.co.astype(np.float64) - self.hull * (w * self.ow)[:, None]
        acc = np.zeros((self.nw, 3))
        for R in self.polys:                             # triangles, then quads (loops in winding order)
            if not len(R):
                continue
            m = R.shape[1]
            V = P[R]
            fn = np.zeros((len(R), 3))
            for j in range(m):                           # Newell's normal
                fn += np.cross(V[:, j], V[:, (j + 1) % m])
            fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-30)
            for j in range(m):
                u, v = V[:, (j + 1) % m] - V[:, j], V[:, (j - 1) % m] - V[:, j]
                ang = np.arctan2(np.linalg.norm(np.cross(u, v), axis=1), np.einsum('ij,ij->i', u, v))
                idx = self.weld[R[:, j]]
                for d in range(3):
                    acc[:, d] += np.bincount(idx, fn[:, d] * ang, minlength=self.nw)
        vn = acc / np.maximum(np.linalg.norm(acc, axis=1, keepdims=True), 1e-30)
        n = vn[self.weld].astype(np.float32)
        out = [n[self.off[i]:self.off[i + 1]] for i in range(len(self.prims))]
        while len(self._cache) >= 4:                     # a few widths (the face and body boards' among them)
            self._cache.pop(next(iter(self._cache)))
        self._cache[k] = out
        return out


def quads(tri, weld):
    """the export's triangles paired back into Blender's quads: consecutive triangles sharing an edge (two welded
    vertices) and four vertices between them -> (triangles (k, 3), quads (q, 4)), each in its winding order."""
    W = weld[tri]
    n = len(tri)
    a, b = W[:-1], W[1:]
    shared = (a[:, :, None] == b[:, None, :]).any(2)             # (n-1, 3): each vertex of t in t+1
    ok = (shared.sum(1) == 2) & ((a[:, :, None] == b[:, None, :]).sum((1, 2)) == 2)
    start = np.zeros(n, bool)
    i = 0
    ok_l = ok.tolist()
    while i < n - 1:                                            # greedy: a pair takes both its triangles
        if ok_l[i]:
            start[i] = True
            i += 2
        else:
            i += 1
    taken = start.copy(); taken[1:] |= start[:-1]
    T0 = tri[~taken]
    s = np.nonzero(start)[0]
    x, y = tri[s], tri[s + 1]
    k = np.argmin(shared[s], 1)                                 # t's vertex not in t+1
    oy_k = np.argmin((weld[y][:, :, None] == weld[x][:, None, :]).any(2), 1)
    r = np.arange(len(s))
    Q = np.stack([x[r, k], x[r, (k + 1) % 3], y[r, oy_k], x[r, (k + 2) % 3]], 1)
    return [T0, Q]
