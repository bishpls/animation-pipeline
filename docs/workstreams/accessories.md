# Workstream: hair accessories (`tool/accessories`)

Clawd's two hair clips, the yellow star and the little red crab, which Michael called "very off-model". The
placeholders in `charkit/accessories.py` were a thin stretched four-point star and a blob; this workstream measures
them against the design, clip by clip and view by view, classes them as accessories in the QA on both sides, and
remodels and places them.

## State: Round 4 (the split: `tool/acc-reclass` first, then this branch's geometry); round 3 gated FAIL under K on palette_iris_shade's unmeasurable crossed cell only; Michael kept round 3's placement

Round 1 (`tool/accessories`, d45f27e, below) was paused 571 commits behind; it is not merged. Round 2 ported it onto
pipeline-3d, measured first, fitted the templates, placed them with the harness, updated the specs and made one hair
selection for the build and the evaluator. Harness, logs and pictures (gitignored): `charkit/out/acc_work/`; the
3ebc3fb baseline box build `charkit/out/acc_base2` (its own QA `qa/`, the new code's QA on its bundle `qa_new/`).

## Round 4: the measure lands first, alone (the coordinator's decision, 2026-09-30)
palette_iris_shade's crossed cell can't be measured while the branch changes the measure and the geometry together
(the old measure reads the fitted star as the iris). So:
1. `tool/acc-reclass`, from pipeline-3d 07fa3c2: the QA's reclass alone (accqa.py whole, the qa3d / bodymeasure /
   checks hunks, bodyeval.hair_tones only, the steps at its own commit, the accqa tests in test_accqa.py), no geometry
   (no accessories.py, scene, cli.hair_select, bodyeval.hair_selection / hair_by_outside, bodysens, specs). Gated
   into pipeline-3d with the old geometry, so the 2x2 is measurable. The coordinator merges it.
2. Then pipeline-3d merged into tool/accessories2 (the steps files resolved to pipeline-3d's: this branch's fc6269c /
   e89c90c entries dropped, so the geometry gates under one measure), and the clips' geometry re-gated (round 3's
   placement, Michael's (a)).
