"""A multi-segment garment's parts and the lines drawn inside them (Michael, 2026-09-30; tool/pieceref,
docs/workstreams/pieceref.md): the bow as its knot and two lobes (its tails are pieces of their own). "The knot has
never been defined and the lobes read as pillows": nothing measured the lines inside the bow, the knot's outline and
rectangle and the crease across each lobe. Here each part has its own shape check, and its inner lines their own.

In context (the turnaround, the QA's grids, registered on the eyes as every piece check is): ours is our z-buffer with
the bow split into its parts (split: the bow mesh's connected parts, or a separate 'bow_knot' object), the design's
the outfit's part masks (outfit.PARTS: VIEW__bow.knot|lobe_L|lobe_R, cut by the drawn cells). The inner lines are read
from pictures with lines: the design's own lines (its class image's ink and its fainter strokes, design_lines), ours drawn with the build's outlines
(lookqa's frame at the design's line scale, the bow's surfaces split by part).

The measures take masks alone, so the isolated-piece checks (charkit.isoqa: the piece alone against garment_breakdown
and the close-ups) use them too:
  knot_rect(knot, ppl)                the knot's height over width and its fill of its box (a rectangle fills ~0.9, an
                                      ellipse 0.79)
  outline_share(region, line, other)  the share of a region's edge against `other` that has a line between (the knot
                                      against the lobes)
  crease(lobe, line, ppl, side)       the lines inside a lobe (its filled silhouette less a band inside its edge): their
                                      length over the lobe's width, their direction (degrees from the horizontal,
                                      outward and up +) and centre (u: 0 at the knot's end .. 1 at the outer end; v: 0
                                      top .. 1 bottom)

Checks (qa3d part 'bow_parts'; flagged: the gate blocks on their regressions):
  bow_part_knot_iou, bow_part_lobe_iou   per view the part's outline agreement (bodymeasure.iou_tol) with the drawn
                                         part, the worst view (and lobe); the lobes' a guard, not a flag check (the
                                         pillow lobes are sized to the drawn ones and pass it); the knot graded on the
                                         front only (GRADED: the turnaround's three-quarter knot is drawn face-on),
                                         its other views reported ('info')
  bow_part_knot_line                     the knot's outlined share against the lobes, the design's less ours (front)
  bow_part_knot_rect                     the knot's rectangle (front): the larger of |ours / design - 1| of its height
                                         over width and its fill of its box short of the design's over FILL_SPAN
  bow_part_crease_len                    each lobe's crease length over its width, |ours / design - 1|, the worse lobe
                                         (front; none drawn in ours: 1)
  bow_part_crease_dir                    each lobe's crease direction, ours less the design's (degrees), the worse lobe
                                         (front; no crease: no reading, FAIL)

    table, checks = partqa.measure(B, design)      # charkit.qa3d's 'bow_parts' part
"""
import math

import numpy as np

from .registry import FLAG as FLAG_KEY, flag_check, qa_part

from . import bodyqa

CODES = {'knot': 6001, 'lobe_L': 6002, 'lobe_R': 6003, 'tail_L': 6004, 'tail_R': 6005}
PARTS = ('knot', 'lobe_L', 'lobe_R')
VIEWS = ('front', 'three_quarter', 'profile')
MIN_PX = 60                         # a drawn part this small in a view (grid px) is not graded there
# the views each part's shape is graded in (the rest reported, INFO). The knot on the front only (coordinator, round 4,
# the canonical view rule's step 3; Michael may overrule): the turnaround draws its three-quarter knot face-on (ours
# z-buffered at other azimuths matches it only at 15-20 deg against the sheet's 35.5: harness azfit.py), and in
# profile it is a sliver within the loops; there the knot's line (bow_part_knot_line) and its seating carry the intent
GRADED = {'knot': ('front',)}
EDGE_BAND = 0.018                   # L: lines this close inside a lobe's silhouette are its outline, not its crease
CREASE_MIN = 0.02                   # L: less crease than this (skeleton length) reads as none
LINE_PPL = 400                      # px per L of the pictures with lines (the head frame's, the design's line scale)
LINE_WIN = (0.7, -0.3, 1.1)         # L round the eye line: the chest frame the bow is drawn in
LIMITS = {                          # (pass, warn): at least for iou, within for the rest
    'iou': (0.6, 0.45),
    'knot_line': (0.15, 0.3),       # the design's outlined share less ours
    'knot_rect': (0.15, 0.3),       # |ours / design - 1| of the knot's height over width
    'crease_len': (0.35, 0.6),      # |ours / design - 1| of a lobe's crease length over its width
    'crease_dir': (12.0, 25.0),     # degrees
}
FLAG = ("the bow's knot has never been defined and its lobes read as pillows: each part its own shape, the knot's "
        "outline and rectangle, the crease across each lobe (Michael 2026-09-30)")


