"""Artifact QA: the jaggedness a viewer sees as "torn", "stepped" or "dotted", measured per region and view as numbers
(numpy, scipy and skimage; venv-side on a build's bundle, from the QA's own numpy drawings: buffers(), qa3d.draw's mesh
and tone buffers without its picture). Every measure is in head lengths (L), so a drawing at another scale reads the
same, and each is graded as a ratio to the design's own value: the design's turnarounds (the head sheet at 400 px/L, the
body sheet at its own scale with the outfit's piece masks) measured by the same detectors, stored beside the refs
(DESIGN_FILE, refreshed by `python -m charkit.artifactqa design BUNDLE_DIR`), so a build doesn't re-measure them.

Regions: hair, face (skin above the chin), neck (skin from the chin to 0.5 L under it), collar, bow, top, skirt, boots.
Views: front, three_quarter, profile, back. The head frame (400 px/L) holds hair, face and neck; the body frame (the
body sheet's px per L) the garments. Outlines are traced at sub-pixel precision (the mask softened by EDGE_AA px, cut at
0.5) and smoothed along their length at S1 (pixel noise off).

  outline      corners per L of a region's outline: a turn of CORNER_DEG or more between the chords CORNER_ARC long
               either side (a torn tip, a notch, a step, a sawtooth tooth; also a drawn tip, which the design has too).
               `rms`: the outline's deviation from itself smoothed at S2, band-passed (L)
  terminator   kinks per L of the cel tone boundaries inside a region (shade from lit, deep from shade; its outline
               and drawn lines' fringes left out): a turn between KINK_DEG over KINK_ARC, the bend where a terminator
               crosses a mesh facet, not a drawn stroke's tapered tip (sharper) nor a curve (gentler).
               `islands`: tone patches between ISLAND_MIN and ISLAND L^2, clear of the outline and lines, per L^2
  fragments    the area of the region's flat colour (between its drawn lines) in small pieces (under FRAG L^2: a lock
               tip broken off, a torn collar tip) and slivers (thinner than SLIVER: a strand peeking between two
               lines, a stepped edge), per L of outline (L^2 / L)
  speckle      skin only: specks under SPECK L^2 in the skin away from the features (tone islands, another surface
               showing through, a drawing's short strokes: the neck seam's dots), per L^2 of skin
  peeks        ours only (the drawing has no pieces): small visible bits of a region's own pieces, each object's
               components but its largest under FRAG L^2 (a lock tip peeking past the lock in front of it); a count

Silhouettes (body frame; Michael's flags as regression checks, each calibrated to pass on the design and fail on the
build where he saw it: docs/workstreams/artifacts.md):
  spikes       the figure's silhouette opened by a disk SPIKE_R across: what it cuts off standing SPIKE_H or more out,
               given to the region inside it; its tallest (L) beyond the design's (a jagged boot protrusion)
  points       the silhouette's sharpest outward turn over CAP_ARC per region (deg), beyond the design's (floored at
               CAP_MIN): the hull-lofted sleeves' pointed caps
  bumps        its sharpest outward turn over BUMP_ARC where the silhouette is one region's own for BUMP_PURE round it
               (a junction with another piece is a corner by design): the knob behind the thigh in profile, a jagged boot
  mirror       1 - IoU of a region with its mirror image: the waist (jacket, band, skirt, flaps) about the figure's axis
               (the skirt jutting past the band on one side), the boots about their own (a pair unlike each other); a
               ratio to the design's
  band         the skirt and flaps' dark hem band's edge on the picture drawn with its textures: kinks per L (pixel
               stairs), a ratio to the design's (its few clean steps)

Checks art_<detector>_<region>: the worst view's ratio to the design's (the design's floored: DETECTORS), per view
ours, the design's and the ratio beside it; INFO, with the grade PROPOSED limits would give. The silhouettes' checks
(SHAPE_CHECKS: art_spikes_*, art_points_*, art_bumps_*, art_mirror_waist, art_mirror_self_boots, art_band_lower): the
worst view's excess over the design's, or ratio to it. Calibration: see docs/workstreams/artifacts.md.

    from charkit import artifactqa
    artifactqa.outline(mask, ppl)                        # -> dict(len, corners, kinks, rms, ...) for any boolean mask
    table, checks = artifactqa.measure(B, design, out)   # charkit.qa3d's 'artifacts' part
"""
import numpy as np

REGIONS = ('hair', 'face', 'neck', 'collar', 'bow', 'top', 'skirt', 'boots')
VIEWS = ('front', 'three_quarter', 'profile', 'back')
S1, S2 = 0.004, 0.02        # L: the band's fine and coarse smoothing along the outline (S1 at least 1 px)
CORNER_ARC = 0.005          # L: a corner turns by CORNER_DEG or more between the chords this long either side of it
CORNER_DEG = 40.0
KINK_ARC = 0.006            # L: a kink turns by KINK_DEG between the chords this long either side of it: a facet's
KINK_DEG = (25.0, 90.0)     # bend, not a drawn stroke's tapered tip (sharper) nor a curve (gentler)
EDGE_AA = 0.7               # px: a mask's soft edge before tracing (sub-pixel outlines from a binary mask)
MIN_LEN = 0.1               # L: outlines shorter than this are fragments, not outlines
ISLAND = 0.002              # L^2: a tone patch under this inside a region is an island ...
ISLAND_MIN = 0.00002        # L^2: ... and over this (a render's pixel filter blurs anything smaller away)
FRAG = 0.002                # L^2: a component of a region under this is a fragment
SLIVER = 0.012              # L: a part of a region thinner than this is a sliver
SPECK = 0.0004              # L^2: a speck in the skin is under this ...
SPECK_MIN = 0.00001         # L^2: ... and over this
EDGE_BAND = 0.006           # L: tone patches within this of a region's outline are the outline's fringe
TONE_BLUR = 0.9             # px: our tone buffer softened as a render's pixel filter (~0.5) and a drawing's cut (0.7)


# ------------------------------------------------------------------------------------------------------ outlines
def _bbox(mask, pad):
    rows, cols = np.nonzero(mask.any(1))[0], np.nonzero(mask.any(0))[0]
    if not len(rows):
        return None
    H, W = mask.shape
    return max(0, rows[0] - pad), min(H, rows[-1] + pad + 1), max(0, cols[0] - pad), min(W, cols[-1] + pad + 1)


def contours(mask):
    """a boolean mask's outlines at sub-pixel precision: the mask softened by EDGE_AA px and cut at 0.5 (every outline
    closed: the mask is padded) -> [(n, 2) (row, col) arrays in the mask's own frame]."""
    from scipy.ndimage import gaussian_filter
    from skimage.measure import find_contours
    bb = _bbox(mask, 3)
    if bb is None:
        return []
    r0, r1, c0, c1 = bb
    m = np.pad(mask[r0:r1, c0:c1], 3).astype(np.float32)
    soft = gaussian_filter(m, EDGE_AA)
    return [c + (r0 - 3, c0 - 3) for c in find_contours(soft, 0.5)]


