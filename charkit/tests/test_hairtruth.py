"""charkit.hairlayers' truth and score: the scorer on labellings with known answers, and the tracked truth against its
source (venv: run this file, or pytest)."""
import json, os, sys, tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import hairlayers as hl

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _truth():
    """a 20 x 20 view: rows 0-9 bangs, 10-14 side_locks or upper_back, 15-19 bun_L; column 0 unscored."""
    t = np.zeros((20, 20), np.int16)
    t[10:15] = 1
    t[15:] = 2
    t[:, 0] = -1
    return {'front': t}, [['bangs'], ['side_locks', 'upper_back'], ['bun_L']], {}


def test_score_known_answers():
    T = _truth()
    perfect = {'front__bangs': np.zeros((20, 20), bool), 'front__upper_back': np.zeros((20, 20), bool),
               'front__buns': np.zeros((20, 20), bool), 'front__bun_L': np.zeros((20, 20), bool)}
    perfect['front__bangs'][:10] = True
    perfect['front__upper_back'][10:15] = True           # the set's second: accepted
    perfect['front__buns'][15:] = True
    perfect['front__bun_L'][15:] = True
    r = hl.score(perfect, T)
    assert r['front']['accuracy'] == 1.0 and r['front']['wrong'] == 0
    assert r['all']['iou'] == {'bangs': 1.0, 'upper_back': 1.0, 'buns': 1.0}
    assert r['sides']['front']['bun_L'] == 1.0
    wrong = {k: v.copy() for k, v in perfect.items()}
    wrong['front__bangs'][:10, 10:] = False               # half the bangs called the lower back
    wrong['front__lower_back'] = np.zeros((20, 20), bool)
    wrong['front__lower_back'][:10, 10:] = True
    r = hl.score(wrong, T)
    assert r['front']['wrong'] == 100                     # 10 rows x 10 columns (column 0 unscored lies elsewhere)
    assert abs(r['all']['iou']['bangs'] - 90 / 190) < 1e-3
    assert r['all']['confusions'][0] == dict(view='front', truth='bangs', got='lower_back', px=100)
    try:
        hl.score({'front__bangs': np.zeros((5, 5), bool)}, T)
    except ValueError:
        pass
    else:
        raise AssertionError('a grid other than the truth\'s must be refused')


def test_a_lock_region_takes_its_agreeing_family_whole():
    """vote_regions: a region 70% bangs becomes bangs whole; a 50/50 region keeps its pixels; a wall pixel inside the
    hair takes its nearest region's family."""
    hair = np.ones((10, 20), bool)
    regions = np.zeros((10, 20), np.int32)
    regions[:, :9] = 1; regions[:, 10:] = 2                 # column 9: a drawn line (a wall)
    fam = np.zeros((10, 20), np.int32)
    fam[:, :9] = 1; fam[:3, :9] = 3                        # region 1: 70% bangs (1), 30% upper_back (3)
    fam[:, 10:] = 2; fam[:5, 10:] = 4                      # region 2: 50/50
    fam[:, 9] = 4
    out = hl.vote_regions(fam, regions, hair, 0.6)
    assert (out[:, :9] == 1).all()
    assert (out[:, 10:] == fam[:, 10:]).all()
    assert (out[:, 9] == 1).all() or (out[:, 9] == np.where(np.arange(10) < 5, 4, 2)).all()


def test_tracked_truth_matches_its_source():
    """hair_truth.npz is what `hairlayers truth` makes from hair_truth.json: the source is the record, the npz its
    product (tracked so a score needs no rebuild)."""
    from charkit import manifest
    spec = manifest.resolve(json.load(open(os.path.join(ROOT, 'charkit/spec/clawd.json'))))
    ent = manifest.load(spec['ref']['manifest'])['references']['hair_truth']
    T0, S0, m0 = hl.load_truth(ent['path'])
    with tempfile.TemporaryDirectory() as d:
        hl.build_truth(spec, ent['source'], os.path.join(d, 't.npz'), log=lambda *a: None)
        T1, S1, m1 = hl.load_truth(os.path.join(d, 't.npz'))
    assert S0 == S1 and set(T0) == set(T1)
    for v in T0:
        assert np.array_equal(T0[v], T1[v]), v


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
