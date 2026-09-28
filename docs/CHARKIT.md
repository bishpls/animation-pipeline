# charkit: a parametric anime character kit in code

A base to build every 3D character from: one detailed, rigged anime body and head with the components to tune every feature,
driven by a character spec. Nothing like it exists in the open: the parametric engines (VRoid Studio for anime; Character
Creator, MetaHuman and Daz for realistic humans) are closed, and the open ones (MakeHuman/MPFB2, NAVER's Anny) are realistic.
The generative services (Tripo, Meshy, Rodin, Hunyuan) are learned models, not templates. So we build one, and it is a
reusable asset. The quality bar is HoYoverse-style 3D (Genshin, Honkai Star Rail): see docs/PIPELINE_3D.md and the review
boards below. Clawd (projects/clawd3d) is the first character rebuilt from it; a second character proves the reuse.

## 1. What a character is

`build(spec) -> a .blend (and a VRM/glTF)`, deterministic. The spec is one JSON file:

```json
{
  "name": "clawd",
  "refs": {"front": "…/base.png", "views": ["…/head_left_1.png"], "palette_from": "…/base.png"},
  "body": {"sex": 0.0, "age": 0.35, "muscle": 0.4, "weight": 0.45, "height_m": 1.55, "heads_tall": 6.4,
           "proportions": {"leg": 1.10, "torso": 0.95, "shoulder": 0.88, "hip": 1.0, "bust": 0.35, "hand": 0.9, "foot": 0.9,
                           "neck_len": 0.85, "neck_w": 0.85, "limb_slim": 0.85}},
  "head": {"width": 1.0, "cranium": 1.0, "face_len": 0.95, "jaw_w": 0.9, "chin": 0.7, "cheek": 0.6, "flat": 0.7,
           "eye_y": 0.0, "eye_gap": 1.0, "eye_scale": 1.1, "eye_tilt": 3.0, "nose": 0.4, "mouth_w": 0.9, "mouth_y": 0.0,
           "brow_y": 0.0, "ear": 0.8},
  "face": {"art": "…/rig/clawd/build", "eyes": ["open","half","closed","happy","surprised","determined","soft","wink"],
           "mouths": "visemes15", "brows": "drawn"},
  "hair": {"preset": "wavy_bob", "buns": "claw_blocks", "ahoge": 1, "length": 0.9, "volume": 1.25, "wave": 0.6,
           "bangs": {"style": "swept", "part": 0.2, "length": 0.8, "gaps": 0.5}, "colors": ["#e8825a", "#c65c42"]},
  "outfit": [{"type": "skirt_aline", "pleats": 10, "hem": "pixel_steps", "…": "…"}, {"type": "jacket_crop", "…": "…"}],
  "palette": {"skin": "#fddbc4", "…": "…"},
  "paint": {"views": "generated", "style": "the reference sheet's"}
}
```

Every number is a knob with a documented range and default (the defaults are a neutral anime heroine). Knobs live with the
component that reads them; `charkit/spec/schema.json` collects them.

## 2. Components

| component | what it builds | the knobs | built from |
|---|---|---|---|
| **body** (`charkit/body.py`) | the body mesh with hands and feet, UVs, a VRM 1.0 humanoid skeleton (fingers included) and skin weights | sex, age, muscle, weight, height, heads tall; per-segment proportions (legs, torso, shoulders, hips, bust, hands, feet, neck, limb slimness) | the MakeHuman base mesh (CC0: 13,380-vertex all-quad body, 125 joint markers, default skeleton and weights) + its macro targets (CC0), then our anime stylisation: segment scaling along the skeleton, limb slimming, joint smoothing, the realistic head removed at a fixed neck ring |
| **head** (`charkit/head.py`) | the anime head: a quad cage with artist topology (two loops round each eye opening, two round the mouth, a jaw line, cheek and nasolabial flow, the cranium), subdivided; the neck ring welds to the body's | width, cranium height, face length, jaw width, chin point, cheek fullness, face flatness, eye height, spacing, scale and tilt, nose size, mouth width and height, brow height, ear size | landmarks (about 60) placed by the knobs, fitted to the reference's drawn face contour (front) and a generated profile |
| **face features** (`charkit/face.py`) | eyes on a shaped eye plate: white, iris (gaze), fixed shine, lashes and lids (strips with shape keys for blink and expressions); the mouth with a cavity, teeth and tongue and viseme shape keys, the lip line in UV space; brows on their own strips drawn over the hair; the VRM expression set (aa ih ou ee oh, blink, happy, angry, sad, relaxed, surprised) plus the character's own | eye style (shape, iris size, lash weight), expressions from drawn variants, mouth shapes | the character's drawn face art (like faces.py today), cut and registered |
| **hair** (`charkit/hair.py`) | a hair volume fitted to the reference silhouette; lens-section clumps in layers from a part and crown, bangs, side locks, back mass, buns and accessories as parametric pieces; spring chains for secondary motion | preset, length, volume, wave, curl, bangs (style, part, length, gaps), clump count and width, tip shape | a clump library + presets |
| **garments** (`charkit/garments.py`) | outfit pieces as templates fitted to the body (offset surfaces, then shaped): skirts (A-line, pleated, layered), jackets, blouses, sleeves (puff, fitted), collars (sailor, stand), bows and ribbons, cuffs, boots, gloves, shorts, tights; weights transferred from the body; springs on loose parts | per piece | templates + the body |
| **materials** (`charkit/shading.py`) | the shader stack: three-tone ramps from ramp textures, the SDF face shadow, hair with gradient, strand strokes and highlight, rim light, coloured outlines with per-vertex width, the forehead hair shadow, inner-line and feature passes for post | palette, ramp softness, outline width | kit.py's shaders, promoted |
| **paint** (`charkit/paint.py`) | painted textures: GPT Image paints matching views of the character (front, both three-quarters, profile, back; head close-ups), which are projected onto the UVs from calibrated cameras and blended by facing, then baked: skin gradients, blush, lip tint, eye-white shading, hair gradients and strands, cloth detail | which views, style prompt | tools/gptimage.py + Blender projection bake |
| **geometry** (`charkit/geom/`, docs/GEOM.md) | deterministic mesh operations venv-side instead of Blender's modifiers: repair, voxel solids and booleans, remeshing, smoothing, envelope normals; a generated character's hair or skirt cut into one closed surface for the Blender stage | voxel size, clearance, seal, colour family, envelope blur | numpy, scipy, scikit-image, numba, manifold3d |
| **export and QA** (`charkit/qa.py`, `export.py`) | boards: turntable, head close-up turntable, expression sheet, viseme sheet, a lighting sweep, range of motion, overlay on the reference, topology stats; VRM 1.0 / glTF export for three.js | | |

### The base mesh: `spec['base']`

Two bases build the same character (`python -m charkit build SPEC.json --base anime`, or `"base": "anime"` in the spec):

- **`makehuman`** (the default): MakeHuman's own realistic head wrapped onto the anime head on every build
  (`charkit/anime_head.reshape`), its eye margins, mouth corners and cavities detected in the realistic topology each time.
- **`anime`**: charkit's own anime base (`charkit/base_anime.py`, asset `charkit/assets/base_anime/base_anime.npz`, 0.6 MB,
  CC0): derived once from MakeHuman through the neutral anime wrap and cleaned for anime use: shallow eye sockets behind the
  plates instead of the realistic pockets, the lid rings round each opening re-laid into clean concentric loops (the wrap
  folds them back over the big anime outline), a compact mouth cavity and flattened lip rolls, the nostrils cut out and
  filled (a soft nose), the ears' folds flattened, the under-jaw/neck junction filleted. It stores its regions (face,
  scalp, neck, ears, nose, lips, jaw, under_jaw, eye margins, sockets and lids, the mouth's loop and cavity), the eye and
  mouth loops with their outer rings and the socket and cavity schedules, landmarks, joints, weights, UVs, and each vertex's
  source vertex in hm08. A build takes the body from MakeHuman's macro targets as before (same vertex indices), re-wraps
  the stored head to the spec's head knobs (`anime_head.rewrap`), and places the eyes and mouth from the stored labels
  (`eyes.labels`, `mouth.labels`): nothing is re-detected. The joints follow the wrap as on `makehuman` (the removed realistic
  interior is stored as ghost points they follow), so garments fitted along the bones fit the same. Re-derive after changing
  the wrap or the cleaning:
  `python -m charkit.base_anime derive`. The QA check `face_folds` counts folded skin round the openings at rest and under
  every lid and mouth key (Clawd: 1014 on `makehuman`, 135 on `anime`).

