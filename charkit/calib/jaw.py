"""Calibration adapter for the jaw, the chin, the three-quarter's jaw and the neck under it (charkit.faceregion, part
face_region: jaw_compare's and taper_compare's checks, and jaw_outline_hidden, Michael's flag on the face curving in
under the head sheet's hair).

The stand-in for ours: the head sheet's own pictures on the jaw window (faceregion.design_jaw_views: the classes the
design's measures read, at the sheet's px per L, round the eyes' point as ours are registered), moved (dy, dx) px, in
place of each of ours' cameras: the level camera's picture, the bare one (ours with the hair hidden) and the boards'.
The design keeps its hair in the bare one: its measures read it only where its hair leaves the face's edge in view, and
ours on the same rows. jaw_outline_hidden holds ours' bare front to head_construction's outline (the bald head) under the
sheet's hair, so its stand-in for ours' bare front is head_construction's face region, registered on the sheet as the
check registers it (rows scaled sz about the eye line so the chins meet, widths sx about the chin's column) and
rasterised at the sheet's px per L (the region's mask, linearly resampled: the construction is drawn at 2.3x the sheet's
px per L, and nearest sampling would break its 2-3 px lines).

Floors (random stand-ins for ours, each view's picture and the construction's region transformed alike, SEEDS seeds).
A generator is a check's floor when it moves what the check reads:
  affine_jaw   a sloppy fit: the pictures under a random affine about the eyes' point, widths and heights each scaled
               8-15% up or down (independently) and sheared 0.08-0.15 (x += k z). Moves the widths, the chin's height,
               the V's rise and opening, the neck's width against the face's, the underside's angle, the outline under
               the hair. (w(t)/w(0) on the design's rows mostly can't be read under it: the hair's edge moves over z0)
  widths_jaw   the widths re-proportioned (the shape analog of affine_jaw): each row from the eye line to the chin
               stretched across about the chin's column by 1 + A g(t), A 8-15%, g a random smooth curve zero at the
               eye line (the eyes kept), free at the chin (the V's arms stretched too). Moves everything read on the
               outline's widths and slopes; not the chin's height
  warp_jaw     a wobbly jaw: the pictures displaced by a smooth random field, across by a sum of three sines down the
               face (0.004-0.008 L each, wavelengths 0.06-0.2 L) and down by three across it; folds kept out (the
               field's slope under 0.5). Local shape: the floor (informational) of the detectors of a local defect
               (a kink, a hollow, a notch, a wiggle, a blunt tip). A shift across per row leaves a width as it was (the
               half-width is the two sides' mean), so it isn't the widths' floor
  other_view   another view's jaw: the front's picture in place of the three-quarter's (and the three-quarter's, mirrored
               to face the front's way, in place of the front's), shifted 0-3 px (seeds); the profile and head_construction
               kept. A jaw drawn, but not this view's. (The chin's height is the same in every view; w(t)/w(0) can't be
               read on it: the three-quarter's hair covers the front's row z0)

Kinds: a check graded against the design's own value (a difference or a ratio) is an agreement ('shape': a random
stand-in must not pass it); one graded against an absolute limit, written for one flagged defect, is a detector
('defect': a random stand-in lacks the defect and may pass; its known-bad must fail). The face's outline has no per-view
shape IoU check for the anti-gaming guard to read: `shape` is empty (jaw_taper_shape and jaw_outline_hidden are the
outline's agreement checks).

Known-bads (stored with `calibrate store`, measured with this tree's code; charkit/calib/known_bad/NAME.json):
  jaw0_flagged  jaw_0: the MakeHuman head on the authored body (clawd_body.json at 91e44ca), the build Michael flagged
                (2026-09-29: the chin and neck "still very obviously visually glitched": the face running straight into
                a neck as wide as the lower face, no chin point, no jaw line, the neck's front wiggling in profile)
  jaw4_review   jaw_4: tool/face round 2 (pipeline-3d 5cb5256 merged), the round Michael reviewed (2026-09-30): in front
                "a U, not a V"; in three-quarter a hollow under the cheek and a notch where the jaw meets the neck. In
                the level camera (the design's projection, how the taper checks grade since face5) its front reads
                jaw_taper_shape 0.0197 PASS, chin_angle 127.7 PASS, chin_tip 0.651 WARN: the U Michael saw was mostly
                the boards' camera looking down at the chin (face.md, "What the U is"). It stands for the three-quarter's
                defects and the jaw lines' kink; jaw0_flagged for the front's V
  f5_base       f5_before: pipeline-3d d60486a, face5's base: the face curving in where the head sheet's side locks cover
                its edge (Michael, 2026-09-30; jaw_outline_hidden's flag)
"""
import numpy as np

