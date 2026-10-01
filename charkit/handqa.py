"""The hands (tool/hands, docs/workstreams/hands.md; docs/ROADMAP.md item 7): each hand against the design's drawn hands
per view, both sides measured the same way from label images on the design's grids (bodyqa's: the sheet's scale,
aligned on the eyes). Until this module nothing measured the hands: the body IoUs average a mitten away.

A hand is the skin beyond its wrist cuff (hand_mask): the arm's direction from the skin within ARM_REACH of the cuff
(cuff_shape's), and the skin past the cuff's middle along it, within HAND_REACH of the cuff, in pieces that touch the
cuff. Ours: our skin and our cuff (the drawn cuff's object: the outfit graph's piece map) in our z-buffer; the
design's: its skin class and its drawn cuff mask.

Checks (QA part 'hands', prefix hand_; lengths in L):
  hand_shape_{L,R}           the hand's silhouette against the drawn hand's per view, ours turned to the drawn arm's
                             direction and the two laid on their centroids (the hand's own shape and its set on the
                             arm: where the arm hangs is the build pose's, body_*_arms), plain IoU;
                             valued by its worst view, `views` {view: IoU} (the anti-gaming guard's shape for the hand
                             checks)
  hand_{view}_reach_{L,R}    how far the hand reaches past its cuff along the arm (the cuff's far edge to the
                             fingertips), ours minus the design's
  hand_{view}_digits_{L,R}   the digits a band across the fingers shows, the median over bands at DIGIT_BANDS of
                             the reach: each run of the hand across the band, plus the seams inside it (the design: its ink
                             lines; ours: where two surfaces meet or the depth steps by SEAM_DEPTH, where an outline
                             draws); ours minus the design's, only in views where the design shows at least 2 (drawn)
                             (PASS within 1 and ours at least 2: a hand showing no separate digit where the design
                             draws some fails)
  hand_{view}_cleft_{L,R}    the deepest pocket between the hand's silhouette and its convex hull (the thumb's cleft,
                             the gaps between spread fingers), ours over the design's; only in views where the design's
                             is at least CLEFT_MIN deep (drawn)
A view where either side shows less than MIN_PX of the cuff or the hand isn't measured (the far hand in profile).
Where something of ours stands in front of our hand (the three-quarter's far hand behind the skirt: our_hidden, the
hand z-buffered alone against the whole figure), the shape is graded on the visible part only: ours' whole silhouette
laid on the drawn hand, the IoU over the pixels not hidden (`views`), its whole-silhouette IoU and visible share
beside it (`whole`, `visible`); the reach is the whole hand's; digits and cleft are not read below VISIBLE_MIN.

    table, checks = handqa.measure(B, design)          # the 'hands' QA part
"""
import numpy as np

from .registry import qa_part

ARM_REACH = 0.35        # L: the skin this close to the cuff gives the arm's direction (pieceqa.cuff_shape's reach)
HAND_REACH = 0.8        # L: a hand pixel lies within this of its cuff (the drawn hands reach 0.60-0.64 L past it)
MIN_PX = 150            # a cuff or hand this small (pixels) in a view isn't measured
DIGIT_BANDS = (0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9)    # shares of the reach past the cuff: bands across the fingers
EDGE_PX = 3             # px: a seam this close to the hand's outline is the outline (the drawn line's width)
SEAM_DEPTH = 0.012      # L: a depth step between neighbouring pixels of ours that the outline draws as a line
VIEWS = ('front', 'three_quarter', 'profile', 'back')
LIMITS = {                                       # (pass within, warn within); else fail
    'shape': (0.75, 0.6),                        # IoU at least (the piece checks' PIECE_PASS; calibrated: charkit/calib)
    'reach': (0.04, 0.08),                       # L: |ours - design| of the reach past the cuff (0.06-0.13 of a hand)
    'digits': (1, 2),                            # |ours - design| digits across the fingers (the drawn count varies
                                                 # by 1 from band to band), ours showing at least 2
    'cleft': ((0.6, 1.67), (0.4, 2.5)),          # ours over the design's deepest silhouette pocket
}
HAND_3D = 0.9           # L: our hand is the skin's shells lying wholly within this of its wrist band's centre, below
                        # it (the palm and each digit are shells of their own: charkit/code_hand.py)
