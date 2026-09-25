"""The fan and every noun it becomes, as morphable cut-paper shapes (Fable: one black shape, its rib slits constant in number,
the ribs becoming legs, ticks, feathers, pages).

    ../../../../../.venv/bin/python fan.py        -> fan.json  {shapes: {name: {outline: [[x, y] x M], slits: [[x0, y0, x1, y1, w] x N]}}}
                                                     + _shapes.png (review)

All shapes share one frame: master px, origin = the grip (the fan's pivot in her fist), +y down, the shape standing above it.
Outlines are resampled to M points by arc length, counter-clockwise, starting at the point nearest the grip, so any two
shapes morph point to point. Slits are N centrelines (+ width), ordered left to right; a shape with fewer drawn slits gets
designed ones (DESIGN), so the count never changes.
Procedural: fan_closed, fan_open (six blades, five gaps), line (the fan closed and laid flat: a ruled line with five ticks).
Drawn (GPT Image, src/): the nouns, cut and traced here.
"""
import json, math, os
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from skimage import measure

HERE = os.path.dirname(os.path.abspath(__file__))
M, N = 400, 5
SIZE = 780                                        # a noun's longest side, master px (the closed fan is ~470 long)
TAKES = {'crab': 'crab_2', 'wings': 'wings_1', 'falling': 'falling_2', 'fox': 'fox_1', 'crow': 'crow_1', 'boy': 'boy_1', 'book': 'book_1'}
# designed slits, in source-image px [x0, y0, x1, y1, w] (for drawings whose feathers/pages are notches, not holes)
DESIGN = {
    # along the drawn feather lines (which open to the edge and trace away), set in from the edge; one at the wing joint
    'wings': [[128, 322, 236, 432, 7], [70, 432, 216, 503, 7], [896, 322, 788, 432, 7], [954, 432, 808, 503, 7], [512, 668, 512, 748, 6]],
    'book': [[210, 330, 360, 250, 6], [215, 420, 380, 330, 6], [640, 250, 800, 330, 6], [650, 330, 810, 420, 6], [512, 300, 512, 760, 5]],
    # the feathered arms and the streaming cloth
    'falling': [[462, 390, 528, 520, 6], [486, 372, 552, 500, 6], [742, 480, 756, 596, 6], [763, 486, 781, 600, 6], [590, 705, 690, 752, 6]],
}


def resample(pts, m):
    pts = np.asarray(pts, float); d = np.r_[0, np.cumsum(np.hypot(*np.diff(np.r_[pts, pts[:1]], axis=0).T))]
    s = np.linspace(0, d[-1], m, endpoint=False); P = np.r_[pts, pts[:1]]
    return np.c_[np.interp(s, d, P[:, 0]), np.interp(s, d, P[:, 1])]


def ccw_from(pts, anchor):
    a = 0.5 * np.sum(pts[:, 0] * np.roll(pts[:, 1], -1) - np.roll(pts[:, 0], -1) * pts[:, 1])
    if a > 0: pts = pts[::-1]                       # image coords (+y down): negative area = counter-clockwise on screen
    i = int(np.argmin(np.hypot(*(pts - anchor).T))); return np.roll(pts, -i, axis=0)


def traced(name):
    im = np.array(Image.open(os.path.join(HERE, 'src', TAKES[name] + '.png')).convert('L')) < 128
    im = ndi.binary_closing(im, iterations=3 if name != 'book' else 9)                # join near-touching pieces
    lab, n = ndi.label(im); sz = ndi.sum(im, lab, range(1, n + 1)); body = lab == (np.argmax(sz) + 1)
    fig = ndi.binary_fill_holes(body); holes = fig & ~body
    c = max(measure.find_contours(np.pad(fig, 2).astype(float), .5), key=len)[:, ::-1] - 2
    slits = []
    hl, nh = ndi.label(holes)
    for k in range(1, nh + 1):
        ys, xs = np.where(hl == k)
        if len(xs) < 60: continue
        P = np.c_[xs, ys].astype(float); mu = P.mean(0); U, S, Vt = np.linalg.svd(P - mu, full_matrices=False); d = Vt[0]
        t = (P - mu) @ d; L = t.max() - t.min(); w = max(4., len(xs) / max(L, 1))
        slits.append([*(mu + d * t.min()), *(mu + d * t.max()), w, L])
    slits = sorted(slits, key=lambda s: -s[5])[:N]
    slits = [s[:5] for s in slits] + DESIGN.get(name, [])[:max(0, N - len(slits))]
    ys, xs = np.where(fig); x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    anchor = np.array([(x0 + x1) / 2, y1]); sc = SIZE / max(x1 - x0, y1 - y0)
    return c, slits, anchor, sc


