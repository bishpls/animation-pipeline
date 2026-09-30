"""The hull-sourced garments read the hull's labelled shell, not its decimated mesh (garments.hull_pieces, shell_points):
on a synthetic hull with known answers, two decimations of one surface give the builders the same points and so the
same garment; the shell's points sit on the surface; stray label patches are left out (venv: run this file, or
pytest)."""
import json, os, sys, tempfile

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from charkit import garments as gm

H = 0.02                                                   # the synthetic grid's spacing (L)
SKIRT, BAND = 8, 10                                        # their labels (the sidecar names them)
STRAY_AT = (0.0, 0.1)                                      # (theta, z): a planted 3 x 3 patch of skirt label on the band


def r_skirt(z):
    return 0.3 + 0.3 * -np.asarray(z)


def hem(th):
    return 1.0 + 0.2 * (1 - np.cos(th)) / 2                # the back hangs 0.2 longer


def figure():
    """a skirt-like occupancy (the hull's frame: z up, the front toward -y; z indexed downward as the hull's is): a cone
    from z 0 (radius 0.3) to its hem (z -1 in front, -1.2 at the back) under a band (z 0 .. 0.16, radius 0.28); its
    shell (occupied with an empty face neighbour) labelled skirt below z 0 and band above, with a small skirt patch
    planted on the band (a stray label). -> dict as hull.npz holds it."""
    xs = np.arange(-0.9, 0.9 + H / 2, H); ys = np.arange(-0.9, 0.9 + H / 2, H); zs = np.arange(0.3, -1.4 - H / 2, -H)
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing='ij')
    th, r = np.arctan2(X, -Y), np.hypot(X, Y)
    V = ((Z <= 0) & (Z >= -hem(th)) & (r <= r_skirt(Z))) | ((Z > 0) & (Z <= 0.16) & (r <= 0.28))
    P = np.pad(V, 1)
    inner = np.ones_like(V)
    for k in range(3):
        for s in (-1, 1):
            sl = [slice(1, -1)] * 3
            sl[k] = slice(1 + s, P.shape[k] - 1 + s)
            inner &= P[tuple(sl)]
    S = np.argwhere(V & ~inner)
    zS, thS = zs[S[:, 2]], np.arctan2(xs[S[:, 0]], -ys[S[:, 1]])
    lab = np.where(zS > 0, BAND, SKIRT).astype(np.int32)
    near = (np.abs(zS - STRAY_AT[1]) < 1.6 * H) & (np.abs(np.angle(np.exp(1j * (thS - STRAY_AT[0])))) * 0.28 < 1.6 * H)
    lab[near] = SKIRT
    return dict(V=V, xs=xs, ys=ys, zs=zs, shell=S.astype(np.int16), shell_label=lab), int(near.sum())


def write_hull(d, Z, faces):
    """a hull directory as charkit.geom.hull.build writes one: hull.glb (the surface decimated to `faces`), the sidecar,
    the per-vertex pieces (each vertex its nearest shell voxel's label), hull.npz."""
    from charkit.geom import hull, io, remesh
    A = hull.Axes(Z['xs'], Z['ys'], Z['zs'], H)
    m = remesh.decimate(hull.surface(Z['V'], A), faces)
    S = Z['shell'].astype(np.int64)
    lab, _ = hull.vertex_labels(m, dict(ix=S[:, 0], iy=S[:, 1], iz=S[:, 2], label=Z['shell_label'],
                                        cls=np.zeros(len(S), np.int16)), A)
    os.makedirs(d, exist_ok=True)
    io.save(m, os.path.join(d, 'hull.glb'))
    np.save(os.path.join(d, 'hull_pieces.npy'), lab)
    json.dump({'eyes': [[0.1, 0, 0], [-0.1, 0, 0]], 'units': 'L', 'pieces': 'hull_pieces.npy',
               'piece_names': {str(SKIRT): 'skirt', str(BAND): 'waistband'}}, open(os.path.join(d, 'hull.glb.json'), 'w'))
    np.savez_compressed(os.path.join(d, 'hull.npz'), **Z)
    return os.path.join(d, 'hull.glb'), len(m.V)


def pieces(glb, source='shell'):
    """hull_pieces on a synthetic hull, its eyes aligned onto themselves (no assembly: the transform is the identity)."""
    from charkit import i3d
    real = i3d.eye_target
    i3d.eye_target = lambda A, shape: (np.zeros(3), 0.2)
    try:
        return gm.hull_pieces({'hair': {'shape': {'glb': glb}}}, None, source=source)
    finally:
        i3d.eye_target = real


A1 = {'head': {'L': 1.0}, 'verts': np.zeros((1, 3)), 'weights': {'hips': np.ones(1)}}
SKIRT_SPEC = {'name': 'skirt', 'pleat': 0.0, 'under': 'waistband', 'tuck': 0.0}


def test_shell_points_lie_on_the_surface():
    """each point on the occupancy's boundary: the cone's radius at its height within half a voxel (median well under)."""
    Z, _ = figure()
    P, lab = gm.shell_points(Z)
    side = (lab == SKIRT) & (P[:, 2] < -0.1) & (P[:, 2] > -0.9)
    e = np.hypot(P[side, 0], P[side, 1]) - r_skirt(P[side, 2])
    assert abs(np.median(e)) < 0.25 * H and np.percentile(np.abs(e), 95) < H, (np.median(e), np.percentile(np.abs(e), 95))
    C = np.stack([Z['xs'][Z['shell'][:, 0]], Z['ys'][Z['shell'][:, 1]], Z['zs'][Z['shell'][:, 2]]], 1)
    Pa, _ = gm.shell_points(Z, stray=None)
    assert np.abs(Pa - C).max() <= 0.5 * H * (1 + 1e-9)             # a voxel's exposed faces: within half a voxel