def grade(key, v):
    p, w = LIMITS[key]
    if key == 'iou':
        return 'PASS' if v >= p else 'WARN' if v >= w else 'FAIL'
    return 'PASS' if v <= p else 'WARN' if v <= w else 'FAIL'


def _check(key, v, **kw):
    c = dict(value=None if v is None else round(float(v), 4), status='FAIL' if v is None else grade(key, v), **kw)
    return flag_check(c, FLAG)


# ------------------------------------------------------------------------------------------------------------ ours
def split(V, T):
    """the bow mesh's triangles by part: its connected parts, the two that reach lowest its tails, of the rest the one
    nearest the midline its knot, the others its lobes by side (world x +: her left). -> per-triangle codes (CODES), or
    None when it has fewer than three parts."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    V, T = np.asarray(V), np.asarray(T)
    n = len(V)
    r = np.concatenate([T[:, 0], T[:, 1], T[:, 2]])
    c = np.concatenate([T[:, 1], T[:, 2], T[:, 0]])
    k, lab = connected_components(coo_matrix((np.ones(len(r)), (r, c)), shape=(n, n)), directed=False)
    parts = [j for j in range(k) if (lab == j).sum() >= 3]
    if len(parts) < 3:
        return None
    low = {j: float(V[lab == j][:, 2].min()) for j in parts}
    mx = {j: float(V[lab == j][:, 0].mean()) for j in parts}
    tails = sorted(parts, key=lambda j: low[j])[:2] if len(parts) >= 5 else []
    rest = [j for j in parts if j not in tails]
    knot = min(rest, key=lambda j: abs(mx[j]) + float(np.ptp(V[lab == j][:, 0])))
    code = {}
    for j in parts:
        if j in tails:
            code[j] = CODES['tail_L' if mx[j] >= 0 else 'tail_R']
        elif j == knot:
            code[j] = CODES['knot']
        else:
            code[j] = CODES['lobe_L' if mx[j] >= 0 else 'lobe_R']
    tl = lab[T[:, 0]]
    return np.array([code.get(j, CODES['knot']) for j in tl])


def tri_codes(name, V, T):
    """a scene object's per-triangle part codes: the bow split, a separate knot object all knot; else None."""
    if name == 'bow':
        return split(V, T)
    if name == 'bow_knot':
        return np.full(len(T), CODES['knot'])
    return None


def grid_labels(B, ppl, az3, views=VIEWS):
    """our objects z-buffered on the design's grids (pieceqa.our_labels' labels) with the bow's parts coded (CODES).
    -> {view: label image}, or None without a bow of three parts."""
    from . import qa3d
    from .faceqa import zbuffer
    meshes, names = qa3d.scene_objects(B)
    obj, got = [], False
    for i, (V, T, _) in enumerate(meshes):
        code = np.where(V[T].mean(1)[:, 0] >= 0, i, i + 1000)
        tc = tri_codes(names[i], V, T)
        if tc is not None:
            code, got = tc, True
        obj.append((V, T, code))
    if not got:
        return None
    As = B.assembly
    iw = np.array(qa3d.iris_centres(B))
    az = bodyqa.azimuths(az3)
    return {v: zbuffer(obj, az[v], bodyqa.origin(v, az[v], iw, As['centre']), As['L'], 1.0 / ppl, bodyqa.WIN)[1]
            for v in views}


def split_surfs(surfs):
    """lookqa's surfaces with the bow's (and its outline hull's) split by part: each gets 'part' (a CODES value, 0 for
    other objects)."""
    out = []
    for s in surfs:
        tc = tri_codes(s['o'].name, s['V'], s['T'])
        if tc is None:
            out.append(dict(s, part=0))
            continue
        nt = len(s['T'])
        for c in np.unique(tc):
            m = tc == c
            d = dict(s, part=int(c))
            for k, x in s.items():
                if k not in ('V', 'o') and isinstance(x, np.ndarray) and x.ndim and len(x) == nt:
                    d[k] = x[m]
            out.append(d)
    return out


