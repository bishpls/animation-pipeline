"""Garment piece details (tool/garments2, docs/workstreams/garments2.md): the faults Michael sees in the outfit's pieces
that the piece IoUs (qa3d.sheet_pieces) average away, each measured on the design's grids (bodyqa's: the sheet's scale,
aligned on the eyes) against the design's own drawn piece masks measured the same way.

Checks (qa3d part 'piece_details'; lengths in L):
  sleeve_{front,three_quarter,back}_rough_{L,R}
        the puff sleeve's outline roughness (detailqa.outline_roughness: the 95th percentile of its outline's distance
        to its own smoothed outline) beyond the design's: a torn or stepped cap
  sleeve_{front,three_quarter,profile,back}_spikes_{L,R}
        spikes on the sleeve's cap (its upper CAP along the arm) where its outline is the silhouette: the parts of its
        mask an opening by a disk of radius SPIKE_R L cuts off that stand out of the opened mask by SPIKE_MIN L or more
        (a thin horn or a pointed cap corner), counted beyond the design's; the value is the deepest one's depth beyond
        the design's deepest (L), the counts beside it
  sleeve_{view}_profile_{L,R}
        the puff's width across its arm at tenths from its cap to its cuff: the RMS against the design's (the pear)
  sleeve_standoff_{L,R}
        3D: the puff seen along its arm, its radius over the arm's under its band, against sleeve_closeup's
        cross-section (segmented from the reference)
  waistband_{view}_rows, waistband_{view}_width, waistband_profile_overhang
        the band's top and bottom edges and its width against the design's (its drawn mask's part inside the ink,
        ink_core: the masks give it the jacket's lower part where the jacket hangs over it; not in profile, where the
        mask holds none of the band); in profile, the jacket's front edge over the band's (the figures' front edges at
        fixed rows: OVERHANG_TOP, OVERHANG_BAND) against the design's (the jacket overhangs the band)
  shorts_{view}_hem, shorts_{front,back}_width
        the shorts' lower edge and their width against the design's
  top_{front,three_quarter}_over_band
        at the jacket/band junction, the share of its columns where our band hides the jacket (drawn alone, the jacket
        reaches down behind the band: its hem tucked under), where the design's jacket and bib hang over the band's top
  top_front_opening, top_front_hem_step
        the jacket's open front: the cream bib's half-width between its fronts below the bow's tails, RMS against the
        design's; the junction's drop from the jacket's fronts to the bib's middle, against the design's
  {collar,bow}_{view}_torn
        the piece's outline roughness, ours drawn FINE x finer round the chest, beyond the design's, and its fragments
        against the design's (the torn lapel tips and bow edges)
  bow_front_flare, bow_front_tail_width, bow_front_tail_gap
        the bow in front: its lobes' height at their ends over at the knot (a bow tie, not a pillow); its tails' width
        and the gap between them low down (they part as they fall), against the design's
  cuff_{front,back}_{flare,trim}_{L,R}
        the wrist cuff across its arm (the forearm's and hand's skin round it give the arm's direction): its width at its
        top over its bottom (a cup, wider at the elbow's side; the blocky band bulged, wider at its bottom), and its
        cream share (the top band and the front tab), against the design's
The design is measured the same way wherever it has the view; a view where either side shows too little of the piece
(MIN_PX drawn or ours) is skipped.

    table, checks = pieceqa.measure(B, design)      # charkit.qa3d's 'piece_details' part
"""
import numpy as np

from . import bodyqa

WIN = bodyqa.WIN
SPIKE_R = 0.03                      # L: the opening's disk radius (a protrusion thinner than twice this is a spike candidate)
SPIKE_MIN = 0.012                   # L: ... that stands this far out of the opened mask
SPIKE_BAND = 0.03                   # L: a spike this close to the piece's band (the sleeve's cuff) is the corner where
                                    # the puff meets it, drawn in the design too: not counted
CAP = 0.55                          # spikes are looked for on the sleeve's cap, its upper share along the arm (the
                                    # shoulder poofs; lower down the drawn masks' inner corners are cutting slivers)
MIN_PX = 150                        # a view's piece mask this small (either side) is not measured
FINE = 3                            # ours drawn this many times finer than the grid for the torn-edge checks (the collar's
                                    # and the bow's jagged tips are a few grid pixels)
CHEST = dict(x=0.9, top=-0.25, bottom=-1.4)          # L round the eyes: the window the collar and the bow are drawn in
HIDDEN = 0.4                        # a view that shows less than this share of a piece's drawn pixels in front (the far
                                    # sleeve in three-quarter, behind the bow): its width along the arm isn't measured
LIMITS = {                          # (pass within, warn within); else fail
    'rough': (0.007, 0.014),        # L beyond the design's (1.5 and 3 px: under that is the grid's pixel)
    'spike': (0.006, 0.015),        # L: the deepest spike beyond the design's deepest
    'standoff': (0.10, 0.20),       # |ours / design - 1| of the puff's radius over the arm's, seen along the arm
    'profile': (0.02, 0.04),        # L: the RMS of the puff's width along its arm against the design's
    'rows': (0.02, 0.04),           # L: a band's top and bottom edges (or the shorts' hem) against the design's
    'width': (0.05, 0.10),          # |ours / design - 1| of a band's width
    'overhang': (0.015, 0.03),      # L: the top's front edge over the band's in profile against the design's
    'flare': (0.08, 0.15),          # |ours - design| of a cuff's width at its top over its width at its bottom
    'trim': (0.08, 0.15),           # |ours - design| of the cream share of a cuff's pixels
    'order': (0.1, 0.3),            # share of the jacket/band junction's columns where our band hides the jacket
    'opening': (0.02, 0.04),        # L: RMS of the jacket's front opening's half-width (the cream bib) against the design's
    'hem_step': (0.015, 0.03),      # L: |ours - design| of the junction's drop from the jacket to the bib's middle
    'torn': (0.004, 0.008),         # L: a piece's outline roughness (ours drawn at FINE x the grid) beyond the design's
    'bow_flare': (0.25, 0.5),       # |ours - design| of the bow's lobes' height at their ends over at the knot
    'tail_width': (0.15, 0.3),      # |ours / design - 1| of the bow tails' width
    'tail_gap': (0.03, 0.06),       # L: |ours - design| of the gap between the bow's tails low down
}
SLEEVE_VIEWS = ('front', 'three_quarter', 'profile', 'back')
CLOSE = 0.012                       # L: a drawn piece mask is closed by a disk this wide and its holes filled before its
                                    # outline is measured: the drawing's fold strokes inside a piece are cut out of its
                                    # mask as slits (ours are closed the same way)
FREE = 0.025                        # L: an outline pixel within this of the background (nothing drawn) is the silhouette
                                    # (the drawing's outline stroke, about 0.02 L wide, lies between its mask and it)


def grade(key, v):
    p, w = LIMITS[key]
    return 'PASS' if v <= p else 'WARN' if v <= w else 'FAIL'


def worst(*ss):
    order = {'FAIL': 0, 'WARN': 1, 'PASS': 2}
    ss = [s for s in ss if s in order]
    return min(ss, key=lambda s: order[s]) if ss else 'SKIPPED'


