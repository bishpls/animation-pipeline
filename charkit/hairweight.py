"""The hair's line weight and taper (tool/hairstrokes, scope (a); Michael, 2026-10-01: the hair's strokes should taper at
their ends and be lighter than the silhouette's outline, as the turnaround draws them). Measured at the head sheet's own
scale (HEAD_PPL, 400 px per L: the body sheet's 212 can't resolve a 1-2 px stroke), by one detector on both pictures:
the design's head sheet (head_turnaround) and our head drawn by the QA's renderer (charkit.qa3d.draw) at that scale.

The detector (weights): a line's darkness is its value under the local fill (a grey closing over CLOSE px: steps
between tones stay, lines and slivers under CLOSE px go), as a coverage of the picture's own outline ink (the darkest
twentieth of the silhouette's band); its skeleton's points each carry the coverage integrated across the line (along
the skeleton's normal, out from the centre until it falls under FLOOR or rises toward another line): its **weight**,
in px of the outline's ink. A line's weight is its width and its darkness at once (a thin black line and a wider brown
one weigh the same): the drawing's strands are brown and thin, its outline black and heavier.

  outline   the skeleton within OUT px of the hair's silhouette, either side
  strands   the strokes inside the hair (at least IN px in, off the clips): the design's, its lines fainter than
            STRAND_PEAK of the outline's ink at their centre (the brown strand strokes: its lock lines and the clips
            are drawn in the outline's black); ours, our ink strokes (a piece's ink slot, qa3d.is_ink)
  weight    the strands' median weight over the outline's (each picture against its own outline)
  taper     how gradually a strand ends: per free end of a strand path (a skeleton path at least MIN_PATH L long, the
            end not a junction's cut), the path followed on past its detected end along its direction (a faint stroke
            fades under the skeleton's threshold before it ends), the length (px) over which its weight falls from
            0.75 to 0.25 of its middle's: the median over the ends. A blunt end falls within the line's blur (1.5-2 px
            here); the turnaround's strands over 5-6 px, our ribbons (tip 0.15 over 60%) over about 4

The checks (charkit.hairstrokeqa's declarations, declared family `line_weight`): ours against the design's per view,
hair_strokes_{view}_weight |log2(ours / design)| (the strands' weight over the outline's: the design 0.25-0.28) and
hair_strokes_{view}_taper ours over the design's taper length (higher is better). Front, three-quarter and profile: the
back's mass is drawn plain (the strand checks' views).

Calibration floors (charkit.declared.Declared: the design's head pictures as ours): heavy_strokes, the design's strands
repainted in the outline's ink at the outline's weight; blunt_strokes, repainted at their own colour and middle weight
with square ends (redraw())."""
import numpy as np

HEAD_PPL = 400.0       # px per L: the head sheet's own (~399)
HEAD_WIN = (1.25, 1.6, 1.45)    # L round the eye line (half-width, above, below): the head, its buns, the hair's ends
SS = 4                 # our drawing's supersampling (the renderer's own filter on the way down)
CLOSE = 9              # px: the local fill's grey closing (a line or sliver narrower than this reads as a line)
FLOOR = 0.06           # coverage: a line's profile ends where it falls under this
OUT, IN = 3, 7         # px: the outline's band either side of the silhouette; the strands at least this far inside
STRAND_PEAK = 0.7      # a strand's centre is lighter than this share of the outline's ink (the design's brown strokes)
THR = 0.12             # coverage: the lines' skeleton
CLIP_PAD = 0.03        # L: round the clips
STAR_PAD = 0.15        # L: the design's clips, round its yellow star (the crab beside it, drawn in the hair's orange)
MIN_PATH = 0.03        # L: a strand path's least length for its taper
VIEWS = ('front', 'three_quarter', 'profile', 'back')


# ------------------------------------------------------------------------------------------------------------ detector
def coverage(rgb, sil):
    """the darkness of each pixel under its local fill, over the outline ink's -> (coverage 0..1, the ink's value)."""
    from scipy import ndimage
    v = np.asarray(rgb, float)[..., :3].max(-1)
    F = ndimage.grey_closing(v, size=(CLOSE, CLOSE))
    d_in = ndimage.distance_transform_edt(sil)
    d_out = ndimage.distance_transform_edt(~sil)
    band = (d_in <= OUT) & (d_out <= OUT) & (F - v > 0.1)
    k = float(np.percentile(v[band], 5)) if band.sum() > 20 else float(np.percentile(v, 1))
    return np.clip((F - v) / np.maximum(F - k, 0.05), 0, 1), k


