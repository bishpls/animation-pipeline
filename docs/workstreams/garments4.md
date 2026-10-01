# The bow and its neighbours, then Michael's garment list (tool/garments4)

Worktree `~/animation-pipeline-garments4`, branch `tool/garments4` from tmp/batch-1001 cf08de35 (pipeline-3d de477dd +
tool/face6 + tool/pieceref, gating into pipeline-3d). Merge pipeline-3d once the coordinator says the batch merged.
The one garments agent while hair is the focus. Rules: `~/.claude/agents/charkit-worker.md` (policy K, the guard, the
tools: `charkit sweep`, declared checks + `calibrate --declared`, `charkit review page`, docs/CODEMAP.md).

Read-only prior work: tool/collar4 (`~/animation-pipeline-garments3`, collar.md rounds 7-8: E2, the lapels, the back
cream panel), tool/sleeves (`~/animation-pipeline-sleeves`, sleeves.md: the pear puff V1, the straight cuff band B1/B2;
untracked harness specs; conflicts with pieceref in collarqa.py), tool/pieceref (pieceref.md: w4, t12, the
attribution of the blockers).

## Brief
**Part 1 (one gate):** `close_hung.on` + `pleat.on` (w4 + t12) with the neighbours placed as drawn:
(a) the collar's lapels end inside the bow's top edge (art_outline_collar 1.379 -> 2.096 came from the lapels reaching
the bow's corners); (b) the sleeve caps 0.06 L up toward the drawing (sleeve_front_spikes_L/R; Michael's "shoulders
still misshapen"); (c) the bust/loop contact behind bow_front_bleed fixed at its source (the bust or jacket front, or
loops conforming without moving forward). Expected: no flag regressions (bleed, loop_end, art_outline_collar back to
PASS), torn/spike checks clear. Review page asks Michael the bow's three compromises (knot graded front only; w4's
slanted loop ends; the loops' bottom at 0.30).

