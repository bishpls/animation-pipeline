"""charkit.refcheck on synthetic drawings with known answers (venv: run this file, or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import faceqa, refcheck


def test_guide_lines_are_painted_out_and_the_head_kept():
    H, W = 400, 600
    rgb = np.full((H, W, 3), 0.76)                                        # the grey paper
    yy, xx = np.mgrid[:H, :W]
    head = (yy - 200) ** 2 + (xx - 300) ** 2 < 120 ** 2
    rgb[head] = (0.97, 0.85, 0.76)                                        # a skin disk
    for y in (100, 230, 330):                                             # guide lines across paper and skin alike
        rgb[y:y + 2] = 0.35
    out, rows = refcheck.without_guides(rgb)
    assert len(rows) == 3 and all(abs(r - y) <= 2 for r, y in zip(rows, (100, 230, 330))), rows
    assert np.allclose(out[230, 300], (0.97, 0.85, 0.76), atol=0.02)      # the skin under the line comes back
    assert np.allclose(out[100, 50], 0.76, atol=0.02)                     # and the paper
    away = head & np.all([np.abs(yy - y) > 6 for y in (100, 230, 330)], 0)   # the rest of the head is untouched
    assert np.allclose(out[away], rgb[away])


def test_drawn_chin_finds_the_turn_to_the_neck_on_a_receding_profile():
    """an anime profile's lower face slopes back from the nose to the chin, then the edge jumps back to the neck."""
    z = np.arange(0.0, -0.6, -0.005)
    lead = np.where(z > -0.36, 0.16 + 0.54 * (z + 0.1), -0.2)            # receding 0.54 L per L (head_turnaround's
                                                                          # profile, measured), then the neck
    lead[z > -0.1] = np.nan
    chin = refcheck.drawn_chin(lead, z)
    assert abs(chin - (-0.355)) < 0.01, chin
    # the QA's rule for our 3D face (the chin as the most forward point) stops halfway down the slope on a drawing
    assert faceqa.chin_bottom(-lead, z, -0.2) > -0.34



def test_checks_are_graded_only_against_their_measures_authority():
    from charkit import checks
    A = {'body_silhouette': 'sheet', 'hair_shape': 'hull', 'expressions': None, 'face_depth': 'hull'}
    C = {'shape_iou': {'value': 0.74, 'status': 'WARN'},                 # the silhouette against the hull: not its authority
         'shape_iou_hair': {'value': 0.97, 'status': 'PASS'},            # the hair shape against the hull: its authority
         'body_front_iou': {'value': 0.78, 'status': 'WARN'},            # against the sheet: its authority
         'expr_laugh_mouth': {'value': 0.2, 'status': 'FAIL'},           # expressions: no reference
         'face_shape_depth': {'value': 0.02, 'status': 'WARN'},
         'poke_share': {'value': 0.01, 'status': 'WARN'}}                # no measure: untouched
    checks.authorize(C, A)
    assert C['shape_iou']['status'] == 'INFO' and C['shape_iou']['graded_as'] == 'WARN' and C['shape_iou']['value'] == 0.74
    assert C['expr_laugh_mouth']['status'] == 'INFO'
    assert [C[k]['status'] for k in ('shape_iou_hair', 'body_front_iou', 'face_shape_depth', 'poke_share')] == \
        ['PASS', 'WARN', 'WARN', 'WARN']


def test_the_manifest_fills_the_design_sheets_from_the_generated_references():
    from charkit import manifest
    spec = {'name': 'clawd', 'ref': {'manifest': 'charkit/refs/clawd/manifest.json'}}
    ref = manifest.resolve(spec)['ref']
    assert ref['face_sheet']['id'] == 'head_turnaround' and ref['eyes_sheet']['id'] == 'head_turnaround'
    assert ref['body_sheet']['id'] == 'body_turnaround' and ref['body_sheet']['layout'] == 'figures'
    assert ref['authority']['eyes'] == 'sheet' and ref['authority']['expressions'] is None
    assert ref['sheet']['image'].endswith('idol_D.png')                  # the source design, still resolved for refs.fit


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)


def test_at_scale_takes_its_closest_attempt_when_the_eyes_read_unevenly():
    """small dark eyes read their spacing to a pixel or so, not linearly in the factor: at_scale never landed within
    0.3 px and raised (a second character's head sheet, 2026-10-01). Its closest attempt within AT_SCALE_NEAR is taken;
    a sheet that converges returns as before; one off by more still raises."""
    real = refcheck.detect_heads
    rgb = np.zeros((40, 60, 3))

    def jittery(native, jit):
        def fake(img, eye_x, facing=-1):
            f = img.shape[1] / 60.0
            k = int(round(f * 1000))
            return dict(ppl=(native * f + (jit if k % 2 else -jit)) / (2 * eye_x), heads={})
        return fake
    try:
        refcheck.detect_heads = jittery(100.0, 1.0)              # +-1 px however the factor is tuned
        small, f, H = refcheck.at_scale(rgb, 0.168, 120.0, guess=1.0)
        assert abs(H['ppl'] * 2 * 0.168 - 120.0) <= refcheck.AT_SCALE_NEAR * 120.0
        refcheck.detect_heads = jittery(100.0, 0.0)              # converges: within 0.3 px
        small, f, H = refcheck.at_scale(rgb, 0.168, 120.0, guess=1.0)
        assert abs(H['ppl'] * 2 * 0.168 - 120.0) <= 0.3
        refcheck.detect_heads = jittery(100.0, 10.0)             # never within 1%: raises
        try:
            refcheck.at_scale(rgb, 0.168, 120.0, guess=1.0)
            assert False, 'expected RuntimeError'
        except RuntimeError:
            pass
    finally:
        refcheck.detect_heads = real
