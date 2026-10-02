"""The appeal scorecard, 3D-native (Michael, 2026-10-02: "you probably shouldn't compare to the 2D result. It keeps
poisoning 3D-native measurements"). Every measure is computed on the 3D groom (its locks.json centrelines and the
bundle's geometry) or on our own renders (TAG_ours.npz), never against the drawing. Calibration: Michael's judgments
of our builds (PAIRS: the better build first); a measure is useful when it orders those pairs as he did.

  noise         per group, how jagged the locks' parameters (width, length, curl) are along the sheet: the mean
                |second difference| over neighbours sorted by alpha, relative to the spread (random: high; designed
                variation: low)
  flow3d        neighbouring locks' agreement in direction: the mean angle (deg) between each lock's tangents and its
                nearest neighbour's at matched positions along them (one flow field: low)
  edge_on       the share of visible hair seen nearly edge-on, front / profile / back (shards: high)
  speckle       on our renders (4 views): the share of the hair in tiny value shapes (noise: high)
  sil_rough     on our renders: the outline's small-scale curvature energy (ragged: high)
  sil_spread    its spread across the 4 views (a shape coherent from every angle: low)
  size_ratio    the locks' width distribution: the ratio of the 80th to the 20th percentile (a clear hierarchy: higher)

    python appeal3d.py              -> studio/appeal3d.json, the calibration table
"""
import json, os, sys
import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
sys.path.insert(0, os.path.expanduser('~/animation-pipeline-3d'))
OUT = os.path.join(HERE, 'studio')
BUILDS = {t: os.path.join(HERE, 'it', t + 'b') for t in ('c42', 'c46', 'c47', 'c48', 'c50', 'c51', 'c52', 'c58', 'c63')}
PAIRS = [('c48', 'c47', '48 is a solid improvement over 47'), ('c47', 'c46', '47 is by far your best work so far'),
         ('c47', 'c42', '47 is by far your best work so far'), ('c48', 'c51', "51: I think that's getting worse"),
         ('c50', 'c51', "51: I think that's getting worse"), ('c63', 'c58', '58 covered the face; 63 the fixes')]
VIEWS = ('front', 'three_quarter', 'profile', 'back')
P = 300


def lockdata(tag):
    p = os.path.join(BUILDS[tag], 'locks.json')
    return json.load(open(p)) if os.path.exists(p) else None


def noise(L):
    C = np.array(L['centre'])
    by = {}
    for lk in L['locks']:
        Pp = np.array(lk['P'])
        if len(Pp) < 4:
            continue
        r = Pp[0] - C
        a = np.degrees(np.arctan2(r[0], r[1]))
        seg = np.linalg.norm(np.diff(Pp, axis=0), axis=1)
        T = np.diff(Pp, axis=0) / np.maximum(seg[:, None], 1e-9)
        curl = np.sum(np.arccos(np.clip(np.sum(T[1:] * T[:-1], 1), -1, 1))) / max(seg.sum(), 1e-9)
        by.setdefault(lk['group'], []).append((a, lk.get('width', 0), seg.sum(), curl))
    vals = []
    for g, rows in by.items():
        if len(rows) < 5:
            continue
        A = np.array(sorted(rows))
        for k in (1, 2, 3):
            x = A[:, k]
            sd = np.std(x)
            if sd < 1e-9:
                vals.append(0.0); continue
            vals.append(float(np.mean(np.abs(np.diff(x, 2))) / sd))
    return round(float(np.mean(vals)), 3) if vals else None


