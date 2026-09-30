"""The measurement steps of the checks charkit/detailqa.py measures (charkit.registry; docs/CHARKIT.md). A step: (check
pattern, the commit that changed the measurement, what changed). Keep a pattern's steps in the order they happened."""

MEASUREMENT_STEPS = [
    # tool/body round 6: the merged hull-det and garment-sampling, the hidden back hem and flaps, Michael's review of round 5
    ('body_front_skirt_overhang_*', '854776f', "new: the skirt's top beside the band, per side and left against right, "
     "beyond the design's (a ledge jutting out sideways)"),
    ('body_profile_leg_back', '854776f', "new: the legs' back edge in profile, its largest bump against the design's"),
    # tool/body round 5 (charkit/detailqa.py): Michael's review of round 4's midriff and boots
    ('body_*_torso_jump_*', '843922c', "new: the torso outline's largest step from under the bust to the skirt, "
     "outward and inward, beyond the design's (the top and the band sliced and shifted)"),
    ('body_*_midriff_gap', '843922c', "new: the top's hem against the band's top: a see-through gap or the top over "
     'the band'),
    ('body_front_panel_edge', '843922c', "new: the cream panel's lower part: its outline's roughness, fragments and "
     "holes against the design's (a torn edge)"),
    ('boot_*', '843922c', "new: the boots' ankle jog and bend, the ankle's folds front and back, the heel block, doubled "
     'outline strokes, the soles in 3D (flat, twist) and the left/right mirror'),
]
