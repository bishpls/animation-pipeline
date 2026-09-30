# Hull limbs: each limb takes its own depth (tool/hull-limbs)

Branch `tool/hull-limbs`, worktree `~/animation-pipeline-hulllimbs`. It merges tool/hull-det 3267aea, then
tool/garment-sampling 47b401f, then pipeline-3d 2e3bdd5. tool/body round 6 merges the first two; this branch goes on top.

## Round 5 (2026-09-30): read first

**Head** `tool/hull-limbs` cddbd12. It merges pipeline-3d e11fadb (72c98f2: hair round 3). The coordinator gave this
workstream `body_profile_leg_back` in detailqa.py for the round, since tool/body is inactive.
- **2479a22:** `body_profile_leg_back` reads **the bare leg**.
  - Our skin alone: `detailqa.bare_skin`, the skin's `eval` variant with no garments' mask, z-buffered on the design's
    profile grid (`our_views`' `bare`).
  - It is read over the design's leg rows only: `leg_rows`, the longest run of rows, which leaves out the design's hand
    above the shorts.
  - It keeps the design's facing and LEG_EDGE (1fd1c63).
- **`body_profile_leg_outline` (INFO), for tool/skirt:**
  - It follows the leg's skin run back through whatever touches it in the dressed profile, and compares that outline
    with the design's, the bare leg's offset taken out.
  - `hugging` counts the rows where something runs more than 0.02 L past the leg's skin.
- **cddbd12:** both steps registered in `history.STEPS`.
- **Tests:** the design's hand is left out; the bare leg sees a bump a flap hides, while the dressed leg can't; the
  outline sees a flap hugging the thigh and reads 0 on a clear one.
- **Calibration** (the evaluator on the real sheet; scratchpad `hl3/calib.py`):

  | | body_profile_leg_back | body_profile_leg_outline |
  |---|---|---|
  | the design against itself | **0.0000 PASS** | 0.0 (3 rows hugging) |
  | pipeline-3d db718ae (the thigh fitted to the slab) | **0.1083 FAIL at -2.797** | 0.570 (82 rows) |
  | this branch | **0.0188 PASS at -3.898** | 0.574 (82 rows) |

  e11fadb changes only the hair. On a real Blender bundle (`hl3_box_after`) the bare profile renders 138,847 skin px
  against 36,881 dressed.

**Gates of cddbd12 into pipeline-3d e11fadb:**
- **Default spec: PASS.**
  - `body_profile_leg_back` 0.2071 FAIL → **0.0188 PASS** (remeasured: the bare leg; the evaluator's number exactly).
  - `body_profile_leg_outline` new, 0.5742 INFO.
  - `piece_collar` 0.745 WARN → 0.754 PASS.
  - `body_back_leg` 0.0565 → 0.0001; `body_front_leg` 0.0612 → 0.0001.
  - **`hair_folds` 4 → 6 WARN**, combined with hair round 3: side_lock_L 1 → 2, lower_back 0 → 1.
  - `hair_penetration` is 0.0124 FAIL (upper_back) in both, the baseline's own.
- **clawd_mh: FAIL** on `hair_penetration` 0.0015 PASS → **0.0484 FAIL** (lower_back, 47 vertices) and
  `body_three_quarter_skirt_aline` 0.026 → 0.078 WARN (round 4, below).
  - The coordinator accepts the hair_penetration FAIL for this merge: the hair's clearance leaned on the wrong
    shoulder slab, and tool/hair4 takes it.
  - `hair_folds` 4 → **11 WARN** (bangs 3 → 7, side_lock_L 0 → 1, lower_back 0 → 2).
  - `body_profile_leg_back` 0.2024 FAIL → 0.0329 WARN, the MakeHuman leg bare. `body_profile_leg_outline` reads 0.0094
    INFO: clawd_mh's flaps don't touch the leg.
- **Why hair_folds moves: the hair reads the decimated mesh.** The hull above the eye line is voxel-identical to
  pipeline-3d's (0 of 708,699 occupied voxels differ; 518 between the eye line and z -0.45). Its decimated mesh isn't:
  13,469 against 13,531 vertices there, 13,408 shared. The limb carve changes the volume below, and the greedy
  decimation then takes another path everywhere. The hair builder places the bangs and locks from those vertices, which
  HULL_CONTRACT.md says not to rely on (tool/hair4: read the shell, or the hull's `V`).
- The hull's code (hull.py, det.py, remesh.py, volume.py, code_base.py) is unchanged since 529d2bc, so round 4's stage
  hashes hold.

**Kept at the coordinator's call:** the shorts' `hem_drop` line (the duplicate with garments2 is resolved at the
second merge), and the `history.STEPS` entries (migrated at merge if tool/infra's self-registering steps land first).

**Review page:** `charkit/out/hl4/review/index.html` (scratchpad `hl3/mkpage4.py cddbd12`).

## Round 4 (2026-09-30)

**Head** `tool/hull-limbs` 529d2bc. It merges pipeline-3d db718ae (751bddf). The gates merged it into pipeline-3d
9397578, which adds docs only. The commits this round:
- 227616e: `history.STEPS` registers body_profile_leg_back's measurement step, 1fd1c63;
- 529d2bc: `docs/HULL_CONTRACT.md`, and the sidecar's `contract` (hull.CONTRACT 1, `hull.sidecar`, `hull.contract_of`),
  with a test.

The full suite passes: 39 files, local.

**Gates of 529d2bc into pipeline-3d 9397578:**
- **Default spec: PASS.**
  - `body_profile_leg_back` 0.2071 FAIL → 0.0235 PASS (remeasured).
  - `body_back_leg` 0.0565 → 0.0001 PASS.
  - `piece_collar` 0.740 → 0.749 WARN.
  - `hair_folds` 6 → 10 WARN, value only: side_lock_L 2 → 4, side_lock_R 0 → 1, lower_back 0 → 1; the flyaways stay 0.
  - `body_profile_iou_skin` WARN → PASS.
  - Skin and outfit IoU are up in all four views; no check changed grade for the worse.
- **clawd_mh: FAIL** on two checks.
  - `hair_penetration` 0.0007 PASS → 0.0484 FAIL.
    - It is the one attributed before (below): the `lower_back` hair sits 0.048 L into the MakeHuman skin at the
      shoulder's top, x 0.32..0.40, z -0.57..-0.59.
    - The MakeHuman shoulder stands outside the design's hull there. The hull's shoulder lost the arm's
      whole-side-run slab, which the smoothing had spread over it.
    - The authored body (default spec) doesn't collide. This is for the hair's clearance against the body
      (tool/hair3), or for clawd_mh's body.
  - `body_three_quarter_skirt_aline` 0.026 PASS → 0.078 WARN.
    - The evaluator reproduces 0.078. clawd_mh's skirt with the default spec's settings (aline, symmetric, hem_cut,
      midline axis) reads 0.088, so those settings don't explain it.
    - The check reads 12-13 rows at the skirt's hem, because the MakeHuman hands cover every other row in the
      three-quarter. The design's value is over all its rows (every design row has a hand against it).
    - Ours moves with one row, z -2.49: 1.845 L wide on pipeline-3d, 1.70 here. There the old skirt was fuller at the
      back, the flap train's slab.
    - The ratio went 0.936 → 0.988 against the design's 0.910. The default spec's value is unchanged. This is for
      tool/skirt (the skirt's back and the flaps) and the check's row choice.
  - Otherwise: `hair_folds` 5 → 6 WARN, `piece_collar` 0.60 → 0.61 WARN, `body_profile_leg_back` 0.2024 FAIL → 0.0188
    PASS (remeasured), `body_front_skirt_overhang_mirror` WARN → PASS.

Reports are in `charkit/out/gate/gate_tool-hull-limbs_529d2bc_into_9397578[_clawd_mh].md`.

**Determinism at 529d2bc:** 44 of 46 arrays are bit-identical on the build box, the render box and the laptop. That
includes all six outputs:
- hull.npz `42a8586a`;
- hull_pieces `37c28ecd`;
- hull_labels `3b91045d`;
- hull.ply `ef3f76e2`;
- hull.glb `90c4f2bd`;
- hull.glb.json `9a54eeae`.

Only `head_sections` (cy, r) differ, as before: `code_base`'s, and it doesn't reach the outputs. The runs are in
`charkit/out/hl4_stages_{build,render,laptop}`.

**The leg: what the check can and can't see (the 2×2, evaluator = box).**
The evaluator reads the same numbers as the box gate: pipeline-3d 0.2071, this branch 0.0235.

| measure | pipeline-3d db718ae | this branch |
|---|---|---|
| body_profile_leg_back dressed, as pipeline-3d codes it (every row) | 0.2071 FAIL at -3.922 | 0.2118 FAIL at -3.922 |
| body_profile_leg_back dressed, as 1fd1c63 codes it (leg ends' rows out) | 0.0188 PASS at -3.898 | 0.0235 PASS at -3.898 |
| **the bare leg** (the body alone against the design's drawn skin) | **0.1083 FAIL at -2.797** | **0.0188 PASS at -3.898** |

- **The fix is real, and only the bare leg shows it.**
  - The body's thigh on pipeline-3d stands 0.108 L behind the design's at z -2.80. It was fitted to the slab.
    code_body's leg rings reach y 0.418 at -2.79, against this branch's 0.321.
  - Here it tracks the design's edge within 0.005 L down to the knee.
  - The design, measured against itself, reads 0.
- **The dressed check can't see the thigh on either tree.** The overskirt flaps (`source: flap`, refitted in 3d0d5f2:
  `out` -0.3, `sweep` 0.364) hang against the back of the thigh on 82 of 114 rows from z -2.76 to -3.3. The design's
  hang 0.55-1.0 L behind the thigh's back (median 0.75), with nothing touching it. The figure's outline behind the thigh
  reaches up to 0.57 L past the design's on both trees.
  - So on pipeline-3d the flap hides the thigh's bump, and the dressed check passes there too once the boot cuff's
    rows are left out. Its PASS in the gate is the remeasure, not the fix.
  - The flaps are tool/skirt's, not the hull's: the two trees' skirt and flap shells match.
  - **The protrusion Michael sees in a dressed profile is now that flap.**
- **For detailqa's owner:**
  - Read `body_profile_leg_back` on the bare leg, the skin's unmasked variant (scratchpad `bareleg.py` +
    `barecheck.py`).
  - Add an outline check behind the leg that sees a garment hugging it (`outline.py`).
- **For tool/skirt:** the flaps' tail should hang clear of the legs as drawn.

**Outside this workstream's areas** (docs/OWNERSHIP.md, published after they were made), to confirm with the owners at
merge:
- detailqa.py's `leg_back_check`, 1fd1c63 (body's);
- the `history.STEPS` entry (shared);
- the shorts' `hem_drop` 0.03 in clawd, clawd_body and clawd_body_pieces, 56b480a (garments2's).
  - tool/garments2 carries the identical `hem_drop` 0.03 on the shorts, at another line with `hem_level` and
    `hem_snap`.
  - Merging both gives the shorts two `hem_drop` keys; json keeps the last, and the values are equal. Drop this
    branch's line at the second merge.
  - Without it, body_back_leg goes back to WARN: the seat shows through the leg gap.

**Review page:** `charkit/out/hl4/review/index.html`. It has the leg in profile beside the design (bare and dressed,
before and after), the 2×2, the Limbs diagnostic before and after (pipeline-3d against this branch), the gates and the
stage hashes. The generator and the measurements are in the scratchpad (`hl3/mkpage4.py`, `bareleg.py`, `barecheck.py`,
`checkall.py`, `outline.py`).

The throwaway worktrees `~/animation-pipeline-hlpin` and `~/animation-pipeline-hlbody` are removed; their branches (tmp/hull-limbs-pin, tmp/hull-limbs-on-body) are kept, never to merge. `~/animation-pipeline-hlbase` (the before, 2111d12) stays.

**Open items:**
- The dressed protrusion is the flaps (tool/skirt), and the leg check reads the dressed figure (body/integrator).
  Details above.
- `hair_folds` +4 on the side locks and lower back, still WARN. The hair builder reads the hull's decimated hair-mass
  vertices, which HULL_CONTRACT.md lists as "may not rely on"; tool/hair3.
- clawd_mh's gate FAILs on `hair_penetration` and `body_three_quarter_skirt_aline` (above): both come from the hull losing
  a wrong slab that downstream fits had leaned on. Their fixes are the hair's and the skirt's.

## Round 3 state (2026-09-30, relaunch)

**Latest (after pipeline-3d b8097cf, tool/body round 6 with hull-det and garment-sampling).** Merged at 4815115. The
round-6 merge fixed the hem regressions that were hull-det's and garment-sampling's. This branch's own three, fixed:
- `hair_folds` and `piece_collar` (5d618ee): `refine` fits the oblique views' axes against the silhouettes' hull without
  the limb split. The three-quarter's offsets tie within 1e-4 of IoU half a voxel apart, so the limb carve had flipped
  it +0.040 → +0.035 L. The whole carve moved a pixel, and the hair's flyaways turned (see below). Without the split it
  is +0.040 in both trees; box builds with the axis at +0.040 give hair_folds 9 (default) and 7 (clawd_mh), the
  three-quarter hair width 0.956 and piece_collar 0.755.
- `body_back_leg` (56b480a): the shorts' hem 0.03 L lower (`hem_drop` in clawd, clawd_body, clawd_body_pieces).
  Without the slab's `shorts` labels the hull-labelled hem sits 0.03 L high at the back. The body's subdivided seat
  showed through the gap the design draws between the legs from z -2.63. Evaluator: 0.0848 WARN → 0.0001 PASS,
  body_front_leg 0.038 → 0.000, dark IoU up in all four views, no check worse. code_body.CROTCH 0.11 changes nothing.
- `body_profile_leg_back` (1fd1c63, detailqa): both figures read on the design's facing (face_side misread ours: offset
  -5.26 L, the front edge), and the rows within 0.02 L (LEG_EDGE) of either figure's leg ends left out. The design's
  sloped boot-cuff line cut its last two rows short: 0.13-0.21 L on every build, the "0.207 FAIL" of round 6's build.
  The thigh bump still reads: before 0.108 FAIL at -2.806, LimbTrack alone 0.061 FAIL, after 0.014 PASS (box),
  0.019 PASS (b8097cf + this branch, evaluator).

## Paused (2026-09-30, usage limit): done in round 4 (above)

- **Head** `tool/hull-limbs` 39da743: pipeline-3d 53a557f merged (tool/face's carve_face hair margin, tool/eyes2). It
  merged cleanly, `clawd_body_pieces.json` still equals `clawd.json` (test_spec_alias ok) and all three authored specs
  keep the shorts' `hem_drop` 0.03. The full test suite passed at 56b480a; it hasn't been rerun after this merge.
- **Box jobs possibly still running at the pause** (their results are superseded by the 53a557f merge):
  - gates of 56b480a into b8097cf, default and clawd_mh. Local logs: `charkit/out/hl3_gate2_{default,mh}.log`;
    reports into `charkit/out/gate/`.
  - the build box's stage-hash run at 56b480a (`charkit/out/hl3_stages_build2`). The render box
    (`hl3_stages_render2`) and laptop (`hl3_stages_laptop2`) runs at 56b480a are done. Compare with the scratchpad's
    `stagecmp.py`, or diff the three `stages.json`.
- **Next, in order:**
  1. Run the whole suite; then gate the head into pipeline-3d 53a557f on both specs
     (`python -m charkit remote gate tool/hull-limbs --into pipeline-3d [--spec charkit/spec/clawd_mh.json]`).
     Expected from this branch: hair_folds, piece_collar and body_back_leg back at the baseline's. The default spec's
     body_profile_leg_back should PASS (0.014-0.019 on the evaluator and box). clawd_mh may still show hair_penetration
     (the MakeHuman shoulder, above) and body_three_quarter_skirt_aline 0.078 WARN; neither is the refine axis's.
  2. Stage hashes at the final head on the build box, render box and laptop
     (`python -m charkit.geom hull charkit/spec/clawd.json --fast --stages DIR`). carve_face changed, so the face stages
     move.
  3. Regenerate the review page `charkit/out/hl3/review/index.html` (scratchpad `hl3/mkpage3.py`) with the new gates,
     and `open` it.
  4. Remove the throwaway worktrees `~/animation-pipeline-hlpin` (tmp/hull-limbs-pin: the refine axis pinned, never
     merge) and `~/animation-pipeline-hlbody` (tmp/hull-limbs-on-body: this branch on tool/body 25d8d48).

**Why relaunched.** Michael saw a protrusion at the back of the leg in profile. tool/body traced it to the hull: at
z -2.72 to -2.76 L the hull labels skin all along the profile's side run behind the leg, where the flap train hangs, and
code_body's thigh fit bulged back to it. The thigh's back edge sat 0.07-0.11 L behind the design's from z -2.74 to
-2.91 (0.113 at -2.80). tool/body added `body_profile_leg_back` (tool/body 854776f, `detailqa.py`).

**The before.** `~/animation-pipeline-hlbase` on `tmp/hull-limbs-base` = 2111d12: 47b401f (garment-sampling on hull-det
3267aea) with pipeline-3d merged, i.e. this branch's bases without its commits. `git diff tmp/hull-limbs-base
tool/hull-limbs` touches only hull.py, test_hull.py and this file. Both worktrees have the TRELLIS field
(`charkit/out/i3d/ext/runA/clawd_3dstyle_s1_field.npz`) and outfit masks `074d9a3f`.

**The cause was not the LimbTrack.** The LimbTrack had already kept the thighs' own parts on their skin (z -2.73: y
0.26..0.32; from -2.76: the thigh's whole skin run). The slab came from the *body* parts at the same heights:
- The profile shows the flap train as a side run of its own behind the hips (y 0.84 to 1.22 from z -2.56 down).
- Every body part took every side run over its whole width. That includes the skirt and shorts spanning the hips
  (-2.56 to -2.71) and the shorts' hem over the thighs (-2.72 to -2.75).
- So a slab stood behind the thighs' columns down to the shorts' hem, with a flat floor there. Front and back both draw
  the flap panels only at |x| 0.47 to 1.07 L.
- No view sees the floor's underside, so `label_volume` gave it the nearest seen label: the thighs' skin, 136
  skin-labelled shell voxels behind the thighs (|x| < 0.55, y > 0.36). The smoothing (0.09 L in z) rounds it into the
  point code_body fitted.

**The fix (`Owners`, in `sections()`, 8e74059).** The widest side run at a height is the body and pairs with every body
part. A run detached from it, made of the body's pieces (at most 5% skin, hair, iris or a limb's pieces), goes only to
the columns where a view shows those pieces (a piece or its mirror partner, one section per piece):
- a run behind the body is read on the back view, which sees it whole;
- a run in front of the body is read on the front view;
- where that view doesn't show the pieces at this height, every part keeps the run, as before;
- a part left with no run keeps all of them.

On Clawd this changes the flap train from z -2.56 to -3.15, the skirt panel's flared hem in front (-2.60 to -2.62, from
the whole width to |x| < 0.34) and the bow at -0.63 (one column). The Limbs diagnostic's depth map shows these runs in
violet. 05f1c1f adds each view's limb image and a sections table to the build's `--stages`.

Variants measured and rejected (the laptop, Clawd's sheet, validated as the page does):

| hull | skin shell voxels behind the thighs | voxels behind the thighs | held out 3/4 | held out back | used front |
|---|---|---|---|---|---|
| before (2111d12) | 423 | 64,136 | 0.8764 | 0.9469 | 0.9608 |
| LimbTrack only (b6f122a) | 136 | 63,461 | 0.8784 | 0.9467 | 0.9612 |
| **Owners (8e74059)** | **0** | **16,164** | **0.8777** | **0.9476** | **0.9605** |
| drop a run only where the part shows none of its pieces | 25 | 57,459 | 0.8785 | 0.9467 | 0.9612 |
| body parts also drop a run that is one limb's | 143 | 63,462 | 0.8679 | 0.9334 | 0.9461 |
| every piece run to the front's columns, plus that | 0 | 15,748 | 0.8613 | 0.9322 | 0.9435 |

- Reading a rear run's columns on the front view loses the flaps' inner halves, which the hips hide from the front. On a
  synthetic flapped figure (test_hull), held-out three-quarter IoU: whole width 0.838, front's columns 0.822, back's
  columns 0.842.
- Dropping the thigh's run from the flap parts empties the front silhouette where the three-quarter carves the flap
  ellipses alone (1,238 px).

**The thigh's back edge in profile** (tool/body's `leg_back`, copied verbatim into the scratchpad): L behind the
design's, the median offset over the leg taken out.

| | before | LimbTrack only | after (Owners) | after on tool/body 25d8d48 |
|---|---|---|---|---|
| evaluator, thigh and knee (z >= -3.5) | 0.108 at -2.81 | 0.061 at -2.80 | **0.005** | **0.005** |
| evaluator, check as coded | 0.202 at -3.922 | 0.132 at -3.917 | 0.132 at -3.917 | 0.132 at -3.917 |
| box build, thigh and knee | 0.108 at -2.81 | | **0.005** | |
| box build, check as coded | 0.202 at -3.922 | | 0.132 at -3.917 | |

- The check as coded peaks on the two rows above the boot cuff (-3.913, -3.917). There the design's sloped cuff line cuts
  its skin row short at the back, while our cuff top is level. That is the boot's (tool/body), and the same before and
  after.
- `leg_back`'s face-direction test flipped on the before evaluator build (ours +1): its as-coded value there (0.099 at
  -2.745) is the front edge's. The table measures every build with the design's direction.
- tool/body: skip the rows within about 0.02 L of either figure's cuff, or require a bump to hold over 0.02 L. Take the
  face direction from the design.

**Per-height borrowing, the real masks** (front limb parts x height against the hand-made profile truth; the truth's
puff now starts at its drawn top under the collar, z -0.57, not -0.70):

| | arm before | arm after | leg before | leg after |
|---|---|---|---|---|
| parts | 440 | 431 | 556 | 531 |
| borrowing | 40 | 10 | 3 | 2 |
| foreign / own cells | 2,350 / 11,992 | 104 / 10,096 | 106 / 22,252 | 8 / 21,884 |
| whole side run | 22 | 0 | 4 | 0 |

- Before: the shoulder (z -0.50 to -0.56, the neck's skin and the collar, the whole side run at -0.52/-0.53), the wrist
  cuff (-1.98 to -2.06: the whole side run, 102-113 skirt cells each), and the right thigh's top (-2.72: the whole side
  run, the flap train included, 96 cells).
- After: z -0.54 to -0.56 (6 parts, 6-11 cells: the sleeve's piece run where the collar covers the shoulder's top), and
  2-3 outline cells at -1.36, -2.49 (arm) and -2.73 (the thigh at the shorts' hem).
- The leg rows never saw the slab: it was the body parts'.

**Determinism** (hull-det's `--stages`, `python -m charkit.geom hull charkit/spec/clawd.json --fast --stages DIR`, at
05f1c1f). Machines: the build box (Xeon, AVX-512), the render box (Xeon, AVX2) and the laptop (arm64).
- 44 of 46 arrays are bit-identical on all three: every hull stage and every output. That includes the new stages (each
  view's limb image, the sections table with its sources, rejected runs and Owners' changes, `rounded`'s V).
  hull.npz is `5f9ceff5…` and hull_pieces.npy `90945005…` everywhere.
- Only `head_sections` (cy, r) differ, three ways for r. That is `code_base.head_sections`, the authored head's
  analytic sections, not hull.py. It doesn't reach `face_carved` or anything after it here, but it is a latent
  cross-machine risk for code_base's owner (tool/face) and hull-det.
- Owners uses only integer image operations and IEEE comparisons (np.isin, flatnonzero, min/max of columns). The widest
  run's tie goes to the lowest y.

**Box builds of charkit/spec/clawd.json, before (2111d12) → after (8e74059)**, QA 105/23/9 → 105/25/7 (PASS/WARN/FAIL):
- Better: `body_front_hem` 0.165 FAIL → 0.113 WARN; `body_three_quarter_hem` 0.174 FAIL → 0.137 WARN; `piece_shorts`
  0.403 FAIL → 0.679 WARN; `body_three_quarter_iou_skin` 0.695 WARN → 0.700 PASS; `piece_overskirt_panel_R_extent`
  0.137 WARN → 0.080 PASS; `body_back_hem_mid` 0.231 → 0.174 (FAIL); `body_back_hem` 0.151 → 0.099 (WARN);
  `shape_iou_legs` 0.896 → 0.915.
- Worse:
  - `hair_folds` 9 WARN → 47 FAIL, all on the flyaways (0 → 41). The limb carve moves the three-quarter's refined axis
    one pixel (+0.040 → +0.035 L), because `refine` fits it against the rounded hull. The whole carve shifts by that
    much, the head included (2,708 voxels above the eye line). `hairpieces.flyaways` sets each blade's plane to the
    median y of the 24 nearest hull hair-mass vertices, which split between the mass's front and back. (Checked: with
    the after code and the three-quarter's axis pinned at the before's +0.040, the hull above the eye line is identical
    to the before's, 0 voxels.) So the planes
    jump (lock 2: 0.108 → 0.040, lock 3: 0.060 → 0.000, lock 4: 0.010 → 0.060 world), and the blades turn against the
    envelope's normal. That fragility is the hair builder's (tool/hair): take the mid-plane as the midpoint of the
    mass's front and back at the root. This is the "hair_folds 7 → 47" of the paused gate: it was this branch's (the
    LimbTrack), not hull-det's.
  - `body_back_leg` 0.075 PASS → 0.118 WARN: a lens of skin shows through the shorts' back at the seat in the back view,
    and `leg_top` reads it as the legs' top. Before, the back view labelled the slab's rear face `shorts`, and the
    shorts' back was sampled there (garment-sampling). Now it is sampled at the hull's true back, level with
    code_body's hips. That clearance is the garments' and body's (tool/body).
  - `piece_collar` 0.753 PASS → 0.736 WARN.
  - `hair_penetration` 0.0148 FAIL is the same in both (not this branch's).

**Gates of 05f1c1f into pipeline-3d 2e3bdd5: FAIL on both specs.** To split the causes, the before (2111d12: hull-det +
garment-sampling without this branch) was gated into the same commit, so both share one baseline build.
Reports: `charkit/out/gate/gate_tool-hull-limbs_05f1c1f_into_2e3bdd5[_clawd_mh].md` and
`gate_tmp-hull-limbs-base_2111d12_into_2e3bdd5[_clawd_mh].md`.

Default spec (baseline → before → this branch):
- hull-det / garment-sampling (regressed in the before gate too; this branch reduces them):
  - `body_front_hem` 0.047 PASS → 0.165 FAIL → 0.113 WARN;
  - `body_three_quarter_hem` 0.080 PASS → 0.174 FAIL → 0.137 WARN;
  - `body_back_hem` 0.033 PASS → 0.151 WARN → 0.099 WARN;
  - `body_back_hem_mid` 0.136 WARN → 0.231 FAIL → 0.174 FAIL;
  - `piece_overskirt_panel_L_extent` 0.042 PASS → 0.141 WARN → 0.099 WARN;
  - `piece_overskirt_panel_R_extent` 0.057 PASS → 0.137 WARN → 0.080 PASS (fixed here).
- This branch:
  - `hair_folds` 9 WARN → 9 → 47 FAIL (the flyaways, via the refine axis, above);
  - `body_back_leg` 0.066 PASS → 0.075 PASS → 0.118 WARN (skin through the shorts' seat, above);
  - `piece_collar` 0.770 PASS → 0.753 PASS → 0.736 WARN.
- Improved by this branch: `piece_shorts` 0.426 FAIL → 0.403 → 0.679 WARN; `body_three_quarter_iou_skin` → PASS.

clawd_mh (baseline → before → this branch):
- hull-det / garment-sampling: `body_back_skirt_width` 0.941 PASS → 0.866 WARN → 0.872 WARN;
  `body_front_skirt_aline` -0.040 PASS → -0.055 WARN → -0.053 WARN.
- This branch:
  - `hair_folds` 7 WARN → 8 → 47 FAIL;
  - `hair_penetration` 0.0009 PASS → 0.0007 → 0.0476 FAIL;
  - `body_three_quarter_hair_width` 0.956 PASS → 0.956 → 0.896 WARN;
  - `body_three_quarter_skirt_aline` 0.043 PASS → 0.026 → 0.078 WARN.
  These are exactly the paused gate's values (a9a84a8): they were never hull-det's edge-mode bug.
- Improved: `piece_waistband` 0.366 FAIL → 0.499 FAIL → 0.502 WARN.

Attribution builds (throwaway branch `tmp/hull-limbs-pin` = 05f1c1f with the three-quarter's refined axis pinned at the
before's +0.040 L; box):
- default: hair_folds 9 (flyaways 0), piece_collar 0.755 PASS, body_back_leg 0.122 WARN (unchanged: not the axis);
- clawd_mh: hair_folds 7, three-quarter hair width 0.956 PASS, hair_penetration 0.048 FAIL and three-quarter skirt
  A-line 0.078 WARN (unchanged: not the axis).
- clawd_mh's hair_penetration is the `lower_back` hair 0.048 L into the MakeHuman skin at the shoulder's top on her
  left (x 0.32..0.40, z -0.57..-0.59, 33 vertices). The hull's shoulder behind the puff is 0.03-0.05 L shallower there
  (x 0.40..0.50, z -0.52..-0.58). Before, the arm parts at z -0.52 took the whole side run (the torso's and the back
  hair's depth), a slab the smoothing spread over the shoulder. The MakeHuman shoulder stands outside the design's hull
  there; the authored body's (default spec) hair_penetration doesn't change.

**Open items**
- tool/body: `body_profile_leg_back` as coded fails on the boot cuff's top rows in every build of ours (above), and its
  face test can flip.
- The flap train below the shorts' hem is in the hull only at the flaps' own columns (|x| > 0.54). Behind the thighs it
  was never there; now the rows above agree.
- The boots' soles (z -5.22 to -5.28): 1-5 cell body runs at the boots' edges in front break `only` for a few heights,
  and the leg takes the interpolated section there (up to 0.1 L shallower). Smoothing hides it. A fix: ignore body
  runs narrower than `split_min` in the `only` test.
- From before: the outfit masks' profile labels (the collar's stripe). `band_hull` should keep only points within
  reach of its bone.

## The report that started it (Michael, 2026-09-29)

The hull page's "Limbs" diagnostic: in the front view the legs are green and the arms blue; in the profile the bare
legs, forearms and hands are pink ("free skin placed by the side view"), only the boot cuffs green, and blue on what
looked like the sleeves and cuffs.

## What the measurement found (before, tool/hull-det 24fa199, the box)

`rounded()` gives each front limb part the depth of the profile's runs of `(limb == t) | FREE_SKIN`. Per height, which
profile pixels each part took, against a hand-made truth for Clawd's profile (the arm: puff, forearm, wrist cuff,
hand; the legs and boots below the shorts):

- **The legs were fine.** The thighs take the profile's thigh skin (the only free skin at their heights); the boots
  take the whole side run, which at those heights is the boot. One height (z −2.72, the right leg) fell back to the
  whole side run (0.96 L deep). The front's thighs start where the profile's do (−2.72), so no thigh is hidden under
  the skirt on this sheet, and no hand shares a height with a thigh (the hands end at −2.57 in front, −2.66 in profile).
- **The arms were wrecked**, 150 heights of each arm borrowing the body's depth:
  - z −0.50 to −0.69 (the shoulder): the neck's free skin (y 0.13 to 0.33), 0.01 to 0.09 L deep: a paper-thin puff.
  - z −0.90 to −1.21 (the puff): the bow's tail, which the profile's masks label `sleeve_cuff_R` (11% of the pixels
    the arm's).
  - z −1.51 to −2.44 (the forearm, cuff and hand): the skirt's cream front panel, which the profile's masks label
    `cuff_R` (12,579 px; the front's cuff is 3,469), running right up to the forearm: 45% of the pixels the arm's,
    sections up to 0.66 L deep against the drawn 0.22. The wrist cuff (−1.9 to −2.05) took only the panel: 0.3 L in
    front of the drawn cuff.
- **The profile's limb pieces are mostly on the wrong garments** (outfit masks, not this branch's code): `sleeve_R`
  on the bow's loop, `sleeve_cuff_R` on the bow's tail, `cuff_R` on the skirt's front panel, `sleeve_L` on the sailor
  collar's stripe. Only `cuff_L` (the wrist cuff's cream stripe) and `boot_cuff_L` are right; the puff, the sleeve's
  cream end, the cuff's orange band and the boot carry no piece. That is the blue Michael saw.
- The hull: detached forearm fragments, puffs nearly gone, arm blobs fused to the skirt's sides. The limb split cost
  the three-quarter 0.029 of held-out IoU (0.8335, against 0.8624 with no limb split).

## The fix

1. **`limb_image` on the side and oblique views (`free_limbs`).** Free skin is split into connected components by the
   drawing's line class (`View.raw`, now kept by `views_from_sheet`). Each takes the limb of the pieces within
   `SEED_REACH` (0.02 L) of it: a limb's pieces seed that limb, pieces on `SEED_BONES` (head, neck, upperChest: the
   collar, the bow, the pins) and the drawn hair and irises seed the body. Torso pieces (skirt, top, shorts) seed
   nothing: limbs are drawn over them. No seed: one step through the unlabelled drawn cells beside it (a cuff's band
   the masks missed). Seeds of two limbs (under `SEED_SHARE` 0.8 for one): FREE_SKIN. Slivers (under 0.005 L²) and
   the outlines' pixels take the nearest component's. On Clawd: the profile's legs, forearm and hand, and the
   three-quarter's forearms, hands and legs, all take their limb; the face and neck the body.
2. **The depth selection (`sections`, `LimbTrack`).** A limb part takes, per height:
   - `only`: the whole side row where the front shows nothing but this limb (the boots; a body fragment enclosed by
     one limb's parts on one side, a hole in the boot's mask, counts as the limb: `_enclosed`);
   - `limb`: the limb's skin runs in the profile, with its piece runs that overlap the skin (`TRACK_OVERLAP` 0.5);
   - `piece`: its piece runs within the skin's track (interpolated from the skin above and below), joined with the
     interpolated section;
   - `interp` (the skirt fallback's replacement): the section's centre and its depth over the limb's front width,
     interpolated between the nearest `only`/`limb` heights above and below (each the median over `TRACK_WINDOW`
     0.15 L of that sighting, away from the gap, since a sighting's edge row is cut short, e.g. skin going into a
     cuff); beyond the last one, that one's. Never the whole side run.
   - A limb the side view never shows keeps the old fallback (skin, else the side run).
   Piece runs off the skin's track are rejected, which removes the mislabelled panel, bow and tail.
3. **Diagnostic.** The page's Limbs row shows every view in one colour scheme, and a new "Limb depth" map shows the
   profile's rows with each limb's chosen interval per height (solid from skin, lighter from pieces, pale
   interpolated) and the rejected piece runs in red, with a table of heights per source.
4. **Determinism.** Integer image ops (scipy `label`, `binary_dilation`, the EDT's feature transform), IEEE `+ − × ÷`
   in a fixed order, `_round` (floor of x + 0.5) for interpolated grid indices, `det.cs` untouched.

## Results (with the no-TRELLIS masks `bc0f48dc`: see PAUSED below)

Hull pair on the box, validated (before tool/hull-det 24fa199; after, that plus this fix):

| held out | before | after | no limb split (after) | plain |
|---|---|---|---|---|
| front | 0.9449 | 0.9449 | 0.9449 | 0.9449 |
| profile (plain carve both times) | 0.3537 | 0.3536 | 0.3536 | 0.3536 |
| three-quarter | 0.8335 | **0.8783** | 0.8614 | 0.7149 |
| back | 0.9343 | **0.9467** | 0.9458 | 0.9458 |

Per-height borrowing (front limb parts, height x side, 2+ foreign cells in the side runs, by the hand-made truth):

| | arm before | arm after | leg before | leg after |
|---|---|---|---|---|
| parts | 416 | 416 | 526 | 526 |
| borrowing | 296 | 8 | 3 | 2 |
| foreign cells / own cells | 6,793 / 6,539 | 80 / 5,890 | 106 / 23,862 | 8 / 21,324 |
| whole side run | 4 | 0 | 244 (the boots) | 0 |

The 8 left: z −0.54..−0.55 (×2 sides), the `sleeve_L` mask on the sailor collar's stripe, on the arm's track (joined
with the interpolated section, it widens nothing); z −1.36 and −2.49 (×2), 2–3 cells of the forearm's and hand's own
outline the truth gives to the skirt. Legs: z −2.73 (×2), the thigh's outline at the shorts' hem.

- **Determinism:** two fast-path builds on the box are bit-identical in every stage and output (hull.npz 908973a8…,
  hull_pieces 9bcfabaf…); the validated build's outputs match them. The new stages (limb images, sections, the
  rejected runs) and the outfit masks hash the same on the laptop (arm64) and the box (x86): 23 of 23.
- **Pieces labels:** the arm pieces gain in every view (held-out front sleeve cuffs 0.15–0.22 → 0.54–0.58, the back's
  used cuff_R 0.50 → 0.84); the skirt loses (held-out three-quarter 0.617 → 0.452) and the weighted pieces IoU dips
  (three-quarter held out 0.4235 → 0.3956). The arm blobs in front of the skirt's sides had carried the profile's
  mislabelled panel masks; without them the profile's panel labels land on the skirt's own side surface.
- **tool/hull-det can't build clawd_body** (24fa199 and 3da2530): `garments.band_hull` fails on `cuff_L` ("no row of
  the piece is measured on 20% of its circle"). Its hull's `sleeve_cuff_L` points sit on the bow's tail: they cover
  17% of the circle round the upper arm, a median 0.43 L from it. With this fix: 58%, 0.15 L. The body's before is
  therefore pipeline-3d (0122617), the gate's baseline.

### The authored body (clawd_body, the box)

| build (its hull) | thigh r median / top ring | thigh max depth | upper arm r median / top ring | upper arm max depth x width |
|---|---|---|---|---|
| pipeline-3d 6ca18da | 0.203 / 0.280 | 0.618 | 0.151 / 0.431 | 0.870 x 0.810 |
| tool/hull-det 3da2530 (before) | 0.203 / 0.283 | 0.608 | 0.151 / 0.431 | 0.870 x 0.810 |
| this branch e7b21e9 (after) | 0.204 / 0.307 | 0.604 | 0.136 / 0.193 | 0.385 x 0.355 |

- The upper arm had a 0.43 L balloon at the shoulder (the ring fitted to hull points on the bow's tail); now a tapered
  tube, 0.19 at the shoulder to 0.10 at the elbow. The thigh's depth just under the shorts (z −2.79) went 0.61 → 0.54
  (drawn 0.55); its top ring at the hip, which no view shows, is the fitter's extrapolation (0.55 → 0.60 deep).
- **Only this branch builds clawd_body.** pipeline-3d 6ca18da fails at `sleeve_L` (`sleeve_hull`), tool/hull-det at
  `cuff_L` (`band_hull`), both "no row of the piece is measured on 15/20% of its circle": the arm's hull points they
  loft round sit on the bow and the skirt panel.
- The after build's QA (111 checks): PASS 75 / WARN 27 / FAIL 9. poke_share 0.0284 FAIL (skirt 203 px, wrist_R 49).
- **The wrist cuffs run the whole forearm** (`wrist_L` z −1.06..−2.12; drawn cuff −1.74..−2.09); piece_cuff_L/R
  0.099 / 0.037. 235 of the hull's 761 `cuff_L` points (31%) lie on the other arm (x median −0.87): the profile's
  `cuff_R` mask on the skirt panel, mirrored by `label_volume` onto her right side as `cuff_L`. `band_hull` spans all
  of its piece's points along the bone; with only those within 0.35 L of it, the span is −1.66..−2.08. Not changed
  here (garments.py and the outfit masks belong to other workstreams); the one-line fix is a reach filter in
  `band_hull`, as `code_body.limb` has.
- The skirt, in 3D: its profile depth is an A-line (near hem over widest 0.995); its front width is widest at
  z −2.01 and 0.832 at the hem.

## Open items

- The outfit masks' profile: `cuff_R` on the skirt's front panel, `sleeve_R` and `sleeve_cuff_R` on the bow and its
  tail, `sleeve_L` on the sailor collar's stripe; the puff, the sleeve's cream end, the cuff's orange band and the
  boot have no piece. The limb carve now works round them; the labels (label_volume, the mirrors) still spread them.
- `band_hull` (and likely `sleeve_hull`) should take only points within reach of their bone.
- The hull-det stages hook stores `rounded`'s V by reference, so its hash is the face-carved V's (`carve_face` edits
  it in place); copy it at the stage.

## PAUSED (2026-09-30, morning): superseded by the relaunch at the top

**History.** Head `tool/hull-limbs` (the SHA in the pause reply). Worktrees: this one and
`~/animation-pipeline-hlbase` on `tmp/hull-limbs-base` = 562bfe2, the exact before (this branch at de6c007 with the
three hull commits 6626176, f2cfa0f, de6c007 reverted; it lacks e803c34 too, which only touches the fix).

**The numbers above were measured with the wrong outfit masks.** Both worktrees lacked `charkit/out/i3d` locally, and
`infra/gcp/build.sh sync` (rsync `--delete`, `charkit/out/i3d/***` included) deletes the box copy's seeded i3d when
the laptop has none, so the outfit masks were built without the TRELLIS field (`i3d/ext/runA/clawd_3dstyle_s1_field.npz`,
read by `outfit.find_field`). That gives mask set `bc0f48dc…` instead of `074d9a3f…`, and the masks' stamp doesn't
include the field, so nothing rebuilds. On the box, every copy without the field has `bc0f48dc` (accessories,
artifacts, bis0122617, bis42df0c8, defspec, face-base, hdbase, hulldet, loft, mouth) and every copy with it has
`074d9a3f`; the gate clones link i3d, so gates and production use `074d9a3f`. With `bc0f48dc`, the profile's arm
pieces sit on the skirt panel and the bow, and clawd_body fails at `sleeve_L`/`cuff_L` on pipeline-3d and
tool/hull-det: the inputs, not the code. Fixes for other owners: sync shouldn't delete a box copy's i3d the laptop
lacks; the masks' stamp should cover the TRELLIS field.
- The fix itself still stands (it made the `bc0f48dc` case build and removed 288 of 296 borrowing arm parts there),
  but the before/after tables must be redone with `074d9a3f`. Done since: the TRELLIS mesh and field copied (plain
  copies, not links) into both worktrees' `charkit/out/i3d/{clawd,ext/runA}`; stale masks and hulls deleted on the
  box; e803c34 widened the track's overlap test (a correctly labelled puff is deeper than the forearm's track: overlap
  over the shorter of the two, and at most TRACK_ASPECT 2x the limb's front width).

**Box jobs still running at the pause** (started with `scratchpad/hl/redo.sh WORKTREE TAG`: sync, a validated hull,
then a clawd_body build; the laptop-side script fetches when done):
- after, this worktree at e803c34: hull -> box `charkit/out/hl2/after` (+ `after_stages`, `after.log`), body ->
  `charkit/out/hl2_body_after` (+ `.log`), then `charkit/out/hl2` and `charkit/out/clawd/outfit` fetched here.
- before, hlbase at 562bfe2: the same under `~/animation-pipeline-hlbase/charkit/out/hl2/before`,
  `hl2_body_before`. Its masks are `074d9a3f` (checked).
- the clawd_body gate of a9a84a8 into pipeline-3d: report into `charkit/out/gate/` here.

**Gate, default spec, a9a84a8 into 01f2cdd: FAIL**, checks worse: `hair_folds` 7 WARN -> 47 FAIL, `hair_penetration`
0.0009 -> 0.0476 FAIL, `body_three_quarter_hair_width` 0.956 -> 0.896 WARN (report
`charkit/out/gate/gate_tool-hull-limbs_a9a84a8_into_01f2cdd.md`). The candidate carries tool/hull-det too, so first
attribute it: gate 562bfe2 (the before, hull-det without this fix) the same way, and compare the hair's source (the
hull round the head and shoulders: the puffs now interpolated) before/after.

**Landed after the pause** (real masks `074d9a3f` in both; the hulls fetched into `charkit/out/hl2/{before,after}` in
each worktree, with their pages and `*_stages`):

| held out | before (562bfe2) | after (e803c34) | no limb split | plain |
|---|---|---|---|---|
| front | 0.9449 | 0.9449 | 0.9449 | 0.9449 |
| three-quarter | 0.8759 | 0.8781 | 0.8614 | 0.7149 |
| back | 0.9467 | 0.9467 | 0.9458 | 0.9458 |

Pieces labels, held-out agree: front 0.7648 -> 0.7643, profile 0.6679 -> 0.6672, three-quarter 0.7225 -> 0.7212,
back 0.6927 -> 0.6847. With the real masks the limb split already helps before the fix (0.8759 against 0.8614 without
it), and the fix adds 0.002: the large before/after gaps above were the no-TRELLIS masks'. The per-height borrowing
table with the real masks is still to measure (step 1). Both body builds died at the start: the box stopped answering
ssh ("server <build box> not responding"), so rerun them (`scratchpad/hl/redo.sh` is not needed: `python -m charkit
remote build charkit/spec/clawd_body.json --out charkit/out/hl2_body_TAG --no-blend` from each worktree).

The clawd_body gate of a9a84a8 into 01f2cdd: **FAIL**, checks worse: `body_back_hem_mid`, `body_front_hair_length`,
`piece_sleeve_cuff_R` (report `charkit/out/gate/gate_tool-hull-limbs_a9a84a8_into_01f2cdd_clawd_body.md`). Attribute
it with the default gate's regressions (step 2).

**Next steps, in order:**
1. When the two jobs land: check the masks are `074d9a3f` in both; rerun the scratchpad measurements on them
   (`measure.py before|after HULL_NPZ` with `WT=before_tree` for before, `pageimgs.py`, `bodym.py`, `bodyalone.py`,
   `bandcov.py`, `radii` in `mkpage.py`'s inputs) and replace the tables above. The scratchpad scripts are not
   tracked; if they're gone, `sections(..., tracks=T)` and `LimbTrack.rejected` give every limb part's source.
2. Attribute the default gate's hair regressions (gate 562bfe2 into pipeline-3d; if they're hull-det's, say so; if
   they're this fix's, look at the hull's shoulders and the hair's labels there).
3. Merge pipeline-3d (01f2cdd, infra only) and gate the head on both specs:
   `python -m charkit remote gate tool/hull-limbs --into pipeline-3d [--spec charkit/spec/clawd_body.json]`.
4. With real masks, recheck the wrist cuffs: with `bc0f48dc`, 31% of the hull's `cuff_L` points lay on the other arm
   (the profile's mislabelled panel, mirrored) and `band_hull` made the cuff a forearm-long gauntlet.
5. Regenerate the review page (`scratchpad/hl/mkpage.py` -> `charkit/out/hl/review/index.html`) and `open` it.

## Measurement tools

The per-row source table, the truth for Clawd's profile and the before/after pages were made with scripts in the
session's scratchpad (not tracked): `sections(..., tracks=T)` gives every limb part's source, runs and the rejected
piece runs, which is what they read.
