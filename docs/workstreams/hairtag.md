# The hair's layer masks against a hand-checked truth (tool/hairtag)

State: in progress. Worktree `~/animation-pipeline-hair4`, branch `tool/hairtag` from pipeline-3d `9549b30`.

The outfit-source method applied to the hair: the layer masks (`hair_layers`: bangs, side locks, upper and lower back,
buns, ahoge, flyaways per view, and each bun by side) scored against a hand-checked labelling of the body sheet, then
the tagging improved where the truth shows errors.

## tool/hairtag-truth: the measurement alone (the fallback split, round 2)

The coordinator held tool/hairtag because the hair pieces fitted to its new masks moved both ways. This branch, from
pipeline-3d, lands the measurement without moving any geometry:
- the truth (`charkit/refs/clawd/hair_truth.{json,npz}`, the manifest's `hair_truth`), the scorer (`hairlayers score`,
  `hairlayers truth`), `charkit/tests/test_hairtruth.py`, the review page and the labs (`tools/hairtag/`);
- the method (the drawing's structure: lock regions, cel tones, the vote, clips out, the buns' rim kept) **behind a
  setting, off by default**: `hairlayers.STRUCT` is the old transfer (the produced hair layers are pipeline-3d's
  exactly, checked array by array), `STRUCT_ON` the method. `python -m charkit hairlayers SPEC --struct --out DIR`
  makes the method's masks off the manifest's path, and `hairlayers score --masks DIR/hair_layers.npz` grades them
  (0.9585 against pipeline-3d's 0.892). No measurement step: the produced layers don't change.

tool/hairtag carries the method on by default with the 2x2 below; the rest of this file is its record.

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

## Merges and gates

- `ecc1358` the truth and scorer; `97d9449` the method; `018f297` pipeline-3d `b43c15e` merged in (tool/infra3's gate
  under K, tool/toonrender2's QA drawing), cleanly; test_hairtruth, test_manifest, test_registry, test_hairpieces,
  test_outfit pass. This branch adds no QA part or step (the hair layers' keys are unchanged; the QA's hair checks read
  them as before).
- **Gate** (default spec): `charkit/out/gate/gate_tool-hairtag_b2b06d0_into_b43c15e.md`, **PASS** under K: no new
  FAIL, no flag check changed status or grade, build CPU 1081 -> 937 s (0.87x). 54 test files pass.

## The downstream effect (the gate's build, default spec, b2b06d0 against pipeline-3d b43c15e)

| check | before | after |
|---|---|---|
| hair_piece_bangs | 0.762 PASS | 0.788 PASS |
| hair_piece_side_locks | 0.545 WARN | 0.528 WARN |
| hair_piece_upper_back | unchanged | |
| hair_piece_lower_back | 0.703 PASS | 0.606 PASS |
| hair_piece_buns | 0.826 PASS | 0.825 PASS |
| hair_piece_ahoge / flyaways (INFO) | 0.267 / 0.19 | 0.336 / 0.15 |
| hair_bun_outline | 0.397 FAIL | 0.358 FAIL |
| hair_folds | 6 WARN | 11 WARN |
| hair_penetration (the skin's crown artifact, hair4) | 0.0124 FAIL | 0.0141 FAIL |
| hair_noise | 0.0748 WARN | 0.0725 WARN |
| art_peeks_hair (flag) | 19 WARN | 15 WARN |
| art_terminator_hair (flag) | 2.376 WARN | 2.428 WARN (grade unchanged) |
| art_fragments_hair / art_outline_hair (INFO) | 1.29 / 0.689 | 1.17 / 0.605 |
| body_{front,profile,back}_top | 0.0048 PASS | 0.0142 PASS (the ahoge piece 0.005 L taller: its whole curl is ahoge now) |

**Read with care:** the hair_piece_* checks grade the pieces against the hair layers, which this branch changes, so
each reading compares the new pieces with a new target. The targets moved (old against new masks, pooled over front,
profile and back): bangs IoU 0.920, side locks 0.827, upper back 0.790 (57.5 k -> 65.7 k px: the back's central lobe),
lower back 0.730 (34.8 k -> 30.7 k), buns 0.999, ahoge 0.656, flyaways 0.546 (6.2 k -> 3.6 k). The 2x2 (each build's
pieces against both mask sets, hairlab `--built` with the layers swapped) is not run: next step 1. The truth score is
the target's own accuracy (0.892 -> 0.958); the pieces' fits are the geometry's.

## State (end of round, 2026-09-30)

- Branch `tool/hairtag`: `ecc1358` truth and scorer, `97d9449` the method, `018f297` pipeline-3d b43c15e merged,
  `b2b06d0` notes (gated), then these notes. Never pushed.
- Review page: `charkit/out/hairtag/review/index.html` (sheet | truth | before | its errors | after | its errors, with
  both outfit mask sets; scores, rules and calls).

## Next steps

1. The 2x2 for the hair pieces: each build's pieces scored against both the old and the new hair layers (hairlab
   `--built`, the produced layers swapped), so the pieces' moves (lower back -0.097, folds 6 -> 11, bun outline -0.039)
   split into target and geometry.
2. hair_folds 6 -> 11: which locks fold on the new partition (the upper back now reaches the back's central lobe;
   tools/hair4/foldlab.py).
3. The front (0.918): the ahoge's shaded half votes bangs under the tone split (ahoge 0.973 without it), the right outer
   mass's shadowed underside votes upper back (1.8 k px; call B/C decide it), flyaways over the outer masses.
4. The profile's far-bun peek (bun_R side 0.003; none at all with the sheet-only outfit masks) and, with them, the
   buns' undersides in profile (1.3 k px): outfit-source's open item.
5. Stretch not done: lock-level labels within the bangs and side locks.

## Round 2 (2026-09-30 night): the 2x2 for the hair pieces, the folds, the refits

Relaunched lean from the notes above. pipeline-3d still b43c15e.

**The 2x2 in the lab** (`tools/hairtag/twobytwo.py BUILD OUT OLD.npz NEW.npz`): hairlab's context over
`charkit/out/h4n_nocrown` (a build-box build whose every hair check equals the gate baseline's: bangs 0.762, side locks
0.545, lower back 0.703, bun outline 0.397, folds 6), once with the old hair layers (`charkit/out/hairtag/masks_base.npz`,
pipeline-3d's, truth 0.892) and once with the new (`charkit/out/hairtag/produced/hair_layers.npz`, this branch's, 0.958);
the pieces built from each set (the geometry) and each scored by the QA's own `hair_pieces_measure` against each set (the
measure). Why not the gate's 2x2 alone: its crossed cell runs the baseline worktree's QA, which reads the hair layers the
baseline worktree produced, and a cached baseline worktree produces none (the hair_pieces part SKIPs there).

**The lab reproduces both gate builds**: the pieces built from the old masks and scored against them read bangs 0.762,
side locks 0.544, upper back 0.760, lower back 0.704, buns 0.826, bun outline 0.397, folds 6 (the gate's baseline:
0.762 / 0.545 / 0.760 / 0.703 / 0.826 / 0.397 / 6); from the new against the new 0.788 / 0.528 / 0.760 / 0.606 / 0.825 /
0.357 / 11 (the candidate: 0.788 / 0.528 / 0.760 / 0.606 / 0.825 / 0.358 / 11). The build as built scores as the old
geometry does to 0.001.

**The 2x2** (`charkit/out/hairtag/r2/x1/twobytwo.json`; geometry = the masks the pieces were built from, measure = the
masks they are scored against):

| check | old geom, old measure | new geom, old measure | old geom, new measure | new geom, new measure | reading |
|---|---|---|---|---|---|
| hair_piece_bangs | 0.762 | 0.759 | 0.786 | 0.788 | flat (-0.003 / +0.002) |
| hair_piece_side_locks | 0.544 | 0.520 | 0.536 | 0.528 | **geometry worse under both** (-0.024 / -0.008; profile 0.501 -> 0.475 under the new) |
| hair_piece_upper_back | 0.760 | 0.711 | 0.697 | 0.760 | target moved (-0.063); geometry +0.063 under the new |
| hair_piece_lower_back | 0.704 | 0.552 | 0.570 | 0.606 | target moved (-0.134); geometry +0.036 under the new |
| hair_piece_buns | 0.826 | 0.826 | 0.824 | 0.825 | flat |
| hair_piece_ahoge (INFO) | 0.270 | 0.262 | 0.362 | 0.337 | geometry worse under both (-0.008 / -0.025) |
| hair_piece_flyaways (INFO) | 0.186 | 0.169 | 0.171 | 0.151 | geometry worse under both (-0.017 / -0.020) |
| hair_bun_outline | 0.397 | 0.361 | 0.392 | 0.357 | **geometry worse under both** (-0.036 / -0.035): front 0.409 -> 0.387, profile 0.362 -> 0.305 |
| hair_fringe_low | 0.0094 | 0.0094 | 0.0094 | 0.0094 | flat |
| hair_folds (geometry only) | 6 | 11 | | | side_lock_L 2 -> 5, side_lock_R 1 -> 2, bangs 1 -> 2 |

The shape (the hair class against the drawn hair, as the body QA draws it; measure-free): front 0.8389 -> 0.8391,
three-quarter 0.7406 -> 0.7381, profile 0.8316 -> 0.8345, back 0.9216 -> 0.9214.

So the lower back's -0.097 at the gate is the target (-0.134 on the same geometry) with the geometry gaining +0.036 on
the new target, and the upper back's 0.760 -> 0.760 hides a -0.063 target move and a +0.063 geometry gain. The real
geometry losses are the side locks, the bun outline, the folds (and the INFO ahoge and flyaways).

**What moves the pieces** (`tools/hairtag/attrib.py`: the hull's labels from one mask set and the build's own mask reads
from another, key by key; `charkit/out/hairtag/r2/a1`, `a2`):

| variant (labels / build's reads) | folds | side_lock_L | side_lock_R | bangs | bun outline (old measure: front, profile) |
|---|---|---|---|---|---|
| old / old (A) | 6 | 2 | 1 | 1 | 0.397 (0.409, 0.375) |
| new / new (B) | 11 | 5 | 2 | 2 | 0.361 (0.387, 0.311) |
| new / old | 16 | 5 | 2 | 7 | 0.398 (0.410, 0.375) |
| old / new | 8 | 1 | 2 | 3 | 0.354 (0.376, 0.311) |
| old / new, the profile's reads old | 7 | 2 | 1 | 2 | 0.385 (0.389, 0.375) |
| old / new, the bun masks old | 8 | 1 | 2 | 3 | 0.377 (0.378, 0.375) |
| new, the profile's labels old / new | 7 | 1 | 2 | 2 | 0.361 |
| new, the profile's bangs and side-lock labels old / new | 6 | **0** | 2 | 2 | 0.361 |
| new / new, the ahoge's reads old | 11 | 5 | 2 | 2 | 0.377 (**0.408**, 0.319) |
| new / new, the bun masks old | 11 | 5 | 2 | 2 | 0.385 (0.390, **0.375**) |

- **side_lock_L's folds (2 -> 5, all on lock 2 at phi 77, theta 125-127, outer and inner)** come from the hull's labels
  under the new profile bangs and side-lock masks alone. Those masks are nearer the truth (profile side locks 0.798 ->
  0.860, bangs 0.925 -> 0.974), so it is the builder's to fix.
- side_lock_R +1 and bangs +1 come from the build's reads of the new profile masks (the drawn tips).
- **The profile's bun outline (0.375 -> 0.311)** is 52 px of the profile's left bun: the field's outfit masks call them
  pin_star, the new clip rule dropped them from the hair, and the truth (and the sheet-only outfit masks) call them
  bun_L. A 0.5% change to one bun mask moved the bun fit to another optimum (its own IoU up in every view, 0.843 ->
  0.847 profile, 0.875 -> 0.893 back; the outline down). A mask error against the truth: **fixed in the mask**
  (`STRUCT['clip_rim']`, default on: within the buns' rim the clips don't take the hair). Truth 0.9581 -> 0.9585,
  profile bun_L side 0.968 -> 0.974 (the old masks' value), the bun keys now identical to the old masks'; profile
  ahoge / bangs / upper back move 12 / 12 / 7 px; the sheet-only outfit masks score the same (0.9496).
- **The front's bun outline (0.409 -> 0.387)** comes from the ahoge built from the new ahoge masks (profile 1,848 -> 1,047
  px: truth profile ahoge 0.315 -> 0.779, front 0.846 -> 0.827, back 0.795 -> 0.758).

**The side_lock_L folds, diagnosed** (scratch diagnostics over the lab's builds):
- The new labels move 267 of the hull's 22,531 hair points, 226 of them between bangs and side locks at the temple (the
  truth's rule 7 accepts either there). The envelope R is identical where the folds are. What moves is side_lock_L's
  top in the columns at phi 66-78 (theta 51 against 42-48), and so the phase of each column's theta samples (each
  column is sampled from its own top in 1.5-degree steps).
- The folds sit where the side-lock trim's pull stops: pulled cells hold the lock at about 0.38 L from the chart's
  centre, and the next cell down is not ahead of the drawn edge and stays at about 0.49 L. So each column has a step of
  about 0.1 L in one row, at phi 76-78, theta 125-129. Columns sampled out of phase across that step stitch into
  flipped faces. Round 3's geometry already had 2 folds on the same spot, lock 2 of side_lock_L.
- Tried, not taken: every column on one theta grid (`th_aligned`): folds 11 -> 13, and the old geometry 6 -> 9. The
  pull carried on below the chin, easing out (`trim_fade` 6 / 12 / 20 deg): 11 / 10 / 10 (the step is above the chin,
  where the drawn edge stops being passed). The trim off: 9 (side_lock_L 3), side locks 0.528 -> 0.524. Taking the
  temple's old labels (bangs and side locks) gives side_lock_L 0 folds, but those labels are the masks'.
- The pull's smoothing wider (`trim_smooth` 5 / 8): folds 11 / 13 (the old geometry 6 -> 7 / 7). **The folds stay
  11 (WARN, the band runs to 40): diagnosed, not fixed this round.** A fix is the trim's pull itself (the pulled cells
  ending in a step), and it has to hold on both geometries.

**pipeline-3d 4de65ab merged** (`ebc8582`: face4-crown's exact hair normals and crown fit, face4's chin, infra3's
carry-over gates, mouth2); only the qa3d steps list conflicted (both kept). Box builds of the merged head, default
spec, `crown_trim` off (`charkit/out/h5_off`) and on (`h5_crown`, spec `charkit/out/h5spec/clawd_crown.json`): the
coordinator's question, whether the crown trim holds art_terminator_hair under 2.5 on the exact normals.

**The side locks' loss (new measure 0.536 -> 0.528, profile 0.501 -> 0.475)** is the profile's lower-back labels
(`charkit/out/hairtag/r2/a3`): with the old profile lower back on the hull (everything else new), the new geometry reads
side locks 0.538, upper back 0.772, lower back 0.605 (all at or above the old geometry's), but folds 12. The new
profile lower back is the shadow tone below the head (the truth's rule 2, call B), and the hull's labeller gives each
point the view that faces it most squarely: at the jaw that is the profile, so points the front view draws as side
lock become lower back. A labeller that weighs the views' agreement (not only the squarest view) is the next step.
Not a mask error: the new masks' remaining profile error runs the other way (lower back called side locks, 1,050 px).

**crown_trim on the exact hair normals** (the coordinator's add-on; box builds of `0161ec5`, default spec, fetched to
`charkit/out/h5_off` and `h5_crown`). Face4-crown's exact normals (pipeline-3d 4de65ab) took away what held the crown
trim off in hair round 4 (art_terminator_hair 2.376 -> 2.607, the proxy normals' flips at the lock edges):

| check | crown_trim off | on |
|---|---|---|
| art_terminator_hair (flag; pass 2.0, warn 2.5) | 2.252 WARN (front 2.192, three-quarter 2.252, profile 1.567, back 1.945) | **2.236** WARN (2.190, 2.236, 1.658, 1.796) |
| art_peeks_hair (flag) | 16 WARN | 15 WARN |
| hair_piece_upper_back / buns | 0.760 / 0.826 | 0.772 / 0.847 |
| hair_bun_outline (front, profile) / corners | 0.385 (0.390, 0.375) / 22 | 0.436 / 19 |
| hair_piece_bangs / side_locks / lower_back | 0.788 / 0.528 / 0.606 | 0.786 / 0.527 / 0.606 |
| hair_noise | 0.0735 WARN | 0.076 WARN |
| art_outline_hair (INFO) | 0.648 | 0.623 |
| body_three_quarter_iou_hair (the other 48 body and shape IoUs, widths and tops unchanged) | 0.740 | 0.739 |
| hair_folds / hair_penetration | 11 / 0 | 11 / 0 |

No status or grade changed; the flag checks both improve. **crown_trim is on by default** (`hairpieces.OPTS`), riding
this round's gate.

### Round 2 gates and state (2026-09-30 night)

- **tool/hairtag** `37c09cf` into pipeline-3d 4de65ab: `charkit/out/gate/gate_tool-hairtag_37c09cf_into_4de65ab.md`,
  **PASS** under K (no new FAIL; the flag checks improve: art_terminator_hair 2.433 -> 2.236, art_peeks_hair 19 -> 15;
  CPU 0.98x). Moved: hair_folds 6 -> 11 WARN, hair_bun_outline 0.397 -> 0.436 (FAIL both), hair_noise 0.0745 -> 0.076
  (WARN both), art_outline_hair 0.71 -> 0.623 (INFO), body_three_quarter_iou_hair 0.742 -> 0.739. The hair_piece_*
  checks are remeasured (the step at 97d9449). The gate's 2x2 fills the new-measure column only (old geometry ->
  new: lower back 0.570 -> 0.606 improved, upper back 0.697 -> 0.772, buns 0.826 -> 0.847, bangs 0.786 -> 0.786, side
  locks 0.537 -> 0.527, ahoge 0.356 -> 0.323, flyaways 0.171 -> 0.150). Its old-measure column is "unmeasured": the
  crossed QA runs in the baseline's worktree, which reads the hair layers that worktree produced, and a cached
  baseline worktree produced none. **A gate gap (infra's):** a 2x2 over a produced reference needs the crossed
  worktree to produce it first. The lab's 2x2 above is that column.
- **tool/hairtag-truth** `257aac0` (from pipeline-3d 4de65ab: the truth, the scorer, the review page and the labs, the
  method behind `--struct`, off by default) into 4de65ab: `charkit/out/gate/gate_tool-hairtag-truth_257aac0_into_4de65ab.md`,
  **PASS**, nothing reported (no check moved), CPU 1.10x.
- pipeline-3d moved after both gates (f2ec090, tool/evalmesh M1): not re-gated.
- Review page: `charkit/out/hairtag/r2page/index.html` (the 2x2, the pieces by family old and new, the crown-trim
  pair's QA pictures side by side).

**For Michael:**
1. Which branch lands: tool/hairtag (the method on, crown_trim on: the back layers fit the truer target better, the
   bun outline +0.039 and both flag checks improve, but folds 6 -> 11 and side locks -0.01 to -0.02), or
   tool/hairtag-truth (the measurement alone, no geometry moved), with the method's geometry waiting on the next
   items.
2. Call B (the shadow tone below the head is the under layer) drives the side locks' loss through the hull's
   labeller. Keep it and make the labeller weigh the views' agreement, or relax it at the jaw.

**Next:**
1. The hull's labeller: weigh the views that see a point, not only the squarest (the side locks' loss at the jaw).
2. The side-lock trim's pull ending in a step (0.1 L in one row at phi 76-78, theta 125-129): the folds' spot.
3. The front ahoge's shaded half (the tone split votes it bangs: truth front ahoge 0.846 -> 0.827), which moves the
   ahoge piece and the front bun outline (-0.019).
4. What the hair side needs from the sheet-only outfit masks (tool/garments3): the profile buns' undersides as bun
   (1,258 px of profile bun are called upper back with them; buns 0.977 -> 0.948), and the far bun's peek as bun_R
   (none at all with them). The clip rule now spares the buns' rim, so a pin piece that overlaps a bun's edge no
   longer takes the bun's pixels, with either outfit mask set.

## Round 3 (2026-09-30): the method on by default, the merge, hair_noise, the folds

Michael's decisions (2026-09-30): the structure-based masks go on by default (0.892 -> 0.958 against the truth); the
truth's calls A-E are accepted as truth. Lock 0 of the lower back (behind the jaw, its junction with the collar) is
tool/collar's this round (art_speckle_neck): its trim is left alone here.

**The merge** (`b7f63ff`, pipeline-3d 25b1936: crowntrim, the garments round's sheet-only outfit masks, look5 and look6,
infra3's 2x2 fix, evalmesh, infra-auth). Conflicts: `hairlayers.STRUCT` (tool/hairtag-truth landed it off, as
`STRUCT_ON` beside it): now `STRUCT = STRUCT_ON`, the plain transfer is `STRUCT_OFF` (`hairlayers SPEC --no-struct
--out DIR`, for the old measure); crown_trim was the same change on both sides; the manifest takes outfit_truth; this
file keeps tool/hairtag-truth's section. The suite the gate's way (`gate._tests`, each file a script): 66 files pass.

**Gate 1** (d4d9033 into pipeline-3d 25b1936): `charkit/out/gate/gate_tool-hairtag_d4d9033_into_25b1936.md`, **FAIL
under K**, one block: the flag check art_terminator_hair 2.286 -> 2.905 (its worst view the back: ratio 2.905 to the
design's kinks per L). Reported, not blocking: hair_noise 0.0807 FAIL -> 0.0793 WARN (improved), art_speckle_neck
2.606 WARN -> 1.34 PASS (improved), hair_folds 5 -> 4, art_peeks_hair 22 -> 16 (flag, value only), art_fragments_hair
1.58 -> 1.23, hair_bun_outline 0.431 -> 0.456 (FAIL both), scalp_px 0 -> 4 (PASS), CPU 1.24x. The fixed 2x2 fills
every cell now (old geometry old measure / new geometry old measure / old geometry new measure / candidate): lower back
0.706 / 0.562 / 0.572 / 0.617 (worse under the old measure, better under the new), side locks 0.550 / 0.523 / 0.543 /
0.534, upper back 0.768 / 0.721 / 0.701 / 0.768, bangs 0.760 / 0.758 / 0.785 / 0.792, buns 0.862 / 0.864 / 0.862 /
0.864. On the merged base the folds and hair_noise premises changed: pipeline-3d's own build reads folds 5 (not round 2's
6 -> 11 on the field's outfit masks) and the method lowers hair_noise under its line.

**The terminator, attributed** (box builds of the merged head, default spec: `charkit/out/h6_m` as committed, and
`h6_off` with the plain transfer, `STRUCT_OFF`, which reproduces pipeline-3d 25b1936's gate baseline exactly: 2.286,
hair_noise 0.0807, folds 5, art_speckle_neck 2.606). The back view's hair terminator: 7 kinks in 3.60 L -> 14 in 3.56 L
(ratio to the design's 1.355 kinks per L: 1.433 -> 2.905); the front's 40 -> 34. `tools/hairtag/termlab.py BEFORE AFTER
OUT` runs the QA's artifacts part on one bundle with one hair object at a time taken whole from the other
(`charkit/out/hairtag/r3/term1.json`): back ratio with the flyaways swapped 2.905 -> 2.080 (and pipeline-3d's with ours
1.433 -> 2.042), side_lock_L 2.492 / 1.664, bun_L 2.553 / 1.735, upper back 2.832 / 1.708; the rest within 0.03. The
flyaway blades barely moved (five, the same places, one 0.02 L deeper): their shading did. Each vertex takes the whole
hair's blurred envelope normal, which turns along a blade standing out of the mass, so a cel terminator crosses each
thin strand (the kinks on the side flicks at mid height and low on both sides, qa_artifacts back).

**Fix, the builder's:** `strand_tone` (a style key; anime 'root', the default profile 'surface'): each flyaway strand
shades in one tone, its root's normal. On the bundles (the flyaways' corner normals alone replaced): h6_m 2.905 FAIL
grade -> **2.308 WARN** (back 3.936 -> 3.128 kinks per L, front 7.378 -> 7.108, three-quarter 9.41 -> 8.809), and
pipeline-3d's own hair 2.286 -> 2.173. Under K a flag check blocks when its status or grade gets worse: 2.286 WARN ->
2.308 WARN is a value move.

**hair_noise, where it sits** (`tools/hairtag/noiselab.py BUILD OUT 'name|{...}'`: hairlab's rebuild, qa3d.hair_noise's
drawing, each piece's pixels and tone-edge pixels per view; the lab reads 0.0791 on h6_m, the build 0.0793): front
0.124 (1,157 edges in 9,304 px: bangs 333 round the star clip, side locks 209 + 205, lower back 197, bun_L 142, bun_R
50, flyaways 21), profile 0.065 (bun_L 175, upper back 156, bangs 113), back 0.048 (upper back 173, lower back 137,
bun_L 133, bun_R 64). bun_L's block facets carry 2-3x bun_R's edges in every view (its fit, not the light: the light is
camera-relative). h6_off (pipeline-3d's hair) reads 0.0807 (front 0.1223, profile 0.0689, back 0.0508).

**pipeline-3d 9eba0b0 merged** (`76b55cb`: tool/look6's design light, tool/evalmesh M4, tool/mouth3): the qa3d
measurement steps conflicted (both kept); anime.json merged clean (look6's face_lift beside strand_tone). Suite: 66 pass.
Pregate PASS (12 moved, 0 blocking): `charkit/out/pregate/pregate_tool-hairtag_76b55cb_into_9eba0b0.md`.

**Gate 2** (76b55cb into 9eba0b0, with strand_tone; job `gate-hair4-0930-150450-121a`):
`charkit/out/gate/gate_tool-hairtag_76b55cb_into_9eba0b0.md`, **PASS under K** (nothing blocks; 37 items; CPU 1.24x).
Flag checks, values only: art_terminator_hair 2.286 -> 2.308 (WARN grade both, as the bundle lab said), art_peeks_hair
22 -> 16. Improved: hair_noise 0.081 FAIL -> 0.0785 WARN, art_speckle_neck 2.606 WARN -> 1.34 PASS. hair_folds 5 -> 4.
Remeasured, the 2x2 (old geometry old measure / new geometry old measure / old geometry new measure / candidate): lower
back 0.706 / 0.562 / 0.572 / 0.617 (the one drop, under the old measure), side locks 0.550 / 0.523 / 0.543 / 0.534,
upper back 0.768 / 0.721 / 0.701 / 0.768, bangs 0.760 / 0.758 / 0.785 / 0.792, buns 0.862 / 0.864 / 0.862 / 0.864.
**Mergeable under K.**

**The folds** (the merged build h6_m, `wherefolds.py` over foldlab's piece_folds; `charkit/out/hairtag/r3/`): 4 against
pipeline-3d's 5: bangs lock 6 (phi 77.4, theta 68, the temple), side_lock_L lock 2 (phi 72.9, theta 126.9: round 2's
spot, the trim's step at the jaw), side_lock_R lock 0 (phi -66.9, theta 119.2), upper back lock 7 inner (the crown).
Round 2's 6 -> 11 was on the field's outfit masks; on the sheet-only masks' hull the new labels fold less than the old.
Tried, not taken: the trim's pull eased along each column (`trim_slope`, a cone over the pulls, 0.005-0.03 L a row):
the side_lock_L fold follows the ease's end (theta 127 -> 134-141; folds 4 / 5 / 5 / 4 / 5) and the lower back drops
0.617 -> 0.602-0.605 (`charkit/out/hairtag/r3/slope1.txt`). Reverted.

**The side locks** (step 5): the gate's 2x2 reads a geometry loss under both measures (0.550 -> 0.523 old, 0.543 ->
0.534 new). Round 2 traced it to the hull labeller's squarest view (the profile's call-B lower back at the jaw). In the
lab now: `label_hull(weigh=p)`, every view that sees a point votes its family with score ** p
(`charkit/out/hairtag/r3/label_weigh.patch`, not committed; `labvote.py BUILD P...` beside it; results to
`r3/vote1.txt`). **Result: weigh 1, 2 and 4 move 0 of the hull's labels** (every check, fold and shape IoU identical):
no hull point is seen by more than two of the views, so the weighted vote always picks the squarest view's family.
Round 2's "weigh the views' agreement" can't move the jaw's labels. What's left is call B itself (the profile's shadow
tone at the jaw as the lower back), which Michael accepted as truth: the side locks' -0.009 under the new measure is
that call's cost to the geometry unless a side-lock prior (the front view's side lock kept where the profile's lower
back meets it at the jaw) is wanted.

**hair_noise:** 0.0807 FAIL -> 0.0793 WARN at gate 1 (the method's masks lower it); where it sits is above (front view:
bangs round the star clip, the side locks, bun_L's facets). Not fixed further this round. noiselab's drawing doesn't
take the rebuilt flyaways' per-vertex normals (strand_tone reads the same there), so the build is its measure.

**Next (a lean relaunch):**
1. Gate 2 PASS under K (above). If pipeline-3d moves before the merge: `python -m charkit gate --carry tool/hairtag
   --into pipeline-3d` (everything after 76b55cb is notes).
2. The side locks: the labeller vote is moot (above). Only a decision on a side-lock prior at the jaw remains
   (Michael's).
3. hair_noise's margin (0.0793 against 0.08): bun_L's block facets (2-3x bun_R's edges in every view: its fit) and the
   bangs' tone loops round the star clip are the largest movable parts.
4. For tool/collar: this round didn't touch lock 0 of the lower back or its trim. art_speckle_neck reads 2.606 -> 1.34
   (PASS) on this branch's masks at gate 1 (the profile 2.606 -> 0.628), so the method's lower-back labels alone clear
   the profile's specks; the front's 1.34 is unchanged.
