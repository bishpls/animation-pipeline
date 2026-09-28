"""Measurement on a geometry bundle (docs/CHARKIT.md §4): the QA's body, garment and hair measures as functions of plain
data, so any geometry source can be measured the same way: the fast evaluator (charkit.bodyeval) now, a Blender export
later.

A bundle:
    dict(objects=[dict(name, group, V (n, 3) world, F (m, 3) triangles, label (m,) charkit.bodyqa.CLASS per triangle,
                       lit (m, 3), shade (m, 3) the sRGB tones its material renders unlit)],
         landmarks=dict(L, centre (3,), chin, waist, knee (world z), iris (2, 3) the iris plates' centres),
         target=(V, F) or None)                               # the generated shape aligned by its eyes

    ctx = bodymeasure.Sheet(spec)                            # the model sheet measured once (charkit.bodyqa's views)
    checks = bodymeasure.sheet_body(bundle, ctx)             # the qa3d body_* checks, numpy
    checks = bodymeasure.sheet_palette(bundle, ctx)          # the qa3d palette_* checks
    depth, label = bodymeasure.zsplat(meshes, az, origin, L, pix, win)    # faceqa.zbuffer, compiled

zsplat is faceqa.zbuffer's point-splat z-buffer (the same barycentric samples, pixels and nearest-wins rule) in numba,
so these checks read what the in-Blender QA reads, at a fraction of the time.
"""
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    import numba as nb
except ImportError:                                     # Blender's Python: faceqa's numpy version instead
    nb = None


# ------------------------------------------------------------------------------------------------------------ z-buffer
if nb is not None:
    @nb.njit(cache=True)
    def _splat(U, Z, D, T, lab, W, H, pix, wx, top, bottom, depth, label):
        for t in range(T.shape[0]):
            a, b, c = T[t, 0], T[t, 1], T[t, 2]
            u0, u1, u2 = U[a], U[b], U[c]
            z0, z1, z2 = Z[a], Z[b], Z[c]
            if max(u0, u1, u2) <= -wx or min(u0, u1, u2) >= wx or max(z0, z1, z2) <= bottom or min(z0, z1, z2) >= top:
                continue
            d0, d1, d2 = D[a], D[b], D[c]
            e = max(np.hypot(u0 - u1, z0 - z1), np.hypot(u1 - u2, z1 - z2), np.hypot(u2 - u0, z2 - z0))
            k = int(np.ceil(e / (0.6 * pix)))
            k = min(64, max(1, k))
            for i in range(k + 1):
                for j in range(k + 1 - i):
                    b1 = i / k
                    b2 = j / k
                    b0 = 1 - b1 - b2
                    su = u0 * b0 + u1 * b1 + u2 * b2
                    sz = z0 * b0 + z1 * b1 + z2 * b2
                    sd = d0 * b0 + d1 * b1 + d2 * b2
                    col = int(np.floor((su + wx) / pix))
                    row = int(np.floor((top - sz) / pix))
                    if 0 <= col < W and 0 <= row < H and sd < depth[row, col]:
                        depth[row, col] = sd
                        label[row, col] = lab[t]


def zsplat(meshes, az, origin, L, pix, win):
    """faceqa.zbuffer (same arguments and result: meshes [(V, tris, tri_label)] -> (depth, label), label -1 where
    nothing), compiled; where numba is missing, faceqa.zbuffer itself. Ties in depth may break the other way."""
    from . import faceqa
    if nb is None:
        return faceqa.zbuffer(meshes, az, origin, L, pix, win)
    ox, oz = origin
    W = int(round(2 * win['x'] / pix)); H = int(round((win['top'] - win['bottom']) / pix))
    depth = np.full((H, W), np.inf); label = np.full((H, W), -1, np.int64)
    for V, T, lab in meshes:
        if len(T) == 0:
            continue
        u, z, d = faceqa.view(np.asarray(V, float), az)
        _splat(np.ascontiguousarray((u - ox) / L), np.ascontiguousarray((z - oz) / L), np.ascontiguousarray(d),
               np.ascontiguousarray(T, np.int64), np.ascontiguousarray(np.asarray(lab, np.int64)), W, H, float(pix),
               float(win['x']), float(win['top']), float(win['bottom']), depth, label)
    return depth, label


