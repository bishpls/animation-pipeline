# Hair, step 2: the B lock-shell pilot (tool/hairshell, round 2: tool/hairshell2)

State: round 2 in progress (see "Round 2" at the end). Round 1 (below) as it was. Worktree `~/animation-pipeline-hairshell`, branch `tool/hairshell` from tool/hairsplit
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
- Real render-box build of the pilot (lockshell DEFAULT = the chosen config; spec tools/hairshell/clawd_shells.json):
  `charkit/out/hs2_shells_r` (job id in charkit/out/remote/jobs/, log charkit/out/hairshell2/hs2_shells_r.log).
