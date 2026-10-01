# Infra round 5, the build-cost half (tool/infra5-o, 2026-10-01)

Worktree `~/animation-pipeline-infra5o`, branch `tool/infra5-o` from pipeline-3d 60c0f1a4. The brief:
`~/animation-pipeline-3d/charkit/out/coord/brief_infra5.md`. Scope after the coordinator's split (15:45): tasks 1
(per-stage profile), 2 (budget, report only), 3 (cut costs), 4 (fail-fast tests in the gate), 6 (declared
denominators). tool/infra5-s owns 5 (calibrate PermissionError), 7 (stall alarm), 8 (sweep/optimize priority): this
branch doesn't edit calibrate.py, boxjob.py or the sweep worker launch. These notes are in their own file
(infra5o.md, not infra5.md) so the two halves' notes don't conflict.

## State (read first when resuming)

Started 15:38 EDT. Wall time per task is logged in "Time" below.

**Done; gated.** Gate K **PASS** f36b2f07 into pipeline-3d 27a4b6c3 (`--code tool/infra5-o`, build box; report
charkit/out/gate/gate_tool-infra5-o_f36b2f07_into_27a4b6c3.md): nothing blocks, no check changed, 104 test files
pass, CPU 1660 -> 1887 s (1.14x: the candidate rebuilt the produced references once under this branch's keys). The
earlier gate 33edd0a7 into 27a4b6c3 (build2) also PASS. Commits after f36b2f07: notes only. Review page:
charkit/out/infra5/page/html/index.html (`charkit review page charkit/out/infra5/page/page.json`). The measurement
worktree ~/animation-pipeline-infra5o-base (branch tmp/infra5o-base2: pipeline-3d + the instrumentation; also
tmp/infra5o-base, tmp/infra5o-failfast) can be removed once the coordinator has the numbers.

**Box state changed by this round:** the stale shared hull entry 60a77c6f-b021909c was moved aside on the build box
(/tmp/stale-hull-...-moved-by-infra5o: recoverable).

**Left / proposed:** the budget's blocking rule (Michael's call); the QA's drawing on a GPU box (routing:
tool/build2's area); the iterate profile as a default for QA-only runs and sweep confirm builds (optimize.py's
confirm builds, not touched); `CHARKIT_PREVIEW_VERIFY` (a verify build per merge) not wired.

## Time
| task | start | end | notes |
| --- | --- | --- | --- |
| orientation, data | 15:38 | 15:50 | brief, code, the box's gate baselines' traces fetched |
| 1 instrumentation + `charkit profile` | 15:50 | 16:05 | per-stage CPU recorded; profile table on stored builds |
| 4 fail-fast, 6 denominators, 2 budget plumbing | 16:05 | 16:35 | code + unit tests (budget numbers wait on b0) |
| b0 profile, QA cProfile, counts | 16:35 | 16:50 | b0 cold build profiled; the renderer is the QA's cost |
| coordinator's stale-cache item | 16:50 | 17:35 | walker, depth, runtime record, verify, affected gates |
| 3 cuts: declared buffers, render culling, memos | 17:35 | 18:20 | b1; culling measured (no gain) and taken out |
| final builds (b2/bb, then the clean pair b4/bb3), pregate | 18:20 | 19:55 | the merge with 27a4b6c3 in between |
| coordinator's like-for-like CPU item | 19:05 | 19:20 | gate.like_for_like + test |
| gates (33edd0a7 build2, f36b2f07 build box), review page | 19:15 | 19:58 | both PASS |

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

## The stale baseline hull (the coordinator's item, 16:50)

