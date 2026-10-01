"""The hair split into locks from the drawing, the way an animator sections it (tool/hairsplit,
docs/workstreams/hairsplit.md).

A turnaround draws the hair's lock lines as open strokes: a line runs up from a notch in the hem and stops short of the
root, a lock's side is drawn where it overlaps the next and left open where it doesn't. Read as regions (the structure
labeller, hairlayers.lock_regions) a view holds 10-22 closed cells, one cell often spanning several locks. This module
closes the strokes and sections the hair into locks per view, then gives each lock an identity across the views. It is
built from the sheet alone: every length is in L (the sheet's head length, its px per L) or in the sheet's own line
width, every threshold a share of the sheet's own contrast; nothing is tuned to one character.

Per view (on the design grids, charkit.bodyqa.design_views):
  ink      the drawn strokes inside the hair: a black top-hat on the value, its threshold a share of the sheet's line
           contrast (the hair's fill against its outline's ink); the sheet's line class is ink too
  flow     the hair's orientation field: each stroke's tangent (a structure tensor on its skeleton) spread by normalised
           convolution in the doubled-angle space at two scales, a radial prior from the crown where nothing is drawn
           (the hair grows from the crown and hangs); downstream is away from the crown
  close    each open stroke end extended along the flow until it meets ink or the silhouette (capped in L), then
           trapped-ball filling (Zhang et al. 2009, "Vectorizing cartoon animations") closes the gaps left -> cells
  tips     the outline's convex corners (its outer edge and its holes: the face) whose outward direction runs downstream;
           notches are the concave ones. Each tip's axis is traced upstream along the flow, through drawn and undrawn
           hair alike
  locks    a cell holding two or more tips is split between them (a geodesic Voronoi under an anisotropic metric: cheap
           along the flow, dear across it); a cell without a tip joins the lock it flows into (its downstream exits),
           or stays a lock of its own when it flows out of the hair (a tip hidden by a clip or behind the face)
  layers   T-junctions: where a drawn stroke ends against another, the ending stroke is behind (the region across the
           bar is in front of the two the stem parts; Sykora et al. 2010's cue); ranks from the votes by least squares
Across views:
  head     each view's known camera (charkit.geom.hull: u = x cos az + y sin az, z up) and an elliptic hair shell per
           height from the front's and the profile's silhouettes: a lock's root and tip -> (azimuth, height) round the
           head's axis
  match    locks matched between views by assignment on their tips' (azimuth, height); along the hem the tips' order is
           kept (an order-preserving alignment)

Stages (for the ablation, `stage`): 'cells' (closing alone: each cell a lock), 'tips' (+ the cells holding several tips
split between them), 'locks' (+ the merge of tipless cells into the locks they flow into: the full splitter).

    python -m charkit hairsplit [SPEC] [--out DIR] [--views ...] [--stage cells|tips|locks] [--score]
"""
import json, math, os, sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORMAT = 'charkit-hair-split/1'
VIEWS = ('front', 'three_quarter', 'profile', 'back')
PIECE_MIN = 0.02           # L^2: a head piece in the hair's colour this large is a hair piece (a bun), else a clip
AZ_NOMINAL = {'front': 0.0, 'profile': 90.0, 'back': 180.0}

# every length below is in L (the sheet's head length) or in line widths (LW: the sheet's own outline width, measured)
P = dict(
    ink_share=0.15,        # a pixel is ink where it is darker than its surround by this share of the line contrast
    ink_size_lw=2.5,       # the top-hat's window, in line widths (+3 px)
    prune_lw=3.0,          # skeleton spurs shorter than this (line widths) are noise
    tangent_lw=3.0,        # a stroke's tangent from its skeleton within this radius (line widths)
    flow_s1=0.04,          # L: the flow's fine scale (normalised convolution)
    flow_s2=0.12,          # L: its coarse scale
    flow_prior=0.15,       # the crown prior's weight, as a share of the peak stroke density at the fine scale
    crown_drop=0.08,       # the crown below the hair's top at the axis, as a share of the top's height over the eye line
    ext_cap=1.0,           # L: an open stroke end is extended along the flow at most this far
    ext_down=False,        # extend the ends that stop going downstream too (off: only the upstream ends)
    ext_keep_cap=True,     # keep an extension that met nothing within the cap
    ext_skip_lw=2.0,       # an extension ignores ink this close to its start (line widths)
    ext_momentum=0.6,      # the extension's direction: this share of its own, the rest the flow's
    ext_min_lw=4.0,        # strokes shorter than this (line widths) are texture, not lock lines: not extended
    ball_lw=3.0,           # the trapped ball's largest radius (line widths)
    protrusion_r=0.0,      # L: the opening that finds the hair's protrusions (0: off)
    protrusion_len=1.0,    # a protrusion is at least this many base widths long
    cell_min=0.0012,       # L^2: a cell smaller than this joins its neighbour
    tip_scales=(0.02, 0.04, 0.07),   # L: the outline's curvature scales
    tip_prom=0.02,         # L: a tip (notch) stands out from the outline's distance to the crown by at least this
    tip_acute=75.0,        # deg: a convex corner sharper than this is a tip whatever its direction (a curled flick)
    seed_mode='axis',      # a tip's seed: 'axis' up its axis, 'disk' its end (the free hair within seed_r of it)
    seed_r=0.025,          # L: the disk seed's radius (at most half the way to the next tip)
    seed_len=0.05,         # L: an axis seed runs up its axis at most this far
    frag_min=0.0,        # L^2: a region smaller than this is a fragment: it joins its longest-edged neighbour
    lock_min=0.003,        # L^2: a tipless region this large that flows out of the hair is a lock of its own
    pieces=False,          # the hair pieces (buns) apart from the lock split (on: their removal cuts the strands under them)
    occ_tips=True,         # no tip where the outline is an occluder's (a clip) edge ('pieces': a hair piece's too)
    region_tips='multi',   # a region holding tips' seeds is theirs: True any, 'multi' only several (split between
                           # them), False none (every region tipless: own or merged)
    merge_by='vall',       # a tipless region joins: 'vall' the tips' Voronoi's majority, 'decided' the nearest decided
                           # lock (own or tips') along the flow, 'exits' the lock it flows into
    notch_lines='hem',     # a lock line traced up from each notch of the outline: 'hem' the outer outline's notches
                           # opening down only, True every notch, False none
    tones=False,
    stroke_min=0.0,        # L: an interior stroke shorter than this is texture: not a lock wall (0: every stroke is)            # the cel tones' edges cut the cells (and, along the flow, the locks)
    closure_along=0.7,     # a trapped ball's closure whose direction . the flow is at least this continues a lock line
    tip_sep=0.025,         # L: tips closer than this along the outline are one
    aniso=4.0,             # the anisotropic metric: a step across the flow costs this much more than along it
    wall_cost=40.0,        # crossing a wall pixel (drawn or extended) costs this many px
    exit_lw=4.0,           # a cell's downstream exits are probed this far past its edge (line widths)
    exit_hair=0.5,         # a tipless cell whose exits are at least this share hair joins the lock it flows into
    split_share=0.3,       # a tipless cell flowing into two locks, each with at least this share, is split between them
    axis_step=0.5,         # px: the tracing step
    axis_max=1.5,          # L: an axis is traced at most this far
    match_cost=0.15,       # L: a cross-view match costs at most this (tip distance on the shell)
    match_du=0.02,         # L: a tip's position is known to this across the picture (its azimuth interval)
    limb_spread=30.0,      # deg: a tip on the silhouette may lie this far round past the shell's limb
    near_t=3.0,            # line widths: a stroke ending this close to other ink is a T-junction's stem
    match_by='tips',       # cross-view links: 'tips' (every detected tip matched, its lock linked) or 'locks'
    match_dir=0.1,         # L per unit: the tips' outward directions' vertical parts differing costs this much
    match_root=0.0,        # the roots' azimuth gap's weight in a match's cost (0: the tips decide; a lock's root moves
                           # with how much of the unscored mass it took)
)


def _p(path):
    return path if os.path.isabs(path) else os.path.join(ROOT, path)


# ------------------------------------------------------------------------------------------------------------ inputs

def inputs(spec, cache=None, log=print):
    """the design's views as the splitter reads them -> {ppl, views: {view: dict(rgb, raw, hair, az, col_axis, row_eye,
    ppl)}}. The hair is the sheet's hair class in the view's figure, the clips the outfit graph finds drawn in the hair
    colour left out (except within the buns' rim): tools/hairlocks/ctx.py's, the lock truth's own reading."""
    import pickle
    if cache and os.path.exists(_p(cache)):
        return pickle.load(open(_p(cache), 'rb'))
    from . import hairlayers as hl, manifest
    from .geom import hull
    from scipy import ndimage
    R = manifest.load(spec['ref']['manifest'])['references']
    dv, ppl = hl.design(spec)
    rgb_b = hl.load_rgb(R['body_turnaround']['path'])
    views, info = hull.views_from_sheet(rgb_b, (spec.get('eyes') or {}).get('x', 0.168), -1)
    Z = np.load(manifest.produced(spec, 'outfit_masks'))
    om = {k: Z[k] for k in Z.files}
    # the outfit graph's pieces on the head: drawn in the hair's colour they are hair pieces of their own (buns: not cut
    # into locks), else occluders over the hair (clips: a lock's end under one is hidden, not a tip)
    graph = json.load(open(_p(R['outfit_graph']['path']))) if 'outfit_graph' in R else {'pieces': []}
    head = [pc['id'] for pc in graph.get('pieces', []) if (pc.get('attach') or {}).get('bone') == 'head']
    out = dict(ppl=ppl, views={}, info=info, head_pieces=head)
    for name in VIEWS:
        if name not in views or name not in dv:
            continue
        v = views[name]
        us, zs, shape, x0y0 = hl.design_grid(v, v.ppl)
        hair = (v.sample(v.labels, us, zs).T == 2) & (v.sample(v.mask.astype(np.uint8), us, zs).T > 0)
        pieces, occ = {}, np.zeros(shape, bool)
        for pid in head:
            m = om.get('%s__%s' % (name, pid))
            if m is None or m.shape != shape or not m.any():
                continue
            if (hair & m).sum() >= 0.5 * m.sum() and m.sum() >= PIECE_MIN * ppl ** 2:
                pieces[pid] = m
            else:
                occ |= m
        keep = np.zeros(shape, bool)
        for m in pieces.values():
            keep |= ndimage.binary_dilation(m, iterations=hl.BUN_RIM)
        # the hair as the lock truth reads it (tools/hairlocks/ctx.py): every other outfit piece out of it, except
        # within the hair pieces' rim
        for k, m in om.items():
            if k.startswith(name + '__') and k.split('__', 1)[1] not in pieces and m.shape == shape:
                hair &= ~(m & ~keep)
        d = dv[name]
        rgb = np.asarray(d['rgb'], float)
        out['views'][name] = dict(rgb=rgb / 255 if rgb.max() > 1.5 else rgb, raw=d['raw'], hair=hair, az=float(v.az),
                                  col_axis=float(v.axis - x0y0[0]), row_eye=float(v.eye_y - x0y0[1]), ppl=float(v.ppl),
                                  pieces=pieces, occ=occ & ~hair)
    if cache:
        os.makedirs(os.path.dirname(_p(cache)), exist_ok=True)
        pickle.dump(out, open(_p(cache), 'wb'))
    return out