CALIBRATION = [
    # agreement with the design (graded on a difference or ratio to the design's value; better None where it's two-sided:
    # ours' value either side of the design's reads worse)
    dict(check='jaw_outline_hidden', part='face_region', adapter='Jaw', known_bad='f5_base',
         baseline=['affine_jaw', 'widths_jaw'], shape=[], better='lower'),
    dict(check='jaw_taper', part='face_region', adapter='Jaw', known_bad='jaw0_flagged',
         baseline=['affine_jaw', 'widths_jaw', 'other_view'], shape=[], better='lower'),
    dict(check='chin_point_z', part='face_region', adapter='Jaw', known_bad='jaw0_flagged',
         baseline=['affine_jaw'], shape=[], better=None),
    dict(check='chin_v', part='face_region', adapter='Jaw', known_bad='jaw0_flagged',
         baseline=['affine_jaw', 'widths_jaw', 'other_view'], shape=[], better=None),
    dict(check='neck_to_face', part='face_region', adapter='Jaw', known_bad='jaw0_flagged',
         baseline=['affine_jaw', 'widths_jaw', 'other_view'], shape=[], better=None),
    dict(check='chin_underside', part='face_region', adapter='Jaw', known_bad='jaw0_flagged',
         baseline=['affine_jaw', 'widths_jaw'], shape=[], better=None),
    dict(check='jaw_taper_shape', part='face_region', adapter='Jaw', known_bad='jaw0_flagged',
         baseline=['widths_jaw'], shape=[], better='lower'),
    dict(check='chin_angle', part='face_region', adapter='Jaw', known_bad='jaw0_flagged',
         baseline=['affine_jaw', 'widths_jaw', 'other_view'], shape=[], better=None),
    # detectors of one flagged defect (graded on an absolute limit): a blunt tip, a kink, a hollow, a notch, a wiggle, a
    # missing jaw line
    dict(check='chin_tip', part='face_region', adapter='Jaw', known_bad='jaw0_flagged', kind='defect',
         baseline=['widths_jaw', 'warp_jaw', 'other_view'], shape=[], better='higher'),
    dict(check='jaw_line_bend', part='face_region', adapter='Jaw', known_bad='jaw4_review', kind='defect',
         baseline=['warp_jaw', 'other_view'], shape=[], better='lower'),
    dict(check='tq_cheek_hollow', part='face_region', adapter='Jaw', known_bad='jaw4_review', kind='defect',
         baseline=['warp_jaw'], shape=[], better='lower'),
    dict(check='tq_jaw_notch', part='face_region', adapter='Jaw', known_bad='jaw4_review', kind='defect',
         baseline=['warp_jaw'], shape=[], better='lower'),
    dict(check='neck_front_wiggle', part='face_region', adapter='Jaw', known_bad='jaw0_flagged', kind='defect',
         baseline=['warp_jaw'], shape=[], better='lower'),
    dict(check='jaw_line_front', part='face_region', adapter='Jaw', known_bad='jaw0_flagged', kind='defect',
         baseline=['affine_jaw', 'other_view'], shape=[], better='higher'),
    dict(check='jaw_line_three_quarter', part='face_region', adapter='Jaw', known_bad='jaw0_flagged', kind='defect',
         baseline=['affine_jaw', 'other_view'], shape=[], better='higher'),
]

AFFINE_S = (0.08, 0.15)             # |scale - 1|, widths and heights independently
AFFINE_K = (0.08, 0.15)             # |shear| (x += k z)
WARP_A = (0.004, 0.008)             # L: each sine's amplitude
WARP_LAMBDA = (0.06, 0.2)           # L: each sine's wavelength
WARP_SLOPE = 0.5                    # the field's largest slope (no folds)
VIEWS = ('front', 'three_quarter', 'profile')


def _rng(kind, seed):
    return np.random.default_rng({'affine_jaw': 4100, 'warp_jaw': 4200, 'other_view': 4300, 'widths_jaw': 4400}.get(
        kind, 4000) + int(seed))


def _grid(shape, ppl, win):
    H, W = shape
    z = win['top'] - (np.arange(H) + 0.5) / ppl
    u = (np.arange(W) + 0.5) / ppl - win['x']
    return np.meshgrid(u, z)


