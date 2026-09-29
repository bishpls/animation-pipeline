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

(Numbers in the round's section below.)

## What doesn't carry over to the export, or isn't measured

- The QA draws the hair without its highlight streaks (hair_noise measures shading, not the drawn highlight).
- Board views are orthographic in the QA and 85 mm in the boards.
- The proxy normals and the neck tilt are rest-pose: the neck's tilt rides the skin's deformation, but it is a
  head-and-neck stand-in, not re-derived per pose.
- look.js lights each view from its camera and widens screen lines from the camera's distance to the head (Blender's
  `render_view` uses the target's distance); not yet checked against the Blender boards in the charkit-look board
  harness.
