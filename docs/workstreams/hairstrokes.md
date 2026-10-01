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

## Jobs
