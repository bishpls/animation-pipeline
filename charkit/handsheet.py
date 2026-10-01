"""The hand sheet's structure (tool/hands2 round 6, Michael 2026-10-01: the hand's structure comes from the hand
breakdown sheet, not the turnaround, whose hands are small with merged fingers: the canonical rule's step 2, internal
structure the turnaround can't resolve). The sheet (charkit/refs/clawd/gen/hand_breakdown.png: relaxed, open, fist and
point, from the back of the hand and from the thumb's side, each out of the wrist cuff) cut into hands (charkit.handref),
and each hand's digits read off its silhouette, the same way for the sheet's drawn hands and for ours drawn alike:

  digits(m, c, u, ppl)    the tips (the silhouette's local maxima of distance from the wrist: the cuff's far edge's
                          centre, each standing TIP_PROM of the reach above the clefts beside it), the clefts between
                          neighbouring tips, and per digit its length (tip to the middle of its base: the two clefts
                          beside it, or one and its mirror across the digit's axis for the outer digits), its width
                          profile across its axis at PROFILE of its length, its tip's roundness, and the palm's width
                          across the knuckle line (the clefts' line)
All lengths are shares of the hand's reach past the cuff (the turnaround stays the authority for overall size: the
sheet's hands reach 16-19% further past the cuff than the turnaround's, handref's refcheck; proportions come from the
sheet).

    S = handsheet.cells()                      # {(pose, row): dict(mask, c, u, end, ppl)} at the sheet's px
    D = handsheet.digits(S['open', 'back'])    # dict(tips, clefts, digits [...], palm_w, knuckles)
"""
import os

import numpy as np

from . import handqa, handref

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEET = os.path.join(ROOT, 'charkit', 'refs', 'clawd', 'gen', 'hand_breakdown.png')
TIP_PROM = 0.06          # a tip stands this share of the reach above the clefts either side of it
PROFILE = (0.1, 0.3, 0.5, 0.7, 0.9)      # a digit's width profile: at these shares of its length from its base
SMOOTH = 0.01            # the contour's distance smoothed over this share of the reach (the ink's ragged edge)


def cells(path=SHEET):
    """the sheet's hands at the sheet's own px -> {(pose, row): dict(mask, c, u, end, ppl (px per cuff width), line,
    box)}; the arm straight down the sheet (u (0, 1)): every figure draws its cuff and forearm upright."""
    from PIL import Image
    from scipy import ndimage
    rgb = np.asarray(Image.open(path).convert('RGB'))
    out = {}
    for f in handref.figures(rgb):
        wpx = handref.cuff_width_px(f)
        if not wpx:
            continue
        sk = ndimage.binary_fill_holes(ndimage.binary_closing(f['skin'], iterations=3) & ~f['cuff'])
        cuff = f['cuff']
        rs, cs = np.nonzero(cuff)
        c = np.array([cs.mean(), rs.mean()])
        u = np.array([0.0, 1.0])
        s = ((np.arange(cuff.shape[0])[:, None] - c[1]) * u[1] + (np.arange(cuff.shape[1])[None, :] - c[0]) * u[0])
        end = float(np.percentile(s[cuff], 98)) / wpx
        cand = sk & (s > 0)
        lab, n = ndimage.label(cand)
        keep = np.unique(lab[ndimage.binary_dilation(cuff, iterations=3) & cand])
        m = np.isin(lab, keep[keep > 0])
        if m.sum() < handqa.MIN_PX:
            continue
        pose = handref.POSES[f['col']] if f['col'] < len(handref.POSES) else str(f['col'])
        out[(pose, handref.ROWS[f['row']])] = dict(mask=m, c=c, u=u, end=end, ppl=wpx, line=f['line'], box=f['box'])
    return out


def contour(m):
    """a mask's outer contour as an ordered (N, 2) array of (x, y) pixel points (the longest one)."""
    from skimage import measure
    cs = measure.find_contours(np.pad(m, 1).astype(float), 0.5)
    C = max(cs, key=len)
    return C[:, ::-1] - 1.0


