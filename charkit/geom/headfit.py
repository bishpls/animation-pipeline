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

from .headgeom import (Sections, _smooth_rows, _smoothstep, _row_at, place, theta_of, _inside, project, front_point,
                       sections_mesh, quality, _neighbours, _harmonic, _near, cylinder_cage)  # noqa: F401

NOSE_SIGMA, LIP_SIGMA = 0.035, 0.07         # the relief's half-widths (L): an anime nose is a narrow wedge
Q_DEFAULT = 2.2


def _smooth(v, k=3):
    """a running mean over finite samples (k rows each side), NaN kept where the input is NaN."""
    out = np.full(len(v), np.nan)
    for i in np.nonzero(np.isfinite(v))[0]:
        w = v[max(0, i - k):i + k + 1]
        out[i] = np.nanmean(w)
    return out


def eye_views(rgb, eye_x, facing=-1):
    """the head sheet's eyes measured per view (charkit.eyeqa on each eye's crop, as charkit.eyepage cuts them): -> {view:
    dict(w, h (the opening's width and height, L), dz (its centre's height over the eye's, L))}; the front's is the two
    eyes' mean, the three-quarter's and the profile's the near eye's."""
    from charkit import eyeqa, refcheck
    rgb0, _ = refcheck.without_guides(np.asarray(rgb, float))
    ppl = refcheck.FACE_PPL
    _, f, H = refcheck.at_scale(rgb0, eye_x, 2 * eye_x * ppl, facing)
    own = ppl / f
    hw, hh = refcheck.EYE_BOX[0] * own, refcheck.EYE_BOX[1] * own
    edge = np.concatenate([rgb0[:4].reshape(-1, 3), rgb0[-4:].reshape(-1, 3), rgb0[:, :4].reshape(-1, 3)])
    bg = np.median(edge, 0)
    out = {}
    for view, n in (('front', 2), ('three_quarter', 2), ('profile', 1)):
        eyes = sorted((H['heads'].get(view) or {}).get('eyes') or [])
        if len(eyes) != n:
            continue
        pick = eyes if view == 'front' else eyes[-1:]
        ms = []
        for x, y in pick:
            cx, cy = x / f, y / f
            crop = rgb0[int(cy - hh):int(cy + hh), int(cx - hw):int(cx + hw)]
            alpha = (np.abs(crop - bg).max(-1) > 0.035).astype(float)[..., None]
            m = eyeqa.measure(np.concatenate([crop, alpha], -1), own)
            if not m.get('found'):
                continue
            rows = np.nonzero(m['_masks']['opening'].any(1))[0]
            dz = ((crop.shape[0] / 2) - (rows.min() + rows.max()) / 2) / own if len(rows) else 0.0
            ms.append((m['open_w'], m['open_h'], dz))
        if ms:
            w, h, dz = np.mean(ms, 0)
            out[view] = dict(w=round(float(w), 4), h=round(float(h), 4), dz=round(float(dz), 4))
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
    # the outline: a drawn line inside the face cuts some rows' region short; those rows (well under their neighbours'
    # median) are dropped and bridged. (A running maximum would handle them too, but on a tapering jaw it always takes
    # the wider row above: 0.012 L too wide at the jaw.)
    med = np.array([np.nanmedian(half[max(0, i - 3):i + 4]) if np.isfinite(half[max(0, i - 3):i + 4]).any() else np.nan
                    for i in range(len(z))])
    good = np.isfinite(half) & (half >= med - 0.01)
    w = np.full(len(z), np.nan)
    if good.sum() > 2:
        idx = np.arange(len(z))
        span = (idx >= idx[good][0]) & (idx <= idx[good][-1])
        w[span] = np.interp(idx[span], idx[good], half[good])
    below = (z < -0.02) & (z > -0.2)
    nose_z = float(z[below][np.nanargmax(lead_p[below])]) if np.isfinite(lead_p[below]).any() else -0.1
    nz, ny = neck_front(rgb, eye_x, facing)
    try:
        ev = eye_views(rgb, eye_x, facing)
    except Exception:                         # (a sheet whose eyes can't be cut: the window falls back to its defaults)
        ev = {}
    try:
        jd = jaw_line(D)
        jd['rise'] = underside_rise(rgb, eye_x, facing)
    except Exception:                         # (a sheet whose chin can't be read: the chin stays the rows' own)
        jd = None
    return dict(z=z, mid=-lead_p, w=_smooth(w, 2), lead3=lead3, az3=float(D['az_three_quarter']), chin=chin,
                nose_z=nose_z, eye_x=eye_x, design=D, neck_z=nz, neck_y=ny, eyes=ev, jaw_design=jd)


def neck_front(rgb, eye_x, facing=-1, z0=-0.5, dz=0.005):
    """the design's neck in profile: per row under the chin, the front edge of the drawn skin (head_turnaround's
    profile; its back is under the hair), in the eye frame (y back, 0 at the eyes) -> (z (descending), y)."""
    from charkit import bodyqa
    from . import hull
    views, info = hull.views_from_heads(rgb, eye_x, facing, floor=z0 - 0.02)
    v = views['profile']
    cls = bodyqa.classes(rgb, v.mask, v.eye_y, v.ppl)[0]
    zs = np.arange(-0.3, z0, -dz)
    ys = np.full(len(zs), np.nan)
    for i, z in enumerate(zs):
        r = int(round(v.eye_y - z * v.ppl))
        skin = np.nonzero((cls[r] == bodyqa.CLASS['skin']) & v.mask[r])[0]
        if len(skin):
            u = ((skin.min() if facing < 0 else skin.max()) - v.axis) / v.ppl
            ys[i] = (u if facing < 0 else -u) - info['y_e']
    return zs, ys


JAW_UNDER = {'jaw_under': True, 'jaw_rise': 'design', 'jaw_rise_range': [8.0, 25.0]}   # the style's face section
                                 # overrides these (charkit/styles: DEFAULT says what each is)


def jaw_line(D, dx=0.005):
    """the design's jaw line in front (refcheck.face_design's front: the face region's half-width per row down to its own
    chin point): the height at which the face's outline reaches each half-width x, from the chin point (x 0) out to the
    widest row under the cheek; the lower face's outline read as a curve over x (the V under the chin) ->
    dict(x, z (L, the eye frame), chin, neck (the neck's half-width under it))."""
    F = D['front']
    z = np.asarray(F['z'], float)
    half = 0.5 * (np.asarray(F['half_left'], float) + np.asarray(F['half_right'], float))
    chin = float(F.get('chin', np.nanmin(np.where(np.isfinite(half), z, np.nan))))
    sel = np.isfinite(half) & (z < -0.12) & (z >= chin - 1e-6)
    zs, hs = z[sel], half[sel]
    o = np.argsort(zs)                                   # from the chin up
    zs, hs = zs[o], np.maximum.accumulate(hs[o])         # the outline widening from the chin up (a row cut short by a
    hs[0] = 0.0                                          # drawn line inside the face doesn't narrow it)
    xs = np.arange(0.0, hs[-1] + 1e-9, dx)
    zx = np.interp(xs, hs, zs)
    return dict(x=[round(float(v), 4) for v in xs], z=[round(float(v), 4) for v in zx], chin=round(chin, 4),
                neck=float(F['neck']) if F.get('neck') else None)


def underside_rise(rgb, eye_x, facing=-1):
    """the design's chin underside in profile: its angle (degrees, + rising from the chin toward the throat), read on the
    head sheet's profile as the QA reads it (charkit.faceregion.jaw_profile) -> degrees or None."""
    import importlib
    fr = importlib.import_module('charkit.faceregion')
    views, ppl = fr.design_jaw_views(rgb, eye_x, facing, which=('profile',))
    return fr.jaw_profile(views['profile']['cls'], ppl).get('underside_deg') if 'profile' in views else None


def jaw_under(C, face=None):
    """the jaw's underside for the head's mesh (charkit.code_base.UnderJaw), from the design's jaw line (C['jaw_design'])
    and the style's face section (JAW_UNDER's keys): None when the style builds the chin as rows alone (jaw_under off) or
    the design's jaw can't be read -> dict(x, z (the jaw line in front), rise (degrees: the underside's rise from the jaw
    line toward the throat, the design's measured in profile or the style's, within jaw_rise_range), neck)."""
    st = dict(JAW_UNDER, **(face or {}))
    J = C.get('jaw_design')
    if not st['jaw_under'] or not J or len(J.get('x') or ()) < 5:
        return None
    lo, hi = st['jaw_rise_range']
    rise = J.get('rise') if st['jaw_rise'] == 'design' else st['jaw_rise']
    rise = float(np.clip(12.0 if rise is None else rise, lo, hi))
    return dict(x=J['x'], z=J['z'], chin=J['chin'], neck=J['neck'], rise=round(rise, 1),
                rise_design=J.get('rise'))


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


