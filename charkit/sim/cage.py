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
    """the cage of a grid (NR, NC) of vertices V with face blocks Fm (NR-1, NC-1; periodic: (NR-1, NC), the last
    block joining column NC-1 to column 0, a ring like the skirt)."""

    def __init__(self, V, NR, NC, Fm, spacing, keep_rows=(), keep_cols=(), periodic=False):
        G = np.asarray(V, float).reshape(NR, NC, 3)
        self.NR, self.NC, self.periodic = NR, NC, periodic
        Gw = np.concatenate([G, G[:, :1]], 1) if periodic else G       # (a periodic grid's column 0 again at the end)
        NCw = Gw.shape[1]
        Fm = np.asarray(Fm, bool)[:, :NCw - 1]
        rg = np.linalg.norm(np.diff(Gw, axis=0), axis=2)          # (NR-1, NCw): row gaps per column
        cg = np.linalg.norm(np.diff(Gw, axis=1), axis=2)          # (NR, NCw-1)
        cmask = np.zeros((NR - 1, NCw), bool)
        cmask[:, :-1] |= Fm; cmask[:, 1:] |= Fm
        rmask = np.zeros((NR, NCw - 1), bool)
        rmask[:-1] |= Fm; rmask[1:] |= Fm
        row_gap = np.array([rg[j][cmask[j]].mean() if cmask[j].any() else rg[j].mean() for j in range(NR - 1)])
        col_gap = np.array([cg[:, i][rmask[:, i]].mean() if rmask[:, i].any() else cg[:, i].mean()
                            for i in range(NCw - 1)])
        self.rows, rs = _keep(row_gap, spacing, set(keep_rows))
        colsw, cs = _keep(col_gap, spacing, set(keep_cols))          # (extended indices; periodic: ends at NC = 0)
        self.cols = colsw[:-1] if periodic else colsw
        nr, nc = len(self.rows), len(self.cols)
        nb = len(colsw) - 1                                          # blocks across
        self.V = G[self.rows][:, self.cols].reshape(-1, 3).copy()
        right = lambda b: (b + 1) % nc if periodic else b + 1
        blocks = np.zeros((nr - 1, nb), bool)
        for a in range(nr - 1):
            for b in range(nb):
                blocks[a, b] = Fm[self.rows[a]:self.rows[a + 1], colsw[b]:colsw[b + 1]].any()
        self.blocks = blocks
        self.faces = [(a * nc + b, a * nc + right(b), (a + 1) * nc + right(b), (a + 1) * nc + b)
                      for a in range(nr - 1) for b in range(nb) if blocks[a, b]]
        n = NR * NC
        self.idx = np.zeros((n, 4), np.int64)
        self.w = np.zeros((n, 4))
        ra = np.clip(np.searchsorted(self.rows, np.arange(NR), side='right') - 1, 0, nr - 2)
        ca = np.clip(np.searchsorted(colsw, np.arange(NC), side='right') - 1, 0, nb - 1)
        for j in range(NR):
            for i in range(NC):
                a, b = ra[j], ca[i]
                cand = [(a, b)]
                if j == self.rows[a] and a > 0:
                    cand.append((a - 1, b))
                if i == colsw[b] and (b > 0 or periodic):
                    bl = (b - 1) % nb
                    cand.append((a, bl))
                    if j == self.rows[a] and a > 0:
                        cand.append((a - 1, bl))
                a, b = next((c for c in cand if blocks[c]), cand[0])
                r0, r1 = self.rows[a], self.rows[a + 1]
                c0, c1 = colsw[b], colsw[b + 1]
                ii = i if i >= c0 else i + NC                        # (the wrap block seen from its left: i = 0 -> NC)
                tr = (rs[j] - rs[r0]) / max(1e-15, rs[r1] - rs[r0])
                tc = (cs[ii] - cs[c0]) / max(1e-15, cs[c1] - cs[c0])
                k = j * NC + i
                self.idx[k] = (a * nc + b, a * nc + right(b), (a + 1) * nc + b, (a + 1) * nc + right(b))
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

    def attach(self, Vx):
        """extra vertices (a piece's ink strokes, which ride on its surface) carried as the template vertex nearest each
        is: its block and weights, with their own residual in that block's frame. carry() returns them after the
        template's."""
        from scipy.spatial import cKDTree
        Vx = np.asarray(Vx, float)
        if not len(Vx):
            return
        T0 = self.carry(self.V)
        nn = cKDTree(T0).query(Vx)[1]
        self.idx = np.concatenate([self.idx, self.idx[nn]])
        self.w = np.concatenate([self.w, self.w[nn]])
        B0 = self._bilinear(self.V)[-len(Vx):]
        F0 = self._frames(self.V)[-len(Vx):]
        self.res = np.concatenate([self.res, np.einsum('nki,ni->nk', F0, Vx - B0)])

    def carry(self, X):
        """the template's vertices carried by cage positions X."""
        return self._bilinear(X) + np.einsum('nki,nk->ni', self._frames(X), self.res)


def of_piece(o, spacing, keep_rows=(0, 1)):
    """the cage of a recorded grid-built garment (charkit.sim.drape.grid_of's layout; a ring when a face joins its last
    column to its first)."""
    from .drape import grid_of, grid_polys
    NR, NC = grid_of(o)
    Fm = np.zeros((NR - 1, NC), bool)
    periodic = False
    for f in grid_polys(o):
        f = np.asarray(f, np.int64)
        cols = set((f % NC).tolist())
        j = f.min() // NC
        if 0 in cols and NC - 1 in cols and NC > 2:
            Fm[j, NC - 1] = True                                     # the wrap block
            periodic = True
        else:
            Fm[j, f.min() % NC] = True
    if not periodic:
        Fm = Fm[:, :NC - 1]
    V = np.asarray(o['V'], float)
    K = Cage(V[:NR * NC], NR, NC, Fm, spacing, keep_rows=keep_rows, periodic=periodic)
    if len(V) > NR * NC:
        K.attach(V[NR * NC:])                                  # (the piece's ink strokes, after its grid)
    return K
