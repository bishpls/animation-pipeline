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
                          'spikes and the gaps between its strokes gone'))}

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
        return ff.checks_of(reads, shapes)
