"""Anime brows (docs/CHARKIT.md §2, face features): a tapered ribbon over each eye on the face surface, knob-driven (height,
arch, length, thickness, tilt), with expression keys (raise, angry, sad, surprised, worried, relaxed, focus, knit, pained) from the same curve. Drawn over
the hair later (the hair phase gives them their own layer); here they sit just in front of the skin.

Brow-local coordinates are the eye's: x along the eye (+ outward), z up, metres, from the eye centre.
"""
import math
import numpy as np

from . import eyes as eyelib

DEFAULT_BROW = {
    'height': 0.42,      # the brow's lowest point above the eye's top, in eye widths
    'inner': -0.42,      # inner end along the eye (eye widths from the centre)
    'outer': 0.62,       # outer end
    'arch': 0.10,        # arch height, in eye widths
    'peak': 0.62,        # where the arch peaks (0 inner .. 1 outer)
    'tilt': -4.0,        # degrees, outer end up (+) / down (-)
    'thick': 0.012,      # thickest, in L
    'taper': 0.25,       # the outer tip's share of the thickness
    'inner_thick': 0.75, # the inner end's share
}


def _knobs(k):
    K = dict(DEFAULT_BROW); K.update(k or {})
    return K


def curve(BK, EK, L, t):
    """brow-local (x, z) of the brow's centre line at t (0 inner .. 1 outer)."""
    W = EK['width'] * L
    t = np.asarray(t, float)
    x = (BK['inner'] + (BK['outer'] - BK['inner']) * t) * W
    top = EK['height'] * (1 - EK['lower']) * W                 # the eye's upper extent above its centre (roughly)
    g = math.log(0.5) / math.log(min(0.95, max(0.05, BK['peak'])))
    arch = np.sin(np.pi * t ** g) * BK['arch'] * W
    z = top + BK['height'] * W + arch + x * math.tan(math.radians(BK['tilt']))
    return x, z


def thickness(BK, L, t):
    t = np.asarray(t, float)
    body = np.clip(t / 0.25, 0, 1) * (1 - BK['inner_thick']) + BK['inner_thick']
    tip = 1 - (1 - BK['taper']) * np.clip((t - 0.55) / 0.45, 0, 1) ** 1.3
    return BK['thick'] * L * body * tip


def ribbon(F, BK, EK, L, side, eye_c, n=32, knobs=None):
    """the brow as a ribbon (verts, quads) centred on its curve."""
    K = _knobs({**BK, **(knobs or {})})
    t = np.linspace(0, 1, n)
    x, z = curve(K, EK, L, t)
    th = thickness(K, L, t)
    pts = np.stack([x, z], 1)
    # _ribbon offsets 18% in / 82% out along the normal; centre it: shift the line down by 32% of the thickness
    tan = np.gradient(pts, axis=0)
    tan /= np.maximum(np.linalg.norm(tan, axis=1, keepdims=True), 1e-12)
    nrm = np.stack([-tan[:, 1], tan[:, 0]], 1)
    pts = pts - nrm * th[:, None] * 0.32
    return eyelib._ribbon(F, side, eye_c, pts, th, 1.0, lift=-0.0008)


def expressions(BK):
    """named brow shapes as knob overrides."""
    return {
        'raise': {'height': BK['height'] + 0.10, 'arch': BK['arch'] * 1.3},
        'surprised': {'height': BK['height'] + 0.16, 'arch': BK['arch'] * 1.8, 'peak': 0.5},
        'angry': {'height': BK['height'] - 0.08, 'tilt': BK['tilt'] + 16, 'arch': BK['arch'] * 0.4, 'peak': 0.75},
        'sad': {'height': BK['height'] + 0.02, 'tilt': BK['tilt'] - 14, 'arch': BK['arch'] * 0.6, 'peak': 0.25},
        'worried': {'height': BK['height'] + 0.06, 'tilt': BK['tilt'] - 10, 'arch': BK['arch'] * 1.2, 'peak': 0.3},
        'relaxed': {'height': BK['height'] - 0.03, 'arch': BK['arch'] * 0.8},
        # the action set (charkit.expressions.PRESETS). focus: lowered a little, the inner ends down
        'focus': {'height': BK['height'] - 0.05, 'tilt': BK['tilt'] + 9, 'arch': BK['arch'] * 0.6, 'peak': 0.7},
        # knit (effort): pulled down and together, the inner ends low
        'knit': {'height': BK['height'] - 0.10, 'tilt': BK['tilt'] + 15, 'arch': BK['arch'] * 0.4, 'peak': 0.8,
                 'inner': BK['inner'] - 0.05},
        # pained: the inner ends pulled up hard, the brow bunched toward them
        'pained': {'height': BK['height'] + 0.04, 'tilt': BK['tilt'] - 18, 'arch': BK['arch'] * 0.9, 'peak': 0.2,
                   'inner': BK['inner'] - 0.03},
    }
