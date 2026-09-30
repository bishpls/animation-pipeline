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

## Round 3: Michael's calls H and I (`tool/look3`, from pipeline-3d 301b661; pipeline-3d cfcdc3a merged in)

Builds on the render box (T4): `charkit/out/look3_before` (pipeline-3d 301b661) and `charkit/out/look3_after`
(0b99529), charkit/spec/clawd.json, `--boards views,body --vrm`. Review page: `charkit/out/look3_review/index.html`
(`python -m charkit.lookab charkit/out/look3_review.json`): per board EEVEE before | after | difference, close-ups of
garment edges and streaks (per renderer and GPU), every table below.

### Call H: the streaks by an integer hash

- `shade.hair_toon` keeps and places a streak column by Blender's **White Noise 1D** on the column index: Jenkins'
  lookup3 (`hash_uint`, `hash_uint2`) of the index's float32 bits, u32 arithmetic, no `sin()`. Shader nodes have no
  integer ops; White Noise is Blender's integer hash (EEVEE's `gpu_shader_common_hash.glsl`, Cycles' `util/hash.h`, the
  same code). Value keeps the column (`< keep`), Color's green places its elevation.
- `shade.streak_hash` / `streak_columns`: the numpy reference. `toon.wgsl` computes the same per pixel (the per-column
  table left the uniform); `look.js` the same in TSL u32 ops (`CK.hash`). The export's highlight says `hash: 'lookup3'`.
