"""The measurement steps of the checks charkit/faceregion.py measures (charkit.registry; docs/CHARKIT.md). A step: (check
pattern, the commit that changed the measurement, what changed). Keep a pattern's steps in the order they happened."""

MEASUREMENT_STEPS = [
    # tool/face: the QA's eyes on the head's eye line; the taper's shape
    ('profile_edge', 'e9a6753', 'registered on the head\'s eye line (faceregion.eye_anchor), not the iris plates\' mean: '
                               'jaw_4 0.0622 -> 0.0278 (its worst row had been the chin\'s corner)'),
    ('jaw_*', 'e9a6753', 'registered on the head\'s eye line (faceregion.eye_anchor): jaw_4 jaw_taper 0.0271 -> 0.0095'),
    ('chin_*', 'e9a6753', 'registered on the head\'s eye line (faceregion.eye_anchor): jaw_4 chin_point_z -0.0224 -> 0'),
    ('neck_to_face', 'e9a6753', 'registered on the head\'s eye line (faceregion.eye_anchor)'),
    ('neck_front_wiggle', 'e9a6753', 'registered on the head\'s eye line (faceregion.eye_anchor)'),
    ('jaw_taper_shape', 'e9a6753', 'new: the front outline\'s w(t)/w(0) from the cheekbone row to the chin against the '
                                  'design\'s, in the boards\' camera'),
    ('jaw_line_bend', 'e9a6753', 'new: the jaw lines\' sharpest local bend (a kink where the silhouette jumps in depth)'),
    ('chin_angle', 'e9a6753', 'new: the V\'s opening near the chin against the design\'s, in the boards\' camera'),
    ('chin_tip', 'e9a6753', 'new: the share of the V\'s turn made at its point (a V, not a U)'),
    ('tq_*', 'e9a6753', 'new: the three-quarter\'s far-cheek hollow and the near jaw line\'s notch at the neck'),
    # tool/face round 3: the head sheet's hair over the face's edge (Michael, 2026-09-30)
    ('jaw_taper_shape', '1129dd5', 'the design read only where its hair leaves the face\'s edge in view (the side locks\' '
                                  'tips at z -0.14 to -0.18 and their inner edges above had been traced as the face), '
                                  'normalised on its widest row in view (z0 -0.113 -> -0.183, w0 0.288 -> 0.264); the '
                                  'mouth\'s line no longer cuts the half-width scan; ours with the hair hidden (jaw_5 '
                                  '0.0281 -> 0.0394, jaw_4 0.0353 -> 0.0421)'),
    ('jaw_taper', '1129dd5', 'the design\'s rows in view only (under z -0.179; its worst row had been the lock\'s tip): '
                            'jaw_5 0.0093 -> 0.0058'),
    ('jaw_line_bend', '1129dd5', 'the jaw lines\' window in t (0.2-0.95) kept at z -0.215 to -0.354 under the new t; ours '
                                'with the hair hidden; the design\'s own 4.4 -> 4.2'),
    ('chin_angle', '1129dd5', 'the outline\'s arc-length samples anchored on the chin (they had moved with where the '
                             'outline was cut): jaw_5 119.7 -> 119.6 (on the 10-degree limit)'),
    ('chin_tip', '1129dd5', 'the outline\'s samples anchored on the chin: jaw_5 0.59 -> 0.584, the design\'s 0.843 -> 0.833'),
    ('tq_cheek_hollow', '1129dd5', 'the far contour stops under the lock over the far cheek (the design\'s 0.0035 at '
                                  'z -0.146 was its tip; now 0.0017 at -0.315), ours on the same rows with the hair '
                                  'hidden'),
    # tool/face5: graded in the design's projection (Michael, 2026-09-30); head_construction under the sheet's hair
    ('jaw_taper_shape', '07ebd58', 'graded in the level camera, orthographic (the design\'s projection), the boards\' '
                                  'camera\'s value beside (board): f4_after 0.0399 board -> 0.0193'),
    ('jaw_line_bend', '07ebd58', 'the level camera\'s bend, orthographic (was the worse of the two cameras)'),
    ('chin_angle', '07ebd58', 'graded in the level camera, orthographic (the design\'s projection; the boards\' raised '
                             'perspective shortens the V): f4_after 118.8 -> 128.3'),
    ('chin_tip', '07ebd58', 'graded in the level camera, orthographic: f4_after 0.826 -> 0.829'),
    ('tq_*', '07ebd58', 'the level camera\'s, orthographic (was the worse of the two cameras)'),
    ('jaw_line_*', '07ebd58', 'ours read in the level camera, orthographic (was the boards\'): f4_after front 0.937 -> '
                             '1.158, three-quarter 1.106 -> 1.133'),
    ('jaw_taper', '07ebd58', 'the level camera orthographic (was 100 m out)'),
    ('chin_point_z', '07ebd58', 'the level camera orthographic (was 100 m out)'),
    ('chin_v', '07ebd58', 'the level camera orthographic (was 100 m out)'),
    ('neck_to_face', '07ebd58', 'the level camera orthographic (was 100 m out)'),
    ('chin_underside', '07ebd58', 'the level camera orthographic (was 100 m out)'),
    ('neck_front_wiggle', '07ebd58', 'the level camera orthographic (was 100 m out)'),
    ('jaw_outline_hidden', '07ebd58', 'new: ours\' front outline against head_construction\'s (registered on the head '
                                     'sheet: 0.002 L rms where both show the face) from the sheet\'s hair-occlusion row '
                                     'to z -0.05 (a flag check: the face curving in under the locks)'),
    # tool/face5 round 7 (2026-09-30): each check discriminating from its calibration triple (charkit/calib/jaw.py;
    # records in charkit/calib/records/; the coordinator's brief: never looser)
    ('chin_angle', '72eb64a', 'the value is |ours - the design\'s| (ours beside); PASS 10 -> 1.45 deg from the triple '
                             '(affine 4.8, widths 2.9, other_view 12.0): f5m 128.2 PASS -> 1.5 WARN'),
    ('chin_underside', '72eb64a', 'the value is |ours - the design\'s|; PASS 6 -> 0.4 deg (affine 1.5, widths 0.8): f5m '
                                 '14.1 PASS -> 0.4 PASS'),
    ('chin_v', '72eb64a', 'the value is |the rise over the design\'s - 1|, the rise on the face\'s outline (sub-pixel; '
                         'was whole rows, 8% steps); PASS 0.15 -> 0.042 (affine 0.084, widths 0.084): f5m 1.084 PASS -> '
                         '0.09 WARN'),
    ('jaw_taper', '72eb64a', 'PASS 0.015 -> 0.0102 L (widths_jaw 0.0125 passed it): f5m 0.0052 PASS'),
    ('jaw_taper_shape', '72eb64a', 'PASS 0.025 -> 0.0141 (the floor\'s median sat on 0.025): f5m 0.0157 PASS -> WARN'),
    ('neck_to_face', '72eb64a', 'remeasured: the face\'s share of the figure\'s width over the 0.05 L above the design\'s '
                               'chin against the design\'s (was the neck\'s width over the face\'s: jaw_0, Michael\'s '
                               'flag, read WARN 0.777, now 0.446 FAIL); PASS 0.0867, WARN 0.24: f5m 0.972 PASS -> 0.0465 '
                               'PASS'),
    ('neck_front_wiggle', '72eb64a', 'ours read on the design\'s band (0.25 L under the throat, was 0.1: the design\'s '
                                    'neck front is behind a lock there), the run ended at the neck\'s foot (a 0.01 L '
                                    'jump in a row): f5m 5.4 -> 4.8 PASS, the design 4.7'),
]
