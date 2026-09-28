"""Face shape QA: our face against the design's face, measured (pure numpy; the Blender side only hands over arrays).

The target is the generated character (the TRELLIS.2 mesh of the 3D-style key, aligned by its eyes onto ours: same eye line,
same eye spacing), its skin found by colour; the 2D design rig's landmarks (charkit.refs.measure) are a second reference for
the heights of the features. Both faces are seen the same way: a z-buffer of point splats from a view azimuth, every
surface in the scene occluding (hair, eyes, clothes), the visible skin masked. Measured, in head lengths L:

  front / three-quarter / profile   IoU of the visible face skin over the lower face (below the eyes to the target's
                chin: above the eyes it is mostly the fringe and the eyes that differ, below the chin the neckline)
  widths        the visible lower face's extent per height, ours against the target (mean and worst row): from the front
                the half-width, from the side views the front edge
  profile       the midline's front edge (side view) from the nose to the chin: mean distance between the two curves
  chin          the chin's bottom (where the profile turns back to the neck) below the eye line: ours, target, design
  depth         over the skin both show from the front, down to the higher of the two chins: ours minus target along the
                view (+ = ours further back), per region (cheeks, jaw, nose and mouth, chin), after taking out the median
                offset (the alignment's)
  features      mouth, nose and brow heights from the eye line against the design rig's

    from charkit import faceqa
    R = faceqa.measure(ours, target, lm, ref=None)     # ours: [(V, tris, label)], target: (V, tris, colours)
"""
import numpy as np

WIN = dict(x=0.65, top=0.45, bottom=-0.75)        # the face window, in L round the head centre and the eye line
PIX = 0.006                                       # pixel size, in L
SKIN = dict(s=(0.07, 0.38), v=0.82, h=(0.0, 42.0))  # the generated skin's colour (HSV; its hair shares the hue, not the pale)
AZ = {'front': 0, 'three_quarter': 45, 'profile': 90}


# ------------------------------------------------------------------------------------------------------------ geometry
def triangles(loopv, starts, counts):
    """fan-triangulate flat polygons -> (m, 3) vertex indices, and each triangle's polygon."""
    tris, poly = [], []
    for k in np.unique(counts):
        if k < 3:
            continue
        sel = np.nonzero(counts == k)[0]
        base = starts[sel]
        for j in range(1, k - 1):
            tris.append(np.stack([loopv[base], loopv[base + j], loopv[base + j + 1]], 1))
            poly.append(sel)
    if not tris:
        return np.zeros((0, 3), np.int64), np.zeros(0, np.int64)
    return np.concatenate(tris), np.concatenate(poly)


def skin_mask(C):
    """per-vertex: the generated mesh's skin, by colour."""
    from .i3d import hsv
    h, s, v = hsv(C)
    return (s > SKIN['s'][0]) & (s < SKIN['s'][1]) & (v > SKIN['v']) & (h >= SKIN['h'][0]) & (h <= SKIN['h'][1])


def view(P, az):
    """world points -> (u right, z up, depth along the view; smaller = nearer) for a camera at azimuth az (0 = front,
    the camera on -y looking +y; 90 = from +x)."""
    a = np.radians(az)
    return P[:, 0] * np.cos(a) + P[:, 1] * np.sin(a), P[:, 2], -P[:, 0] * np.sin(a) + P[:, 1] * np.cos(a)