def _resample(c, h=0.5):
    """a closed outline at even steps of about h px along it -> (points, step)."""
    c = np.asarray(c, float)
    if np.allclose(c[0], c[-1]):
        c = c[:-1]
    seg = np.linalg.norm(np.diff(np.vstack([c, c[:1]]), axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    total = s[-1]
    n = max(int(round(total / h)), 8)
    t = np.arange(n) * total / n
    cc = np.vstack([c, c[:1]])
    return np.stack([np.interp(t, s, cc[:, 0]), np.interp(t, s, cc[:, 1])], 1), total / n


def band(c, ppl):
    """a closed outline (px) band-passed between S1 and S2 -> (points at S1 (px), their signed deviation from the S2
    outline (L), each point's length along the S2 outline (L): lengths are the shape's, not its teeth's)."""
    from scipy.ndimage import gaussian_filter1d
    p, h = _resample(c)
    s1, s2 = max(S1 * ppl, 1.0) / h, S2 * ppl / h
    p1 = gaussian_filter1d(p, s1, axis=0, mode='wrap')
    p2 = gaussian_filter1d(p, s2, axis=0, mode='wrap')
    t = np.roll(p2, -1, 0) - np.roll(p2, 1, 0)
    n = np.stack([t[:, 1], -t[:, 0]], 1) / np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-9)
    return p1, ((p1 - p2) * n).sum(1) / ppl, np.linalg.norm(t, axis=1) / 2 / ppl


def corners(p, keep, ppl, arc=CORNER_ARC, deg=(CORNER_DEG, 360.0)):
    """a closed outline's corners (points at S1, px): where the chords `arc` L long either side turn by deg[0] or more,
    the sharpest within twice the arc kept, and those under deg[1] counted -> (indices, the turn at each point in
    degrees, signed)."""
    n = len(p)
    h = np.linalg.norm(np.diff(np.vstack([p, p[:1]]), axis=0), axis=1).mean()
    k = max(1, int(round(arc * ppl / max(h, 1e-9))))
    f = np.roll(p, -k, 0) - p
    b = p - np.roll(p, k, 0)
    turn = np.degrees(np.arctan2(f[:, 0] * b[:, 1] - f[:, 1] * b[:, 0], (f * b).sum(1)))
    a = np.abs(turn)
    cand = np.nonzero((a >= deg[0]) & (a >= np.roll(a, 1)) & (a > np.roll(a, -1)) & keep)[0]
    taken = np.zeros(n, bool)
    out = []
    for i in cand[np.argsort(-a[cand])]:
        if not taken[i]:
            taken[np.arange(i - 2 * k, i + 2 * k + 1) % n] = True
            if a[i] < deg[1]:
                out.append(i)
    return np.array(sorted(out), int), turn


def _lookup(img, p):
    """a boolean image at outline points (px, row/col; nearest pixel, off the image False)."""
    r = np.rint(p[:, 0]).astype(int)
    c = np.rint(p[:, 1]).astype(int)
    H, W = img.shape
    ok = (r >= 0) & (r < H) & (c >= 0) & (c < W)
    out = np.zeros(len(p), bool)
    out[ok] = img[r[ok], c[ok]]
    return out


def _stats(parts):
    """outline measures pooled over outline records (deviation, kept, length per point, points, (corners, kinks))."""
    L = sum(float(h[keep].sum()) for d, keep, h, _, _ in parts)
    if L <= 0:
        return None
    dd = np.concatenate([d[keep] for d, keep, h, _, _ in parts])
    nc = sum(len(ck[0]) for *_, ck in parts)
    nk = sum(len(ck[1]) for *_, ck in parts)
    return dict(len=round(L, 4), corners=round(nc / L, 3), kinks=round(nk / L, 3),
                rms=round(float(np.sqrt(np.mean(dd ** 2))), 5), n_corners=int(nc), n_kinks=int(nk))


def _outline_parts(cs, ppl, keep_img):
    parts = []
    for c in cs:
        seg = np.linalg.norm(np.diff(c, axis=0), axis=1).sum()
        if seg < MIN_LEN * ppl:
            continue
        p1, d, h = band(c, ppl)
        keep = _lookup(keep_img, p1) if keep_img is not None else np.ones(len(d), bool)
        if not keep.any():
            continue
        parts.append((d, keep, h, p1, (corners(p1, keep, ppl)[0], corners(p1, keep, ppl, KINK_ARC, KINK_DEG)[0])))
    return parts


def outline(mask, ppl, keep=None, parts=None):
    """a region's outline roughness (see the module): mask (H, W) bool at ppl px per L; keep: where outline points count
    (a zone, the frame's inside) or None -> dict(len (L), corners (per L), rms (L), n_corners) or None (no outline).
    parts: a list to receive (deviation, kept, length per point, points, corner indices) per outline, for a picture."""
    P = _outline_parts(contours(mask), ppl, keep)
    if parts is not None:
        parts.extend(P)
    return _stats(P)


# ------------------------------------------------------------------------------------------------------ tones
def _crop(bb, *imgs):
    r0, r1, c0, c1 = bb
    return [None if x is None else (x[r0:r1, c0:c1] if np.ndim(x) == 2 else x) for x in imgs]


def terminator(region, tone, ppl, keep=None, parts=None, inset=2, line=None, marks=None):
    """the cel tone boundaries inside a region (tone: int image, 0 lit, 1 shade, 2 deep, -1 unknown), measured as outline
    measures an outline; the region's own outline (within `inset` px of it) and its drawn lines' fringes left out.
    -> dict(len, corners, kinks, rms, n_corners, n_kinks, islands (tone patches between ISLAND_MIN and ISLAND L^2 per
    L^2 of region), n_islands, shade (share of the region in shade)) or None."""
    from scipy import ndimage
    if region.sum() < 50:
        return None
    bb = _bbox(region, 4)
    rg, tn, kp, ln = _crop(bb, region, tone, keep, line)
    inner = ndimage.binary_erosion(rg, iterations=inset, border_value=0)
    if ln is not None and ln.any():                      # (a tone edge along a drawn line is the line's fringe)
        inner &= ~ndimage.binary_dilation(ln, iterations=2)
    if kp is not None:
        inner &= kp
    known = rg & (tn >= 0)
    P = []
    for k in (1, 2):
        sh = rg & (tn >= k)
        if sh.sum() < 10 or (known & (tn < k)).sum() < 10:
            continue
        P += _outline_parts([c + (bb[0], bb[2]) for c in contours(sh)], ppl,
                            _uncrop(inner, bb, region.shape))
    if parts is not None:
        parts.extend(P)
    st = _stats(P) or dict(len=0.0, corners=0.0, kinks=0.0, rms=0.0, n_corners=0, n_kinks=0)
    area = float((rg & (kp if kp is not None else True)).sum()) / ppl ** 2
    mk = [] if marks is not None else None
    n = islands(rg, tn, ppl, kp, line=ln, cropped=True, marks=mk)
    if mk:
        marks.append(('islands', bb, np.logical_or.reduce(mk)))
    st.update(islands=round(n / max(area, 1e-9), 2), n_islands=n, area=round(area, 4),
              shade=round(float((known & (tn >= 1)).sum() / max(1, known.sum())), 4))
    return st


def _uncrop(m, bb, shape):
    out = np.zeros(shape, bool)
    out[bb[0]:bb[1], bb[2]:bb[3]] = m
    return out


def islands(region, tone, ppl, keep=None, max_area=ISLAND, min_area=ISLAND_MIN, line=None, cropped=False, marks=None):
    """tone patches inside a region between min_area and max_area (L^2; at least a pixel), clear of the region's outline
    band (EDGE_BAND: a patch there is the outline's) and of its drawn lines (a line's fringe), centred in keep -> count.
    marks: a list to receive the patches' mask (in the region's frame: cropped to it when not `cropped`)."""
    from scipy import ndimage
    if not cropped:
        bb = _bbox(region, 4)
        if bb is None:
            return 0
        region, tone, keep, line = _crop(bb, region, tone, keep, line)
    lim = max_area * ppl ** 2
    min_px = max(1.0, min_area * ppl ** 2)
    band = ~ndimage.binary_erosion(region, iterations=int(np.ceil(max(2.0, EDGE_BAND * ppl))), border_value=0)
    if line is not None and line.any():
        band = band | ndimage.binary_dilation(line & region, iterations=1)
    n = 0
    H, W = region.shape
    yy = np.arange(H)[:, None].repeat(W, 1)
    xx = np.arange(W)[None, :].repeat(H, 0)
    for v in np.unique(tone[region & (tone >= 0)]):
        lab, k = ndimage.label(region & (tone == v), structure=np.ones((3, 3)))
        if not k:
            continue
        area = np.bincount(lab.ravel(), minlength=k + 1)
        touch = np.bincount(lab[band], minlength=k + 1) > 0
        small = (area >= min_px) & (area < lim) & ~touch
        small[0] = False
        if keep is not None and small.any():
            cy = np.bincount(lab.ravel(), yy.ravel(), k + 1) / np.maximum(area, 1)
            cx = np.bincount(lab.ravel(), xx.ravel(), k + 1) / np.maximum(area, 1)
            ok = keep[np.clip(np.rint(cy).astype(int), 0, H - 1), np.clip(np.rint(cx).astype(int), 0, W - 1)]
            small &= ok
        n += int(small.sum())
        if marks is not None and small.any():
            marks.append(small[lab])
    return n


def fragments(inner, ppl, keep=None, outline_len=None, marks=None):
    """a region's flat colour between its drawn lines (inner): its small components (under FRAG L^2: a lock tip broken
    off, a torn tip) and its slivers (thinner than SLIVER: what an opening of radius SLIVER / 2 removes, pieces over 2
    px: a strand peeking between two lines) -> dict(n, area (L^2), slivers, sliver_area (L^2), per_L (fragments and
    slivers per L of the region's outline: outline_len, else the inner's own)) or None."""
    from scipy import ndimage
    from skimage.morphology import disk
    if inner.sum() < 20:
        return None
    r0, r1, c0, c1 = _bbox(inner, 4)
    m = inner[r0:r1, c0:c1]
    kp = keep[r0:r1, c0:c1] if keep is not None else None
    lab, k = ndimage.label(m, structure=np.ones((3, 3)))
    area = np.bincount(lab.ravel(), minlength=k + 1)
    small = (area < FRAG * ppl ** 2) & (area > 2)
    small[0] = False
    tiny = area <= 2
    tiny[0] = False
    if kp is not None:
        small &= np.bincount(lab[kp], minlength=k + 1) > 0.5 * area
    rest = m & ~small[lab] & ~tiny[lab]
    rad = max(1, int(round(SLIVER / 2 * ppl)))
    res = rest & ~ndimage.binary_opening(rest, structure=disk(rad))
    rl, rk = ndimage.label(res, structure=np.ones((3, 3)))
    ra = np.bincount(rl.ravel(), minlength=rk + 1)
    big = ra > 2
    big[0] = False
    if kp is not None and rk:
        big &= np.bincount(rl[kp], minlength=rk + 1) > 0.5 * ra
    if marks is not None:
        bb = (r0, r1, c0, c1)
        marks.append(('fragments', bb, small[lab]))
        marks.append(('slivers', bb, big[rl]))
    L = outline_len if outline_len else \
        sum(float(np.linalg.norm(np.diff(c, axis=0), axis=1).sum()) for c in contours(m)) / ppl
    n, ns = int(small.sum()), int(big.sum())
    return dict(n=n, area=round(float(area[small].sum()) / ppl ** 2, 5), slivers=ns,
                sliver_area=round(float(ra[big].sum()) / ppl ** 2, 5), len=round(L, 3),
                per_L=round((n + ns) / max(L, 1e-9), 3))


def peeks(mesh, surfs, members, ppl, keep=None):
    """small visible bits of a region's own pieces (ours only: the drawing has no pieces): each object's pixels (its
    outline hull off) in components, every one but its largest that is over 3 px and under FRAG L^2 (a lock's tip peeking
    past the lock in front of it, a torn collar tip cut off by the bow) -> count."""
    from scipy import ndimage
    if not members:
        return 0
    names = sorted({surfs[i]['o'].name for i in members})
    of = np.zeros(len(surfs) + 1, np.int32)
    for i in members:
        of[i] = names.index(surfs[i]['o'].name) + 1
    obj = of[np.where(mesh >= 0, mesh, len(surfs))]
    lim = FRAG * ppl ** 2
    n = 0
    for j, sl in enumerate(ndimage.find_objects(obj)):
        if sl is None:
            continue
        mm = obj[sl] == j + 1
        lab, k = ndimage.label(mm, structure=np.ones((3, 3)))
        if k < 2:
            continue
        area = np.bincount(lab.ravel(), minlength=k + 1)
        area[0] = 0
        small = (area > 3) & (area < lim)
        small[np.argmax(area)] = False
        if keep is not None:
            small &= np.bincount(lab[keep[sl]], minlength=k + 1) > 0.5 * area
        n += int(small.sum())
    return n


def speckle(clear, tone, ppl, foreign=None, keep=None, dots=None, line=None, marks=None):
    """specks in the skin away from the features (clear): its tone islands between SPECK_MIN and SPECK L^2, and small
    components (under SPECK) of foreign (another surface's pixels showing inside the skin's filled outline) and of dots
    (a drawing's short dark strokes) -> dict(n, per_L2 (specks per L^2 of clear skin), area) or None."""
    from scipy import ndimage
    if clear.sum() < 50:
        return None
    bb = _bbox(clear, 6)
    cl, tn, kp, ln, fo, do = _crop(bb, clear, tone, keep, line, foreign, dots)
    mk = [] if marks is not None else None
    n = islands(cl, tn, ppl, kp, max_area=SPECK, min_area=SPECK_MIN, line=ln, cropped=True, marks=mk)
    near = ndimage.binary_dilation(cl, iterations=1)
    lim = SPECK * ppl ** 2
    for f in (fo, do):
        if f is None:
            continue
        filled = ndimage.binary_fill_holes(cl | f)
        lab, k = ndimage.label(f & filled & near, structure=np.ones((3, 3)))
        if k:
            area = np.bincount(lab.ravel(), minlength=k + 1)
            small = area < lim
            small[0] = False
            if kp is not None:
                small &= np.bincount(lab[kp], minlength=k + 1) > 0.5 * area
            n += int(small.sum())
            if mk is not None and small.any():
                mk.append(small[lab])
    if mk:
        marks.append(('specks', bb, np.logical_or.reduce(mk)))
    area = float(clear.sum()) / ppl ** 2
    return dict(n=int(n), per_L2=round(n / max(area, 1e-9), 2), area=round(area, 4))


# ------------------------------------------------------------------------------------------------------ silhouettes
# Michael's flags on shapes (spiky puff sleeves, a jagged boot, a leg's bump, a midriff's one-sided distortion, the
# hem band's zigzag): measured on the figure's silhouette (each point or piece given to the region inside it), on the
# regions' own masks (mirror) and on the drawn picture (the band), on both sides alike, graded as ours beyond the
# design's in the same view (shape_checks).
SPIKE_R = 0.03              # L: the opening's disk radius: a part of a silhouette narrower than twice this is cut off ...
SPIKE_H = 0.012             # L: ... and is a spike where it stands this far out of what the opening keeps
MIRROR_SHIFT = 0.08         # L: the mirror axis is the figure's (its best mirror within this of its middle column)
LEG_TOP = -2.62             # L from the eye line: the legs are the skin under this (the thighs under the shorts)


SOLID = 0.01                # L: a silhouette's gaps under this closed (a drawn outline parted from its fill by a pale seam)


def solid(mask, ppl):
    """a silhouette as a solid: closed by a disk SOLID across and its holes filled (a drawing's lines and seams, our
    outline hulls' gaps are not its shape)."""
    from scipy import ndimage
    from skimage.morphology import disk
    r = max(1, int(round(SOLID / 2 * ppl)))
    m = np.pad(mask, r + 1)
    m = ndimage.binary_fill_holes(ndimage.binary_closing(m, structure=disk(r)))
    return m[r + 1:-r - 1, r + 1:-r - 1]


def figure_spikes(fg, kinds, ppl, keep=None, marks=None):
    """the figure's silhouette spikes: what an opening by a disk SPIKE_R across cuts off its solid() that stands SPIKE_H
    or more out of what it keeps (a horn, a jagged protrusion, a tail's tooth), each given to the kind holding most of
    its pixels. On the whole figure, as its silhouette doesn't hang on how a drawing's same-coloured pieces are told
    apart (a region's own mask on the design gave the jacket's side to the sleeves) -> [(kind, height (L), area (L^2),
    top row, bottom row)]."""
    from scipy import ndimage
    from skimage.morphology import disk
    if fg.sum() < 50:
        return []
    rad = max(1, int(round(SPIKE_R * ppl)))
    r0, r1, c0, c1 = bb = _bbox(fg, rad + 2)
    m = solid(fg[r0:r1, c0:c1], ppl)
    kept = ndimage.binary_opening(m, structure=disk(rad))
    lab, k = ndimage.label(m & ~kept, structure=np.ones((3, 3)))
    if not k:
        return []
    d = ndimage.distance_transform_edt(~kept) if kept.any() else np.full(m.shape, float(rad))
    idx = np.arange(1, k + 1)
    h = ndimage.maximum(d, lab, idx) / ppl
    area = np.bincount(lab.ravel(), minlength=k + 1)[1:]
    ok = h >= SPIKE_H
    if keep is not None:
        ok &= np.bincount(lab[keep[r0:r1, c0:c1]], minlength=k + 1)[1:] >= 0.5 * area
    names = [n for n in kinds]
    own = np.stack([np.bincount(lab[kinds[n][r0:r1, c0:c1]], minlength=k + 1)[1:] for n in names], 1)
    sl = ndimage.find_objects(lab)
    out = []
    for j in np.nonzero(ok)[0]:
        if own[j].max() == 0:
            continue
        out.append((names[int(own[j].argmax())], round(float(h[j]), 4), round(float(area[j]) / ppl ** 2, 5),
                    r0 + sl[j][0].start, r0 + sl[j][0].stop))
    if marks is not None and out:
        marks.append(('spikes', bb, np.isin(lab, [j + 1 for j in np.nonzero(ok)[0]])))
    return out


CAP_ARC = 0.02              # L: a point of the silhouette turns outward by CAP_DEG or more between chords this long
CAP_DEG = 55.0              # either side of it (a sleeve cap's pointed corner; a drawn puff rounds it)
CAP_MIN = 25.0              # (turns from this up are listed: a region's sharpest is its `turn`)
BUMP_ARC = 0.06             # L: a bump turns between chords this long (a knob behind the thigh; a tuck's pinch, inward),
BUMP_MIN = 10.0             # from this up, where the silhouette is its region's own for BUMP_PURE round it (a junction
BUMP_PURE = 0.015           # with another piece is a corner by design)


def _peaks(a, keep, lo, k):
    """a closed outline's turns a (signed: the outward ones here) at their peaks: from lo up, kept, the largest within
    twice k samples of each (a knob between two concave junctions is its own peak) -> [index]."""
    n = len(a)
    k = max(1, int(round(k)))
    cand = np.nonzero((a >= lo) & (a >= np.roll(a, 1)) & (a > np.roll(a, -1)) & keep)[0]
    taken = np.zeros(n, bool)
    out = []
    for i in cand[np.argsort(-a[cand])]:
        if not taken[i]:
            taken[np.arange(i - 2 * k, i + 2 * k + 1) % n] = True
            out.append(int(i))
    return sorted(out)


def figure_points(fg, kinds, ppl, keep=None, marks=None):
    """the figure's silhouette points (its outline smoothed at S1): its outward turns of CAP_MIN or more over CAP_ARC
    either side ('cap'), and its turns either way of BUMP_MIN or more over BUMP_ARC where every figure pixel within
    BUMP_PURE is of one kind ('bump'), each given to the kind just inside it -> [(tag, kind, turn (deg, + outward), row)]."""
    from scipy import ndimage
    from scipy.ndimage import gaussian_filter1d
    m = solid(fg, ppl)
    names = list(kinds)
    lab = np.full(fg.shape, -1, int)
    for i, n in enumerate(names):
        lab[kinds[n]] = i
    # each pixel of the figure takes its nearest kind (the outline hulls and seams belong to what they wrap)
    _, (iy, ix) = ndimage.distance_transform_edt(lab < 0, return_indices=True)
    lab = np.where(m, lab[iy, ix], -1)
    rp = max(1, int(round(BUMP_PURE * ppl)))
    mixed = np.zeros(fg.shape, bool)                       # figure pixels with another kind within BUMP_PURE
    for i in np.unique(lab[lab >= 0]):
        near = ndimage.binary_dilation(lab == i, iterations=rp)
        mixed |= near & m & (lab != i)
    mixed = ndimage.binary_dilation(mixed, iterations=rp)
    out = []
    for c in contours(m):
        if np.linalg.norm(np.diff(c, axis=0), axis=1).sum() < MIN_LEN * ppl:
            continue
        p, h = _resample(c)
        p = gaussian_filter1d(p, max(S1 * ppl, 1.0) / h, axis=0, mode='wrap')
        k = _lookup(keep, p) if keep is not None else np.ones(len(p), bool)
        _, fine = corners(p, np.ones(len(p), bool), ppl, arc=S1, deg=(360.0, 361.0))
        sgn = 1.0 if fine.sum() >= 0 else -1.0             # (the outline's way round: its turns sum to +-360)
        q = np.rint(p).astype(int)
        q[:, 0] = np.clip(q[:, 0], 0, fg.shape[0] - 1)
        q[:, 1] = np.clip(q[:, 1], 0, fg.shape[1] - 1)
        for tag, arc, lo, kk in (('cap', CAP_ARC, CAP_MIN, k), ('bump', BUMP_ARC, BUMP_MIN, k & ~_lookup(mixed, p))):
            _, turn = corners(p, kk, ppl, arc=arc, deg=(360.0, 361.0))
            turn = sgn * turn
            for i in _peaks(turn, kk, lo, arc * ppl / h) + ([] if tag == 'cap' else _peaks(-turn, kk, lo, arc * ppl / h)):
                t = turn[i]
                r_, c_ = q[i]
                win = lab[max(0, r_ - 2):r_ + 3, max(0, c_ - 2):c_ + 3]      # (the kind just inside the point)
                win = win[win >= 0]
                kind = names[int(np.bincount(win).argmax())] if len(win) else 'other'
                out.append((tag, kind, round(float(t), 1), int(r_)))
                if marks is not None and tag == 'cap' and t >= CAP_DEG and 3 <= r_ < fg.shape[0] - 3 \
                        and 3 <= c_ < fg.shape[1] - 3:
                    mm = np.ones((7, 7), bool)
                    marks.append(('points', (r_ - 3, r_ + 4, c_ - 3, c_ + 4), mm))
    return out


BAND_IN = 0.012             # L: the band's edge counts this far inside its region (its hem is the region's own outline)


def band_edge(rgb, region, ppl, line=None, keep=None, parts=None):
    """the dark band's edge inside a region (the skirt's and the flaps' stepped hem band, a texture on ours, drawn on the
    design): the dark colour family's outline where it runs inside the region (BAND_IN from its outline), as outline()
    reads it: corners per L (a few clean steps; pixel stairs are many) -> dict(len, corners, ...) or None."""
    from scipy import ndimage
    from . import bodyqa
    if region.sum() < 50:
        return None
    r0, r1, c0, c1 = _bbox(region, 4)
    reg = region[r0:r1, c0:c1]
    ln = line[r0:r1, c0:c1] if line is not None else np.zeros_like(reg)
    fam = bodyqa.family(np.asarray(rgb, float)[r0:r1, c0:c1, :3])
    dark = (fam == bodyqa.CLASS['dark']) & reg & ~ln
    dark = ndimage.binary_opening(dark) if dark.sum() > 20 else dark
    if dark.sum() < 20:
        return None
    inner = ndimage.binary_erosion(solid(reg, ppl), iterations=max(1, int(round(BAND_IN * ppl))))
    kp = inner if keep is None else inner & keep[r0:r1, c0:c1]
    P = []
    rec = outline(dark, ppl, keep=kp, parts=P)
    if parts is not None:
        parts.extend([(d, k, h, p + (r0, c0), ck) for d, k, h, p, ck in P])
    return rec


def mirror_axis(fg, ppl):
    """the figure's mirror axis (a column, px, between two): the shift within MIRROR_SHIFT of its middle column whose
    mirror image overlaps it most (front and back views)."""
    rows, cols = np.nonzero(fg.any(1))[0], np.nonzero(fg.any(0))[0]
    if not len(cols):
        return None
    fg = fg[rows[0]:rows[-1] + 1]
    mid = (cols[0] + cols[-1]) / 2.0
    best = None
    for a2 in np.arange(int(round(2 * (mid - MIRROR_SHIFT * ppl))), int(round(2 * (mid + MIRROR_SHIFT * ppl))) + 1):
        m = _mirrored(fg, a2 / 2.0)
        iou = (fg & m).sum() / max((fg | m).sum(), 1)
        if best is None or iou > best[0]:
            best = (iou, a2 / 2.0)
    return best[1]


def _mirrored(mask, axis):
    """a mask mirrored about a column (px; x -> 2 axis - x), on the same grid."""
    W = mask.shape[1]
    src = np.rint(2 * axis - np.arange(W)).astype(int)
    ok = (src >= 0) & (src < W)
    out = np.zeros_like(mask)
    out[:, ok] = mask[:, src[ok]]
    return out


def mirror(mask, axis, ppl):
    """a region's asymmetry about the figure's axis (mirror_axis): 1 - IoU with its mirror image, and the area off it per
    L of the region's height (L^2 / L: a skirt jutting out on one side, a boot unlike its pair) -> dict or None."""
    if axis is None or mask.sum() < 50:
        return None
    m = _mirrored(mask, axis)
    rows = np.nonzero(mask.any(1))[0]
    off = (mask & ~m).sum() + (m & ~mask).sum()
    return dict(asym=round(1 - (mask & m).sum() / max((mask | m).sum(), 1), 4),
                off=round(float(off) / 2 / ppl ** 2 / max((rows[-1] - rows[0] + 1) / ppl, 1e-9), 5))


BANDS = ('lower',)          # the regions whose dark hem band is measured (band_edge): the skirt with its flaps (the
                            # drawing's cells don't part a flap's tail from the skirt's band reliably)
MIRROR_FIGURE = ('waist',)              # asymmetry about the figure's axis (a skirt jutting out on one side)
MIRROR_SELF = ('boots',)                # ... about its own axis (a pair unlike each other, wherever the legs stand)
SHAPES = {                  # the silhouettes measured for shape: region -> the kinds it unites (and rows it keeps)
    'collar': ('collar',), 'bow': ('bow',), 'top': ('top',), 'skirt': ('skirt',), 'boots': ('boots',),
    'sleeves': ('sleeves',), 'flaps': ('flaps',),
    'waist': ('top', 'band', 'skirt', 'flaps'),            # the torso from the jacket to the skirt: ledges, the tuck
    'lower': ('skirt', 'flaps'),                           # the skirt with its flaps: their steps and teeth
    'legs': ('skin',),                                     # under LEG_TOP
}


def shape_view(kinds, fg, ppl, view, z_of_row, keep=None, marks=None, rgb=None, line=None, band_parts=None):
    """the silhouette detectors on a view's kinds ({kind: mask}; fg the figure; z_of_row(rows) -> L from the eye line;
    rgb the picture, for the hem band; line its drawn lines) -> {region (SHAPES): dict(spikes, points, bumps, and where
    they apply band (BANDS), mirror (MIRROR_FIGURE), mirror_self (MIRROR_SELF): front and back)}."""
    H, W = fg.shape
    axis = mirror_axis(fg, ppl) if view in ('front', 'back') and MIRROR_FIGURE else None
    zr = z_of_row(np.arange(H))
    fsp = figure_spikes(fg, kinds, ppl, keep, marks)
    fpt = figure_points(fg, kinds, ppl, keep, marks)
    out = {}
    for r, ks in SHAPES.items():
        m = np.zeros((H, W), bool)
        for k in ks:
            if k in kinds:
                m |= kinds[k]
        if r == 'legs':
            m &= (zr < LEG_TOP)[:, None]
        if m.sum() < 50:
            continue
        mine = [x for x in fsp if x[0] in ks and (r != 'legs' or zr[min(x[4], H) - 1] < LEG_TOP)]
        rec = dict(spikes=dict(n=len(mine), height=max([x[1] for x in mine] or [0.0]),
                               area=round(sum(x[2] for x in mine), 5)))
        pts = [x for x in fpt if x[1] in ks and (r != 'legs' or zr[x[3]] < LEG_TOP)]
        cap = [x[2] for x in pts if x[0] == 'cap']
        bump = [x[2] for x in pts if x[0] == 'bump']
        rec['points'] = dict(n=sum(t >= CAP_DEG for t in cap), turn=max(cap or [0.0]))
        if rgb is not None and r in BANDS:
            rec['band'] = band_edge(rgb, m, ppl, line, keep, band_parts)
        rec['bumps'] = {'out': max([t for t in bump if t > 0] or [0.0]), 'in': max([-t for t in bump if t < 0] or [0.0])}
        if axis is not None and r in MIRROR_FIGURE:
            rec['mirror'] = mirror(m, axis, ppl)
        if view in ('front', 'back') and r in MIRROR_SELF:
            rec['mirror_self'] = mirror(m, mirror_axis(m, ppl), ppl)     # (about its own axis: its shape, not its place)
        out[r] = rec
    return out


# ------------------------------------------------------------------------------------------------------ drawings
WALL_THICK = 0.006          # L: dark runs thinner than this are drawn lines (walls between cells), thicker are colour
ABSORB = 0.02               # L: a wall pixel joins the nearest cell within this
STROKE = 0.08               # a pixel this much darker than its surroundings' closing (luminance) is in a drawn stroke
STROKE_ON = 0.75            # ... on a pale region (its closing brighter than this: skin, cream; on the hair, a darker
                            # stroke is shading, not a line)
STROKE_LEN = 0.02           # L: a stroke this long is a line (a wall); shorter, a dot (a speck)
LUM = np.array([0.3, 0.59, 0.11])


def strokes(rgb, fg, ppl):
    """a drawing's thin dark features on its pale regions: pixels darker by STROKE than the luminance's closing over a
    disk WALL_THICK / 2 + 1 px across, where that closing is over STROKE_ON -> (lines: those in a feature STROKE_LEN or
    longer, dots: the shorter ones)."""
    from scipy import ndimage
    from skimage.morphology import closing, disk
    lum = rgb @ LUM
    r = max(1, int(round(WALL_THICK / 2 * ppl))) + 1
    cl = closing(lum, disk(r))
    th = (cl - lum > STROKE) & (cl > STROKE_ON) & fg
    lab, k = ndimage.label(th, structure=np.ones((3, 3)))
    if not k:
        return th, th
    sl = ndimage.find_objects(lab)
    ext = np.array([0] + [np.hypot(s_[0].stop - s_[0].start, s_[1].stop - s_[1].start) for s_ in sl])
    line = ext >= STROKE_LEN * ppl
    return th & line[lab], th & ~line[lab]


def cells(rgb, fg, ppl):
    """a drawing (sRGB floats, a render or a design sheet) cut into colour cells: the colour families
    (charkit.bodyqa.family) of its figure fg, its drawn lines (dark runs thinner than WALL_THICK, and strokes: strokes())
    and anti-aliasing (pixels of no family) as walls; a cell is a 4-connected run of one family between the walls, and
    each wall pixel joins the nearest cell within ABSORB. -> (cell labels (0: none), the family per cell (index = label),
    lines (the drawn lines with their anti-aliased fringe: the walls less the anti-aliasing between two colours),
    dots (strokes' short features))."""
    from scipy import ndimage
    from . import bodyqa
    fam = np.where(fg, bodyqa.family(rgb), 0)
    dark = fam == bodyqa.CLASS['dark']
    r = max(1, int(round(WALL_THICK / 2 * ppl)))
    thick = ndimage.binary_dilation(ndimage.binary_erosion(dark, iterations=r), iterations=r) & dark
    lines, dots = strokes(rgb, fg, ppl)
    lines = fg & ((dark & ~thick) | lines)
    aa = fg & (fam == bodyqa.CLASS['other'])
    wall = lines | aa
    lines = lines | (aa & ndimage.binary_dilation(lines, iterations=1))      # a line's anti-aliased fringe, not a tone's
    lab = np.zeros(fam.shape, np.int32)
    fams = [0]
    for c in np.unique(fam[fg & ~wall]):
        l, k = ndimage.label(fg & ~wall & (fam == c))
        lab[l > 0] = l[l > 0] + len(fams) - 1
        fams += [int(c)] * k
    d, (iy, ix) = ndimage.distance_transform_edt(lab == 0, return_indices=True)
    take = fg & (lab == 0) & (d <= ABSORB * ppl)
    lab[take] = lab[iy[take], ix[take]]
    return lab, np.array(fams), lines, dots


def vote(lab, votes, names, mixed=0.15):
    """each cell's region by the majority of a vote image under it (an int image of indices into names, -1 none); a
    cell where a second region holds `mixed` of the votes (two regions of one colour with no line between them) is
    split by the votes pixel by pixel. -> {name: mask}."""
    n = lab.max() + 1
    ok = (lab > 0) & (votes >= 0)
    k = len(names)
    tab = np.bincount(lab[ok] * k + votes[ok], minlength=n * k).reshape(n, k)
    tot = tab.sum(1)
    win = np.where(tot > 0, tab.argmax(1), -1)
    win[0] = -1
    second = np.sort(tab, 1)[:, -2] if k > 1 else np.zeros(n)
    split = second >= mixed * np.maximum(tot, 1)
    split[0] = False
    reg = win[lab]
    sp = split[lab] & (votes >= 0)
    reg[sp] = votes[sp]
    return {nm: reg == i for i, nm in enumerate(names)}


def image_tone(rgb, region, wall, blur=0.7, split=0.08, third=0.06, share=0.03):
    """a region's cel tones from a drawing's colours: its luminance off the walls, softened by `blur` px (normalized: the
    walls don't bleed in), cut at Otsu's threshold(s): three tones where a middle class holds `share` of the region and
    each gap is over `third`, two where the classes' means differ by over `split`, else one; walls take the nearest
    tone. -> tone image (0 lit, 1 shade, 2 deep; -1 off the region)."""
    from scipy import ndimage
    from skimage.filters import threshold_multiotsu, threshold_otsu
    own = region & ~ndimage.binary_dilation(wall, iterations=1)      # (a line's darkened fringe is no tone)
    tone = np.full(region.shape, -1, np.int8)
    if own.sum() < 30:
        return tone
    bb = _bbox(region, 4)
    r0, r1, c0, c1 = bb
    o = own[r0:r1, c0:c1].astype(float)
    lum = (rgb[r0:r1, c0:c1] @ LUM) * o
    lum = ndimage.gaussian_filter(lum, blur) / np.maximum(ndimage.gaussian_filter(o, blur), 1e-6)
    x = lum[o > 0]
    cuts = []
    if np.ptp(x) > split:                                # (one flat colour: one tone)
        try:
            t2 = threshold_multiotsu(x, classes=3)
            q = np.digitize(x, t2)
            means = [x[q == i].mean() if (q == i).any() else np.nan for i in range(3)]
            if min((q == i).mean() for i in range(3)) >= share and np.nanmin(np.diff(means)) > third:
                cuts = list(t2)
        except ValueError:
            pass
        if not cuts:
            t = threshold_otsu(x)
            if (x < t).any() and (x >= t).any() and x[x >= t].mean() - x[x < t].mean() > split:
                cuts = [t]
    q = (len(cuts) - np.digitize(lum, cuts)).astype(np.int8)
    sub = tone[r0:r1, c0:c1]
    sub[o > 0] = q[o > 0]
    fill = region[r0:r1, c0:c1] & (o == 0)
    if fill.any():
        _, (iy, ix) = ndimage.distance_transform_edt(o == 0, return_indices=True)
        sub[fill] = sub[iy[fill], ix[fill]]
    return tone


# ------------------------------------------------------------------------------------------------------ our buffers
# our garments by region: object names (charkit.garments' pieces; a name matching a pattern's start)
OBJECTS = {'collar': ('collar',), 'bow': ('bow',), 'top': ('top',), 'skirt': ('skirt',),
           'boots': ('boots', 'shoe_', 'boot_'),          # (boot_L, boot_R: the template since round 5; boot_cuff_*)
           'sleeves': ('sleeve_',), 'flaps': ('overskirt_panel_',), 'band': ('waistband',)}
# the design's garments by region: the outfit graph's piece types (charkit.outfit)
PIECES = {'collar': ('collar',), 'bow': ('bow', 'bow tail'), 'top': ('top', 'bodice panel'),
          'skirt': ('skirt', 'skirt panel'), 'boots': ('boot', 'boot cuff'), 'sleeves': ('sleeve',),
          'flaps': ('overskirt panel',), 'band': ('waistband',)}
KINDS = ('hair', 'skin', 'feature', 'collar', 'bow', 'top', 'skirt', 'boots', 'sleeves', 'flaps', 'band', 'other')


def object_kind(o):
    """what a bundle object is for the regions: hair, skin, feature (eyes, brows, mouth: inside the face), a garment
    region, or other."""
    if o.group == 'hair':
        return 'hair'
    if o.group == 'skin':
        return 'skin'
    if o.group in ('eye', 'mouth'):
        return 'feature'
    if o.group == 'garment':
        for r, pats in OBJECTS.items():
            if any(o.name == p or (p.endswith('_') and o.name.startswith(p)) for p in pats):
                return r
    return 'other'


def kind_image(mesh, surfs):
    """a draw's surface index image (qa3d.draw's aux['mesh'], -1 empty) as indices into KINDS (-1 empty); an outline
    hull is its object's."""
    tab = np.array([KINDS.index(object_kind(s['o'])) for s in surfs] + [-1])
    return tab[np.where(mesh >= 0, mesh, len(surfs))]


def buffer_tone(tone, region, blur=TONE_BLUR):
    """qa3d.draw's tone buffer (0 lit .. 1 shade .. 2 deep, NaN off the toon materials: lines, emissions) as cel tones
    over a region: softened by `blur` px (normalized over the region's toon pixels: a render's pixel filter and a
    drawing's quantization, as image_tone sees a picture), cut at 0.5 and 1.5; pixels off the toon take the nearest
    tone in the region. -> int image, -1 off the region."""
    from scipy import ndimage
    own = region & np.isfinite(tone)
    out = np.full(region.shape, -1, np.int8)
    if not own.any():
        return out
    r0, r1, c0, c1 = _bbox(region, 4)
    o = own[r0:r1, c0:c1].astype(float)
    t = np.where(o > 0, np.nan_to_num(tone[r0:r1, c0:c1]), 0.0)
    if blur:
        t = ndimage.gaussian_filter(t, blur) / np.maximum(ndimage.gaussian_filter(o, blur), 1e-6)
    sub = out[r0:r1, c0:c1]
    q = (t >= 0.5).astype(np.int8) + (t >= 1.5)
    sub[o > 0] = q[o > 0]
    fill = region[r0:r1, c0:c1] & (o == 0)
    if fill.any():
        _, (iy, ix) = ndimage.distance_transform_edt(o == 0, return_indices=True)
        sub[fill] = sub[iy[fill], ix[fill]]
    return out


# ------------------------------------------------------------------------------------------------------ one view
def frame_keep(shape, margin=3):
    """where outline points count: off the picture's edges (a region cut by the frame has a straight edge there)."""
    k = np.zeros(shape, bool)
    k[margin:-margin, margin:-margin] = True
    return k


def view_regions(kinds, chin_row=None, neck_rows=None, line=None, dots=None, ppl=None, regions=REGIONS):
    """a view's region masks from its kinds ({kind: mask}: hair, skin, feature, the garment regions) -> {region: dict(
    mask (the region, for its outline), body (its own pixels, for its tones), inner (body off the drawn lines: the flat
    colour between them, for fragments and slivers), zone (rows it counts in, or None), and for the skin: foreign
    (other surfaces inside it), clear (skin away from the features, for specks), dots (a drawing's short strokes))}.
    The face is the skin above our chin, the neck the skin from the chin down neck_rows; both outlined as the skin with
    the features filled in. line: the drawn lines' pixels (a drawing's walls, our outline hulls)."""
    from scipy import ndimage
    out = {}
    H, W = next(iter(kinds.values())).shape
    rows = np.arange(H)[:, None]
    line = line if line is not None else np.zeros((H, W), bool)
    fg = np.zeros((H, W), bool)
    for m in kinds.values():
        fg |= m
    for r in regions:
        if r in ('face', 'neck'):
            sk = kinds.get('skin')
            if sk is None or chin_row is None or not sk.any():
                continue
            feat = kinds.get('feature')
            feat = feat if feat is not None else np.zeros((H, W), bool)
            filled = ndimage.binary_fill_holes(sk | feat)
            zone = np.broadcast_to((rows < chin_row) if r == 'face' else (rows >= chin_row) & (rows < chin_row + neck_rows),
                                   (H, W))
            holes = filled & ~sk
            near = ndimage.binary_dilation(holes, iterations=max(1, int(round(0.03 * (ppl or 400))))) if holes.any() \
                else holes
            out[r] = dict(mask=filled, body=sk & zone, inner=sk & zone & ~line, zone=zone, foreign=fg & ~sk & ~feat,
                          clear=sk & zone & ~near, dots=None if dots is None else dots & zone & ~near, line=line)
        elif r in kinds and kinds[r].any():
            out[r] = dict(mask=kinds[r], body=kinds[r], inner=kinds[r] & ~line, zone=None, line=line)
    return out


def measure_view(regs, tone_fn, ppl, keep=None, pictures=None, speck_tone_fn=None):
    """the four detectors on a view's regions (view_regions'); tone_fn(body mask) -> its cel tones (speck_tone_fn: the
    tones specks are read from, else the same). -> {region: dict(outline, terminator, fragments, speckle (face and
    neck))}. pictures: a dict to receive each region's outlines, terminators and the islands, fragments, slivers and
    specks found, for the overlays."""
    out = {}
    for r, g in regs.items():
        zk = g['zone']
        k = keep if zk is None else (zk if keep is None else keep & zk)
        tone = tone_fn(g['body'])
        po, pt = [], []
        mk = [] if pictures is not None else None
        rec = dict(outline=outline(g['mask'], ppl, keep=k, parts=po),
                   terminator=terminator(g['body'], tone, ppl, keep=k, parts=pt, line=g['line'], marks=mk))
        rec['fragments'] = fragments(g['inner'], ppl, keep=zk, outline_len=rec_len(po), marks=mk)
        if r in ('face', 'neck'):
            st = speck_tone_fn(g['body']) if speck_tone_fn is not None else tone
            rec['speckle'] = speckle(g['clear'], st, ppl, foreign=g['foreign'], keep=zk, dots=g.get('dots'),
                                     line=g['line'], marks=mk)
        out[r] = rec
        if pictures is not None:
            pictures[r] = dict(outline=po, terminator=pt, marks=mk)
    return out


def rec_len(parts):
    """the kept length (L) of outline parts."""
    return sum(float(h[keep].sum()) for d, keep, h, _, _ in parts)


# ------------------------------------------------------------------------------------------------------ pictures
MARK = {'islands': (1.0, 0.85, 0.1), 'specks': (1.0, 0.85, 0.1), 'fragments': (0.1, 0.85, 0.95),
        'slivers': (1.0, 0.55, 0.1), 'spikes': (0.95, 0.1, 0.55), 'points': (0.55, 0.1, 0.95)}


def overlay(rgb, pics, dim=0.45):
    """a view's detector overlay: the picture dimmed and greyed; each region's outline green with its corners red; its
    terminators blue with their kinks magenta; tone islands and skin specks yellow; fragments cyan; slivers orange.
    rgb (H, W, 3) floats; pics: measure_view's pictures."""
    img = 1 - dim * (1 - np.asarray(rgb, float)[..., :3])
    img = img * 0.55 + 0.45 * img.mean(-1, keepdims=True)
    H, W = img.shape[:2]

    def paint(P, col, cc, j):
        for d, keep, h, p, ck in P:
            q = np.rint(p[keep]).astype(int)
            ok = (q[:, 0] >= 0) & (q[:, 0] < H) & (q[:, 1] >= 0) & (q[:, 1] < W)
            img[q[ok, 0], q[ok, 1]] = col
        for d, keep, h, p, ck in P:
            for r_, c_ in np.rint(p[ck[j]]).astype(int):
                img[max(0, r_ - 2):r_ + 3, max(0, c_ - 2):c_ + 3] = cc
    for g in pics.values():
        for kind, (r0, r1, c0, c1), m in g.get('marks') or ():
            img[r0:r1, c0:c1][m] = MARK[kind]
    for g in pics.values():
        paint(g['outline'], (0.1, 0.65, 0.2), (0.95, 0.1, 0.1), 0)
        paint(g['terminator'], (0.2, 0.35, 0.95), (0.9, 0.1, 0.9), 1)
    return img


# ------------------------------------------------------------------------------------------------------ the part
HEAD_PPL = 400               # the head frame's px per L (the head sheet's own is ~399; the look review's pages 399.4)
HEAD_WIN = (0.85, 1.25, 1.0)    # L round the eye line: half-width, above, below (the hair, the face, the neck zone)
BODY_WIN = (1.6, -0.2, 6.3)     # the body frame from 0.2 L under the eye line to the feet, at the body sheet's scale (from
                                # -0.5 it cut the hull-lofted sleeves' pointed caps off at the neck)
NECK = 0.5                   # L: the neck runs from our chin this far down (as charkit.lookqa's face_shadow)
HEAD_REGIONS = ('hair', 'face', 'neck')
BODY_REGIONS = ('collar', 'bow', 'top', 'skirt', 'boots')
SHAPE_REGIONS = BODY_REGIONS + ('sleeves', 'flaps')      # the silhouettes' regions (SHAPE_CHECKS)
DETECTORS = {                # check -> (detector, its headline measure, the floor under the design's value)
    'outline': ('outline', 'corners', 1.0),          # corners per L of outline
    'terminator': ('terminator', 'kinks', 1.0),      # kinks per L of terminator
    'fragments': ('fragments', 'ragged', 0.0002),    # fragment and sliver area per L of outline (L^2 / L)
    'speckle': ('speckle', 'per_L2', 10.0),          # specks per L^2 of skin
}
PROPOSED = {                 # proposed grades on the worst view's ratio to the design: (pass at or under, warn at or under),
    'outline': (1.5, 2.5),   # set from the calibration (docs/workstreams/artifacts.md): the flagged neck and collar read
    'terminator': (2.0, 2.5),    # 2.2-7.4, clean regions 0.2-0.8; our buffers read hair terminators ~1.8x a render's,
    'fragments': (1.5, 2.5),     # so a render at the design's 1.0 reads ~1.8 here, the flagged hair 2.4-2.9
    'speckle': (1.5, 2.5),
}


def _frame(B, ppl, win):
    from . import lookqa
    return lookqa.HeadFrame(B, ppl=ppl, ss=1, win=win)


def buffers(B, surfs, az, fr, ldir=None):
    """qa3d.draw's buffers without its picture: the surface index per pixel (-1 empty) and the cel tone (0 lit .. 1
    shade .. 2 deep; NaN off the toon and face materials), from azimuth az on frame fr, under the boards' light for the
    view. It mirrors draw() (back faces shaded from their flipped normals, an outline hull's flat normals, the face's SDF
    tone) and skips the colour, textures and pixel filter the detectors don't read."""
    from . import qa3d
    items = [(s_['V'], s_['T'], s_['slots'], s_['cull']) for s_ in surfs]
    zb, lab, mi, ti, bc = fr.zbuffer(items, az, ids=True)
    a = np.radians(az)
    view_d = np.array([-np.sin(a), np.cos(a), 0.0])
    if ldir is None:
        ldir = qa3d.view_light(B, az)
    tone = np.full(mi.shape, np.nan)
    flat = mi.ravel()
    idx = np.nonzero(flat >= 0)[0]
    order = idx[np.argsort(flat[idx], kind='stable')]
    ks, starts = np.unique(flat[order], return_index=True)
    bounds = list(starts[1:]) + [len(order)]
    tflat, bflat = ti.reshape(-1), bc.reshape(-1, 3)
    for k, s0, s1 in zip(ks, starts, bounds):
        s_ = surfs[k]
        if s_['hull']:
            continue                                     # (an outline hull: flat ink, no tone)
        o = s_['o']
        if 'toon' not in s_:                             # (kept on the surface: a frame's views share it)
            s_['toon'] = any((m or {}).get('kind') in ('toon3', 'face')
                             for m in (o.material(int(j))[1] for j in np.unique(s_['slots'])))
        if not s_['toon']:
            continue
        pix = order[s0:s1]
        t, w = tflat[pix], bflat[pix]
        V, T, Tl = s_['V'], s_['T'], s_['Tl']
        fn = np.cross(V[T[t, 1]] - V[T[t, 0]], V[T[t, 2]] - V[T[t, 0]])
        lnor = o.a(s_['variant'], 'lnor')
        if lnor is not None:
            N = (lnor[Tl[t]] * w[:, :, None]).sum(1)
        else:
            if 'vn' not in s_:
                from .geom.mesh import vertex_normals
                s_['vn'] = vertex_normals(V, T)
            N = (s_['vn'][T[t]] * w[:, :, None]).sum(1)
        N = N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
        back = fn @ view_d > 0
        N[back] = -N[back]
        slots = s_['slots'][t]
        tn = np.full(len(t), np.nan)
        for j in np.unique(slots):
            sel = slots == j
            mat = o.material(int(j))[1]
            if mat and mat.get('kind') == 'face':
                _, tn[sel] = qa3d._face(B, o, s_['variant'], mat['shading'], N[sel], view_d, t[sel], w[sel], ldir)
            elif mat and mat.get('kind') == 'toon3':
                _, tn[sel] = qa3d._toon(mat['shading'], N[sel], view_d, ldir)
        tone.reshape(-1)[pix] = tn
    return mi, tone


def _ours_view(B, surfs, fr, az, regions, ppl, line_of, kinds_of, chin_row, pictures=None, view=None, z_of_row=None):
    rgb = None
    if z_of_row is not None:        # (the body frame: drawn whole, for the hem band's texture; its mesh and tone buffers
        from . import qa3d          # are buffers()' to the bit, 2026-09-30)
        aux = {}
        rgb = qa3d.draw(B, surfs, az, fr, ss=1, aux=aux)[..., :3]
        mesh, tone = aux['mesh'], aux['tone']
    else:
        mesh, tone = buffers(B, surfs, az, fr)
    kimg = kinds_of[np.where(mesh >= 0, mesh, len(kinds_of) - 1)]
    kinds = {k: kimg == i for i, k in enumerate(KINDS)}
    line = line_of[np.where(mesh >= 0, mesh, len(line_of) - 1)]
    regs = view_regions(kinds, chin_row, NECK * ppl, line=line, ppl=ppl, regions=regions)
    P = {} if pictures is not None else None
    M = measure_view(regs, lambda body: buffer_tone(tone, body), ppl, keep=frame_keep(mesh.shape), pictures=P,
                     speck_tone_fn=lambda body: buffer_tone(tone, body, blur=0))     # (a render keeps a pixel's speck)
    fk = frame_keep(mesh.shape)
    for r, rec in M.items():
        kind = 'skin' if r in ('face', 'neck') else r
        if rec.get('fragments') is not None and kind in KINDS:
            ids = [i for i in range(len(surfs)) if kinds_of[i] == KINDS.index(kind) and not line_of[i]]
            zone = regs[r]['zone']
            rec['fragments']['peeks'] = peeks(mesh, surfs, ids, ppl, fk if zone is None else fk & zone)
    if z_of_row is not None:
        mk = [] if pictures is not None else None
        bp = [] if pictures is not None else None
        for r, rec in shape_view(kinds, mesh >= 0, ppl, view, z_of_row, keep=fk, marks=mk, rgb=rgb, line=line,
                                 band_parts=bp).items():
            M.setdefault(r, {}).update(rec)
        if mk or bp:
            P['_shapes'] = dict(outline=[], terminator=bp or [], marks=mk)
    if pictures is not None:
        pictures.append((flat_picture(kimg, tone, line), P))
    return M


PALETTE = {'hair': (0.84, 0.47, 0.33), 'skin': (0.98, 0.86, 0.80), 'feature': (0.55, 0.45, 0.40),
           'collar': (0.96, 0.90, 0.72), 'bow': (0.93, 0.86, 0.66), 'top': (0.80, 0.42, 0.30),
           'skirt': (0.75, 0.38, 0.28), 'boots': (0.95, 0.95, 0.95), 'sleeves': (0.84, 0.44, 0.32),
           'flaps': (0.86, 0.50, 0.30), 'band': (0.30, 0.22, 0.20), 'other': (0.70, 0.70, 0.72)}


def flat_picture(kimg, tone, line):
    """a buffer view as a flat picture for the overlays: each kind's colour, darkened by its cel tone, the lines ink."""
    pal = np.array([PALETTE[k] for k in KINDS] + [(0.97, 0.97, 0.97)])
    img = pal[np.where(kimg >= 0, kimg, len(KINDS))]
    img = img * (1 - 0.22 * np.rint(np.clip(np.nan_to_num(tone), 0, 2)))[..., None]
    img[line] = (0.15, 0.08, 0.07)
    return img


def ours(B, az3=35.5, body_ppl=None, body_page=1440, pictures=None):
    """our regions measured on the QA's own numpy drawings (buffers(): qa3d.draw's mesh and tone buffers, as the boards
    light each view): the head frame at HEAD_PPL (hair, face, neck) and, given body_ppl (the body sheet's), the body
    frame (collar, bow, top, skirt, boots). -> {'head': {view: {region: measures}}, 'body': ...}."""
    from . import lookqa
    L = float(B.assembly['L'])
    chin_L = float(B.assembly['chin']) / L
    views = {'front': 0.0, 'three_quarter': az3, 'profile': 90.0, 'back': 180.0}
    out = {}
    frames = [('head', HEAD_PPL, HEAD_WIN, HEAD_REGIONS)]
    if body_ppl:
        frames.append(('body', body_ppl, BODY_WIN, BODY_REGIONS))
    for name, ppl, win, regions in frames:
        fr = _frame(B, ppl, win)
        page = int(round((win[1] + win[2]) * ppl)) if name == 'head' else body_page
        surfs = lookqa._scene(B, skin_outline=True, line_scale=lookqa.line_scale(B, ppl, page))
        kinds_of = np.array([KINDS.index(object_kind(s['o'])) for s in surfs] + [-1])
        line_of = np.array([bool(s['hull']) for s in surfs] + [False])
        chin_row = (win[1] + chin_L) * ppl if name == 'head' else None
        zr = None if name == 'head' else (lambda r, ppl=ppl, top=win[1]: top - (r + 0.5) / ppl)
        out[name] = {}
        for v, az in views.items():
            pics = [] if pictures is not None else None
            out[name][v] = _ours_view(B, surfs, fr, az, regions, ppl, line_of, kinds_of, chin_row, pics, v, zr)
            if pictures is not None:
                pictures.append((name, v, ppl) + pics[0])
    return out


def _figure(rgb, fg=None):
    from scipy import ndimage
    if fg is None:
        bg = np.median(np.concatenate([rgb[:4].reshape(-1, 3), rgb[:, :4].reshape(-1, 3)]), 0)
        fg = np.abs(rgb - bg).sum(-1) > 0.08
    return ndimage.binary_fill_holes(ndimage.binary_opening(fg, iterations=1))


def drawing_kinds(rgb, fg, ppl, votes=None, whole=None):
    """a drawing's kinds (the design's, or a render of ours) from its cells: by a vote image (indices into KINDS, e.g.
    our numpy labels under a render of the same build), else by colour (orange hair, skin and cream skin, every other
    cell but a yellow one taking the kind of the cells round it; what is left is a feature). -> (kinds, lines, dots)."""
    from scipy import ndimage
    from . import bodyqa
    lab, fams, lines, dots = cells(rgb, fg, ppl)
    if votes is not None:
        if whole is not None:                   # (and by a second vote image, each cell whole by its majority: the
            return (vote(lab, votes, KINDS), vote(lab, whole, KINDS, mixed=2.0)), lines, dots      # silhouettes')
        return vote(lab, votes, KINDS), lines, dots
    C = bodyqa.CLASS
    ck = np.full(len(fams), -1)
    ck[np.isin(fams, [C['orange'], C['hair']])] = KINDS.index('hair')
    ck[np.isin(fams, [C['skin'], C['cream']])] = KINDS.index('skin')
    ck[0] = -1
    for _ in range(2):
        k = np.where(lab > 0, ck[lab], -1)
        todo = [c for c in np.nonzero((ck < 0) & (fams != C['iris']))[0] if c > 0]
        if not todo:
            break
        sl = ndimage.find_objects(lab)
        for c in todo:
            s0, s1 = sl[c - 1]
            s0 = slice(max(0, s0.start - 3), s0.stop + 3)
            s1 = slice(max(0, s1.start - 3), s1.stop + 3)
            m = lab[s0, s1] == c
            ring = ndimage.binary_dilation(m, iterations=2) & ~m
            v = k[s0, s1][ring]
            v = v[v >= 0]
            if len(v) and np.bincount(v).max() > 0.6 * len(v):
                ck[c] = int(np.bincount(v).argmax())
    k = np.where(lab > 0, ck[lab], -1)
    kinds = {nm: k == i for i, nm in enumerate(KINDS)}
    kinds['feature'] = fg & (k < 0)
    return kinds, lines, dots


def drawing_view(rgb, fg, ppl, chin_row=None, regions=REGIONS, votes=None, pictures=None, view=None, z_of_row=None,
                 shape_votes=None):
    """the four detectors on a drawing (the design's view, a render), and given z_of_row (rows -> L from the eye line)
    the silhouette detectors (shape_view) on the kinds shape_votes gives whole cells (else votes') -> {region: measures}."""
    whole = None if z_of_row is None or votes is None else (votes if shape_votes is None else shape_votes)
    kinds, lines, dots = drawing_kinds(rgb, fg, ppl, votes, whole=whole)
    kinds, wkinds = kinds if whole is not None else (kinds, kinds)
    regs = view_regions(kinds, chin_row, NECK * ppl, line=lines, dots=dots, ppl=ppl, regions=regions)
    keep = frame_keep(rgb.shape[:2])
    M = measure_view(regs, lambda body: image_tone(rgb, body, lines), ppl, keep=keep, pictures=pictures)
    if z_of_row is not None:
        # the silhouettes from whole cells: a cell two same-coloured pieces share goes to its majority, not split along
        # the outfit masks' rough edge (0.77-0.85 IoU: a split sliver of the jacket read as a 0.45 L sleeve spike)
        for r, rec in shape_view(wkinds, fg, ppl, view, z_of_row, keep=keep, rgb=rgb, line=lines).items():
            M.setdefault(r, {}).update(rec)
    return M


def design_heads(rgb, eye_x, facing, ppl=HEAD_PPL):
    """the head sheet's views measured (hair, face, neck) at ppl, each cut round its head; the face and neck split at the
    sheet's own drawn chin (charkit.refcheck.measure_heads: the profile's). -> ({view: {region: measures}}, chin (L
    under the eye line))."""
    from . import refcheck
    rgb0, _ = refcheck.without_guides(np.asarray(rgb, float))
    rgb1, f, H = refcheck.at_scale(rgb0, eye_x, 2 * eye_x * ppl, facing)
    _, chin = refcheck.measure_heads(rgb1, H['heads'], ppl, facing)
    chin_L = -float(chin) if chin is not None else 0.36
    out = {}
    for view, h in H['heads'].items():
        if view not in VIEWS:
            continue
        x0, y0, x1, y1 = h['box']
        pad = 6
        y0, x0 = max(0, y0 - pad), max(0, x0 - pad)
        y1, x1 = min(rgb1.shape[0], y1 + pad), min(rgb1.shape[1], x1 + pad)
        crop = rgb1[y0:y1, x0:x1]
        fg = _figure(crop, h['_mask'][y0:y1, x0:x1])
        out[view] = drawing_view(crop, fg, ppl, h['eye_y'] - y0 + chin_L * ppl, HEAD_REGIONS)
    return out, round(chin_L, 4)


def design_body(views, masks, graph, ppl):
    """the body sheet's views measured (collar, bow, top, skirt, boots): each view's cells voted by the outfit's piece
    masks (a region's piece types: PIECES), its hair and skin cells by colour -> {view: {region: measures}}."""
    from . import bodyqa
    types = {p['id']: p.get('type') for p in graph['pieces']}
    out = {}
    for view, dv in views.items():
        rgb, fg = np.asarray(dv['rgb'], float), dv['fg']
        votes = np.full(fg.shape, -1, int)
        fam = bodyqa.family(rgb)
        votes[fg & (fam == bodyqa.CLASS['skin'])] = KINDS.index('skin')
        votes[fg & (dv['cls'] == bodyqa.CLASS['hair'])] = KINDS.index('hair')
        shape = votes.copy()
        skin = fam == bodyqa.CLASS['skin']
        for r in PIECES:
            for pid, t in types.items():
                m = masks.get('%s__%s' % (view, pid))
                if m is not None and t in PIECES[r]:
                    if r in BODY_REGIONS:           # (the four detectors' regions voted as calibrated, 2026-09-29)
                        votes[m & fg] = KINDS.index(r)
                    shape[m & fg & ~skin] = KINDS.index(r)      # (a piece's mask spilling onto the arm isn't the piece)
        top = float((dv.get('win') or bodyqa.WIN)['top'])
        out[view] = drawing_view(rgb, fg, ppl, None, BODY_REGIONS, votes=votes, view=view,
                                 z_of_row=lambda r: top - (r + 0.5) / ppl, shape_votes=shape)
    return out


def _value(rec, det):
    """a region's headline value for a check (None when it can't be measured)."""
    d, key, _ = DETECTORS[det]
    x = (rec or {}).get(d)
    if not x:
        return None
    if det == 'fragments':
        return round((x['area'] + x['sliver_area']) / max(x['len'], 1e-9), 6)
    if det == 'terminator' and x.get('len', 0) < 0.05:
        return None                                    # (no terminator to speak of: one tone)
    return x.get(key)


def grade(ratio, det):
    p, w = PROPOSED[det]
    return 'PASS' if ratio <= p else 'WARN' if ratio <= w else 'FAIL'


PEEKS = (4, 12)              # proposed grades on a region's peeking bits in its worst view (ours only): pass at or under,
                             # warn at or under (one build's numbers: look_v5's hair read 10-24)

# Michael's flags on shapes, graded against the design in the same view (the calibration: docs/workstreams/artifacts.md)
SHAPE_CHECKS = {             # check -> (measure, key, how it's compared, the design's floor, (pass, warn), regions)
    'spikes': ('spikes', 'height', 'excess', 0.0, (0.015, 0.025), SHAPE_REGIONS),      # L: the tallest spike's
    'points': ('points', 'turn', 'excess', CAP_MIN, (20.0, 30.0), SHAPE_REGIONS),      # deg: the sharpest cap's
    'bumps': ('bumps', 'out', 'excess', BUMP_MIN, (20.0, 30.0), SHAPE_REGIONS + ('legs',)),  # deg: the sharpest knob's
    'mirror': ('mirror', 'asym', 'ratio', 0.02, (1.5, 2.5), ('waist',)),                # 1 - IoU with its mirror image
    'mirror_self': ('mirror_self', 'asym', 'ratio', 0.02, (1.5, 2.5), ('boots',)),     # (about its own axis)
    'band': ('band', 'kinks', 'ratio', 1.0, (1.5, 2.0), ('lower',)),                   # the hem band's edge kinks per L
}


def shape_checks(ours_m, design_m):
    """the silhouette checks (SHAPE_CHECKS): per view ours, the design's and ours beyond it (an excess in the measure's
    unit, or a ratio to the design's, the design's floored), the worst view's as the value; INFO, with the proposed
    grade -> {check: dict}. A view where the design's own reading is high (a junction the drawing's cells can't part)
    can't fail there: the worst view is what's graded."""
    C = {}
    for name, (meas, key, how, floor, (p, w), regions) in SHAPE_CHECKS.items():
        for r in regions:
            get = lambda M, v: ((((M.get('body') or {}).get(v) or {}).get(r) or {}).get(meas) or {}).get(key)
            o = {v: get(ours_m, v) for v in VIEWS}
            d = {v: get(design_m, v) for v in VIEWS}
            by = {}
            for v in VIEWS:
                if o[v] is None or d[v] is None:
                    continue
                by[v] = round(max(0.0, o[v] - max(d[v], floor)), 4) if how == 'excess' else \
                    round(o[v] / max(d[v], floor), 3)
            if not by:
                continue
            worst = max(by, key=by.get)
            v = by[worst]
            C['%s_%s' % (name, r)] = {'value': v, 'worst': worst, 'per_view': {k: x for k, x in o.items() if x is not None},
                                      'design': {k: x for k, x in d.items() if x is not None}, how: by,
                                      'status': 'INFO', 'grade': 'PASS' if v <= p else 'WARN' if v <= w else 'FAIL'}
    return C


def checks(ours_m, design_m):
    """per detector and region: ours, the design's and their ratio per view (the design's value floored:
    DETECTORS), the worst view's ratio as the value; INFO, with the proposed grade beside it -> {check: dict}."""
    C = {}
    for det in DETECTORS:
        for frame, regions in (('head', HEAD_REGIONS), ('body', BODY_REGIONS)):
            for r in regions:
                if det == 'speckle' and r not in ('face', 'neck'):
                    continue
                o = {v: _value((ours_m.get(frame, {}).get(v) or {}).get(r), det) for v in VIEWS}
                d = {v: _value((design_m.get(frame, {}).get(v) or {}).get(r), det) for v in VIEWS}
                ratio = {v: round(o[v] / max(d[v], DETECTORS[det][2]), 3) for v in VIEWS
                         if o[v] is not None and d[v] is not None}
                if not ratio:
                    if any(x is not None for x in o.values()):
                        C['%s_%s' % (det, r)] = {'status': 'INFO', 'value': None, 'per_view': o,
                                                 'why': 'no design view to compare with'}
                    continue
                worst = max(ratio, key=ratio.get)
                C['%s_%s' % (det, r)] = {'value': ratio[worst], 'worst': worst, 'per_view': o, 'design': d,
                                         'ratio': ratio, 'status': 'INFO', 'grade': grade(ratio[worst], det)}
    for frame, regions in (('head', HEAD_REGIONS), ('body', BODY_REGIONS)):
        for r in regions:
            if r in ('face', 'neck'):
                continue
            o = {v: ((ours_m.get(frame, {}).get(v) or {}).get(r) or {}).get('fragments') for v in VIEWS}
            o = {v: x['peeks'] for v, x in o.items() if x and 'peeks' in x}
            if o:
                w = max(o, key=o.get)
                C['peeks_%s' % r] = {'value': o[w], 'worst': w, 'per_view': o, 'status': 'INFO',
                                     'grade': 'PASS' if o[w] <= PEEKS[0] else 'WARN' if o[w] <= PEEKS[1] else 'FAIL',
                                     'note': 'small visible bits of the region\'s own pieces (no design ratio: the '
                                             'drawing has no pieces)'}
    C.update(shape_checks(ours_m, design_m))
    return C


DESIGN_FILE = 'artifacts_design.json'     # the design's measures, stored beside the spec's manifest (design())
EYE_X_TOL = 0.02            # the stored design serves a build whose eye spacing (which scales the sheets) is within 2%


def _sha(path):
    import hashlib
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()[:16]


def _mask_paths(spec):
    """the produced outfit masks and the outfit graph beside them (charkit.bodymeasure.piece_masks' paths, without
    loading the masks) or None."""
    import os
    from . import manifest, qa3d
    ref = spec.get('ref') if isinstance(spec.get('ref'), dict) else {}
    if not ref.get('manifest'):
        return None
    r = manifest.load(ref['manifest'])['references'].get('outfit_masks')
    if not r:
        return None
    p = qa3d._path(r['path'])
    g = os.path.join(os.path.dirname(p), 'outfit_graph.json')
    return (p, g) if os.path.exists(p) and os.path.exists(g) else None


def _piece_types(graph_path):
    """what design_body reads of the outfit graph: each piece's id and type, as a digest. The produced graph's other
    contents (spring chains, the comparison with the spec's hand list) differ between copies and specs while the masks
    stay bit-identical (2026-09-30: one mask file, three graphs, on the laptop and two box copies), so the whole file's
    hash made every build on the box re-measure the design (~20 s, +6% CPU on clawd_body)."""
    import json
    from . import cache
    G = json.load(open(graph_path))
    return cache.digest(sorted((str(p['id']), str(p.get('type'))) for p in G.get('pieces', ())))[:16]


def design_code():
    """the design side's code as a digest: this module's functions design_heads and design_body run (cache.code_units)
    and the values of the constants they read, not the module's other top-level lines (the grades' limits, the notes:
    changing those doesn't change the design's measures)."""
    import types
    from . import cache
    g = globals()
    units = {k: v for k, v in cache.code_units(design_heads, design_body).items()
             if k.startswith('charkit/artifactqa.py:') and not k.endswith(':<top>')}
    names = set()

    def walk(co):
        names.update(co.co_names)
        for c in co.co_consts:
            if isinstance(c, types.CodeType):
                walk(c)
    defaults = {}
    for k in units:
        f = g.get(k.split(':', 1)[1])
        if hasattr(f, '__code__'):
            walk(f.__code__)
            defaults[k] = repr((f.__defaults__, f.__kwdefaults__))      # (a default's value: arc=CORNER_ARC)
    consts = {n: repr(g[n]) for n in sorted(names) if n in g and n.isupper()}
    return cache.digest([sorted(units.items()), sorted(consts.items()), sorted(defaults.items())])[:16]


def design_inputs(B, design):
    """what the design's measures are made from: the head and body sheets, the outfit's piece masks (their bytes: the
    body sheet's cells are voted by them) and the graph's piece types (which piece is which region), the eye spacing
    that scales the sheets, and the design side's code -> (stamp, inputs, the stored file's path) or (None, why, None)."""
    import os
    from . import cache, qa3d
    ref = design.ref()
    fs, bs = ref.get('face_sheet'), ref.get('body_sheet')
    man = ref.get('manifest')
    if not fs or not bs:
        return None, 'the spec names no face_sheet and body_sheet', None
    mp = _mask_paths(B.spec)
    if mp is None:
        return None, 'no outfit masks produced for this spec', None
    inp = dict(face_sheet=_sha(qa3d._path(fs['image'])), face_facing=fs.get('facing', -1),
               body_sheet=_sha(qa3d._path(bs['image'])), masks=_sha(mp[0]), pieces=_piece_types(mp[1]),
               head_ppl=HEAD_PPL, code=design_code())
    path = os.path.join(os.path.dirname(qa3d._path(man)), DESIGN_FILE) if man else None
    stamp = cache.digest(sorted(inp.items()))[:16]
    inp['eye_x'] = round(float(B.assembly['eye_knobs']['x']), 6)        # (the sheets' scale: within EYE_X_TOL, not stamped)
    return stamp, inp, path


def design_compute(B, design):
    """the design's measures made (slow: the sheets cut and measured, ~20 s) -> dict(head, body, chin)."""
    from . import bodymeasure
    ref = design.ref()
    fs = ref['face_sheet']
    head, chin = design.memo(design_heads, design.rgba(fs['image'])[..., :3], B.assembly['eye_knobs']['x'],
                             fs.get('facing', -1))
    ctx = design.sheet_context()
    masks, graph, paths = bodymeasure.piece_masks(B.spec)
    dv = design.design_views()
    views = {v: dict(rgb=x['rgb'], fg=x['fg'], cls=x['cls'], win=x.get('win')) for v, x in dv.items()}
    body = design.memo(design_body, views, masks, graph, ctx['ppl'])
    return dict(head=head, body=body, chin=chin, body_ppl=round(float(ctx['ppl']), 3))


def _records(S):
    """the stored design file's records (one per stamp: the specs' outfit masks differ) -> [record]."""
    return list(S.get('records') or ([S] if S.get('stamp') else []))


def design_measures(B, design):
    """the design's measures: the stored ones (DESIGN_FILE: a record per stamp) when one matches, else from the shared
    cache or made here (with a note to store them: `python -m charkit.artifactqa design BUNDLE`) -> (dict(head, body,
    ...), note or None)."""
    import json, os
    stamp, inp, path = design_inputs(B, design)
    if stamp is None:
        return {}, inp
    if path and os.path.exists(path):
        design._rec(path)
        recs = _records(json.load(open(path)))
        for S in recs:
            ex = (S.get('inputs') or {}).get('eye_x') or 0
            if S.get('stamp') == stamp and ex and abs(ex / inp['eye_x'] - 1) <= EYE_X_TOL:
                return S, None
        S = recs[0] if recs else {}
        ex = (S.get('inputs') or {}).get('eye_x') or 0
        why = 'the stored design measures are stale (%s changed): made here, ~20 s; store them with ' \
              '`python -m charkit.artifactqa design BUNDLE`' % ', '.join(
                  k for k in inp if (S.get('inputs') or {}).get(k) != inp[k] and k != 'eye_x' or
                  k == 'eye_x' and (not ex or abs(ex / inp['eye_x'] - 1) > EYE_X_TOL))
    else:
        why = 'no stored design measures (%s): made here, ~20 s; store them with `python -m charkit.artifactqa design ' \
              'BUNDLE`' % DESIGN_FILE
    D, hit = _shared_design(stamp, inp, lambda: design_compute(B, design))
    return D, why.replace('made here, ~20 s', 'taken from the shared cache (made here once)') if hit else why


SHARED_KEEP = 30            # stale-stamp design measures kept in the shared cache (newest first)


def _shared_design(stamp, inp, make):
    """the design's measures for a stamp the tracked file doesn't hold, from the produced references' shared cache
    (charkit.manifest.cache_root(): CHARKIT_PRODUCED_CACHE, per user, so a box's gate clones share it), else made and
    stored there: a branch whose outfit masks differ from the tracked stamp's measures the design once per machine, not
    once per build. -> (measures, from the cache?)"""
    import glob, json, os
    from . import manifest
    root = manifest.cache_root()
    if not root:
        return make(), False
    d = os.path.join(root, 'artifacts_design')
    p = os.path.join(d, '%s-%.4f.json' % (stamp, inp['eye_x']))
    for q in [p] + sorted(glob.glob(os.path.join(d, stamp + '-*.json'))):
        try:
            S = json.load(open(q))
        except (OSError, ValueError):
            continue
        ex = (S.get('inputs') or {}).get('eye_x') or 0
        if S.get('stamp') == stamp and ex and abs(ex / inp['eye_x'] - 1) <= EYE_X_TOL:
            os.utime(q)
            return S, True
    D = make()
    try:
        os.makedirs(d, exist_ok=True)
        with open(p + '.%d.tmp' % os.getpid(), 'w') as f:
            json.dump(dict(stamp=stamp, inputs=inp, **D), f, default=float)
        os.replace(p + '.%d.tmp' % os.getpid(), p)
        for old in sorted(glob.glob(os.path.join(d, '*.json')), key=os.path.getmtime)[:-SHARED_KEEP]:
            os.remove(old)
    except OSError:
        pass
    return D, False


STORE_KEEP = 4              # records kept in the stored file (a spec's masks each; the newest first)


def store_design(bdir):
    """python -m charkit.artifactqa design BUNDLE_DIR: the design's measures made and stored beside the spec's manifest
    (DESIGN_FILE, tracked: a build reads them instead of re-measuring the sheets), as the record for this bundle's
    stamp; records made from other sheets or design-side code are dropped, other specs' (their masks) kept."""
    import json, os, platform, time
    from . import bundle as bundlelib, qa3d
    B = bundlelib.load(bdir)
    design = qa3d.Design(B)
    stamp, inp, path = design_inputs(B, design)
    if stamp is None:
        raise SystemExit('artifactqa design: %s' % inp)
    D = design_compute(B, design)
    rec = dict(stamp=stamp, inputs=inp, made=time.strftime('%Y-%m-%d'), where=platform.machine(),
               spec=B.spec.get('name'), **D)
    same = ('face_sheet', 'face_facing', 'body_sheet', 'head_ppl', 'code')
    old = _records(json.load(open(path))) if os.path.exists(path) else []
    keep = [r for r in old if r.get('stamp') != stamp and all((r.get('inputs') or {}).get(k) == inp[k] for k in same)]
    S = dict(note='the design turnarounds measured by charkit.artifactqa (head sheet at %d px/L, body sheet at its own '
                  'scale), a record per stamp (the outfit masks differ between specs); refresh with python -m '
                  'charkit.artifactqa design BUNDLE_DIR (a bundle of each spec)' % HEAD_PPL,
             records=[rec] + keep[:STORE_KEEP - 1])
    json.dump(S, open(path, 'w'), indent=1, default=float)
    print('artifactqa design: stored', path, 'stamp', stamp, '(%d records)' % len(S['records']))
    return path


def measure(B, design=None, out=None):
    """the artifact part: ours on the QA's numpy drawings, the design's turnarounds measured the same way (stored:
    design_measures), graded as ratios -> (table, checks)."""
    D, note = design_measures(B, design) if design is not None else ({}, 'no design')
    ctx = design.sheet_context() if design is not None else {'why': 'no design'}
    body_ppl = None if 'why' in ctx else ctx['ppl']
    az3 = 35.5 if 'why' in ctx else ctx['az3']
    pics = [] if out else None
    O = ours(B, az3, body_ppl if D.get('body') else None,
             body_page=(ctx['rgb'].shape[0] if 'rgb' in ctx else 1440), pictures=pics)
    C = checks(O, D)
    if note:
        C['design'] = {'status': 'INFO' if D else 'SKIPPED', 'why': note}
    if out and pics:
        save_overlays(out, pics)
    return {'ours': O, 'design': {k: D.get(k) for k in ('head', 'body', 'chin', 'stamp', 'made')},
            'frames': {'head': dict(ppl=HEAD_PPL, win=HEAD_WIN), 'body': dict(ppl=body_ppl, win=BODY_WIN)}}, C


def save_overlays(out, pics, name='qa_artifacts.png'):
    """the head views in a row over the body views in a row, each the detector overlay (overlay())."""
    import os
    from . import qa3d
    rows = {}
    for frame, v, ppl, px, P in pics:
        if P:
            rows.setdefault(frame, []).append(overlay(px, P))
    strips = []
    for frame in ('head', 'body'):
        if frame in rows:
            ims = rows[frame]
            h = max(i.shape[0] for i in ims)
            strips.append(np.concatenate([np.pad(i, ((0, h - i.shape[0]), (0, 6), (0, 0)), constant_values=1.0)
                                          for i in ims], 1))
    if not strips:
        return
    w = max(s.shape[1] for s in strips)
    img = np.concatenate([np.pad(s, ((0, 6), (0, w - s.shape[1]), (0, 0)), constant_values=1.0) for s in strips], 0)
    qa3d._save_rgb(os.path.join(out, name), img)


if __name__ == '__main__':
    import sys
    from charkit import artifactqa as _self             # (the module by its name: the stamp keys on its code units)
    if len(sys.argv) > 2 and sys.argv[1] == 'design':
        _self.store_design(sys.argv[2])
    else:
        print(_self.store_design.__doc__)
