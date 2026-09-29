"""The head's shape from the design's own measured contours (the ones the QA grades), for the authored head
(charkit.geom.headmesh): the face surface first.

Frame: L, x her left, y back with 0 at the eyes' depth, z up from the eye line. The design is the head turnaround as
charkit.refcheck.face_design measures it (the QA's measures of a drawing: the face region is the skin reached from under
the eyes with the drawn lines as walls, cut at the profile's chin):
  - the profile's leading contour, forward of the eye: the face's midline, y_mid(z) = -lead(z);
  - the front's face half-width per row: the face's outline w(z) (below the hair: the cheeks and the jaw);
  - the three-quarter's leading contour, forward of its far eye: the far cheek's silhouette.

The face surface, per row z, for |x| <= w(z):
    y(x, z) = base(z) + depth(z) * (|x| / w(z)) ** q  +  relief(z) * bump(x / sigma(z))
  base     the midline with the nose and the lips taken out: the contour bridged straight across them
  relief   the midline's residual against the base (<= 0: forward): the nose, the lips; spread across by a narrow
           bump, sigma the nose's half-width at the nose, widening to the mouth's
  depth    how far back the face turns by its outline, fitted per row so the far cheek meets the three-quarter's
           contour; q the falloff's shape (the style's: a flat anime face turns late)

    python -m charkit.geom headfit SPEC [--out DIR] [--no-open]
"""
import json, os

import numpy as np

NOSE_SIGMA, LIP_SIGMA = 0.035, 0.07         # the relief's half-widths (L): an anime nose is a narrow wedge
Q_DEFAULT = 2.2


def _smooth(v, k=3):
    """a running mean over finite samples (k rows each side), NaN kept where the input is NaN."""
    out = np.full(len(v), np.nan)
    for i in np.nonzero(np.isfinite(v))[0]:
        w = v[max(0, i - k):i + k + 1]
        out[i] = np.nanmean(w)
    return out


def contours(rgb, eye_x, facing=-1, dz=0.005):
    """the design's face contours on a common z grid (rows every dz L, from the forehead to the chin) -> dict(z, mid
    (y of the midline), w (the outline's half-width), lead3 (the three-quarter's leading contour, forward of its far eye),
    az3, chin, nose_z)."""
    from charkit import refcheck
    D = refcheck.face_design(rgb, eye_x, facing)
    P, F, T = D['profile'], D['front'], D['three_quarter']
    chin = float(P['chin'])
    z = np.arange(0.15, chin - 1e-9, -dz)

    def on_grid(zs, v, agg=np.nanmax):
        out = np.full(len(z), np.nan)
        for i, zz in enumerate(z):
            sel = np.abs(zs - zz) <= dz / 2 + 1e-9
            if sel.any() and np.isfinite(v[sel]).any():
                out[i] = agg(v[sel])
        return out
    lead_p = on_grid(P['z'], P['lead'])
    half = on_grid(F['z'], np.fmax(F['half_left'], F['half_right']))
    lead3 = on_grid(T['z'], T['lead'])
    # the outline: a running envelope (a drawn line inside the face cuts some rows' region short), then smoothed
    w = np.array([np.nanmax(half[max(0, i - 3):i + 4]) if np.isfinite(half[max(0, i - 3):i + 4]).any() else np.nan
                  for i in range(len(z))])
    below = (z < -0.02) & (z > -0.2)
    nose_z = float(z[below][np.nanargmax(lead_p[below])]) if np.isfinite(lead_p[below]).any() else -0.1
    return dict(z=z, mid=-lead_p, w=_smooth(w, 2), lead3=lead3, az3=float(D['az_three_quarter']), chin=chin,
                nose_z=nose_z, eye_x=eye_x, design=D)


def relief_split(z, mid, nose_z, top=-0.02, bottom=None):
    """the midline as base + relief: the base bridges the contour straight from `top` (the nose's root) to `bottom` (under
    the lips, default the nose's length again below its tip), the relief is the rest (<= 0)."""
    bottom = nose_z - 1.5 * (top - nose_z) if bottom is None else bottom
    base = mid.copy()
    ok = np.isfinite(mid)
    a = ok & (np.abs(z - top) <= 0.006); b = ok & (np.abs(z - bottom) <= 0.006)
    if a.any() and b.any():
        ya, yb = float(np.nanmean(mid[a])), float(np.nanmean(mid[b]))
        span = (z < top) & (z > bottom)
        base[span] = ya + (yb - ya) * (top - z[span]) / (top - bottom)
    rel = np.where(ok, np.minimum(mid - base, 0.0), 0.0)
    return np.where(ok, np.maximum(base, mid), np.nan), rel, bottom