def zbuffer(meshes, az, origin, L, pix=PIX, win=WIN):
    """the nearest surface per pixel over the face window: meshes [(V, tris, tri_label)] -> (depth (H, W), label (H, W));
    label -1 = nothing, else the label of the nearest surface. Triangles are sampled on a barycentric grid fine enough that
    every pixel they cover gets a sample."""
    ox, oz = origin                                     # the window's centre: x of the midline, z of the eye line
    W = int(round(2 * win['x'] / pix)); H = int(round((win['top'] - win['bottom']) / pix))
    px_all, d_all, l_all = [], [], []
    for V, T, lab in meshes:
        if len(T) == 0:
            continue
        u, z, d = view(V, az)
        u = (u - ox) / L; z = (z - oz) / L
        # keep triangles touching the window
        tu, tz = u[T], z[T]
        keep = (tu.max(1) > -win['x']) & (tu.min(1) < win['x']) & (tz.max(1) > win['bottom']) & (tz.min(1) < win['top'])
        T, lab_ = T[keep], np.asarray(lab)[keep]
        if len(T) == 0:
            continue
        tu, tz, td = u[T], z[T], d[T]
        e = np.maximum.reduce([np.hypot(tu[:, i] - tu[:, j], tz[:, i] - tz[:, j]) for i, j in ((0, 1), (1, 2), (2, 0))])
        k = np.clip(np.ceil(e / (0.6 * pix)).astype(int), 1, 64)
        for kk in np.unique(k):
            sel = k == kk
            ii, jj = np.meshgrid(np.arange(kk + 1), np.arange(kk + 1))
            m = ii + jj <= kk
            b1, b2 = ii[m] / kk, jj[m] / kk
            b0 = 1 - b1 - b2
            su = tu[sel][:, 0:1] * b0 + tu[sel][:, 1:2] * b1 + tu[sel][:, 2:3] * b2
            sz = tz[sel][:, 0:1] * b0 + tz[sel][:, 1:2] * b1 + tz[sel][:, 2:3] * b2
            sd = td[sel][:, 0:1] * b0 + td[sel][:, 1:2] * b1 + td[sel][:, 2:3] * b2
            col = np.floor((su + win['x']) / pix).astype(int); row = np.floor((win['top'] - sz) / pix).astype(int)
            ok = (col >= 0) & (col < W) & (row >= 0) & (row < H)
            px_all.append((row * W + col)[ok]); d_all.append(sd[ok])
            l_all.append(np.broadcast_to(lab_[sel][:, None], su.shape)[ok])
    depth = np.full(H * W, np.inf); label = np.full(H * W, -1)
    if px_all:
        px, dd, ll = np.concatenate(px_all), np.concatenate(d_all), np.concatenate(l_all)
        o = np.lexsort((dd, px))
        px, dd, ll = px[o], dd[o], ll[o]
        first = np.r_[True, px[1:] != px[:-1]]
        depth[px[first]] = dd[first]; label[px[first]] = ll[first]
    return depth.reshape(H, W), label.reshape(H, W)


# ------------------------------------------------------------------------------------------------------------ measures
def _iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 1.0


def row_z(H, pix=PIX, win=WIN):
    return win['top'] - (np.arange(H) + 0.5) * pix


def chin_bottom(front, z, below=-0.1, turn=0.06):
    """the chin's bottom from a side profile's front edge (u per row, smaller = further forward): going down from `below`
    (L from the eye line; start under the nose, or a projecting nose reads as the chin), the lowest row before the edge
    falls `turn` L behind the chin point (the most forward point below `below`); rows where the edge is hidden (NaN) are
    skipped."""
    ok = np.isfinite(front) & (z < below)
    if ok.sum() < 3:
        return None
    idx = np.nonzero(ok)[0]                           # rows top -> bottom
    best, last = np.inf, None
    for r in idx:
        if front[r] > best + turn:
            return float(z[last]) if last is not None else float(z[r])
        best = min(best, front[r]); last = r
    return float(z[idx[-1]])


