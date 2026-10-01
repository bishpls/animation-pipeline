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

### Step 3: the B pilot (in progress)

**Code.** `charkit/geom/lockshell.py` (new): each drawn lock a template fitted to its drawn cells: a degree-5 Bezier
centreline in 3-d (least squares on each matched view's drawn centreline both ways, root and tip; a weak pull to its
start depth under the hull's envelope; smoothness; never within `gap` of the skin), a lens section `depth_ratio` 0.35
as thick as wide, broad side tangent to the head turned by one fitted twist (bounded +-46 deg), widths solved in closed
form per station from every view's drawn width (the section's extent across the projected centreline), clamped by the
bend's radius (no folds) and tapered to the tip, offset `inset` L per T-junction rank behind, the root carried in to
the scalp. Targets: per view, each splitter lock's part inside the family's hair-layer mask (a lock the splitter ran
across two families gives each its part); primary views from the family (side locks: front, then profile; the back
group: back); other views join by centreline proximity among views the lock faces (the splitter's own cross-view ids
are weak), a view the joint fit can't follow (> 4 px) dropped. Opt-in: `hair.shape.pieces_opts.lock_shells`
(`tools/hairshell/clawd_shells.json`: side locks + the back's left hem flicks, phi 100-175); hairpieces.build swaps
the family's pieces for the shells (and drops the group's wedges); cli.pieces_hair reads the new produced reference
`hair_split` (manifest; `python -m charkit hairsplit`). `python -m charkit.geom.lockshell BUILD --out DIR --cache PKL`:
the fit on a build's inputs, per lock and view its cost and IoU, the coverage of each family, a z-buffered picture.
Tests: `charkit/tests/test_lockshell.py` (closed, fold-free tube; a known lock recovered from two drawn views: 0.1 px,
IoU 0.81 / 0.74).

