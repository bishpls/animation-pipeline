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