def face_region(depth, label, jump, seed_z=-0.15, pix=PIX, win=WIN):
    """the face alone: the visible skin reached from a seed on the cheek (the nearest skin pixel in the row at `seed_z`)
    without crossing a depth jump larger than `jump` between neighbouring pixels, so the neck behind the jaw and the chin
    (the same skin, further back) stays out. -> bool mask."""
    Hh, W = label.shape
    z = row_z(Hh, pix, win)
    r0 = int(np.argmin(np.abs(z - seed_z)))
    cand = np.nonzero(label[r0] == 1)[0]
    out = np.zeros_like(label, bool)
    if not len(cand):
        return out
    c0 = int(cand[np.argmin(depth[r0, cand])])
    out[r0, c0] = True
    stack = [(r0, c0)]
    while stack:
        r, c = stack.pop()
        d = depth[r, c]
        for rr, cc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
            if 0 <= rr < Hh and 0 <= cc < W and not out[rr, cc] and label[rr, cc] == 1 and abs(depth[rr, cc] - d) < jump:
                out[rr, cc] = True
                stack.append((rr, cc))
    return out


def extents(face, depth, label, pix=PIX, win=WIN):
    """per row, the face's two edges (u of the leftmost and rightmost face pixel), NaN where there is none or where the
    edge is not the face's own contour but an occluder in front of it (hair crossing the cheek)."""
    Hh, W = face.shape
    us = (np.arange(W) + 0.5) * pix - win['x']
    lo, hi = np.full(Hh, np.nan), np.full(Hh, np.nan)
    for r in range(Hh):
        c = np.nonzero(face[r])[0]
        if not len(c):
            continue
        for side, cc, nb, out in ((-1, c[0], c[0] - 1, lo), (1, c[-1], c[-1] + 1, hi)):
            if nb < 0 or nb >= W:
                continue
            if label[r, nb] == 0 and depth[r, nb] < depth[r, cc]:
                continue                                  # hidden: something in front at the edge
            out[r] = us[cc]
    return lo, hi


def _at(curve, z, z0, band=0.012):
    m = np.isfinite(curve) & (np.abs(z - z0) <= band)
    return float(np.mean(curve[m])) if m.any() else None


