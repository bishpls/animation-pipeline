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
  face     the face's construction (charkit.geom.headfit): eye_region ('socket': a dip at each eye takes the surface back
           to the design's eye depth, a realistic orbit; 'window': the anime eye region, a flat window round each eye,
           yawed back toward its outer corner by the design's own yaw (yaw 'design', or degrees), with the brow and the
           cheek no further forward than it; max_yaw caps it), margin (L: the window past the eye's opening), reach (L,
           up and down: how far above and below the window the correction reaches), hold and curve (the brow and the
           cheek held behind the window's plane, allowed forward of it by curve * d^2 at d L out of the window (a pair:
           above and below the window's centre, the brow and the cheek); toward the
           nose it lets go from `release` of the window's half-width in from the eye), forward (L: how far the window may
           bring the face out of its own surface, None: as far as the plane asks),
           cheek_peak (where across the face, as a share of its half-width, the cheek term that meets the three-quarter's
           far contour is fullest: 0.5 under the eye, larger toward the cheekbone)
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
    'face': {'eye_region': 'socket', 'margin': 0.03, 'reach': [0.2, 0.3], 'yaw': 'design', 'max_yaw': 40.0,
             'hold': True, 'curve': 2.0, 'release': 0.5, 'cheek_peak': 0.5},
    'physics': {'hold_shape': 0.5, 'cloth_stiffness': 0.5, 'cloth_damping': 0.2, 'hair_stiffness': 0.5,
                'hair_damping': 0.2, 'gravity': 1.0},
}


def names():
    return sorted(f[:-5] for f in os.listdir(HERE) if f.endswith('.json'))


def load(name='anime'):
    """a style profile: DEFAULT with the named profile's sections laid over it."""
    S = copy.deepcopy(DEFAULT)
    p = os.path.join(HERE, name + '.json')
    if not os.path.exists(p):
        raise KeyError('no style profile %r (have: %s)' % (name, ', '.join(names())))
    for sec, vals in json.load(open(p)).items():
        if sec.startswith('_'):
            continue
        S.setdefault(sec, {}).update(vals)
    return S
