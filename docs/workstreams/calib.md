# Calibration as a tool, the gate's calibration requirement and anti-gaming guard (tool/calib, 2026-09-30)

Worktree `~/animation-pipeline-infra3`, branch `tool/calib` from pipeline-3d 8b5ecae. The brief (Michael queued it):
several of today's defects passed their checks because a check was miscalibrated or too coarse (look5's chin,
hair_piece_bangs, piece_sleeve, bow_profile_ribbon). Items: (1) `python -m charkit calibrate CHECK`, the calibration
triple, records backfilled; (2) the gate requires a calibration record for a new or remeasured check; (3) the
anti-gaming guard; (4) recorded acceptance of a named new FAIL; (5) the process guide section in CHARKIT_HANDOFF.md.

## Round 2 (2026-09-30, late): the gate, piece_details records, the four WARN-on-known-bad flag checks

Brief: (1) gate tool/calib into pipeline-3d (pregate first); show the guard fix 3d66737 on a real gate; (2) records for
the piece_details checks (collar_back_torn included); (3) recalibrate collar_back_iou, art_speckle_neck,
art_mirror_self_boots and collar_back_lay's grading (its one-sided design smoothing is tool/collar4's) so each passes
on the design moved 1-2 px and fails its known-bad, the limit change registered as a remeasure; (4) delete
tmp/calib-bow and tmp/calib-bow-accept after use (never merge them).

Progress and results:
- **Gate 1: tool/calib edc786e into pipeline-3d 07fa3c2: PASS under K** (nothing blocks, 0 items reported; candidate
  built for cli.py, CPU 685.1 -> 683.4 s, 1.00x; 72 test files ok). Report
  `charkit/out/gate/gate_tool-calib_edc786e_into_07fa3c2.md`. pipeline-3d had moved to 07fa3c2 (tool/xpbd,
  charkit/sim only): merged at ec133ef; pregate PASS (0 moved, 316 s).
- **The guard fix on a real gate:** tmp/calib-bow into 3ebc3fb with `--code tool/calib` (edc786e) FAILed for another
  reason first: the 2x2's "new measure on the old geometry" couldn't load the cached baseline's bundle
  (`base_3ebc3fb_clawd_default/bundle/arrays.npz` missing on the box: an old cached baseline lost its arrays; the gate
  should rebuild or refuse such a reference, for the infra owner), so every bow check fell to "new, with no
  old-geometry reading". Report kept: charkit/out/calib/r2/gate_bowA_2x2fail.md. Re-run with `--build` (fresh builds):
  see below.
