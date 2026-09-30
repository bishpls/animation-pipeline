"""charkit.mouth, charkit.expressions and the expression targets (exprqa.TARGETS): the mouth block the head's cage is
sized by, the teeth, tongue and lip line, the component API, the presets' targets calibrated (venv: run this file, or
pytest). The lab's check against a dumped head (mouthlab --head) runs when a dump is at hand (CHARKIT_MOUTH_HEAD)."""
import hashlib, json, os, sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from charkit import brows, code_base, eyes, expressions, exprqa, mouth, qa3d, scene  # noqa: E402

SPEC = os.path.join(ROOT, 'charkit', 'spec', 'clawd.json')
K = mouth._knobs({'smile': 0.22, 'width': 0.13})
L = 1.0


class Flat:
    """a flat face at y = -0.1 (eyes.Face's points/y), for the mouth's parts' shapes."""

    def points(self, x, z):
        x, z = np.broadcast_arrays(np.asarray(x, float), np.asarray(z, float))
        return np.stack([x, np.full(x.shape, -0.1), z], -1).reshape(-1, 3)

    def y(self, x, z):
        return self.points(x, z)[:, 1] if np.ndim(x) or np.ndim(z) else -0.1


F, MC = Flat(), (0.0, 0.0)


def test_block_held():
    """the head's cage holds the mouth block code_base.mouth_block sizes from the library's extremes (the laugh's
    half-width, the yawn's upper lip): the expressions' keys change, the head's rest mesh doesn't (pipeline-3d's
    1141e74 value, to the last bit)."""
    b, loop = code_base.mouth_block(json.load(open(SPEC)))
    assert tuple(float(x) for x in b) == (0.16, 0.1002, 0.09), b
    assert hashlib.sha1(np.ascontiguousarray(loop, float).tobytes()).hexdigest()[:12] == 'f23bf52f51ca'


def test_explicit_smiles():
    """the action mouths set their own smile: none curves up like a grin from the spec's (Clawd's 0.22)."""
    for sh, sm in (('shout', 0.0), ('clench', -0.02), ('grimace', -0.08)):
        assert mouth.SHAPES[sh]['smile'] == sm
        up, lo = mouth.curves(K, L, sh)
        x, zu = up(np.array([0.0, 0.5, 1.0]))
        assert zu[0] < zu[1] + 1e-9                       # the corners not above the upper lip's middle


