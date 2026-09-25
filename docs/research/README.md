# Research: the animation toolbox (September 2026)

Three research passes commissioned for the idol-group sequels, to push code-native animation past "soulful amateur". Each section below is a condensed version of the full report: the findings, the recommendations and the sources to start from. Treat the licence notes as leads, and verify them before relying on them.

## 1. 2D vtuber-style rigging (the Live2D approach)

**Recommendation.** Build our own small Live2D-style runtime in WebGL (about 1.5–2.5k lines) with rigs stored as JSON that the agent authors, and use Live2D's open Cubism Web Framework as the reference for the math.
- Off-the-shelf runtimes are stateful (`update(dt)`, random blinks), and their authoring tools are GUIs.
- The math is small, and AI layer-decomposition tools now produce rig-ready layer stacks.

**How Cubism works.**
- **Parameters:** standard IDs, e.g. `ParamAngleX/Y/Z` ±30, `EyeL/ROpen`, `EyeBallX/Y`, `MouthOpenY`, `MouthForm`, `BodyAngleX/Y/Z`, `Breath`, `HairFront/Side/Back`.
- **Structure:** ArtMeshes (textured triangle meshes with a draw order, clip masks and blend modes) hang under nested **warp deformers** (Bézier lattices) and **rotation deformers**.
- **Keyforms:** each node stores keyforms at key values of up to 3 parameters, and the runtime blends them multilinearly. "Extended interpolation" arcs rotations.
- **The 3D-ish head turn** is hand-drawn keyforms: far features compress, near ones widen, eyes and nose move more than the outline, and back hair moves the opposite way. That is parallax by depth.
- **Physics** is a Verlet pendulum chain driven by weighted head/body inputs, whose outputs feed the hair parameters. It runs at a fixed step of 1/fps with a pre-settle. Source: `cubismphysics.ts` in CubismWebFramework.

