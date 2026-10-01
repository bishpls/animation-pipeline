# build2: a third box, and load-aware box routing (tool/build2)

State (2026-10-01): build2 is provisioned, installed and verified (under the owner's login); --box auto routes by load
and is the default. **One blocker, Michael's:** the box-control service account has no rights on build2 yet (its grants
are per instance; this branch was not allowed IAM changes), so with the service account, which every env file uses,
build2 reads as `unknown` and the picker skips it. The three grants are under "For Michael". Real names (project, VMs,
service accounts, bucket) live only in the gitignored `infra/gcp/*.env`; this file says "the build box", "build2",
"render2", "the box-control service account".

## Why

Michael, 2026-10-01: "Even if we're technically under capacity still, if it's slowing down iteration, it's worth the
minor cost of another box." Over the 2 h before: the build box (32 vCPU) at a mean 73% CPU, >=90% in 32% of minutes,
load peaking at 129 (about 4 runnable tasks per core); a second character's hull took 492 s there against 178 s on the
laptop; render2 (32 vCPU) averaged 18%. Slots never queued: a build's slot doesn't bound its CPU, and the slot-based
picker (the build box while it had 4 free slots) never saw the oversubscription.

## Task A: the box

- **Provisioning.** `infra/gcp/build-provision.sh` takes its config from `CHARKIT_BOX_ENV` (default build.env) and runs
  on the caller's own gcloud login: the env file's CLOUDSDK_CONFIG (the box-control service account's, which can't
  create VMs) is set aside. `DISK_TYPE` is optional (default pd-balanced; a C4 would need hyperdisk-balanced).
  `CHARKIT_BOX_ENV=infra/gcp/build2.env infra/gcp/build-provision.sh [--execute]`.
- **build2.env** (gitignored, copied into the 28 worktrees that had a build.env; not the main checkout): build.env with
  its own VM (the build box's name with a 2), `MACHINE_TYPE=c3-standard-44` (44 vCPU, 176 GB, Sapphire Rapids),
  `ZONE` the region's third zone, `SLOTS=20`, `CPU_SPEED=1.25`. Same network, service account, bucket, image, disk
  (200 GB pd-balanced), Blender 5.2.2, Python 3.14, labels, IDLE_MINUTES 30, network tag (so the existing IAP-SSH
  firewall rule covers it: nothing else was created).
- **Quota, checked first:** the region's C3 CPUs 0 of 300 in use (44 needed), regional CPUS 10 of 3000. The global
  all-regions CPU quota isn't readable (the Cloud Quotas API isn't enabled; not enabled here).
- **Zone.** c3-standard-44 was stocked out in the build box's zone twice in a row (offered there, no capacity); it was
  created in the region's third zone at the first try. Same regional subnet, NAT and firewall rule; the zone is only in
  the env file. (Restarts after the idle stop can hit a stockout too: build2.env has no FALLBACK_MACHINE_TYPE.)
- **Install:** the boot script ran to READY in 62 s (Blender 5.2.2, the venv). The venv got numba 0.68.0 / llvmlite
  0.50.0 (the build box and the laptop: 0.67.0 / 0.49.0); pinned to the build box's after the comparison below (which
  was bit-identical with either). numpy 2.5.3, scipy 1.18.1, scikit-image 0.26.0, manifold3d 3.5.4, opencv 5.0.0.93,
  wgpu 0.32.0: the same on both.
