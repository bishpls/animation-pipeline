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

Blender's vertex normals: each face's normal weighted by its corner angle, summed per vertex (the mesh's vertices: the
export's primitives welded back by their original position), normalised. Triangles stand in for Blender's quads (their
corner angles sum to the quad's at the diagonal, and a quad's two halves share its normal where it is planar).
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
        self._cache = {}

    def normals(self, w):
        """per primitive, (n, 3) float32 normals of the surface moved inward by w (m) x each vertex's outline factor."""
        k = round(float(w), 9)
        if k in self._cache:
            return self._cache[k]
        P = self.co.astype(np.float64) - self.hull * (w * self.ow)[:, None]
        T = self.tri
        a, b, c = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
        fn = np.cross(b - a, c - a)
        fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-30)

        def angle(p, q, r):
            u, v = q - p, r - p
            return np.arctan2(np.linalg.norm(np.cross(u, v), axis=1), np.einsum('ij,ij->i', u, v))
        acc = np.zeros((self.nw, 3))
        for j, (p, q, r) in enumerate(((a, b, c), (b, c, a), (c, a, b))):
            wgt = fn * angle(p, q, r)[:, None]
            idx = self.weld[T[:, j]]
            for d in range(3):
                acc[:, d] += np.bincount(idx, wgt[:, d], minlength=self.nw)
        vn = acc / np.maximum(np.linalg.norm(acc, axis=1, keepdims=True), 1e-30)
        n = vn[self.weld].astype(np.float32)
        out = [n[self.off[i]:self.off[i + 1]] for i in range(len(self.prims))]
        self._cache = {k: out}                       # the last width only (views sharing a width come together)
        return out