def measure(ours, target, lm, ref=None, pix=PIX, tcache=None):
    """ours: [(V world, tris, per-triangle is-skin bool, part of the face bool)] (the skin, the eyes and the mouth are the
    face; hair, accessories and clothes are not); target: (V world, tris, per-vertex colours); lm: dict(L, eye_z, centre
    (x, y) of the head, mouth_z, nose_z?, brow_z?) world; ref: the design rig's measure (charkit.refs) or None.
    Our face's shape is measured on the face alone (we know it under the hair); the target's only where it shows; how much
    of each face the hair leaves showing is measured separately (coverage). tcache: an optional dict keeping the target's
    z-buffers between calls where it sits the same in the view's window (charkit.faceeval). -> dict (see the module)."""
    L, ez = lm['L'], lm['eye_z']
    cx, cy = lm.get('centre', (0.0, 0.0))[:2]
    TV, TT, TC = target
    tskin = skin_mask(TC)
    tlab = tskin[TT].sum(1) >= 2
    jump = 0.035 * L
    R = {'views': {}}
    maps = {}
    for name, az in AZ.items():
        a = np.radians(az)
        org = (cx * np.cos(a) + cy * np.sin(a), ez)       # the head's centre, seen from this azimuth
        do, lo_ = zbuffer([(V, T, lab.astype(int)) for V, T, lab, face in ours if face], az, org, L, pix)
        if all(face for *_, face in ours):
            dv, lv = do, lo_
        else:
            dv, lv = zbuffer([(V, T, lab.astype(int)) for V, T, lab, face in ours], az, org, L, pix)
        key = None
        if tcache is not None:                            # the target's place in this window: two vertices fix it
            u2, z2, d2 = view(TV[:2], az)
            key = (name, pix, round(L, 9)) + tuple(np.round(np.r_[(u2 - org[0]) / L, (z2 - org[1]) / L, (d2[1] - d2[0]) / L], 9))
        if key is not None and key in tcache:
            dt0, lt, ft = tcache[key]
            dt = dt0 + view(TV[:1], az)[2][0]
        else:
            dt, lt = zbuffer([(TV, TT, tlab.astype(int))], az, org, L, pix)
            ft = face_region(dt, lt, jump, pix=pix)
            if key is not None:
                tcache[key] = (dt - view(TV[:1], az)[2][0], lt, ft)
        fo = face_region(do, lo_, jump, pix=pix)
        fv = fo if dv is do else face_region(dv, lv, jump, pix=pix)
        maps[name] = dict(do=do, lo=lo_, dt=dt, lt=lt, fo=fo, ft=ft, fv=fv & fo, lv=lv)
    z = row_z(maps['front']['fo'].shape[0], pix)
    W = maps['front']['fo'].shape[1]
    us = (np.arange(W) + 0.5) * pix - WIN['x']
    mz = (lm.get('mouth_z', ez - 0.26 * L) - ez) / L
    # the side views: the face's leading contour (the smallest u: the front edge in profile, the far cheek at 3/4) of all
    # the visible skin, rows where something covers the edge left out
    cont = {}
    for name in ('three_quarter', 'profile'):
        M = maps[name]
        cont[name] = (extents(M['lo'] == 1, M['do'], M['lo'], pix)[0], extents(M['lt'] == 1, M['dt'], M['lt'], pix)[0])
    fo_, ft_ = cont['profile']
    below = min(-0.1, mz + 0.06)                      # the search starts under the nose: a projecting nose is no chin
    co, ct = chin_bottom(fo_, z, below), chin_bottom(ft_, z, below)
    R['chin'] = {'ours': co, 'target': ct, 'design': round(ref['chin'], 4) if ref and ref.get('chin') is not None else None}
    # widths from the front at the cheek, the mouth line and halfway to the chin (the mean of the sides that show)
    def half_widths(m):
        lo_, hi_ = extents(maps['front'][m], maps['front']['d' + m[1]], maps['front']['l' + m[1]], pix)
        return np.nanmean(np.stack([-lo_, hi_]), 0) if np.isfinite(lo_).any() or np.isfinite(hi_).any() else lo_
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        wo, wt = half_widths('fo'), half_widths('ft')
    low = ct if ct is not None else mz - 0.13
    R['widths'] = {}
    for k, z0 in (('mouth', mz), ('jaw', (mz + low) / 2)):          # (higher up, ears and the target's hair confound it)
        a, b = _at(wo, z, z0), _at(wt, z, z0)
        R['widths'][k] = {'z': round(z0, 3), 'ours': None if a is None else round(a, 4), 'target': None if b is None else round(b, 4),
                          'ratio': round(a / b, 3) if a and b else None}
    # the leading contours against the target's (+ = ours further back / further in), from under the eyes to the chin
    bottom = max(low, co if co is not None else low)
    for name, (a, b) in cont.items():
        d = a - b
        band = np.isfinite(d) & (z < -0.06) & (z > bottom)
        v = {'rows': int(band.sum())}
        if band.any():
            v.update(gap_mean=round(float(np.mean(d[band])), 4), gap_abs=round(float(np.mean(np.abs(d[band]))), 4))
            for k, z0 in (('nose', -0.13), ('mouth', mz), ('jaw', (mz + low) / 2)):
                g = _at(d, z, z0)
                v[k] = None if g is None else round(g, 4)
        R['views'][name] = v
    M = maps['front']
    rows = (z < -0.06) & (z > bottom)
    R['views']['front'] = {'iou': round(_iou(M['fo'] & rows[:, None], M['ft'] & rows[:, None]), 4)}
    # coverage: the lower face left showing by the hair (from the eyes to the chin), ours against the target's
    R['coverage'] = {}
    for name in ('front', 'three_quarter'):
        M = maps[name]
        vis_o = (M['lv'] == 1) & rows[:, None]
        vis_t = (M['lt'] == 1) & rows[:, None]
        R['coverage'][name] = {'ours_visible_share': round(float(vis_o.sum() / max(1, ((M['lo'] == 1) & rows[:, None]).sum())), 3),
                               'visible_vs_target': round(float(vis_o.sum() / max(1, vis_t.sum())), 3)}
    # depth over the face both show from the front: ours minus the target (+ = ours further back), per region
    M = maps['front']
    both = M['fo'] & M['ft'] & (z > bottom)[:, None]        # the face, not the neck under the chins
    if both.sum() > 50:
        with np.errstate(invalid='ignore'):
            dd = np.where(both, M['do'] - M['dt'], 0.0) / L
        reg0 = both & (np.abs(us)[None, :] > 0.05) & (np.abs(us)[None, :] < 0.2) & (z[:, None] < -0.04) & (z[:, None] > -0.1)
        off = float(np.median(dd[reg0])) if reg0.sum() > 20 else float(np.median(dd[both]))   # aligned under the eyes
        xs = np.abs(us)[None, :]
        zz = z[:, None]
        regions = {'cheeks': (xs > 0.12) & (zz < -0.1) & (zz > mz), 'jaw': (xs > 0.12) & (zz <= mz),
                   'nose_mouth': (xs <= 0.1) & (zz < -0.06) & (zz > mz - 0.03), 'chin': (xs <= 0.12) & (zz <= mz - 0.03)}
        R['depth'] = {'offset': round(off, 4), 'rms': round(float(np.sqrt(np.mean((dd[both] - off) ** 2))), 4)}   # L
        for k, reg in regions.items():
            m = both & reg
            R['depth'][k] = round(float(np.mean(dd[m] - off)), 4) if m.sum() > 20 else None
        R['_depth_map'] = np.where(both, dd - off, np.nan)
    # feature heights against the design rig (L from the eye line)
    if ref:
        f = {}
        for k in ('mouth_z', 'nose_z', 'brow_z'):
            if k in lm and ref.get('features', {}).get(k) is not None:
                f[k] = {'ours': round((lm[k] - ez) / L, 4), 'design': round(ref['features'][k], 4)}
        R['features'] = f
    R['_maps'] = maps
    return R


