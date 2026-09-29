"""Visual hulls from calibrated orthographic reference views (docs/GEOM.md): a character's 3D shape carved from its
turnaround's silhouettes, the way a modeller blocks a figure out from front, side and back drawings.

A view is an orthographic picture of the figure at azimuth `az`, in the QA's convention (charkit.faceqa.view): a point
(x, y, z) shows at u = x cos az + y sin az with z up; 0 is the front (camera on -y), 90 is from +x (the profile, facing
the picture's left), 180 is the back. It has `ppl` px per head length L, its figure mask, its class image, and the
picture's column of its axis and row of its eye line. Coordinates are in L, with z up from the eye line.

A turnaround drawn at one scale with one eye line (charkit refcheck checks this) calibrates exactly from its eyes:
  - the front's eyes put the midline at x = 0;
  - the profile's eye gives the eyes' depth y_e (the profile's own axis is free: it only slides the figure along y);
  - the three-quarter's eyes then fix its axis, since their midpoint shows at u = y_e sin az;
  - the back's axis is its head's.

  carve      the plain hull: every voxel inside the figure in every view given. Three orthogonal views make each
             height's section the rectangle of the front width by the side depth, which a round body isn't.
  rounded    the shape prior (a style's, charkit.styles): each height's section is the union of superellipses inscribed
             in the (front run x side run) rectangles. A front run takes its depth from the side runs of its own class
             where it has them: a forearm's skin from the skin drawn over the clothes, not the torso's depth. The result
             is smoothed across heights and kept inside the plain hull of every view given.
  project    a hull's silhouette at an azimuth, on a (u, z) grid
  validate   leave one out: each view predicted from the others, its IoU against the drawing
  surface    the closed surface (volume.to_mesh), with vertex colours from the view that faces each vertex best

Pieces (the outfit graph's, charkit.outfit; its per-view masks are the manifest's produced `outfit_masks`):
  attach_pieces   the masks onto the views, and each pixel's limb (arm, leg or body: a piece's by its attach bone, free
                  skin's by the graph's skeleton on the front and back). `rounded` splits a front run where a limb meets
                  the body and pairs each limb part with the side view's pixels of that limb.
  label_volume    the hull's surface labelled per piece: each shell voxel takes the label (the piece, else FREE + the
                  class) of the view that faces it most squarely among those that see it. The profile's and the
                  three-quarter's mirrors label the far side, pieces swapped left for right.
  validate_labels each view's labels predicted from the others, against its drawn pieces (agreement strict and within
                  2 px, per-piece IoU)

Clawd's body_turnaround (2026-09-28): the three-quarter predicted from front, side and back only scores IoU 0.715 plain,
0.797 with ellipses, 0.818 with class-aware pairing, 0.862 with the axis refined and the smoothing, 0.876 with the limb
split (the wrist cuffs no longer take the skirt's depth). TRELLIS scores 0.79 there, our build 0.68.

    python -m charkit.geom hull SPEC [--head] [--out DIR] [--h 0.01] [--style anime] [--faces N] [--fast] [--no-open]

--head carves the head turnaround instead (views_from_heads: the heads at about twice the body sheet's scale, down to the
neck), the target the code-authored head is fitted to.
"""
import json, os

import numpy as np

SKIN, HAIR, OTHER = 1, 2, 0         # charkit.bodyqa.CLASS's skin and hair (its classes label the views)


class View:
    """one calibrated orthographic view: mask and class image (H, W), azimuth (deg), px per L, the picture's column of
    the axis (u = 0) and row of the eye line (z = 0), and its pixels for colour."""

    def __init__(self, name, az, mask, ppl, axis, eye_y, labels=None, rgb=None):
        self.name, self.az, self.mask, self.ppl = name, float(az), mask, float(ppl)
        self.axis, self.eye_y, self.labels, self.rgb = float(axis), float(eye_y), labels, rgb
        self.pieces = self.limbs = None       # attach_pieces: piece labels (0 none, k + 1 piece k) and limbs per pixel
        self.grid_eye = None                  # the sheet pixel its bodyqa.design_views grid is centred on

    def pixel(self, u, z):
        """(cols, rows) of picture positions (L) as rounded ints."""
        return (np.round(self.axis + np.asarray(u) * self.ppl).astype(int),
                np.round(self.eye_y - np.asarray(z) * self.ppl).astype(int))

    def sample(self, img, u, z):
        """an image at an outer product of u (N) and z (M) -> (N, M); outside the picture: zero / False."""
        c, r = self.pixel(u, z)
        H, W = img.shape[:2]
        okc, okr = (c >= 0) & (c < W), (r >= 0) & (r < H)
        out = np.zeros((len(c), len(r)) + img.shape[2:], img.dtype)
        out[np.ix_(okc, okr)] = np.swapaxes(img[np.ix_(r[okr], c[okc])], 0, 1)
        return out

    def u_of(self, x, y):
        a = np.radians(self.az)
        return x * np.cos(a) + y * np.sin(a)


def views_from_sheet(rgb, eye_x, facing=-1):
    """a full-body turnaround's views, found as a model sheet's are (charkit.sheetqa.detect_figures) and calibrated from
    their eyes (see the module) -> ({view: View}, info {ppl, az3, y_e, axes})."""
    from charkit import bodyqa, sheetqa
    D = sheetqa.detect_figures(rgb, None, eye_x, facing)
    ppl, F = D['ppl'], D['figures']
    fe = F['front']['eyes']
    # the QA's classes (charkit.bodyqa: colour families; the orange split into hair and dress by where each drawn region
    # lies, above the shoulders or below), over every figure at once: the sheet's figures share one eye line
    fg = sheetqa.foreground(rgb, sheetqa.background(rgb))
    cls = bodyqa.classes(rgb, fg, float(np.mean([e[1] for e in fe])), ppl)[0].astype(np.uint8)
    ax_front = float(np.mean([e[0] for e in fe]))
    eye_front = float(np.mean([e[1] for e in fe]))
    m = F['profile']['_mask']
    ey_p = float(F['profile']['eye_y'])
    rows = range(int(ey_p + 1.0 * ppl), int(ey_p + 2.0 * ppl))           # the torso's band: the profile's (free) axis
    c = [(np.nonzero(m[r])[0][[0, -1]].mean()) for r in rows if m[r].any()]
    ax_prof = float(np.median(c))
    y_e = (F['profile']['eyes'][0][0] - ax_prof) / ppl
    views = {'front': View('front', 0.0, F['front']['_mask'], ppl, ax_front, eye_front, cls, rgb),
             'profile': View('profile', 90.0, m, ppl, ax_prof, ey_p, cls, rgb)}
    info = {'ppl': ppl, 'y_e': round(y_e, 4)}
    if 'three_quarter' in F and len(F['three_quarter']['eyes']) == 2:
        te = F['three_quarter']['eyes']
        az3 = float(np.degrees(np.arccos(np.clip(abs(te[1][0] - te[0][0]) / (abs(fe[1][0] - fe[0][0])), 0, 1))))
        mid = float(np.mean([e[0] for e in te]))
        ax3 = mid - y_e * np.sin(np.radians(az3)) * ppl
        views['three_quarter'] = View('three_quarter', az3, F['three_quarter']['_mask'], ppl, ax3,
                                      float(np.mean([e[1] for e in te])), cls, rgb)
        info['az3'] = round(az3, 2)
    if 'back' in F:
        b = F['back']
        views['back'] = View('back', 180.0, b['_mask'], ppl, float(b.get('axis_x') or b['box'][0] + (b['box'][2] - b['box'][0]) / 2),
                             eye_front, cls, rgb)
    for n, v in views.items():
        v.grid_eye = bodyqa.view_eye(n, F[n])
    info['axes'] = {k: round(v.axis, 2) for k, v in views.items()}
    return views, info


