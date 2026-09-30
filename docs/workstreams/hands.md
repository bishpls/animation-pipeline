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
- Step 3 (template), step 4 (weights): in progress.

## Local harness (charkit/out/hands/)
- `produce.py` (hull and masks produced locally), `run_handqa.py BUNDLE [OUT]`, `write_qa.py BUILD [QA]` (adds the
  hand checks to a build's qa.json for calibrate), `dbg_digits.py`.
- `charkit/out/calib/cur_mitten`: the mitten bundle (hard links) + a qa.json with the hand checks, for the dry run.

## Next steps
- Template (charkit/code_hand.py), weights, build on the box, calibrate records against the new build, pregate, gate.
