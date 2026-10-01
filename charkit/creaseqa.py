"""Creases, folds and pleats measured (tool/garments4; Michael's garment list, 2026-09-30, item 1: "the skirt's cream
section is missing its creases: the biggest overlooked point"; "the bow lacks fine crease texture"). The outline
renderer's inverted hulls draw silhouettes only, so what the design draws inside a piece (a pleat's fold, a wrinkle)
needs geometry or a line layer (charkit.garments.ink_strokes); these checks measure the drawn lines inside each piece
against ours, as declared checks (charkit.declared's ink_inside family: the design's ink and fainter strokes inside the
drawn region, skeletonized, against our outline and ink pixels there; the share of the drawn length ours lacks).
The panel's lines are read where they lie within the panel (`relative`: ours moved row by row from our cream panel's
span onto the drawn one's): the three-quarter view draws the panel face-on, as wide as the front's (a 3D panel turned
35.5 degrees shows 0.81 of it; garments4's two-view triangulation: its near edge implies a depth 0.33 L behind ours, its
far edge agrees with ours), so its absolute place there is a view-dependent drawing; the panel's shape checks keep the
absolute fit and report each view's cost.

Checks (part 'declared'; values 0 .. 1, lower better, but the shape's):
  skirt_panel_{front,three_quarter}_creases   the skirt's cream front panel's pleat folds
  skirt_panel_{front,three_quarter}_edges     the folds that bound the panel (the orange laid over it: the inverted box
                                              pleat's outer folds, drawn as lines along its outline)
  skirt_panel_{front,three_quarter}_shape     the cream panel's shape: our skirt's cream pixels against the drawn
                                              panel (closed IoU, higher better): the drawn panel is a triangle from
                                              the waist, ours was a band as wide at the waist as at the hem. (The
                                              profile draws the pleat's side faces as a cream wedge our panel doesn't
                                              model: 0.232 before, 0.17 after the taper; garments4's notes, next step)
  bow_{front,three_quarter}_creases           the bow's creases and wrinkles inside its lobes and knot
"""

DECLARED_CHECKS = [
    dict(check='skirt_panel_{view}_creases', family='ink_inside', piece='skirt', views=['front', 'three_quarter'],
         params=dict(region='skirt_panel', band=0.02, relative='cream', round=3), limits=[0.35, 0.6], flag="the skirt's cream section is missing its creases (Michael, 2026-09-30: the biggest overlooked point)",
         note="the skirt's cream panel's drawn creases (ink and fainter strokes, skeletonized) our lines lack: "
              "max(0, 1 - ours / design) of their length",
         calibrate=dict(known_bad='g4_before', baseline=['voronoi_pieces'], shape=['piece_skirt'], kind='defect')),
    dict(check='skirt_panel_{view}_edges', family='ink_inside', piece='skirt', views=['front', 'three_quarter'],
         params=dict(region='skirt_panel', band=0.02, edge=True, relative='cream', round=3), limits=[0.35, 0.6],
         flag="the skirt's cream section is missing its creases (Michael, 2026-09-30: the biggest overlooked point)",
         note="the drawn folds bounding the skirt's cream panel (lines along its outline, 0.02 L either side) our lines "
              "lack: 1 - recall of their skeleton within 0.015 L",
         calibrate=dict(known_bad='g4_before', baseline=['voronoi_pieces'], shape=['piece_skirt'], kind='defect')),
    dict(check='skirt_panel_{view}_shape', family='shape_iou', piece='skirt', views=['front', 'three_quarter'],
         params=dict(drawn='skirt_panel', ours_cls='cream', close=True), limits=[0.8, 0.65],
         note="the skirt's cream panel: our skirt's cream pixels against the drawn panel, both closed (IoU)",
         calibrate=dict(known_bad=None, no_known_bad="the panel's shape guard (as the piece_* shape IoUs are: "
                        "agreement with the drawing, no single flagged defect; g4_before's band-shaped panel reads 0.69 "
                        "WARN): the design moved 1-2 px must pass and a random stand-in must fail",
                        baseline=['voronoi_pieces'], shape=['piece_skirt'])),
    dict(check='bow_{view}_creases', family='ink_inside', piece='bow', views=['front', 'three_quarter'],
         params=dict(band=0.015, round=3), limits=[0.35, 0.6], flag="the bow lacks fine crease texture (Michael, 2026-09-30)",
         note="the bow's drawn creases and wrinkles inside its lobes and knot (ink and fainter strokes, skeletonized) our "
              "lines lack: max(0, 1 - ours / design) of their length",
         calibrate=dict(known_bad='g4_before', baseline=['voronoi_pieces'], shape=['piece_bow'], kind='defect')),
]
