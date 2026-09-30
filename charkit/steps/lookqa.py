"""The measurement steps of the checks charkit/lookqa.py measures (charkit.registry; docs/CHARKIT.md). A step: (check
pattern, the commit that changed the measurement, what changed). Keep a pattern's steps in the order they happened."""

MEASUREMENT_STEPS = [
    # tool/look2: the look QA's speedup
    ('line_ink', '0b6e9cd', 'the lines\' own colour (their supersampled pixels before the pixel filter), not the pixels a '
     'line covers wholly after it (blended with their neighbours): the inked hair, garment and accessory lines read '
     '0.48 from the design\'s ink, were 4.5, 7.8 and 15.6; the skin\'s brown 24.67, was 24.9 (tool/look2)'),
]
