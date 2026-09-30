"""charkit.perceptual without the model: a synthetic board registered onto the body grid, the patch matcher, region
pooling, grading, and the calibration's fits (weights, limits, leave-one-out, the geometric comparison) on toy data
with known answers (venv: run this file, or pytest)."""
import json, os, sys, tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import perceptual as P

PATCH = P.PATCH


# ------------------------------------------------------------------------------------------------------------ registration
def synthetic_build(d, L=0.2, H=1.6, x0=0.1, z0=0.9, half=0.03):
    """a build with no bundle: trace landmarks (eyes at z 1.4, the centre at the origin) and one body board (front,
    the board camera's orthographic framing) holding a red square of half-width `half` m at world (x0, z0)."""
    from PIL import Image
    os.makedirs(os.path.join(d, 'boards'))
    lm = dict(L=L, centre=[0.0, 0.0, 1.4], eyes=[[-0.03, 1.4], [0.03, 1.4]], chin_z=1.4 - 0.36 * L)
    with open(os.path.join(d, 'trace.jsonl'), 'w') as f:
        f.write(json.dumps(dict(landmarks=lm)) + '\n')
    json.dump(dict(body=dict(height_m=H)), open(os.path.join(d, 'clawd.spec.json'), 'w'))
    Ww, Hh = P.BODY_BOARD['res']
    ppm = max(Hh, Ww) / (P.BODY_BOARD['ortho'] * H)
    im = np.full((Hh, Ww, 3), 240, np.uint8)
    r = lambda z: Hh / 2 - (z - P.BODY_BOARD['target'] * H) * ppm
    c = lambda x: Ww / 2 + x * ppm
    im[int(round(r(z0 + half))):int(round(r(z0 - half))), int(round(c(x0 - half))):int(round(c(x0 + half)))] = (220, 30, 30)
    Image.fromarray(im).save(os.path.join(d, 'boards', 'body_000.png'))
    return lm


def test_board_lands_on_the_grid_where_the_landmarks_put_it():
    with tempfile.TemporaryDirectory() as d:
        L, x0, z0 = 0.2, 0.1, 0.9
        synthetic_build(d, L=L, x0=x0, z0=z0)
        O = P.Ours(d)
        g = O.on_grid('body', 'front')
        assert g is not None and O.B is None
        u, z = P.grid('body')
        ou, oz = O.anchor('front', 0)
        assert abs(ou) < 1e-9 and abs(oz - 1.4) < 1e-9
        red = (g['rgb'][..., 0] > 0.7) & (g['rgb'][..., 1] < 0.3)
        assert red.sum() > 50, red.sum()
        # the red square's centre on the grid, in L from the eyes: where the world point (x0, z0) should be
        cu, cz = u[red].mean(), z[red].mean()
        assert abs(cu - (x0 - ou) / L) < 0.02 and abs(cz - (z0 - oz) / L) < 0.02, (cu, cz)
        # its figure mask is the square (the board's near-white is background)
        assert g['fg'].sum() < 2 * red.sum() and (g['fg'] & red).sum() == red.sum()


def test_body_hi_is_the_same_window_at_twice_the_scale():
    wb, pb = P.win('body')
    wh, ph = P.win('body_hi')
    assert ph == 2 * pb and all(abs(wb[k] - wh[k]) < 1e-9 for k in wb)
    assert P.SCALES['body_hi']['views'] == P.SCALES['body']['views']


# ------------------------------------------------------------------------------------------------------------ distances
def features(h=6, w=5, c=8, seed=0):
    return np.random.default_rng(seed).standard_normal((h, w, c)).astype(np.float32)


def test_patch_distance_forgives_a_one_patch_shift_only():
    F = features()
    m, a = P.patch_distance(F, F)
    assert np.abs(m).max() < 1e-5 and np.abs(a).max() < 1e-5
    G = np.roll(F, 1, axis=1)                       # everything one patch to the right (the wrapped column aside)
    m, a = P.patch_distance(F, G)
    assert np.median(m[:, 1:-1]) < 1e-5 and np.median(a) > 0.5
    G2 = np.roll(F, 2, axis=1)                      # two patches: out of the match's reach
    m2, _ = P.patch_distance(F, G2)
    assert np.median(m2[:, 2:-2]) > 0.3


