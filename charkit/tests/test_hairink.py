"""The hair's line layer (charkit.geom.hairink, tool/hairstrokes): a stroke drawn in a view lands on the piece the view
sees there, as a tapered ribbon on the piece's surface, appended on an ink slot with no outline; a view that sees the
stroke squarely and draws nothing near it vetoes it; the drawn strokes are read without the lock lines and specks; the
declared strokes family's density reads the same strokes as 0 and none as 1."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit.geom import hairink as hi


def sphere(r=0.1, n=24, m=48, c=(0.0, 0.0, 0.0)):
    th = np.linspace(0.05, np.pi - 0.05, n)
    ph = np.linspace(0, 2 * np.pi, m, endpoint=False)
    T_, P_ = np.meshgrid(th, ph, indexing='ij')
    V = np.c_[(r * np.sin(T_) * np.cos(P_)).ravel(), (r * np.sin(T_) * np.sin(P_)).ravel(), (r * np.cos(T_)).ravel()]
    V += np.asarray(c, float)
    F = []
    for i in range(n - 1):
        for j in range(m):
            a, b, c_, d = i * m + j, i * m + (j + 1) % m, (i + 1) * m + (j + 1) % m, (i + 1) * m + j
            F += [(a, d, c_), (a, c_, b)]
    F = np.array(F)
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    flip = (fn * (V[F].mean(1) - np.asarray(c))).sum(1) < 0
    F[flip] = F[flip][:, [0, 2, 1]]
    N = (V - np.asarray(c)) / r
    return dict(family='bangs', V=V, T=F, vn_shade=N, lock=np.arange(len(V)) // 100, strand=np.zeros((len(V), 3)))


FR = {'front': dict(az=0.0, origin=(0.0, 0.0), L=0.25, ppl=200.0),
      'back': dict(az=180.0, origin=(0.0, 0.0), L=0.25, ppl=200.0)}


def test_a_front_stroke_lands_on_the_front_of_the_piece_as_a_tapered_ribbon():
    P = {'bangs': sphere()}
    S = {'front': [np.c_[np.zeros(9), np.linspace(-0.2, 0.2, 9)]]}           # (u, z) L: a vertical stroke at the middle
    K, rep = hi.place(P, S, {'front': FR['front']}, 0.25, dict(width=0.004, lift=0.0, min_run=0.01))
    k = K['bangs']
    assert len(k['faces']) > 10
    X = k['verts']
    assert (X[:, 1] < -0.08).all()                                          # on the near side (the camera on -y)
    assert np.abs(np.linalg.norm(X, axis=1) - 0.1).max() < 0.002           # on the surface
    w = np.linalg.norm(X[0::2] - X[1::2], axis=1)
    assert w.max() <= 0.004 * 0.25 + 1e-9 and w[0] < 0.5 * w.max()          # 0.004 L wide, narrowing at its ends


def test_apply_appends_ink_faces_with_no_outline():
    R = dict(pieces={'bangs': sphere()})
    nv, nt = len(R['pieces']['bangs']['V']), len(R['pieces']['bangs']['T'])
    K, _ = hi.place(R['pieces'], {'front': [np.c_[np.zeros(9), np.linspace(-0.2, 0.2, 9)]]}, {'front': FR['front']},
                    0.25, dict(min_run=0.01))
    hi.apply(R, K)
    p = R['pieces']['bangs']
    m = len(K['bangs']['verts'])
    assert len(p['V']) == nv + m and len(p['vn_shade']) == nv + m and len(p['lock']) == nv + m
    assert p['ink'].sum() == len(K['bangs']['faces']) and not p['ink'][:nt].any()
    assert (p['outline_w'][:nv] == 1).all() and (p['outline_w'][nv:] == 0).all()


def test_a_view_that_sees_the_stroke_squarely_and_draws_nothing_there_vetoes_it():
    P = {'bangs': sphere()}
    # a stroke drawn in front on the side of the ball (u 0.3 L): the profile (from +x) sees that squarely
    S = {'front': [np.c_[np.full(9, 0.3), np.linspace(-0.1, 0.1, 9)]]}
    side = dict(az=90.0, origin=(0.0, 0.0), L=0.25, ppl=200.0)
    F = {'front': FR['front'], 'profile': side}
    shape = (int(round(7.5 * 200)), int(round(4.6 * 200)))
    empty = {'profile': np.full(shape, 1.0)}                                 # the profile draws nothing anywhere
    drawn = {'profile': np.zeros(shape)}                                     # ... or a line everywhere
    o = dict(min_run=0.01, min_face=0.0, margin=2.0, veto=('profile',), veto_face={'profile': 0.3})
    K1, _ = hi.place(P, S, F, 0.25, o, near=empty)
    K2, _ = hi.place(P, S, F, 0.25, o, near=drawn)
    assert 'bangs' not in K1 and 'bangs' in K2


def test_drawn_strokes_leave_out_lock_lines_and_specks():
    lines = np.zeros((60, 60), bool)
    lines[5:55, 20] = True                                                   # a stroke on a lock boundary
    lines[5:55, 40] = True                                                   # a stroke inside a lock
    lines[30, 50:52] = True                                                  # a speck
    lock = np.zeros((60, 60), int)
    lock[:, :20] = 1
    lock[:, 20:] = 2
    sk = hi.drawn_strokes(lines, np.ones((60, 60), bool), 100.0, lock, 'strand', wall=0.02, min_len=0.05)
    assert not sk[:, 18:23].any() and sk[:, 40].sum() >= 45 and not sk[30, 50:52].any()
    sk_all = hi.drawn_strokes(lines, np.ones((60, 60), bool), 100.0, lock, 'all', wall=0.02, min_len=0.05)
    assert sk_all[:, 20].sum() >= 45


def test_the_density_measure_reads_the_same_strokes_0_and_none_1():
    from charkit import declared
    want = np.zeros((80, 80), bool)
    want[10:70, 30] = True
    keep = np.ones((80, 80), bool)
    g = lambda m: __import__('scipy').ndimage.gaussian_filter(m.astype(float), 3.0) * keep
    same = np.abs(g(want) - g(want)).sum() / (g(want) + g(want)).sum()
    none = np.abs(g(np.zeros_like(want)) - g(want)).sum() / (g(want)).sum()
    assert same == 0 and abs(none - 1) < 1e-9
    th = declared.orientation(want)
    assert abs(np.degrees(th[40, 30]) - 90) < 5                              # a vertical stroke runs at 90 degrees


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f()
    print('ok')
