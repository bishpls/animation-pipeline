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

The authored head and body with the hair as pieces (`clawd_body_pieces`: `clawd_body.json` with `hair.mode` pieces),
built on the render box at 712e736. It is set against the checkpoint Michael reviewed (`ckpt_full`, 35525d1), whose face
and neck measure the same as tool/body's (hollow 0.054, crease 42.6). `face_region` is measured by
`python -m charkit.faceregion` on both.

| check | checkpoint | now |
|---|---|---|
| eye_hollow (L) | 0.054 FAIL | 0.016 PASS |
| cheek_lead (L) | 0.076 FAIL | 0.005 PASS |
| eye_bowl (L) | 0.041 FAIL (under the eye: the socket) | 0.023 WARN (at the nose bridge, the design's profile) |
| eye_width_three_quarter (x design) | 1.236 WARN | 1.083 PASS |
| eye_width_profile (x design) | 1.778 FAIL | 0.889 PASS |
| neck_crease, visible skin (deg) | 41.1 FAIL | 29.6 WARN |
| neck_crease_all, whole skin (deg) | 42.6 | 42.7 (INFO: the flare under the collar) |
| profile_edge, chin to chest (rms L) | 0.052 WARN | 0.052 WARN (worst row: the chin, the two sheets 0.02 L apart) |
| eye_* (the eye engine's checks) | all PASS | all PASS |
| sheet_* (the head against the head sheet) | cheek 0.020 WARN, rest PASS | cheek 0.023 WARN, rest PASS |
| face_folds | 4 | 4 |

Two gate regressions are the hull's, reached through the head: `hair_fringe_low` 0.014 PASS → 0.033 WARN and
`body_back_leg` 0.066 PASS → 0.108 WARN.
- The hull carves away what stands in front of the authored face wherever a view draws skin or iris
  (`hull.carve_face`, which calls `code_base.head_sections`).
- The window sets the eye region back to the design's depth, so the fringe lock over her left eye, which hung partly
  inside the old surface, now stands in front of an eye the side views draw clear, and is carved.
- The legs, fitted to the same hull, shift with it.

The fix is the hull's (keep hair within a margin of the face) or the hair's (pieces keep their drawn length). A cap on
how far the window may bring the face forward (`face.forward` 0) was tried and doesn't change it.

## What's left

- The collar. The body workstream's collar is raised to the torso's top ring, now the slender neck's width, and
  wraps it like a turtleneck. The garments should lay it on the flare below.
- The fringe and hull carve interaction above: the hair and hull owners.
- `eye_bowl`'s remaining WARN is the nose bridge's vertical concavity, at the grid's inner edge. It is the design's own
  profile.
- `poke_share` 0.020 (FAIL) is at the wrists, from the body code.
- Hull building isn't deterministic across box copies. The fork-point baseline, built fresh in its own copy, failed in
  `garments.sleeve_hull` ("no row of the piece is measured on 15% of its circle").
