# Workstream: face round 6, Michael's face flags (`tool/face6`)

Worktree `~/animation-pipeline-face6` (sparse), branch `tool/face6` from pipeline-3d 004efc3. Michael's review of the
build (2026-09-30 evening, preview 1580f95):
1. the iris doesn't fit (larger than the opening, past the sclera; the design's iris top and bottom sit on the lid lines);
2. the lash detail is lost (a solid block; the design's upper lash line has spikes, flicks, separation);
3. the brows' shape and thickness are a little off;
4. the default smile is quite off-model;
5. the mouth seems misplaced in three-quarter;
6. in profile the mouth reads higher than the reference;
7. the nose is invisible from the front and three-quarter (the design draws a small nose mark).

Nothing measured any of them (eye_iris_ratio is a width ratio; no lash, brow, smile, mouth-placement or front/3q nose
check). Order: measure each flag as a calibrated check, then fix cheapest-visible first, reporting the face pieces' shape
IoU per view beside every check moved.

## State

- Step 1 (measurement): `charkit/faceflags.py`, the QA part `face_flags` (order 850). Lab scripts under
  `charkit/out/face6/` (lab1-6).
- Step 1 done (cb540dd): 28 graded flag checks + 5 INFO shape IoUs (`face_piece_*`, per view; the guard's reading)
  + 2 INFO reads the references can't resolve (turnaround profile iris, turnaround 3/4 lash detail). Calibration records
  in `charkit/calib/records/` (all 28 calibrated: the design moved 1-2 px plus half a pixel re-sampled passes, face6_before
  = preview 1580f95 FAILs every one, the floor generators in `charkit/calib/faceflags.py` don't pass). Known-bad stored:
  `python -m charkit calibrate store face6_before ~/animation-pipeline-3d/charkit/out/previews/1580f95 ...`; current
  build for calibration: `charkit/out/calib/cur_face6_1580f95` (curbuild.py: the preview's qa.json + face_flags).
- Step 2 (first fixes, in the spec and code; box build pending):
  - iris inscribed in the opening: `iris.rz` 0.54 -> 0.425, `cz` -0.01 -> 0.105 (the visible opening at the iris's
    column spans -0.303..0.53 eye widths; bottom a hair under the lower lid), pupil size kept absolute (the visible
    iris's height is unchanged: pupil_run 0.993 -> ~1.12, pupil_h 1.07), `pupil_cz` 0 (centred), shine kept absolute;
    the iris's top now shows, so its colour is the design's (`top` (0.55, 0.33, 0.14), sampled off both sheets) and
    the lid shadow lighter (new eyetex knob `lid_shadow` 0.45 -> 0.15). Lab (texture swapped into 1580f95's bundle):
    iris_fit front 1.06/1.04 (design 1.04/0.99), close-up front 1.11/1.10, profile 1.01; 3/4 far eye 1.43 (design 1.05:
    open). eye_lid_gap stays PASS only with the lighter top (the old segmentation read a dark iris top as skin);
    eye_view_profile_flick_out is a knife edge (its window ends at the opening's middle row, where the flick's tip
    lies: rz 0.4165 reads -0.244 FAIL, 0.425 0.038 PASS, 0.435 FAIL): flagged for a remeasure.
  - rest mouth (mouth `rest`, only the neutral; no other shape inherits it): width 1.6 widths (0.208 L; design 0.2025),
    smile 0.14 (design sag 0.135), gap 0.0015 L and line_w 0.005 L (a thin closed line), drop 0.012 L (the whole mouth
    lower: profile height between nose and chin 0.365 vs the design's 0.455). code_base.mouth_block lowers the rest
    loop by `drop` (the block unchanged); cli.code_head's cache key now carries spec `mouth` and charkit.mouth.
  - nose mark: `charkit/nose.py` (a decal on the face round the nose tip: an ink tick and a highlight, object `nose`
    in group mouth, slots nose / nose_high), wired in character (features + Blender), faceeval, bodyeval, qa3d classes;
    on when the spec has a `nose` section (clawd.json: `{}`).
  - lashes: band `lash` 0.034 -> 0.02, `spikes` (new eyes knob; eyes.spike_lines/spikes: strokes off the band's outer
    edge, angle from straight up), merged into the upper lash ribbon (slot 0); chevron_lashes folds them flat (same
    vertex count). Flat lab (`charkit/out/face6/lashfit.py`): spikes 4/6, gaps 7/8 against the close-up; the render's
    band reads ~0.013 L thicker than the ribbon (the lid's eyeline under it).
  - brows fitted to the close-up's front brows (`charkit/out/face6/browfit.py`, centred-mask IoU + thickness + arch):
    IoU 0.46 -> 0.84/0.82, thick 0.0167 (design 0.0178), arch 0.100 (0.096), length 0.154 (0.151).

## Checkpoint (2026-09-30 night, context limit): state for the next agent

Branch `tool/face6` head: see `git log -1` (2bdfc58 = the fixes; later commits notes only). Nothing gated, nothing
pushed. pipeline-3d has moved to 3f7b7308 since the fork (004efc3): merge it before gating; tool/face5 is landing
(code_base.py, headfit.py: expect a small conflict around code_base.mouth_block).

**Jobs done:** pregate on 2bdfc58 into 3f7b7308 PASS (20 moved, 0 blocking; the evaluator's 384 checks;
`charkit/out/pregate/pregate_tool-face6_2bdfc581_into_3f7b7308.md`). Render-box build `charkit/out/face6_a` (boards
views, body, design; 1260 s CPU, the hull rebuilt: code_base changed, so expect the gate's CPU near the 1.5x line on a
produced-cache miss).

**The flag checks: design / before (1580f95, `charkit/out/calib/cur_face6_1580f95`) / after (face6_a).** Ratio checks
read ours / design (1 = the design); differences read ours - design (0 = the design).

| check | design | before | after |
|---|---|---|---|
| eye_iris_fit_front (iris height / opening, ratio) | 1.036 | 1.324 FAIL | 1.009 PASS |
| eye_iris_fit_three_quarter | 1.048 | 1.654 FAIL | 1.383 FAIL (the far eye) |
| eye_iris_fit_profile (INFO: 15 px iris) | 1.112 | 1.243 | 0.842 |
| eye_iris_fit_closeup_front | 0.993 | 1.514 FAIL | 1.072 PASS |
| eye_iris_fit_closeup_profile | 1.083 | 1.259 FAIL | 0.887 WARN (now short) |
| eye_lash_band_closeup_front | 0.0222 L | 1.653 FAIL | 1.153 PASS |
| eye_lash_band_closeup_profile | 0.0233 | 1.575 FAIL | 0.979 PASS |
| eye_lash_band_three_quarter | 0.025 | 1.6 FAIL | 1.0 PASS |
| eye_lash_spikes_closeup_front | 6 | 0.333 FAIL | 0.167 FAIL |
| eye_lash_spikes_closeup_profile | 4 | 0.0 FAIL | 0.0 FAIL |
| eye_lash_gaps_closeup_front | 8 | 0.125 FAIL | 0.75 PASS |
| eye_lash_gaps_closeup_profile | 10 | 0.2 FAIL | 0.4 WARN |
| eye_lash_spikes / gaps_three_quarter (INFO) | 5 / 10 | 0.2 / 0.0 | 0.8 / 0.4 |
| brow_shape_closeup_front (IoU) | 1 | 0.463 FAIL | 0.832 PASS |
| brow_shape_closeup_profile | 1 | 0.509 FAIL | 0.471 FAIL |
| brow_thick_closeup_front / profile | 0.0178 L | 0.562 / 0.624 FAIL | 0.876 WARN / 1.062 PASS |
| brow_arch_closeup_front / profile | 0.096 / 0.127 | -0.030 / -0.034 FAIL | 0.003 / 0.010 PASS |
| mouth_smile_width | 0.2025 L | 0.617 FAIL | 0.914 PASS |
| mouth_smile_curve (sag) | 0.135 | +0.055 FAIL | -0.025 WARN |
| mouth_smile_open (thickness ratio) | 0.005 L | 2.5 FAIL | 2.0 WARN |
| mouth_place_three_quarter (L) | 0 | 0.0865 FAIL | 0.076 FAIL |
| mouth_place_profile / closeup_profile | 0 | -0.090 / -0.075 FAIL | -0.047 WARN / -0.035 PASS |
| nose_mark_front / three_quarter (ink ratio) | 1 | 0 FAIL / 0 FAIL | 0.5 PASS / 0.363 PASS |
| nose_mark_at_front / three_quarter (L) | 0 | none FAIL / none FAIL | 0.0035 PASS / 0.021 WARN |

18 of the 28 graded flag checks PASS (0 before), 6 WARN, 4 FAIL (iris 3/4, spikes front and profile, brow profile
shape, mouth 3/4 place: 5 counting that).

**Pieces' shape IoU per view (the guard), before -> after:** iris front/3q/profile 0.847/0.762/0.677 -> 0.907/0.817/
0.698; lash 0.526/0.286/0.226 -> 0.514/0.23/0.139 (profile -38%, 3/4 -20%: the guard would read these against an
improved lash check; the lash's shape vs the design is the open item); brow 0.461/0.509 -> 0.818/0.471; mouth 0.11/
0.261/0.408 -> 0.465/0.421/0.658; nose 0/0 -> 0.478/0.

**Other checks that moved status (face6_a against 1580f95; the gate's baseline will be pipeline-3d's, so the
accessory and terminator improvements and collar_back_iou/jaw_taper_shape belong to pipeline-3d's own moves):**
- mine, to fix before the gate: `face_preset_effort` 0.0 PASS -> 1.952 FAIL: mouth_width_rel 0.905 (want >= 1.1): the
  clench (1.45 widths = 0.189 L) is now narrower than the wider rest mouth (0.208 L). Scale the action shapes' widths to
  the new rest (or grade width_rel against the unit width), and re-check every face_preset_*;
- `eye_view_profile_flick_out` 0.038 PASS -> -0.337 FAIL: the knife edge noted above (eyeqa.flick's window stops at
  the opening's middle row, where the flick's tip lies; the iris and the thinner lash moved the opening's box). Fix the
  measure (window to the far corner's row plus a margin), register a step in charkit/steps, write a calibration
  adapter and record (eyes2's checks have none);
- `eye_aspect` 0.954 PASS -> 0.872 WARN, `eye_lid_span` 1.022 -> 0.843 WARN: eyeqa.measure's colour segmentation of
  the opening (the iris's new top colour and the thinner lash); check with the qa_eyes.png pair before changing knobs;
- `face_folds` 8 -> 35 (PASS, limit 40): 2-4 folds per mouth key now (the wider rest loop); look at the rings.

**Next steps, in order:**
1. Merge pipeline-3d (3f7b7308 or newer) and resolve code_base.py.
2. face_preset_effort: the action mouths' widths against the new rest (the rest is 1.6 widths).
3. eye_view_profile_flick_out's window (remeasure, step, record) and eye_aspect / eye_lid_span.
4. Lashes: the spikes read 1 of the design's 6 in front, 0 in profile: compare `qa_face_flags.png` and the boards; the
   render's spikes are probably too thin or lost under the band (try width 0.01 L, longer, fewer; profile: the spikes
   lie in the turned surface's plane and vanish edge-on). Keep face_piece_lash's profile from dropping more.
5. The 3/4 far eye's iris (1.38): the far eye's lower lid hides less (parallax); and closeup profile now short (0.887).
6. Mouth in 3/4 (0.076 L off): the design draws it under the eyes' midpoint (x +0.005 L), ours 0.046 L toward the
   leading contour (the muzzle 0.08 L in front of the eye plane); an anime "flat" placement in 3/4 is a per-view cheat
   or a face-shape change: a call for Michael. Profile now WARN (-0.047): drop 0.012 -> ~0.02.
7. Brow profile shape (0.471): the profile brow is foreshortened differently; fit in profile too.
8. Review page: `PYTHONPATH=. python charkit/out/face6/page.py charkit/out/face6/review charkit/out/calib/cur_face6_1580f95
   charkit/out/face6_a --start ~/animation-pipeline-3d/charkit/out/previews/1583cd6/boards --summary SUMMARY.json`
   (the summary box's html in the json's `html`), then the calibration records' `current` re-run on the fixed build
   (`curbuild.py` isn't needed: face6_a's qa.json has the checks), pregate, gate.

## Earlier: running (2026-09-30 night; done, see the checkpoint)

- Box build (render box, boards views,body,design) of 2bdfc58: `charkit/out/face6_a` (log `charkit/out/face6/build_a.log`;
  the hull rebuilds: code_base changed). Pregate: `charkit/out/face6/pregate_a.log`.
- Review page harness: `charkit/out/face6/page.py OUT NOW_BUILD OURS_BUILD --start BOARDS --summary JSON` (design |
  start 1583cd6 board rescaled | now 1580f95 | ours, per flag and view; the old face checks before/after; the pieces'
  IoU). NOW_BUILD = `charkit/out/calib/cur_face6_1580f95` (its qa.json has the face_flags checks).