**Aliveness defaults** (from Cubism's `lappmodel.ts`):
- **Breath:** sines on AngleX ±15 over 6.5345 s, AngleY ±8 over 3.5345 s, AngleZ ±10 over 5.5345 s, BodyAngleX ±4 over 15.5345 s.
- **Blink:** close 0.10 s, hold 0.05 s, open 0.15 s, about every 4 s. Better with an eased close and a slower open, occasional double blinks, and blinks timed to head turns.
- **Saccades:** hold the gaze 0.3–2 s, jump in about 2 frames; the head follows the eyes 100–200 ms later.

**Existing runtimes and licences.**

| Runtime | Can render frame by frame? | Licence and fit |
|---|---|---|
| Cubism Web SDK / untitled-pixi-live2d-engine (Pixi v8) | Yes, if stepped from 0 at a fixed dt with seeded blinks | Publication licence free under ¥10M a year. `.moc3` files need the Cubism Editor GUI |
| Inochi2D | Web runtime is immature | BSD-2; the best open format spec to copy |
| Spine 4.2 | Yes; has physics constraints | Runtime needs an editor licence |
| Rive | Yes (`advance(dt)`) | Runtimes MIT, but files need its editor |
| DragonBones | Yes | MIT; no physics |

Stretchy Studio (MIT: PSD to mesh to DWPose auto-rig to Spine) is worth mining for mesh and skinning code.

**Our runtime.**
- **Rig JSON:** params, nodes (warp lattices, rotation deformers, meshes with verts, UVs and triangles), per-node parameter bindings and keyforms, and physics chains.
- **Pose(t):**
  1. params from the timeline and the procedural layers (breath, seeded blinks and saccades, lip-sync)
  2. physics outputs
  3. keyform blend
  4. deform children in parent space (bilinear lattice / affine)
  5. draw in order, with stencil clip masks and premultiplied alpha
- **Physics as a function of t:** step at 1/120 s from t=0 and checkpoint every N steps. Single accessories can use a closed-form damped oscillator.
- **Procedural head turn:** give each layer a depth (back hair −0.3, face 0, eyes/nose +0.08, bangs +0.12), and generate the AngleX/Y keyforms by projecting the lattice onto a cylinder with depth parallax.

**Layered art.**
- **Manual:** the PSD split (eye parts, lash corners, eye white as a clip mask, mouth lips/interior/teeth/tongue, brows, face/ears/nose, hair strands, limb segments) with every region that might be revealed painted in underneath.
- **AI:**
  - **See-through** (SIGGRAPH 2026, Apache-2.0 code; check the weights licence): one anime image to up to 23 inpainted semantic layers with depth. Needs 8–16 GB of VRAM.
  - **Qwen-Image-Layered:** generic RGBA layer decomposition.
  - **Bunraku:** single image to rig research; no code found.
  - **SAM 3:** masks. **LayerDiffuse:** transparent parts.

**Quality.**
- **Frame rate:** 24 fps, key poses on twos, physics, camera and lip-sync on ones.
- **Anticipation:** 8–12% counter-move over about 4 frames, then 5–10% overshoot.
- **Lead order:** the body leads the head by 2–3 frames, the eyes lead by about 3.
- **Visemes** A/I/U/E/O plus closed and rest, from word or phoneme timestamps, starting 1–2 frames early. Rhubarb (MIT) as a fallback.
- **Limits of 2D:** about ±30° head and ±10–15° body. Full turns need view swaps at cuts or whip-pans.

## 2. Anime-style 3D (three.js + VRM)

**Recommendation.** three.js with @pixiv/three-vrm; a character made in VRoid Studio or a CC0 VRoid sample; Mixamo/CMU mocap retimed to the beat grid; a custom toon shader; rendered frame by frame in Puppeteer. The ceiling is set by the **assets** (model and motion) and the **direction**, not the renderer. The rough EMBER 3D came from procedural modelling and motion.

**The anime look.**
- **Cel shading:** one main light, a steep two-tone ramp, artist-chosen shadow colours. Guilty Gear Xrd biases the threshold per region with vertex colours.
- **Face normals:** transferred from a sphere or ellipsoid (in three.js: set the normal in the vertex shader from a head-space ellipsoid centre). Or a Genshin-style **SDF face-shadow map**, which an agent can generate by rendering 9 light angles and running a distance transform.
- **Outlines:** a GG-style inverted hull (per-vertex width, depth offset, compensation for camera distance and FOV, smoothed normals), or a Sobel pass on depth, normals and IDs. No TAA.
- **Rim and hair:** a Fresnel rim masked to the lit side; hair "angel rings".
- **Limited animation:** hold motion *extremes* snapped to beats for 2–3 frames with ones between; don't quantise uniformly. Keep cameras on ones. Per-shot cheat layers: head and eyes to the lens, long lenses (35–50° vertical FOV or narrower) for faces. Hi-Fi Rush lands key poses on beats.

**Getting a character.**
- **three-vrm** has humanoid bones, expressions (aa/ih/ou/ee/oh, blink), look-at, spring bones and MToon, and its official example retargets Mixamo FBX.
- **Best model source:** about an hour of a human in VRoid Studio. VRoid-made models, presets included, are usable commercially; verify the FAQ.
  - CC0: the β AvatarSample_1–4 models.
  - AvatarSample_A–C: free to use, but check the terms.
- **Blender VRM Add-on** (supports Blender 5.2, has a scripting API): recolour, swap materials, transfer normals, paint outline widths. Procedurally generating new hair or outfits at VRoid quality is not realistic.

**Motion licences.**

| Source | Terms |
|---|---|
| Mixamo | Royalty-free for films; no redistribution of raw files |
| CMU | Commercial use OK |
| AIST++ | Annotations CC BY 4.0, but the SMPL body model is non-commercial |
| Bandai Namco dataset | Non-commercial: avoid |
| MMD motions | Per-author permission only |
| VRoid .vrma pack | Commercial use with credit |

MMD videos look good because the motion and camera are **authored to the song**.

**Motion pipeline.**
1. Retarget: map bones to VRM humanoid names, apply rest-relative quaternions, scale by hip height.
2. Beat-sync with a monotone time warp pinning source downbeats to song downbeats (±10% tempo); stitch clips with pose-matched crossfades on phrase boundaries.
3. Layer on foot-contact IK locks, spring bones, look-at, seeded blinks and Rhubarb visemes.

**Determinism.**
- Pre-bake spring bones: simulate at 1/120 s from 0, write per-frame joint quaternions, reset at hard cuts, and pre-roll 1 s before each shot. Feed the springs the *stepped* pose.
- Render through `renderAt(frame)`, at 2× resolution then a lanczos downscale (or MSAA 4 + SMAA). Selective bloom, diffusion, vignette; depth of field only in close-ups.

**Honest ceiling:** good-vtuber or better-than-MMD, about 6–7 out of 10 against Project Sekai MVs, if camera and compositing are strong. Top risks, in order: dead or noisy faces, foot sliding, weak or repetitive dancing, clipping, missing finger mocap, and licences.

## 3. Code-native aesthetics and music

**Frameworks.**
- **Skip:** Remotion, Motion Canvas and Revideo duplicate our engine.
- **Read:** HyperFrames (Apache-2.0), for its adapter contract.
- **Adopt when needed:**
  - flubber or GSAP (now free) for path morphing and per-character text, always driven by `seek(t)`
  - Theatre.js (the studio is dev-only AGPL) for human-tuned hero keyframes
  - Lottie as an import path (`goToAndStop` is deterministic)

**Highest-leverage additions, ranked.**
1. **A retro raster stage.** Render small, quantise to a palette (image-q, CIEDE2000), dither, upscale with nearest-neighbour.
   - PC-98 is 640×400 with 16 colours from a 4096-colour space.
   - Use ordered or blue-noise dither on moving things and error diffusion only on stills. Tie the dither to world space (Obra Dinn).
   - Saturn-style mesh transparency.
2. **Analog finishing.** ntsc-rs (a real VHS/NTSC chain from the command line) plus a libretro CRT shader (crt-royale, crt-guest).
3. **Better audio features.** allin1 (beats, downbeats and labelled sections; has an MLX port), stems (Demucs or the ElevenLabs stem API), and per-stem onsets. Drive motion by beat and bar *phase*, anticipate 1–2 frames before the downbeat, and give each character an instrument stem to follow.
4. **A shader/SDF layer.**
   - IQ 2D SDFs for blob and vector characters.
   - Raymarched characters (IQ's "Selfie Girl") for one hero member only.
   - WebGPU/TSL for a million particles; keep them closed-form in t for determinism, and check that headless WebGPU works.
5. **Painterly.** An anisotropic Kuwahara pass (Maxime Heckel's walkthrough) plus p5.brush strokes re-seeded on twos.
6. **Shape-matched ASCII.** rummy (6-D glyph shape vectors) and textmode.js, as a terminal-native member.
7. **Path morphing and SplitText-style lyrics.**
8. **Theatre.js** for human-tuned hero moments.

**Leitmotifs with ElevenLabs.**
- Give each member a stored 8–20 s "theme card".
- Condition their sections on it (`conditioning_ref`, up to 30 s, strength high/xhigh), or splice it in literally as an audio-reference chunk.
- Plan key and BPM relationships between members.

**Duets.**
- **Recommended:** generate the song, split out the vocal stem, then convert each singer's lines to a *fixed* voice with singing voice conversion (Seed-VC's 44k singing model, or RVC). This locks each member's timbre across songs and gives per-singer stems for lip-sync. Check the model licences.
- **Cheaper:** per-section vocal descriptors (voices drift between songs).
- **Most controllable:** score-driven singers (ACE Studio, Synthesizer V).
- **Also:** Suno can't lock two personas in one generation. ACE-Step 1.5 runs locally.
- **Licence:** ElevenLabs paid plans cover YouTube and social video, not streaming platforms.

## 4. Measured: how professional 2D rigs couple head, neck and body (September 2026)

Live2D's official sample rigs (Hiyori, Haru, Mao, Natori, from CubismWebSamples) were evaluated in Cubism Core 5.1 and every mesh measured at each parameter's extremes and in pairs. Statistics are in `live2d/coupling.json`, our scripts in `live2d/scripts/` (the models themselves aren't redistributed: fetch them from the repo). Units: face-outline width W and height H.

- **Head parameters stop at the neck.** AngleX/Y/Z move the collar, shoulders, chest and arms by exactly 0. The neck's hidden top follows 0.03× of a turn, 0.24× of a nod, 0.49× of a tilt (0.16× mid-neck, 0 at the collar): the jaw slides over a neck drawn up under it.
- **AngleZ** is a rigid rotation, about 0.33° per unit (±30 → ±10°), about a point 0.075 H above the chin. Hair 0.85× plus physics.
- **AngleX/Y parallax** (per unit, times the outline's shift of 0.0029 W for X, 0.0017 H for Y): nose 2.0, mouth 1.5, eyes 1.4, front hair 1.35, side hair 0.9 (1.3 for Y), ears 0.5, back hair ~0 (0.5 for Y). Diagonals are drawn, not summed.
- **BodyAngleZ** is a progressive bend, 0.49° per unit: the block from the shoulders up rigid at 1.0, chest 0.8, waist 0.47, skirt 0.32, legs 0; the block pivots ~1.4 H below the chin.
- **BodyAngleX** is a turn drawn as a shear peaking at the chest centre (0.0125 W per unit): head, neck and collar 0.3× (a pure shift), shoulders 0.3×, waist 0.8×, skirt 0.52×, legs 0.18×.
- **Breath** raises the head 0.0105 H; shoulders 0.76×, chest 0.68× (and 1–2% wider), waist 0.13×.
- **Nesting** (exact): BodyZ rotation → body warps (X, Y, breath) → neck → AngleZ (chin pivot) → AngleX/Y face warp → parts.
- **Timing** (56 official motions): the body moves the same way as the head in 67–89% of motions, at a smaller amplitude (head:body 1.7 for X, 3.6 for Y, 3.55 for Z in parameter units), leading by 0–67 ms; counter-rotation is an accent (~20%).
- **Human gaze** (literature): the eyes do most of a look within ±18°; beyond that the head adds ~0.77° per degree; the trunk joins only beyond ~40°, 300–550 ms after the head. The neck couples a side-bend with rotation to the same side (0.23–0.75 in C2–C7).
