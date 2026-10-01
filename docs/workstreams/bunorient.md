# tool/bunorient: the buns' 3D orientation fixed by the drawing

Branch `tool/bunorient` from pipeline-3d 004efc3 (worktree `~/animation-pipeline-bunorient`). Follows tool/hull-local
(docs/workstreams/hull-local.md, round 2's "Open"): the stable soft bun fit (hairpieces._fit_block_soft) still has
near-equal minima close by. The silhouettes (front, profile, back) don't fix the bun's 3D orientation: two fits that match
the drawing equally (IoUs within 0.02) read the hair terminator differently (B2s 2.045 against B2a 2.617). face5's re-gate
into 004efc3 (`~/animation-pipeline-face/charkit/out/gate/gate_tool-face5_6fed167_into_004efc3.md`): art_terminator_hair
1.804 PASS -> 2.111 WARN (a flag check: blocks under K), hair_bun_L / R "geometry moved".

Brief (coordinator, 2026-09-30 night):
1. measure first: a check or test that the bun orientation is stable (1-10 um head perturbations and face5's head leave
   the orientation and the terminator put; report the residual 1-in-20 jump at 10 um);
2. an orientation constraint from the drawing (the bun's drawn inner lines, or the three-quarter view in bun_views,
   whichever the numbers favour), guarded: no view's bun IoU drops by more than noise, hair_bun_* checks hold;
3. slim charkit/tests/test_bun_fit.py (81 s on the box) without losing what it guards;
4. calibration records for new or remeasured checks, pregate, gate into pipeline-3d (don't merge).

## State

Started. Nothing built yet.
