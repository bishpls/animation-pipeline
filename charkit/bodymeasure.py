"""Measurement on a geometry bundle (docs/CHARKIT.md §4): the QA's body, garment and hair measures as functions of plain
data, so any geometry source can be measured the same way: the fast evaluator (charkit.bodyeval) now, a Blender export
later.

A bundle:
    dict(objects=[dict(name, group, V (n, 3) world, F (m, 3) triangles, label (m,) charkit.bodyqa.CLASS per triangle,
                       lit (m, 3), shade (m, 3) the sRGB tones its material renders unlit, role: None, or 'masked' /
                       'unmasked' for the skin with and without the garments' mask (objects())],
         landmarks=dict(L, centre (3,), chin, waist, knee (world z), iris (2, 3) the iris plates' centres),
         target=(V, F) or None)                               # the generated shape aligned by its eyes

    ctx = bodymeasure.Sheet(spec)                            # the model sheet measured once (charkit.bodyqa's views)
    checks = bodymeasure.sheet_body(bundle, ctx)             # the qa3d body_* checks, numpy
    checks = bodymeasure.sheet_palette(bundle, ctx)          # the qa3d palette_* checks
    depth, label = bodymeasure.zbuffer(meshes, az, origin, L, pix, win)   # faceqa.zbuffer, the QA's own

The z-buffer is the QA's own (faceqa.zbuffer, the numba rasteriser), so these checks read the pixels qa3d reads.
"""
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ------------------------------------------------------------------------------------------------------------ z-buffer
def zbuffer(meshes, az, origin, L, pix, win, thin=()):
    """the QA's own z-buffer (faceqa.zbuffer: the numba rasteriser in the venv, its point splat in Blender's Python), so
    these checks read the pixels qa3d reads: meshes [(V, tris, tri_label)] -> (depth, label), label -1 where nothing."""
    from . import faceqa
    return faceqa.zbuffer(meshes, az, origin, L, pix, win, thin=thin)


def objects(bundle, face=False):
    """the bundle's objects a measure reads: as rendered (the skin with the garments' mask on), or with face=True as
    the face measures read them (the whole skin, qa3d.sheet's)."""
    skip = 'masked' if face else 'unmasked'
    return [o for o in bundle['objects'] if o.get('role') != skip]


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
        p = lambda x: x if os.path.isabs(x) else os.path.join(ROOT, x)
        self.face_design = None
        self.face_sheet = ref.get('face_sheet')
        gen = ref.get('body_sheet')
        if gen:
            # a generated full-body sheet (the manifest's sheets.body), as qa3d.Design.sheet_context reads it: scaled by
            # its own front eyes (the kit's convention), no rig in the chain
            self.spec_sheet = dict(gen)
            self.rgb = _png(p(gen['image']))[..., :3]
            self.eye_x = eyelib._knobs(spec.get('eyes'))['x']
            self.D = sheetqa.detect_figures(self.rgb, None, self.eye_x, gen.get('facing', -1))
            self.ppl = self.ppl_eyes = self.D['ppl']
            te = self.D['figures'].get('three_quarter', {}).get('eyes') or []
            self.az3 = round(float(np.degrees(np.arccos(np.clip(abs(te[1][0] - te[0][0]) / (2 * self.eye_x * self.ppl), 0, 1))))
                             if len(te) == 2 else 35.0, 1)
            self.design = bodyqa.design_views(self.rgb, self.D, self.ppl)
            self.palette = paletteqa.extract_views(self.design)
            self.caution = None
            return
        sh = ref.get('sheet')
        if not sh or not ref.get('rig'):
            raise ValueError('no spec.ref.sheet / rig')
        self.spec_sheet = sh
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
    """our bundle z-buffered on the design's grid per view, as bodyqa.zbuffer_views does: {view: (depth, label)}."""
    from . import bodyqa
    lm = bundle['landmarks']
    meshes = [(o['V'], o['F'][o['label'] >= 0], o['label'][o['label'] >= 0]) for o in objects(bundle)]
    az = bodyqa.azimuths(sheet.az3)
    which = which or [v for v in bodyqa.AZ if v in sheet.design]
    out = {}
    for v in which:
        org = bodyqa.origin(v, az[v], np.asarray(lm['iris'], float), lm['centre'])
        out[v] = zbuffer(meshes, az[v], org, lm['L'], 1.0 / sheet.ppl, bodyqa.WIN, thin=(bodyqa.CLASS['line'],))
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
    for o in objects(bundle):
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
    zs = np.concatenate([o['V'][:, 2] for o in objects(bundle) if len(o['V'])])
    zmin, zmax = float(zs.min()), float(zs.max())
    return Frame((0.0, 0.0, (zmin + zmax) / 2), (zmax - zmin) * 1.08, RES)


