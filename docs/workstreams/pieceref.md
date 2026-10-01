# Piece references and the bow's sub-pieces (tool/pieceref)

Worktree `~/animation-pipeline-pieceref`, branch `tool/pieceref` from tool/bow2 478f0ce (its bowqa checks and the
close-hung option), pipeline-3d 1580f95 merged in (d07ef79). Builds read (other worktrees, read only):
`~/animation-pipeline-bow2/charkit/out/b2_close` (the option, box), `.../b2_before`, and the old sunken-ribbon build
(pre-M1) `~/animation-pipeline-garments3/charkit/out/g3_render3` (also `co_render`). Harness (untracked):
`charkit/out/pieceref/harness/` (`load.py` finds a build by name in this, bow2's and garments3's out dirs).

## Michael's decisions (2026-09-30)
1. Take the close-hung bow (profile IoU 0.346 -> 0.654). Option C for `bow_profile_ribbon`: remeasure it as what he
   meant, "ribbons merging into the blouse": the ink line between ribbon and jacket, calibrated, registered.
2. Sub-piece-cut multi-segment garments: the bow as knot + left lobe + right lobe (the tails are pieces already), each
   with its own mask in the outfit masks and truth, its own shape checks, and checks of its inner lines (the knot's
   outline and rectangle, each lobe's crease).
3. Isolated-piece checks: shape from the isolated reference (garment_breakdown, close-ups), placement, occlusion and
   silhouette in context from the turnaround. Render each piece alone in the reference's projection, scaled to its
   own size; compare shape and inner lines. Refcheck each generated reference against the turnaround first.
4. Generate references where needed (paid, approved, few calls, logged to tools/ledger.jsonl): a bow close-up sheet.

## State (start here; checkpoint at the context limit, 2026-09-30)

Done and committed (head 9ebcf51); nothing gated, no box build of this branch yet.

1. **The option in the default spec** (2dc325a; clawd.json's bow: ribbon turn 20, w [0.204, 0.338], drop 0.2).
2. **Option C** (2dc325a, step 43d7e16; charkit/collarqa.py `ribbon_line`, `runs_rows`; test): bow_profile_ribbon is
   now, per row over 30-80% of the drawn tails' height in profile, whether the widest ribbon run is at least
   `RUN_MIN` 0.03 L and touches no jacket or sleeve pixel (an ink line between), ours drawn with the build's outlines
   (lookqa frame `RIBBON_WIN`, 400 px/L); the share of rows that don't, beyond the design's; limits 0.15 / 0.30.
   A line-only reading passed the sunk build (its ribbon is a 0.005 L sliver between two lines: lined, but merged),
   hence the width. Calibration (`harness/ribcal.py`): design 0 (widest run 0.115 L) PASS; g3_render3 1.0 FAIL (run
   0.005 L); b2_before 0 (0.165), co_render 0 (0.08), b2_close 0 (0.0775) PASS.
3. **Sub-pieces** (7003551): `outfit.PARTS` {'bow': knot, lobe_L, lobe_R}; `outfit.bow_parts` cuts each view's bow
   mask by the drawn cells (knot: a cell of 1-25% of the bow, in front nearest the middle column, elsewhere centred in
   the front knot's rows; lobes by side of the knot, cell by cell; profile: the rest is the near lobe L); masks keyed
   `VIEW__bow.knot|lobe_L|lobe_R` (a '.' in a key marks a part: `outfit.is_part`; the hull, perceptual and the piece
   partition pass them by); the graph's bow lists its `parts` (the tracked graph got only that insertion: a full
   regeneration rewrites the TRELLIS-era provenance and extents, 1,853 lines: don't); truth `VIEW.parts` +
   `part_sets` in outfit_truth.npz (cells labelled by eye: `harness/mkparts.py`, pictures `harness/bowcells_*.png`);
   `outfit.score_parts`, printed by `python -m charkit outfit score`: front 1.000, three-quarter 0.940 (the piece
   partition gives a fold cell to the tails), profile 1.000; knot 1.000, lobe_L 1.000, lobe_R 0.938. The piece
   partition is unchanged (0.972, mean IoU 0.913). The manifest's outfit_truth and outfit_graph are rehashed.
4. **partqa** (e992be8, step 9c9077a; QA part `bow_parts`, order 1770; tests `test_partqa.py`): ours z-buffered with
   the bow mesh split by part (`partqa.split`: connected parts; a `bow_knot` object is taken as the knot if one is
   added) against the part masks, and in front ours drawn with the build's outlines (surfaces split by part:
   `split_surfs`, `line_picture`) against the design's lines (`design_lines`: its ink and its fainter strokes,
   outfit.ridges; the creases are drawn in a shade). Checks and calibration (`harness/partcal.py`):

   | check | design (moved 1-2 px) | b2_close | b2_before | g3_render3 |
   |---|---|---|---|---|
   | bow_part_knot_iou (flag; worst view) | 1.0 | 0.0 F (front 0.536, 3q 0.127, profile 0.0) | 0.0 F | 0.019 F |
   | bow_part_lobe_iou (guard) | 1.0 | 0.722 P (front 0.94/0.92, 3q 0.85/0.72, profile 0.92) | 0.702 P | 0.715 P |
   | bow_part_knot_line (flag) | 0 (design 1.0 lined) | 0.949 F (ours 0.05) | 0.958 F | 0.961 F |
   | bow_part_knot_rect (flag) | 0 (aspect 1.389, fill 0.98) | 0.475 F (1.235, 0.878) | | |
   | bow_part_crease_len (flag) | 0 (len 1.53 / 1.45 widths) | 1.0 F (none) | 1.0 F | 1.0 F |
   | bow_part_crease_dir (flag) | 0 (-36.7 / -39.8 deg) | None F | None F | None F |

   Ours today: the knot (0.1275 L wide against the drawn 0.0847) has no line against the lobes, hides in profile and
   sits off in three-quarter; the pillows have no line inside them.
5. **isoqa** (9ebcf51 and its step; QA part `iso_pieces`, prefix `iso_`, order 1775): the manifest's authority split
   (`shape_bow`: garment_breakdown, `piece_placement`: outfit_graph, a note) and the breakdown's `pieces` (the bow's
   box [2130, 44, 2484, 350], view front, rigid). `ref_piece` splits an isolated drawing by its ink cells (the
   breakdown's bow: five clean cells, lobes 14.4k px, tails 12.4k, knot 2.8k); `our_piece` draws ours alone;
   `compare` scales both to the body's width. **Refcheck** (the turnaround's front bow the same way): body IoU 0.762,
   tails 0.759, knot 0.110 against 0.147 of the span, knot fill 0.98 against 0.91: the flat-lay's outline and knot
   are not the turnaround's; its inner lines are (crease -39 deg against -37/-40, length 1.56/1.47 against
   1.53/1.45 lobe widths, the knot outlined all round). So graded (flag): iso_bow_knot_line, iso_bow_crease_len,
   iso_bow_crease_dir (the reference scaled 0.8-1.25 and moved reads itself: body 0.988-1.0, creases within 5%,
   0.5 deg; b2_close FAILs all three); INFO: iso_bow_body (b2_close 0.82), _tails (0.51), _knot_size (0.13),
   _knot_rect (0.13), _refcheck (0.762). **No test file for isoqa yet** (add: ref_piece on a synthetic five-cell bow,
   compare's scale invariance).

6. **isoqa tests** (6bd720d, `charkit/tests/test_isoqa.py`): a synthetic five-cell bow names its parts; scaled 0.8-1.25
   and moved it reads itself (body 0.98+, tails 0.97+, knot size within 4%, creases within 6%); a rounder bow 0.90.
7. **The bow close-up call** (round 2, 2026-09-30): prompt `bow_closeup` in prompts.json; one call, n=2, 2560x1440
   high, refs body_turnaround then garment_breakdown, out `charkit/out/pieceref/gen/bow_closeup_1|2.png`, logged to
   this worktree's tools/ledger.jsonl (a gitignored `.env` symlink to the main checkout's, removed after).
