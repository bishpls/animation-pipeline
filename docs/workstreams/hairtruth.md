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
