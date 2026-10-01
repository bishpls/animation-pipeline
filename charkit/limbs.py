"""A piece's parts read from its silhouette (tool/accessories6, docs/workstreams/accessories6.md; Michael 2026-10-01 on
the crab clip: "legs too short, and all on the bottom of the crab, not actually on the sides... the pinchers are solid
circles"): the core (the body), the lobes (big parts joined to it by something thinner: the claws), and the limbs
(thin parts standing off the core: legs, eye stalks; what stands off a lobe is the lobe's), measured in the core's own
width so a drawing and our render compare at any scale. One reading serves the drawing and ours alike (the
declared family `limbs`, charkit.declared).

read(m) on a bool mask, the piece upright (its up the picture's up):
  core, lobes  the mask opened by a disk (OPEN_R of sqrt(area)); its distance transform's h-maxima (H_MAX of
               sqrt(area), above SEED_MIN of the deepest) seed a watershed: the largest region is the core, the others
               above LOBE_MIN of the area are lobes
  limbs        what the opening cut off, beyond BAND core widths from the core (where neighbouring legs drawn touching
               at the body part), as components: each its reach (the farthest pixel from the core, in core widths), its
               root (the core point nearest its base: the elliptical angle on the core, 0 at the side, + up, - down,
               from the core's centroid and half extents) and its direction (base to tip, degrees above the horizontal,
               outward); a limb touching a lobe is the lobe's (its finger tips cut by the opening) and not counted;
               one rooted above STALK_ROOT degrees within STALK_X core widths of the middle is a stalk, the rest legs
  a lobe's     notches: the components of its convex hull less itself, each its depth (the deepest point's distance
  fingers      inside the hull) over the lobe's sqrt(area); fingers = 1 + the notches deeper than NOTCH_MIN
spoil(m, how) makes the calibration floors from a drawing (charkit.calib.clips): its legs cut to stubs, shortened,
turned under the body; its lobes' notches filled; its stalks cut.
"""
import numpy as np

OPEN_R = 0.08          # the opening's disk radius, a share of sqrt(area) (the drawn crab: legs 0.09, stalks 0.04 thick)
H_MAX = 0.04           # the seeds: the opened mask's distance h-maxima this high (share of sqrt(area)) ...
SEED_MIN = 0.25        # ... where the distance is at least this share of its deepest
LOBE_MIN = 0.01        # a lobe: at least this share of the area (sqrt(area) squared)
BAND = 0.06            # core widths: limbs counted beyond this from the core (drawn legs touch each other at the body)
LIMB_MIN = 0.0005      # a limb: at least this share of the area
STALK_ROOT = 35.0      # degrees: a limb rooted above this on the core ...
STALK_X = 0.35         # ... within this many core widths of its middle is a stalk
NOTCH_MIN = 0.12       # a lobe's notch this deep (share of the lobe's sqrt(area)) splits it into fingers


def disk(r):
    r = max(1.0, float(r))
    n = int(np.ceil(r))
    y, x = np.mgrid[-n:n + 1, -n:n + 1]
    return x * x + y * y <= r * r + 0.5


def dilate(m, r):
    """m grown by a disk of radius r px (a distance transform: fast at any radius)."""
    from scipy import ndimage
    return ndimage.distance_transform_edt(~m) <= max(1.0, float(r)) + 0.25 if m.any() else m.copy()


def erode(m, r):
    from scipy import ndimage
    return ndimage.distance_transform_edt(m) > max(1.0, float(r)) + 0.25


def opening(m, r):
    e = erode(m, r)
    return dilate(e, r) & m if e.any() else e


def _crop(m, pad):
    ys, xs = np.nonzero(m)
    return np.pad(m[ys.min():ys.max() + 1, xs.min():xs.max() + 1], pad)