def flow3d(L):
    locks = [np.array(lk['P']) for lk in L['locks'] if len(lk['P']) >= 6 and lk['group'] in (2, 4, 5, 6, 7)]
    if len(locks) < 4:
        return None
    S = 8
    res = []
    for Pp in locks:
        s = np.linspace(0, 1, len(Pp))
        Q = np.stack([np.interp(np.linspace(0, 1, S), s, Pp[:, i]) for i in range(3)], 1)
        T = np.gradient(Q, axis=0); T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)
        res.append((Q, T))
    mids = np.array([q[S // 2] for q, _ in res])
    tree = cKDTree(mids)
    angs = []
    for i, (Q, T) in enumerate(res):
        d, j = tree.query(mids[i], k=2)
        T2 = res[j[1]][1]
        angs.append(np.degrees(np.arccos(np.clip(np.abs(np.sum(T * T2, 1)), -1, 1))).mean())
    return round(float(np.mean(angs)), 2)


def size_ratio(L):
    w = np.array([lk.get('width', 0) for lk in L['locks'] if lk['group'] in (2, 6) and lk.get('width', 0) > 0])
    return round(float(np.percentile(w, 80) / max(np.percentile(w, 20), 1e-9)), 3) if len(w) > 4 else None


def render_measures(tag):
    p = os.path.join(OUT, tag + '_ours.npz')
    if not os.path.exists(p):
        return {}
    z = np.load(p)
    sp, sr = [], []
    from skimage import measure
    for v in VIEWS:
        rgb, hair = z[v + '_rgb'], z[v + '_hair']
        Y = rgb @ np.array([0.299, 0.587, 0.114])
        q = np.quantile(Y[hair], [1 / 3, 2 / 3]) if hair.sum() > 100 else (0.3, 0.6)
        cls = np.digitize(Y, q)
        tiny = 0
        for k in range(3):
            lab, n = ndimage.label((cls == k) & hair)
            if n:
                a = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
                tiny += a[a < 0.002 * P * P].sum()
        sp.append(tiny / max(hair.sum(), 1))
        m = ndimage.binary_fill_holes(hair)
        cs = measure.find_contours(m.astype(float), 0.5)
        if cs:
            c = max(cs, key=len)
            x, y = c[:, 1], c[:, 0]
            def k_(sig):
                xs, ys = ndimage.gaussian_filter1d(x, sig, mode='wrap'), ndimage.gaussian_filter1d(y, sig, mode='wrap')
                dx, dy = np.gradient(xs), np.gradient(ys); ddx, ddy = np.gradient(dx), np.gradient(dy)
                return (dx * ddy - dy * ddx) / np.maximum((dx * dx + dy * dy) ** 1.5, 1e-9)
            sr.append(float(np.mean(np.abs(k_(1.5) - k_(0.04 * P))) * P))
    return dict(speckle=round(float(np.mean(sp)), 3), sil_rough=round(float(np.mean(sr)), 2) if sr else None,
                sil_spread=round(float(np.std(sr) / max(np.mean(sr), 1e-9)), 3) if sr else None)


def main():
    from studio3d import edge_on
    from charkit import bundle as bl
    rep = {}
    for t, b in BUILDS.items():
        L = lockdata(t)
        d = dict(noise=noise(L) if L else None, flow3d=flow3d(L) if L else None, size_ratio=size_ratio(L) if L else None)
        B = bl.load(b)
        d['edge_on'] = round(float(np.mean([edge_on(B, az) for az in (0.0, 90.0, 180.0)])), 3)
        d.update(render_measures(t))
        rep[t] = d
        print(t, json.dumps(d))
    # calibration: for each measure, how many of Michael's pairs it orders correctly (lower-is-better and higher-is-better)
    keys = sorted({k for d in rep.values() for k in d})
    cal = {}
    for k in keys:
        lo = hi = n = 0
        for a, b, _ in PAIRS:
            va, vb = rep[a].get(k), rep[b].get(k)
            if va is None or vb is None or va == vb:
                continue
            n += 1; lo += va < vb; hi += va > vb
        cal[k] = dict(pairs=n, lower_better=lo, higher_better=hi)
    print('\ncalibration against Michael\'s pairs (the better build should be lower / higher):')
    for k, c in cal.items():
        print('  %-11s %d pairs: lower-better %d, higher-better %d' % (k, c['pairs'], c['lower_better'], c['higher_better']))
    json.dump(dict(builds=rep, calibration=cal, pairs=PAIRS), open(os.path.join(OUT, 'appeal3d.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
