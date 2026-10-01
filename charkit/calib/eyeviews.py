"""Calibration adapter for the per-view eye checks (charkit.eyeqa.views, the QA part eye_views; tool/eyes2), starting with
the profile flick (tool/face6 remeasured its window: eyeqa.FLICK_BELOW). The design stands in for ours: the head sheet's
own profile eye (charkit.eyepage.design_eyes) measured against itself moved 1-2 px (the move and half a pixel more,
re-sampling its anti-aliased edges: charkit.faceflags._shift), or perturbed by a generator below; eyeqa's measuring code
runs unchanged on both.

Generators (the floor; seeded, each must not pass):
  flick_cut     the lash line past the opening's far corner cut back to 0-30% of its reach (the skin painted over the
                rest): an eye with no flick
  flick_long    the lash line past the far corner stretched outward 1.6-2.2x about the corner's column: a flick that
                sweeps too far back
"""
import numpy as np

CALIBRATION = [
    dict(check='eye_view_profile_flick_out', part='eye_views', adapter='EyeViews', known_bad=None,
         no_known_bad="no stored build has a wrong flick: Michael's eyes2 flag (the profile eye not looking forward) "
                      "predates the stored builds, and face6_before (1580f95) reads 0.594 against the design's 0.556",
         baseline=['flick_cut', 'flick_long'], shape=['face_piece_lash']),
]


def _rng(name, seed):
    import zlib
    return np.random.default_rng(zlib.crc32(name.encode()) % 1000 + 9000 + int(seed))


def _corner(rgba, ppl, nasal=-1):
    """the opening's far corner (column, row) and its box, from eyeqa's own masks."""
    from charkit import eyeqa
    M = eyeqa.measure_view(rgba, ppl, nasal)
    O = M['_masks']['opening']
    ob = eyeqa._box(O)
    cxc = ob[1] if nasal < 0 else ob[0]
    return cxc, float(np.nonzero(O[:, cxc])[0].mean()), ob


def perturb(rgba, ppl, kind, seed, nasal=-1):
    """a copy of the design's profile eye with its flick changed by a generator (see the module)."""
    from charkit import faceflags as ff
    rng = _rng(kind, seed)
    out = np.array(rgba, float)
    cxc, cy, ob = _corner(rgba, ppl, nasal)
    oh = ob[3] - ob[2] + 1
    H, W = out.shape[:2]
    rows = slice(0, int(min(H, cy + 0.3 * oh)))
    ink = out[..., :3].max(-1) < ff.INK_V
    far = np.arange(W) * -nasal > cxc * -nasal
    if not (ink[rows] & far[None]).any():
        return out
    cols = np.nonzero((ink[rows] & far[None]).any(0))[0]
    tip = cols.max() if nasal < 0 else cols.min()
    reach = abs(tip - cxc)
    if kind == 'flick_cut':
        keep = rng.uniform(0.0, 0.3) * reach
        skin_px = out[rows][~ink[rows] & (out[rows][..., 3] > 0.5)][:, :3]
        skin = np.median(skin_px, 0) if len(skin_px) else np.array([1.0, 0.9, 0.86])
        cut = np.arange(W) * -nasal > (cxc + keep * -nasal) * -nasal
        m = np.zeros((H, W), bool)
        m[rows] = ink[rows] & cut[None]
        out[m, :3] = skin
    elif kind == 'flick_long':
        s = rng.uniform(1.6, 2.2)
        src = out.copy()
        for c in range(W):
            d = (c - cxc) * -nasal
            if d <= 0:
                continue
            u = cxc + d / s * -nasal
            u0 = int(np.floor(u)); f = u - u0
            if 0 <= u0 < W - 1:
                out[rows, c] = src[rows, u0] * (1 - f) + src[rows, u0 + 1] * f
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
