# Incremental builds, round 1 (tool/incremental, 2026-10-01)

Worktree `~/animation-pipeline-incr`, branch `tool/incremental` from pipeline-3d 348397e7. The brief:
`~/animation-pipeline-3d/charkit/out/coord/brief_incremental.md` (gitignored; the parts used are copied below). Outputs:
`charkit/out/incremental/`; harnesses that run on a box live in `tools/incremental/` (charkit/out isn't synced to the
boxes).

The coordinator (20:45, Michael, end of session): land items 1 (budget re-baseline + blocking rule, with a test), 3 (the
iterate default) and the design doc through one gate. Item 2 (the QA's drawing on the GPU) lands only if its readings
verify identical within this pass; otherwise the measured state and exact next steps go here and it stays off the
default. Nothing in the landing may move a check reading (the day's production build and preview run after the merges).

## State (read first when resuming)

Started 20:38 EDT. Commits: 39238efb (items 1 and 3, the doc draft), 8a86c5d4 (budget.json re-baselined), then the QA's
adapter record (qa.json measured.draw.adapter, the gate's report line). `codediff.measure_changes(348397e7, HEAD)`: 0
parts (no measuring code changed).

Running (collect them):
- `qa_r2`: tools/incremental/qa_adapters.py on render2, br's bundle drawn on lavapipe (cpu) and the L4 (gpu) side by
  side (job script-incr-1001-210549-c3bb; fetched to charkit/out/incremental/qa_r2/adapters.json; log qa_r2.log).
- `bv`: a geometry variant (charkit/out/incremental/clawd_variant.json: body.shoulder.fall 0.1 -> 0.14, the collar's
  v_depth 0.5 -> 0.42) built on render2 into charkit/out/incremental/bv (log bv.log): the second geometry of the 2x2
  (CPU and GPU drawing on both geometries). Next: the harness on bv (cpu,gpu), then the 2x2 table.
- pregate (`pregate --box auto`, log charkit/out/incremental/pregate.log).

Next: the gate, `remote gate tool/incremental --into pipeline-3d --code tool/incremental` (gate.py changes: the budget
rule and the 2x2's crossed QA runs at CHARKIT_QA_PROFILE=full are exercised only with this branch's gate code).

## Item 1: the budget's blocking rule (done)

- gate.budget_rule: blocks when the candidate's figure is > 1.10 x budget.json `total` AND > 1.05 x its baseline's
  figure. The figure (gate.budget_basis): the build's CPU with each cached venv step it restored counted at
  budget.json `cold`, and `resolve` (plus code_head, which reuses the head the hull's build computed) at their cold
  figures when it built the shared produced references. The merged tree's budget.json is read (a merge raises it in
  review). The report: a line with both figures and what was counted, the per-stage table (report-only) under it.
- Box speed: not scaled. Measured on one commit: build2's CPU seconds ~0.93x the build box's (gate 3's candidate 1455
  vs bb 1554 on the basis), render2's 1.35-1.65x for numpy and Blender work (Blender 187 -> 251, hair_select 68 -> 113,
  rom 155 -> 243), not remote.py's CPU_SPEED (the picker's 1.25 for build2). gate.cpu_speed reads CHARKIT_CPU_SPEED for
  a measured factor later; nothing sets it. The baseline half (same box, same gate) keeps the difference from blocking.
- Re-baseline (pipeline-3d 348397e7 = batch4 d5a916a7's tree): bb, the build box, `--cache off`: 1717.9 s CPU (1156.7
  s wall); resolve built the produced references (225.9 s) and code_head reused the head (0.02 s); on the basis 1554 ->
  total 1555. cold: code_head 55 (gate 3 51.5 on build2, br 59.9 on render2), code_body 4, hair_select 68,
  pieces_hair 229, garments_geom 22, resolve 7 (br, produced restored). Per-stage figures ~15% over bb's (report only;
  qa/rom added: 155 s, the second dearest QA part).
