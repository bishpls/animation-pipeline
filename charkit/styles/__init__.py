"""Style profiles: the settings that make charkit build a character in one 3D style rather than another (Michael,
2026-09-28: the kit is meant for any 3D style, not only anime). Every stage that assumes something about a style reads it
from the character's profile (spec['style'], default 'anime') instead of hard-coding it.

  hull     charkit.geom.hull's shape prior: p (the cross-sections' superellipse exponent: 2 an ellipse, higher boxier),
           class_share (how much of a front run must be skin for it to take its depth from the side view's skin), smooth
           (L, the smoothing across heights)
  physics  the planned drape and spring solvers (not built yet): how far a garment holds its drawn shape against
           gravity, cloth stiffness and damping, hair spring stiffness and damping, gravity scale. Declared here so the
           solvers are written against a profile from the start

    from charkit import styles; S = styles.load('anime')        # charkit/styles/anime.json, over DEFAULT
"""
import copy, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = {
    'hull': {'p': 2.0, 'class_share': 0.6, 'smooth': 0.09},
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
