"""Calibration adapter for Michael's face flags (charkit.faceflags, the QA part face_flags; tool/face6, 2026-09-30
evening review of preview 1580f95). The design stands in for ours: its own reads (head_turnaround's front,
three-quarter and profile; head_construction's front and profile) measured against themselves with the picture moved
1-2 px against the eyes ours is aligned on, or perturbed by a generator below; faceflags' own measuring code runs
unchanged on them. The known-bad is the build Michael flagged (face6_before: pipeline-3d 1580f95's preview).

Generators (the floor; seeded, each a random stand-in that must not pass):
  iris_scaled     each eye's iris scaled 1.25-1.6x (or 0.6-0.8x) in height about its middle, clipped to the opening
  lash_blocked    the upper lash line closed by a disk of 0.6-1.2 x its band (its spikes and gaps filled) and grown
                  0.3-0.8 x its band: a solid block, at random
  lash_smoothed   the upper lash line low-passed (a Gaussian of 0.6-1.2 x its band, cut at half): its thin spikes and
                  the gaps between its strokes gone
  brow_warped     each brow rebuilt from its centre line and thickness with its arch x (0.2-0.6 or 1.6-2.2), its
                  thickness x (0.45-0.7 or 1.5-2.0) and its length x 0.8-1.3
  mouth_warped    the mouth rebuilt from its centre line 0.5-0.75 as wide, 2.5-4 x as thick, its curve x (0-0.4 or
                  1.8-2.5)
  mouth_moved     the mouth moved 0.03-0.06 L up or down and 0.03-0.06 L across, at random
  nose_moved      the nose's mark moved 0.03-0.06 L in a random direction, 5-20% of its ink kept
  corner_moved    each eye's masks warped so its far corner moves 0.15-0.3 opening heights up or down (tool/face7)
  contour_moved   the face's leading contour at the mouth's rows moved 12-25% nearer or further (tool/face7)
  brow_lengthened each brow rebuilt 0.6-0.8x or 1.25-1.5x as long (tool/face7)
"""
import numpy as np

