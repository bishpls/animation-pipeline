"""The measurement steps of the checks charkit/lookqa.py measures (charkit.registry; docs/CHARKIT.md). A step: (check
pattern, the commit that changed the measurement, what changed). Keep a pattern's steps in the order they happened."""

MEASUREMENT_STEPS = [
    # tool/look2: the look QA's speedup
    ('line_ink', '0b6e9cd', 'the lines\' own colour (their supersampled pixels before the pixel filter), not the pixels a '
     'line covers wholly after it (blended with their neighbours): the inked hair, garment and accessory lines read '
     '0.48 from the design\'s ink, were 4.5, 7.8 and 15.6; the skin\'s brown 24.67, was 24.9 (tool/look2)'),
    # tool/look3: Michael's call I (a thin shell's outline moves inward at most half its thickness, the rest outward)
    ('line_width', '22a1ae7', 'the QA draws a capped outline as Blender does: the surface in by the cap and the hull the '
     'rest of the width outside the original surface (it had the hull at the original surface and scaled the shrink '
     'linearly to the design\'s scale, so a thin garment\'s inner layer poked past it and ate its line); on the same '
     'build the garment lines\' median at the design\'s scale reads 2.75 px, was 1.99; line_width 1.133, was 0.942 '
     '(tool/look3)'),
    ('line_spread', '22a1ae7', 'the same capped outline model as line_width (tool/look3)'),
]