def line_picture(B, az, ppl_design, win=LINE_WIN, ppl=LINE_PPL, only=None):
    """ours drawn with the build's outlines (lookqa's frame, the design's line scale), the bow's surfaces by part ->
    dict(part (CODES or 0 per pixel, lines excluded), line (an outline pixel), name (object per pixel), fr)."""
    from . import artifactqa, lookqa
    fr = lookqa.HeadFrame(B, ppl=ppl, ss=1, win=win)
    surfs = split_surfs(lookqa._scene(B, skin_outline=True, line_scale=lookqa.line_scale(B, ppl_design, 1440)))
    if only is not None:
        surfs = [s for s in surfs if s['o'].name in only]
    mesh, _ = artifactqa.buffers(B, surfs, az, fr)
    idx = np.where(mesh >= 0, mesh, len(surfs))
    nm = np.array([s['o'].name for s in surfs] + [''])
    hull = np.array([bool(s['hull']) for s in surfs] + [False])
    pc = np.array([s['part'] for s in surfs] + [0])
    line = hull[idx]
    return dict(part=np.where(line, 0, pc[idx]), line=line, name=nm[idx], fr=fr)


# ------------------------------------------------------------------------------------------------------------ measures
def _touch(a, b):
    t = np.zeros_like(a)
    t[1:] |= b[:-1]
    t[:-1] |= b[1:]
    t[:, 1:] |= b[:, :-1]
    t[:, :-1] |= b[:, 1:]
    return a & t


def knot_rect(knot, ppl):
    """the knot's height over width and its fill of its bounding box -> dict or None."""
    ys, xs = np.nonzero(knot)
    if len(ys) < 10:
        return None
    h, w = np.ptp(ys) + 1, np.ptp(xs) + 1
    return dict(aspect=round(float(h / w), 3), fill=round(float(len(ys) / (h * w)), 3), w=round(w / ppl, 4),
                h=round(h / ppl, 4))


FILL_SPAN = 1 - math.pi / 4          # a box's fill of its box (1) less an ellipse's (0.785)


def rect_err(ko, kd):
    """the knot's rectangle against the design's (knot_rect's): max(|aspect ratio - 1|, fill short / FILL_SPAN)."""
    if not ko or not kd:
        return None
    return max(abs(ko['aspect'] / kd['aspect'] - 1), max(0.0, kd['fill'] - ko['fill']) / FILL_SPAN)


def outline_share(region, line, other, reach=2):
    """the share of region's edge facing `other` that has a line between: region pixels within `reach` px of other and
    4-touching a line pixel, over those plus the ones 4-touching other directly. -> share or None."""
    from scipy import ndimage
    if not region.any() or not other.any():
        return None
    near = region & ndimage.binary_dilation(other, iterations=reach + 1)
    lined = _touch(near, line) & ~_touch(near, other)
    direct = _touch(region, other)
    n = int(lined.sum() + direct.sum())
    return None if n == 0 else float(lined.sum()) / n


def _skel_len(m, ppl):
    from skimage.morphology import skeletonize
    return float(skeletonize(m).sum()) / ppl if m.any() else 0.0


def crease(lobe, line, ppl, side, band=EDGE_BAND, close=0.012, band_px=None):
    """the lines drawn inside a lobe: its silhouette (the lobe's mask closed over its own lines and filled) less a band
    `band` L inside its edge (or band_px pixels: a picture at an unknown scale); the line pixels there. side 'L' (the picture's right: outward is +x) or 'R'.
    -> dict(len (their skeleton's length over the lobe's width), dir (degrees from the horizontal, outward and up +),
    u, v (their centre across the lobe: u 0 at the knot's end .. 1 at the outer end, v 0 top .. 1 bottom), px) or None
    when the lobe is too small."""
    from scipy import ndimage
    from . import pieceqa as pq
    if lobe.sum() < 30:
        return None
    F = ndimage.binary_fill_holes(ndimage.binary_closing(lobe | (line & ndimage.binary_dilation(lobe, iterations=3)),
                                                         structure=pq.disk(max(1, int(round(close * ppl))))))
    inner = ndimage.distance_transform_edt(F) > (band * ppl if band_px is None else band_px)
    L_ = line & inner
    ys, xs = np.nonzero(F)
    w = (np.ptp(xs) + 1) / ppl
    out = dict(px=int(L_.sum()), width=round(w, 4))
    ln = _skel_len(L_, ppl)
    out['len'] = round(ln / w, 3) if w else 0.0
    if ln < CREASE_MIN:
        out.update(dir=None, u=None, v=None)
        return out
    ly, lx = np.nonzero(L_)
    sgn = 1 if side == 'L' else -1
    P = np.c_[sgn * (lx - lx.mean()), -(ly - ly.mean())]
    wv, U = np.linalg.eigh(np.cov(P.T))
    a = U[:, 1]
    if a[0] < 0:
        a = -a
    out['dir'] = round(math.degrees(math.atan2(a[1], a[0])), 1)
    x0, x1 = xs.min(), xs.max()
    u = (lx.mean() - x0) / max(1, x1 - x0)
    out['u'] = round(float(u if side == 'L' else 1 - u), 3)
    out['v'] = round(float((ly.mean() - ys.min()) / max(1, np.ptp(ys))), 3)
    return out


