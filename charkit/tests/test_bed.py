"""A shell bedded under a piece lying on it (charkit.garments.bed_under, tool/garments4): where the piece covers the
shell in the front projection, the shell goes `gap` behind the piece's back (so the piece's lower outline draws over
it: bow_front_bleed); within `margin` of the piece's outline too, easing back over `ease`; never forward; nothing far
from the piece moves. And the evaluator's piece cache keys a garment on the garments it reads (bodyeval.garment_deps)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import garments as g

L = 1.0


def grid(x0, x1, z0, z1, y, n):
    xs, zs = np.linspace(x0, x1, n), np.linspace(z0, z1, n)
    X, Z = np.meshgrid(xs, zs, indexing='ij')
    V = np.c_[X.ravel(), np.full(X.size, y), Z.ravel()]
    F = [(i * n + j, i * n + j + 1, (i + 1) * n + j + 1, (i + 1) * n + j) for i in range(n - 1) for j in range(n - 1)]
    return V, F


def plate():
    """a piece 0.2 wide whose back sits 0.02 behind the shell (y 0): buried."""
    Vf, Ff = grid(-0.1, 0.1, -0.1, 0.1, -0.01, 9)
    Vb, Fb = grid(-0.1, 0.1, -0.1, 0.1, 0.02, 9)
    return np.r_[Vf, Vb], Ff + [tuple(i + len(Vf) for i in f) for f in Fb]


B = dict(gap=0.01, margin=0.02, ease=0.04, cell=0.005, smooth=3)


def test_the_shell_goes_behind_the_piece_where_it_covers_it_and_eases_back():
    S, SF = grid(-0.4, 0.4, -0.4, 0.4, 0.0, 81)
    P, PF = plate()
    out = g.bed_under(S, SF, P, PF, L, B)
    dy = out[:, 1] - S[:, 1]
    under = (np.abs(S[:, 0]) < 0.09) & (np.abs(S[:, 2]) < 0.09)
    assert (out[under, 1] >= 0.02 + 0.01 - 1e-9).all()             # gap behind the piece's back
    rim = (np.abs(S[:, 0]) < 0.115) & (np.abs(S[:, 2]) < 0.115) & ~under
    assert (out[rim, 1] >= 0.02).all()                              # the outline's band held back too
    far = (np.abs(S[:, 0]) > 0.25) | (np.abs(S[:, 2]) > 0.25)
    assert np.allclose(dy[far], 0.0)                                # nothing far away moves
    assert (dy >= -1e-12).all()                                     # never forward
    mid = (np.abs(S[:, 2]) < 0.01) & (S[:, 0] > 0.1) & (S[:, 0] < 0.2)
    xs = S[mid, 0]
    assert np.all(np.diff(dy[mid][np.argsort(xs)]) <= 1e-9)         # eases back out monotonically


def test_a_piece_in_front_leaves_the_shell_alone():
    S, SF = grid(-0.4, 0.4, -0.4, 0.4, 0.0, 41)
    P, PF = plate()
    P = P.copy()
    P[:, 1] -= 0.05                                                 # its back now 0.03 in front of the shell
    out = g.bed_under(S, SF, P, PF, L, B)
    assert np.allclose(out, S)


def test_a_garment_is_cached_on_the_garments_it_reads():
    from charkit import bodyeval
    spec = {'garments': [
        {'name': 'sleeve_L', 'kind': 'sleeve', 'band': 'cuff_L', 'cap': 0.12},
        {'name': 'sleeve_R', 'kind': 'sleeve', 'mirror': 'sleeve_L', 'band': 'cuff_R'},
        {'name': 'cuff_L', 'kind': 'band'}, {'name': 'cuff_R', 'kind': 'band'},
        {'name': 'top', 'kind': 'shell', 'bed': {'gap': 0.01}}, {'name': 'bow', 'kind': 'bow'}]}
    G = {s['name']: s for s in spec['garments']}
    names = lambda s: [d['name'] for d in bodyeval.garment_deps(s, spec)]
    assert names(G['sleeve_R']) == ['cuff_L', 'cuff_R', 'sleeve_L']
    assert names(G['top']) == ['bow']
    k0 = bodyeval._h(bodyeval.garment_deps(G['sleeve_R'], spec))
    spec['garments'][0]['cap'] = 0.18
    assert bodyeval._h(bodyeval.garment_deps(G['sleeve_R'], spec)) != k0


def test_shoulder_pad_raises_the_upward_faces_by_the_table():
    # a flat-topped box: its top raised by the table's dz at each |x| (0 outside the table), its sides not at all
    from charkit import garments
    L = 1.0
    A = {'head': {'L': L}}
    xs = np.linspace(-1, 1, 21)
    V, F = [], []
    for z in (0.0, 1.0):
        for x in xs:
            V.append((x, 0.0, z))
    n = len(xs)
    for i in range(n - 1):                      # the side wall (a strip facing -y) and the top (facing +z)
        F.append((i, i + 1, n + i + 1, n + i))
    top = [(x, y, 1.0) for y in (0.0, 1.0) for x in xs]
    V += top
    m = len(V) - 2 * n
    for i in range(n - 1):
        F.append((2 * n + i, 2 * n + i + 1, 2 * n + n + i + 1, 2 * n + n + i))
    V = np.array(V, float)
    out = garments.shoulder_pad(A, V, F, dict(lift=[[0.3, 0.1], [0.5, 0.1]], nz=(0.2, 0.7), smooth=0))
    d = out[:, 2] - V[:, 2]
    k = np.arange(2 * n, len(V))
    ax_ = np.abs(V[k, 0])
    assert np.allclose(d[k][(ax_ >= 0.3) & (ax_ <= 0.5)], 0.1) and np.allclose(d[k][ax_ > 0.55], 0.0)
    assert np.allclose(d[:n], 0.0)              # the wall's bottom row faces sideways: not raised