class Face:
    """the face surface (see the module) on the contours' z grid."""

    def __init__(self, C, q=Q_DEFAULT, nose_sigma=NOSE_SIGMA, lip_sigma=LIP_SIGMA):
        self.C, self.z, self.q = C, C['z'], q
        self.base, self.relief, self.lip_bottom = relief_split(C['z'], C['mid'], C['nose_z'])
        self.w = C['w']
        t = np.clip((C['nose_z'] - self.z) / max(1e-6, C['nose_z'] - self.lip_bottom), 0, 1)
        self.sigma = nose_sigma + (lip_sigma - nose_sigma) * t
        self.depth = np.full(len(self.z), 0.25)

    def y(self, x, k):
        """the surface's y at x (array) on row k."""
        w = max(self.w[k], 1e-3)
        s = np.clip(np.abs(x) / w, 0, 1)
        return self.base[k] + self.depth[k] * s ** self.q + self.relief[k] * np.exp(-0.5 * (x / self.sigma[k]) ** 2)

    def lead3(self, k, az, eye_x):
        """the three-quarter's leading contour on row k: forward of the far eye, the far half's silhouette."""
        a = np.radians(az)
        x = -np.linspace(0, self.w[k], 200)
        u = x * np.cos(a) + self.y(x, k) * np.sin(a)
        return (-eye_x * np.cos(a)) - u.min()

    def fit_depth(self, lo=0.0, hi=0.8):
        """each row's depth so its far cheek meets the three-quarter's contour (bisection: the lead falls as the depth
        grows); rows the three-quarter doesn't draw keep their neighbours' by interpolation."""
        C = self.C
        ok = np.isfinite(self.base) & np.isfinite(self.w) & np.isfinite(C['lead3'])
        for k in np.nonzero(ok)[0]:
            a, b = lo, hi
            for _ in range(40):
                m = (a + b) / 2
                self.depth[k] = m
                if self.lead3(k, C['az3'], C['eye_x']) > C['lead3'][k]:
                    a = m
                else:
                    b = m
        rows = np.nonzero(ok)[0]
        if len(rows):
            self.depth = np.interp(np.arange(len(self.z)), rows, _smooth(np.where(ok, self.depth, np.nan), 2)[rows])
        return self

    def measure(self):
        """the model's own contours, as the design's are measured: the profile's lead (the midline's front), the front's
        half-width, the three-quarter's lead -> dict of arrays on the z grid."""
        C = self.C
        mid = np.array([self.y(np.array([0.0]), k)[0] if np.isfinite(self.base[k]) else np.nan for k in range(len(self.z))])
        l3 = np.array([self.lead3(k, C['az3'], C['eye_x']) if np.isfinite(self.base[k]) and np.isfinite(self.w[k]) else np.nan
                       for k in range(len(self.z))])
        return dict(lead_p=-mid, w=self.w.copy(), lead3=l3)


def compare(F):
    """the model's contours against the design's: per contour the mean and max absolute difference (L) over the rows
    both have -> dict."""
    C, M = F.C, F.measure()
    out = {}
    for name, ours, theirs in (('profile_lead', M['lead_p'], -C['mid']), ('front_half_width', M['w'], C['w']),
                               ('three_quarter_lead', M['lead3'], C['lead3'])):
        ok = np.isfinite(ours) & np.isfinite(theirs)
        d = np.abs(ours[ok] - theirs[ok])
        out[name] = {'rows': int(ok.sum()), 'mean_L': round(float(d.mean()), 4) if ok.any() else None,
                     'max_L': round(float(d.max()), 4) if ok.any() else None}
    return out


# ------------------------------------------------------------------------------------------------------------ the head
JAW_ROWS = (-0.12, 0.0)          # z (L): below the first, the head's front outline is the face's own (the design's jaw);
                                 # above the second the skull's; blended between
BLEND = 0.03                     # the face's edge band (L) where its surface hands over to the skull's


