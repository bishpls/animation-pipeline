# Calibration as a tool, the gate's calibration requirement and anti-gaming guard (tool/calib, 2026-09-30)

Worktree `~/animation-pipeline-infra3`, branch `tool/calib` from pipeline-3d 8b5ecae. The brief (Michael queued it):
several of today's defects passed their checks because a check was miscalibrated or too coarse (look5's chin,
hair_piece_bangs, piece_sleeve, bow_profile_ribbon). Items: (1) `python -m charkit calibrate CHECK`, the calibration
triple, records backfilled; (2) the gate requires a calibration record for a new or remeasured check; (3) the
anti-gaming guard; (4) recorded acceptance of a named new FAIL; (5) the process guide section in CHARKIT_HANDOFF.md.

## State (read first when resuming)

- Code: `charkit/calibrate.py` (engine, store, records, CLI, the gate's readings), `charkit/calib/` (the registry
  literals and adapters: labels.py (collar_flags, sheet_pieces, hair_pieces), chin.py, hairtruth.py; records/;
  known_bad/), gate.py (calibration_step, judge, report, `--accept-fail`), cli.py (`calibrate`),
  charkit/tests/test_calibrate.py.
- The current build for calibrations: `charkit/out/calib/cur_8b5ecae` (box build of pipeline-3d 8b5ecae, default spec).
- The known-bad store (local, hard links, gitignored): `charkit/out/calib/builds/{g3_render3,co_render,hl_base,
  look5_before}`; what each is: `charkit/calib/known_bad/NAME.json`.

## Running at the last checkpoint, and next steps

- Box gate A: `remote gate tmp/calib-bow --into 3ebc3fb --code tool/calib` (tmp/calib-bow = cbca3ad; gate code 9b4f17b);
  log `charkit/out/calib/gateA_bow.log`. Expected FAIL: the anti-gaming guard on bow_front_bleed, bow_front_loop_end,
  bow_profile_ribbon (piece_bow profile 0.553 -> 0.341, -38%), and no calibration record for the collar_flags checks.
  (9b4f17b also counted bow_front_loop_width as improved "new, no old-geometry reading" though the 2x2 read it on both
  geometries; fixed after: a 2x2 row decides.) Offline check: `python charkit/out/calib/harness/bow_pair.py` (FAIL, the
  same blocks, 0.05 s).
- Box gate B: `remote gate tmp/calib-bow-accept --into 3ebc3fb --code tool/calib` (59f5b7e = cbca3ad + the 9 records +
  validation-only acceptances of the three guard-blocked bow checks, never merged); log `charkit/out/calib/gateB_accept.log`.
  Expected: the guard blocks reported under "Accepted by name"; records found; collar_back_iou (blind) and
  collar_back_lay (miscalibrated) still block on their verdicts.
- The art_* records: `charkit/out/calib/run_art.log` (the Art adapter; the head sheet moved after refcheck.at_scale).
- Then: pregate, `python -m charkit remote gate tool/calib --into pipeline-3d`, the review page
  (`python charkit/out/calib/harness/page.py` -> charkit/out/calib/review/index.html).

## How it works

`python -m charkit calibrate CHECK[,CHECK] [--build DIR]` runs the check's QA part (this tree's code) on:
- the design against itself: the design's own inputs drawn into the label image our z-buffer would make (the outfit's
  piece masks, the hair layers; the drawing's lines absorbed into the nearest piece, as our surfaces meet with no ink),
  moved 1-2 px in each of 4 directions (8 moves): must PASS every move; spread reported;
