"""The locks drawn, per view, for the review page: the design's hair | each build's locks (z-buffered in the QA's scene,
charkit.hairlocks.build_locks: every lock its own colour, its outline white) | the 52-lock truth (unscored hair dark),
cropped to the hair at one scale; and the lock scores (hairlocks.score) of each build, per view and family.

A build is a folder with bundle/ and geom/hair_pieces/ (a box build; a sweep row's folder gets a `bundle` link to its
base's bundle: the row's pieces z-buffered in the base's scene).

    python tools/hairshell/lockpics.py OUT_DIR LABEL=BUILD [LABEL=BUILD ...] [--k 2]
"""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools/hairsplit'))
from scipy import ndimage
from charkit import hairlocks as hk, hairsplit as hs
import pics

VIEWS = ('front', 'three_quarter', 'profile', 'back')


def colour(lab, base, seed):
    img = pics.colour(lab, base, 0.65, seed=seed)
    img[pics.edges(lab) & (lab > 0)] = [255, 255, 255]
    return img


if __name__ == '__main__':
    a = sys.argv[1:]
    out = a[0]
    k = int(a[a.index('--k') + 1]) if '--k' in a else 2
    builds = [q.split('=', 1) for q in a[1:] if '=' in q and not q.startswith('--')]
    os.makedirs(out, exist_ok=True)
    T = hk.load_truth(os.path.join(ROOT, 'charkit/refs/clawd/hair_locks_truth.npz'))
    import pickle
    I = pickle.load(open(os.path.join(ROOT, 'charkit/out/hairsplit/inputs.pkl'), 'rb'))
    ours, scores = {}, {}
    for label, b in builds:
        img, names, ppl = hk.build_locks(b)
        hair = {v: np.ones(t.shape, bool) for v, t in T[0].items()}
        r = hk.score(img, T, hair, ppl, names)
        ours[label] = img
        scores[label] = {v: dict(lock_iou=r[v]['lock_iou'], families={f: y['lock_iou'] for f, y in
                                                                     r[v].get('families', {}).items()})
                         for v in r}
    json.dump(scores, open(os.path.join(out, 'scores.json'), 'w'), indent=1)
    for v in VIEWS:
        V = I['views'][v]
        hair = V['hair']
        ys, xs = np.nonzero(hair)
        m = int(0.08 * I['ppl'])
        r0, r1, c0, c1 = max(0, ys.min() - m), ys.max() + m, max(0, xs.min() - m), xs.max() + m
        rgb = V['rgb']
        base = (rgb * 255).astype(np.uint8)
        cols = [base]
        caps = ['design']
        for label, img in ours.items():
            cols.append(colour(img[v], rgb, 5))
            s = scores[label].get(v, {})
            caps.append('%s: lock IoU %.3f' % (label, s.get('lock_iou', float('nan'))))
        t = T[0][v]
        tt = np.where(t >= 0, t + 1, 0)
        ti = colour(tt, rgb, 11)
        ti[t == -2] = (0.45 * ti[t == -2]).astype(np.uint8)
        cols.append(ti)
        caps.append('truth (%d locks; unscored dark)' % len(T[1][v]))
        crops = [Image.fromarray(np.ascontiguousarray(c[r0:r1, c0:c1])) for c in cols]
        crops = [c.resize((c.size[0] * k, c.size[1] * k), Image.NEAREST) for c in crops]
        W = sum(c.size[0] for c in crops) + 8 * (len(crops) - 1)
        H = crops[0].size[1] + 22
        canvas = Image.new('RGB', (W, H), (255, 255, 255))
        x = 0
        d = ImageDraw.Draw(canvas)
        for c, cap in zip(crops, caps):
            canvas.paste(c, (x, 22))
            d.text((x + 4, 4), cap, fill=(0, 0, 0))
            x += c.size[0] + 8
        canvas.save(os.path.join(out, 'locks_%s.png' % v))
    print(json.dumps({lb: {v: s[v]['lock_iou'] for v in s} for lb, s in scores.items()}))
