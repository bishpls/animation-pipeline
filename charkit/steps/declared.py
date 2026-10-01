"""The measurement steps of the checks charkit/declared.py's families measure (charkit.registry; docs/CHARKIT.md): the
declarations live in their owners' modules (charkit/hairstrokeqa.py, ...), the measuring code here and in what it calls
(charkit/hairweight.py for line_weight). A step: (check pattern, the commit that changed the measurement, what
changed). Keep a pattern's steps in the order they happened."""

MEASUREMENT_STEPS = [
    # tool/hairtruth: the hair as a piece against its shape truth (charkit.shapetruth; Michael 2026-10-01: hair checks
    # against the no-accessories references): the drawn hair, its lines and strokes from the body turnaround with its
    # clips repainted from hair_clips_layers, the head sheet likewise for line_weight; ours drawn without our clips
    # (pieceqa.our_labels, our_lines, our_ink and hairweight.our_head with hide). Measured on pipeline-3d cd1c327f's
    # default build (old measure -> new, the same geometry)
    ('hair_strokes_*', '7f189116', "the hair against its shape truth (charkit.shapetruth; Michael 2026-10-01: hair checks against the no-accessories references): density 0.417 / 0.395 / 0.587 -> 0.371 / 0.360 / 0.414 (front / three-quarter / "
     "profile), dir 13.7 / 8.8 / 15.0 -> 16.8 / 11.1 / 11.2, weight 0.308 / 0.126 / 0.381 -> 0.244 / 0.152 / 0.205, "
     "taper 0.455 / 0.583 / 0.727 -> 0.591 / 0.560 / 0.667"),
    ('bun_*_lines', '7f189116', "the hair against its shape truth (charkit.shapetruth; Michael 2026-10-01: hair checks against the no-accessories references): bun_L_front_lines 0.009 -> 0.018, the rest unchanged"),
]
