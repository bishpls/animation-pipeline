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
- pipeline-3d 07f305e8 merged (1a460c72): `charkit.accfit` is in the tree now.

## Acceptance (a): results
Review page: `charkit/out/optimize/acceptance/review/index.html` (page.json and make_page.py beside it).

**The staircase knobs** (run `charkit/out/optimize/stairs`, declaration `charkit/out/remote/opt_stairs.json`, render2,
job sweep-optim-1001-104211-9b37). Knobs: the three knot gaps (int degrees; a template keeps the knots monotone), two
heights, the fourth step's drop, the flaps' square; start = the pre-stairs spec (knots 14/28, no fourth step, square
0). Objective: the six declared stair checks toward PASS. Constraints: guard 15% every piece and view, flags, no new
FAIL, keep skirt_pleats* and skirt_panel_*.
- One launch, one read: 221 evaluations, 17 generations of 12 on 6 workers, 60.5 min (rows ~90 s), stopped on
  the target (all six PASS on the screen) at generation 16; then 3 real builds (control, g16_01, g16_10) on render2,
  13 min. The probe found the splice set (skirt + both flaps) and one dead knob at the start (g3: the fourth knot is
  flat while its drop is 0, as expected).
- **Real builds (render drawing), against the real control:** g16_01 (knots 11/21/34 deg, heights 0.21/0.16/0.11,
  square 2.28): crossed 0 / 0, skirt corners 2.9 / 1.6, flaps 2.1 / 0.0, all PASS (control 2 F / 1 F, 8.9 F / 6.0 F,
  11.4 F / 18.8 F); art_band_lower [F] 1.185 -> 1.085 PASS; skirt_pleats, skirt_panel_*_creases unchanged;
  flap_profile_sweep_R W -> P; worst piece shape IoU move -0.1% (piece_overskirt_panel_L profile), flaps front +2.6%.
  g16_10 the same (flaps 1.4 / 0.0).
- **The hand result** (tool/garments4-stairs: knots 13/23/33, 0.25/0.15/0.10, square 2.0; its real build = opt_base):
  the same except stair_flaps_front_corner 4.0 WARN. The hand loop's knob phase: 5 sweeps (st1-st5, 42 rows), 4
  harness scripts, 2 code changes tried and removed, 05:38-06:22 (44 min) with the agent in the loop. Its screen
  reading reproduced by the run's ref_hand row (f 0.5: only the flaps' front WARN).
- Caveat: opt_base predates the clips merge, the confirm builds don't: the hand column's compare row reads
  acc_crab_profile_iou FAIL against the merged control (clips, not stairs).
- Not applied: the optimizer's knobs beat the hand result on one check (flaps front 4.0 W -> 2.1 P); a garments
  follow-up if Michael wants it (asked on the page). Tooling moves no check.

**The clips placement on accfit's own loss** (`charkit/out/optimize/clips_cma`, declaration
`charkit/out/remote/opt_clips.json`; NM baseline `charkit/out/optimize/clips_nm`, job accfit-optim-1001-111439-7440;
comparison `charkit/out/optimize/acceptance/clips_compare.{py,json,png}`). Same start (start_A), same scene (opt_base's
hair, the merged spec), 14 knobs as accfit.fit_place's.
- accfit place (Nelder-Mead, one process): 1,407 evaluations in 25 min, loss 11.25 -> 5.523.
- optimize (CMA-ES, 4 workers): reached 5.523 at 646 evaluations, 3.3 min; converged at 797, loss 5.494, 4.2 min
  total (two resumes with larger budgets: --resume carries a budget-stopped run on).
- At matched evaluations: 100: 7.08 vs 9.98; 200: 6.95 vs 8.74; 400: 6.17 vs 7.25; 600: 5.60 vs 6.09.
- Per view (crab iou / visible): optimize 0.727/0.736/0.716, 1.0/0.998/0.992; NM 0.764/0.789/0.679, 0.991/0.990/0.985;
  star iou optimize 0.545/0.831/0.785, NM 0.501/0.731/0.815; star back px 3 vs 19. No clip IoU fell >15% from the start.

## Next steps
1. Pregate, then `remote gate tool/optimize --into pipeline-3d` (tooling: no check should move; sweep.py,
   optimize.py, remote.py, boxjob.py, codemap.py are outside the build).
