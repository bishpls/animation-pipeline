# Workstream: hands (tool/hands)

Worktree `~/animation-pipeline-hands` (sparse charkit profile), branch `tool/hands` from pipeline-3d ccc9552, merged
pipeline-3d 004efc3 (tool/calib) at 8009443. Brief: coordinator, 2026-09-30 (round 1). Plan (Michael, 2026-09-30;
skeletal, not shape keys), docs/ROADMAP.md item 7:
1. Measure first. 2. The hand breakdown reference (paid, approved). 3. A hand template replacing the mitten.
4. Weights on the VRM finger bones. 5. A `hands` expression component (pose library). 6. QA per pose.

## State
- **Step 1 done (ee2eca7):** `charkit/handqa.py`, QA part `hands` (order 1785, prefix `hand_`; was 1770, which tool/pieceref's bow_parts also took). A hand = the skin past
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

### Box build b2 (a1bbeb7 + 09ddfa2 + 44b05dd, render box, `charkit/out/hands_b2`, landed 2026-09-30 night)
Against b1 (same tree otherwise):
- **art_bumps_legs FAIL -> PASS (118.5 -> 0.0, every view 0): blocker cleared** by the placement (out 5.5).
- **body_three_quarter_skirt_aline still FAIL (-0.313, unchanged): blocker remains.** The far hand (R) in 3q is still
  43% hidden behind the skirt (visible 0.369 -> 0.566); ours leaves 46 rows free of a hand where the design's 3q has
  none (alinerows.py), so a few odd rows decide it. body_front_skirt_width WARN 0.866 (unchanged; the short-hand
  variant gives it too, so it isn't the hands' length).
- Hand checks: 13 PASS, 7 WARN, 1 FAIL (profile reach -0.081, was WARN -0.062: out shortens the profile's reach),
  3q digits R now INFO (43% hidden). hand_shape_L 0.500 -> 0.508 (FAIL: profile, the yaw choice A); views front 0.747 ->
  0.768, 3q 0.623 -> 0.705, profile 0.500 -> 0.508, back 0.718 -> 0.762. hand_shape_R 0.207 -> 0.492 (FAIL, 3q over
  what shows; whole 0.635); front 0.774 -> 0.775, back 0.733 -> 0.756. Reach -0.035..-0.081 L, digits within 1, cleft
  0.88-1.37 (all PASS).
- Guard IoUs: no shape IoU dropped: skin front 0.720 -> 0.738, 3q 0.729 -> 0.740, profile 0.731 -> 0.732, back
  0.740 -> 0.766; piece_skirt 0.899 (views 0.926/0.953/0.776/0.874), piece_cuff_L 0.722, _R 0.583 -> 0.582,
  shape_iou_skirt 0.867 -> 0.871, body_front_iou 0.876 -> 0.878, body_back_iou 0.888 -> 0.892; body_front_arms
  -3.4 -> -1.9.
- The render: both hands now face out and draw a line (ink.py fill share ours/design: front 0.92/0.93, back 0.92/0.91,
  3q L 0.89, profile 0.86; b1 was L 0.80-0.84 with knobs, R 1.0-1.18 with no line). Tiles: charkit/out/hands/ink_b2.

## Round 3 (2026-09-30, relaunched lean; coordinator: fix our arm, option (a))
- **Measured (charkit/out/hands/armangle.py BUILD OUT.json: per view and side the sleeve cuff's and the wrist cuff's
  centroids, the forearm's line between them and its skin's long axis; armfit.py: the 3D fit).** b2 (arm_b2.json):
  drawn forearm off vertical, + out: front 27.6/28.1 (L/R), back 27.2/27.1, 3q 20.9 / -25.3 (image right +), profile
  -1.1; ours 23.6/24.0, 23.6/23.9, 19.2 / -21.6, -1.4. The sleeve cuffs sit where drawn (front half-sum 0.650 vs 0.651 L
  from the midline): the upper arm is right, the forearm hangs 3.3-4.1 deg steeper. **The drawn views agree:** one 3D
  forearm direction fits every view within 0.85 deg (armfit_b2.json: L abduction 27.0, swing 1.4 fwd; R 27.6, 4.1); ours
  fits one too (23.7, 1.2 / 23.9, 3.1) within 0.2 deg (the projection model checks). So it's ours (step 1).
- **Cause:** the code body's arm chain is the outfit graph's front-view skeleton, one straight line shoulder to wrist
  at 22.5 deg; the hull's forearm (its edges' midpoints per height) runs at ~27.7, its cuff at x 1.04 L (the chain
  0.97 there), so the hull-lofted wrist band sat outside our forearm and was pushed in by the skin clearance.
- **Fix (code): `body.arm` {out, elbow_out, elbow_fwd} (code_body.ARM_POSE, pose_arm), applied to the arm's chain
  before its sections are measured round it** (bodypage.save_body, code_hand.Fit; cli.code_body's cache key);
  test_code_body: identity, lengths kept, angle grows by the knob, mirrored. Knob fit (armfit.py, symmetric, the posed
  chain's projections vs the drawn line and skin axes, all views): elbow_out 5.1 / fwd 0.9 (the chain alone, rms 0.74
  deg from 4.62) or 3.9 / 0.7 (b2's rendered offset kept, rms 0.60 from 3.51).
- A/B on the local evaluator (charkit/out/hands/ab/run_r3.sh: r3_cur, r3_e4, r3_e5; ab/r3_*.json), cur | 3.9/0.7 |
  5.1/0.9: **body_three_quarter_skirt_aline -0.313 FAIL | -0.017 PASS | -0.017 PASS**; body_front_skirt_width 0.866 W |
  0.984 P | 0.984 P; iou_skin front 0.738 | 0.812 | 0.828, back 0.766 | 0.847 | 0.845, 3q 0.740 | 0.767 | 0.763, profile
  0.732 | 0.733 | 0.731; body_front_arms -2.0 | +1.6 | +2.5 (back -1.5 | 1.5 | 2.4; INFO); shape_iou_skirt 0.871 | 0.880 |
  0.881; ref_iou 0.717 | 0.753 | 0.762; cuff edges mostly closer (front_L_left -0.127 W -> -0.090 P), but
  piece_cuff_R_three_quarter_bottom -0.099 P -> -0.108 W (both); **5.1 makes piece_overskirt_panel_L_front_top FAIL
  (0.090 -> -0.249)**, 3.9 keeps it PASS (0.043). Sleeves and sleeve cuffs unchanged. **Chosen: elbow_out 3.9,
  elbow_fwd 0.7** (spec: body.arm, both specs).
### Box build b3 (4ea5d18: body.arm elbow_out 3.9, fwd 0.7; render box, `charkit/out/hands_b3`, landed)
Against b2 (qa.json; CPU 1028 s):
- **body_three_quarter_skirt_aline FAIL -0.313 -> PASS -0.017: the last blocker cleared.** body_front_skirt_width
  WARN 0.866 -> PASS 0.984, skirt_pleats WARN -> PASS. **art_bumps_legs 0 (flag, PASS) kept**; art_band_lower PASS.
- The far hand in 3q: visible 0.566 -> 0.882 (occl_b3.json; b1 0.368); hand_shape_R 3q 0.492 -> 0.588 (whole 0.618).
- Arm (arm_b3.json): forearm line front 23.6/24.0 -> 24.8/25.2 (drawn 27.6/28.1), skin axis 23.2/23.8 -> 25.8/25.8
  (27.8/28.5); back skin 23.3/23.9 -> 25.8/25.9 (27.4/27.3); 3q R line -21.6 -> -22.1 (-25.3); handqa's arm axis at the
  cuff 22.5 -> 28.6/28.7 (drawn 28.2-28.6). Cuffs still 0.054 L (front) / 0.027 (back) inside the drawn, the hand tips
  0.085 / 0.061 (b2: 0.165 / 0.10); sleeve cuffs where drawn. Fingertips -2.58/-2.59 (drawn -2.585; LEG_TOP -2.62).
- Guard IoUs (mitten base | b2 | b3): skin front 0.738 | 0.738 | 0.813, 3q 0.726 | 0.740 | 0.767, profile 0.725 |
  0.732 | 0.733, back 0.759 | 0.766 | 0.847; piece_skirt 0.893 | 0.899 | 0.889 (views 0.919/0.932/0.774/0.867);
  shape_iou_skirt 0.871 -> 0.880; sleeves and sleeve cuffs unchanged (piece_sleeve_L 0.931, _R 0.835; sleeve_cuff
  0.790 / 0.784); piece_cuff_L 0.733 | 0.722 | 0.706 (front 0.614, 3q 0.832, profile 0.743, back 0.636), piece_cuff_R
  0.586 | 0.582 | 0.555 (front 0.604, **3q 0.428 | 0.468 | 0.325**, back 0.602). The 3q R cuff falls because it now
  shows: our wrist cuffs are 1.5-1.6x the drawn area in every view (2.2 -> 2.4x in 3q R as it comes out from behind the
  skirt; cuffiou.py: in place 0.416 -> 0.378, centred 0.436 -> 0.404): the cuff's size (its band's offset, thickness,
  bell), not this workstream's; the gate's guard doesn't fire on it (no new or flag check of ours targets the cuff).
- Moves, reported: cuff_back_flare_L PASS -> WARN (0.045 -> 0.121; the mitten 0.069), flap_front_width_R PASS -> WARN
  (0.0386 -> 0.0409), art_bumps_skirt 7.5 -> 24.0 (the base's 24.0), art_points_top 0 -> 5.3 (INFO, grade PASS).
- Hand checks: 13 PASS, 5 WARN, 4 FAIL (all new checks: reported, not blocking): hand_shape_L 0.492 (profile, the turn
  A), hand_shape_R 0.588 (3q), hand_profile_reach_L -0.111, **hand_three_quarter_reach_R WARN -0.071 -> FAIL -0.087**
  (now that the far hand shows, its reach is measured over 88% of it, not 57%); reach -0.040..-0.111 L (ours shorter).
- **Shoulder A/B (local evaluator, ab/r3b.log; on top of elbow 3.9):** out 1.5 | 2.0 | 2.0 with elbow 3.0: skin front
  0.834 | 0.828 | 0.836 (e4 0.812), back 0.829 | 0.808 | 0.829 (0.847), 3q 0.751 | 0.742 | 0.750 (0.767); and
  **piece_overskirt_panel_L_front_top and _R_front_top FAIL in all three** (-0.249, -0.217: new FAILs; also at elbow
  5.1). So the shoulder stays: the per-view costs of the remaining 2 deg are back/3q skin IoU and the panel's top edge.
- Merged pipeline-3d 640ca7c (e94407e). **Calibration: all 22 hand_* CALIBRATED** against b3
  (`charkit/out/calib/cur_hands`, hard links; records charkit/calib/records/hand_*.json; log calib_r3.log): the design
  passes every 1-2 px move (spread 0: the measures are relative to the cuff and laid on centroids), the mitten FAILs
  every one, the floors (stub_hands, blob_hands) FAIL, b3 beats them (hand_shape_L margin 0.174, _R 0.283; the probe
  blob_hands still PASSes hand_shape at 0.80-0.81: shape can't see digits, the digits check does).
- **Review page: charkit/out/hands/review_r3/index.html** (page3.py; tiles review3.py: design | mitten | b2 | b3 per view,
  hand window and arm window round each build's cuff; the arm angle table and per-view angle diagrams; the evaluator
  A/B; guard IoUs; weights and fist; calibration).

- Merged pipeline-3d 342e88c (8fcf271; tool/face5, clean). **Pregate PASS** (0 blocking, 53 moved; report
  charkit/out/pregate/pregate_tool-hands_8fcf2710_into_342e88c8.md): 3q aline 0.08 WARN -> -0.017 PASS (the base's,
  342e88c), skin IoU up in every view, cuff edges mostly PASS. body_front_skirt_aline 0.002 PASS -> gone (not blocking):
  bodyqa.aline uses the rows with no hand against them, and with real hands no free row is left within 0.15 L of the
  front hem, so it returns None (gone since b1: the mitten never reached the hem). Re-reading aline's fallback (all rows
  when the free ones miss the hem band) would be a remeasure: not done here.
- **Box gate** launched: `python -m charkit remote gate tool/hands --into pipeline-3d`, log charkit/out/hands/gate_r3.log.

### Gate 1 (397ffa1 into pipeline-3d 342e88c): FAIL, 7 blockers, all the motion QA's
Report charkit/out/gate/gate_tool-hands_397ffa1_into_342e88c.md (948 s; CPU 1.32x). Nothing of the hands' own blocks:
the 3q aline improved, no new FAIL among existing checks, no flag regression (art_bumps_legs 0, art_band_lower,
art_mirror_waist PASS), the hand checks' calibration accepted, the guard quiet. The 7: motion_kick_skirt_inside/stretch,
motion_squat_skirt_inside/stretch "the 2x2 couldn't measure it (its measure changed with no registered step)" and 3
"calibration record not refreshed". Cause: the motion QA (tool/xpbd, merged 640ca7c) builds its scene with
bodyeval's assembly, i.e. this tree's code_body.build_body_data, and requires the bundle's skin vertex count to match
(charkit/sim/motion.py Scene). So (1) codediff counts code_body/code_hand (our hands, the arm pose) as motion's measuring
code; (2) the crossed cell "old measure on the new geometry" (342e88c's code on our bundle) can't run: the base code
rebuilds a body with no hands, the counts differ, the part raises. The candidate's measure on the old geometry reads
the base's values exactly (0.00244, 0.0635, 0.00601, 0.10386): the measure didn't change; ours moves <= 0.0002.
- Done: the step registered (charkit/steps/code_body.py: motion_* at 5d18d38 and c8c4991, saying so); the 3 graded
  motion records to refresh on a merged build: box build b4 (render box) `charkit/out/hands_b4`, log
  charkit/out/hands/b4.log, then `python -m charkit calibrate motion_kick_skirt_inside,motion_kick_skirt_stretch,
  motion_squat_skirt_stretch --build charkit/out/hands_b4`.
- Left for the coordinator: the 4 unmeasurable 2x2 cells (any branch that changes the body's topology hits this:
  base code can't rebuild the new body). Either `--accept motion_*` named by the coordinator, or the motion scene reads
  the skin's weights from the bundle instead of rebuilding them (a tool/xpbd change; the base side still rebuilds).

## Next steps (exact)
1. **The 3q skirt aline blocker** (new FAIL under K). Its cause is placement: our far hand hangs 43% behind the
   skirt's 3q flare, because our forearm hangs 6 deg steeper than drawn (tips.py: 22.5 vs 28.2-28.6 deg off vertical near
   the cuff; that's the hull's arm chain, and pose.arm_down doesn't reach the code body). Options, in order: (a) a
   code-body arm pose knob (the arm chain turned outward at the shoulder in her frontal plane, ~3-6 deg, as a rest-pose
   rotation the sleeves and bands follow), checked with evalab.py (aline, body_*_arms, skin IoUs) and occl.py (the 3q
   far hand visible), then a box build; (b) if Michael prefers the hull's arm: bodyqa.aline on the rows free in both
   (as skirt_width's `common`) is a remeasure, but the 2x2's old measure on the new geometry still FAILs, so it needs
   his acceptance by name (the coordinator names it). Don't loosen it.
2. Calibration records on b2: copy it to `charkit/out/calib/cur_hands` (hard links + its qa.json), then
   `python -m charkit calibrate 'hand_*' --build charkit/out/calib/cur_hands`; commit charkit/calib/records/hand_*.json.
   The adapter turns our_hidden off for the label stand-ins (calib/hands.py).
3. The review page: `python charkit/out/hands/review2.py charkit/out/hands/review_r2 mitten=charkit/out/calib/builds/mitten
   b1=charkit/out/hands_b1 b2=charkit/out/hands_b2` (tiles at one window round each cuff, rows.json), plus
   charkit/out/hands/review_r2/weights_fist.png (weightspic.py) and fist_report.json, the sheet
   (charkit/refs/clawd/gen/hand_breakdown.png, refcheck_hand_breakdown_1.png). Write review_r2/index.html with the
   summary box first (Recommended: the default hand as b2 builds it, A with out 5.5 and line 0.5; Asked of Michael:
   the arm-angle fix (a) or acceptance (b) for the 3q aline; whether hands should hide behind the skirt in 3q; Key
   numbers: hand_shape per view, art_bumps_legs, aline, fill share, mitten | b1 | b2), then per view design | mitten |
   b1 | b2; `open` it.
4. `python -m charkit pregate`, then (coordinator relaunch) `python -m charkit remote gate tool/hands --into pipeline-3d`.
5. **(Deferred by Michael, 2026-09-30: waits for a dedicated hands/expressions session; not on this branch.)** A draft
   was started before the scope change and parked, untracked: charkit/out/hands/draft_handposes.py (the library:
   relaxed/open/fist/point, per digit curl (3 joints), spread, thumb oppose; pose() blends {name: weight}, blend(a, b,
   t), per_hand {'L','R'}; posed() = numpy LBS on the template's weights; rotations() per VRM bone; grade() renders
   each pose from the back and as the front view sees it, against handref.sheet_hands' cells; fit() Powell per pose)
   and charkit/out/hands/draft_expressions.patch (a skeletal `hands` component: weights() leaves it out,
   hand_poses(P) resolves it, library()/check() know it). Graded on b1's hand (the rest knobs): relaxed back/front IoU
   0.715/0.795; fitted (posefit.log): open 0.571/0.605 (curl -4.3, spread 16.5, thumb spread 26), fist 0.591/0.742
   (MCP 32, PIP 86, DIP 28: the sheet's fist keeps its fingers' first phalanges hanging), point 0.640/0.772. The
   sheet's hands are 16-19% longer and broader than the turnaround's: IoU near 0.7-0.8 is its ceiling. Still to do
   there: the Blender side (pose the finger bones from rotations() on the boards, the export and exprqa's renders),
   fist QA on the built rig (interpenetration, knuckle area), then the original plan below.
6. (Original plan, deferred with step 5) the `hands` expression component (relaxed, fist, open, point; per finger curl, spread, thumb opposition;
   per hand, blendable) on the modular expression API (charkit/expressions.py, the mouth/eyes/brows presets), using
   code_hand.curl_pose's joint convention (bend about along x -dorsal); grade per pose against hand_breakdown
   (handref.sheet_hands gives each cell's hand at the turnaround's scale; the fist's digits/cleft); fist QA on the built
   rig (interpenetration, knuckle area) -> correctives only if asked.
