# Workstream B: the eye and mouth engine on the authored head (`tool/eyes-mouth`)

The eyes and mouth of the code-authored head (`spec['base'] = 'code'`), rebuilt so the head's own loops carry them, fitted
to the eyes sheet (head_turnaround), and measured per view, per expression and per key. The MakeHuman and anime bases
keep their engine: every change below is scoped to a base whose labels carry loops, or to knobs whose defaults keep the
old behaviour.

## What changed

**The eye's lid loop is authored on its outline.** The cage cut each eye as a fixed almond (0.21 x 0.13 L) in a
+-0.09 L block, and `eyes.place` dragged the margin onto the knob outline. Now:
- the lid loop is laid on the spec's own outline (`code_base.eye_outline`, `headgeom.cylinder_cage(eye_outline=)`);
- the block grows to hold it: `EYE_GAP` 0.035 L for the rings, `EYE_GAP_BELOW` 0.025 L under it.

**The lids move the head's own loops, along their spokes.** The loops ride in the eye labels (`'loops'`, index-aligned
from the block's rim to the margin). `eyes.place` and `lid_key` move them with `eyes.spokes`: each ring vertex takes its
rest share of its margin vertex's move, and nothing past the rim moves. The rings stay nested: a closing lid stretches
them and can't fold them. (Moving the margin *along* the spokes to the lid curve was tried: the spokes fan into the
eye's centre and bunch the closed lid there; worse.)

**The mouth is authored for its reach, its keys harmonic over the mesh.**
- The block holds every shape's corners and upper lip (`code_base.mouth_block`: `MOUTH_GAP` past them, 3 rings,
  `MOUTH_BELOW` 0.09 L), half a row clear of the eyes' blocks. The lip loop is the neutral mouth's own smile, opened
  `MOUTH_LENS` for its rings.
- `mouth.key` / `place` on an authored base (the mesh's faces passed in): the lips onto the shape's curves by arc length
  (`_arc_params`: a D's steep sides keep their vertices); the lower lip placed in the jaw's frame (it keeps its depth
  instead of sinking onto the rest face); the jaw's core moved whole by `jaw_follow` (0.6) of the lip's drop; skin with
  no jaw weight kept; the rings and the jaw's edge solved harmonic between them (`mouth.harmonic`: inverse edge-length
  weights, numpy, Blender has no scipy), in all three axes (re-seating on the rest face pulled the jaw's skin back).

**The eyes' shine can come from one light.** `iris.shine_mirror` False gives the right eye its own iris image with the
shine flipped, so both eyes' highlights sit on one side, as the sheet draws them (build, faceeval and bodyeval alike).
Default: mirrored, as before.

**`iris.converge`** (default 0): the irises' rest place toward the nose, in eye widths; the gaze keys add to it.

**Measurement.**
- `python -m charkit eyes BUILD [--against OTHER]` (`charkit/eyepage.py`): the design's eyes against ours in the front,
  three-quarter and profile views (`qa3d.eye_image` takes an azimuth; the sheet's background masked out of the design's
  crops), every expression of the library with its folds, the lids' openings, the mouths' cover.
- `face_mouth_cover` (new check): the worst open mouth's share of its opening that shows its inside, tongue, teeth or
  lip line (`qa3d.mouth_cover`). Skin there means the lips' rings lapped over the opening; nothing means a hole.
  PASS from 0.97, WARN from 0.90.
- `eyeqa.measure` reports the corner line's `tilt`.

**Tools.** `facefit` makes an authored head and the geom hair's cut venv-side before its Blender step, as `build` does.
It had failed on base `code`: Blender's Python has no PIL. `charkit remote gate` passes `--spec` and `--args` through.

## Numbers

(filled at the end of the workstream)

## Found, not done

- **The eye is too wide in profile.** The design's profile eye is a narrow wedge: 0.09 L wide, aspect 1.61. Ours is
  0.17 L wide, aspect 0.70. In profile, width is depth, so our outer corner sits about 0.08 L further back than the
  design's. The face's surface turns back steeply toward the eye's outer corner, and the eye follows it. That's the
  head's shape round the eyes (anime heads keep the eye region flat), not the eye engine.
- **Three-quarter irises.** The design's near-eye iris sits 0.146 of the opening toward the nose, ours 0.053. No depth
  offset reproduces both eyes. Moving the iris forward shifts both irises picture-left (near 0.071, far 0.162, the wrong
  way). Moving it back hides it behind the white. The sheet converges the irises toward the nose in every view, about
  0.1 of the opening in the front. `iris.converge` does that, and it's off: a taste call.
