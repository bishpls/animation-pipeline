# Infrastructure workstream (tool/infra, 2026-09-30)

Michael's process decisions of 2026-09-30 (the handoff's "Process and architecture decisions"), items 2–5: an automatic
preview after every merge, self-registering QA parts and measurement steps, the anti-gaming 2×2 in the gate, and a
standing evaluator-against-box drift test. Worktree `~/animation-pipeline-infra`, branch `tool/infra` from
pipeline-3d 9397578.

## Round 2 (tool/infra2, 2026-09-30): state and next steps (read first when resuming)

Worktree `~/animation-pipeline-infra2`, branch `tool/infra2` from pipeline-3d cfcdc3a. Checkpointed at the
coordinator's call (usage limit): tasks 1-3 done and tested, (b) measured, (c) located; (a) not started.

**Task 1: box jobs survive dropped connections (`charkit/boxjob.py`, `charkit/remote.py`).**
- `remote build | tune | run | gate` send the job to the box and follow it. The box keeps it in `/srv/work/.jobs/<jid>/`:
  `run.sh`, `meta.json`, the job's own `boxjob.py` and `bucketsync.py`, `claim` (O_EXCL: a retried start never runs it
  twice), `pid` (a setsid supervisor that no ssh session owns; the job in its own process group), `log`, `exit`.
- The laptop follows with `boxjob.py follow JID OFFSET`: framed chunks (`D n`, a heartbeat `H` every 15 s, `E rc`). After
  a drop (ssh exits, or no frame for 75 s) it reattaches at the last byte delivered, 3 s after a working connection
  drops, with backoff up to 60 s otherwise. It gives up only after 45 min without a connection (exit 75, the job goes on),
  says "lost" if the box stopped (exit 70), and propagates the job's exit code.
- `remote jobs [--days N]` lists every box's jobs; `remote attach JID` follows a job again from byte 0 and collects its
  outputs (the local record in `charkit/out/remote/jobs/<jid>.json` says what and where); `remote kill JID` SIGTERMs
  the job's process group and descendants only. Ctrl-C stops following and leaves the job running (it says so).
- Setup steps that are safe to repeat (sync, push, pull, keepalive, the gate's ref list and i3d seed) retry on ssh's own
  failure (exit 255). The gate's ref list no longer reads a failed ssh as "the box has nothing" (that bundle would be
  the whole 1.8 GB history). The gate's i3d seed is now idempotent (links under a temporary name, renamed).
- Jobs run with PYTHONUNBUFFERED=1, so the log streams. The supervisor's command line names charkit, so the build
  box's idle stop counts a running job as busy; past 60 min it touches the keepalive every 30 min (the render box's idle
  check has no pgrep).
- **Rollout.** Nothing on the box changed for old clients: their in-session gates and builds ran alongside all of this.
  A worktree gets detached jobs when it merges pipeline-3d after this; `CHARKIT_DETACH=0` keeps the in-session path.