- Measured: `charkit/boards/lookprobe.py --hash` renders the node for columns 0..63 and reads it back in three 11-bit
  windows (EEVEE's film is half float): **64/64 columns match on the laptop (M2, Metal) and on the T4**, worst 0.99 of
  an fp16 step. `test_streak_hash_gpu` runs toon.wgsl's hash in a compute pass: bit-identical to numpy on Metal and
  on the T4's Vulkan. look.js runs it in headless Chrome's WebGPU (M2): the same columns (below).

Streak agreement (`lookab`: each renderer's streak pixels are its board against its own board without streaks, > 4
levels; IoU over all nine boards, and the two boards' difference inside the union):

| pair | before: IoU | before: mean in the region | after: IoU | after: mean in the region |
|---|---|---|---|---|
| EEVEE laptop (M2) / EEVEE T4 | 0.476 | 34.1 lv (48.7% > 8) | **1.000** | 0.01 lv (0.0% > 8) |
| EEVEE T4 / charkit.render (M2) | 0.064 | 56.2 lv | **0.995** | 0.56 lv (0.1% > 8) |
| EEVEE laptop / charkit.render (M2) | 0.054 | 58.2 lv | **0.995** | 0.56 lv |
| EEVEE T4 / charkit.render (T4) | - | - | 0.995 | 0.57 lv |
| charkit.render M2 / T4 | - | - | 1.000 | 0.07 lv |
| EEVEE T4 / look.js (Chrome WebGPU, M2) | - | - | 0.861 | 9.7 lv (35% > 8) |

look.js (`projects/charkit-look` boards, `~noring` for its streak-free base; ss 2, a box filter against EEVEE's
Gaussian): the same kept columns and positions; its streak edges differ (face boards IoU 0.84-0.94, the body boards'
few-hundred-pixel streaks 0.58-0.77).

The kept set changed with the hash: 10 of 36 columns (1, 4, 12, 18, 20, 23, 26, 27, 28, 33); one now lands on the right
bun as a large highlight (face_030). A taste point: a `seed` added to the index would pick another set.

### Call I: the outline's inward move capped at half a shell

- `shade.outline` stores `ck_line_cap` = `SHELL_CAP` (0.5) x the piece's own 'thick' SOLIDIFY (`shell_of`) and sets
  the SOLIDIFY's offset so the surface moves inward by `min(w, cap)` and the hull goes the rest, `w - min(w, cap)`,
  outward (`line_offset`: offset o puts the surface w (1 + o) / 2 in and the hull w (1 - o) / 2 out; checked in
  Blender). `set_view` writes the offset per view with the thickness. The export: `outline.maxInward`; charkit.render's
  vertex stages, `Prim.co()` and the garment normals follow it; look.js moves the surface and the hull per view
  (which also removes toonrender's finding 4 for every mesh: its surface stayed at the build width).
- Capped pieces: shorts 0.75 mm, sleeves 1.0, top / skirt / overskirt panels 1.25, collar 1.5, cuffs 2.5, waistband and
  wrists 3.125, boot cuffs 3.75. At the build width (1.2 mm) only the shorts and sleeves are capped; at the face boards'
  (0.93 mm) only the shorts; at the body boards' (3.62 mm) all.
- **What the cap fixed.** On the body boards the thin shells' inner layer moved outward past the hull (by w - t) and
  covered the line: the line drew only 14-66% of the thin garments' silhouette edges (sleeves ~30%, top ~33%, skirt
  ~51%, shorts ~64%). After: **100% on every piece**. The sleeves had no visible outline on body_000 before
  (review page close-ups).

Silhouettes and lines (EEVEE, render box; per piece: charkit.render ids of the piece alone at 4x, the mean move of its
outline = area change over perimeter):

| | face boards | body boards |
|---|---|---|
| per piece, thin shells | 0.00 px | +0.72 (sleeves) .. +0.75 (top) .. +0.89 (skirt) .. +0.97 (overskirt) .. +1.11-1.16 (shorts) px |
| per piece, thick shells | 0.00 | cuffs +0.52-0.55, waistband +0.27, wrists +0.23 px |
| per piece, everything else (skin, hair, boots, bow, accessories) | 0.00 | 0.00 |
| whole silhouette (IoU, mean move) | 1.0, 0 px | 0.9924-0.9937, +0.16-0.22 px |
| ink mean width (coverage) | 1.49-1.67 px, +-0.004 | 1.55 -> 1.68-1.71 px |
| ink area | +-0.4% | +21-30% |

(Against the original surface the outline of a thin shell now sits w - cap outside, 1.4-1.75 px on the body boards;
the "before" render already had the crossed inner layer w - t outside, so the change as seen is smaller.)

Shading normals turned more than 90 degrees by the outline (`lookprobe --normals`: per corner, outline on against off;
a face flips when its corners' mean cos < 0), garments:

| width | before: all (rim / edge rings / away) | after: all (rim / edge rings / away) |
|---|---|---|
| build 1.2 mm | 5757 (5527 / 32 / 198) | 5757 (5527 / 32 / 198) |
| face boards ~0.93 mm | 4526 (4385 / 19 / 122) | 4526 (4385 / 19 / 122) |
| body boards 3.62 mm | 12702 (7701 / 3406 / 1595) | 9193 (6102 / 2101 / 990) |

Not 0. What remains, by cause:
- **Rim beads** (6102 at the body width, 5527 at the build width, unchanged by the cap): the thick SOLIDIFY's rim,
  subdivided, is a rounded bead of radius about a third of the shell; any inward move beyond that collapses it, at every
  width, before and after, including the face boards where the call changes nothing. Its faces are slivers at open
  edges inside the line (the line now draws 100% of the edges). Measured on the before scene: cap share 0.3 -> 214
  flipped shell faces at the body width, 0.2 -> 84, 0.1 -> 34 (0.5: 8466); creasing the rims (`edge_crease_rim`) doesn't
  help (8438). A smaller share sends more of the line outward (w - s t outside the surface).
- **Edge rings** of the thick cuffs, waistband and wrists (their big rounded edges; 2101 at the body width, down from
  3406).
- **The collar away from its rim** (263 at the body width, 176 at the build width, 122 at the face boards'): it is
  locally thinner than its 3 mm shell (measured p5 0.94 mm, p1 0.17 mm): its geometry (garments2), not the cap.
- **Closed thin pieces** without a shell modifier (bow 501, boots 2 x 113 at the body width; accessories crab 260, star
  8): no cap as built. Capped at half their measured thickness (p5), the bow drops to 144, the boots to 2 x 39, the crab
  to 144 (an experiment, `lookprobe` with ck_line_cap set; not built in).

### charkit.render against the render box's EEVEE (after, streaks included; acceptance)

| board | mean | streak region mean | > 8 lv | silhouette IoU | tones agree |
|---|---|---|---|---|---|
| face_000 | 0.647 | 0.52 | 0.343% | 0.9997 | 0.99942 |
| face_030 | 0.643 | 0.49 | 0.273% | 0.9998 | 0.99951 |
| face_060 | 0.638 | 0.54 | 0.269% | 0.9999 | 0.99971 |
| face_090 | 0.613 | 0.51 | 0.199% | 0.9999 | 0.99972 |
| face_150 | 0.519 | 0.53 | 0.193% | 0.9999 | 0.99970 |
| body_000 | 0.858 | 0.80 | 0.440% | 0.99904 | 0.99959 |
| body_035 | 0.870 | 0.97 | 0.460% | 0.99932 | 0.99931 |
| body_090 | 0.839 | 0.86 | 0.322% | 0.99927 | 0.99965 |
| body_180 | 0.840 | 0.82 | 0.440% | 0.99912 | 0.99949 |

Before (the old renderer, sin hash f64, the before build): whole-board means 0.66-1.04 (face_060 1.036), silhouette IoU
0.99922-0.9999. The body boards' IoU fell a little (0.99922 -> 0.99904 on body_000): more of their outline is line
now, and the line's edges carry the anti-aliasing difference (16 regular samples against EEVEE's 64 jittered).

### The QA

- No check changed status. `line_width` (INFO) moved: the QA's outline model had the hull at the original surface
  and scaled the shrink linearly, so it drew a capped piece wrong; `qa3d.render_surfaces` now puts a capped piece's
  hull the rest of the width outside (from the bundle's recorded offset), `lookqa._scaled` caps the inward move at the
  design's scale, and the bundle records the cap. On the after build: 0.942 under the old model, 1.133 under the new
  (before build 1.0 under both): the garment lines' median at the design's scale 2.75 px (was 1.99; the skin's is
  2.79). Steps registered for `line_width` and `line_spread` (22a1ae7, charkit/steps/lookqa.py).
- Taste point: the garment lines now show at full width, so the body boards carry 21-30% more ink. If they read heavy,
  `look.lines.regions.garment` (1.0) is the dial (call B).

### Gates (712a0a3 into pipeline-3d cfcdc3a)

- `python -m charkit remote gate tool/look3 --into pipeline-3d`: **PASS**. Every test ok; moved: `line_width` 1.0 ->
  1.133 INFO (remeasured; 2x2: new geometry under the old measure 0.942, old geometry under the new 1.0), `shape_iou`
  0.884 -> 0.885, `shape_iou_torso` 0.933 -> 0.934 (INFO). Build 285.8 -> 291.0 s.
- `... --spec charkit/spec/clawd_mh.json`: **PASS**. Moved: `line_width` 0.942 -> 1.133 INFO (remeasured; 2x2 0.912
  under the old measure), `face_shadow_neck_3q` 0.1074 -> 0.1071 INFO. Build 205.3 -> 235.5 s.
- Later commits (4c48e19, 189bb70) touch only these notes, `charkit/lookab.py` and the charkit-look harness's flag.

### Tools (the look's)

| | |
|---|---|
| `charkit/boards/lookprobe.py` | Blender: `--hash` (White Noise bits vs `shade.streak_hash`), `--boards` (scene.boards re-rendered from a saved scene through a shim of its Scene: bit-identical to the build's own boards on the T4; `--streaks off`, `--cap 0`), `--normals` (per piece and width: flips by rim / edge rings / away, geometric flips, the moves). |
| `charkit/lookab.py` | The A/B review from a manifest: streak agreement across renderers and GPUs, silhouettes and line coverage per piece (charkit.render ids), ink, flips, charkit.render's compare, close-ups, the page. |

Commands used: `python -m charkit remote --box render build charkit/spec/clawd.json --out charkit/out/NAME --boards
views,body --vrm`; on the box `infra/gcp/build.sh sync $PWD && infra/gcp/build.sh run $PWD '$BLENDER -b ... --python
charkit/boards/lookprobe.py -- ...'` then `build.sh fetch` (`remote run` runs charkit subcommands, not shell);
`python -m charkit.render compare BUILD`; the old renderer from a pipeline-3d checkout for the before numbers.

### Open items

- The rim beads and the collar's thin regions still flip (above): Michael's call on a smaller share (0.2-0.3), or
  garments2 keeping rims flat / the collar at its thickness.
- Closed thin pieces (bow, boots, crab, star) have no cap: a measured thickness would give them one (experiment above).
- look.js: its streaks are measured (above); its per-view surface and hull aren't yet measured against EEVEE board by
  board (phase 2 B.1: `node engine/render.mjs projects/charkit-look --loop=views~BUILD~vrm:clawd`; needs
  `node_modules` linked into the worktree). For meshes with `_HULL_NORMAL` (skin, hair) the per-view surface move uses
  that attribute unskinned: exact in the build pose, off by the bone's rotation when posed.
- The streak set changed (one on the right bun): a seed if Michael prefers another set.
- OWNERSHIP.md's look row could list `lookab.py` and `boards/lookprobe.py`.

## Next

- The hair's shadow on the face from the side (the design's profile shades the temple and cheek under the side hair;
  ours is a front projection): a side projection, or a shadow map from the light.
- The chin's line over the neck: a line mesh bound to the skin, or a depth-edge pass shared by Blender and look.js.
- The outlines' slivers (hull geometry at piece overlaps and thin tips), with hair-detail.
- The SDF's nose shadow: a thin triangle along the nose instead of the hexagonal cheek patch.
- look.js against the Blender boards in `projects/charkit-look` (camera key, screen lines, streaks).
- Grades for the look checks after a few builds of history.

## Round 5 (look2's cast shadows, landed; `tool/look5`, from pipeline-3d 4de65ab)

Michael's flag: "Today's under-chin shadow reads as a smeared horizontal band low on the neck; the design has a clean V
directly under the chin, following the jaw." Round 2 built the cast shadows (above, "2 and 3") and paused before any
QA number or gate. This round merges them onto today's look (look3's H and I, look4's M, toonrender2's render drawing,
face4's chin) and validates them.

### State

- `tool/look2` merged (afc0a52): conflicts only in gltf.py's material record and look.js's mesh attributes (look3's
  streak hash and region factor kept, the cast added beside them).
- **charkit.render draws the cast** (0010805): the export's `_CK_CAST0..3` read as a third vertex stream; the vertex
  stage reads them at the head light's azimuth (atan2(x, z) in glTF, the two baked azimuths either side, linear, so per
  vertex equals per pixel), the fragment cuts it by a smoothstep; toon3's half-lambert held under `half`, the face's SDF
  shadow its maximum (toon.wgsl, and measure.wgsl's tone). Tests: `test_sphere_cast` (tones and colours against
  qa3d._cast/_toon under three lights), `test_sphere_bare_variant`.
- **The bare head under the render drawing**: round 2's face measures draw the head bare (the bundle's 'bare' skin),
  which the render drawing couldn't draw (it fell back to numpy for any skin but 'masked'). The look export
  (NAME.look.glb) now carries the skin's bare variant (NAME.bare: the garment mask off, no scene node, so no viewer
  draws it; mesh extension `variant: 'bare'`), and qarender draws the 'bare' skin from it.
- **A stale-cache hole closed**: scene.DEPS keyed face shading on the hair's names and `hair_front*` only; the cast
  bakes every hair object's geometry into the skin, so with the cast on the stage now keys on the whole hair (and on the
  cut pieces' bangs and side locks, which the fringe reads, otherwise).
- Builds next (render box): `look5_before` (`charkit/out/look5_specs/clawd_nocast.json`: clawd.json with
  `look.face.cast` null and `chin_tilt` 85, this branch's code) and `look5_after` (clawd.json), then both lookboards.

### First numbers (render box builds, bare head, the QA's render drawing; box and laptop agree to 4 decimals)

`look5_before` (cast off, chin_tilt 85) -> `look5_after` (the cast):

| check | before | after | reading |
|---|---|---|---|
| face_shadow_chin (IoU, front / 3q) | 0.528 (0.716 / 0.340) | 0.508 (0.673 / 0.343) | no separation |
| face_shadow_chin_edge, count per column (round 2's) | 0.0249 | 0.0269 | no separation |
| face_shadow_chin_edge, reach per column | 0.148 | 0.146 | no separation |
| face_shadow_chin_soft (the tone steps' soft width on the neck, L) | 0.0056 | 0.0037 | -34%: the smear |
| face share in shadow, ours / design: front | 0.196 / 0.076 | 0.342 / 0.076 | the hair's cast overshoots |
| three-quarter | 0.135 / 0.194 | 0.261 / 0.194 | |
| profile | 0.079 / 0.207 | 0.304 / 0.207 | |
| face_shadow IoU front / 3q / profile | 0.470 / 0.309 / 0.256 | 0.393 / 0.339 / 0.387 | |
| face_noise, face_islands | 0.0372, 15 | 0.0333, 10 | |

Per column in the chin window (0.5 L under our chin), before and after have the same shadow top (at the window's
top in the middle columns, none at the sides) and nearly the same reach (0.15-0.2 L; the design's 0.3-0.35 L): the
difference from the design is the neck's own toon shading and extent, not the cast. In the EEVEE close-ups the cast
removes the lit haze under the jaw (three-quarter: the shade starts at the jaw line) but the edge is wavy. The hair's
cast shades the forehead under the bangs from the front (34% of the face against the design's 8%).
Option build next: `look5_castneck` (`look.face.cast.face` false: the neck takes the cast, the face keeps the fringe
map).

### Calibration of the chin checks: not calibrated, shipped INFO

The rule: a new check passes on the design and fails on a known-bad example (round 1's band). Measured on the real
masks (the design's shadow in our chin window, look5_after's frame):

| the design's own shadow moved | front: IoU, reach error L | three-quarter: IoU, reach error L |
|---|---|---|
| 0 | 1.0, 0 | 1.0, 0 |
| 1 px down (0.005 L) | 0.765, 0.004 | 0.659, 0.003 |
| 1 px across | 0.872, 0.043 | 0.770, 0.052 |
| 2 px down | 0.660, 0.008 | 0.547, 0.006 |
| 2 px across | 0.796, 0.060 | 0.655, 0.063 |
| 4 px down | 0.577, 0.015 | 0.455, 0.013 |

The design's shadow in the window is thin, so a pixel or two of placement (the eye alignment rounds to a pixel)
costs as much as the PASS line (IoU 0.6, reach 0.03 L). And the known-bad reads as the cast does (0.528 / 0.508;
reach 0.148 / 0.146). So face_shadow_chin and face_shadow_chin_edge report INFO with the proposed grade beside
(`lookqa.CHIN_UNCALIBRATED`), not flag checks; never loosened, never gating. What would calibrate: a window aligned on
the jaw (not the eyes), and the shadow's top edge's distance from the jaw line per column (the flag's "directly under
the chin, following the jaw"), or the soft width (face_shadow_chin_soft, 0.0056 -> 0.0037 L) measured the same way on
the design's picture. The synthetic test (`test_chin_separates_the_v_from_the_band`) keeps the measures' behaviour:
the pixel count per column was blind to a band's position, so the reach is what chin_edge reports.

### charkit.render against EEVEE with the cast (render box EEVEE boards, laptop M2 ours)

`python -m charkit.render compare`: the face boards 0.60-0.62 lv mean, 0.14-0.24% over 8 lv, tones agree
0.9996-0.9998, silhouettes 0.9997-0.9999: as before the cast (0.50-0.63 lv). What changed between the builds (the cast
and the untilted neck, > 8 lv), per face board: EEVEE 9172-17601 px, ours 9159-17581, the two change masks' IoU
0.990-0.994; inside them the after boards differ by 0.42-0.49 lv (0.14-0.32% over 8). Body boards: 24-1506 px changed,
IoU 0.88-0.99. The QA's two drawings agree on the bare head: face_shadow_chin 0.5282 / 0.528 (render / numpy) before,
0.508 / 0.5073 after; chin_soft 0.0056 / 0.0055, 0.0037 / 0.0036.

### Stopped 2026-09-30 ~09:50: gcloud "Reauthentication failed" (box work stopped)

- **The gate is running unfollowed** on the build box: job `gate-look4-0930-094431-f250` (tool/look5 at 40f1d62 into
  pipeline-3d 4de65ab), started before auth expired; its report can't be fetched until Michael re-logs in.
- **The option build `look5_castneck`** (`charkit/out/look5_specs/clawd_castneck.json`: `look.face.cast.face` false)
  built on the render box (exit 0) but its outputs weren't fetched, and its lookboards and look QA didn't run.
- Review page: `charkit/out/look5_review/index.html` (design | before | after on the bare head, the chin and temple
  close-ups, the QA's chin overlays, the numbers).

**Next, in order (after `gcloud auth login`):**
1. `python -m charkit remote attach gate-look4-0930-094431-f250`: collects the report into `charkit/out/gate/`. Read it
   under K. Expect: the look part's bare-head checks `remeasured` (steps at d082a27); face_shadow_chin* new INFO; the
   hull rebuilt once in the candidate (scene.py is in its produced-cache key: DEPS changed), so CPU may read high;
   attribute it from the report's CHARKIT_PRODUCED lines as look4 did. The 2x2's "old geometry, new measure" cell is
   the old measure in practice (a pre-look5 build has no bare skin, so it draws dressed).
2. `CHARKIT_BOX_ENV=$PWD/infra/gcp/render.env infra/gcp/build.sh fetch $PWD charkit/out/look5_castneck`, then on the
   render box its lookboards (`lookboard.py -- charkit/out/look5_castneck/lookboard_bare --L 0.25 --bare` and without
   `--bare`) and `python -m charkit.lookqa charkit/out/look5_castneck`; fetch `lookboard_bare`, `lookboard`, `qa_look`.
   Rebuild the page with `--extra castneck=charkit/out/look5_castneck` (scratch script: the session's `opt.sh`).
3. Michael's calls (below), then a chin measure that calibrates (aligned on the jaw; the shadow's top edge's distance
   from the jaw per column; or the soft width measured the same way on the design's picture), and only then a flag
   check.

**Decisions for Michael:**
- **The hair's cast on the face overshoots from the front** (34% of the face in shadow under the bangs against the
  design's 8%; before 20%); it helps the three-quarter and profile temple and cheek (face shadow IoU 0.309 -> 0.339,
  0.256 -> 0.387; front 0.470 -> 0.393). Keep it, take the neck-only option (`face.cast.face` false: the face keeps
  the fringe map), or tune `at` / the bake's elevation for the face.
- **The chin:** the cast makes the shade start at the jaw (three-quarter) and narrows the smear (soft width -34%), but
  the chin's IoU with the design doesn't move (0.528 -> 0.508): what differs is the neck's own toon shading (the
  three-quarter design shades only a band under the jaw; our lambert shades the whole neck) and its extent (our
  shadow ends 0.15-0.2 L under the chin, the design's 0.3-0.35). A call on the neck's own terminator (e.g. the neck
  lit but for the cast) is the lever the flag points at.
- **The chin checks ship INFO** (not calibrated, above). Promotion waits on a calibrated measure.
