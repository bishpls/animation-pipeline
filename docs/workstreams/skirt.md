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

## For other workstreams

- **clawd_mh body_three_quarter_skirt_aline** (coordinator, from tool/hull-limbs): it reads only 12-13 rows near the hem,
  as the MakeHuman hands block the rest (bodyqa.aline keeps the rows within 0.15 L above the middle hem with no hand
  against the run). Fragile. Proposal: measure each side's half-width from the axis and drop only the side a hand
  blocks. Not changed here: bodyqa.py is covered by the hull's stamp (an edit rebuilds the hull and masks everywhere).

## Paused (2026-09-30, the usage limit), resumed after db718ae

No box jobs were running. Scratch harness (design masks, zooms with an L grid, line fills) is in the session scratchpad
`sk/`, not tracked.
