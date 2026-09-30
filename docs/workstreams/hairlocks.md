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

## Next

1. The side locks' lock truth (front, three-quarter, profile), then the back layers.
2. The pilot (the bangs cut from the drawing): first the ceiling of the builder's lock model (the wedges' cuts placed
   to fit the truth in all three views at once), then the drawn locks lifted into 3D through the hull, then ribbons.
