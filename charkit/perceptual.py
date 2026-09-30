"""A learned perceptual similarity to the design, per view and region (docs/workstreams/perceptual.md): DINOv3 patch
features of the design's view and of our EEVEE board of the same view, registered on one grid at the design's scale,
compared patch by patch and pooled per region (face, eyes, hair, neck, collar, bow, top, skirt, flaps, arms, legs,
boots, accessories), with per-region weights and limits calibrated on Michael's severity calls. A review metric beside
the geometric checks, not a replacement: it reads the boards, so it runs where boards render (the GPU render box or
the laptop), never in a gate (the build box renders none; see the notes for a gate-time variant on qa3d.draw).

The model is Meta's DINOv3 ViT-L/16 (facebook/dinov3-vitl16-pretrain-lvd1689m, the DINOv3 License of 2025-08-19: a
royalty-free licence to use, copy, modify and distribute, commercial use included; no GPL, no non-commercial clause;
its limits are trade controls and military use). The weights are gated on Hugging Face and cached on the render box.

Registration (both sides on one grid per scale and view, the origin on the eyes as charkit.bodyqa's grids have it):
  body   the body sheet's figures (the manifest's sheets.body) against boards/body_{000,035,090,180}.png, orthographic:
         each grid cell maps to a board pixel through the board camera (charkit.scene.boards: ortho 1.12 H round
         0.52 H) and our landmarks, 112 px per L
  head   the head sheet's heads (sheets.face) against boards/face_{000,030,090}.png, perspective (85 mm, 1 m): each
         cell's own surface point (our z-buffer's depth) is projected into the board, so the board is rectified to an
         orthographic view; 224 px per L. Without a bundle the eye plane stands for every cell (weak perspective)
Both pictures are laid on one background. The fit of the two silhouettes (IoU) is reported per view: the registration's
own measure, and a figure that doesn't match the design shows there too.

Regions: the design's from its classes (charkit.bodyqa.classes), the outfit graph's per-view piece masks and the face
region (charkit.sheetqa.face_region); ours from the bundle's objects z-buffered on the same grid (skin split by the
nearest joint and the chin). A region is the union of both sides' masks, so a piece that is missing, moved or extra
counts where it is on either side.

Distance per patch (16 px): 1 - the cosine of the two sides' patch features, each matched to its best neighbour within
one patch on the other side (both ways, averaged), so a shift under a patch costs nothing. A region's distance is the
coverage-weighted mean over its patches (and its 90th percentile, the worst); its score is the region's weight times
(distance - the floor): the calibration's (charkit/refs/clawd/perceptual_calibration.json).

    python -m charkit perceptual BUILD [--out DIR] [--spec SPEC] [--no-page] [--open] [--remote] [--hi]
        -> BUILD/perceptual/perceptual.json (per scale, view and region: distance, p90, score, grade), heat maps
           (heat_SCALE_VIEW.png: the design | ours | ours under the distance), maps.npz (every distance map and region
           coverage, to re-pool without the model) and index.html; --hi adds the body at 224 px per L (body_hi)
    python -m charkit perceptual --calibrate LABELS.json --build LABEL=DIR [...] [--out DIR]
        the calibration: every labelled build scored, per-region weights and limits fitted to the severities, Spearman's
        rho in-sample and leave-one-out -> DIR/calibration.json, DIR/index.html
    python -m charkit perceptual features IN.npz OUT.npz      (internal: the model's pass, in a torch interpreter)
"""
import html, json, os, shutil, subprocess, sys, time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = 'facebook/dinov3-vitl16-pretrain-lvd1689m'
LICENCE = dict(name='DINOv3 License', updated='2025-08-19', url='https://ai.meta.com/resources/models-and-libraries/dinov3-license',
               grant='1.a: non-exclusive, worldwide, royalty-free: use, reproduce, distribute, copy, create derivative works',
               limits='1.b.v: trade controls, ITAR, military, weapons; 1.b.ii: acknowledge in publications')
PATCH = 16
MEAN, STD = np.array([0.485, 0.456, 0.406]), np.array([0.229, 0.224, 0.225])
BG = np.array([0.93, 0.93, 0.93])          # both pictures' background (the design's grey, the boards' near-white)
LAYERS = (24, 18, 12)                       # hidden states read: the last block (the metric), then mid-late and mid (checks)
RADIUS = 1                                  # patches: the best match is sought this far on the other side

# the two scales: ppl px per L, the grid in patches (it tiles exactly), the window's top above the eye line (L), the
# boards and their azimuths per view (the design's three-quarter is its own; the boards' is the nearest they render)
SCALES = {
    'body': dict(ppl=112, cols=32, rows=53, top=1.3, board='body_%03d.png',
                 views={'front': 0, 'three_quarter': 35, 'profile': 90, 'back': 180}),
    'head': dict(ppl=224, cols=28, rows=22, top=0.84, board='face_%03d.png',
                 views={'front': 0, 'three_quarter': 30, 'profile': 90}),
    # the body at the head's px per L (the same window; the body sheet is drawn at 212 px per L, the boards at 152): a
    # 16 px patch is 0.07 L, so a detail of a tenth of an L (the bridge between the boots) spans patches. Optional
    # (--hi): 4x the tokens, maps only (no heat pictures)
    'body_hi': dict(ppl=224, cols=64, rows=106, top=1.3, board='body_%03d.png',
                    views={'front': 0, 'three_quarter': 35, 'profile': 90, 'back': 180}, optional=True),
}
DEFAULT_SCALES = ('body', 'head')
# the head scale shows the head sheet's own subjects only: its heads are bare to the shoulders, where ours wears the
# collar and top (the body scale grades those against the body sheet)
HEAD_REGIONS = ('face', 'eyes', 'hair', 'neck', 'accessories')
BODY_BOARD = dict(res=(600, 1000), ortho=1.12, target=0.52)       # charkit.scene.boards' body views (x H)
FACE_BOARD = dict(res=(900, 900), dist=1.0, lens=85.0, sensor=36.0, lift=0.06)   # its head views (lift: x L over the eyes)
REGIONS = ('face', 'eyes', 'hair', 'neck', 'collar', 'bow', 'top', 'skirt', 'flaps', 'arms', 'legs', 'boots',
           'accessories')
# where each region is graded: the head's scale shows the face at 224 px per L, the body's the figure at 112
PRIMARY = {'face': 'head', 'eyes': 'head', 'hair': 'head', 'neck': 'head', 'accessories': 'head'}
MIN_PATCHES = 3                             # a region over fewer patches (weighted) is reported, not graded
EYE_BOX = (0.15, 0.11)                      # L: the eye region's half-width and half-height round each eye
NECK_DROP = 0.3                             # L: the neck runs this far under the chin (above the collar)
ACC_REACH = 0.1                             # L: the design's hair clips grown by this (the crab beside the star)

# the outfit graph's pieces and our objects to regions (ours by name: garments' hand names, the hair's, the accessories')
PIECE_REGION = {'overskirt_panel': 'flaps', 'boot': 'boots', 'boot_cuff': 'boots', 'shoe': 'boots', 'shorts': 'legs',
                'skirt': 'skirt', 'skirt_panel': 'skirt', 'waistband': 'top', 'top': 'top', 'bodice_panel': 'top',
                'collar': 'collar', 'bow': 'bow', 'bow_tail': 'bow', 'sleeve': 'arms', 'sleeve_cuff': 'arms',
                'cuff': 'arms', 'wrist': 'arms', 'bun': 'hair', 'pin_crab': 'accessories', 'pin_star': 'accessories',
                'star': 'accessories', 'crab': 'accessories', 'boots': 'boots'}
JOINT_REGION = (('finger', 'arms'), ('wrist', 'arms'), ('lowerarm', 'arms'), ('shoulder', 'arms'), ('upperarm', 'arms'),
                ('clavicle', 'neck'), ('neck', 'neck'), ('upperleg', 'legs'), ('lowerleg', 'legs'), ('foot', 'legs'),
                ('toe', 'legs'), ('spine', 'top'), ('breast', 'top'), ('pelvis', 'top'), ('hips', 'top'),
                ('head', 'face'))


def _p(x):
    return x if os.path.isabs(x) else os.path.join(ROOT, x)


def win(scale):
    """a scale's window (L round the origin: x, top, bottom) and its px per L."""
    S = SCALES[scale]
    return dict(x=S['cols'] * PATCH / S['ppl'] / 2, top=S['top'], bottom=S['top'] - S['rows'] * PATCH / S['ppl']), S['ppl']


def grid(scale):
    """the (u, z) in L of each cell centre of a scale's grid (x right, z up from the origin) -> (u (H, W), z (H, W))."""
    w, ppl = win(scale)
    S = SCALES[scale]
    H, W = S['rows'] * PATCH, S['cols'] * PATCH
    u = (np.arange(W) + 0.5) / ppl - w['x']
    z = w['top'] - (np.arange(H) + 0.5) / ppl
    return np.broadcast_to(u[None], (H, W)), np.broadcast_to(z[:, None], (H, W))