def from_ctx(C, info):
    """tools/hairlocks/ctx.py's (or ctx5's) cached context -> inputs()'s form (az from the hull's calibration)."""
    out = dict(ppl=C['ppl'], views={}, info=info)
    for name in VIEWS:
        if name not in C['dv']:
            continue
        g = C['grid'][name]
        rgb = np.asarray(C['dv'][name]['rgb'], float)
        az = AZ_NOMINAL.get(name, info.get('az3', 35.0))
        out['views'][name] = dict(rgb=rgb / 255 if rgb.max() > 1.5 else rgb, raw=C['dv'][name]['raw'],
                                  hair=C['hair'][name], az=float(az), col_axis=float(g['axis'] - g['x0y0'][0]),
                                  row_eye=float(g['eye_y'] - g['x0y0'][1]), ppl=float(g['ppl']))
    return out


# ------------------------------------------------------------------------------------------------------------ helpers

def _disk(r):
    from skimage.morphology import disk
    return disk(max(1, int(round(r))))


def _odd(n):
    n = int(round(n))
    return n + 1 - n % 2


def _nbrs(sk):
    from scipy import ndimage
    k = np.ones((3, 3), int); k[1, 1] = 0
    return ndimage.convolve(sk.astype(int), k, mode='constant') * sk


OFF8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def _branch(sk, nb, r, c, maxlen=10 ** 6):
    """the skeleton walked from an end (r, c) to its first junction or other end -> [(r, c)] (the end first)."""
    path = [(r, c)]
    prev = None
    cur = (r, c)
    H, W = sk.shape
    while len(path) < maxlen:
        nxt = None
        for dr, dc in OFF8:
            q = (cur[0] + dr, cur[1] + dc)
            if 0 <= q[0] < H and 0 <= q[1] < W and sk[q] and q != prev and q not in path[-3:]:
                nxt = q
                break
        if nxt is None:
            break
        if nb[nxt] >= 3:
            path.append(nxt)
            break
        prev, cur = cur, nxt
        path.append(cur)
    return path


# ------------------------------------------------------------------------------------------------------------ per view

