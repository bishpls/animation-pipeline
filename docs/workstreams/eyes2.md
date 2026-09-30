# Workstream: the eyes, round 2 (`tool/eyes2`)

Forked from tool/face (36919f4, the eye window) with pipeline-3d merged (054b71d). Michael, on tool/face's review:
1. In profile our eye doesn't read as looking forward. The design's profile eye has a near-vertical front edge with
   the iris against it (a narrow, foreshortened ellipse), sclera only behind it, and the upper lash line sweeping back
   with a flick. Ours is a symmetric almond, the iris centred, a sliver of white in front of it.
2. "Pupil-sclera ratios are also still off, a little too slit-eyed."

## Measurement (charkit/eyeqa.py: measure_view, views; the QA part `eye_views`)

Every eye the head sheet draws (front both, three-quarter both, profile), ours rendered from the same azimuth at the
sheet's scale (`qa3d.eye_image`), both measured the same way. `nasal` is the picture direction of the nose from the
eye (front L, three-quarter L and profile: the picture's left).

- **Gaze placement:** `front_gap` (the sclera between the iris's nasal edge and the opening's, the median over the
  visible iris's middle 60% of rows, in opening widths), `gaze_off` (the visible iris's centroid across the opening,
  + toward the nose), `behind` (the sclera's share on the far side of the iris).
- **Pupil:** a coverage map, not a threshold: each pixel near the pupil's mask placed, by value, between the iris
  round it on its row (a ring 2-6 px out, highlights excluded) and the pupil's core. A 6 px pupil's width reads to a
  tenth of a pixel. From it: the height (rows whose coverage sums to half a pixel, ends interpolated); the width at
  25/50/75% of the height over the iris's width on the same rows (`pupil_w25/50/75`; `pupil_taper` is the quarters'
  mean over the middle's: an ellipse's is 0.87, a slit's near 1, a lens's lower); the area over the visible iris's
  (`pupil_area`); the second-moment ellipse (`pupil_axis` minor/major, `pupil_tilt`, `pupil_fill` area over the
  moment ellipse's: 1 for an ellipse); the centroid in the iris (`pupil_cx` + nasal, `pupil_cy` + up); the width at
  50% over the opening's (`pupil_open`).
- **Profile opening:** the nasal edge over the middle 80% of the opening's height, fitted with a line: `edge_angle`
  (degrees from vertical, + the top toward the nose) and `edge_rms` (rms off the line, in opening heights); the upper
  lash line's far tip against the far corner (`flick_out`, `flick_up`, `flick_angle`); `aspect` as before.

Graded (`eye_view_<view>_<measure>`, the worse eye per check; limits in `eyeqa.VIEW_LIMITS`):
- front: front_gap, gaze_off, pupil_w50, pupil_taper, pupil_area, pupil_axis, pupil_h, pupil_open, pupil_cy;
- three-quarter: front_gap, gaze_off, behind;
- profile: front_gap, gaze_off, behind, edge_angle, edge_rms, flick_out.

Sanity (`charkit/tests/test_eyeqa.py`): known answers on drawn, anti-aliased eyes (an ellipse pupil's widths and
taper, a slit against a round pupil, an iris against the nasal edge against a centred one, a flat front edge against
an almond's corner), and the head sheet's eyes against themselves resampled at 0.8x and 1.25x and shifted: every
per-view check passes.

## Why a plate can't look forward in profile, and why a sphere at the gaze can't either

The eye window (tool/face) lays the opening on a plane yawed 26.9° back toward the outer corner, so the inner corner
is the opening's most forward point. From the side, every part of a plate in that plane shows: the white nasal of the
iris comes first. That's the sliver in front (profile `front_gap` 0.188, `behind` 0.00: all the white in front).

The obvious fix, an eyeball behind the lids with the iris on its front, facing the gaze, doesn't work:
- From the side, a convex eyeball shows only its half on the camera's side of its apex. The apex is the iris's
  centre when the iris faces the gaze, so only the iris's back half shows, as a sliver. With the front view's iris
  ratio (0.6) on a sphere that fills the opening, the profile's iris is about 0.013 L wide; the design's is 0.040.
- More generally, for any convex surface with the iris centred on a forward gaze, the profile's iris is at most
  (θ_iris / θ_opening)^2 of the profile's opening, 0.36 in the limit of a flat eye. The design draws 0.44.
- With the lids on the window's plane, the opening nasal of the eyeball's apex shows the pocket in profile: a dark
  wedge about 0.2 eye widths across.

The design's own numbers describe a different eye. Its profile iris is a whole, narrow ellipse with its nasal edge on
the opening's front edge, and all the white behind it. Per view:

| | front | three-quarter near | three-quarter far | profile |
|---|---|---|---|---|
| front_gap (the nasal white) | 0.09 | 0.069 | 0.158 | 0.000 |

That is what a surface does if it faces the front nasal of the iris (the white there is edge-on to a side view) and
turns outward from the iris's nasal edge. Take the part past the fold at the window's 27°: the near eye's
three-quarter (35.5°) then predicts 0.09 × cos 35.5° / (0.09 × cos 35.5° + 0.91 × cos 8.5° / cos 27°) = 0.068 (the
design: 0.069). The far eye's predicts 0.134 (0.158). From the widths, the iris region is turned about 21° (its
profile width over its front width is 0.38 = tan 21°) and the white behind it about 45°.

## The fix: the eye's surface turned round a fold (charkit/eyes.py: Surface)

`surface: 'turned'` (the anime style's `eyes` section) makes a depth field over the eye, a function of eye-local
(x, z):
- **The fold.** On each row it follows the iris's nasal outline (the iris's knobs: half-width, half-height, centre,
  convergence), so no white shows in front of the iris at the top and bottom rows either.
- **Nasal of the fold,** the surface faces the front, turned 10° toward the nose (`turn[0]`).
- **Past the fold,** it turns outward, from 5° just past it to 50° at the outer corner (`turn[1:]`). From the design's
  widths, its iris region is turned about 21° and the white behind it about 45°; this ramp puts the profile's iris at
  0.44 of its opening, as drawn, in principle.
- **Its depth.** Each row's fold sits halfway between one depth for all rows and the window's depth on that row
  (`fold_follow` 0.5). The whole is set against the face so the opening's two corners stay on it (`anchor`
  'corners': the middle comes up to 0.03 L forward).

Everything of the eye takes the field at its own (x, z): the sclera and iris plates, the lid margin, the rings
between the margin and the eye block's rim (fading to nothing at `fold_reach` 0.035 L outside the opening, so the rim
stays put), the pocket, and the crease line. The front view is therefore unchanged: every vertex keeps its x and z,
and the plates keep their UVs (test_eye_surface.test_front_view_unchanged).