def skull(spec, h=0.004, log=print):
    """the bald head from head_construction (the skull's authority): its front and profile carved with the style's
    prior, the ears cut off, no silhouette restoration; shifted so the eyes sit at y = 0 -> (V bool, Axes)."""
    from charkit import manifest, refcheck, styles
    from . import hull
    M = manifest.load(spec['ref']['manifest'])['references']
    rgb, _ = refcheck.without_guides(refcheck._load(M['head_construction']['path']))
    ex = spec.get('eyes', {}).get('x', 0.168)
    views, info = hull.views_from_heads(rgb, ex, spec['ref'].get('face_sheet', {}).get('facing', -1), ears=False)
    A = hull.axes_for(views, h)
    prior = dict(styles.load(spec.get('style', 'anime'))['hull'], restore=False)
    V = hull.rounded(views, A, ['front', 'profile'], **prior)
    A.ys = A.ys - info['y_e']
    log('skull: head_construction at %.0f px/L, grid %s, eyes %.3f L in front of the neck' % (info['ppl'], A.shape, -info['y_e']))
    return V, A


def _smooth_rows(v, sigma):
    """a Gaussian over rows (sigma in rows) of a series with NaNs (weights renormalised)."""
    from scipy.ndimage import gaussian_filter1d
    ok = np.isfinite(v)
    num = gaussian_filter1d(np.where(ok, v, 0.0), sigma)
    den = gaussian_filter1d(ok.astype(float), sigma)
    return np.where(ok, num / np.maximum(den, 1e-9), np.nan)


class Sections:
    """the head as one closed section per row: its radius r[k, j] at angle TH[j] round the row's centre (0, cy[k]),
    angle 0 toward the front (-y) and increasing toward her left (+x). zs descend (the skull's grid rows)."""
    N = 256

    def __init__(self, zs, cy, r):
        self.zs, self.cy, self.r = zs, cy, r
        self.th = np.linspace(-np.pi, np.pi, self.N, endpoint=False)

    def xy(self, k):
        return np.sin(self.th) * self.r[k], self.cy[k] - np.cos(self.th) * self.r[k]

    def solid(self, A):
        """the sections as occupancy on A's grid (A.zs must be the sections' rows)."""
        X, Yg = np.meshgrid(A.xs, A.ys, indexing='ij')
        V = np.zeros((len(A.xs), len(A.ys), len(self.zs)), bool)
        for k in range(len(self.zs)):
            if not np.isfinite(self.r[k]).all() or self.r[k].max() <= 0:
                continue
            dx, dy = X, Yg - self.cy[k]
            th = np.arctan2(dx, -dy)
            rr = np.interp(th, self.th, self.r[k], period=2 * np.pi)
            V[:, :, k] = np.hypot(dx, dy) <= rr
        return V


def skull_sections(V, A, smooth_z=0.012, smooth_th=0.01):
    """a solid's rows as polar sections round each row's centroid, centres and radii smoothed over `smooth_z` L of rows
    and the radii over `smooth_th` rad (the carving's voxel noise)."""
    nx, ny, nz = V.shape
    th = np.linspace(-np.pi, np.pi, Sections.N, endpoint=False)
    cy = np.full(nz, np.nan)
    for k in range(nz):
        ij = np.nonzero(V[:, :, k])
        if len(ij[0]):
            cy[k] = A.ys[ij[1]].mean()
    cy = _smooth_rows(cy, smooth_z / A.h)
    r = np.full((nz, len(th)), np.nan)
    steps = np.arange(0, 0.8, A.h / 2)
    for k in np.nonzero(np.isfinite(cy))[0]:
        px = np.sin(th)[:, None] * steps[None, :]
        py = cy[k] - np.cos(th)[:, None] * steps[None, :]
        ix = np.round((px - A.xs[0]) / A.h).astype(int); iy = np.round((py - A.ys[0]) / A.h).astype(int)
        ok = (ix >= 0) & (ix < nx) & (iy >= 0) & (iy < ny)
        inside = np.zeros(ix.shape, bool)
        inside[ok] = V[ix[ok], iy[ok], k]
        # the section's boundary along each ray: the last inside sample (star-shaped round the centroid)
        last = np.where(inside.any(1), inside.shape[1] - 1 - np.argmax(inside[:, ::-1], 1), 0)
        r[k] = steps[last]
    ok = np.isfinite(r).all(1)
    if smooth_z > 0 and ok.any():
        from scipy.ndimage import gaussian_filter
        r[ok] = gaussian_filter(r[ok], (smooth_z / A.h, smooth_th * Sections.N / (2 * np.pi)), mode=('nearest', 'wrap'))
    return Sections(A.zs, cy, r)


