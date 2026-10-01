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
