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

### Merges

- pipeline-3d b30a7e0 (tool/hairsplit, face6 + pieceref, the tooling) -> f8ad43b.

### Step 1: the hem flicks (call A) -- done

The back's hem flicks are lobes of the under layer, drawn in the shadow tone with no lock lines: a short ink tick at
each notch and nothing else. Three changes to the splitter (charkit/hairsplit.py, all params in P):
- `notch_own` (on): a hem notch's lock line passes the notch's own drawn tick (`notch_tick`). It stopped on the tick
  at once (5 px), so the back's right hem had no lateral walls (flicks R1-R3 one region).
- `hem_tone` 'necks' (on): the shadow tone, relative (`tone_rel` 0.1 darker than its local lit base: a normalised
  convolution of the lit pixels over `tone_base` 0.08 L, two passes from the two-tone split; not a palette value), in
  the hem zone only (`hem_zone_mask`: hair at least `hem_free` 0.04 L from every drawn lock line, a stroke of 0.05 L or
  more), cut at its necks (a watershed of its distance to its edge, h-maxima `neck_h` 1.5 line widths): the walls
  between the flick lobes. 'edges' (the tone's edges as walls) and 'both' cost the flyaways (0.66 -> 0.56): off.
- tips: `tip_prom` 0.02 -> 0.012 L (the back's right hem flicks stand 2-13 px out of the crown distance), `tip_acute`
  75 -> 80 (chosen on the check pair, three-quarter + profile: 0.541 -> 0.561). `notch_between` (a notch between two
  tips with none) added, no effect here: off.

| variant (all views) | all | front | 3q | profile | back | back hem (lower_back, back) | lower_back (all) | bangs | flyaways | side |
|---|---|---|---|---|---|---|---|---|---|---|
| round 1 default | 0.583 | 0.653 | 0.467 | 0.634 | 0.541 | 0.464 | 0.465 | 0.571 | 0.661 | 0.612 |
| + notch_own | 0.609 | 0.660 | 0.454 | 0.632 | 0.636 | 0.643 | 0.58 | 0.579 | 0.67 | 0.61 |
| + hem tone edges | 0.557 | 0.606 | 0.463 | 0.576 | 0.548 | | 0.48 | 0.58 | 0.57 | 0.62 |
| + hem tone necks (h 1.5) | 0.610 | 0.677 | 0.454 | 0.625 | 0.624 | 0.621 | 0.60 | 0.579 | 0.67 | 0.60 |
| + tip_prom 0.012 | 0.619 | 0.676 | 0.449 | 0.633 | 0.657 | 0.684 | 0.64 | 0.575 | 0.67 | 0.61 |
| **+ tip_acute 80 (the new default)** | **0.627** | 0.676 | 0.498 | 0.624 | 0.657 | **0.684** | **0.632** | 0.579 | 0.672 | 0.653 |
| structure labeller (reference) | 0.548 | | | | | 0.757 | 0.742 | 0.552 | 0.426 | 0.446 |

The back hem 0.464 -> 0.684 (target about 0.74; the labeller's 0.757 has its R2 at 0 and L1/L2/R1/C at 0.98: the truth's
flick boundaries follow its tone regions). Every back flick is matched now (R2, R3 were 0): C 0.89, R1 0.84, L1 0.73,
L2 0.68, R3 0.64, R2 0.56, L3 0.45. The front's hem (L3, R3) 0.393 -> 0.587. The bangs 0.571 -> 0.579 (unchanged
within noise). The cost: the profile's lower back 0.538 -> 0.494, the three-quarter's ahoge 0.217 -> 0 (it merges
into the crown strip either way). Runs: `tools/hairsplit/sweep.py charkit/out/hairshell/hem.json ...` (now prints the
per-view lower back), pictures `tools/hairshell/zoomview.py`, `zoomtruth.py`. Final: `python -m charkit hairsplit --out
charkit/out/hairshell/split --score` (75 s).

### Step 2: the merge rule (bounded) -- one attempt, off

Ceilings on the new default (tools/hairsplit/oracle.py): regions as cut, no merge 0.611 (3q 0.659!); an oracle merge
of the regions 0.728; of the cells 0.731; our locks 0.627.

`merge_by 'flow'` (`Split._merge_flow`): the regions as nodes (multi-tip regions split between their tips first),
joined Kruskal-wise in order of a cost (flow continuity: the shared boundary's direction against the flow, |t . f|;
width: the boundary's span against the narrower node's width, merge_lambda x the shortfall), never two tips in one
lock; fragments (< 0.002 L^2) to their cheapest neighbour first; tipless groups own locks.

| merge | all | front | 3q | profile | back | ahoge | bangs | side | flyaways | lower |
|---|---|---|---|---|---|---|---|---|---|---|
| vall (default) | **0.627** | 0.676 | 0.498 | 0.624 | 0.657 | 0.52 | 0.58 | 0.65 | 0.67 | 0.63 |
| flow theta 0.5 | 0.573 | 0.563 | 0.521 | 0.561 | 0.630 | 0.59 | 0.58 | 0.50 | 0.59 | 0.60 |
| flow theta 0.2-0.3 | 0.607 | 0.605 | 0.607 | 0.591 | 0.620 | 0.71 | 0.62 | 0.51 | 0.64 | 0.60 |
| flow theta 0.1 | 0.607 | 0.603 | 0.610 | 0.591 | 0.623 | 0.71 | 0.62 | 0.51 | 0.64 | 0.60 |
| flow 0.2, lambda 0 / 1 | 0.602 / 0.601 | | | | | | | | | |
| flow 0.2, fragments 0.004 | 0.601 | 0.590 | 0.616 | 0.589 | 0.613 | 0.71 | 0.61 | 0.54 | 0.61 | 0.60 |

Reading: flow continuity fixes the three-quarter (0.50 -> 0.61), the ahoge (0.52 -> 0.71) and the bangs (0.58 ->
0.62), but costs the side locks (0.65 -> 0.51: L_front in front 0.87 -> 0.37, in profile 0.66 -> 0.37) and the
flyaways; overall 0.607 against 0.627. Kept as an option, off. The gap to the oracle (0.10) stays the merge's; a
per-family choice (flow for the bangs and the crown, the tips' Voronoi for the side masses) would need the families,
which the splitter doesn't know.

## Jobs

None running.
