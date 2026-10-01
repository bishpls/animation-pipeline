"""One view's split zoomed on a window: the drawing with the hair's outline (blue), the truth's lock boundaries
(green), the extensions (red), the notches (magenta squares), the tips (yellow circles); beside it the same window with
the relative shadow tone (purple) and the hem zone (cyan edge), and our locks coloured.

    python tools/hairshell/zoomview.py VIEW OUT.png R0,R1,C0,C1 [--k 4] [--set K=V ...]
"""
import json, os, pickle, sys
import numpy as np
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools/hairsplit'))
from scipy import ndimage
from charkit import hairsplit as hs, hairlocks as hk
import pics

if __name__ == '__main__':
    a = sys.argv[1:]
    view, out = a[0], a[1]
    r0, r1, c0, c1 = [int(x) for x in a[2].split(',')]
    k = int(a[a.index('--k') + 1]) if '--k' in a else 4
    params = {}
    for i, q in enumerate(a):
        if q == '--set':
            kk, v = a[i + 1].split('=')
            params[kk] = json.loads(v)
    I = pickle.load(open(os.path.join(ROOT, 'charkit/out/hairsplit/inputs.pkl'), 'rb'))
    S = hs.Split(view, I['views'][view], I['ppl'], params); S.run()
    if not hasattr(S, 'hem_zone'):
        S.hem_zone_mask()
    T = hk.load_truth(os.path.join(ROOT, 'charkit/refs/clawd/hair_locks_truth.npz'))
    b = S.box
    t = T[0][view][b[0]:b[1], b[2]:b[3]]
    img = (S.rgb * 255).astype(np.uint8).copy()
    img[S.H & ~ndimage.binary_erosion(S.H)] = [0, 0, 255]
    for i in np.unique(t[t >= 0]):
        m = t == i
        img[m & ~ndimage.binary_erosion(m)] = [0, 220, 0]
    img[S.ext & ~S.ink] = [255, 0, 0]
    tone = (S.rgb * 255).astype(np.uint8).copy()
    tone[S.dark_rel] = (0.5 * tone[S.dark_rel] + 0.5 * np.array([90, 0, 160])).astype(np.uint8)
    z = S.hem_zone
    tone[z & ~ndimage.binary_erosion(z)] = [0, 200, 220]
    tone[S.ink] = 0
    lk = pics.colour(S.locks, S.rgb, 0.6, seed=5)
    lk[pics.edges(S.locks) & S.H] = [255, 255, 255]
    lk[S.ink] = 0
    ims = []
    for x in (img, tone, lk):
        im = Image.fromarray(x[r0:r1, c0:c1]).resize(((c1 - c0) * k, (r1 - r0) * k), Image.NEAREST)
        d = ImageDraw.Draw(im)
        for tt in S.notch_list:
            r, c = tt['rc']; d.rectangle([((c - c0) * k - 5, (r - r0) * k - 5), ((c - c0) * k + 5, (r - r0) * k + 5)], outline=(255, 0, 255), width=2)
        for tt in S.tip_list:
            r, c = tt['rc']; d.ellipse([((c - c0) * k - 5, (r - r0) * k - 5), ((c - c0) * k + 5, (r - r0) * k + 5)], outline=(255, 255, 0), width=2)
        ims.append(im)
    W = ims[0].size[0]
    canvas = Image.new('RGB', (W, sum(i.size[1] for i in ims) + 12), (255, 255, 255))
    y = 0
    for im in ims:
        canvas.paste(im, (0, y)); y += im.size[1] + 6
    canvas.save(out)
    print('wrote', out, json.dumps(S.report))
