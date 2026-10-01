"""The lock truth's per-family scores for any lock images, with the floors per family:

  own        the truth against itself (its locks, walls filled as the scorer does): 1.0 by construction
  shuffled   the truth's locks in a view re-cut into as many random Voronoi cells (hairlocks.shuffled; 5 seeds): the
             known-bad partition test_hairlocks.py calibrates on
  shuffled within family
             each family's area re-cut into as many random cells as it has locks (5 seeds): the family boundaries kept,
             the locks random (a family with one lock in a view scores 1.0 here: no floor for it)
  NAME=X.npz a build's locks (tools/hair5truth/ours5.py) or a sheet's regions on the grids (refcheck's _regions.npz)

    python tools/hair5truth/score5.py OUT.json NAME=LOCKS.npz ...
"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
from charkit import hairlocks as hk

TRUTH = os.path.join(ROOT, 'charkit/refs/clawd/hair_locks_truth.npz')
SEEDS = 5


def fam_table(r):
    """hk.score's result -> {view: {family: lock_iou}} and 'all'."""
    out = {}
    for v, x in r.items():
        out[v] = {f: y['lock_iou'] for f, y in x.get('families', {}).items()}
        out[v]['_all'] = x['lock_iou']
    return out


def within_family(t, labels, seed):
    """each family's truth area re-cut into as many random cells as it has locks."""
    rng = np.random.RandomState(seed)
    from scipy import ndimage
    out = np.zeros(t.shape, np.int32)
    k0 = 0
    fams = sorted({hk.family_of(q) for q in labels})
    for f in fams:
        ids = [i for i, q in enumerate(labels) if hk.family_of(q) == f and (t == i).any()]
        m = np.isin(t, ids)
        k = len(ids)
        ys, xs = np.nonzero(m)
        j = rng.choice(len(ys), k, replace=False)
        mk = np.zeros(m.shape, np.int32)
        mk[ys[j], xs[j]] = np.arange(1, k + 1)
        _, idx = ndimage.distance_transform_edt(mk == 0, return_indices=True)
        out[m] = mk[idx[0], idx[1]][m] + k0
        k0 += k
    return out


def mean_tables(ts):
    keys = {(v, f) for t in ts for v in t for f in t[v]}
    out = {}
    for v, f in keys:
        out.setdefault(v, {})[f] = round(float(np.mean([t[v][f] for t in ts if v in t and f in t[v]])), 3)
    return out


def floors(T):
    imgs, labels, meta = T
    hair = {v: np.ones(t.shape, bool) for v, t in imgs.items()}
    # as the scorer fills the truth (hairlocks.score_main: every pixel within WALL_FILL px of a lock, the drawn
    # outline and the lines between locks), so the truth against itself is 1.0
    filled = {v: hk.fill_walls(t, hair[v]) for v, t in imgs.items()}
    own = hk.score({v: np.where(f >= 0, f + 1, 0) for v, f in filled.items()}, T, hair, meta['ppl'])
    sh, shf = [], []
    for s in range(SEEDS):
        sh.append(fam_table(hk.score({v: hk.shuffled(f, s) for v, f in filled.items()}, T, hair, meta['ppl'])))
        shf.append(fam_table(hk.score({v: within_family(f, labels[v], s) for v, f in filled.items()}, T, hair,
                                      meta['ppl'])))
    return dict(own=fam_table(own), shuffled=mean_tables(sh), shuffled_within_family=mean_tables(shf))


def load_any(path):
    Z = np.load(path)
    if 'names' in Z.files:
        names = {int(k): v for k, v in json.loads(str(Z['names'])).items()}
        return {k: Z[k] for k in Z.files if k not in ('names', 'ppl')}, names
    # a sheet's regions: walls (0) inside its regions' reach given to the nearest region, as the labeller's
    img = {}
    for v in Z.files:
        g = Z[v]
        from scipy import ndimage
        reach = ndimage.binary_dilation(g > 0, iterations=2)
        img[v] = hk.fill_labels(g, reach, 2)
    return img, None


if __name__ == '__main__':
    a = sys.argv[1:]
    out = a[0]
    T = hk.load_truth(TRUTH)
    res = dict(truth=dict(locks={v: len(l) for v, l in T[1].items()},
                          per_family={v: {f: sum(1 for q in l if hk.family_of(q) == f)
                                          for f in sorted({hk.family_of(q) for q in l})} for v, l in T[1].items()}),
               floors=floors(T), sets={})
    hair = {v: np.ones(t.shape, bool) for v, t in T[0].items()}
    for arg in a[1:]:
        name, path = arg.split('=', 1)
        img, names = load_any(path)
        r = hk.score(img, T, hair, T[2]['ppl'], names)
        res['sets'][name] = dict(table=fam_table(r), full=r)
    json.dump(res, open(out, 'w'), indent=1)
    # the table: per view and family, each set against the floors
    views = list(T[0]) + ['all']
    fams = sorted({f for v in res['floors']['own'] for f in res['floors']['own'][v]})
    cols = ['own', 'shuffled', 'shuffled_within_family'] + list(res['sets'])
    print('%-14s %-11s %s' % ('view', 'family', ' '.join('%10s' % c[:10] for c in cols)))
    for v in views:
        for f in fams:
            row = [res['floors'][c].get(v, {}).get(f) for c in cols[:3]] + \
                  [res['sets'][c]['table'].get(v, {}).get(f) for c in cols[3:]]
            if row[0] is None:
                continue
            print('%-14s %-11s %s' % (v, f, ' '.join('%10s' % ('-' if q is None else '%.3f' % q) for q in row)))
    print('wrote', out)