def segment(m):
    """the parts' masks -> dict(m (cropped, padded), core, lobes [mask], limbs (label image), n (limbs), D (distance
    from the core), near (index of the nearest core pixel), W, H, cy, cx, s) or None (too small)."""
    from scipy import ndimage
    from skimage.morphology import h_maxima
    from skimage.segmentation import watershed
    if m is None or m.sum() < 200:
        return None
    s = float(np.sqrt(m.sum()))
    r = OPEN_R * s
    m = _crop(m, int(np.ceil(r)) + 8)
    op = opening(m, r)
    if not op.any():
        return None
    dt = ndimage.distance_transform_edt(op)
    pk = (h_maxima(dt, max(1.0, H_MAX * s)) > 0) & (dt > SEED_MIN * dt.max())
    seeds, ns = ndimage.label(pk)
    reg = watershed(-dt, seeds, mask=op)
    areas = ndimage.sum(op, reg, range(1, ns + 1))
    order = np.argsort(areas)[::-1]
    core = reg == order[0] + 1
    lobes = [reg == k + 1 for k in order[1:] if areas[k] > LOBE_MIN * s * s]
    ys, xs = np.nonzero(core)
    W, H = float(xs.max() - xs.min() + 1), float(ys.max() - ys.min() + 1)
    rest = m & ~dilate(op, 2)
    D, near = ndimage.distance_transform_edt(~core, return_indices=True)
    lab, n = ndimage.label(rest & (D > BAND * W), structure=np.ones((3, 3)))
    return dict(m=m, core=core, lobes=lobes, limbs=lab, n=n, D=D, near=near, W=W, H=H, cy=float(ys.mean()),
                cx=float(xs.mean()), s=s, r=r)


def read(m):
    """the parts' numbers (module docstring) -> dict(W, H (the core's extent, px), legs {L, R: [limb]}, stalks [limb],
    lobes [dict(side, size, notch, notches, fingers)], summary numbers) or None."""
    from scipy import ndimage
    from skimage.morphology import convex_hull_image
    S = segment(m)
    if S is None:
        return None
    M, core, D, (iy, ix) = S['m'], S['core'], S['D'], S['near']
    W, H, cy, cx, s = S['W'], S['H'], S['cy'], S['cx'], S['s']
    lobe_near = dilate(np.any(S['lobes'], 0), 3) if S['lobes'] else np.zeros(M.shape, bool)
    legs, stalks = {'L': [], 'R': []}, []
    for k in range(1, S['n'] + 1):
        sel = S['limbs'] == k
        if sel.sum() < LIMB_MIN * s * s or (sel & lobe_near).any():
            continue
        yy, xx = np.nonzero(sel)
        d = D[sel]
        i0, i1 = int(np.argmin(d)), int(np.argmax(d))
        ry, rx = iy[yy[i0], xx[i0]], ix[yy[i0], xx[i0]]
        root = float(np.degrees(np.arctan2(-(ry - cy) / (H / 2), abs(rx - cx) / (W / 2))))
        side = 'R' if xx[i1] > cx else 'L'
        out = 1 if side == 'R' else -1
        rec = dict(reach=round(float(d.max()) / W, 4), root=round(root, 1),
                   dir=round(float(np.degrees(np.arctan2(-(yy[i1] - ry), out * (xx[i1] - rx)))), 1),
                   side=side, px=int(sel.sum()))
        if root > STALK_ROOT and abs(rx - cx) < STALK_X * W:
            stalks.append(rec)
        else:
            legs[side].append(rec)
    lobes = []
    for L_ in S['lobes']:
        cm = M & dilate(L_, S['r'] + 2) & ~dilate(core, S['r'])
        lab, n = ndimage.label(cm)
        if n > 1:
            cm = lab == int(np.argmax(ndimage.sum(cm, lab, range(1, n + 1)))) + 1
        if cm.sum() < 50:
            continue
        hull = convex_hull_image(cm)
        dh = ndimage.distance_transform_edt(hull)
        ld, nd = ndimage.label(hull & ~cm)
        cw = float(np.sqrt(cm.sum()))
        notches = sorted((float(dh[ld == j].max()) / cw for j in range(1, nd + 1)), reverse=True)
        ys, xs = np.nonzero(cm)
        lobes.append(dict(side='R' if xs.mean() > cx else 'L', size=round(cw / W, 4),
                          up=round(float((cy - ys.mean()) / H), 3), notch=round(notches[0], 4) if notches else 0.0,
                          notches=[round(x, 4) for x in notches[:3]],
                          fingers=1 + sum(x >= NOTCH_MIN for x in notches)))
    allegs = legs['L'] + legs['R']
    mean = lambda xs: round(float(np.mean(xs)), 4) if xs else None
    return dict(W=W, H=H, legs=legs, stalks=stalks, lobes=lobes,
                n_legs={k: len(v) for k, v in legs.items()}, n_stalks=len(stalks), n_lobes=len(lobes),
                leg_reach=mean([x['reach'] for x in allegs]), leg_root=mean([x['root'] for x in allegs]),
                leg_dir=mean([x['dir'] for x in allegs]), stalk_reach=mean([x['reach'] for x in stalks]),
                notch=mean([x['notch'] for x in lobes]), fingers=[x['fingers'] for x in lobes])


