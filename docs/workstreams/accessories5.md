# Workstream: the hair clips remade and re-placed (`tool/accessories5`)

Branch `tool/accessories5` from pipeline-3d 00494de, worktree `~/animation-pipeline-acc5`. Earlier rounds:
`accessories.md` (rounds 1-4: the 8-point star and the crab fitted to head_turnaround, the star bent over the crab and
hidden from behind, Michael's call (a)).

## The task (coordinator's brief, 2026-10-01)
Remake and place the crab and the star from the separated layer references (`hair_clips_layers`: the hair without its
clips, the true surface under them; the clips alone, the structure authority; proportions from `head_turnaround` where
they disagree: layerrefs.md section 6).
- **Non-occlusion** (Michael): pieces don't hide each other; "the crab being hidden under the star is poor design".
  Deviate from the drawn placement to keep both clips fully visible; report the deviation.
- Standing calls: the clips balance the front and side views; the star stays hidden from behind (call a); the star's
  outline is the default dark brown.
- Plan: 1. measure first (visible share per view; shape against the clips-alone structure with the turnaround's
  proportions; seating; the star hidden from behind), declared and calibrated; 2. remake the templates; 3. re-place
  both clips; 4. guard (the clips' and hair pieces' IoU per view, palette_iris_* clean); 5. review page, pregate, gate.

## State
Round 1: measured, remade, re-placed (fit A3), box-built (`charkit/out/acc5/after2`), calibrated (34 records), review
page `charkit/out/acc5/review/index.html`; gate running (see "Gate" at the end). Baseline box build of pipeline-3d
00494de: `charkit/out/acc5/base` (its QA under the new measure: `charkit/out/acc5/base_qa_new`; the pair for the review
page: `charkit/out/acc5/before`, links).

Work files (gitignored): `charkit/out/acc5/work/` (design_masks.py: the design's clips from both references ->
design.npz, design_masks.png).

## The design's clips (head_turnaround, accqa.design at 401 px/L)
| view | crab px / size L / centroid (u, z) | star px / size L / centroid (u, z) / h L |
|---|---|---|
| front | 2603 / 0.127 / (0.291, 0.318) | 4126 / 0.160 / (0.436, 0.338) / 0.379 |
| three-quarter | 2729 / 0.130 / (0.280, 0.314) | 4010 / 0.158 / (0.442, 0.340) / 0.364 |
| profile | 2812 / 0.132 / (0.154, 0.322) | 5230 / 0.180 / (0.324, 0.351) / 0.411 |

The drawing layers them inconsistently: the crab's body lies over the star's left arm (shortening it: 0.26-0.33 of the
star's height against the right arm's 0.35-0.41), and the crab's right claw is hidden under the star. So each clip's
drawn mask is reliable only outside the other's.

## 1. Measure first (b45f61e2, the steps at it)
- **Fit tool** `charkit/accfit.py` (`python -m charkit accfit shape|place|measure`): the template fit (one shape, a
  pose per view, scored by the as-drawn IoU + 0.25 x the clips-alone IoU, the star + 2 x its tips' reach off the drawn
  star's) and the placement fit (both clips' at / facing / tilt / size on a build's hair; loss: round 2's per view, +
  20 per unit of a clip's share hidden below 0.985, the star's back past 20 px, the seat). It reproduces the QA on the
  baseline (crab IoU 0.726 / 0.732 / 0.488 against the QA's 0.728 / 0.732 / 0.487). `Ground` keeps its hair BVHs.
- **New checks** (accqa): `acc_KIND_VIEW_visible` (declared, family `visible` added to charkit.declared: the share of
  our clip's own silhouette, drawn alone, that shows; `covered_by` names what covers it), `acc_star_arms` /
  `acc_star_minor` (the star face-on: its longer side arm and minor points over its height against head_turnaround's
  0.385 / 0.311, `accqa.STAR_ARMS`; the clips-alone sheet's compass star reads 0.482), `acc_KIND_alone` and
  `acc_KIND_shape` (INFO: face-on IoU against the clips-alone drawing; the per-view IoUs as one check).
- **Remeasured** (`accqa.as_drawn`): acc_KIND_VIEW_{iou,size,pos,angle,shown} and pos3d compare ours as the drawing
  shows the clip: the drawing layers them inconsistently (the crab's body over the star's left arm, the star over the
  crab's right claw), so ours, aligned on the drawn clip, has the other drawn clip's cover taken out first. A clip the
  drawing doesn't cover measures as before. Registered in charkit/steps/accqa.py.
- **Calibration**: adapter `charkit/calib/clips.py` (`Clips`: the drawn clips as our labels through accqa.evaluate's
  `labels`; floors swap / scaled / moved / turned / compass / four_point; probes touching, star_under_crab). Known-bad
  `acc_r4_overlap` stored (the baseline build: charkit/calib/known_bad/acc_r4_overlap.json).

Baseline (pipeline-3d 00494de, the new measure on the old geometry; ours / design):

| clip | front | three-quarter | profile |
|---|---|---|---|
| crab visible | 0.784 FAIL (star 712 px) | 0.741 FAIL (star 1090) | 0.618 FAIL (star 1354) |
| star visible | 1.000 | 1.000 | 1.000 |
| crab iou (as drawn) | 0.726 | 0.746 | 0.499 FAIL |
| star iou (as drawn) | 0.571 FAIL | 0.763 | 0.763 |
| crab / star pos L | 0.103 / 0.018 | 0.069 / 0.096 | 0.260 / 0.345 |

Star arms 0.349 (WARN, -0.041), minor 0.284 PASS; star back 17 px; seats 0.0000 / 0.0003.

## 2. Templates (accfit shape on the box)
- Star (`charkit/out/acc5/fit_star`, 1,064 evaluations): as-drawn IoU 0.757 / 0.771 / 0.876 -> 0.817 / 0.853 / 0.871
  (the current shape unposed -> fitted with a pose per view), clips-alone 0.773 -> 0.771; but its tips short (side
  0.347 against the drawn 0.36-0.40): refit with the tips' reach term (`fit_star2`, 1,540 evaluations): 0.813 / 0.853
  / 0.859, clips-alone 0.765, arms side 0.384 / minor 0.311 (on the drawn 0.385 / 0.311). Shape: up 0.550, down 0.487,
  side 0.394, minor 0.320, inner 0.167, curve 0.038, minor_at 43.1 (height 1.037 in its own units).
- Crab (`charkit/out/acc5/fit_crab`, 1,057 evaluations): 0.770 / 0.668 / 0.725 -> 0.848 / 0.797 / 0.768, clips-alone
  0.717 -> 0.725; legs at their 0.15 bound (the turnaround draws short legs), claw notch 18 deg.
- Edge-on (the clips-alone sheet): star depth 0.10, thick 0.03 (front relief 47 px of 465, tips 14 px); crab body_d
  0.34 (was 0.42).

**How much of each clip the turnaround itself shows** (the fitted templates posed per view, the drawn cover's share
taken out by as_drawn; `work/drawn_hidden.py`): crab 0.722 / 0.827 / 0.745, star 0.918 / 0.960 / 0.962 (front /
three-quarter / profile). The drawn arrangement fails the non-occlusion check for the crab: the reference's placement
is the rule's known-bad, as Michael said.

## 3. Placement (accfit place on the box, from the baseline build's hair)
Three starts (the fitted shapes, the crab moved off the star): A crab at +(0, -0.07, -0.05) (forward and down), B
+(0, 0, -0.10) (down), C +(0, +0.05, -0.08) (back and down); 25 min each (A 2,135 evaluations, B 1,885, C 1,546),
`charkit/out/acc5/place_{A,B,C}`. All three move the crab down under the star's lower tip rather than forward toward the
face. Each measured under the QA's measure and the plain one (as_drawn off: the gate's old measure on the new geometry;
`accfit measure --starts`, `charkit/out/acc5/measure_abc`). Front / three-quarter / profile:

| placement | crab visible | crab iou (QA / plain) | crab size plain | crab pos L | star iou | star front pos | back px | loss |
|---|---|---|---|---|---|---|---|---|
| round 4 (new shapes) | 0.78 / 0.74 / 0.62 | 0.72/0.74/0.50 / 0.72/0.73/0.49 | 0.99/1.07/0.88 | 0.10/0.07/0.26 | 0.57/0.76/0.76 | 0.018 | 39 | 24.1 |
| **A (chosen)** | **1.00 / 0.985 / 0.985** | 0.64/0.76/0.72 / 0.62/0.67/0.66 | 1.02/1.19/1.13 | 0.18/0.18/0.30 | 0.52/0.80/0.82 | 0.032 | 20 | 5.49 |
| B | 0.986 / 0.992 / 0.985 | 0.71/0.78/0.70 / 0.66/0.61/0.65 | 1.12/**1.27 F**/1.15 | 0.22/0.19/0.26 | 0.56/0.83/0.82 | 0.031 | 18 | 5.66 |
| C | 0.985 / 0.993 / 0.986 | 0.71/0.75/0.72 / **0.59 F/0.56 F**/0.61 | 1.16/**1.33 F**/1.21 | 0.22/0.19/0.26 | 0.54/0.82/0.84 | 0.037 W | 17 | 5.89 |

Seats 0.0000 for every clip in every placement; the star never bends (conform lift 0.000-0.001). **Michael (through the
coordinator, 2026-10-01): moving the crab is fine; weight full visibility and good seating over closeness to the drawn
spot; pick the best visibility and seating (C acceptable unless A or B match it with less movement).** A: the best
visibility (the crab whole in front), the same seats, the least movement in front and three-quarter (0.18 L against
0.19-0.22) and the lowest loss; the only one with no new FAIL under the old measure (B's crab size 1.27 and C's crab
IoU 0.56-0.59 there would block in the gate's 2x2). Its cost: the crab's front IoU 0.726 -> 0.640 (-12%, WARN; plain
0.728 -> 0.624, -14%), its profile position 0.26 -> 0.30 L. Specs: A's clips (the fitted shapes, at / facing / tilt /
size) in all six specs (`work/specs.py`: only the accessories block's text changes).

**The deviation from the drawn placement** (A, the crab's centroid against the drawn crab's, L): front 0.183, three-
quarter 0.176, profile 0.301 (round 4: 0.103 / 0.070 / 0.260); the crab sits under the star's lower tip instead of
beside its left arm. The star: front 0.032, three-quarter 0.090, profile 0.332 (round 4: 0.018 / 0.096 / 0.345).
In 3D: the crab's anchor moved from (0.342, -0.366, 0.266) to (0.365, -0.423, 0.145) L (0.135 L: down 0.12, forward
0.06); the star's from (0.339, -0.324, 0.373) to (0.411, -0.343, 0.379) (0.075 L, outward).

### The polish (A -> A3) and the build
- A's box build (`charkit/out/acc5/after`): the crab's front axis 27.3 deg FAIL (round 4 15.6 WARN): the loss had no axis
  term (an IoU aligned on centroid and area barely sees a turn). Added ANGLE_W (0.05 a degree past 8) and polished from
  A (A2, 15 min): front axis 6.8, but the gate's old measure (as_drawn off) read the crab's three-quarter axis -22.7 FAIL
  (the whole crab against the drawing's half-hidden one; base -4.8 PASS): the 2x2 would block. Polished again with that
  old measure kept off FAIL (`accfit place --plain 1`: hinges at its FAIL limits; A3, 12 min, 1,023 evaluations).
- **A3** (the specs at 36e03aad): crab at (0.380, -0.432, 0.142) facing (56.1, 11.2) tilt -18.0 size 0.140; star at
  (0.427, -0.351, 0.380) facing (65.7, 3.2) tilt 0.45 size 0.434 (conform kept; it doesn't bend: nothing under it).
- **Box build** `charkit/out/acc5/after2` (36e03aad; CPU 1045 s): against round 4 under the new measure (`base_qa_new`):

| check (front / three-quarter / profile) | round 4 | A3 |
|---|---|---|
| crab visible | 0.784 / 0.741 / 0.618 FAIL | **0.997 / 0.988 / 0.988 PASS** |
| star visible | 1.000 | 1.000 |
| crab iou | 0.726 / 0.746 / 0.499 F | 0.724 / 0.770 / 0.648 W |
| crab angle | 15.6 W / 4.1 / 18.2 W | 10.5 W / -1.1 / 10.3 W |
| crab pos L | 0.103 / 0.069 / 0.260 | 0.193 / 0.176 / 0.308 |
| star iou | 0.571 F / 0.763 / 0.763 | 0.541 F / 0.819 / 0.792 |
| star pos L | 0.018 / 0.096 / 0.345 | 0.028 / 0.095 / 0.334 |
| star size | 0.999 / 1.147 W / 0.981 | 0.942 / 1.123 W / 0.996 |
| seats crab / star | 0.0000 / 0.0003 | 0.0000 / 0.0000 |
| star back px | 17 | 18 |
| star arms / minor | -0.025 / -0.027 PASS | 0.018 / 0.002 PASS |

No new FAIL under the new measure; under the old one (the fit's plain reading) crab iou 0.717 / 0.684 / 0.638, size
1.02 / 1.18 / 1.10, axis 3.2 / -18.0 / -15.6: none FAIL. **The guard** (every piece's shape IoU per view, round 4 ->
A3): acc_crab_shape front 0.726 -> 0.724 (-0.3%), acc_star_shape front 0.571 -> 0.541 (-5.3%), hair_piece_side_locks
front 0.560 -> 0.530 (-5.4%: the crab now lies over hair the drawing shows), bangs front 0.849 -> 0.834 (-1.8%); no
garment piece moved; palette_iris_lit / shade 2.19 / 4.74 unchanged (clean); art_peeks_hair 17 WARN both.
**The deviation** (A3, the crab's centroid off the drawn): 0.193 / 0.176 / 0.308 L (round 4 0.103 / 0.069 / 0.260); its
anchor 0.135 L from round 4's (down 0.12, forward 0.07): under the star's lower tip, not beside its left arm. The star:
0.028 / 0.095 / 0.334 L (round 4 0.018 / 0.096 / 0.345).

### Calibration (records committed, a6f6b550)
`python -m charkit remote run --fetch charkit/calib/records calibrate 'acc_*' --build charkit/out/acc5/after2` (the
known-bad stored on the box too). 34 records: acc_crab_*_visible **calibrated** (design 1.0 every move; acc_r4_overlap
0.784 / 0.741 / 0.618 FAIL; probe touching 0.99 PASS); acc_star_*_visible guard (floor star_under_crab 0.84-0.87 FAIL);
the remeasured iou / size / pos / angle / pos3d and the star's arms / minor guard (the design passes every move; the
floors swap / scaled / moved / turned / compass / four_point fail). Fixed on the way: calib/clips.py's CALIBRATION must be
a pure literal (calibrate reads it with ast: named constants broke `calibrate.entries()` for every check).

### Review page
`charkit/out/acc5/review/index.html` (from `review/page.json`, `python -m charkit review page`): the summary box, the
design | round 4 | A3 per view and the clips close-ups at one scale (a new `clips` region in reviewpage.REGIONS), the
references, the template fits, the placement candidates, the QA overlays, the numbers.

### Infra finding (for the coordinator)
A sync failed twice with `download cas/03/0303...: sha256 mismatch`: the shared bucket held a 64,007-byte
docs/workstreams/garments4.md under the 61,473-byte version's hash (a sync read the file while it was being edited:
bucketsync hashes, then uploads the file as it is then). Repaired by uploading the right bytes over it
(`charkit/out/acc5/work/fix_blob.py`). The upload should send the bytes it hashed (or re-hash after upload).

### Pregate
Not run: the coordinator's directive (laptop memory critical, no local heavy jobs) and the box copy has no git for its
target worktree. The box builds above measure the clips; the gate checks the rest.
