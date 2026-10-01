"""A splitter run's locks in one view against the lock truth, zoomed on a band of rows: ours coloured, the truth's lock
boundaries green, the ink black, our lock boundaries white; the truth's scored locks named with ours' IoU.

    python tools/hairshell/zoomtruth.py STAGES.npz VIEW OUT.png [--rows 0.5,1.0] [--stage locks] [--k 3]
"""
import os, pickle, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools/hairsplit'))
from charkit import hairsplit as hs, hairlocks as hk
from scipy import ndimage
import pics

if __name__ == '__main__':
    a = sys.argv[1:]
    Z = np.load(a[0]); view = a[1]; out = a[2]
    st = a[a.index('--stage') + 1] if '--stage' in a else 'locks'
    rows = [float(x) for x in a[a.index('--rows') + 1].split(',')] if '--rows' in a else [0.0, 1.0]
    k = int(a[a.index('--k') + 1]) if '--k' in a else 3
    I = pickle.load(open(os.path.join(ROOT, 'charkit/out/hairsplit/inputs.pkl'), 'rb'))
    T = hk.load_truth(os.path.join(ROOT, 'charkit/refs/clawd/hair_locks_truth.npz'))
    S = hs.Split(view, I['views'][view], I['ppl']); S.measure_ink()
    r0, r1, c0, c1 = S.box
    ours = Z['%s__%s' % (st, view)][r0:r1, c0:c1]
    t = T[0][view][r0:r1, c0:c1]
    rgb = S.rgb
    img = pics.colour(ours, rgb, 0.6, seed=5)
    img[pics.edges(ours) & S.H] = [255, 255, 255]
    for i in np.unique(t[t >= 0]):
        m = t == i
        img[m & ~ndimage.binary_erosion(m)] = [0, 220, 0]
    img[S.ink] = [0, 0, 0]
    H = img.shape[0]
    y0, y1 = int(rows[0] * H), int(rows[1] * H)
    Image.fromarray(pics.zoom(img[y0:y1], k)).save(out)
    print('wrote', out)