VISIBLE_MIN = 0.75      # our hand less visible than this in a view (behind the skirt): its digits and cleft there are
                        # not read (what the picture shows of them is the occluder's edge), its shape on what shows
CLEFT_MIN = 0.03        # L: a drawn pocket this deep is a cleft the hand's shape carries (the three-quarter's far hand,
                        # its thumb behind the fingers: 0.015)


def grade(key, v, ours=None):
    p, w = LIMITS[key]
    if key == 'cleft':
        return 'PASS' if p[0] <= v <= p[1] else 'WARN' if w[0] <= v <= w[1] else 'FAIL'
    if key == 'digits' and ours is not None and ours < 2:
        return 'FAIL'
    if key == 'shape':
        return 'PASS' if v >= p else 'WARN' if v >= w else 'FAIL'
    v = abs(v)
    return 'PASS' if v <= p else 'WARN' if v <= w else 'FAIL'


def arm_axis(skin, cuff, ppl, reach=ARM_REACH):
    """the arm's direction through a cuff (image (x, y), pointing down the arm, toward the hand) from the skin within
    reach L of it (the forearm above and the hand below: their long axis), and the cuff's centroid -> (c, u) or None."""
    from scipy import ndimage
    rs, cs = np.nonzero(cuff)
    if len(rs) < MIN_PX:
        return None
    c = np.array([cs.mean(), rs.mean()])
    near = skin & (ndimage.distance_transform_edt(~cuff) <= reach * ppl)
    ra, ca = np.nonzero(near)
    if len(ra) < 50:
        return None
    P = np.c_[ca, ra].astype(float)
    w, U = np.linalg.eigh(np.cov((P - P.mean(0)).T))
    u = U[:, np.argmax(w)]
    if u[1] < 0:                              # down the arm: the hands hang below their cuffs in every view drawn
        u = -u
    return c, u


def hand_mask(skin, cuff, ppl, reach=HAND_REACH):
    """a hand in one view: the skin past its cuff's middle along the arm, within reach L of the cuff, in pieces touching
    the cuff -> dict(mask, c (the cuff's centroid, x y px), u (down the arm), end (the cuff's far edge along u, L from
    c)) or None."""
    from scipy import ndimage
    got = arm_axis(skin, cuff, ppl)
    if got is None:
        return None
    c, u = got
    from .bodymeasure import window
    w = window(cuff, pad=int(reach * ppl) + 2)
    sk, cf = skin[w], cuff[w]
    yy, xx = np.mgrid[w[0], w[1]]
    s = ((xx - c[0]) * u[0] + (yy - c[1]) * u[1]) / ppl
    cand = sk & (s > 0) & (ndimage.distance_transform_edt(~cf) <= reach * ppl)
    lab, n = ndimage.label(cand)
    keep = np.unique(lab[ndimage.binary_dilation(cf, iterations=3) & cand])
    m = np.zeros(skin.shape, bool)
    m[w] = np.isin(lab, keep[keep > 0])
    if m.sum() < MIN_PX:
        return None
    return dict(mask=m, c=c, u=u, end=float(np.percentile(s[cf], 98)))


def coords(shape, c, u, ppl):
    """per pixel: (s along u, t across it), L from c."""
    yy, xx = np.mgrid[:shape[0], :shape[1]]
    dx, dy = xx - c[0], yy - c[1]
    return (dx * u[0] + dy * u[1]) / ppl, (-dx * u[1] + dy * u[0]) / ppl


def reach(h, ppl):
    """how far a hand reaches past its cuff's far edge along the arm (L)."""
    s, _ = coords(h['mask'].shape, h['c'], h['u'], ppl)
    return float(np.percentile(s[h['mask']], 99.5) - h['end'])