# ------------------------------------------------------------------------------------------------------------ the sheet
def _png(path):
    """an image as floats 0..1 (row 0 = top), RGBA, rounded as Blender's float32 pixels hold it."""
    from PIL import Image
    return (np.asarray(Image.open(path).convert('RGBA'), np.float32) / np.float32(255)).astype(float)


class Sheet:
    """the design's model sheet measured once, as qa3d._sheet_context and qa3d.sheet_body read it: its scale (the front
    figure's height against the rig's), the figures, the three-quarter's angle, the design's views as class images
    (bodyqa.design_views) and its palette (paletteqa.extract_views). spec: the resolved spec (bodyeval.resolve)."""

    def __init__(self, spec):
        from . import bodyqa, eyes as eyelib, paletteqa, refs, sheetqa
        ref = spec.get('ref') if isinstance(spec.get('ref'), dict) else {}
        sh = ref.get('sheet')
        if not sh or not ref.get('rig'):
            raise ValueError('no spec.ref.sheet / rig')
        p = lambda x: x if os.path.isabs(x) else os.path.join(ROOT, x)
        self.rgb = _png(p(sh['image']))[..., :3]
        rig_alpha = _png(os.path.join(p(ref['rig']), 'base.png'))[..., 3]
        R = refs.measure(p(ref['rig']), (spec.get('eyes') or {}).get('x', 0.168))
        self.eye_x = eyelib._knobs(spec.get('eyes'))['x']
        self.ppl = sheetqa.sheet_ppl(self.rgb, sh['front_figure'], rig_alpha, R['ppl'])
        self.D = sheetqa.detect_figures(self.rgb, ppl=self.ppl, eye_x=self.eye_x, facing=sh.get('facing'))
        fe = self.D['figures'].get('front', {}).get('eyes') or []
        self.ppl_eyes = abs(fe[1][0] - fe[0][0]) / (2 * self.eye_x) if len(fe) == 2 else None
        te = self.D['figures'].get('three_quarter', {}).get('eyes') or []
        self.az3 = round(float(np.degrees(np.arccos(np.clip(abs(te[1][0] - te[0][0]) / (2 * self.eye_x * self.ppl), 0, 1))))
                         if len(te) == 2 else 35.0, 1)
        self.design = bodyqa.design_views(self.rgb, self.D, self.ppl)
        self.palette = paletteqa.extract_views(self.design)
        self.caution = None
        if self.ppl_eyes:
            d = self.ppl_eyes / self.ppl - 1
            if abs(d) > 0.03:
                self.caution = 'scale: the sheet\'s eye spacing reads %+.1f%% against its figure height (used); lengths far ' \
                               'from the eyes carry it (%.2f L at the feet)' % (100 * d, abs(d) * 5.2)


def views(bundle, sheet, which=None):
    """our bundle z-buffered on the design's grid per view (bodyqa.zbuffer_views, with zsplat): {view: (depth, label)}."""
    from . import bodyqa
    lm = bundle['landmarks']
    meshes = [(o['V'], o['F'][o['label'] >= 0], o['label'][o['label'] >= 0]) for o in bundle['objects']]
    az = bodyqa.azimuths(sheet.az3)
    which = which or [v for v in bodyqa.AZ if v in sheet.design]
    out = {}
    for v in which:
        org = bodyqa.origin(v, az[v], np.asarray(lm['iris'], float), lm['centre'])
        out[v] = zsplat(meshes, az[v], org, lm['L'], 1.0 / sheet.ppl, bodyqa.WIN)
    return out


