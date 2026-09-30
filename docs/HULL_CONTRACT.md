# Hull contract

**Contract version: 1** (`charkit.geom.hull.CONTRACT`; the sidecar's `"contract"`; a sidecar without the field is 1).

What `charkit.geom.hull.build` produces, and what a consumer may rely on. Pin to it with
`hull.contract_of(sidecar) == 1`, where `sidecar` is the dict or the path of `hull.glb.json`. The code is the authority
for details: `charkit/geom/hull.py`, `garments.shell_points`, `manifest.stamp`.

## Where it is

Get the hull through `manifest.produced(spec, 'hull')`, never by a fixed path. It builds or restores the hull when it's
missing or stale, and returns `charkit/out/hull/NAME/hull.glb`. The other files sit beside it. The spec's
`hair.shape.glb` points at the same file.

## Frame and units

- **Units:** L, the design's head length.
- **Axes:** x toward her left, −y toward the viewer (she faces −y), z up.
- **Origin:** x = 0 is the front view's midline. z = 0 is the eye line. The y origin is arbitrary, because the profile's
  axis only slides the figure along y.
- **Alignment:** align to anything else by the eyes, which are in the sidecar (`i3d.glb_eyes`, `i3d.align_by_eyes`).
- **Mesh files:** `hull.glb` is stored y-up. `charkit.geom.io.load` returns it in this frame, and `hull.ply` is already in
  this frame.
- **Grid:** voxel centres on axes `xs` and `ys` (ascending) and `zs` (descending: the z index runs down), spacing `h` =
  0.01 L (0.005 L for a head sheet).
- **What varies per build:** the grid's origin and extent come from the sheet's calibration. Don't hard-code them, and
  don't hard-code the grid's shape.

## Files

| file | contents |
|---|---|
| `hull.npz` | `V` bool (nx, ny, nz): the occupancy. `xs`, `ys`, `zs` float64: the axes. `shell` int16 (n, 3): the shell voxels' indices (ix, iy, iz), in `np.nonzero` order. `shell_label` int32 (n,): their labels. A shell voxel is occupied and has at least one empty 6-neighbour; outside the grid counts as empty. |
| `hull.glb.json` | The sidecar. `eyes`: [[+x, y_e, 0], [−x, y_e, 0]], her left eye first, exact. `units` "L". `by` "charkit.geom.hull". `contract`. `labels` and `pieces`: the per-vertex arrays' file names. `piece_names` {str(label): name}. |
| `hull.ply`, `hull.glb` | The same mesh: marching cubes on `V` blurred 1 voxel, positions snapped to 2^-20 L, decimated to 150,000 faces. Vertex colours come from the view facing each vertex. |
| `hull_labels.npy` | int16, one per mesh vertex: the `bodyqa.CLASS` code (0-10) the facing view draws there. |
| `hull_pieces.npy` | int16, one per mesh vertex: the label of the nearest shell voxel. |
| `hull.json` | A report: calibration, scores, mesh health, seconds. **Not part of the contract.** |

- The per-vertex arrays follow the mesh's vertex order as `geom.io.load` reads either mesh file.
- `hull_pieces.npy`, `piece_names`, `shell` and `shell_label` exist only for a body sheet with the outfit's masks.
- A head-sheet hull (`--head`) has the mesh files, `hull_labels.npy`, the sidecar, and `hull.npz` with `V` and the axes
  only. It stops at z −0.66.

## Labels (`shell_label`, `hull_pieces.npy`)

| code | meaning |
|---|---|
| 1 … n | Piece k + 1 is `outfit_graph.json`'s `pieces[k]`, the graph the masks were cut with; it sits beside `outfit_masks.npz`. |
| 1000 + c | `FREE` + class: no piece drawn there, and `c` is the drawing's `bodyqa.CLASS` (1001 skin, 1002 hair, 1003 iris, 1004 line, 1006 orange, 1007 cream, 1008 dark, 1009 white, 1010 other). |
| 0 | none |

- **How a shell voxel is labelled:** it takes the label of the view that faces it most squarely among those that see it.
  The views are front, back, profile, three-quarter and the extra views that carry pieces.
- **The far side:** it is labelled from the profile's and three-quarter's mirror images, with pieces swapped left for
  right (their `pair` and `side` in the graph).
- **Voxels no view sees** (undersides, between the legs) copy the nearest seen voxel's label. They are guesses, not
  observations.
- **Names:** `piece_names` covers the labels present on the mesh's vertices. A shell label missing from it (a patch the
  decimation lost) is named by the rule above (`hull.Pieces.name`).
