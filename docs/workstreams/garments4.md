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
- Cuffs branch: part2 merged (e39cb1a7, notes conflict resolved by keeping both). The size checks renamed
  cuff_<side>_<view>_size (01eab65c: calib/details.py's cuff_*_L / cuff_*_R entries matched cuff_*_area_L first).
  calibrate filters names by the build's qa.json part_checks, so the QA is rerun locally on g4_cuffs under the new names
  (charkit/out/g4_cuffs_q: symlinks to g4_cuffs + qa/ rerun; log charkit/out/garments4/qa_cuffs_q.log), then
  `calibrate 'cuff_L_*_size,cuff_R_*_size' --build charkit/out/g4_cuffs_q` (log calib_cuffs.log). Then pregate, gate
  tool/garments4-cuffs. Review JSON: charkit/out/garments4/review/cuffs.json.
- **Cuff size: the measure's reference is wrong, the fit overshot (stop point of this round).** Calibrating
  cuff_*_size: the design moved 1-2 px reads 0.234-0.243 against itself (MISCALIBRATED front/back) because the stand-in
  (calib/labels.Garments) hands the drawing's lines to the nearest piece: the drawn cuff's silhouette (outline split) is
  ~1.23x its fill mask, and our geometry's silhouette (the renderer's hull sits on it) compares with the silhouette,
  not the fill. Against the silhouette: g4_before 1.24-1.33x (3q R 1.85x), g4_cuffs 0.79-0.83x (too small now); the
  hands round's "1.5-2.4x" was against the fill. piece_cuff (fill masks, iou_tol) prefers the smaller cuffs.
- **Cuffs next steps:** (1) `area` against the drawn silhouette (the masks with the drawing's lines given to the nearest
  piece, as labels.Garments builds them; unit test); re-measure g4_before / g4_cuffs; calibrate (expect before
  1.24-1.33x: set limits from the defect, e.g. FAIL over 20%, and say so); (2) refit the template to ~1.0x silhouette
  (k8: top21 reads 1.21-1.29x fill; k9 F 0.95-1.0x fill) with piece_cuff per view as the guard and the trim/flare
  checks; (3) box build, calibrate on it, pregate, gate tool/garments4-cuffs (it carries part2: merge pipeline-3d first).
  Keep: grow_line (straight sides), the trim band + front tab (back trim 0.03 P, front 0.09 W), cuff_R 3q ungraded
  (the drawing's skirt covers the far cuff: Michael's "far cuff shows in 3q", an arm-placement matter).
- Items 3 (shoulders + the back collar's cream section) and 4 (the neck-to-bow V) not started this round.

## Milestone 2: cuffs, relaunch (2026-10-01, lean agent 2)
- tool/garments4-cuffs 918aad4f + pipeline-3d d0d6304 (creases merged) = 9f471f7d.
- **The size remeasured against the drawn silhouette** (bffdfe4a): `declared.area` ref 'silhouette' (default) reads the
  drawn piece from `bodymeasure.drawn_labels` (the drawing as our label image: the lines inside the figure given to the
  nearest piece; calib.labels.Garments now builds its stand-in with the same function); `ratio`, `fill`, `ratio_fill`
  carried into qa.json. Unit test test_declared.test_area_against_the_drawn_silhouette. Limits [0.1, 0.2] from the
  defect. Step registered (charkit/steps/cuffqa.py: cuff_*_size, bffdfe4a).
- **Calibrated** (log charkit/out/garments4/calib_cuffs2.log, records 79c99706): all six CALIBRATED: design 0 every
  move, g4_before 0.237-0.331 FAIL, voronoi floor FAIL. g4_cuffs reads 0.168-0.214 (0.79-0.83x: WARN/FAIL).
- Readings (tools/cuffm2.py; cuffdim.py, pcent.py: extents): ours sits medial and short of the drawn silhouette: front
  cuff_L x [0.818, 1.190] vs drawn [0.851, 1.256], top z -1.766 vs -1.724 (bottom -2.10 vs -2.11); back/3q: inner edge
  as drawn, outer 0.033-0.037 short; profile: ours 0.334 tall x 0.268 wide vs drawn 0.301 x 0.311.
- Refit sweep k10 (tools/garments4/k10.json, base g4_cuffs, box; out sweeps/k10): `out` radius +0.03/+0.04, shift out
  0.01, front/back radii +0.02, span [0.45, 0.73], scale 1.1, combinations.
- **k10** (648 s; sweeps/k10/sweep.md): sizes (L f/3q/p/b, R f/b) and the guard (piece_cuff_L f/3q/p/b, R f/3q/b):
  control 0.196/0.168/0.177/0.206, 0.214/0.208 | L 0.665/0.869/0.753/0.874, R 0.676/0.741/0.905. **span [0.45, 0.73]**:
  0.057/0.033/0.054/0.066, 0.079/0.072 all PASS | L 0.620/0.761/0.667/0.841 (3q -12%, p -11% vs control; vs pipeline-3d
  0.614/0.831/0.742/0.636: -8%/-10%), R 0.635/0.687/0.873; trim front 0.092 W, flare front 0.089 W (was 0.079 P).
  `out` +0.03 cost the profile IoU 16-36% (guard), `fb` +0.02 alone fixes the profile size (0.059) but front/back
  sizes worsen (0.22-0.24). The views disagree on the cuff's top: front's drawn top -1.724, profile's -1.79 (ours
  -1.766 in both): the longer span is the compromise. k11 running: span x fb {0, .01} x out {0, .015}.
- **k11** (span x fb x out; sweeps/k11): pick **s45_730_f1_o0** (span [0.45, 0.73], front/back radii +0.01): sizes
  0.089/0.043/0.0/0.101 (L f/3q/p/b), 0.098/0.091 (R f/b); flares all PASS (back R 0.096 W -> 0.069 P), trim front
  0.094 W, back 0.045 P; guard vs control worst -13.6% (cuff_L 3q 0.869 -> 0.751), vs pipeline-3d's cuffs (L
  0.614/0.831/0.742/0.636) L 0.620/0.751/0.688/0.857: 3q -9.6%, p -7.3%. `out` +0.015 makes every size PASS but costs
  the profile/3q IoU 16-18% vs control (13.7% vs pipeline-3d: too near the guard). In the spec (tools/garments4/
  cuffs2.json via setspec.py); box build g4_cuffs2 running (log charkit/out/garments4/build_cuffs2.log).
- **g4_cuffs2** (76826e3f, box): sizes L f/3q/p/b 0.089/0.043/0.0/0.101 W, R f/b 0.098/0.091 (0.90-1.0x the silhouette);
  trims back 0.045/0.043 P, front 0.094/0.093 W; flares all PASS; piece_cuff_L 0.620/0.751/0.688/0.857, R
  0.633/0.686/0.886. Overlays (tools/cuffov.py, review/cuffs2_ov/): ours sits ~0.05 L inward and lower than the drawn
  cuff in front: the arm's place (hands workstream), not the cuff.
- **Cuffs gate: PASS under K** (76826e3 into pipeline-3d 1d57838, which moved: tool/hairshell2;
  `charkit/out/gate/gate_tool-garments4-cuffs_76826e3_into_1d57838.md`): no new FAIL, no flag regression, CPU within
  1.5x; 6 new checks calibrated; improved: trims (back FAIL -> PASS, front FAIL -> WARN), cuff_back_flare_L, the hands'
  reach (front/back/3q WARN -> PASS), hand_shape_R F -> W, skirt_pleats W -> P; guard: piece_cuff_L 3q -10%, profile -7%
  (the rest up). No PASS -> WARN. Review page `charkit/out/garments4/review/cuffs2/index.html` (cuffs2.json). Mergeable:
  tool/garments4-cuffs at this notes commit.
- Cuffs pregate (`pregate --pair tool/garments4-cuffs --into pipeline-3d`, 76826e3f into d0d6304c): PASS, 47 moved, 0
  blocking (charkit/out/pregate/pregate_tool-garments4-cuffs_76826e3f_into_d0d6304c.md).

## Milestone 3: the shoulders and the back collar (branch tool/garments4-shoulders from the cuffs head 76826e3f)
- Seen (review/shoulders/top_g4_cuffs.png, shline_g4_cuffs.png): ours dips 0.07-0.09 L at |x| 0.30-0.35 in front and
  back between the collar's edge and the puff (the drawn line is level there, -0.47..-0.50); the outer puff 0.03-0.05 L
  low; the drawn back panel is square (half-width 0.40 -> 0.36, top -0.49, flat bottom -0.90), ours a rounded flap
  (0.15 at the top, a point at -0.94). The drawn line at the figure's edge is 5 px (0.0235 L) wide and our_lines put
  ours inside our silhouette: our geometry compares with the drawn silhouette (collarqa's shoulder_back_line reads the
  fill: 0.0047 PASS there is 0.019 L under the silhouette).
- Code: c95cd257 = tool/collar4's garments.py + code_base.py (off by default: outline split/top, stand, drape, stripe
  cut, body.shoulder.join), its checks left out. ca32ff7a: declared family `top_line` (dz / slope / trough over x bands,
  the lower edge not under hair) + `ref` 'silhouette' for any family; tests.