FEATURE_WINDOW = 0.10            # L of rows: the profile's drawn features (the lashes, the nose, the lips) narrower than this
                                 # come off its front edge before the skull is carved; the face's own relief puts them back


def without_features(v, window=FEATURE_WINDOW, zlo=-0.45, zhi=0.25, facing=-1):
    """a profile view's silhouette with its face's drawn features smoothed off its front edge: per row the edge's
    reach forward, opened then closed over `window` L of rows (a forward bump or a notch narrower than that goes: the
    nose, the lips, the lashes, the eye's set-in), between zlo and zhi L from the eye line. In place -> the rows changed."""
    from scipy.ndimage import grey_closing, grey_opening
    m = v.mask
    H, W = m.shape
    rows = np.arange(H)
    z = (v.eye_y - rows) / v.ppl
    sel = (z >= zlo) & (z <= zhi) & m.any(1)
    edge = np.full(H, np.nan)
    for r in np.nonzero(sel)[0]:
        c = np.nonzero(m[r])[0]
        edge[r] = c[0] if facing < 0 else c[-1]
    idx = np.nonzero(np.isfinite(edge))[0]
    if len(idx) < 5:
        return 0
    reach = -edge[idx] if facing < 0 else edge[idx]                  # larger = further forward
    k = max(3, int(window * v.ppl))
    smooth = grey_closing(grey_opening(reach, size=k), size=k)
    new = -smooth if facing < 0 else smooth
    changed = 0
    for r, e0, e1 in zip(idx, edge[idx], new):
        e1 = int(round(e1))
        c = np.nonzero(m[r])[0]
        if facing < 0:
            m[r, :e1] = False
            m[r, e1:c[-1] + 1] |= np.arange(e1, c[-1] + 1) <= c[-1]
        else:
            m[r, e1 + 1:] = False
            m[r, c[0]:e1 + 1] = True
        changed += int(e1 != e0)
    return changed


def skull(spec, h=0.004, log=print):
    """the bald head from head_construction (the skull's authority): its front and profile carved with the style's
    prior, the ears cut off, no silhouette restoration; shifted so the eyes sit at y = 0 -> (V bool, Axes)."""
    from charkit import manifest, refcheck, styles
    from . import hull
    M = manifest.load(spec['ref']['manifest'])['references']
    rgb, _ = refcheck.without_guides(refcheck._load(M['head_construction']['path']))
    ex = spec.get('eyes', {}).get('x', 0.168)
    facing = spec['ref'].get('face_sheet', {}).get('facing', -1)
    views, info = hull.views_from_heads(rgb, ex, facing, ears=False)
    info['profile_rows_smoothed'] = without_features(views['profile'], facing=facing)
    A = hull.axes_for(views, h)
    prior = dict(styles.load(spec.get('style', 'anime'))['hull'], restore=False)
    V = hull.rounded(views, A, ['front', 'profile'], **prior)
    A.ys = A.ys - info['y_e']
    log('skull: head_construction at %.0f px/L, grid %s, eyes %.3f L in front of the neck, %d profile rows smoothed' % (
        info['ppl'], A.shape, -info['y_e'], info['profile_rows_smoothed']))
    return V, A


def bridge_ears(half, dz, window=0.3, bump=0.01, pad=0.02):
    """a front silhouette's half-width per row with the ears taken out: the rows where it stands out of its own
    opening (a running minimum then maximum over `window` L) by more than `bump` L, grown by `pad` L, are bridged by a
    monotone cubic from the rows either side. The opening itself flattens the skull's broad widest band into a plateau
    with kinked ends; used only to find the ear, it doesn't. -> half-widths."""
    from scipy.interpolate import PchipInterpolator
    from scipy.ndimage import binary_dilation, maximum_filter1d, minimum_filter1d
    ok = np.isfinite(half)
    h = np.where(ok, half, 0.0)
    k = max(3, int(window / dz))
    opened = maximum_filter1d(minimum_filter1d(h, k), k)
    ear = binary_dilation(ok & (h - opened > bump), iterations=max(1, int(pad / dz)))
    keep = ok & ~ear
    i = np.arange(len(half))
    kept = np.nonzero(keep)[0]
    if not ear.any() or len(kept) < 4:
        return half
    inside = ear & ok & (i > kept[0]) & (i < kept[-1])     # only runs with kept rows either side: never extrapolated
    out = half.copy()
    out[inside] = PchipInterpolator(i[keep], half[keep])(i[inside])
    return out


NAPE = (-0.05, -0.37)            # z: the back of the head narrows from the skull's width (above the first) to the neck's (by
                                 # the second, the jaw's underside)


def _smooth_piecewise(v, sigma, jump=0.03, smooth=None):
    """a series smoothed on each side of its jumps separately (a change over `jump` L between rows: the chin's underside
    in profile, where the front edge steps back to the neck): the smoothing keeps a drawn corner a corner."""
    smooth = smooth or _smooth_rows
    ok = np.isfinite(v)
    cut = np.nonzero(ok[1:] & ok[:-1] & (np.abs(np.diff(np.where(ok, v, 0.0))) > jump))[0] + 1
    out = np.full(len(v), np.nan)
    for a, b in zip(np.r_[0, cut], np.r_[cut, len(v)]):
        out[a:b] = smooth(v[a:b], sigma)
    return out


def _smooth_crown(half, sigma):
    """a half-width over rows (the crown first) smoothed by a Gaussian, padded at the crown by its odd reflection about a
    zero just above the first row, so it still runs to zero there; NaNs (rows off the head) kept."""
    from scipy.ndimage import gaussian_filter1d
    ok = np.isfinite(half)
    if not ok.any():
        return half
    first = np.nonzero(ok)[0][0]
    h = np.where(ok, half, 0.0)[first:]
    n = int(3 * sigma) + 2
    pad = np.concatenate([-h[:n][::-1], h])
    sm = gaussian_filter1d(pad, sigma, mode='nearest')[n:]
    out = np.full(len(half), np.nan)
    out[first:] = np.where(ok[first:], np.maximum(sm, 0.0), np.nan)
    return out


