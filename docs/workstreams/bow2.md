# The bow in profile (tool/bow2)

Michael's flag (2026-09-30): in profile the bow's ribbon tails project far forward of the chest as flat blades; the
design hangs them close to the chest, nearly vertical, under puffy loops; our loops read as flat disks. M1's
`bow_profile_ribbon` (the ribbons' width seen in profile, from the earlier flag about them merging into the jacket)
passed by swinging the ribbons forward while the bow's profile shape IoU fell 0.52 -> 0.34: the pattern the
anti-gaming guard now blocks. Reference: `~/animation-pipeline-garments3/charkit/out/collar_round3/review/index.html`
(profile).

Worktree `~/animation-pipeline-bow2`, branch `tool/bow2` from pipeline-3d 8b5ecae. tool/collar4
(`~/animation-pipeline-garments3`) reworks the collar and shoulders in garments.py and collarqa.py: this branch keeps
to the bow's functions (`bow_hull`, `_bow_mesh`, garments.py lines ~2423-2640 at 8b5ecae) and puts its checks in a
module of its own (`charkit/bowqa.py`, QA part `bow_profile`, order 1765) so the two don't meet in collarqa.py.

## State (start here)

- **Before build** (box): `charkit/out/b2_before` = pipeline-3d 8b5ecae, default spec. piece_bow 0.754 PASS (front
  0.896, three-quarter 0.759, profile 0.346); bow_front_loop_end 0.121 PASS, bow_front_bleed 0.0 PASS,
  bow_front_tail_width 0.0 PASS, bow_front_tail_gap 0.014 PASS, bow_front_loop_width 0.002 PASS, bow_profile_ribbon
  0.053 PASS, bow_front_flare 1.005 FAIL (the pillows), art_*_bow INFO.
- **Checks built and calibrated** (d179a05; steps `charkit/steps/bowqa.py`; tests `charkit/tests/test_bowqa.py`).
- **Next:** the refit (below), with piece_bow per view beside every variant.

## Measured first (profile, the QA's grid: 212 px/L, registered on the near eye; forward = toward the face)

Harness `charkit/out/bow2/harness/` (untracked): `var.py OUT --set garments.bow.KEY=JSON ...` (the bow built by this
tree's evaluator spliced into b2_before's bundle, then the QA parts collar_flags, sheet_pieces, piece_details,
bow_profile; ~60-160 s; reproduces the box on every bow check but bow_front_bleed, which needs the box's outline
shrink), `cal.py SRC...` (the calibration table), `profrows.py`, `profzoom.py`, `bowpic.py`, `loopdesc.py`, `cand.py`.

- Ours split: the bow mesh is five connected parts (two lobes, two tails, the knot). In world depth our tails sit
  at y -0.545..-0.35 L, 0.11-0.15 L in front of the lobes' front (-0.40): `conform` puts their mid-plane on the hull's
  bow front (the drawn front already), then `hinge` 1 brings each row forward by its turned half-depth
  (0.5 w sin 40 = up to 0.10 L at the ends) and `stand` 0.015 L more.
- The front edge per row (L across the grid; the design | b2_before): the design's runs straight down from the loops'
  front into the tails, -0.18 (z -0.83) to -0.22 (z -1.17); ours steps 0.07 L forward where the tails leave the knot
  (-0.175 at -0.83 to -0.246 at -0.849) and drifts to -0.297 by -1.04: the blade.
- The drawn tails' back edge in profile (-0.02 at z -1.1) lies behind our jacket's centre front (-0.10..-0.14): the
  near tail's outer edge wraps round the bust's side, where the jacket's surface is further back than its centre
  front (and the drawn tails' mask may take some of the bib's cream). The front edge is the robust measure.
- The loops: the drawn 'bow' mask in profile spans z -0.60..-1.05, fullest low (its run 0.24 L at z -0.70..-0.87),
  its back edge matching ours down to -0.83; ours span -0.62..-0.91, fullest high (0.27 L at -0.72..-0.79), tipped
  forward: the lobe's face seen obliquely (wrapped round the chest), a disk.
- Renders (`charkit/out/bow2/review/cu2.py`, registered on the QA's eye point): profile and front register with the
  design's crops; the three-quarter doesn't (the drawn three-quarter's torso is turned less than its head, the QA uses
  one azimuth for both): eyeball only.

## The checks (charkit/bowqa.py, part bow_profile, all flagged)

| check | what | limits | design moved 1-2 px / dilated 1 px | b2_before (current) | g3_render3 (pre-M1: tails merged back) | co_render |
|---|---|---|---|---|---|---|
| bow_profile_tail_reach | the bow's front edge per row from the knot (0.04 L above the drawn tails' top in front) to 90% down the drawn tails, ours less the design's, 90th percentile of the size (L) | 0.03 / 0.06 | <= 0.0094 PASS | 0.109 FAIL (median +0.080: forward) | 0.062 FAIL (-0.038: behind) | 0.044 WARN |
| bow_profile_tail_hang | the chord from the front edge where the tails leave the knot to their foot, from the vertical, ours less the design's (degrees) | 5 / 10 | <= 0.83 PASS | 12.6 FAIL (21.0 vs 8.4) | 10.1 FAIL (-1.7) | 0.8 PASS |
| bow_profile_loop_thick | the loops' run per row at tenths of the drawn loops' height, RMS against the design's (L) | 0.03 / 0.05 | <= 0.0141 PASS | 0.076 FAIL | 0.077 FAIL | 0.076 FAIL |
| bow_profile_loop_lean | the loops' equivalent-ellipse major axis from the vertical, ours less the design's (degrees) | 8 / 15 | <= 0.02 PASS | 20.0 FAIL (49.4 vs 29.3) | 23.3 FAIL | 20.5 FAIL |

Candidates measured and not taken: the loops' minor/major axis ("roundness": 0.57 on b2_before, 0.55 on the design:
blind), their inscribed radius (ours fatter, 0.103 vs 0.093), a line fitted to the front edge over the drawn tails'
visible rows only (5.1 vs 6.4 degrees: the blade's step is above those rows, where the drawn loops hide the drawn
tails). The reach and hang catch both errors: forward blades (b2_before) and tails sunk into the jacket (g3_render3,
the earlier flag). bow_profile_ribbon stays, as the guard against sinking back.

