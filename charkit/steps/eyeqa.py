"""The measurement steps of the checks charkit/eyeqa.py measures (charkit.registry; docs/CHARKIT.md). A step: (check
pattern, the commit that changed the measurement, what changed). Keep a pattern's steps in the order they happened."""

MEASUREMENT_STEPS = [
    # tool/face: the QA's eyes on the head's eye line; the taper's shape
    ('eye_pupil_*', 'b9055f7', 'the pupil read from its coverage map (sub-pixel; a value threshold had cut its soft ends) '
                               'and against the whole iris\'s height (its lid-shadowed top had fallen out of the iris): '
                               'the pre-round-2 build reads pupil_run 0.297 against the design\'s 0.405 (it had read 0.341 '
                               'against 0.394)'),
]
