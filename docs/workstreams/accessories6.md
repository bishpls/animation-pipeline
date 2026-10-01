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

## Next steps
1. Commit; MEASUREMENT_STEPS for the new checks and acc_*_alone's own frame; store acc_a3_crab on the box.
2. optimize stage adapter `accfit_shape`; fit the crab template on the box; spec; build.
3. Part B.