FACE_TOP = 0.10                  # z (L): the turnaround's midline corrects the skull up to here (the forehead under the bangs)
CHEEK_TOP = 0.0                  # z: the outline is the face's own below here (above, the hair bounds it)
CHEEK_FIT = (-0.06, 0.08)        # the cheek term is fitted below the first z (above, the three-quarter's contour is the far
                                 # eye's lashes) and fades out over the second (L) above it


def _falloff(s):
    """1 at the midline, 0 at the outline, flat at both: (1 - s^2)^2 on [0, 1]."""
    s = np.clip(np.abs(s), 0, 1)
    return (1 - s * s) ** 2


def _cheek(s):
    """0 at the midline and the outline, most in between: the cheek's shape term."""
    s = np.clip(np.abs(s), 0, 1)
    return 16 * s * s * (1 - s) ** 2


def skull_chin(S):
    """the skull's chin: the lowest row before its midline front turns back under the jaw (a jump back of 0.05 L within
    two rows) -> z."""
    j0 = int(np.argmin(np.abs(S.th)))
    front = S.cy - S.r[:, j0]
    for k in range(2, len(S.zs)):
        if np.isfinite(front[k]) and np.isfinite(front[k - 2]) and S.zs[k] < -0.2 and front[k] - front[k - 2] > 0.05:
            return float(S.zs[k - 2])
    return float(S.zs[np.nanargmax(np.where(np.isfinite(front), -S.zs * 0 + np.arange(len(S.zs)), np.nan))])


CHIN_BIAS = -0.02                # L: the chin's rows warped this far past the design's chin. The QA reads a chin where the
                                 # front edge starts turning under (faceqa.drawn_chin), and the smoothing rounds the corner
                                 # so the turn starts ~0.015-0.02 L above it (unbiased, Clawd's reads -0.34 against -0.355)


