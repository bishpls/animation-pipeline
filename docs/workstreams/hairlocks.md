# The hair's locks against a hand-checked lock-level truth (tool/hairlocks)

State: in progress. Worktree `~/animation-pipeline-hair4`, branch `tool/hairlocks` from pipeline-3d `2f42155`.

Michael's question: should the hair's strands and locks be defined and cut more accurately than we've been comparing
to? Every hair check so far is at the family level (`hair_piece_<family>` IoU) or on the whole silhouette. The
structure labeller (`hairlayers.lock_regions`) splits the sheet's hair along its drawn lines but only votes families
with it; the builder (`hairpieces.locks`) invents its own lock partition (phi wedges on the crown chart, cut at the lower
edge's notches), and nothing compared it with the drawing.

## The lock truth

`charkit/refs/clawd/hair_locks_truth.{json,npz}` (charkit-hair-locks-truth/1; the manifest's `hair_locks_truth`, no
sha256, as `hair_truth`). Built by `python -m charkit hairlocks truth` from the source; `charkit/tests/test_hairlocks.py`
checks the npz matches it. On the hair layers' grids (bodyqa.design_views, 212.5 px/L), so the family truth, the masks,
the labeller and our z-buffered locks all share one grid.

**How it is made.** As the family truth: the sheet's hair cells (outfit.cells, 25 px or more) cut along polylines
(snapped to the drawn stroke where it runs, straight across its gaps), each piece labelled by a seed `family/name`, or
`x` (unscored). `hairlayers.truth_regions` gained a `valid` argument for the lock labels. A completeness test: a cell
whose family-truth majority is a scope family and has no seed stops the build (the three-quarter skips it: its family
truth is unresolved in the mass, so its bang locks were checked by eye). Tools: `tools/hairlocks/pic.py` (the truth,
the cells or any lock image over a zoomed crop), `raw.py` (a smooth zoom), `walls.py` (the walls the labeller sees:
the raw line class and the faint ridges), `ctx.py` (the cached context: design views, the transfer's hair, the
labeller's regions).

**Size (bangs only, this round):** 12 locks: front 5 (r_out, r, c, l, l_clip; 10,967 px), three-quarter 4 (r, c, l,
l_clip; 8,300 px), profile 3 (c, l, l_clip; 5,994 px). The side locks are not labelled by lock yet.

**Split rules** (the source's `rules`):
1. A lock is a region the drawing bounds by lock lines (strokes along the strands from root toward tip), the hair's
   outline, the skin it hangs over (the eye-holes) and the clips. A short inner stroke that reaches neither the root
   nor a side (a split tip, a strand line) doesn't part it.
2. The crown above the lock lines' upper ends is unscored: the lines stop short of the part. The cut runs straight
   through their upper ends.
3. A lock that merges into another family's lock below (her right bangs into the face-framing side lock) ends at the
   family truth's cut at the eyes' top; its tip is `cut` and left out of the tip scores.
4. A lock whose lower part a clip hides (l_clip under the crab and star): area and boundary scored, tip `hidden`.
5. The strip between the outermost line near the star and the outline (it runs under the star into the side lock) is
   unscored.
6. Scope per view: the families whose locks are labelled. Hair outside the lock truth counts against a lock of ours
   that spills onto it; only `x` is excluded.
7. A lock keeps its name across views where the correspondence is read (below).

**Calls that decide numbers (for Michael):**
- A. The bangs are five locks in front, four in three-quarter, three in profile. The front's r_out is the thin temple
  strip on her right between the outermost line and the outline, below the flyaway's root: its own lock.
- B. The central lock's short inner stroke near its tip is a split tip, not a lock line.
- C. Correspondence: front c (the central lock, tip between the eyes) = profile's front fringe lock; front l (over her
  left eye) = profile's lock over the eye; l_clip above the crab and star in all three. Her right bangs are hidden in
  profile. The three-quarter's outer sweep on her right (the flick at 388,202) is unscored: r_out or the side hair.
- D. The c|l line runs straight down the gap between the eyes.
- E. The strip beside the star is unscored.

## The score

`charkit.hairlocks.score` (`python -m charkit hairlocks score BUILD`; the lab: `tools/hairlocks/ours.py BUILD OUT.npz`
then `tools/hairlocks/score.py OUT.json NAME=OUT.npz`). A build's locks are its mass pieces' locks (the part npz's
per-vertex `lock`) z-buffered on the design grids in the QA's scene (skin, eyes, mouth, accessories, garments occlude;
the buns, ahoge and flyaways occlude as hair). Per view:
- **lock count** per family (ours: candidate locks, 30 px or more visible, at least 30% of it on the truth's locks);
- **lock IoU**: Hungarian matching on IoU, the mean over the truth's locks (unmatched 0); silhouette and family edges
  included. **IoU within the truth**: the partition alone (our pixels off the truth's locks left out);
- **boundary** (the pair's mean symmetric boundary distance, L) and **lines** (the truth's lock lines to our boundary);
- **tip** (tip distance, drawn tips only) and **tip width** (the width profile at 80/85/90/95% of the lock's height);
- **purity**: each candidate region's share in its dominant drawn lock; **best merge**: each truth lock against the
  union of the candidates it dominates.
The drawn lines between locks (unlabelled) go to the nearest lock within 2 px, for the truth and the labeller alike.

**Calibration** (the rule: pass on the design, fail on a known-bad example): the truth against itself 1.000 in every
view; a shuffled partition (the truth's lock area split into as many random Voronoi cells, 5 seeds) 0.441 (front
0.387, three-quarter 0.403, profile 0.583). test_hairlocks.py holds both (own 1.0, shuffled under 0.7).

## Before: how far off we are (pipeline-3d 2f42155, `charkit/out/hl_base`, a build-box build of the default spec)

| set | view | truth locks | ours | lock IoU | within the truth | boundary L | lines L | tip L | tip width L | purity |
|---|---|---|---|---|---|---|---|---|---|---|
| **ours (builder)** | front | 5 | bangs 6 | **0.420** | 0.505 | 0.050 | 0.049 | 0.082 | 0.044 | 0.882 |
| | three-quarter | 4 | bangs 6 | **0.415** | 0.534 | 0.045 | 0.024 | 0.095 | 0.043 | 0.844 |
| | profile | 3 | bangs 4 | **0.501** | 0.610 | 0.040 | 0.035 | 0.046 | 0.006 | 0.871 |
| | all | 12 | | **0.439** | 0.541 | | | | | 0.866 |
| labeller (lock_regions) | front | 5 | 10 regions | 0.308 | 0.337 | 0.081 | 0.030 | 0.024 | 0.039 | 0.789 |
| | three-quarter | 4 | 15 regions | 0.745 | 0.783 | 0.017 | 0.016 | 0.022 | 0.042 | 0.999 |
| | profile | 3 | 10 regions | 0.714 | 0.722 | 0.017 | 0.018 | 0.074 | 0.021 | 0.930 |
| | all | 12 | | 0.555 | 0.582 | | | | | 0.906 |
| shuffled (known-bad) | all | | | 0.441 | 0.441 | | | | | 0.707 |

Readings:
- **Our lock partition scores at the known-bad level** (0.439 against a random partition's 0.441; the partition alone
  0.541). Its counts are off (6 bangs locks in front and three-quarter against 5 and 4 drawn), its lock lines sit
  0.02-0.05 L (5-10 px) from the drawn ones and its drawn tips 0.05-0.10 L away. The builder's wedges are straight
  meridians on the crown chart; the drawn lock lines sweep sideways as they fall (her right bangs sweep down-left).
- **The labeller is a candidate source in three-quarter and profile** (0.745, 0.714; purity 0.93-1.0: its regions
  respect the drawn lines and merge into locks, best merge 0.85-0.89), **not in front** (0.308): the front's lock lines
  are partial strokes that don't close, so one region spans c, l and the crown (region 82). A lock source from the
  drawing needs the truth's move: continue each stroke across its gap (to the next line, the outline or the crown cut).

Review page: `charkit/out/hairlocks/review/index.html` (`tools/hairlocks/review.py OUT SCORES.json NAME=LOCKS.npz`:
per view the sheet | the truth | ours | the labeller, each lock coloured as the truth lock it matches; the per-lock
numbers; the calibration; the rules and calls).

## The pilot, step 0: what limits our locks (measured before cutting anything)

Baseline QA of `charkit/out/hl_base` (pipeline-3d 2f42155, default spec): hair_noise 0.0785 WARN, hair_piece_bangs
0.792, side locks 0.534 WARN, hair_folds 4 WARN, art_terminator_hair 2.308 WARN, art_peeks_hair 16 WARN,
hair_fringe_low 0.0094, body hair IoU front 0.840 / three-quarter 0.757 / profile 0.829.

**The wedge model's ceiling** (`tools/hairlocks/wedge.py BUILD OUT.json [--own] [--shear] [--k ...]`): the bangs
piece's own surface re-cut into K phi wedges on the crown chart (the builder's lock model: straight meridians), the
cuts placed by coordinate descent on the mean lock IoU of front, three-quarter and profile at once; `--shear` lets each
cut lean (phi = a + b (theta - 60)), the drawn lines' sideways sweep. The path reads the builder's own partition as the
scorer does (0.439). Results: below.

**Correspondence across views** (`tools/hairlocks/corr.py BUILD OUT.json`): the drawn locks read back onto our bangs
surface; each triangle takes the truth lock most of its pixels lie in per view, and two views agree where they give it
the same lock. Results: below.

First wedge run (equal-spaced start, k = 5, straight cuts): 0.411 (front 0.380, three-quarter 0.312, profile 0.593),
below the builder's own 7 wedges (0.439): the descent stalls in a local optimum from that start.

**Results (both probes landed):**

| bangs partition (hl_base's bangs surface) | lock IoU | within the truth | front | three-quarter | profile |
|---|---|---|---|---|---|
| the builder's 7 wedges (notches) | 0.439 | 0.541 | 0.420 | 0.415 | 0.501 |
| 7 straight wedges, cuts fitted to the truth | 0.482 | 0.587 | 0.479 | 0.426 | 0.560 |
| 7 sheared wedges, fitted (shear -0.7 to +0.15 deg phi per deg theta) | 0.515 | 0.624 | 0.502 | 0.485 | 0.575 |
| the labeller's regions (for scale) | 0.555 | 0.582 | 0.308 | 0.745 | 0.714 |

Even with the cuts fitted to the truth (which a builder can't do), the wedge model gains only +0.04, and +0.08 with
shear: **the meridian-wedge lock model is the limit, not where its notches fall.** Curved lock boundaries on the chart
(ribbons between two contour curves) are needed to approach the drawing.

Correspondence through our bangs surface (triangles two views both label; agreement = the same lock name):
front~three-quarter 0.547 (1,261 triangles), three-quarter~profile 0.413 (658), **front~profile 0.07** (399: the
front's l reads as the profile's c on 194 triangles, the front's l_clip on 155). So **call C is likely wrong**: the
profile shows her left side, and its front fringe lock is the front's l (over her left eye), not the central c; the
three-quarter's names also shift one lock toward her left (front c ~ three-quarter r on 254, front l ~ three-quarter c
on 193). Our surface's own misfit confounds this, so the correspondence stays a call for Michael; the pilot needs its
lift to find the links, not assume the names.

**Probe jobs (done; they ran on the laptop, one chained job):** `wedge.py charkit/out/hl_base
charkit/out/hairlocks/wedge_own.json --own --shear` (descent from the builder's own 6 cuts, then with shear; log
`wedge_own.log`), then `corr.py charkit/out/hl_base charkit/out/hairlocks/corr_base.json` (log `corr_base.log`). If
the session ends first, rerun both (about 3-5 min each on the laptop).

## Next steps for the bangs pilot (a lean relaunch)

1. Read `wedge_own.json` and `corr_base.json` (above). If the straight wedges with the best cuts stay near 0.44-0.5
   and shear lifts them clearly, the builder's lock model (meridian wedges) is the limit: the pilot needs curved lock
   boundaries on the chart (a boundary phi(theta) per lock line), i.e. ribbons. If even shear stays low, the bangs
   piece's own outline and family edges dominate (compare `lock_iou_in`).
2. A drawn-lock source that isn't the truth (no gaming): `hairlayers.lock_regions` per view, with the front's partial
   strokes continued across their gaps (each stroke end extended along its direction to the next wall, the outline or
   the crown cut; the truth's move automated). Score it with `tools/hairlocks/score.py` as a labeller variant (target:
   the labeller's 0.745 / 0.714 in three-quarter and profile, and the front well above 0.308).
3. Lift onto the crown chart: each bangs chart cell's envelope point projected into front, three-quarter and profile
   (hairpieces.view_px / label_hull's view mapping), taking the region of the view that sees it most squarely; link
   regions across views by the cells they share (a region graph: same lock where the shared cells agree). Report the
   links and the disagreement (corr.py's number is the floor through our current surface).
4. Behind a setting (`hairpieces.OPTS['lock_source'] = 'drawn'`, default 'notches'): `locks()` takes per theta row the
   lifted lock boundaries instead of the lower edge's notches; `lock_shell` samples each lock between two boundary
   curves (the ribbon: two contour curves, the strand direction from the boundaries' mean tangent).
5. Measure in the lab (tools/hair4/lab.py or hairlab over `charkit/out/hl_base`): the lock scores (score.py), every
   hair check (hair_noise's margin: 0.0785 at hl_base against its 0.08 line), the folds, the shape IoU in all views
   (body_*_iou_hair). Default on only if the lock scores improve and nothing FAILs; then
   `python -m charkit pregate` and `python -m charkit remote gate tool/hairlocks --into pipeline-3d`.
6. The side locks' lock truth (front, three-quarter, profile), then the back layers. tool/accessories2 changes the
   star (hair_piece_bangs 0.792 -> 0.772 in its measurement): l_clip sits under it; don't edit accessories.py or the
   shared hair selection. Lock 0 of the lower back is tool/collar3's.

## State (checkpoint, 2026-09-30)

- Branch `tool/hairlocks`: `f1c33ec` the truth, the scorer, the tests, the tools, these notes; then this checkpoint
  (wedge.py, corr.py, the pilot plan). Never pushed; not gated (the branch adds a measurement only: no QA part or step,
  no produced reference changes content; hairlayers.truth_regions gained a defaulted argument).
- Local: `charkit/out/hl_base` (the baseline build), `charkit/out/hairlocks/` (ctx.pkl, ours_base.npz, score_base.json,
  review/, pics/).

## For Michael (decisions)

1. **Lock-level accuracy is worth measuring:** our lock partition scores at the random-partition level against the
   drawing (0.439 against 0.441), while the family IoU (hair_piece_bangs 0.792) calls the bangs PASS. The family checks
   can't see it. Keep the lock scores as a measure (INFO) now; a graded check after the pilot shows what a good
   partition reaches.
2. **The crown above the drawn lines is unscored** (rule 2): the lines stop short of the part. Accept, or extend each
   line straight to the part (more of every lock scored, but a guess).
3. **Call C's correspondence**: the probe says the names shift as the head turns (profile c ~ front l). Rename the
   profile's and three-quarter's locks by the probe's mapping, or keep the names per view and score views apart
   (the per-view scores don't depend on the names; only a cross-view reading does).
4. **The lock source for a pilot:** the structure labeller's regions where its strokes close (three-quarter, profile),
   continued across the gaps in front (the truth's own move, automated), lifted onto the crown chart.

## Round 2 (the ribbons pilot; started 2026-09-30)

The coordinator's decisions for the round (Michael's go-ahead): the lock scores stay INFO until after the pilot; the
crown above the drawn lines stays unscored; call C fixed from the probe; ribbons are the pilot's lock model. Merged
pipeline-3d `8b5ecae` (softras round 3, collar3 M2) first (clean).

**Call C, fixed** (`6c4cfb7`): the profile's locks renamed by the cross-view probe (the truth's source `calls` C and the
profile's `note` hold the evidence): its front fringe lock is the front's `l` (was `c`), its lock with the crab the
front's `l_clip` (was `l`), its lock under the part by the star `l_back` (was `l_clip`; a lock the front doesn't label:
behind the star, in call E's unscored strip). The three-quarter keeps the front's names. Every assignment of the
three-quarter's and profile's names brute-forced over corr.py's triangle pairs: this one agrees on 1,259 of 2,318 shared
triangles (the old names 990; shifting the three-quarter's names too scores lower). corr.py again: front~profile
0.07 -> 0.541, three-quarter~profile 0.413 -> 0.536, front~three-quarter 0.547 (unchanged). The drawn clips disagree
(the crab on l in front, about 27 degrees round her left; on the profile's l_clip, about 70): the sheet doesn't place
them consistently. Per-view scores don't move (they don't read names).

**The ribbon lock model** (`hairpieces.OPTS['lock_model'] = 'ribbon'`, default 'wedge'; `ribbon_pieces` ('bangs',)):
- `lock_lines`: the drawing's lock lines lifted onto the crown chart. Per view (front, three-quarter, profile), each chart
  point of the piece on the envelope that faces the view (normal . view > `ribbon_face` 0.3) and lies in the view's
  drawn family region takes the view's stroke evidence there (`drawn_strokes`: the labeller's walls, the raw line class
  and the faint ridges, off the region's outline by `ribbon_erode` 3 px; the three-quarter, which the hair layers don't
  split into families, uses its whole drawn hair), weighted by how squarely it faces, averaged over the views.
- The lines: smooth curves phi(theta) = a + b s + c s^2 (s = theta / 30 deg from a reference), held at their top value
  above the drawn span (the lines stop short of the part; the locks run on to the crown), straight on below it.
  `ribbon_lines` 'free': every (a, b, c) on a grid scored by the evidence along it, taken greedily (ribbon_rel of the
  best, never within lock_min of or crossing one taken); 'anchored' (default): one line per notch of the lower edge
  (the wedge's own cuts, `locks()`), sliding up to `ribbon_slide` 3 deg and bending (b, c) through the evidence above
  it, a small prior toward straight (`ribbon_prior`); `ribbon_keep`: a notch without that much evidence drops its line
  (its two locks merge); 'anchored+free' adds free lines where they clash with none.
- `ribbon_bounds` -> each lock between two boundary curves (the piece's sides and the lines, held apart); `lock_shell`
  (bounds=...) samples it in columns at fixed fractions across it, each column curving with its boundaries (the strand
  direction follows them); each column's tip where it meets the drawn edge (drawn_tips, iterated as the column curves).
  The wedge path is untouched (bit-identical by construction).

Lab: `charkit/out/hairlocks/multilab.py BUILD OUT.json VARIANTS.json [--noise]` (hairlab's context once, per variant the
pieces rebuilt, z-buffered in the QA scene, scored against the truth; the lab's hair checks); `chartpic.py` (the
chart's evidence with the lines over it). A probe variant (`truth_lines`) feeds the truth's own lock boundaries as the
evidence: the model and its line fit apart from the strokes (never the builder's source).

First runs (the lab over hl_base; lock IoU all / front / three-quarter / profile): the wedge 0.439 (0.420 / 0.415 /
0.501, the lab reproduces the notes' numbers); free lines from the strokes 0.272 then 0.214; free lines from the
truth's boundaries 0.349. Readings: the drawn lock lines on the chart span only theta 35-55 (the hairline to where the
tips separate; below, the eye-holes); free line detection doubles lines on one stroke and misses the notches; the
views' strokes land a few degrees apart on the chart (the drawing's inconsistency and our surface's depth).

**Checkpoint (round 2, about 70 tool calls).** The lab batches over hl_base (`charkit/out/hairlocks/m1.json`, `m2.json`;
lock IoU all (front / three-quarter / profile), hair_piece_bangs, the bangs' builder folds, bangs locks built):

| variant | lock IoU | bangs | folds | locks |
|---|---|---|---|---|
| wedge (default) | 0.439 (0.420 / 0.415 / 0.501) | 0.792 | 1 | 7 |
| anchored at the wedge's notches, strokes, prior 0.02 | 0.436 (0.406 / 0.384 / 0.555) | 0.783 | 1 | 7 |
| anchored, no prior (m1, lines could cross) | 0.452 (0.524 / 0.317 / 0.511) | 0.779 | 0 | 7 |
| anchored, no prior, crossings refused (m2) | 0.441 (0.508 / 0.305 / 0.511) | 0.786 | 0 | 7 |
| the same, front's strokes only | 0.438 (0.518 / 0.317 / 0.465) | 0.776 | 4 | 7 |
| anchored, truth-lines probe | 0.447-0.461 | 0.78 | 15-27 | 7 |
| anchored + free lines, truth-lines probe | 0.475 (0.518 / 0.372 / 0.539) | 0.779 | 15 | 8 |
| free lines, strokes / truth-lines / front's truth only | 0.198 / 0.210 / 0.403 | 0.77-0.79 | 1-18 | 5-7 |

Readings:
- **The ribbons lift the front and cost the three-quarter.** Anchored ribbons from the strokes: front 0.42 -> 0.51-0.52
  (c 0.51 -> 0.73, l 0.49 -> 0.67, l_clip 0.26 -> 0.45: the locks sweep as drawn), three-quarter 0.415 -> 0.31
  (its l 0.32 -> 0.16), profile about level. One chart partition can't follow both: the views' lines land several
  degrees apart on the chart (the drawing's inconsistency and our surface's depth). Overall level with the wedge.
- **Even the truth's own boundaries as the evidence reach only 0.45-0.475**, under the sheared wedges fitted to the truth
  (0.515): the line fit (a Hough-style search over curves) is not the partition's optimum, and the anchors (the
  wedge's notches from 4-degree chart columns, median-filtered: -54, -22, -2, 14, 42, 74) sit off the drawn lines
  (the truth's lift: about -70, -20, -7 and 27 in front; 45-50 and 65-70 in profile). Free lines double up on one
  stroke and extend badly outside the drawn span.
- The truth-lines probe's lines give 15-27 builder folds (tight bends); the strokes' lines 0-4.

Next (running): anchors from the drawn lower edge at 0.5 deg (`ribbon_anchors 'drawn'`, `drawn_notches`), a facing
threshold of 0.5, shear-only lines; and the ribbon form's capacity against the truth (`bendprobe.py`: quadratic cuts
descended from the sheared wedges' 0.515).
