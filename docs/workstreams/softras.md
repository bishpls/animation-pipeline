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

## Log

- 2026-09-30: started; notes skeleton.
