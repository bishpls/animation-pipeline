# Infra round 5, the build-cost half (tool/infra5-o, 2026-10-01)

Worktree `~/animation-pipeline-infra5o`, branch `tool/infra5-o` from pipeline-3d 60c0f1a4. The brief:
`~/animation-pipeline-3d/charkit/out/coord/brief_infra5.md`. Scope after the coordinator's split (15:45): tasks 1
(per-stage profile), 2 (budget, report only), 3 (cut costs), 4 (fail-fast tests in the gate), 6 (declared
denominators). tool/infra5-s owns 5 (calibrate PermissionError), 7 (stall alarm), 8 (sweep/optimize priority): this
branch doesn't edit calibrate.py, boxjob.py or the sweep worker launch. These notes are in their own file
(infra5o.md, not infra5.md) so the two halves' notes don't conflict.

## State (read first when resuming)

Started 15:38 EDT. Wall time per task is logged in "Time" below.

## Time
| task | start | end | notes |
| --- | --- | --- | --- |
| orientation, data | 15:38 | 15:50 | brief, code, the box's gate baselines' traces fetched |
| 1 instrumentation + `charkit profile` | 15:50 | 16:05 | per-stage CPU recorded; profile table on stored builds |
| 4 fail-fast, 6 denominators, 2 budget plumbing | 16:05 | 16:35 | code + unit tests (budget numbers wait on b0) |

## 1. Per-stage build profile

Data: the box's gate baselines (`/srv/work/gate-out/base_*_clawd_default`: trace.jsonl, build_cpu.json, qa/qa.json),
copied to `charkit/out/infra5/prof/`. Gate builds: thread cap 4, `--boards '' --no-blend`, the venv steps mostly
restored from the gates' shared step cache.

The creep (gate baselines, CPU s / wall s, box clock UTC): 09-30 18:23 25b1936 577/334; 20:42 2f42155 605/359;
10-01 03:41 ca489f3 820/532; 10:09 31689611 905/537; 12:35 ff41ca20 1038/641; 14:08 e9cb156a 1122/721 (motion QA
back); 16:59 25ff0f25 1310/787.

Per-stage CPU is now recorded (3842fe5e): cli._phases keeps each step's wall and CPU (this process and the children it
waited for) in build_cpu.json `phases`; trace.stage records `cpu` (Blender's process_time) and `snap`/`snap_cpu` (the
trace's own snapshot); every trace.span records `cpu`. `python -m charkit profile BUILD [--vs OTHER]` tabulates them
(older builds: QA parts' CPU from qa.json, Blender stages' wall only, `all but the QA` = total - QA).

**09-30 evening (25b1936) against today (25ff0f25), gate baselines** (`profile base_25b1936 --vs base_25ff0f25`):
total 577 -> 1310 s CPU, 334 -> 787 s wall. All but the QA (Blender and the venv steps): 209 -> 220 s CPU (flat).
**The QA: 368 -> 1090 s CPU (3x), 209 -> 609 s wall.** By part (CPU s): declared 0 -> 331 (new), look 100 -> 158,
artifacts 100 -> 121, motion 0 -> 105 (restored), face_flags 0 -> 81 (new), face_region 20 -> 38, hair_noise 23 -> 36,
skirt 25 -> 31, scalp 14 -> 24, sheet_body 12 -> 22, piece_details 17 -> 20. Blender walls: character 59 -> 80 s,
look_export 17 -> 28 s, garments 7 -> 12 s.

## 4. Fail fast in the gate (gate.py)

`_tests(on_fail=)` calls back the moment a test file fails; the gate's `on_fail` sets an event and stops the running
builds (their process groups); `build()` refuses to start once it's set and `_build(stop=)` stops a build that started
in the race; the baseline-lock wait polls (1 s) so it gives up too; after each wait (baseline, candidate, before the
2x2) the gate returns `tests_failed()`: the report names the failing tests (the rest still run to the end) and says the
builds were stopped, by which test, how far in. The tests-first path (machines under 16 cores) no longer builds after a
failing test. Tests: test_gate `test_fail_fast_*` (2).

**Demonstrated** (planted failing test, tmp/infra5o-failfast b7e92550 into pipeline-3d 59c93f38, `remote gate --code
tool/infra5-o`, job gate-infra5o-1001-155346-28b3; report charkit/out/gate/gate_tmp-infra5o-failfast_b7e92550_into_
59c93f38.md): **FAIL in 204.7 s** (setup 22 s; the first failing file 35.1 s in; the candidate build stopped 12.3 s
after it started, 10 s of CPU; the baseline-lock wait (another gate was building 59c93f38's) given up at the same
moment; the remaining tests ran to the end, 181 s, so the report names both failing files). Before: a failing test
was reported after both builds and the 2x2, 15-25 min (today's test_spec_alias / test_tune gates). The report's "why"
read "None" (the record was written after the event the gate wakes on): fixed, the record first.

## 6. Declared denominators (registry, qa3d.run, gate.judge)

`@qa_part(..., checks=N | f(B, design))`: how many checks the part measures (status other than SKIPPED). qa3d.run
records `measured.part_status` {part: status ok/short/crashed/skipped/undeclared, checks, expected, why} and
`measured.profile`. The gate (`part_findings`) blocks a candidate part that crashed, measured fewer than it declares,
or was left out by a QA profile, unless `--accept part:NAME`; the baseline's are reported. A qa.json from before (no
part_status) shows a crash by its SKIPPED entry with an exception's text. The declared part's count is computed from
its declarations and the design side only (declared.expected); motion's from the spec (2 per pose per loose skirt).
Tests: test_denominators.py.

## 3a. The iterate profile (motion QA)

`charkit build --profile iterate`, `charkit qa BUNDLE --profile iterate` (CHARKIT_QA_PROFILE): the parts declaring
`skip_in=('iterate',)` (motion) are reported SKIPPED "skipped by profile iterate" and part_status `skipped`; a gate's
builds never pass it, and a gate whose candidate skipped a part blocks.

Running: b0 = this branch (60c0f1a4 + instrumentation), default spec, `--boards '' --no-blend --cache off`, on the build
box into charkit/out/infra5/b0 (log charkit/out/infra5/b0.log).
