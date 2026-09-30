# Workstream: our own toon renderer (`tool/toonrender`)

State: phase 1 done (boards from a build's export, measured against EEVEE, three machines). Phase 2 in progress on
`tool/toonrender2` (`~/animation-pipeline-toonrender2`): "Phase 2, round 2" below, then the checkpoint before it; the
QA's default drawing is still numpy.

Gate: `python -m charkit remote gate tool/toonrender --into pipeline-3d`: **PASS** at 75fe37b into e11fadb (no check
changed; `test_render.py` ok on the build box's llvmpipe). Later commits touch only `charkit/render/page.py`,
`__main__.py` and these notes.

Why: Blender renders are CPU-bound (a still re-evaluates ~130 modifiers); the build box can't render EEVEE, so the QA
draws with a separate numpy rasteriser (`qa3d.draw`) that doesn't match the boards; the web viewer (`look.js`) is a
third renderer nobody had checked. One toon renderer we own should serve the boards, the QA and the web.

## Since phase 1: the look's calls H and I (tool/look3; docs/workstreams/look.md, round 3)

The renderer mirrors two look changes:
- **The streaks' hash** (finding 1, resolved): `toon.wgsl` computes Jenkins' lookup3 of the column index's float bits
  per pixel (`hash_uint`, `hash_uint2`: Blender's White Noise, which `shade.hair_toon` now uses), instead of reading a
  per-column table computed from `sin()`. The uniform block lost the table (`UNIFORM_WORDS` 80, was 204);
  `gpu.streak_table(hl)` is now the numpy reference (`shade.streak_columns`); `--hash f64|f32|nv` is gone; a highlight
  whose export names another hash is refused. Measured: bit-identical to numpy on Metal and the T4's Vulkan
  (`test_streak_hash_gpu`); streak pixels against EEVEE IoU 0.995, 0.56 levels in their region (were 0.06, 56 levels).
- **The outline's inward move capped** (finding 2, resolved as Michael's call I): a mesh's `outline.maxInward` (the
  export) caps the surface's inward move, `inward(w) = min(w, maxInward)`; `vs_surface` moves POSITION by
  `inward(build) - inward(view)`, `vs_hull` puts the hull `w - inward(w)` outside the original surface, and the skin's
  holdout has its own `vs_holdout` (at co). `Prim.co()` and `normals.Group` use the capped move (the garments' normals
  no longer come from crossed layers).
- `compare` includes the streaks: `diff` is every pixel; `diff_streaks` the streak region (`compare.region_stats`),
  `diff_excl` the rest (phase 1's measure). `boards --no-streaks` renders the streak-free base.
- Tests: `test_streak_hash`, `test_streak_hash_gpu`, `test_line_cap`, `test_sphere_thin_shell` (a capped sphere's
  silhouette at r + w - cap and its line still w wide), `test_sphere_streaks` (the kept columns are
  `streak_columns`'). All pass on the laptop (Metal) and the render box (T4).
- Findings 3 and 5 stand. Finding 4 (look.js): its surface now moves per view as Blender's does (for `_HULL_NORMAL`
  meshes along that attribute, exact in the build pose); not yet measured in a browser.

The acceptance on the tool/look3 build (look3_after, render box, ss 4, streaks included): mean 0.51-0.87 levels,
silhouette IoU 0.99904-0.9999, tones agree 0.9993-0.9997 (table in look.md).

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

1. **(Resolved by the look's call H, tool/look3: an integer hash.) The streak hash is GPU-dependent.** `hair_toon` keeps a column by `fract(sin(i k) 43758.5453)` with i k up to
   ~2700 rad: every GPU's `sin` reduces such arguments differently. Emulating NVIDIA's (argument scaled to
   revolutions in float32 first, `gpu.streak_table(..., 'nv')`) recovers some of the T4's columns, not all. So EEVEE on
   the laptop, on the T4 and look.js in a browser all place the streaks differently. Fix in the look: an integer hash,
   or the kept columns and elevations exported as a table (the export already carries the parameters). Ours computes it
   exactly (`f64`) and the comparison measures streaks apart.
2. **(Resolved by the look's call I, tool/look3: the inward move capped at half the shell.) Screen lines turn thin
   garment shells inside out on the body boards.** The outline SOLIDIFY moves every surface
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

- The streak hash (finding 1) and the crossed garment shells (finding 2): done in the look (tool/look3, above).
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

## Phase 2, round 2 (overnight 2026-09-30, `tool/toonrender2`)

In progress. Merged pipeline-3d 08f93e2 (look3's H and I, artifacts, face round 3, geom-truth, nofallback, infra2) at
0f82d34: conflicts in cli.py's docstring and lookqa._scaled (look3's capped outline model kept, with this branch's
`line_k` tag on the scaled surface: toon.wgsl's inward() applies the cap itself). Tests: 402 of 403, and the one
(test_cache.test_code_closure) was this branch's: cache.qa_part's `from . import qarender` put the whole QA into every
stage's code closure (a QA edit would have invalidated the garments stage's cache); now imported by name (928ea2d).

New since the checkpoint: **artifactqa's body frame draws through qa3d.draw**, so under the render drawing the art_*
checks of the collar, bow, top, skirt and boots (and the silhouette checks built from Michael's flags) move too; the
head frame's art_* read artifactqa.buffers() (its own z-buffer) and don't. The calibration now covers them.

Tools added: `python -m charkit qa BUNDLE --draw numpy|render [--threads N]` (LP_NUM_THREADS for llvmpipe); qa.json
`measured.cpu_s` and `measured.parts` {part: [wall s, CPU s]} (process CPU, every thread); `remote run --fetch DIR CMD`.

Plan: box builds of clawd.json and clawd_body.json (hair pieces vs the geom shell: the second geometry for the 2x2) at
the merged head, with the look export and toon boards; the QA timed on the box under both drawings; calibrate (placements
off the 3x grid) and qaref on those builds; decide; register the step; gate.

## Phase 2: state at the checkpoint (2026-09-30, `tool/toonrender2`, from pipeline-3d cfcdc3a)

Stopped at a checkpoint (usage limit). Nothing gated yet; the QA's default drawing is unchanged (`qa3d.DRAW = 'numpy'`).
tool/look3 (0b99529: the integer streak hash, the outline cap) is not in pipeline-3d yet: merge it when it lands (it
edits toon.wgsl, gpu.py, model.py, normals.py, gltf.py, render/__main__.py; this branch's edits there are small and
apart from its hunks, and measure.wgsl picks up `inward()` by itself).

### What is built (all committed)

| piece | where | state |
|---|---|---|
| cheap export for the renderer | `gltf.export(look_only=True)`, `build_blender.py --look` (product `look`), `cli.build` passes `--look` unless `--vrm` / `--no-look` -> `OUT/NAME.look.glb` | done, not yet run in a full build |
| boards' camera and landmarks in every export | `gltf.export_scene`: root `boards` {eye_z, L, centre, height_m} and `landmarks` (trace's), Blender frame; `views.board_views` reads them; `design` set added | done |
| export speed-up | `gltf.Eval._read`: the vertex groups filled once per group (it built a zeros(nv) per vertex-group pair) | done |
| QA buffers from the renderer | `charkit/render/buffers.py` (`Frames`, `window`, `object_at`), `measure.wgsl` (part, hull, tone, depth, normal; appended to toon.wgsl, which it doesn't edit), `qa_resolve.wgsl` (EEVEE's filter, transparent film) | done, tested |
| the QA's drawing switch | `charkit/qarender.py` (`View` stands in for draw_view's dict); `qa3d.DRAW`, `CHARKIT_QA_DRAW`; hooks in `qa3d.draw_view / draw_lit / draw_ids`; `hair_noise` reads the view's mesh; `lookqa._scaled` tags `line_k`, `line_width` and `detailqa.profile_render` call `qa3d.draw_ids`; `qa.json measured.draw` says which drawing measured; `cache.qa_part` keys on the drawing (nothing added with numpy: old keys unchanged) | done; numpy values reproduce exactly |
| toon boards on the build box | `charkit/render/buildboards.py`; `cli.build --boards-renderer eevee|toon` (toon by default where `CHARKIT_NO_RENDER=1`), trace span `boards_toon`; expressions and mouths skipped and said | done, not yet run on the box |
| preview parity | `preview.parity / parity_section`: `python -m charkit.render compare` on the preview's build, per board mean, IoU, ink width, flagged past `PARITY` | done, not yet run |
| standing laptop-vs-box test | `charkit/render/parity.py` (`python -m charkit.render parity BUILD`): boards, head-frame buffers, the drawn checks, each against `BOUNDS` | written, not yet run |
| evidence tools | `charkit/render/eevee_frames.py` (Blender: the QA's frames in EEVEE, same window / light / outlines; no dither), `qaref.py` (numpy vs ours vs EEVEE on those frames), `calibrate.py` (each drawn check under both drawings, noise over 6 sub-pixel placements, the 2x2 over two builds) | done |
| tests | `charkit/tests/test_render_buffers.py` (window = raster's to 1e-6 px; sphere: parts, hull ring, normals, depth, tones vs colour, outline off, paint, coverage, determinism; the fallback). test_render, test_registry, test_lookqa, test_bundle pass | done |

### Numbers so far

Export cost (build box, 32 vCPU, the tr2_base build of clawd.json at cfcdc3a; cProfile in Blender on its .blend):

| export | wall | CPU | size |
|---|---|---|---|
| full VRM (`--vrm`) | 80 s | 161-167 CPU s | 46 MB |
| look only (`--look`), before the group fix | 12.9 s | 33 CPU s | 33 MB |

(the full export's 63 s are the shape keys: 147 evaluations at subdivision 2). The Blender stage of that build was 182 s
wall with the full export, so the look export adds ~7% where the full one added ~44%. The look export after the group
fix is not measured yet (expect ~10 s).

The QA frames drawn three ways (`qaref` on tr_base, phase 1's render-box build; EEVEE on the laptop, Blender 5.2.2):
- **The window mapping is exact**: EEVEE's one-sample frame and our part buffer differ on 5 of ~1M pixels (IoU 0.999995).
- **Tones** (skin, one sample a pixel, each drawing's colour classified to the skin's tones; 4 board-light frames / 12
  sweep frames): agreement with EEVEE 99.80% numpy, **99.91% ours** (board light); 99.78% / **99.91%** (sweep). Exact
  tones against EEVEE's classified: 99.11% / 99.20%.
- **Shadow shares** (face_shadow's inputs, three-quarter): neck in shadow numpy 0.9216, ours 0.9240, EEVEE 0.9240
  (classified; ours equals EEVEE's to 4 decimals in every head frame, numpy is off by 0.0046 at 30 deg).
- **Head pictures** (boards' film) against EEVEE's: mean 1.59-2.14 levels numpy, **0.84-0.91 ours**; >8 levels 2.0-2.5%
  numpy, **0.9-1.1% ours**; the silhouettes both 0.9993+.
- **Hair pictures** (hair_noise's frames, streaks off in both): mean 0.42 numpy, **0.33 ours** on hair pixels; >8
  levels 0.29% / **0.06%**. With streaks both ~0.85 (tr_base predates look3: EEVEE's sin hash on Metal places them
  elsewhere; look3's lookup3 fixes that by construction).
- **Tone edges** (face_noise's measure on classified maps, board light): EEVEE 0.0577, numpy 0.0568, ours 0.0565; the
  drawings sit together, both ~0.001 under EEVEE (EEVEE's hair and skin normals re-sampled after the outline: phase
  1's finding 3, which the export can't carry).
- EEVEE's own picture must be drawn without dither for hair_noise: with the boards' dither its percentile cuts read
  0.27 against 0.07 (every flat tone split by the 1-level noise). eevee_frames.py now sets dither 0 (not rerun yet).

The drawn checks under both drawings (tr_base, the default spec; one run, laptop Metal):

| check | numpy (old) | render (new) |
|---|---|---|
| hair_noise | 0.0721 | 0.0726 (0.0728 streaks off) |
| scalp_px | 0 | 0 |
| face_noise | 0.0542 | 0.0537 |
| face_noise_sweep | 0.0548 | 0.0545 |
| face_islands | 12 | 12 |
| face_shadow_3q | 0.3419 | 0.3419 |
| face_shadow_face_3q | -0.069 | -0.0686 |
| face_shadow_neck_3q | 0.4539 | 0.4579 |
| line_width / line_spread / line_ink | 1.0 / 11.806 / 24.67 | the same |
| boot_profile_double_{L,R}, scrunch_* | 0.0173, 0.0157, ... | the same (part buffer, build widths) |

QA time on the laptop: the drawn parts 22 s numpy, 11 s render (Metal). On the box (llvmpipe) not measured yet; watch
its CPU seconds (llvmpipe threads on every core: the gate WARNs at 1.5x the build's CPU; LP_NUM_THREADS bounds it).

Calibration (`python -m charkit.render calibrate charkit/out/tr_base charkit/out/tr2_base`, laptop, report
`charkit/out/calib1/calibrate.md`): each drawn check under both drawings, its noise (std over 6 sub-pixel placements),
and the 2x2 (two geometries: tr_base, phase 1's render-box build, and tr2_base, the build box's at cfcdc3a).

| check | tr_base old / new (noise) | tr2_base old / new (noise) | 2x2: the geometry's change, old / new | EEVEE evidence |
|---|---|---|---|---|
| hair_noise | 0.0721 / 0.0726 (0.0005) | 0.0739 / 0.0746 (0.0006-0.0008) | +0.0018 / +0.0020 | hair pixels 0.42 -> 0.33 levels from EEVEE's, >8 levels 0.29% -> 0.06% |
| face_shadow_neck_3q | 0.4539 / 0.4579 (0.006) | 0.4589 / 0.4647 (0.004-0.005) | +0.0050 / +0.0068 | neck shade share: ours = EEVEE's (0.9240), numpy 0.9216 |
| face_shadow_face_3q | -0.0690 / -0.0686 (0.0025) | -0.0725 / -0.0719 (0.002) | -0.0035 / -0.0033 | face shade share: ours = EEVEE's to 1e-4 |
| face_shadow_3q | 0.3419 / 0.3419 (0.006) | 0.3417 / 0.3408 (0.005) | -0.0002 / -0.0011 | as above |
| face_noise | 0.0542 / 0.0537 | 0.0541 / 0.0539 | -0.0001 / +0.0002 (opposite, both tiny) | tone agreement 99.80% -> 99.91%; edges both ~0.001 under EEVEE's |
| face_noise_sweep | 0.0548 / 0.0545 | 0.0543 / 0.0543 | -0.0005 / -0.0002 | sweep agreement 99.78% -> 99.91% |
| face_islands | 12 / 12 | 13 / 13 | +1 / +1 | the same on EEVEE's classified maps |
| scalp_px, line_width, line_spread, line_ink, boot_profile_double_*, boot_profile_scrunch_* | identical | identical | identical | geometry alone at build widths (part buffers agree) |

Reading it: every move is within about one noise (the largest, face_shadow_neck_3q at 0.6 and 1.1 noise, moves to
EEVEE's value); every geometry change reads the same way under both drawings except face_noise's, where both changes
are under 0.0003. **The noise of face_noise, face_noise_sweep and face_islands reads 0** because the placements were
multiples of 1/3 px, i.e. whole samples of their 3x grid: the next calibration must use placements that aren't (e.g.
1/6 and 1/2 of a sample). Not yet: clawd_mh.json, a post-look3 build, the box's llvmpipe drawing.

### Next steps (in order)

1. Finish the evidence: rerun `python -m charkit.render qaref BUILD` with the dither off, on a post-look3 build (the
   streak hash then matches EEVEE's; hair_noise's streaks decision: keep them on, as the boards draw them, if ours
   matches EEVEE's streaks there). Calibrate (`python -m charkit.render calibrate A B`) on clawd.json and
   clawd_mh.json box builds; fill the check-by-check table (old, new, noise, EEVEE evidence).
2. A full box build with the look export (`remote build ... --out ...`): its CPU seconds (trace `look_export` cpu_s),
   the toon boards there (`boards_toon` span: seconds per board on llvmpipe), the QA with `CHARKIT_QA_DRAW=render` on
   the box (its seconds and CPU seconds; LP_NUM_THREADS if needed).
3. `python -m charkit.render parity BUILD` (laptop against the box); set BOUNDS from what it reads.
4. Decide the default: switch `qa3d.DRAW` to 'render' only if the table shows the new values more faithful and no
   check degrades unexplained; then a follow-up commit with MEASUREMENT_STEPS (charkit/steps/qa3d.py or the modules'
   own: hair_noise, face_noise*, face_islands, face_shadow_*; scalp, line_*, boot_profile_* only if they move) naming
   the switching commit.
5. Gates: `python -m charkit remote gate tool/toonrender2 --into pipeline-3d` and `--spec charkit/spec/clawd_mh.json`;
   report every drop; no --accept. Note: the gate's crossed QA run on the baseline's bundle has no look export (older
   builds): the render drawing falls back to numpy there and qa.json's measured.draw says so.
6. Review page (numpy | ours | EEVEE per QA frame: qaref's strips are the start) and the preview's parity section on
   the next preview.

Open: hairlab (not a QA part) still draws with numpy (candidate hair isn't in an export); the eye renders
(qa3d.eye_image) and the silhouettes (qa3d.coverage) are their own drawings, not draw()'s, and stay numpy.