def skull_analytic(spec, dz=0.004, smooth=0.015, log=print):
    """the bald head from head_construction without voxels: per row, the superellipse (the style's exponent) inscribed
    in the front silhouette's width (ears opened off) and the profile's depth (its drawn features smoothed off), read
    to a pixel at the sheet's ~900 px/L, each extent smoothed over `smooth` L of rows; its eyes at y = 0. The carve's
    own sections without its voxel grain. -> Sections."""
    from charkit import manifest, refcheck, styles
    from . import hull
    M = manifest.load(spec['ref']['manifest'])['references']
    rgb, _ = refcheck.without_guides(refcheck._load(M['head_construction']['path']))
    ex = spec.get('eyes', {}).get('x', 0.168)
    facing = spec['ref'].get('face_sheet', {}).get('facing', -1)
    views, info = hull.views_from_heads(rgb, ex, facing, ears=True)
    without_features(views['profile'], facing=facing)
    p = styles.load(spec.get('style', 'anime'))['hull']['p']
    f, pr = views['front'], views['profile']
    top = min((f.eye_y - np.nonzero(f.mask.any(1))[0].min()) / f.ppl, (pr.eye_y - np.nonzero(pr.mask.any(1))[0].min()) / pr.ppl)
    zs = np.arange(top - dz / 2, hull.HEAD_FLOOR, -dz)

    def extents(v, z):
        r = int(round(v.eye_y - z * v.ppl))
        if not (0 <= r < v.mask.shape[0]) or not v.mask[r].any():
            return np.nan, np.nan
        c = np.nonzero(v.mask[r])[0]
        runs = np.split(c, np.nonzero(np.diff(c) > 1)[0] + 1)
        run = min(runs, key=lambda q: 0 if q[0] <= v.axis <= q[-1] else min(abs(q[0] - v.axis), abs(q[-1] - v.axis)))
        return (run[0] - 0.5 - v.axis) / v.ppl, (run[-1] + 0.5 - v.axis) / v.ppl
    E = np.array([extents(f, z) + extents(pr, z) for z in zs])          # x left, x right, y front, y back
    E[:, 2:] -= info['y_e']                                             # the eyes at y = 0
    # below the neck's narrowest row the construction's bust flares into the shoulders, which are the body's: the neck
    # holds its width and depth down to the floor
    band = (zs < -0.45) & (zs > -0.62) & np.isfinite(E[:, 1] - E[:, 0])        # under the jaw: the chin's V is narrower
    if band.any():
        kn = np.nonzero(band)[0][np.argmin((E[:, 1] - E[:, 0])[band])]
        E[kn + 1:] = E[kn]
    E[:, 0], E[:, 1] = -bridge_ears(-E[:, 0], dz), bridge_ears(E[:, 1], dz)
    # smoothed over rows: the centres plainly, the half-widths reflected oddly about the crown (they run to zero there;
    # a one-sided smoothing would widen the top rows into a flat top)
    # the sections from smoothly varying extents; then the front alone onto the profile's front edge smoothed piecewise
    # (it steps back under the chin, a drawn corner kept), so the chin turns sharply while the jaw's sides and back,
    # which don't step, stay smooth (one ellipse per row would carry half the step round to the sides)
    rx = _smooth_crown((E[:, 1] - E[:, 0]) / 2, smooth / dz)
    ry = _smooth_crown((E[:, 3] - E[:, 2]) / 2, smooth / dz)
    cy = _smooth_rows((E[:, 2] + E[:, 3]) / 2, smooth / dz)
    front_sharp = _smooth_piecewise(E[:, 2], smooth / dz)
    th = np.linspace(-np.pi, np.pi, Sections.N, endpoint=False)
    # the back half's half-width: the front silhouette's above the ears; below them it narrows to the neck's by the
    # jaw's underside (the front view sees the jaw, the widest; the nape behind it is the neck's back). One width for
    # both halves hung the head on the neck like a cap on a stem
    rx_b = rx.copy()
    okx = np.isfinite(rx)
    neck = (zs < NAPE[1]) & okx
    if neck.any() and (okx & (zs >= NAPE[0])).any():
        rn = float(np.nanmedian(rx[neck & (zs > NAPE[1] - 0.1)]))
        t = _smoothstep((zs - NAPE[1]) / (NAPE[0] - NAPE[1]))
        rx_b = np.where(okx & (zs < NAPE[0]), np.minimum(rx, rn + (rx - rn) * t), rx)
    w = np.where(np.cos(th) >= 0, 1.0, 1.0 - np.cos(th) ** 2)[None, :]   # 1 in front, 0 straight back, smooth at the sides
    rxe = rx_b[:, None] + (rx - rx_b)[:, None] * w
    with np.errstate(divide='ignore', invalid='ignore'):
        r = 1.0 / (np.abs(np.sin(th)[None, :] / rxe) ** p + np.abs(np.cos(th)[None, :] / ry[:, None]) ** p) ** (1 / p)
    ok = np.isfinite(rx) & np.isfinite(ry) & (rx > 0) & (ry > 0)
    j0 = int(np.argmin(np.abs(th)))
    g = np.where(np.cos(th) > 0, np.cos(th) ** 2, 0.0)
    for k in np.nonzero(ok & np.isfinite(front_sharp))[0]:
        d = front_sharp[k] - (cy[k] - r[k, j0])
        if abs(d) < 1e-5:
            continue
        x, y = np.sin(th) * r[k], cy[k] - np.cos(th) * r[k] + d * g
        tn = np.arctan2(x, -(y - cy[k])); o = np.argsort(tn)
        r[k] = np.interp(th, tn[o], np.hypot(x, y - cy[k])[o], period=2 * np.pi)
    log('skull: head_construction analytic, %d rows of superellipses (p %.1f) from %.3f to %.2f L' % (ok.sum(), p, zs[0], zs[-1]))
    return Sections(zs, np.where(ok, cy, np.nan), np.where(ok[:, None], r, np.nan))


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


SOCKET = (0.07, 0.05)            # the eyes' sockets' half-widths (L) across and up (the 'socket' eye region)
EYE_REGION = {'eye_region': 'socket', 'margin': 0.03, 'reach': [0.2, 0.3], 'yaw': 'design', 'max_yaw': 40.0,
              'hold': True, 'curve': 2.0, 'release': 0.5, 'forward': None, 'cheek_peak': 0.5}   # the eye region's construction (charkit/styles' face
                                                             # section overrides it: styles.DEFAULT says what each is)
WINDOW_RELEASE = (0.02, 0.2)     # L: toward the midline the window's hold lets go, from `release` of the window's
                                 # half-width in from the eye (the style's) to this x, by up to this much (the nose's
                                 # side is the profile's midline, not the eye's plane)
EYE_OPENING = (0.18, 0.15)       # L: the front eye opening's width and height when the design's can't be measured


def face_style(spec):
    """the spec's style profile's face section (charkit/styles): how its eye region is built."""
    from charkit import styles
    return styles.load(spec.get('style', 'anime'))['face']


def eye_window(C, face=None):
    """the eye region's construction from the design's eyes (C['eyes']: eye_views) and the style's face section (charkit/
    styles: EYE_REGION's keys) -> dict(mode, a, b (the window's half-width and half-height, L: the front opening's plus
    the margin), zc (its centre's height), tan (the plane's slope back toward the outer corner, y per |x|: the tangent
    of the yaw, the profile opening's width over the front's; a plane's opening shows its width times that in profile),
    yaw (degrees), reach (L: how far above and below the window the correction reaches), margin, hold, curve and
    cheek_peak (the style's))."""
    st = dict(EYE_REGION, **(face or {}))
    ev = C.get('eyes') or {}
    fr = ev.get('front') or {}
    fw, fh = fr.get('w') or EYE_OPENING[0], fr.get('h') or EYE_OPENING[1]
    if st['yaw'] == 'design':
        pw = (ev.get('profile') or {}).get('w')
        yaw = float(np.degrees(np.arctan(pw / fw))) if pw else 25.0
    else:
        yaw = float(st['yaw'])
    yaw = min(yaw, st['max_yaw'])
    two = lambda v: [float(v), float(v)] if np.isscalar(v) else [float(u) for u in v]
    return dict(mode=st['eye_region'], a=fw / 2 + st['margin'], b=fh / 2 + st['margin'], zc=float(fr.get('dz') or 0.0),
                tan=float(np.tan(np.radians(yaw))), yaw=round(yaw, 2), reach=two(st['reach']),
                margin=float(st['margin']), hold=bool(st['hold']), curve=two(st['curve']),
                release=float(st['release']), forward=np.inf if st.get('forward') is None else float(st['forward']),
                cheek_peak=float(st['cheek_peak']))


