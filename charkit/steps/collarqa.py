"""The measurement steps of the checks charkit/collarqa.py measures (charkit.registry; docs/CHARKIT.md). A step: (check
pattern, the commit that changed the measurement, what changed). Keep a pattern's steps in the order they happened."""

MEASUREMENT_STEPS = [
    # tool/collar (charkit/collarqa.py): Michael's flags on the shoulders, the sailor collar and the bow (2026-09-30)
    ('shoulder_back_*', '89bb724', "new: the back view's shoulder line (the upper garments' top edge over |x| "
     "0.25-0.55 L) against the design's: its height, and its slope as a guard"),
    ('collar_back_*', '89bb724', "new: the sailor collar's back panel against the drawn one: IoU, squareness (its width "
     "90% down over 50%) and its lay (the trough between the panel's edge and the shoulder)"),
    ('bow_front_loop_*', '89bb724', "new: the bow's loops in front: their outer ends' straight share (the cut-off "
     "sides), and their span as a guard"),
    ('bow_front_bleed', '89bb724', "new: the bow's cream touching the jacket with no line between, drawn with the "
     "build's outlines, against the design's"),
    ('bow_profile_ribbon', '89bb724', "new: in profile, the ribbons' width seen in front of the jacket against the "
     "design's"),
]
