# Garments as pieces (tool/garments)

## Checkpoint: end of round 6 (2026-09-30). Start here.

**Branch** `tool/body` in `~/animation-pipeline-body`: it contains tool/hull-det 3267aea and tool/garment-sampling
47b401f (merged at d9d9b27, auto-resolved: garment-sampling changed only hull_pieces, shell_points, shell_patches,
STRAY and _knn_mean; round 5 the boots, the midriff and flap_mirror) and pipeline-3d 2e3bdd5 (merged at a9aa137). The
Clawd specs `clawd.json`, `clawd_body.json`, `clawd_body_pieces.json` carry the same garments; clawd_mh's skirt `q` is
0.6. Build of this state: `charkit/out/body6_render` (boards, bundle, QA; the GPU box). Review page:
`charkit/out/review_body6/index.html`.

**Gates** (build box):

| gate | verdict | detail |
|---|---|---|
| a9aa137 default (clawd.json) into 2e3bdd5 | **PASS** | 0 regressed; improved back hem_mid 0.1364 WARN -> 0.0517 PASS, three-quarter IoU 0.833 WARN -> 0.851 PASS, three-quarter A-line -0.189 FAIL -> 0.09 WARN, overskirt_panel_R 0.448 FAIL -> 0.619 WARN, back and profile skin IoU WARN -> PASS, cuff_L FAIL -> WARN (the shell); remeasured the skirt widths and flap hangs; new: the overhang checks PASS, leg_back FAIL (hull-limbs); tests ok. `charkit/out/gate/gate_tool-body_a9aa137_into_2e3bdd5.md` |
| a9aa137 clawd_mh into 2e3bdd5 | **PASS** | 0 regressed; back skirt width 0.941 PASS -> 1.067 PASS (remeasured), front A-line -0.040 -> -0.021 PASS; tests ok. `..._clawd_mh.md` |
| **30f958c default into 2e3bdd5** (the state; the flaps' band trim 0.12) | **PASS** | as a9aa137, 0 regressed, 7 improved; the hems front 0.0424, back 0.0236, three-quarter 0.0471, profile -0.0517 (a9aa137 at trim 0.10: 0.0188, 0.0, 0.0235, -0.0753, the profile a pixel inside its line); tests ok. `charkit/out/gate/gate_tool-body_30f958c_into_2e3bdd5.md`. clawd_mh's gate at a9aa137 stands: 30f958c changes only the default specs' flap band |

**The skirt's hem at the sides and back was cut short by labels, not hidden** (`garments.hem_cut`, knob `hem_cut`).
Per sector, where the skirt's label stops, another piece's points carry its surface on (within 0.12 L below, within
0.08 L of the skirt's radius): the flaps over it (+-115..162 deg), the hands (+-88..98), and elsewhere `shorts`: the
skirt's own dark hem band, labelled as the shorts (both dark) at r 1.0-1.08 L, far outside the shorts. True hem
sectors (the front, the cream panel) have 0-15 such points, cut ones 40-100. Cut sectors (and stretches under 7.5 deg
the test kept between cut ones: one sector in a hand's notch at 0.92 L pinned the whole filled back) are filled round
the circle from the rest: a level hem at 1.19 L all round, as the design draws it. The old occlusion test (occluders,
occluded_span) also dropped the centre back, where the flaps' profile-view labels lie below a hem the back view shows.

**The skirt's axis and symmetry** (`garments.ring_axis`, knobs `axis`, `symmetric`). About the waist ring's median
(x +0.05, y -0.105 L: the bow and panel hide its front and its points crowd elsewhere) the skirt read 0.1-0.12 L
lopsided left against right; about the ring's fitted ellipse centre within 0.02. `axis: midline` puts the axis on the
hips' x (0: the band's and the waist's extents are centred there; the legs' midline, 0.0107 L, is the boots' plane and
put the skirt 0.011 L to her left of the band: overhang mirror 0.0235 WARN). `symmetric` mirrors the hem, the waist
line and the radius field about the axis's plane; flap_mirror mirrors about it too, so the right flap needs no lift.

**Michael's review of round 5:**
- *Midriff, the skirt jutting past the band on her right:* `body_front_skirt_overhang_{L,R,mirror}` (detailqa): level
  with the band's lower half, how far the skirt stands past the band's outer edge, beyond the design's per side, and
  left against right. Round 5 (its box bundle): her right 0.075 FAIL (0.155 L out against the design's 0.08), mirror
  0.151 FAIL. Round 6: 0.0 / 0.0 / 0.0094, all PASS.
- *The bump behind the thigh in profile:* `body_profile_leg_back` (detailqa): the legs' back edge per row against the
  design's, its largest outward bump once the median offset is out. Round 5 0.202, round 6 0.207 FAIL (the box's;
  evaluator 0.099). Diagnosis: tool/hull-limbs'. The hull's thigh skin is right from z -2.78 down (back edge u 0.57 vs
  the design's 0.55), but at z -2.72..-2.76 (the thigh's top rows at the shorts' hem) the hull labels skin from u 0.03
  to 1.35: the profile's whole side run behind the leg, where the flap train is. code_body's thigh fit takes those
  rows and bulges 0.07-0.11 L behind the design's over -2.74..-2.91. hull-limbs.md describes this row ("z -2.72 fell
  back to the whole side run"); its LimbTrack fix leaves 2-3 outline cells. Reported to the coordinator.
- *Spiky puff sleeves:* moved to tool/garments2 (with the band, shorts, pleats, collar, bow and wrist cuffs).

**The flaps, refitted jointly with the hem.** They were 0.14 L short: lowest point -3.064 against the drawn flaps'
-3.19..-3.21 in every view (the outfit graph's extents). The hang check hid it: its reach was the drawn chain's last
joint (-3.07), a skeleton's end, which stops short of the tip by the half-width. Now it is the drawn piece's lowest
point (`qa3d.drawn_low`, registered at 854776f). With the level hem the tails start 0.2 L lower, and three things
pull: the four hems (the lowest orange row per view; the design's profile draws the flap 0.05-0.09 L shorter than its
other views), the extents (the flap's lowest row per view) and the three-quarter hem_mid (the right tail's tip showing
between the thighs). Fitted on the evaluator (a coordinate descent, then grids over az, out, tip, length, trim;
scratch `fit.py`, `grid.py`): **az 128** (143.8: the tails hang further to the sides, as drawn in front and
three-quarter), **tip 0.5** (0.907: the V's point mid-width, as the design's back view has it; at 0.85 the point sat
behind the thigh in front), **out -0.3**, width 0.808, az_waist 175.4, **length 0.36**, **trim 0.12** (the stepped
band). Their chains rewritten into the outfit notes (charkit flapchains): mirror images now (roots x +-0.03; round 5's
0.226 / -0.205), ending at the drawn tip (-3.20). The train is hang (Michael's call, 2e3bdd5); in profile the tails
lean slightly forward where the drawn chain sweeps back.

**clawd_mh.** Skirt `q` 0.6 (front A-line -0.040 PASS base, -0.055 WARN on the shell, -0.021 PASS now). The back width
with no row free of hands in both figures compares matching heights: the design's free rows (the waist, z -1.40..-1.56)
against ours on the same rows, the row whose ratio is the median (26c6bbb). One row alone (the design's widest)
fell where ours' run through the axis breaks for 0.075 L: the MakeHuman body's skin shows at the band's sides in the
back view (0.727 FAIL at that row; median 1.067 PASS).

**Evaluator against the box.** On the shell path the evaluator reads the box's numbers exactly for the hems, hem_mids,
extents, hangs and widths (this round's gates). Garment-sampling's gate read its hems 0.024-0.028 higher than its
evaluator run; that offset didn't recur. The IoUs read 0.01-0.04 lower in the evaluator.

**Hem and flap checks, round 5 (box, ac461eb into 5cb5256) against round 6 (box):** in the table below.

| check | pipeline-3d (gate base) | round 5 (ac461eb) | round 6 (30f958c) |
|---|---|---|---|
| body_front_hem | 0.0471 PASS | 0.0706 PASS | 0.0424 PASS |
| body_back_hem | 0.033 PASS | 0.0565 PASS | 0.0236 PASS |
| body_three_quarter_hem | 0.08 PASS | 0.08 PASS | 0.0471 PASS |
| body_profile_hem | -0.0376 PASS | -0.0188 PASS | -0.0517 PASS |
| body_front_hem_mid | 0.0376 PASS | 0.0376 PASS | 0.0094 PASS |
| body_back_hem_mid | 0.1364 WARN | 0.1364 WARN | 0.0517 PASS |
| body_three_quarter_hem_mid | 0.0141 PASS | -0.3342 FAIL | 0.0094 PASS |
| piece_overskirt_panel_L_extent | 0.0424 PASS | 0.0424 PASS | 0.0659 PASS |
| piece_overskirt_panel_R_extent | 0.0565 PASS | 0.0377 PASS | 0.0377 PASS |
| piece_overskirt_panel_L_hang | 0.0887 PASS | 0.0887 PASS | 0.0236 PASS |
| piece_overskirt_panel_R_hang | 0.0947 PASS | 0.0817 PASS | 0.0286 PASS |
| piece_overskirt_panel_L | 0.47 FAIL | 0.47 FAIL | 0.421 FAIL |
| piece_overskirt_panel_R | 0.448 FAIL | 0.521 WARN | 0.619 WARN |
| piece_skirt | 0.839 PASS | 0.846 PASS | 0.767 PASS |
| piece_skirt_extent | 0.113 WARN | 0.0612 PASS | 0.1271 WARN |
| body_back_skirt_width | 1.091 WARN | 1.091 WARN | 0.995 PASS |
| body_three_quarter_skirt_aline | -0.189 FAIL | -0.208 FAIL | 0.09 WARN |
| body_front_skirt_overhang_R | - | 0.0753 FAIL | 0.0 PASS |
| body_front_skirt_overhang_L | - | 0.0 PASS | 0.0 PASS |
| body_front_skirt_overhang_mirror | - | 0.1506 FAIL | 0.0094 PASS |
| body_profile_leg_back | - | 0.2024 FAIL | 0.2071 FAIL |

The hang rows are remeasured between round 5 and round 6 (reach against the drawn piece's lowest point, not the chain's last joint); the round 5 overhang and leg_back values are the new checks run on its box bundle.

**Open items:**
1. body_profile_leg_back FAIL: tool/hull-limbs (above).
2. piece_skirt_extent 0.127 WARN (base 0.113 WARN): the level hem at the sides. The drawn skirt in profile ends at
   -2.505 (t 1.08: its sides rise), ours at -2.632. The sides' hem is unmeasured on the hull (the hands and the dark
   band cut it); the profile view's drawn skirt could anchor the fill at +-90 deg.
3. The flaps' IoUs: L 0.421 FAIL (base 0.47), R 0.619 WARN (base 0.448 FAIL); the left reads worse than its mirror in
   every grid point (0.42 against 0.62): the design's flaps aren't mirror images in the sheet, or the views disagree.
   With the V's point mid-width the stepped band reads as a dark tip more than round 5's staircase (review page, the
   back close-up); the band's steps (`stair`, `steps`) weren't refitted.
4. The flap train (hang): the tails lean forward in profile; the drawn train sweeps back.
5. clawd_mh: the MakeHuman body's skin shows at the waist's sides in the back view; its overhang reads 0.089 / 0.113
   FAIL (new check; the MakeHuman base is retired).
6. The waistband's height (piece_waistband 0.454 FAIL) and the band's front in profile: tool/garments2 now.
7. From round 5: the outfit drafter (outfit.py) still drafts boots as a shell plus shoes; tool/rig: the flaps' chains
   moved (the notes), the boots are `boot_L`/`boot_R`.

**Gotchas (round 6):**
- clawd.json and clawd_mh.json produce different outfit masks (garment kinds differ) and so different hulls, rebuilt in
  place in one worktree: run one spec's evaluator at a time, and never while another process reads the hull.
- The hull's stamp covers bodyqa.py (the hull uses its classes): a bodyqa edit rebuilds the hull and the masks (the
  same content; 100-180 s).
- An empty dict knob is falsy: `hem_cut: {}` did nothing until the test became `is not None`.
- Scratch harness (evaluator variants, fitter, grids, class-image viz, the review page generator) is in the session's
  scratchpad `r6/`, not tracked.

## Checkpoint: end of round 5 (2026-09-30), superseded by round 6 above

**Branch** `tool/body` in `~/animation-pipeline-body` (see `git log -1`; gated at ac461eb); it contains `pipeline-3d`
5cb5256. The build of this state: `charkit/out/body5b_render` (boards, bundle, QA). The Clawd
specs `clawd.json`, `clawd_body.json` and `clawd_body_pieces.json` carry the same garments (clawd_code.json the same
boots, for the shared outfit masks).

**Gates** (tool/body into pipeline-3d 5cb5256, build box):

| gate | verdict | detail |
|---|---|---|
| ac461eb default (clawd.json, the authored character) | FAIL | one check: body_three_quarter_hem_mid 0.014 PASS -> -0.334 FAIL (the mirrored right tail's tip between the thighs); improved: back and profile skin IoU WARN -> PASS, overskirt_panel_R FAIL -> WARN, skirt_extent WARN -> PASS; the 30 new checks all PASS; tests ok. `charkit/out/gate/gate_tool-body_ac461eb_into_5cb5256.md` |
| ac461eb clawd_body | FAIL | the same one check; improved overskirt_panel_R, skirt_extent. `..._clawd_body.md` |
| fc3344b (tails 0.33 L), both specs | FAIL | six: the hems (front, back, three-quarter), hem_mid still -0.297 on the box's hull, both flap extents; reverted |
| 65ec126, both specs | FAIL | boot_step_L front and back (the cuff's rows: remeasured at 196eace) and hem_mid |

**Michael's review of round 4** (the pleated skirt "MUCH better"): the midriff looked sliced and shifted (the top's
hem stepped short of the band, a torn cream panel, the band a separate ring), and the boots twisted at the ankle,
with a spiked front fold, none at the back, uneven soles unlike each other, a doubled line at the toe and no heel.

**Measured first** (`charkit/detailqa.py`, QA part `details`, 30 checks, registered in history.STEPS at 843922c;
tests `charkit/tests/test_detailqa.py`). The design is measured the same way wherever it has a view:
- the torso outline's steps outward and inward, bust to skirt, front L/R and profile front/back (edges only where
  they are the silhouette; the profile's front below the drawn bow tails, z -1.22);
- the top's hem against the band (a see-through gap or the top over it);
- the cream panel's lower 0.25 L: outline roughness (p95 distance to its smoothed outline), fragments, holes;
- boots: the ankle's jog and bend (front, back), the ankle's folds front and back in profile (as drawn at 3x the
  grid, with the far boot where it shows past the near one), the heel (height, depth, raised arch), doubled outline
  strokes, the bottom face in 3D (flat, twist = roll difference / yaw / tilt), mirror IoUs (front, back, soles from
  below on one grid).
Round 4 (body4b_render) reads 18 FAIL, 6 WARN, 6 PASS. What they found: the doubled toe line is the far boot's toe
0.02 L ahead of the near one (the boots weren't mirror images), and so is the profile's front spike (shoe_R's top).

**Boots as a template** (`garments.boot`, kind `boot`; tests `charkit/tests/test_boots.py`). One watertight upper:
sections from knot tables (`profile` [h, front, back], `width` [h, outer, inner]: offsets from the ankle joint, the
two joints made mirror images about the legs' midline x 0.0107 L), heights over the ground (`ankle_h` 0.667 L under
the ankle). The knots are the drawn boots' silhouettes (front and back views averaged with the mirrored right boot;
profile), so a section's extents are the silhouette. The foot rows bend onto the sole's underside (forefoot on the
ground, the arch raised to `heel.lift` 0.15 L, level over the heel); the sole is the lowest `sole_t` 0.06 L; a heel
block island (inset 0.012 L at its top, flared 0.02 L to the ground, its front at the ankle); the ankle's fold is a
bulge over a crease per quadrant (`scrunch`: at h 0.545, the drawn sizes). `boot_R` is `boot_L` mirrored. The leg and
foot inside are hidden. Every number is in the spec.

**Midriff.** The top's hem drops 0.08 L under the band, kept 0.03 L above its lower edge; its rows above the band
ease out over 0.25 L onto the band's face (`ease_to_band`), so the outline runs into the band without a step. The
band's columns stand upright (`belt_hull` `straight`: its rows had flared into a lip and narrowed 0.07 L to the
bottom). The cream panel is a front-projected texture from a knot table (`panel.profile`, `panel_inside`) that
follows the bow tails' outer edges and runs on under the band, not whole faces (a torn staircase).

**Flaps.** `overskirt_panel_R` mirrors `overskirt_panel_L` about the legs' midline (`flap_mirror`), lifted clear of
the skirt where its right side stands further out (up to 0.21 L: the hull skirt itself is lopsided at the back
sides, its right 0.1-0.2 L wider at 120-145 degrees). Chains rewritten into the notes. Mirrored, the right tail's
tip shows between the thighs in three-quarter (4 px on the QA grid; body_three_quarter_hem_mid 0.014 -> -0.334 FAIL,
the gate's one regression). Shortening the tails to 0.33 L cleared it on the laptop's hull but not on the box's (-0.297)
and regressed the hems and both extents (gate fc3344b), so they stay 0.36 L (ac461eb). The left tail does the same
from her other side, which no check views.

**Measures fixed on the way** (registered): `body_*_boot_step_*` leaves out rows whose outline ends on the cuff
(its rounded lower edge over the narrower shaft read as a 0.02 L step; 196eace). The sole's bottom face is its
down-facing triangles (the subdivision's rounded rim and the arch's slope aren't unevenness).

**Round 4 (body4b_render) against round 5 (body5b_render, the state gated)**, the new checks:

| check | round 4 | round 5 |
|---|---|---|
| body_front_midriff_gap | 0.0 PASS | 0.0 PASS |
| body_front_panel_edge | 0.0251 FAIL | 0.0 PASS |
| body_front_torso_jump_L | 0.0283 FAIL | 0.0 PASS |
| body_front_torso_jump_R | 0.0235 FAIL | 0.0 PASS |
| body_profile_midriff_gap | 0.0706 FAIL | 0.0 PASS |
| body_profile_torso_jump_back | 0.0518 FAIL | 0.0 PASS |
| body_profile_torso_jump_front | 0.0282 FAIL | 0.0 PASS |
| boot_back_ankle_bend_L | 4.44 WARN | 2.47 PASS |
| boot_back_ankle_bend_R | 3.63 PASS | 1.02 PASS |
| boot_back_ankle_jog_L | 0.0576 FAIL | 0.0117 PASS |
| boot_back_ankle_jog_R | 0.0423 FAIL | 0.0009 PASS |
| boot_front_ankle_bend_L | 1.58 PASS | 0.76 PASS |
| boot_front_ankle_bend_R | 4.08 WARN | 0.78 PASS |
| boot_front_ankle_jog_L | 0.0742 FAIL | 0.0053 PASS |
| boot_front_ankle_jog_R | 0.0462 FAIL | 0.0055 PASS |
| boot_mirror_back | 0.9098 WARN | 0.9883 PASS |
| boot_mirror_front | 0.9187 WARN | 0.9893 PASS |
| boot_profile_double_L | 0.2275 FAIL | 0.0173 PASS |
| boot_profile_double_R | 0.0455 WARN | 0.0157 PASS |
| boot_profile_heel_L | 0.16 FAIL | 0.0094 PASS |
| boot_profile_heel_R | 0.1459 FAIL | 0.0094 PASS |
| boot_profile_scrunch_back_L | 0.0086 FAIL | 0.0015 PASS |
| boot_profile_scrunch_back_R | 0.0086 FAIL | 0.0015 PASS |
| boot_profile_scrunch_front_L | 0.0785 FAIL | 0.0039 PASS |
| boot_profile_scrunch_front_R | 0.0777 FAIL | 0.0039 PASS |
| boot_sole_flat_L | 0.0014 PASS | 0.0027 PASS |
| boot_sole_flat_R | 0.0015 PASS | 0.0027 PASS |
| boot_sole_mirror | 0.8458 FAIL | 1.0 PASS |
| boot_sole_twist_L | 0.63 PASS | 0.19 PASS |
| boot_sole_twist_R | 3.57 WARN | 0.33 PASS |

And the existing boot, midriff and flap checks:

| check | round 4 | round 5 |
|---|---|---|
| piece_boot_L | 0.863 PASS | 0.904 PASS |
| piece_boot_R | 0.894 PASS | 0.951 PASS |
| piece_boot_cuff_L | 0.876 PASS | 0.877 PASS |
| piece_boot_cuff_R | 0.831 PASS | 0.831 PASS |
| body_front_leg_gap | 0.0 PASS | 0.0 PASS |
| body_back_leg_gap | 0.0 PASS | 0.0 PASS |
| piece_top | 0.613 WARN | 0.629 WARN |
| piece_waistband | 0.451 FAIL | 0.445 FAIL |
| piece_overskirt_panel_L | 0.47 FAIL | 0.47 FAIL |
| piece_overskirt_panel_R | 0.448 FAIL | 0.521 WARN |
| piece_overskirt_panel_L_extent | 0.0424 PASS | 0.0424 PASS |
| piece_overskirt_panel_R_extent | 0.0565 PASS | 0.0377 PASS |
| body_three_quarter_hem_mid | 0.0141 PASS | -0.3342 FAIL |
| poke_share | 0.0008 PASS | 0.0009 PASS |
| body_front_iou | 0.882 PASS | 0.882 PASS |
| body_profile_iou | 0.873 PASS | 0.876 PASS |
| body_back_iou | 0.89 PASS | 0.888 PASS |
| body_three_quarter_iou | 0.839 WARN | 0.842 WARN |

**Decision for Michael (unchanged default):** the flap train, `charkit/out/decisions/body/flap_train/{hang,sweep}.png`
(the design above ours on its grids, front / three-quarter / profile / back) and `numbers.json`. The fitted hang
(sweep 0.36, out -0.22) against the stronger sweep (1.2, 0.3), which reads more like the drawn profile train and
scores lower (flap IoUs, extents).

**Review page:** `charkit/out/review_body5/index.html`.

**Open items:**
1. The waistband's height and place (piece_waistband 0.445 FAIL, as round 4) and the shorts (0.41): not started. The
   band now stands upright and joins the top; its span is still the hull's (taller than the drawn band).
2. The hull skirt is lopsided at the back sides (its right 0.1-0.2 L wider); the right flap is lifted to clear it.
   Symmetrising the skirt belongs with the garment-sampling work (tool/garment-sampling is changing that path).
3. body_three_quarter_hem_mid FAIL: the mirrored right tail's tip between the thighs in three-quarter (above). Fix
   candidates: the tails' direction per side once the skirt is symmetric (item 2), or the train (Michael's call).
4. The profile's front edge of the band stands a little proud of the top's front (the design's jacket overhangs the
   band by 0.038 L there); the check passes (our bow tails cover those rows).
5. The outfit drafter (outfit.py) still drafts boots as a shell plus shoes; the hand spec uses the template.
6. tool/rig: the boots are new objects (`boot_L`/`boot_R`, kind boot, weighted lowerLeg / foot / toes by
   construction); the top is still a shell under the band (their `under_belts` still applies); the right flap's chain
   moved (notes).

**Gotchas (round 5):**
- detailqa renders ours at 3x the grid for the folds and doubled strokes (qa3d.draw_view); the venv renderer can't
  shade the hair's material (close-ups leave it out).
- An open tube (the band, the top) has no volume sign: orient its normals away from its middle (the scratch swap
  harness got this wrong once and inflated the band by its thickness).
- Scratch harness (swap garments into a built bundle, measure, render close-ups; the flap-train renders; the review
  page generator) is in the session's scratchpad, not tracked.
- Coordination: tool/garment-sampling is changing hull_pieces, _hull_points and the hull-reading paths; round 5 kept
  to the builders' post-processing (belt_hull's straight columns and its returned field) and new functions.

## Checkpoint: end of round 4 (2026-09-30), superseded by round 5 above

**Branch** `tool/body` in `~/animation-pipeline-body` (see `git log -1`); it contains `pipeline-3d` f2d0ea7 (the sync
that keeps i3d) and `tool/loft-robust`. Both specs, `clawd_body.json` and the now-tracked `clawd_body_pieces.json`,
carry the same garments.

**Gates** (tool/body into pipeline-3d, on the build box):

| gate | verdict | detail |
|---|---|---|
| 6d1ca99 (the round 3 refit) default | WARN | build time only (the two gates ran at once; gate-cpu now times CPU) |
| 6d1ca99 clawd_body | FAIL | body_three_quarter_hem_mid 0.009 PASS -> -0.348 FAIL: the refit's inward tails crossed the middle |
| 510e6ae default | **PASS** | `charkit/out/gate/gate_tool-body_510e6ae_into_f2d0ea7.md` |
| 510e6ae clawd_body | **FAIL** | one check: body_three_quarter_iou 0.864 PASS -> 0.839 WARN (the flaps' tails in three-quarter; round 3's flaps read 0.859 in the evaluator but fail hem_mid, and no tail direction reached 0.85 with the rest held). hem_mid 0.014 PASS; poke_share 0.0203 FAIL -> 0.0008 PASS; profile skin, three-quarter hem, collar improved. `..._clawd_body.md` |
| tool/loft-robust a0b66a3, both specs | **PASS** | reports in `~/animation-pipeline-loft/charkit/out/gate` |

**What round 4 did** (numbers: the evaluator on body3's codes unless marked *box*):
- **Flaps.** `garments.flap` has a V hem (`tip`), a stepped silhouette (`stair` treads a side), and a waist centre
  (`az_waist`; `narrow` above 1 is wider at the waist). The spec's flaps are fitted on the build box's hull with the
  skin IoUs, hems and hem_mid as constraints (profile and back weighted 1.5): az 143.8, az_waist 170.4, width 0.688,
  narrow 1.03, length 0.36, train 0.81, tip 0.91, out -0.22, sweep 0.36, stair 4, 32 columns, hem texture steps 3.
  Their colour is now the skirt's (the drawing's lit #d47a55; the spec had held the shade tone, hence "dark wedges").
  The render (`charkit/out/body4_render`) reads as the design: panels over the back sides, a train in profile.
- **The 2 x 2** (evaluator, only the flaps swapped, everything else round 3's; iou_tol L / R):

  | flap geometry | old measure (panels under the skirt) | new measure (over it) |
  |---|---|---|
  | round 2 (849b9a7, template panels) | 0.525 / 0.582 | 0.456 / 0.526 |
  | round 3 (696f957, first flaps) | 0.312 / 0.381 | 0.348 / 0.449 |
  | round 3 refit (be410e0) | 0.333 / 0.475 | 0.389 / 0.592 |
  | round 4 | 0.335 / 0.321 | 0.465 / 0.448 |

  On the old measure round 3 was a regression on both sides that "remeasured" hid; on the render comparison it's
  the other way (see the review page).
- **Collar on the neckline** (`collar_hull`, `neckline: hull`, default): each azimuth starts at the hull collar's
  upper edge round the neck (-0.51..-0.55 L at the back and sides against the level ring's -0.46, which rode up the
  neck like a turtleneck); `keep_edge` shortens each walk by its drop so the outer edge stays. Below tool/face's cut
  (-0.52) the body is the same on both branches, so the seat holds on their slender neck. piece_collar 0.763 -> 0.768.
- **Torn tips** (the new `torn` measure: per piece and view, components, fragments under 2% of the largest, outline
  roughness; fine z-buffer 250 px/L round the chest): the collar's V was cut by whole quads (a staircase: the torn lapel
  tip) and is now resampled edge to edge per row (`v_edge: exact`); the bow's conform shift is smoothed
  (`front_smooth`, `conform_smooth`: its grid stepped the lobes' edges and pushed a lobe into the collar). Collar
  fragments 4 -> 2 (share 0.0023 -> 0.0006), the top's 2 -> 0 (at 667 px/L).
- **Hands clear of the skirt** (tool/rig's finding): `skirt_hull` `clear_hands` 0.05 L caps the skirt's radius clear
  of the hands, fingers, forearms and wrist bands at bind (a cone round each point). Points inside the skirt: 410 skin +
  627 band -> 0 (nearest 0.036 L); *box* poke_share 0.0134 WARN -> 0.0008 PASS; skirt widths unchanged. Cost: the
  drawing lays the (same-orange) skirt over the cuffs' inner edges, so the notes now put the cuffs over the skirt
  (same-colour rule, registered in history).
- **Loft robustness** (task 5): `tool/loft-robust` (bbc9247), merged here. See the handoff's note on i3d: the fresh
  copies' sleeve failure was masks built without the TRELLIS field.
- **flapchains**: parses the notes whole (multi-line entries); the chains are written. The graph keeps the drawing's
  chain as `drawn_chains` and `piece_*_hang` measures against it (the built chain would compare the flap with itself).
  tool/rig: the built chains are in `refs/clawd/outfit_graph.json` springs (source 'notes (the built flap)').

**Review page:** `charkit/out/review_body4/index.html` (the design over round 3 and round 4 at 0/35/90/180, close-ups of
the flaps, collar and boots, the box and evaluator numbers, the 2 x 2, the flaps against the drawn masks). The render
box's boards came back complete this round (`charkit/out/body4b_render/boards`).

**Open items:**
0. The clawd_body gate's one FAIL (body_three_quarter_iou 0.839 WARN) goes with item 1.
1. Taste call for Michael: the flaps' tails fitted to the drawn masks hang down over the outer thighs; a stronger
   train (sweep 1.2, out 0.3) reads more like the drawn profile but scores lower in front and back. The page shows it.
2. The right flap isn't the left's mirror: it sits 0.14-0.3 L further back (the skirt's hull axis is off-centre), and
   the drawn right flap is a sliver in profile and three-quarter (its iou there is 0).
3. back_iou_skin sits at the PASS line (0.70); the flaps cover the thighs' backs about as the drawing does.
4. Waistband (0.45 FAIL) and shorts (0.41 FAIL): not started.
5. The evaluator's garment cache keys a flap by its own spec, not the skirt under it: after changing the skirt,
   rebuild the Evaluator before scoring flaps.

**Gotchas (round 4):**
- A box copy without `charkit/out/i3d` builds its masks without the TRELLIS field (sleeve_L 0.08). pipeline-3d f2d0ea7
  keeps i3d on sync; a new worktree needs `cp -Rc ~/animation-pipeline-3d/charkit/out/i3d charkit/out/`.
- `flapchains` and `outfit relayer` rewrite the masks' graph, which is an input of the hull: the next local evaluator
  run rebuilds the hull (135 s) and its labels move a little.
- Scratch harness for this round (fast flap scoring by compositing z-buffers, the 2 x 2, torn, hand/skirt) is in the
  session scratchpad, not tracked; `bodyeval.Evaluator` + `bodymeasure.piece_shapes` as in round 3's gotchas.

## Checkpoint: end of round 3 (2026-09-29), superseded by round 4 above

**Branch** `tool/body` in `~/animation-pipeline-body`. The head is the commit that adds this section (see
`git log -1`). It contains `pipeline-3d` f3e8747 (merged at a456834). Round 2 is merged into `pipeline-3d` at 76d5bdc.
The authored specs are `charkit/spec/clawd_body.json` (tracked) and `charkit/out/remote/clawd_body_pieces.json`
(gitignored; it carries the same garment edits; the box sync includes `charkit/out/remote/*.json`).

**Gate state** (both into `pipeline-3d` 966ad22, on a456834, before the refit at be410e0):

| gate | verdict | detail | report |
|---|---|---|---|
| default spec | **PASS** | | `charkit/out/gate/gate_tool-body_a456834_into_966ad22.md` |
| `--spec charkit/spec/clawd_body.json` | **FAIL** | one check worse: `body_back_iou_skin` 0.731 PASS → 0.671 WARN (the flap tails hid the backs of the thighs) | `…_into_966ad22_clawd_body.md` |

The flap refit at be410e0 targets that failure: the evaluator reads 0.728 PASS. It hasn't been box-built or gated
yet. **Next step: box-build and re-gate both specs.**

**Round 3 box numbers:** `charkit/out/body3` (clawd_body.json, a456834's garments, before the refit).

| | check | round 2 | round 3 |
|---|---|---|---|
| Boots | `body_{front,back}_leg_gap` | 0.108 / 0.127 L FAIL (bridge at z −5.19 … −5.32) | 0 PASS |
| | `boot_step` (all four) | | ≤ 0.005 L PASS |
| | `piece_boot_L` / `_R` | 0.804 / 0.838 | 0.863 / 0.894 |
| Poke | `poke_share` | 0.0203 FAIL | 0.0134 WARN (wrist cuffs 44 / 37 → 0) |
| Skirt | `front_skirt_width` | 0.795 FAIL | 1.047 PASS |
| | `three_quarter_hem` | WARN | 0.0235 PASS |
| | `back_skirt_width` | | 1.102 WARN (remeasured) |
| | `front_skirt_aline` | | 0.001 PASS |
| | `three_quarter_skirt_aline` | | −0.219 FAIL (see below) |
| | `piece_skirt` | | 0.804 |
| Flaps | `piece_overskirt_panel_L` / `_R` | 0.451 FAIL / 0.526 WARN | 0.348 / 0.453 FAIL |
| | `_extent` L / R | | 0.075 / 0.042 PASS |
| | `_hang` L / R | | 0.083 / 0.095 PASS |
| Other | `body_profile_chest` | | 0.036 WARN |
| | `waist_skin` (all views) | | 0 |
| | wrist cuffs L / R | | 0.403 / 0.774 |

- The piece checks for the skirt and flaps are registered as *remeasured* (same-colour layers), but the flaps'
  geometry changed at the same step. Don't read "remeasured" as neutral.
- The refit (be410e0) in the evaluator: flap fit 0.234 → 0.329, with front 0.61 / 0.67, back 0.50 / 0.64,
  three-quarter 0.23 / 0.44, profile L 0.13.
- The review renders are on the render box's output: `charkit/out/body3_render/sheet_body.png` (the design over
  ours at 0 / 35 / 90 / 180). Its `boards/` came back empty; find out why before relying on it.
- Round 2's page is `charkit/out/review_body2/index.html`. Round 3's generator is `review3.py` in the old session's
  scratch folder, which is lost. Rebuild it from `review.py`'s pattern: the design over ours at four views, a
  MakeHuman / checkpoint / round 2 / round 3 table, crops of the boots and flaps.

**Not done: the 2 × 2 the coordinator asked for.** Score round 2's flap geometry (template panels under the skirt,
clawd_body.json at 849b9a7) and round 3's (be410e0) under both the old measure (the graph's old layer: panels
*under* the skirt) and the new one (panels *over* it, the same-colour rule in `bodymeasure.piece_shapes`). The rule
fires only when the graph's `layer.over` holds the same-coloured piece, so toggle the overskirt entries' `layer`
in a copy of the graph. Keep the masks. Then judge the flaps against the design views on the page: Michael's
complaint was "too small, tucked under", so the render comparison outweighs the piece IoU.

**Chain ownership** (one owner per stage, keeping stages cacheable):
- garments shapes the flap and defines its chain's path as data;
- tool/rig makes the bones and weights in the rig stage from the outfit graph's `springs`;
- tool/motion simulates and exports them.

`garments.flap` no longer adds bones (that made the garments stage uncacheable). It rides `hips` rigidly and
returns `chain` (bone names `overskirt_panel_L_0`…, joints, per-vertex arc length). `charkit/flapchains.py`
(`python -m charkit flapchains SPEC [--build DIR]`) writes each flap's chain into the notes as `chain`, then
relayers. `outfit.apply_notes` puts a noted `chain` into the graph's springs.
- **Its bug:** notes entries aren't all one line (lines 19, 22 and 26 span several), and `write()` parses line by
  line. It raises before writing anything. Fix: parse the whole file, set `chain`, and re-emit only the flaps'
  entries.
- Until it runs, the graph's overskirt chains are the design's (a vertical drop at the hem's radius). Tell tool/rig
  once they're written.

**Open items:**
1. **The flaps.** Box-build and gate the refit; the 2 × 2; three-quarter is still weak because the drawn tails show
   broad beside the legs and ours sit behind (try letting the tail roll outward like a flag, then refit). The tails
   are 0.40 L from the legs, which is ample for colliders.
2. **The collar onto the neck's flare.** tool/face made the neck slender, flaring into the shoulders
   (`code_base._join_neck` in their worktree, not merged yet). Our collar rides up to the torso's top ring like a
   turtleneck; the design lays a sailor collar on the shoulders and chest. Seat it on the flare: a hull-lofted
   collar, or seat the template on the body's surface below the neck. Coordinate against tool/face's branch.
3. **Torn collar tips and bow edges** near the neck in three-quarter and side views (jagged fragments). Measure
   them: small disconnected fragments per piece and outline roughness against the design's. An artifact-measurement
   workstream will provide a shared detector. Then fix them; the likely cause is near-coincident surfaces between the
   collar, bow and top.
4. **The loft on marginal coverage:** done (2c01410). `loft.field` lets the best rows stand in, warns, and records
   `LOW_COVERAGE`; the build keeps `charkit_coverage` on the object and QA reports `garment_coverage` (INFO). Still
   to confirm: a render-box build of clawd_body.json that used to die in garments.
5. **Wrist-cuff clearance:** done (cec59df). `band_hull` clears the skin by 0.006 L plus its thickness. The left
   wrist cuff's piece score is still 0.40 FAIL: the drawn cuffs are boxy, and rounding costs silhouette score.
6. **Waistband (0.45 FAIL) and shorts (0.42 FAIL):** not started.
7. The three-quarter skirt A-line (−0.22) goes with the flaps: at the hem the design's rows are widened by the
   drawn tails, which ours hide from that camera.

**Gotchas:**
- `charkit/out/hull/clawd` and `charkit/out/clawd/outfit` were hard-linked across five worktrees until 18:08, so one
  worktree's rebuild wrote through to all. They're private now, rebuilt here from this worktree's code (hull 18:18,
  outfit 18:19). Evaluator numbers from before then may differ from box builds.
- Box builds build their own hull and outfit from code plus tracked notes (the sync leaves gitignored files at home,
  except `charkit/out/remote/*.json`), so graph edits must come from `outfit.py` and the notes. That's why chains
  go through the notes.
- The render box needs `infra/gcp/render.env` (gitignored). It was copied here from `~/animation-pipeline-3d`.
- Hull labels differ by about 3% between machines at piece boundaries (a hull-determinism workstream is on it). The
  loft now degrades rather than raising.
- Gates run in parallel on `pipeline-3d` ≥ f3e8747. A non-default spec's report ends in `_clawd_body.md`.
- Interactive git (`git add -p`) doesn't work here: commit whole files.
- Fast evaluator loop: build a `bodyeval.Evaluator` on clawd_body.json with `head_code` / `body_code` from a build's
  `geom/` (e.g. `charkit/out/body3/geom`). Then run `E.geometry(spec=…).bundle('viewport')`,
  `bodymeasure.piece_views`, `piece_shapes`, `qa3d.grade_pieces` and `bodymeasure.sheet_body`: about 20 s per run,
  about 0.5 s per flap candidate when only the flap objects are swapped in a cached bundle.
- The poke proxy on the evaluator's bundle (qa3d.poke's rays against the masked skin) overcounts against the build
  (skirt 780 against 153) but ranks changes correctly.

## What changed

Each outfit piece can take its shape from the visual hull (`source: "hull"` on a garment spec), rather than from the
MakeHuman body's section at a knob's height. The design's 3D shape comes from the hull, the piece's topology from its
template, and the body supplies only weights (and, for a tight shell, the surface under it).

- `garments.hull_pieces`: the hull aligned by its eyes, as the build aligns its target, split by the hull's
  per-vertex outfit pieces.
- `charkit.geom.loft`: a piece as a radius field r(t, θ) around its own axis. It's measured from the hull's points,
  filled where no view shows the piece, smoothed with a numpy Gaussian (the builders run in Blender's Python, which
  has no scipy), and lofted into a closed quad grid.
- **Builders:**
  - `belt_hull`: the waistband. It hides the torso across its height, because the body stands out of the design's
    waist by up to 0.12 L at the sides.
  - `skirt_hull`: a waist line and a hem per angle. The waist is tucked under the band and the back hem is longer.
    Knife pleats go on top.
  - `panel_hull`: an open overskirt panel over its own angle span.
  - `bow_hull`: sized and placed from the hull, then wrapped onto the hull's front (`front_surface`).
  - A hull-sourced shell (the top) is cut at the hull's lower edge per angle.
  - `conform`: lays a thin piece onto its hull points. It's available, but off for the collar; see "Blocked".
- The bundle carries the target's per-vertex pieces (`bundle.target_pieces`).

## Measurement

- **QA part `sheet_pieces`** (checks `piece_<id>`): every object is z-buffered with its own index, and each outfit
  piece is compared with the drawn piece mask per view.
  - Graded: `iou_tol`, the overlap with a drawn line's width either side of the drawn outline left out, in the
    piece's worst view. PASS ≥ 0.75, WARN ≥ 0.5.
  - Beside it: the plain IoU, the outline agreement, and where the drawn piece's pixels land in ours (confusion).
  - A piece we don't build (the bodice panel, the bow's tails) is compared as part of its parent.
  - `piece_built` counts the pieces we do build.
- **QA part `pieces_3d`** (checks `piece3d_<id>`, INFO): each piece against the hull's points of that piece. It
  reports reach (where the design has the piece, how far ours is), excess, and the height offset.
- **Review page:** `python -m charkit pieces BUILD [--against OTHER]` gives, per piece and view, crops with the drawn
  piece tinted, its outline red and ours white, plus the numbers.

## Results (box builds, merged at 8f2ec5d: knob garments vs the waistband, skirt, top hem and bow from the hull)

| check | knob garments | hull-sourced |
|---|---|---|
| PASS / WARN / FAIL | 49 / 28 / 33 | 54 / 32 / 24 |
| body_back_hem_mid | −0.207 FAIL | 0.028 PASS |
| body_back_leg | −0.249 FAIL | 0.038 PASS |
| body_front_hem_mid | −0.089 WARN | 0.061 PASS |
| body_profile_skirt_width | 1.291 FAIL | 0.879 WARN |
| body_front_skirt_width | 1.077 PASS | 0.953 PASS |

The piece checks (iou_tol weighted over the views), both builds graded the same way by `charkit pieces`:

| piece | knob | hull |
|---|---|---|
| skirt | 0.50 WARN | 0.77 PASS |
| bow | 0.24 FAIL | 0.58 WARN |
| collar (knobs in both) | 0.53 | 0.61 |
| top | 0.29 | 0.47 |
| waistband | 0.00 | 0.40 |
| shorts (they now show below the hem) | 0.00 | 0.20 |
| overskirt panels (knobs in both) | 0.26 / 0.26 | 0.37 / 0.37 |

In 3D (piece3d, the median reach to the hull's piece), the waistband is 0.008 L, the skirt 0.009, the bow 0.036, the
sleeves 0.04, the boots 0.035. The cuffs (0.25), the shorts (0.35) and the overskirt panels (0.27–0.33) are the far
ones.

## Blocked: the body

A piece lying on the body at the design's surface ends up inside our body. The MakeHuman body isn't the design's:
- its waist sits about 0.3 L low;
- it's up to 0.12 L wider at the sides;
- its back stands out.

Conforming the collar to its hull points halved its 3D distance, but it vanished from the back view (0.72 → 0.01),
buried in the top, which is a shell of the body.

The loose pieces (skirt, waistband, bow) work because they sit outside the body or hide it. The collar, a hull-true
top, the sleeves and the cuffs need the authored body fitted to the hull first, the body's counterpart of the code
head. `geom.loft` is the tool for it: the torso as a field around a vertical axis, and the limbs around their bones.

## Not done yet

- **Overskirt panels:** lofted from the hull (`panel_hull`, not on in the spec), they reach within 0.045 L in 3D, but
  their 2D views are mixed. The hull labels the panels over about 90° round the back sides: the skirt's back shares
  their colour and stepped hem, so the labelling can't split them.
- **Shorts:** the hull's "shorts" points aren't the shorts' shape. The hull fills the hollow under the skirt, and the
  drawings' dark shorts below the hem label that filled surface. Only their lower edge (−2.72 L) is trustworthy, so
  the shorts need the 2D target.
- Sleeves and cuffs lofted around their bones, the collar, and the boots.
- The drape solver on the style profiles.

## On the authored body (tool/body, 2026-09-29, second round)

Found in the checkpoint render (1c57bb0) and by measuring. Evaluator numbers are on `clawd_body.json`, checkpoint →
now:

| piece | checkpoint | now | what changed |
|---|---|---|---|
| bow | 0.305 (hidden behind the top) | 0.646 | See the bow notes below. |
| collar | 0.407 | 0.756 | Raised to the drawn neckline (rise 0.15, v_depth 0.5, v_half 40). It had started at the neck bone's head, 0.23 L low. |
| top | 0.425 | 0.63 | The front panel is a second material by face, from the hull's bodice-panel footprint (symmetric, stray labels dropped). It had been a texture through the MakeHuman UVs, which broke into a cross. |
| wrist cuffs | 0.32 | 0.43 | `band_hull`: a band lofted round its bone through its hull piece. |
| sleeves' cream ends | 0.24 | 0.63 | `band_hull`. |
| boot cuffs | 0.52 | 0.87 | `band_hull`. |
| boots | 0.72 | 0.81 / 0.83 | `shoe_hull`: the boot's foot lofted from above the ankle to the sole. The template shoe had ballooned. |
| overskirt panels | 0.405 / 0.675 (scraps) | 0.45 / 0.52 | See the panel notes below. |
| skirt | 0.864 | 0.814 | Its hem is filled where the panels hide it, across the back (70–180°). |

The bow:
- The torso stays behind the bow and its tails by their measured depth (the hull shows them 0.02–0.06 L proud of the
  chest). Only the bow points inside the drawn bow's extent count, because the hull labels part of the lapels as bow.
- The bow takes its size from its drawn extent (`drawn_extent`, from the outfit graph).
- Its lobes are flatter (0.06 of its size), fuller at the knot (0.6), and lifted 0.03 L. The profile's front at
  −0.70..−0.80 L is now within 0.01 L of the drawing.

The overskirt panels:
- The hull labels them across ~90° of the back, and lofted they came out as twisted scraps.
- They're now the panel template, its knobs fitted to the drawn panel masks in the evaluator (iou_tol per view, plus
  the front view's reach: the lowest row and the outermost column).
- **Not fixed.** Rendered (body2_render), they read as dark, flat wedges hanging under the skirt. The design has orange
  flares with a narrow stepped hem, sweeping into a long train in profile. They also cost two grades on the authored
  spec: front skirt width 0.896 WARN → 0.795 FAIL, three-quarter hem PASS → WARN. What they should be is a taste call
  (one skirt with a longer stepped back and sides; flaps over the skirt; or flaps under it), set out on the review page.

Other fixes:
- **The waist.** The skin showing below the waistband was between the band and the skirt, not the top and the band.
  The skirt now starts under the band all round, where its own points had started lower at the front.
- **The skirt's front panel** takes the densest arc of its points (34°, not 58°).

Measurement: `body_*_skirt_width` now compares the rows neither figure has a hand against (registered in
`history.STEPS`). Each figure's widest free row had sat at a different height, because the hands hang differently.
The results, first in the evaluator, then in the box build (body2):
- profile: 1.23 FAIL → 1.00 PASS in the evaluator; 1.013 PASS in the build.
- back: 1.02 PASS in the evaluator, but **1.995 FAIL in the build**. There, no row is free of hands in both figures, so
  the check falls back to the old measure. The fix: when no row is free in both, measure ours on the design's free
  rows.
- front: 0.77 FAIL in the evaluator; 0.795 FAIL in the build. On the rows free in both, the drawn panels join the
  skirt's run and ours leave a gap. The panel change caused this (0.804 FAIL before the remeasure), not the measure.

## Box builds, round 2 (clawd_body_pieces.json; checkpoint `body_pieces` → now `body2_pieces`)

| check | MakeHuman (code_mh) | checkpoint | now |
|---|---|---|---|
| piece_bow | 0.521 WARN | 0.302 FAIL | 0.635 WARN |
| piece_collar | 0.504 WARN | 0.407 FAIL | 0.731 WARN |
| piece_top | 0.457 FAIL | 0.423 FAIL | 0.623 WARN |
| piece_waistband | 0.439 FAIL | 0.443 FAIL | 0.435 FAIL |
| piece_skirt | 0.784 PASS | 0.864 PASS | 0.803 PASS |
| overskirt panel L / R | 0.358 / 0.361 FAIL | 0.404 FAIL / 0.674 WARN | 0.451 FAIL / 0.526 WARN |
| sleeve's cream end L / R | 0.168 / 0.046 FAIL | 0.24 / 0.002 FAIL | 0.637 / 0.585 WARN |
| wrist cuff L / R | 0.175 / 0.177 FAIL | 0.321 / 0.332 FAIL | 0.443 FAIL / 0.85 PASS |
| boot L / R | 0.722 / 0.744 WARN | 0.722 / 0.567 WARN | 0.804 / 0.838 PASS |
| boot cuff L / R | 0.027 / 0.031 FAIL | 0.519 WARN / 0.446 FAIL | 0.875 / 0.823 PASS |
| poke_share | 0.02 WARN | 0.0165 WARN | 0.0203 FAIL |

The poke rise is all the hull wrist cuffs (wrist_L 14 → 44 px, wrist_R 0 → 37): `band_hull` has no clearance over the
forearm. The fix: take the larger of the loft and the skin's own field plus a margin, per row and angle.

The review page is `charkit/out/review_body2/index.html`, with renders at matching scale, the design above each, the
table and the pieces pages.

Gates, round 2:
- The default spec, tool/body 51c0733 into pipeline-3d ead7d5f: **PASS**. So does the merged head fb9d89c into
  ae55904 (`charkit/out/gate/gate_tool-body_fb9d89c_into_ae55904.md`).
- clawd_body.json, tool/body 51c0733 into ckpt/2026-09-29 35525d1 (pipeline-3d has no clawd_body.json): **FAIL**.
  Two checks got worse: body_three_quarter_hem (PASS → WARN, the panels) and poke_share (WARN → FAIL, the wrist cuffs).
  Nineteen checks improved a grade (`charkit/out/gate/gate_tool-body_51c0733_into_35525d1.md`). The gate lists
  body_front_skirt_width WARN → FAIL as "remeasured", but the panels caused it.

## Round 3 (2026-09-29): flaps over the skirt, boots, cuffs, the new checks

**The overskirt panels are flaps over the skirt** (Michael's call: separate pieces with their own physics).
- `flap()` (a `panel` with `source: flap`):
  - It lies on the built skirt from its waist (under the band) to its hem, 0.03 L plus its thickness off the pleats'
    crests.
  - Below the hem it carries on as a longer section of the skirt's cone. Each column continues the skirt's slope,
    tilted out and toward the centre back, and runs longer at the back edge. That gives a stepped diagonal in front
    and a train in profile.
  - Six bones run along its middle column (`overskirt_panel_L_0` … `_5`, the first from the waist to the hem with
    parent `hips`), weighted by arc length.
  - The tails stay 0.44 L from the legs.
- Fitted in the evaluator to the drawn panels in all four views, weighted equally: az 135°, width 0.8 L at the hem,
  narrow 0.1, length 0.4 L, train 1.0, out −0.4, sweep 0.3. The flap's pixels on the drawn skirt are left out, since
  the drawing can't separate them.
- Per view (L / R): front 0.58 / 0.57, back 0.43 / 0.48, profile 0.14.
- **Three-quarter stays weak (0.16 / 0.23).** From that camera the drawn tails show broadly beside the legs, while
  ours lie behind the skirt and legs. The views don't agree on one sheet shape. Next: let the tail twist outward
  (a flag's roll) and refit.
- The outfit graph now has the panels over the skirt, from the notes (`apply_notes`, also run by
  `python -m charkit outfit relayer`). Each spring chain names its bones.
- The piece checks leave out same-coloured layers: where a piece lies over another of its colour, those pixels count
  for neither (`px_same_colour`).

**The skirt as an A-line:** `aline` stops a column's radius narrowing toward the hem. A visual hull rounds the hem's
corners in, so the skirt read as a bubble. Front A-line FAIL → PASS. Three-quarter is still −0.22 FAIL: all its
rows have a hand against them, and at the hem the drawn tails widen the design's rows while ours are hidden.

**Boots** (`shoe_hull`):
- Each foot keeps 0.03 L off the midline. The hull had closed the gap between the feet at the sole.
- The top 0.12 L eases from the shaft's radius (the leg's skin plus the shell's offset) into the hull's section. The
  outline had stepped at the seam.
- Evaluator: leg gap 0 (round 2's box build: 0.108 / 0.127 L FAIL), boot steps ≤ 0.005 L, boots 0.86 / 0.89.

**Cuffs** (`band_hull`):
- They clear the skin by 0.006 L plus their thickness, taking the outermost skin point per cell (the thumb's base).
- Sections are drawn 0.3 of the way to their fitted ellipse, and the ends roll in.
- Wrist-cuff pokes 415 / 417 → 0 / 0 (evaluator).

**Loft robustness:** when no row reaches `min_row`, the best-covered rows stand in, with a warning. The garment
carries `charkit_coverage`, and QA reports `garment_coverage` (INFO).

**New checks** (registered in `history.STEPS`): `body_*_leg_gap`, `body_*_boot_step_{L,R}`, `body_*_skirt_aline`,
`body_profile_chest`, `body_*_waist_skin`, `piece_*_extent`, `piece_*_hang`, `garment_coverage`.
- `boot_step` compares against the design's cleaner side, because the drawing's shading splits one side's white.
- The skirt width's fallback now measures on the design's free rows.
