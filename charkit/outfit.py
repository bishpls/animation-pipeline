"""Outfit intake (docs/CHARKIT.md §8): a character's references into an outfit component graph, so layered and flowy
attire becomes separately built, rigged and measured pieces. Pure numpy/scipy (PIL for pictures); no Blender, no paid API.

Sources, combined and cross-checked:
  rig        the 2D rig's named layers (front, precise). Each pixel of the front belongs to the top-most layer drawn there;
             a layer's pixels split by colour family into its piece and sub-pieces by rules on their shape: a colour that
             runs the piece's length is a panel (the skirt's cream front panel), a band at its top edge standing proud of
             it is a cuff (a boot's turned-down top), a band along an edge is a trim (the stepped hem), parts hanging free
             from the rest are tails (the bow's), two far-apart halves with nothing of the layer between them are a mirror
             pair (the back panels).
  sheet      the model sheet's four figures (front, 3/4, profile, back), each segmented by colour family into cells
             (the drawn lines as walls) and each cell matched to a piece by colour, position and what the 3D field
             predicts there (below), or by landmarks (heights from the eye line) without a field.
  field      the TRELLIS.2 field (surface voxels with colour, trellis_ext/field.py): aligned to the rig's front and to each
             sheet figure by silhouette, labelled by a colour-aware geodesic competition seeded from the rig's pieces,
             projected into each view (the prediction), then relabelled by the sheet's own masks voting in every view
             where a voxel shows. Each piece gets a 3D extent and its coverage round the body.
  notes      an annotated vision pass (refs/NAME/outfit_notes.json): piece names, types, attachments and motion read off
             the sheet by eye, versioned with provenance. Every annotated piece is verified against the measurement and
             every disagreement is flagged.

Per piece: id, type, side (L = her left, R, C) and mirror pair, attach (bone, parent piece, contacts), layer order (over /
under), colour (sRGB from the drawing), extent per view (bbox and outline in head lengths L from the eye line; x to the
image's right), 3D extent, motion (rigid / spring / cloth, with the measured reason), trims, the template it maps to with
first knob guesses, and spring-chain specs for the VRM exporter.

    python -m charkit outfit SPEC [--out DIR] [--field FIELD.npz] [--no-field] [--no-manifest]
    python -m charkit outfit relayer [SPEC]      # the notes' layer order and chain bone names applied to the graphs
    from charkit import outfit; G = outfit.build(spec)
"""
import json, math, os
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION = 1
VIEWS = ('front', 'three_quarter', 'profile', 'back')
AZ = {'front': 0.0, 'three_quarter': 35.0, 'profile': 90.0, 'back': 180.0}     # 3/4 is re-measured per sheet
W_LAB = np.array([0.4, 1.0, 1.0])            # lightness down-weighted: a fold's shadow stays in its colour family
FAMILY_DE = 12.0                              # colours closer than this (weighted Lab) are one family
LINE_V = 0.3                                  # darker than this and thin: a drawn line

# a layer name's words -> piece type ('' = body: hair, skin, face features). First match wins.
VOCAB = [('skirt_back', 'overskirt panel'), ('overskirt', 'overskirt panel'), ('skirt', 'skirt'),
         ('bodice', 'top'), ('blouse', 'top'), ('shirt', 'top'), ('jacket', 'top'), ('vest', 'top'), ('top', 'top'),
         ('waistband', 'waistband'), ('belt', 'waistband'), ('sash', 'ribbon'), ('shorts', 'shorts'),
         ('pants', 'trousers'), ('tights', 'tights'), ('sock', 'sock'), ('sleeve', 'sleeve'), ('trim', 'sleeve cuff'),
         ('cuff', 'cuff'), ('glove', 'glove'), ('collar', 'collar'), ('bow', 'bow'), ('ribbon', 'ribbon'),
         ('tie', 'ribbon'), ('boot', 'boot'), ('shoe', 'shoe'), ('bun', 'hair accessory'), ('pin', 'hair accessory'),
         ('clip', 'hair accessory'), ('hat', 'hat'), ('cape', 'cape'),
         ('hair', ''), ('ahoge', ''), ('face', ''), ('eye', ''), ('brow', ''), ('mouth', ''), ('nose', ''),
         ('neck', ''), ('chest', ''), ('arm', ''), ('hand', ''), ('leg', ''), ('foot', ''), ('ear', '')]
HAIR_WORDS = ('hair', 'ahoge')


# -------------------------------------------------------------------------------------------------------------- colour
def lab(rgb):
    """sRGB 0..1 (..., 3) -> CIELAB (D65)."""
    c = np.asarray(rgb, np.float64)
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750], [0.0193339, 0.1191920, 0.9503041]])
    xyz = c @ M.T / np.array([0.95047, 1.0, 1.08883])
    e = 6 / 29
    f = np.where(xyz > e ** 3, np.cbrt(np.maximum(xyz, 0)), xyz / (3 * e * e) + 4 / 29)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def de(a, b):
    """weighted Lab distance between rows of a (n,3) and b (m,3) -> (n, m)."""
    return np.sqrt((((np.asarray(a)[:, None] - np.asarray(b)[None]) * W_LAB) ** 2).sum(-1))


def colour_name(rgb):
    """a plain name for an sRGB colour (0..1): white, cream, dark, orange, red, yellow, ..."""
    r, g, b = (float(x) for x in rgb)
    mx, mn = max(r, g, b), min(r, g, b)
    s = 0 if mx == 0 else (mx - mn) / mx
    if mx < 0.45:
        return 'dark'
    if s < 0.12:
        return 'white' if mx > 0.85 else 'grey'
    h = 0.0
    if mx != mn:
        if mx == r:
            h = (60 * (g - b) / (mx - mn)) % 360
        elif mx == g:
            h = 60 * (b - r) / (mx - mn) + 120
        else:
            h = 60 * (r - g) / (mx - mn) + 240
    if s < 0.32 and mx > 0.85 and 15 <= h < 70:
        return 'cream' if h >= 38 else 'skin'
    for lim, name in ((10, 'red'), (30, 'orange'), (42, 'amber'), (70, 'yellow'), (160, 'green'), (200, 'teal'),
                      (255, 'blue'), (290, 'purple'), (340, 'pink'), (361, 'red')):
        if h < lim:
            return name
    return 'red'


def kmeans(X, k, iters=25, seed=0, sample=60000):
    """Lloyd's k-means, k-means++ seeding on a fixed sample (deterministic). -> (labels, centres)."""
    rng = np.random.default_rng(seed)
    S = X[rng.choice(len(X), min(sample, len(X)), replace=False)] if len(X) > sample else X
    k = min(k, len(S))
    C = [S[0]]
    d2 = ((S - C[0]) ** 2).sum(1)
    for _ in range(1, k):
        if d2.sum() <= 0:
            break
        C.append(S[rng.choice(len(S), p=d2 / d2.sum())])
        d2 = np.minimum(d2, ((S - C[-1]) ** 2).sum(1))
    C = np.array(C)
    for _ in range(iters):
        lb = ((S[:, None] - C[None]) ** 2).sum(2).argmin(1)
        new = np.array([S[lb == j].mean(0) if (lb == j).any() else C[j] for j in range(len(C))])
        if np.allclose(new, C, atol=1e-4):
            break
        C = new
    return ((X[:, None] - C[None]) ** 2).sum(2).argmin(1), C


def lines(rgb, r, black=0.0):
    """the drawn lines: dark pixels in strokes thinner than 2r (thick dark regions are a dark colour family), and
    anything darker than `black` (ink)."""
    from scipy import ndimage
    v = np.asarray(rgb).max(-1)
    dark = v < LINE_V
    return (dark & ~ndimage.binary_opening(dark, _disk(r))) | (v < black)


def _disk(r):
    r = max(1, int(round(r)))
    y, x = np.mgrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r + r


def _same_family(a, b):
    """two Lab colours are one family: close (weighted), and when both are coloured, of one hue and similar chroma (a
    fold's shadow is darker, not another hue; cream and skin are close in Lab but not in hue)."""
    if float(de(a[None], b[None])[0, 0]) > FAMILY_DE:
        return False
    ca, cb = math.hypot(a[1], a[2]), math.hypot(b[1], b[2])
    if max(ca, cb) <= 12:
        return True
    if min(ca, cb) < 0.5 * max(ca, cb):
        return False
    dh = abs(math.degrees(math.atan2(a[2], a[1]) - math.atan2(b[2], b[1]))) % 360
    return min(dh, 360 - dh) <= 20


def families_from(samples, body=None, min_frac=0.03, k=4):
    """colour families from pieces' pixels: samples {key: (n,3) sRGB}; each key's k-means colours (tones) holding
    min_frac of it, merged across keys when _same_family with a family's nearest tone. body: {'skin': (n,3), 'hair':
    (n,3)} seed families of their own (a garment colour matching one joins it: position then tells them apart).
    -> list of dict(name, rgb (the main tone), lab, tones (Lab list), n, keys, body)."""
    cand = []
    for key in sorted(samples):
        c = np.asarray(samples[key], np.float64)
        if len(c) < 20:
            continue
        lb, C = kmeans(lab(c) * W_LAB, k)
        for j in range(len(C)):
            m = lb == j
            if m.sum() >= min_frac * len(c):
                cand.append((int(m.sum()), key, np.median(c[m], 0)))
    fams = []
    for name, c in sorted((body or {}).items()):
        c = np.asarray(c, np.float64)
        if len(c):
            rgb = np.median(c, 0)
            f = dict(rgb=rgb, lab=lab(rgb), tones=[lab(rgb)], tone_n=[len(c)], n=len(c), keys=[], body=name)
            lb, C = kmeans(lab(c) * W_LAB, k + 1)                   # its shading tones (lit, shade, deep)
            for j in range(len(C)):
                m = lb == j
                if m.sum() >= 0.05 * len(c) and np.median(c[m], 0).max() >= LINE_V:
                    f['tones'].append(lab(np.median(c[m], 0))); f['tone_n'].append(int(m.sum()))
            fams.append(f)
    for n, key, rgb in sorted(cand, key=lambda t: (-t[0], t[1])):
        L = lab(rgb)
        best, bd = None, np.inf
        for j, f in enumerate(fams):
            for T in f['tones']:
                d = float(de(L[None], T[None])[0, 0])
                if d < bd and _same_family(L, T):
                    best, bd = j, d
        if best is None:
            fams.append(dict(rgb=rgb, lab=L, tones=[L], tone_n=[n], n=n, keys=[key], body=None))
            continue
        f = fams[best]
        f['n'] += n
        if key not in f['keys']:
            f['keys'].append(key)
        if bd > 4:
            f['tones'].append(L); f['tone_n'].append(n)
    names = {}
    for f in fams:
        nm = colour_name(f['rgb'])
        names[nm] = names.get(nm, 0) + 1
        f['name'] = nm if names[nm] == 1 else '%s%d' % (nm, names[nm])
    return fams


def classify(rgb, fams, line=None, paper=None, max_de=30.0):
    """per pixel: the index of the family with the nearest tone (-1 nothing: paper, or too far from every family; -2 a
    line). Each distinct 8-bit colour is classified once."""
    H, W = rgb.shape[:2]
    q = np.clip(np.round(np.asarray(rgb).reshape(-1, 3) * 255), 0, 255).astype(np.int64)
    u, inv = np.unique((q[:, 0] << 16) | (q[:, 1] << 8) | q[:, 2], return_inverse=True)
    L = lab(np.stack([(u >> 16) & 255, (u >> 8) & 255, u & 255], 1) / 255.0)
    C = np.array([T for f in fams for T in f.get('tones', [f['lab']])])
    owner = np.array([j for j, f in enumerate(fams) for _ in f.get('tones', [f['lab']])])
    d = np.full((len(L), len(fams)), np.inf)
    for i0 in range(0, len(L), 200000):
        dd = np.sqrt((((L[i0:i0 + 200000, None] - C[None]) * W_LAB) ** 2).sum(-1))
        for j in range(len(fams)):
            d[i0:i0 + 200000, j] = dd[:, owner == j].min(1)
    res = d.argmin(1)
    res[d.min(1) > max_de] = -1
    if paper is not None:
        dp = np.sqrt(((L - lab(np.asarray(paper, float))) ** 2).sum(-1))
        res[dp < np.minimum(d.min(1), 3.5)] = -1
    out = res[inv.ravel()].reshape(H, W)
    if line is not None:
        out[line] = -2
    return out


# ---------------------------------------------------------------------------------------------------------------- the rig
def load_rig(rig_dir):
    """a 2D rig (tools/rigbuild.py's build/): each front pixel's top-most layer. -> dict(own (H,W) layer index or -1, rgb,
    names, size, order (drawing order, back to front), rig (rig.json or {}))."""
    from PIL import Image
    d = rig_dir if os.path.isabs(rig_dir) else os.path.join(ROOT, rig_dir)
    M = json.load(open(os.path.join(d, 'build', 'manifest.json')))
    W, H = M['size']
    own = np.full((H, W), -1, np.int16)
    rgb = np.zeros((H, W, 3), np.float32)
    names, alpha = [], {}
    for i, l in enumerate(M['layers']):                              # the manifest lists layers back to front
        a = np.asarray(Image.open(os.path.join(d, 'build', l['name'] + '.png')).convert('RGBA'), np.float32) / 255
        x, y = l['x'], l['y']
        h, w = min(a.shape[0], H - y), min(a.shape[1], W - x)
        a = a[:h, :w]
        sub = a[..., 3] > 0.5
        own[y:y + h, x:x + w][sub] = i
        rgb[y:y + h, x:x + w][sub] = a[..., :3][sub]
        names.append(l['name'])
        alpha[l['name']] = Mask(y0=y, x0=x, m=sub)                   # the whole layer, parts hidden under others too
    rj = os.path.join(d, 'rig.json')
    return dict(own=own, rgb=rgb, names=names, size=(W, H), rig=json.load(open(rj)) if os.path.exists(rj) else {},
                dir=d, layers={l['name']: l for l in M['layers']}, alpha=alpha)


def layer_type(name):
    n = name.lower()
    for w, t in VOCAB:
        if w in n.split('_') or n.startswith(w):
            return t
    return None                                                      # unknown: decided by its colour


def rig_frame(R, eye_x=0.168):
    """the rig's head-length frame and 2D skeleton. The scale from the eye layers' spacing (2 * eye_x L), the origin on
    their centre: x_L = (px - ex) / ppl (image right = her left), z_L = (ey - py) / ppl. The skeleton (VRM bone ->
    ((x, z), (x, z)) head to tail in L) from rig.json's joints (arms' shoulder and elbow, the waist, hip, legs' tops,
    ankle and sole, the neck), the wrists and knees placed between; image-left in the rig is her right."""
    Ls = R['layers']
    ec = [(Ls[n]['x'] + Ls[n]['w'] / 2, Ls[n]['y'] + Ls[n]['h'] / 2) for n in ('eye_L', 'eye_R')]
    ex, ey = (ec[0][0] + ec[1][0]) / 2, (ec[0][1] + ec[1][1]) / 2
    ppl = abs(ec[1][0] - ec[0][0]) / (2 * eye_x)
    F = dict(ppl=ppl, eye=(ex, ey))
    to = lambda p: (round((p[0] - ex) / ppl, 4), round((ey - p[1]) / ppl, 4))
    rj = R.get('rig') or {}
    sk = {}
    try:
        hd, bd, pv, ar = rj['head'], rj['body'], rj['body']['pelvis'], rj['arms']
        cx = bd.get('bodyX', {}).get('cx', ex)
        top_y = min(l['y'] for l in Ls.values())
        nt, nb = hd['neck']['top'], hd['neck']['base']
        chest_y = bd.get('breath', {}).get('chestY', (nb + bd['waist'][1]) / 2)
        sk['head'] = (to((cx, nt)), to((cx, top_y)))
        sk['neck'] = (to((cx, nb)), to((cx, nt)))
        sk['upperChest'] = (to((cx, chest_y)), to((cx, nb)))
        sk['chest'] = (to((cx, bd['waist'][1])), to((cx, chest_y)))
        sk['spine'] = (to((cx, (bd['waist'][1] + bd['hip'][1]) / 2)), to((cx, bd['waist'][1])))
        sk['hips'] = (to((cx, pv['legs'][next(iter(pv['legs']))]['top'][1])), to((cx, (bd['waist'][1] + bd['hip'][1]) / 2)))
        for img, side in (('L', 'right'), ('R', 'left')):              # the rig's image-left arm is her right
            a = ar[img]
            sh, el = np.array(a['shoulder'], float), np.array(a['elbow'], float)
            wr = el + (el - sh)
            hand = R.get('alpha', {}).get('hand_' + img)
            if hand is not None and hand.area:                    # the wrist: where the hand's drawing starts
                hy, hx = hand.pixels()
                dvec = (el - sh) / np.linalg.norm(el - sh)
                tt = (np.stack([hx, hy], 1) - el) @ dvec
                wr = el + dvec * float(np.percentile(tt, 3))
            hand = wr + (el - sh) * 0.55
            sk[side + 'Shoulder'] = (to((cx, nb + 0.3 * (sh[1] - nb))), to(sh))
            sk[side + 'UpperArm'] = (to(sh), to(el))
            sk[side + 'LowerArm'] = (to(el), to(wr))
            sk[side + 'Hand'] = (to(wr), to(hand))
            leg = pv['legs'].get('leg_' + img)
            if leg:
                top = np.array(leg['top'], float)
                ank = np.array([top[0], pv.get('ankleJ', pv.get('ankle'))], float)
                boot = Ls.get('boot_' + img)
                if boot:
                    ank[0] = boot['x'] + boot['w'] / 2
                knee = (top + ank) / 2
                sole = np.array([ank[0], pv.get('sole', ank[1] + 0.6 * ppl)], float)
                sk[side + 'UpperLeg'] = (to(top), to(knee))
                sk[side + 'LowerLeg'] = (to(knee), to(ank))
                sk[side + 'Foot'] = (to(ank), to(sole))
    except (KeyError, TypeError, StopIteration):
        pass
    F['skeleton'] = sk
    return F


def to_L(F, px, py):
    return (np.asarray(px, float) - F['eye'][0]) / F['ppl'], (F['eye'][1] - np.asarray(py, float)) / F['ppl']


def nearest_bone(sk, x, z, bones=None):
    """the 2D skeleton's bone nearest a point (L) -> (bone, t along it 0..1, distance L)."""
    best = (None, 0.0, np.inf)
    for b, (h, t) in sk.items():
        if bones and b not in bones:
            continue
        h, t = np.array(h), np.array(t)
        d = t - h
        ln2 = max(1e-9, d @ d)
        u = float(np.clip((np.array([x, z]) - h) @ d / ln2, 0, 1))
        dist = float(np.linalg.norm(h + u * d - np.array([x, z])))
        tt = float((np.array([x, z]) - h) @ d / ln2)
        if dist < best[2] - 1e-9:
            best = (b, tt, dist)
    return best


# ------------------------------------------------------------------------------------------------------------ rig pieces
class Mask:
    """a boolean mask kept as its bounding box: y0, x0, m (h, w)."""
    __slots__ = ('y0', 'x0', 'm')

    def __init__(self, full=None, y0=0, x0=0, m=None):
        if full is not None:
            ys, xs = np.nonzero(full)
            if len(ys) == 0:
                self.y0, self.x0, self.m = 0, 0, np.zeros((0, 0), bool)
                return
            y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
            m = full[y0:y1, x0:x1]
        self.y0, self.x0, self.m = int(y0), int(x0), np.asarray(m, bool)

    def full(self, shape):
        out = np.zeros(shape, bool)
        h, w = self.m.shape
        out[self.y0:self.y0 + h, self.x0:self.x0 + w] = self.m
        return out

    def pixels(self):
        ys, xs = np.nonzero(self.m)
        return ys + self.y0, xs + self.x0

    @property
    def area(self):
        return int(self.m.sum())

    def box(self):
        """(x0, y0, x1, y1) exclusive, of the set pixels."""
        ys, xs = np.nonzero(self.m)
        if not len(ys):
            return None
        return (int(xs.min() + self.x0), int(ys.min() + self.y0), int(xs.max() + 1 + self.x0), int(ys.max() + 1 + self.y0))


def _label(m, conn=1):
    from scipy import ndimage
    st = ndimage.generate_binary_structure(2, conn)
    return ndimage.label(m, st)


def _row_width(m):
    """per row of a mask: the count of set pixels."""
    return m.sum(1)


