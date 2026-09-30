"""The hull's labelled shell as points (charkit.geom.hull's hull.npz): one point per labelled surface voxel, and the
stray patches a view's labels leave round a piece. Moved out of charkit.garments (which re-exports them) so that
charkit.code_body can read the shell without the garments' module in its code closure (the hair stage reads the body
code: every garment edit would have rebuilt the hair). Numpy only.
"""
import numpy as np


STRAY = (0.05, 0.0064)     # a piece's label patch dropped as stray: under this share of its largest patch and this area
                           # (L^2; 64 voxels at the hull's 0.01 L). The views' labels leave small patches round a piece
                           # (a wrist cuff's up the forearm, a boot cuff's out on the skirt): a decimated mesh gave
                           # their flat stretches few vertices, but on the shell they count by area and moved the bands'
                           # spans and radii (wrist_R's start 0.055 L up the arm, boot_cuff_L's radius 0.27 -> 0.37 L)


def shell_points(Z, stray=STRAY):
    """the hull's labelled shell as points on its surface (hull.npz, charkit.geom.hull.build's: the occupancy V on the
    axes xs, ys, zs, its shell voxels' indices and their labels): per shell voxel (occupied, with an empty face
    neighbour; outside the grid is empty), the mean of the centres of its faces toward empty neighbours, so each point
    lies on the occupancy's boundary (where the mesh's surface is, within half a voxel: the mesh is that boundary
    blurred a voxel; median offset -0.0001 L on Clawd), one point per labelled voxel whatever the mesh's decimation.
    stray (share, area L^2): a label's patches (shell_patches) under both are left out (None keeps them). Numpy only (the
    build's Python has no scipy). -> (P (n, 3) in the hull's frame, labels (n,))."""
    V = np.asarray(Z['V'], bool)
    S = np.asarray(Z['shell'], np.int64)
    lab = np.asarray(Z['shell_label'])
    ax = [np.asarray(Z[k], float) for k in ('xs', 'ys', 'zs')]
    C = np.stack([ax[k][S[:, k]] for k in range(3)], 1)
    Vp = np.pad(V, 1)
    I = S + 1
    off = np.zeros_like(C)
    n = np.zeros(len(C))
    for k in range(3):
        step = ax[k][1] - ax[k][0]                               # the index's step in the frame (zs runs down)
        for sgn in (-1, 1):
            J = I.copy()
            J[:, k] += sgn
            empty = ~Vp[J[:, 0], J[:, 1], J[:, 2]]
            off[:, k] += np.where(empty, 0.5 * sgn * step, 0.0)
            n += empty
    P = C + off / np.maximum(n, 1)[:, None]
    if stray:
        size, largest = shell_patches(S, lab)
        h = abs(ax[0][1] - ax[0][0])
        keep = (size >= stray[0] * largest) | (size * h * h >= stray[1])
        P, lab = P[keep], lab[keep]
    return P, lab


def shell_patches(S, lab):
    """each shell voxel's patch: the voxels of its label it connects to (26-neighbours) -> (the patch's size, the size of
    its label's largest patch), per voxel. Numpy union-find: roots hooked to the least root they touch, then paths
    compressed, until every neighbour pair shares a root."""
    S = np.asarray(S, np.int64)
    n = len(S)
    if not n:
        return np.zeros(0, np.int64), np.zeros(0, np.int64)
    dim = S.max(0) + 3
    key = ((S[:, 0] + 1) * dim[1] + S[:, 1] + 1) * dim[2] + S[:, 2] + 1
    order = np.argsort(key, kind='stable')
    ks = key[order]
    a, b = [], []
    for d in [(i, j, k) for i in (-1, 0, 1) for j in (-1, 0, 1) for k in (-1, 0, 1) if (i, j, k) > (0, 0, 0)]:
        q = key + (d[0] * dim[1] + d[1]) * dim[2] + d[2]
        pos = np.minimum(np.searchsorted(ks, q), n - 1)
        hit = ks[pos] == q
        i_, j_ = np.nonzero(hit)[0], order[pos[hit]]
        same = lab[i_] == lab[j_]
        a.append(i_[same]); b.append(j_[same])
    a, b = np.concatenate(a), np.concatenate(b)
    root = np.arange(n)
    while True:
        ra, rb = root[a], root[b]
        diff = ra != rb
        if not diff.any():
            break
        np.minimum.at(root, np.maximum(ra, rb)[diff], np.minimum(ra, rb)[diff])
        while True:
            r2 = root[root]
            if (r2 == root).all():
                break
            root = r2
    size = np.bincount(root, minlength=n)[root]
    largest = np.zeros(int(lab.max()) - int(lab.min()) + 1, np.int64)
    np.maximum.at(largest, lab - lab.min(), size)
    return size, largest[lab - lab.min()]