def _sample(img, ppl, win, us, zs, order):
    """img (on the jaw window at ppl) read at the points (us, zs) (L): order 0 nearest (classes), 1 linear (a mask's
    share) -> array of us' shape, 0 outside."""
    from scipy import ndimage
    r = (win['top'] - zs) * ppl - 0.5
    c = (us + win['x']) * ppl - 0.5
    return ndimage.map_coordinates(img, [r, c], order=order, mode='constant', cval=0)


def _warp(img, ppl, win, back, order=0, mask=False):
    """img remapped: each pixel of the output reads img at back(u, z) (the output's point -> the input's, L)."""
    U, Z = _grid(img.shape, ppl, win)
    us, zs = back(U, Z)
    if mask:
        return _sample(img.astype(float), ppl, win, us, zs, 1) >= 0.5
    return _sample(img, ppl, win, us, zs, 0).astype(img.dtype)


def _sines(rng):
    """a smooth random field of one variable: three sines, amplitudes WARP_A, wavelengths WARP_LAMBDA, slope capped."""
    a = rng.uniform(*WARP_A, 3) * rng.choice((-1, 1), 3)
    lam = rng.uniform(*WARP_LAMBDA, 3)
    ph = rng.uniform(0, 2 * np.pi, 3)
    slope = float(np.sum(np.abs(a) * 2 * np.pi / lam))
    if slope > WARP_SLOPE:
        a = a * WARP_SLOPE / slope
    return lambda x: sum(a[i] * np.sin(2 * np.pi * x / lam[i] + ph[i]) for i in range(3))