- the known-bad: the named stored build: must FAIL;
- the floor: random stand-ins (5 seeds per generator): voronoi_pieces (the garments' area cut into random cells of
  random pieces), affine_pieces (each piece moved 0.03-0.06 L, scaled 0.9-1.1), voronoi_families (hair),
  shadow_moved (the chin: the design's shadow moved 4-8 px), shuffle_regions (the hair truth);
- probes (granularity): cap_up (the sleeves' caps raised 0.04 L);
- the current build: must beat the floor by half the way to the design.
A defect detector (registry `kind='defect'`: a squareness, a trough, a straight end, a bleed, a width) may pass a random
stand-in (it lacks the defect); its shape is the anti-gaming guard's (`shape`). A score (`kind='score'`) is judged by
its separations.

## Records (current build cur_8b5ecae; charkit/calib/records)

| check | verdict | design (moved 1-2 px) | known-bad | floor | current |
|---|---|---|---|---|---|
| shoulder_back_line | calibrated | 0-0.014 | g3_render3 0.0565 FAIL | 1.57 / 0.042 FAIL | 0.0565 FAIL |
| shoulder_back_slope | guard | 0.054-0.072 | (a guard) | FAIL / FAIL | 0.102 WARN |
| collar_back_iou | **blind** | 0.925-0.957 | g3_render3 0.754 **WARN** | 0 FAIL / 0.726 WARN | 0.747 WARN |
| collar_back_square | calibrated (defect) | 0 | 0.345 FAIL | FAIL / 0.029 PASS | 0.345 FAIL |
| collar_back_lay | **miscalibrated** | 0.0141 **WARN** every move | 0.0471 FAIL | 0.005 PASS / 0.014 WARN | 0.0424 FAIL |
| bow_front_loop_end | calibrated (defect) | 0.119-0.146 | 0.593 FAIL | 0 PASS / 0.195 WARN | 0.121 PASS |
| bow_front_loop_width | guard (defect) | 0.018 | (a guard) | FAIL / WARN | 0.002 PASS |
| bow_front_bleed | calibrated (defect) | 0 | 0.3775 FAIL | FAIL / FAIL | 0 PASS |
| bow_profile_ribbon | calibrated (defect) | 0.118-0.171 | 0.868 FAIL | 1.0 FAIL / 0.118 PASS | 0.053 PASS |
| piece_sleeve_L | **blind** | 0.990-0.999 | co_render 0.883 **PASS** | 0.004 FAIL / 0.828 PASS | 0.931 PASS; probe cap_up **0.94 PASS** |
| piece_sleeve_R | **blind** | 0.977-1.0 | co_render 0.777 **PASS** | 0 FAIL / 0.729 WARN | 0.834 PASS; probe cap_up **0.90 PASS** |
| piece_bow | guard | 0.978-0.995 (profile 0.865-0.972) | - | 0.017 FAIL / 0.668 WARN | 0.754 PASS |
| piece_collar | guard | 0.939-0.949 (profile 0.085-0.12) | - | 0 FAIL / 0.647 WARN | 0.756 PASS |
| hair_piece_bangs | **blind** | 0.90-0.953 | hl_base 0.792 **PASS** | 0.15 FAIL | 0.792 PASS |
| face_shadow_chin_edge | calibrated | 0.004-0.0098 | look5_before 0.060 FAIL | 0.029 WARN | 0.0567 FAIL (the flag open) |
| face_shadow_chin (INFO) | blind | 0.83-0.93 | look5_before 0.705 WARN | 0.670 FAIL | 0.695 FAIL |

Readings:
- The tool reproduces Michael's cases: hair_piece_bangs and piece_sleeve are blind to their known-bads (the bangs'
  locks at a random split's level, the caps above the shoulder line), and cap_up (the caps raised 0.04 L) still passes
  the sleeves at 0.90-0.94. face_shadow_chin_edge (look6's jaw measure) is calibrated; the chin IoU isn't (as look6 said).
- collar_back_lay reads 0.0141 WARN on the design itself: its design side is closed (pieceqa.clean, 0.012 L disk) and
  ours isn't, so the drawn shape's own notch counts. collar_back_iou can't fail the flagged build (0.754 WARN; the flag
  is carried by square and lay). For the collar's owner; no check was changed here.
- The guard's own noise: piece_bow's profile moves up to 11% with the design moved 2 px (0.865-0.972); the guard's 15%
  sits just above it. piece_collar's profile reads 0.09-0.12 on the design itself: the guard skips a view whose design
  reading is under 0.5 (calibrate.SHAPE_FLOOR).

## The gate (charkit/gate.py; the gate code comes from the `into` branch)

`calibration_step` runs after the compare (and the 2x2) when any check moved, reading the merged tree:
- **Records (item 2).** A graded check the merge adds needs `charkit/calib/records/CHECK.json`; a graded check it
  remeasures (a registered step's row, a 2x2 row, or a measure the gate found changed unregistered) needs a record the
  merge adds or changes (the same file as the integration head's is `stale`); a record whose verdict isn't
  calibrated or guard blocks too. One line each: `no calibration record: X (a new check; python -m charkit calibrate
  X)`, `the calibration record not refreshed: X`, `the calibration record says blind: X (...)`. INFO checks need none.
- **The anti-gaming guard (item 3).** `calibrate.guard`: a check the merge improves that is its own new check (the 2x2's
  new measure reads it better on the new geometry than the old; or new with no old-geometry reading and not FAIL) or a
  flag check (status better, or its value toward the design per its record's `better`), whose registry `shape` (else
  `piece_<first word>`) drops more than 15% in any view (`views` of piece_*); a view whose design reading (the shape
  check's own record) is under 0.5 is skipped. One block per check, its worst view named. Every moved check's pieces'
  shape per view is reported beside it ("the pieces' shape beside the checks that moved").
- **Acceptances (item 4).** `python -m charkit gate --accept-fail CHECK --by Michael --why TEXT [--branch B] [--value V]`
  writes `charkit/accepted/CHECK.json` (who, when, why, the branch; the coordinator commits it on the branch, on
  Michael's call; git keeps the history). A new FAIL or a guard block on that check is then reported under "Accepted by
  name" with who, when and why, not blocking. An acceptance naming another branch doesn't cover this one.
- Cost: the records and the registry are read in ~0.1-0.2 s (git cat-file for the head's side); the phase is
  `calibration` in the report's phases.
