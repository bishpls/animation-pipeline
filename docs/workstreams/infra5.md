# Gate tooling round 5 (tool/infra5, 2026-09-30)

Worktree `~/animation-pipeline-infra3`, branch `tool/infra5` from pipeline-3d b3c5abf. The brief (infra4's items 4-7):
(4) pregate's coverage (sleeve, face) and its agreement with the real gate; (5) the TRELLIS cleanup (decision 8); (6) k,
the last-bit masked-skin nondeterminism; (7) j, the load sampler at boot on both boxes.

## State (read first when resuming)

Checkpointed at the coordinator's call (tool-call limit). Commits: j 9f5d6f1, the TRELLIS cleanup a08bac4, k 897c987,
notes after. **Gated tip: 897c987** (the commits after it are notes only).

Running when this was written (collect them):
- **The gate** `gate-infra3-0930-161626-6360`: tool/infra5 897c987 into pipeline-3d 0744ffe (pipeline-3d moved from
  b3c5abf to tool/bow's merge; `git merge-tree` merges cleanly). `python -m charkit remote attach
  gate-infra3-0930-161626-6360`; report in charkit/out/gate/gate_tool-infra5_897c987_into_0744ffe.md. Expected under
  K: the candidate builds (garments.py, the manifest and many modules changed); the produced references rebuild once
  (the manifest's `refs` digest changed); the measure-change check flags every QA part (checks.MEASURES is the QA's
  shared code) and runs the 2x2; no value or status should move (only INFO checks' `why` text reads "hull").
- **The after verification build** `build-infra3-0930-161514-424f` (this branch at 897c987, charkit/out/i3d moved away,
  producers and stages from scratch, the closure recorded) into the box copy's `charkit/out/v5_after`. The before build
  (b3c5abf's code, i3d present) finished: 672 s wall, 936 s CPU; **its closure reads no file under charkit/out/i3d**
  (0 read, 0 listed); the produced references' stamps name none (the hull and hair layers read no files, the outfit
  masks the notes and the rig's files); its build log never names i3d. Fetched to
  charkit/out/v5_box/before/{qa/qa.json, bundle/bundle.json, closure.json, build.log}.
- A laptop exploration of the evaluator's parts (scratchpad p4_explore.py; item 4, harmless if lost).

**Next steps, in order:**
1. Attach the gate; read it under K. If pipeline-3d moved again, `gate --carry` (the coordinator decides).
2. When build-infra3-0930-161514-424f ends: its log prints the closure (i3d paths read: must be 0) and the stamps.
   Fetch `charkit/out/v5_after/{qa/qa.json,bundle/bundle.json,closure.json}` as for before and compare: bundle.json's
   `hashes` (every array equal: the rename, the labels and k's no_loose move nothing on the default spec), qa.json's
   checks (values and statuses equal; `why` differs on the INFO checks measured against 'hull'), the produced
   references' content (v5_before/produced vs v5_after/produced: hull.glb, outfit_masks.npz, hair_layers.npz sha256).
   If equal, record the label rename in history (no remeasure: no value changes) as the brief says.
3. Item 4 (pregate coverage), not started beyond a draft: `charkit/evalbundle.py` (uncommitted, untested) turns the
   evaluator's Geometry into a charkit.bundle.Bundle (skin masked/eval at level 1 with the build's skin materials,
   faceeval.features for eyes and mouth, a flat material per tone for hair/accessories/garments, skin/under_garments)
   so `qa3d.evaluate(B, parts=('piece_details', 'face_region', 'details'))` can run. To do: check the evaluator part
   names match the build's object names (pieceqa.piece_map maps pieces to object names), time each part, compare each
   check against the build's own value (v5_before's qa.json: same commit), then wire into pregate's _EVAL (load
   evalbundle.py from this worktree with runpy so an older target tree can run it with its own QA code), and measure
   the agreement with `pregate --against` on today's pairs: tool/face5 36908d0 into 9eba0b0 (gate FAIL on
   sleeve_profile_rough_L 0.0107 WARN -> 0.0146 FAIL; its pre-gates passed), tool/bow cbca3ad into 3ebc3fb, and the
   evalmesh / look6 pairs in infra4.md. Gate-only by construction: the render drawing (art_*, look, face_shadow_*),
   hair_* from the Blender hair, poke/mesh (the build's own meshes), eye renders, the 2x2, tests, CPU.
4. Docs: CHARKIT_HANDOFF.md decision 8's first three bullets are done here (the coordinator's file); its fourth (the
   perceptual metric's own venv on the render box) is provisioning, left.

## 7. j: the load sampler at boot

**Why the build box's per-minute line "stopped" (infra3's question).** It didn't: the one gap in the build box's
2026-09-30 samples, 16:13:02 -> 17:19:02 UTC, is the box being down (stopped 16:14:03, booted 17:17:46 by the kernel's
btime, cron up 17:18:02). The user crontab survived the stop and start; the first sample after the start came 76 s after
boot and had no CPU share (the counters restart at boot, so `cpu` was null: the first CPU reading came at 17:20). The
render box has sampled since its first detached job (10:16 UTC), up 22 h, no gaps. Before: one line on each box
(`* * * * * ... sample ... # boxjob load sampler`), and a gap read as nothing in `remote load`.

**After** (boxjob.py VERSION 3, boxload.py):
- `boxjob.cron_lines`: the per-minute line and `@reboot python3 /srv/work/.jobs/bin/boxjob.py sample --boot`, both with
  the same mark; `cron_merge` adds what's missing and replaces an older line of ours, leaving the owner's other lines. A
  job's start installs them as before (jobs run as the owner through the as-owner session, so it's the owner's crontab).
  VERSION 3: an older client's job no longer overwrites JOBS/bin/boxjob.py with its copy.
- Every sample carries `boot` (the kernel's btime); `sample --boot` adds `event: boot` and resets the CPU baseline, so
  the first minute after a start has its CPU share.
- `remote load` reads each gap of 3 min or more: "the box was down (booted T)" when the boot time changed across it,
  "the box was up, the sampler missed it" when it didn't, "?" for samples from before `boot` was recorded.
- Installed with a no-op job on each box (noop-infra3-0930-155922-e83e build, -155929-26b3 render). `crontab -l` as the
  owner on both: the two lines. `sample --boot` run by hand into a scratch folder on both: exit 0, `event: boot`, boot
  times 2026-09-30T17:17:46Z (build) and 2026-09-29T21:11:52Z (render). The @reboot line itself fires at the next
  boot (no reboot was made: no machine changes).
- Tests: test_boxjob `test_cron_lines_at_boot_and_each_minute`, `test_gaps_read_by_boot_time`.

## 6. k: the masked skin's last-bit nondeterminism

**Measured first.**
- infra3's i A/B (two `--cache off` builds of the default spec, uncapped and capped): 869 bundle arrays, **0 differ**.
- The probe (tools/probe_masked_skin.py; the same reads as charkit.bundle, each after a fresh evaluation; box, detached
  jobs): the default spec's blend (i_before), 5 processes x 6 reads (3 at the default threads, 2 with `-t 1`): eval,
  masked and masked+outline **one hash each** across all 30 reads. clawd_mh's blend (infra2's mhdet1): `eval` one hash;
  `masked` **18 hashes in 18 reads** at the default threads (7-18 vertices of 39393 differ per read, at most
  1.19e-7 m: one float32 ulp), one hash with `-t 1` (both processes the same), one hash with the subdivision off. The
  skin's stack: under_garments (MASK), rig, sub (SUBSURF, level 1), outline, proxy_normals.
- Which vertices: every varying vertex is **loose geometry the mask leaves**: clawd_mh's masked coarse mesh has 65
  vertices in no face and 61 wire edges between them (the default spec's: 0 and 0); all 29 vertices that varied over 8
  reads are among those 65 (none on a face, none a neighbour of one). No SUBSURF setting changes it (limit surface off,
  quality 1 or 6, boundary smooth, creases off, UV smooth: 6 hashes in 6 reads each), and no non-manifold vertex or edge
  is involved (bowties 0 on both). So Blender's subdivision evaluates loose vertices on a threaded path whose last bit
  varies; nothing renders there.

**The fix** (897c987, garments.no_loose): the mask also hides the vertices it would leave in no face (all their faces
dropped), so the masked skin has no loose vertices. A loose edge between two vertices that keep faces stays (the
evaluator's corners, bodyeval.mask_corners, unchanged). The recorded mask_skin call carries the extended set, so the
venv evaluator (geomstage.pieces -> bodyeval) reads the same. On the default spec it hides nothing more (a no-op: the
verification build compares the bundles). On clawd_mh it drops the 65 loose vertices from the masked variant (and adds
them to skin/under_garments); clawd_mh isn't gated. Test: test_bodyeval `test_no_loose_hides_what_the_mask_leaves_in_no_face`.

## 5. The TRELLIS cleanup (decision 8)

What changed (a08bac4):
- **Not shipped any more:** bucketsync (sync_paths no longer lists charkit/out/i3d; `managed` leaves a copy's own i3d
  alone like the rest of charkit/out; `no_i3d` and `seed_i3d` gone), build.sh's rsync path and first-sync seed,
  remote.py's seed tarball and the gate clone's i3d link and push (`GI`), gate.py's `_link_inputs` (the gate's
  worktrees), preview's worktree copy, tools/worktree.sh's clone. Box copies keep whatever i3d they have; nothing reads
  or deletes it.
- **Renamed:** charkit.i3d -> **charkit.target3d** ("the 3D target as kit data": the GLB loader with texture colours, the
  eyes (sidecar or colour), the eye alignment, the hair split by colour). 76 references in 23 files.
- **Labels:** the reference label 'trellis' -> **'hull'** in checks.MEASURES (face_shape_*, shape_iou*), bodyfit's and
  facefit's AUTHORITY and terms, and their tests. The manifest's authority names neither (face_depth and hair_shape
  have none), so no grade moves; the INFO checks' `why` text reads "measured against hull".
- **The manifest:** the 'trellis' reference (its GLB in charkit/out/i3d) removed, with a dated note; key3d's role no
  longer says "the TRELLIS input". This changes the produced references' stamps (the `refs` part hashes the manifest's
  references' sha256s): the hull, outfit masks and hair layers rebuild once in each copy. The outfit graph's provenance
  still names the field it was made with (history; regenerating it is the garment owners' call, outfit-source item 6).
- charkit/spec/clawd_locks.json's `ref.image` points at the tracked key3d (the same sha256) instead of i3d/in.
- **Retired:** tools/imageto3d/trellis_remote.sh. trellis_ext/ and trellis_run.py stay as research history, unwired
  (docs/TOOLS.md says so).
- Tests: the real-GLB geom tests run only when CHARKIT_GEOM_GLB names one (they defaulted to the TRELLIS GLB);
  cache_builds.py's `glb` case uses the hull's GLB with its eyes.
- Left: decision 8's fourth bullet (the perceptual metric's own environment on the render box: it still runs in the
  TRELLIS venv, `/srv/work/trellis2/.venv`) is provisioning, not done here.

---

# Infra round 5, part B (tool/infra5-s, 2026-10-01): tasks 5, 7, 8

Worktree `~/animation-pipeline-infra5s`, branch `tool/infra5-s` from pipeline-3d 60c0f1a4. Brief:
`~/animation-pipeline-3d/charkit/out/coord/brief_infra5.md` (tasks 5, 7, 8 here; tool/infra5-o owns 1-4 and 6: gate.py
and the build stages are theirs; tool/build2 owns remote.py's pick_box/box_slots and test_procs.py's slots).

## State (read first when resuming)

Commits: 204d1f7d (the stopped agent's calibrate writes by replace: kept), cae5b57b (task 5, cow), a22ad464 (task 7,
stall alarm), d91f159e (task 8, gates before sweeps). The stopped agent's uncommitted boxjob/remote edits are in
`git stash list` ("infra5-s: stopped agent wip (boxjob, remote)"): reviewed, its flags/limits design reused in a22ad464;
the stash can be dropped. Next: the box demos (cow reproduction, planted silent job), full suite, pregate, gate.

## 5. The calibrate PermissionError

**Measured.** Of the 22 calibrate jobs that failed on 2026-10-01, 9 died on PermissionError (8 build box, 1 render2): 2
rewriting `charkit/calib/records/*.json` (calibrate's records, in worktrees from before tool/hands2's records-only fix
8580945f), 7 rewriting `charkit/calib/known_bad/*.json` (`calibrate store`). The other 13: FileNotFoundError, NameError,
a calibration that failed its triple, and 4 killed (rc 143). The files: mode 444, link count 2-11, owned by the box's
owner: **root cause:** a box copy hard-links every synced file read-only from the box's blob cache
(charkit/bucketsync.py, by design: a write through a link must not reach every copy sharing the blob), so any command
that rewrites a tracked file in place there fails. Not another worktree's or user's file. Fixing writers one at a time
(8580945f records, then 204d1f7d store/accept) leaves the next one.

**Fix (cae5b57b, charkit/cow.py):** copy on write for a box copy's linked inputs. charkit/__init__.py installs an audit
hook when the package itself is a read-only hard link (`charkit/__init__.py` nlink > 1 and not owner-writable: a box
copy; never a worktree or a gate's git clone). Before any open for writing of a read-only hard-linked regular file under
the copy, the path gets a private writable file: a truncating write unlinks the link (the open creates a new file),
anything else (append, r+, os.open without O_TRUNC) copies and renames over it. The blob and the other copies are
untouched; only opens that would have failed change. CHARKIT_COW=0 off, =1 forced. Cost: 0.09 us per audit event
(2M id() calls: 0.068 -> 0.161 us); test_bodyeval's run raises ~212k events (~20 ms on 14 s CPU, 0.14%); gates don't
install it. Not covered: non-Python writers (shell redirects, Blender's C code).
Test (charkit/tests/test_cow.py): a fake box made with bucketsync.place (read-only blobs, two copies linked to them);
the 2026-10-01 writes as the failed jobs made them (calibrate store's known_bad line, the records line) plus append,
os.open O_WRONLY, np.save and shutil.copyfile: PermissionError without the hook (reproduces), all succeed with it, the
blobs and the other copy unchanged, each written file now nlink 1 and writable; a link outside the copy and a lone
read-only file are left to fail; `import charkit` from a linked package installs it, CHARKIT_COW=0 doesn't.
Box demonstration: see "Box demos" below.

## 7. Stall alarm and time budgets

**Measured first** (the box's kept jobs, rc 0, both boxes): a gate's log is 3 lines written at its end (100 of 102:
silent throughout; duration p50 10.4, p90 17.1, max 36.5 min); a pregate's 1 line (max 20 min); builds (41 lines
median), sweeps, accfit, hand write as they go; qa is short (max 12.5 min). A live sample (the new sampler run once into
a scratch folder on each box) found a sharded `sweep run --jobs 4` with 0 bytes after 17 min: sharded sweeps printed
nothing until their end.

**What changed (a22ad464, d91f159e's sweep part):**
- boxjob `info` (and `list`): `last_write` (the log's mtime: the kernel's record of the last write), `expect_min`,
  `stall_min` and `flags` for a running job: SILENT past its limit (its own `stall_min`, else STALL_MIN: default 20,
  gate 45, pregate 30), OVERRUN past 2x its `expect_min`. Nothing is killed.
- `remote jobs`: a running job's quiet minutes, the box line counts FLAGGED jobs, each alarm under its job with what to
  do (`remote attach`, `remote kill`). `remote jobs --silences [--days N]`: per box and kind, the longest silence of
  each job (from the sampler) for jobs that ended rc 0 and apart the others, against the limit.
- Declaring: `remote build|tune|gate|pregate [--expect MIN] [--stall MIN] ...`, `remote run [--fetch DIR] [--expect
  MIN] [--stall MIN] CMD`, or CHARKIT_JOB_EXPECT_MIN / CHARKIT_JOB_STALL_MIN; kept in the job's meta and local record.
  (Parsed in the commands, not remote.main, to stay clear of tool/build2's main.)
- The follow (`remote attach`, every remote command) prints the alarm once per silence.
- The load sampler (boxjob VERSION 4) records `quiet`: each running job's log bytes and seconds since its last write,
  each minute. Installed on a box by the next job sent from this branch (JOBS/bin/boxjob.py; a VERSION 3 job doesn't
  downgrade it). Note for the merge: build2's boxjob.py stays VERSION 3; the merged file should be VERSION 5 so every
  box takes the merged sampler.
- Sharded sweeps pass their shards' lines on as they're written (`  [shard i] ...`), so the alarm reads real progress.
- Tests (test_boxjob): planted silent / overrun / finished jobs (9 cases, both alarms, own limit), quiet and silences
  per kind, the follow's alarm once.

## 8. Gates before sweeps

**What changed (d91f159e, charkit/procs.py):** slot priorities: gate (CHARKIT_SLOT_PRIO=gate, set by boxjob's supervisor
for kinds gate and pregate; a waiter from older code counts as a gate when its root is a gate's or pre-gate's clone
under /srv/work), normal (default), low (procs.background(): sweeps call it in sweep.main, so optimize, its workers,
shards and confirm builds inherit it; also CPU niceness 10). A free slot goes to a waiting gate first (normal and low
acquirers wait while one waits); a low holder gives its slot to a gate waiting for slots between rows (claimed once per
gate wait: slots/wait/<pid>.given) and takes one again behind it: sweep shards and single sweeps between rows (run_rows'
`between`), swap between measurements, optimize workers before a row (reply `yielded`: the pool puts the row back for
another worker, the worker reports `resumed` once it has a slot again). acquire_slot returns a Slot (close(), claim(),
give(), yield_point()). CHARKIT_SLOTS_DIR (tests), CHARKIT_SLOT_YIELD=0 (off).

**Measured:**
| | without | with |
|---|---|---|
| gate's slot wait, 2 slots held by 2 background workers (12 rows x 0.25 s), gate at 0.6 s (test_slotprio) | 2.51 s | 0.21 s |
| CPU share of a loop sharing one build-box core with a nice-0 loop (taskset, 6 s) | 50.1% (nice 0) | 9.7% (nice 10) |
On the box the first row's scale is minutes: an optimize run's workers held their slots for its whole run (60 min on
2026-10-01); a gate now waits for one row at most.
Tests: charkit/tests/test_slotprio.py (the latency above with and without yielding, one yield per gate; a gate before a
normal build for a freed slot; priorities from env and tree; background()'s niceness inherited and sweep.main calling it;
the optimize pool moving a yielded row to the other worker, results equal to in-process). Known order dependency
unchanged: test_optimize before test_procs (CHARKIT_SLOT_HELD from test_optimize's import; tool/build2 fixes
test_procs' isolation); test_slotprio restores the environment it found.

## Box demos

(pending: the planted silent job, the cow reproduction on the box)
