"""The measurement steps of the checks charkit/truthqa.py declares (measured by charkit/declared.py's shape_iou family
with `truth`; charkit.registry; docs/CHARKIT.md). A step: (check pattern, the commit that changed the measurement, what
changed). Keep a pattern's steps in the order they happened."""

MEASUREMENT_STEPS = [
    # tool/garments8 (Michael, 2026-10-01): the covered pieces against their shape truths
    ('collar_*_truth', '2201e679', "new: the sailor collar and its lapels drawn without the bow against bodice_layers' "
     "collar (the manifest's shape_truth collar), bodymeasure.iou_tol at OUTLINE_TOL"),
    ('top_*_truth', '2201e679', "new: the jacket drawn without the collar and the bow against top_layers' jacket (the "
     "manifest's shape_truth top), bodymeasure.iou_tol at OUTLINE_TOL"),
]