# ------------------------------------------------------------------------------------------------------------ sampling
def sample(img, rows, cols, factor=1.0, order=1, cval=None):
    """img sampled at float pixel indices (rows, cols) (pixel i's centre at i), pre-blurred when it is being shrunk
    (factor: its pixels per output pixel) so a thin line becomes grey rather than aliasing. Outside: cval (default the
    edge's value). -> (H, W[, C])."""
    from scipy import ndimage
    a = np.asarray(img, float)
    if factor > 1.2 and order > 0:
        s = 0.45 * factor
        a = ndimage.gaussian_filter(a, (s, s) + (0,) * (a.ndim - 2))
    mode = 'nearest' if cval is None else 'constant'
    if a.ndim == 2:
        return ndimage.map_coordinates(a, [rows, cols], order=order, mode=mode, cval=cval or 0.0)
    return np.stack([ndimage.map_coordinates(a[..., k], [rows, cols], order=order, mode=mode, cval=cval or 0.0)
                     for k in range(a.shape[-1])], -1)


def _board_bg(im):
    """a board's background colour: its corners' median."""
    c = np.concatenate([im[:6, :6].reshape(-1, 3), im[:6, -6:].reshape(-1, 3), im[-6:, :6].reshape(-1, 3),
                        im[-6:, -6:].reshape(-1, 3)])
    return np.median(c, 0)


def _load(path):
    from PIL import Image
    return np.asarray(Image.open(_p(path)).convert('RGB')).astype(float) / 255


def _dilate(m, r):
    from scipy import ndimage
    return ndimage.binary_dilation(m, iterations=int(r)) if r >= 1 else m


def _grow(m, r):
    """m grown by a disk of radius r px."""
    from scipy import ndimage
    if not m.any():
        return m
    return ndimage.distance_transform_edt(~m) <= r


def _figure(im, bg, tol=0.012, hole=40):
    """a board's figure: the pixels off its flat background colour (the world is a tinted near-white, 239 239 244, and
    the boots a neutral one, 243 244 243: a tight tolerance tells them apart), specks opened away and pinholes filled;
    enclosed background (between the legs) stays background."""
    from scipy import ndimage
    out = np.abs(im - bg).max(-1) > tol
    out = ndimage.binary_opening(out, iterations=1)
    holes = ndimage.binary_fill_holes(out) & ~out
    lab, n = ndimage.label(holes)
    if n:
        small = np.bincount(lab.ravel())[1:] < hole
        out |= small[np.maximum(lab - 1, 0)] & (lab > 0)
    return out


# ------------------------------------------------------------------------------------------------------------ the design
class _DesignB:
    """the minimum charkit.qa3d.Design needs of a bundle: the spec (its references) and the eye spacing knob."""

    def __init__(self, spec, ex):
        self.spec, self.assembly, self._reads = spec, {'eye_knobs': {'x': ex}}, []

    def meta(self, k, d=None):
        return d


def design_spec(spec_path='charkit/spec/clawd.json'):
    """the spec whose manifest names the design (its sheets resolved) and its eye spacing knob (the sheets' scale)."""
    from . import eyes as eyelib, manifest
    spec = manifest.resolve(json.load(open(_p(spec_path))))
    return spec, float(eyelib._knobs(spec.get('eyes'))['x'])


def design_body(spec, ex, chin=-0.37, scale='body'):
    """the body sheet's figures on the body grid: {view: dict(rgb, fg, regions {name: bool}, anchor (sheet px),
    ppl_sheet)} (charkit.qa3d.Design's sheet context and bodyqa's classes; the outfit graph's piece masks). chin: L
    under the eye line, the head sheet's (the body sheet draws the neck in the face's tone, so its own face region runs
    on down the neck)."""
    from . import bodymeasure, bodyqa, qa3d
    from .cache import venv_memo
    D = qa3d.Design(_DesignB(spec, ex))
    ctx = D.sheet_context()
    if 'why' in ctx:
        raise RuntimeError('no body sheet: %s' % ctx['why'])
    dv = D.design_views()
    pm = bodymeasure.piece_masks(spec)
    masks = pm[0] if pm else {}
    return venv_memo(_design_body, ctx['rgb'], ctx['D'], ctx['ppl'], dv, masks, chin, scale), ctx['az3']


def _design_body(rgb, Dfig, ppl0, dv, masks, chin, scale='body'):
    from . import bodyqa
    u, z = grid(scale)
    w, ppl = win(scale)
    out = {}
    for view in SCALES[scale]['views']:
        f = Dfig['figures'].get(view)
        if f is None or view not in dv:
            continue
        eye = bodyqa.view_eye(view, f)
        rows, cols = eye[1] - z * ppl0, eye[0] + u * ppl0
        fac = ppl0 / ppl
        pic = sample(rgb, rows, cols, fac)
        fg = sample(f['_mask'].astype(float), rows, cols, fac, cval=0.0) > 0.5
        # the design_views grid (bodyqa.WIN at the sheet's ppl) for its classes and the piece masks
        r2, c2 = (bodyqa.WIN['top'] - z) * ppl0 - 0.5, (u + bodyqa.WIN['x']) * ppl0 - 0.5
        cls = sample(dv[view]['cls'], r2, c2, order=0, cval=0).astype(int)
        R = {}
        for k, m in masks.items():
            v, piece = k.split('__', 1)
            if v != view:
                continue
            reg = _piece_region(piece)
            if reg:
                mm = sample(m.astype(float), r2, c2, fac, cval=0.0) > 0.5
                R[reg] = R.get(reg, np.zeros_like(mm)) | mm
        R['hair'] = R.get('hair', np.zeros(u.shape, bool)) | (cls == bodyqa.CLASS['hair'])
        eyes = [((e[0] - eye[0]) / ppl0, (eye[1] - e[1]) / ppl0) for e in (f.get('eyes') or [])]
        _skin_regions(R, cls == bodyqa.CLASS['skin'], u, z, chin, eyes, view)
        out[view] = dict(rgb=np.where(fg[..., None], pic, BG), fg=fg, regions=R, eyes=eyes, chin=chin, ppl_sheet=ppl0,
                         anchor=[float(eye[0]), float(eye[1])])
    return out


def _piece_region(name):
    for k in sorted(PIECE_REGION, key=len, reverse=True):
        if name == k or name.startswith(k + '_') or name.startswith(k):
            return PIECE_REGION[k]
    return None


def _skin_regions(R, skin, u, z, chin, eyes, view):
    """the design's skin split into face, neck, arms and legs by position (L from the eyes), and its eye boxes."""
    face = skin & (z > chin) & (z < 0.6)
    neck = skin & (z <= chin) & (z > chin - NECK_DROP) & (np.abs(u - (0.0 if view != 'profile' else 0.25)) < 0.45)
    low = skin & ~face & ~neck & (z < chin)
    legs = low & (z < -3.15) & (np.abs(u) < 0.7)
    arms = low & ~legs
    for k, m in (('face', face), ('neck', neck), ('arms', arms), ('legs', legs)):
        R[k] = R.get(k, np.zeros_like(m)) | m
    R['eyes'] = _eye_boxes(u, z, eyes)


def _eye_boxes(u, z, eyes):
    m = np.zeros(u.shape, bool)
    for eu, ez in eyes:
        m |= ((u - eu) / EYE_BOX[0]) ** 2 + ((z - ez) / EYE_BOX[1]) ** 2 <= 1
    return m


def design_head(spec, ex):
    """the head sheet's heads on the head grid: {view: dict(rgb, fg, regions, eyes, chin)} (charkit.refcheck's heads at
    the grid's px per L; the face region as the QA's face measure finds it; the neck the skin under its chin)."""
    from . import refcheck
    from .cache import venv_memo
    fs = (spec.get('ref') or {}).get('face_sheet')
    if not fs:
        raise RuntimeError('no face sheet in the spec\'s references')
    return venv_memo(_design_head, _p(fs['image']), ex, fs.get('facing', -1))


def _design_head(path, ex, facing):
    from . import bodyqa, refcheck
    rgb0 = _load(path)
    clean, _ = refcheck.without_guides(rgb0)
    w, ppl = win('head')
    rgb, f, H = refcheck.at_scale(clean, ex, 2 * ex * ppl, facing)
    M, chin0 = refcheck.measure_heads(rgb, H['heads'], ppl, facing)
    u, z = grid('head')
    out = {}
    for view in SCALES['head']['views']:
        h = H['heads'].get(view)
        if not h or not h.get('eyes'):
            continue
        E = [tuple(e) for e in h['eyes']]
        anchor = E[0] if view == 'profile' else tuple(np.mean(E, 0))
        rows, cols = anchor[1] - z * ppl, anchor[0] + u * ppl
        pic = sample(rgb, rows, cols)
        fg = sample(h['_mask'].astype(float), rows, cols, cval=0.0) > 0.5
        cls, _ = bodyqa.classes(pic, fg, float(w['top'] * ppl), ppl)
        R = {'hair': cls == bodyqa.CLASS['hair']}
        m = M.get(view) or {}
        face = sample(m['face'].astype(float), rows, cols, cval=0.0) > 0.5 if m.get('face') is not None else None
        chin = m.get('chin') if m.get('chin') is not None else (chin0 if chin0 is not None else -0.37)
        eyes = [((e[0] - anchor[0]) / ppl, (anchor[1] - e[1]) / ppl) for e in E]
        skin = cls == bodyqa.CLASS['skin']
        _skin_regions(R, skin, u, z, chin, eyes, view)
        if face is not None and face.sum() > 50:
            R['neck'] &= ~face
            R['face'] = (R['face'] | face) & ~R['eyes']
        # the hair clips: the yellow star (the iris family) above the eyes, grown to take in the crab beside it
        from .bodyqa import family, CLASS
        star = fg & (family(pic) == CLASS['iris']) & (z > 0.15)
        R['accessories'] = _grow(star, ACC_REACH * ppl) & fg if star.sum() > 20 else np.zeros_like(star)
        R = {k: v for k, v in R.items() if k in HEAD_REGIONS}
        R['hair'] &= ~R['accessories']
        out[view] = dict(rgb=np.where(fg[..., None], pic, BG), fg=fg, regions=R, eyes=eyes, chin=float(chin),
                         anchor=[float(anchor[0]), float(anchor[1])], factor=float(f))
    return out


