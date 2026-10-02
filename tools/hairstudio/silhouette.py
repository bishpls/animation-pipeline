"""silhouette strength (Michael's taste session 1: he picks the builds whose tips are well defined over cleaner interiors):
on our renders (TAG_ours.npz hair masks; 3D-native, no drawing), per view, the hair's outer outline:
  tips        outline points sticking out: local maxima of distance from the hair's centroid, prominence > 0.03 L
  tip_prom    their mean prominence (L): how far each tip stands out
  tip_sharp   their mean sharpness: the outline's turning angle across +-0.03 L at the tip (deg; pointed: high)
  strength    tips x prominence x sharpness, normalised: one number"""
import json, os, sys
import numpy as np
from scipy import ndimage, signal
from skimage import measure
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, 'studio'); P = 300
VIEWS = ('front', 'three_quarter', 'profile', 'back')


def sil(tag):
    z = np.load(os.path.join(OUT, tag + '_ours.npz'))
    res = {}
    for v in VIEWS:
        hair = z[v + '_hair']
        m = ndimage.binary_fill_holes(ndimage.binary_closing(hair, iterations=1))
        lab, n = ndimage.label(m)
        if not n:
            continue
        m = lab == (1 + np.argmax(ndimage.sum(m, lab, range(1, n + 1))))
        cs = measure.find_contours(m.astype(float), 0.5)
        c = max(cs, key=len)
        cy, cx = np.argwhere(m).mean(0)
        r = np.hypot(c[:, 0] - cy, c[:, 1] - cx)
        r = ndimage.gaussian_filter1d(r, 1.5, mode='wrap')
        pk, pr = signal.find_peaks(np.concatenate([r, r]), prominence=0.03 * P)
        keep = (pk >= len(r) // 2) & (pk < len(r) // 2 + len(r))
        pk, prom = pk[keep] % len(r), pr['prominences'][keep]
        step = int(0.03 * P)
        ang = []
        for k in pk:
            a, b, o = c[(k - step) % len(c)], c[(k + step) % len(c)], c[k]
            v1, v2 = a - o, b - o
            cosang = (v1 @ v2) / max(np.linalg.norm(v1) * np.linalg.norm(v2), 1e-9)
            ang.append(180 - np.degrees(np.arccos(np.clip(cosang, -1, 1))))
        res[v] = dict(tips=int(len(pk)), tip_prom=round(float(prom.mean() / P), 4) if len(pk) else 0.0,
                      tip_sharp=round(float(np.mean(ang)), 1) if ang else 0.0)
        res[v]['strength'] = round(res[v]['tips'] * res[v]['tip_prom'] * res[v]['tip_sharp'], 3)
    tot = {k: round(float(np.mean([res[v][k] for v in res])), 4) for k in ('tips', 'tip_prom', 'tip_sharp', 'strength')}
    return tot


if __name__ == '__main__':
    J = [json.loads(l) for l in open(os.path.join(HERE, 'taste', 'judgments.jsonl'))]
    cache = {}
    def g(t):
        t = t.split(' ')[0]
        if t not in cache:
            cache[t] = sil(t)
        return cache[t]
    for t in ('c47', 'c48', 'c52', 'c59', 'c63', 'c64', 's1_paper', 's2_ribbon', 's3_graphic', 's4_lustrous'):
        print('%-12s' % t, g(t))
    print()
    for key in ('tips', 'tip_prom', 'tip_sharp', 'strength'):
        ok = n = 0
        for j in J:
            if j['pick'] == 'same':
                continue
            win, lose = (j['a'], j['b']) if j['pick'] == 'a' else (j['b'], j['a'])
            a_, b_ = g(win)[key], g(lose)[key]
            if a_ != b_:
                n += 1; ok += a_ > b_
        print('%-10s orders %d of %d of Michael\'s picks (higher = his pick)' % (key, ok, n))