def digits(h, seams, ppl, bands=DIGIT_BANDS, edge=EDGE_PX):
    """the digits bands across the fingers show (see the module doc): per band at a share of the reach past the cuff,
    the hand's runs across it and the seams inside each run, a seam counting only more than edge px inside the hand
    (the drawn outline's own ink, and our depth falling away at the silhouette, are the outline) -> (the median over
    the bands, per band)."""
    from scipy import ndimage
    from .bodymeasure import window
    m = h['mask']
    w = window(m, pad=2)
    inner = np.zeros(m.shape, bool)
    inner[w] = seams[w] & m[w] & (ndimage.distance_transform_edt(m[w]) > edge)
    s, t = coords(m.shape, h['c'], h['u'], ppl)
    r = reach(h, ppl)
    out = []
    for f in bands:
        a = h['end'] + f * r
        band = m & (np.abs(s - a) <= 0.75 / ppl)
        if not band.any():
            out.append(0)
            continue
        tb = np.round(t[band] * ppl).astype(int)
        lo = tb.min()
        occ = np.zeros(tb.max() - lo + 1, bool)
        occ[tb - lo] = True
        sm = np.zeros(len(occ), bool)
        sm[tb[inner[band]] - lo] = True
        runs = int(np.sum(occ[1:] & ~occ[:-1]) + occ[0])
        seam_runs = int(np.sum(sm[1:] & ~sm[:-1]) + sm[0])
        out.append(runs + seam_runs)
    return int(np.median(out)), out


def cleft(m, ppl):
    """the deepest pocket between a mask's silhouette and its convex hull (L), and the pockets 0.01 L deep or more."""
    from scipy import ndimage
    from skimage.morphology import convex_hull_image
    from .bodymeasure import window
    w = window(m, pad=2)
    mm = m[w]
    hull = convex_hull_image(mm)
    pocket = hull & ~mm
    if not pocket.any():
        return 0.0, 0
    depth = ndimage.distance_transform_edt(hull)
    lab, n = ndimage.label(pocket)
    deep = ndimage.maximum(depth, lab, np.arange(1, n + 1)) if n else []
    deep = np.asarray(deep, float) / ppl
    return float(deep.max()), int((deep >= 0.01).sum())


def rotated(m, u_from, u_to):
    """a mask turned about its window's centre so the direction u_from (image x, y) lies along u_to (nearest; the
    window grown to hold it)."""
    from scipy import ndimage
    ang = np.degrees(np.arctan2(u_to[1], u_to[0]) - np.arctan2(u_from[1], u_from[0]))
    if abs(ang) < 0.25:
        return m
    from .bodymeasure import window
    w = window(m, pad=2)
    return ndimage.rotate(m[w].astype(np.uint8), -ang, order=0, reshape=True).astype(bool)


def shape_iou(a, b, ua=None, ub=None):
    """two masks' IoU with b turned so its arm direction ub lies along a's ua (when given) and moved so the centroids
    meet (whole pixels)."""
    if ua is not None and ub is not None:
        b = rotated(b, ub, ua)
    ya, xa = np.nonzero(a)
    yb, xb = np.nonzero(b)
    if not len(ya) or not len(yb):
        return 0.0
    dy, dx = int(round(ya.mean() - yb.mean())), int(round(xa.mean() - xb.mean()))
    pa = set(zip(ya.tolist(), xa.tolist()))
    pb = set(zip((yb + dy).tolist(), (xb + dx).tolist()))
    return len(pa & pb) / float(len(pa | pb))


def shape_iou_visible(a, b, hid, ua=None, ub=None):
    """shape_iou over what shows: b (our whole hand) and hid (its hidden pixels, a subset) turned and moved as b is (on
    b's whole centroid), the IoU over the pixels not hidden -> (IoU, b's visible share)."""
    if ua is not None and ub is not None:
        lab = rotated_labels(b.astype(np.uint8) + hid.astype(np.uint8), ub, ua)
        b, hid = lab >= 1, lab >= 2
    ya, xa = np.nonzero(a)
    yb, xb = np.nonzero(b)
    if not len(ya) or not len(yb):
        return 0.0, 0.0
    dy, dx = int(round(ya.mean() - yb.mean())), int(round(xa.mean() - xb.mean()))
    yh, xh = np.nonzero(hid)
    ph = set(zip((yh + dy).tolist(), (xh + dx).tolist()))
    pa = set(zip(ya.tolist(), xa.tolist())) - ph
    pb = set(zip((yb + dy).tolist(), (xb + dx).tolist())) - ph
    return len(pa & pb) / float(max(1, len(pa | pb))), 1.0 - len(yh) / float(len(yb))