def sheet_body(bundle, sheet, labels=None):
    """qa3d.sheet_body's checks on a bundle (bodyqa.evaluate: per view the silhouette, hair, skin and outfit IoUs, the feet,
    top, hair length and width, skirt width and hem, sleeves, leg, boot). -> (table, checks, views)."""
    from . import bodyqa
    labels = labels or views(bundle, sheet)
    table, C, vs = bodyqa.evaluate(labels, sheet.design, sheet.caution)
    return table, C, vs


def colours(bundle):
    """the per-class colours paletteqa.ours reads: {class: [(lit, shade, area)]} over the bundle's triangles."""
    cols = {}
    for o in bundle['objects']:
        V, T, lab = o['V'], o['F'], o['label']
        area = 0.5 * np.linalg.norm(np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]]), axis=1)
        for c in np.unique(lab):
            if c < 0:
                continue
            s = lab == c
            cols.setdefault(int(c), []).extend(zip(map(tuple, o['lit'][s]), map(tuple, o['shade'][s]), area[s]))
    return cols


def sheet_palette(bundle, sheet):
    """qa3d.sheet_palette's checks on a bundle: the design's tones per class against our materials'. -> (table, checks)."""
    from . import paletteqa
    O = paletteqa.ours(colours(bundle))
    return {'ours': O, 'design': sheet.palette}, paletteqa.compare(O, sheet.palette)


# ------------------------------------------------------------------------------------------------ silhouettes (qa3d shape)
AZ = (0, 45, 90, 135, 180, 270)                  # qa3d's azimuths
RES = (360, 560)                                 # qa3d's QA camera


def frame(bundle):
    """qa3d's QA camera: orthographic through the z axis, framing the objects' z range * 1.08 (qa3d reads the base
    meshes: pass the unsubdivided bundle)."""
    from .geom.raster import Frame
    zs = np.concatenate([o['V'][:, 2] for o in bundle['objects'] if len(o['V'])])
    zmin, zmax = float(zs.min()), float(zs.max())
    return Frame((0.0, 0.0, (zmin + zmax) / 2), (zmax - zmin) * 1.08, RES)


def label_image(bundle, az, fr, groups=None):
    """the nearest object per pixel from azimuth az (charkit.geom.raster, pixel centres as Blender's renders sample):
    -> (object index per pixel, -1 where nothing; depth)."""
    from .geom.mesh import Mesh
    from .geom.raster import rasterize
    Vs, Fs, lab, off = [], [], [], 0
    for i, o in enumerate(bundle['objects']):
        if groups and o['group'] not in groups or not len(o['F']):
            continue
        Vs.append(o['V']); Fs.append(o['F'] + off); lab.append(np.full(len(o['F']), i)); off += len(o['V'])
    zb, fb, _ = rasterize(Mesh(np.vstack(Vs), np.vstack(Fs)), az, fr)
    lab = np.concatenate(lab)
    return np.where(fb >= 0, lab[np.maximum(fb, 0)], -1), zb


def target_masks(target, fr, azs=AZ):
    """the aligned generated shape's silhouettes per azimuth."""
    from .geom.mesh import Mesh
    from .geom.raster import silhouette
    m = Mesh(np.asarray(target[0], float), np.asarray(target[1]))
    return {az: silhouette(m, az, fr) for az in azs}


def bands(lm):
    """qa3d's height bands (world z): hair above the chin, torso to the waist, skirt to the knee, legs."""
    return {'hair': (lm['chin'], 99.0), 'torso': (lm['waist'], lm['chin']), 'skirt': (lm['knee'], lm['waist']),
            'legs': (-99.0, lm['knee'])}


