"""The measurement steps of the checks charkit/hairflagqa.py measures (charkit.registry; docs/CHARKIT.md). A step: (check
pattern, the commit that changed the measurement, what changed). Keep a pattern's steps in the order they happened."""

MEASUREMENT_STEPS = [
    # tool/hair5 (charkit/hairflagqa.py): Michael's hair flags (2026-09-30 evening, preview 1580f95)
    ('hair_ahoge_*', '31e6654', "new: the ahoge per view against the drawn one: its shape (the boundary F-score at the "
     "best placement within 0.03 L) and its centreline's bend beyond a steady curl"),
    ('hair_attached', '31e6654', "new: every non-mass hair part's gap to the rest of the hair per view (the floating "
     "flyaway by the right bun)"),
    ('hair_back_lines', '31e6654', "new: the back view's ink inside the mass (our outline hulls as the render draws "
     "them) per L^2 beyond the drawing's (the vertical stripes)"),
    ('hair_back_hem', '31e6654', "new: the back view's hem tips against the drawing's (the smooth bob)"),
    ('hair_lock_lines_*', '31e6654', "new: the layering's ink inside the mass (our outline hulls) in three-quarter and "
     "profile against the drawn lines, a line F-score (the solid mass, the janky layering)"),
    # tool/hairstrokes: the hair's ink strokes (charkit.geom.hairink's ribbons on an ink slot) are lines, not hair: drawn
    # as ink inside the mass (our_ink) and left out of the hair's parts (our_labels); unchanged on a build without strokes
    ('hair_back_lines', 'ae33ac8', "our ink strokes (an ink slot's faces) drawn as ink inside the mass beside the "
     "outline hulls (unchanged without strokes)"),
    ('hair_lock_lines_*', 'ae33ac8', "our ink strokes (an ink slot's faces) drawn as ink inside the mass beside the "
     "outline hulls (unchanged without strokes)"),
]