# ------------------------------------------------------------------------------------------------------------ overlays
def overlay(R, pix=PIX):
    """one RGB image: the two faces from the front (grey both, red ours only, blue the target only; our face without its
    hair, the target's as it shows), then the front depth difference (red = ours further back, blue = ours further forward, +-0.05 L full scale)."""
    tiles = []
    M = R['_maps']['front']
    mo, mt = M['fo'], M['ft']
    im = np.full(mo.shape + (3,), 0.93)
    im[(M['lo'] == 1) | (M['lt'] == 1)] = 0.86                      # skin that isn't face (neck, chest), faint
    im[mo & mt] = (0.55, 0.55, 0.6); im[mo & ~mt] = (0.9, 0.2, 0.2); im[mt & ~mo] = (0.2, 0.35, 0.95)
    tiles.append(im)
    if '_depth_map' in R:
        d = np.clip(R['_depth_map'] / 0.05, -1, 1)
        im = np.full(d.shape + (3,), 0.93)
        ok = np.isfinite(d)
        dp, dn = np.where(ok & (d > 0), d, 0), np.where(ok & (d < 0), -d, 0)
        im[ok] = 1.0
        im[..., 1] -= (dp + dn) * 0.8; im[..., 2] -= dp * 0.8; im[..., 0] -= dn * 0.8
        tiles.append(np.clip(im, 0, 1))
    sep = np.ones((tiles[0].shape[0], 4, 3))
    out = []
    for t in tiles:
        out += [t, sep]
    return np.concatenate(out[:-1], 1)


# ------------------------------------------------------------------------------------------------------------ grading
LIMITS = {                      # (pass within, warn within); else fail
    'width': (0.08, 0.15),      # |ours / target - 1| of the lower face's half-width at the mouth line and halfway to the chin
    'chin': (0.02, 0.04),       # |chin height - target's|, L
    'profile': (0.02, 0.04),    # mean |front-edge gap| in profile, L
    'cheek': (0.02, 0.04),      # mean |far-cheek contour gap| at 3/4, L
    'depth': (0.02, 0.04),      # mean |depth - target| over the cheeks and chin, from under the eyes, L
    'coverage': (0.15, 0.30),   # |visible lower face / target's - 1| (hair framing; warns only)
}


