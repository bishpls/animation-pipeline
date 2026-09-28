# The 3D pipeline, rethought (research pass, September 2026)

EMBER II (`~/opus-anim-test/b3d`) and Round 5 (`~/opus-anim-test/r5`) built every character, rig and move from scratch in Blender
Python, and each round started over. TSUZUKU showed what a sourced-motion base layer does for a performance. This page is the
redesign: what the field looks like now, what we keep, what we adopt, what we build, and in what order. It condenses five research
passes (Japanese creator tooling, open mocap and motion data, image-to-3D and auto-rigging, Blender and the paid tools, camera
conte), each checked on primary sources where they could be reached. Anything marked *unverified* wasn't.

The rules don't change (CLAUDE.md, CRAFT §0): every frame is authored in code as a pure function of time, video models stay off by
default, one clock, look at everything. One rule is added: **licences are read as commercial.** Every tool and dataset below is
flagged for use in a published, possibly monetised film, and non-commercial ones are for previs only.

## 1. The shape of it

```
 design            reference mesh (optional)        character build (Blender 5.2 LTS, bpy)         runtime + render
 GPT Image sheet ─▶ TRELLIS.2 / Pixal3D (GPU box) ─▶ procedural body, VRM-humanoid skeleton,      ─▶ three.js in render.mjs
                    fit target, never the asset      face decals, spring chains, toon materials       (layout, previs, conte,
                                                     ─▶ glTF / VRM                                    review; final toon?)
 motion                                                                                               Blender EEVEE (final
 directed video ─▶ GEM-X (GPU box) ─┐                                                                  where lines/lights need it)
 BONES-SEED, CMU, 100STYLE ─────────┼─▶ canonical clip (SOMA joints + contacts) ─▶ cleanup ─▶ retarget ─▶ bake on ones/twos
 Kimodo text / keyframes (GPU) ─────┘      physics fixer, keyed accents on top (MOTION.md layers)
 camera
 composition library ─▶ move composer ─▶ baked per-frame camera track (JSON) ─▶ three.js blockout · Blender · video-model ref
```

Three decisions carry the design:

1. **Blender stays the build tool, pinned to 5.2 LTS** (supported to July 2028). Nothing open is close, and it runs headless on
   this Mac today. Its gaps (no retargeter, no animation layers, no physics correction, NPR mid-transition) are exactly what we
   build in code anyway. Godot, Bevy, O3DE, Goo Engine and Malt were considered and skipped; Unreal 5.8 needs macOS 14.5 and is a
   year from a compatibility break (UE6).
2. **One character, two runtimes.** A character is built in Blender and exported as glTF/VRM (skin, morph targets, spring-bone
   metadata). three.js renders it inside `engine/render.mjs`, so 3D gets the same timeline, sheets, strips, `filmscan.py` and motion
   audits the 2D films have, and 2D and 3D composite in one engine. Blender EEVEE remains the final renderer where it wins (Line
   Art, the 5.3 light nodes). Which one renders a given film is a bake-off, not a belief.
3. **Motion has one canonical form.** Every source (video, dataset, generator) becomes the same clip: per-frame world joint
   rotations on the SOMA skeleton, a metric root, and contact labels. Cleanup, measuring and retargeting are written once against
   that form. SOMA because the clean sources already speak it: GEM-X outputs it, Kimodo generates it, BONES-SEED ships it as BVH.

## 2. Motion: the mocap spine

TSUZUKU's chain (Seedance → MediaPipe → a 2D retarget, MOTION.md §4) was the unlock. The 3D version replaces the tracker and the
retarget; the directed reference stays.

**The licence trap.** Nearly every well-known video-to-3D model (GVHMR, WHAM, TRAM, PromptHMR, CameraHMR, 4D-Humans, SMPLer-X,
Multi-HMR, CoMotion, Human3R) loads the SMPL body model, whose licence forbids "production of other artefacts for commercial
purposes". There is no carve-out for keeping only the rotations. SMPL commercial licensing moved to Max Planck Innovation after Epic
bought Meshcapade (February 2026); pricing isn't public. GVHMR is the best-validated for foot contact and stays useful as a previs
cross-check only.

**The clean stack (2026):**