**Part 2 (Michael's list, 2026-09-30), each a declared + calibrated check first, then the fix:** (1) creases, folds,
pleats as a mechanism the outline renderer draws (skirt's cream panel, the bow); (2) cuffs: no cream, 1.5-2.4x the
drawn area; (3) shoulders with the back view's cream collar section; (4) the neck-to-bow V: skin, not orange (open V +
the body's neck-chest join).

## State
- Setup: notes created; variant specs under `charkit/out/garments4/specs/` (untracked): `p1.json` = clawd.json with
  close_hung.on and pleat.on.
- pipeline-3d ca489f3 (the batch, same tree as cf08de35) merged in (3c10f1c4).
- Box builds (no boards): `charkit/out/g4_before` (the default spec at cf08de35) and `charkit/out/g4_p1` (p1.json).
  Local helpers (diagnostics, not variant harnesses) in `charkit/out/garments4/tools/`: qcmp.py (checks side by
  side from qa.json), frontrows.py (collar/bow extents per row, drawn vs ours), sleevetop.py (sleeve tops per column),
  buried.py / rim.py (bow depth against the jacket). Produced outfit masks and hull copied from pieceref's out dir
  (stamps 60d84d9b / c798637e) for local reads. Sweep declarations live in `tools/garments4/` (untracked: charkit/out
  isn't synced to the box), outputs in `charkit/out/garments4/sweeps/`.

## Part 1, measured (box builds)
p1 against before (pipeline-3d's bow), the moves:

| check | before | p1 | |
|---|---|---|---|
| piece_bow F/3q/P | 0.896/0.758/0.345 | 0.951/0.852/0.683 | guard up |
| bow_front_bleed (flag) | 0.0 P | **0.2825 F** | blocks |
| sleeve_front_spikes_L / R | 0 / 0 P | **0.0286 / 0.0188 F** | new FAILs, block |
| art_outline_collar (flag) | 1.379 P | 1.402 P | **does not regress on this base** (t12 + the batch) |
| bow_*_torn, collar_front_torn | P | P | t12 clears them |
| collar_three_quarter_torn | 0 P | 0.0045 W | not blocking |
| body_profile_chest | 0.002 P | 0.0482 W | not blocking (the pleat's thinner loops) |
| bow_part_*, iso_bow_*, bow_profile_* | FAIL mostly | P/W | the pleat's gains |

- **(a) The lapels** (frontrows.py): ours end 0.04 L inside the lobes' upper outer corner (collar |x| 0.351 at z
  -0.607; bow corner 0.39 at -0.626), the drawn 0.02-0.04 inside (0.337-0.346 at -0.588; corner 0.34-0.36 at
  -0.607). What differs is the lapel's width at the shoulder: drawn outer |x| 0.39-0.40 at z -0.49..-0.51, ours
  0.22-0.25 (our lapel is a triangle widening down to the bow; the drawn one is wide at the shoulder and narrows to
  it): Part 2 item 3's (the shoulders and collar). art_outline_collar passes on p1 (1.402) and the sleeve caps lower it
  further (0.71-0.82).
- **(b) The sleeve caps** (sleevetop.py, front): ours 0.06 L under the drawn top over |x| 0.43-0.55 (-0.555 against
  -0.494) and 0.08-0.10 under it at 0.57-0.64 (the drawn shoulder squarer): the puff's `out` extent at its top
  stations, not only the cap. s1 (sweep, cap): 0.15 spikes_L 0.02 F; 0.18 spikes_L 0 P but sleeve_front_profile_L
  0.0433 F (before 0.0293 W: a new FAIL) and piece_sleeve_L profile -6%. sleeve_R didn't move: **the evaluator's
  piece cache keyed a garment on its own spec** (sleeve_R mirrors sleeve_L): fixed, bodyeval.garment_deps.
- **(c) The bleed** (buried.py): the lobes' lower parts (z -1.00..-0.90 in the bundle's frame, |x| 0.09-0.33) sit up
  to 0.068 L behind the jacket's front at their (x, z). Fix at the source: the jacket bedded under the bow
  (garments.bed, a shell knob `bed` {under, gap, margin, ease}: the shell set `gap` behind the bow's back where the
  bow covers it and `margin` round its outline, easing back over `ease`; only ever backward). On top and bodice_panel.

## Part 1, fixed (sweeps on g4_p1, box: `charkit sweep run tools/garments4/sN.json --box`; outputs sweeps/s1-s4)
- **(c) the bleed: the jacket bedded under the bow** (`top.bed` {gap .01, margin .02, ease .04}; the lobes only:
  `parts` 'lobes', the knot's and the tails' root's deep backs at the middle left out). bow_front_bleed 0.2825 F -> 0 P;
  also bow_profile_loop_thick 0.0431 -> 0.0306 W, loop_lean 4.84 -> 0.62, bow_three_quarter_torn 0.0037 -> 0.0007,
  piece_top 3q/profile +0.024/+0.030; piece_bow front 0.951 -> 0.934 (-1.8%: the strips' lower rims now show, no longer
  under the jacket). The bib bedded deeper (`bodice_panel.bed` gap .035, margin .03, ease .05) so it stays behind the
  dented jacket. **Guard note:** piece_bodice_panel's profile view 0.342 -> 0.19 against the sweep's control: the drawn
  bib in profile is a 224 px sliver (0.005 L^2), ours 40 px (pieceov.py, review/bib_profile_p1.png): a visibility-floor
  case (the guard's planned floor); against pipeline-3d's 0.169 it is up. Reported, not hidden.
- **(b) the sleeve caps: tool/sleeves' V1 pear table** (sleeve_L.profile; sleeve_R mirrors it): spikes_L/R 0.0286 /
  0.0188 F -> 0 P, **shoulder_back_line (flag) 0.0565 F -> 0.0047 P**, sleeve_profile_profile_L 0.0429 F -> 0.0297 W,
  sleeve_front_profile_L 0.0365 -> 0.0256 W, piece_sleeve_L front 0.865 -> 0.948, R front 0.894 -> 0.954. Costs:
  piece_sleeve_R three_quarter 0.419 -> 0.322 (-23% against the control; -9% against pipeline-3d's 0.353: the far sleeve
  in 3q, where our top is already 0.03-0.06 L above the drawn one while the front's is 0.06 L under: the views disagree),
  piece_sleeve_L profile -4%, back -4%; sleeve_back_profile_L/R 0.066 F -> 0.083/0.086 F (FAIL both; tool/sleeves: the
  drawn back view labels the cap's top as jacket), sleeve_front_profile_R 0.0161 P -> 0.0205 W. `cap` 0.18 (s1/s2)
  cleared the spikes too but made sleeve_front_profile_L a new FAIL (0.0433).
- **(a) the lapels: no change** (measured above: the corner meets the bow as drawn on this base; art_outline_collar
  1.402 P, 1.44 with V1).
- Spec (2b4653d): close_hung.on, pleat.on, sleeve_L.profile = V1, top.bed, bodice_panel.bed (tools/garments4/part1.json,
  setspec.py keeps the file's formatting). Pregate (2b4653d+dirty into 257222b): PASS, 57 moved, 0 blocking.
  pipeline-3d 257222b (tool/hairsplit + the handoff) merged (fe90cb19).
