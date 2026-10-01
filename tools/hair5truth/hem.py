"""The hem's flick tips and notches along a view's hair outline, for cutting hem flicks (notch to notch, straight):
the hair's silhouette (the sheet's hair with its outline strokes, holes filled) traced; along the outline below row R0
and within cols C0..C1, the local extremes of the row (smoothed over SMOOTH px of the outline) with a prominence of
PROM px: tips (lowest points) and notches (highest points between tips).

    python tools/hair5truth/hem.py VIEW R0 C0 C1 [OUT.png] [--prom 4]
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import ctx5
sys.path.insert(0, os.path.join(ROOT, "tools", "hairlocks"))
import refcheck as rc

SMOOTH = 3


def outline(C, view):
    B = rc.body_view(C, view)
    from scipy import ndimage
    from skimage import measure
    m = ndimage.binary_fill_holes(ndimage.binary_closing(B['hair'], iterations=1))
    cs = measure.find_contours(m.astype(float), 0.5)
    return max(cs, key=len)            # (row, col) along the outline


def extremes(C, view, r0, c0, c1, prom=4):
    from scipy.signal import find_peaks
    P = outline(C, view)
    sel = (P[:, 0] >= r0) & (P[:, 1] >= c0) & (P[:, 1] <= c1)
    idx = np.nonzero(sel)[0]
    # the longest run of consecutive outline points in the window
    runs = np.split(idx, np.nonzero(np.diff(idx) > 1)[0] + 1)
    run = max(runs, key=len)
    Q = P[run]
    k = np.ones(2 * SMOOTH + 1) / (2 * SMOOTH + 1)
    r = np.convolve(np.pad(Q[:, 0], SMOOTH, mode='edge'), k, 'valid')
    tips, _ = find_peaks(r, prominence=prom)
    notches, _ = find_peaks(-r, prominence=prom)
    T = [(int(round(Q[i, 1])), int(round(Q[i, 0]))) for i in tips]
    N = [(int(round(Q[i, 1])), int(round(Q[i, 0]))) for i in notches]
    return T, N, Q


if __name__ == '__main__':
    a = sys.argv[1:]
    view, r0, c0, c1 = a[0], int(a[1]), int(a[2]), int(a[3])
    prom = float(a[a.index('--prom') + 1]) if '--prom' in a else 4
    C = ctx5.make()
    T, N, Q = extremes(C, view, r0, c0, c1, prom)
    print('tips (x, y):', T)
    print('notches (x, y):', N)
    if len(a) > 4 and a[4].endswith('.png'):
        import pic as P
        from PIL import ImageDraw
        box = (r0 - 10, int(Q[:, 0].max()) + 10, c0 - 5, c1 + 5)
        im = P.picture(C, view, box, 4, 'sheet')
        dr = ImageDraw.Draw(im)
        for (x, y), col in [(t, (0, 160, 0)) for t in T] + [(n, (220, 0, 0)) for n in N]:
            X, Y = (x - box[2]) * 4, (y - box[0]) * 4
            dr.ellipse([X - 5, Y - 5, X + 5, Y + 5], outline=col, width=2)
        im.save(a[4])
        print(a[4], box)
