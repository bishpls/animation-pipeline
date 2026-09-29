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

### The numbers (look_base -> look_v4; the QA doesn't draw the streaks, so v5's are v4's)

| Measure | before | after | design |
|---|---|---|---|
| face_noise (tone edges / skin px, 0/30/90) | 0.049 | 0.047 | 0.065 |
| face_islands (tone regions) | 6 | 12 | 12 |
| shadow IoU with the design: front / 3/4 / profile | 0.15 / 0.50 / 0.44 | 0.47 / 0.38 / 0.35 | |
| face shadow share: front / 3/4 / profile | 0.08 / 0.27 / 0.55 | 0.18 / 0.10 / 0.02 | 0.09 / 0.18 / 0.22 |
| neck shadow share: front / 3/4 / profile | 0.12 / 0.51 / 0.87 | 0.73 / 0.80 / 1.00 | 0.75 / 0.61 / 0.70 |
| line width, median px on the design's page | 1.25 | 1.81 | 1.99 |
| line width p10 / p90 | 0.25 / 1.99 | 0.25 / 2.91 | 1.75 / 2.79 |
| line colour, dE00 to the design's ink (worst region) | 27.0 | 15.9 | |
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
