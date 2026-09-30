"""charkit.sim: the XPBD cloth solver on problems with known answers: its gradients, convergence, bit-identical
re-runs, energy on a hanging cloth, penetration-free rest on a sphere and a capsule, friction, the bending length's
meaning (Peirce's cantilever), the style dials, the simulation cage (venv: run this file, or pytest)."""
import math, os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit.sim import cage, settings, xpbd


def _sheet(nx, ny, h, z=0.0, x0=0.0, y0=0.0):
    V = np.array([(x0 + i * h, y0 + j * h, z) for i in range(nx) for j in range(ny)], float)
    Q = [(i * ny + j, (i + 1) * ny + j, (i + 1) * ny + j + 1, i * ny + j + 1) for i in range(nx - 1) for j in range(ny - 1)]
    return V, Q


def _plain(C, **kw):
    s = dict(gravity=(0, 0, -9.81), substeps=20, iterations=1, stretch=0.0, bend=-1.0, hold=None, damping=0.0,
             mu_s=0.0, mu_k=0.0, radius=0.0)
    s.update(kw)
    return s


def test_dihedral_gradient_matches_finite_differences():
    rng = np.random.default_rng(0)
    for _ in range(20):
        X = rng.normal(size=(4, 3))
        th, g = xpbd.dihedral(*X)
        G = np.zeros((4, 3))
        for i in range(4):
            for k in range(3):
                Xp, Xm = X.copy(), X.copy()
                Xp[i, k] += 1e-6; Xm[i, k] -= 1e-6
                G[i, k] = (xpbd.dihedral(*Xp)[0] - xpbd.dihedral(*Xm)[0]) / 2e-6
        assert np.abs(G - g).max() < 1e-7 * max(1.0, np.abs(G).max())
        assert np.abs(g.sum(0)).max() < 1e-9                       # translation invariance
    V = np.array([(0, 0, 0), (1, 0, 0), (0.5, 1, 0), (0.5, -1, 0)], float)
    assert abs(xpbd.dihedral(*V)[0]) < 1e-12                       # flat: 0


def test_a_hanging_strip_converges():
    """a strip pinned along its top edge hangs straight down at its rest length; the residual stretch falls as the
    substeps rise, and the strip comes to rest."""
    V, Q = _sheet(2, 21, 0.02)                                      # x across (2), y along (21 x 2 cm)
    pins = [0, 21]                                                  # its first row
    res = []
    for subs in (5, 20, 80):
        C = xpbd.Cloth(V, Q, pins=pins)
        S = xpbd.Solver(C, _plain(C, substeps=subs, damping=4.0))
        for _ in range(360):
            S.step(1 / 60)
        res.append(S.strain().max())
        if subs == 80:
            assert np.abs(S.v).max() < 1e-3
            assert abs(S.x[:, 2].min() + 0.4) < 2e-3                # hangs its length (0.4 m) below the pins
    assert res[0] > res[1] > res[2]
    assert res[2] < 1e-3


def test_re_runs_are_bit_identical():
    V, Q = _sheet(12, 12, 0.02, z=0.3, x0=-0.11, y0=-0.11)
    out = []
    for _ in range(2):
        C = xpbd.Cloth(V, Q)
        S = xpbd.Solver(C, _plain(C, substeps=10, iterations=2, bend=1e-3, mu_s=0.5, mu_k=0.3, radius=0.004,
                                  damping=1.0))
        caps = xpbd.Capsules([[0, 0, 0, 0, 0, 0, 0.12, 0.12], [-0.2, 0.05, 0.05, 0.2, 0.05, 0.05, 0.04, 0.06]])
        S.colliders = [caps]
        for f in range(60):
            caps.move([[0, 0.001 * f, 0, 0, 0.001 * f, 0, 0.12, 0.12], [-0.2, 0.05, 0.05, 0.2, 0.05, 0.05, 0.04, 0.06]])
            S.step(1 / 60)
        out.append((S.x.tobytes(), S.v.tobytes()))
    assert out[0] == out[1]


