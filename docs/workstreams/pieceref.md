# Piece references and the bow's sub-pieces (tool/pieceref)

Worktree `~/animation-pipeline-pieceref`, branch `tool/pieceref` from tool/bow2 478f0ce (its bowqa checks and the
close-hung option), pipeline-3d 1580f95 merged in (d07ef79). Box build of the option (bow2's):
`~/animation-pipeline-bow2/charkit/out/b2_close`; before: `.../b2_before`; the old sunken-ribbon build (pre-M1):
`~/animation-pipeline-garments3/charkit/out/g3_render3`.

## Michael's decisions (2026-09-30)
1. Take the close-hung bow (profile IoU 0.346 -> 0.654). Option C for `bow_profile_ribbon`: remeasure it as what he
   meant, "ribbons merging into the blouse": the ink line between ribbon and jacket, calibrated, registered.
2. Sub-piece-cut multi-segment garments: the bow as knot + left lobe + right lobe (the tails are pieces already), each
   with its own mask in the outfit masks and truth, its own shape checks, and checks of its inner lines (the knot's
   outline and rectangle, each lobe's crease).
3. Isolated-piece checks: shape from the isolated reference (garment_breakdown, close-ups), placement, occlusion and
   silhouette in context from the turnaround. Render each piece alone in the reference's projection, scaled to its
   own size; compare shape and inner lines. Refcheck each generated reference against the turnaround first.
4. Generate references where needed (paid, approved, few calls, logged to tools/ledger.jsonl): a bow close-up sheet.

## State (start here)
- The option is in the default spec (charkit/spec/clawd.json: ribbon turn 20, w [0.204, 0.338], drop 0.2).
- Option C in charkit/collarqa.py (`ribbon_line`): calibration running (harness `charkit/out/pieceref/harness/ribcal.py`).

## Next steps
1. Option C calibration (design, g3_render3 must FAIL, b2_before, b2_close), register the remeasure
   (charkit/steps/collarqa.py), tests.
2. Sub-pieces: outfit graph parts, masks (`VIEW__bow.knot`, `VIEW__bow.lobe_L|R`), truth, score.
3. Isolated-piece checks (garment_breakdown's bow; refcheck against the turnaround), then the bow fix.