def digits(h, prom=TIP_PROM):
    """a hand's digits off its silhouette (see the module doc). h: dict(mask, c, u, end, ppl) (handqa.hand_mask's, ppl
    px per the length unit) -> dict(reach, wrist (x, y), tips [(x, y)], clefts [(x, y)], digits [dict(tip, base, length,
    axis (unit), widths (at PROFILE), round (the width at 0.9 over 0.5))], palm_w, knuckles (the clefts' mean share of
    the reach along the arm)); lengths as shares of the reach."""
    m, c, u, ppl = h['mask'], np.asarray(h['c'], float), np.asarray(h['u'], float), h['ppl']
    r = handqa.reach(h, ppl) * ppl                                          # px
    wrist = c + u * h['end'] * ppl                                          # the cuff's far edge, on the arm's line
    C = contour(m)
    d = np.linalg.norm(C - wrist, axis=1)
    from scipy.ndimage import uniform_filter1d
    k = max(1, int(SMOOTH * r))
    ds = uniform_filter1d(d, 2 * k + 1, mode='wrap')
    # the contour's points past the wrist line only (the cuff's edge is no tip)
    along = (C - wrist) @ u
    ds = np.where(along > 0.05 * r, ds, ds.min())
    tips = _peaks(ds, prom * r)
    clefts, pair = [], {}
    for a, b in zip(tips, tips[1:] + tips[:1]):
        seg = np.arange(a, b if b > a else b + len(C)) % len(C)
        if len(seg) < 3:
            continue
        j = seg[np.argmin(ds[seg])]
        if ds[a] - ds[j] >= prom * r and ds[b] - ds[j] >= prom * r and along[j] > 0.05 * r:
            clefts.append(j)
            pair.setdefault(a, []).append((j, +1))       # (the cleft, which way along the contour from the tip)
            pair.setdefault(b, []).append((j, -1))
    T = [C[i] for i in tips]
    K = [C[j] for j in clefts]
    out_d = []
    for ti in tips:
        got = pair.get(ti) or []
        tip = C[ti]
        if not got:
            continue
        # the digit's base at the level of its shallower cleft (the one nearer its tip: a deep web beside it, the
        # thumb's beside the index, doesn't lengthen it), the other side's edge as far from the tip
        j, sense = min(got, key=lambda g: np.linalg.norm(C[g[0]] - tip))
        P = C[j]
        want = np.linalg.norm(P - tip)
        k, n = ti, 0
        while n < len(C) and np.linalg.norm(C[k] - tip) < want:
            k = (k - sense) % len(C)
            n += 1
        Q = C[k]
        base = 0.5 * (P + Q)
        L = np.linalg.norm(tip - base)
        if L < 1:
            continue
        ax = (tip - base) / L
        w = [_width(m, base + ax * f * L, ax) / r for f in PROFILE]
        out_d.append(dict(tip=tip, base=base, length=L / r, axis=ax, widths=w, round=w[-1] / max(w[2], 1e-9),
                          outer=len(got) == 1, cleft=P, angle=float(np.degrees(np.arctan2(ax[0], ax[1])))))
    palm_w = None
    if len(K) >= 2:
        acr = np.array([-u[1], u[0]])
        palm_w = float(np.ptp([(k_ - wrist) @ acr for k_ in K])) / r
    return dict(reach=r / ppl, wrist=wrist, tips=T, clefts=K, digits=out_d, palm_w=palm_w,
                knuckles=float(np.mean([(k_ - wrist) @ u for k_ in K])) / r if K else None)


def _peaks(x, prom):
    """indices of a closed curve's local maxima standing prom above the lowest point between each and its neighbouring
    higher peaks (topographic prominence on a ring), sorted along the curve."""
    from scipy.signal import find_peaks
    n = len(x)
    xx = np.r_[x, x, x]
    p, _ = find_peaks(xx, prominence=prom)
    p = sorted({int(i % n) for i in p if n <= i < 2 * n})
    return p