class Split:
    """one view's split. Arrays are on a crop of the design grid round the hair (self.box: r0, r1, c0, c1)."""

    def __init__(self, view, V, ppl, params=None):
        self.view, self.V, self.ppl = view, V, ppl
        self.P = dict(P, **(params or {}))
        hair = V['hair']
        ys, xs = np.nonzero(hair)
        m = int(0.1 * ppl)
        r0, r1 = max(0, ys.min() - m), min(hair.shape[0], ys.max() + m + 1)
        c0, c1 = max(0, xs.min() - m), min(hair.shape[1], xs.max() + m + 1)
        self.box = (int(r0), int(r1), int(c0), int(c1))
        self.full_shape = hair.shape
        cr = lambda a: a[r0:r1, c0:c1]
        self.rgb, self.raw, self.hair0 = cr(V['rgb']), cr(V['raw']), cr(hair)
        self.pieces = {k: cr(m) for k, m in (V.get('pieces') or {}).items()}
        self.occ = cr(V['occ']) if V.get('occ') is not None else np.zeros(self.hair0.shape, bool)
        self.col_axis, self.row_eye = V['col_axis'] - c0, V['row_eye'] - r0
        self.az = V['az']
        self.report = {}

    # ---- the sheet's own scales and the ink

    def measure_ink(self):
        from scipy import ndimage
        from skimage import morphology
        from .bodyqa import CLASS
        P = self.P
        val = self.rgb.max(-1)
        line = self.raw == CLASS['line']
        near = ndimage.binary_dilation(self.hair0, iterations=3)
        edge = line & near & ~ndimage.binary_erosion(self.hair0, iterations=2)
        sk = morphology.skeletonize(line & near)
        dt = ndimage.distance_transform_edt(line)
        lw = float(max(1.0, 2 * np.median(dt[sk]))) if sk.any() else 2.0
        v_fill = float(np.median(val[self.hair0 & ~line]))
        v_ink = float(np.percentile(val[edge], 25)) if edge.any() else 0.1
        contrast = max(0.05, v_fill - v_ink)
        size = _odd(P['ink_size_lw'] * lw + 3)
        th = ndimage.grey_closing(val, size=(size, size)) - val
        ink = ((th > P['ink_share'] * contrast) | line) & near
        # the hair region: the hair and the ink that bounds it
        H = self.hair0 | (ink & ndimage.binary_dilation(self.hair0, iterations=2))
        H = ndimage.binary_closing(H, iterations=1) | H
        # the hair pieces (buns) are pieces of their own, not cut into locks: out of the lock region, outline and all
        self.piece_mask = np.zeros(H.shape, bool)
        for m in (self.pieces.values() if self.P['pieces'] else ()):
            self.piece_mask |= ndimage.binary_dilation(m, iterations=int(round(lw)) + 1) & H
        self.H_all = H.copy()
        H = H & ~self.piece_mask
        lab, n = ndimage.label(H)
        if n > 1:
            area = np.bincount(lab.ravel()); area[0] = 0
            H = np.isin(lab, np.nonzero(area >= 0.002 * self.ppl ** 2)[0])
        self.lw, self.contrast, self.H, self.ink = lw, contrast, H, ink & H
        self.tophat = th
        # the cel tones: the hair's fill split in two by Otsu on its value (the lit and the shadow tone), specks
        # under a line width opened away; their edges (off the ink) are the shading's shapes, which follow the locks
        from skimage import filters
        inner = H & ~self.ink
        self.tone_edges = np.zeros(H.shape, bool)
        self.dark = np.zeros(H.shape, bool)
        if inner.sum() > 100:
            dark = (val < filters.threshold_otsu(val[inner])) & inner
            r = max(1, int(round(lw / 2)))
            dark = ndimage.binary_opening(dark, structure=_disk(r))
            light = ndimage.binary_opening(inner & ~dark, structure=_disk(r))
            e = (ndimage.binary_dilation(dark, iterations=1) & light) | (ndimage.binary_dilation(light, iterations=1) & dark)
            self.dark = dark
            self.tone_edges = e & ~self.ink
        self.report.update(dark_share=round(float(self.dark.sum() / max(1, inner.sum())), 3))
        self.report.update(line_width_px=round(lw, 2), fill_value=round(v_fill, 3), ink_value=round(v_ink, 3),
                           contrast=round(contrast, 3), hair_px=int(H.sum()), ink_px=int(self.ink.sum()))

    # ---- strokes: the ink's skeleton, its free ends and tangents

    def strokes(self):
        from scipy import ndimage
        from skimage import morphology
        P, lw = self.P, self.lw
        sk = morphology.skeletonize(self.ink)
        # prune spurs: branches from an end to a junction shorter than prune_lw line widths
        for _ in range(2):
            nb = _nbrs(sk)
            ends = np.argwhere((nb == 1))
            for r, c in ends:
                br = _branch(sk, nb, r, c, maxlen=int(P['prune_lw'] * lw) + 2)
                if len(br) <= P['prune_lw'] * lw and nb[br[-1]] >= 3:
                    for q in br[:-1]:
                        sk[q] = False
            sk = morphology.skeletonize(sk)
        nb = _nbrs(sk)
        self.sk = sk
        outside = ~self.H
        dout = ndimage.distance_transform_edt(~outside)
        self.dout = dout
        ends = []
        for r, c in np.argwhere(nb == 1):
            if dout[r, c] <= lw + 1.5:          # on the silhouette: a stroke ending at the outline (a notch line)
                continue
            br = _branch(sk, nb, r, c)
            n = len(br)
            k = min(n - 1, int(P['tangent_lw'] * lw) + 1)
            if k < 2:
                continue
            a = np.array(br[0], float); b = np.array(br[k], float)
            t = a - b
            t /= max(1e-6, np.hypot(*t))
            ends.append(dict(rc=(int(r), int(c)), t=t, branch=br, length=n, junction=bool(nb[br[-1]] >= 3)))
        self.ends = ends
        # the stroke tangent field: a structure tensor on the skeleton (orientation along it), interior strokes only
        self.report.update(stroke_ends=len(ends))

    # ---- the flow field

    def flow(self, tips=None):
        """the orientation field from the interior strokes' tangents (and, given tips, each tip's protrusion: its
        outward direction along its last tip-scale of length, the lock's own axis where the drawing has no stroke)."""
        from scipy import ndimage
        P, ppl = self.P, self.ppl
        sk = self.sk & (self.dout > self.lw + 1.5)
        # tangent per skeleton pixel: the structure tensor of the skeleton mask (gradients across the stroke)
        f = ndimage.gaussian_filter(sk.astype(float), 1.0)
        gy, gx = np.gradient(f)
        s = P['tangent_lw'] * self.lw / 2
        Jxx = ndimage.gaussian_filter(gx * gx, s); Jyy = ndimage.gaussian_filter(gy * gy, s)
        Jxy = ndimage.gaussian_filter(gx * gy, s)
        # the gradient's doubled angle is (Jxx - Jyy, 2 Jxy); the stroke runs at 90 deg to it: negate in doubled angles
        cx, cy = -(Jxx - Jyy), -2 * Jxy
        mag = np.hypot(cx, cy) + 1e-12
        D = np.stack([np.where(sk, cx / mag, 0), np.where(sk, cy / mag, 0)])       # unit doubled-angle at strokes
        if tips:
            sk = sk.copy()
            for t in tips:
                o = np.array(t['out'])
                a2 = 2 * math.atan2(o[0], o[1])
                L_ = max(3, int(round(t['scale'] * ppl)))
                for k in range(1, L_ + 1):
                    r, c = int(round(t['rc'][0] - k * o[0])), int(round(t['rc'][1] - k * o[1]))
                    if 0 <= r < sk.shape[0] and 0 <= c < sk.shape[1] and self.H[r, c]:
                        D[0, r, c], D[1, r, c] = math.cos(a2), math.sin(a2)
                        sk[r, c] = True
        # the crown: on the head's axis, a little below the hair's top there (thin parts, the ahoge, opened away)
        Ho = ndimage.binary_opening(self.H, structure=_disk(0.03 * ppl))
        ca = int(round(np.clip(self.col_axis, 0, self.H.shape[1] - 1)))
        band = Ho[:, max(0, ca - 3):ca + 4].any(1)
        top = int(np.argmax(band)) if band.any() else int(np.nonzero(self.H.any(1))[0][0])
        crown = (top + P['crown_drop'] * (self.row_eye - top), float(self.col_axis))
        self.crown = crown
        rr, cc = np.mgrid[0:self.H.shape[0], 0:self.H.shape[1]]
        dy, dx = rr - crown[0], cc - crown[1]
        th = np.arctan2(dy, dx)
        prior = np.stack([np.cos(2 * th), np.sin(2 * th)])
        F = np.zeros_like(D)
        for s_ in (P['flow_s1'], P['flow_s2']):
            g = np.stack([ndimage.gaussian_filter(D[i], s_ * ppl) for i in range(2)])
            n = ndimage.gaussian_filter(sk.astype(float), s_ * ppl)
            F += g / max(1e-9, n.max())
        pk = 1.0
        F += P['flow_prior'] * pk * prior
        ang = 0.5 * np.arctan2(F[1], F[0])
        u = np.stack([np.sin(ang), np.cos(ang)])           # (row, col) unit, sign free
        # downstream: away from the crown
        sgn = np.sign(u[0] * dy + u[1] * dx)
        sgn[sgn == 0] = 1
        self.down = u * sgn                                 # (2, H, W): downstream unit (row, col)
        self.coh = np.hypot(F[0], F[1])
        self.report.update(crown_rc=[round(crown[0], 1), round(crown[1], 1)])

    def f_at(self, p, d=None):
        """the flow's unit direction at p (row, col; bilinear-free: nearest), signed to agree with d (else downstream)."""
        r = int(round(min(max(p[0], 0), self.H.shape[0] - 1))); c = int(round(min(max(p[1], 0), self.H.shape[1] - 1)))
        f = self.down[:, r, c]
        if d is not None and f[0] * d[0] + f[1] * d[1] < 0:
            f = -f
        return f

    # ---- closing: extensions, then trapped balls

    def trace(self, start, d0, walls, own=None, cap_px=None, skip_px=0.0, momentum=None):
        """a streamline from start along the flow (agreeing with d0) -> (points [(r, c)], how: 'ink' | 'outline' |
        'cap')."""
        P = self.P
        m = P['ext_momentum'] if momentum is None else momentum
        cap_px = cap_px or P['ext_cap'] * self.ppl
        step = P['axis_step']
        p = np.array(start, float); d = np.array(d0, float)
        pts = [tuple(p)]
        Hh, Ww = self.H.shape
        n = int(cap_px / step)
        for i in range(n):
            f = self.f_at(p, d)
            d = m * d + (1 - m) * f
            d /= max(1e-9, np.hypot(*d))
            p = p + step * d
            r, c = int(round(p[0])), int(round(p[1]))
            if not (0 <= r < Hh and 0 <= c < Ww) or not self.H[r, c]:
                return pts, 'outline'
            pts.append((p[0], p[1]))
            if (i + 1) * step > skip_px and walls[r, c] and (own is None or not own[r, c]):
                return pts, 'ink'
        return pts, 'cap'

    def close(self):
        from scipy import ndimage
        from skimage import draw
        P, lw = self.P, self.lw
        ext = np.zeros(self.H.shape, bool)
        self.extensions = []
        hits = dict(ink=0, outline=0, cap=0, short=0, downstream=0)
        # the longer strokes first; an extension stops at ink or at an extension already drawn
        for e in sorted(self.ends, key=lambda e: -e['length']):
            if e['length'] < P['ext_min_lw'] * lw:
                hits['short'] += 1
                continue
            f = self.f_at(e['rc'])
            e['downstream'] = bool(e['t'][0] * f[0] + e['t'][1] * f[1] > 0)
            if e['downstream'] and not P['ext_down']:
                # a lock line is drawn up from its tip or notch and fades toward the root: an end that stops short
                # going downstream is a strand line's or a split tip's (Michael's truth, rule 1), left open
                hits['downstream'] += 1
                continue
            own = np.zeros(self.H.shape, bool)
            for q in e['branch']:
                own[q] = True
            own = ndimage.binary_dilation(own, iterations=int(lw) + 1)
            pts, how = self.trace(e['rc'], e['t'], self.ink | ext, own=own, skip_px=P['ext_skip_lw'] * lw)
            hits[how] += 1
            e['ext'] = how
            if how == 'cap' and not P['ext_keep_cap']:
                continue
            a = np.array(pts)
            for (r0, c0), (r1, c1) in zip(a[:-1], a[1:]):
                rr, cc = draw.line(int(round(r0)), int(round(c0)), int(round(r1)), int(round(c1)))
                ext[rr, cc] = True
            self.extensions.append(dict(start=e['rc'], how=how, pts=a[::4].round(1).tolist(), length=len(pts) * P['axis_step']))
        # the notches: a lock line runs up from each notch of the outline between two tips (the animator's move where
        # the drawing draws only the notch): traced upstream along the flow until ink, an extension or the outline
        if P['notch_lines']:
            hits['notch'] = 0
            outer = _outer_contour_id(self)
            for t in self.notch_list:
                o = np.array(t['out'])                     # from the chord to the notch: into the hair at a notch
                if P['notch_lines'] == 'hem' and not (t['contour'] == outer and o[0] < -0.5):
                    continue                               # only the hem's notches (the outer outline's, opening down)
                f = self.f_at(t['rc'])
                up = -f
                start = (t['rc'][0] + 1.5 * up[0], t['rc'][1] + 1.5 * up[1])
                pts, how = self.trace(start, up, self.ink | ext, skip_px=P['ext_skip_lw'] * lw)
                if how == 'cap' and not P['ext_keep_cap']:
                    continue
                a = np.array([t['rc']] + pts)
                for (r0, c0), (r1, c1) in zip(a[:-1], a[1:]):
                    rr, cc = draw.line(int(round(r0)), int(round(c0)), int(round(r1)), int(round(c1)))
                    ext[rr, cc] = True
                hits['notch'] += 1
                self.extensions.append(dict(start=[round(t['rc'][0], 1), round(t['rc'][1], 1)], how='notch:' + how,
                                            pts=a[::4].round(1).tolist(), length=len(pts) * P['axis_step']))
        self.ext = ext & self.H
        self.bases = self.protrusions() if P['protrusion_r'] else np.zeros(self.H.shape, bool)
        walls = self.ink | self.ext | self.bases
        if P['tones']:
            walls = walls | self.tone_edges
        free = self.H & ~walls
        # trapped balls: from the largest radius down, the components a ball of that radius can roam become cells
        R = max(1, int(round(P['ball_lw'] * lw)))
        cells = np.zeros(self.H.shape, np.int32)
        k = 0
        amin = P['cell_min'] * self.ppl ** 2
        for r in range(R, 0, -1):
            room = free & (cells == 0)
            o = ndimage.binary_opening(room, structure=_disk(r))
            lab, n = ndimage.label(o)
            if not n:
                continue
            area = np.bincount(lab.ravel())
            for j in range(1, n + 1):
                if area[j] >= max(amin / 4, math.pi * r * r * 2):
                    k += 1
                    cells[lab == j] = k
        # the rest of the free space grows from the cells (geodesically, through the free space), then the walls
        cells = self._grow(cells, free)
        cells = self._grow(cells, self.H)
        cells = self._merge_small(cells, amin)
        self.walls, self.cells = walls, cells
        self.report.update(extensions=hits, cells=int(len(np.unique(cells[cells > 0]))), ball_px=R)

    def protrusions(self):
        """the hair's protrusions (an ahoge, a strand, a flick): what an opening of the hair by a disk of protrusion_r
        L removes, kept where it is elongated (at least as long as its base is wide) and lock-sized; each is cut at its
        base, where it leaves the opened mass (the truth's rules 9-11: the ahoge cut across its base, a strand or flick
        across its base notch to notch). -> the base lines (bool image)."""
        from scipy import ndimage
        P, ppl = self.P, self.ppl
        rad = max(1, int(round(P['protrusion_r'] * ppl)))
        body = ndimage.binary_opening(self.H, structure=_disk(rad))
        pro = self.H & ~body
        lab, n = ndimage.label(pro)
        bases = np.zeros(self.H.shape, bool)
        ring = ndimage.binary_dilation(body, iterations=1) & ~body
        kept = 0
        for j, sl in enumerate(ndimage.find_objects(lab), 1):
            m = lab == j
            area = int(m.sum())
            if area < P['cell_min'] * ppl ** 2:
                continue
            base = ndimage.binary_dilation(m, iterations=1) & ring & self.H
            if not base.any():
                continue                                   # a separate piece: its own region already
            br, bc = np.nonzero(base)
            width = math.hypot(br.max() - br.min(), bc.max() - bc.min()) + 1
            # length: the furthest pixel of the protrusion from its base
            d = ndimage.distance_transform_edt(~base)
            length = float(d[m].max())
            if length < P['protrusion_len'] * width:
                continue
            bases |= ndimage.binary_dilation(base, iterations=1) & self.H
            kept += 1
        self.report.update(protrusions=kept)
        return bases

    def _grow(self, lab, mask, it=None):
        from scipy import ndimage
        out = lab.copy()
        for _ in range(it or 200):
            todo = mask & (out == 0)
            if not todo.any():
                break
            g = ndimage.grey_dilation(out, size=(3, 3))
            add = todo & (g > 0)
            if not add.any():
                break
            out[add] = g[add]
        return out

    def _merge_small(self, cells, amin):
        """cells smaller than amin join the neighbour they share the most edge with."""
        from scipy import ndimage
        for _ in range(3):
            ids, cnt = np.unique(cells[cells > 0], return_counts=True)
            small = ids[cnt < amin]
            if not len(small):
                break
            for i in small:
                m = cells == i
                ring = ndimage.binary_dilation(m, iterations=2) & ~m & (cells > 0)
                if not ring.any():
                    continue
                nb, nc = np.unique(cells[ring], return_counts=True)
                cells[m] = nb[np.argmax(nc)]
        # renumber
        ids = np.unique(cells[cells > 0])
        lut = np.zeros(cells.max() + 1, np.int32); lut[ids] = np.arange(1, len(ids) + 1)
        return lut[cells]

    # ---- tips and notches on the outline

    def tips(self):
        """the outline's tips and notches. Along each outline (the outer edge and the holes), the distance from the crown
        is a potential: its local maxima with a prominence (tip_prom, L) are tips (a lock ends there: the hem's flicks,
        the bangs' points over the face), its local minima notches; a convex corner sharper than tip_acute is a tip
        whatever its direction (a flick curled up)."""
        from scipy import ndimage
        from scipy.signal import find_peaks
        from skimage import measure
        P, ppl = self.P, self.ppl
        conts = measure.find_contours(np.pad(self.H, 1).astype(float), 0.5)
        found = []
        sep = max(2, int(P['tip_sep'] * ppl))
        prom = P['tip_prom'] * ppl
        for ci, C in enumerate(conts):
            C = C - 1
            seg = np.hypot(*np.diff(C, axis=0).T)
            s = np.concatenate([[0], np.cumsum(seg)])
            if s[-1] < 0.05 * ppl:
                continue
            closed = np.allclose(C[0], C[-1])
            ss = np.arange(0, s[-1], 1.0)
            Q = np.stack([np.interp(ss, s, C[:, 0]), np.interp(ss, s, C[:, 1])], 1)
            n = len(Q)
            # sharpness and the outward direction at the best of the tip scales
            best = np.zeros(n); conv = np.zeros(n, bool); outd = np.zeros((n, 2)); scl = np.zeros(n)
            for sc in P['tip_scales']:
                k = max(2, int(round(sc * ppl)))
                if n < 2 * k + 3:
                    continue
                ii = np.arange(n)
                a, b = (Q[(ii - k) % n], Q[(ii + k) % n]) if closed else \
                    (Q[np.clip(ii - k, 0, n - 1)], Q[np.clip(ii + k, 0, n - 1)])
                va, vb = a - Q, b - Q
                cosang = (va * vb).sum(1) / (np.hypot(*va.T) * np.hypot(*vb.T) + 1e-9)
                sharp = 180.0 - np.degrees(np.arccos(np.clip(cosang, -1, 1)))
                mid = 0.5 * (a + b)
                mr = np.clip(np.round(mid[:, 0]).astype(int), 0, self.H.shape[0] - 1)
                mc = np.clip(np.round(mid[:, 1]).astype(int), 0, self.H.shape[1] - 1)
                o = Q - mid
                o /= (np.hypot(*o.T)[:, None] + 1e-9)
                better = sharp > best
                best[better] = sharp[better]; conv[better] = self.H[mr, mc][better]
                outd[better] = o[better]; scl[better] = sc
            dc = np.hypot(Q[:, 0] - self.crown[0], Q[:, 1] - self.crown[1])
            sm = max(1, int(0.006 * ppl))
            kern = np.ones(2 * sm + 1) / (2 * sm + 1)
            dcs = np.convolve(np.concatenate([dc[-sm:], dc, dc[:sm]]) if closed else np.pad(dc, sm, mode='edge'),
                              kern, 'valid')
            ext = np.concatenate([dcs, dcs]) if closed else dcs        # (a closed outline wraps)
            pk, _ = find_peaks(ext, prominence=prom, distance=sep)
            nk, _ = find_peaks(-ext, prominence=prom, distance=sep)
            pk = np.unique(pk % n); nk = np.unique(nk % n)
            acute = np.nonzero(conv & (best >= 180.0 - P['tip_acute']))[0]
            # the acute corners' local maxima of sharpness, one per tip_sep
            ac = []
            for i in acute[np.argsort(-best[acute])]:
                if all(min(abs(i - j), n - abs(i - j)) >= sep for j in ac):
                    ac.append(int(i))
            cand = [(int(i), 'radial') for i in pk] + [(i, 'acute') for i in ac]
            taken = []
            for i, why in sorted(cand, key=lambda q: (q[1] != 'acute', -best[q[0]])):
                if any(min(abs(i - j), n - abs(i - j)) < sep for j in taken):
                    continue
                taken.append(i)
                found.append(dict(rc=(float(Q[i, 0]), float(Q[i, 1])), sharp=float(best[i]), kind=1, why=why,
                                  out=outd[i].tolist(), scale=float(scl[i]) or P['tip_scales'][0], contour=ci, s=int(i)))
            for i in nk:
                found.append(dict(rc=(float(Q[i, 0]), float(Q[i, 1])), sharp=float(best[i]), kind=-1, why='radial',
                                  out=outd[i].tolist(), scale=float(scl[i]), contour=ci, s=int(i)))
        # one tip per place: across outlines too (a hole's edge next to the outer edge), the sharper kept
        sepL = sep
        keep = []
        for t in sorted(found, key=lambda t: (t['kind'] < 0, -t['sharp'])):
            if any(q['kind'] == t['kind'] and math.hypot(q['rc'][0] - t['rc'][0], q['rc'][1] - t['rc'][1]) < sepL
                   for q in keep):
                continue
            keep.append(t)
        found = keep
        tips, notches = [], []
        for t in found:
            if t['kind'] < 0:
                notches.append(t)
                continue
            f = self.f_at(t['rc'])
            o = np.array(t['out'])
            # a tip's outward direction: the protrusion's (from the chord to the tip), unless the corner is blunt, then
            # the outline's normal (the crown's direction)
            if t['sharp'] < 20:
                v = np.array(t['rc']) - np.array(self.crown)
                o = v / max(1e-9, np.hypot(*v))
                t['out'] = o.tolist()
            t['down'] = float(o[0] * f[0] + o[1] * f[1])
            # beyond the tip: an occluder (a clip) or a hair piece (a bun) means the outline there is the edge of
            # something over the hair, not a lock's end
            k = self.lw + 3
            r_, c_ = int(round(t['rc'][0] + k * o[0])), int(round(t['rc'][1] + k * o[1]))
            if 0 <= r_ < self.H.shape[0] and 0 <= c_ < self.H.shape[1]:
                win = (slice(max(0, r_ - 1), r_ + 2), slice(max(0, c_ - 1), c_ + 2))
                if self.P['occ_tips'] and (self.occ[win].any() or self.piece_mask[win].any() or
                                           (self.P['occ_tips'] == 'pieces' and
                                            any(m[win].any() for m in self.pieces.values()))):
                    continue
            tips.append(t)
        self.tip_list, self.notch_list = tips, notches
        self.report.update(tips=len(tips), notches=len(notches),
                           tips_acute=sum(1 for t in tips if t['why'] == 'acute'))

    def axes(self):
        """each tip's axis: a streamline traced upstream from the tip until it leaves the hair (axis_max)."""
        P = self.P
        nowall = np.zeros(self.H.shape, bool)
        for t in self.tip_list:
            r, c = t['rc']
            # step inside first
            o = np.array(t['out'])
            start = (r - o[0] * 1.5, c - o[1] * 1.5)
            pts, how = self.trace(start, -o, nowall, cap_px=P['axis_max'] * self.ppl, momentum=0.7)
            t['axis'] = np.array(pts)
            t['axis_end'] = how

    # ---- cells into locks

    def _graph(self, mask):
        """the anisotropic 8-neighbour graph over mask's pixels -> (csr matrix, index image)."""
        from scipy import sparse
        P = self.P
        idx = -np.ones(mask.shape, np.int64)
        rr, cc = np.nonzero(mask)
        idx[rr, cc] = np.arange(len(rr))
        rows, cols, w = [], [], []
        walls = self.walls
        for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
            r2, c2 = rr + dr, cc + dc
            ok = (r2 >= 0) & (r2 < mask.shape[0]) & (c2 >= 0) & (c2 < mask.shape[1])
            ok[ok] = mask[r2[ok], c2[ok]]
            a, b = idx[rr[ok], cc[ok]], idx[r2[ok], c2[ok]]
            L = math.hypot(dr, dc)
            f = self.down[:, rr[ok], cc[ok]]
            cos = np.abs(f[0] * dr + f[1] * dc) / L
            sin2 = np.clip(1 - cos ** 2, 0, 1)
            wt = L * np.sqrt(cos ** 2 + P['aniso'] ** 2 * sin2)
            wt = wt + P['wall_cost'] * (walls[r2[ok], c2[ok]] | walls[rr[ok], cc[ok]]) * L
            rows.append(a); cols.append(b); w.append(wt)
        rows, cols, w = np.concatenate(rows), np.concatenate(cols), np.concatenate(w)
        G = sparse.coo_matrix((np.concatenate([w, w]), (np.concatenate([rows, cols]), np.concatenate([cols, rows]))),
                              shape=(len(rr), len(rr))).tocsr()
        return G, idx

    def _voronoi(self, mask, seeds):
        """the anisotropic geodesic Voronoi of seeds {label: bool image} within mask -> label image (0 unreached)."""
        from scipy.sparse import csgraph
        G, idx = self._graph(mask)
        src, lab = [], []
        for l, m in seeds.items():
            s = idx[m & mask]
            s = s[s >= 0]
            src.extend(s.tolist()); lab.extend([l] * len(s))
        out = np.zeros(mask.shape, np.int32)
        if not src:
            return out
        src = np.array(src); lab = np.array(lab)
        d, _, owner = csgraph.dijkstra(G, directed=False, indices=src, min_only=True, return_predecessors=True)
        rr, cc = np.nonzero(mask)
        ok = np.isfinite(d)
        lut = dict(zip(src.tolist(), lab.tolist()))
        own = np.array([lut.get(int(o), 0) for o in owner[ok]])
        out[rr[ok], cc[ok]] = own
        return out

    def seeds(self):
        """each tip's seed: its own end. seed_mode 'disk': the hair off the walls within seed_r L of the tip, the part
        of it nearest the tip (a flick's end, a strand's: whatever way it points); 'axis': its axis from the tip
        upstream, up to half the way to the nearest other tip (at most seed_len L), stopping at a wall."""
        from scipy import ndimage
        P = self.P
        T = np.array([t['rc'] for t in self.tip_list]) if self.tip_list else np.zeros((0, 2))
        free = self.H & ~self.walls
        out = {}
        for ti, t in enumerate(self.tip_list):
            m = np.zeros(self.H.shape, bool)
            r0, c0 = t['rc']
            if P['seed_mode'] == 'disk':
                d = np.hypot(*(T - T[ti]).T)
                d[ti] = np.inf
                for rad in (P['seed_r'], 2 * P['seed_r']):
                    R = min(rad * self.ppl, 0.5 * d.min() if len(d) > 1 else np.inf)
                    R = max(R, 2 * self.lw)
                    a, b = int(max(0, r0 - R - 1)), int(min(self.H.shape[0], r0 + R + 2))
                    c, e = int(max(0, c0 - R - 1)), int(min(self.H.shape[1], c0 + R + 2))
                    rr, cc = np.mgrid[a:b, c:e]
                    win = free[a:b, c:e] & (np.hypot(rr - r0, cc - c0) <= R)
                    lab, n = ndimage.label(win)
                    if n:
                        dd = [np.hypot(rr[lab == j] - r0, cc[lab == j] - c0).min() for j in range(1, n + 1)]
                        m[a:b, c:e] = lab == (int(np.argmin(dd)) + 1)
                        break
            else:
                d = np.hypot(*(T - T[ti]).T)
                d[ti] = np.inf
                lim = min(0.5 * d.min() if len(d) > 1 else np.inf, P['seed_len'] * self.ppl)
                a = t['axis']
                seg = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(a, axis=0).T))]) if len(a) > 1 else np.zeros(1)
                started = False
                for (r, c), L_ in zip(a, seg):
                    r, c = int(round(r)), int(round(c))
                    if not (0 <= r < m.shape[0] and 0 <= c < m.shape[1]) or not self.H[r, c]:
                        continue
                    if L_ > lim and started:
                        break
                    if self.walls[r, c]:
                        if started:
                            break                          # the next wall: the seed stops
                        continue                           # the outline's ink at the tip: step over it
                    started = True
                    m[r, c] = True
            if not m.any():
                r, c = int(round(r0)), int(round(c0))
                m[min(max(r, 0), m.shape[0] - 1), min(max(c, 0), m.shape[1] - 1)] = True
            out[ti + 1] = m
        self.seed_masks = out
        return out

    def closures(self):
        """the trapped balls' closures (cell boundaries off the ink) judged by the flow: one running along the flow
        continues a lock line across a gap (a wall: the locks either side differ); one running across it is a neck (a
        flick's base, a lock narrowing): the lock goes on through it. -> self.lockwalls: ink, extensions and the closures
        along the flow."""
        from scipy import ndimage
        from skimage import measure
        P = self.P
        cells, walls = self.cells, self.walls
        free = self.H & ~walls
        b = np.zeros(cells.shape, bool)
        b[:, 1:] |= (cells[:, 1:] != cells[:, :-1]) & free[:, 1:] & free[:, :-1]
        b[1:, :] |= (cells[1:, :] != cells[:-1, :]) & free[1:, :] & free[:-1, :]
        b[:, :-1] |= np.roll(b, -1, 1)[:, :-1] & False
        lab, n = ndimage.label(b, structure=np.ones((3, 3)))
        along = np.zeros(cells.shape, bool)
        nal = ncr = 0
        for j, sl in enumerate(ndimage.find_objects(lab), 1):
            m = lab[sl] == j
            rr, cc = np.nonzero(m)
            rr = rr + sl[0].start; cc = cc + sl[1].start
            if len(rr) < 3:
                continue
            X = np.stack([rr, cc], 1).astype(float)
            X -= X.mean(0)
            w, v = np.linalg.eigh(X.T @ X)
            t = v[:, -1]                                   # the closure's direction (row, col)
            f = self.down[:, rr, cc].mean(1)
            f /= max(1e-9, np.hypot(*f))
            if abs(t @ f) >= P['closure_along']:
                along[rr, cc] = True
                nal += 1
            else:
                ncr += 1
        along = ndimage.binary_dilation(along, iterations=1) & free
        lw_ = walls
        if P['tones']:
            # the tone edges judged per pixel: an edge along the flow (a shadow between two locks) is a lock wall,
            # one across it (a lock's shaded underside) is not
            g = ndimage.gaussian_filter(self.dark.astype(float), max(1.0, self.lw))
            gy, gx = np.gradient(g)
            n = np.hypot(gy, gx) + 1e-9
            cosn = np.abs(gy * self.down[0] + gx * self.down[1]) / n
            te_along = self.tone_edges & (cosn <= math.sqrt(1 - P['closure_along'] ** 2))
            lw_ = (walls & ~self.tone_edges) | te_along
            self.report.update(tone_edge_px=int(self.tone_edges.sum()), tone_edge_along_px=int(te_along.sum()))
        if P['stroke_min']:
            # a short interior stroke (its ink apart from the outline shorter than stroke_min L) is texture, a strand
            # or a split tip's line, not a lock line (the truth's rule 1): it cuts the cells, not the locks
            from skimage import morphology
            band = ndimage.binary_dilation(~self.H, iterations=int(round(self.lw)) + 2)
            inner = self.ink & ~band
            lab, n = ndimage.label(inner, structure=np.ones((3, 3)))
            if n:
                sk = morphology.skeletonize(inner)
                length = np.bincount(lab[sk], minlength=n + 1)
                short = np.isin(lab, np.nonzero(length < P['stroke_min'] * self.ppl)[0]) & (lab > 0)
                lw_ = lw_ & ~short
                self.report.update(short_strokes=int(np.sum((length[1:] > 0) & (length[1:] < P['stroke_min'] * self.ppl))),
                                   long_strokes=int(np.sum(length[1:] >= P['stroke_min'] * self.ppl)))
        self.lockwalls = lw_ | along
        self.report.update(closures_along=nal, closures_across=ncr)

    def _merge_fragments(self, regions, amin):
        """regions smaller than amin (slivers between strokes, fragments a stroke's gaps leave) join the neighbour
        they share the most edge with across the walls, the smallest first -> relabelled regions (1..n)."""
        from scipy import ndimage
        R = regions.copy()
        for _ in range(4):
            ids, cnt = np.unique(R[R > 0], return_counts=True)
            small = ids[cnt < amin][np.argsort(cnt[cnt < amin])]
            if not len(small):
                break
            for i in small:
                m = R == i
                if not m.any():
                    continue
                ring = ndimage.binary_dilation(m, iterations=int(round(self.lw)) + 2) & ~m & (R > 0)
                if not ring.any():
                    continue
                nb, nc = np.unique(R[ring], return_counts=True)
                R[m] = nb[np.argmax(nc)]
        ids = np.unique(R[R > 0])
        lut = np.zeros(R.max() + 1, np.int32); lut[ids] = np.arange(1, len(ids) + 1)
        return lut[R]

    def _exits(self, m, labels):
        """a region's downstream exits: from each of its pixels a step of exit_lw line widths downstream, carried on
        through walls (up to three such steps) -> (n out of the hair, {label: n} into other regions)."""
        P = self.P
        Hh, Ww = m.shape
        rr, cc = np.nonzero(m)
        dr, dc = self.down[0, rr, cc], self.down[1, rr, cc]
        step = P['exit_lw'] * self.lw
        res = np.zeros(len(rr), np.int64) - 1            # -1 undecided, 0 out of the hair, k region k
        for k in (1, 2, 3):
            r2 = np.round(rr + k * step * dr).astype(int); c2 = np.round(cc + k * step * dc).astype(int)
            ok = (r2 >= 0) & (r2 < Hh) & (c2 >= 0) & (c2 < Ww)
            und = res == -1
            outside = und & (~ok | ~self.H[np.clip(r2, 0, Hh - 1), np.clip(c2, 0, Ww - 1)])
            res[outside] = 0
            und = res == -1
            lab = labels[np.clip(r2, 0, Hh - 1), np.clip(c2, 0, Ww - 1)]
            wall = self.walls[np.clip(r2, 0, Hh - 1), np.clip(c2, 0, Ww - 1)]
            inm = m[np.clip(r2, 0, Hh - 1), np.clip(c2, 0, Ww - 1)]
            hit = und & ok & ~wall & ~inm & (lab > 0)
            res[hit] = lab[hit]
        n_out = int((res == 0).sum())
        ids, cnt = np.unique(res[res > 0], return_counts=True)
        return n_out, dict(zip(ids.tolist(), cnt.tolist()))

    def assign(self):
        """stage 'tips': every hair pixel to the tip it reaches most cheaply under the anisotropic metric (along the
        flow cheap, across it dear, through a wall dearer) -> self.locks_tips. Stage 'locks': the hair cut into regions
        by the lock walls (ink, extensions, the closures along the flow); a region holding tips' seeds is split between
        them along the flow (walls impassable); a tipless region is walled off: a lock of its own when it flows out of
        the hair (a tip hidden by a clip or behind the face), else it joins whole the lock that reaches it along the
        flow (the cells along one flow line merge) -> self.locks."""
        from scipy import ndimage
        P = self.P
        seeds = self.seeds()
        V_all = self._grow(self._voronoi(self.H, seeds), self.H)
        self.locks_tips = V_all
        self.closures()
        free = self.H & ~self.lockwalls
        regions, nreg = ndimage.label(free)
        if P['frag_min']:
            regions = self._merge_fragments(regions, P['frag_min'] * self.ppl ** 2)
            nreg = int(regions.max())
        V_free = self._voronoi(free, seeds)
        owners = {}
        for ti, m in seeds.items():
            for c in np.unique(regions[m]):
                if c and P['region_tips']:
                    owners.setdefault(int(c), set()).add(ti)
        if P['region_tips'] == 'multi':
            # only a region holding several tips is theirs (split between them); one with a single tip is read as a
            # tipless one: its own lock where it flows out of the hair, else merged along the flow
            owners = {c: t for c, t in owners.items() if len(t) >= 2}
        out = np.zeros(regions.shape, np.int32)
        nxt = len(self.tip_list) + 1
        amin = P['lock_min'] * self.ppl ** 2
        n_split = n_one = n_own = n_merge = 0
        tipless = []
        for c in range(1, nreg + 1):
            m = regions == c
            tl = owners.get(c, set())
            if len(tl) == 1:
                out[m] = next(iter(tl)); n_one += 1
            elif len(tl) >= 2:
                v = np.where(np.isin(V_free[m], list(tl)), V_free[m], 0)
                sub = np.zeros(regions.shape, np.int32); sub[m] = v
                out[m] = self._grow(sub, m)[m]; n_split += 1
            else:
                tipless.append(c)
        # tipless regions: a lock of its own when it flows out of the hair; else it joins the lock it flows into (its
        # downstream exits, resolved downstream first; split between two when each takes split_share), or by
        # merge_by 'vall' the lock that reaches it most along the flow (the tips' Voronoi through the walls)
        ex = {}
        lock_of = {c: None for c in tipless}
        for c in tipless:
            m = regions == c
            n_out, into = self._exits(m, regions)
            ex[c] = (n_out, into, int(m.sum()))
            tot = n_out + sum(into.values())
            if m.sum() >= amin and (tot == 0 or n_out >= (1 - P['exit_hair']) * tot):
                out[m] = nxt; lock_of[c] = nxt; nxt += 1; n_own += 1
        if P['merge_by'] == 'exits':
            for _ in range(len(tipless) + 1):
                changed = False
                for c in tipless:
                    if lock_of[c] is not None:
                        continue
                    n_out, into, area = ex[c]
                    tot = sum(into.values())
                    if not tot:
                        continue
                    # the downstream regions' locks (decided ones; an undecided tipless one waits)
                    tl = {}
                    wait = False
                    for r_, n_ in into.items():
                        if n_ < P['split_share'] * tot * 0.5:
                            continue
                        if r_ in lock_of and lock_of[r_] is None:
                            wait = True
                            break
                        L_ = lock_of.get(r_) if r_ in lock_of else int(np.bincount(out[regions == r_]).argmax())
                        if L_:
                            tl[L_] = tl.get(L_, 0) + n_
                    if wait or not tl:
                        continue
                    m = regions == c
                    strong = [L_ for L_, n_ in tl.items() if n_ >= P['split_share'] * tot]
                    if len(strong) >= 2:
                        seeds_ = {}
                        for r_, n_ in into.items():
                            L_ = lock_of.get(r_) if r_ in lock_of else int(np.bincount(out[regions == r_]).argmax())
                            if L_ in strong:
                                nb = ndimage.binary_dilation(regions == r_, iterations=int(P['exit_lw'] * self.lw) + 2) & m
                                seeds_[L_] = seeds_.get(L_, np.zeros(m.shape, bool)) | nb
                        vor = self._grow(self._voronoi(m, seeds_), m)
                        out[m] = vor[m]
                        lock_of[c] = -1
                    else:
                        L_ = max(tl, key=tl.get)
                        out[m] = L_; lock_of[c] = L_
                    n_merge += 1
                    changed = True
                if not changed:
                    break
        rest = [c for c in tipless if lock_of[c] is None]
        if rest and P['merge_by'] == 'decided':
            # the regions not yet decided join the decided lock that reaches them most cheaply (the anisotropic metric,
            # walls dear): its neighbour along the flow line rather than across it
            dec = {}
            for L_ in np.unique(out[out > 0]):
                dec[int(L_)] = out == L_
            V_dec = self._voronoi(self.H, dec) if dec else np.zeros(out.shape, np.int32)
        for c in rest:
            m = regions == c
            v = V_dec[m] if P['merge_by'] == 'decided' else V_all[m]
            ids, cnt = np.unique(v[v > 0], return_counts=True)
            if len(ids):
                out[m] = ids[np.argmax(cnt)]; lock_of[c] = int(ids[np.argmax(cnt)]); n_merge += 1
            else:
                out[m] = nxt; lock_of[c] = nxt; nxt += 1; n_own += 1
        out = self._grow(out, self.H)
        self.regions = regions
        self.locks = out
        self.report.update(locks=int(len(np.unique(out[out > 0]))), regions=int(nreg), regions_split=n_split,
                           regions_one_tip=n_one, regions_own=n_own, regions_merged=n_merge)

    # ---- layering from T-junctions

    def layers(self, locks=None):
        """drawn T-junctions: at a skeleton junction where two branches run on (the bar) and the third ends there (the
        stem), the lock across the bar is in front of the locks either side of the stem. -> votes and ranks."""
        P, lw = self.P, self.lw
        locks = self.locks if locks is None else locks
        sk, nb = self.sk, _nbrs(self.sk)
        votes = {}
        Hh, Ww = sk.shape
        nT = 0
        from scipy import ndimage as _nd
        jl, nj = _nd.label(nb >= 3, structure=np.ones((3, 3)))
        L_ = int(2 * lw) + 2
        for j, sl in enumerate(_nd.find_objects(jl), 1):
            cl = jl == j
            rr_, cc_ = np.nonzero(cl[sl]); rr_ = rr_ + sl[0].start; cc_ = cc_ + sl[1].start
            r, c = float(rr_.mean()), float(cc_.mean())
            # the branches leaving the junction's cluster, each walked out L_ px
            starts = set()
            for a_, b_ in zip(rr_, cc_):
                for dr, dc in OFF8:
                    q = (a_ + dr, b_ + dc)
                    if 0 <= q[0] < Hh and 0 <= q[1] < Ww and sk[q] and not cl[q]:
                        starts.add(q)
            dirs = []
            used = set()
            for q in sorted(starts):
                if q in used:
                    continue
                br = _branch_from(sk, np.where(cl, 3, np.minimum(nb, 2)), (int(round(r)), int(round(c))), q, L_)
                used.update(br[:3])
                if len(br) < L_ * 0.8:
                    continue
                v = np.array(br[-1], float) - np.array([r, c], float)
                dirs.append(v / max(1e-9, np.hypot(*v)))
            if len(dirs) != 3:
                continue
            # the bar: the most opposite pair; the stem: the third
            best = None
            for a in range(3):
                for b in range(a + 1, 3):
                    cs = float(dirs[a] @ dirs[b])
                    if best is None or cs < best[0]:
                        best = (cs, a, b)
            cs, a, b = best
            if cs > -0.5:                                   # not a straight bar
                continue
            s = dirs[3 - a - b]
            n = np.array([-s[1], s[0]])
            k = 3 * lw
            pf = (r - k * s[0], c - k * s[1])
            pl = (r + k * s[0] + 1.5 * lw * n[0], c + k * s[1] + 1.5 * lw * n[1])
            pr = (r + k * s[0] - 1.5 * lw * n[0], c + k * s[1] - 1.5 * lw * n[1])
            get = lambda p: int(locks[int(round(min(max(p[0], 0), Hh - 1))), int(round(min(max(p[1], 0), Ww - 1)))]) \
                if self.H[int(round(min(max(p[0], 0), Hh - 1))), int(round(min(max(p[1], 0), Ww - 1)))] else 0
            F, Lb, Rb = get(pf), get(pl), get(pr)
            if not F:
                continue
            nT += 1
            for B in (Lb, Rb):
                if B and B != F:
                    votes[(F, B)] = votes.get((F, B), 0) + 1
        # near T-junctions: a drawn stroke whose end stops within near_t line widths of other ink (its extension met
        # ink at once): the stroke is the stem, the ink it meets the bar
        nN = 0
        for e in self.ends:
            if e.get('ext') != 'ink':
                continue
            ex = next((x for x in self.extensions if tuple(x['start']) == tuple(e['rc'])), None)
            if ex is None or ex['length'] > P['near_t'] * lw:
                continue
            t = np.array(e['t']); n = np.array([-t[1], t[0]])
            hit = np.array(ex['pts'][-1]) if ex['pts'] else np.array(e['rc'], float)
            pf = hit + 2.5 * lw * t
            pl = np.array(e['rc']) - 2 * lw * t + 1.5 * lw * n
            pr = np.array(e['rc']) - 2 * lw * t - 1.5 * lw * n
            get = lambda p: int(locks[int(round(min(max(p[0], 0), Hh - 1))), int(round(min(max(p[1], 0), Ww - 1)))]) \
                if self.H[int(round(min(max(p[0], 0), Hh - 1))), int(round(min(max(p[1], 0), Ww - 1)))] else 0
            F, Lb, Rb = get(pf), get(pl), get(pr)
            if not F:
                continue
            nN += 1
            for B in (Lb, Rb):
                if B and B != F:
                    votes[(F, B)] = votes.get((F, B), 0) + 1
        self.report.update(near_t=nN)
        ids = sorted(int(i) for i in np.unique(locks[locks > 0]))
        rank = _ranks(ids, votes)
        self.layer_votes, self.layer_rank = votes, rank
        self.report.update(t_junctions=nT, layer_votes=int(sum(votes.values())))

    # ---- per lock: axis, tip, root, width profile

    def describe(self, locks=None):
        P = self.P
        locks = self.locks if locks is None else locks
        ids = sorted(int(i) for i in np.unique(locks[locks > 0]))
        tip_of = {}
        if not hasattr(self, 'tip_ends'):
            keep_ = self.P['seed_mode']
            saved = getattr(self, 'seed_masks', None)
            self.P['seed_mode'] = 'disk'
            self.tip_ends = self.seeds()
            self.P['seed_mode'] = keep_
            if saved is not None:
                self.seed_masks = saved
        for ti, t in enumerate(self.tip_list):
            # the tip's lock: the one under its end (the free hair within seed_r of it: the outline's ink at the tip
            # may have grown into a neighbour)
            sm = self.tip_ends.get(ti + 1)
            v = locks[sm] if sm is not None and sm.any() else np.zeros(0, int)
            v = v[v > 0]
            if len(v):
                l_ = int(np.bincount(v).argmax())
            else:
                r, c = int(round(t['rc'][0])), int(round(t['rc'][1]))
                r = min(max(r, 0), locks.shape[0] - 1); c = min(max(c, 0), locks.shape[1] - 1)
                l_ = int(locks[r, c])
            if l_ and (l_ not in tip_of or t['sharp'] > self.tip_list[tip_of[l_]]['sharp']):
                tip_of[l_] = ti
        cells_in = {}
        for l_ in ids:
            cs = np.unique(self.cells[(locks == l_)])
            cells_in[l_] = [int(c) for c in cs if c]
        out = {}
        nowall = np.zeros(self.H.shape, bool)
        for l_ in ids:
            m = locks == l_
            rr, cc = np.nonzero(m)
            if l_ in tip_of:
                t = self.tip_list[tip_of[l_]]
                tip = t['rc']; tipk = 'drawn'
                tip_index = tip_of[l_]
                axis = t['axis']
            else:
                tip_index = None
                # no tip: its most downstream pixel (the furthest from the crown along the flow) and its axis from there
                d = np.hypot(rr - self.crown[0], cc - self.crown[1])
                j = int(np.argmax(d))
                tip = (float(rr[j]), float(cc[j])); tipk = 'hidden'
                axis, _ = self.trace(tip, -self.f_at(tip), nowall, cap_px=P['axis_max'] * self.ppl, momentum=0.5)
                axis = np.array(axis)
            # the axis within the lock: up to where it leaves it for good
            inl = np.array([m[int(round(min(max(p[0], 0), m.shape[0] - 1))), int(round(min(max(p[1], 0), m.shape[1] - 1)))]
                            for p in axis])
            last = int(np.nonzero(inl)[0][-1]) if inl.any() else 0
            ax = axis[:last + 1]
            root = ax[-1] if len(ax) else np.array(tip)
            # width profile: across the axis at 10 stations
            widths = []
            if len(ax) >= 4:
                seg = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(ax, axis=0).T))])
                for f in np.linspace(0.05, 0.95, 10):
                    j = int(np.searchsorted(seg, f * seg[-1]))
                    j = min(j, len(ax) - 2)
                    p = ax[j]; tng = ax[j + 1] - ax[j]
                    tng /= max(1e-9, np.hypot(*tng))
                    nrm = np.array([-tng[1], tng[0]])
                    w = 0
                    for sgn in (1, -1):
                        for k in range(1, int(0.5 * self.ppl)):
                            q = p + sgn * k * nrm
                            r, c = int(round(q[0])), int(round(q[1]))
                            if not (0 <= r < m.shape[0] and 0 <= c < m.shape[1]) or not m[r, c]:
                                break
                            w += 1
                    widths.append(round((w + 1) / self.ppl, 4))
            out[l_] = dict(id=l_, area_px=int(m.sum()), cells=cells_in[l_], tip_rc=[round(tip[0], 1), round(tip[1], 1)],
                           tip=tipk, tip_index=tip_index, root_rc=[round(float(root[0]), 1), round(float(root[1]), 1)],
                           axis_rc=ax[::max(1, len(ax) // 24)].round(1).tolist(), length_L=round(float(
                               np.hypot(*np.diff(ax, axis=0).T).sum() / self.ppl) if len(ax) > 1 else 0.0, 4),
                           width_L=widths, layer=round(float(self.layer_rank.get(l_, 0.0)), 3) if hasattr(
                               self, 'layer_rank') else None)
        self.lock_info = out
        return out

    # ---- to the full grid and to head coordinates

    def full(self, img):
        r0, r1, c0, c1 = self.box
        out = np.zeros(self.full_shape, img.dtype)
        out[r0:r1, c0:c1] = img
        return out

    def uz(self, rc):
        """crop (row, col) -> (u, z) in L (the view's own: u along its picture's x from the axis, z up from the eyes)."""
        return (rc[1] - self.col_axis) / self.ppl, (self.row_eye - rc[0]) / self.ppl

    def pipeline(self):
        """every step up to the locks: ink, strokes, flow (strokes only), tips, flow again (+ the tips' protrusions),
        the tips re-read on it, closing, axes, the tip split, the flow merge."""
        self.measure_ink()
        self.strokes()
        self.flow()
        self.tips()
        self.flow(self.tip_list)
        self.tips()
        self.close()
        self.axes()
        self.assign()

    def run(self, stage='locks'):
        self.pipeline()
        out = {'cells': self.cells, 'tips': self.locks_tips, 'locks': self.locks}[stage]
        self.locks = out
        self.layers(out)
        self.describe(out)
        return out


