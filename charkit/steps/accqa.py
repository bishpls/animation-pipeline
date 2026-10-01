"""The measurement steps of the checks charkit/accqa.py measures (charkit.registry; docs/CHARKIT.md). A step: (check
pattern, the commit that changed the measurement, what changed). Keep a pattern's steps in the order they happened."""

MEASUREMENT_STEPS = [
    # tool/acc-reclass: the hair clips against the design's, per clip and view (docs/workstreams/accessories.md)
    ('acc_*', '9bfbc8b', "new: each hair clip's shape (IoU aligned on centroid and area), size, position and axis per "
     "view against the head turnaround's drawn clip, whether it shows where the design does, its seat on the hair (the "
     "least of its vertices' heights over the hair under them), its triangulated 3D place and its colour; limits "
     "calibrated on the design against itself (the body turnaround's clips pass), the placeholders fail 26 of 30 graded"),
    # tool/accessories5: ours measured as the drawing shows each clip (accqa.as_drawn): the drawing layers the clips over
    # each other (the crab's body over the star's left arm, the star over the crab's right claw), so ours, aligned on the
    # drawn clip, has the other drawn clips' cover taken out before its shape, size, place and axis are read; a clip
    # nothing covers in the drawing measures as before. On pipeline-3d 00494de: crab profile iou 0.487 -> 0.499, size
    # 0.883 -> 0.806, three-quarter iou 0.732 -> 0.746; star three-quarter iou 0.751 -> 0.763
    ('acc_*_iou', 'b45f61e2', "ours as the drawing shows the clip (the other drawn clips' cover taken out of ours, "
     "aligned on the drawn clip), then the shape IoU as before"),
    ('acc_*_size', 'b45f61e2', "ours as the drawing shows the clip (accqa.as_drawn), then sqrt(area) as before"),
    ('acc_*_pos', 'b45f61e2', "ours as the drawing shows the clip (accqa.as_drawn), then the centroid as before"),
    ('acc_*_angle', 'b45f61e2', "ours as the drawing shows the clip (accqa.as_drawn), then the principal axis as before"),
    # (the views both sides draw: the back's acc_KIND_back_shown, where the design hides the clips, is measured as
    # before, as_drawn only applying where both draw the clip)
    ('acc_*_front_shown', 'b45f61e2', "ours as the drawing shows the clip (accqa.as_drawn), then its pixels over the "
     "design's"),
    ('acc_*_three_quarter_shown', 'b45f61e2', "ours as the drawing shows the clip (accqa.as_drawn), then its pixels over "
     "the design's"),
    ('acc_*_profile_shown', 'b45f61e2', "ours as the drawing shows the clip (accqa.as_drawn), then its pixels over the "
     "design's"),
    ('acc_*_shape', 'b45f61e2', "new (INFO): the clip's as-drawn shape IoU per view in one check (the guard's measure)"),
    ('acc_*_alone', 'b45f61e2', "new (INFO): our clip face-on against the clips-alone drawing (shape IoU: the structure)"),
    ('acc_*_pos3d', 'b45f61e2', "triangulated from the views' centroids of ours as the drawing shows the clip"),
    ('acc_*_visible', 'b45f61e2', "new (declared, family 'visible'): the share of our clip's own silhouette (drawn "
     "alone) that shows with everything else drawn, in the views the design draws it (Michael's non-occlusion rule)"),
    ('acc_star_arms', 'b45f61e2', "new: the star face-on, its longer side arm over its height against head_turnaround's "
     "unoccluded reading (accqa.STAR_ARMS)"),
    ('acc_star_minor', 'b45f61e2', "new: the star face-on, its four minor points over its height against "
     "head_turnaround's (accqa.STAR_ARMS)"),
    # tool/accessories6: the crab's parts face-on against the clips-alone sheet (Michael 2026-10-01: the legs too short
    # and under the body, the pincers solid circles), and the clips face-on in their own frame (the spec's facing and
    # tilt: accqa.own_axes) instead of their vertices' principal axes (a crab turned -18 deg was read turned). On
    # pipeline-3d 25ff0f25: acc_crab_alone 0.585 -> 0.694; acc_star_alone 0.716 -> 0.713
    ('acc_*_alone', '6bcf6e39', "the clip face-on in its own frame (its spec's facing and tilt) instead of its vertices' "
     "principal axes, then the shape IoU against the clips-alone drawing as before"),
    ('acc_*_side', '6bcf6e39', "new (INFO): the clip edge-on in its own frame against the clips-alone sheet's side "
     "drawing (its hair-clip loop drawn behind it cut: accqa.edge_body), shape IoU"),
    ('acc_crab_legs', '6bcf6e39', "new (declared, family 'limbs', view face): the crab face-on, its legs per side "
     "against the clips-alone sheet's (charkit.limbs)"),
    ('acc_crab_leg_reach', '6bcf6e39', "new (declared, limbs): the legs' reach off the body over its width against the "
     "sheet's"),
    ('acc_crab_leg_roots', '6bcf6e39', "new (declared, limbs): where the legs leave the body (elliptical angle) against "
     "the sheet's"),
    ('acc_crab_claw_fingers', '6bcf6e39', "new (declared, limbs): each claw's fingers (1 + its notches) against the "
     "sheet's"),
    ('acc_crab_claw_notch', '6bcf6e39', "new (declared, limbs): the claws' deepest notch over their size against the "
     "sheet's"),
    ('acc_crab_stalks', '6bcf6e39', "new (declared, limbs): the eye stalks' reach above the body against the sheet's"),
]
