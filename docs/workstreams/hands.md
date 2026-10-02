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
- b4 (the merged tree, 397ffa1's code; `charkit/out/hands_b4`) reads as the gate's candidate (motion 0.00244 /
  0.06346 / 0.00619 / 0.10404; aline -0.017; art_bumps_legs 0). **Motion records refreshed, all 3 CALIBRATED on b4**
  (calib_motion.log): kick inside design 0.0017-0.0039, known-bad motion_nocol 0.0125 FAIL, current 0.00244 PASS; kick
  stretch 0.056-0.070 / motion_skinned 1.99 FAIL / 0.0635; squat stretch 0.096-0.136 / 0.872 FAIL / 0.104.
- Merged pipeline-3d 961037c (b5e18cb; tool/hair5; prompts.json conflict resolved keeping hand_breakdown and the hair
  prompts). Pregate PASS (0 blocking, 53 moved). Gate 2 launched (log charkit/out/hands/gate_r3b.log) to confirm only
  the 2x2 cells remain.
- Left for the coordinator: the 4 unmeasurable 2x2 cells (any branch that changes the body's topology hits this:
  base code can't rebuild the new body). Either `--accept motion_*` named by the coordinator, or the motion scene reads
  the skin's weights from the bundle instead of rebuilding them (a tool/xpbd change; the base side still rebuilds).

### Gate 2 (6903882 into pipeline-3d 961037c): FAIL on 4 cells only, the coordinator's call
Report charkit/out/gate/gate_tool-hands_6903882_into_961037c.md (989 s; CPU 1.36x; tests all ok; guard quiet; every
calibration requirement met). The only blockers: the 2x2 couldn't measure motion_kick_skirt_inside/stretch,
motion_squat_skirt_inside/stretch in the "old measure on the new geometry" cell (961037c's motion QA can't rebuild a
body with hands from our npz: its vertex count differs from our bundle's skin). Base -> candidate: 0.00244 -> 0.00244,
0.0635 -> 0.0635, 0.0060 -> 0.0062 (INFO), 0.1039 -> 0.1040. Reported, not blocking: cuff_back_flare_L and
flap_front_width_R PASS -> WARN; the 4 new hand FAILs (hand_shape_L 0.492, hand_shape_R 0.589, hand_profile_reach_L
-0.111, hand_three_quarter_reach_R -0.087); body_front_skirt_aline gone.

## Next steps (exact)
1. **Coordinator:** the 4 motion_* 2x2 cells. Either name them for `python -m charkit remote gate tool/hands --into
   pipeline-3d --accept motion_*` (their values are the base's to 0.0002; the step is registered in
   charkit/steps/code_body.py; records refreshed), or have tool/xpbd's scene take the skin's weights from the bundle
   (charkit/sim/motion.py Scene rebuilds them with code_body.build_body_data; that still can't help this merge's base side).
   If pipeline-3d moves first: merge it, `python -m charkit pregate`, gate again.
2. Michael's questions (the review page's summary, charkit/out/hands/review_r3/index.html): keep the elbow-only arm (the
   forearm ~2 deg steeper than drawn, cuffs 0.03-0.05 L inside; a shoulder turn fails the panels' top edges), and
   whether the wrist cuff's size (1.5-1.6x the drawn area; piece_cuff_R 3q 0.428 -> 0.325 now that it shows) goes to
   a garments round.
3. Open items on the hands (reported, new checks): reach 0.04-0.11 L short (the profile's -0.111 and the far hand's
   3q -0.087 FAIL; refit length/out on the posed chain: `python -m charkit.code_hand fit` now uses the posed chain);
   hand_shape_L profile 0.49 (the turn A, Michael's call); body_front_skirt_aline unmeasured with real hands (bodyqa.aline's
   fallback: a remeasure, not done).
4. **(Deferred by Michael, 2026-09-30: waits for a dedicated hands/expressions session; not on this branch.)** The pose
   library draft stays parked, untracked: charkit/out/hands/draft_handposes.py and draft_expressions.patch (see the
   round 2 section's numbers: relaxed 0.715/0.795; open 0.571/0.605, fist 0.591/0.742, point 0.640/0.772 back/front;
   the sheet's hands 16-19% longer than the turnaround's). Still to do there: the Blender side (pose the finger bones from
   rotations() on the boards, the export, exprqa's renders), fist QA on the built rig (interpenetration, knuckle area),
   then the `hands` expression component (relaxed, fist, open, point; per finger curl, spread, thumb opposition; per
   hand, blendable) on charkit/expressions.py, graded per pose against hand_breakdown (handref.sheet_hands).

## Round 4: on-model pass (tool/hands2 from pipeline-3d 71a2f0e, 2026-10-01)
Michael (2026-10-01): the default hand (de2fa87) "looks very bad to a visual inspection ... clearly extremely
off-model" while its checks pass on shape IoU (13 PASS / 7 WARN / 1 FAIL). A check-versus-eye disagreement: calibrate
the measure, truth-check the asset, check granularity, then fix the builder (code_hand.py). Rest orientation A stays;
the pose library stays deferred. Harness and outputs: `charkit/out/hands2/`.
- Box build `charkit/out/hands2_base` (render box, boards body,design): pipeline-3d 71a2f0e as is (the before).

### Round 4 state at wrap-up (2026-10-01; coordinator: WRAP UP at 95% weekly capacity, the fix not started)
Steps done: look, name, measure, truth-check, granularity, a dry calibration. Not done: the builder fix, the records,
the box build, the review page, the gate. Pictures (charkit/out/hands2/, local): `zoom_pairs.png` (design over ours at
matching scale, front L, 3q L, front R, back L), `look_pairs.png`, `look_design_front.png` beside
`look_b4_front_board.png` (the EEVEE board), `feat_b4_4.png` (each hand turned arm-down, its interior seams black:
design | ours for front L, 3q L, profile L, back R). Numbers: feat_b4.json, sheetfeat.json, hq_b4/checks.json.

**What makes it off-model** (ours = de2fa87's hand, read on hands_b4, the same code and knobs; shares of the reach past
the cuff; both drawings agree: the turnaround and the hand sheet at 4x its resolution):
1. **A comb, not a hand.** Four thin separate finger tubes, each outlined, fanned apart, the background (and dark
   double hull lines) between them. Gaps at the fingertips (the hand's span with no hand in it, 80-95% of the reach):
   design 0.000-0.010 (sheet: relaxed back 0.025, side 0), ours 0.106-0.176 (front, back, 3q L); profile 0.023.
2. **Square end.** Taper (the width at 85-95% over the widest): design 0.40-0.51 (sheet 0.43 / 0.32; 3q R 0.70, the
   far hand), ours 0.59-0.67: the fingertips side by side at one level where the drawing converges on the middle tip.
3. **No thumb.** The drawn thumb is its own prong with a V cleft (front, back, 3q); ours is a nub against the palm
   (thumb_out 5.4, thumb_down 5.1 deg: the fit folded it in). The deepest silhouette pocket's bottom: design 0.56-0.64
   (profile 0.74), ours 0.72-0.76, a gap between fingers. The cleft check (depth ratio 0.81-1.37, PASS) was passing on
   our finger gaps.
4. **A block palm.** No wrist: the width at 5% over the widest, design 0.66-0.84 (sheet back 0.60), ours 0.84-0.93
   (largest in 3q L 0.69 vs 0.93 and profile 0.66 vs 0.93).
5. **Lines.** The drawing's interior lines are hairlines starting 30-57% down; ours run from the knuckles (~10%) as
   dark wedges (each finger's hull). Not made a check: our_seams marks the palm/finger shell boundary as a knuckle
   cross-line the drawing of ours doesn't draw, and an interior-ink share (declared.our_lines) reads ours below the
   design because our mask excludes the gaps our ink sits in (inkfeat.py). Fidelity work for later.
6. Profile (orientation A, Michael's call): ours edge-on, widest 0.29 of the reach vs the drawn 0.49: A's known
   per-view cost, not the template's.

**Truth-check:** the drawn cuff masks the hand is cut at equal the hand-checked outfit truth (IoU 1.000 in every view
and side; 3q R's cuff 0.615 but its hand cut identical, 1.000) (truthcheck.py). The hand sheet corroborates 1-4.
**Granularity (probes on hand_shape, dry run):** comb_hands (the drawn fingers slit apart) 0.81 PASS, blunt_hands
(squared tips) 0.82-0.88 PASS, blob_hands 0.80-0.81 PASS: the shape IoU can't see finger separation, square tips or
digits. That's the check-versus-eye gap.

**New checks (committed as work in progress, no records yet):** handqa `hand_{view}_gaps_{L,R}` (ours - design, PASS
0.03 / WARN 0.06), `hand_{view}_taper_{L,R}` (|ours - design|, 0.08 / 0.15), `hand_{view}_cleftpos_{L,R}` (0.06 /
0.12; where the design's cleft >= CLEFT_MIN); INFO below VISIBLE_MIN like digits and cleft; `features` adds gaps,
taper, cleft_at and the width profile. The 22 existing hand checks read identically on b4. calib/hands.py: entries for
the three, known-bad `comb_hand` (stored: charkit/calib/known_bad/comb_hand.json, the store
charkit/out/calib/builds/comb_hand = hands_b4), probes comb_hands, blunt_hands (also on hand_shape).
Dry calibration (`calibrate ... --build charkit/out/calib/cur_comb --no-write`, calib_dry.log; current = comb_hand):
- gaps: CALIBRATED front L/R, back L/R, 3q L (design 0, comb 0.11-0.18 FAIL, comb probe FAIL; kind defect, the blob
  floor passes as expected). BLIND profile L (comb 0.023) and 3q R (0: the far hand edge-on).
- taper: CALIBRATED 6 of 7 (comb 0.15-0.21 FAIL; stub 0.47-0.55 FAIL; blob 0.12-0.22 WARN/FAIL). BLIND 3q R.
- cleftpos: CALIBRATED front R, back L, profile L. BLIND front L (comb 0.092 WARN), back R (0.103 WARN), 3q L (0.059).

**Exact next steps:**
1. Scope, don't loosen: gaps only in front, back and 3q L (views list; profile L and 3q R draw the fingers edge-on, so
   INFO); taper 3q R INFO; cleftpos tightened to 0.05 / 0.08 (the design's spread is 0, so it still PASSes; comb's front
   L and back R then FAIL), 3q L INFO. Re-run the dry calibration. Update handqa's docstring list; register the step
   in charkit/steps/handqa.py ('hand_*', COMMIT, "new: gaps, taper, cleftpos").
2. The builder (code_hand.py), fitted with the new measures beside the shape IoU per view: extend Fit.score with gaps,
   taper and cleft_at on the template's own renders. Knobs: spread allowed negative (tips converge; BOUNDS -8..12),
   fingers wide enough to touch their neighbours along their length (knuckle spacing is 0.24 palm_w), a stronger taper;
   the thumb as a prong parting at ~0.6 of the reach (thumb_out, thumb_len, thumb_w into FIT_KNOBS); a narrower wrist
   (wrist_w / palm_w ~0.7-0.75). Keep the weights summing to 1 and fist_report healthy (charkit/tests/test_code_hand.py).
3. Motion 2x2: build_body_data reads the hand rings from body_code.npz and reaches only code_hand.UV_BAND, so geometry
   changes in code_hand shouldn't flag motion_*; handqa did change, so after the after-build:
   `python charkit/out/hands2/curdir.py BUILD cur_hands2`, then `python -m charkit calibrate 'hand_*' --build
   charkit/out/calib/cur_hands2` (all 42 records).
4. Box build (render, boards body,design), review page (design | before hands_b4 | after, per view and the hands
   close-ups), pregate, `python -m charkit remote gate tool/hands2 --into pipeline-3d`.
- Box build `charkit/out/hands2_base` (pipeline-3d 71a2f0e, the before): **landed** after wrap-up (exit 0, boards
  body,design fetched; log charkit/out/hands2/base.log). Use it as the review page's before (hands_b4 has the same hand).

## Round 5: the on-model hand (tool/hands2, relaunched 2026-10-01; coordinator brief)
Merged pipeline-3d 00494de (f4781fe). Coordinator decisions: gaps and taper report-only only where the view can't show
them, the reason recorded; cleftpos tightened, not loosened. The laptop is memory-critical (coordinator, mid-round):
fits, builds and calibrations run on the boxes; local work is light (single evaluations, reading results).
- **Checks scoped (4c76150):** handqa.EDGE_ON: gaps INFO in profile L (our fingers edge-on at rest A: the comb reads
  0.023) and 3q R (the far hand, drawn 0.16 L across, comb 0); taper INFO in 3q R (the drawing itself ends square there,
  0.70). cleftpos 0.06/0.12 -> 0.04/0.055. `wrist` (width at 5% of the reach over the widest) in the table, not graded.
  Dry calibration vs comb_hand (calib_dry2.log): all 17 graded gaps/taper/cleftpos CALIBRATED (the comb's 3q L
  cleftpos 0.059 now FAILs). The 3 INFO-only checks need no record (leave them out of `calibrate`).
  Steps registered: charkit/steps/handqa.py ('hand_*' at c6aceaa and 4c76150).
- **code_hand.cuff_end was stale:** pipeline-3d's cuff template (span, no t/width) put the cuff 0.31 L up the forearm
  in the fit (reach errors 0.31). Fixed: span[1] - forearm length. The fit then reads the base hand as the QA does
  (front L IoU 0.762 vs QA 0.761).
- **Template rebuilt (code_hand.layout/digits):** the fingers tile the knuckle line (palm_w; neighbours overlap by
  `overlap` of their width), their tips laid the same way at the tapered widths about the middle finger's (converging);
  `spread` a fan beyond that (0 = held together); finger_w gone (derived). Thumb from near the wrist's radial edge
  (0.3 wrist_w), its knobs (thumb_w, thumb_out, thumb_down, thumb_base, thumb_len to 0.46) all fitted. yaw/out fixed
  (rest A). Fit.score adds the structure (gaps, taper, cleftpos, wrist: each over its PASS limit, x STRUCT 0.1, capped
  at 3 units) and per-view IoU floors (`--floors`, FLOOR_W 5 per point under: the guard's intent). `charkit hand
  fit|show` (cli) so fits run on the boxes; `--method de --workers N`.
- fit1 (local Powell, before the floors; charkit/out/hands2/fit1.log, fit1.png): gaps 0 everywhere, taper 0.37-0.44 vs
  drawn 0.40-0.48, cleftpos within 0.01-0.06, wrist 0.79 vs 0.78-0.84 (front/back); but IoU front 0.73/0.74, back
  0.70/0.72, 3q 0.62/0.67, **profile 0.385** (the before's 0.49: the guard). diag/rotwidth.py: in front/back the widths
  now track the drawn; a 9 deg turn gives 0.79-0.82 (the hand's angle: dev 0 gives front 0.79, dev -4 0.81).
- Next: fit2 on the render box (DE + Powell, floors at 0.9 x the before's QA hand_shape views), then the spec, tests,
  the box build, calibrate 'hand_*' on it (42 records minus the 3 INFO-only), review page, pregate, gate.
- **fit2 on the old render box (job hand-hands-1001-081934-0f97): killed at 110 min with no generation done.** A pool
  forked after the parent's first evaluation hung (fork after threads). Now: DE workers spawned, each building its own
  fit (Fit.src), thread counts 1, a per-generation progress line (generation, best cost, per-view IoU); smoke-tested
  locally (2 workers, 1 generation). Fits run on the build box (no --box), which has no build of this worktree:
  **s1** = a QA-only build there of the start knobs (fit1's with dev 0, committed in the spec), `charkit/out/hands2_s1`,
  log charkit/out/hands2/s1.log: the real QA's first reading of the new template and the refit's --build.
  Next: `remote run --fetch charkit/out/hands2/box_fit3 hand fit --build charkit/out/hands2_s1 --floors ... --method de
  --workers 16 --maxiter 30 --rounds 1 --maxfev 300 --png/--json charkit/out/hands2/box_fit3/...`, then setknobs.py,
  the after-build on --box render2 (boards body,design), calibrate on the build box.
- **s1's QA (build box, start knobs; vs the before hands2_base):** gaps 0.10-0.19 FAIL -> 0-0.018 PASS (every graded
  view); taper 0.15-0.25 FAIL -> within 0.07 PASS; cleftpos front L/R, back R PASS, back L FAIL 0.071 (drawn 0.565: the
  drawing's L/R differ by 0.05 in back), profile FAIL -0.338, 3q L WARN 0.043; reach within 0.02 L (profile -0.066 WARN,
  was -0.088 FAIL); hand_shape_L 0.510 -> **0.403 (profile: the guard)**, views front 0.756/0.774, 3q 0.656/0.625, back
  0.743/0.745. Moved, not blocking: body_front_skirt_width PASS 0.982 -> WARN 0.861 and body_three_quarter_skirt_aline
  PASS -0.012 -> WARN 0.09 (both read the rows no hand touches: ours now blocks every row the design leaves free, so
  skirt_width falls back to the waist rows, 0.76 vs 0.88 L); digits back WARN +2 (our seams show 4, drawn 2); 3q cleft L
  WARN 0.42; art_bumps_legs 0 PASS; piece_cuff unchanged.
- **fit3 (build box, job via `remote run --fetch charkit/out/hands2/box_fit3`): DE 30 generations (7936 evaluations,
  16 spawned workers) + Powell 300.** Fit-scale IoU front 0.771/0.793, 3q 0.769/0.715, back 0.760/0.765, profile 0.478;
  gaps 0; taper 0.41-0.44 vs drawn 0.40-0.48; cleftpos front 0.625/0.602 (drawn 0.644/0.639), 3q L 0.626 (0.622), back
  0.608/0.610 (0.565/0.616), profile -0.02 (0.736: our pocket in profile is the wrist's); wrist 0.78-0.83 (drawn
  0.78-0.84; 3q L 0.78 vs 0.69, profile 0.87 vs 0.66). Knobs (e2db92f): length 0.685, palm 0.4345, palm_w 0.219, wrist_w
  0.169, palm_t 0.081, taper 0.567, overlap 0.215, spread -1.06, curl 6.3, thumb_len 0.345, thumb_w 0.047, thumb_out
  14.2, thumb_down 1.9, thumb_base 0.100, bend -2.3, dev -0.84 (yaw 61.9, out 5.5 kept). Fist: knuckles 0.77 of rest,
  thumb 0.94; neighbours' deepest overlap 0.009-0.010 L in the fist vs 0.012-0.015 at rest (held together by design).
- Known-bad stores pushed to the build box (bucket push: comb_hand, mitten), so calibrate runs there.
- **Running:** after-build with boards on render2 `charkit/out/hands2_after` (log after.log) and its QA-only twin on the
  build box `charkit/out/hands2_after_q` (log after_q.log). Then: `remote run --fetch charkit/calib/records calibrate
  NAMES --build charkit/out/hands2_after_q` (NAMES = the graded hand_* in after_q's qa.json, not the 3 EDGE_ON INFO),
  the review page (`charkit review page`, before hands2_base | after hands2_after, regions hands + hands_close), pregate,
  `remote gate tool/hands2 --into pipeline-3d`.
- **After-build** (e2db92f's knobs): render2 `charkit/out/hands2_after` (boards body,design) and its build-box twin
  `charkit/out/hands2_after_q` (QA identical but 4 render-noise values). Against the before (hands2_base): no new FAIL;
  non-hand moves only body_front_skirt_width PASS 0.982 -> WARN 0.861 and body_three_quarter_skirt_aline PASS -0.012 ->
  WARN 0.09 (the hand-row exclusion); hand_shape_L views front 0.761 -> 0.761, 3q 0.701 -> 0.741, profile 0.510 ->
  0.488, back 0.754 -> 0.736; _R front 0.769 -> 0.775, 3q 0.630 -> 0.656, back 0.771 -> 0.757 (worst -4%). Findings
  per view: charkit/out/hands2/findings.txt (gaps 0.10-0.19 -> 0; taper 0.60-0.68 -> 0.40-0.44; cleft at 0.71-0.77
  -> 0.61-0.63; wrist front/back 0.76-0.80 vs drawn 0.78-0.84, 3q L 0.85 -> 0.81 vs 0.69, profile 0.93 vs 0.66).
- **Calibration:** 39 graded hand_* CALIBRATED on hands2_after_q (calib_after.log; records committed). The first try
  lost its run to a PermissionError (the box hard-links synced inputs read-only; calibrate wrote records in place):
  fixed, records written temp + rename (8580945).
- **Review page:** charkit/out/hands2/review/page/index.html (built on the build box from review/page.json: summary,
  key numbers, the fit's silhouettes, qa_hands before/after, per view design | before | after, close-ups hands_board
  (EEVEE boards) and hands_close (bundle drawn, 320 px/L)). The coordinator's review: structure right; two visible gaps
  for what's left (INFO on the page): the hand's outline (skin not in the look's ink_regions: brown (0.42, 0.24, 0.20)
  at body.hand.line 0.5) and the finger separation lines (fingers overlap 0.215 of their width: outline hulls hidden).
- Pregate skipped (laptop memory-critical; it runs the evaluator for both trees locally, and the box copy has no git):
  the after-build's real QA against the before stands in. Merged pipeline-3d 9be5b32 (40a0168). Gate launched.

### Gate of hands2: **PASS under K** (tool/hands2 fc89db1d into pipeline-3d e003960d)
Report charkit/out/gate/gate_tool-hands2_fc89db1d_into_e003960d.md. Nothing blocks: no new FAIL among existing checks,
no flag regression, CPU 1.21x (1153.6 -> 1394.3 s); 39 calibration records accepted, 0 guard findings. Reported: the
two skirt measures PASS -> WARN (body_front_skirt_width 0.982 -> 0.861, body_three_quarter_skirt_aline -0.012 ->
0.09: the hand-row exclusion), the new hand_profile_cleftpos_L FAIL (-0.825; rest A's profile), flag values moved
within PASS (art_mirror_waist 0.72 -> 0.754). The coordinator merges it as the interim (strictly better than the comb).

## Round 6: hands3, the structure from the hand sheet (coordinator, Michael's call 2026-10-01)
The turnaround's hands are small with merged fingers (the canonical rule's step 2: internal structure it can't resolve),
so the structure comes from hand_breakdown.png's OPEN pose (top row second: five digits from the back; bottom row
second: the thumb's side); the turnaround stays the authority for overall size (reach past the cuff). Michael also saw
three-quarter showing no finger delineation (a blur). hands2 goes to pipeline-3d as an interim if its gate passes.
Plan: 1. measure the open pose, fit the template's structure to it per row (tip count, per-digit length and width
profile, shape IoU); 2. validate by posing the fitted structure (LBS on the finger bones) into relaxed, fist, point,
graded against the sheet per row; 3. the rest pose against the turnaround (IoU per view no worse than the comb's);
4. finger delineation: an ink check against the design's lines (front, 3q at least), our renderer drawing a line where
two fingers touch (a seam gap or inked seams, both measured), the hand's dark outline; 5. review page (sheet | comb |
hands2 | hands3, per pose and view; 3q rest close-ups), calibrate, pregate --box auto, gate.
- **charkit/handsheet.py (2f…):** cells() (the sheet's 8 hands, the arm straight down), digits() (tips = the contour's
  local maxima of distance from the wrist standing 0.06 of the reach above the clefts beside them; each digit's base at
  the level of its shallower cleft, the far edge as far from the tip; length, width profile at 0.1-0.9 of its length,
  angle, tip roundness; palm width across the clefts, the knuckle line), draw() (the template in the sheet's rows from
  its own frame), SheetFit, `charkit handsheet fit|show`. The template gained fan_index..fan_little and thumb_across
  (defaults: hands2's hand exactly); code_hand.search is the DE/Powell search both fits share (spawned workers rebuild
  the fit from fit.src = 'module:factory').
- **The sheet's open pose (shares of the reach past the cuff):** back: little 0.385 (angle -40 deg), ring 0.446 (-22),
  middle 0.496 (-6), index 0.454 (+8), thumb 0.320 (+47; its base 0.356 along); widths at the base 0.093-0.119, at
  0.9 of the length 0.045-0.061 (tip roundness 0.62-0.73); palm 0.404 across the clefts; knuckle line 0.494. Side:
  three tips (two fingers, the thumb 0.277 at +32). Relative to the middle: little 0.78, ring 0.90, index 0.92.
- hands2's template drawn open (fan 14/0/-16/-34, thumb out 45): back IoU 0.513 (palm 0.29 vs 0.40, knuckles 0.43 vs
  0.49), side 0.351 (2 tips vs 3). **open1** fit running on the build box (charkit/out/hands3/open1, log open1.log).
- **Open-pose fits (build box, `charkit handsheet fit`):** open1 merged two fingers for IoU while the per-digit terms
  fell away (fixed: every drawn digit is matched, an unmatched one costs its terms; a tip more or fewer 0.25); open2
  matched all five digits but the side row read curled (curl bound 0) and pure-side (the sheet's side is drawn turned:
  view_turn_side, a comparison parameter, side IoU 0.39 -> 0.58 at -20 deg). **open3** (charkit/out/hands3/open3): back
  IoU 0.640, 5/5 tips, lengths little 0.386/0.385, ring 0.464/0.446, middle 0.488/0.496, index 0.448/0.454, thumb
  0.322/0.320; widths RMS 0.002-0.005 (thumb 0.020); angles within 2-9 deg (middle 7.5 vs -6.4); palm 0.387/0.404;
  knuckles 0.497/0.494. Side IoU 0.713, 3/3 tips, lengths within 0.015. Structure taken into the spec (c… commit):
  palm 0.5175, palm_w 0.281, wrist_w 0.109, palm_t 0.084, taper 0.461, overlap -0.017 (a hairline seam), fingers
  0.936/1/0.979/0.812, thumb_base 0.093, thumb_across 0.481, thumb_len 0.389, thumb_w 0.082; line 1.0. The sheet's
  open palm (0.40 of the reach) agrees with the turnaround's front hand once its turn is undone (~0.39).
- **fingerlines_{view}_{L,R}** (declared in handqa.py: ink_inside on the hands as pieces, declared.py's new HANDS and
  align 'centroid'; front/3q/back L, front/back R; limits 0.4/0.5; Michael's flag). Dry calibration on the box: design 0
  (every move), paddle_hand (hands2's hand, stored known-bad) 0.72-0.83 front/back, 0.58 in 3q, floors 1.
- **rest1** running (build box): open3's structure fixed; length, curl, spread, thumb_out/down, bend, dev fitted to
  the turnaround, floors the comb's QA hand_shape views + 0.02 (charkit/out/hands3/floors_rest.json).
- The seam gap: `tip_gap` (fingertips apart, the hulls draw the hairline) and code_hand.SEAM_MAX 0.005 L.
- **rest1** (charkit/out/hands3/rest1): fit-scale IoU front 0.775/0.792, 3q 0.792/0.707, back 0.782/0.779, **profile
  0.583** (comb 0.51, hands2 0.48), but the thumb folded in (thumb_out 1 deg): 3q L cleftpos 0.16 vs 0.62 and profile
  taper 0.35 vs 0.51 would FAIL (new FAILs once hands2 is the base). Fit change: FAIL_COST 0.5 per graded term past its
  WARN limit. **rest2** running (from rest1, thumb_out 14).
- **poses1** (`charkit handposes fit`, build box; the rest = open3's structure with hands2's rest angles; LBS on the
  template's own weights): open back 0.640 (5/5 tips) / side 0.548; relaxed 0.874 / 0.620; fist 0.799 / 0.654 (reach
  0.70 of the open hand vs the sheet's 0.80); point 0.714 / 0.685 (0.95 vs 1.01). Fitted angles: fist MCP 31, PIP 98,
  DIP 24, thumb oppose 79; point index -1, others 69/105/62. The side row now drawn at the sheet's turn (handsheet.TURN
  side -13.4, open3's fit) for every pose.
- **rest2** (FAIL_COST on): fit-scale IoU front 0.748/0.762, 3q 0.798/0.705, back 0.754/0.749, profile 0.584; every
  graded term out of FAIL but back L cleftpos (0.665 vs drawn 0.565; the drawing's L/R differ by 0.05: a cleft at
  0.56-0.62 keeps both backs within WARN, hands2's 0.619). Front/back 2-4% under the comb's QA.
- **The references disagree on the palm's width** (single evaluations, rest2's angles; fit-scale turnaround IoU | the
  sheet's open back IoU, its palm): palm_w 0.281 (the sheet's fit) front 0.75/0.76, back 0.75/0.75 | 0.640, 0.387 vs
  0.404; 0.26: 0.776/0.795, 0.780/0.774, profile 0.556 | 0.622, 0.358; 0.245: 0.795/0.812, 0.798/0.793, profile 0.537 |
  0.598, 0.340. The sheet's hand is ~15% wider for its reach than the turnaround's. The canonical rule's step 3: the
  base takes the best fit across both: **JointFit** (`charkit handsheet joint`: structure shared, the sheet's open
  angles 'open.*' and the rest angles separate, costs summed, the comb's floors kept). **joint1** running (build box,
  charkit/out/hands3/joint1, log joint1.log).
- **joint1 killed** (86 min, 16 of 30 generations, no gain over its start: a saturated box). The joint cost scanned over
  palm_w alone (charkit/out/hands3/palm_scan.json) lands at the sheet's own palm (1.52 at 0.281; 1.60-1.88 at
  0.245-0.275): no distinct compromise.
- **Palm-width page for Michael** (coordinator, 2026-10-01): charkit/out/hands3/palmpage/page/index.html (`charkit
  handsheet palm`: the drawings at one reach past the cuff, the palm across the knuckle line (0.494 of the reach)
  measured on each, ours outlined at each palm with its IoU; panels charkit/out/hands3/palm/). Drawn palm (share of
  the reach): the sheet's relaxed back 0.437, the turnaround's profile 0.472 (both broad-on: they agree), its front
  0.310/0.313 and back 0.328/0.316 (narrow). Options (rest2's angles): A sheet palm_w 0.281: sheet IoU 0.860, palm
  0.435; turnaround front 0.748/0.762, back 0.754/0.749, profile 0.584. B 0.245: 0.806, 0.376; 0.795/0.812,
  0.798/0.793, 0.537. C 0.26 (the widest palm keeping front/back at or above the comb's): 0.834, 0.402; 0.776/0.795,
  0.780/0.774, 0.556. A yaw scan (62 -> 45 at A's palm) doesn't narrow front/back (0.75-0.78), profile 0.58 -> 0.70,
  far hand 3q 0.71 -> 0.58. **Waiting on Michael: A, B or C.**
- **Next (after the palm call):** write the chosen palm_w and rest2's angles into the spec (setknobs.py), check back L
  cleftpos (keep it within WARN: a cleft at 0.56-0.62), then QA-only builds on the build box for the seam gap
  (tip_gap None / 0.003 / 0.006: fingerlines_* and the gaps), the chosen one on render2 with boards; `charkit handposes
  fit` on the final rest (poses per row); the review page (sheet | comb | hands2 | hands3 per pose and view, 3q rest
  close-ups); calibrate fingerlines_* (5 records) on the after-build; pregate --box auto; gate. The hands-only ink colour
  (a per-vertex outline ink: Blender line material, export attribute, our renderer, look.js) stays in what's left.

### Reframing (Michael, 2026-10-01, after the palm page): fixed structural ratios from landmarks; poses only validate
The palm page's widths were wrong: handsheet.palm_line took the silhouette's full width across the arm at 0.494 of the
reach, so a thumb crossing the line (the relaxed back-of-hand views) counted as palm, and one tucked edge-on (the
turnaround's front and back) didn't: the "disagreement" was thumb pose. Using posed hands as structural references is
fraught. **The hand engine is built from fixed structural ratios read off landmarks (thumb excluded), and posed
drawings only validate poses** (joint angles; IoU after posing is a check, not the structure's fit). Addendum: every
finger's three segments and the thumb's (metacarpal from its CMC near the wrist, proximal, distal) as ratios of the
palm length, measured along the joint chain on the open hand (never as projected extents in posed drawings); a
standard-ratio prior per style profile (middle > ring ~ index > little; segments ~1 : 0.6 : 0.45; the thumb reaching
about the index's first joint adducted; anime slimmer and longer) as the default and sanity range: a character without a
hand sheet gets the profile's defaults scaled to its turnaround, one with a sheet refines them from its open hand; the
measure works from the wrist width too (c3's sheet can't be scaled by Clawd's cuffs). The superseded: palm_compare's
palm_line, JointFit's silhouette-IoU structure fit (kept as tools, not the structure's source).
- **Step 1 (landmarks, charkit/handsheet.py landmarks/web_lines; probe charkit/out/hands3/landmarks_probe.py, picture
  landmarks.png, numbers landmarks.json).** The sheet's OPEN hand (every landmark visible: the three finger webs = the
  silhouette's clefts): MCP span 1.064 cuff widths (the run along the MCP line, index's outer edge to the little's) /
  1.029 (4 x the webs' spacing); palm length (the cuff's edge to the middle MCP) 1.109; span / palm length 0.96 / 0.93;
  wrist at the cuff's edge 0.416 (0.375 of the palm length, 0.39 of the span); fingers MCP to tip over the palm length
  little 0.715, ring 0.827, middle 0.920, index 0.843; base widths 0.17-0.20 of it; the thumb's web at 0.74 of the palm
  length from the wrist, the thumb from its web 0.59, base width 0.22. Closed hands (webs from the drawn finger lines'
  starts): the turnaround's front L/R and back R show one line each (not measurable), back L two (0.51 cuff widths:
  not neighbouring lines), three-quarter L two (0.98), profile L three (0.82); the sheet's relaxed back picks the thumb's
  edge line, its fist the knuckle creases (1.52): unreliable. **Thumb out, the references don't measurably disagree**:
  where the turnaround shows the webs (profile L, 3q L) its MCP span is 0.82-0.98 cuff widths against the open hand's
  1.03-1.06 (the drawn lines start below the true webs, profile and 3q foreshorten); the 0.437 vs 0.31 "disagreement"
  (29%) was the thumb. The open hand is the structure's source; the turnaround sets the size.
- Against an anatomical prior (to be set per style profile): span / palm length 0.93-0.96 vs ~0.75-0.85 and wrist / span
  0.39 vs ~0.65-0.75 fall outside: the palm length and the wrist are read at the cuff's edge, and the cuff hides the
  wrist crease (the visible palm starts lower; the visible "wrist" is the cuff's opening). Fingers: middle 0.92 of the
  palm length (anatomy ~0.75-0.85; anime longer), order middle > index 0.843 ~ ring 0.827 > little 0.715. The open
  hand draws no joint creases on its fingers, so the segments along the joint chain need the creases elsewhere (the
  relaxed and point hands' finger lines) or the prior's 1 : 0.6 : 0.45.
- **Steps 1-5 (coordinator: proceed).** Merged pipeline-3d 27a4b6c (0d86390; hands2 already in it as 60c0f1a). Box jobs
  now go to `--box auto` (the freest box): a job reading an earlier output names its box (`--box build`: hands2_after_q,
  the known-bad stores live there).
- **The prior:** charkit/styles `hand` ([default, lo, hi] per ratio over the palm length; anime: middle 0.92 [0.78,
  1.05], span 0.82 [0.7, 0.9], wrist 0.65 [0.5, 0.85], taper 0.6, thumb_w 0.21). Not widened to fit Clawd.
- **The ratio template:** code_hand ratio mode (body.hand.palm_len set: from_ratios(hand_ratios(spec), palm_len,
  wrist_offset)): palm_len the size, wrist_offset 0.034 (Clawd's wrist line is the cuff's edge), segments from the
  ratios (the prior's 1 : 0.6 : 0.45, thumb 1 : 0.7 : 0.55).
- **The landmarks, thumb-invariant** (handsheet.digits picks the thumb out: the radial-most digit of five, or one whose
  cleft is well nearer the wrist; a finger's base only at a web shared with another finger; the wrist line under a cuff
  is the cuff's edge, the first row the hand shows; a covered wrist isn't read). The sheet's open hand (ratios_of):
  span 0.925, middle 0.917, index 0.916, ring 0.899, little 0.777, taper 0.549, thumb 1.31, thumb_w 0.22. Flags against
  the anime prior: span (0.925 > 0.9) and thumb (1.31 > 1.15), both read from the cuff's edge (the palm short); the
  wrist not measurable (cuffed).
- **fit_ratios** (the template's ratios moved by the measured difference, our open hand drawn and read alike; no
  silhouette IoU): within ~0.01 in 2-3 iterations; the template's ratios span 0.900, middle 1.096, index 0.948, ring
  0.932, little 0.857, taper 0.443, thumb 1.907, thumb_w 0.233, wrist the prior's 0.65 (charkit/out/hands3/
  fit_ratios.json). They differ from the measured ones because the template places joints and the measure reads the
  webs (distal of the knuckles) and the wrist line's corner.
- **The check: QA part hand_sheet** (charkit/handsheetqa.py): handsheet_open_span (4 x the finger webs' spacing over the
  palm length, ours minus the sheet's; 0.05/0.10), handsheet_open_fingers (0.05/0.10), the posed IoUs INFO.
  Calibration (charkit/calib/handsheet.py; calibrate's new `invariant` list: a generator the check must not see, else
  'confounded'): the design 0 at every move; floors wide_palm +0.30, narrow_palm -0.23, long_palm -0.22 (fingers -0.45);
  **thumb_only (the thumb alone turned 10-30 deg) 0.000-0.0096 in all 5 seeds** (before the fixes: 3 seeds unmeasured,
  one -0.145 on the index's base, one -0.058 through the wrist line). Known-bad comb_hand (its spec's template).
- **ratio2** running (build box): palm_len + rest angles, the ratio1-era ratios; rerun with fit_ratios.json's after.
- **ratio2 invalid** (the ratio mode derived the knobs once at params(): palm_len moved to its bound with no effect);
  fixed (code_hand.geometry: derived when the hand is built; test_ratio_mode_is_live).
- **ratio3** (charkit/out/hands3/ratio3, fit_ratios' ratios, palm_len live): reach right (errors < 0.03 L), palm_len
  0.314; but fit-scale IoU front 0.626/0.637, back 0.630/0.629, 3q 0.781/0.490, profile 0.545 (the comb's QA 0.76-0.77
  front/back: -17%, the guard) and gaps 0.03-0.05. Cause: the template's thumb, fitted to the open hand's wrist-corner
  to tip distance (1.31 PL measured -> 1.907 template), came out 0.6 L long: that one measure can't separate the thumb's
  length from its angle, and its CMC is under the cuff. **The thumb takes the prior (1.0 PL), flagged** (single local
  evaluations, ratio3's angles: thumb 1.0, thumb_down 10: front 0.707/0.727, back 0.723/0.717, 3q 0.780/0.751, profile
  0.602, gaps 0.027-0.057 WARN). Still ~6% under the comb's front/back.
- **ratio4 RUNNING** (build box: `remote --box build run ... hand fit`, charkit/out/hands3/ratio4, log ratio4.log):
  the prior thumb, knobs palm_len, curl, spread, thumb_out, thumb_down, bend, dev, overlap; floors the comb's + 0.02.

## Checkpoint (2026-10-01 evening, ~750k context): exact next steps for a relaunch
1. Read ratio4 (charkit/out/hands3/ratio4/fit.json). If front/back stay under the comb's QA (0.761/0.769, 0.754/0.771)
   by more than ~0.02, that is the turnaround and the sheet disagreeing on the rest silhouette with the structure from
   landmarks (the canonical rule's step 3): report per-view costs to the coordinator rather than move the structure off
   the sheet's landmarks. The fingertip gaps (0.03-0.06 at rest: the sheet's slimmer tips, taper 0.44) can be held by
   `overlap` (in ratio4's knobs) or tip_gap negative; keep every graded hand check out of FAIL (hands2 is the base now:
   back L cleftpos WARN 0.054 must not FAIL).
2. Write the spec (setknobs.py or by hand: body.hand = palm_len, wrist_offset 0.034, ratios (fit_ratios.json's with
   thumb 1.0, wrist the prior's), overlap, rest angles, yaw 61.88, out 5.5, line 1.0, tip_gap, fans 0, thumb_across 0.3).
   Then `handsheet.fit_ratios(spec, over)` again at the new rest (the open pose is posed from the rest) and rewrite the
   ratios; the hand_sheet checks (handsheet_open_span / _fingers) should then PASS on our hand.
3. `charkit handposes fit --poses relaxed,fist,point` on the box (pose validation only: angles, IoU per row) and record.
4. Builds: render2 with boards (`remote --box render2 build charkit/spec/clawd.json --out charkit/out/hands3_after
   --boards body,design`), optionally a tip_gap variant (0.004) to measure the seam lines (fingerlines_*: the paddle
   read 0.72-0.83 FAIL). Push the chosen build to the build box (`infra/gcp/build.sh push` with CHARKIT_BOX_ENV=build.env)
   and re-push the known-bad stores there (comb_hand, mitten, paddle_hand under charkit/out/calib/builds).
5. Calibrate on the build box: `remote --box build run --fetch charkit/calib/records calibrate
   'fingerlines_*,handsheet_open_*' --build charkit/out/hands3_after` (7 records). The hand_* checks aren't remeasured
   since hands2 (handqa unchanged but its DECLARED_CHECKS literal).
6. Review page (charkit review page): the open hand with its landmarks and ratios drawn (landmarks_probe.py's picture),
   ours vs the sheet per pose (handposes picture), the rest close-ups in 3q (hands_board, hands_close), before (comb,
   hands2_base) | interim (hands2_after) | hands3; then `python -m charkit pregate --box auto` and `remote gate
   tool/hands2 --into pipeline-3d` (merge pipeline-3d first).
7. What's left beyond: the hands-only ink colour (a per-vertex outline ink through the Blender line material, the export,
   charkit/render and look.js); c3's hand sheet (handsheet.cells needs a cuff for the wrist line: the uncuffed path,
   the narrowest run, exists in landmarks(cuffed=False); scale by wrist width: palm_len_over_wrist).
- **ratio4 landed, degenerate** (charkit/out/hands3/ratio4): the DE ran to curl 29.7 (its bound), dev -19, overlap 0.33,
  palm_len 0.369 (the fingers curled shut to close the gaps): fit-scale IoU front 0.551/0.558, back 0.573/0.566, 3q
  0.675/0.522, profile 0.659. Worse than the single evaluation at ratio3's angles with the prior thumb (front 0.707/0.727,
  back 0.723/0.717, 3q 0.780/0.751, profile 0.602; ratio_start4.json with thumb_down 10). **Next rest fit:** start there,
  Powell only (no DE), the curl bounded to about [-10, 12], overlap and dev fixed (0, ratio3's -2.2), knobs palm_len,
  curl, spread, thumb_out, thumb_down, bend; if front/back still sit ~5% under the comb's QA, report the per-view costs
  (the sheet's landmark structure vs the turnaround's rest silhouette) to the coordinator before going further.

## Round 7: land hands3 (relaunched 2026-10-01 night; coordinator brief: finish and land, scope tight)
**Michael's decision (2026-10-01): ACCEPT** the rest pose against the turnaround's front and back ~5% under the comb
(0.71-0.73 vs 0.76-0.77): inside the 15% guard; those views draw the hand narrow by convention; the structure comes from
the open hand. Record it as a named acceptance (charkit/accepted/) for whichever hand checks the gate lists. No further
polish: deferred to the dexterity phase (the hands-only ink colour, the cuffless path for other characters, polish).
- Merged pipeline-3d ae865afc (8c862fb9: rom suite, hair truth). rom reads the fingers (finger_finger inside, the
  knuckles' volume): watch its report-only rows at the gate.
- `charkit hand fit --bounds '{"curl": [-10, 12]}'` (this run's knob bounds).
- ratio_start4 evaluated (charkit/out/hands3/start4.log): IoU front 0.707/0.727, 3q 0.780/0.751, profile 0.602, back
  0.723/0.717; **cleftpos FAILs front L/R and back L/R** (ours 0.745-0.768 vs drawn 0.565-0.644: the thumb near
  parallel, thumb_out 3.8; hands2 PASSes them at 0.61-0.63), gaps 0.027-0.057 WARN, taper front 0.51 vs 0.40 WARN.
  ratio4's degenerate path was the FAIL_COST cliff: curling the fingers shut escaped these FAILs.
- **rest3** (build box, job hand-hands-1001-194909-df46, charkit/out/hands3/rest3, log rest3.log): Powell only from
  ratio_start4, knobs palm_len, curl [-10, 12], spread, thumb_out, thumb_down, bend; overlap 0, dev -2.22 fixed; floors
  hands2's QA views x 0.93 (charkit/out/hands3/floors_rest3.json).
- **rest3 landed** (cost 2.60 -> 2.18): palm_len 0.3166, curl 2.53, spread 0.58, thumb_out 9.45, thumb_down 2.93, bend
  -11.47; IoU front 0.703/0.722, 3q 0.779/0.706, profile 0.609, back 0.713/0.708; gaps 0-0.014 PASS, taper PASS; but
  **cleftpos still FAIL front L/R, back L/R** (the pocket jumps: 0.96-0.97 L, 0.013-0.017 R vs drawn 0.57-0.64). The
  prior thumb (1.0 PL = 0.31 L from the cuff's edge) ends ~0.35 L past the wrist; hands2's (PASS) ended ~0.445 L. The
  sheet's own reading is 1.31 PL (from the wrist line, flagged > the prior's 1.15): the fit_ratios loop's 1.907 was the
  measure confounding length with angle, not the sheet.
- **rest4 / rest4p RUNNING** (build box; charkit/out/hands3/rest4 DE 25 x 70 + Powell, rest4p Powell only): from
  rest3's angles with thumb_out 14 and the sheet's thumb 1.31 PL (rest4_start.json), knobs + `ratios.thumb` [1.0, 1.4]
  (code_hand: a structural ratio as a fit knob), bounds palm_len [0.29, 0.34], curl [-10, 12], spread [-3, 5],
  thumb_out [0, 35], thumb_down [0, 30], bend [-20, 10].
- **rest4p chosen** (charkit/out/hands3/rest4p; written to the spec in the ratio mode, rest_final.json, 3f4d7a9c):
  palm_len 0.3116, curl 4.45, spread 0.13, thumb_out 12.26, thumb_down 1.57, bend -1.46, dev -2.22; **the thumb's ratio
  fitted 1.302 PL against the sheet's own reading 1.31** (an independent agreement; the prior's 1.0 left the cleft
  FAILing). Fit-scale IoU front 0.708/0.724, 3q 0.806/0.803, profile 0.585, back 0.729/0.716; gaps 0; taper PASS;
  cleftpos front 0.621/0.611 (drawn 0.644/0.639), 3q L 0.660 (0.622), back 0.613/0.607 (0.565/0.616: L WARN 0.048, as
  hands2's 0.054), profile FAIL as before. rest4 (DE, cost 0.632) fixed the profile cleft (0.69 vs 0.736) but 3q R
  0.675 and back L cleftpos 0.053 at the FAIL edge, thumb 1.38: not taken.
- **Merged pipeline-3d 348397e7** (689f4108; batch4: the joined shoulder on): both specs conflicted on body.hand (taken
  pipeline-3d's with hands3's hand: setknobs), declared.inputs(hands=, body=). The QA denominators: `hands` declares 42
  (unchanged), `hand_sheet` now declares 2 + 2 x 4 poses = 10, fingerlines_* count in `declared`'s computed count.
- **poses2 RUNNING** (build2, job handposes-hands-1001-203742-6ebe, charkit/out/hands3/poses2): open, relaxed, fist,
  point fitted per row on the new rest. Then: POSES['open'] from it, `charkit handsheet ratios --over rest_final.json
  --keys span,middle,index,ring,little,taper,thumb_w` (the thumb kept: the measure confounds its length and angle),
  the build.
- **poses2** (build2; charkit/out/hands3/poses2, on rest4p): fitted per row, IoU back / side (poses1 before): open
  0.667 / 0.709 (0.640 / 0.548), tips 5/5, 3/3; relaxed 0.823 / 0.803 (0.874 / 0.620); fist 0.861 / 0.716 (0.799 /
  0.654), reach 0.73 vs the sheet's 0.80; point 0.699 / 0.795 (0.714 / 0.685). Fitted angles: open spread 12.1, thumb
  spread 24.8, oppose 14.9 (its curl -18 hyperextends to chase the reach: not taken); fist MCP 39, PIP 111, DIP 23,
  thumb oppose 69; point index -2.6, others 74/112/37. POSES['open'] now flat on the rest (curl -4.45) with poses2's
  fan and thumb; fist and point stay the library's (anatomical: 85/95/60), graded by hand_sheet's INFO rows.
- **ratios2** (`charkit handsheet ratios`, build2; charkit/out/hands3/ratios2): converged within 0.004-0.008 in 4-6
  iterations (the thumb kept); middle 1.096 -> 1.035, span 0.900 -> 0.891, taper 0.443 -> 0.425, thumb_w 0.233 ->
  0.261; index/ring/little within 0.005. **rest5 RUNNING** (build box; charkit/out/hands3/rest5): the size and rest
  angles refit at these ratios (Powell from rest_final, rest5_start.json).
- **rest5** (charkit/out/hands3/rest5; at ratios2's ratios): palm_len 0.3203, curl 3.05, spread 0.78, thumb_out 13.97,
  thumb 1.22 PL; fit-scale IoU front 0.691/0.705, back 0.705/0.692, 3q 0.793/0.784, profile 0.591; cleftpos all within
  PASS/WARN but profile. **Not built:** front/back under Michael's accepted 0.71-0.73. Built **rest4p** (the spec as
  committed; its open hand read on the flat open pose: middle +0.058 PL over the sheet's (handsheet_open_fingers WARN),
  span +0.017, index/ring/little within 0.004; charkit/out/hands3/open_landmarks.png/.json). The page asks A (rest4p,
  built) or B (rest5). Coordinator (Michael, end of session): no further fits or sweeps; land it.
- The library's poses on the built hand (`handposes grade`, charkit/out/hands3/poses_lib): open 0.644 / 0.679, relaxed
  0.870 / 0.727, fist 0.675 / 0.608 (its reach 0.53 of the open hand vs the drawn fist's 0.80: the library's 85/95/60
  curls tighter than the drawing's fitted 39/111/23), point 0.667 / 0.720. Dexterity phase.
- **Builds RUNNING:** charkit/out/hands3_after (boards body,design; auto box; log charkit/out/hands3/after.log) and its
  QA-only twin charkit/out/hands3_after_q (build box; after_q.log). Then: calibrate 'fingerlines_*,handsheet_open_*'
  on the build box against hands3_after_q, the review page (charkit/out/hands3/review/page.json), the acceptance,
  pregate --box auto, gate.
