# Garments from the hull's labelled shell (tool/garment-sampling)

## Checkpoint (2026-09-30). Start here.

**Branch** `tool/garment-sampling` in `~/animation-pipeline-garmsamp`, from `tool/hull-det` 3267aea (which already
contains pipeline-3d 5cb5256). The hull there is built from this branch's code (`hull.glb.stamp` fresh).

**The problem.** tool/hull-det makes the hull bit-identical across machines. Its deterministic 3x3 solve in the
decimation gives a new but equivalent vertex set: the skirt's width matches at every height to three decimals, and its
vertex count goes 7,371 -> 7,378. Yet three checks moved at its gate: body_front_skirt_aline -0.016 PASS -> -0.133
FAIL, body_back_leg 0.066 -> 0.108 WARN, piece_overskirt_panel_R_hang 0.095 -> 0.111 WARN. The garment lofts read the
decimated mesh's vertices, and their statistics amplified which vertices a decimation keeps. Per-cell quantiles, hem
percentiles, dense arcs and span percentiles all weight wherever vertices crowd: at curvature, not by area.

**The change** (charkit/garments.py only; no builder's logic changed):

| function | change |
|---|---|
| `hull_pieces(spec, A, source='shell')` | points from hull.npz's labelled shell (`shell_points`) instead of the glb's vertices and hull_pieces.npy. Names and eyes still come from the sidecar. `source='mesh'`, or a hull without `shell`, keeps the old path |
| `shell_points(Z, stray=STRAY)` (new) | one point per shell voxel: the mean of its exposed faces' centres, so on the occupancy's boundary. Median offset from the marching-cubes surface -0.0001 L (voxel centres would be -0.004 L). Numpy only |
| `shell_patches(S, lab)` (new) | each voxel's 26-connected same-label patch size and its label's largest (numpy union-find; matches scipy.ndimage.label exactly, 0.27 s on Clawd's 274k voxels) |
| `STRAY = (0.05, 0.0064)` (new) | a patch under 5% of its label's largest and under 0.0064 L^2 (64 voxels) is left out |
| `_knn_mean` | chunk bounded to ~2.5M point pairs (the collar's conform sees ~4x the points); results unchanged |

Untouched: hull.py, det.py, every builder (`skirt_hull`, `flap`, `band_hull`, `belt_hull`, `sleeve_hull`, `shoe_hull`,
`shell`, `collar_hull`, `bow_hull`, `panel_hull`), the spec. The build's stage cache keys hull.npz on its own (the
audit hook records every file opened).

**Why the stray filter.** On the shell, label patches count by area. On the mesh, a flat stray patch got few
vertices. Without the filter, dense points moved the bands: wrist_R's start 0.055 L up the forearm (piece_cuff_R 0.595
-> 0.421 FAIL) and boot_cuff_L's radius 0.27 -> 0.37 L (0.876 PASS -> 0.719 WARN). The strays are small disconnected
components (wrist_R: 59, 24, 15, 7 and 1 voxels against a main patch of 1,344). A relative-only threshold also dropped
the skirt's 253–545-voxel bits at the back, and back_leg went 0.066 -> 0.32 FAIL; hence the absolute cap.

## Measurement

Tools:
- `charkit/tests/garment_sensitivity.py`: re-surfaces the spec's hull from its own occupancy, decimates it to other
  face counts (or with `--remesh FILE`, another decimation module), and labels each vertex as the build does. It then
  builds the garments from each variant (`--source mesh` or `shell`) and runs every body_* and piece_* check plus the
  flaps' hang in the evaluator. Output: `charkit/out/garment_sensitivity/`.
- `charkit/tests/test_garment_sampling.py`: a synthetic hull (a cone skirt under a band, with a planted stray patch)
  and two real decimations of it. Shell pieces and the skirt from them are bit-identical across the two, while the
  mesh path's differ; points lie within half a voxel of the cone; the stray is dropped; it runs without scipy.
- The decimation variants reproduce the shipped hull exactly: 150,000 faces gives the glb's vertices to 2.4e-7
  (float32) with identical labels.

**Sensitivity to decimation** (evaluator, default spec, body fitted once to the shipped hull; reference 150,000 faces
by the deterministic solve; LAPACK = pipeline-3d's remesh on this laptop):

| check | 150,000 | 142,500 | 157,500 | LAPACK 150,000 | max change, mesh | max change, shell |
|---|---|---|---|---|---|---|
| body_front_skirt_aline | -0.132 FAIL | -0.02 PASS | -0.133 FAIL | -0.132 FAIL | 0.112 | 0 |
| body_three_quarter_skirt_aline | -0.168 FAIL | -0.174 FAIL | -0.181 FAIL | -0.17 FAIL | 0.013 | 0 |
| body_front_skirt_width | 0.941 PASS | 0.941 PASS | 0.937 PASS | 0.941 PASS | 0.004 | 0 |
| body_back_skirt_width | 1.08 WARN | 1.091 WARN | 1.086 WARN | 1.08 WARN | 0.011 | 0 |
| body_front_hem | 0.0377 PASS | 0.0424 PASS | 0.0424 PASS | 0.0377 PASS | 0.0047 | 0 |
| body_back_hem | 0.0236 PASS | 0.0283 PASS | 0.0236 PASS | 0.0236 PASS | 0.0047 | 0 |
| body_profile_hem | -0.0517 PASS | -0.047 PASS | -0.047 PASS | -0.0517 PASS | 0.0047 | 0 |
| body_back_leg | 0.1083 WARN | 0.0659 PASS | 0.0659 PASS | 0.1083 WARN | 0.0424 | 0 |
| piece_overskirt_panel_R_hang | 0.1112 WARN | 0.0951 PASS | 0.1169 WARN | 0.1111 WARN | 0.0161 | 0 |
| piece_overskirt_panel_R | 0.427 FAIL | 0.447 FAIL | 0.325 FAIL | 0.427 FAIL | 0.102 | 0 |
| piece_skirt | 0.833 PASS | 0.838 PASS | 0.829 PASS | 0.833 PASS | 0.005 | 0 |
| piece_sleeve_R | 0.791 PASS | 0.791 PASS | 0.798 PASS | 0.791 PASS | 0.007 | 0 |
| piece_sleeve_cuff_R | 0.557 WARN | 0.56 WARN | 0.579 WARN | 0.557 WARN | 0.022 | 0 |
| piece_cuff_R (wrist band) | 0.595 WARN | 0.637 WARN | 0.589 WARN | 0.595 WARN | 0.042 | 0 |
| piece_waistband | 0.437 FAIL | 0.399 FAIL | 0.396 FAIL | 0.437 FAIL | 0.041 | 0 |
| body_back_iou_skin | 0.691 WARN | 0.7 WARN | 0.673 WARN | 0.691 WARN | 0.018 | 0 |

Garment vertices, max (p95) displacement from the 150,000 build, L, mesh source. On the shell, every garment is
bit-identical across all variants.

| garment | 142,500 | 157,500 |
|---|---|---|
| skirt | 0.101 (0.057) | 0.127 (0.046) |
| overskirt_panel_R | 0.107 (0.053) | 0.379 (0.280) |
| wrist_R | 0.087 (0.053) | 0.053 (0.007) |
| collar | 0.060 (0.011) | 0.015 (0.003) |
| shoe_L | 0.036 (0.008) | 0.030 (0.004) |
| cuff_R | 0.005 | vertex count 480 -> 528 |
| shorts, top | vertex count changes | vertex count changes |

Tolerance claimed: **0** (bit-identical). The garments no longer read the mesh, so no decimation can move them.
On this laptop, pipeline-3d's LAPACK solve decimates almost as the deterministic solve does (skirt 0.001 L). The
gate's flip came from the build box's x86 LAPACK taking another vertex set; ±5% faces reproduces it.

**The three checks** (evaluator, default spec): body_front_skirt_aline -0.132 FAIL -> **0.002 PASS**; body_back_leg
0.1083 WARN -> **0.0753 PASS**; piece_overskirt_panel_R_hang 0.1112 WARN -> **0.0176 PASS** (L: 0.0883 -> 0.0088).

## What else moves, and why (evaluator, mesh source at 150,000 -> shell)

Better: body_back_skirt_width 1.08 WARN -> 0.979 PASS; body_back_iou_skin 0.691 WARN -> 0.704 PASS; piece_cuff_L
0.375 FAIL -> 0.67 WARN; piece_cuff_R 0.595 -> 0.668; piece_waistband 0.437 FAIL -> 0.527 WARN; piece_skirt 0.833 ->
0.899; piece_sleeve_cuff_L 0.662 -> 0.715. clawd_mh: piece_skirt 0.772 -> 0.831, piece_waistband 0.346 -> 0.499,
piece_top 0.455 -> 0.49.

Worse, and where it comes from:
1. **The skirt's axis was biased by the decimation.** `_vertical_axis` takes the median x and y of the skirt's top
   0.1 L, a partial ring: 8 of its 1,499 shell points fall in -120..-90 deg. On the mesh the median sits at x = +0.152
   to +0.159 L for every decimation, a systematic bias because the mesh's vertices crowd the ring's detailed front.
   On the shell it is +0.050; the body's midline is 0.000 and an ellipse fit gives -0.011. Round 4 fitted the flaps'
   knobs on the biased frame; its open item 2 ("the right flap sits 0.14–0.3 L further back: the skirt's hull axis
   is off-centre") is this bias.
2. **The hem family and the flaps' extent (default spec) follow the skirt's hidden back hem.** A flap is laid on the
   skirt from its waist to the skirt's hem at the flap's azimuth (±144 deg), then its tail. That hem is hidden under
   the flaps (`occluded_span` 70–180 deg) and filled linearly between the single sectors at ±69–71 deg, where the hands
   cut the skirt's points short: 0.97–0.98 L against 1.17–1.20 in the sectors beyond. On the mesh (with its biased
   axis) the fill ran asymmetrically, 1.00 -> 1.18 across the back, putting the flaps' start at 1.06 / 1.13. On the
   shell both ends land on the notch, so the fill is a flat 0.98. The flaps start and end about 0.12 L higher.
   - The lowest rows show it (box): body_front_hem 0.0471 PASS -> 0.1647 FAIL, back 0.033 -> 0.1506 WARN, three-quarter
     0.08 -> 0.1741 FAIL, back hem_mid 0.1364 WARN -> 0.2306 FAIL, piece_overskirt_panel_L/R_extent 0.042 / 0.057
     PASS -> 0.141 / 0.137 WARN.
   - Hang improves (0.0947 -> 0.0176) because it compares the flap's lowest vertex with the drawn *middle* chain's
     end. The flap's V tip sits below that, so hang and extent disagree about the flaps' length. The extent (the
     flap's own lowest visible row against the drawn flap's) is the direct measure, and it says the new flaps are
     short. Also, a flap's last `trim` 0.15 L is its dark stepped band, so the lowest orange row sits ~0.15 L above
     its tip.
   - Probes, all on the shell (evaluator; not applied):
     - flap `length` 0.36 -> 0.42: hems 0.0565 / 0.0471 / 0.08 PASS, hangs 0.089 / 0.098 PASS; back hem_mid stays
       0.23 FAIL (the skirt's, not the flaps').
     - The fill's anchors as the median of the k measured sectors nearest each end: k 3 brings every hem and both
       extents back to PASS and back hem_mid to 0.1364 WARN, but three-quarter hem_mid goes 0.019 PASS -> -0.339 FAIL
       and R hang to 0.106 WARN. k 6 is worse (flat ~1.19 all round the back).
   - The hidden back hem is unconstrained, and the views pull it different ways; the mesh's asymmetric fill happened to
     satisfy them. It needs fitting together with the flaps (tool/body round 5 rebuilds them as `flap_mirror`), so
     neither probe is on this branch.
3. **The axis moves the flaps' frame too.** With every principled axis (shell median, ellipse, circle, hips) the
   flaps' checks move; the old knobs were fitted on the biased one.
4. **clawd_mh body_back_skirt_width** 0.941 PASS -> 0.866 WARN is a measurement artefact. No row is free of hands in
   both figures, so the check falls back to the design's free rows, the waist (z -1.40..-1.56). Row by row the
   shell's skirt is closer to the design: at z -1.40, mesh 0.828, shell 0.673, design 0.635. But the check divides
   each figure's maximum over those rows, and the mesh passed by setting its top row against the design's bottom row
   (0.880 at -1.56).
5. **clawd_mh body_front_skirt_aline** -0.040 PASS -> -0.055 WARN (the line is 0.05). At the sides the skirt's label
   wraps the hands' bulge. The mesh crowds vertices on that curve, so its per-cell median sat on the bulge (r 0.97–1.00
   L at t 0.5); the shell weights the flatter skirt (0.85–0.90). Probe: skirt `q` 0.6 gives -0.021 PASS on clawd_mh and
   is neutral on the default spec (every check's grade unchanged). Not applied: it is a knob, not sampling.

## Gates (build box, 1820d56 into pipeline-3d 5cb5256; all tests ok)

| gate | verdict | regressed | improved |
|---|---|---|---|
| default (`gate_tool-garment-sampling_1820d56_into_5cb5256.md`) | **FAIL** | body_front_hem 0.0471 PASS -> 0.1647 FAIL, body_back_hem 0.033 PASS -> 0.1506 WARN, body_three_quarter_hem 0.08 PASS -> 0.1741 FAIL, body_back_hem_mid 0.1364 WARN -> 0.2306 FAIL, piece_overskirt_panel_L_extent 0.0424 PASS -> 0.1412 WARN, piece_overskirt_panel_R_extent 0.0565 PASS -> 0.1365 WARN | body_back_skirt_width 1.091 WARN -> 0.979 PASS, body_back_iou_skin 0.696 WARN -> 0.704 PASS, body_profile_iou_skin 0.696 WARN -> 0.71 PASS, piece_cuff_L 0.375 FAIL -> 0.67 WARN, piece_waistband 0.451 FAIL -> 0.527 WARN, piece_skirt_extent 0.113 WARN -> 0.0518 PASS |
| clawd_mh (`..._clawd_mh.md`) | **FAIL** | body_back_skirt_width 0.941 PASS -> 0.866 WARN, body_front_skirt_aline -0.04 PASS -> -0.055 WARN | (none graded) |

The three checks on the box, pipeline-3d -> this branch: body_front_skirt_aline -0.016 PASS -> **0.002 PASS**;
body_back_leg 0.0659 PASS -> **0.0753 PASS**; piece_overskirt_panel_R_hang 0.0947 PASS -> **0.0176 PASS**. The
evaluator predicted both gates' regressions exactly (clawd_mh to the third decimal).

**With the body refitted to each decimation too** (code_body reads the decimated mesh). Shell source: the largest check
change is 0.006 (piece_sleeve_R); every other is at most 0.002. The garments built on the body still move: collar 0.089
L, top 0.065, shorts 0.023, shoe_R 0.023; the hull-lofted ones move under 0.008 L. Mesh source: the same 0.112 /
0.042 / 0.016 swings as with the body fixed.

## Open items

- **Fit the skirt's hidden back hem and the flaps together (tool/body round 5).** This is what the default gate
  needs; item 2 has the numbers. The knobs: skirt_hull's fill anchors (the ±70 deg sectors are the hands' notch), the
  flaps' `length` / `train` / `trim`, and the axis. `flap_mirror` builds on the same skirt.
- **clawd_mh:** skirt `q` 0.6 (item 5) and the back-width measure (item 4).
- **The skirt's axis estimator:** the median of a partial ring. The shell makes it decimation-independent, not
  coverage-independent. An ellipse fit or the body's midline are the candidates; the flaps' frame depends on it.
- **The body is still decimation-sensitive:** `code_body.Hull` reads hull.ply and hull_pieces.npy (the decimated
  mesh): with it refitted per decimation the collar still moves 0.089 L and the top 0.065 (Gates, above). `shell_points`
  is the drop-in; code_body is tool/body's.
- **Also on the mesh:** the QA's piece3d_* checks (INFO) read the target's per-vertex pieces, and the hull hair reads
  the glb.
- **back_skirt_width's max-over-rows** (item 4) compares different heights when no row is free in both figures.
- A label that exists only on shell voxels and never on a vertex has no name in the sidecar and is dropped: on Clawd,
  label 1004, 5 voxels.
