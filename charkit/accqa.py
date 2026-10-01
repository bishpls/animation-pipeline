"""Hair accessories (the clips charkit.accessories builds: a star, a crab, ...) against the design, clip by clip and view by
view, and the QA's accessory class (bodyqa.CLASS 'accessory': a clip is neither hair nor iris on either side).

The design's clips: the outfit graph's 'hair accessory' pieces that the hair doesn't carry (not the buns), each found in a
sheet view by a colour-plus-region rule: every pixel of the head window takes the nearest (CIELAB) of the clips' colours
(the graph's) and the view's own hair, skin and paper tones, dark pixels are line; a clip is its colour's components
above the eye line, clear of the eyes, grouped round the largest, closed over the lines inside it and holes filled, with
the outline's inner half (the QA's convention: lines are absorbed into what they bound). Sheets: the head turnaround
(sheets.face, ~400 px/L; graded) and the body turnaround (sheets.body, the bodyqa grids at ~212 px/L; the reclassing, and
its measures as information).

Ours: the build's accessory objects z-buffered on the same grids (faceqa.zbuffer at the design's scale, the origin on the
eyes as bodyqa.origin puts it), everything else drawn as an occluder, so a clip reads what shows of it.

Per clip and view (acc_KIND_VIEW_*):
  iou      silhouette IoU after aligning position (centroids) and scale (areas): the shape alone
  size     sqrt(area) in L, ours / design
  pos      the centroid's offset from the design's, L (x from the view's origin: the eyes' middle, the profile's near eye;
           z from the eye line); dx, dz kept
  angle    the principal axis' angle from the vertical (second moments), ours - design, degrees mod 180; INFO when either
           shape is too round to have an axis
  shown    what shows of it where the design hides it (the back), or hidden where the design shows it
  visible  the share of our clip's own silhouette (drawn alone) that shows with everything else drawn (Michael's
           non-occlusion rule, 2026-09-30: pieces don't hide each other; "the crab being hidden under the star is poor
           design"); `covered_by` names what covers the rest. A declared check (DECLARED_CHECKS, charkit.declared's
           family 'visible'), measured in the views the design draws the clip
iou, size, pos and angle compare ours as the drawing shows the clip (as_drawn(), tool/accessories5): the drawing layers
the clips over each other (the crab's body over the star's left arm, the star over the crab's right claw), so a drawn
clip is only its part the other drawn clips leave; ours, aligned on the drawn clip, has the same cover taken out before
it is measured. A clip nothing covers in the drawing measures as before.
Per clip (3D): acc_KIND_seat, the gap between the clip's back and the hair surface under it (L; - = sunk into the hair:
each vertex's height over the hair under it along the clip's thin axis, the least),
and acc_KIND_pos3d, the design's clip triangulated from its front, three-quarter and profile centroids against ours.
Per clip, face-on (its own facing; the clips-alone sheet `hair_clips_layers`' bottom row is the structure authority,
head_turnaround the proportions', layerrefs.md): acc_star_arms and acc_star_minor, the star's side arms and its four
minor points over its height (arms()) against head_turnaround's unoccluded readings (STAR_ARMS); acc_KIND_alone (INFO),
our clip face-on against the clips-alone drawing (shape IoU: the structure, its proportions the sheet's own).

The QA part `accessories` (order 2400) runs it in every QA pass; its steps are in charkit/steps/accqa.py.
"""
import json, os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACCESSORY = 5                          # bodyqa.CLASS['accessory']
WIN = dict(x=0.85, top=1.0, bottom=-0.35)     # the head window round a view's eye origin, L
VIEWS = ('front', 'three_quarter', 'profile', 'back')
PIECE = {'star': 'pin_star', 'crab': 'pin_crab'}   # a spec accessory's kind -> its outfit graph piece (else its 'piece')
MAX_DE = 30.0                          # CIELAB distance: a pixel further than this from every reference is unclassed
DARK_V = 0.42                          # max channel: a line
GROUP_L = 0.12                         # L: a clip's components within this of its largest belong to it
EYE_CLEAR = 0.09                       # L: components centred this close to an eye are the eye
MIN_AREA_L2 = 0.0006                   # L^2: a component smaller than this is noise (about 0.025 L square)
LIMITS = {                             # (pass within, warn within); else fail. Calibrated on the design against itself
    # (round 2, before any fit: the body turnaround's clips, an independent drawing, as 'ours' against the head
    # turnaround's): its worst iou 0.736 (the crab's profile), size 1.064, pos 0.033 L (the star's profile), angle 6.5 deg
    # all pass; the 3ebc3fb placeholders fail 26 of the 30 graded (docs/workstreams/accessories.md, Round 2)
    'iou': (0.72, 0.60),               # higher is better
    'size': (0.12, 0.25),              # |ours / design - 1|
    'pos': (0.035, 0.06),              # L
    'angle': (10.0, 20.0),             # degrees
    'seat': (0.006, 0.015),            # |gap| L
    'pos3d': (0.04, 0.08),             # L
}
ROUND = 1.15                           # principal axes' ratio under which a shape has no orientation (angle INFO)
MIN_PX = 40                            # a mask this small (either side) is not graded
# the star's proportions face-on (arms(): each arm's reach from the centroid over the height tip to tip), from
# head_turnaround where the clips-alone sheet disagrees (layerrefs.md section 6; Michael, 2026-10-01): the side arm the
# drawn star's longer (unoccluded) one, front / three-quarter / profile 0.361 / 0.393 / 0.400 (the left is under the drawn
# crab: 0.25-0.33), the minor points the four diagonals' 0.302 / 0.316 / 0.315; the clips-alone sheet's star reads side
# 0.482, minor 0.280 (an equal-armed compass star). (target: the views' mean, pass within, warn within)
STAR_ARMS = {'side': (0.385, 0.03, 0.06), 'minor': (0.311, 0.03, 0.06)}
DECLARED_CHECKS = [
    # Michael's non-occlusion rule (2026-09-30, tool/accessories5): each clip's share that shows. Calibrated as a defect
    # detector: the drawn clips standing for ours (each its drawn mask, the other drawn clips moved 1-2 px against it)
    # pass; the round-4 build (the star bent over the crab) fails
    dict(check='acc_crab_{view}_visible', family='visible', piece='pin_crab', part='accessories',
         views=['front', 'three_quarter', 'profile'], limits=[0.97, 0.90], better='higher',
         note="the share of our crab's own silhouette (drawn alone) that shows (Michael: pieces don't hide each other)",
         calibrate=dict(known_bad='acc_r4_overlap', kind='defect', probes=['touching'], shape=['acc_crab_shape'])),
    dict(check='acc_star_{view}_visible', family='visible', piece='pin_star', part='accessories',
         views=['front', 'three_quarter', 'profile'], limits=[0.97, 0.90], better='higher',
         note="the share of our star's own silhouette (drawn alone) that shows (Michael: pieces don't hide each other)",
         calibrate=dict(no_known_bad='no build hides the star: its floor is the drawing with the crab moved 0.05 L '
                                     'onto the star, over it (star_under_crab)', kind='defect',
                       baseline=['star_under_crab'], probes=['touching'], shape=['acc_star_shape'])),
    # Michael on the crab (2026-10-01, tool/accessories6): "Legs on the current version are too short, and... all on the
    # bottom of the crab, not actually on the sides. Also the pinchers are solid circles." Our crab face-on in its own
    # frame (the FACE view: accqa.face_masks) against the clips-alone sheet's crab (the structure authority), read by
    # charkit.limbs (family 'limbs'). Calibrated as defect detectors: the sheet's crab moved 1-2 px passes; pipeline-3d
    # 25ff0f25's crab (round 5's, A3) fails every one; each floor is the sheet's crab with that one part spoiled
    dict(check='acc_crab_legs', family='limbs', piece='pin_crab', part='accessories', views=['face'],
         params=dict(measure='count'), limits=[0, 0], flag="the crab's legs (Michael, 2026-10-01)",
         note="the crab face-on: its legs per side against the clips-alone sheet's (3), the larger difference",
         calibrate=dict(known_bad='acc_a3_crab', kind='defect', baseline=['legless'], shape=['acc_crab_shape'])),
    dict(check='acc_crab_leg_reach', family='limbs', piece='pin_crab', part='accessories', views=['face'],
         params=dict(measure='reach'), limits=[0.2, 0.35], flag="the crab's legs (Michael, 2026-10-01)",
         note="the crab face-on: its legs' reach off the body over the body's width, |ours / sheet's - 1|",
         calibrate=dict(known_bad='acc_a3_crab', kind='defect', baseline=['short_legs'], shape=['acc_crab_shape'])),
    dict(check='acc_crab_leg_width', family='limbs', piece='pin_crab', part='accessories', views=['face'],
         params=dict(measure='width'), limits=[0.2, 0.35], flag="the crab's legs (Michael, 2026-10-01)",
         note="the crab face-on: its legs' width over the body's (twice the median depth along each leg's medial line), "
              "|ours / sheet's - 1|: the sheet's sausage legs, not sticks",
         calibrate=dict(known_bad='acc_a3_crab', kind='defect', baseline=['thin_legs'], shape=['acc_crab_shape'])),
    dict(check='acc_crab_leg_roots', family='limbs', piece='pin_crab', part='accessories', views=['face'],
         params=dict(measure='root'), limits=[12.0, 25.0], flag="the crab's legs (Michael, 2026-10-01)",
         note="the crab face-on: where its legs leave the body (the elliptical angle on the body, 0 at the side, - "
              "below), their mean against the sheet's, degrees: the sides, not the bottom",
         calibrate=dict(known_bad='acc_a3_crab', kind='defect', baseline=['bottom_legs'], shape=['acc_crab_shape'])),
    dict(check='acc_crab_claw_fingers', family='limbs', piece='pin_crab', part='accessories', views=['face'],
         params=dict(measure='fingers'), limits=[0, 0], flag="the crab's pincers (Michael, 2026-10-01)",
         note="the crab face-on: each claw's fingers (1 + its notches deeper than 0.12 of its size) against the "
              "sheet's (2 each), the larger difference",
         calibrate=dict(known_bad='acc_a3_crab', kind='defect', baseline=['solid_claws'], shape=['acc_crab_shape'])),
    dict(check='acc_crab_claw_notch', family='limbs', piece='pin_crab', part='accessories', views=['face'],
         params=dict(measure='notch'), limits=[0.06, 0.1], flag="the crab's pincers (Michael, 2026-10-01)",
         note="the crab face-on: the claws' deepest notch over their size (sqrt area), |ours - sheet's|",
         calibrate=dict(known_bad='acc_a3_crab', kind='defect', baseline=['solid_claws'], shape=['acc_crab_shape'])),
    dict(check='acc_crab_stalks', family='limbs', piece='pin_crab', part='accessories', views=['face'],
         params=dict(measure='stalks'), limits=[0.25, 0.5],
         note="the crab face-on: its eye stalks' reach above the body over its width, |ours / sheet's - 1| (one "
              "missing reads 1)",
         calibrate=dict(known_bad='acc_a3_crab', kind='defect', baseline=['no_stalks'], shape=['acc_crab_shape'])),
    # the crab against the star (Michael 2026-10-01, tool/accessories6: the crab moved under the star's lower tip; "a
    # moved piece keeps its relations, not its absolute drawn angle"): per view, ours each drawn alone against the drawn
    # pair (family 'pair'). Calibrated: the drawn clips standing for ours pass; the round-5 build (A3, the crab under the
    # star's lower tip, turned with it) fails the bearing and the turn; floors move or turn the drawn crab
    dict(check='acc_crab_{view}_bearing', family='pair', piece=['pin_star', 'pin_crab'], part='accessories',
         views=['front', 'three_quarter', 'profile'], params=dict(measure='bearing'), limits=[30.0, 55.0],
         flag="the crab's place against the star (Michael, 2026-10-01)",
         note="the direction from the star's centroid to the crab's (each drawn alone) against the drawn pair's, "
              "degrees: where the crab sits round the star",
         calibrate=dict(known_bad='acc_a3_crab', kind='defect', baseline=['orbit'], shape=['acc_crab_shape'])),
    dict(check='acc_crab_{view}_gap', family='pair', piece=['pin_star', 'pin_crab'], part='accessories',
         views=['front', 'three_quarter', 'profile'], params=dict(measure='gap'), limits=[0.025, 0.05],
         note="the clear distance between the crab and the star (each drawn alone) past the drawn pair's, L: the pair "
              "kept together",
         calibrate=dict(no_known_bad='no build parts the clips: its floor is the drawn crab moved off the star',
                        kind='defect', baseline=['apart'], shape=['acc_crab_shape'])),
    dict(check='acc_crab_{view}_turn', family='pair', piece=['pin_star', 'pin_crab'], part='accessories',
         views=['front', 'three_quarter', 'profile'], params=dict(measure='turn'), limits=[25.0, 45.0],
         flag="the crab's turn against the star (Michael, 2026-10-01)",
         note="the crab's own axis (toward its claws) less the bearing from the star, against the drawn pair's, "
              "degrees: the crab turned against the star as drawn (the target turns as the crab moves round it)",
         calibrate=dict(known_bad='acc_a3_crab', kind='defect', baseline=['pointing_away'], shape=['acc_crab_shape'])),
    dict(check='acc_crab_{view}_flow', family='pair', piece=['pin_star', 'pin_crab'], part='accessories',
         views=['front', 'three_quarter', 'profile'], params=dict(measure='flow'), limits=[25.0, 45.0],
         note="the crab's own axis less the hair's flow under it (our hair's strands), against the drawn crab's (the "
              "flow under the drawn crab), degrees: the crab along the hair as drawn",
         calibrate=dict(no_known_bad="round 5's crab keeps the drawn crab's turn against the hair: its floor is the "
                                     "drawn crab turned across the flow", kind='defect', baseline=['across_flow'],
                        shape=['acc_crab_shape'])),
]
# the drawn crab's own up (toward its claws) in each view's picture, degrees (0 the picture's right, 90 up): 90 + the
# roll of the crab template fitted to the drawn crab in that view (charkit.accfit's template fit, tool/accessories6:
# charkit/out/acc6/opt_crab3: rolls -1.9 / -14.2 / -2.2; the drawing hides its right claw under the star, so its
# axis is the template's)
CRAB_AXIS = {'front': 88.1, 'three_quarter': 75.8, 'profile': 87.8}
FACE = 'face'                          # the clips-alone sheet's straight-on drawing as a view of the declared checks
FACE_SHEET = 'clips_alone'             # (the stand-in's labels() sheet name for it)


