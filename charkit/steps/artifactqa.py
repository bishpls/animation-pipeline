"""The measurement steps of the checks charkit/artifactqa.py measures (charkit.registry; docs/CHARKIT.md). A step:
(check pattern, the commit that changed the measurement, what changed). Keep a pattern's steps in the order they
happened."""

MEASUREMENT_STEPS = [
    # tool/artifacts: jaggedness per region and view (charkit.artifactqa), INFO with a proposed grade
    ('art_outline_*', '1b2a283', 'new (tool/artifacts): corners per L of each region\'s outline (a turn of 40 degrees or '
     'more over 0.005 L) against the design turnarounds\' (the worst view\'s ratio)'),
    ('art_terminator_*', '1b2a283', 'new (tool/artifacts): kinks per L of the cel terminators inside each region (a turn of '
     '25-90 degrees over 0.006 L: a facet\'s bend) against the design turnarounds\''),
    ('art_fragments_*', '1b2a283', 'new (tool/artifacts): the area in small pieces and slivers between drawn lines per L of '
     'outline against the design turnarounds\''),
    ('art_speckle_*', '1b2a283', 'new (tool/artifacts): specks per L^2 of face and neck skin against the design\'s'),
    ('art_peeks_*', '0db2e9b', 'new (tool/artifacts): small visible bits of a region\'s own pieces, a count (ours only)'),
    ('art_outline_collar', 'b9bc3bd', 'ours from a body frame starting 0.2 L under the eyes (0.5 cut the pieces at the '
     'neck: a straight edge in the collar); the design unchanged (tool/artifacts)'),
    ('art_fragments_collar', 'b9bc3bd', 'ours from a body frame starting 0.2 L under the eyes (0.5 cut the collar)'),
    ('art_terminator_collar', 'b9bc3bd', 'ours from a body frame starting 0.2 L under the eyes (0.5 cut the collar)'),
    ('art_*_top', 'b9bc3bd', 'ours from a body frame starting 0.2 L under the eyes (0.5 cut the top at the neck)'),
    ('art_*_bow', 'b9bc3bd', 'ours from a body frame starting 0.2 L under the eyes'),
    ('art_*_boots', 'b9bc3bd', 'ours counts the template boots (boot_L, boot_R): since round 5 only the cuffs were read'),
    ('art_spikes_*', 'b9bc3bd', 'new (tool/artifacts): the silhouette\'s tallest spike (what an opening by a 0.03 L disk '
     'cuts off, 0.012 L or more out) per region, beyond the design\'s (Michael\'s jagged boot protrusion)'),
    ('art_points_*', 'b9bc3bd', 'new (tool/artifacts): the silhouette\'s sharpest outward turn over 0.02 L per region, '
     'beyond the design\'s (the hull sleeves\' pointed caps)'),
    ('art_bumps_*', 'b9bc3bd', 'new (tool/artifacts): the sharpest outward turn over 0.06 L where the silhouette is one '
     'region\'s own, beyond the design\'s (the knob behind the thigh in profile, a jagged boot)'),
    ('art_mirror_waist', 'b9bc3bd', 'new (tool/artifacts): the jacket, band, skirt and flaps\' asymmetry about the '
     'figure\'s axis against the design\'s (the skirt jutting past the band on one side)'),
    ('art_mirror_self_boots', 'b9bc3bd', 'new (tool/artifacts): the boots\' asymmetry about their own axis against the '
     'design\'s (a pair unlike each other)'),
    ('art_band_lower', 'b9bc3bd', 'new (tool/artifacts): the skirt and flaps\' dark hem band\'s edge, kinks per L on the '
     'picture drawn with its textures, against the design\'s (pixel stairs against a few clean steps)'),
    ('art_*_neck', 'f771ec1', 'a view showing under 0.01 L^2 of neck skin is left out (the back view\'s slivers between '
     'the hair and the collar read 740 specks per L^2)'),
    ('art_*_face', 'f771ec1', 'a view showing under 0.01 L^2 of face skin is left out'),
    # tool/toonrender2: the default drawing (the body frame's checks; the head frame's hair, face and neck read artifactqa.buffers(), unchanged)
    ('art_*_collar', '32e9b1e', "the QA draws with charkit.render (qa3d.DRAW 'render', tool/toonrender2): the boards' shader and passes on the build's export, not qa3d's numpy rasteriser; every QA frame nearer EEVEE's (docs/workstreams/toonrender.md); the body frame draws through qa3d.draw: its silhouettes 0-1 px off EEVEE's per view (numpy 9-19), colour 0.17-0.24 levels (numpy 0.68-0.72, the back view 7.9: numpy draws the top's back wrong)"),
    ('art_*_bow', '32e9b1e', "the QA draws with charkit.render (qa3d.DRAW 'render', tool/toonrender2): the boards' shader and passes on the build's export, not qa3d's numpy rasteriser; every QA frame nearer EEVEE's (docs/workstreams/toonrender.md); the body frame draws through qa3d.draw: its silhouettes 0-1 px off EEVEE's per view (numpy 9-19), colour 0.17-0.24 levels (numpy 0.68-0.72, the back view 7.9: numpy draws the top's back wrong)"),
    ('art_*_top', '32e9b1e', "the QA draws with charkit.render (qa3d.DRAW 'render', tool/toonrender2): the boards' shader and passes on the build's export, not qa3d's numpy rasteriser; every QA frame nearer EEVEE's (docs/workstreams/toonrender.md); the body frame draws through qa3d.draw: its silhouettes 0-1 px off EEVEE's per view (numpy 9-19), colour 0.17-0.24 levels (numpy 0.68-0.72, the back view 7.9: numpy draws the top's back wrong)"),
    ('art_*_skirt', '32e9b1e', "the QA draws with charkit.render (qa3d.DRAW 'render', tool/toonrender2): the boards' shader and passes on the build's export, not qa3d's numpy rasteriser; every QA frame nearer EEVEE's (docs/workstreams/toonrender.md); the body frame draws through qa3d.draw: its silhouettes 0-1 px off EEVEE's per view (numpy 9-19), colour 0.17-0.24 levels (numpy 0.68-0.72, the back view 7.9: numpy draws the top's back wrong)"),
    ('art_*_boots', '32e9b1e', "the QA draws with charkit.render (qa3d.DRAW 'render', tool/toonrender2): the boards' shader and passes on the build's export, not qa3d's numpy rasteriser; every QA frame nearer EEVEE's (docs/workstreams/toonrender.md); the body frame draws through qa3d.draw: its silhouettes 0-1 px off EEVEE's per view (numpy 9-19), colour 0.17-0.24 levels (numpy 0.68-0.72, the back view 7.9: numpy draws the top's back wrong)"),
    ('art_*_sleeves', '32e9b1e', "the QA draws with charkit.render (qa3d.DRAW 'render', tool/toonrender2): the boards' shader and passes on the build's export, not qa3d's numpy rasteriser; every QA frame nearer EEVEE's (docs/workstreams/toonrender.md); the body frame draws through qa3d.draw: its silhouettes 0-1 px off EEVEE's per view (numpy 9-19), colour 0.17-0.24 levels (numpy 0.68-0.72, the back view 7.9: numpy draws the top's back wrong)"),
    ('art_*_flaps', '32e9b1e', "the QA draws with charkit.render (qa3d.DRAW 'render', tool/toonrender2): the boards' shader and passes on the build's export, not qa3d's numpy rasteriser; every QA frame nearer EEVEE's (docs/workstreams/toonrender.md); the body frame draws through qa3d.draw: its silhouettes 0-1 px off EEVEE's per view (numpy 9-19), colour 0.17-0.24 levels (numpy 0.68-0.72, the back view 7.9: numpy draws the top's back wrong)"),
    ('art_*_legs', '32e9b1e', "the QA draws with charkit.render (qa3d.DRAW 'render', tool/toonrender2): the boards' shader and passes on the build's export, not qa3d's numpy rasteriser; every QA frame nearer EEVEE's (docs/workstreams/toonrender.md); the body frame draws through qa3d.draw: its silhouettes 0-1 px off EEVEE's per view (numpy 9-19), colour 0.17-0.24 levels (numpy 0.68-0.72, the back view 7.9: numpy draws the top's back wrong)"),
    ('art_mirror_waist', '32e9b1e', "the QA draws with charkit.render (qa3d.DRAW 'render', tool/toonrender2): the boards' shader and passes on the build's export, not qa3d's numpy rasteriser; every QA frame nearer EEVEE's (docs/workstreams/toonrender.md); the body frame draws through qa3d.draw: its silhouettes 0-1 px off EEVEE's per view (numpy 9-19), colour 0.17-0.24 levels (numpy 0.68-0.72, the back view 7.9: numpy draws the top's back wrong)"),
    ('art_band_lower', '32e9b1e', "the QA draws with charkit.render (qa3d.DRAW 'render', tool/toonrender2): the boards' shader and passes on the build's export, not qa3d's numpy rasteriser; every QA frame nearer EEVEE's (docs/workstreams/toonrender.md); the body frame draws through qa3d.draw: its silhouettes 0-1 px off EEVEE's per view (numpy 9-19), colour 0.17-0.24 levels (numpy 0.68-0.72, the back view 7.9: numpy draws the top's back wrong)"),
    # tool/calib round 2 (2026-09-30): the grading recalibrated (charkit/calib/records/art_mirror_self_boots.json)
    ('art_mirror_self_boots', '9d5f649', "grading: limits x1.5 / x2.5 -> x1.37 / x1.58 (the design's boots with one "
     "boot's masks moved 1-2 px read 1.005-1.163; body4b_render's uneven boots 1.787: WARN -> FAIL)"),
    # tool/garments4 Part 2: creases as a line layer
    ('art_*_bow', 'a17ec74c', "the bow's crease strokes read as lines by the QA's render drawing (qarender mapped the "
     "export's ink primitives to the cloth)"),
    ('art_*_skirt', 'a17ec74c', "the skirt panel's crease strokes read as lines by the QA's render drawing"),
    # merge/batch4: a region drawn in one tone keeps its terminator check (the artifacts part's denominator)
    ('art_terminator_neck', '99232882', "kept when ours is one tone (its terminator under MIN_TERM, 0.05 L, in every "
     "view) where the design has a terminator: INFO with no value and why, where the check was dropped with no reason "
     "(the part then measured 57 of its 58; the joined shoulder lit the neck under the chin). Any region read in one "
     "tone is kept so; on Clawd only the neck reads so"),
]
