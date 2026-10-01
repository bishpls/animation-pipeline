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
    ('iso_bow_body', 'da26c03b', "the body compared as its silhouette (isoqa.silhouette: the parts with the lines next to "
     "them taken in, holes filled, both sides): the drawn creases cost the parts-only IoU a share per line; the "
     "calibration set keeps its grades (turnaround 0.871 -> 0.917 PASS, b2_close 0.744 -> 0.772 WARN, b2_before 0.616 "
     "-> 0.679 FAIL, g3_render3 0.659 -> 0.724 FAIL)"),
]