- **piece_details records (59):** charkit/calib/details.py (the Details adapter: Garments' stand-ins plus our_classes
  moved with the labels, alone() from the stand-in, our_section from sleeve_closeup; the band's drawn mask cut to its
  ink core with the rest the jacket's, as pieceqa reads the drawn band; the probe torn_edges bites every drawn piece's
  outline). labels.py's collar_flags patterns made explicit (they had swallowed collar_back_torn and the bow's
  piece_details checks). Known-bads: body6_render (round 6, reviewed by Michael: hull sleeves, the tucked jacket, hull
  cuffs and shorts), look_v5 (torn collar tips), g3_d (stored now: tool/garments3 18f3b41, the bow tails' torn lower
  edge), g3_render3 (the bow's tails). Floors: voronoi for shape and proportions, affine only where a place is
  measured, affine alone for a silhouette measure (voronoi keeps the silhouette).
  Verdicts: 30 calibrated, 19 blind, 7 miscalibrated, 2 unmeasured, 1 guard.
  - calibrated: the cuffs (8), the shorts' hems (4) and back width, the waistband's rows (front, three-quarter,
    profile), widths (front, three-quarter, back) and profile overhang, sleeve_back_profile_L/R, sleeve_front_spikes_R,
    collar_front_torn, bow_profile_torn, bow_front_tail_width, top_*_over_band, top_front_opening, top_front_hem_step.
  - collar_back_torn: **guard** (no build has ever read a torn back panel: look_v5, body6, g2_before, g3_render3,
    current all 0.0); the torn_edges probe reads 0.0053 WARN on it.
  - blind (the known-bad passes): the sleeves' rough (8: ours is closed by a 0.012 L disk before the roughness is
    read, so nothing under ~0.024 L can show; the torn_edges probe reads 0 on every one) and spikes but front_R (6:
    since cda2b7f only the cap's silhouette counts; the hull sleeves read 0 there), sleeve_front_profile_R,
    sleeve_profile_profile_L (the hull sleeves 0.027-0.031 WARN), shorts_front_width, bow_front_tail_gap,
    bow_front_torn, collar_three_quarter_torn, collar_profile_torn (look_v5 WARN).
  - miscalibrated (the design as ours fails its own check): sleeve_front_profile_L 0.0237 WARN and
    sleeve_three_quarter_profile_L 0.021 WARN, waistband_profile_width 0.068 WARN, waistband_back_rows 0.0235 WARN at
    a 2 px move (the design's side stops at the drawn outline stroke or the ink core, ours reaches the silhouette or
    the line's middle: about half a line, 0.01 L, on each edge); bow_three_quarter_torn (fragments: the design's side
    is closed, ours isn't), sleeve_three_quarter_spikes_R (count +1: the cuff's keep-away zone differs), bow_front_flare
    (the design as ours reads 0.53-0.59 FAIL; every build 0.99-1.0: the two sides measure different lobes). For
    pieceqa's owner.
  - unmeasured: sleeve_standoff_L/R (3D; no build has failed it, and a label image has no section to randomise).
    New verdict rule (calibrate.verdict): no known-bad and no floor is unmeasured, not guard.
- **The four flag checks (item 3).** Rule: limits at the thirds of the gap between the design's worst reading (the
  jitter probes included) and the known-bad. Registered as remeasures (charkit/steps/collarqa.py, artifactqa.py).
  | check | old | new | design worst | known-bad | current (old -> new) |
  |---|---|---|---|---|---|
  | collar_back_iou (higher) | 0.80 / 0.65 | 0.87 / 0.81 | 0.9252 (2 px down) | g3_render3 0.7537 WARN -> FAIL | 0.7473 WARN -> FAIL |
  | collar_back_lay | 0.01 / 0.02 | 0.025 / 0.036 | 0.0141 (every move) | g3_render3 0.0471 FAIL | 0.0424 FAIL -> FAIL |
  | art_mirror_self_boots | 1.5 / 2.5 | 1.37 / 1.58 | 1.163 (one boot 2 px up; whole-sheet 1.0) | body4b 1.787 WARN -> FAIL | 0.5 PASS |
  | art_speckle_neck | 1.5 / 2.5 | unchanged | 1.004 whole-pixel; **4.97** half a pixel | look_v5 2.178 WARN | 0.833 PASS |
  Margins: iou design 0.055 above PASS, known-bad 0.056 under the FAIL line; lay 0.011 / 0.011; mirror_self 0.207 /
  0.207. The current build's collar_back_iou goes WARN -> FAIL (its flag is open: square 0.345 and lay 0.0424 FAIL
  already); nothing else on it changes status.
  - collar_back_lay's design reads 0.0141 only because its design side is closed (pieceqa.clean) and ours isn't:
    tool/collar4's to fix (not messaged); once fixed, recalibrate (the design should read ~0 and the limits tighten).
  - art_speckle_neck **can't be calibrated as measured**: whole-pixel moves are invisible to a speck count (1.000-1.004),
    but the head sheet resampled a quarter pixel down reads 2.41, half a pixel 4.97 (front 32.7 -> 155 specks per L^2),
    across (0.5 px) 1.26 (harness: charkit/out/calib/r2/art_subpx.py; probe head_subpx in its record). The design's
    own reading (the ratio's denominator) depends on the sheet's arbitrary resampling phase by up to 5x, and look_v5's
    2.18 lies inside it. Missing: the seam's structure. Proposed fix (artifactqa's owner): read the design's specks as
    the median over 4 half-pixel phases (a stable denominator), and measure the flag itself as specks in runs along a
    row or column (the dotted seam), not specks per L^2; then recalibrate on look_v5. Limits left at 1.5 / 2.5 (its
    record says blind).
  - art_mirror_self_boots' whole-sheet moves read exactly 1.0 (translation invariant); the probe boot_nudge (one
    boot's masks 2 px up) reads 1.163, per-boot moves 1.005-1.163 (charkit/out/calib/r2/art_jitter.py).
