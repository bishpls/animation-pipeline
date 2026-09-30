"""The measurement steps of the checks charkit/skirtqa.py measures (charkit.registry; docs/CHARKIT.md). A step: (check
pattern, the commit that changed the measurement, what changed). Keep a pattern's steps in the order they happened."""

MEASUREMENT_STEPS = [
    # tool/skirt (charkit/skirtqa.py): Michael's review of round 6's flaps, stepped band and back
    ('flap_*', '9153f09', "new: each overskirt flap per view against the whole drawn flap (its face over the skirt filled "
     "between the drawn lines, its tail, its band): IoU, width down its length, attach, hang angle, the profile's sweep"),
    ('skirt_pleat*', '21d28e4', "new here (tool/garments2 cda2b7f's measure, moved): the skirt's orange and cream pleats and "
     "their order against skirt_closeup's top-down view"),
    ('skirt_tuck_jut', '0020f98', "new: 3D, how far the skirt and flaps stand past the band's outer surface where they come out "
     "from under its lower edge"),
    ('flap_profile_clear_*', '4a2bac1', "new: the train's clearance behind the leg in profile against the drawing's (the "
     "drawn flaps hang 0.55-1.0 L clear of the thigh; round 6's hung against it)"),
    ('hemband_*', '9153f09', "new: the stepped band on the skirt's hem and on each flap: its steps (risers between treads "
     "on the band's top edge), their size and the band's height against the drawing's"),
    ('skirt_back_*', '9153f09', "new: the back view's skirt-and-flaps outline, the gap between the flaps and what shows in "
     "it"),
]