def _steps(boundary, tol, run):
    """a boundary profile (NaN where absent) as stair steps: its local slope (over run / 2 columns, after a 5-wide
    median) sorts columns into treads (under 42 degrees) and risers (over 54 degrees); a step is a riser between two
    treads at least `run` long, rising more than tol. Stair-stepped hems (even slanted ones) are mostly steps; curves,
    slants and soles have none or one. -> (steps, share of the profile's whole rise and fall in them)."""
    from scipy.ndimage import median_filter
    b = np.asarray(boundary, float)
    idx = np.nonzero(np.isfinite(b))[0]
    if not len(idx):
        return 0, 0.0
    steps, big, tot = 0, 0.0, 0.0
    w = max(2, run // 2)
    for r in np.split(idx, np.nonzero(np.diff(idx) > 1)[0] + 1):
        if len(r) < 2 * run + w:
            continue
        v = median_filter(b[r], 5, mode='nearest')
        tot += np.abs(np.diff(v)).sum()
        sl = np.abs(v[w:] - v[:-w]) / w
        kind = np.where(sl > 1.4, 2, np.where(sl < 0.9, 1, 0))
        runs = []                                                    # [kind, start, length], in-between columns dropped
        for i, k in enumerate(kind):
            if k == 0:
                continue
            if runs and runs[-1][0] == k:
                runs[-1][2] = i - runs[-1][1] + 1
            else:
                runs.append([int(k), i, 1])
        for a, m, c in zip(runs, runs[1:], runs[2:]):
            if a[0] == 1 and m[0] == 2 and c[0] == 1 and a[2] >= run and c[2] >= run:
                rise = abs(v[min(len(v) - 1, c[1] + w // 2)] - v[max(0, a[1] + a[2] - 1 + w // 2)])
                if rise > tol:
                    steps += 1; big += rise
    return steps, (min(1.0, big / tot) if tot > 0 else 0.0)


def _hugs(g, region, edge, tol):
    """the share of a family's columns where it reaches the region's bottom (edge 'bottom') or top edge."""
    has = g.any(0)
    if not has.any():
        return 0.0
    if edge == 'bottom':
        d = _profile(region, 'top') - _profile(g, 'top')
    else:
        d = _profile(g, 'bottom') - _profile(region, 'bottom')
    return float((d[has] <= tol).mean())


def split_pair(region, ex, ppl, amodal=None, min_frac=0.25, gap_frac=0.4, filled=0.3):
    """a layer's visible region as a mirror pair: two major components, on opposite sides of the axis (x = ex px), far
    apart (their smallest gap over shared rows at least gap_frac of the pair's width), with the gap between them not
    the layer's own (its whole drawing, `amodal`, covers under `filled` of the gap's lower half: a bodice under a bow
    is one piece)
    -> [left_mask, right_mask] in image order, or None (one piece)."""
    lbl, n = _label(region, 2)
    if n < 2:
        return None
    area = np.bincount(lbl.ravel())[1:]
    big = [j + 1 for j in np.argsort(-area) if area[j] >= min_frac * area.sum()]
    if len(big) != 2:
        return None
    a, b = (lbl == big[0]), (lbl == big[1])
    xa, xb = np.nonzero(a)[1], np.nonzero(b)[1]
    if xa.mean() > xb.mean():
        a, b, xa, xb = b, a, xb, xa
    cross = 0.05 * ppl
    if not (xa.max() < ex + cross and xb.min() > ex - cross):
        return None
    rows = np.nonzero(a.any(1) & b.any(1))[0]
    width = max(xb.max(), xa.max()) - min(xa.min(), xb.min()) + 1
    if len(rows):
        gap = min(int(np.nonzero(b[r])[0].min() - np.nonzero(a[r])[0].max()) for r in rows)
    else:
        gap = int(xb.min() - xa.max())
    if gap < gap_frac * width:
        return None
    if amodal is not None and len(rows):
        lo, hi = xa.max() + 1, xb.min()
        between = amodal[(rows.min() + rows.max()) // 2:rows.max() + 1, lo:hi]       # the lower, hanging half
        if between.size and between.mean() >= filled:
            return None
    rest = region & ~a & ~b                                          # small bits go to the nearer half
    if rest.any():
        from scipy import ndimage
        da = ndimage.distance_transform_edt(~a); db = ndimage.distance_transform_edt(~b)
        a = a | (rest & (da <= db)); b = b | (rest & (db < da))
    return [a, b]


def hanging_parts(cells_lbl, n, ppl, line_r, min_len=0.2, min_aspect=1.8, top_contact=0.35, max_share=0.35):
    """parts of a piece hanging free from the rest: its cells at least min_len L long and min_aspect times longer than
    wide, ending in the lowest 30% of the piece; grouped when they touch and lie on the same side of the piece's axis
    (a tail split by a fold line); a group hangs when it touches the rest (the cells that are not candidates) only in
    its own top `top_contact` and holds at most max_share of the piece. Groups either side of the axis are tails, one
    on the axis a panel (a bow's layer holding the bib between its tails). -> list of (bool mask, 'tail' | 'panel')."""
    from scipy import ndimage
    if n < 2:
        return []
    piece = cells_lbl > 0
    rows = np.nonzero(piece.any(1))[0]
    cols = np.nonzero(piece.any(0))[0]
    top, bot = rows.min(), rows.max()
    Hp = bot - top + 1
    axis = (cols.min() + cols.max()) / 2
    Wp = cols.max() - cols.min() + 1
    objs = ndimage.find_objects(cells_lbl)
    cand, side = [], {}
    for j, sl in enumerate(objs):
        if sl is None:
            continue
        h = sl[0].stop - sl[0].start
        c = cells_lbl[sl] == j + 1
        w = c.sum() / max(1, h)
        if h >= 0.3 * Hp and h >= min_len * ppl and h >= min_aspect * w and sl[0].stop - 1 >= bot - 0.3 * Hp:
            cand.append(j + 1)
            cx = np.nonzero(c)[1].mean() + sl[1].start
            side[j + 1] = 0 if abs(cx - axis) < 0.08 * Wp else (1 if cx > axis else -1)
    if not cand:
        return []
    grow = _disk(line_r + 2)
    dil = {c: ndimage.binary_dilation(cells_lbl == c, grow) for c in cand}
    parent = {c: c for c in cand}

    def find(c):
        while parent[c] != c:
            parent[c] = parent[parent[c]]; c = parent[c]
        return c
    for i, c in enumerate(cand):
        for d in cand[i + 1:]:
            if side[c] == side[d] and (dil[c] & (cells_lbl == d)).any():
                parent[find(d)] = find(c)
    groups = {}
    for c in cand:
        groups.setdefault(find(c), []).append(c)
    others = piece & ~np.isin(cells_lbl, cand)
    out = []
    total = piece.sum()
    for g in groups.values():
        gm = np.isin(cells_lbl, g)
        if gm.sum() > max_share * total:
            continue
        ys = np.nonzero(gm)[0]
        h = ys.max() - ys.min() + 1
        touch = ndimage.binary_dilation(gm, grow) & others
        tr = np.nonzero(touch.any(1))[0]
        if not len(tr) or tr.max() > ys.min() + top_contact * h:
            continue
        out.append((gm, 'panel' if side[g[0]] == 0 else 'tail'))
    return out


def _clean(g, r, min_px, frac=0.05):
    """a colour's pixels in a piece without its specks and thin strokes (fold lines in a darker tone): opened by r, and
    the parts holding at least frac of it and min_px kept."""
    from scipy import ndimage
    g = ndimage.binary_opening(g, _disk(r)) if r >= 1 else g
    lbl, n = _label(g, 2)
    if n == 0:
        return g
    area = np.bincount(lbl.ravel())
    keep = (area >= max(min_px, frac * area[1:].sum()))
    keep[0] = False
    return keep[lbl]


def _depth(g, dist):
    return float(np.median(dist[g])) if g.any() else 0.0


def _profile(g, edge):
    """per column of a mask: its first row (edge 'bottom': the upper boundary of a band along the bottom) or its last
    (edge 'top'); NaN where empty."""
    has = g.any(0)
    first = np.argmax(g, 0).astype(float)
    last = (g.shape[0] - 1 - np.argmax(g[::-1], 0)).astype(float)
    prof = first if edge != 'top' else last
    prof[~has] = np.nan
    return prof


def _stepped_hem(g, region, ppl, above=None):
    """a colour along a piece's bottom meeting the cloth above it (`above`, or anything of the piece) in a
    stair-stepped line: a decorative hem, however much of the piece it covers where the piece shows."""
    tol = 0.03 * ppl
    if _hugs(g, region, 'bottom', tol) < 0.6:
        return False
    if above is not None and above.any():
        prof = _profile(above, 'top')                       # the cloth's lower edge, where the band lies under it
        gl = _profile(g, 'top')
        prof[~(np.isfinite(gl) & (gl > prof))] = np.nan
    else:
        prof = _profile(g, 'bottom')
    st, share = _steps(prof, tol, max(3, int(0.03 * ppl)))
    return st >= 2 and share >= 0.3


def sub_regions(fam, region, main, fams, ppl, dist=None):
    """the colour families inside a piece other than its main one, sorted into panels (run the piece's length through
    its body, not along its outline), top bands standing proud of it (a cuff), and trims (bands along its outline:
    hems, stripes, soles). fam: per-pixel family (-2 lines); region: the piece; dist: the region's distance transform.
    -> list of dict(kind panel | band | trim, fam, mask, ...)."""
    from scipy import ndimage
    if dist is None:
        dist = ndimage.distance_transform_edt(region)
    out = []
    rows = np.nonzero(region.any(1))[0]
    top, bot = rows.min(), rows.max()
    Hl = bot - top + 1
    wl = region.sum() / Hl
    mm = fam == main
    d_main = _depth(mm, dist)
    minpx = max(0.02 * region.sum(), (0.04 * ppl) ** 2)
    for g in np.unique(fam[region]):
        if g < 0 or g == main or fams[g]['body'] == 'skin':
            continue
        gm = _clean((fam == g) & region, 0.006 * ppl, minpx / 4)
        if gm.sum() < minpx:
            continue
        lbl, _ = _label(gm, 2)
        big = lbl == (np.argmax(np.bincount(lbl.ravel())[1:]) + 1)       # its largest part decides panel or band
        gr = np.nonzero(big.any(1))[0]
        gt, gb = gr.min(), gr.max()
        hg = gb - gt + 1
        wg = big.sum() / hg
        rec = dict(fam=int(g), mask=gm)
        deep = _depth(gm, dist) >= 0.5 * d_main
        if hg >= 0.6 * Hl and gt <= top + 0.4 * Hl and wg >= 0.12 * wl and deep and not _stepped_hem(gm, region, ppl, mm):
            rec['kind'] = 'panel'
        else:
            below = mm[gb + 1:min(bot + 1, gb + 1 + int(0.15 * Hl))]
            wb = np.median(_row_width(below)[_row_width(below) > 0]) if below.any() else np.inf
            if gt <= top + 0.1 * Hl and gb <= top + 0.35 * Hl and _row_width(big).max() >= 1.08 * wb:
                rec['kind'] = 'band'
            else:
                tol = 0.03 * ppl
                hb, ht = _hugs(gm, region, 'bottom', tol), _hugs(gm, region, 'top', tol)
                edge = 'bottom' if hb >= 0.6 and hb >= ht else 'top' if ht >= 0.6 else 'side'
                st, share = _steps(_profile(gm, edge), tol, max(3, int(0.03 * ppl)))
                stepped = (st >= 3 and share >= 0.25) or (edge == 'bottom' and _stepped_hem(gm, region, ppl, mm))
                gr_ = np.nonzero(gm.any(1))[0]
                rec.update(kind='trim', edge=edge, steps=st, pattern='stepped' if stepped else 'plain',
                           height=round(float((gr_.max() - gr_.min() + 1) / ppl), 4),
                           thickness=round(float(np.median(gm.sum(0)[gm.any(0)]) / ppl), 4))
        out.append(rec)
    return out


SUB_TYPE = {('panel', 'skirt'): 'skirt panel', ('panel', 'top'): 'bodice panel', ('panel', 'overskirt panel'): 'skirt panel',
            ('band', 'boot'): 'boot cuff', ('band', 'sleeve'): 'sleeve cuff', ('band', 'glove'): 'cuff',
            ('band', 'sock'): 'cuff', ('tail', 'bow'): 'bow tail', ('tail', 'ribbon'): 'ribbon tail'}


def _main_family(ff, half, fams, ppl, dist):
    """a piece's own colour: the family with the most pixels (skin aside) that isn't a stepped hem and lies through its
    body rather than along its outline (median depth inside the piece at least half the deepest's): where little of a
    hanging panel shows, its hem band can outweigh the cloth."""
    vals = ff[ff >= 0]
    cnt = np.bincount(vals, minlength=len(fams)).astype(float)
    for j, f in enumerate(fams):
        if f['body'] == 'skin':
            cnt[j] *= 0.01
    order = [int(j) for j in np.argsort(-cnt) if cnt[j] > 0]
    big = [j for j in order if cnt[j] >= 0.15 * cnt.sum()] or order[:1]
    if len(big) > 1:
        cl = {j: _clean(ff == j, 0.006 * ppl, 1) for j in big}
        big = [j for j in big if not any(_stepped_hem(cl[j], half, ppl, cl[k]) for k in big if k != j)] or big
    dep = {j: _depth(_clean(ff == j, 0.006 * ppl, 1), dist) for j in big}
    dmax = max(dep.values())
    for j in big:
        if dep[j] >= 0.5 * dmax:
            return j
    return big[0]


def rig_pieces(R, F):
    """the rig's front cut into pieces. -> (pieces, fams, body, fam) where pieces are dicts: layer, type, fam, mask
    (Mask in the rig's pixels), side (L her left / R / C), rel (None, or panel / band / tail of the piece index `of`),
    trims, order (drawing order: higher is drawn over lower); body: {'skin' | 'hair' | 'face': Mask}; fam: the rig's
    family per pixel."""
    from scipy import ndimage
    own, rgb, names = R['own'], R['rgb'], R['names']
    ppl = F['ppl']
    ex = F['eye'][0]
    lr = 0.011 * ppl
    ys, xs = np.nonzero(own >= 0)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    sub = (slice(y0, y1), slice(x0, x1))
    line = np.zeros(own.shape, bool)
    line[sub] = lines(rgb[sub], lr, black=0.12)
    kinds = {i: layer_type(n) for i, n in enumerate(names)}
    samples, skin, hair = {}, [], []
    for i, n in enumerate(names):
        m = (own == i) & ~line
        if not m.any():
            continue
        if kinds[i] == '':
            if any(w in n for w in HAIR_WORDS):
                hair.append(rgb[m])
            elif not any(w in n for w in ('eye', 'brow', 'mouth', 'nose')):
                skin.append(rgb[m])
        else:
            samples[n] = rgb[m]
    body_cols = {'skin': np.concatenate(skin) if skin else np.zeros((0, 3)),
                 'hair': np.concatenate(hair) if hair else np.zeros((0, 3))}
    fams = families_from(samples, body_cols)
    fam = np.full(own.shape, -1, np.int16)
    fam[sub] = classify(rgb[sub], fams, line[sub])
    fam[own < 0] = -1
    skin_i = next(j for j, f in enumerate(fams) if f['body'] == 'skin')
    pieces = []
    body = {'skin': np.zeros(own.shape, bool), 'hair': np.zeros(own.shape, bool), 'face': np.zeros(own.shape, bool)}
    minpx = (0.02 * ppl) ** 2
    for i, n in enumerate(names):
        region = own == i
        if not region.any():
            continue
        t = kinds[i]
        if t is None:                                               # unknown word: skin-coloured layers are body
            t = '' if (fam[region & ~line] == skin_i).mean() > 0.6 else 'other'
        if t == '':
            key = 'hair' if any(w in n for w in HAIR_WORDS) else \
                'face' if any(w in n for w in ('eye', 'brow', 'mouth', 'nose', 'face')) else 'skin'
            body[key] |= region
            continue
        bb = Mask(region)
        by, bx = bb.y0, bb.x0
        reg = bb.m
        hh, ww = reg.shape
        fl = np.where(reg, fam[by:by + hh, bx:bx + ww], -1)
        am = R['alpha'][n].full(own.shape)[by:by + hh, bx:bx + ww] if n in R.get('alpha', {}) else None
        halves = split_pair(reg, ex - bx, ppl, am) if not n.endswith(('_L', '_R')) else None
        for half in (halves or [reg]):
            ff = np.where(half, fl, -1)
            if not (ff >= 0).any():
                continue
            dist = ndimage.distance_transform_edt(half)
            main = _main_family(ff, half, fams, ppl, dist)
            hr, hc = np.nonzero(half)
            small_piece = max(hr.max() - hr.min(), hc.max() - hc.min()) < 0.35 * ppl
            subs = [] if small_piece else sub_regions(ff, half, main, fams, ppl, dist)
            own_px = np.zeros(half.shape, np.int16)                  # 0 the piece, k > 0 its k-th separate sub-piece
            parts = [dict(rel=None, fam=main)]
            trims = []
            for s_ in subs:
                if s_['kind'] == 'trim':
                    trims.append(s_)
                else:
                    parts.append(dict(rel=s_['kind'], fam=s_['fam'])); own_px[s_['mask']] = len(parts) - 1
            # parts of the main colour hanging free from the rest (tails)
            lbl, nc = _label((ff == main) & (own_px == 0), 1)
            area = np.bincount(lbl.ravel())
            small = area < minpx
            small[0] = False
            lbl[small[lbl]] = 0
            if not small_piece and t != 'hair accessory':                  # a lock drawn in a bun's layer is hair
                for tm, rel in hanging_parts(lbl, nc, ppl, lr):
                    parts.append(dict(rel=rel, fam=main)); own_px[tm] = len(parts) - 1
            # every pixel of the half (lines, trims, specks) to the nearest labelled part
            lab_ = np.where((ff >= 0) & ((ff == main) | (own_px > 0)), own_px, -1)
            if (lab_ < 0).any() and (lab_ >= 0).any():
                _, (iy, ix) = ndimage.distance_transform_edt(lab_ < 0, return_indices=True)
                lab_ = lab_[iy, ix]
            lab_[~half] = -1
            base = len(pieces)
            for k, p in enumerate(parts):
                m = lab_ == k
                if m.sum() < minpx:
                    continue
                typ = t if p['rel'] is None else SUB_TYPE.get((p['rel'], t), '%s %s' % (t, p['rel']))
                mk = Mask(m); mk.y0 += by; mk.x0 += bx
                pc = dict(layer=n, layer_index=i, type=typ, fam=p['fam'], mask=mk, rel=p['rel'],
                          of=None if p['rel'] is None else base, order=i, pair_split=halves is not None, trims=[])
                if p['rel'] is None:
                    for tr in trims:
                        tm = Mask(tr['mask'] & (lab_ == 0))
                        if tm.area:
                            tm.y0 += by; tm.x0 += bx
                            yy_, xx_ = tm.pixels()
                            pc['trims'].append(dict(fam=tr['fam'], edge=tr['edge'], pattern=tr['pattern'],
                                                    steps=tr['steps'], height=tr['height'],
                                                    thickness=tr['thickness'], mask=tm,
                                                    rgb=np.median(rgb[yy_, xx_], 0)))
                pieces.append(pc)
    for p in pieces:
        xl = (p['mask'].pixels()[1] - ex) / ppl
        p['side'] = 'C' if (xl.min() < -0.05 and xl.max() > 0.05 and abs(xl.mean()) < 0.25) else ('L' if xl.mean() > 0 else 'R')
    return pieces, fams, {k: Mask(v) for k, v in body.items()}, fam


def piece_ids(pieces):
    """ids from type and side (her side: L her left, R, C), the rig layer's own name for hair accessories; repeats
    numbered. Mirror pairs (one type, opposite sides, mirrored masks overlapping) share a pair id."""
    seen = {}
    for p in pieces:
        t = p['type']
        base = p['layer'].split('_')[0] if t in ('hair accessory', 'other') else t.replace(' ', '_')
        if t == 'hair accessory' and not p['layer'].endswith(('_L', '_R')):
            base = p['layer']
        named = t == 'hair accessory' and not p['layer'].endswith(('_L', '_R'))
        pid = base + ('_' + p['side'] if p['side'] in 'LR' and not named else '')
        k = seen.get(pid, 0)
        seen[pid] = k + 1
        p['id'] = pid if k == 0 else '%s%d' % (pid, k + 1)
    return pieces


def mirror_pairs(pieces, F):
    """pair ids: pieces of one type on opposite sides whose masks, mirrored about the axis, overlap."""
    ex = F['eye'][0]
    for i, a in enumerate(pieces):
        if a['side'] not in 'LR' or a.get('pair'):
            continue
        ya, xa = a['mask'].pixels()
        for b in pieces[i + 1:]:
            if b['type'] != a['type'] or b['side'] in ('C', a['side']) or b.get('pair'):
                continue
            yb, xb = b['mask'].pixels()
            ka = set(zip((ya // 8).tolist(), (np.round((2 * ex - xa) / 8)).astype(int).tolist()))
            kb = set(zip((yb // 8).tolist(), (xb // 8).tolist()))
            if len(ka & kb) >= 0.3 * min(len(ka), len(kb)):
                pid = a['id'][:-2] if a['id'].endswith(('_L', '_R')) else a['id']
                a['pair'] = b['pair'] = pid
    return pieces


# ------------------------------------------------------------------------------------------------------------- the sheet
SHEET_CLASSES = ('hair', 'iris', 'orange', 'cream', 'dark', 'white')     # bodyqa's classes a piece can be drawn in


def ridges(rgb, size=5, depth=0.10):
    """the drawn lines too faint or thin for a class of their own (a pleat's fold, a waistband's edge at the sheet's
    scale): pixels darker by `depth` than the brightest round them (a black top-hat on the value)."""
    from scipy import ndimage
    v = np.asarray(rgb).max(-1)
    return (ndimage.grey_closing(v, size=(size, size)) - v) > depth


def cells(raw, fg, rgb=None, min_px=6):
    """a view's colour cells: 4-connected runs of one class inside the figure (bodyqa.design_views' class image with
    its lines kept: lines, faint drawn lines (ridges(), with the picture given) and other classes are the walls), skin,
    lines and unclassed pixels left out. -> (cell label image, list of dict(id, cls, area, box, cx, cy))."""
    from scipy import ndimage
    from .bodyqa import CLASS
    if rgb is not None:
        raw = np.where(ridges(rgb) & (raw != CLASS['skin']), CLASS['line'], raw)
    lab_ = np.zeros(raw.shape, np.int32)
    out = []
    k = 0
    for name in SHEET_CLASSES:
        j = CLASS[name]
        l, n = ndimage.label((raw == j) & fg)
        if not n:
            continue
        area = np.bincount(l.ravel())
        objs = ndimage.find_objects(l)
        for c in range(1, n + 1):
            if area[c] < min_px:
                continue
            k += 1
            sl = objs[c - 1]
            m = l[sl] == c
            lab_[sl][m] = k
            ys, xs = np.nonzero(m)
            out.append(dict(id=k, cls=j, area=int(area[c]), box=(sl[1].start, sl[0].start, sl[1].stop, sl[0].stop),
                            cy=float(ys.mean() + sl[0].start), cx=float(xs.mean() + sl[1].start)))
    return lab_, out


# ------------------------------------------------------------------------------------------------------------- the field
def load_field(path, R=384):
    """a TRELLIS.2 field (trellis2-field/1, trellis_ext/field.py) as surface cells on an R^3 grid over its unit cube:
    dict(P (n,3) mean surface point, C (n,3) mean sRGB 0..1, ijk (n,3), h (cell size), R). Frame: z up, the front
    toward -y, x to her left."""
    z = np.load(path, allow_pickle=False)
    meta = json.loads(str(z['meta']))
    if meta.get('format') != 'trellis2-field/1':
        raise ValueError('%s: not a trellis2-field/1 file' % path)
    dual = z['dual']
    dual = dual.astype(np.float32) * (2.0 / 255) - 0.5 if dual.dtype == np.uint8 else dual.astype(np.float32)
    aabb = np.asarray(z['aabb'], np.float32)
    P = aabb[0] + (z['coords'].astype(np.float32) + dual) * float(z['voxel_size'])
    C = z['base_color'].astype(np.float32) / 255 if 'base_color' in z.files else np.full((len(P), 3), 0.7, np.float32)
    g = np.clip(((P - aabb[0]) / (aabb[1] - aabb[0]) * R).astype(np.int64), 0, R - 1)
    key = (g[:, 0] * R + g[:, 1]) * R + g[:, 2]
    u, inv, cnt = np.unique(key, return_inverse=True, return_counts=True)
    Pm = np.stack([np.bincount(inv, P[:, k]) for k in range(3)], 1) / cnt[:, None]
    Cm = np.stack([np.bincount(inv, C[:, k]) for k in range(3)], 1) / cnt[:, None]
    ijk = np.stack([u // (R * R), (u // R) % R, u % R], 1)
    return dict(P=Pm, C=Cm, ijk=ijk, h=float((aabb[1, 0] - aabb[0, 0]) / R), R=R, path=path, meta=meta)


def view_axes(az):
    """image-right and toward-camera axes (field frame) for an azimuth: 0 front, 90 her left side, 180 back."""
    a = math.radians(az)
    return np.array([math.cos(a), math.sin(a), 0.0]), np.array([math.sin(a), -math.cos(a), 0.0])


def _raster_pts(x, z, grid, shape):
    """points (L) onto a boolean grid: grid = (x0, z0, step) with rows running down from z0."""
    x0, z0, st = grid
    c = np.round((x - x0) / st).astype(np.int64)
    r = np.round((z0 - z) / st).astype(np.int64)
    ok = (c >= 0) & (c < shape[1]) & (r >= 0) & (r < shape[0])
    out = np.zeros(shape, bool)
    out[r[ok], c[ok]] = True
    return out


def fit_silhouette(X, Z, target, grid, s0, tx0, tz0, rows=None, spans=(0.06, 0.2, 0.12), steps=(0.01, 0.025, 0.02),
                   levels=3):
    """scale and offset of projected points (X, Z field units) onto a target silhouette (bool grid in L): x_L = (X -
    tx) / s, z_L = (Z - tz) / s, by IoU over a coarse-to-fine search. rows: the grid rows to count (a figure cut by the
    sheet's edge). -> (s, tx, tz, iou)."""
    from scipy import ndimage
    tgt = target if rows is None else target & rows[:, None]

    def iou(s, tx, tz):
        m = _raster_pts((X - tx) / s, (Z - tz) / s, grid, target.shape)
        m = ndimage.binary_closing(m, iterations=1)
        if rows is not None:
            m &= rows[:, None]
        return (m & tgt).sum() / max(1, (m | tgt).sum())
    best = (iou(s0, tx0, tz0), s0, tx0, tz0)
    for it in range(levels):
        f = 0.5 ** it
        _, s1, tx1, tz1 = best
        for ds in np.arange(-spans[0], spans[0] + 1e-9, steps[0]) * f:
            for dz in np.arange(-spans[1], spans[1] + 1e-9, steps[1]) * f:
                s = s1 * (1 + ds); tz = tz1 + dz * s1
                v = iou(s, tx1, tz)
                if v > best[0]:
                    best = (v, s, tx1, tz)
        _, s1, tx1, tz1 = best
        for dx in np.arange(-spans[2], spans[2] + 1e-9, steps[2]) * f:
            tx = tx1 + dx * s1
            v = iou(s1, tx, tz1)
            if v > best[0]:
                best = (v, s1, tx, tz1)
    return best[1], best[2], best[3], round(float(best[0]), 4)


def zbuffer(u, v, depth, W, H, r=1):
    """per pixel the index of the nearest point (smallest depth), points splatted (2r+1)^2 -> (H, W) int (-1 empty)
    and the depth image."""
    best = np.full(H * W, -1, np.int64)
    bd = np.full(H * W, np.inf)
    ui, vi = np.round(u).astype(np.int64), np.round(v).astype(np.int64)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            x, y = ui + dx, vi + dy
            ok = (x >= 0) & (x < W) & (y >= 0) & (y < H)
            lin = y[ok] * W + x[ok]
            idx = np.nonzero(ok)[0]
            d = depth[ok]
            o = np.lexsort((d, lin))
            lo = lin[o]
            first = np.r_[True, lo[1:] != lo[:-1]]
            sel = o[first]
            L_, D_ = lin[sel], d[sel]
            better = D_ < bd[L_]
            bd[L_[better]] = D_[better]
            best[L_[better]] = idx[sel[better]]
    return best.reshape(H, W), bd.reshape(H, W)


GRID = (-3.6, 1.6, 0.02)                     # the L grids the silhouettes are fitted on: x from -3.6, z down from +1.6
GRID_SHAPE = (390, 360)


def silhouette_L(mask, px_of, grid=GRID, shape=GRID_SHAPE):
    """a pixel mask sampled onto the L grid: px_of(x_L, z_L) -> (px, py) arrays."""
    x0, z0, st = grid
    zz, xx = np.mgrid[0:shape[0], 0:shape[1]]
    X, Z = x0 + xx * st, z0 - zz * st
    px, py = px_of(X, Z)
    px, py = np.round(px).astype(np.int64), np.round(py).astype(np.int64)
    ok = (px >= 0) & (px < mask.shape[1]) & (py >= 0) & (py < mask.shape[0])
    out = np.zeros(shape, bool)
    out[ok] = mask[py[ok], px[ok]]
    return out


def fit_field(Fd, target, az, rows=None, init=None, spans=(0.06, 0.2, 0.12), levels=3):
    """the field seen from az, fitted onto a silhouette in L (the rig's front, or a sheet figure). init (s, tx or None,
    tz): start there (tx None: centred on the target's upper body). -> dict(az, s, tx, tz, iou)."""
    r, _ = view_axes(az)
    X, Z = Fd['P'] @ r, Fd['P'][:, 2]
    zs = np.nonzero(target.any(1))[0]
    x0, z0, st = GRID
    top = z0 - zs.min() * st
    if init is not None and init[1] is None:                        # the scale and height known: centre x
        s, tz = init[0], init[2]
        band = (Z > tz + s * (top - 1.6)) & (Z < tz + s * (top - 0.8))
        rr = [r_ for r_ in range(zs.min(), zs.max()) if target[r_].any() and top - 1.6 < z0 - r_ * st < top - 0.8]
        tmid = np.median([(np.nonzero(target[r_])[0].min() + np.nonzero(target[r_])[0].max()) / 2 * st + x0 for r_ in rr])
        init = (s, float(np.median(X[band])) - s * tmid if band.any() else float(X.mean()), tz)
    if init is None:
        full_h = Z.max() - Z.min()
        s = full_h / (top - (z0 - zs.max() * st))
        tz = Z.max() - s * top
        # x: the target's middle over its upper body, the field's likewise
        band = (Z > tz + s * (top - 1.6)) & (Z < tz + s * (top - 0.8))
        tmid = np.median([(np.nonzero(target[r_])[0].min() + np.nonzero(target[r_])[0].max()) / 2 * st + x0
                          for r_ in range(zs.min(), zs.max()) if target[r_].any() and top - 1.6 < z0 - r_ * st < top - 0.8])
        tx = float(np.median(X[band])) - s * tmid if band.any() else X.mean()
    else:
        s, tx, tz = init
    s, tx, tz, iou = fit_silhouette(X, Z, target, GRID, s, tx, tz, rows, spans, levels=levels)
    return dict(az=az, s=float(s), tx=float(tx), tz=float(tz), iou=iou)


def _neighbours(ijk, R):
    """26-neighbour pairs among grid cells -> (a, b, length in cells) with a < b."""
    key = (ijk[:, 0] * R + ijk[:, 1]) * R + ijk[:, 2]
    order = np.argsort(key)
    ks = key[order]
    A, B, D = [], [], []
    for d in [(dx, dy, dz) for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1) if (dx, dy, dz) > (0, 0, 0)]:
        q = ijk + np.array(d)
        ok = (q >= 0).all(1) & (q < R).all(1)
        kq = (q[:, 0] * R + q[:, 1]) * R + q[:, 2]
        pos = np.clip(np.searchsorted(ks, kq), 0, len(ks) - 1)
        hit = ok & (ks[pos] == kq)
        A.append(np.nonzero(hit)[0]); B.append(order[pos[hit]]); D.append(np.full(hit.sum(), math.sqrt(sum(x * x for x in d))))
    return np.concatenate(A), np.concatenate(B), np.concatenate(D)


def project(Fd, fit, ppl, origin, shape, r=1):
    """the field's cells into a picture seen from fit['az'] at ppl pixels per L with the eye line and axis at origin
    (x, y) -> (index image of the front-most cell, depth image, per-cell (u, v, depth))."""
    rv, tv = view_axes(fit['az'])
    P = Fd['P']
    u = origin[0] + (P @ rv - fit['tx']) / fit['s'] * ppl
    v = origin[1] - (P[:, 2] - fit['tz']) / fit['s'] * ppl
    d = -(P @ tv)                                                   # smaller is nearer the camera
    idx, dep = zbuffer(u, v, d, shape[1], shape[0], r)
    return idx, dep, (u, v, d)


def visible(Fd, fit, ppl, origin, shape, tol_L=0.03, r=1):
    """per cell: shown in the view (within tol_L of the front-most surface at its pixel) -> (bool (n,), u, v)."""
    _, dep, (u, v, d) = project(Fd, fit, ppl, origin, shape, r)
    ui = np.clip(np.round(u).astype(int), 0, shape[1] - 1)
    vi = np.clip(np.round(v).astype(int), 0, shape[0] - 1)
    inside = (u >= 0) & (u < shape[1]) & (v >= 0) & (v < shape[0])
    vis = inside & (d <= dep[vi, ui] + tol_L * fit['s'])
    return vis, u, v


def field_labels(Fd, fit, label_img, F_rig, n_labels, body_labels=(), label_fam=None, fams=None, sizes=None, fam_img=None,
                 front_only=(), hue_de=25.0, ctx=0.02, reach=(0.2, 1.0), depth=0.1):
    """every field cell labelled by a colour-aware geodesic competition: seeds are the cells shown in the rig's front
    whose rig pixel and its neighbours ctx L away all carry one label (a piece, or the body's skin / hair) and whose
    colour is within hue_de of that label's median; edges between neighbouring cells cost their length times
    1 + (colour difference / 10)^2, so a label spreads through its own colour and stops at another's. A piece reaches
    at most max(reach[0] L, reach[1] x its seeds' diameter) from them (a clip's yellow doesn't run through the hair's
    highlights; sizes: each label's size in L, its drawing's diagonal, else its seeds' spread), and a front_only piece
    (whole in the front drawing: see complete()) no deeper than `depth` L behind its seeds (a bow doesn't run round the
    neck into the back of a sailor collar). Cells past those limits go to the nearest label that may have them.
    -> (labels (n,) int, -1 unreached; seed mask)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import dijkstra
    H, W = label_img.shape
    ppl = F_rig['ppl']
    vis, u, v = visible(Fd, fit, ppl, F_rig['eye'], (H, W))
    ui, vi = np.round(u).astype(int), np.round(v).astype(int)
    lab0 = np.full(len(u), -1)
    ok = vis.copy()
    for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
        x = np.clip(ui + int(dx * ctx * ppl), 0, W - 1); y = np.clip(vi + int(dy * ctx * ppl), 0, H - 1)
        l = label_img[y, x]
        if dx == 0 and dy == 0:
            lab0 = l.astype(int)
        else:
            ok &= l == lab0
    ok &= lab0 >= 0
    L = lab(Fd['C']) * W_LAB
    fam0 = fam_img[np.clip(vi, 0, H - 1), np.clip(ui, 0, W - 1)] if fam_img is not None else np.zeros(len(u), int)
    if fam_img is not None:
        # the field's own palette: each rig family's median over the candidate seeds drawn in it; a seed keeps only if
        # its colour is nearest its own family's (the rig's skirt drawn longer than the field's lands on the shorts)
        fs = sorted(set(fam0[ok].tolist()) - {-1, -2})
        cen = {g: np.median(L[ok & (fam0 == g)], 0) for g in fs if (ok & (fam0 == g)).sum() >= 20}
        if len(cen) >= 2:
            keys = list(cen)
            C = np.array([cen[g] for g in keys])
            idx = np.nonzero(ok)[0]
            near = np.array(keys)[np.argmin(((L[idx, None] - C[None]) ** 2).sum(-1), 1)]
            ok[idx[(near != fam0[idx]) & np.isin(fam0[idx], keys)]] = False
    seeds = np.nonzero(ok)[0]
    a, b, dist = _neighbours(Fd['ijk'], Fd['R'])
    dc = np.sqrt(((L[a] - L[b]) ** 2).sum(1))
    w = dist * (1 + (dc / 10.0) ** 2)
    n = len(u)
    G = coo_matrix((np.r_[w, w], (np.r_[a, b], np.r_[b, a])), shape=(n, n)).tocsr()
    if not len(seeds):
        return np.full(n, -1), ok
    dd, _, src = dijkstra(G, directed=False, indices=seeds, min_only=True, return_predecessors=True)
    out = np.where(src >= 0, lab0[np.maximum(src, 0)], -1)
    cell_L = Fd['h'] / fit['s']
    far = np.zeros(n, bool)
    _, tv = view_axes(0.0)
    dep = -(Fd['P'] @ tv)                                           # distance behind the front, field units
    for k in range(n_labels):
        if k in body_labels:
            continue
        sk = seeds[lab0[seeds] == k]
        if not len(sk):
            continue
        P = Fd['P'][sk]
        diam = sizes[k] if sizes is not None else 2 * float(np.percentile(np.linalg.norm(P - np.median(P, 0), axis=1), 80)) / fit['s']
        lim = max(reach[0], reach[1] * diam) / cell_L
        far |= (out == k) & (dd > lim)
        if k in front_only:
            far |= (out == k) & (dep > np.percentile(dep[sk], 95) + depth * fit['s'])
    if far.any():
        free = np.array([k not in front_only for k in range(n_labels)])
        bs = np.nonzero((out >= 0) & ~far & free[np.maximum(out, 0)])[0]
        if len(bs):
            _, _, src2 = dijkstra(G, directed=False, indices=bs, min_only=True, return_predecessors=True)
            out[far] = np.where(src2[far] >= 0, out[np.maximum(src2[far], 0)], -1)
    return out, ok


def complete(R, pieces, step=None):
    """pieces the front drawing shows whole: touching no background and occluded (a layer drawn over them) along under a
    quarter of their outline. A bow on the chest is whole; a skirt reaching the silhouette, or a sailor collar running
    under the hair, continues out of sight. -> dict(index: (whole, occluded share, touches background))."""
    own = R['own']
    H, W = own.shape
    out = {}
    for k, p in enumerate(pieces):
        st = step or 6
        ys, xs = p['mask'].pixels()
        m = p['mask']
        over = bg = tot = 0
        for dy, dx in ((st, 0), (-st, 0), (0, st), (0, -st)):
            y2, x2 = np.clip(ys + dy, 0, H - 1), np.clip(xs + dx, 0, W - 1)
            inside = np.zeros(len(ys), bool)
            yy, xx = y2 - m.y0, x2 - m.x0
            ok = (yy >= 0) & (yy < m.m.shape[0]) & (xx >= 0) & (xx < m.m.shape[1])
            inside[ok] = m.m[yy[ok], xx[ok]]
            o = own[y2[~inside], x2[~inside]]
            tot += len(o)
            bg += int((o < 0).sum())
            over += int((o > p['layer_index']).sum())
        share = over / max(1, tot - bg)
        out[k] = (bool(bg == 0 and share < 0.25), round(float(share), 3), bool(bg > 0))
    return out


def match_view(cell_lbl, cell_list, pred, allowed, ppl, r_max=0.12, whole=0.85):
    """a sheet view's cells to pieces: each cell takes the label predicted over most of its pixels among the labels its
    colour class allows (per pixel, the nearest such prediction within r_max L, so a slightly misplaced prediction
    still reaches its cell). A cell where no label holds `whole` of it and another holds 15% and 20 pixels (two pieces
    drawn without a line between) is split pixel by pixel. pred: (H,W) predicted label per pixel (-1 none); allowed: {class: set of labels}.
    -> (assigned label per pixel (-1 none), per cell dict(label, share, dist, split))."""
    from scipy import ndimage
    H, W = cell_lbl.shape
    out = np.full((H, W), -1, np.int32)
    res = {}
    by_fam = {}
    for c in cell_list:
        by_fam.setdefault(c['cls'], []).append(c)
    for j, cl in by_fam.items():
        ok = np.isin(pred, list(allowed.get(j, ()))) & (pred >= 0)
        if not ok.any():
            for c in cl:
                res[c['id']] = dict(label=-1, share=0.0, dist=None, split=False)
            continue
        d, (iy, ix) = ndimage.distance_transform_edt(~ok, return_indices=True)
        near = pred[iy, ix]
        near[d > r_max * ppl] = -1
        for c in cl:
            x0, y0, x1, y1 = c['box']
            m = cell_lbl[y0:y1, x0:x1] == c['id']
            nv = near[y0:y1, x0:x1]
            lv = nv[m]
            lv = lv[lv >= 0]
            if not len(lv):
                res[c['id']] = dict(label=-1, share=0.0, dist=None, split=False)
                continue
            vals, cnt = np.unique(lv, return_counts=True)
            k = int(np.argmax(cnt))
            lb = int(vals[k])
            share = float(cnt[k] / m.sum())
            second = np.sort(cnt)[-2] if len(cnt) > 1 else 0
            split = share < whole and second >= max(0.15 * m.sum(), 20)
            res[c['id']] = dict(label=lb, share=round(share, 3), dist=round(float(np.mean(d[y0:y1, x0:x1][m]) / ppl), 4),
                                split=split)
            if split:
                sub = out[y0:y1, x0:x1]
                sub[m & (nv >= 0)] = nv[m & (nv >= 0)]
            elif share >= 0.25:
                out[y0:y1, x0:x1][m] = lb
    return out, res


def adjacency(label_img, n_labels, step):
    """which labels touch which in a label image (the rig's pieces and body): pixel pairs `step` apart across and down.
    -> (n_labels, n_labels) contact counts (symmetric)."""
    Cn = np.zeros((n_labels, n_labels), np.int64)
    L = label_img
    for a, b in ((L[:, :-step], L[:, step:]), (L[:-step], L[step:])):
        m = (a >= 0) & (b >= 0) & (a != b)
        if m.any():
            np.add.at(Cn, (a[m].astype(int), b[m].astype(int)), 1)
    return Cn + Cn.T


def layer_contacts(R, pieces, step=4, grow=2):
    """pieces whose layers' whole drawings (parts hidden under other layers too) overlap or touch: in contact in 3D
    even where the front shows something between them (a sailor collar lies on the bodice under the bow).
    -> (n, n) bool."""
    from scipy import ndimage
    n = len(pieces)
    H, W = R['own'].shape
    small = {}
    for nm in {p['layer'] for p in pieces}:
        m = R['alpha'][nm].full((H, W))[::step, ::step]
        small[nm] = ndimage.binary_dilation(m, iterations=grow)
    out = np.zeros((n, n), bool)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = pieces[i]['layer'], pieces[j]['layer']
            if a != b and (small[a] & small[b]).any():
                out[i, j] = out[j, i] = True
    return out


def adjacency_pass(A, vn, iters=1, gain=0.3, ring=5, sure=0.7, r_max=0.12):
    """cells moved to the piece whose neighbours in the rig match theirs in the view (the task's third cue, after colour
    and position): each whole cell's ring of neighbouring labels (pieces, and the sheet's own hair and skin) is scored
    for its label and for every other piece its class allows: the share of the ring that piece touches in the rig's
    front, or whose layers lie on each other (or is itself). A cell goes to a piece scoring `gain` more than its labels
    (a cell split between two predictions is scored whole: the back of a sailor collar, predicted as the bow next to
    it, touches the hair, which a bow never does). A tie-breaker only: cells the prediction is sure of (`sure` of them
    one label, unsplit) stay, since in other views things overlap that don't touch (a hand over the skirt), and a cell
    only moves to a piece predicted within r_max L of a tenth of it. -> [(cell id, old, new)]."""
    from scipy import ndimage
    from .bodyqa import CLASS
    n, adj = A['n'], A['adjacency']
    nb = adj > 0
    if A.get('layer_contacts') is not None:
        nb = nb.copy(); nb[:n, :n] |= A['layer_contacts']
    mt, Av, pred = A['match'][vn], A['assigned'][vn], A['pred'][vn]
    raw = A['sheet']['design'][vn]['raw']
    moved = []
    for _ in range(iters):
        full = Av.copy()
        full[(raw == CLASS['skin']) & (full < 0)] = n
        changed = False
        for c in mt['cells']:
            r = mt['result'][c['id']]
            X = r['label']
            if X < 0 or X >= n or (r.get('share', 0) >= sure and not r.get('split')):
                continue
            x0, y0, x1, y1 = c['box']
            sl = (slice(max(0, y0 - ring - 1), y1 + ring + 1), slice(max(0, x0 - ring - 1), x1 + ring + 1))
            m = mt['cell_lbl'][sl] == c['id']
            own = set(np.unique(Av[sl][m]).tolist()) - {-1}
            rg = ndimage.binary_dilation(m, iterations=ring) & ~m
            lv = full[sl][rg]
            lv = lv[lv >= 0]
            if len(lv) < 5:
                continue
            def score(k):
                return float(np.mean(nb[k][lv] | (lv == k)))
            sx = max(score(k) for k in own) if own else 0.0
            best, bs = X, sx
            pv = pred[sl]
            dpx = int(r_max * A['sheet']['ppl'])
            near = ndimage.binary_dilation(m, iterations=min(dpx, 8))
            pk, pc_ = np.unique(pv[near & (pv >= 0)], return_counts=True)
            nearby = {int(a) for a, b in zip(pk, pc_) if b >= 0.1 * m.sum()}
            for k in A['allowed'].get(c['cls'], ()):
                if k != X and k < n and k in nearby:
                    sk = score(k)
                    if sk > bs:
                        best, bs = k, sk
            if best not in own and bs - sx >= gain:
                Av[sl][m] = best
                r.update(label=int(best), adjacency=round(bs, 3), was=int(X), split=False)
                moved.append((c['id'], int(X), int(best)))
                changed = True
        if not changed:
            break
    return moved


def landmark_pass(A, vn, min_px=12):
    """cells no prediction reached, matched by landmarks: a piece allowed for the cell's class, whose heights on the
    sheet's front (else the rig's) hold the cell's, on the cell's side of the body in this view; pieces not yet seen in
    the view first. The body's own cells (a highlight on skin, the hair's shading) stay out: where the prediction
    around the cell is the body. -> the cells taken, [(cell id, label)]."""
    n = A['n']
    mt, Av, pred, toL = A['match'][vn], A['assigned'][vn], A['pred'][vn], A['toL'][vn]
    front = A['assigned'].get('front')
    zr = {}
    for k, p in enumerate(A['pieces']):
        if front is not None and (front == k).any():
            ys = np.nonzero((front == k).any(1))[0]
            zr[k] = (float(A['toL']['front'](0, ys.max())[1]), float(A['toL']['front'](0, ys.min())[1]))
        else:
            b = p['mask'].box()
            _, z0 = to_L(A['F'], 0, b[3]); _, z1 = to_L(A['F'], 0, b[1])
            zr[k] = (float(z0), float(z1))
    taken = []
    seen = set(np.unique(Av[Av >= 0]).tolist())
    for c in mt['cells']:
        r = mt['result'][c['id']]
        if r['label'] >= 0 or c['area'] < min_px:
            continue
        x0, y0, x1, y1 = c['box']
        m = mt['cell_lbl'][y0:y1, x0:x1] == c['id']
        pv = pred[max(0, y0 - 3):y1 + 3, max(0, x0 - 3):x1 + 3]
        pv = pv[pv >= 0]
        from .bodyqa import CLASS
        if len(pv) and np.mean(pv >= n) > 0.5 and c['cls'] in (CLASS['hair'], CLASS['white']):
            r['body'] = True
            continue
        ys = np.nonzero(m.any(1))[0]
        cz0, cz1 = float(toL(0, y0 + ys.max())[1]), float(toL(0, y0 + ys.min())[1])
        cx = float(toL(c['cx'], 0)[0])
        her = None if vn == 'profile' else (('R' if cx < 0 else 'L') if vn != 'back' else ('L' if cx < 0 else 'R'))
        best, bs = None, 0.0
        for k in A['allowed'].get(c['cls'], ()):
            if k >= n:
                continue
            p = A['pieces'][k]
            lo, hi = zr[k]
            ov = max(0.0, min(hi, cz1) - max(lo, cz0)) / max(1e-6, cz1 - cz0)
            if ov <= 0:
                continue
            sc = ov - (0.6 if (her and p['side'] in 'LR' and abs(cx) > 0.15 and p['side'] != her) else 0.0) \
                - (0.2 if k in seen else 0.0)
            if sc > bs:
                best, bs = k, sc
        if best is not None and bs >= 0.5:
            Av[y0:y1, x0:x1][m] = best
            r.update(label=int(best), share=1.0, landmark=True)
            taken.append((c['id'], int(best)))
    return taken


def vote(n_cells, n_labels, views):
    """votes of the sheet's masks into the field: views = [(visible (n,) bool, u, v, assigned label image)]. Every cell
    shown in a view takes a vote for the label the sheet gives its pixel there. -> (votes (n, K) int)."""
    V = np.zeros((n_cells, n_labels), np.int32)
    for vis, u, v, A in views:
        H, W = A.shape
        idx = np.nonzero(vis)[0]
        ui = np.clip(np.round(u[idx]).astype(int), 0, W - 1)
        vi = np.clip(np.round(v[idx]).astype(int), 0, H - 1)
        lb = A[vi, ui]
        ok = lb >= 0
        np.add.at(V, (idx[ok], lb[ok]), 1)
    return V


def outline(mask, to_L, tol=0.01):
    """a mask's outlines as polygons in L (to_L(px, py) -> (x, z)), simplified to tol L; largest first."""
    from skimage import measure
    polys = []
    if not mask.any():
        return polys
    pad = np.pad(mask, 1)
    for c in measure.find_contours(pad.astype(float), 0.5):
        if len(c) < 4:
            continue
        x, z = to_L(c[:, 1] - 1, c[:, 0] - 1)
        P = np.stack([x, z], 1)
        P = measure.approximate_polygon(P, tol)
        if len(P) >= 3:
            a = 0.5 * abs(np.dot(P[:, 0], np.roll(P[:, 1], 1)) - np.dot(P[:, 1], np.roll(P[:, 0], 1)))
            polys.append((a, [[round(float(x_), 3), round(float(z_), 3)] for x_, z_ in P]))
    polys.sort(key=lambda t: -t[0])
    return [p for a, p in polys if a >= tol * tol]


# ------------------------------------------------------------------------------------------------------------ the analysis
def _p(path):
    return path if os.path.isabs(path) else os.path.join(ROOT, path)


def find_field(M):
    """the TRELLIS field for the manifest's generated mesh: charkit/out/i3d/ext/*/<stem>_field.npz (gitignored)."""
    import glob
    tr = M['references'].get('trellis')
    if not tr:
        return None
    stem = os.path.splitext(os.path.basename(tr['path']))[0]
    hits = sorted(glob.glob(os.path.join(ROOT, 'charkit', 'out', 'i3d', 'ext', '*', stem + '_field.npz')))
    return hits[0] if hits else None


def load_image(path):
    from PIL import Image
    return np.asarray(Image.open(_p(path)).convert('RGB'), np.float64) / 255


def sheet_classes(p, R, F, split=None, share=0.08):
    """the sheet classes (charkit.bodyqa.CLASS ids) a rig piece can be drawn in: bodyqa.family of its own pixels, each
    class holding `share` of them (lines aside); orange above the shoulders is the sheet's hair class (bodyqa splits
    them by height too)."""
    from .bodyqa import CLASS, HAIR_SPLIT, family
    split = HAIR_SPLIT if split is None else split
    ys, xs = p['mask'].pixels()
    px = R['rgb'][ys, xs]
    px = px[px.max(1) >= LINE_V]
    cl = family(px)
    cnt = np.bincount(cl.ravel(), minlength=16)
    out = set(int(c) for c in np.nonzero(cnt >= share * max(1, len(px)))[0])
    _, z = to_L(F, 0, ys.mean())
    if CLASS['orange'] in out and z > split:
        out.discard(CLASS['orange']); out.add(CLASS['hair'])
    out |= set(int(c) for c in family(np.array([t['rgb'] for t in p.get('trims', []) if 'rgb' in t]).reshape(-1, 3)))
    out -= {CLASS['other'], CLASS['line'], CLASS['none'], CLASS['skin']}
    return out


def analyse(spec, field=None, use_field=True, log=print):
    """the measurement: the rig's pieces, the sheet's views matched, the field labelled and voted. -> dict A (arrays;
    graph() turns it into the JSON graph)."""
    import time
    from . import bodyqa, manifest, sheetqa
    t0 = time.time()
    ref = spec.get('ref', {}) if isinstance(spec.get('ref'), dict) else {}
    M = manifest.load(ref['manifest']) if ref.get('manifest') else None
    R_ = (M or {}).get('references', {})
    rig_path = ref.get('rig') or R_.get('rig', {}).get('path')
    eye_x = (spec.get('eyes') or {}).get('x') or R_.get('rig', {}).get('scale', {}).get('eye_x', 0.168)
    R = load_rig(rig_path)
    F = rig_frame(R, eye_x)
    pieces, fams, body, fam_img = rig_pieces(R, F)
    piece_ids(pieces)
    mirror_pairs(pieces, F)
    n = len(pieces)
    SKIN, HAIR = n, n + 1
    hair_f = next(j for j, f in enumerate(fams) if f['body'] == 'hair')
    skin_f = next(j for j, f in enumerate(fams) if f['body'] == 'skin')
    log('rig: %d pieces, %d colour families (%.1fs)' % (n, len(fams), time.time() - t0))
    limg = np.full(R['own'].shape, -1, np.int16)                   # the rig's front by label: pieces, then skin, hair
    for k, p in enumerate(pieces):
        yy, xx = p['mask'].pixels(); limg[yy, xx] = k
    for key, lb in (('skin', SKIN), ('face', SKIN), ('hair', HAIR)):
        yy, xx = body[key].pixels(); limg[yy, xx] = lb
    A = dict(R=R, F=F, pieces=pieces, fams=fams, body=body, fam_img=fam_img, spec=spec, manifest=M, n=n, label_img=limg,
             labels=[p['id'] for p in pieces] + ['skin', 'hair'], views={}, eye_x=eye_x,
             adjacency=adjacency(limg, n + 2, max(2, int(0.012 * F['ppl']))), layer_contacts=layer_contacts(R, pieces))
    # --- the sheet: its figures and class images from charkit.sheetqa / charkit.bodyqa (the model-sheet QA's own)
    # the design's full figures: the generated body sheet where the manifest names one (sheets.body, scaled by its own
    # eyes), else the model sheet (scaled against the rig)
    bs = ref.get('body_sheet')
    sh = R_.get('sheet') or {}
    sheet_path = (bs or {}).get('image') or sh.get('path') or (ref.get('sheet') or {}).get('image')
    if not sheet_path:
        return A
    figs = {'facing': bs.get('facing', -1)} if bs else (sh.get('figures') or ref.get('sheet') or {})
    rgb = load_image(sheet_path)
    base = os.path.join(_p(rig_path), 'base.png')
    if figs.get('front_figure') and os.path.exists(base):
        from PIL import Image
        alpha = np.asarray(Image.open(base).convert('RGBA'))[..., 3]
        ppl = sheetqa.sheet_ppl(rgb, figs['front_figure'], alpha, F['ppl'])
    else:
        ppl = None
    D = sheetqa.detect_figures(rgb, ppl=ppl, eye_x=eye_x, facing=figs.get('facing'))
    ppl = float(D['ppl'])
    design = bodyqa.design_views(rgb, D, ppl)
    te = D['figures'].get('three_quarter', {}).get('eyes') or []
    az3 = float(np.degrees(np.arccos(np.clip(abs(te[1][0] - te[0][0]) / (2 * eye_x * ppl), 0, 1)))) if len(te) == 2 else 35.0
    V = {}
    for vn, dv in design.items():
        w = dv['win']
        V[vn] = dict(az=0.0 if vn == 'front' else round(az3, 1) if vn == 'three_quarter' else AZ[vn], cut=dv['cut'],
                     origin=(w['x'] * ppl - 0.5, w['top'] * ppl - 0.5), eye=dv['eye'], box=D['figures'][vn]['box'])
    A['views'] = V
    A['sheet'] = dict(path=sheet_path, rgb=rgb, ppl=ppl, D=D, design=design, az3_eyes=round(az3, 1))
    import functools
    A['toL'] = {vn: functools.partial(_grid_to_L, v['origin'], ppl) for vn, v in V.items()}
    log('sheet: %s at %.1f px/L, 3/4 at %.1f deg by its eyes (%.1fs)' % (', '.join(V), ppl, az3, time.time() - t0))
    classes = {k: sheet_classes(p, R, F) for k, p in enumerate(pieces)}
    allowed = {}
    for k, cs in classes.items():
        for j in cs:
            allowed.setdefault(j, set()).add(k)
    allowed.setdefault(bodyqa.CLASS['hair'], set()).add(HAIR)
    A.update(allowed=allowed, classes=classes)
    # --- the field: fitted to the rig's front and to each figure, labelled from the rig, projected into each view
    fpath = field or (find_field(M) if M else None)
    Fd = load_field(_p(fpath)) if (use_field and fpath and os.path.exists(_p(fpath))) else None
    A['field'] = Fd
    if Fd is not None:
        rigsil = silhouette_L(R['own'] >= 0, lambda X, Z: (F['eye'][0] + X * F['ppl'], F['eye'][1] - Z * F['ppl']))
        fr = fit_field(Fd, rigsil, 0.0)
        sizes = []
        for p in pieces:
            b = p['mask'].box(); sizes.append(float(np.hypot(b[2] - b[0], b[3] - b[1])) / F['ppl'])
        whole = complete(R, pieces)
        A['whole'] = whole
        lab0, seeds = field_labels(Fd, fr, limg, F, n + 2, (SKIN, HAIR), [p['fam'] for p in pieces] + [skin_f, hair_f],
                                   fams, sizes + [0, 0], fam_img, front_only={k for k, w in whole.items() if w[0]})
        log('field: %d cells, rig fit IoU %.3f, %d seeds (%.1fs)' % (len(Fd['P']), fr['iou'], seeds.sum(), time.time() - t0))
        fits = {}
        zz = GRID[1] - np.arange(GRID_SHAPE[0]) * GRID[2]
        for vn in ('front', 'three_quarter', 'profile', 'back'):
            if vn not in V:
                continue
            v, dv = V[vn], design[vn]
            sil = silhouette_L(dv['fg'], lambda X, Z, v=v: (v['origin'][0] + X * ppl, v['origin'][1] - Z * ppl))
            rows = zz > v['cut'] + 0.05 if v['cut'] is not None else None
            if vn == 'front' or 'front' not in fits:
                fits[vn] = fit_field(Fd, sil, v['az'], rows)
                continue
            init = (fits['front']['s'], None, fits['front']['tz'])
            azs = [v['az']] if vn != 'three_quarter' else [v['az'] + d for d in (-10, -5, 0, 5, 10, 15, 20)]
            best = None
            for az in azs:                                          # every azimuth coarsely, then the best one fully
                f = fit_field(Fd, sil, az, rows, init, (0.03, 0.1, 0.12), levels=1 if len(azs) > 1 else 3)
                if best is None or f['iou'] > best['iou']:
                    best = f
            if len(azs) > 1:
                best = fit_field(Fd, sil, best['az'], rows, init, (0.03, 0.1, 0.12))
            fits[vn] = best
        A.update(field_fit_rig=fr, field_fits=fits, field_labels0=lab0, field_seeds=seeds)
        log('fits: %s (%.1fs)' % (', '.join('%s %.3f' % (k, f['iou']) for k, f in fits.items()), time.time() - t0))
    # --- the sheet's cells matched to pieces, view by view
    match, assigned, preds, visib = {}, {}, {}, {}
    for vn, v in V.items():
        dv = design[vn]
        shape = dv['raw'].shape
        clbl, clist = cells(dv['raw'], dv['fg'], dv['rgb'])
        if Fd is not None:
            fit = A['field_fits'][vn]
            idx, _, _ = project(Fd, fit, ppl, v['origin'], shape)
            pred = np.where(idx >= 0, lab0[np.maximum(idx, 0)], -1)
            pred[~dv['fg']] = -1
            visib[vn] = visible(Fd, fit, ppl, v['origin'], shape)
        else:
            pred = landmark_prediction(A, vn, shape)
        Av, res = match_view(clbl, clist, pred, allowed, ppl)
        preds[vn], assigned[vn] = pred, Av
        match[vn] = dict(cells=clist, result=res, cell_lbl=clbl)
    A.update(match=match, assigned=assigned, pred=preds)
    for vn in V:
        match[vn]['adjacency'] = adjacency_pass(A, vn)              # neighbours as in the rig
        match[vn]['landmark'] = landmark_pass(A, vn)                # what no prediction reached, by landmarks
    # --- the field relabelled by the sheet's votes
    if Fd is not None:
        votes = vote(len(Fd['P']), n + 2, [visib[vn] + (assigned[vn],) for vn in V])
        tot = votes.sum(1)
        lab1 = np.where(tot > 0, votes.argmax(1), lab0)
        agree = (votes[np.arange(len(lab0)), np.maximum(lab0, 0)] == votes.max(1)) & (tot > 0)
        A.update(field_labels=lab1, votes=votes, vote_agree=agree)
        log('votes: %d cells voted, %.0f%% agree with the prediction (%.1fs)' % ((tot > 0).sum(), 100 * agree[tot > 0].mean(),
                                                                                time.time() - t0))
    return A


def _grid_to_L(origin, ppl, px, py):
    return (np.asarray(px, float) - origin[0]) / ppl, (origin[1] - np.asarray(py, float)) / ppl


def landmark_prediction(A, view, shape):
    """without a field: each rig piece placed in a sheet view by landmarks alone (heights from the eye line kept; x as
    drawn on the front, mirrored on the back, foreshortened by cos(az) at 3/4; any x in profile). -> label image."""
    V, ppl, F = A['views'][view], A['sheet']['ppl'], A['F']
    H, W = shape
    out = np.full(shape, -1, np.int32)
    for k, p in enumerate(A['pieces']):
        yy, xx = p['mask'].pixels()
        x, z = to_L(F, xx[::7], yy[::7])
        if view == 'back':
            x = -x
        elif view == 'three_quarter':
            x = x * math.cos(math.radians(V['az']))
        elif view == 'profile':
            x = np.zeros_like(x)
        u = np.round(V['origin'][0] + x * ppl).astype(int)
        v = np.round(V['origin'][1] - z * ppl).astype(int)
        ok = (u >= 0) & (u < W) & (v >= 0) & (v < H)
        out[v[ok], u[ok]] = k
    out[~A['sheet']['design'][view]['fg']] = -1
    return out


# ----------------------------------------------------------------------------------------------------------- structure
REGION = {'head': 'head', 'neck': 'neck', 'upperChest': 'chest', 'chest': 'chest', 'spine': 'waist', 'hips': 'hips',
          'Shoulder': 'shoulder', 'UpperArm': 'upper arm', 'LowerArm': 'forearm', 'Hand': 'hand',
          'UpperLeg': 'thigh', 'LowerLeg': 'shin', 'Foot': 'foot'}
TORSO = ('hips', 'spine', 'chest', 'upperChest', 'neck', 'head')


def region_of(bone):
    for k, v in REGION.items():
        if bone == k or bone.endswith(k):
            return v
    return bone


def geometry(p, F):
    """a rig piece's shape in the rig's head-length frame: bbox, area, centroid, top edge, row widths (median, top and
    bottom 15%), flare (the widest row over the top quarter's median width), aspect (height over median width)."""
    ys, xs = p['mask'].pixels()
    x, z = to_L(F, xs, ys)
    ppl = F['ppl']
    top, bot = float(z.max()), float(z.min())
    h = top - bot
    rows = np.round((top - z) * ppl).astype(int)
    wid = np.bincount(rows) / ppl
    wid = wid[wid > 0]
    k = max(1, int(0.15 * len(wid)))
    q = max(1, int(0.25 * len(wid)))
    near_top = z >= top - 0.03
    return dict(bbox=[round(float(x.min()), 3), round(bot, 3), round(float(x.max()), 3), round(top, 3)],
                area=round(float(len(xs) / ppl ** 2), 4), centroid=[round(float(x.mean()), 3), round(float(z.mean()), 3)],
                top=[round(float(x[near_top].mean()), 3), round(top, 3)], height=round(h, 3),
                width=round(float(np.median(wid)), 3), width_top=round(float(np.median(wid[:k])), 3),
                width_bottom=round(float(np.max(wid[-k:])), 3),
                flare=round(float(np.max(wid) / max(1e-3, np.median(wid[:q]))), 2),
                aspect=round(float(h / max(1e-3, np.median(wid))), 2))


def field_frame(A):
    """field cells in the rig's head-length frame (the field fitted to the rig's front): (x her left, y depth toward
    the back, z up from the eye line)."""
    fr, Fd = A['field_fit_rig'], A['field']
    P = Fd['P']
    return np.stack([(P[:, 0] - fr['tx']) / fr['s'], P[:, 1] / fr['s'], (P[:, 2] - fr['tz']) / fr['s']], 1)


def _bone_frame(Q, bone_seg):
    """a bone's axis in 3D: through its middle, at the depth midway between the body's front and back there (every
    field cell within 0.06 L of that point across and up). -> (point, direction, e1, e2) or None."""
    (hx, hz), (tx, tz) = bone_seg
    xm, zm = (hx + tx) / 2, (hz + tz) / 2
    col = (np.abs(Q[:, 0] - xm) < 0.06) & (np.abs(Q[:, 2] - zm) < 0.06)
    if col.sum() < 4:
        return None
    ym = (Q[col, 1].min() + Q[col, 1].max()) / 2
    d = np.array([tx - hx, 0.0, tz - hz])
    d /= max(1e-9, np.linalg.norm(d))
    e1 = np.array([0.0, 1.0, 0.0]); e1 -= (e1 @ d) * d; e1 /= np.linalg.norm(e1)
    return np.array([xm, ym, zm]), d, e1, np.cross(d, e1)


def coverage(Q, cells, bone_seg, bins=36):
    """how far round a bone's axis (_bone_frame) a piece's field cells reach: the share of `bins` sectors round it
    holding 1% of them (2 at least); and its flare there: the cells' distance from the axis over their lowest fifth
    (down the bone: toward the hand or foot, or down the torso) against their highest. -> (coverage, flare) or
    (None, None)."""
    fr = _bone_frame(Q, bone_seg) if len(cells) else None
    if fr is None or len(cells) < 5:
        return None, None
    c, d, e1, e2 = fr
    if d[2] > 0:                                                    # measured down the bone: a torso bone points up
        d, e2 = -d, -e2
    v = Q[cells] - c
    along = v @ d
    v = v - np.outer(along, d)
    r = np.linalg.norm(v, axis=1)
    keep = r >= 0.5 * np.percentile(r, 75)                         # cells near the axis have no direction
    v, along, r = v[keep], along[keep], r[keep]
    if len(v) < 5:
        return None, None
    ang = np.arctan2(v @ e2, v @ e1)
    b = np.floor((ang + np.pi) / (2 * np.pi) * bins).astype(int) % bins
    cov = round(float((np.bincount(b, minlength=bins) >= max(2, 0.01 * len(v))).mean()), 3)
    lo, hi = np.percentile(along, 20), np.percentile(along, 80)
    top_r = np.median(r[along <= lo]) if (along <= lo).any() else np.nan
    bot_r = np.median(r[along >= hi]) if (along >= hi).any() else np.nan
    flare = round(float(bot_r / max(1e-3, top_r)), 2) if np.isfinite(top_r) and np.isfinite(bot_r) else None
    return cov, flare


def layer_groups(rig):
    """the 2D rig's own grouping of its layers (rig.json): {layer: 'head' | 'torso' | ('arm', her side) | ('leg', her
    side)}; the rig's image-left limbs are her right."""
    out = {}
    rj = rig or {}
    for l in (rj.get('head') or {}).get('layers', []):
        out[l] = 'head'
    for l in (rj.get('body') or {}).get('upper', []):
        out[l] = 'torso'
    for img, arm in (rj.get('arms') or {}).items():
        side = 'right' if img == 'L' else 'left'
        for l in arm.get('layers', []):
            out[l] = ('arm', side)
    pv = (rj.get('body') or {}).get('pelvis') or {}
    for l in list((pv.get('legs') or {}).keys()) + list(pv.get('feet') or []):
        out[l] = ('leg', 'right' if l.endswith('_L') else 'left')
    return out


def pick_bone(sk, group, g, mask, F, at):
    """the bone a piece lives on: on a limb (the rig groups its layer with an arm or leg) the limb bone its drawing
    covers most of, else the nearest; on the head the head; on the torso the torso bone at its centroid's height."""
    if group == 'head' and 'head' in sk:
        return 'head', 0.5
    if isinstance(group, tuple):
        kind, side = group
        names = [side + b for b in (('UpperArm', 'LowerArm', 'Hand') if kind == 'arm' else ('UpperLeg', 'LowerLeg', 'Foot'))]
        sub = {b: sk[b] for b in names if b in sk}
        b, t, _ = covered_bone(sub, mask, F, min_len=0.05)
        if b is None:
            b, t, _ = nearest_bone(sub, *g['centroid'])
        return b, t
    z = at[1]
    for b in ('head', 'neck', 'upperChest', 'chest', 'spine', 'hips'):
        if b in sk:
            (_, z0), (_, z1) = sk[b]
            lo, hi = min(z0, z1), max(z0, z1)
            if lo <= z <= hi or (b == 'hips' and z < lo):
                return b, float((z - z0) / (z1 - z0)) if z1 != z0 else 0.5
    b, t, _ = nearest_bone(sk, *at)
    return b, t


def covered_bone(sk, mask, F, min_len=0.1, grow=0.05):
    """the bone the piece covers most of in the rig's front (its 2D segment inside the drawing, grown by `grow` L) ->
    (bone, t of the covered part's middle, covered length L) or (None, 0, 0) under min_len."""
    from scipy import ndimage
    m = mask.m
    g = int(round(grow * F['ppl']))
    mm = ndimage.binary_dilation(np.pad(m, g), iterations=g) if g else m
    best = (None, 0.0, 0.0)
    for b, (h, t) in sk.items():
        h, t = np.array(h), np.array(t)
        ln = float(np.linalg.norm(t - h))
        ts = np.linspace(0, 1, max(2, int(ln / 0.01)))
        pts = h + np.outer(ts, t - h)
        px = np.round(F['eye'][0] + pts[:, 0] * F['ppl']).astype(int) - mask.x0 + g
        py = np.round(F['eye'][1] - pts[:, 1] * F['ppl']).astype(int) - mask.y0 + g
        ok = (px >= 0) & (px < mm.shape[1]) & (py >= 0) & (py < mm.shape[0])
        inside = np.zeros(len(ts), bool)
        inside[ok] = mm[py[ok], px[ok]]
        cl = inside.mean() * ln
        if cl > best[2] + 1e-9:
            best = (b, float(ts[inside].mean()) if inside.any() else 0.0, cl)
    return best if best[2] >= min_len else (None, 0.0, 0.0)


def layering(A):
    """over / under between touching pieces: across layers the rig's drawing order; within one layer a panel is set in
    (level with its piece), a cuff band lies over its piece, a tail hangs under its knot. -> (over {k: set of pieces it
    lies over}, layer number per piece: 1 + the deepest it lies over, body 0)."""
    P, n = A['pieces'], A['n']
    touch = (A['adjacency'][:n, :n] > 0) | A['layer_contacts']
    over = {k: set() for k in range(n)}
    for i in range(n):
        for j in range(n):
            if i == j or not touch[i, j]:
                continue
            a, b = P[i], P[j]
            if a['layer'] != b['layer']:
                if a['order'] > b['order']:
                    over[i].add(j)
            elif a.get('of') == j and a['rel'] == 'band':
                over[i].add(j)
            elif b.get('of') == i and b['rel'] == 'tail':
                over[i].add(j)
            elif a.get('of') == j and a['rel'] == 'panel' and b['type'] in ('bow', 'ribbon'):
                over[j].add(i)
            elif b.get('of') == i and b['rel'] == 'panel' and a['type'] in ('bow', 'ribbon'):
                over[i].add(j)
    level = {}

    def lv(k, seen=()):
        if k in level:
            return level[k]
        if k in seen:
            return 1
        level[k] = 1 + max([lv(j, seen + (k,)) for j in over[k]], default=0)
        return level[k]
    for k in range(n):
        lv(k)
    return over, level


def zone_contacts(A, k, zone='top', frac=0.2):
    """the labels touching a piece's outline in its top (or bottom) `frac` of its height in the rig's front
    -> {label index: pixel count}."""
    p, limg = A['pieces'][k], A['label_img']
    m = p['mask']
    ys, xs = m.pixels()
    top, bot = ys.min(), ys.max()
    h = bot - top + 1
    sel = ys <= top + frac * h if zone == 'top' else ys >= bot - frac * h
    ys, xs = ys[sel], xs[sel]
    st = max(2, int(0.012 * A['F']['ppl']))
    H, W = limg.shape
    out = {}
    for dy, dx in ((st, 0), (-st, 0), (0, st), (0, -st)):
        y2, x2 = np.clip(ys + dy, 0, H - 1), np.clip(xs + dx, 0, W - 1)
        l = limg[y2, x2]
        l = l[(l >= 0) & (l != k)]
        for a, b in zip(*np.unique(l, return_counts=True)):
            out[int(a)] = out.get(int(a), 0) + int(b)
    return out


def motion(g, cov, flare, bone, parent, hair=0.0, tucked=None, wraps=None, small=0.3, wrap=0.6, hang=0.3):
    """rigid / spring / cloth from the measured shape, with the reason. g: geometry(); cov, flare: coverage round the
    bone and flare down it (3D, else None: the drawing's flare then); hair: the share of its outline on the hair;
    tucked: the band its bottom edge is tucked into, if any.
      small (under `small` L both ways)                  rigid: it moves with what it is on
      wraps (cov >= wrap, or `wraps` given), flares 1.5x over 0.4 L or more, not on a forearm, hand, shin or foot
                                                          cloth: hangs free all round (a flared boot or cuff is a stiff shape)
      wraps otherwise                                     rigid: a band that follows the bone
      lies on the hair (hair >= 0.3)                      rigid
      tucked into a band at its bottom                    rigid: held at both ends
      hangs `hang` L or more, 1.5x longer than wide       spring: a chain from its top edge
      else                                                rigid: short and broad on what it lies on"""
    h, w = g['height'], g['width']
    on = parent or region_of(bone or 'body')
    fl = min(flare, g['flare']) if flare is not None else g['flare']
    if max(h, g['bbox'][2] - g['bbox'][0]) < small:
        return 'rigid', 'small (%.2f x %.2f L): moves with %s' % (g['bbox'][2] - g['bbox'][0], h, on)
    if wraps if wraps is not None else (cov is not None and cov >= wrap):
        cov = cov or 0.0
        if fl >= 1.5 and h >= 0.4 and not (bone or '').endswith(('LowerArm', 'Hand', 'LowerLeg', 'Foot')):
            return 'cloth', ('wraps the %s (%.0f%% of the way round) and flares %.1fx down to a hem %.2f L below its top: '
                             'hangs free all round' % (bone, 100 * cov, fl, h))
        return 'rigid', 'wraps the %s (%.0f%% of the way round), %.2f L tall, flare %.1fx: a band that follows the bone' % (
            bone, 100 * cov, h, fl)
    if hair >= 0.3:
        return 'rigid', 'lies on the hair (%.0f%% of its outline): moves with the head' % (100 * hair)
    if tucked:
        return 'rigid', 'hangs from %s but its bottom edge is tucked into %s: held at both ends' % (on, tucked)
    if h >= hang and g['aspect'] >= 1.5:
        return 'spring', ('attached along its top edge (to %s), free elsewhere; long and thin (%.2f x %.2f L); hangs %.2f L '
                          'below its attachment' % (on, h, w, h))
    return 'rigid', 'lies on %s; short and broad (%.2f x %.2f L, %s): stiff enough to follow it' % (
        on, h, w, 'wraps %.0f%%' % (100 * cov) if cov is not None else 'no 3D coverage')


def band_under(A, j, k):
    """how far (L) piece j's whole layer drawing runs on up under piece k above k's bottom edge, in k's columns: a
    waistband a bib is tucked into barely does; shorts under a skirt's hem run far up."""
    R, F = A['R'], A['F']
    mk = A['pieces'][k]['mask']
    am = R['alpha'][A['pieces'][j]['layer']]
    ys, xs = mk.pixels()
    bot = np.full(R['own'].shape[1], -1)
    np.maximum.at(bot, xs, ys)
    ay, ax = am.pixels()
    sel = bot[ax] >= 0
    if not sel.any():
        return 0.0
    rise = bot[ax[sel]] - ay[sel]
    return float(max(0.0, np.percentile(rise, 95)) / F['ppl'])


def seen_views(A, min_px=25, frac=0.03):
    """per piece the sheet views it is seen in: its assigned area there at least min_px and frac of its largest view's.
    -> {k: {view: area px}} (the seen ones), {k: {view: area px}} (all)."""
    n = A['n']
    area = {k: {vn: int((Av == k).sum()) for vn, Av in A['assigned'].items()} for k in range(n)}
    seen = {}
    for k, a in area.items():
        top = max(a.values()) if a else 0
        seen[k] = {vn: v for vn, v in a.items() if v >= max(min_px, frac * top)}
    return seen, area


def structure(A):
    """per piece: geometry, 3D extent (the field cells the sheet confirmed), attach (bone, t, region, contacts, parent
    guess), layer order, motion."""
    P, n, F = A['pieces'], A['n'], A['F']
    sk = F['skeleton']
    Q = field_frame(A) if A.get('field') is not None else None
    lab = A.get('field_labels')
    touch = A['adjacency']
    over, level = layering(A)
    groups = layer_groups(A['R'].get('rig'))
    HAIR = n + 1
    TORSO_WRAP = ('hips', 'spine', 'chest', 'upperChest')
    parent_bone = lambda b: __import__('charkit.mh', fromlist=['VRM_PARENT']).VRM_PARENT.get(b)

    def proximal(a, b):                          # bone a lies nearer the hips than bone b along the hierarchy
        x, seen = b, 0
        while x is not None and seen < 12:
            x = parent_bone(x); seen += 1
            if x == a:
                return True
        return False
    out = []
    for k, p in enumerate(P):
        g = geometry(p, F)
        cells = np.nonzero(lab == k)[0] if lab is not None else np.zeros(0, int)
        seen = cells[A['votes'][cells, k] > 0] if (lab is not None and len(cells)) else cells
        e3 = None
        if Q is not None and len(cells) >= 5:
            q = Q[cells]
            lo, hi = np.percentile(q, 1, 0), np.percentile(q, 99, 0)
            e3 = dict(bbox=[round(float(v), 3) for v in list(lo) + list(hi)], cells=int(len(cells)),
                      confirmed=round(float(len(seen) / len(cells)), 3))
        # the bone: the one the drawing covers most of, else the one nearest its top edge (in 3D where the drawing's
        # top is hidden: a back panel hangs from the waist behind the skirt)
        at = g['top']
        if Q is not None and len(seen) >= 5:
            q = Q[seen]
            ztop = np.percentile(q[:, 2], 98)
            if ztop > g['bbox'][3] + 0.1:
                at = [round(float(np.mean(q[q[:, 2] >= ztop - 0.05, 0])), 3), round(float(ztop), 3)]
        group = groups.get(p['layer'], 'torso')
        cen = g['centroid']
        if Q is not None and len(seen) >= 5:
            cen = [round(float(np.mean(Q[seen, 0])), 3), round(float(np.mean(Q[seen, 2])), 3)]
        bone, t = pick_bone(sk, group, g, p['mask'], F, cen)
        cov, flare = coverage(Q, seen, sk[bone]) if (Q is not None and bone) else (None, None)
        # contacts: pieces and body touching in the rig's front, and the pieces its layer lies on
        ct = {}
        for j in range(n + 2):
            if j != k and touch[k, j] > 0:
                ct[A['labels'][j]] = int(touch[k, j])
        for j in range(n):
            if j != k and A['layer_contacts'][k, j] and A['labels'][j] not in ct:
                ct[A['labels'][j]] = 0
        tz = zone_contacts(A, k, 'top')
        bz = zone_contacts(A, k, 'bottom')
        allz = zone_contacts(A, k, 'top', 1.0)
        hair = allz.get(HAIR, 0) / max(1, sum(allz.values()))
        out.append(dict(geometry=g, extent3d=e3, bone=bone, t=round(float(t), 3), group=group,
                        region=region_of(bone) if bone else None, attach_point=at, coverage=cov, flare3d=flare,
                        contacts=ct, top_contacts=tz, bottom_contacts=bz, hair_share=round(hair, 3),
                        over=sorted(P[j]['id'] for j in over[k]),
                        under=sorted(P[j]['id'] for j in range(n) if k in over[j]), layer=level[k]))
    seen, _ = seen_views(A)
    fb = {k: ('front' in seen[k] and 'back' in seen[k]) for k in range(n)}
    def _hangs(s_):                   # a wrapping piece that flares down to a free hem hangs from its top edge (a skirt)
        if s_['flare3d'] is None and s_['bone'] not in ('hips', 'spine'):
            return False                  # without 3D, only from the waist down
        fl_ = min(s_['flare3d'], s_['geometry']['flare']) if s_['flare3d'] is not None else s_['geometry']['flare']
        return fl_ >= 1.5 and s_['geometry']['height'] >= 0.4
    def wraps_(k, s_):
        if s_['coverage'] is None:            # no 3D: seen from the front and the back, across the body or round a limb
            return fb[k] and (P[k]['side'] == 'C' or isinstance(s_['group'], tuple))
        return s_['coverage'] >= 0.6 or (s_['coverage'] >= 0.35 and fb[k])
    wraps = {k: wraps_(k, s) for k, s in enumerate(out)}
    for k, s in enumerate(out):
        s['wraps'] = bool(wraps[k])
    for k, (p, s) in enumerate(zip(P, out)):
        # the parent guess (the annotation names the parent where it disagrees; the flag stays)
        if p['rel'] is not None:
            par, why = P[p['of']]['id'], {'panel': 'set into it', 'band': 'a band on its edge', 'tail': 'hangs from it'}[p['rel']]
        elif groups.get(p['layer']) == 'head':
            par, why = None, 'on the hair: the head'
        elif wraps[k] and not _hangs(s):
            cand = [(touch[k, j] + (5 if A['layer_contacts'][k, j] else 0), j) for j in range(n)
                    if j != k and wraps[j] and P[j].get('of') != k and (touch[k, j] > 0 or A['layer_contacts'][k, j]) and out[j]['bone']
                    and (proximal(out[j]['bone'], s['bone']) or (out[j]['bone'] == s['bone'] and out[j]['t'] < s['t'] - 0.05))]
            par, why = None, 'wraps the %s: on the body' % s['bone']
            if cand and s['bone'] not in TORSO_WRAP:
                c, j = max(cand)
                par, why = P[j]['id'], 'sewn to it: it wraps the %s, next to it on the %s' % (s['bone'], out[j]['bone'])
        else:
            zone = {j: c for j, c in s['top_contacts'].items() if j < n and j != k}
            above = {j: c for j, c in zone.items() if out[j]['geometry']['centroid'][1] > s['geometry']['top'][1] - 0.05}
            par, why = None, 'on the body'
            pick = above or {j: c for j, c in zone.items() if j in over[k]}
            if pick:
                j = max(pick, key=pick.get)
                par, why = P[j]['id'], 'touches its top edge (%d px)' % pick[j]
        s['parent'], s['parent_why'] = par, why
        tucked = None       # its bottom edge meets a band (wrapping, under 0.4 L tall) that doesn't run on up under it
        for j, c in sorted(s['bottom_contacts'].items(), key=lambda t: -t[1]):
            gj = out[j]['geometry'] if j < n else None
            if j < n and wraps.get(j) and j != k and P[j]['id'] != par and not wraps[k] and gj['height'] <= 0.4 and \
                    band_under(A, j, k) <= 0.1:
                tucked = P[j]['id']
                break
        s['tucked'] = tucked
        fl3 = s['flare3d'] if (s['flare3d'] is not None or s['bone'] in ('hips', 'spine')) else 1.0
        s['motion'], s['motion_why'] = motion(s['geometry'], s['coverage'], fl3, s['bone'], par,
                                              s['hair_share'], tucked, wraps[k])
    return out


# ------------------------------------------------------------------------------------------------ limbs, for the knobs
def along_bone(p, F, seg):
    """a piece's drawn pixels against a 2D bone: t range along it (5..95%) and the half-width across (90%), L."""
    ys, xs = p['mask'].pixels()
    x, z = to_L(F, xs[::3], ys[::3])
    h, t = np.array(seg[0]), np.array(seg[1])
    d = t - h
    ln = float(np.linalg.norm(d))
    u = d / ln
    q = np.stack([x, z], 1) - h
    tt = q @ u / ln
    across = np.abs(q @ np.array([-u[1], u[0]]))
    return float(np.percentile(tt, 5)), float(np.percentile(tt, 95)), float(np.percentile(across, 90)), ln


def limb_halfwidth(A, bone, t, band=0.04):
    """the drawn limb's half-width across a bone at t (L): the rig's skin layers of that limb, whole (the parts under
    the clothes too), within `band` L of t."""
    F, R = A['F'], A['R']
    groups = layer_groups(R.get('rig'))
    side = 'left' if bone.startswith('left') else 'right'
    kind = 'arm' if 'Arm' in bone or 'Hand' in bone else 'leg'
    seg = F['skeleton'].get(bone)
    if seg is None:
        return None
    h, tl = np.array(seg[0]), np.array(seg[1])
    d = tl - h; ln = float(np.linalg.norm(d)); u = d / ln
    vals = []
    for layer, g in groups.items():
        if g != (kind, side) or layer_type(layer) != '' or layer not in R['alpha']:
            continue
        ys, xs = R['alpha'][layer].pixels()
        x, z = to_L(F, xs[::2], ys[::2])
        q = np.stack([x, z], 1) - h
        tt = q @ u / ln
        sel = np.abs(tt - t) * ln <= band
        if sel.any():
            vals.append(np.abs(q[sel] @ np.array([-u[1], u[0]])))
    if not vals:
        return None
    return float(np.percentile(np.concatenate(vals), 90))


# ------------------------------------------------------------------------------------------------- notes, verification
def load_notes(path):
    p = _p(path)
    return json.load(open(p)) if os.path.exists(p) else None


def verify(A, st, notes):
    """the annotated vision pass against the measurement: each annotated piece matched to a measured one (its rig
    layer, side, colour and type), then every field compared; disagreements flagged. -> (match {note id: piece index},
    flags [dict(piece, field, notes, measured, note)])."""
    P = A['pieces']
    flags = []
    if not notes:
        return {}, flags
    seen, _ = seen_views(A)

    def colour_ok(name, k):
        cn = colour_name(A['fams'][P[k]['fam']]['rgb'])
        near = {'red': ('red', 'orange'), 'orange': ('orange', 'red', 'amber'), 'yellow': ('yellow', 'amber'),
                'cream': ('cream',), 'white': ('white', 'grey'), 'dark': ('dark', 'grey')}
        return cn in near.get(name, (name,))
    scores = []
    for a in notes['pieces']:
        for k, p in enumerate(P):
            sc = (2 if a.get('rig') == p['layer'] else 0) + (1 if a.get('side', 'C') == p['side'] else 0) + \
                 (2 if a.get('type') == p['type'] else 0) + (1 if colour_ok(a.get('colour'), k) else 0)
            if sc >= 3:
                scores.append((sc, a['id'], k))
    match, used = {}, set()
    for sc, aid, k in sorted(scores, key=lambda t: (-t[0], t[1], t[2])):
        if aid in match or k in used:
            continue
        match[aid] = k; used.add(k)
    ids = {aid: P[k]['id'] for aid, k in match.items()}
    for a in notes['pieces']:
        if a['id'] not in match:
            flags.append(dict(piece=a['id'], field='found', notes='annotated', measured=None,
                              note='annotated but no measured piece matches it (rig layer, side, colour, type)'))
    for k, p in enumerate(P):
        if k not in used:
            flags.append(dict(piece=p['id'], field='annotated', notes=None, measured=p['type'],
                              note='measured but not in the annotation'))
    for a in notes['pieces']:
        if a['id'] not in match:
            continue
        k = match[a['id']]
        p, s = P[k], st[k]
        def flag(field, nv, mv, note):
            flags.append(dict(piece=a['id'], field=field, notes=nv, measured=mv, note=note))
        if a.get('type') != p['type']:
            flag('type', a.get('type'), p['type'], 'the rule on the rig names it %r (%s)' % (p['type'], p['layer']))
        if a.get('side', 'C') != p['side']:
            flag('side', a.get('side'), p['side'], '')
        if not colour_ok(a.get('colour'), k):
            flag('colour', a.get('colour'), colour_name(A['fams'][p['fam']]['rgb']), 'the drawn colour names otherwise')
        pa = a.get('parent')
        pa_id = ids.get(pa, pa)
        if pa_id != s['parent']:
            flag('parent', pa_id, s['parent'], 'measured: %s' % s['parent_why'])
        if a.get('bone') and a['bone'] != s['bone']:
            near = s['bone'] and (mh_parent(a['bone']) == s['bone'] or mh_parent(s['bone']) == a['bone'])
            flag('bone', a['bone'], s['bone'], 'the next bone along' if near else '')
        if a.get('motion') and a['motion'] != s['motion']:
            flag('motion', a['motion'], s['motion'], s['motion_why'])
        av, mv = set(a.get('views', [])), set(seen[k])
        if av - mv:
            flag('views', sorted(av), sorted(mv), 'annotated in %s, not found there' % ', '.join(sorted(av - mv)))
        if mv - av:
            flag('views', sorted(av), sorted(mv), 'found in %s too' % ', '.join(sorted(mv - av)))
    return match, flags


def mh_parent(bone):
    from .mh import VRM_PARENT
    return VRM_PARENT.get(bone)


# ------------------------------------------------------------------------------------------------------------ templates
# a piece's type -> the template it maps to (charkit/garments.py kinds, charkit/accessories.py kinds): a kind of its own,
# or a knob of another piece's entry ("skirt.panel": the skirt's panel knob). The library is additive: a type missing
# here is a template gap, reported as such; the design never limits it.
TEMPLATES = {
    'top': 'shell', 'shorts': 'shell', 'boot': 'shell+shoe', 'boot cuff': 'band', 'cuff': 'band', 'sleeve cuff': 'band',
    'sleeve': 'sleeve', 'skirt': 'skirt', 'collar': 'collar', 'bow': 'bow', 'waistband': 'belt', 'overskirt panel': 'panel',
    'skirt panel': 'skirt.panel', 'bodice panel': 'shell.panel', 'bow tail': 'bow.tail', 'hair accessory': 'accessory',
}
ACCESSORY_WORDS = ('bun', 'star', 'crab')
TOP_REGION = [["hips", -1, 3], ["spine", -1, 3], ["chest", -1, 3], ["upperChest", -1, 3], ["neck", -1, 0.3],
              ["leftShoulder", -1, 3], ["rightShoulder", -1, 3], ["leftUpperArm", -1, 0.12], ["rightUpperArm", -1, 0.12]]


def _rgb(c):
    return [round(float(v), 3) for v in c]


def _r(v, d=3):
    return None if v is None else round(float(v), d)


def draft(G, A, st):
    """a draft garment and accessory list in spec format from the graph, with each knob's source ('measured' from the
    references, 'default' the template's or the usual value) and the template gaps. -> dict(garments, accessories,
    knobs {entry: {knob: source}}, gaps [...])."""
    P, F = A['pieces'], A['F']
    sk = F['skeleton']
    garments, acc, src, gaps = [], [], {}, []

    def add(entry, knobs, lib=garments):
        lib.append(entry); src[entry['name']] = knobs
    def first(t):
        return next((g for g in G['pieces'] if g['type'] == t), None)
    wb = first('waistband')
    for g in G['pieces']:
        k, t = g['_k'], g['type']
        p, s = P[k], st[k]
        geo = s['geometry']
        kind = TEMPLATES.get(t)
        side = {'L': 'left', 'R': 'right'}.get(g['side'])
        col = _rgb(g['colour']['srgb'])
        if kind is None:
            gaps.append(dict(piece=g['id'], type=t, need='a template for %r' % t))
            continue
        if kind == 'band':
            bone = s['bone']
            if bone not in sk:
                gaps.append(dict(piece=g['id'], type=t, need='a band needs a limb bone; measured %r' % bone)); continue
            t0, t1, half, ln = along_bone(p, F, sk[bone])
            tm = (t0 + t1) / 2
            lh = limb_halfwidth(A, bone, tm)
            e = dict(kind='band', name=g['id'], bone=bone, t=_r(tm, 2), width=_r((t1 - t0) * ln), 
                     offset=_r(max(0.01, half - lh) if lh else 0.03), thick=0.02, color=col)
            kn = dict(bone='measured', t='measured', width='measured', offset='measured' if lh else 'default', thick='default')
            tr = [x for x in g['trims'] if x['edge'] == 'top']
            if tr:
                gaps.append(dict(piece=g['id'], type=t, need="band: a trim colour along an edge (%s %s top edge)" % (
                    tr[0]['pattern'], tr[0]['colour']['name'])))
            add(e, kn)
        elif kind == 'sleeve':
            bone = s['bone']
            t0, t1, half, ln = along_bone(p, F, sk[bone])
            lh = limb_halfwidth(A, bone, 0.6)
            cf = [x for x in G['pieces'] if x['type'] == 'sleeve cuff' and x['attach']['parent'] == g['id']]
            t1_src = 'measured (the drawn end)'
            if cf:                                                  # the tube runs on under its cuff band
                c0, c1, _, _ = along_bone(P[cf[0]['_k']], F, sk[bone])
                t1, t1_src = max(t1, (c0 + c1) / 2), 'measured (to its cuff band)'
            e = dict(kind='sleeve', name=g['id'], side=side, puff=_r(np.clip(half / lh - 1, 0.2, 1.5) if lh else 0.85, 2),
                     t1=_r(t1, 2), color=col)
            add(e, dict(side='measured', puff='measured' if lh else 'default', t1=t1_src))
        elif kind == 'belt':
            add(dict(kind='belt', name=g['id'], waist=0.5, width=_r(geo['height']), offset=0.045, thick=0.025, color=col),
                dict(waist='default', width='measured', offset='default', thick='default'))
        elif kind == 'skirt':
            e, kn = _skirt_entry(g, A, st, G, wb)
            add(e, kn)
        elif kind == 'collar':
            back = g['extent'].get('back')
            e = dict(kind='collar', name=g['id'], v_depth=_r(geo['height'] * 1.9, 2), side_depth=0.34,
                     back_depth=_r(back['bbox'][3] - back['bbox'][1], 2) if back else 0.5, offset=0.03, color=col)
            kn = dict(v_depth='measured (the front halves' + "'" + ' drop, doubled round the curve)', side_depth='default',
                      back_depth='measured (back view)' if back else 'default', offset='default')
            st_ = [x for x in g['trims']]
            if st_:
                e['stripe_color'] = _rgb(st_[0]['colour']['srgb']); kn['stripe_color'] = 'measured'
            add(e, kn)
        elif kind == 'bow':
            size = (geo['bbox'][2] - geo['bbox'][0]) / 1.04
            ch, uc = sk.get('chest'), sk.get('upperChest')
            height = (geo['centroid'][1] - ch[0][1]) / (uc[1][1] - ch[0][1]) if ch and uc else 0.62
            tails = [x for x in G['pieces'] if x['type'] == 'bow tail' and x['attach']['parent'] == g['id']]
            e = dict(kind='bow', name=g['id'], size=_r(size, 2), height=_r(height, 2), offset=0.06, color=col)
            kn = dict(size='measured', height='measured', offset='default')
            if tails:
                drop = geo['centroid'][1] - min(st[x['_k']]['geometry']['bbox'][1] for x in tails)
                e['tail'] = _r(max(0.2, drop / max(1e-3, size) - 0.08), 2); kn['tail'] = 'measured (new knob)'
            add(e, kn)
        elif kind == 'panel':
            e, kn = _panel_entry(g, A, st, G, wb)
            add(e, kn)
        elif kind == 'shell':
            if t == 'top':
                e = dict(kind='shell', name=g['id'], region=TOP_REGION, offset=0.012, thick=0.01, color=col,
                         cuts=[["hips", 0.0, "above", 0.1], ["neck", 0.0, "below", 0.04]])
                kn = dict(region='default', offset='default', thick='default', cuts='default')
                bp = [x for x in G['pieces'] if x['type'] == 'bodice panel']
                if bp:
                    gb = st[bp[0]['_k']]['geometry']
                    e['panel'] = dict(color=_rgb(bp[0]['colour']['srgb']), **{'from': ["hips", 0.0]}, to=["upperChest", 0.25],
                                      half_top=_r(gb['width_top'] / 2), half_bottom=_r(gb['width_bottom'] / 2))
                    kn['panel'] = 'measured (half widths, colour; heights default)'
                add(e, kn)
            else:                                                   # shorts
                lt = sk.get('leftUpperLeg')
                t1 = (lt[0][1] - geo['bbox'][1]) / (lt[0][1] - lt[1][1]) if lt else 0.4
                t1 = float(np.clip(t1, 0.05, 0.9))
                add(dict(kind='shell', name=g['id'], region=[["hips", -1, 3], ["spine", -1, 3], ["leftUpperLeg", -1, _r(t1, 2)],
                                                            ["rightUpperLeg", -1, _r(t1, 2)]],
                         offset=0.008, thick=0.006, color=col, cuts=[["hips", 0.0, "below", 0.16]]),
                    dict(region='measured (the thighs to where the shorts end; the drawn leg starts at the crotch)',
                         offset='default', thick='default', cuts='default'))
        elif kind == 'shell+shoe':
            bone = s['bone']
            t0, t1, half, ln = along_bone(p, F, sk[bone]) if bone in sk else (0.34, 1.0, 0, 1)
            if not any(e_['name'] == 'boots' for e_ in garments):
                bones = sorted({st[x['_k']]['bone'] for x in G['pieces'] if x['type'] == 'boot' and st[x['_k']]['bone']})
                add(dict(kind='shell', name='boots', region=[[b, _r(t0, 2), 1.5] for b in bones], offset=0.016, thick=0.01,
                         color=col), dict(region='measured (from the boot top down the shin)', offset='default', thick='default'))
            sole = [x for x in g['trims'] if x['edge'] == 'bottom']
            e = dict(kind='shoe', name='shoe_' + g['side'], side=side, offset=0.02, sole=_r(sole[0]['thickness'] if sole else 0.07),
                     instep=0.12, color=col)
            kn = dict(side='measured', sole='measured' if sole else 'default', offset='default', instep='default')
            if sole:
                e['sole_color'] = _rgb(sole[0]['colour']['srgb']); kn['sole_color'] = 'measured'
            add(e, kn)
        elif kind == 'accessory':
            words = [w for w in ACCESSORY_WORDS if w in p['layer']]
            if not words:
                gaps.append(dict(piece=g['id'], type=t, need='an accessory template for %s' % p['layer'])); continue
            e, kn = _accessory_entry(g, words[0], A, st)
            add(e, kn, acc)
        # a type that is a knob of another's template (skirt.panel, shell.panel, bow.tail): its host entry measures it
    # a mirror pair's measured knobs averaged (the design is symmetric; each drawn side differs a little)
    for lib in (garments, acc):
        byname = {e['name']: e for e in lib}
        for e in lib:
            nm = e['name']
            if not nm.endswith('_L') or nm[:-2] + '_R' not in byname:
                continue
            o = byname[nm[:-2] + '_R']
            for key in set(e) & set(o):
                a, b = e[key], o[key]
                if key in ('name', 'kind', 'side', 'bone') or isinstance(a, bool) or not isinstance(a, (int, float)) \
                        or not isinstance(b, (int, float)) or not str(src[nm].get(key, '')).startswith('measured'):
                    continue
                if key == 'az':
                    m = round((abs(a) + abs(b)) / 2, 0)
                    e[key], o[key] = math.copysign(m, a), math.copysign(m, b)
                else:
                    m = round((a + b) / 2, 3)
                    e[key] = o[key] = m
                src[nm][key] = src[o['name']][key] = 'measured (mean of the pair)'
    # pieces a template only has as a knob of another, but which move on their own
    for g in G['pieces']:
        kind = TEMPLATES.get(g['type'], '')
        if '.' in kind and g['motion']['class'] in ('spring', 'cloth'):
            host = kind.split('.')[0]
            gaps.append(dict(piece=g['id'], type=g['type'], need=(
                "%s builds its %s as part of itself, weighted with it; this piece is %s: it needs a piece or chain of its "
                "own (springs[] has one)" % (host, kind.split('.')[1], g['motion']['class']))))
    added = [dict(template='garments.panel', for_type='overskirt panel',
                  note='new: a panel hung from the waist ring at an azimuth, with a stepped hem (the library had none)'),
             dict(template='garments.bow: tail', for_type='bow tail',
                  note="new knob: the tails' length as a share of the bow's size (0.62 before, the default)")]
    return dict(garments=garments, accessories=acc, knobs=src, gaps=gaps, added=added)


def _hem_z(mask, F):
    """the median over its columns of a drawn piece's lowest pixel, z in L."""
    ys, xs = mask.pixels()
    bot = np.full(xs.max() + 1, -1)
    np.maximum.at(bot, xs, ys)
    return float(np.median(to_L(F, 0, bot[bot >= 0])[1]))


def _skirt_entry(g, A, st, G, wb):
    P, F = A['pieces'], A['F']
    k = g['_k']
    geo = st[k]['geometry']
    col = _rgb(g['colour']['srgb'])
    waist_z = st[wb['_k']]['geometry']['centroid'][1] if wb else geo['bbox'][3]
    waist_half = st[wb['_k']]['geometry']['width'] / 2 if wb else geo['width_top'] / 2
    hem = _hem_z(P[k]['mask'], F)
    length = waist_z - hem
    hem_half = (geo['bbox'][2] - geo['bbox'][0]) / 2
    e = dict(kind='skirt', name=g['id'], waist=0.5, length=_r(length, 2),
             flare=_r(math.degrees(math.atan2(max(0.0, hem_half - waist_half), max(1e-3, length))), 1), color=col)
    kn = dict(waist='default', length='measured (waistband to the median hem, front)', flare='measured (waist to widest)')
    fr, bk = g['extent'].get('front'), g['extent'].get('back')
    if fr and bk:
        e['back'] = _r(max(0.0, fr['bbox'][1] - bk['bbox'][1]), 2); kn['back'] = 'measured (back hem below the front, sheet)'
    cells = [c for c in A['match'].get('front', {}).get('cells', [])
             if A['match']['front']['result'][c['id']]['label'] == k and c['area'] >= 40]
    if cells:
        e['pleats'] = int(np.clip(2 * len(cells), 8, 40)); kn['pleats'] = 'measured (front cells, doubled)'
    pan = [x for x in G['pieces'] if x['type'] == 'skirt panel' and x['attach']['parent'] == g['id']]
    if pan:
        gp = st[pan[0]['_k']]['geometry']
        e['panel'] = _r(math.asin(min(1.0, (gp['width_bottom'] / 2) / max(1e-3, hem_half))), 2)
        e['panel_color'] = _rgb(pan[0]['colour']['srgb'])
        kn['panel'] = 'measured (its half-width at the hem against the skirt, as an azimuth)'; kn['panel_color'] = 'measured'
    hem_tr = [x for x in g['trims'] if x['edge'] == 'bottom']
    if hem_tr:
        e['hem_color'] = _rgb(hem_tr[0]['colour']['srgb']); kn['hem_color'] = 'measured'
        if hem_tr[0]['pattern'] == 'stepped':
            e['repeat'] = 8; kn['repeat'] = 'default (the hem is stepped: %d steps seen)' % hem_tr[0]['steps']
    return e, kn


def _panel_entry(g, A, st, G, wb):
    """an overskirt panel: its azimuth round the hips from the field cells the sheet confirmed, its width from the back
    view, its length from the lowest view (the profile shows the tail's full drop)."""
    k = g['_k']
    s = st[k]
    col = _rgb(g['colour']['srgb'])
    e = dict(kind='panel', name=g['id'], waist=0.5, color=col, offset=0.02, flare=30)
    kn = dict(waist='default', offset='default (under the skirt)', flare='default')
    az = None
    if A.get('field') is not None and 'field_labels' in A:
        cells = np.nonzero((A['field_labels'] == k) & (A['votes'][:, k] > 0))[0]
        if len(cells) >= 5 and 'hips' in A['F']['skeleton']:
            Q = field_frame(A)
            fr = _bone_frame(Q, A['F']['skeleton']['hips'])
            if fr is not None:
                v = Q[cells] - fr[0]
                az = math.degrees(math.atan2(np.median(v[:, 0]), -np.median(v[:, 1])))
    if az is None:
        az = 150.0 * (1 if g['side'] == 'L' else -1)
        kn['az'] = 'default (back-side)'
    else:
        kn['az'] = 'measured (field cells round the hips)'
    e['az'] = _r(az, 0)
    bk = g['extent'].get('back')
    e['width'] = _r((bk['bbox'][2] - bk['bbox'][0]) if bk else s['geometry']['width'], 2)
    kn['width'] = 'measured (back view)' if bk else 'measured (front)'
    wbe = wb['extent'] if wb else {}
    drops = []
    for vn, ex in g['extent'].items():
        if vn in ('rig',) or not ex:
            continue
        top = wbe.get(vn, {}).get('bbox', [None, None, None, None])[1] if wbe.get(vn) else None
        if top is not None:
            drops.append(top - ex['bbox'][1])
    e['length'] = _r(max(drops) if drops else s['geometry']['height'], 2)
    kn['length'] = 'measured (the waistband to its lowest point, the view that shows most)' if drops else 'measured (front)'
    tr = [x for x in g['trims'] if x['edge'] == 'bottom']
    if tr:
        e['hem_color'] = _rgb(tr[0]['colour']['srgb']); kn['hem_color'] = 'measured'
        if tr[0]['pattern'] == 'stepped':
            e['hem'] = 'stepped'; e['repeat'] = 1; kn['hem'] = 'measured'; kn['repeat'] = 'default'
    return e, kn


def _accessory_entry(g, word, A, st):
    F = A['F']
    geo = st[g['_k']]['geometry']
    hc = ((A['R'].get('rig') or {}).get('head') or {}).get('center')
    xc, zc = to_L(F, *hc) if hc else (0.0, 0.1)
    x, z = geo['centroid'][0] - float(xc), geo['centroid'][1] - float(zc)
    w = geo['bbox'][2] - geo['bbox'][0]
    size = {'bun': w, 'star': w, 'crab': w / 0.84}[word]
    e = dict(kind=word, name=g['id'], az=_r(math.degrees(math.asin(np.clip(x / 0.6, -1, 1))), 0),
             el=_r(math.degrees(math.asin(np.clip(z / 0.7, -1, 1))), 0), size=_r(size, 2))
    kn = dict(az='measured (drawn position on the head)', el='measured (drawn position on the head)', size='measured')
    if word == 'bun':
        e['material'] = 'hair'; kn['material'] = 'measured (the hair colour)'
    else:
        e['color'] = _rgb(g['colour']['srgb']); kn['color'] = 'measured'
    return e, kn


# ----------------------------------------------------------------------------------------------- against the hand list
def _role(e):
    """what a spec entry is, for matching: (kind, side, bone or shell role)."""
    k = e.get('kind')
    side = e.get('side')
    if k == 'shell':
        bones = {r[0] for r in e.get('region', [])}
        role = 'top' if 'chest' in bones else 'boots' if any('LowerLeg' in b for b in bones) else \
            'shorts' if any('UpperLeg' in b for b in bones) else 'shell'
        return (k, None, role)
    if k == 'band':
        return (k, None, e.get('bone'))
    if k in ACCESSORY_WORDS:
        return (k, 'left' if (e.get('az') or 0) > 0 else 'right', None)
    return (k, side, None)


def compare_spec(D, spec, G):
    """the draft against the spec's hand-written garments and accessories: matched (with each shared numeric knob,
    draft against hand), represented only as a knob in the hand list, missed by the hand list, and extra in it."""
    hand = [dict(e, _lib='garments', _nm=e.get('name') or 'garments[%d] %s' % (j, e.get('kind')))
            for j, e in enumerate(spec.get('garments', []))] + \
           [dict(e, _lib='accessories', _nm=e.get('name') or 'accessories[%d] %s' % (j, e.get('kind')))
            for j, e in enumerate(spec.get('accessories', []))]
    draft_ = [dict(e, _lib='garments') for e in D['garments']] + [dict(e, _lib='accessories') for e in D['accessories']]
    used, matched, missed = set(), [], []
    for e in draft_:
        r = _role(e)
        cand = [i for i, h in enumerate(hand) if i not in used and _role(h) == r]
        if not cand and r[1] is None and e['kind'] in ACCESSORY_WORDS:
            cand = [i for i, h in enumerate(hand) if i not in used and h.get('kind') == e['kind']]
        if cand:
            i = cand[0]
            used.add(i)
            h = hand[i]
            kn = {}
            for key in sorted(set(e) & set(h)):
                if key in ('name', 'kind', 'side', 'bone') or key.startswith('_'):
                    continue
                a, b = e[key], h[key]
                if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
                    kn[key] = dict(draft=a, hand=b, delta=round(float(a - b), 3))
                elif a != b:
                    kn[key] = dict(draft=a, hand=b)
            only = sorted(k for k in set(e) - set(h) if not k.startswith('_'))
            matched.append(dict(draft=e['name'], hand=h['_nm'], kind=e['kind'], library=e['_lib'],
                                knobs=kn, draft_only=only, hand_only=sorted(k for k in set(h) - set(e) if not k.startswith('_'))))
        else:
            missed.append(dict(draft=e['name'], kind=e['kind'], library=e['_lib'],
                               why='no hand entry of this kind' + (' and side' if r[1] else '')))
    as_knob = []
    for g in G['pieces']:
        kind = TEMPLATES.get(g['type'], '')
        if '.' not in kind:
            continue
        host, knob = kind.split('.')
        hk = [h for h in hand if h.get('kind') == ('shell' if host == 'shell' else host)]
        present = [h['_nm'] for h in hk if knob in h]
        built_in = [h['_nm'] for h in hk] if (host == 'bow' and knob == 'tail') else []
        if present:
            note = "in the hand list only as %s's %r knob: no piece, motion or chain of its own" % (present[0], knob)
        elif built_in:
            note = "in the hand list only inside %s: the bow template builds its tails (a fixed length), weighted with it" % built_in[0]
        else:
            note = 'missing from the hand list'
        as_knob.append(dict(piece=g['id'], type=g['type'], motion=g['motion']['class'],
                            hand='%s.%s' % ((present or built_in)[0], knob) if (present or built_in) else None, note=note))
    extra = [dict(hand=h['_nm'], kind=h['kind'], library=h['_lib']) for i, h in enumerate(hand) if i not in used]
    return dict(matched=matched, knob_only=as_knob, missed_by_hand=missed, extra_in_hand=extra)


# --------------------------------------------------------------------------------------------------------------- springs
def springs(G, A, st, seg_L=0.15):
    """spring-chain specs for the spring and cloth pieces, as data for the rig / VRM exporter (VRMC_springBone): a
    chain from the attachment down the piece's length (the field cells the sheet confirmed, sliced by height; else
    the front drawing at depth 0), started at its parent's lower edge when the confirmed part begins lower (a panel
    hung under a skirt); a ring of chains round the bone for cloth; a stiffness from its size (longer and wider swings
    slower). Positions in L in the rig's frame: x her left, y toward her back, z up from the
    eye line."""
    P, F = A['pieces'], A['F']
    out = []
    Q = field_frame(A) if A.get('field') is not None and 'field_labels' in A else None
    for g in G['pieces']:
        cls = g['motion']['class']
        if cls not in ('spring', 'cloth'):
            continue
        k, s = g['_k'], st[g['_k']]
        geo = s['geometry']
        pts = None
        if Q is not None:
            cells = np.nonzero((A['field_labels'] == k) & (A['votes'][:, k] > 0))[0]
            if len(cells) >= 12:
                pts = Q[cells]
        if pts is None:
            ys, xs = P[k]['mask'].pixels()
            x, z = to_L(F, xs[::5], ys[::5])
            pts = np.stack([x, np.zeros_like(x), z], 1)
        length = float(pts[:, 2].max() - pts[:, 2].min())
        width = float(geo['width'])
        chains = []
        if cls == 'cloth' and s['bone'] in F['skeleton']:
            fr = _bone_frame(Q, F['skeleton'][s['bone']]) if Q is not None else None
            c = fr[0] if fr is not None else np.array([0.0, 0.0, geo['centroid'][1]])
            ang = np.degrees(np.arctan2(pts[:, 0] - c[0], -(pts[:, 1] - c[1])))
            for a in range(0, 360, 45):
                d = (ang - (a if a <= 180 else a - 360) + 180) % 360 - 180
                sel = np.abs(d) <= 22.5
                if sel.sum() >= 8:
                    chains.append(dict(az=a if a <= 180 else a - 360, joints=_chain(pts[sel], seg_L)))
        else:
            chains.append(dict(joints=_chain(pts, seg_L)))
        # hung from a piece above what the sheet confirmed (a back panel under the skirt): the chain starts at it
        par = next((x for x in G['pieces'] if x['id'] == g['attach']['parent']), None)
        if par is not None:
            zp = par['extent']['rig']['bbox'][1]
            for c in chains:
                if c['joints'] and zp > c['joints'][0][2] + 0.1:
                    c['joints'].insert(0, [c['joints'][0][0], c['joints'][0][1], round(float(zp), 3)])
                    c['root'] = 'at %s' % par['id']
            length = max(length, max((c['joints'][0][2] - c['joints'][-1][2]) for c in chains if c['joints']))
        stiff = round(float(np.clip(0.35 / max(0.1, length), 0.2, 1.5)), 2)
        drag = round(float(np.clip(0.3 + 0.5 * width / max(0.1, length), 0.3, 0.8)), 2)
        out.append(dict(piece=g['id'], motion=cls, root_bone=g['attach']['bone'], length=round(length, 3),
                        chains=chains, stiffness=stiff, drag=drag, gravity=0.3 if cls == 'cloth' else 0.2,
                        gravity_dir=[0, 0, -1], hit_radius=round(0.3 * min(width, 0.3), 3),
                        why='stiffness 0.35 / length (%.2f L), drag 0.3 + 0.5 width / length (width %.2f L)' % (length, width)))
    return out


def _chain(pts, seg_L):
    """joints down a set of points: the top (mean of the highest 5%) then the mean point of each slice by height,
    one per seg_L of drop (3 to 8 joints)."""
    z = pts[:, 2]
    top, bot = float(np.percentile(z, 98)), float(np.percentile(z, 1))
    n = int(np.clip(round((top - bot) / seg_L) + 1, 3, 8))
    edges = np.linspace(top, bot, n)
    joints = []
    for ze in edges:
        half = (top - bot) / max(1, n - 1) / 2
        sel = np.abs(z - ze) <= max(half, 0.02)
        q = pts[sel] if sel.any() else pts[np.argsort(np.abs(z - ze))[:3]]
        joints.append([round(float(v), 3) for v in q.mean(0)])
    return joints


# ------------------------------------------------------------------------------------------------------------ the graph
def _hex(c):
    return '#%02x%02x%02x' % tuple(int(round(v * 255)) for v in np.clip(np.asarray(c, float), 0, 1))


def _colour(rgb, extra=None):
    out = dict(srgb=_rgb(rgb), hex=_hex(rgb), name=colour_name(rgb))
    out.update(extra or {})
    return out


def _main_class(A, k):
    from .bodyqa import CLASS, HAIR_SPLIT, family
    p = A['pieces'][k]
    c = int(family(np.asarray(A['fams'][p['fam']]['rgb'])[None])[0])
    ys, _ = p['mask'].pixels()
    if c == CLASS['orange'] and to_L(A['F'], 0, ys.mean())[1] > HAIR_SPLIT:
        c = CLASS['hair']
    return c


def piece_colour(A, k):
    """a piece's colour: the rig's median over its own colour family's pixels, and the sheet's lit and shade tones
    (charkit.paletteqa.tones) over the pixels matched to it in every view, in its own class, a pixel in from edges."""
    from . import paletteqa
    from .bodyqa import erode
    p = A['pieces'][k]
    ys, xs = p['mask'].pixels()
    own = A['fam_img'][ys, xs] == p['fam']
    rgb = np.median(A['R']['rgb'][ys[own], xs[own]], 0) if own.any() else np.median(A['R']['rgb'][ys, xs], 0)
    extra = {}
    if A.get('views'):
        mc = _main_class(A, k)
        px = []
        for vn in A['views']:
            dv = A['sheet']['design'][vn]
            m = erode((A['assigned'][vn] == k) & (dv['raw'] == mc), 1)
            if m.any():
                px.append(dv['rgb'][m])
        if px:
            t = paletteqa.tones(np.concatenate(px))
            extra['sheet'] = dict(lit=_hex(t['lit']), shade=_hex(t['shade']) if t['shade'] is not None else None, px=t['px'])
    return _colour(rgb, extra)


def _extent(mask, to_L_, px_per_L):
    ys, xs = np.nonzero(mask)
    if not len(ys):
        return None
    x0, z1 = to_L_(xs.min(), ys.min()); x1, z0 = to_L_(xs.max() + 1, ys.max() + 1)
    return dict(bbox=[_r(x0), _r(z0), _r(x1), _r(z1)], area=_r(len(ys) / px_per_L ** 2, 4), px=int(len(ys)),
                outline=outline(mask, to_L_))


def graph(A, st, notes=None, notes_path=None):
    """the outfit component graph (JSON-ready): the measurement merged with the annotation (its names, types and
    parents where it gives them; every disagreement flagged), the extents per view and in 3D, the views each piece is
    seen in, and the sources."""
    import functools
    P, n, F = A['pieces'], A['n'], A['F']
    match, flags = verify(A, st, notes)
    rev = {k: aid for aid, k in match.items()}
    ann = {a['id']: a for a in (notes or {}).get('pieces', [])}
    fid = {P[k]['id']: rev.get(k, P[k]['id']) for k in range(n)}
    fid.update({'skin': 'skin', 'hair': 'hair'})
    seen, area = seen_views(A)
    rig_to_L = functools.partial(_rig_to_L, F, 4)
    pieces = []
    for k, p in enumerate(P):
        s = st[k]
        a = ann.get(rev.get(k))
        gid = fid[p['id']]
        pf = [dict(f, piece=gid) for f in flags if f['piece'] in (rev.get(k), p['id'])]
        par_m = fid.get(s['parent'], s['parent']) if s['parent'] else None
        if a is not None and 'parent' in a:
            par, par_from = a['parent'], 'notes'
        else:
            par, par_from = par_m, 'measured'
        ext = {}
        small = p['mask'].m[::4, ::4]
        ext['rig'] = dict(_extent(small, lambda px, py: rig_to_L(px, py, p['mask']), F['ppl'] / 4), frame='rig')
        for vn in A.get('views', {}):
            e = _extent(A['assigned'][vn] == k, A['toL'][vn], A['sheet']['ppl'])
            if e:
                ext[vn] = e
        sv = sorted(seen[k], key=VIEWS.index)
        if len(sv) < 2:
            pf.append(dict(piece=gid, field='views', notes=None, measured=sv,
                           note='seen in %d sheet view%s (areas %s): below the two the intake asks for' % (
                               len(sv), '' if len(sv) == 1 else 's', {v: a_ for v, a_ in area[k].items() if a_})))
        pieces.append(dict(
            id=gid, _k=k, type=(a or {}).get('type', p['type']), name=(a or {}).get('name'), side=p['side'],
            pair=(p.get('pair') and fid.get(p['id'], gid)[:-2]) if p.get('pair') else None,
            colour=piece_colour(A, k),
            trims=[dict(colour=_colour(t['rgb']), edge=t['edge'], pattern=t['pattern'], steps=t['steps'], height=t['height'],
                        thickness=t['thickness'])
                   for t in p['trims']],
            attach=dict(bone=s['bone'], t=s['t'], region=s['region'], parent=par, parent_from=par_from, parent_measured=par_m,
                        parent_why=s['parent_why'], point=s['attach_point'],
                        contacts={fid.get(c, c): v for c, v in sorted(s['contacts'].items())}),
            layer=dict(n=s['layer'], over=[fid[x] for x in s['over']], under=[fid[x] for x in s['under']]),
            extent=ext, extent3d=s['extent3d'],
            views=dict(seen=sv, areas={v: area[k][v] for v in VIEWS if v in area[k]}),
            motion=dict({'class': s['motion']}, why=s['motion_why'], coverage=s['coverage'], flare3d=s['flare3d'],
                        wraps=s['wraps'], tucked=fid.get(s['tucked'], s['tucked']) if s['tucked'] else None,
                        notes=(a or {}).get('motion')),
            sources=dict(rig_layer=p['layer'], rel=p['rel'], of=fid[P[p['of']]['id']] if p['of'] is not None else None,
                         measured_id=p['id'], measured_type=p['type'], annotated=a is not None),
            flags=pf))
    for g in pieces:                                                # pair ids from the final ids
        if g['pair']:
            g['pair'] = g['id'][:-2] if g['id'].endswith(('_L', '_R')) else g['id']
    unmatched = {}
    from .bodyqa import CLASS
    inv = {v: k for k, v in CLASS.items()}
    for vn, mt in A.get('match', {}).items():
        rows = []
        for c in mt['cells']:
            r = mt['result'][c['id']]
            if r['label'] >= 0 or r.get('body') or c['area'] < 25:
                continue
            x0, y0, x1, y1 = c['box']
            (a0, b1), (a1, b0) = A['toL'][vn](x0, y0), A['toL'][vn](x1, y1)
            rows.append(dict(cls=inv.get(c['cls']), px=c['area'], bbox=[_r(a0), _r(b0), _r(a1), _r(b1)]))
        if rows:
            unmatched[vn] = rows
    G = dict(name=A['spec'].get('name'), format='charkit-outfit/1', version=VERSION,
             generated_by=dict(tool='charkit.outfit', version=VERSION,
                               command='python -m charkit outfit %s' % A['spec'].get('_path', 'SPEC')),
             frame=dict(units='head lengths L', z='up from the eye line',
                        x=("per sheet view: toward the image's right from the view's origin (front and 3/4: the eyes' "
                           "middle; profile: the near eye; back: the head's axis), as charkit.bodyqa.design_views grids; "
                           "rig and 3D: toward her left from the rig's eyes' middle"),
                        y='3D only: toward her back', side='L her left, R her right, C centre'),
             sources=_sources(A, notes, notes_path), pieces=pieces,
             skeleton={b: [list(h), list(t)] for b, (h, t) in F['skeleton'].items()},
             unmatched=unmatched, flags=[f for g in pieces for f in g['flags']] +
             [dict(f) for f in flags if f['field'] == 'found'])
    return G


def _rig_to_L(F, step, px, py, mask):
    return to_L(F, np.asarray(px) * step + mask.x0, np.asarray(py) * step + mask.y0)


def _sources(A, notes, notes_path):
    out = dict(rig=dict(path=A['R']['dir'].replace(ROOT + os.sep, ''), ppl=_r(A['F']['ppl'], 2),
                        eye=[_r(v, 1) for v in A['F']['eye']], layers=len(A['R']['names'])))
    if A.get('views'):
        out['sheet'] = dict(path=A['sheet']['path'], ppl=_r(A['sheet']['ppl'], 2), az_three_quarter_eyes=A['sheet']['az3_eyes'],
                            views={vn: dict(az=_r(A['field_fits'][vn]['az'], 1) if A.get('field_fits') else v['az'],
                                            field_iou=A['field_fits'][vn]['iou'] if A.get('field_fits') else None,
                                            cut=v['cut'], cells=len(A['match'][vn]['cells']),
                                            adjacency_moves=len(A['match'][vn].get('adjacency', [])),
                                            landmark_cells=len(A['match'][vn].get('landmark', [])))
                                   for vn, v in A['views'].items()})
    if A.get('field') is not None:
        Fd = A['field']
        tot = A['votes'].sum(1) > 0
        out['field'] = dict(path=Fd['path'].replace(ROOT + os.sep, ''), cells=int(len(Fd['P'])), grid=Fd['R'],
                            rig_fit_iou=A['field_fit_rig']['iou'], seeds=int(A['field_seeds'].sum()), voted=int(tot.sum()),
                            vote_agrees_with_prediction=_r(A['vote_agree'][tot].mean(), 3))
    if notes:
        out['notes'] = dict(path=notes_path, version=notes.get('version'), **notes.get('provenance', {}))
    return out


# ---------------------------------------------------------------------------------------------------------- the picture
def palette(n):
    """n distinct colours, deterministic: hues round the wheel, alternating two values."""
    import colorsys
    return [colorsys.hsv_to_rgb((i * 0.618034) % 1.0, 0.85, 0.95 if i % 2 else 0.7) for i in range(n)]


def picture(A, G, path, scale=2):
    """each sheet view with every piece outlined and labelled (what the matching gave it; red boxes: cells no piece
    took), then the rig's front with its pieces (layer > piece) and the field from four sides coloured by its voted
    labels (skin pale, hair brown)."""
    from PIL import Image, ImageDraw, ImageFont
    from skimage import measure
    n = A['n']
    cols = palette(n)
    font = ImageFont.load_default(size=9 * scale)
    ids = {g['_k']: g['id'] for g in G['pieces']}

    def outline_(dr, m, c, sc, off=(0, 0)):
        for cc in measure.find_contours(np.pad(m, 1).astype(float), 0.5):
            pts = [((x - 1) * sc + off[0], (y - 1) * sc + off[1]) for y, x in cc[::2]]
            if len(pts) > 2:
                dr.line(pts + [pts[0]], fill=c, width=2)
    tiles = []
    for vn in VIEWS:
        if vn not in A.get('views', {}):
            continue
        dv = A['sheet']['design'][vn]
        base = np.where(dv['fg'][..., None], 0.6 * dv['rgb'] + 0.4, 0.15 * dv['rgb'] + 0.85)
        im = Image.fromarray((np.clip(base, 0, 1) * 255).astype(np.uint8)).resize(
            (base.shape[1] * scale, base.shape[0] * scale), Image.LANCZOS)
        dr = ImageDraw.Draw(im)
        Av = A['assigned'][vn]
        labels = []
        for k in range(n):
            m = Av == k
            if m.sum() < 4:
                continue
            outline_(dr, m, tuple(int(255 * v) for v in cols[k]), scale)
            ys, xs = np.nonzero(m)
            labels.append((xs.mean() * scale, ys.mean() * scale, ids[k], cols[k]))
        for c in A['match'][vn]['cells']:
            r = A['match'][vn]['result'][c['id']]
            if r['label'] < 0 and not r.get('body') and c['area'] >= 25:
                x0, y0, x1, y1 = c['box']
                dr.rectangle([x0 * scale, y0 * scale, x1 * scale, y1 * scale], outline=(220, 0, 0), width=2)
        for x, y, t, c in labels:
            w = dr.textlength(t, font=font)
            dr.rectangle([x - w / 2 - 2, y - 6 * scale, x + w / 2 + 2, y + 5 * scale], fill=(255, 255, 255))
            dr.text((x - w / 2, y - 5 * scale), t, fill=tuple(int(160 * v) for v in c), font=font)
        dr.text((8, 6), '%s (az %s)' % (vn, G['sources']['sheet']['views'][vn]['az']), fill=(0, 0, 0), font=font)
        tiles.append(im)
    row1 = _hstack(tiles)
    R = A['R']
    own = R['own']
    ys, xs = np.nonzero(own >= 0)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    st_ = max(1, int(np.ceil((y1 - y0) / row1.height)))
    rgb = R['rgb'][y0:y1:st_, x0:x1:st_]
    alpha = (own[y0:y1:st_, x0:x1:st_] >= 0)[..., None]
    rim = Image.fromarray((np.clip(np.where(alpha, 0.6 * rgb + 0.4, 1.0), 0, 1) * 255).astype(np.uint8))
    dr = ImageDraw.Draw(rim)
    labels = []
    for k, p in enumerate(A['pieces']):
        m = p['mask'].full(own.shape)[y0:y1:st_, x0:x1:st_]
        outline_(dr, m, tuple(int(255 * v) for v in cols[k]), 1)
        yy, xx = np.nonzero(m)
        if len(yy):
            labels.append((xx.mean(), yy.mean(), '%s > %s' % (p['layer'], ids[k]), cols[k]))
    for x, y, t, c in labels:
        w = dr.textlength(t, font=font)
        dr.rectangle([x - w / 2 - 2, y - 6 * scale, x + w / 2 + 2, y + 5 * scale], fill=(255, 255, 255))
        dr.text((x - w / 2, y - 5 * scale), t, fill=tuple(int(160 * v) for v in c), font=font)
    dr.text((8, 6), 'rig: layer > piece', fill=(0, 0, 0), font=font)
    tiles2 = [rim]
    if A.get('field') is not None and 'field_labels' in A:
        lab_ = A['field_labels']
        C = np.array([cols[l] if l < n else ((0.95, 0.88, 0.84) if l == n else (0.55, 0.38, 0.32)) for l in range(n + 2)])
        Pc = np.where(lab_[:, None] >= 0, C[np.maximum(lab_, 0)], 0.6)
        for az, nm in ((0, 'front'), (45, '3/4'), (90, 'her left'), (180, 'back')):
            tiles2.append(_splat(A['field']['P'], Pc, az, rim.height, 'field, %s' % nm, font))
    row2 = _hstack(tiles2)
    W = max(row1.width, row2.width)
    out = Image.new('RGB', (W, row1.height + row2.height + 8), (255, 255, 255))
    out.paste(row1, (0, 0)); out.paste(row2, (0, row1.height + 8))
    out.save(path)
    return path


def _hstack(ims, pad=6):
    from PIL import Image
    H = max(i.height for i in ims)
    out = Image.new('RGB', (sum(i.width for i in ims) + pad * (len(ims) - 1), H), (255, 255, 255))
    x = 0
    for i in ims:
        out.paste(i, (x, 0)); x += i.width + pad
    return out


def _splat(P, C, az, size, label, font=None):
    """field cells seen from az, flat-coloured by label, the unit cube's height framed, cropped to what shows."""
    from PIL import Image, ImageDraw
    r, t = view_axes(az)
    u = (P @ r + 0.5) * (size - 1)
    v = (0.5 - P[:, 2]) * (size - 1)
    idx, _ = zbuffer(u, v, -(P @ t), size, size, 1)
    im = np.ones((size, size, 3))
    im[idx >= 0] = C[idx[idx >= 0]]
    cols = np.nonzero((idx >= 0).any(0))[0]
    c0, c1 = max(0, cols.min() - 10), min(size, cols.max() + 11)
    out = Image.fromarray((im[:, c0:c1] * 255).astype(np.uint8))
    ImageDraw.Draw(out).text((8, 6), label, fill=(0, 0, 0), font=font)
    return out


# ----------------------------------------------------------------------------------------------------- report, manifest
def report(G, path):
    """the graph, the comparison with the spec and the template gaps as markdown."""
    L = ['# %s: outfit component graph' % G['name'], '']
    L += ['| piece | type | side | bone (t) | parent | layer | colour | motion | views |', '|---|---|---|---|---|---|---|---|---|']
    for g in G['pieces']:
        a = g['attach']
        L.append('| %s | %s | %s | %s (%.2f) | %s | %d | %s | %s | %s |' % (
            g['id'], g['type'], g['side'], a['bone'], a['t'], a['parent'] or '-', g['layer']['n'], g['colour']['hex'],
            g['motion']['class'], ', '.join(g['views']['seen'])))
    C = G.get('comparison', {})
    L += ['', '## Against the hand-written list', '', '**Matched** (draft -> hand; knob draft / hand):', '']
    for m in C.get('matched', []):
        kn = ', '.join('%s %s / %s' % (k, v['draft'], v['hand']) for k, v in m['knobs'].items()
                       if not isinstance(v['draft'], (list, dict)))
        L.append('- %s -> %s (%s): %s' % (m['draft'], m['hand'], m['kind'], kn or 'no shared numeric knobs'))
    L += ['', '**Only a knob in the hand list** (no piece, motion or chain of their own):', '']
    L += ['- %s (%s, %s): %s' % (x['piece'], x['type'], x['motion'], x['note']) for x in C.get('knob_only', [])]
    L += ['', '**Missed by the hand list:**', '']
    L += ['- %s (%s): %s' % (x['draft'], x['kind'], x['why']) for x in C.get('missed_by_hand', [])] or ['- none']
    L += ['', '**Extra in the hand list:**', '']
    L += ['- %s (%s)' % (x['hand'], x['kind']) for x in C.get('extra_in_hand', [])] or ['- none']
    L += ['', '## Template gaps', '']
    L += ['- %s (%s): %s' % (x['piece'], x['type'], x['need']) for x in G.get('templates', {}).get('gaps', [])] or ['- none']
    L += ['', '## Springs', '']
    for s in G.get('springs', []):
        L.append('- %s: %s, %d chain(s) of %s joints from %s, stiffness %.2f, drag %.2f' % (
            s['piece'], s['motion'], len(s['chains']), '/'.join(str(len(c['joints'])) for c in s['chains']), s['root_bone'],
            s['stiffness'], s['drag']))
    L += ['', '## Flags', '']
    L += ['- %s: %s: notes %s, measured %s. %s' % (f['piece'], f['field'], f.get('notes'), f.get('measured'), f.get('note', ''))
          for f in G['flags']] or ['- none']
    open(path, 'w').write('\n'.join(L) + '\n')
    return path


def dumps(o, indent=1, level=0):
    """JSON with dicts indented and short lists (numbers, or lists of numbers: a bbox, an outline) on one line."""
    pad, pad1 = ' ' * (indent * level), ' ' * (indent * (level + 1))
    flat = lambda x: isinstance(x, (int, float, str, bool)) or x is None
    if isinstance(o, dict):
        if not o:
            return '{}'
        return '{\n' + ',\n'.join('%s%s: %s' % (pad1, json.dumps(str(k)), dumps(v, indent, level + 1)) for k, v in o.items()) + \
            '\n' + pad + '}'
    if isinstance(o, (list, tuple)):
        if all(flat(x) for x in o) or all(isinstance(x, (list, tuple)) and all(flat(y) for y in x) for x in o):
            return json.dumps(o, separators=(', ', ': '))
        return '[\n' + ',\n'.join(pad1 + dumps(x, indent, level + 1) for x in o) + '\n' + pad + ']'
    return json.dumps(o)


def _value_end(t, i):
    """the end of the JSON value starting at t[i]."""
    if t[i] in '{[':
        depth, instr, esc = 0, False, False
        for j in range(i, len(t)):
            c = t[j]
            if instr:
                esc = (c == '\\') and not esc
                if c == '"' and not esc:
                    instr = False
                continue
            if c == '"':
                instr = True
            elif c in '{[':
                depth += 1
            elif c in '}]':
                depth -= 1
                if depth == 0:
                    return j + 1
    if t[i] == '"':
        return json.decoder.scanstring(t, i + 1)[1]
    j = i
    while j < len(t) and t[j] not in ',}]\n':
        j += 1
    return j


def _members(t, ob):
    """the top-level members of the JSON object whose '{' is at t[ob] -> [(key, key start, value end)], object end."""
    oe = _value_end(t, ob)
    out, i = [], ob + 1
    while i < oe - 1:
        if t[i] == '"':
            key, k_end = json.decoder.scanstring(t, i + 1)
            v = t.index(':', k_end) + 1
            while t[v] in ' \n\t':
                v += 1
            ve = _value_end(t, v)
            out.append((key, i, ve))
            i = ve
        i += 1
    return out, oe


def set_member(text, parent, key, value, indent=2):
    """the manifest's text with `key` set in the object under the top-level `parent`, the rest of the file as it was
    written (a hand-laid file keeps its layout, so concurrent edits to other entries still merge)."""
    top, _ = _members(text, text.index('{'))
    span = next((s_ for s_ in top if s_[0] == parent), None)
    val = dumps(value, 1, indent).replace('\n', '\n')
    if span is None:
        return text
    ob = text.index('{', text.index(':', span[1]))
    mem, oe = _members(text, ob)
    old = next((m for m in mem if m[0] == key), None)
    item = '%s: %s' % (json.dumps(key), val)
    if old is not None:
        return text[:old[1]] + item + text[old[2]:]
    if not mem:
        return text[:ob + 1] + '\n' + ' ' * indent + item + '\n' + ' ' * (indent - 1) + text[oe - 1:]
    last = mem[-1][2]
    return text[:last] + ',\n' + ' ' * indent + item + text[last:]


def apply_notes(G, notes):
    """what the notes decide over the drawing, applied to a graph in place: a piece noted `over` others lies on them in
    the layer order (the drawing's stack can't tell same-coloured layers apart: the overskirt panels lie over the skirt,
    Michael's call, 2026-09-29), each change flagged; a piece's noted `chain` (joints, L in the graph's frame: the path
    the built garment hangs along, written by charkit.flapchains) replaces its spring chain; and each spring chain's
    bone names, the names the rig stage gives the chain's bones (PIECE_0 .. from the root; PIECE_c_i for a piece with
    several chains)."""
    ids = {g['id']: g for g in G.get('pieces', [])}
    sp_of = {sp['piece']: sp for sp in G.get('springs') or []}
    for a in (notes or {}).get('pieces', []):
        if a.get('chain') and a['id'] in sp_of:          # a chain the build's garment defines (charkit.flapchains)
            sp = sp_of[a['id']]
            J = [list(map(float, j)) for j in a['chain']]
            sp['chains'] = [dict(joints=J, root='at %s' % a.get('parent', 'its parent'), source='notes (the built flap)')]
            sp['length'] = round(float(sum(np.linalg.norm(np.subtract(b, c)) for b, c in zip(J[1:], J[:-1]))), 3)
        g = ids.get(a['id'])
        for q in a.get('over') or []:
            h = ids.get(q)
            if g is None or h is None:
                continue
            lg, lh = g.setdefault('layer', {}), h.setdefault('layer', {})
            was = 'under' if q in (lg.get('under') or []) else None
            lg['over'] = sorted(set(lg.get('over') or []) | {q})
            lg['under'] = [x for x in lg.get('under') or [] if x != q]
            lh['under'] = sorted(set(lh.get('under') or []) | {g['id']})
            lh['over'] = [x for x in lh.get('over') or [] if x != g['id']]
            if was:
                g.setdefault('flags', []).append(dict(piece=g['id'], field='layer', notes='over %s' % q,
                                                      measured='under %s' % q, note='the notes put it over'))
    for sp in G.get('springs') or []:
        chains = sp.get('chains') or []
        for c, ch in enumerate(chains):
            pre = sp['piece'] if len(chains) == 1 else '%s_%d' % (sp['piece'], c)
            ch['bones'] = ['%s_%d' % (pre, i) for i in range(max(0, len(ch.get('joints') or []) - 1))]
    return G


def relayer(spec_path, log=print):
    """apply_notes to the character's graphs as they are (the tracked reference refs/NAME/outfit_graph.json and the
    copy beside the produced masks) without rerunning the intake, and the reference's hash refreshed in its manifest."""
    from . import manifest
    spec = json.load(open(_p(spec_path)))
    mref = (spec.get('ref') or {}).get('manifest')
    N = load_notes(os.path.join(os.path.dirname(mref), 'outfit_notes.json'))
    M = json.load(open(_p(mref)))
    paths = [M['references']['outfit_graph']['path'],
             os.path.join(os.path.dirname(M['references']['outfit_masks']['path']), 'outfit_graph.json')]
    for gp in paths:
        if not os.path.exists(_p(gp)):
            continue
        G = json.load(open(_p(gp)))
        apply_notes(G, N)
        open(_p(gp), 'w').write(dumps(G) + '\n')
        log('relayered', gp)
    rehash(mref)
    return paths


def rehash(mref):
    """the manifest's outfit_graph reference's hash refreshed after the graph changed in place."""
    from . import manifest
    M = json.load(open(_p(mref)))
    ref = dict(M['references']['outfit_graph'], sha256=manifest.sha256(M['references']['outfit_graph']['path']))
    text = set_member(open(_p(mref)).read(), 'references', 'outfit_graph', ref)
    json.loads(text)
    open(_p(mref), 'w').write(text)


def register(manifest_path, graph_path, G, inputs):
    """the graph as the character's reference `outfit_graph` in its manifest (kind, role, provenance, hash), and the
    authority for its pieces; the rest of the manifest's text left as it was."""
    from . import manifest
    mp = _p(manifest_path)
    rel = os.path.relpath(_p(graph_path), ROOT)
    ref = dict(kind='outfit_graph', path=rel, tracked=True, sha256=manifest.sha256(rel),
               role=('the outfit as pieces: types, sides and mirror pairs, attachments (bone, parent), layer order, colours, '
                     'extents per sheet view and in 3D, motion classes with reasons, template mapping and spring chains'),
               provenance=dict(tool='charkit.outfit', version=VERSION, command=G['generated_by']['command'], inputs=inputs),
               cautions=['measured from the rig, the sheet and the generated field, cross-checked with the annotated '
                         'vision pass (outfit_notes.json): read its flags before trusting a piece'])
    text = open(mp).read()
    text = set_member(text, 'references', 'outfit_graph', ref)
    if 'outfit_pieces' not in json.loads(text).get('authority', {}):
        text = set_member(text, 'authority', 'outfit_pieces', 'outfit_graph')
    json.loads(text)                                                # still JSON
    open(mp, 'w').write(text)
    return rel


def build(spec_path, out=None, field=None, use_field=True, notes=None, write_manifest=True, log=print):
    """the whole intake for a spec: analysis, structure, graph, templates, comparison, springs; writes the graph, the
    picture, the report and the masks into `out` (default charkit/out/NAME/outfit), and with write_manifest the graph
    as the character's reference refs/NAME/outfit_graph.json, registered in its manifest. -> (graph, paths)."""
    from . import manifest
    raw = json.load(open(_p(spec_path)))
    spec = manifest.resolve(json.loads(json.dumps(raw)))
    spec['_path'] = os.path.relpath(_p(spec_path), ROOT)
    name = spec['name']
    out = _p(out or os.path.join('charkit', 'out', name, 'outfit'))
    os.makedirs(out, exist_ok=True)
    A = analyse(spec, field, use_field, log)
    st = structure(A)
    mref = (spec.get('ref') or {}).get('manifest')
    npath = notes or (os.path.join(os.path.dirname(mref), 'outfit_notes.json') if mref else None)
    N = load_notes(npath) if npath else None
    G = graph(A, st, N, npath)
    G['templates'] = draft(G, A, st)
    G['comparison'] = compare_spec(G['templates'], raw, G)
    G['springs'] = springs(G, A, st)
    apply_notes(G, N)
    for g in G['pieces']:
        g.pop('_k', None)
    paths = {}
    text = dumps(G) + '\n'
    gp = os.path.join(out, 'outfit_graph.json')
    open(gp, 'w').write(text)
    paths['graph'] = gp
    if write_manifest and mref:                                     # the reference copy, registered in the manifest
        gp = os.path.join(os.path.dirname(_p(mref)), 'outfit_graph.json')
        open(gp, 'w').write(text)
        paths['reference'] = gp
    for g, k in zip(G['pieces'], range(A['n'])):
        g['_k'] = k
    paths['picture'] = picture(A, G, os.path.join(out, 'outfit.png'))
    paths['report'] = report(G, os.path.join(out, 'outfit.md'))
    masks = {'%s__%s' % (vn, g['id']): A['assigned'][vn] == g['_k'] for vn in A.get('assigned', {}) for g in G['pieces']}
    np.savez_compressed(os.path.join(out, 'outfit_masks.npz'), **masks)
    paths['masks'] = os.path.join(out, 'outfit_masks.npz')
    for g in G['pieces']:
        g.pop('_k', None)
    if write_manifest and mref:
        inputs = {}
        for key in ('sheet', 'rig', 'trellis'):
            r = (A['manifest'] or {}).get('references', {}).get(key)
            if r and os.path.isfile(_p(r['path'])):
                inputs[key] = dict(path=r['path'], sha256=manifest.sha256(r['path']))
            elif r:
                inputs[key] = dict(path=r['path'])
        if A.get('field') is not None:
            inputs['field'] = dict(path=os.path.relpath(A['field']['path'], ROOT))
        if N:
            inputs['notes'] = dict(path=npath, version=N.get('version'))
        paths['manifest'] = register(mref, gp, G, inputs)
    return G, paths


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return
    if args[0] == 'relayer':
        relayer(args[1] if len(args) > 1 else 'charkit/spec/clawd.json'); return
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    G, paths = build(args[0], opt('--out'), opt('--field'), '--no-field' not in args, opt('--notes'),
                     '--no-manifest' not in args)
    C = G['comparison']
    print('%d pieces: %s' % (len(G['pieces']), ', '.join('%s (%s)' % (g['id'], g['motion']['class']) for g in G['pieces'])))
    print('hand list: %d matched, %d only as a knob, %d missed by it, %d extra in it; %d template gaps; %d flags' % (
        len(C['matched']), len(C['knob_only']), len(C['missed_by_hand']), len(C['extra_in_hand']),
        len(G['templates']['gaps']), len(G['flags'])))
    for k, p in paths.items():
        print(k, p)