def _outer_contour_id(S):
    """the index (in tips()'s find_contours order) of the hair's longest outline: its outer edge."""
    from skimage import measure
    conts = measure.find_contours(np.pad(S.H, 1).astype(float), 0.5)
    return int(np.argmax([len(c) for c in conts])) if conts else -1


def _branch_from(sk, nb, j, q, maxlen):
    """the skeleton walked from junction j through its neighbour q, at most maxlen px -> [(r, c)]."""
    path = [q]
    prev, cur = j, q
    H, W = sk.shape
    while len(path) < maxlen:
        nxt = None
        for dr, dc in OFF8:
            p = (cur[0] + dr, cur[1] + dc)
            if 0 <= p[0] < H and 0 <= p[1] < W and sk[p] and p != prev and p != j and p not in path[-3:]:
                nxt = p
                break
        if nxt is None or nb[nxt] >= 3:
            break
        prev, cur = cur, nxt
        path.append(cur)
    return path


def _ranks(ids, votes, mu=0.05):
    """front-to-back ranks from pairwise votes {(front, back): n}: least squares on r_front - r_back = 1, a small pull
    to 0 -> {id: rank} (higher is nearer the viewer)."""
    if not ids:
        return {}
    k = {i: j for j, i in enumerate(ids)}
    n = len(ids)
    A = mu * np.eye(n)
    b = np.zeros(n)
    for (f, bk), w in votes.items():
        if f not in k or bk not in k:
            continue
        i, j = k[f], k[bk]
        A[i, i] += w; A[j, j] += w; A[i, j] -= w; A[j, i] -= w
        b[i] += w; b[j] -= w
    r = np.linalg.solve(A, b)
    return {i: float(r[k[i]]) for i in ids}