def eye_fill(zs, X, Y, eye_x, W, iters=12):
    """the anime eye region as a correction of the face's front, on the sections' own grid: rows zs (descending, evenly
    spaced), and per row the front's points from the midline (column 0) round to the side (the last column, a quarter
    turn): X, Y (len(zs), n) in the eye frame. The smoothest correction of y (least thin-plate energy; the other side is
    the mirror) that lays the eye's opening (the window less half its margin) on the window's plane (y = 0 at the eye's
    centre, turned back toward the outer corner: W['tan']), holds the brow and the cheek round it behind that plane
    (allowed forward of it by W['curve'] * d^2 at d L out of the window, and let go toward the midline, whose nose and
    muzzle are the profile's), and vanishes at the midline (the profile's silhouette stays the design's), round the side
    and past the region's reach above and below. -> delta (len(zs), n), to add to Y."""
    from scipy import sparse
    from scipy.sparse.linalg import spsolve
    up, down = W['reach']
    nz, n = X.shape
    inside = (zs >= W['zc'] - W['b'] - down) & (zs <= W['zc'] + W['b'] + up)
    D = np.zeros((nz, n))
    if inside.sum() < 5:
        return D
    ks = np.nonzero(inside)[0]
    Xr, Yr, Zr = np.abs(X[ks]), Y[ks], np.repeat(zs[ks][:, None], n, 1)
    m = len(ks)
    hz = abs(zs[1] - zs[0])
    hx = float(np.nanmedian(np.hypot(np.diff(Xr, axis=1), np.diff(Yr, axis=1))))     # the arc between columns
    idx = np.arange(m * n).reshape(m, n)
    rr, cc, vv = [], [], []
    e = 0
    for i in range(1, m - 1):
        for j in range(0, n - 1):
            left = idx[i, j - 1] if j > 0 else idx[i, 1]                                # the midline: mirrored
            for c, v in ((idx[i, j + 1], 1 / hx ** 2), (left, 1 / hx ** 2), (idx[i + 1, j], 1 / hz ** 2),
                         (idx[i - 1, j], 1 / hz ** 2), (idx[i, j], -2 / hx ** 2 - 2 / hz ** 2)):
                rr.append(e); cc.append(c); vv.append(v)
            e += 1
    Lap = sparse.csr_matrix((vv, (rr, cc)), shape=(e, m * n))
    plane = (Xr - eye_x) * W['tan']
    fixed = np.zeros((m, n), bool); val = np.zeros((m, n))
    fixed[0] = fixed[-1] = True; fixed[:, 0] = fixed[:, -1] = True          # above, below, the midline, the side
    rho_c = np.hypot((Xr - eye_x) / (W['a'] - W['margin'] / 2), (Zr - W['zc']) / (W['b'] - W['margin'] / 2))
    core = (rho_c <= 1) & ~fixed
    fixed |= core; val[core] = np.maximum(plane - Yr, -W.get('forward', np.inf))[core]   # (forward: at most this far out)
    rho = np.hypot((Xr - eye_x) / W['a'], (Zr - W['zc']) / W['b'])
    cu, cd = (W.get('curve', 2.0),) * 2 if np.isscalar(W.get('curve', 2.0)) else W['curve']
    allow = np.where(Zr > W['zc'], cu, cd) * (np.maximum(0.0, rho - 1) * np.sqrt(W['a'] * W['b'])) ** 2
    x0, x1 = WINDOW_RELEASE[0], max(eye_x - W.get('release', 0.5) * W['a'], WINDOW_RELEASE[0] + 0.01)
    allow = allow + WINDOW_RELEASE[1] * (1 - _smoothstep((Xr - x0) / (x1 - x0)))  # toward the midline: let go
    hold = ~fixed & bool(W.get('hold', True))
    for _ in range(iters):
        F_ = ~fixed.ravel()
        A = Lap[:, F_]; Bc = Lap[:, ~F_]
        d = val.ravel().copy()
        d[F_] = spsolve((A.T @ A).tocsc(), -(A.T @ (Bc @ d[~F_])))
        d = d.reshape(m, n)
        ahead = hold & ~fixed & (Yr + d < plane - allow - 1e-4)            # still in front of the plane: hold it there
        if not ahead.any():
            break
        fixed |= ahead; val[ahead] = (plane - allow - Yr)[ahead]
    D[ks] = d
    return D


SCALE_SMOOTH = 0.025             # L of rows: the jaw's and neck's width scaling is smoothed over this
BROAD = 0.05                     # L of height: the midline's correction that spreads across the face is this smooth; the
                                 # rest (the nose, the lips, the bridge) stays at the midline, narrow


def _falloff(s):
    """1 at the midline, 0 at the outline, flat at both: (1 - s^2)^2 on [0, 1]."""
    s = np.clip(np.abs(s), 0, 1)
    return (1 - s * s) ** 2


def _cheek(s, peak=0.5):
    """0 at the midline and the outline, most at `peak` (a share of the half-width) between: the cheek's shape term,
    s^p (1 - s)^2 scaled to 1 there (peak 0.5: 16 s^2 (1 - s)^2). Out toward the side (the cheekbone), the far cheek's
    three-quarter contour is met without bringing the cheek under the eye forward."""
    s = np.clip(np.abs(s), 0, 1)
    p = 2 * peak / (1 - peak)
    return s ** p * (1 - s) ** 2 / (peak ** p * (1 - peak) ** 2)


def skull_chin(S):
    """the skull's chin: the lowest row before its midline front turns back under the jaw (a jump back of 0.05 L within
    two rows) -> z."""
    j0 = int(np.argmin(np.abs(S.th)))
    front = S.cy - S.r[:, j0]
    for k in range(2, len(S.zs)):
        if np.isfinite(front[k]) and np.isfinite(front[k - 2]) and S.zs[k] < -0.2 and front[k] - front[k - 2] > 0.05:
            return float(S.zs[k - 2])
    return float(S.zs[np.nanargmax(np.where(np.isfinite(front), -S.zs * 0 + np.arange(len(S.zs)), np.nan))])


CHIN_BIAS = -0.01                # L: the chin's rows warped this far past the design's chin: the QA reads a chin where the
                                 # front edge starts turning under (faceqa.drawn_chin), a row or two above the corner's
                                 # own (swept on Clawd: -0.01 reads the chin exactly and keeps the outline within 0.021 L)