class Jaw:
    part = 'face_region'
    generators = {
        'affine_jaw': "each view's picture (and head_construction's region) under a random affine about the eyes' point: "
                      "widths and heights scaled 8-15% up or down independently, sheared 0.08-0.15",
        'warp_jaw': "each view's picture (and head_construction's region) displaced by a smooth random field: three sines "
                    "0.004-0.008 L, wavelengths 0.06-0.2 L, across and down (slope under 0.5)",
        'widths_jaw': "the face's widths re-proportioned: each row from the eye line to the design's chin stretched across "
                      "about the chin's column by 1 + A g(t) (t 0 at the eye line, 1 at the chin; A 8-15%; g a random "
                      "smooth curve, three sines sin(pi (i + 1/2) t), zero at the eye line, its largest 1)",
        'other_view': "another view's jaw: the front's picture for the three-quarter's, the three-quarter's (mirrored) for "
                      "the front's, shifted 0-3 px; the profile kept",
    }

    def __init__(self, B, design):
        self.B, self.design = B, design
        self._d = None

    # ------------------------------------------------------------------------------------------------- the design
    def _setup(self):
        if self._d is not None:
            return self._d
        from scipy import ndimage
        from .. import faceregion as fr, manifest, refcheck
        B = self.B
        ex = B.assembly['eye_knobs']['x']
        facing = (B.spec.get('ref') or {}).get('face_sheet', {}).get('facing', -1)
        D, ppl, cls, az = self.design.memo(fr.design_jaw, B.spec, ex)
        win = fr.JAW_WIN
        cons = None
        H = (D.get('front') or {}).get('hidden')
        if H:
            M = manifest.load(B.spec['ref']['manifest'])['references']
            Vc, pc = fr.design_jaw_views(refcheck._load(M[fr.CONS_REF]['path']), ex, facing, which=('front',))
            clsc = Vc['front']['cls']
            region = ndimage.binary_fill_holes(fr._region(clsc, fr.FACE_SEEDS, pc, win))
            uc, _ = H['chin']                                          # (the construction's chin, its own px per L)
            ut = D['front']['chin'][0]                                 # (the sheet's chin column)
            sx, sz = H['sx'], H['sz']
            U, Z = _grid(cls['front'].shape, ppl, win)
            share = _sample(region.astype(float), pc, win, uc + (U - ut) / sx, Z / sz, 1)
            cons = np.where(share >= 0.5, 1, 0).astype(cls['front'].dtype)       # (skin: bodyqa.CLASS['skin'] 1)
        self._d = dict(D=D, ppl=ppl, cls=cls, az=az, facing=facing, cons=cons, win=win,
                       chin_z=(D.get('front') or {}).get('chin', (0, None))[1],
                       z0=((D.get('front') or {}).get('taper') or {}).get('z0'),
                       tq_top=((D.get('three_quarter') or {}).get('taper') or {}).get('top'))
        return self._d

    def standins(self, kind, arg):
        """the stand-in's pictures {view: classes, 'cons': head_construction's region (or None)} for a kind: 'design'
        (arg (dy, dx) px) or a floor generator (arg a seed)."""
        from .labels import _shift
        d = self._setup()
        S = dict(d['cls'], cons=d['cons'])
        ppl, win = d['ppl'], d['win']
        if kind == 'design':
            dy, dx = arg
            return {k: None if v is None else _shift(v, dy, dx, 0) for k, v in S.items()}
        rng = _rng(kind, arg)
        if kind == 'affine_jaw':
            sx = 1 + rng.uniform(*AFFINE_S) * rng.choice((-1, 1))
            sz = 1 + rng.uniform(*AFFINE_S) * rng.choice((-1, 1))
            sh = rng.uniform(*AFFINE_K) * rng.choice((-1, 1))
            back = lambda U, Z: ((U - sh * Z) / sx, Z / sz)              # (out (u, z) = (sx u + sh z, sz z))
        elif kind == 'warp_jaw':
            fx, fz = _sines(rng), _sines(rng)
            back = lambda U, Z: (U - fx(Z), Z - fz(U))
        elif kind == 'widths_jaw':
            amp = rng.uniform(*AFFINE_S) * rng.choice((-1, 1))
            c = rng.normal(size=3)
            tt = np.linspace(0, 1, 201)
            g = lambda t: sum(c[i] * np.sin(np.pi * (i + 0.5) * t) for i in range(3))
            c = c / np.abs(g(tt)).max()
            uc, zc = d['D']['front']['chin']
            back = lambda U, Z: (uc + (U - uc) / (1 + amp * g(np.clip(Z / zc, 0, 1))), Z)
        elif kind == 'other_view':
            dy, dx = (int(v) for v in rng.integers(-3, 4, 2))
            out = dict(S)
            out['three_quarter'] = _shift(S['front'], dy, dx, 0)
            out['front'] = _shift(self._mirror(S['three_quarter']), dy, dx, 0)
            return out
        else:
            raise ValueError(kind)
        out = {}
        for k, v in S.items():
            if v is None:
                out[k] = None
            elif k == 'cons':                                          # (a mask: linearly resampled)
                out[k] = _warp(v, ppl, win, back, mask=True).astype(v.dtype)
            else:
                out[k] = _warp(v, ppl, win, back)
        return out

    def _mirror(self, img):
        """a picture mirrored about the eyes' point (u -> -u)."""
        d = self._setup()
        return _warp(img, d['ppl'], d['win'], lambda U, Z: (-U, Z))

    # ------------------------------------------------------------------------------- ours' measures from pictures
    def ours_from(self, S):
        """faceregion.ours_jaw's measures with the stand-in's pictures in place of ours' cameras (the level, the bare
        and the boards' each the view's picture; the bare front's outline for jaw_outline_hidden head_construction's)."""
        from .. import faceregion as fr
        d = self._setup()
        ppl = d['ppl']
        O = {}
        f = S.get('front')
        if f is not None:
            M = fr.jaw_front(f, ppl, d['chin_z'])
            M.update(jaw_line_L_board=M['jaw_line_L'], jaw_cols_board=M['jaw_cols'])
            M['half'] = fr.jaw_front(f, ppl)['half']
            c = S.get('cons')
            if c is not None:
                Mc = fr.jaw_front(c, ppl)
                if Mc.get('chin'):
                    ze, xl, xr = fr._outer(c, ppl, Mc['chin'])
                    M['extents'] = dict(z=ze, xl=xl, xr=xr)
            M['taper'] = M['taper_level'] = fr.taper_front(f, ppl, d['z0'])
            O['front'] = M
        q = S.get('three_quarter')
        if q is not None:
            M = fr.jaw_front(q, ppl)
            M.update(jaw_line_L_board=M['jaw_line_L'], jaw_cols_board=M['jaw_cols'])
            M['taper'] = M['taper_level'] = fr.tq_jaw(q, ppl, d['facing'], top=d['tq_top'])
            O['three_quarter'] = M
        if S.get('profile') is not None:
            O['profile'] = fr.jaw_profile(S['profile'], ppl)
        return O

    def checks(self, O):
        from .. import faceregion as fr
        d = self._setup()
        C = fr.jaw_compare(d['D'], O, d['ppl'])
        C.update(fr.taper_checks(d['D'], O))
        return C

    def run(self, kind, arg):
        return self.checks(self.ours_from(self.standins(kind, arg)))

    # ------------------------------------------------------------------------------------------ builds (ours)
    def measure(self, B):
        """a build's jaw checks with this tree's code (faceregion.jaw: the part's own jaw measures)."""
        from .. import faceregion as fr
        return fr.jaw(B)[1]
