# The bow and its neighbours, then Michael's garment list (tool/garments4)

Worktree `~/animation-pipeline-garments4`, branch `tool/garments4` from tmp/batch-1001 cf08de35 (pipeline-3d de477dd +
tool/face6 + tool/pieceref, gating into pipeline-3d). Merge pipeline-3d once the coordinator says the batch merged.
The one garments agent while hair is the focus. Rules: `~/.claude/agents/charkit-worker.md` (policy K, the guard, the
tools: `charkit sweep`, declared checks + `calibrate --declared`, `charkit review page`, docs/CODEMAP.md).

Read-only prior work: tool/collar4 (`~/animation-pipeline-garments3`, collar.md rounds 7-8: E2, the lapels, the back
cream panel), tool/sleeves (`~/animation-pipeline-sleeves`, sleeves.md: the pear puff V1, the straight cuff band B1/B2;
untracked harness specs; conflicts with pieceref in collarqa.py), tool/pieceref (pieceref.md: w4, t12, the
attribution of the blockers).

## Brief
**Part 1 (one gate):** `close_hung.on` + `pleat.on` (w4 + t12) with the neighbours placed as drawn:
(a) the collar's lapels end inside the bow's top edge (art_outline_collar 1.379 -> 2.096 came from the lapels reaching
the bow's corners); (b) the sleeve caps 0.06 L up toward the drawing (sleeve_front_spikes_L/R; Michael's "shoulders
still misshapen"); (c) the bust/loop contact behind bow_front_bleed fixed at its source (the bust or jacket front, or
loops conforming without moving forward). Expected: no flag regressions (bleed, loop_end, art_outline_collar back to
PASS), torn/spike checks clear. Review page asks Michael the bow's three compromises (knot graded front only; w4's
slanted loop ends; the loops' bottom at 0.30).

