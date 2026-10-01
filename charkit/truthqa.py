"""The garment pieces against their shape truths (tool/garments8; Michael, 2026-10-01: "Don't we just need to give the
system a reference to the collar / lapels without the bow? That's never actually been defined / spec'd"). A covered
piece's shape is drawn nowhere on the turnaround: the bow hides the lapels' lower half and the V's point, the collar
hides the jacket's neckline, shoulders and back. Its shape truth is its layer without what lies on it (the manifest's
`shape_truth`, charkit.layerref: the separated layer sheets registered against the turnaround and cut into pieces), and
ours is drawn the way that sheet draws the outfit: without the covering pieces' objects (declared's `truth`). The
turnaround stays the placement authority: the piece checks (piece_<id>, in context) are unchanged.

Declared checks (charkit.declared's shape_iou family with `truth`: bodymeasure.iou_tol at OUTLINE_TOL, the guard's
metric; graded as the piece checks are, qa3d.PIECE_PASS / PIECE_WARN):
  collar_{view}_truth   the sailor collar and its lapels drawn without the bow, against bodice_layers' collar (the
                        lapels flat on the chest down to the V's point under the knot): front, three-quarter, back.
                        Not in profile: there the collar is edge-on, a band ~0.04 L thick, and the truth moved 6 px
                        (0.028 L) reads 0.58, 8 px 0.29 (the other views 0.76-0.97 at 8 px): an offset, not a shape
  top_{view}_truth      the jacket drawn without the collar and the bow, against top_layers' jacket (its V neckline,
                        the tops of its shoulders and its back under the collar)
"""

DECLARED_CHECKS = [                 # (a literal: read with ast)
    dict(check='collar_{view}_truth', family='shape_iou', piece='collar', views=['front', 'three_quarter', 'back'],
         params=dict(truth='collar'), limits=[0.75, 0.5], better='higher',
         flag="the lapels bunch into lumps beside the neck; the drawn lapels are wide flat panels whose inner edges "
              "form the V down to the knot, and their shape under the bow was never defined (Michael / the "
              "coordinator, 2026-10-01)",
         note="the collar and its lapels drawn without the bow against bodice_layers' collar (the collar without the "
              "bow, registered: charkit.layerref --kind bodice): iou_tol at OUTLINE_TOL",
         calibrate=dict(known_bad='g8_lapels0', baseline=['voronoi_pieces', 'affine_pieces'],
                        shape=['piece_collar'], kind='shape')),
    dict(check='top_{view}_truth', family='shape_iou', piece='top',
         params=dict(truth='top'), limits=[0.75, 0.5], better='higher',
         note="the jacket drawn without the collar and the bow against top_layers' jacket (the top without the collar "
              "and the bow, registered: charkit.layerref --kind top): iou_tol at OUTLINE_TOL",
         calibrate=dict(known_bad='g8_lapels0', baseline=['voronoi_pieces', 'affine_pieces'],
                        shape=['piece_top'], kind='shape')),
]