def _width(m, p, ax, step=0.5):
    """the mask's width through p across the direction ax (px): the run of the mask's pixels along the normal through
    p that contains p (or the nearest run)."""
    nrm = np.array([-ax[1], ax[0]])
    H, W = m.shape
    ts = np.arange(-W, W, step)
    pts = p[None] + ts[:, None] * nrm[None]
    xi, yi = np.round(pts[:, 0]).astype(int), np.round(pts[:, 1]).astype(int)
    ok = (xi >= 0) & (xi < W) & (yi >= 0) & (yi < H)
    inside = np.zeros(len(ts), bool)
    inside[ok] = m[yi[ok], xi[ok]]
    if not inside.any():
        return 0.0
    i0 = int(np.argmin(np.abs(ts)))
    if not inside[i0]:
        idx = np.nonzero(inside)[0]
        i0 = idx[np.argmin(np.abs(idx - i0))]
    a = i0
    while a > 0 and inside[a - 1]:
        a -= 1
    b = i0
    while b < len(ts) - 1 and inside[b + 1]:
        b += 1
    return (b - a + 1) * step


# ------------------------------------------------------------------------------------------------ ours, drawn alike
ROW_AXES = {'back': (1, 1.0), 'side': (2, -1.0)}   # row -> (the frame's column drawn as image x, its sign): the back of
                                                   # the hand, the thumb (radial) to the right as the sheet draws its
                                                   # left hand; the thumb's side, the palm to the right


def draw(H_, row, ppl, cuff_end=0.0, pad=12):
    """a template hand (code_hand.hand's dict) drawn as the sheet draws it: orthographic in the hand's own frame, the
    arm straight down the image (the frame's along axis), the row's axis across; the part past cuff_end L from the
    wrist -> dict(mask, c, u, end, ppl) as cells() gives (c: the wrist's pixel)."""
    from PIL import Image, ImageDraw
    from . import code_hand
    W, R = H_['frame']
    k, sgn = ROW_AXES[row]
    V, T, _ = code_hand.mesh(H_)
    Q = V - W
    x, y = sgn * (Q @ R[:, k]), Q @ R[:, 0]
    keep = y[T].mean(1) > cuff_end
    T = T[keep]
    x0, x1, y1 = x[T].min() - pad / ppl, x[T].max() + pad / ppl, y[T].max() + pad / ppl
    y0 = min(0.0, cuff_end) - pad / ppl
    Wd, Hd = int(np.ceil((x1 - x0) * ppl)), int(np.ceil((y1 - y0) * ppl))
    im = Image.new('L', (Wd, Hd), 0)
    dr = ImageDraw.Draw(im)
    px, py = (x - x0) * ppl, (y - y0) * ppl
    for t in T:
        dr.polygon([(px[t[0]], py[t[0]]), (px[t[1]], py[t[1]]), (px[t[2]], py[t[2]])], fill=1)
    m = np.asarray(im, bool)
    return dict(mask=m, c=np.array([-x0 * ppl, -y0 * ppl]), u=np.array([0.0, 1.0]), end=cuff_end, ppl=ppl)


# ------------------------------------------------------------------------------------------------------- the sheet fit
CUFF_END = 0.034         # L: our wrist cuff's far edge past the wrist joint (the spec's cuff template on the posed
                         # chain: code_hand.cuff_end, hands2's builds 0.034 / 0.046 L, left / right)
DIGIT_LIMITS = dict(length=0.03, width=0.01, angle=8.0, palm_w=0.03, knuckles=0.03)   # each term's unit (its PASS)
CHAIN = np.array([[0.5, 0, -1.0], [0.6, 0, -1.8], [0.62, 0, -2.5], [0.63, 0, -2.8]])   # a left arm (the frame only)


def sheet_iou(hs, ho):
    """two hands' silhouettes at one px scale (ours drawn at the sheet's reach in px), laid on their centroids -> IoU."""
    return handqa.shape_iou(hs['mask'], ho['mask'])


