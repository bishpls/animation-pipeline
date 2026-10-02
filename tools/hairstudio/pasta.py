"""what reads as pasta (the plateau measure moved but the picture barely did): on the back view's render and lock map,
in the band from the shoulders to mid-back,
  form      within-clump luminance spread over the between-clump spread (a clump shaded as a rounded form: higher;
            flat ribbons: low)
  stripes   the spacing of clump boundaries along rows: its CV (evenly spaced parallel noodles: low)
  crossing  the share of boundary pixels whose boundary runs within 20 deg of vertical (all parallel: high)"""
import os, sys, json
import numpy as np
from scipy import ndimage
HERE = os.path.dirname(os.path.abspath(__file__)); P, EYE = 300, 360


def pasta(tag):
    z = np.load(os.path.join(HERE, 'studio', tag + '_ours.npz'))
    rgb, ids, hair = z['back_rgb'], z['back_ids'], z['back_hair']
    Y = rgb @ np.array([0.299, 0.587, 0.114])
    r0, r1 = int(EYE + 0.55 * P), int(min(EYE + 1.0 * P, ids.shape[0] - 1))
    band = np.zeros_like(hair); band[r0:r1] = True
    m = band & (ids >= 0) & hair
    vals = {}
    for i in np.unique(ids[m]):
        px = m & (ids == i)
        if px.sum() > 60:
            vals[i] = Y[px]
    within = np.mean([v.std() for v in vals.values()])
    between = np.std([v.mean() for v in vals.values()])
    e = np.zeros_like(m)
    e[:, 1:] |= (ids[:, 1:] != ids[:, :-1]) & m[:, 1:]
    sp = []
    for r in range(r0, r1, 4):
        xs = np.where(e[r])[0]
        if len(xs) > 3:
            d = np.diff(xs); d = d[d > 2]
            if len(d) > 2:
                sp.append(np.std(d) / np.mean(d))
    gy, gx = ndimage.sobel(ids.astype(float), 0), ndimage.sobel(ids.astype(float), 1)
    ang = np.degrees(np.arctan2(np.abs(gy), np.abs(gx)))
    vert = (ang[e] < 20).mean() if e.any() else 0
    return dict(form=round(float(within / max(between, 1e-6)), 3), stripes_cv=round(float(np.mean(sp)), 3) if sp else None,
                vertical=round(float(vert), 3))


if __name__ == '__main__':
    for t in sys.argv[1:]:
        print(t, json.dumps(pasta(t)))
