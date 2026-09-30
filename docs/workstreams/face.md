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

## Checkpoint (2026-09-29): state for the next agent

**Branch `tool/face`** in worktree `~/animation-pipeline-face`. Its HEAD is the commit that adds this section; nothing
is pushed or merged anywhere.
- **Forked from** tool/body 849b9a7.
- **Merged into it:**
  - pipeline-3d, up to 0122617 (tool/look's camera key and screen lines, tool/unshare, the parallel gates);
  - tool/hull-det, 5428033 (`charkit/geom/det.py`: `det.cs`, `det.dot3`; hull.py's projection and labels).
- **Gated:** 712e736 into pipeline-3d 966ad22 (reports in `charkit/out/gate/gate_tool-face_712e736_into_966ad22*.md`).
  - Default spec: FAIL, `hair_fringe_low` 0.0565 → 0.0612.
  - `clawd_body.json`: FAIL, `body_back_leg` 0.066 → 0.108.
  - Both are the hull's face carve (decision 4 below). The merges since then (pipeline-3d 0122617, tool/hull-det) are
    not gated; all 215 tests pass after them.

**Current numbers.** The table under Numbers above: the eye region fixed, the visible crease 29.6 WARN.

**Decisions from the coordinator (2026-09-29):**
1. **Collar: (a).** Keep the slender neck; the collar lies on the flare below it. Routed to tool/body, not ours.
2. **Chin:** the head sheet sets the chin.
3. **Crease:** grade the visible skin's (`neck_crease` on the `masked` skin; `neck_crease_all` INFO).
4. **Fringe and hull carve: (a).** `hull.carve_face` keeps hair within a margin of the face. Implement it in
   `carve_face` only, using tool/hull-det's `det.cs` / `det.dot3`, and keep the change local to `carve_face`. Not
   started. The mechanism is in Numbers above: the window sets the eye region back to the design's depth, so a fringe
   lock hanging close in front of the eye is carved by views that draw the eye clear. Keep hair-labelled voxels within
   a margin in front of the face surface.
5. **Eye flatness and brow: (a)** for both (the design's plane; the brow's slight recess), pending Michael's taste page.
   It needs the option renders: `face.forward` 0 for eye (b), `curve` [2, 2] with reach up 0.2 for brow (b).

**Next task, top priority: the front-view chin and jaw.** The coordinator's brief, verbatim:

> NEW, top priority, from Michael's screenshot of the front close-up: the chin and neck are "still very obviously
> visually glitched".
> - No chin: the face flows straight into a neck as wide as the lower face.
> - No jaw line: the design has a V chin overlapping the neck, with a dark wedge under it.
> - The neck reads as a column.
> None of your checks see the front view's jaw. Add front-view checks, then fix:
> - the face outline per row from the cheek down to the chin point, against the design: taper, the chin point's height
>   and sharpness;
> - the chin's underside visible over the neck in front view: the chin must project forward and down past the neck's
>   front, so the outline draws the jaw line (measure the jaw-line pixels in the front and three-quarter views against
>   the design);
> - the neck's width over the face's width at the jaw, against the design.
> Also check the profile (Michael's side screenshot): the neck's front outline wiggles under the jaw.
> Then re-gate both specs, and report with close-ups beside the design at matching scale.

**Found so far:**
- **The likely cause is the jaw's underside, which slopes the wrong way.** In the head sections
  (`charkit/out/face_b/geom/head_code.npz`), the chin tip's row (z −0.36, front y −0.013 in the eye frame) drops to
  the throat's (−0.38, y 0.198): the underside slopes down toward the throat at about 5°. The board camera (eye height
  +0.06 L, 4 L away) looks down about 5.7°, so the underside is nearly edge-on. It barely turns from the camera, so no
  jaw silhouette and no line. The anime design's underside rises from the chin back to the throat, so the chin's V
  overlaps the neck and the jaw rim is a silhouette. The per-row sections can't make the underside rise: each row is
  one closed section, so a rising underside needs the throat junction above the chin tip, with the rows between
  carrying the chin in front and the neck behind.
- **Where it's built.** `headfit.assemble` builds under the chin from the design's profile skin edge per row
  (`headfit.neck_front`, head_turnaround's profile: the front edge of the skin under the chin, via
  `hull.views_from_heads` and `bodyqa.classes`). That edge is single-valued per row, so it can't encode the underside.
  The neck's width comes from the head sheet's front (`D['front']['neck']`: 0.06 L under the chin), eased in under
  the chin (`wk_all`, `wk_back`: the section's back keeps the neck's width, its front narrows to the chin's V).
  `sheet_neck_to_jaw` PASSes (0.987), but it is graded on the head alone.
- **Reuse for the design side of the front checks.** `hull.views_from_heads(rgb, eye_x, facing)` gives the head
  sheet's views (mask, eye_y, ppl, axis) and `bodyqa.classes(rgb, mask, eye_y, ppl)` the classes (skin, line, ...),
  as `neck_front` does.
  - The design's jaw line is the line-class run crossing the skin below the mouth.
  - Its lowest point is the chin point; the V's slopes there give the sharpness.
  - The skin under it, bounded by lines, is the neck.
- **Ours.** The front view's z-buffer (`faceqa.zbuffer` on `qa3d.scene_classes`, az 0 and the three-quarter). A jaw
  line draws where, going down a column below the mouth, the visible depth jumps back by more than the ink line's
  depth (screen lines `frac` 0.0022 of the frame: about 0.004 L at the board camera; use 0.01 L to be safe).
- **The look's stop-gap.** tool/look added `look.face.jaw_line` (it inks the jaw's edge in the face UV; off in anime),
  noting "from the front it doesn't turn from the camera, so no outline draws it". That is the same geometric fault.
- **Tools.** `tools/face_labs/chin_cmp.py` puts the head sheet's front, three-quarter and profile beside builds' face
  boards at the same px per L. The first comparison is `chin_cmp.py OUT.png ~/animation-pipeline-ckpt/charkit/out/ckpt_full
  charkit/out/face_i`.

**Box jobs.** None in flight. Outputs:
- `charkit/out/jaw_0` (render box, HEAD 91e44ca, `clawd_body.json`, views and body boards, `clawd.blend`) is the
  current look's baseline for the jaw task.
- `charkit/out/face_i` is the last `clawd_body_pieces` build (712e736).
- Candidate gate outputs stay on the build box in `/srv/work/gate-out`; the reports come back to `charkit/out/gate`.

**Files owned:**
- `charkit/geom/headfit.py`, `charkit/geom/headgeom.py`, `charkit/code_base.py` (the head, `wrap`, the join);
- `charkit/eyes.py`;
- `charkit/faceregion.py`, `charkit/tests/test_faceregion.py`;
- the style profiles' `face` section;
- `hull.carve_face`, for decision 4 only;
- `code_body`'s torso top rows (re-seated from `code_base._join_neck`).

Garments and the rest of `code_body` are tool/body's, hair is the hair workstream's, and the look is tool/look's.

**Gotchas:**
- The hull carves in front of this head (`hull.carve_face` → `code_base.head_sections`). Any change to the face
  surface changes the hull, and through it the hair pieces, the legs and the garments. Watch `hair_fringe_low`,
  `body_back_leg` and `poke_share` after head changes.
- Hulls built in different box copies can differ (tool/hull-det works on this). A fresh baseline worktree failed in
  `garments.sleeve_hull`.
- The IAP tunnel can drop mid-command. A dropped `remote build` can leave its Blender running on the box, and a
  retry into the same `--out` then corrupts `trace.jsonl` (and the hair once: `hair_folds` 1405). Retry into a new
  folder. Gates with a dropped tunnel keep running on the box; their reports stay there.
- Local builds on the laptop go through `python -m charkit slots 1`; heavy builds go to the boxes
  (`remote build`, `remote --box render build` for boards).
- The QA's `eval` skin variant is subdivided once (the viewport level), not at the render level; `masked` is the
  skin with the garments' mask on. The neck lab subdivides once to match.
- `faceregion`'s eye widths compare `qa3d.eye_image` renders with the head sheet's crops (`eyepage.design_eyes`), so
  lashes and lids count. The geometric prediction in the eye lab runs about 0.89 of the box's profile measure.
- `hair_fringe_low`'s "ours" is the lowest visible bangs pixel in the front class map, so skin, lashes or a carved
  tip in front of the bangs all move it.


## The chin and jaw (2026-09-29): the jaw's underside in the mesh

Michael: the chin and neck are "still very obviously visually glitched". In front the face ran straight into a neck as
wide as the lower face, with no chin point and no jaw line; in profile the neck's front outline wiggled under the jaw.

**Why.** One closed section per row can't hold a chin that overhangs the neck: between the chin point and the throat a
row crosses the chin, then air, then the neck. The rows stepped from the chin to the neck, the cage's rows (0.03 L
apart) turned the step into an underside sloping *down* toward the throat (5 degrees), nearly edge-on to the boards'
camera (it looks down 6.5 degrees at the chin), so no outline drew the jaw. The limit fit rang on the step: it threw the
chin's cage vertex 0.08 L forward and left a lip and a notch under the jaw, the profile's wiggle.

**The construction: `headgeom.UnderJaw`, the mesh's own.** The sections stay the envelope (each row's outline, the air
under the chin filled): the hull's face carve, the eyes, the hair and the shading read the same sections as before (to
1e-12, cross-machine noise). The solid is the envelope less a pocket under the jaw:
- the underside z = U(x, y): a ruled surface from the rim (the design's jaw line in front, `headfit.jaw_line`: the lower
  face's outline read as a height over x, the V; laid on the envelope's front) toward the neck's axis, rising at the
  design's own underside angle (13.7 degrees, read in the head sheet's profile by the QA's measure), eased round off the
  chin (0.75 of it at the rim to 1.15 of it 0.12 L in: the design's underside runs flat under the chin's round bottom,
  then climbs), capped 0.012 L under the mouth block;