- **Limbs are not an output.** The limb split (body, arm, leg and free skin, per view) only shapes `V`. A piece's limb is
  `hull.limb_of` of its `attach.bone` in the graph. Free skin (1001) carries no limb.

## Guarantees

- **Determinism:** the same code and inputs give bit-identical outputs on the build box (x86 AVX-512), the render box
  (AVX2) and the laptop (arm64). This covers every file above except `hull.json`.
  - Checked with `python -m charkit.geom hull SPEC --fast --stages DIR`. Its `stages.json` holds the sha256 of every
    stage's arrays and of the outputs.
  - One intermediate differs by machine: `code_base.head_sections`, the authored head's sections. It doesn't reach the
    outputs.
  - Numerics that feed discrete choices go through `charkit.geom.det`.
- **Stamp** (`hull.glb.stamp`, parts in `.stamp.json`). It covers:
  - `hull.build`'s code, one import deep;
  - its manifest entry;
  - the manifest's tracked references' sha256s;
  - what it reads: `outfit_masks` by stamp, and the body and head turnarounds and `head_construction` by entry;
  - the spec sections `name`, `ref`, `style` and `eyes.x`.

  Nothing else in the spec rebuilds it: body, face and garment knobs don't. Two copies with one stamp hold the same
  bytes.
- **Shared cache:** the key is `hull/STAMP-CODE2`. CODE2 is:
  - the producer's code, two imports deep;
  - the CODE2 of the masks;
  - Python, numpy, the machine and the OS.

  A hit is copied back and checked by sha256.

## What consumers may and may not rely on

**May rely on:**
- the files, keys, dtypes, frame, units, eyes and label codes above;
- the shell as the surface sample: one point per surface voxel, uniform in area, labelled. `garments.shell_points` puts
  each point on the occupancy's boundary; garments and the body's garment fits read it (`garments.hull_pieces`);
- `V` as the design's envelope: inside every view's silhouette;
- equal bytes for equal stamps, on any machine.

**May not rely on:**
- **Decimated vertices as samples.** Their positions, count, order and density move with any shape change. Use the
  mesh for display, the hair mass's surface, and alignment by the eyes.
  - Current mesh readers: `code_body` (`hull.ply` + `hull_pieces.npy`); `hairpieces`' flyaway planes (`hull_labels`);
    `bundle.target_pieces`.
  - They work, but a decimation change moves them. Move them to the shell when they're next touched.
- **Piece label numbers.** They follow the graph's order and change when the graph does, so map them by name. `FREE`
  (1000) and the `CLASS` codes are fixed.
- **The grid's origin, extent or shape, and y = 0.**
- **Labels on unseen or mirrored surface as measurements** (see Labels).
- **The shape staying put.** Every hull fix moves it. Shape changes are gated by the QA, not versioned here.
- **Diagnostics:** `hull.json`, the review page and `--stages` intermediates (limb images, sections, LimbTrack sources,
  Owners' changes). They change without a version bump.

## Changing it

**Breaking changes need a bump:**
- a file or key removed or renamed;
- an array's dtype, shape, order or indexing changed;
- the frame, units or eye convention changed;
- a label code or the piece numbering rule changed;
- what the shell is, or what a label means, changed.

**Not breaking:** new files or keys, new pieces or classes (names are looked up), shape changes, diagnostics.

**A breaking change, in one commit:**
1. Raise `CONTRACT` in `charkit/geom/hull.py`.
2. Update this file: the version line, and a changelog entry saying what changed and how to migrate.
3. Update every in-tree reader (`grep -rn "hull.npz\|hull_pieces\|hull_labels\|hull.glb" charkit`), or make it check
   `contract_of` and refuse.
4. Register a `charkit/history.py` step for any QA check whose measurement moves because of the format (not the shape).
5. Gate on both specs.

The code change changes the stamp, so every copy rebuilds. Where it's cheap, keep reading the old version for one
integration round.

## Changelog

- 1 (2026-09-30, tool/hull-limbs): the first written contract. It describes the outputs as they were since the labelled
  shell (tool/garment-sampling) and hull-det; the `contract` field is new.
