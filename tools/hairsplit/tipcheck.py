"""The tip detector against the lock truth: each truth lock with a drawn tip (the truth's tips: not 'cut' or 'hidden')
has its tip as the pixel of its region furthest from the view's crown (the detector's own potential); a detected tip
within RADIUS L of it is a hit. Reports recall, precision against all truth locks' tips (a detected tip on scored hair
that is near no truth tip is a false tip only where the truth scores the hair: tips on unscored or out-of-truth hair are
left out), per view and family.

    python tools/hairsplit/tipcheck.py [--radius 0.04] [--set K=V ...]
"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
from charkit import hairsplit as hs, hairlocks as hk
import dev


def truth_tips(S, T, labels, tips_meta):
    r0, r1, c0, c1 = S.box
    t = T[r0:r1, c0:c1]
    out = {}
    for i, q in enumerate(labels):
        if tips_meta.get(q, 'drawn') != 'drawn':
            continue
        rr, cc = np.nonzero(t == i)
        if not len(rr):
            continue
        d = np.hypot(rr - S.crown[0], cc - S.crown[1])
        j = int(np.argmax(d))
        out[q] = (float(rr[j]), float(cc[j]))
    return out


if __name__ == '__main__':
    a = sys.argv[1:]
    rad = float(a[a.index('--radius') + 1]) if '--radius' in a else 0.04
    params = {}
    for i, q in enumerate(a):
        if q == '--set':
            k, v = a[i + 1].split('=')
            params[k] = json.loads(v)
    I = dev.load_inputs()
    T = hk.load_truth('charkit/refs/clawd/hair_locks_truth.npz')
    tot = dict(hit=0, n=0, det_scored=0, det_true=0)
    for name, V in I['views'].items():
        S = hs.Split(name, V, I['ppl'], params)
        S.measure_ink(); S.strokes(); S.flow(); S.tips(); S.flow(S.tip_list); S.tips()
        tt = truth_tips(S, T[0][name], T[1][name], T[2]['tips'].get(name, {}))
        D = np.array([t['rc'] for t in S.tip_list])
        R = rad * S.ppl
        miss = []
        hit = 0
        for q, p in tt.items():
            d = np.hypot(*(D - np.array(p)).T).min() if len(D) else np.inf
            if d <= R:
                hit += 1
            else:
                miss.append('%s (%.0f px)' % (q, d))
        # precision: detected tips on the truth's locks (scored, in scope) that are near no truth tip
        r0, r1, c0, c1 = S.box
        tc = hk.fill_walls(T[0][name], np.ones(T[0][name].shape, bool))[r0:r1, c0:c1]
        P_ = np.array(list(tt.values())) if tt else np.zeros((0, 2))
        ds = dt = 0
        for t in S.tip_list:
            r, c = int(round(t['rc'][0])), int(round(t['rc'][1]))
            # the tip's neighbourhood on a truth lock
            win = tc[max(0, r - 3):r + 4, max(0, c - 3):c + 4]
            if not (win >= 0).any():
                continue
            ds += 1
            if len(P_) and np.hypot(*(P_ - np.array(t['rc'])).T).min() <= R:
                dt += 1
        print('%-14s truth tips %2d  hit %2d (recall %.2f)  detected on truth locks %2d, true %2d (precision %.2f)  missed: %s'
              % (name, len(tt), hit, hit / max(1, len(tt)), ds, dt, dt / max(1, ds), ', '.join(miss)))
        tot['hit'] += hit; tot['n'] += len(tt); tot['det_scored'] += ds; tot['det_true'] += dt
    print('all: recall %.3f  precision %.3f' % (tot['hit'] / max(1, tot['n']), tot['det_true'] / max(1, tot['det_scored'])))