# ------------------------------------------------------------------------------------------------------------ ours
class Ours:
    """a build's side: its boards, its landmarks (the bundle's, else the trace's) and, with a bundle, its objects."""

    def __init__(self, build):
        self.dir = _p(build)
        self.B = None
        bd = os.path.join(self.dir, 'bundle')
        if os.path.exists(os.path.join(bd, 'bundle.json')):
            from . import bundle
            self.B = bundle.load(bd)
        spec_f = [f for f in os.listdir(self.dir) if f.endswith('.spec.json') and not f.startswith('input')]
        self.spec = self.B.spec if self.B is not None else (json.load(open(os.path.join(self.dir, spec_f[0]))) if spec_f else {})
        self.H = float((self.spec.get('body') or {}).get('height_m', 1.6))
        if self.B is not None:
            from . import qa3d
            A = self.B.assembly
            self.L, self.eye_z = float(A['L']), float(A['eye_z'])
            self.iris = np.array(qa3d.iris_centres(self.B), float)
            lm = self.B.meta('landmarks') or {}
            self.centre = list(lm.get('centre') or A['centre'])
            self.chin_z = self.eye_z - float(A['chin'])
            self.joints = dict(lm.get('joints') or {})
        else:
            lm = self._trace_landmarks()
            self.L = float(lm['L'])
            self.centre = list(lm['centre'])
            ez = float(np.mean([e[1] for e in lm['eyes']]))
            self.eye_z = ez
            # the eyes' depth isn't traced: the bundle builds put the iris 0.27 L in front of the head's centre
            y = self.centre[1] - IRIS_AHEAD * self.L
            self.iris = np.array([[e[0], y, e[1]] for e in lm['eyes']], float)
            self.chin_z = float(lm.get('chin_z', ez - 0.36 * self.L))
            self.joints = {}

    def _trace_landmarks(self):
        import ast
        got = None
        for line in open(os.path.join(self.dir, 'trace.jsonl')):
            r = json.loads(line)
            lm = r.get('landmarks')
            if lm:
                got = ast.literal_eval(lm) if isinstance(lm, str) else lm
        if not got:
            raise RuntimeError('%s: no bundle and no landmarks in trace.jsonl' % self.dir)
        return got

    def board(self, scale, view):
        p = os.path.join(self.dir, 'boards', SCALES[scale]['board'] % SCALES[scale]['views'][view])
        return p if os.path.exists(p) else None

    def anchor(self, view, az):
        """the grid's origin for a view (world u, z): charkit.bodyqa.origin on our iris centres."""
        from . import bodyqa
        return bodyqa.origin(view, az, self.iris, self.centre)

    def anchor3(self, view):
        """the 3D point the view's grid is anchored on: the eyes' midpoint, the profile's near eye (her left)."""
        return self.iris[np.argmax(self.iris[:, 0])] if view == 'profile' else self.iris.mean(0)

    # ---- our objects on a grid
    def labels(self, scale, view, az):
        """our visible surfaces z-buffered on the scale's grid at az: -> (depth along the view (H, W), inf where empty;
        region names per pixel as a {region: bool} dict). None without a bundle."""
        if self.B is None:
            return None
        from .geom import raster
        w, ppl = win(scale)
        o = self.anchor(view, az)
        items, names = [], []
        sk = self.B.skin()
        for ob in self.B.objects():
            var = 'masked' if ob is sk and ob.has('masked') else 'eval'
            if not ob.has(var):
                continue
            V, T = ob.mesh(var)[:2]
            if not len(T):
                continue
            if ob is sk:
                lab = self._skin_labels(V, T)
            else:
                reg = self._region_of(ob)
                lab = np.full(len(T), REGIONS.index(reg) if reg in REGIONS else -2)
            items.append((V, T, lab))
        dep, lab = raster.window_zbuffer(items, az, o, self.L, 1.0 / ppl, w)
        R = {r: lab == i for i, r in enumerate(REGIONS)}
        R['_other'] = lab == -2
        return dep, lab != -1, R

    def _region_of(self, ob):
        if ob.group == 'hair':
            return 'hair'
        if ob.group == 'eye':
            return 'face' if ob.part == 'brow' else 'eyes'
        if ob.group == 'mouth':
            return 'face'
        return _piece_region(ob.name)

    def _skin_labels(self, V, T):
        """the skin's triangles to regions: face above the chin, else by the nearest joint (arms, legs, neck, torso)."""
        c = V[T].mean(1)
        names, P = [], []
        for k, p in self.joints.items():
            names.append(k.split('____')[0]); P.append(p)
        if not P:
            reg = np.where(c[:, 2] > self.chin_z, REGIONS.index('face'), REGIONS.index('neck'))
            return reg
        P = np.array(P, float)
        from scipy.spatial import cKDTree
        _, j = cKDTree(P).query(c)
        jr = []
        for n in names:
            r = next((reg for key, reg in JOINT_REGION if key in n.lower()), 'top')
            jr.append(REGIONS.index(r))
        reg = np.array(jr)[j]
        head = (c[:, 2] > self.chin_z) & (np.hypot(c[:, 0] - self.centre[0], c[:, 1] - self.centre[1]) < 0.9 * self.L)
        reg[head] = REGIONS.index('face')
        neckish = (reg == REGIONS.index('face')) & ~head
        reg[neckish] = REGIONS.index('neck')
        return reg

    # ---- the board on a grid
    def on_grid(self, scale, view):
        """our board of the view resampled onto the scale's grid -> dict(rgb (laid on BG), fg, regions, depth, how) or
        None when the board is missing."""
        p = self.board(scale, view)
        if p is None:
            return None
        az = SCALES[scale]['views'][view]
        im = _load(p)
        bg = _board_bg(im)
        u, z = grid(scale)
        w, ppl = win(scale)
        ou, oz = self.anchor(view, az)
        U, Z = ou + u * self.L, oz + z * self.L                   # world, per cell (u along the view's right)
        lab = self.labels(scale, view, az)
        if scale.startswith('body'):
            Hh, Ww = BODY_BOARD['res'][1], BODY_BOARD['res'][0]
            ppm = max(Hh, Ww) / (BODY_BOARD['ortho'] * self.H)
            rows = Hh / 2 - (Z - BODY_BOARD['target'] * self.H) * ppm - 0.5
            cols = Ww / 2 + U * ppm - 0.5
            how = 'orthographic board, %.1f board px per L' % (ppm * self.L)
            fac = ppm * self.L / ppl
        else:
            Ww, Hh = FACE_BOARD['res']
            a = np.radians(az)
            tz = self.eye_z + FACE_BOARD['lift'] * self.L
            k = FACE_BOARD['lens'] / FACE_BOARD['sensor'] * max(Ww, Hh)
            A = self.anchor3(view)
            dA = (-A[0] * np.sin(a) + A[1] * np.cos(a)) + FACE_BOARD['dist']    # camera depth of the anchor
            if lab is not None:
                dep = lab[0]
                d = np.where(np.isfinite(dep), dep + FACE_BOARD['dist'], dA)
                how = 'perspective board rectified on our depth (%.0f board px per L at the eyes)' % (k / dA * self.L)
            else:
                d = np.full(U.shape, dA)
                how = 'perspective board, weak perspective at the eyes (%.0f board px per L; no bundle)' % (k / dA * self.L)
            rows = Hh / 2 - (Z - tz) * k / d - 0.5
            cols = Ww / 2 + U * k / d - 0.5
            fac = k / dA * self.L / ppl
        pic = sample(im, rows, cols, fac)
        fg_b = sample(_figure(im, bg).astype(float), rows, cols, fac) > 0.5
        valid = (rows >= 0) & (rows <= Hh - 1) & (cols >= 0) & (cols <= Ww - 1)
        fg_b &= valid
        out = dict(rgb=np.where(fg_b[..., None], pic, BG), fg=fg_b, valid=valid, how=how,
                   board=os.path.relpath(p, self.dir), regions={}, fg_z=None)
        if lab is not None:
            R = {k: v & valid for k, v in lab[2].items() if not k.startswith('_')}
            if scale == 'head':
                # what the head sheet can't show (ours clothed where its heads are bare) is left out of the head scale
                out['clothed'] = sum((R[k] for k in REGIONS if k not in HEAD_REGIONS), np.zeros(valid.shape, bool)) > 0
                R = {k: v for k, v in R.items() if k in HEAD_REGIONS}
            out['regions'] = R
            out['fg_z'] = lab[1] & valid
        return out