- the pocket: under U, outside the neck (its top row continued up), over the neck's width (fading past it), in front of
  its axis; round the neck's sides the envelope closes on the neck and the pocket with it (gone by 85 degrees);
- the cage's rows from the mouth block down to -0.404 (`JAW_BAND_END`) are laid 0.0075 L apart in the chart and placed
  along each column's meridian by arc length: the envelope down to the rim, the underside back up to the throat, the
  neck down. The columns hang from a centre line straight through the band (the sections' centres jump at the chin's
  step) eased into the rows' own at both ends (else the columns shear there and the normals kink). Under -0.404 to the
  join the rows are on the sections, their spacing growing evenly from the band's to the cage's own. The neck behind
  the chin is its top clean row (0.03 L or more under the chin, no lower than the band's foot) continued up.
- the chin's point is lowered 0.006 L at the tip (`TIP_BIAS`): the subdivision rounds the V's point across the cage's
  columns (0.033 L apart there), which raises it that much (as `headfit.CHIN_BIAS` in profile).
- the cage's winding is made consistent across shared edges (`orient_faces`): the cage's own rule (each quad faces away
  from the axis at its height) turned the underside inward; the underside's vertices are held out of the limit fit
  (fitting pushed the cage out round the rim); the UVs take the chart's height in the band (a vertex's z runs back up
  there: 0 of 1152 faces under the chin reversed).
