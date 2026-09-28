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
| **export and QA** (`charkit/qa.py`, `export.py`) | boards: turntable, head close-up turntable, expression sheet, viseme sheet, a lighting sweep, range of motion, overlay on the reference, topology stats; VRM 1.0 / glTF export for three.js | | |

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
  - the face, measured from the shape keys' geometry (no render, about 0.04 s): each expression's eye opening against
    neutral and against its intended range (`FACE_EXPECT`), the iris left visible (none in a blink), left/right symmetry,
    each mouth shape's opening (area, width, height, balance), and the distance between the closest two visemes.

When something can only be judged by eye, name the measurement that would close the loop and add it here.

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
