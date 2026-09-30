"""Measured QA for a built character (docs/CHARKIT.md §4): numbers instead of eyeballing, measured in the venv on the build's
geometry bundle (charkit/bundle.py: Blender builds and exports; this measures), written as a report with PASS / WARN /
FAIL per check (a check that couldn't run says SKIPPED and why) and overlay images. Every view is a numba z-buffer
(charkit.geom.raster: pixel centres, a label per triangle), the renders EEVEE made before are drawn from the bundle's
materials, and nothing here needs Blender. `python -m charkit build --qa blender` still runs the old Blender pass
(charkit/qa3d_blender.py) for comparison.

  shape      silhouette overlap (IoU) with the generated shape (a TRELLIS.2 GLB, aligned as the build aligned it) from six
             azimuths, overall and per height band (hair, torso, skirt, legs)
  ref        front silhouette overlap with the reference image (both cropped to their bounding boxes)
  scalp      pixels of scalp showing through the hair (the upper cranium and the back of the head, flagged), per view
  poke       share of garment pixels where the body shows through
  hair_noise the hair's shading noise: tone edges per hair pixel (clean anime shadow shapes are low; noisy normals high),
             on the hair drawn with its own toon materials, envelope normals and outline hull
  mesh       open edges and loose parts per hair / garment object (information)
  face_shape the face's shape against the generated character's face (charkit/faceqa.py: the lower face's width, the chin,
             the profile, the cheek at three-quarter, depth from under the eyes; how much face the hair leaves showing) and
             the feature heights against the design rig; overlays qa_face_shape.png, qa_face_contours.png
  sheet      the face against the design's model sheet (charkit/sheetqa.py): front half-widths, the profile's front
             edge and reach (nose, chin), the chin's height, the far cheek at three-quarter; overlay qa_sheet.png
  figures    the model sheet's figures found from the picture (charkit/sheetqa.py detect_figures) against the spec's
             hand-typed head boxes; overlay qa_sheet_figures.png
  body       the whole character against the sheet's front, 3/4, profile and back figures (charkit/bodyqa.py): silhouette,
             hair, skin and outfit IoU aligned on the eyes, the feet, hair length and width, the skirt's flare and hem,
             sleeves, leg and boot; z-buffered by class (scene_classes); overlay qa_sheet_body.png
  expr       the sheet's expression heads matched part by part to the kit's library and graded (charkit/exprqa.py; our
             keys applied to the posed base meshes, z-buffered); overlay qa_sheet_expr.png
  palette    the design's colours per class (the sheet's pixels) against our materials' unlit tones, CIEDE2000
             (charkit/paletteqa.py); overlay qa_sheet_palette.png
  eye        each eye head-on against the design rig's eye layer (charkit/eyeqa.py): the opening's aspect and width, how
             much of it the iris fills, the pupil's run and aspect; overlay qa_eyes.png
  face       per expression and mouth shape, from the shape keys' geometry (front projection, no render): each eye's
             opening (area between the lid margins, against neutral), the share of the iris the lids leave visible, left /
             right symmetry, each mouth shape's opening (area, width, height, left / right balance) and how distinct the
             visemes are from each other; graded: blink closes, no iris in a blink, eyes and mouth symmetric, visemes
             distinct, and each expression's openness inside the range it is meant to have (FACE_EXPECT, warn only)
  face_folds skin faces round the eyes and the mouth facing away at rest or flipping under a lid or mouth key (folded lid
             and lip rings: the realistic lids stretched onto the anime outline, the lip rolls), summed over the keys
  look       the render look (charkit/lookqa.py): the head and neck skin's shading noise under the boards' light and a
             sweep of lights (face_noise, face_noise_sweep, face_islands), its shadows against the design's
             (face_shadow_*), the outlines' widths and spread against the design's (line_width, line_spread); overlays
             qa_face_shading.png, qa_face_shadow.png, qa_lines.png. Views are drawn as the boards light them: the style's
             look (a camera key turns with each view), the face's SDF shading from its maps

Each part is cached (charkit.cache.qa_part) on what it read of the bundle (arrays and metadata, by hash), the reference
files it opened (by content) and its code: a QA-only change reruns the QA, an unchanged bundle restores it.

    python -m charkit qa OUT/bundle [--out OUT/qa] [--cache on|off|refresh]
    from charkit import bundle, qa3d; report = qa3d.run(bundle.load('OUT/bundle'), 'OUT/qa')
"""
import json, os, time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AZ = (0, 45, 90, 135, 180, 270)
LIMITS = {                     # (pass at or better, warn at or better); else fail
    'shape_iou': (0.80, 0.65), 'shape_iou_hair': (0.75, 0.60), 'ref_iou': (0.85, 0.70),
    'scalp_px': (30, 300), 'poke_share': (0.005, 0.02), 'hair_noise': (0.04, 0.08), 'face_folds': (40, 300),
    'blink_open': (0.03, 0.10), 'blink_iris': (0.01, 0.05), 'eye_asym': (0.03, 0.08), 'mouth_asym': (0.05, 0.15),
    'viseme_gap': (0.010, 0.005), 'mouth_cover': (0.97, 0.90),
}
COVER = (11, 13, 9, 4)         # exprqa classes an open mouth may show: its inside, tongue, teeth, the lip line
# each eye expression's opening as a share of neutral: (low, high); outside it the check warns
FACE_EXPECT = {'blink': (0.0, 0.03), 'half': (0.3, 0.7), 'wide': (1.05, 2.0), 'happy': (0.0, 0.35), 'squint': (0.2, 0.8),
               'angry': (0.5, 1.05), 'sad': (0.5, 1.05), 'shock': (0.95, 1.05)}
VISEMES = ('aa', 'ih', 'ou', 'ee', 'oh')
FRAME = (360, 560)             # the full-figure views: width, height (pixels), the figure's height x 1.08 across
EYE_SIZE = 0.42                # the eye render's window, in L
# the renderer's anti-aliasing: supersampled, then EEVEE's 1.5 px pixel filter as a Gaussian (sigma in output pixels),
# calibrated against EEVEE on Clawd (docs/CHARKIT.md §4): the eye renders' measures within a pixel, the silhouettes'
# mismatch at its sampling noise (0.07% of their pixels), hair_noise within 2%
EYE_SS, EYE_FILTER = 5, 0.55   # the eye renders
TEX_BLUR = 0.3                 # the eye textures' prefilter, sigma in texels per output pixel (the renderer's mipmaps)
FIG_SS, FIG_FILTER = 3, 0.44   # the full-figure renders: silhouettes, scalp, hair noise
WORLD = (0.86, 0.86, 0.90)     # the world colour behind an opaque render (linear; charkit.scene.reset)
STATUS = ['PASS', 'WARN', 'FAIL', 'SKIPPED']


def _json(o):
    """numpy values in the report as plain JSON."""
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.generic):
        return o.item()
    return str(o)


def _grade(key, v, higher_better=True):
    p, w = LIMITS[key]
    if higher_better:
        return 'PASS' if v >= p else 'WARN' if v >= w else 'FAIL'
    return 'PASS' if v <= p else 'WARN' if v <= w else 'FAIL'


def _path(p):
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def _save_rgb(path, rgb):
    from PIL import Image
    a = np.clip(np.asarray(rgb, float)[..., :3], 0, 1)
    Image.fromarray((a * 255 + 0.5).astype(np.uint8)).save(path)


def _iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 1.0


def _bbox_norm(mask, size=(200, 320)):
    ys, xs = np.nonzero(mask)
    if len(ys) == 0:
        return np.zeros(size[::-1], bool)
    m = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    H, W = size[1], size[0]
    yi = (np.arange(H) * m.shape[0] / H).astype(int); xi = (np.arange(W) * m.shape[1] / W).astype(int)
    return m[yi][:, xi]


def _srgb(c):
    c = np.clip(np.asarray(c, float), 0, None)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def _lin(c):
    c = np.asarray(c, float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


# --------------------------------------------------------------------------------------------------- face (geometry)
def _profile(P, xs):
    """a lid or lip chain's height over x (front view): P (n, 2) as (x, z), sorted by x, sampled at xs."""
    o = np.argsort(P[:, 0])
    return np.interp(xs, P[o, 0], P[o, 1], left=np.nan, right=np.nan)


def opening(upper, lower, xs):
    """the opening between an upper and a lower chain ((n, 2) x-z each) over the x samples: -> (gap per x, area)."""
    g = _profile(upper, xs) - _profile(lower, xs)
    g = np.where(np.isfinite(g), np.maximum(g, 0), 0)
    return g, float(np.trapezoid(g, xs) if hasattr(np, 'trapezoid') else np.trapz(g, xs))


def visible_share(upper, lower, pts):
    """the share of points (m, 2) lying between the chains (below the upper, above the lower)."""
    up, lo = _profile(upper, pts[:, 0]), _profile(lower, pts[:, 0])
    ok = np.isfinite(up) & np.isfinite(lo) & (pts[:, 1] < up) & (pts[:, 1] > lo)
    return float(ok.mean()) if len(pts) else 0.0


def ellipse_points(cx, cz, rx, rz, n=41):
    u = np.linspace(-1, 1, n)
    X, Z = np.meshgrid(u, u)
    m = X ** 2 + Z ** 2 <= 1
    return np.stack([cx + X[m] * rx, cz + Z[m] * rz], 1)


def key_xz_numpy(A):
    """face_from's key reader for an assembly (charkit.character.assemble with keys): the skin's world (x, z) under a
    shape key as the build names them ('eye_blink': both eyes' offsets, 'mouth_aa'), or at rest (None)."""
    V = np.asarray(A['verts'])

    def get(name):
        if name is None:
            return V[:, [0, 2]]
        if name.startswith('eye_') and name[4:] in A['eyes'][0]['keys']:
            return (V + sum(E['keys'][name[4:]][0] for E in A['eyes']))[:, [0, 2]]
        if name.startswith('mouth_') and name[6:] in A['mouth']['keys']:
            return (V + A['mouth']['keys'][name[6:]])[:, [0, 2]]
        return V[:, [0, 2]]
    return get


def key_xz(B):
    """face_from's key reader on a bundle: the skin's base mesh (the assembly's) under one of its keys, or at rest."""
    sk = B.skin()
    V = sk.V('base')
    keys = sk.keys('base')

    def get(name):
        if name is None or name not in keys:
            return V[:, [0, 2]]
        idx, D = keys[name]
        P = V.copy()
        P[idx] += D
        return P[:, [0, 2]]
    return get


def assembly(B, variant='assembly'):
    """the assembly as face_from and face_folds read it (charkit.character.assemble's dict, in part), from a bundle's
    skin: its `assembly` variant (float64, as the assembly made it: the folds) or its `base` (the shape keys Blender
    holds: the face's openings, as the build's keys read)."""
    As = B.assembly
    sk = B.skin()
    loopv, starts, counts = sk.polys(variant)
    faces = np.split(loopv, np.cumsum(counts)[:-1])
    keys = sk.keys(variant)
    n = len(sk.V(variant))

    def dense(name):
        D = np.zeros((n, 3))
        if name in keys:
            D[keys[name][0]] = keys[name][1]
        return D
    eyes = []
    for E in As['eyes']:
        tag = 'L' if E['side'] > 0 else 'R'
        eyes.append(dict(side=E['side'], c=tuple(E['c']), eye=dict(upper=list(E['upper']), lower=list(E['lower']),
                                                                   margin=list(E['margin'])),
                         keys={k: (dense('eye_%s_%s' % (k, tag)),) for k in E['keys']}))
    M = As['mouth']
    return dict(verts=sk.V(variant), faces=faces, fmat=sk.a(variant, 'pmat').astype(np.int64),
                head=dict(L=As['L'], centre=np.asarray(As['centre'], float), eye_knobs=dict(As['eye_knobs'])),
                eyes=eyes, mouth=dict(c=tuple(M['c']), m=dict(upper=list(M['upper']), lower=list(M['lower'])),
                                      keys={k: dense('mouth_' + k) for k in M['keys']}))


def face(B, expressions=None, mouths=None):
    """the face's measured expressions and mouth shapes (see the module docstring), from the bundle's skin keys
    -> (table, checks)."""
    A = assembly(B, 'base')
    mouths = mouths or [k[6:] for k in B.skin().keys('base') if k.startswith('mouth_')]
    return face_from(A, B.spec, key_xz(B), expressions, mouths)


def face_from(A, spec, key_xz, expressions=None, mouths=None):
    """face()'s measures from the assembly A and a key reader key_xz(name) -> the skin's (x, z) under that shape key
    (the basis for None or a missing key). -> (table, checks)."""
    from .eyetex import DEFAULT_IRIS
    Hd = A['head']; L = Hd['L']
    expressions = expressions or FACE_EXPECT.keys()
    EK = Hd['eye_knobs']; W = EK['width'] * L
    IK = dict(DEFAULT_IRIS); IK.update(spec.get('iris') or {})
    base = key_xz(None)
    table = {'eyes': {}, 'mouth': {}}
    eyes = []
    for E in A['eyes']:
        up, lo = E['eye']['upper'], E['eye']['lower']
        xs = np.linspace(base[up + lo, 0].min(), base[up + lo, 0].max(), 96)
        iris = ellipse_points(E['c'][0], E['c'][1] + IK['cz'] * W, IK['rx'] * W, IK['rz'] * W)
        _, a0 = opening(base[up], base[lo], xs)
        eyes.append((E['side'], up, lo, xs, iris, a0))
    for name in ['neutral'] + list(expressions):
        P = base if name == 'neutral' else key_xz('eye_' + name)
        row = {}
        for side, up, lo, xs, iris, a0 in eyes:
            _, a = opening(P[up], P[lo], xs)
            row['L' if side > 0 else 'R'] = {'open': round(a / a0, 4) if a0 > 0 else None,
                                              'iris': round(visible_share(P[up], P[lo], iris), 4)}
        table['eyes'][name] = row
    table['eyes']['neutral_area_L2'] = round(eyes[0][5] / L ** 2, 5)
    m = A['mouth']['m']
    up, lo = list(m['upper']), list(m['lower'])
    xs = np.linspace(base[up, 0].min(), base[up, 0].max(), 96)
    mid = 0.5 * (xs.min() + xs.max())
    mouths = mouths or list(A['mouth'].get('keys') or [])
    for name in ['neutral'] + [k for k in mouths if k != 'neutral']:
        P = base if name == 'neutral' else key_xz('mouth_' + name)
        g, a = opening(P[up], P[lo], xs)
        on = g > 0.002 * L
        left, right = float(np.trapezoid(g[xs < mid], xs[xs < mid])), float(np.trapezoid(g[xs >= mid], xs[xs >= mid]))
        table['mouth'][name] = {'area_L2': round(a / L ** 2, 5), 'width_L': round(float(np.ptp(xs[on])) / L, 4) if on.any() else 0.0,
                                'height_L': round(float(g.max()) / L, 4), 'asym': round(abs(left - right) / a, 4) if a > 1e-9 else 0.0}
    E_ = table['eyes']; M_ = table['mouth']
    checks = {}
    if 'blink' in E_:
        v = max(E_['blink'][s]['open'] or 0 for s in ('L', 'R'))
        checks['blink_open'] = {'value': round(v, 4), 'status': _grade('blink_open', v, False)}
        v = max(E_['blink'][s]['iris'] for s in ('L', 'R'))
        checks['blink_iris'] = {'value': round(v, 4), 'status': _grade('blink_iris', v, False)}
    asym = {k: abs((r['L']['open'] or 0) - (r['R']['open'] or 0)) for k, r in E_.items() if isinstance(r, dict) and 'L' in r}
    k = max(asym, key=asym.get)
    checks['eye_asym'] = {'value': round(asym[k], 4), 'worst': k, 'status': _grade('eye_asym', asym[k], False)}
    out = {k: E_[k]['L']['open'] for k, (lo_, hi_) in FACE_EXPECT.items()
           if k in E_ and not (lo_ <= (E_[k]['L']['open'] or 0) <= hi_)}
    checks['expr_range'] = {'value': len(out), 'outside': out, 'status': 'PASS' if not out else 'WARN'}
    ma = {k: r['asym'] for k, r in M_.items() if r['area_L2'] > 1e-4}
    if ma:
        k = max(ma, key=ma.get)
        checks['mouth_asym'] = {'value': ma[k], 'worst': k, 'status': _grade('mouth_asym', ma[k], False)}
    vs = [k for k in VISEMES if k in M_]
    if len(vs) > 1:
        best = min(((np.hypot(M_[a]['width_L'] - M_[b]['width_L'], M_[a]['height_L'] - M_[b]['height_L']), a, b)
                    for i, a in enumerate(vs) for b in vs[i + 1:]))
        checks['viseme_gap'] = {'value': round(float(best[0]), 4), 'closest': [best[1], best[2]],
                                'status': _grade('viseme_gap', float(best[0]))}
    return table, checks


def _face_normals(V, faces):
    Q = np.array([tuple(f) + (f[-1],) * (4 - len(f)) for f in faces])      # triangles padded (their normal is unchanged)
    n = np.cross(V[Q[:, 2]] - V[Q[:, 0]], V[Q[:, 3]] - V[Q[:, 1]])
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-15)


