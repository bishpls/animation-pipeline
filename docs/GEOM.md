# charkit.geom: the geometry kernel

A deterministic geometry layer for charkit, so the pipeline stops leaning on Blender's modifiers for geometry. Those
misbehave on our meshes: the Laplacian smooth modifier exploded a generated mesh into streaks, the voxel remesh tore thin
shells into lace, and EXACT booleans failed on bodies with internal cavities. The kernel runs venv-side (numpy, scipy,
scikit-image, numba, plus manifold3d for exact booleans). Its results (npz, ply, glb) go to the Blender stage, which reads
them with numpy alone (`charkit.geom.io`, `charkit.geom.blender`).

Every operation is a pure function of its input. Parallel kernels are per-query and independent, and every tie-break
is ordered, so reruns give the same bytes.

## Modules

| module | what |
|---|---|
| `mesh` | `Mesh(V, F, vc, vn, uv)`; face and vertex normals (angle-weighted), areas, signed volume, edges, boundary loops, parts, adjacency, `compact`, `concatenate`, `transform`, frame changes |
| `io` | `load`/`save` for .glb/.gltf, .ply (ascii and binary), .obj and .npz. glTF comes in with node transforms applied and the base-colour texture sampled to per-vertex sRGB colour (bilinear or nearest, times baseColorFactor and COLOR_0), turned z-up the way Blender's importer does it. `blender_compat=True` reproduces `i3d.load_glb`'s colours exactly (see "Findings") |
| `repair` | `merge_close`, `clean` (degenerate faces, duplicates, coincident opposite pairs), `orient` (consistent winding across manifold edges, then each part turned outward: closed parts by volume, open ones by winding number), `fill_holes`, `remove_small_parts`, `fix_self_intersections` (local relaxation), `cut_intersections` (cut out, refill, relax), `report` |
| `bvh` | `BVH(mesh)`: `nearest`, `signed_distance` (sign from the winding number, or from pseudo-normals), `winding_number` (Barill et al. fast dipole approximation), `contains`, `ray_cast`, `ray_count`, `ray_hits`. numba, parallel over queries |
| `volume` | `Grid` (world-lattice snapped, so grids with the same voxel size combine voxel for voxel): `occupancy` (winding number or 3-axis ray parity), `solid` (see below), `sdf` (exact near the surface, EDT far), `thicken` (a sheet to a closed solid), `to_mesh` (marching cubes: closed, manifold, wound outward), `union` / `intersection` / `difference`, `dilate` / `erode` / `opening` / `closing` / `blur`, `fill_cavities`, `keep_components`, `restrict` |
| `boolean` | `boolean(a, b, op)`: exact through manifold3d when both inputs are manifold, the volume path otherwise; reports which path it took |
| `smooth` | `taubin`, `laplacian`, `bilateral_normals` (Zheng et al. normal filtering with the Sun et al. vertex update), `smooth_normals`, `envelope_normals` |
| `remesh` | `isotropic(m, L)` (Botsch-Kobbelt: split, collapse, flip toward valence 6, tangential relaxation, projection back onto the input, colours carried); `decimate(m, faces)` (Garland-Heckbert quadrics). Both keep a closed manifold closed and manifold (link condition, valence and normal-flip checks) |
| `raster` | a numpy/numba z-buffer: orthographic `Frame`s round the character (qa3d's azimuth convention), `silhouette`, `iou`, `overlay`, `render` (flat, lambert or toon; `light_world=shade.LDIR` gives charkit's toon3 steps), `save_png`, `sheet` |
| `parts` | a part cut from a generated character aligned onto ours: `Case.load`, `extract`, `finish`, `hair`, `skirt`, `surface_parts`, `measure`, `render_sheet`, `save_part` |
| `blender` | inside Blender: `load_part` (a saved part as a mesh object), `normals_proxy` and `transfer_normals` (envelope normals that survive an inverted-hull outline) |
| `primitives` | icosphere, box, torus, cylinder and grid for tests and cutters |

`repair.report` returns `charkit.trace.health`'s fields under the same names, so kernel numbers and build-trace numbers
compare directly: open_edges, nonmanifold_edges, shells, closed_shells, inverted_shells, degenerate_faces, loose_verts
and area. It adds parts (= shells), nonmanifold_verts, misoriented_edges, boundary_loops, duplicate_faces, watertight,
volume / euler / genus, and a self-intersection estimate.

