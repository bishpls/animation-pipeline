"""The measurement steps of the checks charkit/handqa.py measures (charkit.registry; docs/CHARKIT.md). A step: (check
pattern, the commit that changed the measurement, what changed). Keep a pattern's steps in the order they happened."""

MEASUREMENT_STEPS = [
    # tool/hands (charkit/handqa.py): the hands, nothing measured them before (docs/workstreams/hands.md)
    ('hand_*', 'ee2eca7', "new: each hand (the skin past its wrist cuff) against the design's drawn hand per view: its "
     "shape (IoU laid on the centroids), its reach past the cuff, the digits across its fingers (the design's ink, our "
     "seams), its deepest silhouette pocket (the thumb's cleft)"),
    ('hand_*', '09ddfa2', "a hand partly hidden by the figure (our_hidden: the hand z-buffered alone): its shape graded "
     "over the pixels that show, its reach the whole hand's, its digits and cleft not read below 75% visible"),
    # tool/hands2 (round 4, Michael 2026-10-01: the hand "clearly extremely off-model" while hand_shape passed): the
    # existing checks' values unchanged on the same bundle (hands_b4: all 22 read identically); new checks beside them
    ('hand_*', 'c6aceaa', "new: the structure inside the silhouette the IoU can't see, along the reach past the cuff: "
     "gaps (the fingertips' span with no hand in it), taper (the fingertips' width over the widest), cleftpos (where "
     "the deepest silhouette pocket lies: the thumb's cleft); the width profile in the table"),
    ('hand_*', '4c76150', "gaps and taper report-only where the view can't show them (EDGE_ON: profile L, the far hand "
     "in 3q), cleftpos limits tightened to 0.04/0.055, the wrist's narrowing in the table"),
]