def label_image(bundle, az, fr, groups=None):
    """the nearest object per pixel from azimuth az (charkit.geom.raster, pixel centres as Blender's renders sample):
    -> (object index per pixel, -1 where nothing; depth)."""
    from .geom.mesh import Mesh
    from .geom.raster import rasterize
    Vs, Fs, lab, off = [], [], [], 0
    shown = objects(bundle)
    for i, o in enumerate(bundle['objects']):
        if groups and o['group'] not in groups or not len(o['F']) or not any(o is x for x in shown):
            continue
        Vs.append(o['V']); Fs.append(o['F'] + off); lab.append(np.full(len(o['F']), i)); off += len(o['V'])
    zb, fb, _ = rasterize(Mesh(np.vstack(Vs), np.vstack(Fs)), az, fr)
    lab = np.concatenate(lab)
    return np.where(fb >= 0, lab[np.maximum(fb, 0)], -1), zb


def scalp(bundle, fr, azs=(0, 90, 180, 270)):
    """qa3d's scalp check: pixels of the flagged scalp (a skin object's 'scalp' triangles) seen through everything
    else, per view (the QA camera, as rendered). -> {az: pixels}."""
    from .geom.mesh import Mesh
    from .geom.raster import rasterize
    Vs, Fs, flag, off = [], [], [], 0
    for o in objects(bundle):
        if not len(o['F']):
            continue
        Vs.append(o['V']); Fs.append(o['F'] + off); off += len(o['V'])
        flag.append(o['scalp'] if 'scalp' in o else np.zeros(len(o['F']), bool))
    m = Mesh(np.vstack(Vs), np.vstack(Fs))
    flag = np.concatenate(flag)
    out = {}
    for az in azs:
        _, fb, _ = rasterize(m, az, fr)
        out[az] = int((flag[np.maximum(fb, 0)] & (fb >= 0)).sum())
    return out


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


# ------------------------------------------------------------------------------------------------ the face on the sheet
def face_region(depth, label, jump, seed_z=-0.15, pix=None, win=None):
    """faceqa.face_region (the visible skin reached from the seed without crossing a depth jump over `jump`), as the
    connected component of the seed in the graph of neighbouring skin pixels whose depths differ by less than `jump`:
    the same pixels, vectorised."""
    from scipy import sparse
    from scipy.sparse.csgraph import connected_components
    from . import faceqa
    pix = faceqa.PIX if pix is None else pix
    win = faceqa.WIN if win is None else win
    H, W = label.shape
    z = faceqa.row_z(H, pix, win)
    r0 = int(np.argmin(np.abs(z - seed_z)))
    cand = np.nonzero(label[r0] == 1)[0]
    out = np.zeros(label.shape, bool)
    if not len(cand):
        return out
    c0 = int(cand[np.argmin(depth[r0, cand])])
    sk = label == 1
    idx = np.arange(H * W).reshape(H, W)
    a, b = [], []
    for (sa, sb) in (((slice(None), slice(0, -1)), (slice(None), slice(1, None))),
                     ((slice(0, -1), slice(None)), (slice(1, None), slice(None)))):
        with np.errstate(invalid='ignore'):
            ok = sk[sa] & sk[sb] & (np.abs(depth[sa] - depth[sb]) < jump)
        a.append(idx[sa][ok]); b.append(idx[sb][ok])
    a, b = np.concatenate(a), np.concatenate(b)
    G = sparse.coo_matrix((np.ones(len(a), bool), (a, b)), shape=(H * W, H * W))
    _, lab = connected_components(G, directed=False)
    return (lab == lab[r0 * W + c0]).reshape(H, W) & sk

