"""The measurement steps of the checks charkit/truthqa.py declares (measured by charkit/declared.py's shape_iou family
with `truth`; charkit.registry; docs/CHARKIT.md). A step: (check pattern, the commit that changed the measurement, what
changed). Keep a pattern's steps in the order they happened."""

MEASUREMENT_STEPS = [
    # tool/garments8 (Michael, 2026-10-01): the covered pieces against their shape truths
    ('collar_*_truth', '2201e679', "new: the sailor collar and its lapels drawn without the bow against bodice_layers' "
     "collar (the manifest's shape_truth collar), bodymeasure.iou_tol at OUTLINE_TOL"),
    ('top_*_truth', '2201e679', "new: the jacket drawn without the collar and the bow against top_layers' jacket (the "
     "manifest's shape_truth top), bodymeasure.iou_tol at OUTLINE_TOL"),
    ('collar_*_truth', 'a1480b81', "grading from the calibration triple: limits [0.75, 0.5] -> [0.85, 0.70], front "
     "and three-quarter only (the design moved 1-2 px 0.927-0.964, the flagged lapels g8_lapels0 0.617 / 0.514 WARN "
     "-> FAIL; the back dropped: the bow hides nothing there, g8_lapels0 0.87 and the affine floor 0.81 PASS)"),
    ('top_*_truth', 'a1480b81', "a guard (no flagged build of the jacket under the collar: g8_lapels0 reads 0.80 / 0.74 "
     "/ 0.83 / 0.91 against the design's 0.94-1.0, the floors 0-0.47)"),
]
