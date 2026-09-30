# The skirt and the flaps (tool/skirt)

Owner of the lower garments: the skirt (silhouette, pleats, hem, its stepped band), the overskirt flaps (shape, drape,
their stepped band), and the skirt's back and its tuck into the waistband. tool/garments2 owns the upper garments
(jacket, bodice, waistband, collar, bow, sleeves, cuffs, shorts); the waist-to-band seam is coordinated through notes.

**Branch** `tool/skirt` in `~/animation-pipeline-skirt`, from pipeline-3d (b571f28, then merged 53a557f and db718ae).

## Michael's review of round 6 (the brief)

1. The flaps' drape and shape (the most severe): in profile each flap is a big curved orange lobe hanging from the back
   waist with a ragged dark band; the design's flap is a stepped panel. piece_overskirt_panel_L 0.42 FAIL, R 0.62 WARN.
2. The stepped band on the skirt's hem and the flaps: fine pixel-stairs, or a dark tip on the flaps, where the design has
   a few clean, larger steps.
3. The back: the flaps part into a pointed V gap showing the dark underlayer; the pleats pinch and warp where the skirt
   meets the band; the back outline doesn't match.

## What the design draws (body_turnaround, on the QA grid, L from the eye line)

- **Back.** Each flap is a narrow wedge at the waist, at the band's lower back-side corner (her left flap x 0.22..0.33),
  fanning out and down over the skirt to 0.47..0.97 at the skirt's hem (z -2.5). Outside it a crescent of the skirt's
  side shows, with the skirt's own level dark band at its hem. Between the two flaps the skirt's centre-back panel shows:
  a trapezoid from about +-0.22 at the waist to +-0.47 at the hem, then its level band and the shorts. So there is a gap
  between the flaps, but it starts at the waist and widens down; round 6's flaps start wide at the centre back and part
  into an inverted V from mid-height. Below the skirt's hem each flap's tail ends in a staircase of four steps descending
  from its outer corner (x 0.98, z -2.52) inward to its tip at the inner corner (x 0.70, z -3.20), with a dark band of
  constant thickness along the treads and risers.
- **Profile** (her left flap). It starts at the back of the band (x 0.46..0.50, z -1.47), lies on the skirt's back flare
  (its front edge meets the skirt's hem at x 1.05, z -2.58), and its tail carries on down and back to the tip at x 1.57,
  z -3.12: the back edge about 34 deg off vertical, the inner edge's tail about 28 deg (the skirt's back flare is about
  38 deg). Three to four steps descend from front to back.
- **Front and three-quarter.** Only the tails show, below the skirt's hem at the sides; each tip is on the flap's inner
  side.
- The outfit masks (`charkit/out/clawd/outfit/outfit_masks.npz`) hold only the tails in back and profile: the flap's
  upper part over the skirt is the same colour and was cut as the skirt. A full drawn flap is its face filled between the
  drawn lines (line gaps closed by 2 px) from a seed inside it, plus the outfit mask's tail.
- **Michael's call "hang"** (the decision page's hang against a near-horizontal swept train): read as "no backward sweep
  beyond the skirt's own flare". The drawn train is itself close to a hang: its tail continues a little steeper than the
  skirt's flare.

## Plan

