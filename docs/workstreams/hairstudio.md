# Hair studio (tools/hairstudio): checkpoint I4, the idol makeover

A local, laptop-speed loop for building and judging procedural anime hair, and the hairstyle it produced: Clawd's new
long, styled, idol hair. It came out of the coordinator's session of 2026-10-02 with Michael (about 130 iterations).
**Checkpoint: style `I4`** (`tools/hairstudio/styles/I4.json`); stills and a motion contact sheet are in
`docs/hairstudio/`.

## Why a new hairstyle
69 cycles on Clawd's original short, tousled, frizzy hair never looked right. In 3D its signature (many small sharp
tips, view-dependent messiness) turns into edge-on shards and noise, and short hair barely moves. Michael's conclusion:
complex motion plus a hairstyle ill-suited to the medium was too much for a first case. Long, flowing, styled hair is
close to the native case for anime 3D. The palette is locked to the costume; everything else was open.

## What I4 is
- **Crown:** a held shell with a scalloped edge.
- **Bangs:** a fuller side-swept fringe of four or five curved flame blades, rooted at the crown's surface and held
  rigid with it in motion.
- **Ahoge:** long and expressive; a spring chain, so it bounces.
- **Back layers:** styled clumps (`styled_path`) cut to the shoulder blades. Each falls in a soft S with about 2 cm of
  air off the body (a curtain hanging from the widest point above it, not draped) and ends in a barrel curl. The
  outer layer under-curls, the inner layer flips out.
- **Face framing:** curls that flip outward at chin height.
- **Clump construction:** rolled-sheet clumps (`ribbon_side`) whose width follows the hair's surface, then the curl's
  roll axis. Each clump's path is its outer surface, and it thickens inward over a long ramp (no ledge).
- **Rendering** (the studio passes): normals leaning 0.35 on the envelope so each clump shades as its own rounded
  form; occlusion; lock-space gradients mixing toward a saturated shade; a contour pass at major depth jumps.

## Running it
- **Base:** any default build's bundle: `python -m charkit build charkit/spec/clawd.json --out charkit/out/hairbase`.
  Set `HAIRSTUDIO_BASE` to a different bundle if needed.
- **Build:** `python tools/hairstudio/groom_long.py BASE_BUNDLE OUT_BUNDLE tools/hairstudio/styles/I4.json` (2-5 s).
  `groom_long.py` is the long and idol builder; `groom42.py` and `groom3.py` are the short-hair builders, kept for
  history.
- **Views:** `python tools/hairstudio/views.py OUT_BUNDLE TAG`. Four head views, three tall views and a top-down view
  go to `tools/hairstudio/studio/` (about 30 s).
- **Motion:**

      CLIP_STYLED=1 CLIP_GRAV_LONG=0.12 CLIP_RIGID_BANGS=1 CLIP_STIFF_LONG=40,12 CLIP_HEAD_COLLIDE=1 CLIP_K=12 \
      CLIP_TALL=1 CLIP_MOVE=turn python tools/hairstudio/clip.py OUT_BUNDLE TAG --views 30,160

  This runs VRM-style spring bones (each segment follows its parent: the root leads, the tip trails), a smooth radial
  body proxy plus a head collider, inelastic contact with friction, a 1.5 s warm-up and C2 easing. About 75 s for 72
  frames on the laptop.

## Measures (each checked against a known case or Michael's judgments before use)
- **Skull fit, `crown.py`:** standoff from the skull along rays front-to-back and ear-to-ear, the largest step and the
  flattest curvature relative to the skull. Validated: a constant 2 cm offset scores about 0.85.
- **Face, `face_vis.py`:** eyes, face and forehead visible with the hair on against off, plus the hair group covering
  each hidden pixel.
- **Motion, `jitter.py`:** rest stability, and the share of tip motion energy above 6 Hz. Validated: a clean 3 Hz
  swing scores 0, a 3 mm buzz 2.7%. A 5-frame average and a cubic fit were both rejected because they counted fast,
  smooth swings as jitter.
- **Shading, `crossshade.py`:** the share of shadow lying in regions spanning 3 or more clumps (a blotch over the mass).
  It ranks the builds as the eye does. A "within-clump over between-clump" measure was rejected because it rewarded a
  blotch.
- **Also:** `form.py` (plateau, width spread, weight), `sections.py` (vertical cross-sections), `studio3d.py`
  (turntable, slices, volume, lock statistics), `isolate.py` (each group alone) and `appeal3d.py` (edge-on share and
  speckle, calibrated 6/6 and 5/6 on Michael's pairs).
- **Taste loop, `taste.py serve`:** blind keyboard A/B with stored predictions. Session 1: his picks followed
  silhouette strength.

## Lessons (also in the coordinator's memory)
- Structure first: one flow logic and a consistent overlap order. Randomness is almost always bad.
- Every measure is checked against the eye or a synthetic case before it's trusted. Several measures were rejected
  for that reason.
- Never calibrate 3D measures against the 2D drawing.
- When a direction regresses, ask a new question or build a new tool, rather than tuning further.
- Describe the result and its intent in words every few cycles (the gestalt check).

## Next
- Break I4's pleat regularity: overlapping layers, a few clumps crossing, curl sizes and timing varied by design.
- Bigger face-framing curls.
- A light pass: highlight band, rim, root-to-tip gradient.
- A choreographed hair-flip clip, and mocap clips (`projects/clawd3d/refs/mocap`, the 77-joint skeletons) retargeted
  onto the build's VRM humanoid.
- Hair colour against the costume: Michael's call.
- Port I4 into the build: a hair stage that replaces the hull-cut pieces, then the VRM export with the hair's spring
  chains.

## Mocap on the rig (2026-10-02)

`mocap.py BUILD GROOM CLIP.npz TAG [--trim N] [--face] [--measure-only]` puts a canonical SOMA-77 clip
(`projects/clawd3d/refs/{mocap,bones}/*.clip.npz`) on the build's VRM humanoid in numpy, on the laptop. It uses the
clawd3d calibration for every bone except the feet and toes, which take the source rotation as-is: Clawd's heeled boot
puts the foot bone 65° down, and aiming it along the source's 21° tipped the foot 44° toe-up. The export's skin weights
are carried onto the bundle meshes (k=8 inverse-distance blend). The groom's spring chains are driven by the head's full
transform, with a body proxy that rides the chest and the head mesh in the head's frame. The figure is grounded by the
planted ankles.

`measure()` reports hair buzz above 6 Hz, tip swing, foot slide while planted, the joint angles below the knee, the
planted ankle's height, the hands' closest approach to the hair chains and the hips' range. It runs in about 3 s.
`curtsy_page.py` builds `clips/curtsy.html`.

The first two clips are the studio curtsy (BONES-SEED; credit "Motion Data by Bones Studio") and the video curtsy
(GEM-X, trimmed by 16 frames past a ~220° settling spin, then turned to face the camera). Hair buzz is 0.1–0.2%; foot
slide is 0.24 mm/frame (studio) and 1.3 mm/frame (video). Not simulated yet: the skirt (it's skinned to the legs) and
the arms as hair colliders.
