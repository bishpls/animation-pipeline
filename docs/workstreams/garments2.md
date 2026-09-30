# Garment pieces, round 2 (tool/garments2)

The outfit's pieces other than the skirt body, hem, flaps and boots (tool/body's): the puff sleeves, the waistband and
shorts, the skirt's pleat detail, the collar and bow, the wrist cuffs. Worktree `~/animation-pipeline-garments2`,
branch `tool/garments2` from tool/body d9d9b27 (rounds 4 and 5, garment-sampling 47b401f merged) plus pipeline-3d
2e3bdd5.

## Round 3: the jacket over the band (2026-09-30, resumed). Start here.

**Branch** `tool/garments2` with pipeline-3d 9397578 merged (face, eyes2, produced-cache, the process decisions and
`docs/OWNERSHIP.md`). The "before" build: `~/animation-pipeline-g2before` (branch `tmp/g2before` at pipeline-3d),
`charkit/out/g2_before`; rebuild it if pipeline-3d moves before the final page.

**Measured first: what the design shows at the junction.**
- The outfit masks label the jacket's lower part as the waistband wherever the jacket hangs over it: the front's
  notched corners (13% of the band's mask), the three-quarter's near front (46%), the back's hem (38%). In profile
  the band's mask holds only the jacket's lower part and the band itself is labelled skirt. Measures on the band now
  take its **ink core** (`pieceqa.ink_core`: the largest part of its mask the drawing's line class leaves connected;
  the jacket's hem stroke cuts the rest off): `waistband_{front,three_quarter,back}_{rows,width}` and
  `top_front_hem_step` (step b3aaf2c). Drawn junction (the band's visible top, QA frame): front -1.38 at the jacket's
  inner corners (x +-0.24), -1.343 under the bib, -1.371 at x +-0.3; back -1.39 in the middle, -1.371 at +-0.3;
  three-quarter -1.39..-1.37 on the near front. So the bib's hem is 0.035 L **higher** than the jacket's fronts (the
  masks had read the corners as band: +0.033).
- **The garment builders' eye line is 0.0235 L below the QA's.** Heights in garment specs (`rows`, `drawn_extent`,
  my `opening` and `drape`) are L from `eye_knobs.z`; the QA aligns our irises (0.0235 L higher) with the design's
  eyes. A spec height z lands at z - 0.0235 in every check. The bow's `lift` 0.03 had absorbed it; the band's rows here
  are set in the QA frame by hand (-1.31/-1.47 land at the drawn -1.3335/-1.4935). A builder-wide fix needs the iris
  line at garment-build time: integrator's call (it also shifts the hull-built skirt and flaps, possibly the
  0.024-0.028 L hem offset seen between the evaluator and the box).
- `top_*_over_band` read a jacket hung over the band all round as tucked: drawn alone, its back panel shows below the
  front hem and through the open front. Now tucked only within 0.08 L behind the band (depth; step a7a6845).
- `waistband_profile_overhang` now from the figures' front edges at fixed rows (the masks' profile band is the
  jacket's lower part; the hanging jacket hides the band's own front): step a7a6845.

**Built (garments.py, the upper garments' area):**
- `shell` over a band (`ease.mode: over`): the hem at the band's top less `hang` (a knot table by azimuth: the
  jacket's fronts hang lower than its sides, the back lowest), `hem_over_band`; the drape (`ease_over_band`) hangs out
  to the band's face plus `gap`, or a `flare` table by azimuth (the hem standing off the waist, from the hull and the
  front/back silhouettes), and `drape` hangs the fronts from the bust (the running maximum of the shell's radius down
  each column, front only: `az` [60, 100]) and brings them back in toward the hem (`taper`).
- `opening`: the jacket's open front as a signed cut (`half` [[z, half-width]]); `inside`: a shell kept inside
  another's opening plus a margin (the bib under the jacket's edges). Cuts are made clean by `snap_cuts` (border
  vertices moved onto each cut along the face's edges and diagonals).
- `refine`: the shell's region Catmull-Clark refined before cutting (the body's 0.038 L torso faces left each front
  corner one vertex and the hem stepping between them); weights carried, the body's vertex points map back for
  masking.