## 3. Build flow

```
spec -> body (MakeHuman base + targets + stylise + skeleton + weights)
     -> head (landmarks -> cage -> topology -> fit to the refs -> weld at the neck)
     -> face features (eye plates, lids and lashes, mouth, brows, shape keys, expressions)
     -> hair (volume fit -> clumps -> springs)
     -> garments (templates -> fit -> weights -> springs)
     -> materials (+ paint: generate views -> project -> bake)
     -> QA boards; export
```

Each stage is its own module with a function that takes the spec and the scene so far, so a stage can be rebuilt alone,
and each writes its review board, looked at before the next is trusted.

## 4. Measurement and review (the quality gate)

Numbers first, pictures second. `python -m charkit build` writes two records into the output folder:

- **`trace.jsonl`, the build's state log** (`charkit/trace.py`). This is the Dolphin game-state log of the character. After every
  stage it records each object the stage added, changed or removed: counts, world bbox, a geometry hash, and mesh health
  (open and non-manifold edges, shells, inside-out shells, degenerate faces, loose verts, measured on the evaluated mesh
  without the outline hull). It also records the landmarks, hashes of the spec sections the stage read, and timings for every
  stage, board and the QA pass. Stages add their own values with `trace.note(...)`.
  - `python -m charkit trace OUT/trace.jsonl` prints it as a table per stage.
  - `python -m charkit trace A/trace.jsonl B/trace.jsonl` prints what changed between two builds: knob sections, landmarks
    moved, per-object geometry and health, stage times and QA values. Two builds of the same spec should print
    `no differences` apart from the QA section.
