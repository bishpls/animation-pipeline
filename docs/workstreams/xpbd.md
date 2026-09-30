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
Tests: `charkit/tests/test_sim.py` (15).
