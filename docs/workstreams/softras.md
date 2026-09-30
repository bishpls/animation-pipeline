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

## Log

- 2026-09-30: started; notes skeleton. The rasteriser and its tests (3593734); the pilot harness (softfit); fitkit's
  opt-in gradient path (6bc550e).