1. Measure (charkit/skirtqa.py, QA part `skirt`, registered in history.STEPS, tests), and show the checks FAIL on round 6
   (`~/animation-pipeline-body/charkit/out/body6_render/bundle`):
   flap shape per view (IoU against the full drawn flap, width profile down its length, attach line, hang angle, the
   profile's sweep); the stepped band per piece (step count, step size, band height); the back (outline, the gap between
   the flaps, the pleats' pinch at the band).
2. The flaps as a template (`garments.flap_template`): edge tracks over the skirt (azimuth per height), a tail per column
   (a stepped lower edge from a knot table), the band as faces of a second material aligned to the steps (crisp in the
   render and exact in the QA, which labels faces at their UV centre), mirrored left/right; fitted on the evaluator.
3. The skirt's band as geometry the same way (a few large steps beside the cream panel, level elsewhere).
4. The back: the tuck under the band and the pleats (tool/garments2's pleat measure is at cda2b7f: skirt_closeup's
   top-down view reads 14-15 orange and 3 cream pleats; ours 17 and 5). Keep garments2's arm_points change in merges.
5. Gates: `python -m charkit remote gate tool/skirt --into pipeline-3d`, and with `--spec charkit/spec/clawd_mh.json`.

Spec edits go into clawd.json and clawd_body_pieces.json together (test_spec_alias), and clawd_body.json where it
applies.

## Measurement (charkit/skirtqa.py, QA part `skirt`; 9153f09, 4a2bac1, d61ae88)

Registered in history.STEPS (0860201, a595dac). Tests: `charkit/tests/test_skirtqa.py` (synthetic stairs, fills, gaps;
calibration: every check PASSes on the design itself, `design_as_ours`, and the flap, band, outline and clearance checks
fail on a round-6-like corruption of it).

- **The drawn flaps.** The outfit masks hold only the flaps' tails in back and profile: the flap's face over the skirt is
  the same colour and was cut as the skirt. `drawn_flaps` fills that face between the drawn lines (gaps closed by 2 px)
  from seeds in `charkit/refs/clawd/skirt_marks.json`, with wall segments where a drawn line fades or breaks (the back's
  right flap's inner edge; the profile's front edge, drawn as two offset strokes), plus the outfit mask's tail.
- **The drawn bands.** The outfit masks leave the trims out (the skirt's band almost wholly) and cut the skirt's band as
  the shorts where both are dark. `design_bands` reads them as dark cells between the drawn lines, each given to the
  face it borders most, clipped to 0.15 L of it.
- **Steps** are read on the band's top edge under the face (per column, the row under the face's lowest pixel where the
  band lies beneath it), simplified to a polyline (2 px): a step is a riser (steeper than 45 deg, at least 0.015 L)
  between two treads at least 0.02 L wide. The drawn stairs tilt with the flap's hem, so treads needn't be level.
  The design reads: flaps two risers (three treads under the face) of 0.13-0.16 L, treads 0.10-0.12 L, band 0.15-0.20 L
  high; the skirt's band 0.13-0.15 L high, level at the back and sides, climbing in steps of about 0.1 L beside the
  cream panel (front three per side, three-quarter three, profile two).
- **Round 6** (its box bundle, `~/animation-pipeline-body/charkit/out/body6_render/bundle`): 36 of the 44 checks FAIL.
  The evaluator reproduces the box's hems exactly (front 0.0424, back 0.0236, three-quarter 0.0471, profile -0.0517).

## The flap template (garments.flap_template; `shape: template` on a `source: flap` panel)

Knot tables fitted to the design's silhouettes: the outer and inner edges' azimuths down the skirt (`edges` [s, outer,
inner]), the standoff (`stand`), a stepped tail per column (`tail`: steps, outer and inner lengths, widths), the tail's
hang (`droop` toward plumb, `out`), the band's thickness (`band`). The band is geometry (a second material on the faces
within `band` of the stepped edge; rows and columns on the stair's corners), not subdivided. The right flap mirrors the
left (`flap_mirror`). The flaps lie on the skirt's band-free surface.

**The skirt's band as geometry** (`skirt_hull`'s `band`: height, and `stair` knots [degrees out from the panel's edge,
height]; `band_rows`): rows per column on the band's levels, a third material. A first try (the stair's rises at 0.1 L)
reads the design's rises exactly in front (0.099 against 0.099) and a level band at the back; its treads are too narrow
(0.10 against 0.14 L) and the back gap's dark share went 0.216 FAIL -> 0.0 PASS.

