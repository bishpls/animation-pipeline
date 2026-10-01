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

## Numbers (2026-10-01; default rom_base2 / joined candidate rom_cand2; laptop and box readings bit-identical)
- Joint volume (ring at the joint, posed over rest; LBS keeps cos(angle/2) at a 50/50 ring): elbow 90 deg 0.706,
  135 deg 0.382; knee 90 0.708, 135 0.384, squat 0.463; fingers (fist PIP 100 deg) 0.643. Same on both bodies. Dual
  quaternion skinning of the same rig: elbow 0.996, knee 0.992, fingers 0.983.
- Arm into torso at the raises (deepest new, L): default 0.0355 (forward 90), 0.0475 (arms forward), 0.052 (across);
  candidate 0 everywhere. The joined shoulder's own skin (within 0.35 L of the joint, edges >= 0.015 L): strain p95
  ~1.1 (forward), 0.5 (side), 1.3 (overhead); folded+collapsed area 4.7% / 0.4% / 5.8%; spine twist strain 0.7 at the
  bridge (the rim's clavicle weight against the torso's chest blend); head turn 0.15 (the bridge's top takes neck weight).
- Thigh into torso: 0.28 L in the squat and the front kick (both bodies: the legs are separate rigid shells).
- Garments: puffs inside the arm/skin at the raises 0.07-0.235 L (default) / 0.04-0.178 (candidate); sleeves through
  the top/collar/bow 1.4-2.5% of their edges (default), up to 4.1% (candidate, across); skirt into the legs 0.108 L
  (squat), 0.072 (kick), 0.112 (spine bend); garment strain p95: skirt 0.62 (squat), collar 0.58 (head turn: neck
  weights), waistband 0.51 (spine bend); candidate garments stretch at the raises (0.42-0.81) and its sleeves move with
  the head turn (sleeve_body 0.04, sleeve_top 1.3%).
- Hair through the shoulders at the head poses: default <= 0.0001 (PASS), candidate 0.0014 (WARN); hands through the
  skirt at the spine twist 0.68% (both).
- Weights: sums exact, the skin has no stray influence; the boots' instep/heel weighted to the toes bone (2% stray, up
  to 0.39).
- Posed toon artefacts (artifactqa on posed bundles vs rest, face/neck left out): nothing FAILs but terminator_hair at
  the kick (lighting on the leaned-back head).
- Known-bad stored: rom_rigid_shoulder (charkit/out/calib/builds, + charkit/calib/known_bad/rom_rigid_shoulder.json).

## Box jobs
- Boards: charkit/out/rom/box_base2/boards, rom-cand's charkit/out/rom/box_cand2/boards (112 each, toon renderer).
- Calibration (build box): A (logs charkit/out/rom/calibA.log, -> charkit/out/rom/calibA/cal.json), B (calibB, the
  shoulder on rom_cand2). Records: write locally from the JSON (the box's synced files are read-only).
- Close-ups: --closeups on both (cu_base2.log / cu_cand2.log -> box_*/closeups).

## Findings on the way
- motion QA ran SKIPPED on hands2_after (`skirt: not a grid`) but runs on rom_base2 (kick inside WARN): fixed upstream.
