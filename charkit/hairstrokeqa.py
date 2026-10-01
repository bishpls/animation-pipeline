"""The hair's strokes measured (tool/hairstrokes; Michael, 2026-10-01: the hair lacks "detail in the bulk of the mass",
which in anime hair is mostly ink strokes inside the locks: strand lines and partial separations). The outline
renderer's hulls draw silhouettes and the boundaries between pieces; what the design draws inside a lock is a stroke (a
line layer: charkit.geom.hairink). These checks read the drawn strokes inside the hair's mass per view against ours, as
declared checks (charkit.declared's `strokes` family on the hair as a piece: the design's lines inside the mass, off its
outline and clear of the buns, the ahoge and the clips, without the splitter's lock lines; ours, our ink strokes).

The turnaround draws its strand texture view by view: strokes placed in 3D from one view add 0.00-0.01 to the recall of
another view's strokes (tool/hairstrokes, lab on hst_base), so a single 3D set of strokes can match each view's exact
strokes only where it was taken from that view (the canonical-view rule: re-measured against the flag's intent, the
exact placement reported as each view's cost). The checks are the intent, in every view:

  hair_strokes_{view}_density  where and how many: the drawn strands' and our strokes' density fields (length per
                               area, 0.06 L): their L1 difference over their sum. The design moved 1-2 px reads
                               0.05-0.06, the strands moved 0.05-0.15 L 0.31-0.36, scattered anywhere in the mass
                               0.67-0.76 (the calibration's stand-in: 0.645-0.80): PASS within 0.3 (the moved
                               strands' level), FAIL past 0.65 (the scattered ones'). recall (0.04 L), place (0.015 L:
                               the exact strokes, each view's cost) and precision reported beside it
  hair_strokes_{view}_dir      direction: the median angle between our strokes and the drawn hair's flow (every drawn
                               line inside the mass, at 0.03 L) where that flow is clear (degrees): the design 4-6, the
                               strands turned 30-90 degrees 51-63

  bun_{L,R}_{view}_lines       the buns' drawn lines (where a bun's front block meets the one behind, its tiers'
                               steps: charkit.geom.hairink's bun set) our lines and strokes lack (declared.ink_inside
                               inside the drawn bun, our ink at least a pixel wide): 1 - recall within 0.015 L

Views (strands): front, three-quarter and profile. The back's drawn interior ink is the hem flicks' notch ticks (0.53 L) and its
mass is plain (Michael's flag 5: hair_back_lines, the ink inside the back's mass, guards it): the flick shells draw the
ticks (the geometry track), the line layer leaves the back alone.

Calibrated (charkit.calibrate, the generic stand-in declared.Declared: for the design its strands are our ink layer, its
other lines our outlines): the design moved 1-2 px, the known-bad hst_base (pipeline-3d 3168961's default: no strokes),
and the stroke floors (declared.STROKE_FLOORS: the drawn strands scattered in the mass, or turned in place).
"""

DECLARED_CHECKS = [
    dict(check='hair_strokes_{view}_density', family='strokes', piece='hair', views=['front', 'three_quarter', 'profile'],
         params=dict(measure='density', strokes='strand', scale=0.06, near=0.04, tol=0.015), limits=[0.3, 0.65],
         flag="the hair lacks detail in the bulk of the mass: the ink strokes inside the locks (Michael, 2026-10-01)",
         note="the drawn strand strokes' and our strokes' density fields inside the hair's mass (0.06 L): their L1 "
              "difference over their sum (0 the same strokes, 1 none where the other has them); recall (0.04 L), "
              "place (0.015 L) and precision beside it",
         calibrate=dict(known_bad='hst_base', baseline=['scattered_strokes'],
                        shape=['hair_piece_bangs', 'hair_piece_side_locks', 'hair_piece_upper_back',
                               'hair_piece_lower_back'])),
    dict(check='hair_strokes_{view}_dir', family='strokes', piece='hair', views=['front', 'three_quarter', 'profile'],
         params=dict(measure='dir', strokes='strand', flow_scale=0.03, coherent=0.6), limits=[20, 30],
         flag="the hair lacks detail in the bulk of the mass: the ink strokes inside the locks (Michael, 2026-10-01)",
         note="the median angle (degrees) between our strokes and the drawn hair's flow where it is clear",
         calibrate=dict(known_bad='hst_base', baseline=['turned_strokes'],
                        shape=['hair_piece_bangs', 'hair_piece_side_locks', 'hair_piece_upper_back',
                               'hair_piece_lower_back'])),
    dict(check='bun_L_{view}_lines', family='ink_inside', piece='hair',
         params=dict(region='bun_L', band=0.015, with_ink=True, round=3), limits=[0.35, 0.6],
         flag="the hair lacks detail in the bulk of the mass: the ink strokes inside the locks (Michael, 2026-10-01)",
         note="the lines drawn inside the left bun (where its front block meets the one behind, its tiers' steps) our "
              "lines and strokes lack: 1 - recall of their skeleton within 0.015 L",
         calibrate=dict(known_bad='hst_base', baseline=['voronoi_pieces'], shape=['hair_piece_buns'])),
    dict(check='bun_R_{view}_lines', family='ink_inside', piece='hair',
         params=dict(region='bun_R', band=0.015, with_ink=True, round=3), limits=[0.35, 0.6],
         flag="the hair lacks detail in the bulk of the mass: the ink strokes inside the locks (Michael, 2026-10-01)",
         note="the lines drawn inside the right bun (where its front block meets the one behind, its tiers' steps) our "
              "lines and strokes lack: 1 - recall of their skeleton within 0.015 L",
         calibrate=dict(known_bad='hst_base', baseline=['voronoi_pieces'], shape=['hair_piece_buns'])),
]