IRIS_AHEAD = 0.27      # L: our iris centres' lead over the head centre (y), for a build with no bundle (measured below)


# ------------------------------------------------------------------------------------------------------------ pairs
def pairs(build, spec_path='charkit/spec/clawd.json', scales=DEFAULT_SCALES):
    """every (scale, view) of a build with its board: the design and ours on one grid, each side's regions, the
    registration's silhouette IoU. -> list of dicts."""
    spec, ex = design_spec(spec_path)
    O = Ours(build)
    Dh = design_head(spec, ex)
    chins = [d['chin'] for v, d in Dh.items() if v == 'profile'] or [d['chin'] for d in Dh.values()]
    chin = float(np.median(chins)) if chins else -0.37
    sides = []
    for scale in scales:
        if scale == 'head':
            sides.append((scale, Dh))
        else:
            Db, az3 = design_body(spec, ex, chin, scale)
            sides.append((scale, Db))
    out = []
    for scale, D in sides:
        for view in SCALES[scale]['views']:
            if view not in D:
                continue
            o = O.on_grid(scale, view)
            if o is None:
                continue
            d = dict(D[view])
            cut = ~o['valid'] | o.get('clothed', np.zeros(o['valid'].shape, bool))
            if cut.any():
                # cells the board doesn't reach, and at the head scale ours clothed where the head sheet is bare: laid
                # on the background on both sides and left out of every region
                d['fg'] = d['fg'] & ~cut
                d['rgb'] = np.where(cut[..., None], BG, d['rgb'])
                d['regions'] = {k: v & ~cut for k, v in d['regions'].items()}
                o['fg'] = o['fg'] & ~cut
                o['rgb'] = np.where(cut[..., None], BG, o['rgb'])
                o['regions'] = {k: v & ~cut for k, v in o['regions'].items()}
            fgo = o['fg']
            iou = float((fgo & d['fg']).sum() / max(1, (fgo | d['fg']).sum()))
            if o.get('fg_z') is not None:
                # the registration's own check: the board's figure against our z-buffered one on the same grid
                fz = o['fg_z'] & ~cut
                o['reg_iou'] = round(float((fz & fgo).sum() / max(1, (fz | fgo).sum())), 4)
            out.append(dict(scale=scale, view=view, design=d, ours=o, iou=round(iou, 4),
                            az_board=SCALES[scale]['views'][view], az_design=(az3 if view == 'three_quarter' and scale != 'head'
                                                                              else SCALES[scale]['views'][view])))
    return out


# ------------------------------------------------------------------------------------------------------------ the model
def _torch_ok():
    """can this interpreter run the model (torch, and a transformers with DINOv3)?"""
    try:
        import torch  # noqa: F401
        import transformers.models.dinov3_vit  # noqa: F401
        return True
    except Exception:
        return False


TORCH_PY = ('/srv/work/trellis2/.venv/bin/python',)      # the render box's TRELLIS venv (torch, transformers 4.57)


def _load_model(dev, dt):
    """DINOv3 from the Hugging Face cache (the render box holds it); if it's missing and CHARKIT_HF_SECRET names the
    cloud secret holding the token, the token is read from the secret manager in memory (never printed or written) and
    the weights fetched. -> (model, snapshot revision)."""
    from transformers import AutoModel
    try:
        m = AutoModel.from_pretrained(MODEL, local_files_only=True, dtype=dt)
    except Exception:
        name = os.environ.get('CHARKIT_HF_SECRET')
        if not name:
            raise RuntimeError('%s is not in this machine\'s Hugging Face cache (gated: the render box has it; set '
                               'CHARKIT_HF_SECRET to the secret holding the token to fetch it)' % MODEL)
        tok = subprocess.run(['gcloud', 'secrets', 'versions', 'access', 'latest', '--secret=' + name],
                             capture_output=True, text=True).stdout.strip()
        m = AutoModel.from_pretrained(MODEL, token=tok, dtype=dt)
        del tok
    rev = getattr(m.config, '_commit_hash', None)
    return m.to(dev).eval(), rev


def features(imgs, layers=LAYERS):
    """DINOv3 patch features of pictures (float sRGB (H, W, 3), H and W multiples of PATCH): per picture {layer: (h, w,
    C) float16}, each layer's tokens through the model's final norm. -> (list, meta)."""
    import torch
    dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    dt = torch.float32                       # (DINOv3 overflows in float16: its patch tokens come out NaN; the T4 has no bf16)
    t0 = time.time()
    m, rev = _load_model(dev, dt)
    nreg = int(getattr(m.config, 'num_register_tokens', 0))
    nl = int(m.config.num_hidden_layers)
    out = []
    for im in imgs:
        H, W = im.shape[:2]
        x = ((np.asarray(im, np.float32) - MEAN) / STD).transpose(2, 0, 1)[None].astype(np.float32)
        with torch.inference_mode():
            o = m(pixel_values=torch.from_numpy(x).to(dev, dt), output_hidden_states=True)
            hs = o.hidden_states
            h, w = H // PATCH, W // PATCH
            f = {}
            for l in layers:
                t = o.last_hidden_state if (l == nl or hs is None or len(hs) <= l) else m.norm(hs[l])
                f[l] = t[0, 1 + nreg:1 + nreg + h * w].float().reshape(h, w, -1).cpu().numpy().astype(np.float16)
        out.append(f)
    meta = dict(model=MODEL, revision=rev, device=dev + (':' + torch.cuda.get_device_name(0) if dev == 'cuda' else ''),
                dtype=str(dt).replace('torch.', ''), torch=torch.__version__, layers=list(layers), registers=nreg,
                seconds=round(time.time() - t0, 2))
    return out, meta


def run_features(imgs, work):
    """features() here if this interpreter can, else in the torch interpreter (CHARKIT_TORCH_PY, else the render box's
    TRELLIS venv) through an npz in `work`. -> (list, meta)."""
    if _torch_ok() and os.environ.get('CHARKIT_TORCH_PY') is None:
        try:
            return features(imgs)
        except RuntimeError as e:
            if 'Hugging Face cache' not in str(e):
                raise
    py = os.environ.get('CHARKIT_TORCH_PY') or next((p for p in TORCH_PY if os.path.exists(p)), None)
    if not py:
        raise RuntimeError('no interpreter with torch and DINOv3 here: run on the render box (python -m charkit perceptual '
                           'BUILD --remote from the laptop), or set CHARKIT_TORCH_PY')
    os.makedirs(work, exist_ok=True)
    fin, fout = os.path.join(work, 'images.npz'), os.path.join(work, 'features.npz')
    np.savez_compressed(fin, **{'img_%03d' % i: _u8(im) for i, im in enumerate(imgs)})
    subprocess.run([py, '-m', 'charkit.perceptual', 'features', fin, fout], cwd=ROOT, check=True)
    Z = np.load(fout)
    meta = json.loads(str(Z['meta']))
    got = [{l: Z['f_%03d_%d' % (i, l)] for l in meta['layers']} for i in range(len(imgs))]
    os.remove(fin)
    os.remove(fout)                       # (the features are ~10 MB a picture: nothing keeps them)
    return got, meta


def _features_main(fin, fout):
    Z = np.load(fin)
    imgs = [Z[k].astype(np.float32) / 255 if Z[k].dtype == np.uint8 else Z[k] for k in sorted(Z.files)]
    got, meta = features(imgs)
    arr = {'f_%03d_%d' % (i, l): f[l] for i, f in enumerate(got) for l in f}
    np.savez(fout, meta=json.dumps(meta), **arr)


# ------------------------------------------------------------------------------------------------------------ distances
def _u8(im):
    return (np.clip(np.asarray(im, float), 0, 1) * 255 + 0.5).astype(np.uint8)


def _norm(F):
    F = np.asarray(F, np.float32)
    return F / np.maximum(np.linalg.norm(F, axis=-1, keepdims=True), 1e-6)


def patch_distance(Fd, Fo, r=RADIUS):
    """per patch: 1 - the cosine of each side's feature with its best match within r patches on the other side, both
    ways averaged; and the plain same-place distance. -> (matched (h, w), aligned (h, w))."""
    Fd, Fo = _norm(Fd), _norm(Fo)
    h, w, _ = Fd.shape
    aligned = 1 - (Fd * Fo).sum(-1)
    best_do = np.full((h, w), -1.0, np.float32)
    best_od = np.full((h, w), -1.0, np.float32)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            ys, ye = max(0, -dy), h - max(0, dy)
            xs, xe = max(0, -dx), w - max(0, dx)
            s = (Fd[ys:ye, xs:xe] * Fo[ys + dy:ye + dy, xs + dx:xe + dx]).sum(-1)
            best_do[ys:ye, xs:xe] = np.maximum(best_do[ys:ye, xs:xe], s)
            best_od[ys + dy:ye + dy, xs + dx:xe + dx] = np.maximum(best_od[ys + dy:ye + dy, xs + dx:xe + dx], s)
    return 1 - (best_do + best_od) / 2, aligned


