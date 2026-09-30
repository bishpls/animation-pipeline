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

## Decisions for Michael

1. Merge the gradient path as opt-in (it changes no default), or keep it on the branch until a second evaluator takes it.
2. Next for gradients: analytic Jacobians in the template builders (half the gradient fit's time), or a distance term
   for views with no overlap (the flap's three-quarter).
3. The flap's three-quarter view: the drawing's tails there disagree with its back, front and profile (skirt notes);
   J has two basins because of it. Which view wins is a design call, not an optimiser's.
