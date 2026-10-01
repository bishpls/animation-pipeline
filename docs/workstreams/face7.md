# Workstream: the face's base shape, round 3 (`tool/face7`)

Worktree `~/animation-pipeline-face7` (sparse), branch `tool/face7` from pipeline-3d 00494de (base build: the preview
`~/animation-pipeline-3d/charkit/out/previews/52f6324`, the same code). Only the default expression: presets, eye/brow
variants and visemes stay paused (Michael).

Michael's four approved items (2026-10-01; face6's findings, `docs/workstreams/face6.md`):
1. **Three-quarter mouth:** rigid placement stays the default; the drawn placement a per-shot override (a camera-angle
   driver or a per-shot setting, off by default). About 0.025 L of the 0.075 L miss is the drawing's own.
2. **Lower-face width at mouth height:** the 3/4 far contour 0.515 of the front half-width against the design's 0.656
   (0.04 L ours): carry the cheek forward at mouth height, holding front and profile.
3. **Forehead at brow height:** the profile brow 0.097 L deep against 0.136 (our forehead flatter there): round it.
4. **The profile eye:** its far corner below the opening's middle (the design's above): an eye-shape fix.
Also the jaw's three honest WARNs if the head-fit work reaches them: chin_angle 1.5, chin_v 0.09, jaw_taper_shape 0.0157.

## Measurements first (52f6324)

**Item 2 is the head fit's cheek term** (`charkit/out/face7/an/cheek.py`): the per-row fit asks -0.033..-0.040 L at
the mouth rows (z -0.16..-0.24), but the term is smoothed over 0.08 L sigma (`assemble(smooth_terms=0.08)`, 20 rows
of 0.004) and one clamped row under the chin (+0.12, the bisection's bound) drags the lower rows up: smoothed -0.019..
-0.024. The sections' 3/4 contour sits 0.018-0.022 L behind the design's over z -0.17..-0.29 (`an/lead3.py`).

**Item 4 is ours in part** (`an/corner.py`: the opening's outer corner height as a share of the opening from its
bottom, per read). Ours 0.41 in every view (orthographic: the corner's z is one 3D point). Design: turnaround front
L 0.456 / R 0.412 (mean 0.434), close-up front 0.521 / 0.436 (mean 0.479), profile 0.539, close-up profile 0.548,
3/4 near 0.455 / far 0.57. The drawing raises the corner ~0.08-0.1 of the opening in profile over its front: no rigid
eye with the corner as its backmost point does that; one whose upper lid's outer part wraps back further than the
corner does (in profile the backmost point climbs the upper lid). New knob `eyes.wrap` (+ `wrap_from`), front view
unchanged by construction.

## Tooling

- `charkit sweep --stage face` (sweep.FaceStage): the head (cli.code_head) and the features (character.assemble, as
  faceeval) rebuilt in the venv per row, the base skin's variants moved by the row's head (matched to the evaluator's
  subdivided skin by position), features replaced; `style.face.KEY` rows run the head uncached. Fixed sweep.base_spec's
  remake of a preview's head/body codes (`getattr(cli, 'head_code')` -> cli.code_head).
- `headfit.LAST`: the last assemble()'s per-row cheek fit (raw, smoothed, the contour), for labs.

## State

- WIP commit 0a50c46c (defaults unchanged: every new knob off). Coordinator (2026-10-01): the laptop's memory is
  critical: no new local heavy jobs; sweeps, builds, labs on the boxes (`charkit sweep --box`, `remote run|build`).
  Sweep declarations for the box go in `charkit/out/remote/*.json` (synced; the rest of charkit/out isn't).
- Running: local sweep `charkit/out/face7/sw1` (started before the memory call; decl `charkit/out/face7/decl/sw1.json`:
  noop, cheek refit x3, forehead x2, eyes.wrap x3, dropbound); box build `charkit/out/face7_a` (render box, boards
  views,body,design; the control: 0a50c46c with defaults = 52f6324 + the new checks), log charkit/out/face7/build_a.log.
- Calibration (dry, on face7_before = 52f6324 stored): face_contour_three_quarter calibrated (design 0.958-1.036,
  known-bad 0.774 FAIL); brow_len_closeup_profile calibrated (design 1.0-1.008, known-bad 0.713); brow_len_closeup_front
  guard; eye_corner_closeup_profile calibrated (design 0.004-0.01, known-bad -0.087), eye_corner_profile known-bad
  -0.074 (FAIL with the corner limits (0.04, 0.06): thirds of the gap design 0.025 -> known-bad 0.074); front, close-up
  front and 3/4 corners guards. The corner read averages the outermost 5-15% of the opening's columns (one 4% window read
  0.047 off with the design moved a pixel). Records not written yet (write after the build: `calibrate ... --build`).