# ------------------------------------------------------------------------------------------------------------ helpers
def lab(rgb):
    from .paletteqa import srgb_to_lab
    return srgb_to_lab(np.clip(rgb, 0, 1))


def _grade(key, v):
    p, w = LIMITS[key]
    if key == 'iou':
        return 'PASS' if v >= p else 'WARN' if v >= w else 'FAIL'
    return 'PASS' if abs(v) <= p else 'WARN' if abs(v) <= w else 'FAIL'


def _disk(r):
    y, x = np.mgrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r + 0.5


def crop(a, eye, ppl, win=WIN, fill=0):
    """the window round an eye point (x, y px) of a sheet at ppl: row 0 at win.top L above the eye line, column 0 at
    -win.x L; the grid faceqa.zbuffer draws at pix = 1 / ppl round the same origin."""
    Wd = int(round(2 * win['x'] * ppl)); Hd = int(round((win['top'] - win['bottom']) * ppl))
    x0 = int(round(eye[0] - win['x'] * ppl)); y0 = int(round(eye[1] - win['top'] * ppl))
    out = np.full((Hd, Wd) + a.shape[2:], fill, a.dtype)
    H, W = a.shape[:2]
    sx0, sy0, sx1, sy1 = max(0, x0), max(0, y0), min(W, x0 + Wd), min(H, y0 + Hd)
    if sx1 > sx0 and sy1 > sy0:
        out[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = a[sy0:sy1, sx0:sx1]
    return out


def grid_uz(shape, ppl, win=WIN):
    """a window grid's pixel centres as (u (W,), z (H,)) in L from the origin."""
    H, W = shape
    return (np.arange(W) + 0.5) / ppl - win['x'], win['top'] - (np.arange(H) + 0.5) / ppl


# ------------------------------------------------------------------------------------------------------ the design's
def clip_pieces(graph):
    """the graph's clips: 'hair accessory' pieces the hair doesn't carry (a bun's pair is the hair's)
    -> {piece id: dict(srgb, side, name)}."""
    out = {}
    for p in (graph or {}).get('pieces', []):
        if p.get('type') != 'hair accessory' or p.get('pair') == 'bun' or p['id'].startswith('bun'):
            continue
        out[p['id']] = dict(srgb=np.array(p['colour']['srgb'], float), side=p.get('side'), name=p.get('name'))
    return out


def _tones(rgb, m):
    """a region's lit and shade tones (the darker third's median, the rest's), or []."""
    px = rgb[m]
    if len(px) < 20:
        return []
    L_ = lab(px)[:, 0]
    lo = L_ < np.percentile(L_, 33)
    if lo.sum() < 5 or (~lo).sum() < 5:                      # (one flat tone)
        return [np.median(px, 0)]
    return [np.median(px[~lo], 0), np.median(px[lo], 0)]


def _nearest(rgb, refs):
    """each pixel's nearest reference (CIELAB) and its distance -> (index (H, W), distance (H, W))."""
    d = np.sqrt(((lab(rgb)[:, :, None, :] - lab(np.array(refs))[None, None]) ** 2).sum(-1))
    near = np.argmin(d, -1)
    return near, np.take_along_axis(d, near[..., None], -1)[..., 0]


def _classify(rgb, dark, clip_refs, others):
    """per pixel: the clip (0..n-1) whose colour (one or a list of tones per clip) is nearest among the clips' and the
    others' references, else -1."""
    refs, owner = [], []
    for k, r in enumerate(clip_refs):
        r = np.atleast_2d(r)
        refs += list(r); owner += [k] * len(r)
    near, best = _nearest(rgb, refs + list(others))
    owner = np.array(owner + [-1] * len(others))
    return np.where((best < MAX_DE) & ~dark, owner[near], -1)


def transfer(m, ppl_src, shape, ppl, shift=(0.0, 0.0), win=WIN):
    """a window mask at ppl_src resampled onto another window grid (shape, ppl) by L, moved by shift (du, dz) L."""
    from scipy import ndimage
    u, z = grid_uz(shape, ppl, win)
    Z, U = np.meshgrid(z - shift[1], u - shift[0], indexing='ij')
    r = (win['top'] - Z) * ppl_src - 0.5
    c = (U + win['x']) * ppl_src - 0.5
    return ndimage.map_coordinates(m.astype(float), [r, c], order=1, mode='constant', cval=0.0) >= 0.5


def design_clips(rgb, ppl, pieces, eyes_uv=(), win=WIN, prior=None):
    """the clips in one sheet view's head window (crop()'s grid): rgb the window's pixels, pieces clip_pieces()'s,
    eyes_uv the drawn eyes' (u, z) in L (their components are the eyes, not a clip); prior {piece: mask on this grid}
    (another sheet's clip, registered: transfer()): a cell mostly inside it is the clip's whatever its colour (a
    small sheet's crab drawn closer to the hair's tone than its seeds' is). -> ({piece: bool mask}, info).

    Two passes: the graph's colours find each clip's seed pixels; the seeds' own median colour (the drawing's, which a
    rig-measured colour only approximates) then classes every pixel again, and each region between the drawn lines
    (a cell) takes the clip most of its pixels are nearest to, when that is most of them."""
    from scipy import ndimage
    from .bodyqa import CLASS, family
    H, W = rgb.shape[:2]
    u, z = grid_uz((H, W), ppl, win)
    Z, U = np.meshgrid(z, u, indexing='ij')
    dark = rgb.max(-1) < DARK_V
    fam = family(rgb)
    others = []
    for c in (CLASS['orange'], CLASS['skin'], CLASS['white']):
        others += _tones(rgb, (fam == c) & ~dark)
    others.append(np.median(np.concatenate([rgb[:3].reshape(-1, 3), rgb[:, :3].reshape(-1, 3),
                                            rgb[:, -3:].reshape(-1, 3)]), 0))           # the paper
    ids = list(pieces)
    min_area = MIN_AREA_L2 * ppl * ppl
    lw = max(1, int(round(0.004 * ppl)))                     # half a drawn line, px
    border = np.zeros((H, W), bool); border[[0, -1], :] = True; border[:, [0, -1]] = True

    def group(m):
        """the clip's components: above the eye line, clear of the eyes and the window's edge (a neighbouring
        figure's clip), within GROUP_L of the largest -> mask or None."""
        lb, n = ndimage.label(m)
        if not n:
            return None
        idx = np.arange(1, n + 1)
        area = ndimage.sum(np.ones_like(lb), lb, idx)
        cu = ndimage.mean(U, lb, idx); cz = ndimage.mean(Z, lb, idx)
        edge = ndimage.maximum(border, lb, idx) > 0
        ok = (cz > -0.05) & ~edge
        for eu, ez in eyes_uv:
            ok &= np.hypot(cu - eu, cz - ez) > EYE_CLEAR
        if not ok.any():
            return None
        big = idx[ok][np.argmax(area[ok])]
        if area[big - 1] < min_area:
            return None
        reach = ndimage.distance_transform_edt(lb != big) / ppl
        keep = [i for i in idx[ok] if reach[lb == i].min() <= GROUP_L]
        return np.isin(lb, keep)
    # pass 1: seeds by the graph's colours
    who = _classify(rgb, dark, [pieces[p]['srgb'] for p in ids], others)
    refs, info = [], {}
    for k, pid in enumerate(ids):
        g = group(ndimage.binary_opening(who == k, _disk(1)))
        seed = g & ~dark if g is not None else None
        if seed is not None and seed.sum() >= 20:
            refs.append(np.array([np.median(rgb[seed], 0)] + _tones(rgb, seed)))    # the median, lit and shade
        else:
            refs.append(np.atleast_2d(pieces[pid]['srgb']))
        info[pid] = {'ref': [round(float(c), 3) for c in refs[-1][0]]}
    # pass 2: the drawing's own clip colours, per pixel and per cell
    who = _classify(rgb, dark, refs, others)
    cells, n = ndimage.label(~dark)
    idx = np.arange(1, n + 1)
    carea = ndimage.sum(np.ones_like(cells), cells, idx)
    votes = np.stack([ndimage.sum(who == k, cells, idx) for k in range(len(ids))], 1) if n else np.zeros((0, len(ids)))
    out = {}
    for k, pid in enumerate(ids):
        take = (votes[:, k] >= 0.5 * carea) & (carea <= 0.05 * ppl * ppl) if n else np.zeros(0, bool)
        if n and prior is not None and prior.get(pid) is not None:
            inside = ndimage.sum(prior[pid], cells, idx)
            others_k = [j for j in range(len(ids)) if j != k]
            theirs = votes[:, others_k].max(1) if others_k else np.zeros(n)
            take |= (inside >= 0.5 * carea) & (carea <= 0.05 * ppl * ppl) & (theirs < 0.5 * carea)
        m = np.isin(cells, idx[take]) | ndimage.binary_opening(who == k, _disk(1))
        m = group(m)
        if m is None:
            out[pid] = np.zeros((H, W), bool); info[pid]['px'] = 0
            continue
        # closed over the lines inside it (the drawn divisions between its parts: a claw's joint), holes filled, then
        # the outline's inner half
        near_lines = dark & ndimage.binary_dilation(m, _disk(2 * lw))
        closed = ndimage.binary_closing(m | near_lines, _disk(lw + 1)) & (m | dark)
        m = ndimage.binary_fill_holes(closed) | m
        m = ndimage.binary_opening(m, _disk(1))
        m = m | (dark & ndimage.binary_dilation(m, _disk(lw)))
        lb2, n2 = ndimage.label(m)
        if n2 > 1:                                           # (only what joins the clip)
            a2 = ndimage.sum(np.ones_like(lb2), lb2, np.arange(1, n2 + 1))
            m = np.isin(lb2, 1 + np.nonzero(a2 >= 0.05 * a2.max())[0])
        out[pid] = m
        info[pid]['px'] = int(m.sum())
    # a pixel two clips claim (their shared outline) goes to the one whose colour is nearer across it
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = out[ids[i]], out[ids[j]]
            both = a & b
            if both.any():
                da = ndimage.distance_transform_edt(~(a & ~both & ~dark))
                db = ndimage.distance_transform_edt(~(b & ~both & ~dark))
                ta = da[both] <= db[both]
                a[both] = ta; b[both] = ~ta
    return out, info


def sheet_views(rgb, eye_x, kind='head', facing=-1):
    """a sheet's views and their origins: kind 'head' (a head turnaround: refcheck.detect_heads) or 'body' (a body
    turnaround: sheetqa.detect_figures) -> dict(ppl, az3, views {view: dict(eye (x, y px: the grid's origin), eyes_uv
    [(u, z) L])})."""
    from . import sheetqa
    if kind == 'head':
        from . import refcheck
        Hd = refcheck.detect_heads(rgb, eye_x, facing)
        ppl, F = Hd['ppl'], Hd['heads']
    else:
        Dd = sheetqa.detect_figures(rgb, None, eye_x, facing)
        ppl, F = Dd['ppl'], Dd['figures']
    fe = (F.get('front') or {}).get('eyes') or []
    te = (F.get('three_quarter') or {}).get('eyes') or []
    az3 = float(np.degrees(np.arccos(np.clip(abs(te[1][0] - te[0][0]) / abs(fe[1][0] - fe[0][0]), 0, 1)))) \
        if len(fe) == 2 and len(te) == 2 else 35.0
    views = {}
    for v in VIEWS:
        f = F.get(v)
        if f is None:
            continue
        e = f.get('eyes') or []
        ey = f['eye_y']
        if v == 'profile' and e:
            o = (e[0][0], ey)
        elif v == 'back':
            ax = f.get('axis_x')
            if ax is None:
                ax = sheetqa._row_centre(f['_mask'], int(ey - 0.3 * ppl), int(ey + 0.3 * ppl))
            o = (ax, ey)
        elif len(e) == 2:
            o = (float(np.mean([p[0] for p in e])), ey)
        else:
            continue
        views[v] = dict(eye=o, eyes_uv=[((p[0] - o[0]) / ppl, (ey - p[1]) / ppl) for p in e])
    return dict(ppl=float(ppl), az3=round(az3, 1), views=views)


def design(rgb, eye_x, pieces, kind='head', facing=-1, win=WIN, prior=None, anchor=None):
    """a sheet's clips per view: {'ppl', 'az3', 'views': {view: dict(rgb (the window), masks {piece: mask}, info, eye)}}.
    prior: another sheet's design() (the head turnaround's, for the body turnaround's small clips), registered per view
    by the anchor piece's centroid (default: the largest clip there) and handed to design_clips."""
    S = sheet_views(rgb, eye_x, kind, facing)
    out = {'ppl': S['ppl'], 'az3': S['az3'], 'views': {}}
    for v, sv in S['views'].items():
        cr = crop(rgb, sv['eye'], S['ppl'], win)
        pr = None
        if prior is not None and v in prior['views']:
            pv = prior['views'][v]
            masks, _ = design_clips(cr, S['ppl'], pieces, sv['eyes_uv'], win)
            a = anchor or max(pv['masks'], key=lambda p: pv['masks'][p].sum())
            Mp, Mo = measure(pv['masks'][a], prior['ppl'], win), measure(masks.get(a, np.zeros(1, bool)), S['ppl'], win)
            if Mp['px'] and Mo['px']:
                sh = (Mo['u'] - Mp['u'], Mo['z'] - Mp['z'])
                pr = {p: transfer(m, prior['ppl'], cr.shape[:2], S['ppl'], sh, win) for p, m in pv['masks'].items()}
        masks, info = design_clips(cr, S['ppl'], pieces, sv['eyes_uv'], win, prior=pr)
        out['views'][v] = dict(rgb=cr, masks=masks, info=info, eye=sv['eye'])
    return out


# ------------------------------------------------------------------------------------------------------------ measures
def measure(m, ppl, win=WIN):
    """one clip mask on a window grid -> dict(px, u, z (centroid, L), size (sqrt area, L), w, h (extent, L), angle
    (principal axis from the vertical, degrees, -90..90, + leaning to the picture's right at the top), ratio (major /
    minor axis))."""
    px = int(m.sum())
    if px == 0:
        return {'px': 0}
    u, z = grid_uz(m.shape, ppl, win)
    ys, xs = np.nonzero(m)
    uu, zz = u[xs], z[ys]
    cu, cz = uu.mean(), zz.mean()
    du, dz = uu - cu, zz - cz
    C = np.array([[np.mean(du * du), np.mean(du * dz)], [np.mean(du * dz), np.mean(dz * dz)]])
    w_, V = np.linalg.eigh(C)
    ax = V[:, 1]                                             # the major axis (u, z)
    if ax[1] < 0:
        ax = -ax
    ang = float(np.degrees(np.arctan2(ax[0], ax[1])))       # from the vertical, + toward +u at the top
    if ang > 90:
        ang -= 180
    return dict(px=px, u=round(float(cu), 4), z=round(float(cz), 4), size=round(float(np.sqrt(px)) / ppl, 4),
                w=round(float(uu.max() - uu.min() + 1 / ppl), 4), h=round(float(zz.max() - zz.min() + 1 / ppl), 4),
                angle=round(ang, 1), ratio=round(float(np.sqrt(w_[1] / max(w_[0], 1e-12))), 3))


def normalised(m, S=64, N=None):
    """a mask moved to its centroid and scaled so sqrt(area) = S px, on an N x N canvas (default 3 S) -> bool."""
    from scipy import ndimage
    N = N or 3 * S
    ys, xs = np.nonzero(m)
    if not len(ys):
        return np.zeros((N, N), bool)
    k = np.sqrt(len(ys)) / S                                 # source px per canvas px
    cy, cx = ys.mean(), xs.mean()
    yy, xx = np.mgrid[0:N, 0:N]
    sy = cy + (yy + 0.5 - N / 2) * k - 0.5
    sx = cx + (xx + 0.5 - N / 2) * k - 0.5
    return ndimage.map_coordinates(m.astype(float), [sy, sx], order=1, mode='constant', cval=0.0) >= 0.5


def shape_iou(a, b):
    """the IoU of two masks after aligning their centroids and scaling to equal areas."""
    A, B = normalised(a), normalised(b)
    u = (A | B).sum()
    return float((A & B).sum() / u) if u else None


def _centroid(m):
    ys, xs = np.nonzero(m)
    return np.array([ys.mean(), xs.mean()])


def as_drawn(mo, md, occ, lw=2, it=10):
    """ours as the drawing shows the clip: the drawing's other clips (occ: their drawn masks, grown lw px over the
    outline they share) cover part of the drawn clip md, so ours is seen through the same cover: ours aligned on the
    drawn clip by centroid and area (as shape_iou aligns them) on what's left of ours, the cover moved onto ours by that
    alignment and taken out, repeated until it holds -> (ours less the cover, the share of ours taken out). A clip the
    drawing doesn't cover (occ None or clear of it) is ours as it is."""
    from scipy import ndimage
    if occ is None or not occ.any() or not mo.any() or not md.any():
        return mo, 0.0
    occ = ndimage.binary_dilation(occ, _disk(lw))
    if not (occ & ndimage.binary_dilation(md, _disk(2 * lw))).any():
        return mo, 0.0
    cd, ad = _centroid(md), float(md.sum())
    yy, xx = np.mgrid[0:mo.shape[0], 0:mo.shape[1]]
    cur, seen = mo, []
    for _ in range(it):
        co, s = _centroid(cur), np.sqrt(ad / cur.sum())
        sy, sx = cd[0] + (yy - co[0]) * s, cd[1] + (xx - co[1]) * s
        cov = ndimage.map_coordinates(occ.astype(float), [sy, sx], order=0, mode='constant', cval=0.0) > 0.5
        nxt = mo & ~cov
        if not nxt.any():
            break
        key = int(nxt.sum())
        if np.array_equal(nxt, cur) or key in seen:          # (held, or cycling between two covers: take this one)
            cur = nxt
            break
        seen.append(key)
        cur = nxt
    return cur, round(1.0 - float(cur.sum()) / float(mo.sum()), 4)


def arms(m, width=20.0):
    """a star's arms from its centroid as fractions of its height (the up and down reaches' sum), each the furthest
    outline point within `width` degrees of its direction: up, down, the longer side arm (a drawn star's other one can
    be under another clip: head_turnaround's left arm under the crab; left and right kept), the four diagonal minor
    points' mean -> dict, or None for an empty mask."""
    from scipy import ndimage
    if m.sum() < MIN_PX:
        return None
    ys, xs = np.nonzero(m & ~ndimage.binary_erosion(m))
    c = _centroid(m)
    dy, dx = -(ys - c[0]), xs - c[1]                          # up and right
    r = np.hypot(dx, dy)
    a = np.degrees(np.arctan2(dx, dy)) % 360                  # 0 up, 90 right
    reach = {}
    for name, ang in (('up', 0), ('ur', 45), ('right', 90), ('dr', 135), ('down', 180), ('dl', 225), ('left', 270),
                      ('ul', 315)):
        d = np.abs((a - ang + 180) % 360 - 180)
        sel = d <= width
        reach[name] = float(r[sel].max()) if sel.any() else 0.0
    h = reach['up'] + reach['down']
    if h <= 0:
        return None
    f = lambda v: round(float(v / h), 3)
    return dict(up=f(reach['up']), down=f(reach['down']), side=f(max(reach['left'], reach['right'])),
                left=f(reach['left']), right=f(reach['right']),
                minor=f((reach['ur'] + reach['dr'] + reach['dl'] + reach['ul']) / 4), height_px=round(h, 1))


def face_on(V, F, axes, ppl=400.0, edge=False):
    """a clip drawn alone along its own facing (axes: columns x, y, z = its facing; world verts V), orthographic at ppl
    px per unit of V -> bool mask. edge: seen from its side (along its x axis), its thickness across."""
    from .faceqa import zbuffer
    V = np.asarray(V, float)
    q = (V - V.mean(0)) @ np.asarray(axes, float)             # its own frame: x across, y up, z out
    W = np.c_[q[:, 2], -q[:, 0], q[:, 1]] if edge else np.c_[q[:, 0], -q[:, 2], q[:, 1]]
    T = _tris(F)
    ext = max(np.abs(W[:, 0]).max(), np.abs(W[:, 2]).max()) * 1.1 + 2.0 / ppl
    win = dict(x=ext, top=ext, bottom=-ext)
    _, lab = zbuffer([(W, T, np.ones(len(T), np.int64))], 0.0, (0.0, 0.0), 1.0, 1.0 / ppl, win)
    return lab > 0


def _tris(F):
    F = [tuple(int(i) for i in f) for f in F]
    return np.array([f[:3] for f in F] + [(f[0], f[2], f[3]) for f in F if len(f) == 4], np.int64)


def clip_axes(V, centre=None):
    """a placed clip's own frame from its vertices: columns x, y, z = its thin axis (the smallest principal axis, away
    from the head's centre), y the largest's made perpendicular and pointing up."""
    P = np.asarray(V, float)
    c = P.mean(0)
    w, U = np.linalg.eigh(np.cov((P - c).T))
    z = U[:, 0]
    if centre is not None and z @ (c - np.asarray(centre, float)) < 0:
        z = -z
    y = np.array([0, 0, 1.0]) - z[2] * z
    y = y / np.linalg.norm(y) if np.linalg.norm(y) > 1e-9 else U[:, 2]
    return np.stack([np.cross(y, z), y, z], 1)


def own_axes(V, spec=None, centre=None):
    """a placed clip's own frame (columns x, y, z = its facing; y its up, toward a crab's claws): from its spec's facing
    and tilt as charkit.accessories places it, else clip_axes() (the vertices' principal axes)."""
    if spec and spec.get('facing') is not None:
        from . import accessories as acc
        return acc._axes(acc._dir(*spec['facing']), spec.get('tilt', 0.0))
    return clip_axes(V, centre)


def face_masks(geo, axes, alone):
    """each clip face-on in its own frame (axes per clip), scaled to the clips-alone drawing's of its kind (equal areas;
    the declared FACE view reads parts in the body's width, so only the raster's grain matters) -> [mask]."""
    out = []
    for (V, F), ax, al in zip(geo, axes, alone):
        V = np.asarray(V, float)
        q = (V - V.mean(0)) @ np.asarray(ax, float)
        ext = max(np.ptp(q[:, 0]), np.ptp(q[:, 1]), 1e-9)
        m = face_on(V, F, ax, ppl=300.0 / ext)
        if al is not None and m.any():
            m = face_on(V, F, ax, ppl=300.0 / ext * float(np.sqrt(al.sum() / m.sum())))
        out.append(m)
    return out


def face_labels(masks, gap=8):
    """clips' face-on masks side by side on one label image (clip k: k + 1) -> label image."""
    ms = [m[np.ix_(m.any(1), m.any(0))] if m.any() else m for m in masks]
    H = max(m.shape[0] for m in ms) + 2 * gap
    W = sum(m.shape[1] + gap for m in ms) + gap
    lab = np.zeros((H, W), np.int64)
    x = gap
    for k, m in enumerate(ms):
        lab[gap:gap + m.shape[0], x:x + m.shape[1]][m] = k + 1
        x += m.shape[1] + gap
    return lab


def axis_in_view(R, az):
    """a clip's own up (its frame's y: a crab's claws) in a view's picture -> degrees (0 the picture's right, 90 up)."""
    y = np.asarray(R, float)[:, 1]
    a = np.radians(az)
    return float(np.degrees(np.arctan2(y[2], y[0] * np.cos(a) + y[1] * np.sin(a)))) % 360.0


def hair_flow(B, azs, iris, centre, L, ppl, views=('front', 'three_quarter', 'profile'), win=WIN):
    """the hair's flow in each view's picture: our hair drawn alone (its nearest surface), each pixel its triangle's
    strand direction (root to tip: the hair pieces' `strand`, geom/hair_pieces beside the bundle) projected -> {view:
    (H, W, 2)}, {} without the pieces' strands."""
    import os
    from .faceqa import zbuffer
    gdir = os.path.join(os.path.dirname(os.path.abspath(B.path)), 'geom', 'hair_pieces')
    Vs, Ts, St, off = [], [], [], 0
    for o in B.objects(groups=('hair',)):
        if not o.has('eval'):
            continue
        p = os.path.join(gdir, o.name.replace('hair_', '', 1) + '.npz')
        if not os.path.exists(p):
            continue
        V, T = o.mesh('eval')[:2]
        st = np.load(p)['strand']
        if len(st) != len(V):
            continue
        Vs.append(V); Ts.append(np.asarray(T) + off); St.append(st[np.asarray(T)].mean(1)); off += len(V)
    if not Vs:
        return {}
    V, T, st = np.vstack(Vs), np.vstack(Ts), np.vstack(St)
    out = {}
    for v in views:
        az = azs[v]
        _, lab = zbuffer([(V, T, np.arange(len(T)))], az, origin(v, az, iris, centre), L, 1.0 / ppl, win)
        a = np.radians(az)
        F = np.zeros(lab.shape + (2,))
        ok = lab >= 0
        F[ok, 0] = st[lab[ok], 0] * np.cos(a) + st[lab[ok], 1] * np.sin(a)
        F[ok, 1] = st[lab[ok], 2]
        out[v] = F
    return out


def flow_under(F, m):
    """the hair's flow under a mask: its strands' mean direction there (picture degrees) and coherence (0..1)."""
    h, w = min(F.shape[0], m.shape[0]), min(F.shape[1], m.shape[1])
    sel = m[:h, :w]
    if not sel.any():
        return None
    s = F[:h, :w][sel].sum(0)
    n = float(np.linalg.norm(s))
    if n < 1e-9:
        return None
    return float(np.degrees(np.arctan2(s[1], s[0]))) % 360.0, n / float(sel.sum())


def edge_body(m, keep=0.3):
    """the clips-alone sheet's edge-on clip less its hair-clip loop (drawn behind it, the back on the right; we don't
    build it: hidden in the hair once worn): the columns past the deepest one where fewer than `keep` of the deepest
    column's pixels remain -> mask."""
    occ = m.sum(0)
    if not occ.any():
        return m
    j = int(np.argmax(occ))
    low = np.nonzero(occ[j:] < keep * occ[j])[0]
    out = m.copy()
    if len(low):
        out[:, j + int(low[0]):] = False
    return out


def compare(mo, md, ppl, kind, view, occ=None):
    """ours against the design for one clip in one view -> {measure: check}. occ: the drawing's other clips' masks over
    this one (ours is measured as the drawing shows the clip: as_drawn())."""
    hid = 0.0
    if occ is not None and mo.sum() >= MIN_PX and md.sum() >= MIN_PX:
        mo, hid = as_drawn(mo, md, occ, max(1, int(round(0.004 * ppl))))
    O, D = measure(mo, ppl), measure(md, ppl)
    C = {}
    tag = 'acc_%s_%s_' % (kind, view)
    if D['px'] < MIN_PX and O['px'] < MIN_PX:
        C[tag + 'shown'] = {'value': O['px'], 'design_px': D['px'], 'status': 'PASS',
                            'note': 'hidden in both (the design and ours show under %d px)' % MIN_PX}
        return C, O, D
    if D['px'] < MIN_PX or O['px'] < MIN_PX:
        C[tag + 'shown'] = {'value': O['px'], 'design_px': D['px'], 'status': 'FAIL',
                            'note': 'ours shows where the design hides it' if D['px'] < MIN_PX else
                            'hidden (or missing) where the design shows it'}
        return C, O, D
    C[tag + 'shown'] = {'value': round(O['px'] / D['px'], 3), 'status': 'INFO', 'note': 'shown pixels, ours / design'}
    v = shape_iou(mo, md)
    C[tag + 'iou'] = {'value': round(v, 3), 'status': _grade('iou', v)}
    if occ is not None:
        C[tag + 'iou']['as_drawn'] = hid            # the share of ours the drawing's cover took out before measuring
    r = O['size'] / D['size']
    C[tag + 'size'] = {'value': round(r, 3), 'ours_L': O['size'], 'design_L': D['size'], 'status': _grade('size', r - 1),
                       'h': [O['h'], D['h']], 'w': [O['w'], D['w']]}
    dx, dz = O['u'] - D['u'], O['z'] - D['z']
    d = float(np.hypot(dx, dz))
    C[tag + 'pos'] = {'value': round(d, 4), 'dx': round(dx, 4), 'dz': round(dz, 4), 'ours': [O['u'], O['z']],
                      'design': [D['u'], D['z']], 'status': _grade('pos', d)}
    da = (O['angle'] - D['angle'] + 90) % 180 - 90
    graded = min(O['ratio'], D['ratio']) >= ROUND
    C[tag + 'angle'] = {'value': round(da, 1), 'ours': O['angle'], 'design': D['angle'],
                        'ratio': [O['ratio'], D['ratio']], 'status': _grade('angle', da) if graded else 'INFO'}
    if not graded:
        C[tag + 'angle']['note'] = 'too round to have an axis (major / minor under %.2f)' % ROUND
    return C, O, D


def triangulate(M, az3):
    """a clip's 3D centroid (x her left, y toward her back from the eyes, z up from the eye line; L) from its centroids
    in the front, three-quarter and profile views (M {view: measure()}), least squares -> (xyz, residual L) or None."""
    rows, rhs, zs = [], [], []
    a = np.radians(az3)
    for v, (cx, cy) in (('front', (1.0, 0.0)), ('three_quarter', (np.cos(a), np.sin(a))), ('profile', (0.0, 1.0))):
        m = M.get(v)
        if not m or not m.get('px'):
            continue
        rows.append([cx, cy]); rhs.append(m['u']); zs.append(m['z'])
    if len(rows) < 2:
        return None
    A, b = np.array(rows), np.array(rhs)
    xy, *_ = np.linalg.lstsq(A, b, rcond=None)
    res = float(np.sqrt(np.mean((A @ xy - b) ** 2)))
    return np.array([xy[0], xy[1], float(np.mean(zs))]), res


# -------------------------------------------------------------------------------------------------------------- ours
def our_labels(meshes, clips, az, origin, L, ppl, win=WIN, ids=False):
    """ours on a view's window grid: meshes [(V, T)] drawn as occluders, clips [(V, T)] labelled 1..n
    -> label image (0 = anything else or nothing, k = clip k's visible pixels); ids: the occluders labelled too,
    OCC_ID + their index (what covers a clip: covered_by())."""
    from . import faceqa
    ms = [(V, T, np.full(len(T), OCC_ID + i if ids else 0, np.int64)) for i, (V, T) in enumerate(meshes)]
    ms += [(V, T, np.full(len(T), k + 1, np.int64)) for k, (V, T) in enumerate(clips)]
    _, lab = faceqa.zbuffer(ms, az, origin, L, 1.0 / ppl, win)
    return np.maximum(lab, 0)


OCC_ID = 100000                        # our_labels(ids=True): an occluder's label, OCC_ID + its index


def covered_by(lab_ids, alone, shown, names, kinds):
    """what covers a clip where it doesn't show: the pixels of its own silhouette (alone) that it doesn't show, by the
    label in front of them (another clip by its kind, an occluder by its object's name: names) -> {name: px}, most first."""
    hid = alone & ~shown
    out = {}
    if hid.any():
        ids, n = np.unique(lab_ids[hid], return_counts=True)
        for i, c in zip(ids, n):
            name = names[i - OCC_ID] if i >= OCC_ID else kinds[i - 1] if 1 <= i <= len(kinds) else 'nothing'
            out[name] = out.get(name, 0) + int(c)
    return dict(sorted(out.items(), key=lambda t: -t[1]))


def origin(view, az, iris, centre):
    from .bodyqa import origin as o
    return o(view, az, iris, centre)


def clip_objects(B):
    """the bundle's visible accessory objects with their spec kind -> [(kind, obj)] (an object named KIND_i, as
    charkit.accessories names them; a hair-material accessory, a bun built as one, is the hair's: left out)."""
    import re
    out = []
    for o in B.objects(groups=('accessory',)):
        if not o.has('eval'):
            continue
        m = re.match(r'([a-z]+)_\d+', o.name)
        kind = m.group(1) if m else o.name
        if kind == 'bun':
            continue
        out.append((kind, o))
    return out


def seat(clip_V, hair, L, centre):
    """how a clip sits on the hair (world): its thin axis (the smallest principal axis, away from the head's centre),
    the hair's outer surface under its middle along that axis (a ray cast in from outside) and under each vertex
    -> dict(gap: the least of its vertices' heights over the hair under them, L (- = sunk into it; the plane over its
    middle's hair where no vertex has hair under it); sunk: the share of its vertices under the hair surface under them;
    plane: its lowest point over the hair under its middle (round 2's gap: a bent clip has no one plane); normal, anchor)
    or None (no hair under its middle)."""
    from .hair import _cast_in
    P = np.asarray(clip_V, float)
    c = P.mean(0)
    w, V_ = np.linalg.eigh(np.cov((P - c).T))
    n = V_[:, 0]
    if n @ (c - np.asarray(centre, float)) < 0:
        n = -n
    hv = np.vstack([h[0] for h in hair]); off, hf = 0, []
    for V, T in hair:
        hf += [tuple(int(i) + off for i in t) for t in T]; off += len(V)
    R = 0.6 * L
    t = _cast_in(hv, hf, (c + n * R)[None], -n[None], 2 * R)[0]
    if not np.isfinite(t):
        return None
    h = c + n * R - n * t                                    # the hair's outer surface under the clip's middle
    tv = _cast_in(hv, hf, P + n * R, np.repeat(-n[None], len(P), 0), 2 * R)
    under = np.isfinite(tv) & (tv < R - 1e-3 * L)            # the hair surface under a vertex lies above it: sunk
    # the gap: each vertex's height over the hair under it, the least (a clip bent to what's under it, round 3's star,
    # has no one plane: over its middle's hair the plane read -0.0096 for a clip with no vertex under the hair)
    hv_ = np.isfinite(tv)
    gap = float((tv[hv_] - R).min()) / L if hv_.any() else float(((P - h) @ n).min()) / L
    plane = float(((P - h) @ n).min()) / L
    return dict(gap=round(gap, 4), sunk=round(float(under.mean()), 3), plane=round(plane, 4),
                normal=[round(float(x), 3) for x in n], anchor=[round(float(x), 4) for x in h])


def sheets(spec):
    """the design's sheets for the clips: [(name, image path, kind 'head' | 'body', graded)] from the spec's ref (the
    manifest's sheets: face -> the head turnaround, graded; body -> the body turnaround, information)."""
    ref = spec.get('ref') if isinstance(spec.get('ref'), dict) else {}
    out = []
    for key, kind, graded in (('face_sheet', 'head', True), ('body_sheet', 'body', False)):
        s = ref.get(key)
        if s and s.get('image'):
            out.append((s.get('id') or key, s['image'], kind, graded, s.get('facing', -1)))
    return out


def _abs(p):
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


ALONE_REF = 'hair_clips_layers'        # the manifest's separated clips reference (its bottom row: the clips alone)


def alone_clips(spec, load=None):
    """the clips-alone drawings (the manifest's ALONE_REF, its bottom row under the widest empty band of rows; each clip
    straight on and edge-on, told apart by colour and by width: charkit.layerref's reading) -> ({kind: face-on mask,
    kind + '_edge': edge-on mask}, [path]) or None (no such reference)."""
    from . import layerref
    ref = spec.get('ref') if isinstance(spec.get('ref'), dict) else {}
    man = ref.get('manifest')
    if not man:
        return None
    M = json.load(open(_abs(man)))
    r = (M.get('references') or {}).get(ALONE_REF)
    if not r or not r.get('path'):
        return None
    path = _abs(r['path'])
    rgb = np.asarray(load(path) if load else layerref._load(path), float)[..., :3]
    cut = layerref._rows_split(rgb)
    out = {}
    blobs = layerref._blobs(rgb[cut:])
    for kind, yellow in (('star', True), ('crab', False)):
        L_ = [b for b in blobs if (b['colour'][1] > 0.6 * b['colour'][0] and b['colour'][2] < 0.75 * b['colour'][1])
              == yellow]
        if not L_:
            continue
        asp = lambda b: (b['box'][2] - b['box'][0]) / max(1, b['box'][3] - b['box'][1])
        for name, b in ((kind, max(L_, key=asp)), (kind + '_edge', min(L_, key=asp) if len(L_) > 1 else None)):
            if b is not None:
                x0, y0, x1, y1 = b['box']
                out[name] = b['mask'][y0:y1 + 1, x0:x1 + 1]
    return out, [path]


def design_sheets(items, eye_x, pieces):
    """every sheet's clips (design()), the head sheet's registered as the body sheet's prior: items [(name, kind,
    graded, facing, path, rgb)] -> {name: design}. (Pure in its arguments: the QA memoises it.)"""
    out, prior = {}, None
    for name, kind, graded, facing, path, rgb in sorted(items, key=lambda t: t[1] != 'head'):
        D = design(rgb, eye_x, pieces, kind, facing, prior=prior if kind == 'body' else None)
        D.update(name=name, kind=kind, graded=graded, path=path)
        out[name] = D
        if kind == 'head':
            prior = D
    return out


def design_all(spec, eye_x, load=None, memo=None):
    """the spec's sheets' clips (design_sheets) -> ({name: design}, pieces, files read). load(path) -> rgb floats;
    memo(fn, *args): a memoiser (the QA's venv memo)."""
    from .bodymeasure import load_graph
    pieces = clip_pieces(load_graph(spec))
    if not pieces:
        return {}, pieces, []
    if load is None:
        from PIL import Image
        load = lambda p: np.asarray(Image.open(p).convert('RGB'), float) / 255
    items, files = [], []
    for name, path, kind, graded, facing in sheets(spec):
        items.append((name, kind, graded, facing, path, np.asarray(load(_abs(path)), float)[..., :3]))
        files.append(_abs(path))
    run = memo or (lambda fn, *a: fn(*a))
    return run(design_sheets, items, eye_x, pieces), pieces, files


def window_to_grid(m, eye, ppl, src=WIN, dst=None):
    """a mask on a window round a sheet pixel (crop()'s grid, window src) moved onto another window's grid round the
    same pixel at the same scale (dst: default bodyqa.WIN, the design_views grids) -> bool (dst's shape)."""
    from .bodyqa import WIN as BW
    dst = dst or BW
    Wd = int(round(2 * dst['x'] * ppl)); Hd = int(round((dst['top'] - dst['bottom']) * ppl))
    xa, ya = int(round(eye[0] - src['x'] * ppl)), int(round(eye[1] - src['top'] * ppl))
    xb, yb = int(round(eye[0] - dst['x'] * ppl)), int(round(eye[1] - dst['top'] * ppl))
    dy, dx = ya - yb, xa - xb                                  # a row of src is row + dy of dst
    out = np.zeros((Hd, Wd), bool)
    H, W = m.shape
    r0, c0 = max(0, -dy), max(0, -dx)
    r1, c1 = min(H, Hd - dy), min(W, Wd - dx)
    if r1 > r0 and c1 > c0:
        out[r0 + dy:r1 + dy, c0 + dx:c1 + dx] = m[r0:r1, c0:c1]
    return out


def grid_masks(designs, ppl, kind='body'):
    """the clips of the sheet of that kind (the body turnaround: the bodyqa grids') on the bodyqa.design_views grids
    -> {view: {piece: mask}} (empty without such a sheet, or at another scale)."""
    D = next((d for d in designs.values() if d['kind'] == kind), None)
    if D is None or abs(D['ppl'] - ppl) > 1e-6 * ppl:
        return {}
    return {v: {p: window_to_grid(m, dv['eye'], ppl) for p, m in dv['masks'].items()} for v, dv in D['views'].items()}


def reclass(dv, masks):
    """bodyqa.design_views' views with the clips' pixels (grid_masks) in the accessory class, cls and raw alike (a
    drawn crab is not hair, a drawn star not iris) -> a new dict (the views without clips are the same objects)."""
    out = {}
    for v, d in dv.items():
        ms = [m for m in (masks.get(v) or {}).values()]
        if not ms:
            out[v] = d
            continue
        m = np.zeros(d['cls'].shape, bool)
        for x in ms:
            h, w = min(m.shape[0], x.shape[0]), min(m.shape[1], x.shape[1])
            m[:h, :w] |= x[:h, :w]
        m &= d['fg']
        d = dict(d, cls=np.where(m, ACCESSORY, d['cls']), raw=np.where(m, ACCESSORY, d['raw']), accessory=m)
        out[v] = d
    return out


def piece_of(kind, spec_acc=None):
    """a spec accessory's outfit graph piece: its 'piece', else PIECE by kind."""
    return (spec_acc or {}).get('piece') or PIECE.get(kind)


def evaluate(B, designs, pieces, az3=None, alone=None, labels=None):
    """ours against every sheet's clips -> (table, checks, pictures {sheet: {view: (design rgb, masks, ours label,
    ids)}}). alone: the clips-alone drawings (alone_clips()) for the face-on structure checks. labels: a stand-in for
    ours in the views (the calibration's: charkit.calib.clips), labels(sheet, view, dv, kinds) -> (label image: clip k
    + 1, else 0 or an occluder's OCC_ID + i; each clip drawn alone [mask]) or None; then only the views' checks."""
    from . import qa3d
    As = B.assembly
    L = float(As['L']); centre = np.asarray(As['centre'], float)
    iris = np.array(qa3d.iris_centres(B))
    clips = clip_objects(B)
    names = {o.name for _, o in clips}
    meshes, objn = qa3d.scene_objects(B)
    occ = [(V, T) for (V, T, _), n in zip(meshes, objn) if n not in names]
    occ_names = [n for n in objn if n not in names]
    geo = [o.mesh('eval')[:2] for _, o in clips]
    kinds = [k for k, _ in clips]
    spec_acc = {a['kind']: a for a in (B.spec.get('accessories') or [])}
    table, C, pics = {'sheets': {}, 'seat': {}}, {}, {}
    flows = None
    # the declared checks' inputs (DECLARED_CHECKS, part 'accessories'): the graded sheet's labels per view (clip k + 1),
    # the drawn clips, each clip's own silhouette drawn alone
    I = dict(O={}, names=['-'] + [o.name for _, o in clips], masks={}, alone={}, dv={},
             pm={piece_of(k, spec_acc.get(k)): [(o.name, None)] for k, o in clips})
    for sname, D in designs.items():
        ppl = D['ppl']
        a3 = D['az3']
        azs = {'front': 0.0, 'three_quarter': a3, 'profile': 90.0, 'back': 180.0}
        T_ = table['sheets'].setdefault(sname, {'ppl': round(ppl, 2), 'az3': a3, 'views': {}})
        pics[sname] = {}
        Mo_all, Md_all = {}, {}
        if D['graded']:
            I['ppl'] = ppl
        for v, dv in D['views'].items():
            extra = {}
            if labels is not None:
                got = labels(sname, v, dv, kinds)
                if got is None:
                    continue
                lab_ids, solo = got[:2]
                extra = got[2] if len(got) > 2 else {}
            else:
                org = origin(v, azs[v], iris, centre)
                lab_ids = our_labels(occ, geo, azs[v], org, L, ppl, ids=True)
                solo = [our_labels([], [g], azs[v], org, L, ppl) == 1 for g in geo]   # each clip drawn alone
            H_, W_ = min(lab_ids.shape[0], dv['rgb'].shape[0]), min(lab_ids.shape[1], dv['rgb'].shape[1])
            lab_ids = lab_ids[:H_, :W_]
            solo = [m[:H_, :W_] for m in solo]
            lab = np.where(lab_ids < OCC_ID, lab_ids, 0)
            pics[sname][v] = (dv['rgb'][:H_, :W_], {p: m[:H_, :W_] for p, m in dv['masks'].items()}, lab, kinds)
            if D['graded']:
                I['O'][v] = {'lab': lab}
                I['alone'][v] = {o.name: a for (_, o), a in zip(clips, solo)}
                I['dv'][v] = {}
                # the pair checks' inputs (the crab against the star): each clip drawn alone, the crab's own axis in
                # the picture (ours from its frame, the drawing's CRAB_AXIS; a stand-in's from its labels), the hair's
                # flow under a mask (our hair's strands: hair_flow)
                if v in CRAB_AXIS:
                    if 'crab' in kinds and labels is None:
                        k_ = kinds.index('crab')
                        ax_o = axis_in_view(own_axes(geo[k_][0], spec_acc.get('crab'), centre), azs[v])
                    else:
                        ax_o = extra.get('axis', CRAB_AXIS[v])
                    if flows is None:
                        flows = hair_flow(B, azs, iris, centre, L, ppl)
                    F = flows.get(v)
                    I.setdefault('pair', {})[v] = dict(
                        alone={piece_of(k, spec_acc.get(k)): m for k, m in zip(kinds, solo)},
                        axis=dict(ours=ax_o, design=CRAB_AXIS[v]),
                        flow=None if F is None else (lambda m, F=F: flow_under(F, m)))
            for k, kind in enumerate(kinds):
                pid = piece_of(kind, spec_acc.get(kind))
                md = dv['masks'].get(pid)
                if md is None:
                    continue
                md = md[:H_, :W_]
                mo = lab == k + 1
                cover = [m[:H_, :W_] for p, m in dv['masks'].items() if p != pid and m is not None and m.any()]
                Ck, O, Dm = compare(mo, md, ppl, kind, v, occ=np.any(cover, 0) if cover else None)
                vis = dict(share=round(float(mo.sum()) / max(1, int(solo[k].sum())), 4), alone=int(solo[k].sum()),
                           covered_by=covered_by(lab_ids, solo[k], mo, occ_names, kinds))
                T_['views'].setdefault(v, {})[kind] = {'ours': O, 'design': Dm, 'visible': vis}
                Mo_all.setdefault(kind, {})[v] = O; Md_all.setdefault(kind, {})[v] = Dm
                if D['graded']:
                    C.update(Ck)
                    I['masks']['%s__%s' % (v, pid)] = md
        if D['graded']:
            # each clip's shape IoU per view in one check (the anti-gaming guard's measure for the clips' own checks)
            for kind in kinds:
                vs = {v: C['acc_%s_%s_iou' % (kind, v)]['value'] for v in VIEWS if 'acc_%s_%s_iou' % (kind, v) in C}
                if vs:
                    C['acc_%s_shape' % kind] = {'value': round(float(np.mean(list(vs.values()))), 3), 'views': vs,
                                                'status': 'INFO', 'note': "the clip's shape IoU per view as the drawing "
                                                                          "shows it (acc_KIND_VIEW_iou): the guard's"}
        # the clip's 3D place: each side triangulated from its views' centroids
        for kind in Mo_all:
            to, td = triangulate(Mo_all[kind], a3), triangulate(Md_all[kind], a3)
            if to is None or td is None:
                continue
            d = float(np.linalg.norm(to[0] - td[0]))
            T_.setdefault('pos3d', {})[kind] = {'ours': [round(float(x), 4) for x in to[0]],
                                                'design': [round(float(x), 4) for x in td[0]],
                                                'residual': [round(to[1], 4), round(td[1], 4)]}
            if D['graded']:
                C['acc_%s_pos3d' % kind] = {'value': round(d, 4), 'status': _grade('pos3d', d),
                                            'ours': T_['pos3d'][kind]['ours'], 'design': T_['pos3d'][kind]['design'],
                                            'note': 'the centroid triangulated from the front, three-quarter and profile '
                                                    '(x her left, y toward her back from the eyes, z up from the eye line; L)'}
    # the FACE view (the declared parts checks): our clips face-on, each in its own frame, against the clips-alone
    # sheet's (the stand-in's: labels(FACE_SHEET, FACE, None, kinds) -> (label image, None) or None)
    if I.get('ppl') is not None and alone:
        if labels is not None:
            got = labels(FACE_SHEET, FACE, None, kinds)
        else:
            axes = [own_axes(V, spec_acc.get(k), centre) for (V, _), k in zip(geo, kinds)]
            got = (face_labels(face_masks(geo, axes, [alone.get(k) for k in kinds])), None)
        if got is not None:
            I['O'][FACE] = {'lab': got[0]}
            I['dv'][FACE] = {}
            for k in kinds:
                if alone.get(k) is not None:
                    I['masks']['%s__%s' % (FACE, piece_of(k, spec_acc.get(k)))] = alone[k]
    # the declared checks (DECLARED_CHECKS: each clip's visible share, Michael's non-occlusion rule; the crab's parts
    # face-on), what covers it
    if I.get('ppl') is not None and I['O']:
        from . import declared
        _, Cd = declared.evaluate_part('accessories', I)
        for name, c in Cd.items():
            for sname, D in designs.items():
                if D['graded']:
                    for v, per in table['sheets'][sname]['views'].items():
                        for kind, rec in per.items():
                            if name == 'acc_%s_%s_visible' % (kind, v) and rec.get('visible'):
                                c['covered_by'] = rec['visible']['covered_by']
        C.update(Cd)
    if labels is not None:
        return table, C, pics
    # the seat on the hair (3D)
    hair = [o.mesh('eval')[:2] for o in B.objects(groups=('hair',)) if o.has('eval')]
    for (kind, o), (V, _) in zip(clips, geo):
        if not hair:
            break
        s = seat(V, hair, L, centre)
        if s is None:
            C['acc_%s_seat' % kind] = {'status': 'SKIPPED', 'why': 'no hair under the clip'}
            continue
        table['seat'][kind] = s
        C['acc_%s_seat' % kind] = {'value': s['gap'], 'sunk': s['sunk'], 'status': _grade('seat', s['gap']),
                                   'plane': s['plane'],
                                   'note': "the least of the clip's vertices' heights over the hair under them, L "
                                           "(- = sunk); sunk: the share of its vertices under the hair"}
    # colours: our material's lit tone against the drawn clip's (the head sheet's inner pixels)
    for sname, D in designs.items():
        if not D['graded']:
            continue
        for kind, o in clips:
            pid = piece_of(kind, spec_acc.get(kind))
            px = [dv['rgb'][_inner(dv['masks'][pid])] for dv in D['views'].values() if pid in dv['masks']]
            px = np.concatenate(px) if px else np.zeros((0, 3))
            mats = [m for m in o.materials if m]
            rec = (B.materials.get(mats[0]) or {}) if mats else {}
            if len(px) < 30 or rec.get('lit') is None:
                continue
            from .paletteqa import ciede2000, srgb_to_lab, tones, _hex
            T = tones(px)
            dE = ciede2000(srgb_to_lab(rec['lit']), srgb_to_lab(T['lit']))
            C['acc_%s_colour' % kind] = {'value': round(float(dE), 2), 'ours': _hex(rec['lit']), 'design': _hex(T['lit']),
                                        'status': 'PASS' if dE <= 5 else 'WARN' if dE <= 10 else 'FAIL',
                                        'note': "our material's lit tone against the drawn clip's (dE00)"}
    C.update(structure(clips, geo, centre, alone, spec_acc))
    return table, C, pics


def structure(clips, geo, centre, alone=None, spec_acc=None):
    """each clip face-on (its own frame: own_axes, from its spec's facing and tilt): the star's arms against
    head_turnaround's proportions (STAR_ARMS: acc_star_arms, acc_star_minor), and every clip against the clips-alone
    drawing (acc_KIND_alone, INFO: the structure authority, its proportions the sheet's own) and edge-on against its
    side drawing (acc_KIND_side, INFO: the hair-clip loop drawn behind it left out, edge_body) -> checks."""
    C = {}
    for (kind, o), (V, F) in zip(clips, geo):
        ax = own_axes(V, (spec_acc or {}).get(kind), centre)
        m = face_on(V, F, ax)
        if kind == 'star':
            a = arms(m)
            if a is not None:
                for key, name in (('side', 'arms'), ('minor', 'minor')):
                    t, p, w = STAR_ARMS[key]
                    d = a[key] - t
                    C['acc_star_%s' % name] = {
                        'value': round(d, 3), 'ours': a[key], 'design': t, 'arms': a,
                        'status': 'PASS' if abs(d) <= p else 'WARN' if abs(d) <= w else 'FAIL',
                        'note': "the star face-on: its %s over its height, against head_turnaround's unoccluded "
                                "reading (the clips-alone sheet's structure, the turnaround's proportions)" % (
                                    'side arms' if key == 'side' else 'four minor points')}
        if alone and alone.get(kind) is not None:
            C['acc_%s_alone' % kind] = {'value': round(shape_iou(m, alone[kind]) or 0.0, 3), 'status': 'INFO',
                                        'note': 'our clip face-on against the clips-alone drawing (shape IoU: its '
                                                'structure; the proportions are head_turnaround\'s)'}
        if alone and alone.get(kind + '_edge') is not None:
            e = face_on(V, F, ax, edge=True)[:, ::-1]               # (its back on the right, as the sheet draws it)
            C['acc_%s_side' % kind] = {'value': round(shape_iou(e, edge_body(alone[kind + '_edge'])) or 0.0, 3),
                                       'status': 'INFO',
                                       'note': "our clip edge-on against the clips-alone sheet's side drawing (shape "
                                               "IoU; the hair-clip loop drawn behind it left out)"}
    return C


def _inner(m):
    from scipy import ndimage
    return ndimage.binary_erosion(m, _disk(2))


# ------------------------------------------------------------------------------------------------------------ pictures
COLOURS = [(0.95, 0.72, 0.05), (0.85, 0.12, 0.12), (0.2, 0.5, 0.95), (0.3, 0.75, 0.3)]


def zoom_box(pics, ppl, pad=0.06, win=WIN):
    """the rows and columns (one box for every view of a sheet) that hold the clips, both sides, padded by pad L."""
    rs, cs = [], []
    for rgb, masks, lab, kinds in pics.values():
        m = (lab > 0)
        for x in masks.values():
            m = m | x
        ys, xs = np.nonzero(m)
        if len(ys):
            rs += [ys.min(), ys.max()]; cs += [xs.min(), xs.max()]
    if not rs:
        return None
    p = int(pad * ppl)
    return max(0, min(rs) - p), max(rs) + p + 1, max(0, min(cs) - p), max(cs) + p + 1


def panels(rgb, masks, lab, kinds, box, pieces_of):
    """one view's three panels over the zoom box: the drawing, ours (the clips in their colours over grey), and the
    silhouettes (grey both, blue the design's only, red ours only) -> list of (H, W, 3)."""
    r0, r1, c0, c1 = box
    im = rgb[r0:r1, c0:c1]
    ours = np.full(im.shape, 0.93)
    ours[lab[r0:r1, c0:c1] == 0] = 0.93
    sil = np.full(im.shape, 0.97)
    for k, kind in enumerate(kinds):
        col = COLOURS[k % len(COLOURS)]
        mo = lab[r0:r1, c0:c1] == k + 1
        ours[mo] = col
        md = masks.get(pieces_of(kind), np.zeros(lab.shape, bool))[r0:r1, c0:c1]
        sil[md & mo] = (0.55, 0.55, 0.6); sil[md & ~mo] = (0.3, 0.45, 0.95); sil[mo & ~md] = (0.92, 0.3, 0.3)
    return [im, ours, sil]


def picture(pics, ppl, pieces_of, scale=2):
    """a sheet's views as rows of panels (panels()), zoomed to the clips at one scale -> image."""
    box = zoom_box(pics, ppl)
    if box is None:
        return None
    rows = []
    for v, (rgb, masks, lab, kinds) in pics.items():
        ps = panels(rgb, masks, lab, kinds, box, pieces_of)
        sep = np.ones((ps[0].shape[0], 4, 3))
        rows.append(np.concatenate([ps[0], sep, ps[1], sep, ps[2]], 1))
    W = max(r.shape[1] for r in rows)
    im = np.concatenate([np.pad(r, ((0, 4), (0, W - r.shape[1]), (0, 0)), constant_values=1.0) for r in rows], 0)
    return np.repeat(np.repeat(im, scale, 0), scale, 1)


# ------------------------------------------------------------------------------------------------------------ QA part
from .registry import qa_part  # noqa: E402  (the registry finds the part by its decorator; nothing else imported)


@qa_part('accessories', order=2400, table='accessories')
def qa_accessories(B, design=None, out=None):
    """the hair clips against the design's: each clip found in the head and body turnarounds by the outfit graph's
    piece, ours z-buffered on the same grids; per clip and view its shape (IoU aligned on position and scale), size,
    position and axis; its seat on the hair and its 3D place; its colour. Overlays qa_accessories.png (the graded head
    sheet) and qa_accessories_body.png. -> (table, checks acc_*)."""
    from .qa3d import _save_rgb
    if not clip_objects(B):
        return None, {'acc': {'status': 'SKIPPED', 'why': 'no clips built (accessories other than buns)'}}
    got = design.clips() if design is not None else None
    if not got:
        return None, {'acc': {'status': 'SKIPPED', 'why': "no clip pieces in the outfit graph, or no turnarounds"}}
    D, P = got
    al = design.memo(alone_clips, B.spec) if design is not None else None
    if al:
        for p in al[1]:
            design._rec(p)
    table, C, pics = evaluate(B, D, P, alone=al[0] if al else None)
    if out:
        for name, pv in pics.items():
            im = picture(pv, D[name]['ppl'], lambda k: PIECE.get(k, k), 2 if D[name]['ppl'] > 300 else 3)
            if im is not None:
                _save_rgb(os.path.join(out, 'qa_accessories%s.png' % ('' if D[name]['graded'] else '_' + D[name]['kind'])), im)
    return table, C
