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
| garments, evaluated | Solidify, then Subdivision | — | `bodyeval.solidify` + `subdivide` | 4e-5 L or less, except **the hull puff sleeves, 0.008 L** (clawd): the port winds them opposite to Blender, so the shell goes on the wrong side |
| rig (tool/rig) | `rigstage.scene_rig` reads the live scene; `springs.plan` (numpy); `springs.rig` (bpy) | — | none | — |
| checks | — | `qa3d` on Blender's bundle | `bodymeasure` on the evaluator's own bundle | 55 of 106 differ / 45 of 106. Hair: hair_length 0.14–0.27 L, iou_hair 0.05–0.18, top 0.047–0.066. `sheet_*_chin` 0.025: the measure's anchor (bodymeasure's iris mean against qa3d's), not geometry. **The hems agree exactly.** |

What this says:

- **The hems no longer drift.** On one machine, on this commit, the evaluator's garments are the build's to float32, and
  every hem check agrees. The 0.024–0.028 L offset tool/body saw didn't recur (its notes say so too). It most likely came
  from inputs rather than from the two computations. At the time, the hull and outfit masks were hard-linked across
  worktrees and rebuilt through the links, box and laptop hulls differed before hull-det, and the evaluator's assembly
  cache didn't key on code_base or code_body. None of these can be re-run now to confirm. Even so, the garments agree
  only by coincidence today: two dispatches that happen to match. The pilot makes them one.
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

The inventory put the garments' raw geometry already equal on one machine. The build and the evaluator agreed there by
coincidence: two dispatches, two material tables and two thickness tables, which happened to match. The worst drift
was the hair: the evaluator didn't build the pieces the build uses. The pilot does both, and changes no shapes. Only
where the computation runs moves.

**Garments (one implementation).**
- `charkit/geomstage.py` records `garments.build` venv-side through its seam and saves the product
  (`OUT/geom/garments.npz`, 0.8–1 MB). The venv step is `cli.garments_geom`, a cached file_step after `pieces_hair`.
- `scene.stage_garments` replays the product when the resolved spec names it (`garments_geom`).
- `bodyeval.garment_piece` records `garments.build` for one garment and reads it back. The second dispatch and both
  tables are gone from bodyeval, and `garments.py` changes by one extracted function (`mask_skin`, build()'s last
  seven lines).

