# Workstream A: cut-piece hair (`tool/hair-pieces`)

Clawd's hair as authored pieces instead of the visual hull's one carved mass. `hair.shape.mode: "pieces"` in a spec,
or `python -m charkit build SPEC --hair pieces`.

## What was built

| Module | What |
|---|---|
| `charkit/hairlayers.py` | The generated hair breakdown turned into per-view family masks on the body sheet's hair: the manifest's produced `hair_layers` (`python -m charkit hairlayers SPEC`, page `charkit/out/clawd/hair/index.html`). |
| `charkit/geom/hairpieces.py` | The pieces: the hull's vertices labelled by family; the mass lofted on a chart round the crown and split into locks; buns, ahoge and flyaways. |
| `charkit/cli.py` `pieces_hair` | The venv-side build step, cached as the geom hair's is: `out/geom/hair_pieces/` (a part `.npz` per piece and `pieces.json`). |
| `charkit/scene.py` `hair_pieces_objects` | The Blender stage: one `hair_NAME` object per piece, with the hair's toon material and outline, rigged to the head, and the envelope normals transferred after the outline. |
| `charkit/qa3d.py` `hair_pieces` | The QA part: `hair_piece_<family>`, `hair_fringe_low`, `hair_fringe_gap`, `hair_penetration` and `hair_folds`. |
| `charkit/hairpage.py` | The review page (`python -m charkit hairpage BUILD --against BASE`). |
| `charkit/styles` `hair_pieces` | The construction's style settings: notch, thickness, inset, lock width, normals, and the shading envelope's close and blur. |

### The families: `charkit.hairlayers`

The breakdown is segmented by its legend: the nearest swatch in Lab, with the lower back's pink above the eye line
counted as the fringe's lightest tone.

It is registered onto body_turnaround's calibrated views:
- one scale and one eye row for all three of its views;
- fitted by FFT correlation of the hair (the buns' zone left out) and the face's skin.

Then each body-sheet hair pixel takes the nearest breakdown family, within the view's own figure. The buns are the
outfit's bun pieces.

On Clawd: 514 px/L, hair overlap 0.68 / 0.72 / 0.80 (front, profile, back) and face overlap 0.69 / 0.57. Two
generations of one design, so the partition comes from the breakdown while the silhouettes stay the body sheet's.

### The pieces: `charkit.geom.hairpieces`

**Labels.** Each hull hair vertex takes the family of the view that sees it most squarely. The profile is mirrored to
label her right side.

**The mass** (bangs, side locks left and right, upper and lower back) lives on a chart round the crown: theta from the
crown direction, phi round it from the front. On that chart:
- **Envelope.** The hull's outermost mass hair per cell, filled along theta and round phi, smoothed, and made round at
  the pole.
- **Not hair.** A cell whose outermost hull point is not hair (the face) is never covered.
- **Skin.** Our skin's triangles, sampled densely: the whole head above the chin, and below it what lies inside the
  envelope. Grown and smoothed.
- **Regions.** Each family's largest region, within what its name allows (the fringe in front, the back layers
  behind), cut free of thin bridges. The crown rows take the family below them.

**Locks.** Each piece's lower edge splits into locks at its notches, which are deepened by the style's `notch`. A lock
is a closed shell:
- its columns are sampled at absolute theta steps and stitched by ladder, so a jagged tip edge shears nothing;
- the outer surface is the envelope less the layer's inset, pushed out smoothly where the skin bulges past it;
- the inner surface is the style's `thick` below, tapering to `tip_thick`, smoothed over the skin's upper envelope and
  never within `gap` of it.

Each lock stores a strand direction per vertex and a chain of 6 joints from root to tip, for VRMC_springBone.

**Buns, ahoge, flyaways.**
- The buns are icosphere radius fields round their cores.
- The ahoge comes from the drawings' strokes: front x and profile y, paired by arc length.
- The flyaways are the front mask's strokes as planar blades.

**Shading.** Every piece shades from the whole hair's envelope (`smooth.envelope_normals` over the union, closed and
blurred as the style says), as the geom hair does. The locks read as one cel-shaded mass, told apart by their outlines.

## Measurements

