"""The wrist cuffs measured (tool/garments4; Michael's garment list, 2026-09-30, item 2: "the design's cuffs have a cream
band that ours lack entirely"; the hands round measured ours at 1.5-2.4x the drawn area). The cream band is
charkit.pieceqa's cuff_{front,back}_trim_{L,R} (calibrated: FAIL 0.29-0.30 on every build, ours have no cream); the size
is declared here (charkit.declared's area family, part 'declared'), named cuff_<side>_<view>_size so that
charkit/calib/details.py's cuff_*_L / cuff_*_R entries don't take them.

Checks (values |ours / design - 1|, lower better):
  cuff_L_{front,three_quarter,profile,back}_size   the left wrist cuff's drawn size against ours
  cuff_R_{front,back}_size                         the right's (the profile hides it; in three-quarter the drawing's
                                                   skirt covers part of the far cuff, which ours shows: a visibility
                                                   matter, the far arm's place, not the cuff's size)
Limits [0.2, 0.4]: the flagged cuffs were 1.47-2.4x the drawn size; 40% over is a FAIL.
"""

DECLARED_CHECKS = [
    dict(check='cuff_L_{view}_size', family='area', piece='cuff_L', views=['front', 'three_quarter', 'profile', 'back'],
         params=dict(round=3), limits=[0.2, 0.4],
         flag="the cuffs: no cream band, 1.5-2.4x the drawn area (Michael, 2026-09-30)",
         note="the left wrist cuff's pixels over the drawn cuff's, |ratio - 1|",
         calibrate=dict(known_bad='g4_before', baseline=['voronoi_pieces'], shape=['piece_cuff_L'], kind='defect')),
    dict(check='cuff_R_{view}_size', family='area', piece='cuff_R', views=['front', 'back'],
         params=dict(round=3), limits=[0.2, 0.4],
         flag="the cuffs: no cream band, 1.5-2.4x the drawn area (Michael, 2026-09-30)",
         note="the right wrist cuff's pixels over the drawn cuff's, |ratio - 1|",
         calibrate=dict(known_bad='g4_before', baseline=['voronoi_pieces'], shape=['piece_cuff_R'], kind='defect')),
]