- Review page: `charkit/out/calib/review2/index.html` (python charkit/out/calib/harness/page2.py).
- Commits: 9d5f649 (records, adapters, limits), 66eb6df (the steps for the three limit changes), bc85e5d (pipeline-3d
  eb7ac94 merged: tool/hairlocks; cli.py's conflict kept both commands), e7268c4 (gate.py: the 2x2's mirror fix below;
  66eb6df's cached-baseline check reverted, a wrong diagnosis). Pregate on bc85e5d: PASS (0 moved).
- **Final gate: tool/calib e7268c4 into pipeline-3d eb7ac94: PASS under K** (nothing blocks; 3 items reported:
  collar_back_iou remeasured 0.7473 WARN -> FAIL, the measure alone, geometry unchanged; the artifacts and collar_flags
  parts listed as measuring code changed (LIMITS, SHAPE_CHECKS: codediff is per part, the steps cover the checks; no
  unregistered check moved); CPU 614.2 -> 624.1 s (1.02x); 73 test files ok). Report
  `charkit/out/gate/gate_tool-calib_e7268c4_into_eb7ac94.md`. (e999b94, before the gate.py fix, PASSed the same way.)
- **The guard fix on a real gate: shown.** tmp/calib-bow (cbca3ad) into 3ebc3fb with `--code tool/calib` (e7268c4):
  FAIL as required, 13 blocks: 10 records missing in tool/bow's tree, and the guard on bow_front_bleed, loop_end and
  profile_ribbon (piece_bow's profile 0.553 -> 0.341, -38%). **bow_front_loop_width no longer blocks**: its 2x2 row
  reads 0.0 PASS on the old geometry, 0.002 PASS on the new (value, not improved). Copy:
  charkit/out/calib/r2/gate_bowA4_e7268c4.md. Getting there took the gate fix: re-gates of the same pair failed the
  2x2 ("new measure on the old geometry": arrays.npz not found) because the candidate folder's mirror of the moved
  baseline (rebased_bundle) kept links through the first gate's clone (`charkit/out/gate` is a per-clone link to
  gate-out), gone with it; the mirror now links real paths and repoints stale links (test_gate
  test_a_crossed_qa_mirror_outlives_the_gate_that_made_it). Any workstream's re-gate of an identical pair was exposed.
- tmp/calib-bow and tmp/calib-bow-accept deleted (never merged).

**Next steps (a fresh agent):**
1. The anti-gaming guard should ignore pieces barely visible in a view (coordinator, from tool/sleeves: piece_collar's
   profile IoU 0.053 -> 0.026 trips the 15% rule as noise). Today calibrate.guard skips a view only when the shape
   check's own record says the design reads under SHAPE_FLOOR 0.5 there, and needs the base value over 0.05; a piece
   without a record, or one at 0.053, isn't covered. Proposed visibility floor, independent of records: skip a view
   where the piece's drawn mask shows under a share of its largest view (e.g. 25%, as pieceqa.HIDDEN's 0.4 does for the
   sleeves) or under ~300 px on the sheet grid, and raise the base-IoU floor from 0.05 to ~0.2 (an IoU that low is
   noise for a relative drop); report the skipped views beside the guard's findings. Test on tool/sleeves' pair and
   keep tool/bow's profile block (0.553, well visible).
2. For pieceqa's owner (records say miscalibrated): the design-side/our-side asymmetries listed above (sleeve profile,
   waistband profile width and back rows: half a line at each edge; bow_three_quarter_torn: one side closed;
   sleeve_three_quarter_spikes_R: the count; bow_front_flare: the two sides measure different lobes).
3. For artifactqa's owner: art_speckle_neck's phase-stable design reading and a seam (runs) measure, then recalibrate on
   look_v5 (limits left 1.5 / 2.5). art_mirror_self_boots is calibrated but capped at WARN until promoted
   (artifactqa.PROMOTED: the integrator's call).
4. For tool/collar4: collar_back_lay's one-sided design smoothing; then recalibrate its limits (tighter).
5. tool/bow's step pattern `collar_back_*` swallows piece_details' collar_back_torn (the gate then asks for its record
   to be refreshed): narrow it to its own checks.
6. The review page: `open charkit/out/calib/review2/index.html`.

## State (read first when resuming)

- Code: `charkit/calibrate.py` (engine, store, records, CLI, the gate's readings), `charkit/calib/` (the registry
  literals and adapters: labels.py (collar_flags, sheet_pieces, hair_pieces), chin.py, hairtruth.py; records/;
  known_bad/), gate.py (calibration_step, judge, report, `--accept-fail`), cli.py (`calibrate`),
  charkit/tests/test_calibrate.py.
- The current build for calibrations: `charkit/out/calib/cur_8b5ecae` (box build of pipeline-3d 8b5ecae, default spec).
- The known-bad store (local, hard links, gitignored): `charkit/out/calib/builds/{g3_render3,co_render,hl_base,
  look5_before}`; what each is: `charkit/calib/known_bad/NAME.json`.

## Done, validated, and next steps (stopped at the coordinator's call, 2026-09-30 evening)

Branch head: see `git log -1 tool/calib`. Items 1-5 are done. Round 2: gated PASS into pipeline-3d eb7ac94 at e7268c4
(see "Round 2" above).

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

**art_* records** (the Art adapter; defect detectors, no floor): 11 calibrated (round 2: art_mirror_self_boots
recalibrated, 12). art_speckle_neck is **blind** (look_v5 reads 2.178 WARN; round 2: not calibratable as measured). art_peeks_hair is **unmeasured against the design**: it counts our pieces, and the drawing has none.
Records: charkit/calib/records (31 total; 90 after round 2). hair_truth_accuracy is calibrated as a score: the truth moved 1-2 px reads
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