NECK_BAND = (-0.62, -0.50)          # L from the eye line: a head sheet's neck, under the chin, above the bust's vignette
HEAD_FLOOR = -0.66                  # a head sheet's hull stops here: below, the bust is cut by the sheet's vignette


def views_from_heads(rgb, eye_x, facing=-1, floor=HEAD_FLOOR):
    """a head turnaround's views (charkit.refcheck.detect_heads), calibrated from their eyes as views_from_sheet's, each
    at its own eye line (a generated sheet's rows drift a few pixels). The profile's free axis and the back's axis are
    the neck's centre (NECK_BAND); every mask stops at `floor` L. -> ({view: View}, info)."""
    from charkit import bodyqa, refcheck, sheetqa
    D = refcheck.detect_heads(rgb, eye_x, facing)
    ppl, F = D['ppl'], D['heads']
    fg = sheetqa.foreground(rgb, sheetqa.background(rgb))
    fe = F['front']['eyes']
    cls = bodyqa.classes(rgb, fg, F['front']['eye_y'], ppl)[0].astype(np.uint8)

    def neck_axis(m, ey):
        rows = range(int(ey - NECK_BAND[1] * ppl), int(ey - NECK_BAND[0] * ppl))
        return float(np.median([np.nonzero(m[r])[0][[0, -1]].mean() for r in rows if m[r].any()]))

    def masked(m, ey):
        m = m.copy()
        m[int(round(ey - floor * ppl)):] = False
        return m
    views, info = {}, {'ppl': ppl, 'eye_rows': {k: h['eye_y'] for k, h in F.items()}}
    f = F['front']
    views['front'] = View('front', 0.0, masked(f['_mask'], f['eye_y']), ppl, float(np.mean([e[0] for e in fe])),
                          f['eye_y'], cls, rgb)
    p = F['profile']
    ax_prof = neck_axis(p['_mask'], p['eye_y'])
    y_e = (p['eyes'][0][0] - ax_prof) / ppl
    views['profile'] = View('profile', 90.0, masked(p['_mask'], p['eye_y']), ppl, ax_prof, p['eye_y'], cls, rgb)
    info['y_e'] = round(y_e, 4)
    if 'three_quarter' in F and len(F['three_quarter']['eyes']) == 2:
        t = F['three_quarter']; te = t['eyes']
        az3 = float(np.degrees(np.arccos(np.clip(abs(te[1][0] - te[0][0]) / abs(fe[1][0] - fe[0][0]), 0, 1))))
        ax3 = float(np.mean([e[0] for e in te])) - y_e * np.sin(np.radians(az3)) * ppl
        views['three_quarter'] = View('three_quarter', az3, masked(t['_mask'], t['eye_y']), ppl, ax3, t['eye_y'], cls, rgb)
        info['az3'] = round(az3, 2)
    if 'back' in F:
        b = F['back']
        views['back'] = View('back', 180.0, masked(b['_mask'], b['eye_y']), ppl, neck_axis(b['_mask'], b['eye_y']),
                             b['eye_y'], cls, rgb)
    for n, v in views.items():
        v.grid_eye = (v.axis, v.eye_y)
    info['axes'] = {k: round(v.axis, 2) for k, v in views.items()}
    info['front_neck_offset_L'] = round((neck_axis(f['_mask'], f['eye_y']) - views['front'].axis) / ppl, 4)
    return views, info


# ------------------------------------------------------------------------------------------------------------- pieces
CORE, ARM, LEG = 0, 1, 2            # the limbs: a front run splits where they meet, each part paired with its own depth
FREE_SKIN = -1                      # a limb image's free skin (no piece) the skeleton can't place: the oblique and side views
LIMB_BONES = {ARM: ('UpperArm', 'LowerArm', 'Hand'), LEG: ('UpperLeg', 'LowerLeg', 'Foot', 'Toes')}
FREE = 1000                         # a volume label no piece claims: FREE + its class (bodyqa.CLASS)


def limb_of(bone):
    for t, parts in LIMB_BONES.items():
        if bone and any(b in bone for b in parts):
            return t
    return CORE


class Pieces:
    """the outfit graph's pieces as the hull reads them (charkit.outfit; the graph the masks were cut with): label k + 1
    for piece k, 0 for none. limb: each label's limb (by its attach bone); mirror: each label's mirror partner's (its
    pair on the other side, else itself); skeleton: the graph's bones as front-view segments (x toward her left, z up
    from the eye line, L)."""

    def __init__(self, graph):
        P = graph['pieces']
        self.ids = [p['id'] for p in P]
        self.limb = np.array([CORE] + [limb_of((p.get('attach') or {}).get('bone')) for p in P], np.int8)
        self.mirror = np.arange(len(P) + 1)
        by = {(p.get('pair'), p.get('side')): k + 1 for k, p in enumerate(P)}
        for k, p in enumerate(P):
            if p.get('pair') and p.get('side') in ('L', 'R'):
                self.mirror[k + 1] = by.get((p['pair'], 'R' if p['side'] == 'L' else 'L'), k + 1)
        self.skeleton = {b: np.asarray(seg, float) for b, seg in (graph.get('skeleton') or {}).items()}

    def name(self, label):
        """a volume label's name: the piece's id, or FREE + class as the class's name."""
        from charkit.bodyqa import CLASS
        if 0 < label <= len(self.ids):
            return self.ids[label - 1]
        if label >= FREE:
            return {v: k for k, v in CLASS.items()}.get(label - FREE, 'class %d' % (label - FREE))
        return 'none'


