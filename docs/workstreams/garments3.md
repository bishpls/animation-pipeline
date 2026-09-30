# The combined garments round (tool/garments3)

The overnight run's item 2 (docs/CHARKIT_HANDOFF.md, "Overnight run plan"): the sheet-only outfit masks, the jacket over
the band and the skirt's template flaps landed together, the garments adapted to the new masks templates first, flat
rims (Michael's call L), the skirt's fit G written into the specs, one gate under policy K.

**Branch** `tool/garments3` in `~/animation-pipeline-garments3` (sparse charkit worktree), from pipeline-3d 08f93e2.

**The merged branches' own notes** (brought along by the merges):
- `docs/workstreams/outfit-source.md`: the masks from the design sheets alone (0.972 against the hand-labelled truth);
  its "Next steps".
- `docs/workstreams/garments2.md`: the jacket over the band, the puff sleeves, the band's drawn rows; "Round 3 state".
- `docs/workstreams/skirt.md`: the template flaps, the stepped band, the tuck, 18 pleats; "Checkpoint ... start here".

## Merges

1. **tool/outfit-source (3d9f456):** clean. cli.py's usage drops the removed `--field/--no-field` and lists
   `outfit score`. Tests: 50 files ok (150 s).
2. **tool/garments2 (2bf75d1):** one conflict, `charkit/bodyeval.py`: garments2's edits to the evaluator's garment
   dispatch (`garment_piece`'s template sleeves and cuffs, `garment_tones`' collar stripe and band trim) dropped, since
   geom-truth replaced that dispatch with the build's own garments stage (`geomstage`), and garments2's
   `garments.build` already carries the same routing and materials. The shorts keep one `hem_drop` (0.03) in all
   three specs. Tests: 53 files ok (127 s).
3. **tool/skirt (73fe12c):** clean (tool/skirt already had geom-truth). Its bodyeval edit (a piece built without a
   Subdivision modifier evaluates unsubdivided: the template flaps' crisp corners) comes along. One registry clash:
   the skirt's QA part and tool/artifacts' both took order 2200; the skirt's moves to 2300 (after the artifacts, which
   test_artifactqa wants after the look). Tests: 55 files ok.

## The skirt's fit G into the specs (step 4, done first: the tuck and A-line adapt on top of it)

`make_garments.py fitG_best.json` then `apply_spec.py` (the skirt's scratch harness, copied into this session's
scratchpad and pointed at this worktree) into clawd.json, clawd_body_pieces.json (still identical) and clawd_body.json:
the template flaps (`shape: template`, `hem: band`, the edges, stand, a three-tread stair), the skirt's geometric band
(0.15 L, stair 0.35/0.25/0.15), `tuck_fit`, 18 pleats (garments2's spec had 22). `_skirt_try.json` was never tracked
(it's untracked in ~/animation-pipeline-skirt, which this round doesn't touch): nothing to delete in the branch.
`flapchains` waits for a box build of this tree.

## Call L: flat, square open rims (garments._thick)

**Measured first** (scratch `rimlab.py`: a garment-scale open shell, 2.5 mm, a partial tube with a hem, a top edge and
two cut edges, built as `garments.build` builds a shell and counted by `lookprobe.normals` itself, faces whose shading
the outline turns past 90 degrees, at the build / face-board / body-board widths):

| rim | flips (build 1.2 mm / face 0.93 / body 3.94) | of which rim faces |
|---|---|---|
| as built (Solidify rim, then Subdivision: a bead) | 486 / 462 / 486 | 480 of 480 |
| `edge_crease_rim` 1 (look round 3's try: "doesn't help") | 480 / 460 / 480 | 480 |
| **`edge_crease_inner` and `_outer` 1 (the border loops)** | **24 / 0 / 30** | 12 |
| all three | 18 / 0 / 18 | 6 |
| no Subdivision | 0 / 0 / 0 | 0 |

Look round 3 creased the wrong edges: in Blender (checked on a solidified grid) `edge_crease_rim` creases the rim's
cross edges, `_outer` the surface's open border loop and `_inner` the moved layer's. Creasing the two border loops keeps
the rim a flat band square to the layers under the Subdivision, so the outline's inward move (still half the shell,
call I unchanged) no longer turns it inside out. Creasing the cross edges as well makes every border vertex a corner
(the hem a polyline) for 6-12 fewer flips; not taken.

**Built:** every garment's thickness goes through `garments._thick` (the ten `thick` SOLIDIFY sites: shells, bands,
belts, cuffs, sleeves, the skirt, collars, panels), which sets both border creases (`RIM_CREASE` 1.0; 0 restores the
bead). The evaluator follows (`bodyeval.garment_part` reads the recorded creases; `solidify` returns the creased border
loops, `subdivide` and `limit_positions` treat them as sharp and pass their children on). Against Blender on the lab's
shell: evaluator vs Blender vertices 6e-8 m apart creased (7.6e-3 m without the evaluator's crease support), 6e-8
uncreased. Test: `test_bodyeval.test_creased_rims_stay_flat_and_square`. The real build's flip count is measured on
the render-box build below.

## The first box build (g3_a: the three merges plus fit G, before call L)

`python -m charkit evaldrift charkit/spec/clawd.json --stages --out charkit/out/g3_a` (box build, then the evaluator on
the box). Against the latest pipeline-3d preview (1583cd6, 186 PASS / 36 WARN / 5 FAIL): 244 / 57 / 35, most of the new
FAILs being checks new in this round (garments2's pieceqa, the skirt's skirtqa), which the gate scores on the old
geometry too. Regressions on existing checks: `piece_collar` 0.754 PASS -> 0.342 FAIL (its **back** view 0.95 -> 0.28;
front and three-quarter better), `piece_top` 0.595 WARN -> 0.486 FAIL (back 0.85 -> 0.58), `neck_crease` 27.6 WARN ->
46.4 FAIL, `body_front_skirt_aline` 0 -> -0.161 FAIL, `body_profile_torso_jump_front` 0 -> 0.0565 FAIL, and two of
Michael's flag checks (blocking under K): `art_speckle_neck` 1.289 PASS -> 2.552 WARN (profile 30.7 -> 127),
`art_mirror_waist` 1.19 PASS -> 1.825 WARN. (That run's evaluator step synced the tree after call L's commit, so its
stage drifts compare creased with uncreased garments: rerun on a consistent build.)

### The collar's back: the body grew through its flap (code_body)

Measured (scratch `depth.py`, `depth2.py`, `hullback.py`, `torsoback.py`): at the flap's heights the **skin** stood
0.07-0.13 L further back than on garments2's build (same garment code, old masks), the jacket lifted off it, and the
jacket then sat at the collar's own depth (within 0.007 L) and hid it. The authored body is fitted to the hull
(code_body.torso: rows measured by the tight pieces' points). With the sheet-only masks the jacket beside the flap is
labelled top (it had been sleeve: the old hull has no top label behind the body above z -0.91; the new one from -0.53,
52-77 points per row at |x| 0.34-0.43), so those rows are now measured, and the per-row section carried them round the
back: the torso's back at z -0.60..-0.84 went from 0.07-0.10 L inside the hull's collar surface to 0.03 L outside it.

Fix (code_body, tool/body's file; the smallest change that holds): the collar joins `IN_FRONT` (depth 0.04 L: its
thickness, the jacket's under it, a clearance), counting only its points behind the torso's axis, on the hull's
labelled shell (the decimated mesh keeps 0-10 collar vertices near the back midline at z -0.60..-0.68), judged by the
back view's drawn extent (`drawn_back`; the front view's extents had judged every point, which would have dropped
the flap below -0.69). The torso's back under the flap moves in 0.03-0.11 L (z -0.56..-0.94: 0.055-0.066 L inside the
collar's surface, garments2's body sat 0.07-0.10); nothing else moves over 6e-5 L (the front, the lapels, the bow's
cap unchanged). Test: `test_code_body.test_the_collars_back_flap_holds_the_torso_behind_it`. The body-code step's
cache now covers charkit.garments (shell_points).

### The other regressions, measured (g3_a; not yet fixed)

- **`body_profile_torso_jump_front` 0 -> 0.0565 FAIL** and the band in profile: ours steps in 0.08 L at z -1.38 from
  the jacket's front to the band (design 0.0235 at -1.352); `waistband_profile_overhang` 0.0847 against 0.0565;
  `waistband_profile_rows` ours -1.343..-1.484 against the drawn -1.390..-1.498. With the sheet-only masks the
  profile's band mask is finally the band (the old one held the jacket's lower part), so these checks' design values
  moved too. Two causes: (1) the new body's bust stands 0.023-0.028 L further forward at z -0.9..-1.1 (the lower
  bodice is now labelled top, pulled in 0.022, not waistband, 0.035), and the jacket's fronts drape from the bust;
  (2) garments2's `hang` knots (fitted to the old masks' junction; 90 deg: 0) leave the jacket's side hem at the band's
  top, where the new profile mask draws it at -1.39 (hang about 0.056 at the side; this also agrees with the
  three-quarter's near side, 0.028 low against the front in garments2's fit).
