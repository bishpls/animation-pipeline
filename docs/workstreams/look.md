# Workstream: the look, shading and lines (`tool/look`)

The toon look against the design's cel shading (head_turnaround, body_turnaround). The anime profile's `look` section
(`charkit/styles/anime.json`) holds every choice; `realistic` and any profile without one keep today's look (DEFAULT:
one fixed world light, each outline its build width and colour, geometric normals, no highlight).

Judged on `charkit/spec/clawd_body.json` with `hair.shape.mode: "pieces"` (`charkit/out/remote/clawd_body_pieces.json`),
built on the GPU render box (`python -m charkit remote --box render build SPEC --boards views,body`).

## What was built

| Where | What |
|---|---|
| `charkit/styles` `look` | light (`world` / `camera` key `[deg left of the camera, deg up]`), lines (`world` / `screen` `frac` of the picture's height x a region factor; colour `build` / `ink` / `material`), face (normals `proxy`, neck `chin_tilt`, fringe drop and side locks, the jaw line), hair (highlight `streaks`, `deep_at`, under-layer shade). `styles.merge` lays sections over each other; `cli.resolve` puts the resolved look into the build spec, so the stage cache keys on it. |
| `charkit/shade.py` | `set_look`, `view_light`, `set_view` (light nodes `ldir` / `ldir_head` and outline widths per view; `qa.render_view` calls it for every still), `line_colors`, `hair_toon` (deep step, under layers, streaks). |
| `charkit/faceshade.py` | `proxy_normals` (the head's normals blurred to its large shapes; the neck's turned round its axis and tilted down under the jaw), carried onto the rendered skin after its outline from a rigged hidden copy (`apply_proxy_normals`); the face mask from them; `ink` (the jaw's edge over the neck, in the face UV, off the neck by `ck_ink_w`); the fringe shadow now found on the cut pieces' bangs (and side locks). |
| `charkit/bundle.py` | The face material (`kind: face`: its toon, SDF, fringe, blush and ink maps), the face UV, mask and ink weight per variant, the skin's render normals, the highlight's parameters, the look. |
| `charkit/qa3d.py` | `draw()` under each view's board light (`view_light`), the SDF face shaded from its maps, a tone buffer (`aux`); the `look` part. |
| `charkit/lookqa.py` | `face_noise` (+ the design's own), `face_islands`, `face_shadow_*` (against head_turnaround's shaded skin), `line_width`, `line_spread`, `line_ink`. INFO for now. |
| `charkit/gltf.py`, `engine/three/charkit/look.js` | Parity: root `light.mode/key`, `lines` (screen), material `highlight` (streaks), face `ink` + `_INK_W`, outline `region`; the pipeline lights each view from its camera. |
| `charkit/boards/turntable.py`, `lookboard.py`, `charkit/lookpage.py` | Turntables and design-matched head views from a saved scene (`--look` overrides for options); the review page. |

## Measures (`charkit.lookqa`, the QA part `look`)

All drawn from the bundle as the boards light it (`qa3d.draw` under `view_light`), the design read at its own scale
(`lookqa.design_heads`: head_turnaround at 399 px per L, its skin split into lit and shaded tones by Otsu, its lines
the pixels darker than half way from ink to paper). INFO for now: they need a few builds of history before grades.

| Check | What |
|---|---|
| `face_noise` | tone edges per visible head-and-neck skin pixel from 0, 30, 90 degrees under each view's light; `design`: head_turnaround's own in front, 3/4, profile. |
| `face_noise_sweep` | the same under four fixed lights round each view (35 and 70 degrees either side, 35 up). |
| `face_islands` | tone regions over 0.002 L^2 (`design`: the drawing's). |
| `face_shadow_3q` | the shadow's IoU with the design's over the skin both show, three-quarter (front and profile in `per_view`). |
| `face_shadow_face_3q`, `face_shadow_neck_3q` | the shadow's share of the face (above our chin) and the neck, ours less the design's. |
| `line_width` | our outlines' median width over the design's, both in px of the design's own page (ours drawn at its px per L, screen lines at its page height). |
| `line_spread` | p90 / p10 of our line widths (the design's alongside). |
| `line_ink` | our lines' colour per region against the design's ink, CIEDE2000. |

The palette checks read the materials' unlit tones: unchanged by the look (the proxy normals and the view's light
change shading, not tones).

## Round 1 (2026-09-29)

Builds on the render box: `charkit/out/look_base` (tool/look before the look: world light, build widths),
`look_v1` (camera key, screen lines, proxy normals), `look_v2` (+ ink lines, streaks, jaw ink: two bugs, below),
`look_v4` (the proposal; built on the laptop's slot: gcloud auth expired mid-round).

What the renders showed and what changed:
- **Light.** The fixed world light put a hard diagonal terminator across the back of the hair and the far half of
  the face in shade in every turned view. A key that turns with the camera lights every view from the viewer's side,
  as the design's turnarounds are drawn.
- **Face and neck.** With the key in front the face is lit (as drawn); the proxy normals take the eye hollows and neck
  folds out of the terminator; the neck under the jaw goes into shade as the design shades it (front neck shadow share
  0.74 against the design's 0.75, was 0.12). The fringe shadow was missing entirely with the cut pieces (the stage
  looked for `hair_front`); it is now cast by the bangs and the side locks, 0.07 L below them.
- **Highlight.** v1's band (one elevation all round) read as a stripe; v2's streak columns were far too dense; v4 keeps
  30% of 36 columns, 5 degrees long, at 47 +- 4 degrees.
- **Jaw line.** Drawn in the face UV it zigzags: the skin renders subdivided, and the face UV is interpolated there,
  not re-projected, so a line one texel wide wanders. Off (`face.jaw_line`); a line mesh bound to the skin
  (shrinkwrap) or a depth-edge pass (Blender and look.js) would carry it.
- **Lines.** Build widths were 0.7 px on the body boards (sub-pixel) and 2.3 px on the face boards; screen lines are
  0.22% of the picture's height in every view. Ink: the design's lines are one near-black brown (#0f0504); ours were
  per-object browns (dE00 ~26).

### The numbers (look_base -> the proposal: look_v5, its skin outline in its build colour as c479043 builds it)

| Measure | before | after | design |
|---|---|---|---|
| face_noise (tone edges / skin px, 0/30/90) | 0.049 | 0.047 | 0.065 |
| face_islands (tone regions) | 6 | 12 | 12 |
| shadow IoU with the design: front / 3/4 / profile | 0.15 / 0.50 / 0.44 | 0.47 / 0.38 / 0.35 | |
| face shadow share: front / 3/4 / profile | 0.08 / 0.27 / 0.55 | 0.18 / 0.10 / 0.02 | 0.09 / 0.18 / 0.22 |
| neck shadow share: front / 3/4 / profile | 0.12 / 0.51 / 0.87 | 0.73 / 0.80 / 1.00 | 0.75 / 0.61 / 0.70 |
| line width, median px on the design's page | 1.25 | 1.81 | 1.99 |
| line width p10 / p90 | 0.25 / 1.99 | 0.25 / 2.91 | 1.75 / 2.79 |
| line colour, dE00 to the design's ink: skin / hair / garment / accessory | 26.4 / 25.6 / 21.9 / 27.0 | 24.9 / 4.5 / 8.2 / 15.9 | |
| hair_noise (remeasured under the view's light) | 0.060 | 0.066 | |
| palette hair lit / shade, skin lit / shade (dE00) | 0.94 / 3.61 / 3.12 / 6.16 | the same | |

Reading them:
- The front and the neck moved to the design: the front's shadow IoU tripled, the neck under the chin is in shade
  as drawn (0.73 against 0.75). The three-quarter and profile IoU fell: the old light put the far cheek in shade and
  the design shades the far side too (under the side hair); with the key from the viewer's side ours is lit there.
  The design's profile shades the temple and cheek under the hair (0.22); ours 0.02. The side locks' shadow is a
  front projection, so it reaches the cheek from the front but not the side: a side projection of the hair's shadow
  (or a view-dependent one) is the next step.
- face_noise stays near the design's (the design has more shadow edges than ours, not fewer); face_islands matches it.
  The sweep (fixed lights round each view) rose with the neck's designed shadow shape: it counts every edge, so it
  isn't a banding measure alone. The tone maps (qa_face_shading.png) show the neck's stripes gone (one shadow
  shape under the jaw instead of two or three bands), under the board light and under side lights. The eye surround
  didn't band in either build under these lights (the SDF covers it). The SDF's nose shadow shows as a hexagonal blob
  on the far cheek when the light is 50-70 degrees to the side (no board view puts it there): its shape wants
  redrawing as a thin triangle along the nose.
- The eye checks hold (eye_aspect 0.954, eye_lid_span 1.022 on this spec). The default spec's gate at 0ed9e4e, with
  the skin's outline inked, read the face's contour as lash in the eye crops (eye_aspect 0.829 -> 0.745): the skin
  keeps its warm brown line (c479043) and inking it is a taste call once the eye QA masks the contour by geometry.
- Line width is 0.91 of the design's median; their spread is dominated by 1-subpixel slivers (p10 0.25 px) where one
  hair piece's hull peeks past another's and at thin lock tips: geometry, not the line width setting. The fix is either
  hull geometry (hair-detail) or a screen-space line pass.

## What doesn't carry over to the export, or isn't measured

- The QA draws the hair without its highlight streaks (hair_noise measures shading, not the drawn highlight).
- Board views are orthographic in the QA and 85 mm in the boards.
- The proxy normals and the neck tilt are rest-pose: the neck's tilt rides the skin's deformation, but it is a
  head-and-neck stand-in, not re-derived per pose.
- look.js lights each view from its camera and widens screen lines from the camera's distance to the head (Blender's
  `render_view` uses the target's distance); not yet checked against the Blender boards in the charkit-look board
  harness.

## Review

`python -m charkit.lookpage charkit/out/look_review --before charkit/out/look_base --after charkit/out/look_final
--options charkit/out/look_v5/optpages/light --options charkit/out/look_v5/optpages/lines`: the design's heads
beside before and after at 399 px per L, turntables, body boards, close-ups, the numbers, and the two taste calls
(the board light; the outline colour and weight) rendered from the proposal's scene with `lookboard.py --look`.

## Round 2 plan (`tool/look2`, from pipeline-3d 0122617; tool/look is merged)

Work in order. Report at each milestone; commit on `tool/look2` only, never push or merge; gate with
`python -m charkit remote gate tool/look2 --into pipeline-3d` and again with `--spec charkit/spec/clawd_body.json` (the
parallel gate path: it doesn't queue). Judge on `charkit/out/remote/clawd_body_pieces.json` (clawd_body.json with
`hair.shape.mode: "pieces"`; `cli.resolve` puts the anime look into the spec). Build and render on the GPU render box:
`python -m charkit remote --box render build SPEC --out charkit/out/NAME --boards views,body`; turntables and the
design-matched head views from the saved scene:
`infra/gcp/build.sh run $PWD '$BLENDER -b charkit/out/NAME/clawd.blend --python charkit/boards/lookboard.py -- charkit/out/NAME/lookboard --L 0.25'`
(with `CHARKIT_BOX_ENV=$PWD/infra/gcp/render.env`; `turntable.py` likewise, then `python charkit/boards/turntable.py --gifs DIR`),
fetched with `infra/gcp/build.sh fetch $PWD charkit/out/NAME/lookboard`. The review page: `python -m charkit.lookpage`
(see Review). The look's QA alone on a bundle: `lookqa.measure(bundle.load(DIR), qa3d.Design(B), OUT)`.

1. **The QA speedup** (the default build went 129.7 -> 265.7 s at the tool/look gate; target 1.2x of pre-look, about
   156 s, or less). The cost is the look part's own venv draws, not Blender: on the v5 bundle `line_width` 59 s (three
   views at the design's 399 px per L, 4x supersampled), `face_noise` 29 s (3 views + 12 sweep lights), `face_shadow`
   7 s; the Blender stages add ~7 s (face_shading 1.0 -> 4.8 s, garments 3.7 -> 7.2 s: the skin's proxy-normal
   transfer is evaluated on every mesh read).
   - Lines at 200 px per L (`FACE_PPL`) with 3x supersampling, converted to the design page's px as now (scale =
     native_ppl / 200); ~9x fewer pixels.
   - face_noise: tool/render-batch's profile of 15 `qa3d.draw` calls (21 s): 10.9 s draw's own Python per-surface
     shading (fancy indexing, a cross product per surface), 5.6 s `raster.window_zbuffer` (0.37 s a call), 1.3 s
     `_blur_down`, 1.2 s `_toon`. Sharing the z-buffer across a view's lights saves at most ~4.5 s; the lever is
     caching each surface's per-view data once per view (the z-buffer, the pixel -> triangle -> corner indices, the
     interpolated normals, the slots, the face UV and mask samples, the SDF/fringe/blush texture samples at those
     UVs) so each extra light re-runs only `_toon` / `_face` on the cached arrays; the sweep needs no picture (skip
     `_blur_down`) and only the skin shaded. `face_shadow` can share face_noise's views (0 and 90) through `B.memo`.
   - Show the cheaper measure measures the same thing: for line_width / line_spread and face_noise, the old and new
     values against their sampling noise (re-run each at 3 sub-pixel offsets of the frame's origin at both
     resolutions; the change must be inside that spread). Put the table here.
   - Measure the Blender side too (trace spans): if the proxy transfer's re-evaluation matters, try
     `loop_mapping='NEAREST_POLYNOR'` or a proxy at the skin's render subdivision with `NEAREST_NORMAL`, and check
     the normals against today's (mean and p99 angle).
2. **The chin's shadow as the jaw's cast shadow** (Michael: today's under-chin shadow reads as a smeared horizontal
   band low on the neck; the design has a clean V directly under the chin, following the jaw). Today it comes from
   `faceshade.proxy_normals` tilting the neck's normals down by up to `chin_tilt` 85 degrees (`tilt_power` 0.25):
   replace that with a shadow shaped from the jaw, e.g. per neck vertex the height of the jaw's silhouette above it
   along the key light's direction (a cast-shadow threshold map, SDF-style, in the neck's own UV or computed per
   vertex and stored as an attribute the shader compares with the light's elevation), so the shadow's upper edge is
   the jaw and it moves with the light. Grade it: extend `lookqa.face_shadow` with the design's shadow region under
   the chin in the front and three-quarter views (head_turnaround via `skin_classes`: its shaded skin between the
   jaw and 0.5 L below) against ours, IoU and the edge's distance from the jaw, and make it a graded check. tool/face
   is fixing the chin's geometry: coordinate before changing anything under the jaw.
3. **The hair's shadow on the temple and cheek from the key light** (the design's profile shades 22% of the face
   under the side hair; ours 2%; three-quarter 18% against 10%). `faceshade.fringe_shadow` projects the bangs and
   side locks from the front only (a planar map in the 'face' UV). Project the hair's silhouette along the key light's
   direction instead: at the boards' camera key the light turns with the camera, so either bake shadow maps for a
   few light azimuths and pick/blend by `ldir_head` in the shader, or compute the shadow from the light each view
   (Blender: EEVEE shadows can't reach an emission material; a depth map from the light, rendered once per view,
   sampled in the shader). The measure is `face_shadow_face_*` against the design per view.
4. **Smooth proxy normals for the hair's terminators** once tool/artifacts' per-region numbers exist (Michael flagged
   torn dark patches with sawtooth terminators on the hair locks in the three-quarter and side views). Likely the
   toon terminator following faceted per-lock normals plus the deep step: transfer smooth normals from a proxy (as
   `faceshade.apply_proxy_normals` does for the skin) and/or raise the look's `hair.deep_at` threshold; measure with
   tool/artifacts' numbers and hair_noise. tool/hair-detail owns the hair's geometry and normals: agree who changes
   what first.
5. **Taste calls A (the board light) and B (outline colour and weight) are with Michael**; apply his answers in
   `charkit/styles/anime.json` (`look.light.key`, `look.lines.color` / `ink_regions` / `frac`). Inking the skin line
   waits on the eye QA masking the face contour by geometry (queued for tool/face).

### Round 2 progress

**1. The QA speedup (done: `0b6e9cd`, `5f90e76`).**
- `qa3d.draw` is now `draw_lit(draw_view(...))`. `draw_view` holds everything that doesn't depend on the light: the
  z-buffer, each surface's pixels, triangles and weights, normals, and the face's and textures' samples. `draw_lit`
  shades a view under one light. It is bit-identical to the old draw: 60 of 60 pictures, tones, labels and depths on
  the default bundle match, and `charkit/tests/test_lookqa.py` checks it. face_noise rasterizes each view once; its
  sweep's four lights shade the skin alone, with no picture. face_shadow reuses face_noise's board views (`board_tones`,
  memoized per bundle, frame and azimuth).
- **line_width stays at the design's scale (401 px per L x 4); the plan's 200 x 3 doesn't measure the same thing.**
  The per-skeleton-pixel width (2 d - 1, the distance transform) is quantized to the sub-pixel, so the median sits on
  a lattice point. It holds at 1.812 px across 5 sub-pixel offsets at 401 x 4, but jumps with the resolution: 1.997
  at 200 x 3, 1.498 at 200 x 4 (default bundle; 1.733 on the pieces bundle), 1.772 at 300 x 4. The p10 is the
  sub-pixel slivers' floor, so line_spread follows the sub-pixel too: 11.6 at x4, 4.66 at 200 x 3. A
  resolution-free estimator (local line area over Kulpa-corrected skeleton length) holds at 2.02-2.10 across all of
  them, but it reads the design's short strokes 27-39% wider (their ends and junctions): a different measure, left as
  an option (`widthlab`, scratch). The cost went elsewhere:
  - the lines come from the z-buffer's labels alone, each in its hull's flat colour (`_hull_colours`), so there's no
    per-pixel preparation;
  - the widths are cut to their box (the same distances and skeleton);
  - the design's widths are measured per group of lines and memoized (bit-identical to the whole sheet's; 4.4 -> 2.6 s
    cold).
- **line_ink now reads the lines' own colour**: their supersampled pixels, not the pixels a line covers wholly after
  the pixel filter, which blended thin lines with their neighbours. The inked hair, garment and accessory lines read
  0.48 from the design's ink (were 4.5, 7.8, 15.6); the skin's brown 24.67 (was 24.9). It's registered as a
  measurement step (`history.STEPS`, `0b6e9cd`).
- **The Blender side**: the skin's `proxy_normals` Data Transfer costs 0.66 s an evaluation at the viewport's
  subdivision and 2.3 s at the render's (measured on the saved scene). Every trace snapshot and every bundle read
  evaluated it, though it moves no vertex: a full snapshot took 8.3 s with it and 4.6 s without. It is now off where
  only positions are read (`trace.OUTLINE_MODS`, `bundle.NORMAL_MODS`): the bundle went 13.3 -> 5.7 s, and every
  array is identical but the skin's masked V (7e-9 m). Other loop mappings aren't faster, and they turn the normals
  (NEAREST_POLYNOR: mean 6.0 deg, p99 54; POLYINTERP_LNORPROJ: 0.9 / 13 and slower), so they were rejected.
  faceshade.apply has trace spans: proxy_normals 1.05 s, fringe 1.73 s (a Python loop over 41,872 faces), sdf 0.03 s.

Per check on the box (median of 5 runs at 5 sub-pixel offsets; the box shared with other gates, so CPU time is the
steadier number):

| check | before, wall / CPU s | after, wall / CPU s |
|---|---|---|
| face_noise (+ sweep, islands) | 44.8 / 56.1 | 9.7 / 16.3 |
| face_shadow | 8.6 / 10.9 | 2.2 / 5.0 |
| line_width (+ spread, ink) | 82.3 / 158.1 | ~10 / ~12.5 |

The values against their sampling spread (the same 5 offsets, before / after; each after equals its before at the
same offset):

| check | default: spread over offsets | pieces: spread over offsets |
|---|---|---|
| face_noise | 0.0647-0.0652, the same at every offset | 0.0459-0.0468, the same |
| face_noise_sweep | 0.0523-0.0524, the same | 0.0508-0.0511, the same |
| face_islands | 7, the same | 11-12, the same |
| face_shadow_3q | 0.4382-0.4466, the same | 0.3639-0.3853, the same |
| line_width | 0.912 at all 5, the same | 0.912, the same |
| line_spread | 11.649 at all 5, the same | 11.649, the same |
| line_ink | 24.9 -> 24.67 (the step above) | 24.9 -> 24.67 |

Whole builds of the default spec (the QA and its caches cold, stages cached alike), three at once on the build box
under the same load:

| build | total s | look part s | ratio to pre-look |
|---|---|---|---|
| 966ad22, pre-look | 142.7 | none | 1.00 |
| 0122617, round 1 | 243.9 | 95.2 | 1.71 |
| 5928f93, round 2 (lines ~4 s slower than 5f90e76) | 168.9 | 27.3 | 1.18 |

Gates at `61b9368` (task 1 merged with pipeline-3d 6ca18da), both **PASS**, the only change line_ink remeasured:
- default: 282.8 -> 171.5 s wall, 778 -> 554 s CPU;
- clawd_body: 265.1 -> 235.2 s wall, 1578 -> 1351 s CPU.

(Reports: `charkit/out/gate/gate_tool-look2_61b9368_into_6ca18da*.md`.)

**2 and 3. Cast shadows: the jaw's on the neck, the hair's on the temple and cheek (one mechanism).**
- **The bake** (`faceshade.cast_maps`, `cast_shadow`, numpy only, in the face_shading stage):
  - per skin vertex (rest pose) and per light direction, how much the occluders shadow it, 0 .. 1;
  - directions: `k` = 16 azimuths round the head (phi = atan2(x, -y), 0 in front of her) at the key's elevation;
  - each direction is a shadow map from the light: the occluders' surfaces splatted into an orthographic map of
    0.012 L pixels, keeping the point nearest the light, grown a pixel, read with percentage-closer filtering 2 px
    round, so the value runs smoothly across the edge;
  - the per-vertex values are smoothed over the mesh twice;
  - receivers and occluders: the face above the chin takes the hair's shadow only (its own shading stays the SDF's).
    The neck, and the head's own polygons under the chin, take the head's and the hair's: the jaw and chin over the
    neck;
  - stored as four RGBA point attributes, `ck_cast0..3`. It costs 1.3 s in Blender (the trace span `face.cast`).
- **The shader** (`faceshade.cast_nodes`, on the skin's toon3 and on the face material):
  - the light's azimuth from `ldir_head`, the value interpolated between the two baked azimuths either side, cut at
    0.5 +- 0.12 by a smoothstep;
  - under the shadow, the toon's half-lambert is held at 0.47 or under (the shade tone, no rim), and the face's SDF
    shadow takes the maximum;
  - its parameters ride on the material (`ck_cast`). Parity: `bundle` (`fcast` per vertex, `shading.cast`), `qa3d`
    (`_cast`, `_toon`/`_face_lit` with the cast), `gltf` (`_CK_CAST0..3`, material `cast`), `look.js` (`castNodes`).
- **The neck's normals no longer tilt** (anime `face.chin_tilt` 85 -> 0). The tilt shaded the whole neck from the chin
  to its base as one band: that was the "smeared band". The neck now shades round its axis as a cylinder, and the jaw's
  cast shadow makes the shape under the chin. It comes from the geometry, so tool/face's new overhanging jaw carries
  straight into it (nothing to change here; rebuild and re-measure).
- **The measures** (`lookqa.face_shadow`):
  - `face_shadow_chin` (graded: PASS >= 0.6, WARN >= 0.4): the shadow's IoU with the design's over the neck window
    (the chin to 0.5 L under it), front and three-quarter;
  - `face_shadow_chin_edge` (graded, L: PASS <= 0.03, WARN <= 0.06): the shadow's depth per column against the
    design's (the V drawn as a profile);
  - `face_shadow_chin_soft` (INFO): the tone step's soft width on the neck;
  - `qa_chin_shadow.png`: close-ups, the design, ours and the overlay.
  - The face measures now draw the head bare, as head_turnaround draws it: no garments, the skin unmasked (the
    bundle's new `bare` skin variant). With the collar on, the neck window held only a strip between the chin and the
    collar, and the old band scored IoU 0.85 there.
- `lookboard.py --bare` renders the head bare for the review; `lookpage.py --board lookboard_bare --shadows` adds the
  close-ups.

### Paused 2026-09-30 ~01:45 (coordinator's request): state and exact next steps

**Committed at the pause** (the SHA is in the commit log, "look round 2, paused"):
- task 1 is done and gated (above);
- the task 2-3 code is in, but **not yet validated by QA numbers or a gate**. The anime defaults now carry
  `face.cast` and `chin_tilt` 0: revert those two in `charkit/styles/anime.json` if a gate is needed before
  validation.
- `faceshade.fringe_shadow` is vectorized, bit-identical to the old loop on the real bangs (41,872 faces;
  0.76 -> 0.20 s here, 1.7-2.6 s on the boxes). `fringe_shadow_loop` is kept as the reference.

**What the renders showed so far** (render box, `clawd_body_pieces`, T4):
- `l2c_base` is round 1's look;
- `l2c_a` and `cl1`/`cl2` are cast-lab re-bakes on l2c_a's scene
  (`blender -b OUT/clawd.blend --python castlab_blender.py -- ROOT BUNDLE_JSON OUTDIR CAST_JSON`: the script is in
  the session's scratch, not tracked; it's a quick loop for bake parameters without a build).
- The old tilt shaded the whole neck, chin to base, as one flat band. With the cast, the neck is lit and the jaw's
  shadow sits directly under it. The shape is a broad, dome-edged band rather than the design's V: our jaw is round
  and barely overhangs (tool/face's rebuild should sharpen it).
- In the 3/4 view the hair's shadow now falls on the temple beside the eye; in profile, on the cheek under the side
  hair (it was ~2% of the face). Its edges follow the locks' tips and are somewhat blotchy. Smoothing 2 and 4 look
  much alike.
- The QA's old chin numbers are misleading: the collar hid the neck, and the band scored IoU 0.85 / edge 0.021 L.
  That's why the face measures now draw the head bare.

**Box jobs running at the pause** (outputs land locally when their fetch finishes; nothing needs killing):
- render box: `l2c_b` (the cast, before the chin split and bare variant), which renders `lookboard_bare` and
  `lookboard` after its fetch. `charkit/out/l2c_b` is still fetching over the tunnel.
- render box: `l2c_c`, the plain pieces spec with the new defaults (the cast, the bare variant) ->
  `charkit/out/l2c_c`.
- render box: `l2c_d`, the "before" with the new code (`clawd_body_pieces_nocast.json`: no cast, chin_tilt 85) ->
  `charkit/out/l2c_d`.
- build box: the A/B/C timing, run 3 (`/srv/work/look2_scratch/ab2.sh`, detached). Its output is in
  `/srv/work/look2_scratch/ab_2.out` and `ab/*_3.log` (`TIME` lines: wall, user, sys). Run 2, under load 45-48:
  - trace totals: pre-look 166.9, round 1 307.7, round 2 (5f90e76) 211.6 s, so 1.27x (run 1 at lighter load: 1.18x);
  - the look part: 123.7 -> 34.7 s;
  - process-tree CPU (hull and outfit production included): 520.6 / 760.7 / 562.1 s, so round 2 is 1.08x.

**Next, in order:**
1. When `l2c_c` and `l2c_d` land, render both bare boards on the render box. Run
   `$BLENDER -b charkit/out/NAME/clawd.blend --python charkit/boards/lookboard.py -- charkit/out/NAME/lookboard_bare --L 0.25 --bare`,
   the same without `--bare` into `lookboard`, then fetch both.
2. Run `python -m charkit.lookqa charkit/out/NAME` for each (on the render box, then fetch `qa_look`). That gives the
   chin and face numbers on the bare head, before (l2c_d) and after (l2c_c).
3. Build the review page:
   `python -m charkit.lookpage charkit/out/look2_review --before charkit/out/l2c_d --after charkit/out/l2c_c --board lookboard_bare --shadows`,
   then `open` it.
4. Run tool/artifacts' detectors on both, for the neck's and face's jaggedness. A scratch copy with cast-aware buffers
   is in the session's scratchpad (`art/artifactqa.py`, `art/artrun.py`, `art/artifacts_design.json`): copy them into
   a scratch worktree, never into this branch.
5. If the numbers hold, register measurement steps for `face_noise*`, `face_islands` and `face_shadow_*` (the bare
   head), then gate both specs. If the budget still needs it, the remaining lever for 1.2x is `face.proxy_normals`
   (O(n^2) numpy, 0.7-1.05 s).
6. Task 4 (the hair's smooth proxy normals): tool/artifacts now has per-region INFO checks (`art_terminator_*`,
   1b2a283), so the precondition is met. It still needs agreement with tool/hair-detail before touching the hair's
   normals.

### Ownership

Yours: `charkit/shade.py`, `charkit/faceshade.py`, `charkit/lookqa.py`, the look parts of `charkit/gltf.py` (the
OPENADS_charkit_look extension; motion owns springBone export there, in separate functions),
`engine/three/charkit/look.js`, `charkit/boards/turntable.py`, `charkit/boards/lookboard.py`, `charkit/lookpage.py`,
the `look` section of `charkit/styles/*.json` and `styles.DEFAULT['look']`. Shared, touch minimally: `qa3d.draw`
(render-batch batches board renders through `qa.render_view` -> `shade.set_view`; keep that hook and set_view's
write-only-when-changed guard), `scene.py` (`stage_face_shading`, `hair_pieces_objects`' material lines, the
`line_colors` call after the stages), `bundle.py` (the face material and look records). Not yours: head geometry and
`eyes.py` (tool/face), hair geometry and normals (tool/hair-detail), `qa.render_view`'s callers' loops
(tool/render-batch).

### Gotchas

- Keep QA imports out of build stages: `shade.py` once imported `bundle.py`, which pulled `faceqa.py` into every
  stage's cache closure (`charkit/tests/test_cache.py::test_code_closure` catches it).
- Anything a build stage reads from the look must come through `S.spec['look']` (the stage cache keys on spec reads;
  `charkit/styles/*.json` opened inside a stage is not keyed).
- `set_view` / `set_light` write a node input or a SOLIDIFY thickness only when its float32 changes (a write re-tags
  the modifier stack: ~1.5 s a frame over 47 outlined objects).
- The outline SOLIDIFY re-derives corner normals: custom normals ride in from a hidden rigged copy by a Data
  Transfer after it (`apply_proxy_normals`), never set on the mesh itself.
- A thin line drawn in the 'face' UV wanders: the UV is interpolated on the subdivided skin, not re-projected (the
  jaw ink line, `face.jaw_line`, is off for this reason).
- The skin's outline in ink reads as lash to the eye QA's crops (eye_aspect 0.829 -> 0.745 on the default spec): the
  skin keeps its build colour (`lines.ink_regions`).
- The QA's venv memo keys on a function's code: memoize module-level functions (`lookqa.design_cut`), not closures.
- The design's lines are measured at v < 0.5 (half way from ink to paper), its skin split lit/shaded by Otsu; the
  eye's `sheetqa.LINE_V` (0.38) is a different threshold for a different job.
- `python -m charkit export BLEND` runs gltf.py as a script: import charkit modules absolutely there.
- Render box: `build.sh up` doesn't check that the VM started (it once stayed stopped and the wait ran 15 min);
  gcloud auth can expire mid-round (every box call fails with "Reauthentication failed": Michael re-logs in);
  the box can come up as a T4 fallback (same speed for boards).
- No foreground sleeps; long jobs with `run_in_background`; the laptop's own heavy work through its one build slot.

## Next

- The hair's shadow on the face from the side (the design's profile shades the temple and cheek under the side hair;
  ours is a front projection): a side projection, or a shadow map from the light.
- The chin's line over the neck: a line mesh bound to the skin, or a depth-edge pass shared by Blender and look.js.
- The outlines' slivers (hull geometry at piece overlaps and thin tips), with hair-detail.
- The SDF's nose shadow: a thin triangle along the nose instead of the hexagonal cheek patch.
- look.js against the Blender boards in `projects/charkit-look` (camera key, screen lines, streaks).
- Grades for the look checks after a few builds of history.
