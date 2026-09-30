"""The measurement steps of the checks charkit/pieceqa.py measures (charkit.registry; docs/CHARKIT.md). A step: (check
pattern, the commit that changed the measurement, what changed). Keep a pattern's steps in the order they happened."""

MEASUREMENT_STEPS = [
    # tool/garments2 (charkit/pieceqa.py): Michael's notes on the pieces (the shoulder poofs' spikes, the waistband and
    # shorts, the pleats, the collar and bow, the cuffs)
    ('sleeve_*', '12c3b97', "new: the puff sleeves' spikes, outline roughness and width along the arm per view "
     "against the design's, and their stand-off from the arm against sleeve_closeup's cross-section"),
    ('waistband_*', '12c3b97', "new: the waistband's top and bottom edges and width per view, and the top's overhang "
     "over it in profile, against the design's"),
    ('shorts_*', '12c3b97', "new: the shorts' hem height per view and width in front and back against the design's"),
    ('cuff_*', 'cda2b7f', "new: the wrist cuffs' flare (top over bottom width) and cream trim in front and back "
     "against the design's"),
    ('top_*', '1b8b30b', "new: the jacket over the band (which hides which at their junction, the jacket and the band "
     "each drawn alone), its open front's width and the junction's drop to the bib, against the design's"),
    ('collar_*', '1b8b30b', "new: the collar's torn edges (roughness, fragments; ours drawn 3x finer)"),
    ('bow_*', '1b8b30b', "new: the bow's torn edges, its lobes' flare and its tails' width and parting"),
    ('sleeve_*', 'cda2b7f', "the spikes on the cap's silhouette only (the drawn masks' inner corners are cutting "
     "slivers), the check set by the design alone, the stand-off against sleeve_closeup"),
    ('waistband_*_rows', 'b3aaf2c', "the design's band inside its ink (the masks gave it the jacket's lower part where "
     "the jacket hangs over it): the back's top -1.314 -> -1.390, the three-quarter's bottom -1.413 -> -1.493"),
    ('waistband_*_width', 'b3aaf2c', "the design's band inside its ink (the jacket's hanging corners left out)"),
    ('top_front_hem_step', 'b3aaf2c', "the design's band inside its ink: the bib's hem is 0.037 L higher than the "
     "jacket's fronts (the masks had read the fronts' corners as band, +0.033)"),
    ('waistband_profile_overhang', 'b3aaf2c', "ours takes the bib (its own object now) with the top"),
    ('top_*_over_band', 'a7a6845', "the jacket alone below the junction is tucked only within 0.08 L behind the band "
     "(a jacket over the band all round showed its back panel there)"),
    ('waistband_profile_overhang', 'a7a6845', "the figures' front edges at fixed rows (the jacket's -1.33..-1.26, the "
     "band's -1.47..-1.40): the masks' profile band is the jacket's lower part"),
]
