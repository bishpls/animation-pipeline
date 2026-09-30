# Workstream: artifact QA, measuring "obvious jaggedness" (`tool/artifacts`)

**State (2026-09-30): round 2 done; final gates PASS both specs at `b745759` into pipeline-3d `8a7d4ea`.** The branch merges cleanly into `ec28825` too.
pipeline-3d `9397578` merged (`0976017`), then `cfcdc3a` (`f87620c`: self-registration; qa3d.py and history.py took the
new side; the part is `@qa_part('artifacts', order=2200, prefix='art_', table='artifacts')` on `artifactqa.measure`;
the steps are in `charkit/steps/artifactqa.py`, text unchanged; `test_registry.py` ok). Round 2:
1. **Step 0, the design's stamp** (`2a963bb`, `15ec3f7`): the stamp now hashes the outfit masks' bytes and the graph's
   piece id/type pairs (what `design_body` reads), not the produced `outfit_graph.json` (its springs and comparison
   differ between copies and specs while the masks are bit-identical: laptop, the box's artifacts/3d/body copies and
   both specs all hold masks `074d9a...`). The code digest (`design_code`) covers the design-side functions and the
   constants and defaults they read, not the module's other lines, so a grade's limit or a docstring no longer
   re-measures. `artifacts_design.json` holds a record per stamp (`records`; both specs share one today), and a
   stamp it lacks is made once per machine into the produced references' shared cache
   (`$CHARKIT_PRODUCED_CACHE/artifacts_design/STAMP-EYEX.json`), not once per build.
2. **Michael's flags as calibrated checks** (`2a963bb`..`b9bc3bd`): silhouette detectors on the body frame, graded
   against the design in the same view; each passes on the design and fails on the build where he saw the flag
   (table below). Registered at `b9bc3bd` (since the self-registration merge: `charkit/steps/artifactqa.py`).
3. **Fixed on the way:** the boots region read only the cuffs since round 5 (`boot_L`/`boot_R` weren't in OBJECTS);
   the body frame started 0.5 L under the eyes and cut the hull sleeves' caps (and the collar's top) off: it starts
   at 0.2 L now; a wrong row-to-height map in the body frame (sign) is fixed before any check used it.

**Gates:**
- `9e3691c` into `301b661` (before the self-registration merge), both **PASS**: tests all ok, every art_* check new,
  no `art_design` note (the stored design served both specs). Build CPU seconds: default 1381.3 -> 1275.3, clawd_mh
  328.0 -> 324.2 (within 3%: step 0 done). Reports `charkit/out/gate/gate_tool-artifacts_9e3691c_into_301b661{,_clawd_mh}.md`.
  (The earlier pair at `15ec3f7` lost its ssh session at the box's load 56; no report.)
- `f87620c` into `cfcdc3a` (after the self-registration merge), both **PASS**: CPU seconds default 1390.2 -> 1424.9
  (+2.5%), clawd_mh 510.8 -> 339.5; the 2x2: default geometry unchanged, clawd_mh geometry changed with the hair knobs
  (below). Its default build read `art_speckle_neck` 16.5 and `art_outline_neck` 9.7 from the back view's neck
  slivers (0.005 L^2 between the hair and the collar), and `art_points_boots` 20.6 on the template boots: fixed at
  `f771ec1` (face and neck left out of a view showing under 0.01 L^2; points_boots back to INFO), step registered at
  `b745759`.
- **Final: `b745759` into `8a7d4ea`, both PASS** (pipeline-3d moved during the gate): tests all ok (test_artifactqa,
  test_registry among them), every art_* check new, no `art_design` note; CPU seconds default 1299.7 -> 1254.5,
  clawd_mh 328.6 -> 331.4; default geometry unchanged in the 2x2. The default build's WARNs (the calibrated checks,
  capped): outline_neck 1.66, outline_collar 4.08, fragments_collar 2.1, terminator_hair 2.49, peeks_hair 19,
  points_sleeves 31.4, bumps_sleeves 44.2, band_lower 2.47. Reports
  `charkit/out/gate/gate_tool-artifacts_b745759_into_8a7d4ea{,_clawd_mh}.md`.
- The gate's build diff shows `hair` knobs changed between base and candidate though this branch touches no spec or hair
  file: the gate's own (the candidate is built as `+dirty`); for the integrator.