**Base:** `charkit/out/hs_base` (box build of the default at 4607707 / f8ad43b's merge; boards views). Its locks against
the truth (`python -m charkit hairlocks score charkit/out/hs_base`): side locks 0.394 (front 0.419, 3q 0.451, profile
0.232), lower back 0.304 (back 0.408).

**Sweep 1** (`charkit/out/hairshell/sw1`, the first cut: whole splitter locks by family majority, overlap association):
side locks front 0.560 -> 0.251 (guard: blocked), profile 0.469 -> 0.519; art_terminator_hair 2.068 -> 3.111; lock lines
3q 0.176 -> 0.207, profile 0.104 -> 0.165; hair_attached 0 -> 0.024 (a flyaway's root lost its side lock in 3q); no
back group (the back's hem locks run to the crown: their majority is the upper back). Builder folds 382 + 124.
Fixed: family-part targets, facing views only, centreline-proximity association, bounded twist, curvature clamp, scalp
roots. Fit after (ls4): 28 shells, coverage of the side-lock family front 0.557 / profile 0.578.

**Sweeps 2-3** (`sw2`, `sw3`; `tools/hairshell/sweepkeys.py OUT/sweep.json` tabulates them with each row's own builder
folds; `tools/hairshell/lockpics.py OUT LABEL=BUILD ...` scores a build's or sweep row's locks against the truth, a
row's folder given a `bundle` link to the base's):
- sw2 `sides` (side locks only): side locks front 0.560 -> 0.559, profile 0.469 -> 0.597; terminator 2.126 -> 2.063;
  lock lines 3q 0.176 -> 0.279, profile 0.120 -> 0.211; but peeks 17 -> 52, noise 0.072 -> 0.099, lock IoU against the
  truth only 0.355 -> 0.362 (side locks 0.394 -> 0.441; the 3q 0.451 -> 0.367): too many small shells (the splitter's
  fragments), gaps between them.
- sw2 `pilot` (+ the back group in place of the wedges): lower back back 0.672 -> 0.494 (guard), lock IoU 0.338.
- Then: fragments merged into their neighbour under 0.008 L^2 (an animator's lock, not every splitter piece), widened by a
  line width (the drawn regions stop at the ink), containment (the centreline half a drawn width inside the drawn
  hair in every view the lock faces), de-dup by coverage, `replace: false` for a group (laid over the family's own
  pieces). sw3: sides 0.559 / 0.697, terminator 2.431, peeks 25, folds 189 (the tubes folded).
- Folds: the root's dive to the scalp ran along the radial (degenerate frame) and the Bezier's own parameter crowded
  stations at its turns; fixed by even arc-length stations, transported and smoothed frames, a smoothstep dive (at
  most 31 deg), max-curvature clamps, smoothness prior 0.02 -> 1.0 (ls13: folds 2, fit IoU mean 0.665, coverage front
  0.610 / profile 0.537).

**Then:** the family's region as containment (a side lock shows where side locks are drawn, not over the lower back),
and each drawing view's envelope depth (the lock on top along that view's ray: `view_depth`).

**Sweep 5** (`charkit/out/hairshell/sw5`, `keys.txt`; lock scores `lp5`; base hs_base, numpy drawing):

| row | lock IoU all / side / lower | side locks front / profile | lower back front / profile / back | upper back profile / back | terminator | peeks | noise | lock lines 3q / profile | hem | folds |
|---|---|---|---|---|---|---|---|---|---|---|
| hull shell (control) | 0.355 / 0.394 / 0.304 | 0.560 / 0.469 | 0.514 / 0.665 / 0.672 | 0.621 / 0.889 | 2.126 | 17 | 0.072 | 0.176 / 0.120 | 3 | 9 |
| sides, depth 0 | 0.375 / 0.501 / 0.292 | 0.611 / 0.517 | 0.483 / **0.544** / 0.669 | 0.698 / 0.891 | 1.686 | 24 | 0.093 | 0.290 / 0.160 | 3 | 9 |
| sides, depth 0.3 | 0.381 / 0.533 / 0.292 | 0.651 / 0.516 | 0.501 / **0.547** / 0.669 | 0.705 / 0.891 | 2.089 | 23 | 0.092 | 0.245 / 0.145 | 3 | 8 |
| sides, depth 1 | 0.379 / 0.529 / 0.293 | 0.589 / 0.629 | 0.474 / 0.654 / 0.669 | 0.704 / 0.891 | 1.894 | 30 | 0.095 | 0.265 / 0.154 | 3 | 14 |
| pilot (+ back flicks over), depth 0.3 | 0.393 / 0.530 / 0.347 | 0.651 / 0.516 | 0.504 / **0.515** / 0.724 | 0.652 / 0.899 | 2.278 | 26 | 0.094 | 0.251 / 0.197 | 2 | 11 |
| **pilot, depth 1 (chosen)** | **0.387 / 0.522 / 0.334** | **0.589 / 0.614** | 0.481 / 0.608 / 0.718 | 0.666 / 0.898 | **2.018** | 37 | 0.096 | **0.269 / 0.203** | **2** | 14 |

Bold lower-back profile: the anti-gaming guard trips (> 15% down). The chosen row trips nothing: every piece within
-9% in every view (lower back front -6%, profile -9%), the side locks +5% / +31%, the back's lower back +7%.
Its costs: art_peeks_hair 17 -> 37 (WARN both: the shells leave gaps the hull's one shell didn't), hair_noise 0.072 ->
0.096 (WARN -> FAIL: more tone edges), folds 9 -> 14 (WARN band). On the build (rows are the numpy drawing): see the
render builds `charkit/out/hs_hull_r` (default) and `charkit/out/hs_shells_r` (`tools/hairshell/clawd_shells.json`).
The fit (`charkit/out/hairshell/ls_final`): 17 shells (12 side locks, 4 hem flicks + 1), 18 views fitted, IoU against
their drawn locks mean 0.650; only 1 lock fitted jointly in two views (the identity across views is the open problem).

## Step 6: extending lock shells to the whole head (exact next steps, for a lean relaunch)

1. **Identity across views first** (the pilot's weak point: 1 of 17 locks fitted in two views). Associate by the
   splitter's tip matches (`hairsplit.json` `tip_matches`, call H's links: 0.03 L) before centreline proximity; a
   target joins the lock whose tip it shares. Measure: locks fitted in 2+ views, the 3q's side-lock IoU (0.424 -> ?).
2. **Gaps (peeks 17 -> 37):** shells of one family overlap their neighbours by a line width at their drawn
   boundaries (widen toward the neighbouring target only), or an under-mass: keep the family's hull piece inset a
   further `inset` L under the shells (`replace: false` for families, as the hem group does). Gate on art_peeks_hair
   back to <= 17.
3. **Noise (0.072 -> 0.096):** the shells' shading normals: lock_shading 0.2 blends each tube's own roundness; try 0 for
   shells, measured on hair_noise and art_terminator_hair.
4. **Bangs** (`families: ["bangs", "side_locks"]`, primary front then profile): the splitter's bangs are its best
   family (0.719 profile, 0.584 front); the hull's bangs piece scores 0.769 IoU, so guard every view.
5. **Upper back** (primary back, phi 100-260): the stripes from the crown; replace: false first (over the cap).
6. **Lower back, whole hem** (both sides, phi 90-270): needs a hooked-flick template (the drawn flicks curl: a Bezier
   tube can't follow a hook; add a curl angle at the tip) and the cell targets (`unit: 'cells'`).
7. **Ahoge and flyaways:** keep their fitted templates (ahoge_fit, flyaways); only re-root them on the shells.
8. Each step: `python -m charkit.geom.lockshell BUILD --opts ...` (fit, coverage, picture), then `charkit sweep` rows
   against the hull (the guard per view), `tools/hairshell/lockpics.py` for the truth, then Michael's call on the page.

## Gate

Merged pipeline-3d c18b0c1 (garments4 Part 1) -> 9509442. Pregate at 9509442: PASS, 0 moved, 0 blocking
(`charkit/out/pregate/pregate_tool-hairshell_9509442e_into_c18b0c10.md`; the first pregate before the merge read
garments4's 57 moves). Box gate running (`python -m charkit remote gate tool/hairshell --into pipeline-3d`, log
`charkit/out/hairshell/gate.log`).

## Jobs

- the box gate (log above); render builds `charkit/out/hs_hull_r` (default) and `charkit/out/hs_shells_r` (the pilot
  spec), boards views,body,design, for the review page.
