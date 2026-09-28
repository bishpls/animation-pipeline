# tool/bodyfit: status

This branch fits the body, garments and hair to the model sheet. It was branched from pipeline-3d at 4fbfb92, and
pipeline-3d was last merged at 9df8b5e. The method is in docs/CHARKIT.md §4: the fast evaluator, the sensitivity
table, the rest pose, bundle-shaped measurement, and fitting.

## Done

### Phase 1

- **The fast evaluator** (`charkit/bodyeval.py`, with `charkit/bodyeval_blender.py` for the Blender dump). It builds
  every object the build does in numpy and measures the same way the QA does.
- **Validation against the final fitted build** (`python -m charkit bodyeval --validate charkit/out/bf_fit2`, PASS):
  - objects within 7e-8 m, and evaluated garments (Solidify, then Subdivision Surface) within 4e-7 m, vertex for
    vertex;
  - shape and ref IoUs within 0.002;
  - silhouettes agree at 0.997 IoU per view;
  - 93 of 93 model-sheet checks (body, palette and face) grade the same;
  - about 90x faster: 0.5 s per garment knob and 1.6 to 2 s per body knob, against 143 s in Blender.
- **Bundle-shaped measurement** (`charkit/bodymeasure.py`). Shape and ref IoU, the sheet's body, face and palette
  checks, per-piece extents and the scalp all take a bundle.
- **Sensitivity and inventory** (`charkit/bodysens.py`). It covers every body, garment and hair knob and flags the
  measurements that need a capability.

### Phase 2

- **Rest-pose knobs** (`body.pose`: `arm_down`, `elbow`, `leg_in`; `body.rest_pose`). They are exact at 0, and the VRM
  export's bind pose and T-pose are unchanged. The final build exports its VRM without errors.
- **The fitter** (`charkit/bodyfit.py` on `charkit/fitkit.py`, with facefit's `declare()`/`fit()` interface).
  `fitters.BodyFitter` registers it for the tune loop. It includes:
  - the outfit graph's draft, ties and piece extents;
  - authority weights, and hold terms for the face;
  - repair and line repair;
  - the palette, including the new garment `shade` knob.
- **Three fixes found on the fitted build and made this session:**
  - **The head is held** (`bodyfit.hold_head`). The body knobs set `height_m` and `heads_tall` so that MakeHuman's head
    keeps its scale and L; the head count follows from the proportions. Before this, the body knobs moved the face skin
    by up to 12 px at the eye QA's scale, which flipped eye_lid_span from WARN to FAIL. With the hold, the face stays
    within 0.03 px and eye_lid_span is 1.107 WARN, identical to the baseline. `--free-head` restores the old
    behaviour.
  - **The Solidify is ported** (`bodyeval.recalc_normals` and `bodyeval.solidify`). The evaluator lacked the garments'
    thickness, so it read sheet_neck_to_jaw as 0.94 PASS where Blender read 1.41 FAIL. `validate` now also compares the
    evaluated garments.
  - **Geom-mode hair is cut per body for the checks the fit is judged by** (`Evaluator.exact_geom`, group 'all'). Each
    group's own optimisation carries the start's cut. Face hold terms are now measured in the details group; before,
    they always read GONE there.
- **The fitted spec is in `charkit/spec/clawd.json`**, from `charkit/out/bodyfit/clawd13`. The final Blender build is
  `charkit/out/bf_fit3`; the baseline build is `charkit/out/bf_base3`.

## Before and after, in Blender QA (bf_base3 against bf_fit3)

| family | before | after |
|---|---|---|
| shape_iou | 0.588 FAIL | 0.741 WARN |
| ref_iou | 0.549 | 0.660 |
| body_* (49 graded) | 10 PASS, 7 WARN, 32 FAIL | 20 PASS, 14 WARN, 15 FAIL |
| palette_* (13 graded) | 5 PASS, 6 WARN, 2 FAIL | 11 PASS, 1 WARN, 1 FAIL |
| face sheet_* | 2 PASS, 8 WARN, 1 FAIL | the same (neck_to_jaw 1.123 WARN) |
| eye_* | 5 PASS, 2 WARN, 1 FAIL | the same (lid_span 1.107 WARN) |

There are 27 improvements and no regressions. Body knobs changed:
- height 1.55 m becomes 1.468 m, and heads_tall 6.2 becomes 5.87 (both derived, since the head is held);
- leg 1.07, torso 0.86, hip 0.95, leg_slim 1.10;
- arm_down 11.1°, leg_in 5.7°, elbow 2.2°.

The garment changes and the added back panels are in the spec diff.

## Not done yet (next steps, in order)

1. **Merge pipeline-3d (now eaf0ec8)** and resolve conflicts. The last ones were in `charkit/cli.py` and
   `docs/CHARKIT.md`, and keeping both sides resolved them.
2. **Run all tests.** Every `charkit/tests/test_*.py` passed on this commit, before the merge.
3. **Run the gate:** `~/animation-pipeline/.venv/bin/python -m charkit gate tool/bodyfit --into pipeline-3d`. It has
   not been run.
4. **Refresh the sensitivity table** (`python -m charkit bodysens charkit/spec/clawd.json`, about 30 min in geom
   mode). The copy in `charkit/out/bodyeval/clawd/` was made before the Solidify port.
5. **Optional: the hair group** (`--pieces hair`). In geom mode its knobs are skipped, because each extraction takes
   30 to 60 s.

## Known issues and capability gaps (from the triage)

- **body_*_top:** the buns sit lower than the sheet's, and no knob reaches them because the generated TRELLIS hair
  carries them.
- **Hair width:** about 12 % narrower (three_quarter 0.854 WARN). `shoulder_x` barely moves it.
- **Front and back IoUs, skin IoU, legs:** these are trade-offs; the triage lists them as "needs a knob" or
  "trade-off".
- **body_three_quarter_hem_mid:** the design's front opening panel is shorter.
- **skirt_width:** fragile where the hands are excluded.
- **palette:** the iris is texture-driven (owned by the eye fit), and the cream shade is not kept.
- **Pixel-level fragility:** eye_lid_span depends on one pixel of lash connectivity, and sheet_neck_to_jaw on one
  skin row. A fit that moves the head or the collar can flip them, which is why the head is held.

## How to resume

```
cd ~/animation-pipeline-bodyfit
PY=~/animation-pipeline/.venv/bin/python
$PY -m charkit bodyfit charkit/spec/clawd.json --out charkit/out/bodyfit/NAME --palette \
    --baseline charkit/out/bf_base3/qa/qa.json [--pieces figure,details] [--no-draft] [--budget 150]
$PY -m charkit build charkit/spec/clawd.json --out charkit/out/bf_NEXT --vrm
$PY -m charkit bodyeval --validate charkit/out/bf_NEXT
```

For the pre-fit spec, use `git show 4ac9b4f:charkit/spec/clawd.json`.
