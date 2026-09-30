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

## The chin's taper (2026-09-30): a V, not a U

Michael, on jaw_4: a "BIG improvement on the neck and jaw", but the chin's taper is shaped wrong. In front the design's
jaw lines run nearly straight from the cheekbones to a sharp V chin with a dark wedge under it; ours stays wide too far
down, then rounds into a broad, blunt, shallow chin (a U). In three-quarter (bare) a hollow under the cheek along the jaw
line, and a notch where the jaw meets the neck behind the chin. jaw_taper and chin_point_z compare widths row by row and
the chin's height, so the shape didn't show.

**The eye anchor first (measurement only, e9a6753).** The QA registered ours on the iris plates' vertex mean, 0.0235 L
over the head's eye line (the design's eye row, which the head is built on; the visible iris centroid is 0.018 L over
it). `faceregion.eye_anchor` and `qa3d.eye_anchor` set the eyes' point on the head's eye line (x, y kept) for the jaw
checks, `profile_edge` and the sheet's face measures (`qa3d.sheet_measure`). Registered in `history.STEPS` (sheet_*,
profile_edge, jaw_*, chin_*, neck_to_face, neck_front_wiggle). On jaw_4: jaw_taper 0.0271 -> 0.0095, chin_point_z
-0.0224 -> 0, sheet_cheek_chin -0.0277 -> -0.0027, sheet_profile_chin -0.0247 -> 0.0003, sheet_profile 0.0136 -> 0.0053,
profile_edge 0.0622 FAIL -> 0.0278 PASS. Whether the eye itself sits high is open (the design's iris class catches only
its lit lower part, so its blob centroid sits low in the drawn iris).

**The measures (`faceregion.taper_front`, `tq_jaw`, `taper_compare`; in `face_region`).** The outline as a curve,
graded in the boards' camera (what the boards show), each with the level camera's value beside it; the defects (bends,
the notch, the hollow) on the worse of the two:

| check | what | limits |
|---|---|---|
| `jaw_taper_shape` | rms of w(t)/w(0), t 0 at the design's cheekbone row (its widest under -0.05, hair-lock tips bridged: -0.113), 1 at each chin; start: where it falls under 0.9 | 0.025 / 0.04 |
| `jaw_line_bend` | the jaw lines' (t 0.4-0.95) sharpest local bend: the direction by arc length, smoothed 0.006 L, less its smoothing over 0.03 L (deg); per side a line fit's rms and bow | 6 / 10 |
| `chin_angle` | the V's opening between its arms fitted 0.06-0.12 L of arc from the chin point, against the design's (deg); w90 alongside | 10 / 20 |
| `chin_tip` | the share of the V's turn made within 0.02 L of arc of its point (1 a sharp V; a U turns all the way round) | >= 0.7 / 0.55 |
| `tq_cheek_hollow` | the three-quarter's far cheek contour, its deepest point inside its local chord (+-0.05 L of arc) | 0.005 / 0.008 |
| `tq_jaw_notch` | the three-quarter's near jaw line (the face's foot per column from the chin), its largest drop under its own rise | 0.008 / 0.016 |

The design against itself: all PASS (bend 4.4, tip 0.84, hollow 0.0035, notch 0). jaw_4: taper 0.035 WARN, bend 24.4,
chin_angle 107.6 (design 129.7), tip 0.30, hollow 0.0097, notch 0.057, all FAIL. Two of the review's readings don't hold
as numbers: ours is narrower than the design at t 0.9 (w90 0.055 against 0.067), and its arms are straighter (line rms
0.002 against 0.004), not bowed. The level camera's row widths match the design's to 0.006 L from z -0.14 down. Lab:
`tools/face_labs/taper_lab.py` (a build, `--geom` a local assembly, `--design`); tests in `test_jaw.py`.

**What the U is.** Three things, measured:
- the boards' camera sits 6 degrees over the chin and lifts whatever lies further back. Our chin's rim had a flat front
  near its point, then swung back fast (0.12 L between x 0.04 and 0.10), so the arms read 37-40 degrees over the
  horizontal near the chin against the design's 22-27 (the level camera: 26). A camera at the chin's height 1 m out
  reads 127 / 0.73 (angle / tip) against 119 / 0.53 at the eye line: it is the look down, not perspective depth;
