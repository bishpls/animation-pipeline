# merge/batch4: finishing the coordinator's batch merge

`merge/batch4` in `~/animation-pipeline-3d` (the integration worktree) = pipeline-3d ae865afc + infra5-o (gate
machinery) + tool/hairshell3's code (default switch off) + tool/garments4-shoulders (the joined shoulder ON by default,
its garment regressions accepted by name in charkit/accepted/). The coordinator merges it into pipeline-3d; nothing here
is pushed.

## What this round fixed (99232882, b72b5bbf)

1. **Acceptances covering a batch's branches.** `charkit gate` and `charkit remote gate` take `--batch BRANCH,...`
   (passed through to the box by `remote.gate_passthrough`); `calibrate.covers(rec, branch, batch)` accepts a record
   whose branch is the gate's or one in the batch; the report carries `rep['batch']` (a line under the verdict, the
   summary json, and each accepted row's branch). A flag check's acceptance still pins its reading
   (`_accepted_reading`). Tests: `test_calibrate.py::test_a_batch_merge_takes_its_branches_acceptances`,
   `::test_the_gate_cli_passes_the_batch`.
2. **artifacts measured 57 of the 58 it declares.** The missing check was `art_terminator_neck`. Not a stale count and
   not a crash: the joined shoulder leaves the neck lit under the chin (the neck's shade share 0.24/0.25/0.18 ->
   0.018/0.026/0.001 front/three-quarter/profile; its terminator 0.043/0.043/0.0 L against the base's 0.49/0.40/0.12),
   under the 0.05 L (`MIN_TERM`) the detector needs in every view, and `artifactqa.checks()` dropped the check with no
   reason. Now kept: INFO, no value, `why` and the lengths (`_one_tone`), whenever ours is one tone where the design
   has a terminator; a region ours doesn't draw at all is still left out (the denominator then reports it). Step
   registered (`charkit/steps/artifactqa.py`, `art_terminator_neck`, 99232882). Recomputed from both gate builds'
   stored tables: base 58 unchanged (every check identical), candidate 57 -> 58. Test:
   `test_artifactqa.py::test_a_region_in_one_tone_keeps_its_terminator_check`.

## Gates

| gate | tip | verdict | blocks | report |
| --- | --- | --- | --- | --- |
| 1 (coordinator) | 224ba8db | FAIL | 16 accepted records not applied (branch mismatch); artifacts 57/58 | `charkit/out/gate/gate_merge-batch4_224ba8db_into_ae865afc.md` |
| 2 | b72b5bbf | FAIL | 1: the 2x2 couldn't measure `art_terminator_neck` (the old measure dropped it on the new geometry) | `charkit/out/gate/gate_merge-batch4_b72b5bbf_into_ae865afc.md` |
| 3 | d5a916a7 | **PASS** | nothing (`art_terminator_neck` accepted; job gate-3d-1001-201211-1c8c) | `charkit/out/gate/gate_merge-batch4_d5a916a7_into_ae865afc.md` |

Gate 2: the 16 acceptances apply through `--batch`; the parts' denominators are met; 109 test files pass; build CPU
1627 -> 1457 s (0.90x; the 1450 s budget, report-only, 1.00x). Michael's standing call ("switch the joined shoulder and
accept the regression", relayed by the coordinator) covers `art_terminator_neck`: recorded in
`charkit/accepted/art_terminator_neck.json` (branch merge/batch4) and added to `--accept` for gate 3 (the 2x2's
unmeasured cell is covered by `--accept` only; the gate can't re-read a stored report with an extra accept, so gate 3 is
cold with the same arguments).

Gate 3 (cold, the gate's code from merge/batch4, the same arguments plus `art_terminator_neck` in `--accept`): PASS
under K, nothing blocks (before K: FAIL); 16 acceptances applied through `--batch`; the parts' denominators met (only
`declared`'s over-count reported); 109 test files pass; build CPU 1627 -> 1455 s (0.89x; the budget's 1450 s total,
report-only). Ready for the coordinator's merge into pipeline-3d (ae865afc, unmoved). Later commits here are notes only.

The full suite (`pytest charkit/tests`, one process): only the three known order-dependent failures (test_optimize qa
stage, test_registry order, test_denominators every part declares; each passes alone). A run under `nice -n 10` also
fails test_slotprio's background-niceness test (the starting niceness is the run's: an artefact of the run, passes
plainly).

## For Michael (via the coordinator)

- The joined shoulder took the neck's chin shadow away (shade share 0.24 -> 0.02 front): the design draws it in all four
  views. Accepted under his standing call; recovery belongs to garments round 8 (the joined shoulder's owner).

## Infra item (separate from this gate)

- **`declared` measures 55 against a computed 47** (the gate's parts table: "measures 55, declares 47"). The 8 extra
  are tool/garments4-shoulders' bodyshoulderqa declarations (`body_shoulder_{front,back}_{top,side,iou}`,
  `body_axilla_{front,back}`), declared with `piece='skin'`; `declared.expected()` counts a declaration only when every
  piece is in the outfit graph's piece map (and its mask drawn), and `skin` (the bare body sheet) is neither, so they
  are measured but never expected: if they stopped measuring, no shortfall would show. Fix: count `skin` as present
  where the body sheet's bare figure is (as HAIR is wherever the view is drawn), and test it against the 55.
