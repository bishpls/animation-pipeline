# XPBD cloth and spring solver (tool/xpbd)

The roadmap's "To hand-roll" item 1 and "Changes, ranked" item 3's solver; "Missing from a production rig" items 2-3
(spring colliders; the skirt's penetration during a kick). A pilot behind a setting: templates stay the default, no
default changes, and the measurement decides.

**Branch** `tool/xpbd` in `~/animation-pipeline-xpbd` (sparse charkit worktree), from pipeline-3d 2f42155.

## Plan
1. The solver, `charkit/sim/`: XPBD in numpy (numba only where it pays). Distance (stretch), bending, pins and
   attachments, body collision (capsules from the skeleton, and an SDF of the posed body) with friction; fixed timestep,
   substeps, deterministic. Settings from the style profile's `physics` section; the departures from physics are named
   dials (gravity scale, damping, hang, stiffness per region). Tests: convergence, bit-identical re-runs, energy on a
   hanging cloth, penetration-free rest on a sphere and a capsule.
2. Rest-drape pilot: the flaps (and the skirt) settled under gravity with body collision from the built rest pose,
   against the template on skirtqa's flap and skirt checks, the pieces' shape IoU in all views, the hems.
3. Motion pilot: at motion QA's extreme poses (the kick first), the skirt's and flaps' body penetration and shape, the
   current rig (skinned skirt, flaps on the hips, the outfit graph's spring chains as VRM springs) against XPBD cloth.
4. Report: what making it the default for loose garments would take; tuning VRM spring chains (stiffness, colliders)
   from simulation.

## The solver (charkit/sim)
- `xpbd.py`: XPBD in numpy with numba kernels, single-threaded in a fixed order (bit-identical re-runs). Constraints:
  distance (every triangle edge), dihedral bending (gradients checked against finite differences to 1e-10), hold
  (each vertex toward a target: the template carried by the rig; the anime dial), long-range tethers to the pins
  (Kim et al. 2012), a one-way and a two-way layer (a flap kept outside the skirt), tapered capsules and signed-distance
  grids (static or carried rigidly; Newton-refined projection) with position-based static and kinetic friction.
  Substeps, and iterations that accumulate the multipliers (a rest drape converges to the equilibrium). Constraints
  are ordered outward from the pins. Self-collision isn't handled.
- `settings.py`: the style profile's `physics` section (anime.json and realistic.json unchanged) mapped to the solver.
  Bending stiffness is a textile bending length c = cloth_stiffness x 0.5 L, flexural rigidity rho g c^3. **Calibrated
  by measurement**: Peirce's cantilever (overhang 2c droops 42.9 deg, ASTM D1388) with the discrete hinge constant
  BEND_K 0.5 droops 42.8 deg at h 0.08 c and 43.8 at 0.053 c (BEND_K 1: 26 deg, 1/3: 53). Dials: gravity scale, hold
  (a spring under which a vertex sags (1-h)/h x 0.1 L), damping, hang (gravity scaled while rising), friction,
  stiffness per region, substeps, iterations, tethers.
- `cage.py`: a simulation cage for grid-built garments (production cloth's way: simulate a clean mesh, carry the render
  mesh). **Measured need**: the flap template's edges run 0.002-0.12 L (the stair's rows and columns); simulated
  directly, 2 substeps x 200 iterations blew up (stretch x3000) and 20 x 50 left 22% strain on slivers. The cage keeps
  grid lines at least `spacing` apart (the flap 37 x 28 -> 33 x 14 at 0.03 L), carries every template vertex
  bilinearly plus its rest residual in the block's frame: exact at rest (0.0), rigid-invariant (4e-16).
- **XPBD's effective stiffness has a discretisation floor** (measured on the cantilever at 40 substeps, one pass: h
  0.02 -> 28 deg, 0.01 -> 43, 0.005 -> 74): with one pass per substep the constraint adds a compliance ~ h_sub^2 /
  (rho h_mesh^4), so finer meshes read softer. Remedies used: the cage (coarser, even spacing), and for statics many
  multiplier-accumulating iterations.
