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
