# Workstream: hands (tool/hands)

Worktree `~/animation-pipeline-hands` (sparse charkit profile), branch `tool/hands` from pipeline-3d ccc9552, merged
pipeline-3d 004efc3 (tool/calib) at 8009443. Brief: coordinator, 2026-09-30 (round 1). Plan (Michael, 2026-09-30;
skeletal, not shape keys), docs/ROADMAP.md item 7:
1. Measure first. 2. The hand breakdown reference (paid, approved). 3. A hand template replacing the mitten.
4. Weights on the VRM finger bones. 5. A `hands` expression component (pose library). 6. QA per pose.

## State
- **Step 1 done (ee2eca7):** `charkit/handqa.py`, QA part `hands` (order 1770, prefix `hand_`). A hand = the skin past
  its wrist cuff (the drawn `cuff_L/R` masks; ours: the cuff's object via the piece map), measured alike on both sides:
  - `hand_shape_{L,R}`: IoU laid on centroids per view (`views`: the guard's shape), worst view; PASS >= 0.75, WARN >= 0.6
  - `hand_{view}_reach_{L,R}`: reach past the cuff, ours - design (L); PASS 0.04, WARN 0.08
  - `hand_{view}_digits_{L,R}`: digits across the fingers (runs + interior seams at 55-90% of the reach, median over
    bands; design: its ink; ours: shell changes or depth steps > 0.012 L); PASS within 1 with ours >= 2; only where the
    design shows >= 2
  - `hand_{view}_cleft_{L,R}`: deepest convex-hull pocket, ours / design; PASS 0.6-1.67, WARN 0.4-2.5; only where the
    design's >= 0.03 L (3q R has 0.015: not drawn)
  - 22 checks. Calibration adapter `charkit/calib/hands.py` (Hands, on labels.Garments): floors `stub_hands` (cut at
    35-60% of the reach) for shape and reach, `blob_hands` (moment-matched ellipse) for digits and cleft, probe
    `blob_hands` on shape (it PASSes the shape IoU 0.81-0.91: a matched blob is a fair silhouette in profile; the digits
    check is the finger structure's). Known-bad `mitten` (pipeline-3d 1580f95's preview build, stored in
    charkit/out/calib/builds/mitten). Dry run against the mitten as current: all 22 CALIBRATED.
- Design numbers: reach 0.59-0.62 L past the cuff; digits front 3, 3q 4, profile 4, back 2; cleft 0.054-0.088 L.
- Mitten: reach 0.21-0.25 (FAIL), shape 0.27-0.48 (FAIL), digits 1 (FAIL), cleft ratio 0.07-0.35 (FAIL).
- **Step 2 done:** `charkit/refs/clawd/gen/hand_breakdown.png` (candidate 1 of 2; gpt-image-2.5-sunburst 2560x1440
  high, n=2, one call, ledger in the main checkout), manifest entry `hand_breakdown` (sha256 in provenance: a top-level
  one restamps every produced reference), prompt in prompts.json. Refcheck (`python -m charkit.handref --build BUILD
  SHEET`): relaxed back ~ profile_L IoU 0.839, relaxed side ~ front_L/R 0.725/0.739, ~ back 0.71-0.72, ~ 3q_L 0.64;
  digits 4/4 and 3/3; cleft 0.055/0.054. Caution: its hands reach 16-19% further past the cuff (0.68-0.73 vs 0.59-0.62).
  Candidate 2 (charkit/out/hands/gen/hand_breakdown_2.png): 0.75 / 0.70-0.72.
- **Step 3 (template), step 4 (weights): built, fitting.** `charkit/code_hand.py`: palm (rounded box), thumb and four
  fingers as capped ring tubes (separate shells, like the body's limbs), joint loops either side of each knuckle, rounded
  tips; knobs in the spec's `body.hand` over `code_hand.DEFAULT`; `python -m charkit.code_hand fit --build B --spec S
  [--write S]` fits them to the drawn hands (handqa's measures: IoU turned to the drawn arm and on centroids, reach past
  our cuff's far edge = the spec's wrist band end, ~0.003 L past the wrist), Powell within anime BOUNDS (an unbounded
  coordinate search drove it to a 0.13 L thick untapered paddle at IoU 0.64-0.70: no hand). Weights by construction
  (each digit's rings on Hand / its 3 bones, eased over 0.8 of the radius across each knuckle); joints from the template
  (code_body._joints). Wired: bodypage.save_body (the arm's tube cut at the wrist, `hand_*` arrays), cli.code_body's
  cache key (body.hand, charkit.code_hand), code_body.build_body_data (hand parts, UV band v 0.1-0.2 under the legs, the
  feet's slots halved to v 0-0.1; weight chunks now summed). Venv test: 49 bones weighted (all 30 finger bones), sums 1.
- handqa change (before any record): hand_shape turns ours to the drawn arm's direction before the centroid IoU (the
  arm's angle is the build pose's: body_*_arms INFO, ours 17 deg vs 19).

- **Fitted knobs (5d18d38, in charkit/spec/clawd.json and the clawd_body_pieces alias):** length 0.654, palm 0.47,
  palm_w 0.199, wrist_w 0.174, palm_t 0.083, finger_w 0.056, taper 0.68, spread 1.1, curl 7.1, thumb_len 0.25,
  thumb_out 5.4, thumb_down 5.1, yaw 61.9, bend -1.0, dev -3.1. Joint fit (charkit/out/hands/fit4.log): IoU front
  0.744/0.754, three-quarter 0.687/0.722, back 0.736/0.731, **profile 0.50**; reach errors <= 0.006 L.
- **The drawn views disagree on the hand's turn (the standing rule):** a yaw scan (charkit/out/hands/yaw_scan.py) at
  the fitted shape: yaw 0 (the back of the hand to her side, as the hand sheet reads the profile) gives profile 0.71,
  front/back 0.34-0.36; yaw 62 gives front/back 0.73-0.75, profile 0.50. No one turn fits both: the turnaround draws
  the hand broad-on in front and in profile (view-dependent, anime convention). Step 1 (ours?): every shape freedom
  opened, no. Step 2: the hand sheet is the isolated reference; it reads the profile as the back of the hand. Step 3:
  the base takes the joint best fit (yaw 62) with per-view costs; the turn is a forearm twist, so a shot can override
  it (the pose library's wrist). **Michael's call:** A (the joint fit, broad to the front) or B (palm to the thigh,
  as the hand sheet and anatomy read it: profile 0.71, front 0.35).
- **Fist pre-check (code_hand.fist_report, linear blend skinning in numpy, fitted knobs):** at 80 deg per finger joint
  the knuckle loops keep >= 0.77 of their rest section area (LBS's loss at a 80 deg bend; the thumb 0.94 at 40);
  neighbouring fingers overlap 0.5-3.3% of their ring points, deepest 0.006 L. Correctives at the knuckles only if
  round 2's numbers on the built rig ask for them.
- Tests: the suite passes (test_spec_alias needed body.hand in the alias: ef298e0).
- **Box build b1** (render box, boards body,design): `charkit/out/hands_b1`, log charkit/out/hands/b1.log, launched
  2026-09-30 evening; if the command died, `python -m charkit remote attach JID` (the id is in the log's start).
- Watch: the skirt has `clear_hands: 0.05` (it clears our hands): the new hands can move the skirt's shape near them.

## Local harness (charkit/out/hands/)
- `produce.py` (hull and masks produced locally), `run_handqa.py BUNDLE [OUT]`, `write_qa.py BUILD [QA]` (adds the
  hand checks to a build's qa.json for calibrate), `dbg_digits.py`.
- `charkit/out/calib/cur_mitten`: the mitten bundle (hard links) + a qa.json with the hand checks, for the dry run.

## Box build b1 (5d18d38 + ef298e0, render box, `charkit/out/hands_b1`, landed 2026-09-30 night)
Compared with 004efc3 (the mitten build's qa.json with the batch gate's candidate rows: charkit/out/hands/compare_b1.py).
- **Hand checks (22):** 13 PASS, 6 WARN, 3 FAIL. hand_shape_L FAIL: front 0.747, 3q 0.623, profile 0.500, back 0.718;
  hand_shape_R FAIL: front 0.774, **3q 0.207**, back 0.733. Reach -0.03 to -0.06 L (PASS/WARN; the mitten -0.35 to
  -0.38). Digits PASS except back_L WARN (+2) and **three_quarter_R FAIL (-3)**. Cleft all PASS (1.05-1.61). The far
  hand in 3q (R) reads worst: the fit had it at 0.72 alone; check what our 3q z-buffer cuts it to (the skirt, the cuff).
- **Non-hand checks moved (the K blockers to clear before the gate):**
  - **art_bumps_legs PASS -> FAIL (0 -> 118.5): a flag check, blocks.** Probably the fingertips near the thighs read as
    leg bumps (the hands now reach 0.65 L, the mitten 0.25), or the skirt's clear_hands moving; look at its overlay.
  - **body_three_quarter_skirt_aline WARN -> FAIL (0.08 -> -0.313): a new FAIL, blocks.** body_front_skirt_width
    PASS -> WARN (0.984 -> 0.866); hemband_skirt_step 0.052 -> 0.223; shape_iou_skirt 0.876 -> 0.867; art_bumps_skirt
    24.0 -> 7.5; piece_skirt 0.893 -> 0.899. The skirt's `clear_hands: 0.05` now clears the longer hands (and the
    aline/width rows exclude rows "a hand touches": the longer hands remove rows from those measures). Fix options for
    round 2: the skirt's hand clearance against the hand's real surface (or off where the hand hangs in front), and
    bodyqa's hand-row exclusion read again for real hands.
  - Improved: cuff flare front L/R WARN -> PASS, back R FAIL -> PASS.
  - body_*_iou_skin: front 0.738 -> 0.720, back 0.759 -> 0.740, profile 0.725 -> 0.731, 3q 0.727 -> 0.729 (the arms' angle
    body_front_arms -2.0 -> -3.4: the hands' mass out past the drawn arm line); piece_cuff_L 0.733 -> 0.722, _R 0.586 ->
    0.583 (noise-level); body_front_iou 0.884 -> 0.876, body_back_iou 0.896 -> 0.888.
- Decision routed by the coordinator: the hand's turn goes to Michael with recommendation A (the joint fit); round 2
  proceeds on A unless he says otherwise.

## Round 2 (2026-09-30, relaunched lean; Michael chose hand rest A, the joint fit, as the default)
Merged pipeline-3d 3f7b730 (879b387). Harness (charkit/out/hands/, local): ink.py (the hands drawn with their screen
lines at the sheet's scale, fill share vs the design; --k simulates an outline weight), occl.py (what hides each hand),
geomview.py (the skin's hand geometry per bundle variant, back faces blue), evalab.py (the local evaluator on spec
variants: `evalab.py NAME '{"path": value}'`, ~150 s), legbumps.py, tips.py, alinerows.py.
- **b1's hands rendered broken (found on the boards, not in any check): fixed a1bbeb7.** The right hand was inside out
  (its frame is mirrored, so its rings ran the other way: the outline hull went inside the skin, no line, a fat pale
  hand); the left folded over at every knuckle (the knuckle loops' averaged frames were right-handed between its
  left-handed segment frames: knobs with back faces showing). Tests: charkit/tests/test_code_hand.py.
- The skin's screen-width outline (0.0022 of the page, ~0.0034 m at full figure; no cap on the skin) moves each
  finger's visible surface inward by the whole width: fingers 0.014 m wide lose half to ink. ink.py on b1's left hand:
  fill share ours/design 0.73 (front), 0.75 (3q), 0.75 (profile); an outline weight of 0.5 on the hand gives 0.84 /
  0.76 / 0.83, 0.3 gives 0.90 / 0.78 / 0.87 (the knobs stayed: geometry, now fixed). Decide after the next build.
- **art_bumps_legs is the fingertips, not the skirt:** every leg bump sits on row z = -2.631 L, the fingertips just
  under LEG_TOP (-2.62). Ours hang to -2.64/-2.65 in front/back, the design's to -2.585 (3q L -2.632, profile -2.665:
  the drawn views disagree by 0.08 L); the design's 3q value 88.4 is its own fingertip. The 2x2 means a remeasure
  can't escape it (the old measure on the new geometry regresses): the fix is placement.
- **The 3q skirt aline is not the clearance:** clear_hands off changes nothing (-0.313 both; IoUs +0.003). The design's
  3q rows are all "a hand against it" (aline falls back to all rows); ours leaves 52 rows free because our far hand
  (R) is 63% hidden behind the skirt in 3q (occl.py), so a few odd rows decide it. Same cause as hand_shape_R 3q 0.21.
- Our arms hang steeper than drawn (body_front_arms: ours 15.5 deg shoulder to hand, the design 18.3-19.0). pose.arm_down
  is MakeHuman's: the code body ignores it (evalab arm8/arm6: no check moves); our arm is the hull's chain. Near the
  cuff (handqa.arm_axis) the drawn forearm is 28.2-28.6 deg off vertical in front/back, ours 22.5; the drawn hand
  flares 4.3-5.6 deg past its forearm, ours -0.4..-0.9 (tips.py).
- **Placement fix (09ddfa2): body.hand.out 5.5** (the hand turned out in her frontal plane at the wrist, matching the
  drawn flare past the forearm). Fit.score (outscan.py, folds fixed): IoU front 0.736/0.743 -> 0.750/0.753, 3q
  0.695/0.718 -> 0.712/0.762, back 0.729/0.740 -> 0.747/0.750, profile 0.503 -> 0.507; reach errors <= 0.024 L.
  Fingertips -2.631/-2.620 -> -2.608/-2.597 L (above LEG_TOP). The forearm's own 6 deg is the hull's (not this
  workstream): out 11 would match the drawn absolute angle (tips -2.58) at a 6 deg excess flare on our forearm.
- **Line (09ddfa2): body.hand.line 0.5** (character.outline_weights: the hand's outline at half the skin's).
- **handqa (09ddfa2, step registered 44b05dd):** our_hidden; a partly hidden hand's shape is graded over what shows,
  with `visible` and `whole` beside it; digits/cleft INFO below 75% visible. On b1: hand_shape_R 3q 0.207 -> 0.372
  (visible 0.369, whole 0.629: the far hand is both hidden and drawn broader than ours shows edge-on).
- **Box build b2** (a1bbeb7 + 09ddfa2 + 44b05dd: folds/winding, out, line): `charkit/out/hands_b2`, log
  charkit/out/hands/b2.log (render box, boards body,design).

## Next steps (exact)
1. Clear the two K blockers above (art_bumps_legs, body_three_quarter_skirt_aline) and the 3q R hand; rebuild.
2. Calibration records: copy b1 to `charkit/out/calib/cur_hands` (hard links + its qa.json), then
   `python -m charkit calibrate 'hand_*' --build charkit/out/calib/cur_hands` (writes charkit/calib/records/hand_*.json);
   commit them. The dry run against the mitten: all 22 CALIBRATED.
3. Review page: `python charkit/out/hands/review.py charkit/out/calib/builds/mitten charkit/out/hands_b1 OUT` makes the
   tiles (design | mitten | ours per view and side, the checks' grid scale) and rows.json; write OUT/index.html with the
   summary box (Recommended: A, the joint fit; Asked of Michael: A or B on the hand's turn; Key numbers), the generated
   sheet (charkit/refs/clawd/gen/hand_breakdown.png) with refcheck_hand_breakdown_1.png, and open it.
4. `python -m charkit pregate`, then `python -m charkit remote gate tool/hands --into pipeline-3d` (export
   CLOUDSDK_CONFIG=$HOME/.config/charkit/gcloud). Merge pipeline-3d first if it moved.
5. Round 2: the `hands` expression component (relaxed, fist, open, point; per finger curl, spread, thumb opposition;
   per hand, blendable) on the modular expression API (charkit/expressions.py, the mouth/eyes/brows presets), using
   code_hand.curl_pose's joint convention (bend about along x -dorsal); grade per pose against hand_breakdown
   (handref.sheet_hands gives each cell's hand at the turnaround's scale; the fist's digits/cleft); fist QA on the built
   rig (interpenetration, knuckle area) -> correctives only if asked.