- **The demonstration** (build box at load 33-55; `remote build charkit/spec/clawd.json`, job
  build-infra2-0930-050445-7dfa):
  - drop 1 at 05:07:04: SIGKILL to the follow's ssh -> "the connection to the box dropped (ssh exit -9) ... reattaching
    in 3 s";
  - drop 2 at 05:08:32: SIGKILL to its IAP tunnel process (gcloud start-iap-tunnel, the ssh's ProxyCommand) -> "ssh
    exit 255: client_loop: send disconnect: Broken pipe", the reported failure;
  - the job ran on and finished; the command reported "followed to its end through 2 dropped connections", pulled its
    outputs (36 files, 44.65 MB, 4.4 s) and exited 0.
  - The laptop command itself killed (SIGKILL at 05:14:10, exit 137) mid-way through a clawd_mh build: the job went
    on; `remote attach build-infra2-0930-051014-2445` followed it from byte 0 to its end, pulled 34 files (40.45 MB,
    2.9 s) into charkit/out/mhdet1 and exited 0.
  - Exit codes: `remote run kill /nonexistent` exits 1 through the detached path; builds exit 0.
- Tests: `test_boxjob` (runs once however often started; log whole and in order from any offset; frames across split
  reads; lost; kill; `remote.attach` over a connection that drops every 700 bytes gets the whole log once with the
  exit code; the sampler; the summary), `test_procs` (the wait log). Run on the laptop and on the box's Linux Python.

**Task 2: box load (`boxjob.py sample`, `charkit/boxload.py`).**
- A user crontab line (installed by the first job on a box; its command line doesn't name charkit, so it never keeps a
  box awake) samples once a minute into `/srv/work/.load/load-<UTC day>.jsonl`: 1/5/15-min load; CPU busy, user,
  system, iowait, steal since the last sample; CPU by process class (charkit build, qa, gate, ...; Blender; other: from
  /proc/PID/stat); memory; the slots (count, holders from /proc/locks, without touching the locks); builds waiting for a
  slot; running jobs; GPU where nvidia-smi exists; free disk. A job's supervisor publishes `/srv/work/.load` to the
  bucket as `load-<VM>` when the job ends.
- `charkit.procs.acquire_slot` now writes `slots/wait/<pid>.json` while waiting and a line per slot taken in
  `slots/waits.jsonl` (the wait, and what for). Builds record these once their code has this (gates: after the merge).
- `remote load [--hours N] [--box NAME] [--fresh] [--json]` summarises per box, with an hourly table and a reading.
- **The sampler runs on the build box since 09:03 UTC**; the render box gets it with its first detached job (none yet).
  **The first 15 minutes** (09:03-09:16 UTC): CPU busy mean 63%, median 66%, p90 84%; load mean 32.6, p90 45.6, peak
  54.6 on 32 vCPU, above 32 in 53% of minutes; memory at most 80 of 126 GB used, never under 46 GB available;
  **8.3 `charkit build` processes at once on average (max 10) against 1.3 slots held (max 4 of 8)**; CPU by class:
  charkit build 42%, Blender 4%, charkit qa 3%.
- **The finding that matters for the capacity call:** a build takes a slot only for its Blender step. Its Python stages
  (the hull, garments, QA) run outside the slots, and on the build box, where boards are skipped, they are most of the
  CPU. So SLOTS doesn't bound the box's load: raising or lowering it changes little. What bounds it is how many builds
  the agents start. Next: let a day of samples accumulate (the render box too), then `remote load --hours 24`. If the
  CPU is saturated at peaks while builds queue on cores, a bigger machine or a second box adds throughput; a machine-wide
  cap on concurrent builds (a slot for the whole build, not only Blender) would turn overload into a visible queue.
  SLOTS left at 8: the data doesn't support a change.
- Caveats: CPU by class counts processes alive at a sample (short-lived ones are missed: about 13 points of the 63% in
  the first window); `procs.available_gb` reads macOS's vm_stat only, so the box never waits for memory.

**Task 3: click-to-flag on the preview page (`charkit/flags.py`, `charkit/flagui.js`).**
- **Michael starts it** in the worktree whose previews he reviews (pipeline-3d's, after the merge):
  `python -m charkit preview serve --open` (port 8765; `--port N`), then presses F (or Flag) on a page and clicks a
  point or drags a box; severity 0 praise / 1 minor / 2 clear / 3 severe (keys 0-3), a note, Cmd-Enter. A marker's
  click edits or deletes it. List shows the page's flags. It serves 127.0.0.1 only, from the standard library.
- Flags go to `charkit/out/previews/flags.jsonl` (the live flags, one per line) and `flags.log.jsonl` (every add,
  edit, delete). Fields: id, t, edited, sha, short, image (the picture clicked), px / box in its pixels, board, view,
  az, board_px / board_box in the board's pixels, part, region (the class: skin, hair, white, orange, line, ...), parts
  (a box's shares), part_source, severity, severity_name, note.
- A flag is anchored on its board through the crops' maps (`preview.crops` records each crop's map in crops.json; for a
  page made before, `flags.crop_maps` works them out once from the stored boards and keeps page/maps.json). It shows on
  every picture of that board: the page's crop, the raw board (`/view?src=...`, linked from `/<sha>/boards/`).
- **The part** comes from an ID pass: the build's bundle drawn in the board's projection with the QA's z-buffer
  (`qa3d.scene_objects`), cached in page/id_<board>.npz (about 5 s the first time). The body boards (orthographic,
  1.12 H across 1000 px round (0, 0, 0.52 H)) and the design boards (orthographic, 2.4 L across round the head) have
  exact projections. Measured on preview 3bc7b86 against each board's rendered silhouette: design boards IoU
  0.993-0.996, no shift; body boards 0.983-0.986 without the white boots (the silhouette detector misses white on the
  near-white background; with them 0.90-0.93), bounding boxes within 1-2 px. The rest is the outline shell outside the
  mesh. **The part is null, with the reason in part_source,** for the perspective face_* boards, the design's own
  pictures, QA overlays and sheets, and previews whose bundle was pruned (only the newest 4 keep one).
- The page still works opened as a file: it shows a note that flags need the server. The server adds the script to
  pages made before this; `preview.page` now includes it and copies flagui.js to previews/flags.js.
- Tests: `test_flags` (a board mark lands where the crop's map says, for figure and head crops; add, edit, delete,
  the log; a flag shows on the board's other pictures; the null-part reasons; the HTTP API). The UI was driven end to
  end in headless Chrome over the DevTools protocol (F, drag a box, severity 3, note, save: part "skirt"; click the
  marker, edit, save). The driver script was a one-off (scratchpad).
- Test data: this worktree's charkit/out/previews holds copies of 3bc7b86 and cfcdc3a and a few test flags (ignored
  files; delete freely).

**The hook's git environment (the coordinator's bug, fixed here).** Git exports GIT_DIR, GIT_INDEX_FILE and more to a
hook's processes, and a git command run with them acts on the hooked repository whatever its cwd: the post-merge
preview's `checkout -f --detach` detached pipeline-3d's HEAD. Now `preview._git` and the preview's build child run
without them, `preview.main` drops them from its own environment (the box sync lists files with git too), and the hook
script unsets them. `test_preview.test_the_hooks_preview_never_touches_the_hooked_worktree` merges in a throwaway
repo whose hook's stub runs a forced detached checkout in a second worktree through `preview._git` with GIT_DIR set:
the hooked worktree stays on main at the merge (the old `_git` detaches it: checked). The hook stays uninstalled
(the integrator reinstalls it after the merge).

**(b) ssh multiplexing: measured, not adopted.** Over IAP to the build box: a plain ssh median 1.24 s (1.05-1.58, 8
runs); with ControlMaster, 1.39 s for the master, then 0.10 s median (0.08-0.13). But killing the master took the
session riding it down (exit 255), which fails the brief's condition. With detached jobs and the retries above, a
shared drop now costs a 3 s reattach, not a job, so it's worth reconsidering (about 4 ssh per remote build: ~4.5 s).
The control socket path must be short (macOS limit 104 bytes: `~/.ssh/cm/%C`).

**(c) The masked skin's nondeterminism: located, not yet fixed.**
- The coordinator's data point (tool/artifacts f87620c into cfcdc3a, clawd_mh: "knobs hair changed", 2 arrays
  changed) has two separate causes:
  1. **"knobs hair changed" and the spec_hash** are a path, not content. The resolved spec's `hair.shape.pieces` is an
     absolute path into the build's own output (`/srv/work/gates/<gate id>/charkit/out/gate/<build>/geom/hair_pieces`),
     and trace.py hashes the whole hair section. Base and candidate always differ there. Fix: resolve it relative to
     the build's out dir, or leave output paths out of the knob hash (trace.STAGE_KEYS / the spec resolution; check
     whether the hair stage's cache key includes it too: then gates never reuse the baseline's hair).
  2. **The 2 arrays** are `o/clawd_skin/masked/V` (15 of 39393 vertices, at most 1.19e-7 m: one float32 ulp) and
     `masked/shrink` (13 rows, at most 1.5e-8). The `eval` variant, the same skin without the garment MASK modifier, is
     bit-identical. So the difference is in Blender's evaluation of the masked skin (bundle.py reads it with every
     shown modifier but the outline and proxy normals; the MASK `under_garments` is first in the stack).