# ------------------------------------------------------------------------------------------------------------ head

class Shell:
    """the hair's elliptic shell per height, from the front's and profile's silhouettes (each view's camera:
    u = x cos az + y sin az): x0(z), a(z) from the front, y0(z), b(z) from the profile."""

    def __init__(self, splits):
        self.z = None
        ex = {}
        for name in ('front', 'profile', 'back', 'three_quarter'):
            if name not in splits:
                continue
            S = splits[name]
            from scipy import ndimage
            Ho = ndimage.binary_opening(S.H, structure=_disk(0.03 * S.ppl))
            rows = np.nonzero(Ho.any(1))[0]
            zs, lo, hi = [], [], []
            for r in rows:
                cs = np.nonzero(Ho[r])[0]
                u0, z = S.uz((r, cs[0])); u1, _ = S.uz((r, cs[-1]))
                zs.append(z); lo.append(u0); hi.append(u1)
            ex[name] = (np.array(zs), np.array(lo), np.array(hi))
        zf, lf, hf = ex['front']
        zp, lp, hp = ex['profile']
        z = np.arange(max(zf.min(), zp.min()), min(zf.max(), zp.max()), 0.01)
        it = lambda zz, zv, v: np.interp(zz, zv[::-1], v[::-1])
        self.z = z
        self.x0 = 0.5 * (it(z, zf, lf) + it(z, zf, hf)); self.a = 0.5 * (it(z, zf, hf) - it(z, zf, lf))
        self.y0 = 0.5 * (it(z, zp, lp) + it(z, zp, hp)); self.b = 0.5 * (it(z, zp, hp) - it(z, zp, lp))
        self.ex = ex
        # check: the back's and three-quarter's silhouettes predicted from the shell
        self.check = {}
        for name, az in (('back', 180.0), ('three_quarter', splits['three_quarter'].az if 'three_quarter' in splits else None)):
            if name not in ex or az is None:
                continue
            zb, lb, hb = ex[name]
            sel = (zb >= z.min()) & (zb <= z.max())
            pl, ph = [], []
            for zz in zb[sel]:
                u = self.u_of(np.linspace(-np.pi, np.pi, 361), zz, az)
                pl.append(u.min()); ph.append(u.max())
            self.check[name] = dict(lo_L=round(float(np.median(np.abs(np.array(pl) - lb[sel]))), 4),
                                    hi_L=round(float(np.median(np.abs(np.array(ph) - hb[sel]))), 4))

    def at(self, z):
        z = np.clip(z, self.z.min(), self.z.max())
        return (float(np.interp(z, self.z, self.x0)), float(np.interp(z, self.z, self.a)),
                float(np.interp(z, self.z, self.y0)), float(np.interp(z, self.z, self.b)))

    def u_of(self, t, z, az):
        x0, a, y0, b = self.at(z)
        x, y = x0 + a * np.sin(t), y0 - b * np.cos(t)
        r = math.radians(az)
        return x * math.cos(r) + y * math.sin(r)

    def phi(self, u, z, az):
        """a visible point (u, z) of view az -> its azimuth round the head (deg: 0 the front, 90 her left (+x), 180 the
        back), on the shell's visible side; beyond the shell's limb, the limb's."""
        t = np.linspace(-np.pi, np.pi, 1441)
        x0, a, y0, b = self.at(z)
        r = math.radians(az)
        vis = (np.sin(t) / max(a, 1e-3)) * math.sin(r) + (np.cos(t) / max(b, 1e-3)) * math.cos(r) > -1e-9
        uu = self.u_of(t, z, az)
        d = np.where(vis, np.abs(uu - u), np.inf)
        return float(np.degrees(t[int(np.argmin(d))]))