def test_region_stats_weights_patches_by_coverage():
    h, w = 4, 4
    dmap = np.zeros((h, w)); dmap[0, 0] = 1.0; dmap[0, 1] = 0.5
    md = np.zeros((h * PATCH, w * PATCH), bool)
    md[:PATCH, :PATCH] = True                       # patch (0, 0) whole
    md[:PATCH, PATCH:PATCH + PATCH // 2] = True     # half of patch (0, 1)
    st = P.region_stats(dmap, {'boots': (md, None)}, grow=0)['boots']
    assert abs(st['patches'] - 1.5) < 1e-9
    assert abs(st['dist'] - (1.0 * 1 + 0.5 * 0.5) / 1.5) < 1e-4, st
    md2 = np.zeros_like(md); md2[:2, :2] = True     # under MIN_COVER of a patch: not in the region
    assert P.region_stats(dmap, {'x': (md2, None)}, grow=0) == {}


def test_grade_against_limits_and_scales():
    C = dict(floors={'body/front/boots': 0.05}, weights={'boots': 2.0}, limits=dict(warn=0.1, fail=0.2))
    assert P.grade(C, 'body', 'front', 'boots', 0.1) == (0.1, 'WARN')
    assert P.grade(C, 'body', 'front', 'boots', 0.2) == (0.3, 'FAIL')
    assert P.grade(C, 'head', 'front', 'boots', 0.2)[1] == 'INFO'      # boots are graded at the body scale
    assert P.grade(None, 'body', 'front', 'boots', 0.2) == (None, 'INFO')


# ------------------------------------------------------------------------------------------------------------ calibration
def test_fit_limits_separates_the_severities():
    y = np.array([0.0, 0.1, 0.5, 0.6, 1.0, 1.2])
    sev = np.array([0, 0, 2, 2, 3, 3])
    lim = P.fit_limits(y, sev)
    assert 0.1 < lim['warn'] < 0.5 and 0.6 < lim['fail'] < 1.0, lim
    assert [P._grade_of(v, lim) for v in y] == ['PASS', 'PASS', 'WARN', 'WARN', 'FAIL', 'FAIL']


def test_fit_weights_scales_a_group_read_too_low():
    # group 1's values run at a fifth of group 0's for the same severity: its fitted weight must come out above 1
    sev = [0, 1, 2, 3] * 2
    X = [[0.0], [0.1], [0.2], [0.3]] + [[0.0], [0.02], [0.04], [0.06]]
    idx = [0] * 4 + [1] * 4
    th = P.fit_weights(X, sev, idx, 2, ridge=0.01)
    assert np.exp(th[1] - th[0]) > 2, np.exp(th)
    y = P._scores(X, idx, th)
    assert P._rho(y, sev) > P._rho(P._scores(X, idx, np.zeros(2)), sev)


def test_boot_diff_and_pair_geometry():
    sev = np.array([0, 1, 2, 3, 0, 1, 2, 3, 3, 2])
    y = sev + np.random.default_rng(1).normal(0, 0.1, len(sev))       # a metric that ranks them
    g = np.zeros(len(sev)); g[-1] = 2                                  # a check that passes nearly everything
    b = P.boot_diff(y, g, sev, n=300)
    assert b['lo'] > 0 and b['mean'] > 0.3, b
    q = dict(check=dict(worse=[0.3, 'FAIL'], better=[0.6, 'WARN'], higher_is_better=True))
    assert P._pair_geo(q) == (True, True)
    q = dict(check=dict(worse=[0.987, 'PASS'], better=[1.001, 'PASS'], target=1.0))
    assert P._pair_geo(q) == (False, True)


def test_geo_region_reads_the_worst_check_of_the_region_and_view():
    qa = {'boot_front_ankle_jog_L': dict(value=0.07, status='FAIL'), 'piece_boot_L': dict(value=0.9, status='PASS'),
          'boot_profile_heel_L': dict(value=0.0, status='WARN'), 'piece_skirt': dict(value=0.5, status='FAIL')}
    assert P.geo_region(dict(region='boots', view='*'), qa) == ('FAIL', 'boot_front_ankle_jog_L')
    assert P.geo_region(dict(region='boots', view='profile'), qa) == ('WARN', 'boot_profile_heel_L')
    assert P.geo_region(dict(region='arms', view='*'), qa) == (None, None)


def test_label_values_take_the_worst_view_less_its_floor():
    res = dict(scales=dict(body=dict(
        front=dict(regions=dict(boots=dict(dist=0.2, p90=0.3, patches=10, dist_l18=0.4))),
        profile=dict(regions=dict(boots=dict(dist=0.1, p90=0.2, patches=10, dist_l18=0.3))))))
    F = {'body/front/boots': 0.15, 'body/*/boots': 0.05}
    v = P.label_values(dict(region='boots', view='*'), res, F)
    assert abs(v['front'] - 0.05) < 1e-9 and abs(v['profile'] - 0.05) < 1e-9      # profile: the fallback floor
    assert abs(P.label_values(dict(region='boots', view='front'), res, {}, 18)['front'] - 0.4) < 1e-9
    assert abs(P.label_values(dict(region='boots', view='front'), res, {}, None, 'p90')['front'] - 0.3) < 1e-9
    assert P.label_values(dict(region='boots', view='*'), res, {}, None, 'dist', 'body_hi') == {}


def test_auc_and_the_local_statistic():
    assert P.auc([0.9, 0.8, 0.1, 0.2], [3, 2, 0, 1]) == 1.0
    assert P.auc([0.5, 0.5], [3, 0]) == 0.5
    # three builds on one 2x3 grid; build c has one bad patch in the boots, the others none: its local statistic (k 1)
    # is that patch's excess over the per-patch floor, the others ~0
    with tempfile.TemporaryDirectory() as d:
        cov = np.array([[1, 1, 0], [0, 0, 0]], np.float16)
        pairs = []
        for name, bad in (('a', 0.0), ('b', 0.0), ('c', 0.3)):
            dm = np.full((2, 3), 0.2); dm[0, 1] += bad
            p = os.path.join(d, name + '.npz')
            np.savez(p, **{'body_front__dmap_l24': dm, 'body_front__cov_boots': cov})
            pairs.append((dict(scales=dict(body=dict(front=dict(regions=dict(boots=dict(dist=0.2, patches=2)))))), p))
        P.local_stats(pairs, layers=(24,), k=1)
        got = [r['scales']['body']['front']['regions']['boots']['top1_l24'] for r, _ in pairs]
        assert abs(got[0]) < 1e-6 and abs(got[1]) < 1e-6 and abs(got[2] - 0.3) < 0.07, got


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok', name)
