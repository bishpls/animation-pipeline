"""The measurement steps of the checks charkit/isoqa.py measures (charkit.registry; docs/CHARKIT.md). A step: (check
pattern, the commit that changed the measurement, what changed). Keep a pattern's steps in the order they happened."""

MEASUREMENT_STEPS = [
    # tool/pieceref (charkit/isoqa.py): rigid pieces alone against their isolated shape references (Michael, 2026-09-30)
    ('iso_bow_*', 'ba2a347', "new: the bow drawn alone in its shape reference's projection (garment_breakdown's flat-lay), "
     "both scaled to the body's width: its body, tails, knot size and rectangle (INFO: the reference's outline "
     "disagrees with the turnaround's), the knot's outline and each lobe's crease (graded), the turnaround's bow "
     "against the reference (refcheck, INFO)"),
    ('iso_bow_*', 'f824be4c', "the bow's outline against bow_closeup (shape_bow: its front bow agrees with the turnaround's, "
     "body IoU 0.871 against the breakdown's 0.762), the lines inside it against garment_breakdown (lines_bow); "
     "iso_bow_body graded (flag); the knot's outline share reaches the picture's line width"),
]
