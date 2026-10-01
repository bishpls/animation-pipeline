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
| orientation, data | 15:38 | | brief, code, box baselines' traces fetched |

## 1. Per-stage build profile

Data: the box's gate baselines (`/srv/work/gate-out/base_*_clawd_default`: trace.jsonl, build_cpu.json, qa/qa.json),
copied to `charkit/out/infra5/prof/`. Gate builds: thread cap 4, `--boards '' --no-blend`, the venv steps mostly
restored from the gates' shared step cache.

The creep (gate baselines, CPU s / wall s, box clock UTC): 09-30 18:23 25b1936 577/334; 20:42 2f42155 605/359;
10-01 03:41 ca489f3 820/532; 10:09 31689611 905/537; 12:35 ff41ca20 1038/641; 14:08 e9cb156a 1122/721 (motion QA
back); 16:59 25ff0f25 1310/787.