def weights(c, sk, R=5.0, step=0.25):
    """each skeleton pixel's weight: c integrated across the line, from the centre out until it falls under FLOOR or
    rises 0.15 over the lowest point reached (another line) -> (rows, cols, weights px, peak coverage)."""
    from scipy import ndimage
    from .declared import orientation
    th = orientation(sk)
    rr, cc = np.nonzero(sk)
    if not len(rr):
        return rr, cc, np.zeros(0), np.zeros(0)
    t = np.arange(-R, R + 1e-9, step)
    a = th[rr, cc] + np.pi / 2
    X = cc[:, None] + np.cos(a)[:, None] * t[None]
    Y = rr[:, None] + np.sin(a)[:, None] * t[None]
    P = ndimage.map_coordinates(c, [Y.ravel(), X.ravel()], order=1, mode='constant').reshape(X.shape)
    mid = len(t) // 2
    keep = np.zeros(P.shape, bool)
    keep[:, mid] = True
    for side in (range(mid + 1, len(t)), range(mid - 1, -1, -1)):
        lo = P[:, mid].copy()
        on = np.ones(len(rr), bool)
        for j in side:
            on &= (P[:, j] >= FLOOR) & (P[:, j] <= lo + 0.15)
            keep[:, j] = on
            lo = np.where(on, np.minimum(lo, P[:, j]), lo)
    w = (P * keep).sum(1) * step
    pk = ndimage.maximum_filter(c, size=3)[rr, cc]
    return rr, cc, w, pk


def paths(sk, min_px):
    """the skeleton cut at its junctions into simple paths, each in order from one end to the other -> [(rows,
    cols)], the paths of at least min_px pixels."""
    from scipy import ndimage
    nb = ndimage.convolve(sk.astype(int), np.ones((3, 3), int), mode='constant') - 1
    s = sk & (nb <= 2)
    lab, n = ndimage.label(s, np.ones((3, 3)))
    out = []
    for k, sl in enumerate(ndimage.find_objects(lab)):
        if sl is None:
            continue
        m = lab[sl] == k + 1
        if m.sum() < min_px:
            continue
        rr, cc = np.nonzero(m)
        P = set(zip(rr.tolist(), cc.tolist()))
        deg = {p: sum((p[0] + i, p[1] + j) in P for i in (-1, 0, 1) for j in (-1, 0, 1) if i or j) for p in P}
        ends = [p for p, d in deg.items() if d == 1]
        if len(ends) != 2:
            continue                                     # (a loop or a knot: no ends to follow)
        seq, seen, p = [ends[0]], {ends[0]}, ends[0]
        while True:
            nxt = [(p[0] + i, p[1] + j) for i in (-1, 0, 1) for j in (-1, 0, 1)
                   if (i or j) and (p[0] + i, p[1] + j) in P and (p[0] + i, p[1] + j) not in seen]
            if not nxt:
                break
            nxt.sort(key=lambda q: abs(q[0] - p[0]) + abs(q[1] - p[1]))     # (4-neighbours first)
            p = nxt[0]
            seq.append(p); seen.add(p)
        if len(seq) < 0.9 * len(P):
            continue
        a = np.array(seq)
        out.append((a[:, 0] + sl[0].start, a[:, 1] + sl[1].start))
    return out


def weight_at(c, P, ang, R=4.0, step=0.25):
    """the weight at points P (rows, cols) across lines at angles ang (weights()' integral, not stopped)."""
    from scipy import ndimage
    t = np.arange(-R, R + 1e-9, step)
    n = ang + np.pi / 2
    X = P[:, 1][:, None] + np.cos(n)[:, None] * t
    Y = P[:, 0][:, None] + np.sin(n)[:, None] * t
    return ndimage.map_coordinates(c, [Y.ravel(), X.ravel()], order=1).reshape(X.shape).sum(1) * step