**Hair (the evaluator reads the build's product).**
- `bodyeval.Evaluator.hair_parts` in mode 'pieces' reads the pieces from the build's product (`shape['pieces']`), or
  makes them with the build's own step (`cli.pieces_hair`) when a spec has none.
- Its carried filter now includes 'pieces', as `scene.stage_hair`'s does.

**The shared assembly.** `geomstage.assemble` memoises `character.assemble` for the venv steps and the evaluator.
`bodyeval.assemble_cached` now keys on the assembly's code closure: its old key listed nine modules by hand.

**Before and after** (build box; before = pipeline-3d 9397578 with the old evaluator, after = this branch; stagedrift
on each build's own spec; boarddiff between the before and after builds):

| | clawd before | clawd after | clawd_mh before | clawd_mh after |
|---|---|---|---|---|
| garments raw, f32-identical | 18 of 18 pieces | 18 of 18 | 17 of 19 (top 888/898, shorts 384/386) | **19 of 19**, by construction |
| hair pieces | not modelled; IoU 0.78 / 0.67 / 0.78 | **f32-identical; IoU 1.0** | not modelled; IoU 0.78 / 0.71 / 0.78 | **f32-identical; IoU 1.0** |
| accessories | no overlap, 2 extra buns | **7e-7 L; IoU 1.0** | no overlap, 2 extra buns | **7.6e-7 L; IoU 1.0** |
| QA target | — | identical (1e-16 L) | — | identical (2e-16 L) |
| checks that differ, evaluator against build | 55 of 106 | **29** | 45 of 106 | **8** |
| boarddiff, before build against after build | | **16 QA images identical, 294 checks identical** | | **16 QA images identical, 292 checks identical** |
| `garments_body` (venv body against Blender's) | | 0 nm, 18,478 of 18,478 f32-equal | | 18 of 13,380 vertices differ (numpy) |

The checks still differing come from elsewhere:
- the face sheet measures' anchor (`sheet_*_chin`, 0.025 L): bodymeasure against qa3d, rollout step 8;
- the arms' angle (INFO);
- the sleeves' evaluated shell (0.008–0.01): the winding port, step 7;
- palette shades (up to 0.05 ΔE);
- hundredths on IoUs.

**Cost.**
- Blender's garments stage fell from 11.5 s to 5.7 s (clawd); it now only replays.
- The venv step costs 10.6 s of garments plus an assembly when the memo misses. The assembly is 81 s on the box for
  the code head, which the build now does three times (the pieces step, the garments step and Blender) until step 3.
- A rebuild in the same copy hits the memo. A gate's fresh clone doesn't.

## Rollout

Each step merges on its own, gated as usual (`charkit remote gate BRANCH --into pipeline-3d`, both specs). Its exit
test is the same every time: stagedrift (or `evaldrift --stages`, once folded) shows the stage exact on one machine,
boarddiff shows the QA unchanged except where the old evaluator was wrong, and the stage's Blender side reads a product.
Owners come from `docs/OWNERSHIP.md`.

| # | stage | owner(s) | what moves | exit test | when |
|---|---|---|---|---|---|
| 1 | garments, and the hair pieces in the evaluator | integrator (this branch); skirt, garments2 affected | the pilot (below) | done: garments f32-identical by construction, hair identical | now |
| 2 | resolve and fit_cranium | integrator / infra (`cli.py`, `scene.py`, `bodyeval.resolve`) | one resolve for the build and the evaluator (the evaluator's lacks the style merge); `fit_cranium` run once venv-side and written into the resolved spec (Blender's becomes a no-op; measured equal) | evaldrift: no difference traced to resolve | small; any time |
| 3 | character | integrator for the split; face (tool/face: `code_base.py`), mouth (expression keys), eyes | `character.build` split into `character.arrays(A, spec)` (venv: UVs per loop, face UVs, crease pairs, outline weights, group weights, shape-key offsets, eye and mouth parts, material descriptors) and `character.instantiate` (Blender). Every venv step and the evaluator share one assembly; Blender's 46 s character stage becomes a load | assembly f32-identical on both specs (mh's 18 vertices); `garments_body` 0 by construction; face checks unchanged | after tool/face's jaw round merges (the split touches `character.py`, not `code_base.py`) |
| 4 | hair volume, QA target, accessories | hair (tool/hair3) with accessories (tool/accessories) | `scene.hair_shape_volume` venv-side: the GLB through `geom.io`'s Blender-compatible reader (the target is already identical to 1e-16 L), the selection through charkit.geom's BVH instead of mathutils (measure it equal first); `accessories.generate` venv-side (recorded like the garments, or split) | accessories f32-identical (7e-7 L now), target identical, hair checks unchanged | hair3's next round |
| 5 | rig and springs | rig (tool/rig), motion (tool/motion: `springs.py`) | `rigstage.scene_rig` built from products, not the live scene (weights read as `_object` stores them: 3 decimals, over 1e-4); `springs.plan` venv-side (scipy for `nearest` and `components`); a rig product; Blender adds bones and groups only. Rest frames from the character product | the springs plan identical to the in-Blender plan on both specs; motion QA unchanged | after 3, and after tool/rig's R1–R6 gate |
| 6 | face shading | look (tool/look2: `faceshade.py`) | the SDF, fringe shadow, ink maps and proxy normals venv-side; Blender makes the images and the transfer | the bundle's images and corner normals identical; look checks unchanged | when look2 resumes |
| 7 | evaluated meshes | integrator, with body and garments | fix the shell side on the hull puff sleeves (0.008 L now). `bodyeval.recalc_normals`, the port of
`bmesh.ops.recalc_face_normals` that `_object` runs, winds them opposite to Blender: 0 of 1,856 polygons agree, against
100% on every other piece. The bundle's `raw` loops hold Blender's winding, so a test can compare the two per piece.
The exact fix is to decide the winding venv-side and pass it through, instead of re-deriving it in Blender; then choose: Blender stays the truth for evaluated meshes (ports held to a tolerance), or the subdivision and Solidify move venv-side and the QA measures a venv-made bundle | evaluated garments within 1e-5 L; the skin's subdivision residual bounded | 7a now (small); 7b a decision for Michael |
| 8 | measurement | infra (evaldrift, the QA registry) | one implementation per check: `bodymeasure` re-implements qa3d's (the 0.025 L chin anchor); stagedrift folded into `evaldrift --stages` | evaldrift: no check drifts on a build's own spec | after tool/infra merges |

While a stage waits, its owners work as they do now. The only rule the pilot adds is for `garments.build`: Blender
calls go through the seam. tool/garments2's template cuff and puff sleeve already do (`_object`, `_toon`,
`modifiers.new`). Its two hunks in `bodyeval.garment_piece` are dropped at merge, because the recording covers the new
kinds. When a stage moves, its numpy stand-ins for scipy (`_knn_mean`, `_grow`, the union-find in `shell_patches`,
`springs.nearest`) can go, at their owners' pace.

## Open questions

- **`CHARKIT_GARMENTS=blender`** keeps the old in-Blender garments path for one round, as a fallback and for A/B
  checks. Remove it once gates have run on the product path.
- **The garments step's cost.** It assembles the character venv-side: 37 s on the laptop, about 68 s on the box for the
  code head, unless the memo has it. The memo is per copy, and a gate's fresh clone assembles once per build. Step 3
  removes the duplicate outright.
- **Cross-machine.** The code head's assembly differs by up to 0.0027 L on 1,726 vertices between laptop (ARM) and box
  (x86), and it reaches the collar. Laptop loops against box gates will see it until `code_base.wrap` is made
  deterministic, as hull-det did for the hull (face owner), or until evaluations run on the box.
- **The flap cache key.** The evaluator's per-piece cache keys a flap by its own spec, not the skirt it hangs from
  (garments.md's gotcha). The recording doesn't change this. A key that includes the specs build() reads through
  `spec_all` would close it, at some cost in cache hits during fits.
- **Tones.** The evaluator now samples textures as Blender's byte image stores them, a tone change of under 1/255 from
  before.
- **Numpy pinning:** not worth it (above).
