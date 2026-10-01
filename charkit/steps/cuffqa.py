"""The measurement steps of the checks charkit/cuffqa.py declares (measured by charkit/declared.py's area family;
charkit.registry; docs/CHARKIT.md). A step: (check pattern, the commit that changed the measurement, what changed). Keep
a pattern's steps in the order they happened."""

MEASUREMENT_STEPS = [
    # tool/garments4 Part 2, the cuffs (Michael's garment list, 2026-09-30, item 2)
    ('cuff_*_size', 'bffdfe4a', "new, and against the drawn cuff's silhouette (declared.area ref 'silhouette': the "
     "drawing's lines inside the figure given to the nearest piece, bodymeasure.drawn_labels) instead of its fill: "
     "against the fill the design moved 1-2 px read 0.23-0.24 off itself (the silhouette is ~1.23x the fill); limits "
     "[0.1, 0.2] from the defect (the flagged cuffs 1.24-1.33x the silhouette)"),
]