def test_stray_patches_are_left_out():
    """the planted patch of skirt label on the band is its own small patch: dropped, and nothing else is."""
    Z, n_stray = figure()
    size, largest = gm.shell_patches(Z['shell'], Z['shell_label'])
    lab = Z['shell_label']
    assert n_stray >= 4 and (size[lab == BAND] == (lab == BAND).sum()).all()        # the band: one patch round it
    stray = (lab == SKIRT) & (Z['zs'][Z['shell'][:, 2]] > 0)
    assert (size[stray] == n_stray).all() and (largest[stray] == (lab == SKIRT).sum() - n_stray).all()
    P, l = gm.shell_points(Z)
    Pa, la = gm.shell_points(Z, stray=None)
    assert len(Pa) - len(P) == n_stray and not ((l == SKIRT) & (P[:, 2] > H)).any()


def test_the_garments_do_not_depend_on_the_decimation():
    """two decimations of the same hull: the mesh's vertices (the old source) differ and so does the skirt lofted from
    them; the shell's points are the same bits, and so is the skirt."""
    Z, _ = figure()
    with tempfile.TemporaryDirectory() as d:
        g1, n1 = write_hull(os.path.join(d, 'a'), Z, 12000)
        g2, n2 = write_hull(os.path.join(d, 'b'), Z, 12600)
        assert n1 != n2
        S1, S2 = pieces(g1), pieces(g2)
        assert S1.keys() == S2.keys() and all(np.array_equal(S1[k], S2[k]) for k in S1)
        M1, M2 = pieces(g1, 'mesh'), pieces(g2, 'mesh')
        assert len(M1['skirt']) != len(M2['skirt'])
        k1 = gm.skirt_hull(A1, SKIRT_SPEC, S1)['verts']
        k2 = gm.skirt_hull(A1, SKIRT_SPEC, S2)['verts']
        assert np.array_equal(k1, k2)
        m1 = gm.skirt_hull(A1, SKIRT_SPEC, M1)['verts']
        m2 = gm.skirt_hull(A1, SKIRT_SPEC, M2)['verts']
        assert np.abs(m1 - m2).max() > 1e-4                   # the mesh's source moves with its decimation


def test_the_skirt_from_the_shell_follows_the_cone():
    """lofted from the shell: on the cone, the back longer, the waist under the band."""
    Z, _ = figure()
    P, lab = gm.shell_points(Z)
    Hd = {'skirt': P[lab == SKIRT], 'waistband': P[lab == BAND]}
    V = gm.skirt_hull(A1, SKIRT_SPEC, Hd)['verts']
    th, r = np.arctan2(V[:, 0], -V[:, 1]), np.hypot(V[:, 0], V[:, 1])
    mid = (V[:, 2] < -0.1) & (V[:, 2] > -0.9)
    assert np.percentile(np.abs(r[mid] - r_skirt(V[mid, 2])), 90) < 0.03
    lo_front, lo_back = V[np.abs(th) < 0.3, 2].min(), V[np.abs(th) > np.pi - 0.3, 2].min()
    assert -1.05 < lo_front < -0.93 and -1.25 < lo_back < -1.12, (lo_front, lo_back)
    assert V[:, 2].max() < 0.02 + 1.5 * H          # tucked under the band: its lowest voxels sit at z = H (0.035 here)


def test_shell_sampling_runs_without_scipy():
    """Blender's Python has no scipy: the shell's sampling and the pieces from it mustn't need it."""
    import subprocess, textwrap
    Z, _ = figure()
    with tempfile.TemporaryDirectory() as d:
        np.savez_compressed(os.path.join(d, 'hull.npz'), **Z)
        json.dump({'eyes': [[0.1, 0, 0], [-0.1, 0, 0]], 'pieces': 'hull_pieces.npy',
                   'piece_names': {str(SKIRT): 'skirt', str(BAND): 'waistband'}}, open(os.path.join(d, 'hull.glb.json'), 'w'))
        code = textwrap.dedent('''
            import sys, builtins
            real = builtins.__import__
            def guard(name, *a, **k):
                if name == 'scipy' or name.startswith('scipy.'):
                    raise ImportError('no scipy here (as in Blender)')
                return real(name, *a, **k)
            builtins.__import__ = guard
            sys.path.insert(0, %r)
            import numpy as np
            from charkit import garments as gm, i3d
            i3d.eye_target = lambda A, shape: (np.zeros(3), 0.2)
            Hd = gm.hull_pieces({'hair': {'shape': {'glb': %r}}}, None)
            A = {'head': {'L': 1.0}, 'verts': np.zeros((1, 3)), 'weights': {'hips': np.ones(1)}}
            gm.skirt_hull(A, {'name': 'skirt', 'under': 'waistband'}, Hd)
            print('ok', len(Hd['skirt']))
        ''') % (ROOT, os.path.join(d, 'hull.glb'))
        r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
        assert r.returncode == 0 and 'ok' in r.stdout, r.stderr[-1500:]


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok', name)