def assemble(F, V, A=None, smooth_th=0.008, smooth_z=0.004, smooth_terms=0.08, chin_bias=CHIN_BIAS,
             terms=('corr', 'rel', 'cheek', 'scale', 'warp', 'socket'), face=None):
    """the head (see the module) -> (Sections, report). The skull's sections (head_construction), then per row:
      - its chin moved to the design's (the rows between the nose and the chin stretched or squeezed in z);
      - below CHEEK_TOP each row's x scaled so its half-width is the face's own outline (blended up to JAW_ROWS[1]);
      - the face as corrections on the skull's front that vanish at the outline: the midline onto the turnaround's
        base (up to FACE_TOP), a cheek term fitted so the far cheek meets the three-quarter's contour, and the nose and
        lips' relief;
    then smoothed as one field over angle and height."""
    from scipy.ndimage import gaussian_filter
    S0 = V if isinstance(V, Sections) else skull_sections(V, A)
    zs, th = S0.zs, S0.th
    A = A if A is not None else type('Rows', (), {'h': abs(zs[1] - zs[0])})()
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
    sig = np.interp(-zs, -F.z, F.sigma)
    l3 = np.interp(-zs, -F.z, F.C['lead3'], left=np.nan, right=np.nan)
    # the midline onto the design's, in two parts: a broad correction, smooth over BROAD L of height, spread across the
    # face by the falloff; and the exact remainder (the nose, the lips, the bridge), kept narrow at the midline. A
    # correction that changes quickly with height and spreads across the face bands it
    mid_d = _smooth_rows(np.interp(-zs, -F.z, F.C['mid'], left=np.nan, right=np.nan), 0.006 / A.h)
    diff = np.where(np.isfinite(mid_d) & (zs <= FACE_TOP), mid_d - (cy - R0[:, j0]), np.nan)   # NaN off the face's
    fade = _smoothstep((FACE_TOP + 0.04 - zs) / 0.08)                                         # rows: the smoothing
    corr = np.nan_to_num(_smooth_rows(diff, BROAD / A.h), nan=0.0) * fade                       # mustn't average 0s in
    rel = np.nan_to_num(diff - _smooth_rows(diff, BROAD / A.h), nan=0.0) * fade
    corr, rel = corr * ('corr' in terms), rel * ('rel' in terms)          # (terms: switched off to measure each alone)
    tj = _smoothstep((zs - JAW_ROWS[0]) / (JAW_ROWS[1] - JAW_ROWS[0]))
    front = np.cos(th) > 0
    # the jaw's scaling per row (the design's outline over the skull's half-width), smoothed over rows: both widths are
    # quantised a pixel at a time, and a scale that jitters row to row stripes the whole section
    half_all = np.nanmax(np.abs(np.sin(th)[None, :] * R0), 1)
    wk_all = np.where(np.isfinite(wf) & (zs <= CHEEK_TOP + 0.03), wf, half_all)
    # under the chin: the neck's own half-width, the design's (head_turnaround's front: the neck 0.06 L under its chin),
    # eased in over the jaw's underside
    neck_d = F.C['design']['front'].get('neck')
    wk_back = wk_all.copy()
    if neck_d:
        # under the chin the face's outline gives way to the neck's half-width (the design's, head_turnaround's front),
        # eased in over the jaw's underside
        under = zs < zc_d
        ease = _smoothstep((zc_d - zs) / 0.06)
        wk_all = np.where(under, (1 - ease) * np.where(np.isfinite(wk_all), wk_all, half_all) + ease * neck_d, wk_all)
        # round the chin the face's outline runs to its point while the neck shows behind it (the front view's silhouette
        # there is the neck's): the section's back keeps the neck's width, its front narrows to the chin's V
        near = zs < zc_d + 0.1
        wk_back = np.where(near & np.isfinite(wk_all), np.maximum(wk_all, neck_d), wk_all)
        tj = np.where(under, 0.0, tj)

    def scaled(w):
        sc = np.where(half_all > 0, (1 - tj) * w / np.where(half_all > 0, half_all, 1) + tj, 1.0)
        return np.nan_to_num(_smooth_rows(np.where(np.isfinite(cy), sc, np.nan), SCALE_SMOOTH / A.h), nan=1.0)
    scale, scale_b = scaled(wk_all), scaled(wk_back)
    if 'scale' not in terms:
        scale, scale_b = np.ones_like(scale), np.ones_like(scale)
    wc_all = np.nan_to_num(_smooth_rows(np.where(np.isfinite(cy), (1 - tj) * wk_all + tj * np.minimum(half_all, 0.3), np.nan),
                                        SCALE_SMOOTH / A.h), nan=0.3)
    g_front = np.where(np.cos(th) > 0, np.cos(th) ** 2, 0.0)          # 1 at the front, 0 from the sides back
    win = eye_window(F.C, face)                    # the style's eye region: the socket below, or the anime window

    def row(k):
        """row k's section points (x, y) after the jaw's scaling, its falloff coordinate, and a shaper by cheek term."""
        x = np.sin(th) * R0[k] * (scale_b[k] + (scale[k] - scale_b[k]) * g_front)
        y = cy[k] - np.cos(th) * R0[k]
        s_ = x / max(wc_all[k], 1e-3)
        base = y + front * (corr[k] * _falloff(s_) + rel[k] * np.exp(-0.5 * (x / sig[k]) ** 2))
        return x, lambda c: base + front * c * _cheek(s_, win['cheek_peak'])

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
        cheek[:k0] = cheek[k0] * _smoothstep(1 - (zs[:k0] - zs[k0]) / CHEEK_FIT[1])
    cheek = np.nan_to_num(cheek, nan=0.0) * ('cheek' in terms)
    # the eyes' sockets: where the design draws the eye in profile (the eye frame's y = 0, set back from the nose's
    # bridge by the profile's lead) is where the build's eye plate must sit, on the surface; a smooth dip at each eye takes
    # the surface there back to it (the construction's own set-in went with its drawn features)
    ke = int(np.argmin(np.abs(zs)))
    xe, ye = row(ke)[0], row(ke)[1](cheek[ke])
    fr = np.cos(th) > 0
    y_eye = float(np.interp(F.C['eye_x'], xe[fr][np.argsort(xe[fr])], ye[fr][np.argsort(xe[fr])]))
    window = win['mode'] == 'window' and 'socket' in terms
    sock = max(0.0, -y_eye) * ('socket' in terms) * (not window)
    R = np.full_like(R0, np.nan)
    dfill = None
    if window:
        # the anime eye region (eye_fill): the smoothest correction that lays the eye's opening on the design's plane
        # and holds the brow and the cheek behind it, in place of the socket; on the right half's front columns, mirrored
        jr = np.nonzero((th >= -1e-9) & (th <= np.pi / 2 + 1e-9))[0]
        jr = jr[np.argsort(th[jr])]
        jl = np.array([int(np.argmin(np.abs(np.angle(np.exp(1j * (th + th[j])))))) for j in jr])   # their mirrors
        Xg = np.full((len(zs), len(jr)), np.nan); Yg = np.full((len(zs), len(jr)), np.nan)
        for k in valid:
            x, shaped = row(k)
            Xg[k], Yg[k] = x[jr], shaped(cheek[k])[jr]
        rows_ok = np.isfinite(Xg).all(1)
        dfill = np.zeros_like(Xg)
        run = np.nonzero(rows_ok)[0]
        dfill[run] = eye_fill(zs[run], Xg[run], Yg[run], F.C['eye_x'], win)
    for k in valid:
        x, shaped = row(k)
        yy = shaped(cheek[k])
        if dfill is not None:
            yy = yy.copy()
            yy[jr] += dfill[k]; yy[jl] += dfill[k]                     # (the midline's 0 either way)
        if sock > 0 and abs(zs[k]) < 4 * SOCKET[1]:
            yy = yy + fr * sock * np.exp(-0.5 * ((np.abs(x) - F.C['eye_x']) / SOCKET[0]) ** 2 - 0.5 * (zs[k] / SOCKET[1]) ** 2)
        tn = np.arctan2(x, -(yy - cy[k])); o = np.argsort(tn)
        R[k] = np.interp(th, tn[o], np.hypot(x, yy - cy[k])[o], period=2 * np.pi)
    # under the chin the front onto the design's drawn skin edge (head_turnaround's profile: the jaw's underside, then
    # the neck), row by row, as a correction on the section's front that fades out by its sides: the back of the neck
    # (under the hair in the design) stays the construction's
    if F.C.get('neck_y') is not None and np.isfinite(F.C['neck_y']).any():
        okn = np.isfinite(F.C['neck_y'])
        target = np.interp(-zs, -F.C['neck_z'][okn], _smooth_rows(F.C['neck_y'], 1)[okn], left=np.nan, right=np.nan)
        below = zs < zc_d
        front_now = np.array([cy[k] - R[k, j0] if np.isfinite(R[k]).all() else np.nan for k in range(len(zs))])
        # first the neck whole, by its offset from the design's neck (its depth is the construction's, under the hair in
        # the design), ramped in over the jaw's underside so the back moves smoothly; then the front alone for the rest
        neck_rows = (zs < zc_d - 0.06) & np.isfinite(target) & np.isfinite(front_now)
        if neck_rows.any():
            # the neck's offset: its front moves by it under the chin; its back, the nape, moves gradually from the ears
            # down, so the back of the head runs on into the neck's back without a ledge
            off = float(np.median((target - front_now)[neck_rows]))
            w_front = _smoothstep((zc_d - zs) / 0.06)
            w_back = _smoothstep((NAPE[0] - zs) / (NAPE[0] - (zc_d - 0.06)))
            for k in np.nonzero(np.isfinite(R).all(1) & (w_back > 1e-4))[0]:
                x, y = np.sin(th) * R[k], cy[k] - np.cos(th) * R[k]
                y = y + off * (w_back[k] * (1 - g_front) + w_front[k] * g_front)
                tn = np.arctan2(x, -(y - cy[k])); o = np.argsort(tn)
                R[k] = np.interp(th, tn[o], np.hypot(x, y - cy[k])[o], period=2 * np.pi)
            front_now = front_now + off * w_front
        d = np.where(below & np.isfinite(target) & np.isfinite(front_now), target - front_now, np.nan)
        last = np.nonzero(np.isfinite(d))[0]
        if len(last):
            d = np.where(below & (np.arange(len(zs)) > last[-1]), d[last[-1]], d)   # under the drawn neck: held
            d = np.nan_to_num(_smooth_rows(d, 0.006 / A.h), nan=0.0) * _smoothstep((zc_d - zs) / 0.01)
            for k in np.nonzero(below & (np.abs(d) > 1e-6) & np.isfinite(R).all(1))[0]:
                x, y = np.sin(th) * R[k], cy[k] - np.cos(th) * R[k]
                y = y + d[k] * g_front
                tn = np.arctan2(x, -(y - cy[k])); o = np.argsort(tn)
                R[k] = np.interp(th, tn[o], np.hypot(x, y - cy[k])[o], period=2 * np.pi)
    ok = np.isfinite(R).all(1) & np.isfinite(cy)
    Rs = R.copy()
    Rs[ok] = gaussian_filter(R[ok], (smooth_z / A.h, smooth_th * Sections.N / (2 * np.pi)), mode=('nearest', 'wrap'))
    rep = {'socket_L': round(sock, 4), 'eye_window': win if window else None, 'align_dy_L': round(dy, 4), 'skull_chin': round(zc_s, 4), 'design_chin': round(zc_d, 4),
           'cheek_range_L': [round(float(np.min(cheek)), 4), round(float(np.max(cheek)), 4)],
           'cheek_fit_noise_L': round(float(np.nanstd(raw_cheek - cheek)), 4) if np.isfinite(raw_cheek).any() else None}
    return Sections(zs, np.where(ok, cy, np.nan), np.where(ok[:, None], Rs, np.nan)), rep


