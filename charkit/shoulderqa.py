"""The shoulders and the sailor collar's back panel measured (tool/garments4 milestone 3; Michael's garment list,
2026-09-30, item 3, and his note relayed 2026-10-01: "the shoulders are still misshapen"; the back view's cream collar
section may be shoulder-related). Declared checks (charkit.declared), part 'declared', each against the drawn pieces'
silhouettes (ref 'silhouette': the drawing's lines inside the figure given to the nearest piece; the drawn line at the
figure's edge is 0.0235 L wide and our outline sits inside our silhouette).

Checks (lengths in L):
  shoulder_{front,back}_top    the upper garments' (the jacket, the collar, the puffs) top edge over |x| 0.15-0.70 each
                               side, where the lower edge of ours and the drawn isn't under hair: the median of ours
                               less the design's, the worse side's size (declared top_line 'dz')
  shoulder_{front,back}_dip    the deepest trough in that edge (the water line between its higher points either side)
                               beyond the design's: the dip between the collar and the puff (top_line 'trough')
  shoulder_front_tilt          its slope against |x| (L per L), |ours - design's|, the worse side (top_line 'slope'; in
                               back collarqa's shoulder_back_slope reads it, a guard)
  collar_back_rows             the collar's back panel: the RMS of its row widths at tenths of the way down it against
                               the drawn panel's (declared width 'rms'): a square panel against a rounded flap
The three-quarter view isn't graded: there the drawing puts the far shoulder and collar 0.03-0.05 L under ours while
the front puts them 0.02-0.09 L over (the views disagree: Part 1's far-sleeve note); it is reported beside these.
"""

DECLARED_CHECKS = [
    dict(check='shoulder_{view}_top', family='top_line', piece=['top', 'collar', 'sleeve_L', 'sleeve_R'], views=['front', 'back'],
         params=dict(x=[[-0.7, -0.15], [0.15, 0.7]], measure='dz', ref='silhouette'), limits=[0.015, 0.03],
         flag="the shoulders: still misshapen (Michael, 2026-10-01): a dip between the collar and the puff where the drawn "
              "line runs level, the line low",
         note="the upper garments' top edge over |x| 0.15-0.70 (not under hair) against the drawn silhouette's: "
              "the median of ours less the design's, the worse side",
         calibrate=dict(known_bad='g4_before', baseline=['voronoi_pieces'], shape=['piece_top', 'piece_collar', 'piece_sleeve_L'], kind='defect')),
    dict(check='shoulder_{view}_dip', family='top_line', piece=['top', 'collar', 'sleeve_L', 'sleeve_R'], views=['front', 'back'],
         params=dict(x=[[-0.7, -0.15], [0.15, 0.7]], measure='trough', ref='silhouette'), limits=[0.025, 0.036],
         flag="the shoulders: still misshapen (Michael, 2026-10-01): a dip between the collar and the puff where the drawn "
              "line runs level, the line low",
         note="the deepest trough in the upper garments' top edge over |x| 0.15-0.70 beyond the design's: the "
              "dip between the collar and the puff",
         calibrate=dict(known_bad='g4_cuffs2', baseline=['voronoi_pieces'], shape=['piece_top', 'piece_collar', 'piece_sleeve_L'], kind='defect')),
    dict(check='shoulder_front_tilt', family='top_line', piece=['top', 'collar', 'sleeve_L', 'sleeve_R'], views=['front'],
         params=dict(x=[[-0.7, -0.15], [0.15, 0.7]], measure='slope', ref='silhouette'), limits=[0.1, 0.2],
         flag="the shoulders: still misshapen (Michael, 2026-10-01): a dip between the collar and the puff where the drawn "
              "line runs level, the line low",
         note="the slope of the upper garments' top edge against |x| over 0.15-0.70, |ours - design's|, the "
              "worse side",
         calibrate=dict(known_bad='g4_cuffs2', baseline=['voronoi_pieces'], shape=['piece_top', 'piece_collar', 'piece_sleeve_L'], kind='defect')),
    dict(check='collar_back_rows', family='width', piece='collar', views=['back'],
         params=dict(mode='rms', ref='silhouette', round=3), limits=[0.03, 0.06],
         flag="the back view's cream collar: the drawn panel is square, lying on the shoulders; ours a rounded flap "
              "(Michael, 2026-09-30)",
         note="the collar's back panel: the RMS of its row widths at tenths of the way down it against the "
              "drawn panel's (L)",
         calibrate=dict(known_bad='g4_cuffs2', baseline=['voronoi_pieces'], shape=['piece_collar'], kind='defect')),
]
