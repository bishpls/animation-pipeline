"""The measurement steps of the checks charkit/necklineqa.py declares (measured by charkit/declared.py's class_iou
family; charkit.registry; docs/CHARKIT.md). A step: (check pattern, the commit that changed the measurement, what
changed). Keep a pattern's steps in the order they happened."""

MEASUREMENT_STEPS = [
    # tool/garments8 (Michael, 2026-10-01: the collar and lapels without the bow were never defined): the V's shape truth
    ('neck_v_*_skin', '2201e679', "against the V's shape truth (the manifest's shape_truth neck_v: bodice_layers' skin in "
     "the V, the outfit without the bow, registered by charkit.layerref --kind bodice), ours drawn without the bow "
     "(declared's `truth`: the bow's objects left out of the z-buffer), the windows down to z -0.90 (the V's point, "
     "-0.88 in front); was the turnaround's skin above the knot (z -0.45..-0.75), where the bow hid the V's lower half "
     "on both sides"),
]
