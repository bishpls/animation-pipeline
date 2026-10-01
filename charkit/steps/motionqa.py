"""The measurement steps of the checks charkit/sim/motionqa.py reports (motion_<pose>_<garment>_*; charkit.registry). A step:
(check pattern, the commit that changed the measurement, what changed)."""

MEASUREMENT_STEPS = [
    # tool/garments4 (2026-10-01): the cloth read without its ink strokes
    ('motion_*', '531c835f', 'the cloth grid read from the cloth\'s own faces (drape.grid_polys): a piece carrying ink strokes '
                       '(garments.with_ink, since the creases milestone) read SKIPPED "skirt: not a grid"; the cage '
                       'carries the strokes (Cage.attach)'),
    ('motion_*', '4eb2c02b', 'the stretch edges and the penetration surface leave the ink strokes out (their edges set the '
                       'stretch p99 at 0.36 / 0.93); no ink (g4_part1) reads as before: kick inside 0.00244, kick '
                       'stretch 0.06346, squat stretch 0.10404'),
]
