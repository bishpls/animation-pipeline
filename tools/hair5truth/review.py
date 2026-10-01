"""Review pictures for the hair-5 truth: per view the body sheet | the lock truth (each lock its own colour in its
family's hue, its name; unscored hatched grey; out of the truth dimmed) | each generated close-up take registered onto
the sheet's grid (refcheck's registration) at the same scale. -> OUT/VIEW.png and OUT/index.html.

    python tools/hair5truth/review.py OUT SCORES.json NAME=SHEET.png:REFCHECK.json ...
"""
import colorsys, json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import ctx5
from charkit import hairlocks as hk

HUE = dict(bangs=0.0, side_locks=0.12, upper_back=0.75, lower_back=0.92, ahoge=0.47, flyaways=0.27)
VIEWS = ('front', 'three_quarter', 'profile', 'back')
ZOOM = 2


def colours(labels):
    out, n = {}, {}
    for q in labels:
        f = hk.family_of(q)
        k = n.get(f, 0); n[f] = k + 1
        h = HUE.get(f, 0.6)
        v = (0.95, 0.72, 0.85, 0.6, 0.8, 0.68, 0.9)[k % 7]
        s = (0.75, 0.9, 0.55, 0.85, 0.65, 0.95, 0.5)[k % 7]
        out[q] = np.array(colorsys.hsv_to_rgb((h + 0.03 * (k % 3)) % 1, s, v))
    return out


def box_of(C, view):
    ys, xs = np.nonzero(C['hair'][view])
    return ys.min() - 8, ys.max() + 8, xs.min() - 8, xs.max() + 8


def truth_panel(C, T, view, box):
    from scipy import ndimage
    rgb = np.asarray(C['dv'][view]['rgb'], float)
    rgb = rgb / 255 if rgb.max() > 1.5 else rgb
    t = T[0][view]
    labels = T[1][view]
    col = colours(labels)
    pic = 0.35 * rgb + 0.65
    for i, q in enumerate(labels):
        m = t == i
        pic[m] = col[q]
        e = m & ~ndimage.binary_erosion(m)
        pic[e] = 0.35 * col[q]
    x = t == -2
    hatch = ((np.indices(t.shape).sum(0) // 3) % 2 == 0)
    pic[x] = 0.75
    pic[x & hatch] = 0.6
    return pic, labels, col


def take_panel(C, view, sheet_rgb, reg):
    """the take's figure onto the grid (nearest), white where it has nothing."""
    g = C['grid'][view]
    H, W = len(g['zs']), len(g['us'])
    I, J = np.mgrid[0:H, 0:W]
    r = np.round((I - reg['di']) / reg['f'] + reg['r0']).astype(int)
    c = np.round((J - reg['dj']) / reg['f'] + reg['c0']).astype(int)
    ok = (r >= 0) & (r < sheet_rgb.shape[0]) & (c >= 0) & (c < sheet_rgb.shape[1])
    out = np.ones((H, W, 3))
    out[ok] = sheet_rgb[r[ok], c[ok]]
    return out


def crop(pic, box):
    from PIL import Image
    r0, r1, c0, c1 = box
    im = Image.fromarray((np.clip(pic[r0:r1, c0:c1], 0, 1) * 255).astype(np.uint8))
    return im.resize((im.size[0] * ZOOM, im.size[1] * ZOOM), Image.NEAREST)


def label(im, text, font):
    from PIL import Image, ImageDraw
    out = Image.new('RGB', (im.size[0], im.size[1] + 22), 'white')
    out.paste(im, (0, 22))
    ImageDraw.Draw(out).text((4, 4), text, fill=(0, 0, 0), font=font)
    return out


def main(out, scores, takes):
    from PIL import Image, ImageDraw, ImageFont
    os.makedirs(out, exist_ok=True)
    C = ctx5.make()
    T = hk.load_truth(os.path.join(ROOT, 'charkit/refs/clawd/hair_locks_truth.npz'))
    S = json.load(open(scores))
    font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 14)
    small = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 11)
    from charkit.hairlayers import load_rgb
    tk = [(n, load_rgb(p), json.load(open(j))) for n, p, j in takes]
    files = {}
    for view in VIEWS:
        box = box_of(C, view)
        rgb = np.asarray(C['dv'][view]['rgb'], float)
        rgb = rgb / 255 if rgb.max() > 1.5 else rgb
        panels = [label(crop(rgb, box), 'body sheet (the authority): %s' % view, font)]
        tp, labels, col = truth_panel(C, T, view, box)
        im = crop(tp, box)
        dr = ImageDraw.Draw(im)
        t = T[0][view]
        for i, q in enumerate(labels):
            ys, xs = np.nonzero(t == i)
            k = np.argmin((ys - ys.mean()) ** 2 + (xs - xs.mean()) ** 2)
            X, Y = (xs[k] - box[2]) * ZOOM, (ys[k] - box[0]) * ZOOM
            nm = q.split('/', 1)[1]
            dr.text((X - 3 * len(nm), Y - 6), nm, fill=(0, 0, 0), font=small)
        fams = {}
        for q in labels:
            fams[hk.family_of(q)] = fams.get(hk.family_of(q), 0) + 1
        panels.append(label(im, 'lock truth: %d locks (%s)' % (len(labels), ', '.join('%s %d' % kv for kv in
                                                                                       sorted(fams.items()))), font))
        for n, srgb, rj in tk:
            if view not in rj['views']:
                continue
            x = rj['views'][view]
            p = take_panel(C, view, srgb, x['registration'])
            sc = S['sets'].get(n, {}).get('table', {}).get(view, {}).get('_all')
            panels.append(label(crop(p, box), '%s: sil IoU %.2f, line F %.2f (floor %.2f), lock IoU %s' % (
                n, x['silhouette']['iou'], x['lines']['F'], x['lines_floor_F'], '-' if sc is None else '%.2f' % sc),
                font))
        w = sum(p.size[0] for p in panels) + 8 * (len(panels) - 1)
        h = max(p.size[1] for p in panels)
        o = Image.new('RGB', (w, h), 'white')
        xo = 0
        for p in panels:
            o.paste(p, (xo, 0)); xo += p.size[0] + 8
        f = os.path.join(out, '%s.png' % view)
        o.save(f)
        files[view] = os.path.basename(f)
        print(f, o.size)
    return files


if __name__ == '__main__':
    a = sys.argv[1:]
    takes = []
    for q in a[2:]:
        n, rest = q.split('=', 1)
        p, j = rest.split(':', 1)
        takes.append((n, p, j))
    main(a[0], a[1], takes)
