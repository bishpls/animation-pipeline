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

## Round 2 (relaunched lean, 2026-09-30 night)

Scope (coordinator, Michael): the default/rest expression only (iris, lashes, brows, rest mouth, nose). Presets, eye and
brow variants and visemes are paused: keep every preset check measured, don't tune them; a preset the rest change breaks
is reported for a named acceptance ("expressions paused (Michael, 2026-09-30)").

Merged pipeline-3d 3f7b730 (clean). tool/face5 not merged yet (expect code_base.py).

**Labs (charkit/out/face6r2/):** `assemble.py` builds the face in the venv from a build's resolved spec (geom/ paths
rebased): `assemble.bundle(build, over)` is faceeval's in-memory bundle (no hair, garments or target) in ~25 s, and
face_flags on it in ~15 s; it reproduces face6_a's eye, lash and brow reads exactly (the mouth's profile marks and the
nose differ: no neck variant; compare deltas there). `eyerun.py BUILD JSON...` (eye, lash, brow checks, pieces' IoU,
eye_*, eye_view_*), `tips.py` (counted lash tips), `eyelab.py`, `lashlab.py`, `browlab.py`, `far3q2.py`, `farfit.py`,
`flicklab.py`, `eyeseg.py`, `ffrun.py BUILD [OUT.json]` (face_flags on a build).

**Done:**
- face_preset_effort FAIL (mouth_width_rel 0.905 < 1.1): the clench (1.45 widths = 0.189 L) against the wider rest
  (0.208 L). Made relative to the rest it would be 2.32 widths = 0.30 L, wider than the laugh (the mouth block's
  extreme: the head's cage would move). Not tuned (expressions paused): reported for a named acceptance.
- eye_view_profile_flick_out: remeasured (eyeqa.FLICK_BELOW: the window reaches 0.15 opening heights under the far
  corner's row; it ended at the opening's middle row, where face6_a's flick tip lies). face6_a 0.219 -> 0.531 (design
  0.556); the design and 1580f95 unchanged. Step d6c5ee7, record (guard: no stored build has a wrong flick).
- eye_lid_span PASS -> WARN (1.022 -> 0.843): the same window cut the flick off the front lid line (the iris inscribed
  moved the opening's bottom up 3 px, its middle row with it). Remeasured the same way: 1.096 -> 1.247 (design 1.30).
  Step 314025e, record (guard).
- eye_aspect PASS -> WARN (0.954 -> 0.872): the old iris overflowed past the lower lid and segment()'s opening took its
  ellipse (2 px taller: swapping the old iris back reads 0.849); the thinner lash uncovered 3 px of white at the outer
  corner (open_w 0.1753 -> 0.1828).
- The eye textures' span (eyetex.SPAN 1 -> 1.25, TEX_N 640, plate UVs / SPAN): the inscribed iris reached 0.53 eye
  widths up, past the texture's edge, which cut its top flat; the sclera past +-0.5 widths was clipped black at the
  corners. Lab: eye_aspect 0.872 -> 0.944 PASS, iris front 1.009 -> 0.998, 3/4 1.383 -> 1.342, face_piece_iris profile
  0.698 -> 0.782; eye_lid_gap 0.0036 -> 0.0042 (WARN by 0.0002); the profile flick 0.531 -> 0.40 (the far corner's
  white now reads to the corner: 3 px further out): lengthen the flick.
- **Build B's set** (venv lab on face6_a, `run_cand*.log`, `run_v1-3.log`): style anime `eyes.fold_shape` 0 (new knob,
  eyes.Surface: the fold runs straight down at the iris's middle-row nasal edge; following the iris outline row by row
  compressed the far eye's iris more in its middle rows: a straight-sided iris), spec `eyes.lash` 0.02 -> 0.022,
  `lash_inner` 0.75 (the band's inner half had thinned under the measure's opening and swallowed the inner spike), six
  spikes (two added: t 0.1 and 0.5; the outer-corner one at 0.985), `flick` 0.26 -> 0.32 (the profile flick against
  the corner the SPAN fix uncovered); eyes.SPIKE_ROOT 0.55 -> 0.3 (roots inside the band). Lab readings, face6_a ->
  set C: iris 3/4 1.383 FAIL -> 1.127 WARN, iris closeup profile 0.887 -> 0.936 PASS, lash spikes closeup front
  0.167 FAIL -> 1.0 PASS, gaps front 0.75 -> 0.875, profile gaps 0.4 -> 0.8 PASS, lash band 1.0/1.10/0.9, eye_aspect
  0.872 -> 0.944 PASS, lid_span 0.843 -> 1.012 PASS, lid_gap 0.0033 PASS, profile flick -0.337 -> -0.056 PASS; every
  eye_view_* PASS. Pieces' IoU (1580f95 / face6_a / C): iris front 0.847/0.907/0.898, 3/4 0.762/0.817/0.808, profile
  0.677/0.698/0.721; lash front 0.526/0.514/0.489 (-7%), profile 0.226/0.139/0.233 (+3%), 3/4 0.286/0.23/0.259 (-9%).
  Tried and dropped: fold_follow 0 (iris 3/4 1.32), fold_soft 0.12 (1.33), fold_at -0.08/+0.1 (1.47/1.43), turn
  (-10, 20, 50) (1.26, but profile flick -0.36 FAIL, lid_span WARN) and (-10, 30, 60) (3/4 behind FAIL).
- Still failing after C (lab): `eye_lash_spikes_closeup_profile` 0/4: our profile lash band runs on a slant, and the
  measure's opening (a disk of 0.45 x the band's median column height, which a slanted band over-reads) erodes the whole
  band into one wide "tip" that swallows the spikes; the design's profile band runs level over the top. The profile
  eye's shape (the turned surface: its outer part recedes on a diagonal), not the spikes. `brow_shape_closeup_profile`
  0.469: our brow spans 0.097 L in depth on the forehead (its profile length) against the drawn 0.136; its front length
  pins its x-extent (0.155 L), so the forehead at brow height is flatter than the design's (a circle of radius ~0.34 L
  through the brow's ends against ~0.29): head shape (the head fit's eye window holds the brow region back), not the
  brow. `mouth_place_three_quarter` (below).
