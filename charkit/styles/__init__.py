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
           blurred to the shadow shapes' scale), relief (L: each lock's ridge across it, the grooves between locks),
           lock_shading (0..1: how much of each lock's own outer normal, smoothed within the lock lock_shading_smooth
           times, is blended into the mass's, so its relief and grooves shade), bun_e, bun_q, bun_slab (a block bun's squareness (0 a box, 1 an ellipsoid), the share of the hull's bun
           points its extent ignores at either end, its folded slab's share of its width)
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
           far contour is fullest: 0.5 under the eye, larger toward the cheekbone); jaw_under (the chin overhangs the
           neck: the head's mesh carries the jaw's underside, rising from the design's jaw line toward the throat,
           charkit.geom.headgeom.UnderJaw; off, the chin is the rows' own step), jaw_rise ('design': the underside's angle
           read in the head sheet's profile, or degrees) within jaw_rise_range (degrees; Clawd's design reads 13.7),
           jaw_edge ('design': the jaw line an edge in 3D at the depth the head sheet's three-quarter draws it, its
           underside carried round the sides to the jaw's angle, charkit.geom.headgeom.jaw_envelope; None: the rim on
           the envelope's front under the neck's width only), jaw_side (True: the pocket under the jaw carried round its
           sides to its angle, each cage column's underside hung from its own point of the jaw's edge, the rim and the
           throat edge loops along the jaw line, charkit.geom.headgeom.SIDE; False: the pocket ends at the neck's width
           and the jaw's side is a ledge under the mouth's block)
  look     the render look (charkit.shade, faceshade; the boards, turntables and the glTF export's look extension):
           light: mode 'world' (one fixed art-directed light, `dir` toward it) or 'camera' (a key that turns with the
           camera: `key` = [degrees to the camera's left, degrees above], so a turntable's back is lit as its front is);
           lines: mode 'world' (each outline its build width in metres) or 'screen' (every view's outlines `frac` of the
           picture's height wide, times `regions`' factor per object kind: skin, hair, garment, accessory), `color`
           'build' (each object's own line colour), 'ink' (one `ink` colour everywhere, as a drawing's pen) or
           'material' (each object's deep tone times `darken`), `ink_regions` the regions it applies to (the rest
           keep their build colour; anime leaves the skin's line its warm brown: inked, the face's contour reads as
           lash to the eye QA's crops, eye_aspect 0.83 -> 0.75 on the default spec);
           face: normals 'geometric' or 'proxy' (the head and neck shade on a smooth stand-in's normals: an ellipsoid
           round the head, a cylinder round the neck tilted down under the jaw by up to `chin_tilt` degrees; the face
           mask taken from it too, so the eye hollows and cheeks never band), fringe (the bangs' shadow on the forehead,
           `fringe_drop` L below them; with fringe_sides the side locks' too, on the temples and cheeks),
           jaw_line (the jaw's edge over the neck inked in the face's UV, `jaw_width` L wide: from the front it doesn't
           turn from the camera, so no outline draws it); cast (None, or the head's and hair's shadows baked per skin
           vertex for `k` light azimuths at the key's elevation, charkit.faceshade.cast_maps: the jaw's on the neck, the
           hair's on the face; shadow maps of `px` L pixels, filtered `soft` pixels round, the values smoothed over the
           mesh `smooth` times; read where they cross `at` +- `width`; the toon held at or under `half` in them);
           hair: highlight None or 'streaks' (short drawn streaks down the hair on the crown's lit side: `count`
           columns of azimuth round the head, a share `keep` of them carrying one `length` degrees long and `duty` of
           its column wide about `elevation` +- `jitter`; `amount`, `color`), deep_at (the deep tone's step on
           half-lambert: lower keeps the deep tone to hair turned right away from the light), lock_shade (the families
           in `under`, the layers under others, drawn that far from their lit tone toward their shade: 0 off .. 1)
  eyes     the eye's surface behind its opening (charkit.eyes: Surface, the knobs in eyes.DEFAULT_EYE): surface 'plate'
           (on the face, `depth` behind it: every view sees the whole opening, as a plate on the face) or 'turned' (a
           vertical fold following the iris's nasal outline; nasal of it the surface faces the front, turn[0] degrees
           toward the nose, so a side view can't see it; past it the surface turns outward from turn[1] to turn[2] at
           the outer corner; the lids, lashes, pocket and the skin within fold_reach L of the opening follow it, every
           (x, z) kept: the front view is the plate's), anchor (where it sits against the face: 'corners', 'min',
           'mean', 'fold'), fold_follow (0: the profile's front edge upright; 1: each row's fold at the face's depth
           there), converge (the irises' rest place toward the nose, eye widths, when the spec's iris doesn't set it;
           only with a turned surface: a plate's far eye in three-quarter loses its nasal white)
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
                    'normals': 'geometric', 'shade_close': 0.1, 'shade_blur': 0.06,
                    'relief': 0.0, 'lock_shading': 0.0, 'lock_shading_smooth': 8, 'bun_e': 0.3, 'bun_q': 0.06, 'bun_slab': 0.38},
    'face': {'eye_region': 'socket', 'margin': 0.03, 'reach': [0.2, 0.3], 'yaw': 'design', 'max_yaw': 40.0,
             'hold': True, 'curve': 2.0, 'release': 0.5, 'cheek_peak': 0.5,
             'jaw_under': True, 'jaw_rise': 'design', 'jaw_rise_range': [8.0, 25.0], 'jaw_edge': 'design',
             'jaw_side': True},
    'look': {'light': {'mode': 'world', 'dir': [-0.45, -0.55, 0.70], 'key': [39.3, 44.6]},
             'lines': {'mode': 'world', 'frac': 0.0025, 'regions': {'skin': 1.0, 'hair': 1.0, 'garment': 1.0, 'accessory': 1.0},
                       'color': 'build', 'ink': [0.24, 0.13, 0.11]},
             'face': {'normals': 'geometric', 'chin_tilt': 0.0, 'fringe': True, 'fringe_drop': 0.03,
                      'fringe_sides': False, 'jaw_line': False, 'cast': None},
             'hair': {'highlight': None, 'elevation': 40.0, 'length': 9.0, 'jitter': 8.0, 'count': 40, 'duty': 0.35,
                      'keep': 0.5, 'amount': 0.8, 'color': [0.97, 0.86, 0.78], 'deep_at': 0.27, 'lock_shade': 0.0,
                      'under': []}},
    'physics': {'hold_shape': 0.5, 'cloth_stiffness': 0.5, 'cloth_damping': 0.2, 'hair_stiffness': 0.5,
                'hair_damping': 0.2, 'gravity': 1.0},
    'eyes': {'surface': 'plate'},
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