## The solid of a generated character

TRELLIS.2 outputs every surface as a hair-thin double wall. The head, the body, each lock and each piece of cloth is a
closed skin about 1 mm thick with nothing inside. The winding number sees only that skin. The shells are also open to
each other: the fringe hangs free in front of the forehead, the hair is a bell open at the bottom, and garments leave
gaps round the limbs. So a flood from outside reaches everywhere.

`volume.solid(m, grid, walls, seal)` voxelises the surface, adds `walls` (our body, grown by `clear`) as blockers, and
closes gaps narrower than 2 × seal against the flood. The flood runs through the blockers grown by `seal`, then grows
back by as much without crossing them. Everything the flood doesn't reach is solid. On the outer boundary the winding
number decides the voxels the surface passes through.

`solid_sdf` then gives a signed distance that is exact against the generated surface on the outside, so the part's outer
surface is the generated one at sub-voxel accuracy.

## Hair (`parts.hair`, `python -m charkit.geom extract SPEC --part hair`)

1. Align the generated character exactly as the Blender build does. `Case.load` resolves the spec the way
   `python -m charkit build` does (refs fit, then `scene.fit_cranium` with the numpy GLB reader), assembles our
   character (cached by the resolved spec's hash), finds the generated eyes (`i3d.find_eyes` on the i3d-compatible
   colours) and places them with `scene.eye_target`, now shared with `scene.hair_shape_volume`.