def test_teeth_tongue_line():
    """the teeth bands sized by the shape's shares of the opening, the tongue under the teeth, the lower lip's line
    open only as the lips part."""
    g_c, gmax_c = mouth._opening(K, L, 'clench', np.array([0.5]))
    tv, tq = mouth.teeth(F, K, L, MC, 'clench')
    n = len(tv) // 4
    up_h = tv[:n, 2] - tv[n:2 * n, 2]                     # the upper band's height (top minus bottom), per column
    assert abs(up_h[n // 2] - (mouth.SHAPES['clench']['teeth'] * gmax_c + 0.006 * L)) < 0.15 * gmax_c
    lo_h = tv[2 * n:3 * n, 2] - tv[3 * n:, 2]
    assert lo_h[n // 2] > 0.006 * L                       # the lower row shows (teeth_lo)
    tv, _ = mouth.teeth(F, K, L, MC, 'laugh')
    lo_h = tv[2 * n:3 * n, 2] - tv[3 * n:, 2]
    assert np.allclose(lo_h, 0.0)                         # none: a band of no height tucked under the lip
    # the tongue: its top never past most of the opening beside the upper teeth
    for sh in ('laugh', 'shout', 'yawn', 'aa'):
        v, _ = mouth.tongue(F, K, L, MC, sh)
        _, lo_f = mouth.curves(K, L, sh)
        up_f, _ = mouth.curves(K, L, sh)
        assert v[:, 2].max() <= up_f(np.array([0.5]))[1][0] + 1e-9
    # closed: no higher over the lower lip than the closed line's own gap (behind the line)
    v, _ = mouth.tongue(F, K, L, MC, 'neutral')
    _, lo_f = mouth.curves(K, L, 'neutral')
    t = np.linspace(0.12, 0.88, 16)
    g, _ = mouth._opening(K, L, 'neutral', t)
    assert np.all(v[-16:, 2] - lo_f(t)[1] <= 0.9 * g + 1e-9)
    # the lower line: thin while the lips meet, line_lo of the upper's width once they part
    for sh, lo_w in (('neutral', 0.15), ('laugh', K['line_lo'])):
        v, q = mouth.line(F, K, L, MC, sh)
        m = len(v) - 2 * 32
        w = np.linalg.norm(v[m:m + 32] - v[m + 32:], axis=1)
        wu = np.linalg.norm(v[:32] - v[32:m], axis=1) if m == 64 else None
        assert w[16] > 0
        if wu is not None:
            assert abs(w[16] / wu[16] - lo_w) < 0.05, (sh, w[16] / wu[16])


def test_jaw_drop():
    """an authored base's lower lip rides the jaw jaw_follow of its drop (the chin's dial)."""
    _, lo_n = mouth.curves(K, L, 'neutral')
    _, lo_s = mouth.curves(K, L, 'laugh')
    d = float(lo_n(0.5)[1] - lo_s(0.5)[1])
    assert abs(mouth.jaw_drop(K, L, 'laugh') - d * K['jaw_follow']) < 1e-12
    assert mouth.jaw_drop(K, L, 'smile') == 0.0


def test_components():
    """the component API: presets as components' keys and weights, layered, every shape in the library."""
    assert expressions.weights('laugh') == {'eye_happy': 1.0, 'mouth_laugh': 1.0, 'brow_raise': 1.0}
    assert expressions.weights('rest') == {} and expressions.weights(None) == {}
    P = expressions.combine('angry', {'mouth': {'shout': 0.6}})
    assert expressions.weights(P) == {'eye_angry': 1.0, 'brow_angry': 1.0, 'mouth_shout': 0.6}
    assert expressions.weights({'mouth': 'neutral', 'eye': {'blink': 0.0, 'half': 0.5}}) == {'eye_half': 0.5}
    try:
        expressions.weights({'nose': 'x'})
        assert False, 'an unknown component passes'
    except KeyError:
        pass
    assert expressions.check() == []
    assert scene.PRESETS is expressions.PRESETS
    lib = expressions.library()
    assert set(lib['eye']) <= set(scene.EXPR) and set(lib['mouth']) <= set(scene.MOUTH)
    # every graded preset has targets, every target a preset; the lid shapes each an opening range
    assert set(exprqa.TARGETS) == set(expressions.PRESETS) - {'rest'}
    assert set(lib['eye']) == set(qa3d.FACE_EXPECT)
    assert set(brows.expressions(brows._knobs({}))) == set(lib['brow'])


def test_closed_lines_held():
    """the blink's and the happy eye's closed lines as before the squeeze's parameters (arch, sharp, drop)."""
    EK = eyes._knobs({})
    t = np.linspace(0, 1, 9)
    W = EK['width']
    x, zb = eyes.outline(EK, 1.0, t, 'lower')
    import math
    base = x * math.tan(math.radians(EK['tilt'])) - EK['inner_drop'] * W * (1 - t) ** 2
    arc = np.sin(np.pi * t) * 0.10 * W
    assert np.array_equal(eyes.closed_line(EK, 1.0, t)[1], base - arc)
    assert np.array_equal(eyes.closed_line(EK, 1.0, t, True)[1], base + arc * 1.6)
    # the squeeze: shut (its upper at or under its lower), arched up
    up, lo = eyes.expressions(EK, 1.0)['squeeze']
    assert np.all(up(t)[1] <= lo(t)[1] + 1e-12) and lo(t)[1][4] > lo(t)[1][0]


# the model sheet's heads (idol_D, as exprqa measures them against the drawing's own neutral; the lab's mouth.json)
DESIGN_NEUTRAL = {'eye_open': 1.0, 'eye_aspect': 0.871, 'iris_ratio': 0.504, 'mouth_width': 0.0609, 'mouth_open': 0.0,
                  'mouth_area': 0.0, 'mouth_fill': 0.0, 'mouth_lift': 0.0714, 'mouth_wave': 0.0, 'mouth_skew': 0.4286,
                  'mouth_teeth': 0.0, 'mouth_tongue': 0.0, 'mouth_line_top': 0.0, 'mouth_line_bottom': 0.0,
                  'brow_tilt': -13.5, 'brow_height': 0.2207, 'brow_z': 0.2274}
HEADS = [
    ('laugh', {'eye_open': 0.0, 'eye_arc': 0.1383, 'mouth_width': 0.2606, 'mouth_open': 0.1528, 'mouth_area': 0.0238,
               'mouth_fill': 0.598, 'mouth_lift': 0.1026, 'mouth_wave': 0.0261, 'mouth_teeth': 0.132,
               'mouth_line_top': 0.72, 'brow_tilt': -12.0, 'brow_z': 0.2236}),
    ('angry', {'eye_open': 1.0, 'eye_aspect': 0.798, 'eye_aspect_rel': 0.9162, 'mouth_width': 0.1348, 'mouth_open': 0.0,
               'mouth_lift': -0.0667, 'mouth_wave': 0.0151, 'brow_tilt': 22.15, 'brow_z': 0.1573}),
    ('fluster', {'eye_open': 1.0, 'iris_ratio': 0.1575, 'iris_ratio_rel': 0.3125, 'mouth_width': 0.2696,
                 'mouth_open': 0.0719, 'mouth_wave': 0.0221, 'mouth_lift': -0.025}),
    ('yawn', {'eye_open': 0.0, 'eye_arc': -0.05, 'mouth_width': 0.1707, 'mouth_open': 0.1797, 'mouth_fill': 0.626,
              'mouth_lift': -0.0382}),
]


def test_targets_calibrated():
    """exprqa.TARGETS pass on the drawn heads (their presets) and fail on the rest face (every preset)."""
    C = exprqa.calibrate_targets(HEADS, DESIGN_NEUTRAL, (DESIGN_NEUTRAL, DESIGN_NEUTRAL))
    assert C['ok'], ({h: g['status'] for h, g in C['design'].items()}, {n: g['status'] for n, g in C['rest'].items()})
    for g in C['rest'].values():
        assert g['miss'] > 1.0
    for g in C['design'].values():
        assert g['miss'] <= 1.0


def test_lab_on_head():
    """the lab on a dumped head (CHARKIT_MOUTH_HEAD: mouthlab --dump's pickle): every mouth key without folds, the
    open ones covered, every graded preset PASS or WARN."""
    path = os.environ.get('CHARKIT_MOUTH_HEAD')
    if not path or not os.path.exists(path):
        print('  (skipped: no CHARKIT_MOUTH_HEAD)')
        return
    from charkit import mouthlab
    M = mouthlab.measure(mouthlab.head_bundle(path))
    for k, r in M['keys'].items():
        assert r['folds'] == 0, (k, r['folds'])
        assert r['cover'] is None or r['cover'] >= 0.9, (k, r['cover'])
    for n, p in M['presets'].items():
        assert p['targets']['status'] in ('PASS', 'WARN', 'INFO'), (n, p['targets'])


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f()
            print('ok', k)
