"""A simulation cage for a grid-built garment (the way production cloth runs: simulate a clean mesh, carry the render
mesh on it). The templates' grids are built for the render and the QA, not for a solver: the flaps' stair puts rows and
columns on every riser and band edge (edges from 0.002 L to 0.12 L on Clawd's flap), and the skirt's pleats are many
narrow columns. The cage keeps every grid line at least `spacing` of rest length from the last one kept (the first and
last, and any asked for, always kept), so its vertices are template vertices; a cage quad exists where any template face
in its block does. Every template vertex is carried bilinearly by its block's four cage vertices (weights from the rest
arc lengths along the grid lines) plus its rest residual turned with the block's frame, so the cage at rest gives the
template back exactly and the pleats and stair ride on it as detail.
"""
import numpy as np


def _keep(gaps, spacing, always=()):
    """indices 0..len(gaps) kept so that consecutive ones are at least `spacing` apart in cumulative gap length (the
    last always kept, the one before it dropped if too close; `always` kept whatever)."""
    s = np.r_[0.0, np.cumsum(gaps)]
    n = len(s)
    keep = [0]
    for i in range(1, n - 1):
        if i in always or s[i] - s[keep[-1]] >= spacing:
            keep.append(i)
    if keep[-1] != n - 1:
        if n - 1 - 0 > 0 and s[n - 1] - s[keep[-1]] < 0.5 * spacing and len(keep) > 1 and keep[-1] not in always:
            keep.pop()
        keep.append(n - 1)
    return np.array(sorted(set(keep) | set(always)), np.int64), s


class Cage:
    """the cage of a grid (NR, NC) of vertices V with face blocks Fm (NR-1, NC-1)."""

    def __init__(self, V, NR, NC, Fm, spacing, keep_rows=(), keep_cols=()):
        G = np.asarray(V, float).reshape(NR, NC, 3)
        self.NR, self.NC = NR, NC
        used_r = Fm.any(1)
        used_c = Fm.any(0)
        rg = np.linalg.norm(np.diff(G, axis=0), axis=2)          # (NR-1, NC): row gaps per column
        cg = np.linalg.norm(np.diff(G, axis=1), axis=2)          # (NR, NC-1)
        cmask = np.zeros((NR - 1, NC), bool)
        cmask[:, :-1] |= Fm; cmask[:, 1:] |= Fm
        rmask = np.zeros((NR, NC - 1), bool)
        rmask[:-1] |= Fm; rmask[1:] |= Fm
        row_gap = np.array([rg[j][cmask[j]].mean() if cmask[j].any() else rg[j].mean() for j in range(NR - 1)])
        col_gap = np.array([cg[:, i][rmask[:, i]].mean() if rmask[:, i].any() else cg[:, i].mean()
                            for i in range(NC - 1)])
        self.rows, rs = _keep(row_gap, spacing, set(keep_rows))
        self.cols, cs = _keep(col_gap, spacing, set(keep_cols))
        nr, nc = len(self.rows), len(self.cols)
        self.V = G[self.rows][:, self.cols].reshape(-1, 3).copy()
        # cage faces: a block exists where any template face inside it does
        blocks = np.zeros((nr - 1, nc - 1), bool)
        for a in range(nr - 1):
            for b in range(nc - 1):
                blocks[a, b] = Fm[self.rows[a]:self.rows[a + 1], self.cols[b]:self.cols[b + 1]].any()
        self.blocks = blocks
        self.faces = [(a * nc + b, a * nc + b + 1, (a + 1) * nc + b + 1, (a + 1) * nc + b)
                      for a in range(nr - 1) for b in range(nc - 1) if blocks[a, b]]
        # each template vertex's block (one that is a cage face when it can be) and its bilinear weights
        n = NR * NC
        self.idx = np.zeros((n, 4), np.int64)
        self.w = np.zeros((n, 4))
        ra = np.clip(np.searchsorted(self.rows, np.arange(NR), side='right') - 1, 0, nr - 2)
        ca = np.clip(np.searchsorted(self.cols, np.arange(NC), side='right') - 1, 0, nc - 2)
        for j in range(NR):
            for i in range(NC):
                a, b = ra[j], ca[i]
                cand = [(a, b)]
                if j == self.rows[a] and a > 0:
                    cand.append((a - 1, b))
                if i == self.cols[b] and b > 0:
                    cand.append((a, b - 1))
                    if j == self.rows[a] and a > 0:
                        cand.append((a - 1, b - 1))
                a, b = next((c for c in cand if blocks[c]), cand[0])
                r0, r1 = self.rows[a], self.rows[a + 1]
                c0, c1 = self.cols[b], self.cols[b + 1]
                tr = (rs[j] - rs[r0]) / max(1e-15, rs[r1] - rs[r0])
                tc = (cs[i] - cs[c0]) / max(1e-15, cs[c1] - cs[c0])
                k = j * NC + i
                self.idx[k] = (a * nc + b, a * nc + b + 1, (a + 1) * nc + b, (a + 1) * nc + b + 1)
                self.w[k] = ((1 - tr) * (1 - tc), (1 - tr) * tc, tr * (1 - tc), tr * tc)
        self.used = np.zeros(len(self.V), bool)
        if self.faces:
            self.used[np.unique(np.asarray(self.faces).ravel())] = True
        # rest residuals in each block's frame (so a turned block turns its detail with it)
        B0 = self._bilinear(self.V)
        self.frames0 = self._frames(self.V)
        self.res = np.einsum('nki,ni->nk', self.frames0, np.asarray(V, float) - B0)     # (local coordinates)

    def _bilinear(self, X):
        return np.einsum('nk,nkd->nd', self.w, X[self.idx])

    def _frames(self, X):
        """per template vertex its block's orthonormal frame (rows: along the columns, across, the normal)."""
        P = X[self.idx]                                            # (n, 4, 3): (a,b) (a,b+1) (a+1,b) (a+1,b+1)
        du = (P[:, 1] - P[:, 0]) + (P[:, 3] - P[:, 2])
        dv = (P[:, 2] - P[:, 0]) + (P[:, 3] - P[:, 1])
        e1 = du / np.maximum(np.linalg.norm(du, axis=1, keepdims=True), 1e-15)
        nrm = np.cross(du, dv)
        e3 = nrm / np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-15)
        e2 = np.cross(e3, e1)
        return np.stack([e1, e2, e3], 1)                           # (n, 3, 3): rows e1, e2, e3

    def carry(self, X):
        """the template's vertices carried by cage positions X."""
        return self._bilinear(X) + np.einsum('nki,nk->ni', self._frames(X), self.res)


def of_piece(o, spacing, keep_rows=(0, 1)):
    """the cage of a recorded grid-built garment (charkit.sim.drape.grid_of's layout)."""
    from .drape import grid_of
    NR, NC = grid_of(o)
    Fm = np.zeros((NR - 1, NC - 1), bool)
    for f in o['polys']:
        f = np.asarray(f, np.int64)
        j, i = f.min() // NC, f.min() % NC
        Fm[j, i] = True
    return Cage(o['V'], NR, NC, Fm, spacing, keep_rows=keep_rows)