- style keys (`charkit/styles`, `face`): `jaw_under` (on in DEFAULT: realistic builds it too), `jaw_rise` ('design' or
  degrees), `jaw_rise_range` [8, 25].

Tried and dropped (don't retry): the underside as the lowest of cones from the rim's points (the V's arms rise faster
than the cones, so the rim sagged 0.01 L under the drawn arms); as the rim's height at its nearest point plus the rise
(jumps where two parts of the rim are equally near); in each sagittal slice from the V's height at that x (descends
along the columns at the neck's sides: the pocket ended in a wall at 55 degrees); a band running to the join (the neck's
rows went coarse and the crease rose to 45.7); cage rows anchored on the rim and the throat (the throat's row became a
wiggle, 13.5 degrees); a rise capped at 11 or 9 degrees for face_folds (below: no help).

**The measures: `faceregion.jaw`** (in `face_region`), the design side from the head sheet (`hull.views_from_heads`,
`bodyqa.classes` with the lines kept), ours from the scene (`qa3d.scene_classes`) in two cameras: the boards' own, with
the outline emulated as the look draws it (the skin offset by the line's width, faces flipped, back faces culled), for
whether a jaw line draws; a level one far out, as the design is drawn, for the shape.

| check | what | limits (PASS / WARN) |
|---|---|---|
| `jaw_taper` | the face outline's half-width per row from the cheek (z -0.1) to the design's chin point, rms against the design's (L) | 0.015 / 0.03 |
| `chin_point_z` | the chin point (the face region's lowest pixel near the middle) less the design's (L) | 0.015 / 0.03 |
| `chin_v` | the V's rise 0.08 L either side of the chin point, ours over the design's | 15% / 30% |
| `neck_to_face` | the neck's width 0.1 L under the chin over the face's 0.1 L over it, ours over the design's | 15% / 30% |
| `jaw_line_front`, `jaw_line_three_quarter` | the jaw line's length with neck skin under it (the boards' camera, the outline emulated), ours over the design's | >= 0.7 / >= 0.4 |
| `chin_underside` | the profile's underside angle (deg, + rising to the throat) against the design's | 6 / 12 deg |
| `neck_front_wiggle` | the neck's front outline's sharpest bend 0.1 L under the throat (deg) | 12 / 18 |

Labs: `tools/face_labs/jaw_lab.py` (a build, or `--geom` a local assembly in 30 s: the pictures, face_folds' rest
count and the join's crease), `jaw_page.py` (the review page), `carve_lab.py` (the hull carve's detail, on the build
box). Tests: `charkit/tests/test_jaw.py`.

**Two things the measures showed that are not the jaw's:**
- **The irises sit 0.0235 L above the head frame's eye line** (iris centres z 1.3127 m, eye line 1.3068 m; the eye
  knob `z` is 0). The head is built on the design's eye row; the QA reads every feature from the irises. So below the
  eyes everything reads 0.024 L low: `chin_point_z` -0.022 and the sheet's `sheet_profile_chin` -0.025 /
  `sheet_cheek_chin` -0.028 (WARN) on the build, while the chin is on the design's to 0.001 L in the head frame. The
  old chin's rounded step read about 0.015 L high and hid it (`CHIN_BIAS` was swept on that). The fix is where the eye
  engine puts the iris against the design's eye row (charkit/eyes.py), which moves the whole face region: not done.
