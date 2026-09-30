"""Garment piece details (tool/garments2, docs/workstreams/garments2.md): the faults Michael sees in the outfit's pieces
that the piece IoUs (qa3d.sheet_pieces) average away, each measured on the design's grids (bodyqa's: the sheet's scale,
aligned on the eyes) against the design's own drawn piece masks measured the same way.

Checks (qa3d part 'piece_details'; lengths in L):
  sleeve_{front,three_quarter,back}_rough_{L,R}
        the puff sleeve's outline roughness (detailqa.outline_roughness: the 95th percentile of its outline's distance
        to its own smoothed outline) beyond the design's: a torn or stepped cap
  sleeve_{front,three_quarter,back}_spikes_{L,R}
        spikes on the sleeve's outline: the parts of its mask an opening by a disk of radius SPIKE_R L cuts off that
        stand out of the opened mask by SPIKE_MIN L or more (a thin horn or a pointed cap corner), counted beyond the
        design's; the value is the deepest one's depth beyond the design's deepest (L) and the count beside it
The design is measured the same way wherever it has the view; a view where either side shows too little of the piece
(MIN_PX drawn or ours) is skipped.

    table, checks = pieceqa.measure(B, design)      # charkit.qa3d's 'piece_details' part
"""
import numpy as np

from . import bodyqa

WIN = bodyqa.WIN
SPIKE_R = 0.03                      # L: the opening's disk radius (a protrusion thinner than twice this is a spike candidate)
SPIKE_MIN = 0.012                   # L: ... that stands this far out of the opened mask
MIN_PX = 150                        # a view's piece mask this small (either side) is not measured
LIMITS = {                          # (pass within, warn within); else fail
    'rough': (0.004, 0.008),        # L beyond the design's
    'spike': (0.006, 0.015),        # L: the deepest spike beyond the design's deepest
    'standoff': (0.10, 0.20),       # |ours / design - 1| of the puff's radius over the arm's, seen along the arm
    'profile': (0.02, 0.04),        # L: the RMS of the puff's width along its arm against the design's
    'rows': (0.02, 0.04),           # L: a band's top and bottom edges (or the shorts' hem) against the design's
    'width': (0.05, 0.10),          # |ours / design - 1| of a band's width
    'overhang': (0.015, 0.03),      # L: the top's front edge over the band's in profile against the design's
}
SLEEVE_VIEWS = ('front', 'three_quarter', 'profile', 'back')
CLOSE = 0.012                       # L: a drawn piece mask is closed by a disk this wide and its holes filled before its
                                    # outline is measured: the drawing's fold strokes inside a piece are cut out of its
                                    # mask as slits (ours are closed the same way)
FREE = 2                            # px: an outline pixel within this of the background (nothing drawn) is the silhouette


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


def spikes(m, ppl, r=SPIKE_R, min_depth=SPIKE_MIN, where=None):
    """a mask's spikes: the components of what an opening by a disk of radius r L cuts off that reach min_depth L or
    more out of the opened mask (with `where`: only those touching it, the silhouette). -> dict(n, depth (the deepest,
    L; 0 without one), depths [L...], at [(row, col)...])."""
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
    depths, at = [], []
    for k in range(1, n + 1):
        sel = lab == k
        if W is not None and not (sel & W).any():
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


def silhouette(m, fg, free=FREE):
    """a mask's outline pixels within `free` px of the background (fg False): where it is the figure's silhouette."""
    from scipy import ndimage
    edge = m & ~ndimage.binary_erosion(m)
    bg = ndimage.binary_dilation(~fg, iterations=free + 1)
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


def members(lab, names, pm, pid):
    from .bodymeasure import member_mask
    idx = {n: i for i, n in enumerate(names)}
    return member_mask(lab, idx, pm.get(pid, []))


