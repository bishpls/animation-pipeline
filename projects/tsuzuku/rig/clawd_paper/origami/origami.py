"""The origami crab and its unfolding into Clawd's puppet (FABLE.md §7: "a crab folded from a single square of clay-orange paper;
her transformation is unfolding, the sheet opening into the jointed puppet, in stop-motion").

    ../../../../../.venv/bin/python origami.py      -> origami.json (morph shapes, fan.json format) + _shapes.png

Shapes share the puppet's master frame (rig/clawd_paper, 2880 px tall): origin at her feet (the floor), +y down.
  ocrab   the folded crab (src crab_2.png, traced; its creases found as straight segments)
  obase   half unfolded: a folded base (a wide kite), its creases radiating from the top
  osquare the flat sheet, its crease pattern showing (diagonals, midlines)
  opuppet the sheet opened into her outline (the figure of src/front.png), creases where she folds (neck, waist, hem, knees)
Each has CREASES creases (straight lines, drawn darker in the gel), matched by order, so they morph line to line.
"""
import json, math, os
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from skimage import measure
from skimage.transform import probabilistic_hough_line

HERE = os.path.dirname(os.path.abspath(__file__)); PUP = os.path.dirname(HERE)
M, NC = 400, 8
FEET = np.array([1076., 2800.])                 # the puppet master's feet (floor) point


def resample(pts, m):
    pts = np.asarray(pts, float); d = np.r_[0, np.cumsum(np.hypot(*np.diff(np.r_[pts, pts[:1]], axis=0).T))]
    s = np.linspace(0, d[-1], m, endpoint=False); P = np.r_[pts, pts[:1]]
    return np.c_[np.interp(s, d, P[:, 0]), np.interp(s, d, P[:, 1])]


def ccw_from(pts, anchor):
    a = 0.5 * np.sum(pts[:, 0] * np.roll(pts[:, 1], -1) - np.roll(pts[:, 0], -1) * pts[:, 1])
    if a > 0: pts = pts[::-1]
    i = int(np.argmin(np.hypot(*(pts - anchor).T))); return np.roll(pts, -i, axis=0)


def outline_of(mask):
    return max(measure.find_contours(np.pad(mask, 2).astype(float), .5), key=len)[:, ::-1] - 2


def order(cr):                                   # creases left to right by midpoint (the matching order)
    return sorted(cr, key=lambda s: ((s[0] + s[2]) / 2, (s[1] + s[3]) / 2))


def crab():
    rgb = np.array(Image.open(os.path.join(HERE, 'crab_2.png')).convert('RGB')).astype(float)
    paper = (rgb.sum(2) < 690); fig = ndi.binary_fill_holes(ndi.binary_closing(paper, iterations=2))
    lab, n = ndi.label(fig); fig = lab == (np.argmax(ndi.sum(fig, lab, range(1, n + 1))) + 1)
    dark = (rgb[..., 0] < 175) & fig & ~ndi.binary_erosion(~fig, iterations=4)
    segs = probabilistic_hough_line(dark, threshold=10, line_length=60, line_gap=6, rng=np.random.default_rng(1))
    segs = sorted(segs, key=lambda s: -math.hypot(s[1][0] - s[0][0], s[1][1] - s[0][1]))
    keep = []
    for (x0, y0), (x1, y1) in segs:                # drop near-duplicates (Hough returns several per drawn line)
        if all(math.hypot((x0 + x1) / 2 - (a + c) / 2, (y0 + y1) / 2 - (b + d) / 2) > 25 for a, b, c, d in keep): keep.append((x0, y0, x1, y1))
        if len(keep) == NC: break
    ys, xs = np.where(fig); sc = 1150 / (xs.max() - xs.min()); base = np.array([(xs.min() + xs.max()) / 2, ys.max()])
    f = lambda p: (np.asarray(p, float) - base) * sc
    o = f(outline_of(fig)); cr = [[*f(s[:2]), *f(s[2:]), 9] for s in keep]
    return o, order(cr)


def base_kite():
    w, h = 1300, 1150                              # a folded base standing on the floor: a wide kite (the sheet half open)
    o = np.array([[0, 0], [w / 2, -h * .42], [0, -h], [-w / 2, -h * .42]], float)
    top, cr = [0, -h], []
    for k in range(NC):                            # creases fanning down from the top point
        t = -w / 2 + w * (k + .5) / NC; cr.append([top[0], top[1], t * .9, -h * .42 + abs(t) * .1, 8])
    return o, order(cr)


def square():
    s = 1900; o = np.array([[-s / 2, 0], [s / 2, 0], [s / 2, -s], [-s / 2, -s]], float); c = [0, -s / 2]
    cr = [[-s / 2, 0, s / 2, -s, 8], [-s / 2, -s, s / 2, 0, 8], [0, 0, 0, -s, 8], [-s / 2, -s / 2, s / 2, -s / 2, 8],
          [-s / 2, -s / 4, s / 2, -s / 4, 6], [-s / 2, -s * .75, s / 2, -s * .75, 6], [-s / 4, 0, -s / 4, -s, 6], [s / 4, 0, s / 4, -s, 6]]
    return o, order(cr)


def puppet():
    rgb = np.array(Image.open(os.path.join(PUP, 'src', 'front.png')).convert('RGB')).astype(float)
    fig = ndi.binary_fill_holes(ndi.binary_closing(rgb.sum(2) < 690, iterations=6))
    f = lambda p: np.asarray(p, float) - FEET
    cr = [[760, 940, 1400, 940, 8], [800, 1330, 1350, 1330, 8], [560, 1940, 1600, 1940, 8], [760, 2160, 1400, 2160, 7],
          [1076, 950, 1076, 1330, 7], [760, 1340, 560, 1920, 7], [1390, 1340, 1600, 1920, 7], [720, 520, 1430, 520, 6]]
    return f(outline_of(fig)), order([[*f(c[:2]), *f(c[2:4]), c[4]] for c in cr])


def main():
    out = {'M': M, 'N': NC, 'shapes': {}}
    for name, (o, cr) in {'ocrab': crab(), 'obase': base_kite(), 'osquare': square(), 'opuppet': puppet()}.items():
        o = ccw_from(resample(o, M), np.array([0., 0.]))
        while len(cr) < NC: m = o.mean(0); cr.append([m[0], m[1], m[0], m[1], 0])
        out['shapes'][name] = {'outline': o.round(1).tolist(), 'slits': [[round(float(v), 1) for v in s] for s in cr[:NC]]}
    json.dump(out, open(os.path.join(HERE, 'origami.json'), 'w'))
    cell = 360; sheet = Image.new('RGB', (cell * 4, cell), 'white'); d = ImageDraw.Draw(sheet)
    for i, (n, S) in enumerate(out['shapes'].items()):
        sc = cell / 3000; T = lambda p: (i * cell + cell / 2 + p[0] * sc, cell * .95 + p[1] * sc)
        d.polygon([T(p) for p in S['outline']], fill=(224, 118, 60))
        for x0, y0, x1, y1, w in S['slits']: d.line([T((x0, y0)), T((x1, y1))], fill=(142, 53, 21), width=2)
        d.text((i * cell + 4, 4), n, fill='black')
    sheet.save(os.path.join(HERE, '_shapes.png')); print('shapes:', list(out['shapes']))


if __name__ == '__main__':
    main()