def _grade(key, v, warn_only=False):
    p, w = LIMITS[key]
    st = 'PASS' if v <= p else 'WARN' if v <= w or warn_only else 'FAIL'
    return st


def checks(R):
    """the graded face-shape checks from measure()'s result -> {name: {value, status, ...}}."""
    C = {}
    W = [v['ratio'] for v in R.get('widths', {}).values() if v.get('ratio')]
    if W:
        worst = max(W, key=lambda r: abs(r - 1))
        C['width'] = {'value': worst, 'status': _grade('width', abs(worst - 1)), 'per_height': R['widths']}
    ch = R.get('chin', {})
    if ch.get('ours') is not None and ch.get('target') is not None:
        d = round(ch['ours'] - ch['target'], 4)
        C['chin'] = {'value': d, 'status': _grade('chin', abs(d)), 'heights': ch}
    for key, view in (('profile', 'profile'), ('cheek', 'three_quarter')):
        v = R['views'].get(view, {})
        if v.get('gap_abs') is not None:
            C[key] = {'value': v['gap_abs'], 'status': _grade(key, v['gap_abs']),
                      'at': {k: v.get(k) for k in ('nose', 'mouth', 'jaw')}}
    dp = R.get('depth')
    if dp:
        vals = [abs(dp[k]) for k in ('cheeks', 'chin') if dp.get(k) is not None]
        if vals:
            v = round(float(np.mean(vals)), 4)
            C['depth'] = {'value': v, 'status': _grade('depth', v), 'regions': {k: dp[k] for k in ('cheeks', 'jaw', 'nose_mouth', 'chin')}}
    for view, c in R.get('coverage', {}).items():
        r = c['visible_vs_target']
        C['coverage_' + view] = {'value': r, 'status': _grade('coverage', abs(r - 1), warn_only=True), **c}
    if R.get('features'):
        C['features'] = {'status': 'INFO', 'against_design': R['features']}
    return C


def contours_image(R, scale=3):
    """per view: the visible skin (ours pink, the target's blue, both lilac; hair and clothes grey), our contour red, the
    target's blue; the eye line green, the chins dotted."""
    tiles = []
    for name in AZ:
        M = R['_maps'][name]
        im = np.full(M['lo'].shape + (3,), 1.0)
        im[M['lv'] == 1] = (1.0, 0.85, 0.85); im[M['lt'] == 1] = (0.85, 0.88, 1.0)
        im[(M['lv'] == 1) & (M['lt'] == 1)] = (0.9, 0.85, 0.95)
        im[M['lv'] == 0] = np.minimum(im[M['lv'] == 0], 0.8)
        def draw(a, c):
            for r in np.nonzero(np.isfinite(a))[0]:
                cc = int((a[r] + WIN['x']) / PIX)
                im[r, max(0, cc - 1):cc + 1] = c
        if name == 'front':
            for m, c in (('fo', (0.85, 0.1, 0.1)), ('ft', (0.1, 0.2, 0.9))):
                for a in extents(M[m], M['d' + m[1]], M['l' + m[1]]):
                    draw(a, c)
        else:
            draw(extents(M['lo'] == 1, M['do'], M['lo'])[0], (0.85, 0.1, 0.1))
            draw(extents(M['lt'] == 1, M['dt'], M['lt'])[0], (0.1, 0.2, 0.9))
        z = row_z(im.shape[0])
        for zz, c in ((0, (0, 0.7, 0)), (R['chin'].get('ours'), (0.85, 0.1, 0.1)), (R['chin'].get('target'), (0.1, 0.2, 0.9))):
            if zz is not None:
                im[int(np.argmin(np.abs(z - zz))), ::3] = c
        tiles += [im, np.ones((im.shape[0], 3, 3))]
    im = np.concatenate(tiles[:-1], 1)
    return np.repeat(np.repeat(im, scale, 0), scale, 1)
