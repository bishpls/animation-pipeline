"""The measurement steps of the checks charkit/detailqa.py measures (charkit.registry; docs/CHARKIT.md). A step: (check
pattern, the commit that changed the measurement, what changed). Keep a pattern's steps in the order they happened."""

MEASUREMENT_STEPS = [
    # tool/body round 6: the merged hull-det and garment-sampling, the hidden back hem and flaps, Michael's review of round 5
    ('body_front_skirt_overhang_*', '854776f', "new: the skirt's top beside the band, per side and left against right, "
     "beyond the design's (a ledge jutting out sideways)"),
    ('body_profile_leg_back', '854776f', "new: the legs' back edge in profile, its largest bump against the design's"),
    ('body_profile_leg_back', '1fd1c63', "both figures read on the design's facing (face_side had misread ours: the "
     "front edge, offset -5.26 L) and the rows within 0.02 L of either figure's leg ends left out (the design's sloped "
     "boot-cuff line cut its last two rows short at the back: 0.13-0.21 L on every build) (tool/hull-limbs)"),
    ('body_profile_leg_back', '2479a22', "the bare leg (the skin alone, no garments) over the design's leg rows: the "
     "overskirt flaps hanging against the thigh had hidden its edge (the dressed check read PASS on pipeline-3d's "
     "0.108 L bump) (tool/hull-limbs)"),
    ('body_profile_leg_outline', '2479a22', "new (INFO): the dressed outline behind the leg against the design's, a "
     "garment hugging the thigh (tool/hull-limbs, for tool/skirt)"),
    ('body_profile_leg_outline', 'd977ce8', "graded (was INFO): the step outward within 0.05 L, the rows hugging the leg "
     "within 10 of the design's (tool/skirt: the flaps' clearance target)"),
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
