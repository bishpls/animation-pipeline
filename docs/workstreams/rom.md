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

## QA part (romqa)
- 20 checks over 17 poses: 95 s wall / 133 s CPU on the laptop (default build), 1.7 GB peak. Calibrated (records
  pending): rom_vol_elbow/_knee/_fingers (RomVolume: dual quaternion reference, known-bad rom_lbs = the build as it
  ships), rom_shoulder_torso/_open (RomShoulder on rom_cand2, known-bad stored rom_rigid_shoulder), rom_hair_shoulders,
  rom_finger_finger, rom_weights_stray (Rom: the build itself; known-bads hair_on_chest, fingers_shifted, stray),
  rom_garment_strain (RomRigid). The rest INFO (calib/rom.py says why: no reference rig passes them yet).
- Calibration A (calibrate-rom-1001-140816-7e7a, follower re-attached) ran with the old thumb flexion: re-run
  rom_finger_finger after it (the thumb's flex changed in pose.py, THUMB_PALM 0.15). B
  (shoulder_torso + shoulder_open on rom_cand2) relaunched after adding rom_shoulder_open.

## Calibration (2026-10-01, local: the build box was loaded, 86 min in one group; killed my box jobs)
- CALIBRATED on rom_base2 (records committed 26e06b0e): rom_vol_elbow (design DQS 0.995-0.996, known-bad rom_lbs
  0.382), rom_vol_knee (0.991-0.993 / 0.384), rom_vol_fingers (0.982-0.984 / 0.643), rom_hair_shoulders (5e-5..1.1e-4 /
  hair_on_chest 0.0106), rom_finger_finger (0 / fingers_shifted 0.0228), rom_weights_stray (0 / stray 0.0152),
  rom_garment_strain (rigid 0 / shuffled 102.6; current 0.62 FAIL).
- Shoulder (RomShoulder on rom_cand2, known-bad stored rom_rigid_shoulder): the first run read shoulder_torso
  MISCALIBRATED (arm_across nudged 5% put the hand 0.11 L into the head: arm_head). Fixed: arm_torso pairs only, the
  shoulder poses (forward, side, overhead, arms forward); recalibration running (log charkit/out/rom/calibB_local.log).
- The candidate's skin has stray neck weight on its bridge (0.53% of the skin, 10% of the jacket): rom_weights_stray
  (calibrated) will FAIL on tool/garments4-shoulders' merge until the bridge drops it (a new FAIL under K: blocks).

## Gate
- tool/rom merged pipeline-3d 27a4b6c3 (4ccdc339); pre-gate on the earlier tip bc06dc6d into 60c0f1a4: PASS (0 moved).
  Gate launched: `remote gate tool/rom --into pipeline-3d` (log charkit/out/rom/gate.log).
- Expected under K: the nine graded rom_* checks are new (records calibrated); five FAIL on the default (vol_elbow,
  vol_knee, vol_fingers, shoulder_torso, shoulder_open, garment_strain: reported, not blocking); the candidate builds
  with --vrm (gltf.py changed: EXPORT_CODE) and runs the rom QA part (about 95 s wall, 133 s CPU on the laptop).

## Box jobs
- Boards: charkit/out/rom/box_base2/boards, rom-cand's charkit/out/rom/box_cand2/boards (112 each, toon renderer).
- Calibration (build box): A (logs charkit/out/rom/calibA.log, -> charkit/out/rom/calibA/cal.json), B (calibB, the
  shoulder on rom_cand2). Records: write locally from the JSON (the box's synced files are read-only).
- Close-ups: --closeups on both (cu_base2.log / cu_cand2.log -> box_*/closeups).

## Michael's answers (2026-10-01, through the coordinator)
1. Volume at the elbows, knees and knuckles: **A**, helper bones driven by VRM node constraints (not corrective shapes).
2. A joined hip built like the joined shoulder: **yes**.
3. The garment failures on the raised arms go to the garments' round 8 (told), not the motion round.

## The next motion round's brief (launches when tool/rom merges): each failure, its measure, its fix
Measure everything with `python -m charkit rom BUILD [--boards] [--closeups]` (the suite, 28 poses) and the QA part
(`rom_*` in qa.json); numbers below are rom_base2 (the default) / rom_cand2 (the joined shoulder), 2026-10-01. Every fix
keeps the pieces' shape IoUs (the guard) and reports them per view next to the check it targets.

1. **Elbow, knee and knuckle volume (both bodies; blocks every arm and leg motion).** Measure: rom_vol_elbow (the ring
   at the joint posed over rest, elbows_135) 0.382 FAIL, rom_vol_knee 0.384 FAIL (knees_135; squat 0.463), rom_vol_fingers
   0.643 FAIL (the fist's PIP); 90 deg reads 0.71 (WARN); rom_knee_folded 4.8% (INFO). The band at each joint is a 50/50
   blend, so linear blend skinning keeps cos(angle / 2); the same weights under dual quaternion skinning keep 0.99 (the
   calibration's design leg), so the weights' layout is fine and the skinning is the issue. Fix (Michael: A): a helper
   bone per elbow, knee and finger joint (PIP, DIP, MCP; the thumb's two) at the joint, child of the parent bone,
   turning half the joint's rotation through a VRMC_node_constraint rotation constraint (source the child bone, weight
   0.5); the blend band's middle weights move onto it (the parent / helper / child split the band in thirds). The
   export writes the constraint (charkit/gltf.py: VRMC_node_constraint on the helper node) and the suite's rig
   evaluates it (charkit.rom.Rig: constraints applied after charkit.pose.solve; add a test that the helper turns half).
   Target: rom_vol_* >= 0.8 at 135 deg (PASS), no new garment penetration at the elbows (rom_sleeve_body elbows_135
   0.043 today).
2. **The hip (both bodies).** Measure: rom_leg_torso (thigh skin newly inside the torso) 0.28 L FAIL in the squat, 0.27
   in the front kick; rom_leg_open (the thigh shell's buried top out of the pelvis) 0.21 L. The legs are separate rigid
   shells (thigh + shin one shell, weighted to the leg bones only). Fix (Michael: yes): a joined hip built like the joined
   shoulder (code_body.socket_rim / shoulder_bridge generalised: a socket in the torso's hip, a bridge of edge loops to
   the thigh's ring, weights eased hips -> upperLeg over the bridge, the rig's hip joint where the thigh's rotation
   centre is); under the shorts, so garments' shape IoUs stay. Target: rom_leg_torso <= 0.01 L, rom_leg_open 0, the
   hip zone's strain and folding reported (add hip_folded to the QA when it has a joined hip).
3. **The joined shoulder's bridge (the candidate, tool/garments4-shoulders' body).** (a) Neck weight on the bridge's
   top rows: rom_weights_stray (skin) 0.53% FAIL (the default 0); the jacket inherits it (10% of its vertices stray);
   a head turn pulls the shoulders (shoulder strain 0.15) and the jacket and sleeves (sleeve_top 1.3%, sleeve_body 0.04
   L). Fix: clamp the neck influence to the neck join's own rows (code_base's neck join), renormalise. This check will
   FAIL the shoulder branch's merge under K until it's fixed. (b) The bridge stretches and folds: rom_shoulder_strain
   (zone within 0.35 L of the joint, edges >= 0.015 L) p95 1.11 forward, 0.65 side, 1.30 overhead; rom_shoulder_folded
   4.7% / 0.4% / 5.8% (INFO: no shoulder passes yet). Fix: more edge loops on the armpit side of the bridge, the
   clavicle following the raise (a VRMC_node_constraint rotation on the shoulder bone, a third of the upper arm's
   elevation), the arm's weight spread wider over the bridge. (c) The rim against the torso stretches 0.71 in the spine
   twist: blend the rim's weights chest / upperChest as the torso round it. Targets: strain p95 <= 0.5 (WARN) then
   0.25, folded <= 1%; rom_shoulder_torso and rom_shoulder_open stay 0 (calibrated, PASS on the candidate).
4. **Reported, not this round:** the neck stretches 0.29 (default) / 0.18 (joined) at a 60 deg turn (rom_neck_strain,
   INFO WARN); the hands through the skirt flaps in the spine twist 0.7% of their edges (rom_hand_skirt, INFO WARN); the
   hair through the joined body's shoulder line at the head turn 0.14% (rom_hair_shoulders WARN on the candidate) and
   the arms through the buns overhead; the boots' instep and heel weighted to the toes bone (2%, up to 0.40: toes only
   from the ball forward).
5. **Garments (round 8, Michael: yes):** puffs inside the arm at the raises 0.07-0.24 L (rom_sleeve_body), sleeves
   through the jacket, collar and bow 1-4% of their edges (rom_sleeve_top), the jacket into the skin 0.035-0.10 L
   (rom_top_body), the skirt into the legs 0.11 L (squat, spine bend; rom_skirt_legs), garment strain p95 0.62 (the
   skirt in the squat), 0.57-0.61 (the collar at the head turn: neck weight on the collar), 0.75-0.78 (the joined
   body's jacket at the raises; rom_garment_strain calibrated, FAIL). The garment checks other than strain are INFO:
   neither the body's weights on the garments nor the garments riding the skin as shells keep the puffs and the skirt
   out (calib/rom.py), so they wait for a cloth or spring solution to calibrate against.

## Findings on the way
- motion QA ran SKIPPED on hands2_after (`skirt: not a grid`) but runs on rom_base2 (kick inside WARN): fixed upstream.