| step | tool | licence | runs on |
|---|---|---|---|
| video → 3D body, hands, face joints, world root | **GEM-X** (NVIDIA): SOMA 77 joints, `--static_cam` for locked-off references, contact confidences | Apache-2.0 code, NVIDIA Open Model License weights ("commercially usable"; trained on NVIDIA-owned data); consent clause for filmed people | GPU box; an ONNX + CoreML demo runs on macOS 13 |
| single-image cross-check | **SAM 3D Body** (Meta) + MHR body model | SAM Licence (no commercial bar) + Apache-2.0 | GPU box |
| face | **MediaPipe Face Landmarker**: 52 ARKit-named blendshapes + head matrix | Apache-2.0 | Mac CPU (we already run MediaPipe) |
| foot skate, trajectory | **Kimodo MotionCorrection** (C++ with Python bindings) | Apache-2.0 | Mac CPU (build unverified) |
| repair, extend, in-between | **Kimodo** (text + keyframe/end-effector/path constraints, 10 s max, BVH out); **ARDY** for longer streams | Apache-2.0 + OML (SOMA variants only; the SMPL-X variant is R&D-only) | GPU box (~17 GB) |
| retarget | **Retarget BVH** (Diffeomorphic, v5.2.0, operators scriptable headless, ships rig maps incl. Mixamo, Rigify, mocopi) or our own recipe (below) | GPL | Blender |

**Motion banks** (read as commercial):

| bank | what | terms | use |
|---|---|---|---|
| **BONES-SEED** | 288 h, 142k BVH on the SOMA skeleton: stunts, martial arts, dance, locomotion | free for entities under $1M annual revenue (we qualify, confirmed 2026-09-27); credit "Motion Data by Bones Studio"; no training generative models on it | the main bank |
| CMU Graphics Lab | ~2,500 trials, some martial arts, acrobatics, dance | free for all uses incl. commercial products; no reselling the data | generic dynamics |
| 100STYLE | 100 locomotion styles | CC BY 4.0 | walks and runs with character |
| Rokoko free packs, Mixamo, Quaternius UAL | fight, weapon, dance loops | commercial use allowed; don't redistribute raw files (Quaternius is CC0) | stock moves |
| LAFAN1, Bandai Namco, AIST++, AMASS, HumanML3D, Motion-X, FineDance, Motorica, BEAT | – | non-commercial | previs only |

There is **no commercially clean music-to-dance model** (all train on AIST++/FineDance). Dance stays what TSUZUKU proved: a
directed reference per phrase, tracked, with keyed accents on top.

**Retarget recipe** (if we write our own; the pitfalls are verified): FK the source to world rotations; convert Y-up to Z-up
(`G' = C·G·Cᵀ`, `C = Rx(+90°)`); pose the target into the source's rest pose and record calibration rotations; take world
rotations through the calibration and back to bone-local, parents first (never copy local rotations across skeletons); scale the
root by hip height; foot-lock on the target after retargeting (two-bone IK over contact windows, 3–5-frame blends); write keys through
5.x channelbags (`action.fcurves` is gone since 5.0).

**Directed references, what the camera-conte pass found:** one move per clip, locked tripod, full body in frame throughout, plain
set, fitted contrasting clothes, real-time speed; tag each reference by role in the prompt; and QA every clip before trusting it
(foot velocity during contact, left/right swaps as joint-velocity spikes, bone-length variance, airborne phases that should fit a
parabola under 9.8 m/s²).

## 3. Characters: design, build, rig

The strongest finding here is negative. **No open or paid generator produces topology that deforms well**: every open model
outputs dense isosurface triangles, and the paid "quad" modes give evenly spaced quads without the loops joints and faces need.
Anime characters in particular come back rounded (faces from normal maps, mitten hands, hair as a shell). Round 5's procedural build
(`r5/char.py`: skin-modifier body on an authored joint table, drawn face decals, verlet cloak chains) is already ahead on everything
that matters for animation. No tool, paid or open, rigs a cloak.

So generation joins the build in three narrow places:

1. **A fit target, not an asset.** Turn the GPT Image turnaround into a mesh with a multi-view generator (Pixal3D or TRELLIS.2, MIT;
   swap their bundled RMBG-2.0 matting, which is non-commercial, for pre-matted RGBA). Fit the joint table to it (cross-section radii
   by raycast), then shrinkwrap the procedural body toward it under a falloff, keeping our loops, weights and decals.