Calibration is by this branch's harness (cal.py), the tool/calib triple's design half (moved 1-2 px) and its
known-bad (the current build). tool/calib (not in pipeline-3d yet) would want records
(`python -m charkit calibrate bow_profile_*`); its Garments adapter patches pieceqa's label functions, and this part
labels through `bowqa.split_labels`, so the adapter needs that patched too (the design's loops as LOOPS, its tails
as TAILS).

## The refit: what the jacket allows (measured)

`probe3d.py` (b2_before, the profile frame: u = (y - y_near_eye) / L, forward negative): with `hinge` 1 the tails'
outer edge already sits on the jacket (z -1.05: outer edge x 0.257 at u -0.133, the jacket there -0.129) and the 40
degree turn swings the inner edge 0.165 L forward (u -0.298). The jacket's front at z -1.05 by |x|: -0.147 (the bib,
0-0.1), -0.138 (0.2), -0.129 (0.25), -0.105 (0.3), -0.07 (0.35). The drawn tails in front span |x| 0.08-0.26..0.29
(ours the same: tail_width 0.0), and in profile from -0.21 (front) back to -0.03..-0.04: a ribbon turned ~43 degrees
whose outer edge would lie 0.07-0.09 L inside our jacket. So a ribbon whose front edge is at the drawn one and which
doesn't sink can show only jacket_u(x_out) - front = 0.08-0.11 L of face in profile, against the drawn 0.179:
`bow_profile_ribbon` (PASS within 25%: 0.134 L) and `bow_profile_tail_reach` (PASS within 0.03 L) can't both pass on
this jacket with the tails' front width held (tail_width). The drawing's profile tails are deeper than its front view
and our jacket allow; our jacket's centre front matches the drawn one where it shows (z -1.2: -0.104 against
-0.09..-0.10).

Sweep s1 (`sweep.py s1.json`; one evaluator process, ~16-21 s a variant; summary lines in harness/sweep.log):

| variant | reach | hang | ribbon (flag) | tail width | gap | bow IoU front / 3q / profile |
|---|---|---|---|---|---|---|
| b2_before (hinge 1, turn 40) | 0.109 F | 12.6 F | 0.053 P | 0.0 P | 0.014 P | 0.896 / 0.758 / 0.346 |
| hinge 0 (turned about the middle) | 0.035 W | 2.5 P | 0.526 F | 0.436 F | 0.014 P | 0.792 / 0.664 / 0.520 |
| hinge -1 (the inner edge on the wrap) | 0.066 F | - | 0.97 F | 0.92 F | 0.21 F | 0.543 / 0.543 / 0.524 |
| hinge 0, turn 60 | 0.063 F | 2.5 P | 0.368 W | 0.62 F | 0.089 F | 0.770 / 0.672 / 0.487 |

Hinge 0 and -1 sink the ribbons' outer halves into the jacket (the ribbon and tail width checks fail, and front and
three-quarter IoU drop 12%+).
