# Batch optimizer for fits (`tool/optimize`, 2026-10-01)

Worktree `~/animation-pipeline-optim`, branch `tool/optimize` from pipeline-3d ad081524.

Why (Michael, 2026-10-01): today's fits are tuned by an agent hand-stepping sweeps (sweep, read the table, design the
next sweep): face on sweep 8, lapels 7+, hair shells 11. Replace that loop with a batch optimizer (one launch, one
read). Precedent: tool/accessories5's `accfit place` (Nelder-Mead in-process on its own loss, one launch, ~550
evaluations a start, three starts; not merged).

## What it is (charkit/optimize.py; usage in its docstring)
- `python -m charkit sweep optimize DECL.json [--box] [--out DIR]` (also `sweep --optimize`): a sweep declaration
  (base, stage, spec, set, parts, objects, boards) with an `optimize` block: knobs (spec paths, or names a `template`
  combines with '=EXPR' arithmetic; bounds; int; log), objective terms on checks (toward 'pass' in warn bands from the
  check's limits: the term's, its declaration's (charkit.declared) or charkit.checks'; 'max'/'min'/'target' on a value
  or a view's IoU), constraints, budget, stop, probe, references, confirm.
- **Search:** CMA-ES of our own (numpy, Hansen's tutorial; no dependency), on the unit cube through reflection;
  integer knobs keep a least spread (no stalling on one value). Seeded per (seed, generation): ask() is a function of
  the state, so a run is reproducible and resumes exactly. `method: random` is a uniform baseline.
- **Constraints enforced, not weighted:** feasibility-first ranking (Deb): a candidate that breaks one ranks below every
  one that doesn't, by its violation; the best reported is always feasible. Against the control row: every piece's
  shape IoU per view within 15% (calibrate.DROP: the anti-gaming guard, every piece, not only the target's), no flag
  check's status or grade worse, no new FAIL, `keep` patterns stay PASS. Missing objective checks and failed rows are
  infeasible.
- **Parallel:** persistent workers (`sweep worker`), each in a build slot holding the stage's context (the garments
  Evaluator: ~1-2 min to make, paid once a worker, not once a generation), fed rows through the sweep's own stage
  classes, splice and measure; population sized to the free slots (less `--reserve`, default 1; at least 4 + 3 ln n).
  Every evaluation is written to history.jsonl as it finishes (the cache): an interrupted generation keeps its rows.
- **Probe:** before the search, every knob one step either side of the start: the splice set (what any probe changed,
  when `objects` isn't declared), dead knobs (a step that moves no check), each knob's local effect.
- **Multi-fidelity:** the screen is the sweep stage (fast evaluator, numpy drawing). Checks are fast-OK or real-only
  (FIDELITY / REAL_PARTS; `sweep optimize audit BUILD` measures numpy vs render per check on a build). Real-only
  objective terms are scored only at the confirm; real-only constraints are enforced on the screen as a proxy (against
  the control in the same drawing) and again on real builds. The confirm builds the top-k distinct feasible candidates
  (and the control when `set` changes the base) with `charkit build`, scores them with every term and constraint
  against the real control, and picks the best confirmed feasible.
- **Outputs:** history.jsonl / history.csv (every evaluation: knobs, objective and terms, broken constraints, every
  check, every piece's IoU per view), history.md, best_override.json (the sweep's `set` form), sensitivity.json/.md/.png
  (OAT probe, linear effect across the range and near the best, rank correlation per knob and per term, final spread),
  convergence.png, sweep.json (control, start, references, top 5 in the sweep's form: `sweep table`, review pages),
  confirm.json, review/ (charkit review page).
- `--box`: runs on the build box (`remote run --fetch OUT`), then makes the reports here. The declaration must reach the
  box: `charkit/out/remote/*.json` (synced) or a tracked folder.

## Usage (for agents)
```
# 1. declare: the sweep's fields + optimize {knobs, objective, constraints?, budget?, reference?, confirm?}
#    (example: charkit/out/remote/opt_stairs.json, below)
python -m charkit sweep optimize charkit/out/remote/my_fit.json --plan          # knobs, start, population, budget
# 2. one launch (background it; it reports when done):
python -m charkit sweep optimize charkit/out/remote/my_fit.json --box --out charkit/out/optimize/my_fit
# 3. one read: OUT/review/index.html (summary box), OUT/best_override.json, OUT/history.md, OUT/sensitivity.md
python -m charkit sweep optimize charkit/out/remote/my_fit.json --box --out charkit/out/optimize/my_fit --resume
python -m charkit sweep optimize report charkit/out/optimize/my_fit             # the reports again
python -m charkit sweep optimize audit charkit/out/MY_BUILD                    # fast-OK vs real-only per check
```
Rules of thumb: name the parts your knobs reach (the constraints hold over the parts measured); give integer knobs
for anything the builder snaps (fold positions, counts); use a `template` for ordered or coupled values (monotone
knots from gaps); put a hand-found result under `reference` to compare; leave `--reserve 1` so other agents' builds
get a slot; budget ~15-25 generations (population 16: 240-400 rows) for 5-10 knobs.

## State
- Code: charkit/optimize.py, `sweep optimize|worker` dispatch in charkit/sweep.py, charkit/tests/test_optimize.py
  (9 tests pass locally: CMA convergence and reproducibility, the integer floor, knobs and templates, scorer terms and
  every constraint kind with real-only routing, declared limits, a synthetic run that meets the anti-gaming trap and
  refuses it, resume after an interrupted generation equals the uninterrupted run, the subprocess pool equals the
  in-process evaluator, a qa-stage run through the sweep's own stage).
- Synthetic, 10 seeds (constrained optimum 0.0176, start 0.49): CMA-ES median best 0.033 at 100 evaluations, 0.021 at
  200; the random baseline 0.108 / 0.067. Constraint ranking variants (Deb, static and adaptive penalty, stochastic
  ranking) tried: within noise of each other at 200-400 evaluations; Deb kept (strict).
- Base build of the head (ad081524, default spec) on the build box: `charkit/out/opt_base` (fetched; 14 min).
- **Fidelity audit** on opt_base (`charkit/out/optimize/audit_opt_base/audit.md`): 639 checks, every part; 10 read
  differently numpy vs render (face shadows, terminator bow/collar, art_band_lower 1.111 / 1.238, ink fragments 2-4%);
  the palette and the eyes read the same. FIDELITY updated from it.
- **Smoke run** (`charkit/out/optimize/stairs_smoke`, 8 workers, 26 evaluations, 9 min): end to end on the box. Splice
  set from the probe: skirt + both flaps. Rows 70-150 s (the build 0.2-16 s; the measure dominates: declared 82 s and
  artifacts 42 s of wall in the build's own QA). `ref_hand` (the hand result's knobs) reads f 0.5 on the screen: only
  stair_flaps_front_corner WARN, as the hand loop's local rebuild read it (4.0 W). Fixed after: probe labels at a
  bound, the boards' folder.
- Busy box: the first full launch found 16 of 16 slots held (hair-shell sweeps): sized to 1 worker, killed. Now the
  pool is dynamic (workers join as they get slots; at least 4 queued).
- The second launch (10 workers queued on the build box, job sweep-optim-1001-103226-7799) waited behind the hair-shell
  sweeps; killed on the coordinator's word (render2 had 9 of 10 free). Built in: `--box auto` (every running box's free
  slots over ssh: remote.box_slots / boxjob `slots`; the build box while it has 4 free beyond the reserve, else the
  most free), the base pushed to a box whose copy lacks it, the minutes budget counted from the first ready worker.
  At launch: build 0 of 16 free (6 waiting), render 3 of 3, render2 7 of 10 -> render2.
- **Running:** the staircase acceptance with `--box auto` (render2), out `charkit/out/optimize/stairs`, log
  `charkit/out/optimize/stairs.log` (the job id is in the log). If the local follow dies: `python -m charkit remote
  --box render2 attach JID`; resume: the same command with `--box render2 --resume`.

## Next steps
1. Read the staircase run (OUT/review, opt.json, confirm.json); compare with the hand loop (st1-st5: 5 sweeps, ~42
   rows, 4 harness scripts, 05:38-06:22 local on 2026-10-01 plus code changes later removed).
2. Acceptance review page; pregate; gate (tooling: no check should move).
