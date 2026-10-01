# tool/rom: the range-of-motion (ROM) suite

Branch `tool/rom` (worktree `~/animation-pipeline-rom`, from pipeline-3d 60c0f1a4). Brief (coordinator, 2026-10-01): the
measurement between the base model and motion testing. Named pose presets (data), scored per pose (joint volume,
interpenetration by pairs, garment stretch, posed toon artefacts, weight sanity), report-only, on two bodies (the
default; the joined-shoulder candidate), calibrated against known-bads, wired into QA as report-only checks, gated.

## Layout
- `tool/rom-cand` (worktree `~/animation-pipeline-rom-cand`): tool/rom + tool/garments4-shoulders 72bc6bf7 merged (the
  joined shoulder's code, off by default), ONLY to build and measure the candidate body. Never gated or merged. Merge
  tool/rom into it to get the suite's code there.
- Out dir: `charkit/out/rom/` (specs, logs, lab scripts), builds `charkit/out/rom_base` (tool/rom, default spec) and
  `~/animation-pipeline-rom-cand/charkit/out/rom_cand` (cand.json = clawd.json + candidate_shoulder.json, copied from
  garments4's tools/garments5/v/candidate_shoulder.json into rom-cand's charkit/out/rom/specs/).

## Design
- The rig measured is the shipped export (OUT/clawd.look.glb): its skeleton (VRM humanoid nodes, inverse bind
  matrices), every mesh's 4-slot JOINTS_0/WEIGHTS_0, linear blend skinning as a runtime does.
- Poses: `charkit/poses/rom.json` (data), applied by `charkit/pose.py` per bone in hierarchy order: aim, raise, swing,
  bend (anatomical hinge, carried by the parent), spread, twist, turn/nod/tilt (body axes).
- Hand poses after the hand sheet (refs gen/hand_breakdown.png): relaxed, open (spread), fist, point.

## Code (tool/rom)
- `charkit/pose.py` + `charkit/poses/rom.json`: the pose library (29 presets) and its solver; tests `test_pose.py`.
- `charkit/rom.py`: Rig (the export: skeleton from the IBMs, tails from the bundle's landmarks, helper bones merged into
  their humanoid ancestor), Context, measure_pose, summary, LIMITS/grade, weight_sanity, joint rings, Posable +
  art_posed (artifactqa's detectors on posed bundles vs rest), render_boards (toon renderer), run/markdown/main
  (`python -m charkit rom BUILD [--boards] [--art]`); tests `test_rom.py`.
- `charkit/romqa.py`: QA part 'rom' (order 2600), checks rom_* (INFO + proposed grade until calibrated: CALIBRATED).
- `charkit/calib/rom.py`: the adapter Rom (nudges, shuffled floor, BROKEN known-bads, stored rom_rigid_shoulder).
- `charkit/gltf.py`: the look export carries the skin weights (look_only read only the outline group before: every
  vertex bound to the hips, so the look.glb wasn't posable). The QA's cached parts are unaffected (33/34 restored).

## State
- 2026-10-01: builds on the build box: rom_base / rom_cand (look export without weights: their QA only), then
  rom_base2 / rom_cand2 (after 847d7c6c: the weighted look export; logs build_base2.log, rom-cand's build_cand2.log).

## Findings on the way
- motion QA is SKIPPED on the current default (hands2_after's qa.json: `ValueError: skirt: not a grid (5110 vertices,
  stride 144)`): the motion_* checks don't run since the staircase/pleat skirt.
