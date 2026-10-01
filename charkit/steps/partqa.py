"""The measurement steps of the checks charkit/partqa.py measures (charkit.registry; docs/CHARKIT.md). A step: (check
pattern, the commit that changed the measurement, what changed). Keep a pattern's steps in the order they happened."""

MEASUREMENT_STEPS = [
    # tool/pieceref (charkit/partqa.py): the bow's parts and the lines drawn inside them (Michael, 2026-09-30)
    ('bow_part_*', 'e992be8', "new: the bow's knot and lobes against the drawn parts (outline agreement per view), the "
     "knot's outline against the lobes and its rectangle, each lobe's crease (the lines inside it: length over width, "
     "direction), ours drawn with the build's outlines against the design's lines"),
    ('bow_part_knot_line', 'd814b6a2', "the knot's outline share reaches the outline's own width (was 2 px: an outlined "
     "knot read None, its lines 3-5 px wide at 400 px/L)"),
    ('bow_part_knot_iou', '2a71baff', "graded on the front only (partqa.GRADED; coordinator, round 4: the turnaround "
     "draws its three-quarter knot face-on, ours matching it only turned 15-20 deg against the sheet's 35.5, and in "
     "profile a sliver in the loops); the three-quarter and profile knots reported as info"),
    ('bow_part_knot_iou', '480f0a19', "graded on its own tighter lines (LIMITS 'knot_iou' 0.9 / 0.7, was the lobes' "
     "0.6 / 0.45) from its calibration triple: at the grid's scale it reads the knot's placement (the design moved "
     "1-4 px 0.94-1.0); the flagged knots (pipeline-3d's 0.536, g3_render3's 0.467) read WARN before (blind), FAIL now"),
]