- **Mouth in three-quarter (Step 1, "is it ours?")**, face6_a's reads (L; x from the eyes' midpoint, the near eye in
  profile; lead from the leading contour): design front x 0.0003 lead 0.256, 3/4 x +0.0046 lead 0.173 (contour -0.168),
  profile x -0.047 lead 0.056 (contour -0.103); ours front -0.002 / 0.246, 3/4 -0.031 / 0.097 (contour -0.128),
  profile -0.070 / 0.018 (contour -0.088). The 0.076 L miss is two parts: (a) the mouth against the eyes, 0.036: ours'
  own geometry projects the profile's mouth-to-eye depth into three-quarter at 0.443 (0.031 / 0.070); a rigid head
  with the design's profile (-0.047) puts the 3/4 mouth at -0.021, so the drawing's +0.005 sits 0.025 L back from any
  rigid head that matches its profile: not ours. Our profile stroke also sits 0.038 L nearer the lip contour than the
  drawn one (lead 0.018 vs 0.056: the design draws the profile mouth as a short stroke set back from the lips); (b) the
  far cheek's contour at mouth height, 0.040: our lower face's section is more V-shaped (the 3/4 contour over the front
  half-width 0.515 against the design's 0.656; a section carrying the width forward reaches up to 0.81): ours, and
  fixable without moving the front or profile silhouettes (only the section between them), but it is the head fit's
  (tool/face5's three-quarter cheek and jaw work is landing). Best joint fit for the mouth's depth (least squares over
  profile and 3/4): profile 0.009 L off, 3/4 0.021 L off (now 0.023 / 0.036); with (b) fixed the 3/4 check would read
  about 0.025 (WARN). The view-exact placement is a per-shot override for Michael, not the default.
- `mouth_place_profile` -0.047 WARN: the mouth's absolute height matches (0.199 vs 0.202 L under the eye line; front
  and 3/4 match too); the between-ratio is off because our profile nose tip is 0.012 L lower (0.090 vs 0.078) and the
  chin 0.007 lower: head shape (the nose), not the mouth. Not moved.

**Build B** (`charkit/out/face6_b`, f55ba8e before the face5 merge; render box, boards views,body,design; CPU 1306 s):
the 27 graded flag checks 16 PASS, 7 WARN, 4 FAIL (face6_a 18/6/4 counting differently: B's lab-predicted moves all
landed: iris 3/4 1.127 WARN, closeup profile 0.936 PASS, spikes front 1.0 PASS, gaps profile 0.8 PASS, profile flick
-0.056 PASS, eye_aspect 0.944 PASS, lid_span 1.012 PASS). FAILs: brow_shape_closeup_profile 0.469,
eye_lash_spikes_closeup_profile 0, mouth_place_three_quarter 0.076, nose_mark_at_three_quarter 0.0337 (face6_a 0.021
WARN). The nose: no nose change between a and b; face6_a's 3/4 mark (4 px at 400 ppl) took a stray nose-class pixel on
the face's contour into its centroid (x -0.103), B reads the tick alone (-0.085; the design -0.114, y 0.110 vs ours
0.094). The front matches (0.0035 PASS), and the drawing's 3/4 tick is 0.016 L lower than its front tick (heights don't
move with yaw: the drawing's), and 0.03 L toward the leading side (part ours: the profile nose reach is 0.018 L short,
sheet_nose_reach). A tick offset to her right (lab knob nose.side -0.008) reads 0.0287 WARN in 3/4 but the nose's shape
IoU falls 0.478 -> 0.391 front: not taken (reverted). Expressions (paused, reported): face_preset_angry 0 PASS -> 0.039
WARN (the angry eye's eye_aspect_rel 0.954 against <= 0.95: fold_shape moves every eye variant), face_preset_effort
FAIL as before. Other moves a -> b: jaw_taper_shape 0.0401 FAIL -> 0.0399 WARN, tq_cheek_hollow 0.0049 PASS -> 0.0051
WARN (both pipeline-3d's jaw; face5 merged since), brow_arch_closeup_profile 0.01 -> 0.014 WARN.
Guard (pieces' IoU 1580f95 -> B): iris 0.847/0.762/0.677 -> 0.898/0.808/0.721; lash 0.526/0.286/0.226 -> 0.489 (-7%)
/0.26 (-9%)/0.23; brow 0.461/0.509 -> 0.818/0.469 (-8%); mouth 0.11/0.261/0.408 -> 0.465/0.461/0.624; nose 0/0 ->
0.478/0.072. None falls more than 15%.

Merged pipeline-3d 342e88c (tool/face5) at 71fab0c (cli.py: code_head's modules keep charkit.mouth and add
charkit.faceregion). Pregate on 71fab0c into 342e88c: PASS (20 value moves, 0 blocking;
charkit/out/pregate/pregate_tool-face6_71fab0cc_into_342e88c8.md).

**The nose tick sized to the design's** (spec `nose.tick` (0.0045, 0.016, -0.006) -> (0.0075, 0.022, -0.007)): the
calibration re-run on build B (dry, `charkit/out/face6r2/calib_b.log`) read nose_mark_three_quarter COARSE: our 3/4
mark's ink 0.36 of the drawn one passed the 0.35 band at margin 0.375 from the floor (needs 0.5). Lab: ink front 0.5 ->
1.0, 3/4 0.363 -> 0.817; nose IoU front 0.478 -> 0.506; nose_mark_at_three_quarter unchanged (0.034 FAIL). Every other
face_flags record re-reads calibrated on B (eye_iris_fit_profile and eye_lash_spikes_three_quarter are INFO reads,
miscalibrated as recorded). The first gate (6db6973) was stopped for this change.

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