def assemble(F, V, A, smooth_th=0.008, smooth_z=0.004, smooth_terms=0.025, chin_bias=CHIN_BIAS):
    """the head (see the module) -> (Sections, report). The skull's sections (head_construction), then per row:
      - its chin moved to the design's (the rows between the nose and the chin stretched or squeezed in z);
      - below CHEEK_TOP each row's x scaled so its half-width is the face's own outline (blended up to JAW_ROWS[1]);
      - the face as corrections on the skull's front that vanish at the outline: the midline onto the turnaround's
        base (up to FACE_TOP), a cheek term fitted so the far cheek meets the three-quarter's contour, and the nose and
        lips' relief;
    then smoothed as one field over angle and height."""
    from scipy.ndimage import gaussian_filter
    S0 = skull_sections(V, A)
    zs, th = S0.zs, S0.th
    j0 = int(np.argmin(np.abs(th)))
    # the chin: the skull's rows re-sampled so its chin lands on the design's (a z warp from the nose down)
    zc_s, zc_d, top = skull_chin(S0), F.C['chin'] + chin_bias, F.C['nose_z']      # bias < 0: past the design's, for the
                                                                                    # corner the smoothing rounds
    src = zs.copy()
    mid = (zs < top) & (zs >= zc_d)
    src[mid] = top + (zs[mid] - top) * (top - zc_s) / (top - zc_d)      # nose to chin: stretched or squeezed
    src[zs < zc_d] = zs[zs < zc_d] + (zc_s - zc_d)                       # under the chin: the neck moves with it
    cy0 = np.interp(-src, -zs, S0.cy)
    R0 = np.stack([np.interp(-src, -zs, S0.r[:, j]) for j in range(len(th))], 1)
    # align in y: the skull's forehead onto the face's midline there
    fore = (zs > 0.06) & (zs < FACE_TOP + 0.05)
    face_mid = np.interp(-zs, -F.z, F.base, left=np.nan, right=np.nan)
    ok = fore & np.isfinite(face_mid) & np.isfinite(cy0)
    dy = float(np.median(face_mid[ok] - (cy0[ok] - R0[ok, j0]))) if ok.any() else 0.0
    cy = cy0 + dy
    a = np.radians(F.C['az3'])
    wf = np.interp(-zs, -F.z, F.w, left=np.nan, right=np.nan)
    rel = np.interp(-zs, -F.z, F.relief, left=0.0, right=0.0)
    sig = np.interp(-zs, -F.z, F.sigma)
    l3 = np.interp(-zs, -F.z, F.C['lead3'], left=np.nan, right=np.nan)
    corr = np.where(np.isfinite(face_mid), face_mid - (cy - R0[:, j0]), np.nan)     # NaN off the face's rows: the
                                                                                     # smoothing mustn't average in 0s
    corr = np.nan_to_num(_smooth_rows(np.where(zs <= FACE_TOP, corr, np.nan), 2), nan=0.0)
    corr *= np.clip((FACE_TOP + 0.03 - zs) / 0.03, 0, 1)
    tj = np.clip((zs - JAW_ROWS[0]) / (JAW_ROWS[1] - JAW_ROWS[0]), 0, 1)
    front = np.cos(th) > 0

    def row(k):
        """row k's section points (x, y) after the jaw's scaling, its falloff coordinate, and a shaper by cheek term."""
        x, y = np.sin(th) * R0[k], cy[k] - np.cos(th) * R0[k]
        half = np.abs(x).max()
        wk = wf[k] if np.isfinite(wf[k]) and zs[k] <= CHEEK_TOP + 0.03 else half
        if half > 0:
            x = x * ((1 - tj[k]) * wk / half + tj[k])
        s_ = x / max((1 - tj[k]) * wk + tj[k] * min(half, 0.3), 1e-3)
        base = y + front * (corr[k] * _falloff(s_) + rel[k] * np.exp(-0.5 * (x / sig[k]) ** 2))
        return x, lambda c: base + front * c * _cheek(s_)

    valid = [k for k in range(len(zs)) if np.isfinite(cy[k]) and np.isfinite(R0[k]).all()]
    cheek = np.full(len(zs), np.nan)
    for k in valid:                                # the cheek term: the far cheek onto the three-quarter's contour
        if not (np.isfinite(l3[k]) and zs[k] <= CHEEK_FIT[0]):
            continue
        x, shaped = row(k)
        lo_c, hi_c = -0.12, 0.12
        for _ in range(30):                        # the lead grows as the cheeks come forward (c < 0)
            m = (lo_c + hi_c) / 2
            lead = (-F.C['eye_x'] * np.cos(a)) - (x * np.cos(a) + shaped(m) * np.sin(a)).min()
            lo_c, hi_c = (m, hi_c) if lead > l3[k] else (lo_c, m)
        cheek[k] = (lo_c + hi_c) / 2
    raw_cheek = cheek.copy()
    cheek = _smooth_rows(cheek, smooth_terms / A.h)
    top = np.nonzero(np.isfinite(cheek))[0]
    if len(top):                                        # held at the top fitted row's value, faded out above it
        k0 = top.min()
        cheek[:k0] = cheek[k0] * np.clip(1 - (zs[:k0] - zs[k0]) / CHEEK_FIT[1], 0, 1)
    cheek = np.nan_to_num(cheek, nan=0.0)
    R = np.full_like(R0, np.nan)
    for k in valid:
        x, shaped = row(k)
        yy = shaped(cheek[k])
        tn = np.arctan2(x, -(yy - cy[k])); o = np.argsort(tn)
        R[k] = np.interp(th, tn[o], np.hypot(x, yy - cy[k])[o], period=2 * np.pi)
    ok = np.isfinite(R).all(1) & np.isfinite(cy)
    Rs = R.copy()
    Rs[ok] = gaussian_filter(R[ok], (smooth_z / A.h, smooth_th * Sections.N / (2 * np.pi)), mode=('nearest', 'wrap'))
    rep = {'align_dy_L': round(dy, 4), 'skull_chin': round(zc_s, 4), 'design_chin': round(zc_d, 4),
           'cheek_range_L': [round(float(np.min(cheek)), 4), round(float(np.max(cheek)), 4)],
           'cheek_fit_noise_L': round(float(np.nanstd(raw_cheek - cheek)), 4) if np.isfinite(raw_cheek).any() else None}
    return Sections(zs, np.where(ok, cy, np.nan), np.where(ok[:, None], Rs, np.nan)), rep