# ------------------------------------------------------------------------------------------------------------ measures
def disk(r):
    """a disk structuring element of radius r pixels."""
    n = int(np.ceil(r))
    y, x = np.mgrid[-n:n + 1, -n:n + 1]
    return x * x + y * y <= r * r + 1e-9


def spikes(m, ppl, r=SPIKE_R, min_depth=SPIKE_MIN, where=None, away=None):
    """a mask's spikes: the components of what an opening by a disk of radius r L cuts off that reach min_depth L or
    more out of the opened mask (with `where`: only those touching it, the silhouette; with `away`: not those touching
    it, the corners where a piece meets its band). -> dict(n, depth (the deepest, L; 0 without one), depths [L...],
    at [(row, col)...])."""
    from scipy import ndimage
    if not m.any():
        return dict(n=0, depth=0.0, depths=[], at=[])
    rp = max(1.0, r * ppl)
    pad = int(np.ceil(rp)) + 2
    M = np.pad(m, pad)
    op = ndimage.binary_opening(M, structure=disk(rp))
    cut = M & ~op
    if not op.any():                   # the whole mask is thinner than the disk: no body to stand out of
        return dict(n=0, depth=0.0, depths=[], at=[])
    d = ndimage.distance_transform_edt(~op)
    lab, n = ndimage.label(cut, structure=np.ones((3, 3)))
    W = np.pad(where, pad) if where is not None else None
    X = np.pad(away, pad) if away is not None else None
    depths, at = [], []
    for k in range(1, n + 1):
        sel = lab == k
        if W is not None and not (sel & W).any():
            continue
        if X is not None and (sel & X).any():
            continue
        dk = d[sel]
        i = int(np.argmax(dk))
        depth = float(dk[i]) / ppl
        if depth >= min_depth:
            rr, cc = np.nonzero(sel)
            depths.append(round(depth, 4))
            at.append((int(rr[i] - pad), int(cc[i] - pad)))
    order = np.argsort(depths)[::-1]
    depths = [depths[i] for i in order]
    at = [at[i] for i in order]
    return dict(n=len(depths), depth=depths[0] if depths else 0.0, depths=depths, at=at)


def clean(m, ppl, r=CLOSE):
    """a piece mask closed by a disk of radius r L (the drawing's strokes inside it: slits) and its holes filled."""
    from scipy import ndimage
    if not m.any():
        return m
    rp = max(1.0, r * ppl)
    pad = int(np.ceil(rp)) + 2
    M = ndimage.binary_closing(np.pad(m, pad), structure=disk(rp))
    return ndimage.binary_fill_holes(M)[pad:-pad, pad:-pad]


def silhouette(m, fg, ppl, free=FREE):
    """a mask's outline pixels within `free` L of the background (fg False): where it is the figure's silhouette."""
    from scipy import ndimage
    edge = m & ~ndimage.binary_erosion(m)
    bg = ndimage.distance_transform_edt(fg) <= free * ppl
    return edge & bg


def outline_roughness(m, ppl, sigma=0.01, where=None):
    """detailqa.outline_roughness, over the outline pixels `where` (default all)."""
    from scipy import ndimage
    if not m.any():
        return None
    sm = ndimage.gaussian_filter(m.astype(float), sigma * ppl) > 0.5
    a = m & ~ndimage.binary_erosion(m)
    if where is not None:
        a &= where
    b = sm & ~ndimage.binary_erosion(sm)
    if not b.any() or not a.any():
        return None
    d = ndimage.distance_transform_edt(~b)
    return round(float(np.percentile(d[a], 95)) / ppl, 4)


def cap_region(Ms, Mc, share=CAP):
    """the pixels of a sleeve's upper `share` along its arm (the sleeve and its cuff's long axis, from the sleeve's top
    toward the cuff) -> bool image, or None."""
    rs, cs = np.nonzero(Ms)
    rc, cc = np.nonzero(Mc) if Mc is not None else (np.zeros(0, int), np.zeros(0, int))
    if len(rs) < 20 or len(rc) < 5:
        return None
    P = np.c_[np.r_[cs, cc], np.r_[rs, rc]].astype(float)
    m = P.mean(0)
    w, U = np.linalg.eigh(np.cov((P - m).T))
    u = U[:, np.argmax(w)]
    if (np.array([cc.mean(), rc.mean()]) - np.array([cs.mean(), rs.mean()])) @ u < 0:
        u = -u
    yy, xx = np.mgrid[:Ms.shape[0], :Ms.shape[1]]
    s_ = (xx - m[0]) * u[0] + (yy - m[1]) * u[1]
    ss = s_[Ms]
    lo, hi = np.percentile(ss, 1), np.percentile(ss, 99)
    return s_ <= lo + share * (hi - lo)


def arm_profile(Ms, Mc, skin, ppl, above=(0.01, 0.04), below=(0.03, 0.08)):
    """a puff sleeve's widths across its arm in one view, from its mask Ms, its cuff's Mc and the arm's skin: the arm's
    direction is the long axis of the sleeve and cuff together (pointing from the sleeve to the cuff); across it, the
    puff's widest, its width just above the cuff (`above` L over the cuff's top: the gathers into the band), the cuff's
    and the bare arm's just below the cuff (`below` L under its lower edge). -> dict(puff, above, cuff, arm (L), and the
    ratios standoff = puff / arm, gather = above / puff) or None."""
    rs, cs = np.nonzero(Ms)
    rc, cc = np.nonzero(Mc)
    if len(rs) < MIN_PX or len(rc) < 20:
        return None
    P = np.c_[np.r_[cs, cc], np.r_[rs, rc]].astype(float)
    m = P.mean(0)
    w, U = np.linalg.eigh(np.cov((P - m).T))
    u = U[:, np.argmax(w)]
    cS, cC = np.array([cs.mean(), rs.mean()]), np.array([cc.mean(), rc.mean()])
    if (cC - cS) @ u < 0:
        u = -u
    v = np.array([-u[1], u[0]])

    def coords(r, c):
        Q = np.c_[c, r].astype(float) - m
        return Q @ u / ppl, Q @ v / ppl

    ss, vs = coords(rs, cs)
    sc, vc = coords(rc, cc)
    top, bot = np.percentile(sc, 5), np.percentile(sc, 95)

    def width(s_, v_, a, b):
        k = (s_ >= a) & (s_ <= b)
        if k.sum() < 3:
            return None
        # per station of one pixel along the axis, the extent across; their median over [a, b]
        st = np.round(s_[k] * ppl).astype(int)
        ws = [v_[k][st == q].max() - v_[k][st == q].min() for q in np.unique(st) if (st == q).sum() >= 2]
        return float(np.median(ws)) if ws else None
    # the puff's widest: the widest of its stations (a running median over 0.03 L)
    st = np.round(ss * ppl).astype(int)
    qs = np.unique(st)
    wq = np.array([vs[st == q].max() - vs[st == q].min() for q in qs])
    k = max(1, int(round(0.03 * ppl)))
    wq = np.array([np.median(wq[max(0, i - k):i + k + 1]) for i in range(len(wq))])
    puff = float(wq.max())
    ab = width(ss, vs, top - above[1], top - above[0])
    cuff = width(sc, vc, top, bot)
    arm = None
    if skin is not None and skin.any():
        ra, ca = np.nonzero(skin)
        sa, va = coords(ra, ca)
        near = np.abs(va) < 1.5 * max(puff, 1e-6)
        arm = width(sa[near], va[near], bot + below[0], bot + below[1])
    out = dict(puff=round(puff, 4), above=None if ab is None else round(ab, 4), cuff=None if cuff is None else round(cuff, 4),
               arm=None if arm is None else round(arm, 4))
    out['standoff'] = round(puff / arm, 3) if arm else None
    out['gather'] = round(ab / puff, 3) if ab else None
    # the width along the arm, from the sleeve's top (0) to the cuff's top (1), in tenths
    s0 = float(np.percentile(ss, 1))
    fr = (qs / ppl - s0) / max(1e-6, top - s0)
    out['widths'] = [round(float(np.interp(x, fr, wq)), 4) for x in np.linspace(0, 1, 11)]
    return out