def compare(Ro, Rd, measure):
    """one measure of ours (Ro) against the drawing's (Rd), both read() -> dict(value, ours, design[, why]) or None
    (the drawing lacks it). value: count, fingers: the largest |ours - design| per side or lobe (a missing one counts);
    reach, stalks: |ours / design - 1|; root: |ours - design| degrees; notch: |ours - design| (share of the lobe)."""
    if Rd is None:
        return None
    if Ro is None:
        return dict(value=None, why='ours reads no parts')
    if measure == 'count':
        d = max(abs(Ro['n_legs'][k] - Rd['n_legs'][k]) for k in ('L', 'R'))
        return dict(value=d, ours=Ro['n_legs'], design=Rd['n_legs'])
    if measure == 'fingers':
        fo, fd = sorted(Ro['fingers']), sorted(Rd['fingers'])
        if not fd:
            return None
        d = max(abs(a - b) for a, b in zip(fo + [0] * len(fd), fd)) if len(fo) <= len(fd) else \
            max([abs(a - b) for a, b in zip(fo, fd + [0] * len(fo))])
        return dict(value=d, ours=fo, design=fd)
    key = dict(reach='leg_reach', root='leg_root', stalks='stalk_reach', notch='notch', dir='leg_dir')[measure]
    if Rd.get(key) is None:
        return None
    o, dd = Ro.get(key), Rd[key]
    extra = dict(n=[Ro['n_stalks'], Rd['n_stalks']]) if measure == 'stalks' else {}
    if o is None:
        return dict(value=None, why='ours has none (%s)' % key, design=dd, **extra)
    if measure in ('reach', 'stalks'):
        v = abs(o / dd - 1) if dd else None
        if measure == 'stalks' and Ro['n_stalks'] != Rd['n_stalks']:
            v = max(v or 0.0, 1.0)                          # (a stalk missing: as far off as none)
        return dict(value=None if v is None else round(v, 3), ours=o, design=dd, **extra)
    return dict(value=round(abs(o - dd), 3 if measure == 'notch' else 1), ours=o, design=dd)


# ------------------------------------------------------------------------------------------------ calibration floors
SPOILS = {
    'legless': 'its legs cut to stubs at the body (BAND core widths out)',
    'short_legs': 'its legs cut to 45% of their reach',
    'bottom_legs': 'its legs turned under the body: each moved round the core by 55 degrees down',
    'solid_claws': "its lobes' notches filled (each lobe its convex hull: solid pincers)",
    'no_stalks': 'its eye stalks cut: the eyes sit on the body',
}