def rotated_labels(m, u_from, u_to):
    """rotated() for a small label image (nearest: labels kept)."""
    from scipy import ndimage
    ang = np.degrees(np.arctan2(u_to[1], u_to[0]) - np.arctan2(u_from[1], u_from[0]))
    from .bodymeasure import window
    w = window(m > 0, pad=2)
    if abs(ang) < 0.25:
        return m[w]
    return ndimage.rotate(m[w], -ang, order=0, reshape=True)


def aligned_pair(a, b, pad=4):
    """two masks cropped and laid on their centroids, on one canvas -> (A, B) (for pictures)."""
    ya, xa = np.nonzero(a)
    yb, xb = np.nonzero(b)
    dy, dx = int(round(ya.mean() - yb.mean())), int(round(xa.mean() - xb.mean()))
    yb, xb = yb + dy, xb + dx
    y0, x0 = min(ya.min(), yb.min()) - pad, min(xa.min(), xb.min()) - pad
    H, W = max(ya.max(), yb.max()) - y0 + pad + 1, max(xa.max(), xb.max()) - x0 + pad + 1
    A, Bm = np.zeros((H, W), bool), np.zeros((H, W), bool)
    A[ya - y0, xa - x0] = True
    Bm[yb - y0, xb - x0] = True
    return A, Bm


# ------------------------------------------------------------------------------------------------------ ours and theirs
def shells(T, n):
    """a mesh's connected pieces: per triangle its shell's id."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    T = np.asarray(T)
    if not len(T):
        return np.zeros(0, int)
    r = np.r_[T[:, 0], T[:, 1], T[:, 2]]
    c = np.r_[T[:, 1], T[:, 2], T[:, 0]]
    _, lab = connected_components(coo_matrix((np.ones(len(r)), (r, c)), shape=(n, n)), directed=False)
    return lab[T[:, 0]]


def our_seams(B, ppl, az3, O, names, views=VIEWS):
    """where our render draws a line inside the skin, per view: two of the skin's shells meeting (a finger laid on the
    palm or its neighbour) or the depth stepping by SEAM_DEPTH L between neighbouring pixels (a finger in front of
    another) -> {view: bool image}. O: pieceqa.our_labels' (its depth)."""
    from . import bodyqa, qa3d
    from .faceqa import zbuffer
    meshes, names_ = qa3d.scene_objects(B)
    skin = {i for i, n in enumerate(names_) if n in _skin_names(B, names_)}
    obj = []
    for i, (V, T, _) in enumerate(meshes):
        if i in skin:
            obj.append((V, T, shells(T, len(V))))
        else:
            obj.append((V, T, np.full(len(T), -2)))
    As = B.assembly
    iw = np.array(qa3d.iris_centres(B))
    az = bodyqa.azimuths(az3)
    L = float(As['L'])
    out = {}
    for v in views:
        if v not in O:
            continue
        org = bodyqa.origin(v, az[v], iw, As['centre'])
        _, sh = zbuffer(obj, az[v], org, L, 1.0 / ppl, bodyqa.WIN)
        d = np.nan_to_num(np.asarray(O[v]['depth'], float) / L, nan=1e3, posinf=1e3, neginf=-1e3)
        sk = sh >= 0
        seam = np.zeros(sh.shape, bool)
        for a, b in (((slice(None), slice(1, None)), (slice(None), slice(None, -1))),
                     ((slice(1, None), slice(None)), (slice(None, -1), slice(None)))):
            both = sk[a] & sk[b]
            step = both & ((sh[a] != sh[b]) | (np.abs(d[a] - d[b]) > SEAM_DEPTH))
            seam[a] |= step
            seam[b] |= step
        out[v] = seam
    return out


