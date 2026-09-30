"""The measurement steps of the checks charkit/bodyqa.py measures (charkit.registry; docs/CHARKIT.md). A step: (check
pattern, the commit that changed the measurement, what changed). Keep a pattern's steps in the order they happened."""

MEASUREMENT_STEPS = [
    # tool/body round 6: the merged hull-det and garment-sampling, the hidden back hem and flaps, Michael's review of round 5
    ('body_*_skirt_width', '26c6bbb', "no row free of hands in both figures: the design's free rows against ours on the "
     "same rows, the row whose ratio is the median (one row alone fell where clawd_mh's run breaks at the waist)"),
    ('body_*_skirt_width', '854776f', "no row free of hands in both figures: the design's widest free row against ours "
     "on that same row (each figure's own widest over the design's free rows had sat at different heights)"),
    # tool/body round 5 (charkit/detailqa.py): Michael's review of round 4's midriff and boots
    ('body_*_boot_step_*', '196eace', "rows whose outline ends on the cuff (orange) left out: the cuff's rounded "
     "lower edge over the narrower shaft had counted as a 0.02 L step (round 5's boots meet the cuff at its edge)"),
    ('body_*_leg_gap', 'd35fbaf', "new: rows over the lower legs and boots where the design's legs stand apart and ours join (a bridge)"),
    ('body_*_boot_step_*', 'd35fbaf', "new: each boot's outline's largest row-to-row jump beyond the design's (the shaft/foot seam)"),
    ('body_*_skirt_aline', 'd35fbaf', "new: the skirt's width near its hem over its widest row against the design's (a bubble)"),
    ('body_profile_chest', 'd35fbaf', "new: the chest's front edge in profile against the design's"),
    ('body_*_waist_skin', 'd35fbaf', "new: the waist's skin across the body beyond the design's (a bare band)"),
    ('body_*_skirt_width', '4053ecd', "the skirt's width measured on the design's rows free of hands when no row is free in both (the back view had fallen back to each figure's own widest free row)"),
    ('body_*_skirt_width', 'ecd4d79', "the skirt's width compared on the rows neither figure has a hand against (each figure's widest free row had sat at different heights)"),
]