def sheet_face(bundle, sheet):
    """qa3d.sheet's checks on a bundle (the face against the model sheet's heads: front half-widths, the neck against
    the jaw, the profile's edge and reaches, the chin, the far cheek; how much face the hair leaves): its classes on the
    bundle's objects, measured by the same code (sheetqa.measure_ours) with the compiled z-buffer and flood fill.
    -> (table, checks)."""
    from . import sheetqa
    from .bodyqa import CLASS as B
    CL = sheetqa.CLASS
    lm = bundle['landmarks']
    if getattr(sheet, 'face_design', None) is None:
        fs = getattr(sheet, 'face_sheet', None)
        if fs:                                          # a generated head sheet (sheets.face), as qa3d reads it
            from . import refcheck
            sheet.face_design = refcheck.face_design(_png(os.path.join(ROOT, fs['image']) if not os.path.isabs(fs['image'])
                                                          else fs['image'])[..., :3], sheet.eye_x, fs.get('facing', -1))
        else:
            heads = {k: tuple(v) for k, v in (sheet.spec_sheet.get('heads') or {}).items()}
            sheet.face_design = sheetqa.measure_sheet(sheet.rgb, heads, sheet.eye_x, ppl=sheet.ppl)
    D = sheet.face_design
    meshes, covers = [], []
    for o in objects(bundle, face=True):
        lab = o['label']
        if o['group'] in ('hair', 'accessories'):
            covers.append((o['V'], o['F'], np.full(len(o['F']), CL['hair' if o['group'] == 'hair' else 'other'])))
        elif o['name'].startswith('iris_'):
            meshes.append((o['V'], o['F'], np.full(len(lab), CL['iris'])))       # (qa3d: the whole plate)
        else:
            meshes.append((o['V'], o['F'], np.where(lab == B['skin'], CL['skin'],
                                                    np.where(lab == B['line'], CL['line'], CL['other']))))
    O = sheetqa.measure_ours(meshes, covers, np.asarray(lm['iris'], float), lm['centre'], lm['L'], D['ppl'],
                             D.get('az_three_quarter', 35.0), face_region=face_region)
    C = sheetqa.compare(O, D)
    C.update(sheetqa.shown(O, D))
    strip = lambda M: {k: v for k, v in M.items() if not isinstance(v, np.ndarray) and k not in ('face', 'lab', 'z', 'lead')}
    return {'ours': {v: strip(O[v]) for v in O}}, C


# ------------------------------------------------------------------------------------------------ pieces (outfit graph)
def load_graph(spec):
    """the character's outfit component graph (charkit.outfit; the manifest's `outfit_graph` reference), or None."""
    import json
    ref = spec.get('ref') if isinstance(spec.get('ref'), dict) else {}
    mp = ref.get('manifest')
    if not mp:
        return None
    p = lambda x: x if os.path.isabs(x) else os.path.join(ROOT, x)
    M = json.load(open(p(mp)))
    g = (M.get('references') or {}).get('outfit_graph')
    return json.load(open(p(g['path']))) if g and os.path.exists(p(g['path'])) else None


def piece_map(graph, spec):
    """the graph's pieces to our objects: {graph piece id: [(object name, side filter)]}, from its comparison with the
    spec's list (a draft name to a hand name) and the draft's own names where the spec holds them; a one-sided graph piece
    drawn by a two-sided object of ours (the boots' shell) takes that object's side of the body (world x: + her left),
    with the side's shoe. Pieces with no object of ours (the skirt's panel, the bow's tails: knobs of other pieces) are
    left out."""
    names = {g['name'] for g in spec.get('garments') or []}
    hand = {m['draft']: m['hand'] for m in (graph.get('comparison') or {}).get('matched', [])}
    out = {}
    for pc in graph['pieces']:
        pid, side = pc['id'], pc.get('side')
        h = hand.get(pid, pid)
        if h in names:
            out[pid] = [(h, None)]
        elif pc['type'] == 'boot' and 'boots' in names:
            sgn = 1 if side == 'L' else -1
            out[pid] = [('boots', sgn)] + ([('shoe_' + side, None)] if 'shoe_' + side in names else [])
    return out