3. A render-box build with face and body boards (the bent star's shading), the review page updated.

### Progress
- `tool/acc-reclass`: 9bfbc8b (the code), 6e3757b (the steps at 9bfbc8b: acc_* new; body_*_iou_*, palette_iris_*,
  hair_piece_*, hair_bun_* remeasured), 9e9f5aa (pipeline-3d eb7ac94 merged: hairlocks, no QA part). New test
  `test_hair_tones_class_an_accessory_by_object` (calibrated: the old rule's family() reads the fitted star as iris).
  Pregate PASS (`charkit/out/pregate/pregate_tool-acc-reclass_6e3757b_into_859f610.md`: 11 moved, all remeasured:
  iou_hair -0.013 to -0.020, palette_iris_lit 7.06 WARN -> 2.06 PASS, palette_iris_shade 4.68 -> 4.79 on the
  evaluator). Box gate: job `gate-accessories-0930-185553-72fb` (log `charkit/out/acc_work/r4/gate_reclass.log`).
- `tool/accessories2` dc7a40a: tool/acc-reclass merged in (steps files resolved to the reclass's; test_accessories
  without the accqa tests). What's left against the reclass: the geometry only (accessories.py, scene, cli.hair_select,
  bodyeval.hair_selection / hair_by_outside / the evaluator's ground, bodysens, the six specs).
- Next: the render-box boards of dc7a40a (`charkit/out/acc_r4_render`); when the coordinator has merged the reclass,
  merge pipeline-3d here, pregate, gate.

## Round 3 (`tool/accessories2`, continued): the gate's three blockers

### Michael's decisions (2026-09-30, through the coordinator)
1. **Which view the clips honour:** the clips balance between the front and side views, the current compromise: the
   placement fit keeps its view weighting (front and three-quarter 1, profile 0.6).
2. **The star's outline:** the default dark brown outline is fine for the star (the golden `line` stays dropped).
3. **Round 3's placement stays** (Michael chose (a), 2026-09-30): the star hidden from behind and bending over the crab,
   accepting the three-quarter and profile placement cost (both clips' three-quarter pos to FAIL, the crab's profile
   iou 0.627 -> 0.492), against (b) round 2's placement with the star conformed and the back check failing.

### Blocker 1: `acc_star_back_shown` (the star shows from behind)
Harness: `acc_work/r3/lab.py` (round 2's `fitlib.Harness` on the round 2 box build `acc_new`'s hair, each clip optionally
seated on the hair alone, and a poke-through count: per view the crab's visible pixels inside the star's own silhouette).
It reproduces the gate: star back 1502 px (gate 1501), seat 0.0462.

**The float is not the whole cause.** The same pose seated on the hair alone (rigid): back 454 px (still FAIL), and
the crab pokes through the star (849 / 968 / 689 px in front / three-quarter / profile). A coarse scan round that pose
(`scan.py`: 'at' down to -0.1 L, forward / back 0.06 L, facing az 66-90, size 0.42-0.47) never got under 371 px, and
raising the facing's elevation to lie on the head made it worse (`scan_el.py`: 1,068-1,702 px). The hair's height under
the star's plane (`hmap.py`) shows why: the star faces almost level (el 3.7) on the upper side of the head, where the
hair falls away; its top tip stands 0.15-0.2 L off the hair and is what shows past the back silhouette (next to the
notch between the bun and the side lock). The design's triangulated star is 0.25 L further back and 0.12 L further in
than ours ((0.40, 0.29, 0.34) against (0.51, 0.04, 0.37), both sheets agree): the drawn place is inside our hair.
A placement scan round the head (`scan_place.py`) finds the seated star hidden from behind only further forward (the
'at' direction about 40 deg from the front): where the crab is.

**Shaping the star to the crab** (`accessories.conform`, spec `"conform": true`): the star rests on the hair alone
(seated as before, the clips before it not ground), then bends over what lies under its outline: every point of the
earlier clips inside the outline (or within `clear` of it), and the top of what lies under each of its own vertices
(cast down along its facing), needs its back `clear` (0.004 L) over it; each vertex is lifted along the facing by the
smooth envelope of those needs, each spread over `reach` (0.1 L) as (1 - s^2)^2, back and front together (its thickness
kept). The star gets `rings` (8) so it can bend: the same facets split into bands from the rim in (`rings` 1 is the old
mesh, byte for byte). At round 2's pose: poke-through 0 in every view, the bend 0.057 L, back 1,184 px.
- Tried and dropped: curving the star to the hair's quadratic under it first (`curve_to`): a 0.13 L bend, every view's
  IoU down (front 0.35, three-quarter 0.48, profile 0.57), back 2,222 px. The code is removed.
- **The seat measure** misread a bent clip: its lowest point over the plane of its middle's hair read -0.0096 for a
  star with no vertex under the hair (per vertex +0.0099). `accqa.seat`'s gap is now the least of the vertices' heights
  over the hair under them (`plane` kept in the table); registered as `acc_*_seat` (e89c90c). On the 3ebc3fb
  placeholders star 0.0204 -> 0.0153, crab -0.0144 -> -0.0127 (the same statuses); round 2's floating star
  0.0462 -> 0.0412.
- **A star-only refit that hides it** (`fit_star2.py`, from the scan's hidden start; round 2's loss and weights, the back
  + 2 + px / 40 when it shows): back 33 px, seat 0.0065, front pos 0.085 -> 0.005, but three-quarter pos 0.031 -> 0.155
  and profile iou 0.797 -> 0.705, and **it covers the crab** (crab iou 0.74 / 0.75 / 0.63 -> 0.20 / 0.12 / 0.28): the
  fit never scored the crab. Not shipped. Hence the joint fit (below).

**The joint fit (shipped)** (`fit_joint.py`, from the star-only refit; both clips' 14 knobs, Nelder-Mead, 1,037
evaluations, stopped at the 30 min limit with the last 150 moving the loss 0.002). Loss: for each clip and view (front,
three-quarter 1, profile 0.6: Michael's weighting) (1 - shape IoU) + 1.5 |log size| + 4 pos, each clip's IoU as the
QA sees it (what the other covers counts); each clip's back + 2 + px / 40 when it shows; + 20 x seat beyond 0.004 L;
+ 3 x the bend. Harness numbers on `acc_new`'s hair (round 2's pose -> round 3):

| check | round 2 | round 3 |
|---|---|---|
| star back shown | 1502 FAIL | **30 PASS** |
| star seat (per vertex) | 0.0412 FAIL | **0.0003 PASS** |
| crab through the star (px, fr / 3/4 / pr) | 0 / 0 / 0 (floating) | 0 / 0 / 0 (bent 0.046 L) |
| star iou fr / 3/4 / pr | 0.541 / 0.792 / 0.797 | 0.570 / 0.749 / 0.748 |
| star pos fr / 3/4 / pr | 0.085 F / 0.031 / 0.279 F | **0.018** / 0.098 F / 0.348 F |
| star size 3/4 | 1.128 W | 1.156 W |
| crab iou fr / 3/4 / pr | 0.741 / 0.754 / 0.627 W | 0.726 / 0.732 / **0.492 F** |
| crab pos fr / 3/4 / pr | 0.120 F / 0.010 / 0.227 F | 0.104 F / 0.066 F / 0.243 F |
| crab back shown, seat | 17, -0.0000 | 0, 0.0000 |
| the views' loss (star + crab) | 2.19 + 1.98 = 4.17 | 2.36 + 2.34 = 4.69 |

Hiding the star from behind costs 0.52 of the views' loss: both clips move forward on the head (the only place a seated
star hides from behind), which puts the front on the drawing (star front pos 0.018) and the three-quarter and profile
further off (both clips' three-quarter pos to FAIL, the crab's profile iou to FAIL: the star now covers more of it in
profile). Specs: the star's and the crab's at / facing / tilt / size, the star's `"conform": true`, in all six specs.
Against the gate's baseline (pipeline-3d's placeholders) none of these is a new FAIL. Pictures: `acc_work/r3/pic_r3.png`
(accqa.picture on the harness), `backzoom_r3.png` (the back, round 2 over round 3).

