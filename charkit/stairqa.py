"""The staircase hem (tool/garments4, Michael 2026-10-01): the skirt's and the overskirt flaps' dark stepped band, drawn
with exact right angles (vertical risers, horizontal treads), each step one pleat: its risers on the pleats' folds and
its treads within a pleat's face. Ours was sheared: its risers mid-pleat, its treads across the folds ("our zigzag
runs across a crease, and it shouldn't: a fold bends a step that spans it").

Declared checks (charkit.declared's `stair` family, front and three-quarter, where the design draws the steps):
  stair_{view}_crossed   the zigzag's steps (treads with a riser at either end) a fold crosses, each a defect (ours:
                         our lines and our geometry's folds, declared.our_folds: the pleats' folds show in the render
                         as cel shading's edges; the design's: its ink), ours beyond the design's (a count); the flat
                         band beyond the stair crossing the side pleats is reported beside it, not counted
  stair_skirt_{view}_corner, stair_flaps_{view}_corner
                         the corners' median departure from square (degrees: each segment's direction the principal
                         axis of its boundary points), ours beyond the design's: the skirt's, the flaps' (pooled)
The family's 'spacing' measure (our folds' spacing at the band against the drawn steps' widths) is reported by the
review, not declared: the turnaround draws only some of its folds as lines, so the design reads it against itself
0.5 off (calibration: miscalibrated); ours spaces its folds as the drawn steps (0.16 / 0.13 L vs 0.15 / 0.14).
"""

DECLARED_CHECKS = [                 # (a literal: read with ast; the pieces pooled per view)
    dict(check='stair_{view}_crossed', family='stair', piece=['skirt', 'overskirt_panel_L', 'overskirt_panel_R'], views=['front', 'three_quarter'],
         params=dict(measure='crossed'), limits=[0, 0],
         flag="the staircase hem's steps are sheared: our zigzag runs across a crease, and it shouldn't; a fold bends a "
              "step that spans it (Michael, 2026-10-01)",
         note="the skirt's and the flaps' stepped dark band: the zigzag's steps (treads with a riser at either end) a fold "
              "crosses, each a defect (our folds: our lines and our geometry's turns, declared.our_folds; the "
              "design's: its ink), ours beyond the design's; count [steps crossed, every tread crossed, treads]",
         calibrate=dict(known_bad='g4_stairs0', baseline=['voronoi_pieces'], shape=['piece_skirt', 'piece_overskirt_panel_L', 'piece_overskirt_panel_R'], kind='defect')),
    dict(check='stair_skirt_{view}_corner', family='stair', piece='skirt', views=['front', 'three_quarter'],
         params=dict(measure='corner', round=1), limits=[3, 5],
         flag="the staircase hem's steps are sheared: the design draws them with exact right angles (Michael, "
              "2026-10-01)",
         note="the skirt's stepped dark band: its corners' median departure from square (degrees), ours beyond the "
              "design's",
         calibrate=dict(known_bad='g4_stairs0', baseline=['voronoi_pieces'], shape=['piece_skirt'], kind='defect')),
    dict(check='stair_flaps_{view}_corner', family='stair', piece=['overskirt_panel_L', 'overskirt_panel_R'],
         views=['front', 'three_quarter'], params=dict(measure='corner', round=1), limits=[3, 5],
         flag="the staircase hem's steps are sheared: the design draws them with exact right angles (Michael, "
              "2026-10-01)",
         note="the overskirt flaps' stepped dark band (both pooled): its corners' median departure from square "
              "(degrees), ours beyond the design's",
         calibrate=dict(known_bad='g4_stairs0', baseline=['voronoi_pieces'],
                        shape=['piece_overskirt_panel_L', 'piece_overskirt_panel_R'], kind='defect')),
]
