# Batch optimizer for fits (`tool/optimize`, 2026-10-01)

Worktree `~/animation-pipeline-optim`, branch `tool/optimize` from pipeline-3d ad081524.

Why (Michael, 2026-10-01): today's fits are tuned by an agent hand-stepping sweeps (sweep, read the table, design the
next sweep): face on sweep 8, lapels 7+, hair shells 11. Replace that loop with a batch optimizer (one launch, one
read). Precedent: tool/accessories5's `accfit place` (Nelder-Mead in-process, one launch, ~550 evaluations, 3 starts).

## Plan
1. `charkit sweep optimize DECL.json` (charkit/optimize.py): the sweep declaration plus an `optimize` block (knobs with
   bounds, continuous or integer; objective terms on checks; constraints enforced by feasibility-first ranking: the
   shape guard per piece and view, flags not regressing, no new FAIL, named checks kept).
2. CMA-ES of our own (numpy; no new dependency), population sized to the free slots; persistent workers (each holds
   the stage's context: the garments Evaluator is ~60-90 s to make) fed rows through the sweep's own stages, splice
   and measure.
3. Multi-fidelity: the sweep stage (fast evaluator, numpy drawing) screens; the top-k feasible are confirmed by real
   builds; checks marked fast-OK or real-only (an audit measures numpy vs render drawing on a build).
4. Outputs: best override, history (every check and guard IoU per evaluation), convergence plot, per-knob sensitivity,
   review page. Deterministic seeds; resume from history; early stop.
5. Acceptance: reproduce the garments staircase knobs (tool/garments4-stairs st1-st5, hand result deg4_sq2) from the
   pre-stairs knobs in one launch; tests (synthetic objective, constraints, resume); pregate, gate.

## State
- Started. Base build of the head on the build box: pending.