def coverage(mask):
    """a pixel mask's share of each patch -> (h, w)."""
    H, W = mask.shape
    return mask.reshape(H // PATCH, PATCH, W // PATCH, PATCH).mean((1, 3))


def _wq(v, w, q):
    o = np.argsort(v)
    c = np.cumsum(w[o])
    return float(v[o][np.searchsorted(c, q * c[-1])]) if c[-1] > 0 else None


MIN_COVER = 0.15                 # a patch belongs to a region when the region covers this much of it


def region_stats(dmap, masks, grow=3):
    """a distance map pooled per region: {region: dict(dist (coverage-weighted mean), p90, patches (the weight), px)}.
    masks {region: (design mask, our mask or None)}; a region is their union grown by `grow` px."""
    out = {}
    for reg, (md, mo) in masks.items():
        m = md if mo is None else (md | mo)
        if not m.any():
            continue
        m = _dilate(m, grow)
        cov = coverage(m)
        w = np.where(cov >= MIN_COVER, cov, 0.0)
        if w.sum() <= 0:
            continue
        v = dmap[w > 0].astype(float); ww = w[w > 0]
        out[reg] = dict(dist=round(float((v * ww).sum() / ww.sum()), 4), p90=round(_wq(v, ww, 0.9), 4),
                        patches=round(float(ww.sum()), 2), px_design=int(md.sum()), px_ours=None if mo is None else int(mo.sum()))
    return out


def score_pairs(prs, feats, layer=LAYERS[0]):
    """each pair's distance maps and region stats (in place: pair['dmap'], ['aligned'], ['regions'], ['layers'])."""
    for pr, (fd, fo) in zip(prs, feats):
        dm, al = patch_distance(fd[layer], fo[layer])
        pr['dmap'], pr['aligned'] = dm, al
        masks = {}
        for reg in REGIONS:
            md = pr['design']['regions'].get(reg)
            mo = pr['ours']['regions'].get(reg) if pr['ours']['regions'] else None
            if md is None and mo is None:
                continue
            masks[reg] = (md if md is not None else np.zeros_like(mo), mo)
        pr['regions'] = region_stats(dm, masks)
        pr['cover'] = {reg: coverage(_dilate(md if mo is None else md | mo, 3)) for reg, (md, mo) in masks.items()}
        pr['maps'] = {'aligned_l%d' % layer: al}
        pr['layers'] = {'aligned': {k: dict(dist=v['dist'], p90=v['p90']) for k, v in region_stats(al, masks).items()}}
        for l in fd:
            if l == layer:
                continue
            d2, _ = patch_distance(fd[l], fo[l])
            pr['maps']['dmap_l%d' % l] = d2
            pr['layers'][l] = {k: dict(dist=v['dist'], p90=v['p90']) for k, v in region_stats(d2, masks).items()}
        pr['whole'] = round(float(dm[coverage(pr['design']['fg'] | pr['ours']['fg']) >= MIN_COVER].mean()), 4)
    return prs


# ------------------------------------------------------------------------------------------------------------ grading
CALIBRATION = 'charkit/refs/clawd/perceptual_calibration.json'


def load_calibration(path=CALIBRATION):
    """the fitted floors, weights and limits (calibrate()), or None before a calibration exists."""
    p = _p(path)
    return json.load(open(p)) if os.path.exists(p) else None


def grade(C, scale, view, region, dist):
    """a region's calibrated score (its weight x (distance - its floor)) and grade (PASS / WARN / FAIL against the
    limits; INFO where the region isn't graded at this scale or there's no calibration). -> (score, grade)."""
    if C is None or dist is None:
        return None, 'INFO'
    fl = (C.get('floors') or {}).get('%s/%s/%s' % (scale, view, region))
    if fl is None:
        fl = (C.get('floors') or {}).get('%s/*/%s' % (scale, region), C.get('floor', 0.0))
    w = (C.get('weights') or {}).get(region, 1.0)
    sc = round(w * (dist - fl), 4)
    if PRIMARY.get(region, 'body') != scale:
        return sc, 'INFO'
    lim = C['limits']
    return sc, 'FAIL' if sc >= lim['fail'] else 'WARN' if sc >= lim['warn'] else 'PASS'


# ------------------------------------------------------------------------------------------------------------ pictures
def heat_colour(d, lo=0.1, hi=0.45):
    """a distance map (h, w) -> RGBA (h, w, 4): transparent below lo, then yellow to red to magenta up to hi."""
    t = np.clip((np.asarray(d, float) - lo) / (hi - lo), 0, 1)
    r = np.clip(0.6 + 0.8 * t, 0, 1)
    g = np.clip(1.0 - 1.4 * t, 0, 1)
    b = np.clip(2.0 * t - 1.0, 0, 1) * 0.9
    a = np.clip(t * 1.6, 0, 0.85)
    return np.stack([r, g, b, a], -1)


def heat_picture(pr, lo=0.1, hi=0.45):
    """the design | ours | ours under the distance map (per patch), at the grid's resolution."""
    from scipy import ndimage
    d, o = pr['design'], pr['ours']
    H = heat_colour(pr['dmap'], lo, hi)
    H = np.repeat(np.repeat(H, PATCH, 0), PATCH, 1)
    base = o['rgb'] * 0.75 + 0.25
    over = base * (1 - H[..., 3:]) + H[..., :3] * H[..., 3:]
    edge = d['fg'] & ~ndimage.binary_erosion(d['fg'])          # the design's outline over ours
    over[edge] = (0.15, 0.3, 0.9)
    sep = np.ones((d['rgb'].shape[0], 6, 3))
    return np.concatenate([d['rgb'], sep, o['rgb'], sep, over], 1)


def _save(path, im):
    from PIL import Image
    Image.fromarray(_u8(im)).save(path)


def legend(lo=0.1, hi=0.45, w=240, h=14):
    t = np.linspace(lo, hi, w)[None].repeat(h, 0)
    H = heat_colour(t, lo, hi)
    return np.ones((h, w, 3)) * (1 - H[..., 3:]) + H[..., :3] * H[..., 3:]


# ------------------------------------------------------------------------------------------------------------ the run
def run(build, out=None, spec_path='charkit/spec/clawd.json', calib=CALIBRATION, pictures=True, log=print,
        scales=DEFAULT_SCALES):
    """the whole pass on a build with boards -> the result dict (also out/perceptual.json, the heat maps, maps.npz: every
    pair's per-patch distance maps (each layer, and layer 24 unmatched) and region coverage, for re-pooling without the
    model; index.html)."""
    build = _p(build)
    out = _p(out) if out else os.path.join(build, 'perceptual')
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    prs = pairs(build, spec_path, scales)
    if not prs:
        raise RuntimeError('%s: no boards (boards/body_*.png, face_*.png) to compare' % build)
    t1 = time.time()
    imgs = [x for pr in prs for x in (pr['design']['rgb'], pr['ours']['rgb'])]
    feats, meta = run_features(imgs, out)
    t2 = time.time()
    score_pairs(prs, [(feats[2 * i], feats[2 * i + 1]) for i in range(len(prs))])
    C = load_calibration(calib) if calib else None
    res = dict(build=build, when=time.strftime('%Y-%m-%d %H:%M'), model=meta, licence=LICENCE, layer=LAYERS[0],
               radius=RADIUS, calibration=(C or {}).get('fitted'), scales={}, seconds=dict(
                   register=round(t1 - t0, 1), features=round(t2 - t1, 1)))
    maps = {}
    for pr in prs:
        sc, v = pr['scale'], pr['view']
        R = {}
        for reg, st in pr['regions'].items():
            score, g = grade(C, sc, v, reg, st['dist'])
            if st['patches'] < MIN_PATCHES and g != 'INFO':
                g = 'INFO'
            ex = {}
            for l, per in pr['layers'].items():
                tag = l if isinstance(l, str) else 'l%d' % l
                if reg in per:
                    ex['dist_' + tag], ex['p90_' + tag] = per[reg]['dist'], per[reg]['p90']
            R[reg] = dict(st, score=score, grade=g, graded_here=PRIMARY.get(reg, 'body') == sc, **ex)
        key = '%s_%s' % (sc, v)
        maps[key + '__dmap_l%d' % LAYERS[0]] = pr['dmap'].astype(np.float16)
        for k, m in pr['maps'].items():
            maps[key + '__' + k] = m.astype(np.float16)
        for reg, c in pr['cover'].items():
            maps[key + '__cov_' + reg] = c.astype(np.float16)
        maps[key + '__cov_fg'] = coverage(pr['design']['fg'] | pr['ours']['fg']).astype(np.float16)
        entry = dict(iou=pr['iou'], registration_iou=pr['ours'].get('reg_iou'), how=pr['ours']['how'],
                     board=pr['ours']['board'], az_board=pr['az_board'], az_design=pr['az_design'], whole=pr['whole'],
                     regions=R)
        if pictures and not SCALES[sc].get('optional'):
            f = 'heat_%s_%s.png' % (sc, v)
            _save(os.path.join(out, f), heat_picture(pr))
            np.save(os.path.join(out, 'dmap_%s_%s.npy' % (sc, v)), pr['dmap'].astype(np.float16))
            entry['picture'] = f
        res['scales'].setdefault(sc, {})[v] = entry
    res['summary'] = summary(res)
    np.savez_compressed(os.path.join(out, 'maps.npz'), **maps)
    if pictures:
        _save(os.path.join(out, 'legend.png'), legend())
    json.dump(res, open(os.path.join(out, 'perceptual.json'), 'w'), indent=1)
    if pictures:
        page(res, out)
    log('perceptual: %d views, %.0f s (registration %.0f, model %.0f) -> %s' % (
        len(prs), time.time() - t0, t1 - t0, t2 - t1, os.path.relpath(out, ROOT) if out.startswith(ROOT) else out))
    return res


def summary(res):
    """per region, its graded scale's worst view: [dict(region, view, dist, score, grade)], worst first."""
    rows = []
    for reg in REGIONS:
        sc = PRIMARY.get(reg, 'body')
        best = None
        for v, e in (res['scales'].get(sc) or {}).items():
            r = e['regions'].get(reg)
            if not r or r['patches'] < MIN_PATCHES:
                continue
            key = r['score'] if r['score'] is not None else r['dist']
            if best is None or key > best[0]:
                best = (key, dict(region=reg, scale=sc, view=v, dist=r['dist'], p90=r['p90'], score=r['score'],
                                  grade=r['grade']))
        if best:
            rows.append(best[1])
    return sorted(rows, key=lambda r: -(r['score'] if r['score'] is not None else r['dist']))


def page(res, out):
    """out/index.html: the summary table, then each scale's views: the design | ours | the heat map, per-region numbers."""
    e = html.escape
    G = {'PASS': '#2e7d32', 'WARN': '#b26a00', 'FAIL': '#c62828', 'INFO': '#666'}
    H = ['<!doctype html><meta charset="utf-8"><title>Perceptual review</title><style>',
         'body{font:14px/1.45 -apple-system,system-ui,sans-serif;margin:24px;background:#f4f3f1;color:#222}',
         'h1{font-size:22px}h2{font-size:18px;margin-top:30px}table{border-collapse:collapse;font-size:13px;margin:6px 0}',
         'td,th{border:1px solid #ccc;padding:3px 7px;text-align:right}th:first-child,td:first-child{text-align:left}',
         'img{border:1px solid #ccc;background:#fff;display:block;max-width:100%}.note{max-width:1000px;color:#444}',
         'figure{display:inline-block;margin:0 14px 18px 0;vertical-align:top}figcaption{font-size:12px;color:#555;max-width:900px}',
         '</style>']
    C = res.get('calibration')
    H.append('<h1>Perceptual similarity to the design: %s</h1>' % e(os.path.basename(res['build'].rstrip('/'))))
    H.append('<p class="note">%s DINOv3 ViT-L/16 patch features (layer %d, %s, %s; the %s), our boards against the design\'s '
             'sheets registered on one grid per view. Per patch: 1 - cosine, each patch matched to its best neighbour '
             'within %d patch on the other side. A region is the union of the design\'s and our masks; its distance the '
             'coverage-weighted mean over its patches, p90 its worst tenth. Score = weight x (distance - floor), graded '
             'against limits fitted to Michael\'s severity calls%s. A review metric: it complements the geometric '
             'checks and never gates.</p>' % (
                 e(res['when']), res['layer'], e(res['model'].get('device', '')), e(res['model'].get('dtype', '')),
                 e(LICENCE['name']), res['radius'],
                 (' (%s)' % e(json.dumps(C))) if C else ' (no calibration yet: distances only)'))
    H.append('<h2>Worst view per region</h2><table><tr><th>region</th><th>scale</th><th>view</th><th>distance</th>'
             '<th>p90</th><th>score</th><th>grade</th></tr>')
    for r in res['summary']:
        H.append('<tr><td>%s</td><td>%s</td><td>%s</td><td>%.3f</td><td>%.3f</td><td>%s</td><td style="color:%s">%s</td></tr>' % (
            r['region'], r['scale'], r['view'], r['dist'], r['p90'], '' if r['score'] is None else '%.3f' % r['score'],
            G[r['grade']], r['grade']))
    H.append('</table><p class="note">Heat maps: the design | ours | ours under the per-patch distance (transparent '
             'below 0.1, yellow to red to magenta at 0.45; the design\'s outline in blue).</p><img src="legend.png">')
    for sc in ('head', 'body'):
        for v, en in (res['scales'].get(sc) or {}).items():
            if 'picture' not in en:
                continue
            H.append('<h2>%s scale, %s</h2>' % (sc, v.replace('_', '-')))
            cap = ('silhouette IoU with the design %.3f; registration (board against our z-buffer) %s; %s; board %s at '
                   '%s deg, the design at %s deg; whole-figure distance %.3f' % (
                       en['iou'], en['registration_iou'], en['how'], en['board'], en['az_board'], en['az_design'],
                       en['whole']))
            H.append('<figure><a href="%s"><img src="%s"></a><figcaption>%s</figcaption></figure>' % (
                en['picture'], en['picture'], e(cap)))
            H.append('<table><tr><th>region</th><th>distance</th><th>p90</th><th>patches</th><th>score</th><th>grade</th>'
                     '<th>layer 18</th></tr>')
            for reg, r in sorted(en['regions'].items(), key=lambda kv: -kv[1]['dist']):
                H.append('<tr><td>%s%s</td><td>%.3f</td><td>%.3f</td><td>%.1f</td><td>%s</td><td style="color:%s">%s</td>'
                         '<td>%s</td></tr>' % (reg, '' if r['graded_here'] else ' <small>(graded at the other scale)</small>',
                                               r['dist'], r['p90'], r['patches'], '' if r['score'] is None else
                                               '%.3f' % r['score'], G[r['grade']], r['grade'],
                                               '' if r.get('dist_l18') is None else '%.3f' % r['dist_l18']))
            H.append('</table>')
    open(os.path.join(out, 'index.html'), 'w').write('\n'.join(H))
    return os.path.join(out, 'index.html')


# ------------------------------------------------------------------------------------------------------------ calibration
LABELS = 'charkit/refs/clawd/perceptual_labels.json'
GROUPS = {'face': 'face', 'eyes': 'face', 'neck': 'face', 'hair': 'hair', 'accessories': 'accessories',
          'collar': 'garment', 'bow': 'garment', 'top': 'garment', 'skirt': 'garment', 'flaps': 'garment',
          'arms': 'limbs', 'legs': 'limbs', 'boots': 'limbs'}
FLOOR_Q = 0.1                    # a (scale, view, region)'s floor: this quantile of its distance over the pool's builds
RIDGE = 0.5                      # the weights' pull toward 1 (log-weights, per group): the set is small


def _build_dir(labels, name):
    b = labels['builds'].get(name)
    if not b:
        return None
    return os.path.join(os.path.dirname(ROOT), b['worktree'], b['out'])


def _result(build, rescore=False, log=print):
    p = os.path.join(_p(build), 'perceptual', 'perceptual.json')
    if os.path.exists(p) and not rescore:
        return json.load(open(p))
    return run(build, calib=None, log=log)


def _dist(res, scale, view, region, layer=None):
    e = ((res.get('scales') or {}).get(scale) or {}).get(view)
    r = (e or {}).get('regions', {}).get(region)
    if not r or r['patches'] < MIN_PATCHES:
        return None
    return r['dist'] if layer is None else r.get('dist_l%d' % layer)


def floors(results, q=FLOOR_Q, layer=None):
    """per (scale, view, region): the q-quantile of the region's distance over the builds (the drawn-against-rendered
    gap every build pays), and per (scale, region) over all views as the fallback."""
    got = {}
    for res in results:
        for sc, vs in (res.get('scales') or {}).items():
            for v, e in vs.items():
                for reg in e['regions']:
                    d = _dist(res, sc, v, reg, layer)
                    if d is not None:
                        got.setdefault('%s/%s/%s' % (sc, v, reg), []).append(d)
                        got.setdefault('%s/*/%s' % (sc, reg), []).append(d)
    return {k: round(float(np.quantile(v, q)), 4) for k, v in got.items()}


def label_values(lab, res, F, layer=None):
    """a label's distance less its floor at its region's graded scale, per view it names ('*': every view measured)
    -> {view: value}."""
    sc = PRIMARY.get(lab['region'], 'body')
    views = list(SCALES[sc]['views']) if lab['view'] == '*' else [lab['view']]
    out = {}
    for v in views:
        d = _dist(res, sc, v, lab['region'], layer)
        if d is None:
            continue
        fl = F.get('%s/%s/%s' % (sc, v, lab['region']), F.get('%s/*/%s' % (sc, lab['region']), 0.0))
        out[v] = d - fl
    return out


def _scores(X, idx, theta):
    """labels' scores: each group's weight (exp theta) times its value, the worst view where a label names none."""
    return np.array([max(np.exp(theta[g]) * x for x in xs) for xs, g in zip(X, idx)])


def fit_weights(X, sev, idx, ng, ridge=RIDGE):
    """log-weights per group that rank the labels by severity: a pairwise logistic loss over every pair of labels whose
    severities differ, plus a ridge toward weight 1. -> theta (ng,)."""
    from scipy.optimize import minimize
    sev = np.asarray(sev, float)
    P = [(i, j) for i in range(len(sev)) for j in range(len(sev)) if sev[i] > sev[j]]
    if not P:
        return np.zeros(ng)
    base = _scores(X, idx, np.zeros(ng))
    tau = max(float(np.std(base)), 1e-3)

    def loss(th):
        y = _scores(X, idx, th)
        m = np.array([(y[i] - y[j]) / tau for i, j in P])
        return float(np.mean(np.logaddexp(0, -m))) + ridge * float(np.sum(th ** 2)) / ng
    r = minimize(loss, np.zeros(ng), method='Nelder-Mead', options=dict(maxiter=4000, xatol=1e-4, fatol=1e-7))
    return r.x


def fit_limits(y, sev):
    """the WARN and FAIL limits: each the cut between sorted scores that best separates the labels below it from those
    at or above it (praised from flagged; severe from the rest), by balanced accuracy, placed half way. -> dict."""
    y, sev = np.asarray(y, float), np.asarray(sev)

    def cut(pos):
        if pos.all() or not pos.any():
            return None
        cands = np.unique(y)
        mids = (cands[:-1] + cands[1:]) / 2
        best = None
        for c in mids:
            acc = 0.5 * ((y[pos] >= c).mean() + (y[~pos] < c).mean())
            if best is None or acc > best[0] + 1e-9:
                best = (acc, c)
        return round(float(best[1]), 4) if best else None
    warn, fail = cut(sev >= 1), cut(sev >= 3)
    if warn is None:
        warn = fail if fail is not None else 0.0
    if fail is None or fail < warn:
        fail = warn
    return dict(warn=warn, fail=fail)


def _grade_of(y, lim):
    return 'FAIL' if y >= lim['fail'] else 'WARN' if y >= lim['warn'] else 'PASS'


def _caught(sev, g):
    return {3: g == 'FAIL', 2: g in ('WARN', 'FAIL'), 1: g in ('WARN', 'FAIL'), 0: g == 'PASS'}[sev]


def _spearman(a, b):
    from scipy.stats import spearmanr
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3 or np.all(a == a[0]) or np.all(b == b[0]):
        return None
    r = spearmanr(a, b)
    return dict(rho=round(float(r.correlation), 3), p=round(float(r.pvalue), 4), n=int(len(a)))


def calibrate(labels_path=LABELS, builds=None, pool=(), out='charkit/out/perceptual_calibration', write=None,
              rescore=False, log=print):
    """score every labelled build (and the pool's, for the floors), fit the weights and limits, validate by leave-one-
    out -> the report dict (out/calibration.json, out/index.html); write: also save the calibration there (the
    tracked charkit/refs/clawd/perceptual_calibration.json)."""
    labels = json.load(open(_p(labels_path)))
    dirs = {k: _build_dir(labels, k) for k in labels['builds']}
    dirs.update(builds or {})
    out = _p(out)
    os.makedirs(os.path.join(out, 'img'), exist_ok=True)
    R, missing = {}, []
    for k, d in dirs.items():
        if d and os.path.isdir(_p(d)):
            log('scoring %s (%s)' % (k, d))
            R[k] = _result(d, rescore, log)
        else:
            missing.append(k)
    pool_res = []
    for d in pool:
        if os.path.isdir(_p(d)):
            log('scoring pool build %s' % d)
            pool_res.append(_result(d, rescore, log))
    allres = list(R.values()) + pool_res
    report = dict(labels=labels_path, model=MODEL, licence=LICENCE, layer=LAYERS[0], builds={k: dirs[k] for k in R},
                  missing_builds=missing, pool=list(pool), floor_quantile=FLOOR_Q, ridge=RIDGE, variants={})
    names = sorted(set(GROUPS.values()))

    def evaluate(layer, use_floors, tag):
        F = floors(allres, layer=layer) if use_floors else {}
        rows, X, sev, idx = [], [], [], []
        for lab in labels['labels']:
            res = R.get(lab['build'])
            vals = label_values(lab, res, F, layer) if res else {}
            if not vals:
                rows.append(dict(lab, usable=False, why='no %s measure of %s on %s' % (
                    PRIMARY.get(lab['region'], 'body'), lab['region'], lab['build'])))
                continue
            rows.append(dict(lab, usable=True, values={v: round(x, 4) for v, x in vals.items()}))
            X.append(list(vals.values())); sev.append(lab['severity']); idx.append(names.index(GROUPS[lab['region']]))
        n = len(X)
        th = fit_weights(X, sev, idx, len(names))
        y_in = _scores(X, idx, th)
        y0 = _scores(X, idx, np.zeros(len(names)))
        lim = fit_limits(y_in, sev)
        y_loo, g_loo = np.zeros(n), []
        for i in range(n):
            keep = [j for j in range(n) if j != i]
            th_i = fit_weights([X[j] for j in keep], [sev[j] for j in keep], [idx[j] for j in keep], len(names))
            y_all = _scores(X, idx, th_i)
            lim_i = fit_limits(y_all[keep], [sev[j] for j in keep])
            y_loo[i] = y_all[i]
            g_loo.append(_grade_of(y_all[i], lim_i))
        k = 0
        for r in rows:
            if not r['usable']:
                continue
            r.update(raw=round(float(max(r['values'].values())), 4), score=round(float(y_in[k]), 4),
                     score_unweighted=round(float(y0[k]), 4), grade=_grade_of(y_in[k], lim), score_loo=round(float(y_loo[k]), 4),
                     grade_loo=g_loo[k], caught=_caught(r['severity'], _grade_of(y_in[k], lim)),
                     caught_loo=_caught(r['severity'], g_loo[k]),
                     worst_view=max(r['values'], key=r['values'].get))
            k += 1
        geo = {'PASS': 0, 'INFO': 0, 'WARN': 1, 'FAIL': 2}
        use = [r for r in rows if r['usable']]
        V = dict(floors=F, weights={g: round(float(np.exp(t)), 3) for g, t in zip(names, th)}, limits=lim,
                 rho_unweighted=_spearman(y0, sev), rho_in=_spearman(y_in, sev), rho_loo=_spearman(y_loo, sev),
                 rho_geometric=_spearman([geo.get(r['check']['status'], 0) for r in use], [r['severity'] for r in use]),
                 caught=sum(r['caught'] for r in use), caught_loo=sum(r['caught_loo'] for r in use), n=n, rows=rows)
        # the pairs: a praised improvement must lower the distance
        PR = []
        for pq in labels.get('pairs', []):
            a, b = R.get(pq['better']), R.get(pq['worse'])
            if not a or not b:
                continue
            lab = dict(region=pq['region'], view=pq['view'])
            va, vb = label_values(lab, a, F, layer), label_values(lab, b, F, layer)
            if va and vb:
                PR.append(dict(pq, better_value=round(max(va.values()), 4), worse_value=round(max(vb.values()), 4),
                               agrees=max(va.values()) < max(vb.values())))
        V['pairs'] = PR
        report['variants'][tag] = V
        return V
    main_v = evaluate(None, True, 'layer24_floors')
    evaluate(None, False, 'layer24_raw')
    evaluate(LAYERS[1], True, 'layer18_floors')
    extra = [l for l in labels['labels'] if l.get('extra')]
    if extra:
        keep = dict(labels)
        labels = dict(labels, labels=[l for l in labels['labels'] if not l.get('extra')])
        evaluate(None, True, 'layer24_floors_brief_only')
        labels = keep
    cal = dict(model=MODEL, layer=LAYERS[0], radius=RADIUS, floors=main_v['floors'],
               weights={reg: main_v['weights'][GROUPS[reg]] for reg in REGIONS}, groups=GROUPS, limits=main_v['limits'],
               fitted=dict(when=time.strftime('%Y-%m-%d'), labels=main_v['n'], rho_in=main_v['rho_in'],
                           rho_loo=main_v['rho_loo'], labels_file=labels_path))
    report['calibration'] = cal
    json.dump(report, open(os.path.join(out, 'calibration.json'), 'w'), indent=1)
    if write:
        json.dump(cal, open(_p(write), 'w'), indent=1)
    calibration_page(report, R, dirs, out)
    for tag, V in report['variants'].items():
        log('%-26s n=%d  rho unweighted %s  in-sample %s  LOO %s  geometric %s  caught %d / LOO %d' % (
            tag, V['n'], (V['rho_unweighted'] or {}).get('rho'), (V['rho_in'] or {}).get('rho'),
            (V['rho_loo'] or {}).get('rho'), (V['rho_geometric'] or {}).get('rho'), V['caught'], V['caught_loo']))
    return report


def calibration_page(report, R, dirs, out):
    """out/index.html: the labels with their scores and the geometric checks' verdicts, the fit's numbers, and each
    flag's heat map (our render under the distance beside the design)."""
    e = html.escape
    V = report['variants']['layer24_floors']
    G = {'PASS': '#2e7d32', 'WARN': '#b26a00', 'FAIL': '#c62828', 'INFO': '#666'}
    H = ['<!doctype html><meta charset="utf-8"><title>Perceptual calibration</title><style>',
         'body{font:14px/1.45 -apple-system,system-ui,sans-serif;margin:24px;background:#f4f3f1;color:#222}',
         'h1{font-size:22px}h2{font-size:18px;margin-top:30px}table{border-collapse:collapse;font-size:13px;margin:6px 0}',
         'td,th{border:1px solid #ccc;padding:3px 7px;text-align:right;vertical-align:top}th:first-child,td:first-child,td.l{text-align:left}',
         'img{border:1px solid #ccc;background:#fff;display:block;max-width:100%}.note{max-width:1100px;color:#444}',
         'figure{display:inline-block;margin:0 14px 18px 0;vertical-align:top}figcaption{font-size:12px;color:#555;max-width:1000px}',
         '</style><h1>The perceptual metric against Michael\'s severity calls</h1>']
    H.append('<p class="note">%d labels (%s). Severity 0 praised, 1 mild, 2 moderate, 3 severe. Raw: the region\'s DINOv3 '
             'distance less its floor (the pool\'s %d%% quantile for that scale, view and region: the drawn-against-'
             'rendered gap every build pays), at the region\'s graded scale, the worst view where the flag names none. '
             'Score: raw x the region group\'s fitted weight. LOO: each label scored by weights and limits fitted without '
             'it. The geometric column is what the QA said of the same thing on that build.</p>' % (
                 V['n'], e(report['labels']), int(report['floor_quantile'] * 100)))
    H.append('<table><tr><th>variant</th><th>n</th><th>rho unweighted</th><th>rho in-sample</th><th>rho LOO</th>'
             '<th>rho geometric checks</th><th>caught</th><th>caught LOO</th><th>weights</th><th>limits</th></tr>')
    for tag, W in report['variants'].items():
        f = lambda r: '' if not r else '%.3f (p %.3f)' % (r['rho'], r['p'])
        H.append('<tr><td>%s</td><td>%d</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%d</td><td>%d</td><td class="l">%s</td>'
                 '<td class="l">%s</td></tr>' % (tag, W['n'], f(W['rho_unweighted']), f(W['rho_in']), f(W['rho_loo']),
                                                 f(W['rho_geometric']), W['caught'], W['caught_loo'],
                                                 e(json.dumps(W['weights'])), e(json.dumps(W['limits']))))
    H.append('</table><h2>The labels</h2><table><tr><th>flag</th><th>build</th><th>view</th><th>region</th><th>severity</th>'
             '<th>raw</th><th>score</th><th>grade</th><th>LOO score</th><th>LOO grade</th><th>geometric check</th>'
             '<th>Michael</th></tr>')
    for r in V['rows']:
        if not r['usable']:
            H.append('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%d</td><td colspan="5" class="l">%s</td><td></td>'
                     '<td class="l">%s</td></tr>' % (r['id'], r['build'], r['view'], r['region'], r['severity'],
                                                     e(r['why']), e(r['quote'])))
            continue
        ck = r['check']
        H.append('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%d</td><td>%.3f</td><td>%.3f</td><td style="color:%s">%s</td>'
                 '<td>%.3f</td><td style="color:%s">%s%s</td><td class="l">%s %s <b style="color:%s">%s</b></td><td class="l">%s</td></tr>' % (
                     r['id'], r['build'], r['view'] + ('' if r['view'] != '*' else ' (%s)' % r['worst_view']), r['region'],
                     r['severity'], r['raw'], r['score'], G[r['grade']], r['grade'], r['score_loo'], G[r['grade_loo']],
                     r['grade_loo'], '' if r['caught_loo'] else ' (miss)', e(ck['name']), e(json.dumps(ck['value'])),
                     G.get(ck['status'], '#666'), ck['status'], e(r['quote'])))
    H.append('</table>')
    if V['pairs']:
        H.append('<h2>Praised improvements</h2><table><tr><th>pair</th><th>region</th><th>better build</th><th>value</th>'
                 '<th>worse build</th><th>value</th><th>agrees</th></tr>')
        for q in V['pairs']:
            H.append('<tr><td>%s</td><td>%s</td><td>%s</td><td>%.3f</td><td>%s</td><td>%.3f</td><td>%s</td></tr>' % (
                q['id'], q['region'], q['better'], q['better_value'], q['worse'], q['worse_value'], q['agrees']))
        H.append('</table>')
    H.append('<h2>Each flag: the design | ours | ours under the distance</h2><img src="img/legend.png">')
    for r in V['rows']:
        if not r['usable']:
            continue
        sc = PRIMARY.get(r['region'], 'body')
        v = r['view'] if r['view'] != '*' else r['worst_view']
        src = os.path.join(_p(dirs[r['build']]), 'perceptual', 'heat_%s_%s.png' % (sc, v))
        if not os.path.exists(src):
            continue
        dst = 'img/%s_%s_%s.png' % (r['build'], sc, v)
        shutil.copy(src, os.path.join(out, dst))
        H.append('<figure><a href="%s"><img src="%s" style="max-height:640px"></a><figcaption>%s: %s (severity %d), %s %s '
                 'at the %s scale; raw %.3f, score %.3f %s; LOO %s. Geometric: %s %s %s</figcaption></figure>' % (
                     dst, dst, e(r['id']), e(r['quote']), r['severity'], r['region'], v, sc, r['raw'], r['score'],
                     r['grade'], r['grade_loo'], e(r['check']['name']), e(json.dumps(r['check']['value'])),
                     r['check']['status']))
    _save(os.path.join(out, 'img', 'legend.png'), legend())
    open(os.path.join(out, 'index.html'), 'w').write('\n'.join(H))


# ------------------------------------------------------------------------------------------------------------ remote
def remote(build, args, log=print):
    """from the laptop: the build's boards, bundle, spec and trace sent to the render box (infra/gcp/render.env), the
    pass run there in this worktree's synced copy, its output fetched back into BUILD/perceptual."""
    from . import remote as R
    R.BOX['env'] = os.path.join(ROOT, 'infra', 'gcp', 'render.env')
    build = _p(build).rstrip('/')
    name = os.path.basename(build)
    wt = '/srv/work/%s' % os.path.basename(ROOT)
    dst = '%s/charkit/out/perceptual_in/%s' % (wt, name)
    R.up()
    R._sh('sync', ROOT)
    R._sh('ssh', 'mkdir -p %s/boards %s/charkit/out/clawd/outfit' % (dst, wt))
    om = os.path.join(ROOT, 'charkit', 'out', 'clawd', 'outfit')
    if os.path.isdir(om):
        R._sh('push', om + '/', '%s/charkit/out/clawd/outfit/' % wt)
    for f in ('boards', 'bundle'):
        if os.path.isdir(os.path.join(build, f)):
            R._sh('push', os.path.join(build, f) + '/', '%s/%s/' % (dst, f))
    for f in os.listdir(build):
        if f.endswith('.spec.json') or f == 'trace.jsonl':
            R._sh('push', os.path.join(build, f), '%s/%s' % (dst, f))
    rel = 'charkit/out/perceptual_in/%s' % name
    code = R._sh('run', ROOT, 'python -m charkit perceptual %s %s' % (rel, ' '.join(args)), check=False)
    cfg = os.path.expanduser('~/.ssh/charkit-%s.config' % R._box_name())
    os.makedirs(os.path.join(build, 'perceptual'), exist_ok=True)
    subprocess.run(['rsync', '-az', '-e', 'ssh -F %s' % cfg, '%s:%s/perceptual/' % (R._box_name(), dst),
                    os.path.join(build, 'perceptual') + '/'], check=False)
    log('perceptual (render box): exit %d, fetched into %s/perceptual' % (code, build))
    return code


def main(args):
    if args and args[0] == 'features':
        return _features_main(args[1], args[2])
    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    if '--calibrate' in args:
        builds = dict(a.split('=', 1) for i, a in enumerate(args) if i and args[i - 1] == '--build')
        pool = [a for i, a in enumerate(args) if i and args[i - 1] == '--pool']
        r = calibrate(opt('--calibrate'), builds, pool, out=opt('--out', 'charkit/out/perceptual_calibration'),
                      write=opt('--write'), rescore='--rescore' in args)
        return 0 if r else 1
    build = args[0]
    if '--remote' in args:
        return remote(build, [a for a in args[1:] if a != '--remote'])
    res = run(build, opt('--out'), opt('--spec', 'charkit/spec/clawd.json'), pictures='--no-page' not in args,
              scales=DEFAULT_SCALES + (('body_hi',) if '--hi' in args else ()))
    for r in res['summary']:
        print('  %-12s %-5s %-14s dist %.3f  p90 %.3f  %s %s' % (r['region'], r['scale'], r['view'], r['dist'], r['p90'],
                                                             '' if r['score'] is None else 'score %.3f' % r['score'],
                                                             r['grade']))
    if '--open' in args:
        subprocess.run(['open', os.path.join(opt('--out') or os.path.join(_p(build), 'perceptual'), 'index.html')])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]) or 0)
