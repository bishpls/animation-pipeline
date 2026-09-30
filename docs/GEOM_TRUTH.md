# Geometry truth: one implementation of the geometry

Michael approved this on 2026-09-30. It follows from process decision 5 ("trustworthy local loops", `docs/CHARKIT_HANDOFF.md`).
Workstream notes: `docs/workstreams/geom-truth.md`.

## Why

The numpy evaluator (`charkit.bodyeval`, which workstreams iterate with) and the Blender build compute the same geometry in
two places, and the two drift apart:

- tool/body's gate read the hems 0.024–0.028 L apart from its evaluator run, which cost several rounds;
- every new garment kind has to be added to two dispatches (`garments.build` and `bodyeval.garment_piece`), two material
  tables (`build`'s and `bodyeval.garment_tones`) and two thickness tables (`build`'s Solidify settings and
  `bodyeval.SOLID`). tool/garments2's template cuff and puff sleeve are edits to both copies.

Blender's bundled Python has no scipy either, so code that runs there carries numpy re-implementations (`_knn_mean`,
`_grow`, the union-find in `shell_patches`, `springs.nearest`, `springs.components`).

**The goal:** one implementation. Geometry is computed in the venv (charkit.geom and the builders) and saved as arrays.
Blender only instantiates meshes, materials, rigs and renders from them. The evaluator then becomes the build's own
geometry step, exact by construction.

## Where the geometry is computed today

Measured with `python -m charkit stagedrift` on clean builds of pipeline-3d 9397578. The evaluator ran on the build
box on the build's own spec, so every difference is the stage's own computation, on one machine. Both gate specs were
measured: `clawd.json` (code head and body) and `clawd_mh.json` (MakeHuman). Distances are in head lengths L (about
0.25 m). "f32" means equal once both sides are rounded to float32, as Blender stores them.

