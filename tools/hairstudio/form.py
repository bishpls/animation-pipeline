"""clump form and weight (Michael: "very pasta-like, with broad flat strands"; "weight on the top might be too high"):
  plateau     per long clump (outer and inner back, front framing), the share of its length at >= 80% of its widest
              (parallel-edged ribbons: high)
  width_cv    the spread of the clumps' widths (uniform noodles: low)
  weight      the front view's hair width (from the hair mask, L) at temple height (0.1 L above the eyes) over the
              width at shoulder height (0.9 L below): top-heavy > 1, fuller below < 1"""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
P, EYE = 300, 360


def form(tag, bdir):
    L = json.load(open(os.path.join(bdir, 'locks.json')))
    pl, ws = [], []
    for lk in L['locks']:
        if lk['group'] in (2, 3, 4, 5) and lk.get('wprof'):
            w = np.interp(np.linspace(0, 1, 101), np.linspace(0, 1, len(lk['wprof'])), lk['wprof'])
            pl.append(float((w >= 0.8).mean())); ws.append(lk.get('width_max', 0))
    z = np.load(os.path.join(HERE, 'studio', tag + '_ours.npz'))
    hm = z['front_hair']
    def width(row):
        cols = np.where(hm[int(row)])[0]
        return (cols.max() - cols.min()) / P if len(cols) else 0.0
    wt, ws_ = width(EYE - 0.1 * P), width(min(EYE + 0.9 * P, hm.shape[0] - 1))
    return dict(plateau=round(float(np.mean(pl)), 3), width_cv=round(float(np.std(ws) / max(np.mean(ws), 1e-9)), 3),
                weight=round(wt / max(ws_, 1e-9), 3), temple_w=round(wt, 3), shoulder_w=round(ws_, 3))


if __name__ == '__main__':
    for t in sys.argv[1:]:
        print(t, json.dumps(form(t, os.path.join(HERE, 'it', t))))
