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

- Before build (pipeline-3d 08f93e2, render box): `charkit/out/look4_before` (`--boards views,body --vrm`), done.
  After build (this branch at d7c8333: call M): `charkit/out/look4_after`, running.
- Call M code: 423e831 (shade.outline cap='measured', garments LINE_CAP_MEASURED = bow, boot; lookprobe --thickness;
  tests test_line_cap_measured (Blender stand-ins) and test_geomstage's boots). Not yet built.
- The known-bad builds re-measured with this tree's artifactqa (outfit masks from the local produced cache): body4b
  spikes_boots 0.0628, bumps_boots 63.1, bumps_legs 42.4, mirror_waist 6.425; body5b bumps_legs 42.4, mirror_waist
  6.915 (artifacts.md's numbers reproduce).
- bodyeval --knob-path (d7c8333): the measuring tool for item 3.

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