CALIBRATION = [
    dict(check='eye_iris_fit_*', part='face_flags', adapter='FaceFlags', known_bad='face6_before',
         baseline=['iris_scaled'], shape=['face_piece_iris'], better='lower'),
    dict(check='eye_lash_spikes_*', part='face_flags', adapter='FaceFlags', known_bad='face6_before',
         baseline=['lash_smoothed'], shape=['face_piece_lash'], better='higher'),
    dict(check='eye_lash_band_*', part='face_flags', adapter='FaceFlags', known_bad='face6_before',
         baseline=['lash_blocked'], shape=['face_piece_lash']),
    dict(check='eye_lash_gaps_*', part='face_flags', adapter='FaceFlags', known_bad='face6_before',
         baseline=['lash_smoothed'], shape=['face_piece_lash'], better='higher'),
    # tool/face7 (Michael's 2026-10-01 items on the face6 build, 52f6324's state: face7_before); before 'brow_*' (an
    # entry is the first that matches a name) and by exact names (a pattern needs the current build's qa.json to have it)
    dict(check='eye_corner_profile', part='face_flags', adapter='FaceFlags', known_bad='face7_before',
         baseline=['corner_moved'], shape=['face_piece_lash', 'face_piece_iris']),
    dict(check='eye_corner_closeup_profile', part='face_flags', adapter='FaceFlags', known_bad='face7_before',
         baseline=['corner_moved'], shape=['face_piece_lash', 'face_piece_iris']),
    dict(check='eye_corner_front', part='face_flags', adapter='FaceFlags', known_bad=None,
         no_known_bad="the front corner was never flagged: it holds the eye's front while the profile's far corner "
                      "moves (a turned eye keeps every (x, z): its front is unchanged by construction)",
         baseline=['corner_moved'], shape=['face_piece_lash', 'face_piece_iris']),
    dict(check='eye_corner_closeup_front', part='face_flags', adapter='FaceFlags', known_bad=None,
         no_known_bad="the front corner was never flagged: it holds the eye's front while the profile's far corner "
                      "moves (a turned eye keeps every (x, z): its front is unchanged by construction)",
         baseline=['corner_moved'], shape=['face_piece_lash', 'face_piece_iris']),
    dict(check='eye_corner_three_quarter', part='face_flags', adapter='FaceFlags', known_bad=None,
         no_known_bad="the three-quarter's near eye was never flagged: it holds while the profile's far corner moves",
         baseline=['corner_moved'], shape=['face_piece_lash', 'face_piece_iris']),
    dict(check='face_contour_three_quarter', part='face_flags', adapter='FaceFlags', known_bad='face7_before',
         baseline=['contour_moved'], shape=['face_piece_mouth']),
    dict(check='mouth_place_three_quarter_override', part='face_flags', adapter='FaceFlags', known_bad=None,
         no_known_bad="the per-shot override is new (off by default; no build had it): it reads the drawn placement "
                      "as mouth_place_three_quarter does, with the override's keys on",
         baseline=['mouth_moved'], shape=['face_piece_mouth'], better='lower'),
    dict(check='brow_len_closeup_profile', part='face_flags', adapter='FaceFlags', known_bad='face7_before',
         baseline=['brow_lengthened'], shape=['face_piece_brow']),
    dict(check='brow_len_closeup_front', part='face_flags', adapter='FaceFlags', known_bad=None,
         no_known_bad="the front brow's length was never flagged: it holds the brow's x extent while the forehead "
                      "rounds and the profile's length grows",
         baseline=['brow_lengthened'], shape=['face_piece_brow']),
    dict(check='brow_*', part='face_flags', adapter='FaceFlags', known_bad='face6_before',
         baseline=['brow_warped'], shape=['face_piece_brow']),
    dict(check='mouth_smile_*', part='face_flags', adapter='FaceFlags', known_bad='face6_before',
         baseline=['mouth_warped'], shape=['face_piece_mouth']),
    dict(check='mouth_place_*', part='face_flags', adapter='FaceFlags', known_bad='face6_before',
         baseline=['mouth_moved'], shape=['face_piece_mouth'], better='lower'),
    dict(check='nose_mark_*', part='face_flags', adapter='FaceFlags', known_bad='face6_before',
         baseline=['nose_moved'], shape=['face_piece_nose']),
]


def _rng(name, seed):
    import zlib
    return np.random.default_rng(zlib.crc32(name.encode()) % 1000 + 7000 + int(seed))


def _either(rng, a, b):
    return rng.uniform(*a) if rng.random() < 0.5 else rng.uniform(*b)


def _scale_rows(m, s, clip=None):
    """a mask scaled s times in height about its centroid's row (nearest rows), clipped to `clip`."""
    ys, xs = np.nonzero(m)
    out = np.zeros_like(m)
    if not len(ys):
        return out
    cy = ys.mean()
    H = m.shape[0]
    for r in range(H):
        src = int(round(cy + (r - cy) / s))
        if 0 <= src < H:
            out[r] = m[src]
    return out & clip if clip is not None else out


def _rebuild(m, arch=1.0, thick=1.0, length=1.0, rows_up=True):
    """a stroke (a brow, a mouth) rebuilt from its columns' centre line and thickness: its bend from the chord through
    its ends times arch, its thickness times thick, its length times length (about its middle column)."""
    cols = np.nonzero(m.any(0))[0]
    out = np.zeros_like(m)
    if len(cols) < 3:
        return out
    ys = np.array([np.nonzero(m[:, c])[0].mean() for c in cols])
    th = np.array([m[:, c].sum() for c in cols], float)
    c0, c1 = cols[0], cols[-1]
    chord = ys[0] + (cols - c0) / max(1, c1 - c0) * (ys[-1] - ys[0])
    yn = chord + arch * (ys - chord)
    cm = (c0 + c1) / 2
    H, W = m.shape
    for c in range(W):
        u = cm + (c - cm) / length
        if u < c0 or u > c1:
            continue
        y = float(np.interp(u, cols, yn))
        t = float(np.interp(u, cols, th)) * thick
        r0, r1 = int(round(y - t / 2)), int(round(y + t / 2))
        out[max(0, r0):min(H, max(r1, r0 + 1)), c] = True
    return out