def line_width(line):
    """a line mask's typical width (px): twice the median distance to its edge along its skeleton."""
    from scipy import ndimage
    from skimage.morphology import skeletonize
    if not line.any():
        return 0.0
    d = ndimage.distance_transform_edt(line)
    sk = skeletonize(line)
    return 2.0 * float(np.median(d[sk])) if sk.any() else 1.0


def part_measures(knot, lobes, line, ppl, band_px=None, reach=2):
    """the knot's rectangle and outlined share and each lobe's crease on one picture's masks (lobes {'L', 'R'}); reach:
    outline_share's (px: a picture's lines wider than 2 px, the gap between its cells wider too)."""
    other = lobes.get('L', np.zeros_like(knot)) | lobes.get('R', np.zeros_like(knot))
    return dict(knot=knot_rect(knot, ppl), knot_line=outline_share(knot, line, other, reach=reach),
                crease={s: crease(m, line, ppl, s, band_px=band_px) for s, m in lobes.items()})


def design_lines(dvv, sh=None):
    """a design view's drawn lines: its ink (the class image's line pixels) and its fainter drawn strokes (outfit.ridges:
    the lobes' creases are drawn in a shade, not in ink), skin left out, as outfit.cells walls its cells."""
    from . import outfit
    raw = dvv['raw']
    m = raw == bodyqa.CLASS['line']
    if dvv.get('rgb') is not None:
        m = m | (outfit.ridges(dvv['rgb']) & (raw != bodyqa.CLASS['skin']))
    return m if sh is None else _fit(m, sh)


# ------------------------------------------------------------------------------------------------------------ the part
@qa_part('bow_parts', order=1772, table='bow_parts')
def bow_parts(B, design=None, out=None):
    """the bow's parts (knot, lobes) against the drawn parts, and the lines drawn inside them (Michael, 2026-09-30)."""
    return measure(B, design)


def _fit(m, sh):
    o = np.zeros(sh, bool)
    if m is not None:
        h, w = min(sh[0], m.shape[0]), min(sh[1], m.shape[1])
        o[:h, :w] = m[:h, :w]
    return o