def sections_mesh(S, step=2):
    """the sections as a closed-top mesh: rows of the (angle, height) grid joined as quads (split to triangles), the top
    closed by a fan to its centre, the bottom (the neck) open -> Mesh."""
    from .mesh import Mesh
    rows = [k for k in range(0, len(S.zs), step) if np.isfinite(S.cy[k]) and np.isfinite(S.r[k]).all()]
    n = len(S.th)
    V = []
    for k in rows:
        x, y = S.xy(k)
        V.append(np.stack([x, y, np.full(n, S.zs[k])], 1))
    V = np.concatenate(V + [[[0.0, S.cy[rows[0]], S.zs[rows[0]]]]])
    F = []
    for i in range(len(rows) - 1):
        a, b = i * n, (i + 1) * n
        for j in range(n):
            j1 = (j + 1) % n
            F += [[a + j, b + j, b + j1], [a + j, b + j1, a + j1]]
    top = len(V) - 1
    F += [[top, j, (j + 1) % n] for j in range(n)]
    m = Mesh(V, np.array(F))
    from .mesh import signed_volume
    if signed_volume(m.V, m.F) < 0:
        m.F = m.F[:, ::-1]
    return m


def banding(S, span=np.radians(60), zlo=None, zhi=0.1):
    """the face's banding: RMS of the radius' second difference over rows (L per row pair) across the face's angles
    (|angle| < span) and rows -> float. Smooth faces score about the voxel noise; ridges score several times it."""
    zlo = S.zs[np.isfinite(S.cy)].min() if zlo is None else zlo
    sel = (S.zs >= zlo) & (S.zs <= zhi)
    R = S.r[sel][:, np.abs(S.th) < span]
    d2 = R[2:] - 2 * R[1:-1] + R[:-2]
    return float(np.sqrt(np.nanmean(d2 ** 2)))


def hair_covers(spec, dy=0.0):
    """the head turnaround's hull hair (charkit.geom.hull --head: hull.glb, its per-vertex classes, its eyes) moved so its
    eyes sit at y = 0: the hair's triangles as a cover for the QA -> [(V, tris, class per triangle)] or []."""
    from charkit import bodyqa, sheetqa
    from . import io
    d = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'charkit', 'out',
                     'hull', '%s_head' % spec.get('name', 'char'))
    if not os.path.exists(os.path.join(d, 'hull.glb')):
        return []
    m = io.load(os.path.join(d, 'hull.ply'))
    lab = np.load(os.path.join(d, 'hull_labels.npy'))
    side = json.load(open(os.path.join(d, 'hull.glb.json')))
    V = m.V.copy()
    V[:, 1] -= side['eyes'][0][1]
    hair = (lab[m.F] == bodyqa.CLASS['hair']).all(1)
    return [(V, m.F[hair], np.full(int(hair.sum()), sheetqa.CLASS['hair']))]


def grade(S, spec, D, covers=None):
    """the head as the build's QA grades a face (charkit.sheetqa.measure_ours, then compare against the design's
    measures D, refcheck.face_design's): our sections' mesh as skin, the hull's hair as covers -> (checks, our
    measures)."""
    from charkit import sheetqa
    m = sections_mesh(S)
    ex = spec.get('eyes', {}).get('x', 0.168)
    covers = hair_covers(spec) if covers is None else covers
    k0 = int(np.argmin(np.abs(S.zs)))
    O = sheetqa.measure_ours([(m.V, m.F, np.full(len(m.F), sheetqa.CLASS['skin']))], covers,
                             [(ex, 0.0, 0.0), (-ex, 0.0, 0.0)], (0.0, float(S.cy[k0])), 1.0, D['ppl'], D['az_three_quarter'])
    return sheetqa.compare(O, D), O