def face_folds(A):
    """skin faces round the eyes and the mouth (the openings' own walls, fmat 2 and 3, left out) facing away from the viewer
    at rest, and flipped (turned past 90 degrees) or facing away under each lid and mouth key. A: an assembly (or
    assembly(B) of a bundle). -> dict(rest, keys {key: count}, total)."""
    V = np.asarray(A['verts']); F = A['faces']; fm = np.asarray(A['fmat']); Hd = A['head']; L = Hd['L']
    q = (np.array([V[list(f)].mean(0) for f in F]) - Hd['centre']) / L
    mouth = (fm == 1) & (np.abs(q[:, 0]) < 0.16) & (np.abs(q[:, 2] + 0.28) < 0.1) & (q[:, 1] < -0.2)
    eyes = (fm == 1) & (np.abs(np.abs(q[:, 0]) - 0.17) < 0.14) & (np.abs(q[:, 2]) < 0.12) & (q[:, 1] < -0.15)
    n0 = _face_normals(V, F)
    rest = int(((mouth | eyes) & (n0[:, 1] > 0.2)).sum())
    keys = {}
    for sh, D in A['mouth']['keys'].items():
        n1 = _face_normals(V + D, F)
        keys['mouth_' + sh] = int((mouth & (((n0 * n1).sum(1) < 0) | (n1[:, 1] > 0.2))).sum())
    for sh in A['eyes'][0]['keys']:
        n1 = _face_normals(V + sum(E['keys'][sh][0] for E in A['eyes']), F)
        keys['eye_' + sh] = int((eyes & (((n0 * n1).sum(1) < 0) | (n1[:, 1] > 0.2))).sum())
    return dict(rest=rest, keys=keys, total=rest + sum(keys.values()))


def folds(B, design=None, out=None):
    """the face_folds check on a bundle -> ({}, checks)."""
    ff = face_folds(assembly(B))
    return None, {'face_folds': {'value': ff['total'], 'rest': ff['rest'], 'per_key': ff['keys'],
                                 'base': B.spec.get('base', 'makehuman'), 'status': _grade('face_folds', ff['total'], False)}}


# --------------------------------------------------------------------------------------------------- the references
class Design:
    """the design side of a bundle's QA: the references its spec names (the model sheet, the design rig and its eye
    layers, the reference image) and the rig's measures (in the bundle), loaded once and measured through the venv memo.
    Every file it reads is recorded into the bundle's open recordings, so a cached part is keyed on it."""

    def __init__(self, B):
        self.B = B
        self._m = {}

    def _rec(self, path):
        for r in self.B._reads:
            r.files.add(os.path.abspath(path))

    def rgba(self, path):
        """an image as floats (H, W, 4), row 0 = top, as Blender's loader gives it (bundle.bytes_to_float, straight
        alpha)."""
        path = _path(path)
        self._rec(path)
        if ('img', path) not in self._m:
            from PIL import Image
            from .bundle import bytes_to_float
            self._m[('img', path)] = bytes_to_float(np.asarray(Image.open(path).convert('RGBA')))
        return self._m[('img', path)]

    def has_alpha(self, path):
        """does the image carry transparency (Blender loads it with four channels)?"""
        from PIL import Image
        im = Image.open(_path(path))
        return im.mode in ('RGBA', 'LA', 'PA') or 'transparency' in im.info

    def ref(self):
        r = self.B.spec.get('ref')
        return r if isinstance(r, dict) else {}

    def R(self):
        """the design rig's measures (ref_measure.json, carried in the bundle) or None."""
        return self.B.meta('ref_measure')

    def memo(self, fn, *a, **kw):
        from . import cache
        return cache.venv_memo(fn, *a, **kw)

    def _kept(self, key, files=()):
        """a result this Design already made (the evaluator's calls share it), its files recorded again, or None."""
        if key in self._m:
            for p in self._m[key][1]:
                self._rec(p)
            return self._m[key][0]
        return None

    def _keep(self, key, value, files):
        self._m[key] = (value, list(files))
        return value

    def sheet_context(self):
        """the model sheet, loaded and measured once: the picture, its scale (the front figure's height against the rig's),
        its figures (detected; the spec's head boxes where it has them) and the three-quarter's angle; or {'why'}."""
        key = ('ctx', self.B.assembly['eye_knobs']['x'], json.dumps(self.ref(), sort_keys=True, default=str))
        got = self._kept(key)
        if got is not None:
            return got
        from . import sheetqa
        ref = self.ref()
        gen = ref.get('body_sheet')
        if gen:
            # a generated full-body sheet (the manifest's sheets.body): scaled by its own front eyes (the kit's
            # convention), no rig in the chain
            rgb = self.rgba(gen['image'])[..., :3].astype(float)
            ex = self.B.assembly['eye_knobs']['x']
            D = self.memo(sheetqa.detect_figures, rgb, None, ex, gen.get('facing', -1))
            ppl = D['ppl']
            te = D['figures'].get('three_quarter', {}).get('eyes') or []
            az3 = float(np.degrees(np.arccos(np.clip(abs(te[1][0] - te[0][0]) / (2 * ex * ppl), 0, 1)))) if len(te) == 2 else 35.0
            heads = {v: tuple(D['figures'][v]['head']) for v in ('front', 'three_quarter', 'profile') if v in D['figures']}
            return self._keep(key, dict(rgb=rgb, ppl=ppl, ppl_eyes=ppl, D=D, az3=round(az3, 1), heads=heads, eye_x=ex,
                                        verify={}, generated=gen.get('id')), [_path(gen['image'])])
        got, files = self._source_sheet()
        return self._keep(key, got, files)

    def _source_sheet(self):
        """the source model sheet (the spec's ref.sheet: idol_D on Clawd), scaled by its front figure against the rig and
        its figures found -> (the sheet_context dict, the files read) or ({'why'}, ())."""
        from . import sheetqa
        ref = self.ref()
        sh = ref.get('sheet')
        R = self.R()
        if not sh or not ref.get('rig') or not R:
            return {'why': 'no spec.ref.sheet / rig / ref_measure.json'}, ()
        rgb = self.rgba(sh['image'])[..., :3].astype(float)
        rig_alpha = self.rgba(os.path.join(_path(ref['rig']), 'base.png'))[..., 3]
        ex = self.B.assembly['eye_knobs']['x']
        ppl = self.memo(sheetqa.sheet_ppl, rgb, sh['front_figure'], rig_alpha, R['ppl'])
        D = self.memo(sheetqa.detect_figures, rgb, ppl=ppl, eye_x=ex, facing=sh.get('facing'))
        fe = D['figures'].get('front', {}).get('eyes') or []
        ppl_eyes = abs(fe[1][0] - fe[0][0]) / (2 * ex) if len(fe) == 2 else None
        te = D['figures'].get('three_quarter', {}).get('eyes') or []
        az3 = float(np.degrees(np.arccos(np.clip(abs(te[1][0] - te[0][0]) / (2 * ex * ppl), 0, 1)))) if len(te) == 2 else 35.0
        heads = {k: tuple(v) for k, v in (sh.get('heads') or {}).items()} or \
            {v: tuple(D['figures'][v]['head']) for v in ('front', 'three_quarter', 'profile') if v in D['figures']}
        return (dict(rgb=rgb, ppl=ppl, ppl_eyes=ppl_eyes, D=D, az3=round(az3, 1), heads=heads, eye_x=ex,
                     verify=sheetqa.verify_figures(D, sh)),
                [_path(sh['image']), os.path.join(_path(ref['rig']), 'base.png')])

    def expression_sheet(self):
        """the sheet that draws the character's expressions: the design sheet's (sheet_context) when it has expression
        heads, else the source model sheet's (the spec's ref.sheet: on Clawd idol_D, the only drawing of her expressions;
        the generated body sheet has none). The manifest gives the expressions no authority, so the checks against it
        read INFO (checks.authorize). -> sheet_context's dict with 'source' (the sheet's path), or {'why'}."""
        ctx = self.sheet_context()
        if 'why' not in ctx and ctx['D']['expressions']:
            return dict(ctx, source=self.ref().get('body_sheet', self.ref().get('sheet', {})).get('image'))
        if not self.ref().get('body_sheet'):
            return ctx if 'why' in ctx else dict(ctx, source=self.ref().get('sheet', {}).get('image'))
        key = ('ctx_expr', self.B.assembly['eye_knobs']['x'], json.dumps(self.ref().get('sheet'), sort_keys=True,
                                                                      default=str), self.ref().get('rig'))
        got = self._kept(key)
        if got is not None:
            return got
        got, files = self._source_sheet()
        return self._keep(key, got if 'why' in got else dict(got, source=self.ref()['sheet']['image']), files)

    def design_views(self):
        """the design's full figures cut and classified (charkit.bodyqa.design_views)."""
        from . import bodyqa
        ctx = self.sheet_context()
        return self.memo(bodyqa.design_views, ctx['rgb'], ctx['D'], ctx['ppl'])

    def sheet_measures(self):
        """charkit.sheetqa.measure_sheet on the sheet's own float32 pixels, at the rig-matched scale -> (D, ppl) or
        None."""
        from . import sheetqa
        ref = self.ref()
        ex = self.B.assembly['eye_knobs']['x']
        gen = ref.get('face_sheet')
        if gen:
            # a generated head sheet (the manifest's sheets.face), measured as a drawn head at refcheck.FACE_PPL
            from . import refcheck
            key = ('sheet', ex, 'gen', gen['image'])
            got = self._kept(key)
            if got is not None:
                return got
            D = self.memo(refcheck.face_design, self.rgba(gen['image'])[..., :3], ex, gen.get('facing', -1))
            return self._keep(key, (D, D['ppl']), [_path(gen['image'])])
        sh = ref.get('sheet')
        R = self.R()
        if not sh or not ref.get('rig') or not R:
            return None
        key = ('sheet', ex, json.dumps(sh, sort_keys=True, default=str), R['ppl'])
        got = self._kept(key)
        if got is not None:
            return got
        rgb = self.rgba(sh['image'])[..., :3]
        rig_alpha = self.rgba(os.path.join(_path(ref['rig']), 'base.png'))[..., 3]
        ppl = self.memo(sheetqa.sheet_ppl, rgb, sh['front_figure'], rig_alpha, R['ppl'])
        D = self.memo(sheetqa.measure_sheet, rgb, {k: tuple(v) for k, v in sh['heads'].items()}, ex, ppl=ppl)
        return self._keep(key, (D, ppl), [_path(sh['image']), os.path.join(_path(ref['rig']), 'base.png')])

    def eye_ppl(self):
        """the eye design's px per L: the generated eye sheet's own, else the design rig's; None without either."""
        if self.ref().get('eyes_sheet'):
            self.eye_layers()
            return self._m['eye_ppl'][0]
        R = self.R()
        return R['ppl'] if R else None

    def eye_layers(self):
        """the design rig's eye layers measured: {our side: (rgba, eyeqa.measure)} (the rig's eye_L is on the picture's
        left: our eye at -x, 'R')."""
        from . import eyeqa
        ref = self.ref()
        gen = ref.get('eyes_sheet')
        if gen:
            # a generated head sheet's front eyes (the manifest's sheets.eyes), at the sheet's own resolution
            from . import refcheck
            key = ('eyes', 'gen', gen['image'], self.B.assembly['eye_knobs']['x'], refcheck.EYE_BOX)
            got = self._kept(key)
            if got is not None:
                return got
            crops, own = self.memo(refcheck.eye_design, self.rgba(gen['image'])[..., :3],
                                   self.B.assembly['eye_knobs']['x'], gen.get('facing', -1), refcheck.FACE_PPL,
                                   refcheck.EYE_BOX)
            self._m['eye_ppl'] = (own, [])
            return self._keep(key, {side: (px, self.memo(eyeqa.measure, px, own)) for side, px in crops.items()},
                              [_path(gen['image'])])
        R = self.R()
        out = {}
        if not ref.get('rig') or not R:
            return out
        key = ('eyes', ref['rig'], R['ppl'])
        got = self._kept(key)
        if got is not None:
            return got
        files = []
        for side, layer in (('R', 'eye_L'), ('L', 'eye_R')):
            p = os.path.join(_path(ref['rig']), 'build', layer + '.png')
            if os.path.exists(p):
                px = self.rgba(p)
                files.append(p)
                out[side] = (px, self.memo(eyeqa.measure, px, R['ppl']))
        return self._keep(key, out, files)


