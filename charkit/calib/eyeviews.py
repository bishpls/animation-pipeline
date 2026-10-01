"""Calibration adapters for the eye checks charkit.eyeqa measures whose measuring code tool/face6 changed: the profile
flick (eye_view_profile_flick_out, the QA part eye_views; EyeViews) and the front upper lid line's span (eye_lid_span,
the QA part eyes; Eyes): both read the upper lid line in a window that ended at the opening's middle row, where a flick
can lie, and now reach eyeqa.FLICK_BELOW opening heights under the corner's row. The design stands in for ours: the head
sheet's profile eye (charkit.eyepage.design_eyes) or the design's front eye layers (qa3d.Design.eye_layers) measured
against themselves moved 1-2 px (the move and half a pixel more, re-sampling the anti-aliased edges:
charkit.faceflags._shift), or perturbed by a generator below; eyeqa's measuring code runs unchanged on both.

Generators (seeded; the *_cut are the floor, which must not pass; the *_long are probes, reported: a check that
passes one is blind to a line sweeping too far):
  flick_cut     the lash line past the opening's far corner cut back to 0-30% of its reach (the skin painted over the
                rest): an eye with no flick
  flick_long    the lash line past the far corner stretched outward 1.6-2.2x about the corner's column: a flick that
                sweeps too far back
  lid_cut       the front eye's upper lid line past both corners cut back to 0-30% of its reach: a line that stops at
                the corners
  lid_long      the front eye's upper lid line past both corners stretched outward 2.2-3x: a lash arc floating past
                the eye
"""
import numpy as np

CALIBRATION = [
    dict(check='eye_view_profile_flick_out', part='eye_views', adapter='EyeViews', known_bad=None,
         no_known_bad="no stored build has a wrong flick: Michael's eyes2 flag (the profile eye not looking forward) "
                      "predates the stored builds, and face6_before (1580f95) reads 0.594 against the design's 0.556",
         baseline=['flick_cut'], probes=['flick_long'], shape=['face_piece_lash']),
    dict(check='eye_lid_span', part='eyes', adapter='Eyes', known_bad=None,
         no_known_bad="no stored build has a wrong lid span (1580f95 and the builds before it read 1.33 against 1.30)",
         baseline=['lid_cut'], probes=['lid_long'], shape=['face_piece_lash']),
]


def _rng(name, seed):
    import zlib
    return np.random.default_rng(zlib.crc32(name.encode()) % 1000 + 9000 + int(seed))


def _corner_rows(O, ob):
    return {c: float(np.nonzero(O[:, c])[0].mean()) for c in (ob[0], ob[1])}


def _past(out, rows, cxc, d, kind, rng, ink):
    """the ink past the column cxc in direction d (+1 the picture's right) over `rows` cut back or stretched."""
    H, W = out.shape[:2]
    beyond = (np.arange(W) - cxc) * d > 0
    if not (ink[rows] & beyond[None]).any():
        return
    cols = np.nonzero((ink[rows] & beyond[None]).any(0))[0]
    reach = np.abs(cols - cxc).max()
    if kind.endswith('_cut'):
        keep = rng.uniform(0.0, 0.3) * reach
        skin_px = out[rows][~ink[rows] & (out[rows][..., 3] > 0.5)][:, :3]
        skin = np.median(skin_px, 0) if len(skin_px) else np.array([1.0, 0.9, 0.86])
        cut = (np.arange(W) - cxc) * d > keep
        m = np.zeros((H, W), bool)
        m[rows] = ink[rows] & cut[None]
        out[m, :3] = skin
    else:
        s = rng.uniform(*((1.6, 2.2) if kind == 'flick_long' else (2.2, 3.0)))
        src = out.copy()
        for c in range(W):
            dd = (c - cxc) * d
            if dd <= 0:
                continue
            u = cxc + dd / s * d
            u0 = int(np.floor(u)); f = u - u0
            if 0 <= u0 < W - 1:
                out[rows, c] = src[rows, u0] * (1 - f) + src[rows, u0 + 1] * f