2. **Skinning help.** SkinTokens (VAST, MIT) skins a mesh to a skeleton we supply (`--use_skeleton`); Robust Skin Weights Transfer
   (GPL) carries body weights onto a cloak or a game mesh. Bone heat stays the default where it works.
3. **Props, sets and creatures that don't deform (or deform rigidly):** generate, then QuadriFlow or QuadWild Bi-MDF (arm64 CLI) to
   budget, xatlas UVs, and StableGen (GPL; Blender on the Mac, ComfyUI on the GPU box) for textures.

The **skeleton contract** is VRM 1.0 humanoid naming for our characters (the Japanese ecosystem's standard: three-vrm with MToon
and spring bones on the web side, the VRM Add-on for Blender, VRoid bases, Tripo's and Mixamo's maps). Motion is retargeted
SOMA → VRM humanoid once, then onto each character. Fixed game skeletons (Geno) keep their own contract and get a map.

Tripo is what Japanese creators use now (agents drive Blender through bpy or Blender MCP on Tripo meshes, rigged by Tripo, Mixamo
or Auto-Rig Pro, exported as VRM). Its reputation: clean P2 quad meshes, rigging "much better", weak textures, shaky shoulders, anime
"still not quite there", and many of the positive posts are sponsored. At about $0.65 per textured, low-poly, rigged model it's
worth buying a handful as a benchmark against our own build; it isn't the build.

## 4. Camera: the conte tool (Remotion not needed)

The trend the brief quoted is @Kashiko_AIart's (28–29 August 2026): Codex built a Remotion/SVG catalogue of 30 compositions, rendered
an ID sequence as one continuous gray-box move, and gave that MP4 to Seedance 2.5 as the reference. Remotion adds a React layer over
what `render.mjs` already does (pure-function frames in headless Chrome) and is free only up to three employees; a few of its ideas
are worth taking (a per-frame ready handshake like `delayRender`, FFmpeg frame extraction for video textures).

Ours, built on three.js in `render.mjs`:

1. **Composition library** (`comps/*.json`): each composition is defined relative to the subjects, not in world space: framing
   target (`A.head`, `mid(A,B)`), azimuth from the A→B line or A's facing, elevation, shot size as the primary subject's screen
   height, screen anchors, focal length, roll. A solver places the camera ("toric space", Lino & Christie 2015). A contact sheet
   renders the whole library with cyan/orange mannequins.
2. **Move composer:** a composition sequence becomes a centripetal Catmull-Rom path in pivot-relative spherical coordinates (orbits
   stay orbits), a separately smoothed look-at, log-space FOV, a damped roll channel, and minimum-jerk timing. Validators cap
   speed, acceleration and angular rate (a "teleport" gets a waypoint or more time), keep subject scale monotonic between keys,
   and flag occlusion and 180° crossings.
3. **Baked track:** per-frame position, quaternion, vertical FOV and focus in one JSON. It's the only thing any renderer reads.
4. **Renderers:** the three.js blockout (passes: review with burn-ins, clean gray reference, depth, normal, line art, ID), and a
   Blender importer (LINEAR keys every frame, Y-up to Z-up, vertical sensor fit, `lens = sensor_h / (2·tan(vfov/2))`). A
   round-trip test projects markers in both and must agree within about 1 px.
5. **Model adapters, for when a video model is signed off:** Seedance 2.5 takes gray blockouts natively but follows the camera
   approximately; where frames must register with a Blender render, depth- and pose-conditioned open models (VACE, Wan Fun Control)
   on the GPU box hold the camera exactly. Clean passes only (overlays bleed into outputs), low-frequency camera motion only.

The mannequins in the blockout get real motion from §2, so a conte is also a motion review.

## 5. The look: anime NPR in 3D

- **Now (5.2):** Round 5's emission toon (art-directed N·L ramp, fresnel rim, fog), inverted-hull outlines, drawn face decals.
- **Add:** an SDF face-shadow threshold map (SciPy distance transforms of a few drawn masks, compared against the light projected
  on the head axes: the Genshin approach), and face normals from a head-parented ellipsoid through Set Mesh Normal in tangent
  space (the Guilty Gear Xrd idea, done in Geometry Nodes).