- The bib is its own garment, `bodice_panel` (cream shell inside the top's opening, 0.04 margin, its hem 0.005 over
  the band); the top lost its textured `panel` and `fold`. `detailqa`'s midriff lists take `bodice_panel`.
- The hem's `hang` knots fitted to the drawn junction by coordinate descent (scratch `fithang.py`: front, back and
  three-quarter columns plus the side hems): junction errors 0-0.01 L except the three-quarter's near side (0.028: the
  drawn front and three-quarter disagree about the side's height).
- Tests: `charkit/tests/test_jacket.py` (the cuts on their lines, the bib's margin, the hem over the band and lower in
  front, the flare), `test_pieceqa.py` (the ink core, the depth-aware junction).

**Box build `charkit/out/g2_m3` (68ae58c) against pipeline-3d's (db718ae):** piece_waistband 0.454 FAIL -> 0.892
PASS; piece_top 0.620 -> 0.653; piece_bodice_panel 0.66 (new: front IoU 0.80); top_front_over_band and
three-quarter 0.0 PASS (0.977/0.968 FAIL on the round-6 build), top_front_hem_step 0.007 PASS; waistband rows PASS in
front, three-quarter and back; the midriff gaps and panel edge PASS. top_front_opening FAILed there (0.040: a sliver
of bib beside our tails at z -1.05); the opening now narrows under the tails (ff1a053: 0.007 in the evaluator).
Worse: `body_front_skirt_overhang_{L,R}` PASS -> FAIL 0.113-0.115 and the band's widths (see Coordination: the
skirt's top stands out past the drawn-width band, since milestone 2's `fit_rows`), `body_front_torso_jump_L` PASS ->
WARN 0.014 (the jacket's side corner steps in 0.0235 L to the band; drawn 0.009), `sleeve_profile_rough_L` 0 -> 0.0096
WARN.

**Bow and cuffs: not into the spec this round.**
- Bow `wing`/`ribbon` (b1) on the jacket state (evaluator, skin mask rebuilt): piece_bow 0.703 -> 0.81 PASS,
  bow_front_flare 0.994 -> 0.468 WARN, tail width 0.308 -> 0.180 WARN, but bow_front_tail_gap 0.038 WARN -> 0.353
  FAIL, bow_front_torn 0.0002 -> 0.082 FAIL, collar_three_quarter_torn 0 -> 0.124 FAIL (the far wing cut where it
  passes the collar), collar_front_torn 0.137 -> 0.194. Needs the tails' parting and the wings' back edge first.
- Cuff template (k2 knobs) on the same harness: all four views' IoU up on the left cuff (0.57/0.64/0.52/0.60 ->
  0.66/0.68/0.61/0.71), the trims FAIL -> PASS (4), but the right cuff's three-quarter IoU 0.506 -> 0.442 and
  piece_cuff_R 0.668 -> 0.593, and the flares still FAIL (the back right's worse, 0.299 -> 0.381). The milestone-3
  figures (0.80-0.85) were read with the base build's skin mask; with the mask rebuilt for the variant they don't hold.

**The collar (item 3): the template is built, not in the spec. Blocked on the shoulders' height.**
- Built: a shell `outline` (`outline_dist`: the lapels between an inner V and an outer edge by height in front, the
  back flap to a bottom, signed distances in the front/back projections) and a `stripe` (faces a band in from the
  outer edge, a second material, its edges snapped onto the lines); `cuts` take `eye` (a height from the eye line).
  The jacket's `opening` can carry the collar's V above the bib's opening (scratch `fitcol.py`: `top_open`).
- Measured: our shoulder line stands 0.06-0.09 L under the design's (the garments' top edge at x +-0.3..0.4: front
  -0.547..-0.571 against the drawn -0.463..-0.486; back -0.547..-0.571 against -0.491..-0.514; 0.0235 of it is the
  eye-line frame above). The drawn lapels start at -0.50 at x +-0.16..0.39, where our body is still the neck (x +-0.12).
  A collar lying on our body can't reach them: its front IoU against the drawn collar 0.04 (the standing hull collar's
  0.43-0.47), piece_collar would fall from 0.757 PASS. So the spec keeps the hull collar (collar_front_torn 0.137 FAIL,
  its tips standing at the neck) until the shoulders rise (tool/body, and the eye-line frame), or a collar template
  standing off the body.
