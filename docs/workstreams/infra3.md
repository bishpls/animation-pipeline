# Gate-loop redesign (tool/infra3, 2026-09-30 night)

Worktree `~/animation-pipeline-infra3`, branch `tool/infra3` from pipeline-3d 08f93e2. The brief: ROADMAP "Iteration
speed: the gate loop", the handoff's "Overnight run plan" item 1. Targets: a gate on a branch that can't change geometry
in 2 min or less; a geometry-changing gate in 5 min or less; local iteration about 1 min on the laptop.

## State

Milestone A in progress: (a) Michael's gate policy K, (b) the resolved spec's absolute hair path, (c) no build when
nothing the build reads changed, (d) the gate's phases timed, (e) the VRM export, (f) one live gate per branch.

## Baseline (before)

Measuring: the current gate (pipeline-3d's gate.py) on this branch's docs-only first commit, on the idle build box.
