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
]