# ------------------------------------------------------------------------------------------------------------ the parts
def sleeves(O, names, masks, pm, ppl, dv, skin_names=('clawd_skin',)):
    """the puff sleeves' outline and shape checks per view and side (see the module doc) -> (table, checks)."""
    from .bodyqa import CLASS as CL
    T, C = {}, {}
    for view in SLEEVE_VIEWS:
        if view not in O or view not in dv:
            continue
        for side in ('L', 'R'):
            pid = 'sleeve_' + side
            Md = masks.get('%s__%s' % (view, pid))
            Mo = members(O[view]['lab'], names, pm, pid)
            if Md is None or Md.sum() < MIN_PX or Mo.sum() < MIN_PX:
                continue
            Md, Mo = clean(Md, ppl), clean(Mo, ppl)
            wd, wo = silhouette(Md, dv[view]['fg']), silhouette(Mo, O[view]['lab'] >= 0)
            ro, rd = outline_roughness(Mo, ppl, where=wo), outline_roughness(Md, ppl, where=wd)
            so, sd = spikes(Mo, ppl, where=wo), spikes(Md, ppl, where=wd)
            T['%s_%s' % (view, side)] = dict(ours=dict(rough=ro, spikes=so), design=dict(rough=rd, spikes=sd),
                                             px=[int(Mo.sum()), int(Md.sum())])
            if ro is not None and rd is not None:
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
            # the puff's shape across the arm: its stand-off and its gathers into the band
            cd_ = masks.get('%s__sleeve_cuff_%s' % (view, side))
            co_ = members(O[view]['lab'], names, pm, 'sleeve_cuff_' + side)
            if cd_ is not None and cd_.sum() >= 20 and co_.sum() >= 20:
                sk_o = np.isin(O[view]['lab'], [i + k for i, n in enumerate(names) if n in skin_names for k in (0, 1000)])
                po = arm_profile(Mo, clean(co_, ppl), sk_o, ppl)
                pd = arm_profile(Md, clean(cd_, ppl), dv[view]['cls'] == CL['skin'], ppl)
                T['%s_%s' % (view, side)]['profile'] = dict(ours=po, design=pd)
                if po and pd and po.get('widths') and pd.get('widths'):
                    dw = np.array(po['widths'][1:-1]) - np.array(pd['widths'][1:-1])
                    v_ = round(float(np.sqrt((dw ** 2).mean())), 4)
                    C['sleeve_%s_profile_%s' % (view, side)] = {
                        'value': v_, 'status': grade('profile', v_), 'ours': po['widths'], 'design': pd['widths'],
                        'note': "the puff's width across its arm from its top to its cuff (tenths of its length): the RMS "
                                "of ours against the design's (L): the pear, narrow at the cap and widest low"}
    return T, C


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


def waist(O, names, masks, pm, ppl):
    """the waistband's edges and width per view, the top's overhang over it in profile, and the shorts' hem and width
    (see the module doc) -> (table, checks)."""
    T, C = {}, {}
    for view in ('front', 'three_quarter', 'profile', 'back'):
        if view not in O:
            continue
        for pid in ('waistband', 'shorts'):
            Md = masks.get('%s__%s' % (view, pid))
            Mo = members(O[view]['lab'], names, pm, pid)
            if Md is None:
                continue
            ed, eo = edges(clean(Md, ppl)), edges(clean(Mo, ppl))
            if ed is None or eo is None:
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
    # the top's front edge over the band's in profile (the design's jacket overhangs the band)
    if 'profile' in O:
        res = {}
        for who in ('ours', 'design'):
            if who == 'ours':
                band = clean(members(O['profile']['lab'], names, pm, 'waistband'), ppl)
                top = members(O['profile']['lab'], names, pm, 'top')
            else:
                band = masks.get('profile__waistband'); top = masks.get('profile__top')
                if band is None or top is None:
                    break
                band = clean(band, ppl)
            e = edges(band)
            if e is None or not top.any():
                break
            r0 = int(round(e['top']))
            bf = [np.nonzero(band[r])[0].min() for r in range(r0 + 2, int(e['bottom']) - 1) if band[r].any()]
            above = range(max(0, r0 - int(0.05 * ppl)), max(0, r0 - int(0.01 * ppl)))
            tf = [np.nonzero(top[r])[0].min() for r in above if top[r].any()]
            if not bf or not tf:
                break
            res[who] = round((float(np.median(bf)) - float(np.min(tf))) / ppl, 4)
        if len(res) == 2:
            v_ = round(abs(res['ours'] - res['design']), 4)
            T['overhang'] = res
            C['waistband_profile_overhang'] = {
                'value': v_, 'status': grade('overhang', v_), 'ours': res['ours'], 'design': res['design'],
                'note': "in profile, how far the top's front edge (just above the band) stands in front of the band's "
                        "(L; + the top overhangs), against the design's: the band's front proud of the top where the "
                        "design's jacket overhangs it"}
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
            continue
        v_ = round(abs(o_['standoff'] / cl['standoff'] - 1), 3)
        C['sleeve_standoff_%s' % side] = {
            'value': v_, 'status': grade('standoff', v_), 'ours': o_, 'design': cl,
            'note': "the puff seen along its arm, as sleeve_closeup's cross-section: its radius over the arm's under the "
                    "band (the balloon's stand-off), ours over the design's, less one (area-equivalent radii)"}
    t, c = waist(O, names, masks, pm, ppl)
    T['waist'] = t
    C.update(c)
    return T, C