def _move(m, dy, dx):
    from charkit.faceflags import _moved
    return _moved(m, dy, dx)


def _corner_warp(m, side, s):
    """an eye's mask with its columns shifted up (s > 0) or down by s x the opening's height times t^2, t 0 at its
    inner end and 1 at its outer (her left eye's outer end the picture's right): its far corner moves, its inner part
    stays."""
    if m is None or not m.any():
        return m
    rows, cols = np.nonzero(m.any(1))[0], np.nonzero(m.any(0))[0]
    h = rows[-1] - rows[0] + 1
    out = np.zeros_like(m)
    for c in cols:
        t = (c - cols[0]) / max(1, cols[-1] - cols[0])
        t = t if side == 'L' else 1 - t
        out[:, c] = np.roll(m[:, c], -int(round(s * h * t * t)))
    return out


def perturb(F, kind, seed):
    """a copy of a read's design features perturbed by a generator (see the module)."""
    from charkit import faceflags as ff
    from scipy import ndimage
    F = dict(F)
    rng = _rng(kind, seed)
    ppl = F['ppl']
    if kind == 'iris_scaled':
        E2 = {}
        for side, E in (F.get('eye_masks') or {}).items():
            if E is None:
                E2[side] = None
                continue
            s = _either(rng, (1.25, 1.6), (0.6, 0.8))
            E2[side] = dict(E, I=_scale_rows(E['I'], s, clip=E['O']))
        F['eye_masks'] = E2
    elif kind == 'lash_blocked':
        E2 = {}
        for side, E in (F.get('eye_masks') or {}).items():
            if E is None or not E['U'].any():
                E2[side] = E
                continue
            band = (ff.eye_numbers(E, ppl).get('lash_band') or 0.02) * ppl
            r = max(1, int(round(rng.uniform(0.6, 1.2) * band)))
            disk = np.hypot(*np.mgrid[-r:r + 1, -r:r + 1]) <= r
            U = ndimage.binary_closing(np.pad(E['U'], r), structure=disk)[r:-r, r:-r]
            U = ndimage.binary_dilation(U, iterations=max(1, int(round(rng.uniform(0.3, 0.8) * band / 2)))) & ~E['O']
            E2[side] = dict(E, U=U)
        F['eye_masks'] = E2
    elif kind == 'lash_smoothed':
        E2 = {}
        for side, E in (F.get('eye_masks') or {}).items():
            if E is None or not E['U'].any():
                E2[side] = E
                continue
            band = (ff.eye_numbers(E, ppl).get('lash_band') or 0.02) * ppl
            sig = rng.uniform(0.6, 1.2) * band
            U = ndimage.gaussian_filter(E['U'].astype(float), sig) > 0.5
            E2[side] = dict(E, U=U & ~E['O'])
        F['eye_masks'] = E2
    elif kind == 'brow_warped':
        F['brow'] = {s: _rebuild(m, arch=_either(rng, (0.2, 0.6), (1.6, 2.2)), thick=_either(rng, (0.45, 0.7), (1.5, 2.0)),
                                 length=rng.uniform(0.8, 1.3)) for s, m in F['brow'].items()}
    elif kind == 'mouth_warped' and F.get('mouth') is not None:
        F['mouth'] = _rebuild(F['mouth'], arch=_either(rng, (0.0, 0.4), (1.8, 2.5)), thick=rng.uniform(2.5, 4.0),
                              length=rng.uniform(0.5, 0.75))
    elif kind == 'mouth_moved' and F.get('mouth') is not None:
        dy, dx = (rng.choice((-1, 1)) * rng.uniform(0.03, 0.06) * ppl for _ in range(2))
        F['mouth'] = _move(F['mouth'], dy, dx)
    elif kind == 'corner_moved':
        E2 = {}
        s_ = rng.choice((-1, 1)) * rng.uniform(0.15, 0.3)          # (both eyes the same way: a symmetric stand-in)
        for side, E in (F.get('eye_masks') or {}).items():
            if E is None or not E['O'].any():
                E2[side] = E
                continue
            E2[side] = {k: _corner_warp(m, side, s_) for k, m in E.items()}
        F['eye_masks'] = E2
    elif kind == 'contour_moved' and F.get('lead') is not None:
        from charkit.faceflags import CONTOUR_ROWS
        ax, ey = F['anchor']
        f = rng.choice((-1, 1)) * rng.uniform(0.12, 0.25)
        lead = F['lead'].copy()
        r0, r1 = int(ey + (CONTOUR_ROWS[0] - 0.05) * ppl), int(ey + (CONTOUR_ROWS[1] + 0.05) * ppl)
        sl = slice(max(0, r0), max(0, r1) + 1)
        lead[sl] = ax - (ax - lead[sl]) * (1 + f)
        F['lead'] = lead
    elif kind == 'brow_lengthened':
        F['brow'] = {s_: _rebuild(m, length=_either(rng, (0.6, 0.8), (1.25, 1.5))) for s_, m in F['brow'].items()}
    elif kind == 'nose_moved' and 'nose_ink' in F:
        a, r = rng.uniform(0, 2 * np.pi), rng.uniform(0.03, 0.06) * ppl
        keep = rng.uniform(0.05, 0.2)
        for k in ('nose_ink', 'nose_high'):
            m = _move(F[k], r * np.sin(a), r * np.cos(a))
            m &= rng.random(m.shape) < keep
            F[k] = m
    return F