def _scale_caution(ctx):
    """a caution when the sheet's two scales disagree (the rig-matched figure height against the small eye spacing)."""
    if ctx.get('ppl_eyes'):
        d = ctx['ppl_eyes'] / ctx['ppl'] - 1
        if abs(d) > 0.03:
            return 'scale: the sheet\'s eye spacing reads %+.1f%% against its figure height (used); lengths far from the ' \
                   'eyes carry it (%.2f L at the feet)' % (100 * d, abs(d) * 5.2)
    return None


# --------------------------------------------------------------------------------------------------- the bundle's meshes
def _cls_by_names(o, table, default):
    """a class per material slot of an object, by the material's base name."""
    names = [(m or '').split('.')[0] for m in o.materials]
    return np.array([table.get(n, default) for n in names] or [default])


def _visible(B, groups):
    return [o for o in B.objects(groups=groups) if o.has('eval')]


def iris_centres(B):
    """each iris plate's evaluated vertices' mean (world), in the bundle's eye order."""
    return [o.V('eval').mean(0) for o in B.objects(groups=('eye',), parts=('iris',), visible=False)]


def sheet_meshes(B):
    """sheetqa.measure_ours' inputs from a bundle: every surface but the hair as (V, tris, sheet class), the hair and
    accessories as covers, the iris centres."""
    from . import sheetqa
    CL = sheetqa.CLASS
    sk = B.skin()
    V, T, tm, _ = sk.mesh('eval')
    by = _cls_by_names(sk, {'skin': CL['skin'], 'face_skin': CL['skin'], 'cavity': CL['line'], 'eyeline': CL['line']},
                       CL['other'])
    meshes = [(V, T, by[tm])]
    part_cls = {'iris': CL['iris'], 'lash': CL['line'], 'brow': CL['line'], 'sclera': CL['other']}
    for E in B.assembly['eyes']:
        tag = 'L' if E['side'] > 0 else 'R'
        for k, c in part_cls.items():
            o = B.part(k, tag)
            if o is not None:
                v, t, _, _ = o.mesh('eval')
                meshes.append((v, t, np.full(len(t), c)))
    for o in B.objects(groups=('mouth',), visible=False):
        v, t, _, _ = o.mesh('eval')
        meshes.append((v, t, np.full(len(t), CL['line'] if 'line' in o.part else CL['other'])))
    covers = []
    for group, c, dst in (('hair', CL['hair'], covers), ('accessory', CL['other'], covers), ('garment', CL['other'], meshes)):
        for o in _visible(B, (group,)):
            v, t, _, _ = o.mesh('eval')
            dst.append((v, t, np.full(len(t), c)))
    return meshes, covers, iris_centres(B)


def face_meshes(B, covers=True):
    """faceqa.measure's `ours` and landmarks from a bundle: [(V, tris, is skin, part of the face)], dict(L, eye_z, centre,
    mouth_z, nose_z, brow_z)."""
    As = B.assembly
    L = As['L']
    sk = B.skin()
    V, T, tm, _ = sk.mesh('eval')
    skin_slots = [i for i, n in enumerate(sk.materials) if n in ('skin', 'face_skin')]
    ours = [(V, T, np.isin(tm, skin_slots), True)]
    face_obs = [o for o in B.objects(groups=('eye',)) if o.part in ('sclera', 'iris', 'lash', 'brow')]
    face_obs += B.objects(groups=('mouth',), visible=False)
    for o in face_obs:
        v, t, _, _ = o.mesh('eval')
        ours.append((v, t, np.zeros(len(t), bool), True))
    if covers:
        for o in _visible(B, ('hair', 'accessory', 'garment')):
            v, t, _, _ = o.mesh('eval')
            ours.append((v, t, np.zeros(len(t), bool), False))
    ez = float(np.mean([E['c'][1] for E in As['eyes']]))
    Vb = sk.V('assembly')
    mid = (np.abs(Vb[:, 0]) < 0.01 * L) & (Vb[:, 2] < ez - 0.05 * L) & (Vb[:, 2] > ez - 0.25 * L)
    lm = dict(L=L, eye_z=ez, centre=list(As['centre']), mouth_z=float(As['mouth']['c'][1]))
    if mid.any():
        lm['nose_z'] = float(Vb[mid][np.argmin(Vb[mid][:, 1]), 2])
    brows = B.objects(groups=('eye',), parts=('brow',), visible=False)
    if brows:
        lm['brow_z'] = float(np.mean([o.V('eval')[:, 2].mean() for o in brows]))
    return ours, lm


def poly_colours(B, o, pmat, puv, variant='eval'):
    """per polygon: the sRGB lit and shade colours its material renders unlit (a texture sampled at the polygon's UV
    centre and multiplied in) and the texture's alpha there (1 without one). -> (lit (nf, 3), shade (nf, 3), alpha)."""
    nf = len(pmat)
    lit, shd, alpha = np.full((nf, 3), 0.5), np.full((nf, 3), 0.5), np.ones(nf)
    for mi in np.unique(pmat):
        sel = pmat == mi
        _, m = o.material(int(mi))
        if m is None:
            continue
        if m.get('lit') is not None:
            lit[sel], shd[sel] = m['lit'], m['shade']
        if m.get('image') and np.isfinite(puv[sel]).all():
            px = B.image_raw(m['image'])
            h, w = px.shape[:2]
            uv = np.clip(puv[sel], 0, 1 - 1e-6)
            tx = px[(uv[:, 1] * h).astype(int), (uv[:, 0] * w).astype(int)]
            lit[sel] = lit[sel] * tx[:, :3]; shd[sel] = shd[sel] * tx[:, :3]; alpha[sel] = tx[:, 3]
    return lit, shd, alpha


def _tri_area(V, T):
    return 0.5 * np.linalg.norm(np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]]), axis=1)


def scene_classes(B):
    """every visible surface of the character as triangles with a model-sheet class each (charkit.bodyqa.CLASS), by
    object: the skin (its garment mask on: what the clothes hide stays hidden) by material (skin, the mouth's cavity and
    the eye line as line), the eye plates (iris where its texture is opaque, the sclera white), lashes and brows as line,
    the teeth white, the hair, accessories and garments by their colour family (an orange accessory sits in the hair).
    -> ([(V, T, labels)], {class: (lit (n, 3), shade (n, 3), area (n,))}) (the colours per class for the palette).
    Made once per bundle (the body, the palette and the pieces read it)."""
    return B.memo('scene_classes', lambda: _scene_classes(B))[:2]


def scene_objects(B):
    """scene_classes' meshes with the name of the object each came from -> ([(V, T, labels)], [name])."""
    got = B.memo('scene_classes', lambda: _scene_classes(B))
    return got[0], got[2]


def _scene_classes(B):
    from . import bodyqa
    CL = bodyqa.CLASS
    meshes, cols, names = [], {}, []

    def put(o, labels_fn, variant='eval'):
        V, T, _, poly = o.mesh(variant)
        if not len(T):
            return
        pmat = o.a(variant, 'pmat').astype(np.int64)
        lit, shd, alpha = poly_colours(B, o, pmat, o.puv(variant))
        lab = labels_fn(pmat[poly], lit[poly], alpha[poly])
        keep = lab >= 0
        T, lab, poly = T[keep], lab[keep], poly[keep]
        meshes.append((V, T, lab))
        names.append(o.name)
        area = _tri_area(V, T)
        for c in np.unique(lab):
            s = lab == c
            cols.setdefault(int(c), []).append((lit[poly][s], shd[poly][s], area[s]))
    sk = B.skin()
    by = _cls_by_names(sk, {'skin': CL['skin'], 'face_skin': CL['skin'], 'cavity': CL['line'], 'eyeline': CL['line']},
                       CL['other'])
    put(sk, lambda mi, c, a: by[mi], 'masked')
    for E in B.assembly['eyes']:
        tag = 'L' if E['side'] > 0 else 'R'
        for k, c_ in (('iris', CL['iris']), ('sclera', CL['white']), ('lash', CL['line']), ('brow', CL['line'])):
            o = B.part(k, tag)
            if o is not None:
                put(o, lambda mi, c, a, c_=c_, k=k: np.where(a >= 0.5, c_, -1) if k == 'iris' else np.full(len(mi), c_))
    for o in B.objects(groups=('mouth',), visible=False):
        c_ = CL['white'] if o.part == 'teeth' else CL['line'] if 'line' in o.part else CL['other']
        put(o, lambda mi, c, a, c_=c_: np.full(len(mi), c_))
    for o in _visible(B, ('hair',)):
        put(o, lambda mi, c, a: np.full(len(mi), CL['hair']))
    for o in _visible(B, ('accessory',)):
        put(o, lambda mi, c, a: np.where(bodyqa.family(c) == CL['orange'], CL['hair'], bodyqa.family(c)))
    for o in _visible(B, ('garment',)):
        put(o, lambda mi, c, a: bodyqa.family(c))
    return meshes, {c: tuple(np.concatenate([r[i] for r in rows]) for i in range(3)) for c, rows in cols.items()}, names


def expression_data(B):
    """the head's parts for charkit.exprqa: the base meshes as posed (armature only: vertices match the shape keys) with
    a class per triangle and each expression key's world offsets (sparse). Only the skin's front head faces are kept;
    no hair (the features are measured, the drawing's brows only where its fringe shows them).
    -> dict(parts [(name, V, T, labels, {key: (idx, D)})], eye_z, L)."""
    from . import exprqa
    CL = exprqa.CLASS
    As = B.assembly
    L = As['L']; c = np.asarray(As['centre'], float)
    parts = []

    def put(name, o, labels_fn, keep_fn=None, skin=False):
        V, T, tm, poly = o.mesh('base')
        pmat = o.a('base', 'pmat').astype(np.int64)
        _, _, alpha = poly_colours(B, o, pmat, o.puv('base'))
        lab = labels_fn(pmat[poly], alpha[poly])
        ok = lab >= 0
        if keep_fn is not None:
            ok &= keep_fn(V[T].mean(1))
        T, lab = T[ok], lab[ok]
        keys = {}
        for kn, (idx, D) in o.keys('base').items():
            if kn.startswith(('eye_', 'mouth_', 'brow_')) and not kn.endswith(('_L', '_R')):
                big = np.abs(D).max(1) > 1e-7
                keys[kn] = (idx[big], D[big])
        parts.append((name, V, T, lab, keys))
    sk = B.skin()
    by = _cls_by_names(sk, {'skin': CL['skin'], 'face_skin': CL['skin'], 'cavity': CL['mouth'], 'eyeline': CL['line']}, -1)
    head = lambda P: (P[:, 2] > c[2] - 0.85 * L) & (P[:, 2] < c[2] + 0.55 * L) & (P[:, 1] < c[1] + 0.1 * L)
    put('skin', sk, lambda mi, a: by[np.minimum(mi, len(by) - 1)], head)
    for E in As['eyes']:
        tag = 'L' if E['side'] > 0 else 'R'
        for k, cl in (('iris', CL['iris']), ('sclera', CL['white']), ('lash', CL['line']), ('brow', CL['brow'])):
            o = B.part(k, tag)
            if o is not None and o.has('base'):
                put(o.name, o, lambda mi, a, cl=cl, k=k: np.where(a >= 0.5, cl, -1) if k == 'iris' else np.full(len(mi), cl))
    for o in B.objects(groups=('mouth',), visible=False):
        if o.has('base'):
            cl = CL['white'] if o.part == 'teeth' else CL['tongue'] if o.part == 'tongue' else CL['line']
            put(o.part, o, lambda mi, a, cl=cl: np.full(len(mi), cl))
    iw = iris_centres(B)
    return dict(parts=parts, eye_z=float(np.mean([w[2] for w in iw])), L=L)


# --------------------------------------------------------------------------------------------------- eyes
def _blur(img, s):
    """a Gaussian blur (sigma s pixels) of an (H, W, c) image, edges extended."""
    from scipy.ndimage import gaussian_filter1d
    out = gaussian_filter1d(np.asarray(img, float), s, axis=0, mode='nearest', truncate=3.0)
    return gaussian_filter1d(out, s, axis=1, mode='nearest', truncate=3.0)


def _blur_tex(tex, sigma):
    """a Gaussian blur of a texture (sigma in texels), premultiplied by its alpha."""
    if sigma < 0.3:
        return tex
    a = tex[..., 3:4]
    tmp = _blur(np.concatenate([tex[..., :3] * a, a], -1), sigma)
    al = tmp[..., 3:4]
    return np.concatenate([np.where(al > 1e-6, tmp[..., :3] / np.maximum(al, 1e-6), tex[..., :3]), al], -1)


def _blur_down(img, ss, sigma):
    """a Gaussian pixel filter (sigma in output pixels) read at each output pixel's centre: (H ss, W ss, c) -> (H, W, c)
    (an even ss reads between the two middle subpixels)."""
    tmp = _blur(img, sigma * ss)
    if ss % 2:
        return tmp[ss // 2::ss, ss // 2::ss]
    h = ss // 2
    tmp = 0.5 * (tmp[h - 1::ss] + tmp[h::ss])
    return 0.5 * (tmp[:, h - 1::ss] + tmp[:, h::ss])


def _sample(tex, uv):
    """bilinear texture lookup (tex (n, n, c), row 0 = top = v 1) at uv (m, 2); outside [0, 1] -> 0 (the plates' CLIP)."""
    n = tex.shape[0]
    x = uv[:, 0] * n - 0.5; y = (1 - uv[:, 1]) * n - 0.5
    x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int)
    fx, fy = (x - x0)[:, None], (y - y0)[:, None]

    def at(yy, xx):
        return tex[np.clip(yy, 0, n - 1), np.clip(xx, 0, n - 1)]
    out = (at(y0, x0) * (1 - fx) * (1 - fy) + at(y0, x0 + 1) * fx * (1 - fy) + at(y0 + 1, x0) * (1 - fx) * fy
           + at(y0 + 1, x0 + 1) * fx * fy)
    inside = (uv[:, 0] >= 0) & (uv[:, 0] <= 1) & (uv[:, 1] >= 0) & (uv[:, 1] <= 1)
    return np.where(inside[:, None], out, 0.0)