def test_energy_on_a_hanging_cloth():
    """released from level, pinned at two corners, with the profiles' own bending: with no damping the total energy
    (kinetic, gravity, bending) never rises above where it started (XPBD dissipates, it doesn't pump; measured: the
    worst rise is -2e-4 m g h at 40 substeps, +0.017 at 160, the hard stretch constraints' residual unaccounted); with
    damping it comes to rest below it. (With no bending at all the two-pin hammock is a mechanism that never settles.)"""
    V, Q = _sheet(11, 11, 0.02)
    C = xpbd.Cloth(V, Q, pins=[0, 10])
    E = lambda S: S.kinetic() + S.potential() + S.bending_energy()
    scale = C.mass.sum() * 9.81 * 0.2
    for style in ('anime', 'realistic'):
        bend = settings.cloth(C, style, L=0.25)['bend']
        S = xpbd.Solver(C, _plain(C, substeps=40, bend=bend))
        E0 = E(S)
        worst = -np.inf
        for _ in range(90):
            S.step(1 / 60)
            worst = max(worst, E(S) - E0)
        assert worst < 1e-3 * scale, (style, worst / scale)
        S = xpbd.Solver(C, _plain(C, substeps=40, bend=bend, damping=3.0))
        peak = 0.0
        for _ in range(300):
            S.step(1 / 60)
            peak = max(peak, S.kinetic())
        assert S.kinetic() < 1e-6 * peak, (style, S.kinetic() / peak)
        assert E(S) < E0 - 0.3 * scale


def _drop(collider, radius=0.005, seconds=2.0, mu=0.4):
    V, Q = _sheet(15, 15, 0.02, z=0.2, x0=-0.14, y0=-0.14)
    C = xpbd.Cloth(V, Q)
    bend = settings.cloth(C, 'realistic', L=0.25)['bend']
    S = xpbd.Solver(C, _plain(C, substeps=20, bend=bend, radius=radius, mu_s=mu, mu_k=0.8 * mu, damping=2.0))
    S.colliders = [collider]
    for _ in range(int(seconds * 60)):
        S.step(1 / 60)
    return S


def test_rests_on_a_sphere_without_penetration():
    sph = xpbd.Capsules([[0, 0, 0, 0, 0, 0, 0.1, 0.1]])
    S = _drop(sph)
    d = sph.distance(S.x) - 0.005
    assert d.min() > -1e-9                                          # resting on it, not in it
    assert S.x[:, 2].min() < -0.02                                  # and draped round it
    assert np.abs(S.v).max() < 0.05


def test_rests_on_a_capsule_without_penetration():
    cap = xpbd.Capsules([[-0.2, 0, 0, 0.2, 0, 0, 0.06, 0.06]])
    S = _drop(cap)
    assert (cap.distance(S.x) - 0.005).min() > -1e-9
    assert S.x[:, 2].min() < -0.03                                  # the free sides hang down past its equator


def test_rests_on_a_signed_distance_grid():
    """a sphere's mesh sampled into a grid: no vertex inside the grid's field, and within the grid's own error of the
    true sphere."""
    from charkit.geom import primitives
    m = primitives.icosphere(4) if hasattr(primitives, 'icosphere') else None
    if m is None:
        return
    Vs, Fs = (m.V, m.F) if hasattr(m, 'V') else m
    Vs = np.asarray(Vs, float) * 0.1
    G = xpbd.SDFGrid.from_mesh(Vs, Fs, 0.004, pad=0.05)
    S = _drop(G)
    assert (G.distance(S.x) - 0.005).min() > -1e-6                  # (friction's tangent move after the projection)
    assert (np.linalg.norm(S.x, axis=1) - 0.105).min() > -5e-4          # the grid's own error (h 4 mm)


def test_friction_holds_cloth_on_a_slope():
    """a small patch laid on a big sphere 25 degrees off its top: static friction (mu 0.8 > tan 25) holds it; none lets
    it slide off."""
    R = 1.0
    a = math.radians(25)
    V, Q = _sheet(4, 4, 0.01, x0=-0.015, y0=-0.015)
    Rm = np.array([[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]])
    V = V @ Rm.T + (R + 0.002) * np.array([math.sin(a), 0, math.cos(a)])
    moved = {}
    for mu in (0.8, 0.0):
        C = xpbd.Cloth(V, Q)
        S = xpbd.Solver(C, _plain(C, substeps=20, radius=0.002, mu_s=mu, mu_k=mu))
        S.colliders = [xpbd.Capsules([[0, 0, 0, 0, 0, 0, R, R]])]
        for _ in range(30):
            S.step(1 / 60)
        moved[mu] = np.linalg.norm(S.x - V, axis=1).max()
    assert moved[0.8] < 1e-3 and moved[0.0] > 0.02