These are from the merge gate: **PASS**. The report is `charkit/out/gate/gate_tool-hair-pieces_14dd9f0_into_6a576ce.md`.
The gate builds Clawd's default spec (the MakeHuman head) with the geom hair before and the pieces after. The review
page is `charkit/out/hair_review/index.html` (`python -m charkit hairpage`).

| Check | Geom hair (base) | Pieces |
|---|---|---|
| body hair width front / 3/4 / back | 0.877 / 0.905 / 0.890 WARN | 0.971 / 0.956 / 0.986 PASS |
| body hair width profile | 0.976 PASS | 0.962 PASS |
| body hair IoU front / profile / 3/4 / back | 0.829 / 0.783 / 0.762 / 0.920 PASS | 0.835 / 0.752 / 0.741 / 0.897 PASS |
| hair_noise | 0.1036 FAIL (old measure; 0.047 WARN as re-measured) | 0.0444 WARN (remeasured: no outlines, occluded) |
| scalp_px | 0 PASS | 5 PASS |
| sheet_shown front / profile / 3/4 | 0.584 / 0.331 / 0.504 WARN | 0.672 / 0.181 / 0.524 WARN |
| hair_piece_* (pooled IoU against the hair layers) | none | bangs 0.605, upper back 0.725, lower back 0.645, buns 0.655 PASS; side locks 0.482 WARN; ahoge 0.22, flyaways 0.21 INFO |
| hair_penetration / hair_folds / hair_fringe_low | none | 0 PASS / 9 WARN / 0.057 L WARN |

- No graded check lost its status.
- On the code head (`--base code`, built before the last two commits), no PASS was lost either, and hair_noise went
  0.057 to 0.050. But the lower back reaches into the neck and shoulders (hair_penetration 0.049 L FAIL, 201
  vertices), and the fringe ends 0.07 L short over the eyes (FAIL).

## Detail round (`tool/hair-detail`)

Michael's note on the checkpoint: the detail of the drawn pieces was lost in the render, and the buns came out as
smooth blobs. Measured first with `python -m charkit hairlab BUILD` (new: the pieces rebuilt over a finished build's bundle with
style, opts and shape overrides, and measured by the QA's own hair checks with no Blender, about 20 s a variant). The
causes were:
- **Buns.** An icosphere radius field over the hull's bun points: the visual hull keeps outlines only, so a blob.
- **The head swelled up into the buns.** The hull is the union of head and bun (it can't carve the notch between
  them). Its fill under each bun was labelled bangs or side locks and lifted the envelope, so from the front our bangs
  covered the lower half of each drawn bun (5,600 of its 16,100 px).
- **The hair sat 0.024 L low against our eyes.** `i3d.eye_target` put the hull's eyes (the drawn irises' centroid)
  on our eye knobs' line, but our irises sit 0.024 L above it. The QA anchors on the irises, as the drawings do.
- **The fringe ended short.** A lock's lower edge was the chart's 4 degree columns interpolated, then notched 7
  degrees deeper, so the drawn points over the eyes were rounded off.
- **Side locks** stood in front of the face in profile (the hull fills the gap between lock and cheek).
- **Shading.** Every lock shaded with the one envelope normal, so a lock had no relief of its own.

What changed:

| Where | What |
|---|---|
| `hairpieces.bun_block`, `fit_block` | A block bun template: two rounded boxes (superellipsoids, `bun_e` 0.3: flat faces, bevelled edges), the main block and the fold's slab. Its pose, size and slab are fitted by Nelder-Mead to the drawn bun's front, profile and back silhouettes (the hull's views, `view_px`). It shades with its own normals. Chosen per design: `hair.shape.pieces_opts.bun: "block"` (default `round`). |
| `hairpieces.carve_under_buns` | A mass point that the front or back view draws inside a bun, and beyond the head's outline, becomes `BUN_BASE`, out of the envelope. The head's outline is the convex hull of the drawn mass above the eye line (the buns hide the head's top). The envelope fills over it from its column. On Clawd, 723 points. |
| `i3d.eye_target` | `hair.shape.eye_anchor: "iris"` aligns the generated shape to our irises' height. Opt-in; the default stays on the knobs' line. |
| `hairpieces.drawn_tips`, `fine_tips` | The drawn lower edge at any phi. With `fine_tips` (default `('bangs',)`), a lock's edge is the drawing's at its own 1.5 degree columns (median of 3). |
| `hairpieces.clamp_to_view`, `skin_front` | The side locks are held behind the drawn profile's front edge. A vertex in front of the cheek stays `gap` in front of it, because the front view draws the lock over the cheek. The free clamp buried 715 vertices behind it. |
| `hairpieces.crown_cap` | The cap's inner face clears the skin, as a lock's does. It was the upper back's penetration. |
| `lock_shell` relief, `shade_normals` lock_shading | Each lock gets a ridge across it (`relief` L), with grooves between locks. Its shading blends its own normal into the mass's (`lock_shading`). Anime: 0.015 L and 0.35. Its notch is now 3 (was 7): the drawn edge already carries the notches. |
| `qa3d` | Added `hair_bun_outline` (outline agreement at 0.012 L, graded 0.7 / 0.5), `hair_bun_corners` (INFO, ours against drawn) and `hair_tips_front`/`_back` (INFO, the lock tips along the lower edge). |
| `hairlab` | The measurement loop above, as a command (`--labels PNG`: the QA scene's family labels per view with the drawn outlines). |
| `hairpage` | A renders section (the design's turnaround figures beside the before and after boards). With `--against`, the hair pieces' checks are remeasured on both builds by the current QA. |
| `charkit/spec/clawd_body_pieces.json` | clawd_body with the hair in pieces, block buns and the iris anchor. |

Measured by `hairlab` over the same build (`charkit/out/hd_base`, a box build of clawd_body in pieces at 849b9a7),
so the skin and the QA are the same. "Before" is the hair as built there. "After" is `--opts bun=block --shape
eye_anchor=iris` with the new defaults:

| Check | Before | After | Step that moved it |
|---|---|---|---|
| hair_piece_bangs | 0.611 | 0.739 | carve (+0.13), iris anchor (+0.04) |
| hair_piece_buns | 0.687 | 0.829 | carve, block fit with its slab |
| hair_bun_outline (0.012 L) | 0.212 FAIL | 0.385 FAIL | block fit |
| hair_bun_corners (ours / drawn) | 20 / 35 | 17 / 35 | the round buns' lumps counted as corners; the bevels round ours off |
| hair_piece_side_locks | 0.505 | 0.557 | clamp, iris anchor |
| hair_piece_upper_back / lower_back | 0.780 / 0.692 | 0.778 / 0.726 | notch 3, iris anchor |
| hair_fringe_low (L, + short) | 0.014 | 0.009 | fine tips (the iris anchor alone made it 0.038) |
| hair_tips front / back (drawn 4 / 8) | 4 / 4 | 4 / 4 | |
| hair_penetration (L) | 0.038 | 0.015 (2 vertices) | crown cap |
| face shown / design: front, 3/4, profile | 1.12, 1.02, 0.53 | 1.12, 1.08, 0.82 | clamp (profile) |

Ablations with `hairlab` were the evidence for each default:
- **Round buns.** With the carve they score 0.772 IoU and 0.303 outline; the fitted block scores 0.829 and 0.385.
- **Knobs anchor** (final config otherwise): bangs 0.698, side locks 0.521, buns 0.811, tips 2 / 4, but the face shown
  front is 1.06.

## Left

- **Side locks** (IoU 0.46, WARN). Ours follow the hull's envelope, which fills the gap between the lock and the cheek
  that no view shows. The drawn locks hang closer to the face and curl in at the chin. That needs per-view silhouette
  constraints on the side locks (the drawn masks in front and profile), not just the envelope.
- **Code head.**
  - The lower back penetrates the neck and shoulders. Below the chin, the skin field only counts skin inside the
    envelope. Clear the neck's and shoulders' own surface instead.
  - The fringe ends short over the eyes.
- **The fringe's tips** end 0.05-0.07 L above the drawn ones over the eyes. The lower edges now come from the drawing
  that faces each column, but a 4 degree column can fall between narrow drawn tips.
- **Folds.** 11 faces remain (WARN; bangs, side locks and the upper back's crown).
- **Springs.** The chains are stored in the parts' meta, but no bones or VRMC_springBone export yet.
- **hair_noise.** The front still reads 0.066: the lit fringe against the side locks turned away, a real shadow shape
  along jagged tips.
