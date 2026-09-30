# Look round 4 (`tool/look4`, from pipeline-3d 08f93e2)

A small round, one gate (default spec only, policy K):
1. **Michael's call M:** the bow and the boots get the outline cap at half their measured thickness (look.md round 3's
   experiment: flips at the body boards' width bow 501 -> 144, boots 2 x 113 -> 2 x 39). The crab and star unchanged.
2. **Promote four flag checks WARN -> FAIL:** art_spikes_boots, art_bumps_boots, art_bumps_legs, art_mirror_waist,
   if they still hold on the merged tree (bad build >= 2x clean, current passes). art_points_sleeves,
   art_bumps_sleeves and art_band_lower stay at WARN (the garments round).
3. **Investigate:** does `bodyeval.Evaluator.assembly` evaluate body-knob changes on MakeHuman's body when the spec's
   body is the code body (tool/nofallback's finding)?
4. **Gate once.**

## State

- Branch `tool/look4`: call M (423e831), the bodyeval fix (e12f6cc), the promotion (f0f4286). pipeline-3d still
  08f93e2 at the gate. Review page: `charkit/out/look4_review/index.html` (the bow and boots on the body boards, EEVEE
  and charkit.render, before | after | change at 3x, and the tables below).
- Builds (render box, `--boards views,body --vrm`, charkit/spec/clawd.json): before = pipeline-3d 08f93e2
  (`charkit/out/look4_before`), after = this branch at d7c8333 with call M (`charkit/out/look4_after`).

## Item 1: call M (the bow and boots capped at half their measured thickness)

- `shade.outline(..., cap='measured')`: a closed thin piece without a shell modifier gets `ck_line_cap` = SHELL_CAP
  (0.5) x `shade.measured_thickness` (look.md round 3's measure, now in the code: per vertex of the evaluated mesh,
  outline off, a ray along the inward normal to the far side within 5 cm; the p5 of the hits, to the micrometre), and
  keeps the thickness in `ck_line_thick`. `garments.LINE_CAP_MEASURED = ('bow', 'boot')` asks for it; geomstage records
  the kwarg (replayed in Blender, shown in the evaluator's view). The crab and star (accessories.py) are unchanged.
  Everything downstream already reads `ck_line_cap` through `shade.line_cap`: set_view's offsets, the bundle's
  `outline.cap`, the VRM's `outline.maxInward` and charkit.render's inward move and normals.
- Measured at the build (outline time) = measured on the saved scene (`lookprobe --thickness`), to the micrometre:
  bow 2.654 mm (cap 1.327), boot_L 4.913 (2.4565), boot_R 4.907 (2.4535); look3's experiment read 2.654 / 4.913 /
  4.907. At the build width (1.2 mm) and the face boards' (0.93) the caps don't bind; at the body boards' (3.62) the
  bow's surface moves 1.327 mm in and its hull 2.29 mm out, the boots' 2.46 in and 1.16 out.
- **Flips** (`lookprobe --normals`, faces whose shading turns > 90 degrees, outline on against off; laptop):

  | piece | body width: before | after | build width: before / after |
  |---|---|---|---|
  | bow | 501 | **144** | 22 / 22 |
  | boot_L + boot_R | 113 + 113 = 226 | **39 + 39 = 78** | 0 / 0 |
  | crab_1, star_0 (not capped) | 260, 8 | 260, 8 | 0 / 0 |
  | all garments | 9193 | 8688 | 5756 / 5756 |

- **Across renderers** (`python -m charkit.render compare BUILD`: charkit.render on the laptop's M2 against the box's
  EEVEE boards): face boards identical before and after (both renderers bit-identical to themselves: the caps don't
  bind there); body boards before mean 0.839-0.871 lv, > 8 lv 0.321-0.460%, after 0.837-0.869, 0.316-0.442% (a hair
  closer), silhouette IoU 0.9991-0.9993, tones agree 0.9993-0.9996. What changed between the builds (> 8 lv) is a
  thin band along the bow's and the boots' outlines: EEVEE 3341-6369 px a body board, charkit.render 3342-6349, the two
  change masks' IoU 0.957-0.968. The bow's line now sits partly outside it (about 1.4 px on the body boards; the boots
  0.7 px), as call I did for the thin garments.
- **The QA.** The bundles' geometry is identical (every object's V and shrink); only `outline.cap` is new on the bow and
  boots. The QA's design-scale drawings (lookqa._scaled, line scale 3.1 x the build width, 3.73 mm) now cap them too,
  so the art_* measures that see the bow and boots moved (no measure changed, so no 2x2): calibrated
  art_bumps_boots 13.3 -> 11.0 PASS, art_mirror_self_boots 0.511 -> 0.497 PASS, art_outline_collar 4.435 -> 4.234 WARN,
  art_fragments_collar 8.775 -> 6.495 WARN, art_points_sleeves 28.0 -> 27.9 WARN; INFO: art_outline_bow 0.846 -> 1.027,
  art_fragments_bow 0.56 -> 2.12 (profile), art_terminator_bow none -> 6.0 (front: the bow's own shading is drawn
  now; before, its surface pulled 3.7 mm into a 2.65 mm piece and the view showed mostly its line), art_fragments_top
  1.58 -> 2.60, art_outline_top 5.08 -> 4.92, art_terminator_boots 4.82 -> 5.16, art_peeks_collar 3 -> 2,
  art_bumps_skirt/flaps +-0.1. line_width (INFO) unchanged at 1.133.

## Item 2: four flag checks promoted to FAIL

Re-verified on this tree (call M in): the known-bad builds re-measured with this code (`artifactqa.measure` on their
bundles; outfit masks from the produced cache) against the after build's QA:

| check | known-bad | current (after M) | ratio | promoted |
|---|---|---|---|---|
| art_spikes_boots | body4b 0.0628 L | 0.0133 PASS (pass <= 0.015) | 4.7x | yes |
| art_bumps_boots | body4b 63.1 deg | 11.0 PASS (13.3 before M) | 5.7x | yes |
| art_bumps_legs | body4b 42.4, body5b 42.4 | 0.0 PASS | inf | yes |
| art_mirror_waist | body4b 6.43, body5b 6.92 | 1.19 PASS | 5.4x | yes |

`artifactqa.PROMOTED` holds the four (their grade is their status); points_sleeves (28 WARN), bumps_sleeves (45.6,
graded FAIL, shown WARN) and band_lower (2.16, graded FAIL, shown WARN) stay capped for the garments round. Note:
art_spikes_boots' current 0.0133 is the template boots' known borderline back spike, 0.0017 L under the pass line (a
move over it reads WARN, not FAIL; FAIL is over 0.025).

## Item 3: the evaluator's body knobs on the code body (measured, fixed)

Measured with `python -m charkit bodyeval --knob-path BUILD/clawd.spec.json --knob PATH=V` (d7c8333: Evaluator.assembly
at the knobs against character.assemble at the knobs, the build's own code; vertices, joints, head frame, and the
shape checks by the fast path and by a fresh evaluator). On the before build's resolved spec (clawd.json, base code,
body.source code), `body.proportions.leg` 1.07038 -> 1.12:
- **Before the fix: IndexError.** Evaluator.assembly sends every non-anime base's body-knob change to `compose`, which
  builds the new body with MakeHuman's `body.build_body_data` (13380 vertices) and indexes it with the assembled code
  body's head weights (18478): `V1[pure]` raises. So the evaluator never evaluated a body knob on MakeHuman's body
  silently; it could not evaluate one on the default spec at all (bodyfit's body knobs, and validate's 'body' timing
  probe, on any code-body build). It enters at `Evaluator.assembly`'s `base_of(spec) != 'anime'` test.
