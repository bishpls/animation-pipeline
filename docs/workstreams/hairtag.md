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

## The method: the drawing's structure over the transferred families

`hairlayers.transfer` gave every body-sheet hair pixel the family of the nearest breakdown pixel at its registered
position, so a family boundary is wherever the other generation's boundary lands, straight across the body sheet's
drawn locks (the back's layer edge cut at the breakdown's height through the central lobe). Now (`hairlayers.STRUCT`,
default on):
- **lock regions** (`lock_regions`): the sheet's hair split by its own drawing: the drawn lines (the raw class) and
  faint ridges (`outfit.ridges`) as walls, the hair's two cel tones apart (Otsu on its value: base and shadow; no
  palette), each tone's runs cut at their necks (a watershed of the distance to the walls, markers its h-maxima,
  h = 1.5 px), so partial strokes still part locks;
- **the vote** (`vote_regions`): a region whose transferred families agree to 0.6 takes that family whole, else keeps
  them per pixel; the walls take their nearest region's family;
- **clips** are not hair: the outfit's pieces other than the buns (the crab, drawn in the hair colour) leave the hair.

The breakdown still decides the families; the body sheet now decides where they part. No colour tuning: the tones are
the hair's own two modes.

`tools/hairtag/lab.py OUT [--outfit M.npz] 'name|{struct}' ...` runs variants from a cached context (about 5 s each).

| variant (field outfit masks) | front | profile | back | all | mean IoU | bangs | side | upper | lower | buns | ahoge | fly |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| before (pipeline-3d) | 0.904 | 0.855 | 0.907 | 0.892 | 0.732 | 0.937 | 0.806 | 0.792 | 0.649 | 0.978 | 0.560 | 0.401 |
| clips only | 0.908 | 0.860 | 0.907 | 0.895 | 0.736 | 0.952 | 0.815 | 0.799 | 0.649 | 0.977 | 0.560 | 0.401 |
| regions, no tone split | 0.933 | 0.909 | 0.911 | 0.917 | 0.820 | 0.972 | 0.888 | 0.835 | 0.670 | 0.969 | 0.973 | 0.434 |
| **regions + tones, vote 0.6 (default)** | **0.918** | **0.944** | **0.995** | **0.958** | **0.826** | 0.963 | 0.846 | 0.955 | 0.870 | 0.977 | 0.786 | 0.383 |
| vote 0.5 / 0.75 | 0.893 / 0.911 | 0.944 / 0.889 | 0.995 / 0.994 | 0.951 / 0.941 | 0.800 / 0.776 | | | | | | | |
| h 1.0 / 3.0 | 0.918 / 0.881 | 0.938 / 0.947 | 0.990 / 0.993 | 0.955 / 0.947 | 0.823 / 0.809 | | | | | | | |
| buns vote too | 0.915 | 0.946 | 0.993 | 0.957 | 0.826 | | | | | 0.971 | | |

Wrong pixels 18,443 -> 7,128. Largest left (default): front lower_back called upper_back 1,784 (the right outer mass's
shadowed underside votes with its lit part), profile lower_back called side_locks 1,050, front flyaways over the outer
masses 937, front lower_back called side_locks 611, the profile's under-bun strand 552 (called pin_star by the field's
outfit masks, so the clip rule drops it), the profile's far-bun peek 351 (bun_R side still 0.003).

**Caveat on the numbers** (as outfit-source's): the truth's rule 2 (the shadow tone below the head is the under layer)
and the method's tone split share a premise. The back's gain (0.907 -> 0.995) is that premise. Without the tone split
the regions alone score 0.917 (front 0.933, profile 0.909, back 0.911); the tone split costs the front 0.015 (the
ahoge's shaded half joins the crown's shadow and votes bangs: ahoge 0.973 -> 0.786) and gains the back and profile.

## The coupling: the outfit masks the hair layers read

`bun_sides` and the buns family are the outfit's bun pieces, and the clip rule reads its pin pieces. tool/garments3
merges tool/outfit-source's sheet-only masks (read-only from `~/animation-pipeline-garments3`, its produced
`outfit_masks.npz`: 0.9722 on the outfit truth, the field's 0.865).

| hair layers | outfit masks | front | profile | back | all | mean IoU | buns | profile bun_L side |
|---|---|---|---|---|---|---|---|---|
| before | field (pipeline-3d) | 0.904 | 0.855 | 0.907 | 0.892 | 0.732 | 0.978 | 0.974 |
| before | sheet-only (garments3) | 0.905 | 0.829 | 0.907 | 0.885 | 0.721 | 0.948 | 0.853 |
| default | field | 0.918 | 0.944 | 0.995 | 0.958 | 0.826 | 0.977 | 0.968 |
| default | sheet-only | 0.920 | 0.911 | 0.994 | 0.950 | 0.821 | 0.948 | 0.853 |

The sheet-only masks cost the hair's buns in profile (profile buns called upper_back 1,258 px: outfit-source's known
miss, the buns' undersides) and there is no profile bun_R at all (the field's masks had 2 px of it). The structure
method's gain holds under both (+0.066 / +0.065).