2. The generated solid, with our body grown by `clear` (0.012 L) as a wall. Seal 0.012 L everywhere, and 0.04 L in the
   cap (above the ears' middle, outside the face cone), so the mass sits on the scalp. The fringe and hanging locks keep
   their shapes.
3. Minus our grown body, within the region: above the chin minus the spec's `below`, with no sleeves beyond
   `shoulder_x` below the chin.
4. Colour: every voxel takes the colour of the generated surface nearest to it. Voxels that aren't hair-coloured go:
   skin, the collar, eyes and clips. The hair colour family is fitted to the generated crown (`hair_color`). This
   replaces `scene.cull_face`'s geometric face rule, which cuts the side locks flat in front of the cheeks. That rule
   is still available as `face=True`.
5. Poke-through cover: where our head pokes out through the generated hair, a 3 mm layer over our grown skin closes
   the hole. This happens where hair-coloured generated surface lies inside our body and nothing of the hair is left
   outside along that direction from the hair centre (2.5° bins, excluding the face cone, above the chin). On Clawd
   this closes the hole our cranium makes at the back of the head, and smaller ones at the temples.
6. Cleanup: thin remnants against the body are opened away, and below the chin only what hangs from above is kept (a
   slice-by-slice flood: the orange top under the chin and the sleeves go). Then the part holding the crown is kept,
   along with parts over 2 % of it, inner cavities are filled, and pits narrower than 3 mm are closed.
7. The signed distance is exact against the generated surface and our grown body where they bound the part, and
   voxel-smooth where a mask cuts.
8. `finish`: marching cubes (coincident opposite pairs dropped), Taubin 10, isotropic remesh at 2.5 h, Taubin 10,
   self-crossings relaxed or cut out and refilled.
9. Envelope normals: the part's solid, closed by 0.30 L, blurred by 0.25 L, and the gradient taken at every vertex.
   The toon ramp sees one soft mass.

Voxel h defaults to 0.006 L (1.5 mm on Clawd). One hair run takes about 45 s on the laptop, plus 15 s the first time
to assemble the character (cached after that).

## Skirt (`parts.skirt`, `--part skirt`)

Our legs don't match the generated pose, so subtracting our body would cut holes in the skirt. Garments are also
hair-thin double walls. So the skirt comes from the generated surface itself:

- Cut it to the band from the waist to mid-thigh. The band's top is searched for the cut that frees the most skirt.
- Split it into its own pieces by edge connectivity. The skirt panels come apart from the legs-and-shorts piece and
  from the hands.
- Drop the pieces that are 30 % or more skin, then the faces of the rest that hug a dropped piece: anything within
  0.05 L of the legs (shorts, tights).
- Thicken what is left into a solid 0.016 L thick with `volume.thicken`. That is an exact distance, so the result is
  closed.
- Finish as the hair does: remesh at 1.6 × the half-thickness, so no edge is longer than the cloth is thick and
  nothing folds across it, then quadric-decimate to 60 k faces.

`--skirt-bottom 0.6` extends the band toward the knees to take in the generated skirt's back tails.

## How the Blender stage consumes a part

`save_part` writes `PART.npz`:

- V: world metres, z up, the assembled character's rest pose.
- F: triangles.
- vn: the envelope normals.
- vn_geom: the geometric vertex normals.
- meta (JSON): the alignment, the extraction's numbers and the health report.

It also writes `PART.ply` (V, F, vn); `io.save(mesh, 'x.glb')` writes a GLB for three.js. The surface is closed and
manifold, so it needs no backface culling, remesh or smoothing in Blender.

```python
from charkit.geom.blender import load_part, normals_proxy, transfer_normals
ob, meta = load_part(path, 'hair_shape', material=m, normals=None)
shade.outline(ob, thick=0.0014, color=line)                 # the inverted hull first
transfer_normals(ob, normals_proxy(path, 'hair_shape_normals'))   # then the envelope normals, by transfer
```

Set custom normals *after* the outline. Solidify re-derives the corner normals of the surface it thickens. Custom normals
set on the mesh come out about 2° off on average, with 1 % of corners more than 24° off, which shows as a mottled
terminator. A Data Transfer after it keeps them within a degree.

The build already does this, opt-in. `python -m charkit build SPEC --hair geom` (or `hair.shape.mode: "geom"`) runs the
hair extraction venv-side into `OUT/geom/hair.npz`, cached by the resolved spec, the GLB and `parts.VERSION`.
`scene.hair_geom_mesh` then loads it with the hair look, the outline, the normals transfer and the head rig. The
analytic cap is not needed (`shape.cap` turns it back on), and the generated shape still places the accessories. The
default build is unchanged.

## Command line

```
python -m charkit.geom report MESH                     python -m charkit.geom remesh IN OUT --edge L
python -m charkit.geom repair IN OUT [--weld --holes]  python -m charkit.geom decimate IN OUT --faces N
python -m charkit.geom smooth IN OUT --taubin N        python -m charkit.geom voxel IN OUT --h H [--close R ...]
python -m charkit.geom thicken IN OUT --r R            python -m charkit.geom boolean A B OUT --op difference
python -m charkit.geom render IN OUT.png --az 0,90     python -m charkit.geom extract SPEC.json --part hair,skirt --glb PATH
```

Tests (36, about 10 s): `python -m pytest charkit/tests/geom`. `CHARKIT_GEOM_REAL=1` adds the real Clawd hair and skirt.

## Findings along the way

- `i3d.load_glb` gamma-encodes colours twice. Blender's `img.pixels` for an 8-bit sRGB PNG are already sRGB-encoded,
  and the function applies linear-to-sRGB again, so every colour it returns is brightened and washed out. On Clawd the
  skin's median saturation reads 0.21 instead of 0.41, and the hair's 0.63 instead of 0.88. The spec's colour knobs
  (`hue`, `sat`) were tuned on those numbers, so nothing was changed.
  `io.load_gltf(blender_compat=True)` reproduces them bit for bit (1e-7), and the kernel's own classes use the true
  colours.
- `scene.cull_face`'s upper rule, `p.y > face.y - clear`, has no depth limit. It drops every generated hair vertex behind
  the face surface in that height band within |x| < 0.3 L, and that includes the back hair there: on Clawd, all 155 of
  155 sampled hair-coloured vertices behind the head's centre in the band. This is probably why the mesh-mode build
  needs `hair_cap` as a backstop. `parts.face_cull` bounds the rule to the face's width and 0.15 L deep.
- qa3d's `hair_noise` read mostly Blender's dither. Renders are dithered by default, and ±0.5/255 of noise inside a flat
  toon tone splits it at a luminance percentile. The same hair measures 0.006 to 0.014 without dither and 0.19 to 0.73
  with it. qa3d's QA renders now turn dither off.