def spoil(m, how):
    """a drawing spoiled one way (SPOILS) -> mask (the cropped, padded frame segment() reads), or None."""
    from scipy import ndimage
    from skimage.morphology import convex_hull_image
    S = segment(m)
    if S is None:
        return None
    R = read(m)
    M, core, D = S['m'].copy(), S['core'], S['D']
    lobe_near = dilate(np.any(S['lobes'], 0), 3) if S['lobes'] else np.zeros(M.shape, bool)
    cy, cx, W, H = S['cy'], S['cx'], S['W'], S['H']
    if how == 'solid_claws':
        for L_ in S['lobes']:
            cm = M & dilate(L_, S['r'] + 2) & ~dilate(core, S['r'])
            lab, n = ndimage.label(cm)
            if n > 1:
                cm = lab == int(np.argmax(ndimage.sum(cm, lab, range(1, n + 1)))) + 1
            if cm.sum() < 50:
                continue
            hull = convex_hull_image(cm)
            dh = ndimage.distance_transform_edt(hull)
            ld, nd = ndimage.label(hull & ~cm)
            cw = float(np.sqrt(cm.sum()))
            for j in range(1, nd + 1):                        # (only the notches: the arm's join stays open)
                if dh[ld == j].max() >= NOTCH_MIN * cw:
                    M |= ld == j
        return M
    # the limbs' full extent (the band to the core included): the cut pixels by nearest limb
    rest = M & ~dilate(opening(M, S['r']), 2)
    owners = np.zeros(M.shape, np.int32)
    kinds = {}
    for k in range(1, S['n'] + 1):
        sel = S['limbs'] == k
        if sel.sum() < LIMB_MIN * S['s'] ** 2 or (sel & lobe_near).any():
            continue
        yy, xx = np.nonzero(sel)
        i0 = int(np.argmin(D[sel]))
        ry, rx = S['near'][0][yy[i0], xx[i0]], S['near'][1][yy[i0], xx[i0]]
        root = float(np.degrees(np.arctan2(-(ry - cy) / (H / 2), abs(rx - cx) / (W / 2))))
        kinds[k] = 'stalk' if root > 35 and abs(rx - cx) < 0.35 * W else 'leg'
        owners[sel] = k
    # grow each limb back through the band to the core (the nearest limb takes a band pixel)
    if owners.any():
        dist, (jy, jx) = ndimage.distance_transform_edt(owners == 0, return_indices=True)
        grown = np.where(rest & (dist < 0.25 * W), owners[jy, jx], 0)
    else:
        grown = owners
    want = 'stalk' if how == 'no_stalks' else 'leg'
    sel = np.isin(grown, [k for k, v in kinds.items() if v == want])
    if how in ('legless', 'no_stalks'):
        keep = D <= (BAND * W if how == 'legless' else 0.02 * W)
        return M & ~(sel & ~keep)
    if how == 'short_legs':
        out = M.copy()
        for k, v in kinds.items():
            if v != 'leg':
                continue
            s_ = grown == k
            reach = D[s_].max()
            out &= ~(s_ & (D > 0.45 * reach))
        return out
    if how == 'bottom_legs':
        P_ = int(0.3 * W)                                     # (room below for the turned legs)
        M, sel = np.pad(M, P_), np.pad(sel, P_)
        cy, cx = cy + P_, cx + P_
        out = M & ~sel
        yy, xx = np.mgrid[0:M.shape[0], 0:M.shape[1]]
        for side in (-1, 1):
            a = np.radians(55.0) * side                       # each pixel's source: turned back up toward the side
            u, v = xx - cx, -(yy - cy)                        # (x right, y up)
            su = u * np.cos(a) - v * np.sin(a)
            sv = u * np.sin(a) + v * np.cos(a)
            src = ndimage.map_coordinates((sel & (np.sign(xx - cx) == side)).astype(float), [cy - sv, cx + su],
                                          order=0, mode='constant') > 0.5
            out |= src & (np.sign(xx - cx) == side)
        return out
    raise KeyError(how)