def fan(spread, R=470, r0=36, blades=6, stagger=0.0):
    """Six blades radiating from the pivot (origin) about 'up', total spread in degrees; the gaps between blades are the slits."""
    a0, pts = -spread / 2, []
    edges = [a0 + spread * i / blades for i in range(blades + 1)]
    for i in range(blades):                                   # the outer edge: each blade tip a straight chord (staggered when closed)
        rr = R * (1 - stagger * ((i * 37) % 5) / 5)
        for a in (edges[i], edges[i + 1]):
            t = math.radians(a); pts.append([rr * math.sin(t), -rr * math.cos(t)])
    for k in range(9):                                        # the pivot end, round
        t = math.radians(edges[-1] + (180 + spread) * 0 + k * (360 - spread) / 8); pts.append([r0 * math.sin(t), -r0 * math.cos(t)])
    slits = []
    for i in range(1, blades):
        t = math.radians(edges[i]); s, c = math.sin(t), -math.cos(t)
        slits.append([s * R * .3, c * R * .3, s * R * .97, c * R * .97, 7 if spread > 40 else 5])
    return np.array(pts), slits


def ruled(L=700, h=30):
    """The fan closed and laid flat: a long bar standing up from the grip like the closed fan (so the fan -> line in-betweens
    stay thin); the runtime lays it level by rotating the prop. Five tick slits across it."""
    pts = np.array([[-h / 2, 30], [-h / 2, -L], [h / 2, -L], [h / 2, 30]], float)
    return pts, [[-h * .38, -L * (i + 1) / 6, h * .38, -L * (i + 1) / 6, 6] for i in range(N)]


def main():
    out = {'M': M, 'N': N, 'shapes': {}}
    for name, (pts, slits) in {'fan_closed': fan(16, stagger=.05), 'fan_open': fan(150), 'line': ruled()}.items():
        o = ccw_from(resample(pts, M), np.array([0., 0.]))
        out['shapes'][name] = {'outline': o.round(1).tolist(), 'slits': sorted(slits, key=lambda s: (s[0] + s[2]) / 2)}
    for name in TAKES:
        c, slits, anchor, sc = traced(name)
        f = lambda p: ((np.asarray(p, float) - anchor) * sc)
        o = ccw_from(resample(f(c), M), np.array([0., 0.]))
        sl = [[*f(s[:2]), *f(s[2:4]), max(4, s[4] * sc)] for s in slits]
        while len(sl) < N: m = o.mean(0); sl.append([m[0], m[1], m[0], m[1], 0])        # a collapsed slit (never seen)
        out['shapes'][name] = {'outline': o.round(1).tolist(), 'slits': [[round(v, 1) for v in s] for s in sorted(sl, key=lambda s: (s[0] + s[2]) / 2)]}
    json.dump(out, open(os.path.join(HERE, 'fan.json'), 'w'))
    # review: every shape, slits cut, the grip marked
    names = list(out['shapes']); cell = 300; sheet = Image.new('RGB', (cell * len(names), cell + 20), 'white'); d = ImageDraw.Draw(sheet)
    for i, n in enumerate(names):
        S = out['shapes'][n]; sc2 = cell / 900; ox, oy = i * cell + cell / 2, cell * .85
        T = lambda p: (ox + p[0] * sc2, oy + p[1] * sc2)
        d.polygon([T(p) for p in S['outline']], fill='black')
        for x0, y0, x1, y1, w in S['slits']: d.line([T((x0, y0)), T((x1, y1))], fill='white', width=max(1, int(w * sc2)))
        d.ellipse([ox - 3, oy - 3, ox + 3, oy + 3], fill='red'); d.text((i * cell + 4, cell + 4), n, fill='black')
    sheet.save(os.path.join(HERE, '_shapes.png'))
    print('shapes:', names)


if __name__ == '__main__':
    main()