- **Gate clone seeded:** /srv/work/repo on build2 cloned from a bundle of the build box's clone, through the bucket
  (1.87 GB: 34 s to bundle and upload, 39 s to download and clone; the bucket object deleted). A first gate there now
  sends about 31 MB (the commits since the seed's pipeline-3d head) instead of the whole history (~1.8 GB from the laptop).
- **Cost (us-east4 on-demand list):** build2 about $2.22/h while running (44 x $0.03465 core + 176 GB x $0.003938
  RAM); the build box about $1.75/h. The 200 GB disk is about $22/month, stopped or not. It stops itself after 30 idle
  minutes.

### Verified (with the owner's own login: the service account can't reach build2 yet)

- `python -m charkit remote --box build2 run slots`: up, bucket sync, detached job; "build slots: 20" (22 before SLOTS
  was set). The default `remote run slots` (no --box) read all four boxes in parallel and chose build2: 13 s end to end.
- **Bit for bit.** The same QA-only build of charkit/spec/clawd.json on both boxes (`--boards '' --no-blend --cache off`,
  CHARKIT_PRODUCED_CACHE=off, so neither box reused anything): 50 files each, 42 byte-identical. The other 8 differ only
  in timings (build_cpu.json, trace.jsonl, garments.json's seconds, qa_motion.json's seconds, 71 of qa.json's 72
  differing values) and in the output folder's name (clawd.spec.json and pieces.spec.json identical once
  `b2cmp/build2` reads `b2cmp/build`; bundle.json's content digest covers its meta, which holds that path: recomputed
  with the path normalised, both are 916ed1de05). Every QA value and the bundle's data are identical. The outputs:
  charkit/out/b2cmp/{build,build2} in tool/build2's worktree (gitignored).
