"""Deterministic numerics: the same bits on every machine, for code whose output feeds discrete decisions (a voxel in or
out, which view a vertex takes, which edge collapses next).

numpy dispatches its transcendental functions (exp, sin, cos, arccos, ...) and its reductions to per-CPU SIMD code
(AVX-512 on one Xeon, AVX2 on another, NEON on the Mac), BLAS picks per-CPU kernels, and C extensions built for arm64
fuse a multiply and an add into one rounding (FMA). Each is within an ulp or so, but at a threshold an ulp decides,
and a greedy decimation then takes a different path. The visual hull came out 3% different in its labels between the
two build boxes (2026-09-29). These helpers use only IEEE-exact elementwise arithmetic (+, -, *, /, sqrt: correctly
rounded everywhere, and numpy never fuses two ufuncs), in a fixed order, and snap anything that comes from libm to a
power-of-two grid far coarser than an ulp:

    cs(az)                  cos and sin of an angle in degrees: exact at multiples of 90, else libm snapped to 2^-40
    gaussian(x, sigma)      a separable Gaussian blur (scipy.ndimage.gaussian_filter's kernel and 'nearest' edges),
                            as a fixed sequence of elementwise multiply-adds with snapped weights
    snap(x, q)              x rounded to multiples of q (a power of two, so the result is exact)
    dot3(P, v)              rows of P dotted with a 3-vector, term by term (not BLAS)
    normals_area(V, F)      unit vertex normals, area weighted (no transcendental functions)
"""
import math

import numpy as np

TRIG_Q = 2.0 ** -40                 # libm's cos/sin differ by an ulp (1e-16) between glibc and Apple's: snapped this
                                    # coarsely, the same bits everywhere unless a value sits within an ulp of a step
KERNEL_Q = 2.0 ** -40               # Gaussian weights likewise
ANGLE_Q = 2.0 ** -30                # degrees: an angle measured from a drawing (the three-quarter view's), from libm's acos
DECIDE_Q = 2.0 ** -30               # a value compared with a threshold after a per-CPU function (np.power)


def snap(x, q):
    """x to the nearest multiple of q (half to even); q a power of two, so x / q and the product back are exact."""
    return np.round(np.asarray(x, float) / q) * q


def cs(az):
    """(cos, sin) of `az` degrees, the same on every machine."""
    a = float(az) % 360.0
    exact = {0.0: (1.0, 0.0), 90.0: (0.0, 1.0), 180.0: (-1.0, 0.0), 270.0: (0.0, -1.0)}
    if a in exact:
        return exact[a]
    r = math.radians(a)
    return float(snap(math.cos(r), TRIG_Q)), float(snap(math.sin(r), TRIG_Q))


def kernel(sigma, truncate=4.0):
    """scipy.ndimage's Gaussian kernel (radius int(truncate * sigma + 0.5), normalised), from libm's exp snapped and a
    correctly rounded sum (math.fsum) -> float64 (2r + 1,)."""
    r = int(truncate * float(sigma) + 0.5)
    w = [math.exp(-0.5 * (k / float(sigma)) ** 2) for k in range(-r, r + 1)]
    s = math.fsum(w)
    return np.array([float(snap(x / s, KERNEL_Q)) for x in w])


def gaussian(x, sigma, mode='nearest', dtype=np.float32):
    """a separable Gaussian blur of an N-d array (sigma a number or one per axis; 0 skips an axis), computed in `dtype`
    as elementwise multiply-adds in a fixed order -> dtype array. Only 'nearest' edges (scipy's default for the hull's
    uses). Within a float32 ulp of scipy.ndimage.gaussian_filter, and the same bits on every machine."""
    if mode != 'nearest':
        raise ValueError("det.gaussian: only mode='nearest'")
    x = np.asarray(x, dtype)
    sig = [float(sigma)] * x.ndim if np.ndim(sigma) == 0 else [float(s) for s in sigma]
    for ax, sg in enumerate(sig):
        if sg <= 0:
            continue
        w = kernel(sg).astype(dtype)
        r = len(w) // 2
        pad = [(0, 0)] * x.ndim
        pad[ax] = (r, r)
        xp = np.pad(x, pad, mode='edge')
        n = x.shape[ax]
        out = np.zeros_like(x)
        for k in range(len(w)):
            sl = [slice(None)] * x.ndim
            sl[ax] = slice(k, k + n)
            out += w[k] * xp[tuple(sl)]
        x = out
    return x


def dot3(P, v):
    """(N, 3) rows dotted with a 3-vector, in the order x, y, z -> (N,)."""
    P = np.asarray(P, float)
    return P[:, 0] * v[0] + P[:, 1] * v[1] + P[:, 2] * v[2]


def norm3(P):
    """(N, 3) rows' lengths, in the order x, y, z -> (N,)."""
    P = np.asarray(P, float)
    return np.sqrt(P[:, 0] * P[:, 0] + P[:, 1] * P[:, 1] + P[:, 2] * P[:, 2])


def normals_area(V, F):
    """unit vertex normals, the sum of the incident faces' (area-weighted) normals: cross products and sums in a fixed
    order, so no transcendental function and no reordering. -> (N, 3)."""
    V = np.asarray(V, float)
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    e1, e2 = b - a, c - a
    n = np.stack([e1[:, 1] * e2[:, 2] - e1[:, 2] * e2[:, 1],
                  e1[:, 2] * e2[:, 0] - e1[:, 0] * e2[:, 2],
                  e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]], 1)
    out = np.zeros_like(V)
    for k in range(3):
        np.add.at(out, F[:, k], n)
    return out / np.maximum(norm3(out), 1e-300)[:, None]
