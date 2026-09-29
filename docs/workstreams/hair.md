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
- **Side locks** stood in front of the face in profile, because the hull fills the gap between lock and cheek. This
  one is not fixed yet; see Left.
- **Shading.** Every lock shaded with the one envelope normal, so a lock had no relief of its own.

What changed:

| Where | What |
|---|---|
| `hairpieces.bun_block`, `fit_block` | A block bun template: two rounded boxes (superellipsoids, `bun_e` 0.3: flat faces, bevelled edges), the main block and the fold's slab. Its pose, size and slab are fitted by Nelder-Mead to the drawn bun's front, profile and back silhouettes (the hull's views, `view_px`). It shades with its own normals. Chosen per design: `hair.shape.pieces_opts.bun: "block"` (default `round`). |
| `hairpieces.carve_under_buns` | A mass point that the front or back view draws inside a bun, and beyond the head's outline, becomes `BUN_BASE`, out of the envelope. The head's outline is the convex hull of the drawn mass above the eye line (the buns hide the head's top). The envelope fills over it from its column. On Clawd, 723 points. |
| `i3d.eye_target` | `hair.shape.eye_anchor: "iris"` aligns the generated shape to our irises' height. Opt-in; the default stays on the knobs' line. |
| `hairpieces.drawn_tips`, `fine_tips` | The drawn lower edge at any phi. With `fine_tips` (default `('bangs',)`), a lock's edge is the drawing's at its own 1.5 degree columns (median of 3). |
| `hairpieces.clamp_to_view`, `skin_front` | Opt-in (`clamp_side_locks`). It holds the side locks behind the drawn profile's front edge, as a shear per height, and never behind the cheek the front view draws them over. It is off because moving a built lock folds it. The first renders crumpled at the cheeks: 150-200 outer folds per side lock, per vertex; 40-130 sheared. The builder counted its folds before the clamp, so the QA missed them (they are now counted after it). |
| `hairpieces.crown_cap` | The cap's inner face clears the skin, as a lock's does. It was the upper back's penetration. |
| `lock_shell` relief, `shade_normals` lock_shading | Each lock gets a ridge across it (`relief` L), with grooves between locks. Its shading blends in the lock's outer normal, smoothed within the lock `lock_shading_smooth` times (`lock_shading`). The relief fades out again over the lock's last 30%: out along the chart's radius, a hanging tip dipped into the shoulders. On the default spec that gave the lower back 0.004 L of penetration, 1 vertex, the gate's one regression. Anime: relief 0.008 L and lock_shading 0.2. The raw facets at 0.35 put the p95 angle between adjacent shading normals at 30 degrees. Smoothed at 0.2 it is 3-7 degrees (the envelope alone gives 3), and it adds under 0.002 to hair_noise. The anime notch is now 3 (was 7), because the drawn edge already carries the notches. |
| `qa3d` | Added `hair_bun_outline` (outline agreement at 0.012 L, graded 0.7 / 0.5), `hair_bun_corners` (INFO, ours against drawn) and `hair_tips_front`/`_back` (INFO, the lock tips along the lower edge). |
| `hairlab` | The measurement loop above, as a command. `--labels PNG` draws the QA scene's family labels per view with the drawn outlines. `--noise` gives hair_noise's measure for the rebuilt pieces, drawn as the build's hair objects with the pieces' meshes and shading normals. |
| `hairpage` | A renders section: the design's turnaround figures beside the before and after boards, with close-ups of the top (buns, fringe, locks). With `--against`, the hair pieces' checks are remeasured on both builds by the current QA. |
| `charkit/spec/clawd_body_pieces.json` | clawd_body with the hair in pieces, block buns and the iris anchor. |

Measured by `hairlab` over the same build (`charkit/out/hd_base`, a box build of clawd_body in pieces at 849b9a7),
so the skin and the QA are the same. "Before" is the hair as built there. "After" is `--opts bun=block --shape
eye_anchor=iris` with the new defaults:

| Check | Before | After | Step that moved it |
|---|---|---|---|
| hair_piece_bangs | 0.611 | 0.757 | carve (+0.13), iris anchor (+0.04) |
| hair_piece_buns | 0.687 | 0.831 | carve, block fit with its slab |
| hair_bun_outline (0.012 L) | 0.212 FAIL | 0.400 FAIL | block fit |
| hair_bun_corners (ours / drawn) | 20 / 35 | 17 / 35 | the round buns' lumps counted as corners; the bevels round ours off |
| hair_piece_side_locks | 0.505 | 0.537 | iris anchor (the clamp's 0.557 is off, see above) |
| hair_piece_upper_back / lower_back | 0.780 / 0.692 | 0.780 / 0.723 | notch 3, iris anchor |
| hair_fringe_low (L, + short) | 0.014 | 0.009 | fine tips (the iris anchor alone made it 0.038) |
| hair_tips front / back (drawn 4 / 8) | 4 / 4 | 4 / 4 | |
| hair_penetration (L) | 0.038 | 0.015 (2 vertices) | crown cap |
| face shown / design: front, 3/4, profile | 1.12, 1.02, 0.53 | 1.12, 1.04, 0.63 | iris anchor (the clamp reached 0.82 in profile) |
| hair_noise (builds, per-group cuts) | 0.060 | 0.068 | see below |

Ablations with `hairlab` were the evidence for each default:
- **Round buns.** With the carve they score 0.772 IoU and 0.303 outline; the fitted block scores 0.829 and 0.385.
- **Knobs anchor** (final config otherwise): bangs 0.698, side locks 0.521, buns 0.811 and tips 2 / 4. The face shown
  in front is 1.06.
- **hair_noise.** hair_noise rose with the block buns, not with the lock detail. `hairlab` with the old shared cuts:
  - final 0.070; with round buns 0.047; without the carve 0.054; without the lock detail 0.069; without fine tips 0.069.
  - The measure cut tones at percentiles of all the hair's pixels, so the blocks' large flat faces moved the mass's cuts.
  - It now cuts each tone group at its own percentiles (`qa3d.tone_edges`, `HAIR_NOISE_GROUPS`: the buns apart from
    the mass). This is registered in `history.STEPS` (cc79d07), so gates call it remeasured.
  - Remeasured builds: before (849b9a7) 0.0597; after (e4c5d18) 0.0879 FAIL becomes 0.068 WARN; the default spec's
    candidate 0.048 becomes 0.055.
  - **The real cost of block buns**, the mass's front tone edges on its own cuts, block against round with all else
    equal: 0.128 to 0.139 per pixel (+9%). Between the two builds, where everything changed: front 0.125 to 0.148;
    profile 0.034 to 0.031; back 0.044 to 0.037. The buns' own edges went from 0.02 to 0.06; that is the blocks'
    faces and bevels.

## Left

- **Side locks: face shown in profile** is 0.63 of the design's (IoU 0.54, WARN). The hull fills the gap between lock
  and cheek. Pushing built locks back folds them (above), so the profile constraint has to go into the chart's
  envelope before lofting, from the drawn profile edge per row. The drawn locks also curl in at the chin.
- **Buns** outline 0.40 at 0.012 L (FAIL against 0.7), IoU 0.83. The drawn bun has two loops with a visible step
  between them. Ours is a block plus a slab, so the next template would be real loop geometry: a ribbon swept around
  the knot. Corners are 17 against the drawn 35, because our bevels round them off.
- **hair_penetration** 0.015 L (2 vertices, the upper back near the pole): the chart's coarse skin sampling at the pole.
- **eye_anchor 'iris' as the default.** It is opt-in here. It moves every hair mode's alignment 0.024 L up on Clawd,
  and bodyeval, faceeval and garments use eye_target too, so it is the integrator's call.
- **Shared generated inputs.** charkit/out/hull and charkit/out/clawd were hard-linked across seven worktrees. A build
  whose stamp is stale rewrote them in place for everyone. (It was the same content: the hull code didn't change.)
  This worktree's copies are now its own.
- **Lock outlines and highlight streaks:** not done. The relief is 0 at a lock's edges, so adjacent locks meet with no
  depth step for the inverted-hull outline to catch.
- **Folds.** 9 on clawd_body (WARN): the bangs and the side locks.
- **Springs.** The chains are stored in the parts' meta, but no bones or VRMC_springBone export yet.
