# Hair, step 2: the B lock-shell pilot (tool/hairshell)

State: round 1 starting. Worktree `~/animation-pipeline-hairshell`, branch `tool/hairshell` from tool/hairsplit
`db2ca2d` (the lock splitter, gate PASS; it merges into pipeline-3d separately).

## The brief (Michael, 2026-09-30, via the coordinator)

Hair is the model's weakest part. The bulk is one visual-hull shell with locks painted on as regions: 0.331 against the
52-lock truth, below a random split (0.392). Michael chose **option B**: each drawn lock its own thick, tapered, layered
shell (how anime 3D hair is made). The splitter (`charkit/hairsplit.py`) finds the locks from the drawing (0.583, with
cross-view identity and T-junction layer votes). Michael's calls: F, G, H all yes; back seams A.

Plan, in order:
1. **Hem flicks (call A):** the cel shadow tone as a cue in the splitter, only where no strokes are drawn (the hem); tone
   as relative darkness against the local base, not a palette value. Target: the back hem about 0.74, the bangs
   unchanged (0.580). Re-score all views.
2. **The merge rule (bounded):** an oracle merge of the regions reaches 0.707 against 0.583. One bounded attempt (flow
   continuity, width consistency, tip ownership).
3. **The B pilot** on the side locks plus one back flick group: each matched lock a tapered, layered shell (the axis
   fitted across views, widths from the drawn widths, thickness and offset from the layer order; rooted on the scalp,
   curled at the tip). Opt-in behind a spec setting; templates first (the hull gives guesses and measurement only).
   Fitted per view to its lock cells; variants through `charkit sweep`. Scored against today's hull shell region by
   region: lock IoU, hair_lock_lines_*, builder folds, art_terminator_hair (no worse than 2.064), art_peeks_hair,
   hair_noise, every hair piece's IoU per view (the guard). Canonical rule where the views disagree.
4. **Review page** via `charkit review page`.
5. **Pregate, then gate** (`python -m charkit remote gate tool/hairshell --into pipeline-3d`); opt-in: nothing moves on
   the default spec.
6. If the pilot beats the hull shell: the plan to extend it to the whole head as exact next steps.

Out of scope (noted only): the buns' orientation ambiguity (`~/animation-pipeline-bunorient`); garments, face, hands.

## Setup

The splitter's cached inputs cloned from `~/animation-pipeline-hairsplit/charkit/out/hairsplit/` (inputs.pkl, ref/,
final/) into this worktree's `charkit/out/hairsplit/`.

## Log

## Jobs

None running.
