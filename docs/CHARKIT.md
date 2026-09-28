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
     -> boards; the geometry bundle; export
     => the QA, in the venv, on the bundle
```

Each stage is its own module with a function that takes the spec and the scene so far, so a stage can be rebuilt alone,
and each writes its review board, looked at before the next is trusted.

In code (`charkit/scene.py`): `fit_cranium` (the skull's height from the generated hair) -> `character` (body, head,
features, keys) -> `hair` (and accessories) -> `face_shading` -> `garments`; then the products: boards, the geometry
bundle (`OUT/bundle`, `charkit/bundle.py`: everything the QA measures), the VRM, the `.blend`. With `hair.shape.mode
'geom'` the hair is cut venv-side first (`charkit.geom`, `OUT/geom/hair.npz`). Blender builds and exports; the venv
measures: after Blender, `python -m charkit build` runs the QA on the bundle in its own process (`charkit/qa3d.py`,
`python -m charkit qa OUT/bundle`), appending to the build's trace. `--qa blender` runs the old Blender-side QA pass
instead (`charkit/qa3d_blender.py`), for comparison during the move (§4, the geometry bundle).

### The build cache

`python -m charkit build` restores a stage from `charkit/out/.cache/` instead of running it when nothing the stage read
has changed (`charkit/cache.py`), and restores the boards, the geometry bundle and the VRM the same way when the whole
scene is unchanged. The QA runs venv-side on the bundle, and each of its parts (shape, scalp, poke, hair noise, folds,
mesh, eyes, sheet, figures, body, expressions, palette, face shape, face) is cached on its own (`cache.qa_part`): on the
bundle's arrays and metadata it read (recorded as it ran, by the hashes the bundle carries), the reference files it
opened and its code. A QA-only code change reruns only the parts that run that code (a `bodyqa.py` edit: the body,
expression and palette parts, 8.9 s for the whole build, the Blender side restored); an unchanged bundle restores
all of it. The design-side measurements of the model sheet (figure detection, the sheet's scale and measures, the
design's views and palette) are kept per reference and code (`cache.venv_memo`). The trace says, per stage, product and part, what was restored and,
for what ran, why (`python -m charkit trace OUT/trace.jsonl`; the summary line reads `cache: 12/14 restored; ran garments
(spec.garments changed), qa (the scene changed ...)`). `history` rows carry the same.

**A stage's key is what it read, recorded as it ran**, not a list kept by hand (the trace's `STAGE_KEYS` misses keys such
as `lash_color` and `base`, which the character reads):
- *code*: the stage function, the `scene.py` helpers it calls and `scene.py`'s top-level statements, and every charkit
  module those import, transitively, compared as syntax trees (a comment or docstring edit doesn't count); the kit's data
  (`charkit/assets`); `cache.py`; the Blender, numpy and Python versions.
- *spec*: every key it read, at any depth (`spec.head.width`, `spec.eyes.x`), exactly.
- *upstream*: every value it read of earlier stages, key by key through the Scene's dicts (`character.data.head.L`,
  `character.data.joints.neck01____head`), `shade.MATS` entries, Blender objects (their full state), except where
  `scene.DEPS` declares that a stage reads a value only in part (below).
- *files*: every file it opened outside the kit (the TRELLIS GLB; `OUT/geom/hair.npz`) and every path named in the spec
  keys it read, by sha256 (a stat-checked memo skips re-hashing an unchanged file; the reference manifest's own sha256 is
  compared against, never trusted instead). A file under the output folder is keyed relative to it.

A lookup evaluates each stored entry's recorded reads against the scene as it stands and restores the first that matches
in full. Keys are exact: a float that moved by 1e-11 is a change.

**The dependency map** (Clawd, as recorded in its entries' manifests):

| step | spec keys read | what it reads of earlier steps | files |
| --- | --- | --- | --- |
| geom hair (venv, `mode: geom`) | the resolved spec without the outfit | (assembles the character itself) | the GLB; the venv's packages |
| fit_cranium | `body.height_m`, `body.heads_tall`, `eyes.x`, `hair.shape.{glb, fit_cranium, under}`, whether `head.cranium` is set | - | the GLB |
| character | `base`, `name`, `body`, `head`, `head_detail`, `eyes`, `iris`, `brows`, `mouth`, `skin`, `skin_line`, the lash, brow, crease, cavity, eyeline and mouth-line colours | which `shade.MATS` materials exist | (the MakeHuman or anime base: the kit's data, in the code key) |
| hair | `hair`, `hair_colors`, `accessories` | the head (`H`, `L`, centre, eye knobs `x` and `z`, the wrap's target), the body's verts and faces (the generated hair is cut against our skin), the rig's structure, `shade.MATS` | the GLB, or `OUT/geom/hair.npz` |
| face_shading | - | the head (`H`, centre), verts, faces, the head weights, the skin colours, the skin's structure, the hair objects' names and the fringe (`hair_front*`) | - |
| garments | `garments` | verts below the neck's middle, faces, 52 bones' weights, the 22 joints its bones run between (the neck's two among them), `L`, the head's centre, the body's UVs, the rig's and the skin's structure | - |
| boards, bundle, VRM | the whole spec and every file it names | every stage's entry, and the products before them | what they open |
| QA parts (venv) | what each reads of the bundle's metadata (`spec.ref`, `spec.iris`, `assembly.eye_knobs`, a material) | the bundle's arrays each reads, by the hashes the bundle carries: eyes and face the head and its keys, figures nothing, body, palette, sheet and face shape the whole character and the clothes | the sheet, the rig's layers, the reference image, by content |

`scene.DEPS` holds the partial reads, each with its reason: garments read the body only below the neck's middle
(`body_below_neck`: shell regions, the collar's neckline, bands, sections and nearest-vertex weights all lie there; an
outfit reaching the head or past the neck's middle is keyed on the whole body); a stage that only parents to the rig, or
adds a vertex group and a modifier to the skin, reads their *structure* (names, stack, transform, pose), not their
geometry; face shading reads the fringe, not the rest of the hair.

What the measured keys show about the build itself:
- **head.width is not a face-only knob**: the head wrap drags the joints near the head with it (`anime_head.follow`
  moves every joint within 0.35 L of the chin with the surface: 127 of them), among them the neck bone's two ends, which
  the top's neckline, the collar and the neck's cut hang from, by 0.055 and 0.069 mm. A fresh build at `head.width` 1.1
  moves the collar by 0.5 mm and the sleeves and cuffs a little, so garments rebuild, and the trace says why:
  `garments: miss (character.data.joints.head____head moved 6.9e-05; character.data.joints.neck01____head moved
  5.5e-05; ...)`. `eyes.width` moves no joint the outfit uses: garments are restored.
- **Body knobs reach the head by float noise**: `body.proportions.leg_slim` moves every vertex, and the joints at the
  head by about 2e-11 m (rounding through the body's proportion and height scaling), so the hair, which reads the head
  and the body round it, rebuilds. Keys are exact on purpose; removing that noise at its source (and keying the hair on
  the body near the head only) is what would let a body-only change keep the hair.

**A checkpoint holds what the stage changed**, so it restores onto a rebuilt upstream (garments onto a new face): the
datablocks it made (`data.blend`, written by `bpy.data.libraries.write`; what they point at from before, the rig or a
shared material, is re-bound by name on append), and pickled (`state.pkl`, Blender references by name) the Scene
attributes and the spec and dict entries it wrote, key by key, its `shade.MATS` entries, its notes, and its changes to
objects made before it: new vertex groups, modifiers (settings and stack position), attributes and material slots,
replayed on restore. Pickle holds numpy arrays and charkit's own classes as Python keeps them (a `.npz`/JSON schema would
have to track every structure a stage keeps); entries are read only from this folder, which charkit alone writes.

**Correctness before speed.** A stage that changes anything a restore can't replay (an earlier mesh's vertices, a
material made before it, the scene's settings, an object it reached without reading it through the Scene, a value it read
changed in place) is uncacheable: it runs every time, and the trace and `CHARKIT_CACHE_UNCACHEABLE` say why. After a
restore the trace's own snapshot of the stage (the objects it added, their geometry hashes and health; the names and
modifier stacks of those it changed) must equal the one stored with the entry, or the build starts over with every step
run and the entry dropped (`CHARKIT_CACHE_RESTORE_FAILED`). `--cache verify` runs every step and compares it with the
entry a lookup would have restored, flagging a key that missed an input (`CHARKIT_CACHE_STALE`; images are compared by
their pixels' encoding, not the date Blender stamps into each PNG). Nothing is stored from a run that printed a traceback
(a QA check that caught an error and reported SKIPPED: a full disk once did that to the model-sheet body check), from a
build whose charkit sources changed while it ran, or with less than `CHARKIT_CACHE_MIN_FREE_GB` (2) left on the disk; a
store that fails leaves the build running, uncached.

Modes: `--cache on` (the default), `off` (or `--no-cache`), `refresh` (run and store everything), `stages` (restore the
stages, run the products afresh on the restored scene), `verify`. `python -m charkit cache info | clear`; the cache
keeps under `CHARKIT_CACHE_GB` (5) by dropping the least recently used entries (`python -m charkit ps` and `cache info` show its size); `CHARKIT_CACHE_DIR` moves it.

### The build worker

`python -m charkit worker start | stop | status` keeps one Blender running with charkit loaded (`charkit/worker.py`,
`charkit/worker_blender.py`); `build` sends its job over a local socket when the worker runs, and starts a fresh Blender
otherwise or with `--no-worker`. Each job drops and re-imports charkit's modules (edited code and module state never
carry over), resets the scene to factory settings, and checks the datablock counts and charkit's own handlers against
the worker's first clean state; a job that finds anything left over prints `CHARKIT_WORKER_LEAK` and the worker restarts
itself in place afterwards. The worker is recorded in `charkit/out/worker/.pid.json` and each job in its output folder
under the worker's pid (`python -m charkit ps`, `kill`); `stop` signals only that pid, after checking it is this
checkout's worker. Each job takes a machine-wide build slot (`procs.acquire_slot`, with its memory check) and, after
clearing its scene and collecting Python's garbage, gives it back: an idle worker holds no slot. It saves Blender's
start-up and keeps its render state warm between builds. Memory: 0.2 GB idle when started; a job's scene is cleared and
Python's garbage collected before its slot goes back, but Blender and Python keep 0.5 to 1.2 GB of what a Clawd build
freed (measured after cold, warm and other-character jobs), so after a job that leaves it above
`CHARKIT_WORKER_MAX_IDLE_MB` (600) the worker restarts in place (same pid and socket; a build that arrives meanwhile
waits for it) and idles at 0.2 GB again. `worker status` shows its resident memory and restarts; stop it when done.

Measured on Clawd (`--boards views`, QA on, `--no-blend`; wall clock on a machine shared with other builds, load
average 30 to 60, so the ratios matter more than the seconds):

| build | time | restored | ran |
| --- | --- | --- | --- |
| fresh, `--cache off` | 200.7 s | - | everything |
| cold (cache on, empty) | 203.2 s | - | everything (the cache's own cost: 1%) |
| warm, no change | 4.6 s (Blender 3.3 s) | every stage, the boards, the QA | nothing: 44x |
| warm in the worker | 4.2 s | everything | nothing |
| `--cache stages` | 104.8 s | the stages | the boards and QA, on the restored scene |
| `eyes.width` 0.2 -> 0.22 | 150.5 s | fit, garments, 1 QA part | character, hair, face shading, boards, 7 QA parts |
| `head.width` 1.0 -> 1.1 | 292.1 s | fit, 1 QA part | every stage (the neck's joints moved), boards, QA |
| a skirt's colour | 145.8 s | fit, character, hair, face shading, 4 QA parts | garments, boards, 4 QA parts |
| the GLB changed in place | 183.7 s | character, face shading, garments, 3 QA parts | fit, hair, boards, the rest of QA |
| a comment in garments.py | 8.1 s | everything | nothing |
| a code edit in garments.py | 133.0 s | fit, character, hair, face shading, 4 QA parts | garments, boards, 4 QA parts |

Every one of those builds trace-diffs to `no differences` against a fresh build of the same spec, with identical
`qa.json` values and pixel-identical boards and QA overlays (`charkit/tests/cache_builds.py`); the worker's builds, the
same spec twice with another character between, likewise (`charkit/tests/worker_builds.py`).

Tests: `charkit/tests/test_cache.py` (digests, recorded reads, the code closure, the file memo, invalidation by a code
file, an input file or a spec key, and a restore onto a rebuilt upstream in Blender);
`charkit/tests/cache_builds.py` and `charkit/tests/worker_builds.py` (real builds: what each change restores and runs,
the times, and the trace and qa.json proofs against fresh builds).

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
- **`qa/qa.json`, the graded checks** (`charkit/qa3d.py`, measured in the venv on the build's geometry bundle: see *The
  geometry bundle* below; PASS, WARN or FAIL against `LIMITS`, with overlays):
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
    is bounded by depth jumps and cut at the chin, where the profile's front edge turns back to the neck (searched from
    0.2 L under the eye line, below the nose: a projecting nose isn't the chin). Graded:
    - the front half-widths at 55% and 75% of the way to each face's own chin;
    - the neck's width under the chin against the jaw's (no jaw line reads as a face running into the neck). It reads
      one row, 0.06 L under the chin; `neck_run` (INFO) says how much neck shows there before the collar. Under about
      0.1 L, a one-pixel chin move flips that row between the neck and the shirt: on Clawd the neck read 0.139 or
      0.048 L;
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

### The geometry bundle: Blender builds, the venv measures

Every check runs in the venv, on one export of the build (`charkit/bundle.py`, schema `charkit.bundle/1`), with the
geometry kernel's numba rasteriser (`charkit.geom.raster.window_zbuffer`). Nothing is measured inside Blender, and nothing
needs a Blender render, a material override or the scene's state juggled for it. The fast evaluators make the same bundle
in memory (`bundle.Builder`) and call the same functions, so a fit's objective is the QA itself.

**The bundle** (`OUT/bundle/`: `bundle.json` and `arrays.npz`, about 18 MB for Clawd; a build product, cached like the
boards) holds everything the checks read:
- every object (the skin, the eye and mouth parts, the hair, accessories and garments) as its group, part, side,
  visibility, material slots and outline hull, with one or more variants of its geometry, each as world vertices
  (float64, as Blender evaluates them), polygons, a material slot per polygon and, where a check needs them, UVs and the
  render's normals per corner, the outline's pull per vertex, the base polygon each came from, and shape keys (world
  offsets, sparse):
  - `eval`: evaluated without the outline hull or the garment mask (what the face and sheet measures read);
  - `masked` (the skin): the garment mask on (what renders and what the body classes read);
  - `base`: the armature-posed base mesh and its shape keys (`eye_*`, `mouth_*`, `brow_*`, `look_*`, the iris's and
    teeth's); the skin's base is the assembly's own mesh and keys, exactly;
  - `raw`: the mesh data itself (hair and garments: poke-through and open edges);
  - `render_eye_L`, `render_eye_R`: the skin round each eye at the render's subdivision level (2), for the eye renders;
- the assembly's landmarks the checks use (`bundle.assembly_meta`: L, the head's centre, chin, eye knobs, each eye's
  centre and lid chains, the mouth's centre and lip chains, the waist and knee heights, the figure's height range);
- each material's flat tones as it renders unlit (`bundle.material_tones`: toon3's lit, shade and deep, a flat emission,
  a plate's texture), its back-face culling and, for a plain toon3, its shading (light, ramp steps, tones, rim);
- the images a check samples (the eye plates, the textured garments), as Blender stores them (bytes, rows bottom-up);
- the TRELLIS target aligned as the build aligned it, with its colours; the spec; the rig's measures.

The outline matters: `shade.outline`'s solidify leaves its hull on the original surface and pulls the surface itself in
by its thickness times the vertex's `outline_w` weight (`character.outline_weights`: none round the eye and mouth
openings). A render draws that pulled-in surface and the hull (flipped, back-face culled), and where a surface curls the
pulled-in side can reach past the hull; the bundle keeps the pull per vertex (`shrink`) so the venv draws both.

**What moved, and how each is measured now** (`python -m charkit qa OUT/bundle`, run by `build` after Blender):
- the class z-buffers of the sheet, body, expression and face-shape checks: `faceqa.zbuffer` keeps its API, backed by
  the numba raster (pixel centres, as a renderer covers them); lines and brows (`thin`) are still drawn at least a pixel
  wide, as the drawings' strokes are (the raster splats those triangles). The point-splat path (`faceqa.zbuffer_splat`)
  stays for Blender's Python and `CHARKIT_ZBUFFER=splat`;
- the silhouettes (`shape_iou*`, `ref_iou`): every visible surface as a flat render draws it (the pulled-in surface and
  the hull, no culling), supersampled 3x3 and filtered like EEVEE's 1.5 px pixel filter (a Gaussian of 0.44 px),
  covered where the filtered alpha passes 0.5;
- the scalp: the scalp polygons (the skin's base polygons over the cranium and the back of the head, by `parent`) drawn
  green, everything else in its materials' tones with its hull and culling, the world behind, filtered and read at 8 bits
  as the PNG was; a view with no green at any pixel centre reads 0 without the picture;
- hair noise: the hair drawn with its own materials (`qa3d.draw`: toon3 on the envelope normals the build transferred,
  its soft steps, the rim, a back face shaded from its flipped normal, the hull in its line colour), supersampled and
  filtered, 8 bits, then the same tone-edge count;
- the eyes: each eye drawn head-on (`qa3d.eye_image`: the render-level skin pulled in by its outline with the hull
  culled on the surface, the plates by their textures at their UVs, the iris over the white by its alpha, 5x5
  supersampled, a 0.55 px filter), then `eyeqa` as before;
- poke-through: `geom.bvh` ray casts instead of mathutils' BVH (in float32 as mathutils is);
- open edges and parts, the face's expressions, the folds, the palette, the figures: the same functions on the bundle.

The filters were calibrated against EEVEE on Clawd (`FIG_FILTER`, `EYE_FILTER`, `TEX_BLUR`): the silhouettes' mismatch
is at EEVEE's own sampling noise (about 0.07% of the pixels, even both ways), the eye renders' measures within a pixel,
hair noise within 1%.

**Validation.** Three builds of Clawd, each measured by the old Blender pass (`--qa blender`) and in the venv: the
fitted default, `--hair geom` and `--base anime`, 142 checks each. First the port alone: the venv QA with the old splat
z-buffer (`CHARKIT_ZBUFFER=splat`) reads the same bundle as the Blender pass read the scene, so everything but the
renders must be identical, and is. Then the renders drawn from the bundle, and the raster's own step:

| checks | tolerance | default | geom hair | anime base | the difference |
| --- | --- | --- | --- | --- | --- |
| `face_*` (6), `face_folds`, `poke_share`, `palette_*` (14), `figures_*` (4), `mesh` | exact | identical | identical | identical | the same functions on the bundle |
| `sheet_*` (12), `body_*` (67), `expr_*` (12), `face_shape_*` (8), splat z-buffer | exact | identical | identical | identical | the port alone |
| `shape_iou*` (5), `ref_iou` | ±0.005 | 0.001 at most | 0.001 | 0.001 | EEVEE's anti-aliasing is stochastic |
| `scalp_px` | ±5 px | 0 and 0 | 0 and 0 | 0 and 0 | (the hair cap covers the scalp) |
| `hair_noise` | ±0.01 | 0.2929 -> 0.2911 | 0.2265 -> 0.2210 | 0.2910 -> 0.2923 | anti-aliasing at the tone edges |
| `eye_*` (8) | ±0.03 in a ratio (a pixel of the eye render); the lid gap ±0.0003 L | 0.018 at most (pupil run) | 0.018 | 0.025 (iris ratio) | a pixel at the rig's 586 px/L |
| the same four families, pixel-centre raster | remeasured | below | below | below | pixel accuracy |

With the raster (the new measurement), the median shift is about a pixel: 0.0087 L for the body's heights and the
sheet's lengths (one sheet pixel), 0.003 for the body's IoUs (0.02 at most: the hair's), 0.0035 for the face-shape
measures (the width 0.024, the chin 0.012 L: two of its pixels), 0.014 to 0.034 for an expression match's distance. The
largest are single-pixel measures: `sheet_neck_to_jaw` 1.123 -> 1.303 (its one row, 0.06 L under the chin, moves from
the neck to the shirt: `neck_run` is under 0.1 L), `expr_fluster_eye` 0.12 -> 0.39 (a pixel of the shocked eye's small
iris), and on the anime base `expr_angry_brow` 0.87 -> 0.56 (the brow's tilt, a 7-pixel stroke, 8.2 -> 13.2 degrees
against the design's 22.1). Statuses that change: default `body_back_leg` and `body_profile_hair_width` PASS -> WARN,
`sheet_neck_to_jaw` and `sheet_profile` WARN -> FAIL, `sheet_width` WARN -> PASS; geom hair the same but the hair
width; anime base `body_back_leg`, `body_profile_hair_width` and `face_shape_depth` PASS -> WARN, `sheet_profile`
WARN -> FAIL, `sheet_width` WARN -> PASS. No render check changes status. The evaluator (`charkit.faceeval`) reads
every one of its 46 checks exactly as the venv QA does, on each base.

**Time and memory** (Clawd, `--boards views --no-blend`, fresh Blenders; the machine shared, so the ratios matter):

| | before: the QA in Blender | after: the bundle, then the QA in the venv |
| --- | --- | --- |
| the QA, first build of a scene (cache on) | 83 to 98 s | 8 to 13 s, plus 3 to 5.6 s to export the bundle |
| the QA, `--cache off` | 46 s | 10.6 s, plus 4.5 s for the bundle |
| the whole build, `--cache off` | 94 s | 66 s (Blender 55 s, the QA 10.6 s) |
| no change (everything restored) | 4.6 s | 4.9 s |
| a QA code change (a `bodyqa.py` edit) | the whole QA product ran again | the three parts that run it: 8.9 s for the build |
| peak memory | Blender 2.8 to 3.4 GB, with its QA | Blender 2.2 to 2.5 GB; the QA 1.2 to 1.5 GB on its own, after Blender exits (the build's venv process 2.2 GB, with the reference fit) |

Inside Blender the cached QA parts cost about as much again as the checks (46 s uncached, 83 to 98 s through the part
cache, which keyed each part on the Blender objects' full state); in the venv a part's key is the hashes the bundle
already carries. The venv QA's parts, cold: shape 3.6 s (twelve 3x3-supersampled full-figure views), scalp 1.4 s,
eyes 1.3 s, body 1.3 s, hair noise 0.7 s, the rest under 0.5 s each.

**The measurement steps it brings** (`history.STEPS`, so the gate and the tune call them `remeasured`): the sheet, body,
expression and face-shape z-buffers at pixel centres (the splats read about half a pixel wider: body heights move by
one sheet pixel, 0.0087 L; `sheet_neck_to_jaw` reads its one row, which a pixel moves from the neck to the shirt); the
eye, silhouette, scalp and hair-noise renders drawn from the bundle.

**Known gaps.**
- The scalp and hair-noise renders shade toon3 (plain or textured), flat and plate materials. A material the bundle
  can't read as one of those (the analytic hair's angel-ring material, the face shading's SDF) is drawn in its flat lit
  tone; `hair_noise` then carries a caution naming it. The eye renders draw the skin in its flat tone (the SDF face shading and blush aren't drawn: the
  eye segmentation doesn't read skin tones).
- EEVEE's anti-aliasing is stochastic; the calibrated filter matches it in the mean, not pixel for pixel.
- `--qa blender` is kept for the transition; it measures inside Blender with the splat z-buffer and EEVEE, as before.

**Every build is recorded, and every merge is measured first.**
- `python -m charkit history NAME [--check CHECK]` shows QA across builds. Each build appends its checks to
  `charkit/out/history/NAME.jsonl`, with the git commit, spec hash, base, hair mode and a note (a tune run's rows say
  which run and checkpoint made them).
- **Measurement steps.** When a check's measurement changes rather than the character, its numbers step. `hair_noise`
  read about 0.31 instead of 0.35 to 0.7 once the QA renders stopped dithering (c500f21, the geom merge). `face_folds`
  rose from 1014 to 1257 on the same skin when the expression library grew, because it sums over every key (8017ff3,
  tool/sheet). `face_shape_coverage_*` became INFO once the sheet took over grading framing (5652f64). `history.STEPS`
  lists each step (the check, the commit, what changed). A build is before or after a step by whether that commit is in
  its history. `history --check` draws a line at each step, `history.trend` reads only the builds since the latest one,
  and the gate's and the tune loop's comparisons call such a check `remeasured`, neither better nor worse. Add a step
  whenever a QA change moves a check's numbers.
- `python -m charkit gate BRANCH [--into REF] [--args "--base anime"]` shows what merging a branch would do, before it
  happens. A throwaway worktree at the integration head builds the baseline (cached per commit and options). It then takes
  the branch with `git merge --no-commit`, runs the tests and builds again. The report in `charkit/out/gate/` lists every
  check that moved (regressed, improved, value, new, gone, remeasured), the tests and the trace diff.
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

**The QA chooses the face's knobs: `python -m charkit fit SPEC`** (`charkit/facefit.py`). The face, eye and neck knobs
are fitted to the graded eye, sheet and face-shape checks, then built (`build DIR/NAME.fit.json`).
- **The fast evaluator** (`charkit/faceeval.py`, numpy only) measures a knob set the QA's way in about two seconds
  (a full Blender build takes 50 to 90). It makes the geometry bundle a build would export, in memory
  (`Evaluator.bundle`, `bundle.Builder`), and measures it with the QA's own functions (`qa3d.sheet_measure`,
  `qa3d.face_shape`, `qa3d.eyes`, `qa3d.face`, `qa3d.folds`, `qa3d.sheet_expressions`): one code path, so the evaluator
  and the QA agree by construction. The bundle holds what the build would make: `character.assemble` without the shape
  keys (with them for the expression checks), keeping the body and the wrap's knob-independent part between calls
  (0.5 s); the skin subdivided as Blender's modifier does it (`charkit/subdiv.py`: level 1, limit surface, eye margins
  creased, OpenSubdiv's child order; within 1 µm of Blender's), and round the eyes at the render's level 2, pulled in by
  its outline (the `outline_w` weights subdivided with it) with the hull left on the surface; the eye and mouth parts
  and their keys; the eye plates' `eyetex` textures stored as Blender stores them (bytes); the cranium fitted from the
  hair and the TRELLIS target aligned on our eyes, both as the build does. What only Blender makes is cached once per
  spec by `charkit/fit_blender.py` (`charkit/out/fit_cache/`): the loaded TRELLIS mesh, and the scene's hair,
  accessories and garments. The garments follow the skin they were fitted on, so neck knobs move the neckline.
  `python -m charkit fit --validate BUILD_DIR` compares it with a build's own `qa.json`.
- **The fit** (`charkit/fitkit.py`, generic; `facefit.py` declares the face's part). Knobs carry a spec path, template
  default, step, bounds and group. Terms are graded checks read as residuals in units of their PASS tolerance. The
  manifest's authority map weights them: full weight where that reference is the authority for the measure, a quarter
  otherwise, so the sheet leads the face's 2D shape, the rig the eyes, and TRELLIS the depth. A residual beyond its
  tolerance counts again (a hinge); a missing check costs 3; a regulariser pulls toward the template defaults. Each
  group is fitted by scipy's trust-region least squares on a parallel finite-difference Jacobian (one knob step). The
  sheet's 115-px/L grid is smoothed there over four sub-pixel offsets, with a soft-L1 loss so a term that flips between
  two readings can't steer. A pattern search at the QA's own grid then polishes the result. It is deterministic.
  The groups are `eyes` (the eye checks) and `face` (sheet and face-shape: front, 3/4, profile and depth at once).
  - Interface: `facefit.fit(spec, out, budget=None) -> (fitted_spec, report)`; `facefit.declare()` lists the knobs
    (bounds included) and the terms.
  - `DIR/sensitivity.json` (schema `charkit.sensitivity/1`): knob -> measure -> {at, minus, plus, per_step, per_unit}.
    `sensitivity.md` is the readable version.
  - `DIR/fit_report.json|md`: every check before and after, residuals per view, each knob's start, fitted value, default
    and whether it ended at a bound. What still fails is triaged (`fitkit.triage`) as *needs a knob*, *knob at bound* or
    *trade-off*.
  - `--views` also fits each view alone. If every view passes alone but not together, one rigid face can't match them
    all, which is the case for view-dependent face keys.
- **Knobs added for it**: `head.nose_tip` (the nose's projection in L: a relief on the wrapped face, both bases;
  `Head.nose_relief`) and `head.low_flat` (the lower face's section, from a sharp V to a broad jaw, growing from the eye
  line to the chin). The neck already had `body.proportions.neck_w`, `neck_len` and `head.neck_r`.
- **Fixes it needed**: `refs.fit` takes the chin from the model sheet (`refs.sheet_chin`), or from the rig's face layer
  less its bleed. The QA's chin search (`faceqa.chin_bottom`) starts under the nose, where a projecting nose used to
  read as the chin. `faceqa`'s depth regions stop at the higher of the two chins, since below it the check read the
  target's neck against our under-chin.
- **Every graded check keeps its status.** The merge gate fails any check that reads worse, so the fit protects them:
  - its own terms are held in the status band they had at the start, or in `--baseline QA.json` (the gate's build),
    by a steep extra residual;
  - the hair's coverage checks are held the same way, with a token weight: they are the hair's to meet, not the face's;
  - the checks it doesn't model as terms (expressions, folds) are held by `fitkit.guard`, which scales a group's change
    back while one of them reads worse.
- **The cached hair and garments follow the fit.** While searching, the garments move with the skin (only an
  approximation of refitting them: it misread the neckline by 0.1 in `neck_to_jaw`). The hair stays as culled against
  the start's face, but a fuller face culls more of the generated side locks, which moved Clawd's 3/4 coverage from
  0.93 to 1.34. So the fit rebuilds both in Blender for the fitted head and body and fits the face again from there, up
  to twice (`--refresh-only` runs just this from the spec's knobs).
- **Clawd** (`charkit/spec/clawd.json` carries the fitted knobs). Against the integration build, 18 graded checks move up a
  status and 1 down; the rest keep theirs. Per view, the RMS residual against the design (in tolerances; 1 passes):
  - front 3.65 -> 1.10: the sheet's widths FAIL -> WARN; `neck_to_jaw` FAIL -> WARN;
  - 3/4 2.88 -> 1.43: the far cheek's chin WARN -> PASS;
  - profile 3.55 -> 1.50: the front edge and chin reach FAIL -> WARN; the chin's height WARN -> PASS;
  - depth against TRELLIS 7.96 -> 1.02: FAIL -> WARN;
  - eyes 2.98 -> 1.15: pupil run and aspect, iris ratio, width and lid gap now PASS; lid span WARN; the opening's
    aspect is still short of the design's tall oval (0.74, a trade-off with pupil run and lid gap).
  The one move down is `face_shape_coverage_three_quarter` (PASS 0.93 -> WARN 1.34), a hair check. `scene.cull_face`
  drops generated hair lying within the face's width below the eyes, so the sheet's wider jaw culls the side locks
  that cover the cheeks. Scaling the face change back to half still reads 1.19; freezing the widths restores it, but
  gives up the width, neck and depth gains. Keeping the side locks is the hair's to decide (the geom hair already
  keeps them in front of the cheeks).
  - Each view fitted alone from the joint result (`--views`), against the joint fit: front 1.19 (1.10 jointly), 3/4
    1.45 (1.43), profile 1.45 (1.50). So one rigid face holds all three about as well as each could alone. What limits
    them is the knob set, not a conflict between views:
    - front: `neck_to_jaw`;
    - 3/4: TRELLIS's fuller cheek;
    - profile: the drawn nose reach, which a rigid face can't follow (the one candidate for a profile-only face key).
    Depth against TRELLIS passes alone (0.04) but reads 1.02 with the sheet: the 3D restyle's rounder face disagrees
    with the drawing, and the sheet has the authority.
  - The evaluator agrees with the build's QA on every one of its 46 checks, values and statuses, on the fitted Clawd
    (tool/measure). Before the bundle, when it rendered the eyes its own way, 183 of 184 statuses matched over four
    builds and the eye values were 0.04 to 0.09 apart: it didn't draw the skin's outline, which renders as the surface
    pulled in by 1.1 mm with the hull left on it (a lash within that of folded lid skin hides behind the hull).
- **Known gaps**:
  - The sheet is 115 px per head length, so one pixel is 0.009 L, half a chin tolerance. `neck_to_jaw` reads a single
    row, and `neck_run` above 0.1 L keeps that row off the collar.
  - The drawn profile's nose reach (0.157 L in front of the eye) is a drawing convention. A rigid 3D nose that long
    reads as a spike, so `nose_tip` stops at 0.04 L and the nose-reach term stays a trade-off.

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
- **Geom mode's hair and the body.** The geom hair cut also reads the body: the hair is kept outside the skin, so the
  back and shoulders trim what hangs there. A cut takes 30 to 60 s. So by default it is cut once at the evaluator's
  own body and carried in the head frame. With `Evaluator.exact_geom` it is cut for each spec (cached on disk by the
  spec). The body fit judges with exact cuts: its before, after, repair and guard checks. On Clawd, carrying the
  start's cut read body_profile_hair_width 0.914 WARN, and the fitted body's own cut reads 0.920 PASS.
- **Checked against Blender.** Run `python -m charkit bodyeval --validate BUILD` on a finished build. It dumps the
  build's geometry (`charkit/bodyeval_blender.py`) and compares object by object, then compares the QA checks and each
  view's silhouette pixel by pixel (from qa3d's overlay). With `--from SPEC --knob PATH=VALUE ...`, it evaluates the base
  spec with those knobs, which tests the fast knob path against a build made from them. On Clawd:
  - Every object built by the same code matches to 1e-7 m, and the float32 trace hashes match. The evaluated
    garments (Solidify, then the Subdivision Surface) match Blender's to 4e-7 m, vertex for vertex. Before the Solidify
    was ported, the garments' inner shell and rims were missing. That changed nothing the base build measures, but on
    the fitted Clawd it opened two-pixel gaps beside the neck: sheet_neck_to_jaw read 0.94 PASS here and 1.41 FAIL in
    Blender.
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
    scaled along or across a bone, so none turned a limb. They moved only as side effects of the torso's length or the
    head count, which left the front torso and legs spans out. The rest-pose knobs below were added for this.

**The rest pose** (`body.pose`: `arm_down`, `elbow`, `leg_in`, in degrees from MakeHuman's A-pose; `body.rest_pose`).
- **What each turns.** Each knob turns its bone in the frontal plane about the front-back axis through the bone's head:
  the upper arms at the shoulders, the forearms at the elbows, the thighs at the hips.
- **How.** The skin follows by linear blend skinning with the body's own weights, down the VRM hierarchy. The VRM
  joints land exactly on the turned bones, and the result becomes the rest. The armature, the garments (sleeves and
  cuffs ride their bones) and the head are then built on it.
- **Zero is the old build.** At zero nothing is computed, so it is bit for bit the old build.
- **Export.** The VRM export's T-pose is taken from whatever the rest is (`gltf.skeleton` turns each bone from its
  bind direction to the T-pose's), and `bindPose` brings the build pose back.
- **On Clawd.** `arm_down` 14 and `leg_in` 5 bring the arms to 26 degrees and the legs together. That raises shape_iou
  from 0.577 to 0.675, the legs band from 0.30 to 0.53, and ref_iou from 0.546 to 0.749.

**One measurement code for every geometry source** (`charkit/bodymeasure.py`).
- **The bundle.** The measures take a bundle, which is plain data:
  - per object: world vertices, triangles, and per triangle a model-sheet class (`bodyqa.CLASS`) and the lit and shade
    tones its material renders unlit; the skin twice, with and without the garments' mask (role `masked` or
    `unmasked`: the face measures read it without, as qa3d.sheet does);
  - the landmarks (L, the head centre, the chin, waist and knee heights, the iris centres);
  - the aligned generated shape.
- **Producing one.** `bodyeval.Geometry.bundle(levels)` makes one from the fast evaluator. It evaluates the skin and
  garments as the build's modifier stacks do:
  - the garments' thickness: `bodyeval.recalc_normals` (bmesh's recalc_face_normals, which `garments._object` runs),
    then `bodyeval.solidify` (the Solidify modifier: offset -1, the rim filled, per kind as `garments.build` sets it);
  - then Catmull-Clark to the limit surface (`bodyeval.subdivide`), each child quad starting at the corner Blender's
    does, so a fan triangulation cuts it along the same diagonal.

  'viewport' is what the
  in-Blender QA z-buffers, 'render' what its renders show. The classes and tones come from the build's own material
  rules: the skirt's and panels' stepped hems and the top's front panel sampled per subdivided face, the iris where its
  texture is opaque. A Blender export of the same bundle would be measured by the same functions:
  - `shape` (qa3d's shape and ref IoUs, charkit.geom.raster);
  - `sheet_body` (charkit.bodyqa's checks against the model sheet);
  - `sheet_face` (qa3d.sheet's face checks; the body fit holds them until the face fit's evaluator lands);
  - `sheet_palette` (charkit.paletteqa's);
  - `piece_extents` / `piece_checks` (each outfit piece's visible extent per view against the outfit graph's, §8);
  - `scalp` (qa3d's scalp check: the flagged scalp's pixels seen through everything, per view);
  - `measures` (the band, extent and pose measurements).
- **Fast parts.** `bodymeasure.zbuffer` is the QA's own z-buffer (`faceqa.zbuffer`, the numba rasteriser that
  `charkit measure` brought), with lines drawn at least a pixel wide as `bodyqa` and `sheetqa` draw them, so the fit
  reads the pixels the QA reads. It replaced `bodymeasure.zsplat`, a compiled copy of the old point splat, when
  tool/measure merged; the validation numbers below were measured against the splat QA, before that merge. `bodymeasure.face_region` is faceqa's flood fill as a
  connected-components pass: the same pixels (tested), in milliseconds.
- **Against the merged build's QA.** All 81 body_* and palette_* checks grade the same, with values within 0.012
  (lengths in L, width ratios) and 0.14 dE. The front arm angle, which is information only, is within 0.5 degrees. The
  face's sheet_* checks match to 0.0001 (the hair-coverage shares, warn only, to 0.011: our hair isn't decimated). The
  shape silhouettes agree at 0.993 to 0.997 per view.

**Fitting the body, garments and hair to the sheet** (`charkit/bodyfit.py`: `python -m charkit bodyfit SPEC [--pieces
figure,details,hair] [--palette] [--no-outfit] [--no-draft] [--workers N] [--baseline QA.json] [--free-head]
[--write-spec]`). It uses the face fit's machinery (charkit.fitkit) and has its interface (`declare()`, `fit()`), so
a tune loop can register it alike.
- **The start.** The fit starts from the outfit graph's draft (§8):
  - it adds the pieces the spec's list lacks (on Clawd, the two stepped-hem back panels the list faked with the skirt's
    `back`);
  - it takes the draft's measured first guesses for the knobs the fit owns: the skirt's back, the bow's size, the
    cuffs' widths, the collar's depths;
  - it ties attached pieces' knobs (`tie`): a piece hung from the waistband shares its waist line (the skirt, its back
    panels), a cuff sits at its sleeve's end, a boot's cuff at its top, each at its drafted offset.
- **Groups.** Fitted in this order:
  - the figure: the body (head count, proportions and the rest pose; the neck's knobs are left to the face fit), the
    skirt (flare, length, back, the shared waist line) and its back panels (length, flare, width, azimuth, a mirror
    pair), and the boots (the shell's top on the shins, its cuffs tied). They go together because where the legs show
    depends on the hem;
  - the details: the sleeves' puff and length (the cuffs tied), the wrist cuffs' position and width, the waistband's
    width, the collar's depths, and the bow's size, height and tails;
  - the hair: its mode first (`hair.shape.mode`, mesh or geom, whichever its terms cost less), then hair.shape's below
    and shoulder_x.
- **Terms.** One per graded check, fitkit's readings (1 = the PASS line, a WARN line past it). Each group is a
  least-squares fit over its knobs against all its terms at once, every view together:
  - the sheet's four views: feet, legs, boots, hems, the skirt's and sleeves' widths, the hair's length and width, the
    top, the arms' angle, and the silhouette, skin, outfit and hair IoUs (toward 1);
  - the generated shape's IoUs;
  - each piece's visible extent (its bbox edges) per view against the outfit graph's, a piece's views sharing one
    view's weight. The arms' pieces also count for the body, whose rest pose moves them;
  - the face's model-sheet checks, held where they start (a `hold` reading: no further from their targets; the face
    fit owns them).
- **Weights.** Each term is weighted by the manifest's authority map: full where its reference is the authority for its
  measure (the sheet for the body's and hair's silhouettes, the generated shape for the hair's shape, the outfit graph
  for the pieces), a quarter otherwise. Each knob is pulled toward its template default (fitkit's REG).
- **Protection.** fitkit keeps every term in the status band it starts in, or has in `--baseline`'s QA (the merge
  gate's build). That protection is soft, because many terms can outvote one. So after the groups:
  - **the repair**: a check that reads worse than at the start (or in the baseline) has its terms weighed 16 times,
    and its groups are fitted again from where they are (two rounds at most);
  - **the line repair**: for what is still worse, a line search along the knobs that move it most (from the
    sensitivity table), taking the smallest step that brings it back into its band while no other graded check reads
    worse.

  fitkit.guard then scales a group's change back while a check no term aims at reads worse.
- **The head is held.** The body's knobs keep the head as the spec builds it (`bodyfit.hold_head`). Each sets
  `body.height_m` and `body.heads_tall` so that MakeHuman's head keeps both its scale and L, and the head count then
  follows from the proportions (height = L + k × the chin's height). `anime_head.reshape` has thresholds in metres, so a
  head scaled any other way wraps a little differently.
  - On Clawd, the first fit's head count (6.2 to 6.1) and legs (1.0 to 1.14) moved the face skin near the eyes by up
    to 12 px at the eye QA's scale, about 0.6 px on average. The evaluator's measures didn't see it.
  - In the Blender build, that was enough to cut the right eye's lash wing from its lash by one pixel. The lash line's
    largest component then shrank, and eye_lid_span went from WARN 1.107 to FAIL 0.795.
  - With the head held, the face skin near the eyes stays within 0.03 px.
  - `--free-head` makes the head count a knob of its own again.
- **The optimiser.** fitkit.optimise: a bounded trust region on soft-L1 residuals, a finite-difference Jacobian in
  worker processes (`--workers`, 2 by default: each holds an evaluator), then a pattern search, restarted while it
  helps. It is deterministic. A sensitivity table (fitkit's SCHEMA) feeds the triage of what still fails: needs a
  knob, knob at bound, or trade-off.
- **The palette.** `--palette` sets the skin and hair colours to the sheet's lit and shade tones. Each class of
  garment colours moves by the one shift that minimises its lit tone's dE00, kept inside its colour family. Then one
  shade multiplier for every garment is fitted to the garment classes' shade tones. It is the garments' new `shade`
  knob (garments.SHADE_MUL, 0.86 0.80 0.84, when unset): the sheet's garments shade warmer and darker (0.74 0.64 0.65
  on the orange, 0.68 0.63 0.62 on the dark) than one fixed multiplier allows. A step that doesn't read better,
  re-measured, is not kept.
- **What it writes.** `DIR/NAME.bodyfit.json` is the fitted spec. `DIR/sensitivity.json` is the table.
  `bodyfit_report.md` has every check before and after, the knobs per group, what the outfit graph set, and the
  triage. `--write-spec` writes the fitted knobs (and the added pieces) into SPEC.

### The tune loop: from a spec to a fitted, checked build and a list of what's left

`python -m charkit tune SPEC [--out DIR] [--budget N | Nm] [--review] [--args "..."]` (`charkit/tune.py`) is the outer
loop. The fast fitters choose knobs, full builds check them, and the error they leave becomes ranked work items.

1. **Checkpoint 0** builds the spec as it is, with full QA. Every checkpoint builds its own snapshot of its spec
   (`ckN/input.spec.json`), so nothing a later fit writes can change what an accepted checkpoint was.
2. **Rounds.** Each fitter in the registry (`charkit/fitters.py`) runs from the best checkpoint so far (the spec it
   resolved to), if any of its target checks isn't passing. What it changes is built and QA'd as a new checkpoint. The
   fitters, in order:
   - **build options**, a discrete choice. The character's tune config lists them, e.g. `geom-hair` (hair.shape.mode
     geom) and `anime-base`. Each is tried once as its own checkpoint. `set` writes the spec (so the fitters see it);
     `args` go to the build. `--args` applies to every checkpoint.
   - **face**: `charkit.facefit` (`python -m charkit fit`: tool/fit).
   - **body, garments, hair and palette**: tool/bodyfit (the `shape_iou*`, `ref_iou`, model-sheet `body_*` and
     `palette_*` checks).

   **The probe.** Before a landed fitter's full fit, the tune measures that fitter's sensitivity table at the start
   (two fast evaluations per knob, 1 to 3 minutes). From it the probe reads two things:
   - how far the fitter's own objective (fitkit's cost over its terms, regulariser included) drops at the best single
     knob step;
   - what every knob's better step gains in the tune's weighted QA score, summed.

   If the objective drops by less than `probe.min_headroom` (2%), or the QA score gains less than
   `probe.min_score_gain` (1 warn band), the fit is skipped as `converged` and the table serves the triage. The probe
   is recorded in tune.jsonl: both headrooms, the best steps and the verdict.

   Both measures are needed. On Clawd's fitted spec with geom hair, the objective had 8.9% headroom, but the QA score
   could gain only 0.68 warn bands (`body.neck_w` 0.38, `eyes.lash` 0.18, `iris.rz` 0.12). The full face fit then took
   about 40 minutes and moved 21 knobs by under 1% each, and its checkpoint scored worse than its start. The fit's
   `REFRESH_BUDGET` rounds, with their Blender cache rebuilds, aren't capped by `--budget`.

   **The prescreen.** After a fit, the tune reads the fit's report. If the report predicts a status regression that no
   trade-off rule allows, the whole move isn't built, since the fast evaluator agrees with the build. Only its blocks
   and its half step are built.

   A fitter that hasn't landed is a stub, marked `STUB` everywhere. It declares its targets and knobs, and fits nothing.
   Each fitter declares the check patterns it targets and the knobs it owns (path, default, step, bounds, group: a
   fitkit fitter's `declare()`). The builds go through `python -m charkit build`, so each takes a machine build slot
   and uses the stage and QA cache: a face fit's checkpoint rebuilds only what the face knobs reach. Each checkpoint
   records its cache hits. The tune starts the worker if none is running and stops it at the end (`--no-worker` uses
   fresh Blenders). Fitters and builds run in their own process groups, so `python -m charkit kill DIR` stops the
   whole run.
3. **Accept or reject.** Each checkpoint is compared with the best by the gate's QA diff (`gate.compare_qa`). It is
   accepted only if no graded check regresses (its status gets worse, or it disappears), unless a trade-off rule allows
   it, and only if the total severity drops. `checks.score` sums, over the checks both builds share, how far each is from
   passing in warn bands: 0 at the pass limit, 1 at the fail limit, capped at 5. A warn-only check's severity keeps
   growing past 1, so getting worse still shows. A check measured against a reference that isn't its measure's
   authority counts a quarter, as fitkit weighs its terms: the TRELLIS face's width counts a quarter of the sheet's. A
   rejected fit with several knob groups is tried again one group at a time, then at half its step (flips at a limit
   often vanish there). A build option whose only losses are checks a landed fitter owns gets that fitter's re-fit
   first, and the option and fit are judged as one move. anime-base, for example, costs the eye width, which is the
   face fitter's.
4. **Stop** when:
   - every graded check passes (`pass`);
   - the best score improved by less than `min_gain` over the last `rounds` rounds (`stalled`);
   - no fitter has anything left to change (`converged`);
   - or the budget runs out (`budget`: full builds including the final one, or minutes).
5. **The end.**
   - The best checkpoint is built once more with every board (`final`), which also checks that its QA repeats.
   - Each landed fitter measures its sensitivity table there. A fit's own table is measured at its start.
   - Each landed fitter checks its fast evaluator against that build's QA (`python -m charkit fit --validate`).
   - The residuals are triaged.
   - With `--review`, the review board is written and the final build exports a VRM.

Everything goes to `DIR/tune.jsonl`: begin, fit, checkpoint, compare (every check that moved, trades, the fast
evaluator's disagreements with the build), probe, prescreen, round, stop, repeat, sensitivity, validate, triage, review and end. `DIR/tune.json` is
the summary. Each checkpoint's history row carries `{tune, checkpoint, label}`. The run records its pid in DIR, so
`python -m charkit kill DIR` stops it and the build it started. A checkpoint folder holding the same build (spec, options,
boards, code) is reused; `--fresh` rebuilds.

**The character's tune config** is `charkit/refs/NAME/tune.json`, beside the manifest. Its trade-off rules write out the
manifest's authority table. For Clawd the sheet is the authority for the face's front, 3/4 and profile shape and for the
chin. So `face_shape_width` (against the TRELLIS face, which the key's caution calls rounder and fuller) may get worse
when `sheet_width` gets better, by at most 3x the gain. Depth has no sheet counterpart and is never traded. A `noise`
rule lets a sheet, body or palette check cross its limit by at most 0.15 warn bands (never past WARN) when the
checkpoint gains overall: a flip smaller than the sheet's own error is noise. Without it, geom hair was rejected for
`body_profile_hair_width` moving 0.920 -> 0.914 while three hair lengths reached PASS. The config also holds the build
options, the stop settings and each reference's stated error (`uncertain`: the sheet is good to about a pixel, 0.009 L,
or 3% on a ratio). Its `decisions` record a class people decided for a check, with who and why. The triage puts that
class first and keeps its own beside it: Clawd's `sheet_shown_*` gap after the face fit is a hair capability, because
`scene.cull_face` takes the cheek side locks when the jaw widens.

**Triage** (`charkit/triage.py`; `python -m charkit triage DIR` redoes it for a tune folder or any build). Every check
still WARN or FAIL is classified by why the loop couldn't fix it. The first class that applies wins; the others are
listed as `also`:
- `measurement uncertain`: any of these holds:
  - the fast evaluator predicted a severity the build doesn't reproduce, or disagrees with the final build;
  - the final build didn't repeat;
  - the check reports missing or thin data ("few pixels");
  - the value is within the error the check itself states (a scale caution's percentage) or the reference's stated
    error of passing.

  A standing caution alone (every `body_*` check carries the sheet's scale caution) is listed, not the class.
- `trade-off`: fixing it costs another check. Either:
  - a checkpoint that improved it was rejected because another regressed (built and measured);
  - a rule let it get worse to pay for another;
  - or every knob that improves it worsens another check, per the sensitivity table (which, and how many warn bands
    per step).
- `knob at a bound`: the improving knobs are at their range's end (which, which bound, the value), or would reach it
  before the check passes.
- `needs a knob`: no fitted knob moves it, or every one that does is already at its best for it. The spec's hand knobs
  that may move it (the knob inventory, `checks.SECTIONS`) and the stub fitter that will own them are listed.
- `needs a capability`: it measures a template or geometry matter, not a parameter (`checks.CAPABILITY`). Examples:
  the lid rings' topology, and a mouth cavity that doesn't follow tall openings (`face_folds`); the hair surface's
  normals; garment fitting. An `expr_*` part the expression library has nothing close to (`missing`) is a template
  addition.
- `not in the objective`: a knob improves it at no cost, but no fitter's objective includes the check.

Each item carries its evidence:
- the value, status, sub-values and limits;
- the severity;
- the overlays that show it;
- the reference it is measured against and the manifest's authority for its measure, with the reference's cautions;
- the knobs and conflicts behind its class.

Beside the items, **blocked moves** lists every rejected checkpoint that would have lowered the score: its gain, and
which checks blocked it. Each blocking check is marked as inside a fitter's objective (the fitter traded it) or outside
every objective (a side effect no fitter measures, such as the eye knobs changing the yawn's closed eye). The move is
then decided by adding the check to that fitter's terms, or by writing a trade-off rule.

The list is ranked by severity times visibility (`checks.REGIONS`: the eyes, the face's front and the silhouette first,
face depth and topology last). A reviewer's note multiplies the rank by 1.5; a check measured against a reference
that isn't its measure's authority, by 0.6. It is written to `DIR/work_items.json` (with the knob inventory: every
numeric spec knob and its owner) and `DIR/work_items.md`.

**Review** (`--review`, `charkit/review.py`). Every metric is a proxy: the face checks exist because a person saw what the
numbers missed, so review feeds back into the checks.
- **Board.** `python -m charkit review board BUILD` writes `BUILD/review/board.png` and `index.html`: the design's model
  sheet beside our views, body and face sheets, the QA overlays, and the ranked work items.
- **Notes.** `python -m charkit review serve BUILD` serves the page on 127.0.0.1 and saves notes from it to
  `BUILD/review/notes.json` (and `notes.md`). Served that way, the inspector (`projects/charkit-look`) has a review panel
  that saves a note with the camera it was written from. From the command line:
  `python -m charkit review note BUILD "the face reads long" --view front`.
- **Tickets.** `python -m charkit review ticket BUILD N001` turns a note into a ticket in
  `charkit/refs/NAME/tickets.json` (tracked). The note's words are matched against `review.CONCERNS` ("long" with "face"
  means the face's length over its width), which name the checks that measure it.
  - **Work ticket.** If any of those checks is WARN or FAIL, the note joins their work items as evidence and ranks them
    up.
  - **Measure ticket.** If they all pass, the metrics missed it. The ticket carries a proposed check (its name, what to
    measure, the views, and the reference that is the authority), the passing checks that should have caught it, and,
    where the QA's tables already hold the numbers, the proposed measure's value now. For example, the face's length
    over its width against the design's comes from sheetqa's chin and widths.
  - The triage lists every open measure ticket as `needs a measurement` until a check of that name appears in a build's
    QA. `python -m charkit review tickets NAME --sync` then marks it landed.
  - Where the ticket has a prototype, every triage measures it again on that build (`PROVISIONAL PASS/WARN/FAIL`). A
    reviewer's note is therefore a tracked number from the moment it is ticketed, until the real check replaces it.

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
