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

Local loop (`--hair pieces` pieces measured over a build's body): see the build numbers below for the Blender build.

(numbers: see the report in the session and `charkit/out/pieces_mh3/hair/index.html`)

## Left

- **Side locks** (IoU 0.46, WARN). Ours follow the hull's envelope, which fills the gap between the lock and the cheek
  that no view shows. The drawn locks hang closer to the face and curl in at the chin. That needs per-view silhouette
  constraints on the side locks (the drawn masks in front and profile), not just the envelope.
- **The fringe's tips** read flatter than the drawn ones: 4 x 3 degree cells and a mode filter erode narrow tips. Take
  each piece's lower edge from the drawing that faces it, at pixel resolution. `hair_fringe_low` is 0.057 L on her left
  (WARN).
- **Folds.** 11 faces remain (WARN; bangs, side locks and the upper back's crown).
- **Springs.** The chains are stored in the parts' meta, but no bones or VRMC_springBone export yet.
- **hair_noise.** The front still reads 0.066: the lit fringe against the side locks turned away, a real shadow shape
  along jagged tips.