def our_hidden(B, ppl, az3, names, pm, views=VIEWS):
    """our hands z-buffered alone (each hand's shells: the skin's shells lying wholly within HAND_3D L of its wrist
    band's centre and below it; with the band) against the whole figure, per view and side -> {(view, side):
    dict(hand (the hand alone), cuff (its band alone), hidden (the hand alone where the figure shows something else in
    front))}, on the design's grids (pieceqa.our_labels'). Empty where the skin or a band isn't found."""
    from . import bodyqa, qa3d
    from .faceqa import zbuffer
    meshes, names_ = qa3d.scene_objects(B)
    sk = [i for i, n in enumerate(names_) if n in _skin_names(B, names_)]
    if not sk:
        return {}
    V, T, _ = meshes[sk[0]]
    V, T = np.asarray(V, float), np.asarray(T)
    L = float(B.assembly['L'])
    sh = shells(T, len(V))
    obj = [(V_, T_, np.full(len(T_), i)) for i, (V_, T_, _) in enumerate(meshes)]
    HAND = {'L': 10000, 'R': 10001}
    hand_tri, band_ids = {}, {}
    for side in ('L', 'R'):
        want = {m[0] if isinstance(m, (tuple, list)) else m for m in pm.get('cuff_' + side, [])}
        ids = [i for i, n in enumerate(names_) if n in want]
        if not ids:
            continue
        C = np.concatenate([np.asarray(meshes[i][0], float) for i in ids])
        c = C.mean(0)
        far = np.linalg.norm(V[T].reshape(-1, 3) - c, axis=1).reshape(len(T), 3).max(1) > HAND_3D * L
        out = np.zeros(sh.max() + 1, bool)
        np.logical_or.at(out, sh, far)
        cz = np.zeros(sh.max() + 1)
        np.add.at(cz, sh, V[T].mean(1)[:, 2])
        cz /= np.maximum(np.bincount(sh, minlength=len(cz)), 1)
        mine = ~out[sh] & (cz[sh] < c[2])
        if mine.any():
            hand_tri[side], band_ids[side] = mine, ids
    if not hand_tri:
        return {}
    rest = ~np.any(list(hand_tri.values()), axis=0)
    full = [o for i, o in enumerate(obj) if i != sk[0]] + [(V, T[rest], np.full(rest.sum(), sk[0]))]
    full += [(V, T[m], np.full(m.sum(), HAND[s])) for s, m in hand_tri.items()]
    As = B.assembly
    iw = np.array(qa3d.iris_centres(B))
    az = bodyqa.azimuths(az3)
    got = {}
    for v in views:
        org = bodyqa.origin(v, az[v], iw, As['centre'])
        _, lab = zbuffer(full, az[v], org, L, 1.0 / ppl, bodyqa.WIN)
        for s, m in hand_tri.items():
            if s not in sides(v):
                continue
            alone = [(V, T[m], np.full(m.sum(), HAND[s]))] + [obj[i] for i in band_ids[s]]
            _, la = zbuffer(alone, az[v], org, L, 1.0 / ppl, bodyqa.WIN)
            hand = la == HAND[s]
            hid = hand & (lab != HAND[s])
            by = {}
            for k in np.unique(lab[hid]):
                n = 'nothing' if k < 0 else 'her own skin' if k == sk[0] else 'the other hand' if k >= 10000 else names_[k]
                by[n] = by.get(n, 0) + int((lab[hid] == k).sum())
            got[(v, s)] = dict(hand=hand, cuff=np.isin(la, band_ids[s]), hidden=hid, by=by)
    return got


def _skin_names(B, names):
    got = [o.name for o in B.objects(groups=('skin',))]
    return [n for n in names if n in got] or [n for n in names if n.endswith('_skin')]


def design_seams(dv, views=VIEWS):
    """the design's ink inside its figures (its raw classes' line pixels), per view -> {view: bool image}."""
    from .bodyqa import CLASS
    return {v: (dv[v]['raw'] == CLASS['line']) for v in views if v in dv and dv[v].get('raw') is not None}


def sides(view):
    return ('L',) if view == 'profile' else ('L', 'R')


def hands_of(skin, cuffs, ppl):
    """{side: hand_mask()} for one view: cuffs {side: mask}."""
    return {s: hand_mask(skin, m, ppl) for s, m in cuffs.items() if m is not None and m.sum() >= MIN_PX}


def features(h, seams, ppl):
    """what the checks read of one hand -> dict(px, reach, digits, per_band, cleft, pockets, width)."""
    m = h['mask']
    n, per = digits(h, seams, ppl)
    cd, pk = cleft(m, ppl)
    _, t = coords(m.shape, h['c'], h['u'], ppl)
    return dict(px=int(m.sum()), reach=round(reach(h, ppl), 4), digits=int(n), per_band=per, cleft=round(cd, 4),
                pockets=pk, width=round(float(np.percentile(t[m], 99) - np.percentile(t[m], 1)), 4))