### The gate (aec2fda: pipeline-3d 8b5ecae and 07fa3c2 merged in, into 07fa3c2)
`charkit/out/gate/gate_tool-accessories2_aec2fda_into_07fa3c2.md`: **FAIL under K, one blocker** (before K: PASS).
Pregate PASS (14 moved, 0 blocking). Tests: all files ok.
1. `acc_star_back_shown` 1501 FAIL -> **31 PASS** (harness 30); `acc_star_seat` 0.0003 PASS: cleared.
2. `palette_iris_shade`: the 2x2's old measure on the new geometry still can't measure it (below): the one blocker.
3. CPU **1.11x** (685.1 -> 761.5 s): cleared. Round 2's 1.63x was one-time misses: the candidate's `resolve` (the
   produced references, whose code the branch changes) 182.6 s then, 4.4 s now from the shared cache; `hair_select`
   64.7 s and `pieces_hair` 72.0 s still ran (their keys follow the branch's code and the spec).
Reported, not blocking: 9 new acc_* FAILs (star front iou 0.57; the positions; crab profile iou 0.492; pos3d);
art_outline_face 0.481 -> 0.300, art_speckle_face 0.233 -> 0.332, art_outline_hair 0.734 -> 0.840 (INFO); the flag check
art_peeks_hair 16 -> 18 (WARN both, its grade FAIL both); body_profile_iou_hair 0.829 -> 0.795 (remeasured, PASS).
Review page (local): `charkit/out/acc_work/review/round3.html` (per view round 2 | round 3, the back zoomed, the
numbers, the palette cells, the gate).

### Decisions for Michael (round 3)
1. **Hiding the star from behind costs the side views.** The design hides it; on our hair a seated star hides only
   further forward on the head, so both clips moved forward: front on the drawing (star front pos 0.018), three-quarter
   and profile further off (both clips' three-quarter pos to FAIL, the crab's profile iou 0.627 -> 0.492). The
   alternative is round 2's placement with the star conformed (no float, no poke-through) and the back check failing
   (1,184 px), which the gate blocks. Or widen our hair where the design's star sits (0.40, 0.29, 0.34): the drawn
   place is inside our hair.
2. **palette_iris_shade's crossed cell** (for the coordinator): land the QA's reclass on its own first (accqa.py,
   qa3d.py, bodymeasure.py, checks.py, bodyeval.hair_tones, the steps: a measure-only merge with the geometry
   unchanged, so no 2x2), then this branch's geometry under one measure; or accept it by name with the evidence below.
3. The bend is flat-shaded in 8 bands: the toon ramp may split a bent facet into stripes; check the boards before a
   default (the gate builds no boards).

### Blocker 2: `palette_iris_shade` (the 2x2's crossed cell, unmeasured)
**The cause is the palette's classes, not the crab's reclass.** Measured with each tree's own code on the box builds'
bundles (`acc_work/r3`, `pal_probe.py`; the old code from a detached worktree at 3a0ad37):

| cell | ours' iris texels (kept by the colour rule) | ours' iris lit / shade | shade share | iris_lit | iris_shade |
|---|---|---|---|---|---|
| old measure, old geometry (3ebc3fb placeholders) | 1276 (276) | #ffd638 / #ecaf39 | 0.214 | 7.06 WARN | 4.63 PASS |
| old measure, new geometry (the fitted clips) | 1500 (500) | #fada7d / none | 0.065 | 2.68 PASS | **no entry** |
| new measure, either geometry | 1244 (244) | #f4ce67 / #ecad38 | 0.609 | 1.65 PASS | 4.65 PASS |

- The design's iris is the same under both measures (481 px, lit #f8d173, shade #dbab54): the reclass of the drawn
  clips doesn't touch it (the iris is taken in the eye band only). What changed is ours: the old `_scene_classes` put an
  accessory in its colour family, and a yellow star is the iris's. The placeholder star (#ffd638) joined our iris too
  (hence iris_lit 7.06), but it was small: the shade share stayed 0.214. The fitted star (#fada7d, the drawing's own
  colour) is about 10x the iris plate's area, so the old measure's iris is the star: one tone (share 0.065, under
  `paletteqa.SHADE_MIN` 0.08), and `paletteqa.compare` skips a class's shade tone when ours has none and the design has
  one, with no entry at all (not even SKIPPED).
- So the check is registered correctly (`palette_iris_*`, the step at fc6269c: its text was wrong, it said the design's
  star facets; now it says what moves) and the geometry doesn't move it under the new measure (4.65 on both; the
  iris plate's texels are the same 244). Its old-measure cell on the new geometry can't be measured by construction:
  the old measure reads the new star as the iris. No change on this branch can make the base's code read it.
- Not a gate bug: the gate does what policy K says (a crossed cell that can't be measured blocks). Two things for infra,
  with this as the evidence: (1) `paletteqa.compare` drops a check silently when ours loses a tone the design has (it
  should report it, graded or SKIPPED with why), so the gate can only say "unmeasured", not why; (2) a remeasure that
  fixes a measure the new geometry breaks (here: the old classes can't tell the new star from the iris) can never fill
  its old-measure cell. The clean route is to land the measure change on its own first (the QA's reclass alone, with
  the geometry unchanged: no 2x2), then the geometry under one measure. See "The split" below.

## Round 2

### The port
- Taken whole from d45f27e: `charkit/accessories.py`, `charkit/accqa.py`, `charkit/tests/test_accessories.py`.
- Re-applied to the current files: `bodyeval.hair_tones` and the evaluator's clips on the built hair (ground),
  `bodymeasure.Sheet` (the reclass on both sheet paths), `bodysens.ACCESSORY_AT`, `checks` (acc_* overlays and
  sections), `qa3d` (`Design.design_views` reclass, `Design.clips`, `_scene_classes`' accessory class,
  `hair_layers_masks` minus the drawn clips), `scene.stage_hair` (ground).
- The QA part registers itself in `accqa.py`: `@qa_part('accessories', order=2400, table='accessories')`.
- Steps: `charkit/steps/accqa.py` (`acc_*`, new) and, where those patterns already live, `charkit/steps/qa3d.py`
  (`body_*_iou_*`, `palette_iris_*`, `hair_piece_*`, `hair_bun_*`), all at fc6269c.

### 1. Measure first
**The design side against the hand-checked truth** (`outfit_truth.npz`, body turnaround, bodyqa grids;
`acc_work/m_truth.py`): accqa's colour-plus-region finder against the new sheet-only outfit masks, IoU per view.

| clip | view | accqa | outfit masks |
|---|---|---|---|
| star | front / 3/4 / profile | 1.000 / 1.000 / 1.000 | 0.936 / 1.000 / 1.000 (+93 px in the back) |
| crab | front / 3/4 / profile | 1.000 / 1.000 / 1.000 | 0.881 / 0 / 0 |

So the QA keeps accqa's finder for the design's clips (the outfit masks lose the crab in two views).

**The reclass alone** (the new code's QA on the 3ebc3fb baseline's bundle, same geometry; `acc_work/reclass_diff.json`):
16 checks move, all remeasures: `body_*_iou_hair` 0.840 -> 0.827 (front), 0.757 -> 0.743 (3/4), 0.829 -> 0.809
(profile): the placeholders sit where the design draws hair, and now count against it on both sides; `iou_outfit`
+0.002..+0.004, `iou_cream` +0.005..+0.011; `palette_iris_lit` 7.06 WARN -> 1.65 PASS (the star's pale facets had been
the design's iris); `hair_piece_bangs` 0.792 -> 0.772, `side_locks` 0.534 -> 0.526, `ahoge`, `upper_back`,
`hair_bun_outline` within 0.004. Registered as steps (above); the gate's 2x2 checks them under the old measure.

**Calibration** (`acc_work/calib.py`): the body turnaround's clips (an independent drawing of the same design) moved
onto the head turnaround's grids and measured as "ours": worst iou 0.736 (the crab's profile), size 1.064, pos 0.033 L
(the star's profile), angle 6.5 deg. The limits were set from this before any fit: iou pass 0.72 (was 0.75), pos pass
0.035 L (was 0.03); size, angle, seat and pos3d unchanged. The design passes every graded check; the placeholders
fail 26 of 30.

**Baseline at 3ebc3fb** (the placeholders under the new code's QA; ours / design):

| clip | view | iou | size | pos (L) | angle |
|---|---|---|---|---|---|
| star | front | 0.500 FAIL | 0.533 FAIL | 0.096 FAIL | -3.1 PASS |
| star | 3/4 | 0.547 FAIL | 0.531 FAIL | 0.245 FAIL | -1.6 PASS |
| star | profile | 0.552 FAIL | 0.447 FAIL | 0.453 FAIL | 2.9 PASS |
| crab | front | 0.518 FAIL | 0.402 FAIL | 0.124 FAIL | -32.6 FAIL |
| crab | 3/4 | 0.523 FAIL | 0.395 FAIL | 0.237 FAIL | -31.5 FAIL |
| crab | profile | 0.492 FAIL | 0.281 FAIL | 0.343 FAIL | 81.2 INFO |

pos3d star 0.427 FAIL, crab 0.337 FAIL; seat star +0.020 FAIL, crab -0.014 WARN; colour dE star 7.19, crab 5.51 WARN.

### 2. Templates fitted to the design's clips (`acc_work/fit2d.py`)
One shape for all three views of the head turnaround, a similarity per view (rotation, x-squash, size, offset),
Nelder-Mead from explicit simplices with real steps on every parameter (round 1's crab rotations never left 0), three
restarts. The crab is scored where the star doesn't cover it. Per view: the fit's IoU and the QA's shape IoU.

| template | front | 3/4 | profile | the shape |
|---|---|---|---|---|
| star, round 1's shape | 0.809 / 0.761 | 0.826 / 0.795 | 0.854 / 0.804 | |
| star, fitted | **0.825 / 0.767** | **0.845 / 0.791** | **0.891 / 0.815** | up 0.542, down 0.538, side 0.373, minor 0.295, inner 0.159, curve 0.045 |
| crab, round 1's shape | 0.673 / 0.638 | 0.673 / 0.615 | 0.623 / 0.594 | |
| crab, fitted free | 0.861 / 0.843 | 0.814 / 0.794 | 0.782 / 0.754 | legs shrank to 0.061: dropped |
| crab, fitted, legs >= 0.15 | **0.855 / 0.838** | **0.796 / 0.758** | **0.802 / 0.786** | body_h 0.892, claw 0.588 at (0.566, 0.377), claw_up 9, arm 0.131, leg 0.165, leg_span (-22, -73) |

The free fit bought 0.001 of loss by dropping the drawn legs (ours pointed the wrong way); bounded, the legs stay and
turn down-left as drawn at no real cost, so the bounded fit ships (a model feature, not a number).

### 3. The placement fit (`acc_work/fit3d2.py`, resumed by `fit3d2b.py`; the harness `fitlib.py`)
On the 3ebc3fb baseline's hair (bundle `acc_base2`), the fitted templates placed by at / facing / tilt / size: the
star alone (466 evaluations), the crab under it (the star resting on it), the star again on the crab. Loss per view
(front, 3/4 weight 1, profile 0.6): (1 - shape IoU) + 1.5 |log size ratio| + 4 pos (L), + 1 when shown in the back,
+ 20 x seat beyond 0.004 L. The first run was stopped at 30 min in the crab phase (loss 1.980) and resumed from its
best. Final loss: star 4.02 (3.00 alone: the +1 is the back view), crab 1.978.

| clip | view | iou | size | pos (L) | angle |
|---|---|---|---|---|---|
| star | front | 0.542 FAIL | 0.944 | 0.085 FAIL | 4.0 |
| star | 3/4 | 0.797 | 1.127 WARN | 0.030 | 3.4 |
| star | profile | 0.798 | 0.998 | 0.279 FAIL | 3.4 |
| crab | front | 0.741 | 1.000 | 0.120 FAIL | 13.1 WARN |
| crab | 3/4 | 0.754 | 1.094 | 0.010 | -2.7 |
| crab | profile | 0.627 WARN | 0.939 | 0.227 FAIL | 10.4 WARN |

Seats: star +0.046 L FAIL (it rests on the crab's body), crab -0.0014 PASS. Back view: the crab hidden, the star shows
1,501 px (FAIL).

**Tried and dropped: the star on the hair alone** (a `rests_on: hair` knob, `fit3d2c.py`): seat 0.005, but the front
iou 0.445, the back still 778 px, and the crab's hidden claw pokes through the star (crab 3/4 iou 0.581). Worse; the
knob is not shipped.

**Why the front and profile positions still fail.** The drawings put each clip face-on in every view and at places no
one 3D point satisfies (round 1: triangulation residual ~0.045 L; our hair at the clips' height is narrower than the
drawing's, so the drawn 3D place is inside our hair and seating pushes the clips out). A flat star facing 66 deg to
the side reads face-on in profile (iou 0.80) and foreshortened in front (0.54); the fit trades the views by the
weights above. This is a decision for Michael (below), not a tuning gap.

### 4. The specs
`clawd.json`, `clawd_body.json`, `clawd_body_pieces.json`, `clawd_code.json`, `clawd_locks.json`, `clawd_mh.json`:
crab then star, `at` (L from the head's centre), `facing` [az, el], `tilt`, `size` (the star's height tip to tip
0.466 L, the crab's body width 0.153 L), the fitted shapes, the measured colours (star #fada7d, crab #d26544); the
placeholders' az / el / lift and the star's golden `line` dropped (the drawing inks both clips dark: the default
outline). Only the accessories block's text changes in each file. Only clawd.json is verified on the box (policy K).

### 5. One hair selection for the build and the evaluator (crab_1's stage drift)
- `bodyeval.hair_selection(spec)`: the evaluator's own `select_hair` on its own assembly (after the cranium fit), the
  gridded face cull. `cli.hair_select`, a cached venv step before the hair steps, writes it to
  `geom/hair_select.npz` and points `hair.shape.selection` at it; `scene.hair_shape_volume` reads it in place of
  Blender's BVH selection (`CHARKIT_HAIR_SELECT=blender` keeps the old path).
- The sign is tie-free: `bodyeval.hair_by_outside` signs by the angle-weighted pseudo-normal at the nearest feature
  (`BVH.signed_distance(sign='normal')`), not the face the BVH reached first. On the 3ebc3fb hull it decides 1,499 of
  75,006 vertices' `clear` test differently from the old face-normal sign (1,270 sign flips); the selection keeps
  19,919 vertices (19,917 on the box), 30 s with the assembly, 11.7 s as the build's step.
- **Measured** (`evaldrift --stages` on the placeholders' spec, the clips still on the volume; box,
  `charkit/out/acc_drift_old`): crab_1 **2.05e-4 L -> 4.06e-7 L** (mean 2.7e-7), star_0 2.6e-7; no stage drifts
  (GEOM_TOL 1e-5); 0 of 110 checks drift. With the fitted specs the clips no longer read the volume at all (placed by
  `at`, seated on the built pieces).
- Test: `test_hair_by_outside_sign_is_tie_free` (a cube's edge and corner).

### 6. The box builds, the review page, the gate
- After (box build `charkit/out/acc_new`, clawd.json at 7d1ab98) against before (`acc_base2/qa_new`): the harness's
  numbers reproduce exactly. Graded acc_* checks: before 23 FAIL; after 19 PASS, 4 WARN, 9 FAIL. Colour dE: star
  7.19 -> 0.04, crab 5.51 -> 0.30. pos3d: star 0.427 -> 0.277, crab 0.337 -> 0.254 (both still FAIL).
- Render box: `charkit/out/acc_new_render` (boards views, body). Review page (local, gitignored):
  `charkit/out/acc_work/review/index.html` (per view the QA's close-ups before and after at one scale, the numbers,
  the face boards before / after / EEVEE after).
- Merged pipeline-3d 3a0ad37 into the branch (b9d9823; one conflict in bodyeval.hair_by_outside: i3d renamed
  target3d). Tests 544 passed. Pregate PASS (31 moved, 0 blocking; body_profile_chest 0.013 -> 0.045 WARN on the
  evaluator, not seen by the gate).
- **Gate** (`charkit/out/gate/gate_tool-accessories2_b9d9823_into_3a0ad37.md`): **FAIL under K**, 3 blockers:
  1. `palette_iris_shade`: the 2x2 couldn't measure it under the old measure on the new geometry (4.63 PASS on the
     old geometry, 4.65 PASS on the candidate): unverified, not worse;
  2. `acc_star_back_shown` 0 -> 1501 px FAIL under the new measure on both geometries: the star, resting on the crab,
     shows from behind (the known fault of step 3);
  3. CPU 1.63x (591 -> 966 s). My like-for-like box builds: 890 -> 952 CPU s (+7%); the gate's baseline likely
     restored stages the candidate had to run (the new hair_select step; `hair.shape.selection` in the spec changes
     garments_geom's and pieces_hair's keys). Unverified.
  Reported, not blocking: 9 new acc_* FAILs, art_outline_face 0.481 -> 0.376 INFO, art_outline_hair 0.734 -> 0.799
  INFO, hair_noise 0.0791 -> 0.0776 WARN.

### Decisions for Michael
1. **Which view the clips honour.** The drawings put both clips face-on in every view and at no single 3D place. The
   fit weights front and 3/4 at 1 and profile at 0.6: the front star reads foreshortened (iou 0.54), and the profile
   places are 0.23-0.28 L forward of the drawn ones. The options: re-weight, let the clips turn toward the camera per
   view (a rig or shader trick, not geometry), or widen our hair at the clips' height so the drawn place lies on it.
2. **The star over the crab.** Resting on the crab lifts the star 0.046 L and shows it from behind (the blocker);
   resting on the hair alone lets the crab's claw poke through it. The fix is to shape the star to the crab (tilt or
   bend it where they overlap), or to accept the float.
3. The CPU blocker: re-gate with warm caches, or accept the one-time misses.
4. The outline colour of the clips (the default dark brown; the golden star line was dropped).

## Round 1 (tool/accessories, d45f27e): PAUSED (2026-09-29, coordinator's request to cut concurrency)

Nothing is running: no box jobs, no local jobs (the local placement fit was stopped; its best-so-far is below).
Local outputs (gitignored): the baseline box build `charkit/out/acc_base` (bundle and its QA), the fit harness, logs
and pictures in `charkit/out/acc_work`.

**Work in progress: don't gate or merge this commit as it stands.** The new generators and the seating already change
the build, but the specs still carry the placeholders' knobs (az / el, `size` 0.16 meaning the old star's scale where
it is now the height tip to tip), so the clips come out smaller and elsewhere until step 3 lands.

| step | state |
|---|---|
| 1. measure first (`charkit/accqa.py`) | done: design clip crops, our silhouettes, per-clip checks; baseline numbers below (all FAIL) |
| 2. classify by object | code done, **not yet measured**: `qa3d.Design.design_views` reclasses the drawn clips, `qa3d._scene_classes` and `bodyeval.hair_tones` class ours as `accqa.ACCESSORY` (5), `qa3d.hair_layers_masks` drops the drawn clips from the hair families; STEPS entry not yet added (needs the commit that lands it) |
| 3. remodel (`charkit/accessories.py`) | generators and placement rewritten; a fit harness found placements (below); **the spec is not yet updated** |
| 4. gate | not run |

### Code written so far (committed on `tool/accessories`)

- `charkit/accqa.py`: the design's clips (`clip_pieces`, `design_clips`, `design`, `design_sheets`, `design_all`),
  measures (`measure`, `shape_iou`, `compare`, `triangulate`, `seat`), ours (`clip_objects`, `our_labels`,
  `evaluate`), the reclass (`window_to_grid`, `grid_masks`, `reclass`), pictures (`picture`).
- `charkit/qa3d.py`: QA part `accessories` (checks `acc_KIND_VIEW_{iou,size,pos,angle,shown}`, `acc_KIND_pos3d`,
  `acc_KIND_seat`, `acc_KIND_colour`; overlays `qa_accessories.png`, `qa_accessories_body.png`); `Design.clips()`;
  the reclass in `Design.design_views()`; `_hair_material`; hair layers minus the drawn clips.
- `charkit/checks.py`: `acc_*` sections and overlays (not in MEASURES: graded as the piece checks are).
- `charkit/bodymeasure.py` `Sheet`, `charkit/bodyeval.py` `hair_tones` and `hair_parts`: the same classing and the
  hair ground for the fast evaluator.
- `charkit/accessories.py`: `star_outline` / `star` (n major points with up / down / side lengths, optional minor
  points, valleys, concave edges as a radial pull, a raised faceted middle), `crab` (body, notched claws on arms, eyes
  on stalks, legs; per-face materials: 1 = the eyes), placement `at` (L from the head centre) + `facing` [az, el] +
  `tilt`, seating on `ground` (the built hair; each clip also rests on the clips listed before it), `hair_ground`
  (Blender objects -> meshes), `build(..., ground=)` with a second material for the crab's eyes. Buns keep the old
  volume placement (`_frame`). Old specs (az / el, no `at`) still build: the clip is anchored at `V.point(az, el)`
  and, with ground, seated along its facing.
- `charkit/scene.py` `stage_hair`: passes `ground=accessories.hair_ground(S.hair)`.
- `charkit/bodysens.py`: `ACCESSORY_AT` knobs for `at` / `facing` clips.
- `charkit/tests/test_accessories.py`: 8 tests (pass).
- Not touched on purpose: `bodyqa.py` and `paletteqa.py` (both are in the hull's and outfit masks' produced-reference
  stamps: editing them rebuilds the hull in every worktree), so `ACCESSORY = 5` lives in `accqa` (bodyqa's free id),
  and `bodyqa.PALETTE` has no colour for it (the clips paint black in `qa_sheet_body.png`). `qa3d_blender.py` (the old
  `--qa blender` pass) still classes clips by colour family.

### Exact next steps

1. **Measure the reclass alone** on the baseline bundle, before any remodel:
   `python -m charkit qa charkit/out/acc_base/bundle --out charkit/out/acc_base/qa_reclass --cache off`, then diff
   its `qa.json` against `charkit/out/acc_base/qa/qa.json` (the box build's own QA, pre-reclass): the hair checks
   (`body_*_iou_hair`, `body_*_hair_*`, `body_*_top`, `palette_hair_*`, `palette_iris_*`, `hair_piece_*`,
   `hair_bun_*`, `hair_fringe_*`, `sheet_shown_*`) and the outfit ones (the star's pale facets were `cream` on the
   design side: 500 px of front "outfit"). Record the movement here; add a STEPS entry in `charkit/history.py` for
   each pattern whose measurement changes (`body_*`, `palette_*`, `hair_piece_*`, `hair_bun_*`, `hair_tips_*`) with
   the commit that lands the reclass. Commit.
2. **Finish the placement fit** (harness in `charkit/out/acc_work/`, gitignored: `fitlib.py` + `t_fit3d.py`; run from
   the worktree root with `PYTHONPATH=.`; ~1.3 s an evaluation on the laptop). Best so far, eye-frame at (x her left,
   y toward her back from the eyes' middle, z up from the eye line; the spec's `at` adds `Harness.eye_off` =
   (0, -0.344, 0.003) L to get the head-centre frame):
   - star: at (0.419, 0.103, 0.336), facing (58.7, 0.8), tilt 2.2, size 0.424 (height tip to tip, L), shape from the
     2D fit (`star2d.json`: up 0.52, down 0.471, side 0.371, minor 0.283, inner 0.168, curve 0.02), loss 2.985 (three
     views summed; per view (1 - IoU) + 1.5 |log size ratio| + 4 pos);
   - crab (with that star over it): at (0.289, 0.020, 0.285), facing (45.9, -0.6), tilt 3.4, size 0.159 (body
     width, L), shape body_h 0.78, claw 0.31, claw_at (0.5, 0.55), claw_up 36, leg 0.2, leg_r 0.03; loss 2.512 and
     still falling when stopped (iteration 155).
   The fit ran before the concave-edge change (edges are now pulled radially; `curve` 0.02 is negligible either way)
   and before `accqa._tones` handled flat regions (no effect on real drawings). Look at the per-view numbers and
   pictures (`H.measure(..., verbose=True)`, `H.picture`, `H.scene_picture`) before trusting the loss: the star is
   at its best a compromise, because the drawings put the clips face-on in every view and not at one 3D place
   (triangulation residual ~0.045 L; `accqa.triangulate`).
   Open question found on the way: our hair at the clips' height is narrower than the drawing's (the star sits 0.44 L
   out in the front drawing, near our hair's silhouette edge), so the design's 3D place is inside our hair and seating
   pushes the clips out; the front and three-quarter positions are weighted 1, the profile 0.6.
3. Put the fitted clips into `charkit/spec/clawd.json` and `clawd_body.json` (and `clawd_body_pieces.json`,
   `clawd_code.json`, `clawd_locks.json`, which carry the same accessories): order crab then star (the star rests on
   the crab), `at`, `facing`, `tilt`, `size`, `shape`, and the measured colours (star lit #fada7d, crab #d26544; the
   outline is the look's ink in the anime style). Check the crab 2D shape against the design (`t_crabfit.py`: IoU
   0.60-0.66 on its first fit; its rotation parameters never moved off 0 in Nelder-Mead: give them a real initial
   step).
4. Box builds of both specs (`python -m charkit remote build SPEC --out charkit/out/acc_new --boards views
   --no-blend`), the QA's `acc_*` checks before/after, the review page (design crops beside ours, before and after,
   per view, at one scale: `accqa.picture` per sheet), board renders on the render box
   (`python -m charkit remote --box render build SPEC --out DIR --boards views,body`).
5. Gates: `python -m charkit remote gate tool/accessories --into pipeline-3d` and the same with
   `--spec charkit/spec/clawd_body.json`.

## The design's clips

Sources: the head turnaround (`sheets.face`, ~401 px/L at its own resolution; graded) and the body turnaround
(`sheets.body`, the bodyqa grids at ~212 px/L; information, and the source of the design-side reclassing). The
outfit graph has both clips as pieces (`pin_star`, `pin_crab`, type `hair accessory`), with their colours, but its
per-view extents are the outfit field's votes (the crab's front extent is 0.05 L wide against a drawn 0.17 L), so
`accqa.design_clips` finds them in each view by a colour-plus-region rule:

- every pixel of the head window takes the nearest (CIELAB) of the clips' colours and the view's own hair, skin and
  paper tones; dark pixels are line;
- two passes: the graph's colours find each clip's seeds; the seeds' own median, lit and shade tones then class every
  pixel again (the graph's crab colour, measured on the rig, is more saturated than the turnarounds' crab);
- each region between the drawn lines takes the clip most of its pixels are nearest to, when that is most of them;
- a clip is its colour's components above the eye line, clear of the eyes and the window's edge (a neighbouring
  head's clip), within 0.12 L of the largest; closed over the lines inside it, holes filled, plus the outline's inner
  half (the QA's convention: lines are absorbed into what they bound);
- on the body turnaround the crab's body reads closer to the hair's tone than its seeds, so the head turnaround's
  clips, registered by the star's centroid, are a prior: a cell mostly inside it is the clip's.

What the design draws (all three views; the back hides both):
- **the star** has eight points, not four: four major (up and down about equal, the sides about 0.7 of them) and four
  minor diagonal ones (about 0.55), straight edges, a valley radius about 0.17 of the height, and a bevelled face (each
  point a lit and a shaded half). 2D fit of `star_outline` to the three views' masks (aligned on centroid and area):
  up 0.52, down 0.47, side 0.37, minor 0.28, inner 0.17, curve 0.02 (of the height), IoU 0.73 / 0.78 / 0.82.
- **the crab**: a flattened round body, a big notched claw raised on an arm at its upper left, the other claw behind
  the star, eyes on stalks, three thin legs a side.
- The generated turnarounds draw both clips nearly face-on in every view, and not quite at one 3D place: triangulated
  from the three views' centroids, the star's front, three-quarter and profile positions disagree by up to 0.05 L.

## Baseline (pipeline-3d at 6b1d500, box build `charkit/out/acc_base`)

The placeholders measured against the head turnaround (`accqa.evaluate` on the box build's bundle; ours / design):

| clip | view | shape IoU | size (sqrt area) | position off | axis | notes |
|---|---|---|---|---|---|---|
| star | front | 0.522 FAIL | 0.528 FAIL (0.085 / 0.160 L) | 0.103 L FAIL (dx -0.036, dz +0.096) | -1.3 deg PASS | h 0.21 / 0.38 L |
| star | three-quarter | 0.548 FAIL | 0.533 FAIL | 0.225 L FAIL (dx -0.204, dz +0.094) | -1.9 PASS | |
| star | profile | 0.558 FAIL | 0.453 FAIL | 0.472 L FAIL (dx -0.465, dz +0.083) | 0.6 PASS | ours 0.14 L in front of the eyes, the design's 0.32 L behind |
| star | back | hidden in both PASS | | | | |
| crab | front | 0.513 FAIL | 0.399 FAIL (0.051 / 0.127 L) | 0.186 L FAIL (dx -0.046, dz +0.181) | -33 FAIL | |
| crab | three-quarter | 0.514 FAIL | 0.394 FAIL | 0.273 L FAIL | -32 FAIL | |
| crab | profile | 0.491 FAIL | 0.300 FAIL | 0.393 L FAIL | -64 FAIL | |
| crab | back | hidden in both PASS | | | | |

3D: the star's triangulated place is 0.44 L from the design's, the crab's 0.38 L (both too far forward, and 0.08-0.18
L too high); seat: star 0.0085 L over the hair, crab 0.007 L into it; colour dE00: star 7.2 WARN (#ffd638 against the
drawn #fada7d), crab 5.5 WARN (#e04c33 against #d26544).

In short: both clips are about half the design's size, sit high and on the front of the head where the design puts
them on its side under the bun, and the star is thin with no minor points.