def piece_views(bundle, sheet, which=None):
    """our objects z-buffered on the design's grids per view, each pixel the index of the nearest object (a two-sided
    object's triangles split by side: index + 1000 for her right). -> {view: label image}."""
    from . import bodyqa
    lm = bundle['landmarks']
    obs = objects(bundle)
    meshes = []
    for o in obs:
        i = bundle['objects'].index(o)
        side = np.where(o['V'][o['F']].mean(1)[:, 0] >= 0, i, i + 1000)
        meshes.append((o['V'], o['F'], side))
    az = bodyqa.azimuths(sheet.az3)
    which = which or [v for v in bodyqa.AZ if v in sheet.design]
    out = {}
    for v in which:
        org = bodyqa.origin(v, az[v], np.asarray(lm['iris'], float), lm['centre'])
        out[v] = zbuffer(meshes, az[v], org, lm['L'], 1.0 / sheet.ppl, bodyqa.WIN)[1]
    return out


def piece_extents(bundle, sheet, graph, spec, labels=None, min_px=40):
    """each mapped piece's visible extent per view against the graph's (its bbox in L from the view's origin, x to the
    image's right, z up from the eye line: left, bottom, right, top). -> {piece: {view: dict(ours, graph, d (ours -
    graph per edge), px)}}; views where either side shows fewer than min_px pixels are left out."""
    from . import bodyqa
    labels = labels or piece_views(bundle, sheet)
    idx = {o['name']: i for i, o in enumerate(bundle['objects']) if o.get('role') != 'unmasked'}
    ppl, win = sheet.ppl, bodyqa.WIN
    out = {}
    for pid, members in piece_map(graph, spec).items():
        pc = next(p for p in graph['pieces'] if p['id'] == pid)
        for view, lab in labels.items():
            e = (pc.get('extent') or {}).get(view)
            if not e or e.get('px', 0) < min_px:
                continue
            m = member_mask(lab, idx, members)
            if m.sum() < min_px:
                continue
            rows, cols = np.nonzero(m)
            x0, x1 = (cols.min() + 0.5) / ppl - win['x'], (cols.max() + 0.5) / ppl - win['x']
            z1, z0 = win['top'] - (rows.min() + 0.5) / ppl, win['top'] - (rows.max() + 0.5) / ppl
            ours = [round(x0, 4), round(z0, 4), round(x1, 4), round(z1, 4)]
            g = e['bbox']
            out.setdefault(pid, {})[view] = dict(ours=ours, graph=g, d=[round(a - b, 4) for a, b in zip(ours, g)],
                                                 px=[int(m.sum()), int(e['px'])])
    return out


def member_mask(lab, idx, members):
    """the pixels of a label image (piece_views': object index, + 1000 for a two-sided object's right side) that belong
    to a piece's members [(object name, side filter: None both, +1 her left, -1 her right)]."""
    m = np.zeros(lab.shape, bool)
    for name, sgn in members:
        if name not in idx:
            continue
        i = idx[name]
        m |= (lab == i) if sgn is None else (lab == i) if sgn > 0 else (lab == i + 1000)
        if sgn is None:
            m |= lab == i + 1000
    return m


EDGES = ('left', 'bottom', 'right', 'top')


def piece_checks(bundle, sheet, graph, spec, tol=0.10):
    """the per-piece extents as checks named piece_<id>_<view>_<edge> (value: ours - the graph's, L; PASS within tol,
    WARN within twice, else FAIL), for the fit to answer to."""
    out = {}
    for pid, vs in piece_extents(bundle, sheet, graph, spec).items():
        for view, r in vs.items():
            for k, d in zip(EDGES, r['d']):
                out['piece_%s_%s_%s' % (pid, view, k)] = {'value': d, 'px': r['px'], 'status': 'PASS' if abs(d) <= tol else
                                                          'WARN' if abs(d) <= 2 * tol else 'FAIL'}
    return out


# ------------------------------------------------------------------------------------------------------ piece shapes
OUTLINE_TOL = 0.02       # L: an outline pixel this close to the other outline agrees (about a drawn line's width)