- **`qa/qa.json`, the graded checks** (`charkit/qa3d.py`: PASS, WARN or FAIL against `LIMITS`, with overlays):
  - silhouette IoU against the generated shape, overall and per band;
  - IoU against the reference image;
  - scalp showing through the hair;
  - garment poke-through;
  - hair shading noise;
  - the face's shape against the generated character's face (`charkit/faceqa.py`). Both faces are z-buffered from the front,
    at 3/4 and in profile with every surface occluding; the generated mesh's skin is found by colour. Ours is measured
    without its hair, since we know it underneath, and the target only where its face shows. The checks: the lower face's
    half-width at the mouth line and halfway to the chin (as a ratio), the chin's height (where the profile turns back to
    the neck), the profile's front edge, the far cheek's contour at 3/4, and depth over the cheeks and chin from under the
    eyes (where the two are aligned). How much face the hair leaves showing is a separate, warn-only check, and the feature
    heights against the design rig are informational. Overlays: `qa_face_contours.png` (both contours per view, the
    chins) and `qa_face_shape.png` (the two faces from the front, and the depth difference);
  - the face against the design's model sheet (`charkit/sheetqa.py`; `spec.ref.sheet` holds the image and the head boxes of
    its front, 3/4 and profile figures). The sheet is scaled by matching its front figure's height to the rig's, which
    is the same drawing at a known scale, and each view is aligned on its eyes. The 3/4 angle comes from how much the
    eye spacing shortens. In the drawing, the face is the skin reached from under the eyes with the drawn lines as
    walls. Ours is `faceqa`'s z-buffer at the sheet's scale, each triangle labelled by class, without the hair. Its face
    is bounded by depth jumps and cut at the chin, where the profile's front edge turns back to the neck. Graded:
    - the front half-widths at 55% and 75% of the way to each face's own chin;
    - the neck's width under the chin against the jaw's (no jaw line reads as a face running into the neck);
    - the profile's front edge, the nose's and chin's reach in front of the eye, and the chin's height;
    - the far cheek at 3/4.

    How much face the hair leaves showing against the design's warns only. Overlay: `qa_sheet.png`;
  - the eyes against the design rig's eye layers (`charkit/eyeqa.py`), which are drawn whole under the hair. Each of our eyes
    is rendered head-on at the rig's scale with no hair or brows, and both are segmented by colour into sclera, iris (an
    ellipse through its ring), pupil, highlight and lid line. Graded: the opening's aspect and width, the iris's width in
    it, the pupil's run (height over the iris's) and aspect (a slit is thin), and the gap between the upper lid line and
    the opening. The highlight's side warns only. Overlay: `qa_eyes.png`, each eye's picture above its segmentation;
  - the face, measured from the shape keys' geometry (no render, about 0.04 s): each expression's eye opening against
    neutral and against its intended range (`FACE_EXPECT`), the iris left visible (none in a blink), left/right symmetry,
    each mouth shape's opening (area, width, height, balance), and the distance between the closest two visemes.