- **`qa3d.face_folds` counts the chin's underside** (see the gate section below).

**Carve margin (decision 4a):** `hull.carve_face` keeps hair the front view draws over the face (a hair pixel with
face either side in its row: the fringe) within `HAIR_KEEP` 0.03 L of the face (`CK_HAIR_KEEP` overrides it for A/B
builds). `carve_lab.py` on the build box: every carved voxel is hair in some view, so "hair in any view" would have kept
a layer over the side locks' gap too; the carve never took a lock over the eyes; it took the bangs' inner layer over
the forehead (z 0.1-0.3, 0.006-0.24 L in front of it); the rule keeps 523 voxels. On the current pipeline-3d neither
regression it was for reproduces: `hair_fringe_low` isn't computed on the default spec, and `body_back_leg` PASSes
(0.0518) on jaw_0 without it. An A/B build of the MakeHuman default (margin off) read `hair_folds` 46 against the
gate's candidate 47: the margin moves none of the gate's hair checks.

**Gotchas from this round:**
- **Don't run remote builds in parallel from one worktree when a produced reference is stale.** The hull and the outfit
  masks live per character (`charkit/out/hull/clawd`, `charkit/out/clawd/outfit`), not per spec, and every build in
  the box's copy rebuilds a stale one at once: one read a half-written npz (`BadZipFile`). Build once, then fan out.
