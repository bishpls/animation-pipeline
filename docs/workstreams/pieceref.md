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

Not done: the bow close-up generation (no paid call made yet), the bow fix, loop_end / bleed, the review page, the
gate, the cuffs and boots.

## Next steps, in order
1. **Tests for isoqa** (synthetic five-cell bow: ref_piece's naming, compare reads itself scaled and moved). Run
   `python -m pytest -q charkit/tests/test_partqa.py charkit/tests/test_collarqa.py charkit/tests/test_outfit.py`.
2. **The bow close-up** (Michael approved; one call, n=2): the bow ALONE, front, three-quarter (turned to the
   viewer's left) and side (facing left), knot and each lobe's crease clear, one scale, orthographic, white ground;
   inputs body_turnaround and garment_breakdown (the turnaround first: its proportions are the ones to keep; the
   breakdown's knot is 33% wider). Prompt in `charkit/refs/clawd/gen/prompts.json` (key `bow_closeup`, the existing
   `bow_detail` prompt's style); `~/animation-pipeline/.venv/bin/python tools/gptimage.py "PROMPT" OUT.png --size
   2560x1440 --quality high --ref charkit/refs/clawd/gen/body_turnaround.png --ref
   charkit/refs/clawd/gen/garment_breakdown.png --n 2` (it logs to tools/ledger.jsonl itself; it reads the key from
   `~/animation-pipeline/.env`, so run it from the main checkout's tools with OUT an absolute path in this worktree,
   or copy the script's call). Refcheck both with `isoqa.compare` against the turnaround's front, three-quarter and
   profile bow (design_piece for each view); register the better one in the manifest (provenance, cautions, sha256,
   `pieces` boxes per view) and, if it beats the breakdown's 0.76, make it `shape_bow` and grade body / tails / knot
   size (then calibrate them: the reference moved and scaled PASS, b2_close's pillows FAIL?). Existing unregistered
   `~/animation-pipeline-refs2/charkit/out/refs2/gen/bow_detail_1|2.png` (the bow on a bust, five views, 2026-09-29,
   paid): refs2 rejected them (bust 0.74 against the sheet); the bow is ~350 px wide there: usable for a three-quarter
   and side refcheck if the new call fails.
3. **Fix the bow** (charkit/garments.py `_bow_mesh`, `bow_hull`; knobs in clawd.json): trapezoid lobes (the `wing`
   branch is a bow tie's wing: start there) with a real crease fold the outlines draw (an overlapping pleat: the
   lobe's upper face folded over its lower along the crease from the knot's lower corner toward the lower outer
   corner, standing proud enough that its edge is a silhouette: inverted hulls draw silhouettes only, not valleys or
   ridges); the knot as its own object or at least its own outlined part standing in front of the lobes (the drawn
   knot 0.085 x 0.118 L, aspect 1.39, fill 0.98; ours 0.1275 x 0.1575); visible in profile between the lobes. Fit to
   the isolated references for shape and lines (iso_*), to the turnaround for placement (bow_part_*), with piece_bow
   and every part's IoU in all views reported beside (the anti-gaming guard). Harness: bow2's
   `~/animation-pipeline-bow2/charkit/out/bow2/harness/var.py` (splices an evaluator bow into a box bundle; copy it
   here, point WT at this worktree; its splice zeroes the outline shrink, so bow_front_bleed and anything read with
   lines is only right on box builds: run `python -m charkit remote build` for those).
4. `bow_front_loop_end` (flag, 0.121 P -> 0.244 W with drop 0.2: retune `end_p` [upper, lower] with drop, e.g. the
   lower corner rounder [4, 1.0-1.2]) and `bow_front_bleed` (0.205 FAIL on b2_close, reproduces locally on the box
   bundle: `harness/ribcal.py b2_close`; locate with a picture like `harness/ribpic.py` in front: the dropped loops'
   lower corners or the closer ribbons' outer edges).
5. Review page (summary box first: Recommended / Asked of Michael / Key numbers; design and the isolated reference |
   before (b2_before) | after, per sub-piece numbers), pregate, box build, gate
   `python -m charkit remote gate tool/pieceref --into pipeline-3d`. Expect under K: bow_part_* and iso_* are new
   (FAILs reported, not blocking); bow_profile_ribbon is a remeasure (registered); bow_front_bleed FAIL is new against
   pipeline-3d's 0.0 PASS (blocking until item 4 fixes it); bow_front_loop_end WARN is a flag regression (blocking).
6. If room: the cuffs and boots in isoqa (boxes on the breakdown; cuffs also on sleeve_closeup). Not the collar
   (tool/collar4), the puffs (tool/sleeves, paused) or the clips (tool/accessories2).
