"""charkit.garments' puff sleeve template and the waistband's rows on small stand-ins: the puff closed at a round cap,
widest where its knots say, its lower rim inside its band; the right sleeve the left's mirror image; the band upright
at the drawn rows with the section of its fit rows (venv: run this file, or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import garments as gm

L = 1.0


def assembly():
    """two arms, mirror images about x = 0, hanging down and out; a few skin vertices on each upper arm."""
    J = {}
    for S, sx in (('L', 1), ('R', -1)):
        J['shoulder01.%s____head' % S] = [sx * 0.55, 0.1, 4.3]
        J['lowerarm01.%s____head' % S] = [sx * 0.75, 0.1, 3.8]
    V, W = [], {'leftUpperArm': [], 'rightUpperArm': []}
    for S, sx, b in (('L', 1, 'leftUpperArm'), ('R', -1, 'rightUpperArm')):
        h, e = np.array(J['shoulder01.%s____head' % S]), np.array(J['lowerarm01.%s____head' % S])
        d = (e - h) / np.linalg.norm(e - h)
        for t in np.linspace(0, 0.5, 11):
            for a in np.linspace(0, 2 * np.pi, 12, endpoint=False):
                u = np.cross(d, [0, 1.0, 0]); u /= np.linalg.norm(u); w = np.cross(d, u)
                V.append(h + d * t + 0.12 * (np.cos(a) * u + np.sin(a) * w))
                for k in W:
                    W[k].append(1.0 if k == b else 0.0)
    return dict(head=dict(L=L, centre=np.array([0, 0, 5.0]), eye_knobs=dict(z=0.0)), joints=J, verts=np.array(V),
                weights={k: np.array(v) for k, v in W.items()}, faces=[])


PROFILE = [[-0.25, 0.14, 0.19, 0.11, 0.19], [-0.1, 0.22, 0.23, 0.15, 0.23], [0.0, 0.26, 0.27, 0.22, 0.27],
           [0.1, 0.26, 0.23, 0.23, 0.22], [0.15, 0.24, 0.2, 0.21, 0.19]]
PUFF_L = dict(kind='sleeve', name='sleeve_L', side='left', source='template', profile=PROFILE, cap=0.12, cols=32,
              step=0.02, gathers=[12, 0.04, 0.1, 0.06], lobes=[6, 0.03])
PUFF_R = dict(kind='sleeve', name='sleeve_R', side='right', source='template', mirror='sleeve_L')


def test_the_cap_is_a_closed_round_dome():
    A = assembly()
    G = gm.puff(A, PUFF_L)
    V = np.asarray(G['verts'])
    h, d, o, f = gm.puff_frame(A, 'left')
    apex = h + d * (PROFILE[0][0] - 0.12)
    assert np.allclose(V[0], apex)                                     # the fan's centre: the apex on the axis
    fan = [f_ for f_ in G['faces'] if len(f_) == 3]
    assert len(fan) == 32 and all(0 in f_ for f_ in fan)                # closed over the top
    # round: a quarter ellipse, so just under the apex the section is wide (no point: a knot at zero would be one)
    E = gm.puff_extents(PUFF_L, np.array([PROFILE[0][0] - 0.12 * 0.8]))
    assert (E[0] > 0.55 * np.array(PROFILE[0][1:])).all()


def test_the_widest_where_the_knots_say_and_the_faces_face_out():
    A = assembly()
    G = gm.puff(A, dict(PUFF_L, gathers=None, lobes=None))
    V = np.asarray(G['verts'])
    h, d, o, f = gm.puff_frame(A, 'left')
    q = V - h
    t, x = q @ d, q @ o
    k = np.abs(t - 0.0) < 0.011
    assert abs(x[k].max() - 0.26) < 0.01                              # out, at t 0
    F = [f_ for f_ in G['faces'] if len(f_) == 4]
    c = np.array([V[list(f_)].mean(0) for f_ in F])
    n = np.array([np.cross(V[f_[1]] - V[f_[0]], V[f_[2]] - V[f_[0]]) for f_ in F])
    rad = (c - h) - np.outer((c - h) @ d, d)
    assert ((n * rad).sum(1) > 0).mean() > 0.95


def test_the_right_sleeve_is_the_lefts_mirror_image():
    A = assembly()
    whole = dict(garments=[PUFF_L, PUFF_R])
    GL = gm.puff(A, dict(PUFF_L, _spec=whole))
    GR = gm.puff(A, dict(PUFF_R, _spec=whole))
    VL, VR = np.asarray(GL['verts']), np.asarray(GR['verts'])
    M = VL.copy()
    M[:, 0] = -M[:, 0]
    # the same point set (the columns run the other way round a mirrored frame)
    d = np.sqrt(((M[:, None, :] - VR[None, :, :]) ** 2).sum(-1)).min(1)
    assert d.max() < 1e-6
    assert set(GR['weights']) == {'rightUpperArm'}


def test_the_lower_rim_hides_inside_its_band():
    A = assembly()
    band = dict(kind='band', name='cuff_L', bone='leftUpperArm', t=0.5, width=0.1, offset=0.0, thick=0.02)
    whole = dict(garments=[dict(PUFF_L, band='cuff_L'), band])
    Gb = gm.band(A, band)
    G = gm.puff(A, dict(PUFF_L, band='cuff_L', _spec=whole), hull={})
    h, d, o, f = gm.puff_frame(A, 'left')
    Vb = np.asarray(Gb['verts']) - h
    tb, rb = Vb @ d, np.hypot(Vb @ o, Vb @ f)
    V = np.asarray(G['verts']) - h
    t, r = V @ d, np.hypot(V @ o, V @ f)
    below = t > tb.min() + 0.012                                       # past the band's top: inside it
    assert below.any()
    assert r[below].max() < rb.max() - 0.02 + 1e-6                     # inside its inner surface (its thickness)
    assert t.max() <= tb.min() + 0.03 + 1e-9                          # `tuck` under its top


def test_the_band_stands_at_its_rows_with_its_fit_rows_section():
    """a hull band whose upper rows flare out (the top's hem over it): with `rows` and `fit_rows` it spans the drawn
    rows, upright at the radius of the rows below the flare."""
    rng = np.random.default_rng(0)
    A = dict(head=dict(L=1.0, centre=np.array([0.0, 0.0, 0.0]), eye_knobs=dict(z=0.0)), verts=np.zeros((1, 3)),
             weights={'hips': np.ones(1)}, faces=[])
    P = []
    for z in np.linspace(-1.50, -1.26, 25):
        rad = 0.30 if z < -1.38 else 0.40
        for a in rng.uniform(-np.pi, np.pi, 80):
            P.append([rad * np.sin(a), -rad * np.cos(a), z])
    hull = dict(waistband=np.array(P))
    s = dict(kind='belt', name='waistband', source='hull', straight=True, rows=[-1.33, -1.50], fit_rows=[-1.40, -1.48],
             thick=0.025, offset=0.0, round=0.0)
    G = gm.belt_hull(A, s, hull)
    V = np.asarray(G['verts'])
    assert abs(V[:, 2].max() + 1.33) < 1e-6 and abs(V[:, 2].min() + 1.50) < 1e-6
    r = np.hypot(V[:, 0], V[:, 1])
    assert np.abs(r - 0.30).max() < 0.02                              # upright at the lower rows' radius
    G0 = gm.belt_hull(A, dict(s, rows=None, fit_rows=None), hull)     # without: the hull's span and flare
    assert np.hypot(G0['verts'][:, 0], G0['verts'][:, 1]).max() > 0.33


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok', name)
