# The hair's layer masks against a hand-checked truth (tool/hairtag)

State: in progress. Worktree `~/animation-pipeline-hair4`, branch `tool/hairtag` from pipeline-3d `9549b30`.

The outfit-source method applied to the hair: the layer masks (`hair_layers`: bangs, side locks, upper and lower back,
buns, ahoge, flyaways per view, and each bun by side) scored against a hand-checked labelling of the body sheet, then
the tagging improved where the truth shows errors.

## The truth

`charkit/refs/clawd/hair_truth.npz` (charkit-hair-truth/1), built from its source `hair_truth.json` by
`python -m charkit hairlayers truth` (the source is the record; `charkit/tests/test_hairtruth.py` checks the npz matches
it). Registered in the manifest as `hair_truth`, without a sha256: it grades, no produced reference reads it, so it
stays out of their stamps.

**How it is made.** The body sheet's hair cells (`outfit.cells`: runs of the hair class, drawn lines and faint ridges
as walls) of 25 px or more, on the masks' grids (`bodyqa.design_views`, 212.5 px/L). Only 19 / 17 / 9 / 9 hair cells
are that large in front / three-quarter / profile / back: the drawing's lock lines are partial strokes, so the big cells
(front 17.6 k px, profile 32 k, back 59 k) hold several families. Those are cut along polylines (snapped to the drawn
lines between waypoints: the cheapest path over the picture's value, so a cut follows a stroke and crosses its gap
straight; or straight where marked), and every piece of 12 px or more takes the family set of the seed inside it.
`tools/hairtag/truthpic.py` draws a view's regions, cuts and seeds (unseeded pieces red) for writing and checking it.

**Size:** 93 regions: front 36 (51,274 px), three-quarter 18 (51,732), profile 19 (46,075), back 20 (73,480). Lines,
cut paths and slivers are unscored.

**Split rules** (in the source's `rules`):
1. One drawn lock, one family: family boundaries run along the drawn lines, straight across their gaps.
2. The under layer is drawn in the shadow tone. In a zone below the head (front rows 305+, profile 265+, back 270+),
   hair darker than 0.75 is lower_back unless a seed says otherwise. In the back, the lit lock tips below the dark band
   (rows 352+) are lower_back too.
3. The ahoge ends at the head's outline (a straight cut across its base).
4. The flick tips at the outer silhouette, cut straight across their base, accept flyaways or their mass's families.
5. The strands under the buns (a cell each) accept flyaways or their bun (bun tails).
6. Clips drawn in the hair colour (the crab) are none.
7. The side of the head above the side lock accepts bangs or side_locks (front: the temple strip down to the eyes'
   top; profile: from the fringe's back line to the star). Below the eyes' top, the face-framing lock is side_locks.
8. The lit outer masses behind the side locks accept side_locks or upper_back (hair_breakdown paints them side-lock
   yellow with upper-back purple at the edge). The inner locks by the jaw accept side_locks or lower_back.
9. The profile's far-bun peek accepts either bun (as the outfit truth does).
10. The three-quarter's mass is unresolved (any mass family). Only the buns by side, the ahoge, the clips and the side
    lock under the star are scored there; the hair layers make only bun sides in that view.

**Calls that decide numbers (for Michael):**
- A. The flick tips as flyaways-or-mass (front 4, back 4, profile 1). hair_breakdown's green strands sit at the body
  sheet's flicks, which the body sheet draws joined to the mass.
- B. The shadow tone below the head as the under layer. This puts the back's central lit lobe (down to the V at row
  355) in the upper back; the current masks call it lower back (5.5 k px, the largest error).
- C. The temple strip and the profile's side-of-head region as bangs-or-side_locks, the outer masses as
  side_locks-or-upper_back.
- D. The crab as none (the masks label it hair).
- E. The profile's small flick at the side lock's back edge is its lock's, not a flyaway.

The head turnaround isn't truthed: the hair checks that read it (hairlab's fragments and steps) read its silhouette,
not its families.

## The score

`python -m charkit hairlayers score [SPEC] [--masks M.npz] [--json OUT]` (`hairlayers.score`), as `outfit score`:
- **hair accuracy** per view and in all: of the scored pixels where the truth or the masks put a family, the share
  whose family the truth accepts;
- **per family IoU**, with the truth resolved per pixel (the masks' family where the set accepts it, else the set's first);
- the largest confusions;
- **bun sides** per view (VIEW__bun_L / _R, the three-quarter too), each pixel's side resolved the same way.

Review page: `python tools/hairtag/review.py OUT NAME=MASKS.npz ...` (sheet | truth | each mask set | its errors, per
view at one scale; the tables; the rules and calls). This round's: `charkit/out/hairtag/review/index.html`.

### Before (pipeline-3d's masks, `charkit/out/clawd/hair/hair_layers.npz`, outfit masks with the TRELLIS field)

| view | front | profile | back | all | mean family IoU |
|---|---|---|---|---|---|
| accuracy | 0.904 | 0.855 | 0.907 | **0.892** (18,443 px wrong) | 0.732 |

Per family: bangs 0.937, side_locks 0.806, upper_back 0.792, lower_back 0.649, buns 0.978, ahoge 0.560, flyaways 0.401.
Bun sides: front L 0.979 / R 1.0; back 0.999 / 0.998; three-quarter 0.999 / 0.998; profile L 0.974, **R 0.003** (the
far bun's peek: the outfit masks give it to bun_L, 804 px, and the family masks give 515 px of it to bangs, upper back
and ahoge).

Largest confusions: back upper_back called lower_back 5,510 px (the central lit lobe: the masks cut the layers straight
across at the breakdown's height, the drawing's layer edge is the scalloped shadow line); front lower_back called
upper_back 2,036; profile lower_back called side_locks 1,388 and upper_back called lower_back 1,099 (bands across drawn
locks); front flyaways spilling over the outer masses 938; profile upper_back called ahoge 916; the profile's bun strand
called ahoge 552 (the breakdown's cyan strand segments as the ahoge's teal); the crab called bangs 291.