- The harness now rebuilds the skin's mask for a variant's garments (`g3lib.with_skin`): the swapped bundles had kept
  the base build's mask, which hid the chest in the collar's V.

**Coordination (tool/skirt):** the skirt's top follows the hull's band label's lower edge (`skirt_hull`, `under`),
which the masks put about 0.09 L high at the sides (the band's lower part labelled skirt): in front the skirt's top
stands out past the band from z -1.40 (x +-0.33 at -1.40, +-0.35 at -1.45 against the band's +-0.315) and in profile
it covers the band below -1.39. With the jacket now covering the band's top rows, that's what's left of the band's
width: `waistband_front_width` PASS -> FAIL (ours 0.44 against the drawn 0.52), three-quarter and profile likewise.
Suggested: tuck the skirt under the band garment's lower edge (its `rows` bottom) rather than the hull label's.
This is also what fails `body_front_skirt_overhang_{L,R}` in the default gate (PASS -> FAIL 0.115-0.118, the skirt
standing past the band's side in its lower half): it has been there since milestone 2's `fit_rows` narrowed the band
to its drawn width (0.63 L; the hull's rows had made it 0.77-0.80, which covered the skirt's top). Widening the band
again to hide the skirt would trade the band's own shape (piece_waistband 0.894 PASS, its widths) for another
piece's fault; left for tool/skirt and the integrator.

## State (2026-09-30, milestone 3)

**Branch** `tool/garments2` (see `git log -1`), with pipeline-3d b571f28 merged (tool/body round 6, hull-det,
garment-sampling). **Rescoped** (coordinator, after Michael's review of round 6): this workstream owns the UPPER
garments: the top/jacket and its cream bodice panel (bib), the waistband, collar, bow, puff sleeves, wrist cuffs and
shorts. The pleats moved to tool/skirt (their checks were dropped here; the code is in cda2b7f: `closeup_pleats`,
`our_pleats`, `pleat_checks` in pieceqa, and a knife-pleat layout that was never committed). The band's seam with the
skirt is coordinated with tool/skirt through these notes only.

**Done and in the spec** (clawd.json = clawd_body_pieces.json, clawd_body.json the same garments):
- puff sleeves as a template (`source: template`, `garments.puff`): spikes FAIL -> PASS in every view;
- waistband: `fit_rows` (the band's drawn width): piece_waistband 0.448 FAIL -> 0.652 WARN;
- shorts: `hem_level`, `hem_snap`, `hem_drop` 0.03: piece_shorts 0.408 FAIL -> 0.518 WARN, hems PASS (three-quarter
  FAIL: the drawn three-quarter hem is 0.05 L above the other three views').

**Built, not in the spec yet:** the wrist cuff template (`garments.cuff`, `source: template`, piece_cuff 0.67 -> 0.80-0.85
in the evaluator; front flare still off where the hand overlaps: see below); the bow's `wing`/`ribbon` knobs
(bow_front_flare 0.99 FAIL -> 0.47 WARN, piece_bow 0.662 -> 0.717).

**Measured, failing, next (priority order):**
1. **The jacket over the band** (Michael's new top item): `top_{front,three_quarter}_over_band` 0.977 / 0.968 FAIL
   (our band hides the jacket's hem: tucked under), `top_front_hem_step` 0.033 FAIL (the bib hangs lower in the middle),
   `top_front_opening` 0.142 FAIL (our cream is a flat trapezoid 0.18-0.27 L half-wide; the drawn bib is 0.05 L at z
   -1.0 widening to 0.105 at -1.2, then 0.18-0.19 in the jacket's notched corners at -1.25..-1.30).
   Plan: the bib as its own object (a `bodice_panel` shell of the top's front faces inside the opening, behind the
   jacket, tucked under the band at its foot) and the jacket's front opening cut out of the top (its edges then carry
   the outline rim); the jacket's hem hung over the band (outside it, 0.03-0.05 L below its top edge) with the notched
   front corners; `ease` gains an "over" mode. The midriff checks (detailqa) read `top` and `waistband`: add
   `bodice_panel` to their piece lists (the top is this workstream's now). Adding a garment restamps the outfit masks
   and the hull (reads_spec names the garments' names).
2. The band's height: `rows: [-1.33, -1.505]` once the jacket hangs over it (see "Coordination").
3. Collar: `collar_front_torn` 0.14 FAIL (only its two tips show above the bow, as thin horns), profile 0.018 FAIL;
   smoothing the conform doesn't help (cl1, cl2). The design's lapels lie on the chest between the neck and the bow's
   lobes; ours stand at the neck under the bow.
4. Bow: `wing`/`ribbon` (b1 in the scratch runs) into the spec; `bow_front_tail_width` 0.35 -> 0.23; the tails lie
   flat on the cream bib (no outline between them): the bib behind (item 1) gives them a depth step.
5. Cuffs: the template into the spec once its front flare reads right (the hand's base overlaps the cuff's lower
   inner corner in front: the rows now grow clear of the skin; re-measure).

## Measurement first (charkit/pieceqa.py)

On the design's grids (bodyqa's: 212 px/L, aligned on the eyes) against the drawn piece masks, the design measured the
same way; the drawn masks are closed by a 0.012 L disk and their holes filled first (the drawing's fold strokes are
slits in them). Checks, registered in history.STEPS at 12c3b97, tests `charkit/tests/test_pieceqa.py`:

| check | what | limits |
|---|---|---|
| `sleeve_{view}_spikes_{L,R}` | spikes on the sleeve's silhouette: what an opening by a 0.03 L disk cuts off that stands 0.012 L or more out (a horn, a pointed corner), the deepest beyond the design's; counts beside | 0.006 / 0.015 L, and the count |
| `sleeve_{view}_rough_{L,R}` | the silhouette's outline roughness beyond the design's | 0.004 / 0.008 L |
| `sleeve_{view}_profile_{L,R}` | the puff's width across its arm at tenths from its cap to its cuff: RMS against the design's (the pear: narrow at the cap, widest low, gathered into the band) | 0.02 / 0.04 L |
| `sleeve_standoff_{L,R}` | 3D: the puff seen along its arm (the band's ring normal), area-equivalent radius over the arm's under the band, against sleeve_closeup's cross-section (segmented from the reference: puff / arm 1.93, band / arm 1.12) | 10% / 20% |
| `waistband_{view}_rows` | the band's top and bottom edges (medians over its middle columns) | 0.02 / 0.04 L |
| `waistband_{view}_width` | its median row width over the design's | 5% / 10% |
| `waistband_profile_overhang` | in profile, the top's front edge just above the band ahead of the band's front, against the design's (0.019 L) | 0.015 / 0.03 L |
| `shorts_{view}_hem`, `shorts_{front,back}_width` | the shorts' lower edge; their width | 0.02 / 0.04 L; 5% / 10% |

Views: front, three_quarter, profile, back where both sides show the piece (150 px or more).

## Baseline (the branch's start, box build `charkit/out/g2_base`)

The spike detector finds what Michael saw: the sleeve caps' pointed top corners (front, back, three-quarter) and a
small tip where the sleeve's lower rim pokes out past the cuff on the inner side. The design has none.

## The puff sleeve as a template (`garments.puff`, kind `sleeve`, `source: template`)

Cause of the spikes: `sleeve_hull` lofted an open tube round the upper arm through the hull's sleeve points between
their percentiles; its top rim, cut square across the arm over the shoulder, stood up as a pointed corner, and its
lower rim poked out past the cuff. The template (Michael's direct control, as round 5's boots):
- sections on the upper arm's frame (`puff_frame`: the shoulder joint, d down the arm, o out, f front; the two frames
  mirror images), superellipse quadrants whose extents are a knot table `profile` [[t, out, front, in, back]] (L down
  the arm from the shoulder joint), exponent `round`;
- a round cap: a quarter ellipse `cap` L long above the table's first station, closed by a fan at the apex (a knot at
  zero would end in a point);
- past the last station each column rounds under (a quarter ellipse) to its band's outside at the band's top (`band`:
  the cream sleeve cuff's garment, built to find it), `over` proud, then `tuck` L on inside the band's inner surface
  (`clear` in): the rim hides under the band;
- `gathers` [n, cap amp, band amp, reach] fine folds fading in from the cap's seam and the band; `lobes` [n, amp] the
  balloon's scallops (sleeve_closeup's cross-section);
- `mirror`: the right sleeve takes the left's knots in its own frame (one table). Rigid on the upper arm.
- `puff_knots(A, hull, side)` measures a starting table from the hull (quadrant percentiles per station); the spec's
  table was then fitted to the design's width profiles (front, back and profile views; the scratch fit multiplies the
  out+in extents by the front/back width ratio per station and front+back by the profile's, five rounds).
Tests: `charkit/tests/test_puff.py`.

## Waistband and shorts

`belt_hull` takes `rows` [top, bottom] (L from the eye line: the drawn band's edges) and `fit_rows` (the hull rows
whose section it takes, upright): the hull's waistband label runs up into the top's flared hem (its rows above -1.38
are 0.77-0.80 L wide against the drawn band's 0.60-0.64), and the band took that width.

## Coordination with tool/body (the midriff junction)

What the waistband needs from tool/body (the top's hem, `shell`'s `ease` and the midriff checks are theirs):
- The drawn band stands from z -1.338 (its top, front) to -1.493 (its bottom); ours from -1.28 (the hull's span).
  With the band's `rows` at [-1.33, -1.505] (fit rows [-1.40, -1.47]) the band is right (piece_waistband 0.448 FAIL
  -> 0.888-0.892 PASS, its rows and widths PASS/WARN) but the top's hem then covers the band's upper 0.03-0.05 L in
  front (the ease holds the top at the band's face 0.03 L under its top edge, and the band's rounded top row lets it
  show) and a see-through gap opens in profile: body_profile_midriff_gap 0.0 PASS -> 0.028-0.047 FAIL (variants: the
  top's `ease.hold` 0, `hem_drop` 0; the band's top at -1.31 or -1.33). With `hem_drop` 0 the gap opens in front too.
- So the band's height is left at the hull's span on this branch (only its width: `fit_rows`): piece_waistband 0.448
  FAIL -> 0.652 WARN, widths FAIL -> WARN/PASS, the midriff checks unchanged.
- Needed: the top's hem ending at the band's top edge outside it, overhanging it a little (the design's jacket stands
  0.019 L in front of the band in profile: `waistband_profile_overhang`), with nothing see-through under it; then
  `rows: [-1.33, -1.505]` on the band.

## Harness (scratchpad, not tracked)

A box build's bundle with garments rebuilt by this worktree's code swapped in (the numpy builders as bodyeval runs
them, then Solidify and one subdivision level, the outline's pull-in 0.0012 m along outward normals, textured UVs
carried): unchanged pieces reproduce the box's piece checks (waistband, cuffs identical; the hull sleeves within 0.012,
their open rims subdivide a little differently). QA renders of close-ups on the design's grids at 3x (the design
upscaled beside). The venv renderer draws the top's back faces black (their u = 5 is clipped; Blender repeats it and
the QA's classes clamp it): pictures only.