- **Wall time, the same job:** build2 idle 879 s (1,525 CPU-s: 1.7 cores on average) against the build box 2,961 s
  (2,262 CPU-s) at load 50-65 on its 32 vCPUs (other agents' work): 3.4x, mostly the build box's oversubscription.
  Phases, build2 / build box: resolve 193 / 833 s, hair_select 54 / 248, pieces_hair 115 / 476, Blender 97 / 406, QA
  405 / 949.
- **Per-core speed, single thread** (best of 7, three rounds; build2 idle, the build box never idle):

  | workload (s) | build2 (load 0.1) | build box, run 1 (load 21) | build box, run 2 (load 18) | render2 (load 12) |
  |---|---|---|---|---|
  | Python loop | 0.351 | 0.661 | 0.408 | 0.678 |
  | numpy matmul, 1 thread | 0.177 | 0.220 | 0.200 | 0.208 |
  | numpy sort | 0.112 | 0.170 | 0.172 | 0.155 |

  build2 against the build box's cleaner run: 1.16x, 1.13x, 1.54x (geomean 1.26); run 1 shows what busy SMT siblings
  cost (the Python loop 1.6x slower). `CPU_SPEED=1.25` for build2. render2 is mixed (geomean ~0.86, under its own
  load): left at 1.0.
- **SLOTS=20:** one build on idle build2 averaged 1.7 cores (peak ~2.9 at one-minute samples) and +6.3 GB; 44 vCPU /
  (1.7 x 1.3) = 20, and 20 x 6.3 GB is well under its 170 GB available (the build box: 16 for 32 vCPU).
- The idle stop's timer runs; the load sampler's crontab is installed (the first job).

## Task B: --box auto by load, the default

- **boxjob `slots`** (`reading()`): the slots, plus the box's cores, its 1/5/15-minute load, memory available and GPU use.
- **box_slots(env)**: those, with `cpu_free` = (cores - 1-minute load) x CPU_SPEED, `gpu` (MACHINE_GPU in the env
  file), `speed`. Reading a box no longer changes the chosen one: `_env`, `_cfg`, `_box_status`, `_sh` take an env
  file, and `_genv` gives each box's gcloud and ssh calls its own CLOUDSDK_CONFIG.
- **choose(readings, reserve, gpu, need, wake)**, pure, so the tests feed it readings:
  - room: running, and a free slot beyond the reserve; among those, the most `cpu_free` (a render box taking CPU work
    counts GPU_KEEP = 4 fewer cores); ties to a CPU box, then the env order (build, render, then by name);
  - no slot beyond the reserve anywhere: the most free slots (the shortest wait);
  - busy (the choice has under MIN_FREE = 4 free cores, or no slot): a stopped CPU box is started instead
    (CHARKIT_BOX_WAKE=0: never); a render box only for --gpu; a box gcloud can't read (`unknown`) is never started;
  - `gpu` (a build whose boards render in EEVEE: `--boards` not '' (the default draws four sets) and not
    `--boards-renderer toon`; tune): a render box with room and MIN_FREE cores first, else as a CPU job (a CPU box
    draws the boards with the toon renderer, said in the log); `need` (`--gpu`): only a render box.
- **pick_box()**: every box read in parallel (~3 s for four), each reading logged
  (`box build2   44 vCPU, load 0.6: 54.3 cores free (x1.25 per core); 20 of 20 slots free (0 held, 0 waiting)`), then
  choose; nothing running and nothing to start: the build box, which the command's up() starts.
- **Where it applies:** `remote build | tune | run | gate` with no --box (or `--box auto`); `CHARKIT_BOX=NAME` makes
  another default; `--box NAME` wins; `--gpu` anywhere in the command. `charkit sweep --box`, `sweep optimize --box`
  and `pregate --box` with no name now mean auto (they meant the build box). Unchanged: up/status/stop (the build
  box), jobs/load (every box), attach/kill (the job's own box), evaldrift/perceptual/parity/preview (their own boxes).
  A chosen box that's stopped is started by route(); when it won't start, the best running box instead.
- **Gates:** one live gate per branch across every running box (supersede lists and stops this branch's older gate
  for the same spec wherever auto sent it). Gate baselines (/srv/work/gate-out) and the produced cache are per box: the
  first gate into a commit on a box builds its baseline there.
- **Tests:** charkit/tests/test_boxpick.py (13: free CPU beats free slots, speed weighting, reserve and full slots,
  ties, boards' render-box preference, --gpu, waking a stopped box, unreadable boxes, wants_gpu, pick_box's parallel
  read and log, main's routing and defaults, supersede across boxes, boxjob's reading). test_procs now runs every test
  on a temporary slots directory with the slot variables cleared: test_optimize and test_sweep set CHARKIT_SLOT_HELD at
  import, which made test_slots_queue_and_release fail in the full suite (reproduced before the fix: `assert 0 == 2`).
- **Full suite on the laptop:** 727 passed, 2 failed: test_optimize's qa stage and test_registry's order, the two
  remaining known order-dependent ones; each passes alone.

## For Michael

1. **Grant the box-control service account build2** (your login; the same as the other boxes have): the instance-level
   box-instance custom role and `roles/compute.osAdminLogin` on build2's instance, and build2 added to the condition
   of the service account's project-level `roles/iap.tunnelResourceAccessor` binding (port 22 on a list of instance
   IDs, the three other boxes'; build2's resource name: `projects/<number>/iap_tunnel/zones/<build2's
   zone>/instances/<build2's id>`). The exact commands are in tool/build2's report to the coordinator.
2. Then, with the service account's config (the env file's): `CHARKIT_BOX_ENV=infra/gcp/build2.env
   infra/gcp/as-owner.sh install` (the owner's home on build2 exists), then `python -m charkit remote --box build2 run
   slots` and `python -m charkit remote run slots` (should choose build2 while the build box is busier).
3. Cost: about $2.22/h while it runs, about $22/month for the disk.

## Next steps / follow-ups

- After the grants: steps 2 above, then `remote load --box build2` after a day for its utilisation.
- render2's slots bind (10 of 10 held, 3-4 waiting, at load 12, 2026-10-01 20:00 UTC): board builds hold a slot for a
  whole build. Its SLOTS (10) may be low for its CPU; the picker now sends CPU work elsewhere when it's full.
- sweep optimize's worker count on a box still comes from its free slots, not its free CPU (optimize.Run.n_workers).
- build.sh writes a default-login ssh config with no CLOUDSDK_CONFIG in its ProxyCommand, so a plain `ssh -F` there
  inherits the caller's; remote.py's multi-box calls now pass each box's own (_genv). `env -u CLOUDSDK_CONFIG` in that
  ProxyCommand would make the file self-contained.
- build-startup.sh installs unpinned packages: a box built later drifts (build2's numba). A pinned list beside it
  (the laptop's versions) would keep the boxes identical.