- A remote build's sync takes the worktree as it is when that build starts: a chain of builds picks up whatever you
  commit or merge in between.
- The jaw lab's local assembly has no eyes: its reference is the head's eye line, not the irises (see above).

**Numbers.** jaw_0 (the baseline Michael saw: HEAD 91e44ca, `clawd_body.json`) against jaw_4 (this round's final build:
the merged pipeline-3d 5cb5256, `clawd.json` now the authored character; render box, boards). The jaw checks
measured with the final `faceregion` on both (`jaw_page.py`); the rest from each build's QA; face_folds recounted with
the corrected check (below) on both.

| check | jaw_0 | jaw_4 |
|---|---|---|
| jaw_taper (L) | 0.0361 FAIL | 0.0271 WARN (the iris anchor, below) |
| chin_point_z (L) | -0.2169 FAIL (the face ran into the neck to the collar) | -0.0224 WARN (the iris anchor) |
| chin_v | 4.211 FAIL | 1.084 PASS |
| neck_to_face | 0.862 PASS | 0.862 PASS |
| jaw_line_front | 0.032 FAIL | 0.979 PASS |
| jaw_line_three_quarter | 0.147 FAIL | 1.333 PASS |
| chin_underside (deg; design 13.7) | -7.5 FAIL | 12.8 PASS |
| neck_front_wiggle (deg) | 29.8 FAIL | 6.2 PASS |
| eye_hollow_L / cheek_lead_L / eye_bowl_L | 0.0164 / 0.0047 / 0.0228 WARN | the same |
| eye_width_three_quarter / profile | 1.083 / 0.889 PASS | the same |
| neck_crease (visible skin, deg) | 26.4 WARN | 24.2 WARN |
| neck_crease_all (INFO) | 48.1 | 48.1 |
| profile_edge (rms L) | 0.0501 WARN | 0.0622 FAIL (worst row -0.36: the chin's corner, the anchor) |
| face_folds (corrected check) | 4 PASS | 4 PASS (530 on the old check: the underside) |
| sheet_profile_chin / sheet_cheek_chin | -0.0097 / -0.0127 PASS | -0.0247 / -0.0277 WARN (the anchor) |
| hair_fringe_low | (not computed) | 0.0141 PASS |
| hair_folds | (not computed) | 43 FAIL (the gate's hull regression, below) |

**Gates** (on the build box; tool/hull-det 5428033 is in this branch and not in pipeline-3d):
- 13ffa22 into f2d0ea7: default (MakeHuman then) FAIL (hair_folds 7 -> 47, body_three_quarter_hair_width
  0.956 -> 0.896); `clawd_body` FAIL (face_folds, sheet_cheek_chin, sheet_profile_chin, body_front_hair_length).
- dff58bd into 5cb5256: default (`clawd.json`, the authored character) FAIL (face_folds 4 -> 530, hair_folds 9 -> 43,
  sheet_cheek_chin, sheet_profile_chin, piece_collar 0.77 -> 0.737, body_front_waist_skin 0 -> 0.013,
  body_front_skirt_aline gone); `clawd_mh.json` FAIL (hair_folds 7 -> 47, body_three_quarter_hair_width,
  body_back_skirt_width 0.941 -> 0.882, body_three_quarter_skirt_aline 0.043 -> 0.086).
- face_folds: fixed since in `qa3d.face_folds` (624a516, outside this workstream's files, at the coordinator's
  request): faces facing down at rest (normal z < -0.7) no longer count as facing away; a flip still counts. Over the
  13 mouth keys the underside flips no face; all 488 counted were the underside's own. jaw_0 4 -> 4, jaw_4 530 -> 4.
- hair_folds (41 of the 46 in the flyaways piece) and the hull-built garments' moves are the hull's: an A/B build of
  the MakeHuman spec with the carve margin off read hair_folds 46 against the candidate's 47, so the margin isn't it;
  and an A/B with the eye region back to the socket (pipeline-3d's; `CK_EYE_REGION=socket`) read hair_folds 49
  (flyaways 41), three-quarter hair width 0.896, back skirt 0.882, A-line 0.086: the candidate's numbers exactly. So
  neither the margin nor the eye window's carve moves them; what's left between this branch and pipeline-3d on the
  hull is tool/hull-det (its facing view and decimation) and this branch's reconciling of it with refs2's banded views
  (`_facing` masked by `View.band`). hull-det's owner should gate it alone into pipeline-3d to confirm.

**Final gates** (89b8d1d into pipeline-3d 5cb5256, build box; tool/hull-det and tool/eyes2 are merged in this branch):
- default (`clawd.json`): FAIL. Worse: hair_folds 9 -> 43, piece_collar 0.77 -> 0.736, body_front_waist_skin
  0 -> 0.013, body_front_skirt_aline gone (the hull's: above), sheet_cheek_chin and sheet_profile_chin (the iris
  anchor). face_folds no longer regresses. The jaw checks: 6 PASS, jaw_taper 0.0271 and chin_point_z -0.0224 WARN.
- `clawd_mh.json`: FAIL on the hull's four (hair_folds 7 -> 49, three-quarter hair width, back skirt width, the
  three-quarter A-line); face_folds 1318 -> 1218 (the MakeHuman head's own, a value change).
- Review page: `charkit/out/face_review/jaw/index.html` (`jaw_page.py`: jaw_0 against jaw_4). Decision renders for
  Michael's calls: `charkit/out/decisions/face/{eye_flatness/a,b,c, brow/a,b}.png` and `.json`, index `index.json`
  (a: jaw_3; b, c: `dec2_*`, the same code and spec as jaw_3; eye (c) wasn't defined: rendered as the midpoint,
  forward 0.018 L, and reads as a).

## Checkpoint (2026-09-30): state for the next agent

**Branch `tool/face`** at the commit adding this section; nothing pushed. Merged in: pipeline-3d 5cb5256, tool/eyes2
97a7480 (clean). The chin and jaw are done to their checks; the open items, in order:
1. **The iris anchor** (0.0235 L): our irises sit that far above the head frame's eye line; the QA and the sheet
   checks anchor on the iris plate's vertex mean, the design on its eye row. It puts the chin 0.024 L low against the
   eyes: jaw_taper and chin_point_z WARN, sheet_profile_chin / sheet_cheek_chin WARN, profile_edge FAIL (its worst row
   is the chin's corner). tool/eyes2 found part of it (the plate's mean runs 0.012-0.013 L off the visible iris) and
   proposes a visible-iris anchor in qa3d/sheetqa. Settle the anchor first, then whether the head's frame or the eye's
   placement moves (eyes.py is this workstream's).
2. **The hull regressions** (hair_folds, flyaways 41 of them; the three-quarter hair width; the hull-built skirt,
   collar, waist): not the jaw, the carve margin or the eye window (A/B builds above); tool/hull-det, gated alone into
   pipeline-3d, would confirm. This branch's reconciling of hull-det with refs2's bands (`_facing` masked by
   `View.band`) is in 9de3a6d.
3. **qa3d.face_folds** (624a516) is outside this workstream's files: the integrator should keep or re-home it.
4. The look (tool/look2): the jaw line is the skin's outline (warm brown, thin); the design's is near-black and heavier
   toward the point, with a dark wedge under it: the chin now overhangs the neck (0.19-0.23 L at the midline) for a
   cast shadow. The cage's per-vertex part (`Cg.under_part`, 1 the underside) isn't exported as a vertex group yet.
