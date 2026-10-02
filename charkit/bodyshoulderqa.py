"""The bare body's shoulders measured against the base body sheet (tool/garments4 rounds 5-7; Michael's flag,
2026-10-01: "the body has no real shoulder": the torso's top fitted to the costume's silhouette, the arms capped tubes
beside it). Declared checks (charkit.declared), part 'declared', each on our skin alone (garments off: declared's
our_body) against the base body sheet's body (ref 'base_body': the manifest's sheet at the refcheck scale, registered
on the turnaround's head; its hair's place counted as body, ours has no hair over it).

Checks (lengths in L):
  body_shoulder_{front,back}_top   the bare shoulder line over |x| 0.18-0.62, below z -0.42 (not under the sheet's hair):
                                   the median of ours less the sheet's, the worse side (top_line 'dz')
  body_shoulder_{front,back}_side  the deltoid's outer edge over z -0.58..-0.95: the median |x| difference, the worse
                                   side (side_line 'dx')
  body_axilla_{front,back}         where the arm parts from the torso (the armpit's height) against the sheet's, the
                                   worse side (side_line 'axilla')
  body_shoulder_{front,back}_iou   the bare upper body's silhouette, z -0.42..-1.15, against the sheet's: IoU
Calibrated on the joined shoulder (g6_c2; known-bad g5_base, the body without a shoulder; floor voronoi_pieces). The
profile and three-quarter IoUs aren't graded: in profile the old body already reads 0.88 (the known-bad doesn't fail:
the joined shoulder changes the front and back extents), and in three-quarter the floor reads 0.90 (the current build
only 0.42 of the way from it to the design: too coarse to trust).
"""

DECLARED_CHECKS = [
    dict(check='body_shoulder_{view}_top', family='top_line', piece='skin', views=['front', 'back'],
         params=dict(x=[[-0.62, -0.18], [0.18, 0.62]], measure='dz', ref='base_body', below=-0.42), limits=[0.02, 0.04],
         flag="the body has no real shoulder (Michael, 2026-10-01: the torso's top fitted to the costume's silhouette, the arms capped tubes beside it)",
         note="our bare shoulder line (the skin alone, the top edge over |x| 0.18-0.62 not under the sheet's hair) "
              "against the base body sheet's: the median of ours less its, the worse side (L)",
         calibrate=dict(known_bad='g5_base', baseline=['voronoi_pieces'], shape=['body_shoulder_front_iou', 'body_shoulder_back_iou'], kind='defect')),
    dict(check='body_shoulder_{view}_side', family='side_line', piece='skin', views=['front', 'back'],
         params=dict(z=[[-0.58, -0.95]], measure='dx', ref='base_body'), limits=[0.02, 0.04],
         flag="the body has no real shoulder (Michael, 2026-10-01: the torso's top fitted to the costume's silhouette, the arms capped tubes beside it)",
         note="the deltoid's outer edge (the skin alone, z -0.58..-0.95) against the base body sheet's: the median |x| "
              "difference, the worse side (L)",
         calibrate=dict(known_bad='g5_base', baseline=['voronoi_pieces'], shape=['body_shoulder_front_iou', 'body_shoulder_back_iou'], kind='defect')),
    dict(check='body_axilla_{view}', family='side_line', piece='skin', views=['front', 'back'],
         params=dict(z=[[-0.7, -1.35]], measure='axilla', ref='base_body'), limits=[0.03, 0.06],
         flag="the body has no real shoulder (Michael, 2026-10-01: the torso's top fitted to the costume's silhouette, the arms capped tubes beside it)",
         note="where the arm parts from the torso (the armpit's height) against the base body sheet's, the worse "
              "side (L)",
         calibrate=dict(known_bad='g5_base', baseline=['voronoi_pieces'], shape=['body_shoulder_front_iou', 'body_shoulder_back_iou'], kind='defect')),
    dict(check='body_shoulder_{view}_iou', family='shape_iou', piece='skin', views=['front', 'back'],
         params=dict(ref='base_body', window=[-1.0, 1.0, -0.42, -1.15]), limits=[0.9, 0.8], better='higher',
         flag="the body has no real shoulder (Michael, 2026-10-01: the torso's top fitted to the costume's silhouette, the arms capped tubes beside it)",
         note="the bare upper body's silhouette (the skin alone, z -0.42..-1.15) against the base body sheet's, its "
              "hair left out: IoU",
         calibrate=dict(known_bad='g5_base', baseline=['voronoi_pieces'], shape=[], kind='shape')),
]