def attach_pieces(views, masks_path):
    """the outfit's per-view piece masks (outfit_masks.npz, keys VIEW__PIECE on bodyqa.design_views grids; its graph
    outfit_graph.json beside it) onto the views' pictures: View.pieces and View.limbs, in place -> Pieces."""
    from charkit import bodyqa
    P = Pieces(json.load(open(os.path.join(os.path.dirname(masks_path), 'outfit_graph.json'))))
    M = np.load(masks_path)
    k_of = {pid: k + 1 for k, pid in enumerate(P.ids)}
    win = bodyqa.WIN
    for n, v in views.items():
        img = np.zeros(v.mask.shape, np.int16)
        x0 = int(round(v.grid_eye[0] - win['x'] * v.ppl)); y0 = int(round(v.grid_eye[1] - win['top'] * v.ppl))
        for key in M.files:
            vn, pid = key.split('__', 1)
            if vn != n or pid not in k_of:
                continue
            m = M[key]
            H, W = img.shape
            sy0, sx0 = max(0, y0), max(0, x0)
            sy1, sx1 = min(H, y0 + m.shape[0]), min(W, x0 + m.shape[1])
            if sy1 > sy0 and sx1 > sx0:
                sub = m[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] & v.mask[sy0:sy1, sx0:sx1]
                img[sy0:sy1, sx0:sx1][sub] = k_of[pid]
        v.pieces = img
        v.limbs = limb_image(v, P)
    return P


def limb_image(v, P):
    """each pixel's limb: a piece's by its bone; free skin's by the nearest bone of the graph's skeleton on the front
    and back (where the skeleton's x shows as drawn), FREE_SKIN on the other views; anything else CORE. -> int8 image."""
    out = P.limb[v.pieces]
    free = (v.pieces == 0) & (v.labels == SKIN) & v.mask
    a = np.radians(v.az)
    if abs(np.sin(a)) < 1e-9 and P.skeleton:
        r, c = np.nonzero(free)
        x = (c - v.axis) / v.ppl * np.cos(a); z = (v.eye_y - r) / v.ppl
        pts = np.stack([x, z], 1)
        best, lim = np.full(len(pts), np.inf), np.zeros(len(pts), np.int8)
        for bone, (p0, p1) in P.skeleton.items():
            d = p1 - p0
            t = np.clip(((pts - p0) @ d) / max(d @ d, 1e-12), 0, 1)
            dist = np.linalg.norm(pts - (p0 + t[:, None] * d), axis=1)
            take = dist < best
            best[take], lim[take] = dist[take], limb_of(bone)
        out[r, c] = lim
    else:
        out[free] = FREE_SKIN
    return out


def mirrored(v, P):
    """the view of the figure's mirror image, at -az: by symmetry what the far side shows (a profile's other side, a
    three-quarter's other quarter), with each piece swapped for its mirror partner. For labels only: a silhouette's
    mirror carves nothing new (the view from az + 180 is the same silhouette mirrored)."""
    W = v.mask.shape[1]
    m = View(v.name + '_mirror', (-v.az) % 360.0, v.mask[:, ::-1], v.ppl, W - 1 - v.axis, v.eye_y,
             None if v.labels is None else v.labels[:, ::-1], None if v.rgb is None else v.rgb[:, ::-1])
    if v.pieces is not None:
        m.pieces = P.mirror[v.pieces[:, ::-1]].astype(np.int16)
        m.limbs = v.limbs[:, ::-1]
    return m


class Axes:
    """the voxel grid's axes (L): xs, ys, zs (z descending from the top), spacing h."""

    def __init__(self, xs, ys, zs, h):
        self.xs, self.ys, self.zs, self.h = xs, ys, zs, h

    @property
    def shape(self):
        return (len(self.xs), len(self.ys), len(self.zs))


def axes_for(views, h=0.01, pad=0.05):
    """a grid covering every view's figure: x from the front, y from the profile, z from the tallest to the lowest."""
    def extent(v, axis_is):
        cols = np.nonzero(v.mask.any(0))[0]; rows = np.nonzero(v.mask.any(1))[0]
        u = ((cols[[0, -1]] - v.axis) / v.ppl)
        z = ((v.eye_y - rows[[-1, 0]]) / v.ppl)
        return u, z
    uf, zf = extent(views['front'], 'x')
    up, zp = extent(views['profile'], 'y')
    zlo = min(zf[0], zp[0]) - pad; zhi = max(zf[1], zp[1]) + pad
    ext = max(abs(uf).max(), abs(extent(views['back'], 'x')[0]).max() if 'back' in views else 0) + pad
    xs = np.arange(-ext, ext + h / 2, h)
    ys = np.arange(up[0] - pad, up[1] + pad + h / 2, h)
    zs = np.arange(zhi, zlo - h / 2, -h)
    return Axes(xs, ys, zs, h)


def carve(views, A, use):
    """the plain hull of the views named in `use` -> bool (nx, ny, nz)."""
    V = np.ones(A.shape, bool)
    for n in use:
        v = views[n]
        a = np.radians(v.az)
        if abs(np.sin(a)) < 1e-9:                                          # front / back: u = +-x
            V &= v.sample(v.mask, np.cos(a) * A.xs, A.zs)[:, None, :]
        elif abs(np.cos(a)) < 1e-9:                                        # the profiles: u = +-y
            V &= v.sample(v.mask, np.sin(a) * A.ys, A.zs)[None, :, :]
        else:                                                              # an oblique view: per (x, y) column
            U = A.xs[:, None] * np.cos(a) + A.ys[None, :] * np.sin(a)
            c, r = v.pixel(U, A.zs)
            H, W = v.mask.shape
            ok = (c >= 0) & (c < W)
            cc = np.clip(c, 0, W - 1); rr = np.clip(r, 0, H - 1)
            V &= v.mask[rr[None, None, :], cc[:, :, None]] & ok[:, :, None] & ((r >= 0) & (r < H))[None, None, :]
    return V


def _runs(b):
    d = np.diff(np.concatenate([[0], b.astype(np.int8), [0]]))
    return list(zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0] - 1))


def _split(g, min_w):
    """a run's cells (their limb values g) as maximal sub-runs of one value, a sub-run narrower than min_w cells joined
    to its wider neighbour -> [(a, b, value)], a and b inclusive, relative to the run."""
    cut = np.flatnonzero(np.diff(g)) + 1
    R = [[a, b - 1, int(g[a])] for a, b in zip(np.r_[0, cut], np.r_[cut, len(g)])]
    while len(R) > 1:
        w = [b - a + 1 for a, b, _ in R]
        i = int(np.argmin(w))
        if w[i] >= min_w:
            break
        j = i - 1 if i == len(R) - 1 or (i > 0 and w[i - 1] >= w[i + 1]) else i + 1
        R[j] = [min(R[i][0], R[j][0]), max(R[i][1], R[j][1]), R[j][2]]
        del R[i]
        k = 1
        while k < len(R):                                                  # neighbours of one value merge
            if R[k][2] == R[k - 1][2]:
                R[k - 1][1] = R[k][1]
                del R[k]
            else:
                k += 1
    return [tuple(r) for r in R]


