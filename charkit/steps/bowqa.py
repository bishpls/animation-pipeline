"""The measurement steps of the checks charkit/bowqa.py measures (charkit.registry; docs/CHARKIT.md). A step: (check
pattern, the commit that changed the measurement, what changed). Keep a pattern's steps in the order they happened."""

MEASUREMENT_STEPS = [
    # tool/bow2 (charkit/bowqa.py): Michael's flag on the bow in profile (2026-09-30): the ribbon tails project far
    # forward of the chest as flat blades; the loops read as flat disks
    ('bow_profile_tail_*', 'd179a05', "new: the ribbons in profile: the bow's front edge per row from the knot down "
     "the drawn tails against the design's (the forward projection), and its chord from the knot to the tails' foot "
     "from the vertical against the design's (the hang)"),
    ('bow_profile_loop_*', 'd179a05', "new: the loops in profile: their run per row at tenths of the drawn loops' "
     "height against the design's (the thickness where it is), and their silhouette's lean against the design's"),
]