def build(spec, out, against=None, log=print):
    """the head from a resolved spec's references into `out`: head.ply (the sections' mesh), head.npz (the sections),
    head.json (the checks, the assembly's report, the banding) and the review page -> the report. against: a build's
    qa.json whose sheet_* checks to show beside ours."""
    import time
    from charkit import refcheck
    from . import io
    t0 = time.time()
    os.makedirs(out, exist_ok=True)
    fs = spec['ref']['face_sheet']
    C = contours(refcheck._load(fs['image']), spec.get('eyes', {}).get('x', 0.168), fs.get('facing', -1))
    F = Face(C)
    V, A = skull(spec, log=log)
    S, rep = assemble(F, V, A)
    covers = hair_covers(spec)
    checks, O = grade(S, spec, C['design'], covers)
    m = sections_mesh(S)
    io.save(m, os.path.join(out, 'head.ply'))
    np.savez_compressed(os.path.join(out, 'head.npz'), zs=S.zs, cy=S.cy, r=S.r, th=S.th)
    rep.update(checks={k: {kk: vv for kk, vv in v.items() if kk in ('value', 'status', 'ours', 'design', 'mean', 'ratios')}
                       for k, v in checks.items()}, banding=round(banding(S), 5), seconds=round(time.time() - t0, 1))
    if against and os.path.exists(against):
        q = json.load(open(against))
        q = q.get('checks', q)
        rep['against'] = {'path': against, 'checks': {k[len('sheet_'):]: (v.get('value'), v.get('status')) if isinstance(v, dict)
                                                      else tuple(v) for k, v in q.items() if k.startswith('sheet_')}}
    json.dump(rep, open(os.path.join(out, 'head.json'), 'w'), indent=1, default=str)
    rep['page'] = _page(rep, S, F, V, A, m, O, C, covers, out)
    log('headfit: %s (%.0fs)' % (rep['page'], time.time() - t0))
    return rep