def shape(bundle, fr, masks=None, ref=None, azs=AZ, labels=False):
    """qa3d's silhouette checks: IoU against the generated shape's silhouettes (masks, per azimuth; target_masks) per
    view and band, their means (shape_iou, shape_iou_<band>), and the front silhouette against the reference image's
    mask (ref), both cropped to their boxes (ref_iou). -> dict(views, checks[, labels, target, frame, bands])."""
    B = bands(bundle['landmarks'])
    H = fr.res[1]
    row = lambda z: int(round((0.5 - (z - fr.centre[2]) / fr.scale) * H))
    out = {'views': {}, 'checks': {}}
    labs = {}
    for az in azs:
        lab, _ = label_image(bundle, az, fr)
        labs[az] = lab
        if masks is None:
            continue
        o, g = lab >= 0, masks[az]
        d = {'iou': round(iou(o, g), 3)}
        for bn, (z0, z1) in B.items():
            r0, r1 = max(0, row(z1)), min(H, row(z0))
            if r1 > r0:
                d['iou_' + bn] = round(iou(o[r0:r1], g[r0:r1]), 3)
        out['views'][az] = d
    if masks is not None:
        out['checks']['shape_iou'] = round(float(np.mean([out['views'][a]['iou'] for a in azs])), 3)
        for bn in B:
            out['checks']['shape_iou_' + bn] = round(float(np.mean([out['views'][a].get('iou_' + bn, 0) for a in azs])), 3)
    if ref is not None and 0 in labs:
        out['checks']['ref_iou'] = round(iou(bbox_norm(labs[0] >= 0), bbox_norm(ref)), 3)
    if labels:
        out['labels'], out['target'], out['frame'], out['bands'] = labs, masks, fr, B
    return out


def iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 1.0


def bbox_norm(mask, size=(200, 320)):
    """qa3d._bbox_norm: a mask cropped to its bounding box and resampled (nearest) to size."""
    ys, xs = np.nonzero(mask)
    if len(ys) == 0:
        return np.zeros(size[::-1], bool)
    m = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    H, W = size[1], size[0]
    yi = (np.arange(H) * m.shape[0] / H).astype(int); xi = (np.arange(W) * m.shape[1] / W).astype(int)
    return m[yi][:, xi]


# ---------------------------------------------------------------------------------------- the silhouette measurements
MEASURES = {
    'iou': 'shape IoU against the generated shape, the mean over the six QA azimuths (qa3d shape_iou)',
    'iou_hair': 'the same above the chin', 'iou_torso': 'chin to waist', 'iou_skirt': 'waist to knee', 'iou_legs': 'below the knee',
    'ref_iou': 'front silhouette against the reference image, both cropped to their boxes (qa3d ref_iou)',
    'top': 'the silhouette top (hair, buns) above the target\'s, L', 'bottom': 'the feet\'s bottom below the target\'s, L',
    'arm_angle': 'the arms\' outer line from vertical (front, shoulder to waist) minus the target\'s, degrees',
    'leg_angle': 'each leg\'s centre line from vertical (front, below the knee) minus the target\'s, degrees',
    'leg_gap': 'the gap between the legs (front, below the knee) minus the target\'s, L',
}
for _v in ('front', 'side'):
    for _b in ('hair', 'torso', 'skirt', 'legs'):
        MEASURES['%s_%s_fill' % (_v, _b)] = 'filled width per row in the %s band, %s view, minus the target\'s, L' % (_b, _v)
        MEASURES['%s_%s_span' % (_v, _b)] = 'outer extent per row in the %s band, %s view, minus the target\'s, L' % (_b, _v)


def _rows_z(fr):
    H = fr.res[1]
    return fr.centre[2] + (0.5 - (np.arange(H) + 0.5) / H) * fr.scale


def _profile(m):
    """per row: filled count, leftmost and rightmost column (NaN where empty)."""
    cnt = m.sum(1).astype(float)
    has = cnt > 0
    lo = np.where(has, np.argmax(m, 1), np.nan)
    hi = np.where(has, m.shape[1] - 1 - np.argmax(m[:, ::-1], 1), np.nan)
    return cnt, lo, hi


