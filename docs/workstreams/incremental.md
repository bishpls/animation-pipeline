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

Started 20:38 EDT.

Running:
- `bb`: cold default build on the build box (`remote --box build build charkit/spec/clawd.json --out
  charkit/out/incremental/bb --boards '' --no-blend --cache off`; log charkit/out/incremental/bb.log): the CPU drawing
  (llvmpipe), the budget's cold figures.
- `br`: the same on render2 (log charkit/out/incremental/br.log): the QA drawn on the L4 (render2's wgpu `auto` adapter
  is the L4 through Vulkan; probe: tools/incremental/probe_adapters.py).

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
