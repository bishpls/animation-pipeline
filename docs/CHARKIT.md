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
| **outfit intake** (`charkit/outfit.py`, §8) | the outfit component graph from the references: each piece's type, side, attachment, layer order, colour, extents per view and in 3D, motion class; a draft garment list and spring chains | none: it measures | the rig's layers, the model sheet, the TRELLIS field, annotated notes |
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
  - the model sheet's figures, found from the picture (`sheetqa.detect_figures`). Blobs off the paper, the regions they
    enclose filled (white boots on white paper). A blob at least half as tall as the tallest is a full figure; its view
    comes from its eyes: a level pair centred in the head's silhouette is the front, off-centre the 3/4, one eye the
    profile (facing the side its eye is on), none under a head of hair the back. A shorter blob carrying the hair's colour
    is an expression head; the rest (the hand studies) is skipped. A figure whose bottom stops short of the others' is cut
    (the 3/4 stands behind the heads). Head boxes follow one framing (`HEAD_BOX`, in L round the eyes), which reproduces
    the manifest's hand-typed boxes within 2 px given the sheet's scale. `python -m charkit figures SPEC [--write]` checks
    them against the manifest or writes them into it. Checks `figures_head_*` (px off the typed box), overlay
    `qa_sheet_figures.png`;
  - the whole character against the sheet's full figures (`charkit/bodyqa.py`). The drawing is segmented into skin, hair,
    iris, line and the garment families (orange dress, cream bow, panel and cuffs, dark hems and shorts, white boots).
    Hair and dress share their orange, so a line-bounded orange region centred above the shoulders (`HAIR_SPLIT`, -0.8 L)
    is hair. A cream fold's shadow has skin's hue, so each pale region takes its majority. Dark regions that survive an
    erosion are garment, thin ones line, and the lines are then absorbed. Ours is z-buffered (`faceqa.zbuffer`) at the
    sheet's scale from 0, the sheet's 3/4 angle, 90 and 180 degrees, each triangle classed by its object (the skin by
    material with the garment mask on, eye parts, hair) or, for garments and accessories, by the colour family of what its
    material renders there (`qa3d.material_tones`, a texture sampled at the polygon's UV). Both sides share one grid,
    aligned on the eyes rather than the feet: every other sheet check runs from the eye line, and a proportion error then
    shows where it is (long legs put the feet low) instead of being spread over the figure. The back has no eyes, so it
    takes the front's eye line and its head's axis. Per view, checks `body_<view>_*`:
    - IoU of the silhouette, hair, skin and outfit (every garment family); each family's IoU is information;
    - the feet and the top (L from the eye line);
    - the hair's length, width and reach;
    - the skirt's widest row through the body's axis (rows where an arm reaches it left out) and its hem, overall and at
      the middle;
    - the sleeves' span;
    - the leg, from where the legs show under the skirt to the sole, and the boot's white top (front and back);
    - each arm's angle, as information: the build pose isn't the sheet's, so the skin IoU carries it.

    A cut figure is compared above its cut. A sheet whose eye spacing and figure height disagree on the scale by more than
    3% puts a `caution` on every check. `bodyqa.design_views` hands the segmentation over as data (class, garment-family
    and figure masks per view on the eye-aligned grid), and `bodyqa.evaluate` grades any label image from
    `faceqa.zbuffer` without Blender. Overlay: `qa_sheet_body.png`, per view the design's classes, ours, and the
    silhouettes with the hair outlined and the measured heights ticked;
  - the expression heads against the kit's expression library (`charkit/exprqa.py`). Both sides are measured from class
    images: the drawn head segmented by colour, ours z-buffered head-on with the eye, mouth and brow keys summed onto
    the posed base meshes (the key blocks, no render, no hair). The sheet's heads share one scale, from their hair's
    width against the front figure's; their eye spacing is kept as a check and cautions past 10%. Each head is aligned on
    its found eyes.
    - Eyes: open or closed. Open eyes give the aspect and the iris over the opening, both against the face's neutral: the
      sheet's front figure for the design, ours at rest, so the iris size `eyeqa` grades doesn't read as an expression.
      Closed eyes give the lid's arc: + an arch (^^), - a sag.
    - Mouth: width, open height, area, fill, corner lift and wobble.
    - Brows: tilt and height, only where the drawing shows them past its fringe.

    Each head is matched part by part to the closest library entry, the match is rendered, and each part is graded
    (`expr_<head>_<eye|mouth|brow>`, with the ranked candidates). The template owns the library: the sheet never defines
    or limits it. A part with nothing within tolerance FAILs as `missing`, which means it gets added to the template.
    Clawd's sheet asked for mouths `laugh` (a wide D), `wavy` (flustered) and `yawn` (a tall O), and eyes `shock` (the
    iris shrunk by `eyes.IRIS_SCALE`), plus the combined `scene.PRESETS` laugh, angry, fluster and yawn. Overlay:
    `qa_sheet_expr.png`, per head the drawing, its classes and our match;
  - the palette (`charkit/paletteqa.py`). The design's tones per class come from the sheet's own pixels: the full
    figures' class images, a pixel in from each edge, the iris only round the eyes. Each class is split into lit and
    shade at the L* that best separates them, and each tone is its pixels' median. Ours are the flat tones our materials
    render unlit (toon3's lit and shade; a texture sampled where it is used), area-weighted. Graded by CIEDE2000: lit
    passes within 5 and warns within 10, shade within 7 and 14. dL, dC and dh ride along (Clawd's skin: +5 L*, -8 C*, the
    paler look). `paletteqa.extract` and `tones` take any picture with a class image. Overlay: `qa_sheet_palette.png`,
    the design over ours per class, lit then shade, with a grade bar;
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
- Builds share a machine-wide number of slots, and start only when memory is available.
  - A Clawd build with QA and export peaks at 2.2 GB of Blender (measured). Five worktrees building at once ran a 16 GB
    machine out of memory.
  - A build takes a free slot once `CHARKIT_BUILD_MEM_GB` (default 3) is available, or waits. The OS releases a slot when
    its process ends, crashed or not.
  - `python -m charkit slots N` sets the machine's count, and waiting builds pick it up. `CHARKIT_BUILD_SLOTS` in the
    environment wins over it. Use 3 on this 16 GB machine when it's dedicated to charkit, 2 otherwise.
  - Anything that starts Blender goes through `procs.run` (or `procs.acquire_slot`). `ps` shows who holds the slots.

**References live in one manifest per character.** `charkit/refs/NAME/manifest.json` lists every reference the build,
fit and QA read: the model sheet, the 2D rig, the generated 3D-style key, the TRELLIS mesh and the outfit graph (§8).
For each it records its role, scale method and figures, provenance (the model and ledger entry, or the regeneration
command for large files kept out of git, with their hash) and cautions (the rig's face layer is bled out under the hair,
so its bottom isn't the chin). It also names which reference is the authority for each measurement, so a disagreement between the 2D design and
the 3D rebuild is settled in writing.
- A spec points at it with `ref.manifest`, and any spec value `ref:KEY` becomes that reference's path.
- `python -m charkit refs-check SPEC` verifies the manifest.

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

## 8. Outfit intake: the references as pieces

`python -m charkit outfit SPEC [--out DIR] [--field FIELD.npz] [--no-field] [--notes NOTES.json] [--no-manifest]`
(`charkit/outfit.py`, numpy and scipy, about 80 s on Clawd) turns a character's references into an **outfit component
graph**. Layered and flowy attire then becomes separately built, rigged and measured pieces instead of knobs on one
garment. It writes into `--out` (default `charkit/out/NAME/outfit/`):

- `outfit_graph.json`: the graph;
- `outfit.png`: each sheet view with every piece outlined and labelled (red boxes mark cells no piece took), the rig's
  layer to piece mapping, and the field from four sides coloured by piece;
- `outfit.md`: the table, the comparison with the spec's hand-written list, the template gaps, the springs and the flags;
- `outfit_masks.npz`: each piece's exact mask in each view.

It also writes the graph as the character's reference `refs/NAME/outfit_graph.json` and registers it in the manifest
(kind `outfit_graph`, role, provenance with the inputs' hashes, authority `outfit_pieces`). The rest of the manifest's
text is left as written. A run is deterministic: two runs give the same bytes.

**Per piece:** `id`, `type`, `side` (L her left, R, C) and mirror `pair`; `colour` (the rig's drawn sRGB, plus the sheet's
lit and shade tones by `paletteqa.tones`) and `trims` (a colour along an edge: its edge, stepped or plain, height and
thickness);
`attach` (bone and t along it, region, parent and where the parent came from, contacts); `layer` (number, over, under);
`extent` per view (bbox, area and outline polygons in L from the eye line; x toward the image's right from the view's
origin, as `bodyqa.design_views` grids, or her left in the rig's frame); `extent3d` (bbox `[x0, y0, z0, x1, y1, z1]` in
the rig's frame, y toward her back, and the share of cells the sheet confirmed); `views` (seen in, pixel areas); `motion`
(class, reason, coverage round the bone, 3D flare); `sources`; `flags`. At the top level: the sources (rig, sheet with each
view's azimuth and field fit, field, notes), the 2D skeleton, unmatched cells, `templates` (the draft), `comparison` and
`springs`.

**Sources, combined and cross-checked:**

1. **The rig** (front, precise). Each front pixel belongs to the top-most layer drawn there. A layer's pixels are split by
   colour family: k-means tones per layer, merged when close in weighted Lab and of one hue, so a fold's shadow stays with
   its cloth while cream and skin stay apart. Rules on shape then cut out the sub-pieces:
   - the piece's own colour: the largest family that lies through the piece, not along its outline and not a stepped hem;
   - a colour running the piece's length through its body is a **panel** (the skirt's cream front);
   - a band at its top edge standing proud of it is a **cuff** (a boot's turned-down top);
   - a colour along an edge is a **trim**. It is **stepped** when the line between it and the cloth is a stair: the treads
     and risers of its slope, even on a slanted hem;
   - cells of the piece's colour that hang free, long and thin, touching the rest only at their top, are **tails**
     either side, or a centre **panel** (the bib the rig draws between the bow's tails);
   - two major components far apart, the layer's own whole drawing absent from the gap, are a **mirror pair** (the back
     panels). A bodice split by the bow over it stays one piece.

   Types come from the layer names' words and these rules. Sides are hers, so the rig's `sleeve_L` (the image's left) is
   `sleeve_R`. The 2D skeleton comes from `rig.json`'s joints, with the wrist where the hand's layer starts. `rig.json`'s
   own grouping of layers (head, torso, each arm and leg) picks the bone.
2. **The sheet.** The figures come from `sheetqa.detect_figures` and the class images from `bodyqa.design_views` (the
   model-sheet QA's own: orange, cream, dark, white, hair, iris). Nothing is re-segmented. Faint drawn lines (a black
   top-hat on the value) split the classes into cells, and the cells are matched to pieces:
   - by the field's prediction: the nearest predicted piece its class allows, within 0.12 L. A cell two predictions
     share is split pixel by pixel;
   - by adjacency as a tie-breaker: a doubtful cell goes to the piece whose rig neighbours match its own;
   - by landmarks for cells no prediction reached: heights from the eye line, side, class.

   Without a field the prediction is by landmarks alone (`--no-field`: coarser; about twice the flags on Clawd).
3. **The field** (TRELLIS.2, `trellis_ext/field.py`; `charkit/out/i3d/ext/*/<stem>_field.npz`). Surface cells on a 384³
   grid are fitted by silhouette IoU to the rig's front and to each figure. The 3/4 azimuth is searched from the one the
   eyes give. The cells are labelled by a geodesic competition that is aware of colour:
   - the seeds are front-visible cells whose rig label agrees 0.02 L round, whose colour is nearest the field's own colour
     for the rig family drawn there, and near their label's median;
   - an edge costs its length × (1 + (ΔE/10)²);
   - a piece reaches at most its drawn size from its seeds;
   - a piece the front shows whole (no background, under a quarter occluded: a bow, its tails, the bib) goes no deeper than
     0.1 L behind its seeds, so a bow can't run round the neck into the collar's back flap.

   The labels projected into each view are the prediction. The sheet's own masks then vote back into every cell shown in
   a view (Clawd: 76 k cells voted, 86% agreeing with the prediction). The final labels give `extent3d`, the coverage and
   the springs.
4. **The notes** (`refs/NAME/outfit_notes.json`, versioned, with provenance): an annotated vision pass, piece by piece
   (names, types, rig layers, parents, bones, motion, views). Each note is matched to a measured piece (rig layer, side,
   colour, type) and every field is compared. Disagreements go to `flags`. In the graph the notes give the id, type, name
   and parent (`parent_from: notes`, `parent_measured` kept); the measurement gives everything else.

**Attach and layers.** The bone is the limb bone the drawing covers most of, for pieces in an arm or leg group. On the
head it is the head. On the torso it is the torso bone at the piece's height (3D centroid). Parents:
- a sub-piece's own piece;
- for a hanging piece, the garment touching its top edge from above;
- for a wrapping limb piece, a wrapping garment on a nearer bone (sleeve on top, sleeve cuff on sleeve);
- for torso wraps and head pieces, the body.

Over and under come from the rig's drawing order between touching layers (whole drawings included). Within a layer a
panel is level with its piece, a cuff over it, and a tail under its knot. `layer.n` is the depth of that chain.

**Motion** (reasons are recorded). A piece **wraps** its bone when the confirmed cells cover 60% of the way round it, or
35% and it is seen from front and back. Without a field it wraps when seen front and back and it crosses the body or lies
on a limb. Then:
- **rigid**: small (under 0.3 L), or wraps without flaring;
- **cloth**: wraps and flares 1.5x over 0.4 L, not on a forearm, hand, shin or foot (a skirt: a ring of chains);
- **rigid**: lies on the hair, or has its bottom edge tucked into a band that doesn't run up under it (the bib into the
  waistband);
- **spring**: hangs 0.3 L below its top edge and is 1.5x longer than wide;
- **rigid** otherwise.

**Templates** are additive: a type the library lacks is a gap, and the design never limits the library. The map
(`outfit.TEMPLATES`):

| type | template |
|---|---|
| top, shorts | shell |
| boot | shell + shoe |
| boot cuff, cuff, sleeve cuff | band |
| sleeve | sleeve |
| skirt | skirt |
| collar | collar |
| bow | bow |
| waistband | belt |
| overskirt panel | **panel** (new) |
| hair accessory | accessories bun, star or crab (by the layer's name) |
| skirt panel, bodice panel, bow tail | a knob of the skirt, the top and the bow |

New here are `garments.panel`, a panel hung from the waist ring at an azimuth with a stepped hem, and the bow's `tail`
length. The defaults are unchanged. The draft's first knob guesses come from the measured extents, each knob marked
`measured` or `default`, with mirror pairs averaged. The comparison with the spec's list gives matched entries (with knob
deltas), pieces the hand list has only as a knob, pieces it misses, and entries it has extra.

**Springs** (`springs[]`) are data for the rig / VRM exporter:
- the joints run down the confirmed cells from the attachment (from the parent's lower edge when the piece hangs under
  it), one per 0.15 L;
- cloth gets eight chains round its bone;
- stiffness is 0.35 / length, drag is 0.3 + 0.5 width / length, with gravity and hit radius;
- positions are in L in the rig's frame.

They are not wired into `gltf.py` yet. That needs spring bones in the armature and the pieces' weights moved onto them.
Each chain then becomes one `VRMC_springBone.springs[]` entry, its joints the chain's bones with these values.

**Clawd** (`charkit/refs/clawd/outfit_graph.json`): 26 pieces. The comparison with the spec's list:
- 21 match (every hand entry is found; none is extra);
- 4 pieces exist in the hand list only as knobs: the cream skirt panel, the two bow tails and the bib;
- 2 are missing from it: the stepped-hem back panels. The hand list fakes them with the skirt's `back` of 0.55, while
  the skirt's own back hem measures 0.06.

Motion:
- spring: the skirt panel, both back panels and both bow tails;
- cloth: the skirt;
- rigid: everything else (cuffs, waistband, boots and their cuffs, sleeves, the collar, the bow, the bib, buns, clips).

There are 12 flags:
- the back panels' parent: skirt measured, waistband noted;
- the collar's parent: body measured, top noted;
- the bib's type and parent: the rig draws it in the bow's layer;
- the tails' bone: chest against upperChest;
- views: the crab clip is seen only on the front (a doodle elsewhere), the far bun is not found in profile.

**Known limits.**
- One test character.
- Bone heights are the drawing's 2D skeleton, not the 3D body's, so torso cut knobs stay defaults.
- The 3/4 fit picks 41° by silhouette against 26° from the eyes.
- Pleat counts and repeats are rough.
- The springs are not wired into the VRM.
- Accessories only map by layer name.