def rounded(views, A, use, p=2.0, class_share=0.6, smooth=0.02, limbs=True, split_min=0.04):
    """the shape prior's hull (see the module): superellipse sections |x/rx|^p + |y/ry|^p <= 1 per (front run x side
    run), class-aware, smoothed across heights by `smooth` L (a Gaussian on its signed distance), inside the plain hull
    of `use`. With the views' pieces (attach_pieces) and `limbs`, a front run splits where an arm or a leg meets the
    body (sub-runs under `split_min` L join a neighbour), and each limb part takes its depth from the side view's pixels
    of that limb (its pieces and the free skin): a wrist cuff from the forearm drawn over the skirt, not the skirt's
    depth. Needs the front and a profile among `use`; else the plain hull. -> bool (nx, ny, nz)."""
    plain = carve(views, A, use)
    if 'front' not in use or 'profile' not in use:
        return plain
    f, s = views['front'], views['profile']
    Fxz = f.sample(f.mask, A.xs, A.zs)
    if 'back' in use:
        b = views['back']
        Fxz &= b.sample(b.mask, -A.xs, A.zs)
    Fskin = f.sample(f.labels, A.xs, A.zs) == SKIN
    Syz = s.sample(s.mask, A.ys, A.zs)
    Sskin = (s.sample(s.labels, A.ys, A.zs) == SKIN) & Syz
    Flimb, Slimb = None, {}
    if limbs and f.limbs is not None and s.limbs is not None:
        Flimb = f.sample(f.limbs, A.xs, A.zs)
        Sl = s.sample(s.limbs, A.ys, A.zs)
        Slimb = {t: ((Sl == t) | (Sl == FREE_SKIN)) & Syz for t in (ARM, LEG)}
    min_w = max(1, int(round(split_min / A.h)))
    V = np.zeros(A.shape, bool)
    X, Y = np.meshgrid(A.xs, A.ys, indexing='ij')
    for k in range(len(A.zs)):
        side, side_skin = _runs(Syz[:, k]), _runs(Sskin[:, k])
        side_limb = {t: _runs(m[:, k]) for t, m in Slimb.items()}
        for r0, r1 in _runs(Fxz[:, k]):
            parts = [(r0 + a, r0 + b, t) for a, b, t in _split(Flimb[r0:r1 + 1, k], min_w)] if Flimb is not None \
                else [(r0, r1, CORE)]
            for x0, x1, t in parts:
                if t in side_limb and side_limb[t]:
                    ys = side_limb[t]
                else:
                    skin = Fskin[x0:x1 + 1, k].mean() > class_share
                    ys = side_skin if skin and side_skin else side
                for y0, y1 in ys:
                    cx, rx = (A.xs[x0] + A.xs[x1]) / 2, (A.xs[x1] - A.xs[x0]) / 2 + A.h / 2
                    cy, ry = (A.ys[y0] + A.ys[y1]) / 2, (A.ys[y1] - A.ys[y0]) / 2 + A.h / 2
                    V[:, :, k] |= (np.abs((X - cx) / rx) ** p + np.abs((Y - cy) / ry) ** p) <= 1
    V &= plain
    if smooth > 0:
        from scipy.ndimage import distance_transform_edt, gaussian_filter
        d = distance_transform_edt(~V) - distance_transform_edt(V)          # signed distance in voxels (+ outside)
        d = gaussian_filter(d.astype(np.float32), (0.3 * smooth / A.h, 0.3 * smooth / A.h, smooth / A.h))
        Vs = (d < 0) & plain
        # the silhouettes restored: where a given view's drawing shows figure the smoothed hull no longer covers (a
        # finger, a hair tip the blur eroded), the unsmoothed voxels on those rays come back; the smoothing acts only
        # where no view says anything
        for n in use:
            v = views[n]
            a = np.radians(v.az)
            Ps, us = project(Vs, A, v.az)
            Dm = v.sample(v.mask, us, A.zs)
            miss = Dm & ~Ps
            ix, iy, iz = np.nonzero(V & ~Vs)
            iu = np.clip(np.round((A.xs[ix] * np.cos(a) + A.ys[iy] * np.sin(a) - us[0]) / A.h).astype(int), 0, len(us) - 1)
            back = miss[iu, iz]
            ix, iy, iz, iu = ix[back], iy[back], iz[back], iu[back]
            if not len(ix):
                continue
            # one voxel per missing pixel, the one at the median depth on its ray: enough to show there, without
            # giving back the depth a slab had (which the unseen views would show)
            key = iu.astype(np.int64) * len(A.zs) + iz
            dep = -A.xs[ix] * np.sin(a) + A.ys[iy] * np.cos(a)
            o = np.lexsort((dep, key))
            k_sorted = key[o]
            starts = np.flatnonzero(np.r_[True, k_sorted[1:] != k_sorted[:-1]])
            ends = np.r_[starts[1:], len(o)]
            pick = o[(starts + ends - 1) // 2]
            Vs[ix[pick], iy[pick], iz[pick]] = True
        V = Vs
    return V


def project(V, A, az, u0=-3.0, u1=3.0):
    """a hull's silhouette at azimuth `az` on a (u, z) grid of the voxel spacing -> (bool (nu, nz), us)."""
    a = np.radians(az)
    ix, iy, iz = np.nonzero(V)
    u = A.xs[ix] * np.cos(a) + A.ys[iy] * np.sin(a)
    us = np.arange(u0, u1, A.h)
    iu = np.clip(np.round((u - u0) / A.h).astype(int), 0, len(us) - 1)
    M = np.zeros((len(us), len(A.zs)), bool)
    M[iu, iz] = True
    return M, us


def iou(a, b):
    return float((a & b).sum() / max(1, (a | b).sum()))


def score(V, A, view):
    """a hull against one view's drawing: IoU of its silhouette there, and the horizontal offset (L) at which the
    drawing fits it best (0 for a well calibrated view) -> dict."""
    P, us = project(V, A, view.az)
    Dm = view.sample(view.mask, us, A.zs)
    s = iou(P, Dm)
    best = (s, 0.0)
    for d in np.arange(-0.1, 0.1 + 1e-9, A.h):                          # the calibration check
        b = iou(P, view.sample(view.mask, us + d, A.zs))
        if b > best[0] + 1e-9:
            best = (b, d)
    return {'iou': round(s, 4), 'best_offset_L': round(best[1], 3), 'iou_at_best': round(best[0], 4)}


# --------------------------------------------------------------------------------------------------------------- labels
def _shell(V):
    from scipy.ndimage import binary_erosion
    return V & ~binary_erosion(V)


def _normals(V, ix, iy, iz, sigma=1.5):
    """outward unit normals at voxels, from the gradient of the occupancy blurred `sigma` voxels -> (N, 3)."""
    from scipy.ndimage import gaussian_filter
    G = gaussian_filter(V.astype(np.float32), sigma)
    I = [ix, iy, iz]
    n = []
    for ax in range(3):
        lo, hi = list(I), list(I)
        lo[ax] = np.clip(I[ax] - 1, 0, V.shape[ax] - 1); hi[ax] = np.clip(I[ax] + 1, 0, V.shape[ax] - 1)
        n.append(G[tuple(lo)] - G[tuple(hi)])
    n = np.stack(n, 1)
    n[:, 2] *= -1                                                          # the grid's z index runs down
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)


