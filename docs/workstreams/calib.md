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

## Done, validated, and next steps (stopped at the coordinator's call, 2026-09-30 evening)

Branch head: see `git log -1 tool/calib`. Items 1-5 are done. **tool/calib has NOT been gated into pipeline-3d yet.**

**Real-pair validation (box, `--code tool/calib` at 9b4f17b, into 3ebc3fb):**
- **A: tmp/calib-bow (= tool/bow cbca3ad): FAIL, as required.** Report
  `charkit/out/gate/gate_tmp-calib-bow_cbca3ad_into_3ebc3fb.md`. Blocks: the anti-gaming guard on bow_profile_ribbon
  (0.8684 FAIL -> 0.0789 PASS under the new measure on both geometries), bow_front_loop_end and bow_front_bleed, each
  while piece_bow's profile fell 0.553 -> 0.341 (-38%); plus no calibration record for the 9 collar_flags checks and
  collar_back_torn (remeasured). The old gate code passed this pair.
- **B: tmp/calib-bow-accept (59f5b7e = cbca3ad + the records + validation-only acceptances): FAIL, as intended.** Report
  `charkit/out/gate/gate_tmp-calib-bow-accept_59f5b7e_into_3ebc3fb.md`. The three accepted guard blocks show under
  "Accepted by name", with who, when and why. The records were read from the merged tree: collar_back_iou (blind)
  and collar_back_lay (miscalibrated) block on their verdicts, and collar_back_torn has no record.
- Both reports also block bow_front_loop_width through the guard ("new, with no old-geometry reading"). That came from
  9b4f17b's rule and was fixed at 3d66737: a 2x2 row reads it on both geometries (0.0 -> 0.002 PASS: not improved).
  The offline check agrees: `python charkit/out/calib/harness/bow_pair.py`.
- **Added gate time: the `calibration` phase took 0.0 s in both reports** (laptop: records 0.1 s via git, registry 0.12 s).
  It runs only when some check moved.
- The tmp branches `tmp/calib-bow` and `tmp/calib-bow-accept` are validation only. Never merge them; delete them when done.

**art_* records** (the Art adapter; defect detectors, no floor): 11 calibrated. art_speckle_neck is **blind** (look_v5
reads 2.178 WARN) and art_mirror_self_boots is **blind** (body4b_render 1.787 WARN; artifacts.md already called its
separation weak). art_peeks_hair is **unmeasured against the design**: it counts our pieces, and the drawing has none.
Records: charkit/calib/records (31 total). hair_truth_accuracy is calibrated as a score: the truth moved 1-2 px reads
0.930-0.971, the transfer masks 0.885, the floor 0.357, current 0.950. Past about 0.95 the score can't tell our masks
from the truth moved a pixel.

**Next steps (a fresh agent):**
1. `python -m charkit pregate`, then `python -m charkit remote gate tool/calib --into pipeline-3d` (export
   CLOUDSDK_CONFIG first). Merge pipeline-3d in first if it moved. Expect a candidate build (cli.py changed) and no
   check moving.
2. Registry entries and records for the checks the gate will ask about next: collar_back_torn and the other
   piece_details checks (their part reads our_section and alone(): check the Garments stand-in covers them first).
3. The review page: `python charkit/out/calib/harness/page.py` writes charkit/out/calib/review/index.html (the records'
   table and the stand-ins). Open it for Michael.
4. For the owners (no check changed here): collar_back_lay's design side is closed and ours isn't, so the design reads
   0.0141 WARN against itself. collar_back_iou can't fail its flagged build. The chin IoU, art_speckle_neck and
   art_mirror_self_boots are blind to their known-bads.

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
