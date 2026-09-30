"""Zoomed crops of a view for labelling locks by eye: the sheet alone, and with an overlay (the labeller's lock regions,
or the lock truth's regions with their cuts and seeds), a 10 px grid with 50 px labels.

    python tools/hairlocks/pic.py VIEW OUT.png [--box r0 r1 c0 c1] [--zoom 3] [--what sheet|regions|truth] [--src SRC.json]
"""
import json, os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ctx as cx

RNG = np.random.RandomState(3)
RCOL = RNG.uniform(0.15, 0.95, (4000, 3))


def grid(im, box, zoom, font):
    from PIL import ImageDraw
    r0, r1, c0, c1 = box
    dr = ImageDraw.Draw(im, 'RGBA')
    for x in range((c0 // 10 + 1) * 10, c1, 10):
        X = (x - c0) * zoom
        dr.line([(X, 0), (X, im.size[1])], fill=(0, 90, 255, 60 if x % 50 == 0 else 16))
        if x % 50 == 0:
            dr.text((X + 2, 2), str(x), fill=(0, 60, 220, 255), font=font)
    for y in range((r0 // 10 + 1) * 10, r1, 10):
        Y = (y - r0) * zoom
        dr.line([(0, Y), (im.size[0], Y)], fill=(255, 0, 90, 60 if y % 50 == 0 else 16))
        if y % 50 == 0:
            dr.text((2, Y + 2), str(y), fill=(220, 0, 60, 255), font=font)
    return dr


def picture(C, view, box, zoom=3, what='sheet', src=None, alpha=0.55, labels=None, names=None):
    from PIL import Image, ImageDraw, ImageFont
    from scipy import ndimage
    rgb = np.asarray(C['dv'][view]['rgb'], float)
    rgb = rgb / 255 if rgb.max() > 1.5 else rgb
    pic = rgb.copy()
    if what == 'regions':
        labels = C['regions'][view]
    elif what in ('truth', 'cells'):
        from charkit import hairlayers as hl, hairlocks as hk
        vs = src['views'].get(view, {}) if src else {}
        reg, regions, cut, problems = hl.truth_regions(C['dv'][view], vs, valid=hk.is_label)
        if what == 'truth':
            lab = {}
            for rid, st, _ in regions:
                lab.setdefault(st[0], []).append(rid)
            L = np.zeros(reg.shape, np.int32)
            names = {}
            for k, (q, rids) in enumerate(sorted(lab.items())):
                L[np.isin(reg, rids)] = k + 1
                names[k + 1] = q
            unk = (reg > 0) & (L == 0)
            labels = L
        else:
            labels = reg
        for p_ in problems:
            if 'no seed' not in p_:
                print(p_)
    if labels is not None:
        m = labels > 0
        pic[m] = (1 - alpha) * rgb[m] + alpha * RCOL[labels[m] % len(RCOL)]
        edge = m & (ndimage.grey_dilation(labels, 3) != ndimage.grey_erosion(np.where(m, labels, 10 ** 6), 3))
        pic[edge] = (0, 0, 0)
    if what == 'truth':
        pic[unk] = 0.5 * pic[unk] + 0.5 * np.array([0.6, 0.6, 0.6])
        pic[unk & (((np.indices(unk.shape).sum(0)) // 2) % 2 == 0)] = (0.9, 0.2, 0.2)
    if what in ('truth', 'cells'):
        pic[cut] = (0, 1, 1)
    r0, r1, c0, c1 = box
    crop = pic[r0:r1, c0:c1]
    im = Image.fromarray((np.clip(crop, 0, 1) * 255).astype(np.uint8)).resize(((c1 - c0) * zoom, (r1 - r0) * zoom),
                                                                            Image.NEAREST)
    font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 12)
    dr = grid(im, box, zoom, font)
    if labels is not None:
        for rid in np.unique(labels[r0:r1, c0:c1]):
            if rid <= 0:
                continue
            ys, xs = np.nonzero(labels == rid)
            if len(ys) < 15:
                continue
            k = np.argmin((ys - ys.mean()) ** 2 + (xs - xs.mean()) ** 2)
            y, x = ys[k], xs[k]
            if r0 <= y < r1 and c0 <= x < c1:
                t = names.get(int(rid), str(rid)).split('/')[-1] if names else str(rid)
                dr.text(((x - c0) * zoom - 4, (y - r0) * zoom - 6), t, fill=(0, 0, 0, 255), font=font)
    if what == 'truth':
        for s in src['views'].get(view, {}).get('seeds', []):
            x, y = s[0], s[1]
            X, Y = (x - c0) * zoom, (y - r0) * zoom
            dr.ellipse([X - 3, Y - 3, X + 3, Y + 3], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))
            dr.text((X + 4, Y - 6), s[2], fill=(0, 0, 0, 255), font=font)
    return im


if __name__ == '__main__':
    a = sys.argv[1:]
    view, out = a[0], a[1]
    box = tuple(int(q) for q in a[a.index('--box') + 1:a.index('--box') + 5]) if '--box' in a else None
    zoom = int(a[a.index('--zoom') + 1]) if '--zoom' in a else 3
    what = a[a.index('--what') + 1] if '--what' in a else 'sheet'
    src = json.load(open(a[a.index('--src') + 1])) if '--src' in a else None
    C = cx.make()
    if box is None:
        ys, xs = np.nonzero(C['hair'][view])
        box = (ys.min() - 10, ys.max() + 10, xs.min() - 10, xs.max() + 10)
    picture(C, view, box, zoom, what, src).save(out)
    print(out, box)