- **What a real assembly does with that knob: nothing.** The code body (`code_body.build_body_data`) reads only
  `body.height_m` and `body.heads_tall`; `body.proportions.*` and `body.pose.*` are MakeHuman's (body.py). Assembled
  afresh with leg 1.12: every vertex and joint 0.0 m from the base.
- **Fix (e12f6cc):** compose only when `body_source(spec) == 'makehuman'`; the code body's knobs assemble afresh
  (~25 s cold, cached by the assembly key). Test: `test_body_knobs_compose_only_on_makehumans_body` (fails without
  it). After it, leg 1.12 + heads_tall 6.0: fast path = fresh assembly to 0.0 m (the knobs move the assembly
  mean 15.6 mm, max 31.9 mm; L 0.2500 -> 0.2447).
- **Open, for the body-fit owner:** at those knobs the fast path's shape checks differ from a fresh evaluator's on
  the same assembly: shape_iou_torso 0.933 vs 0.943, shape_iou_hair 0.912 vs 0.905, ref_iou 0.661 vs 0.659 (the
  composed tolerance is 0.01). Not attributed; the likely cause is the documented carry of the hair selection across
  body knobs (module doc). And bodyfit's `body.proportions.*` / `body.pose.*` knobs do nothing on a code body: a fit
  on clawd.json should drop them (only height_m / heads_tall move it, and those are held).

