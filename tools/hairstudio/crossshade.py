"""shadow that ignores the clumps (L17c's diagonal band vs L18b's per-clump form): in the front, three-quarter and back
views, the renderer's tone map (shade + deep) on the hair, split into connected shadow regions; a region crossing 3 or
more clumps (lock ids) is cross-clump shadow. Reported: the share of the hair's shadow pixels in cross-clump regions
(shadow that reads as a blotch over the mass: high) and the hair's total shadow share."""
import os, sys, json
import numpy as np
from scipy import ndimage
HERE = os.path.dirname(os.path.abspath(__file__))


def cross(tag):
    z = np.load(os.path.join(HERE, 'studio', tag + '_ours.npz'))
    out = {}
    for v in ('front', 'three_quarter', 'back'):
        if v + '_tone' not in z.files:
            continue
        t, ids, hair = z[v + '_tone'], z[v + '_ids'], z[v + '_hair']
        sh = (t >= 1) & (ids >= 0) & hair
        lab, n = ndimage.label(sh)
        cross_px = 0
        for k in range(1, n + 1):
            px = lab == k
            if px.sum() < 30:
                continue
            if len(np.unique(ids[px])) >= 3:
                cross_px += px.sum()
        out[v] = dict(cross=round(float(cross_px / max(sh.sum(), 1)), 3), shade=round(float(sh.sum() / max(hair.sum(), 1)), 3))
    return out


if __name__ == '__main__':
    for t in sys.argv[1:]:
        print(t, json.dumps(cross(t)))