def _line_angle(z, x):
    """the angle from vertical (degrees) of a least-squares line x(z)."""
    ok = np.isfinite(x)
    if ok.sum() < 4:
        return np.nan
    k = np.polyfit(z[ok], x[ok], 1)[0]
    return float(np.degrees(np.arctan(k)))


def pose_measures(m, fr, lm):
    """the arms' and legs' lines in a front silhouette: arm_angle (outer contour, shoulder to waist, both sides' mean),
    leg_angle (each leg's centre line below the knee), leg_gap (the empty run between the legs there, L)."""
    z = _rows_z(fr)
    pix = fr.scale / fr.res[1]
    L = lm['L']
    W = m.shape[1]; mid = W // 2
    _, lo, hi = _profile(m)
    arm = (z < lm['chin'] - 0.45 * L) & (z > lm['waist'])
    a_r = _line_angle(z[arm], (hi[arm] - mid) * pix)
    a_l = _line_angle(z[arm], (mid - lo[arm]) * pix)
    legs = (z < lm['knee'] - 0.2 * L) & (z > lm['knee'] - 1.2 * L)
    cols = np.arange(W)
    left, right = m[:, :mid], m[:, mid:]
    with np.errstate(invalid='ignore'):
        cl = (left * cols[:mid]).sum(1) / left.sum(1)
        cr = (right * cols[mid:]).sum(1) / right.sum(1)
    l_r = _line_angle(z[legs], (cr[legs] - mid) * pix)
    l_l = _line_angle(z[legs], (mid - cl[legs]) * pix)
    gap = []
    for r in np.nonzero(legs)[0]:
        row = m[r]
        if row[:mid].any() and row[mid:].any():
            a_ = mid - 1 - np.argmax(row[:mid][::-1])          # the left leg's inner edge
            b_ = mid + np.argmax(row[mid:])                     # the right leg's inner edge
            gap.append((b_ - a_ - 1) * pix / L)
    return dict(arm_angle=-np.nanmean([a_r, a_l]), leg_angle=-np.nanmean([l_r, l_l]),
                leg_gap=float(np.mean(gap)) if gap else np.nan)


def measures(Q, lm):
    """the silhouette measurements (MEASURES) from a shape(..., labels=True) result and the landmarks: the QA's IoUs, and
    ours minus the target's for the band profiles (front and side), the extents and the pose lines."""
    fr, B = Q['frame'], Q['bands']
    L = lm['L']
    pix = fr.scale / fr.res[1]
    z = _rows_z(fr)
    out = {k.replace('shape_', ''): v for k, v in Q['checks'].items()}
    T = Q['target']
    if T is None:
        return out
    for view, az in (('front', 0), ('side', 90)):
        o, g = Q['labels'][az] >= 0, T[az]
        (co, lo_o, hi_o), (cg, lo_g, hi_g) = _profile(o), _profile(g)
        for b, (z0, z1) in B.items():
            rows = (z >= z0) & (z < z1) & ((co > 0) | (cg > 0))
            if not rows.any():
                continue
            out['%s_%s_fill' % (view, b)] = float((co[rows] - cg[rows]).mean() * pix / L)
            so, sg = hi_o - lo_o + 1, hi_g - lo_g + 1
            both = rows & np.isfinite(so) & np.isfinite(sg)
            out['%s_%s_span' % (view, b)] = float(np.nanmean(so[both] - sg[both]) * pix / L) if both.any() else np.nan
        if view == 'front':
            ro, rg = np.nonzero(co)[0], np.nonzero(cg)[0]
            out['top'] = float((z[ro[0]] - z[rg[0]]) / L)
            out['bottom'] = float((z[rg[-1]] - z[ro[-1]]) / L)
            po, pg = pose_measures(o, fr, lm), pose_measures(g, fr, lm)
            for k in po:
                out[k] = float(po[k] - pg[k])
                out[k + '_ours'] = float(po[k]); out[k + '_target'] = float(pg[k])
    return out
