# Differentiable silhouettes (`tool/softras`)

Roadmap: "Changes, ranked" item 5 (differentiable silhouettes in `charkit.render`, so template fits optimise with
gradients rather than by sampling; hand-rolled, because nvdiffrast is non-commercial) and "To hand-roll" item 4 (soft
silhouette rasterisation).

**Branch** `tool/softras` in `~/animation-pipeline-softras`, from pipeline-3d 2f42155.

A pilot behind a setting: no default changes. Files: `charkit/render/softras.py` (the rasteriser), the fit harness,
and an opt-in gradient path in `charkit/fitkit.py`.

## Plan

1. A soft silhouette rasteriser with analytic gradients with respect to vertex positions (numpy + numba), on the same
   cameras as charkit.render (`views.camera`) and the QA's measuring windows (`geom.raster.window_project`, the sheet's
   grids). Tests: gradients against finite differences; convergence to the hard silhouette as the softness goes to 0
   (IoU against charkit.render's silhouette at the same camera); timing per view.
2. The chain: template parameters -> vertices (the template builder; finite differences where there's no cheap
   analytic Jacobian) -> silhouettes -> an IoU loss against the design's per-view masks.
3. Pilot: the flap template (`garments.flap_template`, the skirt's fit G), against its coordinate descent, from the
   same start: wall time, evaluations, final objective, the flap's IoU in every view.
4. Report: where gradients pay, where the objective is non-smooth, how fitkit could offer a gradient path.

## The rasteriser (`charkit/render/softras.py`)

numpy + numba, no GPU, no new dependency (torch 2.11 is in the venv but not needed: the kernels are a few ms a view).

- **Soft coverage from the contour's signed distance.** Hard coverage C is the QA's own (`geom.raster._raster`, pixel
  centres, the same tie tolerance). Only pixels near the silhouette's contour change: F(p) = k(sign(p) d(p) / s), d the
  distance from p's centre to the nearest contour segment, sign +1 where C covers p, s the softness in px, k the
  logistic k(x) = 1 / (1 + exp(-4x)) (or `linear`, clip(0.5 + x, 0, 1): at s = 1 about a box filter's area
  coverage). Elsewhere F = C, exactly. dF/dvertex is analytic (a point-to-segment distance).
- **Finding the contour.** Every visible covered pixel beside an uncovered one: the segment between their centres is
  walked through the union of the triangles over the two pixels (each triangle's interval along it, chained from the
  covered end); where the union ends is a contour point, on the edge of the triangle it leaves through. Each edge is
  kept over the span of its points plus 1.5 px, so an edge that runs on inside the union (a fold, a far layer) isn't
  taken for contour there.
- **Occlusion.** A depth image of everything else (`occ`) hides the mesh where it is nearer, as the QA composites by
  depth. That boundary stays hard (not differentiated): it moves only with depth.
- **Why not SoftRas's aggregation** (1 - prod (1 - D_j), a sigmoid per triangle): every internal edge is a soft edge
  too, so the interior dips along them. Measured on the flap (1036 vertices, back view, s = 0.5 px): interior mean
  coverage 0.925, 33% of its covered pixels under 0.9, the summed coverage 7% short (26926 against 29007 px).
  `softras.aggregate` keeps it for the comparison.
- **Cameras.** `SheetView` is the QA's measuring window (`geom.raster.window_project`: bodyqa's azimuths and origins on
  the sheet's grid); `CameraView` is charkit.render's (`views.camera`, glTF or Blender frame, orthographic or
  perspective; pixel y = (1 - ndc y) / 2 H).
- **Work on a crop** round the mesh (its bounding box plus the reach): a view at the QA's full-body window
  (977 x 1594) costs its crop only.

### Tests (`charkit/tests/test_softras.py`, all pass on the laptop)

| test | result |
|---|---|
| gradient vs central differences (h = 1e-4 px), a twisted open panel, SheetView at 30 deg, s 1 and 0.5 | cosine 1.000000; relative error median 3e-9 / 1e-8, p95 2e-8 / 3e-8 (46 coordinates) |
| the same with an occluder over half the panel | median 9e-9, p95 2e-8 |
| a non-convex blob through charkit.render's perspective camera (85 mm) | median 2e-9, p95 2e-8 |
| convergence: sum \|F - C\| over the view as s -> 0 (328 contour points) | 208, 104, 52, 10.1, 0.99, 0.000 px at s 2, 1, 0.5, 0.1, 0.01, 0.001; F = C off the contour band exactly; IoU(F >= 0.5, C) 1.0 |
| box filter: `linear` at s = 1 | a square's edge columns read 0.7 and 0.3, exact |
| against charkit.render (gpu.ids at ss 1, the blob, orthographic and 85 mm) | IoU 0.99991 (1 of 10597 px differs: a tie) and 1.00000 (0 of 24228), hard and soft at s 0.5 and 0.01 |
| time per view, the QA's full-body window (977 x 1594, ~1000 vertices, ~18k px covered), warm | forward 1.7 ms (raster 0.8, contour 0.3, field 0.5), backward 0.03 ms |

On the flap itself (1036 vertices, 846 quads, back view): 5 ms a view forward with the occluder; its contour 107 edges
from 1147 points.

## The chain and the pilot harness (`charkit/render/softfit.py`)

- **The frozen scene** (`python -m charkit.render.softfit scene`, 116 s once, `charkit/out/softras/flap_scene.pkl`):
  the evaluator's assembly and hull (what `garments.flap` reads), the spec, bodyqa's windows per view (front,
  three-quarter, profile, back, and profile_R: the profile from the other side, mirrored onto the drawn near flap, as
  skirtqa reads the right flap), the scene without the flaps z-buffered once per view (depth, object labels, the
  side-split labels piece_shapes reads), the drawn flaps (skirtqa.drawn_pieces), the outfit masks and graph. The skirt
  harness's `fast.py` compositing, frozen: a candidate costs its two flaps' builds and their rasterisation only.
- **The objective** J = sum over skirtqa's flap IoUs (flap_{view}_iou_{L,R}: the flap's visible pixels against the
  drawn flap) of VW[view] (1 - IoU), fit G's view weights (back 1, profile 1, front 0.7, three-quarter 0.4). Every J
  and IoU reported is the hard one, on the QA's pixels. The piece IoUs (qa3d.grade_pieces over
  bodymeasure.piece_shapes) are reported beside it for every start and result (no gaming).
