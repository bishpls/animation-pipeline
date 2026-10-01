"""The sailor collar's lapels framing the V (tool/garments4 milestone 2, the flat lapels; Michael / the coordinator
2026-10-01: the drawn lapels are wide flat panels whose inner edges form the V down to the knot; ours bunched into
lumps beside the neck). Declared checks (charkit.declared's `band_rows` family: a two-sided band row by row against the
drawn silhouette, the rows where the bow, its tails, the hair or a sleeve covers a band's edge left out per side):
  collar_three_quarter_lapel_width   the RMS of each lapel's width, ours less the drawn (L), z -0.46..-0.80
  collar_three_quarter_lapel_v       the RMS of the lapels' inner edges (the V's line), ours less the drawn (L)
In front the same measure isn't calibrated yet: a 1-2 px vertical move of the design reads 0.035-0.06 L (the lapels'
rows under the shoulder change width fast with height, and the hair over their outer ends takes most rows); the front
lapels are graded by piece_collar's front IoU (the guard), neck_v_front_skin and art_outline_collar.
"""

DECLARED_CHECKS = [                 # (a literal: read with ast)
    dict(check='collar_three_quarter_lapel_width', family='band_rows', piece='collar', views=['three_quarter'],
         params=dict(z=[-0.46, -0.80], measure='width', ref='silhouette',
                     occluders=['bow', 'bow_tail_L', 'bow_tail_R', 'hair', 'sleeve_L', 'sleeve_R']),
         limits=[0.015, 0.03],
         flag="the lapels bunch into lumps beside the neck; the drawn lapels are wide flat panels whose inner edges "
              "form the V down to the knot (Michael / the coordinator, 2026-10-01)",
         note="the collar's lapels in three-quarter row by row (z -0.46..-0.80 L): the RMS of each lapel's width, ours "
              "less the drawn silhouette's, where neither is under the bow, its tails, the hair or a sleeve (L)",
         calibrate=dict(known_bad='g4_v0', baseline=['voronoi_pieces'], shape=['piece_collar'], kind='defect')),
    dict(check='collar_three_quarter_lapel_v', family='band_rows', piece='collar', views=['three_quarter'],
         params=dict(z=[-0.46, -0.80], measure='inner', ref='silhouette',
                     occluders=['bow', 'bow_tail_L', 'bow_tail_R', 'hair', 'sleeve_L', 'sleeve_R']),
         limits=[0.015, 0.03],
         flag="the lapels bunch into lumps beside the neck; the drawn lapels are wide flat panels whose inner edges "
              "form the V down to the knot (Michael / the coordinator, 2026-10-01)",
         note="the lapels' inner edges (the V's line) in three-quarter row by row (z -0.46..-0.80 L): the RMS of the "
              "inner edge's x, ours less the drawn silhouette's (L)",
         calibrate=dict(known_bad='g4_v0', baseline=['voronoi_pieces'], shape=['piece_collar'], kind='defect')),
]