- Draft declarations charkit/out/garments4/drafts/shoulders.json (tools/declm.py): g4_cuffs front top 0.033 F, tilt
  0.203 F, dip 0.052 F; back top 0.019 W, tilt 0.086 P, dip 0.042 F; 3q top 0.042 F (ours ABOVE: the views disagree,
  Part 1's far-sleeve note) -> 3q reported, not declared; collar_back_rows (width rms, silhouette) 0.147 F.
- Box builds (collar4's body.shoulder {z -.525, x .47, join} + collars; specs charkit/out/garments4/specs/, overrides
  tools/garments4/sh_*.json): g4_sh0 (body.shoulder only) build-garments4-1001-034242-aa9c, g4_shA3 (+ collar A3)
  -034301-4999, g4_shE2 (+ collar E2) -034321-8333; logs charkit/out/garments4/build_sh*.log.
- **Calibrated** (charkit/out/garments4/calib_shoulders.log; QA rerun on g4_cuffs2 as g4_cuffs2_q; known-bad g4_cuffs2
  stored): shoulder_{front,back}_top, _dip, shoulder_front_tilt, collar_back_rows all CALIBRATED (design 0-0.03 every
  move; known-bad FAIL; voronoi floor FAIL, but shoulder_back_dip's passes). On g4_cuffs2 they read 0.033 F / 0.019 W,
  0.052 F / 0.042 F, 0.203 F, 0.147 F: **they must reach WARN or better before a gate** (new FAILs block).
- Variant builds against g4_cuffs2 (tools/kcmp.py: K's view, the guard at -10%; declm.py the shoulder checks):

| build | dips f/b | top f/b | tilt f | back rows | blockers under K |
|---|---|---|---|---|---|
| g4_cuffs2 | 0.052 / 0.042 | 0.033 / 0.019 | 0.203 | 0.147 | (base) |
| sh0: body.shoulder | 0.005 / 0.005 | 0.028 / 0.019 | 0.104 | 0.194 | art_outline_collar P->F (back: the jacket through the hull collar's top), neck_crease 26.9 W -> 61.5 F |
| shA3: + A3 collar | 0.005 / 0 | 0.033 / 0.019 | 0.161 | 0.079 | art_outline_collar F (front 3.9), neck F, guard piece_top f -25% 3q -15% |
| shE2: + E2 collar | 0.005 / 0 | 0.021 / 0.019 | 0.091 | 0.065 | art_outline_collar F (front 4.7), art_outline_neck F (3q 8.7), neck_crease 57.4 F, guard collar 3q -15.3% |
| cA3: A3, no body.shoulder | - | - | - | - | collar front -56%, neck 35 F, spikes F: the template collar needs the shoulders |
| cE2: E2, no body.shoulder | 0.047 / 0.028 | 0.038 / 0.019 | 0.191 | 0.097 | neck 38.2 F, art_outline_collar F, collar 3q -18% |

  E2 + body.shoulder looks closest to the design in every view (review/shoulders/side_vars.png: the lapels with their
  stripe in front and 3q, the square back panel), but carries tool/collar4's blockers. The corners (tools/corners.py,
  c_E2.png, c_A3.png): the collar's outer ends where the hair crosses its top (x +-0.36..0.41, z -0.48..-0.51), the
  lapels' inner corners at the neck (x +-0.12, z -0.52) and where they meet the bow (x +-0.08, z -0.65).
- **The jacket's shoulder pad** (garments.shoulder_pad, a shell's `pad` {lift [[|x|, dz]], nz, smooth}; also on the
  hull collar): the body untouched (no neck_crease or hair refit), the jacket's (and collar's) upward faces raised to a
  level shoulder. Sweep k13 (base g4_cuffs2, hull collar; tools/garments4/k13.json) running.
- k13 (pad on the hull collar, base g4_cuffs2): the dips go (front 0.052 -> 0.014, back 0.042 -> 0.005 at lift x1.0),
  collar_back_lay (flag) 0.061 F -> 0.024 P, shoulder_back_slope W -> P (x1.3); but art_outline_collar 1.45 P -> 3-3.9 F
  (the padded jacket shows round the hull collar's edges, review: sweeps/k13 boards) and piece_top front -15%.
  shoulder_front_top stays 0.033 F: the puffs' outer slope (|x| 0.55-0.75) is 0.03-0.05 L under the drawn one.
- k14 (+ the hull collar draped over the padded jacket, + the puff's upper stations' `out` +0.03/0.05): the drape
  wrecks the hull collar (front -28%, 3q -33%, corners 4-4.8 F); the puffs' `out` +0.03 takes the front/back top to
  0.014 / 0.005 PASS but tilt 0.20 -> 0.30-0.33 F and sleeve_R 3q -15%.
- k15 (hybrid template collars on base g4_shA3: E2's lapel table without the stand, H1-H5) running (log sweeps/k15.log;
  started detached, no notification: read the log).
- **Item 4 (the neck-to-bow V), measured:** declared family `class_iou` (fed2ef44): neck_v_front_skin (skin IoU in
  x +-0.2, z -0.45..-0.75; draft charkit/out/garments4/drafts/neckv.json) 0.476 FAIL on g4_cuffs2 (ours 0.028 L^2 of
  skin there, drawn 0.060), shE2 0.415, shA3 0.424. Drawn V: skin half-width 0.15 at -0.475 tapering to 0.06 at -0.70;
  ours ends at -0.55 (the jacket's opening starts at -0.72). Box builds g4_nv1 (top.opening + the drawn V rows),
  g4_nv2 (x0.85) running (specs charkit/out/garments4/specs/nv*.json, overrides tools/garments4/nv*.json).
- Plan: item 4 gates first on its own branch (tool/garments4-neckv from the cuffs head + the declared families,
  without shoulderqa's checks, which FAIL until the shoulders land).
- k15 (base g4_shA3: A3 + E2's lapel table without the stand, H1-H5): H1 repairs A3's guard (piece_top front 0.437 ->
  0.544, 3q 0.584 -> 0.662; vs g4_cuffs2's 0.583/0.688: -7%/-4%), keeps the dips at 0.005/0, collar_back_iou 0.81 W,
  square P; but art_outline_collar (numpy drawing) 3.4-5.6 FAIL and art_outline_neck ~5 FAIL in every row, and the
  collar's profile IoU 0.028 -> 0.021 (a sliver). **Shoulders parked here** (the coordinator's queue: the neck V, then
  the staircase): what blocks is tool/collar4's corners: art_outline_collar (the collar's outer ends at the puff and
  hair, the lapels' corners at the neck and the bow) and art_outline_neck (3q: the collar's top edge meeting the neck).
  Best candidate: body.shoulder + H1 (spec: sh0.json + k15's H1 collar). Next: corners.py on an H1 box build, round the
  lapels' neck corners and the outer ends (the front table's first rows; the top edge easing down into the puff).
- **The V:** g4_nv2 (top.opening's V rows x0.85): neck_v_front_skin 0.476 F -> 0.765 W, art_outline_neck 1.684 W ->
  1.472 P; but neck_crease 26.9 W -> 55.3 F (column -25): the opened V shows the body's own join, which reads 40-45
  degrees all round on the whole skin (neck_crease_all 44.7 on every build): the neck turns into the chest within
  ~0.02 L under the cut (NECK_BASE 0.12 L loft). New knob body.neck_join (code_base; default unchanged): builds
  g4_nv2j18 / g4_nv2j24 (neck_join 0.18 / 0.24) running.

## The staircase hem (coordinator, Michael 2026-10-01: square steps, risers on the creases, crease spacing): measured
- Tool `charkit/out/garments4/tools/stairm.py BUILD` (the band's top edge per piece and view from skirtqa's machinery,
  RDP-simplified into risers and treads; tilt of risers from vertical and treads from horizontal; creases = lines
  reaching within 0.06 L over the band's top; treads crossed by a crease; riser-to-crease distance; crease spacing).
- The design (front skirt): risers 21-24 deg off vertical, treads 13-16 deg off horizontal: the steps are square (the
  corner ~90 deg) but the whole stair follows the pleat folds' fan and the hem's slope; every riser sits on a drawn
  fold (riser-crease 0.026-0.035 L next to the panel), no tread crossed. 3q likewise (risers 14-27, 0 crossed). The
  flaps: risers ~2 deg, treads 22-29 deg (along the flap's slanted hem), risers 0.002-0.007 L from a crease.
- Ours (g4_cuffs2): skirt risers 16-22 deg but treads 2-11 deg (level): the corners sheared by 10-20 deg; risers
  0.2-0.4 L from any crease, 2 treads crossed (front); the flaps' treads level (2-5 deg, drawn 22-29). Our pleat folds
  aren't lines (the skirt's knife pleats are geometry plus a faint texture line), so our_lines sees only the panel's
  edges near the hem: the crease measure on ours needs the folds' azimuths (geometry) or inked folds.
- The cause: band_rows' stair is per column at azimuth knots [0, 14, 28] deg out from the panel's edge while the 18
  knife pleats fold every 20 deg (outer folds at 0, +-20, +-40 deg, inner at +-10, +-30...): risers mid-pleat, treads
  across folds; the treads at constant v (a share of each column's length), not along the hem's local slope.
- Plan (not started): a declared/calibrated check on the corner angle (riser vs tread, |90 - angle| beyond the
  design's) and riser-on-fold / tread-crossing counts per view (front, 3q; skirt and flaps), the crease spacing (pleat
  widths) against the drawn folds' spacing; then the stair knots on the pleat folds (risers on folds), the treads along
  the hem, the pleat count/phase fitted jointly to the drawn fold spacing; the merged crease checks must stay PASS.
- **The join, tried:** g4_nv2j18 / g4_nv2j24 (body.neck_join 0.18 / 0.24 with nv2's V): neck_crease 48.2 / 52.8 FAIL
  (no better), and the longer loft moves the body's shoulders: sleeve_front_spikes_L/R 0 -> 0.02-0.027 FAIL,
  shoulder_back_slope W -> F, art_outline_collar P -> W, piece_collar front -13% / -34%; j18 also
  collar_profile_torn 0 -> 0.021 F. Not the fix.

## Stop point (2026-10-01, lean agent 2, ~520k): what's gated, what's next
- **Gated:** the cuffs (tool/garments4-cuffs 28f088c2, PASS under K into 1d57838; review
  charkit/out/garments4/review/cuffs2/index.html).
- **Not gated (no candidate clears K):** the shoulders + back collar, the neck V. Branch tool/garments4-shoulders
  carries: collar4's builder code (c95cd257, off by default), declared families top_line / class_iou and `ref`
  'silhouette' (ca32ff7a, fed2ef44; tests), charkit/shoulderqa.py (6 checks CALIBRATED, 2428729c; they FAIL on the
  default, so this branch can't gate before the shoulders are fixed: or move shoulderqa.py to defer/ to gate the rest),
  garments.shoulder_pad + the hull collar's pad/over (k13/k14: not taken), code_base body.neck_join (default unchanged).
  Shoulders review page (options, asks Michael): charkit/out/garments4/review/shoulders_page/index.html.
- **Next, the shoulders (a collar milestone):** base body.shoulder + k15's H1 collar (A3 + E2's lapel table, no stand):
  dips PASS, panel square PASS, guard ok, neck_crease 26 W; blockers art_outline_collar (front: the collar's outer ends
  at the puff/hair x +-0.35..0.41 z -0.48..-0.52; 3q: those and x -0.07 at the neck) and art_outline_neck (3q 3 corners:
  the collar's top edge meeting the neck, x 0.13-0.21 z -0.49..-0.53). Box-build H1 (sh0.json + k15's H1 collar), run
  tools/corners.py on it, then round the outer ends (the front table's top rows easing the outer edge down under the
  puff) and the neckline by azimuth (outline.top) in a garments sweep on that base; keep shoulder_front_top <= 0.03
  (the puffs' outer slope is 0.03-0.05 L low: sleeve `out` +0.03 fixes it but tilt FAILs: fit top/tilt jointly).
- **Next, the neck V (item 4):** nv2's opening rows (tools/garments4/nv2.json) give neck_v_front_skin 0.476 -> 0.765
  WARN and art_outline_neck W -> P; what blocks is neck_crease 26.9 -> 55.3 F: the body's own neck-to-chest turn (the
  whole skin reads 40-45 deg in every column; the V now shows columns -25..25). Fix the join's shape, not its reach:
  the monotone cubic from the cut (neck_curve) turns from vertical to the chest's flare within ~0.02 L; ease the head's
  neck slope into it over 0.04-0.06 L above the cut (code_base.blend_neck / neck_curve), or a front-only join table
  that keeps the sides (neck_join as [[0, .18], [40, .12], [180, .12]] keeps the shoulders' rows as they are). Then
  declare neck_v_front_skin (draft charkit/out/garments4/drafts/neckv.json; class_iou, limits [0.8, 0.6], known-bad
  g4_cuffs2), calibrate, and gate it alone (branch from the cuffs head + c95cd257 + ca32ff7a + fed2ef44 + f6e33039,
  without shoulderqa.py).
- **Next, the staircase (lean relaunch):** see "The staircase hem" above: the check (corner angle |90 - angle| beyond
  the design's per view; risers on folds and treads crossed by a fold as defects; crease spacing against the drawn
  folds' spacing), calibrated (design jittered 1-2 px PASS, g4_cuffs2 FAIL); then the stair's azimuth knots on the
  pleat folds (band_rows `stair` knots at the folds' azimuths: 18 pleats -> folds every 20 deg from the front), treads
  along the hem's local slope, pleat count and phase fitted jointly to the drawn fold spacing per view; the merged
  crease checks (skirt_panel_*_creases/_edges/_shape, bow_*_creases) stay PASS.

## Relaunch 3 (2026-10-01, lean agent 3): the queue
Coordinator's order (Michael's review): (1) the staircase, branch `tool/garments4-stairs` from pipeline-3d 31689611;
(2) the body's neck-chest join, branch `tool/garments4-neck` from pipeline-3d; (3) a new isolated reference; (4) the V;
(5) flat lapels. Gate each. Not ours: the shoulders/back collar (Michael's two calls; E2/A3 superseded by item 5); hair.
- **Item 2 adds (coordinator 2026-10-01):** (a) a manifest caution on `garment_breakdown`: its flat-lay's bodice V shows
  the inside of the back panel (orange), not the bodice front; the turnaround's V is skin; nothing reads the flat-lay's V
  as the blouse front. (b) Reference generation (Michael's general approval; one call, n=2, tools/gptimage.py, ledger):
  the blouse as worn WITHOUT the bow, front / three-quarter / side / back, one scale, orthographic, `--ref` the
  turnaround: the sailor collar flat over the shoulders and chest, the stripe along its edges, a low band at the back
  of the neck, the V opening showing skin down to where the bow sits. Refcheck against the turnaround (bodice and collar
  silhouettes, the V's shape); register only if it passes, as the shape authority for the lapels, the V and the bodice
  front (shape vs placement split, as the bow's close-up). (c) The lapels are wide flat panels whose inner edges form
  the V down to the knot (ours bunch into lumps beside the neck): after the V opens, a lapel template lying flat along
  the V's edges, scored per view on lapel shape and width along its length; re-judge art_outline_collar after it.

## Milestone 1: the staircase (branch tool/garments4-stairs from pipeline-3d 31689611)
- **Measured** (declared family `stair` in charkit/declared.py; checks in charkit/stairqa.py; tools
  charkit/out/garments4/tools/stairdbg.py (overlays) / stairseg.py (segments) / stairchk.py (the checks on builds)):
  the face/band boundary traced as a sub-pixel outline (skimage find_contours) where the band lies along its outward
  normal within 0.03 L, RDP'd into risers and treads; corners = 90 less the acute angle between consecutive segments'
  principal axes (the middle 70% of each one's points); folds = drawn ink (design) or our lines + our geometry's folds
  (declared.our_folds: face normals z-buffered, smoothed 1.5 px, a turn of >= 15 deg across +-4 px, thinned) reaching
  within 0.08 L of the band; a fold meeting a tread > 0.02 L inside its ends = crossed.
- Design: corners square (median 4.4 skirt front, 6.0 skirt 3q, flaps 6.4 / 9.2), no tread crossed. The turnaround
  draws its first wide pleat face with 3 steps (2 risers mid-face) and one fold line per side in front; the closeup
  (skirt_closeup.png) draws one step per pleat, risers on the folds (rule 2: the closeup is the pleat-structure authority).
- g4_cuffs2 (= known-bad g4_stairs0, stored): crossed front 5 / 3q 3; corners skirt 13.3 / 11.9, flaps 17.8 / 28.0;
  our fold spacing at the band 0.16 / 0.13 L vs the drawn steps' 0.15 / 0.14 (spacing already right: one face = one step).
- Cause: band_rows' stair knots [0, 14, 28] deg from the panel edge (27 deg unwarped) vs the zig's folds every 10 deg
  (ridges at 0, +-20, +-40.., valleys at +-10, +-30..: the texture's fold lines are the valleys); the skirt's treads
  run level (3D-square to the folds, sheared in the ortho views where the folds lean with the flare); the flaps' treads
  run along the hem while their columns hang slanted (3D-sheared).
- Knobs (default unchanged): skirt `panel_snap` (the panel edge on the nearest fold: 27 -> 30 deg, with
  panel_shape.scale 1.1 -> 0.99 to keep the drawn panel), band `stair_unit: 'fold'` (knots count folds out from the
  edge: one face per step), band `lean` (L/deg: treads rising outward, per-column band rows), flap `square` (0..1:
  treads turned perpendicular to the columns' hang).
- Sweep st1 (tools/garments4/st1.json, box; out charkit/out/garments4/sweeps/st1): snap, fold, fold + lean 2/4/6e-3,
  flap square 0.5/1, fold_l4 + square 1.
- Coordinator (2026-10-01): tool/layerrefs merged into pipeline-3d: the garment_breakdown flat-lay caution is already in
  the manifest (don't duplicate); new references: the base body inside the costume (for the neck-chest join; its
  profile cautioned only at the back thigh) and the hair without its clips. The bow-less bodice + flat collar sheet is
  still ours to generate (milestone 2). Merge pipeline-3d before the next gate.

## Next, milestone 2 (for the lean relaunch; coordinator: neck join, then reference, then the V, then flat lapels; gate each)
1. **Neck-chest join** (branch tool/garments4-neck from pipeline-3d after layerrefs, 393539e7+): measure first. The
   check is faceregion.neck_crease (per column round the neck, the skin outline's bend over the join window CUT -0.52 L,
   -0.10/+0.08 L; masked skin) and neck_crease_all (whole skin, INFO: 44.7 on every build). Reference: the new base-body
   reference (tool/layerrefs: the body inside the costume; profile cautioned at the back thigh only): measure our body's
   neck-to-chest front and profile silhouettes against it (declared shape/width-profile family on the skin in the window
   z -0.45..-0.75, front and profile). Fix the shape, not the reach (body.neck_join 0.18/0.24 made it no better and
   moved the shoulders: tool/garments4-shoulders f6e33039): ease the head's neck slope into the chest over 0.04-0.06 L
   above the cut in code_base.neck_curve / blend_neck (the monotone cubic turns vertical -> chest flare within ~0.02 L
   under the cut, NECK_BASE 0.12 L loft). Guard: skin, neck and torso IoUs per view; face/jaw checks (faceregion,
   jaw_*) hold. Gate the join alone.
2. **Reference**: one gptimage call, n=2, tools/gptimage.py, ledger: the blouse as worn WITHOUT the bow, front / 3q /
   side / back, one scale, orthographic, --ref the turnaround (sailor collar flat over shoulders and chest, the stripe
   along its edges, a low band at the back of the neck, the V showing skin down to where the bow sits). Refcheck with
   charkit/layerref.py against the turnaround (bodice and collar silhouettes, the V's shape); register only if it
   passes, as the shape authority for the lapels, the V and the bodice front (the garment_breakdown caution is already
   in the manifest).
3. **The V**: nv2's opening rows (tools/garments4/nv2.json on tool/garments4-shoulders) gave neck_v_front_skin 0.476
   -> 0.765 and art_outline_neck W -> P; blocked by neck_crease 26.9 -> 55.3 until (1) lands. Declare
   neck_v_front_skin (class_iou family from fed2ef44; draft charkit/out/garments4/drafts/neckv.json), calibrate, gate.
4. **Flat lapels**: a lapel template lying flat along the V's edges, scored per view on lapel shape and width along its
   length (declared width-profile family against the new reference); then re-judge art_outline_collar (its FAILs
   likely the stand-up lumps). Supersedes the shoulders branch's E2/A3 question.
- **Sweeps st1-st5** (tools/garments4/st*.json; outs charkit/out/garments4/sweeps/st1, st4; local rebuilds
  tools stairrow.py / rowqa.py): anchoring the pleats on the panel's edge (a valley on it) + the stair on those folds
  fixed crossing and corners but broke skirt_panel_three_quarter_creases (W -> F: the cream's edge face changed) and
  art_band_lower (W -> F, 2.09: the flag) and moved skirt_pleats P -> W; keeping the panel's own pleats (outer-only
  anchoring) still broke the 3q creases; leaning treads (per-level rows) helped corners but rounded under the
  subdivision. **The fix that holds**: the original pleats, the knots in degrees on the existing folds (40/50/60 deg:
  13/23/33 out from the panel's edge at 27) with a fourth step 0.10 L, and the flaps' treads squared to their hang
  (flap `square` 2.0: 1.0 is perpendicular to the columns in 3D, 2.0 reads square in front; a dial). deg4_sq2 (local,
  vs g4_cuffs2): crossed 0 / 0 (2 F / 1 F), skirt corners 2.9 P / 0.5 P (8.9 F / 6.0 F), flaps 4.0 W / 0.0 P (11.4 F /
  22.2 F), art_band_lower 1.623 W (1.693 W), skirt_panel_* and skirt_pleats* unchanged, piece_overskirt_panel_L/R
  0.697 / 0.821 (0.691 / 0.812). The anchoring/lean code was removed (7a6d6af5); calibrate's draft-check filter fixed.
- Merged pipeline-3d 393539e7 (92cfd7f5). Box build g4_stairs1 (the default spec) next; then calibrate 'stair_*' on it,
  pregate, gate.
- Coordinator (2026-10-01): Michael says yes to the base body reference's profile for the torso: use
  base_body_turnaround (pipeline-3d 393539e) for the neck-chest join (milestone 2, step 1). skirt_layers take 1 is
  being registered as the structure authority for the panel and pleats without the flaps; its flaps-alone row is the
  shape authority for the staircase's edges. The staircase milestone converged on the turnaround before it landed:
  follow-up (after this gate) = re-measure the stair family against skirt_layers (the pleat widths at the sides: the
  flat band beyond the stair still crosses the side pleats, 2 front / 1 3q, reported not counted) and the flaps-alone
  row (the flap square dial 2.0).

## Stop point (2026-10-01, lean agent 3, wrap-up: weekly capacity 95%; box SSH dropping)
- **Branch tool/garments4-stairs** (head = this notes commit; code at d29f54c4 + notes): pipeline-3d 393539e7 merged.
  Carries: declared family `stair` + `our_folds` (charkit/declared.py), charkit/stairqa.py (stair_{front,three_quarter}
  _crossed [0, 0], stair_skirt_{view}_corner and stair_flaps_{view}_corner [3, 5], known-bad g4_stairs0 stored in
  this worktree's calib store), calibrate's draft-check fix, the flap `square` knob, the spec (skirt stair knots
  [[0,.35],[13,.25],[23,.15],[33,.10]], overskirt_panel_L square 2.0), test_declared's stair test, CODEMAP.
- **Running when stopped**: box build g4_stairs1 of the default spec, job `build-garments4-1001-065031-2168`
  (out charkit/out/g4_stairs1, log charkit/out/garments4/build_stairs1.log). If the local follow died: `python -m
  charkit remote attach build-garments4-1001-065031-2168` to collect it (or rebuild: `remote build
  charkit/spec/clawd.json --out charkit/out/g4_stairs1 --boards '' --no-blend`).
- **Exact next steps, the staircase** (no gate run yet):
  1. On g4_stairs1: `python -m charkit calibrate 'stair_*' --build charkit/out/g4_stairs1` (a dry run on g4_cuffs2
     before the crossing fix: corners CALIBRATED (skirt and flaps, front and 3q); crossed was MISCALIBRATED by the
     panel-edge folds, fixed since (margin 0.035 L, steps only) and must be re-run; the spacing measure was dropped
     from the declarations: the turnaround draws only some folds). Commit charkit/calib/records/stair_*.json and
     charkit/calib/known_bad/g4_stairs0.json (committed).
  2. Expected on g4_stairs1 (local rebuild deg4_sq2 against g4_cuffs2): crossed 0 / 0, skirt corners 2.9 / 0.5 P,
     flaps 4.0 W / 0.0 P; art_band_lower 1.62 W (control 1.69 W); skirt_panel_*, skirt_pleats*, bow creases unchanged;
     piece_overskirt_panel_L/R 0.697 / 0.821 (0.691 / 0.812). Check the guard and flap_profile_sweep_L (0.075 -> 0.08,
     its PASS limit).
  3. `python -m charkit pregate` locally, then `python -m charkit remote gate tool/garments4-stairs --into pipeline-3d`.
  4. Review page (charkit/out/garments4/review/stairs.json -> `charkit review page ... --open`): design | before
     (g4_cuffs2) | after (g4_stairs1) front and 3q crops, the stair overlays (tools/stairdbg.py), the numbers above.
     Ask Michael: (a) the flap square dial 2.0 (1.0 is perpendicular in 3D; 2.0 reads square in front) yes/no;
     (b) the flat band beyond the fourth step still crosses the side pleats (2 front / 1 3q, reported, not counted):
     leave it, or step every side pleat (crenellation tried: read as pixel stairs) or widen the side pleats per
     skirt_layers; (c) lean treads (squarer in front, rounded by the subdivision) declined.
  5. Follow-up with the new references: skirt_layers take 1 (panel/pleat structure) and its flaps-alone row (the
     staircase edges' shape authority): re-measure the stair family against them.
- **Neck join, bodice reference, V, flat lapels**: the exact steps are in "Next, milestone 2" above; use
  base_body_turnaround (Michael: yes to its profile for the torso) for the join.

## Relaunch 4 (2026-10-01, lean agent 4): the staircase's gate, then milestone 2
- pipeline-3d 00494dec merged (c197e2fd: refs and docs only). g4_stairs1 collected (`remote attach`; 874 CPU s):
  stair_{front,three_quarter}_crossed 0 / 0 P, skirt corners 2.9 / 0.5 P, flaps 4.0 W / 0.0 P; art_band_lower 1.185 ->
  1.111 P; flap_profile_sweep_R W -> P; piece_overskirt_panel_L/R front 0.902/0.923 -> 0.925/0.947, back 0.977/0.958 ->
  0.984/0.965; nothing worse against g4_cuffs2 (tools/kcmp.py). (motion SKIPPED "skirt: not a grid" since the creases
  milestone: the ink strokes ride on the skirt object; pre-existing on pipeline-3d, a follow-up.)
- Calibrated on g4_stairs1 (log charkit/out/garments4/calib_stairs1.log, records 30610f7a): all six CALIBRATED (design
  0-2.6 every move; known-bad g4_stairs0 crossed 2 / 1, skirt corners 8.9 / 6.0, flaps 11.4 / 18.8 FAIL; the voronoi
  floor passes crossed and skirt_front_corner: a defect detector's floor).
- Pregate (30610f7a into 00494dec): PASS, 36 moved, 0 blocking.
- **Stairs gate 1: FAIL under K, one blocker: test_spec_alias** (clawd_body_pieces.json must equal clawd.json; the stair
  knots and the flap square reached clawd.json only): fixed (the alias copied). Otherwise: no new FAIL, no flag
  regression (art_band_lower 1.185 -> 1.111 P, art_mirror_waist 0.715 -> 0.72 P); report
  charkit/out/gate/gate_tool-garments4-stairs_7134ff6d_into_00494dec.md. Gate 2 running.
- **Stairs gate** running: job gate-garments4-1001-074750-2f1e (log charkit/out/garments4/gate_stairs.log), branch
  tool/garments4-stairs 7134ff6d into pipeline-3d 00494dec.

## Milestone 2, step 1: the neck join (branch tool/garments4-neck from pipeline-3d 00494dec)
- **neck_crease's FAILs are its sampling, not a crease** (tools charkit/out/garments4/tools/creasecol.py: the old
  measure's rows printed; creasex.py: the skin's exact cut per column). The old measure took the largest vertex radius
  within 6 degrees and 0.006 L of each height every 0.01 L, interpolating gaps: (1) on the steep flare under the cut the
  torso's subdivided rows are ~0.019 L apart, so two heights catch one row (flat), then a jump (-75 deg): 44.7 on the
  whole skin, at the window's bottom row, every column; (2) a garment mask's edge crossing the 12-degree sector (the V
  opened, column -25: r 0.196 -> 0.183 -> 0.190 over 0.02 L) reads a 55.3 bend; (3) the window's clamped ends. The exact
  cut (each column's half-plane crossed with the triangles) bends 12.6 (masked) / 14.4 (whole) on g4_stairs1, 12.7 /
  14.4 on g4_nv2 (the V opened), 9.5 / 11.6 on g4_nv2j18; ckpt_full (Michael's "major issues with the neck", the old
  ring join) 12.5 / 12.3: its join is a smooth cone in this window too.
- **Remeasure** (958bfcd2): faceregion.crease_of on the exact cut (section_outline), bends read on unbroken runs only
  (CREASE_RUN 4 steps); tests (test_faceregion: steep flare at 0.004 / 0.019 L rows reads 14.8 / 13.3 PASS, a V cut out
  of the front PASS, a 0.02 L ring 58 FAIL, the old flat join worse than the cubic). Step registered (steps/faceregion.py
  'neck_crease*', 958bfcd2). Calibration adapter charkit/calib/neck.py (NeckJoin, computed stand-ins as calib/motion's:
  design = our join one subdivision level finer, window moved 1-2 px and columns 2.5-5 deg; known-bad 'neck_ring' = a
  0.02 L ring at the cut, charkit/calib/known_bad/neck_ring.json; floor 'jitter_skin' sd 0.003 L): **CALIBRATED** on
  g4_stairs1 (design 9.9-10.4, known-bad 49.6 FAIL, floor 35.5-36.8 FAIL, current 12.6 PASS, margin 0.91; no piece
  shape check covers the skin: shape [] as the jaw entries). Record 4c6272a7. CODEMAP regenerated (pipeline-3d's was
  stale). Pregate (4c6272a7 into 00494dec): PASS, 0 moved (the evaluator has no face_region).
- **The join against the base body reference** (tools neckm.py; review/neck_m0.png): only the profile compares (the
  front's and three-quarter's neck sides are under the drawn hair, our skin is cut at the shoulders). Profile front edge:
  the turnaround's visible throat and the base body agree at x 0.16-0.17 (z -0.37..-0.50); ours sits 0.035 L behind
  from the chin to the cut (the head sheet's neck), then 0.03-0.05 L ahead at z -0.62..-0.75 (the torso's top under the
  collar), behind below -0.78; rms 0.062 L (z -0.36..-0.95), 0.045 in the join window. Not changed this step (the head's
  neck is the face workstream's, the torso's top the body fit's): reported for the V and the lapels.
- Next: box gate tool/garments4-neck (after the stairs gate finishes); then step 2 (the reference).
- **Neck gate** running: job via charkit/out/garments4/gate_neck.log (tool/garments4-neck 6598251b into 00494dec).

## Milestone 2, steps 2-3 (branch tool/garments4-v from tool/garments4-neck 6598251b)
- Coordinator 2026-10-01 ~08:10: the laptop's memory is critical: no new local heavy jobs; fits, sweeps, builds, labs,
  calibrations and pregates on the boxes (`remote run|build`, `sweep --box`); local work = reading results, small
  scripts. charkit/out isn't synced to the box: box-run tools go under tools/garments4/ (untracked).
- **Step 2, the reference: registered** (71d7dbe4). layerref's new `bodice` kind (the turnaround redrawn in its layout
  without the bow: kept parts' IoU; the bodice/collar layer against the outfit truth's collar, top and bodice_panel with
  the bow and its tails free; the V's skin against the turnaround's visible skin), tolerances declared before measuring,
  calibrated on the turnaround (itself moved 2 px PASS every view, iou_dc 0.995-0.999; torso band widened 6% FAIL every
  view, outside 0.10-0.14; tool charkit/out/garments4/tools/bodicecal.py). One call, n=2 (prompt `bodice_layers`,
  ledger): take 1 PASS every view (kept 0.987-0.990; layer iou_dc 0.974 / 0.996 / 0.924 / 0.995; V recall 0.99 / 0.998,
  outside 0.098 / 0.047), take 2 FAIL (profile outside 0.045). Registered as charkit/refs/clawd/gen/bodice_layers.png:
  shape authority for what the bow hides (the lapels flat along the V, wide at the shoulders narrowing to the point; the
  V's point at z -0.88 under the knot, -0.72..-0.83; the bodice front), placement the turnaround's; cautions: its V
  0.005-0.015 L wider each side than the turnaround's visible V, cleavage lines not ours. (.env: a gitignored symlink to
  the main checkout's, read only.)
- **Step 3, the V:** cherry-picked the declared families top_line + `ref` 'silhouette' (be1a47f9 = ca32ff7a) and
  class_iou (88e572f9 = fed2ef44). Spec: top.opening carries nv2's V rows (z -0.70..-0.50, half 0.052..0.128 L: the
  drawn V's x0.85; nv1's x1.0 regressed art_outline_collar 1.44 -> 2.17 WARN, a flag) in clawd.json and the alias
  (tools/garments4/setspec.py). charkit/necklineqa.py declares neck_v_front_skin (x -0.2..0.2) and
  neck_v_three_quarter_skin (x -0.1..0.35: the drawn 3q V lies right of the eyes' middle), z -0.45..-0.75, limits
  [0.8, 0.6], Michael's item-4 flag, known-bad g4_cuffs2. Box build g4_v1 running (log
  charkit/out/garments4/build_v1.log). Next: compare with g4_cuffs2 / g4_stairs1 (kcmp), calibrate neck_v_* on the box,
  gate.
- **Stairs gate 2: PASS under K** (tool/garments4-stairs 0425973b into pipeline-3d 00494dec;
  charkit/out/gate/gate_tool-garments4-stairs_0425973b_into_00494dec.md): nothing blocks; CPU 1.04x; 6 new checks
  calibrated; art_band_lower (flag) 1.185 -> 1.111; flap_profile_sweep_R W -> P; guard: piece_overskirt_panel_L/R front
  +3%, back +1%, piece_skirt unchanged. Mergeable at 0425973b (+ notes).
- **Neck gate: PASS under K** (tool/garments4-neck 6598251b into 00494dec;
  charkit/out/gate/gate_tool-garments4-neck_6598251b_into_00494dec.md): remeasured neck_crease 26.9 W -> 12.6 P,
  neck_crease_all 44.7 -> 14.4 INFO, record calibrated; geometry unchanged (no 2x2); CPU 1.07x. Mergeable at 6598251b.
- **g4_v1** (the V opened, box): neck_v_front_skin 0.765 W, neck_v_three_quarter_skin 0.566 F; neck_crease 12.7 P;
  art_outline_neck 1.684 W -> 1.472 P; art_outline_collar 1.442 P (unchanged); piece_top front 0.583 -> 0.749, 3q 0.688
  -> 0.800 (profile, back unchanged); piece_collar, piece_bow, piece_bodice_panel unchanged. Nothing worse under K.
  neck_v_* CALIBRATED (box; design 0.90-0.97 every move, known-bad g4_v0 0.476 / 0.358 FAIL, voronoi floor 1.0: it
  relabels pieces, not classes). Records via tools/garments4/box_records (the box's synced files are read-only:
  `calibrate store` on the box linked the build but couldn't rewrite the JSON; --json needs an existing synced dir).
- **The V's gate order:** gated into pipeline-3d before the neck remeasure lands, the 2x2 scores neck_crease's old
  measure on the V geometry (26.9 W -> 55.3 F) and blocks; gate the V into tool/garments4-neck (its parent), carry
  after the coordinator merges neck.
- Lapels (step 4) branch tool/garments4-lapels (from tool/garments4-v): declared family band_rows (a1f16db1, 3b4886c3:
  a two-sided band row by row, width / inner (the V) / outer edge vs the drawn silhouette, occluders' rows left out per
  side incl. hair); drafts tools/garments4/drafts/lapels.json (collar_{front,three_quarter}_lapel_width / _v), being
  calibrated on the box with neck_v_*.
- Review page JSONs (built on the box: `remote run --fetch DIR review page JSON --out DIR`): tools/garments4/review/
  stairs.json, neck.json, v1.json (figures copied under tools/garments4/review/).
- **Stairs gate 3: PASS under K** (b4670264, the merge of pipeline-3d ff41ca2, into ff41ca20;
  charkit/out/gate/gate_tool-garments4-stairs_b4670264_into_ff41ca20.md): CPU 1.00x. Mergeable at b4670264. (The carry
  was refused: the build reads faceregion.py, which the neck merge changed.)
- Review pages (built on the box): stairs charkit/out/garments4/review/stairs/index.html, neck
  charkit/out/garments4/review/neck_page/index.html (sources tools/garments4/review/*.json).
- V gate running (tool/garments4-v a6e0e465+records into ff41ca2; log charkit/out/garments4/gate_v.log).
- **Lapels, step 4 (tool/garments4-lapels):** the front band measure didn't calibrate (a 1-2 px vertical move reads
  0.035-0.06 L; the hair occluder takes every design row in front): declared three-quarter only (charkit/lapelqa.py,
  limits [0.015, 0.03] from the draft's design worst 0.0083 / 0.0104 and known-bad 0.061 / 0.063); the front graded by
  piece_collar front, neck_v_front_skin, art_outline_collar. Sweep l1 (flat_front alone, conform off in front): worse
  (collar front IoU 0.657 -> 0.506 at 60 deg, 0.19 at 120; art_outline_neck 1.47 -> 3.94): the conform was the
  shape. New template: collar 'lapel' {a, point, soft} (a Coons patch per lapel in the front view: V edge straight
  from the collar's V top to the point, the neckline row, the column at a, the outer edge; laid on the body from the
  front; garments.front_hits) with flat_front over the same azimuths; the jacket's opening must reach under the lapels
  (x1.0-1.1 of the drawn V; nv2's x0.85 leaves orange inside a drawn-width V). Sweep l2 running (tools/garments4/l2.json:
  a 60/75, opening x0.85/1.0/1.1, v_half 40/48).
- **Stairs gate 2: PASS under K** (0425973b into 00494dec; charkit/out/gate/gate_tool-garments4-stairs_0425973b_into_00494dec.md):
  nothing blocks, CPU 1.04x, 6 new checks calibrated, art_band_lower 1.185 -> 1.111, guard flat or up. pipeline-3d
  ff41ca2 (the neck merged) merged in afterwards (notes and CODEMAP conflicts resolved, CODEMAP regenerated).
- **V gate 2: PASS under K** (tool/garments4-v a3bb4a8b, pipeline-3d 0d53cb8 merged in (declared families unioned),
  into 0d53cb84; charkit/out/gate/gate_tool-garments4-v_a3bb4a8b_into_0d53cb84.md): CPU 1.01x; the one new FAIL is the
  branch's own neck_v_three_quarter_skin 0.566 (reported). Mergeable at a3bb4a8b. Review page
  charkit/out/garments4/review/v_page/index.html.
- Lapels: sweeps l2 (the Coons patch) and l3 (the walk cut at the drawn outer edge) both worse than the hull collar
  (collar front IoU 0.657 -> 0.41-0.54, 3q 0.468 -> 0.24-0.37, lap3q width 0.061 -> 0.095-0.128): the walk crumples over
  the neck's flare. l4 running: mode 'project' (straight front-view columns laid on the torso). tool/garments4-v merged
  into lapels (a3bb4a8b; declared families unioned: top_line, class_iou, stair, band_rows).

## The motion QA fix (branch tool/garments4-motionfix from pipeline-3d ad081524; coordinator's priority)
- Cause (confirmed from the builds' qa.json): motion read SKIPPED "skirt: not a grid" since the creases milestone
  (g4_creases 5108 vertices, g4_cuffs2 5110, g4_stairs1 5398 at stride 144), not the staircase: garments.with_ink
  appends the crease strokes to the skirt object (their faces on 'skirt_ink', their 70 vertices after the grid's); the
  stairs' fourth step added 2 grid rows. The gates reported motion SKIPPED, not blocking.
- Fix at the cloth's grid reader (charkit/sim): drape.ink_slots / grid_polys (the cloth's own faces), grid_of reads the
  grid from them; cage.of_piece builds on the grid and carries the strokes (Cage.attach: the nearest template vertex's
  block and weights, their own residual); piece_cloth pins them inert; motion's stretch edges and penetration surface
  leave the strokes out (with them in, the stroke edges set the stretch p99: kick 0.36, squat 0.93). Test test_sim
  (a grid with strokes: grid_of, carried exactly at rest and with a rigid move).
- Readings: the calibration build hands_b4 (pre-creases): kick inside 0.0024, kick stretch 0.063, squat stretch 0.104
  (all PASS). Being re-measured on the box: g4_stairs1 (ink + stairs) and g4_part1 (no ink) with the fix.
- **Motion readings with the fix (box QA):** g4_part1 (no ink) kick inside 0.00244 P, kick stretch 0.06346 P, squat
  stretch 0.10404 P: the calibration build's exactly (the fix is neutral without ink); g4_cuffs2 (creases + cuffs, no
  stairs) 0.00235 P / 0.0790 P / 0.1272 P; g4_stairs1 (pipeline-3d's skirt: + the staircase) 0.0071 **WARN** / 0.0796 P /
  0.1338 P (squat inside 0.0171 INFO). **The staircase raised the kick's penetration 0.0024 -> 0.0071** (WARN; hidden while
  motion read SKIPPED during the stairs gates): a follow-up (the fourth step's rows at the hem).
- **Motion gate: PASS under K** (tool/garments4-motionfix 4da79555 into pipeline-3d ad081524;
  charkit/out/gate/gate_tool-garments4-motionfix_4da79555_into_ad081524.md): CPU 1.04x; the four motion checks back
  (records calibrated); motion's measurement steps registered after the gate (charkit/steps/motionqa.py), carried.

## Lapels (step 4), stop point: not gated; what the sweeps showed and the exact next steps
- Branch tool/garments4-lapels (pipeline-3d merged in after the V). Carries: declared band_rows (+ hair occluder),
  charkit/lapelqa.py (collar_three_quarter_lapel_width / _v, limits [0.015, 0.03]; front not calibrated: a 1-2 px vertical
  move reads 0.035-0.06 L; the drafts' records not written: calibrate the module on the chosen build), calibrate's
  draft-check fix, garments: collar_hull flat_front {a, fade} (conform off in front), collar front_length table, collar
  'lapel' {mode 'project' (straight front-view columns laid on the torso, garments.front_hits) or the walk cut at the
  drawn outer edge; a, point, shoulder, spread, off, top, blend}. All off by default; bodysens NOT_KNOBS lists them.
- Sweeps on g4_v1 (box; tools/garments4/l1..l7.json, outs charkit/out/garments4/sweeps/l1..l7, table
  charkit/out/garments4/tools/ltab.py): control collar F/3q 0.657/0.468, V 0.765/0.566, lap3q width 0.061, ao_collar 1.45,
  ao_neck 2.09 (numpy drawing). l1 conform off alone: worse (collar F 0.19-0.51). l2 Coons patch / l3 walk cut at the
  outer edge: worse (0.41-0.54 / 0.24-0.37), the walk crumples over the neck's flare. l4/l5 projected: l5 Q2 (a 85, v_half
  55, opening x1.1, spread 0.7, off 0.06) collar 0.765/0.428, V 0.80 P / 0.627, ao_collar 0.69, but ao_neck 5.7 and
  fragments 9.2, lap3q width 0.079; l7 showed Q2's front gain came from rows that missed the torso collapsing onto the
  neckline point (degenerate faces at the neck); with them filled by the walk (S0) 0.452/0.309. Neckline drops 0.02-0.06
  (l7) give V 0.78-0.80 / 0.68-0.70 but collar 0.48-0.59 / 0.35-0.43.
- **Why it doesn't converge:** the drawn lapels' top runs along a level shoulder line where our body dips 0.07-0.09 L
  (milestone 3's measurement: shoulder_*_dip); in front view there's no body under the lapel's top (x 0.15-0.40 at
  z -0.47..-0.52), so a lapel laid on the body has nothing to lie on there: the hull conform supplied it (as lumps).
  The flat lapels need the shoulders first (body.shoulder template or the jacket's shoulder pad, tool/garments4-shoulders;
  parked on Michael's two calls).
- **Next steps:** (1) with Michael's shoulders answer: body.shoulder {z -0.525, x 0.47, join} (or the pad) on this branch;
  (2) then the projected lapels laid on the jacket's surface (not the body's), all rows (no collapsed rows), lap_T
  including the shoulder tops; sweep a/v_half/opening/off against collar F/3q (guard), neck_v_*, lap3q width/v, ao_collar,
  ao_neck, af_collar; (3) calibrate lapelqa on the chosen build (`calibrate 'collar_three_quarter_lapel_*' --build`,
  known-bad g4_v0), box build, merge pipeline-3d, gate; (4) re-judge art_outline_collar on it (today 1.442 PASS on the
  default with the V: its FAILs were tool/collar4's stand-up template collars E2/A3/H1, 3.4-5.6).
- Review pages: stairs charkit/out/garments4/review/stairs/index.html, neck .../review/neck_page/index.html, the V
  .../review/v_page/index.html, lapels (informational) .../review/lapels_page/index.html (sources tools/garments4/review).
- Heads (2026-10-01 end of this run): stairs b4670264 (merged, pipeline-3d 0d53cb8), neck 6598251b (merged, ff41ca2),
  the V a3bb4a8b (gate PASS into 0d53cb84; merged, 9f6379e8), motion fix 880202e9 (carried PASS into ad081524; not yet
  merged), lapels this commit (not gated).

## Round 5 (2026-10-01, lean agent 5): shoulders first, then the flat lapels
- Coordinator: (1) shoulders on tool/garments4-shoulders (pipeline-3d e9cb156 merged in: 1b83a84d, CODEMAP f2a1dffe):
  re-measure with the V open, fix the shoulder line to the drawing's level line (template or pad, on the numbers) with
  the back collar's cream panel; guard skin/top/sleeves/collar IoUs per view; gate. (2) then the flat lapels on the
  fixed shoulders (tool/garments4-lapels + pipeline-3d): inner edges on the V to the knot, the stripe, a low band at the
  back of the neck, the span stopping at the front-facing columns; gate; re-judge art_outline_collar.
- Box builds running: g5_base (the merged head's default spec, charkit/out/garments5/specs/base.json; log
  charkit/out/garments5/build_base.log), g5_sh0 (+ body.shoulder {z -0.525, x 0.47, join}: specs/sh0.json; log
  build_sh0.log). Outputs charkit/out/g5_base, charkit/out/g5_sh0.
- **Scope expansion (coordinator, Michael's diagnosis, 2026-10-01):** the body has no real shoulder (separate meshes:
  the torso tube and capped arm tubes; the torso's top fitted from the hull, i.e. the costume; body.shoulder off). Order:
  (1) the body's shoulder, structurally: measured against base_body_turnaround, a continuous shoulder joining the arms
  to the torso (welded, or a joined region with edge loops), skinnable (clavicle and upper-arm weights; garments'
  transferred weights valid), the shoulder template on; guard skin/arm/sleeve/top IoUs, hands, cuffs, motion, art_bumps_*;
  a posed check (arm raised 90 deg front and side) in the notes; gate. (2) the garment shoulders and back collar on the
  new body; gate. (3) the flat lapels; gate; re-judge art_outline_collar.
- Baseline g5_base (the merged head's default; qa charkit/out/g5_base/qa/qa.json): shoulder_front_top 0.033 F, _dip
  0.052 F, _tilt 0.203 F, back top 0.019 W, dip 0.042 F, collar_back_rows 0.147 F, collar_back_iou 0.73 F;
  art_outline_collar 1.442 P (3q 3.29), art_outline_neck 1.472 P, neck_crease 12.7 P, neck_v_front 0.765 W, 3q 0.566 F;
  motion kick inside 0.0071 W. g5_sh0 (+ body.shoulder level template): dips 0.005 P, front top 0.028 W, tilt 0.104 W;
  but art_outline_collar 1.44 P -> 2.83 W, art_outline_neck 1.47 -> 2.84 W (flags), neck_crease 12.7 -> 28.2 W.
- **The body's shoulder measured** (tool tools/garments5/shm.py, box: `remote run --fetch charkit/out/garments5/shm
  script tools/garments5/shm.py BUILD..`; our skin alone z-buffered, triangles labelled torso/arm/head by the nearest
  body_code part; against base_body_turnaround's figures less hair (opened 3x3) on the design grid; picture
  charkit/out/garments5/shm/v1b.png, numbers v1b.json). The reference (front; back within 0.01): shoulder top line z at
  |x| 0.3 / 0.4 / 0.5 / 0.6 = -0.50 / -0.525 / -0.535 / -0.615 (an upper bound under the hair's edge at |x| < 0.5: the
  first body pixel under the hair); shoulder point (0.585, -0.595); outer edge |x| at z -0.6 / -0.7 / -0.8 / -0.9 / -1.0 /
  -1.2 = 0.585 / 0.64 / 0.673 / 0.696 / 0.73 / 0.80; armpit z -1.005; profile: the deltoid's back edge x 0.50 / 0.53 /
  0.53 / 0.51 / 0.49 at z -0.62 / -0.75 / -0.85 / -0.9 / -1.0. Ours (g4_v1 = default body): the top line at |x| 0.3 /
  0.4 / 0.5 / 0.6 = -0.637 / -0.696 / -0.93 / -0.89 (0.14-0.40 L low); the outer edge 0.41 / 0.40 at z -0.7 / -0.8 (the
  torso's vertical side wall: no deltoid), then the arm tube's flat cap at z -0.86 (its corner the "shoulder point"
  (0.74, -0.856)); armpit -0.85; no arm in profile above z -0.85. The arm below z -1.0 is within 0.03 L (outer edge
  0.759 / 0.792 at -1.0 / -1.2 against 0.73 / 0.80). The skeleton's shoulder joint (the 2D rig's, outfit.rig_frame) sits
  at (0.544, -0.886): ~0.16 L under where the deltoid's centre would be.
- **The joined shoulder (52949256, off by default: body.shoulder.socket):** code_body.socket_rim / shoulder_bridge: a
  hole in the torso's side (rows from where the side reaches `top` L out down to the armpit `bottom`; columns within
  `half` deg of the side), a bridge of `loops` edge loops from its rim to the arm's ring at `s0` L down the chain (per
  rim vertex a cubic leaving the torso toward the hole's middle lifted `lift` deg, arriving along the arm; `reach`
  tangent shares), the arm's columns matched to the rim's (angle round the bridge's axis) and evened over `blend` rings.
  build_body_data stitches the torso with holes, the bridges and the arms into one closed surface (only the neck ring
  open; tests charkit/tests/test_shoulder_join.py), the torso's partial rows listed for the neck join
  (code_base._torso_rings), weights: the clavicle round the rim (`clav`), the bridge eased from the rim's to the arm's
  (`arm_w`), optionally the upper arm over the torso round the rim (`torso_arm`); the template's widening at the sides
  only (`az`). Harness tools/garments5/bodyj.py (box: `remote run --fetch OUT script tools/garments5/bodyj.py
  charkit/out/g5_base VARIANTS.json --out OUT`): the body data built from the spec without Blender, topology, the base
  body measures (shm.measure_labels), the posed check.
- Grid j2 (charkit/out/garments5/bodyj2): best `t36_l65_a45_b50` = shoulder {z -0.525, x 0.38, round 0.03, hold 0,
  fall 0.10, az 50, join [[0,.12],[45,.12],[75,.03],[180,.03]], socket {top 0.36, lift [65, 75], reach [0.45, 0.5]}}:
  score 0.051 (j1 defaults) -> 0.030 (own body 0.17-0.2 rms); front: top rms 0.042, outer 0.019, point (0.585, -0.588)
  vs ref (0.585, -0.595), armpit -1.047 vs -1.01; profile arm front/back rms 0.029/0.026. Residual top line at |x|
  0.2-0.35: ours -0.547 (the neck join re-seats the template's top rows within 0.03 L of the cut at the sides) against
  the sheet's -0.50..-0.53 (under its hair's edge: an upper bound); the trapezius flare above the cut is the head's neck.
- Posed check (90 deg, LBS on the body's own weights): the old body's arm tubes don't deform but go through the torso
  in the forward raise (27 vertices, 0.04 L deep); the joined shoulder deforms with the 2D rig's low joint (0.544,
  -0.886): stretch up to 4.7x (the armpit's short bridge), faces down to 3% area in the forward raise. Being tested:
  the pivot up the arm's line (0.1-0.26 L) and the weights (arm_w, torso_arm), metrics strain p95 (edges >= 0.015 L),
  folded/collapsed area shares, penetration, volume (run j3, charkit/out/garments5/bodyj3).
- Declared checks for the body against the base body sheet (uncommitted until calibrated): declared `ref`
  'base_body' (base_body(): the manifest's sheet at the refcheck scale, registered on the turnaround's head; our_body():
  the skin alone) with `below` / `window`, family `side_line` (dx / rms / axilla); the Declared adapter's stand-in for
  our_body (the sheet's body moved; a floor: the costume's silhouette). Draft tools/garments5/drafts/bodyshoulder.json
  (body_shoulder_{front,back}_top / _side, body_axilla_{front,back}, body_shoulder_{view}_iou).
- **Weights and the pivot (runs j3, j4: charkit/out/garments5/bodyj3, bodyj4):** the 2D rig's joint (0.544, -0.886) as
  the pivot folds the deltoid in the side raise (folded 1.8%, the arm leaving the torso under the deltoid); with the
  rig's joint 0.18 L up the arm's line (socket.pivot; the garments keep the chain's root: garments.arm_seg) and the arm's
  weight over the bridge's outer half (arm_w [0.5, 1]): side raise strain p95 1.77, folded 0.1%, collapsed 0.55%,
  nothing inside the torso, volume +0.6%; forward raise 1.91 / 2.7% / 0.24% / none / -0.7% (the old body: no deformation
  but the arm tube 0.04 L into the torso, 27 vertices). The upper arm over the torso round the rim (torso_arm) and an
  earlier arm weight made it worse (penetration 0.06-0.15 L). Pivots 0.12 / 0.18 / 0.24 all fine for the side raise;
  0.18 chosen (the deltoid's centre, ~0.1 L under the shoulder point).
- **Candidate in the default spec** (b184f019): body.shoulder {z -0.525, x 0.38, round
  0.03, hold 0, fall 0.10, az 50, join [[0,.12],[45,.12],[75,.03],[180,.03]], socket {top 0.36, lift [65, 75], reach
  [0.45, 0.5], arm_w [0.5, 1.0], pivot 0.18}}. Box build g5_c1 (log charkit/out/garments5/build_c1.log).
- Known-bad g5_base stored on the box (`remote run calibrate store g5_base charkit/out/g5_base ...`: the link made, the
  JSON written locally: charkit/calib/known_bad/g5_base.json, the box's synced files being read-only).
- Next: QA g5_c1 against g5_base (kcmp: guard IoUs skin/arm/sleeves/top, hands, cuffs, motion, art_bumps_*, the
  collar's flags); calibrate the body-shoulder drafts on the box (`remote run --fetch tools/garments5/box_records
  calibrate 'body_shoulder_*,body_axilla_*' --declared tools/garments5/drafts/bodyshoulder.json --build
  charkit/out/g5_c1 --json tools/garments5/box_records/cal_body.json`), move them into charkit/bodyshoulderqa.py with
  the records; pregate on the box; gate.
- Coordinator 10:4x: the build box full (16 slots, sweeps): overflow to render2 (`remote --box render2 ...`). g5_c1
  relaunched on render2 (log charkit/out/garments5/build_c1.log); the baseline built again there as g5_base_r2 (log
  build_base_r2.log) so the known-bad can be stored and the drafts calibrated on one box.
- **The candidate's full build g5_c1 (render2; QA charkit/out/g5_c1/qa/qa.json) against g5_base_r2 (the same box's
  baseline), under K: blocked.** The body's shoulder is right (above) but the garments, fitted round the old body,
  don't hold on it:
  - piece_top front 0.749 -> 0.311 (-58%), 3q 0.80 -> 0.58, back 0.93 -> 0.74; piece_sleeve_L/R front -22% / -29%.
    tools/garments5/topiou.py: our jacket's extra area 0.038 -> 0.136 L^2, at |x| 0.4-0.6, z -0.6..-0.9: the bridge's
    front columns (the socket's front edge at 60 deg on the torso, y ~ -0.19) stand in front of the puffs' inner front
    (the puffs match the drawn profile, IoU 0.94). tools/garments5/confuse.py: drawn sleeve -> our jacket +0.034 (front),
    +0.025 (3q), +0.017 (back); drawn collar -> our jacket +0.022 (back: the jacket over the raised shoulder comes up
    through the hull collar's back flap).
  - sleeve_*_spikes / _profile FAIL (front spikes 0 -> 0.21): the same jacket past the puffs.
  - neck_crease 12.7 P -> 81 F (whole skin 14.4 -> 88): the neck (the head's, slender to the cut) turns into a shoulder
    top at the cut's height within 0.006-0.03 L at the sides (the template's rows; the join's reach 0.03 there).
  - art_outline_collar 1.44 P -> 4.67 W, art_outline_neck 1.47 P -> 4.93 W (flags), collar_*_torn 0 -> 0.013-0.071 F,
    collar_back_rows / square / iou worse: the hull collar is walked on the body (garments.collar: from the neckline
    outward a fixed surface length) and now walks out along the level shoulder and over the bridge.
  - bow_front_bleed 0 -> 0.155 F (flag), hair_penetration 0 -> 0.0065 W, hand_three_quarter_reach_L P -> W (-0.0403).
  - Better: shoulder_front_dip 0.052 F -> 0 P, shoulder_front_tilt 0.203 F -> 0.109 W, art_terminator_hair W -> P.
  - Skin above the jacket at the shoulder tops (tools/garments5/skinpeek.py: the body's top at |x| 0.25-0.45 at
    -0.505..-0.51 from the eye line; the jacket's top -0.553..-0.579: its neck cut, 0.04 L over the neck bone's head).
- **Garment sweeps on g5_c1 (render2; charkit/out/garments5/sweeps/g1, g2):** g1, the jacket's neck cut 0.04 -> 0.05 /
  0.06 / 0.08: collar_front_torn and 3q torn clear at 0.06, nothing else; 0.08 trips the guard (piece_top front -17%).
  g2, the puffs' clearance (garments.puff_clear, e5cd247e: spec clear_body {gap, bones, inner}) with the cut at 0.06:
  sleeve front spikes 0.21 -> 0.08, piece_top 0.613 -> 0.632-0.647 (front 0.31 -> 0.35-0.38), but piece_sleeve_R 3q
  0.458 -> 0.36-0.40 (the far puff grows) and art_outline_neck worse: the clearance alone isn't the fix (the deltoid's
  front-inner part is in the excluded inner sector).
- **The neck join against the shoulder's height (run j5, tools/garments5/bodyj.py now assembles with character.assemble,
  the neck's join included, and reads the whole skin's neck_crease):** T0 (the candidate) crease 88; T1 (the join's reach
  at the sides 0.08 L, the rim's top under it at z -0.61 (socket.top_z)) crease 21 but the shoulder's silhouette score
  0.029 -> 0.103 (the join's loft pulls the shoulder's top rows in: the point (0.61, -0.71) against the sheet's (0.585,
  -0.595)). The sheet's shoulder line at |x| 0.3-0.4 sits at our cut's height (-0.50..-0.53): its trapezius flare is
  above the cut, in the head's neck (the face workstream's). T2-T4 (reach 0.10/0.12) pending in
  charkit/out/garments5/bodyj5.
- j5 complete: T0 (candidate) score 0.029 crease(whole, cage) 88; T1 (join reach 0.08 at the sides, rim top -0.61) 0.103
  / 21; T2 (0.10, -0.63) 0.109 / 24; T3 (0.12, -0.65) 0.127 / 21; T4 (x 0.42, round 0.08, 0.10, -0.63) 0.110 / 24. The
  old body (j6): score 0.184, crease (whole, cage) 24.5. So the crease comes back to the old body's with a deeper join,
  but the variants tried lose the shoulder's top (the join's loft pulls the template's top rows in); a better try: the
  template wider (x ~0.55-0.6) under the join's reach so the torso's rows make the shoulder cap, the rim below them.
  Decision asked of Michael (review page): A flare the head's neck above the cut (face workstream), B a lower shoulder
  top, C re-measure neck_crease.

### Round 5 stop point (2026-10-01): the body's shoulder done, off by default; the garments next
- **Branch tool/garments4-shoulders** (pipeline-3d e9cb156 merged in). Carries, off by default: the joined shoulder
  (code_body socket/bridge, weights, the rig's pivot; garments.arm_seg keeps the arm-placed garments on the chain's
  root), garments.puff_clear, declared `ref` 'base_body' + side_line, `charkit script` (hairshell3's d9b5e521),
  known-bad g5_base, plus the earlier shoulder work (collar4's builder code, shoulderqa.py's 6 calibrated garment
  shoulder checks: they FAIL on the default body, so this branch still can't gate as is). The spec switch was tried
  (b184f019) and reverted (6739aa7f); the candidate's knobs: tools/garments5/v/candidate_shoulder.json.
- **Review page:** charkit/out/garments5/review/body_shoulder/index.html (source tools/garments5/review/body_shoulder.json,
  built on render2: `remote --box render2 run --fetch tools/garments5/review/page review page
  tools/garments5/review/body_shoulder.json --out tools/garments5/review/page`). Asks Michael: keep the moved joint;
  the neck join A (flare the head's neck above the cut: face workstream) / B (a lower shoulder top) / C (re-measure
  neck_crease); refit the garments to the body rather than slim the body.
- **Builds (render2 and local):** g5_base_r2 (the old default), g5_c1 (the switch on). Build box: g5_base, g5_sh0.
- **Exact next steps (the garment round, with the switch on: tools/garments5/v/candidate_shoulder.json into the spec):**
  1. The shoulder's top: fix the bridge's top loops overlapping the torso's top rows near the neck (lift top 65 -> 30-45,
     or the rim's top further out), then the neck join per Michael's A/B/C (B: the template wider, x 0.55-0.6, under
     a 0.08-0.10 L join so the torso's rows make the shoulder cap, the rim below them; bodyj.py with the join modelled).
  2. The socket's front edge back (half 30 -> 20-24, or shift toward the back) so the deltoid's front stays under the
     puffs, and puff_clear for the rest (inner 20-30 deg, gap 0.035); guard piece_top F, piece_sleeve_R 3q.
  3. The jacket's neck cut 0.06 (covers the shoulder tops; clears collar front/3q torn).
  4. The collar on the new body: the walk's lengths (side_depth, back_depth) refit so the back panel and the lapels'
     outer ends land as before (collar_back_rows/square/iou, torn, art_outline_collar), or the hull collar's conform
     reach; the jacket bedded under the back flap (bed() generalised: the collar, from the back).
  5. bow_front_bleed (flag): find what moved under the bow (the template's sides widen from 40 deg: az 50 -> 35).
  6. Calibrate the body-shoulder drafts on render2 (`calibrate 'body_shoulder_*,body_axilla_*' --declared
     tools/garments5/drafts/bodyshoulder.json --build charkit/out/<candidate>`; the known-bad g5_base must be stored on
     that box: `calibrate store g5_base charkit/out/g5_base_r2 ...`), move them into charkit/bodyshoulderqa.py with the
     records; motion_* step if the rig moves the motion values; pregate on the box; gate.
  7. Then the flat lapels (tool/garments4-lapels) on it, and re-judge art_outline_collar.
- tool/optimize (`charkit sweep --optimize`) was in testing on the boxes, not landed: use it for steps 1-4 once it is.

## Round 6 (2026-10-01, lean agent 6): the garments refit to the joined shoulder
- Coordinator: Michael confirmed the three answers as recommended: (1) keep the joint 0.18 L up at the deltoid's
  centre; (2) A: flare the head's neck above the cut (ours end to end, minimal and local in the head's neck code; face7
  doesn't touch the neck; do it last); (3) refit the garments to the new body (puffs contain the deltoid, the collar
  walked on the new shoulder, the jacket bedded under the collar's back flap). Acceptance: gate PASS under K with the
  joined shoulder ON by default (clawd.json + clawd_body_pieces.json); no garment piece's shape IoU below the old body's
  by more than the guard in any view; the 90 deg raises clean with the garments on; review page (design | old body |
  refit per view, plus the raised poses) with the summary box. Then the flat lapels; re-judge art_outline_collar.
- pipeline-3d 07f305e8 (the clips) merged in: 1425a80c (declared.py: both families side_line + visible kept).
- Fresh candidate base: charkit/out/garments6/specs/c0.json (clawd.json + tools/garments5/v/candidate_shoulder.json),
  box build g6_c0 on render2 (log charkit/out/garments6/build_c0.log).
- g6_c0 built (render2; = g5_c1 + the clips). Diagnosis on it / g5_c1 (tools/garments6, outputs charkit/out/garments6/lab):
  - shoulderlab.py (design | ours | diff per view): front, the jacket stands in front of the puffs' inner part at
    x 0.3-0.5, z -0.55..-0.95, and over the shoulder top; back, the jacket's shoulders over the collar's flap region.
  - xsec.py (sections x = 0.3/0.45/0.55, z = -0.55/-0.65/-0.75): the jacket (region leftShoulder + leftUpperArm t <
    0.12) now wraps the whole deltoid (the bridge's vertices are dominated by the clavicle and the upper arm): at z
    -0.65/-0.75 it is a full loop round the arm, the same size as the puff, coming out at its inner front and back.
  - depthgap.py: front view, the jacket nearer than the puff inside the drawn puff 0.0345 L^2, by p50 0.045 / max 0.117 L
    (z -0.5..-0.8, x 0.39-0.59); back 0.017 L^2; profile 0.0035.
  - contain.py (the skin of the bridge + arm in the puff's frame): 28% outside the puff, the bridge's front and back
    columns by the torso (angles +-60..150, t -0.45..0): the puff's inner front/back, and the shoulder top above the
    dome.
  - neckring.py: the neck ring at z -0.544 (r 0.117 sides .. 0.2 back), the jacket's plane cut at -0.563; the bridge's
    top loops rise to -0.505 beside the neck (the skin wings over the collar in the c1 renders: the round-5 defect).
  - The design (sleeve_closeup): the puff sits over the shoulder, its seam at the armhole, the bodice up to it.
- Plan: (1) the body first (the garments fit the final body): the neck flare (A: code_base.flare_neck, body.neck_flare
  {h, share by azimuth, to, p}) with the bridge's top lift lowered; measured by tools/garments6/bodyj6.py (score vs the
  sheet, whole-skin neck crease, bridge over the ring, posed, a zoomed picture). (2) the garments: the jacket tucked under
  the puffs (top.tuck {under, margin}: the bridge/arm vertices inside a puff left out), the puffs grown round the
  deltoid by part (sleeve_L.clear_body {gap, parts [shoulder, arm], inner 0}), the jacket's neck cut a neckline
  (cuts' 5th element r round the neck's axis); then the collar walk, the back flap bed, bow_front_bleed.
- Running: sweep d1 (render2, base g6_c0, tools/garments6/v/d1.json -> charkit/out/garments6/sweeps/d1, log
  sweep_d1.log): tuck / clear by parts / neck r; local bodyj6 test (T0, F1) -> charkit/out/garments6/bodyj6_test.
- Sweeps d1/d2 (render2, base g6_c0; tools/garments6/sweepk.py reads a sweep's rows under K against the old body
  g5_base_r2): the jacket tucked under the puffs (top.tuck margin 0) + the puffs grown round the bridge and arm by part
  (sleeve_L.clear_body {gap 0.025, parts [shoulder, arm], inner 0}): piece_top f/3q/p/b 0.311/0.577/0.577/0.743 ->
  0.626/0.719/0.623/0.860 (old body 0.749/0.800/0.634/0.931), sleeve_L 0.889/0.964/0.867/0.867, sleeve_R front 0.891,
  bow_front_bleed 0.153 F -> 0.06 W, art_bumps/points_top 20/27 -> 0. The smooth envelope (clear_body.spread 0.04-0.06)
  balloons the puff (profile 0.94 -> 0.65-0.69, a block up to the neck): not used; the 3x3 max filter leaves lumps on
  the inner front (sleeve_front_spikes 0.08 F).
- The sweep can't see the skin's mask (the garments stage splices garments only; neck_crease reads the base's masked
  skin): neck_crease, the skin's wings, art_outline_neck need full builds.
- Body variants k2 (tools/garments6/bodyj6.py, render2 -> charkit/out/garments6/bodyj6_k2): score vs the sheet / whole-skin
  crease / the bridge over the neck ring: T0 0.0293 / 88 / 25 verts 0.038 L; F1 (the flare: h 0.08, share 1 at 75-180
  deg, to 0.04, p 2) 0.0281 / 90 / same; L45 (socket lift top 45) 0.0324 / 88 / 5, 0.021; F1L45 0.0315 / 83 / 5, 0.021;
  L30 0.040. The whole-skin crease stays 83-90 (the level shoulder's own turn; the QA reads the masked skin). Posed on
  every variant: strain p95 1.75-1.95, folded <= 3.3%, nothing inside the torso.
- tools/garments6/bodysec.py (sections by part): the bridge forms the whole shoulder top from x 0.15 out (the hole's
  top starts by the neck); its front and back columns leave the torso nearly perpendicular (a wall at the hole's front
  edge, x 0.2-0.25, y -0.05); the rim's top corners rise to -0.505 (the skin wings over the collar in the renders).
- posed.py (the raises with the garments on, left arm): with the puff rigid on the upper arm the skin it holds comes out
  under it (side raise 53 vertices, 0.12 L; forward 19, 0.11); with the cap weighted from the body (sleeve weights {from
  body, rigid_from 0.05, blend 0.15}) 8 / 0.046 and 13 / 0.041, the puff's strain p95 2.0 / 2.4, folded 1.2% / 3.9%.
- poke.py (what comes through what, at rest): with the radial neck cut the jacket covers the shoulder tops and came
  through the collar (front 209, back 20 vertices); the collar beds: the back/front projections (bed side back/front)
  front 102 / back 23; along the collar's normal (bed side normal, 6 passes) front 10 / back 5 (max 0.04 L).
- Builds running (render2): g6_f1 (body F1 + garments tools/garments6/v/ga.json: tuck, radial neck cut, beds bow + collar
  back/front projections, clear_body {gap 0.02, from_t -0.3}, the cap's body weights), g6_f1l45 (body F1L45, same);
  specs charkit/out/garments6/specs/b_F1.json, b_F1L45.json; logs build_f1.log, build_f1l45.log. Next garment set gb.json
  (the collar bed along its normal).
- Builds g6_f1 / g6_f1l45 (render2; garments ga.json) against the old body (kcmp): piece_top f/3q 0.565/0.691 and
  0.649/0.744 (old 0.749/0.800), sleeve_L front 0.79 / 0.81, sleeve_R front 0.76 / 0.81; bow_front_bleed 0.0125 /
  0.015 PASS; shoulder_front/back_dip 0 PASS, front tilt 0.10 W / 0.078 P, front top 0.028 W (were FAIL); but
  neck_crease 96 / 104 FAIL (worst columns +-55..75 deg), collar torn x4 FAIL, piece_collar front/3q -28/-41% and
  -21/-31% (guard), art_outline_collar 8.8 / 9.6 W, art_outline_neck 9.0 / 6.3 W, art_speckle_neck (flag) 3.9 / 9.2 W,
  sleeve spikes/profile FAIL. tools/garments6/look.py (renders, collar region): skin patches at the puffs' inner front and
  back and at the shoulder tops; skinwhere.py: the skin showing is mostly the bridge's skin on the jacket's border
  (front 0.055 L^2, back 0.066): with tuck margin 0 the jacket's last faces are dropped where one vertex is inside the
  puff, and the border skin there lies outside it. Next: margin 0.02-0.03; the collar bed along its normal (gb).
- Builds running (render2): g6_b1 (F1L45 + gb, tuck margin 0.02), g6_b2 (margin 0.03), g6_b3 (F1 + gb margin 0.02);
  specs charkit/out/garments6/specs/b1-3.json, logs build_b1..3.log.
- puff_clear `dilate`/`blur` (a smooth plateau over the needs, never under them) added for the lumps.
- Builds b1/b2 (tuck margin 0.02/0.03): the jacket kept near the seam stands in front of the puffs (piece_top front
  0.43/0.40). The tuck now sinks (tuck {sink -0.004, drop 0.06, ease 0.02}: the jacket's offset eased under the skin
  where the body lies inside a puff; only faces deeper than drop cut): bridge skin showing at the seam 0.055 -> 0.001 L^2.
  b4 (sink): no skin patches in the renders (look_b45.png), piece_top front 0.41 (the puff's dome doesn't hold the
  bridge's top: top in front of it 0.028 L^2, up to 0.1 L); b5 (sink + puff clear dilate 5 / blur 1.2): piece_top
  0.614/0.737/0.624/0.952 (old 0.749/0.800/0.634/0.931: front -18%), sleeves front 0.79-0.81 (old 0.95), but
  bow_front_bleed 0.205 F (the dilated puffs reach the bow's loop ends with no outline: bleedpic.py) -> the puffs
  bedded behind the bow (sleeve bed). b4/b5's QA rerun on render2 (their build's QA had imported a declared.py synced
  mid-merge: keep the tree committed while box jobs run).
- Sweep d3 (collar lengths on g6_b1): side_depth 0.455 -> 0.34, back_depth 0.51 -> 0.47: piece_collar f/3q/p/b
  0.49/0.30/0.05/0.88 -> 0.87/0.53/0.03/0.94 (old body 0.66/0.47/0.03/0.93), art_outline_collar 5.7 -> 3.7 W.
- neck_crease (masked skin): the flare's bug (the rows at the cut interpolated with the unflared row under it) fixed
  (k3: F1 score 0.0282, front top at |x| 0.2 -0.543 -> -0.519, sheet -0.496); the crease the QA reads is the visible
  skin's: the flare's bottom showing under the collar (the collar masked no skin). Now the collar masks the skin under
  it (collar hide_under {reach, rim, neck}: under_sheet; the intent of neck_crease leaves a flare under a collar out):
  the unsubdivided estimate 76 -> 51 (old body 24.5 -> the QA's 12.7), one column (-65) left; trying the mask's reach.
- The jacket's neck cut in front back to the plane (the radial cut opened a round skin notch over the bow's knot: the
  neck V's outline corners, art_outline_neck 10): r [[0, 1], [40, 1], [70, 0.15], [90, 0.15], [150, 0.2], [180, 0.23]].

### Round 6 checkpoint (2026-10-01, ~680k context): state, numbers, running job, exact next steps
- **Branch tool/garments4-shoulders**, pipeline-3d 60c0f1a4 (hands2 interim) merged in (a3e425fd, CODEMAP 31932ec1).
  The joined shoulder is still OFF in charkit/spec/clawd.json; the candidate lives in variant specs.
- **New code this round (all opt-in by spec, nothing changes the default build):**
  - code_base.flare_neck (body.neck_flare {h, share by azimuth, to, p}): Michael's answer A, the head's neck rows over
    the cut pushed toward the torso's ring (fix 2: the rows round the cut at the full gap).
  - garments.shell: cuts' 5th element r (a neckline round the neck's axis; an azimuth table); `tuck` {under, sink, drop,
    ease} (the jacket sunk under the puffs, deep faces cut); `bed` as a list incl. under a hull collar (side back/front
    projections, or 'normal': bed_sheet along the collar's normal, 6 passes).
  - garments.puff: `clear_body` by body parts ({parts [shoulder, arm], inner 0}), `from_t`, `taper`, `dilate`/`blur`
    (or `spread`); `weights` {from body, rigid_from, blend} (the cap bends with the body at a raise); `bed` behind the bow.
  - garments.collar_hull `symmetric` (the halves mirrored); collar `hide_under` {reach, rim, neck} (under_sheet: the skin
    under the collar masked, the neck's flare under it too).
  - helpers body_part_mask, puff_margin, tucked, under_sheet, bed_sheet.
- **Harness (tools/garments6):** shoulderlab (design|ours|diff labels), depthgap, xsec, contain (the puff's hold on the
  deltoid), neckring, bodyj6 (body variants: score vs the sheet, whole-skin crease, bridge over the ring, posed),
  bodysec (sections by part), posed (the raises with the garments on), poke (what comes through what), skinwhere
  (the skin showing by part and why + the masked crease estimate), look (renders: design | builds), bleedpic, necklab,
  sweepk (a sweep under K vs the old body). Variant/garment sets in tools/garments6/v (body_*.json, g*.json, k*.json).
- **Best candidate so far: g6_c2** (spec charkit/out/garments6/specs/c2.json = clawd.json + tools/garments6/v/
  body_F1_fl3.json + gh.json; render2, fetched). Against the old body g5_base_r2 (K view, kcmp):
  neck_crease 12.7 -> 13.7 PASS (was 81-105); shoulder_front/back_dip FAIL -> PASS, front tilt FAIL -> PASS,
  collar_back_square FAIL -> WARN; piece_collar f/3q/b 0.87/0.52/0.91 (old 0.66/0.47/0.93); sleeves front 0.80-0.82
  (old 0.95: -14%); **still blocking:** piece_top front 0.40 / 3q 0.62 (old 0.75/0.80: the guard), bow_front_bleed
  0.065 F, art_mirror_waist 2.1 W (flag), art_outline_collar 3.65 W, art_outline_neck 8.3 W, art_speckle_neck 2.2 W
  (flags), collar_front_torn 0.036 F, collar_three_quarter_torn 0.009 F, sleeve front spikes 0.08 F, sleeve profile/3q
  profile 0.06-0.08 F, sleeve_three_quarter_rough_R F. hand_three_quarter_reach_L WARN, hair_penetration WARN,
  poke_share WARN (reported only).
- Body: F1 (lift 65, the flare at the sides and back: share [[0,0],[55,0],[85,1],[180,1]], h 0.1, p 1.5) keeps the bare
  shoulder's score vs the sheet 0.028 (round 5's 0.029; old body 0.2); F1L45 0.032. Posed (body alone) unchanged:
  strain p95 1.73-1.92, folded <= 2.7%, nothing inside the torso.
- Posed with the garments on (posed.py on g6_c0 + tuck/clear): the rigid puff leaves the deltoid's skin out under it
  (side raise 53 vertices 0.12 L); the cap weighted from the body: 8 / 0.046 L, the puff's strain p95 2.0-2.4, folded
  1.2-3.9%. Not yet run on c2.
- **Running:** optimizer opt1 (tools/garments6/v/opt1.json: base g6_c2, set {collar symmetric, clear_body from_t -0.3
  taper 0.05}, 10 knobs: the puffs' clearance gap/from_t/dilate/blur/taper, the tuck's ease/sink, the puffs' bow bed
  gap, the collar's side/back depth; objective: piece_top/sleeve/collar views toward the old body's, sleeve spikes/
  profile/rough, bow_front_bleed x3, collar torn, art_outline_collar, art_mirror_waist; guard 0.15, flags, no new FAIL;
  220 evals / 100 min, confirm top 2). Box job sweep-garments4-1001-132917-edb4 on the BUILD box, 13 workers; out
  charkit/out/optimize/g6_opt1 (log charkit/out/garments6/opt1.log). If the local follow died: `python -m charkit remote
  attach sweep-garments4-1001-132917-edb4`, then `python -m charkit sweep optimize report charkit/out/optimize/g6_opt1`.
- **Seen, not yet fixed (necklab.png, look_c.png, look_sleeve_c2.png):** the front lapels are still the hull collar's
  crumpled bits by the neck (the flat lapels, step 5, are the fix); a thin skin strip along the collar's inner edge on the
  shoulder tops (z -0.55, x 0.1-0.35; the jacket's top border / the zip band showing under the collar's rim): the
  neck's outline corners (art_outline_neck) and specks; the jacket intrudes into the neck's V at x +-0.05-0.1, z -0.55
  (the V's notch); in profile the grown puff's top came out flat (taper added); the puffs' inner edge merges into the
  jacket in front with no outline (no depth step between them).
- **Exact next steps:**
  1. Read opt1 (OUT/review/index.html, best_override.json, confirm.json); put its best into a new garment set; if
     the puff profile or bleed still block, refit the puff's upper knots (profile table's first stations: front/in/back)
     instead of growing it.
  2. The neck's base: hide the skin strip under the collar's inner rim (collar hide_under rim 0 or the jacket's top
     border raised under the collar), restore the V (the jacket's opening rows at z -0.55..-0.65 for the new chest);
     check with necklab.py and skinwhere.py, then a build (art_outline_neck, art_speckle_neck must return to PASS).
  3. Merge pipeline-3d if it moved; switch the candidate into charkit/spec/clawd.json and clawd_body_pieces.json
     (body.shoulder from tools/garments5/v/candidate_shoulder.json + body.neck_flare + the garment set).
  4. Final build; posed.py on it (both raises, the review page's posed pictures); calibrate the body-shoulder drafts
     (tools/garments5/drafts/bodyshoulder.json) on the box that holds the build: first `calibrate store g5_base
     charkit/out/g5_base_r2 --why ...` there (pipeline-3d's 8580945f fixed the read-only rewrite), then `calibrate
     'body_shoulder_*,body_axilla_*' --declared tools/garments5/drafts/bodyshoulder.json --build <final>`; move them
     into charkit/bodyshoulderqa.py (DECLARED_CHECKS) with the records.
  5. `python -m charkit pregate --box auto`; then `python -m charkit remote gate tool/garments4-shoulders --into
     pipeline-3d`. Known: 3 order-dependent test failures exist on pipeline-3d (test_optimize qa stage, test_procs,
     test_registry), per its d44db780.
  6. Review page (tools/garments5/review/body_shoulder.json as the template: design | old body | refit per view, the
     posed pictures, the summary box), then the flat lapels and art_outline_collar.
- Box hygiene: keep the tree committed while box jobs run (b4/b5's QA imported a declared.py synced mid-merge and failed;
  their QA was rerun with `remote run --fetch charkit/out/<build>/qa qa charkit/out/<build>/bundle`).

## Round 7 (2026-10-01, lean agent 7): finishing the refit to the joined shoulder
- Coordinator: Michael confirmed YES: the collar masks the skin under it, as the jacket does (collar `hide_under`;
  neck_crease's own intent). Kept.
- c2 against the old body g5_base_r2 (kcmp, piece IoUs by view): the guard blocker is piece_top only (front 0.749 ->
  0.400, 3q 0.80 -> 0.616); the sleeves in c2 are within it (front L/R 0.948/0.954 -> 0.867/0.881, -8.5% / -7.6%).
  tools/garments5/topiou.py: c2's extra jacket is all at z -0.5..-0.7 (0.064 L^2 more than the old body's), |x| 0.3-0.5
  (the jacket over the bridge's top, in front of the puff's inner top: the dome above clear_body.from_t isn't grown)
  and at |x| < 0.12 (the V).
- The V's notch (look_neck_c2.png): the jacket's opening table is unchanged (half 0.092 at z -0.6); the old body's
  lapels (collar side_depth 0.455) covered |x| 0.05-0.12 there; c2's shorter collar (0.34, sweep d3) shows the jacket
  between the lapel and the V.
- The skin strip (tools/garments7/stripwhy.py: per pixel, what lies behind the skin showing): right side only in c2
  (x 0.2-0.42, z ~-0.54), the near jacket absent there, the skin 0.03 L outside the puff (the bridge's top through the
  ungrown dome). skinwhere: bridge/border. Tied to the puff dome (opt1's from_t/taper) and the lopsided collar (c2 has
  no collar.symmetric; opt1 sets it).
- Posed on c2 with the garments on (posed.py, lab/posed_c2.png): skin out of the puff side 5 verts / 0.027 L, forward
  11 / 0.020 (c0+tuck: 8 / 0.046, 13 / 0.041); jacket strain p95 1.17, puff p95 2.09 / 2.34, folded 1.3% / 4.7%; a skin
  strip at the armpit under the puff's lower edge when raised.
- tools/garments7/compose.py: a spec with override files applied (base + body + garment sets). specs/c2.json predates
  the hands2 merge (its body.hand is the old one): the final candidate is composed from today's clawd.json.
- Body-shoulder calibration on render2 against c2 (its body is final): known-bad store hit the box's read-only
  known_bad/g5_base.json (the links made; the JSON is committed locally); calibrate job
  calibrate-garments4-1001-133646-695d -> tools/garments7/box_records/cal_body_c2.json (log
  charkit/out/garments6/cal_body.log).
- opt1 status at the checkpoint: the box job (sweep-garments4-1001-132917-edb4, build box) is still running; the local
  follow was stopped at the 30 min background limit, so its outputs aren't fetched: `python -m charkit remote attach
  sweep-garments4-1001-132917-edb4` (run_in_background, timeout 7200000) collects them. Generation 0: 0/13 feasible
  (every row breaks a constraint against the control g6_c2), best f 33.2 (the from_t low probe); rows take ~6 min each
  on 13 workers. If it stays infeasible, read history.md for the broken constraints (likely a flag check or a
  no-new-fail on the control's WARN/FAIL set) before relaunching with `keep`/looser knob bounds.
- **The skin strip, found** (tools/garments7/stripsrc.py traces the visible skin to body vertices; the shell's
  tests replayed): the neck's head sits at y +0.099 L (behind the throat), so the shoulder top's front lies at 59 deg
  round it, where gh's radial table interpolated r 0.45 (40 deg 1 -> 70 deg 0.15): the jacket was cut over the shoulder
  front out to x 0.34 above the neck plane (z -0.563), and the strip is the border skin along that edge, outside the
  puff (margin -inf / -0.12) and not under the collar. Table [[0,1],[30,1],[45,0.18],[70,0.15],[90,0.15],[150,0.2],
  [180,0.23]]: the bridge skin showing (skinwhere) front 0.0242 -> 0.0009 L^2, 3q 0.0145 -> 0.0001; the jacket through
  the collar (poke) 45 -> 51 vertices front, depths unchanged.
- **The V's notch, found** (tools/garments7/vjacket.py): the opening applies only before the chest's head (y < -0.065 L);
  the joined shoulder's throat at the neck base lies at y -0.058..-0.063, so its faces counted as the back and stayed,
  the offset carrying them 0.07 L into the V (29 jacket vertices inside the opening at z -0.55..-0.6; 77 without the
  beds; the old body 7). New opt-in `opening.ahead` (L): ahead 0.02 -> 0 there (7 left lower down, the old body's).
- Garment set tools/garments7/gi.json = gh + that neck table + opening.ahead 0.02 + collar.symmetric.
- body-shoulder checks: charkit/bodyshoulderqa.py (from the draft; front/back IoU only, the line checks guarded by them);
  first calibration on c2 (draft, cal_body_c2.json): top/side/axilla/IoU front+back CALIBRATED (axilla 0.038/0.047 WARN),
  profile IoU BLIND (known-bad 0.8785 WARN), 3q IoU COARSE (margin 0.42). declared.py's floor stand-in lacked an import
  (fixed). Module calibration rerunning (render2) -> tools/garments7/box_records/cal_body_mod.json (log
  charkit/out/garments6/cal_body3.log); the records then go to charkit/calib/records.
- opt1: each evaluation ~6 min (13 workers); gen 0: 0/13 feasible, the best so far the probe from_t at its low end
  (-0.38): f 33.19 v 0 (control 37.50). Its follower died at 13:58; reattached (log charkit/out/garments6/opt1_attach.log).
- Builds running (render2): g7_base (today's clawd.json, the K baseline with the hands2 hand) and g7_c4 (clawd.json +
  body_F1_fl3 + gi; specs charkit/out/garments7/specs; logs charkit/out/garments7/build_*.log).
- **g7_base / g7_c4 built (render2).** c4 (gi) against g7_base under K: art_speckle_neck back to PASS (0.88), art_mirror_waist
  2.1 -> 1.57 W (the mirrored collar), the strip gone (look_neck_c4.png), the body checks all PASS but the axilla (W);
  still blocking: piece_top front/3q 0.378/0.597 (base 0.749/0.799), bow_front_bleed 0.065 F, art_outline_neck 11.1 W,
  art_outline_collar 3.86 W (worst back 8.0: the puffs' inner backs and the jacket over the flap's upper corners),
  collar torn back 0.0136 F / profile 0.0165 F / 3q F (fragments), sleeve spikes/profile/rough F.
- The V's edge: the jacket alone in front view (tools/garments7/vedge.py) is clean with no beds or the bow's bed alone;
  the collar's bed along its normal (the crumpled lapels' normals sideways) notches it. The continuous opening cut
  (tried, reverted): no change. Bedding along the shell's normal (tried, reverted): blew the jacket apart. New opt-in
  bed `hold` L: within it outside the opening's edge the collar bed keeps x and z (sinks back only); left edge clean,
  right still notched (not a slide: likely faces sunk behind). Sweep s1 (render2, base g7_c4: hold 0.06 / 0.12 / no
  collar bed; art_outline_*, art_speckle_*, collar torn) -> charkit/out/garments7/sweeps/s1.
- Profile/back (look_collar_back.png): the puff's dome rises over the collar's shoulder band in profile (the design lays
  the band over a lower puff) and the puffs' inner backs lap over the flap's corners: the same crowded shoulder top
  opt1 searches (the dome's growth vs the collar's lengths).
- piece_top on c4 (topiou, xsec_c4.png): the extra jacket +0.061 L^2 front, all z -0.5..-0.7; at z -0.55 the puff's
  dome is a small ring (x 0.4-0.6, y 0..0.2) while the jacket over the bridge spans y -0.1..0.27 at x 0.4-0.45: the
  jacket stands out of the dome in front and behind. The dome must hold the bridge's top (clear_body.from_t toward
  -0.38: gen 0's best probe); the sleeves' spikes and the profile's flat top are that growth's cost.