def _flat_tone(m, default=(0.5, 0.5, 0.5)):
    return np.array(m['lit'] if m and m.get('lit') is not None else default, float)


def render_surfaces(B, o, variant):
    """an object as its render draws it: the surface pulled in by its outline (V + shrink) with its own material slots,
    and the hull on the original surface (flipped, back-face culled, the hull's slot) -> [(V, T, slot per tri, cull
    per tri, tris' corner loops, is hull)]."""
    V, T, tm, poly = o.mesh(variant)
    _, _, Tl = o.tris(variant)
    cull = np.array([bool((o.material(int(s))[1] or {}).get('cull')) for s in range(max(1, len(o.materials)))])
    sh = o.a(variant, 'shrink')
    out = [((V + sh) if sh is not None else V, T, tm, cull[np.minimum(tm, len(cull) - 1)], Tl, False)]
    if sh is not None and o.outline:
        slot = int(o.outline['slot'])
        hc = bool((o.material(slot)[1] or {}).get('cull', True))
        out.append((V, T[:, ::-1], np.full(len(T), slot), np.full(len(T), hc), Tl[:, ::-1], True))
    return out


def eye_image(B, side, ppl, ss=EYE_SS, size=EYE_SIZE, az=0.0):
    """one eye rendered as the build rendered it (head-on, orthographic, `size` L square round the eye centre at the
    rig's scale ppl; the skin at the render's subdivision level, pulled in by its outline with the hull on the original
    surface, and that eye's white, iris and lashes; no hair, no brows): the skin and lashes in their materials' flat
    tones, the plates by their textures at their UVs (the iris over the white by its alpha), supersampled and filtered
    like the renderer's pixel filter. az: seen from that azimuth instead (charkit.faceqa.view: 35 a three-quarter, 90 the
    profile), the window round the iris's centre as that view projects it. -> RGBA floats (n, n, 4), row 0 = top."""
    from .geom import raster
    As = B.assembly; L = As['L']
    E = next(E for E in As['eyes'] if (E['side'] > 0) == (side == 'L'))
    org = (E['c'][0], E['c'][1])
    if az:
        from .faceqa import view
        ic = next(c for c in iris_centres(B) if (c[0] > 0) == (side == 'L'))
        org = (float(view(np.asarray([ic], float), az)[0][0]), E['c'][1])
    n = int(round(size * ppl))
    pix = size * L / n / ss
    N = n * ss
    win = dict(x=size * L / 2, top=size * L / 2, bottom=-size * L / 2)
    sk = B.skin()
    items = []                          # (V, T, labels, cull), and what each is
    kinds = []
    for V, T, tm, cull, Tl, hull in render_surfaces(B, sk, 'render_eye_' + side):
        items.append((V, T, tm, cull)); kinds.append(('skin_hull' if hull else 'skin', sk, Tl))
    for part in ('sclera', 'iris', 'lash'):
        o = B.part(part, side)
        if o is None:
            continue
        V, T, tm, _ = o.mesh('eval')
        items.append((V, T, tm)); kinds.append((part, o, o.tris('eval')[2]))
    zb, lab, mi, ti, bc = raster.window_zbuffer(items, az, org, 1.0, pix, win, ids=True)
    rgb = np.zeros((N, N, 3)); al = np.zeros((N, N))
    for k, (kind, o, Tl) in enumerate(kinds):
        m = mi == k
        if not m.any():
            continue
        if kind in ('skin', 'skin_hull', 'lash'):
            slots = lab[m]
            tone = np.array([_flat_tone(o.material(int(s))[1], (1.0, 0.9, 0.86)) for s in range(max(1, len(o.materials)))])
            rgb[m] = tone[np.minimum(slots, len(tone) - 1)]
            al[m] = 1
    # the plates: the sclera's texture, the iris's over it by its alpha (the iris plate lies just in front)
    tex = {}
    for part in ('sclera', 'iris'):
        o = B.part(part, side)
        if o is None:
            continue
        _, mat = o.material(0)
        img = mat.get('image') if mat else None
        if img:
            t = B.image(img)
            if TEX_BLUR:                          # the renderer's mipmapped lookup: a texel footprint per pixel
                tpp = t.shape[0] / (As['eye_knobs']['width'] * L / (size * L / n))
                t = _blur_tex(t, TEX_BLUR * tpp)
            tex[part] = t
    for k, (kind, o, Tl) in enumerate(kinds):
        if kind not in ('sclera', 'iris') or kind not in tex:
            continue
        m = mi == k
        if not m.any():
            continue
        luv = o.a('eval', 'luv')
        tl = Tl[ti[m]]
        w = bc[m]
        u = luv[tl[:, 0]] * w[:, 0:1] + luv[tl[:, 1]] * w[:, 1:2] + luv[tl[:, 2]] * w[:, 2:3]
        s_rgb = _sample(tex['sclera'], u)[:, :3] if 'sclera' in tex else np.ones((len(u), 3))
        if kind == 'sclera':
            rgb[m] = s_rgb
        else:
            ci = _sample(tex['iris'], u)
            rgb[m] = ci[:, :3] * ci[:, 3:4] + s_rgb * (1 - ci[:, 3:4])
        al[m] = 1
    img = _blur_down(np.concatenate([rgb * al[..., None], al[..., None]], -1), ss, EYE_FILTER)
    a = img[..., 3:4]
    return np.concatenate([np.where(a > 1e-6, img[..., :3] / np.maximum(a, 1e-6), 0), a], -1)


def eyes(B, design, out=None, ss=EYE_SS):
    """our eyes against the eye design (the generated head sheet's front eyes, or the design rig's eye layers;
    charkit.eyeqa), measured the same way at its scale -> (table, checks)."""
    from . import eyeqa
    layers = design.eye_layers()
    ppl = design.eye_ppl()
    if not layers or not ppl:
        return None, {'eye': {'status': 'SKIPPED', 'why': 'no eye design (spec.ref.eyes_sheet, or a rig with ref_measure.json)'}}
    table, checks, pics = {}, {}, []
    for side_name in ('R', 'L'):
        if side_name not in layers or not B.skin().has('render_eye_' + side_name):
            continue
        ours_px = eye_image(B, side_name, ppl, ss)
        des_px, md = layers[side_name]
        mo = eyeqa.measure(ours_px, ppl)
        table[side_name] = {'ours': {k: v for k, v in mo.items() if not k.startswith('_')},
                            'design': {k: v for k, v in md.items() if not k.startswith('_')}}
        for k, v in eyeqa.compare(mo, md).items():
            prev = checks.get(k)
            if prev is None or STATUS.index(v['status']) > STATUS.index(prev['status']):
                checks[k] = dict(v, eye=side_name)
        pics.append(eyeqa.picture(ours_px, des_px, mo, md))
    if out and pics:
        Hm = max(p.shape[0] for p in pics)
        _save_rgb(os.path.join(out, 'qa_eyes.png'),
                  np.concatenate([np.pad(p, ((0, Hm - p.shape[0]), (0, 12), (0, 0)), constant_values=1.0) for p in pics], 1))
    return table, checks


# --------------------------------------------------------------------------------------------------- model sheet
def sheet_measure(B, design, covers=True):
    """the model sheet's face measures, ours and the design's -> (O, D, ppl, az3, checks) or None (no sheet)."""
    from . import sheetqa
    got = design.sheet_measures()
    if got is None:
        return None
    D, ppl = got
    az3 = D.get('az_three_quarter', 35.0)
    meshes, cov, irc = sheet_meshes(B)
    O = sheetqa.measure_ours(meshes, cov if covers else [], irc, B.assembly['centre'], B.assembly['L'], ppl, az3)
    C = sheetqa.compare(O, D)
    if covers:
        C.update(sheetqa.shown(O, D))
    return O, D, ppl, az3, C


def sheet(B, design, out=None, covers=True):
    """our face against the design's model sheet (charkit.sheetqa): the sheet measured at its scale (from the rig's
    front figure), ours z-buffered in class labels at the same scale and angles. -> (table, checks)."""
    from . import sheetqa
    got = sheet_measure(B, design, covers)
    if got is None:
        return None, {'sheet': {'status': 'SKIPPED', 'why': 'no spec.ref.sheet / rig / ref_measure.json'}}
    O, D, ppl, az3, C = got
    if out:
        _save_rgb(os.path.join(out, 'qa_sheet.png'), sheetqa.picture(O, D))
    strip = lambda M: {k: v for k, v in M.items() if not isinstance(v, np.ndarray) and k not in ('face', 'lab', 'z', 'lead')}
    table = {'ppl': ppl, 'az_three_quarter': az3, 'design': {v: strip(D[v]) for v in ('front', 'three_quarter', 'profile') if v in D},
             'ours': {v: strip(O[v]) for v in O}}
    return table, C


def sheet_expressions(B, design, out=None):
    """the sheet's expression heads against the kit's expression library (charkit.exprqa) -> (table, checks)."""
    from . import exprqa
    ctx = design.expression_sheet()
    if 'why' in ctx:
        return None, {'expr': {'status': 'SKIPPED', 'why': ctx['why']}}
    if not ctx['D']['expressions']:
        return None, {'expr': {'status': 'SKIPPED', 'why': 'no expression heads found on the sheet'}}
    table, C, pic = exprqa.sheet_run(expression_data(B), ctx['rgb'], ctx['D'], ctx['eye_x'])
    table['source'] = os.path.relpath(_path(ctx['source']), ROOT) if ctx.get('source') else None
    for c in C.values():
        c.setdefault('against', table['source'])
    if out:
        _save_rgb(os.path.join(out, 'qa_sheet_expr.png'), pic)
    return table, C


def sheet_body(B, design, out=None):
    """the whole character against the design's full figures (charkit.bodyqa): front, three-quarter, profile, back, each
    z-buffered at the sheet's scale from the same azimuth with a class per triangle, aligned on the eyes. -> (table,
    checks)."""
    from . import bodyqa
    ctx = design.sheet_context()
    if 'why' in ctx:
        return None, {'body': {'status': 'SKIPPED', 'why': ctx['why']}}
    meshes, _ = scene_classes(B)
    As = B.assembly
    iw = np.array(iris_centres(B))
    dv = design.design_views()
    labels = bodyqa.zbuffer_views(meshes, ctx['az3'], iw, As['centre'], As['L'], ctx['ppl'], list(dv))
    table, C, views = bodyqa.evaluate(labels, dv, _scale_caution(ctx))
    table.update(ppl=round(ctx['ppl'], 2), az=bodyqa.azimuths(ctx['az3']))
    for v in bodyqa.AZ:
        if v not in dv:
            C[v] = {'status': 'SKIPPED', 'why': 'no %s figure on the sheet' % v}
    if views and out:
        _save_rgb(os.path.join(out, 'qa_sheet_body.png'), bodyqa.picture(views))
    return table, C


HAIR_FAMILIES = ('bangs', 'side_locks', 'upper_back', 'lower_back', 'buns', 'ahoge', 'flyaways')   # charkit.hairlayers'
HAIR_PIECE_FAMILY = {'bangs': 'bangs', 'side_lock_L': 'side_locks', 'side_lock_R': 'side_locks', 'upper_back': 'upper_back',
                     'lower_back': 'lower_back', 'bun_L': 'buns', 'bun_R': 'buns', 'ahoge': 'ahoge', 'flyaways': 'flyaways'}
HAIR_GRADED = ('bangs', 'side_locks', 'upper_back', 'lower_back', 'buns')    # the ahoge and flyaways: INFO (a few pixels)
HAIR_IOU = (0.6, 0.4)          # a family's IoU pooled over the views against the hair layers: pass at, warn at (their boundaries are a
                               # transfer from another generation of the design: charkit.hairlayers' cautions)
HAIR_BUN_TOL = 0.012         # L: an outline pixel within this of the other bun outline agrees (a tight tolerance: a blob
                             # filled out to the drawn block's outline still misses its corners)
HAIR_BUN_OUTLINE = (0.7, 0.5)  # the buns' outline agreement (bodymeasure.outline_f) pooled over the views: pass at, warn at
HAIR_TIP_PROM = 0.03         # L: how far a lock's tip must hang below its neighbours to count (hair_tips)
HAIR_FRINGE = (0.03, 0.06)     # L: the fringe's lowest point over each eye against the drawing's: pass within, warn within
HAIR_PENETRATION = (0.004, 0.012)   # L: the deepest hair vertex inside the skin
HAIR_FOLDS = (0, 40)           # edges folded back sharply (their faces' normals over 110 degrees apart), all pieces


def hair_layers_masks(B, design):
    """the produced hair_layers masks (charkit.hairlayers; VIEW__FAMILY on the design grids) or None (none made: the QA
    builds nothing)."""
    from . import manifest
    ref = B.spec.get('ref') if isinstance(B.spec.get('ref'), dict) else {}
    if not ref.get('manifest'):
        return None
    r = manifest.load(ref['manifest'])['references'].get('hair_layers')
    if not r:
        return None
    path = _path(r['path'])
    if not os.path.exists(path):
        return None
    design._rec(path)
    Z = np.load(path)
    return {k: Z[k] for k in Z.files}


def hair_pieces_report(B, design):
    """the hair pieces' build report (the spec's hair.shape.pieces: pieces.json) or None."""
    p = ((B.spec.get('hair') or {}).get('shape') or {}).get('pieces')
    if not p:
        return None
    path = os.path.join(_path(p), 'pieces.json')
    if not os.path.exists(path):
        return None
    design._rec(path)
    return json.load(open(path))


def _fold_edges(V, T, cos_max=-0.34):
    """edges whose two faces' normals are more than ~110 degrees apart (cos below cos_max)."""
    if not len(T):
        return 0
    fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    fn /= np.linalg.norm(fn, axis=1, keepdims=True) + 1e-18
    E = np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]])
    f = np.tile(np.arange(len(T)), 3)
    key = np.sort(E, 1)
    o = np.lexsort((key[:, 1], key[:, 0]))
    key, f = key[o], f[o]
    same = np.all(key[1:] == key[:-1], axis=1)
    a, b = f[:-1][same], f[1:][same]
    return int((np.einsum('ij,ij->i', fn[a], fn[b]) < cos_max).sum())


