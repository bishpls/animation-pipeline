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
    # tool/toonrender2: the default drawing
    ('face_noise', '32e9b1e', "the QA draws with charkit.render (qa3d.DRAW 'render', tool/toonrender2): the boards' shader and passes on the build's export, not qa3d's numpy rasteriser; every QA frame nearer EEVEE's (docs/workstreams/toonrender.md); tone edges on colour-classified maps 0.0565 against EEVEE's 0.0566 (numpy 0.0569); tr3_a 0.0552 -> 0.0546, noise 0.0002"),
    ('face_noise_sweep', '32e9b1e', "the QA draws with charkit.render (qa3d.DRAW 'render', tool/toonrender2): the boards' shader and passes on the build's export, not qa3d's numpy rasteriser; every QA frame nearer EEVEE's (docs/workstreams/toonrender.md); sweep tones 99.97% EEVEE's (numpy 99.79%)"),
    ('face_islands', '32e9b1e', "the QA draws with charkit.render (qa3d.DRAW 'render', tool/toonrender2): the boards' shader and passes on the build's export, not qa3d's numpy rasteriser; every QA frame nearer EEVEE's (docs/workstreams/toonrender.md)"),
    ('face_shadow_*', '32e9b1e', "the QA draws with charkit.render (qa3d.DRAW 'render', tool/toonrender2): the boards' shader and passes on the build's export, not qa3d's numpy rasteriser; every QA frame nearer EEVEE's (docs/workstreams/toonrender.md); the face and neck shade shares equal EEVEE's to 4 decimals (numpy up to 0.003 off)"),
    # tool/look2 -> tool/look5: the face measures on the bare head
    ('face_noise', 'd082a27', "the head drawn bare, as head_turnaround draws it (tool/look2 d082a27, landed by tool/look5): the garments left out and the skin unmasked under them (the bundle's 'bare' skin; the render drawing reads the look export's NAME.bare). With the collar on, the neck window held only a strip between the chin and the collar (round 1's band read IoU 0.85 there). A build without a bare skin (before tool/look5) is still drawn dressed"),
    ('face_noise_sweep', 'd082a27', "the head drawn bare, as head_turnaround draws it (tool/look2 d082a27, landed by tool/look5): the garments left out and the skin unmasked under them (the bundle's 'bare' skin; the render drawing reads the look export's NAME.bare). With the collar on, the neck window held only a strip between the chin and the collar (round 1's band read IoU 0.85 there). A build without a bare skin (before tool/look5) is still drawn dressed"),
    ('face_islands', 'd082a27', "the head drawn bare, as head_turnaround draws it (tool/look2 d082a27, landed by tool/look5): the garments left out and the skin unmasked under them (the bundle's 'bare' skin; the render drawing reads the look export's NAME.bare). With the collar on, the neck window held only a strip between the chin and the collar (round 1's band read IoU 0.85 there). A build without a bare skin (before tool/look5) is still drawn dressed"),
    ('face_shadow_3q', 'd082a27', "the head drawn bare, as head_turnaround draws it (tool/look2 d082a27, landed by tool/look5): the garments left out and the skin unmasked under them (the bundle's 'bare' skin; the render drawing reads the look export's NAME.bare). With the collar on, the neck window held only a strip between the chin and the collar (round 1's band read IoU 0.85 there). A build without a bare skin (before tool/look5) is still drawn dressed"),
    ('face_shadow_face_3q', 'd082a27', "the head drawn bare, as head_turnaround draws it (tool/look2 d082a27, landed by tool/look5): the garments left out and the skin unmasked under them (the bundle's 'bare' skin; the render drawing reads the look export's NAME.bare). With the collar on, the neck window held only a strip between the chin and the collar (round 1's band read IoU 0.85 there). A build without a bare skin (before tool/look5) is still drawn dressed"),
    ('face_shadow_neck_3q', 'd082a27', "the head drawn bare, as head_turnaround draws it (tool/look2 d082a27, landed by tool/look5): the garments left out and the skin unmasked under them (the bundle's 'bare' skin; the render drawing reads the look export's NAME.bare). With the collar on, the neck window held only a strip between the chin and the collar (round 1's band read IoU 0.85 there). A build without a bare skin (before tool/look5) is still drawn dressed"),
]
