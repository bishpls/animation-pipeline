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

## 1. Measure first

**face5's re-gate pair is not a bun flip** (the box's gate-out base_004efc3_clawd_default and
cand_tool-face5_6fed167_into_004efc3_default; `charkit/out/bo/pair_face5.json`, `term_face5.json`):
- `tools/bunorient/pairmove.py` (each hair object's largest vertex move, and the buns' rigid rotation by Kabsch):
  hair_bun_L / R 4.8e-7 L, rotation 0.000 deg. side_lock_L moves (0.88 L at its largest vertex: re-indexed), the
  bangs and side_lock_R change vertex counts (10460 -> 10464, 4390 -> 4386), lower_back 0.0032 L.
- `tools/hairtag/termlab.py` piece swaps (art_terminator_hair, the worst view's ratio to the design's: front 3.743, 3q
  4.351, profile 5.919, back 1.355 kinks per L): before 1.804 (front), after 2.111 (3q). Swapping either bun changes
  nothing (identical readings). before + face5's side_lock_L 2.114, after + base side_lock_L 1.979; after + base
  side_lock_R 1.989, before + face5's side_lock_R 1.973; before + face5's lower_back 1.976; bangs 2.052 / 1.788.
  **The side locks carry it** (face5's own reshaping of the locks round the jaw), with the lower back. Reported to
  the coordinator 2026-09-30 20:15. This branch can't clear face5's terminator.
- The orientation ambiguity is real all the same: hull-local's B2s (the kept fit) against B2a (the annealed prior),
  IoUs within 0.02: bun_L turned 16.3 deg, bun_R 28.6 deg (pairmove.py), terminator 2.045 against 2.617.
