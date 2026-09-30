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

- Before build (pipeline-3d 08f93e2, render box): `charkit/out/look4_before` (`--boards views,body --vrm`), running.