- **The knobs**: fit G's (skirt_scratch/fit.py PARAMS) less `band` (the band's material and rows, not the
  silhouette): e1o, e1i (the edges' azimuths at the hem), standm, stand1 (the standoff), first, rise (the stair),
  droop, out, twist; their steps and bounds as fit G's.
- **The chain**: dJ/dV from the silhouettes (each flap's, the other flap and the frozen scene as its occluder), then
  dV/dknob by central differences of the builder at 0.01 step (the builder takes 3 ms). The builder re-samples its rows
  and columns on the stair's corners and the band's edges (`first`, `rise`, the edges), so a vertex's two one-sided
  differences can disagree (a row slid past another): there the smaller is taken; a knob whose builds change the faces
  on both sides falls back to differences of the soft J itself. Checked against differences of the soft J at 0.05
  step: within 1-8% on every knob (the 0.05-step differences carry the builder's re-sampling).
- **Coordinate descent** as the skirt ran it (fit.py): each knob a step up then down, the first move that lowers J
  taken and the sweep begun again, a sweep with no move halving every step, until three halvings; fit.py caps it at 12
  sweeps (a move or a halving each). Run both as written and to convergence.
- **The gradient fit**: L-BFGS-B (scipy) on the soft J at softness s, in steps from the start within the bounds.

## The pilot: the flap template, gradient against coordinate descent (laptop, M2 Pro, one process)

Starts: **g** = fit G's own start (skirt_scratch/t8.json's knobs), **far** = every knob 2-6 steps off it. J and the
IoUs are hard (the QA's pixels); "evaluations" are J evaluations for CD (a build and a hard render of 5 views, 66 ms) and
gradient evaluations for L-BFGS (a soft render with its backward and 19 builds for dV/dknob, 170-210 ms). Records:
`charkit/out/softras/fit_*.json`; page `charkit/out/softras/index.html`.

| start | fit | wall s | evaluations | builds | J | front L/R | 3/4 L/R | profile L/R | back L/R | piece L | piece R |
|---|---|---|---|---|---|---|---|---|---|---|---|
| g | start | | | | 2.1846 | 0.680 / 0.688 | 0.029 / 0.016 | 0.675 / 0.674 | 0.853 / 0.837 | 0.653 WARN | 0.759 PASS |
| g | CD as fit.py runs it (12 sweeps) | 4.8 | 71 | 71 | 1.8869 | 0.708 / 0.727 | 0.024 / 0.000 | 0.780 / 0.779 | 0.885 / 0.854 | 0.705 WARN | 0.791 PASS |
| g | CD to convergence | 15.6 | 235 | 235 | 1.8413 | 0.755 / 0.773 | 0.024 / 0.000 | 0.752 / 0.751 | 0.903 / 0.873 | 0.711 WARN | 0.811 PASS |
| g | **L-BFGS, s 0.5** | 16.4 | 71 | 1313 | **1.8270** | 0.774 / 0.793 | 0.018 / 0.000 | 0.757 / 0.757 | 0.892 / 0.862 | 0.712 WARN | 0.814 PASS |
| g | L-BFGS, s 1 | 12.5 | 57 | 1047 | 1.8266 | 0.774 / 0.793 | 0.018 / 0.000 | 0.757 / 0.757 | 0.893 / 0.863 | 0.712 WARN | 0.814 PASS |
| g | L-BFGS, s 0.25 | 11.6 | 60 | 1104 | 1.8263 | 0.775 / 0.794 | 0.018 / 0.000 | 0.756 / 0.755 | 0.893 / 0.864 | 0.713 WARN | 0.816 PASS |
| g | L-BFGS annealed s 2, 1, 0.5 | 30.7 | 118 | 2170 | 1.8262 | 0.775 / 0.793 | 0.018 / 0.000 | 0.757 / 0.757 | 0.892 / 0.863 | 0.712 WARN | 0.814 PASS |
| far | start | | | | 3.1683 | 0.508 / 0.520 | 0.046 / 0.427 | 0.349 / 0.349 | 0.721 / 0.705 | 0.524 WARN | 0.718 PASS |
| far | CD as fit.py runs it (12 sweeps) | 3.4 | 49 | 49 | 2.4870 | 0.661 / 0.671 | 0.060 / 0.152 | 0.502 / 0.498 | 0.855 / 0.841 | 0.616 WARN | 0.763 PASS |
| far | CD to convergence | 26.5 | 380 | 380 | 1.9293 | 0.721 / 0.735 | 0.025 / 0.000 | 0.755 / 0.755 | 0.878 / 0.854 | 0.691 WARN | 0.787 PASS |
| far | **L-BFGS, s 0.5** | 16.9 | 83 | 1541 | **1.8275** | 0.774 / 0.792 | 0.019 / 0.000 | 0.754 / 0.755 | 0.895 / 0.865 | 0.712 WARN | 0.814 PASS |
| far | L-BFGS annealed s 2, 1, 0.5 | 29.0 | 148 | 2740 | 2.3012 | 0.801 / 0.819 | 0.116 / 0.601 | 0.333 / 0.329 | 0.921 / 0.896 | 0.647 WARN | 0.910 PASS |

(The piece IoUs are qa3d's graded `piece_overskirt_panel_{L,R}` over the four views; they rise with J in every row.)

Reading it:
- **The gradient fit reaches the lowest J from both starts, and the same point**: from g and from far, e1o 126.3 /
  126.1, e1i 156.3 / 156.5, stand1 0.120 / 0.118, first 0.178 / 0.179, rise 0.187 / 0.190, twist -0.02 / -0.03 (droop
  0.35 / 0.18: it hardly moves J, its gradient is -0.01 a step). J 1.8270 / 1.8275.
- **Coordinate descent depends on its start and its budget.** As fit.py runs it (12 sweeps, one move or halving
  each) it stops early: 1.887 from g, 2.487 from far. Run to convergence it gets 1.841 from g (0.8% short of the
  gradient's) in about the same wall time, and from far it walks down another valley to 1.929 (droop at its bound
  -0.5, first 0.4, rise 0.1), 5.6% short, in 1.6x the gradient's wall time.
- **Wall time is even; evaluations are 3-5x fewer.** A gradient evaluation costs ~3x a hard one here, and half of it
  is the builder: 19 builds a gradient for dV/dknob by differences (7.9 of 16.4 s from g). An analytic Jacobian of
  the builder, or builds in parallel, halves the gradient fit's wall time; nothing like it helps CD, whose cost is its
  count of evaluations.
- **The softness hardly matters** (s 0.25, 0.5, 1: J 1.8263-1.8270). s is a pixel-scale smoothing, not a shape-scale
  one: annealing from s 2 doesn't widen the capture range; from far it found a different minimum (J 2.30: the
  three-quarter's right tail 0.60 at the profile's cost, 0.33): the three-quarter's drawn tails disagree with the other
  views (docs/workstreams/skirt.md), so J has two basins.

### Where the objective is smooth and where it isn't

`scan.json` (python -m charkit.render.softfit scan): at g, each knob's dJ/dstep by the chain against differences of
the hard J at 0.01, 0.1 and 1 step and of the soft J at 0.01 step:

| knob | chain | hard 0.01 | hard 0.1 | hard 1 | soft 0.01 |
|---|---|---|---|---|---|
| e1o | -0.0497 | -0.0622 | -0.0486 | -0.0331 | -0.0495 |
| e1i | +0.1542 | +0.1523 | +0.1490 | +0.1329 | +0.1541 |
| standm | +0.0407 | +0.0369 | +0.0337 | +0.0149 | +0.0369 |
| stand1 | +0.0356 | +0.0598 | +0.0395 | +0.0364 | +0.0357 |
| first | -0.0648 | -0.1259 | -0.0540 | -0.0519 | -0.0645 |
| rise | -0.1081 | -0.1983 | -0.1022 | -0.0932 | -0.1077 |
| droop | -0.0105 | -0.0171 | -0.0171 | -0.0098 | -0.0105 |
| out | +0.0098 | +0.0154 | +0.0092 | +0.0109 | +0.0098 |
| twist | -0.0444 | -0.0345 | -0.0453 | -0.0533 | -0.0444 |

- **Pixels.** The hard J's differences at 0.01 step are off by up to 2x (first, rise, stand1: a few pixels flipping
  decide them); at 1 step they average the curvature. The flap is large (~30k px a view), so the hard J is rarely flat
  over a 0.05 step, but it is a staircase at the scale a gradient needs. The soft J's differences match the chain to
  0.1-1% on 8 of 9 knobs.
- **Occlusion.** standm (the standoff over the skirt) is the exception: chain +0.0407 against the soft J's own +0.0369
  (10%). Moving the flap off the skirt moves the flap-skirt occlusion boundary, which the rasteriser keeps hard. Where a
  knob mostly moves depth against an occluder, the chain undercounts it.
- **No overlap, no gradient.** The three-quarter view's drawn tails sit where ours are hidden behind the legs
  (IoU 0.02 / 0.00 at the optimum): an IoU's gradient is zero where ours and the drawing don't meet (d IoU / d cov is
  -I / U^2 there, and I is 0). A distance-based loss (chamfer, or a distance transform of the drawn mask) would pull.
- **Topology.** first, rise and the edges re-sample the builder's rows and columns. The limiter (the smaller one-sided
  difference where the two disagree) handled every one: 621 and 729 knob derivatives by the chain, none needed the
  soft J's own differences.

### Through fitkit itself (`python -m charkit.render.softfit fitkit fd|grad`)

The same IoUs as fitkit terms (each 'ratio' at tol 0.1, weighted by fit G's view weight, no protection, the regulariser
pulling toward the start), `charkit.render.softfit:FlapChecks` as the evaluator (fine: the hard IoUs; smooth: the soft
ones; `jacobian()`: the chain), `fitkit.optimise` with its finite differences (FAST: Broyden between full Jacobians)
against its new gradient path:

| start | fitkit | wall s | evaluations (step / Jacobian / polish) | J | 3/4 L/R | profile L/R | piece L | piece R |
|---|---|---|---|---|---|---|---|---|
| g | finite differences | 20.7 | 280 (29 / 18 / 233) | 1.8693 | 0.026 / 0.000 | 0.762 / 0.762 | 0.709 WARN | 0.802 PASS |
| g | gradient path | 19.9 | 198 (60 / 49 / 89) | 1.8310 | 0.018 / 0.000 | 0.764 / 0.764 | 0.712 WARN | 0.812 PASS |
| far | finite differences | 31.8 | 441 (24 / 18 / 399) | 2.3775 | 0.126 / 0.597 | 0.350 / 0.345 | 0.635 WARN | 0.882 PASS |
| far | gradient path | 26.4 | 235 (49 / 38 / 148) | 2.3780 | 0.077 / 0.401 | 0.404 / 0.400 | 0.625 WARN | 0.833 PASS |

- From g the gradient path reaches J 1.831 (finite differences 1.869) with 30% fewer evaluations: the trust region
  keeps stepping (60 steps against 29) on exact Jacobians, so the polish (the pattern search on the hard pixels) has
  far less left to do (89 against 233).
- From far both stop in the three-quarter's basin (J 2.378): fitkit's cost is not J (soft-L1 over the hinged
  residuals, a regulariser toward the start, 4 x knobs trust-region evaluations a cycle), and plain L-BFGS on J got
  out of it (1.8275). The gradient path doesn't change fitkit's objective; it changes how cheaply fitkit sees it.

## Recommendation for fitkit

1. **Keep the gradient path opt-in** (landed: `fitkit.GRADIENT = False`; `optimise(gradient=True)`; an evaluator adds
   `jacobian(spec, group, knob_names) -> (checks, {measure: {knob: d value / d knob}})`; `Term.dresidual` turns
   measure derivatives into residual ones for every reading kind; `Pool.jacobian`; phase 'jacobian'). Tests:
   charkit/tests/test_fitkit.py (the toy: plain 180, fast 85, gradient 71 evaluations to the same fine cost; dresidual
   against differences for ratio, abs, gap, floor).
2. **Which evaluators should offer jacobian()**: those whose terms are silhouette IoUs (piece shapes, flap and skirt
   outlines, the body's per-view IoUs): softras gives d IoU / dV per view in ms, and a template builder's dV/dknob by
   differences costs builds only (3 ms a flap). Width, hang, attach and band-step checks are read off silhouettes by
   non-smooth rules (row maxima, line fits, step counts); leave them to the differences and the polish.
3. **Chain helper**: the limited central difference of a builder (`Flaps.value_and_grad`'s per-vertex minmod where
   a builder re-samples rows) is generic; lift it into fitkit (or softras) when a second template takes the path.
4. **What would pay most next**: analytic dV/dknob for the templates (half the gradient's time here is 19 builds);
   a distance-based term for views where ours and the drawing don't overlap (IoU has no gradient there); and the
   depth-occlusion boundary made soft if a knob mostly moves depth (standm's 10%).

## Round 3 (after the merge, ba51e43): the distance term, call A, a second template

The coordinator's calls: the opt-in path merged as is; next the distance term, then analytic builder derivatives; the
flap's three-quarter tails follow Michael's call A (front, back and profile win).

- **Call A in the objective**: the three-quarter's flap terms weigh 0 (`--weights a`: VW_A, three-quarter 0; it
  draws only the tails there, so this masks exactly its tails). They are still measured and reported in every
  record and on the page (no gaming), just not fitted.
- **The distance term** (`softras.Outline`, `softras.chamfer`): the symmetric chamfer between our visible contour and
  the drawn outline, in px (the mean over our contour points of the drawn outline's distance transform, sampled
  bilinearly, plus the mean over the drawn outline's pixels of the distance to our nearest contour point). It has a
  gradient where ours and the drawing don't overlap (the IoU's is 0 there). Each contour point sits on its pixel
  segment, t = cross(A - p, B - A) / cross(e, B - A), so the derivative is exact for what is computed: tested against
  differences, overlapping and apart, relative error 1e-8 (test_chamfer_gradient). The fit's objective with it:
  J + LAMBDA sum over terms of w x chamfer (L), LAMBDA 1 (`--dist 1`).
- **What the chamfer isn't**: smooth at the scale of a pixel. Its samples are the pixel pairs the contour crosses, so
  points appear and vanish as the contour sweeps over pixel centres. At the far start, 0.01-step differences of J
  with the term read 1.4-1.6x the chain's local derivative (e1o -0.061 against -0.037, first +0.080 against +0.059,
  droop -0.042 against -0.028), with the same sign. A continuous version (samples weighted by the contour length they
  stand for) is the refinement if the fits show it matters.
- **The second template: the puff sleeve** (`garments.puff`, `Sleeves`): its frozen scene without the sleeves
  (`scene --template sleeve`), drawn as the outfit masks (VIEW__sleeve_{L,R}, as piece_shapes reads them), 7 terms
  (every view with 200 px or more; the right sleeve is hidden in profile), every view weighing 1. Knobs: the knot
  table's four extents each scaled (sxp, syp, sxm, sym, 0.05 steps), a taper across the stations, the cap's height,
  the section's roundness. The stations stay, so no knob changes the topology. The right sleeve mirrors the left's
  knots. A build takes 16 ms a side (2625 vertices).

### Round 3's numbers (`charkit/out/softras/r3`: fit_*.json, runs.log; pages index.html, index_sleeve.html)

J is the hard IoU objective under the fit's weights (the flap's under call A); C is the weighted chamfer (L), measured
for every fit whether or not it was fitted. CD runs to convergence; L-BFGS at s 0.5; "+ chamfer" adds the term
(LAMBDA 1).

| template | start | fit | wall s | evaluations | J | C | IoUs (3/4 reported, weight 0 for the flap) | piece L | piece R |
|---|---|---|---|---|---|---|---|---|---|
| flap | g | start | | | 1.3874 | 0.497 | | 0.653 WARN | 0.759 PASS |
| flap | g | CD | 12.6 | 235 | 1.0351 | 0.387 | front .755/.773, 3/4 .023/.000, profile .752/.754, back .906/.883 | 0.712 WARN | 0.818 PASS |
| flap | g | **L-BFGS** | 6.8 | 38 | **1.0189** | 0.389 | front .775/.794, 3/4 .017/.000, profile .756/.759, back .895/.873 | 0.714 WARN | 0.823 PASS |
| flap | g | L-BFGS + chamfer | 14.5 | 82 | 1.0247 | **0.382** | front .760/.778, 3/4 .020/.000, profile .759/.761, back .901/.878 | 0.715 WARN | 0.821 PASS |
| flap | far | start | | | 2.5556 | 0.894 | | 0.524 WARN | 0.718 PASS |
| flap | far | CD | 20.9 | 383 | 1.1238 | 0.416 | front .721/.735, 3/4 .025/.000, profile .755/.757, back .881/.865 | 0.692 WARN | 0.794 PASS |
| flap | far | **L-BFGS** | 20.6 | 88 | **1.0199** | 0.394 | front .777/.796, 3/4 .017/.000, profile .754/.757, back .895/.873 | 0.712 WARN | 0.821 PASS |
| flap | far | L-BFGS + chamfer | 26.4 | 130 | 1.0242 | **0.383** | front .765/.782, 3/4 .021/.000, profile .750/.752, back .907/.884 | 0.715 WARN | 0.823 PASS |
| sleeve | g | start | | | 2.0326 | 0.688 | | | |
| sleeve | g | **CD** | 6.7 | 106 | **1.8235** | 0.619 | front .757/.769, 3/4 .866/.398, profile .855, back .761/.771 | 0.932 PASS | 0.830 PASS |
| sleeve | g | L-BFGS | 26.6 | 51 | 1.8540 | 0.637 | front .762/.775, 3/4 .877/.394, profile .837, back .744/.756 | 0.925 PASS | 0.819 PASS |
| sleeve | g | L-BFGS + chamfer | 19.9 | 40 | 1.8544 | **0.611** | front .773/.780, 3/4 .861/.399, profile .832, back .745/.755 | 0.930 PASS | 0.832 PASS |
| sleeve | far | start | | | 2.2746 | 0.772 | | | |
| sleeve | far | **CD** | 22.1 | 308 | **1.8254** | 0.620 | front .756/.765, 3/4 .870/.391, profile .861, back .761/.772 | 0.934 PASS | 0.830 PASS |
| sleeve | far | L-BFGS | 19.4 | 37 | 1.8382 | 0.629 | front .765/.763, 3/4 .871/.374, profile .854, back .761/.774 | 0.937 PASS | 0.831 PASS |
| sleeve | far | L-BFGS + chamfer | 46.7 | 90 | 1.9145 | 0.649 | front .753/.730, 3/4 .849/.387, profile .852, back .756/.759 | 0.935 PASS | 0.823 PASS |

Reading it:
- **Call A** makes the flap's objective the four views that agree: the gradient fit still wins from both starts
  (1.0189 / 1.0199 against CD's 1.0351 / 1.1238), from g in half CD's wall time and a sixth of its evaluations. The
  three-quarter's IoUs stay 0.02 / 0.00 in every fit (reported, weight 0).
- **The distance term doesn't pay on these two**: on the flap it buys the lowest chamfer (0.382 / 0.383) for +0.005 J;
  on the sleeve from g the lowest chamfer for the same J, and from far it lands worse (1.9145). Both far starts here
  already overlap the drawing in every fitted view, so the IoU has a gradient everywhere it's needed; the term's use is
  starts or views with no overlap, which call A removed from the flap's objective (its three-quarter tails). The
  chamfer's own non-smoothness (samples appearing as the contour sweeps pixel centres, 1.4-1.6x) costs the line
  searches evaluations (the sleeve's far run, 90 evaluations and 46.7 s).
- **The sleeve is where the gradient loses**, and the measurement says why: 23-54% of its visible outline is an
  occlusion boundary (the torso, the cuffs, the other arm), against 2-6% for the flap in back and profile. The chain
  differentiates only the free outline, so at g it matches the soft J's own differences for the knob that moves the
  free outline (sxp 1.00x) and not for those that move depth against the torso and cuff (sxm 0.54x, round 0.46x, cap
  2.98x, syp 1.25x). L-BFGS then converges on a biased gradient: J 1.854 / 1.838 against CD's 1.824 / 1.825.

What that means for the order of work: **soft occlusion** (the depth-order boundary between the piece and its
occluders made soft and differentiated, as the contour is) comes before analytic builder derivatives for any piece
that sits against the body (sleeves, collar, boots at the cuff); the distance term stays opt-in (`--dist`) for
no-overlap cases, with length-weighted samples if it's used.

## Round 4: soft occlusion

Coordinator's call: soft occlusion before analytic builder derivatives (the sleeve's outline is 23-54% occlusion).
Branch at pipeline-3d 004efc3 (merged). The frozen scenes are round 3's (symlinked into `charkit/out/softras/r4`), so
the fits compare like for like with round 3 (the scene holds its own hull; garments.py hasn't changed since).
Runs: `charkit/out/softras/r4/runs.sh` (laptop, one process, sequential), log `r4/runs.log`, records `r4/fit_*.json`;
measurement `python -m charkit.render.softfit occ --template sleeve|flap [--weights a] --out charkit/out/softras/r4`
-> `r4/occ_*_g.json` and `.log`; smoothness `r4/smooth.py` -> `r4/smooth_*.json`; review `r4/review.py` ->
**`r4/occ.html`** (summary box), view by view `r4/index_sleeve.html`, `r4/index.html` (the flap).

### What it is (`softras.silhouette(..., occlusion='soft')`, opt-in; 'hard' the default, unchanged)

- **Where the visible outline runs** (`softfit.boundary_kinds`, the QA's pixels, 4-neighbour pairs of a visible pixel
  and one that isn't): *free* (the piece's own contour), *depth-order* (the occluder covers both pixels on one surface,
  continuous in depth: where the piece passes into or behind it), *occluder edge* (the occluder's own outline over the
  piece: fixed while only the piece moves, so its gradient is rightly 0), *other piece*. At the sleeve's start: free
  47-78%, depth-order 7-28% (the cuffs, the bodice `top`, the collar), occluder edge 7-46%, other piece 0%. The flap:
  free 26-99%, depth-order 0-6% (the skirt), occluder edge 0-73% (the legs, in front and three-quarter), other 0%.
- **The depth-order edge made soft.** A covered pixel's visibility is v = k(delta / s), delta the first-order signed
  distance (px) to where the piece's plane passes behind the occluder's: (z_occ - z) / |grad z_occ - grad z|, z and its
  screen gradient from the covering triangle's plane, the occluder's gradient by differences on its depth image, per
  surface (the frozen scene's object labels; the central difference where the one-sided ones agree within 20%, else the
  smaller: a fold or an edge on one side). |grad| is floored at 0.02 and capped at 3 pixel widths of depth a pixel
  (GMIN, GMAX). Beyond R (3 s) v is the hard 0 / 1. cov = F (the contour's) x v; the contour search runs on into the
  soft band behind. Its derivative: d v / d delta analytic, d delta / d the triangle's corners (2D and depth) by complex
  steps (exact to rounding), pulled back through the view's projection and its depth (`pullback_depth`).
- **The cap (GMAX 3)**, measured: without it, edge-on contact (the flap lying on the skirt in three-quarter, surfaces
  steeper than 100 pixel widths of depth a pixel) reads delta a few hundredths of a pixel and v about 0.5 at any
  softness: that term's area came out 1.25-1.31% short at s 0.25-1. Caps 30 / 10 / 5 / 3: -0.97 / -0.49 / -0.30 /
  -0.22%; the sleeve's chain against differences improved with it (at 3: 0.99-1.07x, against 0.93-1.13x uncapped).
- **Not done**: the other piece's depth isn't differentiated when it is the occluder (0% of both pilots' outlines);
  the band pixels outside the piece keep hard visibility at their contour point's depth, as before.

### Tests (`charkit/tests/test_softras.py`, all pass)

| test | result |
|---|---|
| gradient vs central differences, the panel cut by a tilted plane (a depth-order edge across it), soft occlusion | cosine 1.000000; median 2e-9 / 1e-8, p95 3e-8 / 4e-8 (s 1 / 0.5) |
| a depth-only move (only the depth-order edge moves): chain against the hard IoU's differences over 2-8 px | hard occlusion 0 (the round-3 blind spot); soft at s 1 +1.7985 against +1.72-1.84 (median +1.811); at s 0.5 +2.0125 (+11%: a 0.23 px kernel aliases on one straight edge at one angle to the grid) |
| convergence as s -> 0, soft occlusion | sum \|F - C\| 90.4, 46.3, 10.0, 0.92, 0.000 px at s 1, 0.5, 0.1, 0.01, 0.001; IoU(F >= 0.5, C) 1.0 |
| the default (hard) | every earlier test unchanged |

### The measurement before building on it (at each template's start g; `r4/occ_*_g.log`)

Agreement with the QA's hard z-buffered masks at s 0.5 (hard / soft occlusion): IoU(cov >= 0.5, hard) 1.0000 /
0.9999-1.0000 in every term, outline distance 0.000 / <= 0.003 px, area bias within 0.15% (flap three-quarter R,
weight 0: -0.03 / -0.22%), soft IoU minus hard IoU within 0.0007 (0.0013 flap front L).

The chain's dJ/dstep against differences of the soft J at 0.01 step (and of the hard J at 0.1 / 0.3 / 1 step):

| knob | chain, hard occl. | soft J fd | ratio | chain, soft occl. | soft J fd | ratio | hard J 0.1 / 0.3 / 1 |
|---|---|---|---|---|---|---|---|
| sxp | -0.0699 | -0.0698 | 1.00x | -0.0698 | -0.0697 | 1.00x | -0.0686 / -0.0720 / -0.0706 |
| syp | +0.0197 | +0.0157 | 1.25x | +0.0244 | +0.0245 | 0.99x | +0.0255 / +0.0248 / +0.0234 |
| sxm | +0.0218 | +0.0407 | 0.54x | +0.0371 | +0.0370 | 1.00x | +0.0433 / +0.0364 / +0.0344 |
| sym | +0.0146 | +0.0181 | 0.81x | +0.0178 | +0.0177 | 1.00x | +0.0187 / +0.0180 / +0.0157 |
| taper | +0.0132 | +0.0167 | 0.79x | +0.0146 | +0.0145 | 1.00x | +0.0152 / +0.0173 / +0.0106 |
| cap | -0.0057 | -0.0019 | 2.98x | -0.0035 | -0.0033 | 1.07x | -0.0040 / -0.0019 / -0.0013 |
| round | +0.0100 | +0.0221 | 0.46x | +0.0151 | +0.0150 | 1.01x | +0.0215 / +0.0158 / +0.0120 |
| flap standm (the only flap knob that moved) | +0.0429 | +0.0413 | 1.04x | +0.0406 | +0.0406 | 1.00x | +0.0372 / +0.0376 / +0.0202 |

Smoothness (`smooth.py`: the soft J over +-0.1 step at 41 points, the residual RMS of a quadratic, x1e4): the sleeve
at g, hard occlusion s 0.5 0.17-1.13, soft 0.06-0.31 (s 1: 0.04-0.15); the flap at g unchanged but standm (0.29 ->
0.01); at the flap's far soft-occlusion endpoint e1i reads 14.5 in both modes (the builder's re-sampling, not the
occlusion).

### The pilots (`r4/fit_*.json`; laptop, one process; J the QA's hard objective; evaluations incl. 2 hard)

| template | start | fit | wall s | evals | builds | J | piece L | piece R |
|---|---|---|---|---|---|---|---|---|
| sleeve | g | CD to convergence | 6.6 | 106 | 106 | 1.8235 | 0.932 PASS | 0.830 PASS |
| sleeve | g | L-BFGS s 0.5, occlusion hard | 24.6 | 51 | 737 | 1.8540 | 0.925 PASS | 0.819 PASS |
| sleeve | g | L-BFGS s 0.5, soft occlusion | 29.5 | 63 | 917 | **1.8192** | 0.932 PASS | 0.834 PASS |
| sleeve | g | L-BFGS s 1, soft occlusion | 32.0 | 68 | 992 | 1.8218 | 0.932 PASS | 0.833 PASS |
| sleeve | far | CD to convergence | 22.3 | 308 | 308 | 1.8254 | 0.934 PASS | 0.830 PASS |
| sleeve | far | L-BFGS s 0.5, occlusion hard | 18.8 | 37 | 527 | 1.8382 | 0.937 PASS | 0.831 PASS |
| sleeve | far | L-BFGS s 0.5, soft occlusion | 68.2 | 111 | 1637 | **1.8204** | 0.933 PASS | 0.831 PASS |
| sleeve | far | L-BFGS s 1, soft occlusion | 22.6 | 41 | 587 | 1.8215 | 0.934 PASS | 0.833 PASS |
| flap (call A) | g | CD | 13.0 | 235 | 235 | 1.0351 | 0.712 WARN | 0.818 PASS |
| flap | g | L-BFGS s 0.5, hard | 9.5 | 38 | 686 | 1.0189 | 0.714 WARN | 0.823 PASS |
| flap | g | L-BFGS s 0.5, soft occlusion | 18.7 | 102 | 1902 | **1.0184** | 0.714 WARN | 0.823 PASS |
| flap | far | CD | 20.6 | 383 | 383 | 1.1238 | 0.692 WARN | 0.794 PASS |
| flap | far | L-BFGS s 0.5, hard | 21.3 | 88 | 1636 | **1.0199** | 0.712 WARN | 0.821 PASS |
| flap | far | L-BFGS s 0.5, soft occlusion | 22.7 | 101 | 1883 | 1.0304 | 0.709 WARN | 0.807 PASS |

Per view (every fit's piece IoU per view is in the records and on the page): no view of any fit falls more than 15%
below its start except the terms call A weighs 0 (the flap's three-quarter: L 0.034 -> 0.002-0.012, R from far 0.515
-> 0 in every fit, CD included) and the sleeve R's three-quarter from g (0.306 -> 0.282-0.285, -7%, CD the same).

Reading it:
- **Soft occlusion fixes the sleeve.** With the depth-order edge hard the gradient fit stopped at 1.8540 / 1.8382 on a
  biased gradient (sxm 0.965 from g against CD's 0.875); with it soft it reaches 1.8192 / 1.8204 (s 0.5) and 1.8218 /
  1.8215 (s 1), below CD's 1.8235 / 1.8254 from both starts, at CD's point (sxm 0.86-0.88, cap 0.118-0.121, round
  2.22-2.36 against CD's 0.85-0.875, 0.12, 2.3-2.5). Piece IoUs equal or up (sleeve R 0.830 -> 0.833-0.834).
- **s 1 for soft occlusion.** At s 0.5 both sleeve runs ended ABNORMAL in the line search and the far run took 111
  evaluations (68 s); at s 1 they converged (68 / 41 evaluations), 0.1% above s 0.5's J. The unit test says why: a kernel
  narrower than a pixel aliases on a straight depth-order edge (+11% at s 0.5, within 1% at s 1).
- **The flap (control) gains nothing**: its outline is 0-6% depth-order. From g the same point (1.0184 against 1.0189)
  for 2.7x the evaluations (the smoother standm keeps the relative-reduction test going); from far the path took the
  other valley (droop at its bound -0.5, first 0.42: CD's far valley of round 1) to 1.0304 against 1.0199 (both at the
  60-iteration cap), still below CD's 1.1238. Use soft occlusion where the measurement finds depth-order edges.
- **Wall time is now the builds.** Sleeve: builds are 26.3 of 29.5 s (89%) from g, 60.6 of 68.2 s and 19.7 of 22.6 s
  from far: 15 builds a gradient (dV/dknob by central differences, 29 ms a build of both sleeves) against one soft
  render and backward (~50 ms, soft occlusion +5 ms). So from g the gradient fit takes 4.5-4.8x CD's wall time for its
  better J, and from far (s 1) the same wall time as CD.

### The next step: analytic builder derivatives, yes

The gradient is now unbiased on both pilots (the chain within 0.99-1.07x of the soft J's own differences on every
knob), so what's left between it and coordinate descent is cost, and the cost is the builder: 85-90% of the sleeve's
gradient fit, ~50% of the flap's. An analytic dV/dknob (or a builder Jacobian by forward-mode / complex step through
the builder) removes 14 of the 15 builds a gradient; with the Jacobian itself cheap, the sleeve's fit from g would take
~5 s (its renders 3.2 s plus one build an evaluation) against CD's 6.6, from far (s 1) ~4 s against 22.3. Cheaper stopgaps: one-sided differences (7 builds, half; the limiter needs both sides at
re-sampling events, which the sleeve's knobs don't have) or the builds in parallel (fitkit's Pool).

## Log

- 2026-09-30: started; notes skeleton. The rasteriser and its tests (3593734); the pilot harness (softfit); fitkit's
  opt-in gradient path (6bc550e).
- The pilot runs (round 1 kept in charkit/out/softras/round1: before the flap build memo; round 2 the numbers above),
  the scan, fitkit's runs, the review page. Then the gate, once (policy K): `python -m charkit remote gate tool/softras
  --into pipeline-3d`, expected to move no check (nothing on the build path imports softras or softfit; fitkit's
  default is unchanged and only the fit commands import it).
- Merged into pipeline-3d as ba51e43 (gate --carry); round 3 on top (the chamfer, call A, the sleeve).
- **Round 3 gate PASS** (d18d8cf into pipeline-3d ba51e43, policy K): nothing blocks, 0 items reported, no candidate
  build (4 files changed, none the baseline build read), 70 test files 0 failing (test_softras.py's chamfer test among
  them). Report charkit/out/gate/gate_tool-softras_d18d8cf_into_ba51e43.md. Round 3's decisions: soft occlusion before
  builder derivatives (the sleeve's evidence); keep the chamfer opt-in.
- **Gate PASS** (161f9af into pipeline-3d 3a0ad37, policy K): nothing blocks, 0 items reported; no candidate build
  (6 files changed, none among the 560 the baseline build read); 70 test files, 0 failing, test_softras.py and
  test_fitkit.py among them on the build box. Report charkit/out/gate/gate_tool-softras_161f9af_into_3a0ad37.md.

- **Round 4** (soft occlusion): 955a7d0 and on; measured (agreement 0.9999-1.0000 IoU against the hard masks, the
  sleeve's chain 0.99-1.07x from 0.46-2.98x), the pilots (sleeve: the gradient fit below CD from both starts, 1.8218 /
  1.8215 at s 1 against 1.8235 / 1.8254; flap control unchanged); page r4/occ.html. Gate: see below.

## Decisions for Michael

1. Merge the gradient path as opt-in (it changes no default), or keep it on the branch until a second evaluator takes it.
2. Next for gradients: analytic Jacobians in the template builders (half the gradient fit's time), or a distance term
   for views with no overlap (the flap's three-quarter).
3. The flap's three-quarter view: the drawing's tails there disagree with its back, front and profile (skirt notes);
   J has two basins because of it. Which view wins is a design call, not an optimiser's.
