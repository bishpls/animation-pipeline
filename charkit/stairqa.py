"""The staircase hem (tool/garments4, Michael 2026-10-01): the skirt's and the overskirt flaps' dark stepped band, drawn
with exact right angles (vertical risers, horizontal treads), each step one pleat: its risers on the pleats' folds and
its treads within a pleat's face. Ours was sheared: its risers mid-pleat, its treads across the folds ("our zigzag
runs across a crease, and it shouldn't: a fold bends a step that spans it").

Declared checks (charkit.declared's `stair` family, front and three-quarter, where the design draws the steps):
  stair_{view}_crossed   the treads a fold crosses (ours: our lines and our geometry's folds, declared.our_folds: the
                         pleats' folds show in the render as cel shading's edges; the design's: its ink), ours beyond
                         the design's (a count)
  stair_skirt_{view}_corner, stair_flaps_{view}_corner
                         the corners' median departure from square (degrees: each segment's direction the principal
                         axis of its boundary points), ours beyond the design's: the skirt's, the flaps' (pooled)
  stair_{view}_spacing   our folds' median spacing where they meet the band against the drawn steps' median width (a
                         step is a pleat), |ratio - 1|: a guard (ours already spaces its folds as the drawn steps; it
                         keeps a fix from respacing them)
"""

DECLARED_CHECKS = [                 # (a literal: read with ast; the pieces pooled per view)
    dict(check='stair_{view}_crossed', family='stair', piece=['skirt', 'overskirt_panel_L', 'overskirt_panel_R'], views=['front', 'three_quarter'],
         params=dict(measure='crossed'), limits=[0, 1],
         flag="the staircase hem's steps are sheared: our zigzag runs across a crease, and it shouldn't; a fold bends a "
              "step that spans it (Michael, 2026-10-01)",
         note="the skirt's and the flaps' stepped dark band: treads a fold crosses (our folds: our lines and our "
              "geometry's turns, declared.our_folds; the design's: its ink), ours beyond the design's",
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
    dict(check='stair_{view}_spacing', family='stair', piece=['skirt', 'overskirt_panel_L', 'overskirt_panel_R'], views=['front', 'three_quarter'],
         params=dict(measure='spacing'), limits=[0.2, 0.4],
         note="our folds' median spacing where they meet the stepped band against the drawn steps' median width (a "
              "step is a pleat), |ratio - 1|",
         calibrate=dict(known_bad=None, no_known_bad="a guard: ours already spaces its folds as the drawn steps "
                        "(g4_stairs0 0.04 / 0.08); it keeps the staircase's fix from respacing the pleats",
                        baseline=['voronoi_pieces'], shape=['piece_skirt', 'piece_overskirt_panel_L', 'piece_overskirt_panel_R'])),
]
