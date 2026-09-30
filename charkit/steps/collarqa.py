"""The measurement steps of the checks charkit/collarqa.py measures (charkit.registry; docs/CHARKIT.md). A step: (check
pattern, the commit that changed the measurement, what changed). Keep a pattern's steps in the order they happened."""

MEASUREMENT_STEPS = [
    # tool/collar (charkit/collarqa.py): Michael's flags on the shoulders, the sailor collar and the bow (2026-09-30)
    ('shoulder_back_*', 'a12f99d', "new: the back view's shoulder line (the upper garments' top edge over |x| "
     "0.25-0.55 L) against the design's: its height, and its slope as a guard"),
    ('collar_back_*', 'a12f99d', "new: the sailor collar's back panel against the drawn one: IoU, squareness (its width "
     "90% down over 50%) and its lay (the trough between the panel's edge and the shoulder)"),
    ('bow_front_loop_*', 'a12f99d', "new: the bow's loops in front: their outer ends' straight share (the cut-off "
     "sides), and their span as a guard"),
    ('bow_front_bleed', 'a12f99d', "new: the bow's cream touching the jacket with no line between, drawn with the "
     "build's outlines, against the design's"),
    ('bow_profile_ribbon', 'a12f99d', "new: in profile, the ribbons' width seen in front of the jacket against the "
     "design's"),
    # tool/pieceref: Michael's call C (2026-09-30) on the close-hung ribbons
    ('bow_profile_ribbon', '2dc325a', "remeasured as what the flag meant, the ribbons merging into the jacket: per row "
     "over 30-80% of the drawn tails' height in profile, whether the widest ribbon run is at least 0.03 L and touches no "
     "jacket or sleeve pixel (an ink line between), drawn with the build's outlines; the share of rows that don't, "
     "beyond the design's (was: the ribbons' width seen in profile over the design's, which asked for a depth the "
     "close-hung ribbons can't give)"),
]