- **Blender 5.3 (November 2026)** ships material lighting nodes (Light Info, Light Evaluation, Shadow Raycast): a real per-light
  loop in vanilla Blender, which is what Goo Engine was for. Port the toon shader when it lands; production stays on 5.2 until then.
- **Lines** are the biggest quality gap to the studios' standard, Pencil+ 4. Build: Line Art (or ID/normal/depth edges from
  three.js render targets) → per-frame polylines as JSON → strokes in the skia compositor with pressure, taper and jitter, the way
  Round 5's `comp/` already draws smears.

## 6. Paid tools: what they have, and what building it takes

Ranked by value for effort. Effort assumes Claude Code does the building.

| paid tool | the capability that sets it apart | closest open thing | build our own | effort | value |
|---|---|---|---|---|---|
| **Cascadeur** AutoPhysics / Ballistic ($96/yr indie; runs on macOS 13.3) | corrects keyed motion to physics: centre-of-mass parabolas in flight, angular momentum conserved, contact phases colour-coded (ballistic, weak, strong, impossible) | none | A: detect airborne spans, replace root motion with an exact parabola under g, counter-rotate to hold whole-body angular momentum about the COM (NumPy, in the retarget bake). B: contact phases (support polygon, friction cone) and full trajectory optimisation with Pinocchio + Crocoddyl (BSD, arm64) | A 3–5 d, B 3–6 wk | **high** (the physics-grounded fights rule) |
| **Pencil+ 4** (Line free, Render App ¥67,760; macOS 13) | anime line sets: per-brush width, taper, distortion, hidden-line styles, vector output; used by Toei, Shirogumi, Khara | Blender Line Art, Freestyle, inverted hull | lines → JSON polylines → skia strokes (§5) | 1–2 wk | **high** |
| **Move.ai, Rokoko Vision, Autodesk Flow Studio** (RADiCAL shut down July 2026) | markerless capture with foot-lock filtering, delivered as FBX | FreeMoCap (multi-cam), XR Animator | the §2 chain | 1–2 wk | **high** |
| **AccuLips / AccuFace** (Windows only) | audio lip-sync with many lip morphs; webcam face capture | Rhubarb; MediaPipe blendshapes | our lips (`MOVES.lips`, `vocalenv.py`) already beat it for drawn mouths; add MediaPipe blendshapes → brow and eye decal states | 2–4 d | high |
| **Cascadeur** AutoPosing | a whole-body pose from a few pinned controllers (learned) | none (ProtoRes code isn't public) | IK with effector targets + a pose prior learned from our own clean pose library (PCA or a small VAE; not LaFAN1, not AMASS) | 2–4 wk | medium |
| **Tripo, Meshy, Rodin** | native low-poly/quad generation, parts, T-pose conversion, auto-rig incl. non-bipeds, one API | TRELLIS.2, Pixal3D, TripoSG, PartCrafter, SkinTokens, QuadriFlow | the §3 chain | 5–8 d | medium (props), low (heroes) |
| **Maya** (+ MotionBuilder) | HumanIK retargeting, animation layers, the graph editor | Retarget BVH, NLA | our motion is layered in code already (MOTION.md §2) | 1–3 d | medium |
| **Houdini** (KineFX, Vellum) | procedural rigs across skeletons, cloth and hair solvers | Blender 5.2 XPBD physics nodes (experimental) | extend 5.2's closures; the verlet cloak stays | 1–2 wk | low |
| **Marvelous Designer** | sewing flat patterns into garments | GarmentCode (MIT) + XPBD | pattern → sewn mesh → drape → bake to bone chains | 2–4 wk | low (cloak solved) |
| Unreal (MetaHuman, Control Rig, Motion Matching), Substance, ZBrush, Character Creator | realistic humans, painting, sculpting | – | not our look | – | skip |

Worth buying: **Cascadeur Indie**, if its Python API or MCP server can run AutoPhysics in batch (test on the free edition first).
Pencil+ 4 Render App only if our line renderer disappoints. A little Tripo API credit as a benchmark.

## 7. Where compute runs

This Mac (M2 Pro, 16 GB, macOS 13.5) runs Blender, three.js, MediaPipe and the CPU cleanup. Nothing neural runs on it: since
PyTorch 2.9, MPS needs macOS 14. **A macOS upgrade is the cheapest unlock available**: MPS back, MLX (trellis2mlx runs TRELLIS.2 on
exactly this machine in about 21 minutes), and Maya/Marvelous/ZBrush/Unreal become installable. 16 GB stays tight either way.

Until then, **torch 2.8.0 still has MPS on macOS 13.5** (measured: a 4096² matmul in 29 ms on MPS against 98 ms on CPU); only
repos that need torch 2.9 or later are blocked.

Everything CUDA runs on the GPU box (`infra/gcp/`): one L4 (24 GB) by default, bigger cards by changing the machine type. It sits
on a VPC of its own with SSH only through IAP and no external IP, under a service account that can write only its own bucket,
because research repos run arbitrary code. It stops itself after 30 idle minutes. `infra/gcp/gpu.sh up | ssh | push | pull | stop`.

## 8. Build order

Each phase ends in something to watch, reviewed the usual way (sheets, strips, full passes).

1. **The mocap spine.** *Done, 2026-09-27 (projects/clawd3d).* GEM-X runs on the GPU box (`tools/mocap3d/`): all 13 of
   TSUZUKU's directed references tracked, about 2 min and 9.3 GB of VRAM per 5 s clip on an L4, no left/right swaps, feet
   within 1.5 cm of the floor after a floor lock (GEM-X's height wanders up to 14 cm in 5 s). Fingers are placed well but
   articulate poorly: keep keyed hand shapes. The canonical clip is `<name>.clip.npz` (`soma_clip.py` documents it). Retarget
   in armature space with a rest-pose calibration; the test shot (bars 58–66, two phrases time-warped by the 2D film's anchors)
   is `projects/clawd3d/shots/dance_test.py`. Still to add: `motion_audit.py` on 3D joints, keyed accents over the mocap.
2. **The camera conte.** Composition library + contact sheet, move composer + validators, baked track, three.js blockout in
   `render.mjs` with the phase-1 mannequins moving, Blender import, the round-trip test. *A drone-style one-shot of two dancers.*
3. **The character kit.** Round 5's builder promoted into reusable modules (body from a joint table, decals, spring chains, toon
   materials, VRM export); reference-mesh fitting; SkinTokens and weight transfer as helpers. Round 5's source is in
   `legacy/ember/r5/` (the full round, shots and score included, is in the EMBER repo).
4. **The physics fixer** (Cascadeur-style A) in the bake: parabolas and momentum on every airborne span.
5. **The look and lines:** SDF face shadow, face normals, the line pipeline; the three.js vs EEVEE bake-off.
6. **A pilot shot** that uses all of it.

## 9. Open questions

- **BONES-SEED access:** we qualify, but the dataset is gated: a Hugging Face account, token and the access form (name,
  affiliation, work email, intended use, the revenue checkbox), and the BVHs come only as 45 GB tarballs (SOMA layout, but
  centimetres, 120 fps, bind-pose-relative: `soma_clip.py` needs a BVH input mode). Its raw files must never enter this repo.
- Does GEM-X's hand and face output hold up on generated references? What are its speed and VRAM on an L4? (Phase 1 answers both.)
- Does Cascadeur's API run AutoPhysics headless?
- WebGPU in headless Chrome on macOS 13 (else WebGL2, which three.js falls back to).
- Unverified licence details: Mixamo's current redistribution/AI terms; Tripo's paid-tier output terms; StdGEN's checkpoints
  ("research only" in the README vs Apache-2.0 on Hugging Face).

## Other finds

- **JIZURA** (852wa, MIT) isn't a 3D tool: it's a browser app that builds lyric videos from lyrics and audio, deterministic from a
  seed, rendered on Canvas2D, exported with WebCodecs. Its registry of 860 drop-in parts (layouts, motions, 36 camera moves) is a
  good pattern for our own engine, and its smoke test drives it headless from Playwright. The same author's Anime2.5DRig (MIT)
  auto-rigs a layered PSD, and See-through (SIGGRAPH 2026, Apache-2.0) splits an anime illustration into up to 23 inpainted layers:
  both relevant to the 2D rigs (RIGGING.md), not to 3D.
- **Seedance 2.5** takes untextured 3D blockouts ("white model") as reference and single shots up to 30 s; a creator has an LLM
  build the Blender blockout for it. It interprets the camera rather than matching it.
