# Gate tooling round 5 (tool/infra5, 2026-09-30)

Worktree `~/animation-pipeline-infra3`, branch `tool/infra5` from pipeline-3d b3c5abf. The brief (infra4's items 4-7):
(4) pregate's coverage (sleeve, face) and its agreement with the real gate; (5) the TRELLIS cleanup (decision 8); (6) k,
the last-bit masked-skin nondeterminism; (7) j, the load sampler at boot on both boxes.

## State (read first when resuming)

- j (9f5d6f1): done, installed on both boxes, tested. Not gated yet.
- 5 (a08bac4) and k (897c987): code done, unit tests pass locally. The verification builds (before: b3c5abf's code with
  charkit/out/i3d present; after: this branch with it absent; both `--cache off`, producers from scratch, the closure
  recorded) run on the build box in this worktree's copy (`charkit/out/v5_before`, `v5_after`). Then the gate.
- 4: not started.

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