@qa_part('hands', order=1785, prefix='hand_', table='hands')
def hands(B, design=None, out=None):
    return measure(B, design, out)


def measure(B, design, out=None):
    from . import bodymeasure, pieceqa
    from .bodyqa import CLASS
    ctx = design.sheet_context()
    if 'why' in ctx:
        return None, {'hands': {'status': 'SKIPPED', 'why': ctx['why']}}
    got = bodymeasure.piece_masks(B.spec)
    if got is None:
        return None, {'hands': {'status': 'SKIPPED', 'why': 'no outfit_masks produced for this spec'}}
    masks, graph, paths = got
    for p in paths:
        design._rec(p)
    ppl, az3 = ctx['ppl'], ctx['az3']
    pm = bodymeasure.piece_map(graph, B.spec)
    dv = design.design_views()
    O, names = pieceqa.our_labels(B, ppl, az3)
    seams_o = our_seams(B, ppl, az3, O, names)
    seams_d = design_seams(dv)
    hidden = our_hidden(B, ppl, az3, names, pm)
    skin_ids = [i + k for i, n in enumerate(names) if n in _skin_names(B, names) for k in (0, 1000)]
    T, C, shape = {}, {}, {'L': {}, 'R': {}}
    whole, seen = {'L': {}, 'R': {}}, {'L': {}, 'R': {}}
    pics = []
    for v in VIEWS:
        if v not in dv or v not in O:
            continue
        cls, fg = dv[v]['cls'], dv[v]['fg']
        lab = O[v]['lab']
        skin_d = fg & (cls == CLASS['skin'])
        skin_o = np.isin(lab, skin_ids)
        for s in sides(v):
            pid = 'cuff_' + s
            md = masks.get('%s__%s' % (v, pid))
            if md is None or md.sum() < MIN_PX or pid not in pm:
                continue
            md = md[:cls.shape[0], :cls.shape[1]]
            hd = hand_mask(skin_d, md, ppl)
            if hd is None:
                continue
            fd = features(hd, seams_d.get(v, np.zeros(cls.shape, bool)), ppl)
            mo = pieceqa.members(lab, names, pm, pid)
            ho = hand_mask(skin_o, mo, ppl) if mo.sum() >= MIN_PX else None
            fo = features(ho, seams_o.get(v, np.zeros(lab.shape, bool)), ppl) if ho is not None else None
            key = '%s_%s' % (v, s)
            T[key] = dict(ours=fo, design=fd)
            if fo is None:
                why = 'our hand not found past our cuff' if mo.sum() >= MIN_PX else 'our cuff not seen'
                shape[s][v] = 0.0
                for k in ('reach', 'digits', 'cleft'):
                    if (k == 'digits' and fd['digits'] < 2) or (k == 'cleft' and fd['cleft'] < CLEFT_MIN):
                        continue
                    C['%s_%s_%s' % (v, k, s)] = {'value': None, 'status': 'FAIL', 'design': fd[k], 'why': why}
                continue
            H = hidden.get((v, s))
            ha = hand_mask(H['hand'], H['cuff'], ppl) if H is not None and H['cuff'].sum() >= MIN_PX else None
            hid = H['hidden'] & ha['mask'] if ha is not None else None
            if ha is not None and hid.sum() > 0.02 * ha['mask'].sum():
                iou, vis = shape_iou_visible(hd['mask'], ha['mask'], hid, hd['u'], ha['u'])
                whole[s][v] = round(shape_iou(hd['mask'], ha['mask'], hd['u'], ha['u']), 4)
                fo['reach'] = round(reach(ha, ppl), 4)          # (the whole hand's)
            else:
                iou, vis = shape_iou(hd['mask'], ho['mask'], hd['u'], ho['u']), 1.0
            shape[s][v] = round(iou, 4)
            seen[s][v] = round(vis, 3)
            T[key]['iou'] = round(iou, 4)
            T[key]['visible'] = round(vis, 3)
            for k, note in (('reach', "how far the hand reaches past its cuff along the arm (L), ours minus the "
                                      "design's"),
                            ('digits', "the digits a band across the fingers shows (runs and the seams inside them, "
                                       "the median over bands at 55-90% of the reach), ours minus the design's"),
                            ('cleft', "the deepest pocket between the hand's silhouette and its convex hull (the "
                                      "thumb's cleft, spread fingers), ours over the design's")):
                if (k == 'digits' and fd['digits'] < 2) or (k == 'cleft' and fd['cleft'] < CLEFT_MIN):
                    continue
                if k in ('digits', 'cleft') and vis < VISIBLE_MIN:
                    C['%s_%s_%s' % (v, k, s)] = {'value': None, 'status': 'INFO', 'design': fd[k], 'ours': fo[k],
                                                 'why': 'our hand is %d%% hidden in this view (behind %s)'
                                                        % (round(100 * (1 - vis)), max(H['by'], key=H['by'].get)),
                                                 'note': note}
                    continue
                d_ = fo[k] / fd[k] if k == 'cleft' else fo[k] - fd[k]
                C['%s_%s_%s' % (v, k, s)] = {'value': round(d_, 4) if k != 'digits' else int(d_),
                                             'status': grade(k, d_, fo[k]), 'ours': fo[k], 'design': fd[k],
                                             'note': note}
            if out:
                if vis < 1.0:
                    lab_ = rotated_labels(ha['mask'].astype(np.uint8) + hid.astype(np.uint8), ha['u'], hd['u'])
                    pics.append((key, hd['mask'], lab_ >= 1, iou, lab_ >= 2))
                else:
                    pics.append((key, hd['mask'], rotated(ho['mask'], ho['u'], hd['u']), iou, None))
    for s in ('L', 'R'):
        if not shape[s]:
            continue
        worst = min(shape[s].values())
        C['shape_' + s] = {'value': round(worst, 4), 'status': grade('shape', worst), 'views': shape[s],
                           'visible': seen[s], 'whole': whole[s] or None,
                           'note': "the hand's silhouette IoU with the drawn hand's per view, laid on their centroids "
                                   "(its own shape; the arm's pose is body_*_arms'), the worst view; where ours is "
                                   "partly hidden, over what shows (visible: its share; whole: the whole silhouette's)"}
    if out and pics:
        _picture(pics, out)
    return T, C


