"""Style profiles: the settings that make charkit build a character in one 3D style rather than another (Michael,
2026-09-28: the kit is meant for any 3D style, not only anime). Every stage that assumes something about a style reads it
from the character's profile (spec['style'], default 'anime') instead of hard-coding it.

  hull     charkit.geom.hull's shape prior: p (the cross-sections' superellipse exponent: 2 an ellipse, higher boxier),
           class_share (how much of a front run must be skin for it to take its depth from the side view's skin), smooth
           (L, the smoothing across heights)
  hair_pieces  charkit.geom.hairpieces' construction: notch (deg: the V between two locks deepened at their seam, how
           sharp the tips read), thick and tip_thick (L: a lock's depth at its root and at its tip), inset (L per layer:
           how far a piece under another sits inside it), lock_min (deg: the narrowest lock), normals ('envelope': the
           mass's smoothed normals as custom normals, one clean shadow shape; 'geometric': each lock shades on its own),
           shade_close and shade_blur (L: the envelope those normals come from, closed across the gaps between locks and
           blurred to the shadow shapes' scale)
  look     the render look (charkit.shade, faceshade; the boards, turntables and the glTF export's look extension):
           light: mode 'world' (one fixed art-directed light, `dir` toward it) or 'camera' (a key that turns with the
           camera: `key` = [degrees to the camera's left, degrees above], so a turntable's back is lit as its front is);
           lines: mode 'world' (each outline its build width in metres) or 'screen' (every view's outlines `frac` of the
           picture's height wide, times `regions`' factor per object kind: skin, hair, garment, accessory), `color`
           'build' (each object's own line colour) or 'ink' (one `ink` colour everywhere);
           face: normals 'geometric' or 'proxy' (the head and neck shade on a smooth stand-in's normals: an ellipsoid
           round the head, a cylinder round the neck tilted down under the jaw by up to `chin_tilt` degrees; the face
           mask taken from it too, so the eye hollows and cheeks never band), fringe (the bangs' shadow on the forehead),
           jaw_line (the jaw's edge over the neck inked in the face's UV, `jaw_width` L wide: from the front it doesn't
           turn from the camera, so no outline draws it);
           hair: highlight None or 'streaks' (short drawn streaks along the locks on the crown's lit side: `elevation`,
           `width` (deg), `amount`, `color`), lock_shade (the root side of each lock a step darker: 0 off .. 1)
  physics  the planned drape and spring solvers (not built yet): how far a garment holds its drawn shape against
           gravity, cloth stiffness and damping, hair spring stiffness and damping, gravity scale. Declared here so the
           solvers are written against a profile from the start

    from charkit import styles; S = styles.load('anime')        # charkit/styles/anime.json, over DEFAULT
"""
import copy, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = {
    'hull': {'p': 2.0, 'class_share': 0.6, 'smooth': 0.09},
    'hair_pieces': {'notch': 3.0, 'thick': 0.22, 'tip_thick': 0.012, 'inset': 0.012, 'lock_min': 6.0,
                    'normals': 'geometric', 'shade_close': 0.1, 'shade_blur': 0.06},
    'look': {'light': {'mode': 'world', 'dir': [-0.45, -0.55, 0.70], 'key': [39.3, 44.6]},
             'lines': {'mode': 'world', 'frac': 0.0025, 'regions': {'skin': 1.0, 'hair': 1.0, 'garment': 1.0, 'accessory': 1.0},
                       'color': 'build', 'ink': [0.24, 0.13, 0.11]},
             'face': {'normals': 'geometric', 'chin_tilt': 0.0, 'fringe': True, 'jaw_line': False},
             'hair': {'highlight': None, 'elevation': 38.0, 'width': 4.0, 'amount': 0.8, 'color': [1.0, 0.86, 0.74],
                      'lock_shade': 0.0}},
    'physics': {'hold_shape': 0.5, 'cloth_stiffness': 0.5, 'cloth_damping': 0.2, 'hair_stiffness': 0.5,
                'hair_damping': 0.2, 'gravity': 1.0},
}


def names():
    return sorted(f[:-5] for f in os.listdir(HERE) if f.endswith('.json'))


def merge(base, over):
    """`over` laid over `base` (a copy), dict by dict: a nested section keeps what `over` doesn't set."""
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        out[k] = merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else copy.deepcopy(v)
    return out


def load(name='anime'):
    """a style profile: DEFAULT with the named profile's sections laid over it."""
    S = copy.deepcopy(DEFAULT)
    p = os.path.join(HERE, name + '.json')
    if not os.path.exists(p):
        raise KeyError('no style profile %r (have: %s)' % (name, ', '.join(names())))
    for sec, vals in json.load(open(p)).items():
        if sec.startswith('_'):
            continue
        S[sec] = merge(S.get(sec, {}), vals)
    return S