def silhouette_corners(mask, ppl, tol=0.02, angle=35.0):
    """the corners of a mask's outlines: each outline simplified to a polygon within tol L (skimage's
    approximate_polygon) and its vertices turning by more than `angle` degrees counted: a drawn block shows its corners,
    a smooth blob none."""
    from skimage import measure
    n = 0
    for c in measure.find_contours(mask.astype(float), 0.5):
        if len(c) < 12:
            continue
        p = measure.approximate_polygon(c, tolerance=tol * ppl)
        if len(p) < 4:
            continue
        p = p[:-1] if np.allclose(p[0], p[-1]) else p
        a, b = np.roll(p, 1, 0) - p, np.roll(p, -1, 0) - p
        cosang = np.einsum('ij,ij->i', a, b) / (np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1) + 1e-9)
        turn = 180.0 - np.degrees(np.arccos(np.clip(cosang, -1, 1)))
        n += int((turn > angle).sum())
    return n


def hair_bun_measures(labels, masks, code, ppl):
    """the buns against the drawing's buns in the front, three-quarter and profile: the outline agreement at
    HAIR_BUN_TOL (bodymeasure.outline_f, pooled over the views' outline pixels) and the silhouettes' corners, ours and
    the drawing's. -> checks hair_bun_outline, hair_bun_corners."""
    from . import bodymeasure
    agree, total, per, corners = 0.0, 0, {}, {}
    for v in ('front', 'three_quarter', 'profile'):
        m = masks.get('%s__buns' % v)
        if v not in labels or m is None or m.sum() < 40 or m.shape != labels[v][1].shape:
            continue
        ours = labels[v][1] == code
        o = bodymeasure.outline_f(ours, m, HAIR_BUN_TOL * ppl)
        npx = int(bodymeasure.outline(m).sum()) + int(bodymeasure.outline(ours).sum())
        per[v] = round(o['f'], 3)
        agree += o['f'] * npx; total += npx
        corners[v] = [silhouette_corners(ours, ppl), silhouette_corners(m, ppl)]
    if not per:
        return {}
    f = agree / max(1, total)
    return {'hair_bun_outline': {'value': round(f, 3), 'views': per, 'status': 'PASS' if f >= HAIR_BUN_OUTLINE[0] else
                                 'WARN' if f >= HAIR_BUN_OUTLINE[1] else 'FAIL'},
            'hair_bun_corners': {'value': sum(c[0] for c in corners.values()),
                                 'drawn': sum(c[1] for c in corners.values()), 'views': corners, 'status': 'INFO'}}


def hair_tips(mask, ppl, prom=None):
    """the lock tips along a hair mask's lower edge: per column its lowest hair pixel, the edge lightly smoothed, and the
    points lower than everything within 0.05 L either side by at least HAIR_TIP_PROM L counted."""
    from scipy.ndimage import gaussian_filter1d, maximum_filter1d
    prom = HAIR_TIP_PROM if prom is None else prom
    cols = np.nonzero(mask.any(0))[0]
    if len(cols) < 5:
        return 0
    low = np.full(mask.shape[1], np.nan)
    rows = np.arange(mask.shape[0])
    for c in cols:
        low[c] = rows[mask[:, c]].max()
    ok = np.isfinite(low)
    x = np.interp(np.arange(len(low)), np.nonzero(ok)[0], low[ok])
    x = gaussian_filter1d(x, 1.0)
    w = max(3, int(0.05 * ppl))
    peak = (x == maximum_filter1d(x, 2 * w + 1)) & ok
    base = -maximum_filter1d(-x, 4 * w + 1)                      # the edge's highest point near each column
    tip = peak & (x - base > prom * ppl)
    return int(((tip[1:] & ~tip[:-1]).sum()) + int(tip[0]))       # a flat tip's columns count once


def hair_pieces(B, design, out=None):
    """the hair's pieces (hair.shape.mode 'pieces': objects hair_NAME, charkit.geom.hairpieces) against the design's
    families: every visible surface z-buffered on the design's grids with each hair object labelled by its family,
    each family's IoU against the hair layers (charkit.hairlayers) in the front, profile and back; how deep the hair
    reaches inside the skin; the fringe's lowest point over each eye against the drawing's; sharp folds per piece.
    -> (table, checks hair_piece_<family>, hair_fringe_low, hair_penetration, hair_folds)."""
    objs = {o.name[5:]: o for o in _visible(B, ('hair',)) if o.name.startswith('hair_') and
            o.name[5:] in HAIR_PIECE_FAMILY}
    if not objs:
        return None, {'hair_pieces': {'status': 'SKIPPED', 'why': 'the hair is not built in pieces'}}
    hair = {n: (o.mesh('eval')[:2], o.mesh('raw' if o.has('raw') else 'eval')[:2]) for n, o in objs.items()}
    return hair_pieces_measure(B, design, hair, out)


def hair_pieces_measure(B, design, hair, out=None):
    """hair_pieces' measures with the hair given as {piece: ((V, T) as rendered, (V, T) raw)} over the bundle's
    character (a fit's candidate pieces, measured without a Blender build)."""
    from . import bodyqa
    ctx = design.sheet_context()
    masks = hair_layers_masks(B, design)
    if 'why' in ctx or masks is None:
        return None, {'hair_pieces': {'status': 'SKIPPED', 'why': ctx.get('why') or 'no hair_layers produced'}}
    As = B.assembly
    L = As['L']
    fam_k = {f: k + 1 for k, f in enumerate(HAIR_FAMILIES)}
    BROW = 50
    meshes = []
    sk = B.skin()
    V, T = sk.mesh('masked')[:2]
    meshes.append((V, T, np.zeros(len(T), int)))
    for o in B.objects(groups=('eye', 'mouth', 'accessory', 'garment')):
        if o.has('eval'):
            V, T = o.mesh('eval')[:2]
            meshes.append((V, T, np.full(len(T), BROW if o.part == 'brow' else 0)))
    for name, (ev, _) in hair.items():
        V, T = ev
        meshes.append((V, T, np.full(len(T), fam_k[HAIR_PIECE_FAMILY[name]])))
    iw = np.array(iris_centres(B))
    dv = design.design_views()
    views = [v for v in ('front', 'profile', 'back', 'three_quarter') if v in dv]
    labels = bodyqa.zbuffer_views(meshes, ctx['az3'], iw, As['centre'], L, ctx['ppl'], views)
    table = {'iou': {}, 'pixels': {}}
    C = {}
    for f in HAIR_FAMILIES:
        per = {}
        for v in ('front', 'profile', 'back'):
            m = masks.get('%s__%s' % (v, f))
            if v not in labels or m is None or m.sum() < 20:
                continue
            ours = labels[v][1] == fam_k[f]
            if ours.shape != m.shape:
                continue
            per[v] = round(float((ours & m).sum() / max(1, (ours | m).sum())), 4)
            table['pixels'].setdefault(f, {})[v] = [int(ours.sum()), int(m.sum())]
        if not per:
            continue
        table['iou'][f] = per
        px = table['pixels'][f]
        inter = sum((labels[v][1] == fam_k[f]).__and__(masks['%s__%s' % (v, f)]).sum() for v in per)
        union = sum((labels[v][1] == fam_k[f]).__or__(masks['%s__%s' % (v, f)]).sum() for v in per)
        pooled = float(inter / max(1, union))                      # over the views: a family a view barely shows
        C['hair_piece_' + f] = {'value': round(pooled, 3), 'views': per, 'status': (   # doesn't decide it alone
            'PASS' if pooled >= HAIR_IOU[0] else 'WARN' if pooled >= HAIR_IOU[1] else 'FAIL') if f in HAIR_GRADED else 'INFO'}
    # the fringe's lowest point over each eye (columns within 0.1 L of it), ours and the drawing's, in the front view
    if 'front' in labels and masks.get('front__bangs') is not None:
        lab = labels['front'][1]
        ppl = ctx['ppl']
        W = bodyqa.WIN
        H_, W_ = lab.shape
        zrow = W['top'] - (np.arange(H_) + 0.5) / ppl
        ucol = (np.arange(W_) + 0.5) / ppl - W['x']
        ex = As['eye_knobs']['x'] if 'eye_knobs' in As else 0.168
        d, lows = [], {}
        for side, sx in (('R', -1), ('L', 1)):                     # (her right shows on the picture's left)
            cols = np.abs(ucol - sx * ex) < 0.1
            ours = lab[:, cols] == fam_k['bangs']
            drawn = masks['front__bangs'][:, cols]
            zo = zrow[np.nonzero(ours.any(1))[0].max()] if ours.any() else None
            zd = zrow[np.nonzero(drawn.any(1))[0].max()] if drawn.any() else None
            lows[side] = [None if zo is None else round(float(zo), 4), None if zd is None else round(float(zd), 4)]
            if zo is not None and zd is not None:
                d.append(zo - zd)
        if d:
            worst = max(d, key=abs)
            C['hair_fringe_low'] = {'value': round(float(worst), 4), 'ours_drawn_L': lows, 'status': 'PASS' if abs(worst) <=
                                    HAIR_FRINGE[0] else 'WARN' if abs(worst) <= HAIR_FRINGE[1] else 'FAIL'}
            # ours: the fringe's lowest point less the brows' top in the same columns (INFO: a gap under 0 covers the brow)
            br = [zrow[np.nonzero((lab[:, np.abs(ucol - sx * ex) < 0.1] == BROW).any(1))[0].min()]
                  for sx in (-1, 1) if (lab[:, np.abs(ucol - sx * ex) < 0.1] == BROW).any()]
            if br and all(v[0] is not None for v in lows.values()):
                C['hair_fringe_gap'] = {'value': round(float(min(v[0] for v in lows.values()) - max(br)), 4),
                                        'status': 'INFO'}
    # the buns' shape (blocky or a blob): their outline against the drawing's at a tight tolerance, and their corners
    ppl = ctx['ppl']
    C.update(hair_bun_measures(labels, masks, fam_k['buns'], ppl))
    # the locks' tips along the hair's lower edge, ours against the drawing's, per view
    hair_codes = [fam_k[f] for f in HAIR_FAMILIES]
    for v in ('front', 'back'):
        if v not in labels:
            continue
        drawn = np.zeros(labels[v][1].shape, bool)
        for f in HAIR_FAMILIES:
            m = masks.get('%s__%s' % (v, f))
            if m is not None and m.shape == drawn.shape:
                drawn |= m
        ours = np.isin(labels[v][1], hair_codes)
        td, to = hair_tips(drawn, ppl), hair_tips(ours, ppl)
        C['hair_tips_' + v] = {'value': to, 'drawn': td, 'status': 'INFO'}
    # penetration: hair vertices behind the planes of the nearest skin triangles (by centroid), raw geometry (no outline)
    from scipy.spatial import cKDTree
    Vs, Ts = sk.mesh('eval')[:2]
    fn = np.cross(Vs[Ts[:, 1]] - Vs[Ts[:, 0]], Vs[Ts[:, 2]] - Vs[Ts[:, 0]])
    fn /= np.linalg.norm(fn, axis=1, keepdims=True) + 1e-18
    cen = Vs[Ts].mean(1)
    tree = cKDTree(cen)
    deepest, where, inside = 0.0, None, 0
    for name, (_, raw) in hair.items():
        V, T = raw
        dd, j = tree.query(V, 4)
        near = dd[:, 0] < 0.05 * L
        # the median over the four nearest triangles' planes: a thin feature (an ear) can put one plane on its far side
        sd = np.median(np.einsum('ikj,ikj->ik', V[near][:, None] - cen[j[near]], fn[j[near]]), axis=1) / L
        if len(sd):
            inside += int((sd < -HAIR_PENETRATION[0]).sum())
            if -sd.min() > deepest:
                deepest, where = float(-sd.min()), name
    C['hair_penetration'] = {'value': round(deepest, 4), 'piece': where, 'vertices': inside, 'status': 'PASS' if deepest <=
                             HAIR_PENETRATION[0] else 'WARN' if deepest <= HAIR_PENETRATION[1] else 'FAIL'}
    # folds: the builder's own count (it knows each face's surface: charkit.geom.hairpieces.folds) when its report is
    # there, else the sharp dihedrals
    rep_p = hair_pieces_report(B, design)
    if rep_p is not None:
        folds = {n: r.get('folds', 0) for n, r in rep_p['report']['pieces'].items()}
    else:
        folds = {name: _fold_edges(*raw) for name, (_, raw) in hair.items()}
    nf = sum(folds.values())
    C['hair_folds'] = {'value': nf, 'per_piece': folds, 'source': 'builder' if rep_p is not None else 'dihedral',
                       'status': 'PASS' if nf <= HAIR_FOLDS[0] else 'WARN' if nf <= HAIR_FOLDS[1] else 'FAIL'}
    table['pieces'] = sorted(hair)
    if out:
        pal = np.array([[1, 1, 1], [.85, .2, .2], [1, .8, .2], [.55, .3, .9], [1, .5, .7], [.2, .4, 1], [.1, .8, .7],
                        [.5, .9, .1]])
        pics = []
        for v in ('front', 'profile', 'back'):
            if v not in labels:
                continue
            lab = labels[v][1]
            ours = np.zeros(lab.shape, int)
            drawn = np.zeros(lab.shape, int)
            for f, k in fam_k.items():
                ours[lab == k] = k
                m = masks.get('%s__%s' % (v, f))
                if m is not None and m.shape == lab.shape:
                    drawn[m] = k
            rows = np.nonzero((ours > 0).any(1) | (drawn > 0).any(1))[0]
            r0, r1 = (rows.min(), rows.max() + 1) if len(rows) else (0, lab.shape[0])
            pics.append(np.concatenate([pal[drawn[r0:r1]], np.ones((r1 - r0, 6, 3)), pal[ours[r0:r1]]], 1))
        if pics:
            H = max(p.shape[0] for p in pics)
            _save_rgb(os.path.join(out, 'qa_hair_pieces.png'), np.concatenate(
                [np.pad(p, ((0, H - p.shape[0]), (0, 12), (0, 0)), constant_values=1.0) for p in pics], 1))
    return table, C


PIECE_PASS, PIECE_WARN = 0.75, 0.5     # a piece's overlap (bodymeasure.iou_tol) over its views, each weighted by how much
                                       # of it the drawing shows there; the masks reach 0.77-0.85 IoU against the sheet's
                                       # own figures, so a PASS asks for what they can show


