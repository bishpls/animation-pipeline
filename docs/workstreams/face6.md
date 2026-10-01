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