- **`body_front_skirt_aline` 0 -> -0.161 FAIL** (ours 0.837, design 0.998): bodyqa.aline is the median width within
  0.15 L above the middle hem over the widest row no hand touches. Our skirt flares out at once under the band and then
  hangs nearly straight (a bell; close-up `cu_front_skirt.png`); the design is a straight A-line widest at the hem.
  outfit-source alone read -0.122 (the skirt's label now starts under the band, top -1.476, and reaches its dark hem).
  Plan, templates first: the skirt's columns as a line from under the band to the hem (`aline` a shape exponent
  fitted to the drawn per-view widths), not the hull's per-row section.
- **`piece_top` 0.595 -> 0.486 FAIL** (back 0.85 -> 0.58) and `neck_crease`, `art_speckle_neck` (profile 30.7 -> 127):
  expected to come mostly from the body through the collar (fixed above); to be confirmed on the next build.
- **`art_mirror_waist` 1.19 PASS -> 1.825 WARN** (back: ours 0.0365 against the design's 0.0133): not attributed yet.
- Held or better: skirt overhang L/R 0 PASS (garments2 alone 0.118 FAIL: the skirt's tuck under the band garment's
  bottom row fixed it), `body_front_torso_jump_L` 0 PASS, `piece_waistband` 0.885 PASS, the flaps' pieces 0.696/0.805,
  `art_band_lower`, `art_points_sleeves`, `art_bumps_sleeves` WARN -> PASS.

## Checkpoint (coordinator's request, about 200 tool calls in)

**Branch** `tool/garments3`, head after this commit. Merges done (outfit-source 2ae1269, garments2 8bfb844, skirt
40ec955), fit G in the specs (6bc770a), call L (dcfc681), the body's collar cap (529da75). Tests: 55 files ok at the
skirt merge; since then test_bodyeval, test_geomstage, test_subdiv, test_code_body ok (the full suite not rerun).

**Harness** (session scratchpad `g3/`, not tracked; copies of the skirt's `sk/` pointed at this worktree):
`qadiff.py A/qa.json B/qa.json` (moves by status), `cu.py OUT VIEW x0 x1 z0 z1 BUNDLE...` (design | builds close-ups,
the QA renderer, one height), `depth.py`/`depth2.py` (collar/top/skin/band depths per height in bundles),
`hullback.py HULL_DIR` (backmost hull labels per height), `torsoback.py [BODY_CODE]` (the torso's back against the
hull's collar), `ev3.py OUT [--geom DIR] [--body CODE] [--set garments.NAME.KEY=JSON]` (the evaluator: body sheet
checks, piece IoUs per view, skirtqa -> OUT/ev.json), `evcmp.py A/ev.json B/ev.json`, `rimlab.py` (Blender).
Local produced refs (hull, masks) fetched from the box (`infra/gcp/build.sh fetch WT charkit/out/hull`, `.../clawd`):
current against this tree's stamps.

**Running at checkpoint:** local evaluator job (background shell id bhxkyxrhp): `ev3.py` baseline on g3_a's codes
(-> scratchpad `g3/ev_base/ev.json`) then with the fixed body (`g3/bc1/body_code.npz` -> `g3/ev_bc1/ev.json`); purpose:
its timing and which checks it covers. No box jobs running.

**Next steps, in order** (coordinator: prefer box variant builds over porting garments2's hang fitter):
1. Box build of the head (`python -m charkit remote build charkit/spec/clawd.json --out charkit/out/g3_b`), then
   `qadiff.py` against g3_a and 1583cd6: confirm the body fix (piece_collar back, piece_top, neck_crease,
   art_speckle_neck) and call L's effect on every check.
2. The jacket over the band in profile: variant builds of `top.ease.hang` (the side knots 71-117 deg lowered toward
   0.05) and, if needed, the drape (`drape.spread`) for the bust's +0.025 L; score torso_jump_front,
   waistband_*_rows, piece_top, top_*_over_band, waistband_*_width.
3. The skirt's A-line as a template (garments.skirt_hull: a column shape exponent from under the band to the hem),
   fitted on the evaluator or by variant builds against body_*_skirt_aline, body_*_skirt_width, the hems, piece_skirt.
4. The collar's V (hidden under the bow): `v_depth` from the template, not the hull's visible labels; check
   piece_collar front/three-quarter after step 1 before touching it.
5. art_mirror_waist: attribute (left/right difference of the midriff in back).
6. `flapchains`, outfit_graph.json regeneration (outfit-source step 6), evaldrift --stages on a consistent build, the
   render-box build with boards and lookprobe --normals for call L's real flip count, the review page, one gate.

## The skirt's A-line as a template (skirt_hull `aline: {shape, sides}`)

On the evaluator (scratch `ev3.py`, the fixed body, ~2 min a run), against the same state with `aline: true`:

| aline | front_skirt_aline | back_skirt_width | profile_skirt_width | piece_skirt | skirt_back_outline | hemband_skirt_step | flap_profile_iou L |
|---|---|---|---|---|---|---|---|
| true (the hull's rows, monotone) | -0.159 FAIL | 0.866 WARN | 1.0 PASS | 0.876 | 0.033 WARN | 0.040 WARN | 0.739 |
| every column a line, shape 1.0 | -0.02 PASS | 0.834 FAIL | 0.843 FAIL | 0.786 | 0.084 FAIL | 0.506 FAIL | 0.529 WARN |
| every column, shape 0.8 | -0.02 PASS | 0.898 WARN | 0.906 WARN | 0.838 | 0.060 FAIL | 0.52 FAIL | 0.636 WARN |
| sides (sin^4), shape 1.0 | -0.02 PASS | 0.84 FAIL | 0.997 PASS | 0.822 | 0.072 FAIL | 0.047 FAIL | 0.736 |
| sides (sin^4), shape 0.8 | -0.02 PASS | 0.893 WARN | 0.997 PASS | 0.855 | 0.052 FAIL | 0.047 FAIL | 0.736 |
| **sides (sin^8), shape 0.7 (taken)** | **-0.02 PASS** | **0.936 PASS** | 1.0 PASS | 0.867 | 0.045 FAIL | 0.052 FAIL | 0.739 |

The front view's outline is the side columns, the profile's the front and back columns (and the flaps lie on the
back): the template on the sides only (`sides` k: weight |sin th| ** k) fixes the bell without touching the profile.
Worse: `skirt_back_outline` 0.033 WARN -> 0.045 FAIL and `hemband_skirt_step` 0.040 WARN -> 0.052 FAIL; both are
tool/skirt's new checks, FAIL on round 6's geometry (0.051, and no step found), so not new FAILs in the gate's 2x2 if
pipeline-3d's geometry reads the same; to report.

## Box builds g3_b (the body cap, call L) and g3_h1 (a hang variant); the pipeline-3d merge

- **g3_b** (529da75) against g3_a: `piece_collar` 0.342 FAIL -> 0.771 PASS, `piece_top` 0.486 FAIL -> 0.653 WARN
  (pipeline-3d 0.595), `neck_crease` 46.4 -> 39.6 FAIL (pipeline-3d 27.6 WARN), `sleeve_profile_rough_L` 0.0105 WARN ->
  0.0021 PASS; worse `piece_sleeve_cuff_R` 0.508 WARN -> 0.496 FAIL (pipeline-3d 0.500 WARN), `flap_back_attach_R`
  0.08 WARN -> 0.1035 FAIL, `flap_profile_attach_R`/`sweep_R` PASS -> WARN. Unchanged: `art_speckle_neck` 2.6 WARN (all
  in profile: 130 against the design's 50), `art_mirror_waist` 1.65 WARN, `body_profile_torso_jump_front` 0.061 FAIL.
  In profile the jacket's shoulder still covers the collar's side (the cap counts only the collar behind the torso's
  axis within the back view's x +-0.40); `piece_collar`'s profile view was 0.016 on pipeline-3d too.
- **g3_h1** (the jacket's `hang` from the new masks' drawn junction: side 90-100 deg 0 -> 0.04, back 180 0.06 ->
  0.01): `waistband_profile_rows` 0.047 FAIL -> 0.009 PASS, `piece_waistband` 0.886 -> 0.922, but
  `body_front_torso_jump_L` 0.009 PASS -> 0.038 FAIL and `waistband_back_rows` 0.005 PASS -> 0.042 FAIL, and the
  profile's torso jump unchanged: **not taken** (the hang stays garments2's). Scratch `junction.py` measures the drawn
  and our jacket hem per column per view.
- **Merged pipeline-3d a3073f5** (tool/look4: call M, the bow and boots' measured outline cap; art_spikes_boots,
  bumps_boots, bumps_legs and mirror_waist promoted to FAIL-capable): one conflict in garments.py (call L's `_thick`
  beside look4's `LINE_CAP_MEASURED`; the skirt's optional Subdivision beside look4's `cap='measured'`), both kept.
  `test_cache.test_code_closure` edited a line call L had replaced; it now edits the panel's `_thick` call. The hull's
  shell reader (`STRAY`, `shell_points`, `shell_patches`) moved to `charkit/geom/hullshell.py` (garments re-exports it):
  code_body importing garments had put garments.py into the hair stage's code closure. Tests: 56 files ok.
- **flapchains** (`python -m charkit flapchains charkit/spec/clawd.json --build charkit/out/g3_b`): both flaps' chains
  (7 joints) rewritten in `outfit_notes.json` for the template flaps (their root at the band's back corner, x 0.125,
  z -1.463; the tail to z -2.956), the graphs relayered (`refs/clawd/outfit_graph.json`: the chains only; its full
  regeneration from the sheet-only masks, outfit-source's step 6, isn't done), the manifest's sha256 updated.

**Launched together at c0010c2+flapchains** (no edits while they run): `evaldrift --stages --out charkit/out/g3_c`
(box build and the evaluator), `remote gate tool/garments3 --into pipeline-3d` (report in charkit/out/gate/),
`remote --box render build charkit/spec/clawd.json --boards body --out charkit/out/g3_render`.

## The gate, the consistent build, call L measured, the review page (end of round)

**Gate** `python -m charkit remote gate tool/garments3 --into pipeline-3d`: 7408658 into a3073f5, **FAIL**. Report:
`charkit/out/gate/gate_tool-garments3_7408658_into_a3073f5.md` (and .json). Tests all ok. No --accept. Under K:
- **New FAILs on existing checks:** `body_profile_torso_jump_front` 0 PASS -> 0.0612 FAIL; `neck_crease` 27.6 WARN ->
  39.6 FAIL; `piece_sleeve_cuff_R` 0.500 WARN -> 0.496 FAIL (0.004 under the line).
- **Flag-check regression:** `art_speckle_neck` 1.289 PASS -> 2.602 WARN (all in profile: 130 against the design's 50).
  `art_mirror_waist` 1.19 -> 1.17 PASS on the gate's build (g3_a/g3_b read 1.83/1.65 WARN: to watch). Flag checks
  better: `art_band_lower`, `art_bumps_sleeves`, `art_points_sleeves` WARN -> PASS (promotable), `art_outline_collar`
  WARN -> PASS.
- **2x2, the new measures regressed on the new geometry:** `bow_profile_torn` 0 -> 0.025 FAIL and `bow_front_tail_gap`
  0 -> 0.033 WARN (garments2's known drops), `flap_three_quarter_iou_R` 0.571 WARN -> 0.0 FAIL and
  `flap_three_quarter_width_R` 0.073 WARN -> 0.184 FAIL (the three-quarter's drawn tails disagree with the other
  views; the skirt fit weighted it 0.25), `hemband_overskirt_panel_R_steps` 2 WARN -> no step FAIL, `shorts_*_hem`
  0.0-0.014 PASS -> 0.028-0.038 WARN (four views).
- **Build CPU** (Blender and QA) 229.8 -> 349.9 s = **1.52x** (over 1.5x). Likely garments2's `refine: 2` on the top
  (14,168 -> 197,608 faces), untimed per stage.
- Better (selection): `piece_waistband` 0.453 FAIL -> 0.886, `piece_overskirt_panel_L` 0.422 FAIL -> 0.698 WARN, `_R`
  0.623 -> 0.807 PASS, `piece_shorts` 0.393 FAIL -> 0.601, `piece_skirt` 0.762 -> 0.869, `piece_cuff_L` 0.659 WARN ->
  0.779 PASS, `body_profile_iou` 0.852 -> 0.916, `body_profile_leg_outline` 0.574 -> 0.014, `piece_skirt_extent` 0.127
  WARN -> 0.014 PASS, `body_front_skirt_aline` held at -0.02 PASS. WARN moves: `body_three_quarter_iou` 0.855 PASS ->
  0.840 WARN, `body_back_skirt_width` 0.995 -> 0.936.

**evaldrift** `--stages` on the consistent build `charkit/out/g3_c` (7408658): **0 of 110 checks drift**. Stage drifts
left: the collar evaluated 0.012 L apart; the template flaps 7,526 against 2,072 vertices (evaldrift's stage compare
subdivides a piece the build leaves unsubdivided: from the skirt merge, evaldrift's side); the masked skin 0.199 L (95
vertices; the same on g3_a). Every creased garment's evaluated stage now matches Blender (call L's evaluator side).

**Call L on the real build** (`lookprobe --normals` on `charkit/out/g3_render/clawd.blend`, result copied to
`charkit/out/g3_render/normals.json`; the "before" is look round 3's measurement, an older garment set): garment faces
flipped by the outline at the build width 5,757 -> 338 (rim faces 5,527 -> 38), the face boards' 4,526 -> 233 (rim
4,385 -> 17), the body boards' 9,193 -> 3,798 (rim 6,102 -> 138; the rest are layers and the thick bands' edge rings,
3,660).

**Render-box build with boards:** `charkit/out/g3_render` (boards body_000/035/090/180). **Review page:**
`charkit/out/g3_review/index.html` (design | pipeline-3d 1583cd6 | garments3: full figures on the EEVEE boards;
close-ups of the collar's back, the neck in profile, the jacket over the band in profile, the skirt's front, the
flaps back and profile, the back tuck; every check whose status moved). Generator: scratch `review3.py`.

## Open, in order (for the next round)

1. `body_profile_torso_jump_front` (0.061): the jacket's fronts drape from the bust, which the new body puts 0.025 L
   further forward; the band's front recessed 0.08 L behind them at z -1.38 (design 0.0235). Try the drape
   (`top.ease.drape`) or the band's front radius (its hull points in front are the jacket's in profile).
2. `neck_crease` / `art_speckle_neck`: the neck's joint at the back side (column 125) and the collar in profile, where
   the jacket's shoulder still covers the collar's side: extend the body's collar cap to the shoulders' sides (the
   cap counts only the collar behind the torso's axis within the back view's x +-0.40), or lift the jacket's shoulders
   under the collar.
3. Build CPU 1.52x: time the garments stage; the top's `refine: 2`.
4. The 2x2 drops above: Michael's calls (bow, three-quarter flaps), the shorts' hems (the new masks' shorts label).
5. `piece_sleeve_cuff_R` 0.496: call L's creases or the body; attribute.
6. The hang (`g3_h1`) fixes `waistband_profile_rows` but costs `torso_jump_L` and `waistband_back_rows`: the front
   and profile junctions disagree at the side; a per-view fit (garments2's fithang on the evaluator) is the next tool.
7. Not done: the collar's V from the template (piece_collar front 0.63, three-quarter 0.49 already above
   pipeline-3d's 0.55/0.24); outfit_graph.json's full regeneration from the sheet-only masks (outfit-source step 6);
   the TRELLIS cleanup; promoting art_points/bumps_sleeves and art_band_lower (they PASS here).

## Round 2 (the second agent): clearing the gate's blockers under K

Scratch harness (session scratchpad `g4/`, not tracked): `qaprof.py` (cProfile per QA part), `qadump.py BUNDLE OUT
parts` (every check and table of the named parts, for exactness), `front.py` (the profile's front edges, design masks
against a bundle), `ev4.py`/`ev5.py OUT [--set garments.NAME.KEY=JSON]` (the evaluator: piece IoUs per view, the
profile's front edges per height, ev5 also the neck crease on the masked skin; `RIM_CREASE=0` env for call L off),
`evshow.py DIR...`, `collarside.py` (the collar's hull shell against the torso and the top by azimuth and height).

### Build CPU 1.52x: measured, it is the new QA, not the top's refine

The candidate's trace (g3_c): Blender 97 s (the garments stage 7 s), QA 246 s against look4's 154 s. The new parts:
`piece_details` 36.6 s and `skirt` 34.7 s (neither on pipeline-3d), `sheet_pieces` 28.7 -> 38.3 s. Profiled locally: the
z-buffer of all 975k faces (the top's refine: 2 is 395k of them) is 1.8 s for four views; the time is morphology on the
whole design grid per piece (distance transforms, openings, closings, absorbing lines). **bdeeb8e**: those measures on
each piece's own window (`bodymeasure.window`), exact: every check and table of sheet_pieces, piece_details, skirt,
details and sheet_body identical on g3_c's bundle; sheet_pieces 15.8 -> 2.6 s, piece_details 21.3 -> 11.7 s (laptop).

### The jacket's fronts in profile (torso_jump_front, bow_profile_torn)

Measured (`front.py`, profile, x of the front edge, L): the design's bib stands at -0.097..-0.102 (z -1.23..-1.32; the
figure's ink edge -0.116..-0.121), its hem comes in to the band (-0.050..-0.055) by z -1.35. Ours hangs straight from
the bust at -0.144 down to z -1.37, then the band at -0.060: the 0.085 step. The bow's tails in profile hang at the
jacket's front (-0.144), so the jacket covers their lower edge (bow_profile_torn). On the evaluator: `drape.taper` 3
brings the front in to the band (-0.144 at z -1.11, -0.10 at -1.23..-1.26, -0.079 at -1.32, -0.064 at -1.35) and the
bow's tails show in front of it; piece IoUs top 0.657 -> 0.669 (profile 0.47 -> 0.53), waistband 0.886 -> 0.907,
bodice_panel 0.804 -> 0.828, bow 0.604 -> 0.598. `from` -1.05 with taper 3: top 0.674, bow 0.633 (front 0.668 ->
0.712), waistband 0.907. `from` -1.05 alone changes nothing in profile.

### The neck (neck_crease, art_speckle_neck)

pipeline-3d's masked skin shows no neck column at +-115..175 degrees near the cut (the jacket hides it); ours shows
+-125..145 (crease 39.5-39.6 there; g3_a +-115..175). At the shoulders' sides (90 deg, z -0.62..-0.78) our torso stands
at 0.404-0.416 L from its axis, pipeline-3d's 0.31-0.365; the hull's collar has no points there (only above z -0.58
and behind, 105-180 deg). A cap over the collar's side points (tried, reverted) bound only at 50 deg (the lapels).

Measured on the evaluator (`ev5.py`: its masked skin reads the box's 39.6 exactly; `neckline.py` per column): at
+-125..175 the masked skin shows down to z -0.597, one body row below the jacket's neckline, which dips at the back
(-0.549 at 125 deg, -0.591 at 155) where the region's `neck` weight rule leaves the upper back out; the collar covers
that band in the render but not in the mask. The top's `refine` 0/1/2 leaves the crease at 39.6 (not the cause).

| top variant | neck_crease (worst col) | back cols 125/135 | top IoU (front/3q) | collar |
|---|---|---|---|---|
| as merged (neck 0.3, cut 0.04) | 39.6 (125) | 39.6 / 29.0 | 0.364 / 0.515 | 0.784 |
| **neck 0.6 (taken, d7029ef)** | **26.9 (75)** | 17.6 / 14.7 | 0.364 / 0.515 | 0.784 |
| cut 0.08 | 45.4 (65) | 39.9 / 20.5 | 0.342 / 0.499 | 0.786 |
| neck 0.6, cut 0.08 | 18.7 (-25) | 1.8 / 8.6 | 0.342 / 0.499 | 0.786 |

(IoUs with taper 2.) pipeline-3d reads 27.6 WARN. art_speckle_neck needs the box's look QA.

### Taken so far (commits)

- bdeeb8e the QA's windowed measures (exact); 1be39ab `drape.taper` 2 in the four specs that carry it (clawd, clawd_body,
  clawd_body_pieces, clawd_code) and the promotion of art_points_sleeves, art_bumps_sleeves, art_band_lower
  (`artifactqa.PROMOTED`; re-measured with this code: points_sleeves body6 31.7 / pipeline-3d 27.9 vs 0.0, bumps_sleeves
  63.7 / 45.6 vs 0.0, band_lower body6 3.259 vs 1.201: 2.7x); d7029ef the top's neck weight 0.6.
- Taper variants on the evaluator (piece IoU top / bow / bodice / waistband): none 0.657/0.604/0.804/0.886; taper 2
  0.690/0.674/0.839/0.907; 3 0.669/0.598/0.828/0.907; 4 0.667/0.600/0.825/0.907; from -1.05 + 3 0.674/0.633/0.826/0.907.
- af8cd2c merged pipeline-3d b43c15e (infra3 milestone A: K in gate.py, CPU seconds at the same thread cap;
  toonrender2: the QA draws with charkit.render; hair4). Clean. infra3's local pre-gate check isn't in yet (its (l)).

### The three-quarter flaps

The flaps' template edges run 126-166 deg (fit G); the drawn three-quarter tails sit at about +-100 deg while front,
back and profile place them at 118-155 (skirt.md). g3_c three-quarter px ours/drawn: R 305/5409, L 6348/11607 (IoU
0.0 / 0.013); the other views 0.73-0.88. The design's views disagree: Michael's call.
