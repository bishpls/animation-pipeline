"""The wrist cuffs measured (tool/garments4; Michael's garment list, 2026-09-30, item 2: "the design's cuffs have a cream
band that ours lack entirely"; the hands round measured ours at 1.5-2.4x the drawn area). The cream band is
charkit.pieceqa's cuff_{front,back}_trim_{L,R} (calibrated: FAIL 0.29-0.30 on every build, ours have no cream); the size
is declared here (charkit.declared's area family, part 'declared'), named cuff_<side>_<view>_size so that
charkit/calib/details.py's cuff_*_L / cuff_*_R entries don't take them.

The size is measured against the drawn cuff's silhouette (declared.area's ref 'silhouette': the drawing's lines
inside the figure given to the nearest piece, as our geometry meets its neighbours with no ink between them and as the
calibration's stand-in draws the design), not the drawn fill: the cuff's silhouette is ~1.23x its fill, and against the
fill the design moved 1-2 px read 0.23-0.24 off itself (MISCALIBRATED, 2026-10-01). Against the silhouette the flagged
cuffs (g4_before, pipeline-3d's) are 1.24-1.33x; the first template fit (g4_cuffs) 0.79-0.83x (~1.0x the fill).

Checks (values |ours / design - 1|, lower better):
  cuff_L_{front,three_quarter,profile,back}_size   the left wrist cuff's drawn size against ours
  cuff_R_{front,back}_size                         the right's (the profile hides it; in three-quarter the drawing's
                                                   skirt covers part of the far cuff, which ours shows: a visibility
                                                   matter, the far arm's place, not the cuff's size)
Limits [0.1, 0.2], set from the defect: the flagged cuffs read 1.24-1.33x the drawn silhouette, so over 20% off is a
FAIL (either way: the first fit's 0.79-0.83x fails too); within 10% (about 5% in width) passes.
"""

DECLARED_CHECKS = [
    dict(check='cuff_L_{view}_size', family='area', piece='cuff_L', views=['front', 'three_quarter', 'profile', 'back'],
         params=dict(round=3, ref='silhouette'), limits=[0.1, 0.2],
         flag="the cuffs: no cream band, 1.5-2.4x the drawn area (Michael, 2026-09-30)",
         note="the left wrist cuff's pixels over the drawn cuff's, |ratio - 1|",
         calibrate=dict(known_bad='g4_before', baseline=['voronoi_pieces'], shape=['piece_cuff_L'], kind='defect')),
    dict(check='cuff_R_{view}_size', family='area', piece='cuff_R', views=['front', 'back'],
         params=dict(round=3, ref='silhouette'), limits=[0.1, 0.2],
         flag="the cuffs: no cream band, 1.5-2.4x the drawn area (Michael, 2026-09-30)",
         note="the right wrist cuff's pixels over the drawn cuff's, |ratio - 1|",
         calibrate=dict(known_bad='g4_before', baseline=['voronoi_pieces'], shape=['piece_cuff_R'], kind='defect')),
]
