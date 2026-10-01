"""The neckline's V (tool/garments4, Michael's garment list 2026-09-30, item 4: "the neck-to-bow V: skin, not orange"):
the design draws bare skin between the sailor collar's lapels from the neck down to the bow's knot; ours had the
jacket's orange there (its open front started under the knot, z -0.72 L).

Declared checks (charkit.declared's `class_iou` family: a model-sheet class inside a window, IoU with the drawing's):
  neck_v_front_skin            the skin in the V, x -0.2..0.2 L, z -0.45..-0.75 L (the drawn V: half-width 0.15 at
                               z -0.50 narrowing to 0.06 at -0.70, under the bow's knot from -0.72)
  neck_v_three_quarter_skin    the same in three-quarter, its window x -0.1..0.35 L (the drawn V lies right of the
                               eyes' middle there: x 0.06..0.31 at z -0.50, -0.01..0.09 at -0.70)
The V below the knot is the bodice sheet's (charkit/refs/clawd/gen/bodice_layers.png, registered for what the bow
hides): its point at z -0.88, under the knot, which hides it.
"""

DECLARED_CHECKS = [                 # (a literal: read with ast)
    dict(check='neck_v_front_skin', family='class_iou', piece='top', views=['front'],
         params=dict(cls='skin', window=[-0.2, 0.2, -0.45, -0.75]), limits=[0.8, 0.6],
         flag="the V between the neck and the bow: the design shows skin, ours the jacket's orange (Michael, "
              "2026-09-30, item 4)",
         note="the skin in the V between the collar's lapels above the bow, front: our skin pixels' IoU with the "
              "drawing's in x -0.2..0.2, z -0.45..-0.75 L",
         calibrate=dict(known_bad='g4_v0', baseline=['voronoi_pieces'], shape=['piece_top', 'piece_collar'],
                        kind='defect')),
    dict(check='neck_v_three_quarter_skin', family='class_iou', piece='top', views=['three_quarter'],
         params=dict(cls='skin', window=[-0.1, 0.35, -0.45, -0.75]), limits=[0.8, 0.6],
         flag="the V between the neck and the bow: the design shows skin, ours the jacket's orange (Michael, "
              "2026-09-30, item 4)",
         note="the skin in the V between the collar's lapels above the bow, three-quarter: our skin pixels' IoU with "
              "the drawing's in x -0.1..0.35, z -0.45..-0.75 L",
         calibrate=dict(known_bad='g4_v0', baseline=['voronoi_pieces'], shape=['piece_top', 'piece_collar'],
                        kind='defect')),
]