def _visible(ix, iy, iz, A, az, u0=-3.0, tol=None):
    """of shell voxels, those a view sees: within `tol` (default 1.5 voxels) of the nearest to its camera on each ray,
    rays binned on the voxel spacing as project's pixels (a z-buffer test with a bias: at an oblique view a slanted
    surface's voxels share bins, and only the single nearest would leave stripes unseen) -> (bool (N,), their u bins)."""
    a = np.radians(az)
    u = A.xs[ix] * np.cos(a) + A.ys[iy] * np.sin(a)
    dep = A.xs[ix] * np.sin(a) - A.ys[iy] * np.cos(a)                     # toward the camera
    iu = np.round((u - u0) / A.h).astype(np.int64)
    key = iu * len(A.zs) + iz
    uk, inv = np.unique(key, return_inverse=True)
    near = np.full(len(uk), -np.inf)
    np.maximum.at(near, inv, dep)
    return dep >= near[inv] - (1.5 * A.h if tol is None else tol), iu


def label_volume(V, A, views, names, normals=None):
    """the hull's surface labelled from the views named: each shell voxel takes what the view facing it most squarely,
    among those that see it (nearest the camera on its ray, inside the drawing), draws at its pixel: the piece (View.pieces)
    or else FREE + the class. Shell voxels no view sees take their nearest labelled neighbour's. -> dict(ix, iy, iz
    (the shell voxels), label, cls, seen, normals)."""
    S = _shell(V)
    ix, iy, iz = np.nonzero(S)
    N = _normals(V, ix, iy, iz) if normals is None else normals
    best = np.full(len(ix), -np.inf)
    lab = np.zeros(len(ix), np.int32); cls = np.zeros(len(ix), np.int16)
    for n in names:
        v = views[n]
        a = np.radians(v.az)
        w = N @ np.array([np.sin(a), -np.cos(a), 0.0])
        vis, _ = _visible(ix, iy, iz, A, v.az)
        c, r = v.pixel(v.u_of(A.xs[ix], A.ys[iy]), A.zs[iz])
        H, W = v.mask.shape
        ok = vis & (c >= 0) & (c < W) & (r >= 0) & (r < H)
        ok[ok] = v.mask[r[ok], c[ok]]
        take = ok & (w > best)
        cc = v.labels[r[take], c[take]]
        pc = v.pieces[r[take], c[take]] if v.pieces is not None else np.zeros(len(cc), np.int16)
        lab[take] = np.where(pc > 0, pc, FREE + cc.astype(np.int32))
        cls[take] = cc
        best[take] = w[take]
    seen = np.isfinite(best)
    if (~seen).any() and seen.any():
        from scipy.spatial import cKDTree
        P = np.stack([ix, iy, iz], 1)
        _, j = cKDTree(P[seen]).query(P[~seen])
        lab[~seen] = lab[seen][j]; cls[~seen] = cls[seen][j]
    return dict(ix=ix, iy=iy, iz=iz, label=lab, cls=cls, seen=seen, normals=N)


def render_labels(L, A, az, u0=-3.0, u1=3.0):
    """a labelled surface's front-most label per pixel of a view at az, on project's (u, z) grid -> (int (nu, nz), us)."""
    us = np.arange(u0, u1, A.h)
    vis, iu = _visible(L['ix'], L['iy'], L['iz'], A, az, u0, tol=0.0)
    img = np.zeros((len(us), len(A.zs)), np.int32)
    ok = vis & (iu >= 0) & (iu < len(us))
    img[iu[ok], L['iz'][ok]] = L['label'][ok]
    return img, us


def drawn_labels(v, us, A):
    """a view's drawing as volume labels on a (u, z) grid: its pieces, else FREE + its class; 0 off the figure."""
    M = v.sample(v.mask, us, A.zs)
    C = v.sample(v.labels, us, A.zs).astype(np.int32)
    Pc = v.sample(v.pieces, us, A.zs).astype(np.int32) if v.pieces is not None else np.zeros_like(C)
    return np.where(M, np.where(Pc > 0, Pc, FREE + C), 0)


def label_scores(pred, drawn, P=None, tol=2):
    """labels predicted against drawn: per label IoU and areas; 'agree': the share of pixels both call figure where the
    labels match; 'agree_tol': where the drawing has the predicted label within `tol` pixels (the drawn outlines between
    pieces are a class of their own, a pixel or two wide); 'pieces_iou': the pieces' IoUs weighted by their drawn area."""
    from scipy.ndimage import binary_dilation
    both = (pred > 0) & (drawn > 0)
    near = np.zeros(pred.shape, bool)
    st = np.ones((2 * tol + 1, 2 * tol + 1), bool)
    for l in np.unique(pred[both]):
        m = both & (pred == l)
        near[m] = binary_dilation(drawn == l, st)[m]
    out = {'agree': round(float((pred[both] == drawn[both]).mean()) if both.any() else 0.0, 4),
           'agree_tol': round(float(near[both].mean()) if both.any() else 0.0, 4), 'labels': {}}
    wsum = wtot = 0.0
    for l in sorted((set(np.unique(pred)) | set(np.unique(drawn))) - {0}):
        a, b = pred == l, drawn == l
        s = iou(a, b)
        name = P.name(int(l)) if P else str(l)
        out['labels'][name] = {'label': int(l), 'iou': round(s, 4), 'drawn_px': int(b.sum()), 'pred_px': int(a.sum())}
        if l < FREE:
            wsum += s * b.sum(); wtot += b.sum()
    out['pieces_iou'] = round(wsum / max(wtot, 1), 4)
    return out


def label_views(views, P):
    """the views to label from: the drawn ones and, when pieces are known, the mirrors of the oblique and side views (the
    far side by symmetry)."""
    out = dict(views)
    if P is not None:
        for n, v in views.items():
            if abs(np.sin(np.radians(v.az))) > 1e-9:
                out[n + '_mirror'] = mirrored(v, P)
    return out


def validate_labels(V, A, views, P):
    """the pieces' labels checked two ways: 'used', every view against the labels from all of them; 'held_out', each
    drawn view against the labels from the others (its own mirror left out too) -> (scores, the labels from all; each
    held-out labelling under Lall['held'][view])."""
    LV = label_views(views, P)
    Lall = label_volume(V, A, LV, list(LV))
    Lall['held'] = {}
    out = {'used': {}, 'held_out': {}}
    for n, v in views.items():
        img, us = render_labels(Lall, A, v.az)
        out['used'][n] = label_scores(img, drawn_labels(v, us, A), P)
        L = Lall['held'][n] = label_volume(V, A, LV, [k for k in LV if k.split('_mirror')[0] != n],
                                           normals=Lall['normals'])
        img, us = render_labels(L, A, v.az)
        out['held_out'][n] = label_scores(img, drawn_labels(v, us, A), P)
    return out, Lall


def vertex_labels(m, L, A):
    """each mesh vertex's label and class: its nearest shell voxel's -> (int16 (N,), int16 (N,))."""
    from scipy.spatial import cKDTree
    C = np.stack([A.xs[L['ix']], A.ys[L['iy']], A.zs[L['iz']]], 1)
    _, j = cKDTree(C).query(m.V)
    return L['label'][j].astype(np.int16), L['cls'][j].astype(np.int16)