def end_length(c, pr, pc, mid, free, inside=6, past=14.0):
    """a path's free ends: each followed from `inside` px in to `past` px beyond along its direction, the length (px)
    over which the weight falls from 0.75 to 0.25 of mid -> [lengths]."""
    n = len(pr)
    out = []
    for j, (e, i) in enumerate(((0, min(inside, n - 1)), (n - 1, max(0, n - 1 - inside)))):
        if not free[j]:
            continue
        p1 = np.array([pr[e], pc[e]], float)
        d = p1 - np.array([pr[i], pc[i]], float)
        L = np.linalg.norm(d)
        if L < 2:
            continue
        d /= L
        s = np.arange(-L, past, 0.5)
        w = weight_at(c, p1[None] + s[:, None] * d[None], np.full(len(s), np.arctan2(d[0], d[1])))
        hi = np.nonzero(w >= 0.75 * mid)[0]
        if not len(hi):
            continue
        low = np.nonzero((w <= 0.25 * mid) & (np.arange(len(w)) > hi[0]))[0]
        if not len(low):
            continue
        lo = low[0]                                          # (the first fall to 0.25 past the line's body)
        top = hi[hi < lo].max()                              # (the last point at 0.75 before it)
        out.append(float(s[lo] - s[top]))
    return out


def strands_of(rgb, hair, strands=None, clips=None, ppl=HEAD_PPL):
    """the lines of a view's picture: dict(c coverage, ink value, sil, outline weights, the strand points (rr, cc, w,
    peak) and their paths) or None without a hair. strands: our ink's pixels (None: the design's faint lines)."""
    from scipy import ndimage
    from skimage.morphology import skeletonize
    if hair is None or hair.sum() < 100:
        return None
    sil = ndimage.binary_fill_holes(ndimage.binary_closing(hair, iterations=2))
    c, k = coverage(rgb, sil)
    d_in = ndimage.distance_transform_edt(sil)
    d_out = ndimage.distance_transform_edt(~sil)
    sk = skeletonize((c > THR) & ((d_in > 0) | (d_out <= OUT)))
    away = np.ones(sk.shape, bool)
    if clips is not None and clips.any():
        away = ndimage.distance_transform_edt(~clips) > CLIP_PAD * ppl
    o_sk = sk & (d_in <= OUT) & (d_out <= OUT) & away
    i_sk = sk & (d_in >= IN) & away
    _, _, w_o, _ = weights(c, o_sk)
    rr, cc, w_i, pk = weights(c, i_sk)
    sel = pk < STRAND_PEAK if strands is None else ndimage.binary_dilation(strands, iterations=1)[rr, cc]
    st = np.zeros(sk.shape, bool)
    st[rr[sel], cc[sel]] = True
    W = np.zeros(sk.shape)
    W[rr, cc] = w_i
    nb = ndimage.convolve(sk.astype(int), np.ones((3, 3), int), mode='constant') - 1
    P = []
    for pr, pc in paths(st, int(MIN_PATH * ppl)):
        w = W[pr, pc]
        n = len(w)
        mid = float(np.median(w[int(0.3 * n):int(0.7 * n) + 1]))
        if mid > 0:
            P.append(dict(rr=pr, cc=pc, w=w, mid=mid, free=(nb[pr[0], pc[0]] == 1, nb[pr[-1], pc[-1]] == 1)))
    return dict(c=c, ink=k, sil=sil, w_out=w_o, rr=rr[sel], cc=cc[sel], w=w_i[sel], peak=pk[sel], paths=P)


def measure(rgb, hair, strands=None, clips=None, ppl=HEAD_PPL):
    """one view's picture: rgb (H, W, 3) floats, hair the hair's pixels (lines and ink included), strands our ink's
    pixels (None: the design's faint lines), clips the clips' pixels (None: none) -> dict(w_out, w_strand, weight,
    taper (px), ends, paths, strand_px, ink, peak) or None without a hair."""
    S = strands_of(rgb, hair, strands, clips, ppl)
    if S is None:
        return None
    n = len(S['w'])
    res = dict(ink=round(S['ink'], 3), outline_px=int(len(S['w_out'])), strand_px=int(n),
               w_out=round(float(np.median(S['w_out'])), 3) if len(S['w_out']) else None,
               w_strand=round(float(np.median(S['w'])), 3) if n >= 20 else None,
               peak=round(float(np.median(S['peak'])), 3) if n >= 20 else None)
    res['weight'] = round(res['w_strand'] / res['w_out'], 3) if res['w_out'] and res['w_strand'] else None
    ends = []
    for p in S['paths']:
        ends += end_length(S['c'], p['rr'], p['cc'], p['mid'], p['free'])
    res['taper'] = round(float(np.median(ends)), 2) if len(ends) >= 5 else None
    res['ends'], res['paths'] = len(ends), len(S['paths'])
    return res


