# hairtruth: Clawd's hair checks against the hair WITHOUT its clips (tool/hairtruth)

Worktree `~/animation-pipeline-hairtruth`, branch `tool/hairtruth` from pipeline-3d cd1c327f. Harness and outputs:
`charkit/out/hairtruth/`.

## Brief (Michael, 2026-10-01, via the coordinator)
"If we aren't yet comparing hair checks against the no-accessories references, we absolutely should be." Every hair
check reads the turnaround WITH the star and crab clips, so the pixels under the clips count as clip, not hair.
1. Register `charkit/refs/clawd/gen/hair_clips_layers.png`'s top row (the hair without clips: front, three-quarter,
   profile) as the hair pieces' shape truth (manifest `shape_truth`, read by `manifest.shape_sheet`). Refcheck first.
   The turnaround stays the placement authority; the back keeps the turnaround (no clean back; the clips don't reach it).
2. Every hair check reads its piece's shape truth (hair masks, hair_piece_* IoUs, hair_lock_lines_*, hair_back_*,
   art_peeks_hair's drawn side, the strokes checks' drawn strokes, the lock truth's side-lock labels,
   art_terminator_hair's drawn side). Fill the clip area from the clean sheet, or exclude clip pixels: measure both.
3. A remeasure: MEASUREMENT_STEPS per module, calibration records refreshed (design pass, known-bad fail, floor).
4. Report the distortion: every hair check before/after per view, grades changed.
Coordinate: tool/hairshell3 and the hair strokes round read these checks; whichever merges second refreshes records.
The second character's hair under his crown uses the same rule: keep it generic.

## State
- Setup (2026-10-01).

## Done (2026-10-01)
- Baseline: box build of pipeline-3d cd1c327f, default spec, `charkit/out/hairtruth/base` (QA 402 s, CPU 1334 s).
- **Mechanism** (`charkit/shapetruth.py`, commit 7f189116): the manifest's `shape_truth.hair` = hair_clips_layers'
  top row (`rows: top`, views front/three_quarter/profile, placement head_turnaround, covers: the accessories accqa
  finds). Per turnaround view: register the redraw by the eyes, refine scale (+-4%) and shift (+-0.04 L) on the hair
  colour's IoU over the head (each figure its own blob), then the shift on a ring 0.02-0.15 L round the clip; repaint
  only the clip pixels (grown 0.012 L, plus turnaround pixels within 0.04 L differing from the redraw and joined to
  the clip: the crab's legs the finder misses). The turnaround stands everywhere else. `CHARKIT_SHAPE_TRUTH=off`
  restores the old reading (bit-identical to the box QA on cd1c327f's build).
- QA side: `qa3d.Design.shape_truth/shape_views/shape_head/hidden`. Consumers: sheet_body (iou_hair, hair_length,
  hair_width from a second evaluate on the shape views, ours without our clips), hair_pieces (families under the clip
  from the nearest drawn family, `shapetruth.fill_labels`), hair_flags (truth labels under the clip cleared: the
  nearest drawn lock), declared hair families (O_hair, lines_hair, ink_hair, hairweight design/our head), artifacts'
  hair region (design from the composite head sheet, ours drawn without clips). Calibration stand-ins (Hair,
  HairFlags, Declared via `views_for`, Art) read the same views.
- **Refcheck** (`python -m charkit.shapetruth charkit/spec/clawd.json`; recorded in the manifest's shape_truth.hair):
  head sheet hair silhouette IoU outside the clips 0.971/0.934/0.975, ring 0.943/0.930/0.958; body sheet
  0.850/0.858/0.915 (the head turnaround itself registered the same way: 0.849/0.880/0.919), ring 0.869/0.914/0.946.
  Known-bad (views mislaid): FAIL every view (hair IoU 0.36-0.54).
- **Fill vs exclude** (tools/exclude.py): body iou_hair F/3q/P drawn 0.827/0.743/0.797, fill 0.862/0.777/0.852,
  exclude 0.856/0.771/0.852; bangs drawn 0.758, fill 0.833, exclude 0.856; side locks 0.505/0.536/0.545; lock lines P
  0.167/0.205/0.160. Picked **fill**: it scores the hair under the clips against the separated layer (exclude leaves
  2.5-3% of the hair unscored per view, and would leave a crown's whole region unscored on the second character); it
  decouples the hair checks from our clips' placement (exclude's region includes our clip's footprint); it needs no
  per-check special case.
- Steps registered (4477784b): steps/qa3d.py, hairflagqa.py, artifactqa.py, declared.py (new).

## Coordination
- tool/hairshell3 and the hair strokes round read these checks: whichever merges second refreshes its calibration
  records (the remeasure moves hair_strokes_*, hair_lock_lines_*, hair_piece_*, art_*_hair). The strokes round's
  target art_terminator_hair <= 2.064 was set under the old reading (the clips inflated the design's kinks: 3.74 ->
  2.54 per L front): under the shape truth the same build reads 3.211.

## Calibration (box build2, my copy; known-bads hair5_1580f95, hst_base pushed into it from hairstrokes' store)
- Before/after on cd1c327f's build (tools/measure.py with CHARKIT_SHAPE_TRUTH off/on; table: charkit/out/hairtruth/
  distortion.md): body iou_hair F/3q/P 0.827/0.743/0.797 -> 0.862/0.777/0.852; bangs 0.758 -> 0.833 (profile 0.629 ->
  0.789); side locks 0.505 -> 0.536; lock lines P 0.167 -> 0.205; strokes density P 0.587 -> 0.414; art_terminator_hair
  2.178 -> 3.211 (grade WARN -> FAIL: the design's kinks per L 3.74/4.35/5.92 -> 2.54/2.73/3.44); art_peeks 18 -> 16.
- Records: hair_lock_lines_3q/P, hair_back_lines calibrated (hair5_1580f95 FAIL); hair_piece_{bangs, side_locks,
  upper_back, lower_back, buns}, hair_bun_outline: guard (floor voronoi_families FAILs). hair_piece_bangs re-registered
  as a shape guard (its hl_base record was blind: a family IoU can't see the lock partition): a decision for Michael.
  body_*_iou_hair (calib/bodyhair.py): first floor (re-partition inside the drawn head) passed in profile (0.785):
  coarse; floor now voronoi_head (a random hair silhouette round the head), the old one a probe (job running).
- art_terminator_hair / art_peeks_hair: known-bad look_v5 is on no reachable machine (laptop, build, build2, render2;
  the render box is stopped): their records can't be refreshed -> the gate blocks on them (calibration rows can't be
  --accept'ed). ck7_blotchy (hairshell's store) can't stand in: its spec predates 'base' (the QA refuses it).
  The Art stand-in now reads no peeks for the design (dbae8593).

## The artifact detectors: held (98453674), ready on tool/hairtruth-art (55640985)
- On tool/hairtruth `artifactqa.HAIR_SHAPE_TRUTH = False`: art_*_hair read as before (verified bit-identical). The
  calibration's design leg passes under the switch (terminator 1..1, peeks 0..0 with the Art stand-in's no-peeks fix);
  the known-bad look_v5 is missing, so their records would read `unmeasured` and the gate blocks (calibration rows
  can't be accepted). tool/hairtruth-art = tool/hairtruth + the flip (2eb75288) + its step (55640985). To land it:
  restore look_v5 (the stopped render box ran perceptual on it, 2026-09-29: it may hold it) into charkit/out/calib/
  builds, `python -m charkit calibrate art_terminator_hair,art_peeks_hair --build BUILD`, store the design measures
  (`python -m charkit.artifactqa design BUNDLE_DIR`: a new stamp, hair_shape), gate.

## Gate (2026-10-01)
- All remeasured graded checks have fresh GOOD records (calibrated: hair_lock_lines_*, hair_back_lines, the 12
  hair_strokes_*, bun_L_front_lines; guard: hair_piece_{bangs,side_locks,upper_back,lower_back,buns},
  hair_bun_outline, body_*_iou_hair). pipeline-3d 27a4b6c3 (accessories6, infra5-s) merged in (clean).
- Pregate --box auto: PASS (0 moved), 98453674 into 27a4b6c3.
- Gate launched: `python -m charkit remote gate tool/hairtruth --into pipeline-3d` (log charkit/out/hairtruth/gate.log).