**Cause.** code_base.head_sections imports headfit and refcheck with importlib.import_module (deliberately, to keep
the QA's modules out of the stage keys), and headfit imports faceregion and refcheck the same way. The code walk behind
every cache key (cache.code_units) read only import statements, so the hull's shared-cache key (manifest.code2, depth 2)
never saw headfit's head fit: after face7 changed headfit (9be5b320), the gates' baselines restored a hull made by
other code. A second hole of the same kind: the produced references' shared key stopped two imports deep.

**Fix, generic** (b22652e5):
1. The walk follows literal runtime imports: `m = importlib.import_module('charkit.x')` (in a function or at the top),
   `__import__('charkit.x', fromlist=..).f`, relative names; a computed name isn't followed (`_Mod.SCHEMA` 5).
   Grep of runtime imports in charkit: code_base (refcheck, headfit), geom/headfit (faceregion, refcheck),
   build_blender (bundle, qa3d_blender), outfit (`__import__('charkit.mh')`): all literal, all followed now. Computed
   ones (registry's part discovery, calibrate/sweep/optimize/fitkit by data, geom/__init__'s lazy loader, cache's
   qarender, declared's limit references) aren't stage code or are covered below. head_sections now reaches 547
   definitions in 41 files (headfit.assemble among them); test_cache's step-closure test said "the head step doesn't
   reach the QA": it only held because the walk couldn't see the imports (updated, with what it does reach).
2. The produced references' shared-cache key (CACHE_DEPTH) follows all the code (was 2 imports); the in-tree stamp stays
   one import deep (a QA edit would rebuild every copy's hull), guarded by 3.
3. **The code that ran, recorded as it runs** (cache.ran: sys.monitoring PY_START, each code object once, so no cost to
   speak of): every venv step entry, QA part entry and produced-reference entry (and PATH.stamp.json) keeps the
   definitions it ran with their digests; a restore checks them (cache.ran_changed) and an entry whose code changed, or
   made before the record, is a miss and replaced. This is what a static walk can't promise (computed imports, depth
   limits): a restore can no longer give a product of code that differs from what this tree would run.
4. `--cache verify` covers the venv steps (file_step(verify=): run, compare products with the entry a lookup would
   restore, same_product: an .npz by its arrays) and the produced references (CHARKIT_PRODUCED_VERIFY): CHARKIT_CACHE_STALE
   lines, the stale entry replaced. The gate reports stale lines from either build; CHARKIT_GATE_VERIFY_BASE=1 builds the
   baseline with --cache verify (off by default: 3 makes it unnecessary, and verifying costs the venv steps' ~400 s CPU
   per baseline). A periodic verify build: `python -m charkit remote --box build build charkit/spec/clawd.json --out
   charkit/out/verify --boards '' --no-blend --cache verify` (grep CHARKIT_CACHE_STALE); proposed for the post-merge
   preview (`CHARKIT_PREVIEW_VERIFY`, not wired: the coordinator's call).
Tests: test_cache (the walk follows call-made imports; a step entry checked against the code it ran; verify finds a
stale step product; a produced entry made by other code misses), test_produced_cache (verify names a stale entry).

**Which of today's gates could have been affected** (charkit/out/infra5/stale/scan.py on the box's produced cache:
restores of a hull entry stored before a merge that changed code its key couldn't see; 68 restores, times UTC):
- face5 342e88c8 (09-30 21:44 EDT, faceregion + headfit): entry 18c7bdd8-55bedf8f (stored 23:39Z, before it) restored
  01:46Z-03:13Z by the gates of tool/hair5 (2), tool/hands (2), tool/face6 (3), tool/sweep (3), tmp/sweep-declared,
  tool/pieceref, tmp/batch-1001, tool/hairsplit (bases and candidates alike).
- garments4-neck ff41ca20 (08:17 EDT, faceregion): entry aefd7446-dc07e4e5 (stored 04:20Z) restored 12:24Z-14:52Z by
  tool/garments4-stairs, tool/garments4-v (2), tool/hairstrokes (3, merge_hairstrokes too), tool/accessories5 (2),
  tool/garments4-motionfix, tool/face7 (d8c6fa8a's base).
- face7 gate 1 9be5b320 (10:46 EDT, headfit; the coordinator's case): entry 60a77c6f-b021909c (stored 14:10Z by the face7
  worktree) restored 15:55Z-19:54Z by tool/face7 (2), tool/hairshell3 (2), tool/hairstrokes (2), tool/optimize,
  tool/hands2, tool/accessories6, the pregates of optimize, hairshell3, rom and accessories6, this branch's fail-fast
  gate and its b0 build.
Whether each restore was actually wrong depends on whether that change moved the hull (the third is confirmed by c3).
Where base and candidate both restored the same entry, nothing moved between them (the gate compared like with like);
the risk is a side that rebuilt (its key changed for another reason) against one that restored.

## 1 (continued). The cold default build, b0 (this branch at 60c0f1a4 + the instrumentation)

`remote build charkit/spec/clawd.json --out charkit/out/infra5/b0 --boards '' --no-blend --cache off` (build box,
threads 4): **1790 s CPU, 1133 s wall.** venv steps 407 s CPU (pieces_hair 209, hair_select 95, code_head 76; a gate
restores these from the shared step cache), Blender 190 (character 59, look_export 56, bundle 26, garments 19, the
trace's own snapshots 16), **QA 1192 (67%)**: declared 364, look 192, artifacts 141, face_flags 93, motion 45,
face_region 44, skirt 39, hair_noise 38, scalp 34, hands 33.

**Where the QA's CPU goes** (`profile qa` on b0's bundle under cProfile: charkit/out/infra5/qaprof/qa_profile.json):
the toon renderer drawing on the CPU box's software rasteriser (wgpu on lavapipe: `proxy_func` inside `submit`, its
threads making CPU about 2.5x wall): declared 7 draws, 80 s of its 136 s wall; look 22 draws, 40 s of 68; artifacts 4
draws, 33 of 45; face_flags 5 draws, 13 of 40. The look export is 2.03M triangles and every frame drew all of it, the
picture 4 x 4 supersampled. The design side (the references measured, per build) ~100 s a pass, much of it already
kept on disk by Design.memo (cache.venv_memo); not kept: the skirt's drawn bands (20 s), the hair weight's head sheet
(8 s), the face flags' design reads (11 s).

**Top 5 costs and what they buy** (b0, CPU s): (1) qa/declared 364: Michael's flags as declared checks (41: the hair's
strokes, line weight and tones, the stairs, creases, cuffs, neckline); (2) venv/pieces_hair 209: the hair pieces, lock
shells and strokes (restored in most gates); (3) qa/look 192: the look checks (face shadows, noise, line widths);
(4) qa/artifacts 141: the art_* flag checks; (5) venv/hair_select 95 (restored in most gates), then qa/face_flags 93,
venv/code_head 76, blender/character 59, blender/look_export 56, qa/motion 45 (105 at 25ff0f25: the box's load).

## 3. The cuts

1. **The iterate profile** (motion QA skipped explicitly, section 3a): 45-120 s CPU an iteration's QA.
2. **declared's line images drew a picture they threw away** (cbe69922^^): `qa3d.draw(..., aux=aux)` renders the
   picture 4 x 4 supersampled and the buffers; _line_images read only the buffers. Now draw_lit(picture=False): the
   same buffers. 35 s of the part's 136 s wall on b0.
3. **Culling in the renderer** (render/buffers.py `_cull`): an orthographic frame leaves out the primitives wholly
   outside its window (their extent grown by CULL_PAD 0.1 m, many times an outline's push) before drawing; what's
   left draws exactly as before. CHARKIT_RENDER_CULL=0 turns it off. Laptop check (Metal): look, face_flags, artifacts
   on b0's bundle, readings equal with and without (`profile same`). The box's numbers: pending (b2).
4. **Design-side measures kept on disk** (venv_memo): the skirt's drawn bands, the hair weight's head sheet (pure
   functions of the drawing's arrays). Iteration only: a gate's builds are cold. And a `--cache off` (or verify)
   build now skips the venv memo too (CHARKIT_CACHE=off): it had restored the design side from earlier builds.

Running: b1 (this branch before the culling and the memos, `--box build`, `--cache off`) into charkit/out/infra5/b1
(log charkit/out/infra5/b1.log); its venv memo is warm from b0 (the --cache off fix came after), so b1's QA isn't a
cold figure; b2 will be.

**Culling, measured and taken out.** On the build box, six render-heavy parts on b1's bundle, side by side with
CHARKIT_RENDER_CULL=0 and 1 (`profile qa --no-cprofile --env ...`, charkit/out/infra5/cull0, cull1): readings equal in
all six, 741 -> 737 s CPU, 323 -> 318 s wall (frame times equal within noise; ~115 primitives culled a frame in the
head and body windows). lavapipe's cost is the fragments (the picture 4 x 4 supersampled), not the triangles off the
window. The frame log stays (render.buffers: each frame's inputs as a digest): **no frame is drawn twice** in a QA
pass (0 repeats in all six parts), so a cross-part frame memo wouldn't pay either. The renderer's CPU cost is
intrinsic on a CPU box: drawing the QA on a GPU box would remove most of it (recommendation, routing is
tool/build2's).

## 6 (continued). Denominators demonstrated on the real crash

`remote run gate --rejudge` (this branch's judge) on the box's reports of the gates that let motion QA's crash in:
- **tool/garments4-part2 312d83d into 6620113: then PASS, under K with denominators FAIL**: "a QA part crashed:
  motion (ValueError: skirt: not a grid (5110 vertices, stride 144))";
- tool/garments4-part2 9e35959 into 6620113: then FAIL (tests), now also the motion crash;
- tool/garments4-stairs b4670264 into ff41ca20: then PASS, now FAIL (the base crashed too: the rule is unconditional on
  the candidate, the baseline's own crash is reported).
(log charkit/out/infra5/rejudge_motion.log; these qa.json predate part_status, so the crash is read from the part's
lone SKIPPED entry with an exception's text.)

## 2. The budget: the proposed blocking rule (not enabled; Michael's call)

The relative rule (candidate <= 1.5x its baseline) can't see creep: each of today's merges added 3-15% and passed,
577 -> 1310 s in a day. Proposal: **block when the candidate's total build CPU is over charkit/budget.json's total by
more than 10% and over its baseline's by more than 5%** (this merge pushed it over), unless the merge raises the budget
in charkit/budget.json itself, with a reason, in the same merge (reviewable: the gate report shows the old and new
budget). Per-stage budgets stay report-only (they name where the cost went). The total is compared on gate builds
(threads 4, venv steps restored from the shared step cache); a candidate that rebuilds a venv step its baseline
restored is judged on the stages both built (the phases in build_cpu.json make that possible now).

## Before and after, side by side (bb: the base code b2d96808 = 60c0f1a4 + the instrumentation; b2: this branch)

Both `--cache off`, `--boards '' --no-blend`, threads 4, launched 30 s apart on the build box
(~/animation-pipeline-infra5o-base charkit/out/infra5/bb; charkit/out/infra5/b2; `profile bb --vs b2`:
charkit/out/infra5/profile_bb_b2.md). **Readings: 702 checks, 0 differ; the bundles' 962 arrays identical; every QA
part ok against its count.** CPU 1525 -> 1446 s, wall 971 -> 944 s. The QA: declared 281 -> 190 s CPU (108 -> 87 s
wall: the line images' picture); the rest moved because of where shared in-process work fell: bb rebuilt the hull in
resolve (the stale entry moved aside), which computed the head and the design's clips in-process for the later steps;
and b2's `--cache off` turned the venv memo off entirely, so face_region, piece_details, skirt and code_body
recomputed their design side at every call (+60 s). Fixed (a3...: the memo stays in memory with the cache off); the
clean pair (b3, bb2) is running.

## The gate (33edd0a7 into pipeline-3d 27a4b6c3, `remote gate --code tool/infra5-o`, build2 box)

**PASS under K, nothing blocks, no check changed** (charkit/out/gate/gate_tool-infra5-o_33edd0a7_into_27a4b6c3.md;
902 s; 104 test files, 0 failing). The QA part statuses all ok against their counts (accessories measures 71, declares
50: raised to 71 in 880d2188). The budget table is in the report (venv/* 522 > 500 s WARN: the candidate ran the venv
steps cold, below). Measure-code changes listed for 32 parts (manifest.produced and the frame log reached through the
QA's shared code), geometry unchanged, no check moved. Build CPU 1103 -> 1418 s (1.29x): **the baseline restored the
venv steps and produced references, the candidate ran them** (resolve 4 -> 200 s, hair_select 3 -> 53 s, pieces_hair
0.5 -> 116 s: this branch's new cache keys and runtime records miss the old entries once). Like for like (below):
QA 886 -> 709 s CPU (-20%), wall 464 -> 371 s; declared 273 -> 178, skirt 31 -> 20.

## The CPU rule like for like (the coordinator's fairness item, 18:05)

The 1.5x rule compared a baseline that restored stages from the shared caches against a candidate that ran them cold
(the hair shells' switch: 871 -> 1406 s, 1.61x, blocking; cold against cold ~1.04x). Design chosen: **compare only
the stages both builds ran.** Each build records what it restored (build_cpu.json `restored`: each venv step's
file_step outcome, cache.STEP_RESULTS; each produced reference kept, restored or built, manifest.PRODUCED_RESULTS)
beside its phases' CPU. gate.like_for_like: a venv step counts when both ran it (one restored: left out of both);
`resolve` (the produced references and the design measured) counts when both built the same references; Blender, the
QA and the rest always count (a gate's worktrees are fresh: both run them cold); the CPU outside the phases as it is.
Policy K's 1.5x then reads that pair; the report shows the totals, the like-for-like pair and what was left out. A
build from before the record: the totals, as before. The alternative (each side's cold figure, a restored stage
counted at the CPU its cache entry recorded) would need every entry to record its CPU and older entries have none;
the chosen one needs nothing stored. What it can't see: a branch that makes a cached step slower while the baseline
restored it (the candidate's cold cost isn't compared); the budget table still shows the candidate's figure per stage.
Test: test_gate `test_build_cpu_is_compared_like_for_like` (the hair-shell numbers: 1.61x raw, 1.02x like for like;
cold against cold at 1.62x still blocks; no record: the totals).

## Before and after, the clean pair (bb3: pipeline-3d 27a4b6c3 + the instrumentation; b4: this branch 880d2188)

Side by side on the build2 box (c3-standard-44), `--cache off --boards '' --no-blend`, threads 4 (bb3 in
~/animation-pipeline-infra5o-base on tmp/infra5o-base2; `profile bb3 --vs b4`: charkit/out/infra5/profile_bb3_b4.md).
**Readings: 723 checks, 0 differ; the bundles' 962 arrays identical; every part ok against its count.**

| group / stage | before CPU s | after CPU s | change |
| --- | --- | --- | --- |
| **QA** | **854.5** (433 s wall) | **749.2** (400 s wall) | **-105 (-12%)**, wall -8% |
| qa/declared | 280.9 (100 s wall) | 184.7 (75 s wall) | -96 (-34%): the line images' wasted picture |
| qa/skirt | 28.1 | 20.9 | -7 (the drawn bands in memory once) |
| qa/look, artifacts, face_flags, motion | 134.6, 101.3, 60.4, 29.8 | 128.5, 99.4, 68.0, 29.1 | noise (unchanged code) |
| Blender | 175.5 | 180.6 | unchanged code, noise |
| venv (resolve and the steps) | 321.7 | 549.2 | not comparable: b4 rebuilt the produced references (this branch's keys, once per box), and building the hull in-process computed the head that code_head then reused |
| total | 1351.8 | 1479.4 | the venv row above; QA and Blender like for like: 1030 -> 930 |

Gate conditions (the gate above, the like-for-like pair): QA 886 -> 709 s CPU, 464 -> 371 s wall.