**Fitting** (scratch `sk/fast.py`, `sk/fit.py`): the scene without the flaps z-buffered once per view, each candidate's
flaps z-buffered and composited by depth (3-6 s a candidate); coordinate descent. The objective is the flaps' shape in
every view (IoU, width, hang, attach, sweep, clearance), the gated piece IoUs and extents, the band per view, with the
hem checks held as penalties (no gaming: the piece's IoU in all views is in the objective and the log).

**The three-quarter view disagrees with the others.** Projected, the drawn three-quarter tails sit at about +-100 deg
azimuth (beside the thighs), while the back, front and profile place them at 118-155 deg. A flap fitting the back and
profile hides its three-quarter tails behind the legs (IoU near 0). The fit weights the three-quarter at 0.25.

## Round 1 progress (2026-09-30, later)

- **Merged** pipeline-3d 120d197 (tool/hull-limbs) and cfcdc3a (self-registering QA parts and steps): the skirt part is
  `@qa_part('skirt', order=2200)`; its steps are in `charkit/steps/skirtqa.py`, the leg outline's grading step in
  `charkit/steps/detailqa.py`.
- **More checks** (all with round 6 failing them):
  - `flap_profile_clear_{L,R}` (tool/hull-limbs' hand-off): per row where the drawing shows the flap hanging clear behind
    the leg, how much less clearance ours has. Round 6 0.739 FAIL, hugging on 98% of those rows.
  - `body_profile_leg_outline` graded (was INFO; the coordinator's call): the step outward within 0.05 L (WARN 0.10),
    the hugging rows within 10 of the design's. Calibrated: the design 0 and 3 rows, pipeline-3d's flaps 0.57 L and 82.
  - `skirt_tuck_jut` (3D): the skirt and flaps past the band's outer surface where they come out from under it. Round
    6 0.0805 FAIL at the centre back. A 2D version (the silhouette just under the band) doesn't discriminate: the
    design's skirt flares out right from the band's corner (0.08 L within 0.05 L), round 6's reads less.
  - `skirt_pleats`, `skirt_pleats_cream`, `skirt_pleat_order`: tool/garments2 cda2b7f's measure, moved here (garments2
    dropped it, 74fdc64). Round 6: 19 orange against the design's 14.5 FAIL, 3 cream against 3.
- **The tuck** (`tuck_fit` on the skirt; `tuck_under`, `tuck_pull`): the skirt pulled in to come out half the band's
  thickness inside its lower edge, easing back over 0.25 L; capped inside the band above that edge; the flap template's
  top follows, just over the skirt. At the back the skirt now comes out 0.01-0.02 L inside the band (was 0.04-0.05 out).
- **The skirt's band** swept on the evaluator: two steps of 14 deg beside the panel, base 0.15 L, rise 0.10 L, with 18
  pleats. It reads the design's rise and tread in every view (profile two risers of 0.104 against 0.099) and the step
  count PASSes; its front median height reads 0.245 against 0.155 (FAIL): the front's median sits on the stair's
  columns. Three narrower steps swap that for a WARN on step size and a FAIL on the count. Round 6: 13-16 fine stairs,
  a 0.25 L band.
- **Pleats**: 18 round the skirt gives 15 orange and 3 cream (the design 14.5 and 3); 22 gave 19 and 3.
- **The flap fit** (on the evaluator, round 6's body): back IoU 0.75, profile IoU 0.75, attach, sweep, hang and leg
  clearance PASS, every hem PASS, no row hugging the leg. The irregular stair it found (lengths 0.18, 0.47, 0.55, 0.52)
  is replaced by a regular one (first + rise) and the fit rerun.
- **The leg outline's 0.10 L on the evaluator is the body's thigh, not the flap**: with the flap clear of the leg the
  dressed outline shows our thigh 0.10 L behind the design's at z -2.8, round 6's body (the evaluator ran on
  body6_render's head and body codes). pipeline-3d now carries tool/hull-limbs' thigh fix (the bare leg 0.019 PASS), so
  the codes are rebuilt from the current tree for the final fit.

## The final fit (fresh codes from the current tree)

- **The edges from the drawing.** The flap's outer and inner edges are read off the drawn back-view flap row by row
  and turned into azimuths on our skirt's crest surface (our skirt matches the design's widths): about 129/164 deg a
  quarter of the way down, 129/161 halfway, 126/159 at three quarters, ~123/157 at the hem (scratch `edges.py`). The
  earlier descents had drifted the inner edge to 167 deg (hiding the tails behind the thighs to dodge the hem checks).
- **The stair**: three treads, the first as long as the band is thick (so under the face two risers show, as drawn),
  rising evenly (`tail`: steps 3, first, rise). The irregular stairs the free lengths found are gone.
- **The fit** (scratch `fit.py`, coordinate descent) then moves only the hem knots (+-2 deg), the standoff, the stair's
  first and rise, droop, out, twist and the band's thickness. The objective carries every view's flap IoU, width, hang
  and attach, the profile's sweep and clearance, the leg outline (graded), the gated piece IoUs (the right flap's kept
  over 0.53: round 6's 0.619 WARN must not fall below 0.5) and extents, the flaps' band per view, and the hems as
  penalties from 0.07.

## For other workstreams

- **clawd_mh body_three_quarter_skirt_aline** (0.078 WARN on pipeline-3d, handed to tool/skirt): bodyqa.aline keeps
  the rows within 0.15 L above the middle hem where no hand touches either end of the skirt's run. In the three-quarter
  the MakeHuman hands leave ours 12 such rows and the design none: the design's value falls back to rows where its hand
  joins the run (wider), so the check compares ours against a hand. Read per side (each side's half-width from the axis,
  dropping only a side a hand touches; scratch `aline.py`), the design's free left side reads 0.972 on 17 rows and ours
  0.859 on 28 rows (her right side 0.970): clawd_mh's skirt does narrow toward the hem on that side, -0.113 against
  the design (WARN either way). The default spec reads the same way today (0.088 WARN). Proposal: bodyqa.aline per
  side, as above, registered as a measurement step (charkit/steps/bodyqa.py). Not changed here: bodyqa.py is covered
  by the hull's stamp (an edit rebuilds the hull and the outfit masks), so it wants the integrator's slot.

## Checkpoint (2026-09-30, the usage limit): start here

**Branch** `tool/skirt` in `~/animation-pipeline-skirt`, HEAD 9bea979 (contains pipeline-3d 8a7d4ea: geometry truth,
tool/infra, tool/hull-limbs). No gate run yet. **The specs don't use the new geometry yet**: the template flaps, the
skirt's geometric band, the tuck and 18 pleats are code, fitted on the evaluator, not yet written into clawd.json,
clawd_body_pieces.json and clawd_body.json.

**Done and committed:** the measurement (charkit/skirtqa.py, QA part `skirt`, steps in charkit/steps/skirtqa.py; tests
charkit/tests/test_skirtqa.py: every check passes on the design itself and fails on a round-6-like corruption); the
graded leg outline (detailqa); the pleat checks moved from garments2; the flap template (garments.flap_template,
flap_stair: first + rise, twist), the skirt's band as geometry (band_rows), the tuck (tuck_under, tuck_pull) with
tests (charkit/tests/test_skirt_geometry.py).

**Scratch** (gitignored, this worktree): `charkit/out/skirt_scratch/` holds the harness (`fast.py` the flap evaluator
compositing each candidate into the scene z-buffered once; `fit.py` the coordinate descent and its objective;
`edges.py` the edge azimuths from the drawn back flap; `skband.py` the skirt band sweep; `apply_spec.py` the
span-preserving spec editor; `make_garments.py` the final entries from a knobs file; `closeup.py`, `review.py`,
`tables.py` the review page; `aline.py` the per-side A-line) and the fit states (`fitG_best.json` the best, `t8.json`
its start, `r6qa/skirt.json` round 6's new checks). The harness predates the geometry-truth merge: `fast.py` reads
bodyeval's internals (`E._garments`' hull key, `Part.subdiv`) and may need adjusting; run it from this worktree with
`~/animation-pipeline/.venv/bin/python`, GEOM=charkit/out/skirt_codes/geom (head and body codes from this tree; round
6's codes carry the old thigh bump).

**The best state (fit G, evaluator, fresh codes):** the left flap (the right mirrors it):
`edges` [[0, 130, 166], [0.25, 128.7, 163.8], [0.5, 128.7, 161.2], [0.75, 126.2, 158.8], [1, 127, 157]],
`stand` [[0, 0], [0.5, -0.02], [1, 0.16]], `tail` {steps 3, first 0.18, rise 0.17}, `droop` 0.4, `out` 0.2,
`twist` 0, `band` 0.13, clear 0.02, thick 0.01, bones 6, cols 24, rows 20, tail_rows 12, `hem` band, `shape` template.
The skirt: `pleats` 18, `band` {height 0.15, stair [[0, 0.35], [14, 0.25], [28, 0.15]]}, `tuck_fit` {inset 0.5,
clear 0.005, blend 0.25}. Objective 33.4 (fit C's irregular-stair state 29.8 on round 6's body; round 6 itself far
worse): every hem PASS, the flaps' extents PASS, the leg outline PASS (0.014 on the fresh body), the right flap's piece
IoU held over 0.53.

**Numbers so far** (evaluator; fit F's state, a step before G, on fresh codes: back IoU 0.78 PASS both, front 0.64
WARN, profile 0.55 WARN, three-quarter under 0.1 FAIL; fit C's state on round 6's body: back 0.75, profile 0.75,
attach, sweep, hang and clearance PASS). The flap band at fit G: two main risers of 0.165 against the design's
0.15-0.16, treads 0.09 against 0.10, but the band reads heavy (median 0.32 against 0.19): band 0.13 was the fit's last
move toward it. A box build of fit F's state (`charkit/spec/_skirt_try.json`, untracked; out
`charkit/out/skirt_try`) was running at the checkpoint: its QA is the first Blender check of the template.

**Next steps, in order:**
1. Record the box build's QA (`charkit/out/skirt_try/qa/qa.json`) and check the template in Blender (materials, no
   subdivision, the band) and `python -m charkit evaldrift --stages` on it.
2. Write the best state into the three specs: `python charkit/out/skirt_scratch/make_garments.py
   charkit/out/skirt_scratch/fitG_best.json /tmp/g.json` then `apply_spec.py /tmp/g.json charkit/spec/clawd.json
   charkit/spec/clawd_body_pieces.json charkit/spec/clawd_body.json`; delete `_skirt_try.json`.
3. `python -m charkit flapchains charkit/spec/clawd.json --build charkit/out/skirt_codes` (the flaps' chains into the
   outfit notes; it restamps the outfit masks).
4. The test suite, then the gates: `python -m charkit remote gate tool/skirt --into pipeline-3d` and with
   `--spec charkit/spec/clawd_mh.json` (clawd_mh keeps its own skirt and panels: only the new checks reach it). Don't
   use --accept; report regressions.
5. A render-box build with boards for the review (`remote --box render build charkit/spec/clawd.json --boards body`),
   then `review.py OUT charkit/out/.. (round 6: ~/animation-pipeline-body/charkit/out/body6_render) NEW` and
   `tables.py` for the before/after tables.
6. Open: the flap band's median height (make the band thinner or the treads wider: `widths`); the three-quarter view
   (the design's tails there disagree with its back, front and profile); the skirt band's front median height
   (0.245 against 0.155); clawd_mh's three-quarter A-line (below).

## Paused (2026-09-30, the usage limit), resumed after db718ae

No box jobs were running. Scratch harness (design masks, zooms with an L grid, line fills) is in the session scratchpad
`sk/`, not tracked.