def sheet_pieces(B, design, out=None):
    """the outfit piece by piece against the design's (the outfit's per-view piece masks, cut from the body sheet):
    every object z-buffered on the design's grids with its own index, so a piece shows only where nothing of ours is in
    front of it, as the drawing's masks do; then per piece and view the outline agreement within
    bodymeasure.OUTLINE_TOL (bodymeasure.iou_tol: the graded value is its worst view) and, in the table and the check,
    the plain IoU and the outline agreement (bodymeasure.outline_f).
    -> (table, checks <piece id> and built: the graph's pieces we build as their own objects)."""
    from . import bodyqa, bodymeasure
    ctx = design.sheet_context()
    if 'why' in ctx:
        return None, {'pieces': {'status': 'SKIPPED', 'why': ctx['why']}}
    got = bodymeasure.piece_masks(B.spec)
    if got is None:
        return None, {'pieces': {'status': 'SKIPPED', 'why': 'no outfit_masks produced for this spec'}}
    masks, graph, paths = got
    for p in paths:
        design._rec(p)
    meshes, names = scene_objects(B)
    obj = []
    for i, (V, T, _) in enumerate(meshes):
        # a two-sided object's right half (world x < 0: her right) as index + 1000 (bodymeasure.piece_views')
        obj.append((V, T, np.where(V[T].mean(1)[:, 0] >= 0, i, i + 1000)))
    dv = design.design_views()
    az = bodyqa.azimuths(ctx['az3'])
    iw = np.array(iris_centres(B))
    As = B.assembly
    labels = {v: bodyqa_zbuffer(obj, az[v], bodyqa.origin(v, az[v], iw, As['centre']), As['L'], ctx['ppl'])
              for v in dv}
    S = bodymeasure.piece_shapes(labels, names, masks, graph, B.spec, ctx['ppl'])
    C, table = grade_pieces(S), {'tol_L': bodymeasure.OUTLINE_TOL, 'pieces': S}
    table['confusion'] = {v: bodymeasure.piece_confusion(labels, names, masks, graph, B.spec, v) for v in labels}
    if out:
        _save_rgb(os.path.join(out, 'qa_sheet_pieces.png'), pieces_picture(labels, names, masks, graph, B.spec, dv))
    return table, C


PIECE3D_PASS, PIECE3D_WARN = 0.04, 0.08     # L: a piece's median reach to the design's in 3D (bodymeasure.piece_depths)


def pieces_3d(B, design, out=None):
    """the outfit piece by piece against the visual hull's pieces in 3D (the target's per-vertex pieces, carried in the
    bundle: bodymeasure.piece_depths): checks <piece id> valued by its median reach (L), with the 90th percentile, the
    excess and the height offset beside it. INFO: the hull's pieces are carved from the same drawn masks the 2D checks
    grade against, so these locate a fault (too low, too far out) rather than add a verdict; a fit reads them."""
    from . import bodymeasure
    tp = B.target_pieces()
    t = B.target()
    if tp is None or t is None:
        return None, {'pieces': {'status': 'SKIPPED', 'why': 'the target carries no per-vertex pieces'}}
    got = bodymeasure.piece_masks(B.spec)
    if got is None:
        return None, {'pieces': {'status': 'SKIPPED', 'why': 'no outfit graph beside the produced masks'}}
    graph = got[1]
    meshes, names = scene_objects(B)
    R = bodymeasure.piece_depths(meshes, names, t[0], tp[0], tp[1], graph, B.spec, B.assembly['L'])
    C = {}
    for pid, r in R.items():
        if 'reach' not in r:
            continue
        v = r['reach']
        C[pid] = dict(r, value=v, status='INFO', grade='PASS' if v <= PIECE3D_PASS else 'WARN' if v <= PIECE3D_WARN
                      else 'FAIL')
    return {'pieces': R}, C


def grade_pieces(S):
    """bodymeasure.piece_shapes' records as checks: <piece id> (its iou_tol over the views, weighted by the drawn
    piece's pixels in each: a sliver a view barely shows doesn't decide it; the worst view beside it; INFO for a piece
    no object of ours builds) and built (the drawn pieces we build as their own objects)."""
    C = {}
    built = [p for p, r in S.items() if r['views'] and r['members']]
    shown = [p for p, r in S.items() if r['views']]
    for pid in shown:
        r = S[pid]
        fs = {v: x['iou_tol'] for v, x in r['views'].items()}
        if not r['members']:
            C[pid] = {'value': None, 'status': 'INFO', 'views': fs, 'why': 'no object of ours builds it' + (
                ' (compared as part of %s)' % r['part_of'] if r['part_of'] else '')}
            continue
        w = {v: x['px'][1] for v, x in r['views'].items()}
        val = sum(fs[v] * w[v] for v in fs) / max(1, sum(w.values()))
        C[pid] = {'value': round(val, 3), 'status': 'PASS' if val >= PIECE_PASS else 'WARN' if val >= PIECE_WARN
                  else 'FAIL', 'worst': round(min(fs.values()), 3), 'views': fs,
                  'iou': {v: x['iou'] for v, x in r['views'].items()}, 'outline': {v: x['f'] for v, x in r['views'].items()}}
    C['built'] = {'value': '%d/%d' % (len(built), len(shown)), 'status': 'PASS' if len(built) == len(shown) else 'WARN',
                  'missing': sorted(set(shown) - set(built))}
    return C


def bodyqa_zbuffer(meshes, az, org, L, ppl):
    """the body checks' z-buffer (bodyqa.zbuffer_views') for one view, by label: -> the label image (-1 nothing)."""
    from . import bodyqa
    from .faceqa import zbuffer
    return zbuffer(meshes, az, org, L, 1.0 / ppl, bodyqa.WIN)[1]


def pieces_picture(labels, names, masks, graph, spec, dv):
    """per view: the drawing dimmed, each drawn piece's pixels green where our same piece covers them, red where it
    doesn't, blue where ours puts a piece the drawing doesn't have there; both outlines on top (ours white)."""
    from . import bodymeasure
    idx = {n: i for i, n in enumerate(names)}
    pm = bodymeasure.piece_map(graph, spec)
    cols = []
    for v, lab in labels.items():
        img = 0.35 * np.asarray(dv[v]['rgb'], float)
        drawn_any = np.zeros(lab.shape, bool)
        ours_any = np.zeros(lab.shape, bool)
        agree = np.zeros(lab.shape, bool)
        for pc in graph['pieces']:
            d = masks.get('%s__%s' % (v, pc['id']))
            if d is None:
                continue
            m = bodymeasure.member_mask(lab, idx, pm[pc['id']]) if pm.get(pc['id']) else np.zeros(lab.shape, bool)
            drawn_any |= d
            ours_any |= m
            agree |= d & m
        img[drawn_any & ~agree] = (0.85, 0.2, 0.2)
        img[ours_any & ~drawn_any] = (0.2, 0.35, 0.9)
        img[agree] = (0.25, 0.7, 0.3)
        img[bodymeasure.outline(ours_any)] = (1.0, 1.0, 1.0)
        cols.append(img)
    H = max(c.shape[0] for c in cols)
    return np.concatenate([np.pad(c, ((0, H - c.shape[0]), (0, 8), (0, 0)), constant_values=1.0) for c in cols], 1)


def sheet_palette(B, design, out=None):
    """the design's colours per class (the sheet's own pixels, charkit.paletteqa) against the flat tones our materials
    render unlit -> (table, checks)."""
    from . import paletteqa
    ctx = design.sheet_context()
    if 'why' in ctx:
        return None, {'palette': {'status': 'SKIPPED', 'why': ctx['why']}}
    dv = design.design_views()
    cols = scene_classes(B)[1]
    D, O = design.memo(paletteqa.extract_views, dv), paletteqa.ours(cols)
    if out:
        _save_rgb(os.path.join(out, 'qa_sheet_palette.png'), np.repeat(np.repeat(paletteqa.picture(O, D), 2, 0), 2, 1))
    hx = lambda T: {k: paletteqa._hex(v) if v is not None and not isinstance(v, (int, float)) else v for k, v in T.items()}
    table = {'design': {n: hx(t) for n, t in D.items() if t}, 'ours': {n: hx(t) for n, t in O.items()}}
    return table, paletteqa.compare(O, D)


def sheet_figures(B, design, out=None):
    """what figure detection found on the sheet (charkit.sheetqa.detect_figures) against the spec's hand-typed head boxes
    -> (table, checks); overlay qa_sheet_figures.png."""
    from . import sheetqa
    ctx = design.sheet_context()
    if 'why' in ctx:
        return None, {'figures': {'status': 'SKIPPED', 'why': ctx['why']}}
    D = ctx['D']
    if out:
        _save_rgb(os.path.join(out, 'qa_sheet_figures.png'), sheetqa.figures_picture(ctx['rgb'], D))
    C = {}
    for v, r in ctx['verify'].items():
        C['head_' + v] = {'value': r.get('off'), 'status': 'PASS' if r['ok'] else 'WARN', 'detected': r['detected'],
                          'typed': r['typed'], 'note': 'max |detected - typed| px over the head box'}
    table = {'ppl': round(D['ppl'], 2), 'facing': D['facing'],
             'figures': {v: {k: f[k] for k in ('box', 'head', 'eyes', 'eye_y', 'partial', 'bottom_L')} for v, f in D['figures'].items()},
             'expressions': [{k: e[k] for k in ('box', 'head', 'eyes', 'eye_y', 'eye_y_from', 'ppl')} for e in D['expressions']],
             'skipped': D['skipped'], 'manifest': sheetqa.manifest_figures(D)}
    C['found'] = {'value': sorted(D['figures']), 'expressions': len(D['expressions']), 'status': 'INFO'}
    return table, C


# --------------------------------------------------------------------------------------------------- face shape
def face_shape(B, design, out=None, covers=True, tcache=None):
    """our face against the generated character's (charkit.faceqa), from the bundle's meshes. -> (result, checks)."""
    from . import faceqa
    target = B.target()
    if target is None:
        return None, {'face_shape': {'status': 'SKIPPED', 'why': 'no generated shape in this build'}}
    ours, lm = face_meshes(B, covers)
    R = faceqa.measure(ours, target, lm, design.R(), tcache=tcache)
    if out:
        _save_rgb(os.path.join(out, 'qa_face_shape.png'), faceqa.overlay(R))
        _save_rgb(os.path.join(out, 'qa_face_contours.png'), faceqa.contours_image(R))
    C = faceqa.checks(R)
    return {k: v for k, v in R.items() if not k.startswith('_')}, C


# --------------------------------------------------------------------------------------------------- full-figure views
class Frame:
    """the full-figure orthographic framing round the character (the figure's height x 1.08 across FRAME's height,
    centred on the world's vertical axis): the window arguments for charkit.geom.raster.window_zbuffer, and a
    height's image row."""

    def __init__(self, zmin, zmax, res=FRAME, ss=1):
        self.zc = (zmin + zmax) / 2
        self.scale = (zmax - zmin) * 1.08
        self.res = res
        W, H = res
        self.pix = self.scale / H / ss
        self.win = dict(x=W / 2 * self.scale / H, top=self.scale / 2, bottom=-self.scale / 2)
        self.origin = (0.0, self.zc)

    def row(self, z):
        """the image row of a world height (orthographic, the long side vertical)."""
        W, H = self.res
        return int(round((0.5 - (z - self.zc) / self.scale) * H))

    def zbuffer(self, items, az, ids=False):
        from .geom import raster
        return raster.window_zbuffer(items, az, self.origin, 1.0, self.pix, self.win, ids=ids)


def figure_frame(B, ss=1):
    zr = B.assembly.get('raw_z')
    if zr is None:
        zs = np.concatenate([o.V('eval')[:, 2] for o in B.objects(visible=False) if o.has('eval')])
        zr = (float(zs.min()), float(zs.max()))
    return Frame(zr[0], zr[1], ss=ss)


def silhouette_items(B):
    """every visible surface of ours as a flat silhouette render draws it (every face, no culling): the skin with its
    garment mask on, each object's surface pulled in by its outline and the hull left on the original surface (where the
    surface curls, the pulled-in side can reach past the hull)."""
    items = []
    for o in B.objects():
        variant = 'masked' if o.group == 'skin' and o.has('masked') else 'eval'
        if o.has(variant):
            for V, T, *_ in render_surfaces(B, o, variant):
                items.append((V, T, 1))
    return items


def coverage(fr, items, az, ss=FIG_SS, sigma=FIG_FILTER):
    """a silhouette as the renderer's alpha reads it (> 0.5 after its pixel filter), from a frame built at ss."""
    m = (fr.zbuffer(items, az)[1] >= 0).astype(float)
    return _blur_down(m[..., None], ss, sigma)[..., 0] > 0.5


def shape(B, design, out=None, ref_image=None):
    """silhouette IoU against the generated shape per azimuth and height band, and the front against the reference
    image -> (views, checks)."""
    fr = figure_frame(B, ss=FIG_SS)
    items = silhouette_items(B)
    masks = {az: coverage(fr, items, az) for az in AZ}
    As = B.assembly
    chin = As['centre'][2] - As['chin']
    bands = {'hair': (chin, 99.0), 'torso': (As['waist_z'], chin), 'skirt': (As['knee_z'], As['waist_z']),
             'legs': (-99.0, As['knee_z'])}
    C, per = {}, {}
    target = B.target()
    if target is None:
        C['shape'] = {'status': 'SKIPPED', 'why': 'no generated shape in this build'}
    else:
        tv, tt, _ = target
        overlays = []
        for az in AZ:
            g = coverage(fr, [(tv, tt, 1)], az)
            o = masks[az]
            d = {'iou': round(_iou(o, g), 3)}
            for bn, (z0, z1) in bands.items():
                r0, r1 = fr.row(z1), fr.row(z0)
                r0, r1 = max(0, r0), min(o.shape[0], r1)
                if r1 > r0:
                    d['iou_' + bn] = round(_iou(o[r0:r1], g[r0:r1]), 3)
            per[az] = d
            ov = np.full(o.shape + (3,), 0.93)
            ov[o & g] = (0.55, 0.55, 0.6); ov[o & ~g] = (0.9, 0.2, 0.2); ov[g & ~o] = (0.2, 0.35, 0.95)
            overlays.append(ov)
        mean = float(np.mean([per[a]['iou'] for a in AZ]))
        hair = float(np.mean([per[a].get('iou_hair', 0) for a in AZ]))
        C['shape_iou'] = {'value': round(mean, 3), 'status': _grade('shape_iou', mean)}
        C['shape_iou_hair'] = {'value': round(hair, 3), 'status': _grade('shape_iou_hair', hair)}
        for bn in ('torso', 'skirt', 'legs'):
            C[f'shape_iou_{bn}'] = {'value': round(float(np.mean([per[a].get('iou_' + bn, 0) for a in AZ])), 3),
                                    'status': 'INFO'}
        if out:
            _save_rgb(os.path.join(out, 'qa_shape_overlay.png'), np.concatenate(overlays, 1))
    if ref_image and os.path.exists(_path(ref_image)):
        px = design.rgba(ref_image)
        ref = px[..., 3] > 0.5 if design.has_alpha(ref_image) else px[..., :3].sum(-1) < 2.8
        a, b = _bbox_norm(masks[0]), _bbox_norm(ref)
        v = _iou(a, b)
        C['ref_iou'] = {'value': round(v, 3), 'status': _grade('ref_iou', v)}
        if out:
            ov = np.full(a.shape + (3,), 0.93)
            ov[a & b] = (0.55, 0.55, 0.6); ov[a & ~b] = (0.9, 0.2, 0.2); ov[b & ~a] = (0.2, 0.35, 0.95)
            _save_rgb(os.path.join(out, 'qa_ref_overlay.png'), ov)
    else:
        C['ref_iou'] = {'status': 'SKIPPED', 'why': 'no reference image'}
    return per, C


