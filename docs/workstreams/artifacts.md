# Workstream: artifact QA, measuring "obvious jaggedness" (`tool/artifacts`)

**State (2026-09-29, night): PAUSED by the coordinator** (usage limit). Built, calibrated and committed on
`tool/artifacts`: `charkit/artifactqa.py`, the QA part `artifacts` (`qa3d.PARTS`; checks `art_<detector>_<region>` and
`art_peeks_<region>`, INFO with a proposed `grade`), tests (`charkit/tests/test_artifactqa.py`), the stored design
measures (`charkit/refs/clawd/artifacts_design.json`), `history.STEPS` entries. pipeline-3d `01f2cdd` is merged in
(`f3ebb42`; the only conflict was history.py's STEPS, both kept). The code under gate is `0db2e9b`.

**Box jobs running at the pause** (started from this worktree, 2026-09-29 ~21:30; the local ssh sessions were this
agent's background tasks and may have died with it: if a report is missing, re-run):
- `python -m charkit remote gate tool/artifacts --into pipeline-3d` -> report `charkit/out/gate/gate_tool-artifacts_0db2e9b_into_01f2cdd.md`
  (log `charkit/out/gate_default_2.log`);
- the same with `--spec charkit/spec/clawd_body.json` -> `..._into_01f2cdd_clawd_body.md` (log `charkit/out/gate_body_2.log`);
- `python -m charkit remote build charkit/spec/clawd_body.json --out charkit/out/art_body --no-blend` -> `charkit/out/art_body`
  (`qa/qa.json`, `qa/qa_artifacts.png`; log `charkit/out/art_body.log`): the current pipeline with this branch, for the
  review page's per-view table.
The first gates (`25e6679`) failed only on the merge conflict, before any build.
**The remote build failed** (after the pause) in Blender's garments stage, not this branch's code:
`garments.sleeve_hull` -> `loft.field`: "no row of the piece is measured on 15% of its circle" (log
`charkit/out/art_body.log`). It ran from this worktree's synced copy on the box (pipeline-3d `01f2cdd` merged); the
clawd_body gate's builds may hit it too. If they do, it's tool/body's (the sleeves from the hull) or the hull's inputs on
the box, not this workstream's: report it to the integrator, and take the per-view table from a default-spec build instead
(`python -m charkit remote build charkit/spec/clawd.json --out charkit/out/art_default --no-blend`).

**Default-spec gate (`0db2e9b` into `01f2cdd`): PASS.** Tests all ok, every art_* check new (INFO). Build CPU seconds
793.0 -> 803.2 (+1.3%), wall 271.7 -> 293.6 s (+8%, the box was running two gates and a build at once). Its
`art_design` note (value None, INFO) means **the stored design measures were stale on the box and re-measured (~20 s)**:
the stamp hashes the outfit graph *beside the produced masks* (`_graph_path`), and that produced copy differs from the
tracked one (locally `db557989...` against the tracked `charkit/refs/clawd/outfit_graph.json`, `308d5dcc...`, the
manifest's sha). Worst views on that build: outline neck 11.8, collar 3.9, top 2.2; terminator hair 4.8, bow 8.6,
skirt 3.2; fragments boots 2.9, top 2.9; speckle neck 1.7; peeks hair 17.

**Next steps, in order:**
0. **Fix the stamp first:** in `artifactqa.design_inputs`, hash the tracked outfit graph (the manifest's
   `outfit_graph` reference, as `bodymeasure.piece_masks` names its graph, or the masks' `.stamp`), not the produced
   copy; re-store `artifacts_design.json`, test, commit, and re-gate both specs. The `art_design` note must be gone
   and the CPU seconds within ~1% (the part itself is ~4 s).
1. Read the two gate reports (expect PASS: the art_* checks are new and INFO; watch the CPU-seconds slowness line, the
   budget is +3%: the part costs 3.5-4.0 s idle on the laptop). If a gate is missing, re-run it (commands above).
2. If `charkit/out/art_body/qa/qa.json` exists: rebuild the review page with it and the final table:
   `python charkit/out/artifacts_review/scripts/review.py charkit/out/artifacts_review/data/look_v5_qa/qa.json "current=charkit/out/art_body/qa/qa.json"`
   and `python charkit/out/artifacts_review/scripts/final_table.py charkit/out/art_body/qa/qa.json`. The scripts were
   written in a session scratchpad: set `SP` at their top to `charkit/out/artifacts_review/data/` (np2, np3, cal,
   calib2.json, table2.txt are there) and run from the worktree with the venv python. Open the page
   (`open charkit/out/artifacts_review/index.html`).
3. Report to the integrator: branch head, gate verdicts, the per-region table, the review page path, the proposed limits
   and open items (all below).
4. If the detectors change again: `python -m charkit.artifactqa design BUNDLE_DIR` (any build's bundle; ~20 s) and commit
   the refreshed `artifacts_design.json`, or every build re-measures the design and says so in `art_design`.

## What was built

- **Where it measures.** Our side runs on the QA's own numpy drawings, not EEVEE boards (the build box renders none):
  `artifactqa.buffers()` is `qa3d.draw()`'s z-buffer and tone buffer without its picture, textures or pixel filter
  (bit-identical to draw's `aux` buffers, about half the time). Two frames, each from front, three-quarter (the sheet's
  angle), profile and back under the boards' light for the view:
  - the head frame at 400 px/L (0.85 L either side, 1.25 above to 1.0 under the eye line): hair, face, neck;
  - the body frame at the body sheet's px/L (212), from 0.5 L under the eye line to the feet: collar, bow, top, skirt,
    boots.
  Regions come from each pixel's object (`object_kind`: hair, skin, features, garments by name), outline hulls counting as
  their object's and as drawn lines. The face is the skin above our chin, the neck the skin from the chin to 0.5 L under it.
- **The detectors** (every length in L, so any scale reads the same):
  - `outline`: corners per L of a region's outline (sub-pixel trace of the mask, smoothed at 0.004 L; a corner turns
    40 degrees or more over 0.005 L). A torn tip, a notch, a step or a tooth each make corners.
  - `terminator`: kinks per L of the cel tone boundaries inside a region (lit/shade and shade/deep, the outline and drawn
    lines' fringes left out; a kink turns 25-90 degrees over 0.006 L). A faceted terminator bends at every triangle it
    crosses; a drawn shadow flows and turns sharply only at a tapered stroke tip (over 90, not counted). Also `islands`
    (tone patches of 0.00002-0.002 L^2 per L^2) and `corners`, in the table.
  - `fragments`: the area of small pieces (under 0.002 L^2) and slivers (thinner than 0.012 L) of the region's flat
    colour between its drawn lines, per L of outline.
  - `speckle` (face, neck): specks under 0.0004 L^2 in the skin away from the features, per L^2: tone islands (read from
    the unsoftened tone: a render keeps a single pixel's speck), another surface showing through, a drawing's short
    strokes.
  - `peeks` (ours only; a count): small visible bits of each of a region's own objects, all components but the largest
    under 0.002 L^2. A lock tip peeking past the lock in front of it. The drawing has no pieces, so no ratio.
- **The design side** runs the same detectors on the drawings (`drawing_view`): cells of one colour family between the
  drawn lines (dark thin runs, and on pale regions the lighter strokes a drawing uses for collarbones and folds; the
  anti-aliasing touching a line is the line's), tones by Otsu on the luminance off the lines. Head regions from
  head_turnaround at 400 px/L (hair by colour, skin by colour, the rest by its neighbours; the face and neck split at
  the sheet's own drawn chin, 0.349 L); garments from body_turnaround at 212 px/L, its cells voted by the outfit's piece
  masks. It takes ~20 s, so it's stored: `charkit/refs/clawd/artifacts_design.json`, stamped on the two sheets, the outfit
  graph and this module's design-side code (and serving builds whose eye spacing is within 2%). A stale stamp makes the
  build re-measure and say so (`art_design`). **Refresh after changing the detectors:**
  `python -m charkit.artifactqa design BUNDLE_DIR`.
- **Grades.** Each check's value is the worst view's ratio of ours to the design's (the design's value floored: outline
  and terminator 1.0 per L, fragments 0.0002 L, speckle 10 per L^2), with per-view ours, design and ratio beside it.
  Status INFO; `grade` is what the proposed limits would give (below).
- **Cost.** 3.5-4.0 s a build on an idle laptop (the overlay `qa_artifacts.png` is ~0.5 s of it); under load 5-6 s.
  The first attempt, drawing with `qa3d.draw` and measuring the design each build, took 38 s.

## Calibration (look_v5: the build Michael flagged)

Four readings of each flagged view, all through the same detectors at the design's scale:
- the design: the stored measures (head_turnaround at 400 px/L; body_turnaround at 212);
- Michael's EEVEE crops (look_review `after_*`, `light_light_front`), their regions voted by our numpy labels of the
  same build, their edges and tones from their own pixels;
- our numpy picture of the same build, framing (the lookboard's: 399.4 px/L, the irises' eye line) and light;
- our numpy buffers of the same (the gate's path).

The scripts and their data are kept (gitignored) in `charkit/out/artifacts_review/scripts` and `.../data`: `t_np2.py`
and `np3.py` (numpy draws at the lookboard framing, 399.4 and 212.47 px/L), `calib2.py` (all four readings), `table2.py`
(the full table: `data/table2.txt`), `review.py` (the page), `steps.py` (the stepped-edge try). The review page:
`charkit/out/artifacts_review/index.html`. The flagged items, ratio to the design (EEVEE / numpy buffers):

| flagged | region, measure | view | design | EEVEE | buffers |
|---|---|---|---|---|---|
| wiggly neck outline | neck outline corners/L | profile | 2.09 | 7.59 (3.6x) | 7.63 (3.7x) |
| (collar tips across the neck) | neck outline | front | 0.85 | 7.38 (7.4x) | 7.35 (7.4x) |
| | neck outline | three-quarter | 0.78 | 3.32 (3.3x) | 2.24 (2.2x) |
| dotted neck seam | neck specks/L^2 | front | 32.6 | 122 (3.7x) | 62 (1.9x) |
| | | three-quarter | 47.9 | 162 (3.4x) | 61 (1.3x) |
| torn collar tips | collar outline (212 px/L) | front | 0.84 | 3.26 (3.3x) | 2.60 (2.6x) |
| | collar fragments (212 px/L) | front | 0.13e-3 L | 0.67e-3 (3.3x) | 0.51e-3 (2.5x) |
| torn hair shadow patches | hair terminator kinks/L | three-quarter, frontal key | 4.35 | 6.76 (1.6x) | 12.7 (2.9x) |
| | | three-quarter | 4.35 | 6.50 (1.5x) | 11.8 (2.7x) |
| | | front | 3.74 | 5.67 (1.5x) | 10.3 (2.8x) |
| (not flagged) | | profile | 5.92 | 3.51 (0.6x) | 5.52 (0.9x) |
| fragments at lock tips | hair peeks (count) | three-quarter | (none) | | 24 (lookboard framing), 27 (gate) |
| | | front / profile / back | | | 13 / 11 / 10 |
| stepped hair edges | hair outline corners | profile | 5.08 | 3.37 (0.7x) | 3.94 (0.8x) |
| | hair fragments | profile | 1.36e-3 | 0.49e-3 (0.4x) | 1.57e-3 (1.2x) |

What separates and what doesn't:
- **Separates, in both the renders and our buffers:** the neck's outline (every view), the neck seam's specks (the
  buffers read ~0.4x the render's count: a single-pixel speck in our 1-sample buffer is a 2-3 px dot in a 64-sample
  render), the collar's torn tips (front), the hair's faceted terminators (front and three-quarter; the profile, not
  flagged for them, stays under 1), the peeking lock bits (three-quarter highest, where Michael saw "fragments at the lock
  tips").
- **Doesn't separate from this design:** the hair's outline and its fragments and slivers. head_turnaround's hair is
  drawn with many flicks, tapered tips and fine strands, so by any small-scale measure it is rougher than ours; our
  stepped profile edge (parallel lines just inside the silhouette, where one piece's edge runs beside another's) and our
  lock-tip bits hide inside that. `peeks` catches the lock-tip bits because it reads our pieces, which the drawing
  doesn't have. The stepped edge needs its own measure (open items).
- **Where the representations differ:** our numpy buffers read the hair's terminators ~1.8x a render's (point-sampled
  tone against a filtered picture; thin deep slivers the image path takes for lines) and speckle ~0.4x; outlines agree
  (median buffer/render 1.00). Rank agreement across every calibrated region, view and measure (Spearman, render ratio
  against buffer ratio): outline 0.74, speckle 0.77, terminator 0.25, fragments 0.32. The last two agree on the flagged
  cells; the disagreement is small garment cells at 212 px/L and the back view, where the design's hair is barely shaded
  (1.35 kinks/L), so ratios there are noisy.
- **The design's own roughness** where it isn't clean: the collar in the three-quarter and profile (5.5 and 11 corners/L:
  the piece masks cut the sailor collar's stripes into cells), the bow (5-7.7: its loops and knot), the face (7-9: the
  eyes, blush strokes and mouth sit inside it). Ratios there are under 1 and say little.

## Proposed limits (on the worst view's ratio; PASS at or under, WARN at or under, else FAIL)

| detector | pass | warn | why |
|---|---|---|---|
| outline | 1.5 | 2.5 | flagged neck and collar read 2.2-7.4; clean regions 0.2-0.8 (hair 0.5-0.8, face 0.3-0.6, boots 0.2) |
| terminator | 2.0 | 2.5 | our buffers read hair ~1.8x a render, so a render at the design's 1.0 reads ~1.8 here; the flagged hair 2.4-2.9 |
| fragments | 1.5 | 2.5 | the flagged collar 2.5-6.2; hair 1.0-1.4 (see above) |
| speckle | 1.5 | 2.5 | the flagged neck front 1.9-2.2 in the buffers (3.4-3.7 in the renders) |
| peeks (count) | 4 | 12 | one build's numbers: look_v5's hair 8-27, its garments 0-4 |

On look_v5 through the gate's path these give: FAIL `art_outline_neck` 7.9 (front), `art_outline_collar` 8.8 (front),
`art_fragments_collar` 6.2 (front), `art_terminator_hair` 2.6 (three-quarter), `art_peeks_hair` 27 (three-quarter),
`art_terminator_bow` 3.1 (front), `art_terminator_skirt` 6.0 (back: thin spiky shade along the hem, where the design's
back is unshaded), `art_outline_top` 2.6 (back: the top's shoulder corners against a smooth drawn back);
WARN `art_speckle_neck` 2.2, `art_fragments_boots` 1.9 (profile); PASS the rest (hair outline 0.7, face 0.4, boots
outline 0.2). Keep them INFO until a few builds of history exist, then promote outline, speckle and peeks first (their
buffer and render readings agree best).

## Owners of what the checks flag

- hair (terminators, peeks, the stepped edge): **tool/hair-detail** (geometry and normals); the terminators' shading
  (proxy normals for the hair, the deep step): **tool/look2**, their round-2 item 4, which was waiting on these numbers.
- collar, bow, top, skirt hem, boots: **tool/body**.
- face and neck skin (the neck's silhouette in profile, the seam specks' geometry): **tool/face**; the neck's terminator
  and specks' shading: **tool/look2** (their chin-shadow item).
- Note the front neck outline's corners sit where the collar's torn tips cross the neck: fixing the collar moves it too.

## Open items

- **Stepped hair edges** (profile) aren't graded. Tried: drawn-line length within 0.006-0.02 L inside the hair's
  silhouette per L of outline: design 0.42-0.68, EEVEE 0.20-0.40, buffers 0.30-0.42, so ours read *under* the design
  (its strand lines run into the edge). The next try is parallelism: count only the lines running along the outline
  (their direction against the distance field's gradient), which the design's strands, meeting the edge at an angle,
  wouldn't.
- **face_090.png** (the perspective board) isn't measured: the boards are 85 mm, our drawings orthographic; the
  profile at the design's scale (after_profile) stands in for it.
- The body boards (600x1000, perspective) likewise; the collar and bow were measured on the head views resampled to
  the body sheet's scale.
- The design's collar in three-quarter and profile is rough by construction (piece masks cutting the stripes): a
  collar reference from garment_breakdown, or its cells merged across the stripes, would make those ratios mean something.
- Grades: INFO now; promote after history. Re-measure the calibration on the next look/hair round (the scripts are in
  this note's "Calibration").
- Box timing: the gate now compares CPU seconds (tool/gate-cpu); read it in the gate reports (State, next step 1).

## The original plan and findings (before any code)

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