def redraw(img, hair, clips, kind, seed=0, ss=4):
    """the design's head picture with its strands repainted (the calibration's floors): 'heavy_strokes' in the outline's
    ink at the outline's weight, 'blunt_strokes' at each strand's own colour and middle weight with square ends; the
    strands' own pixels first filled with the local fill -> (picture, the repainted strands' pixels)."""
    from PIL import Image, ImageDraw
    from scipy import ndimage
    S = strands_of(img, hair, None, clips)
    img = np.asarray(img, float)[..., :3].copy()
    if S is None:
        return img, np.zeros(img.shape[:2], bool)
    rng = np.random.default_rng(7000 + int(seed))
    zone = np.zeros(img.shape[:2], bool)
    zone[S['rr'], S['cc']] = True
    zone = ndimage.binary_dilation(zone, iterations=3) & (S['c'] > 0.02)
    fill = np.stack([ndimage.grey_closing(img[..., j], size=(CLOSE, CLOSE)) for j in range(3)], -1)
    img[zone] = fill[zone]
    v = img.max(-1)
    ink = img[np.unravel_index(np.argmin(np.where(S['sil'], v, 9)), v.shape)]
    w_out = float(np.median(S['w_out'])) if len(S['w_out']) else 2.5
    H, W = img.shape[:2]
    cov = Image.new('F', (W * ss, H * ss), 0.0)
    dr = ImageDraw.Draw(cov)
    cols = np.zeros((H, W, 3))
    acc = np.zeros((H, W))
    for p in S['paths']:
        jit = rng.uniform(-0.25, 0.25, 2)
        pts = [((c_ + 0.5 + jit[1]) * ss, (r_ + 0.5 + jit[0]) * ss) for r_, c_ in zip(p['rr'], p['cc'])]
        if kind == 'heavy_strokes':
            width, col = w_out, ink
        else:
            k = int(np.argmin(np.abs(p['w'] - p['mid'])))
            r_, c_ = p['rr'][k], p['cc'][k]
            pk = max(0.15, float(S['c'][r_, c_]))
            width, col = float(np.clip(p['mid'] / pk, 1.0, 4.0)), img[r_, c_] * 0 + (
                fill[r_, c_] - pk * (fill[r_, c_] - ink))
        one = Image.new('F', (W * ss, H * ss), 0.0)
        ImageDraw.Draw(one).line(pts, fill=1.0, width=max(1, int(round(width * ss))))
        a = np.asarray(one).reshape(H, ss, W, ss).mean((1, 3))
        cols += a[..., None] * np.asarray(col)[None, None]
        acc += a
    a = np.clip(acc, 0, 1)[..., None]
    col = cols / np.maximum(acc, 1e-9)[..., None]
    return img * (1 - a) + col * a, acc[..., None][..., 0] >= 0.25


# ------------------------------------------------------------------------------------------------------------- pictures
def design_head(B, design):
    """the design's head sheet at HEAD_PPL, per view: dict(rgb, hair, clips, az3), or {} without a face sheet."""
    from . import hairlab
    fs = design.ref().get('face_sheet')
    if not fs:
        return {}
    ex = B.assembly['eye_knobs']['x']
    rgb = design.rgba(fs['image'])[..., :3]
    # (kept on disk too, design.memo: a pure function of the sheet's pixels, 8 s a QA pass)
    return B.memo(('hairweight_design', ex), lambda: design.memo(_design_head, rgb, ex, fs.get('facing', -1)))


