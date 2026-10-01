"""Creases, folds and pleats measured (tool/garments4; Michael's garment list, 2026-09-30, item 1: "the skirt's cream
section is missing its creases: the biggest overlooked point"; "the bow lacks fine crease texture"). The outline
renderer's inverted hulls draw silhouettes only, so what the design draws inside a piece (a pleat's fold, a wrinkle)
needs geometry or a line layer (charkit.garments.ink_strokes); these checks measure the drawn lines inside each piece
against ours, as declared checks (charkit.declared's ink_inside family: the design's ink and fainter strokes inside the
drawn region, skeletonized, against our outline and ink pixels there; the share of the drawn length ours lacks).

Checks (part 'declared'; values 0 .. 1, lower better):
  skirt_panel_{front,three_quarter}_creases   the skirt's cream front panel's pleat folds
  bow_{front,three_quarter}_creases           the bow's creases and wrinkles inside its lobes and knot
"""

DECLARED_CHECKS = [
    dict(check='skirt_panel_{view}_creases', family='ink_inside', piece='skirt', views=['front', 'three_quarter'],
         params=dict(region='skirt_panel', band=0.02, round=3), limits=[0.35, 0.6], flag="the skirt's cream section is missing its creases (Michael, 2026-09-30: the biggest overlooked point)",
         note="the skirt's cream panel's drawn creases (ink and fainter strokes, skeletonized) our lines lack: "
              "max(0, 1 - ours / design) of their length",
         calibrate=dict(known_bad='g4_before', baseline=['voronoi_pieces'], shape=['piece_skirt'], kind='defect')),
    dict(check='bow_{view}_creases', family='ink_inside', piece='bow', views=['front', 'three_quarter'],
         params=dict(band=0.015, round=3), limits=[0.35, 0.6], flag="the bow lacks fine crease texture (Michael, 2026-09-30)",
         note="the bow's drawn creases and wrinkles inside its lobes and knot (ink and fainter strokes, skeletonized) our "
              "lines lack: max(0, 1 - ours / design) of their length",
         calibrate=dict(known_bad='g4_before', baseline=['voronoi_pieces'], shape=['piece_bow'], kind='defect')),
]