def refine(views, A, prior, bound=0.1):
    """the oblique views' axes refined by their silhouettes: each against the hull of the axis-aligned views, the
    horizontal offset (within `bound` L) where its drawing fits best. The eyes calibrate a three-quarter only roughly: its
    far eye shows partly, so its visible centroid sits toward the nose. In place -> {view: offset L}."""
    fixed = [n for n, v in views.items() if abs(np.sin(np.radians(v.az))) < 1e-9 or abs(np.cos(np.radians(v.az))) < 1e-9]
    out = {}
    for n, v in views.items():
        if n in fixed:
            continue
        V = rounded(views, A, fixed, **prior)
        P, us = project(V, A, v.az)
        best = (-1.0, 0.0)
        for d in np.arange(-bound, bound + 1e-9, A.h / 2):
            b = iou(P, v.sample(v.mask, us + d, A.zs))
            if b > best[0]:
                best = (b, d)
        v.axis += best[1] * v.ppl                     # the drawing at u + d fits: the axis moves by d
        out[n] = round(float(best[1]), 4)
    return out


def validate(views, A, method='rounded', **prior):
    """leave one out: each view predicted from the others -> {view: score + 'from'}; also each view against the hull of
    all of them ('used')."""
    names = list(views)
    out = {}
    for held in names:
        use = [n for n in names if n != held]
        V = rounded(views, A, use, **prior) if method == 'rounded' else carve(views, A, use)
        out[held] = dict(score(V, A, views[held]), **{'from': use, 'method': method if 'profile' in use else 'carve'})
    Vall = rounded(views, A, names, **prior) if method == 'rounded' else carve(views, A, names)
    out['used'] = {n: score(Vall, A, views[n]) for n in names}
    return out, Vall


def surface(V, A, views=None, blur=1.0):
    """the hull's closed surface (charkit.geom.volume.to_mesh on its occupancy, blurred `blur` voxels), in L, z up from
    the eye line, with vertex colours from the view whose camera faces each vertex most -> Mesh."""
    from . import mesh as meshlib, volume
    G = volume.Grid((A.xs[0], A.ys[0], A.zs[-1]), A.h, V[:, :, ::-1])     # z ascending for the grid
    m = volume.to_mesh(G, blur=blur)
    if views and len(m.V):
        N = meshlib.vertex_normals(m.V, m.F)
        cams = {n: np.array([np.sin(np.radians(v.az)), -np.cos(np.radians(v.az)), 0.0]) for n, v in views.items()}
        names = list(views)
        best = np.argmax(np.stack([N @ cams[n] for n in names], 1), 1)
        col = np.zeros((len(m.V), 3))
        for i, n in enumerate(names):
            sel = best == i
            if not sel.any():
                continue
            v = views[n]
            c, r = v.pixel(v.u_of(m.V[sel, 0], m.V[sel, 1]), m.V[sel, 2])
            H, W = v.rgb.shape[:2]
            col[sel] = v.rgb[np.clip(r, 0, H - 1), np.clip(c, 0, W - 1)]
        m.vc = col
    return m


def label_vertices(m, views):
    """each vertex's class (charkit.bodyqa.CLASS) from the view whose camera faces it most -> int array (N,)."""
    from .mesh import vertex_normals
    N = vertex_normals(m.V, m.F)
    names = list(views)
    cams = np.stack([[np.sin(np.radians(views[n].az)), -np.cos(np.radians(views[n].az)), 0.0] for n in names])
    best = np.argmax(N @ cams.T, 1)
    lab = np.zeros(len(m.V), np.int16)
    for i, n in enumerate(names):
        sel = best == i
        if sel.any():
            v = views[n]
            c, r = v.pixel(v.u_of(m.V[sel, 0], m.V[sel, 1]), m.V[sel, 2])
            H, W = v.labels.shape
            lab[sel] = v.labels[np.clip(r, 0, H - 1), np.clip(c, 0, W - 1)]
    return lab


def build(spec, out, h=0.01, style=None, faces=150000, validate_views=True, page=True, pieces=True, sheet='body',
          log=print):
    """a resolved spec's hull into `out`: hull.glb (coloured, with its sidecar hull.glb.json: the eyes, exactly, the
    per-vertex classes hull_labels.npy and, with the outfit's piece masks, the per-vertex pieces hull_pieces.npy),
    hull.ply, hull.npz (the occupancy and its labelled shell), hull.json (calibration, the leave-one-out scores when
    validate_views, the mesh's health) and the review page. validate_views=False: the fast path a build takes (no
    leave-one-out sweeps, no page). pieces: carve and label per piece from the manifest's outfit_masks (built where
    missing). sheet 'head': the head turnaround's hull instead (the manifest's sheets.face; views_from_heads), for the
    head's shape, without pieces. -> the report."""
    import time
    from charkit import eyes as eyelib, manifest, refcheck, styles
    from . import io, remesh, repair
    t0 = time.time()
    bs = spec['ref'].get('face_sheet' if sheet == 'head' else 'body_sheet')
    if not bs:
        raise ValueError("hull: the spec has no generated %s sheet (the manifest's sheets.%s)" % (
            sheet, 'face' if sheet == 'head' else 'body'))
    style = style or spec.get('style', 'anime')
    prior = styles.load(style)['hull']
    ex = eyelib._knobs(spec.get('eyes'))['x']
    if sheet == 'head':
        views, info = views_from_heads(refcheck._load(bs['image']), ex, bs.get('facing', -1))
        pieces = False
    else:
        views, info = views_from_sheet(refcheck._load(bs['image']), ex, bs.get('facing', -1))
    A = axes_for(views, h)
    os.makedirs(out, exist_ok=True)
    rep = {'spec': spec.get('name'), 'sheet': bs['image'], 'style': style, 'prior': prior, 'grid': list(A.shape), 'h_L': A.h}
    masks = manifest.produced(spec, 'outfit_masks', log) if pieces else None
    P = attach_pieces(views, masks) if masks and os.path.exists(masks) else None
    rep['pieces'] = {'masks': masks and os.path.relpath(masks, manifest.ROOT), 'n': len(P.ids) if P else 0}
    if validate_views:
        rep['leave_one_out_eyes_only'], _ = validate(views, A, 'rounded', **prior)      # the eyes' calibration alone
    info['refined_L'] = refine(views, A, prior)
    if validate_views:
        rep['leave_one_out'], V = validate(views, A, 'rounded', **prior)
        rep['plain_leave_one_out'], _ = validate(views, A, 'carve')
        if P is not None:
            rep['leave_one_out_no_limbs'], _ = validate(views, A, 'rounded', **dict(prior, limbs=False))
    else:
        V = rounded(views, A, list(views), **prior)
    L = None
    if P is not None:
        if validate_views:
            rep['pieces']['labels'], L = validate_labels(V, A, views, P)
        else:
            LV = label_views(views, P)
            L = label_volume(V, A, LV, list(LV))
    m = surface(V, A, views)
    full = len(m.F)
    m = remesh.decimate(m, faces)
    io.save(m, os.path.join(out, 'hull.ply'))
    io.save(m, os.path.join(out, 'hull.glb'))            # a coloured 'generated character' for charkit.geom.parts
    np.save(os.path.join(out, 'hull_labels.npy'), label_vertices(m, views))     # per vertex, bodyqa.CLASS
    side = {'labels': 'hull_labels.npy'}
    shell = {}
    if L is not None:
        vl, _ = vertex_labels(m, L, A)
        np.save(os.path.join(out, 'hull_pieces.npy'), vl)                       # per vertex, Pieces labels
        side.update(pieces='hull_pieces.npy', piece_names={int(l): P.name(int(l)) for l in np.unique(vl)})
        shell = dict(shell=np.stack([L['ix'], L['iy'], L['iz']], 1).astype(np.int16), shell_label=L['label'])
    ey = info['y_e']                                      # its eyes, known exactly (charkit.i3d.glb_eyes reads them)
    json.dump(dict({'eyes': [[ex, ey, 0.0], [-ex, ey, 0.0]], 'units': 'L', 'by': 'charkit.geom.hull'}, **side),
              open(os.path.join(out, 'hull.glb.json'), 'w'), indent=1)
    np.savez_compressed(os.path.join(out, 'hull.npz'), V=V, xs=A.xs, ys=A.ys, zs=A.zs, **shell)
    rep.update(calibration=info, mesh={'vertices': len(m.V), 'faces': len(m.F), 'faces_before_decimation': full,
                                       'health': repair.report(m)}, seconds=round(time.time() - t0, 1))
    json.dump(rep, open(os.path.join(out, 'hull.json'), 'w'), indent=1, default=str)
    if page and validate_views:
        rep['page'] = _page(rep, views, A, V, m, out, P, L)
    log('hull: %s, %d faces, three-quarter axis refined %+.3f L (%.0fs)' % (
        out, len(m.F), info['refined_L'].get('three_quarter', 0.0), time.time() - t0))
    return rep