| stage | computed in Blender (its Python: numpy 2.3.4, no scipy) | computed in the venv (numpy 2.5.3, scipy) | in the evaluator (`bodyeval`) | drift, clawd / clawd_mh |
|---|---|---|---|---|
| resolve | — | `cli.resolve`: produced references, the design rig's fit, the style's look and eyes merged in | `bodyeval.resolve`: the same, without the style merge | not measured here (stagedrift gives the evaluator the build's spec); `evaldrift` covers it end to end |
| fit_cranium | `scene.fit_cranium`, the GLB read by Blender's glTF importer | `parts.Case.load` (the hair-pieces step), with charkit.geom's reader | `bodyeval.resolve`, charkit.geom's reader | none: 1.1 both (the fit clamps at 1.1) |
| character | `character.assemble`, all numpy: the body, the code head's wrap, eyes, mouth, brows and their keys. Then the mesh, UVs, groups, armature and shape keys | the code head's and body's sections (`head_code.npz`, `body_code.npz`); `Case.load` assembles again for the hair pieces | `assemble_cached` (venv; its cache key missed code_base and code_body); `compose()` for body knobs | assembly 9e-16 L, f32-identical / 1.8e-14 L, **18 of 13,380 vertices differ in f32** (numpy 2.3.4 against 2.5.3, same code). Eye and mouth parts 7e-7 L: Blender's float32 armature at rest |
| character, evaluated | Subdivision level 1, Armature, the garments' Mask | — | `bodyeval.subdivide` (a numpy port) | SKINEVAL |
| hair (pieces) | the pieces loaded from the venv's npz; `hair_shape_volume`: the GLB imported, the hair selected (mathutils BVH), culled off the face, giving the volume the accessories sit on and the QA's target | the pieces (`charkit.geom.hairpieces`) | **not modelled**: analytic locks (`hair.generate`) on a volume from a numpy port of the selection | **silhouette IoU 0.78 / 0.67 / 0.78** (front, side, back); 0.78 / 0.71 / 0.78 |
| accessories | `accessories.build` on Blender's volume | — | `accessories.generate` on the ported volume, plus the two buns the pieces carry (its carried filter left out 'pieces') | **no overlap at all** (star, crab); two extra buns |
| face shading | `faceshade.apply`: proxy normals, the SDF, fringe shadow and ink maps (numpy), then images and materials | — | none (shading only; the look checks read the bundle) | — |
| garments | `garments.hull_pieces` + `garments.build` (numpy), then materials, Solidify, Subdivision, the skin mask | — | a second dispatch (`garment_piece`), a second material table (`garment_tones`), a second thickness table (`SOLID`) | raw: all 18 f32-identical, mask identical / f32-identical except 10 top and 2 shorts vertices (shells on the body's 18); mask identical |
| garments, evaluated | Solidify, then Subdivision | — | `bodyeval.solidify` + `subdivide` | 4e-5 L or less, except **the hull puff sleeves, 0.008 L** (clawd): the port puts the shell on the wrong side |
| rig (tool/rig) | `rigstage.scene_rig` reads the live scene; `springs.plan` (numpy); `springs.rig` (bpy) | — | none | — |
| checks | — | `qa3d` on Blender's bundle | `bodymeasure` on the evaluator's own bundle | 55 of 106 differ / 45 of 106. Hair: hair_length 0.14–0.27 L, iou_hair 0.05–0.18, top 0.047–0.066. `sheet_*_chin` 0.025: the measure's anchor (bodymeasure's iris mean against qa3d's), not geometry. **The hems agree exactly.** |

What this says:

- **The hems no longer drift.** On one machine, on this commit, the evaluator's garments are the build's to float32, and
  every hem check agrees. The 0.024–0.028 L offset tool/body saw came from inputs, not from the two computations: the
  hull and outfit masks were hard-linked across worktrees and rebuilt through the links, box and laptop hulls differed
  before hull-det, and the evaluator's assembly cache didn't key on code_base or code_body. The garments agree by
  coincidence, though: two dispatches that happen to match today. The pilot makes it one.
- **The worst drift is the hair and the accessories.** The evaluator doesn't build the pieces the build uses, and puts
  the accessories on a different volume.
- **Across machines** (laptop evaluator, box build): the raw garments are f32-identical except the collar (133 vertices,
  4.8e-7 L).
- **The numpy versions differ** (Blender 2.3.4, venv 2.5.3), and it shows: 18 body vertices on the MakeHuman spec.
  Pinning the venv's numpy to Blender's would make stages that still run in Blender agree to the bit on one machine.
  It isn't worth it as a fix. It couples the venv to Blender's release cycle (Python 3.13 against the venv's 3.14), and
  hides rather than removes the duplicate. Once a stage is venv-side, Blender runs none of its numpy, and the versions
  stop mattering. Until the character stage moves, each build's trace reports the gap (`garments_body`, in nanometres).
- **Measurement is duplicated too.** `bodymeasure` re-implements qa3d's checks for the evaluator's bundle (the 0.025 L
  chin anchor). That's the QA side of the same problem. tool/infra's self-registering QA parts are the place to make
  it one.

## The interface

### Products

A stage's geometry is a **product**: one `.npz` per stage in the build's `geom/` folder (`OUT/geom/garments.npz`), with a
JSON record (`meta`) and named arrays. Its content is deterministic: the same inputs give the same bytes. No timings or
dates are stored in it; they go beside it (`garments.json`). The Blender stage's cache keys on that content.

Two kinds of product:

- **Recorded** (`charkit/geomstage.py`, schema `charkit.geomstage/1`). A builder that talks to Blender through a narrow seam
  is run venv-side with the seam recorded. The product is the ordered list of seam calls (`events`), with their arrays.
  Blender replays them through the real seam functions. This is how the garments work. It needs no change to the
  builders, which matters while several workstreams edit them.
- **Plain arrays** (what `head_code.npz`, `body_code.npz` and the hair pieces already are). The stage is split
  explicitly into `compute(spec, upstream) -> arrays` (venv) and `instantiate(S, arrays)` (Blender). This suits stages
  whose Blender side is broad (the character: UV layers per loop, shape keys, crease attributes, vertex groups).

Either way, a product carries what its consumers need to check it against. The garments product keeps the body it was
built on (`check/body`, float32), so the Blender side can report how far its own body is from it.

### The venv steps (`cli.build`)

Each stage's compute runs as a `charkit.cache.file_step` after `resolve`, in stage order: `code_head`, `code_body`,
`geom_hair`, `pieces_hair`, then `garments_geom`. The step is keyed on its code closure (two imports deep, plus the
modules it names), its explicit key (the resolved spec it's given), the content of its inputs and every file it opened.
It writes the product and points the resolved spec at it (`spec['garments_geom']`). A step that is restored copies its
files back; one that reruns and makes the same bytes leaves the Blender stage's cache hitting.

The venv steps share one assembly: `geomstage.assemble(spec)` memoises `character.assemble` on disk, keyed by the spec
without the outfit, the content of the code head and body files, and the assembly's code closure
(`charkit.cache.code_units`). The evaluator uses the same memo (`bodyeval.assemble_cached`).

### The Blender stages (`scene.STAGES`)

A stage whose spec names a product loads it and instantiates. `scene.stage_garments` replays `spec['garments_geom']`.
Without the key, the old in-Blender path runs (the Blender-side dump for `bodyeval --validate`, older specs, and
`CHARKIT_GARMENTS=blender`). The stage cache (`charkit.cache.Cache.stage`) keys the product by content, since it is a
path named in a spec section the stage read, and keys the skin and armature by structure (`scene.DEPS`).

### The evaluator

`bodyeval.Evaluator.geometry` calls the same compute functions in-process, per piece where a fit needs speed, and keeps
its caches. For the garments, `bodyeval.garment_piece` records `garments.build` for one garment spec and reads the
recording back as a `Part`: its mesh, the tones its materials render unlit (a textured toon sampled as Blender's byte
image holds the texture), and its Solidify thickness. Its second dispatch and its tone and thickness tables are gone.
Per-piece recordings compose to the build's whole recording (one object per garment spec; the skin mask is the union of
each piece's), so a fit's cache granularity is unchanged.

### Recording a builder: the seam

`garments.build` talks to Blender only through these calls:

| call | recorded as |
|---|---|
| `garments._object(name, verts, faces, weights, arm, mats, uv=, uv_corner=, mat_idx=, smooth=)` | a mesh object: its arrays |
| `garments._toon(name, color, shade_mul)`, `garments._toon_tex(name, image, shade_mul)` | a material |
| `eyetex.to_blender_image(name, rgba)` | an image (float32, as Blender takes it; shared by content) |
| `shade.outline(ob, thick=, color=, name=)` | the outline's call |
| `garments.mask_skin(skin, hide)` | the skin mask (the union of what the garments hide) |
| `ob.modifiers.new(name, type)` and settings on it; `ob[key] = value` | a modifier, its settings; a custom property |

`geomstage.recording()` swaps these for recorders while `build()` runs venv-side. Anything else build() asks of Blender
raises `SeamError` naming it (`ob.data`, `modifiers.find`, the skin's groups), so an owner who adds a Blender call finds
out at once, in `charkit/tests/test_geomstage.py` or the build's venv step. The fix is to route it through a seam function
or keep it out of build(). The replay makes the real calls in the recorded order with the recorded values, so Blender
ends up with the same datablocks build() would have made, including materials build() makes and then replaces.

### Drift monitoring

- `python -m charkit stagedrift BUILD` runs the evaluator on a build's own spec (the bundle's) and compares every stage
  object by object: the assembly, eye and mouth parts, landmarks, hair, accessories, garments (raw and evaluated), the
  skin mask, and the checks the evaluator measures (body, palette, sheet). It writes `BUILD/stagedrift/drift.md` and
  `drift.json`. It is a stand-in for tool/infra's `charkit evaldrift`, and should fold into it.
- Every build notes `garments_body` in its trace: the largest distance between the body the garments product was built on
  (venv) and Blender's own assembly. It is 0 when the character stage agrees. Until the character stage moves, this is
  the standing test for its drift.

### Produced references

The hull, the outfit masks and the hair layers stay as they are (`manifest.produced`: stamped, shared through the
produced cache). They are inputs of venv steps only. After the pilot, the garments' Blender stage no longer reads
`hull.npz`. The venv step reads it, and the step's file record keys it by content.

### The rig and the springs

tool/rig's `rigstage.stage_rig` runs after the garments. `scene_rig(S)` reads the live Blender scene: the armature's rest
frames (`gltf.skeleton`), every rigged mesh's world vertices, normals, triangles and vertex-group weights. It then plans
the spring chains (`springs.plan`, numpy) and adds their bones and groups (`springs.rig`, bpy). Under geometry truth:

- the plan's inputs come from the products: the skin and joints from the character product, the hair pieces, and the
  garments with their weights as Blender stores them (`_object` rounds them to 3 decimals and drops those at or under
  1e-4, so the venv reads the product the same way);
- the armature's rest frames come from the character product. They are computed venv-side with `body.build_armature`'s
  roll convention, and Blender checks its edit bones against them, as the garments check the body;
- `springs.plan` runs venv-side into a rig product: the bones (head, tail, roll, parent) and, per object, the new
  groups' weights. Blender's rig stage only adds bones and groups (`springs.rig`'s bpy half). scipy becomes available to
  the plan, so `springs.nearest` and `springs.components` can use cKDTree and csgraph;
- the evaluator can then plan the springs too, so motion QA runs without Blender.

### Modifiers and the evaluated meshes

The QA reads Blender's evaluated meshes: Subdivision Surface (skin level 1 in the viewport, 2 at render; garments 1),
Solidify (garment thickness and the outlines), Armature and Mask. The evaluator ports them to numpy
(`bodyeval.subdivide`, `solidify`, `limit_positions`), and the residual is measured separately from the stages' drift
(stagedrift's `evaluated` column). Two ways to close it:

- keep Blender as the truth for evaluated meshes, and hold the ports to a measured tolerance;
- or own it: bake Solidify venv-side (it's an offset along normals plus a rim), make `bodyeval.subdivide` match
  OpenSubdiv's limit rules, and let the QA measure a venv-made bundle, with Blender's subdivision used only for the
  render.

The second is the more ambitious option. It makes the whole QA venv-side (tune and gate without Blender), but it needs
the port exact first.

### What stays in Blender

Materials and shader nodes, images, objects, modifiers, armature and bone objects, constraints, the render (EEVEE), and
the VRM/glTF export, which reads the instantiated scene.

## The pilot: the garments

PILOT

## Rollout

ROLLOUT

## Open questions

OPEN
