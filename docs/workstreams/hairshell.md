# Hair, step 2: the B lock-shell pilot (tool/hairshell, round 2: tool/hairshell2)

State: **round 4: the default switched** (Michael's yes; see "## The default switch" at the end; round 4's own gate PASS under K; review page `charkit/out/hairshell3/review/index.html`; see "# Round 4" at the end). Round 3 stopped at a checkpoint (coordinator's wrap-up, weekly capacity; tool/hairshell3; see "# Round 3" at the end: no real build, no gate this round). Round 2 done (gate PASS; see "Round 2 result"). Round 1 (below) as it was. Worktree `~/animation-pipeline-hairshell`, branch `tool/hairshell` from tool/hairsplit
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
(`charkit/out/pregate/pregate_tool-hairshell_9509442e_into_c18b0c10.md`). **Box gate: PASS** under K, tool/hairshell
e28fd7f into pipeline-3d c18b0c1: nothing blocks; reported: the motion part's code closure reaches the changed
pieces_hair / hairpieces.build / lockshell (no check moved: the geometry is the same); build CPU 1.18x
(`charkit/out/gate/gate_tool-hairshell_e28fd7f_into_c18b0c1.md`). Commits after e28fd7f: notes only.

## Render builds and the review page

`charkit/out/hs_hull_r` (default) and `charkit/out/hs_shells_r` (`tools/hairshell/clawd_shells.json`), render box,
boards views,body,design. Their QA (render drawing) against the sweep's numpy reading: side locks front 0.560 -> 0.589,
profile 0.469 -> 0.612; lower back 0.514 / 0.665 / 0.672 -> 0.481 / 0.607 / 0.717 (no piece down more than 10%); lock lines
3q 0.176 -> 0.271, profile 0.104 -> 0.223; hem 3 -> 2 PASS; **art_terminator_hair 2.009 -> 2.32** (the brief's limit
2.064; the sweep's numpy drawing read 2.126 -> 2.018: the render drawing's terminator disagrees, so it is the first fix
next round, measured on a render build); art_peeks_hair 17 -> 39; hair_noise 0.072 -> 0.098 (FAIL); folds 9 -> 15. Lock
IoU against the truth (`tools/hairshell/lockpics.py`, lp7): 0.355 -> 0.387 (side locks 0.394 -> 0.521, lower back 0.304 ->
0.333). Review page: `charkit/out/hairshell/review/index.html` (`python -m charkit review page
charkit/out/hairshell/review.json --out charkit/out/hairshell/review`; the page tool gained `figures` sections).

**Decision for Michael (on the page):** lock shells the default for the pilot region now? Recommended no (terminator,
gaps, identity first); extend B to the whole head next? Recommended yes; hem flicks over (A) or in place (B)? A.

**First steps of the next round** (before step 6's list): the terminator on the render build (swap the shells' shading
normals: lock_shading 0 for shells, or the shells out of the envelope normals' union: `charkit sweep swap
charkit/out/hs_hull_r charkit/out/hs_shells_r --check art_terminator_hair` names the carrier), then the gaps (peeks).

## The candidate (converged, coordinator 2026-10-01): lockshell DEFAULT

proxy shading, shade_lock 0, widen {side_locks 4, lower_back 2}, over_ink 0.3, join 'sequential' (three-quarter on, no
trim), fold_fix 4 (sw10: a folded shell narrowed 0.7 a step round its folded faces: shells' folds 2 -> 0), shade_at
'vertex' (sw11: sampling the proxy at its nearest vertex, all shells or the flicks only, is worse: terminator mean
1.89 / 2.11). Real builds: `charkit/out/hs2_shells_r` (before fold_fix: folds 12, f10.2 5 and f21.1 2 on the box, 0
on the laptop: those two locks still fit differently on the two machines), `charkit/out/hs3_shells_r` (the candidate).

## Round 2 result (real render builds; review page charkit/out/hairshell2/review/index.html)

| measure | hull (hs_hull_r) | round 1 (hs_shells_r) | round 2 (hs3_shells_r) |
|---|---|---|---|
| art_terminator_hair (placement; 6-placement mean +- std, max) | 2.009 W (2.007 +- 0.081, 2.155) | 2.32 W (1.989 +- 0.183, 2.320) | **1.624 P** (1.956 +- 0.225, 2.234) |
| per view, 6-placement mean F / 3q / P / B | 7.51 / 8.22 / 3.81 / 1.87 | 6.84 / 5.91 / 2.64 / 2.63 | 6.08 / 4.11 / 1.85 / 2.52 |
| art_peeks_hair (placement / mean) | 17 / 17.5 | 39 / 34.2 | 18 / 17.0 |
| hair_noise | 0.0717 W | 0.098 F | 0.0784 W |
| hair_folds | 9 | 15 | 9 |
| hair_back_lines | 0.894 W | 1.305 F | **0.459 P** |
| hair_back_hem | 3 W | 2 P | 2 P |
| lock lines 3q / profile | 0.176 / 0.104 | 0.271 / 0.223 | 0.228 / 0.112 |
| truth lock IoU all / side / lower back | 0.355 / 0.394 / 0.304 | 0.387 / 0.521 / 0.333 | **0.401 / 0.569** / 0.328 |
| side locks F / P | 0.560 / 0.469 | 0.589 / 0.612 | 0.585 / 0.604 |
| lower back F / P / B | 0.514 / 0.665 / 0.672 | 0.481 / 0.607 / 0.717 | 0.496 / **0.588** / 0.712 |
| locks in 2+ views | - | 1 / 17 | 2 / 17 |

Still losing to the hull, with causes: hair_noise (front: the lower back's tone edges 224 -> 506, seen beside the
side shells; the check draws no outlines, so occlusion boundaries count), the lower back's profile IoU (-11.6%: the
widened side shells cover it), the back view's terminator mean (1.87 -> 2.52: the flicks' terminator steps), peeks at
the one placement (17 -> 18; the means tie), identity (2 / 17; joined views compromise), 3 locks still
machine-dependent (f10.2 folds 4 on the box).

## Round 3 (lean): next steps

1. hair_noise: ask the check's owner whether occlusion boundaries should count (it draws without outlines); else
   shade the lower back where the side shells overlap it toward their tone, measured on noisemap.py.
2. The lower back's profile: widen the side shells toward their neighbours only (in the front's plane), not in
   profile; per-view widening from each view's gaps.
3. The flicks' back terminator: the flick's normal blended toward the mass's over its root half (shade_at was all or
   nothing).
4. Identity: a lock breakdown sheet (Michael's rule 2) before more association work; the assoc records
   (pieces report lock_shells.locks[].assoc) say per view why a lock didn't join.
5. Then extend (step 6's list: bangs, upper back, whole hem, ahoge/flyaways re-rooted), region by region on real
   builds.

## Jobs

None running.

# Round 2 (tool/hairshell2, from pipeline-3d 6620113)

Worktree `~/animation-pipeline-hairshell`, branch `tool/hairshell2`. Harness scripts and outputs: `charkit/out/hairshell2/`.

## Step 1: why the sweep read 2.018 and the build 2.32 (measurement fidelity) -- found, for the infra queue

The hair's art checks (art_terminator_hair, art_peeks_hair, ...) don't depend on the drawing setting: artifactqa's head
frame reads its own numpy z-buffer (`artifactqa.buffers`) under both drawings, so numpy against render is not the cause.
Measured on hs_shells_r's own bundle locally: 2.32 exactly (8 s, `charkit/out/hairshell2/splicecmp.py`). Three causes:

1. **The sweep's splice ignored the pieces' `outline_w`** (the Blender build's outline_w vertex group: the ink fades
   where the back's locks meet). `sweep.hair_arrays` drew every hair line full width. On the build's own geometry the
   splice read 2.207 against the build's 2.318; with the splice's shrink times outline_w it reads 2.318 (peeks 43 ->
   39 = the build's). **Fixed** in `charkit/sweep.py` (hair_arrays takes `ow`, HairStage loads it from the npz).
   Also fixed: `sweep._changed` compared only vertices, so a shading-only variant (same V, new normals) was never
   spliced and read the base; it now compares vn and outline_w too.
2. **The lock-shell fit wasn't reproducible**: the same spec and code fitted on two machines (or on two box builds of
   one head, whose envelope fields differ by 1e-10 m) gave shells up to 1.3 cm apart (side_lock_L; lower_back 4 mm).
   The art reading of three such fits of one spec: 2.026 (sweep 5's), 1.932 (a local refit today), 2.318 (the box
   build). So the sweep row and the build were two draws of the fit, not one geometry measured two ways; this was most
   of the gap (2.026 -> 2.318 with the splice fixed). Causes in `lockshell`: scipy's default finite-difference step
   (1.5e-8 m) probing an objective with pixel-level corners (the nearest drawn station's width, a step function; the
   envelope ray-cast's first sample inside, which jumps a ray step when noise flips a sample; NaN depths off the drawn
   hair read as 0). **Fixed** (opt-in code only): `diff_step` 1e-3 (a millimetre, about a drawing pixel),
   `soft_width` (Gaussian-weighted drawn widths), the ray-cast's crossing interpolated, the depth map filled off the
   hair. Two contexts 1e-10 apart now fit to a median 1e-6 m (was 9e-4); one lock (f10.2, front-only, 7 px cost) still
   forks (4 cm, equal cost): an ill-posed single-view lock (cross-view identity is the cure: step 4).
   (`charkit/out/hairshell2/determ2.py CTX_A CTX_B`.)
3. Blender's loop normals differ from the pieces' vn by up to ~0.5 deg (custom normals as stored): the hull's own
   pieces spliced back read 2.065 against its build's 2.009. Small; not fixed (note for the infra queue: the splice
   could round-trip normals the way Blender stores them).

4. **The check's own sampling noise is as large as the move**: art_terminator_hair under six sub-pixel placements
   of the head frame (`charkit/out/hairshell2/termnoise.py BUILD [N] [PIECES]`, render.calibrate's offsets):
   hs_hull_r 2.007 +- 0.081 (1.875-2.155), hs_shells_r **1.989 +- 0.183** (1.757-2.320). The build's 2.32 is the
   highest of the six placements; the shells' mean equals the hull's. Peeks: 17.5 +- 0.8 against 34.2 +- 2.5 (that
   move is real). From here every terminator reading is given as the frame's own placement (what the gate reads) and
   the six-placement mean +- std. Note for the infra queue: the gate compares one placement of a check whose noise
   is ~0.1-0.2 against a 2.0 / 2.5 grade line.

Rule kept this round: every art_* number in this round's tables is from a real build's bundle, or a splice of a real
build's pieces (`splice2x2.py`: the sweep's splice with outline_w), not a sweep row's own refit.

## Step 2: the shading (in progress)

Carriers (`charkit sweep swap hs_hull_r hs_shells_r --check art_terminator_hair --groups hair --drop`,
`charkit/out/hairshell2/swap_term/swap.md`): the back view (1.154 -> 2.32 ratio) carries it; B + A.lower_back takes
back 115% of the move (back 2.32 -> 1.45), B + A.upper_back 66% and B + A.side_lock_R 52% although the upper back's
geometry is the same in both builds: **the shells changed every piece's shading normals** (bangs and upper back up to
3.3 deg, every corner): `hairpieces.shade_normals` takes the envelope of the union of all pieces, shells included.
Fix: lock_shells `shade: 'proxy'` (default for shells): the envelope's solid is the pieces as the default builds them
(each piece's wedges), sampled at every final vertex (`smooth.envelope_normals(at=)`), so the untouched pieces keep the
default's normals exactly and the shells shade as the hull's mass does where they lie. `shade_lock`: lock_shading on
the shells' vertices (style 0.2).

Sweeps on base hs_shells_r, every hair object spliced (the sweep's splice, outline_w honoured); terminator as the
frame's placement and the six-placement mean +- std (`termnoise.py` on the row's pieces spliced into hs_shells_r):

| row (sw1, sw2) | terminator (placement / mean +- std) | per view mean F / 3q / P / B | peeks (placement / mean) | hair_noise |
|---|---|---|---|---|
| hull (the default's pieces) | 2.196 / 2.057 +- 0.103 | 7.70 / 8.57 / 3.74 / 1.70 | 17 / 17.5 | 0.0717 W |
| shells, proxy shading, shade_lock 0.2 | 1.918 / 2.160 +- 0.227 | 6.61 / 5.23 / 1.56 / 2.93 | 29 / 26.3 | 0.096 F |
| shells, union shading (round 1), shade_lock 0.2 | 1.622 / 1.787 +- 0.173 | 6.07 / 5.00 / 1.39 / 2.32 | 29 / 26.3 | 0.0961 F |
| **shells, proxy, shade_lock 0** | **1.510 / 1.616 +- 0.086** | 5.83 / 5.74 / 1.99 / 1.69 | 29 / 26.3 | 0.0871 F |
| shells over the side lock's wedges (under), proxy, sl 0 | 2.367 / 2.294 +- 0.117 | 8.59 / 8.46 / 3.58 / 1.57 | 22 / 23.3 | 0.0703 W |

Reading: the shells' own relief (lock_shading 0.2: a narrow tube's ring normals blended in) tears the terminator,
the back's hem flicks most (back 2.93 -> 1.69 with it off). shade_lock 0 for shells is the shading fix (terminator
mean 1.62 against the hull's 2.06). The underlayer brings back the hull side lock's own terminator (front 8.6).

## Step 3: the gaps (in progress)

`charkit/out/hairshell2/peekmap.py BUILD PNG`: the peeks by object and view. hs_hull_r -> hs_shells_r: front 15 -> 25
(lower_back 2 -> 10, upper_back 3 -> 8), three-quarter 17 -> 39 (lower_back 2 -> 13, upper_back 6 -> 14): the back's
pieces seen in slivers between the narrow side-lock shells (their coverage of the side-lock family ~0.55-0.6).
`under` (lock_shells: families whose own wedges stay under their shells, the shells laid over them by `over`, the
front-most layer furthest out): any gap shows the side lock's own mass, connected to its large component.

More rows (sw3-sw5; all shade_lock 0, proxy; folds from each row's pieces report, since the sweep's hair_folds
reads the base's: an infra note):

| row | terminator place / mean | peeks place / mean | hair_noise | folds | side locks F / P | lower back F / P / B | lock lines 3q / P |
|---|---|---|---|---|---|---|---|
| hull (hs_hull_r, the build) | 2.009 / 2.007 | 17 / 17.5 | 0.0717 W | 9 | 0.560 / 0.469 | 0.514 / 0.665 / 0.672 | 0.176 / 0.104 |
| shells, union, sl 0 | 1.482 / - | 29 | 0.086 F | 5 | 0.559 / 0.607 | 0.480 / 0.603 / 0.719 | 0.268 / 0.229 |
| widen_lw 2 | 1.828 | 22 | 0.0832 F | 7 | 0.593 / 0.610 | 0.493 / 0.597 / 0.714 | 0.256 / 0.219 |
| widen_lw 3 | 1.551 | 23 | 0.0803 F | - | 0.613 / 0.599 | 0.502 / 0.589 / 0.707 | 0.249 / 0.192 |
| **widen_lw 4** | **1.441 / 1.548 +- 0.141** | **19 / 17.7** | 0.0768 W | 7 | 0.620 / 0.581 | 0.507 / 0.580 / 0.701 | 0.237 / 0.168 |
| widen_lw 5 | 1.168 | 19 | 0.0746 W | 7 | 0.619 / 0.558 | 0.512 / 0.569 / 0.695 | 0.238 / 0.159 |
| widen_lw 6 | 1.18 | 19 | 0.0721 W | 11 | 0.617 / 0.535 | 0.515 / **0.556** / 0.688 | 0.228 / 0.123 |
| under, widen 2 | 2.266 | 19 | 0.0685 W | - | 0.552 / 0.488 | 0.531 / 0.594 / 0.715 | 0.239 / 0.189 |
| under, widen 4 | 2.023 | 21 | 0.0655 W | - | 0.545 / 0.478 | 0.529 / 0.574 / 0.703 | 0.228 / 0.191 |

Bold lower back profile: past the guard's 15% (0.665 -> 0.556). Reading: widening closes the gaps (peeks 29 -> 19,
the six-placement mean 17.7 = the hull's 17.5) and lowers the noise; the lower back's profile pays (the side shells
cover it there). The underlayer brings the side locks' IoU back to the hull's (it is the hull's piece) and the
terminator with it. hair_noise by object (`noisemap.py`): front view, the hull 0.121 / widen 4 0.143; its extra edges
are the lower back's (224 -> 484): the lower back seen in the gaps beside the side shells, a shade tone against the
shells' lit one. Without outlines (as hair_noise draws) every occlusion boundary between two pieces of different tone
counts as noise: a question for the check's owner, not changed here.

## Step 4: identity across views (in progress)

`charkit/out/hairshell2/assoc2.py CTX [OPTS]` (the dev copy `lsdev.py`) and now each lock's `fit.assoc` in the pieces
report: per other view faces away / no candidate (nearest, claimed?) / joined / dropped (its joint cost, the primary's).
Found: (1) **the three-quarter had no targets at all**: `targets()` skipped a view that has any `VIEW__*` mask but not
the family's, and the three-quarter has the buns' masks (`three_quarter__bun_L/R`): fixed (only hair families' masks
count). (2) Registration is not the problem: the hull's hair projected into each view is best within 2 px; the
splitter's matched tips' heights agree with ours to the digit (front-profile 0.054 L mean apart: the splitter's links
disagree in height, they are weak). (3) The joint fits fail on cost: the primary view's cost rises 1-3 px -> 5-9 px
when another view's drawn lock joins. Secondary views are now trimmed to the heights the shell spans and their root
end isn't pulled (`trim_other`, `root_w_other` 0): 0 -> 2 of 17 locks in two views at view_cost_max 4 (f20.1 front +
three-quarter, f52.1 front + profile); 3 of 17 at view_cost_max 6 with primary_slack 1.5 px; 5 of 17 at 8 / 2.0.
The splitter's own links (hairsplit.json matches, xid) point 35-95 px away from the shells' projections for these
locks: not usable as association yet.

Then (sw6-sw8): the three-quarter fix and joins per view (`join` 'sequential': each other view tried alone, nearest
first, kept when the fit follows it, so one bad view no longer takes the others out: round 1's joint drop). Every row
shade_lock 0. Lock IoU against the 52-lock truth (`tools/hairshell/lockpics.py`, lp1 / lp2):

| row | locks 2+ views | truth all / side locks / lower back | side F / P | terminator place / mean | peeks place / mean | back_lines | hem | noise | folds |
|---|---|---|---|---|---|---|---|---|---|
| hull | - | 0.355 / 0.394 / 0.304 | 0.560 / 0.469 | 2.009 / 2.007 | 17 / 17.5 | 0.894 W | 3 W | 0.0717 | 9 |
| round 1 shells (hs_shells_r) | 1 / 17 | 0.387 / 0.521 / 0.333 | 0.589 / 0.612 | 2.32 / 1.989 | 39 / 34.2 | 1.305 F | 2 P | 0.098 | 15 |
| widen 4, 3q off (sw3 wide4) | 1 / 17 | **0.407 / 0.589 / 0.350** | 0.620 / 0.581 | 1.441 / 1.548 | 19 / 17.7 | 1.255 F | 3 W | 0.0768 | 7 |
| widen 4, 3q on, trim (sw6 id_w4) | 2 / 17 | 0.401 / 0.557 / 0.350 | 0.586 / 0.602 | 1.631 / 1.739 | 21 / 19.8 | 1.259 F | 3 W | 0.0776 | 7 |
| widen 4, sequential (sw7 seq_w4) | 2 / 17 | - | 0.583 / 0.604 | 1.632 / - | 19 | 1.255 F | 3 W | 0.0777 | 7 |
| side 4 / flicks 2 (sw8 s4f2) | 2 / 17 | - | 0.583 / 0.603 | 1.628 | 20 | 1.343 F | 2 P | 0.0781 | 7 |
| **+ over_ink 0.3 (sw8 s4f2_ink30)** | 2 / 17 | 0.397 / 0.559 / 0.328 | 0.583 / 0.603 | 1.628 / 1.806 +- 0.123 | 19 / 18.2 | **0.462 P** | 2 P | 0.0781 | 7 |
| + over_ink 0.15 | 2 / 17 | - | 0.583 / 0.603 | 1.628 | 19 | 0.316 P | 2 P | 0.0781 | 7 |

Readings: (a) **hair_back_lines** (a flag check, the back's ink inside the mass) was a FAIL on round 1's build too
(1.305 against the hull's 0.894 WARN), missing from round 1's table: the hem flicks laid over the back drew their
whole outlines. `over_ink` (a laid-over group's shells ink only their last 30% toward the tip, as the design's
flicks: a tick at each notch) takes it to 0.462 PASS. (b) The flicks widened 4 line widths lose a hem tip (hem 2 ->
3); flicks at 2, side locks at 4 keep hem 2 PASS. (c) Joining the three-quarter (f20.1) costs the front's side-lock
IoU (0.620 -> 0.583) and the truth score (side locks 0.589 -> 0.559): the joined views compromise rather than agree.

## Jobs

- sw1-sw5 done (`charkit/out/hairshell2/swN.json` -> `swN/`). sw6-sw9 done (sw9: the underlayer set in 0.02 / 0.04 L: folds 7 -> 21-22, side locks' IoU down: off).
- Merged pipeline-3d d0d6304 (garments4 Part 2) -> bc26951. Pregate at bc26951: PASS, 0 moved
  (`charkit/out/pregate/pregate_tool-hairshell2_bc269518_into_d0d6304c.md`).
- Real render-box builds of the pilot (spec tools/hairshell/clawd_shells.json): `charkit/out/hs2_shells_r` (before
  fold_fix), `charkit/out/hs3_shells_r` (the candidate at 4c2ddc2). None running. Pregate at 4c2ddc2: PASS, 0 moved. **Box gate: PASS** under K, tool/hairshell2
  5ca5f37 (code 4c2ddc2) into pipeline-3d d0d6304: nothing blocks; reported: the motion part's code closure reaches
  hairpieces / lockshell (no check moved: the default's geometry is the same); build CPU 1.17x
  (`charkit/out/gate/gate_tool-hairshell2_5ca5f37_into_d0d6304.md`). (A first launch failed: a notes commit landed
  while the gate bundled the branch; don't commit while a gate starts.)


# Round 3 (tool/hairshell3, from pipeline-3d 1d57838)

Coordinator's calls (2026-10-01): don't switch the default yet; first (a) reproducibility (every lock's fit
bit-identical, laptop vs box, with a test) and (b) the back view's terminator (judge look checks on the six-placement
average too); hair_noise remeasured with the outlines drawn as the render draws them, then recalibrated (design jitter
PASS, known-bad FAIL, random floor; never loosen); one paid reference attempt (an exploded lock breakdown, n=2) for
cross-view identity, else the canonical rule's step 3; then the lower back's profile and peeks. Harness and outputs:
`tools/hairshell3/` (box-runnable), `charkit/out/hairshell3/`.

## (a) Reproducibility

`tools/hairshell3/determ.py CTX OUT.json [--perturb 1e-10]` (build_shells on a fit context, per lock the sha256 of its
shell; `--cmp A B`). The two box builds' contexts (hs_base, hs_shells_r) differ by 8e-11 m in R, Rn, S and the chart's
centre (views, masks, split identical). Round 2's fit on one context twice: identical; with its inputs moved 1e-10 m:
0 of 17 identical, 14 within 1e-9..1e-5 m, f10.2 2.7 mm (folds 0 vs 4), f20.1 2.2 cm, p13.1 0.26 mm. A tighter
least_squares (ftol/xtol/gtol 1e-15 polish) changes nothing: trf stops (xtol) wherever the trust region gives up on
a kinked objective probed by 1 mm secants, so the end is the path's, not the inputs'.

Fix (`lock_shells.det`, default on for shells): a smooth objective (drawn centrelines through cubic splines, the curve
sampled 4x, the fields and the envelope's depth by cubic splines, softplus limits, smooth abs, the widths' Gaussian on
squared distance), central-difference Jacobian (1e-6), converged (tol 1e-12); the fit's inputs snapped to 2^-12 m, its
parameters to 2^-12 m, the tube's arrays to 2^-26 m (`lockshell.det_inputs`: fields, chart centre, hull frame, L, the
views' calibration). trf on the smooth objective converged too slowly (some fits > 3000 evaluations, 13 min a
pilot); MINPACK's LM (`det_method 'lm'`, the twist through tanh) converges in 9-350 evaluations, and a fit's end
moves 2e-10..6e-8 m for inputs moved 1e-10 m (trf, round 2: 5e-7..2.5e-3). The 4 fits that stop at det_nfev 600
are trial joins the fit can't follow (costs 9-17 px against view_cost_max 4): dropped either way.
**Result** (`charkit/out/hairshell3/determ/det3.log`): 17 of 17 locks bit-identical between the context and it moved
1e-10 m (two seeds: the fields, the chart, the hull frame, the views), and between the two box builds' contexts
(CPU box hs_base, render box hs_shells_r; round 2: 0 of 17). A pilot fit takes 196 s (round 2: 57 s). The splitter's
product is identical laptop vs box (`split_box`: every image bit-identical; hairsplit.json differs only in width_L
of 4 locks, which the fit doesn't read). Test: `charkit/tests/test_lockshell.py::test_fit_bit_identical_under_input_noise`
(det on unsnapped inputs moved 1e-12: same bits, where round 2's fit moves 1e-12..1e-11, its calibration; inputs moved
1e-10 and snapped: same bits in 5 seeds). Laptop vs box on a real build: `tools/hairshell3/xmachine.py BUILD OUT`
(the build's pieces step made again here, compared bit for bit) on the candidate's box build.

## The reference attempt (3): failed (sub-agent; `charkit/out/hairshell3/ref/result.md`, `index.html`)

One call, n=2 (ledger 2026-10-01T03:58:50), an exploded lock breakdown with the body turnaround as the ref;
criteria pre-registered (`ref/criteria.md`). Take 1: scale spread 7.0% (FAIL), pilot locks matched 8/19 (FAIL),
identity 5/8 (FAIL); take 2: scale 1.4% (PASS), pilot locks 8/19 (FAIL: front 3/4, 3q 3/4, profile 1/4, back 1/7),
identity 14/14 (but the back numbered as a mirror of the front). Neither draws the turnaround's back hem or profile
flicks; line F and the 52-lock IoU at or below their random floors. Not registered. So the canonical rule's step 3:
the best joint fit with per-view costs (sweep rows `joint_all*`: view_cost_max 1000, every associated view kept).

## (b) The back view's terminator, step 3 and the lower back (sweeps sw1-sw3, base hs3_shells_r, numpy drawing)

`charkit/out/hairshell3/swN.json` -> `swN/` (sweep.md), six placements per row `term6.py SWEEP BASE` (term6.json),
attribution `term6mix.py BASE ROW OTHER NAMES` (a row with some pieces from another), truth `tools/hairshell/lockpics.py`
(lp1). Terminator: placement / six-placement mean (back view's mean).

| row | terminator | back mean | peeks place / mean | back_lines | hem | lock lines 3q / P | side locks F / P | lower back P | truth all / side | 2+ views |
|---|---|---|---|---|---|---|---|---|---|---|
| hull (spliced) | 2.196 / 2.057 | 1.70 | 17 / 17.5 | 0.894 W | 3 W | 0.176 / 0.105 | 0.560 / 0.469 | 0.665 | 0.356 / 0.394 | - |
| round 2 fit (det off) | 1.629 / 1.822 | 2.33 | 20 / 19.0 | 0.474 P | 2 | 0.228 / 0.159 | 0.584 / 0.606 | 0.588 | 0.397 / 0.558 | 2/17 |
| **det fit (control)** | 1.64 / 1.904 | 2.58 | 17 / 17.3 | 0.433 P | 2 | 0.223 / 0.119 | 0.608 / 0.579 | 0.579 | 0.400 / 0.563 | 2/17 |
| shade_at surface_over | 1.446 / 1.873 | 2.54 | 17 / 17.3 | 0.433 | 2 | = | = | = | | |
| shade_at surface (all shells) | 1.926 / 2.008 | 2.52 | 17 | | | | | | | |
| step 3: every associated view kept | 1.808 / 2.208 | 2.99 | 27 / 24.3 | 0.706 W | 3 W | 0.240 / 0.129 | 0.620 / 0.508 | 0.616 | 0.384 / 0.532 | 9/16 (costs 4-24 px) |
| over 0.002 / 0.0005 L | 1.447 / 1.867, 1.648 / 1.829 | 2.51, 2.46 | 17 / 17.5 | 0.444 | 2 | | 0.608 / 0.574 | 0.600 | | |
| over_ink 0.45 | 1.441 / 1.534 | **1.69** | 17 / 17.3 | 0.627 **W** | 2 | | = | = | | |
| widen_back 0.5 / 0 (side locks) | 1.666, 1.665 | 2.58 | 19 / 19.8, 26 / 26.0 | 0.437, 0.505 | 2 | 0.235 / 0.144, 0.243 / 0.183 | 0.613 / 0.597, 0.597 / 0.600 | 0.590, 0.594 | | |

Readings: (1) the det fit reads as round 2's fit (truth 0.400 against 0.397, side locks F +0.024, P -0.027). (2) The
back view's excess (2.58 against the hull's 1.70) is the flicks' (the hull's lower_back in its place: 2.23) and the
side shells' (the hull's side locks: 2.41); their normals aren't the cause (shading them from the mass's surface under
them changes nothing), nor their offset; inking 45% of each flick (the design's notch ticks, longer) takes the back to
the hull's 1.69 (overall mean 1.53) but back_lines 0.433 PASS -> 0.627 WARN (a flag check): sw3 tries 0.35 / 0.40 and
the flicks in one tone. sw3: over_ink 0.35 back 2.41 (back_lines 0.485 PASS), 0.40 back 2.15 (0.545 WARN); the
flicks in one tone (over_tone 'root', new) worse, back 2.96; widen_back 0.75 peeks 20 / 18.8, lower back P +0.006.
sw4 (single placement only; stopped at the wrap-up): thin flicks (a group's own depth_ratio, `groups[].opts`, new)
worse: 0.15 back 2.94, 0.08 back 3.30 (control 2.22), terminator 2.17-2.43 WARN. So the flicks' terminator step is
neither their normals, their offset nor their thickness; inking them longer hides it at back_lines' cost. Overlays:
`charkit/out/hairshell3/back_term_hull_det.png` (kinks where the terminator crosses the left flick group's edges and
where the group starts at her left side, and the side shells' silhouette there). (3) Step 3 (the best joint fit, every associated view kept): 9 of 16 locks in 2+ views at
per-view costs up to 24 px, and it loses: peeks 17 -> 27, side locks' profile 0.579 -> 0.508, truth 0.400 -> 0.384,
back lines WARN, hem WARN. The sequential join (a view kept when the fit follows it within 4 px) stays the base
model's best fit; per-view costs are in the pieces report. (4) The lower back's profile (-13%) is the side shells'
cover; asymmetric widening (widen_back, new) buys +0.011..0.015 at peeks +2..+9; over 0.0005 L +0.021 free.

## hair_noise remeasure (side branch tool/hairshell3-noise, aa7b3e6)

`qa3d.hair_noise` draws the hair with its outlines as the render does; a pixel within 1 px of ink is the line's (the
film filter darkens the hair beside its lines: luminance 0.498 at 1 px against 0.515 at 1.5-3 px). New readings
(`charkit/out/hairshell3/noise3.py`, pictures `noisepic.py`): hull hs_hull_r 0.0717 W -> 0.0342 P (front 0.122 ->
0.035); round 2 shells hs3 0.0784 W -> 0.0303 P; round 1 hs_shells_r 0.098 F -> 0.036 P; hl_base 0.0785 -> 0.0424;
hair5_1580f95 0.079 -> 0.0397; look_v5 0.066 -> 0.020. Known-bad: pipeline-3d's confirm build ck6_body (the hull-era
hair of T003 "blotchy: light speckles on the back and sides") 0.221 (its era) -> 0.104 FAIL (0.0365/0.055/0.047
without outlines under today's code: its speckles show only in the outline-correct drawing, where the pulled-in
surface shows the hull's folds). Floor (speckle blots 6%): 0.25-0.29 FAIL.
**The design leg fails**: the body sheet's hair (`charkit/calib/hairnoise.py`: its cel tones, paletteqa's lit and
shade, the lines as ink, at the QA's 82.3 px/L) reads 0.216 FAIL (front 0.27, profile 0.25, back 0.13); median-
filtered tones 0.16-0.21. The design draws a shadow shape per lock: its tone-edge density is 5-7x any render's, so
hair_noise (absolute tone-edge density; PASS < 0.04) rewards flat shading and would call the design's lock shadows
noise. A speckle prototype (`speckle_proto.py`: the hair's share in tone islands under 12 px) doesn't separate either
(design 0.020, ck6 0.030, hull 0.010, floor 0.040). So the triple can't come out calibrated without redefining what
hair_noise measures: kept off this branch (the gate blocks a remeasured check without a calibrated record);
a decision for Michael.

## Where round 3 stopped (2026-10-01, the coordinator's wrap-up) and exact next steps

Committed: the det fit (default for shells), its test, det_inputs; options shade_at 'surface'/'surface_over',
over_tone 'root', widen_back, groups[].opts (all opt-in, off by default); harness tools/hairshell3/ (determ.py,
xmachine.py, refcheck_exploded.py, numpics.py); the hair_noise remeasure on the side branch tool/hairshell3-noise
(aa7b3e6, not merged: its design leg fails). No box jobs running (the box splitter job hairsplit-hairshell-1001-045050
finished; nothing else sent). No real build of a round-3 candidate, no pregate, no gate.

**The pilot so far** (numpy-drawing sweep rows on hs3_shells_r's bundle; round 2's real builds for reference):
the det fit reads as round 2's (truth 0.400 / side locks 0.563 against 0.397 / 0.558; terminator 1.64 PASS, six-
placement mean 1.904 against the spliced hull's 2.057; peeks 17 / 17.3 against 17 / 17.5; back_lines 0.433 PASS against
0.894 W; hem 2 PASS against 3 W; lock lines 3q 0.223 / profile 0.119 against 0.176 / 0.105; folds 9 = 9). Still losing:
the back view's six-placement terminator 2.58 against 1.70, the lower back's profile 0.579 against 0.665 (-13%),
hair_noise 0.0782 against 0.0716 under the current measure (0.030 against 0.034 under the remeasure).

**Next steps, in order** (each: sweep rows on hs3_shells_r, six placements with term6.py, then a real build):
1. The back view's terminator: attribute it per flick (term6mix with one flick at a time from the hull row: which
   of b13/b23/b36/b38 carries it), and try the group's phi range trimmed (phi [110, 175]: the group's start at her
   left side is a kink) and over_ink 0.35 (back 2.41, back_lines 0.485 PASS) as the candidate if nothing better.
2. The candidate spec `tools/hairshell3/clawd_shells3.json` (tools/hairshell/clawd_shells.json with the chosen
   options; det is the default), a render-box build (`python -m charkit remote --box render build SPEC --boards
   views,body,design --out charkit/out/hs4_shells_r`, about 13 min), then on the laptop `python
   tools/hairshell3/xmachine.py charkit/out/hs4_shells_r charkit/out/hairshell3/xm` (laptop vs box, bit for bit:
   the round's acceptance for (a) on a real build), lockpics against hs_hull_r, term6 on the build's own bundle.
3. Review page (`python -m charkit review page charkit/out/hairshell3/review.json --open`, round 2's review.json as
   the template): summary box asking Michael (A) the default switch for the pilot region yes/no, (B) extend to the
   whole head yes/no, (C) hair_noise: redefine (a speckle measure) or keep as is; the reference result
   (`charkit/out/hairshell3/ref/index.html`) and step 3's rows as figures.
4. `python -m charkit pregate`, then `python -m charkit remote gate tool/hairshell3 --into pipeline-3d` (opt-in:
   nothing should move on the default spec; the det fit changes only lockshell and the new options default off).
5. **The default switch** (only on Michael's yes): set `hair.shape.pieces_opts.lock_shells` (the candidate's) in
   charkit/spec/clawd.json; it moves the default's geometry, so the gate scores it as a geometry change: expect the
   flag checks art_terminator_hair (back view), hair_back_lines, hair_back_hem and the lower back's profile IoU to
   move; the build's CPU rises ~2 min (the det fit: 196 s against 57 s for the pilot; check the 1.5x limit).
6. **The whole head** (only if the pilot wins on every count), region by region on real builds, each against the
   hull with the guard per view: bangs (families ['bangs', 'side_locks'], primary front then profile; the hull's
   bangs score 0.769 IoU: guard every view), upper back (primary back, phi 100-260, replace false first), the whole
   hem (both sides, phi 90-270, a hooked-flick template: a curl angle at the tip, unit 'cells'), ahoge and flyaways
   re-rooted on the shells. Identity across views stays the open problem: three generated references have failed;
   step 3 (keep every associated view) loses on peeks, terminator and the truth; a hand-made correspondence
   (the truth's cross-view names for the side locks) would be the next reference, but it is the scoring truth, so it
   needs its own held-out check before it is used for fitting.
7. hair_noise (Michael's call): the remeasure (outlines drawn as the render draws them) is right for ours (the flagged
   blotchy build ck6_body 0.104 FAIL, the round-1 shells' false FAIL gone), but the design leg can't pass: the
   design's own cel tones read 0.216 (its lock-shaped shadows; hair_noise rewards flat shading). Options: (A) a speckle
   measure (tone islands under a size; the prototype doesn't separate yet: design 0.020, ck6 0.030), (B) keep the old
   measure and its WARN, (C) the remeasure with a 'defect' record calibrated on the known-bad and the floor only
   (needs the gate to accept a defect detector without a design leg).


# Round 4 (tool/hairshell3, option B continued; coordinator's brief 2026-10-01)

Merged pipeline-3d 00494de and tool/hairshell3-noise aa7b3e6 (-> c8caefa; tools/ledger.jsonl: both sides kept).
Decisions (coordinator; Michael may overrule): (1) hair_noise a speckle measure, calibrated, the old one INFO for a
release; (2) the back view's terminator on real builds, six-placement averages (if it's a normals problem: report, the
normals are tool/hairstrokes' (d)); (3) the lower back's profile cost; (4) the default switch for the pilot once the
shells beat the hull on every count (Michael's yes/no on the page); (5) then region by region: back and hem, bangs,
ahoge. The exploded references failed: the canonical rule's step 3 (best joint fit, per-view costs).
Harness: tools/hairshell3/ (mkspec.py: a candidate spec = today's clawd.json + overrides; kinkattr.py: each terminator
kink's pieces/components; compview.py; famconf.py: a family's per-view confusion; flickoff.py; piecemix.py; radialnormals.py;
term6p.py: six placements for pieces dirs). Outputs charkit/out/hairshell3/{speck,kink,radn,mix,kb}.

## Real builds (render box, boards views,body,design, merged head)
- `charkit/out/r4_hull` (charkit/spec/clawd.json at 84bcb29): art_terminator_hair 2.002 W (back 1.564), peeks 17,
  back_lines 0.894 W, hem 3 W, folds 9, lower back F/P/B 0.514/0.665/0.672, side locks F/P 0.560/0.469 (= hs_hull_r).
- `charkit/out/r4_pilot` (tools/hairshell3/r4_pilot.json = clawd.json + lock_shells pilot.json; round 3's defaults).
  Both QA'd before the hair_noise change (their hair_noise is aa7b3e6's).

## (1) hair_noise: a speckle measure -- done, CALIBRATED (34b8ad1, record ebd02ee)
qa3d.speckles: per tone group, the luminance's blobs under 0.002 L^2 (area opening for light ones, closing for dark;
artifactqa.ISLAND) standing out by half the hair's cel step (hair_cel_step: the design palette's lit - shade, 0.144),
ink and background filled from the nearest hair pixel, none within 2 px of the silhouette; per L^2 of hair, the three
views' mean; limits 8 / 12. Lab (`charkit/out/hairshell3/speck/lab.py`, cached pictures): blobs at 0.001/0.002/0.003
L^2; the two-tone design stand-in dropped the design's drawn shine marks (the crown's pale strokes), so the adapter
keeps them as a third tone (SHINE_DL 0.06 over lit, tool/hairstrokes' definition). Known-bad: **ck7_blotchy**, the
build T003 was raised on (pipeline-3d confirm ck7_final, copied: 35.8 FAIL here, back 46; the old measure read it 0.046
WARN, i.e. missed the flag); ck6_body (round 3's stand-in) 28.2. Calibration on r4_hull: design 3.88-5.93 PASS every
move, ck7_blotchy 32.6 FAIL, floor speckle 14.8 FAIL, current 4.46 PASS (margin 1.07), probe voronoi_tones 0 PASS (a
speckle detector is blind to tone shapes: the pieces' shape checks guard them). Readings: hs_hull_r 4.46, hs3 (round 2
shells) 4.55: the shells add no speckle. Old measure as INFO `hair_tone_edges` (0.0717 / 0.0784, unchanged).
qa3d_blender's pass reports its tone edges as hair_tone_edges INFO. Ink strokes (tool/hairstrokes) are read as lines
by render_surfaces already (hull=True): compatible. **Conflict to coordinate:** tool/hairstrokes registered its own
hair_noise step (ae33ac8, without_ink) and needs a record for it; whichever merges second recalibrates.

## (2) The back view's terminator: diagnosis (on hs3_shells_r, round 2's real build)
- kinkattr (six placements, components = each surface's connected triangle sets): back kinks hull 7.2 / shells 9.2;
  the excess is hair_lower_back's (4.9 against 2.75), 72-78% of kinks at a junction between components in both.
  compview: the terminator steps at the edges of flick lower_back#7 (and #8-#10): the flick stays lit ~0.04 L lower
  than the mass beside it.
- flickoff (each flick pixel against the same pixel with the flicks removed): the flick is lit where the mass is
  shaded on 17-68% of its pixels; the mass behind a flick pixel lies 0.07-0.13 L deeper along the back view's ray
  (the hem curling under toward the nape); the flicks' vertices sit 0.009 L off the mass at the root, 0.025-0.029 L
  at the tip: they hang straight while the mass curls under.
- Normals transplanted (radialnormals.py: each vertex the hull's outer surface normal along the ray from the head's
  centre; six placements): flicks back 2.52 -> 2.79 (worse), the whole lower back 2.57, the side shells too: front 6.08
  -> 9.87; the hull's own lower back 1.87 -> 1.61. **Reading: not a normals problem the envelope normals fix; it is
  geometry (the flicks leave the curling mass).** Next: the flick group's depth pull/smoothness (sweep), not the
  hairstrokes normals.

## (3) The lower back's profile: diagnosis
famconf (hair_pieces' grids): profile lower back hull 0.665 / hs3 0.588. Ours grew (5603 -> 8093 px) and 23% of it lies
where the drawing has upper back (hull 5%). Swaps (piecemix): without the flick shells 0.624 (+0.036), with the hull's
side locks 0.606 (+0.018). In profile flicks 9 and 10 show as long blades, 58% / 64% over the drawn upper back (they
are fitted in the back view only; containment holds only the centreline). The side shells, narrower than the hull's
side lock in profile (side locks P 0.469 -> 0.604), uncover the lower back's top.

## (2b) tool/hairstrokes' ellipsoid normals tested (coordinator's request; scratch worktree)
Scratch branch `scratch/hairshell3-ell` (worktree `~/animation-pipeline-hairshell-ell`, not for merge): tool/hairstrokes'
769465a4 (hairpieces.shade_normals' shade_ellipsoid / shade_squash: the mass's normals, and the shells' proxy normals,
blended toward an ellipsoid round the hair's mass) cherry-picked onto tool/hairshell3 08bf224, turned on through style
profiles anime_ell50 / anime_ell100 (the anime profile with the blend; the build reads hair_pieces style by name).
Real builds on the build box (boards views), six placements each (tools/hairshell3/term6p.py on the box):

| build | art_terminator_hair place / mean +- std | per view mean F / 3q / P / B |
|---|---|---|
| hull (r4_hull) | 2.002 / 2.006 +- 0.081 | 7.51 / 8.12 / 3.81 / **1.87** |
| hull + ellipsoid 1.0 (ell_hull100) | 2.100 / 2.119 +- 0.168 | 7.51 / 9.11 / 5.70 / 1.77 |
| pilot shells (r4_pilot) | 1.844 / 1.990 +- 0.199 | 5.45 / 4.09 / 1.60 / **2.67** |
| pilot + ellipsoid 0.5 (ell_pilot50) | 1.686 / 1.687 +- 0.210 | 5.07 / 3.12 / 3.16 / 2.24 |
| pilot + ellipsoid 1.0 (ell_pilot100) | 1.533 / 1.593 +- 0.119 | 4.37 / 3.20 / 5.12 / 2.13 |

Reading: the ellipsoid blend narrows the back view's gap (2.67 -> 2.13 at 1.0) but doesn't close it (the hull 1.87;
the hull with the blend 1.77); it costs the profile view (1.6 -> 5.1; the check takes the worst view's ratio, so the
overall still improves). The remaining gap is the flicks' geometry (they hang off the curling hem: (2) above). The
other checks don't move with the blend (peeks 17, back lines 0.433, hem 2, folds 9, the pieces' IoU: normals only).

## (2c) The flicks' geometry (sweep r4sw2 on r4b_pilot, the build box's pilot build: its QA = r4_pilot's exactly)
`tools/hairshell3/r4sw2.json` -> `charkit/out/hairshell3/r4sw2/` (sweep.md; `tools/hairshell3/swkeys.py` the key
columns; term6.json the six placements, `tools/hairshell3/term6.py SWEEP BASE` on the box). The flick group's opts:

| row | terminator place / mean (back mean) | peeks | back_lines | hem | lower back F / P / B | upper back P | side locks P |
|---|---|---|---|---|---|---|---|
| control (the pilot) | 1.844 / 1.989 (2.67) | 17 | 0.433 P | 2 | 0.512 / 0.579 / 0.713 | 0.628 | 0.574 |
| contain 5 | 2.017 / 2.167 (2.90) | 18 | 0.484 P | 3 | 0.509 / **0.642** / 0.713 | 0.668 | 0.576 |
| min_px 600 | = control (no target that small) | | | | | | |
| root_in 0 | 2.041 / 2.088 (2.80) | 19 | 0.451 P | 2 | 0.512 / 0.560 / 0.722 | 0.628 | 0.572 |
| prior_depth 10 | 1.661 / 1.760 (2.34) | 19 | 0.613 W | 3 | 0.500 / 0.604 / 0.707 | 0.650 | 0.563 |
| prior_depth 3, smooth 0.1 | 1.641 / 1.828 (2.36) | 17 | 0.569 W | 2 | 0.506 / 0.582 / 0.710 | 0.633 | 0.559 |
| pd 3 + contain 5 + min_px 600 | 1.826 / 2.219 (3.01) | 18 | 0.490 P | 4 | 0.505 / 0.644 / 0.710 | 0.671 | 0.579 |

Reading: pulling the flicks onto the curling mass (prior_depth) lowers the back view's terminator 2.67 -> 2.34 but raises
back_lines to WARN (the flicks' inked tips now lie inside the mass); holding them in the lower back's drawn region in
every view (contain 5) mends the lower back's profile (0.579 -> 0.642, the hull 0.665) but steps the back terminator
(2.90). Neither closes the back view alone (hull 1.87).

## (2d) Flick geometry with and without tool/hairstrokes' ellipsoid normals (six-placement back-view means)
r4sw1 (render box, single placements only: rows not on the build box), r4sw3 (build box, r4b_pilot; term6 on the box),
ell_sw1 (scratch branch, base ell_pilot100 = the pilot with shade_ellipsoid 1.0). Group opts on the pilot's flicks:

| row | no ellipsoid: term mean (back) | back_lines | ellipsoid 1.0: term mean (back) | back_lines | lower back P | hem |
|---|---|---|---|---|---|---|
| control | 1.989 (2.67) | 0.433 P | 1.593 (2.13) | 0.433 P | 0.579 | 2 |
| prior_depth 1 | 1.968 (2.55) | 0.475 P | | | 0.599 | 2 |
| view_depth 3 | 1.761 (2.24) | 0.493 P | | | 0.595 | 3 |
| pd 3 + vd 3 | 1.694 (2.15) | 0.504 W | | | 0.595 | 3 |
| pd 3 + vd 3 + over_ink 0.2 | 1.880 (2.49) | 0.410 P | | | 0.595 | 3 |
| pd 3 + vd 3 + contain 2 | 2.064 (2.77) | 0.548 W | | | 0.590 | 3 |
| prior_depth 10 | 1.760 (2.34) | 0.613 W | 1.594 (2.13) | 0.613 W | 0.604 | 3 |
| contain 5 | 2.167 (2.90) | 0.484 P | 1.540 (2.06) | 0.484 P | 0.642 | 3 |
| pd 3 + smooth 0.1 | 1.828 (2.36) | 0.569 W | 1.575 (2.11) | 0.569 W | 0.582 | 2 |
| pd 3 + smooth 0.1 + contain 5 | | | 1.471 (1.96) | 0.537 W | 0.635 | 4 |
| **pd 10 + contain 5** | | | **1.369 (1.78)** | 0.531 W | **0.639** | 3 |
| hull (r4_hull; hull + ellipsoid) | 2.006 (1.87) | 0.894 W | 2.119 (1.77) | 0.894 W | 0.665 | 3 |

**Answer to the coordinator's question:** tool/hairstrokes' ellipsoid normals alone take the pilot's back view 2.67 ->
2.13; the flick geometry alone (pulled onto the curling hem) 2.67 -> 2.15; together (ellipsoid 1.0, flicks prior_depth
10 + contain 5) 1.78, under the hull's 1.87 (the hull with the ellipsoid 1.77: a tie), with the lower back's profile
0.639 (hull 0.665, -3.9%), back_lines 0.531 W (hull 0.894 W), hem 3 (= hull), peeks 18 / 17.7 (hull 17 / 17.5). So the
merge order strokes first, then the shells with their flicks pulled onto the hem, closes the back view; neither alone.

## (5) Regions: the whole hem and the bangs (sweeps on r4b_pilot; six placements)
**Whole hem, both sides** (r4sw4: groups hem_L phi [90, 180], hem_R [-180, -90], laid over; no ellipsoid):

| row | term mean (back) | peeks | back_lines | hem (ours/drawn 8) | lower back F / P / B | upper back P |
|---|---|---|---|---|---|---|
| pilot pd10 + c5 | 1.782 (2.31) | 18 / 17.7 | 0.531 W | 3 | 0.502 / 0.639 / 0.706 | 0.672 |
| hem2 (defaults) | 2.061 (2.79) | 24 / 25.2 | -0.129 P | 3 | 0.511 / 0.597 / 0.748 | 0.627 |
| hem2 pd10 + c5 | 1.908 (2.56) | 19 / 18.7 | 0.217 P | 4 | 0.500 / 0.655 / 0.733 | 0.674 |
| hem2 pd3 + vd3 + c5 | 1.854 (2.48) | 19 / 19.3 | 0.010 P | **5 F** | 0.502 / 0.663 / 0.736 | 0.674 |
| hem2 pd10 + c5 + ink 0.2 | 2.089 (2.83) | 19 / 18.7 | 0.012 P | 4 | = | = |

The whole hem takes the back's stripes off (back_lines 0.894 -> 0.01-0.22) and the lower back's back-view IoU up
(0.672 -> 0.73-0.75), the profile to the hull's (0.663), but pulled onto the curling mass the flicks' tips no longer
hang below it: the hem's tips 5 (hull) -> 3 of the drawing's 8 (hair_back_hem 5 FAIL). Hence `hug_free` (lockshell,
opt-in): the depth pulls fade out over the last share of the lock, the tip free (sweep r4sw6 / ell_sw3).

**Bangs** (r4sw5: families + bangs; all rows with the pilot's flicks pd10 + c5):

| row | term mean (front) | peeks | bangs F / P | fringe_low | lock lines 3q / P |
|---|---|---|---|---|---|
| control | 1.782 (5.37) | 17.7 | 0.847 / 0.636 | P | 0.245 / 0.123 |
| bangs as shells (replace) | 1.795 (5.80) | 20.0 | **0.548 / 0.298** (guard) | F | 0.232 / 0.128 |
| + primary front, profile | 1.796 (5.82) | 21.0 | 0.561 / 0.591 | F | 0.233 / 0.110 |
| + widen 4 | 1.717 (4.96) | 20.0 | 0.665 / 0.336 (guard) | F | 0.245 / 0.125 |
| + front, profile, widen 4 | 1.719 (4.92) | 20.0 | 0.658 / 0.599 | F | 0.240 / 0.115 |
| **over the bangs' wedges (under: [bangs])** | **1.706 (4.72)** | 17.7 | **0.854 / 0.640** | P | **0.256 / 0.138** |

Reading: the bangs as shells in place of the hull's bangs lose their coverage (the hull's bangs piece is the best
family, 0.85 front); laid over their own wedges they keep it and add the locks' structure (front terminator 5.37 ->
4.72, lock lines up), so the bangs region is `under: ["bangs"]`.
Infra note: since ~11:00 the laptop's python3 (python.org 3.11) fails TLS verification on the bucket pulls
(bucketsync); `CHARKIT_PY=~/animation-pipeline/.venv/bin/python` works (used from here).

## (2e) Free tips (hug_free) and the candidates
r4sw6 (no ellipsoid) / ell_sw3 (ellipsoid 1.0), six placements, mean (back):

| row | no ellipsoid | ellipsoid 1.0 | peeks | back_lines | hem | lower back P / B |
|---|---|---|---|---|---|---|
| pilot pd10 + c5 + hug_free 0.3 | 1.608 (1.98) | **1.361 (1.76)** | 17 / 17.5 | 0.543 W | **2 P** | 0.610 / 0.720 |
| hem2 pd3 + vd3 + c5 + hf 0.3 | **1.513 (1.93)** | 1.793 (2.43) | 21 / 20.3 | **0.135 P** | 3 | 0.627 / 0.751 |
| hem2 pd3 + vd3 + c5 + hf 0.5 | 1.609 (1.97) | 1.658 (2.25) | 19 / 19.5 | 0.145 P | 3 | 0.644 / 0.753 |
| hem2 pd10 + c5 + hf 0.3 | 1.679 (2.20) | 1.881 (2.55) | 17 / 18.5 | 0.108 P | 3 | 0.626 / 0.751 |
| hem2 pd10 + c5 + hf 0.5 | 1.806 (2.35) | 1.817 (2.46) | 20 / 20.2 | 0.107 P | 3 | 0.634 / 0.755 |

Free tips keep the hem's tips (hem 5 F -> 2-3) at no terminator cost. The pilot's flicks want the ellipsoid (back 1.76
< the hull's 1.87); the whole hem does better without it (1.93 against 2.25-2.55 with it).

**Merged pipeline-3d 9be5b320** (the hair strokes milestone f28affa with the ellipsoid normals, off by default; the
clips; face7 gate 1) -> 8e39808 (clean). The coordinator: finish r4 at the bangs/hem results; the next hair round is
cross-view lock identity; the whole head waits for it.

**Candidates (merged head, specs from mkspec):** C1 the pilot = `tools/hairshell3/c1_pilot.json` (side locks; the left
hem's flicks phi [100, 175] laid over, opts prior_depth 10, contain 5, hug_free 0.3); C2 extended =
`tools/hairshell3/c2_ext.json` (side locks; the bangs laid over their wedges; the whole hem, hem_L [90, 180] and hem_R
[-180, -90], opts prior_depth 3, view_depth 3, contain 5, hug_free 0.3). Ellipsoid: `hair.shape.style`
{shade_ellipsoid: 1.0} (`tools/hairshell3/ell100.json`). Real builds (`tools/hairshell3/r5_launch.sh NAME SPEC BOX
BOARDS`: the build, then its six placements on the same box, logs in charkit/out/hairshell3/r5/): r5_hull (render2,
boards), r5_c1e (render2, boards), r5_c2 (render2, boards), r5_c2e (render2, boards), r5_c1 (build box), r5_hull_e
(build box).

## Gate (round 4)
Pregate: not run (the box copy has no git refs: `remote run pregate` stops at `git rev-parse pipeline-3d`; the laptop
is out of memory, the coordinator's rule; the diff reaches none of the evaluator's checks). Gate 1 (c2977768 into
9be5b320): FAIL under K, one blocker: test_tune.py asserted hair_noise's severities on the old scale (0.12 -> 2.0);
moved to the new scale (16 -> 2.0, the same severities) and test_hairnoise.py added (qa3d.speckles). **Gate 2: PASS
under K** (2c1966ef into pipeline-3d 9be5b320, `charkit/out/gate/gate_tool-hairshell3_2c1966ef_into_9be5b320.md`):
nothing blocks; hair_noise remeasured 0.0756 W -> 4.4 P (record CALIBRATED), hair_tone_edges new INFO (0.0756);
measuring code changed with no step reported for parts that read qa3d.LIMITS / lockshell / shade_normals (nothing
moved: the geometry is the same); 95 test files pass; build CPU 1432.7 -> 1198.2 s (0.84x).


## Round 4 result: real builds on the merged head (pipeline-3d 9be5b320, the strokes in)
Builds: r5_hull, r5_c1e, r5_c2, r5_c2e (render2, boards views,body,design), r5_c1, r5_hull_e (build box). Six placements
`charkit/out/hairshell3/r5/t6_*.log`; the 52-lock truth `charkit/out/hairshell3/r5/locks_*.log` (hairlocks score; the
all-locks figure is the lock-weighted mean of the family lines); overlays `charkit/out/hairshell3/r5/pics/`.

| count | hull | hull + ell | C1 pilot | **C1e pilot + ell** | C2 hem + bangs | C2e + ell |
|---|---|---|---|---|---|---|
| art_terminator_hair placement | 2.370 W | 2.151 W | 1.646 P | **1.303 P** | 1.460 P | 1.894 P |
| six placements mean (back) | 2.173 (1.87) | 2.172 (1.77) | 1.740 (2.02) | **1.417 (1.77)** | 1.521 (1.93) | 1.937 (2.62) |
| art_peeks_hair place / mean | 17 / 17.3 | 17 / 17.3 | 18 / 18.2 | 18 / 18.2 | 24 / 22.5 | 24 / 22.5 |
| hair_back_lines | 0.928 W | 0.928 W | 0.584 W | 0.584 W | 0.285 P | 0.285 P |
| hair_back_hem | 3 W | 3 W | 2 P | 2 P | 3 W | 3 W |
| lock lines 3q / P | 0.290 / 0.172 | 0.285 / 0.188 | 0.314 / 0.189 | 0.312 / 0.205 | 0.326 / 0.201 | 0.320 / 0.238 |
| truth all / side / lower / bangs | 0.352 / 0.379 / 0.304 / 0.431 | = hull | 0.405 / 0.580 / 0.344 / 0.431 | = C1 | 0.409 / 0.580 / 0.414 / 0.367 | = C2 |
| side locks F / P | 0.529 / 0.474 | = | 0.598 / 0.573 | = | 0.600 / 0.568 | = |
| lower back F / P / B | 0.514 / 0.664 / 0.672 | = | 0.508 / 0.610 / 0.720 | = | 0.508 / 0.627 / 0.750 | = |
| upper back P / B | 0.621 / 0.889 | = | 0.659 / 0.898 | = | 0.662 / 0.895 | = |
| bangs F / P | 0.834 / 0.630 | = | 0.824 / 0.633 | = | 0.831 / 0.637 | = |
| hair_noise (speckle) / folds | 4.40 / 9 | 4.82 / 9 | 4.39 / 9 | 4.40 / 9 | 4.84 / 9 | 4.84 / 9 |

**Decision 4 (the default switch):** the pilot with the ellipsoid (C1e) wins every count but two: peeks 17 -> 18 (WARN
both; the mean 17.3 -> 18.2) and the lower back's profile 0.664 -> 0.610 (-8%, inside the guard). Not "every count", so
the page asks A (switch now, accepting those) / B (wait), recommended B. **Decision 5:** the whole hem takes the back's
stripes off (0.928 W -> 0.285 P) and lifts the lower back's truth (0.304 -> 0.414) but opens gaps (peeks 24) and the
bangs laid over their wedges cut them off-truth (0.431 -> 0.367); the hem prefers no ellipsoid (back 1.93 vs 2.62).
Looked at on the boards: every build still reads as a rounded bob at the back's hem against the design's lobed,
flicked hem (tips ours 5-6, the drawing's 8): the flicks now lie on the mass.

**Review page:** `charkit/out/hairshell3/review/index.html` (`python -m charkit review page
charkit/out/hairshell3/review.json --out charkit/out/hairshell3/review --open`; figures under
charkit/out/hairshell3/review_src, kink/, speck/). Asked of Michael: (1) default switch A/B (rec. B); (2) keep hair_noise
as the speckle measure (rec. yes); (3) continue the whole hem after the identity round (rec. yes).

## Next steps (for the round after the cross-view identity round)
1. Peeks (17 -> 18 on the pilot; 24 on the whole hem): `tools/hairshell2/peekmap.py`-style attribution per object on
   r5_c1e / r5_c2 (charkit/out/hairshell2/peekmap.py BUILD PNG, run on the box via `charkit script`), then widen the
   flick groups toward their neighbours (widen_lw lower_back 2 -> 3-4) or an under-mass for the hem groups.
2. The lower back's profile (0.610): containment on the left flicks already in (contain 5); the rest is the side shells
   uncovering the lower back's top in profile (famconf: +0.018 with the hull's side locks) and the flicks' free tips;
   try widen_back > 1 on the side shells (their back edge) and contain 8 on the flicks; famconf.py on the row.
3. The hem's silhouette (Michael's tips priority): a hooked-flick template (a curl at the tip: the centreline turning
   out and up over its last share, fitted to the back's lobes and the profile's J hooks), unit 'cells' for the hem's
   lobes; hem tips toward the drawing's 8.
4. Bangs: as shells over their wedges they cut the bangs off-truth (0.431 -> 0.367): needs the identity round (their
   locks joined across front and profile) before more.
5. The ellipsoid: on for the pilot's flicks (back 2.13 -> 1.77), off for the whole hem (1.93 -> 2.62): per-family
   shade_ellipsoid would need hairpieces.shade_normals to blend per piece (tool/hairstrokes' code; coordinate).

## Jobs
None running. The scratch worktree `~/animation-pipeline-hairshell-ell` (branch scratch/hairshell3-ell, not for merge:
the ellipsoid cherry-pick and style profiles, superseded by pipeline-3d's merge of the strokes; its builds ell_* and
sweeps charkit/out/ell/ hold (2b)-(2d)'s numbers) can be removed once this round's numbers are read.


## The default switch (Michael's answers, 2026-10-01, via the coordinator)
(1) Switch the pilot default now: yes. (2) Keep the speckle hair_noise: yes. (3) The whole hem waits for the identity
round. Merged pipeline-3d d44db780 (face7 gate 2b, tool/optimize, a bow test fix) -> 27d42f6. 520a317:
charkit/spec/clawd.json and the alias clawd_body_pieces.json set hair.shape.pieces_opts.lock_shells =
tools/hairshell3/c1_pilot.json and hair.shape.style {shade_ellipsoid: 1.0} (the default now equals r5_c1e's spec but
for brows / mouth from face7). Expected moves on the gate (r5_hull -> r5_c1e): art_terminator_hair 2.370 W -> 1.303 P,
hair_back_lines 0.928 W -> 0.584 W, hair_back_hem 3 W -> 2 P, art_peeks_hair 17 W -> 18 W, the lower back's profile
IoU 0.664 -> 0.610 (-8%), side locks up, the lock lines up; build CPU up by the lock fit (~2-3 min). Pregate
`python -m charkit pregate --box auto`, then `python -m charkit remote --box render2 gate tool/hairshell3 --into
pipeline-3d`.

### The switch gate (63e20dce into pipeline-3d 60c0f1a4): FAIL under K, 3 blockers
`charkit/out/gate/gate_tool-hairshell3_63e20dce_into_60c0f1a4.md` (render2). Pregate (build box) PASS, 24 moved, 0
blocking (body_profile_iou_skin 0.727 P -> 0.692 W; sheet_shown_front 0.465 -> 0.524, profile 0.34 -> 0.29). Blockers:
1. **hair_penetration 0.0 P -> 0.0398 F**: side_lock_L's shell f20.1 (joined front + three-quarter, 0.29 L wide,
   twist -46 deg at its bound): stations 9-41 of 55 cut 0.040 L into the head at the temple (72 vertices; x 0.32 L,
   0.04 L over the eye line). The fit keeps the centreline gap off the skin, not a wide twisted tube's edge. It was in
   every shells build since round 2 (my sweep tables left it out). Fix: `skin_clear` (lockshell, on): every shell
   vertex held gap outside the crown chart's skin field (a smooth max over 0.002 L), as the hull's pieces are.
2. **hair_noise's 2x2**: the old tone-edge measure on the new geometry 0.0748 W -> 0.0808 F; the speckle measure 4.81
   -> 4.4 P. Michael's named acceptance (the coordinator): `charkit/accepted/hair_noise.json` ("superseded by the speckle
   remeasure..."), and the gate runs with `--accept hair_noise`.
3. **Build CPU 1.67x** (1190.5 -> 1989.8 s): pieces_hair 100 -> 900 s, all the lock fit. Profile
   (`tools/hairshell3/profile_fit.py` on the build box, charkit/out/hairshell3/prof/): 893 s CPU over 34 fits; the trial
   joins the fit can't follow (dropped anyway) ran to det_nfev 600 (six of them ~630 s, two more ~100 s); every
   accepted join converged within 40 evaluations. Fix: `det_join_nfev` 150 (a trial's evaluations; an accepted one the
   cap stopped is fitted again in full, so kept joins end where they did). Hot functions for later: frames() 188 s own,
   _seg_dist 68 s, norm 66 s.
Also reported: scalp_px 4 P -> 65 W (the scalp between the side shells), art_peeks_hair 17 -> 18 W, the flag values
(back lines 0.928 -> 0.584, lock lines up). Checks: `tools/hairshell3/capcheck.py` (cap bit-identity, skin_clear's moves),
real build r6_default (render2) with six placements.
Fix results: capcheck (build box, r5_c1's context; `charkit/out/hairshell3/capcheck/`): the trial-join cap leaves 17 of
17 shells bit-identical, the fit's CPU 1009 -> 558 s. skin_clear per vertex (r6_default) cleared the penetration but
folds 9 -> 16, so each station's ring is pushed out by its deepest vertex's need instead (598eb4e). Real build
**r6b_default** (render2, the default at 598eb4e): hair_penetration 0.0 P, folds 9, art_terminator_hair 1.310 P (six
1.432 +- 0.164, back 1.77), peeks 19 / 19.0 (r5_c1e 18 / 18.2; this head has face7 gate 2b and hands2), back lines
0.584 W, hem 2 P, hair_noise 4.37 P, scalp_px 65 W (hull 4), side locks F/P 0.601 / 0.557, lower back 0.511 / 0.610 /
0.720, pieces_hair 905 -> 481 s, build CPU 1897 -> 1342.5 s (render2). Re-gate: `python -m charkit remote --box render2
gate tool/hairshell3 --into pipeline-3d --accept hair_noise`.

### Re-gate (140e8dbe into 60c0f1a4, `--accept hair_noise`): FAIL under K, 1 blocker
`charkit/out/gate/gate_tool-hairshell3_140e8dbe_into_60c0f1a4.md`: penetration, the 2x2 and the CPU cleared; the one
blocker: **hair_strokes_profile_dir 14.6 P -> 22.8 W** (the strokes milestone's flag check: our profile strokes'
median angle to the drawn flow). Cause: the ring push (r6b) moved f20.1's whole sections out by up to 0.055 L, so the
strokes projected onto it land elsewhere; the per-vertex push (r6_default) read 16.9 P (= r5_c1e) but folds 16.
Reported, not blocking: scalp_px 4 P -> 65 W, body_profile_iou_skin 0.724 P -> 0.686 W, art_peeks_hair 17 -> 19 W,
back lines 0.928 -> 0.584, lock lines up. Next: skin_clear modes (lockshell): 'narrow' (narrow the lock where its edge
enters the head, as fold_fix narrows a fold; the visible face stays), 'ring', 'vertex'; sweep r6sw1 on r6b_default
(render2, six placements), then the default's mode and a re-gate.
Sweep r6sw1 (render2, base r6b_default; penetration and folds from each row's own pieces, since the splice reads the
base's raw mesh): ring (r6b) pen 0, folds 9, strokes P dir 22.8 W, peeks 19 / 19.0, term mean 1.484; **vertex** pen 0,
folds 16, dir 16.9 P, peeks 19 / 19.2, term 1.461; narrow pen 0, folds 9, dir 16.9 P, peeks 21 / 20.3, term 1.583,
side locks P 0.600; off pen 0.0398. art_peeks_hair is Michael's flag, hair_folds isn't (WARN to 40; the new folds lie
on f20.1's inner face against the temple, under the lock), so the default is `skin_clear 'vertex'` (= r6_default's
build: hair_penetration 0 P, strokes P dir 16.9 P, art_terminator_hair 1.303 P, six 1.417, back 1.77). Re-gate 3.

### Re-gate 3 (05854cdd into pipeline-3d 59c93f38, `--accept hair_noise`): FAIL under K, 1 blocker: build CPU 1.71x
`charkit/out/gate/gate_tool-hairshell3_05854cdd_into_59c93f38.md`: penetration, the 2x2 and the strokes cleared
(hair_strokes_profile_dir 14.6 -> 16.9 P); the baseline itself got faster (pipeline-3d: 1190 -> 884.7 s CPU), so our
lock fit (~600 s) is 1.71x (884.7 -> 1509.6 s; the limit 1327 s). Reported: scalp_px 4 P -> 65 W, body_profile_iou_skin
0.724 P -> 0.69 W, peeks 17 -> 19 W, back lines 0.928 -> 0.584, lock lines and strokes moved. Next cut: frames()'s
transport on plain floats (3.5x on frames, 45% of the fit; not bit-identical per frame, BLAS's dot rounds differently, so
the shells' identity is checked by capcheck2 on the box), det_join_nfev 150 -> 60.
capcheck2 (build box; `charkit/out/hairshell3/capcheck2/`): the old path (numpy transport, no cap) against the new
(plain-float transport, det_join_nfev 60): **17 of 17 shells bit-identical**, the fit's CPU 661 -> 252 s. (`remote run`
now picks a box itself (build2 joined): name `--box build` for a build that lives there.) Re-gate 4 on render2.
