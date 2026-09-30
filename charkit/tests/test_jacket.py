"""charkit.garments' jacket over the band on small stand-ins (garments2): a shell's open front cut clean (its edge
vertices on the opening's line, not the body's staircase), the bib inside the opening with a margin under the jacket,
the hem hung over the band (below its top edge, outside its face) with the fronts lower where `hang` says, and a flare
standing the hem off the band (venv: run this file, or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import garments as gm
from charkit.geom import loft

L = 1.0


def torso(n=24, rows=20, r=0.3, z0=-1.6, z1=-0.8):
    """a cylinder of quads round the z axis (the eye line at z 0), front toward -y; chest's head at y 0."""
    V, F = [], []
    for i in range(rows):
        z = z1 + (z0 - z1) * i / (rows - 1)
        for k in range(n):
            a = 2 * np.pi * k / n
            V.append((r * np.sin(a), -r * np.cos(a), z))
    for i in range(rows - 1):
        for k in range(n):
            k2 = (k + 1) % n
            F.append((i * n + k, i * n + k2, (i + 1) * n + k2, (i + 1) * n + k))
    J = {'spine03____head': [0, 0, -1.2], 'spine01____head': [0, 0, -0.9]}
    return dict(head=dict(L=L, centre=np.array([0, 0, 0.0]), eye_knobs=dict(z=0.0)), joints=J, verts=np.array(V),
                faces=F)


def band(top=-1.3, bottom=-1.5, r=0.32):
    """belt_hull's result for an upright band round the z axis: its axis from z 0 down, rows ts, a constant radius."""
    ax = loft.Axis((0, 0, 0.0), (0, 0, -1), (0, -1, 0))
    ts = np.linspace(-top, -bottom, 5)
    th = np.linspace(-np.pi, np.pi, 36, endpoint=False)
    return {}, dict(axis=ax, ts=ts, th=th, R=np.full((len(ts), len(th)), r))


def cut_shell(A, cuts):
    """the faces all of whose vertices every cut keeps, and their vertices snapped onto the cuts."""
    V, F = A['verts'], A['faces']
    ins = np.ones(len(V), bool)
    for g in cuts:
        ins &= g(V) >= 0
    keep = [i for i, f in enumerate(F) if all(ins[v] for v in f)]
    used = sorted({v for i in keep for v in F[i]})
    sv = gm.snap_cuts(V, F, used, keep, V[used].copy(), cuts, ins)
    remap = {o: n for n, o in enumerate(used)}
    return sv, [tuple(remap[v] for v in F[i]) for i in keep], used


def border(faces):
    """the vertices on a face set's open border (edges used once)."""
    from collections import Counter
    e = Counter(tuple(sorted(p)) for f in faces for p in zip(f, list(f[1:]) + [f[0]]))
    return sorted({v for k, c in e.items() if c == 1 for v in k})


OPEN = dict(half=[[-0.9, 0.08], [-1.1, 0.15], [-1.6, 0.15]])


def test_the_opening_is_cut_clean_on_its_line():
    A = torso()
    g = gm.opening_cut(A, OPEN)
    sv, F, used = cut_shell(A, [g])
    front = [v for v in border(F) if sv[v, 1] < -0.05]
    X = sv[front]
    half = np.interp(X[:, 2], [-1.6, -1.1, -0.9], [0.15, 0.15, 0.08])
    edge = np.abs(np.abs(X[:, 0]) - half) < 3e-3
    assert edge.sum() >= 20                                    # the two edges, snapped onto |x| = half
    ends = np.isclose(X[:, 2], -0.8) | np.isclose(X[:, 2], -1.6)
    assert (edge | ends).all()                                 # the rest are the cylinder's own ends
    # nothing kept inside the opening on the front, the back untouched
    C = np.array([sv[list(f)].mean(0) for f in F])
    fr = C[:, 1] < -0.05
    assert (np.abs(C[fr, 0]) >= np.interp(C[fr, 2], [-1.6, -1.1, -0.9], [0.15, 0.15, 0.08]) - 1e-9).all()
    assert (C[:, 1] > 0.25).sum() > 0


def test_the_bib_fills_the_opening_with_a_margin():
    A = torso()
    g = gm.opening_cut(A, OPEN)
    m = 0.04
    sv, F, used = cut_shell(A, [lambda X: m - g(X)])
    X = sv[border(F)]
    X = X[(X[:, 2] < -0.85) & (X[:, 2] > -1.55)]
    half = np.interp(X[:, 2], [-1.6, -1.1, -0.9], [0.15, 0.15, 0.08])
    assert np.allclose(np.abs(X[:, 0]), half + m, atol=3e-3)    # its edges m past the jacket's, under it
    assert (sv[:, 1] < 0).all()                                 # only the front


def test_the_hem_hangs_over_the_band_and_the_fronts_lower():
    A = torso()
    bd = band()
    ez = dict(mode='over', gap=0.02, over=0.2, hang=[[0, 0.06], [90, 0.03], [180, 0.03]])
    hz = gm.hem_over_band(A, ez, bd)
    sv, F, used = cut_shell(A, [lambda X: X[:, 2] - hz(X)])
    sv = gm.ease_over_band(A, sv, ez, bd)
    hem = sv[border(F)]
    hem = hem[hem[:, 2] < -1.0]
    front, back = hem[(hem[:, 1] < 0) & (np.abs(hem[:, 0]) < 0.01)], hem[hem[:, 1] > 0.28]
    assert len(front) and np.allclose(front[:, 2], -1.36, atol=0.002)          # the band's top less 0.06 at the front
    assert np.allclose(back[:, 2], -1.33, atol=0.005)           # and 0.03 behind
    r = np.hypot(sv[:, 0], sv[:, 1])
    under = sv[:, 2] <= -1.3 + 1e-9
    assert np.allclose(r[under], 0.34, atol=1e-6)               # hung straight at the band's face plus the gap
    above = sv[:, 2] > -1.1 + 1e-9
    assert np.allclose(r[above], 0.3, atol=1e-6)                # untouched above the ease


def test_a_flare_stands_the_hem_off_the_band():
    A = torso()
    bd = band()
    ez = dict(mode='over', gap=0.02, over=0.2, hang=0.03, flare=[[0, 0.33], [90, 0.4], [180, 0.36]])
    sv = gm.ease_over_band(A, A['verts'].copy(), ez, bd)
    t, th, r = bd[1]['axis'].coords(sv)
    low = sv[:, 2] < -1.35
    side = low & (np.abs(np.abs(np.degrees(th)) - 90) < 1)
    front = low & (np.abs(np.degrees(th)) < 1)
    assert np.allclose(r[side], 0.4, atol=1e-6) and np.allclose(r[front], 0.34, atol=1e-6)  # the band's face wins in front
    mid = (sv[:, 2] < -1.15) & (sv[:, 2] > -1.25)
    assert ((r[mid] > 0.3 - 1e-9) & (r[mid] < 0.4 + 1e-9)).all()     # eased out, only ever outward


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f()
            print('ok', k)