When something can only be judged by eye, name the measurement that would close the loop and add it here.

**Every build is recorded, and every merge is measured first.**
- `python -m charkit history NAME [--check CHECK]` shows QA across builds. Each build appends its checks to
  `charkit/out/history/NAME.jsonl`, with the git commit, spec hash and base.
- `python -m charkit gate BRANCH [--into REF] [--args "--base anime"]` shows what merging a branch would do, before it
  happens. A throwaway worktree at the integration head builds the baseline (cached per commit and options). It then takes
  the branch with `git merge --no-commit`, runs the tests and builds again. The report in `charkit/out/gate/` lists every
  check that moved (regressed, improved, value, new, gone), the tests and the trace diff.
  - FAIL: a conflict, a failing test, a failed build, or a graded check that got worse or disappeared.
  - WARN: the build is 1.5x slower.
  - No branch moves.
- Builds record their Blender process in their output folder (`.pid.json`). `python -m charkit ps` lists them across
  worktrees, and `python -m charkit kill OUT_DIR` stops that one only. Never stop builds by pattern.

**References live in one manifest per character.** `charkit/refs/NAME/manifest.json` lists every reference the build,
fit and QA read: the model sheet, the 2D rig, the generated 3D-style key and the TRELLIS mesh. For each it records its
role, scale method and figures, provenance (the model and ledger entry, or the regeneration command for large files kept
out of git, with their hash) and cautions (the rig's face layer is bled out under the hair, so its bottom isn't the
chin). It also names which reference is the authority for each measurement, so a disagreement between the 2D design and
the 3D rebuild is settled in writing.
- A spec points at it with `ref.manifest`, and any spec value `ref:KEY` becomes that reference's path.
- `python -m charkit refs-check SPEC` verifies the manifest.