def measure(B, design):
    """the checks on a bundle against the design (qa3d.Design) -> (table, checks)."""
    from . import bodymeasure, pieceqa as pq
    ctx = design.sheet_context()
    if 'why' in ctx:
        return None, {'bow_parts': {'status': 'SKIPPED', 'why': ctx['why']}}
    got = bodymeasure.piece_masks(B.spec)
    if got is None:
        return None, {'bow_parts': {'status': 'SKIPPED', 'why': 'no outfit_masks produced for this spec'}}
    masks, graph, paths = got
    if not any(k.endswith('__bow.knot') for k in masks):
        return None, {'bow_parts': {'status': 'SKIPPED', 'why': "the outfit masks have no bow parts (outfit.PARTS)"}}
    for p in paths:
        design._rec(p)
    ppl = ctx['ppl']
    dv = design.design_views()
    O = grid_labels(B, ppl, ctx['az3'], [v for v in VIEWS if v in dv])
    tol = bodymeasure.OUTLINE_TOL * ppl
    T, C = {'iou': {}}, {}
    worst = {'knot': None, 'lobe': None}
    for v in VIEWS:
        if v not in dv:
            continue
        sh = dv[v]['cls'].shape
        for part in PARTS:
            d = pq.clean(_fit(masks.get('%s__bow.%s' % (v, part)), sh), ppl)
            if d.sum() < MIN_PX:
                continue
            o = (O[v] == CODES[part]) if O is not None else np.zeros(sh, bool)
            o = pq.clean(o, ppl) if o.any() else o
            x = bodymeasure.iou_tol(o, d, tol)
            T['iou'].setdefault(v, {})[part] = round(x, 3)
            k = 'knot' if part == 'knot' else 'lobe'
            if v not in GRADED.get(part, VIEWS):
                continue
            if worst[k] is None or x < worst[k][0]:
                worst[k] = (x, v, part)
    for k in ('knot', 'lobe'):
        w = worst[k]
        c = _check('iou', None if w is None else w[0], worst=None if w is None else w[1:],
                                          views=T['iou'],
                                          note="the bow's %s against the drawn part (outfit's VIEW__bow.PART), per "
                                               "view its outline agreement (bodymeasure.iou_tol); the worst view%s" % (
                                                   'knot' if k == 'knot' else 'lobes', k == 'lobe' and ' and lobe' or ''))
        if k == 'knot':
            info = {v: T['iou'][v]['knot'] for v in T['iou'] if 'knot' in T['iou'][v] and v not in GRADED['knot']}
            c['info'] = info
            c['note'] += ('; graded on %s only: the other views reported (INFO: %s), the turnaround drawing its '
                          'three-quarter knot face-on (view-dependent; ours matches it only turned 15-20 deg against the '
                          "sheet's 35.5) and in profile a sliver in the loops, where the knot's line and its seating "
                          'carry the intent' % ('/'.join(GRADED['knot']), info))
        if k == 'lobe':                     # a guard, not a flag check: the pillow lobes read 0.70-0.72 (PASS) too
            c.pop(FLAG_KEY, None)
            c['note'] += ' (a guard, not a flag check: the lobes are sized to the drawn ones, the pillows pass it)'
        C['bow_part_%s_iou' % k] = c
    # the inner lines, in front: the design's ink against ours drawn with lines
    if 'front' in dv:
        sh = dv['front']['cls'].shape
        dline = design_lines(dv['front'], sh)
        D = part_measures(_fit(masks.get('front__bow.knot'), sh),
                          {'L': _fit(masks.get('front__bow.lobe_L'), sh), 'R': _fit(masks.get('front__bow.lobe_R'), sh)},
                          dline, ppl)
        pic = line_picture(B, 0.0, ppl)
        P = pic['part']
        # (the knot's outline share reaching the line's width: the build's outlines are 3-5 px at LINE_PPL, and an
        # outlined knot read None at 2 px, no knot pixel near a lobe's)
        Om = part_measures(P == CODES['knot'], {'L': P == CODES['lobe_L'], 'R': P == CODES['lobe_R']}, pic['line'],
                           LINE_PPL, reach=max(2, int(np.ceil(line_width(pic['line'])))))
        T['lines'] = dict(ours=Om, design=D)
        kl_o, kl_d = Om['knot_line'], D['knot_line']
        C['bow_part_knot_line'] = _check('knot_line', None if kl_o is None or kl_d is None else max(0.0, kl_d - kl_o),
                                         ours=kl_o and round(kl_o, 3), design=kl_d and round(kl_d, 3),
                                         note="the knot's edge against the lobes with a line between (front): its "
                                              "share, the design's less ours")
        ko, kd = Om['knot'], D['knot']
        C['bow_part_knot_rect'] = _check('knot_rect', rect_err(ko, kd), ours=ko, design=kd,
                                         note="the knot's rectangle (front): the larger of |ours / design's - 1| of its "
                                              "height over width and its fill of its box short of the design's, over "
                                              "a rectangle's lead on an ellipse (%.3f)" % FILL_SPAN)
        lens, dirs = {}, {}
        for s in ('L', 'R'):
            co, cd = Om['crease'].get(s), D['crease'].get(s)
            if not cd or not cd.get('len'):
                continue
            lens[s] = 1.0 if not co else abs(co['len'] / cd['len'] - 1)
            dirs[s] = None if not co or co.get('dir') is None or cd.get('dir') is None else abs(co['dir'] - cd['dir'])
        C['bow_part_crease_len'] = _check('crease_len', max(lens.values()) if lens else None, per_side=lens,
                                          ours={s: (Om['crease'].get(s) or {}).get('len') for s in 'LR'},
                                          design={s: (D['crease'].get(s) or {}).get('len') for s in 'LR'},
                                          note="each lobe's crease (the lines inside it, %.3f L in from its edge): "
                                               "their length over the lobe's width, |ours / design's - 1|, the worse "
                                               "lobe (front)" % EDGE_BAND)
        dv_ = [x for x in dirs.values()]
        C['bow_part_crease_dir'] = _check('crease_dir', None if not dv_ or any(x is None for x in dv_) else max(dv_),
                                          per_side=dirs,
                                          ours={s: (Om['crease'].get(s) or {}).get('dir') for s in 'LR'},
                                          design={s: (D['crease'].get(s) or {}).get('dir') for s in 'LR'},
                                          note="each lobe's crease direction (degrees from the horizontal, outward "
                                               "and up +), ours less the design's, the worse lobe (front); no crease "
                                               "in ours: no reading")
    return T, C
