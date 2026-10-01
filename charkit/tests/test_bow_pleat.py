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