def banding(S, span=np.radians(60), zlo=None, zhi=0.1, scale=0.02):
    """the face's banding: RMS (L) of the radius against itself smoothed over `scale` L of height, across the face's
    angles (|angle| < span) and rows: ridges and grooves running across the face, a few rows wide. The voxel noise is
    finer than `scale` and mostly smoothed already; a smooth face scores a few 1e-4."""
    from scipy.ndimage import gaussian_filter1d
    ok = np.isfinite(S.cy) & np.isfinite(S.r).all(1)
    zlo = S.zs[ok].min() if zlo is None else zlo
    rows = ok & (S.zs >= zlo) & (S.zs <= zhi)
    dz = abs(S.zs[1] - S.zs[0])
    R = S.r[ok]
    low = gaussian_filter1d(R, scale / dz, axis=0, mode='nearest')
    sel = rows[ok]
    d = (R - low)[sel][:, np.abs(S.th) < span]
    return float(np.sqrt(np.mean(d ** 2)))


def banding_rows(S, span=np.radians(60), scale=0.02):
    """the banding per row (RMS over the face's angles) -> (zs, values): where the ridges are."""
    from scipy.ndimage import gaussian_filter1d
    ok = np.isfinite(S.cy) & np.isfinite(S.r).all(1)
    dz = abs(S.zs[1] - S.zs[0])
    R = S.r[ok]
    d = (R - gaussian_filter1d(R, scale / dz, axis=0, mode='nearest'))[:, np.abs(S.th) < span]
    return S.zs[ok], np.sqrt(np.mean(d ** 2, 1))


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
    # the eyes where the build's iris plates sit: on the surface at the eyes' (x, z) (charkit/eyes.py places them there),
    # which is what the QA measures the leads from
    irc = [tuple(p) for p in front_point(S, np.array([ex, -ex]), np.array([0.0, 0.0]))]
    O = sheetqa.measure_ours([(m.V, m.F, np.full(len(m.F), sheetqa.CLASS['skin']))], covers,
                             irc, (0.0, float(S.cy[k0])), 1.0, D['ppl'], D['az_three_quarter'])
    return sheetqa.compare(O, D), O


def outline(S, rgb, eye_x, facing=-1, zs=np.arange(-0.2, -0.505, -0.02)):
    """the head's outline against the design's drawn skin below the face, where the sheet checks stop (the jaw, the
    chin's underside, the neck), front and profile: per row our silhouette's edge against the skin's (the profile's
    back is under the hair in the design; its front only) -> dict(rows [...], front_max_L, profile_max_L, views)."""
    from charkit import bodyqa
    from . import hull
    views, info = hull.views_from_heads(rgb, eye_x, facing, floor=-0.9)
    out = {'rows': [], 'views': {}}
    for vn, az in (('front', 0.0), ('profile', 90.0)):
        v = views[vn]
        cls = bodyqa.classes(rgb, v.mask, v.eye_y, v.ppl)[0]
        ours = []
        for k in range(len(S.zs)):
            if np.isfinite(S.cy[k]) and np.isfinite(S.r[k]).all():
                x, y = S.xy(k)
                u = x * np.cos(np.radians(az)) + y * np.sin(np.radians(az)) + (info['y_e'] if vn == 'profile' else 0.0)
                ours.append((S.zs[k], u.min(), u.max()))
        ours = np.array(ours)
        out['views'][vn] = dict(view=v, ours=ours)
        for z in zs:
            r = int(round(v.eye_y - z * v.ppl))
            skin = np.nonzero((cls[r] == bodyqa.CLASS['skin']) & v.mask[r])[0]
            if not len(skin):
                continue
            k = int(np.argmin(np.abs(ours[:, 0] - z)))
            d0, d1 = (skin.min() - v.axis) / v.ppl, (skin.max() - v.axis) / v.ppl
            e = (ours[k, 1] - d0, ours[k, 2] - d1) if vn == 'front' else (ours[k, 1] - d0, None)
            out['rows'].append(dict(view=vn, z=round(float(z), 3), design=[round(d0, 4), round(d1, 4)],
                                    ours=[round(float(ours[k, 1]), 4), round(float(ours[k, 2]), 4)],
                                    off=[round(float(q), 4) if q is not None else None for q in e]))
    for vn in ('front', 'profile'):
        offs = [abs(q) for r_ in out['rows'] if r_['view'] == vn for q in r_['off'] if q is not None]
        out[vn + '_max_L'] = round(max(offs), 4) if offs else None
    return out


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
    V, A = skull_analytic(spec, log=log), None
    S, rep = assemble(F, V, A, face=face_style(spec))
    covers = hair_covers(spec)
    fair, ang = normal_fairness(S)
    rep['fairness_deg'] = fair
    ol = outline(S, refcheck._load(fs['image']), spec.get('eyes', {}).get('x', 0.168), fs.get('facing', -1))
    rep['outline'] = {k: v for k, v in ol.items() if k != 'views'}
    checks, O = grade(S, spec, C['design'], covers)
    m = sections_mesh(S)
    Cg, ctr = cylinder_cage(S, C)
    from . import headmesh
    q = quality(Cg.V, Cg.F, Cg.origins)
    rep['cage'] = dict(headmesh.check(Cg), **{k: v for k, v in q.items() if k != 'flipped_idx'},
                       loops={k: [len(r) for r in v] for k, v in Cg.loops.items()})
    np.savez_compressed(os.path.join(out, 'head_cage.npz'), V=Cg.V, F=Cg.F, group=Cg.group, groups=np.array(Cg.groups),
                        origins=Cg.origins, **{'loop_%s_%d' % (k, i): np.array(r) for k, v in Cg.loops.items()
                                               for i, r in enumerate(v)})
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
    rep['page'] = _page(rep, S, F, V, A, m, O, C, covers, out, Cg, ang, ol, refcheck._load(fs['image']))
    log('headfit: %s (%.0fs)' % (rep['page'], time.time() - t0))
    return rep


