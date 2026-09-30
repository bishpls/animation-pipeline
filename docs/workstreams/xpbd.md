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
