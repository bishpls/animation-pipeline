"""The closing stage against the lock truth's lines: the truth's lock lines (the boundary pixels of a truth lock next to
another truth lock: the drawn and the truth-maker's closed lines) against our walls (ink, extensions, the along-flow
closures; skeletonised). Recall: the truth's lock-line pixels within TOL px of a wall. Precision: our wall skeleton's
pixels inside the truth's locks (scored, away from the truth's outer edges by TOL) that lie within TOL px of a lock
line (a wall through a lock's middle is a false cut). Per view; the drawn ink alone and with the extensions.

    python tools/hairsplit/linecheck.py [--tol 3] [--set K=V ...]
"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
from charkit import hairsplit as hs, hairlocks as hk
import dev


def truth_lines(t):
    from scipy import ndimage
    inner = np.zeros(t.shape, bool)
    lock = t >= 0
    for i in np.unique(t[lock]):
        ti = t == i
        other = ndimage.binary_dilation(lock & ~ti, iterations=2)
        inner |= (ti & ~ndimage.binary_erosion(ti)) & other
    return inner


def measure(walls, t, tol):
    from scipy import ndimage
    from skimage import morphology
    lines = truth_lines(t)
    sk = morphology.skeletonize(walls)
    dw = ndimage.distance_transform_edt(~sk)
    rec = float((dw[lines] <= tol).mean()) if lines.any() else None
    lock = t >= 0
    core = ndimage.binary_erosion(lock, iterations=int(tol) + 1) | lines  # inside the locks (not on their outer edge)
    dl = ndimage.distance_transform_edt(~lines)
    ours = sk & ndimage.binary_erosion(lock, iterations=int(tol))
    prec = float((dl[ours] <= tol).mean()) if ours.any() else None
    f = 2 * rec * prec / (rec + prec) if rec and prec else 0.0
    return dict(recall=round(rec, 3) if rec is not None else None, precision=round(prec, 3) if prec is not None else None,
                f=round(f, 3), line_px=int(lines.sum()), wall_px_in_locks=int(ours.sum()))


if __name__ == '__main__':
    a = sys.argv[1:]
    tol = float(a[a.index('--tol') + 1]) if '--tol' in a else 3
    params = {}
    for i, q in enumerate(a):
        if q == '--set':
            k, v = a[i + 1].split('=')
            params[k] = json.loads(v)
    I = dev.load_inputs()
    T = hk.load_truth('charkit/refs/clawd/hair_locks_truth.npz')
    agg = {}
    for name, V in I['views'].items():
        S = hs.Split(name, V, I['ppl'], params)
        S.pipeline()
        r0, r1, c0, c1 = S.box
        t = hk.fill_walls(T[0][name], np.ones(T[0][name].shape, bool))[r0:r1, c0:c1]
        rows = {'ink': S.ink, 'ink+ext': S.walls, 'lock walls': S.lockwalls,
                'lock edges': (lambda L: (np.pad(L[:, 1:] != L[:, :-1], ((0, 0), (0, 1))) |
                                         np.pad(L[1:, :] != L[:-1, :], ((0, 1), (0, 0)))) & S.H)(S.locks)}
        for k, w in rows.items():
            m = measure(w, t, tol)
            agg.setdefault(k, []).append((m['recall'] or 0, m['precision'] or 0, m['line_px'], m['wall_px_in_locks']))
            print('%-14s %-11s recall %.3f  precision %.3f  F %.3f' % (name, k, m['recall'] or 0, m['precision'] or 0, m['f']))
    for k, v in agg.items():
        R = sum(x[0] * x[2] for x in v) / sum(x[2] for x in v)
        Pp = sum(x[1] * x[3] for x in v) / max(1, sum(x[3] for x in v))
        print('%-14s %-11s recall %.3f  precision %.3f  F %.3f' % ('all', k, R, Pp, 2 * R * Pp / max(1e-9, R + Pp)))