def piece_masks(spec):
    """the outfit's per-view piece masks (the manifest's produced `outfit_masks`: keys VIEW__PIECE on bodyqa.design_views
    grids) and the graph they were cut with (outfit_graph.json beside them) -> (masks {key: bool image}, graph, paths),
    or None when the spec's manifest has none or it hasn't been produced (nothing is built here)."""
    import json
    from . import manifest
    ref = spec.get('ref') if isinstance(spec.get('ref'), dict) else {}
    if not ref.get('manifest'):
        return None
    r = manifest.load(ref['manifest'])['references'].get('outfit_masks')
    if not r:
        return None
    p = r['path'] if os.path.isabs(r['path']) else os.path.join(ROOT, r['path'])
    g = os.path.join(os.path.dirname(p), 'outfit_graph.json')
    if not (os.path.exists(p) and os.path.exists(g)):
        return None
    Z = np.load(p)
    return {k: Z[k] for k in Z.files}, json.load(open(g)), (p, g)


def outline(m):
    """a mask's outline: its pixels with a 4-neighbour outside it."""
    from scipy import ndimage
    return m & ~ndimage.binary_erosion(m, border_value=0)


def outline_f(ours, drawn, tol_px):
    """how two shapes' outlines agree (the boundary F-score): the share of our outline within tol_px of the drawn one
    (p), of the drawn outline within tol_px of ours (r), their harmonic mean (f), and each outline's mean distance to the
    other (px). Scale-free enough for a cuff and a skirt alike, where an IoU punishes the small piece."""
    from scipy import ndimage
    a, b = outline(ours), outline(drawn)
    if not a.any() or not b.any():
        return dict(f=0.0, p=0.0, r=0.0, d_ours=None, d_drawn=None)
    to_b = ndimage.distance_transform_edt(~b)
    to_a = ndimage.distance_transform_edt(~a)
    p, r = float((to_b[a] <= tol_px).mean()), float((to_a[b] <= tol_px).mean())
    return dict(f=2 * p * r / (p + r) if p + r else 0.0, p=p, r=r, d_ours=float(to_b[a].mean()),
                d_drawn=float(to_a[b].mean()))


def iou_tol(ours, drawn, tol_px):
    """the area overlap with a band tol_px either side of the drawn outline left out: the drawn line's width is where
    the masks themselves are unsure, and a thin piece (a cuff) loses most of a plain IoU to it. The band is at most half
    the drawn piece's inscribed half-width, so a piece thinner than the band still has a middle to compare."""
    from scipy import ndimage
    b = outline(drawn)
    if not b.any():
        keep = np.ones(drawn.shape, bool)
    else:
        band = min(tol_px, 0.5 * float(ndimage.distance_transform_edt(drawn).max()))
        keep = ndimage.distance_transform_edt(~b) > band
    u = ((ours | drawn) & keep).sum()
    if not u:                                   # all of it within the band (a line-thin piece): the plain overlap
        u = (ours | drawn).sum()
        return float((ours & drawn).sum() / u) if u else 0.0
    return float(((ours & drawn) & keep).sum() / u)


def built_parent(graph, pm):
    """each piece no object of ours builds -> the nearest piece up its attach chain that one does (the bodice's panel ->
    the top, the bow's tails -> the bow), or None: what it is part of in our build."""
    by = {p['id']: p for p in graph['pieces']}
    out = {}
    for pid in by:
        if pm.get(pid):
            continue
        q, seen = (by[pid].get('attach') or {}).get('parent'), set()
        while q and q in by and not pm.get(q) and q not in seen:
            seen.add(q)
            q = (by[q].get('attach') or {}).get('parent')
        out[pid] = q if q and pm.get(q) else None
    return out


def folded(masks, graph, pm):
    """the drawn masks with each piece we don't build folded into the piece of ours it is part of (built_parent), so
    our top is compared with the drawn top and its panel; the unbuilt piece keeps its own mask for the count."""
    up = built_parent(graph, pm)
    out = dict(masks)
    for pid, parent in up.items():
        if not parent:
            continue
        for k, m in masks.items():
            view, q = k.split('__', 1)
            if q == pid:
                key = '%s__%s' % (view, parent)
                out[key] = (out[key] | m) if key in out else m
    return out