def _page(rep, S, F, V, A, m, O, C, covers, out):
    """the head's review page: the checks beside a build's, the QA's face regions, the contours ours against the
    design's, the sections face against skull, renders in clay and with the hull's hair."""
    import html
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    from charkit import sheetqa
    from . import raster
    from .mesh import Mesh
    img = os.path.join(out, 'img')
    os.makedirs(img, exist_ok=True)

    def save(a, name):
        Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8) if a.dtype != np.uint8 else a).save(os.path.join(img, name))
        return 'img/' + name
    D = C['design']
    L = ['<!doctype html><meta charset="utf-8"><title>code-authored head</title><style>body{font:14px/1.45 -apple-system,'
         'system-ui,sans-serif;margin:24px;background:#fafafa;color:#222}h2{font-size:17px;margin-top:30px}.row{display:flex;'
         'gap:12px;flex-wrap:wrap;align-items:flex-end}.tile{text-align:center;font-size:12px;color:#555}.tile img{display:'
         'block;border:1px solid #ddd;background:#fff}table{border-collapse:collapse;font-size:13px}td,th{border:1px solid '
         '#ddd;padding:3px 8px;text-align:right}th{background:#f0f0f0}td:first-child{text-align:left}.PASS{color:#070}'
         '.WARN{color:#b60}.FAIL{color:#c00}.note{color:#666;font-size:12px}</style>',
         '<h1>The code-authored head: %s</h1>' % html.escape(str(rep.get('spec', ''))),
         '<p class="note">The skull is head_construction\'s front and profile, carved. The face is corrections on its front '
         'that vanish at the outline: the turnaround\'s midline, a cheek term fitted per row to the three-quarter\'s '
         'contour, and the nose and lips as relief. The jaw rows are scaled to the design\'s outline, and the chin rows '
         'warped to its chin. It is graded by the QA\'s own sheet comparison (sheetqa.measure_ours + compare, as the '
         'build\'s sheet_* checks), with the head hull\'s hair as covers. Assembly: %s; banding %.5f L.</p>' % (
             html.escape(json.dumps({k: v for k, v in rep.items() if k in ('align_dy_L', 'skull_chin', 'design_chin',
                                                                           'cheek_range_L', 'cheek_fit_noise_L')})),
             rep['banding'])]
    ag = (rep.get('against') or {}).get('checks', {})
    L.append('<table><tr><th>check</th><th>ours</th><th>status</th><th>design</th>%s</tr>' % (
        '<th>%s</th>' % html.escape(os.path.relpath(rep['against']['path'])) if ag else ''))
    for k, v in rep['checks'].items():
        a = ag.get(k)
        L.append('<tr><td>%s</td><td>%s</td><td class="%s">%s</td><td>%s</td>%s</tr>' % (
            k, v.get('value'), v['status'], v['status'], v.get('design', ''),
            '<td class="%s">%s %s</td>' % (a[1], a[0], a[1]) if a else ('<td></td>' if ag else '')))
    L.append('</table><h2>The QA\'s face regions: grey both, red ours only, blue the design only</h2>')
    L.append('<div class="row"><div class="tile"><img src="%s" height="300">front, three-quarter, profile</div></div>' %
             save(sheetqa.picture(O, D), 'regions.png'))
    fig, ax = plt.subplots(1, 3, figsize=(15, 5.5))
    for i, (view, key, title) in enumerate((('profile', 'lead', 'profile: lead, L forward of the eye'),
                                            ('front', 'half', 'front: half-width, L'),
                                            ('three_quarter', 'lead', 'three-quarter: lead, L'))):
        for src, M, col in (('design', D[view], 'k'), ('ours', O[view], 'r')):
            if key == 'half':
                ax[i].plot(np.fmax(M['half_left'], M['half_right']), M['z'], '.', color=col, ms=2, label=src)
            else:
                ax[i].plot(M[key], M['z'], '.', color=col, ms=2, label=src)
        ax[i].set_ylim(-0.45, 0.25); ax[i].grid(True); ax[i].set_title(title); ax[i].legend()
    fig.tight_layout(); fig.savefig(os.path.join(img, 'contours.png'), dpi=70); plt.close(fig)
    L.append('<h2>Contours, ours (red) against the design\'s (black), as the QA reads them</h2><div class="row"><div '
             'class="tile"><img src="img/contours.png" height="380"></div></div>')
    S0 = skull_sections(V, A)
    fig, axs = plt.subplots(1, 6, figsize=(18, 3.6))
    for ax, z in zip(axs, (0.1, 0.0, -0.1, -0.2, -0.28, -0.34)):
        k = int(np.argmin(np.abs(S.zs - z)))
        x, y = S0.xy(k); ax.plot(x, y + rep['align_dy_L'], color='0.6', lw=1)
        x, y = S.xy(k); ax.plot(x, y, 'r-', lw=1)
        ax.plot([0.168, -0.168], [0, 0], 'bo', ms=3)
        ax.set_aspect('equal'); ax.invert_yaxis(); ax.set_xlim(-0.45, 0.45); ax.set_ylim(0.75, -0.25); ax.grid(True)
        ax.set_title('z = %.2f' % z, fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(img, 'sections.png'), dpi=70); plt.close(fig)
    L.append('<h2>Sections: the skull as carved (grey) and the head (red); the eyes blue</h2><div class="row"><div '
             'class="tile"><img src="img/sections.png" height="240"></div></div>')
    fr = raster.Frame.around([m], res=520, aspect=0.85)
    hair = [Mesh(c[0], c[1]) for c in covers]
    L.append('<h2>The head in clay, and with the head hull\'s hair</h2><div class="row">')
    for az in (0, 35, 90, 180):
        im = raster.render([(m, dict(color=(0.86, 0.8, 0.76), shade='lambert'))], az, fr)
        L.append('<div class="tile"><img src="%s" height="360">%d deg</div>' % (save(im, 'clay_%03d.png' % az), az))
    L.append('</div><div class="row">')
    for az in (0, 35, 90):
        im = raster.render([(m, dict(color=(0.96, 0.84, 0.76), shade='lambert'))] +
                           [(h, dict(color=(0.85, 0.45, 0.28), shade='lambert')) for h in hair], az, fr)
        L.append('<div class="tile"><img src="%s" height="360">%d deg, with hair</div>' % (save(im, 'hair_%03d.png' % az), az))
    L.append('</div>')
    p = os.path.join(out, 'index.html')
    open(p, 'w').write('\n'.join(L))
    return p


def main(args):
    """python -m charkit.geom headfit SPEC [--out DIR] [--against BUILD/qa/qa.json] [--no-open]"""
    import subprocess
    from charkit import manifest, refcheck
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    spec = manifest.resolve(json.load(open(refcheck._p(args[0]))))
    out = refcheck._p(opt('--out', 'charkit/out/head/%s' % spec.get('name', 'char')))
    rep = build(spec, out, refcheck._p(opt('--against')) if opt('--against') else None)
    for k, v in rep['checks'].items():
        print('%-14s %-5s %s' % (k, v['status'], v.get('value')))
    if '--no-open' not in args:
        subprocess.run(['open', rep['page']])