def _adiff(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0)


def _limb(shell, z, az, side):
    """the azimuth (deg) of the shell's limb at height z seen from az, on the picture's side (+1 right, -1 left)."""
    t = np.linspace(-np.pi, np.pi, 1441)
    x0, a, y0, b = shell.at(z)
    r = math.radians(az)
    vis = (np.sin(t) / max(a, 1e-3)) * math.sin(r) + (np.cos(t) / max(b, 1e-3)) * math.cos(r) > -1e-9
    uu = shell.u_of(t, z, az)
    uu = np.where(vis, uu, np.nan)
    j = int(np.nanargmax(uu)) if side > 0 else int(np.nanargmin(uu))
    return float(np.degrees(t[j]))


def head_coords(splits, shell):
    """each lock's tip and root in head-centred coordinates: (phi deg round the head's axis: 0 the front, 90 her left,
    180 the back; z L up from the eye line), from each view's camera onto the hair's elliptic shell. A tip's azimuth is
    an interval: its position +- match_du L across the picture; a tip on the silhouette (at or past the shell's limb)
    reaches limb_spread degrees past the limb, since a point on the outline can lie anywhere round it."""
    du, spread = P['match_du'], P['limb_spread']
    for name, S in splits.items():
        for l_, x in S.lock_info.items():
            ut, zt = S.uz(x['tip_rc']); ur, zr = S.uz(x['root_rc'])
            x['tip_uz'] = [round(ut, 4), round(zt, 4)]; x['root_uz'] = [round(ur, 4), round(zr, 4)]
            x['tip_phi'] = round(shell.phi(ut, zt, S.az), 1); x['root_phi'] = round(shell.phi(ur, zr, S.az), 1)
            lo, hi = sorted([shell.phi(ut - du, zt, S.az), shell.phi(ut + du, zt, S.az)])
            if hi - lo > 180:
                lo, hi = hi, lo + 360
            # on the silhouette: within du of the shell's limb (or past it)
            umin = float(np.nanmin(shell.u_of(np.linspace(-np.pi, np.pi, 721), zt, S.az)))
            umax = float(np.nanmax(shell.u_of(np.linspace(-np.pi, np.pi, 721), zt, S.az)))
            limb = 0
            if ut >= umax - du:
                limb = 1
            elif ut <= umin + du:
                limb = -1
            if limb:
                L_ = _limb(shell, zt, S.az, limb)
                # past the limb: away from the camera's side, round to the back of this view
                beyond = L_ + spread * (1 if ((L_ - S.az + 540) % 360 - 180) > 0 else -1)
                a_, b_ = sorted([L_, beyond])
                lo, hi = min(lo, a_), max(hi, b_)
            x['tip_phi_range'] = [round(lo, 1), round(hi, 1)]
            x['tip_limb'] = limb