def compare(Ds, Do, row):
    """the sheet's digits against ours in one row -> {term: (ours, sheet, units)}: the tip count (a unit per tip more
    or fewer), and with the counts equal per digit (in order across the image) its length, width profile (RMS) and
    angle; the palm's width and the knuckle line (the back row)."""
    T = {}
    ns, no = len(Ds['digits']), len(Do['digits'])
    T['tips'] = (no, ns, 2.0 * abs(no - ns))
    if ns == no:
        a = sorted(Ds['digits'], key=lambda d: d['tip'][0])
        b = sorted(Do['digits'], key=lambda d: d['tip'][0])
        names = DIGIT_NAMES.get((row, ns), ['d%d' % i for i in range(ns)])
        for n, ds, do in zip(names, a, b):
            T[n + '_length'] = (do['length'], ds['length'], abs(do['length'] - ds['length']) / DIGIT_LIMITS['length'])
            rms = float(np.sqrt(np.mean((np.array(do['widths']) - np.array(ds['widths'])) ** 2)))
            T[n + '_width'] = (rms, 0.0, rms / DIGIT_LIMITS['width'])
            T[n + '_angle'] = (do['angle'], ds['angle'], abs(do['angle'] - ds['angle']) / DIGIT_LIMITS['angle'])
    if row == 'back':
        for k in ('palm_w', 'knuckles'):
            if Ds[k] is not None and Do[k] is not None:
                T[k] = (Do[k], Ds[k], abs(Do[k] - Ds[k]) / DIGIT_LIMITS[k])
    return T


DIGIT_NAMES = {('back', 5): ['little', 'ring', 'middle', 'index', 'thumb'],
               ('side', 3): ['finger_a', 'finger_b', 'thumb']}


class SheetFit:
    """the template's structure against one of the sheet's poses (the open hand: five separate digits), per row:
    1 - the silhouettes' IoU at equal reach, plus each compare() term's units times WEIGHT (capped at CAP). The
    template's knobs carry the pose (fan_*, thumb_out/down, curl): the structure is shared with every pose."""
    WEIGHT, CAP = 0.05, 4.0

    def __init__(self, spec_path, pose='open', rows=('back', 'side'), over=None):
        import json
        from . import code_hand
        spec = json.load(open(spec_path))
        self.base = code_hand.params(spec, **(over or {}))
        S = cells()
        self.pose, self.rows = pose, tuple(rows)
        self.sheet = {r: S[(pose, r)] for r in self.rows}
        self.D = {r: digits(self.sheet[r]) for r in self.rows}
        self.floors = None
        self.src = ('charkit.handsheet:SheetFit', (spec_path, pose, rows, over))

    def ours(self, P, row):
        """our hand in the row, drawn at the sheet's reach in px -> (h, digits)."""
        from . import code_hand
        H_ = code_hand.hand(CHAIN, 'left', P)
        W, R = H_['frame']
        V, T, _ = code_hand.mesh(H_)
        reach = float(np.percentile((V - W) @ R[:, 0], 99.9)) - CUFF_END
        ppl = self.D[row]['reach'] * self.sheet[row]['ppl'] / max(reach, 1e-6)
        h = draw(H_, row, ppl, CUFF_END)
        return h, digits(h)

    def score(self, P, detail=False):
        costs, per, full = [], {}, {}
        for r in self.rows:
            h, Do = self.ours(P, r)
            iou = sheet_iou(self.sheet[r], h)
            T = compare(self.D[r], Do, r)
            costs.append((1 - iou) + self.WEIGHT * sum(min(t[2], self.CAP) for t in T.values()))
            per[r] = (round(iou, 4), len(Do['digits']))
            full[r] = dict(iou=round(iou, 4), terms={k: tuple(None if x is None else round(float(x), 3) for x in t)
                                                     for k, t in T.items()})
        c = float(np.mean(costs))
        return (c, full) if detail else (c, per)


