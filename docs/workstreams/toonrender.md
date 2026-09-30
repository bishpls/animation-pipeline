# Workstream: our own toon renderer (`tool/toonrender`)

State: phase 1 done (boards from a build's export, measured against EEVEE, three machines). Phase 2 planned below.

Why: Blender renders are CPU-bound (a still re-evaluates ~130 modifiers); the build box can't render EEVEE, so the QA
draws with a separate numpy rasteriser (`qa3d.draw`) that doesn't match the boards; the web viewer (`look.js`) is a
third renderer nobody had checked. One toon renderer we own should serve the boards, the QA and the web.

## What was built (`charkit/render/`)

| File | What |
|---|---|
| `model.py` | Our export (charkit/gltf.py: VRM + `OPENADS_charkit_look`) read back with numpy + Pillow: primitives, look, outline, textures (SDF's 16 bits unpacked, colour maps to linear). |
| `views.py` | `scene.boards`' views (face 0/30/60/90/150 at 900x900, 85 mm; body 0/35/90/180 at 600x1000, orthographic) and `qa._aim`'s camera, in the glTF frame. The per-view look comes from `charkit.shade` itself (`view_light`, `line_width`), not a copy. |
| `toon.wgsl` | The look as Blender's node graphs compute it: toon3 (half-lambert, linear ramps, lit-side rim by Layer Weight 'Facing', Screen mix), `hair_toon`'s streaks, the SDF face (mirrored map, fringe, blush, ink, face mask), flat, plates (straight vs premultiplied as Blender's image node outputs them), textures multiplied. Textures read by `textureLoad` with our own bilinear / cubic B-spline and EXTEND / CLIP (border zero). Surface = the original surface moved inward by the view's width x the outline factor; hull = the original surface, front faces culled. |
| `normals.py` | Garments' shading normals per line width (below). |
| `resolve.wgsl` | EEVEE's film filter (Gaussian sigma 0.284 x filter_size 1.5 px over the ss x ss supersamples), the sRGB curve, the features pass laid over at 0.55 x alpha in sRGB (`qa.features_blend`). |
| `gpu.py` | wgpu device (Metal / Vulkan / GL, `CHARKIT_RENDER_ADAPTER`), upload, passes: main (surfaces, hulls, blended plates back to front), features (skin as depth holdout at the original surface, features only), resolve, readback. `ids()`: which part and hull each pixel shows. |
| `compare.py`, `page.py`, `__main__.py` | `python -m charkit.render compare BUILD [--open]`: our boards against the build's EEVEE boards, `compare.json`, heatmaps, the review page. `boards`, `bench`, `probe`. |
| `charkit/tests/test_render.py` | Cameras against `qa._aim`'s geometry, the look against `shade`'s, the export read back (a sphere written by gltf.py's own `Writer`), quad normals, and a toon sphere drawn on whatever adapter the machine has (silhouette at the hull, terminator on the light's great circle, determinism). Passes on the laptop (Metal), the render box (T4 Vulkan) and the build box (llvmpipe GL). |

## The stack: wgpu-py

| | wgpu-py 0.32 | moderngl 5.12 |
|---|---|---|
| Licence | BSD-2-Clause; bundles wgpu-native (MIT OR Apache-2.0); cffi MIT, rendercanvas BSD-2, rubicon-objc BSD-3 (macOS) | MIT (glcontext MIT) |
| Laptop (M2 Pro) | Metal | GL 4.1 over Metal (Apple's deprecated GL) |
| Render box (T4) | Vulkan (NVIDIA ICD); lavapipe (CPU); its GL adapter loses the device | not installable: glcontext has no Python 3.14 Linux wheel (its build needs X11 headers, an apt change) |
| Build box (CPU) | Mesa llvmpipe through GL/EGL (already installed); lavapipe would need `mesa-vulkan-drivers libvulkan1` (apt, not done) | same as the render box |
| Shader language | WGSL: the browser's WebGPU language (phase 2: one shader source for the web viewer) | GLSL 330 |

Chosen: wgpu-py. A pure-Python wheel (py3-none) that ran on all three machines with no system change, native Metal on
the Mac, Vulkan on the T4, and a CPU path on the build box; WGSL can be shared with the browser. Installed into the
laptop venv and both boxes' `/opt/anim-build/venv` (by hand, and now in `infra/gcp/render-setup.sh` and
`build-startup.sh`, which also install it into an existing venv). No GPL / AGPL / non-commercial anywhere.

## Measurements (build `charkit/out/tr_base`: charkit/spec/clawd.json on the render box, `--boards views,body --vrm`)

Everything below is against that build's own EEVEE boards (T4, Blender 5.2.2, 64 samples) and its own export, at
ss 4 unless said. Review page: `charkit/out/tr_base/toonrender/index.html` (EEVEE | ours | heatmap per board).

### How it got there (all 9 boards; share of pixels more than 8 levels off, streaks excluded)

| Step | >8 levels | what the measurement showed |
|---|---|---|
| first port (look_v5 dev build) | ~0.5-1.0% | streaks placed differently (GPU hash, below); tone patches on garments |
| film filter | sigma sweep 0.30 / 0.38 / **0.426** / 0.47 / 0.55 -> mean 1.22 / 0.87 / **0.76** / 0.82 / 1.03 | EEVEE's Gaussian (0.284 x 1.5 px) is the minimum: the filter model is right |
| geometry | positions match Blender's evaluated meshes to 1 um; the outline's inward move is linear in width to 2e-7 m; hull == original surface exactly | measured in Blender on tr_base's .blend |
| garment normals (recomputed per width, triangles) | body 0.78% -> 0.42% | Blender recomputes an outlined object's normals after the SOLIDIFY moves it; the export stores the outline-off ones (collar: p90 147 deg apart at the body width) |
| quads (Newell normals) | face 0.43 -> 0.39%, body 0.41% | normals match Blender's to p99 0.05 deg (triangles: 1-93 deg on twisted quads) |
| ss 6 (option) | 0.18-0.33% | the rest is mostly anti-aliased line edges: 16 regular samples vs EEVEE's 64 jittered |

### Per board (ss 4)

| board | max | mean | >8 lv | mean excl. streaks | silhouette IoU | ink mean width EEVEE / ours (px) | ink ratio | tones agree |
|---|---|---|---|---|---|---|---|---|
| face_000 | 101 | 0.683 | 0.389% | 0.633 | 0.9997 | 1.626 / 1.637 | 0.998 | 0.99959 |
| face_030 | 101 | 0.720 | 0.444% | 0.642 | 0.9998 | 1.632 / 1.629 | 0.997 | 0.99958 |
| face_060 | 115 | 0.774 | 0.451% | 0.626 | 0.9999 | 1.593 / 1.596 | 0.998 | 0.99977 |
| face_090 | 101 | 0.712 | 0.393% | 0.597 | 0.9998 | 1.490 / 1.495 | 0.995 | 0.99977 |
| face_150 | 101 | 0.636 | 0.415% | 0.504 | 0.9999 | 1.602 / 1.620 | 1.000 | 0.99975 |
| body_000 | 100 | 0.846 | 0.411% | 0.839 | 0.9991 | 1.555 / 1.553 | 0.999 | 0.99974 |
| body_035 | 100 | 0.857 | 0.405% | 0.846 | 0.9993 | 1.554 / 1.544 | 0.998 | 0.99945 |
| body_090 | 100 | 0.836 | 0.291% | 0.811 | 0.9992 | 1.592 / 1.590 | 0.999 | 0.99979 |
| body_180 | 100 | 0.818 | 0.396% | 0.804 | 0.9993 | 1.555 / 1.548 | 0.995 | 0.99964 |

Reading them:
- **The floor.** EEVEE dithers its 8-bit output: 1 level on ~80% of flat background pixels (mean 0.8 there). Flat
  interiors agree within 2 levels everywhere; a mean under 1 level is at the dither floor.
- **The tail.** >24 levels: 0.026% of all pixels (1676 over 9 boards): 35% on line edges, 10% on part edges, 55%
  interior, almost all on the hair (below). >8 levels: 0.28%: 67% on line edges (sub-pixel anti-aliasing), 25%
  interior (hair tone patches, skirt texture pleat lines: Blender mipmaps the 1024 px texture, we supersample).
- **Lines.** The ink's coverage-based mean width agrees within 0.02 px on every board; the ink area within 0.5%.
- **Tones.** 99.95-99.98% of classified pixels (91-97% of the picture) get the same tone. Per-class IoU of the small
  classes (deep 0.56-0.96, flat 0.54-0.88) is low only because they are slivers of a few hundred pixels; within 1 px
  75-95% of them match; the rest are scattered at grazing angles.
- **Max ~100** on every board is a line edge off by part of a pixel (ink against a light surface is ~220 levels).

### Speed (seconds per board, warm; ours at ss 4)

| where | ours: face / body | EEVEE |
|---|---|---|
| laptop, M2 Pro (Metal) | 0.018 / 0.012 (ss 6: 0.032 / 0.016) | 2.0 s a still (handoff) |
| render box, T4 (Vulkan) | 0.036 / 0.023 (ss 6: 0.057 / 0.030) | in this build: 5.3 (face, batched, features pass included) / 3.8 (body, batched); the handoff's saved-scene numbers 2.2 still, 0.53 batched |
| render box CPU, 8 vCPU (lavapipe, Vulkan) | 6.6 / 3.9 | - |
| build box CPU, 32 vCPU (llvmpipe, GL) | 1.60 / 1.07 | software EEVEE: minutes a board (why it skips boards) |

Setup (load the export, upload, compile) is 1.2-2 s once per process; the first frame 0.2-2 s. The garment normals cost
under 10 ms per line width (numpy), cached per width.

### Across machines (ours)

The same nine boards drawn on each machine, against the laptop's (M2, Metal):

| machine | pixels bit-identical (min / mean over boards) | max diff |
|---|---|---|
| build box, llvmpipe (GL) | 99.851% / 99.918% | 31 |
| render box, lavapipe (Vulkan) | 99.839% / 99.918% | 24 |
| render box, T4 (Vulkan) | 98.428% / 98.952% | 24 |

The differing pixels sit on part and line edges (rasteriser ties). The T4's extra ~1% differ by one level (rounding:
0.013% of its pixels differ by more than 2 levels); not yet traced to a function. EEVEE itself isn't the same across GPUs (the streak hash, below).

## Findings for other workstreams (the look is paused; these are for it and the integrator)

1. **The streak hash is GPU-dependent.** `hair_toon` keeps a column by `fract(sin(i k) 43758.5453)` with i k up to
   ~2700 rad: every GPU's `sin` reduces such arguments differently. Emulating NVIDIA's (argument scaled to
   revolutions in float32 first, `gpu.streak_table(..., 'nv')`) recovers some of the T4's columns, not all. So EEVEE on
   the laptop, on the T4 and look.js in a browser all place the streaks differently. Fix in the look: an integer hash,
   or the kept columns and elevations exported as a table (the export already carries the parameters). Ours computes it
   exactly (`f64`) and the comparison measures streaks apart.
2. **Screen lines turn thin garment shells inside out on the body boards.** The outline SOLIDIFY moves every surface
   inward by the line width: 3.6 mm at the body boards' scale, 0.93 mm on the face boards, 1.2 mm build. The garments'
   'thick' shells are 1.5-3 mm, and both of a shell's layers move toward each other, so wherever twice the width passes
   the shell (every garment on the body boards; the 1.5 mm shorts and 2 mm sleeves at build width) the layers cross
   and Blender's recomputed normals turn by up to 180 degrees (the collar's p90 147 degrees on the body boards). The
   tones on the collar, top and overskirt panels there come from crossed layers. Worth a look decision (cap the inward
   move at a share of the shell, or no inward move for garments).
3. **The export doesn't carry the normals Blender renders.** Garments: the export stores the outline-off normals; the
   render uses the moved surface's (we recompute them, exactly). Hair and skin: normals transferred after the outline
   are re-sampled at the moved surface (hair_bangs p99 7.8 deg at build width, 12 deg at the body width; skin 1-4 deg),
   which the export can't carry: the remaining hair tone patches. Options: export the transfer sources, or the look
   transfers before the outline in a way the SOLIDIFY keeps.
4. **look.js differs from Blender** (not measured in a browser yet): its hull goes out from POSITION by the screen
   width, but the surface stays at the build width, so silhouettes grow by w_view - w_build (+1.5 px on the body
   boards); garments use the export's normals (above); the streak hash is the browser GPU's; its line width uses the
   camera-to-head distance, Blender's the target's.
5. **The fringe map is exported at 8 bits** (the SDF at 16): ~2% of its 0.35-0.55 ramp per step. Minor.

## Phase 2 plan

**A. The QA draws with this renderer** (replacing `qa3d.draw` / `draw_view` / `draw_lit` and lookqa's frames).
1. Input: make `--vrm` part of every build (measure its cost on the build box first) and give the QA a
   `render.Renderer` over the export; the bundle stays for the geometry measures. Keep the numpy draw until 2-4 pass.
2. Buffers the QA reads, as extra targets of the same passes: part id (done: `ids()`), hull mask, tone class (0 lit ..
   2 deep, face lit / shade), depth, linear colour before the filter, per supersample. Orthographic views at the
   design's px per L (lookqa's `HeadFrame`), sub-pixel frame offsets, and several lights in one pass (face_noise's sweep).
3. Calibrate like any new check (process decision 2 and 3): each QA measure on the numpy draw and on ours for the same
   builds; old measure / new measure x old geometry / new geometry (the 2x2); the design's own values unchanged.
4. Trustworthy local loops (decision 5): the standing test compares the laptop (Metal) against the build box
   (llvmpipe) on the same build; today 99.85%+ bit-identical, the rest on rasteriser ties. Make it bit-identical or
   bound it per measure.
5. Speed target: lookqa's line_width (59 s) and face_noise (29 s) are numpy draws; on the GPU each is milliseconds,
   on the build box's llvmpipe about a second.
6. Boards from builds on the build box: `scene.boards` (or `cli build --boards-renderer toon`) calls charkit.render,
   with the EEVEE comparison as a standing parity test on merges; EEVEE boards stay available on the render box.
   Needs expressions and mouths: apply the export's morph targets (the loader reads them) and the head's light in
   head space for posed heads (skinning).

**B. The web viewer matches.**
1. Measure look.js with the same `compare`: render the board views headless in Chrome (projects/charkit-look's
   harness) and diff against EEVEE and ours.
2. Converge on one shader: the browser runs WGSL natively, so the ambitious path is to draw the character in the web
   viewer with `toon.wgsl` and the same passes (a small WebGPU host) instead of three.js TSL materials, keeping
   three-vrm for the skeleton, expressions and look-at. The cheaper path ports the fixes above into look.js.
3. The look-side fixes (findings 1, 3, 5) make all three renderers agree by construction.

## Open items

- The streak hash (finding 1) and the crossed garment shells (finding 2) need look decisions.
- Hair and skin normals re-sampled after the outline (finding 3): the export's limit; the largest remaining tone patches.
- Only the build pose, and only the 'views' and 'body' boards: no morph targets or skinning applied yet.
- The analytic hair material (`kind: hair`: ring, gradient, strands) isn't ported (Clawd's spec uses cut pieces); it
  draws as toon3.
- No mipmaps (supersampling instead): the skirt's texture lines differ slightly on the body boards.
- EEVEE's dither isn't emulated (it's noise).
- Without a bundle, the face boards' eye height is the export's head centre (right on code heads, not in general); the
  export could carry `eye_z`.
- The T4's OpenGL adapter in wgpu loses its device (Vulkan works). lavapipe on the build box needs
  `mesa-vulkan-drivers libvulkan1` (apt; not done; llvmpipe through GL works).
