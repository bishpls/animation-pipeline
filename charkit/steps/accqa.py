"""The measurement steps of the checks charkit/accqa.py measures (charkit.registry; docs/CHARKIT.md). A step: (check
pattern, the commit that changed the measurement, what changed). Keep a pattern's steps in the order they happened."""

MEASUREMENT_STEPS = [
    # tool/acc-reclass: the hair clips against the design's, per clip and view (docs/workstreams/accessories.md)
    ('acc_*', '9bfbc8b', "new: each hair clip's shape (IoU aligned on centroid and area), size, position and axis per "
     "view against the head turnaround's drawn clip, whether it shows where the design does, its seat on the hair (the "
     "least of its vertices' heights over the hair under them), its triangulated 3D place and its colour; limits "
     "calibrated on the design against itself (the body turnaround's clips pass), the placeholders fail 26 of 30 graded"),
]
