# Garment pieces, round 2 (tool/garments2)

The outfit's pieces other than the skirt body, hem, flaps and boots (tool/body's): the puff sleeves, the waistband and
shorts, the skirt's pleat detail, the collar and bow, the wrist cuffs. Worktree `~/animation-pipeline-garments2`,
branch `tool/garments2` from tool/body d9d9b27 (rounds 4 and 5, garment-sampling 47b401f merged) plus pipeline-3d
2e3bdd5.

## State (in progress)

Milestone 1: the measurement (`charkit/pieceqa.py`, QA part `piece_details`, 12c3b97) and the puff sleeve as a template.

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
