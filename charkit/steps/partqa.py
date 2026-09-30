"""The measurement steps of the checks charkit/partqa.py measures (charkit.registry; docs/CHARKIT.md). A step: (check
pattern, the commit that changed the measurement, what changed). Keep a pattern's steps in the order they happened."""

MEASUREMENT_STEPS = [
    # tool/pieceref (charkit/partqa.py): the bow's parts and the lines drawn inside them (Michael, 2026-09-30)
    ('bow_part_*', 'e992be8', "new: the bow's knot and lobes against the drawn parts (outline agreement per view), the "
     "knot's outline against the lobes and its rectangle, each lobe's crease (the lines inside it: length over width, "
     "direction), ours drawn with the build's outlines against the design's lines"),
]