**The fast evaluator: the body, garments and hair without Blender** (`charkit/bodyeval.py`). A fit needs many
evaluations, and a Blender build with its QA takes about 100 s. `bodyeval.Evaluator(spec)` makes every object the build
makes, in numpy, at the rest pose: the skin (masked under the tight garments, as the build masks it), the eyes and the
mouth, every garment piece (the builders in `charkit/garments.py`), the hair and its cap, and the accessories. It then
measures qa3d's silhouette checks with `charkit.geom.raster` (pixel centres, qa3d's camera and bands, a part label per
triangle).
- **The hair.** The generated TRELLIS hair is selected, culled and smoothed as `scene.hair_shape_volume` and
  `hair_shape_mesh` do it (BVH signed distance, a vectorised face cull, Blender's Smooth modifier, which moves each
  vertex toward its edges' midpoints). Mode `geom` uses charkit.geom's closed hair, and the analytic locks are
  `hair.generate`. The cap comes from `hair.cap`, and the accessories sit on `hair.MeshVolume`. Both run in the venv
  because `hair` casts rays with charkit.geom's BVH when numba is there.
- **What is cached.** The assembly is pickled by spec and code. A body knob rebuilds only the body: the macro stage of
  `body.build_body_data` is cached, so this takes about 0.2 s. `bodyeval.compose` carries the assembled head over in its
  own frame (head centre, L), because the anime head is a wrap onto an L-sized target. The hair layers (selection,
  finish, cap, accessories) are kept in the head frame by the knobs each reads, and garment pieces are cached by their
  own spec.
- **Checked against Blender.** Run `python -m charkit bodyeval --validate BUILD` on a finished build. It dumps the
  build's geometry (`charkit/bodyeval_blender.py`) and compares object by object, then compares the QA checks and each
  view's silhouette pixel by pixel (from qa3d's overlay). With `--from SPEC --knob PATH=VALUE ...`, it evaluates the base
  spec with those knobs, which tests the fast knob path against a build made from them. On Clawd:
  - Every object built by the same code matches to 1e-7 m, and the float32 trace hashes match.
  - The ported hair is within 1.1 mm (bbox) and at 0.98 silhouette IoU of Blender's.
  - The QA checks are within 0.005: shape_iou 0.577 against 0.579, hair 0.971 against 0.976, torso 0.631 against
    0.633, skirt 0.569, legs 0.299, ref_iou 0.546 against 0.549.
  - The silhouettes agree at 0.986 to 0.990 IoU per view (the target's at 0.998). What is left is the subdivision
    surface's shrinkage, under a pixel. The QA's flat renders don't draw the outline hulls.
  - A body knob through `compose` stays within 0.002 of a full assembly on every QA number, and within 0.3 mm on
    average, across ten body knobs.
  - A Blender build of Clawd with four body knobs changed (leg 1.0, hip 1.0, neck_w 0.7, heads_tall 6.0) was validated
    against the evaluator's fast path from the base spec. The objects are within 0.5 mm on average. The collar's surface
    walk can jump one vertex on a sub-millimetre change: 23 mm, once. The QA checks are within 0.005, and the
    silhouettes agree at 0.986 or better (0.994 for the target).
  - faceqa's splat z-buffer covers any pixel a triangle touches, so it reads 3.6 % more pixels (0.96 IoU against Blender)
    and is about 40x slower. That is why the raster is used.
  - Speed, warm, per evaluation with the QA and measurements. It depends on the machine's load:
    - a garment knob or an accessory: 0.15 to 0.3 s;
    - a body knob: 1.2 to 2.7 s;
    - a hair-selection knob: 0.9 to 2.5 s.

    Blender takes about 100 s, so the slowest knob is at least 40x faster. The first evaluation of a spec takes 12 to
    20 s.
- **The measurements** (`bodyeval.MEASURES`, `bodyeval.measures`): the QA's IoUs, and ours minus the target's for the
  following, in head lengths L.
  - The filled width and outer extent per band, front and side.
  - The silhouette's top and bottom.
  - The arms' line from vertical (front, shoulder to waist).
  - Each leg's line and the gap between the legs.

**Every knob's effect on the silhouette** (`charkit/bodysens.py`). `python -m charkit bodysens SPEC [--only
body,garments,hair]` writes `sensitivity.json` and `sensitivity.md` to `charkit/out/bodyeval/NAME/`.
- **The inventory.** It lists every knob the body, the garment builders (parsed from `charkit/garments.py`, and a test
  holds the table to them) and the hair read, with its value or the builder's default, a step and a range. Each knob has
  a kind: geometry, colour, resolution, categorical, or inactive (read on a path this spec doesn't take).
- **The table.** Each geometry knob is moved a step each way through the evaluator, and the table records every
  measurement's change per step. The analytic locks, inactive under the TRELLIS hair, are measured on the analytic
  variant. Hair modes are measured as variants.
- **Needs a capability.** A measurement is listed when no knob moves it, when no single knob reaches half way to the
  target within its range, when it needs a limb turned, or when the best knob closes it only by pushing other
  measurements further out of tolerance. Each listing gives the best knob, its reach and its cost.
- **Findings on Clawd** (305 knobs listed, 221 measured, 10 min).
  - The figure is 0.27 L longer than the generated shape (`body.heads_tall`: 0.20 L per 0.2).
  - The skirt is 0.41 L too full from the front (`flare` 0.08 L per 3 degrees, `length` 0.07 L per 0.05 L, `back`
    0.06 L).
  - The legs stand 0.43 L further apart (`hip` 0.034 L per 0.05).
  - `height_m` moves nothing: the target is scaled by our eye spacing, so everything is in L.
  - Many garment knobs move nothing at band scale (cuffs, sleeves, collar, the shells' regions and cuts). That needs
    per-piece measurements.
  - Needing a capability: the arms' angle (40 degrees against 26) and the legs' splay (5 degrees). Every body knob
    scales along or across a bone, so none turns a limb. They move only as side effects of the torso's length or the
    head count. This leaves the front torso and legs spans out, and it wants a rest-pose knob.

Boards are still how a change gets seen: a front orthographic render over the reference drawing; a head
turntable at 85 mm (0 to 360 in 30-degree steps); an expression sheet (every eye state and viseme at front and three-quarter);
a lighting sweep of the face; a range-of-motion sheet (T-pose, arms up, deep bend, twist, crouch, kick); and topology stats
(face count per part, poles, non-manifold edges, weights per vertex). The bar: side by side with HoYoverse-style references
at the same framing.

## 5. Licences

MakeHuman's assets (base mesh, targets, skeleton, weights) are CC0 1.0 (LICENSE.ASSETS.md in makehumancommunity/makehuman):
vendored under `charkit/assets/makehuman/` with the notice, and credited in THIRD_PARTY.md. MakeHuman's code is AGPL and is
not used. Everything else is ours. Painted textures come from GPT Image under OpenAI's terms (outputs owned by us).

## 6. Phases

1. **Foundation:** the MakeHuman loader, macro morphs and anime stylisation; the VRM skeleton and weights; the head template
   and the neck weld. Board: three body types and three head shapes, clay and cel.
2. **Face features:** eye plates, lids and lashes, the mouth with a cavity and visemes, brows over the hair, expressions.
   Board: the expression and viseme sheets.
3. **Paint and shading:** generated views projected and baked; the shader stack. Board: head turntable, lighting sweep.
4. **Hair:** the clump library, presets and springs. Board: hair turntable against the reference.
5. **Garments:** the template set and fitting. Board: outfit turntable and range of motion.
6. **Export and QA:** VRM export, the three.js preview, the automated boards.
7. **Clawd v2** from the kit, re-rendered in the dance test; then a second character from a new spec.

## 7. Export and the three.js look

`python -m charkit export charkit/out/NAME/NAME.blend` (or `build ... --vrm`) writes `NAME.vrm`: our own glTF 2.0 / VRM 1.0
writer (`charkit/gltf.py`, numpy + bpy, no add-on), clean under the Khronos validator (`node tools/gltf_validate.mjs`).

- **Meshes** as Blender renders them: modifiers evaluated at the render subdivision (`--subdiv`, default 2: level 1 visibly
  moves the creased eye margins), without armature and outline. POSITION is the surface Blender draws (the outline SOLIDIFY
  moves it inward by the line width); `_HULL_NORMAL` where the hull's direction differs from NORMAL (the hair's envelope
  normals, flat parts); `_OUTLINE_WIDTH` (the outline's per-vertex factor), `_FACE_MASK`; TEXCOORD_0 'uv' and TEXCOORD_1
  'face' or 'lock', only where a material reads them. A keyed mesh splits into the part its keys move (sparse POSITION
  targets, NORMAL targets from the keyed hull directions) and a static rest.
- **Skeleton**: nodes with identity rotations in the VRM T-pose; the inverse bind matrices keep the build's A-pose, so no
  mesh or key is re-baked. `bindPose` (normalized-bone rotations) brings the build pose back.
- **VRMC_vrm**: humanoid, meta, expressions from our keys (aa ih ou ee oh from mouth_*, blink and per-eye blinks, happy angry
  sad relaxed surprised, lookUp/Down/Left/Right from the iris keys, lookAt type expression), every other key as a custom
  expression. **VRMC_materials_mtoon** fallbacks for other viewers (two tones, the step as shift and toony, world outlines).
- **OPENADS_charkit_look** (version 1; glTF frame, linear colours): root `{character, light.direction, head {bone, centre, L},
  height, features.through, bindPose}`; per material `{kind: toon3 | face | hair | flat | plate, role, doubleSided, alpha,
  lit, shade, deep, threshold, deepThreshold, softness, light, rim {color, amount, facing, range}, texture?, face {sdf
  (rg16: R high byte, G low), fringe, blush, softness, fringeRange, lit, shade, mask}, hair {lock, ring {color, elevation,
  centre, width, soft, facing, facingBlend, mid, amount}, gradient, strands}, color}` (texture infos add `wrap`, `filter`);
  per mesh `{object, outline {width, color, widthAttribute, normalAttribute}, feature, holdout}`. The exporter reads the
  parameters back from the node graphs `shade.py`, `faceshade.py`, `hair.py` and `garments.py` build.

`engine/three/charkit/look.js` renders it in three.js WebGPU with TSL (every number from the file; the face light in head
space, so the SDF shadow follows the head), and `projects/charkit-look` inspects it (`--serve`) and boards it against the
Blender build's own boards: every Clawd board (head views, body, expressions, mouths) and the analytic-hair variant
(`charkit/spec/clawd_locks.json`) match to under 1.1/255 mean difference, the rest being edge anti-aliasing.