# --------------------------------------------------------------------------------------------------- shaded views
def view_light(B, az):
    """toward the key light (world) for a view from azimuth az as the boards light it (charkit.shade.view_light on the
    bundle's look: a camera key turns with the view), or None: each material's own light (a bundle without a look)."""
    look = B.meta('look')
    if not look:
        return None
    from . import shade
    return shade.view_light(az, dict(look))


def _toon(sh, N, view_d, ldir=None):
    """toon3's linear colour and tone (0 lit .. 1 shade .. 2 deep) for shading normals N under ldir (else its own)."""
    Ld = np.asarray(ldir if ldir is not None else sh['ldir'], float)
    half = (N @ Ld) * 0.5 + 0.5

    def ramp(at):
        p0, p1 = at
        return np.clip((half - p0) / max(p1 - p0, 1e-9), 0, 1)[:, None]
    rd = ramp(sh['deep_at'])
    m1 = np.asarray(sh['deep']) * (1 - rd) + np.asarray(sh['shade']) * rd
    fl = ramp(sh['lit_at'])
    col = m1 * (1 - fl) + np.asarray(sh['lit']) * fl
    if sh.get('rim_amt'):
        f = np.abs(N @ (-np.asarray(view_d)))
        b = min(max(sh['blend'], 0.0), 0.99999)
        b = 2 * b if b < 0.5 else 0.5 / (1 - b)
        f = 1 - (f ** b if sh['blend'] != 0.5 else f)
        r0, r1 = sh['rim_from']
        rr = np.clip((f - r0) / max(r1 - r0, 1e-9), 0, 1)
        fac = (rr * sh['rim_amt'])[:, None] * fl
        col = 1 - (1 - fac * np.asarray(sh['rim'])) * (1 - col)
    return col * sh.get('strength', 1.0), (1 - fl[:, 0]) * (2 - rd[:, 0]) + fl[:, 0] * 0.0


def _face(B, o, variant, sh, N, view_d, t, w, ldir=None):
    """charkit.faceshade's material for pixels of triangles t (barycentric weights w): toon3 blended by the face mask
    with the SDF face (the threshold map at the light's angle, mirrored for light from her right; the fringe's shadow;
    the blush multiplied in) -> (linear colour, tone 0 lit .. 1 shade (.. 2 deep off the face))."""
    col, tone = _toon(sh['toon'], N, view_d, ldir)
    fuv, fm = o.a(variant, 'fuv'), o.a(variant, 'fmask')
    if fuv is None or fm is None:
        return col, tone
    Tv, _, Tl = o.tris(variant)
    uv = (fuv[Tl[t]] * w[:, :, None]).sum(1)
    mk = (fm[Tv[t]] * w).sum(1)[:, None]
    lh = np.asarray(ldir if ldir is not None else sh['ldir_head'], float)       # at rest the head's frame is the world's
    ang = np.arctan2(abs(lh[0]), -lh[1]) / np.pi
    u = 1 - uv[:, 0] if lh[0] < 0 else uv[:, 0]
    thr = _sample(B.image(sh['sdf']), np.clip(np.stack([u, uv[:, 1]], 1), 0, 1))[:, 0]
    s_ = np.clip((ang - thr + sh['soft']) / (2 * sh['soft']), 0, 1)
    if sh.get('fringe'):
        a0, a1 = sh['fringe_at']
        s_ = np.maximum(s_, np.clip((_sample(B.image(sh['fringe']), uv)[:, 0] - a0) / (a1 - a0), 0, 1))
    fc = np.asarray(sh['lit']) * (1 - s_[:, None]) + np.asarray(sh['shade']) * s_[:, None]
    if sh.get('blush'):
        bt = _sample(B.image(sh['blush']), uv)
        fc = fc * (1 - bt[:, 3:4]) + fc * _lin(bt[:, :3]) * bt[:, 3:4]
    col = col * (1 - mk) + fc * mk
    tone = tone * (1 - mk[:, 0]) + s_ * mk[:, 0]
    iw = o.a(variant, 'finkw')
    if sh.get('ink') and iw is not None:                # the drawn lines (faceshade.ink), off the neck: not shading
        it = _sample(B.image(sh['ink']), uv)
        a = it[:, 3:4] * (iw[Tv[t]] * w).sum(1)[:, None]
        col = col * (1 - a) + _lin(it[:, :3]) * a
        tone = np.where(a[:, 0] > 0.5, np.nan, tone)
    return col, tone


def _shade(B, o, m, N, view_d, ldir=None):
    """a material's linear colour for pixels with shading normals N (unit, world), as the renderer shades it: toon3's
    three tones on half-lambert N.L with its soft steps and lit-side rim (under ldir, else its own light), a flat
    emission, else its flat lit tone."""
    if m is None:
        return np.full((len(N), 3), 0.5)
    sh = m.get('shading') or {}
    if m.get('kind') == 'toon3':
        return _toon(sh, N, view_d, ldir)[0]
    if m.get('kind') == 'face':
        return _toon(sh['toon'], N, view_d, ldir)[0]
    if m.get('kind') == 'flat':
        return np.broadcast_to(np.asarray(sh['color'], float) * sh.get('strength', 1.0), (len(N), 3))
    return np.broadcast_to(_lin(_flat_tone(m)), (len(N), 3))


def surfaces(B, o, variant='eval', outline=True, paint=None):
    """an object's surfaces for draw(): render_surfaces' (with outline=False: the surface where it is, no hull), each
    as dict(o, variant, V, T, slots, cull, Tl, hull, paint (per-triangle linear RGB overriding the material, or None))."""
    if outline:
        got = render_surfaces(B, o, variant)
    else:
        V, T, tm, _ = o.mesh(variant)
        cull = np.array([bool((o.material(int(k))[1] or {}).get('cull')) for k in range(max(1, len(o.materials)))])
        got = [(V, T, tm, cull[np.minimum(tm, len(cull) - 1)], o.tris(variant)[2], False)]
    return [dict(o=o, variant=variant, V=V, T=T, slots=tm, cull=cull, Tl=Tl, hull=hull,
                 paint=paint if not hull else None) for V, T, tm, cull, Tl, hull in got]


def draw(B, surfs, az, fr, transparent=True, ss=FIG_SS, ldir=None, aux=None):
    """surfaces drawn as the renderer draws them, from azimuth az on frame fr (built at ss): back-face culling per
    material, toon materials on the render's normals (a back face shaded from its flipped normal) under the view's light
    (ldir, else the boards' for this view: view_light), the face's SDF shading, flat emissions, the world behind an
    opaque render; supersampled and filtered -> RGBA floats (H, W, 4): sRGB colour and straight alpha at 8 bits, as a
    saved PNG reads back. aux (a dict) gets the supersampled buffers: 'tone' (0 lit .. 1 shade .. 2 deep; NaN off the
    toon materials), 'mesh' (the surface index per pixel, -1 empty), 'depth'."""
    items = [(s['V'], s['T'], s['slots'], s['cull']) for s in surfs]
    zb, lab, mi, ti, bc = fr.zbuffer(items, az, ids=True)
    a = np.radians(az)
    view_d = np.array([-np.sin(a), np.cos(a), 0.0])
    if ldir is None:
        ldir = view_light(B, az)
    H, W = zb.shape
    rgb = np.zeros((H, W, 3))
    tone = np.full((H, W), np.nan) if aux is not None else None
    if not transparent:
        rgb[:] = WORLD
    for k, s in enumerate(surfs):
        m = mi == k
        if not m.any():
            continue
        o, V, T, Tl, t = s['o'], s['V'], s['T'], s['Tl'], ti[m]
        fn = np.cross(V[T[t, 1]] - V[T[t, 0]], V[T[t, 2]] - V[T[t, 0]])
        lnor = o.a(s['variant'], 'lnor')
        if s['hull']:
            N = fn
        elif lnor is not None:
            N = (lnor[Tl[t]] * bc[m][:, :, None]).sum(1)
        else:                                                   # smooth shading without stored normals: vertex normals
            if 'vn' not in s:
                from .geom.mesh import vertex_normals
                s['vn'] = vertex_normals(V, T)
            N = (s['vn'][T[t]] * bc[m][:, :, None]).sum(1)
        N = N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
        back = fn @ view_d > 0
        N[back] = -N[back]
        slots = s['slots'][t]
        col = np.zeros((len(t), 3))
        luv = o.a(s['variant'], 'luv') if not s['hull'] else None
        tn = np.full(len(t), np.nan)
        for k_ in np.unique(slots):
            sel = slots == k_
            mat = o.material(int(k_))[1]
            if mat and mat.get('kind') == 'face' and not s['hull']:
                col[sel], tn[sel] = _face(B, o, s['variant'], mat['shading'], N[sel], view_d, t[sel], bc[m][sel], ldir)
            elif mat and mat.get('kind') == 'toon3':
                col[sel], tn[sel] = _toon(mat['shading'], N[sel], view_d, ldir)
            else:
                col[sel] = _shade(B, o, mat, N[sel], view_d, ldir)
            img = mat and ((mat.get('shading') or {}).get('texture') or (mat.get('kind') == 'plate' and mat.get('image')))
            if img and luv is not None:                       # a texture multiplied in (a plate: the texture is the colour)
                tl, w = Tl[t[sel]], bc[m][sel]
                tx = _sample(B.image(img), luv[tl[:, 0]] * w[:, 0:1] + luv[tl[:, 1]] * w[:, 1:2] + luv[tl[:, 2]] * w[:, 2:3])
                c = _lin(tx[:, :3])
                col[sel] = col[sel] * c if mat.get('kind') == 'toon3' else c * tx[:, 3:4] + (1 - tx[:, 3:4])
        if s['paint'] is not None:
            p = np.asarray(s['paint'], float)[t]
            ok = np.isfinite(p[:, 0])
            col[ok] = p[ok]
        rgb[m] = col
        if tone is not None:
            tone[m] = tn
    if aux is not None:
        aux.update(tone=tone, mesh=mi, depth=zb)
    alpha = (mi >= 0).astype(float) if transparent else np.ones((H, W))
    img = _blur_down(np.concatenate([rgb * alpha[..., None], alpha[..., None]], -1), ss, FIG_FILTER)
    al = img[..., 3:4]
    out = np.concatenate([_srgb(np.where(al > 1e-6, img[..., :3] / np.maximum(al, 1e-6), 0.0)), al], -1)
    return np.floor(np.clip(out, 0, 1) * 255 + 0.5) / 255.0


