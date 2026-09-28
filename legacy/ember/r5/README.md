# EMBER III · 3D (Round 5)

This round remakes EMBER III, "KINDLE", as anime-style 3D. It is built in Blender 5.2 and finished with a 2D compositing pass. There were no API calls and no generated imagery; every frame comes from code in this folder. The score is the Round 4 synth score, re-spotted to the new choreography (`score5.py`).

## What is different this time

Rounds 2 to 4 each taught something:

- Round 2 (3D, physically grounded) had the weight right but looked like a game engine.
- Round 3 (hand-coded 2D) had the anime timing but a Flash look.
- Round 4 (a generated-cel studio) had the look but drifted from shot to shot (the wing mismatch).

Round 5 keeps one model for the whole film and makes it behave like drawn animation.

- **Cel look, no render noise.** The shader has a hard two-tone ramp driven by an art-directed light vector (N·L), a fresnel rim, and depth fog, all output as emission. That gives no shadow acne and no sampling noise, and the lighting is set per shot. Outlines are inverted-hull, and the face is a set of drawn decals (one shell per expression) swapped on the frame.
- **Timing like a key animator.** Poses are authored as keys and sampled on twos or threes, with ones for the fast beats. Every key uses constant interpolation, and the camera moves on ones. Hit-stops are real holds. Travel shots go on ones so the character doesn't judder against the pan.
- **An anime cloak, not a cloth sim.** The cloak runs on seven bone chains driven by a small verlet solver. The solver has a shape spring, air drag against the wind, and body-capsule collision. It can't crumple into the body, and it is stepped with the drawings.
- **A weapon that is a machine.** The shaft telescopes in three segments, and the blade swings on a hinge with overshoot. The fold, extend and lock each land on a click in the score.
- **One Hollow King and one set of wings,** so every shot matches. The King is split down the middle by a pair of half-masked materials.
- **Physics that is honest.** The blade tip's real 3D position decides where each wolf meets the steel. In the spin, the blade meets one wolf on the beat and the next half a turn later, on the off-beat.
- **A 2D pass on top** (`comp/`). The Blender frames carry projected meta data: contact points, the blade's continuous sweep sampled between drawings, and events. From that, the compositor draws:
  - smears from the true 3D arc
  - impact frames
  - spark and ink cels
  - muzzle flashes and light-cracks
  - memory flashes
  - the line of light
  - bloom from the emissives
  - grade, shake, letterbox and title

## Layout

| file | role |
|---|---|
| `char.py` | the heroine: body, rig, face decals, hair, clothes, cloak rig, weapon, wings, cel shaders |
| `rig.py` | pose model (IK hands and feet, FK spine), pose tracks with easing and procedural layers (sprint) |
| `cloak.py` | cloak secondary motion (verlet chains, bone damped-track) |
| `world.py` | sky, moon (eclipse in the shader), snowfield, pines, void wolves, the Hollow King |
| `sets.py` | set presets (night, dawn, crater), King placement |
| `shot.py` | shot framework: bake on twos, camera on ones, meta projection, render |
| `shots/sNN.py` | the 19 shots, each authored to the score's cue map |
| `comp/` | the 2D compositor (Node + skia-canvas, reusing Round 4's FX library and sheets) |
| `score5.py` | the score, re-spotted |
| `render_all.sh`, `assemble.sh` | render, composite and encode |
