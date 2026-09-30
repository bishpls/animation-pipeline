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

## Log
- 2026-09-30: started; a baseline box build of 2f42155 (`charkit/out/xpbd/base`) for the products the pilots read.
