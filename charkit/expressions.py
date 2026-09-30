"""The expression system: the face as combinable components (Michael, 2026-09-30), each a family of shape keys the build
makes on the character (charkit.character.features), named '<component>_<name>':

  eye    the lids (charkit.eyes.expressions: on the skin, the lashes, the sclera and iris plates; 'shock' also shrinks
         the iris)
  brow   the brows (charkit.brows.expressions: on the brow ribbons)
  mouth  the mouth (charkit.mouth.SHAPES: on the skin, the teeth, the tongue and the lip line)
  look   the gaze (the iris keys: left, right, up, down)

A preset is {component: name, or {name: weight, ...}}. A component it leaves out stays at rest, so the rest face is the
empty preset (PRESETS['rest']), and presets layer: combine(a, b) takes b's components over a's (a shout's mouth on an
angry face: combine('angry', {'mouth': 'shout'})). weights(P) -> {shape key: weight} is what every consumer applies: the
boards (charkit.boards.face_board.set_preset), the export's combined expressions (charkit.gltf) and the QA's renders
(charkit.exprqa.render). The library is the template's and additive: a drawing's expression the library lacks is added
here, never the library cut to a drawing's.

    from charkit import expressions as ex
    ex.weights('laugh')                          # {'eye_happy': 1.0, 'mouth_laugh': 1.0, 'brow_raise': 1.0}
    ex.weights(ex.combine('angry', {'mouth': {'shout': 0.6}}))
    ex.library()                                 # {component: [names]} the template's shapes

Graded: exprqa.TARGETS (what each preset must read as) as the face QA's face_preset_* checks (qa3d.face_part).
Pure Python (Blender imports it for the boards).
"""
COMPONENTS = ('eye', 'brow', 'mouth', 'look')

# the template's combined expressions: the model sheet's heads (laugh, angry, fluster, yawn) and the standard anime set
# for action shorts (docs/workstreams/mouth.md)
PRESETS = {
    'rest': {},
    'laugh': dict(eye='happy', mouth='laugh', brow='raise'),
    'angry': dict(eye='angry', mouth='frown', brow='angry'),
    'fluster': dict(eye='shock', mouth='wavy', brow='surprised'),
    'yawn': dict(eye='blink', mouth='yawn', brow='raise'),
    'effort': dict(eye='squeeze', mouth='clench', brow='knit'),
    'shout': dict(eye='angry', mouth='shout', brow='angry'),
    'focus': dict(eye='focus', mouth='firm', brow='focus'),
    'surprise': dict(eye='wide', mouth='surprised', brow='surprised'),
    'pain': dict(eye='wince', mouth='grimace', brow='pained'),
    'smug': dict(eye='half', mouth='smirk', brow='relaxed'),
    'embarrassed': dict(eye='shy', mouth='wobble', brow='worried'),
    'sad': dict(eye='sad', mouth='frown', brow='sad'),
}


def preset(P):
    """a preset by name (PRESETS) or as given; None: the rest face."""
    if P is None:
        return {}
    if isinstance(P, str):
        return PRESETS[P]
    return P


def parts(P):
    """{component: {name: weight}}: each component's shapes and weights (a name alone weighs 1; 'neutral', None and zero
    weights left out)."""
    out = {}
    for c, v in preset(P).items():
        if c not in COMPONENTS:
            raise KeyError('expression component %r: one of %s' % (c, ', '.join(COMPONENTS)))
        if not v:
            continue
        w = {v: 1.0} if isinstance(v, str) else {n: float(x) for n, x in v.items()}
        w = {n: x for n, x in w.items() if n and n != 'neutral' and x}
        if w:
            out[c] = w
    return out


def weights(P):
    """a preset -> {shape key: weight} ('<component>_<name>')."""
    return {'%s_%s' % (c, n): x for c, w in parts(P).items() for n, x in w.items()}


def combine(*layers):
    """presets layered: each later one's components replace the earlier ones' -> a preset."""
    out = {}
    for P in layers:
        out.update(preset(P))
    return out


def library():
    """the template's shapes per component, from the modules that make them: {component: [names]}."""
    from . import brows, eyes, mouth
    ek = eyes.expressions(eyes._knobs({}), 1.0)
    return {'eye': sorted(ek), 'brow': sorted(brows.expressions(brows._knobs({}))),
            'mouth': sorted(k for k in mouth.SHAPES if k != 'neutral'), 'look': ['down', 'left', 'right', 'up']}


def check():
    """every preset's shapes are in the library -> [problems] (empty: fine)."""
    lib = library()
    return ['%s: %s %r is not in the library' % (name, c, n) for name, P in PRESETS.items()
            for c, w in parts(P).items() for n in w if n not in lib[c]]
