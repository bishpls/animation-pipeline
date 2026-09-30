"""The measurement steps of the checks charkit/qa3d.py measures (charkit.registry; docs/CHARKIT.md). A step: (check
pattern, the commit that changed the measurement, what changed). Keep a pattern's steps in the order they happened."""

MEASUREMENT_STEPS = [
    # tool/body round 6: the merged hull-det and garment-sampling, the hidden back hem and flaps, Michael's review of round 5
    ('piece_*_hang', '854776f', "the reach against the drawn piece's lowest point (the outfit graph's extents), not the "
     "drawn chain's last joint (a skeleton ends short of the tip by the half-width: 0.13 L on the flaps)"),
    # tool/body round 5 (charkit/detailqa.py): Michael's review of round 4's midriff and boots
    ('piece_*_extent', 'd35fbaf', "new: a spring piece's lowest row, outer edge and area per view against the drawing's"),
    ('piece_*_hang', 'd35fbaf', "new: a chained piece's top and lowest point against its drawn chain's root and tip"),
    ('garment_coverage', 'd35fbaf', 'new (INFO): garments lofted from marginal hull coverage'),
    ('piece_skirt', 'd35fbaf', "same-colour layers: pixels where a piece lies over another of its colour count for neither (the overskirt panels over the skirt); the flaps' geometry changed at the same time"),
    ('piece_overskirt_panel_*', 'd35fbaf', "same-colour layers (as piece_skirt); the flaps' geometry changed at the same time"),
    ('piece_cuff_*', 'e34aeff', 'same-colour layers: the wrist cuffs lie over the skirt (the notes; both orange), so where they overlap the pixels count for neither; the skirt was cleared of the arms at the same time'),
    ('piece_skirt', 'e34aeff', 'same-colour layers: the wrist cuffs over it too; the skirt was cleared of the arms at the same time'),
    ('hair_noise', 'c500f21', 'QA renders undithered (charkit/geom merge): hair_noise reads ~0.31 on the default hair and '
                              '~0.19 on geom hair, where dither noise split the toon tones before'),
    ('face_folds', '8017ff3', 'the expression library grew (tool/sheet: shock eyes; laugh, yawn and wavy mouths), and '
                              'face_folds sums its folds over every key: Clawd 1014 -> 1257 with the same skin'),
    ('face_expr_range', '8017ff3', 'FACE_EXPECT gained the shock eye (tool/sheet)'),
    ('face_shape_coverage_*', '5652f64', 'framing against the generated shape is INFO: the sheet grades framing '
                                         '(sheet_shown_*), per the manifest'),
    # tool/measure: the QA measures the build's geometry bundle in the venv (charkit/bundle.py, charkit/qa3d.py)
    ('sheet_*', '5394358', 'the QA runs in the venv on the geometry bundle (tool/measure): the sheet\'s class z-buffer '
                          'rasterises at pixel centres (numba) where the point splats read about half a pixel wider; '
                          'lines stay a pixel wide. neck_to_jaw reads one row, which a pixel moves off the neck'),
    ('body_*', '5394358', 'the body classes z-buffered at pixel centres (tool/measure): heights move by a sheet pixel '
                         '(0.0087 L), IoUs by about 0.01'),
    ('expr_*', '5394358', 'the expression heads z-buffered at pixel centres (tool/measure): a match distance moves with '
                         'a pixel of the small iris (fluster 0.12 -> 0.39)'),
    ('face_shape_*', '5394358', 'the face-shape z-buffers at pixel centres (tool/measure): widths about 0.02, the chin '
                               'by two pixels (0.012 L)'),
    ('eye_*', '5394358', 'the eye renders drawn from the bundle, not EEVEE (tool/measure): within a pixel'),
    ('shape_iou*', '5394358', 'the silhouettes drawn from the bundle, anti-aliased like EEVEE (tool/measure): within 0.001'),
    ('ref_iou', '5394358', 'the front silhouette drawn from the bundle (tool/measure)'),
    ('hair_noise', '5394358', 'the hair drawn with its toon materials from the bundle, not EEVEE (tool/measure): within '
                             '2.5%'),
    ('scalp_px', '5394358', 'the scalp drawn from the bundle, not EEVEE (tool/measure)'),
    # tool/refs: the generated references are the design (Michael, 2026-09-28: idol_D is the source design, not a
    # benchmark); each check graded only against its measure's authority (checks.authorize)
    ('sheet_*', '9307073', 'the face measured against head_turnaround (generated, 200 px/L, scaled by its own eyes), not '
                          'idol_D at 115 px/L'),
    ('eye_*', '9307073', 'the eyes measured against head_turnaround\'s front eyes at its own resolution, not the rig\'s '
                        'eye layers'),
    ('body_*', '9307073', 'the body measured against body_turnaround (generated, one A-pose, 212 px/L, scaled by its own '
                         'eyes), not idol_D'),
    ('palette_*', '9307073', 'the palette read from body_turnaround, not idol_D'),
    ('figures_*', '9307073', 'the figures found on body_turnaround; no hand-typed head boxes to verify'),
    ('expr_*', '9307073', 'no expression reference: the expressions are the template library\'s (the body sheet has no '
                         'expression heads)'),
    ('shape_iou*', '9307073', 'INFO unless the measure\'s authority (checks.authorize): the body silhouette\'s is the body '
                             'turnaround, the hair shape\'s TRELLIS'),
    ('ref_iou', '9307073', 'INFO: the 3D-style key is no measure\'s authority (checks.authorize)'),
    ('face_shape_*', '9307073', 'INFO but the depth: TRELLIS is only the face depth\'s authority (checks.authorize)'),
    # tool/review: the generated 3D character grades nothing (Michael, 2026-09-28)
    ('face_shape_depth', 'b8307af', 'the face\'s depth against the generated character is INFO: face_depth has no '
                                 'authority (the hull is the hair\'s source, not a face target)'),
    ('shape_iou_hair', 'b8307af', 'the hair against the generated character is INFO: hair_shape has no authority (our '
                               'hair is cut from it; the sheet grades the hair)'),
    # tool/chin: our chin read with the design's rule
    ('sheet_*', '5843d44', 'our chin read with the design\'s rule (faceqa.drawn_chin: the turn under the chin), not '
                          'chin_bottom (0.06 L behind the lips); the chin, the widths\' rows, the neck\'s row and the '
                          'contours\' extent move with it on a receding chin'),
    ('hair_noise', '51a87aa', 'the hair drawn without its outlines (a drawn line between two locks is not shading) and behind '
     'the rest of the character (the hair\'s inside through the face is hidden, as in a render) (tool/hair-pieces): '
     'the geom hair reads 0.047, was 0.104'),
    # tool/look: the QA draws what the boards light
    ('hair_noise', '37ff417', 'the hair drawn under each view\'s board light (the style\'s look: the anime key turns with '
     'the camera), not its material\'s one fixed light: the back view is lit as the front is (tool/look)'),
    # tool/hair-detail: the buns' tones cut apart from the mass's
    ('hair_noise', 'cc79d07', 'each tone group cut at its own percentiles, the buns apart from the mass (qa3d.tone_edges; '
     'tool/hair-detail): a block bun\'s flat faces had moved the shared cuts. The clawd_body pieces build reads 0.068, '
     'was 0.088; the default spec 0.055, was 0.048'),
    # tool/face: the QA's eyes on the head's eye line; the taper's shape
    ('sheet_*', 'e9a6753', 'ours registered on the eyes at the head\'s eye line (qa3d.eye_anchor: the design\'s eye row, '
                          'which the head is built on), not the iris plates\' vertex mean 0.0235 L over it: every height '
                          'under the eyes had read that much low (jaw_4: cheek_chin -0.0277 -> -0.0027, profile_chin '
                          '-0.0247 -> 0.0003, profile 0.0136 -> 0.0053)'),
    # tool/toonrender2: the default drawing
    ('hair_noise', '32e9b1e', "the QA draws with charkit.render (qa3d.DRAW 'render', tool/toonrender2): the boards' shader and passes on the build's export, not qa3d's numpy rasteriser; every QA frame nearer EEVEE's (docs/workstreams/toonrender.md); hair pictures 0.15 levels from EEVEE's on the hair, numpy 0.25 (0.70 with streaks); tr3_a 0.0739 -> 0.0744, noise 0.0007"),
    # tool/mouth (round 1, dee61e7) and tool/mouth2: the expressions measured against the source sheet again, the library
    # grew (docs/workstreams/mouth.md)
    ('expr_*', 'dee61e7', "measured against the source sheet's heads again (qa3d.Design.expression_sheet: idol_D when the "
     "body sheet draws none; INFO by authority): since tool/refs the part was one `expr` SKIPPED"),
    ('face_folds', 'dee61e7', 'the expression library grew (tool/mouth: shout, clench, grimace, smirk, firm, wobble '
     'mouths) and face_folds sums its folds over every key'),
    ('face_mouth_cover', 'dee61e7', 'the library grew (the open shout, clench, grimace and wobble; cover is the worst '
     'key) and COVER counts the tongue, a new class (tool/mouth)'),
    ('face_mouth_asym', 'dee61e7', 'the library grew (tool/mouth: the smirk is asymmetric by design; the worst key)'),
    ('face_folds', 'bf797d4', 'the library grew (tool/mouth2: lids focus, squeeze, wince, shy) and face_folds sums every key'),
    ('face_expr_range', 'bf797d4', 'FACE_EXPECT gained focus, squeeze, wince, shy (tool/mouth2)'),
    ('face_eye_asym', 'bf797d4', 'the library grew (tool/mouth2: lids focus, squeeze, wince, shy; the worst key)'),
    ('face_preset_*', 'bf797d4', 'new: the combined expressions (charkit.expressions.PRESETS) against exprqa.TARGETS, '
     'the furthest feature past its target in WARN margins (tool/mouth2)'),
]
