"""The appeal scorecard (Michael, 2026-10-02: "what makes a hairstyle look good?"), measured on the studio's crops
(design.npz and TAG_ours.npz: the head window at 300 px per L, the eye line at row 360, the hair mask). Each measure
is read the same way from the design and from ours; the design is the calibration (it should score as "good").

  face_window   front: the opening the hair frames round the face, its isoperimetric roughness (1 = smooth oval;
                higher = jagged) and the share of the face's width it shows
  silhouette    the outline's curvature energy at large scale (a simple big shape: low) and the share of its
                small-scale energy that sits in the lower half (detail at the tips, not on the crown: high)
  hierarchy     value shapes (the hair's luminance in 3 clusters, connected components): the Gini of their areas
                (a few big + many small: high) and the count of big shapes (> 4% of the hair)
  speckle       the share of the hair's area in value shapes under 0.002 L^2 (noise: low)
  detail        edge density in the face-frame band (within 0.25 L of the face window) over the crown's (the hair
                above the window, away from the face): detail where the eye should go (> 1)
  flow          the structure tensor's coherence over the hair (one direction field: high)
  rhythm        the lower outline's tips: the CV of their spacing (mechanical ~0, random > 0.6)
  symmetry      front: the hair mask's IoU with its mirror (balanced but alive: ~0.85-0.95)

    python appeal.py TAG [TAG ...]       -> studio/appeal.json, studio/appeal.html
"""
import json, os, sys
import numpy as np
from scipy import ndimage, signal

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'studio')
P, EYE = 300, 360
VIEWS = ('front', 'three_quarter', 'profile', 'back')


def load(tag):
    z = np.load(os.path.join(OUT, 'design.npz' if tag == 'design' else tag + '_ours.npz'))
    return {v: (z[v + '_rgb'], z[v + '_hair']) for v in VIEWS}


def lum(rgb):
    return rgb @ np.array([0.299, 0.587, 0.114])


def outline(hair):
    """the hair's outer contour (the largest component, holes filled) as (n, 2) row, col, ordered."""
    from skimage import measure
    m = ndimage.binary_fill_holes(hair)
    lab, n = ndimage.label(m)
    if not n:
        return None
    big = lab == (1 + np.argmax(ndimage.sum(m, lab, range(1, n + 1))))
    cs = measure.find_contours(big.astype(float), 0.5)
    return max(cs, key=len) if cs else None


def curvature_energy(c, sigma):
    x = ndimage.gaussian_filter1d(c[:, 1], sigma, mode='wrap'); y = ndimage.gaussian_filter1d(c[:, 0], sigma, mode='wrap')
    dx, dy = np.gradient(x), np.gradient(y); ddx, ddy = np.gradient(dx), np.gradient(dy)
    k = (dx * ddy - dy * ddx) / np.maximum((dx ** 2 + dy ** 2) ** 1.5, 1e-9)
    return k


def face_window(rgb, hair):
    """the face opening: inside the hair's filled outline, above the chin, below the crown, not hair."""
    filled = ndimage.binary_fill_holes(ndimage.binary_closing(hair, iterations=6))
    H, W = hair.shape
    rows = (np.arange(H) > EYE - 0.55 * P) & (np.arange(H) < EYE + 0.45 * P)
    win = filled & ~hair
    win[~rows] = False
    lab, n = ndimage.label(win)
    if not n:
        return None, None
    cx = W // 2
    k = lab[EYE, cx] if lab[EYE, cx] else 1 + np.argmax(ndimage.sum(win, lab, range(1, n + 1)))
    w = lab == k
    area = w.sum()
    per = np.logical_xor(w, ndimage.binary_erosion(w)).sum()
    rough = per / (2 * np.sqrt(np.pi * max(area, 1)))
    cols = np.where(w.any(0))[0]
    return round(float(rough), 3), round(float((cols.max() - cols.min()) / P), 3) if len(cols) else None


def value_shapes(rgb, hair):
    Y = lum(rgb)
    v = Y[hair]
    if v.size < 100:
        return None
    qs = np.quantile(v, [1 / 3, 2 / 3])
    cls = np.digitize(Y, qs)
    areas = []
    for k in range(3):
        lab, n = ndimage.label((cls == k) & hair)
        if n:
            areas += list(ndimage.sum(np.ones_like(lab), lab, range(1, n + 1)))
    a = np.sort(np.array(areas, float))
    tot = hair.sum()
    gini = 1 - 2 * np.sum(np.cumsum(a) / a.sum()) / len(a) + 1 / len(a)
    big = int((a > 0.04 * tot).sum())
    speck = float(a[a < 0.002 * P * P].sum() / tot)
    return round(float(gini), 3), big, round(speck, 3)