def _gap(r1, r2):
    """the angular gap (deg) between two azimuth intervals (0 where they overlap), on the circle."""
    best = 360.0
    for k in (-360, 0, 360):
        a0, a1 = r1[0] + k, r1[1] + k
        g = max(0.0, max(a0, r2[0]) - min(a1, r2[1]))
        best = min(best, g)
    return best


def _visible(rng, az, margin=10.0):
    """does the azimuth interval reach the side view az sees (within margin degrees past its limbs)?"""
    return _gap(rng, [az - 90 - margin, az + 90 + margin]) == 0


def match(splits, shell, pairs=None, cost_max=None):
    """locks matched between views: per pair of views, the locks whose tips both can see, by assignment on the tips'
    distance round the head (L: the gap between their azimuth intervals as arc length at the shell's radius, and their
    heights); along the hem (tips on the outer outline's lower edge) the order round the head is kept (crossing pairs
    dropped, the dearer first). Cross-view ids by union over the links, one lock per view per id, cheapest first.
    -> ({(view, lock): xid}, [per pair of views: its links])."""
    from scipy.optimize import linear_sum_assignment
    cost_max = cost_max or P['match_cost']
    names = [n for n in VIEWS if n in splits]
    pairs = pairs or [(a, b) for i, a in enumerate(names) for b in names[i + 1:]]
    matches = []
    for va, vb in pairs:
        A, B = splits[va], splits[vb]
        la = [l for l, x in A.lock_info.items() if _visible(x['tip_phi_range'], B.az)]
        lb = [l for l, x in B.lock_info.items() if _visible(x['tip_phi_range'], A.az)]
        if not la or not lb:
            continue
        M = np.full((len(la), len(lb)), 10.0)
        for i, l1 in enumerate(la):
            x = A.lock_info[l1]
            for j, l2 in enumerate(lb):
                y = B.lock_info[l2]
                zt = 0.5 * (x['tip_uz'][1] + y['tip_uz'][1])
                _, a_, _, b_ = shell.at(zt)
                rad = 0.5 * (a_ + b_)
                dphi = math.radians(_gap(x['tip_phi_range'], y['tip_phi_range'])) * rad
                dz = x['tip_uz'][1] - y['tip_uz'][1]
                droot = math.radians(_adiff(x['root_phi'], y['root_phi'])) * rad
                M[i, j] = math.hypot(dphi, dz) + P['match_root'] * abs(droot)
        ra, cb = linear_sum_assignment(M)
        got = [(la[i], lb[j], float(M[i, j])) for i, j in zip(ra, cb) if M[i, j] <= cost_max]
        hem = [g for g in got if A.lock_info[g[0]].get('hem') and B.lock_info[g[1]].get('hem')]
        mid = lambda x: 0.5 * (x['tip_phi_range'][0] + x['tip_phi_range'][1])
        hem.sort(key=lambda g: mid(A.lock_info[g[0]]))
        dropped = []
        changed = True
        while changed:
            changed = False
            for i in range(len(hem) - 1):
                p1, p2 = hem[i], hem[i + 1]
                if ((mid(B.lock_info[p2[1]]) - mid(B.lock_info[p1[1]]) + 540) % 360 - 180) < -1e-6:
                    worst = p1 if p1[2] > p2[2] else p2
                    hem.remove(worst); got.remove(worst); dropped.append(worst)
                    changed = True
                    break
        matches.append(dict(views=[va, vb], pairs=[[int(a), int(b), round(c, 4)] for a, b, c in got],
                            order_dropped=len(dropped), candidates=[len(la), len(lb)]))
    parent, members = {}, {}

    def find(k):
        while parent.setdefault(k, k) != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k
    for name, S in splits.items():
        for l_ in S.lock_info:
            parent[(name, l_)] = (name, l_); members[(name, l_)] = {name}
    links = sorted((c, (m['views'][0], a), (m['views'][1], b)) for m in matches for a, b, c in m['pairs'])
    for c, ka, kb in links:
        ra, rb = find(ka), find(kb)
        if ra == rb or members[ra] & members[rb]:
            continue
        parent[rb] = ra
        members[ra] |= members[rb]
    roots, xid = {}, {}
    for k in parent:
        xid[k] = roots.setdefault(find(k), len(roots) + 1)
    return xid, matches


def tip_coords(splits, shell):
    """every detected tip (not only the locks') in head-centred coordinates, as head_coords' locks: -> {view: [dict(i,
    rc, uz, phi, phi_range, limb, lock)]}."""
    du, spread = P['match_du'], P['limb_spread']
    out = {}
    for name, S in splits.items():
        lst = []
        lk = {}
        for l_, x in S.lock_info.items():
            if x.get('tip_index') is not None:
                lk[x['tip_index']] = l_
        for i, t in enumerate(S.tip_list):
            u, z = S.uz(t['rc'])
            phi = shell.phi(u, z, S.az)
            lo, hi = sorted([shell.phi(u - du, z, S.az), shell.phi(u + du, z, S.az)])
            if hi - lo > 180:
                lo, hi = hi, lo + 360
            tt = np.linspace(-np.pi, np.pi, 721)
            umin, umax = float(np.nanmin(shell.u_of(tt, z, S.az))), float(np.nanmax(shell.u_of(tt, z, S.az)))
            limb = 1 if u >= umax - du else (-1 if u <= umin + du else 0)
            if limb:
                L_ = _limb(shell, z, S.az, limb)
                beyond = L_ + spread * (1 if ((L_ - S.az + 540) % 360 - 180) > 0 else -1)
                a_, b_ = sorted([L_, beyond])
                lo, hi = min(lo, a_), max(hi, b_)
            sm = S.tip_ends.get(i + 1) if hasattr(S, 'tip_ends') else None
            v = S.locks[sm] if sm is not None and sm.any() else np.zeros(0, int)
            v = v[v > 0]
            lst.append(dict(i=i, rc=[round(t['rc'][0], 1), round(t['rc'][1], 1)], uz=[round(u, 4), round(z, 4)],
                            phi=round(phi, 1), phi_range=[round(lo, 1), round(hi, 1)], limb=limb,
                            out=[round(t['out'][0], 3), round(t['out'][1], 3)],
                            lock=int(np.bincount(v).argmax()) if len(v) else None))
        out[name] = lst
    return out


