# Garment pieces, round 2 (tool/garments2)

The outfit's pieces other than the skirt body, hem, flaps and boots (tool/body's): the puff sleeves, the waistband and
shorts, the skirt's pleat detail, the collar and bow, the wrist cuffs. Worktree `~/animation-pipeline-garments2`,
branch `tool/garments2` from tool/body d9d9b27 (rounds 4 and 5, garment-sampling 47b401f merged) plus pipeline-3d
2e3bdd5.

## Paused (2026-09-30, usage limit). Start here.

- **Branch** at the merge of pipeline-3d 53a557f (tool/face, tool/eyes2, the spec-alias test): `cbea649`. No code
  changed since milestone 3; the jacket-over-band work (item 1 below) hasn't started in code.
- **Box job running:** the "before" build, `~/animation-pipeline-g2before` fast-forwarded to 53a557f (branch
  `tmp/g2before`), `remote build charkit/spec/clawd.json --out charkit/out/g2_before --boards views --no-blend`, log
  `charkit/out/remote_g2_before.log` there. Rebuild it again if pipeline-3d moves before the final page.
- **Found while reading the design (to confirm with numbers first):** the drawn piece masks label the jacket's lower
  front corners as the waistband. In front, 0.2-0.3 L out, the masks' `top` ends at -1.30 and the band starts there,
  while the drawing's jacket fronts hang to about -1.35..-1.37 (their hems slant down toward the opening: about -1.32 at
  x ±0.4, -1.37 at the inner corners). So the design's `top_front_hem_step` 0.033 L (the band's visible top lower in the
  middle) is an artefact: drawn, the band shows from about -1.33 under the bib and -1.36 under the jacket's corners,
  so the middle is higher. Next: measure the design's junction from its ink (the band's region flooded inside its
  strokes), not the masks, and re-derive the hem step's design value.
- **Also to settle before building:** the plan tucks the bib's foot under the band, but `top_*_over_band` counts
  `bodice_panel` among the jacket's pieces and expects it over the band. Either the bib hangs over the band too (flush
  with its face, the jacket's fronts proud of it) or the check leaves the bib out. The drawn bib's bottom is a gentle
  curve at about -1.325, the band's top edge line.
- **Drawn jacket front:** the opening's edges stand at x ±0.175-0.18 L from the hem up to the bow tails' ends (-1.22);
  above that the tails cover them.
- **Scratch harness** (untracked): `g2lib.py`, `puffrun.py`, `specrun.py` and the junction crops `j0.py`-`j2.py` in
  this session's scratchpad (`/private/tmp/claude-501/-Users-michaelbishop-opus-anim-test/ed87a979-.../scratchpad`).
  Swap garments into `charkit/out/g2_m2` (the current box build of this branch's spec).
- **Next, in order:** confirm the mask finding and fix the design-side measure; then item 1 below (the bib as
  `bodice_panel`, the opening cut, the jacket's hem over the band with the slanted front corners, `bodice_panel` in
  detailqa's midriff piece lists), in the evaluator first; then the box build.

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
