# Hair strokes and tones (tool/hairstrokes)

Worktree `~/animation-pipeline-hairstrokes`, branch `tool/hairstrokes` from pipeline-3d 3168961. Rules:
`~/.claude/agents/charkit-worker.md` (policy K, the guard, the tools: `charkit sweep`, declared checks + `calibrate
--declared`, `charkit review page`, docs/CODEMAP.md). Harness scripts and outputs: `charkit/out/hairstrokes/`.

## Brief (Michael, 2026-10-01, via the coordinator)
Hair lacks "detail in the bulk of the mass": in anime hair that detail is mostly ink strokes inside the locks (strand
lines, partial separations), not 3D relief. Do for hair what garments4 did for the skirt's creases (traced from the
design, drawn as a line layer, scored by declared calibrated checks). The geometry track (tool/hairshell3, the lock
shells over the whole head) owns the shells' geometry; this track owns the strokes and the tones on top, on both the
hull shell and the lock shells. Don't touch shell geometry, garments, face, hands.

1. Measure first: trace the design's interior hair strokes per view (ink inside the hair silhouette that isn't a lock
   boundary the splitter uses); declared, calibrated checks per view for presence, position, direction (pass on the
   design jittered 1-2 px, fail on today's build).
2. The hair line layer: the traced strokes rendered on the hair surface, moving with it (garments.ink_strokes'
   mechanism), projected per lock where the splitter's locks exist; right in every view, on real render-box builds.
3. Cel tones: the drawn shadow and highlight shapes per lock, traced, measured, rendered in the hair's look layer;
   art_terminator_hair <= 2.064 (six-placement means as well as the placement).
4. Guard and review: every hair piece's IoU per view, art_peeks_hair, hair_noise, folds beside every change; review
   page (design | today | strokes | strokes + tones, per view, matching scale, close-ups).
5. Gate each milestone (strokes, then tones): `python -m charkit remote gate tool/hairstrokes --into pipeline-3d`.

Scope additions (coordinator, 2026-10-01; each checked against the design first, built only where drawn, each a
declared calibrated check):
- Strokes milestone: (a) line weight and taper (strokes taper at their ends, inner lines thinner than the silhouette
  outline); (b) thin strays beyond the silhouette at the sides (Michael's flag 4) as tapered strokes (the larger flicks
  are the geometry track's); (c) the buns' drawn wrap lines.
- Tones milestone: (d) custom shading normals per lock blended from a smooth head envelope (clean cel shadow shapes;
  should control art_terminator_hair); (e) the inner/underside tone (darker on lock undersides and the underlayer);
  (f) the highlight band (the drawn shine marks on the crown and bangs, view-aware, not fixed patches).

## State
- Setup done (2026-10-01): notes, `charkit/out/hairstrokes/`.
- **Baseline** `charkit/out/hst_base` (render box, the default at 3168961, boards views/body/design; stored as the
  known-bad `hst_base`): art_terminator_hair 2.002 WARN (six placements 2.006 +- 0.081, max 2.155), art_peeks_hair 17
  (17.5), hair_noise 0.0717 W, folds 9, hair_back_lines 0.894 W, lock lines 3q/P 0.176/0.104 F, hem 3 W; guard IoUs
  bangs F/P 0.849/0.630, side locks 0.560/0.469, upper back P/B 0.621/0.890, lower back F/P/B 0.514/0.665/0.672.

## Step 1: the measure (what the drawing's strokes are, and what one 3D stroke set can match)
- The drawn hair's lines (hairflagqa's drawn lines: the line class + outfit.ridges' faint strokes) inside the mass
  (hairflagqa's keep) per view: front 6.15 L, 3q 5.74, profile 3.42, back 1.68. The splitter's lock boundaries (the
  produced hair_split's lock image, within 0.012 L) take most: the **strands** (the rest, pieces of 0.02 L or more) are
  front 1.20 L, 3q 1.05, profile 0.63, back 0.53 (`geom.hairink.drawn_strokes`; tools/strandov.py pictures). The top-hat
  ink the splitter also reads adds mostly shadow-tone bands, not strokes (tools/inkdet.py): line class + ridges kept.
- The back's "strands" are the hem flicks' notch ticks and a tone edge: its mass is drawn plain.
- **The views draw their strand texture independently**: strokes placed in 3D from one view add 0.00-0.01 to the
  1.5 px recall of another view's strokes (front-only strokes: 3q 0.094 -> 0.105, profile 0.018 -> 0.018; lab_front,
  lab_three_quarter, lab_profile). So one 3D stroke set matches each view's exact strokes only where taken from that
  view (rule 3: the checks measure the intent; exact placement is each view's reported cost).
- The QA's camera vs the hull views' frame: 1-6 px apart in profile/3q (tools/reg.py); the layer projects in the QA's
  frames (geom.hairink.frames: our iris centres from the assembly, the sheet's 3q angle as qa3d measures it).
- Our strokes (0.0035 L wide, 0.74 px at 212 px/L) came out dashed in the numpy line drawing (pixel centres, no
  supersampling): `declared.our_ink` draws ink-slot faces at least a pixel wide (geom.raster thin labels), as the
  drawing's faint strokes are read; front-only strokes' front recall 0.65 at 0.25 L of ours -> 0.71 at 0.63 L.
- Candidate measures (tools/cands.py, cands2.py; floors: strands moved 0.05-0.15 L / scattered anywhere in the mass /
  turned 30-90 deg): nearest-line recall at 0.04 L is coarse (the drawn lines lie ~0.04 L apart: scattered all-lines
  0.62-0.74); **density** (the two density fields at 0.06 L, L1 over the sum): design 0.05-0.06, moved 0.31-0.36,
  scattered 0.67-0.76, today 1.0; **dir** (median angle to the drawn flow at 0.03 L where coherent): design 4-6,
  turned 51-63, scattered 23-50.
- Checks (charkit/hairstrokeqa.py, declared family `strokes` in declared.py, the hair as a piece `hair`):
  hair_strokes_{front,three_quarter,profile}_density [0.4, 0.65] and _dir [20, 30]; recall, place, precision reported.
  Back: none (the back draws no strand texture; hair_back_lines guards it).

## Step 2: the line layer (charkit/geom/hairink.py; hair.shape.strokes; cli.pieces_hair; scene ink slot)
- trace (inkfit) -> project along each view (QA frames, z-buffer of the mass pieces + skin, exact ray hit) -> keep
  (facing >= min_face 0.2 within margin of the best; the cross-view veto: every other view that sees the point
  squarely, facing >= veto_face, draws a line within veto_near) -> tapered ribbons (width 0.0035 L, tip 0.15, taper
  0.6, lift -0.002 L) appended to the piece on an ink slot (`ink` per face in the part npz; scene: flat `hair_ink` in
  the hair's line colour; outline_w 0). QA: hairflagqa draws ink as ink and leaves it out of the parts; hair_noise
  leaves it out (qa3d.without_ink); sweep's hair splice carries it (needs a base with ink slots).
- Lab (tools/lab.py: hairink on hst_base's own pieces spliced into its bundle; ok as the bootstrap until a strokes
  build exists, then `charkit sweep`). Readings (density per view F/3q/P/B; ours L):
  ownership 0.05: 0.56/0.63/0.45/0.33; all views kept (margin 0.5): 0.45/0.43/0.52/0.30 (ours 1.4/2.2/1.6/0.65: other
  views' strokes overdraw 3q/P); + veto, back not traced: 0.38/0.40/0.70/- (ours 0.97/1.19/0.66, precision ~1.0).
- Guard on the all-kept lab: every hair piece IoU unchanged; hair_noise 0.0717 = ; lock lines 3q 0.176 -> 0.298,
  P 0.104 -> 0.257; **hair_back_lines 0.894 W -> 1.375 F** (0.61 L more ink in the back: a profile stroke on the upper
  back's side and the back's hem ticks; the hull's own stripes already read 0.894, so the back has 0.13 L of headroom):
  hence the back left out and the veto; art_terminator_hair single placement 2.147 but six placements 2.020 +- 0.088
  (base 2.006 +- 0.081): neutral; peeks 17.5 -> 17.7.

## Scope additions, strokes milestone
- **(c) the buns' drawn lines** (where a bun's front block meets the one behind, its tiers' steps; tools/bunov.py):
  today ours lack them (bun_{L,R}_{view}_lines, ink_inside in the drawn bun with our ink: 0.65-1.0 FAIL in every view).
  Traced from the design (geom.hairink bun set: the lines inside each drawn bun, off its outline 0.015 L) and laid on
  the bun pieces: lab (bun veto by head-on views only, facing 0.9: our bun block isn't the drawn one exactly, so lines
  from one view land off the others; without a veto the profile bun's side fills with other views' lines): L front /
  3q / profile / back 0.009 / 0.254 / 0.269 / 0.059, R front / 3q / back 0.118 / 0.291 / 0.235, all PASS.
- **(b) strays beyond the silhouette** (tools/strays.py: what an opening by a disk r 2 / 4 px cuts off the hair's
  silhouette): the design's thin parts are the locks' sharp flick tips (front 28 pieces 0.81 L at r 4; profile 14),
  plus the hooked flyaways under the buns: filled thin shapes with two outlines, not single-line strays. Nothing for the
  line layer to build (the brief: the flicks are the geometry track's). Measured for the geometry track: ours in front
  sticks out more at r 2 (0.306 L against the drawn 0.089: the flyaway blades, horizontal), and the profile has no tips
  at all (0 against 14 pieces 0.34 L).
- **(a) line weight and taper:** built (ribbons 0.0035 L against the outline's 0.0056 L, tapering to 0.15 over 60% of
  their length; the head turnaround draws inner strokes thinner than the outline, tapered). A calibrated check needs
  our head drawn at the head sheet's 400 px/L against the sheet's own strokes (the body sheet's 212 px/L can't resolve
  1-2 px widths): pending (after the strokes gate).

## Tones: today's reading (tools/tones.py on hst_base; shadow = value under the outfit graph's lit/shade midpoint)
- Shadow IoU (inside both hairs, off the lines) F/3q/P/B 0.360/0.362/0.450/0.463; shadow share design 0.22/0.23/0.24/
  0.21, ours 0.26/0.21/0.19/0.14. The drawn shadow: the lower halves of the locks, the back's hem lobes, the buns' lower
  faces, a thin band under the bangs.
- Highlights (value 0.06 over lit): design 0.004-0.009 L^2 per view (short pale marks on the crown), ours 0.002-0.015
  (the streaks and the buns' diamond), IoU 0.000 in every view.

## Strokes milestone: the real build (charkit/out/hst_s1, 619659c, render box, boards views/body/design)
Reproduces the lab exactly (base hst_base -> hst_s1):
- hair_strokes_{front,3q,profile}_density 1.0/1.0/1.0 FAIL -> 0.384/0.420/0.594 WARN; _dir none (FAIL) -> 12.2/9.4/14.4
  PASS; recall (0.04 L) 0.71/0.51/0.41, place (0.015 L) 0.62/0.48/0.35, precision 0.99/0.94/0.91.
- bun lines L front/3q/profile/back 0.791/0.646/0.969/1.0 FAIL -> 0.009/0.254/0.269/0.059 PASS; R front/3q/back
  0.785/0.848/0.959 FAIL -> 0.118/0.291/0.235 PASS.
- Guard: every hair piece IoU per view unchanged (bangs F/P 0.849/0.630, side locks 0.560/0.469, upper back P/B
  0.621/0.890, lower back F/P/B 0.514/0.665/0.672, buns 0.856/0.851/0.875); art_terminator_hair 2.002 W -> 1.979 P
  (six placements on the lab: 2.006 +- 0.081 -> 2.020 +- 0.088); art_peeks_hair 17 -> 18 (W); hair_noise 0.0717 ->
  0.0743 (W); folds 9 = ; hair_back_lines 0.894 -> 0.928 (W); lock lines 3q 0.176 -> 0.281, profile 0.104 -> 0.167
  (FAIL both, better); hem 3 = ; attached 0 = ; build CPU 1426 -> 1089 s.
- Calibration (lab labb_v2, calib3.log): 13 CALIBRATED; bun_R_profile had no drawn bun (views fixed, 3daa50b).
  Records on hst_s1: all 13 CALIBRATED, committed (54a0c57).
- Pregate (54a0c57 into 3168961): PASS, 2 moved, 0 blocking
  (charkit/out/pregate/pregate_tool-hairstrokes_54a0c578_into_31689611.md).
- **Gate 1: FAIL under K, 4 blockers** (54a0c57 into 3168961;
  charkit/out/gate/gate_tool-hairstrokes_54a0c578_into_31689611.md): (1) test_spec_alias.py: clawd_body_pieces.json
  is an alias of clawd.json and lacked the strokes block (fixed); (2-4) hair_back_lines, hair_lock_lines_profile,
  hair_lock_lines_three_quarter are remeasured (hairflagqa now draws ink strokes as ink) and need refreshed records
  (steps registered against ae33ac8 in charkit/steps/hairflagqa.py, and hair_noise's in steps/qa3d.py). Otherwise:
  no new FAIL, no flag grade regression (flag values moved: lock lines 3q 0.176 -> 0.281, profile 0.104 -> 0.167,
  peeks 17 -> 18, back lines 0.894 -> 0.928), 0 guard findings, build CPU 1.22x, the 13 new checks calibrated. The
  2x2: the hair flags read the same on the old geometry under the new measure (0.894, 0.1044, 0.1764).

## Round 2 (2026-10-01, relaunch)
- Merged pipeline-3d 00494de (clean). The known-bad store hair5_1580f95 (its laptop source, the hair4 worktree, is gone):
  restored from the render box's autopreview copy of the 1580f95 preview (/srv/work/animation-pipeline-autopreview/
  charkit/out/previews/1580f95: bundle b37ed795a314d2b9, the record's own) via my box copy and `build.sh fetch`, then
  calibrate.store (the tracked known_bad record kept as it was).
- Records refreshed (3b1fe35; calib_flags.log): hair_back_lines, hair_lock_lines_{three_quarter,profile} CALIBRATED;
  design and known-bad read as before (-0.022 / 3.761; 0.98-1.00 / 0.164; 0.99-1.00 / 0.202), current 0.928 W /
  0.167 F / 0.281 F. Pregate 3b1fe35 into 00494de: PASS, 2 moved, 0 blocking.
- (a) line weight: charkit/hairweight.py (the same detector on the head sheet and our head drawn at 400 px/L, the
  lines at the head boards' screen width: darkness under a grey closing (9 px) as coverage of the picture's outline
  ink, integrated across each line at its skeleton = its weight, width and darkness at once). The design's strands are
  its faint lines (peak < 0.7 of the outline ink: brown), its lock lines and clips black. Readings (hst_s1, F/3q/P):
  weight (strand / outline) design 0.256/0.253/0.265, ours 0.276/0.247/0.305; heavy floor 1.00/1.01/0.97, blunt 0.26-0.28.
  Taper = px over which a strand's weight falls 0.75 -> 0.25 of its middle's, followed past each free end (the design's
  faint ends fall under the skeleton's threshold: an end/middle ratio read it 0.8-0.9, untapered): design 5.5/6.0/5.5,
  ours 4.0, blunt floor 1.0-1.5. Declared family `line_weight` (declared.py; inputs' `head`), checks
  hair_strokes_{view}_weight |log2(ours/design)| [0.5, 1.0] and _taper ours/design [0.6, 0.4] higher (hairstrokeqa.py),
  floors heavy_strokes / blunt_strokes (declared.WEIGHT_FLOORS, hairweight.redraw), known-bad hst_base (no strokes:
  FAIL). Declared part on hst_s1: weight 0.109/0.035/0.203 PASS, taper 0.727/0.667/0.727 PASS; hst_base all FAIL.
  Calibration needs the checks in the build's qa.json: hst_s1's QA re-run (`charkit qa`), then calibrate
  (calib_weight.log).
- Observation for Michael: our hair outline reads 1.84-1.87 px at 400 px/L against the drawn 2.47-2.58 (the look's
  screen lines, 0.0022 of the page); the strokes are world-wide ribbons, so their weight against the outline changes
  with the framing (heavier in close-ups, thinner in full-body shots).
- Coordinator default (lock lines as ink on the hull shell, per region, off where the lock shells are on): built.
  hairink `lock_lines` (spec strokes.lock_lines true in clawd.json and its alias): the splitter's lock lines (the
  drawn lines within `wall` of its lock boundaries) traced and placed as the strands are (same veto), at lock_width
  0.005 L (the head boards' outline), skipping points that land on a lock shell's vertices; ink kind 2 on their own
  material `hair_lock_ink` (scene.py), which declared.our_ink and hairweight leave out of the strands (lines, not
  strokes; hairflagqa reads them as lines). Sweep lock_lines on over hst_s1: charkit/out/hairstrokes/sw_locklines.

- Commit d3ac002: the weight/taper checks and records (all 6 CALIBRATED: design 0.017-0.038 / 0.91-1.0, hst_base
  FAIL, floors heavy 1.97 / blunt 0.25 FAIL; hst_s1 weight 0.32/0.20/0.42, taper 0.64/0.67/0.68 PASS), lock lines,
  hairtones + the `tones` family. charkit/hairtoneqa.py (the tones checks' declarations, provisional limits) is kept
  uncommitted until calibrated, so the strokes gate carries no uncalibrated check.
- **Laptop memory critical (coordinator, 2026-10-01 08:10): no heavy local jobs.** Calibrations, sweeps, builds, labs
  on the boxes: `charkit sweep ... --box render`, `charkit remote --box render run ...`; harness scripts pushed with
  `CHARKIT_BOX_ENV=infra/gcp/render.env bash infra/gcp/build.sh push charkit/out/hairstrokes/tools/
  /srv/work/animation-pipeline-hairstrokes/charkit/out/hairstrokes/tools/` and run with `build.sh run $PWD 'python
  ...'`, outputs fetched with `build.sh fetch $PWD DIR` (the sync leaves charkit/out alone). On the render box:
  hst_base, hst_s1, the store charkit/out/calib/builds/hst_base (linked; the box copy's synced files are read-only,
  so `calibrate store` fails writing the tracked record after linking: harmless).
- **Boxes (coordinator, 08:40): the render box has 3 slots and is saturated; sweeps, calibrations, QA-only builds,
  gates go to the build box (8 slots; omit --box render).** The build box's QA draws with charkit's toon renderer too
  (gate builds' qa.json measured.draw: render, 65 frames, clawd.look.glb), so the highlight checks read the streaks
  there; a sweep's spliced bundle is drawn with numpy (no streaks): highlights need real builds or tools/hlfit.py.
  Render box only for builds whose boards go on a review page.
- Box jobs (2026-10-01 ~08:10): the lock-line sweep (charkit/out/hairstrokes/sw_locklines, sw_locklines.log), the
  tones triple on hst_s1 (box_tonecal.log: QA re-run there, calibrate --no-write), the shadow blame (blame/).

## Tones milestone: the measure
- Checks (charkit/hairtoneqa.py, uncommitted until gated with the tones: family `tones`, charkit/hairtones.py):
  hair_shadow_{view} IoU [0.6, 0.5] higher, hair_highlight_{view} F1 within 0.02 L [0.5, 0.25] higher. The triple on
  hst_s1 (render box, --no-write; box_tonecal.log): shadow design 0.86-0.95, hst_base 0.36/0.36/0.45/0.46 FAIL,
  scattered 0.02-0.04 FAIL; highlight design 1.0, hst_base 0/0.10/0.05/0 FAIL, scattered 0-0.07 FAIL: all
  CALIBRATED with these limits (set before any tones change). Records to write on the tones build.
- Shadow blame (tools/toneblame.py, blame/s1.png, s1.log): the drawn shadow is height-driven and symmetric (the
  locks' lower ends both sides, the hem band ~ the back's lower third, the buns' undersides); ours follows the camera
  key (30 deg left, 40 up): the right side lock shaded (front: ours 0.38 vs drawn 0.27), the left lock's hem lit, the
  back's hem band too thin (lower_back back 0.63 vs 0.90), the buns' undersides lit (0.08-0.20 vs 0.16-0.30), the
  profile's side lock unshaded (0.01 vs 0.17).
  (d): hairpieces shade_ellipsoid / shade_squash (769465a, off by default): the mass envelope's normals blended toward
  an ellipsoid round the hair's mass, its vertical semi-axis squashed: normals turn down below the middle, so the
  camera key shades by height in every view. Sweep on the render box (queued): grid ellipsoid [0.5, 1] x squash
  [0.5, 0.8] (sw_normals). Touches shade_normals, which also shades the lock shells when they're on (tool/hairshell3):
  flag to the coordinator.
- Highlights (tools/hlmap.py: marks cast onto our hair, elevation/azimuth about the streaks' centre): the drawn marks
  sit at elevation 36-46 deg (median 39-41) in every view, spread over the crown facing the camera (az within ~45 deg
  of the view); ours at 42-52 (median 49), clustered at az 94 and -135 (streaks landing on the buns): the style's
  streaks (anime.json look.hair: elevation 47, length 5, jitter 4, count 36, duty 0.25, keep 0.3) miss the crown.
  (f): tools/hlfit.py evaluates the streak function (shade.streak_columns, facing map, lit only) on our hair's pixels
  and fits elevation/length/keep/jitter/duty/count to the drawn marks (F1 per view); the fit goes in the spec's
  look.hair (the character's), confirmed on a real build.

## Exact next steps (lean relaunch)
1. Refresh the three remeasured flags' records: copy the known-bad store
   `~/animation-pipeline-hair4/charkit/out/calib/builds/hair5_1580f95` into this worktree's
   charkit/out/calib/builds/ (read-only source), then `python -m charkit calibrate
   hair_back_lines,hair_lock_lines_three_quarter,hair_lock_lines_profile --build charkit/out/hst_s1` (writes
   charkit/calib/records/; expect CALIBRATED: the design reads the same, hair5_1580f95 has no strokes). Commit, pregate,
   `python -m charkit remote gate tool/hairstrokes --into pipeline-3d` (the box ssh drops often: if the follower
   dies, `remote attach JID`). Merge pipeline-3d first if it moved.
2. Review page (charkit review page): design | today (hst_base) | strokes (hst_s1) per view at matching scale, the
   boards' close-ups of the side locks and buns; tools/ovl.py, bunov.py pictures. Asked of Michael: the per-view cost
   (strokes from one view don't match another view's texture: density WARN in every view, by design of the rule);
   draw the lock lines as ink too on the hull shell until the lock shells cover the head (set 'all')?
3. (a) line weight and taper check (head frame at 400 px/L against the head sheet's strokes: inner/outline effective
   width, end/middle width), then the tones milestone: declared checks from tools/tones.py (shadow IoU per view,
   highlight marks), (d) lock normals (shade_normals' lock_shading; art_terminator_hair <= 2.064 on six placements),
   (e) the underside tone (hair_toon `inner` / under families), (f) highlight marks (traced, view-aware), gate.

## Jobs
- Done: box build charkit/out/hst_s1 (build_s1.log); calib3 (lab); calib_s1 (records); pregate; gate 1 (FAIL, 4
  blockers: next steps 1). None running.