class FaceFlags:
    part = 'face_flags'
    generators = {g: d for g, d in (
        ('iris_scaled', 'each iris scaled 1.25-1.6x or 0.6-0.8x in height about its middle, clipped to the opening'),
        ('lash_blocked', 'the upper lash line closed by a disk of 0.6-1.2 x its band and grown 0.3-0.8 x its band'),
        ('brow_warped', 'each brow rebuilt: arch x (0.2-0.6 | 1.6-2.2), thickness x (0.45-0.7 | 1.5-2.0), length x '
                        '0.8-1.3'),
        ('mouth_warped', 'the mouth rebuilt 0.5-0.75 as wide, 2.5-4x as thick, its curve x (0-0.4 | 1.8-2.5)'),
        ('mouth_moved', 'the mouth moved 0.03-0.06 L up or down and 0.03-0.06 L across, at random'),
        ('nose_moved', "the nose's mark moved 0.03-0.06 L in a random direction, 5-20% of its ink kept"),
        ('lash_smoothed', 'the upper lash line low-passed (a Gaussian of 0.6-1.2 x its band, cut at half): its thin '
                          'spikes and the gaps between its strokes gone'),
        ('corner_moved', "each eye's masks warped (both eyes the same way): its columns shifted 0.15-0.3 x the "
                         "opening's height up or down times t^2 (0 at the inner end, 1 at the outer): the far corner "
                         "moved, the inner part kept"),
        ('contour_moved', "the face's leading contour over the mouth's rows (and 0.05 L either side) moved 12-25% "
                          "nearer or further from the eyes' midpoint"),
        ('brow_lengthened', 'each brow rebuilt 0.6-0.8x or 1.25-1.5x as long'))}

    def __init__(self, B, design):
        self.B, self.design = B, design

    def measure(self, B):
        from charkit import faceflags as ff
        return ff.part(B, self.design)[1]

    def run(self, kind, arg):
        """the checks with the design standing in for ours: kind 'design' (arg: the move, rows and columns) or a
        generator (arg: its seed)."""
        from charkit import faceflags as ff
        reads, shapes = {}, {}
        for sheet, view in ff.READS:
            Fd = ff.design_read(sheet, view)
            Fo = ff.design_read(sheet, view, shift=tuple(arg)) if kind == 'design' else perturb(Fd, kind, arg)
            Nd, No = ff.numbers(Fd), ff.numbers(Fo)
            shapes[(sheet, view)] = ff.pair(Fd, Fo, No)
            reads[(sheet, view)] = (Nd, No)
        reads[ff.OVERRIDE] = reads[('turnaround', 'three_quarter')]     # (the override's read: the same stand-in)
        return ff.checks_of(reads, shapes)