Lashes are rigid across their width: both edges take the lid line's depth, so a lash stands off its lid instead of
twisting into the skin that fades behind it. The flick goes on from the corner at its own angle (`flick_turn` 40°),
not along the face's steep turn behind the corner: profile `flick_out` 0.545 (the design's 0.556; the plate's 0.75).
Carried on the corner's own slope, it swept too far back once the corner turned 50° (0.70-0.81).

The iris converges 0.09 eye widths toward the nose (the style's `converge`, used only with a turned surface: on a
plate the far eye in three-quarter loses its nasal white). The head sheet converges its irises 0.087 of the opening in
front.

Tried and dropped:
- **anchor 'min'** (the surface never in front of the plate's depth). The corners go 0.03-0.05 L behind the face:
  eye_hollow 0.029-0.046 (was 0.016), and the notch hides the far eye's nasal white in three-quarter (front_gap 0).
- **A straight fold** (one x for every row). White shows in front of the iris at the top rows, where the iris narrows.
- **fold_follow 0** (every fold at one depth). The front edge is upright (edge_rms 0.006 against the design's 0.021),
  but the upper lid comes up to 0.01 L further forward. fold_follow 1 (each fold at the window's depth) widens the
  profile's iris (gaze_off 0.181 against 0.258, WARN).
- **turn (-5, 10, 45)** with fold_follow 1, the first working setting. Two per-view WARNs: the far eye's
  three-quarter white (0.092) and the profile's iris too wide (gaze_off 0.181).
- **converge 0.06-0.07.** Widens the far eye's three-quarter white (0.125-0.15, PASS), but moves the front's gaze and
  the far eye's iris and white out of their bands (3-4 non-PASS).
- **Lashes following the field at both edges.** The ribbon twists where the field fades outside the opening. In
  profile the upper lash broke into pieces.
- **fold_at +0.03 / +0.05** (the fold outward of the iris's edge, hiding a sliver of it in profile). No setting
  cleared the far eye's white: 0.075-0.105 in every combination scanned (18).

Blender's Python has no scipy: the Surface is numpy only (a test checks).

## The pupil

"A little too slit-eyed" measured: against the head sheet's front eyes, our pupil was 0.67 of the design's width
(w50 0.099 of the iris against 0.146), 0.70 of its height, 0.50 of its area. Its shape was right: axis ratio 0.28
against 0.26, taper 0.89 against 0.83-0.88. So the pupil was the right ellipse, too small, and sitting low in what
shows of the iris (`pupil_cy` -0.25 against +0.03: the lids clip a tall iris, and the pupil sat at the whole iris's
centre).

Fix (the authored-head specs' iris): `pupil_rx` 0.03 → 0.0435 and `pupil_rz` 0.122 → 0.185 (x1.45, x1.52), and a new
eyetex knob `pupil_cz` (default -0.01 as before) at 0.1. Raising the pupil ran it under the shine: the highlight is
drawn over the iris, and it cut the pupil's top (taper 0.60). The design's main highlight also sits further out
(`highlight_at` -0.56 of the iris's half-width against our -0.29), so the shine moved to (-0.16, 0.14), with the
small one clear of the pupil at (0.09, 0.2).

The old pupil checks had hidden this. They read a thresholded bounding box against an iris height that lost the
iris's lid-shadowed top: ours 0.341 against 0.394, a PASS. Read from the coverage map against the whole iris, the
pre-round-2 build is 0.297 against 0.405 (WARN). `measure()` now reads them that way, registered as a measurement step
(`history.STEPS`: `eye_pupil_*`, b9055f7), so the gate calls them remeasured.

## For tool/face (the eye window's owner)

- **What the eye engine now moves.** The eye's Surface is a depth field relative to the window (`F`). It moves the
  lid margin and the eye block's rings within `fold_reach` (0.035 L) of the opening. It also moves the pocket, the
  plates, the lashes and the crease. The block's rim never moves (it sits at least 0.035 L out), so the face outside
  the block is untouched. With `anchor` 'corners' the opening's corners stay on the window; the middle of the eye
  comes up to 0.03 L forward of it, the lids riding over the eye.
- **faceregion reads it.** `eye_hollow` reads the plates (`visible_front`): 0.016 → 0.012. The cheek lead goes
  0.0047 → 0.0076 and `eye_bowl` is unchanged. The eye widths go from 1.083 to 1.014 (three-quarter) and from 0.889
  to 0.917 (profile).
- **The window's nasal half.** The design implies more than the window can hold: seen from the side, the inner corner
  is hidden behind the eye. The eye engine gets that by facing the white nasal of the iris to the front. A window
  whose nasal part turned toward the front (rather than the one 26.9° plane) would do the same with the skin, and the
  eye field there would drop to nearly nothing. Not needed now, but it's the cleaner place for it if the window is
  revisited.
- **Ownership.** face.md lists `charkit/eyes.py` among tool/face's files. This round changed it (Surface, `knobs`,
  place, lid_key, lashes, spokes). The window code (headfit, code_base, faceregion) is untouched.

## Open items

- **The far eye's three-quarter nasal white** reads 0.103 of the opening against the design's 0.158 (WARN). Before
  this round it read 0.135 (PASS), but only because the plate showed white on both sides in every view. No setting
  scanned clears it without moving the front or the far eye's iris out of band. The design's own geometry (the
  frontal white against the turned rest) predicts 0.134. The rest is the sheet's drawing.
- **The MakeHuman base** (`clawd.json`, the default gate spec) has no lid loops, so its eye stays the plate
  (`eyes.knobs`). Its new per-view checks fail as the old authored head's did. Its pupil wasn't retuned: w50 0.138
  (PASS), height 0.048 against 0.067 (WARN), sitting low (WARN).
- **Gaze keys.** look_left/right/up/down still shift the iris plate in (x, z), and it now slides on the turned
  surface. They aren't measured per view (no design reference for them).
- **Export.** The fix is geometry only: vertex positions, the plates' UVs unchanged. VRM/glTF carry it as-is, with no
  shader or view-dependent cost. A realistic style keeps the plate (DEFAULT). A physical eyeball (a sphere at the
  gaze) would be its own surface kind, but the design can't use one (see above).
- **clawd_locks.json** keeps its old pupil knobs (not a gated spec).
