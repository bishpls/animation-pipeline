# Workstream: the crab clip detailed and placed by its relations (`tool/accessories6`)

Branch `tool/accessories6` from pipeline-3d 25ff0f25 (the remade clips from tool/accessories5 and `sweep optimize`),
worktree `~/animation-pipeline-acc6`. Earlier: `accessories5.md` (in `~/animation-pipeline-acc5`, read-only: the clip
templates, accfit, accqa, A3).

## The task (coordinator's brief, 2026-10-01)
Michael's review of round 5 (A3):
- Detailing: "Legs on the current version are too short, and... all on the bottom of the crab, not actually on the
  sides. Also the pinchers are solid circles." The clips-alone sheet (`hair_clips_layers`, bottom left) draws three long
  legs a side off the body's sides, raised arms ending in open V-notched claws, eyes on stalks.
- Placement: the crab moved under the star's lower tip; his eye: upper-left of the star (head-on), turned so the
  pincers' midpoint points upper-left, along the star. Cause: accfit pins the crab's axis to the drawing's absolute
  angle, nothing scores the pair's relation, the local polish took the nearest exit. Rule: a moved piece keeps its
  relations, not its absolute drawn angle.
- Part A: measure (declared checks, sheet passes, today's crab fails), remake the template, fit with `sweep optimize`.
- Part B: diagnose Michael's placement under accfit's loss vs A3; relational measures (bearing star -> crab, gap, the
  crab's axis against the bearing, against the hair's flow), declared and calibrated; fit from a ring of starts.
- Coordinator (mid-round): art_terminator_hair rose with the clips merge (strokes alone 2.001 six-placement mean;
  pipeline-3d with the clips 2.173 +- 0.128, single placement 2.37; bound 2.064): report it as six placements for A3
  and every fit, recover it if the crab's spot allows; it's a flag check, don't worsen it.

## State
Round DONE: gate 2 PASS under K (f5afc94e into 59c93f38). Review page `charkit/out/acc6/review/index.html`.

- Baseline box build of pipeline-3d 25ff0f25: `charkit/out/acc6/base` (art_terminator_hair 2.432 WARN single
  placement, art_peeks_hair 17 WARN). A local copy of acc5's A3 build (the same clips): `charkit/out/acc6/a3_local`.
- Work files: `charkit/out/acc6/work/` (alone_*.png the sheet's masks; parts_proto.py, limbs_try.py, clips_try.py,
  qa_try.py BUILD [OUT.json] (the accessories part on a build), tpl_try.py SHAPE_JSON, checks_try.py).

## Part A: measure first
`charkit/limbs.py`: a piece's parts read from its silhouette, upright, in its core's width (scale-free): the core (the
body) and lobes (the claws) by a watershed on the opened mask (opening 0.08 sqrt(area); seeds the distance's h-maxima),
the limbs (legs, stalks) as what the opening cut off beyond 0.06 core widths, each its reach, root (elliptical angle on
the body: 0 the side, - below) and direction; a lobe's notches from its convex hull (fingers = 1 + notches deeper than
0.12 of its size). Distance-transform morphology (0.3 s a crab). `spoil()` makes the calibration floors.

The sheet's crab (face-on, read by limbs): legs 3 / 3, reach 0.247 body widths, roots +15 / -13 / -28 deg (mean -8.8),
directions -25 / -31 / -55; claws 0.58 across at (+-0.62, 0.46), notch 0.247, fingers 2 / 2; stalks 2, reach 0.208.

Declared checks (accqa.DECLARED_CHECKS, family `limbs` added to charkit.declared, view `face`: accqa.FACE, our clips
face-on in their own frame (accqa.own_axes: the spec's facing and tilt), scaled to the sheet's area, side by side
(face_labels)):

| check | measure | limits | sheet moved (8 moves) | A3 (pipeline-3d) | floor |
|---|---|---|---|---|---|
| acc_crab_legs | legs per side, max diff | [0, 0] | 0 PASS | 3 FAIL (0 / 0) | legless 3 F |
| acc_crab_leg_reach | |ours/sheet - 1| | [0.2, 0.35] | <= 0.006 | none FAIL | short_legs 0.553 F |
| acc_crab_leg_roots | mean root, deg | [12, 25] | <= 1.9 | none FAIL | bottom_legs 52.5 F |
| acc_crab_claw_fingers | per claw, max diff | [0, 0] | 0 | 1 FAIL (1, 1) | solid_claws 2 F |
| acc_crab_claw_notch | |ours - sheet| | [0.06, 0.1] | <= 0.009 | 0.139 FAIL | solid_claws 0.156 F |
| acc_crab_stalks | |ours/sheet - 1| | [0.25, 0.5] | <= 0.009 | none FAIL | no_stalks none F |

INFO beside them: acc_KIND_alone now in the clip's own frame (A3 crab 0.585 -> 0.694: a remeasure), acc_KIND_side
(new: edge-on against the sheet's side drawing, its hair-clip loop cut: accqa.edge_body; A3 crab 0.680, star 0.751).
Calibration stand-in: calib/clips.py `Clips._face` (the sheet's crab redrawn at 1 + 0.015 dy scale and (dy, dx) / 2 px;
floors legless, short_legs, bottom_legs, solid_claws, no_stalks). Known-bad to store: `acc_a3_crab` (charkit/out/acc6/base).

## Part A: the template
accessories.crab remade: the body ellipsoid; pincer(): a flat-backed dome over an outline with a V notch (opening
claw_notch deg, depth claw_cut of the radius, axis claw_up deg from vertical toward the inside); capsule legs from the
body's sides (leg_at roots, leg_dir directions, leg_bend), eyes on stalks. Defaults = the sheet's numbers: face-on IoU
0.884, side 0.654, every parts check PASS; turnaround as-drawn IoU with zero poses 0.726 / 0.651 / 0.704 (round 5's fit
with poses 0.848 / 0.797 / 0.768). accfit.shape_checks / shape_loss: a template scored as the QA scores the built clip
(per view as-drawn IoU, piece_pin_crab per view, alone, side, the declared FACE checks through charkit.declared).

## Part A: the template fit (sweep optimize, stage adapter accfit_shape)
- opt_crab (charkit/out/acc6/opt_crab, 656 evaluations): failed: sigma0 0.2 of each range on 28 knobs with hard
  constraints (guard 15% per view, the parts checks as flags/keep): 90% of rows infeasible, the best a probe row.
- opt_crab2 (2,671 evaluations, 6 min on 13 build-box workers; per-knob steps 0.75 x accfit.SHAPE_KNOBS, poses 4 deg):
  shape_loss 0.943 -> 0.720; turnaround as-drawn IoU 0.693 / 0.680 / 0.657 -> 0.841 / 0.763 / 0.757; but the parts
  rested on their PASS edges (leg reach 0.198 of 0.2, stalks 0.247 of 0.25: legs 20% shorter than the sheet's), the
  face-on 0.883 -> 0.781, side 0.651 -> 0.540: the loss had no pull inside PASS.
- opt_crab3 (from opt_crab2's best; w_alone 1.0, w_side 0.3, w_parts 0.3 with pull: each parts check's value over its
  pass limit inside PASS too; 2,697 evaluations): every parts check on the sheet's reading, face-on 0.855, side 0.626,
  turnaround 0.780 / 0.699 / 0.740. But the legs came out sticks (width 0.055 of the body against the sheet's 0.087):
  thick legs bunched at the body read as body, so the fit escaped through thin ones. Added acc_crab_leg_width (limbs
  'width': twice the median depth along each leg's medial line; floor thin_legs; 3f7fdfd5).
- **opt_crab4** (the width in, w_side 0.5; 3,114 evaluations): **the crab** (in the six specs, 9ea... see git log):
  legs 3 / 3, reach 0.2473 (sheet 0.2474), width 0.001 off, roots -7.8 (sheet -7.7), fingers 2 / 2, notch 0.2459
  (0.2469), stalks 0.2071 (0.2078); face-on IoU 0.893 (A3's crab 0.728), side 0.661 (0.740); turnaround as-drawn IoU
  0.772 / 0.691 / 0.740 (the template posed; round 5's template 0.848 / 0.797 / 0.768: the turnaround draws short
  legs). CRAB_AXIS = 90 + its rolls: 89.2 / 80.9 / 87.4. Figures: work/faceon_parts.png, edgeon.png, shape_fits.png.

## Part B: the ring (tools/acc6/ring.py, four box jobs; charkit/out/acc6/ring/ring.json)
Each bearing solved (the crab 0.012 L clear, its axis the bearing + the drawn turn -99.5), measured with accfit's loss
(W_REL 0.5, ANGLE_NEAR 0.05): b000 / b045 / b315 unsolvable (behind the star toward the ear: the crab hidden, cost 30-87);
b090 loss 24.9 (profile visible 0.82); b135 13.2; **b180 7.9**; b225 11.6; b270 18.3 (vis 0.94); Michael's 16.7 (turn
FAIL 98-100 deg off); the drawn arrangement nudged clear 7.2 (profile visible 0.959: under 0.97); 'rotated slightly'
(bearing 140, axis 115) 12.7.

## Part B: diagnosis (tools: charkit/out/acc6/work/diag.py, diag2.py; terms.py: accfit's loss by term; the A3 crab
template as built: pipeline-3d's accessories.crab)
Michael's placement by hand (the crab upper-left of the star in front, bearing 135, its axis 135 = pincers upper-left,
0.01 L clear; its facing turned with its anchor): accfit loss **10.57 vs A3 5.67**. The terms that prefer A3: the
absolute angle (+6.0: the crab's axis 50-65 deg off the drawn absolute angle), the crab IoU (+0.65: the shape IoU aligns
centroid and area, not rotation, so a turned crab reads worse: 0.51 / 0.42 / 0.51 vs 0.72 / 0.77 / 0.65), pos +0.32,
size +0.10. Visible 1.0 / 1.0 / 1.0, seats 0. And it was never searched: round 5's starts A / B / C all moved the crab
down. Other hand placements (loss): the drawn arrangement nudged 0.01 L clear (left of the star, upright) 6.50 (profile
visible 0.979); upper-left upright 5.99; upper-left with the drawn turn kept (axis 30) 8.83; upper-left 'rotated
slightly' (axis 115) 6.85.

The relations (front / three-quarter / profile; ours vs the drawn pair):
- drawn: bearing 188 / 189 / 190 (the crab left of the star), axis 83 / 78 / 82 (upright), turn -105 / -112 / -108,
  axis against the hair's flow 171 / 164 / 166 (the claws up against the strands), gap 0 (touching).
- A3: bearing 254 / 249 / 253, turn -165 / -172 / 176, flow -172 / 162 / 140, overlapping silhouettes.
- Michael's (bearing 135, axis 135): turn 0 / -17 / -50, flow -156 / -149 / -157.
- The finding: Michael's rotation keeps the crab's turn against the hair (axis 115: flow -173, the drawn 171), not its
  turn against the star (the drawing's crab stands upright beside the star: -105). The turn check (target the drawn
  pair's) fails his placement (105 deg off); the flow check passes it at axis 115. A decision for Michael.

## Part B: the relational checks (declared family `pair`, accqa.DECLARED_CHECKS; 2f19de99)
acc_crab_VIEW_{bearing [30, 55] deg, gap [0.025, 0.05] L past the drawn, turn [25, 45] deg, flow [25, 45] deg}, front /
three-quarter / profile; ours each clip drawn alone, the crab's axis its frame's y in the picture (accqa.axis_in_view),
the drawing's accqa.CRAB_AXIS (90 + the template fit's roll per view), the flow our hair's strands (geom/hair_pieces
`strand`, root to tip) under the crab (accqa.hair_flow, flow_under). Calibration (Clips): the drawn pair passes every
move (all 0.0-0.4); floors orbit (bearing 101-145 F), pointing_away (turn 105-112 F), across_flow (flow 71-116 F), apart
(gap 0.052-0.076 F); A3 fails bearing (66 / 59 / 64 with [30, 55]) and turn (60 / 61 / 77). Known-bad acc_a3_crab stored
on the build box (charkit/out/calib/builds/acc_a3_crab; charkit/calib/known_bad/acc_a3_crab.json).

## The tool: sweep optimize, first real use (for the coordinator)
- `starts` added (a ring of starts: each its own CMA-ES from that point with its share of the budget, one history,
  the best across; test_optimize::test_a_ring_of_starts_searches_from_each).
- Friction: sigma0 0.2 of each range is too wide for a 28-knob template fit under hard constraints (90% infeasible);
  per-knob `step` fixed it. The stall rule's 'still wide' x3 spent 45 generations on a run that had stalled.
- accfit_place now emits graded visible / seat / pair checks and piece_pin_KIND (the guard reads them); args shapes,
  relate {w_rel, angle_near}.

## art_terminator_hair (six placements, tools/acc6/term6.py on the build box)
| build | single | six-placement mean +- std | per view f / 3q / p / back | peeks |
|---|---|---|---|---|
| A3 (pipeline-3d 25ff0f25, charkit/out/acc6/base) | 2.432 | 2.204 +- 0.151 | 8.25 / 7.71 / 4.46 / 1.87 | 17.3 |

## Part B: the placement fit (sweep optimize with starts; charkit/out/acc6/opt_place, render2, 5,009 evaluations)
8 starts (b000..b315), each ~630 evaluations (34 generations of 18): best per start (f = accfit loss with W_REL 0.5,
ANGLE_NEAR 0.05): **b180 5.57**, b225 6.61, b135 7.25 (it moved round to the drawn bearing too), b090 9.98, b315
20.4, b270 21.8, b000 26.1, b045 30.7; control (A3 with the fit-4 crab) 13.56; refs: Michael's 16.49 (infeasible: no
new FAIL / turn), the drawn arrangement nudged 7.56 (infeasible: profile visible 0.952), 'rotated slightly' 12.21.
sb180_g34_10: bearing 2.0 / 5.4 / 5.6 off, turn 2.5 / 8.1 / 2.1, flow 1.1 / 1.5 / 4.5, gap 0; crab visible 1.0 /
0.998 / 0.982; crab IoU 0.758 / 0.677 / 0.620 (A3 build 0.724 / 0.769 / 0.650); crab pos 0.038 / 0.183 / 0.339; back 10
px; but the star shrank 10% (lsize -0.106: front size 0.941 PASS -> 0.847 WARN) and moved: the star is not this round's,
so polished again with A3's star kept: opt_place2 (crab knobs only, starts the three best crabs), running.
Fixed on the way: `--box auto` picked render2, whose copy lacked the python stage's args.build: optimize._box now pushes
it (as a sweep's base). Michael's placement build: charkit/out/remote/clawd_michael.json -> charkit/out/acc6/michael
(ring_M's solve: bearing 127 not 135, cost 0.61), running.

## Part B: the pick and the builds
opt_place2 (A3's star kept; crab knobs; starts the three best crabs; 2,402 evaluations): sb180_g45_11 f 5.77 but the
crab faced front (profile size 0.784, angle 50 FAIL, profile IoU 0.533: -18% against pipeline-3d's build, the gate's
guard). The optimizer's guard compares with its control (A3's placement with the new crab: profile 0.584), not the gate's
base build; so the pick takes the best f among rows that hold the gate's rules against pipeline-3d's build (crab IoU per
view >= max(0.60, 0.85 x 0.724 / 0.769 / 0.650), |angle| <= 20, |size - 1| <= 0.25, no relational FAIL):
**sb180_g16_11** (f 6.44). In the six specs (commit "the crab placed by its relations").

Builds (box): `charkit/out/acc6/after` (the fit), `charkit/out/acc6/michael` (Michael's placement, clawd_michael.json).
QA (base A3 -> after; Michael's):
- parts: every acc_crab parts check FAIL -> PASS (both new-crab builds).
- relations: bearing 66 / 58 / 64 F -> 12.4 / 5.4 / 9.4 PASS (Michael 60 / 57 / 71 F); turn 65 / 63 / 82 F -> 20.0 /
  0.4 / 2.3 PASS (Michael 107 / 103 / 67 F); flow 9 / 5 / 32 -> 6.1 / 3.7 / 7.2 PASS (Michael 29 / 39 / 31 W); gap 0.
- crab IoU 0.724 / 0.769 / 0.650 -> 0.728 / 0.677 / 0.705 (three-quarter -12%; Michael 0.57 / 0.41 / 0.54 F);
  visible 0.997 / 0.988 / 0.988 -> 1.0 / 0.997 / 0.980; pos front 0.193 F -> 0.059 W; angle 10.4 W / -1.1 / 10.6 W ->
  -0.2 / -13.1 W / 13.8 W; acc_crab_alone 0.585 -> 0.769; no new FAIL.
- art_terminator_hair (flag): single 2.432 -> **2.509, grade WARN -> FAIL** (Michael 2.482 WARN); six placements A3
  2.204 +- 0.151, fit 2.254 +- 0.151, Michael 2.246 +- 0.148. Attribution (`sweep swap base after --groups accessory
  --drop`, charkit/out/acc6/swap_term): the crab carries 100%; without any crab the hair reads 2.49 (base) / 2.49
  (after): round 5's crab under the star's tip was hiding torn shadow patches (2.493 -> 2.432); at the drawn spot it
  hides none (and adds 0.02). Screening placements for it: tools/acc6/termscreen.py (the crab substituted into the
  after bundle, the artifacts part with the numpy drawing: it reproduces the real 2.432 / 2.509), 40 candidates that
  hold the gate's rules, four box jobs (charkit/out/acc6/termscreen_*).
- Calibration (box, records committed): 13 calibrated against acc_a3_crab, 6 guard (flow, gap: floors only).

### The terminator recovered (sb180_g17_07)
Screen (tools/acc6/termscreen.py, 40 candidates, charkit/out/acc6/termscreen_*): 2.453 (sb180_g17_07, sb180_g11_11) ..
2.509 (sb180_g16_11, reproducing the real build). Six placements: g17_07 2.198, g11_11 2.197, g16_11 2.254 (A3 2.204).
Picked **sb180_g17_07** (visible 0.987 in profile against g11_11's 0.973). Specs at it; box build
`charkit/out/acc6/after2` (base -> after2): no new FAIL, no flag grade moved (art_terminator_hair 2.432 -> 2.453 WARN
both; art_peeks_hair 17 -> 21, grade FAIL both); every parts check PASS; relations bearing 16.1 / 8.1 / 12.8, turn 25.2 W
/ 7.1 / 10.4, flow 6.9 / 0.6 / 1.8, gap 0; crab IoU 0.711 / 0.698 / 0.680 (A3 0.724 / 0.769 / 0.650: -1.8 / -9.2 /
+4.6%); visible 1.0 / 0.999 / 0.987; pos front 0.193 F -> 0.049 W; angle 3.0 / -9.7 / 17.2 W; acc_crab_alone 0.798;
hair_piece_bangs 0.759 -> 0.743, side_locks 0.505 -> 0.520.

Review page: `charkit/out/acc6/review/index.html` (page.json, make_page.py beside it): A3 | Michael's | the fit.
pipeline-3d 60c0f1a4 (hands2) merged (1056491c); CODEMAP regenerated; pregate on the box running.

## Gates
- Pregate (box): PASS, 6 moved, 0 blocking (charkit/out/pregate/pregate_tool-accessories6_5da2372b_into_60c0f1a4.md).
- Gate 1 (48e5898d into 59c93f38): FAIL under K, 2 blockers, both mine: acc_star_arms / acc_star_minor remeasured with
  no fresh record (structure() reads every clip face-on in its own frame since 6bcf6e39: the star's too). Fixed: their
  steps (a4fa5426), records refreshed on the build box (guard, as before).
- pipeline-3d 59c93f38 (tool/build2: box choice by CPU load) merged (f7e30919). Note: `remote run` now picks a box by
  load; a run that reads a build must name its box (`remote --box build run ...`).
- **Gate 2: PASS under K** (f5afc94e into 59c93f38, `charkit/out/gate/gate_tool-accessories6_f5afc94e_into_59c93f38.md`):
  nothing blocks; build CPU 1316 -> 1345 s (1.02x); 97 test files, 0 failing; 21 records needed, all good, 0 guard
  findings. Reported: acc_crab_front_iou 0.724 -> 0.713 and three_quarter 0.770 -> 0.698 (PASS -> WARN, -1.5 / -9.3%),
  three_quarter size 1.098 -> 1.131 WARN; flags moved, grades unchanged: art_terminator_hair 2.178 -> 2.134 (the
  gate's own reading), art_peeks_hair 18 -> 22 (FAIL grade both), hair_strokes_front_weight 0.308 -> 0.229 (PASS both).

## Next steps
1. For the coordinator to merge (head f5afc94e plus notes).
2. Michael's A/B on the review page (the crab's place: the drawing's arrangement vs his upper-left with the pincers along
   the bearing); if B: the turn check's target 'pincers along the bearing' (accqa.CRAB_AXIS against a relation
   constant), refit (opt_place declarations in charkit/out/remote/, the ring in tools/acc6/ring.py).
3. Follow-ups: sweep optimize could take constraints against an external reference build (the gate's base: here the
   pick filtered the history by hand); art_peeks_hair and hair_strokes_front_weight read the crab over the bangs.