WIN_X = 2.3                      # L: the design grids' eyes' middle from their left edge (bodyqa.WIN['x'])


def piece_shapes(labels, names, masks, graph, spec, ppl, min_px=40, tol=OUTLINE_TOL):
    """each outfit piece's visible shape against its drawn mask, per view. labels: {view: object-index image
    (piece_views')}; names: the objects' names by index; masks: piece_masks()'s. -> {piece id: {'members': our objects
    or None (no object of ours builds it), 'views': {view: dict(iou, iou_tol (iou_tol at tol), f, p, r (outline_f at
    tol), d_ours, d_drawn (L), px (ours, drawn))}}}.
    A view where the drawing shows fewer than min_px of the piece is left out (a piece a view hides has an empty mask).
    A piece we don't build is compared as part of the piece of ours it belongs to (folded); its record says which.
    Where a piece lies over another of the same colour (the graph's layer order: the overskirt panels over the skirt),
    the drawing can't tell them apart: our over-piece's pixels on the other's drawing, and the other's drawn pixels
    under our over-piece, count for neither (px_same_colour: those pixels, per view)."""
    idx = {n: i for i, n in enumerate(names)}
    pm = piece_map(graph, spec)
    up = built_parent(graph, pm)
    masks = folded(masks, graph, pm)
    col = {pc['id']: (pc.get('colour') or {}).get('name') for pc in graph['pieces']}
    lies_on = {}                                         # piece -> the same-coloured pieces it lies over
    for pc in graph['pieces']:
        for q in (pc.get('layer') or {}).get('over') or []:
            if col.get(q) and col.get(q) == col.get(pc['id']) and pm.get(pc['id']) and pm.get(q):
                lies_on.setdefault(pc['id'], []).append(q)
    under = {}                                           # piece -> the same-coloured pieces lying over it
    for a, qs in lies_on.items():
        for q in qs:
            under.setdefault(q, []).append(a)
    out = {}
    for pc in graph['pieces']:
        pid = pc['id']
        members = pm.get(pid)
        rec = out[pid] = {'members': [m[0] for m in members] if members else None, 'views': {},
                          'part_of': up.get(pid), 'with': sorted(q for q, par in up.items() if par == pid)}
        for view, lab in labels.items():
            d = masks.get('%s__%s' % (view, pid))
            if d is None or d.sum() < min_px:
                continue
            if d.shape != lab.shape:
                raise ValueError('%s: mask %s against labels %s' % (view, d.shape, lab.shape))
            m = member_mask(lab, idx, members) if members else np.zeros(lab.shape, bool)
            amb = np.zeros(lab.shape, bool)
            for q in lies_on.get(pid, ()):                  # ours over the drawn other
                dq = masks.get('%s__%s' % (view, q))
                if dq is not None:
                    amb |= m & dq & ~d
            for a in under.get(pid, ()):                    # the drawn this under our other
                amb |= d & member_mask(lab, idx, pm[a]) & ~masks.get('%s__%s' % (view, a), np.zeros(lab.shape, bool))
            m, d = m & ~amb, d & ~amb
            inter, union = (m & d).sum(), (m | d).sum()
            ext = {}
            if m.any() and d.any():                          # its reach against the drawing's (L): the lowest row, and
                ro, co = np.nonzero(m); rd, cd = np.nonzero(d)   # the column farthest from the eyes' middle
                c0 = WIN_X * ppl
                ext = dict(bottom=round(float(ro.max() - rd.max()) / ppl, 4),
                           outer=round(float(np.abs(co - c0).max() - np.abs(cd - c0).max()) / ppl, 4),
                           area=round(float(m.sum()) / float(d.sum()), 3))
            o = outline_f(m, d, tol * ppl)
            rec['views'][view] = dict(iou=round(float(inter / union), 4) if union else 0.0,
                                      iou_tol=round(iou_tol(m, d, tol * ppl), 4), f=round(o['f'], 4),
                                      p=round(o['p'], 4), r=round(o['r'], 4),
                                      d_ours=None if o['d_ours'] is None else round(o['d_ours'] / ppl, 4),
                                      d_drawn=None if o['d_drawn'] is None else round(o['d_drawn'] / ppl, 4),
                                      px=[int(m.sum()), int(d.sum())], px_same_colour=int(amb.sum()), **ext)
    return out