## Gate (1b91cfc into pipeline-3d 08f93e2, default spec)

`python -m charkit remote gate tool/look4 --into pipeline-3d`: **WARN**, "the build takes 1.8x the CPU time".
Report: `charkit/out/gate/gate_tool-look4_1b91cfc_into_08f93e2.md`. Every test ok (test_line_cap_measured and the
new test_geomstage / test_bodyeval / test_artifactqa cases included). Read under K:
- **New FAILs: none.** No check changed status.
- **Flag-check regressions: none.** The calibrated ones held or improved: art_bumps_boots 13.3 -> 11.0 PASS,
  art_mirror_self_boots 0.511 -> 0.497 PASS, art_outline_collar 5.679 -> 2.836 WARN, art_fragments_collar
  8.39 -> 6.45 WARN, art_points_sleeves 28.0 -> 27.9 WARN; the four promoted ones pass (spikes 0.0133, legs 0,
  mirror_waist 1.19 unchanged).
- **Build CPU 579.3 -> 1046.0 s (1.8x), over K's 1.5x.** Attributed to a produced-reference rebuild, not the build:
  the hull's produced-cache key covers charkit modules this branch edits (bodyeval.py, shade.py), so a candidate
  rebuilds the hull once. The render box shows it: before build `hull: hit` (its build 178 s saved), after build
  `hull: miss ... built in 195.7 s`; locally the hull's key changed with the bodyeval.py edit alone. Blender + QA
  time 234.2 -> 265.1 s (1.13x, wall, on a shared box); on the render box the whole Blender side 236.3 -> 234.1 s and
  the garments stage 7.7 -> 8.9 s (the three thickness measurements). The gate's clone is cleaned up, so its own
  log isn't kept to split the 467 s exactly. Once pipeline-3d holds these files the hull is cached again.
- **WARN / INFO moves** (all from the bow and boots now drawn with the cap in the QA's design-scale drawing, line
  scale 3.1x): INFO art_fragments_bow 0.74 -> 2.12, art_outline_bow 0.90 -> 0.97, art_terminator_bow new 6.0,
  art_fragments_top 1.59 -> 2.60, art_outline_top 5.08 -> 4.92, art_terminator_boots 4.82 -> 5.16,
  art_fragments_boots 0.77 -> 0.64, art_peeks_collar 3 -> 2, art_bumps_collar/flaps +-0.1, art_outline_boots +0.001.
  These are INFO detectors, not calibrated on a flag.
- **Finding (noise):** art_outline_collar reads 5.68 (build box) and 4.44 (render box) for the same commit 08f93e2,
  and 2.84 / 4.23 with call M: the collar's outline corners are not stable across boxes (or builds). A calibrated
  WARN check; worth a look before it is promoted.