- **Next step (not run: no new experiments at the checkpoint):** open a clawd_mh build's blend on the build box
  (`/srv/work/animation-pipeline-infra2/charkit/out/mhdet1/clawd.blend`, or any clawd_mh build's) and, in one Blender
  process, read the masked skin 6 times, each after a fresh evaluation (all modifiers off, update, the bundle's set on,
  `evaluated_get(dg).to_mesh()`), then with each modifier after the mask turned off. Varies within a process: bisect to
  the modifier and try `-t 1`. Identical within a process but not across: compare two processes' saves, with
  PYTHONHASHSEED fixed and with `-t 1`. The fix is then either that modifier's settings or rounding the masked read
  (e.g. to 1e-6 m) where the bundle stores it.

**Gates.** See "Round 2 gates" below.

**Next steps (a lean relaunch):**
1. Record the round's gates (below); gate `--spec charkit/spec/clawd_mh.json` if not yet done.
2. (c): the probe above, then the fix; and the hair path in the resolved spec (with its owner).
3. (a) bucket GC: list `cas/m/*` manifests and `cas/n/*` names, keep what the last N days' manifests reference, dry
   run first (count and bytes), then delete; the bucket's soft delete keeps deletes 7 days.
4. After a day of samples: `remote load --hours 24` for both boxes, and the capacity note for Michael.
5. Old job dirs prune after 14 days, load logs after 60.

## 1. The combined preview after a merge: `python -m charkit preview`

- `python -m charkit preview [REF]` (default HEAD) builds REF on the render box with boards `views,body,design` in its
  own detached worktree, `../animation-pipeline-autopreview`. That worktree is kept between previews, so its box copy
  syncs only what changed, and the build never sees the integrator's working tree.
- The result is stored under `charkit/out/previews/<sha7>/`: boards, qa, bundle, trace, and `page/` with the page's
  crops. `index.jsonl` lists the previews, and `latest.html` redirects to the newest.
- Previews queue on a lock. `--tip BRANCH` resolves the branch once the lock is taken, so a burst of merges previews
  its last commit once.
- **The page** is `review.html`, with these sections:
  - the QA tally against the previous preview: the newest earlier preview of an ancestor commit, else the newest other
    one. It lists FAIL → PASS, FAIL → WARN, WARN → PASS, PASS → FAIL, WARN → FAIL, PASS → WARN, new, gone and every
    FAIL now. A check a measurement step between the two commits covers is starred;
  - the full figure: the design (body_turnaround's four figures), previous and current, each cut to its figure and
    shown at one height;
  - the head in the design's projection beside head_turnaround's front, three-quarter, profile and back, with the
    previous preview's heads too;
  - a turntable in that projection;
  - links to the QA overlays.
- **Close-ups in the design's projection.** `scene.boards` has a new `design` board: orthographic and level at the
  eye line, centred on the head, 2.4 L across at 400 px/L. It renders at 0, 30, 35, 60, 90 … 330°. The design's
  three-quarter is measured at 35.7°. The page cuts both ours and the design to one window round the eye line (1.2 L
  above, 1.0 L below, ±1.0 L), each from its own px per L, and resamples both to 300 px/L:
  - head_turnaround is 399.4 px/L at its own size (the kit's convention: its front eyes 2 × 0.168 L apart);
  - the eye lines line up to the pixel. `test_preview.test_head_crop_keeps_the_eye_line_and_the_scale` checks the
    projection with synthetic marks.
- **A commit without the design board** (anything before tool/infra) has its head drawn from the build's bundle in the
  venv instead (`qa3d.draw`, the QA's own renderer, in the same projection). The page says which source it used.
- **One command for the integrator:** `python -m charkit preview` (run_in_background), right after the merge.
- **Optional hook:** `python -m charkit preview hook install` in the pipeline-3d worktree.
  - It sets a per-worktree `core.hooksPath` (`extensions.worktreeConfig` is already on), so the repo's other
    worktrees and its shared hooks are untouched.
  - The post-merge hook checks the branch, starts `nohup … preview --tip pipeline-3d &` and exits 0. It never blocks
    or fails the merge (test_preview checks this in a throwaway repo).
  - Not installed yet: it's the integrator's call. `hook status` and `hook remove` are there too.
- **The real run** on pipeline-3d 9397578 took 878 s on the render box (T4, n1-standard-8): 176 PASS, 29 WARN, 8 FAIL,
  78 INFO, 3 SKIPPED. Page: `~/animation-pipeline-infra/charkit/out/previews/9397578/review.html`. It's the first
  preview, so there is no previous one, and its close-ups are the venv drawing (the commit predates the design board).

## 2. Self-registering QA parts and measurement steps

- `charkit/registry.py` holds the mechanism. How to register a part or a step, and how to merge a branch from before
  the change: docs/CHARKIT.md, "Registering a QA part or a measurement step".
- **Parts:** `@qa_part(name, order=…, prefix, table, ref_image, keep, skip_key)` on the function where it's defined.
  - `registry.parts()` finds the modules by the decorator at a line's start, imports them, and sorts the parts by
    (order, name).
  - The 21 parts from `qa3d.PARTS` are decorated in place in qa3d.py, 100 apart (shape 100 … look 2100).
  - The special cases in `run()` and `evaluate()` became registration fields: shape's reference image,
    face_shape's kept prefix, eyes' SKIPPED name.
- **Steps:** `charkit/steps/<module>.py`, each a `MEASUREMENT_STEPS` literal read with `ast`. Nothing imports them.
  - `history.registered()` (and `history.STEPS`, via a module `__getattr__`) is every file's steps, in module-name
    order.
  - `history.load_steps(path)` reads a tree's steps without importing it. It handles trees from before the change (the
    old `STEPS` literal in history.py) and after.
  - The 65 steps moved by their text (comments kept), to bodyqa (10), detailqa (6), eyeqa (1), faceregion (10),
    lookqa (1) and qa3d (37: the cross-cutting tool/measure and tool/refs steps, pieces, hair_noise, sheet_*).
- **Why a separate package.** The first placement put each list inside its measuring module (bodyqa.py and the
  others). That changed the build-stage keys and the hull and outfit-mask stamps, because the producers import
  bodyqa, eyeqa and qa3d. Adding one step would have rebuilt the hull everywhere. In `charkit/steps/` no stage key and
  no produced stamp changes. Measured with code_units / `manifest._producer_code` on both trees:
  - unchanged: the hull, outfit_masks and hair_layers stamps; code_head, code_body; every scene stage;
  - changed once: the QA parts (qa3d changed); `boards` (the design board); geom_hair and pieces_hair (they import
    qa3d two deep). The design board's constants are local to `boards()` so scene's top level, which keys every stage,
    is unchanged.
- **Behaviour.**
  - The parts are identical: the same 21 names, functions, prefixes and tables in the same order.
  - The steps are the same 65 as a multiset, and each pattern's steps keep their order.
  - `steps_between` is identical on all 812 ordered pairs of 29 commits (every step commit and some merges).
    `remeasured(names)` returns the same check sets on all of them. Its reason text differs in 32 pairs, for
    `eye_pupil_*` only: that check matches both eyeqa's `eye_pupil_*` and qa3d's `eye_*`, and the files' order
    changed which reason comes last.
  - `history NAME --check CHECK` now prints the steps each boundary actually crosses, not the last matching step.
  - Bit-identical QA: see "Verification" below.

## 3. The 2×2 in the gate

- `gate.cross_qa(tree, bundle, out)` runs one tree's QA on another build's bundle, with the cache off.
- `gate.twobytwo(base, cand, old_on_new, new_on_old, remeasured, accept)` builds the rows: for each remeasured check,
  the four cells, `old` (the new geometry against the old under the old measure) and `new`.
- **In `gate()`:** when the branch brings a step that covers a check and the bundles' content differs:
  1. the merged tree's QA measures the baseline's bundle (the new measure on the old geometry);
  2. `git merge --abort`;
  3. the baseline's QA measures the candidate's bundle (the old measure on the new geometry).
- **The verdict.** A remeasured check that reads worse on the new geometry under one measure applied to both
  geometries fails the gate, unless `--accept PATTERN[,…]` names it (`remote gate` passes `--accept` through).
  "One measure" is the old measure on both, or the new measure on both (`gate.twobytwo_drops`). If a crossed run can't
  run, the verdict is WARN (unverified).
  - The brief asked for the old measure. The demo showed the new measure on both geometries hides drops too: the
    remeasured row compares the new measure on the new geometry with the old measure on the old, so a drop by either
    standard can hide in it. Both are flagged.
- The report gets a 2×2 table.
- **The bundle format** is schema `charkit.bundle/1`, unchanged since tool/measure: named arrays plus JSON metadata,
  read by name. Old code reads a newer bundle unless an array it reads was renamed or removed, and such a part comes
  back SKIPPED, which shows. A schema bump would need the candidate exported by the baseline's bundle writer (open
  item).

**The demonstration: tool/body round 3's flap measure change.** Round 3 was the first flaps. Step d35fbaf registered
`piece_skirt` and `piece_overskirt_panel_*` as remeasured (the same-colour layer rule) while the flaps' geometry
changed. The setup:
- the gate at a456834 into 966ad22 on `clawd_body.json`, as round 3 was gated on 2026-09-29;
- run with this branch's gate.py, history.py and registry.py in a clone at 966ad22 on the build box;
- the cached 966ad22 baseline, a fresh candidate build and both crossed QA runs;
- script: scratchpad `demo2x2.sh`. Report: `charkit/out/gate/gate_demo2x2-tool-body_a456834_into_966ad22_clawd_body.md`
  (and `.json`).

| check | old geom, old measure | new geom, old measure | old geom, new measure | new geom, new measure | old | new |
|---|---|---|---|---|---|---|
| piece_overskirt_panel_R | 0.526 WARN | 0.382 FAIL | 0.526 WARN | 0.453 FAIL | **regressed** | **regressed** |
| piece_overskirt_panel_L | 0.451 FAIL | 0.306 FAIL | 0.453 FAIL | 0.348 FAIL | value | value |
| piece_skirt | 0.803 PASS | 0.733 WARN | 0.803 PASS | 0.804 PASS | **regressed** | value |
| body_back_skirt_width | 1.995 FAIL | 2.487 FAIL | 1.037 PASS | 1.102 WARN | value | **regressed** |
| piece_skirt_extent (new) | - | - | 0.0612 PASS | 0.1035 WARN | - | **regressed** |
| body_front_skirt_width | 0.795 FAIL | 1.047 PASS | 0.795 FAIL | 1.047 PASS | improved | improved |

- The old gate called the first three rows "remeasured", neutral, and FAILed only on `body_back_iou_skin`. The 2×2
  shows `piece_overskirt_panel_R` dropping WARN → FAIL under the old measure. That is the regression the notes' 2×2
  found by hand: 0.381 in the evaluator, 0.382 here.
- `piece_skirt` held at 0.804 only because the new rule stopped counting the flaps' pixels over it. Under the old
  measure it dropped 0.803 PASS → 0.733 WARN, which nobody had caught.
- Under the new measure alike, the back skirt width (1.037 PASS → 1.102 WARN) and the new skirt extent check
  (0.0612 PASS → 0.1035 WARN) got worse too.
- The front skirt width improved by both measures, so the remeasure didn't dress up the gain.
- Tests ok; no crossed-run errors; the geometry changed (bundle 4837e0c42c → f6eccdb4b3). The verdict with this
  code is FAIL: body_back_iou_skin, plus the four hidden regressions listed by `gate.twobytwo_drops`. This run's
  report predates flagging the new-measure drops and lists the old-measure two, which were recomputed from the same
  rows.

## 4. The evaluator against the box: `python -m charkit evaldrift [SPEC]`

- It builds SPEC on the build box, then runs the evaluator there on the same synced copy: `bodyfit.BodyChecks(spec,
  graph).checks(spec, 'all', fine=True)`, which is the body fit's own view (shape_*, body_*, palette_*, sheet_*,
  piece_*).
- It compares every check both sides have. The tolerance is 0.01 by default (L, IoUs, shares) and 0.5 for palette_*
  (CIEDE2000); `--tol` sets one for all.
- It writes `drift.json` and `drift.md` into the build folder and exits 1 on drift. `test_evaldrift` tests the
  comparison.
- The evaluator reads the build's own resolved spec (`BUILD/NAME.spec.json`), as `bodyeval.validate` does. The raw
  default spec can't be assembled by the evaluator: the code-built body's `body_code` file comes from the build's
  `code_body` step.
- `--no-build` reuses the box build at `--out`.

**The first result** (clawd.json; box build of c1016fa, whose geometry is pipeline-3d 9397578's; the evaluator on the
same synced copy, 128 s): 38 of the 110 shared checks drift, 12 grade differently.
- **Hems and skirt: no drift.** All 13 `body_*_hem`, `hem_mid`, `skirt_width` and `skirt_aline` checks agree to the
  last digit. The body round's 0.024–0.028 L hem offset is gone at this commit.
- **Hair: the evaluator doesn't build the build's hair.**
  - `body_*_hair_length` reads 0.20–0.27 L shorter in every view: PASS on the box, FAIL in the evaluator.
  - `body_*_top` reads 0.066 L lower; `body_*_iou_hair` is down by 0.05–0.18 and `hair_width` by 0.04–0.06
    (profile +0.09).
  - The knock-on effects: `body_*_iou_skin` (profile -0.082), `sheet_shown_*` (profile 0.356 → 0.038), `shape_iou*`,
    `ref_iou`, `body_*_iou`.
  - The default spec's cut-piece hair (`geom/hair_pieces`) isn't what `bodyeval.Evaluator.hair_parts` builds, so a fit
    on the evaluator aims at the wrong hair. Owner: hair / body.
- **Face registration.** `sheet_cheek_chin` -0.0027 → -0.0277, `sheet_profile_chin` 0.0003 → -0.0247 and
  `sheet_neck_to_jaw` read 0.025 L apart. `sheet_width` is +0.026.
  - These are e9a6753's numbers exactly: the QA's face registered on the head's eye line instead of the iris plates'
    mean, 0.0235 L over it. That change reached `qa3d` but not the evaluator's `bodymeasure.sheet_face`.
  - Owner: face; the fix is the evaluator using `qa3d.eye_anchor`.
- **Not compared:**
  - 171 checks only the box gives: detailqa's boot, torso and midriff checks, the pieces' aggregate checks, and the
    rest of the parts the evaluator doesn't run;
  - 264 only the evaluator gives: `bodymeasure.piece_checks`' per-view sub-measures such as
    `piece_boot_L_back_bottom`, which the box's QA reports under other names.
- Report: `charkit/out/evaldrift/clawd/drift.md`.
- **Rerun at 4fa804a** (a fresh box build; the tree was dirty only in this notes file; the evaluator took 47 s with
  its cache warm): the same 38 checks drift and 12 grade differently; the hems still agree exactly.

## Verification

- **Tests:** `test_registry` (6), `test_preview` (5), `test_evaldrift` (2), and `test_gate` (+2: the 2×2, the geometry
  digest). The gates run the whole suite.
- **Task 2: identical QA before and after.**
  - The clawd_mh gate (c1016fa into e11fadb, build box) PASSes with "no check changed".
  - `python -m charkit.boarddiff` on its baseline and candidate: 16 QA overlay images, 0 differ; 292 checks, 0 differ.
    qa.json is identical apart from `measured` (timings): the same 292 checks in the same order, the same tables.
  - The default-spec gate (c1016fa into e11fadb) PASSes with "no check changed". boarddiff: 16 images and 294 checks,
    0 differ; qa.json identical but for timings; all 733 bundle arrays identical (the geometry bit for bit).
  - On the render box, preview 3bc7b86 against preview 9397578 (the same boards and QA): no graded check changed
    status, and the counts are identical (176/29/8/78).
- **The 2×2's "did the geometry change".** The two gate builds' bundles have different content hashes: the resolved
  spec's absolute output paths are part of it. So the gate compares the bundles' array hashes instead
  (`gate.geometry`). Those differ too, in `o/clawd_skin/masked/V` and `shrink` only, with every QA number identical
  (see Open items).
- **Task 1:** two real previews on the render box.
  - 9397578: 878 s, cold cache; its close-ups are the venv drawing.
  - 3bc7b86: 573 s; its close-ups are the EEVEE design board, and its previous is 9397578. The heads line up with
    head_turnaround on the eye line at one scale; the turntable has 13 views.

## Merges and final gates

- **pipeline-3d 120d197 (tool/hull-limbs) merged at f2635f3.** hull-limbs had added three measurement steps to
  `history.STEPS`: `body_profile_leg_back` 1fd1c63 and 2479a22, and `body_profile_leg_outline` 2479a22. They moved
  word for word to `charkit/steps/detailqa.py`, right after `body_profile_leg_back`'s first step (854776f), so that
  check's steps keep their order. It added no QA part.
  - All 68 of pipeline-3d's steps are registered (the same multiset).
  - `steps_between` is identical to pipeline-3d's list on every ordered pair of 32 commits.
  - The whole suite passes.
- **Gates of f2635f3**, on the build box:
  - default spec into 120d197: **PASS**, no check changed (`gate_tool-infra_f2635f3_into_120d197.md`);
  - `--spec charkit/spec/clawd_mh.json` into 62b0556: **PASS**, no check changed. pipeline-3d had moved on to
    tool/bucket-sync, which is `bucketsync.py`, remote.py and build.sh only.
- **Earlier gates**, all PASS with no check changed: c1016fa into e11fadb (both specs), 4fa804a into e11fadb (both
  specs).
- **301b661** (tool/toonrender, `charkit/render/`) came after both gates. tool/infra merges into it cleanly, the whole suite passes on the merge result (21 parts, 68 steps), and the
  merge result has no `PARTS` or `STEPS` list or reader: toonrender registers nothing.

## Open items

- **Masked skin differs between builds.** The skin's garment-masked vertices (`o/clawd_skin/masked/V`, `shrink`)
  differ between the clawd_mh gate's baseline and candidate, though no geometry code differs between them and every
  QA number is identical. The default spec's two builds match in all 733 arrays, so this is the MakeHuman base's
  garment mask, apparently nondeterministic run to run (not measured further). It makes
  the 2×2 run where it isn't needed, which costs time but not correctness.
- **The evaluator's drift** (task 4's result) belongs to the hair and face owners: the evaluator doesn't build the
  cut-piece hair, and its face registration lacks e9a6753's eye line.

- The hook isn't installed in the pipeline-3d worktree (the integrator's call).
- A bundle schema bump would disable the 2×2 (WARN, unverified). The fix then is exporting the candidate's scene with
  the baseline's `bundle.py`.
