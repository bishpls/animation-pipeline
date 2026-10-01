"""The wrist cuffs measured (tool/garments4; Michael's garment list, 2026-09-30, item 2: "the design's cuffs have a cream
band that ours lack entirely"; the hands round measured ours at 1.5-2.4x the drawn area). The cream band is
charkit.pieceqa's cuff_{front,back}_trim_{L,R} (calibrated: FAIL 0.29-0.30 on every build, ours have no cream); the size
is declared here (charkit.declared's area family, part 'declared').

Checks (values |ours / design - 1|, lower better):
  cuff_{front,three_quarter,profile,back}_area_L   the left wrist cuff's drawn size against ours
  cuff_{front,three_quarter,back}_area_R           the right's (the profile hides it)
"""

DECLARED_CHECKS = [
    dict(check='cuff_{view}_area_L', family='area', piece='cuff_L', views=['front', 'three_quarter', 'profile', 'back'],
         params=dict(round=3), limits=[0.25, 0.5],
         flag="the cuffs: no cream band, 1.5-2.4x the drawn area (Michael, 2026-09-30)",
         note="the left wrist cuff's pixels over the drawn cuff's, |ratio - 1|",
         calibrate=dict(known_bad='g4_before', baseline=['voronoi_pieces'], shape=['piece_cuff_L'], kind='defect')),
    dict(check='cuff_{view}_area_R', family='area', piece='cuff_R', views=['front', 'three_quarter', 'back'],
         params=dict(round=3), limits=[0.25, 0.5],
         flag="the cuffs: no cream band, 1.5-2.4x the drawn area (Michael, 2026-09-30)",
         note="the right wrist cuff's pixels over the drawn cuff's, |ratio - 1|",
         calibrate=dict(known_bad='g4_before', baseline=['voronoi_pieces'], shape=['piece_cuff_R'], kind='defect')),
]
