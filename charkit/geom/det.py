"""Deterministic numerics: the same bits on every machine, for code whose output feeds discrete decisions (a voxel in or
out, which view a vertex takes, which edge collapses next).

numpy dispatches its transcendental functions (exp, sin, cos, arccos, ...) and its reductions to per-CPU SIMD code
(AVX-512 on one Xeon, AVX2 on another, NEON on the Mac), BLAS picks per-CPU kernels, and C extensions built for arm64
fuse a multiply and an add into one rounding (FMA). Each is within an ulp or so, but at a threshold an ulp decides,
and a greedy decimation then takes a different path. The visual hull came out 3% different in its labels between the
two build boxes (2026-09-29). These helpers use only IEEE-exact elementwise arithmetic (+, -, *, /, sqrt: correctly
rounded everywhere, and numpy never fuses two ufuncs), in a fixed order, and snap anything that comes from libm to a
power-of-two grid far coarser than an ulp:

    cs(az)                  cos and sin of an angle in degrees: numpy's values at multiples of 90 (QUADRANTS), else
                            libm's snapped to 2^-40
    gaussian(x, sigma)      a separable Gaussian blur (scipy.ndimage.gaussian_filter's kernel, order and edge modes),
                            as a fixed sequence of elementwise multiply-adds with snapped weights
    snap(x, q)              x rounded to multiples of q (a power of two, so the result is exact)
    dot3(P, v)              rows of P dotted with a 3-vector, term by term (not BLAS)
    normals_area(V, F)      unit vertex normals, area weighted (no transcendental functions)
    normals_angle(V, F)     unit vertex normals, angle weighted (mesh.vertex_normals' pseudo-normals), the corner angles
                            from arccos snapped to ANGLE_W_Q
    nearest(P, Q)           each query's nearest point, a tie going to the lowest index (not cKDTree's own order)
"""
import math

import numpy as np

TRIG_Q = 2.0 ** -40                 # libm's cos/sin differ by an ulp (1e-16) between glibc and Apple's: snapped this
                                    # coarsely, the same bits everywhere unless a value sits within an ulp of a step
KERNEL_Q = 2.0 ** -40               # Gaussian weights likewise
ANGLE_Q = 2.0 ** -30                # degrees: an angle measured from a drawing (the three-quarter view's), from libm's acos
DECIDE_Q = 2.0 ** -30               # a value compared with a threshold after a per-CPU function (np.power)
ANGLE_W_Q = 2.0 ** -30              # radians: corner angles weighting normals (np.arccos is per-CPU SIMD)


def snap(x, q):
    """x to the nearest multiple of q (half to even); q a power of two, so x / q and the product back are exact."""
    return np.round(np.asarray(x, float) / q) * q


# the quadrants' cos and sin as numpy gives them (np.cos(np.radians(90)) is 6.1e-17, not 0), the same literal bits on
# every machine: a sample on an exact half bin rounds by that residue's sign, so exact zeros shifted the hull's
# restored silhouette voxels at the head's top by half a voxel against every hull built before (2026-09-30)
QUADRANTS = {0.0: (1.0, 0.0), 90.0: (6.123233995736766e-17, 1.0), 180.0: (-1.0, 1.2246467991473532e-16),
             270.0: (-1.8369701987210297e-16, -1.0)}


def cs(az):
    """(cos, sin) of `az` degrees, the same on every machine."""
    a = float(az) % 360.0
    if a in QUADRANTS:
        return QUADRANTS[a]
    r = math.radians(a)
    return float(snap(math.cos(r), TRIG_Q)), float(snap(math.sin(r), TRIG_Q))


def kernel(sigma, truncate=4.0):
    """scipy.ndimage's Gaussian kernel (radius int(truncate * sigma + 0.5), normalised), from libm's exp snapped and a
    correctly rounded sum (math.fsum) -> float64 (2r + 1,)."""
    r = int(truncate * float(sigma) + 0.5)
    w = [math.exp(-0.5 * (k / float(sigma)) ** 2) for k in range(-r, r + 1)]
    s = math.fsum(w)
    return np.array([float(snap(x / s, KERNEL_Q)) for x in w])


PAD = {'reflect': 'symmetric', 'nearest': 'edge'}      # scipy.ndimage's edge modes as np.pad's