- Test: test_gate `test_budget_rule_blocks_over_the_budget_and_the_baseline` (blocks over both; over the budget alone or
  the baseline alone doesn't; restored steps and rebuilt references don't move the figure; the shipped budget's keys).

## Item 3: the iterate profile as the default (done)

- `python -m charkit qa BUNDLE`: 'iterate' unless --profile or CHARKIT_QA_PROFILE says otherwise; prints
  `CHARKIT_QA_PROFILE iterate: motion skipped (reported SKIPPED; --profile full runs it)`; qa.json reports motion
  SKIPPED 'skipped by profile iterate' and part_status skipped (infra5o's machinery).
- optimize's confirm builds: `--profile iterate` unless confirm.profile / confirm.args say otherwise or an objective
  term or keep pattern reads a motion check (then full); the skipped part's checks (the base build's record, the
  prefix, the SKIPPED key) are left out of the comparison on both sides; confirm.json `profile`, `skipped`; logged.
- Gates and full builds keep everything: gate._build sets CHARKIT_QA_PROFILE=full; gate.cross_qa (the 2x2's crossed
  runs of `charkit qa`) too. A build's QA is qa3d.measure (not main): 'full' unless --profile.
- Tests: test_denominators `test_a_qa_only_run_defaults_to_the_iterate_profile` (the four cases, the announcement,
  the gate's crossed run's env), test_optimize `test_confirm_builds_run_the_iterate_profile_unless_a_term_reads_motion`.
- Saving (infra5o, the QA-only pair): motion 24-31 s CPU per QA-only run (105 s on a loaded box).

## Item 2: the QA's drawing on a GPU (measured; see below)

Same code, same bundle (bb and br: 962 bundle arrays, 0 differ), the QA drawn on the build box's CPU rasteriser (bb)
and on render2's L4 (br, the `auto` adapter there):
- **Readings: 753 of 758 identical.** 5 differ, all INFO, no status or grade change: art_terminator_boots 5.41 ->
  5.679 (grade FAIL both), face_shadow_3q 0.2825 -> 0.2824, face_shadow_chin 0.6234 -> 0.6231 (grade FAIL both),
  face_shadow_neck_3q 0.0781 -> 0.0782, hair_tone_edges 0.0766 -> 0.0763. Same 77 frames drawn.
- **CPU and wall** (QA, bb -> br): 981.6 -> 774.0 s CPU (-21%), 609 -> 719 s wall (+18%). The drawn parts: declared
  207.8 -> 86.3, look 130.9 -> 31.8, artifacts 101.0 -> 16.5, hair_noise 70.3 -> 27.0, face_flags 61.2 -> 28.3, scalp
  19.9 -> 10.8: 591 -> 201 s CPU (-66%) despite render2's slower cores. The numpy parts got slower on render2: rom
  154.6 -> 242.7 (its draws aren't the cost), motion 31 -> 49, skirt 23 -> 37, sheet_body 26 -> 34, hands 19 -> 28.
- Whole build: 1717.9 -> 1472.8 s CPU raw; on the budget's basis 1554 -> 1473 (-5%); wall 1157 -> 1194 s.
- Gates already land on render2 by the auto pick (7 of today's gates in the worktrees' job records), where `auto`
  draws on the L4: those 5 INFO readings have depended on the box all along (within a gate both builds share a box).

## The brief (copied)

1. Budget blocking rule: re-baseline charkit/budget.json on today's default (1455 s measured against 1450), then block
   when the build is >10% over budget.json AND >5% over its baseline; a test.
2. QA drawing on a GPU box: readings identical (a gate pair, every check side by side); any moved reading is a remeasure
   (charkit/steps/, the 2x2, flag statuses unchanged); checks that can't match stay on the CPU path; QA wall and CPU
   before and after.
3. `--profile iterate` the default for QA-only runs and sweep confirm builds; motion QA skipped explicitly and reported;
   gates and full builds keep everything.
4. docs/INCREMENTAL.md: Parts 1 and 2 (per-piece content-addressed stage graph, QA checks declaring reads, the local
   piece studio, checkpoint gating with bisection, the three verification layers), grounded in infra5's profile and
   today's cost, ending with lean follow-up rounds and their acceptance.
