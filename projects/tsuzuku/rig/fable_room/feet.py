"""Find the geta in a keyed drawing: each one's box, its lowest point, the front tooth (the planted foot's anchor: a geta that
rolls onto its toe pivots on it), and whether it's flat, tipped (heel up) or lifted. Used by build.py and for checking.
    .venv/bin/python projects/tsuzuku/rig/fable_room/feet.py NAME [NAME ...]     (drawings in rig/fable_room/src, full res)
"""
import os, sys
import numpy as np
from scipy import ndimage as ndi

D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(D, '..', '..', '..', '..', 'tools'))


def geta(img, xmin=900, facing=1, k=1.0):
    """img: keyed RGBA (full res). The geta are near-black, unsaturated wood at the bottom of the figure (x > xmin: not the props).
    facing +1: she faces right (the toe is the max-x end). k: the image's scale against the full-res drawings."""
    H, W = img.shape[:2]; yy, xx = np.mgrid[:H, :W]
    a = img[..., 3] > 200; r, g, b = [img[..., i].astype(int) for i in range(3)]
    fig = a & (xx > xmin); sole = np.nonzero(fig.any(1))[0].max()
    lum = .299 * r + .587 * g + .114 * b
    dark = fig & (lum < 72) & (np.abs(b - r) < 30) & (yy > sole - 330 * k)
    dark = ndi.binary_opening(dark, iterations=max(1, round(2 * k)))
    lab, n = ndi.label(ndi.binary_closing(dark, iterations=max(1, round(6 * k))))
    out = []
    for j in range(1, n + 1):
        m = lab == j
        if m.sum() < 2500 * k * k: continue
        ys, xs = np.nonzero(m); y1 = ys.max()
        band = m & (yy > y1 - 26 * k)                                   # the lowest 26 px: the tooth (or teeth) touching the floor
        bx = np.nonzero(band.any(0))[0]
        # split the band into teeth by gaps
        teeth, s = [], bx[0]
        for i in range(1, len(bx)):
            if bx[i] - bx[i - 1] > max(2, 6 * k): teeth.append((s, bx[i - 1])); s = bx[i]
        teeth.append((s, bx[-1]))
        front = max(teeth, key=lambda t: facing * t[0]) if facing else teeth[0]
        out.append({'box': [int(xs.min()), int(ys.min()), int(xs.max()), int(y1)], 'low': int(y1), 'teeth': [[int(a), int(b)] for a, b in teeth],
                    'toe': [round((front[0] + front[1]) / 2), int(y1)], 'lift': int(sole - y1)})
    out.sort(key=lambda g: g['toe'][0])
    return {'sole': int(sole), 'geta': out}


if __name__ == '__main__':
    from chroma import key
    for n in sys.argv[1:]:
        p = n if n.endswith('.png') else os.path.join(D, 'src', n + '.png')
        f = geta(key(p), facing=-1 if 'left' in n else 1)
        print(f'{os.path.basename(n):10s} sole {f["sole"]}', '  '.join(f'[box {g["box"]} toe {g["toe"]} teeth {len(g["teeth"])} lift {g["lift"]}]' for g in f['geta']))