def picture(F, P, out):
    """the sheet's hand (grey) with ours (red outline) per row, laid on the centroids, the terms under each."""
    from PIL import Image, ImageDraw
    from scipy import ndimage
    _, full = F.score(P, detail=True)
    tiles = []
    for r in F.rows:
        h, _ = F.ours(P, r)
        A, Bm = handqa.aligned_pair(F.sheet[r]['mask'], h['mask'])
        img = np.full(A.shape + (3,), 255, np.uint8)
        img[A] = (190, 190, 190)
        img[ndimage.binary_dilation(Bm & ~ndimage.binary_erosion(Bm))] = (220, 30, 30)
        lines = ['%s %s IoU %.3f' % (F.pose, r, full[r]['iou'])]
        lines += ['%s %s / %s (%.1f)' % (k, t[0], t[1], t[2]) for k, t in full[r]['terms'].items()]
        canvas = np.full((img.shape[0] + 12 * len(lines) + 4, max(img.shape[1], 220), 3), 255, np.uint8)
        canvas[:img.shape[0], :img.shape[1]] = img
        im = Image.fromarray(canvas)
        for i, t in enumerate(lines):
            ImageDraw.Draw(im).text((2, img.shape[0] + 2 + 12 * i), t, fill=(0, 0, 0))
        tiles.append(np.asarray(im))
    H = max(t.shape[0] for t in tiles)
    row = np.concatenate([np.pad(t, ((0, H - t.shape[0]), (0, 10), (0, 0)), constant_values=255) for t in tiles], 1)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    Image.fromarray(row).save(out)
    return out


OPEN_KNOBS = ('palm', 'palm_w', 'wrist_w', 'palm_t', 'taper', 'overlap', 'fingers.0', 'fingers.2', 'fingers.3',
              'thumb_base', 'thumb_across', 'thumb_len', 'thumb_w', 'thumb_out', 'thumb_down', 'curl', 'dev',
              'fan_index', 'fan_middle', 'fan_ring', 'fan_little')


def main(args):
    """python -m charkit handsheet fit [--pose open] [--spec S] [--over JSON] [--knobs a,b] [--method de --workers N
                                        --maxiter N] [--rounds N] [--png P] [--json J]
       python -m charkit handsheet show [--pose open] [--spec S] [--over JSON] --out PNG"""
    import json
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    from . import code_hand
    spec_path = opt('--spec') or os.path.join(ROOT, 'charkit', 'spec', 'clawd.json')
    over = json.loads(opt('--over')) if opt('--over') else None
    F = SheetFit(spec_path, opt('--pose', 'open'), over=over)
    if not args or args[0] == 'show':
        c, full = F.score(F.base, detail=True)
        print(json.dumps(dict(cost=round(c, 4), per=full), indent=1, default=str))
        print(picture(F, F.base, opt('--out', 'sheet_fit.png')))
        return 0
    knobs = tuple(opt('--knobs').split(',')) if opt('--knobs') else OPEN_KNOBS
    P, c, per = code_hand.search(F, knobs, rounds=int(opt('--rounds', 2)), log=lambda *a, **k: print(*a, flush=True),
                                 method=opt('--method', 'powell'), workers=int(opt('--workers', 1)),
                                 maxiter=int(opt('--maxiter', 40)), popsize=int(opt('--popsize', 12)),
                                 maxfev=int(opt('--maxfev', 400)))
    c, full = F.score(P, detail=True)
    res = dict(cost=round(c, 4), per=full, knobs={k: (round(v, 4) if isinstance(v, float) else v) for k, v in P.items()})
    print(json.dumps(res, indent=1, default=str))
    if opt('--json'):
        os.makedirs(os.path.dirname(os.path.abspath(opt('--json'))), exist_ok=True)
        json.dump(res, open(opt('--json'), 'w'), indent=1, default=str)
    if opt('--png'):
        print(picture(F, P, opt('--png')))
    return 0