8. **The close-up registered** (f824be4, step fc0952a): refcheck per view (`harness/curef.py`, cells pictures
   `harness/curef_*.png`, overlays `curov_*.png`; `harness/cucal.py IMG BUILD..` reads builds against one):

   | reference (front) | body IoU | tails | knot / span (turnaround 0.110) | whole silhouette 3q / profile |
   |---|---|---|---|---|
   | garment_breakdown | 0.762 | 0.759 | 0.147 | (front only) |
   | close-up take 1 | 0.818 | 0.531 | 0.121 | 0.522 / 0.318 |
   | close-up take 2 (registered) | **0.871** | 0.516 | 0.135 | 0.444 / 0.314 |

   Take 2's three-quarter is turned the other way (its larger lobe the picture's left); both takes' 3q and side views
   draw no line between a lobe and its tail (the ink-cell split fails there), their tails ~20% longer: only the front
   is registered. Authority split per property: `shape_bow: bow_closeup` (iso_bow_body now graded, flag: the
   turnaround 0.871 PASS, b2_close 0.754 WARN, b2_before 0.616 and g3_render3 0.659 FAIL; the breakdown couldn't
   separate: b2_close 0.82 above the design's 0.76), `lines_bow: garment_breakdown` (knot line, creases: its creases
   match the turnaround's, the close-up's run 1.84-1.90 lobe widths against 1.40-1.53); tails, knot size, knot rect
   INFO (knot size: the turnaround 0.18 against the close-up, flagged builds 0.22: no separation). isoqa's knot-line
   reach now scales with the picture's line width (the close-up's 5-6 px lines read None at 2 px).
9. **pipeline-3d 004efc3 merged** (857ffbd; tool/calib: `charkit calibrate`, records required for new and remeasured
   checks, the guard in the gate). steps/collarqa.py conflict: both sides' entries kept.
