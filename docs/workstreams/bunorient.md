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

**What face5 changes in the side locks** (the gate pair's pieces.json reports): the lock partition moves:
side_lock_L tips 38 / 58 / 74 -> 34 / 58 / 82 deg, side_lock_R -74 / -66 -> -78 / -62; body-clearance push 0.0401 ->
0.0338 L (L) and 0.0326 -> 0.0283 (R); side_lock_trim pulled 91 -> 88 cells, pull_max 0.2324 -> 0.2162 L; the hull's
labels front 6527 -> 6539, filled 2353 -> 2355; field cells 2693 -> 2697. The locks read the face through the hull's
labels (the carve near the cheek), the skin's clearance (F['S']: trim floor, body_clear) and case.chin_z (the trim stops
at the chin). Which one moves the tips: `tools/hull_local/hairswap.py` on the pair (B = face5, A = base; B+headA,
B+hullA), next.

## Plan for 2 (the orientation constraint), not started
- `hairpieces.fit_block(start=)` (committed): the soft fit's first stage from another pose, the prior still on
  block_frame's: the multistart probe. A tool `tools/bunorient/orient.py` to write: capture (bunstab.capture plus
  bun_targets' inputs: the hair layers' masks, so targets can be rebuilt with other bun_views / per_side), then per
  variant: the base fit, perturbations (head 1 and 10 um, points 3 seeds; bunstab.perturbations) and starts rotated
  +-10 / 20 deg about each axis; per fit the bun mesh, Kabsch angle to the base fit, loss, IoUs. Determined = the
  starts land within ~1 deg, or the lowest-loss basin is clear of the next by more than the 10 um noise.
- Candidate A: three_quarter in bun_views with bun_per_side (the hair layers have three_quarter__bun_L / _R; the 3q
  view's az 35.47 deg; without per_side bun_targets skips the 3q). The soft path has no occlusion: the far bun's
  hidden part lands on the drawing's other hair (w_over 0.25). Maybe the near bun only.
- Candidate B: the bun's drawn inner lines (ink inside the bun masks) against our knot / loop boundaries projected.
- The terminator per fit: swap the refit buns into the base bundle (o/hair_bun_*/eval/V; lnor = geometric vertex
  normals per loop; shrink = outline thickness -0.0014 x the normal; raw/V) and run the artifacts part (termlab's
  measure); validate by reproducing the build's own reading.
- Base build for the capture: `charkit/out/bo_base` (box build of a26f4c2 = pipeline-3d 3f7b730, running).

**Which input moves the side locks** (the coordinator's question, 2026-09-30 night; hairswap.py on the box from the face
copy, A = base `bo_base` + its hull, B = face5 `f5m` (aac435e) + its hull; `~/animation-pipeline-face/charkit/out/f5swap/
swap.json`): B's own inputs reproduce B's pieces exactly. With A's **hull**: the bangs are A's (5.4e-5 L) and the lower
back A's (8.9e-5 L); side_lock_R takes A's vertex count (0.009 L from A's); side_lock_L matches neither. With A's
**head**: side_lock_L 0.010 L and side_lock_R 0.0089 L from B's, B's counts, the bangs 0.0063 L. So the hull carries
it (face5's jaw changes the carve between the cheek and the locks: the hull's labels front 6527 -> 6539, and the lock
partition, tips 38 / 58 / 74 -> 34 / 58 / 82), with the skin's clearance from the new jaw adding about 0.01 L (trim
pulled 91 -> 88 cells, push 0.040 -> 0.034 L). Neither alone gives the base's side locks. It is the hair answering the
new jaw through the lock partition: no clean local fix in tool/face5 (a fix is in the lock partition's stability,
tool/hair5's ground). Stopped there as the coordinator asked; for Michael as a named acceptance.

## Checkpoint (2026-09-30 ~20:40, context budget)
- head: this branch a26f4c2 + commits (the start= option, notes, pairmove.py); pipeline-3d 3f7b730 merged.
- outputs: `charkit/out/bo_base` (box build of a26f4c2: art_terminator_hair 1.804 PASS, hair_piece_buns 0.862,
  hair_bun_outline 0.459), `charkit/out/bo/base_inputs.pkl` (bunstab capture on bo_base: both fit_block calls'
  arguments; rebuilt buns 0 L from the build's; the box copy has it too).
- next: write tools/bunorient/orient.py (plan above), measure the base fit's multistart spread and the 10 um jumps on
  base_inputs.pkl, then try three_quarter in bun_views (needs bun_targets' masks: extend the capture), then the slimmed
  test, then calibrate / pregate / gate.

## Round 2 (2026-09-30 night, relaunched lean after face5's calibration)
- `tools/bunorient/orient.py`: `capture` (bunstab's plus bun_targets' inputs: the 25 hair-layer masks, the views, the
  hull frame; `charkit/out/bo/base_inputs_tg.pkl` from bo_base, rebuilt buns 1.4e-8 / 1.2e-8 L from the build's) and
  `spread` (per bun, the fit from block_frame's pose and 12 starts rotated +-10 / 20 deg about each axis; each fit's
  rotation from the default start's fit, soft loss, and IoU in all four views, fitted or not). Variants: default,
  per_side, tq (the three-quarter added), tq_near (the near bun only in the three-quarter).
- Running (laptop): bunstab stab at 1 um and 10 um on base_inputs.pkl -> `charkit/out/bo/stab_1um.json`,
  `stab_10um.json`; orient spread default / tq / per_side / tq_near -> `charkit/out/bo/spread_*.json`.