def _picture(pics, out):
    """qa_hands.png: per view and side the drawn hand (grey), ours (red outline) laid on it, the IoU above; where ours
    is partly hidden, its whole silhouette, the hidden part blue (not graded)."""
    import os
    from PIL import Image, ImageDraw
    from scipy import ndimage
    tiles = []
    for key, d, o, iou, hid in pics:
        A, Bm = aligned_pair(d, o)
        img = np.full(A.shape + (3,), 255, np.uint8)
        img[A] = (170, 170, 170)
        if hid is not None:
            _, Hm = aligned_pair(o, hid)                 # (hid in o's frame: laid as o is)
            ya, xa = np.nonzero(d); yo, xo = np.nonzero(o); yh, xh = np.nonzero(hid)
            dy, dx = int(round(ya.mean() - yo.mean())), int(round(xa.mean() - xo.mean()))
            y0, x0 = min(ya.min(), yo.min() + dy) - 4, min(xa.min(), xo.min() + dx) - 4
            yy, xx = yh + dy - y0, xh + dx - x0
            ok = (yy >= 0) & (yy < img.shape[0]) & (xx >= 0) & (xx < img.shape[1])
            img[yy[ok], xx[ok]] = (150, 190, 235)
        img[Bm & ~ndimage.binary_erosion(Bm)] = (220, 30, 30)
        img = np.kron(img, np.ones((2, 2, 1), np.uint8))
        canvas = np.full((img.shape[0] + 16, max(img.shape[1], 120), 3), 255, np.uint8)
        canvas[16:, :img.shape[1]] = img
        im = Image.fromarray(canvas)
        ImageDraw.Draw(im).text((2, 2), '%s %.2f' % (key, iou), fill=(0, 0, 0))
        tiles.append(np.asarray(im))
    H = max(t.shape[0] for t in tiles)
    row = np.concatenate([np.pad(t, ((0, H - t.shape[0]), (0, 6), (0, 0)), constant_values=255) for t in tiles], 1)
    Image.fromarray(row).save(os.path.join(out, 'qa_hands.png'))
