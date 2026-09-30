# Workstream: artifact QA, measuring "obvious jaggedness" (`tool/artifacts`)

**State (2026-09-29, evening).** Built and committed: `charkit/artifactqa.py`, the QA part `artifacts` (checks
`art_<detector>_<region>`, INFO with a proposed `grade`), `charkit/tests/test_artifactqa.py`, the stored design measures
`charkit/refs/clawd/artifacts_design.json` (refresh: `python -m charkit.artifactqa design BUNDLE_DIR` after changing the
detectors or the sheets), `history.STEPS` entries. Calibration and gates: below, when done. The plan and findings that
led here follow.

Checkpointed 2026-09-29 before any code: findings and the plan. Worktree `~/animation-pipeline-artifacts`, branch
`tool/artifacts` from pipeline-3d `0122617` (the look is merged). `infra/gcp/build.env` and `render.env` are copied in
(gitignored).

**Goal.** Turn Michael's screenshots of jaggedness into graded numbers per region and per view, so every gate sees them.
It's measurement only: `charkit/artifactqa.py`, a QA part with INFO checks first.

## What Michael flagged, and where the originals are

- **Front chin and neck close-up** (`~/animation-pipeline-look/charkit/out/look_review/zoom_after_front.png`, 768x686,
  beside `zoom_design_front.png` and `zoom_before_front.png`):
  - a smeared shadow band across the neck;
  - a dotted line at the neck seam;
  - torn cream collar tips.
- **Three-quarter, "frontal key, 35° up"** (`look_review/light_light_*.png`, 1278x1038 pairs;
  `look_review/after_three_quarter.png` 639x1038 beside `design_three_quarter.png`):
  - torn dark shadow patches with sawtooth edges on the hair locks;
  - fragments at the lock tips;
  - ragged collar and bow edges.
- **Side** (`~/animation-pipeline-look/charkit/out/look_v5/boards/face_090.png`, 900x900; also
  `look_review/after_profile.png`):
  - stepped, jagged hair edges at the back and the fringe;
  - a wiggly neck outline;
  - a ragged collar.
- **Design references at the same scale** (399 px/L): `look_review/design_{front,three_quarter,profile,back}.png`
  (639x1038). The sources are `charkit/refs/clawd` (body_turnaround, and the spec's `ref.face_sheet`).

## What the QA already produces, and where (none of it needs Blender)

- **Gates run on the build box with `CHARKIT_NO_RENDER`:** there are no EEVEE boards there
  (`OUT/boards/body_{000,035,090,180}.png` 600x1000, `face_{000,030,060,090,150}.png` 900x900 exist only on the
  render box or the laptop). To be gate-visible, the detectors must run on the QA's own numpy drawings of the bundle,
  not on the boards.
- `charkit/qa3d.py`:
  - **QA parts:** `PARTS` (about line 1817) holds `(part, fn, check prefix, table key)`; `fn(B, design, out)` returns
    `(table, checks)`. Limits are in `LIMITS` (about line 57), graded by `_grade(key, v, higher_better)`.
  - **Drawing:** `draw(B, surfs, az, fr, ss, ldir, aux)` draws the bundle as the renderer does (toon, face SDF,
    outlines optional). With `aux`, it also returns supersampled buffers: `tone` (0 lit, 1 shade, 2 deep; NaN off toon),
    `mesh` (surface index per pixel) and `depth`. Surfaces come from `surfaces(B, o, variant, outline)`; the full-body
    frame from `figure_frame(B, ss=FIG_SS)`.
  - **Existing draws to reuse:**
    - `hair_noise` draws the hair (no outlines, occluded by the rest) at 0/90/180;
    - `sheet_body` z-buffers class labels per view at the sheet's scale (`bodyqa.zbuffer_views` on
      `scene_classes(B)` meshes);
    - `sheet_pieces` and `pieces_3d` hold per-piece masks (outfit graph names: collar, bow, top, skirt, boots and
      the rest).
- `charkit/lookqa.py`:
  - **The head frame:** `HeadFrame(B)` is at 200 px/L (`FACE_PPL`), ss 3, with a window (1.0, 1.05, 1.3) L round the
    eye line.
  - **Skin tones:** `skin_tones(B, fr, az)` returns the skin's tone image and mask. `face_noise` draws views 0/30/90
    plus a 4-light sweep; `face_shadow` draws front, three-quarter and profile.
  - **Design alignment:** `design_heads(design)` returns the head sheet at the same scale (`lab` = skin_classes, head
    boxes and eyes). `face_shadow` shows the design/ours alignment by the eyes (translation only), which the
    detectors can reuse for the head views.
- `charkit/bodyqa.py`:
  - **Classes:** `CLASS` = none 0, skin 1, hair 2, iris 3, line 4, orange 6, cream 7, dark 8, white 9, other 10.
  - **Design class images:** `classes(rgb, fg, eye_y, ppl)` turns a drawing into a class image (lines absorbed, and
    raw with the lines kept). `design_views(rgb, D, ppl)` returns the sheet's full figures on the shared grid (`WIN`).
- **A quick check** (`bodyqa.family` on `design_three_quarter` and `after_three_quarter`): anti-aliased edges and the
  lines read as "other" or line on both. So region masks must absorb lines first (`bodyqa.absorb`). Roughness must
  also be measured at a scale above the anti-aliasing width, 2–3 px or more, or it measures the anti-aliasing. The
  torn hair shadow patches and the cream collar fragments show plainly in the family image.

## The plan

**Regions**, per view (front, three-quarter, profile, back; the head views at 200 px/L, the body at the sheet's
scale): hair, face skin, neck skin, collar, bow, top, skirt and boots. They come from the class images plus the
piece masks, and the neck from the chin row (`B.assembly['chin']`, as `face_noise` splits it).

**The four detectors:**
1. **Outline roughness:** the region's outline against its own Gaussian-smoothed outline at σ of about 3 px. This is
   the length ratio (raw over smoothed) and the high-frequency curvature energy per unit length. Notches and teeth
   narrower than N px are counted, from the opening and closing residues.
2. **Terminator roughness:** the cel shadow boundary inside a region (`aux['tone']` steps in the class mask), with the
   same measure. It's calibrated on the design's two-tone skin and hair.
3. **Fragments and slivers:** the connected components of a class smaller than a set area in L², plus slivers
   (removed by an opening of radius r), as counts and areas.
4. **Seam speckle:** runs of isolated high-contrast pixels inside a skin region along a row or column (the neck-ring
   dots). That's the dashed-line density per unit length of skin.

**Calibration:**
- Compute every measure on the design's views and regions; grade ours as a ratio to the design's.
- Michael's flagged crops (paths above) are the positives: they must score clearly worse than the design. Set the
  limits so they FAIL, and record the numbers in the module's docstring.
- Check that a clean region (the boots after tool/body's round-3 fix) doesn't FAIL.

**Integration:**
- Reuse the draws other parts already make, via a memo on the design or bundle, so the build time stays within 3%.
  There are to be no new renders.
- New checks `art_<detector>_<region>` (with per-view values) go in as INFO. Register them in `history.STEPS` when the
  measure changes, and propose limits from the calibration table.

**Owners of the worst offenders**, named in the report:
- hair: tool/hair-detail;
- collar, bow and the other garments: tool/body;
- face and neck skin geometry: tool/face;
- shading terminators: the look (merged; whoever takes the next look round).

**Deliverables:**
- a review page: the flagged crops and design crops side by side, with the detector overlays and the numbers;
- tests on synthetic masks: a clean disc scores low; a jagged disc, a fragmented mask and a dotted line score high;
- a default-spec gate PASS, since it adds only INFO.
