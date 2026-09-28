"""Small synthetic meshes for tests and cutters: closed and outward-oriented unless said otherwise."""
import numpy as np

from .mesh import Mesh


def icosphere(subdiv=3, r=1.0, centre=(0, 0, 0)):
    t = (1 + 5 ** 0.5) / 2
    V = np.array([(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
                  (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)], float)
    F = np.array([(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6),
                  (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10),
                  (8, 6, 7), (9, 8, 1)], np.int64)
    V /= np.linalg.norm(V, axis=1, keepdims=True)
    for _ in range(subdiv):
        E = np.sort(np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), axis=1)
        U, inv = np.unique(E, axis=0, return_inverse=True)
        inv = inv.ravel()
        mid = V[U].mean(1)
        mid /= np.linalg.norm(mid, axis=1, keepdims=True)
        m = len(F)
        a, b, c = F[:, 0], F[:, 1], F[:, 2]
        ab, bc, ca = inv[:m] + len(V), inv[m:2 * m] + len(V), inv[2 * m:] + len(V)
        V = np.vstack([V, mid])
        F = np.concatenate([np.stack([a, ab, ca], 1), np.stack([b, bc, ab], 1), np.stack([c, ca, bc], 1),
                            np.stack([ab, bc, ca], 1)])
    return Mesh(V * r + np.asarray(centre, float), F)


def box(size=(1, 1, 1), centre=(0, 0, 0), n=1):
    """an axis-aligned box, each face a grid of n x n quads (2 triangles each), shared vertices on the edges."""
    sx, sy, sz = np.asarray(size, float) / 2
    g = np.linspace(-1, 1, n + 1)
    Vs, Fs = [], []
    # six faces: (normal axis, sign)
    for ax in range(3):
        for sg in (-1, 1):
            u, v = [k for k in range(3) if k != ax]
            U, W = np.meshgrid(g, g, indexing='ij')
            P = np.zeros((n + 1, n + 1, 3))
            P[..., ax] = sg; P[..., u] = U; P[..., v] = W
            idx = np.arange((n + 1) ** 2).reshape(n + 1, n + 1) + sum(len(x) for x in Vs)
            q = np.stack([idx[:-1, :-1], idx[1:, :-1], idx[1:, 1:], idx[:-1, 1:]], -1).reshape(-1, 4)
            T = np.concatenate([q[:, [0, 1, 2]], q[:, [0, 2, 3]]])
            # orient outward: (u, v, ax) right-handed?
            right = np.cross(np.eye(3)[u], np.eye(3)[v])[ax] * sg > 0
            if not right:
                T = T[:, ::-1]
            Vs.append(P.reshape(-1, 3)); Fs.append(T)
    V = np.vstack(Vs) * np.array([sx, sy, sz]) + np.asarray(centre, float)
    F = np.vstack(Fs)
    from .repair import merge_close
    return merge_close(Mesh(V, F), 1e-9 * max(sx, sy, sz))


def torus(R=1.0, r=0.3, nu=48, nv=24, centre=(0, 0, 0)):
    u = np.linspace(0, 2 * np.pi, nu, endpoint=False)
    v = np.linspace(0, 2 * np.pi, nv, endpoint=False)
    U, W = np.meshgrid(u, v, indexing='ij')
    X = (R + r * np.cos(W)) * np.cos(U); Y = (R + r * np.cos(W)) * np.sin(U); Z = r * np.sin(W)
    V = np.stack([X, Y, Z], -1).reshape(-1, 3) + np.asarray(centre, float)
    i, j = np.meshgrid(np.arange(nu), np.arange(nv), indexing='ij')
    a = i * nv + j; b = ((i + 1) % nu) * nv + j; c = ((i + 1) % nu) * nv + (j + 1) % nv; d = i * nv + (j + 1) % nv
    F = np.concatenate([np.stack([a, b, c], -1).reshape(-1, 3), np.stack([a, c, d], -1).reshape(-1, 3)])
    return Mesh(V, F)


def cylinder(r=0.5, h=1.0, n=32, rows=8, capped=True, centre=(0, 0, 0)):
    """along z; capped=False leaves two open boundary loops."""
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    z = np.linspace(-h / 2, h / 2, rows + 1)
    A, Z = np.meshgrid(a, z, indexing='ij')
    V = np.stack([r * np.cos(A), r * np.sin(A), Z], -1).reshape(-1, 3)
    i, j = np.meshgrid(np.arange(n), np.arange(rows), indexing='ij')
    p = i * (rows + 1) + j; q = ((i + 1) % n) * (rows + 1) + j
    F = np.concatenate([np.stack([p, q, q + 1], -1).reshape(-1, 3), np.stack([p, q + 1, p + 1], -1).reshape(-1, 3)])
    if capped:
        bot, top = len(V), len(V) + 1
        V = np.vstack([V, [[0, 0, -h / 2], [0, 0, h / 2]]])
        ib = np.arange(n) * (rows + 1); it = ib + rows
        F = np.concatenate([F, np.stack([np.full(n, bot), np.roll(ib, -1), ib], 1),
                            np.stack([np.full(n, top), it, np.roll(it, -1)], 1)])
    return Mesh(V + np.asarray(centre, float), F)


def grid(n=10, size=1.0, z=0.0):
    """an open square sheet in the xy plane, facing +z."""
    g = np.linspace(-size / 2, size / 2, n + 1)
    X, Y = np.meshgrid(g, g, indexing='ij')
    V = np.stack([X, Y, np.full_like(X, z)], -1).reshape(-1, 3)
    idx = np.arange((n + 1) ** 2).reshape(n + 1, n + 1)
    q = np.stack([idx[:-1, :-1], idx[1:, :-1], idx[1:, 1:], idx[:-1, 1:]], -1).reshape(-1, 4)
    return Mesh(V, np.concatenate([q[:, [0, 1, 2]], q[:, [0, 2, 3]]]))