def perturb(rgba, ppl, kind, seed, nasal=-1):
    """a copy of a design eye with its upper lid line changed by a generator (see the module): the flick_* the far
    corner's (the profile eye, its nose `nasal`), the lid_* both corners' (a front eye)."""
    from charkit import eyeqa, faceflags as ff
    rng = _rng(kind, seed)
    out = np.array(rgba, float)
    M = eyeqa.measure_view(rgba, ppl, nasal) if kind.startswith('flick') else eyeqa.measure(rgba, ppl)
    O = M['_masks']['opening']
    ob = eyeqa._box(O)
    oh = ob[3] - ob[2] + 1
    cr = _corner_rows(O, ob)
    ink = out[..., :3].max(-1) < ff.INK_V
    if kind.startswith('flick'):
        cxc = ob[1] if nasal < 0 else ob[0]
        _past(out, slice(0, int(min(out.shape[0], cr[cxc] + 0.3 * oh))), cxc, -nasal, kind, rng, ink)
    else:
        rows = slice(0, int(min(out.shape[0], max(cr.values()) + 0.3 * oh)))
        _past(out, rows, ob[1], 1, kind, rng, ink)
        _past(out, rows, ob[0], -1, kind, rng, ink)
    return out


class EyeViews:
    part = 'eye_views'
    generators = {
        'flick_cut': "the lash line past the opening's far corner cut back to 0-30% of its reach (skin painted over it)",
        'flick_long': "the lash line past the far corner stretched outward 1.6-2.2x about the corner's column",
    }

    def __init__(self, B, design):
        self.B, self.design = B, design

    def measure(self, B):
        from charkit import eyeqa
        _, C = eyeqa.views(B, self.design)
        return {'eye_' + k: v for k, v in C.items()}

    def _design(self):
        from charkit import eyepage
        des, ppl = eyepage.design_eyes(self.B.spec)
        return dict(des['profile'])['L'], ppl

    def run(self, kind, arg):
        """the profile checks with the design's profile eye standing in for ours: kind 'design' (arg: the move, rows
        and columns) or a generator (arg: its seed)."""
        from charkit import eyeqa, faceflags as ff
        px, ppl = self._design()
        md = eyeqa.measure_view(px, ppl, -1)
        mo = eyeqa.measure_view(ff._shift(px, tuple(arg)) if kind == 'design' else perturb(px, ppl, kind, arg), ppl, -1)
        if not (md.get('found') and mo.get('found')):
            return {}
        C = eyeqa.compare_view(mo, md, eyeqa.VIEW_CHECKS['profile'])
        return {'eye_view_profile_' + k: dict(v, eye='L') for k, v in C.items()}


class Eyes:
    part = 'eyes'
    generators = {
        'lid_cut': "the front eye's upper lid line past both corners cut back to 0-30% of its reach",
        'lid_long': "the front eye's upper lid line past both corners stretched outward 2.2-3x",
    }

    def __init__(self, B, design):
        self.B, self.design = B, design

    def measure(self, B):
        from charkit import qa3d
        _, C = qa3d.eyes(B, self.design)
        return {'eye_' + k: v for k, v in C.items()}

    def run(self, kind, arg):
        """the front eye checks with the design's eye layers standing in for ours: kind 'design' (arg: the move, rows
        and columns) or a generator (arg: its seed); the worse eye per check, as the part grades."""
        from charkit import eyeqa, qa3d, faceflags as ff
        ppl = self.design.eye_ppl()
        C = {}
        for side, (px, md) in self.design.eye_layers().items():
            md = eyeqa.measure(px, ppl)
            q = ff._shift(px, tuple(arg)) if kind == 'design' else perturb(px, ppl, kind, arg)
            mo = eyeqa.measure(q, ppl)
            if not mo.get('found'):
                continue
            for k, v in eyeqa.compare(mo, md).items():
                prev = C.get('eye_' + k)
                if prev is None or qa3d.STATUS.index(v['status']) > qa3d.STATUS.index(prev['status']):
                    C['eye_' + k] = dict(v, eye=side)
        return C