def _design_head(rgb, ex, facing):
    from scipy import ndimage
    from . import bodyqa, hairlab, refcheck
    rgb0, _ = refcheck.without_guides(np.asarray(rgb, float))
    rgb1, _, _ = refcheck.at_scale(rgb0, ex, 2 * ex * HEAD_PPL, facing)
    rgb1 = rgb1 / 255.0 if rgb1.max() > 1.5 else rgb1
    hd = hairlab._head_design(rgb, ex, facing, HEAD_PPL)
    out = {}
    for v, h in hd.items():
        x0, y0, x1, y1 = h['box']
        img = np.asarray(rgb1[y0:y1, x0:x1, :3], float)
        # the clips: the star's yellow (bright, saturated, high red and green) with the crab beside it
        mx, mn = img.max(-1), img.min(-1)
        yel = (img[..., 1] > 0.7) & (img[..., 0] > 0.8) & (mx - mn > 0.3) & (img[..., 2] < 0.6)
        lab, n = ndimage.label(yel)
        clips = np.zeros(yel.shape, bool)
        if n:
            big = np.argmax(np.bincount(lab.ravel())[1:]) + 1
            clips = ndimage.binary_dilation(lab == big, iterations=int(STAR_PAD * HEAD_PPL))
        out[v] = dict(rgb=img, hair=h['hair'], clips=clips, az3=h['az3'])
    return out


def our_head(B, az3, views=VIEWS, ss=SS):
    """our head drawn by the QA's renderer at HEAD_PPL (charkit.lookqa's head frame and scene, the lines at the head
    boards' width: lookqa.line_scale on charkit.artifactqa's head page), per view: dict(rgb on the sheet's grey, hair
    (our hair objects, their outlines and ink), strands (our ink strokes' coverage >= 0.25), clips (the accessories)).
    Memoized on the bundle."""
    def make():
        from . import artifactqa, bodyqa, lookqa, qa3d
        # (the lines as the head boards draw them: the look's screen lines on a page of the head frame's height, as
        # charkit.artifactqa's head frame draws them at the same scale; our ink strokes are world-wide ribbons)
        page = int(round((artifactqa.HEAD_WIN[1] + artifactqa.HEAD_WIN[2]) * HEAD_PPL))
        from .geom.hairink import LOCK_MATERIAL
        surfs, ink = [], []
        for s_ in lookqa._scene(B, skin_outline=True, line_scale=lookqa.line_scale(B, HEAD_PPL, page)):
            is_ink = bool(s_['hull']) and len(s_['slots']) > 0 and \
                all(qa3d.is_ink(s_['o'].materials[int(t)]) for t in np.unique(s_['slots']))
            lock = np.array([s_['o'].materials[int(t)] == LOCK_MATERIAL for t in s_['slots']], bool) if is_ink \
                else np.zeros(len(s_['T']), bool)
            if not lock.any():
                surfs.append(s_); ink.append(is_ink)
                continue
            for strand, sel in ((True, ~lock), (False, lock)):   # (the lock lines are lines, not strands)
                if sel.any():
                    c_ = s_['cull']
                    surfs.append(dict(s_, T=s_['T'][sel], slots=s_['slots'][sel], Tl=s_['Tl'][sel],
                                      cull=np.asarray(c_)[sel] if np.ndim(c_) else c_))
                    ink.append(strand)
        ink = np.array(ink + [False])
        fr = lookqa.HeadFrame(B, ppl=HEAD_PPL, ss=ss, win=HEAD_WIN)
        az = bodyqa.azimuths(az3)
        hair = np.array([s_['o'].name.startswith('hair_') for s_ in surfs] + [False])
        acc = np.array([s_['o'].group == 'accessory' for s_ in surfs] + [False])
        out = {}
        for v in views:
            aux = {}
            img = qa3d.draw(B, surfs, az[v], fr, ss=ss, aux=aux)
            mesh = aux['mesh']
            idx = np.where(mesh >= 0, mesh, len(surfs))
            H, W = img.shape[:2]
            cov = lambda m: m[:H * ss, :W * ss].reshape(H, ss, W, ss).mean((1, 3))
            a = img[..., 3:4]
            rgb = img[..., :3] * a + (1 - a) * 0.75
            out[v] = dict(rgb=rgb, hair=cov(hair[idx]) >= 0.5, strands=cov(ink[idx]) >= 0.25,
                          clips=cov(acc[idx]) > 0)
        return out
    return B.memo(('hairweight_ours', float(az3), tuple(views), ss), make)