**Part 2 (Michael's list, 2026-09-30), each a declared + calibrated check first, then the fix:** (1) creases, folds,
pleats as a mechanism the outline renderer draws (skirt's cream panel, the bow); (2) cuffs: no cream, 1.5-2.4x the
drawn area; (3) shoulders with the back view's cream collar section; (4) the neck-to-bow V: skin, not orange (open V +
the body's neck-chest join).

## State
- Setup: notes created; variant specs under `charkit/out/garments4/specs/` (untracked): `p1.json` = clawd.json with
  close_hung.on and pleat.on.
- pipeline-3d ca489f3 (the batch, same tree as cf08de35) merged in (3c10f1c4).
- Box builds (no boards): `charkit/out/g4_before` (the default spec at cf08de35) and `charkit/out/g4_p1` (p1.json).
  Local helpers (diagnostics, not variant harnesses) in `charkit/out/garments4/tools/`: qcmp.py (checks side by
  side from qa.json), frontrows.py (collar/bow extents per row, drawn vs ours), sleevetop.py (sleeve tops per column),
  buried.py / rim.py (bow depth against the jacket). Produced outfit masks and hull copied from pieceref's out dir
  (stamps 60d84d9b / c798637e) for local reads. Sweep declarations live in `tools/garments4/` (untracked: charkit/out
  isn't synced to the box), outputs in `charkit/out/garments4/sweeps/`.

## Part 1, measured (box builds)
p1 against before (pipeline-3d's bow), the moves:

| check | before | p1 | |
|---|---|---|---|
| piece_bow F/3q/P | 0.896/0.758/0.345 | 0.951/0.852/0.683 | guard up |
| bow_front_bleed (flag) | 0.0 P | **0.2825 F** | blocks |
| sleeve_front_spikes_L / R | 0 / 0 P | **0.0286 / 0.0188 F** | new FAILs, block |
| art_outline_collar (flag) | 1.379 P | 1.402 P | **does not regress on this base** (t12 + the batch) |
| bow_*_torn, collar_front_torn | P | P | t12 clears them |
| collar_three_quarter_torn | 0 P | 0.0045 W | not blocking |
| body_profile_chest | 0.002 P | 0.0482 W | not blocking (the pleat's thinner loops) |
| bow_part_*, iso_bow_*, bow_profile_* | FAIL mostly | P/W | the pleat's gains |

- **(a) The lapels** (frontrows.py): ours end 0.04 L inside the lobes' upper outer corner (collar |x| 0.351 at z
  -0.607; bow corner 0.39 at -0.626), the drawn 0.02-0.04 inside (0.337-0.346 at -0.588; corner 0.34-0.36 at
  -0.607). What differs is the lapel's width at the shoulder: drawn outer |x| 0.39-0.40 at z -0.49..-0.51, ours
  0.22-0.25 (our lapel is a triangle widening down to the bow; the drawn one is wide at the shoulder and narrows to
  it): Part 2 item 3's (the shoulders and collar). art_outline_collar passes on p1 (1.402) and the sleeve caps lower it
  further (0.71-0.82).
- **(b) The sleeve caps** (sleevetop.py, front): ours 0.06 L under the drawn top over |x| 0.43-0.55 (-0.555 against
  -0.494) and 0.08-0.10 under it at 0.57-0.64 (the drawn shoulder squarer): the puff's `out` extent at its top
  stations, not only the cap. s1 (sweep, cap): 0.15 spikes_L 0.02 F; 0.18 spikes_L 0 P but sleeve_front_profile_L
  0.0433 F (before 0.0293 W: a new FAIL) and piece_sleeve_L profile -6%. sleeve_R didn't move: **the evaluator's
  piece cache keyed a garment on its own spec** (sleeve_R mirrors sleeve_L): fixed, bodyeval.garment_deps.
- **(c) The bleed** (buried.py): the lobes' lower parts (z -1.00..-0.90 in the bundle's frame, |x| 0.09-0.33) sit up
  to 0.068 L behind the jacket's front at their (x, z). Fix at the source: the jacket bedded under the bow
  (garments.bed, a shell knob `bed` {under, gap, margin, ease}: the shell set `gap` behind the bow's back where the
  bow covers it and `margin` round its outline, easing back over `ease`; only ever backward). On top and bodice_panel.

## Part 1, fixed (sweeps on g4_p1, box: `charkit sweep run tools/garments4/sN.json --box`; outputs sweeps/s1-s4)
- **(c) the bleed: the jacket bedded under the bow** (`top.bed` {gap .01, margin .02, ease .04}; the lobes only:
  `parts` 'lobes', the knot's and the tails' root's deep backs at the middle left out). bow_front_bleed 0.2825 F -> 0 P;
  also bow_profile_loop_thick 0.0431 -> 0.0306 W, loop_lean 4.84 -> 0.62, bow_three_quarter_torn 0.0037 -> 0.0007,
  piece_top 3q/profile +0.024/+0.030; piece_bow front 0.951 -> 0.934 (-1.8%: the strips' lower rims now show, no longer
  under the jacket). The bib bedded deeper (`bodice_panel.bed` gap .035, margin .03, ease .05) so it stays behind the
  dented jacket. **Guard note:** piece_bodice_panel's profile view 0.342 -> 0.19 against the sweep's control: the drawn
  bib in profile is a 224 px sliver (0.005 L^2), ours 40 px (pieceov.py, review/bib_profile_p1.png): a visibility-floor
  case (the guard's planned floor); against pipeline-3d's 0.169 it is up. Reported, not hidden.
- **(b) the sleeve caps: tool/sleeves' V1 pear table** (sleeve_L.profile; sleeve_R mirrors it): spikes_L/R 0.0286 /
  0.0188 F -> 0 P, **shoulder_back_line (flag) 0.0565 F -> 0.0047 P**, sleeve_profile_profile_L 0.0429 F -> 0.0297 W,
  sleeve_front_profile_L 0.0365 -> 0.0256 W, piece_sleeve_L front 0.865 -> 0.948, R front 0.894 -> 0.954. Costs:
  piece_sleeve_R three_quarter 0.419 -> 0.322 (-23% against the control; -9% against pipeline-3d's 0.353: the far sleeve
  in 3q, where our top is already 0.03-0.06 L above the drawn one while the front's is 0.06 L under: the views disagree),
  piece_sleeve_L profile -4%, back -4%; sleeve_back_profile_L/R 0.066 F -> 0.083/0.086 F (FAIL both; tool/sleeves: the
  drawn back view labels the cap's top as jacket), sleeve_front_profile_R 0.0161 P -> 0.0205 W. `cap` 0.18 (s1/s2)
  cleared the spikes too but made sleeve_front_profile_L a new FAIL (0.0433).
- **(a) the lapels: no change** (measured above: the corner meets the bow as drawn on this base; art_outline_collar
  1.402 P, 1.44 with V1).
- Spec (2b4653d): close_hung.on, pleat.on, sleeve_L.profile = V1, top.bed, bodice_panel.bed (tools/garments4/part1.json,
  setspec.py keeps the file's formatting). Pregate (2b4653d+dirty into 257222b): PASS, 57 moved, 0 blocking.
  pipeline-3d 257222b (tool/hairsplit + the handoff) merged (fe90cb19).

## Part 1: box build, gate, review page
- Box build `charkit/out/g4_part1` (2b4653d): confirms the sweeps. Against g4_before (pipeline-3d's bow): piece_bow
  0.753 -> 0.863 (F/3q/P 0.896/0.758/0.345 -> 0.934/0.855/0.683), bow_front_bleed 0 -> 0 P, sleeve spikes 0 -> 0 P,
  shoulder_back_line (flag) 0.0565 F -> 0.0047 P, art_outline_collar (flag) 1.379 -> 1.442 P, loop_lean 19.9 F -> 0.62 P,
  loop_thick 0.076 F -> 0.031 W, tail_hang 12.6 F -> 0 P, bow_part_knot_iou 0.536 F -> 1.0 P, knot_line 0.904 F ->
  0.046 P, crease_len 1.0 F -> 0.21 P, iso_bow_body 0.679 F -> 0.811 W, piece_top 0.714 W -> 0.775 P, piece_collar
  0.754 -> 0.767. PASS -> WARN (not blocking): body_profile_chest 0.002 -> 0.048, collar_three_quarter_torn 0 -> 0.004,
  sleeve_front_profile_R 0.014 -> 0.021. FAIL -> worse FAIL: sleeve_back_profile_L/R 0.066 -> 0.083/0.086.
  Guard IoUs (before -> after): sleeve_L F/3q/P/B 0.859/0.976/0.983/0.893 -> 0.948/0.986/0.941/0.854; sleeve_R F/3q/B
  0.889/0.353/0.900 -> 0.954/0.323/0.862; top F/3q/P/B 0.492/0.570/0.527/0.914 -> 0.583/0.688/0.620/0.931; bodice_panel
  P 0.169 -> 0.192; collar F/3q/P/B 0.603/0.403/0.025/0.928 -> 0.657/0.470/0.026/0.928.
- **Gate 1** (def9343 into 257222b): FAIL, one blocker: test_bodyeval's knob inventory (the shell's new `bed` not
  listed; bodysens.NOT_KNOBS now lists `bed` and `creases`, 9e5d6f5). Carry refused (the build reads bodysens.py).
- **Gate 2: PASS under K** (9e5d6f5 into pipeline-3d 257222b; `charkit/out/gate/gate_tool-garments4_9e5d6f5_into_257222b.md`):
  no new FAIL, no flag-check regression, build CPU 0.97x, 0 calibration records needed, 0 guard findings; 106 items
  reported. PASS -> WARN: body_profile_chest, collar_three_quarter_torn, sleeve_front_profile_R. Flag values moved,
  grade unchanged: collar_back_lay 0.042 -> 0.061 FAIL (the puffs' raised tops beside the unchanged collar flap),
  collar_back_square 0.325 -> 0.305 FAIL, art_outline_collar 1.379 -> 1.442 PASS. Mergeable (branch head after the notes).
- **Review page:** `charkit/out/garments4/review/part1/index.html` (part1.json beside it; sweep s3's boards). Asked of
  Michael: (1) the knot graded on the front only, (2) w4's slanted loop ends, (3) the loops' bottom at 0.30, (4) the far
  sleeve's 3q cost (0.353 -> 0.323).

## Part 2: started, parked on branch `tool/garments4-part2` (3f2d550d, from def9343a; not gated, not in tool/garments4)
Built and unit-tested (charkit/tests/test_ink.py, test_bed.py pass), not yet box-built:
- **The crease mechanism (a line layer):** `garments.ink_strokes(G, creases, L, frame)` / `with_ink`: strokes given in a
  piece's UV, or `space: 'front'` as (x, z) in L in the QA's front frame (midline, iris eye line: `_eye_z`), placed on
  the piece's level-1 subdivided surface (frontmost for front strokes), `lift` L off it, `width`, `taper`, `tip`;
  appended to the same object on an `<name>_ink` toon slot (one object per garment: the evaluator and the piece masks
  stay as they are), weights from the surface; `outline_w` vertex group 0 on the strokes (_object makes it: shade.outline
  reads it, so no hull on them); `evalmesh.finalize` keeps ink faces out of the venv Solidify. `qa3d.render_surfaces`
  draws `*_ink` triangles as line surfaces (our_lines / partqa read them as lines); `sweep.garment_arrays` gives ink
  vertices no outline shrink. Wired in `garments.build` for the skirt and the hull bow (no-op without `creases`).
- **The measure:** declared family `ink_inside` (declared.py; LINE_FAMILIES) = 1 - recall: the share of the drawn
  creases' skeleton (ink + outfit.ridges faint strokes inside the drawn region, its outline band left out) with none of
  our lines within `tol` 0.015 L; `ours`, `design` lengths and `precision` reported. The generic calibration stand-in
  (declared.Declared) now draws the design's lines with its faint strokes. Declarations in `charkit/creaseqa.py`:
  skirt_panel_{front,three_quarter}_creases (piece skirt, region skirt_panel), bow_{front,three_quarter}_creases;
  limits [0.35, 0.6]; flags Michael's; calibrate known_bad 'g4_before'.
- **Readings (local, `charkit/out/garments4/tools/decl.py`):** g4_before: skirt 0.998 / 1.0 FAIL, bow 0.925 / 0.902
  FAIL; g4_p1 (pleated bow): skirt 0.998 / 1.0 FAIL, bow 0.46 / 0.41 WARN (the pleat's almond and lower crease sit
  0.01-0.02 L off the drawn ones; the drawn almond tops, the spokes from the knot and the knot's side lines are missing:
  `review/inkov_bow_front_p1.png`). The drawn panel has 2 creases in front (~0.9 L each, from z -1.69 to the hem at
  |x| 0.06 -> 0.19), 2.5 L of lines in 3q.
- **Strokes traced from the design:** `python -m charkit.inkfit SPEC PIECE [--region R] [--band] [--min] --build DIR`
  (skeleton -> polylines, RDP, joined across junctions) -> `charkit/out/garments4/strokes_{skirt,bow}_front.json`; the
  ink variant spec `charkit/out/garments4/specs/ink1.json` (= Part 1's spec + skirt and bow `creases`; overrides in
  `tools/garments4/ink1.json`).

### Part 2: exact next steps (lean relaunch)
1. On tool/garments4-part2 (merge tool/garments4 / pipeline-3d first): box-build ink1
   (`remote build charkit/out/garments4/specs/ink1.json --out charkit/out/g4_ink1 --boards '' --no-blend`); check the
   strokes render (Blender: outline_w group present, no hull on strokes; the bundle's materials include skirt_ink /
   bow_ink), the crease checks (`decl.py '*creases*' charkit/out/g4_ink1`), every piece's shape IoU (skirt, bow) and the
   art_* checks. Then sweeps on g4_ink1 as base (its bundle has the ink slots, so spliced strokes read as lines) for
   width/lift and stroke choice (the bow: strokes for the drawn almond tops, spokes and knot sides; consider the pleat's
   almond lens off when the strokes draw it; the skirt: check the 3q recall: the drawn 3q panel shows more folds, maybe
   strokes along the pleats' ridges in UV space instead of front projection).
2. Store the known-bad (`python -m charkit calibrate store g4_before charkit/out/g4_before --why "no creases on the
   skirt's cream panel; pillow bow without wrinkles"`), calibrate `skirt_panel_*_creases,bow_*_creases` (`--build` the
   ink build), commit records; register a MEASUREMENT_STEPS entry if the gate flags qa3d/declared measuring code (values
   on old geometry are unchanged: no ink slots there).
3. Cuffs (item 2): the cream is already measured and calibrated (cuff_{front,back}_trim_{L,R}: FAIL 0.29-0.30 on every
   build: ours have no cream); the size (ours 1.5-2.4x the drawn area, hands round) needs a declared check (width family
   on piece cuff_L/R, or a shape_iou guard) calibrated. The fix exists as code: `garments.cuff` (band `source:
   template`: a frustum with a cream top band and front tab, garments2), never fitted into the spec since the hands
   round moved the arms: fit `span`, `top`, `bottom`, `band`, `tab`, `shift` to the drawn per-view cuffs (sweep), with
   piece_cuff_L/R per view as the guard (before: L 0.614/0.831/0.742/0.636, R 0.604/0.325/0.602).
4. Shoulders + the back view's cream collar (item 3): collar_back_iou 0.745 F, _square 0.325 F, _lay 0.042 F on
   pipeline-3d; the lapels' width at the shoulder (drawn 0.40 L, ours 0.22). tool/collar4's template collar E2 and
   body.shoulder (collar.md rounds 7-8: the guard, torn, neck_crease, art_outline_neck still blocking there) are the
   prior work; Part 1's V1 sleeves already put shoulder_back_line at 0.0047 P.
5. Neck to bow V (item 4): the jacket's `opening` table starts at z -0.72 (half 0), so the V between the lapels above
   the knot is jacket (orange); extend the opening up the collar's V (collar round 1's variant D: the jacket's opening
   carrying the collar's V) so the skin shows, and check neck_crease (26.9 W now) for the neck-chest join.

## Part 2, relaunch (2026-10-01, lean agent)
- tool/garments4-part2 3f2d550d + pipeline-3d c18b0c1 (Part 1 merged) = 5d3a7167.
- Known-bad stored: `calibrate store g4_before charkit/out/g4_before` (charkit/calib/known_bad/g4_before.json; the store
  is charkit/out/calib/builds/g4_before, local).
- Box build g4_ink1 (ink1.json: Part 1's spec + the traced skirt and bow strokes): job build-garments4-1001-005337-96fd,
  out `charkit/out/g4_ink1`, log `charkit/out/garments4/build_ink1.log`.
- **g4_ink1 built** (box, 904 CPU s). Findings:
  1. The QA's render drawing (qarender.view) mapped the export's `*_ink` primitives to the cloth surface, so our_lines
     never saw the strokes (the numpy drawing did): skirt creases read 0.998 with the strokes there. Fixed
     (qarender: ink primitives -> the ink surface; `qa3d.is_ink`). Re-read on g4_ink1: skirt front 0.005 P, **3q 1.0 F**;
     bow front 0.044 P, 3q 0.372 W: front-traced strokes pass only in the view they were traced from.
  2. **The cream panel's shape is off** (not measured before: piece_skirt_panel INFO, "no object builds it"): ours a band
     as wide at the waist as at the hem, the drawn one a triangle (an inverted box pleat). New declared checks
     (creaseqa.py): `skirt_panel_{front,three_quarter,profile}_shape` (shape_iou, close, our skirt's cream pixels vs the
     drawn panel: declared params `drawn` + `ours_cls`) 0.695 / 0.689 / 0.232; `skirt_panel_{front,three_quarter}_edges`
     (ink_inside `edge`: the folds bounding the panel) 0.806 / 0.825 on g4_before.
  3. Two-view triangulation (tools/tri.py): the drawn 3q panel is as wide as the front one (cos 35.5 would make it 0.81x):
     the 3q draws the panel more face-on than any rigid 3D panel can be (its right edge implies a depth 0.33 L behind
     ours, its left edge agrees with ours): the views disagree there (rule 2/3: view-dependent drawing).
  4. sweep's garment splice dropped material slots (all slot 0: no panel, band or ink): fixed (bodyeval bundle pmat).
- Fix in progress: `skirt_hull` `panel_shape` {top, power, scale} (a column warp: the panel tapers to `top` at the waist,
  its edge a clean vertex column); crease strokes in `space: 'panel'` (f across the panel, v down: ride with its shape).
  Sweep k1 (tools/garments4/k1.json, out sweeps/k1): top/power/scale and panel-space creases (+ edge strokes t15e).
- Tools: charkit/out/garments4/tools/side.py (design vs builds side by side round a drawn piece), paneliou.py, tri.py.
- Sweeps k1-k2 (sweeps/k1, k2; stab.py tabulates): the taper (panel_shape top .15, power 1, scale 1.1) takes the panel's
  front shape 0.695 -> 0.91 P; its 3q 0.689 -> 0.665 W; profile 0.232 -> 0.155 F (both FAIL). Recessing the panel (an
  inverted box pleat, `depth` > 0) hides the cream in profile (0.04) and broke skirt_pleats_cream (0 -> 3 F: the knife
  pleats were turned off on the panel): rejected; the knife pleats stay on the panel. Panel-space creases at f 0.55
  read (relative) front 0.34 P, 3q 0.68 F; edges 0.26 P / 0.42 W. Running: k3 (protruding panel, crease placement),
  k4 (the bow's stroke subsets: none, knot sides, + almond tops, + spokes, all but the lower creases).
- Cuffs (item 2) measured: `cuffqa.py` declared `cuff_{view}_area_{L,R}` (new family `area`: |ours/design - 1|):
  0.47-0.65 FAIL, 3q R 1.435 FAIL on g4_ink1. Seed for the template (tools/cuffseed.py): our band span 0.455-0.760 L,
  radii top 0.20/0.16, bottom 0.14-0.17 L.
- k3: protruding the panel (depth < 0) also lost profile cream (0.13/0.10) and broke skirt_pleats_cream: box-pleat depth
  removed. Shape compromise: power 0.7 (ep07) front 0.894 P, 3q 0.698 W (up from 0.689), profile 0.169 (down from
  0.232: the drawn profile shows the pleat's side faces as a cream wedge, which our panel doesn't model; measured by
  tools/paneliou.py, reported, not declared this round: no geometry here reaches it).
- k4/k5 (the bow's strokes): the knot's side strokes break bow_part_knot_iou (1.0 P -> 0.0 F: they split the knot);
  `tops_tips` (strokes 0, 1, 2, 7 of ink1.json: the almond tops and tips) reads front 0.46 W -> 0.337 P, 3q 0.407 ->
  0.379 W, bow_part_crease_len 0.221 -> 0.026 P, knot_iou 1.0 P, piece_bow unchanged (0.934/0.855/0.683).
- k6 running: the skirt creases' f at top/bottom (power 0.7 panel).
- k6 (crease f top/bottom on the power-0.7 panel): front (relative) 0.002 P at f 0.65 -> 0.45 (t65b45); 3q 0.63-0.79 F at
  every placement (front and 3q pull opposite ways; the drawn 3q panel widens on its far side at the hem).
- **Milestone 1 (creases) spec, e3891817:** skirt panel_shape {top .15, power .7, scale 1.1}; skirt creases (panel
  space) f +-0.65 (v .15) -> +-0.45 (hem) and edge folds f +-0.97; bow creases = ink1's strokes 0, 1, 2, 7 (tools/
  garments4/creases.json via setspec.py). Draft `_at` checks dropped; skirt_panel_profile_shape not declared (reported);
  cuffqa.py moved to charkit/out/garments4/defer/ until the cuffs milestone (its checks FAIL until fixed).
- Box build g4_creases running (log charkit/out/garments4/build_creases.log). Next: calibrate the crease checks
  (`calibrate 'skirt_panel_*,bow_*_creases' --build charkit/out/g4_creases`), pregate, remote gate.
- g4_creases (e3891817, box): skirt panel creases front 0.002 P / 3q 0.734 F (relative), edges 0.105 / 0.341 P, shape
  0.894 P / 0.698 W; bow 0.337 P / 0.379 W; guard: no piece over 15% (piece_cuff_R 3q -6.2% the most); PASS -> WARN
  flap_profile_iou_R, flap_profile_sweep_R, skirt_pleats (0.5 -> 2.5: it reads strokes as pleat lines).
- Calibration (log charkit/out/garments4/calib_creases.log): bow front/3q, panel front creases, both edges CALIBRATED;
  3q creases MISCALIBRATED (the design 0.41 against itself: the drawn 3q mask, closed, took in 1621 dark px the class
  region lacks) -> fixed (relative mode: the drawn span by the same class rule); panel shapes BLIND (g4_before 0.69
  WARN) -> declared as the panel's shape guard (no_known_bad, as the piece_* IoUs).
- k7 (crease placement under the fixed measure): f 0.65 -> 0.5 by mid-skirt (t65m50b50) front 0.059 P, 3q 0.597 W.
  Spec updated; box build g4_creases2 running. Then: calibrate the 8 checks on it, pregate, gate.
- Cuff template seed build g4_cuff0 (charkit/out/garments4/specs/cuff0.json) also running.
- **Calibrated on g4_creases2** (charkit/out/garments4/calib_creases2.log; records committed): bow front/3q,
  skirt_panel front/3q creases, front/3q edges CALIBRATED (3q creases' design 0.104-0.108 after the span fix); panel
  front/3q shape GUARD. g4_creases2 readings: skirt creases 0.059 P / 0.591 W, edges 0.103 / 0.308 P, shape 0.894 P /
  0.698 W, bow 0.337 P / 0.379 W; guard vs g4_part1: largest drop piece_cuff_R 3q -6.2%; PASS -> WARN flap_profile_iou_R,
  flap_profile_sweep_R, skirt_pleats.
- **Branches (coordinator: one milestone per gate):** tool/garments4-part2 = the creases milestone (gated alone);
  tool/garments4-cuffs (b5997d73 = part2 + garments.cuff's grow_line) carries the cuffs work; cuffqa.py stays in
  charkit/out/garments4/defer/ until the cuffs milestone. Cuff sweep k8 (tools/garments4/k8.json, base g4_cuff0) running.
- Review page JSON: charkit/out/garments4/review/creases.json.
- pipeline-3d 6620113d (tool/hairshell, opt-in) merged (639339a3). Pregate (639339a3 into 6620113d): PASS, 49 moved,
  0 blocking (`charkit/out/pregate/pregate_tool-garments4-part2_639339a3_into_6620113d.md`; evaluator-only row
  piece_overskirt_panel_L_three_quarter_left -0.151 W -> -0.330 F, not in the gate's QA). Box gate running (log
  charkit/out/garments4/gate_creases.log).
- **Creases gate 1: FAIL under K, 5 blockers** (`charkit/out/gate/gate_tool-garments4-part2_9e35959_into_6620113.md`):
  test_subsurf (evalmesh.finalize read o['materials'] unguarded: fixed) and 4 unregistered remeasures (the render
  drawing now reads the bow's strokes as lines: bow_part_crease_dir/len, iso_bow_crease_dir/len): steps registered
  (steps/partqa, isoqa, artifactqa: a17ec74c), records being refreshed on g4_creases2 (known-bad g3_render3 copied into
  this worktree's store from pieceref's; log charkit/out/garments4/calib_remeasure.log). No new FAIL, no flag regression,
  guard clean, CPU 1.30x. Then gate again.
- g4_cuffs (cuffs branch 2aff9697) built: cuff sizes 0.002-0.055 P (3q R 0.03), trim front 0.086 W / back 0.029 P,
  piece_cuff_L 0.614/0.831/0.742/0.636 -> 0.665/0.869/0.753/0.874, R 0.604/0.305/0.602 -> 0.676/0.741/0.905; hands'
  reach WARN -> PASS (front/back/3q L), hand_shape_R F -> W; PASS -> WARN cuff_back_flare_R 0.02 -> 0.096.
- **Creases gate 2: PASS under K** (312d83d into pipeline-3d 6620113;
  `charkit/out/gate/gate_tool-garments4-part2_312d83d_into_6620113.md`): no new FAIL, no flag regression, CPU within
  1.5x; 8 new checks calibrated/guard, 4 remeasured calibrated. PASS -> WARN: flap_profile_iou_R, flap_profile_sweep_R,
  skirt_pleats. Review page `charkit/out/garments4/review/creases/index.html` (creases.json). Mergeable: tool/garments4-part2
  at the notes commit after 312d83d.

## Milestone 2: cuffs (branch tool/garments4-cuffs = part2 + the cuff work)
- garments.cuff: rows grow by the lowest straight line over each row's clearance need (grow_line; row by row made
  ripples where rows caught a ring of forearm vertices). Review pages: close-ups drawn from the bundle when a build has
  no boards. declared `area` counts piece_<id>'s pixels (same-colour layers left out: the drawn far cuff in 3q lies over
  the orange skirt; raw masks read it 0.7-1.0 FAIL in every row).
- Sweeps k8 (one knob at a time on g4_cuff0) and k9 (combinations): row F = span [0.48, 0.72], top [.17,.14,.17,.14],
  bottom [.13,.115,.12,.115], band 0.3, tab [0.08, 0.5], thick 0.012, clear 0.003: sizes 0.008-0.056 P, trim front
  0.086 W / back 0.029 P, flare back 0.06 / front 0.079 P, piece_cuff_L 0.665/0.869/0.753/0.874, R 0.676/0.741/0.905
  (pipeline-3d: L 0.614/0.831/0.742/0.636, R 0.604/0.305/0.602). In the spec (tools/garments4/cuffs.json); box build
  g4_cuffs running. Next: calibrate cuff_*_area_* (known-bad g4_before), pregate, gate tool/garments4-cuffs (after the
  creases gate's result; merge pipeline-3d first if it moved).