def _page(rep, S, F, V, A, m, O, C, covers, out, Cg=None, ang=None, ol=None, sheet=None):
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
    L.append('</table>')
    if ang is not None:
        fz = rep['fairness_deg']
        L.append('<h2>Fairness: what shading sees</h2><p class="note">The angle between the surface\'s normal and its '
                 'normals smoothed by a local quadratic fit over 0.04 L (normal_fairness): a fair surface stays within a '
                 'degree or so; a lump, crease, ridge or grain shows as a band or streak. The face region holds the nose '
                 'and lips (real, sharp); face_sides leaves them out. The map is the (angle, height) chart, the front in '
                 'the middle, white 0 to red 6 degrees.</p><table><tr><th>region</th><th>RMS, deg</th><th>95th pct</th>'
                 '<th>max</th></tr>')
        for k, v in fz.items():
            L.append('<tr><td>%s</td><td class="%s">%.2f</td><td>%.1f</td><td>%.1f</td></tr>' % (
                k, 'PASS' if v['rms_deg'] <= 1.0 else 'WARN' if v['rms_deg'] <= 2.5 else 'FAIL', v['rms_deg'], v['p95_deg'],
                v['max_deg']))
        t = np.clip(ang / 6.0, 0, 1)
        im = np.stack([np.ones_like(t), 1 - t, 1 - t], -1)
        L.append('</table><div class="row"><div class="tile"><img src="%s" height="360" style="image-rendering:pixelated">'
                 'angle map</div></div>' % save(np.repeat(np.repeat(im, 2, 0), 2, 1), 'fairness.png'))
    if ol is not None and sheet is not None:
        from PIL import ImageDraw
        L.append('<h2>Below the face: the jaw, the chin\'s underside, the neck</h2><p class="note">Where the sheet checks '
                 'stop. Our silhouette (red) over head_turnaround\'s drawing; per row, our edge against the drawn skin\'s '
                 '(L, + further out or back). The profile\'s back is under the hair in the design: its front only. The '
                 'design\'s neck flares into the shoulders below -0.5 L: the body\'s. Worst: front %.4f L, profile %.4f L.'
                 '</p><div class="row">' % (ol['front_max_L'] or 0, ol['profile_max_L'] or 0))
        for vn in ('front', 'profile'):
            v, ours = ol['views'][vn]['view'], ol['views'][vn]['ours']
            r0, r1 = int(v.eye_y + 0.05 * v.ppl), int(v.eye_y + 0.7 * v.ppl)
            c0, c1 = int(v.axis - 0.55 * v.ppl), int(v.axis + 0.55 * v.ppl)
            im = Image.fromarray((np.clip(sheet[r0:r1, c0:c1], 0, 1) * 255).astype(np.uint8)).convert('RGB')
            d = ImageDraw.Draw(im)
            sel = (ours[:, 0] <= -0.05) & (ours[:, 0] >= -0.7)
            for side in (1, 2):
                d.line([(v.axis + ours[i, side] * v.ppl - c0, v.eye_y - ours[i, 0] * v.ppl - r0) for i in np.nonzero(sel)[0]],
                       fill=(230, 20, 20), width=3)
            L.append('<div class="tile"><img src="%s" height="360">%s</div>' % (save(np.asarray(im), 'outline_%s.png' % vn), vn))
        L.append('</div><table><tr><th>view</th><th>z, L</th><th>design</th><th>ours</th><th>off</th></tr>')
        for r_ in ol['rows']:
            L.append('<tr><td>%s</td><td>%.2f</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
                r_['view'], r_['z'], r_['design'], r_['ours'], r_['off']))
        L.append('</table>')
    L.append('<h2>The QA\'s face regions: grey both, red ours only, blue the design only</h2>')
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
    S0 = V if isinstance(V, Sections) else skull_sections(V, A)
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
    if Cg is not None:
        from charkit import subdiv
        cq = rep['cage']
        L.append('<h2>The authored cage on it (charkit.geom.headmesh.cylinder)</h2><p class="note">%d vertices, %d quads, '
                 'manifold (%d non-manifold, %d mis-wound edges), open only at the neck (%d edges, Euler %d); fitted with '
                 '%d flipped faces and %d folded corners, worst corner sine %.3f. Loops: %s. Eyes blue, mouth red, crown '
                 'violet; the second row is its Catmull-Clark subdivision (level 2), as the build draws it.</p><div class="row">' % (
                     cq['verts'], cq['quads'], cq['nonmanifold_edges'], cq['misoriented_edges'], cq['boundary_edges'],
                     cq['euler'], cq['flipped'], cq['folded_corners'], cq['corner_min'],
                     html.escape(', '.join('%s %s' % (k, v) for k, v in cq['loops'].items()))))
        wire = cage_wire(Cg)
        frc = raster.Frame.around([wire[0][0]], res=520, aspect=0.85)
        for az in (0, 35, 90, 180):
            L.append('<div class="tile"><img src="%s" height="380">%d deg</div>' % (
                save(raster.render(wire, az, frc, outline=False), 'cage_%03d.png' % az), az))
        L.append('</div><div class="row">')
        V1, Q, _ = subdiv.catmull_clark(Cg.V, [list(f) for f in Cg.F], levels=2)
        ms = Mesh(V1, np.concatenate([Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]]))
        for az in (0, 35, 90):
            L.append('<div class="tile"><img src="%s" height="380">%d deg, subdivided</div>' % (
                save(raster.render([(ms, dict(color=(0.86, 0.8, 0.76), shade='lambert'))], az, frc), 'cage_sub_%03d.png' % az), az))
        L.append('</div>')
    p = os.path.join(out, 'index.html')
    open(p, 'w').write('\n'.join(L))
    return p


GROUP_COLOURS = {'face': (0.9, 0.84, 0.78), 'skull': (0.8, 0.8, 0.84), 'crown': (0.7, 0.74, 0.86), 'neck': (0.85, 0.8, 0.7),
                 'eye': (0.35, 0.55, 0.95), 'eye_cap': (0.2, 0.3, 0.7), 'mouth': (0.95, 0.4, 0.4), 'mouth_cap': (0.6, 0.2, 0.2)}


def cage_wire(Cg, shrink=0.14):
    """the cage drawn to show its quads: each quad on its own vertices, shrunk toward its centre and coloured by its
    group (eyes blue, mouth red, crown violet), over a dark copy set a little inside -> [(Mesh, render opts)]."""
    from .mesh import Mesh
    grp = np.array(Cg.groups)[Cg.group]
    P = Cg.V[Cg.F]
    c = P.mean(1, keepdims=True)
    Q = (c + (P - c) * (1 - shrink)).reshape(-1, 3)
    col = []
    for g in grp:
        key = g if g in GROUP_COLOURS else ('eye_cap' if g.startswith('eye') and g.endswith('cap') else 'eye' if g.startswith('eye')
                                            else 'mouth_cap' if g.startswith('mouth') and g.endswith('cap') else 'mouth'
                                            if g.startswith('mouth') else 'face')
        col.append(GROUP_COLOURS[key])
    col = np.repeat(np.array(col), 4, 0)
    n = np.arange(len(Cg.F) * 4).reshape(-1, 4)
    quads = Mesh(Q, np.concatenate([n[:, [0, 1, 2]], n[:, [0, 2, 3]]]))
    O = getattr(Cg, 'origins', None)
    Vin = Cg.V + ((O - Cg.V) * 0.01 if O is not None else 0)
    back = Mesh(Vin, np.concatenate([Cg.F[:, [0, 1, 2]], Cg.F[:, [0, 2, 3]]]))
    return [(quads, dict(color=col, shade='lambert')), (back, dict(color=(0.15, 0.15, 0.18), shade='flat'))]


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


# ------------------------------------------------------------------------------------------------------------ the cage


def head_cage(S, C, cell=0.03, eye_w=0.21, eye_h=0.13, mouth_w=0.12, rings=(3, 2)):
    """the authored cage (charkit.geom.headmesh) laid out for this head: its box round the head's extent, the eye blocks
    on the design's eyes, the mouth's under the nose, the neck's under the jaw -> Cage (in the box, before fitting)."""
    from . import headmesh as hm
    ok = np.isfinite(S.cy) & np.isfinite(S.r).all(1)
    zs = S.zs[ok]
    ex = C['eye_x']
    mz = C['nose_z'] - 0.11
    bw, bh = 0.27, 0.18                                             # the eye block, L
    mw, mh = 0.18, 0.09
    xe = [ex - bw / 2, ex + bw / 2, -ex - bw / 2, -ex + bw / 2]
    X = hm.lines(-0.40, 0.40, cell, must=xe + [-mw / 2, mw / 2, -0.12, 0.12])
    front_y = float(np.nanmin(S.cy[ok] - S.r[ok][:, int(np.argmin(np.abs(S.th)))]))
    back_y = float(np.nanmax(S.cy[ok] + S.r[ok][:, int(np.argmin(np.abs(np.abs(S.th) - np.pi)))]))
    Y = hm.lines(front_y - 0.05, back_y + 0.02, cell * 1.5, must=[0.0, 0.3])
    chin = C['chin']
    Z = hm.lines(chin, float(zs.max()), cell, must=[-bh / 2, bh / 2, mz - mh / 2, mz + mh / 2])

    def almond(cx, cz, w, h, n=64):
        t = np.linspace(0, 2 * np.pi, n, endpoint=False)
        return np.stack([cx + w / 2 * np.cos(t), cz + h / 2 * np.sin(t) * (1 + 0.15 * np.cos(t))], 1)
    snap = lambda v, lines: float(lines[np.argmin(np.abs(lines - v))])
    feats = [dict(name='eye_L', box=(snap(ex - bw / 2, X), snap(ex + bw / 2, X), snap(-bh / 2, Z), snap(bh / 2, Z)),
                  outline=almond(ex, 0.0, eye_w, eye_h), rings=rings[0]),
             dict(name='eye_R', box=(snap(-ex - bw / 2, X), snap(-ex + bw / 2, X), snap(-bh / 2, Z), snap(bh / 2, Z)),
                  outline=almond(-ex, 0.0, eye_w, eye_h), rings=rings[0]),
             dict(name='mouth', box=(snap(-mw / 2, X), snap(mw / 2, X), snap(mz - mh / 2, Z), snap(mz + mh / 2, Z)),
                  outline=almond(0.0, mz, mouth_w, 0.012), rings=rings[1])]
    neck = dict(box=(snap(-0.12, X), snap(0.12, X), snap(0.0, Y), snap(0.3, Y)),
                rings=[(0.05, 1.0), (0.12, 1.0), (0.2, 1.0)], radius=(0.12, 0.14))
    return hm.cage(X, Y, Z, feats, neck=neck)


