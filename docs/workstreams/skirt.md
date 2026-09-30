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

## Paused (2026-09-30, the usage limit), resumed after db718ae

No box jobs were running. Scratch harness (design masks, zooms with an L grid, line fills) is in the session scratchpad
`sk/`, not tracked.