- the subdivision rounds the V's point: the outline's bottom sits 0.004 L over the rim's point in the level camera,
  0.008 L in the boards' (steeper arms, the same rounding cuts a flatter bottom);
- past the neck's width the jaw was the sections' side: the front silhouette jumped from the rim (0.13 L behind the
  chin) to the side (0.22 L) where the V crosses the neck's edge, a kink in the boards' camera and, in three-quarter,
  the notch (the near jaw line rose to z -0.308, ran flat, and dropped to -0.340 at the neck).

The design's jaw edge in 3D, triangulated from its front V and its three-quarter jaw line (`headfit.jaw_depth`), recedes
about as fast as it widens (0.9-1.1 L back per L out) up to where the hair covers it (z -0.27).

**The construction (`headgeom.jaw_envelope`; the mesh only: the sections are bit-identical to jaw_4's, so the hull's
face carve, the eyes and the hair read the same).** Per row up to the jaw's angle (-0.215, where the design's edge reaches
the side's depth), the outline made to pass through the design's edge point (x_V, y_J), y_J the design's recession
(`headgeom.jaw_depth`: a quadratic through the chin point, D = 1.14 x - 1.24 x^2 on Clawd) placed at our chin's own depth
over x 0.06-0.16 (`EDGE_REF`):
- brought out radially where the point lies outside the outline (rows -0.33 to -0.30: the rim had sat 0.02-0.05 L too far
  back where the V crosses the neck's edge);
- where it lies inside (the rows near the tip: our chin's flat front), the front held behind a prow from the midline's
  front to it, y as (|x| / x_V)^1.5, a soft max (`EDGE_PROW`, `EDGE_SOFT`); faded in over x_V 0.03-0.07 (`EDGE_TIP`);
- style key `face.jaw_edge` ('design' in DEFAULT: both profiles; None: the rim on the envelope's front as before).

The prow is what moves the checks: without it (the bump alone) the hollow stays 0.0097 and the chin 110 / 0.37.

Tried and dropped (don't retry as they were):
- a straight wedge (EDGE_PROW 1): a ridge down the chin's midline that the cage crumpled; 1.2: hollow 0.0055, chin 110;
- a radial pull-in near the tip: pinched the chin's front into a beak;
- the side carved per row behind the edge (the face's front wedge and the neck's own section): sharp (turn 1.2, round
  0.03 L) it scalloped the jaw's silhouette row by row and left fins where the neck met the jaw; soft (0.8, 0.08) and
  only over the band's top it changed nothing measured (the soft chamfer under the edge stays in view in three-quarter,
  so no line draws there); reaching into the band it fixed the notch (0.0075) but folded the neck's side (12-30 edges
  over 90 degrees);
- the side as UnderJaw's pocket (`EDGE_BAND`, kept, off): the band's top raised per column outside the mouth block
  (`UnderJaw(top=...)`, `phi_end`), so the side's columns would run face, rim, underside, neck as the chin's do. The
  side's columns found no rim: U is parametrised round the neck's axis, and going inward along a side column the angle
  sweeps across a rim that climbs 0.08 L, so the underside steps and the continuity test drops the pocket; the rows then
  twisted along the neck's sides (6-30 edges over 90 degrees), and a small raise (0.02-0.03 L) made the three-quarter's
  jaw line fade out past du 0.2. A piecewise row map (the rim held to the band's top row, `EDGE_PIECEWISE`) twisted them
  more.

**Cage health** (`tools/face_labs`: the fitted cage in the jaw region, z -0.45 to -0.25, and its subdivision): jaw_4 18
folded corners, 0 edges over 90 degrees (max 72.5); now 22 and 2 (93: the concave crease where the jaw's underside
meets the neck's side, x 0.13, z -0.315, where jaw_4's sharpest are too).

**Numbers** (jaw_4: the round Michael reviewed; jaw_5: this construction, render box, `clawd.json`, views and body boards,
built at 816ada9; the new checks measured on jaw_4's bundle with the same code; boards' camera, level in brackets):

| check | design | jaw_4 | jaw_5 |
|---|---|---|---|
| jaw_taper_shape (rms of w(t)/w(0)) | 0 | 0.0353 WARN (0.0192) | 0.0281 WARN (0.0247) |
| jaw_line_bend (deg) | 4.4 | 24.4 FAIL (board 9.9) | 41.2 FAIL (board 13.5): the neck-edge T-junction, below |
| chin_angle (deg) | 129.7 | 107.6 FAIL (121.4) | 119.7 PASS (129.5) |
| chin_tip (share of the V's turn at its point) | 0.843 | 0.301 FAIL (0.448) | 0.59 WARN (0.83) |
| w90 (L) | 0.067 | 0.055 | 0.051 |
| tq_cheek_hollow (L) | 0.0035 | 0.0097 FAIL | 0.005 PASS |
| tq_jaw_notch (L) | 0 | 0.0573 FAIL | 0.0573 FAIL (open, below) |
| jaw_taper / chin_point_z (anchor) | | 0.0271 WARN / -0.0224 WARN | 0.0093 / 0 PASS |
| chin_underside (deg) | 13.7 | 12.8 PASS | 12.5 PASS |
| neck_front_wiggle (deg) | | 6.2 PASS | 6.9 PASS |
| jaw_line_front / three_quarter | | 0.979 / 1.333 PASS | 0.968 / 1.333 PASS |
| face_folds | | 4 (530 on the old check) | 4 PASS |
| sheet_cheek_chin / profile_chin (anchor) | | -0.0277 / -0.0247 WARN | -0.0027 / 0.0003 PASS |
| profile_edge | | 0.0622 FAIL (0.0278 remeasured) | 0.0391 WARN |
| eye_hollow / eye_bowl | | 0.0164 / 0.0228 | 0.0121 PASS / 0.0243 WARN (eyes2's) |

- The level camera's bend is a 0.005 L nick where the neck's silhouette line meets the jaw's (a T-junction in the
  emulated outline; the design's drawn neck lines stop at the jaw line). The outward bump at rows -0.33 to -0.30 sharpens
  it: without it (EDGE_BUMP 0) 25 degrees, but the chin reads 116 and the hollow 0.0053 WARN; kept at 1.
- profile_edge: every row from the chin to the chest reads 0.019 L further back than jaw_4's: the profile's horizontal
  registration is still the iris plate's depth, which eyes2's turned surface moved (sheet_nose_reach and chin_reach
  shift the same way, still PASS). The depth anchor (the head frame's eye depth) needs the build to record it: open.
- The boards' chin angle (119.7 against 129.7) is what the design's own recession gives under the boards' 6-degree
  look down (a camera at the chin's height reads 127); flattening the chin's recession to close it would undo the
  three-quarter.

**Gates** (816ada9 into pipeline-3d 2e3bdd5, build box; 2e3bdd5 is notes only and merged since, 2be295e):
- default (`clawd.json`): FAIL on body_front_skirt_aline (gone), body_front_waist_skin 0 -> 0.0131, hair_folds 9 -> 43,
  piece_collar 0.77 -> 0.736: the same four at the same values as the last round's gate (89b8d1d into 5cb5256), the
  hull's (tool/hull-det, merged in this branch; A/B builds above). face_folds unchanged (4); the face region's checks
  are new to pipeline-3d (jaw_taper_shape 0.0281 WARN, jaw_line_bend 41.2 FAIL, chin_angle 119.7 PASS, chin_tip 0.59
  WARN, tq_cheek_hollow 0.005 PASS, tq_jaw_notch 0.0573 FAIL; chin_underside 12.5, neck_front_wiggle 6.9 PASS); sheet_*
  remeasured, all PASS (sheet_cheek WARN -> PASS); body_back_skirt_width and body_back_iou_skin improved.
- `clawd_mh.json`: FAIL on hair_folds 7 -> 49, body_three_quarter_hair_width 0.956 -> 0.896, body_back_skirt_width
  0.941 -> 0.882, body_three_quarter_skirt_aline 0.043 -> 0.086: the hull's four, as before. The MakeHuman head isn't
  the code head: jaw_envelope doesn't touch it; its face-region checks are new (its own jaw, e.g. chin_underside -5.5).
- Reports: `charkit/out/gate/gate_tool-face_816ada9_into_2e3bdd5.md`, `..._clawd_mh.md`.

**Review page:** `charkit/out/face_review/taper/index.html` (`tools/face_labs/taper_page.py`): design | jaw_4 | jaw_5,
close on the chin in front and three-quarter at 420 px per L with each picture's traced outline (red the design's, blue
ours), the taper curves, the bare views, the checks.

## Checkpoint (2026-09-30, after the taper round): state for the next agent

Branch `tool/face`; nothing pushed. Merged in: pipeline-3d 2e3bdd5, tool/eyes2 97a7480, tool/hull-det. Michael's calls
(2e3bdd5): eye flatness (a) and brow (a), the current defaults: decision 5 is settled.

Open, in order:
1. **The three-quarter notch** (tq_jaw_notch 0.057 FAIL, level camera; the boards' 0.032): the near jaw line rises with
   the design's to du 0.2, then runs flat and hooks down into the neck where the design's keeps rising to the ear. It
   needs the jaw's side as an underside of its own (the band's rows carried round the sides: `EDGE_BAND`, off). Two
   pieces are missing: U round the sides parametrised along the rim (the polar form round the neck's axis steps there),
   and a row map that keeps the rim and the throat on fixed rows across the side's columns. `jaw_health.py` and
   `tools/face_labs/taper_lab.py` measure both; the unrolled chart (the cage's rows by angle and height) showed the
   failure directly.
2. **The neck-edge nick** (jaw_line_bend 41 in the level camera, 13.5 in the boards'): a T-junction in the emulated
   outline where the neck's silhouette meets the jaw's; the outward bump sharpens it (EDGE_BUMP 0: 25, at a cost to the
   chin and the hollow).
3. **The chin in the boards' camera**: chin_tip 0.59 WARN, the arms 30 degrees against the design's 25: the look down
   on the design's own recession. A crease on the V's rim near its point (character.py sets creases for the eye margins
   only; not this workstream's file) would keep its point through the subdivision.
4. **The profile's depth registration**: profile_edge, sheet_nose_reach and chin_reach read ours by the iris plate's
   depth, which eyes2's turned surface moved 0.019 L; registering on the head frame's eye depth needs the build to record
   it (the assembly carries eye_z, not the eye plane's y).
5. The hull's regressions (hair_folds, the hull-built skirt, collar and waist): tool/hull-det's, gated alone to confirm.
6. `qa3d.face_folds` (624a516) and `qa3d.eye_anchor` are outside this workstream's files: the integrator should keep or
   re-home them.

## Next round, first task: the design's jaw outline is poisoned by hair (Michael, 2026-09-30)

In the taper page's "front: the lower outline" plot, the design curve (head sheet) has dip-spikes on both sides at
about z −0.15 to −0.18 L round the eyes. There the side locks overlap the face in the drawing, and the tracer follows
the hair's edge, not the face's. Ours are bare renders (hair hidden), so those rows compare hair against no hair. The
rows are at the face's widest point, and the taper checks normalise by it (w(t)/w(0), where the taper starts), so the
whole taper curve and jaw_taper_shape are biased. Fix the measure before any more jaw geometry:
1. Prefer a hairless design reference: check whether head_construction (the skull's authority) draws the bare head at
   the front and three-quarter angles. If it does, use it for the jaw outline checks.
2. Otherwise mask the occlusions: drop any row where the design's face outline pixel touches the hair class (both
   sides of the comparison) and normalise by the widest visible face row. Register it as a remeasure in history.STEPS.
Then re-read jaw_4 and jaw_5 on the corrected measure before touching the three-quarter notch.

## Round 3 (2026-09-30): the hair off the design's jaw, the jaw's side carried round

**1. The design's outline without its hair** (Michael's flag; the measure 1129dd5, its steps now in
`charkit/steps/faceregion.py`). `head_construction` (the bald head) draws front and profile only, and its front chin is
the manifest's outlier (0.034 L lower, more pointed), so it can't stand in for the head sheet. The head sheet's own
outline is masked instead:
- `faceregion._occluded`: going up a side from the chin, the first row whose visible extent falls `OCC_DROP` 0.006 L
  under its running maximum with hair within `OCC_REACH` 0.03 L beyond the edge is a lock's tip; the rows from
  `OCC_MARGIN` 0.008 L under it up are dropped. Hair beside the edge alone marks nothing: the sheet's jaw is drawn over
  its hanging locks down to z -0.3 (a literal "touches hair" mask dropped nearly every row).
- The front: the visible top is z -0.179 (the side locks' tips at -0.14 to -0.17 on both sides; above them the edge was
  the locks' inner edges). t 0 is now the widest row in view, z0 -0.183 (was -0.113, the hair's edge), w0 0.264 (0.288).
- The half-width scan runs through the region's holes: the mouth's line had cut its rows (z -0.178 to -0.21) to
  0.01-0.08 L, bridged by a running maximum into the flat step at t 0.25-0.42 in both curves.
- The three-quarter's far cheek stops under the lock over it (-0.154): the design's own "hollow" 0.0035 at z -0.146 was
  the lock's tip; the cheek's own is 0.0017 at -0.315.
- `jaw_taper` (rows from -0.1) reads only the design's rows in view (its worst row had been the lock's tip, -0.156).
- Ours is read with the hair hidden (`faceregion.bare`) for the outline's shape, on the design's rows. Ours with and
  without hair read the same today (our locks don't reach the face's edge in front).
- `ARMS` (0.2, 0.95) keeps the jaw lines' window at z -0.215 to -0.354; the arc-length samples are anchored on the
  chin (the chin's measures had moved with where the outline was cut).
- Tests (`test_jaw.py`): a lock over each side and hair behind the jaw, a mouth line across the chin's column, a lock
  over the three-quarter's far cheek.

Remeasured (the boards' camera; level in brackets). With the hair gone from the comparison the taper's gap grew: ours
falls away faster than the design's under its widest row in view. In the level camera ours sits on the design's; the
boards' camera, 6 degrees over the chin, narrows the lower jaw (w at z -0.3: 0.105 board, 0.147 level, 0.14 design).

| check | design | jaw_4 old -> new measure | jaw_5 old -> new measure |
|---|---|---|---|
| jaw_taper_shape | 0 | 0.0353 WARN -> 0.0421 FAIL (0.019) | 0.0281 WARN -> 0.0394 WARN (0.0266) |
| jaw_taper (L) | | 0.0095 -> 0.0061 PASS | 0.0093 -> 0.0058 PASS |
| jaw_line_bend (deg) | 4.4 -> 4.2 | 24.4 FAIL | 41.2 FAIL |
| chin_angle (deg) | 129.7 | 107.6 FAIL | 119.7 PASS -> 119.6 WARN (on the limit) |
| chin_tip | 0.843 -> 0.833 | 0.30 -> 0.317 FAIL | 0.59 -> 0.584 WARN |
| tq_cheek_hollow, the design's (L) | 0.0035 -> 0.0017 | 0.0097 FAIL | 0.005 PASS |

**2. The jaw's side carried round (the notch; headgeom `SIDE`, style `face.jaw_side`, on in DEFAULT; b9f0ab3,
1fb4e24).** The three-quarter's near jaw line rose with the design's to the neck's edge, ran flat at z -0.31, and
hooked down into the neck. Past the neck's width the pocket ended and every side column's rim sat at -0.31 with its
throat at the pocket's cap: a ledge under the mouth block's bottom row (z -0.29, the band's top). EDGE_BAND's try
failed because U's polar form round the neck's axis sweeps across the rim going in along a side column: their rays
start from the sections' own centre there (y 0.245 at z -0.2, 0.1 L in front of the axis), so the pocket dropped out
in columns 62-84 degrees.
- **Per column** (`UnderJaw(side=...)`): each column's underside hangs from its own point of the jaw's edge (the V on the
  envelope, crossed by the column's sheet, up to the jaw's angle at -0.215), rising over how far in from it the point
  lies in plan (the band's centre line moves with height; the column's radius alone put the midline's throat at
  (0.091, -0.304) instead of U's (0.12, -0.325)), capped under the column's top as U was. The rim is where the
  envelope's path first drops under it (the V's own height puts it on the chin's rounded bottom, 0.02 L behind its
  front: TIP_BIAS). The throat is where it meets the neck (its top row continued up). The chin's columns match U's
  rims and throats to a few thousandths of L.
- **The band's top** rises round the sides over the rim (EDGE_BAND's `top()`); behind the jaw it comes back down only
  after the rows have relaxed.
- **The rows.** At the chin the linear map's own breakpoints (the rim on band rows 3-5, the throat 8-12); eased over
  `SIDE_EASE` (0.4-0.7 rad) onto fixed rows round the sides, `SIDE_ROWS` (3, 9): the rim and the throat are edge loops
  along the jaw line there, so no row runs from the face onto the underside between two columns. Fixed rows at the
  chin too crumpled the V's point (chin_angle 108, chin_tip 0.35); (4, 11) left 14 edges over 90 degrees; (4, 10) two
  faces at the jaw's side just past the neck's width turned in and back (x 0.13, z -0.296; face_folds 4 -> 32 on the
  box, those two under every mouth key: jaw_6); (3, 9) none.
- **Behind the jaw's angle** the pocket blends into the envelope over `SIDE_FADE` 0.2 rad, and the rows (the rim's at
  the jaw angle's height there, `SIDE_DROP` 0.05 L under it for the throat's) ease back to level over `SIDE_RELAX`
  1 rad. Dropped over the fade alone (0.1 L in two columns) they folded (a dihedral of 175 degrees).
- **The old U at the chin** (`SIDE_UOLD`, off): U's own heights (the polar form, without its neck-width sink) at the
  chin's columns, eased to the per-column form over (0.45, 0.7) rad. Lab (rows (3, 9)): chin_angle 116.4 -> 119.8,
  chin_tip 0.612 -> 0.671, jaw_taper_shape 0.0385 -> 0.0371, but a small nick where the V crosses the neck's edge
  (jaw_line_bend 4.6 -> 7.9, at z -0.316). It is the no-drop option for the gate's 2x2 (below).
- Test: the side pocket on the synthetic head (`test_side_pocket_follows_the_jaw_round_its_sides`).
- Labs: `tools/face_labs/jaw_health.py` counts the sharp edges by region; the per-column meridians, the plan view and
  the sharp-edge chart were scratch scripts (the chart of dihedrals by angle round the head and height is worth keeping
  if the jaw's cage is worked again).

**Numbers** (render box, `clawd.json`, views and body boards). jaw_5: the head pipeline-3d carries (816ada9); jaw_6:
b9f0ab3 (rows (4, 10)); jaw_7: 1fb4e24 with pipeline-3d 301b661 merged (rows (3, 9), the final geometry). The jaw's
checks under the new measure:

| check | jaw_5 | jaw_6 | jaw_7 |
|---|---|---|---|
| tq_jaw_notch (L) | 0.0573 FAIL | 0 PASS | 0 PASS |
| jaw_line_bend (deg; the neck-edge nick) | 41.2 FAIL | 4.9 PASS | 4.6 PASS |
| jaw_taper_shape | 0.0394 WARN | 0.039 WARN | 0.0388 WARN |
| jaw_taper (L) | 0.0058 PASS | 0.0056 PASS | 0.0055 PASS |
| chin_angle (deg; design 129.7) | 119.6 WARN | 116.4 WARN | 116.7 WARN |
| chin_tip | 0.584 WARN | 0.554 WARN | 0.557 WARN |
| tq_cheek_hollow (L) | 0.005 PASS | 0.005 PASS | 0.005 PASS |
| jaw_line_front / three_quarter | 0.968 / 1.333 | 0.937 / 1.12 | 0.937 / 1.106 PASS |
| chin_underside (deg; design 13.7) | 12.5 | 12.8 | 12.8 PASS |
| face_folds | 4 | 32 PASS | 4 PASS |
| neck_crease (visible skin, deg) | 24.2 WARN | 24.3 WARN | 27.6 WARN |
| profile_edge (rms L) | 0.0391 WARN | 0.0349 WARN | 0.0356 WARN |
| body_profile_iou_skin | 0.688 WARN | 0.696 WARN | 0.713 PASS |
| piece_collar | 0.736 WARN | 0.74 WARN | 0.754 PASS |

jaw_7 carries pipeline-3d's hair round 3 and hull-limbs, which jaw_5 and jaw_6 don't: body_profile_iou_skin,
piece_collar and neck_crease between jaw_6 and jaw_7 are theirs as much as the head's (the gate against pipeline-3d
separates them).

**The gate's 2x2** (the old measure, pipeline-3d's faceregion, on each geometry; the gate measures the same):

| check | old measure, jaw_5 | old measure, jaw_7 | new measure, jaw_5 | new measure, jaw_7 |
|---|---|---|---|---|
| jaw_taper_shape | 0.0281 WARN | 0.0291 WARN | 0.0394 WARN | 0.0388 WARN |
| jaw_taper | 0.0093 PASS | 0.0092 PASS | 0.0058 PASS | 0.0055 PASS |
| jaw_line_bend | 41.2 FAIL | 4.6 PASS | 41.2 FAIL | 4.6 PASS |
| chin_angle | 119.7 PASS | 116.7 WARN | 119.6 WARN | 116.7 WARN |
| chin_tip | 0.59 WARN | 0.56 WARN | 0.584 WARN | 0.557 WARN |
| tq_cheek_hollow | 0.005 PASS | 0.005 PASS | 0.005 PASS | 0.005 PASS |

The geometry costs chin_angle 3 degrees and chin_tip 0.03 under both measures, and jaw_taper_shape 0.001 under the
old: the gate fails on them unless they're accepted. **The coordinator accepted the three (2026-09-30)**: the notch
and the neck-edge bend are the flags Michael raised, and the alternative trades them for a neck nick he already
flagged once. chin_angle's design value is 129.7 degrees (PASS within 10: at least 119.7; WARN within 20: at least
109.7); 116.7 is 13 short in the boards' camera, 126 in the level one.

**The fallback: `SIDE_UOLD` (0.45, 0.7)** (headgeom; off). No drop under either measure (chin_angle 119.8, chin_tip
0.671, jaw_taper_shape 0.0371 in the lab), at a nick of 7.9 degrees (WARN) where the V crosses the neck's edge instead
of 4.6. Turn it on if the chin's V matters more than that nick.

**Gates** (9a85cf5 into pipeline-3d cfcdc3a, build box; the commits after it are notes only):
- default (`clawd.json`): FAIL on one line, the 2x2's chin_angle under the old measure (119.7 PASS -> 116.7 WARN),
  accepted by the coordinator. chin_tip (0.59 -> 0.557) and jaw_taper_shape (0.0281 -> 0.0291 old, 0.0388 new) moved
  within their grades (value). Improved: tq_jaw_notch 0.0573 FAIL -> 0 PASS, jaw_line_bend 41.2 FAIL -> 4.6 PASS.
  Values within grade: jaw_line_three_quarter 1.333 -> 1.106, jaw_line_front 0.968 -> 0.937, chin_v 1.084 -> 1.127,
  chin_underside 12.5 -> 12.8, sheet_width 1.01 -> 0.987, the face's shadow and noise INFO. The side locks and the
  collar moved slightly (the hair's trim and the collar read the new jaw), with no check moved by them.
  body_profile_iou_skin, piece_collar and neck_crease are unchanged against the base: jaw_7's 0.713, 0.754 and 27.6
  are pipeline-3d's (hair round 3, hull-limbs).
- `clawd_mh.json`: PASS; the MakeHuman head's jaw checks only remeasured, the same under both measures.
- Reports: `charkit/out/gate/gate_tool-face_9a85cf5_into_cfcdc3a.md`, `..._clawd_mh.md`.

**3. The evaluator's eye line** (evaldrift; 9a85cf5). `bodymeasure.sheet_face` registered ours on the iris plates'
mean; it now sets them level with the head's eye line (`bodyeval`'s landmarks carry `eye_z`), as `qa3d.eye_anchor`
does since e9a6753. On jaw_7's spec, sheet_cheek_chin, sheet_profile_chin and sheet_neck_to_jaw now match the box
exactly (they were 0.025 L low). sheet_width still drifts +0.023 (the report's +0.026): another cause, open.

**4. body_profile_iou_skin** (`skin_profile` diff by height, jaw_5): the face band loses most (3096 design-only px:
the hair over our face in profile), then the waist and hands (4685 / 2939). The chin and jaw band: 653 ours-only, 386
design-only. The body QA (`qa3d.sheet_body`) registers ours on the iris plates' mean, not the eye anchor: our chin
draws 5 px (0.0235 L) low there. Shifting ours 5 px up lifts the head band's skin IoU 0.507 -> 0.544 but the whole
view's falls 0.688 -> 0.663 (the legs and arms prefer ours 4 px forward: 0.718). On the box it reads 0.713 PASS at
jaw_7.

**Review page:** `charkit/out/face_review/round3/index.html` (`tools/face_labs/jaw3_page.py`): design | jaw_5 (the
pipeline-3d head) | jaw_7, close on the chin and jaw in front, three-quarter and profile at 420 px per L, the corrected
traces overlaid (the design's red, with a dashed line where its hair's rows start; ours blue, traced with the hair
hidden), the curves, the jaw's shading before and after (jaw_health), and the checks.

**Gotchas from this round:**
- The scratchpad is shared with the other agents of the session: a log named `gate_default.log` was overwritten by
  another workstream's gate. Use a subfolder of your own.
- `remote gate` runs in parallel on the box now; stopping the local process leaves the gate running there (kill it by
  its gate id's PIDs, then remove `/srv/work/gates/<gid>*`).
- zsh doesn't split an unquoted `$v`: a loop over variant strings needs `${=v}`.
- A lab's `KEY=VALUE` override is set on the module at run time; the build's caches are keyed by code, so overrides only
  reach the local assembly (`jaw_lab.local`), never a box build.

**Open, in order:**
1. (Settled: the 2x2's three drops accepted; `SIDE_UOLD` the fallback.)
2. The chin in the boards' camera: chin_tip 0.557, chin_angle 116.7 (the design 0.83 / 129.7; level camera 0.95 /
   126). The look down on the design's recession, and the subdivision rounding the V's point across columns 0.033 L
   apart; a crease on the V's rim near its point (character.py, not this workstream's) or denser columns at the chin.
3. jaw_taper_shape 0.0388 WARN: the boards' camera narrows the lower jaw (level 0.0165).
4. neck_crease 27.6 WARN at jaw_7 (24.3 at jaw_6): the gate will say whether the head or the merged collar moved it.
5. The side pocket's fade behind the jaw's angle curls up to the band's top (under the ear, behind the side locks):
   a ramus going up to the ear would be the design's.
6. sheet_width's evaluator drift (+0.023); the body QA's registration (`qa3d.sheet_body` on the iris mean).

## Round 4 (2026-09-30, overnight): the chin in the design's projection, the crown, the ramus

Branch `tool/face4` from pipeline-3d a3073f5. Labs on jaw_7's head code (`charkit/out/jaw_7/geom`), the local assembly
(the skin subdivided once, as the QA's eval mesh; the lab now creases the eye margins and the jaw's crease as the
modifier does).

**1. The crown's inward triangles (hair4's false hair_penetration; fixed).** Not duplicates: `code_base.fit_limit` (the
cage moved so its level-1 surface passes through the placed points) turned 60 of the crown's quads over (120
triangles; x +-0.064, z 0.630-0.641 L), dragging the dome's top rows up to 0.043 L along the surface. It fits all three
coordinates, so it tries to reproduce where along the surface each vertex was placed, which the crown's cap (a Coons
grid, three-valent corners) can't; the placed cage has none turned. The same fit folds 60 on a plain ellipsoid
(`test_the_limit_fit_keeps_the_crown_facing_out`, the known-bad case). Now the dome's vertices (groups skull and
crown) move only along the placed surface's normal (`code_base.SKULL_NORMAL`): 0 turned over, the fit's largest move
there 0.043 -> 0.007 L, the level-1 surface within 0.0013 L of the placed points (0.0001 before), the skin's top
0.6406 (unchanged). hair_penetration on the default spec should read the hair's true clearance (+0.013 L) after a build.

**2. The chin: what the measure can resolve.** The jaw checks read ours off a picture at the head sheet's scale (401 px
per L: a pixel is 0.0025 L). chin_angle fits each arm over 0.06 L of arc (24 px): a pixel at one end of an arm is 2.4
degrees. `tools/face_labs/chin_lab.py` reads the same measures on ours drawn K times finer (K=4) beside the sheet's
scale, and prints each chin column's rim against its target. jaw_7 at the sheet's scale / 4x: level 126.1 / 126.3,
boards' 116.4 / 116.1 (the design 129.7).
