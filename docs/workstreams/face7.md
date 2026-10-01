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

## Sweeps

- **sw1** (local, before the memory call; `charkit/out/face7/sw1`): the noop splice reproduces the base exactly. The
  head-fit rows read nothing new: code_base.head_sections' in-process cache was keyed without the style's face section
  (fixed: the key carries face_style). The skin match: worst 4.2 mm between the base's Blender skin and the evaluator's
  (some vertices; where is logged now). eyes.wrap (front view kept by construction): eye_corner_profile -0.074 -> +0.062
  (wrap 0.5) / +0.146 (1.0), close-up -0.087 -> +0.046 / +0.131, three-quarter 0.017 -> 0.072 / 0.12 (overshoots past
  ~0.25); the profile spikes 0 -> 0.75 PASS, iris 3/4 1.127 -> 1.096 PASS, close-up profile iris 0.936 -> 0.982; but the
  front spikes 1.0 -> 0.33 FAIL and face_piece_lash front 0.49 -> 0.41 (-16%): the spikes stand rigid at their root's
  depth and the skin over the lid (fading back to the face over fold_reach) came in front of them. New knob
  `eyes.wrap_reach` (L): the skin follows the wrap that far out.
- **sw2** (render box, base `charkit/out/face7_a`; decl `charkit/out/remote/face7_sw2.json`): cheek refit x4, forehead
  x4, wrap 0.15-0.3 with wrap_reach 0.07 / wrap_from 0.2, scale_smooth 0.015 / 0.035 (the jaw WARNs).
- Box build `charkit/out/face7_a` (control, 0a50c46c, render box, 1600 s wall incl. a hull miss): every face check as
  52f6324 plus the 8 new ones (face_contour_three_quarter 0.774 FAIL, brow_len_closeup_profile 0.713 FAIL,
  eye_corner_profile -0.074 FAIL, close-up profile -0.087 FAIL, front 0.022 / close-up front -0.033 / 3/4 0.017 PASS,
  brow_len_closeup_front 1.022 PASS).

- **sw2** (build box, base face7_b0; all its numbers in `charkit/out/face7/sw2/sweep.md`):
  - cheek refit (-0.12, smooth 0.03, drop_bound): face_contour_three_quarter 0.774 -> 0.911 WARN, mouth_place_three_quarter
    0.0748 -> 0.0514, mouth_place_profile -0.046 -> -0.030 PASS, nose_mark_at_three_quarter 0.0337 -> 0.0074 PASS; but the
    refit moves the mouth block's cage column (x 0.16 at the mouth row reaches the surface at 0.514 rad, was 0.574: column
    38 -> 37): another cage topology; the rows took the whole-skin path and face_piece_mouth read 0.47/0.43/0.61 ->
    0.44/0.38/0.49 (profile -20%: the guard would block with mouth_place_profile improving). sw4 checks the whole-skin
    path's fidelity (noop replaced) before trusting it.
  - forehead depth 0.045 (z 0.2, dz 0.1, peak 0.75): brow_len_closeup_profile 0.713 -> 0.959 PASS, brow_shape_closeup_profile
    0.471 -> 0.794 PASS (face_piece_brow profile 0.47 -> 0.79), but brow_arch_closeup_profile 0.013 -> -0.029 FAIL (the
    brow's middle went back nearly as far as its end) and eye_bowl 0.0248 -> 0.0274 (0.06: 0.0337 FAIL). sw5: the bump's
    peak further out (0.85-0.9), the band higher (z 0.21-0.22, dz 0.08).
  - wrap 0.2 + wrap_reach 0.07: eye_corner_profile -0.074 -> -0.026 PASS, close-up -0.087 -> -0.031 PASS, 3/4 0.017 ->
    0.036 PASS, front spikes 1.0 -> 0.833 PASS (the reach fixed sw1's 0.33), profile spikes 0 -> 0.5 WARN; with wrap_from
    0.2: profile spikes 0.75 PASS; wrap 0.3 from 0.2: corners -0.009 / -0.021 / 0.039 (3/4 at its limit). Pieces: lash 3/4
    0.24 -> 0.30, iris profile 0.72 -> 0.77, nothing down >15%.
  - scale_smooth 0.015 / 0.035 (the jaw WARNs): worse (chin_angle 2.3 / 6.8; 0.035 breaks the jaw: bend 40, tip 0.19).
    Not the lever; default kept.
- **sw3** (the override, on the refit): slide 0.02-0.05 moves the 3/4 mouth's lead only 0.42 x the slide (0.121 ->
  0.142 at 0.05; design 0.173): mouth_place_three_quarter_override 0.0425 / 0.0372 / 0.0337 / 0.0303. Suspect the skin's
  lips (the slit, read as mouth) don't move with the line in the keyed bundle; the check now records each object's move.

## State

- Coordinator (2026-10-01): the render box has 3 slots and is saturated: sweeps, QA-only builds, calibrations, gates go
  to the build box (no `--box render`); `--box render` only for builds whose boards I need. sw2 (already running on the
  render box) left to finish. Build-box sweep base: `charkit/out/face7_b0` (7e89130f, defaults = control, boards views).
  Coordinator (later): builds that need boards go to `--box render2` (32 vCPU, L4, 10 slots); `--box render` drains.

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
