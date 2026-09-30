# Gate-loop redesign (tool/infra3, 2026-09-30 night)

Worktree `~/animation-pipeline-infra3`, branch `tool/infra3` from pipeline-3d 08f93e2. The brief: ROADMAP "Iteration
speed: the gate loop", the handoff's "Overnight run plan" item 1. Targets: a gate on a branch that can't change geometry
in 2 min or less; a geometry-changing gate in 5 min or less; local iteration about 1 min on the laptop.

## State (read first when resuming)

Milestone A (a-f) done and gated; waiting for the coordinator's merge and go-ahead for milestone B (g-l).
- Gated: 472df97 into pipeline-3d a3073f5: **PASS** with pipeline-3d's gate code (`gate_tool-infra3_472df97_into_a3073f5`,
  no check changed, 52 test files ok), and **PASS under K** with this branch's gate code on the same commit
  (`gate_tmp-infra3-self_472df97_into_a3073f5`, no check changed, one note).
- pipeline-3d then moved to 1141e74 (tool/toonrender2). Merged here (bf161b1): conflicts in charkit/cli.py (the build's
  step timers around toonrender2's toon boards: kept both, the toon boards timed as their own step) and
  charkit/remote.py (usage lines: both kept); gate.py auto-merged (toonrender2's cross_qa fallback check). Unit tests
  pass; not re-gated (the coordinator decides).
- Throwaway test branches tmp/infra3-* and tmp/hair4-gated: deleted.

## Milestone B (in progress, 2026-09-30 night)

Subset 1 (g, the baseline finding, the boards), code done, unit-tested, being gated:
- (g) **A gate carries over when pipeline-3d moves.** The report's json now holds three closures: the baseline's, the
  candidate's and each test file's (the tests run with CHARKIT_CLOSURE, one log per file, packed as indexes into one
  path list). `python -m charkit gate --carry BRANCH [--into pipeline-3d]` (laptop, no box, no build) finds the newest
  report of the branch's tip into an ancestor H0 (this worktree's charkit/out/gate, then every worktree's), checks the
  merge into the new head with `git merge-tree`, and carries the verdict when no change H0..HEAD reaches the baseline's
  closure and no difference between the two merged trees reaches the candidate's. The test files a difference reaches
  (and test files added) run again here, in a throwaway sparse worktree of the merge (a commit object no ref names); a
  failure there makes it a FAIL. It writes gate_TAG_into_HEAD.{md,json,summary.json} with `carried`. Exit 0 PASS, 1
  FAIL, 3 not carried (gate it). In the gate itself the same test reuses an earlier candidate of the same tip
  (`_cand_reference`: its merged tree from `git merge-tree H0 TIP` against this merge's index), as the baseline already
  was, so a re-gate after a move is tests only.
- **The first gate into a fresh commit** (the smoke-docs finding, 705 s for a one-line doc): a merge that changes only
  docs/ and charkit/tests/, or docs files no nearby closure read or listed (`closure.unreadable`), builds nothing,
  not even the baseline. When the baseline must be built, the candidate starts beside it only if the newest baseline
  closure (a nearby commit's) is reached by the merge; otherwise it waits for the baseline's own closure.
- **Boards:** gate builds pass `--boards ''` (the toon boards took 16 s a build, nothing in the gate reads them).

## What changed (milestone A)

**(a) Michael's policy K in gate.py.** The verdict is PASS or FAIL. FAIL (blocking) only on:
- the merge conflicting, a test failing, a build failing (as before);
- a new FAIL: a check that PASSed or WARNed on the baseline and FAILs on the candidate. A check the branch adds that
  FAILs is reported (bucket `new_failing`), not blocking: it measures a fault, it doesn't make one. (The first cut
  counted new checks too: rejudging the box's 148 old reports turned many PASSes into FAILs on checks like
  body_*_boot_step that shipped at FAIL, so it was wrong for K's intent, a relaxation.)
- a regression in a flag check: a check whose qa.json entry carries `flag` (charkit.registry.FLAG; `registry.flag_check`
  sets it, `registry.is_flag` reads it; artifactqa marks its CALIBRATED checks). Its status or its calibrated grade
  gets worse, or it goes. The grade matters: an unpromoted flag check's status is capped at WARN, so only the grade
  can show it going past its FAIL limit.
- the build's CPU over 1.5x the baseline's.
- the 2x2's drops (a remeasured check worse under one measure on both geometries) only when they end at FAIL under that
  measure or are flag checks; --accept still exempts by name.

Everything else goes to the report's "Report (not blocking)" section, by kind: warn (PASS -> WARN), new_failing,
flag_values (flag checks' value moves), values (value moves, the biggest relative first), gone, new, improved, removed,
remeasured, twobytwo, notes. The machine-readable summary is `gate_..._into_HEAD.summary.json` next to the .md (and
`summary` inside the .json): verdict, verdict_pre_k (what the old rules said), why, blocking, report, counts, build
decision, CPU, tests, phases. `python -m charkit gate --rejudge 'PATTERN'` reads old reports under K (the flags from the
two builds' qa.json when they're still in gate-out).

**(b) The absolute hair path.** trace.portable(): the knob hashes and the spec_hash are taken on the spec with paths in
the build's own folder as `<out>/...` and paths in the worktree relative, so "knobs hair changed" and the spec_hash
change no longer show in every gate. The Blender hair stage's cache key was already portable: cache.Recorder.facet runs
spec reads through `_out_rel` (hair.shape.pieces keys as `<out>/geom/hair_pieces`, its files by content). Not portable
(milestone B, item h): the venv file steps' keys. pieces_hair's `cut` carries head_code and body_code as absolute paths
in the out folder, and file_step keys `inputs` by absolute path, so those steps never hit across two out folders or
clones.

**(c) No build when nothing the build reads changes (charkit/closure.py).** A gate's build records its input closure:
with CHARKIT_CLOSURE set, importing charkit installs an audit hook in every charkit process of the build (the venv's
`charkit build`, its Blender, the QA), logging each file under the worktree opened for reading (modules by their .py),
written (outputs), listed by charkit's own code, or run as a script. The registry's scans for `@qa_part(` and
MEASUREMENT_STEPS are recorded as scans (a file there counts when its old or new text has the marker), and the cache's
look for edited sources is paused (it isn't an input). The gate keeps OUT/closure.json: the tracked files read, the
untracked inputs by sha256 (charkit/out/i3d), the listed folders, the scans. A change reaches the build when it's a file
read, in a listed folder, a scanned file with the marker, an untracked input with other content, or a data file (not
Python, not docs) in the checkout: Blender's C code reads images and libraries the hook can't see, so data counts
anyway. Python the build never imported, docs and tests don't.
- The candidate isn't built when no change reaches the baseline's closure: only the tests run, and the report says so.
- The baseline itself comes from an earlier one (base_COMMIT of the same spec and options, newest first) when no change
  from COMMIT to head reaches its closure: base_HEAD becomes a link to it. So a docs or tooling merge into pipeline-3d
  doesn't cost the next gate a baseline build.
- When both must build, they build side by side in two worktrees, the tests alongside (CHARKIT_GATE_PARALLEL, default
  on 16+ cores). A candidate started beside an unfinished baseline is stopped if the baseline's closure then shows it
  can't differ.
- `--build` builds anyway. A baseline built before closure.py (all cached bases today) has no record: the gate builds.

**(d) Phases timed.** The report's "Phases" table: each phase's start and length (setup, merge, tests, baseline lock,
baseline build, candidate build, 2x2, compare), and "The builds by step": `charkit build` now prints `CHARKIT_PHASE NAME
SECONDS` for resolve, code_head, code_body, geom_hair, pieces_hair, garments_geom, blender (including the wait for a
slot), qa and sheets; the trace adds the Blender stages and the Blender/QA split. Tests run 8 at a time on the box
(CHARKIT_GATE_TEST_JOBS), each file's seconds recorded. A build's CPU is now os.wait4's (the build and what it
waited for), so tests running beside it don't count.

**(e) The VRM export.** Gate builds never ran it: `gate._build` doesn't pass --vrm, and no trace in the box's gate-out
has a `vrm` product (the 80 s in the ROADMAP comes from `remote build ... --vrm` runs). Now the export runs only when the
branch changes its code (gate.EXPORT_CODE, charkit/gltf.py): the candidate builds with --vrm and the export checks itself.

**(f) One live gate per branch.** `remote gate` lists the box's running jobs first and stops (`remote kill`) any gate of
the same branch and spec (--keep-older doesn't). The gate step has a trap: a killed gate removes its clone, its inputs
and its temporary files (TMPDIR is the clone's `.tmp`, where the gate's worktrees and the builds' scratch live).

## Numbers

**Before (the old gate, pipeline-3d 08f93e2's gate.py; build box shared with 3-4 other agents' jobs):**
`gate_tool-infra3_4789e12_into_08f93e2` (a docs-only commit):
- 778 s end to end (10:35:32 -> 10:48:18 UTC): waited 88 s for the baseline another gate was building (its build about
  437 s), tests 195 s (48 files one at a time), candidate build 483 s wall.
- The candidate build by step: resolve about 1 s, code_head 55 s, code_body 3 s, pieces_hair 176 s, garments 6 s,
  Blender 86 s (to the bundle), QA 154 s.
- Verdict WARN: "the build takes 2.3x the CPU time" (579 -> 1,331 s) on identical code. Under K that would block.
- Without a cached baseline, a gate is baseline + tests + candidate: about 1,115 s (18.6 min).

**After (this branch's gate code, the same shared box):**
- **A docs-only branch, the baseline cached** (`gate_tmp-infra3-docs3_cdd613c_into_82c8094`): **72 s** in the gate
  (setup 14 s: two sparse worktrees; tests 58 s, 51 files 8 at a time, 287 s of test time; no build), 89 s end to end
  from the laptop. Before: 778 s, and a spurious CPU WARN.
- **A docs-only branch into a commit with no baseline of its own** (`gate_tmp-infra3-docs2_ac7a220_into_4d0d9b5`: the
  target is 82c8094 plus a docs commit): the baseline is base_82c8094 (no change since reaches its closure; linked),
  the candidate isn't built: **69 s** in the gate, 86 s end to end. Before: a baseline build, tests and a candidate
  build, about 1,115 s.
- **An already-gated branch, re-gated** (`gate_tmp-hair4-gated_14d9e42_into_08f93e2`: tool/hair4's gated tip; the
  baseline cached from before the closure, so the candidate builds): 521 s (setup 17 s, tests 50 s beside the build,
  candidate 504 s wall). Before: the same gate took 319 s for the build plus about 195 s of tests one after the other.
  All 14 changed checks are identical to the old report's rows (values and statuses). K's verdict: FAIL on
  art_terminator_hair's grade (WARN -> FAIL, 2.376 -> 2.607), which `--rejudge` also reads from the old report
  (then PASS), and on the CPU (2.23x: 579 -> 1,291 s; the old run measured 379 s for the same build: see Findings).
- **Both sides built, side by side** (`gate_tmp-infra3-docs_42353c2_into_82c8094`, before the numba-cache fix): 749 s;
  the baseline and candidate built at once (730 and 709 s wall; 1,663 and 1,643 s CPU, 0.99x), the tests alongside
  (53 s). Each build's resolve took about 255 s: this branch changes charkit/cache.py, so the produced references
  (hull, outfit masks, hair layers), keyed on their producers' code two imports deep, missed the shared cache and
  were rebuilt (a one-off per such change). The candidate was built only because numba's cache files
  (`__pycache__/*.nbi`) counted as inputs: fixed (c8cdb4c), and the docs gates above then skipped it.

**This branch, gated (d5452dd into pipeline-3d a3073f5, which had moved to include tool/look4):**
- pipeline-3d's own gate code (the normal gate): **PASS**, no check changed, 52 test files ok; CPU 1,353 -> 512 s;
  1,109 s end to end (it built the baseline a3073f5 itself). `gate_tool-infra3_d5452dd_into_a3073f5.md`.
- this branch's gate code on the same commit (as tmp/infra3-self): **PASS** under K, no check changed, one note (CPU not
  judged: an uncapped cached baseline against a capped candidate, 0.49x); 1,059 s, of which 415 s waiting for the
  baseline lock the other gate held before starting its candidate build. Fixed after (af1477d): while another gate
  builds the baseline, the candidate now builds beside the wait (dry-run: the wait, the candidate stopped once the
  baseline's closure showed it the same).
- The trace diff still shows "knobs hair changed" and a spec_hash change: the baseline was built with the old trace
  code (absolute paths hashed). It goes once both sides are built with trace.portable().
- (f) live: a second gate of one branch stopped the first (exit 143, "stopped the older gate ... still running"), and
  the trap removed the stopped gate's clone, inputs and temporary files; the second then ran to PASS.

## Validation

- Unit tests: test_closure (the record from a real subprocess; which changes reach a build; changes between commits;
  pauses), test_gate (K's verdicts, the 2x2 under K, the report and summary, rejudge, the job label), plus the existing
  ones. A dry run of gate() with the builds stubbed exercised: an uncached baseline with a speculative candidate stopped;
  a cached baseline (tests only); a baseline taken from an equivalent earlier commit (linked); a code change (built);
  an export change (--vrm).
- `--rejudge` over the box's 148 reports in gate-out (both specs, since 2026-09-29): 72 PASS stay PASS, 62 FAIL stay FAIL
  (conflicts, failing tests, and real regressions to FAIL: hems, skirt overhang, hair_folds, face_folds,
  hair_penetration...), 8 FAIL and 3 WARN become PASS (PASS -> WARN moves, gone checks, slow builds under 1.5x), and
  three become FAIL: tool/geom-truth 851fd15 (CPU 1.78x, real), tool/infra3 4789e12 (CPU 2.30x, noise: docs only),
  **tool/hair4 14d9e42 (art_terminator_hair's grade WARN -> FAIL, 2.376 -> 2.607: a flag-check regression the old gate
  passed)**.

## Findings for the coordinator and Michael

- **Uncapped builds burn most of their CPU spinning, which made K's CPU rule noise; a gate's builds are now capped.**
  The same build measured 379 s and 1,291 s of CPU in two gates (tool/hair4 14d9e42, identical checks), and a
  docs-only candidate 2.3x its baseline. The A/B (two builds of clawd.json side by side on the loaded box, --cache off):
  uncapped 490 s wall, 1,313 s CPU; capped at 4 threads with OMP_WAIT_POLICY=PASSIVE 485 s wall, **527 s CPU**; outputs
  bit-identical (733 bundle arrays, 351 checks). So gate builds now run capped (gate.THREAD_VARS, 4 threads on the
  32-core box), each build records its cap in cpu_seconds.json, and K compares CPU only between builds with the same
  cap: a cached baseline from before this (uncapped) gets a note, not a block. The same caps for every build on the box
  (`remote build`, tunes) would cut the box's CPU by about 60% at no cost in wall time: that's item (i), next.
- **Tests run 8 at a time:** 51 files, about 280 s of test time, 50-58 s wall (test_geom.py alone is 46-49 s).
- **Flag checks: the grade counts.** Under K a flag check blocks when its calibrated grade gets worse even though its
  (capped) status doesn't: tool/hair4's PASS becomes a FAIL on art_terminator_hair. That's my reading of "regressions in
  the checks built from Michael's flags"; if Michael means status only, it's one line in gate.judge.

## Next steps

Milestone B after the coordinator's go-ahead:
- (g) carry a result over when pipeline-3d moves: the same test as the no-build path, the intervening commits'
  changes against the candidate's closure (the candidate records one now); a command for the integrator's queue.
- (h) shared stage caches across clones: the venv steps' keys need portable paths first (pieces_hair's `cut` holds
  head_code and body_code as absolute out paths; file_step keys `inputs` by absolute path).
- (i) a slot for the whole build, with the thread caps every build gets (not only the gate's): the A/B says about 60%
  of the box's build CPU is spinning. Add llvmpipe (LP_NUM_THREADS) now that the QA draws with charkit.render, measured
  bit-identical first.
- (j) the sampler at boot: the crontab line exists on the build box; check why it stopped, and the render box.
- (k) the masked-skin last bit (infra.md (c) cause 2), (l) the local pre-gate check.
- Smaller: create the baseline worktree only when it's needed (the tests-only path spends 7 of its 14 s of setup on
  it); a leftover clone from infra2's killed gate (/srv/work/gates/tool_infra2-2a85a869, from before the trap).