def test_bending_length_is_peirces():
    """the profile's stiffness means a textile bending length c (settings.cloth): a strip clamped level and
    overhanging 2c droops to about Peirce's 42.9 degrees (the cantilever test, ASTM D1388)."""
    c, h = 0.1, 0.02
    xs = np.arange(-0.1, 2 * c + 1e-9, h)
    ny = 3
    V = np.array([(x, y * 0.025, 0.0) for x in xs for y in range(ny)])
    Q = [(i * ny + j, (i + 1) * ny + j, (i + 1) * ny + j + 1, i * ny + j + 1) for i in range(len(xs) - 1)
         for j in range(ny - 1)]
    C = xpbd.Cloth(V, Q, pins=[k for k in range(len(V)) if V[k, 0] <= 1e-9])
    st = settings.cloth(C, 'anime', L=1.0, hold_shape=0.0, cloth_stiffness=c / settings.BEND_LENGTH_MAX,
                        cloth_damping=0.8, substeps=2, iterations=300)
    S = xpbd.Solver(C, st)
    for _ in range(180):
        S.step(1 / 60)
    tip = S.x[np.isclose(V[:, 0], xs[-1])].mean(0)
    droop = math.degrees(math.atan2(-tip[2], tip[0]))
    assert abs(droop - 42.9) < 2.0, droop


def test_the_style_dials():
    """anime holds its drawn shape and is stiffer; realistic drapes. hold 0 is pure physics (no hold constraint)."""
    A, R = settings.physics('anime'), settings.physics('realistic')
    assert A['hold_shape'] > R['hold_shape'] and A['cloth_stiffness'] > R['cloth_stiffness']
    V, Q = _sheet(5, 5, 0.02)
    C = xpbd.Cloth(V, Q, pins=[0])
    sa, sr = settings.cloth(C, 'anime', L=0.25), settings.cloth(C, 'realistic', L=0.25)
    assert (sa['bend'] < sr['bend']).all() and (sa['hold'] < sr['hold']).all()
    assert settings.cloth(C, 'anime', L=0.25, hold_shape=0.0)['hold'] is None
    # the hold's meaning: a free vertex held at hold h sags (1 - h) / h * HOLD_SAG under its own weight
    V1 = np.array([(0, 0, 0), (0.01, 0, 0), (0, 0.01, 0)], float)
    C1 = xpbd.Cloth(V1, [(0, 1, 2)], pins=[1, 2])
    for h in (0.5, 0.8):
        st = settings.cloth(C1, 'anime', L=1.0, hold_shape=h, cloth_stiffness=0.0, stretch=1e9, substeps=4,
                            iterations=20, cloth_damping=0.5, tethers=False)
        S = xpbd.Solver(C1, st)
        for _ in range(600):
            S.step(1 / 60)
        assert abs(-S.x[0, 2] - (1 - h) / h * settings.HOLD_SAG) < 0.02 * settings.HOLD_SAG


def test_tethers_stop_a_long_hang_stretching():
    V, Q = _sheet(2, 41, 0.01)
    out = {}
    for teth in (False, True):
        C = xpbd.Cloth(V, Q, pins=[0, 41])
        S = xpbd.Solver(C, _plain(C, substeps=2, iterations=2, tethers=teth, damping=2.0))
        for _ in range(120):
            S.step(1 / 60)
        out[teth] = S.strain().max()
    assert out[True] < 0.25 * out[False]


def test_the_cage_carries_the_template():
    """a grid with a stepped lower edge and a sliver column: the cage keeps grid lines at least `spacing` apart, gives
    the template back exactly at rest, carries it rigidly, and follows a bend smoothly."""
    NR, NC = 12, 9
    xs = np.r_[0, 0.1, 0.2, 0.3, 0.302, 0.4, 0.5, 0.6, 0.7]
    zs = -np.arange(NR) * 0.1
    V = np.array([(x, 0.05 * math.sin(3 * x), z) for z in zs for x in xs])
    Fm = np.ones((NR - 1, NC - 1), bool)
    Fm[9:, 5:] = False                                               # a stair
    K = cage.Cage(V, NR, NC, Fm, 0.15, keep_rows=(0, 1))
    assert len(K.cols) < NC and len(K.rows) < NR and set(K.rows[:2]) == {0, 1}
    assert np.abs(K.carry(K.V) - V).max() < 1e-12
    th = 0.4
    Rz = np.array([[math.cos(th), -math.sin(th), 0], [math.sin(th), math.cos(th), 0], [0, 0, 1]])
    assert np.abs(K.carry(K.V @ Rz.T + 0.3) - (V @ Rz.T + 0.3)).max() < 1e-12
    Xb = K.V.copy()
    Xb[:, 1] += 0.2 * Xb[:, 2] ** 2                                  # bent back as it falls
    Vb = K.carry(Xb)
    assert np.abs(Vb[:, 1] - (V[:, 1] + 0.2 * V[:, 2] ** 2)).max() < 0.01


if __name__ == '__main__':
    import time
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            t = time.time(); f(); print('ok', k, '%.1fs' % (time.time() - t))