def _pieces_section(rep, views, A, m, P, Lab, save, N, fr):
    """the page's pieces: label agreement per view (all views and held out), the held-out predictions against the
    drawings, per-piece IoUs, the surface coloured by piece, the limb maps the carving split runs by."""
    import html
    from . import raster
    S = rep['pieces']['labels']
    out = ['<h2>Pieces</h2><p class="note">The surface labelled from the outfit\'s per-view piece masks (%s): each '
           'surface voxel takes the piece (or, where no piece is drawn, the class) of the view that faces it most '
           'squarely among those that see it; the profile\'s and three-quarter\'s mirrors label the far side, pieces '
           'swapped left for right. <b>agree</b>: the share of pixels both call figure whose labels match; <b>within '
           '2 px</b>: where the drawing has the label within 0.02 L (the drawn outlines between pieces are a class of '
           'their own). <b>pieces IoU</b>: per piece, weighted by drawn area. Held out: the view\'s labels predicted '
           'from the others. The input masks are the outfit field\'s votes (0.77-0.85 IoU per view): where two views\' '
           'masks disagree about one surface, one of them loses.</p>' % html.escape(str(rep['pieces']['masks'])),
           '<table><tr><th>view</th><th>held out: agree</th><th>within 2 px</th><th>pieces IoU</th><th>used: agree</th>'
           '<th>within 2 px</th><th>pieces IoU</th></tr>']
    for n in views:
        h, u = S['held_out'][n], S['used'][n]
        out.append('<tr><td>%s</td><td>%.4f</td><td>%.4f</td><td>%.4f</td><td>%.4f</td><td>%.4f</td><td>%.4f</td></tr>' % (
            n, h['agree'], h['agree_tol'], h['pieces_iou'], u['agree'], u['agree_tol'], u['pieces_iou']))
    out.append('</table><h3>Held out: predicted | drawn | disagreement (red: both figure, labels differ)</h3>'
               '<div class="row">')
    for n, v in views.items():
        img, us = render_labels(Lab['held'][n], A, v.az)
        dr = drawn_labels(v, us, A)
        both = (img > 0) & (dr > 0)
        dis = np.full(img.shape + (3,), 0.96); dis[both] = (0.8, 0.8, 0.82); dis[both & (img != dr)] = (0.9, 0.2, 0.2)
        cols = np.nonzero(((img > 0) | (dr > 0)).any(1))[0]
        sl = slice(max(0, cols[0] - 10), cols[-1] + 10)
        for tag, im in (('pred', label_colours(img[sl], P)), ('drawn', label_colours(dr[sl], P)), ('dis', dis[sl])):
            out.append('<div class="tile"><img src="%s" height="420">%s %s</div>' % (
                save(np.transpose(im, (1, 0, 2)), 'pieces_%s_%s.png' % (n, tag)), n, tag))
        out.append('<div style="width:24px"></div>')
    out.append('</div><h3>Per piece, IoU</h3><table><tr><th>label</th>' + ''.join(
        '<th>%s held out</th><th>%s used</th>' % (n, n) for n in views) + '</tr>')
    names = sorted({k for n in views for k in S['used'][n]['labels']} | {k for n in views for k in S['held_out'][n]['labels']},
                   key=lambda k: -max(S['used'][n]['labels'].get(k, {}).get('drawn_px', 0) for n in views))
    for k in names:
        row = ['<td>%s</td>' % html.escape(k)]
        for n in views:
            for part in ('held_out', 'used'):
                e = S[part][n]['labels'].get(k)
                row.append('<td>%s</td>' % ('%.3f' % e['iou'] if e and e['drawn_px'] else '-'))
        out.append('<tr>%s</tr>' % ''.join(row))
    out.append('</table><h3>The surface by piece</h3><div class="row">')
    vl, _ = vertex_labels(m, Lab, A)
    vc = label_colours(vl, P)
    for az in (0, 35, 90, 135, 180, 225, 270, 315):
        im = raster.render([(m, dict(color=vc, normals=N, shade='lambert'))], az, fr)
        out.append('<div class="tile"><img src="%s" height="460">%d deg</div>' % (save(im, 'pieces_render_%03d.png' % az), az))
    out.append('</div><h3>Limbs: where a front run splits (grey body, blue arm, green leg, pink free skin placed by '
               'the side view)</h3><div class="row">')
    for n in ('front', 'profile'):
        v = views[n]
        rows, cols = np.nonzero(v.mask)
        im = np.full(v.mask.shape + (3,), 0.96)
        for t, c in LIMB_COLOURS.items():
            im[v.mask & (v.limbs == t)] = c
        im = im[rows.min():rows.max() + 1, cols.min():cols.max() + 1]
        out.append('<div class="tile"><img src="%s" height="520">%s</div>' % (save(im, 'limbs_%s.png' % n), n))
    out.append('</div>')
    return out