- Tests `charkit/tests/test_sim.py` (13, ~25 s): gradients; a hanging strip converges (residual stretch 2.5e-3 ->
  1.7e-4 -> 1.1e-5 at 5/20/80 substeps, hangs its length to 2e-3); bit-identical re-runs with moving capsules and
  friction; energy on a hanging cloth (never above its start: worst -2e-4 m g h at 40 substeps; comes to rest with
  damping); penetration-free rest on a sphere, a capsule and an SDF grid (>= -1e-6 m against the grid's own field:
  friction's tangent move after the projection); static friction holds on a 25 deg slope, none slides; Peirce's
  cantilever within 2 deg; the style dials (anime stiffer and holding; the hold's sag as defined); tethers; the cage.
- `rig.py`: venv posing from the build's joints and motion QA's poses. **Checked against Blender's Armature**
  (evalmesh.motion_main) on the skirt, a flap and the shorts at all 7 poses: <= 1.1e-5 L. Capsules fitted to the skin.
- `springbone.py`: VRMC_springBone chains as the VRM 1.0 spec runs them (verlet tail, drag, stiffness toward the rest
  direction, gravity, length, sphere/capsule colliders by hit radius).

## The harness (charkit/sim/drape.py)
A settled coarse mesh goes through the build's own finalize (Solidify, Subdivision) into a copy of the bundle (the
bundle's evaluated garments equal finalize(coarse) vertex for vertex, 7e-7 L), and the build's own QA parts run on it
(skirt, sheet_pieces, sheet_body, poke: 161 checks). **Calibrated**: on the unmodified bundle it reproduces the box's
qa.json on 160 of 161 checks (body_front_arms -2.0 vs -2.1, ARM against x86, not garments); a round trip of the flaps
through finalize changes none. Colliders: signed-distance grids (0.01 L) of the skin (base, closed), the skirt and the
shorts (closed shells). Each vertex's collision radius is capped at its rest clearance (the right flap's tucked top sits
0.0015 L inside the skirt's pleats, which aren't mirror-symmetric: pushed out against its pinned rows it strained 107%).

## Log
- 2026-09-30: started; a baseline box build of 2f42155 (`charkit/out/xpbd/base`) for the products the pilots read;
  the produced refs (outfit masks, hull) fetched from the box for the local QA.
- The opt-in hook (f6bac5b): `geomstage.garments_product` calls `charkit.sim.hook.apply` only when a garment's spec has
  a `drape` dict; `drape: {"solver": "xpbd", ...}` settles that garment's coarse vertices before finalize (style, rest
  'template' or 'pattern', colliders, seconds, dials). No spec sets it: no build changes. charkit/sim is imported only
  then (not in a default build's closure); geomstage.py is the one shared file touched. Test:
  test_sim.test_the_hook_is_off_unless_asked (the product's digest unchanged without it; settled onto a sphere with).
- Merged pipeline-3d 8b5ecae (collar3 M2: the eye-line frame and the flap tails refit; softras) at 4d2ccc2: clean;
  test_sim and test_geomstage ok. Launched: the gate (policy K, once, for the hook) and a base build of the merged tree
  (`charkit/out/xpbd/base2`) for the pilots' final numbers (the first rest pilot ran on 2f42155's build).
- **Gate PASS under K** (5a33f4d into pipeline-3d 8b5ecae; `charkit/out/gate/gate_tool-xpbd_5a33f4d_into_8b5ecae.md`):
  nothing blocks, 0 items, no check changed; 71 test files ok; the candidate rebuilt (geomstage.py is read by the build),
  build CPU 591.4 -> 643.6 s (1.09x).
- Motion pilot, first run (kick, on 2f42155's build): the shipped garments have 0.7% (skirt) and 1.5% (flaps) of their
  surface vertices inside the skin at rest (their tops tucked under the band), so penetration is counted as new against
  that baseline. The pelvis capsule fitted badly (0.24 L at p90) and is left out (legs only: p90 0.058 L). **The
  skinned skirt's kick is a stretch failure, not a skin one**: 0 new vertices inside, but its coarse edges stretch 197%
  at p99 (535% max): the front panel is skinned to the lifted thigh. The skirt's grid is a ring: the cage now keeps it
  closed (a first run split it at the back seam, 8x there).
- Base build of the merged tree `charkit/out/xpbd/base2` (4d2ccc2 + notes); the harness reproduces its QA (160 of 161,
  the arms' known 0.1; the flaps' finalize round trip moves flap_profile_iou_R by 1e-4).

## Results (the merged tree's build `charkit/out/xpbd/base2`; review page `charkit/out/xpbd/review/index.html`)

### Rest drape (`charkit/out/xpbd/rest_final/rest.md`): templates win; physics hangs the flaps onto the legs
Both flaps settled on their cages (5 s, 60 fps, 10 substeps x 10 iterations; settle speed <= 1e-3 L/s except the
realistic variants' 0.03-0.04), spliced through finalize, the build's QA on it (161 checks):

| variant | PASS / WARN / FAIL | piece L / R | flap back IoU L / R | profile IoU L | profile clear L | hems front / back / 3q mid |
|---|---|---|---|---|---|---|
| template (the build) | 104 / 17 / 14 | 0.693 / 0.815 | 0.863 / 0.835 | 0.710 | 0.005 PASS | 0.038 / 0.028 / 0.024 |
| anime (hold 0.8) | 102 / 19 / 14 | 0.701 / 0.815 | 0.881 / 0.855 | 0.730 | 0.014 PASS | 0.028 / 0.014 / 0.024 |
| stiff_pattern (flat pattern, bending length 0.75 L, no hold) | 99 / 19 / 17 | 0.666 / 0.780 | 0.878 / 0.851 | 0.663 WARN | 0.068 PASS | 0 / -0.009 / 0.024 |
| stiff (template rest, 0.75 L, no hold) | 84 / 27 / 24 | 0.566 / 0.652 | 0.776 / 0.767 | 0.508 | 0.212 WARN | -0.052 / -0.066 / -0.297 FAIL |
| realistic (hold 0.1, 0.15 L) | 84 / 29 / 22 | 0.570 / 0.656 | 0.768 / 0.766 | 0.509 | 0.202 WARN | -0.066 / -0.075 / -0.306 FAIL |
| physics (hold 0, 0.35 L) | 84 / 21 / 30 | 0.538 / 0.618 | 0.727 / 0.728 | 0.456 FAIL | 0.297 FAIL | -0.075 / -0.089 / -0.311 FAIL |
| pattern (flat, 0.35 L) / pattern_soft | 85/26/24, 82/23/30 | 0.563 / 0.653 | 0.761 / 0.755 | 0.500 | 0.238 WARN | similar |

- Physics as the baseline (no hold) drops about 20 checks from PASS: the drawn flaps stand out from the legs (the
  design's stylisation); under gravity their tails swing to plumb (moved 0.3-0.4 L), onto the back of the legs
  (flap_profile_clear 0.005 -> 0.30 FAIL, sweep -0.29 FAIL) and the hem mid drops (three-quarter 0.024 -> -0.31 FAIL).
- anime (the profile's hold 0.8) is the template with a 0.025 L sag by construction (hold's meaning): 102/19/14 against
  104/17/14; the flaps' back and profile IoUs rise 0.017-0.020 (the tails sag toward the drawing), front IoU and two
  hems move a little the other way. Not a replacement, a near-identity.
- The most interesting variant: **stiff_pattern** (a flat pattern with the template's lengths, bending length 0.75 L,
  no hold) lands 99/19/17 and matches the template's back IoUs (0.878 / 0.851) and hems with no hand-fitted drape
  knobs (droop, out, twist): physics plus one stiffness dial gets within 5 PASS of the fit. It loses on the profile
  (IoU 0.663 WARN) and the pieces (0.666 / 0.780).
- Nothing beats the template on the whole set. Recommendation: templates stay the default for the flaps; the pattern
  route is worth a fitted stiffness per region (the dial exists: `regions`) before calling it.

### Motion (`charkit/out/xpbd/motion_final/motion.md`): the kick's failure is stretch, and the cloth fixes it
Methods: skinned (as shipped), springs (the outfit graph's chains as VRMC_springBone runs them, no colliders: none are
fitted yet), springs_col (with capsules fitted to the skin), xpbd_anime (hold 0.8 toward the skinned template),
xpbd_hips (hold 0.8 toward the drawn shape carried by the pelvis: the legs push the skirt), xpbd_physics (no hold).
New penetration: the garment's surface vertices inside the posed skin that weren't at rest as shipped (share, deepest
L); stretch: the coarse mesh's edges (p99 / max).

| pose | skinned skirt | springs skirt | springs_col skirt | xpbd_anime skirt | xpbd_hips skirt | xpbd_physics skirt |
|---|---|---|---|---|---|---|
| kick: new inside, depth | 0.001, 0.007 | 0.279, 0.141 | 0.113, 0.089 | 0.008, 0.039 | 0.002, 0.008 | 0.000, 0.000 |
| kick: stretch p99 / max | **1.99 / 5.35** | 0.62 / 0.75 | 0.73 / 0.92 | 0.11 / 0.22 | 0.10 / 0.26 | 0.06 / 0.22 |
| squat: new inside, depth | 0.058, 0.185 | 0.372, 0.187 | 0.179, 0.187 | 0.103, 0.185 | 0.047, 0.185 | 0.036, 0.185 |
| split: new inside, depth | 0.011, 0.163 | 0.211, 0.080 | 0.069, 0.114 | 0 | 0 | 0 |
| split: stretch p99 / max | 1.68 / 2.07 | 0.62 / 0.75 | 0.66 / 0.82 | 0.15 / 0.20 | 0.15 / 0.20 | 0.15 / 0.20 |

- **The kick**: the shipped skirt barely enters the skin (0.1%) because it is skinned to the thigh, and pays for it
  in stretch: 199% at p99, 535% at worst (the front panel dragged up with the leg; the pictures show it ballooning).
  The XPBD cloth holds stretch to 10-11% p99 with 0-0.8% new penetration; xpbd_hips (the drawn shape carried by the
  pelvis, the legs pushing it) is the best balance: 0.2% at 0.008 L, stretch 10% p99, departs 0.15 L from the skinned.
- **The flaps** ride the hips as shipped: no penetration at any pose (the kick's legs don't reach them). On the graph's
  spring chains the right flap goes 13.6% into the right leg at the kick (0.146 L; 10% with colliders).
- **The graph's spring chains don't hold the design at rest**: stiffness 0.29 against gravity 0.3 lets the skirt's
  ring sag 0.34 L off the template and 23% into the legs before any motion (9% with fitted capsules); the flaps sag
  0.45 L. Spring chains as exported would need tuning before they ship (next round's first step, below).
- **The squat isn't solved by anything**: every method has 3.6-10% of the skirt 0.185 L inside (the same region):
  with the thighs raised 100 deg and the spine bent, the skirt meets the belly and pelvis, which have no collider (the
  one-capsule pelvis fitted at 0.24 L p90 and was left out). A pelvis collider (two or three spheres, or an SDF carried
  by the hips) is the fix to try.
- The split: the skinned skirt stretches 168% p99 and goes 1.1% in at 0.163 L; every XPBD variant 0.

### Costs
Rest drape: 30-40 s a flap on the laptop (5 s simulated), the collider grid 15 s a mesh at 0.01 L. Motion: about 55 s
per method per pose for the skirt and both flaps (2,238 cage vertices, 20 substeps x 2 iterations, 96 frames), most of
it the three finalizes a frame. Not yet tried on the GPU (upstream Warp would be the route if it's needed).

## What making it the default would take
For loose garments (the skirt, and the flaps in motion):
1. **Motion first, rest second.** At rest the templates win; in motion the shipped skinning stretches the skirt 2-5x at
   the kick and split. A baked or runtime cloth pass on the skirt (xpbd_hips: hold the drawn shape on the pelvis, the
   legs push it) is the change that pays. Rest stays the template.
2. **A pelvis/belly collider** (the squat's 0.185 L is shared by every method), then a collider QA: the fitted capsules'
   error per bone (legs p90 0.033-0.058 L now) and penetration per pose as checks, calibrated (0 on the rest pose).
3. **Where the motion lives**: VRM has no cloth. Either bake per-clip vertex caches (glTF morph targets or a
   per-frame cache for our own renderer), or ship spring chains tuned against the cloth (step 4) and keep XPBD as the
   reference that tunes them. The second fits VRM and three-vrm; the first fits our renderer and offline shots.
4. **Gate checks for motion**: motion QA grows the new-penetration and stretch measures above (per garment, per pose),
   so a change to the skirt or its rig is gated on them.
5. Before the rest drape could be a default: a stiffness per region fitted like the templates (the stiff_pattern
   variant is within 5 PASS without any fitting), and the three-quarter flap disagreement (Michael's call A) left out
   of the objective as the template fit does.

For VRM spring chains: the colliders are ready to export (uniform-radius capsules, two per leg bone, fitted to the
skin); the chains' settings need the tuning below. The rig stage still has to build the flap and skirt chain bones
and weights (the flaps ride the hips today).

## Next round (a fresh agent; the coordinator's call)
1. **Tune the spring chains against the cloth** (code ready, not run: `python -m charkit.sim tune BUILD --pose kick`,
   `motion.tune_springs`): the reference XPBD run (anime, hold toward the pelvis) records every frame's carried
   template; each chain joint follows the template point it starts on; per piece a grid of (stiffness, gravity, drag)
   runs the chains with the fitted capsules, scored by the joints' mean distance from the reference (L) over the
   motion, at rest and at the end. Then write the best settings next to the graph's (stiffness 0.29 / 0.22, gravity
   0.3 / 0.2, drag 0.76 / 0.4) with the kick's and squat's penetration, and the VRM capsule colliders.
2. A pelvis collider and the squat rerun.
3. The motion checks into motion QA (calibrated), then decide the default for the skirt in motion.

## Checkpoint (2026-09-30, final for this round)
Branch `tool/xpbd` (see the report for the head). Gate PASS under K at 5a33f4d (the hook); the commits after it touch
only `charkit/sim/*`, `charkit/tests/test_sim.py` and these notes: `charkit/sim` isn't read by a default build (imported
only when a garment opts in), so no new gate. Outputs (gitignored): `charkit/out/xpbd/{base,base2}` (box builds),
`rest_final/`, `motion_final/`, `review/` (the page), `gate/`. Commands: `python -m charkit.sim rest|motion|tune|review`.
Tests: `charkit/tests/test_sim.py` (14).

## Round 2 (2026-09-30, late): the squat, motion checks, style defaults, the bake, the spring tuning

Brief (Michael's decisions 2026-09-30): the anime skirt moves as XPBD cloth held toward the drawn shape carried by the
pelvis (`xpbd_hips`, hold 0.8, a named liberty); realistic has no hold (`xpbd_physics`, hold 0); ship both: bake cloth
caches for rendered shots, and tune the VRM spring chains against the cloth for real-time; templates stay the rest shape.
Merged pipeline-3d 004efc3 (tool/calib: records required for new checks) at the start.

### 1. The squat: the pins, not a collider (measured)
- Where the squat's shared 0.185 L sat (`charkit/out/xpbd/r2/diag_squat*.py`): the skirt's top front (rest height 0.96-1.15
  of its 1.17 L, azimuth +-55 deg), nearest skin bone `spine`. The spine bends 25 deg and the belly comes down over the
  waist, while the skirt's pinned top rows follow the skirt's own weights (100% hips). The waistband (skinned, 100% hips)
  goes 30.6% of its surface 0.265 L into the skin at the squat too: the waist garments don't bend with the body. The skin
  itself folds 7.2% into itself at the squat (hips, upper legs: LBS).
- Pelvis and belly capsules (`rig.fit_torso`: per bone three slabs, each a left-right capsule fitted by least squares):
  p90 0.022 / 0.014 / 0.015 L (hips), 0.005 / 0.008 / 0.010 (spine), against round 1's one capsule's 0.24 L. **They change
  nothing measured**: squat worst new-inside 0.049 at 0.185 L with or without them.
- **The pins carried by the skin** (`rig.transfer_weights`: each pinned cage vertex takes the skin's weights at its nearest
  point, as production rigs transfer the body's weights to cloth): squat skirt worst new-inside 0.049 / 0.185 L ->
  0.006 / 0.014 L (end 0.001 / 0.004), stretch p99 0.19 -> 0.10; kick 0.002 / 0.031 L, stretch 0.06. With the torso
  capsules too: identical numbers, 40% slower (67 s against 48 s a pose). Default `motion.CLOTH = dict(colliders='legs',
  pins='body')`; `colliders='body'` adds the torso capsules (kept for VRM export and the spring chains).
- For the rig's owner: the waistband needs the same (the body's weights near the waist), else at the squat it sits 0.265 L
  inside the belly.

### 2. Motion checks (charkit/sim/motionqa.py, QA part `motion`, order 2500)
`motion_{kick,squat}_skirt_inside` (worst share of the skirt's surface newly inside the posed skin) and
`motion_{kick,squat}_skirt_stretch` (worst coarse edge stretch p99), moved as the style says (physics.garment_motion);
limits inside 0.01 / 0.03, stretch 0.25 / 0.5. The panels' numbers in the table, not graded. On base2 (local): 0.0024,
0.064, 0.0061, 0.104, all PASS; 95 s wall, 91 s CPU (the added build CPU). Calibration adapter charkit/calib/motion.py
(defect detectors, shape guard piece_skirt): design = the held solve with one nuisance nudged per move (substeps 16/24,
ramp 0.35/0.45 s, 3 iterations, colliders +0.005 L, hold +-0.05); known-bads computed from the same build:
motion_skinned (stretch at both poses, inside at the squat), motion_pelvis_rigid (inside at the kick: the skinned skirt
enters the skin only 0.1% there because it stretches instead). Records: not yet run (on the r2 box build).

### 3. Style profiles
anime.json physics.garment_motion {method xpbd_hips, hold_shape 0.8, loose [skirt, panel]}; realistic.json
{xpbd_physics, 0.0, [skirt, panel]}. The code reads the method from the profile (a spec's physics.garment_motion over it);
a profile without it gets 'skinned'. test_sim.test_garment_motion_comes_from_the_style_profile.

### 4. The bake (charkit/sim/bake.py; `python -m charkit.sim bake BUILD --clip kick --pc2 --replay`)
BUILD/cloth/CLIP/: cloth.json (clip, method and settings, colliders, pieces, bundle digest, commit, measures every 6
frames), coarse.npz (per piece (frames, coarse vertices, 3) float32, and the skeleton's per-frame matrices), PIECE.pc2
(Blender's Mesh Cache modifier, first in the stack, its Armature off; Blender's own Solidify and Subdivision make the render
mesh). The replay check (Blender against our finalize, L) writes replay.json.

### 4b. The bake pilot (base2, the kick: `charkit/out/xpbd/r2/bake_base2_kick`)
120 frames (60 settle pre-roll, 24 ramp, 36 held) in 54.7 s on the laptop; coarse.npz 6.0 MB (compressed, bones
included), skirt.pc2 3.9 MB, each flap's 1.5 MB. Measured as baked (last frame): skirt 0.2% new inside at 0.008 L,
stretch p99 6%; flaps 0, 0.3%. Digest 4dad66820b868a35. **The Blender replay (Mesh Cache against our finalize) has not
run yet** (`python -m charkit.sim bake BUILD --clip kick --pc2 --replay`, local Blender 5.2: the object names, the
stack order and the PC2 frame mapping are unverified until it does).

### 5. The spring chains tuned to the cloth (base2, kick + squat, `charkit/out/xpbd/r2/tune_base2/tune.md`)
Reference xpbd_hips (round 2: pins on the skin); chains against the body capsules (legs, pelvis, belly; shrunk to clear
the chains' rest joints). Joint error (mean L from the cloth's points, over the motion / settled at rest):
| piece | graph (stiffness, gravity, drag) | error | tuned | error |
|---|---|---|---|---|
| skirt | 0.29, 0.3, 0.76 | 0.334 / 0.324 | 8.0, 0.05, 0.3 | 0.070 / 0.015 |
| flap L / R | 0.22, 0.2, 0.4 | 0.587 / 0.549, 0.580 / 0.549 | 8.0, 0.05, 0.7 | 0.050 / 0.020 |
Garments on the chains, as motion QA measures them (worst new inside share, depth L, stretch p99):
skirt kick 0.042 / 0.184 / 0.72 -> 0.013 / 0.168 / 0.02; squat 0.098 / 0.195 / 0.78 -> 0.063 / 0.185 / 0.11; flap R kick
0.100 / 0.142 / 0.84 -> 0.001 / 0 / 0; at rest the flaps 1.1% -> 0-0.1%. Two limits of the tuned chains: stiffness 8 is
the grid's edge (widen it); the skirt's chains still put 6.3% inside at 0.185 L at the squat: their roots ride the hips,
the waist problem item 1 fixed for the cloth (root the chains' top joints on the skin's weights, or on a spine-blended
bone, before shipping them).

### Motion QA's CPU (about 91 s a build when its inputs change)
Where it goes (laptop profile, charkit/out/xpbd/r2/prof.py): the XPBD step is nearly all of it: about 0.26-0.4 s a frame
(20 substeps x 2 iterations on 2,220 cage vertices, numba, one thread) x 96 frames a pose, and 60 of those 96 are the
1 s settle at rest, run once per pose; measuring (posing the 75k-vertex skin, its BVH, winding numbers) is about 0.2 s x 11
measured frames a pose, about 2.5 s; the finalizes about 1 s a pose (only the measured frames: motion._Finals); the scene
about 1.5 s. It is a cached QA part (cache.qa_part keyed on the bundle arrays, garments.npz, the style file and its code),
so a build pays it only when the skirt, the body, the style or charkit/sim changed. To shrink it, in order of payoff:
(1) settle once and start both poses from the settled state (the settle is identical: -60 frames of 192, about 30%);
(2) a shorter settle (0.5 s: with hold 0.8 the cloth starts at the template and sags 0.025 L; measure its drift first);
(3) fewer substeps (15; the calibration's 16-substep nudge says whether the checks hold). Measuring only near the worst
frames saves little (measuring is under 5%). (1)+(2) together should roughly halve it.

### The box build of 5ad798e (`charkit/out/xpbd/r2/build`, the merged tree with the motion QA part)
motion_kick_skirt_inside 0.0024 PASS (depth 0.031 L), motion_kick_skirt_stretch 0.064 PASS (max 0.27),
motion_squat_skirt_inside 0.0060 PASS (0.014 L), motion_squat_skirt_stretch 0.104 PASS (max 0.33): within 1e-4 of
base2's local run. The part took 117.5 s wall, 119.9 s CPU on the box (91 s on the laptop); the build 1157 s CPU, 650 s
wall (base2, 4d2ccc2: 885 s, not comparable: other merges and cache states; the gate measures the ratio). Piece IoUs
unchanged (piece_skirt 0.893, flaps 0.693 / 0.815). QA 310 PASS / 43 WARN / 41 FAIL / 142 INFO / 2 SKIPPED (not
motion's); the FAILs that base2 didn't have are the merges' (collar_back_iou regraded by tool/calib, acc_* new from
tool/accessories2 and acc-reclass), none of this branch's.

### Exact next steps (a fresh agent; Michael's decisions above stand)
1. Calibration records (the gate requires them for the four new checks): `python -m charkit calibrate
   motion_kick_skirt_inside,motion_kick_skirt_stretch,motion_squat_skirt_inside,motion_squat_skirt_stretch --build
   charkit/out/xpbd/r2/build` (laptop, background, about 16 min: the current run, 2 computed known-bads, 8 nudged
   design runs; charkit/calib/motion.py). If a nudge reads WARN (the squat's inside sits at 0.006 against 0.01 at
   frame 24, mid-ramp: the 0.35 s ramp is the likeliest), report it rather than loosen; limits come from the records.
   Commit the records (charkit/calib/records/motion_*.json).
2. Shrink the part's CPU before the gate if the coordinator wants (above: settle once for both poses, then a 0.5 s
   settle; re-read the four checks after, the change is a remeasure only if their numbers move).
3. The Blender replay of the kick bake: `python -m charkit.sim bake charkit/out/xpbd/r2/build --clip kick --pc2
   --replay` (local Blender; writes replay.json, max |d| in L per frame). Fix the object names, the stack order or the
   PC2 frame mapping if it disagrees.
4. The final motion run for the page, on the r2 build: `python -m charkit.sim motion charkit/out/xpbd/r2/build --out
   charkit/out/xpbd/r2/motion --poses kick,squat --methods skinned,xpbd_hips_r1,xpbd_hips,xpbd_physics,springs_body,
   springs_tuned,pelvis_rigid --tuned charkit/out/xpbd/r2/tune_base2/tune.json`; then `review.page2(build, motion_dir,
   out, tune_dir, cache, rec_text, ask)` -> charkit/out/xpbd/r2/review/index.html (summary box drafted below).
5. Spring chains: widen the grid past stiffness 8; root the skirt chains' top joints on the skin's weights (the squat's
   6.3% at 0.185 L); then write the tuned settings beside the graph's (Michael's call A/B).
6. Pregate, then `python -m charkit remote gate tool/xpbd --into pipeline-3d` (merge pipeline-3d first if it moved).

Draft summary box. Recommended: ship the anime default (cloth held toward the drawn shape on the pelvis, pins on the
skin): all four gated motion checks PASS (kick 0.2% inside / 6% stretch, squat 0.6% / 10%) where the shipped skinned
skirt stretches 199% at the kick and has 5.8% 0.185 L inside at the squat. Asked of Michael: (1) give the waistband the
body's weights near the waist too (yes/no; it sits 31% / 0.265 L inside the belly at the squat); (2) write the tuned
spring settings into the outfit graph now (A) or after the skirt chains are rooted on the skin (B); (3) informational:
the pelvis and belly capsules are fitted (p90 <= 0.022 L) but the cloth doesn't need them; they are for the VRM colliders.

## Round 3 (2026-09-30, night): calibration records, the waistband's weights, the replay, motion QA's CPU, the chains

Coordinator's decisions: (1) the waistband takes the body's weights near the waist (measure before/after; its shape IoU
in all views must hold); (2) spring settings go into the outfit graph only after the skirt chains are rooted on the skin
and the stiffness grid goes past 8. Merged pipeline-3d 3f7b730 (softras round 4, opt-in) at 5b95cc2: clean.
Harness scripts and outputs: `charkit/out/xpbd/r3/`.

### Motion QA's CPU (cpu.py, cpu2.py)
- **Settle once** (motionqa.settled: the 1 s rest settle is the same for both poses, the pose's matrices at share 0 are
  the identity exactly, so it runs once and each pose starts from a deep copy): the four checks bit-identical to the
  per-pose settle (cpu.json `identical: true`). Kept.
- **A 0.5 s settle: not taken.** It moves motion_squat_skirt_inside 0.00601 -> 0.00582 (stretch 0.10386 -> 0.10397), and
  the cloth isn't settled at 0.5 s: 0.011 L from the 1 s state (1 s against 1.5 s: 0.0019 L).
- Process time (cpu2.json, the scene built first and shared): per-pose settle 82.7 / 72.3 s, settle once 63.8 / 55.6 s
  (-23%). Not half: the XPBD step is 85% of a pose (cProfile: 22.8 s of 27 s, 0.38 s a frame).
- **The step's two slow kernels rewritten without allocation** (kern.py: per call, bending 5.6 ms over 5,766 hinges and
  capsules 2.6 ms over 2,220 x 8, the rest under 0.1 ms; 20 substeps x 2 iterations a frame): `_dihedral_into` writes
  the gradients into a buffer, `_collide_capsules` is scalar; the same arithmetic in the same order, so bit-identical
  (test_sim.test_the_scalar_kernels_are_bit_identical: positions, multipliers and hits equal to the bit against the array
  forms on a perturbed sheet; cpu3.py: motion QA's table and checks against cpu.json's).
- Floor for the calibration: method `skinned_shuffled` (motion.Shuffled: the skirt's coarse weights shuffled among its
  vertices, seeded; a random rig), generator `shuffled_weights` in charkit/calib/motion.py.

### Results so far
- **Motion QA CPU** (cpu3.json, process time, laptop): 82.7 / 72.3 s (round 2) -> 17.0 / 14.8 s, table and checks
  identical (0.00244, 0.0635, 0.00601, 0.10386). The kick's bake: 54.7 s -> 11.6 s.
- **The Blender replay** (replay2.log, `charkit/out/xpbd/r2/build/cloth/kick/replay.json`): the first replay found the
  coarse PC2 can't drive the build's objects (they hold the finalized mesh: stack = Armature, outline Solidify; 2,736
  cached positions against 21,888 vertices). The bake now writes the render mesh's positions (the build's finalize per
  frame; skirt.pc2 31.5 MB, each flap 3.1 MB for the 2 s clip; coarse.npz stays the compact cache): Blender's Mesh Cache
  (first, Armature off, outline off for the comparison) against our finalize, max |d| 1.2e-7 L at frames 0, 70, 95 for
  all three pieces (float32 rounding; frame 70 is mid-ramp, so the frame mapping is right).
- **The waistband's weights** (wb2.py -> wb2.json; skinstretch.py). The band sits across the spine/chest joint (the
  chest's head 0.10 L above its bottom edge, the hips' head 1.08 L below): the skin under it is spine 0.07-1.0, chest
  0.93-0; nothing on the hips. Variants at motion QA's poses (band: new inside share / depth L, coarse stretch p99;
  the skirt's top covered by the band at rest and exposed posed, ray out from the hips axis missing the band and the
  skin, for the cloth skirt (the anime default, pins on the skin) and the skinned skirt as shipped):

  | pose | rigid on the hips (as built) | the body's per vertex (shipped) | per column / one blend |
  |---|---|---|---|
  | squat: band inside | 0.377 / 0.265 | **0 / 0** | 0 / 0 |
  | squat: skirt top exposed, cloth / skinned | 0.370 / 0.168 | **0.032 / 0.647** | 0.032 / 0.647 |
  | twist_bend: band inside | 0.373 / 0.109 | **0.059 / 0.009** | 0.182 / 0.066 |
  | twist_bend: band stretch p99 | 0 | **2.08** (the skin under it: 1.34) | 0.05 |
  | twist_bend: skirt top exposed, cloth / skinned | 0.104 / 0 | **0 / 0.275** | 0.20 / 0.40 |
  | kick, split, arm poses | 0 inside | 0 inside (same) | same |

  Shipped: `"weights": "body"` on the waistband (garments.band_weights; a belt's default stays the hips). It ends the
  band's dive into the belly and keeps the anime cloth skirt's top under the band; the twist's stretch is the skin's own
  (LBS across the chest joint). The cost lands on the skinned skirt (VRM's real-time path): its top stays on the hips
  while the band follows the spine, exposed 0.17 -> 0.65 at the squat. Its fix is the same transfer for the skirt's top
  rows (or the chains rooted on the skin, item 5): asked of Michael.
- **Calibration** (calib.log; the first records kept in `charkit/out/xpbd/r3/calib1/`): kick stretch and squat stretch
  CALIBRATED (design 0.056..0.070 / 0.096..0.135, known-bad skinned 1.99 / 0.87 FAIL, floor (shuffled rig) 47 FAIL).
  Kick inside BLIND: the pelvis-carried skirt reads 0.012 WARN at the kick, not a FAIL; the known-bad is now the style's
  cloth with no body colliders (`motion_nocol`: the thigh through the skirt; recalibration calib2.log). **Squat inside
  MISCALIBRATED**: the held solve's nudges read 0.0027..0.0149 (WARN at substeps 16, ramp 0.45 s, hold 0.85; PASS <=
  0.01): not robust to nuisance settings. Not loosened: it is now ungraded (INFO, in the table; motionqa.UNGRADED) and
  its CALIBRATION entry removed. To grade it again: make the squat's waist robust (the nudges' spread), then re-run.
- The waist pictures (`charkit.sim.waist`, `python -m charkit.sim waist BUILD --out DIR`): `charkit/out/xpbd/r3/waist/`,
  framed on the band; numbers identical to wb2.json.
- **Kick inside recalibrated** (calib3.log): the cloth with no colliders also reads only 0.0125 at the kick (calib2: still
  WARN): the thigh through the skirt is a ~1% defect there, so the kick's inside limits are tightened from the records,
  PASS <= 0.005, WARN <= 0.01 (motionqa.POSE_LIMITS; tighter, not looser): CALIBRATED (design 0.0017..0.0039, known-bad
  motion_nocol 0.0125 FAIL, floor 0.054 FAIL, current 0.0024 PASS). Three motion checks graded and calibrated; the
  squat's inside INFO.
- **The chains** (tune_hips/, tune_skin/; grid stiffness 2..64, gravity 0..0.3, drag 0.3..0.9), joint error L over the
  motion, and the garments on the best chains (worst inside share / depth L / stretch p99):

  | roots | skirt best (stiff, grav, drag) | err | squat skirt | flaps best | err |
  |---|---|---|---|---|---|
  | the hips | 64, 0.15, 0.9 (the grid's top edge again) | 0.069 (at 8: 0.070) | 0.064 / 0.185 / 0.09 | 8, 0.05, 0.7 (interior) | 0.050 |
  | the skin (chain_root: polar blend) | 2, 0, 0.9 (the bottom edge) | 0.103 | 0.049 / 0.190 / 0.21 | 2, 0.05, 0.9 | 0.168 |

  Rooting the whole chain on the skin isn't the fix: the root's rotation (spine/chest) turns the chains' rest direction
  away from the cloth's (held toward the drawn shape carried by the hips), so softer chains win and the error grows; the
  squat's 0.185-0.19 L stays. Next (not run, the coordinator's call): the root's position on the skin and its rest
  direction on the hips (as the cloth does: pins on the skin, hold toward the hips-carried shape), i.e. a helper root
  bone whose head rides the skin and whose rotation stays the hips'; above stiffness 8 the skirt gains 0.001 L, so 8 is
  enough. Spring settings stay out of the outfit graph (decision 2).
- Pregate PASS at 78bc572 (0 moved). Gate launched at 6dee774 (`python -m charkit remote gate tool/xpbd --into pipeline-3d`, log charkit/out/xpbd/r3/gate.log).
- **Review page** `charkit/out/xpbd/r3/review/index.html` (review.page3, made by `charkit/out/xpbd/r3/page.py`): the
  summary box, the waistband (numbers and pictures), the calibration, the CPU, the chains, the bake and its replay.
- **Chains, roots riding the skin with the hips' rest direction** (`--root skin_pos`, tune_skinpos/, stiffness 1..32): skirt
  best 2, 0, 0.9 (interior: 4 -> 0.0664, 32 -> 0.0683) err 0.066 L (the hips' roots 0.069); flaps best 1, 0, 0.9 (the
  grid's bottom edge) err 0.046 (0.050). The squat's skirt: worst inside 0.066 at 0.141 L, stretch 0.23 (hips' roots:
  0.064 at 0.185 L, 0.09): the depth drops a quarter, the share doesn't; the flaps at the squat 0.027 / 0.008 L (hips' roots:
  0). Eight chains round the skirt (each column carried by its azimuth blend, its top bone rigid) can't follow the
  thighs as the cloth does: the roots aren't the limit. Not ready for the outfit graph (decision 2 stands). Next, if
  wanted: more chains (16-24) or the skirt's chain colliders on the thighs; the realistic alternative is the bake.