def fit_cage(Cg, S, C, relax=8):
    """the cage onto the head by rays from its axis (origins (0, the row's centre, z*), z* the vertex's height held to
    the head's middle band: rays go out sideways, up through the crown, down through the jaw's underside, sideways round
    the neck at its own height). The front face's vertices inside the face take the direction that meets the surface at
    their own front-view (x, z), so the eyes' and mouth's loops land where the design draws them; every other direction
    is interpolated harmonically between those and the cage's own, so the mapping doesn't fold. Then `relax` rounds of
    smoothing the free vertices along the surface. -> (V fitted, fixed mask)."""
    V0 = Cg.V
    grp = np.array(Cg.groups)[Cg.group]
    okr = np.isfinite(S.cy)
    zlo, zhi = C['chin'] + 0.15, 0.25
    neck = set(np.concatenate(Cg.loops['neck'][1:]).tolist()) if 'neck' in Cg.loops else set()
    isneck = np.array([i in neck for i in range(len(V0))])
    nb, off = _neighbours(Cg.F, len(V0))
    if 'neck' in Cg.loops:
        isneck |= np.isin(np.arange(len(V0)), Cg.loops['neck'][0])
    # the rays' origins on the head's axis: at the vertex's own height round the neck, at its height held to the middle
    # band elsewhere, and harmonic between the two over the jaw's underside, so the jaw's rays hand over to the neck's
    zc = np.clip(V0[:, 2], zlo, zhi)
    zc[isneck] = V0[isneck, 2]
    under = np.zeros(len(V0), bool)                       # the box's bottom face, the jaw's underside
    under[Cg.F[grp == 'jaw'].ravel()] = True
    pin = isneck | ~under
    zc = _harmonic(zc[:, None], pin, nb, off)[:, 0]
    O = np.stack([np.zeros(len(V0)), np.interp(-zc, -S.zs[okr], S.cy[okr]), zc], 1)
    D = V0 - O
    D[isneck, 2] = 0.0
    D /= np.maximum(np.linalg.norm(D, axis=1, keepdims=True), 1e-12)
    front = np.zeros(len(V0), bool)
    feature = np.zeros(len(V0), bool)
    for f, g in zip(Cg.F, grp):
        if g == 'face' or g.startswith(('eye_', 'mouth')):
            front[f] = True
        if g.startswith(('eye_', 'mouth')):
            feature[f] = True
    wf = np.interp(-V0[:, 2], -C['z'], np.nan_to_num(C['w'], nan=0.0), left=0.0, right=0.0)
    inner = front & ((np.abs(V0[:, 0]) <= 0.85 * wf) | feature)
    P = front_point(S, V0[inner, 0], V0[inner, 2])
    ok = np.isfinite(P).all(1)
    idx = np.nonzero(inner)[0][ok]
    Dt = P[ok] - O[idx]
    D[idx] = Dt / np.maximum(np.linalg.norm(Dt, axis=1, keepdims=True), 1e-12)
    fixed = np.zeros(len(V0), bool)
    fixed[idx] = True
    # the free directions: harmonic between the fixed ones and a light pull back to the cage's own
    D = _harmonic(D, fixed | ~front & ~_near(front, nb, off, 3), nb, off)
    D /= np.maximum(np.linalg.norm(D, axis=1, keepdims=True), 1e-12)
    V = project(S, O, D)
    V[idx] = P[ok]
    for _ in range(relax):                                 # even the quads out, back onto the surface along the rays
        L = _harmonic(V, fixed, nb, off, iters=1)
        Dn = L - O
        Dn[isneck, 2] = 0.0
        V = np.where(fixed[:, None], V, project(S, O, Dn))
    return V, fixed


# ------------------------------------------------------------------------------------------------------------ fairness
REGIONS = {                       # (z range, |angle| range in degrees): where a lump shows
    'face': ((-0.36, 0.1), (0, 35)), 'face_sides': ((-0.3, 0.1), (12, 35)), 'cheeks': ((-0.3, 0.05), (35, 80)),
    'forehead': ((0.1, 0.35), (0, 60)),
    'skull': ((0.1, 0.7), (60, 180)), 'jaw_neck': ((-0.6, -0.3), (0, 180)),
}


def fairness(S, scale=0.04, arc=0.04):
    """the surface's fairness: its radius against a local quadratic fit (Savitzky-Golay, `scale` L of height by about
    `arc` L of arc at the face's radius), which a smooth surface matches exactly whatever its curvature; what's left
    is lumps, dents, ridges and grain finer than the window. RMS and worst per region (L) -> (dict, the residual map
    (valid rows, angles), valid rows)."""
    from scipy.signal import savgol_filter
    ok = np.isfinite(S.cy) & np.isfinite(S.r).all(1)
    R = S.r[ok]
    dz = abs(S.zs[1] - S.zs[0])
    wz = max(5, int(round(scale / dz)) | 1)
    wt = max(5, int(round(arc / 0.3 / (2 * np.pi / R.shape[1]))) | 1)
    fit = savgol_filter(savgol_filter(R, wz, 2, axis=0, mode='nearest'), wt, 2, axis=1, mode='wrap')
    res = R - fit
    zs = S.zs[ok]
    ang = np.degrees(np.abs(S.th))
    rep = {}
    for name, ((z0, z1), (a0, a1)) in REGIONS.items():
        sel = res[(zs >= z0) & (zs <= z1)][:, (ang >= a0) & (ang <= a1)]
        if sel.size:
            rep[name] = {'rms_L': round(float(np.sqrt(np.mean(sel ** 2))), 5), 'max_L': round(float(np.abs(sel).max()), 4)}
    return rep, res, ok


def fairness_image(S, res, ok, span=1.2e-3):
    """the residual as a heat map on the (angle, height) chart, the front in the middle: blue dents, red lumps, white
    within the span's tenth -> float image (rows, angles, 3)."""
    t = np.clip(res / span, -1, 1)
    img = np.ones(t.shape + (3,))
    img[..., 0] = np.where(t < 0, 1 + t, 1.0); img[..., 1] = 1 - np.abs(t); img[..., 2] = np.where(t > 0, 1 - t, 1.0)
    return img


def normal_fairness(S, scale=0.04):
    """what shading sees: the angle (degrees) between the surface's normal and its normal field smoothed by a local
    quadratic fit over `scale` L of height and of arc. A fair surface stays within a degree or so; a crease, a ridge,
    grain or a lump shows as a band or streak of several. -> (per region {rms_deg, p95_deg, max_deg}, the angle map
    (valid rows, angles))."""
    from scipy.signal import savgol_filter
    ok = np.isfinite(S.cy) & np.isfinite(S.r).all(1)
    zs, R, cy = S.zs[ok], S.r[ok], S.cy[ok]
    X = np.sin(S.th)[None, :] * R
    Y = cy[:, None] - np.cos(S.th)[None, :] * R
    Z = np.repeat(zs[:, None], R.shape[1], 1)
    P = np.stack([X, Y, Z], -1)
    du = np.roll(P, -1, 1) - np.roll(P, 1, 1)                        # along the angle
    dv = np.zeros_like(P); dv[1:-1] = P[:-2] - P[2:]; dv[0] = P[0] - P[1]; dv[-1] = P[-2] - P[-1]   # up the rows
    N = np.cross(du, dv)
    N /= np.maximum(np.linalg.norm(N, axis=-1, keepdims=True), 1e-12)
    out = P - np.stack([np.zeros_like(cy), cy, zs], 1)[:, None, :]
    N *= np.sign(np.einsum('ijk,ijk->ij', N, out))[..., None]           # outward
    dz = abs(zs[1] - zs[0])
    wz = max(5, int(round(scale / dz)) | 1)
    wt = max(5, int(round(scale / 0.3 / (2 * np.pi / R.shape[1]))) | 1)
    Ns = savgol_filter(savgol_filter(N, wz, 2, axis=0, mode='nearest'), wt, 2, axis=1, mode='wrap')
    Ns /= np.maximum(np.linalg.norm(Ns, axis=-1, keepdims=True), 1e-12)
    ang = np.degrees(np.arccos(np.clip(np.einsum('ijk,ijk->ij', N, Ns), -1, 1)))
    deg = np.degrees(np.abs(S.th))
    rep = {}
    for name, ((z0, z1), (a0, a1)) in REGIONS.items():
        sel = ang[(zs >= z0) & (zs <= z1)][:, (deg >= a0) & (deg <= a1)]
        if sel.size:
            rep[name] = {'rms_deg': round(float(np.sqrt(np.mean(sel ** 2))), 2),
                         'p95_deg': round(float(np.percentile(sel, 95)), 2), 'max_deg': round(float(sel.max()), 1)}
    return rep, ang
