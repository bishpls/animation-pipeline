"""The measurement steps of the checks charkit/handqa.py measures (charkit.registry; docs/CHARKIT.md). A step: (check
pattern, the commit that changed the measurement, what changed). Keep a pattern's steps in the order they happened."""

MEASUREMENT_STEPS = [
    # tool/hands (charkit/handqa.py): the hands, nothing measured them before (docs/workstreams/hands.md)
    ('hand_*', 'ee2eca7', "new: each hand (the skin past its wrist cuff) against the design's drawn hand per view: its "
     "shape (IoU laid on the centroids), its reach past the cuff, the digits across its fingers (the design's ink, our "
     "seams), its deepest silhouette pocket (the thumb's cleft)"),
]