def _to_shape(m, shape):
    """a boolean image at another resolution (nearest): a z-buffer's labels onto a drawn (filtered) picture's grid."""
    if m.shape == tuple(shape):
        return m
    r = (np.arange(shape[0]) * m.shape[0] // shape[0]); c = (np.arange(shape[1]) * m.shape[1] // shape[1])
    return m[r][:, c]


HAIR_NOISE_GROUPS = ('buns',)   # hair families whose tones are cut apart from the rest's (hair_noise): a block bun's
                                # large flat faces moved the shared cuts, and with them the rest's tone edges


def hair_noise_group(o):
    """an object's tone group for hair_noise: 1 the hair's mass, 2 + k for HAIR_NOISE_GROUPS[k] (a piece of that
    family: charkit.geom.hairpieces' objects hair_NAME)."""
    f = HAIR_PIECE_FAMILY.get(o.name[5:]) if o.name.startswith('hair_') else None
    return 2 + HAIR_NOISE_GROUPS.index(f) if f in HAIR_NOISE_GROUPS else 1


def tone_edges(lum, grp, min_px=50):
    """the tone edges of a picture's hair: per group (grp: 0 none, else the pixel's tone group) its pixels' luminance cut
    into three tones at the group's own 33rd and 66th percentiles, and an edge wherever two neighbouring pixels of one
    group differ in tone. -> (edge map (H, W) bool: the pixel or its left/upper neighbour, pixels counted)."""
    e = np.zeros(grp.shape, bool)
    n = 0
    for g in np.unique(grp[grp > 0]):
        a = grp == g
        n += int(a.sum())
        if a.sum() <= min_px:
            continue
        q = np.digitize(lum, np.percentile(lum[a], [33, 66]))
        e[:, 1:] |= (np.abs(np.diff(q, axis=1)) > 0) & a[:, 1:] & a[:, :-1]
        e[1:] |= (np.abs(np.diff(q, axis=0)) > 0) & a[1:] & a[:-1]
    return e, n


def hair_noise(B, design=None, out=None):
    """the hair's shading noise as a render shows it: the hair drawn with its own materials, without its outlines (a
    drawn line between two locks is not shading) and behind the rest of the character (which hides the hair's inside
    through the face), from 0, 90 and 180 degrees; each visible hair pixel's luminance cut into three tones at its
    group's 33rd and 66th percentiles (the buns apart from the rest: tone_edges), the tone edges per visible hair
    pixel."""
    hair = _visible(B, ('hair',))
    if not hair:
        return None, {}
    fr = figure_frame(B, ss=FIG_SS)
    vals, per = [], {}
    surfs, groups = [], []
    for o in hair:
        for x in surfaces(B, o, outline=False):
            surfs.append(x); groups.append(hair_noise_group(o))
    occ = [x for o in B.objects() if o.group != 'hair' and o.has('eval')
           for x in surfaces(B, o, 'masked' if o.group == 'skin' else 'eval', outline=False)]
    for az in (0, 90, 180):
        px = draw(B, surfs + occ, az, fr)
        items = [(s_['V'], s_['T'], np.full(len(s_['T']), groups[k] if k < len(surfs) else -1), s_['cull'])
                 for k, s_ in enumerate(surfs + occ)]
        lab = _to_shape(fr.zbuffer(items, az)[1], px.shape[:2])
        grp = np.where((px[..., 3] > 0.5) & (lab >= 1), lab, 0)
        lum = px[..., :3] @ np.array([0.3, 0.59, 0.11])
        e, n = tone_edges(lum, grp)
        a = grp > 0
        vals.append(float((e & a).sum()) / max(1, n))
        per[az] = round(float(vals[-1]), 4)
        if out and az == 0:
            pic = np.where(a[..., None], px[..., :3], 0.93)
            _save_rgb(os.path.join(out, 'qa_hair_front.png'), pic)
    unsupported = sorted({m for o in hair for m in o.materials if m and (B.materials.get(m) or {}).get('kind') == 'other'})
    v = float(np.mean(vals))
    C = {'hair_noise': {'value': round(v, 4), 'per_view': per, 'status': _grade('hair_noise', v, False)}}
    if unsupported:
        C['hair_noise']['caution'] = 'drawn with flat tones for %s (a material the QA does not shade)' % ', '.join(unsupported)
    return per, C


def scalp(B, design=None, out=None):
    """pixels of scalp showing through the hair: the skin's base polygons over the upper cranium and the back of the head
    drawn pure green (its outline off, as before), everything else as it renders, from 0, 90, 180 and 270 degrees; a
    pixel counts where it reads green (G > 0.9, R and B < 0.15 in the saved picture)."""
    As = B.assembly
    L = As['L']
    sk = B.skin()
    V = sk.V('assembly')
    hw = B.array('assembly/head_w')
    cz, cy = As['centre'][2], As['centre'][1]
    region = (hw > 0.5) & ((V[:, 2] > cz + 0.30 * L) | ((V[:, 1] > cy + 0.10 * L) & (V[:, 2] > cz - 0.20 * L)))
    loopv, starts, counts = sk.polys('assembly')
    allin = np.logical_and.reduceat(region[loopv], starts) if len(counts) else np.zeros(0, bool)
    parent = sk.a('masked', 'parent')
    green = allin[parent]                                            # per masked polygon
    _, poly, _ = sk.tris('masked')
    green_t = green[poly]
    objs = B.objects()
    fr = figure_frame(B, ss=FIG_SS)

    paint = np.where(green_t[:, None], np.array([[0.0, 1.0, 0.0]]), np.nan)
    surfs = surfaces(B, sk, 'masked', outline=False, paint=paint)     # (the skin's outline off, as before)
    surfs += [x for o in objs if o.group != 'skin' and o.has('eval') for x in surfaces(B, o)]
    per = {}
    f1 = figure_frame(B)
    items = [(x['V'], x['T'], np.isfinite(x['paint'][:, 0]).astype(int) if x['paint'] is not None else 0, x['cull'])
             for x in surfs]
    for az in (0, 90, 180, 270):
        # a pixel reads green only when green covers nearly all of its filter: then green is at its centre, so a view
        # with no green at any pixel centre reads 0 without the full picture
        if not (f1.zbuffer(items, az)[1] == 1).any() and not (out and az == 0):
            per[az] = 0
            continue
        px = draw(B, surfs, az, fr, transparent=False)
        g_ = (px[..., 1] > 0.9) & (px[..., 0] < 0.15) & (px[..., 2] < 0.15)
        per[az] = int(g_.sum())
        if out and az == 0:
            ov = px[..., :3].copy(); ov[g_] = (0, 1, 0)
            _save_rgb(os.path.join(out, 'qa_scalp_front.png'), ov)
    worst = max(per.values())
    return per, {'scalp_px': {'value': worst, 'per_view': per, 'status': _grade('scalp_px', worst, False)}}


def poke(B, design=None, out=None):
    """body vertices (the unmasked ones) lying just outside a garment's surface, where the garment is close: the body
    showing through it (3D, so legs seen below a skirt or an arm in front of it don't count). A short ray inward from
    the skin (along its normal, from 0.5 mm out) that meets the garment within 0.06 L is poking through."""
    garments = [o for o in B.objects(groups=('garment',), visible=False) if o.has('raw')]
    if not garments:
        return None, {'poke_share': {'status': 'SKIPPED', 'why': 'no garments'}}
    from .anime_head import vertex_normals
    from .faceqa import triangles
    from .geom.bvh import BVH
    As = B.assembly
    L = As['L']
    sk = B.skin()
    BV = sk.V('assembly')
    loopv, starts, counts = sk.polys('assembly')
    faces = np.split(loopv, np.cumsum(counts)[:-1])
    BN = vertex_normals(BV, faces)
    hidden = B.array('skin/under_garments')
    near_d = 0.06 * L
    per_g, tot_bad = {}, 0
    for o in garments:
        vs = o.V('raw')
        T, _ = triangles(*o.polys('raw'))
        if not len(T):
            continue
        lo, hi = vs.min(0) - 0.02, vs.max(0) + 0.02
        cand = np.nonzero(~hidden & np.all((BV > lo) & (BV < hi), 1))[0]
        bad = 0
        if len(cand):
            # (mathutils' BVH runs in float32: its origins and vertices so here)
            tree = BVH((vs.astype(np.float32).astype(float), T))
            Oo = (BV[cand] + BN[cand] * 0.0005).astype(np.float32).astype(float)
            Dd = (-BN[cand]).astype(np.float32).astype(float)
            t, _ = tree.ray_cast(Oo, Dd, tmax=near_d)
            bad = int(np.isfinite(t).sum())
        per_g[o.name] = bad; tot_bad += bad
    share = tot_bad / max(1, int((~hidden).sum()))
    return None, {'poke_share': {'value': round(share, 4), 'per_garment': per_g, 'status': _grade('poke_share', share, False)}}


def mesh_info(B, design=None, out=None):
    """open edges and loose parts per hair and garment object's own mesh (information)."""
    mh = {}
    for o in B.objects(groups=('hair', 'garment'), visible=False):
        if not o.has('raw'):
            continue
        loopv, starts, counts = o.polys('raw')
        nxt = np.arange(len(loopv)) + 1
        nxt[starts + counts - 1] = starts
        e = np.sort(np.stack([loopv, loopv[nxt]], 1), 1)
        _, uses = np.unique(e, axis=0, return_counts=True)
        nv = len(o.V('raw'))
        from .trace import _components
        lab = _components(nv, e[:, 0], e[:, 1]) if len(e) else np.arange(nv)
        mh[o.name] = {'open_edges': int((uses == 1).sum()), 'parts': int(len(np.unique(lab)))}
    return None, {'mesh': {'status': 'INFO', 'objects': mh}}


# ------------------------------------------------------------------------------------------------------------------ run
def mouth_cover(B, ppl=200.0, shapes=None):
    """how much of each open mouth shows its inside: the lips' loop under the shape's key, seen head-on (exprqa's class
    render at ppl), and the share of what it encloses that is the mouth's inside, tongue, teeth or lip line; skin there
    is the lips' rings lapped over the opening, nothing a hole through the head. -> {shape: dict(cover, skin, none, px,
    cls)} for the shapes open by 20 px or more."""
    from matplotlib.path import Path
    from . import exprqa
    data = expression_data(B)
    A = assembly(B, 'base')
    L, win = A['head']['L'], exprqa.WIN
    V = np.asarray(A['verts'], float)
    m = A['mouth']['m']
    loop = list(m['upper']) + list(m['lower'])[::-1][1:-1]
    out = {}
    for name in shapes or [k for k in A['mouth']['keys']]:
        cls = exprqa.render(data, {'mouth': name}, ppl)
        xz = (V + A['mouth']['keys'][name])[loop][:, [0, 2]]
        col = xz[:, 0] / L * ppl + win['x'] * ppl
        row = (win['top'] - (xz[:, 1] - data['eye_z']) / L) * ppl
        H, W = cls.shape
        yy, xx = np.mgrid[0:H, 0:W]
        inside = Path(np.stack([col, row], 1)).contains_points(
            np.stack([xx.ravel() + 0.5, yy.ravel() + 0.5], 1)).reshape(H, W)
        n = int(inside.sum())
        if n < 20:
            continue
        c = cls[inside]
        out[name] = dict(cover=round(float(np.isin(c, COVER).mean()), 3), skin=round(float((c == 1).mean()), 3),
                         none=round(float((c == 0).mean()), 3), px=n, cls=cls)
    return out


def face_part(B, design=None, out=None):
    """the face's expressions and mouth shapes (face()) as a part, with the open mouths' cover (mouth_cover)."""
    table, C = face(B)
    mc = mouth_cover(B)
    if mc:
        k = min(mc, key=lambda s: mc[s]['cover'])
        C['mouth_cover'] = {'value': mc[k]['cover'], 'worst': k, 'skin': mc[k]['skin'], 'none': mc[k]['none'],
                            'status': _grade('mouth_cover', mc[k]['cover'])}
        table['mouth_cover'] = {s: {k_: v for k_, v in r.items() if k_ != 'cls'} for s, r in mc.items()}
    return table, C


def look(B, design=None, out=None):
    """the look's measures (charkit.lookqa): the face's shading noise, its shadows against the design's, the outlines'
    widths."""
    from . import lookqa
    return lookqa.measure(B, design, out)


PARTS = [                       # (part, function, check prefix, table key)
    ('shape', shape, '', 'views'), ('scalp', scalp, '', None), ('poke', poke, '', None), ('hair_noise', hair_noise, '', None),
    ('face_folds', folds, '', None), ('mesh', mesh_info, '', None),
    ('eyes', eyes, 'eye_', 'eyes'), ('sheet', sheet, 'sheet_', 'sheet'),
    ('sheet_figures', sheet_figures, 'figures_', 'sheet_figures'), ('sheet_body', sheet_body, 'body_', 'sheet_body'),
    ('sheet_expr', sheet_expressions, '', 'sheet_expr'), ('sheet_palette', sheet_palette, 'palette_', 'sheet_palette'),
    ('hair_pieces', hair_pieces, '', 'hair_pieces'),
    ('sheet_pieces', sheet_pieces, 'piece_', 'sheet_pieces'), ('pieces_3d', pieces_3d, 'piece3d_', 'pieces_3d'),
    ('face_shape', face_shape, 'face_shape_', 'face_shape'), ('face', face_part, 'face_', 'face'),
    ('look', look, '', 'look'),
]


def evaluate(B, parts=('shape', 'sheet_body', 'sheet_palette'), design=None, ref_image=None):
    """checks on a bundle without the report, the overlays or the cache (an evaluator's call: charkit.faceeval, the
    body evaluator): the named parts run as run() runs them -> {check: {value, status, ...}} with run()'s names."""
    design = design or Design(B)
    out = {}
    for name, fn, pre, _ in PARTS:
        if name in parts:
            _, C = fn(B, design, None, *((ref_image,) if name == 'shape' else ()))
            out.update({(k if name == 'face_shape' and k.startswith('face_shape') else pre + k): v for k, v in C.items()})
    from . import checks as checklib
    return checklib.authorize(out, design.ref().get('authority') or {})


def _strip(x):
    """a part's table for the report (the measurement's own arrays and pictures left out)."""
    if isinstance(x, dict):
        return {k: v for k, v in x.items() if not str(k).startswith('_')}
    return x


def run(B, out, ref_image=None, mode='on', parts=None):
    """every check on a bundle (a Bundle or its folder), the report and overlays into out -> the report (qa.json's)."""
    from . import bundle as bundlelib, cache, trace
    if isinstance(B, str):
        B = bundlelib.load(B)
    os.makedirs(out, exist_ok=True)
    design = Design(B)
    if ref_image is None:
        ref = B.spec.get('ref')
        ref_image = ref.get('image') if isinstance(ref, dict) else None
    rep = {'checks': {}, 'views': {}}
    t0 = time.perf_counter()
    for name, fn, pre, tkey in PARTS:
        if parts is not None and name not in parts:
            continue
        args = (ref_image,) if name == 'shape' else ()
        try:
            with trace.span('qa.' + name):
                table, C = cache.qa_part(name, fn, B, design, out, args, mode=mode)
        except Exception as e:
            import traceback; traceback.print_exc()
            rep['checks'][{'eyes': 'eye'}.get(name, name)] = {'status': 'SKIPPED', 'why': '%s: %s' % (type(e).__name__, e)}
            continue
        if tkey == 'views':
            rep['views'] = table
        elif tkey is not None and table is not None:
            rep[tkey] = _strip(table)
        for k, v in C.items():
            key = k if name == 'face_shape' and k.startswith('face_shape') else pre + k
            rep['checks'][key] = v
    from . import checks as checklib
    checklib.authorize(rep['checks'], design.ref().get('authority') or {})
    order = {'FAIL': 0, 'WARN': 1, 'PASS': 2}
    graded = [c['status'] for c in rep['checks'].values() if c.get('status') in order]
    rep['summary'] = min(graded, key=lambda s: order[s]) if graded else 'SKIPPED'
    rep['measured'] = {'where': 'venv', 'bundle': B.meta('content'), 'seconds': round(time.perf_counter() - t0, 2)}
    json.dump(rep, open(os.path.join(out, 'qa.json'), 'w'), indent=1, default=_json)
    if mode != 'off':
        cache.prune()                                           # (the cache's size cap, once per pass)
    return rep


def main(args):
    """python -m charkit qa BUNDLE_DIR [--out QA_DIR] [--cache on|off|refresh|verify] [--trace TRACE.jsonl]
    the QA on a build's geometry bundle (default out: the build's qa folder); --trace appends its records to a trace
    (a build's own does it: python -m charkit build)."""
    if not args or args[0] in ('-h', '--help'):
        print(main.__doc__); return
    from . import trace
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    bdir = os.path.abspath(args[0])
    out = os.path.abspath(opt('--out', os.path.join(os.path.dirname(bdir), 'qa')))
    tp = opt('--trace')
    opened = False
    if tp and not trace.active():
        trace.resume(tp)
        opened = True
    try:
        rep = measure(bdir, out, mode=opt('--cache', 'on'))
    finally:
        if opened:
            trace.end()
    print('CHARKIT_QA_SUMMARY', rep['summary'])


def measure(bdir, out, mode='on', ref_image=None):
    """the QA pass on a bundle folder as a build runs it: the report, its trace records ('qa' span, parts, the checks)
    and the CHARKIT_QA lines. -> the report."""
    from . import trace
    t = time.perf_counter()
    with trace.span('qa', where='venv'):
        rep = run(bdir, out, ref_image=ref_image, mode=mode)
    trace.event('qa', checks={k: (v.get('value'), v['status']) for k, v in rep['checks'].items() if k != 'mesh'},
                summary=rep['summary'])
    print('CHARKIT_QA', json.dumps({k: (v.get('value'), v['status']) for k, v in rep['checks'].items() if k != 'mesh'},
                                   default=_json))
    rep['measured']['total'] = round(time.perf_counter() - t, 2)
    return rep
