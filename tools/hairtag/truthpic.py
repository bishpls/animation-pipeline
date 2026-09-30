"""The hair truth's annotation picture, for writing and checking its source: a view's crop at a zoom, each region in its
family's colour (a set striped with its second label), the cuts cyan, the seeds as dots, regions without a seed red.

    python tools/hairtag/truthpic.py SRC.json VIEW OUT.png [--zoom 3] [--box r0 r1 c0 c1] [--dv PICKLE]
"""
import json, os, pickle, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from charkit import hairlayers as hl

COL = dict(bangs=(.85, .2, .2), side_locks=(1, .8, .2), upper_back=(.55, .3, .9), lower_back=(1, .5, .7),
           buns=(.2, .4, 1), bun_L=(.2, .4, 1), bun_R=(.35, .75, 1), ahoge=(.1, .8, .7), flyaways=(.5, .9, .1),
           none=(.45, .45, .45))


def picture(dv, src, zoom=3, box=None, label_ids=False):
    from PIL import Image, ImageDraw, ImageFont
    reg, regions, cut, problems = hl.truth_regions(dv, src)
    rgb = np.asarray(dv['rgb'])
    if box is None:
        ys, xs = np.nonzero(reg > 0)
        box = (max(0, ys.min() - 12), ys.max() + 12, max(0, xs.min() - 12), xs.max() + 12)
    r0, r1, c0, c1 = box
    pic = rgb.copy() * 0.5 + 0.5
    yy, xx = np.mgrid[0:rgb.shape[0], 0:rgb.shape[1]]
    stripe = ((yy + xx) // 3) % 2 == 0
    known = set()
    for rid, st, _ in regions:
        m = reg == rid
        known.add(rid)
        pic[m] = 0.35 * rgb[m] + 0.65 * np.array(COL[st[0]])
        if len(st) > 1:
            m2 = m & stripe
            pic[m2] = 0.35 * rgb[m2] + 0.65 * np.array(COL[st[1]])
    unk = (reg > 0) & ~np.isin(reg, list(known))
    pic[unk] = (1, 0, 0)
    pic[cut] = (0, 1, 1)
    crop = pic[r0:r1, c0:c1]
    im = Image.fromarray((np.clip(crop, 0, 1) * 255).astype(np.uint8)).resize(((c1 - c0) * zoom, (r1 - r0) * zoom),
                                                                            Image.NEAREST)
    dr = ImageDraw.Draw(im, 'RGBA')
    font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 13)
    for x in range((c0 // 10 + 1) * 10, c1, 10):
        X = (x - c0) * zoom
        dr.line([(X, 0), (X, im.size[1])], fill=(0, 90, 255, 110 if x % 50 == 0 else 35))
        if x % 50 == 0:
            dr.text((X + 2, 2), str(x), fill=(0, 60, 220, 255), font=font)
    for y in range((r0 // 10 + 1) * 10, r1, 10):
        Y = (y - r0) * zoom
        dr.line([(0, Y), (im.size[0], Y)], fill=(255, 0, 90, 110 if y % 50 == 0 else 35))
        if y % 50 == 0:
            dr.text((2, Y + 2), str(y), fill=(220, 0, 60, 255), font=font)
    for x, y, s in src.get('seeds', []):
        X, Y = (x - c0) * zoom, (y - r0) * zoom
        dr.ellipse([X - 3, Y - 3, X + 3, Y + 3], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))
    if label_ids:
        for rid in np.unique(reg[unk]):
            ys, xs = np.nonzero(reg == rid)
            dr.text(((xs.mean() - c0) * zoom, (ys.mean() - r0) * zoom), str(rid), fill=(0, 0, 0, 255), font=font)
    return im, problems, regions


if __name__ == '__main__':
    a = sys.argv[1:]
    src = json.load(open(a[0]))
    view, out = a[1], a[2]
    zoom = int(a[a.index('--zoom') + 1]) if '--zoom' in a else 3
    box = tuple(int(q) for q in a[a.index('--box') + 1:a.index('--box') + 5]) if '--box' in a else None
    if '--dv' in a:
        dv = pickle.load(open(a[a.index('--dv') + 1], 'rb'))['dv'][view]
    else:
        spec = json.load(open(os.path.join(ROOT, 'charkit/spec/clawd.json')))
        from charkit import manifest
        dv = hl.design(manifest.resolve(spec))[0][view]
    im, problems, regions = picture(dv, src['views'][view], zoom, box, label_ids=True)
    im.save(out)
    print('%d regions; %d problems' % (len(regions), len(problems)))
    for p in problems:
        print('  ' + p)
