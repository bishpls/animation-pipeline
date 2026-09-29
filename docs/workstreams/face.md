# Workstream: the face region, eye window and neck join (`tool/face`)

Michael, on the authored head and body: "the eye sockets / eyes are forming this strange curved hollow in the face... Do
we need to rethink the architecture of how this section of the head is being modeled, or does the eye tooling need to
essentially 'fill in' the missing face hollow?", and "there are still major issues with the neck and chin."

The answer on the eyes is the architecture. The eye tooling was doing what the head gave it. `headfit.assemble` dug a
Gaussian socket at each eye (`SOCKET`) to take the surface back to the design's eye depth. Its cheek term, fitted to the
three-quarter's far contour, peaked right under the eye and brought the cheek forward. The eye plates, draped on that
surface, wrapped round the bowl. The anime construction is a flat window round each eye with nothing standing proud of
it. That is now a style setting (`charkit/styles`, `face` section): anime builds the window; realistic keeps the socket.

## What changed

**The eye region, as a style.** The anime profile builds the window, the realistic one keeps the socket:
`styles/anime.json` sets `face.eye_region: "window"`; `realistic` inherits `DEFAULT` (`"socket"`).

**The window (`headfit.eye_fill`).** It is the smoothest correction of the face's front (least thin-plate energy),
solved on the head sections' own angle-by-height grid and mirrored across the midline. It is held to four things:
- **The opening lies on a plane.** The eye's opening, plus a margin, lies on a plane through the design's eye depth (the
  eye frame's y = 0), turned back toward the outer corner by the design's own yaw. The yaw is
  `atan(profile eye width / front eye width)`, both measured on the head sheet with eyeqa (`headfit.eye_views`); for
  Clawd, 0.090 / 0.178 gives 26.9 degrees. A plane's opening shows its front width times tan(yaw) in profile, so the eye
  comes out as wide in profile as drawn.
- **The brow and cheek stay behind it.** Round the window they are held behind the plane, allowed forward of it by
  `curve * d^2` at d L out of the window. That is a shallow bowl, eased. An earlier flat hold ended in a hard edge.
- **The midline lets go.** Toward the midline the hold releases, so the nose and muzzle stay the profile's.
- **It vanishes at the edges.** The correction is zero at the midline (the profile silhouette stays the design's), round
  the side of the head, and past the region's reach above and below.

Two earlier forms failed on the shading lab below, and are documented so they aren't retried:
- a plane swapped in over an ellipse and blended: a faceted disc round each eye;
- the eye row's correction carried up and down with a separable weight: box edges and a groove down the nose.

A fill on an (x, z) grid rippled at the jaw, where the rows end.

**The cheek term's shape (`headfit._cheek(s, peak)`).** It met the far cheek's three-quarter contour with a bump
peaking at half the face's half-width, under the eye. The three-quarter silhouette sits near 0.8 of the half-width, so
the fit pushed the cheek under the eye forward about 2.4 times as far as the contour moved. The anime profile puts the
peak at the cheekbone (`cheek_peak` 0.75).

**The neck join is C1 (`code_base.blend_neck(ring_dr=)`).** The head's last `NECK_BLEND` rows eased flat into the
body's neck ring, and the authored torso then flared at its own slope: a slope jump, the crease. Now each column runs
from the head's row at the blend's top to the ring as a monotone cubic (Fritsch-Carlson) meeting both with their own
slopes. The torso's slope is taken from its ring under the top one (`_ring_below`). A first try, easing the torso's top
rows into the head's neck section, narrowed the neck base under the design's and pulled the chest front back 0.04 L at
the collar; it is gone.

**Measurement: `charkit/faceregion.py`, a QA part (`qa3d.PARTS`: `face_region`).** It measures on the assembled,
subdivided figure, where the head's own sheet checks, graded on the head alone, can't see:

| check | what |
|---|---|
| `eye_hollow_<side>` | how far the eye sits behind the brow-to-cheek chord down its column (L) |
| `cheek_lead_<side>` | how far the cheek under the eye stands in front of it (L) |
| `eye_bowl_<side>` | the deepest local hollow round the eye, against neighbours 0.06 L across or down (L) |
| `eye_width_three_quarter`, `eye_width_profile` | the opening's width against the head sheet's, eyepage's crops at the QA's scale |
| `profile_edge` | the profile's front edge, chin to chest, against the body sheet, row by row (rms L; the worst row) |
| `neck_crease` | the sharpest bend of the neck's outline down any column at the join, less its 0.03 L smoothing (deg) |

`python -m charkit.faceregion BUILD` prints them. `charkit/tests/test_faceregion.py` covers the fill, the crease
measure and the C1 blend, with known answers.

**The head's code step keys on the style's settings.** `cli.code_head`'s cache key carries the profile's `face`
section, not just its name.

## The shading lab

A numpy z-buffer of the head sections (`faceqa.zbuffer`), lit by the boards' key light, two-tone toon and Lambert, in
seconds per try. It is how the window's form was chosen: the numbers alone (hollow, cheek lead) passed forms that shaded
as discs and boxes. The build shades the face's front with the SDF threshold map (`charkit/faceshade.py`), not its
normals, so the lab's toon overstates what geometry does there. It still shows the rim light and the sides, and it
shows where a surface has an edge.

## Numbers

(filled in from the box builds: see below)