def main(args):
    """python -m charkit.geom hull SPEC [--head] [--out DIR] [--h 0.01] [--style anime] [--faces N] [--fast] [--no-open]"""
    import subprocess
    from charkit import bodyeval, refcheck
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    spec = bodyeval.resolve(args[0])
    head = '--head' in args
    out = refcheck._p(opt('--out', 'charkit/out/hull/%s%s' % (spec.get('name', 'char'), '_head' if head else '')))
    rep = build(spec, out, float(opt('--h', 0.005 if head else 0.01)), opt('--style'), int(opt('--faces', 150000)),
                validate_views='--fast' not in args, sheet='head' if head else 'body')
    loo, nol = rep.get('leave_one_out'), rep.get('leave_one_out_no_limbs')
    if loo:
        for n in [k for k in loo if k != 'used']:
            print('%-14s held out: IoU %.4f (%seyes only %.4f, plain %.4f)   used: %.4f   offset left %+.3f L' % (
                n, loo[n]['iou'], 'no limb split %.4f, ' % nol[n]['iou'] if nol else '',
                rep['leave_one_out_eyes_only'][n]['iou'], rep['plain_leave_one_out'][n]['iou'],
                loo['used'][n]['iou'], loo[n]['best_offset_L']))
    S = rep['pieces'].get('labels')
    if S:
        for n in S['used']:
            h, u = S['held_out'][n], S['used'][n]
            print('%-14s pieces: held out agree %.4f (2 px %.4f), IoU %.4f   used agree %.4f (2 px %.4f), IoU %.4f' % (
                n, h['agree'], h['agree_tol'], h['pieces_iou'], u['agree'], u['agree_tol'], u['pieces_iou']))
    if rep.get('page'):
        print('page:', rep['page'])
        if '--no-open' not in args:
            subprocess.run(['open', rep['page']])


def label_colours(labels, P=None):
    """label images (or per-vertex labels) as colours: pieces on a golden-angle hue wheel, free pixels in bodyqa's
    class palette, 0 pale grey -> float (..., 3)."""
    import colorsys
    from charkit.bodyqa import PALETTE
    out = np.zeros(np.shape(labels) + (3,))
    for l in np.unique(labels):
        if l == 0:
            c = (0.96, 0.96, 0.96)
        elif l >= FREE:
            c = PALETTE.get(int(l) - FREE, (0.5, 0.5, 0.5))
        else:
            c = colorsys.hsv_to_rgb((l * 0.618034) % 1.0, 0.7, 0.85)
        out[labels == l] = c
    return out


LIMB_COLOURS = {CORE: (0.72, 0.72, 0.75), ARM: (0.25, 0.45, 0.95), LEG: (0.2, 0.7, 0.35), FREE_SKIN: (0.98, 0.6, 0.6)}


def _page(rep, views, A, V, m, out, P=None, L=None):
    """the review page: per view the held-out prediction against the drawing, renders of the surface, the numbers."""
    import html
    from PIL import Image
    from . import raster
    img = os.path.join(out, 'img')
    os.makedirs(img, exist_ok=True)

    def save(a, name):
        Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).save(os.path.join(img, name))
        return 'img/' + name
    Lab = L
    L = ['<!doctype html><meta charset="utf-8"><title>hull</title><style>body{font:14px/1.45 -apple-system,system-ui,'
         'sans-serif;margin:24px;background:#fafafa;color:#222}h2{font-size:17px;margin-top:30px}.row{display:flex;gap:12px;'
         'flex-wrap:wrap;align-items:flex-end}.tile{text-align:center;font-size:12px;color:#555}.tile img{display:block;'
         'border:1px solid #ddd;background:#fff}table{border-collapse:collapse;font-size:13px}td,th{border:1px solid #ddd;'
         'padding:3px 8px;text-align:right}th{background:#f0f0f0}td:first-child{text-align:left}.note{color:#666;font-size:12px}'
         '</style>', '<h1>Visual hull: %s</h1>' % html.escape(os.path.basename(rep['sheet'])),
         '<p class="note">Carved from the turnaround\'s calibrated orthographic views with the %s style\'s shape prior '
         '(%s). Leave one out: each view predicted from the others (grey both, <b style="color:#e33">red</b> the hull only, '
         '<b style="color:#35f">blue</b> the drawing only). %d x %d x %d voxels of %.3f L.</p>' % (
             html.escape(rep['style']), html.escape(json.dumps(rep['prior'])), *rep['grid'], rep['h_L']),
         '<table><tr><th>view</th><th>held out (prior)</th>%s<th>held out (plain)</th><th>used (all views)</th>'
         '<th>calibration offset, L</th></tr>' % ('<th>held out, no limb split</th>' if 'leave_one_out_no_limbs' in rep else '')]
    loo, plain, nol = rep['leave_one_out'], rep['plain_leave_one_out'], rep.get('leave_one_out_no_limbs')
    for n in views:
        L.append('<tr><td>%s</td><td>%.4f</td>%s<td>%.4f</td><td>%.4f</td><td>%+.3f</td></tr>' % (
            n, loo[n]['iou'], '<td>%.4f</td>' % nol[n]['iou'] if nol else '', plain[n]['iou'], loo['used'][n]['iou'],
            loo[n]['best_offset_L']))
    L.append('</table><h2>Held-out views</h2><div class="row">')
    for n, v in views.items():
        use = [k for k in views if k != n]
        Vh = rounded(views, A, use, **rep['prior'])
        P, us = project(Vh, A, v.az)
        Dm = v.sample(v.mask, us, A.zs)
        im = np.full(P.shape + (3,), 0.96)
        im[P & Dm] = (0.55, 0.55, 0.6); im[P & ~Dm] = (0.9, 0.2, 0.2); im[Dm & ~P] = (0.2, 0.35, 0.95)
        cols = np.nonzero((P | Dm).any(1))[0]
        im = im[max(0, cols[0] - 10):cols[-1] + 10]
        L.append('<div class="tile"><img src="%s" height="520">%s: IoU %.4f</div>' % (
            save(np.transpose(im, (1, 0, 2)), 'held_%s.png' % n), n, loo[n]['iou']))
    L.append('</div><h2>The surface, coloured from the views that face it, and in clay</h2><div class="row">')
    from .mesh import vertex_normals
    N = vertex_normals(m.V, m.F)
    fr = raster.Frame.around([m], res=620, aspect=0.55)
    for shade, col in (('lambert', m.vc), ('lambert', (0.82, 0.8, 0.78))):
        L.append('<div class="row">')
        for az in (0, 35, 90, 135, 180, 225, 270, 315):
            im = raster.render([(m, dict(color=col if col is not None else (0.8, 0.8, 0.8), normals=N, shade=shade))], az, fr)
            L.append('<div class="tile"><img src="%s" height="460">%d deg</div>' % (
                save(im, 'render_%s_%03d.png' % ('colour' if col is m.vc else 'clay', az)), az))
        L.append('</div>')
    L.append('</div>')
    if P is not None and Lab is not None and rep['pieces'].get('labels'):
        L += _pieces_section(rep, views, A, m, P, Lab, save, N, fr)
    p = os.path.join(out, 'index.html')
    open(p, 'w').write('\n'.join(L))
    return p