def gaussian(x, sigma, mode='reflect', dtype=np.float32):
    """a separable Gaussian blur of an N-d array (sigma a number or one per axis; 0 skips an axis), as
    scipy.ndimage.gaussian_filter computes it: per axis, the centre tap then each symmetric pair summed and weighted,
    accumulated in float64, the axis's result stored in `dtype` before the next -> dtype array. Edges as scipy's
    'reflect' (its default: d c b a | a b c d) or 'nearest' (a a a | a b c d).
    Elementwise IEEE operations in a fixed order and snapped weights, so the same bits on every machine; scipy's own
    sums (float64 too) differ only in the weights' last bits, so a threshold on the result falls where scipy's does
    (accumulated in float32, 5,502 voxels of the hull's smoothing changed sign, 2026-09-30)."""
    if mode not in PAD:
        raise ValueError("det.gaussian: mode 'reflect' or 'nearest'")
    x = np.asarray(x, dtype)
    sig = [float(sigma)] * x.ndim if np.ndim(sigma) == 0 else [float(s) for s in sigma]
    for ax, sg in enumerate(sig):
        if sg <= 0:
            continue
        w = kernel(sg)
        r = len(w) // 2
        pad = [(0, 0)] * x.ndim
        pad[ax] = (r, r)
        xp = np.pad(x, pad, mode=PAD[mode]).astype(np.float64)
        n = x.shape[ax]

        def tap(k):
            sl = [slice(None)] * x.ndim
            sl[ax] = slice(k, k + n)
            return xp[tuple(sl)]
        out = np.multiply(tap(r), w[r])
        pair = np.empty_like(out)
        for k in range(1, r + 1):
            np.add(tap(r - k), tap(r + k), out=pair)
            np.multiply(pair, w[r - k], out=pair)
            np.add(out, pair, out=out)
        x = out.astype(dtype)
    return x


def dot3(P, v):
    """(N, 3) rows dotted with a 3-vector, in the order x, y, z -> (N,)."""
    P = np.asarray(P, float)
    return P[:, 0] * v[0] + P[:, 1] * v[1] + P[:, 2] * v[2]


def norm3(P):
    """(N, 3) rows' lengths, in the order x, y, z -> (N,)."""
    P = np.asarray(P, float)
    return np.sqrt(P[:, 0] * P[:, 0] + P[:, 1] * P[:, 1] + P[:, 2] * P[:, 2])


def _cross(e1, e2):
    return np.stack([e1[:, 1] * e2[:, 2] - e1[:, 2] * e2[:, 1],
                     e1[:, 2] * e2[:, 0] - e1[:, 0] * e2[:, 2],
                     e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]], 1)


def normals_area(V, F):
    """unit vertex normals, the sum of the incident faces' (area-weighted) normals: cross products and sums in a fixed
    order, so no transcendental function and no reordering. -> (N, 3)."""
    V = np.asarray(V, float)
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    n = _cross(b - a, c - a)
    out = np.zeros_like(V)
    for k in range(3):
        np.add.at(out, F[:, k], n)
    return out / np.maximum(norm3(out), 1e-300)[:, None]


def normals_angle(V, F):
    """unit vertex normals weighted by each face's corner angle (mesh.vertex_normals' default, the pseudo-normal): the
    same arithmetic in a fixed order, the angles from np.arccos snapped to ANGLE_W_Q. -> (N, 3)."""
    V = np.asarray(V, float)
    n = _cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    nf = n / np.maximum(norm3(n), 1e-300)[:, None]
    out = np.zeros_like(V)
    for k in range(3):
        a = V[F[:, (k + 1) % 3]] - V[F[:, k]]
        b = V[F[:, (k + 2) % 3]] - V[F[:, k]]
        c = (a[:, 0] * b[:, 0] + a[:, 1] * b[:, 1] + a[:, 2] * b[:, 2]) / np.maximum(norm3(a) * norm3(b), 1e-300)
        w = snap(np.arccos(np.clip(c, -1, 1)), ANGLE_W_Q)
        np.add.at(out, F[:, k], nf * w[:, None])
    return out / np.maximum(norm3(out), 1e-300)[:, None]


def nearest(P, Q, k=8):
    """the index into P of each Q's nearest point, the same on every machine. cKDTree finds k candidates, but among
    equidistant points it answers in its tree's order, and the tree is built with the C++ library's nth_element
    (libstdc++ on Linux, libc++ on macOS): on a voxel lattice, where ties are everywhere, the two machines picked
    different neighbours. Here the candidates' squared distances are recomputed termwise and a tie goes to the lowest
    index. Where the k-th candidate still ties the nearest (the tie may go on past k), k doubles. -> int (M,)."""
    from scipy.spatial import cKDTree
    P = np.asarray(P, float)
    Q = np.asarray(Q, float)
    tree = cKDTree(P)
    out = np.empty(len(Q), np.int64)
    todo = np.arange(len(Q))
    kk = min(k, len(P))
    while len(todo):
        _, j = tree.query(Q[todo], k=kk)
        j = np.asarray(j).reshape(len(todo), kk)
        q = Q[todo]
        D = np.zeros(j.shape)
        for a in range(P.shape[1]):
            d = q[:, a, None] - P[j, a]
            D = D + d * d
        o = np.lexsort((j, D), axis=-1)
        rows = np.arange(len(todo))
        out[todo] = j[rows, o[:, 0]]
        more = (D[rows, o[:, -1]] == D[rows, o[:, 0]]) & (kk < len(P))
        todo = todo[more]
        kk = min(kk * 2, len(P))
    return out