def closeup_section(rgb):
    """sleeve_closeup's cross-section (in its lower left quarter: the puff seen along the arm, round the cream band and
    the grey arm): the area-equivalent radii of the puff's outline, the band's and the arm's (px), segmented by colour.
    -> dict(puff, band, arm, standoff = puff / arm, band_arm = band / arm) or None."""
    from scipy import ndimage
    H, W = rgb.shape[:2]
    c = np.asarray(rgb, float)[H // 2:, :W // 2, :3]
    if c.max() > 1.5:
        c = c / 255.0
    R, G, B_ = c[..., 0], c[..., 1], c[..., 2]
    orange = (R > 0.6) & (G < 0.6) & (B_ < 0.45) & (R - G > 0.2)
    cream = (R > 0.85) & (G > 0.8) & (B_ > 0.55) & (B_ < 0.85)
    grey = (np.abs(R - G) < 0.04) & (np.abs(G - B_) < 0.04) & (R > 0.6) & (R < 0.9)

    def biggest(m):
        lab, n = ndimage.label(m)
        if not n:
            return m
        sz = np.bincount(lab.ravel())
        sz[0] = 0
        return lab == sz.argmax()
    fig = biggest(ndimage.binary_fill_holes(ndimage.binary_closing(orange | cream, iterations=3)))
    inner = biggest(ndimage.binary_fill_holes(ndimage.binary_closing(cream & fig, iterations=3)))
    arm = ndimage.binary_fill_holes(biggest(grey & inner))
    if not (fig.sum() and inner.sum() and arm.sum()):
        return None
    r = lambda m: float(np.sqrt(m.sum() / np.pi))
    out = dict(puff=r(fig), band=r(inner), arm=r(arm))
    out['standoff'] = round(out['puff'] / out['arm'], 3)
    out['band_arm'] = round(out['band'] / out['arm'], 3)
    return out


def our_section(B, sleeve, band, skin, nth=72):
    """our puff seen along its arm, as the design's cross-section: the arm's axis the normal of its band's ring (the
    least spread of the band's vertices), the puff's and the band's outlines round it (their vertices' farthest per
    angle), the arm's (the skin within 0.02 L of the band's middle plane) -> the same dict (L) or None."""
    L = float(B.assembly['L'])
    get = lambda n: B.obj(n).mesh('eval')[0] if n in [o.name for o in B.objects()] else None
    Vs, Vb, Vk = get(sleeve), get(band), get(skin)
    if Vs is None or Vb is None or Vk is None:
        return None
    c = Vb.mean(0)
    w, U = np.linalg.eigh(np.cov((Vb - c).T))
    n = U[:, 0]
    e1 = np.cross(n, [0.0, 0.0, 1.0]) if abs(n[2]) < 0.9 else np.cross(n, [1.0, 0.0, 0.0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(n, e1)

    def polar(V, keep=None):
        Q = V - c
        if keep is not None:
            Q = Q[keep(Q)]
        a = np.arctan2(Q @ e2, Q @ e1)
        r = np.hypot(Q @ e1, Q @ e2)
        k = ((a + np.pi) / (2 * np.pi) * nth).astype(int) % nth
        rmax = np.zeros(nth)
        np.maximum.at(rmax, k, r)
        return rmax
    rs = polar(Vs)
    rb = polar(Vb)
    rb_ = rb[rb > 0]
    ra = polar(Vk, lambda Q: (np.abs(Q @ n) < 0.02 * L) & (np.hypot(Q @ e1, Q @ e2) < 1.2 * np.median(rb_)))
    if (rs == 0).any() or (ra == 0).mean() > 0.2:
        return None
    ra = np.where(ra > 0, ra, np.median(ra[ra > 0]))
    eq = lambda r: float(np.sqrt((r ** 2).mean()))           # the area-equivalent radius of a polar outline
    out = dict(puff=eq(rs) / L, band=eq(rb) / L, arm=eq(ra) / L)
    out['standoff'] = round(out['puff'] / out['arm'], 3)
    out['band_arm'] = round(out['band'] / out['arm'], 3)
    return out


# ------------------------------------------------------------------------------------------------------------ our views
def our_labels(B, ppl, az3, views=('front', 'three_quarter', 'profile', 'back')):
    """our objects z-buffered on the design's grids: per view the object label image (index into names; + 1000 for a
    two-sided object's right half: world x < 0) and its depth. -> ({view: dict(lab, depth)}, names)."""
    from . import qa3d
    from .faceqa import zbuffer
    meshes, names = qa3d.scene_objects(B)
    obj = [(V, T, np.where(V[T].mean(1)[:, 0] >= 0, i, i + 1000)) for i, (V, T, _) in enumerate(meshes)]
    As = B.assembly
    iw = np.array(qa3d.iris_centres(B))
    az = bodyqa.azimuths(az3)
    out = {}
    for v in views:
        org = bodyqa.origin(v, az[v], iw, As['centre'])
        depth, lab = zbuffer(obj, az[v], org, As['L'], 1.0 / ppl, WIN)
        out[v] = dict(lab=lab, depth=depth, az=az[v], org=org)
    return out, names


def our_classes(B, ppl, az3, views=('front', 'three_quarter', 'profile', 'back')):
    """our model-sheet classes on the design's grids per view (bodyqa.ours: lines absorbed) -> {view: cls}."""
    from . import qa3d
    from .faceqa import zbuffer
    meshes, _ = qa3d.scene_objects(B)
    As = B.assembly
    iw = np.array(qa3d.iris_centres(B))
    az = bodyqa.azimuths(az3)
    out = {}
    for v in views:
        org = bodyqa.origin(v, az[v], iw, As['centre'])
        _, cl = zbuffer(meshes, az[v], org, As['L'], 1.0 / ppl, WIN, thin=(bodyqa.CLASS['line'],))
        out[v] = bodyqa.ours(cl)[0]
    return out


def members(lab, names, pm, pid):
    from .bodymeasure import member_mask
    idx = {n: i for i, n in enumerate(names)}
    return member_mask(lab, idx, pm.get(pid, []))


# ------------------------------------------------------------------------------------------------------------ the parts
def sleeves(O, names, masks, pm, ppl, dv, skin_names=('clawd_skin',)):
    """the puff sleeves' outline and shape checks per view and side (see the module doc) -> (table, checks). Which
    checks there are depends on the design alone (the views that show the piece), so a build that loses a piece reads
    FAIL, not a missing check."""
    from scipy import ndimage
    from .bodyqa import CLASS as CL
    T, C = {}, {}
    for view in SLEEVE_VIEWS:
        if view not in O or view not in dv:
            continue
        for side in ('L', 'R'):
            pid = 'sleeve_' + side
            Md = masks.get('%s__%s' % (view, pid))
            if Md is None or Md.sum() < MIN_PX or pid not in pm:
                continue
            front = masks.get('front__' + pid)
            seen = Md.sum() / max(1, front.sum()) if front is not None else 1.0
            Md = clean(Md, ppl)
            Mo = clean(members(O[view]['lab'], names, pm, pid), ppl)
            wd = silhouette(Md, dv[view]['fg'], ppl)
            cd_ = masks.get('%s__sleeve_cuff_%s' % (view, side))
            co_ = members(O[view]['lab'], names, pm, 'sleeve_cuff_' + side)
            near = lambda c: (ndimage.distance_transform_edt(~c) <= SPIKE_BAND * ppl) if c is not None and c.any() \
                else None
            capd = cap_region(Md, cd_)
            rd = outline_roughness(Md, ppl, where=wd)
            sd = spikes(Md, ppl, where=wd & capd if capd is not None else wd, away=near(cd_))
            if rd is None:                                        # the design shows no silhouette of it here
                continue
            key = '%s_%s' % (view, side)
            if Mo.sum() < MIN_PX:
                why = {'value': None, 'status': 'FAIL', 'why': "ours shows %d px of the piece here" % int(Mo.sum())}
                C['sleeve_%s_rough_%s' % (view, side)] = dict(why)
                C['sleeve_%s_spikes_%s' % (view, side)] = dict(why)
                if seen >= HIDDEN:
                    C['sleeve_%s_profile_%s' % (view, side)] = dict(why)
                continue
            wo = silhouette(Mo, O[view]['lab'] >= 0, ppl)
            capo = cap_region(Mo, co_)
            ro = outline_roughness(Mo, ppl, where=wo)
            so = spikes(Mo, ppl, where=wo & capo if capo is not None else wo, away=near(co_))
            ro = 0.0 if ro is None else ro                    # (no silhouette of ours here: nothing rough)
            T[key] = dict(ours=dict(rough=ro, spikes=so), design=dict(rough=rd, spikes=sd),
                          px=[int(Mo.sum()), int(Md.sum())])
            v_ = round(max(0.0, ro - rd), 4)
            C['sleeve_%s_rough_%s' % (view, side)] = {
                'value': v_, 'status': grade('rough', v_), 'ours': ro, 'design': rd,
                'note': "the sleeve's silhouette's roughness (the 95th percentile of its outline's distance to its "
                        "own smoothed outline, L) beyond the design's: a torn or stepped cap"}
            v_ = round(max(0.0, so['depth'] - sd['depth']), 4)
            dn = so['n'] - sd['n']
            st_n = 'PASS' if dn <= 0 else 'WARN' if dn == 1 else 'FAIL'
            C['sleeve_%s_spikes_%s' % (view, side)] = {
                'value': v_, 'status': worst(grade('spike', v_), st_n) if so['n'] else 'PASS',
                'count': [so['n'], sd['n']], 'ours': so['depths'], 'design': sd['depths'],
                'note': "spikes on the sleeve's silhouette (what an opening by a disk of radius %.3f L cuts off that "
                        "stands %.3f L or more out of it): the deepest one's depth beyond the design's deepest (L); the "
                        "counts, ours and the design's, beside it" % (SPIKE_R, SPIKE_MIN)}
            # the puff's width along its arm: the pear, narrow at the cap, widest low, gathered into its band
            if seen < HIDDEN:
                continue
            if cd_ is None or cd_.sum() < 20:
                continue
            sk_o = np.isin(O[view]['lab'], [i + k for i, n in enumerate(names) if n in skin_names for k in (0, 1000)])
            pd = arm_profile(Md, clean(cd_, ppl), dv[view]['cls'] == CL['skin'], ppl)
            po = arm_profile(Mo, clean(co_, ppl), sk_o, ppl) if co_.sum() >= 20 else None
            if not pd:
                continue
            T[key]['profile'] = dict(ours=po, design=pd)
            if not po:
                C['sleeve_%s_profile_%s' % (view, side)] = {'value': None, 'status': 'FAIL',
                                                             'why': 'our sleeve or its cuff is too small here'}
                continue
            dw = np.array(po['widths'][1:-1]) - np.array(pd['widths'][1:-1])
            v_ = round(float(np.sqrt((dw ** 2).mean())), 4)
            C['sleeve_%s_profile_%s' % (view, side)] = {
                'value': v_, 'status': grade('profile', v_), 'ours': po['widths'], 'design': pd['widths'],
                'note': "the puff's width across its arm from its top to its cuff (tenths of its length): the RMS "
                        "of ours against the design's (L): the pear, narrow at the cap and widest low"}
    return T, C


def cuff_shape(M, skin, cream, ppl, reach=0.35):
    """a wrist cuff's shape in one view: the arm's direction from the skin within `reach` L of the cuff (the forearm
    above it and the hand below: their long axis), and across it the cuff's width at its top (the elbow's side, 15%
    along), its bottom (85%) and its widest; its cream share. -> dict(top, bottom, widest (L), flare = top / bottom,
    bulge = widest / mean(top, bottom), trim) or None."""
    from scipy import ndimage
    rs, cs = np.nonzero(M)
    if len(rs) < MIN_PX:
        return None
    c = np.array([cs.mean(), rs.mean()])
    near = skin & (ndimage.distance_transform_edt(~M) <= reach * ppl)
    ra, ca = np.nonzero(near)
    if len(ra) < 50:
        return None
    P = np.c_[ca, ra].astype(float)
    w, U = np.linalg.eigh(np.cov((P - P.mean(0)).T))
    u = U[:, np.argmax(w)]
    if u[1] < 0:                                              # pointing down the arm (toward the hand, lower in the view)
        u = -u
    v = np.array([-u[1], u[0]])
    Q = np.c_[cs, rs].astype(float) - c
    s_, t_ = Q @ u / ppl, Q @ v / ppl
    lo, hi = np.percentile(s_, 2), np.percentile(s_, 98)
    st = np.round(s_ * ppl).astype(int)

    def width_at(f, half=0.05):
        a = lo + f * (hi - lo)
        k = np.abs(s_ - a) <= half * (hi - lo)
        ws = [np.ptp(t_[k][st[k] == q]) for q in np.unique(st[k]) if (st[k] == q).sum() >= 2]
        return float(np.median(ws)) if ws else None
    top, bot = width_at(0.15), width_at(0.85)
    wid = max(filter(None, [width_at(f) for f in np.linspace(0.15, 0.85, 8)]), default=None)
    if not top or not bot or not wid:
        return None
    return dict(top=round(top, 4), bottom=round(bot, 4), widest=round(wid, 4), flare=round(top / bot, 3),
                bulge=round(wid / (0.5 * (top + bot)), 3), trim=round(float((cream & M).sum() / M.sum()), 3),
                length=round(float(hi - lo), 4))


def cuffs(O, names, masks, pm, ppl, dv, skin_names, cls_o):
    """the wrist cuffs' shape per view and side: flare, bulge and cream trim against the design's (see the module doc)
    -> (table, checks)."""
    from .bodyqa import CLASS as CL
    T, C = {}, {}
    for view in ('front', 'back'):                           # (in three-quarter and profile the hand and the skirt cut
        if view not in O or view not in dv:                   # the drawn cuffs' lower ends)
            continue
        for side in ('L', 'R'):
            pid = 'cuff_' + side
            Md = masks.get('%s__%s' % (view, pid))
            if Md is None or Md.sum() < MIN_PX or pid not in pm:
                continue
            front = masks.get('front__' + pid)
            if front is not None and Md.sum() < HIDDEN * front.sum():
                continue
            Md = clean(Md, ppl)
            d_ = cuff_shape(Md, dv[view]['cls'] == CL['skin'], dv[view]['cls'] == CL['cream'], ppl)
            if d_ is None:
                continue
            Mo = clean(members(O[view]['lab'], names, pm, pid), ppl)
            sk_o = np.isin(O[view]['lab'], [i + k for i, n in enumerate(names) if n in skin_names for k in (0, 1000)])
            o_ = cuff_shape(Mo, sk_o, cls_o[view] == CL['cream'], ppl) if Mo.sum() >= MIN_PX else None
            T['%s_%s' % (view, side)] = dict(ours=o_, design=d_)
            for key in ('flare', 'trim'):
                name = 'cuff_%s_%s_%s' % (view, key, side)
                if o_ is None:
                    C[name] = {'value': None, 'status': 'FAIL', 'design': d_, 'why': 'our cuff not measured here'}
                    continue
                v_ = round(abs(o_[key] - d_[key]), 3)
                C[name] = {'value': v_, 'status': grade(key, v_), 'ours': o_[key], 'design': d_[key], 'table': o_,
                           'note': {'flare': "the cuff's width at its top (the elbow's side) over its width at its "
                                             "bottom, against the design's (a cup wider at its top)",
                                    'trim': "the cream share of the cuff's pixels (its top band and front tab) "
                                            "against the design's"}[key]}
    return T, C


def fine_labels(B, ppl, az3, views=('front', 'three_quarter', 'profile', 'back'), fine=FINE, win=CHEST):
    """our objects' labels as our_labels', `fine` times finer, in a window round the chest -> ({view: lab}, names)."""
    from . import qa3d
    from .faceqa import zbuffer
    meshes, names = qa3d.scene_objects(B)
    obj = [(V, T, np.where(V[T].mean(1)[:, 0] >= 0, i, i + 1000)) for i, (V, T, _) in enumerate(meshes)]
    As = B.assembly
    iw = np.array(qa3d.iris_centres(B))
    az = bodyqa.azimuths(az3)
    out = {}
    for v in views:
        org = bodyqa.origin(v, az[v], iw, As['centre'])
        out[v] = zbuffer(obj, az[v], org, As['L'], 1.0 / (ppl * fine), win)[1]
    return out, names


def crop_win(m, ppl, win=CHEST):
    """a design-grid mask cut to the chest window (rows and columns of WIN's grid)."""
    r0, r1 = int(round((WIN['top'] - win['top']) * ppl)), int(round((WIN['top'] - win['bottom']) * ppl))
    c0, c1 = int(round((WIN['x'] - win['x']) * ppl)), int(round((WIN['x'] + win['x']) * ppl))
    return m[r0:r1, c0:c1]


def torn(m, ppl):
    """a piece mask's torn-edge measures: its outline's roughness (detailqa's: the 95th percentile distance to its
    smoothed self, L) and its fragments (parts under 2% of its largest). -> (rough, fragments) or None."""
    from .detailqa import fragments
    if m.sum() < 20:
        return None
    r = outline_roughness(m, ppl, sigma=0.01)
    return (r, fragments(m)[0]) if r is not None else None


def bow_shape(lobes, tails, ppl):
    """the bow in front: its lobes' height at their ends (the outer 15% of the half-width) over at the knot (a quarter
    of the half-width out), each side, averaged (a bow tie flares to its ends; a pillow doesn't); its tails' width
    (their rows' median run) and the gap between them 80% of the way down them. -> dict or None."""
    rs, cs = np.nonzero(lobes)
    if len(rs) < MIN_PX:
        return None
    cx = 0.5 * (cs.min() + cs.max())
    hw = 0.5 * (cs.max() - cs.min())

    def height(f):
        hs = []
        for sgn in (-1, 1):
            c = int(round(cx + sgn * f * hw))
            col = lobes[:, max(0, c - 1):c + 2].any(1)
            r = np.nonzero(col)[0]
            if len(r):
                hs.append((r.max() - r.min() + 1) / ppl)
        return float(np.mean(hs)) if hs else None
    end, knot = height(0.85), height(0.25)
    out = dict(width=round(2 * hw / ppl, 4), end=None if end is None else round(end, 4),
               knot=None if knot is None else round(knot, 4))
    out['flare'] = round(end / knot, 3) if end and knot else None
    rt, ct = np.nonzero(tails)
    if len(rt) >= 50:
        t0, t1 = rt.min(), rt.max()
        runs, gaps = [], []
        for r in range(int(t0 + 0.3 * (t1 - t0)), int(t0 + 0.8 * (t1 - t0)) + 1):
            c = np.nonzero(tails[r])[0]
            if not len(c):
                continue
            parts = np.split(c, np.nonzero(np.diff(c) > 1)[0] + 1)
            runs += [len(p_) for p_ in parts if len(p_) > 1]
        r = int(t0 + 0.8 * (t1 - t0))
        c = np.nonzero(tails[r])[0]
        parts = np.split(c, np.nonzero(np.diff(c) > 1)[0] + 1) if len(c) else []
        parts = [p_ for p_ in parts if len(p_) > 1]
        out['tail_width'] = round(float(np.median(runs)) / ppl, 4) if runs else None
        out['tail_gap'] = round(float(parts[-1][0] - parts[0][-1]) / ppl, 4) if len(parts) >= 2 else 0.0
        out['tail_bottom'] = round(float(WIN['top'] - (t1 + 0.5) / ppl), 4)
    return out


def collar_bow(B, O, names, masks, pm, ppl, az3, dv):
    """the collar's and the bow's torn edges (ours drawn FINE x finer round the chest) and the bow's shape in front
    against the design's (see the module doc) -> (table, checks)."""
    T, C = {}, {}
    F, fnames = fine_labels(B, ppl, az3)
    for pid in ('collar', 'bow'):
        if pid not in pm:
            continue
        for view in ('front', 'three_quarter', 'profile', 'back'):
            Md = masks.get('%s__%s' % (view, pid))
            if Md is None or crop_win(Md, ppl).sum() < MIN_PX:
                continue
            d_ = torn(clean(crop_win(Md, ppl), ppl), ppl)
            if d_ is None:
                continue
            Mo = members(F[view], fnames, pm, pid)
            o_ = torn(Mo, ppl * FINE)
            T['%s_%s' % (pid, view)] = dict(ours=o_, design=d_)
            name = '%s_%s_torn' % (pid, view)
            if o_ is None:
                C[name] = {'value': None, 'status': 'FAIL', 'design': d_, 'why': 'ours not seen here'}
                continue
            v_ = round(max(0.0, o_[0] - d_[0]), 4)
            df = o_[1] - d_[1]
            st_f = 'PASS' if df <= 0 else 'WARN' if df <= 1 else 'FAIL'
            C[name] = {'value': v_, 'status': worst(grade('torn', v_), st_f), 'ours': o_, 'design': d_,
                       'note': "the piece's outline roughness (ours drawn %dx finer, the 95th percentile of its outline's "
                               "distance to its smoothed self, L) beyond the design's, and its fragments (parts under 2%% "
                               "of its largest) against the design's: a torn edge" % FINE}
    # the bow's shape in front
    if 'front' in O and 'bow' in pm:
        lob_d = masks.get('front__bow')
        tl = [masks.get('front__bow_tail_%s' % s_) for s_ in 'LR']
        if lob_d is not None and all(t is not None for t in tl):
            d_ = bow_shape(clean(lob_d, ppl), clean(tl[0] | tl[1], ppl), ppl)
            Mo = clean(members(O['front']['lab'], names, pm, 'bow'), ppl)
            o_ = None
            if Mo.sum() >= MIN_PX and d_:
                # ours in one object: the lobes above the design's tails' top, the tails below it
                zt = WIN['top'] - (np.nonzero(tl[0] | tl[1])[0].min() + 0.5) / ppl
                rt = int(round((WIN['top'] - zt) * ppl))
                lob_o, tail_o = Mo.copy(), Mo.copy()
                lob_o[rt:] = False
                tail_o[:rt] = False
                o_ = bow_shape(lob_o, tail_o, ppl)
            T['bow_front'] = dict(ours=o_, design=d_)
            if d_:
                for key, lim in (('flare', 'bow_flare'), ('tail_width', 'tail_width'), ('tail_gap', 'tail_gap')):
                    name = 'bow_front_' + key
                    if d_.get(key) is None:
                        continue
                    if not o_ or o_.get(key) is None:
                        C[name] = {'value': None, 'status': 'FAIL', 'design': d_.get(key), 'why': 'ours not measured'}
                        continue
                    v_ = round(abs(o_[key] / d_[key] - 1) if key == 'tail_width' else abs(o_[key] - d_[key]), 4)
                    C[name] = {'value': v_, 'status': grade(lim, v_), 'ours': o_[key], 'design': d_[key],
                               'note': {'flare': "the bow's lobes' height at their ends over at the knot, against the "
                                                 "design's (a bow tie flares out to its ends; a pillow doesn't)",
                                        'tail_width': "the bow's tails' width (their rows' median run), ours over the "
                                                      "design's, less one",
                                        'tail_gap': "the gap between the bow's two tails 80% of the way down them (L), "
                                                    "against the design's (the tails part as they fall)"}[key]}
    return T, C


def alone(B, names, view, az3, ppl, keep, depth=False):
    """the objects `keep` (names) z-buffered alone on the design's grid for a view -> bool silhouette (with depth: and
    the depth image)."""
    from . import qa3d
    from .faceqa import zbuffer
    meshes, nm = qa3d.scene_objects(B)
    obj = [(V, T, np.full(len(T), i)) for i, (V, T, _) in enumerate(meshes) if nm[i] in keep]
    if not obj:
        return None
    As = B.assembly
    iw = np.array(qa3d.iris_centres(B))
    az = bodyqa.azimuths(az3)
    org = bodyqa.origin(view, az[view], iw, As['centre'])
    d, lab = zbuffer(obj, az[view], org, As['L'], 1.0 / ppl, WIN)
    return (lab >= 0, d) if depth else lab >= 0


def junction_order(top, band, top_alone, band_alone, ppl, reach=0.05, depths=None, near=None):
    """at the jacket/band junction (the columns where a jacket pixel sits right above a band pixel, within 2 px): per
    column, which hides which: the band alone reaching up behind the jacket (the jacket over it) or the jacket alone
    reaching down behind the band (tucked under it). depths (the jacket alone's depth image, the composite's) and near
    (depth units): the jacket alone below the junction counts as tucked only within `near` behind the band there (a
    jacket hung over the band all round shows its back panel through its open front and below its front hem, far
    behind the band: not tucked). -> dict(cols, over (share: the jacket in front), under (share: the band in front),
    boundary (per column: the junction's row)) or None."""
    H, W = top.shape
    k = int(round(reach * ppl))
    cols, over, under, rows = [], 0, 0, {}
    for c in range(W):
        rt = np.nonzero(top[:, c])[0]
        rb = np.nonzero(band[:, c])[0]
        if not len(rt) or not len(rb):
            continue
        b0 = rb.min()
        t1 = rt[rt < b0].max() if (rt < b0).any() else None
        if t1 is None or b0 - t1 > 2:
            continue
        cols.append(c)
        rows[c] = b0
        if band_alone[max(0, b0 - k):b0 - 1, c].sum() >= 2:
            over += 1
        else:
            below = top_alone[b0 + 1:min(H, b0 + k), c]
            if depths is not None and near is not None:
                dt, dc = depths[0][b0 + 1:min(H, b0 + k), c], depths[1][b0 + 1:min(H, b0 + k), c]
                below = below & band[b0 + 1:min(H, b0 + k), c] & (np.abs(dt - dc) <= near)
            if below.sum() >= 2:
                under += 1
    if not cols:
        return None
    return dict(cols=len(cols), over=round(over / len(cols), 3), under=round(under / len(cols), 3), rows=rows)


def half_widths(m, ppl, zs, cx=None):
    """a mask's half-width round the middle `cx` (px; default its own) at heights zs (L from the eye line)."""
    rs, cs = np.nonzero(m)
    if not len(rs):
        return [None] * len(zs)
    cx = 0.5 * (cs.min() + cs.max()) if cx is None else cx
    out = []
    for z in zs:
        r = int(round((WIN['top'] - z) * ppl - 0.5))
        c = np.nonzero(m[max(0, r - 1):r + 2].any(0))[0] if 0 <= r < m.shape[0] else []
        out.append(round(float(max(cx - c.min(), c.max() - cx) + 0.5) / ppl, 4) if len(c) else None)
    return out


OVERHANG_TOP = (-1.33, -1.26)        # L from the eye line: the jacket's front in profile (below the bow's tails, -1.21)
OVERHANG_BAND = (-1.47, -1.40)      # ... the band's (below the jacket's hem, above the skirt)
NEAR = 0.08                         # L: the jacket alone below the junction counts as tucked under the band only this
                                    # near behind it (its front hem inside the band: the band's thickness and clearance)
OPENING_Z = (-1.0, -1.05, -1.1, -1.15, -1.2, -1.25, -1.3)    # L: the bib's rows below the bow's tails, above the band


def jacket(B, O, names, masks, pm, ppl, az3, dv, cls_o):
    """the jacket over the band and its open front (see the module doc) -> (table, checks)."""
    from .bodyqa import CLASS as CL
    T, C = {}, {}
    tops = [m[0] for m in pm.get('top', [])] + [m[0] for m in pm.get('bodice_panel', [])]
    bands = [m[0] for m in pm.get('waistband', [])]
    if not tops or not bands:
        return T, C
    for view in ('front', 'three_quarter'):
        if view not in O:
            continue
        top = members(O[view]['lab'], names, pm, 'top') | members(O[view]['lab'], names, pm, 'bodice_panel')
        band = members(O[view]['lab'], names, pm, 'waistband')
        ta, ba = alone(B, names, view, az3, ppl, tops, depth=True), alone(B, names, view, az3, ppl, bands)
        j = junction_order(top, band, ta[0], ba, ppl, depths=(ta[1], O[view]['depth']),
                           near=NEAR * float(B.assembly['L'])) if ta is not None and ba is not None else None
        name = 'top_%s_over_band' % view
        if j is None:
            C[name] = {'value': None, 'status': 'FAIL', 'why': 'no jacket/band junction seen'}
            continue
        T['order_' + view] = {k: v for k, v in j.items() if k != 'rows'}
        v_ = j['under']
        C[name] = {'value': v_, 'status': grade('order', v_), 'over': j['over'], 'cols': j['cols'],
                   'note': "at the jacket/band junction, the share of its columns where our band hides the jacket (the "
                           "jacket's hem tucked under the band); the design's jacket and bib hang over the band's top "
                           "(Michael's review of round 6; the drawn junction steps with the bodice's hem, not a level "
                           "band edge)"}
    # the open front: the bib's half-width between the jacket's fronts, and the junction's drop to it
    if 'front' in O and masks.get('front__bodice_panel') is not None:
        Pd = clean(masks['front__bodice_panel'], ppl)
        if 'bodice_panel' in pm:
            Po = members(O['front']['lab'], names, pm, 'bodice_panel')
        else:
            Po = members(O['front']['lab'], names, pm, 'top') & (cls_o['front'] == CL['cream'])
        Po = clean(Po, ppl)
        cx = WIN['x'] * ppl - 0.5                                      # the grid's middle (the eyes' midpoint)
        wd, wo = half_widths(Pd, ppl, OPENING_Z, cx), half_widths(Po, ppl, OPENING_Z, cx)
        pairs = [(a, b) for a, b in zip(wo, wd) if b is not None]
        T['opening'] = dict(z=list(OPENING_Z), ours=wo, design=wd)
        if pairs:
            dw = [(a if a is not None else 0.0) - b for a, b in pairs]
            v_ = round(float(np.sqrt(np.mean(np.square(dw)))), 4)
            C['top_front_opening'] = {'value': v_, 'status': grade('opening', v_), 'ours': wo, 'design': wd,
                                      'z': list(OPENING_Z),
                                      'note': "the jacket's open front: the cream bib's half-width between its fronts at "
                                              "heights below the bow's tails (L), RMS against the design's"}
        # the junction's drop from the jacket's fronts (0.2-0.3 L out) to the bib's middle (within 0.06 L)
        def drop(top, band):
            rs = {}
            for c in range(top.shape[1]):
                rb = np.nonzero(band[:, c])[0]
                if len(rb):
                    rs[c] = rb.min()
            mid = [rs[c] for c in rs if abs(c - cx) / ppl < 0.06]
            side = [rs[c] for c in rs if 0.2 <= abs(c - cx) / ppl <= 0.3]
            return round((np.median(mid) - np.median(side)) / ppl, 4) if mid and side else None
        dd = drop(masks['front__top'], clean(ink_core(masks['front__waistband'], dv['front'].get('cls')), ppl))
        do = drop(members(O['front']['lab'], names, pm, 'top') | members(O['front']['lab'], names, pm, 'bodice_panel'),
                  members(O['front']['lab'], names, pm, 'waistband'))
        if dd is not None:
            T['hem_step'] = dict(ours=do, design=dd)
            if do is None:
                C['top_front_hem_step'] = {'value': None, 'status': 'FAIL', 'design': dd, 'why': 'ours not measured'}
            else:
                v_ = round(abs(do - dd), 4)
                C['top_front_hem_step'] = {'value': v_, 'status': grade('hem_step', v_), 'ours': do, 'design': dd,
                                           'note': "the junction's drop from the jacket's fronts (0.2-0.3 L out) to the "
                                                   "bib's middle (L: the band's visible top, the design's inside its ink "
                                                   "(ink_core); negative: the bib's hem higher than the jacket's fronts, "
                                                   "which hang lower over the band), against the design's"}
    return T, C


def ink_core(band, cls):
    """a drawn band's own region: the largest part of its piece mask that the drawing's ink (the line class, grown a
    pixel) leaves connected. The outfit masks give the band the jacket's lower part where the jacket hangs over it (the
    front's notched corners, the three-quarter's near front, the back's hem: 13%, 46% and 38% of the band's mask), and
    the jacket's hem stroke cuts that part off. None without ink (a synthetic mask): the mask itself."""
    from scipy import ndimage
    if band is None or not band.any():
        return band
    ink = cls == bodyqa.CLASS['line'] if cls is not None else None
    if ink is None or not ink.any():
        return band
    lab, n = ndimage.label(band & ~ndimage.binary_dilation(ink))
    if not n:
        return band
    sz = np.bincount(lab.ravel())
    sz[0] = 0
    return lab == int(np.argmax(sz))


def edges(m, mid=(0.2, 0.8)):
    """a piece mask's top and bottom edges: per column its first and last row, their medians over the middle `mid`
    of its columns (a band's ends curve round), and its rows' median width there. -> dict(top, bottom (rows), width
    (px), c0, c1) or None."""
    rs, cs = np.nonzero(m)
    if len(rs) < MIN_PX:
        return None
    c0, c1 = np.percentile(cs, [100 * mid[0], 100 * mid[1]])
    cols = [c for c in np.unique(cs) if c0 <= c <= c1]
    if not cols:
        return None
    top = float(np.median([rs[cs == c].min() for c in cols]))
    bot = float(np.median([rs[cs == c].max() for c in cols]))
    rows = [r for r in np.unique(rs) if top <= r <= bot]
    wid = float(np.median([np.ptp(cs[rs == r]) + 1 for r in rows])) if rows else None
    return dict(top=top, bottom=bot, width=wid, c0=float(cs.min()), c1=float(cs.max()))


def z_of(row, ppl):
    return WIN['top'] - (row + 0.5) / ppl


def x_of(col, ppl):
    return (col + 0.5) / ppl - WIN['x']


def waist(O, names, masks, pm, ppl, dv=None):
    """the waistband's edges and width per view, the top's overhang over it in profile, and the shorts' hem and width
    (see the module doc) -> (table, checks). The design's band is its ink-bounded part (ink_core; not in profile, where
    the outfit masks' band is the jacket's lower part and the band itself is labelled skirt)."""
    T, C = {}, {}
    for view in ('front', 'three_quarter', 'profile', 'back'):
        if view not in O:
            continue
        for pid in ('waistband', 'shorts'):
            Md = masks.get('%s__%s' % (view, pid))
            if Md is None or pid not in pm:
                continue
            if pid == 'waistband' and dv and view in dv and view != 'profile':
                Md = ink_core(Md, dv[view].get('cls'))
            ed = edges(clean(Md, ppl))
            if ed is None:
                continue
            eo = edges(clean(members(O[view]['lab'], names, pm, pid), ppl))
            if eo is None:
                why = {'value': None, 'status': 'FAIL', 'why': 'ours shows too little of the piece here'}
                if pid == 'waistband':
                    C['waistband_%s_rows' % view] = dict(why); C['waistband_%s_width' % view] = dict(why)
                else:
                    C['shorts_%s_hem' % view] = dict(why)
                    if view in ('front', 'back'):
                        C['shorts_%s_width' % view] = dict(why)
                continue
            zo = dict(top=z_of(eo['top'], ppl), bottom=z_of(eo['bottom'], ppl), width=eo['width'] / ppl)
            zd = dict(top=z_of(ed['top'], ppl), bottom=z_of(ed['bottom'], ppl), width=ed['width'] / ppl)
            zo = {k: round(v, 4) for k, v in zo.items()}
            zd = {k: round(v, 4) for k, v in zd.items()}
            T['%s_%s' % (pid, view)] = dict(ours=zo, design=zd)
            if pid == 'waistband':
                v_ = round(max(abs(zo['top'] - zd['top']), abs(zo['bottom'] - zd['bottom'])), 4)
                C['waistband_%s_rows' % view] = {
                    'value': v_, 'status': grade('rows', v_), 'ours': [zo['top'], zo['bottom']],
                    'design': [zd['top'], zd['bottom']],
                    'note': "the band's top and bottom edges (the medians of its middle columns' first and last rows, L "
                            "from the eye line) against the design's: the larger difference (its height and place)"}
            else:
                v_ = round(abs(zo['bottom'] - zd['bottom']), 4)
                C['shorts_%s_hem' % view] = {
                    'value': v_, 'status': grade('rows', v_), 'ours': zo['bottom'], 'design': zd['bottom'],
                    'note': "the shorts' lower edge (their middle columns' last rows, L from the eye line) against the "
                            "design's"}
            if view in ('front', 'back') or pid == 'waistband':
                v_ = round(abs(zo['width'] / max(zd['width'], 1e-6) - 1), 3)
                C['%s_%s_width' % (pid, view)] = {
                    'value': v_, 'status': grade('width', v_), 'ours': zo['width'], 'design': zd['width'],
                    'note': "the piece's median row width over its middle columns' rows, ours over the design's, less "
                            "one"}
    # the jacket's front edge over the band's in profile, from the figures' front edges at fixed rows (the outfit masks'
    # profile band is the jacket's lower part, and the jacket hanging over the band hides the band's own front)
    if 'profile' in O and dv and 'profile' in dv:
        def overhang(fg):
            rows = lambda z0, z1: range(int(round((WIN['top'] - z1) * ppl)), int(round((WIN['top'] - z0) * ppl)) + 1)
            bf = [np.nonzero(fg[r])[0].min() for r in rows(*OVERHANG_BAND) if fg[r].any()]
            tf = [np.nonzero(fg[r])[0].min() for r in rows(*OVERHANG_TOP) if fg[r].any()]
            if not bf or not tf:
                return None
            return round((float(np.median(bf)) - float(np.min(tf))) / ppl, 4)
        d_ = overhang(dv['profile']['fg'])
        o_ = overhang(O['profile']['lab'] >= 0)
        if d_ is not None:
            T['overhang'] = dict(ours=o_, design=d_)
            if o_ is None:
                C['waistband_profile_overhang'] = {'value': None, 'status': 'FAIL', 'design': d_,
                                                   'why': 'our figure not seen at the band or above it in profile'}
            else:
                v_ = round(abs(o_ - d_), 4)
                C['waistband_profile_overhang'] = {
                    'value': v_, 'status': grade('overhang', v_), 'ours': o_, 'design': d_,
                    'note': "in profile, how far the jacket's front edge (the figure's, z %.2f..%.2f: below the bow's "
                            "tails, above the band) stands in front of the band's (the figure's median, z %.2f..%.2f), "
                            "L, against the design's" % (OVERHANG_TOP + OVERHANG_BAND)}
    return T, C


def measure(B, design, out=None):
    """the piece details' checks on a bundle against the design (qa3d.Design) -> (table, checks)."""
    from . import bodymeasure
    ctx = design.sheet_context()
    if 'why' in ctx:
        return None, {'piece_details': {'status': 'SKIPPED', 'why': ctx['why']}}
    got = bodymeasure.piece_masks(B.spec)
    if got is None:
        return None, {'piece_details': {'status': 'SKIPPED', 'why': 'no outfit_masks produced for this spec'}}
    masks, graph, paths = got
    for p in paths:
        design._rec(p)
    ppl = ctx['ppl']
    O, names = our_labels(B, ppl, ctx['az3'])
    pm = bodymeasure.piece_map(graph, B.spec)
    T, C = {}, {}
    skin = [o.name for o in B.objects(groups=('skin',))]
    t, c = sleeves(O, names, masks, pm, ppl, design.design_views(), skin)
    T['sleeves'] = t
    C.update(c)
    ref = design.ref()
    cl = None
    try:
        from . import manifest
        M = manifest.load(ref['manifest'])['references'] if ref.get('manifest') else {}
        if 'sleeve_closeup' in M:
            cl = design.memo(closeup_section, design.rgba(manifest._p(M['sleeve_closeup']['path']))[..., :3])
    except (KeyError, OSError):
        cl = None
    T['closeup'] = cl
    skin_name = skin[0] if skin else None
    for side in ('L', 'R'):
        so = [m[0] for m in pm.get('sleeve_' + side, [])]
        cu = [m[0] for m in pm.get('sleeve_cuff_' + side, [])]
        if not (cl and so and cu and skin_name):
            continue
        o_ = our_section(B, so[0], cu[0], skin_name)
        if o_ is None:
            C['sleeve_standoff_%s' % side] = {'value': None, 'status': 'FAIL', 'design': cl,
                                              'why': 'our puff, band or arm round it not found'}
            continue
        v_ = round(abs(o_['standoff'] / cl['standoff'] - 1), 3)
        C['sleeve_standoff_%s' % side] = {
            'value': v_, 'status': grade('standoff', v_), 'ours': o_, 'design': cl,
            'note': "the puff seen along its arm, as sleeve_closeup's cross-section: its radius over the arm's under the "
                    "band (the balloon's stand-off), ours over the design's, less one (area-equivalent radii)"}
    t, c = waist(O, names, masks, pm, ppl, design.design_views())
    T['waist'] = t
    C.update(c)
    t, c = cuffs(O, names, masks, pm, ppl, design.design_views(), skin, our_classes(B, ppl, ctx['az3']))
    T['cuffs'] = t
    C.update(c)
    t, c = collar_bow(B, O, names, masks, pm, ppl, ctx['az3'], design.design_views())
    T['collar_bow'] = t
    C.update(c)
    t, c = jacket(B, O, names, masks, pm, ppl, ctx['az3'], design.design_views(), our_classes(B, ppl, ctx['az3']))
    T['jacket'] = t
    C.update(c)
    return T, C