def piece_confusion(labels, names, masks, graph, spec, view):
    """where each drawn piece's pixels land in ours for one view: {drawn piece: {our piece, 'other' (an object of ours
    that builds no piece: the skin, the hair) or 'none' (nothing of ours): pixels}}: the skirt drawn where we put the
    overskirt panel, the collar under our hair."""
    lab = labels[view]
    idx = {n: i for i, n in enumerate(names)}
    ours = np.full(lab.shape, -1, np.int32)
    ids = [pc['id'] for pc in graph['pieces']]
    pm = piece_map(graph, spec)
    for k, pid in enumerate(ids):
        if pm.get(pid):
            ours[member_mask(lab, idx, pm[pid])] = k
    out = {}
    for pid in ids:
        d = masks.get('%s__%s' % (view, pid))
        if d is None or not d.any():
            continue
        got, anything = ours[d], lab[d] >= 0
        row = {ids[j]: int(n) for j, n in zip(*np.unique(got[got >= 0], return_counts=True))}
        for k, sel in (('other', (got < 0) & anything), ('none', ~anything)):
            if sel.any():
                row[k] = int(sel.sum())
        out[pid] = row
    return out


# ------------------------------------------------------------------------------------------------- pieces in 3D
OUTER = 0.03             # L: a point of ours this close to the target's surface is on the outside (the rest is inside it)


def _piece_points(meshes, names, members):
    """a piece's surface as points (vertices and triangle centres) of its member objects, a two-sided object's by its
    side (world x: + her left)."""
    pts = []
    for name, sgn in members:
        if name not in names:
            continue
        V, T = meshes[names.index(name)][:2]
        q = np.concatenate([V, V[T].mean(1)]) if len(T) else V
        if sgn is not None:
            q = q[(q[:, 0] >= 0) == (sgn > 0)]
        pts.append(q)
    return np.concatenate(pts) if pts else np.zeros((0, 3))


def piece_depths(meshes, names, target_V, labels, piece_names, graph, spec, L):
    """each outfit piece of ours against the target's points of that piece in 3D (the visual hull's per-vertex pieces,
    bundle.target_pieces): reach, the distance from each target point to our piece (where the design has it, how far
    ours is: the median and 90th percentile, L); excess, from our piece's outer points (within OUTER of the target's
    surface) to the target's piece; dz, our piece's median height less the target's (L). A piece we don't build is
    folded into the built piece it attaches to, as in 2D. -> {piece id: dict(n, reach, reach90, excess, excess90, dz)
    or dict(n, members=None)}."""
    from scipy.spatial import cKDTree
    pm = piece_map(graph, spec)
    up = built_parent(graph, pm)
    by_name = {v: int(k) for k, v in piece_names.items()}
    allT = cKDTree(target_V)
    out = {}
    for pc in graph['pieces']:
        pid = pc['id']
        ks = [by_name[q] for q in [pid] + [q for q, par in up.items() if par == pid] if q in by_name]
        tp = target_V[np.isin(labels, ks)] if ks else np.zeros((0, 3))
        if not pm.get(pid):
            out[pid] = dict(n=int((labels == by_name.get(pid, -1)).sum()), members=None, part_of=up.get(pid))
            continue
        O = _piece_points(meshes, names, pm[pid])
        if not len(tp) or not len(O):
            out[pid] = dict(n=int(len(tp)), ours=int(len(O)))
            continue
        reach = cKDTree(O).query(tp)[0] / L
        outer = O[allT.query(O)[0] / L < OUTER]
        exc = cKDTree(tp).query(outer)[0] / L if len(outer) else None
        out[pid] = dict(n=int(len(tp)), reach=round(float(np.median(reach)), 4),
                        reach90=round(float(np.percentile(reach, 90)), 4),
                        excess=None if exc is None else round(float(np.median(exc)), 4),
                        excess90=None if exc is None else round(float(np.percentile(exc, 90)), 4),
                        dz=round(float((np.median(O[:, 2]) - np.median(tp[:, 2])) / L), 4))
    return out