10. **The pleated bow** (d814b6a; knobs, OFF in the default spec, so builds are unchanged): garments.py
   `_bow_mesh(pleat=, knot_box=)`, `_pleat_band`: each lobe a trapezoid panel (pinched at the knot, top rising to a
   square upper corner, bottom to a rounder lower one) folded along a straight crease from the knot's lower corner to
   the lower outer corner over a strip behind (the fold's underside, `step` half-depths back), meant to make the
   panel's edge a silhouette the hull draws; the knot `knot_box` [w, d, h, corner radius] (sizes) stood in front of
   the lobes by its sides after the wrap (`pleat.stand`, bow_hull), so its hull's back faces outline it; `pleat.cup`
   (the lobes' ends forward) and `pleat.wrap: 'row'` (lobes wrapped by their centre row) are there but hurt (p3).
   7 connected parts: partqa.split names them. partqa's knot line now reaches the outline's width (b591b22 step).
   Harness: `harness/var.py OUT --base b2_close --set 'garments.bow.pleat=JSON' --set 'garments.bow.knot_box=JSON'`
   (bow2's, the outline's shrink rebuilt from the normals: -N |thickness| (1 + offset) / 2; b2_close's bow matches at
   cos 0.99998, and v0 reproduces the box's partqa numbers exactly, so line checks read on splices); ~70-110 s;
   `harness/bowview.py SRC` (front/3q/profile with lines, bow by part: `bowview_*.png`); `harness/partonly.py SRC`.

   | run (on b2_close's bundle) | piece_bow F/3q/P | knot_iou F/3q/P | lobe_iou | knot_line | knot_rect | crease_len | profile thick/lean/hang | iso body |
   |---|---|---|---|---|---|---|---|---|
   | v0 (b2_close as is) | 0.926/0.828/0.654 | 0.536/0.127/0 | 0.722 | 0.889 F | 0.475 F | 1.0 F | 0.035 W/2.6/4.2 | 0.744 F |
   | p2 pleat knot .07 top/bottom .24 sag .06 step 1.4 thin .4 pinch .6 stand .01; knot_box [.10,.09,.145,.02] | 0.948/0.874/0.582 | 1.0?/0/0 | 0.703 | **0 P** | **0.094 P** | 0.748 F | 0.066 F/34 F/15 F | 0.739 F |
   | p3 = p2 + cup .12, depth .09, wrap row | 0.941/0.793/**0.458** | | 0.503 W | | | 0.935 F | 0.060 F/51 F/20 F | 0.769 W |

   Findings: the knot is fixed in front (outlined all round, a rectangle). Open: (a) **no crease line is drawn**
   (bowview: no line inside the panels in p1-p3): probe the depth at mid-lobe across the crease after the wrap (panel
   rim vs strip front) before tuning; the hull's visible ring at a lower edge is the panel's BACK half (flipped shell,
   front-culled), so the strip must sit behind the panel's back surface there, not just its centre plane: try step >=
   1 + thin with the strip's top overlap small, or build the fold as the panel's lower edge turned back (a lip) rather
   than a separate strip. (b) **The knot in profile**: it floats 0.004 L + lines in front of the lobes (a gap), knot
   IoU 0 in 3q and profile; the design's knot overlaps the lobe in profile: the lobes' middles must come forward past
   the knot's back while staying behind it by its sides (cup did that but wrecked the profile: try cup with the default
   wrap and a smaller value, 0.03-0.06). (c) **The profile loop checks** (bow_profile_loop_thick/lean, tail_hang;
   flag-calibrated in bow2's bowqa: regressions block): pleat lobes are thin wedges in profile; the pillow's depth
   (spec depth 0.06, pinch) and the top/bottom heights set them. (d) bow_part_knot_iou front reads 1.0 on p1-p3 (a
   round and a square knot alike): check partqa's front knot mask at the sheet scale before trusting it.
   Guard: piece_bow must stay within ~15% of v0 in every view (profile >= 0.556).
11. **Calibration records not written yet** (the gate needs them: bow_profile_ribbon (remeasured; the existing record
   is for the old measure), bow_part_*, the graded iso_*). `python -m charkit calibrate CHECK` runs a QA part with an
   adapter from `charkit/calib/*.py` (CALIBRATION literals; labels.py's Garments patches our label pictures with the
   design's masks). Needed: (i) Garments.patches: patch `collarqa.ribbon_line` like `bleed` (the design's tails moved,
   lines kept -> reads the design's value; a generator's stand-in: no line between pieces); (ii) a new
   `charkit/calib/parts.py`: adapter for `bow_parts` (patch `partqa.grid_labels` with the design's part masks moved /
   voronoi-relabelled / affine-moved, and `partqa.line_picture` with the design's parts and lines) and for
   `iso_pieces` (patch `isoqa.our_piece` with `design_piece(front)` moved, or relabelled cells); known-bad
   g3_render3 (stored) for all; kinds: knot_iou, lobe_iou, iso_bow_body 'shape'; knot_line, knot_rect, crease_*
   'defect'; shape ['piece_bow'].

12. **Round 3 (2026-09-30, relaunched lean; coordinator: split authority accepted, take 2's front only).**
   - Diagnosis (harness `probe.py SRC` [each connected part its colour, hull lines black, 1200 ppl], `dcrease.py SRC`
     [the counted crease pixels, design | ours, and per-u stations: top, bottom, crease rows in L from the knot's
     centre], `partov.py SRC` [what bow_part_*_iou compares, per view], `depth.py SRC`, `isofill.py SRC..`): the panel's
     lower edge WAS drawn, but as the lobe's own lower silhouette (the strip showed only as a sag sliver), so the crease
     measure (lines over 0.018 L inside the lobe) read only 0.39-0.42 widths. The design's lower crease sits a quarter of
     the lobe's height above its lower edge mid-lobe (0.055-0.1 sizes of strip), closing at the lower outer corner, and
     an upper almond (two strokes, u 0.1-0.45, 0.65-0.7 of the height) makes its direction -37/-40 (the lower crease
     alone runs ~-24).
   - garments.py pleat keys (all off unless set): `crease` [share at the knot, at the end] + `crease_p` + `close` (the
     crease its own line; the strip below closes onto it before the end cap), `almond` {u, f, h, d, gap} (a thin lens
     standing `gap` proud of the panel: its outline draws the fold), `bulge` [amount, u] (lobes' middles forward:
     hurt: the 3q far lobe and the lean), `seat` (L; knot's back in front of the side lobes; `stand`'s rule followed the
     lobes' frontmost and floated the knot), `top_p`, `bottom_p`.
   - isoqa remeasure: iso_bow_body compares silhouettes (`isoqa.silhouette`: the parts with the lines next to them,
     holes filled), both sides: the drawn creases cost the old body IoU a share per line (p6 0.598 with its silhouette
     unchanged). Calibration set, old -> new: turnaround 0.871 -> 0.917 PASS, v0/b2_close 0.744 -> 0.772 WARN, b2_before
     0.616 -> 0.679 FAIL, g3_render3 0.659 -> 0.724 FAIL (same grades). Step to register (steps/isoqa.py).
   - Calibration adapter `charkit/calib/parts.py` (BowParts for bow_parts, IsoParts for iso_pieces; the turnaround's
     part masks and lines as ours; generators voronoi_parts, affine_parts; known-bad g3_render3, now stored here:
     `charkit/out/calib/builds/g3_render3`), labels.py Garments patches `collarqa.ribbon_line` (design moved: its own
     reading; generators: no line between). Records need a box build of this branch (`calibrate ... --build`).

   | run (b2_close splice) | piece_bow F/3q/P | knot_iou F/3q/P | crease len/dir | iso body (silh.) | thick/lean/hang |
   |---|---|---|---|---|---|
   | v0 (b2_close) | 0.926/0.828/0.654 | 0.536/0.127/0 | 1.0 F / None F | 0.772 W | 0.035 W / 2.6 P / 4.2 P |
   | p2 (round 2) | 0.948/0.874/0.582 | 1.0/0/0 | 0.748 F / 21 W | 0.864 | 0.066 F / 34 F / 15 F |
   | q1 crease [.27,0] p2, almond, sag .06, no stand | 0.949/0.873/0.675 | 1.0/0.012/0 | 0.134 P / 5.8 P | 0.850 P | 0.064 F / 2.75 P / 0 P |

   q1's knot isn't stood (no `stand`/`seat`): its front 0.016 L proud of the side lobes, outlined all round in front
   (knot_line 0 P), seated in the loops in profile (hang 0, lean 2.75). Its 3q knot sits ~0.05-0.08 L left of the
   drawn one (a stood knot projects further left still: p2): the turnaround's 3q knot can't be met by a knot that shows
   in front (reference step 3: reported per view). Open: loop_thick (rows 1-2 and 5-10 thin: the loops end at row ~7.5
   in profile).
   - **The 3q knot is drawn view-dependently** (`azfit.py SRC`: ours z-buffered at other azimuths against the drawn
     3q parts, r1): at the sheet's 35.5 deg the lobes and the whole bow fit best (body 0.928, lobes 0.85/0.91) and the
     knot reads 0.01; at 15-20 deg the knot reads 0.67-0.84 while the body falls to 0.75-0.80. The turnaround draws the
     3q knot as if seen nearly face-on: the rule's step 2-3 (front-exact knot; the 3q knot a per-shot override). Asked
     of Michael: grade bow_part_knot_iou on the front only (the views that agree), the 3q/profile knot reported?
   - Calibration stand-ins tried (`caltry.py SRC`, b2_close): the design moved passes all (knot_iou 0.62-1.0, iso body
     0.93), voronoi/affine fail the shape checks; adapters committed (c808df7).
   - r-runs (knot .07-.08, top_p .6, bottom_p .7, bottom .24-.30; no stand): front lobes 0.99, thick 0.058 (r1) ->
     0.045 W at bottom .30 (r4) but crease_dir 20 W (the almond too high: ours -48..-57 deg against -37/-40) and iso
     body 0.84 W; depth .08 (r3) no help, profile 0.64. Next: `hang` (the strip's lower layer lower by the knot, behind
     the tails in front) and the almond lower (f .57-.63): s1-s3.
   - The drawn bow's height (knot + lobes) per view: front 0.353 L, 3q 0.400, profile 0.448 (ours 0.35-0.37 in all):
     the profile draws the loops 0.09 L lower than the front does, so loop_thick's lower rows can't be met without
     the front's lobes going long; `hang` (lower layer lower behind the tails) changed nothing (hidden in profile).
     bottom .30 is the compromise: front lobes 0.994/0.988.
   - u3 (knot .08, top .24, bottom .30, top_p .6, bottom_p .7, sag .06, crease [.27, 0] p2, almond u [.06,.5] f
     [.54,.60] h .025 d .012 gap .004, hang [.1,.15,.15], step 1.4, thin .4, pinch .6; no stand): piece_bow
     0.954/0.857/0.682 (v0 0.926/0.828/0.654), lobes F 0.994/0.988, 3q 0.843/0.904, P 0.850; thick 0.0447 W, lean 1.05
     P, hang 0 P; crease len 0.14 P, dir 11.0 P; knot line/rect P; iso body 0.839 W, iso creases P. collar_flags
     (`qaonly.py collar_flags SRC`; the splice reproduces the box's v0: loop_end 0.244 W, bleed 0.205 F): u3/s3
     loop_end 0.567 FAIL (the pleat's square cap: a straight end over 71-78% of its rows, design 21%), bleed 0.275 FAIL
     (`bleedpic.py SRC`: the strip's lower edge at the outer ends has no line: its back sits in the jacket). Baseline
     (b2_before = pipeline-3d's bow): loop_end 0.121 P, bleed 0.0 P: both flag checks, so both must PASS. Next:
     v1-v4 (rounder caps, `shear` slanting the ends, the strip shallower: step 1.0, thin 0.3).
   - v-runs (+ collar_flags): rounder caps fix loop_end (cap .3, end_p [2, 1.2]: 0.106 P) but cost the close-up's
     silhouette (iso body 0.744 F: the close-up's ends are squarer); shear .3 on the square cap: loop_end 0.014 P, iso
     0.729 F; a shallower strip (step 1.0, thin .3) costs loop_thick (0.057 F). Bleed (`bleeddepth.py SRC`: per
     touching pixel the jacket's depth less the bow's, by part): the strips' lower edges sit 0.003-0.01 L BEHIND the
     jacket's surface (u3, v2). Added `tilt` (the strip's bottom forward by tilt panel half-depths, none at the crease):
     w1-w5 (tilt .5-1, caps .27-.3 or shear .1-.15).
   - **w-runs (checkpoint, 2026-09-30).** All on u3's pleat (knot .08, top .24, bottom .30, top_p .6, bottom_p .7, sag
     .06, crease [.27, 0] p2, almond u [.06,.5] f [.54,.60] h .025 d .012 gap .004, hang [.1,.15,.15], step 1.4,
     thin .4, pinch .6), knot_box [.10,.09,.145,.02], no stand/seat. Res: `harness/NAME/res.json` (+ splice.pkl).

     | run | changes on u3 | piece_bow F/3q/P | knot F/3q/P | lobe_L F/3q/P | lobe_R F/3q | loop_end | bleed | thick | lean | hang | crease len/dir | iso body |
     |---|---|---|---|---|---|---|---|---|---|---|---|---|
     | v0 (b2_close, default now) | (pillows) | 0.925/0.828/0.654 | 0.536/0.127/0 | 0.937/0.851/0.919 | 0.923/0.722 | 0.244 W | 0.205 F | 0.035 W | 2.6 P | 4.2 P | 1.0 F / None F | 0.744 F |
     | u3 | - | 0.954/0.857/0.682 | 1.0/0.008/0 | 0.994/0.843/0.850 | 0.988/0.904 | 0.567 F | 0.275 F | 0.045 W | 1.1 P | 0 P | 0.14 P / 11.0 P | 0.839 W |
     | w1 | cap .3, end_p [2,1.2], tilt .5 | 0.939/0.849/0.675 | 1.0/0.008/0 | 0.964/0.824/0.874 | 0.946/0.907 | 0.106 P | 0.190 F | 0.060 F | 2.5 P | 0 P | 0.18 P / 11.5 P | 0.744 F |
     | w2 | cap .3, end_p [2,1.2], tilt 1 | 0.939/0.850/0.674 | 1.0/0.008/0 | 0.962/0.821/0.883 | 0.945/0.897 | 0.106 P | 0.178 F | 0.058 F | 3.3 P | 0 P | 0.18 P / 11.5 P | 0.744 F |
     | w3 | cap .27, end_p [2.5,1.2], tilt 1 | 0.950/0.854/0.686 | 1.0/0.008/0 | 0.979/0.831/0.896 | 0.967/0.894 | 0.21 W | 0.203 F | 0.056 F | 3.6 P | 0 P | 0.18 P / 11.1 P | 0.778 W |
     | **w4** | shear .15, tilt 1 | 0.951/0.852/0.685 | 1.0/0.008/0 | 0.989/0.834/0.894 | 0.980/0.887 | **0.123 P** | 0.250 F | **0.046 W** | 4.2 P | 0 P | 0.17 P / 11.4 P | 0.811 W |
     | w5 | shear .1, tilt .5 | 0.953/0.855/0.685 | 1.0/0.008/0 | 0.992/0.838/0.885 | 0.984/0.895 | 0.26 W | 0.265 F | 0.048 W | 2.6 P | 0 P | 0.16 P / 11.3 P | 0.826 W |

     Every run also: knot_line 0 P, knot_rect 0.094 P, iso creases P, ribbon 0 P, tail_reach ~0.03.
     **Best: w4** (`harness/w4/res.json`'s sets): every flag check at PASS or WARN except bow_front_bleed; piece_bow
     above v0 in every view (+3%/+3%/+5%); lobes within 3% of v0 or better except profile lobe_L 0.894 (-2.7%) and 3q
     lobe_L 0.834 (-2.0%); the knot's 3q 0.127 -> 0.008 is the view-dependent drawing (azfit above), not a drop the
     guard means (both FAIL). Rounder caps (w1-w2) pass loop_end but cost the close-up's silhouette (iso 0.744 F) and
     loop_thick; the tilt didn't clear the bleed.
   - **w4's bleed** (`bleeddepth.py w4`, `bleedpic.py w4` -> `bleed_w4.png`): 0.25 L, rows 250-265 at 400 ppl (the lobes'
     lowest rows, outer half), on the strips (parts 1, 5: the jacket 0.004-0.009 L in front of their edge pixels) and
     7 px on a panel's lower corner (bow 0.02 L in front, no line). Tilt 1 (0.046 L forward at the strip's bottom) left
     it: the bleeding pixels are likely the strip's outer end (u 0.65-0.85, where `close` folds its bottom onto the
     crease and the wrap pushes it back), not its mid-lobe bottom.
   - pipeline-3d 3f7b730 (tool/softras round 4) merged (beb1492, no conflicts). g3_render3 stored locally
     (`charkit/out/calib/builds/g3_render3`, gitignored; `calibrate store` rewrote no tracked file).
   - Harness added this round (untracked): probe.py, dcrease.py, partov.py, depth.py, isofill.py, azfit.py, caltry.py,
     caltry2.py, qaonly.py PARTS SRC.., bleedpic.py, bleeddepth.py, clear.py (unreliable: binned jacket fronts), batch.sh
     NAME JSON .. (EXTRA="--parts ...,collar_flags" for loop_end/bleed; ~70-130 s a run), wbatch.sh, setspec.py RUN
     (writes a run's pleat + knot_box into clawd.json's bow, drops knot/end/end_p/drop), tiles.py OUT SRC.. (review
     pictures at 400 px/L: design crops and qa3d.draw of ours), review.py BEFORE AFTER (needs review/summary.json:
     recommended, asked, key_cols, key, checks); `charkit/out/pieceref/review/` has design_*.png, b2_before_*.png (drawn
     before tiles.py's frame fix: redo) and closeup_front.png.

13. **Round 4 (2026-09-30, relaunched lean; coordinator: knot graded front only, w4's shear, bottom .30).**
   - **bow_front_bleed fixed** (f506933): garments.bow_hull `clear` -> `clear_of`: the lobes (panels, strips, almonds;
     not the knot or tails) pushed out along the jacket's normal to >= `gap` L in front of the jacket's rendered surface
     (the 'top' shell rebuilt from `_spec`, subdivided level 1 as it renders: the render sits up to 0.007 L in front of
     the cage under the lobes), by a monotone soft floor (gap + soft log(1 + e^((d - gap)/soft))); the bow's Subdivision
     baked first (`bake`, default; the piece then built with subdiv 0), since clearing the cage left the subdivided
     strip 0.0016 L into the jacket. Harness: `jgap.py SRC` (per-vertex gap by part; at the bleed pixels), `section.py
     SRC X..` (vertical section, env SC/Z0/Y0), `cagecmp.py`, `topcmp.py`, `xbatch.sh NAME CLEAR_JSON..` (w4 + clear).
     The remaining bleed after a normal gap is the view direction: the bust below the lobes' lower edge comes toward the
     camera (slope ~0.6), hiding the outline's lower band, so the gap had to grow past the line's width x that slope.

     | run (w4 + clear) | bleed | piece_bow F/3q/P | lobes F L/R, 3q L/R, P | thick | lean | iso body |
     |---|---|---|---|---|---|---|
     | w4 | 0.25 F | 0.951/0.852/0.685 | .989/.980, .834/.887, .894 | 0.046 W | 4.2 | 0.811 W |
     | x1-x3 cage gap .006/.012 | 0.225/0.105 F | | | | | |
     | x4/x5 limit surface .006/.010 | 0.215/0.105 F | | | | | |
     | x6/x7 baked .006/.010 | 0.208 F / 0.053 W | | | | | |
     | x8 baked .014 soft .004 | 0.028 P | 0.951/0.851/0.685 | .990/.987, .846/.889, .923 | 0.031 W | 2.2 | 0.834 W |
     | **x9 baked .018 soft .004 (default)** | **0.018 P** | 0.952/0.851/0.685 | .990/.989, .847/.895, .923 | 0.030 P | 2.8 P | 0.834 W |

     x9 also: loop_end 0.123 P, knot line/rect P, crease len 0.15 / dir 10.7 P, iso creases P, ribbon 0 P, tail_reach
     0.034 W, hang 0. `xs` (the spec, no sets) reproduces x9 exactly.
   - **bow_part_knot_iou graded on the front only** (2a71baf, step 021a8f0; partqa.GRADED; 3q/profile in the check's
     `info`). Reads 1.0 PASS on x9 (was the worst view 0.0 FAIL).
   - Pregate (f506933's tree): PASS, 0 blocking. Regressions to WARN (not flag, not blocking): body_profile_chest
     0.0023 P -> 0.0438 W (b2_before 0.0023, v0/b2_close 0.0245, w4 and x9 0.0438: the pleat's thinner loops in profile,
     not the clearance), piece_collar_front_bottom 0.028 P -> -0.127 W.
   - pipeline-3d's bow (b2_before) for the review: loop_end 0.121 P, bleed 0 P, tail_reach 0.109 F, hang 12.6 F, thick
     0.076 F, lean 20 F, knot_iou 0.536 W (front), lobe 0.702, knot_line 0.904 F, rect 0.359 F, crease 1.0 F / None F,
     iso body 0.679 F, iso knot line 0.904 F, iso creases F.

   - **The clearance folds** (coordinator's bound reached; db98f8a): every gap tried flips the strips' triangles against
     the bake alone (`flips.py x0 RUN`; x0 = bake, gap -1): x6 110, x7 137, x8 199, x9 297 flipped (z 0.19-0.38 L below the
     bow's top), and in front the lower outer corners read crumpled (x9's tiles, probe_x9_front.png). So the default spec
     is w4 WITHOUT clear (bleed 0.25 FAIL, for the coordinator to judge); `clear` stays a knob. Options: (a) a column push
     (every lobe vertex at (x, z) by one smoothed vector: no squeeze, but the panels' fronts come forward where the strips'
     backs are buried, up to ~0.05 L: the profile); (b) a depth-weighted floor (deep vertices left as they are, only the
     ones within ~0.01 L of the jacket cleared) with a smoothed normal field; (c) the strip built shallower behind the
     panel at its lower edge (step/thin per u), so less is buried. The cause is measured: the strips' backs sit 0.004-0.03 L
     inside the jacket's rendered surface (the subdivided render up to 0.007 L in front of its cage), and the bust below
     the lower edge comes toward the camera, so the outline's lower band needs ~0.015 L clear along the normal.
   - The x9 box build (build-pieceref-0930-210737-312d) was killed when the spec went back to w4.

   - **Box build pr3** (charkit/out/pr3, w4 without clear, db98f8a): shape numbers match the splice (piece_bow
     0.951/0.852/0.685; lobes F .989/.980, 3q .834/.886, P .894; knot F 1.0). Line checks differ from the splice (the
     splice's outline from normals diverges on the pleat's thin parts): knot_rect 0.270 W (splice 0.094), crease_dir
     19.0 W (11.4; ours -56 deg), bleed 0.275 F (0.25), iso crease_dir 16.8 W, iso body 0.810 W.
     **New FAILs against pipeline-3d (block the gate; same in the coordinator's all-in build with clear on):**
     bow_front/three_quarter/profile_torn (outline roughness 0.020-0.035 L vs design 0.0047: the pleat's square corners,
     the sag sliver, the strips' ragged ends), collar_front_torn 0.0031 -> 0.0033 (3 fragments), sleeve_front_spikes_L/R
     0 -> 0.029/0.019; flag regression art_outline_collar 1.379 P -> 2.096 W.
   - Calibration records (856e536, from pr3): CALIBRATED bow_part_knot_line/rect/crease_*, bow_profile_ribbon (rerun,
     remeasured), bow_profile_tail_*/loop_*, iso_bow_body, iso_bow_knot_line, iso_bow_crease_* (4466d2f: pr3's qa.json given the
     un-prefixed iso_bow_* names, as the fixed QA names them); GUARD bow_part_lobe_iou; **BLIND bow_part_knot_iou**
     (front only, the known-bad g3_render3's front knot reads 0.467 WARN).
   - Tests ok (partqa, isoqa, spec_alias, manifest); pregate 3ae7e5e into 640ca7c PASS, 0 blocking. **Gate FAIL**
     (493cad7 into 640ca7c, charkit/out/gate/gate_tool-pieceref_493cad7_into_640ca7c.md), 10 blockers: art_outline_collar
     (flag) 1.379 P -> 2.096 W; new FAILs bow_front_bleed 0.275, bow_front/3q/profile_torn, collar_front_torn,
     sleeve_front_spikes_L/R; the 2x2's bow_profile_ribbon under the old measure 0.053 P -> 0.553 F (the close-hung bow,
     option C's reason; new measure 0 P); bow_part_knot_iou's record BLIND.
   - Fixes for the coordinator's findings: isoqa lost its doubled part prefix (17106263: the box named them
     iso_iso_bow_*); QA part orders unique (e9319b8: bow_profile 1767, bow_parts 1772, iso_pieces 1776; with tool/hands
     merged (merge-tree) the registry loads, 31 parts, no shared orders); pipeline-3d 640ca7c merged (e9a670a);
     clawd_body_pieces.json = clawd.json (3ae7e5e, test_spec_alias ok). tool/sleeves conflicts with this branch in
     collarqa.py and steps/collarqa.py (textual; the coordinator's merge).
   - Review page: `charkit/out/pieceref/review/index.html` (review.py b2_before_res pr3 x9; summary.json).

14. **Round 5 (2026-09-30, relaunched lean; coordinator: accept bow_profile_ribbon, recalibrate the knot IoU by
   tightening, attribute and fix the real regressions, the bleed without folds or named acceptance).**
   - pipeline-3d 342e88c (tool/face5) merged (ed29b131, clean).
   - **bow_part_knot_iou recalibrated by tightening** (480f0a19, step 1821836c, record CALIBRATED): its own lines
     `LIMITS['knot_iou']` (0.9, 0.7), was the lobes' (0.6, 0.45). Ladder (`harness/kcal.py`, kcal.json): at the grid's
     212.5 px/L the drawn knot is 18 x 25 px against iou_tol's 4.25 px band, so it reads placement, not shape (x1.5
     wide, an ellipse in its box, scaled 0.8-1.2: all 1.0; knot_rect and knot_line carry shape). The design moved 1-4 px
     0.94-1.0, 5 px 0.833, 6 px 0.621; pr3 1.0; pipeline-3d's knot (b2_before, b2_close) 0.536 and g3_render3 0.467
     FAIL now (WARN before: the blind record). Test test_the_knot_is_graded_on_tighter_lines.
   - **Attribution by swapping the bow** (`harness/swap.sh`, `swcmp.py`; splices on pr3's bundle): pipeline-3d's bow
     spliced into pr3 (sw_old) reads every blocker at the base's value (bow torn 0.0003/0.0011/0.0, collar_front_torn
     0.0031, spikes 0/0, bleed 0, art_outline_collar 0.731 P), w4 spliced back (sw_w4) the candidate's: **the bow
     carries all of them** (garments.py's branch changes are bow-only).
   - Where (`harness/torndiag.py SRC`: the torn masks at 3x with the bow by connected part; rough pixels by surface,
     holes, knock-outs; `torn_SRC_*.png`): front (0.0202 L; holes filled 0.0078, knot knocked out 0.005): a hole under
     the knot (the tails' tops start TAIL0 = 0.08 sizes under the centre, the fitted knot's bottom 0.0625: the jacket
     shows through) and gaps by the knot's rounded corners (where the collar shows: collar_front_torn's 3 fragments);
     three-quarter (0.0254; filled 0.0255): a thin hole between the near tail and the strip and notches where the tails'
     outer edges meet the lobes' lower edges; profile (0.0353; strip L knocked out 0.0067): a see-through slit between
     the tails and the strip's `hang`. `depths.py SRC`: the tails' backs 0.012-0.033 L behind the knot's front, the
     strips' fronts 0.030-0.036 (a gap up to 0.04 L lower down).
   - Sleeve spikes (`spikediag.py`, `corner.py`): our lobes' upper outer corners sit where the drawn ones are (rows
     407 vs 406, outermost 84 vs 81 px; the pillows' were 6 px lower and 7 px in), but our sleeves' caps sit 13 px
     (0.06 L) lower than drawn (top row 394 vs 381), so the corner bites 7 px into the sleeve's inner top edge and
     leaves a horn there that borders background (the design's: 3 px, collar round it).
   - Variants (`fix.sh NAME --set ..`: var.py on pr3 with every affected part, then torndiag; `fixcmp.py RUN..`):
     h0 hang off: profile torn 0.0101, 3q 0.0706 (worse); h1 hang off + x0 .03: front 0.0086, collar_front_torn
     0.0016 P but knot_line 0.64 F. New knobs (off unless set): `ribbon.root` (the tails' tops carried up behind the
     knot), `ribbon.back` (L: the tails' tops set back toward the loops), `pleat.tuck` [sizes, u-width] (the strip's
     lower half forward by the knot), `clear.mode 'column'` (`clear_column`: the lobes moved toward the camera by one
     smoothed offset per column, measured at the lower rim against the jacket's rendered front `below` under it).
     Also `pleat.strip_ov` (the strip's top higher behind the panel; the panel's edge kept). Committed 6671831d with
     tests (test_bow_pleat.py: root rows inside the knot and nothing else moved, tuck, strip_ov).

     | run (splice on pr3; w4 +) | bow torn F/3q/P | collar_front_torn | knot iou/rect | piece_bow F/3q/P | lobes F L/R, 3q L/R, P | iso body |
     |---|---|---|---|---|---|---|
     | sw_w4 (= pr3) | 0.0155 F/0.0207 F/0.0306 F | 0.0033 F (3 frag) | 1.0 / 0.270 W | 0.951/0.852/0.685 | .989/.980, .834/.887, .894 | (0.810 box) |
     | t1 root .08 (unpinned) | 0.0031 P/0.0229 F/0.0384 F | 0.0018 W | 0.6 F / 0.404 F | same | | 0.772 |
     | t2 t1 + tuck [.04,.3] | 0.0031 P/0.0228 F/0.0 P | 0.0018 W | 0.6 F / 0.404 F | same | | 0.772 |
     | t4 root pinned + tuck | 0.0031 P/0.0228 F/0.0 P | 0.0018 W | 1.0 / 0.270 W | same | .989/.980, .838/.887, .894 | 0.799 W |
     | t6/t7 strip_ov .04/.07 alone | 0.0153 F/0.0153-0.013 F/0.03 F | 0.0033 F | | same | | 0.81 |
     | t8 t4 + strip_ov .07 | 0.0042 W/0.0037 P/0.0 P | 0.0018 W | 1.0 / 0.270 W | 0.951/0.853/0.685 | .989/.980, .839/.889, .897 | 0.800 W |
     | **t9** root .155 + tuck + strip_ov .07 | **0.0015 P/0.0037 P/0.0 P** | **0.0017 P** (0 frag) | 1.0 / 0.294 W | 0.951/0.853/0.685 | .990/.980, .841/.888, .897 | 0.792 W |

     t9 also: knot_line 0 P, crease len 0.23 P / dir 16.4 W, loop_end 0.123 P, thick 0.042 W, lean 4.5 P, hang 0 P,
     reach 0.033 W, ribbon 0 P. (zsh doesn't split an unquoted variable: pass sets literally or via `batch5.sh`, bash.)

   - **Corners, the bleed, the knot's ring (round 5's end; coordinator: stop compensating in the bow).**

     | run (on t9 unless said) | sleeve spikes L/R | art_outline_collar (flag) | loop_end (flag) | bleed (flag) | other |
     |---|---|---|---|---|---|
     | t9 | 0.0286 F / 0.0188 F | 2.096 W | 0.123 P | 0.2775 F | |
     | r1 rounder upper corner (end_p [2.5,1.4]) | 0.0188 F / 0 P | 2.091 W | **0.242 W** | | collar_3q_torn 0.0084 F |
     | r2 top .22 | 0.0235 F / 0.0133 W | **0.731 P** | **0.163 W** | | piece_collar F 0.655 -> 0.573 |
     | c1 clear column gap .015 | | | | **0.0 P** (0 flips) | lobes F .92/.92, 3q .78/.86, P .84 (-6..-8%); piece_bow P 0.651; offsets 0.07-0.08 L at mid-lobe: the loops balloon off the chest in profile, streaks across the lower lobes (427 tris turned > 45 deg) |
     | c2 c1 + ramp .08 | | | | 0.0 P | 243 flipped |
     | c3/c4 c1 + cover | | | | 0.0125 P / 0.045 W | 327/323 flipped, torn back to F/W |

     The knot's ring (`harness/knotring.py SRC`: the share of the knot's edge, per side, with a line beside it, front,
     line_picture): pr3 1.0; t9 0.767 (bottom 0.5); t10 (t9 + root_seat 1) 0.642; t11 (root behind the knot's back
     0.006 L + seat 1) 1.0 but collar_front_torn 0.0031 F, front torn 0.0051 W, knot_line 0.164 W; t12 (seat 0.5) 0.983
     (bottom 0.917), torn all P, collar_front_torn P, knot_line 0.179 W, tail_reach 0.043 W. The root fixes the torn
     edges but costs the knot's outline (pinned at its centre depth it hides the back half of the knot's outline shell;
     behind it, the tails' turned top row still covers the knot's lower line). Neither met the coordinator's bar (torn
     and collar cleared with the knot lined all round 1.0 and the guard intact): **the default spec stays w4 (pr3) as
     drawn**; the knobs stay in code, off (6671831d, and the root_back/root_seat/cover commit).

     **Attribution of what remains (for the coordinator):**
     - bow_front/three_quarter/profile_torn, collar_front_torn: **bow-caused** (the pleat's junctions: a hole under
       the fitted knot, gaps by its rounded corners where the collar shows, slits between the tails and the strips).
       A fix exists (t12: root .155 behind the knot, seat .5, tuck [.04,.3], strip_ov .07: all four PASS, guard up)
       at the cost of knot_line 0 -> 0.18 WARN and the ring 1.0 -> 0.983.
     - bow_front_bleed: **bow-caused** (the strips' lower rims buried in the bust, which comes toward the camera under
       them). The non-folding column push clears it but moves mid-lobe 0.08 L forward (c1): named acceptance.
     - sleeve_front_spikes_L/R: **neighbour off-design**: the lobes' upper outer corners sit where drawn (1-3 px), our
       sleeve caps 13 px (0.06 L) lower than drawn, so the corner bites 7 px into the cap's inner top and leaves a horn.
     - art_outline_collar (flag): **neighbour off-design**: the lapels reach out to the lobes' upper outer corners
       (drawn, they end inside the bow's top), so the collar region's outline turns a corner there (front: 3 corners
       against the pillows' 1). Lowering the bow's corners clears it (r2) but regresses loop_end (flag).

   - pipeline-3d 961037c (tool/hair5) merged (f08882b6; prompts.json and tools/ledger.jsonl: both sides kept).
     Tests ok (bow_pleat, partqa, isoqa, bowqa, collarqa, outfit, manifest, spec_alias, registry, gate); pregate
     a2d0bd11 into 961037c PASS, 0 blocking.
   - **Gate FAIL, 8 blockers** (f08882b into 961037c, `--accept bow_profile_ribbon`;
     charkit/out/gate/gate_tool-pieceref_f08882b_into_961037c.md): exactly the attributed set: bow_front/3q/profile_torn
     0.0155/0.0207/0.0307, collar_front_torn 0.0033, bow_front_bleed 0.275 (bow-caused); sleeve_front_spikes_L/R
     0.0286/0.0188, art_outline_collar 1.379 P -> 2.096 W (neighbours off-design). The 2x2 accepted; bow_part_knot_iou
     a calibrated new check, 1.0 PASS. Not blocking: body_profile_chest, collar_three_quarter_torn,
     sleeve_three_quarter_spikes_R PASS -> WARN. **Build CPU 1.49x** (737 -> 1102 s): at K's 1.5x bound.
   - Review page `charkit/out/pieceref/review/index.html` (review.py b2_before_res pr3 t12; summary.json): w4 kept,
     the attribution with pictures, the options measured and not taken (t12, c1, r1/r2), the three questions.

   - **Coordinator's decision (round 5's end; Michael may switch it): land the measurement, hold the geometry.**
     0cfac70a: `garments.bow_spec` resolves `pleat.on`; the default spec (clawd.json = clawd_body_pieces.json) has the
     close-hung pillow bow on (Michael's choice, as at 2dc325a: knot 0.6, end 0.2, end_p [4, 1.4], drop 0.2, ribbon
     turn 20, w [0.204, 0.338]) and the pleated bow OFF: `pleat` {on: false, w4's keys, tuck [.04,.3], strip_ov .07,
     knot_box [.10,.09,.145,.02], tails {root .155, root_back .006, root_seat .5}} (w4 + t12 behind one switch; test
     test_one_switch_turns_the_pleated_bow_and_its_fixes_on_together). The measurement lands: partqa/isoqa/bowqa's
     checks and records, bow_profile_ribbon's remeasure (accepted), bow_part_knot_iou on its tightened lines. On the
     current bow the new bow_part_*/iso_* checks read FAIL (reported, new checks). Close-hung pillows' own readings from
     round 2's box build b2_close (for the gate's reader): bow_front_bleed 0.205 F and bow_front_loop_end 0.244 W were
     its values there (pipeline-3d's bow 0.0 P / 0.121 P): if the batch gate shows them, they are the close-hung
     option's, not this round's.
   - pipeline-3d de2fa87 (tool/hands) merged (59ce8f96; prompts.json: both kept). The coordinator gates this branch
     in a batch with tool/face6 and tool/sweep (no gate of mine this round).

## The garments round's plan (coordinator)
Turn w4 + t12 on (`pleat.on: true`) in the same gate as the neighbours' placement fixes, so the bow's corners meet
pieces placed as drawn:
1. **The collar's lapels** end inside the bow's top edge as drawn (now they reach out to the lobes' upper outer
   corners: art_outline_collar 1.379 -> 2.096 W, 3 corners in front against 1).
2. **The sleeve caps** 0.06 L higher (our top row 394 against the drawn 381 at 212.5 px/L): the bow's corner then no
   longer bites the cap's inner top (sleeve_front_spikes_L/R 0.029/0.019 F).
3. **The bust/loop contact behind the bleed** (bow_front_bleed 0.275 F): the strips' lower rims buried in the bust,
   which comes toward the camera under them; the non-folding column push (`clear` mode 'column', c1) clears it but
   moves mid-lobe 0.08 L forward. Bring the strips' rims out of the bust at the source (their step behind the panel
   smaller toward the outer half) and push only what remains, or shape the bust/jacket under the loops.
4. With t12 on: the bow's torn checks and collar_front_torn PASS (splice t12); the knot's lower line still thin
   (knotring 0.983, bow_part_knot_line 0.18 W): the tails' turned top row stands in front of the knot's bottom (try it
   un-turned, the turn eased in over the first tenth). Build CPU sat at 1.49x with w4 on.
tool/sleeves (paused) conflicts with this branch in collarqa.py and steps/collarqa.py.

## Round 3's next steps (done but as noted in State 13)
1. **bow_front_bleed on w4** (flag; baseline b2_before 0.0 P: must PASS, <= 0.03): add u (along the lobe) to
   bleeddepth.py's touching pixels to confirm where; then try, one knob at a time with collar_flags in EXTRA: the strip
   ending earlier or closing sooner (`close` .3-.4), `tilt` 2-3, the strip's step smaller only toward the end; or the
   lobes' outer bottoms held off the jacket (bow_hull `conform_k` < 1, or a new per-vertex stand-off ramped over the
   outer half). Keep w4's other numbers (loop_end <= 0.15, thick <= 0.05, iso body >= 0.75) and the guard (piece_bow and
   every part's IoU per view within 15% of v0's, table above).
2. `python setspec.py RUN` (the pleated bow into clawd.json, pillow knobs out), commit; `python -m charkit pregate`
   (background).
3. Box build `python -m charkit remote build charkit/spec/clawd.json --out charkit/out/pr3` (background); calibration
   records on it: `python -m charkit calibrate 'bow_part_*,iso_bow_*,bow_profile_*' --build charkit/out/pr3` (adapters
   charkit/calib/parts.py: BowParts, IsoParts, BowProfile; labels.py's ribbon_line patch covers bow_profile_ribbon,
   whose record is for the old measure: rerun it too); commit charkit/calib/records/*.json.
4. Review page (tiles.py on b2_before and pr3, then review.py with summary.json), gate
   `python -m charkit remote gate tool/pieceref --into pipeline-3d`.
5. Decisions for Michael (put on the page): (a) bow_part_knot_iou graded on the front only (the turnaround's 3q knot is
   drawn as if face-on: azfit), 3q/profile reported? (b) the loops' ends: the close-up's square ends (iso body) against
   the turnaround's slanted ones (loop_end, his flag): w4's shear .15 the compromise; (c) the profile draws the loops
   27% taller than the front (0.448 against 0.353 L): bottom .30 the compromise (loop_thick WARN).
6. If room: the cuffs and boots in isoqa. Not the collar, sleeves or accessories (paused, Michael).
