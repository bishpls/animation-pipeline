"""charkit.hairlocks: the lock scorer on partitions with known answers, the calibration (the truth passes, a shuffled
partition fails), and the tracked lock truth against its source (venv: run this file, or pytest)."""
import json, os, sys, tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import hairlocks as hk

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _truth():
    """a 40 x 40 view: three vertical locks (cols 0-12, 13-25, 26-39) over rows 10-39, the crown rows 0-9 unscored."""
    t = np.full((40, 40), -1, np.int32)
    t[10:, :13] = 0
    t[10:, 13:26] = 1
    t[10:, 26:] = 2
    t[:10] = -2
    return t, ['bangs/a', 'bangs/b', 'bangs/c']


def test_known_answers():
    t, labels = _truth()
    hair = np.ones(t.shape, bool)
    ours = np.where(t >= 0, t + 1, 0)
    r = hk.score_view(ours, t, labels, hair, 20.0)
    assert r['lock_iou'] == 1.0 and r['matched'] == 3 and r['boundary_L'] == 0 and r['purity'] == 1.0
    # the crown is unscored: ours reaching into it changes nothing
    o2 = ours.copy(); o2[:10, :13] = 1
    assert hk.score_view(o2, t, labels, hair, 20.0)['lock_iou'] == 1.0
    # one line moved 4 columns: locks a and b change, c doesn't
    o3 = ours.copy(); o3[10:, 13:17] = 1
    r = hk.score_view(o3, t, labels, hair, 20.0)
    a = 13 * 30 / (17 * 30); b = 9 * 30 / (13 * 30)
    assert abs(r['locks']['bangs/a']['iou'] - a) < 1e-3 and abs(r['locks']['bangs/b']['iou'] - b) < 1e-3
    assert r['locks']['bangs/c']['iou'] == 1.0
    # two locks merged: one of them unmatched (0)
    o4 = ours.copy(); o4[o4 == 2] = 1
    r = hk.score_view(o4, t, labels, hair, 20.0)
    assert r['matched'] == 2 and min(x['iou'] for x in r['locks'].values()) == 0.0


def test_calibration_on_the_tracked_truth():
    """the check separates: the truth against itself 1.0; a shuffled partition (random Voronoi cells, as many as the
    locks) scores far lower in every view."""
    T = hk.load_truth(os.path.join(ROOT, 'charkit/refs/clawd/hair_locks_truth.npz'))
    for v, t in T[0].items():
        hair = t != -1
        f = hk.fill_walls(t, hair)
        own = hk.score_view(np.where(f >= 0, f + 1, 0), t, T[1][v], hair, T[2]['ppl'])
        sh = np.mean([hk.score_view(hk.shuffled(f, s), t, T[1][v], hair, T[2]['ppl'])['lock_iou'] for s in range(3)])
        assert own['lock_iou'] == 1.0, v
        assert sh < 0.7, (v, sh)


def test_tracked_truth_matches_its_source():
    from charkit import manifest
    spec = manifest.resolve(json.load(open(os.path.join(ROOT, 'charkit/spec/clawd.json'))))
    R = manifest.load(spec['ref']['manifest'])['references']
    ent = R['hair_locks_truth']
    T0, L0, m0 = hk.load_truth(ent['path'])
    with tempfile.TemporaryDirectory() as d:
        hk.build_truth(spec, ent['source'], os.path.join(d, 't.npz'), R['hair_truth']['path'], log=lambda *a: None)
        T1, L1, m1 = hk.load_truth(os.path.join(d, 't.npz'))
    assert L0 == L1 and set(T0) == set(T1)
    for v in T0:
        assert np.array_equal(T0[v], T1[v]), v


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
