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
