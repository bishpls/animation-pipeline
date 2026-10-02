# garments8: separated references for the collar, lapels, top and bow; the joined-shoulder regressions recovered

Branch `tool/garments8` from pipeline-3d cd1c327f, worktree `~/animation-pipeline-garments8`. Brief:
`~/animation-pipeline-3d/charkit/out/coord/brief_garments8.md` (+ the coordinator's launch message).

**Why (Michael, 2026-10-01):** "Don't we just need to give the system a reference to the collar / lapels without the
bow? That's never actually been defined / spec'd, and it's causing a gap..." The joined shoulder was switched ON with
the garment regressions accepted by name (tool/garments4-shoulders); this round recovers them.

## Order
1. Now (in parallel with the switch): generate the missing separated references (paid calls authorized, ~8 calls at
   n=2, ledger), refcheck each against the turnaround, register them in Clawd's manifest with per-piece
   `shape_truth`, then make the garment checks read them (a remeasure: MEASUREMENT_STEPS + refreshed records).
2. When tool/garments4-shoulders merges (the coordinator messages): merge pipeline-3d; rebuild the flat lapels
   ('smooth' mode) and the puffs' dome against the truths with `sweep optimize`; recover art_outline_neck (5.8 vs 1.5),
   piece_top front (0.50 vs 0.75 before) and the rest in charkit/accepted/; clear each acceptance as it passes.
   **Added (coordinator, 2026-10-01: Michael routed the range-of-motion suite's garment failures here)**, measured by
   the ROM suite (tool/rom, merging soon; its posed checks and boards in ~/animation-pipeline-rom/charkit/out/rom/,
   compare.md; QA part romqa: 17 poses, ~95 s on the laptop):
   - the puffs going into the arm on raised poses (sleeve_body 0.16-0.24 L; limit 0.01 / 0.03): default 0.07-0.235,
     joined 0.04-0.178 (raise_side_90 0.235 / 0.164, arm_twist_90 0.113 / 0.178, arms_up 0.071 / 0.175);
   - the sleeves poking through the jacket (sleeve_top_L/R 1-4% of their edges; joined up to 4.1% arm_across);
   - the collar stretched 0.58 (garment_strain p95) by a head turn: the collar's weights are copied from the nearest
     body vertex (garments.collar: W = body weights at nearest(verts)), so its band by the neck carries neck weight:
     the garment-side part (the collar riding the chest bones, the neck left out of its weights) is mine; the shoulder
     bridge's stray neck weight (rom_weights_stray, 10% of the jacket on the joined body) is the motion round's (rig).
     Also garment-side to check: the joined body's sleeves move with the head turn (sleeve_body 0.04, sleeve_top
     1.3%): the cap weighted from the body (sleeve weights {from body}) inherits the bridge's neck weight.
3. Review page (summary box): design | new references | before | after; `pregate --box auto`; gate.

## Step 1: the references (2026-10-01)

Tools: `tools/garments8/gen.py KEY` (prompts in `tools/garments8/prompts_new.json`, inputs in its REFS; tools/gptimage.py,
gpt-image-2.5-sunburst 2560x1440 high, n=2, ledger tools/ledger.jsonl; the `.env` is a gitignored symlink to the main
checkout's: remove at the end). Takes in `charkit/out/garments8/gen/`.

Calls so far: 4 (collar_alone, top_layers, collar_ghost, bow_ghost), all n=2, none refused.

Refcheck kinds (charkit/layerref.py): Clawd has no palette, so `--kind edit|alone` (palette swatches) can't read her;
her kinds grade on the hand-checked outfit truth. check_bodice generalized to `check_layer` over a table `LAYERS`
(bodice unchanged: bodice_layers re-reads 0.974/0.9961/0.924/0.9947 iou_dc, identical): `top` (the top without the
collar and the bow), `collar_alone` / `bow_alone` (worn on base_body_turnaround's bodysuit). New `GHOSTS` kinds
(`collar_ghost`, `bow_ghost`): one piece alone as worn over the costume by an invisible person; drawn without a body the
model kept neither place nor scale (2.3x larger, ~200 px lower), so each view is registered by one joint scale for the
sheet and a shift per view.

| sheet (take) | kind | front | three-quarter | profile | back | verdict |
|---|---|---|---|---|---|---|
| top_layers 1 | top | 0.974 | 0.992 | 0.965 | 0.996 | PASS: **registered** (shape truth: top) |
| top_layers 2 | top | 0.974 | 0.984 | 0.968 | 0.997 | PASS |
| collar_ghost 2 | collar_ghost | 0.926 | 0.949 | 0.656 F | 0.964 | **registered** front, 3q, back (collar alone) |
| collar_ghost 1 | collar_ghost | 0.968 | 0.788 F | 0.690 F | 0.957 | front, back only |
| collar_alone 1 (on the bodysuit) | collar_alone | 0.600 | 0.675 | 0.390 | 0.966 | FAIL: not registered |
| collar_alone 2 | collar_alone | 0.477 | 0.482 | 0.056 | 0.941 | FAIL |
| bow_ghost 1 | bow_ghost | 0.955 (out 0.035) | 0.933 (out 0.056) | 0.820 (out 0.106) | hidden | FAIL on outside (tol 0.03) |
| bow_ghost 2 | bow_ghost | 0.743 | 0.716 | 0.791 | hidden | FAIL (tails drawn long) |
| bow_closeup (existing, 3q mirrored) | bow_ghost | 0.810 | 0.776 | 0.665 | - | FAIL |

(iou_dc per view. top: V recall 1.0/0.998 and 0.992/1.0, V outside 0.068/0.055 and 0.060/0.051; kept parts >= 0.983.
Ghosts: one joint scale per sheet, a shift per view (FFT cross-correlation, coarse at half resolution then fine);
collar_ghost 2's views' own scales spread 0.10, take 1's 0.31.)

Calibration (tools/garments8/layercal.py -> charkit/out/garments8/layercal.txt, layercal_ghost.txt): `top` the
turnaround moved 2 px PASS (0.998-1.000), its torso band widened 6% FAIL (outside 0.10-0.14). `collar_ghost` the truth's
own collar itself, moved or at 2.3x PASS (1.000); the collar drawn on the bare body (collar_alone take 1's) FAIL (front
0.626, 3q 0.739, profile 0.415; back 0.967); its resolution: a 12% stretch across or down fails only the profile
(front/3q/back 0.91-0.97). `bow_ghost`: itself/moved/2.3x PASS; a 12% stretch across PASSES (blind), down fails only
the profile: not registered anyway.

- The collar on the bare base body spreads out over the bare shoulders (drawn where the turnaround shows the jacket's
  shoulders) and drops the rise beside the neck: drawn over a different layer it is a different shape. The cover
  alone must be drawn as worn over its layer: the ghost sheets (a ghost-mannequin product sheet from bodice_layers).
- The ghosts keep neither place nor scale (drawn 2.3x, ~200 px lower): registered by a similarity fit; first fits slid
  the piece into the head (the hair and neck allowed everywhere): the allowances now only within 0.10 L of the piece.
- The bow: the outermost piece, so the turnaround is its own shape truth (front, 3q, profile drawn whole). Neither
  bow_closeup (0.81/0.78/0.66) nor the bow ghosts pass as a multi-view bow-alone: nothing registered for the bow;
  bow_closeup stays the construction and lines reference.

### Registered (charkit/refs/clawd/manifest.json)
- references `top_layers` (take 1), `collar_ghost` (take 2), `shape_truth_masks` (charkit/refs/clawd/shape_truth.npz:
  VIEW__NAME on outfit_truth's grids, built by `python -m charkit.layerref truths charkit/spec/clawd.json`); sha256s in
  provenance (a top-level one restamps every produced reference). Prompts in gen/prompts.json (all four used).
- `shape_truth` (top-level): collar (bodice_layers' collar: the lapels without the bow), bodice_panel, top (top_layers'),
  neck_v (bodice_layers' V skin, front/3q), collar_alone (collar_ghost front/3q/back), bow (a note: its own truth).
- The pieces cut from a layer sheet by its own colours (layerref.layer_pieces: orange the jacket, each cream component
  voted by the outfit truth where visible, the collar takes its stripes); views: tools/garments8/segview.py
  (charkit/out/garments8/look/seg_bodice.png, seg_top.png).

### The checks reading the truths (in progress)
- declared.py: a declaration's `truth: NAME` (the manifest's shape_truth entry): ours drawn the way that sheet draws the
  outfit (pieceqa.our_labels / our_classes `exclude`: the entry's `without` pieces' objects left out of the z-buffer;
  `alone`: the piece's objects alone), against the truth mask VIEW__NAME; shape_iou there is bodymeasure.iou_tol at
  OUTLINE_TOL (the guard's metric; the truth masks moved 1-2 px read 1.0). Inputs: declared.inputs(truth=True) ->
  I['truth'], I['without'](view, exclude, classes), I['alone_of'].
- The calibration stand-in (calib/labels.py Garments: our_labels / our_classes with exclude): the design drawn without
  the cover = the matching truths painted, moved with the labels; a floor keeps its holes.
- New checks (charkit/truthqa.py): collar_{view}_truth (the collar and lapels without the bow vs bodice_layers'
  collar; flag: the bunched lapels), top_{view}_truth (the jacket without the collar and bow vs top_layers');
  limits [0.75, 0.5] (qa3d.PIECE_PASS/WARN). Known-bad: `g8_lapels0` to store (a build with the bunched hull lapels).
- Remeasure (charkit/necklineqa.py): neck_v_{front,three_quarter}_skin against the V's truth (bodice_layers' skin),
  ours without the bow, windows to z -0.90 (were -0.75 above the knot). Needs a MEASUREMENT_STEPS entry
  (charkit/steps/necklineqa.py) with the commit, and refreshed calibration records (known-bad g4_v0).
- Harness: tools/garments8/truthlab.py BUILD (the truth checks and pictures on a fetched build).

### Committed (2201e679 the references, truths and checks; 5336dcb6 the steps)
Truth checks on fetched builds (tools/garments8/truthlab.py, the views front/3q/profile/back; collar without profile):
| check | g7_base (old body = pipeline-3d's default geometry) | g7_c4 (joined shoulder, round 7) |
|---|---|---|
| collar_{front,3q,back}_truth | 0.617 / 0.514 / 0.872 | 0.751 / 0.514 / 0.813 |
| top_{front,3q,profile,back}_truth | 0.801 / 0.743 / 0.826 / 0.911 | 0.734 / 0.679 / 0.777 / 0.877 |
| neck_v_{front,3q}_skin (remeasured) | 0.574 / 0.505 FAIL | 0.561 / 0.491 FAIL |
- The collar's profile view dropped from its truth check: edge-on, ~0.04 L thick, the truth moved 6 px reads 0.58 (an
  offset, not a shape; other views 0.92-0.97 at 6 px).
- vlab (charkit/out/garments8/look/v_g7_c4.png): without the bow our V closes at about z -0.70 (cream: our lapels and
  bib meet), the truth's V reaches -0.88: the V's lower part is the miss.
- Calibration plan (box): known-bad `g8_lapels0` = the branch base's default build (the bunched hull lapels flagged
  2026-10-01). With the a-priori limits [0.75, 0.5] the flagged lapels read WARN (0.51-0.62): the triple decides the
  limits (the collarqa precedent: limits between the design's moves and the flagged build). top_*_truth: no flagged
  build separates it (0.73 vs 0.80 front): kind shape without a known-bad (guard) unless one does.
- Running: box build g8_base (charkit/spec/clawd.json at 5336dcb6, --boards '' --no-blend) on build2, job
  build-garments8-1001-174757-7b36 (`python -m charkit remote attach build-garments8-1001-174757-7b36` if the follow
  dies), log charkit/out/garments8/build_g8_base.log -> charkit/out/g8_base. (The first try failed at the sync: a blob's
  sha256 mismatch on download, transient; the retry synced.)
- Then on build2: `calibrate store g8_lapels0 charkit/out/g8_base --why ...` (and locally for the JSON), then
  `remote run --box build2 --fetch charkit/calib/records python -m charkit calibrate
  'collar_*_truth,top_*_truth,neck_v_*_skin' --build charkit/out/g8_base`.

### The lapels read off the collar truth (front, L from the midline and the eye line; for step 2's template)
- inner edge (the V): z -0.49 x 0.156, -0.60 0.125, -0.72 0.08, the V's point (0, -0.88) (neck_v's lowest skin -0.881).
- outer edge: the shoulder (0.40, -0.49), -0.60 0.34, -0.72 0.26-0.28, -0.79 0.20: convex, reaching the middle only
  under the knot. In the flat lapels' terms (garments.collar lapel project + inner/bottom_a): shoulder ~[0.40, -0.49],
  point (the outer edge's low end) ~[0.20, -0.80], inner (the V's point) ~[0.0, -0.88]. Round 7's settings stopped at
  the bow's top edge (point [0.2, -0.66], inner [0.02, -0.68]): nothing defined the lapels under the bow.
- Caution: the truth's lapel tips z -0.83..-0.90 (111 px) went to bodice_panel (layer_pieces: the tip is cut from the
  lapel by the 2 px erosion and shares more border with the panel); the V truth carries the point.
- Box: g8_base built (build2; CPU 1397 s, the declared part 109 s wall / 306 s CPU against g7_base's 79 / 79: the
  truth z-buffers cost 0.2 s each locally, the rest a fresh clone's caches/JIT). Its QA matches truthlab exactly.
- Known-bad g8_lapels0 stored (622f6344; locally and on build2). Calibration running on build2 -> fetched
  charkit/out/g8_base/qa/cal_g8.json (log charkit/out/garments8/cal_g8.log); then write the records locally
  (calibrate._write_json into charkit/calib/records/) and set the collar truth's limits from the triple.

### Calibration (local, g8_base as current; known-bads g8_lapels0, g4_v0 stored locally)
First triple (a-priori limits): collar front/3q BLIND (g8_lapels0 0.617 / 0.514 WARN; design moves 0.927-0.964 /
0.928-0.953; affine floor 0.26 / 0.35), collar back BLIND and the affine floor passes (0.81); top_* BLIND (no top defect
in g8_lapels0: 0.80 / 0.74 / 0.83 / 0.91; design 0.94-1.0; floors 0-0.47); neck_v_front CALIBRATED (design 0.90-0.97,
g4_v0 0.352, voronoi 0.728 WARN); neck_v_three_quarter MISCALIBRATED (the design moved +0,+2 reads 0.794 < 0.8).
Grading set from it (a1480b81): collar truth front/3q [0.85, 0.70], back dropped; top truth a guard; neck_v 3q
[0.75, 0.6]. Re-run writing the records: log charkit/out/garments8/cal_g8_local2.log.
Step 2's targets from these (goals, not merge gates; coordinator 2026-10-01: under K a NEW check shipping at FAIL is
reported, not blocking; blocking is existing checks regressing to FAIL, flag-check regressions, CPU > 1.5x, missing
calibration records and the guard): collar_front/3q_truth >= 0.70 (Michael wants the lapels right), neck_v_* up from
0.574 / 0.505 (the base under the new measure), top_* WARN or better. If one stops short: report it, bend nothing.
- Records committed (09ebeb00): collar_front/3q_truth CALIBRATED, top_*_truth GUARD, neck_v_*_skin CALIBRATED.
- pipeline-3d 241f0547 (tool/rom, tool/hairtruth) merged in (0b4065f9): hairtruth added the same z-buffer option as
  `hide` (pieceqa.our_labels): adopted (our_classes' too); the stand-in draws a garment truth's way only when the
  hidden objects are a garment truth's covers (the hair's clips keep its labels); Clawd's shape_truth now holds the
  hair's entry (pipeline-3d's, read by charkit.shapetruth) and garments8's in one object (the auto-merge had left two
  "shape_truth" keys). The truth checks on g8_base read the same after the merge. Tests: manifest, declared, registry,
  calibrate, spec_declared, shapetruth, hairtruth, rom, hairflags pass.
- Waiting: the shoulder switch's merge (tool/garments4-shoulders c8d30430, not in pipeline-3d yet).

## Step 2 (2026-10-01): the joined shoulder merged (pipeline-3d 348397e7, batch4), merged in
- Merge commit: declared.inputs takes both `body` (pipeline-3d's base-body ref) and `truth`.
- The recovery list (charkit/accepted/, the joined shoulder's default against the old body):
  art_outline_collar 1.442 PASS -> 3.47 WARN; art_outline_neck 1.468 -> 10.307 WARN; art_terminator_neck (INFO now:
  the neck lit under the chin, shade share 0.24 -> 0.02 front, terminator 0.043 L < MIN_TERM 0.05; the design draws the
  chin shadow in all four views: find it in the neck's normals/shading on the joined surface or its shape under the
  jaw; keep the ROM gains: arm into torso 0, no arm parting); bow_front_bleed 0 -> 0.1475 FAIL; collar_back/front/
  profile_torn 0 -> 0.0101/0.0261/0.0197 FAIL; neck_v_front 0.7648 -> 0.7434 WARN, 3q 0.5663 -> 0.5493 FAIL (old
  measure; remeasured here); sleeve_profile_profile_L 0.0307 -> 0.1139 FAIL, sleeve_three_quarter_profile_L 0.016 ->
  0.0618 FAIL; the shoulder_* accepted for the guard (piece_top front 0.749 -> 0.507, -32%). rom_weights_stray is the
  motion round's. Plus the ROM garment items above.
- New in pipeline-3d: gate --batch, QA denominators (a part measuring fewer checks than it declares blocks), like-for-like
  CPU, the budget rule (report-only).
- The neck's chin shadow: faceshade.proxy_normals (the neck's normals turned round its axis and tilted down under the
  jaw: s from the neck bone's base to the head joint, the neck within 1.25 x its radius rn, rn the median radius over
  s 0.25-0.6) and cast_maps (the jaw's and hair's shadow baked on neck_w > 0 under the chin). To compare on g8_base vs
  g8_c0: qa_chin_shadow.png, qa_artifacts.png, and the faceshade inputs (the neck joints, rn, k).
- Running: box build g8_c0 (the merged default, joined shoulder) -> charkit/out/g8_c0 (log build_g8_c0.log).

## Step 2 plan for the next round (exact first steps; Michael 2026-10-01: wrap up, no fits or sweeps tonight)
"Before" = g8_c0 (the merged default with the joined shoulder at the branch head; box build, fetched to
charkit/out/g8_c0; its QA carries the truth checks). The g8_base build (pre-shoulder) is the old body's reference.
1. Lapels from the collar truth (template first): in a garment set (tools/garments8/v/l0.json) set garments.collar.lapel
   {mode project, smooth {grid 0.01, dilate 0.03, blur 0.02}, shoulder [0.40, -0.49], point [0.20, -0.80],
   inner [0.0, -0.88], bottom_a 30, a 85} + flat_front {a 85, fade 15} (the values read off the truth above; round 7's
   F0 stopped at -0.66). Screen with `python -m charkit sweep charkit/out/g8_c0 --stage garments --parts
   declared,collar_flags,piece_details,artifacts,face_region,sheet_pieces --oat 'garments.collar.lapel.point=[...]'`
   (the s5 check list: tools/garments7/s5.json; add collar_*_truth, neck_v_*, top_*_truth). Read collar_front/3q_truth
   (goal >= 0.70; g8_c0's values first), neck_v_* (goal up from the base's), art_outline_neck (<= 1.5), bow_front_bleed,
   collar_*_torn, piece_collar/piece_top per view (guard), neck_crease (the hide_under mask under the new collar).
   tools/garments8/truthlab.py BUILD draws ours-without-the-bow against the truths (truth_collar.png, truth_top.png);
   tools/garments8/vlab.py the V.
2. The V: the jacket's opening table (garments.top.opening.half closes at z -0.72) must stay open to the V's point
   (-0.88) with the lapels over its edges: extend the table under the knot after the lapels land; read neck_v_*.
3. Then `sweep optimize` (charkit/optimize.py) on the lapel knobs (point, inner, shoulder, a, spread, off, smooth.*,
   bottom_a) and the puffs' dome (sleeve_L/R.clear_body gap/from_t/dilate/blur/taper, top.tuck): objective toward pass
   on collar_*_truth, neck_v_*, art_outline_neck/collar, collar_*_torn, bow_front_bleed, sleeve_*_profile_L,
   top_*_truth, piece_top front (guard 0.15); confirm.spec = the base build's spec (round 7's trap: the confirm built
   the default spec).
4. The ROM garment items (romqa on the candidate builds): puffs into the arm at the raises (sleeve_body), sleeves through
   the jacket (sleeve_top_L/R), the collar's head-turn strain (its weights copied from the body by nearest vertex carry
   neck weight: a collar weights option leaving neck/head out, opt-in in clawd.json).
5. Clear each acceptance in charkit/accepted/ as its check passes; review page (design | the new references | before
   g8_c0 | after) with `python -m charkit review page`; pregate --box auto; gate.

### Coordinator corrections (2026-10-01)
- "Wrap up" = finish step 2 through a gate (not stop); no new scope beyond step 2; the motion-suite items are NOT
  pulled into this round (dropped from the plan above). Step 1 lands with step 2 in one gate unless step 2 is many hours
  out. Pregate on step 1's state: PASS (0 moved, 0 blocking; 21aaa856 into 348397e7).
- The neck item verified and dropped (77939464; charkit/accepted/art_terminator_neck.json's why amended): g8_base vs
  g8_c0 (tools/garments8/neckcheck.py -> charkit/out/garments8/neck/): face_shadow_chin 0.693 -> 0.623 (front 0.746 ->
  0.713, 3q 0.640 -> 0.534); the neck shadow share under the board light 0.143/0.206/0.201 -> 0.132/0.152/0.138 (design
  0.13-0.16); qa_chin_shadow.png shows it under the jaw in both. The artifact detector's numpy neck window (same area,
  0.062 L^2) had its shade at its foot by the collar line (the old neck base), now lit by the raised shoulder: shade
  0.24/0.25/0.18 -> 0.018/0.026/0.001, no edge in front, 3q, profile.

### g8_c0 (the "before": joined shoulder default at the branch head)
| check | g8_base (old body) | g8_c0 (joined) |
|---|---|---|
| collar_front / 3q_truth | 0.617 / 0.514 | 0.771 / 0.559 |
| neck_v_front / 3q_skin | 0.574 / 0.505 | 0.562 / 0.499 |
| top_front / 3q / profile / back_truth | 0.80 / 0.74 / 0.83 / 0.91 | 0.75 / 0.66 / 0.80 / 0.86 |
| art_outline_neck / art_outline_collar | 1.47 / 1.44 | 10.31 / 3.47 |
| bow_front_bleed | 0 | 0.1475 F |
| collar_front / back / profile_torn | 0.001 / 0 / 0 | 0.026 / 0.010 / 0.020 F |
| sleeve_profile_profile_L / sleeve_three_quarter_profile_L | 0.031 / 0.016 | 0.114 / 0.062 F |
| neck_crease | 12.7 | 24.2 W |
| piece_top f/3q/p/b | 0.749 / 0.800 / 0.635 / 0.931 | 0.507 / 0.669 / 0.657 / 0.962 |
| piece_collar f/3q/p/b | 0.657 / 0.467 / 0.027 / 0.928 | 0.905 / 0.532 / 0.103 / 0.890 |
- Running: sweep l1 (tools/garments8/l1.json: the truth-read lapel template T0 and 9 OAT variants) on build2 ->
  charkit/out/garments8/sweeps/l1 (log charkit/out/garments8/sweep_l1.log).

### The collar's two measures reconciled (coordinator: audit before hill-climbing)
l1's T0 (the truth-read lapels): collar_front_truth 0.771 -> 0.863 while piece_collar front (the in-context guard)
0.90 -> 0.75. tools/garments8/recon.py, recon2.py, stripe_check.py (charkit/out/garments8/recon/: recon2_T0.png,
truth_vs_hand.png, recon2.json):
- (c) no: the separated reference agrees with the turnaround where both see the collar: the truth vs the hand-checked
  outfit_truth's collar outside the bow reads 0.688 / 0.746 only because the truth's collar includes the drawn ink
  lines (the stripe's edges, the collar's outline, the bow's outline just outside its mask) that the hand truth leaves
  unscored (truth_vs_hand.png: every disagreement is a 1-2 px line); the truth puts 12-18 px on the drawn skin.
- (a) no: the guard's design side (the produced outfit_masks' collar) is the hand truth's (IoU 0.993 front, 0.873 3q).
- (b) minor: ours on the drawn bow 121 / 238 px (12-14% of ours-only, front / 3q); the bows' IoU 0.77 / 0.68 in every row.
- What it is: a real lapel error both measures see. T0's lapels' inner edges cut into the drawn V's skin near the
  neck (ours on drawn skin: front 91 -> 239 px, 3q 469 -> 475; the truth has 12-18 px there) and onto the drawn lines;
  the truth check still rises because T0's lapels now continue under the bow to the V's point (truth only: the guard
  can't see under the bow). So: fix the inner edge (the collar's V near the neck: v_half / the inner edge's top), not
  the measures.
- Sweep l2 (the V on lapels B = T0 + off 0.025 + inner [0.02, -0.82]): the panel cut to -0.88 + the jacket open along
  the truth's V (B_V): neck_v_front 0.558 -> 0.717, 3q 0.523 -> 0.531, top_front_truth 0.773 -> 0.796, piece_top front
  0.56 -> 0.59; but art_outline_neck 7.4 -> 9.3 and neck_crease 24.2 W -> 34.6 F on B (lapels off 0.025 + inner -0.82;
  28.2 W with off 0.015): neck_crease is an existing check: a regression to FAIL blocks.

### Sweep l3: v_half on the truth-read lapels (the coordinator's one targeted step) -> no row clears the landing bar
Base: T0 with the V point at -0.82 (inner [0.02, -0.82], off 0.04); v_half 40/46/52/58, each with and without l2's V
(the bodice panel cut to -0.88, the jacket's opening along the truth's V). tools/garments8/rowjudge.py on
charkit/out/garments8/sweeps/l3/sweep.json (control = g8_c0):
| row | collar truth f / 3q | neck_v f / 3q | art_outline_neck | neck_crease | piece_collar guard (worst) | new FAIL |
|---|---|---|---|---|---|---|
| control | 0.771 / 0.559 | 0.562 / 0.498 | 11.23 | 24.2 W | - | - |
| vh40 | 0.887 / 0.500 | 0.570 / 0.519 | 6.16 | 14.8 | f -16%, 3q -27%, p -27% | collar_three_quarter_torn |
| vh40_V | 0.892 / 0.509 | 0.725 / 0.512 | 9.08 | 14.8 | 3q -25%, p -27% | collar_three_quarter_torn |
| vh46_V | 0.907 / 0.529 | 0.735 / 0.558 | 9.90 | 50.1 F | 3q -20%, p -24% | 3q torn, neck_crease |
| vh52_V | 0.901 / 0.532 | 0.757 / 0.582 | 7.49 | 105.8 F | 3q -17%, p -23% | 3q torn, neck_crease |
| vh58_V | 0.876 / 0.522 | 0.772 / 0.587 | 7.33 | 13.7 P | 3q -17%, p -22% | collar_three_quarter_torn |
- Every row breaks the guard on piece_collar three-quarter (-17..-27%) and profile (-22..-27%) and adds
  collar_three_quarter_torn (control 0.001 W -> 0.012-0.063 F: the flat lapels' edge in three-quarter); v_half 46/52
  also push neck_crease to FAIL (the collar's mask under the neck). The front recovers (collar truth 0.88-0.91 PASS,
  piece_collar front within 15% from v_half 46), the V opens with l2's changes (neck_v_front 0.56 -> 0.73-0.77).
- So per the coordinator: not landed; step 1 gated alone. The lapels stay as in pipeline-3d's default.

### Next steps for the lapels (next round, start here)
1. The three-quarter is the open problem: the flat lapels in 3q (the near lapel's outer part and the far lapel's
   shoulder band) cover the drawn V's skin and leave the drawn collar's shoulder end bare (recon2_T0.png, right).
   Measure the 3q lapel per row against the truth (collar_three_quarter_truth stays ~0.50-0.53 in every l1-l3 row:
   none of the front-view knobs move it): the projected lapels are laid from the front view (garments.collar lapel
   project: the columns straight in the front view), so their 3q shape is whatever that projection gives on the
   chest. A 3q-aware term (the lapel's azimuth spread `spread`, the outer edge's depth `off` per azimuth, or fitting
   the template in 3q too: the truth's 3q collar) is the lever to try; and the profile (piece_collar profile -22%).
2. collar_three_quarter_torn with the flat lapels: their 3q edge (0.012-0.063 F); off 0.025 cleared it in l1
   (0.000) but pushed neck_crease to FAIL (34.6): the collar's hide_under mask (reach/rim) with the new collar.
3. Then the V (l2/l3's opening + panel cut: neck_v_front 0.73-0.77) and the puffs' dome (bow_front_bleed 0.158,
   sleeve_*_profile_L) as planned; the motion items are not this round's.
