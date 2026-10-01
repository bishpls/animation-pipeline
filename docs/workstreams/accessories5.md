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
Round 1 started. Baseline box build of pipeline-3d 00494de (clawd.json, `--boards views --no-blend`):
`charkit/out/acc5/base` (log `charkit/out/acc5/logs/base_build.log`).

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
  0.347 against the drawn 0.36-0.40): refit with the tips' reach term (`fit_star2`, running).
- Crab (`charkit/out/acc5/fit_crab`, 1,057 evaluations): 0.770 / 0.668 / 0.725 -> 0.848 / 0.797 / 0.768, clips-alone
  0.717 -> 0.725; legs at their 0.15 bound (the turnaround draws short legs), claw notch 18 deg.
- Edge-on (the clips-alone sheet): star depth 0.10, thick 0.03 (front relief 47 px of 465, tips 14 px); crab body_d
  0.34 (was 0.42).