def match_tips(tips, splits, shell, pairs=None, cost_max=None):
    """tips matched between views (the anchors of the locks' identity): by assignment on the gap between their
    azimuth intervals (arc length at the shell's radius), their heights and the vertical part of their outward
    direction (a flick curling up does so in every view); along each side's limb the order by height is kept.
    -> [dict(views, pairs [[tip a, tip b, cost]])]."""
    from scipy.optimize import linear_sum_assignment
    cost_max = cost_max or P['match_cost']
    names = [n for n in VIEWS if n in tips]
    pairs = pairs or [(a, b) for i, a in enumerate(names) for b in names[i + 1:]]
    res = []
    for va, vb in pairs:
        A = [t for t in tips[va] if _visible(t['phi_range'], splits[vb].az)]
        B = [t for t in tips[vb] if _visible(t['phi_range'], splits[va].az)]
        if not A or not B:
            continue
        M = np.full((len(A), len(B)), 10.0)
        for i, x in enumerate(A):
            for j, y in enumerate(B):
                zt = 0.5 * (x['uz'][1] + y['uz'][1])
                _, a_, _, b_ = shell.at(zt)
                rad = 0.5 * (a_ + b_)
                dphi = math.radians(_gap(x['phi_range'], y['phi_range'])) * rad
                dz = x['uz'][1] - y['uz'][1]
                dout = abs(x['out'][0] - y['out'][0]) * P['match_dir']
                M[i, j] = math.sqrt(dphi ** 2 + dz ** 2 + dout ** 2)
        ra, cb = linear_sum_assignment(M)
        got = [(A[i]['i'], B[j]['i'], float(M[i, j])) for i, j in zip(ra, cb) if M[i, j] <= cost_max]
        res.append(dict(views=[va, vb], pairs=[[a, b, round(c, 4)] for a, b, c in got], candidates=[len(A), len(B)]))
    return res


# ------------------------------------------------------------------------------------------------------------ run

def split_views(I, views=None, stage='locks', params=None, log=print):
    """inputs() -> {view: Split} (run), the shell, the cross-view ids and matches."""
    splits = {}
    for name, V in I['views'].items():
        if views and name not in views:
            continue
        S = Split(name, V, I['ppl'], params)
        S.run(stage)
        splits[name] = S
        log('%s: %s' % (name, json.dumps(S.report)))
    shell = Shell(splits) if 'front' in splits and 'profile' in splits else None
    xid, matches = {}, []
    if shell:
        head_coords(splits, shell)
        for S in splits.values():
            outer = _outer_bottom(S)
            for l_, x in S.lock_info.items():
                x['hem'] = bool(x['tip'] == 'drawn' and outer(x['tip_rc']))
        if P['match_by'] == 'tips':
            tips = tip_coords(splits, shell)
            tm = match_tips(tips, splits, shell)
            xid, matches = _locks_from_tips(splits, tips, tm)
            for name, S in splits.items():
                S.tips_head = tips[name]
            shell.tip_matches = tm
        else:
            xid, matches = match(splits, shell)
        for (name, l_), k in xid.items():
            splits[name].lock_info[l_]['xid'] = k
    return splits, shell, xid, matches


def _locks_from_tips(splits, tips, tm):
    """the locks' cross-view links from their tips' (each tip's lock: the one its end lies in), the cheapest first,
    one lock per view per id -> ({(view, lock): xid}, [per pair of views: lock links])."""
    matches = []
    for m in tm:
        va, vb = m['views']
        la = {t['i']: t['lock'] for t in tips[va]}; lb = {t['i']: t['lock'] for t in tips[vb]}
        seen = {}
        for a, b, c in m['pairs']:
            if la.get(a) and lb.get(b):
                k = (la[a], lb[b])
                if k not in seen or c < seen[k]:
                    seen[k] = c
        matches.append(dict(views=[va, vb], pairs=[[int(a), int(b), round(c, 4)] for (a, b), c in seen.items()],
                            tip_pairs=m['pairs']))
    parent, members = {}, {}

    def find(k):
        while parent.setdefault(k, k) != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k
    for name, S in splits.items():
        for l_ in S.lock_info:
            parent[(name, l_)] = (name, l_); members[(name, l_)] = {name}
    links = sorted((c, (m['views'][0], a), (m['views'][1], b)) for m in matches for a, b, c in m['pairs'])
    for c, ka, kb in links:
        if ka not in parent or kb not in parent:
            continue
        ra, rb = find(ka), find(kb)
        if ra == rb or members[ra] & members[rb]:
            continue
        parent[rb] = ra
        members[ra] |= members[rb]
    roots, xid = {}, {}
    for k in parent:
        xid[k] = roots.setdefault(find(k), len(roots) + 1)
    return xid, matches


def _outer_bottom(S):
    """-> f(rc): is this point on the hair's outer outline's lower edge (below it, within a few px, nothing but
    background)."""
    from scipy import ndimage
    filled = ndimage.binary_fill_holes(S.H)
    Hh = S.H.shape[0]

    def f(rc):
        r, c = int(round(rc[0])), int(round(rc[1]))
        c = min(max(c, 0), S.H.shape[1] - 1)
        below = filled[min(Hh - 1, r + 3):, c]
        return not below.any() or not filled[min(Hh - 1, r + 3):min(Hh, r + int(0.2 * S.ppl)), c].any()
    return f


def lock_images(splits, shape=None):
    """{view: full-grid int image (0 none)} of each split's locks."""
    return {n: S.full(S.locks.astype(np.int32)) for n, S in splits.items()}


def save(out, splits, shell, xid, matches, extra=None):
    os.makedirs(_p(out), exist_ok=True)
    imgs = {}
    for n, S in splits.items():
        imgs[n] = S.full(S.locks.astype(np.int32))
        imgs[n + '__cells'] = S.full(S.cells.astype(np.int32))
        imgs[n + '__walls'] = S.full((S.ink.astype(np.uint8) + 2 * S.ext.astype(np.uint8)))
    np.savez_compressed(os.path.join(_p(out), 'hairsplit.npz'), **imgs)
    meta = dict(format=FORMAT, params=P, views={})
    for n, S in splits.items():
        meta['views'][n] = dict(report=S.report, box=S.box, az=S.az, crown_rc=list(S.crown),
                                locks={str(k): v for k, v in S.lock_info.items()},
                                tips=[dict(rc=[round(t['rc'][0], 1), round(t['rc'][1], 1)], sharp=round(t['sharp'], 1),
                                           down=round(t['down'], 3)) for t in S.tip_list],
                                notches=[dict(rc=[round(t['rc'][0], 1), round(t['rc'][1], 1)], sharp=round(t['sharp'], 1))
                                         for t in S.notch_list],
                                layer_votes=[[int(a), int(b), int(w)] for (a, b), w in S.layer_votes.items()],
                                tips_head=getattr(S, 'tips_head', None))
    if shell is not None:
        meta['shell'] = dict(check=shell.check, z=shell.z[::5].round(3).tolist(), x0=shell.x0[::5].round(4).tolist(),
                             a=shell.a[::5].round(4).tolist(), y0=shell.y0[::5].round(4).tolist(),
                             b=shell.b[::5].round(4).tolist())
        meta['tip_matches'] = getattr(shell, 'tip_matches', None)
    meta['matches'] = matches
    if extra:
        meta.update(extra)
    json.dump(meta, open(os.path.join(_p(out), 'hairsplit.json'), 'w'), indent=1, default=float)
    return meta


# ------------------------------------------------------------------------------------------------------------ score

def floors(T, seeds=5):
    """the lock truth's floors: a random Voronoi split of its locks per view (hairlocks.shuffled) and one within each
    family (the family boundaries kept) -> {name: hairlocks.score result} (the seeds' mean per view and family)."""
    from . import hairlocks as hk
    from scipy import ndimage
    imgs, labels, meta = T
    hair = {v: np.ones(t.shape, bool) for v, t in imgs.items()}
    filled = {v: hk.fill_walls(t, hair[v]) for v, t in imgs.items()}

    def within(t, lab, seed):
        rng = np.random.RandomState(seed)
        out = np.zeros(t.shape, np.int32); k0 = 0
        for f in sorted({hk.family_of(q) for q in lab}):
            ids = [i for i, q in enumerate(lab) if hk.family_of(q) == f and (t == i).any()]
            m = np.isin(t, ids); k = len(ids)
            ys, xs = np.nonzero(m)
            j = rng.choice(len(ys), k, replace=False)
            mk = np.zeros(m.shape, np.int32); mk[ys[j], xs[j]] = np.arange(1, k + 1)
            _, idx = ndimage.distance_transform_edt(mk == 0, return_indices=True)
            out[m] = mk[idx[0], idx[1]][m] + k0
            k0 += k
        return out
    res = {}
    for name, fn in (('random', lambda v, s: hk.shuffled(filled[v], s)),
                     ('random_within_family', lambda v, s: within(filled[v], labels[v], s))):
        runs = [hk.score({v: fn(v, s) for v in imgs}, T, hair, meta['ppl']) for s in range(seeds)]
        res[name] = _mean_scores(runs)
    return res


def _mean_scores(runs):
    out = {}
    for v in runs[0]:
        out[v] = dict(lock_iou=round(float(np.mean([r[v]['lock_iou'] for r in runs])), 3), families={})
        for f in runs[0][v].get('families', {}):
            out[v]['families'][f] = dict(lock_iou=round(float(np.mean([r[v]['families'][f]['lock_iou'] for r in runs])), 3))
    return out


def truth_of(spec):
    """the spec's lock truth (the manifest's hair_locks_truth) or None."""
    from . import hairlocks as hk, manifest
    R = manifest.load(spec['ref']['manifest'])['references']
    return hk.load_truth(R['hair_locks_truth']['path']) if 'hair_locks_truth' in R else None


def score(imgs, truth=None, spec=None):
    """lock images {view: int image} against the lock truth (given, or the spec's) -> hairlocks.score's result (per
    view and family, 'all')."""
    from . import hairlocks as hk
    T = truth or truth_of(spec)
    hair = {v: np.ones(t.shape, bool) for v, t in T[0].items()}
    return hk.score({v: imgs[v] for v in T[0] if v in imgs}, T, hair, T[2]['ppl'])


def table(scores, floors_=None, views=VIEWS + ('all',)):
    """a compact {view: {family: lock_iou, '_all': ...}} of a score result."""
    out = {}
    for v in views:
        if v not in scores:
            continue
        out[v] = {f: y['lock_iou'] for f, y in scores[v].get('families', {}).items()}
        out[v]['_all'] = scores[v]['lock_iou']
    return out


# ------------------------------------------------------------------------------------------------------------ CLI

def main(args):
    if args and args[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    from . import manifest
    sp = next((a for a in args if a.endswith('.json')), 'charkit/spec/clawd.json')
    spec = manifest.resolve(json.load(open(_p(sp))))
    out = args[args.index('--out') + 1] if '--out' in args else 'charkit/out/hairsplit/run'
    stage = args[args.index('--stage') + 1] if '--stage' in args else 'locks'
    views = None
    if '--views' in args:
        views = args[args.index('--views') + 1].split(',')
    I = inputs(spec, cache=os.path.join(out, 'inputs.pkl') if '--cache' in args else None)
    splits, shell, xid, matches = split_views(I, views, stage)
    extra = {}
    if '--score' in args:
        T = truth_of(spec)
        if T is None:
            print('no lock truth in the manifest: nothing to score')
        else:
            r = score(lock_images(splits), T)
            extra['score'] = table(r)
            extra['floors'] = {k: {v: x[v]['lock_iou'] for v in x} for k, x in floors(T).items()}
        for v, x in extra.get('score', {}).items():
            print('%-14s %s' % (v, '  '.join('%s %.3f' % (f, q) for f, q in sorted(x.items()))))
        if 'floors' in extra:
            print('floors (all): %s' % ', '.join('%s %.3f' % (k, x['all']) for k, x in extra['floors'].items()))
    save(out, splits, shell, xid, matches, extra)
    print('wrote', os.path.join(out, 'hairsplit.json'))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
