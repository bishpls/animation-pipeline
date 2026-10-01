"""The pleated bow's template (charkit.garments._bow_mesh's `pleat`, tool/pieceref): the lines the design draws inside
the bow only show if the geometry gives the outline shells a silhouette there (inverted hulls draw silhouettes only).
The crease is the panel's lower edge standing in front of the strip below it, inside the lobe's silhouette; the upper
almond stands proud of the panel; the outer end leans out at its top under `shear`."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import garments as g

SZ = 0.19
DEPTH = 0.06 * SZ
P = {'knot': 0.08, 'top': 0.24, 'bottom': 0.30, 'sag': 0.06, 'pinch': 0.6, 'step': 1.0, 'thin': 0.3,
     'crease': [0.27, 0.0], 'crease_p': 2, 'top_p': 0.6, 'bottom_p': 0.7,
     'almond': {'u': [0.06, 0.5], 'f': [0.54, 0.60], 'h': 0.025, 'd': 0.012, 'gap': 0.004}}


def band(kind, **kw):
    vs, us, fs = g._pleat_band(dict(P, **kw), kind, 1, SZ, DEPTH, 24)
    return np.array(vs), np.array(us)


def at(V, U, u, tol=0.02):
    return V[np.abs(U[:, 1] - u) < tol]


def test_the_strip_shows_below_the_crease_mid_lobe_and_sits_behind_the_panel():
    Vp, Up = band('panel')
    Vs, Us = band('strip')
    for u in (0.25, 0.5):
        p, s = at(Vp, Up, u), at(Vs, Us, u)
        assert s[:, 2].min() < p[:, 2].min() - 0.02 * SZ          # the lower layer shows below the panel's lower edge
        assert s[:, 1].min() > p[:, 1].min() + 0.5 * DEPTH         # ... behind the panel's front (its edge a silhouette)


def test_the_almond_stands_proud_of_the_panel_in_the_lobes_upper_half():
    Vp, Up = band('panel')
    Vs, Us = band('strip')
    Va, Ua = band('almond')
    a = at(Va, Ua, 0.28, 0.03)
    p, s = at(Vp, Up, 0.28, 0.03), at(Vs, Us, 0.28, 0.03)
    zc = a[:, 2].mean()
    front = p[np.abs(p[:, 2] - zc) < 0.03 * SZ][:, 1].min()
    assert a[:, 1].max() < front                                     # wholly in front of the panel there
    assert zc > 0.5 * (s[:, 2].min() + p[:, 2].max())               # in the lobe's upper half


def test_shear_leans_the_outer_end_out_at_its_top():
    V0, U0 = band('panel')
    V1, U1 = band('panel', shear=0.3)
    end0, end1 = V0[U0[:, 1] > 0.95], V1[U1[:, 1] > 0.95]
    top = lambda E: E[E[:, 2] > np.percentile(E[:, 2], 80)][:, 0].mean()
    low = lambda E: E[E[:, 2] < np.percentile(E[:, 2], 20)][:, 0].mean()
    assert top(end1) > top(end0) and low(end1) < low(end0)
    assert np.allclose(V0[U0[:, 1] < 0.4], V1[U1[:, 1] < 0.4])      # the knot's end untouched


def test_the_pleated_bow_splits_into_its_named_parts():
    from charkit import partqa
    G = g._bow_mesh(np.zeros(3), SZ, 0.65, 0.25, depth=DEPTH, pleat=P, knot_box=[0.10, 0.09, 0.145, 0.02])
    V = np.asarray(G['verts'])
    T = np.array([(f[0], f[k], f[k + 1]) for f in G['faces'] for k in range(1, len(f) - 1)])
    codes = partqa.split(V, T)
    got = {c: int((codes == c).sum()) for c in np.unique(codes)}
    assert set(got) == set(partqa.CODES.values())                  # knot, both lobes (with their strips and almonds), tails
    kx = V[np.unique(T[codes == partqa.CODES['knot']])][:, 0]
    assert abs(kx.mean()) < 0.01 * SZ


def test_strip_ov_raises_the_strips_top_behind_the_panel_and_leaves_the_panel():
    Vp0, Up0 = band('panel', strip_ov=0.07)
    Vp1, Up1 = band('panel')
    assert np.allclose(Vp0, Vp1)                                      # the panel's edge (the crease's line) kept
    Vs0, Us0 = band('strip')
    Vs1, Us1 = band('strip', strip_ov=0.07)
    for u in (0.2, 0.5):
        assert at(Vs1, Us1, u, 0.04)[:, 2].max() > at(Vs0, Us0, u, 0.04)[:, 2].max() + 0.04 * SZ


def test_tuck_brings_the_strips_lower_half_forward_by_the_knot_only():
    Vs0, Us0 = band('strip')
    Vs1, Us1 = band('strip', tuck=[0.04, 0.3])
    near0, near1 = at(Vs0, Us0, 0.1), at(Vs1, Us1, 0.1)
    low = lambda S: S[S[:, 2] < np.percentile(S[:, 2], 25)][:, 1].mean()
    top = lambda S: S[S[:, 2] > np.percentile(S[:, 2], 90)][:, 1].mean()
    assert low(near1) < low(near0) - 0.02 * SZ                        # forward (-y) low down by the knot
    assert abs(top(near1) - top(near0)) < 0.005 * SZ                  # its top stays behind the panel
    assert np.allclose(at(Vs0, Us0, 0.85, 0.01), at(Vs1, Us1, 0.85, 0.01), atol=1e-3 * SZ)   # the outer end untouched


def test_the_tails_root_reaches_up_into_the_knot_and_changes_nothing_else():
    kw = dict(depth=DEPTH, pleat=P, knot_box=[0.10, 0.09, 0.145, 0.02])
    rb = {'w': [0.204, 0.338], 'turn': 20, 'hinge': 1.0}
    G0 = g._bow_mesh(np.zeros(3), SZ, 0.65, 0.25, ribbon=rb, **kw)
    G1 = g._bow_mesh(np.zeros(3), SZ, 0.65, 0.25, ribbon=dict(rb, root=0.08), **kw)
    assert G0.get('root_v') is None and len(G1['root_v']) == 24      # two rows of six per tail
    V1, K = np.asarray(G1['verts']), np.asarray(G1['verts'])[G1['knot_v']]
    rz = V1[G1['root_v'], 2]
    assert rz.min() > K[:, 2].min() and rz.max() < K[:, 2].max()      # the root rows inside the knot's height
    keep = np.setdiff1d(np.arange(len(V1)), G1['root_v'])
    assert np.allclose(np.asarray(G0['verts']), V1[keep])            # every other vertex where it was
