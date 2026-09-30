# The shoulders, the sailor collar and the bow (tool/collar)

Michael's review flags of 2026-09-30 on the shoulders, the collar and the bow. Branch `tool/collar` in
`~/animation-pipeline-garments3` (sparse charkit worktree), from pipeline-3d d60486a (the combined garments round).

Scratch harness (session scratchpad `co/`, not tracked): `lib.py` (a bundle's QA labels against the drawn piece
masks, iris or knob registration), `pics1.py BUNDLE` (design | drawn pieces | ours per view, chest window),
`shoulder2.py BUNDLE iris|knobs VIEWS` (the upper garments' top edge per column, and what is above it),
`collarshape.py` (the drawn and our collar's runs per row per view), `cu.py BUILD PREFIX` (chest close-ups of a build's
export with charkit.render: level, orthographic, 400 px/L, 2 s), `qaframe.py BUNDLE OUT iris|knobs` (the whole QA with
the body frame registered on the irises, as built, or on the head's eye line), `qadiff.py A B`, `runpart.py BUNDLE OUT
PARTS` (QA parts on a bundle).

## Measured first

### The eye-line offset: how much of the shoulder gap it is

The body QA (bodyqa.origin, and every piece, skirt, detail and flap check through it) registers our irises' plate
mean on the design's eye row; the garment builders, the hull's placement and the code body use the head's eye line
(`eye_knobs.z` = `eye_z`), 0.0235 L lower (g3_render3: iris mean z - eye_z = 0.02354 L). The face QA (qa3d.eye_anchor)
and the art_* frames (lookqa.HeadFrame) register on eye_z.

- **The shoulder gap:** the back view's upper-garment top edge over |x| 0.25-0.55 L reads 0.0565 L under the drawn one
  (ours -0.566, design -0.510/-0.514). 0.0235 of that is the frame; **0.033 L is geometry**, and a 0.047-0.066 L dip
  sits between the collar's edge and the puffs (the torso's top rows slope down from the neck ring: half-width 0.226
  at the cut, 0.38 at z -0.60, 0.41 at -0.64; the arm tubes start at the shoulder joint, z -0.886).
- **The whole QA under both registrations** (qaframe.py on g3_render3's bundle; the local QA reproduces the box's
  qa.json on every check but hair_folds, whose builder count is box-only): 374 checks unchanged, 98 moved, 8 better,
  7 worse. Better with eye_z: piece_sleeve_cuff_R 0.555 -> 0.803, _L 0.712 -> 0.778, piece_sleeve_R 0.779 -> 0.861,
  the shorts' hems (4 views) WARN -> PASS, body_profile_chest 0.045 -> 0.028, skirt_back_outline FAIL -> WARN. Worse:
  everything tuned by hand or by fit in the iris frame (waistband rows 0.005 -> 0.028 in three views, its profile
  overhang WARN -> FAIL, top_front_opening, piece_bow 0.696 -> 0.659, piece_top, piece_bodice_panel, flap_profile_iou_L)
  and the hair, which is placed by the irises (hair_piece_* 0.02-0.07 lower, body_*_top 0.005 -> 0.028,
  hair_fringe_low PASS -> WARN). The feet read 0.014 L high on the irises, 0.038 on eye_z.
- **Not fixed here (a decision):** a one-place fix is either the QA's registration (bodyqa.origin on eye_z: the
  hull-built pieces then read as built, but the band's rows, the bow's lift, the jacket's hang and opening, the skirt
  fit and the hair's iris placement were all tuned in the iris frame and would need refitting) or the builders' eye
  line on the irises (the hull, the code body and every garment 0.0235 L up against the head: the neck 0.0235 L
  shorter at tool/face's join). Both reach well beyond this round. This round builds and measures in the QA's current
  frame; the shoulders are raised by the geometry share (0.033 L plus the dip), not the frame's.

### The new checks (charkit/collarqa.py, part `collar_flags`, order 1760; 89bb724, steps d3205d5)

Each flag check carries its flag (registry.flag_check: the gate blocks its regressions). Calibration: every measure
compares ours with the design measured the same way, so the design reads 0 (IoU 1) against itself; the flagged build is
g3_render3 (pipeline-3d's garments merge, e66abc8's render):

| check | what | limits (pass / warn) | g3_render3 |
|---|---|---|---|
| shoulder_back_line | the upper garments' top edge over |x| 0.25-0.55, median vs the design's | 0.015 / 0.03 L | 0.0565 FAIL (ours -0.566, design -0.510) |
| shoulder_back_slope | its fitted slope vs the design's: a guard, not a flag check (the dip and the puffs' rise cancel on the flagged build) | 0.10 / 0.20 | 0.079 PASS |
| collar_back_iou | the back panel vs the drawn one, both closed | >= 0.80 / 0.65 | 0.754 WARN |
| collar_back_square | the panel's width 90% down over 50% vs the design's | 0.08 / 0.15 | 0.345 FAIL (0.588 vs 0.933) |
| collar_back_lay | the trough in the garments' top edge beside the panel | 0.01 / 0.02 L | 0.047 FAIL |
| bow_front_loop_end | the straight share of each loop's outer end | 0.15 / 0.30 | 0.593 FAIL (0.81 vs 0.22) |
| bow_front_loop_width | the loops' span: a guard (the bow is sized to the drawn span) | 0.06 / 0.12 | 0.0 PASS |
| bow_front_bleed | L of the bow's edge on the jacket with no line, drawn with the build's outlines | 0.03 / 0.06 L | 0.378 FAIL (design 0.0) |
| bow_profile_ribbon | the ribbons' width seen in profile vs the design's | 0.25 / 0.5 | 0.868 FAIL (0.024 vs 0.179 L) |

The puffs (flag 3): on g3_render3 art_points_sleeves 0 PASS, art_bumps_sleeves 0 PASS and every sleeve_*_spikes 0 PASS:
the spiky shoulders were the hull sleeves (fixed by garments2's template puffs). What remains at the shoulders is the dip
and the height (above).

### What forms the shoulder line (back view, g3_render3)

Per column, the topmost garment: |x| 0.25-0.35 the collar (its rounded flap's edge falling -0.52 -> -0.62), 0.40-0.55
the puff (its top -0.557..-0.594). The jacket never reaches the silhouette there. So raising the body alone moves
nothing (variant s1: the torso's top rows widened to 0.43-0.47 L, every check within 0.01): the collar must lie flat
out to the shoulder, and the puffs' tops rise ~0.05 L.

### The segmentation (flag 4), measured

The authored body is a torso (a radial loft from the neck cut) and limb tubes; each arm tube starts at its shoulder joint
(x 0.544, z -0.886), capped there by a fan, and meets the torso's side (half-width 0.41 at z -0.64..-0.83) under the
puff. Visible skin within z -0.45..-1.0 at |x| > 0.3 on g3_render3's QA labels (seg.py): front 0 px, back 0 px (the
jacket and the puffs cover the join in both), three-quarter 81 px and profile 385 px (the upper arm below the cuff and
the neck's back, not the join). So the join itself is not what reads as segmented: the look is the garments' shoulder
(the collar's flap falling to -0.62, the dip, then the puff standing up to -0.56: collar_back_lay 0.047), which the
template shoulders, collar and puffs address. Restructuring the body (a continuous torso-and-arm cage through the
shoulder, as the head's neck zip joins the head) is not needed for these flags; it would be for a posed arm (raised
arms open the join under the puff), about a round's work: a zip between the torso's side rings and the arm's top ring
(code_base's arc-length zip), the weights blended across it.

### Variants (on the evaluator, spliced into g3_render3's bundle: var.py)

The harness reproduces the box's checks on the unchanged spec (v_base: every piece, sleeve, collar and bow check equal)
except bow_front_bleed (1.34 against the box's 0.378: the splice drops Blender's outline shrink, so the bleed's line
hull differs; compare variants with v_base there, not with the box).

| variant (evaluator, spliced) | shoulder_back_line | collar_back_iou | _square | _lay | collar_front_torn | sleeve_back_profile_L |
|---|---|---|---|---|---|---|
| v_base (as built) | 0.0565 FAIL | 0.754 WARN | 0.345 FAIL | 0.047 FAIL | 0.0023 PASS | 0.068 FAIL |
| s1: body.shoulder {z -0.525, x 0.47, round 0.05, hold 0.05, fall 0.15} | 0.0565 | 0.758 | 0.349 | 0.038 | 0.0072 | 0.068 |
| c1: s1 + the template collar (outline + stripe) | 0.0612 FAIL | 0.799 WARN | 0.113 WARN | 0.019 WARN | 0.0427 FAIL | 0.069 |
| **c1p2: c1 + the puffs' table one station up (t -0.30, the first station's extents)** | **0.0235 WARN** | 0.790 WARN | 0.113 WARN | **0.0094 PASS** | 0.0719 FAIL | 0.065 FAIL |

The puffs' tops, 0.05 L under the drawn line, and the collar's rounded flap made the line; the body's shoulder top
under them makes the collar lie flat out to the puffs. The remaining 0.0235 L is the eye-line frame (above): the
shoulders' top sits at the neck cut (-0.525 L against the cut's -0.52: the torso can't rise above its neck ring,
tool/face's join), and the drawn line is 0.0235 L higher in the QA's iris frame than in the builders'.
collar_front_torn regressed (a new FAIL): in front the template collar shows as a thin band along the shoulders' top
and a patch of the jacket stands at the neck between the lapels (the design shows skin in the V there). Next (spec D):
the collar's region up the neck as the jacket's (0.6 of the neck bone), cut at eye -0.43 L, and the jacket's opening
carrying the collar's V above the bib's (the V shows the skin).

**The template collar** (garments.build: kind 'collar', `source: template`; COLLAR_TEMPLATE's region and offset): a
shell of the neck's base, shoulders and upper back and chest, cut to garments2's outline (outline_dist: the lapels
between the V and an outer edge in front, the square back panel to its bottom) with its stripe a second material. The
spec keeps kind 'collar' and names no region: the outfit masks' and hull's stamps read the garments' kinds and region
bones, and a kind 'shell' restamped them (the box rebuilt both: killed). Outline heights are the builders' (eye_knobs),
the drawn ones +0.0235 L.

**Box variants (build box, specs `charkit/spec/_v_*.json`, untracked):** A = c1p2 + the bow's loops closed (end 0.2) +
the ribbons stood 0.05 L off and turned 40 degrees; B = A with the puff's cap 0.17 instead of the extra station; C = A
without the template collar; D = A with the collar up the neck and the jacket's V (above). Outputs charkit/out/cv_*.

## Box variants (build box, g3_render3 = before)

| check | g3_render3 | A | B | C | D | E |
|---|---|---|---|---|---|---|
| shoulder_back_line | 0.0565 FAIL | 0.0235 WARN | 0.0329 FAIL | **0.0188 WARN** | 0.0235 WARN | 0.0235 WARN |
| collar_back_iou / _square / _lay | 0.754 / 0.345 / 0.047 | 0.791 / 0.113 / **0.009** | 0.795 / 0.113 / 0.014 | 0.747 / 0.349 / 0.047 | 0.793 / 0.12 / 0.009 | = D |
| bow_front_loop_end / bleed / ribbon | 0.593 / 0.378 / 0.868 | 0.059 / 0.033 / 0.526 | = A | = A | 0.059 / **0.0** / 0.526 | = D |
| piece_collar | 0.771 PASS | 0.646 WARN | 0.644 | 0.771 | 0.638 | 0.638 |
| collar_front_torn / _profile_torn | 0.002 / 0.0 PASS | 0.039 / 0.035 FAIL | 0.008 WARN / 0.012 FAIL | 0.004 / 0.0 | 0.037 / 0.025 FAIL | = D |
| art_outline_collar (flag) | 0.743 PASS | 3.589 WARN | 3.509 WARN | 1.366 PASS | 2.321 WARN | = D |
| art_speckle_neck (flag) | 2.602 WARN | 1.954 | 1.904 | 2.636 | 2.245 | 2.245 |
| neck_crease | 26.9 WARN | 39.1 FAIL | 39.1 FAIL | 32.7 FAIL | 92.6 FAIL | 92.6 FAIL |
| hair_noise | 0.0767 WARN | 0.0804 FAIL | | 0.0808 FAIL | | 0.0807 FAIL |

A = the shoulders template {z -0.525, x 0.47} + the template collar (region: the neck to 0.3 of its bone) + the puffs one
station up + the bow's loops closed (end 0.2) + its ribbons (stand 0.05, turn 40); B = A with the puff's cap 0.17 for the
station; C = A with the hull collar; D = A with the template collar up the neck (0.6, cut eye -0.43) and the jacket's
opening carrying its V; E = D with the hair's body_clear_garments 0.035 (identical to D: the specks are lock 0's tip at
the collar's corner, not the hair inside a garment; 15fd2cd, default 0, left in).

Read: the bow and the puffs are clean wins (every variant). The shoulders template raises neck_crease to FAIL (a
shelf 0.21 L wide right under the neck ring: the crease between the neck and the shoulders' top) and the hair's noise
over 0.08 (the hair rebuilt over the new shoulders); the template collar fixes the back (square, the lay) but FAILs the
front and profile torn checks and regresses art_outline_collar (a flag check) and piece_collar (its front and
three-quarter: in front the shoulders' top sits at the neck cut, so the drawn lapels over the shoulders, 0.0235 L higher
still in the QA's frame, have no body to lie on; the collar shows as a thin band there). Under K each of those blocks.

**Taken into the specs (5ffd446):** the bow's `end` 0.2 and ribbon {stand 0.05, turn 40}; the puffs' table one station up.
**Built, not in the spec:** body.shoulder (code_body.shoulders), the template collar (kind collar, source template),
the jacket's V opening; their variants' specs are reproducible with the scratch mkspec.py from the knobs above.

## The gate (5ffd446 into pipeline-3d 25b1936): FAIL under K, one blocker

Report `charkit/out/gate/gate_tool-collar_5ffd446_into_25b1936.md`. pipeline-3d 25b1936 merged first (a4e84b4: clean;
tool/infra-auth's service account, tool/evalmesh M2+M3). **Blocking:** art_outline_collar 0.743 PASS -> 3.873 WARN (a
flag check: the torn collar tips, look_v5). The collar is the hull collar, unchanged; what moved is round it: the
puffs one station up meet its flap's side over the steep shoulders (variant C, the same garments on the shoulders
template, read 1.366 PASS; look4 measured this check's cross-box noise at 4.44-5.68 for one commit). Reported, not
blocking: sleeve_front_profile_R and sleeve_three_quarter_profile_L PASS -> WARN (the puffs' new top), the new checks
that FAIL (collar_back_lay 0.0565, collar_back_square 0.345, bow_profile_ribbon 0.526: measuring the known faults the
template collar would fix), bow_front_tail_width 0.308 -> 0.462 (FAIL both: the ribbons turned 40 degrees), art_*_bow
INFO moves (the closed loops: terminator 8.4 -> 0, fragments 1.8 -> 0.8, points/bumps 0 -> 16/15). Better:
bow_front_loop_end 0.593 -> 0.059, bow_front_bleed 0.378 -> ~0.03, shoulder_back_line 0.0565 -> ~0.03 (the puffs),
bow_front_tail_gap WARN -> PASS, sleeve_profile_profile_L FAIL -> WARN, piece_bodice_panel 0.899 -> 0.939,
body_profile_chest 0.045 -> 0.035.

**For the coordinator:** accept art_outline_collar (the collar untouched; the check noisy across boxes), or drop the
puffs' extra station (one spec line: sleeve_L.profile's first row) and re-gate: the bow's fixes alone don't touch the
collar's outline region's corners... (unverified: not rebuilt this round).

## Open, in order (next round)

1. The eye-line frame (Michael's decision, above): with the QA on the head's eye line the shoulders template's line
   reads within 0.015 L; in the iris frame it can't pass without the torso rising above the neck cut.
2. The template collar (built, variant D): fix its front (the lapels over the shoulders need a surface above the cut:
   the collar standing off the body there, or the shoulders' top above the neck ring, tool/face's join) and the
   neck crease under it (the shelf under the neck ring: a larger `round`, the neck ring's own rows); then its
   art_outline_collar and piece_collar front/three-quarter.
3. The shoulders template's neck_crease (26.9 -> 32.7 FAIL) and hair_noise (0.077 -> 0.081 FAIL, the hair rebuilt
   over the new shoulders).
4. art_speckle_neck (flag 5): unchanged on the hull collar (2.60); the template collar moves it to 1.90-2.25 (still
   WARN). The hair's body_clear_garments (15fd2cd) doesn't reach it: the specks are lock 0's tip at the collar's
   corner in profile, not the hair inside a garment.
5. bow_profile_ribbon 0.526 FAIL: the ribbons need their faces turned further to the side (turn 60-90) with the front
   width kept (`w`), fitted against bow_front_tail_width and piece_bow per view.

## End of round: the render build and the review page

Render-box build of the head (5ffd446, boards body): `charkit/out/co_render`. Against g3_render3: shoulder_back_line
0.0565 FAIL -> 0.0188 WARN, bow_front_loop_end 0.593 FAIL -> 0.059 PASS, bow_front_bleed 0.378 FAIL -> 0.0325 WARN,
bow_profile_ribbon 0.868 -> 0.526 FAIL, collar_back_square 0.345 FAIL (unchanged: the hull collar), **collar_back_lay
0.047 -> 0.0565 FAIL (worse: the puffs' tops rose beside the unchanged flap, deepening the trough; the lay needs the
template collar and the shoulders together, variant A/D 0.009 PASS)**, art_speckle_neck 2.606 (unchanged),
art_outline_collar 3.873 WARN (the gate's blocker, the render box agrees), neck_crease 26.9 (unchanged),
art_points_sleeves 0 PASS.

Review page: `charkit/out/collar_review/index.html` (design | before g3_render3 | after co_render | option D, close-ups
by charkit.render at the QA's registration, the back, the bow zoomed, the profile, the neck junction; every check whose
status moved; the generator and harness copied beside it).

## Round 2 (second agent): milestones M1 bow, M2 eye-line frame, M3 template collar

The coordinator's plan: M1 lands the bow alone (branch `tool/bow` from pipeline-3d 25b1936, without the puffs' extra
station that broke art_outline_collar), with the ribbons in profile fitted to PASS; M2 fixes the eye-line frame in one
place; M3 the template collar D and the squared shoulders on M2. Harness (session scratchpad `co/`, untracked):
`var.py` (as round 1; zsh doesn't split a `$VAR` of flags, pass them literally), `pics1lib.py` (the drawn bow and tails
against ours per view: red drawn only, blue ours only, purple both, grey our jacket), `prof.py` (per profile row over the
drawn tails: their front and back, ours, and the drawn jacket's front, against our jacket's front), `tab.py`.

### M1: tool/bow

b581df9, c176f07 (collarqa, its steps: cherry-picked), dbcdd1c (the bow half of 73e2d03: `end`; code_body's
shoulders left on tool/collar), then the specs' bow lines (end 0.2, ribbon stand 0.05 turn 40; no puff station). The
harness reproduces the box on the bow's checks on this spec (bow_profile_ribbon 0.5263, bow_front_tail_width 0.4619,
piece_bow 0.672: front 0.755, three-quarter 0.637, profile 0.521); shoulder_back_line back to 0.0565 (the puffs as on
pipeline-3d), collar_back_lay 0.0471 (pipeline-3d's value).

**The ribbons in profile, fitted (harness, co_render's bundle; the ribbon's `w` sizes, `stand` L, `turn` degrees):**
the drawn ribbons read 0.184 L wide in front and 0.179 L in profile, ours 0.099 and 0.085 (turn 40): a flat ribbon
matching both is about twice as wide at about 45 degrees. prof.py: the conform puts the ribbons' mid-plane on our
jacket's front, so a turned ribbon's back half sinks into the jacket unless it stands off by about half its turned
depth; and the drawn ribbons span from 0.10 L behind our jacket's front to 0.06-0.10 L in front of it (the drawn
jacket's visible front, below them at z -1.17..-1.22, sits 0.04-0.05 L behind ours: our jacket fills part of the
ribbons' drawn depth). So a ribbon wide enough in profile trades the bow's profile IoU: ours can only show in front of
our jacket.

| variant | ribbon | profile_ribbon | front_tail_width | tail_gap | piece_bow (front / 3q / profile) |
|---|---|---|---|---|---|
| vb (spec as committed) | stand .05, turn 40 | 0.526 FAIL | 0.462 FAIL | 0.005 PASS | 0.672 WARN (0.755 / 0.637 / 0.521) |
| r1 | .05, 44, w [.25,.425] | 0.276 WARN | 0.231 WARN | 0.089 FAIL | 0.675 (0.779 / 0.660 / 0.422) |
| r3 | .10, 44, w [.25,.425], out .285 | 0.013 PASS | 0.039 PASS | 0.005 | 0.736 (0.873 / 0.743 / 0.342) |
| s0.00 / s0.03 / s0.06 (r3's, stand) | 0 / .03 / .06 | 0.579 / 0.408 / 0.211 | 0.539 / 0.385 / 0.180 | 0.005 | 0.652 / 0.689 / 0.731 (profile 0.531 / 0.481 / 0.437) |
| **gb (taken)** | **.07, 40, w [.27,.45], out .30** | **0.092 PASS** | **0.0125 PASS** | **0.0 PASS** | **0.754 PASS (0.856 / 0.764 / 0.446)** |
| gc | .08, 44, w [.25,.425], out .285 | 0.053 PASS | 0.077 PASS | 0.005 | 0.751 (0.867 / 0.761 / 0.404) |

`out` 0.30 keeps the gap between the tails (a wider ribbon's inner edges move in). The bow's profile IoU 0.521 -> 0.446
is the cost; restoring it is the jacket's front under the ribbons (profile), not the bow.

pipeline-3d moved twice during M1 (9a12d01 tool/look6, 6ddcb5b evalmesh M4); tool/bow rebased onto 6ddcb5b (no
conflicts; the steps file names the rebased collarqa commit, a12f99d: the gate matches steps by ancestry). Pre-gate
(`charkit/out/pregate/pregate_tool-bow_5629e58_into_6ddcb5b.md`): PASS under K, 26 moved, 0 blocking;
body_profile_chest 0.045 WARN -> 0.024 PASS; the evaluator's bodice-panel rows move (the wider ribbons cover more of the
panel: its three-quarter top -0.085 -> -0.160 WARN, its profile rows gone, hidden behind the ribbons).

**Gate 1 (5ce7954 into 9eba0b0): FAIL under K, one blocker** (`charkit/out/gate/gate_tool-bow_5ce7954_into_9eba0b0.md`):
art_outline_collar 0.743 PASS -> 2.193 WARN, without the puffs. Improved: bow_front_tail_width 0.308 FAIL -> 0.0125
PASS, bow_profile_ribbon 0.868 -> 0.092 PASS, bow_front_loop_end 0.593 -> 0.059 PASS, piece_bow 0.696 WARN -> 0.754
PASS, bow_front_tail_gap WARN -> PASS, body_profile_chest WARN -> PASS. But bow_front_bleed 0.3425 FAIL (round 1's
narrower ribbons 0.0325; pipeline-3d's bow 0.3775).

**art_outline_collar is a corner count** (box builds bw_e0/p3/p4, the gate's flags; corners.py on their bundles): the
collar's visible outline in front is two small pieces above the loops, 1.34 L long, so each corner is 0.745 (limits
1.5 / 2.5 on the design's 0.84: 2 corners PASS, 3 WARN). One corner is at every build's right collar tip at the neck
(x 0.187, z -0.47); the round caps add one at each collar piece's outer bottom end (x -0.352, z -0.614), where the
collar's edge meets the loop's top edge: a round cap drops the loop's top there (0.035 L at p2, 0.024 p3, 0.020 p4,
from the lobe's own taper plus the cap). Box: end 0 (open) 0.745 PASS, loop_end 0.593 FAIL; p2 (the gate) 2.193 WARN,
0.059 PASS; p3 1.48 PASS (2 corners), 0.215 WARN; p4 0.743 PASS, 0.316 FAIL. No single power passes both, so
`end_p` [upper, lower] (5fded59: the powers at the section's top and bottom, blended round it; the drawn loops'
upper outer corners are square, their lower ones round): the top as p4's (no corner), the bottom round. Harness
loop_end: [4,2] 0.186 WARN, [5,2] 0.222, [4,1.6] 0.143 PASS, [6,1.6] 0.200.

**The bleed** (bleedpic.py on bw_p3): the widened ribbons, turned about their middle, sink their outer edges onto the
jacket (0.107 L back at the ends against 0.07 of stand): no line along them there (rows 240-320 of the bleed frame).
Round 1's narrow ribbon kept its outer edge ~0.008 L clear. `ribbon.hinge` (0..1): each row forward by that share of
its turned half-depth (1: the outer edge on the wrap; `stand` then its clearance), the front view unchanged.

**Box builds of the fix (the merged tree, pipeline-3d 3ebc3fb):**

| check | gate 1 candidate | v1 (taken) | v2 |
|---|---|---|---|
| bow: end_p / ribbon | 2 / stand .07, w [.27,.45] | [4, 1.4] / hinge 1, stand .015, w [.25,.415] | = v1, stand .03 |
| art_outline_collar (flag) | 2.193 WARN | **0.742 PASS** (1 corner, base's) | 0.742 PASS |
| bow_front_loop_end | 0.059 PASS | 0.121 PASS | 0.121 PASS |
| bow_front_bleed | 0.3425 FAIL | **0.0325 WARN** | 0.035 WARN |
| bow_profile_ribbon | 0.092 PASS | 0.079 PASS | 0.053 PASS |
| bow_front_tail_width / gap | 0.0125 / 0.0 PASS | 0.0 / 0.014 PASS | = v1 |
| piece_bow (front / 3q / profile) | 0.754 PASS | 0.735 WARN (0.867 / 0.746 / 0.341) | 0.719 (… / 0.715 / 0.314) |
| art_fragments_collar (flag) | 4.917 WARN | 4.741 WARN | 4.693 WARN |
| art_speckle_neck (flag) | | **1.34 PASS** (tool/hairtag's masks, as the coordinator said) | 1.34 |
| hair_noise | | 0.0785 WARN | 0.0785 |

The cost: the bow's profile IoU (pipeline-3d's 0.52 -> 0.34): our ribbons now show their face in profile clear of
the jacket, as drawn, but our jacket's front under them sits up to 0.10 L forward of the drawn ribbons' back edges (the
drawn jacket's visible front below them 0.04-0.05 L behind ours), so they stand forward of the drawn ones. The fix is
the jacket's front in profile under the ribbons (a decision; not this milestone). piece_bodice_panel's profile view
0.139 (the panel behind the ribbons in profile; the check overall 0.927 PASS, base 0.899).

**Gate 2 (cbca3ad into pipeline-3d 3ebc3fb): PASS under K** (`charkit/out/gate/gate_tool-bow_cbca3ad_into_3ebc3fb.md`;
pre-gate PASS, 21 moved, 0 blocking). Flag checks: art_outline_collar 0.743 -> 0.742 PASS, art_fragments_collar 4.69
-> 4.741 WARN (grade FAIL both). Improved: bow_front_tail_width 0.308 FAIL -> 0.0 PASS, bow_front_tail_gap 0.033 WARN ->
0.014 PASS, body_profile_chest 0.045 WARN -> 0.013 PASS, piece_bow 0.696 -> 0.735 WARN, piece_bodice_panel 0.899 ->
0.927. New: bow_front_loop_end 0.121 PASS (old geometry 0.593 FAIL), bow_profile_ribbon 0.079 PASS (0.868 FAIL),
bow_front_bleed 0.0325 WARN (0.3775 FAIL); collar_back_lay/_square and shoulder_back_line FAIL as on pipeline-3d
(M2/M3's). PASS -> WARN: collar_three_quarter_torn (roughness 0.0; one collar fragment in three-quarter beside the
ribbons, design 0). INFO: art_points_bow 0 -> 25.2 and art_spikes_bow 0.014 -> 0.024 (the caps' corners and the
ribbons' ends), art_terminator_bow 8.4 -> 0, art_fragments_bow 1.8 -> 0.13. CPU 1.11x.

Open after M1: the jacket's front in profile under the ribbons (the bow's profile IoU 0.52 -> 0.34); the collar
fragment in three-quarter; bow_front_flare 1.005 FAIL (unchanged: the drawn loops flare to tall ends, ours are pillows;
the `wing` template exists, not taken).

### Handoff after M1 (tool/bow merged into pipeline-3d cf8994d; the second agent stops here)

**Harness** (untracked, copied from the session scratchpad): `charkit/out/collar_round2/harness/` (var.py splices the
evaluator's garments into a box bundle: `python var.py OUT --base charkit/out/co_render --set garments.bow.KEY=JSON
--parts collar_flags,sheet_pieces,piece_details [--pics]`, 60-90 s; it reproduces the box's piece, bow-shape and
collar_flags checks but NOT bow_front_bleed or art_* (no Blender outline shrink, a pre-M4 base bundle): measure those on
box builds, `python -m charkit remote build SPEC --out charkit/out/NAME --boards '' --no-blend`, ~6 min, several at
once staggered 75 s). corners.py BUILD... (art_outline_collar's corners, positions and a picture), bleedpic.py BUILD...
(where the bow touches the jacket with no line), prof.py VARIANT... (profile depths per row: drawn ribbons, ours, the
jacket). Pictures of this round beside it. Box builds of the round: charkit/out/bw_{e0,p3,p4,v1,v2} (v1 = the merged
bow).

**M1 result** (gate `charkit/out/gate/gate_tool-bow_cbca3ad_into_3ebc3fb.md`, PASS under K): above. Lessons for M3:
art_outline_collar is a corner count on a short outline (front: 1.34 L, 0.745 per corner; PASS <= 2 corners), so any
change where another piece meets the collar's visible edge moves it a whole step; locate corners with corners.py
before guessing. The harness can't see art_* or the bleed.

**M2: the eye-line frame, scoped (not started).** The body QA registers our irises' mean z on the design's eye row:
`bodyqa.origin(view, az, iris, centre)` takes `ez = mean(iris[:, 2])`, and every piece, skirt, detail, flap and
collar_flags check goes through it (pieceqa.our_labels, lib.our_labels). The builders take the head's eye line from the
assembly, `A['eye_z']` (= eye_knobs.z): garments.py (8 uses: the drawn outline heights, drawn_extent's placement), the
hull's placement, code_body, hair (3), geom/parts (3), bodyeval (3); the face QA (qa3d.eye_anchor) and the art frames
(lookqa.HeadFrame) also use eye_z. Offset: iris mean z - eye_z = 0.02354 L (g3_render3). The one-place fix the
coordinator asked for: the garment builders' frame on the irises (one assembly value, e.g. the irises' mean z, read
where the garments place drawn heights), not per garment. Expect (round 1's qaframe.py table, read in reverse): the
hull-built pieces improve (piece_sleeve_cuff_*, piece_sleeve_R, the shorts' hems, body_profile_chest,
skirt_back_outline, shoulder_back_line: ~0.0235 of its 0.0565), and whatever was tuned by hand in the iris frame to
compensate regresses by the offset and needs refitting (the waistband's rows and its profile overhang, the bow's
`lift` 0.03, the jacket's hang and top_front_opening, the bodice panel, the skirt fit, flap_profile_iou_L). The torso
can't rise above the neck ring (tool/face's join at the neck cut, -0.52 L): decide whether the body moves with the
garments (the neck 0.0235 L shorter) or only the garments do. Measure every garment check before and after (a
build of pipeline-3d as it stands is the before); refit with each piece's shape IoU in all views; gate alone.

**M3: plan (on M2).** Code for it lives on tool/collar, not in pipeline-3d: code_body's shoulders template
(`body.shoulder`, 73e2d03's code_body/bodypage/cli part and tests/test_shoulders.py), the template collar (ed2ddbd,
garments kind 'collar' source 'template'), the jacket's V opening (variant D), hairpieces' body_clear_garments
(15fd2cd, default 0). Don't merge tool/collar whole: its specs carry the old bow lines and the puffs' extra station, and
its steps file names 89bb724 (pipeline-3d's names a12f99d); branch from pipeline-3d after M2 and cherry-pick those
code commits. Variant D's knobs: round 1's table above and mkspec.py. Then:
- D's new FAILs: neck_crease (26.9 -> 92.6: the shelf under the neck ring; a larger `round`, the ring's own rows),
  hair_noise (now 0.0785 WARN on pipeline-3d with 0.0015 of margin, tool/hairtag's masks; only the lowest lock-0
  junction is ours), collar_front_torn / collar_profile_torn (the lapels over the shoulders need a surface above the
  neck cut), piece_collar front/three-quarter; art_outline_collar under D (count its corners).
- art_speckle_neck: 1.34 PASS on pipeline-3d (tool/hairtag's masks; box build bw_v1): verify under D.
- The puffs' raised station (tool/collar 5ffd446's sleeve_L.profile first row, t -0.30) meeting the square collar.
- **The jacket's front in profile under the ribbons**: prof.py on the bow: the drawn ribbons' back edges reach 0.10 L
  behind our jacket's front at z -0.94..-1.17, and the drawn jacket's visible front below them (z -1.17..-1.22) sits
  0.04-0.05 L behind ours: the jacket (hull-built) fills the ribbons' drawn depth. A profile refit of the jacket's front
  there restores the bow's profile IoU (0.52 -> 0.34 with the ribbons standing clear, as drawn) and should not cost
  piece_top's profile (0.534 now); measure top_front_opening and body_profile_* with it.
- The collar fragment in three-quarter beside the ribbons (collar_three_quarter_torn PASS -> WARN in M1's gate).
- Review page for Michael: design | before | after, the back view, the bow close-up, the profile (round 1's
  review.py in charkit/out/collar_review/ builds one).

## Round 3 (third agent, branch tool/collar3 from pipeline-3d 0744ffe): M2 the garments' frame, M3 collar D + shoulders

Harness: `charkit/out/collar_round3/harness/` (untracked): round 2's, with var.py's `--frame knobs` (the builders' old
frame, monkeypatched, to measure both frames from one tree; default base bw_v1, `--quiet`), `qadiff.py A B` (a build's
qa.json or a var output's res.json: every moved check), `../irisz.py BUILD` (the assembly's iris plates' mean z against
eye_z, and the bundle's). Before build (box): `charkit/out/c3_before` (0744ffe as it stands).

### M2: the garment builders' eye line on the QA's frame

The coordinator's decision: only the garments' frame moves; the body (code body, hull fit, the face) keeps eye_z.
Measured (irisz.py on bw_v1): the assembly's iris plates' mean z = the bundle's to 1e-9, eye_z + 0.02354 L.
The one place: `garments._eye_z(A)` = the iris plates' mean z (knob line only without irises), which every drawn
height in the builders now reads (the `eye` cuts, opening_cut, outline_dist, the drape's `from`, the lofts' `rows`,
drawn_extent), and `garments.hull_target(A, shape)` (i3d.eye_target with eye_anchor 'iris', as the hair pieces
already align) for the hull's pieces (hull_pieces) and flapchains.chains' mapping into the graph's frame.

**Measured (harness, bw_v1's bundle; k0 = the old frame, i0 = the new frame alone, r* = refits; `qadiff.py`).** The
frame alone (i0 against k0, 139 of 263 harness checks moved): better, the hull-built pieces now read as built:
piece_sleeve_cuff_L 0.712 WARN -> 0.790 PASS, _R 0.544 -> 0.782 PASS, piece_sleeve_R 0.777 -> 0.835, piece_shorts 0.601
-> 0.701, the shorts' hems in four views WARN -> PASS, front_hem and three_quarter_hem WARN -> PASS, skirt_back_outline
FAIL -> WARN, piece_skirt 0.869 -> 0.885, sleeve_profile_rough_L WARN -> PASS. Worse, the knobs tuned in the old frame:
the waistband's rows 0.0047 -> 0.0282 (three views PASS -> WARN; piece_waistband 0.907 -> 0.803), piece_bow 0.735 ->
0.699, the flaps' tails 0.0235 L shorter against the drawn (flap_profile_iou_L/R PASS -> WARN), the wrist cuffs
(cuff_front_flare_L WARN -> FAIL: the hull's cuff now sits 0.0235 L up our forearm), shoulder_back_slope PASS -> WARN
(a guard; M3's shoulders), collar_front_torn PASS -> WARN.

Refits (each against its piece's IoU in all views):
- waistband `rows` -0.0235 (the band's placement against the drawn band), `fit_rows` kept (the hull's rows its section is
  measured on: shifting them too, r1, sampled the hips and widened it, waistband_front_width PASS -> WARN).
- bow `lift` 0.03 -> 0.0065 (the drawn extent now in the right frame): piece_bow 0.735 WARN -> 0.754 PASS (0.843 / 0.699
  / 0.303 per view before the lift; bow_front_tail_width 0.0, bow_profile_ribbon 0.0789 -> 0.0526).
- the flaps' tails `first` 0.18 -> 0.2035 (their treads hang below the skirt's hem, which rose with the hull):
  flap_profile_iou_L/R back to PASS (0.71), flap_front_iou 0.73/0.75 -> 0.78/0.79.
- the wrist cuffs: `bell` (new, band_hull: the top rows grown by `bell` L tapering to 0 at the bottom; the drawn cuffs
  flare 1.22, ours 1.04-1.08) 0.015: every cuff flare better than before (front_L 0.138 WARN -> 0.102 WARN, back_L PASS,
  front_R 0.178 FAIL -> 0.147 WARN, back_R 0.196 -> 0.155 FAIL); piece_cuff_L 0.779 PASS -> 0.733 WARN (the frame's
  cost mostly: 0.75 without the bell), piece_cuff_R 0.565 -> 0.586. 0.03 flares all PASS/WARN but costs the IoU more and
  pushes the skirt (clear_hands): front_skirt_aline FAIL. (A first name, `flare`, collided with the boot cuffs'
  template key and moved them: renamed.)
- Insensitive, left as drawn: the jacket's opening and drape `from`, the bodice panel's eye cut (shifting them -0.0235
  moved piece_top and piece_bodice_panel by <= 0.001).

**Box (c3_before = bw_v1 on all 496 checks; c3_m2 = 9c99e44):** the harness's reading held; plus bow_front_bleed
0.0325 WARN -> 0 PASS, art_speckle_neck 1.34 -> 0.833 PASS, art_outline_collar 0.742 -> 1.381 PASS (flag; grade PASS),
art_fragments_collar 4.741 -> 6.338 WARN (flag; grade FAIL both), hair_noise 0.0785 -> 0.0791 WARN (0.0009 of margin).

**M2 gate (9c99e44 into pipeline-3d 0744ffe): PASS under K** (`charkit/out/gate/gate_tool-collar3_9c99e44_into_0744ffe.md`;
pregate PASS, 188 moved, 0 blocking): no new FAIL, no flag-check regression, CPU 0.97x; PASS -> WARN: piece_cuff_L
0.779 -> 0.733, shoulder_back_slope 0.08 -> 0.102 (a guard). shoulder_back_line stays 0.0565 FAIL: its top edge is the
puffs (template, on the body's bones) and the hull collar's flap; M3's.

**Merged pipeline-3d 2f42155 (tool/infra5)** into tool/collar3 (b361654): conflicts in garments.hull_pieces and
flapchains.chains resolved keeping both (hull_target for the frame, target3d for i3d's rename; no_loose untouched).
Not carried (`gate --carry`: the baseline's manifest and the candidate's code moved); gated on the box (below).

### M3: variant D on M2's frame (box builds c3_D3 = D, c3_D3np = D without the puffs' station)

mkD.py (harness) writes D on the new frame: body.shoulder {z -0.525, x 0.47, round 0.05, hold 0.05, fall 0.15}; the
template collar with every outline height round 1 raised by 0.0235 back at the drawn one (front V -0.48..-0.68, back
bottom -0.905 = the design's), its cut up the neck at eye -0.4535 (the same world height); the jacket's opening with the
collar's V above its own rows; the puffs' station (sleeve profile t -0.30). D3 reproduces round 1's D (same geometry):
against c3_m2, better shoulder_back_line 0.0565 FAIL -> 0.0235 WARN, collar_back_lay 0.0424 FAIL -> 0.0094 PASS,
collar_back_square 0.345 FAIL -> 0.12 WARN, collar_back_iou 0.747 -> 0.793, piece_top 0.714 WARN -> 0.771 PASS,
art_fragments_collar 6.34 -> 3.62, art_speckle_neck 0.833 -> 1.08 PASS, hair_noise 0.0791 -> 0.0782; blocking under K:
neck_crease 26.9 WARN -> 92.6 FAIL, collar_front_torn 0.0031 -> 0.0197 FAIL, collar_profile_torn 0 -> 0.0252 FAIL,
shoulder_back_slope 0.102 WARN -> 0.249 FAIL, art_outline_collar 1.381 PASS -> 3.818 WARN (flag); also piece_collar
0.756 -> 0.639 WARN, sleeve_front_profile_R / sleeve_three_quarter_profile_L PASS -> WARN. Without the station (D3np)
shoulder_back_line 0.0612 FAIL, collar_back_lay 0.0188 WARN, art_outline_collar 2.227 WARN: the station is needed.

**neck_crease located (crease.py):** not a crease in the surface. On D3 the masked skin has no vertices from the cut to
+0.04 L round the front (columns +-15 degrees): the neck there is hidden under the template collar, and the measure's
per-height maximum radius jumps from the jaw's underside (r 0.30 L) to the chest in the V (0.31-0.42 L), a 92.6 degree
"bend". Why the neck is hidden: outline_dist splits front from back at the chest bone's head (`front_of` 'chest'); the
whole neck lies behind that plane, so it reads as the back panel (half-width 0.4) and the collar (and its skin mask)
wraps the neck. Variants c3_D4 (collar outline `front_of` 'neck') and c3_D5 (D4 + the jacket's opening `front_of`
'neck') test the split at the neck's own plane.

**The split at the neck (box c3_D4: the collar's outline `front_of` 'neck'; c3_D5: + the jacket's opening):** against D3,
neck_crease 92.6 -> 45.5/45.7 FAIL (the neck's front now shows: r 0.115 L continuous through the cut), piece_collar 0.639
-> 0.683 WARN, collar_front_torn 0.0197 -> 0.0087 FAIL; but collar_profile_torn 0.0252 -> 0.0976 FAIL, art_outline_collar
3.82 -> 8.54 / 6.80 WARN and art_fragments_collar 3.62 -> 9.27 (the collar's front and back halves meet in profile at the
neck's plane, a torn edge). Not taken. The crease left on D5 (crease.py): columns +-25..55 degrees, 0.07-0.10 L under
the cut, r 0.146 -> 0.175 -> 0.202 with gaps: the chest in the V (the jacket's V shows skin there now, as drawn) and
the shoulders template's turn; the measure reads the V's chest within JOIN (0.10 L under the cut).

Review page: `charkit/out/collar_round3/review/index.html` (design | before c3_before | after c3_m2 = M2 | option D3, the
back view, the bow zoomed, the profile, the neck junction; every check whose status moved; generator review.py and
cu2.py beside it).

### M3: open, in order (for the next agent)

1. The collar's front/back split: neither the chest's plane (the neck wrapped: neck_crease 92.6, the front torn) nor the
   neck's (the profile torn) works. Next: a split that follows the body (the lapels' front outline defined round the
   neck by azimuth, e.g. outline_dist's `front` as |angle from the front| < a table per height, so the neck's sides
   belong to the lapels' inner edge), measured on collar_profile_torn, collar_front_torn and neck_crease per column
   (crease.py) together.
2. shoulder_back_slope 0.249 FAIL on every D (a guard, not a flag): the level shoulders template against the design's
   slope; fit `fall`/`round`/`x` with shoulder_back_line (0.0235 WARN: the torso can't rise above the neck ring) and
   collar_back_lay (0.0094 PASS).
3. art_outline_collar (flag; PASS <= 2 corners): 3.8 on D3; count the corners with corners.py on c3_D3 before changing
   anything (the puffs' station adds a corner where the puffs meet the collar's side in front, round 1).
4. The jacket's front in profile under the ribbons (the bow's profile IoU 0.30 on M2): not started.
5. hair_noise 0.0782 WARN on D3 (0.0018 of margin), art_speckle_neck 1.08 PASS on D3: held.

**M2 on the merge (b361654 into pipeline-3d 2f42155): PASS under K**
(`charkit/out/gate/gate_tool-collar3_b361654_into_2f42155.md`): the same 193 items as 9c99e44's gate, PASS -> WARN
piece_cuff_L and shoulder_back_slope, CPU 1.27x (605.7 -> 770.6 s). M3's code is in it, off by default. Mergeable.
