"""The measurement steps of the checks charkit/hairflagqa.py measures (charkit.registry; docs/CHARKIT.md). A step: (check
pattern, the commit that changed the measurement, what changed). Keep a pattern's steps in the order they happened."""

MEASUREMENT_STEPS = [
    # tool/hair5 (charkit/hairflagqa.py): Michael's hair flags (2026-09-30 evening, preview 1580f95)
    ('hair_ahoge_*', '4d2d2fc', "new: the ahoge per view against the drawn one: its shape (the boundary F-score at the "
     "best placement within 0.03 L) and its centreline's bend beyond a steady curl"),
    ('hair_attached', '4d2d2fc', "new: every non-mass hair part's gap to the rest of the hair per view (the floating "
     "flyaway by the right bun)"),
    ('hair_back_lines', '4d2d2fc', "new: the back view's ink inside the mass (our part boundaries) per L^2 beyond the "
     "drawing's (the vertical stripes)"),
    ('hair_back_hem', '4d2d2fc', "new: the back view's hem tips against the drawing's (the smooth bob)"),
    ('hair_lock_lines_*', '4d2d2fc', "new: the layering's ink inside the mass in three-quarter and profile against the "
     "drawn lines, a line F-score (the solid mass, the janky layering)"),
]
