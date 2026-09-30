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
