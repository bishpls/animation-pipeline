"""charkit/eyes.py's and charkit/mouth.py's authored-base keys on small meshes with known answers (venv: run this file,
or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import eyes as eyelib, mouth as mouthlib


class Flat:
    """a flat face at y = 0 (charkit.eyes.Face's interface)."""

    def points(self, x, z):
        return np.stack([np.asarray(x, float), np.zeros(np.size(x)), np.asarray(z, float)], 1)

    def y(self, x, z):
        return np.zeros(np.broadcast(np.asarray(x), np.asarray(z)).shape) if np.ndim(x) or np.ndim(z) else 0.0


def rings(n=16, radii=(0.1, 0.07, 0.04, 0.02)):
    """concentric loops (the rim first, the margin last), index-aligned along spokes, on the plane y = 0."""
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    V, loops = [], []
    for r in radii:
        loops.append(list(range(len(V), len(V) + n)))
        V += [(r * np.cos(t), 0.0, r * np.sin(t)) for t in a]
    return np.array(V), loops


def test_spokes_keep_the_rings_nested_when_the_lid_closes():
    V, loops = rings()
    eye = {'loops': loops}
    mar = loops[-1]
    # close the lid: every margin vertex onto z = 0, keeping its x
    moved = {m: np.array([0.0, 0.0, -V[m, 2]]) for m in mar}
    D = eyelib.spokes(V, eye, Flat(), moved)
    assert set(D) == set(loops[1]) | set(loops[2])                      # the rim and past it stay
    P = V.copy()
    for v, d in D.items():
        P[v] += d
    for m, d in moved.items():
        P[m] += d
    for i in range(len(mar)):                                            # along each spoke, the order is kept
        r = [np.linalg.norm(P[lp[i], [0, 2]]) for lp in loops]
        assert r[0] >= r[1] >= r[2] >= r[3] - 1e-12, r


def grid(n=7):
    """an n x n quad grid on the plane, spacing 1."""
    V = np.array([(i, 0.0, j) for j in range(n) for i in range(n)], float)
    F = [(j * n + i, j * n + i + 1, (j + 1) * n + i + 1, (j + 1) * n + i) for j in range(n - 1) for i in range(n - 1)]
    return V, F


def test_harmonic_reproduces_a_linear_field():
    V, F = grid()
    n = 7
    border = [v for v in range(len(V)) if V[v, 0] in (0, n - 1) or V[v, 2] in (0, n - 1)]
    free = [v for v in range(len(V)) if v not in border]
    field = lambda v: np.array([0.1 * V[v, 0], 0.0, -0.05 * V[v, 2]])
    D = mouthlib.harmonic(V, F, free, field)
    assert np.allclose(D, [field(v) for v in free], atol=1e-9)


def test_arc_params_give_a_steep_side_its_share():
    """a D-shaped lip as the kit draws its curves (x linear in t, the sides as z falling fast near the corners): spaced
    by x, the steep sides get a vertex or two; by arc length, their share of its length."""
    V = np.array([(x, 0.0, 0.0) for x in np.linspace(-1, 1, 21)])
    chain = list(range(21))

    def D(t):
        t = np.asarray(t, float)
        return -1 + 2 * t, -2 * (1 - np.abs(2 * t - 1) ** 16)
    steep = lambda x, z: int(((z < -0.2) & (z > -1.8)).sum())
    by_arc = steep(*D(mouthlib._arc_params(V, chain, D)))
    by_x = steep(*D(mouthlib._params(V, chain)))
    assert by_x <= 2 and by_arc >= 6, (by_x, by_arc)


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok', name)
