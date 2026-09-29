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
