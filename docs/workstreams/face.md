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
- **The cheek stays flush, the brow nearly so.** Round the window the face is held behind the plane, allowed forward of
  it by `curve * d^2` at d L out of the window: a shallow bowl, eased (an earlier flat hold ended in a hard edge). The
  pair `curve` [8, 2] holds the brow more loosely than the cheek, and the reach up is 0.12. The brow sits under the
  fringe and keeps a slight recess over the eye (hollow 0.021 L on the head's sections). Set back its full 0.05 L, it
  moved the hull's face carve under the fringe.
- **Built out to the plane (`forward` unset).** Where the design's yaw is flatter than the face round the eye, the plane
  brings the outer corner and the lid above it up to 0.037 L forward. A cap (`forward` 0, the window only carving in)
  was tried to keep the outer eye behind the fringe tip drawn over it. The box read `hair_fringe_low` 0.033 either way
  (the tip goes to the hull's face carve, below), while the eye widths moved from 1.08/0.89 to 1.14/1.11 and
  `sheet_width` crossed into WARN. It is off; the knob stays for other styles.
- **The midline lets go.** Toward the nose the hold releases, from the eye's own column in (`face.release` 0), so the
  nose and muzzle stay the profile's. From half the window in, it left a groove where the held cheek met the muzzle:
  the largest local hollow was 0.024 L, now 0.016.
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

**The neck join is lofted as one surface (`code_base._join_neck`, `neck_curve`).**
- **Before.** The head's last `NECK_BLEND` rows eased flat into the authored torso's top ring, a circle as wide as the
  hull's neck skin (0.21 L at the sides, against the head's 0.12). Below it the torso flared at its own slope, so the
  neck was a stalk ending in a ring. The ring also stood out past the torso's next rows at ±45°.
- **Now.** The head's own neck (the head sheet's, slender) is kept to the cut. Each column is then one monotone cubic
  (Fritsch–Carlson), meeting both the head's slope and the torso's, down to the torso's ring `NECK_BASE` (0.12 L) under
  the cut. The torso's rings in between are re-seated on it. The neck flares into the shoulders under the collar, as
  the body sheet draws it.
- **Tried and dropped:**
  - Easing the torso's top rows into the head's neck section over 0.18 L pulled the chest front back 0.04 L at the
    collar.
  - A cubic starting 0.1 L above the cut made the visible neck a cone.
- **Measured on the visible skin.** The crease is graded on the skin with the garments' mask on. A flare hidden
  under a collar isn't a crease anyone sees. The whole skin's figure is kept as INFO (`neck_crease_all`), for a
  costume without one.

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

## The neck lab

`crease_of` on the local assembly (`character.assemble`), subdivided once with `charkit.subdiv` as the bundle's eval
mesh is. It reads the box build's figure to within 2° (49.2 against 49.3), in seconds. At two subdivision levels it read
38 against 49.

## Numbers

(filled in from the box builds: see below)
