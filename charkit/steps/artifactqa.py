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
]