def edges(rgb, hair):
    Y = ndimage.gaussian_filter(lum(rgb), 1.0)
    g = np.hypot(ndimage.sobel(Y, 1), ndimage.sobel(Y, 0))
    inner = ndimage.binary_erosion(hair, iterations=3)
    return (g > 0.25) & inner, g, inner


def scores(rgb, hair, view):
    d = {}
    c = outline(hair)
    if c is not None and len(c) > 200:
        kL = curvature_energy(c, 0.08 * P)
        kS = curvature_energy(c, 0.008 * P) - kL
        d['silhouette_simple'] = round(float(np.mean(np.abs(kL)) * P), 3)
        lower = c[:, 0] > EYE
        eS = np.abs(kS)
        d['detail_at_tips'] = round(float(eS[lower].sum() / max(eS.sum(), 1e-9)), 3)
        # rhythm: the lower outline's tips (local maxima of the row coordinate along the contour)
        yy = ndimage.gaussian_filter1d(c[:, 0], 2, mode='wrap')
        pk, _ = signal.find_peaks(yy, prominence=0.02 * P)
        pk = pk[yy[pk] > EYE + 0.1 * P]
        if len(pk) >= 4:
            sp = np.diff(np.sort(pk))
            d['rhythm_cv'] = round(float(np.std(sp) / max(np.mean(sp), 1e-9)), 3)
    vs = value_shapes(rgb, hair)
    if vs:
        d['hierarchy_gini'], d['big_shapes'], d['speckle'] = vs
    e, g, inner = edges(rgb, hair)
    J = [ndimage.gaussian_filter(x, 6) for x in (ndimage.sobel(lum(rgb), 1) ** 2, ndimage.sobel(lum(rgb), 0) ** 2,
                                                  ndimage.sobel(lum(rgb), 1) * ndimage.sobel(lum(rgb), 0))]
    tr = J[0] + J[1]
    coh = np.sqrt((J[0] - J[1]) ** 2 + 4 * J[2] ** 2) / np.maximum(tr, 1e-9)
    wgt = g * inner
    d['flow_coherence'] = round(float((coh * wgt).sum() / max(wgt.sum(), 1e-9)), 3)
    if view == 'front':
        fw = face_window(rgb, hair)
        if fw[0] is not None:
            d['face_window_rough'], d['face_window_width'] = fw
            filled = ndimage.binary_fill_holes(ndimage.binary_closing(hair, iterations=6))
            win = filled & ~hair
            band = ndimage.binary_dilation(win, iterations=int(0.25 * P)) & hair
            crown = hair & (np.arange(hair.shape[0])[:, None] < EYE - 0.35 * P) & ~band
            db = e[band].mean() if band.any() else 0
            dc = e[crown].mean() if crown.any() else 0
            d['detail_frame_vs_crown'] = round(float(db / max(dc, 1e-4)), 2)
        d['symmetry'] = round(float((hair & hair[:, ::-1]).sum() / max((hair | hair[:, ::-1]).sum(), 1)), 3)
    return d


def main(tags):
    rep = {}
    for t in ['design'] + list(tags):
        V = load(t)
        rep[t] = {v: scores(*V[v], v) for v in VIEWS}
    json.dump(rep, open(os.path.join(OUT, 'appeal.json'), 'w'), indent=1)
    keys = ['silhouette_simple', 'detail_at_tips', 'rhythm_cv', 'hierarchy_gini', 'big_shapes', 'speckle', 'flow_coherence',
            'face_window_rough', 'face_window_width', 'detail_frame_vs_crown', 'symmetry']
    for k in keys:
        row = []
        for t in rep:
            vals = [rep[t][v].get(k) for v in VIEWS if rep[t][v].get(k) is not None]
            row.append('%7s' % ('%.3g' % np.mean(vals) if vals else '-'))
        print('%-22s' % k, ' '.join(row))
    print('%-22s' % '', ' '.join('%7s' % t[:7] for t in rep))


if __name__ == '__main__':
    main(sys.argv[1:])
