"""A zoomed debug crop of one view: the sheet, the regions or locks, the tips (numbered), notches, seeds.

    python tools/hairsplit/zoom.py VIEW R0 R1 C0 C1 OUT.png [--what regions|locks|cells|truth] [--zoom 4] [--set K=V]
"""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
from charkit import hairsplit as hs, hairlocks as hk
import dev, pics

if __name__ == '__main__':
    a = sys.argv[1:]
    v, r0, r1, c0, c1, out = a[0], int(a[1]), int(a[2]), int(a[3]), int(a[4]), a[5]
    what = a[a.index('--what') + 1] if '--what' in a else 'regions'
    k = int(a[a.index('--zoom') + 1]) if '--zoom' in a else 4
    params = {}
    for i, q in enumerate(a):
        if q == '--set':
            kk, vv = a[i + 1].split('=')
            params[kk] = json.loads(vv)
    I = dev.load_inputs()
    S = hs.Split(v, I['views'][v], I['ppl'], params)
    S.pipeline()
    if what == 'truth':
        T = hk.load_truth('charkit/refs/clawd/hair_locks_truth.npz')
        b = S.box
        t = T[0][v][b[0]:b[1], b[2]:b[3]]
        lab = np.where(t >= 0, t + 1, 0)
    else:
        lab = {'regions': S.regions, 'locks': S.locks, 'cells': S.cells, 'tips': S.locks_tips}[what]
    im = pics.colour(lab, S.rgb, 0.55, seed=4)
    im[pics.edges(lab) & S.H] = [0, 0, 0]
    im[S.ink & ~pics.edges(lab)] = (0.5 * im[S.ink & ~pics.edges(lab)]).astype(np.uint8)
    im[S.ext] = [255, 0, 0]
    if hasattr(S, 'seed_masks'):
        for m in S.seed_masks.values():
            im[m] = [255, 255, 255]
    im = Image.fromarray(pics.zoom(im[r0:r1, c0:c1], k))
    d = ImageDraw.Draw(im)
    for i, t in enumerate(S.tip_list, 1):
        r, c = t['rc']
        if r0 <= r < r1 and c0 <= c < c1:
            X, Y = (c - c0) * k, (r - r0) * k
            d.ellipse([X - 6, Y - 6, X + 6, Y + 6], outline=(255, 0, 0), width=2)
            d.text((X + 7, Y - 7), '%d%s' % (i, t['why'][0]), fill=(255, 255, 0))
    for t in S.notch_list:
        r, c = t['rc']
        if r0 <= r < r1 and c0 <= c < c1:
            X, Y = (c - c0) * k, (r - r0) * k
            d.rectangle([X - 4, Y - 4, X + 4, Y + 4], outline=(0, 0, 255), width=2)
    im.save(out)
    print(out)
