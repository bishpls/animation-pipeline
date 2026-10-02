"""The identity map of builds: each build's hair locks z-buffered per view (charkit.hairlocks.build_locks: the QA's
scene), every 3D lock one colour in every view, numbered, over the drawing dimmed; Michael's linked regions (the held-out
truth) outlined. One picture per build, the views side by side, cropped round the hair.

    python tools/hairident/identpic.py OUT_DIR LABEL=BUILD ... [--families side_locks,lower_back]
"""
import json, os, pickle, sys, zlib
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from charkit import hairlocks as hk
import truth as tr

VIEWS = ('front', 'three_quarter', 'profile', 'back')


def colour(name):
    h = zlib.crc32(name.encode())
    import colorsys
    r, g, b = colorsys.hsv_to_rgb((h % 360) / 360.0, 0.75, 0.95)
    return np.array([r, g, b]) * 255


def main(a):
    out = a[0]
    os.makedirs(out, exist_ok=True)
    fams = (a[a.index('--families') + 1] if '--families' in a else 'side_locks,lower_back').split(',')
    builds = [x.split('=', 1) for x in a[1:] if '=' in x]
    I = pickle.load(open(os.path.join(ROOT, 'charkit/out/hairsplit/inputs.pkl'), 'rb'))
    T = tr.load(os.path.join(ROOT, 'charkit/refs/clawd/hair_lock_links.json'))
    for lab, b in builds:
        img, names, ppl = hk.build_locks(b)
        tiles = []
        for v in VIEWS:
            d = I['views'][v]
            hair = d['hair']
            ys, xs = np.nonzero(hair)
            r0, r1, c0, c1 = max(0, ys.min() - 25), ys.max() + 25, max(0, xs.min() - 25), xs.max() + 25
            base = np.clip(d['rgb'], 0, 1) * 255 * 0.45 + 140
            L = img[v]
            for code in np.unique(L[L > 0]):
                nm = names[int(code)]
                if nm.split('/')[0] not in fams:
                    continue
                m = L == code
                base[m] = 0.35 * base[m] + 0.65 * colour(nm.split('/', 1)[1].rsplit('.', 1)[0] + nm.rsplit('.', 1)[-1])
            # the truth's linked regions outlined (each item's region in this view)
            for k, q in T.items():
                m = q['home'][1] if q['home'][0] == v else (q['views'].get(v) if not isinstance(q['views'].get(v), (str, list, type(None))) else None)
                if m is None:
                    continue
                e = m & ~ndimage.binary_erosion(m, iterations=1)
                base[e] = (20, 20, 20)
            im = Image.fromarray(base[r0:r1, c0:c1].astype(np.uint8)).resize(((c1 - c0) * 2, (r1 - r0) * 2), Image.NEAREST)
            dr = ImageDraw.Draw(im)
            for k, q in T.items():
                m = q['home'][1] if q['home'][0] == v else (q['views'].get(v) if not isinstance(q['views'].get(v), (str, list, type(None))) else None)
                if m is None or not m.any():
                    continue
                cy, cx = ndimage.center_of_mass(m)
                dr.text(((cx - c0) * 2 - 4, (cy - r0) * 2 - 6), str(q['number']), fill=(0, 0, 0))
            dr.text((6, 6), '%s %s' % (lab, v), fill=(0, 0, 0))
            tiles.append(im)
        W = sum(t.size[0] for t in tiles) + 8 * 3
        H = max(t.size[1] for t in tiles)
        cv = Image.new('RGB', (W, H), (255, 255, 255))
        x = 0
        for t in tiles:
            cv.paste(t, (x, 0)); x += t.size[0] + 8
        cv.save(os.path.join(out, 'identity_%s.png' % lab))
        print('wrote', os.path.join(out, 'identity_%s.png' % lab), len(names), 'locks')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
