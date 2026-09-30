"""The measurement steps of the checks charkit/isoqa.py measures (charkit.registry; docs/CHARKIT.md). A step: (check
pattern, the commit that changed the measurement, what changed). Keep a pattern's steps in the order they happened."""

MEASUREMENT_STEPS = [
    # tool/pieceref (charkit/isoqa.py): rigid pieces alone against their isolated shape references (Michael, 2026-09-30)
    ('iso_bow_*', 'ba2a347', "new: the bow drawn alone in its shape reference's projection (garment_breakdown's flat-lay), "
     "both scaled to the body's width: its body, tails, knot size and rectangle (INFO: the reference's outline "
     "disagrees with the turnaround's), the knot's outline and each lobe's crease (graded), the turnaround's bow "
     "against the reference (refcheck, INFO)"),
]
