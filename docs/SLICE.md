# The vertical slice: one action beat, end to end (scoped 2026-09-29, not started)

**What it is.** One choreographed action beat of Clawd, 6–10 s, taken all the way through: choreography, camera, edit,
secondary motion, the look, and the final render. It's a production test, not a rig test. It should tell us which
character details matter in motion before we polish more static checks, and prove the "physics dial" way of directing
action (below). The quality bar is the RWBY trailers (Monty Oum). The principles it follows are in the handoff's
"Production principles".

**How it relates to the dance demo** (handoff, phase 4 item 7). The dance port replays an existing clip to test the rig
and springs. The slice is new action: choreography, camera, cutting and exaggeration. The dance can run first as the
rig's motion QA.

**When it starts:** after the rig is adequate (Michael, 2026-09-29: motion after rigging). Until then this is a scope.

## Start gate: "the rig is adequate"

Each item is measured by motion QA (`tool/motion`) on the current authored body with hair pieces, over a
range-of-motion sweep and the dance clip.

| # | Item | Acceptance |
|---|---|---|
| R1 | Torso bones near upright at rest (the dance port found hips 35° back, neck 60° forward) | Each torso bone within 10° of the VRM rest. The dance port runs with no torso calibration. |
| R2 | Shoulder and hip skinning (arm through the top at dance frame 260, skirt blowing out at 200) | Skin-through-cloth and limb-through-body interpenetration under limits across the sweep. Joint volume loss under limits at the shoulder, elbow, hip and knee. |
| R3 | Spring bones in charkit, not shot-side: hair locks, overskirt flaps (separate pieces, Michael 2026-09-29), skirt ring, bow tails; colliders on the thighs, hips and skirt | Stable (bounded energy, no explosion) across the sweep at 24 and 60 fps. Flap-through-skirt and flap-through-leg under limits. |
| R4 | Foot contact | Foot sliding under limits on planted frames, and soles on the floor (the port found 9 mm below). |
| R5 | Face for the beat: the expressions the beat uses (effort, shout, focus) | They pass `expr_*`, and face folds don't rise. |
| R6 | Render path | Board batching merged (`tool/render-batch`). A clip renders as one animation, bit-identical to stills. |

## The beat (proposal; the content is Michael's call)

The default is solo and unarmed, against a practice target (a post or dummy that breaks). That avoids a second rigged
character.
1. Ready stance.
2. Run-up.
3. Anticipation crouch.
4. Launch.
5. Airborne spin: the first place for liberties (hang time).
6. Strike: an impact hold, a smear and a camera punch.
7. The target breaks.
8. Landing slide: momentum carried past the physical version.
9. Recover.
10. Pose, while the hair, flaps and skirt settle.

It runs to about 8 s over 3–5 shots.

## The physics dial (Michael's principle, 2026-09-29)

Physics is the baseline that standardises the motion. Liberties are named, deterministic parameters off it, spent where
the story needs emphasis and measured as departures. They're never tuned by feel alone.
- **The baseline:** key the beat's poses. A physics pass then makes the root consistent: centre of mass ballistic in
  flight, angular momentum conserved in the air, ground reaction on contacts. It's recorded as the physical version.
- **The dials, per beat:**
  - `gravity_scale` (hang time);
  - `time_ramp` (speed ramps);
  - `impact_hold` (frames);
  - `momentum_carry` (overshoot past the physical);
  - `anticipation_scale`;
  - `smear` and `multiples`;
  - `reach` (limb stretch within a limit);
  - camera `shake` and `punch`.
  Each dial is in the shot's spec, seeded, and renders bit-identically.
- **The liberties report, per shot:** where physics is broken, by how much (hang time against ballistic, peak height,
  unconserved momentum Δp, stretch), and which dial did it. The review page overlays a ghost of the physical version on
  the final motion, so each liberty can be seen and sized.

## Design for the shot

- **QA from the shot's cameras:** a silhouette-clarity score per key pose (limb separation, negative space), whether
  the face and hands are visible, and the character checks weighted by what each camera sees.
- **Per-shot and per-frame overrides** layered over the character without changing it: pose offsets, line thickness,
  piece visibility, shape keys and light. Monty designed for the angle; Guilty Gear Xrd tweaked the model per camera.
  The overrides are logged like the dials.

## Edit alongside animation

- The shot list lives in code: beats, cameras and durations. An animatic comes from low-resolution batched renders
  within minutes of a change. Timing is iterated in the cut.
- **Shoot wide, cut tight:** render variants in bulk (dial sweeps, alternative takes; cheap with batching and the
  render box), then pick. A contact-sheet page shows takes side by side with their dials and numbers.

## The impression of movement: primitives, each with a measurement

- **Holds and stepped keys:** limited animation per section (on 2s or 3s where it reads better). Spacing charts check it.
- **Smears:** mesh stretched along velocity, with its amount keyed to speed. Measured as stretch against a limit.
- **Multiples, speed lines, impact frames:** a flash or silhouette frame, as 2D overlays composited over the render.
- **Camera:** shake, punch-in zoom and whip pans, all tied to the beat's events.
- **Secondary motion reviewed as motion:** springs' overshoot and settle times per piece, with the flaps looser than the
  skirt.

## Phases

| Phase | Work | Output |
|---|---|---|
| S0 | The start gate (R1–R6): the body, motion and render-batch workstreams | the gate's numbers |
| S1 | Choreography and the physics baseline: keyed poses, the physics pass, foot contacts | the physical version, with motion QA numbers |
| S2 | Cameras and cutting: the shot list, cameras, animatic | an animatic page (under 5 min from change to cut) |
| S3 | The dials: liberties per beat, the report, ghost overlays | the liberties report |
| S4 | The impression of movement: holds, smears, impact frames, camera | primitives with measurements |
| S5 | Secondary motion: springs and flaps in motion, collisions | motion QA on the beat |
| S6 | The final render, then Michael's review | the clip, and a review page with everything above side by side |

## Options and costs

- **Base motion:** hand-keyed poses with the physics pass by default. Optionally, Kimodo (NVIDIA; Apache-2.0 code,
  non-SMPL weights cleared for commercial use; fits on the L4) for base actions from text and keyframes, in the way
  Monty cleaned up mocap. Evaluate it in S1. Its licence needs a check at that point.
- **Money:** no paid calls. Renders go on the boxes.

## Michael's calls, when the slice starts

1. The beat's content: solo against a target (the default), or an opponent (a second character: much more work).
   Unarmed, or a prop or weapon?
2. Frame rate, and limited animation (stepped sections) or full.
3. Sound: its own synth score (as EMBER did) or silent for review.
