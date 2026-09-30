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


## The chin and jaw (2026-09-29, in progress: see the next section when it lands)

State before the final build and gates, for a resumer:
- **Measures:** `faceregion.jaw` (a `face_region` part): 8 checks, the design side from the head sheet
  (`hull.views_from_heads` + `bodyqa.classes`, lines kept), ours from the scene in two cameras (the boards' own for
  "does the jaw line draw", the outline emulated as an inverted hull; a level one far out for the shape). Lab:
  `tools/face_labs/jaw_lab.py OUT.png BUILD` or `--geom GEOM_DIR` (a local assembly, 30 s).
- **Construction:** `headgeom.UnderJaw` (the mesh's own: the sections stay the envelope, so the hull, eyes, hair and
  shading read the same sections as before, to 1e-12). The cage's rows from the mouth block down to -0.404 follow each
  column's meridian: the envelope to the rim, the underside back up to the throat, the neck down. Wired through
  `cylinder_cage(jaw=...)`, `code_base.head_mesh` (the underside held out of the limit fit), the UVs (the chart's
  height in the band). The style's `face.jaw_*` keys; the design's rise is read in the head sheet's profile (13.7).
- **Baseline jaw_0 FAILs 7 of 8** (neck_to_face PASSes: the widths were right, the line was missing); the lab's local
  assembly of the new head PASSes all 8, in anime and realistic.
- **Open: `qa3d.face_folds` counts the chin's underside.** Its mouth box reaches 0.38 L under the eyes and counts a skin
  face whose normal leans back more than 0.2 as folded. The underside faces down and back (a V rim that climbs toward
  the ears leans it back 0.2 to 0.3 wherever it is laid), so 20 to 36 faces count at rest and again under every mouth
  key. Not my file; the fix is to leave out faces facing down at rest (normal z < -0.7 and y > 0).
- **Carve margin (decision 4a):** `hull.carve_face` keeps hair the front view draws over the face (a hair pixel with
  face either side in its row: the fringe) within `HAIR_KEEP` 0.03 L of the face. Measured with
  `tools/face_labs/carve_lab.py` on the build box: every carved voxel is hair in some view, so "hair in any view" would
  have kept a layer over the side locks' gap too; the carve never took a lock over the eyes, it took the bangs' inner
  layer over the forehead (z 0.1-0.3, 0.006-0.24 L in front of it).
- **Gotcha (2026-09-29): don't run remote builds in parallel from one worktree when a produced reference is stale.** The
  hull and the outfit masks live per character (`charkit/out/hull/clawd`, `charkit/out/clawd/outfit`), not per spec,
  and every build in the box's copy of the worktree rebuilds a stale one at once: one read a half-written npz
  (`BadZipFile`). Build once (it refreshes them), then fan out.
