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

## Next steps (exact)
1. When b1 lands: `python charkit/out/hands/run_handqa.py charkit/out/hands_b1/bundle` (or read qa.json's hand_*);
   compare body_*_iou_skin, piece_cuff_*, piece_skirt*, skirt_* and the art_* flags against the mitten's
   (charkit/out/calib/builds/mitten/qa/qa.json) -- the default build's other checks must not move beyond noise.
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