**Statuses:** the checks calibrated on a flag (`artifactqa.CALIBRATED`, 14: outline_neck, speckle_neck,
outline_collar, fragments_collar, terminator_hair, peeks_hair, spikes_boots, bumps_boots, mirror_self_boots,
mirror_waist, points_sleeves, bumps_sleeves, bumps_legs, band_lower) report their proposed grade
capped at WARN until the integrator promotes them (`PROMOTED`); all other art_* checks stay INFO with the proposed grade
beside. On the current build 8 read WARN: outline_neck, outline_collar, fragments_collar, terminator_hair, peeks_hair,
points_sleeves, bumps_sleeves, band_lower. The perceptual result (8ae6ce9) found the region-mean metric blind to local
defects; these per-flag geometric checks are the signal (the coordinator: rho 0.59 against Michael's labels).

**Next steps, in order:**
0. Done: the final gates (above).
1. Report to the integrator (the summary table below, the review page, the open items).
2. When a flagged area's fix lands (tool/garments2's sleeves, tool/skirt's band, tool/hull-limbs' thigh), re-read its
   check on that build: it should drop to PASS. That's the "good build" several flags still lack.
3. Promotion (the integrator's call): outline, speckle, peeks, spikes_boots, bumps_boots, points_sleeves,
   bumps_legs and mirror_waist first (their separations are widest; see "Proposed limits").
4. If the design-side detectors change: `python -m charkit.artifactqa design BUNDLE_DIR` (~15 s; any bundle whose
   spec's masks match: both specs today) and commit `artifacts_design.json`.

**Review page:** `charkit/out/artifacts_review/flags/index.html` (the flags: design | the flagged build | current at
the body sheet's scale, the level orthographic projection, detector marks, the summary table, other workstreams'
checks per flag). Round 1's calibration page: `charkit/out/artifacts_review/index.html`. The page's generator and
the measuring scripts: `charkit/out/artifacts_review/scripts/flags/` (copied from the session scratchpad; `meas.py
NAME=BUNDLE` writes `m_NAME.json`, `ctab.py` tabulates checks, `page.py OUTDIR` writes the page).

## Michael's flags as regression checks (round 2, 2026-09-30)

Measured with the code at `b9bc3bd` on each build's bundle (the QA's numpy drawings: level, orthographic, the body
sheet's 212 px/L). Builds: design (the turnarounds); current = pipeline-3d `9397578` + this branch (box,
`charkit/out/art_default`, and `art_mh` for clawd_mh); look_v5 (`~/animation-pipeline-look/charkit/out/look_v5`);
body4b, body5b, body6 = tool/body rounds 4-6 (`~/animation-pipeline-body/charkit/out/body{4b,5b,6}_render`); g2m2 =
tool/garments2's template sleeves (`~/animation-pipeline-garments2/charkit/out/g2_m2`); jaw_4/jaw_5 (tool/face).
Values: the graded value (the worst view's excess over the design, or ratio to it) and, in brackets, ours and the
design's raw values in that view. The design reads PASS against itself; its raw value is the baseline beside ours.

| flag | check | design (raw) | bad build: value | current: value | proposed pass / warn |
|---|---|---|---|---|---|
| jaggedness, three-quarter and side (hull-lofted pieces) | art_outline_neck | 0.85 corners/L (front) | look_v5 7.9 FAIL (7.9 vs 0.85, front) | 1.6 WARN (three-quarter: 1.59 vs 0.78) | x1.5 / x2.5 |
| | art_speckle_neck (the dotted seam) | 32.6 specks/L^2 (front) | look_v5 2.2 WARN (front) | 1.3 PASS | x1.5 / x2.5 |
| | art_outline_collar | 0.84 (front) | look_v5 5.5 FAIL | 4.3 FAIL | x1.5 / x2.5 |
| | art_fragments_collar | 0.13e-3 L (front) | look_v5 3.5 FAIL | 8.0 FAIL | x1.5 / x2.5 |
| | art_terminator_hair, art_peeks_hair | 4.35 kinks/L; none | look_v5 2.6 FAIL; 27 FAIL | 2.1 WARN; 21 FAIL | x2.0 / x2.5; 4 / 12 |
| boots: twisted ankle, jagged protrusion, uneven soles, doubled toe, no heel | art_spikes_boots | 0 L | body4b 0.063 FAIL (profile) | 0 PASS | 0.015 / 0.025 L |
| | art_bumps_boots | 73 deg (profile) | body4b 63 FAIL (136 vs 73) | 13 PASS (82 vs 68, front) | 20 / 30 deg |
| | art_points_boots (INFO: too thin) | 52 deg (front) | body4b 35 FAIL (87 vs 52) | 16 (20.6 on cfcdc3a) | 20 / 30 deg |
| | art_mirror_self_boots | 0.037 (front) | body4b 1.79 WARN | 0.54 PASS | x1.5 / x2.5 |
| midriff: one-sided distortion (skirt past the band on her right) | art_mirror_waist | 0.012 (back), 0.034 (front) | body5b 6.9 FAIL (0.138); body4b 6.4 FAIL | 1.12 PASS (0.022) | x1.5 / x2.5 |
| | art_bumps_skirt, art_points_skirt | | body5b 59 FAIL, 38 FAIL (the lopsided back) | 13 PASS, 0 PASS | 20 / 30 deg |
| puff sleeves' spikiness | art_points_sleeves | 29 deg (front) | current (hull sleeves) 32 FAIL (61 vs 29) | = bad; g2m2 (template) 0 PASS | 20 / 30 deg |
| | art_bumps_sleeves | 35 (front), 0 (profile) | current 55 FAIL (profile 65 vs 0) | = bad; g2m2 0.8 PASS | 20 / 30 deg |
| bump on the back of the leg, profile | art_bumps_legs | 13 deg (profile) | body5b 42 FAIL (56 vs 13); body4b 42 FAIL | 0 PASS (the flap hides it) | 20 / 30 deg |
| skirt and flaps' zigzag band | art_band_lower | 7.1 kinks/L (profile) | body6 2.67 FAIL (18.9 vs 7.1) | = body6 2.67 FAIL; clawd_mh 2.75 FAIL | x1.5 / x2.0 |
| chin and neck: nick, taper | (face_region, tool/face) jaw_line_bend | 4.4 deg | jaw_4 24.4 FAIL, jaw_5 41.2 FAIL | 41.2 FAIL | theirs: 6 / 10 |
| | jaw_taper_shape, chin_tip | 0, 0.843 | jaw_4 0.035 WARN, 0.30 FAIL | 0.028 WARN, 0.59 WARN | theirs |

What each separation rests on, and what it can't see:
- **Boots** (round 4 against the template from round 5): the protrusion and the doubled, heelless toe are a spike
  (0.063 L) and a 136 deg knob in profile; the template reads 0 and 82 deg (the design 73). tool/body's detailqa
  `boot_*` checks cover the ankle jog, heel, doubled stroke and soles in 3D (round 4 18 FAIL, round 5+ PASS).
- **Midriff:** the asymmetry of jacket + band + skirt + flaps about the figure's axis. Round 5's jut and round 4's
  lopsided back read 6-7x the design; round 6 on 1.1x. The **ledge** (round 4) is detailqa's `body_*_torso_jump`
  (0.028 FAIL -> 0); the **jacket over the band** is tool/garments2's `top_*_over_band` (pieceqa, not merged): not
  re-measured here (a layering question, not a silhouette's).
- **Sleeves:** the hull sleeves' caps are a pointed corner (61 deg over 0.02 L) and a knob (65-89 deg over 0.06 L);
  the template and the design round them. **Round 5 (body5b), where Michael flagged them, reads clean:** its hair
  covered the caps in the level view (the boards' raised camera showed them). The current build, with the same
  sleeves and the new hair, shows them. tool/garments2's `sleeve_*_spikes` measure the piece's own mask and see both.
- **Leg bump:** a 56 deg knob over 0.06 L behind the thigh in rounds 4 and 5 (on the silhouette). **From round 6 the
  flap's train covers it in the level view,** so the current build reads 0 while detailqa's `body_profile_leg_back`
  (0.207 FAIL on the box) still sees the geometry. The flag holds for what's visible; the geometry is tool/hull-limbs'.
- **Band zigzag:** the band is a texture, so it's measured on the picture drawn with its textures (`qa3d.draw`, ss 1:
  its mesh and tone buffers are `buffers()`' to the bit, checked). Kinks per L of the dark band's edge (25-90 deg over
  0.006 L: pixel stairs) against the design's few clean steps: every build reads 2.4-2.7x (round 4-6, clawd_mh); no
  build has a clean band yet (tool/skirt's). The design passes by construction; the calibration's good side is only
  the design until tool/skirt's band lands.
- **Chin and neck:** tool/face's `face_region` checks are the calibrated ones (design all PASS; jaw_4 FAIL). This
  module's neck outline doesn't separate the nick: jaw_4 and jaw_5 read alike (3.17 and 3.20 corners/L in
  three-quarter), and the nick is 0.005 L, a pixel here. Anti-gaming: not tuned to pass.

**Can't be measured yet:**
- **The back's warping tuck-in** (round 6): tried the waist's silhouette bumps and dents at 0.06 L (junctions left out)
  and its asymmetry; neither separates round 6 from the design (the pinch sits at the band/skirt junction, which the
  design has too, and in the pleats' shading). tool/skirt's skirtqa (back outline, the flaps' gap, the pleats' pinch)
  is the place; it's in progress there (untracked).
- **The jacket over the band:** layering, measured by pieceqa on tool/garments2.
- **The chin's taper and the nick** as artifacts: see above (face_region measures them).

**Other findings on the current build** (INFO, not flagged by Michael): the back view's neck shows only slivers of skin
between the hair and the collar (0.003-0.005 L^2; left out of the rates since `f771ec1`; whether they read as a defect
is tool/hair3's and the collar's to judge);
`art_terminator_collar` 20.7 (three-quarter) and `art_fragments_collar` 8.0 (front): the collar's torn tips
(tool/garments2's collar item); `art_bumps_collar` 44 and `art_bumps_flaps` 49 (the collar's back knob in profile, the
flap tail's point in three-quarter); `art_spikes_flaps` 0.057 (three-quarter: the tail tip).

**Cost:** the part takes 6-8 s CPU a build on the laptop (was 3.5-4): the body frame drawn with textures (+~1 s), the
silhouettes (+~2 s). The design is stored, so no build re-measures it.

## What was built

- **Where it measures.** Our side runs on the QA's own numpy drawings, not EEVEE boards (the build box renders none):
  `artifactqa.buffers()` is `qa3d.draw()`'s z-buffer and tone buffer without its picture, textures or pixel filter
  (bit-identical to draw's `aux` buffers, about half the time). Two frames, each from front, three-quarter (the sheet's
  angle), profile and back under the boards' light for the view:
  - the head frame at 400 px/L (0.85 L either side, 1.25 above to 1.0 under the eye line): hair, face, neck;
  - the body frame at the body sheet's px/L (212), from 0.2 L under the eye line to the feet (0.5 until round 2):
    collar, bow, top, skirt, boots, and in round 2 the silhouettes (sleeves, flaps, the waist, the skirt with its
    flaps, the legs). Round 2 draws it with `qa3d.draw` (ss 1) for the hem band's texture.
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

Round 2's silhouette checks (`SHAPE_CHECKS`; the worst view's excess over the design, floored, or ratio to it):

| check | pass | warn | why (calibration above) |
|---|---|---|---|
| art_spikes_* | 0.015 L | 0.025 L | round 4's boot 0.063, look_v5's 0.029; clean builds 0-0.013 (one borderline 0.013 spike on the template boots' back) |
| art_points_* | 20 deg | 30 deg | hull sleeves 31-32, round 4 boots 35; template boots 16, template sleeves 0 |
| art_bumps_* | 20 deg | 30 deg | round 4 boots 63, round 5 leg 42, hull sleeves 55; template boots 13, template sleeves 0.8 |
| art_mirror_waist | x1.5 | x2.5 | rounds 4-5 6.4-6.9, look_v5 3.1; round 6 on 1.1-1.2 (clawd_mh 2.2 WARN: the MakeHuman body's skin at the band's sides in back) |
| art_mirror_self_boots | x1.5 | x2.5 | round 4 1.79 (WARN only: a mild separation), template 0.54 |
| art_band_lower | x1.5 | x2.0 | every build 2.4-2.7 (no clean band exists yet) |

Promote first: spikes_boots, bumps_boots, points_sleeves, bumps_legs, mirror_waist (margins 2x or more between the
bad and the clean build). Keep art_band_lower at WARN until tool/skirt's band gives a clean build to calibrate on;
mirror_self_boots stays INFO (1.79 against 0.54 is a weak separation).

## Owners of what the checks flag

- hair (terminators, peeks, the stepped edge): **tool/hair-detail** (geometry and normals); the terminators' shading
  (proxy normals for the hair, the deep step): **tool/look2**, their round-2 item 4, which was waiting on these numbers.
- collar, bow, top, skirt hem, boots: **tool/body**.
- face and neck skin (the neck's silhouette in profile, the seam specks' geometry): **tool/face**; the neck's terminator
  and specks' shading: **tool/look2** (their chin-shadow item).
- Note the front neck outline's corners sit where the collar's torn tips cross the neck: fixing the collar moves it too.
- Round 2: sleeves' caps (points, bumps): **tool/garments2** (the template is the fix, unmerged); the band's zigzag,
  the back's tuck-in, the flaps' tail tips: **tool/skirt**; the leg's knob: **tool/hull-limbs** (the thigh's top rows);
  the neck's bits between the back hair locks: **tool/hair3**; the collar's torn tips: **tool/garments2**; the nick
  and the taper: **tool/face**.

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
- Round 2: the flags that still lack a clean build to calibrate against: the band (tool/skirt), the sleeves on the
  design's own back view (its jacket and sleeves are one cell: the back can't fail there), the leg bump from round 6
  on (hidden by the flap in the level view: measure it with the flap hidden, or leave it to detailqa).
- The back's tuck-in and the jacket over the band aren't measured here (above).
- A board-camera variant (the boards' raised camera) would see what the level view hides (round 5's sleeve caps behind
  the hair); the process decisions put review close-ups in the design's projection, so it's not built.
- `artifactqa.design_code` reads `cache.code_units`; if tool/infra's self-registration moves the part, keep the stamp's
  code digest on the design-side functions only.

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
