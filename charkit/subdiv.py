"""Catmull-Clark subdivision in numpy, as Blender's Subdivision Surface modifier evaluates it at level 1 with its defaults
(limit surface on, creases used, boundaries smooth): one refinement with sharp rules on creased and boundary edges, then
every refined vertex moved to its limit position. The skin's modifier is level 1 in the viewport, which is what the QA
measures (charkit.trace.mesh_arrays), so charkit.faceeval gets the same surface without Blender.

    V1, quads, parent = subdiv.catmull_clark(V, faces, sharp_edges)   # parent: each quad's source face
"""
import numpy as np


def _pad(faces):
    """faces (list of tuples) -> (F, k) index array padded with -1, and the counts."""
    cnt = np.array([len(f) for f in faces])
    P = np.full((len(faces), cnt.max()), -1, np.int64)
    for k in np.unique(cnt):
        sel = np.nonzero(cnt == k)[0]
        P[sel, :k] = np.array([faces[i] for i in sel])
    return P, cnt


def catmull_clark(V, faces, sharp=(), limit=True):
    """one Catmull-Clark level. V (N, 3); faces: polygons (lists of vertex indices); sharp: (a, b) vertex pairs of the
    creased edges (infinitely sharp, like Blender's crease 1.0; open boundary edges are sharp too).
    -> (V1 (N + E + F, 3): the vertex, edge and face points, at their limit positions when limit; quads (4F', 4);
    parent (quads,): each quad's source face)."""
    V = np.asarray(V, float)
    N = len(V)
    P, cnt = _pad(faces)
    F = len(P)
    j = np.arange(P.shape[1])
    valid = j[None, :] < cnt[:, None]
    nxt = np.where(j[None, :] + 1 < cnt[:, None], np.roll(P, -1, 1), P[:, :1])
    fi, ci = np.nonzero(valid)
    a, b = P[fi, ci], nxt[fi, ci]
    lo, hi = np.minimum(a, b), np.maximum(a, b)
    key = lo * N + hi
    ek, einv = np.unique(key, return_inverse=True)
    E = len(ek)
    e0, e1 = ek // N, ek % N
    nfe = np.bincount(einv, minlength=E)                       # faces per edge
    sh = nfe != 2
    if len(sharp):
        s = np.asarray(sharp, np.int64)
        sk = np.minimum(s[:, 0], s[:, 1]) * N + np.maximum(s[:, 0], s[:, 1])
        sh |= np.isin(ek, sk)
    # face points
    fp = np.zeros((F, 3))
    np.add.at(fp, fi, V[a])
    fp /= cnt[:, None]
    # edge points: sharp -> midpoint; smooth -> the midpoint and the two face points averaged
    efp = np.zeros((E, 3))
    np.add.at(efp, einv, fp[fi])
    mid = (V[e0] + V[e1]) / 2
    ep = np.where(sh[:, None], mid, (V[e0] + V[e1] + efp) / 4)
    # vertex points
    val = np.bincount(np.r_[e0, e1], minlength=N)
    nsh = np.bincount(np.r_[e0[sh], e1[sh]], minlength=N)
    nf = np.bincount(a, minlength=N)
    Q = np.zeros((N, 3)); np.add.at(Q, a, fp[fi]); Q /= np.maximum(nf, 1)[:, None]
    R = np.zeros((N, 3)); np.add.at(R, e0, mid); np.add.at(R, e1, mid); R /= np.maximum(val, 1)[:, None]
    n = np.maximum(val, 1)[:, None]
    vp = (Q + 2 * R + (n - 3) * V) / n
    # creases and boundaries: (a + 6 v + b) / 8 along the two sharp edges; three or more: a corner, kept
    other = np.zeros((N, 3))
    np.add.at(other, e0[sh], V[e1[sh]]); np.add.at(other, e1[sh], V[e0[sh]])
    vp = np.where((nsh == 2)[:, None], (other + 6 * V) / 8, vp)
    vp = np.where((nsh > 2)[:, None], V, vp)
    vp = np.where((val == 0)[:, None], V, vp)
    V1 = np.vstack([vp, ep, fp])
    # the refined quads: per face corner (v, its next edge, the face, its previous edge)
    ecorner = np.full(P.shape, -1, np.int64)
    ecorner[fi, ci] = einv
    prev_e = np.where(j[None, :] == 0, ecorner[np.arange(F), cnt - 1][:, None], np.roll(ecorner, 1, 1))
    quads = np.stack([P[fi, ci], N + ecorner[fi, ci], N + E + fi, N + prev_e[fi, ci]], 1)
    # a quad's children keep its parametric origin as their first corner (OpenSubdiv's order in Blender): child j starts
    # j corners on, which decides the diagonal a fan triangulation takes
    r = np.where(cnt[fi] == 4, ci, 0)
    quads = quads[np.arange(len(quads))[:, None], (np.arange(4)[None, :] - r[:, None]) % 4]
    parent = fi
    if not limit:
        return V1, quads, parent
    # the limit positions on the refined all-quad mesh: smooth (n^2 v + 4 sum(edge nbrs) + sum(diagonals)) / (n (n + 5));
    # along a crease (e_a + 4 v + e_b) / 6; corners stay
    M = len(V1)
    q = quads
    sh1 = np.zeros(M, np.int64)                                # sharp edges per refined vertex
    s_other = np.zeros((M, 3))
    se = np.nonzero(sh)[0]
    for end in (e0[se], e1[se]):                               # a sharp edge's two children: (end, edge point)
        np.add.at(sh1, end, 1); np.add.at(s_other, end, V1[N + se])
        np.add.at(sh1, N + se, 1); np.add.at(s_other, N + se, V1[end])
    nq = np.bincount(q.ravel(), minlength=M)
    En = np.zeros((M, 3)); Dg = np.zeros((M, 3))
    for k in range(4):
        v_ = q[:, k]
        np.add.at(En, v_, V1[q[:, (k + 1) % 4]] + V1[q[:, (k + 3) % 4]])
        np.add.at(Dg, v_, V1[q[:, (k + 2) % 4]])
    n1 = np.maximum(nq, 1)[:, None].astype(float)
    Lm = (n1 * n1 * V1 + 2 * En + Dg) / (n1 * (n1 + 5))
    Lm = np.where((sh1 == 2)[:, None], (s_other + 4 * V1) / 6, Lm)
    Lm = np.where(((sh1 > 2) | (nq == 0))[:, None], V1, Lm)
    return Lm, quads, parent


def region(V, faces, keep):
    """the faces with every vertex in `keep` (bool per vertex), compacted: -> (V', faces', face indices, vertex indices)."""
    fk = [i for i, f in enumerate(faces) if all(keep[v] for v in f)]
    used = np.unique(np.concatenate([faces[i] for i in fk]))
    remap = np.full(len(V), -1, np.int64); remap[used] = np.arange(len(used))
    return V[used], [tuple(remap[list(faces[i])]) for i in fk], np.array(fk), used
